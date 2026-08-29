from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MarketBar:
    metric_id: str
    source_code: str
    business_date: date
    close: float
    pre_close: float
    official_return: float
    unit: str
    certification_status: str


@dataclass(frozen=True)
class CoreSeriesValidation:
    metric_id: str
    status: str
    observations: int
    first_business_date: date
    last_business_date: date


CORE_SOURCE_CODES = {
    "CN_EQUITY_CORE_000985": "000985.CSI",
    "CN_BOND_CORE_000012": "000012.SH",
    "CN_COMMODITY_CORE_NHII": "NHII.NH",
}


def validate_core_market_bars(
    metric_id: str,
    bars: list[MarketBar],
    *,
    expected_business_dates: tuple[date, ...] | None = None,
) -> CoreSeriesValidation:
    expected_code = CORE_SOURCE_CODES.get(metric_id)
    if expected_code is None:
        raise ValueError("unknown_core_metric")
    if not bars:
        raise ValueError("core_series_missing")
    if any(item.metric_id != metric_id or item.source_code != expected_code for item in bars):
        raise ValueError("metric_identity_mismatch")
    if any(item.unit != "index_points" for item in bars):
        raise ValueError("metric_unit_mismatch")
    if any(item.certification_status != "certified" for item in bars):
        raise ValueError("source_not_certified")
    if any(item.close <= 0 or item.pre_close <= 0 for item in bars):
        raise ValueError("nonpositive_core_price")
    dates = [item.business_date for item in bars]
    if len(dates) != len(set(dates)):
        raise ValueError("duplicate_business_date")
    if dates != sorted(dates):
        raise ValueError("business_date_order_mismatch")
    if expected_business_dates is not None and tuple(dates) != expected_business_dates:
        raise ValueError("business_date_gap")
    return CoreSeriesValidation(metric_id, "validated", len(bars), dates[0], dates[-1])
