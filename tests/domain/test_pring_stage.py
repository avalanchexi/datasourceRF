from __future__ import annotations

import itertools

import pytest

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import derive_formal_stage


@pytest.mark.parametrize(
    ("bond", "stock", "commodity", "expected"),
    [
        ("bull", "bear", "bear", FormalStage.STAGE_I),
        ("bull", "bull", "bear", FormalStage.STAGE_II),
        ("bull", "bull", "bull", FormalStage.STAGE_III),
        ("bear", "bull", "bull", FormalStage.STAGE_IV),
        ("bear", "bear", "bull", FormalStage.STAGE_V),
        ("bear", "bear", "bear", FormalStage.STAGE_VI),
    ],
)
def test_six_canonical_core_asset_combinations_map_to_formal_stages(
    bond: str,
    stock: str,
    commodity: str,
    expected: FormalStage,
) -> None:
    result = derive_formal_stage(
        bond=CoreAssetState(bond),
        stock=CoreAssetState(stock),
        commodity=CoreAssetState(commodity),
        last_confirmed_stage=FormalStage.STAGE_V,
    )

    assert result.current_stage is expected
    assert result.last_confirmed_stage is expected
    assert result.reason == "canonical_combination"


@pytest.mark.parametrize(
    ("bond", "stock", "commodity"),
    [("bull", "bear", "bull"), ("bear", "bull", "bear")],
)
def test_noncanonical_combinations_remain_unclassified(
    bond: str, stock: str, commodity: str
) -> None:
    result = derive_formal_stage(
        bond=CoreAssetState(bond),
        stock=CoreAssetState(stock),
        commodity=CoreAssetState(commodity),
        last_confirmed_stage=FormalStage.STAGE_II,
    )

    assert result.current_stage is None
    assert result.last_confirmed_stage is FormalStage.STAGE_II
    assert result.reason == "noncanonical_combination"


def test_any_unavailable_core_state_pauses_current_stage_without_defaulting() -> None:
    for unavailable_asset in range(3):
        states: list[CoreAssetState | None] = [
            CoreAssetState.BEAR,
            CoreAssetState.BEAR,
            CoreAssetState.BEAR,
        ]
        states[unavailable_asset] = None
        result = derive_formal_stage(
            bond=states[0],
            stock=states[1],
            commodity=states[2],
            last_confirmed_stage=FormalStage.STAGE_III,
        )

        assert result.current_stage is None
        assert result.last_confirmed_stage is FormalStage.STAGE_III
        assert result.reason == "core_state_unavailable"


def test_macro_evidence_cannot_change_a_formal_stage() -> None:
    stages = {
        derive_formal_stage(
            bond=CoreAssetState.BULL,
            stock=CoreAssetState.BULL,
            commodity=CoreAssetState.BEAR,
            last_confirmed_stage=None,
            contextual_evidence={
                "policy": policy,
                "inventory": inventory,
                "overheat": overheat,
            },
        ).current_stage
        for policy, inventory, overheat in itertools.product(
            ("easing", "tightening"),
            ("active_restocking", "active_destocking"),
            ("heating", "cooling"),
        )
    }

    assert stages == {FormalStage.STAGE_II}
