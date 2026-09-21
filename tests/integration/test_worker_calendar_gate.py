"""Independent calendar evidence is required before publishing a new full run."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.p0 import P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_full_run_retrieval import prepare, seed_core_history
from tests.integration.test_p0_gate import readiness


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 13, tzinfo=UTC))


@pytest.mark.parametrize("has_previous_projection", [False, True])
def test_missing_independent_calendar_blocks_publication_and_preserves_previous_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_clock,
    has_previous_projection: bool,
) -> None:
    def offline(*args, **kwargs):
        raise OSError("fixture external source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    paths, runs = prepare(tmp_path)
    seed_core_history(paths, include_calendar=False)
    projections = ProjectionSetRepository(paths.database)
    previous_id = None
    if has_previous_projection:
        previous = P0ProjectionService(projections).publish(
            target_business_date="2026-08-28",
            system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
            assets=(
                readiness("bond", CoreAssetState.BULL),
                readiness("stock", CoreAssetState.BULL),
                readiness("commodity", CoreAssetState.BEAR),
            ),
            last_confirmed_stage=None,
        )
        previous_id = previous.projection_set_id
        assert previous_id is not None
        report_run = runs.submit(
            command_type="report_generation",
            target_business_date="2026-08-28",
            client_request_id="previous-report",
            model_version_id="model-v0001",
            system_as_of=datetime(2026, 8, 28, 13, 5, tzinfo=UTC),
        )
        process_pending_run(paths, report_adapters=())
        assert runs.get(report_run.run_id).status == "completed"
    before_history = projections.stage_history()
    before_reports = ReportRepository(paths.database).history()
    assert bool(before_reports) is has_previous_projection
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="missing-independent-calendar",
        model_version_id="model-v0001",
        system_as_of=runtime_clock(),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    window = runs.full_retrieval_plan(submitted.run_id)["final"]["daily_window"]
    assert window["status"] == "unavailable"
    assert window["basis"] == "independent_calendar_unavailable"
    assert stored.status == "action_required"
    assert stored.error_classification == "p0_required_calendar_unavailable"
    assert stored.projection_set_id is None
    assert ReportRepository(paths.database).history() == before_reports
    assert projections.stage_history() == before_history
    if previous_id is None:
        with pytest.raises(LookupError):
            projections.current()
    else:
        assert projections.current().envelope.projection_set_id == previous_id


@pytest.mark.usefixtures("runtime_clock")
def test_an_independent_calendar_lets_the_run_publish_what_the_assets_say(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime_clock
) -> None:
    """The mirror of the gate above: with the calendar present, the run gets to answer.

    Blocking publication when the calendar is missing is only half of #28. The other half is
    that a run holding one publishes a projection whose core assets are populated and whose
    stage is whatever the trend rules make of them -- including empty, when three assets
    genuinely do not form a typical combination. An empty stage is a conclusion here, not the
    silence that a missing calendar produced.
    """

    def offline(*args, **kwargs):
        raise OSError("fixture external source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)

    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="independent-calendar-present",
        model_version_id="model-v0001",
        system_as_of=runtime_clock(),
    )
    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    window = runs.full_retrieval_plan(submitted.run_id)["final"]["daily_window"]
    assert window["status"] == "available"
    assert len(window["dates"]) == 120

    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id or "")
    assets = projection.datasets["core_assets"]["assets"]
    assert {asset["asset"] for asset in assets} == {"bond", "stock", "commodity"}
    overview = projection.datasets["cycle_overview"]
    # These three assets do not form a canonical combination, so an empty stage is the answer
    # -- and it arrives with a reason, which is what separates it from the gate's silence.
    assert overview["current_stage"] is None
    assert overview["stage_reason"] == "noncanonical_combination"
