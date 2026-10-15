"""Registered warrants read as a note on inventory, never counted (ADR-0037, macro ticket 08).

Each symbol's warrants on a day are its warehouses' total, one observation each however
many catalog versions defining them alike stamped it (ADR-0036). The model's frozen table
converts them to tonnes -- a CF sheet 40 tonnes, a TA sheet 5, a PP lot 5, CU, RB, RU and
SP already tonnes -- each conversion stating its input unit, weight basis, official ground
and when it holds; crude oil (SC) stays in barrels (expectation-table.md O2).

The reading is of the evidence window's first and last days every symbol read holds: each
symbol's change between them, their median, and how many rose, held or fell; the seven
symbols' tonnes together are told beside it, never in place of it. A symbol not held, or
held on a base of zero, has no change rate: neither is a change of nothing, and a day not
held is not filled with nothing. Registered warrants are not the industry's inventory.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

# A day's warehouses' total of a symbol, the unit it was delivered in, and the
# observations it rests on.
HeldDay = tuple[float, str, tuple[str, ...]]


@dataclass(frozen=True)
class Conversion:
    """One symbol's frozen conversion: ``factor`` of ``unit`` to one of ``input_unit``.

    It holds from ``effective_from`` to ``effective_until`` (ISO days, both kept), each
    open when None: a term in fact changing starts a new one.
    """

    symbol: str
    input_unit: str
    factor: float
    unit: str
    weight_basis: str
    basis: str
    effective_from: str | None = None
    effective_until: str | None = None

    def holds_on(self, day: str) -> bool:
        return (self.effective_from is None or self.effective_from <= day) and (
            self.effective_until is None or day <= self.effective_until
        )


@dataclass(frozen=True)
class WarrantRules:
    """The model's warrant conversions; those to tonnes are summed beside the reading."""

    conversions: tuple[Conversion, ...]

    @classmethod
    def parse(cls, value: object) -> WarrantRules:
        if not isinstance(value, list) or not value:
            raise ValueError("confirmation_warrant_conversions_invalid")
        conversions = []
        for item in value:
            if not isinstance(item, Mapping):
                raise ValueError("confirmation_warrant_conversions_invalid")
            texts = [item.get(name) for name in _TEXTS]
            bounds = [item.get(name) for name in ("effective_from", "effective_until")]
            factor = item.get("factor")
            if (
                not all(isinstance(text, str) and text for text in texts)
                or not all(bound is None or _iso_day(bound) for bound in bounds)
                or (None not in bounds and str(bounds[0]) > str(bounds[1]))
                or not isinstance(factor, (int, float))
                or isinstance(factor, bool)
                or not math.isfinite(factor)
                or factor <= 0
                or item.get("unit") not in _UNITS
            ):
                raise ValueError("confirmation_warrant_conversions_invalid")
            symbol, input_unit, unit, weight_basis, basis = (str(text) for text in texts)
            conversions.append(
                Conversion(
                    symbol,
                    input_unit,
                    float(factor),
                    unit,
                    weight_basis,
                    basis,
                    str(bounds[0]) if bounds[0] is not None else None,
                    str(bounds[1]) if bounds[1] is not None else None,
                )
            )
        for index, first in enumerate(conversions):
            # A symbol's conversions follow one another, none holding on a day another does.
            for second in conversions[index + 1 :]:
                if first.symbol == second.symbol and _overlap(first, second):
                    raise ValueError("confirmation_warrant_conversions_overlap")
        return cls(tuple(conversions))

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.symbol for item in self.conversions))

    @property
    def tonnes(self) -> tuple[str, ...]:
        """The symbols converted to tonnes: the seven summed beside the reading."""
        return tuple(
            dict.fromkeys(item.symbol for item in self.conversions if item.unit == "tonne")
        )

    def conversion(self, symbol: str, day: str) -> Conversion | None:
        return next(
            (item for item in self.conversions if item.symbol == symbol and item.holds_on(day)),
            None,
        )


_TEXTS = ("symbol", "input_unit", "unit", "weight_basis", "basis")
_UNITS = frozenset({"tonne", "barrel"})


def _iso_day(value: object) -> bool:
    """Whether ``value`` is a day as ISO states it, ``YYYY-MM-DD``."""
    if not isinstance(value, str):
        return False
    try:
        # A week date ("2026-W01-1") parses too, and compares as no day does.
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _overlap(first: Conversion, second: Conversion) -> bool:
    starts = [item for item in (first.effective_from, second.effective_from) if item is not None]
    ends = [item for item in (first.effective_until, second.effective_until) if item is not None]
    return not starts or not ends or max(starts) <= min(ends)


def registered_warrant_change(
    rules: WarrantRules,
    held: Mapping[str, Mapping[str, HeldDay]],
    *,
    window: tuple[str | None, str],
) -> dict[str, object]:
    """The registered warrants' change over the evidence ``window`` (first and last day).

    ``held`` is each symbol's warehouses' total by day, as delivered; a day outside the
    window is not read. A day whose unit is not the input unit its conversion states, or
    that no conversion holds on, is not read either: it is named, never converted
    otherwise.
    """
    converted: dict[str, dict[str, tuple[float, tuple[str, ...]]]] = {}
    refused: dict[str, list[str]] = {}
    for symbol in rules.symbols:
        own: dict[str, tuple[float, tuple[str, ...]]] = {}
        for day, (total, unit, versions) in sorted(held.get(symbol, {}).items()):
            if (window[0] is not None and day < window[0]) or day > window[1]:
                continue
            conversion = rules.conversion(symbol, day)
            if conversion is None or unit != conversion.input_unit:
                refused.setdefault(symbol, []).append(day)
                continue
            own[day] = (total * conversion.factor, versions)
        converted[symbol] = own
    read = [symbol for symbol in rules.symbols if converted[symbol]]
    common = sorted(set.intersection(*(set(converted[symbol]) for symbol in read))) if read else []
    first, last = (common[0], common[-1]) if len(common) >= 2 else (None, None)
    symbols: list[dict[str, object]] = []
    rates: list[float] = []
    directions: dict[str, str] = {}
    inputs: list[str] = []
    for symbol in rules.symbols:
        conversion = rules.conversion(symbol, last or window[1])
        days = converted[symbol]
        document: dict[str, object] = {
            "symbol": symbol,
            "input_unit": conversion.input_unit if conversion is not None else None,
            "factor": conversion.factor if conversion is not None else None,
            "unit": conversion.unit if conversion is not None else None,
            "weight_basis": conversion.weight_basis if conversion is not None else None,
            "basis": conversion.basis if conversion is not None else None,
            "days_held": len(days),
            "days_refused": refused.get(symbol, []),
            "first": None,
            "last": None,
            "change_rate": None,
            "direction": None,
        }
        if not days:
            symbols.append(
                {**document, "status": "unit_refused" if symbol in refused else "missing"}
            )
            continue
        if first is None or last is None:
            symbols.append({**document, "status": "no_common_span"})
            continue
        (start, start_inputs), (end, end_inputs) = days[first], days[last]
        direction = _direction(end, start)
        directions[symbol] = direction
        inputs.extend((*start_inputs, *end_inputs))
        # A base of zero has no rate of change: never a change of nothing.
        rate = (end - start) / start if start != 0 else None
        if rate is not None:
            rates.append(rate)
        symbols.append(
            {
                **document,
                "status": "read" if rate is not None else "zero_base",
                "first": start,
                "last": end,
                "first_claim_ids": list(start_inputs),
                "last_claim_ids": list(end_inputs),
                "change_rate": rate,
                "direction": direction,
            }
        )
    missing = [f"{item['symbol']}:{item['status']}" for item in symbols if item["status"] != "read"]
    tonnes = rules.tonnes
    whole = first is not None and last is not None and all(s in directions for s in tonnes)
    summed = (
        {
            "first": sum(converted[symbol][str(first)][0] for symbol in tonnes),
            "last": sum(converted[symbol][str(last)][0] for symbol in tonnes),
        }
        if whole
        else None
    )
    return {
        "label": "注册库存变化",
        "counted": False,
        "window_start": window[0],
        "window_end": window[1],
        "first_day": first,
        "last_day": last,
        "symbols": symbols,
        "median_change_rate": statistics.median(rates) if rates else None,
        "breadth": {
            "increase": sum(1 for item in directions.values() if item == "up"),
            "flat": sum(1 for item in directions.values() if item == "flat"),
            "decrease": sum(1 for item in directions.values() if item == "down"),
            "read": len(directions),
            "symbols": len(rules.symbols),
        },
        # Beside the reading, never in its place: a tonne of copper is not a tonne of pulp.
        "tonnes": {
            "symbols": list(tonnes),
            "unit": "tonne",
            "first": summed["first"] if summed is not None else None,
            "last": summed["last"] if summed is not None else None,
            "change": summed["last"] - summed["first"] if summed is not None else None,
            "missing": [symbol for symbol in tonnes if symbol not in directions],
        },
        "missing": missing,
        "observation_version_ids": list(dict.fromkeys(inputs)),
    }


def _direction(value: float, previous: float) -> str:
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    if value - previous > tolerance:
        return "up"
    if previous - value > tolerance:
        return "down"
    return "flat"
