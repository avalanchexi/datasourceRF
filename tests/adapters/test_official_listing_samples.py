"""Phase two #12: selecting a release on the real official listings (see fixtures README)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pring_cycle.official_listing import entry_days, next_listing_page, reaches_back, release_url

SAMPLES = Path(__file__).parents[1] / "fixtures" / "official_listing"
NBS = "https://www.stats.gov.cn/sj/zxfb/"
PBC = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"
PBC_REPORTS = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html"
TOOLS = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/"
PBC_DATA = "https://www.pbc.gov.cn/diaochatongjisi/116219/116319/index.html"
NBS_READINGS = "https://www.stats.gov.cn/sj/zxfbhjd/"


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
    assert not reaches_back(entry_days(page("nbs_zxfb_index.html")), "2026-Q2")
    assert next_listing_page(page("nbs_zxfb_index.html"), NBS) == NBS + "index_1.html"
    assert select("nbs_zxfb_index_1.html", "nbs_gdp", "2026-Q2", NBS + "index_1.html") is None
    assert not reaches_back(entry_days(page("nbs_zxfb_index_1.html")), "2026-Q2")
    assert next_listing_page(page("nbs_zxfb_index_1.html"), NBS + "index_1.html") == (
        NBS + "index_2.html"
    )
    assert select("nbs_zxfb_index_2.html", "nbs_gdp", "2026-Q2", NBS + "index_2.html") == (
        NBS + "202607/t20260716_1964142.html"
    )


OMO_PAGES = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"


@pytest.mark.parametrize(
    ("name", "page_url", "following"),
    [
        # The NBS list states its page count: createPageHTML(67, 0, "index", "html").
        ("nbs_zxfb_index.html", NBS, NBS + "index_1.html"),
        ("nbs_zxfb_index_2.html", NBS + "index_2.html", NBS + "index_3.html"),
        ("nbs_zxfbhjd_index_20260924.html", NBS_READINGS, NBS_READINGS + "index_1.html"),
        # A PBC column names its next page in the pager ("下一页").
        ("pbc_125475_index_20260924.html", OMO_PAGES + "index.html", OMO_PAGES + "17081-2.html"),
        (
            "pbc_125475_17081-2_20261009.html",
            OMO_PAGES + "17081-2.html",
            OMO_PAGES + "17081-3.html",
        ),
        (
            "pbc_116225_index_20261009.html",
            PBC_REPORTS,
            PBC_REPORTS.replace("index.html", "11871-2.html"),
        ),
        # The tool liquidity page leaves its pager unfilled: it is all there is.
        ("pbc_5727710_index_20260925.html", TOOLS + "index.html", None),
        # The department page has no pager.
        ("pbc_116219_index_20260923.html", PBC, None),
    ],
)
def test_a_listing_names_its_next_page(name: str, page_url: str, following: str | None) -> None:
    """Lookback L05: history periods are found by going back the listings' pages."""
    assert next_listing_page(page(name), page_url) == following


def test_the_last_nbs_page_has_no_next_one() -> None:
    last = b'<script>createPageHTML(67, 66, "index", "html");</script>'

    assert next_listing_page(last, NBS + "index_66.html") is None


@pytest.mark.parametrize(
    ("name", "newest", "oldest"),
    [
        ("nbs_zxfb_index_1.html", "20260821", "20260730"),
        ("pbc_125475_17081-2_20261009.html", "20260904", "20260811"),
        ("pbc_116225_index_20261009.html", "20260914", "20251212"),
    ],
)
def test_entries_are_dated_by_their_paths(name: str, newest: str, oldest: str) -> None:
    days = entry_days(page(name))

    assert (max(days), min(days)) == (newest, oldest)


@pytest.mark.parametrize(
    ("days", "period", "reached"),
    [
        (["20260915", "20260820"], "2026-08", True),
        (["20260915", "20260901"], "2026-08", False),
        # A day's notices may go on to the next page until an earlier day is listed.
        (["20260912", "20260911"], "2026-09-11", False),
        (["20260911", "20260910"], "2026-09-11", True),
        (["20260716", "20260701"], "2026-Q2", False),
        (["20260701", "20260629"], "2026-Q2", True),
        ([], "2026-08", False),
    ],
)
def test_a_page_reaches_back_to_a_period_once_an_entry_predates_its_end(
    days: list[str], period: str, reached: bool
) -> None:
    assert reaches_back(days, period) is reached


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


@pytest.mark.parametrize(
    ("family", "source_url", "listing"),
    [
        ("nbs_industrial_value_added", NBS_READINGS, NBS_READINGS),
        ("nbs_capacity_utilization", NBS_READINGS, NBS_READINGS),
        # The column's directory answers 403 (five real reads); its index page lists it.
        ("pbc_tool_liquidity_monthly", TOOLS, TOOLS + "index.html"),
        ("pbc_tool_liquidity_monthly", TOOLS + "index.html", TOOLS + "index.html"),
        # The statistics directory lists each year's tables; the department's page only
        # the latest few reports. The monthly report, which carries loans and social
        # financing, is listed page by page in its column (lookback L05).
        ("pbc_loan_structure", PBC_DATA, PBC_REPORTS),
        ("pbc_social_financing", PBC_DATA, PBC_REPORTS),
        ("pbc_social_financing", PBC, PBC_REPORTS),
        ("pbc_money", PBC, PBC_REPORTS),
        ("pbc_money", PBC_REPORTS, PBC_REPORTS),
    ],
)
def test_each_lookback_family_is_looked_up_on_the_listing_of_its_releases(
    family: str, source_url: str, listing: str
) -> None:
    """Lookback L01: these families' history periods went unrequested, their registered
    pages not recognized as the listings their releases are found on."""
    from pring_cycle.official_listing import is_release_listing, release_listing

    assert is_release_listing(family, source_url)
    assert release_listing(family, source_url) == listing


def test_a_release_page_is_not_a_listing() -> None:
    from pring_cycle.official_listing import is_release_listing, release_listing

    release = TOOLS + "2026080416515912098/index.html"
    assert release_listing("pbc_tool_liquidity_monthly", release) is None
    assert not is_release_listing("pbc_tool_liquidity_monthly", release)
    assert not is_release_listing("pbc_loan_structure", TOOLS)


@pytest.mark.parametrize(
    ("family", "name", "listing", "period", "release"),
    [
        (
            "nbs_industrial_value_added",
            "nbs_zxfbhjd_index_20260924.html",
            NBS_READINGS,
            "2026-08",
            NBS_READINGS + "202609/t20260915_1965308.html",
        ),
        (
            "pbc_tool_liquidity_monthly",
            "pbc_5727710_index_20260925.html",
            TOOLS + "index.html",
            "2026-06",
            TOOLS + "2026070216555861498/index.html",
        ),
        (
            "pbc_tool_liquidity_monthly",
            "pbc_5727710_index_20260925.html",
            TOOLS + "index.html",
            "2025-11",
            TOOLS + "5920112/index.html",
        ),
        (
            "pbc_loan_structure",
            "pbc_116219_index_20260923.html",
            PBC,
            "2026-08",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026091417020862747/index.html",
        ),
        # June's report is titled by the half year, for loans as for money.
        (
            "pbc_loan_structure",
            "pbc_116219_index_20260923.html",
            PBC,
            "2026-06",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026071515025183948/index.html",
        ),
    ],
)
def test_a_lookback_family_s_release_is_selected_on_its_real_listing(
    family: str, name: str, listing: str, period: str, release: str
) -> None:
    assert select(name, family, period, listing) == release


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
