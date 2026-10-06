"""Confirmation: how far the key indicators bear out the formal stage's narrative (ADR-0037).

The formal stage is the three cores' alone and is decided first. Confirmation reads each
key indicator's members -- level against the indicator's line, momentum on the period
before, slope change over the three newest periods -- lists where they agree with the
main member or split from it, and has the main member's reading answer the current
stage's cells of the model's frozen expectation table: support, counterevidence,
observation only or unconfirmed, with the proposition it bears on. A member opposite to
the main one caps the relation at observation only. A non-canonical combination or a held
stage has no narrative to confirm: every relation is not applicable and the readings are
still given. Each dimension counts its indicators' relations; one the model reads no
indicator of yet says so, with no label in its place.

A reading not known is never a direction: a main member missing a month of its lookback
leaves the indicator unconfirmed with the months named, and an unchanged value is flat,
not an easing.

Not here: grace and signal maturity (ticket 05). A cell whose counterevidence waits on
grace is observation only, its grace not evaluated, until grace is read.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pring_cycle.domain import FormalStage

OUTPUT_STRUCTURE = "confirmation-v0001"
MACRO_RULES_VERSION = "macro-confirmation-v0001"
# The manifest fields that hold confirmation; a manifest with none of them reads the four
# single-dimension labels of the models before it.
MANIFEST_FIELDS = ("macro_rules_version", "projection_output_structure", "confirmation_rules")
DIMENSIONS = ("policy", "credit", "overheat", "price", "inventory")
RELATIONS = ("support", "counterevidence", "observation_only", "unconfirmed", "not_applicable")
_CELL_RELATIONS = frozenset({"support", "counterevidence", "observation_only"})
_STAGES = tuple(stage.value for stage in FormalStage)
_READINGS = {
    "level": frozenset({"above", "below", "at"}),
    "momentum": frozenset({"up", "down", "flat"}),
    "slope": frozenset({"steeper", "slower", "turn", "flat"}),
    "crossed": frozenset({"above", "below", "none"}),
}


@dataclass(frozen=True)
class Condition:
    """Readings that must all hold, of the main member unless ``member`` names another.

    ``outpaces`` names a member this one must have risen more than since the period
    before.
    """

    readings: Mapping[str, str]
    member: Mapping[str, str] | None = None
    outpaces: Mapping[str, str] | None = None


@dataclass(frozen=True)
class Annotation:
    """A note or turn hint a cell gives, when its condition holds (always without one)."""

    text: str
    when: Condition | None = None


@dataclass(frozen=True)
class Cell:
    """One cell of a stage's expectations: the relation when any alternative holds.

    ``grace`` says the relation needs the indicator past its grace, which is not read yet.
    """

    relation: str
    when: tuple[Condition, ...]
    note: Annotation | None = None
    turn_hint: Annotation | None = None
    grace: bool = False


@dataclass(frozen=True)
class KeyIndicator:
    key: str
    name: str
    dimension: str
    metric_id: str
    main: Mapping[str, str]
    auxiliary: tuple[Mapping[str, str], ...]
    level_line: float
    lookback_months: int
    propositions: Mapping[str, str]
    cells: Mapping[str, tuple[Cell, ...]]
    # Notes a stage gives whichever cell answers, when their condition holds.
    notes: Mapping[str, tuple[Annotation, ...]]

    @property
    def members(self) -> tuple[Mapping[str, str], ...]:
        return (self.main, *self.auxiliary)


@dataclass(frozen=True)
class ConfirmationRules:
    """A model's frozen confirmation rules: its key indicators and their expectations."""

    output_structure: str
    macro_rules_version: str
    indicators: tuple[KeyIndicator, ...]

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, object]) -> ConfirmationRules | None:
        """The manifest's rules; None for a manifest without them, read the old way."""
        if not any(field in manifest for field in MANIFEST_FIELDS):
            return None
        if (
            manifest.get("macro_rules_version") != MACRO_RULES_VERSION
            or manifest.get("projection_output_structure") != OUTPUT_STRUCTURE
        ):
            raise ValueError("confirmation_rules_version_unsupported")
        document = manifest.get("confirmation_rules")
        if not isinstance(document, Mapping):
            raise ValueError("confirmation_rules_invalid")
        raw = document.get("key_indicators")
        if not isinstance(raw, list) or not raw:
            raise ValueError("confirmation_rules_invalid")
        indicators = tuple(_indicator(item) for item in raw)
        if len({item.key for item in indicators}) != len(indicators):
            raise ValueError("confirmation_key_indicator_duplicate")
        return cls(OUTPUT_STRUCTURE, MACRO_RULES_VERSION, indicators)


@dataclass(frozen=True)
class MemberReading:
    """One member's readings over its newest consecutive periods, oldest first.

    ``points`` are (period end, value, observation version) of the periods held of the
    lookback; ``missing`` the months (``YYYY-MM``) of it that are not.
    """

    member: Mapping[str, str]
    role: str
    evidence_status: str
    points: tuple[tuple[str, float, str], ...]
    missing: tuple[str, ...]
    level_line: float

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(value for _period, value, _version in self.points)

    @property
    def change(self) -> float | None:
        values = self.values
        return values[-1] - values[-2] if len(values) >= 2 else None

    @property
    def level(self) -> str | None:
        if not self.points:
            return None
        return _side(self.values[-1], self.level_line)

    @property
    def momentum(self) -> str | None:
        values = self.values
        return _direction(values[-1], values[-2]) if len(values) >= 2 else None

    @property
    def slope(self) -> str | None:
        """The change against the one before: steeper, slower, a turn, or flat.

        Alike in sign and wider is steeper, narrower slower; opposite is a turn. With no
        change on either side, or the same one, the slope is flat.
        """
        values = self.values
        if len(values) < 3:
            return None
        earlier = _direction(values[-2], values[-3])
        later = _direction(values[-1], values[-2])
        if "flat" in {earlier, later}:
            return "flat"
        if earlier != later:
            return "turn"
        widened = _direction(abs(values[-1] - values[-2]), abs(values[-2] - values[-3]))
        return {"up": "steeper", "down": "slower", "flat": "flat"}[widened]

    @property
    def crossed(self) -> str | None:
        """Whether the newest period crossed the line from the one before: above, below.

        From on the line counts: 50.0 to 50.4 has just crossed above 50.
        """
        values = self.values
        if len(values) < 2:
            return None
        before, now = _side(values[-2], self.level_line), _side(values[-1], self.level_line)
        if before != "above" and now == "above":
            return "above"
        if before != "below" and now == "below":
            return "below"
        return "none"

    def reading(self, name: str) -> str | None:
        return getattr(self, name)  # type: ignore[no-any-return]


def confirmation_document(
    indicators: Sequence[KeyIndicator],
    readings: Mapping[str, Sequence[MemberReading]],
    *,
    current_stage: FormalStage | None,
    stage_reason: str,
) -> dict[str, object]:
    """The dimension summary of ``indicators`` read as ``readings`` under the formal stage.

    ``readings`` holds each indicator's members by its key, the main one first.
    """
    stage = current_stage.value if current_stage is not None else None
    documents = [_indicator_document(item, readings[item.key], stage=stage) for item in indicators]
    dimensions = []
    for dimension in DIMENSIONS:
        own = [document for document in documents if document["dimension"] == dimension]
        dimensions.append(
            {
                "dimension": dimension,
                "status": "connected" if own else "not_connected",
                "counts": (
                    {
                        relation: sum(1 for item in own if item["relation"] == relation)
                        for relation in RELATIONS
                    }
                    if own
                    else None
                ),
                "key_indicators": own,
            }
        )
    return {
        "macro_rules_version": MACRO_RULES_VERSION,
        "stage": stage,
        "stage_reason": stage_reason,
        "applicable": stage is not None,
        "dimensions": dimensions,
    }


def _indicator_document(
    indicator: KeyIndicator, members: Sequence[MemberReading], *, stage: str | None
) -> dict[str, object]:
    main, auxiliary = members[0], tuple(members[1:])
    agreement = [_agreement(main, member) for member in auxiliary]
    divergent = "opposes" in agreement
    document: dict[str, object] = {
        "key": indicator.key,
        "name": indicator.name,
        "dimension": indicator.dimension,
        "metric_id": indicator.metric_id,
        "level_line": indicator.level_line,
        "consistency": (
            "unknown" if main.momentum is None else "divergent" if divergent else "consistent"
        ),
        "members": [
            _member_document(main, "main"),
            *(
                _member_document(member, state)
                for member, state in zip(auxiliary, agreement, strict=True)
            ),
        ],
        "relation": "not_applicable",
        "proposition": None,
        "matched": None,
        "notes": [],
        "turn_hint": None,
        "grace": None,
        "divergence_capped": False,
        "missing": [],
    }
    if stage is None:
        return document
    if main.evidence_status != "current" or not main.points or main.missing:
        # Every reading of the main member is known, or none is said: a month short of
        # its lookback leaves a momentum or a slope unknown, never read as a direction.
        status = (
            [main.evidence_status] if main.evidence_status != "current" or not main.points else []
        )
        missing = [f"{_member_label(main)}:{item}" for item in (*status, *main.missing)]
        return {**document, "relation": "unconfirmed", "missing": missing}
    by_member = {_member_key(member.member): member for member in members}
    matched: tuple[Cell, Condition] | None = None
    for cell in indicator.cells[stage]:
        holds = [_holds(condition, main, by_member) for condition in cell.when]
        hit = next(
            (condition for condition, held in zip(cell.when, holds, strict=True) if held), None
        )
        if hit is not None:
            matched = (cell, hit)
            break
        if None in holds:
            # An earlier cell may hold: what it reads is not known, so nothing is said.
            missing = [f"{_member_label(main)}:{_unknown_readings(cell, main)}"]
            return {**document, "relation": "unconfirmed", "missing": missing}
    document["proposition"] = indicator.propositions[stage]
    notes = (matched[0].note,) if matched is not None and matched[0].note is not None else ()
    document["notes"] = [
        note.text for note in (*notes, *indicator.notes[stage]) if _annotated(note, main, by_member)
    ]
    if matched is None:
        # Known, and no cell of the stage names it: related, not counted.
        return {**document, "relation": "observation_only"}
    cell, condition = matched
    relation = cell.relation
    if cell.grace:
        relation, document["grace"] = "observation_only", "not_evaluated"
    if divergent and relation in {"support", "counterevidence"}:
        relation, document["divergence_capped"] = "observation_only", True
    document["matched"] = dict(condition.readings)
    if cell.turn_hint is not None and _annotated(cell.turn_hint, main, by_member):
        document["turn_hint"] = cell.turn_hint.text
    return {**document, "relation": relation}


def _holds(
    condition: Condition, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> bool | None:
    """True, False, or None when a reading it needs is not known: False wins over None."""
    member = by_member.get(_member_key(condition.member)) if condition.member is not None else main
    results: list[bool | None] = []
    for name, expected in condition.readings.items():
        actual = member.reading(name) if member is not None else None
        results.append(None if actual is None else actual == expected)
    if condition.outpaces is not None:
        other = by_member.get(_member_key(condition.outpaces))
        changes = (
            member.change if member is not None else None,
            other.change if other is not None else None,
        )
        results.append(
            None if None in changes else changes[0] > changes[1]  # type: ignore[operator]
        )
    if False in results:
        return False
    return None if None in results else True


def _annotated(
    annotation: Annotation, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> bool:
    return annotation.when is None or _holds(annotation.when, main, by_member) is True


def _agreement(main: MemberReading, member: MemberReading) -> str:
    """How a member's momentum stands to the main one's: agrees, opposes, flat, unknown."""
    if member.evidence_status != "current" or member.momentum is None or main.momentum is None:
        return "unknown"
    if member.momentum == main.momentum:
        return "agrees"
    if "flat" in {member.momentum, main.momentum}:
        return "flat"
    return "opposes"


def _member_document(member: MemberReading, consistency: str) -> dict[str, object]:
    latest = member.points[-1] if member.points else None
    return {
        "role": member.role,
        "member": dict(member.member),
        "evidence_status": member.evidence_status,
        "period": latest[0] if latest is not None else None,
        "value": latest[1] if latest is not None else None,
        "periods": [period for period, _value, _version in member.points],
        "values": list(member.values),
        "observation_version_ids": [version for _period, _value, version in member.points],
        "level": member.level,
        "momentum": member.momentum,
        "slope": member.slope,
        "crossed": member.crossed,
        "consistency": consistency,
        "missing": list(member.missing),
    }


def _unknown_readings(cell: Cell, main: MemberReading) -> str:
    names = sorted(
        {name for condition in cell.when for name in condition.readings}
        - {name for name in _READINGS if main.reading(name) is not None}
    )
    return "unknown_" + "_".join(names)


def _member_label(member: MemberReading) -> str:
    return ",".join(f"{key}={value}" for key, value in sorted(member.member.items()))


def _member_key(member: Mapping[str, str] | None) -> str:
    return ",".join(f"{key}={value}" for key, value in sorted((member or {}).items()))


def _side(value: float, line: float) -> str:
    return {"up": "above", "down": "below", "flat": "at"}[_direction(value, line)]


def _direction(value: float, previous: float) -> str:
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    if value - previous > tolerance:
        return "up"
    if previous - value > tolerance:
        return "down"
    return "flat"


def _indicator(value: object) -> KeyIndicator:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_key_indicator_invalid")
    texts = {}
    for field in ("key", "name", "dimension", "metric_id"):
        raw = value.get(field)
        if not isinstance(raw, str) or not raw:
            raise ValueError("confirmation_key_indicator_invalid")
        texts[field] = raw
    if texts["dimension"] not in DIMENSIONS:
        raise ValueError("confirmation_dimension_unknown")
    line, lookback = value.get("level_line"), value.get("lookback_months")
    raw_auxiliary = value.get("auxiliary")
    expectations = value.get("expectations")
    if (
        not isinstance(line, (int, float))
        or isinstance(line, bool)
        or not isinstance(lookback, int)
        or isinstance(lookback, bool)
        or not 1 <= lookback <= 13
        or not isinstance(raw_auxiliary, list)
        or not isinstance(expectations, Mapping)
        or set(expectations) != set(_STAGES)
    ):
        raise ValueError("confirmation_key_indicator_invalid")
    propositions: dict[str, str] = {}
    cells: dict[str, tuple[Cell, ...]] = {}
    notes: dict[str, tuple[Annotation, ...]] = {}
    for stage in _STAGES:
        expectation = expectations[stage]
        if not isinstance(expectation, Mapping):
            raise ValueError("confirmation_expectation_invalid")
        proposition, raw_cells = expectation.get("proposition"), expectation.get("cells")
        raw_notes = expectation.get("notes", [])
        if (
            not isinstance(proposition, str)
            or not proposition
            or not isinstance(raw_cells, list)
            or not isinstance(raw_notes, list)
        ):
            raise ValueError("confirmation_expectation_invalid")
        propositions[stage] = proposition
        cells[stage] = tuple(_cell(item) for item in raw_cells)
        notes[stage] = tuple(
            annotation for item in raw_notes if (annotation := _annotation(item)) is not None
        )
    return KeyIndicator(
        **texts,
        main=_member(value.get("main")),
        auxiliary=tuple(_member(item) for item in raw_auxiliary),
        level_line=float(line),
        lookback_months=lookback,
        propositions=propositions,
        cells=cells,
        notes=notes,
    )


def _cell(value: object) -> Cell:
    if not isinstance(value, Mapping) or value.get("relation") not in _CELL_RELATIONS:
        raise ValueError("confirmation_cell_invalid")
    when = value.get("when")
    if not isinstance(when, list) or not when:
        raise ValueError("confirmation_cell_invalid")
    conditions = tuple(_condition(item) for item in when)
    if any(item.member is not None or item.outpaces is not None for item in conditions):
        # The main member gives the indicator's opinion; the others show agreement only.
        raise ValueError("confirmation_cell_reads_main_member_only")
    grace = value.get("grace", False)
    if not isinstance(grace, bool):
        raise ValueError("confirmation_cell_invalid")
    return Cell(
        relation=str(value["relation"]),
        when=conditions,
        note=_annotation(value.get("note")),
        turn_hint=_annotation(value.get("turn_hint")),
        grace=grace,
    )


def _annotation(value: object) -> Annotation | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or not isinstance(value.get("text"), str):
        raise ValueError("confirmation_annotation_invalid")
    when = value.get("when")
    return Annotation(str(value["text"]), _condition(when) if when is not None else None)


def _condition(value: object) -> Condition:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_condition_invalid")
    readings: dict[str, str] = {}
    for name, expected in value.items():
        if name in {"member", "outpaces"}:
            continue
        if name not in _READINGS or expected not in _READINGS[name]:
            raise ValueError(f"confirmation_condition_unknown:{name}")
        readings[name] = str(expected)
    member, outpaces = value.get("member"), value.get("outpaces")
    if not readings and outpaces is None:
        raise ValueError("confirmation_condition_invalid")
    return Condition(
        readings,
        _member(member) if member is not None else None,
        _member(outpaces) if outpaces is not None else None,
    )


def _member(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("confirmation_member_invalid")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError("confirmation_member_invalid")
    return {str(k): str(v) for k, v in value.items()}


_MANUFACTURING = {"measure": "level", "series": "manufacturing"}
_NEW_ORDERS = {"measure": "level", "series": "new_orders"}
_PRODUCTION = {"measure": "level", "series": "production"}
_PURCHASE_VOLUME = {"measure": "level", "series": "purchase_volume"}


def rules_v0001() -> dict[str, Any]:
    """The first confirmation rules: the PMI alone (expectation-table.md, key-indicators.md).

    Each stage's cells are tried in order and the first that holds answers; a known
    reading no cell names is observation only. A cell's slope reads along the momentum it
    names: steepening is a quickening, slowing a slackening, of that move (user, 2026-10-07).
    """
    return {
        "key_indicators": [
            {
                "key": "pmi",
                "name": "PMI",
                "dimension": "overheat",
                "metric_id": "CN_PMI_ACTIVITY",
                "main": dict(_MANUFACTURING),
                "auxiliary": [dict(_NEW_ORDERS), dict(_PRODUCTION), dict(_PURCHASE_VOLUME)],
                "level_line": 50,
                # Level, momentum on the month before, slope change on the two before.
                "lookback_months": 3,
                "expectations": copy.deepcopy(_PMI_EXPECTATIONS),
            }
        ]
    }


_PMI_EXPECTATIONS: dict[str, Any] = {
    "stage_i": {
        "proposition": "经济走弱，增长仍弱",
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "above", "momentum": "up"}]},
            # Below 50 and falling, a slowing fall included.
            {"relation": "support", "when": [{"level": "below", "momentum": "down"}]},
            {
                "relation": "observation_only",
                "when": [{"level": "below", "momentum": "up"}],
                "turn_hint": {"text": "stage_ii", "when": {"slope": "steeper"}},
            },
        ],
    },
    "stage_ii": {
        "proposition": "增长仍低但不再恶化",
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"level": "below", "momentum": "down", "slope": "steeper"}],
            },
            {
                "relation": "support",
                "when": [{"level": "below", "momentum": "up"}, {"crossed": "above"}],
                "note": {
                    "text": "新订单领先生产",
                    "when": {"member": dict(_NEW_ORDERS), "outpaces": dict(_PRODUCTION)},
                },
            },
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "steeper"}],
                "turn_hint": {"text": "stage_iii"},
            },
        ],
    },
    "stage_iii": {
        "proposition": "经济自底部恢复，需求与生产扩张",
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "below"}], "grace": True},
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "slower"}],
                "note": {"text": "扩张仍在、动能减弱"},
            },
            {"relation": "support", "when": [{"level": "above", "momentum": "up"}]},
        ],
    },
    "stage_iv": {
        "proposition": "经济充分扩张",
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "below"}], "grace": True},
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "slower"}],
                "note": {"text": "扩张后段，斜率放缓"},
            },
            {"relation": "support", "when": [{"level": "above"}]},
        ],
    },
    "stage_v": {
        "proposition": "增长动量见顶回落",
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"momentum": "up", "slope": "steeper"}],
                "grace": True,
            },
            {
                "relation": "support",
                "when": [{"momentum": "down"}],
                "note": {"text": "水平仍高、动量下降", "when": {"level": "above"}},
            },
            {"relation": "observation_only", "when": [{"momentum": "flat"}]},
        ],
    },
    "stage_vi": {
        "proposition": "经济由扩张转向收缩",
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"level": "above", "momentum": "up"}],
                "grace": True,
            },
            {"relation": "support", "when": [{"level": "below", "momentum": "down"}]},
        ],
        # Orders improving first is told whatever the PMI does; against a falling PMI it
        # is a split, and the relation is observation only.
        "notes": [
            {
                "text": "订单先改善：只改动量描述，不宣布复苏",
                "when": {"member": dict(_NEW_ORDERS), "momentum": "up"},
            }
        ],
    },
}
