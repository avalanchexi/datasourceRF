from __future__ import annotations

from pring_cycle.retrieval_registry import families_of

# Opt-in delivery contract, bound into a newly reviewed immutable metric definition.
# This identifier does not itself confer source certification.
TUSHARE_PPI_SOURCE_CODE = "tushare:cn_ppi:official-sampled-v0001"
TUSHARE_CPI_SOURCE_CODE = "tushare:cn_cpi:official-sampled-v0001"
TUSHARE_PMI_SOURCE_CODE = "tushare:cn_pmi:official-sampled-v0001"
TUSHARE_MONEY_SOURCE_CODE = "tushare:cn_m:official-sampled-v0001"
TUSHARE_SF_TOTAL_SOURCE_CODE = "tushare:sf_month:official-sampled-v0001"
TUSHARE_GDP_SOURCE_CODE = "tushare:cn_gdp:official-sampled-v0001"

TUSHARE_OFFICIAL_DELIVERY_CODES = {
    "CN_PPI": TUSHARE_PPI_SOURCE_CODE,
    "CN_CPI_HEADLINE": TUSHARE_CPI_SOURCE_CODE,
    "CN_PMI_ACTIVITY": TUSHARE_PMI_SOURCE_CODE,
    "CN_PMI_INVENTORY": TUSHARE_PMI_SOURCE_CODE,
    "CN_PMI_PRICES": TUSHARE_PMI_SOURCE_CODE,
    "CN_M1_M2": TUSHARE_MONEY_SOURCE_CODE,
    "CN_SF_TOTAL": TUSHARE_SF_TOTAL_SOURCE_CODE,
    "CN_GDP": TUSHARE_GDP_SOURCE_CODE,
}
TUSHARE_GDP_FIELDS = (
    ("total", "gdp", "gdp_yoy"),
    ("primary", "pi", "pi_yoy"),
    ("secondary", "si", "si_yoy"),
    ("tertiary", "ti", "ti_yoy"),
)
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


# The official NBS/PBC families live in the retrieval registry with every other family
# search can reach; this is their view by the official release parser.
OFFICIAL_CONTEXT_FAMILIES = families_of("official_context")


OFFICIAL_CONTEXT_FAMILY_BY_METRIC = {
    metric_id: family
    for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
    for metric_id in descriptor.metric_ids
}
