"""ADR-0030: the ex-hog basket without session evidence, chained on the held level."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from pring_cycle.basket import PRODUCT_EXCHANGES, PRODUCTS, basket_scalars, select_contract

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
