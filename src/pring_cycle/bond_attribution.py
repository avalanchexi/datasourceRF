"""Bond trend attribution: what drives the bond core's trend, told beside its state (ADR-0037).

Two axes are read from key indicators' main members: the policy dimension (easing,
tightening or neutral) and growth and inflation (the overheat and price dimensions:
stronger or weaker). With the bond core's bull or bear they name its driver by the
model's frozen table (expectation-table.md, 债券归因, every stage alike): fundamentals,
policy or liquidity, fundamentals and easing together, or unclear. It is a note beside the
bond's state: never counted, never read back into the bond's bull or bear, nor the formal
stage -- easing does not make a bull market.

An axis stands only where no reading not known could change it: signals that must agree
need every one known unless the known already split, and a majority must hold of every
signal, known or not. An axis not known, split or without a majority, a bond with no state
standing, or a combination the table does not name, leaves the driver unclear and says
why. Term premium is never attributed, and said so; the yield curve and credit spreads
will tell the unclear apart once connected.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Each axis and the dimensions whose key indicators it may read.
AXES = {"policy": frozenset({"policy"}), "growth_inflation": frozenset({"overheat", "price"})}
DRIVERS = ("fundamentals", "policy_liquidity", "fundamentals_and_easing", "unclear")
BOND_TRENDS = ("bull", "bear")
# What a signal may read of its indicator's main member, and the values each takes: a
# policy action, or the momentum.
READINGS = {
    "action": frozenset({"cut", "hike", "none"}),
    "momentum": frozenset({"up", "down", "flat"}),
}
# Every signal agreeing (a silent one aside), or a majority of all of them.
_COMBINES = ("agree", "majority")
# What an axis is when its signals do not name one of its values.
_UNSETTLED = ("mixed", "unconfirmed")
_TEXTS = ("label", "boundary", "term_premium", "unclear_refinement", "bond_unknown", "not_in_table")


@dataclass(frozen=True)
class Signal:
    """An indicator's main member read as ``reading``; each value it may take names the
    axis value it ``means``, and any other is silent."""

    indicator: str
    label: str
    reading: str
    means: Mapping[str, str]

    @property
    def name(self) -> str:
        return f"{self.indicator}:{self.reading}"


@dataclass(frozen=True)
class SignalReading:
    """A signal's value, None when not known, and what it misses."""

    value: str | None
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class Axis:
    key: str
    label: str
    combine: str
    signals: tuple[Signal, ...]
    # Every signal known and silent: the axis is this (agreeing signals alone).
    otherwise: str | None
    texts: Mapping[str, str]

    @property
    def values(self) -> frozenset[str]:
        named = {value for signal in self.signals for value in signal.means.values()}
        return frozenset(named | ({self.otherwise} if self.otherwise else set()))


@dataclass(frozen=True)
class Row:
    """A row of the table: the bond's trend and each axis value it takes (an axis it does
    not name, any), and the driver it names."""

    bond: str
    axes: Mapping[str, frozenset[str]]
    driver: str
    typical: str | None = None
    suspicion: str | None = None


@dataclass(frozen=True)
class AttributionRules:
    """A model's frozen rules for the bond's trend attribution."""

    core: str
    bond_texts: Mapping[str, str]
    axes: tuple[Axis, ...]
    table: tuple[Row, ...]
    drivers: Mapping[str, str]
    texts: Mapping[str, str]

    @property
    def signals(self) -> tuple[Signal, ...]:
        return tuple(signal for axis in self.axes for signal in axis.signals)

    @classmethod
    def parse(
        cls,
        value: object,
        *,
        indicators: Mapping[str, tuple[str, str]],
        acting: Collection[str],
    ) -> AttributionRules:
        """The rules of a confirmation document's ``bond_attribution``; ``indicators``
        names each key indicator's name and dimension, ``acting`` those read as actions."""
        try:
            document = _mapping(value)
            axes = tuple(_axis(item, indicators) for item in _list(document["axes"]))
            table = tuple(
                Row(
                    str(item["bond"]),
                    {
                        str(key): frozenset(str(value) for value in _list(item[key]))
                        for key in AXES
                        if key in item
                    },
                    str(item["driver"]),
                    str(item["typical"]) if item.get("typical") else None,
                    str(item["suspicion"]) if item.get("suspicion") else None,
                )
                for item in map(_mapping, _list(document["table"]))
            )
            rules = cls(
                str(document["core"]),
                _texts(document["bond"], BOND_TRENDS),
                axes,
                table,
                _texts(document["drivers"], DRIVERS),
                _texts(document["texts"], _TEXTS),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("confirmation_bond_attribution_invalid") from error
        by_key = {axis.key: axis for axis in axes}
        if (
            rules.core != "bond"
            or [axis.key for axis in axes] != list(AXES)
            or set(rules.drivers) != set(DRIVERS)
            or any(
                signal.indicator not in indicators
                or indicators[signal.indicator][1] not in AXES[axis.key]
                or signal.reading not in READINGS
                # An action is read of the indicators read as their actions.
                or (signal.reading == "action") is not (signal.indicator in acting)
                or not signal.means
                or set(signal.means) - READINGS[signal.reading]
                for axis in axes
                for signal in axis.signals
            )
            # A signal read twice would count twice.
            or len({signal.name for signal in rules.signals}) != len(rules.signals)
            or any(
                not axis.signals
                or axis.combine not in _COMBINES
                or (axis.otherwise is None) is (axis.combine == "agree")
                or axis.values & set(_UNSETTLED)
                or set(axis.texts) != axis.values | set(_UNSETTLED)
                for axis in axes
            )
            # A row's field misspelt would leave its axis taken as any.
            or any(
                set(item) - {"bond", "driver", "typical", "suspicion", *AXES}
                for item in map(_mapping, _list(_mapping(value)["table"]))
            )
            or any(
                row.bond not in BOND_TRENDS
                or row.driver not in DRIVERS
                or any(
                    not values or values - by_key[key].values for key, values in row.axes.items()
                )
                for row in table
            )
        ):
            raise ValueError("confirmation_bond_attribution_invalid")
        return rules


def bond_attribution_document(
    rules: AttributionRules,
    *,
    bond: str | None,
    readings: Mapping[str, SignalReading],
) -> dict[str, object]:
    """The driver of the bond's trend: ``bond`` is its state as its gate let it stand, None
    when none does; ``readings`` holds each signal by its name (``dr007:momentum``)."""
    axes = [_axis_document(axis, readings) for axis in rules.axes]
    values = {item["axis"]: item["value"] for item in axes}
    row = next(
        (
            item
            for item in rules.table
            if item.bond == bond
            and all(values[key] in allowed for key, allowed in item.axes.items())
        ),
        None,
    )
    reasons: list[dict[str, str]] = []
    if row is None and bond is None:
        reasons.append({"reason": "bond_unknown", "text": rules.texts["bond_unknown"]})
    # An axis not settled is said so, even under a row taking it as any.
    for axis, document in zip(rules.axes, axes, strict=True):
        if document["value"] in _UNSETTLED:
            missing = "、".join(document["missing"])
            reasons.append(
                {
                    "reason": f"{axis.key}_{document['value']}",
                    "text": f"{axis.label}{document['text']}"
                    + (f"，缺：{missing}" if document["value"] == "unconfirmed" else ""),
                }
            )
    if row is None and not reasons:
        reasons.append({"reason": "not_in_table", "text": rules.texts["not_in_table"]})
    driver = row.driver if row is not None else "unclear"
    return {
        "label": rules.texts["label"],
        "counted": False,
        "core": rules.core,
        "bond_trend": bond,
        # The bond core is a price index: its trend said as its price, never a yield.
        "bond_text": rules.bond_texts[bond] if bond is not None else rules.texts["bond_unknown"],
        "axes": axes,
        "driver": driver,
        "text": rules.drivers[driver],
        "typical": row.typical if row is not None else None,
        "suspicion": row.suspicion if row is not None else None,
        "reasons": reasons,
        "notes": [
            rules.texts["term_premium"],
            *([rules.texts["unclear_refinement"]] if driver == "unclear" else []),
        ],
        "boundary": rules.texts["boundary"],
    }


def _axis_document(axis: Axis, readings: Mapping[str, SignalReading]) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    for signal in axis.signals:
        read = readings.get(signal.name) or SignalReading(None, ("not_read",))
        signals.append(
            {
                "indicator": signal.indicator,
                "label": signal.label,
                "reading": signal.reading,
                "value": read.value,
                "means": signal.means.get(read.value) if read.value is not None else None,
                "missing": list(read.missing),
            }
        )
    said: list[str] = [item["means"] for item in signals if item["means"] is not None]
    unknown = any(item["value"] is None for item in signals)
    if axis.combine == "agree":
        named = set(said)
        value = (
            "mixed"
            if len(named) > 1
            else "unconfirmed"
            if unknown
            else named.pop()
            if named
            else axis.otherwise
        )
    else:
        value = next(
            (name for name, count in Counter(said).items() if 2 * count > len(signals)),
            "unconfirmed" if unknown else "mixed",
        )
    assert value is not None
    return {
        "axis": axis.key,
        "label": axis.label,
        "value": value,
        "text": axis.texts[value],
        "signals": signals,
        "missing": [
            f"{item['label']}（{'；'.join(item['missing'])}）"
            for item in signals
            if item["value"] is None
        ],
    }


def _axis(value: object, indicators: Mapping[str, tuple[str, str]]) -> Axis:
    item = _mapping(value)
    return Axis(
        str(item["key"]),
        str(item["label"]),
        str(item["combine"]),
        tuple(
            Signal(
                str(signal["indicator"]),
                indicators[str(signal["indicator"])][0]
                if str(signal["indicator"]) in indicators
                else str(signal["indicator"]),
                str(signal["reading"]),
                _texts(signal["means"]),
            )
            for signal in map(_mapping, _list(item["signals"]))
        ),
        str(item["otherwise"]) if item.get("otherwise") else None,
        _texts(item["texts"]),
    )


def _texts(value: object, required: Sequence[str] = ()) -> dict[str, str]:
    """Words by key, each of ``required`` among them."""
    item = _mapping(value)
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in item.items()) or set(
        required
    ) - set(item):
        raise ValueError("confirmation_bond_attribution_invalid")
    return dict(item)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_bond_attribution_invalid")
    return value


def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("confirmation_bond_attribution_invalid")
    return value
