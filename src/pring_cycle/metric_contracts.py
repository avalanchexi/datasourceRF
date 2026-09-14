from __future__ import annotations

from dataclasses import dataclass

from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS

# The OMO policy rate is announced by event and remains effective until the
# publisher changes it.  The v0003 catalog retained the source's operational
# daily cadence, so consumers must not interpret that field as a requirement
# for a newly reported rate on every trading day.
EFFECTIVE_UNTIL_CHANGED_METRICS = frozenset({"CN_OMO_7D_RATE"})


def evidence_frequency(metric_id: str, declared_frequency: str) -> str:
    if metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS:
        return "event"
    return declared_frequency


def evidence_max_age_days(metric_id: str, declared_frequency: str) -> int:
    """The existing freshness limits, with operational cadence resolved to event semantics."""
    if metric_id == "CN_RRR_EVENT":
        return 730
    return {"daily": 10, "monthly": 95, "quarterly": 190, "event": 370}.get(
        evidence_frequency(metric_id, declared_frequency), 95
    )


REQUIRED_DIMENSION_MEMBERS: dict[str, tuple[dict[str, str], ...]] = {
    "CN_LPR_1Y_5Y": (
        {"tenor": "1y"},
        {"tenor": "5y_plus"},
    ),
    "CN_M1_M2": tuple(
        {"aggregate": aggregate, "measure": measure}
        for aggregate in ("m1", "m2")
        for measure in ("balance", "yoy")
    ),
    "CN_OMO_7D_AMOUNT": ({"measure": "injection"},),
    "CN_FUTURES_WARRANTS": tuple(
        {"symbol": symbol, "measure": "registered_receipts"}
        for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
    ),
    "CN_EQ_ADV_DEC": tuple(
        {"measure": measure} for measure in ("advances", "declines", "flats", "net")
    ),
    "CN_EQ_NEW_HIGH_LOW_120": tuple({"measure": measure} for measure in ("new_highs", "new_lows")),
    "CN_MARGIN_BALANCE": tuple(
        {"measure": measure, "scope": "all_exchanges"}
        for measure in ("financing_balance", "financing_buy_amount")
    ),
    "CN_INDEX_VALUATION": tuple(
        {"index": index, "measure": measure}
        # Required model members do not shrink to a provider's delivery coverage.
        for index in ("000300.SH", "000905.SH", "000852.SH")
        for measure in ("price_earnings", "price_book", "turnover_rate")
    ),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": tuple(
        {"sleeve": sleeve}
        for sleeve in (
            "copper",
            "rebar",
            "polypropylene",
            "textiles",
            "rubber",
            "pulp",
            "crude_oil",
        )
    ),
    "CN_PMI_ACTIVITY": (
        {"series": "manufacturing", "measure": "level"},
        {"series": "production", "measure": "level"},
        {"series": "new_orders", "measure": "level"},
        {"series": "purchase_volume", "measure": "level"},
    ),
    "CN_PMI_INVENTORY": (
        {"series": "raw_materials", "measure": "level"},
        {"series": "finished_goods", "measure": "level"},
    ),
    "CN_PMI_PRICES": (
        {"series": "purchase_prices", "measure": "level"},
        {"series": "output_prices", "measure": "level"},
    ),
    "CN_SHIBOR_ON_1W_3M": tuple({"tenor": tenor} for tenor in ("overnight", "1w", "3m")),
    "CN_SF_TOTAL": tuple({"measure": measure} for measure in ("ytd_increment", "stock_end")),
}


@dataclass(frozen=True)
class OfficialMember:
    dimensions: dict[str, str]
    unit: str
    period_kind: str


def official_source_members(metric_id: str, period: str) -> tuple[OfficialMember, ...] | None:
    """Source-backed members for newly registered official macro contracts."""
    amount = "hundred_million_cny"
    month = int(period[-1]) * 3 if "-Q" in period else int(period[5:7])
    if metric_id in {"CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"}:
        return tuple(
            OfficialMember(d, "diffusion_index_points", "month")
            for d in REQUIRED_DIMENSION_MEMBERS[metric_id]
        )
    if metric_id == "CN_PPI":
        measures = ("mom", "yoy") if month == 1 else ("mom", "yoy", "cumulative_average_yoy")
        return tuple(
            OfficialMember({"category": category, "measure": measure}, "percent", "month")
            for category in ("headline", "means_of_production", "consumer_goods")
            for measure in measures
        )
    if metric_id == "CN_INDUSTRIAL_VA":
        return tuple(
            OfficialMember({"measure": measure}, "percent", kind)
            for measure, kind in (
                ("current_month_real_yoy", "month"),
                ("mom_seasonally_adjusted", "month"),
                ("ytd_real_yoy", "year_to_month"),
            )
            if month != 2 or measure != "current_month_real_yoy"
        )
    if metric_id == "CN_INDUSTRIAL_FINANCE":
        return tuple(
            OfficialMember({"item": item, "measure": measure}, unit, "year_to_month")
            for item in ("revenue", "cost", "profit")
            for measure, unit in (("ytd_level", amount), ("official_yoy", "percent"))
        )
    if metric_id == "CN_FINISHED_GOODS_INVENTORY":
        return tuple(
            OfficialMember({"measure": measure}, unit, "month")
            for measure, unit in (("nominal_end_level", amount), ("official_yoy", "percent"))
        )
    if metric_id == "CN_INVENTORY_TURNOVER":
        return tuple(
            OfficialMember({"measure": measure}, "days", "year_to_month")
            for measure in ("days", "official_yoy_change")
        )
    if metric_id == "CN_CAPACITY_UTILIZATION":
        return tuple(
            OfficialMember({"industry": "all_industry", "measure": measure}, unit, kind)
            for measure, unit, kind in (
                ("quarter_rate", "percent", "quarter"),
                ("yoy_change", "percentage_points", "quarter"),
                ("ytd_rate", "percent", "year_to_quarter"),
            )
        )
    if metric_id == "CN_M1_M2":
        return tuple(
            OfficialMember({"aggregate": aggregate, "measure": measure}, unit, "month")
            for aggregate in ("m1", "m2")
            for measure, unit in (("balance", amount), ("yoy", "percent"))
        )
    if metric_id in {"CN_SF_TOTAL", "CN_SF_COMPONENTS"}:
        components = (
            ({},)
            if metric_id == "CN_SF_TOTAL"
            else tuple(
                {"component": component}
                for component in (
                    "renminbi_loans",
                    "foreign_currency_loans_rmb",
                    "entrusted_loans",
                    "trust_loans",
                    "undiscounted_bank_acceptances",
                    "corporate_bonds",
                    "government_bonds",
                    "nonfinancial_enterprise_equity",
                )
            )
        )
        return tuple(
            OfficialMember({**component, "measure": measure}, unit, kind)
            for component in components
            for measure, unit, kind in (
                ("stock_end", amount, "month"),
                ("stock_yoy", "percent", "month"),
                ("ytd_increment", amount, "year_to_month"),
            )
        )
    if metric_id == "CN_LOAN_STRUCTURE":
        pairs = (
            ("household", "total"),
            ("household", "short_term"),
            ("household", "long_term"),
            ("enterprise", "total"),
            ("enterprise", "short_term"),
            ("enterprise", "long_term"),
            ("enterprise", "bill_financing"),
            ("nonbank_financial", "total"),
            ("all_rmb_loans", "total"),
        )
        return tuple(
            OfficialMember(
                {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"},
                amount,
                "year_to_month",
            )
            for borrower, tenor in pairs
        )
    if metric_id == "CN_TOOL_LIQUIDITY_MONTHLY":
        return tuple(
            OfficialMember({"tool": tool, "measure": measure}, amount, "month")
            for tool in (
                "常备借贷便利（SLF）",
                "中期借贷便利（MLF）",
                "抵押补充贷款（PSL）",
                "其他结构性货币政策工具",
                "7天期逆回购",
                "其他期限逆回购",
                "公开市场国债买卖",
                "中央国库现金管理",
            )
            for measure in ("injection", "withdrawal", "net_injection")
        )
    if metric_id == "CN_OMO_7D_AMOUNT":
        return (OfficialMember({"measure": "injection"}, amount, "business_day"),)
    if metric_id == "CN_OMO_7D_RATE":
        return (OfficialMember({}, "percent", "business_day"),)
    return None


def required_dimension_members(
    metric_id: str, *, definition_version: str, period: str
) -> tuple[dict[str, str], ...] | None:
    """Resolve new CPI completeness by reporting month without changing old catalogs."""
    categories = {"CN_CPI_HEADLINE": "headline", "CN_CORE_CPI": "ex_food_energy"}
    if definition_version not in BUILTIN_CATALOG_VERSIONS and metric_id in categories:
        measures: tuple[str, ...] = ("mom", "yoy")
        # January's official table does not report a separate cumulative column.
        # Never synthesize that field or treat it as an index level.
        if period[5:7] != "01":
            measures += ("cumulative_average_yoy",)
        return tuple({"category": categories[metric_id], "measure": value} for value in measures)
    if definition_version not in BUILTIN_CATALOG_VERSIONS:
        from pring_cycle.commodity_basket import COMMODITY_FORMULA_VERSION, COMMODITY_METRICS
        from pring_cycle.market_breadth import DAILY_BREADTH_MEASURES, WINDOW_BREADTH_MEASURES
        from pring_cycle.tushare_context import MARKET_INDEX_IDENTITIES

        if metric_id in COMMODITY_METRICS:
            commodity_members = REQUIRED_DIMENSION_MEMBERS.get(metric_id, ({},))
            return tuple(
                {"formula_version": COMMODITY_FORMULA_VERSION, **m} for m in commodity_members
            )

        if metric_id == "CN_EQ_ADV_AMOUNT_SHARE":
            return (
                {"measure": "advancing_amount_share", "universe": "point_in_time_traded_a_shares"},
            )

        if metric_id in WINDOW_BREADTH_MEASURES:
            return tuple(
                {"measure": m, "universe": "point_in_time_traded_a_shares"}
                for m in WINDOW_BREADTH_MEASURES[metric_id]
            )

        if metric_id in DAILY_BREADTH_MEASURES:
            return tuple(
                {"measure": m, "universe": "point_in_time_traded_a_shares"}
                for m in DAILY_BREADTH_MEASURES[metric_id]
            )

        if metric_id in MARKET_INDEX_IDENTITIES:
            return ({"source_code": MARKET_INDEX_IDENTITIES[metric_id][1]},)

        members = official_source_members(metric_id, period)
        if members is not None:
            return tuple(
                member.dimensions
                for member in members
                if metric_id != "CN_SF_TOTAL" or member.dimensions["measure"] != "stock_yoy"
            )
    return REQUIRED_DIMENSION_MEMBERS.get(metric_id)
