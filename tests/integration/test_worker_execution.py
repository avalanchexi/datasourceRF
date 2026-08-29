from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.domain import CoreAssetState
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
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
