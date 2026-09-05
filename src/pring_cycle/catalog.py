from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILY_BY_METRIC

METRIC_CATALOG_V0001 = "metric-catalog-v0001"
METRIC_CATALOG_VERSION = "metric-catalog-v0002"
METRIC_CATALOG_V0003 = "metric-catalog-v0003"
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
) -> MetricDefinition:
    catalog = {
        METRIC_CATALOG_V0001: _BY_ID_V0001,
        METRIC_CATALOG_VERSION: _BY_ID,
        METRIC_CATALOG_V0003: _BY_ID_V0003,
    }.get(definition_version)
    if catalog is None:
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
