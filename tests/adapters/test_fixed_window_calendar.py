"""China trading sessions keep administrative working weekends closed."""

from datetime import date, timedelta

import pytest

from pring_cycle.source_adapters import TushareCoreAdapter


def calendar_adapter(items: list[list[object]]) -> TushareCoreAdapter:
    response = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
    return TushareCoreAdapter("synthetic-token", transport=lambda _: response)


def every_day(start: date, end: date) -> list[list[object]]:
    """A ``trade_cal`` answer stating each day of the range, weekdays open."""
    days = (start + timedelta(days=n) for n in range((end - start).days + 1))
    return [[day.strftime("%Y%m%d"), int(day.weekday() < 5)] for day in days]


def test_public_calendar_rejects_administrative_working_sunday() -> None:
    adapter = calendar_adapter(
        [
            ["20260918", 1],
            ["20260919", 0],
            ["20260920", 1],
            ["20260921", 1],
            ["20260922", 1],
        ]
    )

    with pytest.raises(ValueError, match="china_trading_calendar_invalid"):
        adapter.trading_days(date(2026, 9, 18), date(2026, 9, 22))


def test_a_calendar_stating_every_day_gives_its_sessions() -> None:
    adapter = calendar_adapter(every_day(date(2026, 9, 18), date(2026, 9, 22)))

    assert adapter.trading_days(date(2026, 9, 18), date(2026, 9, 22)) == (
        date(2026, 9, 18),
        date(2026, 9, 21),
        date(2026, 9, 22),
    )


def test_flags_as_digits_in_any_row_order_are_read_alike() -> None:
    items = [[day, str(flag)] for day, flag in every_day(date(2026, 9, 18), date(2026, 9, 22))]
    adapter = calendar_adapter(items[::-1])

    assert adapter.trading_days(date(2026, 9, 18), date(2026, 9, 22)) == (
        date(2026, 9, 18),
        date(2026, 9, 21),
        date(2026, 9, 22),
    )


def test_an_answer_listing_no_day_is_missing() -> None:
    with pytest.raises(ValueError, match="china_trading_calendar_missing"):
        calendar_adapter([]).trading_days(date(2026, 9, 18), date(2026, 9, 22))


@pytest.mark.parametrize(
    "missing",
    [
        pytest.param(date(2026, 10, 9), id="today"),
        pytest.param(date(2026, 10, 7), id="a-middle-day"),
        pytest.param(date(2026, 9, 30), id="the-session-before"),
        pytest.param(date(2026, 9, 26), id="the-first-day"),
    ],
)
def test_a_day_the_answer_leaves_out_is_not_read_as_closed(missing: date) -> None:
    # A day TuShare does not list is unknown, not a holiday: the response does not cover it.
    items = [
        row
        for row in every_day(date(2026, 9, 26), date(2026, 10, 9))
        if row[0] != missing.strftime("%Y%m%d")
    ]
    adapter = calendar_adapter(items)

    with pytest.raises(ValueError, match="china_trading_calendar_incomplete"):
        adapter.trading_days(date(2026, 9, 26), date(2026, 10, 9))


@pytest.mark.parametrize("flag", [2, -1, "", None, "open", True])
def test_an_open_flag_other_than_zero_or_one_is_refused(flag: object) -> None:
    items = every_day(date(2026, 9, 21), date(2026, 9, 25))
    items[2] = [items[2][0], flag]
    adapter = calendar_adapter(items)

    with pytest.raises(ValueError, match="china_trading_calendar_invalid"):
        adapter.trading_days(date(2026, 9, 21), date(2026, 9, 25))
