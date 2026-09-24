"""TuShare news: one pull of `major_news` per full run, read locally by every gap (ADR-0026).

The pull covers the time since the last successful full run's cutoff (the last three days
on a first run), page by page: the interface returns at most 400 items per call, newest
first, so each next call ends where the last page's oldest item was. Every page is kept as
an acquisition of the run's batch. A failed or unauthorized pull is recorded there and the
run carries on without it.

A gap is then filled from these items when the family's news rules find the due period's
sentences in them (P1/P2 only). Each value keeps its matched quote; the originals are
deleted a few days later by retention, and the quotes stay as long as the values.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.runs import RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_connection

NEWS_API = "major_news"
NEWS_FIELDS = ("title", "content", "pub_time", "src")
PAGE_LIMIT = 400
FIRST_RUN_SPAN = timedelta(days=3)
# Originals older than this are deleted at the end of a successful run.
NEWS_ORIGINAL_RETENTION = timedelta(days=3)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_MAX_PAGES = 200

NewsTransport = Callable[[dict[str, Any]], bytes]


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
    """From the last successful full run's cutoff (or three days back) to ``end``."""
    with database_connection(paths.database) as connection:
        row = connection.execute(
            "SELECT max(system_as_of) FROM parent_run WHERE status='completed' "
            "AND command_type IN ('manual_full', 'scheduled_full') AND run_id<>?",
            (run.run_id,),
        ).fetchone()
    previous = datetime.fromisoformat(row[0]) if row and row[0] else None
    start = previous if previous is not None and previous < end else end - FIRST_RUN_SPAN
    return start, end


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
            if not isinstance(document, dict) or int(document.get("code", -1)) != 0:
                raise ValueError("tushare_source_failed")
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
            outcome = "source_failed" if isinstance(error, OSError | TimeoutError) else str(error)
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
    return outcome


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
    from pring_cycle.news_rules import (
        TUSHARE_NEWS,
        TakenValue,
        extract,
        plain_text,
        rules_for,
        store_news_values,
        text_hash,
    )

    scope = run.retrieval_scope
    assert scope is not None
    if scope.priority == "P0" or not rules_for(scope.metric_ids):
        return ()
    taken: dict[tuple[str, str], TakenValue] = {}
    for item in run_news(paths, run.run_id):
        if item.published_at > run.system_as_of:
            continue
        text = plain_text(item.content)
        for value in extract(scope.metric_ids, scope.period, text).values:
            taken.setdefault(
                (value.metric_id, json.dumps(value.dimensions, sort_keys=True)),
                TakenValue(
                    value,
                    item.title,
                    item.source,
                    item.published_at.isoformat(),
                    text_hash(text),
                    None,
                    item.acquisition_id,
                    item.fetched_at,
                    item.published_at,
                ),
            )
    if not taken:
        return ()
    return store_news_values(
        paths.database,
        tuple(taken.values()),
        route=TUSHARE_NEWS,
        provider=TUSHARE_NEWS,
        source_reference=lambda t: f"{TUSHARE_NEWS}:{t.acquisition_id}#{t.body_hash}",
        period=scope.period,
        definition_version=definition_version,
        available_at=_now(),
    )


def _now() -> datetime:
    from pring_cycle.retrieval_ledger import utc_now

    return utc_now()
