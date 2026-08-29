from __future__ import annotations

from datetime import date

import pytest

from pring_cycle.adapters import MarketBar, validate_core_market_bars


def bar(metric_id: str, source_code: str, unit: str = "index_points") -> MarketBar:
    return MarketBar(
        metric_id=metric_id,
        source_code=source_code,
        business_date=date(2026, 8, 28),
        close=141.0,
        pre_close=140.0,
        official_return=1.0 / 140.0,
        unit=unit,
        certification_status="certified",
    )


@pytest.mark.parametrize(
    ("metric_id", "source_code"),
    [
        ("CN_EQUITY_CORE_000985", "000985.CSI"),
        ("CN_BOND_CORE_000012", "000012.SH"),
        ("CN_COMMODITY_CORE_NHII", "NHII.NH"),
    ],
)
def test_core_adapters_bind_exact_metric_identity(metric_id: str, source_code: str) -> None:
    result = validate_core_market_bars(metric_id, [bar(metric_id, source_code)])

    assert result.status == "validated"
    assert result.metric_id == metric_id


@pytest.mark.parametrize(
    ("metric_id", "wrong_code"),
    [
        ("CN_EQUITY_CORE_000985", "000300.SH"),
        ("CN_BOND_CORE_000012", "CN10Y_ETF"),
        ("CN_COMMODITY_CORE_NHII", "NHCI.NH"),
    ],
)
def test_proxy_identity_cannot_clear_a_core_task(metric_id: str, wrong_code: str) -> None:
    with pytest.raises(ValueError, match="metric_identity_mismatch"):
        validate_core_market_bars(metric_id, [bar(metric_id, wrong_code)])


def test_etf_price_cannot_enter_a_yield_field() -> None:
    with pytest.raises(ValueError, match="metric_unit_mismatch"):
        validate_core_market_bars(
            "CN_BOND_CORE_000012",
            [bar("CN_BOND_CORE_000012", "000012.SH", unit="percent_yield")],
        )
