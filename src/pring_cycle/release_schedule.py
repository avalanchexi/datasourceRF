"""Release pre-announcements, used before the inferred release time (ticket 25).

A registered source's release time is first taken from a pre-announcement: TuShare
``cn_schedule``, then the National Bureau of Statistics' yearly release schedule page read
by its parser. Anything else is discarded. With no pre-announcement for a period, freshness
falls back to the Nth SSE trading day after the period end; that is not a gap.

Each batch records the entries it received (``release_schedule``), and freshness reads them
for the rest of the run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TushareRefused
from pring_cycle.storage import database_connection
from pring_cycle.tushare_quota import TushareCallNotAttempted

SHANGHAI = ZoneInfo("Asia/Shanghai")
CN_SCHEDULE = "tushare:cn_schedule"
NBS_SCHEDULE_PAGE = "nbs:schedule_page"
NBS_SCHEDULE_PARSER = "nbs-release-schedule-parser-v0001"
# The NBS yearly schedule page, registered per year (host and path are the whitelist).
NBS_SCHEDULE_PAGES = {
    2026: "https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html",
}
# Freshness source → (cn_schedule data_api, NBS schedule row title). A source that neither
# names keeps its inferred release time.
SCHEDULE_ITEMS: dict[str, tuple[str | None, str | None]] = {
    "tushare:cn_pmi": ("cn_pmi", "采购经理指数月度报告"),
    "tushare:cn_cpi": ("cn_cpi", "居民消费价格指数月度报告"),
    "nbs:core_cpi": ("cn_cpi", "居民消费价格指数月度报告"),
    "tushare:cn_ppi": ("cn_ppi", "工业生产者价格指数月度报告"),
    "nbs:industrial_va": (None, "规模以上工业生产月度报告"),
    "nbs:industrial_finance": (None, "工业经济效益月度报告"),
    "nbs:capacity_utilization": (None, "全国工业产能利用率季度报告"),
    "tushare:cn_gdp": ("cn_gdp", "国民经济运行情况"),
    "tushare:cn_m": ("cn_m", None),
    "tushare:sf_month": ("sf_month", None),
    "pbc:social_financing": ("sf_month", None),
    "pbc:loan_structure": ("sf_month", None),
}

RELEASE_SCHEDULE_SCHEMA = """
CREATE TABLE IF NOT EXISTS release_schedule (
    batch_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    item TEXT NOT NULL,
    publish_date TEXT NOT NULL,
    publish_time TEXT,
    acquisition_id TEXT REFERENCES acquisition_request(acquisition_id),
    PRIMARY KEY(batch_id, origin, item, publish_date)
);
"""


@dataclass(frozen=True)
class ScheduleEntry:
    origin: str
    item: str
    publish_date: date
    publish_time: time | None


def parse_cn_schedule(raw: bytes) -> tuple[ScheduleEntry, ...]:
    """TuShare ``cn_schedule`` rows: each API's scheduled publication date."""
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError("cn_schedule_response_not_object")
    if (code := document.get("code")) != 0 and isinstance(code, int):
        # TuShare's refusal, read as its other interfaces' are (tickets 22, 31).
        raise TushareRefused(code, document.get("msg"))
    data = document.get("data")
    if document.get("code") != 0 or not isinstance(data, dict):
        raise ValueError("cn_schedule_source_failed")
    fields, items = data.get("fields"), data.get("items")
    if not isinstance(fields, list) or not isinstance(items, list):
        raise ValueError("cn_schedule_rows_missing")
    if not {"publish_date", "data_api"} <= set(fields):
        raise ValueError("cn_schedule_fields_missing")
    entries = []
    for item in items:
        row = dict(zip(fields, item, strict=True))
        api = row.get("data_api")
        if not api:
            continue
        entries.append(
            ScheduleEntry(
                CN_SCHEDULE,
                str(api),
                datetime.strptime(str(row["publish_date"]), "%Y%m%d").date(),
                None,
            )
        )
    return tuple(entries)


class _Table(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", "", "".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_nbs_schedule(raw: bytes, *, year: int) -> tuple[ScheduleEntry, ...]:
    """The NBS schedule table: a row per release with a day in each month, then its times."""
    table = _Table()
    table.feed(raw.decode("utf-8"))
    header = ["序号", "内容", *(f"{month}月" for month in range(1, 13))]
    if f"{year}年国家统计局主要统计信息发布日程表" not in raw.decode("utf-8"):
        raise ValueError("nbs_schedule_identity_missing")
    if header not in table.rows:
        raise ValueError("nbs_schedule_table_missing")
    entries: dict[tuple[str, date], ScheduleEntry] = {}
    rows = table.rows
    for index, row in enumerate(rows):
        if len(row) != 14 or not row[0].isdigit():
            continue
        title, cells = row[1], row[2:]
        times = rows[index + 1] if index + 1 < len(rows) else []
        dated = [cell for cell in cells if cell != "……"]
        if len(times) != len(dated) or not all(re.fullmatch(r"\d{1,2}:\d{2}", t) for t in times):
            raise ValueError("nbs_schedule_times_mismatch")
        clock = iter(times)
        for month, cell in enumerate(cells, start=1):
            if cell == "……":
                continue
            at = time.fromisoformat(next(clock).zfill(5))
            days = re.findall(r"(\d{1,2})/[一二三四五六日]", cell)
            if not days:
                raise ValueError("nbs_schedule_day_missing")
            for day in days:
                published = date(year, month, int(day))
                entries[title, published] = ScheduleEntry(NBS_SCHEDULE_PAGE, title, published, at)
    if not entries:
        raise ValueError("nbs_schedule_rows_missing")
    return tuple(entries.values())


def _fetch_page(url: str) -> bytes:
    from pring_cycle.http_transport import open_no_redirects

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.stats.gov.cn":
        raise ValueError("nbs_schedule_url_not_official")
    request = Request(url, headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0"})
    with open_no_redirects(request, timeout=15) as response:
        if int(response.status) != 200 or response.geturl() != url:
            raise OSError("nbs_schedule_status_or_redirect")
        return bytes(response.read(2_000_000))


def _post_tushare(token: str, payload: dict[str, object]) -> bytes:
    from pring_cycle.tushare_context import TushareContextAdapter

    return TushareContextAdapter(token)._post({**payload, "token": token})


def _record_held_back(paths: RuntimePaths, batch_id: str, error: TushareCallNotAttempted) -> None:
    """The batch's note that ``cn_schedule`` was not asked, why and when (ticket 31)."""
    document = json.dumps(
        {"api_name": error.api_name, "at": datetime.now(UTC).isoformat(), "condition": str(error)},
        sort_keys=True,
    )
    with database_connection(paths.database) as connection:
        if (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='full_run_gap_plan'"
            ).fetchone()
            and connection.execute(
                "SELECT 1 FROM parent_run WHERE run_id=?", (batch_id,)
            ).fetchone()
        ):
            connection.execute(
                "INSERT OR IGNORE INTO full_run_gap_plan "
                "VALUES (?, 'release_schedule_held_back', ?, ?)",
                (batch_id, document, hashlib.sha256(document.encode()).hexdigest()),
            )


def refresh_release_schedule(paths: RuntimePaths, batch_id: str, target: date) -> int:
    """Record this batch's pre-announcements from ``cn_schedule`` and the NBS schedule page."""
    from pring_cycle.secrets import parse_data_source_secrets

    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
    received: list[tuple[ScheduleEntry, str]] = []
    if token is not None:
        fields = "month,publish_date,title,issuing_org,data_api"
        try:
            acquired = acquisitions.capture(
                provider="tushare",
                api_name="cn_schedule",
                parameters={},
                fields=fields,
                parser_version="tushare-cn-schedule-parser-v0001",
                fetch=lambda: _post_tushare(
                    token, {"api_name": "cn_schedule", "params": {}, "fields": fields}
                ),
                parse=parse_cn_schedule,
                normalize=lambda entries: [_document(entry) for entry in entries],
            )
            received.extend((entry, acquired.receipt.acquisition_id) for entry in acquired.value)
        except TushareCallNotAttempted as error:
            # Held back for TuShare's day: no call to record it on (ticket 31).
            _record_held_back(paths, batch_id, error)
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Recorded on the call; the NBS page is next.
    # The NBS page is always read: some sources (industrial output and profits, capacity
    # utilization) have no cn_schedule API, and it backs up the ones that do.
    url = NBS_SCHEDULE_PAGES.get(target.year)
    if url is not None:
        try:
            page = acquisitions.capture(
                provider="国家统计局",
                api_name="official_schedule_get",
                parameters={"source_url": url, "year": str(target.year)},
                fields="",
                parser_version=NBS_SCHEDULE_PARSER,
                fetch=lambda: _fetch_page(url),
                parse=lambda raw: parse_nbs_schedule(raw, year=target.year),
                normalize=lambda entries: [_document(entry) for entry in entries],
            )
            received.extend((entry, page.receipt.acquisition_id) for entry in page.value)
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Discarded; freshness falls back to the inferred release time.
    with database_connection(paths.database) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO release_schedule VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    batch_id,
                    entry.origin,
                    entry.item,
                    entry.publish_date.isoformat(),
                    entry.publish_time.isoformat() if entry.publish_time else None,
                    acquisition_id,
                )
                for entry, acquisition_id in received
            ],
        )
    return len(received)


def batch_schedule(database: Path, batch_id: str) -> dict[str, tuple[datetime | date, ...]]:
    """Per freshness source, the batch's announced publications, ``cn_schedule`` first.

    A date without a time (``cn_schedule``) takes the source's registered update time.
    """
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT origin, item, publish_date, publish_time FROM release_schedule "
            "WHERE batch_id=?",
            (batch_id,),
        ).fetchall()
    by_origin: dict[tuple[str, str], list[datetime | date]] = {}
    for origin, item, published, at in rows:
        day = date.fromisoformat(published)
        by_origin.setdefault((origin, item), []).append(
            datetime.combine(day, time.fromisoformat(at), SHANGHAI) if at else day
        )
    schedule: dict[str, tuple[datetime | date, ...]] = {}
    for source, (api, title) in SCHEDULE_ITEMS.items():
        announced = by_origin.get((CN_SCHEDULE, api or "")) or by_origin.get(
            (NBS_SCHEDULE_PAGE, title or "")
        )
        if announced:
            schedule[source] = tuple(sorted(announced, key=_day))
    return schedule


def latest_schedule(database: Path) -> dict[str, tuple[datetime | date, ...]]:
    """The pre-announcements of the latest batch that recorded any (for targeted runs)."""
    with database_connection(database) as connection:
        row = connection.execute(
            "SELECT batch_id FROM release_schedule ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    return batch_schedule(database, str(row[0])) if row is not None else {}


def _day(value: datetime | date) -> date:
    return value.date() if isinstance(value, datetime) else value


def _document(entry: ScheduleEntry) -> dict[str, str | None]:
    return {
        "origin": entry.origin,
        "item": entry.item,
        "publish_date": entry.publish_date.isoformat(),
        "publish_time": entry.publish_time.isoformat() if entry.publish_time else None,
    }
