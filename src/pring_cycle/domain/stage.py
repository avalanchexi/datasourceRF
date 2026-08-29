from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pring_cycle.domain.types import CoreAssetState, FormalStage


@dataclass(frozen=True)
class StageResult:
    current_stage: FormalStage | None
    last_confirmed_stage: FormalStage | None
    reason: str


_FORMAL_STAGE_BY_PATTERN: Mapping[
    tuple[CoreAssetState, CoreAssetState, CoreAssetState], FormalStage
] = {
    (CoreAssetState.BULL, CoreAssetState.BEAR, CoreAssetState.BEAR): FormalStage.STAGE_I,
    (CoreAssetState.BULL, CoreAssetState.BULL, CoreAssetState.BEAR): FormalStage.STAGE_II,
    (CoreAssetState.BULL, CoreAssetState.BULL, CoreAssetState.BULL): FormalStage.STAGE_III,
    (CoreAssetState.BEAR, CoreAssetState.BULL, CoreAssetState.BULL): FormalStage.STAGE_IV,
    (CoreAssetState.BEAR, CoreAssetState.BEAR, CoreAssetState.BULL): FormalStage.STAGE_V,
    (CoreAssetState.BEAR, CoreAssetState.BEAR, CoreAssetState.BEAR): FormalStage.STAGE_VI,
}


def derive_formal_stage(
    *,
    bond: CoreAssetState | None,
    stock: CoreAssetState | None,
    commodity: CoreAssetState | None,
    last_confirmed_stage: FormalStage | None,
    contextual_evidence: Mapping[str, object] | None = None,
) -> StageResult:
    """Mechanically map three core price states; context is deliberately non-voting."""
    del contextual_evidence
    if bond is None or stock is None or commodity is None:
        return StageResult(None, last_confirmed_stage, "core_state_unavailable")
    current_stage = _FORMAL_STAGE_BY_PATTERN.get((bond, stock, commodity))
    if current_stage is None:
        return StageResult(None, last_confirmed_stage, "noncanonical_combination")
    return StageResult(current_stage, current_stage, "canonical_combination")
