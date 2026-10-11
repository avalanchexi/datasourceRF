"""The day summary module: the summary rules, asked of one day at a time (ADR-0034)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.day_summary as day_summary
from pring_cycle.day_summary import DaySummaries, FailedDay, ModelRules, RunMaterials
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import P0ProjectionService
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import cpi_periods, query, summary
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_worker_execution import runtime

SHANGHAI = ZoneInfo("Asia/Shanghai")


def summaries(paths: RuntimePaths, window_calendar: TradingCalendar | None = None) -> DaySummaries:
    return DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), "model-v0001"),
        calendar=TradingCalendar(sessions()),
        window_calendar=window_calendar,
    )


def target_projection(paths: RuntimePaths, materials: RunMaterials | None = None) -> ProjectionSet:
    result = (
        summaries(paths)
        .summarize_target(
            TARGET.isoformat(), system_as_of=CUTOFF, run_materials=materials or RunMaterials()
        )
        .result
    )
    assert result.projection_set_id is not None
    return ProjectionSetRepository(paths.database).get(result.projection_set_id)


def stage(projection: ProjectionSet) -> tuple[Any, Any]:
    overview = projection.datasets["cycle_overview"]
    return overview["current_stage"], overview["stage_reason"]


def test_a_core_one_session_behind_is_carried(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=1)

    projection = target_projection(paths)

    assert stage(projection)[0] == "stage_iii"
    assert projection.datasets["cycle_overview"]["core_carry_forward"] == ["commodity"]


def test_a_core_two_sessions_behind_holds_the_stage(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=2)

    assert stage(target_projection(paths)) == (None, "core_data_pending")


def test_a_core_conflict_holds_the_stage(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths, stock_conflict=True)

    assert stage(target_projection(paths)) == (None, "core_data_pending")


def core(projection: ProjectionSet, asset: str) -> dict[str, Any]:
    return next(
        item for item in projection.datasets["core_assets"]["assets"] if item["asset"] == asset
    )


def test_a_core_session_missing_inside_the_window_holds_the_stage(tmp_path: Path) -> None:
    # Gate ①: the window has a session the visible series lacks.
    paths = runtime(tmp_path)
    seed_cores(paths, stock_gap=sessions()[-10])

    projection = target_projection(paths)

    assert stage(projection) == (None, "core_data_pending")
    assert core(projection, "stock")["reason"] == "window_session_missing"


def test_a_backfilled_day_is_held_only_by_a_session_missing_by_then(tmp_path: Path) -> None:
    # The same gate on a backfilled day, over its own window (ticket 11).
    paths = runtime(tmp_path)
    days = sessions()
    seed_cores(paths, stock_gap=days[-4])
    before, after = days[-6].isoformat(), days[-3].isoformat()

    failed = summaries(paths).backfill(
        (before, after), target=TARGET.isoformat(), system_as_of=CUTOFF
    )

    assert failed == ()
    assert stage(summary(paths, before))[0] == "stage_iii"
    assert stage(summary(paths, after)) == (None, "core_data_pending")
    assert core(summary(paths, after), "stock")["reason"] == "window_session_missing"


def test_a_day_summarized_again_without_a_stage_is_no_longer_the_last_confirmed_one(
    tmp_path: Path,
) -> None:
    # Each day counts by its latest summary (ADR-0040): a day summarized again without a
    # stage, the target among them, no longer has one, so the day looks back past the window.
    paths = runtime(tmp_path)
    seed_cores(paths)
    staged = sessions()[-6]
    module = summaries(paths)
    asked: list[date] = []

    def summarize(day: date, minutes: int) -> ProjectionSet:
        def look_back(_readiness: object, window_start: date) -> None:
            asked.append(window_start)

        result = module.summarize_target(
            day.isoformat(),
            system_as_of=CUTOFF + timedelta(minutes=minutes),
            run_materials=RunMaterials(look_back=look_back),
        ).result
        assert result.projection_set_id is not None
        return ProjectionSetRepository(paths.database).get(result.projection_set_id)

    assert stage(summarize(staged, 0))[0] == "stage_iii"
    EvidenceRepository(paths.database).append_source_claims(
        (stock_conflict(staged), stock_conflict(TARGET))
    )

    assert stage(summarize(staged, 1)) == (None, "core_data_pending")
    projection = summarize(TARGET, 2)

    assert stage(projection) == (None, "core_data_pending")
    assert projection.datasets["cycle_overview"]["last_confirmed_stage"] is None
    assert asked == [staged, TARGET]


def stock_conflict(day: date) -> SourceClaimInput:
    """An official stock close that disagrees with TuShare's: the day's stage is held."""
    api_name, code = CORE_API_IDENTITIES["CN_EQUITY_CORE_000985"]
    return replace(
        claim(
            "CN_EQUITY_CORE_000985",
            day,
            1.0,
            unit="index_points",
            provider="official",
            reference=f"official:{code}:{day}",
        ),
        release_event_id=f"official:{code}:{day}",
    )


def test_a_backfilled_day_the_calendar_does_not_reach_back_for_fails(tmp_path: Path) -> None:
    # Its window is not guessed from weekdays: the day is left for a later run.
    paths = runtime(tmp_path)
    seed_cores(paths)
    days = sessions()
    reached, unreached = days[-5].isoformat(), days[-20].isoformat()

    failed = summaries(paths, TradingCalendar(days[-130:])).backfill(
        (unreached, reached), target=TARGET.isoformat(), system_as_of=CUTOFF
    )

    assert failed == (FailedDay(unreached, "LookupError"),)
    assert stage(summary(paths, reached))[0] == "stage_iii"


def test_a_day_that_cannot_be_summarized_is_returned_and_the_rest_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    window = tuple(day.isoformat() for day in sessions()[-5:])
    broken = window[1]
    build = day_summary.build_context_projection

    def failing(*args: Any, **kwargs: Any) -> Any:
        if kwargs["target_business_date"] == broken:
            raise ValueError("fixture_context_failed")
        return build(*args, **kwargs)

    monkeypatch.setattr(day_summary, "build_context_projection", failing)

    failed = summaries(paths).backfill(window, target=window[-1], system_as_of=CUTOFF)

    assert failed == (FailedDay(broken, "ValueError"),)
    summarized = {
        event["business_date"] for event in ProjectionSetRepository(paths.database).stage_history()
    }
    assert broken not in summarized
    assert {window[0], window[2], window[3]} <= set(summarized)
    assert window[-1] not in summarized  # the target is summarized by the run, not here


def test_a_failed_backfill_day_does_not_stop_the_target_and_is_told_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    window = tuple(day.isoformat() for day in sessions()[-5:])
    broken = window[1]
    build = day_summary.build_context_projection

    def failing(*args: Any, **kwargs: Any) -> Any:
        if kwargs["target_business_date"] == broken:
            raise ValueError("fixture_context_failed")
        return build(*args, **kwargs)

    monkeypatch.setattr(day_summary, "build_context_projection", failing)
    heard: list[object] = []

    target = summaries(paths).summarize_target(
        TARGET.isoformat(),
        system_as_of=CUTOFF,
        run_materials=RunMaterials(
            step_done=heard.append,
            snapshot_frozen=lambda snapshot_id: heard.append(("snapshot", snapshot_id)),
            day_failed=heard.append,
        ),
        backfill_window=window,
    )

    assert target.result.status == "published"
    assert target.failed_days == (FailedDay(broken, "ValueError"),)
    assert heard == [
        "core_readiness",
        "context",
        FailedDay(broken, "ValueError"),
        "backfill",
        ("snapshot", target.evidence_snapshot_id),
    ]


def test_only_the_target_day_moves_the_current_projection(tmp_path: Path) -> None:
    # A run that stops after its backfill leaves the page on the last whole set (ticket 13).
    paths = runtime(tmp_path)
    seed_cores(paths)
    days = [day.isoformat() for day in sessions()]
    projections = ProjectionSetRepository(paths.database)
    module = summaries(paths)

    assert module.backfill(tuple(days[-6:-1]), target=days[-1], system_as_of=CUTOFF) == ()
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        projections.current()
    earlier = module.summarize_target(
        days[-10], system_as_of=CUTOFF, run_materials=RunMaterials()
    ).result.projection_set_id
    assert module.backfill(tuple(days[-9:-6]), target=days[-1], system_as_of=CUTOFF) == ()
    assert projections.current().envelope.projection_set_id == earlier

    target = module.summarize_target(
        days[-1], system_as_of=CUTOFF, run_materials=RunMaterials()
    ).result
    assert projections.current().envelope.projection_set_id == target.projection_set_id
    assert summary(paths, days[-3]).envelope.target_business_date == days[-3]


def test_a_stored_set_published_again_is_kept_once_and_may_take_the_pointer(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    service = P0ProjectionService(ProjectionSetRepository(paths.database))
    readiness = summaries(paths)._core_readiness(TARGET.isoformat(), system_as_of=CUTOFF)

    def publish(*, as_current: bool) -> str | None:
        return service.publish(
            target_business_date=TARGET.isoformat(),
            system_as_of=CUTOFF,
            assets=readiness,
            last_confirmed_stage=None,
            as_current=as_current,
        ).projection_set_id

    history = publish(as_current=False)
    assert publish(as_current=False) == history
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()
    assert publish(as_current=True) == history
    assert ProjectionSetRepository(paths.database).current().envelope.projection_set_id == history
    assert query(paths, "SELECT count(*) FROM projection_set") == [(1,)]


def test_the_backfill_rebuilds_the_stage_history_day_by_day(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    window = tuple(day.isoformat() for day in sessions()[-10:])

    target = summaries(paths).summarize_target(
        TARGET.isoformat(),
        system_as_of=CUTOFF,
        run_materials=RunMaterials(),
        backfill_window=window,
    )

    assert target.failed_days == ()
    assert target.result.projection_set_id is not None
    projection = ProjectionSetRepository(paths.database).get(target.result.projection_set_id)
    history = projection.datasets["stage_history"]["events"]
    assert [event["business_date"] for event in history] == list(window)


def test_a_day_summarized_later_keeps_no_later_stage_event(tmp_path: Path) -> None:
    # A set is the record as of its day: a missed day filled after the next one (ticket 14).
    paths = runtime(tmp_path)
    seed_cores(paths)
    days = [day.isoformat() for day in sessions()]
    module = summaries(paths)
    assert module.backfill((days[-3],), target=days[-1], system_as_of=CUTOFF) == ()
    module.summarize_target(days[-1], system_as_of=CUTOFF, run_materials=RunMaterials())
    target_history = events(summary(paths, days[-1]))

    assert module.backfill((days[-2],), target=days[-1], system_as_of=CUTOFF) == ()

    assert events(summary(paths, days[-2])) == [days[-3], days[-2]]
    assert events(summary(paths, days[-1])) == target_history == [days[-3], days[-1]]
    # Read whole, the history still has every day.
    history = ProjectionSetRepository(paths.database).stage_history()
    assert [event["business_date"] for event in history] == days[-3:]


def events(projection: ProjectionSet) -> list[str]:
    return [event["business_date"] for event in projection.datasets["stage_history"]["events"]]


def test_the_backfilled_days_read_their_series_from_one_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ticket 29: the days share one copy of the claims, opened for the backfill alone."""
    paths = runtime(tmp_path)
    seed_cores(paths)
    days = [day.isoformat() for day in sessions()]
    snapshots: list[object] = []
    original = EvidenceRepository.metric_series

    def noted(self: EvidenceRepository, *args: Any, **kwargs: Any) -> Any:
        snapshots.append(self._series_snapshot)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(EvidenceRepository, "metric_series", noted)
    module = summaries(paths)

    assert module.backfill(tuple(days[-4:-1]), target=days[-1], system_as_of=CUTOFF) == ()
    assert len(snapshots) >= 3
    assert snapshots[0] is not None
    assert all(snapshot is snapshots[0] for snapshot in snapshots)
    assert module._evidence._series_snapshot is None


def july_cpi_public_on_5_august(paths: RuntimePaths) -> Any:
    public = datetime(2026, 8, 5, 9, 30, tzinfo=SHANGHAI)
    acquired = datetime(2026, 8, 6, tzinfo=UTC)
    return EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_CPI_HEADLINE",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start="2026-07-01",
            period_end="2026-07-31",
            dimensions={"measure": "yoy", "category": "headline"},
            value=0.5,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="fixture",
            source_reference="fixture:cpi:2026-07",
            release_event_id="fixture:cpi:2026-07",
            release_at=public,
            public_available_at=public,
            fetched_at=acquired,
            available_at=acquired,
            quality_status="validated",
        )
    )


def test_a_backfilled_day_sees_only_what_was_public_by_its_end(tmp_path: Path) -> None:
    # Moved from test_backfill: July's CPI became public on 5 August.
    paths = runtime(tmp_path)
    seed_cores(paths)
    cpi = july_cpi_public_on_5_august(paths)
    module = summaries(paths)
    for day in ("2026-08-04", "2026-08-05"):
        assert module.backfill((day,), target=TARGET.isoformat(), system_as_of=CUTOFF) == ()

    assert "2026-07-31" not in cpi_periods(summary(paths, "2026-08-04"))
    assert "2026-07-31" in cpi_periods(summary(paths, "2026-08-05"))
    # Each day froze the inputs it read, as the target does (ticket 12).
    for day, cpi_visible in (("2026-08-04", False), ("2026-08-05", True)):
        projection = summary(paths, day)
        members = snapshot_members(paths, projection.envelope.evidence_snapshot_id)
        assert (cpi.claim_id in members) is cpi_visible
        assert read_inputs(projection) <= members
        # Nothing the day did not read: each member is one the day's projection names.
        published = json.dumps(projection.datasets)
        assert all(member in published for member in members)


def test_a_day_summarized_on_an_older_core_history_is_corrected_as_of_its_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ticket 07: summarized again the same way, from what was public by the day's end, and
    # appended beside the summary it corrects; a day already on the basis is left alone.
    paths = runtime(tmp_path)
    seed_cores(paths)
    july_cpi_public_on_5_august(paths)
    repository = ProjectionSetRepository(paths.database)
    days = ("2026-08-04", "2026-08-05")
    with monkeypatch.context() as patch:
        patch.setattr(day_summary, "CORE_HISTORY_BASIS", "core-history-v0001")
        assert summaries(paths).backfill(days, target=TARGET.isoformat(), system_as_of=CUTOFF) == ()
    old = {event["business_date"]: event for event in repository.stage_history()}

    later = CUTOFF + timedelta(days=1)
    assert summaries(paths).backfill(days, target=TARGET.isoformat(), system_as_of=later) == ()
    assert summaries(paths).backfill(days, target=TARGET.isoformat(), system_as_of=later) == ()

    latest = {event["business_date"]: event for event in repository.stage_history()}
    assert len(query(paths, "SELECT 1 FROM p0_assessment")) == 4
    for day, cpi_visible in zip(days, (False, True), strict=True):
        assert latest[day]["corrects"] == {
            "assessment_id": old[day]["assessment_id"],
            "projection_set_id": old[day]["projection_set_id"],
            "reason": "core_history_basis_changed",
        }
        assert repository.p0_assessment(str(old[day]["assessment_id"])) == old[day]
        projection = repository.get(str(latest[day]["projection_set_id"]))
        assert ("2026-07-31" in cpi_periods(projection)) is cpi_visible


def test_a_correction_made_at_the_corrected_summary_s_cutoff_is_its_day_s_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A run interrupted before ticket 07 and resumed after it keeps its batch and cutoff: its
    # correction is a set of its own, and the day's latest summary all the same.
    paths = runtime(tmp_path)
    seed_cores(paths)
    repository = ProjectionSetRepository(paths.database)
    days = tuple(day.isoformat() for day in sessions()[-12:-1])
    with monkeypatch.context() as patch:
        patch.setattr(day_summary, "CORE_HISTORY_BASIS", "core-history-v0001")
        assert summaries(paths).backfill(days, target=TARGET.isoformat(), system_as_of=CUTOFF) == ()
    old = {event["business_date"]: event for event in repository.stage_history()}

    assert summaries(paths).backfill(days, target=TARGET.isoformat(), system_as_of=CUTOFF) == ()

    latest = {event["business_date"]: event for event in repository.stage_history()}
    for day in days:
        assert latest[day]["corrects"]["assessment_id"] == old[day]["assessment_id"]
        assert latest[day]["projection_set_id"] != old[day]["projection_set_id"]
    assert repository.last_confirmed_stage(on_or_before=days[-1]) == "stage_iii"


def snapshot_members(paths: RuntimePaths, snapshot_id: str) -> set[str]:
    [(mode, cutoff, members)] = query(
        paths,
        "SELECT as_of_mode, as_of_cutoff, observation_version_ids_json FROM evidence_snapshot "
        "WHERE evidence_snapshot_id=?",
        snapshot_id,
    )
    assert (mode, datetime.fromisoformat(cutoff)) == (AsOfMode.SYSTEM.value, CUTOFF)
    return set(json.loads(members))


def read_inputs(projection: ProjectionSet) -> set[str]:
    """The cores shown and their model inputs, the context's model inputs and claims."""
    core = projection.datasets["core_assets"]
    macro = projection.datasets["macro"]
    shown = {version for item in core["assets"] for version in item["observation_version_ids"]}
    # The cores' preheat reaches before the 120 closes shown.
    assert set(core["model_input_observation_version_ids"]) - shown
    return {
        *shown,
        *core["model_input_observation_version_ids"],
        *macro["model_input_observation_version_ids"],
        *claim_ids((macro, projection.datasets["inventory"])),
    }


def claim_ids(value: object) -> set[str]:
    if isinstance(value, dict):
        found = {str(value["claim_id"])} if isinstance(value.get("claim_id"), str) else set()
        return found.union(*(claim_ids(item) for item in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(claim_ids(item) for item in value))
    return set()
