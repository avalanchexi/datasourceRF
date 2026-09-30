from __future__ import annotations

import pytest

from pring_cycle.domain.macro import (
    EvidenceSignal,
    derive_credit_response,
    derive_inventory_cycle,
    derive_overheat_state,
    derive_policy_direction,
    derive_price_pressure,
)


def signal(metric_id: str, direction: str, role: str) -> EvidenceSignal:
    return EvidenceSignal(
        observation_id=f"obs:{metric_id}",
        metric_id=metric_id,
        direction=direction,
        role=role,
        freshness="current",
        conflict=False,
    )


def test_policy_action_and_market_transmission_remain_separate() -> None:
    result = derive_policy_direction(
        actions=[signal("CN_OMO_7D_RATE", "easing", "policy_action")],
        transmission=[signal("CN_DR007_POLICY_SPREAD", "tightening", "transmission")],
    )

    assert result.state == "transmission_conflict"
    assert result.score is None
    assert result.support[0].metric_id == "CN_OMO_7D_RATE"
    assert result.counterevidence[0].metric_id == "CN_DR007_POLICY_SPREAD"


def test_overheat_and_price_pressure_publish_named_states_without_scores() -> None:
    overheat = derive_overheat_state(
        [
            signal("CN_PMI_ACTIVITY", "up", "demand"),
            signal("CN_INDUSTRIAL_VA", "up", "production"),
            signal("CN_CREDIT_IMPULSE", "up", "credit"),
        ]
    )
    price = derive_price_pressure(
        [
            signal("CN_COMMODITY_CORE_NHII", "up", "upstream"),
            signal("CN_PPI", "up", "producer"),
            signal("CN_CORE_CPI", "flat", "consumer"),
        ]
    )

    assert overheat.state == "heating"
    assert overheat.score is None
    assert price.state == "producer_diffusion"
    assert price.score is None


def test_inventory_requires_demand_production_and_inventory_and_has_seven_cards() -> None:
    result = derive_inventory_cycle(
        demand="up",
        production="up",
        inventory="up",
        observations=[signal("CN_ORDER_INVENTORY_SPREAD", "up", "orders_inventory_gap")],
    )

    assert result.quadrant == "active_restocking"
    assert len(result.cards) == 7
    assert result.score is None
    assert result.cards[0].status in {"support", "conflict", "missing"}


def test_credit_response_keeps_money_social_financing_and_loan_structure_distinct() -> None:
    result = derive_credit_response(
        [
            signal("CN_M1_M2", "up", "money"),
            signal("CN_SF_TOTAL", "up", "social_financing"),
            signal("CN_LOAN_STRUCTURE", "down", "loan_structure"),
        ]
    )

    assert result.state == "mixed"
    assert {item.metric_id for item in result.support} == {"CN_M1_M2", "CN_SF_TOTAL"}
    assert {item.metric_id for item in result.counterevidence} == {"CN_LOAN_STRUCTURE"}


def test_inventory_cards_do_not_duplicate_unrelated_evidence() -> None:
    result = derive_inventory_cycle(
        demand="up",
        production="up",
        inventory="down",
        observations=[signal("CN_ORDER_INVENTORY_SPREAD", "up", "orders_inventory_gap")],
    )

    assert result.cards[0].status == "support"
    assert result.cards[0].evidence_ids == ("obs:CN_ORDER_INVENTORY_SPREAD",)
    assert all(card.evidence_ids == () for card in result.cards[1:])


def test_inventory_card_with_current_evidence_is_not_marked_missing_when_quadrant_is_unresolved() -> (
    None
):
    result = derive_inventory_cycle(
        demand="up",
        production="down",
        inventory="up",
        observations=[signal("CN_ORDER_INVENTORY_SPREAD", "up", "orders_inventory_gap")],
    )

    assert result.quadrant is None
    assert result.cards[0].status == "support"


@pytest.mark.parametrize(
    "freshness",
    (
        "awaiting_source_certification",
        "missing",
        "source_failed",
        "validation_failed",
        "invalid",
    ),
)
def test_inventory_card_never_labels_unusable_evidence_as_support(
    freshness: str,
) -> None:
    unusable = EvidenceSignal(
        observation_id=f"obs:{freshness}",
        metric_id="CN_ORDER_INVENTORY_SPREAD",
        direction="unknown",
        role="orders_inventory_gap",
        freshness=freshness,
        conflict=False,
    )

    result = derive_inventory_cycle(
        demand=None,
        production=None,
        inventory=None,
        observations=[unusable],
    )

    assert result.cards[0].status == "missing"


@pytest.mark.parametrize(
    ("demand", "production", "inventory", "expected"),
    (
        ("down", "down", "down", "active_destocking"),
        ("up", "up", "down", "passive_destocking"),
        ("up", "up", "up", "active_restocking"),
        ("down", "down", "up", "passive_restocking"),
    ),
)
def test_inventory_four_quadrants_are_mechanical(
    demand: str,
    production: str,
    inventory: str,
    expected: str,
) -> None:
    result = derive_inventory_cycle(
        demand=demand,
        production=production,
        inventory=inventory,
        observations=[],
    )

    assert result.quadrant == expected


def test_inventory_refuses_noncanonical_or_missing_direction_combinations() -> None:
    assert (
        derive_inventory_cycle(
            demand="up",
            production="down",
            inventory="up",
            observations=[],
        ).quadrant
        is None
    )
    assert (
        derive_inventory_cycle(
            demand=None,
            production="up",
            inventory="up",
            observations=[],
        ).quadrant
        is None
    )
