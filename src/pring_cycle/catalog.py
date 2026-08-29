from __future__ import annotations

from dataclasses import dataclass

METRIC_CATALOG_VERSION = "metric-catalog-v0001"


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    name_cn: str
    priority: str
    role: str
    unit: str
    frequency: str
    dimensions: tuple[str, ...]
    source_codes: tuple[str, ...]
    source_candidates: tuple[str, ...]
    certification_status: str
    definition_version: str = METRIC_CATALOG_VERSION


_P0 = (
    "CN_TRADE_CALENDAR",
    "CN_RELEASE_SCHEDULE",
    "SOURCE_OBSERVED_AVAILABILITY",
    "CN_EQUITY_CORE_000985",
    "CN_BOND_CORE_000012",
    "CN_COMMODITY_CORE_NHII",
)
_P1 = (
    "CN_EQ_CSI300",
    "CN_EQ_CSI500",
    "CN_EQ_CSI1000",
    "CN_EQ_ADV_DEC",
    "CN_EQ_AD_RATIO",
    "CN_EQ_NEW_HIGH_LOW_120",
    "CN_EQ_ABOVE_MA120",
    "CN_EQ_ADV_AMOUNT_SHARE",
    "CN_MARGIN_BALANCE",
    "CN_INDEX_VALUATION",
    "CN_BOND_FULL_PRICE_CNY030",
    "CN_BOND_10Y_930916",
    "CN_DR007",
    "CN_OMO_7D_RATE",
    "CN_OMO_7D_AMOUNT",
    "CN_DR007_POLICY_SPREAD",
    "CN_SHIBOR_ON_1W_3M",
    "CN_LPR_1Y_5Y",
    "CN_RRR_EVENT",
    "CN_TOOL_LIQUIDITY_MONTHLY",
    "CN_COMMODITY_BROAD_NHCI",
    "CN_COMMODITY_EX_HOG_BASKET",
    "CN_COMMODITY_SLEEVE_CONTRIBUTION",
    "CN_FUTURES_WARRANTS",
    "CN_PMI_ACTIVITY",
    "CN_PMI_INVENTORY",
    "CN_PMI_PRICES",
    "CN_ORDER_INVENTORY_SPREAD",
    "CN_PRODUCTION_ORDER_SPREAD",
    "CN_CPI_HEADLINE",
    "CN_CORE_CPI",
    "CN_PPI",
    "CN_INDUSTRIAL_VA",
    "CN_INDUSTRIAL_FINANCE",
    "CN_FINISHED_GOODS_INVENTORY",
    "CN_INVENTORY_TURNOVER",
    "CN_CAPACITY_UTILIZATION",
    "CN_M1_M2",
    "CN_SF_TOTAL",
    "CN_SF_COMPONENTS",
    "CN_LOAN_STRUCTURE",
    "CN_CREDIT_IMPULSE",
)
_P2 = (
    "CN_GDP",
    "CN_USDCNY_CENTRAL_PARITY",
    "CN_USDCNH_FXCM",
    "CN_USDCNY_CLOSE_1630",
    "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
    "LBMA_GOLD_PRICE_PM_USD_OZT",
    "EIA_BRENT_RBRTE",
    "EIA_WTI_RWTC",
    "UST10Y_NOMINAL_YIELD",
    "UST2Y_NOMINAL_YIELD",
    "UST_2S10S_SPREAD",
    "CBOE_VIX_INDEX",
    "NASDAQ_SOX_INDEX",
)

_SOURCE_CODES = {
    "CN_EQUITY_CORE_000985": ("000985.CSI",),
    "CN_BOND_CORE_000012": ("000012.SH",),
    "CN_COMMODITY_CORE_NHII": ("NHII.NH",),
    "CN_COMMODITY_BROAD_NHCI": ("NHCI.NH",),
    "EIA_BRENT_RBRTE": ("RBRTE",),
    "EIA_WTI_RWTC": ("RWTC",),
    "UST10Y_NOMINAL_YIELD": ("us_tycr.y10",),
    "UST2Y_NOMINAL_YIELD": ("us_tycr.y2",),
}

_AWAITING_CERTIFICATION = {
    "CN_USDCNY_CLOSE_1630",
    "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
    "LBMA_GOLD_PRICE_PM_USD_OZT",
    "CBOE_VIX_INDEX",
    "NASDAQ_SOX_INDEX",
}


def metric_catalog() -> tuple[MetricDefinition, ...]:
    definitions: list[MetricDefinition] = []
    for priority, metric_ids in (("P0", _P0), ("P1", _P1), ("P2", _P2)):
        for metric_id in metric_ids:
            source_codes = _SOURCE_CODES.get(metric_id, (metric_id,))
            definitions.append(
                MetricDefinition(
                    metric_id=metric_id,
                    name_cn=_NAME_OVERRIDES.get(metric_id, metric_id),
                    priority=priority,
                    role=_role(metric_id),
                    unit=_unit(metric_id),
                    frequency=_frequency(metric_id),
                    dimensions=_dimensions(metric_id),
                    source_codes=source_codes,
                    source_candidates=source_codes,
                    certification_status=(
                        "awaiting_source_certification"
                        if metric_id in _AWAITING_CERTIFICATION
                        else "certified"
                    ),
                )
            )
    return tuple(definitions)


def metric_definition(metric_id: str) -> MetricDefinition:
    try:
        return _BY_ID[metric_id]
    except KeyError as error:
        raise KeyError("unknown_metric_id") from error


def _role(metric_id: str) -> str:
    if "CORE" in metric_id and metric_id != "CN_CORE_CPI":
        return "core_barometer"
    if metric_id.startswith(("COMEX", "LBMA", "EIA", "UST", "CBOE", "NASDAQ")):
        return "international_context"
    if any(token in metric_id for token in ("OMO", "RRR", "DR007", "SHIBOR")):
        return "policy_transmission"
    if any(token in metric_id for token in ("M1_M2", "SF_", "LOAN", "CREDIT")):
        return "credit_response"
    if any(token in metric_id for token in ("INVENTORY", "WARRANT")):
        return "signature_card"
    return "macro_confirmation"


def _unit(metric_id: str) -> str:
    if metric_id in _P0[3:] or "INDEX" in metric_id or "NH" in metric_id:
        return "index_points"
    if any(token in metric_id for token in ("RATE", "YIELD", "CPI", "PPI", "PMI")):
        return "percent"
    if "SPREAD" in metric_id:
        return "basis_points"
    return "scalar"


def _frequency(metric_id: str) -> str:
    if metric_id.endswith("EVENT") or metric_id in {"CN_RELEASE_SCHEDULE"}:
        return "event"
    if metric_id.startswith(("CN_PMI", "CN_CPI", "CN_CORE_CPI", "CN_PPI", "CN_SF")):
        return "monthly"
    if metric_id in {"CN_CAPACITY_UTILIZATION", "CN_GDP"}:
        return "quarterly"
    return "daily"


def _dimensions(metric_id: str) -> tuple[str, ...]:
    if metric_id == "CN_SF_COMPONENTS":
        return ("component", "measure")
    if metric_id == "CN_LOAN_STRUCTURE":
        return ("borrower", "tenor", "measure")
    if metric_id == "CN_SHIBOR_ON_1W_3M":
        return ("tenor",)
    if metric_id == "CN_LPR_1Y_5Y":
        return ("tenor",)
    if metric_id == "CN_FUTURES_WARRANTS":
        return ("symbol", "warehouse", "exchange")
    if metric_id.startswith("CN_PMI"):
        return ("series", "measure")
    if metric_id in {"CN_CPI_HEADLINE", "CN_CORE_CPI", "CN_PPI"}:
        return ("measure", "category")
    if metric_id.startswith(("COMEX", "LBMA")):
        return ("contract_or_fixing",)
    return ()


_NAME_OVERRIDES = {
    "CN_EQUITY_CORE_000985": "中证全指",
    "CN_BOND_CORE_000012": "上证国债指数",
    "CN_COMMODITY_CORE_NHII": "南华工业品指数",
    "CN_CORE_CPI": "核心 CPI",
    "CN_CPI_HEADLINE": "居民消费价格",
    "CN_PPI": "工业生产者价格",
}

_BY_ID = {item.metric_id: item for item in metric_catalog()}
