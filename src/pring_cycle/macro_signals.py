"""The signal list under the macro judgement (ADR-0043, macro stage ticket 04).

Three kinds of turning signal are listed together, each with the transition it supports,
its group against the main conclusion (forward, back or hold on Pring's ring) and its
maturity (GLOSSARY: 信号成熟度):

- a divergent key indicator, loans among them: which indicator, which way its minority
  points, and the stage the day is judged at when that indicator alone votes the
  minority's way (decision 47);
- the price signals of the price signal table (signal-table.md, frozen in the model):
  relative momentum, the stock and basket breadth's divergences, and each asset's peers
  turning against its core; of the same source as the cores, they never vote;
- the cores' own turn watch: a 30-day candidate or an asset candidate against the core's
  state, mapped as the peers are.

A table signal is listed once forming (decision 37): five sessions running, or two cells
pointing to one transition that day; confirmed when its target is the day's price stage
(decision 43). A sprout is kept apart, so that the next session counts on from it. The
divergences are all listed, forming once divergent two periods running.

Nothing here judges the stage: the signals read what the day summary published, and the
judgement they would make is the macro judgement's own (``rejudge``).
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import candidate_direction
from pring_cycle.macro_judgement import MacroJudgementRules, ring_steps
from pring_cycle.price_consistency import ASSETS, CorePrices, PriceRules, relative_momentum

RULES_VERSION = "macro-signals-v0001"
MANIFEST_FIELD = "macro_signal_rules"
STAGES = tuple(stage.value for stage in FormalStage)
STATES = ("bull", "bear")
_LEVELS = ("up", "down")


def _cell(cell: str, origin: str, target: str, **reading: object) -> dict[str, object]:
    return {"cell": cell, **reading, "from": origin, "to": target}


def table_v0001() -> dict[str, Any]:
    """The price signal table as the user settled it on 2026-10-19 (signal-table.md,
    decisions 37-43), frozen into model-v0016."""

    def pair(cell: str, key: str, level: str, turn: str, origin: str, target: str) -> Any:
        return _cell(cell, origin, target, pair=key, level=level, turn=turn)

    return {
        "rules_version": RULES_VERSION,
        "listed_from": "forming",
        "forming_sessions": 5,
        "divergence_forming_periods": 2,
        "turn_sessions": 20,
        "candidate_sessions": 30,
        "relative_momentum": [
            pair("R1", "commodity_vs_bond", "down", "up", "stage_ii", "stage_iii"),
            pair("R2", "commodity_vs_bond", "up", "up", "stage_iii", "stage_iv"),
            pair("R3", "commodity_vs_bond", "up", "down", "stage_v", "stage_vi"),
            pair("R4", "commodity_vs_bond", "down", "down", "stage_vi", "stage_i"),
            pair("R5", "stock_vs_bond", "down", "up", "stage_i", "stage_ii"),
            pair("R9", "stock_vs_commodity", "up", "up", "stage_i", "stage_ii"),
            pair("R10", "stock_vs_commodity", "up", "down", "stage_ii", "stage_iii"),
            pair("R11", "stock_vs_commodity", "down", "down", "stage_iv", "stage_v"),
        ],
        "stock_breadth": [
            _cell("B2", "stage_iv", "stage_v", readings=["narrow_rise"]),
            _cell("B4", "stage_i", "stage_ii", readings=["narrow_fall"]),
        ],
        "basket_breadth": [
            _cell("K2", "stage_v", "stage_vi", readings=["single_sleeve_rise", "few_sleeves_rise"]),
            _cell(
                "K4", "stage_ii", "stage_iii", readings=["single_sleeve_fall", "few_sleeves_fall"]
            ),
        ],
        "peers": {
            "bond": ["CN_BOND_10Y_930916", "CN_BOND_FULL_PRICE_CNY030"],
            "stock": ["CN_EQ_CSI300", "CN_EQ_CSI500", "CN_EQ_CSI1000"],
            "commodity": [
                "CN_COMMODITY_BROAD_NHCI",
                "CN_COMMODITY_EX_HOG_BASKET",
                "EIA_WTI_RWTC",
                "EIA_BRENT_RBRTE",
            ],
        },
        "flips": {
            "peers": {
                "bond": {"bear": "P1", "bull": "P2"},
                "stock": {"bear": "P3", "bull": "P4"},
                "commodity": {"bear": "P5", "bull": "P6"},
            },
            "cores": {
                "bond": {"bear": "C1", "bull": "C2"},
                "stock": {"bear": "C3", "bull": "C4"},
                "commodity": {"bear": "C5", "bull": "C6"},
            },
        },
    }


@dataclass(frozen=True)
class MomentumCell:
    cell: str
    pair: str
    level: str
    turn: str
    origin: str
    target: str


@dataclass(frozen=True)
class ReadingCell:
    cell: str
    readings: tuple[str, ...]
    origin: str
    target: str


@dataclass(frozen=True)
class SignalRules:
    """A model's frozen price signal table and how its signals mature."""

    forming_sessions: int
    divergence_forming_periods: int
    turn_sessions: int
    candidate_sessions: int
    momentum: tuple[MomentumCell, ...]
    breadth: tuple[ReadingCell, ...]
    basket: tuple[ReadingCell, ...]
    peers: Mapping[str, tuple[str, ...]]
    # (asset, the state it turns to) -> cell, of its peers and of its core.
    peer_cells: Mapping[tuple[str, str], str]
    core_cells: Mapping[tuple[str, str], str]

    @classmethod
    def from_manifest(
        cls, manifest: Mapping[str, object], prices: PriceRules | None
    ) -> SignalRules | None:
        """The manifest's table, or None for a model without one. Every cell reads what
        the model's price consistency (``prices``) reads: its pairs, its breadth and basket
        readings, and each core's observation interfaces."""
        raw = manifest.get(MANIFEST_FIELD)
        if raw is None:
            return None
        try:
            if prices is None:
                raise ValueError("macro_signal_rules_invalid")
            return cls._parse(raw, prices)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ValueError("macro_signal_rules_invalid") from error

    @classmethod
    def _parse(cls, raw: Any, prices: PriceRules) -> SignalRules:
        counts = [
            raw[key]
            for key in (
                "forming_sessions",
                "divergence_forming_periods",
                "turn_sessions",
                "candidate_sessions",
            )
        ]
        if (
            raw["rules_version"] != RULES_VERSION
            or raw["listed_from"] != "forming"
            or any(type(count) is not int or count < 1 for count in counts)
        ):
            raise ValueError("macro_signal_rules_invalid")

        def stages(item: Mapping[str, Any]) -> tuple[str, str]:
            origin, target = str(item["from"]), str(item["to"])
            if origin not in STAGES or target not in STAGES or origin == target:
                raise ValueError("macro_signal_rules_invalid")
            return origin, target

        pairs = {pair.key for pair in prices.pairs}
        momentum = tuple(
            MomentumCell(
                str(item["cell"]),
                str(item["pair"]),
                str(item["level"]),
                str(item["turn"]),
                *stages(item),
            )
            for item in raw["relative_momentum"]
        )
        if any(
            cell.pair not in pairs or cell.level not in _LEVELS or cell.turn not in _LEVELS
            for cell in momentum
        ):
            raise ValueError("macro_signal_rules_invalid")

        def readings(items: Sequence[Any], texts: Mapping[str, str]) -> tuple[ReadingCell, ...]:
            cells = tuple(
                ReadingCell(
                    str(item["cell"]), tuple(str(r) for r in item["readings"]), *stages(item)
                )
                for item in items
            )
            if any(not cell.readings or set(cell.readings) - set(texts) for cell in cells):
                raise ValueError("macro_signal_rules_invalid")
            return cells

        breadth = readings(raw["stock_breadth"], prices.breadth.texts)
        basket = readings(raw["basket_breadth"], prices.basket.texts)
        members = {
            item.core: {member.metric_id for member in item.members} for item in prices.interfaces
        }
        peers = {asset: tuple(str(metric) for metric in raw["peers"][asset]) for asset in ASSETS}
        if set(raw["peers"]) != set(ASSETS) or any(
            not named or set(named) - members[asset] for asset, named in peers.items()
        ):
            raise ValueError("macro_signal_rules_invalid")

        def flips(value: Mapping[str, Any]) -> dict[tuple[str, str], str]:
            if set(value) != set(ASSETS) or any(
                set(value[asset]) != set(STATES) for asset in ASSETS
            ):
                raise ValueError("macro_signal_rules_invalid")
            return {
                (asset, state): str(value[asset][state]) for asset in ASSETS for state in STATES
            }

        peer_cells, core_cells = flips(raw["flips"]["peers"]), flips(raw["flips"]["cores"])
        names = [
            *(cell.cell for cell in momentum),
            *(cell.cell for cell in (*breadth, *basket)),
            *peer_cells.values(),
            *core_cells.values(),
        ]
        if len(set(names)) != len(names):
            raise ValueError("macro_signal_rules_invalid")
        return cls(
            forming_sessions=counts[0],
            divergence_forming_periods=counts[1],
            turn_sessions=counts[2],
            candidate_sessions=counts[3],
            momentum=momentum,
            breadth=breadth,
            basket=basket,
            peers=peers,
            peer_cells=peer_cells,
            core_cells=core_cells,
        )


# How a judgement is made again with one indicator voting otherwise: the macro judgement's
# own rule, given the rules (another voter added) and the dimension summary to read.
Rejudge = Callable[[MacroJudgementRules, Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class SignalDay:
    """What a day's signals read: its published documents and the cores as their gates read
    them, and the previous session's published judgement, which the runs count on from."""

    confirmation: Mapping[str, Any]
    macro: Mapping[str, Any]
    # Each core's state, 30-day candidate, asset candidate and its days.
    cores: Mapping[str, Mapping[str, Any]]
    core_prices: Mapping[str, CorePrices]
    # The SSE sessions to the day, enough for the momentum and its turn; None when the
    # calendar does not state them.
    sessions: Sequence[str] | None
    price_stage: str | None
    previous: Mapping[str, Any] | None = None


def signal_list(
    rules: SignalRules,
    prices: PriceRules,
    judgement_rules: MacroJudgementRules,
    day: SignalDay,
    *,
    conclusion: str | None,
    rejudge: Rejudge,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The day's listed signals and its sprouts, grouped against ``conclusion``, the main
    conclusion's stage."""
    before = _previous(day.previous)
    table = [
        *_momentum(rules, prices, day),
        *_breadth(rules, day),
        *_basket(rules, day),
        *_flips(rules, day),
    ]
    moves = Counter(_move(item) for item in table)
    for item in table:
        held = before.get(_run(item))
        item["sessions"] = int(held.get("sessions", 0)) + 1 if held is not None else 1
        target = item["transition"]["to"]
        item["maturity"] = (
            "confirmed"
            if target is not None and target == day.price_stage
            else "forming"
            if item["sessions"] >= rules.forming_sessions or moves[_move(item)] >= 2
            else "sprout"
        )
    divergences = _divergences(rules, judgement_rules, day, before, conclusion, rejudge)
    listed = [item for item in table if item["maturity"] != "sprout"] + divergences
    sprouts = [item for item in table if item["maturity"] == "sprout"]
    for item in (*listed, *sprouts):
        item.update(_grouped(item, conclusion))
    return listed, sprouts


def _grouped(item: Mapping[str, Any], conclusion: str | None) -> dict[str, Any]:
    """Forward, back or hold: the target's steps on the ring from the main conclusion; an
    asset turning to no typical combination is unmapped (decision 41), any other signal
    without a target open."""
    target = item["transition"]["to"]
    steps = ring_steps(conclusion, target) if target is not None else None
    if steps is None:
        group = "unmapped" if target is None and item.get("asset_turn") else "open"
    else:
        group = "forward" if steps > 0 else "back" if steps < 0 else "hold"
    return {"group": group, "steps": steps}


def _run(item: Mapping[str, Any]) -> str:
    """What a run of sessions is of: a cell and the move it points to."""
    return f"{item['id']}>{_move(item)}"


def _move(item: Mapping[str, Any]) -> str:
    turn = _object(item.get("asset_turn"))
    target = item["transition"]["to"]
    return str(target) if target is not None else f"{turn.get('asset')}:{turn.get('to')}"


def _previous(block: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    """The previous session's signals and sprouts, by their runs; a divergence by its id."""
    if block is None:
        return {}
    held: dict[str, Mapping[str, Any]] = {}
    for item in (*_objects(block.get("signals")), *_objects(block.get("sprouts"))):
        if item.get("kind") == "divergence":
            held[str(item.get("id"))] = item
        elif isinstance(item.get("transition"), Mapping):
            held[_run(item)] = item
    return held


# The price signal table.


def _momentum(rules: SignalRules, prices: PriceRules, day: SignalDay) -> list[dict[str, Any]]:
    """Section one: each pair's level, the sign of its 120-session return difference as the
    price consistency published it, and its turn, the sign of that difference's change over
    ``turn_sessions`` (decision 37); a pair unread, flat or in a cell taken out is none."""
    pairs = {
        str(item.get("key")): item
        for item in _objects(_object(day.macro.get("price_consistency")).get("relative_momentum"))
    }
    sessions = tuple(day.sessions or ())
    earlier_span = (
        sessions[-prices.points - rules.turn_sessions : -rules.turn_sessions]
        if len(sessions) >= prices.points + rules.turn_sessions
        else None
    )
    earlier = {
        str(item["key"]): item.get("value_pp")
        for item in relative_momentum(prices, day.core_prices, earlier_span)
    }
    out = []
    for cell in rules.momentum:
        pair = pairs.get(cell.pair, {})
        value, before = pair.get("value_pp"), earlier.get(cell.pair)
        if not isinstance(value, (int, float)) or not isinstance(before, (int, float)):
            continue
        level, turn = pair.get("direction"), _sign(value - before)
        if (level, turn) != (cell.level, cell.turn):
            continue
        out.append(
            {
                "id": cell.cell,
                "kind": "price",
                "source": "relative_momentum",
                "same_source": True,
                "momentum": {
                    "pair": cell.pair,
                    "label": pair.get("label"),
                    "of": pair.get("of"),
                    "against": pair.get("against"),
                    "value_pp": value,
                    "change_pp": value - before,
                    "level": level,
                    "turn": turn,
                    "turn_sessions": rules.turn_sessions,
                },
                "transition": {"from": cell.origin, "to": cell.target},
            }
        )
    return out


def _sign(value: float) -> str:
    """Up, down or flat: a change of the difference against none."""
    return "up" if value > 1e-12 else "down" if value < -1e-12 else "flat"


def _breadth(rules: SignalRules, day: SignalDay) -> list[dict[str, Any]]:
    """Section two: the stock breadth's divergences alone (decision 39)."""
    return _readings(rules.breadth, "stock_breadth", day)


def _basket(rules: SignalRules, day: SignalDay) -> list[dict[str, Any]]:
    """Section three: the basket's sleeves' divergences alone, over the price consistency's
    120 sessions (decision 40)."""
    return _readings(rules.basket, "basket_breadth", day)


def _readings(cells: Sequence[ReadingCell], key: str, day: SignalDay) -> list[dict[str, Any]]:
    item = _object(_object(day.macro.get("price_consistency")).get(key))
    reading = item.get("reading")
    return [
        {
            "id": cell.cell,
            "kind": "price",
            "source": key,
            "same_source": True,
            "breadth": {
                "label": item.get("label"),
                "reading": reading,
                "text": item.get("text"),
                **{name: item.get(name) for name in ("share", "along", "of") if name in item},
            },
            "transition": {"from": cell.origin, "to": cell.target},
        }
        for cell in cells
        if reading in cell.readings
    ]


def _flips(rules: SignalRules, day: SignalDay) -> list[dict[str, Any]]:
    """Sections four and five: an asset's peers whose 30-day candidates point against its
    core's state, merged into one signal (decision 42), then the core's own 30-day or asset
    candidate against it; each flips that asset in the day's combination, a typical one its
    target, any other none (decision 41)."""
    states = {asset: _object(day.cores.get(asset)).get("state") for asset in ASSETS}
    members = {
        str(core.get("core")): {
            str(item.get("metric_id")): item for item in _objects(core.get("members"))
        }
        for core in _objects(_object(day.macro.get("observation_interfaces")).get("cores"))
    }
    out = []
    for asset in ASSETS:
        state = states[asset]
        if state not in STATES:
            continue
        read = [
            (str(member.get("label")), candidate)
            for metric_id in rules.peers[asset]
            if (member := members.get(asset, {}).get(metric_id)) is not None
            and (candidate := _peer_candidate(member, rules.candidate_sessions)) is not None
        ]
        against = [label for label, candidate in read if candidate != state]
        if against:
            turned = _opposite(str(state))
            out.append(
                _flip(rules.peer_cells[asset, turned], "peers", asset, turned, states, day)
                | {"peers": {"against": against, "read": len(read)}}
            )
    for asset in ASSETS:
        state, core = states[asset], _object(day.cores.get(asset))
        against = [
            kind
            for kind in ("candidate_30d", "candidate_state")
            if state in STATES and core.get(kind) in STATES and core.get(kind) != state
        ]
        if against:
            turned = _opposite(str(state))
            out.append(
                _flip(rules.core_cells[asset, turned], "core_candidate", asset, turned, states, day)
                | {
                    "kind": "observation",
                    "candidates": {
                        "against": against,
                        "candidate_days": core.get("candidate_days"),
                    },
                }
            )
    return out


def _flip(
    cell: str,
    source: str,
    asset: str,
    turned: str,
    states: Mapping[str, object],
    day: SignalDay,
) -> dict[str, Any]:
    flipped = {
        name: CoreAssetState(str(state)) if state in STATES else None
        for name in ASSETS
        for state in [turned if name == asset else states[name]]
    }
    target = derive_formal_stage(
        bond=flipped["bond"],
        stock=flipped["stock"],
        commodity=flipped["commodity"],
        last_confirmed_stage=None,
    ).current_stage
    return {
        "id": cell,
        "kind": "price",
        "source": source,
        "same_source": True,
        "asset_turn": {"asset": asset, "to": turned, "state": states[asset]},
        "combination": {name: states[name] for name in ASSETS},
        "transition": {"from": day.price_stage, "to": target.value if target else None},
    }


def _peer_candidate(member: Mapping[str, Any], window: int) -> str | None:
    """A peer's 30-day candidate from the closes its rows show, the newest public last."""
    for row in _objects(member.get("evidence")):
        values = [
            float(point["value"])
            for point in _objects(_object(row.get("display")).get("points"))
            if isinstance(point.get("value"), (int, float))
        ]
        candidate = candidate_direction(values, window)
        if candidate is not None:
            return candidate.value
    return None


def _opposite(state: str) -> str:
    return "bear" if state == "bull" else "bull"


# Divergent key indicators.


def _divergences(
    rules: SignalRules,
    judgement_rules: MacroJudgementRules,
    day: SignalDay,
    before: Mapping[str, Mapping[str, Any]],
    conclusion: str | None,
    rejudge: Rejudge,
) -> list[dict[str, Any]]:
    """Each divergent key indicator, in its dimension's order, with its minority's way and
    the judgement that way makes: loans, not voting, join credit for it (decision 47)."""
    out = []
    for dimension in _objects(day.confirmation.get("dimensions")):
        for item in _objects(dimension.get("key_indicators")):
            if item.get("consistency") != "divergent":
                continue
            members = _objects(item.get("members"))
            minority = [
                member
                for member in members[1:]
                if member.get("consistency") == "opposes" and member.get("direction")
            ]
            if not minority:
                continue
            direction = Counter(str(member["direction"]) for member in minority).most_common(1)[0][
                0
            ]
            key, name = str(item.get("key")), str(item.get("dimension"))
            period = item.get("statistical_period")
            held = before.get(f"D-{key}")
            periods = (
                1
                if held is None
                else int(held.get("periods", 1))
                + (held.get("indicator", {}).get("period") != period)
            )
            rejudged = (
                _rejudged(judgement_rules, day.confirmation, key, name, direction, rejudge)
                if name in judgement_rules.voters
                else None
            )
            out.append(
                {
                    "id": f"D-{key}",
                    "kind": "divergence",
                    "same_source": False,
                    "indicator": {
                        "key": key,
                        "name": item.get("name"),
                        "dimension": name,
                        "period": period,
                        "main_direction": members[0].get("direction") if members else None,
                    },
                    "minority": {
                        "direction": direction,
                        "members": [str(member.get("label")) for member in minority],
                    },
                    "rejudged": rejudged,
                    "transition": {
                        "from": conclusion,
                        "to": rejudged.get("stage") if rejudged is not None else None,
                    },
                    "periods": periods,
                    "maturity": (
                        "forming" if periods >= rules.divergence_forming_periods else "sprout"
                    ),
                }
            )
    return out


def _rejudged(
    rules: MacroJudgementRules,
    confirmation: Mapping[str, Any],
    key: str,
    dimension: str,
    direction: str,
    rejudge: Rejudge,
) -> dict[str, Any]:
    """The day judged again with ``key``'s main member voting ``direction``, and added to
    its dimension's voters when not one of them."""
    twin = copy.deepcopy(dict(confirmation))
    for item in _objects(twin.get("dimensions")):
        for indicator in _objects(item.get("key_indicators")):
            if indicator.get("key") == key and _objects(indicator.get("members")):
                indicator["members"][0].update(direction=direction, evidence_status="current")
    voters = rules.voters[dimension]
    if key not in voters:
        rules = replace(rules, voters={**rules.voters, dimension: (*voters, key)})
    block = rejudge(rules, twin)
    raw = _object(block.get("raw"))
    value = next(
        (
            item.get("value")
            for item in _objects(block.get("dimensions"))
            if item.get("dimension") == dimension
        ),
        None,
    )
    return {
        "stage": raw.get("stage"),
        "confidence": raw.get("confidence"),
        "matched": raw.get("matched"),
        "known": raw.get("known"),
        "basis": raw.get("basis"),
        "tied": list(raw.get("tied") or ()),
        "dimension": {"dimension": dimension, "value": value},
        "joined": key not in voters,
    }


def _objects(value: object) -> list[Any]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def regrouped(block: Mapping[str, Any]) -> dict[str, Any]:
    """``block`` with its signals grouped against its main conclusion again, as a
    correction restating that conclusion leaves them; nothing else is read again."""
    conclusion = _object(block.get("conclusion")).get("stage")
    stage = None if conclusion is None else str(conclusion)

    def again(item: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(item)
        if item.get("kind") == "divergence":
            item["transition"] = {**_object(item.get("transition")), "from": stage}
        return (
            {**item, **_grouped(item, stage)}
            if isinstance(item.get("transition"), Mapping)
            else item
        )

    return {
        **block,
        **{
            key: [again(item) for item in _objects(block.get(key))]
            for key in ("signals", "sprouts")
            if key in block
        },
    }


GROUPS = ("forward", "back", "hold", "open", "unmapped")
MATURITIES = ("sprout", "forming", "confirmed")
# The table's own signals, listed from forming; any other kind is listed as it is.
_TABLE_KINDS = ("price", "observation")


def validate(block: object) -> None:
    """A published signal list agrees with itself: each signal once, grouped by its target's
    steps from the main conclusion, and of the table's, only forming ones listed."""
    if not _consistent(block):
        raise ValueError("projection_macro_judgement_invalid")


def _consistent(block: object) -> bool:
    if not isinstance(block, Mapping):
        return False
    conclusion = _object(block.get("conclusion")).get("stage")
    listed, sprouts = block.get("signals", []), block.get("sprouts", [])
    if not isinstance(listed, list) or not isinstance(sprouts, list):
        return False
    for items, kept in ((listed, True), (sprouts, False)):
        if len(_objects(items)) != len(items):
            return False
        ids = [item.get("id") for item in items]
        if len(set(ids)) != len(ids):
            return False
        for item in items:
            table = item.get("kind") in _TABLE_KINDS
            if item.get("maturity") not in (*MATURITIES, None) or (
                table and (item.get("maturity") == "sprout") is kept
            ):
                return False
            if not isinstance(item.get("transition"), Mapping) or {
                key: item.get(key) for key in ("group", "steps")
            } != _grouped(item, None if conclusion is None else str(conclusion)):
                return False
    return True
