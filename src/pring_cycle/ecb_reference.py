from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from functools import lru_cache
from http.client import HTTPException, IncompleteRead
from math import isfinite
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile
from zlib import error as ZlibError

from pring_cycle.acquisition import (
    AcquisitionReceipt,
    AcquisitionRepository,
    SourceFailed,
    utc_now,
)
from pring_cycle.acquisition_outcome import (
    SUCCEEDED,
    attempt_details,
    capture_failure,
    ingest_failure,
)
from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.http_transport import open_no_redirects
from pring_cycle.runtime import RuntimePaths

ECB_METRIC = "CN_USDCNY_ECB_REFERENCE_CROSS"
ECB_PROVIDER = "European Central Bank"
ECB_HISTORY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
ECB_PAGE = (
    "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
    "euro_reference_exchange_rates/html/index.en.html"
)
ECB_FORMULA = "ecb-eur-reference-cny-usd-cross-v0001"
ECB_SOURCE_CODE = "ECB_EUR_REFERENCE_CNY_USD_CROSS_V0001"
_PARSER = "ecb-reference-zip-parser-v0001"
_MEMBER = "eurofxref-hist.csv"
_MAX_ZIP_BYTES = 2_000_000
_MAX_CSV_BYTES = 8_000_000


@dataclass(frozen=True)
class FetchedEcbReferenceZip:
    content: bytes
    final_url: str
    http_status: int
    media_type: str
    complete: bool = True
    content_length: str = ""


@dataclass(frozen=True)
class EcbReferenceRow:
    date: str
    cny_per_eur: str
    usd_per_eur: str
    decimal_value: str
    value: float


@dataclass(frozen=True)
class EcbReferenceBatch:
    source_url: str
    start_date: str
    end_date: str
    csv_sha256: str
    csv_member: str
    base_currency: str
    unit: str
    formula_version: str
    expression: str
    decimal_precision: int
    rounding: str
    rows: tuple[EcbReferenceRow, ...]
    missing: tuple[dict[str, str], ...]
    total_source_rows: int


@dataclass(frozen=True)
class EcbReferenceImportResult:
    acquisition_id: str
    observation_count: int
    claim_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]


def _source_url(source_url: str) -> None:
    parts = urlsplit(source_url)
    if (
        parts.scheme != "https"
        or parts.netloc != "www.ecb.europa.eu"
        or parts.path != "/stats/eurofxref/eurofxref-hist.zip"
        or parts.fragment
        or parts.query
        and re.fullmatch(r"[a-f0-9]{32}", parts.query) is None
    ):
        raise ValueError("ecb_reference_source_url_invalid")


def _rate(text: str) -> Decimal | None:
    if text in {"", "N/A"}:
        return None
    if len(text) > 64 or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text) is None:
        raise ValueError("ecb_reference_rate_invalid")
    value = Decimal(text)
    if not value.is_finite() or value <= 0:
        raise ValueError("ecb_reference_rate_invalid")
    return value


def _parse(
    content: bytes, *, source_url: str, start_date: date, end_date: date
) -> EcbReferenceBatch:
    _source_url(source_url)
    if end_date < start_date:
        raise ValueError("ecb_reference_date_range_invalid")
    if not content or len(content) > _MAX_ZIP_BYTES:
        raise ValueError("ecb_reference_zip_size_invalid")
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if (
                len(members) != 1
                or members[0].filename != _MEMBER
                or members[0].flag_bits & 1
                or members[0].compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                or not 0 < members[0].file_size <= _MAX_CSV_BYTES
            ):
                raise ValueError("ecb_reference_zip_member_invalid")
            with archive.open(members[0]) as member:
                raw_csv = member.read(_MAX_CSV_BYTES + 1)
            if len(raw_csv) != members[0].file_size or len(raw_csv) > _MAX_CSV_BYTES:
                raise ValueError("ecb_reference_csv_size_invalid")
    except (BadZipFile, RuntimeError, EOFError, ZlibError) as error:
        raise ValueError("ecb_reference_zip_invalid") from error
    reader = csv.reader(io.StringIO(raw_csv.decode("utf-8-sig")), strict=True)
    try:
        columns = next(reader)
        trailing_empty = columns[-1:] == [""]
        if trailing_empty:
            columns = columns[:-1]
        if (
            not {"Date", "USD", "CNY"}.issubset(columns)
            or len(set(columns)) != len(columns)
            or any(c != "Date" and re.fullmatch(r"[A-Z]{3}", c) is None for c in columns)
        ):
            raise ValueError("ecb_reference_columns_invalid")
        rows: list[EcbReferenceRow] = []
        missing = []
        seen: set[date] = set()
        for fields in reader:
            if not fields:
                continue
            if trailing_empty:
                if fields[-1:] != [""]:
                    raise ValueError("ecb_reference_trailing_column_invalid")
                fields = fields[:-1]
            if len(fields) != len(columns):
                raise ValueError("ecb_reference_row_width_invalid")
            entry = dict(zip(columns, fields, strict=True))
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", entry["Date"]) is None:
                raise ValueError("ecb_reference_date_invalid")
            day = date.fromisoformat(entry["Date"])
            if day in seen:
                raise ValueError("ecb_reference_duplicate_date")
            seen.add(day)
            cny, usd = _rate(entry["CNY"]), _rate(entry["USD"])
            if not start_date <= day <= end_date:
                continue
            if cny is None or usd is None:
                missing.append(
                    {
                        "date": str(day),
                        "cny_per_eur": entry["CNY"],
                        "usd_per_eur": entry["USD"],
                        "reason": "reference_leg_missing",
                    }
                )
                continue
            with localcontext() as context:
                context.prec = 34
                context.rounding = ROUND_HALF_EVEN
                cross = cny / usd
            numeric = float(cross)
            if not isfinite(numeric) or numeric <= 0:
                raise ValueError("ecb_reference_cross_invalid")
            rows.append(EcbReferenceRow(str(day), entry["CNY"], entry["USD"], str(cross), numeric))
    except (csv.Error, StopIteration) as error:
        raise ValueError("ecb_reference_csv_invalid") from error
    if not seen:
        raise ValueError("ecb_reference_empty_document")
    return EcbReferenceBatch(
        source_url,
        str(start_date),
        str(end_date),
        hashlib.sha256(raw_csv).hexdigest(),
        _MEMBER,
        "EUR",
        "cny_per_usd",
        ECB_FORMULA,
        "CNY_per_EUR / USD_per_EUR",
        34,
        "ROUND_HALF_EVEN",
        tuple(sorted(rows, key=lambda row: row.date)),
        tuple(sorted(missing, key=lambda row: row["date"])),
        len(seen),
    )


def _definition(definition: MetricDefinition) -> None:
    expected = {
        "metric_id": ECB_METRIC,
        "name_cn": "ECB 美元兑人民币参考交叉汇率",
        "priority": "P2",
        "role": "macro_confirmation",
        "unit": "cny_per_usd",
        "allowed_units": ("cny_per_usd",),
        "dimensions": (),
        "frequency": "daily",
        "source_codes": (ECB_SOURCE_CODE,),
        "source_candidates": (ECB_PAGE,),
        "release_event_family": "ecb_eur_reference_cross",
        "release_rule": "source_schedule_required",
        "release_timezone": "Europe/Berlin",
    }
    if any(getattr(definition, key) != value for key, value in expected.items()):
        raise ValueError("registered_ecb_definition_mismatch")


def _reference(day: str) -> str:
    return f"{ECB_HISTORY_URL}#date={day}&formula={ECB_FORMULA}"


def require_ecb_reference_claim(
    definition: MetricDefinition,
    *,
    database_path: Path,
    provider: str,
    source_reference: str,
    period_kind: str,
    period_start: str,
    period_end: str,
    dimensions: object,
    unit: str,
    value: float | None,
    acquisition_ids: tuple[str, ...],
    release_at: datetime | None,
    public_available_at: datetime | None,
) -> None:
    _definition(definition)
    if (
        provider != ECB_PROVIDER
        or unit != "cny_per_usd"
        or dimensions != {}
        or period_kind != "business_day"
        or period_start != period_end
        or source_reference != _reference(period_end)
        or len(acquisition_ids) != 1
    ):
        raise ValueError("registered_ecb_source_identity_mismatch")
    if release_at is not None or public_available_at is not None:
        raise ValueError("registered_ecb_publication_evidence_required")
    acquisitions = AcquisitionRepository(database_path, database_path.parent / "artifacts/sha256")
    receipt = acquisitions.get(acquisition_ids[0])
    batch = _validated_batch(
        receipt,
        acquisitions.read_content(receipt.acquisition_id, "raw"),
        acquisitions.read_content(receipt.acquisition_id, "normalized"),
        # Fetched under any version defining the cross alike (ADR-0036).
        definition_versions=frozenset(
            EvidenceRepository(database_path).same_definition_versions(
                definition.metric_id, definition.definition_version
            )
        ),
    )
    if not any(row.date == period_end and row.value == value for row in batch.rows):
        raise ValueError("registered_ecb_cross_mismatch")


def _validated_batch(
    receipt: AcquisitionReceipt,
    raw: bytes,
    normalized: bytes,
    *,
    definition_versions: frozenset[str],
) -> EcbReferenceBatch:
    params = receipt.parameters
    if (
        receipt.state != "validated"
        or receipt.provider != ECB_PROVIDER
        or receipt.api_name not in {"document_import", "official_http_get"}
        or receipt.parser_version != _PARSER
        or receipt.fields != "Date,CNY,USD"
        or set(params) != {"source_url", "start_date", "period", "definition_version"}
        or params["definition_version"] not in definition_versions
    ):
        raise ValueError("registered_ecb_acquisition_identity_mismatch")
    return _verified_document(
        raw,
        normalized,
        source_url=params["source_url"],
        start_date=date.fromisoformat(params["start_date"]),
        end_date=date.fromisoformat(params["period"]),
        http=receipt.api_name == "official_http_get",
    )


@lru_cache(maxsize=4)
def _verified_document(
    raw: bytes,
    normalized: bytes,
    *,
    source_url: str,
    start_date: date,
    end_date: date,
    http: bool,
) -> EcbReferenceBatch:
    # Every caller re-reads and hash-checks both artifacts and checks the receipt first.
    # Cache by their full bytes, never an acquisition ID: changed proof cannot reuse a result.
    batch = _parse(raw, source_url=source_url, start_date=start_date, end_date=end_date)
    document = json.loads(normalized)
    expected = json.loads(json.dumps(asdict(batch)))
    if http:
        response = document.get("http_response") if isinstance(document, dict) else None
        _require_http_response(response, source_url, content_size=len(raw))
        expected["http_response"] = response
    if document != expected:
        raise ValueError("registered_ecb_normalized_mismatch")
    return batch


def _matches_content_length(declaration: str, content_size: int) -> bool:
    return declaration == "" or (
        re.fullmatch(r"[0-9]{1,12}", declaration) is not None and int(declaration) == content_size
    )


def _require_http_response(response: object, endpoint: str, *, content_size: int) -> None:
    if (
        not isinstance(response, dict)
        or set(response)
        != {
            "response_final_url",
            "response_http_status",
            "response_media_type",
            "response_complete",
            "response_content_length",
        }
        or not all(isinstance(v, str) for v in response.values())
    ):
        raise ValueError("ecb_reference_response_identity_invalid")
    if response["response_http_status"] != "200":
        # An answer that is itself a failure, not a response to check (ticket 18).
        raise SourceFailed(
            "ecb_reference_response_http_status_invalid",
            external_code=response["response_http_status"],
        )
    if response["response_final_url"] != endpoint:
        raise ValueError("ecb_reference_response_identity_invalid")
    if response["response_complete"] != "true" or not _matches_content_length(
        response["response_content_length"], content_size
    ):
        raise SourceFailed("ecb_reference_response_incomplete")
    if response["response_media_type"].split(";", 1)[0].strip().lower() != "application/zip":
        raise ValueError("ecb_reference_response_media_type_invalid")


def _fetch_zip(endpoint: str) -> FetchedEcbReferenceZip:
    request = Request(
        endpoint, headers={"Accept": "application/zip", "User-Agent": "pring-cycle/1.0"}
    )
    try:
        try:
            response = open_no_redirects(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            complete = True
            try:
                content = bytes(response.read(_MAX_ZIP_BYTES + 1))
            except IncompleteRead as error:
                content = error.partial[: _MAX_ZIP_BYTES + 1]
                complete = False
            content_length = (
                str(response.headers.get("Content-Length", "")) if response.headers else ""
            )
            complete = complete and _matches_content_length(content_length, len(content))
            return FetchedEcbReferenceZip(
                content,
                response.geturl(),
                int(response.status),
                str(response.headers.get("Content-Type", "")) if response.headers else "",
                complete,
                content_length,
            )
    except HTTPException as error:
        raise OSError("ecb_reference_http_protocol_failed") from error


def import_ecb_reference_cross(
    paths: RuntimePaths,
    content: bytes,
    *,
    source_url: str,
    start_date: date,
    end_date: date,
    definition_version: str,
) -> EcbReferenceImportResult:
    return _ingest(
        paths,
        content,
        source_url=source_url,
        start_date=start_date,
        end_date=end_date,
        definition_version=definition_version,
    )


def refresh_ecb_reference_cross(
    paths: RuntimePaths,
    *,
    start_date: date,
    end_date: date,
    definition_version: str,
    fetcher: Callable[[str], FetchedEcbReferenceZip] | None = None,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> EcbReferenceImportResult:
    return _ingest(
        paths,
        b"",
        source_url=ECB_HISTORY_URL,
        start_date=start_date,
        end_date=end_date,
        definition_version=definition_version,
        fetcher=fetcher or _fetch_zip,
        on_acquisition_started=on_acquisition_started,
    )


def _ingest(
    paths: RuntimePaths,
    content: bytes,
    *,
    source_url: str,
    start_date: date,
    end_date: date,
    definition_version: str,
    fetcher: Callable[[str], FetchedEcbReferenceZip] | None = None,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> EcbReferenceImportResult:
    definition = metric_definition(
        ECB_METRIC, definition_version=definition_version, database_path=paths.database
    )
    _definition(definition)
    _source_url(source_url)
    if end_date < start_date:
        raise ValueError("ecb_reference_date_range_invalid")
    repository = EvidenceRepository(paths.database)
    metadata = {
        "source_url": source_url,
        "start_date": str(start_date),
        "period": str(end_date),
        "definition_version": definition_version,
    }
    identities: list[str] = []
    response_metadata: dict[str, str] = {}
    channel = "ecb_reference_http" if fetcher else "ecb_reference_import"

    def started(acquisition_id: str) -> None:
        identities.append(acquisition_id)
        if on_acquisition_started is not None:
            on_acquisition_started(acquisition_id)

    def fetch() -> bytes:
        if fetcher is None:
            return content
        response = fetcher(source_url)
        response_metadata.update(
            response_final_url=response.final_url,
            response_http_status=str(response.http_status),
            response_media_type=response.media_type,
            response_complete=str(response.complete).lower(),
            response_content_length=response.content_length,
        )
        return response.content

    def parse(raw: bytes) -> EcbReferenceBatch:
        if fetcher is not None:
            _require_http_response(response_metadata, source_url, content_size=len(raw))
        return _parse(raw, source_url=source_url, start_date=start_date, end_date=end_date)

    try:
        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=ECB_PROVIDER,
            api_name="official_http_get" if fetcher else "document_import",
            parameters=metadata,
            fields="Date,CNY,USD",
            parser_version=_PARSER,
            fetch=fetch,
            parse=parse,
            normalize=lambda batch: {
                **asdict(batch),
                **({"http_response": response_metadata} if fetcher else {}),
            },
            on_started=started,
        )
    except Exception as error:
        outcome, recorded = capture_failure(error)
        repository.record_retrieval_attempt(
            metric_id=ECB_METRIC,
            channel=channel,
            outcome=outcome,
            fetched_at=utc_now(),
            acquisition_ids=tuple(identities),
            safe_metadata={**metadata, **response_metadata, **recorded},
        )
        raise
    batch, receipt = acquired.value, acquired.receipt
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    try:
        stored = _store_batch(repository, batch, receipt, definition, definition_version)
    except Exception as error:
        outcome, recorded = ingest_failure(error)
        if isinstance(error, ValueError):
            acquisitions.record_ingest_result(receipt.acquisition_id, error)
        repository.record_retrieval_attempt(
            metric_id=ECB_METRIC,
            channel=channel,
            outcome=outcome,
            fetched_at=utc_now(),
            acquisition_ids=(receipt.acquisition_id,),
            safe_metadata={**metadata, **response_metadata, **recorded},
        )
        raise
    if stored:
        acquisitions.record_ingest_result(receipt.acquisition_id, None)
    # A date one reference leg left blank is a member the delivery is missing (ticket 18).
    repository.record_retrieval_attempt(
        metric_id=ECB_METRIC,
        channel=channel,
        outcome=SUCCEEDED,
        fetched_at=utc_now(),
        acquisition_ids=(receipt.acquisition_id,),
        safe_metadata={
            **metadata,
            **response_metadata,
            **attempt_details(
                step="ingest" if stored else "structure",
                completeness=(
                    "source_empty"
                    if not stored
                    else "partial_members_missing"
                    if batch.missing
                    else "complete"
                ),
                missing_members=tuple(f"{row['date']}:{row['reason']}" for row in batch.missing),
                formula_version=batch.formula_version,
                observations=str(len(stored)),
                missing_rows=str(len(batch.missing)),
                **(
                    {
                        "condition": "reference_legs_missing"
                        if batch.missing
                        else "source_dates_missing"
                    }
                    if not stored
                    else {}
                ),
            ),
        },
    )
    return EcbReferenceImportResult(
        receipt.acquisition_id,
        len(stored),
        tuple(item.claim_id for item in stored),
        tuple(item.observation_id for item in stored),
    )


def _store_batch(
    repository: EvidenceRepository,
    batch: EcbReferenceBatch,
    receipt: AcquisitionReceipt,
    definition: MetricDefinition,
    definition_version: str,
) -> tuple[StoredSourceClaim, ...]:
    """Store the checked batch's rates, keeping a date's claim whose original still agrees."""
    if receipt.received_at is None or receipt.validated_at is None:
        raise ValueError("ecb_reference_acquisition_incomplete")
    wanted = {row.date for row in batch.rows}
    prior = {
        point.period_end: point
        for point in repository.metric_series(
            ECB_METRIC,
            mode=AsOfMode.SYSTEM,
            as_of=utc_now(),
            definition_version=definition_version,
        )
        if point.period_end in wanted and point.period_start == point.period_end
    }
    originals = repository.source_claim_acquisitions_many(
        tuple(
            point.selected_claim_id
            for point in prior.values()
            if point.selected_claim_id is not None
        )
    )
    prior_batches: dict[str, EcbReferenceBatch | None] = {}
    reused: dict[str, StoredSourceClaim] = {}
    for row in batch.rows:
        point = prior.get(row.date)
        if point is None:
            continue
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if (
            claim is None
            or point.selection_status != "selected"
            or claim.provider != ECB_PROVIDER
            or claim.quality_status != "validated"
            or claim.certification_status != definition.certification_status
            or claim.value_state is not EvidenceValueState.REPORTED_VALUE
            or claim.value != row.value
            or claim.unit != batch.unit
            or claim.source_reference != _reference(row.date)
            or claim.release_at is not None
            or claim.parsed_public_available_at is not None
        ):
            continue
        inputs = originals.get(claim.claim_id, ())
        if len(inputs) != 1:
            continue
        original = inputs[0]
        identity = original.receipt.acquisition_id
        if identity not in prior_batches:
            try:
                prior_batches[identity] = _validated_batch(
                    original.receipt,
                    original.raw,
                    original.normalized,
                    definition_versions=frozenset({definition_version}),
                )
            except (LookupError, OSError, TypeError, ValueError):
                prior_batches[identity] = None
        old_batch = prior_batches[identity]
        if old_batch is not None and any(
            old.date == row.date
            and Decimal(old.cny_per_eur) == Decimal(row.cny_per_eur)
            and Decimal(old.usd_per_eur) == Decimal(row.usd_per_eur)
            for old in old_batch.rows
        ):
            reused[row.date] = StoredSourceClaim(
                claim.claim_id,
                point.observation_id,
                claim.supersedes_claim_id,
            )
    claims = tuple(
        SourceClaimInput(
            metric_id=ECB_METRIC,
            definition_version=definition_version,
            period_kind="business_day",
            period_start=row.date,
            period_end=row.date,
            dimensions={},
            value=row.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=batch.unit,
            provider=ECB_PROVIDER,
            source_reference=_reference(row.date),
            release_event_id=f"unresolved-publication:ecb-reference:{receipt.acquisition_id}",
            release_at=None,
            public_available_at=None,
            fetched_at=receipt.received_at,
            available_at=receipt.validated_at,
            certification_status=definition.certification_status,
            quality_status="validated",
            acquisition_id=receipt.acquisition_id,
        )
        for row in batch.rows
        if row.date not in reused
    )
    created = iter(
        repository.append_source_claims(claims, availability_clock=utc_now) if claims else ()
    )
    return tuple(reused[row.date] if row.date in reused else next(created) for row in batch.rows)
