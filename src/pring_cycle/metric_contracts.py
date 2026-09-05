from __future__ import annotations

# The OMO policy rate is announced by event and remains effective until the
# publisher changes it.  The v0003 catalog retained the source's operational
# daily cadence, so consumers must not interpret that field as a requirement
# for a newly reported rate on every trading day.
EFFECTIVE_UNTIL_CHANGED_METRICS = frozenset({"CN_OMO_7D_RATE"})


def evidence_frequency(metric_id: str, declared_frequency: str) -> str:
    if metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS:
        return "event"
    return declared_frequency


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
        {"measure": measure}
        for measure in ("advances", "declines", "flats", "net")
    ),
    "CN_EQ_NEW_HIGH_LOW_120": tuple(
        {"measure": measure} for measure in ("new_highs", "new_lows")
    ),
    "CN_MARGIN_BALANCE": tuple(
        {"measure": measure, "scope": "all_exchanges"}
        for measure in ("financing_balance", "financing_buy_amount")
    ),
    "CN_INDEX_VALUATION": tuple(
        {"index": index, "measure": measure}
        # index_dailybasic publishes broad-market daily indicators for CSI 300
        # and CSI 500, but not CSI 1000. Keep every supported valuation field
        # instead of inventing a CSI 1000 value from a different methodology.
        for index in ("000300.SH", "000905.SH")
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
    "CN_SHIBOR_ON_1W_3M": tuple(
        {"tenor": tenor} for tenor in ("overnight", "1w", "3m")
    ),
    "CN_SF_TOTAL": tuple(
        {"measure": measure} for measure in ("ytd_increment", "stock_end")
    ),
}
