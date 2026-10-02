"""A domestic holiday is no due day; foreign metrics keep their own calendars (run-findings 01)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.freshness import assess
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.trading_calendar import TradingCalendar, judging_calendar
from tests.integration.test_trading_calendar import record_sse_calendar

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
