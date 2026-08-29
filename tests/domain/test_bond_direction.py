from __future__ import annotations

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.market import bond_yield_confirmation


def test_bond_price_direction_is_primary_and_yield_is_inverse_confirmation() -> None:
    consistent = bond_yield_confirmation(CoreAssetState.BULL, yield_change_bp=-12.0)
    conflict = bond_yield_confirmation(CoreAssetState.BULL, yield_change_bp=8.0)
    missing = bond_yield_confirmation(CoreAssetState.BEAR, yield_change_bp=None)

    assert consistent.core_state is CoreAssetState.BULL
    assert consistent.status == "consistent"
    assert conflict.core_state is CoreAssetState.BULL
    assert conflict.status == "conflicted"
    assert missing.core_state is CoreAssetState.BEAR
    assert missing.status == "missing"
