from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import uvicorn
from dash import Dash, Input, Output
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog
from pring_cycle.dashboard import dashboard_page, dashboard_shell
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.health_types import RuntimeHealthDocument
from pring_cycle.logging import write_runtime_event
from pring_cycle.maintenance import mutation_rejection
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.release_calendar import current_lpr_period, lpr_release_calendar
from pring_cycle.reports import ReportRepository, ReportSnapshot
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import (
    RuntimeNotInitializedError,
    RuntimePaths,
    runtime_health,
)
from pring_cycle.storage import database_health

COMMAND_BODY_LIMIT = 4096


def create_web_application(paths: RuntimePaths, port: int) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        write_runtime_event(paths, "web", "web_started")
        try:
            yield
        finally:
            write_runtime_event(paths, "web", "web_stopped")

    server = FastAPI(
        docs_url=None,
        lifespan=lifespan,
        openapi_url=None,
        redoc_url=None,
        title="Pring local runtime",
    )

    @server.get("/api/v1/health", name="runtime_health")
    def health() -> RuntimeHealthDocument:
        return runtime_health(paths, port)

    @server.get("/api/v1/projections/current", name="current_projection")
    def current_projection() -> JSONResponse:
        projection = _current_projection(paths)
        if projection is None:
            return JSONResponse(
                status_code=404,
                content={"error": "current_projection_unavailable", "status": "unavailable"},
            )
        return JSONResponse(content=jsonable_encoder(_projection_document(projection)))

    @server.get(
        "/api/v1/projections/current/{dataset_name}",
        name="current_projection_dataset",
    )
    def current_projection_dataset(dataset_name: str) -> JSONResponse:
        projection = _current_projection(paths)
        if projection is None:
            return JSONResponse(
                status_code=404,
                content={"error": "current_projection_unavailable", "status": "unavailable"},
            )
        if dataset_name not in projection.datasets:
            return JSONResponse(
                status_code=404,
                content={"error": "projection_dataset_not_found", "status": "unavailable"},
            )
        document = {
            "envelope": _projection_document(projection)["envelope"],
            "dataset_name": dataset_name,
            "data": projection.datasets[dataset_name],
        }
        return JSONResponse(content=jsonable_encoder(document))

    @server.get("/api/v1/evidence/{observation_id}", name="evidence_trace")
    def evidence_trace(
        observation_id: str,
        mode: AsOfMode,
        as_of: datetime,
    ) -> JSONResponse:
        result = EvidenceRepository(paths.database).trace(
            observation_id,
            mode=mode,
            as_of=as_of,
        )
        return JSONResponse(content=jsonable_encoder(asdict(result)))

    @server.get("/api/v1/catalog", name="metric_catalog")
    def catalog() -> dict[str, object]:
        return {
            "catalog_version": METRIC_CATALOG_VERSION,
            "metrics": [asdict(item) for item in metric_catalog()],
        }

    @server.get("/api/v1/release-calendar", name="release_calendar")
    def release_calendar_view(period: str, as_of: datetime) -> dict[str, object]:
        return {
            "events": [
                asdict(item)
                for item in lpr_release_calendar(
                    EvidenceRepository(paths.database),
                    period=period,
                    as_of=as_of,
                )
            ],
            "status": "ok",
        }

    @server.get("/api/v1/runs", name="run_index")
    def run_index() -> list[dict[str, object]]:
        return [asdict(item) for item in _runs(paths)]

    @server.get("/api/v1/reports", name="report_index")
    def report_index() -> list[dict[str, object]]:
        return [asdict(item) for item in _reports(paths)]

    @server.get("/api/v1/reports/{report_snapshot_id}", name="report_detail")
    def report_detail(report_snapshot_id: str) -> JSONResponse:
        repository = ReportRepository(paths.database)
        try:
            snapshot = repository.get(report_snapshot_id)
        except LookupError:
            return JSONResponse(
                status_code=404,
                content={"error": "report_snapshot_not_found", "status": "unavailable"},
            )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "attempts": [asdict(item) for item in repository.attempts(report_snapshot_id)],
                    "snapshot": asdict(snapshot),
                }
            )
        )

    @server.get("/api/v1/models", name="model_index")
    def model_index() -> list[dict[str, object]]:
        return [asdict(item) for item in ModelRepository(paths.database).list_versions()]

    @server.get("/api/v1/stage-history", name="stage_history")
    def stage_history() -> dict[str, object]:
        return {
            "events": list(ProjectionSetRepository(paths.database).stage_history()),
            "status": "ok",
        }

    @server.get("/api/v1/gap-notices", name="gap_notice_index")
    def gap_notice_index() -> dict[str, object]:
        return {
            "notices": list(ProjectionSetRepository(paths.database).gap_notices()),
            "status": "ok",
        }

    @server.post("/api/v1/commands", response_model=None, name="append_command")
    async def append_command(request: Request) -> JSONResponse:
        rejection = _command_origin_rejection(request, port)
        if rejection is not None:
            return rejection
        payload, parse_rejection = await _command_payload(request)
        if parse_rejection is not None:
            return parse_rejection
        assert payload is not None
        try:
            document = _persist_command(paths, payload)
        except (KeyError, LookupError, TypeError, ValueError) as error:
            return JSONResponse(
                status_code=409,
                content={"error": str(error), "status": "rejected"},
            )
        return JSONResponse(status_code=202, content=jsonable_encoder(document))

    dashboard = Dash(
        __name__,
        server=cast(Any, server),
        title="Pring 本机运行状态",
        assets_folder=str(Path(__file__).with_name("assets")),
        suppress_callback_exceptions=True,
        update_title="更新投影视图…",
    )
    dashboard.layout = lambda: dashboard_shell(
        _current_projection(paths),
        _runs(paths),
        _reports(paths),
    )

    @dashboard.callback(Output("page-content", "children"), Input("dashboard-location", "pathname"))
    def route_dashboard(pathname: str | None) -> object:
        return dashboard_page(
            pathname,
            _current_projection(paths),
            _runs(paths),
            _reports(paths),
            _stage_history(paths),
            _release_calendar_events(paths),
        )

    return server


def run_web(paths: RuntimePaths, port: int) -> None:
    if database_health(paths.database)["status"] != "ok":
        raise RuntimeNotInitializedError("runtime_not_initialized")
    if not 1 <= port <= 65535:
        raise ValueError("invalid_port")
    uvicorn.run(
        create_web_application(paths, port),
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
    )


def _current_projection(paths: RuntimePaths) -> ProjectionSet | None:
    try:
        return ProjectionSetRepository(paths.database).current()
    except (LookupError, OSError):
        return None


def _runs(paths: RuntimePaths) -> tuple[RunRecord, ...]:
    try:
        return RunRepository(paths.database).list_runs()
    except (OSError, ValueError):
        return ()


def _reports(paths: RuntimePaths) -> tuple[ReportSnapshot, ...]:
    try:
        return ReportRepository(paths.database).history()
    except (OSError, ValueError):
        return ()


def _stage_history(paths: RuntimePaths) -> tuple[dict[str, object], ...]:
    try:
        return ProjectionSetRepository(paths.database).stage_history()
    except (OSError, ValueError):
        return ()


def _release_calendar_events(paths: RuntimePaths) -> tuple[dict[str, object], ...]:
    now = datetime.now(UTC)
    try:
        return tuple(
            asdict(item)
            for item in lpr_release_calendar(
                EvidenceRepository(paths.database),
                period=current_lpr_period(now),
                as_of=now,
            )
        )
    except (OSError, ValueError):
        return ()


def _projection_document(projection: ProjectionSet) -> dict[str, object]:
    return {
        "envelope": asdict(projection.envelope),
        "datasets": projection.datasets,
    }


def _command_origin_rejection(request: Request, port: int) -> JSONResponse | None:
    trusted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    trusted_origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    if (
        request.headers.get("host") not in trusted_hosts
        or request.headers.get("origin") not in trusted_origins
    ):
        return JSONResponse(
            status_code=403,
            content={"error": "untrusted_local_command_origin", "status": "rejected"},
        )
    return None


async def _command_payload(
    request: Request,
) -> tuple[dict[str, object] | None, JSONResponse | None]:
    content_length = request.headers.get("content-length")
    try:
        declared_size = int(content_length) if content_length is not None else 0
    except ValueError:
        return None, JSONResponse(
            status_code=400,
            content={"error": "invalid_content_length", "status": "rejected"},
        )
    if declared_size > COMMAND_BODY_LIMIT:
        return None, JSONResponse(
            status_code=413,
            content={"error": "command_body_too_large", "status": "rejected"},
        )
    body = bytearray()
    async for body_chunk in request.stream():
        body.extend(body_chunk)
        if len(body) > COMMAND_BODY_LIMIT:
            return None, JSONResponse(
                status_code=413,
                content={"error": "command_body_too_large", "status": "rejected"},
            )
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, JSONResponse(
            status_code=400,
            content={"error": "invalid_command_json", "status": "rejected"},
        )
    if not isinstance(value, dict):
        return None, JSONResponse(
            status_code=400,
            content={"error": "command_body_must_be_object", "status": "rejected"},
        )
    return {str(key): item for key, item in value.items()}, None


def _persist_command(paths: RuntimePaths, payload: dict[str, object]) -> dict[str, object]:
    command = str(payload["command"])
    rejection = mutation_rejection(
        paths.database,
        paths.data,
        non_core_large_task=command in {"report_generation", "manual_deep_search"},
    )
    if rejection is not None:
        raise ValueError(rejection)
    if command == "data_gap_notice":
        return ProjectionSetRepository(paths.database).create_gap_notice(
            str(payload["assessment_id"]),
            client_request_id=str(payload["client_request_id"]),
        )
    repository = RunRepository(paths.database)
    if command == "resume":
        run = repository.resume(
            str(payload["run_id"]),
            client_request_id=str(payload["client_request_id"]),
            confirm_external_calls=payload.get("confirm_external_calls") is True,
        )
    elif command == "cancel":
        run = repository.cancel(str(payload["run_id"]))
    else:
        model_version_id = str(payload.get("model_version_id") or _default_model(paths))
        run = repository.submit(
            command_type=command,
            target_business_date=str(payload["target_business_date"]),
            client_request_id=str(payload["client_request_id"]),
            model_version_id=model_version_id,
            system_as_of=datetime.now(UTC),
        )
    return {
        "accepted_at": datetime.now(UTC).isoformat(),
        "client_request_id": str(payload["client_request_id"]),
        "run_id": run.run_id,
        "status": run.status,
        "target_projection_set_id": run.projection_set_id,
    }


def _default_model(paths: RuntimePaths) -> str:
    repository = ModelRepository(paths.database)
    try:
        return repository.active().model_version_id
    except LookupError:
        raise LookupError("active_model_unavailable") from None
