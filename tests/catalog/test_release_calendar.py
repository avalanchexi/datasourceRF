from __future__ import annotations

from datetime import UTC, datetime

from pring_cycle.release_calendar import (
    ReleasedObservation,
    ReleaseExpectation,
    assess_release_state,
    lpr_release_expectation,
)


def test_before_expected_window_reuses_previous_period_without_retrieval() -> None:
    expectation = ReleaseExpectation(
        metric_id="CN_CPI_HEADLINE",
        period="2026-08",
        window_start=datetime(2026, 9, 9, tzinfo=UTC),
        window_end=datetime(2026, 9, 10, tzinfo=UTC),
        grace_until=datetime(2026, 9, 11, tzinfo=UTC),
        timezone="Asia/Shanghai",
        rule_version="release-rule-v0001",
    )
    previous = ReleasedObservation(
        observation_id="obs:cpi:2026-07",
        period="2026-07",
        public_available_at=datetime(2026, 8, 10, tzinfo=UTC),
        available_at=datetime(2026, 8, 10, 1, tzinfo=UTC),
    )

    state = assess_release_state(
        expectation,
        as_of=datetime(2026, 9, 8, tzinfo=UTC),
        previous=previous,
    )

    assert state.status == "awaiting_release"
    assert state.display_period == "2026-07"
    assert state.should_retrieve is False
    assert state.observation_id == "obs:cpi:2026-07"


def test_stale_source_failure_conflict_and_not_disclosed_are_distinct() -> None:
    expectation = ReleaseExpectation(
        metric_id="CN_CPI_HEADLINE",
        period="2026-08",
        window_start=datetime(2026, 9, 9, tzinfo=UTC),
        window_end=datetime(2026, 9, 10, tzinfo=UTC),
        grace_until=datetime(2026, 9, 11, tzinfo=UTC),
        timezone="Asia/Shanghai",
        rule_version="release-rule-v0001",
    )
    as_of = datetime(2026, 9, 12, tzinfo=UTC)

    assert assess_release_state(expectation, as_of=as_of).status == "stale"
    assert (
        assess_release_state(expectation, as_of=as_of, retrieval_outcome="source_failed").status
        == "source_failed"
    )
    assert (
        assess_release_state(expectation, as_of=as_of, observation_conflicted=True).status
        == "conflicted"
    )
    assert (
        assess_release_state(expectation, as_of=as_of, value_state="not_disclosed").status
        == "not_disclosed"
    )


def test_unknown_p0_release_configuration_fails_closed() -> None:
    state = assess_release_state(
        None,
        as_of=datetime(2026, 9, 12, tzinfo=UTC),
        metric_id="CN_COMMODITY_CORE_NHII",
        priority="P0",
    )

    assert state.status == "unknown_release_configuration"
    assert state.blocks_formal_stage is True
    assert state.should_retrieve is False


def test_released_expected_period_becomes_current_and_unblocks_p0() -> None:
    expectation = ReleaseExpectation(
        metric_id="CN_EQUITY_CORE_000985",
        period="2026-08-28",
        window_start=datetime(2026, 8, 28, 7, 30, tzinfo=UTC),
        window_end=datetime(2026, 8, 28, 8, tzinfo=UTC),
        grace_until=datetime(2026, 8, 28, 9, tzinfo=UTC),
        timezone="Asia/Shanghai",
        rule_version="release-rule-v0001",
    )
    released = ReleasedObservation(
        observation_id="obs-equity-2026-08-28",
        period="2026-08-28",
        public_available_at=datetime(2026, 8, 28, 7, 31, tzinfo=UTC),
        available_at=datetime(2026, 8, 28, 7, 35, tzinfo=UTC),
    )

    state = assess_release_state(
        expectation,
        as_of=datetime(2026, 8, 28, 7, 40, tzinfo=UTC),
        previous=released,
        priority="P0",
    )

    assert state.status == "current"
    assert state.display_period == "2026-08-28"
    assert state.observation_id == "obs-equity-2026-08-28"
    assert state.should_retrieve is False
    assert state.blocks_formal_stage is False


def test_lpr_rule_uses_official_0900_shanghai_window_and_rolls_weekends() -> None:
    normal = lpr_release_expectation("2026-08")
    weekend = lpr_release_expectation("2026-06")

    assert normal.window_start.isoformat() == "2026-08-20T09:00:00+08:00"
    assert normal.window_end.isoformat() == "2026-08-20T09:05:00+08:00"
    assert normal.grace_until.isoformat() == "2026-08-20T12:00:00+08:00"
    assert normal.rule_version == "lpr-release-rule-v0001"
    assert weekend.window_start.isoformat() == "2026-06-22T09:00:00+08:00"


def test_lpr_rule_accepts_frozen_statutory_holidays_instead_of_guessing_release() -> None:
    expectation = lpr_release_expectation(
        "2026-09",
        holidays=("2026-09-21",),
    )

    assert expectation.window_start.isoformat() == "2026-09-22T09:00:00+08:00"
