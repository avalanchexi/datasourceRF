from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def is_release_listing(family: str, source_url: str) -> bool:
    return release_listing(family, source_url) is not None


def release_listing(family: str, source_url: str) -> str | None:
    """The listing page the family's releases are looked up on, when ``source_url`` is one
    of its registered listings; None when it is not (a release page itself, say).

    The tool liquidity column is read through its index page: its directory answers 403.
    The central parity's column lists each day's announcement, the day in its path.
    The PBC statistics directory lists each year's tables, not releases, and the
    department's page only the latest few; the monthly financial statistics report, which
    carries money, loans and social financing, is listed page by page in its column.
    """
    path = urlsplit(source_url).path
    if family in _NBS_FAMILIES:
        return source_url if path in {"/sj/zxfb/", "/sj/zxfbhjd/"} else None
    if family == "pbc_omo_notice":
        return source_url if path == _OMO_LISTING else None
    if family == "pbc_tool_liquidity_monthly":
        return urljoin(source_url, "index.html") if path in _TOOL_LIQUIDITY_LISTING else None
    if family == "pbc_usdcny_central_parity":
        return urljoin(source_url, "index.html") if path in _CENTRAL_PARITY_LISTING else None
    if family in _PBC_REPORT_FAMILIES and path in _PBC_REPORT_LISTINGS:
        return urljoin(source_url, _PBC_REPORT_COLUMN)
    return None


class _ReleaseLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href is not None:
            self.links.append((self.href, re.sub(r"\s+", "", "".join(self.parts))))
            self.href = None


_OMO_LISTING = "/zhengcehuobisi/125207/125213/125431/125475/index.html"
# An OMO notice is dated only by its path: .../125475/2026092308513432696/index.html.
_OMO_NOTICE = re.compile(r"/125475/(20\d{6})\d+/index\.html$")
# An entry's day: an NBS release's file ("./202609/t20260915_1965263.html"), a PBC entry's
# directory (".../2026091417020862747/index.html"). Older PBC entries are not dated.
_ENTRY_DAY = re.compile(r"^\./20\d{4}/t(20\d{6})_|/(20\d{6})\d{6,}/index\.html$")
# The NBS list's page count and this page's index: createPageHTML(67, 0, "index", "html").
_NBS_PAGER = re.compile(r"createPageHTML\((\d+),\s*(\d+),")
_NBS_FAMILIES = {
    "nbs_core_cpi",
    "nbs_ppi",
    "nbs_pmi",
    "nbs_gdp",
    "nbs_industrial_finance",
    "nbs_industrial_value_added",
    "nbs_capacity_utilization",
}
_TOOL_LIQUIDITY_LISTING = {
    "/zhengcehuobisi/125207/125213/5727710/",
    "/zhengcehuobisi/125207/125213/5727710/index.html",
}
_CENTRAL_PARITY_LISTING = {
    "/zhengcehuobisi/125207/125217/125925/",
    "/zhengcehuobisi/125207/125217/125925/index.html",
}
# The families whose figures the PBC's monthly financial statistics report carries.
_PBC_REPORT_FAMILIES = {"pbc_money", "pbc_social_financing", "pbc_loan_structure"}
_PBC_REPORT_COLUMN = "/diaochatongjisi/116219/116225/index.html"
# The department's page and its statistics directory, as registered, and the column.
_PBC_REPORT_LISTINGS = {
    "/diaochatongjisi/116219/index.html",
    "/diaochatongjisi/116219/116319/index.html",
    _PBC_REPORT_COLUMN,
}
_AGGREGATE_MONTHS = {3: "一季度", 6: "上半年", 9: "前三季度", 12: "全年"}
# Same-period pieces that are not the release itself.
_NOT_THE_RELEASE = ("解读", "答记者问", "图解", "快报")


def _normal(title: str) -> str:
    title = re.sub(r"\s+", "", title).replace("月份", "月")
    return re.sub(r"年0(\d)月", r"年\1月", title)


def release_titles(family: str, period: str) -> tuple[str, ...]:
    """The release titles a listing entry may start with: the family's search template and
    the other titles it is registered under."""
    from pring_cycle.retrieval_registry import RETRIEVAL_FAMILIES, search_query, title_variants

    if family == "nbs_gdp" and not re.fullmatch(r"[0-9]{4}-Q[1-4]", period):
        raise ValueError("official_context_period_invalid")
    # Loans are in the monthly report: listed by its title, not by the search's narrowing.
    titled = "pbc_money" if family == "pbc_loan_structure" else family
    metric_id = RETRIEVAL_FAMILIES[titled].metric_ids[0]
    titles = [search_query((metric_id,), period), *title_variants(metric_id, period)]
    if family in _PBC_REPORT_FAMILIES:
        # PBC titles a quarter-end month's report by the quarter; December's by the year.
        # The report is the period's: the financial statistics report, or before September
        # 2025 social financing's own stock report (lookback 14).
        year, month = period[:4], int(period[5:7])
        report = titles[0].removeprefix(f"{year}年{month}月")
        aggregate = _AGGREGATE_MONTHS.get(month)
        if aggregate is not None:
            titles.append(f"{year}年{aggregate}{report}")
        if month == 12:
            titles.append(f"{year}年{report}")
    return tuple(_normal(title) for title in titles)


def release_url(content: bytes, *, family: str, listing_url: str, period: str) -> str | None:
    """The one release on this listing page for ``period``; None when the page has none.

    An entry is the release when its title starts with the family's release title for the
    period (the same wording search queries use) and it is not a reading of the release.
    A GDP title must be exactly the release title.
    """
    titles = release_titles(family, period)
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig"))
    matches = {
        urljoin(listing_url, href)
        for href, title in parser.links
        if not any(word in title for word in _NOT_THE_RELEASE)
        and any(
            _normal(title) == wanted if family == "nbs_gdp" else _normal(title).startswith(wanted)
            for wanted in titles
        )
    }
    if len(matches) > 1:
        raise ValueError("official_context_release_link_not_unique")
    return matches.pop() if matches else None


def release_urls(content: bytes, *, family: str, listing_url: str, period: str) -> tuple[str, ...]:
    """The releases on this listing page that may be the period's, in the listing's order.

    An OMO day can have several notices (a reverse repo, central bank bills), titled alike
    and dated only by their paths: each is a candidate, and parsing tells which it is. Every
    other family has at most the one release ``release_url`` selects.
    """
    if family != "pbc_omo_notice":
        found = release_url(content, family=family, listing_url=listing_url, period=period)
        return (found,) if found is not None else ()
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig", "replace"))
    day = period.replace("-", "")
    urls = [
        urljoin(listing_url, href)
        for href, _title in parser.links
        if href and (match := _OMO_NOTICE.search(href)) and match.group(1) == day
    ]
    return tuple(dict.fromkeys(urls))


def entry_days(content: bytes) -> list[str]:
    """The YYYYMMDD of each dated entry of the list itself, in its order (newest first).

    Fixed page links (contact, terms) are not entries and are left out.
    """
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig", "replace"))
    return [
        match.group(1) or match.group(2)
        for href, _title in parser.links
        if (match := _ENTRY_DAY.search(href or ""))
    ]


def listing_entries(content: bytes) -> list[str]:
    """What a page lists, to tell one page from another: its dated entries, else (a page
    of older, undated entries) every link on it."""
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig", "replace"))
    hrefs = [href for href, _title in parser.links if href]
    return [href for href in hrefs if _ENTRY_DAY.search(href)] or hrefs


def period_last_day(period: str) -> str:
    """The YYYYMMDD a day, month (YYYY-MM) or quarter (YYYY-Qn) ends on."""
    if len(period) == 10:
        return period.replace("-", "")
    month = int(period[-1]) * 3 if "-Q" in period else int(period[5:7])
    last = calendar.monthrange(int(period[:4]), month)[1]
    return f"{period[:4]}{month:02d}{last:02d}"


def reaches_back(days: list[str], period: str) -> bool:
    """Whether the pages read so far list everything published since ``period`` ended.

    A release comes out after its period: once an entry predates the period's last day, the
    release, if listed, was on the pages read. A day's notices may run on to the next page,
    so its own day does not reach back yet.
    """
    return bool(days) and min(days) < period_last_day(period)


# A retrieval's classification when the listing read stopped short of its period, followed
# by where it stopped: listing_not_covered_page_limit, ...
LISTING_NOT_COVERED = "listing_not_covered"


class ListingNotCovered(ValueError):
    """The listing read stopped before reaching back to the period: its release may be
    listed further back, so not finding it says nothing about whether it was published.

    ``stopped`` says where: ``page_limit`` (the run's pages of the site are read),
    ``repeated_page`` (a page listed what the one before did), ``unreadable_page`` (a page
    failed each read the run made of it) or ``last_page``.
    """

    def __init__(self, stopped: str, pages: int, oldest: str | None) -> None:
        super().__init__("official_listing_not_covered")
        self.stopped = stopped
        self.pages = pages
        self.oldest = oldest


def next_listing_page(content: bytes, page_url: str) -> str | None:
    """The listing's next page: named in a PBC column's pager, counted in the NBS list's;
    None on the last page, and on a page without a pager."""
    if (following := chronicle_next_page(content, page_url)) is not None:
        return following
    match = _NBS_PAGER.search(content.decode("utf-8-sig", "replace"))
    if match is None or int(match[2]) + 1 >= int(match[1]):
        return None
    return urljoin(page_url, f"index_{int(match[2]) + 1}.html")


RRR_CHRONICLE_LISTING = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125963/index.html"
# "2026年上半年中国货币政策大事记"; before 2021 a quarter's issue is titled by the quarter.
_CHRONICLE_TITLE = re.compile(
    r"^(?P<year>20\d{2})年(?P<part>第一季度|第二季度|第三季度|第四季度|上半年|前三季度)?"
    r"中国货币政策大事记$"
)
_CHRONICLE_THROUGH = {
    "第一季度": 3,
    "第二季度": 6,
    "上半年": 6,
    "第三季度": 9,
    "前三季度": 9,
    "第四季度": 12,
    None: 12,
}


@dataclass(frozen=True)
class ChronicleEntry:
    """One issue of the PBC's monetary policy chronicle: its year, to which month it goes,
    and the day the column lists it as published."""

    url: str
    year: int
    through_month: int
    published: str


class _DatedLinks(_ReleaseLinks):
    """Links with the first date (YYYY-MM-DD) written after each, as the column lists it."""

    def __init__(self) -> None:
        super().__init__()
        self.dates: dict[int, str] = {}

    def handle_data(self, data: str) -> None:
        super().handle_data(data)
        last = len(self.links) - 1
        if (
            self.href is None
            and last not in self.dates
            and self.links
            and (match := re.search(r"20\d{2}-\d{2}-\d{2}", data))
        ):
            self.dates[last] = match.group(0)


def chronicle_entries(content: bytes, listing_url: str) -> tuple[ChronicleEntry, ...]:
    """The chronicle issues on one page of the column, in its order (newest first)."""
    parser = _DatedLinks()
    parser.feed(content.decode("utf-8-sig", "replace"))
    entries = []
    for index, (href, title) in enumerate(parser.links):
        match = _CHRONICLE_TITLE.match(title)
        if match is None or index not in parser.dates:
            continue
        entries.append(
            ChronicleEntry(
                urljoin(listing_url, href),
                int(match["year"]),
                _CHRONICLE_THROUGH[match["part"]],
                parser.dates[index],
            )
        )
    return tuple(entries)


def chronicle_next_page(content: bytes, listing_url: str) -> str | None:
    """The column's next page, from its pager ("下一页" names it in ``tagname``)."""
    match = re.search(
        r"<a[^>]*tagname=\"(?P<page>[^\"\[][^\"]*)\"[^>]*>\s*下一页\s*</a>",
        content.decode("utf-8-sig", "replace"),
    )
    return urljoin(listing_url, match["page"]) if match else None
