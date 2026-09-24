"""Phase two #09 and #10: the NBS and PBC news rules on real release-day texts.

Each sample is TuShare `major_news` as fetched (tests/fixtures/news). A member not listed
for a family is not stated in these texts at all: core CPI's month-on-month change, the
PMI finished-goods inventory index, capacity utilization for the year to date, each
industry's quarterly GDP growth and the monthly tool liquidity table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pring_cycle.news_rules import (
    NEWS_RULES,
    PERIOD_MISMATCH,
    extract,
    plain_text,
)

NEWS = Path(__file__).parents[1] / "fixtures" / "news"


def texts(sample: str) -> list[str]:
    return [
        plain_text(item["content"]) for item in json.loads((NEWS / sample).read_text())["items"]
    ]


def stated(
    sample: str, metric_ids: tuple[str, ...], period: str
) -> dict[tuple[str, ...], set[float]]:
    found: dict[tuple[str, ...], set[float]] = {}
    for text in texts(sample):
        for value in extract(metric_ids, period, text).values:
            key = (value.metric_id, *sorted(value.dimensions.values()))
            found.setdefault(key, set()).add(value.value)
    return found


CASES = [
    pytest.param(
        "nbs_20260831_pmi.json",
        ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
        "2026-08",
        {
            ("CN_PMI_ACTIVITY", "level", "manufacturing"): 49.8,
            ("CN_PMI_ACTIVITY", "level", "production"): 50.4,
            # Not the non-manufacturing new orders index (44.1%) further down.
            ("CN_PMI_ACTIVITY", "level", "new_orders"): 50.6,
            ("CN_PMI_ACTIVITY", "level", "purchase_volume"): 50.5,
            ("CN_PMI_INVENTORY", "level", "raw_materials"): 48.1,
            ("CN_PMI_PRICES", "level", "purchase_prices"): 56.6,
            ("CN_PMI_PRICES", "level", "output_prices"): 50.4,
        },
        id="pmi",
    ),
    pytest.param(
        "nbs_20260915_industrial_value_added.json",
        ("CN_INDUSTRIAL_VA", "CN_CORE_CPI"),
        "2026-08",
        {
            # August's 5.2% is the month; "1—8月份 ... 5.3%" is the year to date.
            ("CN_INDUSTRIAL_VA", "current_month_real_yoy"): 5.2,
            ("CN_INDUSTRIAL_VA", "ytd_real_yoy"): 5.3,
            ("CN_INDUSTRIAL_VA", "mom_seasonally_adjusted"): 0.54,
            ("CN_CORE_CPI", "ex_food_energy", "yoy"): 1.0,
        },
        id="industrial-value-added",
    ),
    pytest.param(
        "nbs_20260827_industrial_profit.json",
        ("CN_INDUSTRIAL_FINANCE", "CN_FINISHED_GOODS_INVENTORY", "CN_INVENTORY_TURNOVER"),
        "2026-07",
        {
            ("CN_INDUSTRIAL_FINANCE", "revenue", "ytd_level"): 809200.0,
            ("CN_INDUSTRIAL_FINANCE", "official_yoy", "revenue"): 6.5,
            ("CN_INDUSTRIAL_FINANCE", "cost", "ytd_level"): 687900.0,
            ("CN_INDUSTRIAL_FINANCE", "cost", "official_yoy"): 5.9,
            ("CN_INDUSTRIAL_FINANCE", "profit", "ytd_level"): 45820.6,
            ("CN_INDUSTRIAL_FINANCE", "official_yoy", "profit"): 17.6,
            # 10.8% is the inventory's growth, not the receivables' 8.5% before it.
            ("CN_FINISHED_GOODS_INVENTORY", "nominal_end_level"): 72700.0,
            ("CN_FINISHED_GOODS_INVENTORY", "official_yoy"): 10.8,
            ("CN_INVENTORY_TURNOVER", "days"): 21.3,
            ("CN_INVENTORY_TURNOVER", "official_yoy_change"): 0.6,
        },
        id="industrial-finance",
    ),
    pytest.param(
        "nbs_20260715_gdp_capacity.json",
        ("CN_GDP", "CN_CAPACITY_UTILIZATION"),
        "2026-Q2",
        {
            ("CN_GDP", "nominal_ytd_level", "total"): 695704.0,
            ("CN_GDP", "nominal_ytd_level", "primary"): 31522.0,
            ("CN_GDP", "nominal_ytd_level", "secondary"): 250473.0,
            ("CN_GDP", "nominal_ytd_level", "tertiary"): 413709.0,
            # The second quarter's 4.3%, not the half year's 4.7% or the first quarter's 5.0%.
            ("CN_GDP", "real_quarter_yoy", "total"): 4.3,
            ("CN_CAPACITY_UTILIZATION", "all_industry", "quarter_rate"): 73.0,
            # Against a year earlier, not against the first quarter (-0.6).
            ("CN_CAPACITY_UTILIZATION", "all_industry", "yoy_change"): -1.0,
        },
        id="gdp-capacity",
    ),
    pytest.param(
        "nbs_20260715_gdp_capacity.json",
        ("CN_CORE_CPI", "CN_INDUSTRIAL_VA"),
        "2026-06",
        {
            ("CN_CORE_CPI", "ex_food_energy", "yoy"): 1.0,
            ("CN_CORE_CPI", "cumulative_average_yoy", "ex_food_energy"): 1.2,
            ("CN_INDUSTRIAL_VA", "current_month_real_yoy"): 5.3,
            ("CN_INDUSTRIAL_VA", "ytd_real_yoy"): 5.4,
            ("CN_INDUSTRIAL_VA", "mom_seasonally_adjusted"): 0.76,
        },
        id="june-core-cpi-and-value-added",
    ),
    pytest.param(
        "pbc_20260914_financial_statistics.json",
        ("CN_SF_TOTAL", "CN_M1_M2"),
        "2026-08",
        {
            ("CN_SF_TOTAL", "ytd_increment"): 239100.0,
            ("CN_SF_TOTAL", "stock_end"): 4648000.0,
            ("CN_M1_M2", "balance", "m2"): 3568100.0,
            ("CN_M1_M2", "m2", "yoy"): 7.5,
            ("CN_M1_M2", "balance", "m1"): 1157700.0,
            ("CN_M1_M2", "m1", "yoy"): 4.1,
        },
        id="social-financing-and-money",
    ),
    pytest.param(
        "pbc_20260914_financial_statistics.json",
        ("CN_SF_COMPONENTS",),
        "2026-08",
        {
            ("CN_SF_COMPONENTS", *sorted((component, measure))): value
            for component, stock, growth, increment in (
                ("renminbi_loans", 2786300.0, 5.0, 102300.0),
                ("foreign_currency_loans_rmb", 12300.0, 3.1, 2103.0),
                ("entrusted_loans", 112600.0, 1.0, -582.0),
                ("trust_loans", 45800.0, 1.9, -905.0),
                ("undiscounted_bank_acceptances", 20100.0, -5.1, -1404.0),
                ("corporate_bonds", 367100.0, 9.7, 27900.0),
                ("government_bonds", 1036900.0, 13.5, 87700.0),
                ("nonfinancial_enterprise_equity", 126700.0, 5.7, 4700.0),
            )
            for measure, value in (
                ("stock_end", stock),
                ("stock_yoy", growth),
                ("ytd_increment", increment),
            )
        },
        id="social-financing-components",
    ),
    pytest.param(
        "pbc_20260914_financial_statistics.json",
        ("CN_LOAN_STRUCTURE",),
        "2026-08",
        {
            ("CN_LOAN_STRUCTURE", "household", "total", "ytd_increment"): -10300.0,
            ("CN_LOAN_STRUCTURE", "household", "short_term", "ytd_increment"): -10500.0,
            ("CN_LOAN_STRUCTURE", "household", "long_term", "ytd_increment"): 188.0,
            ("CN_LOAN_STRUCTURE", "enterprise", "total", "ytd_increment"): 112600.0,
            ("CN_LOAN_STRUCTURE", "enterprise", "short_term", "ytd_increment"): 41800.0,
            ("CN_LOAN_STRUCTURE", "enterprise", "long_term", "ytd_increment"): 56400.0,
            ("CN_LOAN_STRUCTURE", "bill_financing", "enterprise", "ytd_increment"): 12900.0,
            ("CN_LOAN_STRUCTURE", "nonbank_financial", "total", "ytd_increment"): -4380.0,
            # All RMB loans (10.44 trillion), not the social-financing 10.23 trillion.
            ("CN_LOAN_STRUCTURE", "all_rmb_loans", "total", "ytd_increment"): 104400.0,
        },
        id="loan-structure",
    ),
    pytest.param(
        "pbc_20260920_lpr.json",
        ("CN_LPR_1Y_5Y",),
        "2026-09",
        {("CN_LPR_1Y_5Y", "1y"): 3.0, ("CN_LPR_1Y_5Y", "5y_plus"): 3.5},
        id="lpr",
    ),
    pytest.param(
        "pbc_20260920_lpr.json",
        ("CN_OMO_7D_AMOUNT", "CN_OMO_7D_RATE"),
        "2026-09-20",
        {("CN_OMO_7D_AMOUNT", "injection"): 320.0, ("CN_OMO_7D_RATE",): 1.4},
        id="omo-in-a-market-brief",
    ),
    pytest.param(
        "pbc_daily_omo_central_parity.json",
        ("CN_OMO_7D_AMOUNT", "CN_OMO_7D_RATE", "CN_USDCNY_CENTRAL_PARITY"),
        "2026-09-21",
        {
            ("CN_OMO_7D_AMOUNT", "injection"): 1650.0,
            ("CN_USDCNY_CENTRAL_PARITY", "CNY per USD", "USD/CNY"): 6.7487,
            # The day's rate appears only after "今日", which names no date: not taken.
        },
        id="omo-and-central-parity",
    ),
]


@pytest.mark.parametrize(("sample", "metric_ids", "period", "expected"), CASES)
def test_rules_take_each_stated_member_once(
    sample: str,
    metric_ids: tuple[str, ...],
    period: str,
    expected: dict[tuple[str, ...], float],
) -> None:
    found = stated(sample, metric_ids, period)

    assert {key: sorted(values) for key, values in found.items()} == {
        key: [value] for key, value in expected.items()
    }


@pytest.mark.parametrize(
    ("sample", "metric_ids", "other"),
    [
        ("nbs_20260831_pmi.json", ("CN_PMI_ACTIVITY", "CN_PMI_PRICES"), "2026-07"),
        ("nbs_20260915_industrial_value_added.json", ("CN_INDUSTRIAL_VA",), "2026-07"),
        ("nbs_20260827_industrial_profit.json", ("CN_INDUSTRIAL_FINANCE",), "2026-06"),
        ("nbs_20260715_gdp_capacity.json", ("CN_GDP", "CN_CAPACITY_UTILIZATION"), "2026-Q3"),
        ("pbc_20260914_financial_statistics.json", ("CN_SF_TOTAL", "CN_M1_M2"), "2026-07"),
        ("pbc_20260914_financial_statistics.json", ("CN_LOAN_STRUCTURE",), "2026-07"),
        ("pbc_20260920_lpr.json", ("CN_LPR_1Y_5Y",), "2026-08"),
        ("pbc_daily_omo_central_parity.json", ("CN_USDCNY_CENTRAL_PARITY",), "2026-09-22"),
    ],
)
def test_another_period_is_not_taken(sample: str, metric_ids: tuple[str, ...], other: str) -> None:
    extractions = [extract(metric_ids, other, text) for text in texts(sample)]

    assert all(extraction.values == () for extraction in extractions)
    assert any(extraction.reason == PERIOD_MISMATCH for extraction in extractions)


def test_every_rule_is_exercised_by_a_real_sample() -> None:
    covered = {
        (metric, *dims)
        for sample, metric_ids, period, _expected in (case.values for case in CASES)
        for metric, *dims in stated(sample, metric_ids, period)
    }
    covered |= {
        ("CN_CPI_HEADLINE", *sorted(("headline", m)))
        for m in ("yoy", "mom", "cumulative_average_yoy")
    }
    covered |= {
        ("CN_PPI", *sorted((c, m)))
        for c in ("headline", "means_of_production", "consumer_goods")
        for m in ("yoy", "mom", "cumulative_average_yoy")
    }
    registered = {
        (rule.metric_id, *sorted(value for _key, value in rule.dimensions))
        for rules in NEWS_RULES.values()
        for rule in rules
    }

    assert registered <= covered


def test_every_rule_writes_a_member_the_catalog_requires() -> None:
    """A news value must land on the same observation as the official one."""
    from pring_cycle.metric_contracts import required_dimension_members

    for rule in (rule for rules in NEWS_RULES.values() for rule in rules):
        period = {
            "CN_GDP": "2026-Q2",
            "CN_CAPACITY_UTILIZATION": "2026-Q2",
            "CN_OMO_7D_RATE": "2026-09-21",
            "CN_OMO_7D_AMOUNT": "2026-09-21",
            "CN_USDCNY_CENTRAL_PARITY": "2026-09-21",
        }.get(rule.metric_id, "2026-08")
        members = required_dimension_members(
            rule.metric_id, definition_version="registered", period=period
        )
        if members is None:  # Members come from the parser: central parity, LPR.
            continue
        assert dict(rule.dimensions) in [dict(m) for m in members], rule.metric_id


def test_a_monthly_fixing_stated_by_its_day_is_that_month_s() -> None:
    """The real run's AI candidate for September's LPR: the fixing day names the month."""
    quote = (
        "据央行网站，中国人民银行授权全国银行间同业拆借中心公布，"
        "2026年9月20日贷款市场报价利率（LPR）为：1年期LPR为3.0%，5年期以上LPR为3.5%。"
    )

    lpr = extract(("CN_LPR_1Y_5Y",), "2026-09", quote)
    assert {v.dimensions["tenor"]: v.value for v in lpr.values} == {"1y": 3.0, "5y_plus": 3.5}
    assert extract(("CN_LPR_1Y_5Y",), "2026-08", quote).values == ()
