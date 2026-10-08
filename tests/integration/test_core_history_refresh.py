from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.routing import APIRoute

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.core_history import CORE_HISTORY_SCHEMA_VERSION, refresh_core_history
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    publication_times,
)
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import TushareCoreAdapter
from pring_cycle.storage import artifact_is_registered
from pring_cycle.web import create_web_application
from pring_cycle.worker import process_pending_run


def historical_response(payload: dict[str, Any]) -> bytes:
    start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
    end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
    calendar = [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    if payload["api_name"] == "trade_cal":
        fields = ["cal_date", "is_open"]
        items = [[day.strftime("%Y%m%d"), 1] for day in calendar]
    else:
        fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
        items = [
            [
                payload["params"]["ts_code"],
                day.strftime("%Y%m%d"),
                100.0 + i,
                99.0 + i,
                0.01 if payload["api_name"] == "fut_index_daily" else 1.0,
            ]
            for i, day in enumerate(calendar)
        ]
    return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}, indent=2).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_core_history_refresh_is_atomic_content_addressed_and_queryable(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-token", transport=historical_response),
        start=date(2025, 12, 30),
        end=date(2026, 1, 2),
        definition_version="metric-catalog-v0001",
    )

    assert result.status == "validated"
    assert result.observations_per_metric == 4
    assert result.network_requests == 8
    assert artifact_is_registered(
        paths.database,
        result.artifact_hash,
        f"{CORE_HISTORY_SCHEMA_VERSION}:2025-12-30:2026-01-02",
    )
    series = EvidenceRepository(paths.database).metric_series(
        "CN_COMMODITY_CORE_NHII",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert [point.selected_value for point in series] == [100.0, 101.0, 100.0, 101.0]


def core_response(payload: dict[str, Any]) -> bytes:
    if payload["api_name"] == "trade_cal":
        document = {
            "code": 0,
            "data": {
                "fields": ["cal_date", "is_open"],
                "items": [["20260803", 1]],
            },
        }
    else:
        document = {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                "items": [
                    [
                        payload["params"]["ts_code"],
                        "20260803",
                        101.0,
                        100.0,
                        0.01 if payload["api_name"] == "fut_index_daily" else 1.0,
                    ]
                ],
            },
        }
    return json.dumps(document, indent=2).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_unknown_core_catalog_is_rejected_before_any_request(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    calls: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        calls.append(payload["api_name"])
        return core_response(payload)

    with pytest.raises(KeyError, match="unknown_metric_definition_version"):
        refresh_core_history(
            paths,
            TushareCoreAdapter("fixture-secret", transport=transport),
            start=date(2026, 8, 3),
            end=date(2026, 8, 3),
            definition_version="unregistered-core-catalog",
        )
    assert calls == []
    assert AcquisitionRepository(paths.database, paths.artifacts).history() == ()


@pytest.mark.usefixtures("runtime_clock")
def test_core_claim_trace_retains_each_request_original(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-secret", transport=core_response),
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
        definition_version="metric-catalog-v0001",
    )
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    point = evidence.metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version="metric-catalog-v0001",
    )[0]
    trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=now)

    assert trace.acquisition_status == "linked"
    assert len(trace.acquisitions) == 1
    receipt = trace.acquisitions[0]
    assert receipt.api_name == "index_daily"
    assert receipt.parameters["ts_code"] == "000985.CSI"
    assert receipt.state == "validated"
    assert receipt.started_at <= receipt.received_at <= receipt.validated_at
    assert point.claims[0].fetched_at == receipt.received_at
    assert point.claims[0].available_at >= receipt.validated_at
    assert "fixture-secret" not in repr(receipt)
    raw_path = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
    assert json.loads(raw_path.read_bytes())["data"]["items"][0][0] == "000985.CSI"
    normalized_path = paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash
    assert json.loads(normalized_path.read_bytes())[0]["close"] == 101.0


def test_manual_run_cannot_backdate_daily_core_availability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from time import monotonic

    origin = datetime.now(UTC)
    started = monotonic()

    class StableDateTimeMeta(type):
        def __instancecheck__(cls, value):
            return isinstance(value, datetime)

    class StableDateTime(datetime, metaclass=StableDateTimeMeta):
        @classmethod
        def now(cls, tz=None):
            value = origin + timedelta(seconds=monotonic() - started)
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    # WSL wall-clock resynchronization must not move this availability probe
    # behind receipts that were just validated. Replace only the clock boundary.
    monkeypatch.setattr("pring_cycle.acquisition.datetime", StableDateTime)
    monkeypatch.setattr("pring_cycle.core_history.datetime", StableDateTime)
    monkeypatch.setattr("pring_cycle.worker.datetime", StableDateTime)

    def offline_optional(*args, **kwargs):
        raise OSError("fixture optional source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline_optional)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    during_stock_request = []

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            code = payload["params"].get("ts_code")
            if payload["api_name"] == "trade_cal":
                return BytesIO(historical_response(payload))
            if code not in {"000985.CSI", "000012.SH", "NHII.NH"}:
                raise OSError("fixture_context_unavailable")
            if code == "000985.CSI":
                during_stock_request.append(StableDateTime.now(UTC))
            return BytesIO(historical_response(payload))

    # Replace only the external HTTP transport, retaining both real adapters.
    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
    )
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id="daily-acquisition",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    evidence = EvidenceRepository(paths.database)
    before_response = evidence.metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=during_stock_request[0],
        definition_version="metric-catalog-v0001",
    )
    assert before_response == ()
    after = evidence.metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=StableDateTime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    # 160 sessions were fetched for the trend over the run's 120-session window; the
    # projection cites the 40 before it, so they stay until it expires (lookback 08).
    assert len(after) == 160
    # The source states no publication time, so public time is the earlier of the
    # registered 17:00 close update and the moment the system first held the value.
    for point in after:
        claim = point.claims[0]
        inferred = datetime.combine(
            date.fromisoformat(point.period_end), time(17), ZoneInfo("Asia/Shanghai")
        )
        assert claim.public_available_at == min(inferred, claim.fetched_at)
    trace = evidence.trace(
        after[-1].observation_id, mode=AsOfMode.SYSTEM, as_of=StableDateTime.now(UTC)
    )
    assert len(trace.acquisitions) == 1
    # The isolated legacy model permits SYSTEM evidence; unknown publication
    # is a PUBLIC availability gap, not a fabricated transport failure.
    assert runs.get(run.run_id).status == "completed"
    plan = runs.full_retrieval_plan(run.run_id)
    window = plan["final"]["daily_window"]
    assert window["status"] == "available"
    assert window["basis"] == "validated_independent_calendar_response"
    assert len(window["dates"]) == 120
    assert any(
        item["api_name"] == "trade_cal" and item["state"] == "validated"
        for item in plan["acquisitions"]
    )
    projection = ProjectionSetRepository(paths.database).current()
    assert len(projection.datasets["core_assets"]["assets"]) == 3
    assert projection.datasets["cycle_overview"]["current_stage"] == "stage_iii"
    public = evidence.metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.PUBLIC,
        as_of=StableDateTime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert [point.period_end for point in public] == [point.period_end for point in after]
    report = ReportRepository(paths.database).history()[0]
    assert report.projection_set_id == projection.envelope.projection_set_id
    assert (report.target_business_date, report.current_stage) == ("2026-08-03", "stage_iii")
    assert report.status == "completed_degraded"


@pytest.mark.usefixtures("runtime_clock")
def test_trace_api_can_read_the_original_and_reject_unrelated_artifact_kinds(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-secret", transport=core_response),
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
        definition_version="metric-catalog-v0001",
    )
    point = EvidenceRepository(paths.database).metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )[0]
    application = create_web_application(paths, 8877, eager_dashboard=False)
    routes = {route.name: route for route in application.routes if isinstance(route, APIRoute)}
    response = routes["evidence_trace"].endpoint(
        point.observation_id, AsOfMode.SYSTEM, datetime.now(UTC)
    )
    traced = json.loads(response.body)
    request_id = traced["acquisitions"][0]["acquisition_id"]
    original = routes["acquisition_artifact"].endpoint(request_id, "raw")
    assert original.status_code == 200
    assert bytes(original.body) == core_response(
        {"api_name": "index_daily", "params": {"ts_code": "000985.CSI"}}
    )
    assert routes["acquisition_artifact"].endpoint(request_id, "secrets").status_code == 400
    assert routes["acquisition_artifact"].endpoint("missing-request", "raw").status_code == 404


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    ("column", "value", "error"),
    [
        (2, 0, "nonpositive_core_price"),
        (2, True, "core_number_invalid"),
        (3, True, "core_number_invalid"),
        (4, True, "core_number_invalid"),
        (2, "NaN", "core_number_invalid"),
        (3, "NaN", "core_number_invalid"),
        (4, "NaN", "core_number_invalid"),
        (2, "Infinity", "core_number_invalid"),
        (3, "-Infinity", "core_number_invalid"),
        (4, "Infinity", "core_number_invalid"),
    ],
)
def test_invalid_core_rows_keep_the_response_without_creating_claims(
    tmp_path: Path,
    column: int,
    value: object,
    error: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    bad_originals = []

    def invalid_price(payload: dict[str, Any]) -> bytes:
        document = json.loads(core_response(payload))
        if payload["api_name"] != "trade_cal":
            document["data"]["items"][0][column] = value
        raw = json.dumps(document, indent=4).encode()
        bad_originals.append(raw)
        return raw

    with pytest.raises(ValueError, match=error):
        refresh_core_history(
            paths,
            TushareCoreAdapter("fixture-secret", transport=invalid_price),
            start=date(2026, 8, 3),
            end=date(2026, 8, 3),
            definition_version="metric-catalog-v0001",
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    failed = acquisitions.history()[-1]
    assert failed.state == "failed"
    assert failed.validated_at is None and failed.normalized_hash is None
    assert acquisitions.read_content(failed.acquisition_id, "raw") == bad_originals[-1]
    application = create_web_application(paths, 8877, eager_dashboard=False)
    index = next(
        route
        for route in application.routes
        if isinstance(route, APIRoute) and route.name == "acquisition_index"
    )
    assert index.endpoint()["acquisitions"][-1]["state"] == "failed"
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQUITY_CORE_000985",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        == ()
    )


@pytest.mark.parametrize("failure_phase", ["raw", "aggregate"])
@pytest.mark.usefixtures("runtime_clock")
def test_artifact_storage_failure_never_leaves_unbacked_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_phase: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    real_replace = os.replace

    def failed_disk_write(source: str, destination: str) -> None:
        document = json.loads(Path(source).read_bytes())
        if failure_phase == "raw" or (
            isinstance(document, dict)
            and document.get("schema_version") == CORE_HISTORY_SCHEMA_VERSION
        ):
            raise OSError("fixture_artifact_write_failed")
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", failed_disk_write)
    with pytest.raises(OSError, match="fixture_artifact_write_failed"):
        refresh_core_history(
            paths,
            TushareCoreAdapter("fixture-secret", transport=core_response),
            start=date(2026, 8, 3),
            end=date(2026, 8, 3),
            definition_version="metric-catalog-v0001",
        )
    requests = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert requests
    if failure_phase == "raw":
        assert requests[0].state == "failed" and requests[0].raw_hash is None
        assert requests[0].received_at is not None
    for metric in ("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012", "CN_COMMODITY_CORE_NHII"):
        assert (
            EvidenceRepository(paths.database).metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version="metric-catalog-v0001",
            )
            == ()
        )


@pytest.mark.parametrize("days", [["20260804"], ["20260803", "20260803"]])
@pytest.mark.usefixtures("runtime_clock")
def test_acquired_calendar_rejects_wrong_period_or_duplicate_days(
    tmp_path: Path, days: list[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def calendar_response(payload: dict[str, Any]) -> bytes:
        if payload["api_name"] == "trade_cal":
            return json.dumps(
                {
                    "code": 0,
                    "data": {
                        "fields": ["cal_date", "is_open"],
                        "items": [[day, 1] for day in days],
                    },
                }
            ).encode()
        return historical_response(payload)

    with pytest.raises(ValueError, match="china_trading_calendar_invalid"):
        refresh_core_history(
            paths,
            TushareCoreAdapter("fixture-secret", transport=calendar_response),
            start=date(2026, 8, 3),
            end=date(2026, 8, 3),
            definition_version="metric-catalog-v0001",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert len(receipts) == 1
    assert receipts[0].state == "failed" and receipts[0].raw_hash is not None
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQUITY_CORE_000985",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_new_acquisition_preserves_old_release_and_claim_bytes(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence = EvidenceRepository(paths.database)
    old_at = datetime(2026, 8, 3, 8, tzinfo=UTC)
    old = evidence.append_source_claim(
        SourceClaimInput(
            metric_id="CN_EQUITY_CORE_000985",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start="2026-08-03",
            period_end="2026-08-03",
            dimensions={},
            value=100.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference="tushare:index_daily:000985.CSI:2026-08-03",
            release_event_id="release:index_daily:000985.CSI:2026-08-03",
            release_at=old_at,
            public_available_at=old_at,
            fetched_at=old_at,
            available_at=old_at,
            certification_status="certified",
            quality_status="validated",
        )
    )
    before = json.dumps(
        asdict(evidence.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=old_at)),
        default=str,
        sort_keys=True,
    )
    assert (
        evidence.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=old_at).acquisition_status
        == "untraced"
    )
    # Reproduce the previous on-disk schema inside this isolated runtime.
    with sqlite3.connect(paths.database) as connection:
        connection.execute("DROP TABLE registered_metric_catalog")
        connection.execute("DROP TABLE retrieval_candidate_validation")
        connection.execute("DROP TABLE source_claim_acquisition")
        connection.execute("DROP TABLE acquisition_request")
        connection.execute(
            "UPDATE alembic_version SET version_num='0013_source_claim_provider_identity_index'"
        )
    legacy_read = json.dumps(
        asdict(evidence.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=old_at)),
        default=str,
        sort_keys=True,
    )
    assert legacy_read == before
    legacy_application = create_web_application(paths, 8877, eager_dashboard=False)
    legacy_routes = {
        route.name: route for route in legacy_application.routes if isinstance(route, APIRoute)
    }
    assert legacy_routes["acquisition_index"].endpoint() == {"acquisitions": []}
    assert (
        legacy_routes["acquisition_artifact"].endpoint("legacy-untraced", "raw").status_code == 404
    )
    initialize_runtime(paths)
    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-secret", transport=core_response),
        start=date(2026, 8, 3),
        end=date(2026, 8, 3),
        definition_version="metric-catalog-v0001",
    )
    after = json.dumps(
        asdict(evidence.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=old_at)),
        default=str,
        sort_keys=True,
    )
    assert after == before
    current = evidence.trace(old.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
    assert current.selected_value == 101.0
    assert len(current.acquisitions) == 1
    assert (
        next(
            claim
            for claim in evidence.trace(
                old.observation_id, mode=AsOfMode.SYSTEM, as_of=old_at
            ).claims
            if claim.claim_id == old.claim_id
        ).public_available_at
        == old_at
    )


@pytest.mark.parametrize(
    ("published_at", "before", "available", "release_at"),
    [
        (
            datetime(2026, 8, 4, 9, 15, tzinfo=UTC),
            datetime(2026, 8, 4, 9, 14, tzinfo=UTC),
            datetime(2026, 8, 4, 9, 15, tzinfo=UTC),
            datetime(2026, 8, 4, 9, 15, tzinfo=UTC),
        ),
        (
            date(2026, 8, 4),
            datetime(2026, 8, 4, 15, 59, tzinfo=UTC),
            datetime(2026, 8, 4, 16, tzinfo=UTC),
            None,
        ),
    ],
)
def test_supported_publication_precision_controls_public_queries(
    tmp_path: Path,
    published_at: date | datetime,
    before: datetime,
    available: datetime,
    release_at: datetime | None,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    # Synthetic domain input, not evidence of an official source's publication.
    actual_release, public_at = publication_times(published_at, ZoneInfo("Asia/Shanghai"))
    evidence = EvidenceRepository(paths.database)
    fetched_at = datetime(2026, 8, 5, 8, tzinfo=UTC)
    validated_at = datetime(2026, 8, 5, 9, tzinfo=UTC)
    stored = evidence.append_source_claim(
        SourceClaimInput(
            metric_id="CN_EQUITY_CORE_000985",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start="2026-08-03",
            period_end="2026-08-03",
            dimensions={},
            value=101.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference="synthetic:domain-time",
            release_event_id="synthetic:domain-publication",
            release_at=actual_release,
            public_available_at=public_at,
            fetched_at=fetched_at,
            available_at=validated_at,
            certification_status="certified",
            quality_status="validated",
        )
    )
    assert (
        evidence.query(stored.observation_id, mode=AsOfMode.PUBLIC, as_of=before).selected_value
        is None
    )
    public = evidence.query(stored.observation_id, mode=AsOfMode.PUBLIC, as_of=available)
    assert public.selected_value == 101.0
    assert public.claims[0].release_at == release_at
    assert public.claims[0].public_available_at == available
    assert (
        evidence.query(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=fetched_at).selected_value
        is None
    )
    assert (
        evidence.query(
            stored.observation_id, mode=AsOfMode.SYSTEM, as_of=validated_at
        ).selected_value
        == 101.0
    )
