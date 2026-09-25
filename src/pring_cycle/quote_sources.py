"""P2 daily quotes read straight from their publishers (ADR-0029, gap sources #06/#07).

Cboe's VIX history and the CFETS 16:30 USD/CNY close each have one official file. They are
registered sources: fetched once a run, never searched. A file whose shape has changed is a
source failure, not a value, so nothing is taken from a document that no longer reads as
expected.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionRepository, utc_now
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


CBOE_VIX = QuoteSource(
    metric_id="CBOE_VIX_INDEX",
    provider="Cboe Global Markets",
    url="https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
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
QUOTE_SOURCES = (CBOE_VIX, CHINAMONEY_USDCNY_1630)


def _fetch(source: QuoteSource) -> bytes:
    request = Request(
        source.url,
        headers={"Accept": source.accept, "User-Agent": "Mozilla/5.0 (pring-cycle/1.0)"},
    )
    try:
        with open_no_redirects(request, timeout=20) as response:
            if int(response.status) != 200 or response.geturl() != source.url:
                raise OSError("quote_source_response_invalid")
            content = bytes(response.read(_MAX_BYTES + 1))
    except HTTPError as error:
        raise OSError(f"quote_source_http_{error.code}") from error
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
            api_name="official_http_get",
            parameters=metadata,
            fields=source.fields,
            parser_version=source.parser_version,
            fetch=lambda: _fetch(source),
            parse=lambda raw: source.parse(raw, start_date, end_date),
            normalize=lambda rows: [asdict(row) for row in rows],
            on_started=identities.append,
        )
    except (OSError, ValueError) as error:
        repository.record_retrieval_attempt(
            metric_id=source.metric_id,
            channel=source.channel,
            outcome="source_failed",
            fetched_at=utc_now(),
            acquisition_ids=tuple(identities),
            safe_metadata={**metadata, "error_type": type(error).__name__, "reason": str(error)},
        )
        raise
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
    except ValueError as error:
        # The file read well; the registered contract refused its values.
        acquisitions.record_ingest_result(receipt.acquisition_id, error)
        repository.record_retrieval_attempt(
            metric_id=source.metric_id,
            channel=source.channel,
            outcome="validation_failed",
            fetched_at=utc_now(),
            acquisition_ids=(receipt.acquisition_id,),
            safe_metadata={**metadata, "stage": "ingest", "reason": str(error)[:300]},
        )
        raise
    acquisitions.record_ingest_result(receipt.acquisition_id, None)
    repository.record_retrieval_attempt(
        metric_id=source.metric_id,
        channel=source.channel,
        outcome="verified_candidate" if acquired.value else "missing_values",
        fetched_at=utc_now(),
        acquisition_ids=(receipt.acquisition_id,),
        safe_metadata={**metadata, "observations": str(len(acquired.value))},
    )
    return len(claims)
