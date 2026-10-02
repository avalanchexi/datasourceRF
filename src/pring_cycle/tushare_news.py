"""TuShare news: one pull of `major_news` per full run, read locally by every gap (ADR-0026).

The pull reads on from where the last complete pull of a successful full run ended, a week
back at most, page by page: the interface returns at most 400 items per call, newest first,
so each next call ends where the last page's oldest item was. Every page is kept as an
acquisition of the run's batch. A failed, unauthorized or rate-limited pull (the interface
allows 40 calls a day) is recorded there and the run carries on without it; the next run
reads its window again.

A gap is then filled from these items when the family's news rules find the due period's
sentences in them (P1/P2 only). Each value keeps its matched quote; the originals are
deleted a few days later by retention, and the quotes stay as long as the values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository, SourceFailed
from pring_cycle.runs import RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TushareRefused
from pring_cycle.storage import database_connection
from pring_cycle.tushare_quota import TushareCallNotAttempted

if TYPE_CHECKING:
    from pring_cycle.news_rules import NewsValue, TakenValue

NEWS_API = "major_news"
NEWS_FIELDS = ("title", "content", "pub_time", "src")
PAGE_LIMIT = 400
# A week covers a weekend's releases on a first run, and about 20 pages: half a day's quota.
NEWS_LOOKBACK = timedelta(days=7)
# Originals older than this are deleted at the end of a successful run.
NEWS_ORIGINAL_RETENTION = timedelta(days=3)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_MAX_PAGES = 200

NewsTransport = Callable[[dict[str, Any]], bytes]
# Read from every run's news on the day their sentences name, not for a gap (ADR-0028).
NEWS_EVENT_METRICS = frozenset({"CN_RRR_EVENT"})


@dataclass(frozen=True)
class NewsItem:
    title: str
    content: str
    published_at: datetime
    source: str
    content_sha256: str
    acquisition_id: str
    fetched_at: datetime


def _stamp(value: datetime) -> str:
    return value.astimezone(_SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def _published(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_SHANGHAI)


def news_window(paths: RuntimePaths, run: RunRecord, end: datetime) -> tuple[datetime, datetime]:
    """From where the last complete pull before ``end`` ended, a week back at most, to ``end``.

    Runs chain by what their pulls read, not by their cutoffs: a run cut off on Monday for
    Friday read nothing after Friday. A pull with a failed page, or held back for the day's
    quota, read only part of its window, so it is passed over; a rerun for the same day
    passes over its predecessor's pull.
    """
    # The interface takes whole seconds: a target day's end (23:59:59.999999) is 23:59:59.
    end = _published(_stamp(end))
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT max(json_extract(a.parameters_json, '$.end_date')) "
            "FROM full_run_acquisition o JOIN acquisition_request a USING(acquisition_id) "
            "JOIN parent_run r ON r.run_id=o.run_id WHERE a.api_name=? AND o.run_id<>? "
            "AND r.status='completed' AND r.command_type IN ('manual_full', 'scheduled_full') "
            "AND o.run_id NOT IN (SELECT started.run_id FROM full_run_gap_plan AS started "
            "LEFT JOIN full_run_gap_plan AS ended ON ended.run_id=started.run_id "
            "AND ended.phase='news_pull' WHERE started.phase='news_pull_started' "
            "AND coalesce(json_extract(ended.document_json, '$.outcome'), '') "
            "<> 'verified_candidate') "
            "GROUP BY o.run_id HAVING sum(a.state<>'validated')=0",
            (NEWS_API, run.run_id),
        ).fetchall()
    read = [_published(row[0]) for row in rows]
    return max([end - NEWS_LOOKBACK, *(stop for stop in read if stop < end)]), end


def _post(payload: dict[str, Any]) -> bytes:
    from pring_cycle import tushare_context
    from pring_cycle.http_transport import NoRedirect
    from pring_cycle.source_adapters import TUSHARE_ENDPOINT

    request = Request(
        TUSHARE_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    # The TuShare context layer's opener, so one transport serves every TuShare call.
    opener = getattr(tushare_context, "build_opener")(NoRedirect())  # noqa: B009
    with opener.open(request, timeout=60) as response:
        return bytes(response.read())


def pull_news(
    paths: RuntimePaths,
    run: RunRecord,
    token: str,
    *,
    end: datetime,
    transport: NewsTransport | None = None,
) -> str:
    """Pull this run's news into its batch; a failure stays on its acquisition, not raised."""
    from pring_cycle.tushare_context import _response_rows

    start, stop = news_window(paths, run, end)
    # Started, so a pull cut off before it ends is not taken for a whole one (ticket 31).
    _record_pull(paths, run.run_id, "news_pull_started", "started")
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    send = transport or _post
    seen: set[str] = set()
    outcome = "verified_candidate"
    for _page in range(_MAX_PAGES):
        params = {"start_date": _stamp(start), "end_date": _stamp(stop)}
        payload = {
            "api_name": NEWS_API,
            "fields": ",".join(NEWS_FIELDS),
            "params": params,
            "token": token,
        }

        def parse(raw: bytes, params: dict[str, str] = params) -> tuple[dict[str, object], ...]:
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("tushare_response_invalid")
            if (code := int(document.get("code", -1))) != 0:
                # Its code kept on the exception and read, with its message, as the other
                # TuShare paths read them (ticket 22).
                raise TushareRefused(code, document.get("msg"))
            rows = _response_rows(document, required_fields=NEWS_FIELDS)
            for row in rows:
                published = _published(str(row["pub_time"]))
                if (
                    not _published(params["start_date"])
                    <= published
                    <= _published(params["end_date"])
                ):
                    raise ValueError("tushare_news_outside_window")
            return rows

        try:
            acquired = acquisitions.capture(
                provider="tushare",
                api_name=NEWS_API,
                parameters=params,
                fields=",".join(NEWS_FIELDS),
                parser_version="tushare-news-v0001",
                fetch=partial(send, payload),
                parse=parse,
                normalize=lambda rows: {"count": len(rows)},
            )
        except (OSError, TimeoutError, ValueError) as error:
            outcome = (
                error.condition
                if isinstance(error, TushareCallNotAttempted)
                else (
                    "tushare_rate_limited"
                    if error.classification == "rate_limited"
                    else "tushare_source_failed"
                )
                if isinstance(error, SourceFailed)
                else "source_failed"
                if isinstance(error, OSError | TimeoutError)
                else str(error)
            )
            break
        rows = acquired.value
        fresh = [row for row in rows if _item_key(row) not in seen]
        seen.update(_item_key(row) for row in rows)
        if len(rows) < PAGE_LIMIT or not fresh:
            break
        oldest = min(_published(str(row["pub_time"])) for row in rows)
        if oldest <= start or oldest >= stop:
            break
        stop = oldest
    _record_pull(paths, run.run_id, "news_pull", outcome)
    return outcome


def _record_pull(paths: RuntimePaths, run_id: str, phase: str, outcome: str) -> None:
    """That the run's pull started, or how it first ended: one held back for the quota, or
    cut off, left no failed page to say it read only part of its window (ticket 31)."""
    document = json.dumps({"outcome": outcome}, sort_keys=True)
    with database_connection(paths.database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='full_run_gap_plan'"
        ).fetchone():
            return
        connection.execute(
            "INSERT OR IGNORE INTO full_run_gap_plan VALUES (?, ?, ?, ?)",
            (run_id, phase, document, hashlib.sha256(document.encode()).hexdigest()),
        )


def _item_key(row: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps([row.get("pub_time"), row.get("title"), row.get("content")]).encode()
    ).hexdigest()


def run_news(paths: RuntimePaths, run_id: str) -> tuple[NewsItem, ...]:
    """Every item this run's pull kept, once each, oldest first."""
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    with database_connection(paths.database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='full_run_acquisition'"
        ).fetchone():
            return ()
        ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT a.acquisition_id FROM full_run_acquisition o JOIN acquisition_request a "
                "USING(acquisition_id) WHERE o.run_id=? AND a.api_name=? AND a.state='validated' "
                "ORDER BY o.rowid",
                (run_id, NEWS_API),
            )
        ]
    items: dict[str, NewsItem] = {}
    for acquisition_id in ids:
        try:
            document = json.loads(acquisitions.read_content(acquisition_id, "raw"))
        except (LookupError, OSError, ValueError):
            continue
        received = acquisitions.get(acquisition_id).received_at
        assert received is not None
        fields = document["data"]["fields"]
        for values in document["data"]["items"]:
            row = dict(zip(fields, values, strict=True))
            key = _item_key(row)
            content = str(row.get("content") or "")
            items.setdefault(
                key,
                NewsItem(
                    str(row.get("title") or ""),
                    content,
                    _published(str(row["pub_time"])),
                    str(row.get("src") or ""),
                    hashlib.sha256(content.encode()).hexdigest(),
                    acquisition_id,
                    received,
                ),
            )
    return tuple(sorted(items.values(), key=lambda item: item.published_at))


def fill_from_news(
    paths: RuntimePaths,
    run: RunRecord,
    *,
    definition_version: str,
) -> tuple[str, ...]:
    """Store the due period's values the news rules find in this run's news, with quotes.

    Items published after the run's cutoff are not read. The first item to state a member
    gives it; a later item stating another value for it is ignored.
    """
    from pring_cycle.news_rules import extract, rules_for

    scope = run.retrieval_scope
    assert scope is not None
    if scope.priority == "P0" or not rules_for(scope.metric_ids):
        return ()
    taken: dict[tuple[str, str], TakenValue] = {}
    for item, text in _readable(paths, run):
        for value in extract(scope.metric_ids, scope.period, text).values:
            taken.setdefault(_member(value), _taken(value, item, text))
    if not taken:
        return ()
    return _store(paths, tuple(taken.values()), scope.period, definition_version)


def fill_events_from_news(
    paths: RuntimePaths,
    run: RunRecord,
    *,
    metric_ids: tuple[str, ...],
    definition_version: str,
) -> tuple[str, ...]:
    """Store the events this run's news states, each on the effective day its sentence names.

    No gap asks for an event (an RRR change has no due period): the news is read for one
    on every run, and what was held stays the baseline when it states none (ADR-0028).
    """
    from pring_cycle.news_rules import extract, stated_event_days

    by_day: dict[str, dict[tuple[str, str], TakenValue]] = {}
    for item, text in _readable(paths, run):
        for day in stated_event_days(metric_ids, text, published=item.published_at.date()):
            for value in extract(metric_ids, day, text).values:
                by_day.setdefault(day, {}).setdefault(_member(value), _taken(value, item, text))
    stored: list[str] = []
    for day, taken in sorted(by_day.items()):
        values = tuple(taken.values())
        stored += _store(paths, values, day, definition_version, published_is_public=True)
    return tuple(stored)


def _readable(paths: RuntimePaths, run: RunRecord) -> Iterator[tuple[NewsItem, str]]:
    """The run's news items published by its cutoff, with their plain text."""
    from pring_cycle.news_rules import plain_text

    for item in run_news(paths, run.run_id):
        if item.published_at <= run.system_as_of:
            yield item, plain_text(item.content)


def _member(value: NewsValue) -> tuple[str, str]:
    return value.metric_id, json.dumps(value.dimensions, sort_keys=True)


def _taken(value: NewsValue, item: NewsItem, text: str) -> TakenValue:
    from pring_cycle.news_rules import TakenValue, text_hash

    return TakenValue(
        value=value,
        title=item.title,
        source_name=item.source,
        published_at=item.published_at.isoformat(),
        body_hash=text_hash(text),
        url=None,
        acquisition_id=item.acquisition_id,
        fetched_at=item.fetched_at,
        release_at=item.published_at,
    )


def _store(
    paths: RuntimePaths,
    taken: tuple[TakenValue, ...],
    period: str,
    definition_version: str,
    *,
    published_is_public: bool = False,
) -> tuple[str, ...]:
    from pring_cycle.news_rules import TUSHARE_NEWS, store_news_values

    return store_news_values(
        paths.database,
        taken,
        route=TUSHARE_NEWS,
        provider=TUSHARE_NEWS,
        source_reference=lambda t: f"{TUSHARE_NEWS}:{t.acquisition_id}#{t.body_hash}",
        period=period,
        definition_version=definition_version,
        available_at=_now(),
        published_is_public=published_is_public,
    )


def _now() -> datetime:
    from pring_cycle.retrieval_ledger import utc_now

    return utc_now()
