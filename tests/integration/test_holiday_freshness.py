"""A domestic holiday is no due day; foreign metrics keep their own calendars (run-findings 01)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.freshness import assess
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.trading_calendar import TradingCalendar, acquire_sse_calendar, judging_calendar
from tests.integration.test_trading_calendar import record_sse_calendar, sse_adapter

HOLIDAYS = {date(2026, 9, 25), *(date(2026, 10, day) for day in range(1, 8))}


def sse_sessions(first: date, last: date) -> list[date]:
    return [
        first + timedelta(days=n)
        for n in range((last - first).days + 1)
        if (first + timedelta(days=n)).weekday() < 5 and first + timedelta(days=n) not in HOLIDAYS
    ]


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    # Fetched at launch: the response runs past the holiday, its closed days stated.
    record_sse_calendar(paths, sse_sessions(date(2026, 9, 1), date(2026, 10, 9)))
    return paths


def window(target: date) -> list[date]:
    return sse_sessions(date(2026, 9, 1), target)


# 2026-10-02 22:23 in Shanghai, the cutoff of the run of 2026-10-02 (target 2026-09-30).
NATIONAL_DAY = datetime(2026, 10, 2, 14, 23, tzinfo=UTC)


def test_national_day_is_not_due_for_a_domestic_daily_metric(paths: RuntimePaths) -> None:
    calendar = judging_calendar(paths, window(date(2026, 9, 30)), NATIONAL_DAY)

    for metric_id in ("CN_EQUITY_CORE_000985", "CN_EQ_ADV_DEC", "CN_SHIBOR_ON_1W_3M"):
        assessed = assess(metric_id, date(2026, 9, 30), NATIONAL_DAY, calendar)
        assert assessed.status != "stale", metric_id
        assert assessed.periods_behind in (0, None), metric_id


def test_every_day_of_national_day_holds_the_last_session_as_current(paths: RuntimePaths) -> None:
    for day in range(1, 8):
        judged = datetime(2026, 10, day, 14, tzinfo=UTC)
        calendar = judging_calendar(paths, window(date(2026, 9, 30)), judged)
        assessed = assess("CN_EQUITY_CORE_000985", date(2026, 9, 30), judged, calendar)
        assert assessed.status == "current", day


def test_the_last_session_s_value_is_awaited_through_the_holiday(paths: RuntimePaths) -> None:
    """DR007 held 9/29: 9/30's value has its grace session after the holiday, not on 10/01.

    The run of 2026-10-02 counted it two periods behind.
    """
    calendar = judging_calendar(paths, window(date(2026, 9, 30)), NATIONAL_DAY)

    assessed = assess("CN_DR007", date(2026, 9, 29), NATIONAL_DAY, calendar)
    assert assessed.status == "awaiting_release"
    assert assessed.periods_behind == 0


def test_the_window_alone_took_the_holiday_for_a_weekday(paths: RuntimePaths) -> None:
    """What the run of 2026-10-02 did: the reason the judging calendar reaches past it."""
    alone = TradingCalendar(window(date(2026, 9, 30)))

    assert assess("CN_EQUITY_CORE_000985", date(2026, 9, 30), NATIONAL_DAY, alone).status == "stale"


def test_mid_autumn_is_not_due_either(paths: RuntimePaths) -> None:
    judged = datetime(2026, 9, 26, 4, tzinfo=UTC)
    calendar = judging_calendar(paths, window(date(2026, 9, 24)), judged)

    assert assess("CN_DR007", date(2026, 9, 24), judged, calendar).status != "stale"


def test_a_foreign_metric_still_moves_on_its_own_market_s_days(paths: RuntimePaths) -> None:
    judging = judging_calendar(paths, window(date(2026, 9, 30)), NATIONAL_DAY)
    alone = TradingCalendar(window(date(2026, 9, 30)))

    for metric_id in ("CBOE_VIX_INDEX", "UST10Y_NOMINAL_YIELD"):
        held = date(2026, 9, 30)
        assert assess(metric_id, held, NATIONAL_DAY, judging) == assess(
            metric_id, held, NATIONAL_DAY, alone
        ), metric_id
    # Held a week back, the U.S. sessions of the Chinese holiday are owed.
    assert assess("CBOE_VIX_INDEX", date(2026, 9, 23), NATIONAL_DAY, judging).status == "stale"


def test_beyond_what_the_calendar_covers_weekdays_stand_in(paths: RuntimePaths) -> None:
    later = datetime(2026, 10, 20, 14, tzinfo=UTC)
    calendar = judging_calendar(paths, window(date(2026, 9, 30)), later)

    assert calendar.is_trading(date(2026, 10, 19))


@pytest.fixture
def bare(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "bare")
    initialize_runtime(paths)
    return paths


def record_range(paths: RuntimePaths, first: date, last: date) -> None:
    """One response stating every day from ``first`` to ``last``, its holidays closed."""
    at = datetime.combine(first, datetime.min.time(), tzinfo=UTC)
    acquire_sse_calendar(paths, sse_adapter(closed=HOLIDAYS, at=at), first, last)


DOMESTIC_DAILY = ("CN_EQUITY_CORE_000985", "CN_EQ_ADV_DEC", "CN_SHIBOR_ON_1W_3M", "CN_DR007")


def test_a_cutoff_a_day_past_the_stored_calendar_keeps_its_holidays(bare: RuntimePaths) -> None:
    """The stored calendar ends on the last day of National Day; the cutoff is the day after.

    The run of 2026-10-09 dropped the whole stretch for the one day uncovered and counted the
    holiday as sessions owed (lookback 12).
    """
    record_range(bare, date(2026, 9, 1), date(2026, 10, 7))
    judged = datetime(2026, 10, 8, 0, tzinfo=UTC)  # 08:00 in Shanghai
    calendar = judging_calendar(bare, window(date(2026, 9, 30)), judged)

    assert not any(calendar.is_trading(date(2026, 10, day)) for day in range(1, 8))
    assert calendar.is_trading(date(2026, 10, 8))
    for metric_id in DOMESTIC_DAILY:
        held = date(2026, 9, 30)
        assessed = assess(metric_id, held, judged, calendar)
        assert assessed.status == "current", metric_id
        assert assessed.periods_behind == 0, metric_id


def test_the_run_of_2026_10_09_judges_as_if_the_calendar_reached_its_cutoff(
    bare: RuntimePaths, paths: RuntimePaths
) -> None:
    """Stored to 10-08, cut off at 06:39 on 10-09: only 10-09 itself is left to weekdays."""
    record_range(bare, date(2026, 9, 1), date(2026, 10, 8))
    judged = datetime(2026, 10, 8, 22, 39, tzinfo=UTC)
    short = judging_calendar(bare, window(date(2026, 9, 30)), judged)
    full = judging_calendar(paths, window(date(2026, 9, 30)), judged)

    for metric_id in DOMESTIC_DAILY:
        held = date(2026, 9, 30)
        assessed = assess(metric_id, held, judged, short)
        assert assessed == assess(metric_id, held, judged, full), metric_id
        # 10-08's value is still within its grace, not five sessions owed.
        assert assessed.status == "awaiting_release", metric_id
        assert assessed.periods_behind == 0, metric_id


def test_a_cutoff_inside_the_stored_calendar_reads_it_as_before(paths: RuntimePaths) -> None:
    """Stored to 10-09 and judged on it: every stored session through the cutoff, as before."""
    judged = datetime(2026, 10, 9, 2, tzinfo=UTC)
    calendar = judging_calendar(paths, window(date(2026, 9, 30)), judged)
    before = TradingCalendar(
        sse_sessions(date(2026, 9, 1), date(2026, 10, 9)), through=date(2026, 10, 9)
    )

    days = [date(2026, 8, 20) + timedelta(days=n) for n in range(70)]
    assert [calendar.is_trading(day) for day in days] == [before.is_trading(day) for day in days]
    assert [calendar.covers(day) for day in days] == [before.covers(day) for day in days]


def test_known_days_past_a_gap_in_the_stored_calendar_still_answer(bare: RuntimePaths) -> None:
    """Only the days no response states fall back to weekdays."""
    record_range(bare, date(2026, 9, 1), date(2026, 9, 30))
    record_range(bare, date(2026, 10, 5), date(2026, 10, 20))
    judged = datetime(2026, 10, 9, 14, tzinfo=UTC)
    calendar = judging_calendar(bare, window(date(2026, 9, 30)), judged)

    assert calendar.is_trading(date(2026, 10, 1)) and calendar.is_trading(date(2026, 10, 2))
    assert not any(calendar.is_trading(date(2026, 10, day)) for day in (5, 6, 7))
    assert calendar.is_trading(date(2026, 10, 8))
    # What the source does not state stays out of what the calendar says it covers.
    assert not calendar.covers(date(2026, 10, 1))
