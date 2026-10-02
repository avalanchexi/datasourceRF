"""Where the context families' requests start: before the window, not two years back (#30)."""

from __future__ import annotations

from datetime import date

import pytest

from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.worker import context_fetch_starts

WEEKDAYS = TradingCalendar()


@pytest.mark.parametrize(
    ("first_day", "metric_id", "start"),
    [
        # On 2026-04-07 March's CPI is not out yet (it comes after the 9th), so February's
        # is the newest out and January's the one before it to compare with.
        (date(2026, 4, 7), "CN_CPI_HEADLINE", "202601"),
        (date(2026, 4, 20), "CN_CPI_HEADLINE", "202602"),
        # A month's PMI comes out on its last day; social financing mid-month after.
        (date(2026, 4, 7), "CN_PMI_ACTIVITY", "202602"),
        (date(2026, 4, 7), "CN_SF_TOTAL", "202601"),
        # Q1's GDP is out mid-April: 2025-Q4 newest on the 7th, Q3 before it.
        (date(2026, 4, 7), "CN_GDP", "2025Q3"),
        (date(2026, 4, 20), "CN_GDP", "2025Q4"),
    ],
)
def test_a_period_family_starts_at_the_period_before_the_newest_out_on_the_first_day(
    first_day: date, metric_id: str, start: str
) -> None:
    starts = context_fetch_starts(first_day, WEEKDAYS)

    assert starts.period(metric_id) == start


def test_a_daily_family_starts_two_weeks_before_the_window() -> None:
    # The newest value out on the first day and the one before it, in any market and
    # across the longest holiday.
    assert context_fetch_starts(date(2026, 10, 8), WEEKDAYS).daily == date(2026, 9, 24)


def test_a_family_starts_at_its_earliest_member() -> None:
    starts = context_fetch_starts(date(2026, 4, 7), WEEKDAYS)

    assert starts.period("CN_CPI_HEADLINE", "CN_PMI_ACTIVITY") == "202601"
