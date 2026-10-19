"""The macro stage judgement (ADR-0043): the day's main conclusion, from five dimensions.

Policy, credit, growth, prices and inventory each read one direction from the key
indicators the day summary has already read (GLOSSARY: 维度方向), and the six stages of
the macro cycle signature table, frozen with the model, are scored against them: one
point a dimension that matches, an unknown dimension scored nowhere. A unique top score of
at least the threshold is an explicit judgement (decisions 8, 18, 27); the judgement is
never empty short of one (ADR-0043 revised): a tied top is a tendency, too little evidence
weak, each stated with what it was taken from.

The judgement reads the published key indicator documents only -- their members' evidence,
direction, position, consistency and actions -- so it never depends on the formal stage:
the confirmation's own relations, caps, loan count and expectation table are untouched
(macro stage goal). It never rewrites the formal stage, its history or the last confirmed
stage; it is stated against the last confirmed stage, on Pring's ring.

The published block (``cycle_overview.macro_judgement``) keeps apart what later tickets
extend: the raw judgement, the main conclusion, the dimensions, the scores, the hysteresis
state, the signal list and the price verification.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import derive_formal_stage

RULES_VERSION = "macro-judgement-v0001"
MANIFEST_FIELD = "macro_judgement_rules"
DIMENSIONS = ("policy", "credit", "overheat", "price", "inventory")
# The board's three cycles (decision 10): money, the economy, inventory.
GROUPS = (
    ("monetary", ("policy", "credit")),
    ("economic", ("overheat", "price")),
    ("inventory", ("inventory",)),
)
STAGES = tuple(stage.value for stage in FormalStage)
ASSETS = ("bond", "stock", "commodity")


def _typical() -> dict[str, tuple[str, str, str]]:
    """Each stage's typical three cores, as the price stage maps them (ADR-0001)."""
    typical = {}
    for bond, stock, commodity in product(CoreAssetState, repeat=len(ASSETS)):
        result = derive_formal_stage(
            bond=bond, stock=stock, commodity=commodity, last_confirmed_stage=None
        )
        if result.current_stage is not None:
            typical[result.current_stage.value] = (bond.value, stock.value, commodity.value)
    return typical


TYPICAL = _typical()
DIRECTIONS = ("up", "down", "flat")
POSITIONS = ("high", "middle", "low")
POLICY_STATES = ("easing", "tightening", "neutral")
QUADRANTS = ("active_destocking", "passive_destocking", "active_restocking", "passive_restocking")
CONFIDENCES = ("explicit", "tendency", "weak")
# Each raw judgement's basis and the confidence it is stated with (decisions 18, 24).
_CONFIDENCE_OF = {"unique_top": "explicit", "tied": "tendency", "insufficient": "weak"}
# The dimensions read by a vote of key indicators; policy and inventory read their own.
_VOTED = ("credit", "overheat", "price")
# What each dimension's value may be, and so what a signature cell may name.
_VALUES = {
    "policy": POLICY_STATES,
    "credit": DIRECTIONS,
    "overheat": DIRECTIONS,
    "price": DIRECTIONS,
    "inventory": QUADRANTS,
}
_ACTIONS = {"cut": "easing", "hike": "tightening"}


def _cell(
    values: Sequence[str] | None = None, positions: Sequence[str] | None = None
) -> dict[str, list[str]]:
    cell: dict[str, list[str]] = {}
    if values is not None:
        cell["values"] = list(values)
    if positions is not None:
        cell["positions"] = list(positions)
    return cell


# Decision 8: Pring's six stages, each dimension's direction and, where it says, position.
_SIGNATURE = {
    "stage_i": {
        "policy": _cell(["easing"]),
        "credit": _cell(["down"]),
        "overheat": _cell(["down"]),
        "price": _cell(["down"]),
        "inventory": _cell(["active_destocking"]),
    },
    "stage_ii": {
        "policy": _cell(["easing"]),
        "credit": _cell(["flat", "up"]),
        "overheat": _cell(["flat", "up"], ["low"]),
        "price": _cell(positions=["low"]),
        "inventory": _cell(["passive_destocking"]),
    },
    "stage_iii": {
        "policy": _cell(["easing", "neutral"]),
        "credit": _cell(["up"]),
        "overheat": _cell(["up"]),
        "price": _cell(["up"], ["low"]),
        "inventory": _cell(["active_restocking"]),
    },
    "stage_iv": {
        "policy": _cell(["tightening"]),
        "credit": _cell(["up"]),
        "overheat": _cell(["up"]),
        "price": _cell(["up"]),
        "inventory": _cell(["active_restocking"]),
    },
    "stage_v": {
        "policy": _cell(["tightening", "neutral"]),
        "credit": _cell(["down"]),
        "overheat": _cell(["down"], ["high", "middle"]),
        "price": _cell(positions=["high"]),
        "inventory": _cell(["passive_restocking"]),
    },
    "stage_vi": {
        "policy": _cell(["neutral", "easing"]),
        "credit": _cell(["down"]),
        "overheat": _cell(["down"]),
        "price": _cell(["down"]),
        "inventory": _cell(["active_destocking"]),
    },
}


def rules_v0001() -> dict[str, Any]:
    """The first macro judgement rules, frozen into model-v0016 (decisions 7-8, 18-29, 46).

    ``voters``: the key indicators whose main members' directions vote in each dimension,
    loans out of credit; ``tie_breakers``: the one whose direction decides a tied vote;
    ``positions``: the indicator whose main member's place in a year's range is the
    dimension's; ``policy``: the indicators whose cuts and hikes in the evidence window are
    the policy dimension's; ``inventory``: the indicator whose quadrant is the inventory
    dimension's; ``threshold``: the dimensions known and the top score an explicit
    judgement needs; ``hysteresis_sessions``: the sessions running a new judgement stands
    before it replaces the main conclusion (decision 26, the user's "for now").
    """
    return {
        "rules_version": RULES_VERSION,
        "threshold": 3,
        "hysteresis_sessions": 10,
        "policy": ["policy_rate", "lpr", "rrr"],
        "voters": {
            "credit": ["social_financing", "money"],
            "overheat": [
                "pmi",
                "industrial_va",
                "gdp",
                "capacity_utilization",
                "industrial_profit",
            ],
            "price": ["ppi", "cpi", "pmi_prices"],
        },
        "tie_breakers": {"credit": "social_financing"},
        "positions": {"credit": "social_financing", "overheat": "industrial_va", "price": "ppi"},
        "inventory": "inventory_quadrant",
        # Each call its own copy: a manifest edited never edits the next one built.
        "signature": copy.deepcopy(_SIGNATURE),
    }


@dataclass(frozen=True)
class MacroJudgementRules:
    threshold: int
    hysteresis_sessions: int
    policy: tuple[str, ...]
    voters: Mapping[str, tuple[str, ...]]
    tie_breakers: Mapping[str, str]
    positions: Mapping[str, str]
    inventory: str
    signature: Mapping[str, Mapping[str, Mapping[str, tuple[str, ...]]]]

    @classmethod
    def from_manifest(
        cls, manifest: Mapping[str, object], indicators: Mapping[str, str] | None
    ) -> MacroJudgementRules | None:
        """The manifest's rules, or None for a model without them. ``indicators`` are the
        confirmation's key indicators by key, with their dimension: every key the rules
        name is one of them, in the dimension it is read for."""
        raw = manifest.get(MANIFEST_FIELD)
        if raw is None:
            return None
        try:
            return cls._parse(raw, indicators or {})
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ValueError("macro_judgement_rules_invalid") from error

    @classmethod
    def _parse(cls, raw: Any, indicators: Mapping[str, str]) -> MacroJudgementRules:
        if raw["rules_version"] != RULES_VERSION or not indicators:
            raise ValueError("macro_judgement_rules_invalid")
        threshold = raw["threshold"]
        if not isinstance(threshold, int) or not 1 <= threshold <= len(DIMENSIONS):
            raise ValueError("macro_judgement_rules_invalid")
        sessions = raw["hysteresis_sessions"]
        if not isinstance(sessions, int) or isinstance(sessions, bool) or sessions < 1:
            raise ValueError("macro_judgement_rules_invalid")

        def keys(value: Any, dimension: str) -> tuple[str, ...]:
            named = tuple(str(item) for item in value)
            if not named or any(indicators.get(item) != dimension for item in named):
                raise ValueError("macro_judgement_rules_invalid")
            return named

        voters = {dimension: keys(raw["voters"][dimension], dimension) for dimension in _VOTED}
        if set(raw["voters"]) != set(_VOTED):
            raise ValueError("macro_judgement_rules_invalid")
        positions = {key: keys([value], key)[0] for key, value in raw["positions"].items()}
        tie_breakers = {key: str(value) for key, value in raw["tie_breakers"].items()}
        if any(value not in voters[key] for key, value in tie_breakers.items()):
            raise ValueError("macro_judgement_rules_invalid")
        # A stored manifest's keys are sorted: the stages and dimensions keep their own order.
        signature: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {}
        if set(raw["signature"]) != set(STAGES):
            raise ValueError("macro_judgement_rules_invalid")
        for stage in STAGES:
            cells = raw["signature"][stage]
            if set(cells) != set(DIMENSIONS):
                raise ValueError("macro_judgement_rules_invalid")
            signature[stage] = {}
            for dimension in DIMENSIONS:
                cell = cells[dimension]
                values = tuple(cell.get("values", ()))
                wanted = tuple(cell.get("positions", ()))
                if (
                    set(cell) - {"values", "positions"}
                    or not (values or wanted)
                    or not set(values) <= set(_VALUES[dimension])
                    or not set(wanted) <= set(POSITIONS)
                    or (wanted and dimension not in positions)
                ):
                    raise ValueError("macro_judgement_rules_invalid")
                signature[stage][dimension] = {"values": values, "positions": wanted}
        return cls(
            threshold=threshold,
            hysteresis_sessions=sessions,
            policy=keys(raw["policy"], "policy"),
            voters=voters,
            tie_breakers=tie_breakers,
            positions=positions,
            inventory=keys([raw["inventory"]], "inventory")[0],
            signature=signature,
        )


def judge(
    rules: MacroJudgementRules,
    confirmation: Mapping[str, object],
    *,
    reference: FormalStage | None,
    cores: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """The day's macro judgement block, from its published key indicator documents.

    ``reference`` is the last confirmed stage the day's set states: the cores' own stage
    when typical. ``cores`` are the day's three core states (bond, stock, commodity) when
    its combination is read, typical or not; None when a core is unavailable or pending.
    The judgement is never empty (decisions 18, 24, 27, 35): a unique top of at least the
    threshold is explicit, a tied top the tied stage nearest ``reference`` (a tendency),
    and too little evidence weak, from the cores' combination. The conclusion is the raw
    judgement's, and no hysteresis is counted: ``hold`` counts it against the conclusion
    before.
    """
    keyed = {
        str(item["key"]): item
        for dimension in _objects(confirmation.get("dimensions"))
        for item in _objects(dimension.get("key_indicators"))
    }
    dimensions = [
        {"dimension": name, "group": _group(name), **_dimension(rules, name, keyed)}
        for name in DIMENSIONS
    ]
    known = [item for item in dimensions if item["value"] is not None]
    scores = {
        stage: sum(_matches(rules.signature[stage][str(item["dimension"])], item) for item in known)
        for stage in STAGES
    }
    top = max(scores.values())
    leaders = [stage for stage in STAGES if scores[stage] == top]
    # Too little evidence first, so a tie below the threshold is weak, never a tendency.
    if len(known) < rules.threshold or top < rules.threshold:
        fallback = _fallback(cores)
        weak = _pick("insufficient", (), fallback, reference)
        raw = _raw(weak, scores, len(known), basis="insufficient", fallback=fallback)
    elif len(leaders) > 1:
        # The tied stage nearest the last confirmed one, the others stated with it.
        raw = _raw(nearest(leaders, reference), scores, len(known), basis="tied", tied=leaders)
    else:
        raw = _raw(leaders[0], scores, len(known), basis="unique_top")
    raw["threshold"] = rules.threshold
    return {
        "rules_version": RULES_VERSION,
        "raw": raw,
        "conclusion": conclusion(raw, reference),
        "hysteresis": None,
        "dimensions": scored(rules, dimensions, raw["stage"]),
        "scores": scores,
        "signals": [],
        "price_verification": None,
    }


def scored(
    rules: MacroJudgementRules, dimensions: Sequence[Mapping[str, Any]], stage: object
) -> list[dict[str, Any]]:
    """``dimensions``, each told whether it matches ``stage``'s signature cell: the main
    conclusion's, so that what the board and the report give as its basis is its own
    (decision 45); none for a dimension not known, or without a stage."""
    return [
        {
            **item,
            "matches": (
                _matches(rules.signature[str(stage)][str(item["dimension"])], item)
                if stage is not None and item.get("value") is not None
                else None
            ),
        }
        for item in dimensions
    ]


def formed(block: Mapping[str, object], day: str) -> dict[str, object]:
    """What a main conclusion taken from the day's raw judgement keeps of it while the
    hysteresis holds it: its stage and confidence, the tie or fallback it was taken from,
    the stage it was stated against, the day's scores and unknown dimensions, and the day
    (decisions 24, 45)."""
    raw = _object(block.get("raw"))
    return {
        "on": day,
        **{
            field: raw.get(field)
            for field in ("stage", "confidence", "basis", "tied", "matched", "known")
        },
        "threshold": raw.get("threshold"),
        "fallback": raw.get("fallback"),
        "reference_stage": _object(block.get("conclusion")).get("reference_stage"),
        "scores": dict(_object(block.get("scores"))),
        "unknown": [
            str(item.get("dimension"))
            for item in _objects(block.get("dimensions"))
            if item.get("value") is None
        ],
    }


# A day corrected on its cores only, its context past retention, keeps the judgement it
# published, restated against its last confirmed stage and marked so (integration review F4).
NOT_RECOMPUTED = "not_recomputed"


def record(block: Mapping[str, object]) -> dict[str, object]:
    """What the stage history records of a day's judgement: its main conclusion's stage
    and confidence, after the hysteresis, never the run counted toward replacing it
    (decision 33); both None on a day with no stage to take (decision 49), and marked when
    the day's context was not recomputed."""
    main = _object(block.get("conclusion"))
    recorded: dict[str, object] = {"stage": main.get("stage"), "confidence": main.get("confidence")}
    if block.get("context_status") == NOT_RECOMPUTED:
        recorded["context_status"] = NOT_RECOMPUTED
    return recorded


def conclusion(raw: Mapping[str, object], reference: FormalStage | str | None) -> dict[str, object]:
    """The main conclusion the raw judgement makes, stated against ``reference``."""
    stage = raw.get("stage")
    reference_stage = FormalStage(reference).value if reference is not None else None
    steps = ring_steps(reference_stage, str(stage)) if stage is not None else None
    return {
        "stage": stage,
        "confidence": raw.get("confidence"),
        "matched": raw.get("matched"),
        "known": raw.get("known"),
        "reference_stage": reference_stage,
        "steps": steps,
        "direction": (
            None if steps is None else "forward" if steps > 0 else "back" if steps < 0 else "same"
        ),
    }


@dataclass(frozen=True)
class Earlier:
    """The judgement a day's hysteresis counts on from: the latest one an earlier day
    published, and whether that day is the session before (decision 32; ticket 05)."""

    judgement: Mapping[str, Any]
    previous_session: bool


def hold(
    block: Mapping[str, object],
    earlier: Earlier | None,
    *,
    rules: MacroJudgementRules,
    day: str,
) -> dict[str, object]:
    """``block``, ``day``'s, with its main conclusion and hysteresis counted on from
    ``earlier`` (decisions 26, 32, 44, 45), and its dimensions told against the conclusion.

    With no conclusion before, the raw judgement is the conclusion; one at the conclusion's
    stage is it, at the day's confidence. One at another stage is a candidate, counted on
    from the session before when that session's was the same, else from one: on its
    ``sessions_required``-th session running it replaces the conclusion, and until then the
    conclusion keeps its stage and confidence, scored on the day's dimensions. A weak one
    replaces only a weak conclusion: against any other it counts nothing, and a run is
    broken. Nothing is counted across a session without a judgement. A conclusion keeps
    what it was ``formed`` from: the day's raw judgement, or, held, the one it was taken
    from before."""
    sessions_required = rules.hysteresis_sessions
    raw = _object(block.get("raw"))
    reference = _object(block.get("conclusion")).get("reference_stage")
    before = _object(earlier.judgement.get("conclusion")) if earlier is not None else {}
    stage, kept = raw.get("stage"), before.get("stage")
    candidate, sessions = None, 0
    if kept is None:
        basis = "initial"
    elif stage == kept:
        basis = "agrees"
    elif stage is None or (raw.get("confidence") == "weak" and before.get("confidence") != "weak"):
        basis = "held"
    else:
        assert earlier is not None
        counted = _object(earlier.judgement.get("hysteresis"))
        sessions = 1 + (
            int(counted.get("sessions") or 0)
            if earlier.previous_session and counted.get("candidate") == stage
            else 0
        )
        if sessions >= sessions_required:
            basis, sessions = "replaced", 0
        else:
            basis, candidate = "held", stage
    state = {
        "sessions_required": sessions_required,
        "basis": basis,
        "candidate": candidate,
        "sessions": sessions,
    }
    if basis != "held":
        main = {**conclusion(raw, reference), "formed": formed(block, day)}
    else:
        main = conclusion(
            {
                "stage": kept,
                "confidence": before.get("confidence"),
                "matched": _object(block.get("scores"))[str(kept)],
                "known": raw.get("known"),
            },
            reference,
        )
        main["formed"] = before.get("formed")
    return {
        **block,
        "conclusion": main,
        "hysteresis": state,
        "dimensions": scored(rules, _objects(block.get("dimensions")), main["stage"]),
    }


def with_reference(
    block: Mapping[str, object],
    reference: str | None,
    *,
    earlier: Earlier | None,
    rules: MacroJudgementRules,
    day: str,
) -> dict[str, object]:
    """``block`` with its conclusion stated against another last confirmed stage, as a
    correction of that stage alone states it; nothing else is judged again.

    A tendency or weak raw judgement takes its stage again from the same ties or fallback
    against that stage, and an explicit one keeps its stage; the hysteresis is counted
    again on from ``earlier``, as it stands now."""
    raw = _object(block.get("raw"))
    if (basis := raw.get("basis")) in {"tied", "insufficient"}:
        tied, fallback = raw.get("tied") or (), raw.get("fallback")
        raw = {
            **_raw(
                _pick(str(basis), tied, fallback, reference),
                _object(block.get("scores")),
                int(raw["known"]),
                basis=str(basis),
                tied=tied,
                fallback=fallback,
            ),
            "threshold": raw.get("threshold"),
        }
    judged = {**block, "raw": raw, "conclusion": conclusion(raw, reference)}
    if not _object(block.get("hysteresis")):
        return {
            **judged,
            "dimensions": scored(rules, _objects(block.get("dimensions")), raw["stage"]),
        }
    return hold(judged, earlier, rules=rules, day=day)


def nearest(candidates: Sequence[str], reference: FormalStage | str | None) -> str:
    """The candidate fewest ring steps from ``reference``, forward on equal steps (decision
    35); without a last confirmed stage, the first in Pring's order."""
    if reference is None:
        return candidates[0]
    origin = FormalStage(reference).value
    return min(candidates, key=lambda stage: _distance(ring_steps(origin, stage)))


def _distance(steps: int | None) -> tuple[int, int]:
    return (abs(steps or 0), -(steps or 0))


def ring_steps(origin: str | None, target: str) -> int | None:
    """Steps from ``origin`` to ``target`` on Pring's ring (I to VI and on to I), the
    shorter way, forward when both ways are three (decision 35); none without an origin."""
    if origin is None:
        return None
    steps = (STAGES.index(target) - STAGES.index(origin)) % len(STAGES)
    return steps if steps <= len(STAGES) // 2 else steps - len(STAGES)


def _raw(
    stage: str | None,
    scores: Mapping[str, int],
    known: int,
    *,
    basis: str,
    tied: Sequence[str] = (),
    fallback: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "stage": stage,
        # Only without a stage to take (no cores and no last confirmed stage) is it none.
        "confidence": _CONFIDENCE_OF[basis] if stage is not None else None,
        # The stage's matching dimensions; without a stage, the top score.
        "matched": scores[stage] if stage is not None else max(scores.values()),
        "known": known,
        "basis": basis,
        "tied": list(tied),
        "fallback": dict(fallback) if fallback is not None else None,
    }


def _fallback(cores: Mapping[str, str] | None) -> dict[str, object]:
    """Where a weak judgement is taken from: the typical stages fewest assets off the day's
    combination -- the price stage itself when typical -- or, its cores unavailable, the
    last confirmed stage (decisions 18, 35)."""
    if cores is None:
        return {"source": "reference", "combination": None, "differences": None, "candidates": []}
    off = {
        stage: sum(cores[asset] != state for asset, state in zip(ASSETS, pattern, strict=True))
        for stage, pattern in TYPICAL.items()
    }
    fewest = min(off.values())
    return {
        "source": "combination",
        "combination": {asset: cores[asset] for asset in ASSETS},
        "differences": fewest,
        "candidates": [stage for stage in STAGES if off[stage] == fewest],
    }


def _pick(
    basis: str,
    tied: Sequence[str],
    fallback: Mapping[str, Any] | None,
    reference: FormalStage | str | None,
) -> str | None:
    """The stage a judgement short of explicit takes against ``reference``."""
    if basis == "tied":
        return nearest(tied, reference)
    if fallback is not None and fallback.get("source") == "combination":
        return nearest(list(fallback["candidates"]), reference)
    return FormalStage(reference).value if reference is not None else None


def _group(dimension: str) -> str:
    return next(group for group, members in GROUPS if dimension in members)


def _matches(cell: Mapping[str, tuple[str, ...]], reading: Mapping[str, object]) -> bool:
    values, positions = cell["values"], cell["positions"]
    return (not values or reading["value"] in values) and (
        not positions or reading["position"] in positions
    )


def _dimension(
    rules: MacroJudgementRules, name: str, keyed: Mapping[str, Mapping[str, Any]]
) -> dict[str, object]:
    if name == "policy":
        return _policy(rules, keyed)
    if name == "inventory":
        return _inventory(rules, keyed)
    return _voted(rules, name, keyed)


def _main(item: Mapping[str, Any] | None) -> Mapping[str, Any]:
    members = _objects(item.get("members")) if item is not None else []
    return members[0] if members else {}


def _voted(
    rules: MacroJudgementRules, name: str, keyed: Mapping[str, Mapping[str, Any]]
) -> dict[str, object]:
    """Decision 7, 19, 29, 46: the clear main members' majority, a divergent indicator by
    its main member; fewer than half clear, or a tie, is unknown -- a tie in credit is
    social financing's. The dimension's other indicators are listed, not voting."""
    voters = rules.voters[name]
    indicators = []
    votes: list[str] = []
    for key in voters:
        item = keyed.get(key)
        vote = _vote(item)
        if vote is not None:
            votes.append(vote)
        indicators.append(_voter(key, item, vote, voting=True))
    indicators += [
        _voter(key, item, None, voting=False)
        for key, item in keyed.items()
        if item.get("dimension") == name and key not in voters
    ]
    tally = dict(sorted(Counter(votes).items()))
    position_main = _main(keyed.get(rules.positions[name]))
    position = (
        position_main.get("position")
        if position_main.get("evidence_status") == "current"
        and position_main.get("position") in POSITIONS
        else None
    )
    reading: dict[str, object] = {
        "value": None,
        "position": position,
        "position_from": rules.positions[name],
        "tally": tally,
        "indicators": indicators,
    }
    if len(votes) * 2 < len(voters):
        return {**reading, "basis": "short_of_half"}
    ranked = Counter(votes).most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        breaker = rules.tie_breakers.get(name)
        decided = _vote(keyed.get(breaker)) if breaker is not None else None
        if decided is None:
            return {**reading, "basis": "tied"}
        return {**reading, "value": decided, "basis": "tie_broken", "tie_breaker": breaker}
    return {**reading, "value": ranked[0][0], "basis": "majority"}


def _vote(item: Mapping[str, Any] | None) -> str | None:
    """The indicator's main member's direction, when its evidence is current."""
    main = _main(item)
    direction = main.get("direction")
    return (
        str(direction)
        if main.get("evidence_status") == "current" and direction in DIRECTIONS
        else None
    )


def _voter(
    key: str, item: Mapping[str, Any] | None, vote: str | None, *, voting: bool
) -> dict[str, object]:
    main = _main(item)
    return {
        "key": key,
        "name": item.get("name") if item is not None else None,
        "voting": voting,
        "vote": vote,
        "divergent": item is not None and item.get("consistency") == "divergent",
        "period": item.get("statistical_period") if item is not None else None,
        "evidence_status": main.get("evidence_status"),
    }


def _policy(
    rules: MacroJudgementRules, keyed: Mapping[str, Mapping[str, Any]]
) -> dict[str, object]:
    """Decision 7: a cut (the policy rate, the LPR, the RRR) in the window is easing, a hike
    tightening, both unknown; none is neutral, supporting neither side.

    Read as the backtest read it (macro stage 01): a member whose history is not whole --
    its baseline or a session's notice not held -- adds no action, and no action seen in a
    window where another member was read is none; with no member read, the policy is not
    known."""
    indicators = []
    kinds: list[str] = []
    read = False
    for key in rules.policy:
        item = keyed.get(key)
        members = _objects(item.get("members")) if item is not None else []
        actions = [
            {
                "period": action.get("period"),
                "action": action.get("action"),
                "member": member.get("name"),
            }
            for member in members
            if member.get("role") in {"main", "auxiliary"}
            for action in _objects(member.get("actions"))
            if action.get("action") in _ACTIONS
        ]
        kinds += [str(action["action"]) for action in actions]
        main_action = _main(item).get("action")
        read = read or main_action is not None
        indicators.append(
            {
                "key": key,
                "name": item.get("name") if item is not None else None,
                "voting": True,
                "action": main_action,
                "actions": actions,
                "evidence_status": _main(item).get("evidence_status"),
            }
        )
    indicators += [
        {"key": key, "name": item.get("name"), "voting": False}
        for key, item in keyed.items()
        if item.get("dimension") == "policy" and key not in rules.policy
    ]
    if "cut" in kinds and "hike" in kinds:
        value, basis = None, "cut_and_hike"
    elif "cut" in kinds or "hike" in kinds:
        value, basis = _ACTIONS[kinds[-1]], kinds[-1]
    elif read:
        value, basis = "neutral", "no_action"
    else:
        value, basis = None, "unread"
    return {"value": value, "position": None, "basis": basis, "indicators": indicators}


def _inventory(
    rules: MacroJudgementRules, keyed: Mapping[str, Mapping[str, Any]]
) -> dict[str, object]:
    """The inventory dimension is its quadrant (GLOSSARY: 维度方向); unclassified, or its
    evidence not current, it is not known."""
    item = keyed.get(rules.inventory)
    main = _main(item)
    quadrant = main.get("quadrant")
    known = main.get("evidence_status") == "current" and quadrant in QUADRANTS
    return {
        "value": quadrant if known else None,
        "position": None,
        "basis": "quadrant" if known else "unclassified",
        "indicators": [
            {
                "key": rules.inventory,
                "name": item.get("name") if item is not None else None,
                "voting": True,
                "quadrant": quadrant,
                "divergent": item is not None and item.get("consistency") == "divergent",
                "period": item.get("statistical_period") if item is not None else None,
                "evidence_status": main.get("evidence_status"),
            }
        ],
    }


def _objects(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _object(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate(block: object) -> None:
    """A published judgement agrees with itself: its five dimensions in order and group,
    each stage's score within the dimensions known, an explicit stage the unique top, and
    its conclusion stated on the ring from its last confirmed stage."""
    if not _consistent(block):
        raise ValueError("projection_macro_judgement_invalid")


def _consistent(block: object) -> bool:
    if not isinstance(block, Mapping) or block.get("rules_version") != RULES_VERSION:
        return False
    dimensions = _objects(block.get("dimensions"))
    if [(item.get("dimension"), item.get("group")) for item in dimensions] != [
        (name, _group(name)) for name in DIMENSIONS
    ]:
        return False
    if any(
        item.get("value") not in (None, *_VALUES[str(item["dimension"])])
        or item.get("position") not in (None, *POSITIONS)
        for item in dimensions
    ):
        return False
    known = sum(item.get("value") is not None for item in dimensions)
    scores = _object(block.get("scores"))
    if set(scores) != set(STAGES) or any(
        not isinstance(score, int) or not 0 <= score <= known for score in scores.values()
    ):
        return False
    raw, main = _object(block.get("raw")), _object(block.get("conclusion"))
    for judgement in (raw, main):
        stage, confidence = judgement.get("stage"), judgement.get("confidence")
        if (stage is None) != (confidence is None) or stage not in (None, *STAGES):
            return False
        if confidence not in (None, *CONFIDENCES) or judgement.get("known") != known:
            return False
    if not _raw_consistent(raw, scores, known, main.get("reference_stage")):
        return False
    stage = main.get("stage")
    expected = conclusion(main, main.get("reference_stage"))
    if stage is not None and main.get("matched") != scores[str(stage)]:
        return False
    # Each dimension is told against the main conclusion: its marks are the conclusion's
    # score, and only a known dimension of a stage is marked.
    marks = [item.get("matches") for item in dimensions]
    if any(
        (mark is None) != (stage is None or item.get("value") is None)
        or mark not in (None, True, False)
        for mark, item in zip(marks, dimensions, strict=True)
    ):
        return False
    if stage is not None and marks.count(True) != main.get("matched"):
        return False
    if not _held_consistent(block.get("hysteresis"), raw, main):
        return False
    if not _formed_consistent(block, main):
        return False
    return all(main.get(field) == expected[field] for field in ("steps", "direction"))


def validate_inputs(
    block: object,
    rules: MacroJudgementRules,
    *,
    confirmation: object,
    last_confirmed: object,
) -> None:
    """A published judgement is the one its model's frozen ``rules`` make of its set: its
    dimensions read from the set's ``confirmation`` (when its context was summarized), its
    scores and marks from those dimensions, and its conclusion stated against the last
    confirmed stage the set states (``last_confirmed``)."""
    if not isinstance(block, Mapping) or not _inputs_consistent(
        block, rules, confirmation, last_confirmed
    ):
        raise ValueError("projection_macro_judgement_invalid")


def _inputs_consistent(
    block: Mapping[str, Any],
    rules: MacroJudgementRules,
    confirmation: object,
    last_confirmed: object,
) -> bool:
    dimensions = _objects(block.get("dimensions"))
    main = _object(block.get("conclusion"))
    if main.get("reference_stage") != last_confirmed:
        return False
    known = [item for item in dimensions if item.get("value") is not None]
    if dict(_object(block.get("scores"))) != {
        stage: sum(_matches(rules.signature[stage][str(item["dimension"])], item) for item in known)
        for stage in STAGES
    }:
        return False
    if dimensions != scored(rules, dimensions, main.get("stage")):
        return False
    if not isinstance(confirmation, Mapping):
        return True
    fresh = judge(rules, confirmation, reference=None)
    return [_unmarked(item) for item in _objects(fresh.get("dimensions"))] == [
        _unmarked(item) for item in dimensions
    ]


def _unmarked(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "matches"}


def _formed_consistent(block: Mapping[str, Any], main: Mapping[str, Any]) -> bool:
    """A conclusion taken from the day's raw judgement keeps that judgement as it stands; a
    held one keeps the one it was taken from, at its stage and confidence (decision 24)."""
    if block.get("hysteresis") is None:
        return "formed" not in main
    kept = main.get("formed")
    if not isinstance(kept, Mapping):
        return False
    if _object(block.get("hysteresis")).get("basis") == "held":
        return (kept.get("stage"), kept.get("confidence")) == (
            main.get("stage"),
            main.get("confidence"),
        )
    return {**kept, "on": None} == {**formed(block, ""), "on": None}


def _held_consistent(counted: object, raw: Mapping[str, Any], main: Mapping[str, Any]) -> bool:
    """The conclusion is the raw judgement's unless held; held, it is at another stage, and
    the raw judgement is the candidate, short of the sessions that replace it, or one that
    counts nothing: weak against a conclusion that is not, or without a stage."""
    follows = (main.get("stage"), main.get("confidence")) == (
        raw.get("stage"),
        raw.get("confidence"),
    )
    if counted is None:
        return follows
    if not isinstance(counted, Mapping):
        return False
    required, basis = counted.get("sessions_required"), counted.get("basis")
    candidate, sessions = counted.get("candidate"), counted.get("sessions")
    if not isinstance(required, int) or required < 1 or not isinstance(sessions, int):
        return False
    if basis in {"initial", "agrees", "replaced"}:
        return (
            follows
            and candidate is None
            and sessions == 0
            and (basis != "agrees" or main.get("stage") is not None)
        )
    if basis != "held" or main.get("stage") is None or main.get("stage") == raw.get("stage"):
        return False
    uncounted = raw.get("stage") is None or (
        raw.get("confidence") == "weak" and main.get("confidence") != "weak"
    )
    if candidate is None:
        return uncounted and sessions == 0
    return not uncounted and candidate == raw.get("stage") and 1 <= sessions < required


def _raw_consistent(
    raw: Mapping[str, Any], scores: Mapping[str, int], known: int, reference: object
) -> bool:
    """The raw judgement is the one its scores, ties and fallback give against the last
    confirmed stage: explicit only a unique top of at least the threshold, a tendency only
    a tie at or past it, weak only short of it (decisions 18, 24, 27, 35)."""
    basis, stage, threshold = raw.get("basis"), raw.get("stage"), raw.get("threshold")
    top = max(scores.values())
    leaders = [name for name in STAGES if scores[name] == top]
    if basis not in _CONFIDENCE_OF or not isinstance(threshold, int):
        return False
    if reference is not None and reference not in STAGES:
        return False
    short = known < threshold or top < threshold
    if short != (basis == "insufficient") or (basis == "tied") != (not short and len(leaders) > 1):
        return False
    tied, fallback = raw.get("tied"), raw.get("fallback")
    if tied != (leaders if basis == "tied" else []):
        return False
    if basis == "insufficient":
        if not isinstance(fallback, Mapping):
            return False
        combination = fallback.get("combination")
        if fallback != _fallback(_combination(combination) if combination is not None else None):
            return False
    elif fallback is not None:
        return False
    expected = leaders[0] if basis == "unique_top" else _pick(basis, leaders, fallback, reference)
    if stage != expected:
        return False
    if stage is None:
        return raw.get("confidence") is None and raw.get("matched") == top
    return raw.get("confidence") == _CONFIDENCE_OF[basis] and raw.get("matched") == scores[stage]


def _combination(value: object) -> Mapping[str, str] | None:
    """A published combination's three core states, when it states each as bull or bear."""
    states = {state.value for state in CoreAssetState}
    if (
        isinstance(value, Mapping)
        and set(value) == set(ASSETS)
        and all(value[asset] in states for asset in ASSETS)
    ):
        return {asset: str(value[asset]) for asset in ASSETS}
    return None
