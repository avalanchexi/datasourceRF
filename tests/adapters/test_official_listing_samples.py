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


def test_industrial_finance_is_followed_from_its_registered_listing() -> None:
    """The 2026-09-25 real run parsed the registered /sj/zxfbhjd/ list itself as July's
    release: the family was missing from the listings the NBS pages are followed through."""
    from pring_cycle.official_listing import is_release_listing

    assert is_release_listing("nbs_industrial_finance", "https://www.stats.gov.cn/sj/zxfbhjd/")
    assert select("nbs_zxfb_index_20260923.html", "nbs_industrial_finance", "2026-07") == (
        "https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html"
    )


OMO = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html"


def test_omo_notices_are_the_day_s_entries_newest_first() -> None:
    """Event #04: OMO notice titles carry no date; the entry's path does (…/2026092308…/)."""
    from pring_cycle.official_listing import is_release_listing, release_urls

    listing = page("pbc_125475_index_20260924.html")
    notice = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/{}/index.html"

    assert is_release_listing("pbc_omo_notice", OMO)
    # 9/23 had two: the HK central bank bills (no. 188), then the day's reverse repo (187).
    assert release_urls(listing, family="pbc_omo_notice", listing_url=OMO, period="2026-09-23") == (
        notice.format("2026092311141529051"),
        notice.format("2026092308513432696"),
    )
    assert release_urls(listing, family="pbc_omo_notice", listing_url=OMO, period="2026-09-24") == (
        notice.format("2026092408454713496"),
    )


CHRONICLES = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125963/index.html"


def test_the_chronicle_column_lists_each_issue_with_the_months_it_covers() -> None:
    """Event #03: the RRR is traced back through the monetary policy chronicles."""
    from pring_cycle.official_listing import (
        RRR_CHRONICLE_LISTING,
        chronicle_entries,
        chronicle_next_page,
    )

    assert RRR_CHRONICLE_LISTING == CHRONICLES
    first = page("pbc_125963_index_20260925.html")
    entries = chronicle_entries(first, CHRONICLES)

    assert len(entries) == 20
    newest = entries[0]
    assert newest.url == CHRONICLES.replace("index.html", "2026081218415997958/index.html")
    assert (newest.year, newest.through_month, newest.published) == (2026, 6, "2026-08-12")
    # A year's issue covers it to December; a first quarter's to March.
    assert [(e.year, e.through_month, e.published) for e in entries[1:3]] == [
        (2026, 3, "2026-05-11"),
        (2025, 12, "2026-02-10"),
    ]
    assert (entries[3].year, entries[3].through_month) == (2025, 9)
    assert chronicle_next_page(first, CHRONICLES) == CHRONICLES.replace(
        "index.html", "17134-2.html"
    )

    second = page("pbc_125963_17134-2_20260925.html")
    older = chronicle_entries(second, CHRONICLES.replace("index.html", "17134-2.html"))
    # Before 2021 a quarter's issue is titled by the quarter alone.
    assert [(e.year, e.through_month) for e in older[:3]] == [(2021, 6), (2021, 3), (2020, 12)]
    assert chronicle_next_page(second, CHRONICLES) == CHRONICLES.replace(
        "index.html", "17134-3.html"
    )
