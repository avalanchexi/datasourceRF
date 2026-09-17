from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


def is_release_listing(family: str, source_url: str) -> bool:
    path = urlsplit(source_url).path
    if family in {"nbs_core_cpi", "nbs_ppi", "nbs_pmi"}:
        return path in {"/sj/zxfb/", "/sj/zxfbhjd/"}
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


def release_url(content: bytes, *, family: str, listing_url: str, period: str) -> str:
    parser = _ReleaseLinks()
    parser.feed(content.decode("utf-8-sig"))
    year, month = period.split("-")
    report = {
        "nbs_core_cpi": "居民消费价格",
        "nbs_ppi": "工业生产者出厂价格",
        "nbs_pmi": "中国采购经理指数运行情况",
        "pbc_money": "金融统计数据报告",
        "pbc_social_financing": "金融统计数据报告",
    }[family]
    period_label = rf"0?{int(month)}月份?"
    if family in {"pbc_money", "pbc_social_financing"}:
        aggregate = {3: "一季度", 6: "上半年", 9: "前三季度", 12: "全年|"}.get(int(month))
        if aggregate is not None:
            period_label = rf"(?:{period_label}|{aggregate})"
    pattern = rf"{year}年{period_label}{report}"
    matches = {
        urljoin(listing_url, href) for href, title in parser.links if re.match(pattern, title)
    }
    if len(matches) != 1:
        raise ValueError("official_context_release_link_not_unique")
    return matches.pop()
