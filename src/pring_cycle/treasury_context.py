from __future__ import annotations

import codecs
import csv
import io
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from email.message import Message
from math import isfinite
from urllib.error import HTTPError
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
)
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.runtime import RuntimePaths

_FIELDS = {"2 Yr": "UST2Y_NOMINAL_YIELD", "10 Yr": "UST10Y_NOMINAL_YIELD"}
TREASURY_SOURCE_CODES = {
    metric: (f"treasury_nominal_yields_csv.{field}",) for field, metric in _FIELDS.items()
}
TREASURY_METRICS = frozenset(TREASURY_SOURCE_CODES)
_PROVIDER = "U.S. Department of the Treasury"
_MAX_BYTES = 4_000_000


@dataclass(frozen=True)
class FetchedTreasuryYieldCsv:
    content: bytes
    final_url: str
    http_status: int
    media_type: str


@dataclass(frozen=True)
class TreasuryYieldCell:
    metric_id: str
    business_date: date
    value: float | None
    state: str
    source_text: str


@dataclass(frozen=True)
class TreasuryYieldBatch:
    source_year: int
    endpoint: str
    source_timezone: str
    unit: str
    cells: tuple[TreasuryYieldCell, ...]
    total_source_rows: int
    latest_reported_periods: dict[str, date]


@dataclass(frozen=True)
class TreasuryIngestionResult:
    status: str
    acquisition_id: str
    observation_count: int
    missing_cell_count: int
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    condition: str | None


def treasury_yield_endpoint(year: int) -> str:
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
        f"&field_tdr_date_value={year}&page&_format=csv"
    )


def _decode_csv(content: bytes, media_type: str) -> str:
    header = Message()
    header["Content-Type"] = media_type
    declarations = [value for key, value in (header.get_params() or []) if key.lower() == "charset"]
    if len(declarations) > 1:
        raise ValueError("treasury_csv_charset_conflict")
    try:
        encoding = codecs.lookup(str(declarations[0]) if declarations else "utf-8").name
    except LookupError as error:
        raise ValueError("treasury_csv_charset_unsupported") from error
    if encoding not in {"utf-8", "ascii"}:
        raise ValueError("treasury_csv_charset_unsupported")
    return content.decode("utf-8-sig" if encoding == "utf-8" else encoding)


def parse_treasury_yield_csv(
    content: bytes, *, start_date: date, end_date: date, media_type: str = "text/csv"
) -> TreasuryYieldBatch:
    if end_date < start_date or start_date.year != end_date.year:
        raise ValueError("treasury_csv_request_must_cover_one_source_year")
    if not content or len(content) > _MAX_BYTES:
        raise ValueError("treasury_csv_size_invalid")
    reader = csv.reader(io.StringIO(_decode_csv(content, media_type)), strict=True)
    try:
        columns = next(reader)
        if (
            len(set(columns)) != len(columns)
            or not {"Date", *_FIELDS}.issubset(columns)
            or any(not name for name in columns)
        ):
            raise ValueError("treasury_csv_columns_invalid")
        points: list[TreasuryYieldCell] = []
        seen: set[date] = set()
        latest: dict[str, date] = {}
        for row in reader:
            if len(row) != len(columns):
                raise ValueError("treasury_csv_row_width_invalid")
            values = dict(zip(columns, row, strict=True))
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", values["Date"]) is None:
                raise ValueError("treasury_csv_date_invalid")
            period = datetime.strptime(values["Date"], "%m/%d/%Y").date()
            if period.year != start_date.year or period in seen:
                raise ValueError("treasury_csv_date_identity_invalid")
            seen.add(period)
            for field, metric in _FIELDS.items():
                source_text = values[field]
                text = source_text.strip()
                value: float | None = None
                if text in {"", "N/A"}:
                    state = "blank" if not text else "not_available"
                else:
                    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text) is None:
                        raise ValueError("treasury_csv_value_invalid")
                    value = float(text)
                    if not isfinite(value) or value < 0:
                        raise ValueError("treasury_csv_nominal_value_invalid")
                    state = "reported_value"
                    latest[metric] = max(period, latest.get(metric, period))
                if start_date <= period <= end_date:
                    points.append(TreasuryYieldCell(metric, period, value, state, source_text))
    except (csv.Error, StopIteration) as error:
        raise ValueError("treasury_csv_structure_invalid") from error
    if not seen:
        raise ValueError("treasury_csv_empty_document")
    return TreasuryYieldBatch(
        start_date.year,
        treasury_yield_endpoint(start_date.year),
        "America/New_York",
        "percent",
        tuple(sorted(points, key=lambda item: (item.business_date, item.metric_id))),
        len(seen),
        latest,
    )


def _parse_treasury_acquisition(
    receipt: AcquisitionReceipt, raw: bytes, normalized: bytes
) -> TreasuryYieldBatch:
    parameters = receipt.parameters
    if (
        receipt.provider != _PROVIDER
        or receipt.api_name != "treasury_nominal_yields_csv"
        or receipt.fields != "Date,2 Yr,10 Yr"
        or receipt.parser_version != "treasury-nominal-csv-parser-v0001"
        or set(parameters)
        != {"endpoint", "source_year", "start_date", "period", "definition_version"}
    ):
        raise ValueError("treasury_acquisition_identity_mismatch")
    start = date.fromisoformat(parameters["start_date"])
    end = date.fromisoformat(parameters["period"])
    endpoint = treasury_yield_endpoint(start.year)
    if (
        parameters["source_year"] != str(start.year)
        or parameters["endpoint"] != endpoint
        or parameters["start_date"] != start.isoformat()
        or parameters["period"] != end.isoformat()
    ):
        raise ValueError("treasury_acquisition_period_mismatch")
    document = json.loads(normalized)
    response = document.get("http_response") if isinstance(document, dict) else None
    if not isinstance(response, dict) or set(response) != {
        "response_final_url",
        "response_http_status",
        "response_media_type",
    }:
        raise ValueError("treasury_acquisition_response_mismatch")
    media_type = response["response_media_type"]
    if (
        response["response_final_url"] != endpoint
        or response["response_http_status"] != "200"
        or not isinstance(media_type, str)
        or media_type.split(";", maxsplit=1)[0].strip().lower() != "text/csv"
    ):
        raise ValueError("treasury_acquisition_response_mismatch")
    batch = parse_treasury_yield_csv(raw, start_date=start, end_date=end, media_type=media_type)
    expected = {**asdict(batch), "http_response": response}
    if json.dumps(document, sort_keys=True, allow_nan=False) != json.dumps(
        expected, default=str, sort_keys=True, allow_nan=False
    ):
        raise ValueError("treasury_acquisition_normalized_mismatch")
    return batch


def treasury_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]],
    *,
    definition_version: str,
) -> set[str]:
    """Match selected Treasury values to complete CSV receipts, without inventing PUBLIC time.

    A catalog registering ``us_tycr`` delivers the same yields through TuShare; those
    claims are matched to their TuShare deliveries instead.
    """
    from pring_cycle.tushare_context import (
        parse_treasury_acquisition,
        tushare_claims_matching_acquisitions,
    )

    selected = {
        point.selected_claim_id: (metric, point)
        for metric, points in points_by_metric.items()
        for point in points
        if metric in TREASURY_METRICS and point.selected_claim_id is not None
    }
    valid_ids: set[str] = tushare_claims_matching_acquisitions(
        repository,
        tuple(
            point
            for _metric, point in selected.values()
            if any(
                c.claim_id == point.selected_claim_id and c.provider == "tushare"
                for c in point.claims
            )
        ),
        definition_version=definition_version,
        parse=parse_treasury_acquisition,
    )
    checked: dict[str, TreasuryYieldBatch | None] = {}
    for claim_id, acquisitions in repository.source_claim_acquisitions_many(
        tuple(selected)
    ).items():
        metric, point = selected[claim_id]
        claim = next((item for item in point.claims if item.claim_id == claim_id), None)
        if (
            not acquisitions
            or claim is None
            or claim.provider != _PROVIDER
            or claim.unit != "percent"
            or point.dimensions != {}
            or point.period_start != point.period_end
            # This CSV contains no proof of per-row first publication or revisions.
            or claim.release_at is not None
            or claim.parsed_public_available_at is not None
        ):
            continue
        valid = True
        for acquisition in acquisitions:
            receipt = acquisition.receipt
            identity = receipt.acquisition_id
            if identity not in checked:
                try:
                    checked[identity] = _parse_treasury_acquisition(
                        receipt, acquisition.raw, acquisition.normalized
                    )
                except (ValueError, TypeError, KeyError, OverflowError):
                    checked[identity] = None
            batch = checked[identity]
            if (
                batch is None
                or receipt.parameters.get("definition_version") != definition_version
                or claim.source_reference != f"{batch.endpoint}#date={point.period_end}"
                or not any(
                    cell.metric_id == metric
                    and cell.business_date.isoformat() == point.period_end
                    and cell.state == "reported_value"
                    and cell.value == point.selected_value == claim.value
                    for cell in batch.cells
                )
            ):
                valid = False
                break
        if valid:
            valid_ids.add(claim_id)
    return valid_ids


def _fetch_csv(url: str) -> FetchedTreasuryYieldCsv:
    request = Request(url, headers={"Accept": "text/csv", "User-Agent": "pring-cycle/1.0"})
    try:
        with open_no_redirects(request, timeout=15) as response:
            return FetchedTreasuryYieldCsv(
                bytes(response.read(_MAX_BYTES + 1)),
                response.geturl(),
                int(response.status),
                str(response.headers.get("Content-Type", "")),
            )
    except HTTPError as error:
        with error:
            return FetchedTreasuryYieldCsv(
                error.read(_MAX_BYTES + 1),
                error.geturl(),
                error.code,
                str(error.headers.get("Content-Type", "")) if error.headers else "",
            )


def refresh_treasury_yields(
    paths: RuntimePaths,
    *,
    start_date: date,
    end_date: date,
    definition_version: str = METRIC_CATALOG_VERSION,
    fetcher: Callable[[str], FetchedTreasuryYieldCsv] | None = None,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> TreasuryIngestionResult:
    if end_date < start_date or start_date.year != end_date.year:
        raise ValueError("treasury_csv_request_must_cover_one_source_year")
    definitions = [
        metric_definition(
            metric, definition_version=definition_version, database_path=paths.database
        )
        for metric in _FIELDS.values()
    ]
    if any(item.unit != "percent" for item in definitions):
        raise ValueError("treasury_csv_definition_unit_mismatch")
    endpoint = treasury_yield_endpoint(start_date.year)
    repository = EvidenceRepository(paths.database)
    ids: list[str] = []
    responses: list[FetchedTreasuryYieldCsv] = []
    metadata = {
        "endpoint": endpoint,
        "source_year": str(start_date.year),
        "start_date": str(start_date),
        "period": str(end_date),
        "definition_version": definition_version,
    }

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
        response = (fetcher or _fetch_csv)(endpoint)
        responses.append(response)
        return response.content

    def parse(raw: bytes) -> TreasuryYieldBatch:
        response = responses[0]
        if response.final_url != endpoint:
            raise ValueError("treasury_csv_response_identity_invalid")
        if response.http_status != 200:
            raise OSError("treasury_csv_response_http_status_invalid")
        if response.media_type.split(";", maxsplit=1)[0].strip().lower() != "text/csv":
            raise ValueError("treasury_csv_response_media_type_invalid")
        return parse_treasury_yield_csv(
            raw, start_date=start_date, end_date=end_date, media_type=response.media_type
        )

    try:
        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=_PROVIDER,
            api_name="treasury_nominal_yields_csv",
            parameters=metadata,
            fields="Date,2 Yr,10 Yr",
            parser_version="treasury-nominal-csv-parser-v0001",
            fetch=fetch,
            parse=parse,
            normalize=lambda batch: {**asdict(batch), "http_response": response_metadata()},
            on_started=started,
        )
        receipt, batch = acquired.receipt, acquired.value
        if receipt.received_at is None or receipt.validated_at is None:
            raise ValueError("treasury_csv_acquisition_incomplete")
        claims = tuple(
            SourceClaimInput(
                metric_id=cell.metric_id,
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
                release_event_id=f"unresolved-publication:treasury-csv:{receipt.acquisition_id}",
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
                else "no_source_dates_in_requested_window"
            )
        )
        for metric in _FIELDS.values():
            cells = [cell for cell in batch.cells if cell.metric_id == metric]
            count = sum(cell.value is not None for cell in cells)
            repository.record_retrieval_attempt(
                metric_id=metric,
                channel="treasury_csv_candidate",
                outcome="verified_candidate" if count else "missing_values",
                fetched_at=utc_now(),
                acquisition_ids=tuple(ids),
                safe_metadata={
                    **metadata,
                    **response_metadata(),
                    "observations": str(count),
                    "missing_cells": str(sum(cell.value is None for cell in cells)),
                    "source_timezone": batch.source_timezone,
                    **(
                        {"latest_source_period": str(batch.latest_reported_periods[metric])}
                        if metric in batch.latest_reported_periods
                        else {}
                    ),
                    **(
                        {
                            "condition": "no_reported_values_in_source_cells"
                            if cells
                            else "no_source_dates_in_requested_window"
                        }
                        if not count
                        else {}
                    ),
                },
            )
        return TreasuryIngestionResult(
            "stored_candidate" if stored else "missing_values",
            receipt.acquisition_id,
            len(stored),
            missing,
            tuple(item.observation_id for item in stored),
            tuple(item.claim_id for item in stored),
            condition,
        )
    except (OSError, TypeError, ValueError) as error:
        for metric in _FIELDS.values():
            repository.record_retrieval_attempt(
                metric_id=metric,
                channel="treasury_csv_candidate",
                fetched_at=utc_now(),
                outcome="source_failed" if isinstance(error, OSError) else "validation_failed",
                acquisition_ids=tuple(ids),
                safe_metadata={
                    **metadata,
                    **response_metadata(),
                    "error_type": type(error).__name__,
                },
            )
        raise
