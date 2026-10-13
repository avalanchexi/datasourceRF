"""ADR-0030: the ex-hog basket without session evidence, chained on the held level."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from pring_cycle.basket import PRODUCT_EXCHANGES, PRODUCTS, basket_scalars, select_contract
from pring_cycle.tushare_context import TushareSourceError

SUFFIX = {"SHFE": "SHF", "DCE": "DCE", "CZCE": "ZCE", "INE": "INE"}
# Each product: a November contract expiring 2026-10-15, and a January one.
EXPIRIES = {"202611": "20261015", "202701": "20261215"}


def weekdays(start: date, end: date) -> list[date]:
    return [
        start + timedelta(days=n)
        for n in range((end - start).days + 1)
        if (start + timedelta(days=n)).weekday() < 5
    ]


def contract_rows(product: str) -> list[dict[str, object]]:
    exchange = PRODUCT_EXCHANGES[product]
    unit = "桶" if product == "SC" else "吨"
    return [
        {
            "ts_code": f"{product}{month[2:]}.{SUFFIX[exchange]}",
            "symbol": f"{product}{month[2:]}",
            "exchange": exchange,
            "fut_code": product,
            "d_month": month,
            "list_date": "20250101",
            "delist_date": expiry,
            "quote_unit": f"人民币元/{unit}",
            "per_unit": 10,
            "trade_unit": unit,
        }
        for month, expiry in EXPIRIES.items()
    ]


def fake_call(calls: list[tuple[str, dict[str, str]]], growth: float = 1.01):  # type: ignore[no-untyped-def]
    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append((api, params))
        if api == "fut_basic":
            return tuple(contract_rows(params["fut_code"]))
        if api == "fut_trade_cal":
            start = date.fromisoformat(params["start_date"])
            end = date.fromisoformat(params["end_date"])
            return tuple(
                {
                    "exchange": params["exchange"],
                    "cal_date": (start + timedelta(days=n)).strftime("%Y%m%d"),
                    "is_open": int((start + timedelta(days=n)).weekday() < 5),
                }
                for n in range((end - start).days + 1)
            )
        assert api == "fut_daily"
        return tuple(
            {
                "ts_code": params["ts_code"],
                "trade_date": d.strftime("%Y%m%d"),
                "pre_settle": 100.0,
                "settle": 100.0 * growth,
            }
            for d in weekdays(
                date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
            )
        )

    return call


def levels(scalars: Any) -> dict[str, float]:
    return {s.period_end: s.value for s in scalars if s.metric_id == "CN_COMMODITY_EX_HOG_BASKET"}


def test_without_a_held_level_the_chain_is_rebuilt_from_the_base_only_to_calculate() -> None:
    day = date(2026, 3, 13)  # The fifth trading day after the base.

    scalars = basket_scalars(fake_call([]), end_date=day, held_levels={})

    # Every product returns 1%, and the weights add up to one.
    assert levels(scalars)["2026-03-13"] == pytest.approx(1000 * 1.01**5)
    assert len(levels(scalars)) == 5  # The window's other days are output too.
    contributions = {
        s.dimensions["sleeve"]: s.value
        for s in scalars
        if s.metric_id == "CN_COMMODITY_SLEEVE_CONTRIBUTION" and s.period_end == "2026-03-13"
    }
    assert contributions["crude_oil"] == pytest.approx(0.2)
    assert contributions["textiles"] == pytest.approx(100 * 2 / 15 * 0.01)
    assert len(contributions) == 7


def test_a_held_previous_level_is_carried_on_and_only_the_new_day_fetched() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    scalars = basket_scalars(
        fake_call(calls),
        end_date=date(2026, 9, 24),
        # Every earlier day of the window is held already.
        held_levels={day: 1234.5 for day in weekdays(date(2026, 3, 9), date(2026, 9, 23))},
    )

    assert levels(scalars) == {"2026-09-24": pytest.approx(1234.5 * 1.01)}
    daily = [p for api, p in calls if api == "fut_daily"]
    assert len(daily) == len(PRODUCTS)
    assert {(p["start_date"], p["end_date"]) for p in daily} == {("20260924", "20260924")}


def test_a_contract_with_ten_or_fewer_open_days_left_rolls_to_the_next() -> None:
    contracts = [
        {"contract_code": "CU2611.SHF", "listed_on": "2025-01-01", "last_trade_date": "2026-10-15"},
        {"contract_code": "CU2701.SHF", "listed_on": "2025-01-01", "last_trade_date": "2026-12-15"},
        # Listed on the day itself: not yet known at the previous close.
        {"contract_code": "CU2610.SHF", "listed_on": "2026-09-30", "last_trade_date": "2026-10-10"},
    ]
    calendar = {
        date(2026, 9, 1) + timedelta(days=n): (date(2026, 9, 1) + timedelta(days=n)).weekday() < 5
        for n in range(200)
    }

    assert select_contract(contracts, calendar, date(2026, 9, 30)) == "CU2611.SHF"
    # 2026-10-01 leaves exactly ten weekdays to the 15th: roll.
    assert select_contract(contracts, calendar, date(2026, 10, 1)) == "CU2701.SHF"


def test_a_day_without_a_settlement_stops_the_chain_there() -> None:
    def missing_settle(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        rows = fake_call([])(api, params, fields)
        if api == "fut_daily":
            return tuple(
                {**row, "settle": None} if row["trade_date"] == "20260924" else row for row in rows
            )
        return rows

    scalars = basket_scalars(
        missing_settle,
        end_date=date(2026, 9, 25),
        held_levels={day: 1000.0 for day in weekdays(date(2026, 3, 9), date(2026, 9, 22))},
    )

    assert set(levels(scalars)) == {"2026-09-23"}


def test_two_contracts_with_one_expiry_are_not_resolved_by_guessing() -> None:
    contracts = [
        {"contract_code": "CU2611.SHF", "listed_on": "2025-01-01", "last_trade_date": "2026-11-16"},
        {
            "contract_code": "CU2611X.SHF",
            "listed_on": "2025-01-01",
            "last_trade_date": "2026-11-16",
        },
    ]
    calendar = {date(2026, 9, 1) + timedelta(days=n): True for n in range(120)}

    with pytest.raises(ValueError, match="commodity_expiry_ambiguous"):
        select_contract(contracts, calendar, date(2026, 9, 30))


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("ts_code", "CU2612.SHF", "identity"),
        ("exchange", "DCE", "identity"),
        ("quote_unit", "人民币元/桶", "unit"),
        ("per_unit", "not-a-number", "unit"),
    ],
)
def test_a_contract_row_that_is_not_its_delivery_month_is_refused(
    field: str, value: object, reason: str
) -> None:
    from pring_cycle.basket import contract_data

    row = {**contract_rows("CU")[0], field: value}

    with pytest.raises(ValueError, match=f"futures_input_contract_{reason}"):
        contract_data(row, "CU")


def test_a_duplicated_settlement_refuses_the_delivery() -> None:
    def duplicated(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        rows = fake_call([])(api, params, fields)
        if api == "fut_daily":
            return (*rows, {**rows[-1], "settle": 110.0})
        return rows

    with pytest.raises(ValueError, match="commodity_settlement_duplicate"):
        basket_scalars(
            duplicated,
            end_date=date(2026, 9, 24),
            held_levels={d: 1000.0 for d in weekdays(date(2026, 3, 9), date(2026, 9, 23))},
        )


def test_an_earlier_gap_does_not_stop_a_day_whose_previous_level_is_held() -> None:
    def missing_22nd(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        rows = fake_call([])(api, params, fields)
        if api == "fut_daily":
            return tuple(
                {**row, "settle": None} if row["trade_date"] == "20260922" else row for row in rows
            )
        return rows

    held = {d: 1000.0 for d in weekdays(date(2026, 3, 9), date(2026, 9, 21))}
    held[date(2026, 9, 23)] = 1200.0

    scalars = basket_scalars(missing_22nd, end_date=date(2026, 9, 24), held_levels=held)

    # The 22nd stays missing; the 24th builds on the held 23rd.
    assert levels(scalars) == {"2026-09-24": pytest.approx(1200.0 * 1.01)}


def test_nothing_computable_raises_the_first_reason() -> None:
    def ambiguous(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        rows = fake_call([])(api, params, fields)
        if api == "fut_basic":
            twin = {**rows[0], "ts_code": rows[0]["ts_code"], "d_month": rows[0]["d_month"]}
            return (*rows, twin)
        return rows

    with pytest.raises(ValueError, match="commodity_expiry_ambiguous"):
        basket_scalars(
            ambiguous,
            end_date=date(2026, 9, 24),
            held_levels={d: 1000.0 for d in weekdays(date(2026, 3, 9), date(2026, 9, 23))},
        )


# Ticket 06: a window all held is told from the four exchanges' calendars alone.
HELD_END = date(2026, 9, 24)
EXCHANGES = ("CZCE", "DCE", "INE", "SHFE")


def every_day_held() -> dict[date, float]:
    return {d: 1000.0 for d in weekdays(date(2026, 3, 9), HELD_END)}


def the_full_flow() -> list[str]:
    """The calls of the flow without a shortcut: contracts, then calendars to expiry."""
    return ["fut_basic"] * len(PRODUCTS) + ["fut_trade_cal"] * len(EXCHANGES)


def test_a_window_all_held_asks_only_the_four_calendars() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    assert basket_scalars(fake_call(calls), end_date=HELD_END, held_levels=every_day_held()) == ()

    assert [api for api, _ in calls] == ["fut_trade_cal"] * 4
    assert sorted((p["exchange"], p["start_date"], p["end_date"]) for _, p in calls) == [
        (exchange, "20260306", "20260924") for exchange in EXCHANGES
    ]


def without_day(missing: date, exchanges: tuple[str, ...] = EXCHANGES):  # type: ignore[no-untyped-def]
    """Calendars of ``exchanges`` that leave ``missing`` out."""

    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append(api)
        rows = fake_call([])(api, params, fields)
        if api == "fut_trade_cal" and params["exchange"] in exchanges:
            return tuple(row for row in rows if row["cal_date"] != missing.strftime("%Y%m%d"))
        return rows

    calls: list[str] = []
    return call, calls


def first_calendar_failing(answer: Any = None):  # type: ignore[no-untyped-def]
    """Calls (``answer``'s) whose first calendar request fails: the full flow alone answers."""
    answer = answer or fake_call([])

    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append(api)
        if api == "fut_trade_cal" and calls.count("fut_trade_cal") == 1:
            raise OSError("timed out")
        return answer(api, params, fields)

    calls: list[str] = []
    return call, calls


def outcome(call: Any, held: dict[date, float]) -> object:
    """What the basket returns, or the reason it raised."""
    try:
        return basket_scalars(call, end_date=HELD_END, held_levels=held)
    except ValueError as error:
        return str(error)


@pytest.mark.parametrize(
    ("exchanges", "asked", "expected"),
    [
        # As before: a day no calendar lists is no basket day.
        (EXCHANGES, 1, ()),
        # As before: one exchange not listing a day the others trade cannot choose for it.
        (("SHFE",), 4, "commodity_trading_day_unavailable"),
    ],
    ids=["all_four_leave_it_out", "one_leaves_it_out"],
)
def test_calendars_leaving_a_day_out_never_say_the_window_is_all_held(
    exchanges: tuple[str, ...], asked: int, expected: object
) -> None:
    missing = date(2026, 9, 23)
    held = every_day_held()
    del held[missing]  # The day left out is the one not held.
    call, calls = without_day(missing, exchanges)

    result = outcome(call, held)

    # Not taken for all held: the first calendar leaving the day out stops the shortcut, and
    # the contracts and their calendars decide, as before.
    assert calls[:asked] == ["fut_trade_cal"] * asked
    assert calls[asked : asked + 12] == the_full_flow()
    reference, _ = first_calendar_failing(without_day(missing, exchanges)[0])
    assert result == outcome(reference, held) == expected


@pytest.mark.parametrize(
    "spoil",
    [
        lambda rows: (*rows, rows[-1]),  # a day stated twice
        lambda rows: ({**rows[0], "is_open": "Y"}, *rows[1:]),  # a day stated otherwise
        lambda rows: ({**rows[0], "exchange": "DCE"}, *rows[1:]),  # another exchange's day
    ],
    ids=["duplicated_day", "unknown_open_flag", "foreign_exchange"],
)
def test_a_calendar_stating_a_day_oddly_never_says_the_window_is_all_held(spoil: Any) -> None:
    calls: list[str] = []

    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append(api)
        rows = fake_call([])(api, params, fields)
        return spoil(rows) if api == "fut_trade_cal" and calls.count(api) == 1 else rows

    assert basket_scalars(call, end_date=HELD_END, held_levels=every_day_held()) == ()
    assert calls == ["fut_trade_cal", *the_full_flow()]


def first_calendar_raising(error: Exception):  # type: ignore[no-untyped-def]
    """Calls whose first calendar request raises ``error``; every other answers."""

    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append(api)
        if api == "fut_trade_cal" and calls.count(api) == 1:
            raise error
        return fake_call([])(api, params, fields)

    calls: list[str] = []
    return call, calls


def at_step(error: Exception, step: str) -> Exception:
    error.acquisition_step = step  # type: ignore[attr-defined]
    return error


@pytest.mark.parametrize(
    "error",
    [
        at_step(OSError("disk_full"), "store"),
        at_step(ValueError("receipt_unreadable"), "normalize"),
        at_step(OSError("quota_held_back"), "start"),
    ],
    ids=["storing_failed", "reading_back_failed", "not_sent"],
)
def test_this_system_failing_or_a_call_not_made_is_raised_not_fallen_back_from(
    error: Exception,
) -> None:
    call, calls = first_calendar_raising(error)

    with pytest.raises(type(error)) as raised:
        basket_scalars(call, end_date=HELD_END, held_levels=every_day_held())

    assert raised.value is error and calls == ["fut_trade_cal"]


@pytest.mark.parametrize(
    "error",
    [
        at_step(OSError("timed out"), "request"),
        TushareSourceError("tushare_source_failed:40001", external_code=40001),
        at_step(ValueError("tushare_response_row_invalid"), "parse"),
    ],
    ids=["no_answer", "source_refused", "answer_refused"],
)
def test_the_source_failing_or_its_answer_refused_falls_back(error: Exception) -> None:
    call, calls = first_calendar_raising(error)

    assert basket_scalars(call, end_date=HELD_END, held_levels=every_day_held()) == ()
    assert calls == ["fut_trade_cal", *the_full_flow()]


def test_a_failed_calendar_falls_back_to_the_full_flow() -> None:
    call, calls = first_calendar_failing()

    assert basket_scalars(call, end_date=HELD_END, held_levels=every_day_held()) == ()

    # The failed request stops the shortcut; nothing else is asked for it.
    assert calls == ["fut_trade_cal", *the_full_flow()]


def test_a_window_with_a_day_not_held_selects_as_the_full_flow_does() -> None:
    held = every_day_held()
    del held[HELD_END]
    calls: list[tuple[str, dict[str, str]]] = []

    scalars = basket_scalars(fake_call(calls), end_date=HELD_END, held_levels=held)

    assert levels(scalars) == {"2026-09-24": pytest.approx(1000.0 * 1.01)}
    sent = [api for api, _ in calls]
    assert sent[:4] == ["fut_trade_cal"] * 4
    assert sent[4:16] == the_full_flow()
    assert sent[16:] == ["fut_daily"] * len(PRODUCTS)
    reference, _ = first_calendar_failing()
    assert scalars == basket_scalars(reference, end_date=HELD_END, held_levels=held)
