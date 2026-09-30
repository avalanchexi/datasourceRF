"""The day summary module: the summary rules, asked of one day at a time (ADR-0034)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.day_summary as day_summary
from pring_cycle.day_summary import DaySummaries, FailedDay, ModelRules, RunMaterials
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import cpi_periods, query, summary
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
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
    summarized = ProjectionSetRepository(paths.database).summarized_dates()
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


def test_a_backfilled_day_sees_only_what_was_public_by_its_end(tmp_path: Path) -> None:
    # Moved from test_backfill: July's CPI became public on 5 August.
    paths = runtime(tmp_path)
    seed_cores(paths)
    public = datetime(2026, 8, 5, 9, 30, tzinfo=SHANGHAI)
    acquired = datetime(2026, 8, 6, tzinfo=UTC)
    cpi = EvidenceRepository(paths.database).append_source_claim(
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
