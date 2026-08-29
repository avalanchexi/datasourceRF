from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pring_cycle.domain.market import FuturesSettlement, continuous_futures_returns


def test_known_contract_roll_removes_the_non_economic_price_gap() -> None:
    settlements = [
        FuturesSettlement("GCZ26", 100.0, datetime(2026, 8, 27, tzinfo=UTC)),
        FuturesSettlement(
            "GCG27",
            110.0,
            datetime(2026, 8, 28, tzinfo=UTC),
            roll_from_contract="GCZ26",
            roll_adjustment_factor=100.0 / 110.0,
        ),
    ]

    result = continuous_futures_returns(settlements)

    assert result.returns == (0.0,)
    assert result.contract_chain == ("GCZ26", "GCG27")


def test_contract_switch_without_roll_metadata_is_rejected() -> None:
    settlements = [
        FuturesSettlement("GCZ26", 100.0, datetime(2026, 8, 27, tzinfo=UTC)),
        FuturesSettlement("GCG27", 110.0, datetime(2026, 8, 28, tzinfo=UTC)),
    ]

    with pytest.raises(ValueError, match="roll_metadata_missing"):
        continuous_futures_returns(settlements)
