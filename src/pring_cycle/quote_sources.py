"""P2 daily quotes read straight from their publishers (ADR-0029, gap sources #06/#07).

Cboe's VIX history and the CFETS 16:30 USD/CNY close each have one official file, and
Nasdaq's index site gives SOX's history for a window (ADR-0042). They are registered
sources: fetched once a run, never searched. A file whose shape has changed is a source
failure, not a value, so nothing is taken from a document that no longer reads as expected.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository, SourceFailed, utc_now
from pring_cycle.acquisition_outcome import (
    SOURCE_FAILED,
    STRUCTURE_REJECTED,
    SUCCEEDED,
    attempt_details,
    capture_failure,
    ingest_failure,
)
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.runtime import RuntimePaths

_MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class QuoteRow:
    business_date: str
    value: float
    source_text: str


def _price(text: str, reason: str) -> float:
    if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,10})?", text) is None or float(text) <= 0:
        raise ValueError(reason)
    return float(text)


def parse_cboe_vix_history(
    content: bytes, *, start_date: date, end_date: date
) -> tuple[QuoteRow, ...]:
    """Each session's close from Cboe's daily VIX history (``DATE,OPEN,HIGH,LOW,CLOSE``)."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("cboe_vix_columns_invalid") from error
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        if next(reader, None) != ["DATE", "OPEN", "HIGH", "LOW", "CLOSE"]:
            raise ValueError("cboe_vix_columns_invalid")
        rows: list[QuoteRow] = []
        seen: set[date] = set()
        for fields in reader:
            if not fields:
                continue
            if len(fields) != 5 or re.fullmatch(r"\d{2}/\d{2}/\d{4}", fields[0]) is None:
                raise ValueError("cboe_vix_row_invalid")
            day = datetime.strptime(fields[0], "%m/%d/%Y").date()
            if day in seen:
                raise ValueError("cboe_vix_duplicate_date")
            seen.add(day)
            close = _price(fields[4], "cboe_vix_row_invalid")
            if start_date <= day <= end_date:
                rows.append(QuoteRow(day.isoformat(), close, fields[4]))
    except csv.Error as error:
        raise ValueError("cboe_vix_row_invalid") from error
    if not seen:
        raise ValueError("cboe_vix_columns_invalid")
    return tuple(rows)


_NEW_YORK = ZoneInfo("America/New_York")
_JSON_DATE = re.compile(r"/Date\((\d{1,15})\)/")


def parse_nasdaq_index_history(
    content: bytes, *, start_date: date, end_date: date
) -> tuple[QuoteRow, ...]:
    """Each U.S. session's end-of-day index value from Nasdaq Global Indexes' history.

    The history page's table reads ``aaData``: a session's row is stamped at New York's
    midnight of its trade date, and its ``Value`` is the index value the page shows (the
    ``Close`` field stays empty). A row of another shape refuses the whole document.
    """
    try:
        rows_in = json.loads(content, parse_float=Decimal)["aaData"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("nasdaq_index_document_invalid") from error
    if not isinstance(rows_in, list):
        raise ValueError("nasdaq_index_document_invalid")
    rows: list[QuoteRow] = []
    seen: set[date] = set()
    for item in rows_in:
        if not isinstance(item, dict):
            raise ValueError("nasdaq_index_document_invalid")
        stamp = _JSON_DATE.fullmatch(str(item.get("TimeStamp")))
        if stamp is None:
            raise ValueError("nasdaq_index_date_invalid")
        try:
            moment = datetime.fromtimestamp(int(stamp.group(1)) / 1000, _NEW_YORK)
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError("nasdaq_index_date_invalid") from error
        if (moment.hour, moment.minute, moment.second, moment.microsecond) != (0, 0, 0, 0):
            raise ValueError("nasdaq_index_date_invalid")
        day = moment.date()
        if day in seen:
            raise ValueError("nasdaq_index_duplicate_date")
        seen.add(day)
        value = item.get("Value")
        if (
            not isinstance(value, Decimal | int)
            or isinstance(value, bool)
            or not Decimal(value).is_finite()
            or value <= 0
        ):
            raise ValueError("nasdaq_index_value_invalid")
        if start_date <= day <= end_date:
            rows.append(QuoteRow(day.isoformat(), float(value), str(value)))
    return tuple(sorted(rows, key=lambda row: row.business_date))


# The intraday snapshot marks its 16:30 point with a blank time; the page labels it 16:30.
_CLOSE_POINT = re.compile(r'\{\s*"time"\s*:\s*" "\s*,\s*spotPrice\s*:\s*([0-9.]+)')


def parse_chinamoney_close(content: bytes) -> tuple[QuoteRow, ...]:
    """The 16:30 USD/CNY close of the session the CFETS intraday file last covered.

    A session runs from 09:30 to 03:00 the next morning, so a file stamped before 09:30
    belongs to the previous day's session. Its ``spotPriceStr`` is the latest price (the
    03:00 night close once the session ends) and is never taken; ``closeSpotPrice`` is taken
    only when the snapshot's own 16:30 point shows the same price.
    """
    try:
        data = json.loads(content)["data"]
        stamp = datetime.strptime(str(data["lastDate"]), "%Y-%m-%d %H:%M")
        close_text = str(data["closeSpotPrice"]).strip()
        snapshot = str(data["chartsDataStr"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("chinamoney_close_document_invalid") from error
    session = stamp.date() - timedelta(days=1) if stamp.hour * 60 + stamp.minute < 570 else None
    if session is None:
        if stamp.hour * 60 + stamp.minute < 990 or close_text in {"", "---"}:
            return ()  # The session has not reached 16:30 yet.
        session = stamp.date()
    close = _price(close_text, "chinamoney_close_value_invalid")
    marked = _CLOSE_POINT.findall(snapshot)
    if len(marked) != 1 or abs(float(marked[0]) - close) > 5e-5:
        raise ValueError("chinamoney_close_snapshot_mismatch")
    return (QuoteRow(session.isoformat(), close, close_text),)


@dataclass(frozen=True)
class QuoteSource:
    metric_id: str
    provider: str
    url: str
    channel: str
    fields: str
    parser_version: str
    accept: str
    unit: str
    parse: Callable[[bytes, date, date], tuple[QuoteRow, ...]]
    # A source asked for a window posts this form; any other is one file, fetched whole.
    form: Callable[[date, date], dict[str, str]] | None = None


CBOE_VIX = QuoteSource(
    metric_id="CBOE_VIX_INDEX",
    provider="Cboe Global Markets",
    # cdn.cboe.com answers 307 to this host since 2026-09-26; redirects are not followed.
    url="https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    channel="cboe_official",
    fields="DATE,CLOSE",
    parser_version="cboe-vix-history-parser-v0001",
    accept="text/csv",
    unit="index_points",
    parse=lambda raw, start, end: parse_cboe_vix_history(raw, start_date=start, end_date=end),
)
CHINAMONEY_USDCNY_1630 = QuoteSource(
    metric_id="CN_USDCNY_CLOSE_1630",
    provider="中国外汇交易中心",
    url="https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/rfx-sp-iday-chrt.json",
    channel="chinamoney_official",
    fields="lastDate,closeSpotPrice,chartsDataStr",
    parser_version="chinamoney-usdcny-1630-parser-v0001",
    accept="application/json",
    unit="scalar",
    parse=lambda raw, start, end: tuple(
        row
        for row in parse_chinamoney_close(raw)
        if start.isoformat() <= row.business_date <= end.isoformat()
    ),
)
# Nasdaq administers SOX; its index site's history table, the one the page's own script
# posts, has no published interface (ADR-0042). Each day is stamped at its midnight.
NASDAQ_SOX = QuoteSource(
    metric_id="NASDAQ_SOX_INDEX",
    provider="Nasdaq Global Indexes",
    url="https://indexes.nasdaqomx.com/Index/HistoryData",
    channel="nasdaq_index_official",
    fields="TimeStamp,Value",
    parser_version="nasdaq-index-history-parser-v0001",
    accept="application/json",
    unit="index_points",
    parse=lambda raw, start, end: parse_nasdaq_index_history(raw, start_date=start, end_date=end),
    form=lambda start, end: {
        "id": "SOX",
        "startDate": f"{start.isoformat()}T00:00:00.000",
        "endDate": f"{end.isoformat()}T00:00:00.000",
        "timeOfDay": "EOD",
    },
)
QUOTE_SOURCES = (CBOE_VIX, CHINAMONEY_USDCNY_1630, NASDAQ_SOX)


def _fetch(source: QuoteSource, start_date: date, end_date: date) -> bytes:
    headers = {"Accept": source.accept, "User-Agent": "Mozilla/5.0 (pring-cycle/1.0)"}
    body = None
    if source.form is not None:
        body = urlencode(source.form(start_date, end_date)).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(source.url, data=body, headers=headers)
    try:
        with open_no_redirects(request, timeout=20) as response:
            if int(response.status) != 200 or response.geturl() != source.url:
                raise SourceFailed(
                    "quote_source_response_invalid", external_code=int(response.status)
                )
            content = bytes(response.read(_MAX_BYTES + 1))
    except HTTPException as error:
        raise OSError("quote_source_http_protocol_failed") from error
    if len(content) > _MAX_BYTES:
        raise OSError("quote_source_response_oversize")
    return content


def refresh_quote_source(
    paths: RuntimePaths,
    source: QuoteSource,
    *,
    start_date: date,
    end_date: date,
    definition_version: str,
) -> int:
    """Fetch the file once, hold each new or changed value; the attempt records the outcome.

    A document that fails to parse is recorded as a source failure with its reason code.
    """
    definition = metric_definition(
        source.metric_id, definition_version=definition_version, database_path=paths.database
    )
    repository = EvidenceRepository(paths.database)
    metadata = {
        "source_url": source.url,
        "start_date": start_date.isoformat(),
        "period": end_date.isoformat(),
        "definition_version": definition_version,
    }
    identities: list[str] = []
    try:
        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=source.provider,
            api_name="official_http_get" if source.form is None else "official_http_post",
            parameters=metadata,
            fields=source.fields,
            parser_version=source.parser_version,
            # An HTTP failure reaches the receipt store as such, which keeps the page it
            # answered with (an anti-bot page, say) as the receipt's original.
            fetch=lambda: _fetch(source, start_date, end_date),
            parse=lambda raw: source.parse(raw, start_date, end_date),
            normalize=lambda rows: [asdict(row) for row in rows],
            on_started=identities.append,
            count_scalars=len,
            max_error_body_bytes=_MAX_BYTES,
        )
    except (LookupError, OSError, TypeError, ValueError) as caught:
        error: Exception = caught
        if isinstance(caught, HTTPError):
            # The source's answer was a failure: its code is kept (ticket 18).
            error = SourceFailed(f"quote_source_http_{caught.code}", external_code=caught.code)
        outcome, recorded = capture_failure(error)
        if outcome == STRUCTURE_REJECTED:
            # By the source's specification a file that does not parse is the source failing
            # (ticket 18 keeps it so); the rule that refused it stays its reason.
            outcome = SOURCE_FAILED
        repository.record_retrieval_attempt(
            metric_id=source.metric_id,
            channel=source.channel,
            outcome=outcome,
            fetched_at=utc_now(),
            acquisition_ids=tuple(identities),
            safe_metadata={**metadata, **recorded, "reason": str(error)},
        )
        if error is caught:
            raise
        raise error from caught
    receipt = acquired.receipt
    held = {
        point.period_end: point.selected_value
        for point in repository.metric_series(
            source.metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=utc_now(),
            definition_version=definition_version,
        )
    }
    claims = tuple(
        SourceClaimInput(
            metric_id=source.metric_id,
            definition_version=definition_version,
            period_kind="business_day",
            period_start=row.business_date,
            period_end=row.business_date,
            dimensions={},
            value=row.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=source.unit,
            provider=source.provider,
            source_reference=f"{source.url}#date={row.business_date}",
            release_event_id=f"unresolved-publication:{source.channel}:{receipt.acquisition_id}",
            release_at=None,
            public_available_at=None,
            fetched_at=receipt.received_at or utc_now(),
            available_at=receipt.validated_at or utc_now(),
            certification_status=definition.certification_status,
            quality_status="validated",
            acquisition_id=receipt.acquisition_id,
        )
        for row in acquired.value
        if held.get(row.business_date) != row.value
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    try:
        if claims:
            repository.append_source_claims(claims, availability_clock=utc_now)
    except (OSError, TypeError, ValueError) as error:
        # The file read well; the registered contract refused its values, or this system
        # failed storing them, which is no refusal.
        if isinstance(error, ValueError):
            acquisitions.record_ingest_result(receipt.acquisition_id, error)
        outcome, recorded = ingest_failure(error)
        repository.record_retrieval_attempt(
            metric_id=source.metric_id,
            channel=source.channel,
            outcome=outcome,
            fetched_at=utc_now(),
            acquisition_ids=(receipt.acquisition_id,),
            safe_metadata={**metadata, **recorded},
        )
        raise
    acquisitions.record_ingest_result(receipt.acquisition_id, None)
    repository.record_retrieval_attempt(
        metric_id=source.metric_id,
        channel=source.channel,
        outcome=SUCCEEDED,
        fetched_at=utc_now(),
        acquisition_ids=(receipt.acquisition_id,),
        safe_metadata={
            **metadata,
            # Every day the file gave already held at that value: nothing new to add.
            **attempt_details(
                step="ingest" if claims else "structure",
                completeness=(
                    "source_empty"
                    if not acquired.value
                    else "nothing_new"
                    if not claims
                    else "complete"
                ),
            ),
            "observations": str(len(acquired.value)),
        },
    )
    return len(claims)
