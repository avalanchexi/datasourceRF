"""Phase two #12: selecting a release on the real official listings (see fixtures README)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pring_cycle.official_listing import listing_months, release_url, worth_older_pages

SAMPLES = Path(__file__).parents[1] / "fixtures" / "official_listing"
NBS = "https://www.stats.gov.cn/sj/zxfb/"
PBC = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"


def page(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def select(name: str, family: str, period: str, listing: str = NBS) -> str | None:
    return release_url(page(name), family=family, listing_url=listing, period=period)


def test_social_financing_selects_the_one_monthly_report() -> None:
    listing = page("pbc_116219_index_20260923.html")

    assert release_url(
        listing, family="pbc_social_financing", listing_url=PBC, period="2026-08"
    ) == ("https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026091417020862747/index.html")
    # June's report is titled by the half year.
    assert release_url(listing, family="pbc_money", listing_url=PBC, period="2026-06") is not None


def test_the_first_run_asked_for_2024_periods_the_listing_no_longer_shows() -> None:
    """Zero matches, which the first run reported as ambiguous."""
    assert (
        release_url(
            page("pbc_116219_index_20260923.html"),
            family="pbc_social_financing",
            listing_url=PBC,
            period="2024-08",
        )
        is None
    )
    assert (
        release_url(
            page("nbs_zxfb_index_20260923.html"),
            family="nbs_gdp",
            listing_url=NBS,
            period="2024-Q2",
        )
        is None
    )


def test_second_quarter_gdp_is_two_pages_back_and_is_the_one_release() -> None:
    assert select("nbs_zxfb_index.html", "nbs_gdp", "2026-Q2") is None
    assert worth_older_pages(listing_months(page("nbs_zxfb_index.html")), "2026-Q2")
    assert select("nbs_zxfb_index_1.html", "nbs_gdp", "2026-Q2", NBS + "index_1.html") is None
    assert worth_older_pages(listing_months(page("nbs_zxfb_index_1.html")), "2026-Q2")
    assert select("nbs_zxfb_index_2.html", "nbs_gdp", "2026-Q2", NBS + "index_2.html") == (
        NBS + "202607/t20260716_1964142.html"
    )


@pytest.mark.parametrize("period", ["2026-08", "2026-07"])
def test_monthly_nbs_releases_are_found_on_the_current_pages(period: str) -> None:
    found = [
        url
        for name, suffix in (("nbs_zxfb_index.html", ""), ("nbs_zxfb_index_1.html", "index_1.html"))
        if (url := select(name, "nbs_core_cpi", period, NBS + suffix))
    ]

    assert len(found) == 1


def test_a_reading_of_the_release_is_not_the_release() -> None:
    listing = (
        '<a href="./202609/a.html">2026年8月份居民消费价格同比上涨0.8%</a>'
        '<a href="./202609/b.html">国家统计局城市司首席统计师解读2026年8月份居民消费价格数据</a>'
        '<a href="./202609/c.html">2026年8月份居民消费价格数据解读</a>'
    ).encode()

    assert release_url(listing, family="nbs_core_cpi", listing_url=NBS, period="2026-08") == (
        NBS + "202609/a.html"
    )
