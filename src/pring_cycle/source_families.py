from __future__ import annotations

from dataclasses import dataclass

# Opt-in delivery contract, bound into a newly reviewed immutable metric definition.
# This identifier does not itself confer source certification.
TUSHARE_PPI_SOURCE_CODE = "tushare:cn_ppi:official-sampled-v0001"
TUSHARE_CPI_SOURCE_CODE = "tushare:cn_cpi:official-sampled-v0001"
TUSHARE_PMI_SOURCE_CODE = "tushare:cn_pmi:official-sampled-v0001"
TUSHARE_MONEY_SOURCE_CODE = "tushare:cn_m:official-sampled-v0001"
TUSHARE_SF_TOTAL_SOURCE_CODE = "tushare:sf_month:official-sampled-v0001"
TUSHARE_SF_TOTAL_FIELDS = (
    ("inc_cumval", "ytd_increment", 1.0, "year_to_month"),
    ("stk_endval", "stock_end", 10_000.0, "month"),
)
TUSHARE_MONEY_FIELDS = tuple(
    (
        aggregate if measure == "balance" else f"{aggregate}_{measure}",
        aggregate,
        measure,
        "hundred_million_cny" if measure == "balance" else "percent",
    )
    for aggregate in ("m1", "m2")
    for measure in ("balance", "yoy")
)
TUSHARE_PMI_FIELDS = (
    ("pmi010000", "CN_PMI_ACTIVITY", "manufacturing"),
    ("pmi010400", "CN_PMI_ACTIVITY", "production"),
    ("pmi010500", "CN_PMI_ACTIVITY", "new_orders"),
    ("pmi010700", "CN_PMI_INVENTORY", "raw_materials"),
    ("pmi011100", "CN_PMI_ACTIVITY", "purchase_volume"),
    ("pmi011200", "CN_PMI_PRICES", "purchase_prices"),
    ("pmi011300", "CN_PMI_PRICES", "output_prices"),
    ("pmi011400", "CN_PMI_INVENTORY", "finished_goods"),
)
TUSHARE_CPI_FIELDS = (
    ("nt_yoy", "yoy"),
    ("nt_mom", "mom"),
    ("nt_accu", "cumulative_average_yoy"),
)
TUSHARE_PPI_FIELDS = tuple(
    (f"ppi{suffix}_{field}", category, measure)
    for suffix, category in (
        ("", "headline"),
        ("_mp", "means_of_production"),
        ("_cg", "consumer_goods"),
    )
    for field, measure in (("yoy", "yoy"), ("mom", "mom"), ("accu", "cumulative_average_yoy"))
)


@dataclass(frozen=True)
class OfficialContextFamily:
    provider: str
    host: str
    metric_ids: tuple[str, ...]
    required_p1_rehearsal: bool = True


OFFICIAL_CONTEXT_FAMILIES = {
    "nbs_core_cpi": OfficialContextFamily(
        "国家统计局",
        "www.stats.gov.cn",
        ("CN_CPI_HEADLINE", "CN_CORE_CPI"),
    ),
    "nbs_pmi": OfficialContextFamily(
        "国家统计局",
        "www.stats.gov.cn",
        ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
    ),
    "nbs_ppi": OfficialContextFamily("国家统计局", "www.stats.gov.cn", ("CN_PPI",)),
    "nbs_gdp": OfficialContextFamily("国家统计局", "www.stats.gov.cn", ("CN_GDP",)),
    "nbs_industrial_value_added": OfficialContextFamily(
        "国家统计局", "www.stats.gov.cn", ("CN_INDUSTRIAL_VA",)
    ),
    "nbs_industrial_finance": OfficialContextFamily(
        "国家统计局",
        "www.stats.gov.cn",
        (
            "CN_INDUSTRIAL_FINANCE",
            "CN_FINISHED_GOODS_INVENTORY",
            "CN_INVENTORY_TURNOVER",
        ),
    ),
    "nbs_capacity_utilization": OfficialContextFamily(
        "国家统计局", "www.stats.gov.cn", ("CN_CAPACITY_UTILIZATION",)
    ),
    "pbc_omo_notice": OfficialContextFamily(
        "中国人民银行",
        "www.pbc.gov.cn",
        ("CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT"),
    ),
    "pbc_rrr_notice": OfficialContextFamily("中国人民银行", "www.pbc.gov.cn", ("CN_RRR_EVENT",)),
    "pbc_tool_liquidity_monthly": OfficialContextFamily(
        "中国人民银行", "www.pbc.gov.cn", ("CN_TOOL_LIQUIDITY_MONTHLY",)
    ),
    "pbc_social_financing": OfficialContextFamily(
        "中国人民银行",
        "www.pbc.gov.cn",
        ("CN_SF_TOTAL", "CN_SF_COMPONENTS"),
    ),
    "pbc_loan_structure": OfficialContextFamily(
        "中国人民银行", "www.pbc.gov.cn", ("CN_LOAN_STRUCTURE",)
    ),
    "pbc_money": OfficialContextFamily("中国人民银行", "www.pbc.gov.cn", ("CN_M1_M2",)),
    "pbc_usdcny_central_parity": OfficialContextFamily(
        "中国人民银行",
        "www.pbc.gov.cn",
        ("CN_USDCNY_CENTRAL_PARITY",),
        required_p1_rehearsal=False,
    ),
}


OFFICIAL_CONTEXT_FAMILY_BY_METRIC = {
    metric_id: family
    for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
    for metric_id in descriptor.metric_ids
}
