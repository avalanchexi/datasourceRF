from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceSignal:
    observation_id: str
    metric_id: str
    direction: str
    role: str
    freshness: str
    conflict: bool
    period_start: str | None = None
    period: str | None = None
    available_at: str | None = None
    selected_claim_id: str | None = None
    source_reference: str | None = None
    value: float | None = None
    unit: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)
    value_state: str | None = None


@dataclass(frozen=True)
class MacroState:
    state: str
    support: tuple[EvidenceSignal, ...]
    counterevidence: tuple[EvidenceSignal, ...]
    gaps: tuple[EvidenceSignal, ...]
    score: None = None


@dataclass(frozen=True)
class SignatureCard:
    name: str
    status: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class InventoryCycle:
    quadrant: str | None
    cards: tuple[SignatureCard, ...]
    score: None = None


def derive_policy_direction(
    *, actions: list[EvidenceSignal], transmission: list[EvidenceSignal]
) -> MacroState:
    valid_actions = _valid(actions)
    valid_transmission = _valid(transmission)
    if not valid_actions or not valid_transmission:
        return MacroState(
            "insufficient_data", tuple(valid_actions), (), tuple(actions + transmission)
        )
    action_directions = {item.direction for item in valid_actions}
    transmission_directions = {item.direction for item in valid_transmission}
    if (
        len(action_directions) != 1
        or len(transmission_directions) != 1
        or action_directions != transmission_directions
    ):
        return MacroState(
            "transmission_conflict", tuple(valid_actions), tuple(valid_transmission), ()
        )
    direction = next(iter(action_directions))
    state = direction if direction in {"easing", "tightening", "neutral"} else "neutral"
    return MacroState(state, tuple(valid_actions + valid_transmission), (), ())


def derive_credit_response(signals: list[EvidenceSignal]) -> MacroState:
    valid = _valid(signals)
    required_roles = {"money", "social_financing", "loan_structure"}
    observed_roles = {item.role for item in valid}
    if not required_roles.issubset(observed_roles):
        state = "insufficient_data"
    else:
        directions = {item.direction for item in valid}
        if directions <= {"up", "expanding"}:
            state = "expanding"
        elif directions <= {"down", "contracting"}:
            state = "contracting"
        else:
            state = "mixed"
    return MacroState(
        state,
        tuple(item for item in valid if item.direction in {"up", "expanding"}),
        tuple(item for item in valid if item.direction in {"down", "contracting"}),
        tuple(item for item in signals if item not in valid),
    )


def derive_overheat_state(signals: list[EvidenceSignal]) -> MacroState:
    valid = _valid(signals)
    required_roles = {"demand", "production", "credit"}
    observed_roles = {item.role for item in valid}
    up_roles = {item.role for item in valid if item.direction == "up"}
    high_roles = {item.role for item in valid if item.direction == "high"}
    down = [item for item in valid if item.direction == "down"]
    if not required_roles.issubset(observed_roles):
        state = "insufficient_data"
    elif len(high_roles & required_roles) >= 2:
        state = "overheated"
    elif up_roles >= required_roles:
        state = "heating"
    elif down:
        state = "cooling"
    else:
        state = "insufficient_data"
    return MacroState(
        state,
        tuple(item for item in valid if item.direction in {"up", "high"}),
        tuple(down),
        tuple(item for item in signals if item not in valid),
    )


def derive_price_pressure(signals: list[EvidenceSignal]) -> MacroState:
    valid = _valid(signals)
    up_roles = {item.role for item in valid if item.direction == "up"}
    if not valid:
        state = "insufficient_data"
    elif "consumer" in up_roles:
        state = "consumer_diffusion"
    elif "producer" in up_roles:
        state = "producer_diffusion"
    elif "upstream" in up_roles:
        state = "upstream_pressure"
    else:
        state = "easing"
    return MacroState(
        state,
        tuple(item for item in valid if item.direction == "up"),
        tuple(item for item in valid if item.direction in {"down", "flat"}),
        tuple(item for item in signals if item not in valid),
    )


def derive_inventory_cycle(
    *,
    demand: str | None,
    production: str | None,
    inventory: str | None,
    observations: list[EvidenceSignal],
) -> InventoryCycle:
    quadrant_by_directions: Mapping[tuple[str | None, str | None, str | None], str] = {
        ("down", "down", "down"): "active_destocking",
        ("up", "up", "down"): "passive_destocking",
        ("up", "up", "up"): "active_restocking",
        ("down", "down", "up"): "passive_restocking",
    }
    quadrant = quadrant_by_directions.get((demand, production, inventory))
    card_names = (
        "orders_inventory_gap",
        "materials_finished_goods",
        "physical_inventory",
        "inventory_sales_turnover",
        "prices_profits",
        "capacity",
        "credit_physical_inventory",
    )
    cards = tuple(_signature_card(name, observations, quadrant) for name in card_names)
    return InventoryCycle(quadrant, cards)


def _signature_card(
    name: str,
    observations: list[EvidenceSignal],
    quadrant: str | None,
) -> SignatureCard:
    matching = [item for item in observations if item.role == name]
    evidence_ids = tuple(item.observation_id for item in matching)
    if any(item.conflict for item in matching):
        status = "conflict"
    elif any(item.freshness == "awaiting_release" for item in matching):
        status = "awaiting_release"
    elif any(item.freshness == "current" for item in matching):
        status = "support"
    elif any(item.freshness == "stale" for item in matching):
        status = "stale"
    else:
        status = "missing"
    return SignatureCard(name, status, evidence_ids)


def _valid(signals: list[EvidenceSignal]) -> list[EvidenceSignal]:
    return [item for item in signals if item.freshness == "current" and not item.conflict]
