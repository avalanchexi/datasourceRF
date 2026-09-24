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
        "CN_USDCNY_CLOSE_1630",
        "CBOE_VIX_INDEX",
        "NASDAQ_SOX_INDEX",
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
    assert registered_host("CBOE_VIX_INDEX", "https://cdn.cboe.com/x") == "cdn.cboe.com"
    assert registered_host("CN_EQ_ADV_DEC", "https://www.stats.gov.cn/sj/x.html") is None
