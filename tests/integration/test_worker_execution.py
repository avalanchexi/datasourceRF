from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.maintenance import MaintenanceRepository
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_model_v0001_manifest,
)
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run, submit_schedule_if_crossed


def runtime(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    return paths


def test_worker_fails_closed_when_a_manual_run_has_no_certified_p0(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-p0-missing",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    processed = process_pending_run(paths, report_adapters=())

    assert processed == submitted.run_id
    assert runs.get(submitted.run_id).status == "action_required"
    assert runs.get(submitted.run_id).error_classification == "p0_unavailable"
    assert runs.next_queued() is None


def test_worker_rejects_a_formal_run_for_a_candidate_model(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    candidate = certified_model_v0001_manifest()
    candidate["model_version_id"] = "model-v0002"
    ModelRepository(paths.database).create_candidate(candidate)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-candidate-model",
        model_version_id="model-v0002",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.error_classification == "model_version_not_active"
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()


def test_worker_does_not_mutate_a_runtime_that_requires_reinitialization(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-integrity-gate",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    MaintenanceRepository(paths.database).record_upgrade_failure("fixture_failure")

    assert process_pending_run(paths, report_adapters=()) is None
    assert runs.get(submitted.run_id).status == "queued"


def test_report_command_reads_the_published_projection_and_never_rewrites_it(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    projections = ProjectionSetRepository(paths.database)
    readiness = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=160,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    published = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=readiness,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="report_generation",
        target_business_date="2026-08-28",
        client_request_id="worker-report-1",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, 5, tzinfo=UTC),
    )

    process_pending_run(paths, report_adapters=())

    assert runs.get(submitted.run_id).status == "completed"
    assert projections.current().envelope.projection_set_id == published.projection_set_id
    reports = ReportRepository(paths.database).history()
    assert len(reports) == 1
    assert reports[0].status == "completed_degraded"


def test_enabled_schedule_only_runs_when_a_live_worker_crosses_1830_shanghai(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    runs.configure_schedule(enabled=True, requested_by="test")

    missed_on_startup = submit_schedule_if_crossed(
        paths,
        datetime(2026, 8, 28, 11, tzinfo=UTC),
        datetime(2026, 8, 28, 12, tzinfo=UTC),
    )
    crossed = submit_schedule_if_crossed(
        paths,
        datetime(2026, 8, 28, 10, 29, 59, tzinfo=UTC),
        datetime(2026, 8, 28, 10, 30, 1, tzinfo=UTC),
    )

    assert missed_on_startup is None
    assert crossed is not None
    assert runs.get(crossed).target_business_date == "2026-08-28"


def test_targeted_refresh_runs_serial_retrieval_and_persists_auditable_attempts(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="targeted-lpr-1",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    calls: list[str] = []

    def adapter(channel: str) -> object:
        def retrieve(_event: str) -> str | None:
            calls.append(channel)
            return "claim:lpr:2026-08" if channel == "official" else None

        return retrieve

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters={
            channel: adapter(channel)  # type: ignore[dict-item]
            for channel in ("local", "tushare", "official")
        },
        retrieval_now=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )

    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    assert calls == ["local", "tushare", "official"]
    assert [item["channel"] for item in stored.retrieval_attempts] == [
        "local",
        "tushare",
        "official",
    ]
    assert stored.retrieval_attempts[-1]["outcome"] == "verified"
    assert runs.reusable_checkpoints(submitted.run_id) == (
        {"kind": "verified_evidence", "reference": "claim:lpr:2026-08"},
    )


def test_unreleased_targeted_refresh_and_active_negative_cache_make_no_calls(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    calls: list[str] = []
    adapters = {"official": lambda _event: calls.append("official")}
    future = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-01",
        client_request_id="future-lpr",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-09",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-09",
    )

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters=adapters,  # type: ignore[arg-type]
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert calls == []
    assert runs.get(future.run_id).next_action == "wait_for_release_or_cache_expiry"

    runs.store_negative_cache(
        "chinamoney-lpr:2026-08-20",
        ("CN_LPR_1Y_5Y",),
        reason="not_found",
        expires_at=datetime(2026, 8, 31, tzinfo=UTC),
        now=datetime(2026, 8, 30, tzinfo=UTC),
    )
    cached = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="cached-lpr",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters=adapters,  # type: ignore[arg-type]
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert calls == []
    assert runs.get(cached.run_id).retrieval_attempts[0]["cache_hit"] is True


def test_p2_stops_before_ai_and_manual_deep_search_records_budget_exemption(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    calls: list[str] = []

    with pytest.raises(ValueError, match="manual_deep_search_requires_one_explicit_metric"):
        runs.submit(
            command_type="manual_deep_search",
            target_business_date="2026-08-20",
            client_request_id="deep-invalid",
            model_version_id="model-v0001",
            system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
            release_event_id="release-p2",
            metric_ids=("CBOE_VIX_INDEX", "NASDAQ_SOX_INDEX"),
            period="2026-08",
        )

    deep = runs.submit(
        command_type="manual_deep_search",
        target_business_date="2026-08-20",
        client_request_id="deep-p2",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="release-p2",
        metric_ids=("CBOE_VIX_INDEX",),
        period="2026-08",
    )

    def miss(channel: str) -> object:
        def retrieve(_event: str) -> RetrievalAdapterResponse:
            calls.append(channel)
            return RetrievalAdapterResponse("not_found")

        return retrieve

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters={
            channel: miss(channel)  # type: ignore[dict-item]
            for channel in ("local", "tushare", "official", "tavily", "exa", "ai_websearch")
        },
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
        retrieval_release_resolver=lambda _scope, _now: True,
    )

    stored = runs.get(deep.run_id)
    assert calls == ["local", "tushare", "official", "tavily", "exa"]
    assert stored.consumed_budget == {"tavily": 0, "exa": 0, "ai_websearch": 0}
    assert all(item["manual_budget_exemption"] is True for item in stored.retrieval_attempts)
