from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pring_cycle.domain.types import CoreAssetState


@dataclass(frozen=True)
class BondConfirmation:
    core_state: CoreAssetState
    status: str
    yield_change_bp: float | None


def bond_yield_confirmation(
    core_state: CoreAssetState, *, yield_change_bp: float | None
) -> BondConfirmation:
    if yield_change_bp is None:
        status = "missing"
    else:
        expected_sign = -1 if core_state is CoreAssetState.BULL else 1
        observed_sign = 1 if yield_change_bp > 0 else -1 if yield_change_bp < 0 else 0
        status = "consistent" if observed_sign == expected_sign else "conflicted"
    return BondConfirmation(core_state, status, yield_change_bp)


@dataclass(frozen=True)
class FuturesSettlement:
    contract_month: str
    official_settlement: float
    observed_at: datetime
    roll_from_contract: str | None = None
    roll_adjustment_factor: float | None = None


@dataclass(frozen=True)
class ContinuousFuturesResult:
    returns: tuple[float, ...]
    contract_chain: tuple[str, ...]


def continuous_futures_returns(
    settlements: list[FuturesSettlement],
) -> ContinuousFuturesResult:
    ordered = sorted(settlements, key=lambda item: item.observed_at)
    if len(ordered) < 2 or any(item.official_settlement <= 0 for item in ordered):
        raise ValueError("insufficient_futures_settlements")
    returns: list[float] = []
    for previous, current in zip(ordered, ordered[1:], strict=False):
        adjusted_current = current.official_settlement
        if current.contract_month != previous.contract_month:
            if (
                current.roll_from_contract != previous.contract_month
                or current.roll_adjustment_factor is None
            ):
                raise ValueError("roll_metadata_missing")
            adjusted_current *= current.roll_adjustment_factor
        returns.append(adjusted_current / previous.official_settlement - 1.0)
    return ContinuousFuturesResult(
        returns=tuple(returns),
        contract_chain=tuple(item.contract_month for item in ordered),
    )
