from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialContextFamily:
    provider: str
    host: str
    metric_ids: tuple[str, ...]
    required_p1_rehearsal: bool = True


OFFICIAL_CONTEXT_FAMILIES = {
    "nbs_core_cpi": OfficialContextFamily(
        "国家统计局", "www.stats.gov.cn", ("CN_CORE_CPI",)
    ),
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
    "pbc_rrr_notice": OfficialContextFamily(
        "中国人民银行", "www.pbc.gov.cn", ("CN_RRR_EVENT",)
    ),
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
