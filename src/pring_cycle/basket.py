"""The ex-hog commodity basket from TuShare's contracts, calendars and settlements (ADR-0030).

Eight products in seven sleeves, fixed weights restored each day. On a trading day T each
product holds the nearest-expiry contract listed before T with strictly more than ten of its
exchange's open days left after T; only what was known at T-1's close decides the choice.
A product's return is that contract's ``settle / pre_settle - 1`` on T, so a roll never
divides one contract by another. The basket starts at 1000 on 2026-03-06 and each day
multiplies the previous day's held level by one plus its return; without that level the
chain is rebuilt from the base for the calculation only, and only the requested days are
returned.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pring_cycle.tushare_context import ContextScalar

FORMULA_VERSION = "ex-hog-calendar-settlement-v0003"
SOURCE_CODE = "tushare:fut_daily:" + FORMULA_VERSION
BASE_DATE = date(2026, 3, 6)
BASE_LEVEL = Fraction(1000)
SLEEVES: tuple[tuple[str, tuple[str, ...], Fraction], ...] = (
    ("copper", ("CU",), Fraction(2, 15)),
    ("rebar", ("RB",), Fraction(2, 15)),
    ("polypropylene", ("PP",), Fraction(2, 15)),
    ("textiles", ("CF", "TA"), Fraction(2, 15)),
    ("rubber", ("RU",), Fraction(2, 15)),
    ("pulp", ("SP",), Fraction(2, 15)),
    ("crude_oil", ("SC",), Fraction(1, 5)),
)
PRODUCTS = tuple(product for _, members, _ in SLEEVES for product in members)
BASKET_METRICS = frozenset({"CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"})
API_NAME = "commodity_basket"

PRODUCT_EXCHANGES = {
    "CU": "SHFE",
    "RB": "SHFE",
    "PP": "DCE",
    "CF": "CZCE",
    "TA": "CZCE",
    "RU": "SHFE",
    "SP": "SHFE",
    "SC": "INE",
}
CONTRACT_FIELDS = (
    "ts_code",
    "symbol",
    "exchange",
    "fut_code",
    "d_month",
    "list_date",
    "delist_date",
    "quote_unit",
    "per_unit",
    "trade_unit",
)

Rows = tuple[dict[str, object], ...]
Call = Callable[[str, dict[str, str], tuple[str, ...]], Rows]


def contract_data(row: dict[str, object], product: str) -> dict[str, Any]:
    """One ``fut_basic`` row as a real delivery-month contract of ``product``, or refused."""
    exchange = PRODUCT_EXCHANGES[product]
    suffix = {"SHFE": "SHF", "DCE": "DCE", "CZCE": "ZCE", "INE": "INE"}[exchange]
    month = str(row["d_month"])
    if re.fullmatch(r"[0-9]{6}", month) is None:
        raise ValueError("futures_input_contract_identity_mismatch")
    date(int(month[:4]), int(month[4:]), 1)
    symbols = {product + month[2:]}
    if exchange == "CZCE":
        symbols.add(product + month[3:])
    if (
        row["exchange"] != exchange
        or row["fut_code"] != product
        or row["ts_code"] != product + month[2:] + "." + suffix
        or str(row["symbol"]).upper() not in symbols
    ):
        raise ValueError("futures_input_contract_identity_mismatch")
    unit = "桶" if product == "SC" else "吨"
    try:
        multiplier = Decimal(str(row["per_unit"]))
    except InvalidOperation as error:
        raise ValueError("futures_input_contract_unit_invalid") from error
    if (
        row["quote_unit"] != "人民币元/" + unit
        or row["trade_unit"] != unit
        or not multiplier.is_finite()
        or multiplier <= 0
    ):
        raise ValueError("futures_input_contract_unit_invalid")
    return {
        "contract_code": str(row["ts_code"]),
        "listed_on": _day(row["list_date"]).isoformat(),
        "last_trade_date": _day(row["delist_date"]).isoformat(),
    }


def _day(value: object) -> date:
    return date.fromisoformat(str(value))


def select_contract(
    contracts: list[dict[str, Any]], calendar: Mapping[date, bool], day: date
) -> str:
    """The v0002 calendar rule, from contracts listed before ``day``.

    ``calendar`` is the exchange's open (True) or closed (False) days; a day it lacks up to
    a candidate's expiry makes the choice unknowable.
    """
    if calendar.get(day) is not True:
        raise ValueError("commodity_trading_day_unavailable")
    known = sorted(
        (c for c in contracts if _day(c["listed_on"]) < day),
        key=lambda c: str(c["last_trade_date"]),
    )
    for contract in known:
        expiry = _day(contract["last_trade_date"])
        following = [day + timedelta(days=n) for n in range(1, (expiry - day).days + 1)]
        if any(d not in calendar for d in following):
            raise ValueError("commodity_calendar_unavailable")
        if sum(calendar[d] for d in following) <= 10:
            continue
        if sum(c["last_trade_date"] == contract["last_trade_date"] for c in known) != 1:
            raise ValueError("commodity_expiry_ambiguous")
        return str(contract["contract_code"])
    raise ValueError("commodity_eligible_contract_missing")


def _settlement(value: object) -> Fraction:
    if value is None or isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("commodity_settlement_unavailable")
    number = Fraction(str(value))
    if number <= 0:
        raise ValueError("commodity_settlement_unavailable")
    return number


def basket_scalars(
    call: Call,
    *,
    end_date: date,
    held_levels: Mapping[date, float],
    window: int = 120,
) -> tuple[ContextScalar, ...]:
    """The level and sleeve contributions of each of the last ``window`` basket days to
    ``end_date`` that is not already held.

    ``held_levels`` are the levels already held; a held day anchors the chain, so only the
    days after it are recalculated. A day the chain cannot compute breaks it until the next
    held level; when no requested day can be computed, the first reason is raised.
    """
    if end_date <= BASE_DATE:
        return ()
    if _window_held(call, end_date=end_date, held_levels=held_levels, window=window):
        return ()
    contracts: dict[str, list[dict[str, Any]]] = {}
    for product in PRODUCTS:
        rows = call(
            "fut_basic",
            {"exchange": PRODUCT_EXCHANGES[product], "fut_type": "1", "fut_code": product},
            CONTRACT_FIELDS,
        )
        contracts[product] = [
            contract
            for contract in (contract_data(row, product) for row in rows)
            if _day(contract["listed_on"]) <= end_date
            and _day(contract["last_trade_date"]) >= BASE_DATE
        ]
    calendars: dict[str, dict[date, bool]] = {}
    for exchange in sorted({PRODUCT_EXCHANGES[p] for p in PRODUCTS}):
        members = [c for p in PRODUCTS if PRODUCT_EXCHANGES[p] == exchange for c in contracts[p]]
        end = max([end_date, *(_day(c["last_trade_date"]) for c in members)])
        rows = call(
            "fut_trade_cal",
            {
                "exchange": exchange,
                "start_date": BASE_DATE.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            ("exchange", "cal_date", "is_open"),
        )
        calendars[exchange] = {_day(row["cal_date"]): str(row["is_open"]) == "1" for row in rows}
    # A day is a basket day when any exchange trades; all of them share China's holidays.
    chain = sorted(
        day
        for day in set().union(*calendars.values())
        if BASE_DATE < day <= end_date and any(c.get(day) for c in calendars.values())
    )
    if not chain:
        from pring_cycle.tushare_context import ContextObservationsMissingError

        # The calendars delivered no trading day: nothing to hold, which is not all held.
        raise ContextObservationsMissingError("source_empty")
    wanted = [day for day in chain[-window:] if day not in held_levels]
    if not wanted:
        return ()
    held = {day: Fraction(str(value)) for day, value in held_levels.items()}
    # Each requested day, and before it every day back to a held level (or the base).
    needed: set[date] = set()
    for day in wanted:
        index = chain.index(day)
        while index >= 0 and chain[index] not in held and chain[index] not in needed:
            needed.add(chain[index])
            index -= 1
    choices: dict[date, dict[str, str]] = {}
    failures: list[str] = []
    for day in sorted(needed):
        try:
            choices[day] = {
                product: select_contract(
                    contracts[product], calendars[PRODUCT_EXCHANGES[product]], day
                )
                for product in PRODUCTS
            }
        except ValueError as error:
            failures.append(str(error))
    settlements = _settlements(call, choices)
    scalars: list[ContextScalar] = []
    level: Fraction | None = BASE_LEVEL
    for day in chain:
        if day in held:
            level = held[day]
            continue
        if day not in needed:
            level = None  # Neither held nor needed: no later day builds on it.
            continue
        prices = (
            [settlements.get((choices[day][p], day)) for p in PRODUCTS] if day in choices else []
        )
        if level is None or not prices or any(price is None for price in prices):
            # The chain breaks here; a later day resumes only from a held level.
            if day in choices and level is not None:
                failures.append("commodity_settlement_unavailable")
            level = None
            continue
        returns = {
            product: price[0] / price[1] - 1
            for product, price in zip(PRODUCTS, prices, strict=True)
            if price is not None
        }
        contributions = {
            sleeve: weight * sum(returns[p] for p in members) / len(members)
            for sleeve, members, weight in SLEEVES
        }
        level *= 1 + sum(contributions.values())
        if day not in wanted:
            continue
        scalars.append(_scalar(day, "CN_COMMODITY_EX_HOG_BASKET", "level", level, "index_points"))
        scalars.extend(
            _scalar(
                day,
                "CN_COMMODITY_SLEEVE_CONTRIBUTION",
                sleeve,
                value * 100,
                "percentage_points",
                sleeve=sleeve,
            )
            for sleeve, value in contributions.items()
        )
    if not scalars and failures:
        # Nothing could be computed: the first reason is what the maintainer has to see.
        raise ValueError(failures[0])
    return tuple(scalars)


def _window_held(
    call: Call, *, end_date: date, held_levels: Mapping[date, float], window: int
) -> bool:
    """Whether every basket day of the window is held, told from the four exchanges'
    calendars to ``end_date`` alone: four requests, not the contracts' twelve (ticket 06).

    Only calendars stating each day from the base to ``end_date`` once, open or closed, can
    say so: one the source fails to answer or whose answer is refused, leaves a day out or
    states one otherwise says nothing, and the contracts and their calendars to expiry decide
    as before. This system failing to keep an answer, or a call not made, is raised.
    """
    days = {BASE_DATE + timedelta(days=n) for n in range((end_date - BASE_DATE).days + 1)}
    calendars: list[dict[date, bool]] = []
    for exchange in sorted(set(PRODUCT_EXCHANGES.values())):
        try:
            rows = call(
                "fut_trade_cal",
                {
                    "exchange": exchange,
                    "start_date": BASE_DATE.strftime("%Y%m%d"),
                    "end_date": end_date.strftime("%Y%m%d"),
                },
                ("exchange", "cal_date", "is_open"),
            )
            stated = {
                _day(row["cal_date"]): str(row["is_open"]) == "1"
                for row in rows
                if row["exchange"] == exchange and str(row["is_open"]) in ("0", "1")
            }
        except (OSError, ValueError) as error:
            from pring_cycle.acquisition_outcome import (
                SOURCE_FAILED,
                STRUCTURE_REJECTED,
                capture_failure,
            )

            if capture_failure(error)[0] not in {SOURCE_FAILED, STRUCTURE_REJECTED}:
                raise
            return False
        if len(rows) != len(days) or set(stated) != days:
            return False
        calendars.append(stated)
    chain = sorted(
        day
        for day in calendars[0]
        if BASE_DATE < day <= end_date and any(c[day] for c in calendars)
    )
    return bool(chain) and all(day in held_levels for day in chain[-window:])


def _scalar(
    day: date, metric_id: str, field: str, value: Fraction, unit: str, **dimensions: str
) -> ContextScalar:
    from pring_cycle.tushare_context import ContextScalar

    return ContextScalar(
        metric_id=metric_id,
        api_name=API_NAME,
        source_field=field,
        period_kind="business_day",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        dimensions={"formula_version": FORMULA_VERSION, **dimensions},
        value=float(value),
        unit=unit,
    )


def _settlements(
    call: Call, choices: dict[date, dict[str, str]]
) -> dict[tuple[str, date], tuple[Fraction, Fraction]]:
    """Each chosen contract's settle and pre-settle on the days it was chosen: one call each."""
    days_by_contract: dict[str, list[date]] = {}
    for day, chosen in choices.items():
        for code in chosen.values():
            days_by_contract.setdefault(code, []).append(day)
    prices: dict[tuple[str, date], tuple[Fraction, Fraction]] = {}
    unavailable: set[tuple[str, date]] = set()
    for code, days in sorted(days_by_contract.items()):
        rows = call(
            "fut_daily",
            {
                "ts_code": code,
                "start_date": min(days).strftime("%Y%m%d"),
                "end_date": max(days).strftime("%Y%m%d"),
            },
            ("ts_code", "trade_date", "pre_settle", "settle"),
        )
        wanted = set(days)
        for row in rows:
            day = _day(row["trade_date"])
            if row["ts_code"] != code:
                raise ValueError("commodity_settlement_identity_mismatch")
            if day in wanted:
                if (code, day) in prices or (code, day) in unavailable:
                    raise ValueError("commodity_settlement_duplicate")
                try:
                    prices[code, day] = (_settlement(row["settle"]), _settlement(row["pre_settle"]))
                except ValueError:
                    unavailable.add((code, day))  # That day stays uncomputable.
    return prices
