from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def is_release_listing(family: str, source_url: str) -> bool:
    path = urlsplit(source_url).path
    if family in _NBS_FAMILIES:
        return path in {"/sj/zxfb/", "/sj/zxfbhjd/"}
    if family == "pbc_omo_notice":
        return path == _OMO_LISTING
    return (
        family in {"pbc_money", "pbc_social_financing"}
        and path == "/diaochatongjisi/116219/index.html"
    )


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
# Listing pages the NBS release list is followed back through (index, index_1, ...).
NBS_LISTING_PAGES = 10
_NBS_FAMILIES = {"nbs_core_cpi", "nbs_ppi", "nbs_pmi", "nbs_gdp", "nbs_industrial_finance"}
_AGGREGATE_MONTHS = {3: "一季度", 6: "上半年", 9: "前三季度", 12: "全年"}
# Same-period pieces that are not the release itself.
_NOT_THE_RELEASE = ("解读", "答记者问", "图解", "快报")


def listing_page_url(family: str, listing_url: str, page: int) -> str | None:
    """The ``page``-th page of a release listing; only the NBS list goes back by pages."""
    if page == 0:
        return listing_url
    if family in _NBS_FAMILIES and page < NBS_LISTING_PAGES:
        return urljoin(listing_url, f"index_{page}.html")
    return None


def _normal(title: str) -> str:
    title = re.sub(r"\s+", "", title).replace("月份", "月")
    return re.sub(r"年0(\d)月", r"年\1月", title)


def release_titles(family: str, period: str) -> tuple[str, ...]:
    """The release title a listing entry must start with: the family's search template."""
    from pring_cycle.retrieval_registry import RETRIEVAL_FAMILIES, search_query

    if family == "nbs_gdp" and not re.fullmatch(r"[0-9]{4}-Q[1-4]", period):
        raise ValueError("official_context_period_invalid")
    titles = [search_query((RETRIEVAL_FAMILIES[family].metric_ids[0],), period)]
    if family in {"pbc_money", "pbc_social_financing"}:
        # PBC titles a quarter-end month's report by the quarter; December's by the year.
        aggregate = _AGGREGATE_MONTHS.get(int(period[5:7]))
        if aggregate is not None:
            titles.append(f"{period[:4]}年{aggregate}金融统计数据报告")
        if period[5:7] == "12":
            titles.append(f"{period[:4]}年金融统计数据报告")
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


def listing_months(content: bytes) -> list[str]:
    """The YYYYMM of each entry of the list itself ("./202609/t20260915_..."), newest first.

    Fixed page links (contact, terms) are not entries and are left out.
    """
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig", "replace"))
    return [
        match.group(1)
        for href, _title in parser.links
        if (match := re.match(r"\./(20\d{4})/t\d{8}", href or ""))
    ]


def period_last_month(period: str) -> str:
    if "-Q" in period:
        return f"{period[:4]}{int(period[-1]) * 3:02d}"
    return period[:4] + period[5:7]


def worth_older_pages(months: list[str], period: str) -> bool:
    """Whether a release missing from a page may still be further down the NBS list.

    Not once the page already reaches back to the period's last month (a release comes out
    after its period), and not for a period more than six months older than the list's
    newest entry: ten pages cover a few months, so a history period is not listed at all.
    """
    if not months:
        return False
    last = period_last_month(period)
    if min(months) <= last:
        return False
    newest = max(months)
    gap = (int(newest[:4]) - int(last[:4])) * 12 + int(newest[4:]) - int(last[4:])
    return gap <= 6
