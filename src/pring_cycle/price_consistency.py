"""Where the three cores stand against each other, and what is shown beside them (ADR-0037).

None of it confirms the stage, whose own prices it reads: it is shown apart from the
dimension summary and never counted (macro semantics ticket 09).

- Observation interfaces: prices of a core's own kind (the bond indices, the CSI indices
  and the market's breadth, valuation and margin financing, NHCI, the basket and crude
  oil) hang under that core. NHII is the commodity core: no evidence of prices.
- Relative momentum: commodities against bonds, stocks against bonds and stocks against
  commodities, each the difference of the two cores' returns over 120 SSE sessions. It
  needs 121 actual closes of both on the same sessions; a close carried forward from the
  session before is no actual one, and with any missing the pair is unconfirmed.
- Breadth: whether the stock core's move is broad or rests on fewer shares, read from the
  share of all A shares above their moving average against a majority. It reads all
  shares alike: never sectors, never weights.
- The basket's sleeves: whether the basket's move over the same sessions is broad, or
  rests on one sleeve or a few.
- Each stage's expectations of these say where the cores stand and any turn they hint.
- The supply-demand note (stages III to V): whether demand bears out the commodity rise,
  and where it does not a supply suspicion. The data cannot tell what drives prices, and
  the note never says.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

# Each pair's difference of the two cores' returns, in percentage points.
PRICE_FORMULAS = frozenset({"return-difference-v0001"})
ASSETS = ("bond", "stock", "commodity")
_DIRECTIONS = frozenset({"up", "down", "flat"})
# A core's prices stand when its gate passed; a close carried forward stands in for the
# target day in the stage's calculation alone.
_PRICED = frozenset({"validated", "carried_forward_one_session"})
# The words each reading is said in, all of which the rules must give.
_BREADTH_READINGS = (
    "broad_rise",
    "narrow_rise",
    "broad_fall",
    "narrow_fall",
    "even",
    "index_flat",
)
_BASKET_READINGS = (
    *(
        f"{breadth}_{move}"
        for breadth in ("broad", "single_sleeve", "few_sleeves")
        for move in ("rise", "fall")
    ),
    "flat",
    "unaligned",
)
_NOTE_TEXTS = (
    "label",
    "headline",
    "boundary",
    "demand_supported",
    "demand_insufficient",
    "mixed",
    "unconfirmed",
    "supply_suspicion",
    "warrants_with_prices",
)


@dataclass(frozen=True)
class CorePrices:
    """A core's actual closes (ISO day, value), oldest first, as its gate read them.

    None when the gate failed, ``reason`` saying why; a close carried forward to the target
    day is not among them.
    """

    asset: str
    metric_id: str
    reason: str
    closes: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class InterfaceMember:
    metric_id: str
    label: str
    # A price read as such: a bond index's rise is a stronger bond price, never a yield.
    reads_as: str | None = None


@dataclass(frozen=True)
class Interface:
    core: str
    core_metric_id: str
    label: str
    members: tuple[InterfaceMember, ...]


@dataclass(frozen=True)
class Pair:
    """``of``'s return less ``against``'s."""

    key: str
    label: str
    of: str
    against: str


@dataclass(frozen=True)
class TurnHint:
    """Given when each subject (a pair, or a core) moves as ``when`` says."""

    text: str
    toward: tuple[str, ...]
    when: Mapping[str, str]


@dataclass(frozen=True)
class StagePosition:
    """Where a stage expects the cores to stand: each subject's direction, its turn hints,
    and a note on the breadth's reading."""

    text: str
    expect: Mapping[str, str]
    turn_hints: tuple[TurnHint, ...] = ()
    breadth_notes: Mapping[str, str] | None = None


@dataclass(frozen=True)
class Breadth:
    """The share of all shares above their moving average, against ``line``."""

    metric_id: str
    dimensions: Mapping[str, str]
    line: float
    label: str
    texts: Mapping[str, str]


@dataclass(frozen=True)
class Basket:
    """Each sleeve's daily contribution to the basket's return, summed over the sessions."""

    metric_id: str
    dimensions: Mapping[str, str]
    sleeves: tuple[str, ...]
    label: str
    texts: Mapping[str, str]


@dataclass(frozen=True)
class DemandReading:
    """A member of a key indicator read as ``readings`` say: ``pmi:new_orders`` rising on."""

    indicator: str
    member: str
    readings: Mapping[str, str]

    @property
    def name(self) -> str:
        return f"{self.indicator}:{self.member}"


@dataclass(frozen=True)
class SupplyDemand:
    """The note's stages, and what bears demand out (all ``improving``) or leaves it short
    (all ``weakening``); any other known readings are mixed."""

    stages: frozenset[str]
    improving: tuple[DemandReading, ...]
    weakening: tuple[DemandReading, ...]
    texts: Mapping[str, str]

    @property
    def readings(self) -> tuple[DemandReading, ...]:
        named: dict[str, DemandReading] = {}
        for item in (*self.improving, *self.weakening):
            named.setdefault(item.name, item)
        return tuple(named.values())


@dataclass(frozen=True)
class PriceRules:
    """A model's frozen rules for what is shown beside confirmation, never counted."""

    interfaces: tuple[Interface, ...]
    formula: str
    sessions: int
    cores: Mapping[str, str]
    pairs: tuple[Pair, ...]
    stages: Mapping[str, StagePosition]
    breadth: Breadth
    basket: Basket
    supply_demand: SupplyDemand

    @property
    def interface_metrics(self) -> frozenset[str]:
        return frozenset(member.metric_id for item in self.interfaces for member in item.members)

    @property
    def points(self) -> int:
        """The actual closes a return over ``sessions`` sessions needs: one more."""
        return self.sessions + 1

    @classmethod
    def parse(
        cls,
        document: Mapping[str, object],
        *,
        stages: Collection[str],
        members: Mapping[str, Collection[str]],
    ) -> PriceRules:
        """The rules of a manifest's confirmation document; ``members`` names each key
        indicator's members, which the supply-demand note may read."""
        try:
            consistency = _mapping(document["price_consistency"])
            momentum = _mapping(consistency["relative_momentum"])
            cores = {str(k): str(v) for k, v in _mapping(momentum["cores"]).items()}
            interfaces = tuple(
                Interface(
                    str(item["core"]),
                    str(item["core_metric_id"]),
                    str(item["label"]),
                    tuple(
                        InterfaceMember(
                            str(member["metric_id"]),
                            str(member["label"]),
                            str(member["reads_as"]) if member.get("reads_as") else None,
                        )
                        for member in _list(item["members"])
                    ),
                )
                for item in _list(document["observation_interfaces"])
            )
            pairs = tuple(
                Pair(str(item["key"]), str(item["label"]), str(item["of"]), str(item["against"]))
                for item in _list(momentum["pairs"])
            )
            positions = {
                str(stage): StagePosition(
                    str(item["text"]),
                    _directions(item["expect"]),
                    tuple(
                        TurnHint(
                            str(hint["text"]),
                            tuple(str(toward) for toward in hint["toward"]),
                            _directions(hint["when"]),
                        )
                        for hint in _list(item.get("turn_hints", []))
                    ),
                    _texts(item["breadth_notes"]) if "breadth_notes" in item else None,
                )
                for stage, item in _mapping(consistency["stages"]).items()
                if isinstance(item, Mapping)
            }
            breadth_document = _mapping(consistency["stock_breadth"])
            breadth = Breadth(
                str(breadth_document["metric_id"]),
                _texts(breadth_document["dimensions"]),
                _finite(breadth_document["line"]),
                str(breadth_document["label"]),
                _texts(breadth_document["texts"], _BREADTH_READINGS),
            )
            basket_document = _mapping(consistency["basket_breadth"])
            basket = Basket(
                str(basket_document["metric_id"]),
                _texts(basket_document["dimensions"]),
                tuple(str(item) for item in _list(basket_document["sleeves"])),
                str(basket_document["label"]),
                _texts(basket_document["texts"], _BASKET_READINGS),
            )
            note = _mapping(document["supply_demand"])
            supply_demand = SupplyDemand(
                frozenset(str(item) for item in _list(note["stages"])),
                tuple(_demand(item) for item in _list(note["improving"])),
                tuple(_demand(item) for item in _list(note["weakening"])),
                _texts(note["texts"], _NOTE_TEXTS),
            )
            formula = str(momentum["formula"])
            sessions = momentum["sessions"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("confirmation_price_rules_invalid") from error
        assets = {item.core for item in interfaces}
        subjects = {*ASSETS, *(pair.key for pair in pairs)}
        if (
            formula not in PRICE_FORMULAS
            or type(sessions) is not int
            or sessions < 2
            or set(cores) != set(ASSETS)
            or assets != set(ASSETS)
            or any(item.core_metric_id != cores[item.core] for item in interfaces)
            or not pairs
            or len({pair.key for pair in pairs}) != len(pairs)
            or any(
                {pair.of, pair.against} - set(ASSETS) or pair.of == pair.against for pair in pairs
            )
            or set(positions) != set(stages)
            or any(
                set(item.expect) - subjects
                or any(
                    set(hint.when) - subjects or set(hint.toward) - set(stages)
                    for hint in item.turn_hints
                )
                for item in positions.values()
            )
            or not basket.sleeves
            or len(set(basket.sleeves)) != len(basket.sleeves)
            # Breadth and the basket are read of observation interfaces: never counted.
            or {breadth.metric_id, basket.metric_id}
            - {member.metric_id for item in interfaces for member in item.members}
            or not supply_demand.improving
            or not supply_demand.weakening
            or supply_demand.stages - set(stages)
            or any(
                item.member not in members.get(item.indicator, ())
                for item in supply_demand.readings
            )
        ):
            raise ValueError("confirmation_price_rules_invalid")
        return cls(
            interfaces,
            formula,
            sessions,
            cores,
            pairs,
            positions,
            breadth,
            basket,
            supply_demand,
        )


def price_consistency_document(
    rules: PriceRules,
    *,
    stage: str | None,
    cores: Mapping[str, CorePrices] | None,
    span: Sequence[str] | None,
    breadth: Mapping[str, float],
    sleeves: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    """The cores' relative momentum over ``span`` (the 121 SSE sessions to the day, None
    when the calendar does not state them), the breadth on its last session (``breadth``,
    the share by day), the sleeves' contributions on the sessions after its first
    (``sleeves``, by sleeve and day), and where ``stage`` expects them to stand."""
    read = {asset: _core(asset, rules, cores, span) for asset in ASSETS}
    pairs = [_pair(pair, read) for pair in rules.pairs]
    directions: dict[str, str | None] = {
        **{asset: item["direction"] for asset, item in read.items()},
        **{item["key"]: item["direction"] for item in pairs},
    }
    stock_breadth = _breadth(rules.breadth, read["stock"], span, breadth)
    return {
        "label": "价格内部一致性",
        "counted": False,
        "formula": rules.formula,
        "sessions": rules.sessions,
        "first_session": span[0] if span else None,
        "last_session": span[-1] if span else None,
        "cores": list(read.values()),
        "relative_momentum": pairs,
        "stock_breadth": stock_breadth,
        "basket_breadth": _basket(rules.basket, span, sleeves),
        "position": _position(rules, stage, directions, stock_breadth["reading"]),
    }


def supply_demand_document(
    rules: SupplyDemand,
    *,
    stage: str | None,
    readings: Mapping[str, Mapping[str, str | None] | None],
    warrants: Mapping[str, object] | None,
) -> dict[str, object] | None:
    """The note in the stages it is given in, None in any other: ``readings`` holds each
    member the note reads by its name (``pmi:new_orders``), None when not known.

    Demand is borne out when every improving reading holds, left short when every
    weakening one does, mixed otherwise; with any not known, unconfirmed. Registered
    warrants rising with prices are a note of their own. What drives prices is never said.
    """
    if stage not in rules.stages:
        return None
    missing = [item.name for item in rules.readings if readings.get(item.name) is None]

    def holds(items: Sequence[DemandReading]) -> bool:
        return all(
            (readings[item.name] or {}).get(name) == value
            for item in items
            for name, value in item.readings.items()
        )

    outcome = (
        "unconfirmed"
        if missing
        else "demand_supported"
        if holds(rules.improving)
        else "demand_insufficient"
        if holds(rules.weakening)
        else "mixed"
    )
    rate = warrants.get("median_change_rate") if warrants is not None else None
    return {
        "label": rules.texts["label"],
        "counted": False,
        "stage": stage,
        "headline": rules.texts["headline"],
        "outcome": outcome,
        "text": rules.texts[outcome],
        # The data tests demand; it never tells what drives prices.
        "driver": "unconfirmed",
        "boundary": rules.texts["boundary"],
        "supply_suspicion": (
            rules.texts["supply_suspicion"] if outcome == "demand_insufficient" else None
        ),
        "registered_warrants": (
            rules.texts["warrants_with_prices"]
            if isinstance(rate, (int, float)) and rate > 0
            else None
        ),
        "readings": [
            {
                "name": item.name,
                **{name: (readings.get(item.name) or {}).get(name) for name in ("momentum", "run")},
            }
            for item in rules.readings
        ],
        "missing": missing,
    }


def _core(
    asset: str,
    rules: PriceRules,
    cores: Mapping[str, CorePrices] | None,
    span: Sequence[str] | None,
) -> dict[str, Any]:
    """A core's return over ``span``, from its first actual close to its last."""
    given = (cores or {}).get(asset)
    document: dict[str, Any] = {
        "asset": asset,
        "core_metric_id": rules.cores[asset],
        "held": 0,
        "return_pct": None,
        "direction": None,
        "missing": [],
    }
    if span is None:
        return {**document, "missing": ["trading_calendar_incomplete"]}
    if given is None:
        return {**document, "missing": [f"{asset}:no_prices"]}
    if given.reason not in _PRICED:
        return {**document, "missing": [f"{asset}:{given.reason}"]}
    held = dict(given.closes)
    absent = [day for day in span if day not in held]
    missing = [
        *([f"{asset}:{given.reason}"] if given.reason != "validated" else []),
        *_spans(asset, absent, span),
    ]
    document.update(held=len(span) - len(absent), missing=missing)
    if absent:
        return document
    change = (held[span[-1]] / held[span[0]] - 1) * 100
    return {**document, "return_pct": change, "direction": _direction(change, 0.0)}


def _pair(pair: Pair, read: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    of, against = read[pair.of], read[pair.against]
    # The gaps of both, by core, without saying the calendar's twice.
    missing = list(
        dict.fromkeys(
            gap
            for asset in ASSETS
            if asset in {pair.of, pair.against}
            for gap in read[asset]["missing"]
            if gap.startswith(f"{asset}:") or gap == "trading_calendar_incomplete"
        )
    )
    known = of["return_pct"] is not None and against["return_pct"] is not None
    value = of["return_pct"] - against["return_pct"] if known else None
    return {
        "key": pair.key,
        "label": pair.label,
        "of": pair.of,
        "against": pair.against,
        "status": "read" if known else "unconfirmed",
        "value_pp": value,
        "direction": _direction(value, 0.0) if value is not None else None,
        "missing": [] if known else missing,
    }


def _breadth(
    rule: Breadth,
    stock: Mapping[str, Any],
    span: Sequence[str] | None,
    shares: Mapping[str, float],
) -> dict[str, Any]:
    """The stock core's move against the share of all shares above their average: broad
    with a majority along it, on fewer shares without."""
    day = span[-1] if span else None
    share = shares.get(day) if day is not None else None
    missing = [
        *(stock["missing"] if stock["direction"] is None else []),
        *([f"{rule.metric_id}:{day}"] if day is not None and share is None else []),
    ]
    reading = None
    if not missing and share is not None:
        side = _direction(share, rule.line)
        reading = (
            "index_flat"
            if stock["direction"] == "flat"
            else "even"
            if side == "flat"
            else ("broad" if (side == "up") is (stock["direction"] == "up") else "narrow")
            + ("_rise" if stock["direction"] == "up" else "_fall")
        )
    return {
        "label": rule.label,
        "metric_id_read": rule.metric_id,
        "session": day,
        "status": "read" if reading is not None else "unconfirmed",
        "index_direction": stock["direction"],
        "share": share,
        "line": rule.line,
        "reading": reading,
        "text": rule.texts[reading] if reading is not None else None,
        "missing": missing,
    }


def _basket(
    rule: Basket, span: Sequence[str] | None, contributions: Mapping[str, Mapping[str, float]]
) -> dict[str, object]:
    """Each sleeve's contributions summed over the sessions after the span's first, and how
    many move as the basket does: most, one, or a few."""
    days = tuple(span[1:]) if span else ()
    missing = (
        [
            gap
            for sleeve in rule.sleeves
            for gap in _spans(
                sleeve, [d for d in days if d not in contributions.get(sleeve, {})], days
            )
        ]
        if span
        else ["trading_calendar_incomplete"]
    )
    sums = (
        {sleeve: sum(contributions[sleeve][day] for day in days) for sleeve in rule.sleeves}
        if not missing
        else {}
    )
    # The basket's own return compounds its days, as its level does: the sleeves' sums
    # say which way each moved, not how the basket did.
    level = 1.0
    for day in days if sums else ():
        level *= 1 + sum(contributions[sleeve][day] for sleeve in rule.sleeves) / 100
    direction = _direction(level, 1.0) if sums else None
    along = sum(1 for value in sums.values() if _direction(value, 0.0) == direction)
    reading = (
        None
        if direction is None
        else "flat"
        if direction == "flat"
        # No sleeve's sum moved as the compounded basket did: its days offset each other.
        else "unaligned"
        if along == 0
        else (
            "broad"
            if along * 2 > len(rule.sleeves)
            else "single_sleeve"
            if along == 1
            else "few_sleeves"
        )
        + ("_rise" if direction == "up" else "_fall")
    )
    return {
        "label": rule.label,
        "status": "read" if reading is not None else "unconfirmed",
        "direction": direction,
        "sleeves": [
            {
                "sleeve": sleeve,
                "sum_pp": sums.get(sleeve),
                "direction": _direction(sums[sleeve], 0.0) if sleeve in sums else None,
            }
            for sleeve in rule.sleeves
        ],
        "return_pct": (level - 1) * 100 if sums else None,
        "along": along if sums else None,
        "of": len(rule.sleeves),
        "reading": reading,
        "text": rule.texts[reading] if reading is not None else None,
        "missing": missing,
    }


def _position(
    rules: PriceRules,
    stage: str | None,
    directions: Mapping[str, str | None],
    breadth: str | None,
) -> dict[str, object]:
    """What the stage expects of each subject, whether it holds, the turns hinted and the
    note on the breadth's reading; nothing placed for no stage."""
    expected = rules.stages.get(stage or "")
    if expected is None:
        return {
            "applicable": False,
            "stage": None,
            "text": None,
            "expected": [],
            "agrees": None,
            "turn_hints": [],
            "notes": [],
        }
    subjects = [
        {
            "subject": subject,
            "expected": direction,
            "observed": directions[subject],
            "agrees": (
                directions[subject] == direction if directions[subject] is not None else None
            ),
        }
        for subject, direction in expected.expect.items()
    ]
    agreements = [item["agrees"] for item in subjects]
    notes = expected.breadth_notes or {}
    return {
        "applicable": True,
        "stage": stage,
        "text": expected.text,
        "expected": subjects,
        "agrees": None if None in agreements else all(agreements),
        "turn_hints": [
            {"text": hint.text, "toward": list(hint.toward)}
            for hint in expected.turn_hints
            if all(directions[subject] == value for subject, value in hint.when.items())
        ],
        "notes": [notes[breadth]] if breadth is not None and breadth in notes else [],
    }


def _spans(name: str, absent: Sequence[str], days: Sequence[str]) -> list[str]:
    """The days absent of ``days``, each run of neighbouring ones said as its first..last."""
    place = {day: index for index, day in enumerate(days)}
    runs: list[list[str]] = []
    for day in absent:
        if runs and place[day] == place[runs[-1][-1]] + 1:
            runs[-1].append(day)
        else:
            runs.append([day])
    return [f"{name}:{run[0]}" if len(run) == 1 else f"{name}:{run[0]}..{run[-1]}" for run in runs]


def _direction(value: float, previous: float) -> str:
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    if value - previous > tolerance:
        return "up"
    if previous - value > tolerance:
        return "down"
    return "flat"


def _demand(value: object) -> DemandReading:
    item = _mapping(value)
    readings = {str(k): str(v) for k, v in item.items() if k not in {"indicator", "member"}}
    if not readings:
        raise ValueError("confirmation_price_rules_invalid")
    return DemandReading(str(item["indicator"]), str(item["member"]), readings)


def _directions(value: object) -> dict[str, str]:
    directions = _texts(value)
    if not directions or set(directions.values()) - _DIRECTIONS:
        raise ValueError("confirmation_price_rules_invalid")
    return directions


def _texts(value: object, required: Collection[str] = ()) -> dict[str, str]:
    """Words by key, each of ``required`` among them."""
    item = _mapping(value)
    if not all(isinstance(k, str) and isinstance(v, str) and v for k, v in item.items()) or set(
        required
    ) - set(item):
        raise ValueError("confirmation_price_rules_invalid")
    return dict(item)


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("confirmation_price_rules_invalid")
    return float(value)


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_price_rules_invalid")
    return value


def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("confirmation_price_rules_invalid")
    return value
