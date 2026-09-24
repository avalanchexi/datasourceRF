"""News extraction rules: which sentences of a news or media text may give a P1/P2 value.

Each registered family lists one rule per metric and dimension member (ADR-0026). A rule
only recognizes the publisher's own wording, for example "2026年8月份，全国居民消费价格
同比上涨0.8%"; any other number in the text is never taken. A value is adopted only when
its sentence names the gap's due period. The sentence it came from is kept as the
matched quote, with the title, source, publication time and a hash of the text, for as
long as the value itself is kept.

Rules are written against real texts (tests/fixtures/news). A family whose members are
not all stated in the text (PPI's cumulative component averages appear only in the
official table) cannot be completed from the news; its values still land, and the model
input stays incomplete until another route fills the rest.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pring_cycle.evidence import MetricSeriesPoint

NEWS_RULES_VERSION = "news-rules-v0001"
RULE_NOT_MATCHED = "rule_not_matched"
PERIOD_MISMATCH = "period_mismatch"
# How a value came from a text, recorded with its matched quote.
MEDIA_PAGE = "media_page"
TUSHARE_NEWS = "tushare_news"
AI_WEBSEARCH = "ai_websearch"
MEDIA_PAGE_API = "media_page_get"

_VALUE = r"(?:(?P<dir>上涨|下降|增长|回落)(?P<value>\d+(?:\.\d+)?)%|(?P<flat>持平))"
_MONTH = r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月份?"
_YEAR_TO_MONTH = r"(?:(?P<year>\d{4})年)?1[—–\-－~至](?P<month>\d{1,2})月份?平均"
_SEP = r"[，,]\s*"


@dataclass(frozen=True)
class NewsRule:
    metric_id: str
    dimensions: tuple[tuple[str, str], ...]
    pattern: re.Pattern[str]


def _rule(metric_id: str, dimensions: dict[str, str], pattern: str) -> NewsRule:
    return NewsRule(metric_id, tuple(sorted(dimensions.items())), re.compile(pattern))


def _cpi(measure: str, pattern: str) -> NewsRule:
    return _rule("CN_CPI_HEADLINE", {"category": "headline", "measure": measure}, pattern)


def _ppi(category: str, measure: str, pattern: str) -> NewsRule:
    return _rule("CN_PPI", {"category": category, "measure": measure}, pattern)


_PPI_PRICES_IN = _MONTH + _SEP + "工业生产者出厂价格中" + _SEP
NEWS_RULES: dict[str, tuple[NewsRule, ...]] = {
    "nbs_core_cpi": (
        _cpi("yoy", _MONTH + _SEP + "全国居民消费价格同比" + _VALUE),
        _cpi("mom", _MONTH + _SEP + "全国居民消费价格环比" + _VALUE),
        _cpi(
            "cumulative_average_yoy", _YEAR_TO_MONTH + _SEP + "全国居民消费价格比上年同期" + _VALUE
        ),
    ),
    "nbs_ppi": (
        _ppi("headline", "yoy", _MONTH + _SEP + "全国工业生产者出厂价格同比" + _VALUE),
        _ppi(
            "headline",
            "mom",
            _MONTH + _SEP + "全国工业生产者出厂价格同比[^，,。]*" + _SEP + "环比" + _VALUE,
        ),
        _ppi(
            "headline",
            "cumulative_average_yoy",
            _YEAR_TO_MONTH + _SEP + "工业生产者出厂价格比上年同期" + _VALUE,
        ),
        _ppi("means_of_production", "yoy", _PPI_PRICES_IN + "生产资料价格同比" + _VALUE),
        _ppi("means_of_production", "mom", _PPI_PRICES_IN + "生产资料价格环比" + _VALUE),
        # The consumer-goods figure is the first "生活资料价格" sentence after the
        # producer-goods one, in the same paragraph (a breakdown may come between).
        _ppi(
            "consumer_goods",
            "yoy",
            _PPI_PRICES_IN + "生产资料价格同比[^\\n]*?。\\s*生活资料价格" + _VALUE,
        ),
        _ppi(
            "consumer_goods",
            "mom",
            _PPI_PRICES_IN + "生产资料价格环比[^\\n]*?。\\s*生活资料价格" + _VALUE,
        ),
    ),
}
NEWS_RULE_METRICS = frozenset(rule.metric_id for rules in NEWS_RULES.values() for rule in rules)


@dataclass(frozen=True)
class NewsValue:
    metric_id: str
    dimensions: dict[str, str]
    value: float
    quote: str


@dataclass(frozen=True)
class NewsExtraction:
    values: tuple[NewsValue, ...]
    # Why nothing was taken: the rules found no sentence, or only another period's.
    reason: str | None


def rules_for(metric_ids: tuple[str, ...]) -> tuple[NewsRule, ...]:
    wanted = set(metric_ids)
    return tuple(
        rule for rules in NEWS_RULES.values() for rule in rules if rule.metric_id in wanted
    )


def plain_text(content: str) -> str:
    """Readable text of an HTML or plain body: one line per paragraph, entities decoded."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", content)
    text = re.sub(r"(?i)</(p|div|h\d|li|tr)>|<br\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = text.replace("　", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def extract(metric_ids: tuple[str, ...], period: str, text: str) -> NewsExtraction:
    """The values the registered rules state for ``period`` (YYYY-MM) in ``text``.

    A member stated twice with different values is not taken: the text contradicts itself.
    """
    year, month = int(period[:4]), int(period[5:7])
    found: dict[tuple[str, tuple[tuple[str, str], ...]], list[NewsValue]] = {}
    other_period = False
    for rule in rules_for(metric_ids):
        for match in rule.pattern.finditer(text):
            if int(match["month"]) != month or (match["year"] and int(match["year"]) != year):
                other_period = True
                continue
            value = 0.0 if match["flat"] else float(match["value"])
            if match["dir"] in {"下降", "回落"}:
                value = -value
            found.setdefault((rule.metric_id, rule.dimensions), []).append(
                NewsValue(rule.metric_id, dict(rule.dimensions), value, _sentence(text, match))
            )
    values = tuple(items[0] for items in found.values() if len({item.value for item in items}) == 1)
    if values:
        return NewsExtraction(values, None)
    return NewsExtraction((), PERIOD_MISMATCH if other_period else RULE_NOT_MATCHED)


def _sentence(text: str, match: re.Match[str]) -> str:
    """The whole sentence(s) the rule matched: a recheck runs the same rule on it again."""
    start = max(text.rfind(mark, 0, match.start()) for mark in "。；\n") + 1
    ends = [position for mark in "。；\n" if (position := text.find(mark, match.end())) >= 0]
    return text[start : min(ends) + 1 if ends else len(text)].strip()


def page_title(content: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", content)
    return plain_text(match.group(1)) if match else ""


_PUBLISHED = (
    r"(?i)<meta[^>]+(?:property|name)=[\"'](?:article:published_time|pubdate|publishdate|"
    r"publish_time|og:release_date)[\"'][^>]+content=[\"']([^\"']+)",
    r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?\s+(\d{1,2}):(\d{2})",
)


def page_published_at(content: str) -> str | None:
    """The page's own publication time as written (a meta tag, else the first timestamp)."""
    meta = re.search(_PUBLISHED[0], content)
    if meta:
        return meta.group(1).strip()
    stamp = re.search(_PUBLISHED[1], plain_text(content))
    if stamp:
        year, month, day, hour, minute = stamp.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}:00+08:00"
    return None


def parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


MATCHED_QUOTE_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_matched_quote (
    claim_id TEXT PRIMARY KEY REFERENCES source_claim(claim_id),
    route TEXT NOT NULL,
    quote TEXT NOT NULL,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    published_at TEXT,
    body_hash TEXT NOT NULL,
    url TEXT,
    rules_version TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class MatchedQuote:
    claim_id: str
    route: str
    quote: str
    title: str
    source_name: str
    published_at: str | None
    body_hash: str
    url: str | None


def record_matched_quotes(connection: sqlite3.Connection, quotes: tuple[MatchedQuote, ...]) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO claim_matched_quote VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                q.claim_id,
                q.route,
                q.quote,
                q.title,
                q.source_name,
                q.published_at,
                q.body_hash,
                q.url,
                NEWS_RULES_VERSION,
            )
            for q in quotes
        ],
    )


def matched_quotes(
    connection: sqlite3.Connection, claim_ids: tuple[str, ...]
) -> list[dict[str, object]]:
    connection.row_factory = sqlite3.Row
    return [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM claim_matched_quote WHERE claim_id IN (SELECT value FROM json_each(?))",
            (json.dumps(list(claim_ids)),),
        )
    ]


def news_claims_matching_quotes(
    database: Path, points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]]
) -> set[str]:
    """Selected claims whose kept matched quote still gives their value under the rules.

    The original text is kept only a few days; the quote is kept as long as the claim.
    """
    from pring_cycle.storage import database_connection

    selected = {
        point.selected_claim_id: (metric_id, point)
        for metric_id, points in points_by_metric.items()
        for point in points
        if point.selected_claim_id is not None
    }
    if not selected:
        return set()
    with database_connection(database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='claim_matched_quote'"
        ).fetchone():
            return set()
        quotes = {str(row["claim_id"]): row for row in matched_quotes(connection, tuple(selected))}
    valid = set()
    for claim_id, row in quotes.items():
        metric_id, point = selected[claim_id]
        values = extract((metric_id,), point.period_start[:7], str(row["quote"])).values
        if any(
            item.dimensions == point.dimensions and item.value == point.selected_value
            for item in values
        ):
            valid.add(claim_id)
    return valid
