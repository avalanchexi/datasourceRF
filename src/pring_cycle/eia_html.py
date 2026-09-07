from __future__ import annotations

import codecs
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from email.message import Message
from html.parser import HTMLParser
from math import isfinite
from urllib.error import HTTPError

from pring_cycle.acquisition import AcquisitionRepository, utc_now
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.runtime import RuntimePaths

_SOURCES = {
    "RBRTE": (
        "EIA_BRENT_RBRTE",
        "Europe Brent Spot Price FOB",
        "https://www.eia.gov/dnav/pet/hist/RBRTED.htm",
    ),
    "RWTC": (
        "EIA_WTI_RWTC",
        "Cushing, OK WTI Spot Price FOB",
        "https://www.eia.gov/dnav/pet/hist/RWTCD.htm",
    ),
}
_PROVIDER = "U.S. Energy Information Administration"
_MAX_BYTES = 4_000_000
_MONTHS = {
    name: i
    for i, name in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}
_MISSING = {
    "": "blank",
    "-": "no_data_reported",
    "--": "not_applicable",
    "NA": "not_available",
    "W": "withheld",
}


@dataclass(frozen=True)
class FetchedEiaHistory:
    content: bytes
    final_url: str
    http_status: int
    media_type: str


@dataclass(frozen=True)
class EiaHistoryCell:
    business_date: date
    value: float | None
    state: str
    source_text: str


@dataclass(frozen=True)
class EiaHistoryBatch:
    series_id: str
    endpoint: str
    description: str
    unit: str
    release_date: date
    next_release_date: date
    release_timezone: str
    release_precision: str
    source_upstream: str
    cells: tuple[EiaHistoryCell, ...]
    total_calendar_cells: int


@dataclass(frozen=True)
class EiaHistoryIngestionResult:
    status: str
    acquisition_id: str
    metric_id: str
    observation_count: int
    missing_cell_count: int
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    condition: str | None


def _clean(value: str) -> str:
    return " ".join(value.split())


def _charset(value: str) -> str:
    try:
        encoding = codecs.lookup(value).name
    except LookupError as error:
        raise ValueError("eia_history_charset_unsupported") from error
    if encoding not in {"utf-8", "ascii"}:
        raise ValueError("eia_history_charset_unsupported")
    return encoding


def _http_charset(media_type: str) -> str | None:
    header = Message()
    header["Content-Type"] = media_type
    declarations = [value for key, value in (header.get_params() or []) if key.lower() == "charset"]
    if len(declarations) > 1:
        raise ValueError("eia_history_charset_conflict")
    return _charset(str(declarations[0])) if declarations else None


class _HistoryTable(HTMLParser):
    def __init__(self, title: str) -> None:
        super().__init__(convert_charrefs=True)
        self.expected_title = title
        self.depth = 0
        self.data_depth: int | None = None
        self.table_count = 0
        self.row: list[str] | None = None
        self.row_is_spacer = False
        self.cell: list[str] | None = None
        self.rows: list[tuple[str, ...]] = []
        self.in_title = False
        self.title: list[str] = []
        self.text: list[str] = []
        self.html_closed = False
        self.declared_encodings: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self.declared_encodings.extend(
                _charset(value or "") for key, value in attrs if key == "charset"
            )
            attributes = dict(attrs)
            if (attributes.get("http-equiv") or "").lower() == "content-type":
                encoding = _http_charset(attributes.get("content") or "")
                if encoding is not None:
                    self.declared_encodings.append(encoding)
        if tag == "title":
            self.in_title = True
        if tag == "table":
            self.depth += 1
            if self.data_depth is not None:
                raise ValueError("eia_history_nested_data_table")
            if _clean(dict(attrs).get("summary") or "") == self.expected_title:
                self.table_count += 1
                self.data_depth = self.depth
        if self.data_depth is None:
            return
        if tag == "tr":
            if self.row is not None:
                raise ValueError("eia_history_row_not_closed")
            self.row = []
            self.row_is_spacer = False
        if tag in {"td", "th"}:
            if self.row is None or self.cell is not None:
                raise ValueError("eia_history_cell_structure_invalid")
            attributes = dict(attrs)
            if any(attributes.get(span) not in {None, "1"} for span in ("colspan", "rowspan")):
                raise ValueError("eia_history_cell_span_invalid")
            if not self.row and tag == "td":
                self.row_is_spacer = dict(attrs).get("height") == "3"
            self.cell = []

    def handle_data(self, data: str) -> None:
        self.text.append(_clean(data))
        if self.in_title:
            self.title.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "html":
            self.html_closed = True
        if self.data_depth is not None:
            if tag in {"td", "th"}:
                if self.cell is None or self.row is None:
                    raise ValueError("eia_history_cell_structure_invalid")
                self.row.append(_clean("".join(self.cell)))
                self.cell = None
            if tag == "tr":
                if self.row is None or self.cell is not None:
                    raise ValueError("eia_history_row_structure_invalid")
                # The published table inserts a six-cell, height=3 blank
                # layout row every five weeks; it has no observation date.
                if not (self.row_is_spacer and len(self.row) == 6 and not any(self.row)):
                    self.rows.append(tuple(self.row))
                self.row = None
            if tag == "table" and self.depth == self.data_depth:
                if self.row is not None or self.cell is not None:
                    raise ValueError("eia_history_table_not_closed")
                self.data_depth = None
        if tag == "table":
            self.depth -= 1


def _release_date(text: list[str], label: str) -> date:
    matches = [re.fullmatch(re.escape(label) + r":\s*(\d+)/(\d+)/(\d{4})", t) for t in text]
    found = [match for match in matches if match is not None]
    if len(found) != 1:
        raise ValueError("eia_history_release_metadata_invalid")
    month, day, year = map(int, found[0].groups())
    return date(year, month, day)


def parse_eia_history_document(
    content: bytes,
    *,
    series_id: str,
    start_date: date,
    end_date: date,
    http_charset: str | None = None,
) -> EiaHistoryBatch:
    if series_id not in _SOURCES or end_date < start_date:
        raise ValueError("eia_history_request_invalid")
    if not content or len(content) > _MAX_BYTES:
        raise ValueError("eia_history_response_size_invalid")
    _, description, endpoint = _SOURCES[series_id]
    title = f"{description} (Dollars per Barrel)"
    encoding = _charset(http_charset) if http_charset is not None else None
    parser = _HistoryTable(title)
    try:
        parser.feed(content.decode("utf-8-sig"))
        parser.close()
        declarations = set(parser.declared_encodings) | (
            {encoding} if encoding is not None else set()
        )
        if len(declarations) > 1:
            raise ValueError("eia_history_charset_conflict")
        if "ascii" in declarations:
            content.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("eia_history_encoding_invalid") from error
    if (
        not parser.html_closed
        or parser.data_depth is not None
        or parser.table_count != 1
        or _clean("".join(parser.title)) != title
    ):
        raise ValueError("eia_history_source_table_identity_invalid")
    if not parser.rows or parser.rows[0] != ("Week Of", "Mon", "Tue", "Wed", "Thu", "Fri"):
        raise ValueError("eia_history_daily_columns_invalid")
    release_date = _release_date(parser.text, "Release Date")
    next_release = _release_date(parser.text, "Next Release Date")
    if next_release <= release_date:
        raise ValueError("eia_history_release_order_invalid")
    cells: list[EiaHistoryCell] = []
    seen: set[date] = set()
    previous_monday: date | None = None
    for row in parser.rows[1:]:
        if len(row) != 6:
            raise ValueError("eia_history_daily_cell_count_invalid")
        match = re.fullmatch(
            r"(\d{4}) ([A-Z][a-z]{2})-\s*(\d{1,2}) to ([A-Z][a-z]{2})-\s*(\d{1,2})", row[0]
        )
        if match is None:
            raise ValueError("eia_history_week_label_invalid")
        year, month, day, end_month, end_day = match.groups()
        if month not in _MONTHS or end_month not in _MONTHS:
            raise ValueError("eia_history_week_month_invalid")
        monday = date(int(year), _MONTHS[month], int(day))
        friday = date(
            int(year) + (_MONTHS[end_month] < _MONTHS[month]), _MONTHS[end_month], int(end_day)
        )
        if monday.weekday() != 0 or friday != monday + timedelta(days=4):
            raise ValueError("eia_history_week_coordinates_invalid")
        if previous_monday is not None and monday != previous_monday + timedelta(days=7):
            raise ValueError("eia_history_week_continuity_invalid")
        previous_monday = monday
        for offset, raw in enumerate(row[1:]):
            observed = monday + timedelta(days=offset)
            if observed in seen:
                raise ValueError("eia_history_duplicate_date")
            seen.add(observed)
            value = None
            if raw in _MISSING:
                state = _MISSING[raw]
            else:
                if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw) is None:
                    raise ValueError("eia_history_value_invalid")
                value = float(raw)
                if not isfinite(value):
                    raise ValueError("eia_history_value_invalid")
                state = "reported_value"
            if start_date <= observed <= end_date:
                cells.append(EiaHistoryCell(observed, value, state, raw))
    if not seen:
        raise ValueError("eia_history_observations_missing")
    return EiaHistoryBatch(
        series_id,
        endpoint,
        description,
        "usd_per_barrel",
        release_date,
        next_release,
        "America/New_York",
        "date",
        "Refinitiv, an LSEG business",
        tuple(sorted(cells, key=lambda c: c.business_date)),
        len(seen),
    )


def _fetch_history(url: str) -> FetchedEiaHistory:
    from urllib.request import Request

    request = Request(url, headers={"Accept": "text/html", "User-Agent": "pring-cycle/1.0"})
    try:
        with open_no_redirects(request, timeout=15) as response:
            return FetchedEiaHistory(
                bytes(response.read(_MAX_BYTES + 1)),
                response.geturl(),
                int(response.status),
                str(response.headers.get("Content-Type", "")),
            )
    except HTTPError as error:
        with error:
            return FetchedEiaHistory(
                error.read(_MAX_BYTES + 1),
                error.geturl(),
                error.code,
                str(error.headers.get("Content-Type", "")) if error.headers else "",
            )


def refresh_eia_history(
    paths: RuntimePaths,
    *,
    series_id: str,
    start_date: date,
    end_date: date,
    definition_version: str = METRIC_CATALOG_VERSION,
    fetcher: Callable[[str], FetchedEiaHistory] | None = None,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> EiaHistoryIngestionResult:
    if series_id not in _SOURCES or end_date < start_date:
        raise ValueError("eia_history_request_invalid")
    metric_id, _, endpoint = _SOURCES[series_id]
    definition = metric_definition(metric_id, definition_version=definition_version)
    repository = EvidenceRepository(paths.database)
    ids: list[str] = []
    responses: list[FetchedEiaHistory] = []

    def response_metadata() -> dict[str, str]:
        if not responses:
            return {}
        response = responses[0]
        return {
            "response_final_url": response.final_url,
            "response_http_status": str(response.http_status),
            "response_media_type": response.media_type,
        }

    def started(acquisition_id: str) -> None:
        ids.append(acquisition_id)
        if on_acquisition_started is not None:
            on_acquisition_started(acquisition_id)

    def fetch() -> bytes:
        response = (fetcher or _fetch_history)(endpoint)
        responses.append(response)
        return response.content

    def parse(raw: bytes) -> EiaHistoryBatch:
        response = responses[0]
        if response.final_url != endpoint:
            raise ValueError("eia_history_response_source_identity_invalid")
        if response.http_status != 200:
            raise OSError("eia_history_response_http_status_invalid")
        if response.media_type.split(";", maxsplit=1)[0].strip().lower() != "text/html":
            raise ValueError("eia_history_response_media_type_invalid")
        return parse_eia_history_document(
            raw,
            series_id=series_id,
            start_date=start_date,
            end_date=end_date,
            http_charset=_http_charset(response.media_type),
        )

    metadata = {
        "endpoint": endpoint,
        "series_id": series_id,
        "start_date": str(start_date),
        "period": str(end_date),
        "definition_version": definition_version,
    }
    try:
        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=_PROVIDER,
            api_name="eia_history_html",
            parameters=metadata,
            fields="Mon,Tue,Wed,Thu,Fri",
            parser_version="eia-history-html-parser-v0001",
            fetch=fetch,
            parse=parse,
            normalize=lambda batch: {**asdict(batch), "http_response": response_metadata()},
            on_started=started,
        )
        receipt, batch = acquired.receipt, acquired.value
        if receipt.received_at is None or receipt.validated_at is None:
            raise ValueError("eia_history_acquisition_incomplete")
        claims = tuple(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version=definition_version,
                period_kind="business_day",
                period_start=str(cell.business_date),
                period_end=str(cell.business_date),
                dimensions={},
                value=cell.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=batch.unit,
                provider=_PROVIDER,
                source_reference=f"{endpoint}#date={cell.business_date}",
                release_event_id=f"unresolved-publication:eia-html:{receipt.acquisition_id}",
                release_at=None,
                public_available_at=None,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="awaiting_source_certification",
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
            for cell in batch.cells
            if cell.value is not None
        )
        if definition.unit != batch.unit:
            raise ValueError("eia_history_definition_unit_mismatch")
        stored = (
            repository.append_source_claims(claims, availability_clock=utc_now) if claims else ()
        )
        missing = sum(cell.value is None for cell in batch.cells)
        condition = (
            None
            if stored
            else (
                "no_reported_values_in_source_cells"
                if batch.cells
                else "no_source_calendar_cells_in_requested_window"
            )
        )
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="eia_html_candidate",
            outcome="verified_candidate" if stored else "missing_values",
            fetched_at=utc_now(),
            acquisition_ids=tuple(ids),
            safe_metadata={
                **metadata,
                **response_metadata(),
                **({"condition": condition} if condition is not None else {}),
                "observations": str(len(stored)),
                "missing_cells": str(missing),
                "release_date": str(batch.release_date),
                "next_release_date": str(batch.next_release_date),
                "release_timezone": batch.release_timezone,
            },
        )
        return EiaHistoryIngestionResult(
            "stored_candidate" if stored else "missing_values",
            receipt.acquisition_id,
            metric_id,
            len(stored),
            missing,
            tuple(s.observation_id for s in stored),
            tuple(s.claim_id for s in stored),
            condition,
        )
    except (OSError, TypeError, ValueError) as error:
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="eia_html_candidate",
            fetched_at=utc_now(),
            outcome="source_failed" if isinstance(error, OSError) else "validation_failed",
            acquisition_ids=tuple(ids),
            safe_metadata={**metadata, **response_metadata(), "error_type": type(error).__name__},
        )
        raise
