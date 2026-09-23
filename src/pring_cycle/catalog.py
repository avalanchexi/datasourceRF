from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILY_BY_METRIC

if TYPE_CHECKING:
    from pring_cycle.context_projection import ContextProjectionRules

METRIC_CATALOG_V0001 = "metric-catalog-v0001"
METRIC_CATALOG_VERSION = "metric-catalog-v0002"
METRIC_CATALOG_V0003 = "metric-catalog-v0003"
MARGIN_FINANCING_V0002 = "margin-financing-v0002"
_METRIC_CATALOG_V0003_SHA256 = (
    "594524ea647db3ab3824e4ea8ca4e1c7ce04fd53e9f29226b4a22364d10525fa"
)


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
    release_event_family: str
    release_rule: str
    release_timezone: str
    definition_version: str = METRIC_CATALOG_VERSION
    allowed_units: tuple[str, ...] = ()


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
    "CN_LPR_1Y_5Y": ("CHINAMONEY_LPR",),
    "CN_USDCNY_CENTRAL_PARITY": ("PBC_CFETS_USDCNY_CENTRAL_PARITY",),
    "CN_OMO_7D_RATE": ("PBC_OMO_NOTICE_HTML_V1",),
    "CN_OMO_7D_AMOUNT": ("PBC_OMO_NOTICE_HTML_V1",),
    "CN_RRR_EVENT": ("PBC_RRR_NOTICE_HTML_V1",),
    "CN_TOOL_LIQUIDITY_MONTHLY": ("PBC_TOOL_LIQUIDITY_HTML_V1",),
    "CN_CORE_CPI": ("NBS_CORE_CPI_HTML_V1",),
    "CN_INDUSTRIAL_VA": ("NBS_INDUSTRIAL_VA_HTML_V1",),
    "CN_INDUSTRIAL_FINANCE": ("NBS_INDUSTRIAL_FINANCE_HTML_V1",),
    "CN_FINISHED_GOODS_INVENTORY": ("NBS_INDUSTRIAL_FINANCE_HTML_V1",),
    "CN_INVENTORY_TURNOVER": ("NBS_INDUSTRIAL_FINANCE_HTML_V1",),
    "CN_CAPACITY_UTILIZATION": ("NBS_CAPACITY_UTILIZATION_HTML_V1",),
    "CN_SF_COMPONENTS": ("PBC_SOCIAL_FINANCING_HTML_V1",),
    "CN_LOAN_STRUCTURE": ("PBC_LOAN_STRUCTURE_HTML_V1",),
}

_SOURCE_CODES_V0001 = {
    "CN_EQUITY_CORE_000985": ("000985.CSI",),
    "CN_BOND_CORE_000012": ("000012.SH",),
    "CN_COMMODITY_CORE_NHII": ("NHII.NH",),
    "CN_COMMODITY_BROAD_NHCI": ("NHCI.NH",),
    "EIA_BRENT_RBRTE": ("RBRTE",),
    "EIA_WTI_RWTC": ("RWTC",),
    "UST10Y_NOMINAL_YIELD": ("us_tycr.y10",),
    "UST2Y_NOMINAL_YIELD": ("us_tycr.y2",),
    "CN_LPR_1Y_5Y": ("CHINAMONEY_LPR",),
}

_SOURCE_CANDIDATES = {
    "CN_LPR_1Y_5Y": (
        "https://www.chinamoney.com.cn/chinese/bklpr/",
    ),
    "CN_USDCNY_CENTRAL_PARITY": (
        "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html",
    ),
    "CN_OMO_7D_RATE": (
        "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html",
    ),
    "CN_OMO_7D_AMOUNT": (
        "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html",
    ),
    "CN_RRR_EVENT": ("https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/",),
    "CN_TOOL_LIQUIDITY_MONTHLY": (
        "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/",
    ),
    "CN_CORE_CPI": ("https://www.stats.gov.cn/sj/zxfb/",),
    "CN_INDUSTRIAL_VA": ("https://www.stats.gov.cn/sj/zxfbhjd/",),
    "CN_INDUSTRIAL_FINANCE": ("https://www.stats.gov.cn/sj/zxfbhjd/",),
    "CN_FINISHED_GOODS_INVENTORY": ("https://www.stats.gov.cn/sj/zxfbhjd/",),
    "CN_INVENTORY_TURNOVER": ("https://www.stats.gov.cn/sj/zxfbhjd/",),
    "CN_CAPACITY_UTILIZATION": ("https://www.stats.gov.cn/sj/zxfbhjd/",),
    "CN_SF_COMPONENTS": (
        "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html",
    ),
    "CN_LOAN_STRUCTURE": (
        "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html",
    ),
    "CN_SF_TOTAL": (
        "sf_month",
        "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html",
    ),
    "EIA_BRENT_RBRTE": (
        "https://api.eia.gov/v2/petroleum/pri/spt/data/",
    ),
    "EIA_WTI_RWTC": (
        "https://api.eia.gov/v2/petroleum/pri/spt/data/",
    ),
}

_CERTIFIED_SOURCES = {
    "CN_TRADE_CALENDAR",
    "CN_EQUITY_CORE_000985",
    "CN_BOND_CORE_000012",
    "CN_COMMODITY_CORE_NHII",
    "CN_LPR_1Y_5Y",
}

_V0002_OFFICIAL_FAMILY_BY_METRIC = {
    metric_id: family
    for metric_id, family in OFFICIAL_CONTEXT_FAMILY_BY_METRIC.items()
    if family
    not in {
        "nbs_gdp",
        "nbs_pmi",
        "nbs_ppi",
        "pbc_money",
    }
    and not (family == "nbs_core_cpi" and metric_id == "CN_CPI_HEADLINE")
}

_DERIVED_P1_V0003 = {
    "CN_DR007_POLICY_SPREAD",
    "CN_ORDER_INVENTORY_SPREAD",
    "CN_PRODUCTION_ORDER_SPREAD",
    "CN_CREDIT_IMPULSE",
}
_CERTIFIED_P2_V0003 = {
    "CN_GDP",
    "UST10Y_NOMINAL_YIELD",
    "UST2Y_NOMINAL_YIELD",
    "UST_2S10S_SPREAD",
}
_V0003_SOURCE_CODES = {
    "CN_EQ_CSI300": ("000300.SH",),
    "CN_EQ_CSI500": ("000905.SH",),
    "CN_EQ_CSI1000": ("000852.SH",),
    "CN_EQ_ADV_DEC": ("tushare:daily:breadth-v0001",),
    "CN_EQ_AD_RATIO": ("tushare:daily:breadth-v0001",),
    "CN_EQ_NEW_HIGH_LOW_120": ("tushare:daily:breadth-v0001",),
    "CN_EQ_ABOVE_MA120": ("tushare:daily:breadth-v0001",),
    "CN_EQ_ADV_AMOUNT_SHARE": ("tushare:daily:breadth-v0001",),
    "CN_MARGIN_BALANCE": ("tushare:margin",),
    "CN_INDEX_VALUATION": ("tushare:index_dailybasic",),
    "CN_BOND_FULL_PRICE_CNY030": ("000012CNY030.CSI",),
    "CN_BOND_10Y_930916": ("930916.CSI",),
    "CN_COMMODITY_EX_HOG_BASKET": ("tushare:fut_daily:ex-hog-basket-v0001",),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": (
        "tushare:fut_daily:ex-hog-basket-v0001",
    ),
}
_V0003_UNITS = {
    "CN_EQ_CSI300": ("index_points",),
    "CN_EQ_CSI500": ("index_points",),
    "CN_EQ_CSI1000": ("index_points",),
    "CN_EQ_ADV_DEC": ("count",),
    "CN_EQ_AD_RATIO": ("ratio",),
    "CN_EQ_NEW_HIGH_LOW_120": ("count",),
    "CN_EQ_ABOVE_MA120": ("percent",),
    "CN_EQ_ADV_AMOUNT_SHARE": ("percent",),
    "CN_MARGIN_BALANCE": ("hundred_million_cny",),
    "CN_INDEX_VALUATION": ("multiple", "percent"),
    "CN_BOND_FULL_PRICE_CNY030": ("index_points",),
    "CN_BOND_10Y_930916": ("index_points",),
    "CN_COMMODITY_EX_HOG_BASKET": ("index_points",),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": ("percentage_points",),
    "CN_INDUSTRIAL_VA": ("percent",),
}
_V0003_DIMENSIONS = {
    "CN_EQ_CSI300": ("source_code",),
    "CN_EQ_CSI500": ("source_code",),
    "CN_EQ_CSI1000": ("source_code",),
    "CN_EQ_ADV_DEC": ("measure", "universe"),
    "CN_EQ_AD_RATIO": ("measure", "universe"),
    "CN_EQ_NEW_HIGH_LOW_120": ("measure", "universe"),
    "CN_EQ_ABOVE_MA120": ("measure", "universe"),
    "CN_EQ_ADV_AMOUNT_SHARE": ("measure", "universe"),
    "CN_MARGIN_BALANCE": ("measure", "scope"),
    "CN_INDEX_VALUATION": ("index", "measure"),
    "CN_BOND_FULL_PRICE_CNY030": ("source_code",),
    "CN_BOND_10Y_930916": ("source_code",),
    "CN_COMMODITY_BROAD_NHCI": ("source_code",),
    "CN_COMMODITY_EX_HOG_BASKET": ("formula_version",),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": ("formula_version", "sleeve"),
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
                    source_candidates=_SOURCE_CANDIDATES.get(metric_id, source_codes),
                    certification_status=(
                        "certified"
                        if metric_id in _CERTIFIED_SOURCES
                        else "awaiting_source_certification"
                    ),
                    release_event_family=_release_event_family(metric_id),
                    release_rule=_release_rule(metric_id),
                    release_timezone=_release_timezone(metric_id),
                    allowed_units=_allowed_units(metric_id),
                )
            )
    return tuple(definitions)


def metric_catalog_v0001() -> tuple[MetricDefinition, ...]:
    """Return the frozen catalog embedded in the immutable model-v0001 manifest."""
    definitions: list[MetricDefinition] = []
    for priority, metric_ids in (("P0", _P0), ("P1", _P1), ("P2", _P2)):
        for metric_id in metric_ids:
            source_codes = _SOURCE_CODES_V0001.get(metric_id, (metric_id,))
            definitions.append(
                MetricDefinition(
                    metric_id=metric_id,
                    name_cn=_NAME_OVERRIDES.get(metric_id, metric_id),
                    priority=priority,
                    role=_role(metric_id),
                    unit=_unit_v0001(metric_id),
                    frequency=_frequency_v0001(metric_id),
                    dimensions=_dimensions_v0001(metric_id),
                    source_codes=source_codes,
                    source_candidates=(
                        ("https://www.chinamoney.com.cn/chinese/bklpr/",)
                        if metric_id == "CN_LPR_1Y_5Y"
                        else source_codes
                    ),
                    certification_status=(
                        "certified"
                        if metric_id in _CERTIFIED_SOURCES
                        else "awaiting_source_certification"
                    ),
                    release_event_family=(
                        "chinamoney_lpr"
                        if metric_id == "CN_LPR_1Y_5Y"
                        else metric_id.lower()
                    ),
                    release_rule=_release_rule(metric_id),
                    release_timezone=_release_timezone(metric_id),
                    definition_version=METRIC_CATALOG_V0001,
                    allowed_units=_allowed_units_v0001(metric_id),
                )
            )
    return tuple(definitions)


def metric_catalog_v0003() -> tuple[MetricDefinition, ...]:
    """Return the catalog produced by the accepted 120-day source certification."""
    definitions = []
    for definition in metric_catalog():
        certified = (
            definition.certification_status == "certified"
            or definition.priority == "P1"
            or definition.metric_id in _CERTIFIED_P2_V0003
        )
        allowed_units = _V0003_UNITS.get(definition.metric_id, definition.allowed_units)
        definitions.append(
            replace(
                definition,
                unit=allowed_units[0],
                dimensions=_V0003_DIMENSIONS.get(
                    definition.metric_id,
                    definition.dimensions,
                ),
                source_codes=_V0003_SOURCE_CODES.get(
                    definition.metric_id,
                    definition.source_codes,
                ),
                source_candidates=_V0003_SOURCE_CODES.get(
                    definition.metric_id,
                    definition.source_candidates,
                ),
                release_event_family=OFFICIAL_CONTEXT_FAMILY_BY_METRIC.get(
                    definition.metric_id,
                    definition.release_event_family,
                ),
                certification_status=(
                    "derived_from_certified_inputs"
                    if definition.metric_id in _DERIVED_P1_V0003
                    or definition.metric_id == "UST_2S10S_SPREAD"
                    else "certified"
                    if certified
                    else "awaiting_source_certification"
                ),
                definition_version=METRIC_CATALOG_V0003,
                allowed_units=allowed_units,
            )
        )
    catalog = tuple(definitions)
    digest = hashlib.sha256(
        json.dumps(
            [asdict(item) for item in catalog],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if digest != _METRIC_CATALOG_V0003_SHA256:
        raise ValueError("metric_catalog_v0003_canonical_hash_mismatch")
    return catalog


def metric_definition(
    metric_id: str,
    *,
    definition_version: str = METRIC_CATALOG_VERSION,
    database_path: Path | None = None,
) -> MetricDefinition:
    catalog = {
        METRIC_CATALOG_V0001: _BY_ID_V0001,
        METRIC_CATALOG_VERSION: _BY_ID,
        METRIC_CATALOG_V0003: _BY_ID_V0003,
        MARGIN_FINANCING_V0002: _MARGIN_FINANCING_V0002,
    }.get(definition_version)
    if catalog is None:
        if database_path is not None:
            from pring_cycle.catalog_registry import registered_metric_definition

            return registered_metric_definition(database_path, definition_version, metric_id)
        raise KeyError("unknown_metric_definition_version")
    try:
        return catalog[metric_id]
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
    if metric_id == "CN_USDCNY_CENTRAL_PARITY":
        return "cny_per_usd"
    if metric_id in {"CN_DR007", "CN_SHIBOR_ON_1W_3M", "CN_LPR_1Y_5Y"}:
        return "percent"
    if metric_id == "CN_CREDIT_IMPULSE":
        return "percentage_points"
    if metric_id in {"EIA_BRENT_RBRTE", "EIA_WTI_RWTC"}:
        return "usd_per_barrel"
    if metric_id in {
        "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
        "LBMA_GOLD_PRICE_PM_USD_OZT",
    }:
        return "usd_per_troy_ounce"
    if metric_id in {"CN_OMO_7D_AMOUNT", "CN_TOOL_LIQUIDITY_MONTHLY"}:
        return "hundred_million_cny"
    if metric_id == "CN_RRR_EVENT":
        return "percentage_points"
    if metric_id == "CN_INVENTORY_TURNOVER":
        return "days"
    if metric_id in {"CN_ORDER_INVENTORY_SPREAD", "CN_PRODUCTION_ORDER_SPREAD"}:
        return "diffusion_index_points"
    if metric_id.startswith("CN_PMI"):
        return "diffusion_index_points"
    if metric_id in {"CBOE_VIX_INDEX", "NASDAQ_SOX_INDEX"}:
        return "index_points"
    if metric_id in _P0[3:] or "INDEX" in metric_id or "NH" in metric_id:
        return "index_points"
    if any(token in metric_id for token in ("RATE", "YIELD", "CPI", "PPI", "PMI")):
        return "percent"
    if "SPREAD" in metric_id:
        return "basis_points"
    return "scalar"


def _unit_v0001(metric_id: str) -> str:
    if metric_id == "CN_LPR_1Y_5Y":
        return "percent"
    if metric_id == "CN_CREDIT_IMPULSE":
        return "percentage_points"
    if metric_id in {"EIA_BRENT_RBRTE", "EIA_WTI_RWTC"}:
        return "usd_per_barrel"
    if metric_id in {
        "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
        "LBMA_GOLD_PRICE_PM_USD_OZT",
    }:
        return "usd_per_troy_ounce"
    if metric_id in {"CN_OMO_7D_AMOUNT", "CN_TOOL_LIQUIDITY_MONTHLY"}:
        return "hundred_million_cny"
    if metric_id == "CN_RRR_EVENT":
        return "percentage_points"
    if metric_id == "CN_INVENTORY_TURNOVER":
        return "days"
    if metric_id.startswith("CN_PMI"):
        return "diffusion_index_points"
    if metric_id in {"CBOE_VIX_INDEX", "NASDAQ_SOX_INDEX"}:
        return "index_points"
    if metric_id in _P0[3:] or "INDEX" in metric_id or "NH" in metric_id:
        return "index_points"
    if any(token in metric_id for token in ("RATE", "YIELD", "CPI", "PPI", "PMI")):
        return "percent"
    if "SPREAD" in metric_id:
        return "basis_points"
    return "scalar"


def _allowed_units(metric_id: str) -> tuple[str, ...]:
    mixed = {
        "CN_RRR_EVENT": ("percentage_points", "percent", "hundred_million_cny"),
        "CN_M1_M2": ("hundred_million_cny", "percent"),
        "CN_SF_TOTAL": ("hundred_million_cny", "percent"),
        "CN_SF_COMPONENTS": ("hundred_million_cny", "percent"),
        "CN_LOAN_STRUCTURE": ("hundred_million_cny", "percent"),
        "CN_INDUSTRIAL_FINANCE": ("hundred_million_cny", "percent"),
        "CN_FINISHED_GOODS_INVENTORY": ("hundred_million_cny", "percent"),
        "CN_INVENTORY_TURNOVER": ("days", "percent"),
        "CN_CAPACITY_UTILIZATION": ("percent", "percentage_points"),
        "CN_GDP": ("hundred_million_cny", "percent"),
        "CN_FUTURES_WARRANTS": (
            "tonne",
            "kilogram",
            "sheet",
            "lot",
            "barrel",
        ),
    }
    return mixed.get(metric_id, (_unit(metric_id),))


def _allowed_units_v0001(metric_id: str) -> tuple[str, ...]:
    mixed = {
        "CN_M1_M2": ("hundred_million_cny", "percent"),
        "CN_SF_TOTAL": ("hundred_million_cny", "percent"),
        "CN_SF_COMPONENTS": ("hundred_million_cny", "percent"),
        "CN_LOAN_STRUCTURE": ("hundred_million_cny", "percent"),
        "CN_INDUSTRIAL_FINANCE": ("hundred_million_cny", "percent"),
        "CN_FINISHED_GOODS_INVENTORY": ("hundred_million_cny", "percent"),
        "CN_INVENTORY_TURNOVER": ("days", "percent"),
        "CN_CAPACITY_UTILIZATION": ("percent", "percentage_points"),
        "CN_GDP": ("hundred_million_cny", "percent"),
        "CN_FUTURES_WARRANTS": ("tonne", "kilogram", "sheet", "lot"),
    }
    return mixed.get(metric_id, (_unit_v0001(metric_id),))


def _frequency(metric_id: str) -> str:
    if metric_id.endswith("EVENT") or metric_id in {"CN_RELEASE_SCHEDULE"}:
        return "event"
    if (
        metric_id.startswith(("CN_PMI", "CN_CPI", "CN_CORE_CPI", "CN_PPI", "CN_SF"))
        or metric_id == "CN_LPR_1Y_5Y"
    ):
        return "monthly"
    if metric_id in {"CN_CAPACITY_UTILIZATION", "CN_GDP"}:
        return "quarterly"
    if metric_id in {
        "CN_M1_M2",
        "CN_LOAN_STRUCTURE",
        "CN_INDUSTRIAL_VA",
        "CN_INDUSTRIAL_FINANCE",
        "CN_FINISHED_GOODS_INVENTORY",
        "CN_INVENTORY_TURNOVER",
        "CN_TOOL_LIQUIDITY_MONTHLY",
        "CN_CREDIT_IMPULSE",
    }:
        return "monthly"
    return "daily"


def _frequency_v0001(metric_id: str) -> str:
    if metric_id.endswith("EVENT") or metric_id == "CN_RELEASE_SCHEDULE":
        return "event"
    if (
        metric_id.startswith(("CN_PMI", "CN_CPI", "CN_CORE_CPI", "CN_PPI", "CN_SF"))
        or metric_id == "CN_LPR_1Y_5Y"
    ):
        return "monthly"
    if metric_id in {"CN_CAPACITY_UTILIZATION", "CN_GDP"}:
        return "quarterly"
    return "daily"


def _dimensions(metric_id: str) -> tuple[str, ...]:
    if metric_id == "CN_USDCNY_CENTRAL_PARITY":
        return ("currency_pair", "quote_direction")
    if metric_id == "CN_OMO_7D_AMOUNT":
        return ("measure",)
    if metric_id == "CN_RRR_EVENT":
        return ("scope", "measure")
    if metric_id == "CN_TOOL_LIQUIDITY_MONTHLY":
        return ("tool", "measure")
    if metric_id == "CN_M1_M2":
        return ("aggregate", "measure")
    if metric_id == "CN_SF_TOTAL":
        return ("measure",)
    if metric_id == "CN_SF_COMPONENTS":
        return ("component", "measure")
    if metric_id == "CN_LOAN_STRUCTURE":
        return ("borrower", "tenor", "measure")
    if metric_id == "CN_SHIBOR_ON_1W_3M":
        return ("tenor",)
    if metric_id == "CN_LPR_1Y_5Y":
        return ("tenor",)
    if metric_id == "CN_FUTURES_WARRANTS":
        return ("symbol", "warehouse", "exchange", "measure")
    if metric_id == "CN_INDUSTRIAL_VA":
        return ("measure",)
    if metric_id == "CN_INDUSTRIAL_FINANCE":
        return ("item", "measure")
    if metric_id in {"CN_FINISHED_GOODS_INVENTORY", "CN_INVENTORY_TURNOVER"}:
        return ("measure",)
    if metric_id == "CN_CAPACITY_UTILIZATION":
        return ("industry", "measure")
    if metric_id == "CN_GDP":
        return ("aggregate", "measure")
    if metric_id.startswith("CN_PMI"):
        return ("series", "measure")
    if metric_id in {"CN_CPI_HEADLINE", "CN_CORE_CPI", "CN_PPI"}:
        return ("measure", "category")
    if metric_id.startswith("COMEX"):
        return ("contract_month", "measure", "roll_chain_version")
    if metric_id.startswith("LBMA"):
        return ("fixing", "measure")
    return ()


def _dimensions_v0001(metric_id: str) -> tuple[str, ...]:
    if metric_id == "CN_OMO_7D_AMOUNT":
        return ("measure",)
    if metric_id == "CN_RRR_EVENT":
        return ("scope", "measure")
    if metric_id == "CN_TOOL_LIQUIDITY_MONTHLY":
        return ("tool", "measure")
    if metric_id == "CN_M1_M2":
        return ("aggregate", "measure")
    if metric_id == "CN_SF_TOTAL":
        return ("measure",)
    if metric_id == "CN_SF_COMPONENTS":
        return ("component", "measure")
    if metric_id == "CN_LOAN_STRUCTURE":
        return ("borrower", "tenor", "measure")
    if metric_id in {"CN_SHIBOR_ON_1W_3M", "CN_LPR_1Y_5Y"}:
        return ("tenor",)
    if metric_id == "CN_FUTURES_WARRANTS":
        return ("symbol", "warehouse", "exchange")
    if metric_id == "CN_INDUSTRIAL_VA":
        return ("measure",)
    if metric_id == "CN_INDUSTRIAL_FINANCE":
        return ("item", "measure")
    if metric_id in {"CN_FINISHED_GOODS_INVENTORY", "CN_INVENTORY_TURNOVER"}:
        return ("measure",)
    if metric_id == "CN_CAPACITY_UTILIZATION":
        return ("industry", "measure")
    if metric_id == "CN_GDP":
        return ("aggregate", "measure")
    if metric_id.startswith("CN_PMI"):
        return ("series", "measure")
    if metric_id in {"CN_CPI_HEADLINE", "CN_CORE_CPI", "CN_PPI"}:
        return ("measure", "category")
    if metric_id.startswith("COMEX"):
        return ("contract_month", "measure", "roll_chain_version")
    if metric_id.startswith("LBMA"):
        return ("fixing", "measure")
    return ()


def _release_event_family(metric_id: str) -> str:
    if metric_id in _V0002_OFFICIAL_FAMILY_BY_METRIC:
        return _V0002_OFFICIAL_FAMILY_BY_METRIC[metric_id]
    if metric_id in {"EIA_BRENT_RBRTE", "EIA_WTI_RWTC"}:
        return "eia_petroleum_spot_prices"
    if metric_id == "CN_LPR_1Y_5Y":
        return "chinamoney_lpr"
    return metric_id.lower()


def _release_rule(metric_id: str) -> str:
    if metric_id == "CN_LPR_1Y_5Y":
        return "monthly_day_20_holiday_roll_0900_asia_shanghai"
    if metric_id == "CN_TRADE_CALENDAR":
        return "china_exchange_calendar"
    if metric_id in _P0[3:]:
        return "china_trading_day_source_schedule"
    return "source_schedule_required"


def _release_timezone(metric_id: str) -> str:
    if metric_id.startswith("CN_") or metric_id == "SOURCE_OBSERVED_AVAILABILITY":
        return "Asia/Shanghai"
    return "source_local_timezone"


_NAME_OVERRIDES = {
    "CN_EQUITY_CORE_000985": "中证全指",
    "CN_BOND_CORE_000012": "上证国债指数",
    "CN_COMMODITY_CORE_NHII": "南华工业品指数",
    "CN_CORE_CPI": "核心 CPI",
    "CN_CPI_HEADLINE": "居民消费价格",
    "CN_PPI": "工业生产者价格",
}

_BY_ID = {item.metric_id: item for item in metric_catalog()}
_BY_ID_V0001 = {item.metric_id: item for item in metric_catalog_v0001()}
_BY_ID_V0003 = {item.metric_id: item for item in metric_catalog_v0003()}
_MARGIN_FINANCING_V0002 = {
    "CN_MARGIN_BALANCE": replace(
        _BY_ID_V0003["CN_MARGIN_BALANCE"],
        definition_version=MARGIN_FINANCING_V0002,
        certification_status="awaiting_source_certification",
        source_codes=("tushare:margin:SSE+SZSE+BSE:v0002",),
        source_candidates=("tushare:margin:SSE+SZSE+BSE:v0002",),
        release_rule="publication_unknown_until_official_evidence",
    )
}


P2_IDENTITY_MIGRATION: dict[str, Any] = {
    "version": "p2-official-identity-v0001",
    "replacements": {"CN_USDCNH_FXCM": "CN_USDCNH_TMA_SPOT_RATE"},
    "removed_metric_ids": [
        "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
        "LBMA_GOLD_PRICE_PM_USD_OZT",
    ],
    "history_policy": "retain_separate",
}
P2_ECB_IDENTITY_MIGRATION: dict[str, Any] = {
    **P2_IDENTITY_MIGRATION,
    "version": "p2-ecb-reference-cross-v0001",
    "replacements": {"CN_USDCNH_FXCM": "CN_USDCNY_ECB_REFERENCE_CROSS"},
}
# Beijing refuses every public endpoint this project can reach, so the all-exchange scope can
# never be delivered. The approved disposition renames the metric to what it does measure
# rather than demoting it or subtracting a residual; the old identity keeps its history.
# ``removed_metric_ids`` and ``history_policy`` are not read by the branch below: they are
# part of the declaration the manifest must match exactly, which is what makes an approved
# migration distinguishable from an arbitrary catalog edit.
MARGIN_SCOPE_MIGRATION: dict[str, Any] = {
    "version": "margin-two-exchange-scope-v0001",
    "replacements": {"CN_MARGIN_BALANCE": "CN_MARGIN_BALANCE_SSE_SZSE"},
    "removed_metric_ids": [],
    "history_policy": "retain_separate",
}
CNY030_OPTIONAL_MIGRATION: dict[str, Any] = {
    **P2_ECB_IDENTITY_MIGRATION,
    "version": "cny030-optional-ecb-margin-v0001",
    "replacements": {
        **P2_ECB_IDENTITY_MIGRATION["replacements"],
        **MARGIN_SCOPE_MIGRATION["replacements"],
    },
    "priority_changes": {"CN_BOND_FULL_PRICE_CNY030": {"from": "P1", "to": "P2"}},
}


def migrated_catalog(manifest: dict[str, Any]) -> dict[str, MetricDefinition]:
    """The catalog a model manifest must declare, after its approved identity migration."""
    expected = {item.metric_id: item for item in metric_catalog()}
    if "metric_identity_migration" not in manifest:
        return expected
    migration = manifest["metric_identity_migration"]
    if migration == CNY030_OPTIONAL_MIGRATION:
        # ADR-0020 composes only these approved dispositions. Keep the old declarations
        # valid for historical candidates without opening an arbitrary migration pipeline.
        expected = migrated_catalog(
            {**manifest, "metric_identity_migration": P2_ECB_IDENTITY_MIGRATION}
        )
        margin = migrated_catalog({**manifest, "metric_identity_migration": MARGIN_SCOPE_MIGRATION})
        del expected["CN_MARGIN_BALANCE"]
        expected["CN_MARGIN_BALANCE_SSE_SZSE"] = margin["CN_MARGIN_BALANCE_SSE_SZSE"]
        # Preserve the frozen CNY030 definition, not the earlier sparse catalog stub.
        previous = next(
            item for item in metric_catalog_v0003() if item.metric_id == "CN_BOND_FULL_PRICE_CNY030"
        )
        expected[previous.metric_id] = replace(
            previous, priority="P2", certification_status="awaiting_source_certification"
        )
        return expected
    if migration not in (
        P2_IDENTITY_MIGRATION,
        P2_ECB_IDENTITY_MIGRATION,
        MARGIN_SCOPE_MIGRATION,
    ):
        raise ValueError("certification_identity_migration_unsupported")
    if migration == MARGIN_SCOPE_MIGRATION:
        previous_margin = expected.pop("CN_MARGIN_BALANCE")
        # The reviewed catalog states margin far more fully than the builtin stub does
        # (its own unit, dimensions and candidates), and those carry across a rename
        # untouched. Only the fields that say *which delivery this is* are dictated here,
        # so the drift gate compares identity rather than re-litigating the whole shape.
        declared = next(
            (
                item
                for item in manifest.get("metric_definitions", ())
                if item.get("metric_id") == "CN_MARGIN_BALANCE_SSE_SZSE"
            ),
            None,
        )
        carried: dict[str, Any] = {}
        if declared is not None:
            carried = {
                field: tuple(declared[field])
                if isinstance(declared[field], list)
                else declared[field]
                for field in ("unit", "allowed_units", "dimensions", "source_candidates")
                if field in declared
            }
        expected["CN_MARGIN_BALANCE_SSE_SZSE"] = replace(
            previous_margin,
            metric_id="CN_MARGIN_BALANCE_SSE_SZSE",
            name_cn="沪深两所融资余额与买入额",
            source_codes=("SSE_SZSE_MARGIN_BALANCE",),
            release_event_family="cn_margin_balance_sse_szse",
            **carried,
        )
        return expected
    for metric_id in P2_IDENTITY_MIGRATION["removed_metric_ids"]:
        del expected[metric_id]
    previous = expected.pop("CN_USDCNH_FXCM")
    if migration == P2_ECB_IDENTITY_MIGRATION:
        expected["CN_USDCNY_ECB_REFERENCE_CROSS"] = replace(
            previous,
            metric_id="CN_USDCNY_ECB_REFERENCE_CROSS",
            name_cn="ECB 美元兑人民币参考交叉汇率",
            unit="cny_per_usd",
            allowed_units=("cny_per_usd",),
            dimensions=(),
            source_codes=("ECB_EUR_REFERENCE_CNY_USD_CROSS_V0001",),
            source_candidates=(
                "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
                "euro_reference_exchange_rates/html/index.en.html",
            ),
            frequency="daily",
            release_event_family="ecb_eur_reference_cross",
            release_timezone="Europe/Berlin",
        )
        return expected
    expected["CN_USDCNH_TMA_SPOT_RATE"] = replace(
        previous,
        metric_id="CN_USDCNH_TMA_SPOT_RATE",
        name_cn="TMA 美元兑离岸人民币即期参考汇率",
        unit="cnh_per_usd",
        allowed_units=("cnh_per_usd",),
        dimensions=(),
        source_codes=("TMA_USD_CNY_HK_SPOT_RATE",),
        source_candidates=(),
        frequency="daily",
        release_event_family="tma_usd_cny_hk_spot_rate",
        release_timezone="Asia/Hong_Kong",
    )
    return expected


_CORE_METRICS = {
    "stock": "CN_EQUITY_CORE_000985",
    "bond": "CN_BOND_CORE_000012",
    "commodity": "CN_COMMODITY_CORE_NHII",
}
_REQUIRED_FORMULAS = {
    "credit_impulse",
    "dr007_policy_spread",
    "loan_monthly_change",
    "omo_net_injection",
    "order_inventory_spread",
    "production_order_spread",
    "real_inventory_approximation",
    "ust_2s10s_spread",
}
_IDENTITY_FIELDS = (
    "name_cn",
    "unit",
    "allowed_units",
    "dimensions",
    "source_codes",
    "source_candidates",
    "frequency",
    "release_event_family",
    "release_rule",
    "release_timezone",
)


def validate_model_catalog(manifest: dict[str, Any]) -> ContextProjectionRules:
    """Check a model manifest's catalog, formulas and trend rules against the approved shape.

    Returns the manifest's ``ContextProjectionRules``. Structure only: whether a source is
    certified is not a catalog question.
    """
    from pring_cycle.catalog_registry import SYSTEM_TARGET_CUTOFF_VERSION
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.models import certified_model_v0001_manifest

    rules = ContextProjectionRules.from_manifest(manifest)
    expected = migrated_catalog(manifest)
    definitions = {item["metric_id"]: item for item in manifest["metric_definitions"]}
    if set(definitions) != set(expected):
        raise ValueError("certification_catalog_scope_mismatch")
    optional_cny030 = manifest.get("metric_identity_migration") == CNY030_OPTIONAL_MIGRATION
    for definition in rules.metric_definitions:
        baseline = expected[definition.metric_id]
        if (
            optional_cny030
            and baseline.role == "core_barometer"
            and definition.source_codes != baseline.source_codes
        ):
            raise ValueError(f"certification_core_source_identity_mismatch:{definition.metric_id}")
        if (
            optional_cny030
            and definition.metric_id == "CN_BOND_FULL_PRICE_CNY030"
            and definition != replace(baseline, definition_version=definition.definition_version)
        ):
            raise ValueError("certification_cny030_definition_mismatch")
        identity = {
            "CN_USDCNH_TMA_SPOT_RATE": "tma",
            "CN_USDCNY_ECB_REFERENCE_CROSS": "ecb",
            "CN_MARGIN_BALANCE_SSE_SZSE": "margin_scope",
        }.get(definition.metric_id)
        if identity is not None and any(
            getattr(definition, field) != getattr(baseline, field) for field in _IDENTITY_FIELDS
        ):
            raise ValueError(f"certification_{identity}_identity_mismatch")
        if set(definitions[definition.metric_id]) != set(asdict(definition)):
            raise ValueError(f"certification_definition_fields_unsupported:{definition.metric_id}")
        if definition.frequency not in {"daily", "monthly", "quarterly", "event"}:
            raise ValueError(f"certification_frequency_unsupported:{definition.metric_id}")
        if (definition.priority, definition.role) != (baseline.priority, baseline.role):
            raise ValueError(f"certification_metric_role_mismatch:{definition.metric_id}")
    if manifest.get("core_metrics") != _CORE_METRICS:
        raise ValueError("certification_core_roles_invalid")
    _validate_trend_rules(manifest.get("trend_rules"))
    if manifest.get("stage_mapping") != certified_model_v0001_manifest()["stage_mapping"]:
        raise ValueError("certification_stage_mapping_invalid")
    if manifest.get("point_in_time_rule_version") not in {
        "public-cutoff-v0002",
        SYSTEM_TARGET_CUTOFF_VERSION,
    }:
        raise ValueError("certification_rule_version_unsupported:point_in_time_rule_version")
    versions = {
        "selection_rule_version": "selection-v0001",
        "visible_context_window_rule_version": "exact-core-calendar-120-v0001",
    }
    for name, supported in versions.items():
        if manifest.get(name) != supported:
            raise ValueError(f"certification_rule_version_unsupported:{name}")
    if (
        manifest.get("visible_evidence_window_trading_days") != 120
        or manifest.get("hidden_preheat_policy") != "minimum_formula_inputs_only"
    ):
        raise ValueError("certification_evidence_window_invalid")
    if set(rules.formula_versions) != _REQUIRED_FORMULAS:
        raise ValueError("certification_formulas_incomplete")
    return rules


def _validate_trend_rules(trend: object) -> None:
    if (
        not isinstance(trend, dict)
        or trend.get("candidate_duration_rule_version") != "candidate-duration-v0002"
    ):
        raise ValueError("certification_candidate_duration_rule_required")
    if trend.get("rule_version") != "trend-v0001":
        raise ValueError("certification_trend_version_unsupported")
    for name in (
        "window_days",
        "slope_days",
        "volatility_days",
        "persistence_days",
        "candidate_window_days",
    ):
        value = trend.get(name)
        if type(value) is not int or value < 1:
            raise ValueError(f"certification_trend_parameter_invalid:{name}")
    noise = trend.get("noise_multiplier")
    if (
        isinstance(noise, bool)
        or not isinstance(noise, (int, float))
        or not math.isfinite(noise)
        or noise <= 0
    ):
        raise ValueError("certification_trend_parameter_invalid:noise_multiplier")
    if trend["window_days"] != 120:
        raise ValueError("certification_trend_window_invalid")
    if trend["volatility_days"] >= trend["window_days"] + trend["slope_days"]:
        raise ValueError("certification_trend_volatility_window_invalid")
