from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.domain.trend import TrendRules, trend_rules_from_manifest
from pring_cycle.evidence import (
    AsOfMode,
    DerivedEvidenceTrace,
    EvidenceRepository,
    EvidenceTrace,
)
from pring_cycle.health_types import RuntimeHealthDocument
from pring_cycle.logging import write_runtime_event
from pring_cycle.maintenance import mutation_rejection
from pring_cycle.models import ModelRepository
from pring_cycle.navigation import DASHBOARD_NAVIGATION, LEGACY_ROUTES
from pring_cycle.page_identity import identity_fields
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.release_calendar import current_lpr_period, lpr_release_calendar
from pring_cycle.reports import ReportRepository, ReportSnapshot
from pring_cycle.run_health import ProducerRun, RunHealth, comparison, filtered_flow
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import (
    RuntimeNotInitializedError,
    RuntimePaths,
    runtime_health,
)
from pring_cycle.source_contract_review import (
    active_source_contract_review,
    require_model_source_contract,
)
from pring_cycle.storage import database_health
from pring_cycle.web_config import HostBoundary, WebConfig
from pring_cycle.wording import macro_title, stage_title

COMMAND_BODY_LIMIT = 4096


def create_web_application(
    paths: RuntimePaths,
    port: int | None = None,
    *,
    eager_dashboard: bool = True,
) -> FastAPI:
    config = WebConfig.read(paths, port)
    dashboard_state: dict[str, object] = {}

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        write_runtime_event(paths, "web", "web_started")
        if not eager_dashboard:
            threading.Thread(
                target=_load_deferred_dashboard,
                args=(dashboard_mount, paths, dashboard_state),
                daemon=True,
                name="pring-dashboard-loader",
            ).start()
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

    server.add_middleware(HostBoundary, config=config)

    @server.get("/api/v1/health", name="runtime_health")
    def health() -> RuntimeHealthDocument:
        return runtime_health(paths, config=config)

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

    @server.get("/api/v1/projections/{projection_id}", name="pinned_projection")
    def pinned_projection(projection_id: str) -> JSONResponse:
        try:
            projection = ProjectionSetRepository(paths.database).get(projection_id)
        except LookupError:
            return JSONResponse(status_code=404, content={"error": "projection_not_found"})
        return JSONResponse(content=jsonable_encoder(_projection_document(projection)))

    @server.get("/api/v1/projections/{projection_id}/{dataset_name}", name="pinned_dataset")
    def pinned_dataset(projection_id: str, dataset_name: str) -> JSONResponse:
        try:
            projection = ProjectionSetRepository(paths.database).get(projection_id)
        except LookupError:
            return JSONResponse(status_code=404, content={"error": "projection_not_found"})
        if dataset_name not in projection.datasets:
            return JSONResponse(status_code=404, content={"error": "projection_dataset_not_found"})
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "envelope": _projection_document(projection)["envelope"],
                    "dataset_name": dataset_name,
                    "data": projection.datasets[dataset_name],
                }
            )
        )

    @server.get("/api/v1/projection-evidence/{projection_id}/{version_id}")
    def projection_evidence(projection_id: str, version_id: str, trail: str = "") -> JSONResponse:
        try:
            projection = ProjectionSetRepository(paths.database).get(projection_id)
            document = _frozen_evidence(paths, projection, version_id, trail=trail)
        except LookupError as error:
            return JSONResponse(status_code=404, content={"error": str(error)})
        return JSONResponse(content=jsonable_encoder(document))

    @server.get("/api/v1/projection-evidence/{projection_id}")
    def projection_evidence_search(projection_id: str, q: str = "") -> JSONResponse:
        try:
            projection = ProjectionSetRepository(paths.database).get(projection_id)
            rows = EvidenceRepository(paths.database).search_frozen(
                projection.envelope.evidence_snapshot_id, q
            )
        except LookupError as error:
            return JSONResponse(status_code=404, content={"error": str(error)})
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "projection_set_id": projection_id,
                    "system_as_of": projection.envelope.system_as_of,
                    "results": rows,
                    "limit": 100,
                }
            )
        )

    @server.get("/api/v1/evidence/{observation_id}", name="evidence_trace")
    def evidence_trace(
        observation_id: str,
        mode: AsOfMode,
        as_of: datetime,
    ) -> JSONResponse:
        repository = EvidenceRepository(paths.database)
        result: EvidenceTrace | DerivedEvidenceTrace
        try:
            result = repository.trace(
                observation_id,
                mode=mode,
                as_of=as_of,
            )
        except LookupError:
            result = repository.derived_trace(
                observation_id,
                mode=mode,
                as_of=as_of,
            )
        return JSONResponse(content=jsonable_encoder(asdict(result)))

    @server.get("/api/v1/acquisitions", name="acquisition_index")
    def acquisition_index() -> dict[str, object]:
        return {
            "acquisitions": [
                asdict(receipt)
                for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
            ]
        }

    @server.get(
        "/api/v1/acquisitions/{acquisition_id}/artifacts/{kind}",
        name="acquisition_artifact",
    )
    def acquisition_artifact(acquisition_id: str, kind: str, view: bool = False) -> Response:
        try:
            content = AcquisitionRepository(paths.database, paths.artifacts).read_content(
                acquisition_id, kind
            )
        except FileNotFoundError:
            return JSONResponse(status_code=404, content={"error": "artifact_file_missing"})
        except LookupError as error:
            return JSONResponse(
                status_code=410 if str(error) == "search_response_expired" else 404,
                content={"error": str(error)},
            )
        except ValueError as error:
            return JSONResponse(
                status_code=409 if str(error) == "artifact_hash_mismatch" else 400,
                content={"error": str(error)},
            )
        return Response(
            content=content,
            media_type="text/plain" if view else "application/octet-stream",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Content-Disposition": "inline" if view else f'attachment; filename="{kind}.txt"',
            },
        )

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
                    definition_version=_current_definition_version(paths),
                )
            ],
            "status": "ok",
        }

    @server.get("/api/v1/runs", name="run_index")
    def run_index() -> list[dict[str, object]]:
        return [asdict(item) for item in RunRepository(paths.database).list_runs()]

    @server.get("/api/v1/runs/{run_id}/audit", name="run_audit")
    def run_audit(run_id: str) -> JSONResponse:
        runs = RunRepository(paths.database)
        try:
            run = runs.get(run_id)
        except LookupError:
            return JSONResponse(status_code=404, content={"error": "run_not_found"})
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "run": asdict(run),
                    "full_retrieval": runs.full_retrieval_plan(run_id),
                }
            )
        )

    @server.get("/api/v1/run-health", name="run_health_history")
    def run_health_history() -> list[dict[str, Any]]:
        return RunHealth(paths.database).history()

    @server.get("/api/v1/runs/{run_id}/health", name="run_health_detail")
    def run_health_detail(run_id: str, request: Request) -> JSONResponse:
        try:
            run = RunRepository(paths.database).get(run_id)
            reader = RunHealth(paths.database)
            summary = (
                reader.observe(run_id)
                if run.status in {"queued", "running"}
                else reader.latest(run_id)
            )
        except LookupError:
            return JSONResponse(status_code=404, content={"error": "run_not_found"})
        if summary is None:
            return JSONResponse(status_code=404, content={"error": "legacy_summary_unavailable"})
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "summary": summary,
                    "comparison": comparison(summary, reader.history()),
                    "flow": filtered_flow(summary, dict(request.query_params)),
                }
            )
        )

    @server.get("/api/v1/reports", name="report_index")
    def report_index() -> list[dict[str, object]]:
        return [asdict(item) for item in _reports(paths)]

    @server.get("/api/v1/report-attempts", name="report_attempt_index")
    def report_attempt_index(bundle_id: str) -> list[dict[str, object]]:
        return [
            asdict(item) for item in ReportRepository(paths.database).attempts_for_bundle(bundle_id)
        ]

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
                    "explanation_reviews": repository.explanation_reviews(report_snapshot_id),
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
        rejection = _command_origin_rejection(request, config)
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

    if eager_dashboard:
        # Dash consumes JSON for its callbacks. Keep that middleware on its own app,
        # so commands retain their streaming size limit and receive their request body.
        dashboard_server = FastAPI()
        _load_dashboard(dashboard_server, paths, dashboard_state)
        server.router.routes.append(Mount("/", app=dashboard_server, name="dashboard"))
    else:
        loading_server = FastAPI()

        @loading_server.get("/{path:path}", response_class=HTMLResponse)
        def dashboard_loading(path: str) -> HTMLResponse:
            del path
            failure = dashboard_state.get("failure")
            return HTMLResponse(_initial_dashboard_html(paths, failed=failure is not None))

        dashboard_mount = Mount("/", app=loading_server, name="dashboard")
        server.router.routes.append(dashboard_mount)

    return server


def _initial_dashboard_html(paths: RuntimePaths, *, failed: bool) -> str:
    status = "交互驾驶舱加载失败，请查看本机日志。" if failed else "交互驾驶舱正在加载…"
    refresh = "" if failed else "<meta http-equiv='refresh' content='1'>"
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"{refresh}<title>Pring 本机运行状态</title></head><body>"
        f"{_meaningful_dashboard_shell(paths, status=status)}</body></html>"
    )


def _meaningful_dashboard_shell(paths: RuntimePaths, *, status: str) -> str:
    projection = _current_projection(paths)
    identity = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>"
        for label, value in identity_fields(
            projection,
            producer=_producer(paths, projection, _runs(paths)),
            rendered_at=datetime.now(UTC),
        )
    )
    navigation = "".join(
        f"<a href='{escape(path)}'>{escape(label)}</a>" for path, label in DASHBOARD_NAVIGATION
    )
    notice = _source_contract_notice(paths)
    notice_html = f"<aside role='alert'>{escape(notice)}</aside>" if notice is not None else ""
    overview = projection.datasets.get("cycle_overview", {}) if projection else {}
    macro = overview.get("macro_judgement")
    judged = macro.get("conclusion") if isinstance(macro, dict) else None
    conclusion = (
        "等待首次完整运行"
        if projection is None
        # The judgement leads the set as it leads the page (ADR-0043, ticket 16); a block
        # without its conclusion is unreadable, never the judgement's own 无可取阶段.
        else (macro_title(judged) if isinstance(judged, dict) else "宏观判断数据不可用")
        if isinstance(macro, dict)
        else stage_title(overview.get("current_stage"))
    )
    return (
        "<header><p>PRING CYCLE</p><h1>周期驾驶舱</h1>"
        f"<dl>{identity}</dl></header>"
        f"{notice_html}"
        f"<nav aria-label='一级导航'>{navigation}</nav>"
        "<main id='initial-page-content' data-pring-meaningful-content='true'>"
        f"<h2>三核心资产与周期结论</h2><p>{escape(conclusion)}</p>"
        f"<h2>本机运行状态</h2><p>{escape(status)}</p></main>"
    )


def _source_contract_notice(paths: RuntimePaths) -> str | None:
    if active_source_contract_review(paths.database) is None:
        return None
    return (
        "来源认证仍有缺口，已暂停更新和新报告。下方保留上次发布的历史结果。"
        "融资发布时间、估值方法、商品篮子口径及官方样本仍需复核。"
    )


def _dashboard_index_document(
    paths: RuntimePaths,
    *,
    metas: str,
    title: str,
    css: str,
    config: str,
    scripts: str,
    app_entry: str,
    favicon: str,
    renderer: str,
) -> str:
    shell = _meaningful_dashboard_shell(paths, status="交互驾驶舱正在启动…")
    return (
        f"<!doctype html><html lang='zh-CN'><head>{metas}"
        f"<meta charset='utf-8'><title>{title}</title>{favicon}{css}</head><body>"
        f"<div id='pring-initial-shell'>{shell}</div>{app_entry}"
        f"<footer>{config}{scripts}{renderer}</footer>"
        "<script>(function(){var fallback=document.getElementById('pring-initial-shell');"
        "var root=document.getElementById('react-entry-point');"
        "if(!fallback||!root||!window.MutationObserver){return;}"
        "var hide=function(){if(root.querySelector('#page-content > *')){"
        "fallback.remove();observer.disconnect();}};"
        "var observer=new MutationObserver(hide);"
        "observer.observe(root,{childList:true,subtree:true});hide();"
        "})();</script></body></html>"
    )


def _frozen_evidence(
    paths: RuntimePaths,
    projection: ProjectionSet,
    version_id: str,
    *,
    trail: str = "",
) -> dict[str, Any]:
    evidence = EvidenceRepository(paths.database)
    chain = [item for item in trail.split(",") if item] + [version_id]
    if len(chain) > 30:
        raise LookupError("lineage_depth_limit")
    if len(set(chain)) != len(chain):
        raise LookupError("lineage_cycle")
    if chain[0] not in evidence.frozen_versions(projection.envelope.evidence_snapshot_id):
        raise LookupError("version_not_in_snapshot")
    for parent, child in zip(chain, chain[1:], strict=False):
        node = evidence.trace_version(parent, as_of=projection.envelope.system_as_of)
        if child not in node["trace"].get("input_observation_version_ids", []):
            raise LookupError("version_not_in_parent_inputs")
    return {
        "projection_set_id": projection.envelope.projection_set_id,
        "system_as_of": projection.envelope.system_as_of.isoformat(),
        "lineage_path": chain,
        **evidence.trace_version(version_id, as_of=projection.envelope.system_as_of),
    }


def _load_deferred_dashboard(
    mount: Mount,
    paths: RuntimePaths,
    state: dict[str, object],
) -> None:
    dashboard_server = FastAPI()
    _load_dashboard(dashboard_server, paths, state)
    if "dashboard" in state:
        mount.app = dashboard_server


def _load_dashboard(
    server: FastAPI,
    paths: RuntimePaths,
    state: dict[str, object],
) -> None:
    try:
        from dash import Dash, Input, Output, State, no_update

        from pring_cycle.cockpit import evidence_workspace, identity_strip
        from pring_cycle.dashboard import dashboard_page, dashboard_shell

        class MeaningfulDash(Dash):
            def interpolate_index(
                self,
                metas: str = "",
                title: str = "",
                css: str = "",
                config: str = "",
                scripts: str = "",
                app_entry: str = "",
                favicon: str = "",
                renderer: str = "",
            ) -> str:
                return _dashboard_index_document(
                    paths,
                    metas=metas,
                    title=title,
                    css=css,
                    config=config,
                    scripts=scripts,
                    app_entry=app_entry,
                    favicon=favicon,
                    renderer=renderer,
                )

        dashboard = MeaningfulDash(
            __name__,
            server=cast(Any, server),
            title="Pring 本机运行状态",
            assets_folder=str(Path(__file__).with_name("assets")),
            suppress_callback_exceptions=True,
            update_title="更新投影视图…",
        )

        def dashboard_layout() -> Any:
            projection = _current_projection(paths)
            runs = _runs(paths)
            return dashboard_shell(
                projection,
                runs,
                _reports(paths),
                source_contract_notice=_source_contract_notice(paths),
                producer=_producer(paths, projection, runs),
            )

        dashboard.layout = dashboard_layout

        dashboard_index_endpoint = next(
            cast(Any, route).endpoint
            for route in server.routes
            if getattr(route, "path", None) == "/"
        )
        for path in (*[item[0] for item in DASHBOARD_NAVIGATION], *LEGACY_ROUTES):
            if path == "/":
                continue
            route_name = "dashboard_" + path.strip("/").replace("-", "_")
            server.add_api_route(
                path,
                dashboard_index_endpoint,
                methods=["GET"],
                name=route_name,
                include_in_schema=False,
            )

        @dashboard.callback(
            Output("page-content", "children"),
            Output("runtime-poll", "interval"),
            Output("projection-strip", "children"),
            Output("view-fingerprint", "data"),
            Output("refresh-notice", "children"),
            Input("dashboard-location", "pathname"),
            Input("dashboard-location", "search"),
            Input("runtime-poll", "n_intervals"),
            Input("command-refresh", "data"),
            State("view-fingerprint", "data"),
        )
        def route_dashboard(
            pathname: str | None,
            search: str | None,
            _n_intervals: int,
            _command_refresh: str | None,
            previous: str | None,
        ) -> tuple[Any, ...]:
            runs = _runs(paths)
            interval = (
                30_000 if any(item.status in {"queued", "running"} for item in runs) else 300_000
            )
            query = {
                key: values[-1] for key, values in parse_qs((search or "").lstrip("?")).items()
            }
            try:
                projection = (
                    ProjectionSetRepository(paths.database).get(query["projection"])
                    if query.get("projection")
                    else _current_projection(paths)
                )
                reports = _reports(paths)
                identity = projection.envelope.projection_set_id if projection else None
                producer = _producer(paths, projection, runs)
                strip = identity_strip(projection, producer=producer, rendered_at=datetime.now(UTC))
                # The producer's summary can land after the page first renders.
                signature = [pathname, search, identity, repr(producer)]
                signature.append(repr(reports))
                signature.append(
                    repr(
                        [
                            run
                            for run in runs
                            if run.projection_set_id == identity
                            and (
                                run.command_type == "report_generation"
                                or run.current_step == "generating_report"
                            )
                        ]
                    )
                )
                if pathname in {"/runs", "/data-chain", "/reports"}:
                    signature.extend([repr(runs), repr(reports)])
                if pathname in {"/runs", "/data-chain"}:
                    signature.append(repr(RunHealth(paths.database).history()))
                fingerprint = hashlib.sha256(repr(signature).encode()).hexdigest()
                # Unchanged views keep their bar too, so "页面生成" stays the actual render time.
                if previous == fingerprint and pathname not in {"/runs", "/data-chain"}:
                    return no_update, interval, no_update, no_update, ""
                if pathname in {"/runs", "/data-chain"}:
                    from pring_cycle.cockpit_operations import data_chain, runs_workspace

                    candidates = [
                        run
                        for run in runs
                        if pathname != "/runs"
                        or (
                            (not query.get("type") or run.command_type == query["type"])
                            and (not query.get("status") or run.status == query["status"])
                        )
                    ]
                    selected = next(
                        (run for run in candidates if run.run_id == query.get("run")), None
                    )
                    if selected is None and not query.get("run"):
                        produced = (
                            _producer_run(paths, projection, candidates)
                            if pathname == "/data-chain" or query.get("projection")
                            else None
                        )
                        selected = (
                            produced
                            if produced
                            else candidates[0]
                            if candidates and not query.get("projection")
                            else None
                        )
                    if selected and pathname == "/data-chain":
                        selected = RunRepository(paths.database).get(selected.run_id)
                    health = RunHealth(paths.database)
                    summary = (
                        (
                            health.observe(selected.run_id)
                            if selected.status in {"queued", "running"}
                            else health.latest(selected.run_id)
                        )
                        if selected
                        else None
                    )
                    # Request receipts can change while the run stays in one step.
                    fingerprint = hashlib.sha256(repr((fingerprint, summary)).encode()).hexdigest()
                    if previous == fingerprint:
                        return no_update, interval, no_update, no_update, ""
                    if pathname == "/runs":
                        page = runs_workspace(runs, summary, health.history(), query)
                        return page, interval, strip, fingerprint, ""
                    try:
                        document = (
                            _frozen_evidence(
                                paths, projection, query["version"], trail=query.get("trail", "")
                            )
                            if projection and query.get("version")
                            else None
                        )
                    except LookupError as error:
                        document = {"error": str(error)}
                    search_results = (
                        EvidenceRepository(paths.database).search_frozen(
                            projection.envelope.evidence_snapshot_id, query.get("q", "")
                        )
                        if projection
                        else []
                    )
                    page = data_chain(
                        runs,
                        selected,
                        summary,
                        query,
                        evidence_workspace(projection, document, query, search_results),
                    )
                else:
                    page = dashboard_page(
                        pathname,
                        projection,
                        runs,
                        reports,
                        (),
                        _release_calendar_events(paths, projection),
                        producer_run=producer,
                        trend_rules=_projection_trend_rules(paths, projection),
                    )
                return page, interval, strip, fingerprint, ""
            except (
                Exception
            ) as error:  # Preserve the last complete view; never mix partial datasets.
                write_runtime_event(
                    paths, "web", "dashboard_read_failed:" + type(error).__name__, level="error"
                )
                return (
                    no_update,
                    interval,
                    no_update,
                    no_update,
                    "读取失败，请重试；已有完整视图继续保留。",
                )

        state["dashboard"] = dashboard
    except Exception as error:  # noqa: BLE001 - preserve API availability on UI failure
        state["failure"] = type(error).__name__
        write_runtime_event(paths, "web", "dashboard_load_failed", level="error")


def run_web(paths: RuntimePaths, port: int | None = None) -> None:
    if database_health(paths.database)["status"] != "ok":
        raise RuntimeNotInitializedError("runtime_not_initialized")
    config = WebConfig.read(paths, port)
    uvicorn.run(
        create_web_application(paths, config.port, eager_dashboard=False),
        host=config.host,
        port=config.port,
        access_log=False,
        log_level="warning",
    )


def _current_projection(paths: RuntimePaths) -> ProjectionSet | None:
    try:
        return ProjectionSetRepository(paths.database).current()
    except (LookupError, OSError):
        return None


def _producer(
    paths: RuntimePaths, projection: ProjectionSet | None, runs: Sequence[RunRecord]
) -> ProducerRun | None:
    """The run that produced ``projection`` with its persisted summary, as pages show it."""
    produced_by = _producer_run(paths, projection, runs)
    if produced_by is None:
        return None
    return ProducerRun(produced_by.run_id, RunHealth(paths.database).latest(produced_by.run_id))


def _producer_run(
    paths: RuntimePaths, projection: ProjectionSet | None, runs: Sequence[RunRecord]
) -> RunRecord | None:
    """The full run among ``runs`` that produced ``projection``, or none; never another run.

    The writing batch comes first, since a run also owns the days it backfilled; projections
    published before batches existed fall back to the run that linked them.
    """
    if projection is None:
        return None
    identity = projection.envelope.projection_set_id
    batch = ProjectionSetRepository(paths.database).producer_run_id(identity)
    full = [run for run in runs if run.command_type in {"manual_full", "scheduled_full"}]
    return next((run for run in full if run.run_id == batch), None) or next(
        (run for run in full if run.projection_set_id == identity), None
    )


def _runs(paths: RuntimePaths) -> tuple[RunRecord, ...]:
    try:
        return RunRepository(paths.database).list_runs(limit=-1, include_details=False)
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


def _release_calendar_events(
    paths: RuntimePaths, projection: ProjectionSet | None = None
) -> tuple[dict[str, object], ...]:
    now = projection.envelope.system_as_of if projection else datetime.now(UTC)
    try:
        return tuple(
            asdict(item)
            for item in lpr_release_calendar(
                EvidenceRepository(paths.database),
                period=projection.envelope.target_business_date[:7]
                if projection
                else current_lpr_period(now),
                as_of=now,
                definition_version=str(
                    ModelRepository(paths.database).manifest(projection.envelope.model_version_id)[
                        "metric_catalog_version"
                    ]
                )
                if projection
                else _current_definition_version(paths),
            )
        )
    except (OSError, ValueError):
        return ()


def _projection_trend_rules(
    paths: RuntimePaths, projection: ProjectionSet | None
) -> TrendRules | None:
    """The trend rules frozen in the projection's model, from the manifest the Worker reads.

    None when there is no projection, or its model provides no valid rules; the board
    then says so and never shows defaults.
    """
    if projection is None:
        return None
    try:
        manifest = ModelRepository(paths.database).manifest(projection.envelope.model_version_id)
        return trend_rules_from_manifest(manifest)
    except (LookupError, OSError, ValueError):
        return None


def _current_definition_version(paths: RuntimePaths) -> str:
    models = ModelRepository(paths.database)
    projection = _current_projection(paths)
    try:
        model_version_id = (
            projection.envelope.model_version_id
            if projection is not None
            else models.active().model_version_id
        )
        return ContextProjectionRules.from_manifest(
            models.manifest(model_version_id)
        ).metric_catalog_version
    except (LookupError, ValueError):
        return METRIC_CATALOG_VERSION


def _projection_document(projection: ProjectionSet) -> dict[str, object]:
    return {
        "envelope": asdict(projection.envelope),
        "datasets": projection.datasets,
        "corrections": projection.corrections,
    }


def _command_origin_rejection(request: Request, config: WebConfig) -> JSONResponse | None:
    if (
        request.headers.get("host", "").lower() not in config.allowed_hosts
        or request.headers.get("origin") not in config.allowed_origins
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
    public_commands = {
        "manual_full",
        "targeted_refresh",
        "manual_deep_search",
        "report_generation",
        "resume",
        "cancel",
        "data_gap_notice",
    }
    if command not in public_commands:
        raise ValueError("unsupported_public_command")
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
    models = ModelRepository(paths.database)
    if command == "resume":
        bound_run = repository.get(str(payload["run_id"]))
        require_model_source_contract(models.manifest(bound_run.model_version_id))
        run = repository.resume(
            str(payload["run_id"]),
            client_request_id=str(payload["client_request_id"]),
            confirm_external_calls=payload.get("confirm_external_calls") is True,
        )
    elif command == "cancel":
        run = repository.cancel(str(payload["run_id"]))
    elif command == "report_generation":
        projection = (
            ProjectionSetRepository(paths.database).get(str(payload["projection_set_id"]))
            if payload.get("projection_set_id")
            else ProjectionSetRepository(paths.database).current()
        )
        require_model_source_contract(models.manifest(projection.envelope.model_version_id))
        run = repository.submit(
            command_type=command,
            target_business_date=projection.envelope.target_business_date,
            client_request_id=str(payload["client_request_id"]),
            model_version_id=projection.envelope.model_version_id,
            system_as_of=projection.envelope.system_as_of,
            projection_set_id=projection.envelope.projection_set_id,
        )
    else:
        model_version_id = str(payload.get("model_version_id") or _default_model(paths))
        require_model_source_contract(models.manifest(model_version_id))
        metric_values = payload.get("metric_ids", ())
        if not isinstance(metric_values, (list, tuple)) or any(
            not isinstance(item, str) for item in metric_values
        ):
            raise ValueError("retrieval_metric_ids_must_be_string_list")
        run = repository.submit(
            command_type=command,
            target_business_date=str(payload["target_business_date"]),
            client_request_id=str(payload["client_request_id"]),
            model_version_id=model_version_id,
            system_as_of=(
                datetime.fromisoformat(str(payload["system_as_of"]))
                if payload.get("system_as_of") is not None
                else datetime.now(UTC)
            ),
            cutoff_mode="explicit" if payload.get("system_as_of") is not None else None,
            release_event_id=(
                str(payload["release_event_id"])
                if payload.get("release_event_id") is not None
                else None
            ),
            metric_ids=tuple(metric_values),
            period=str(payload["period"]) if payload.get("period") is not None else None,
            source_url=(
                str(payload["source_url"]) if payload.get("source_url") is not None else None
            ),
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
