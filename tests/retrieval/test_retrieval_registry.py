"""Ticket 01 (phase two): one registry decides which gaps a web page can fill."""

from __future__ import annotations

import pytest

from pring_cycle.freshness import DERIVED_INPUTS
from pring_cycle.retrieval_registry import is_searchable_gap, registered_host


@pytest.mark.parametrize(
    "metric_id",
    [
        "CN_CPI_HEADLINE",
        "CN_PMI_ACTIVITY",
        "CN_SF_TOTAL",
        "CN_USDCNY_CENTRAL_PARITY",
        "CN_LPR_1Y_5Y",
        "CN_EQUITY_CORE_000985",
        "CN_BOND_CORE_000012",
    ],
)
def test_parser_families_and_lenient_hosts_are_searchable(metric_id: str) -> None:
    assert is_searchable_gap(metric_id)


@pytest.mark.parametrize(
    "metric_id",
    [
        "CN_COMMODITY_CORE_NHII",
        "CN_EQ_ADV_DEC",
        "CN_EQ_ABOVE_MA120",
        "CN_COMMODITY_EX_HOG_BASKET",
        "CN_FUTURES_WARRANTS",
        "CN_INDEX_VALUATION",
        "CN_MARGIN_BALANCE",
        "CN_EQ_CSI300",
        # Read from official files, or a restricted-licence gap: never searched (ADR-0029).
        "CN_USDCNY_CLOSE_1630",
        "CBOE_VIX_INDEX",
        "NASDAQ_SOX_INDEX",
        *DERIVED_INPUTS,
    ],
)
def test_metrics_computed_from_tushare_have_no_searchable_source(metric_id: str) -> None:
    assert not is_searchable_gap(metric_id)


def test_a_registered_host_is_matched_by_host_and_path_prefix() -> None:
    assert registered_host("CN_CPI_HEADLINE", "https://www.stats.gov.cn/sj/zxfb/x.html") == (
        "www.stats.gov.cn"
    )
    assert registered_host("CN_CPI_HEADLINE", "https://www.stats.gov.cn/xw/x.html") is None
    assert registered_host("CN_CPI_HEADLINE", "http://www.stats.gov.cn/sj/x.html") is None
    assert (
        registered_host("CN_LPR_1Y_5Y", "https://www.chinamoney.com.cn/chinese/x")
        == "www.chinamoney.com.cn"
    )
    assert registered_host("CN_EQ_ADV_DEC", "https://www.stats.gov.cn/sj/x.html") is None


def test_nbs_releases_under_zwfwck_sjfb_are_on_the_registered_host() -> None:
    """Lookback 13: the NBS serves its releases under /zwfwck/sjfb/ as well as /sj/."""
    release = "https://www.stats.gov.cn/zwfwck/sjfb/202604/t20260416_1963322.html"

    assert registered_host("CN_CAPACITY_UTILIZATION", release) == "www.stats.gov.cn"
    assert registered_host("CN_CPI_HEADLINE", release) == "www.stats.gov.cn"
    assert registered_host("CN_CAPACITY_UTILIZATION", "https://www.stats.gov.cn/zwfwck/x") is None
    assert registered_host("CN_SF_TOTAL", release) is None


@pytest.mark.parametrize(
    ("metric_ids", "period", "query"),
    [
        # Until August 2025 the stock was released in its own report (lookback 14).
        (("CN_SF_TOTAL",), "2025-07", "2025年7月社会融资规模存量统计数据报告"),
        (("CN_SF_COMPONENTS",), "2025-08", "2025年8月社会融资规模存量统计数据报告"),
        (("CN_SF_TOTAL",), "2025-09", "2025年9月金融统计数据报告"),
        # Money stays with the financial statistics report.
        (("CN_M1_M2",), "2025-07", "2025年7月金融统计数据报告"),
    ],
)
def test_social_financing_is_searched_by_the_report_its_period_was_released_in(
    metric_ids: tuple[str, ...], period: str, query: str
) -> None:
    from pring_cycle.retrieval_registry import search_query

    assert search_query(metric_ids, period) == query
