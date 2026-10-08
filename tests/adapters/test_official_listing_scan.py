"""Lookback L05: a history period is looked up by reading its listing back to its date.

The NBS list stopped after ten pages, or at once for a period six months older than its
newest entry; the PBC columns were read on their first page only. A run's 100 OMO days
read that one first page 100 times, and each day not on it was simply "not found".
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.official_context import (
    LISTING_PAGES_PER_SITE,
    FetchedOfficialContextDocument,
    ListingScan,
    refresh_official_context_document,
)
from pring_cycle.official_listing import ListingNotCovered
from pring_cycle.runtime import RuntimePaths, initialize_runtime

FIXTURES = Path(__file__).parents[1] / "fixtures"
NBS = "https://www.stats.gov.cn/sj/zxfb/"
NBS_READINGS = "https://www.stats.gov.cn/sj/zxfbhjd/"
OMO = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"


class Site:
    """Serves the pages it holds and remembers each URL asked for."""

    def __init__(self, documents: dict[str, bytes]) -> None:
        self.documents = documents
        self.requested: list[str] = []

    def __call__(self, url: str) -> FetchedOfficialContextDocument:
        self.requested.append(url)
        return FetchedOfficialContextDocument(self.documents[url], "text/html", url, 200)


def nbs_page(index: int, count: int, entries: list[tuple[str, str]]) -> bytes:
    links = "".join(f'<li><a href="{href}">{title}</a></li>' for href, title in entries)
    pager = f'<script>createPageHTML({count}, {index}, "index", "html");</script>'
    return f"<html><ul>{links}</ul>{pager}</html>".encode()


def nbs_url(listing: str, index: int) -> str:
    return listing if index == 0 else f"{listing}index_{index}.html"


def nbs_filler(day: date, number: int) -> tuple[str, str]:
    return f"./{day:%Y%m}/t{day:%Y%m%d}_{number}.html", "国家统计局其他发布"


def omo_page(index: int, entries: list[str], *, following: int | None) -> bytes:
    """A page of the OMO column: its notices by path, and the pager's next page."""
    links = "".join(
        f'<li><a href="{OMO}{notice}/index.html">公开市场业务交易公告</a></li>'
        for notice in entries
    )
    pager = (
        f'<a style="cursor:pointer" tagname="/zhengcehuobisi/125207/125213/125431/125475/'
        f'17081-{following}.html" class="pagingNormal">下一页</a>'
        if following is not None
        else '<a tagname="[NEXTPAGE]">下一页</a>'
    )
    return f"<html><ul>{links}</ul>{pager}</html>".encode()


def omo_url(page: int) -> str:
    return OMO + ("index.html" if page == 1 else f"17081-{page}.html")


def core_cpi_february() -> bytes:
    return """
    <html><body>
      <h1>2026年2月份居民消费价格</h1>
      <p>发布时间：2026-03-09 09:30</p>
      <table>
        <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
        <tr><td>不包括食品和能源</td><td>0.1</td><td>0.8</td><td>0.6</td></tr>
      </table>
    </body></html>
    """.encode()


def runtime(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def test_a_month_far_down_the_nbs_list_is_found_by_its_date(tmp_path: Path) -> None:
    """February's CPI is twenty pages and seven months back: past both old limits."""
    paths = runtime(tmp_path)
    newest = date(2026, 9, 20)
    release = "./202603/t20260309_1.html"
    documents = {}
    for index in range(30):
        entries = [nbs_filler(newest - timedelta(days=10 * index + n), n) for n in range(3)]
        if index == 19:
            entries.insert(1, (release, "2026年2月份居民消费价格同比上涨0.8%"))
        documents[nbs_url(NBS, index)] = nbs_page(index, 30, entries)
    documents[NBS + "202603/t20260309_1.html"] = core_cpi_february()
    site = Site(documents)

    result = refresh_official_context_document(
        paths,
        family="nbs_core_cpi",
        source_url=NBS,
        expected_period="2026-02",
        fetched_at=datetime.now(UTC),
        fetcher=site,
    )

    assert result.observation_count == 3
    # Read back page by page to the release, and no further.
    assert site.requested == [nbs_url(NBS, index) for index in range(20)] + [
        NBS + "202603/t20260309_1.html"
    ]
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    counts = [
        receipts.counts(receipt.acquisition_id)
        for receipt in receipts.history()
        if receipt.api_name == "official_listing_get"
    ]
    # Each page read is a receipt, its records the list's dated entries (lookback L06).
    assert sorted(item.source_records or 0 for item in counts) == [3] * 19 + [4]
    assert {(item.normalized_scalars, item.ingested_claims) for item in counts} == {(None, None)}


OMO_REPO_0923 = "2026092308513432696"
OMO_BILLS_0923 = "2026092311141529051"
OMO_REPO_0924 = "2026092408454713496"


def omo_column() -> dict[str, bytes]:
    """Four pages; 9/23's two notices run on from the second page to the third."""
    pages = [
        ["2026093008450000001", "2026092908450000001", "2026092808450000001"],
        ["2026092508450000001", OMO_REPO_0924, OMO_BILLS_0923],
        [OMO_REPO_0923, "2026092208450000001"],
        ["2026091908450000001", "2026091708450000001"],
    ]
    documents = {
        omo_url(page): omo_page(page, entries, following=page + 1 if page < 4 else None)
        for page, entries in enumerate(pages, start=1)
    }
    for notice in (OMO_REPO_0923, OMO_BILLS_0923, OMO_REPO_0924):
        documents[f"{OMO}{notice}/index.html"] = (
            FIXTURES / "pbc_omo_notice" / f"{notice}.html"
        ).read_bytes()
    return documents


def refresh_omo(paths: RuntimePaths, site: Site, scan: ListingScan, day: str) -> tuple[str, ...]:
    return refresh_official_context_document(
        paths,
        family="pbc_omo_notice",
        source_url=omo_url(1),
        expected_period=day,
        fetched_at=datetime.now(UTC),
        fetcher=site,
        listings=scan,
    ).metric_ids


def test_the_days_of_one_run_read_each_listing_page_once(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    site = Site(omo_column())
    scan = ListingScan()

    # 9/23's notices are on two pages: both are read, the bills passed over for the repo.
    assert refresh_omo(paths, site, scan, "2026-09-23") == ("CN_OMO_7D_AMOUNT", "CN_OMO_7D_RATE")
    assert site.requested == [
        omo_url(1),
        omo_url(2),
        omo_url(3),
        f"{OMO}{OMO_BILLS_0923}/index.html",
        f"{OMO}{OMO_REPO_0923}/index.html",
    ]
    # A later day is on a page already read.
    refresh_omo(paths, site, scan, "2026-09-24")
    assert site.requested[5:] == [f"{OMO}{OMO_REPO_0924}/index.html"]
    # An earlier one reads on from the last page read: the column lists none for 9/18.
    with pytest.raises(ValueError, match="official_context_release_link_not_found"):
        refresh_omo(paths, site, scan, "2026-09-18")
    assert site.requested[6:] == [omo_url(4)]
    # The column ends before 9/1: not listed, which is not "no operation".
    with pytest.raises(ListingNotCovered) as ended:
        refresh_omo(paths, site, scan, "2026-09-01")
    assert (ended.value.stopped, ended.value.pages, ended.value.oldest) == (
        "last_page",
        4,
        "20260917",
    )
    assert len(site.requested) == 7


def test_a_page_listing_what_the_one_before_did_ends_the_listing(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    first = ["2026093008450000001", "2026092908450000001"]
    site = Site(
        {
            omo_url(1): omo_page(1, first, following=2),
            omo_url(2): omo_page(2, first, following=3),
        }
    )

    with pytest.raises(ListingNotCovered, match="official_listing_not_covered"):
        refresh_omo(paths, site, ListingScan(), "2026-09-01")

    assert site.requested == [omo_url(1), omo_url(2)]
    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "CN_OMO_7D_AMOUNT", period="2026-09-01", as_of=datetime.now(UTC)
    )
    assert attempt is not None
    # No request went out for the day's notice: the listing did not reach it.
    assert attempt.outcome == "not_attempted"
    assert attempt.safe_metadata["condition"] == "official_listing_not_covered"
    assert attempt.safe_metadata["listing_stopped"] == "repeated_page"
    assert attempt.safe_metadata["listing_pages"] == "2"


def test_a_site_reads_at_most_fifty_listing_pages_a_run(tmp_path: Path) -> None:
    """Every page lists September: February is beyond what one run reads of the site."""
    paths = runtime(tmp_path)
    documents = {}
    for listing in (NBS, NBS_READINGS):
        for index in range(LISTING_PAGES_PER_SITE + 5):
            documents[nbs_url(listing, index)] = nbs_page(
                index, 500, [nbs_filler(date(2026, 9, 30) - timedelta(days=index % 20), index)]
            )
    site = Site(documents)
    scan = ListingScan()

    with pytest.raises(ListingNotCovered) as capped:
        refresh_official_context_document(
            paths,
            family="nbs_core_cpi",
            source_url=NBS,
            expected_period="2026-02",
            fetched_at=datetime.now(UTC),
            fetcher=site,
            listings=scan,
        )
    assert capped.value.stopped == "page_limit"
    assert site.requested == [nbs_url(NBS, index) for index in range(LISTING_PAGES_PER_SITE)]

    # The site's other listing has no page left this run.
    with pytest.raises(ListingNotCovered) as other:
        refresh_official_context_document(
            paths,
            family="nbs_industrial_value_added",
            source_url=NBS_READINGS,
            expected_period="2026-02",
            fetched_at=datetime.now(UTC),
            fetcher=site,
            listings=scan,
        )
    assert (other.value.stopped, other.value.pages) == ("page_limit", 0)
    assert len(site.requested) == LISTING_PAGES_PER_SITE


def test_a_page_that_fails_its_reads_is_not_asked_for_again_each_period(tmp_path: Path) -> None:
    """A retrieval retries a transient failure; the run's other days do not add their own."""
    paths = runtime(tmp_path)
    site = Site({omo_url(1): omo_page(1, ["2026093008450000001"], following=2)})
    scan = ListingScan()

    for _try in range(3):
        with pytest.raises(KeyError):
            refresh_omo(paths, site, scan, "2026-09-01")
    with pytest.raises(ListingNotCovered) as unread:
        refresh_omo(paths, site, scan, "2026-08-31")

    assert unread.value.stopped == "unreadable_page"
    assert site.requested == [omo_url(1)] + [omo_url(2)] * 3


def test_lookups_inside_one_listing_scan_share_its_pages(tmp_path: Path) -> None:
    """A targeted run's official channel and the search candidates it checks read the
    listing once between them; each lookup outside one reads it afresh."""
    from pring_cycle.official_context import listing_scan

    paths = runtime(tmp_path)
    site = Site(omo_column())

    def refresh(day: str) -> None:
        refresh_official_context_document(
            paths,
            family="pbc_omo_notice",
            source_url=omo_url(1),
            expected_period=day,
            fetched_at=datetime.now(UTC),
            fetcher=site,
        )

    with listing_scan():
        refresh("2026-09-23")
        refresh("2026-09-24")
    assert [url for url in site.requested if url.startswith(OMO + "17081-")] == [
        omo_url(2),
        omo_url(3),
    ]
    refresh("2026-09-24")
    assert site.requested.count(omo_url(1)) == 2
