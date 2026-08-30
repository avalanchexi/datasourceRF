from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from pring_cycle.source_adapters import TushareCoreAdapter


def transport(payloads: list[dict[str, Any]]) -> Any:
    def call(payload: dict[str, Any]) -> dict[str, Any]:
        payloads.append(payload)
        if payload["api_name"] == "trade_cal":
            return {
                "code": 0,
                "data": {
                    "fields": ["cal_date", "is_open"],
                    "items": [["20260827", 1], ["20260828", 1]],
                },
            }
        pct_chg = 0.01 if payload["api_name"] == "fut_index_daily" else 1.0
        return {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                "items": [
                    [payload["params"]["ts_code"], "20260828", 101.0, 100.0, pct_chg],
                    [payload["params"]["ts_code"], "20260827", 100.0, 99.0, pct_chg],
                ],
            },
        }

    return call


@pytest.mark.parametrize(
    ("metric_id", "api_name", "source_code"),
    [
        ("CN_EQUITY_CORE_000985", "index_daily", "000985.CSI"),
        ("CN_BOND_CORE_000012", "index_daily", "000012.SH"),
        ("CN_COMMODITY_CORE_NHII", "fut_index_daily", "NHII.NH"),
    ],
)
def test_tushare_core_adapter_binds_the_frozen_api_identity(
    metric_id: str,
    api_name: str,
    source_code: str,
) -> None:
    payloads: list[dict[str, Any]] = []
    adapter = TushareCoreAdapter("fixture-token", transport=transport(payloads))
    expected = adapter.trading_days(date(2026, 8, 27), date(2026, 8, 28))

    smoke = adapter.smoke(
        metric_id,
        start=date(2026, 8, 27),
        end=date(2026, 8, 28),
        expected_business_dates=expected,
    )

    assert smoke.api_name == api_name
    assert smoke.source_code == source_code
    assert smoke.observations == 2
    assert payloads[-1]["params"]["ts_code"] == source_code
    assert "fixture-token" not in repr(smoke)


@pytest.mark.parametrize(
    ("metric_id", "expected_return"),
    [
        ("CN_EQUITY_CORE_000985", 0.01),
        ("CN_BOND_CORE_000012", 0.01),
        ("CN_COMMODITY_CORE_NHII", 0.01),
    ],
)
def test_tushare_core_adapter_normalizes_endpoint_specific_return_units(
    metric_id: str,
    expected_return: float,
) -> None:
    adapter = TushareCoreAdapter("fixture-token", transport=transport([]))

    bars = adapter.core_bars(
        metric_id,
        start=date(2026, 8, 27),
        end=date(2026, 8, 28),
    )

    assert {bar.official_return for bar in bars} == {expected_return}


def test_calendar_gap_fails_the_core_source_smoke() -> None:
    adapter = TushareCoreAdapter("fixture-token", transport=transport([]))

    with pytest.raises(ValueError, match="business_date_gap"):
        adapter.smoke(
            "CN_EQUITY_CORE_000985",
            start=date(2026, 8, 27),
            end=date(2026, 8, 28),
            expected_business_dates=(date(2026, 8, 26), date(2026, 8, 27), date(2026, 8, 28)),
        )
