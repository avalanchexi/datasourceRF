from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from uuid import uuid4

from pring_cycle.artifacts import store_artifact
from pring_cycle.storage import database_connection

# A TuShare call refused for the day: the mark its receipt keeps (ticket 31).
DAILY_QUOTA_REFUSED = "tushare_daily_quota_refused"
# The phase of a receipt a run read but did not acquire (``reference_acquisitions``).
REFERENCED = "referenced"


def utc_now() -> datetime:
    return datetime.now(UTC)


def failed_step(error: BaseException) -> str | None:
    """Where in a call through the receipt store ``error`` arose, if it arose in one.

    ``start`` before any request went out (a budget refusing it), ``request`` asking,
    ``response`` an HTTP error's answer, ``store`` keeping the answer, ``parse`` reading
    it, ``normalize`` storing what it said.
    """
    step = getattr(error, "acquisition_step", None)
    return step if isinstance(step, str) else None


def refused_by_parse(error: BaseException, step: str | None) -> bool:
    """Whether reading the answer refused it: a rule it broke (ValueError) or a member it
    lacked (LookupError). Any other error there is this system's own (ticket 18)."""
    return step == "parse" and isinstance(error, ValueError | LookupError)


class SourceFailed(OSError):
    """The source answered with a failure, or not at all: there was no response to check.

    Raised by an adapter where it reads the answer (an HTTP status, a TuShare code), so the
    receipt keeps the answer without calling it a refused response (ticket 18).
    ``external_code`` is the source's own code, when it gave one; ``classification`` what
    the adapter reads it as.
    """

    def __init__(
        self,
        reason: str,
        *,
        external_code: int | str | None = None,
        classification: str | None = None,
        quota: str | None = None,
        source_message: object = None,
    ) -> None:
        super().__init__(reason)
        self.external_code = None if external_code is None else str(external_code)
        # The adapter's reading of the code, for whoever backs off on it (ticket 22):
        # ``rate_limited`` or ``forbidden``.
        self.classification = classification
        # Which of a rate limit's quotas it names, when it names one (ticket 31): ``daily``.
        self.quota = quota
        # What the source said, as it said it, for the attempt to keep (ticket 31).
        self.source_message = None if source_message is None else str(source_message)[:300]


@dataclass(frozen=True)
class AcquisitionOwner:
    database: Path
    run_id: str
    phase: str
    metric_ids: tuple[str, ...]
    period: str | None


_acquisition_owner: ContextVar[AcquisitionOwner | None] = ContextVar(
    "acquisition_owner", default=None
)
# What a call must pass before its receipt is written (``start_gate``).
_start_gate: ContextVar[Callable[[], None] | None] = ContextVar(
    "acquisition_start_gate", default=None
)


@contextmanager
def start_gate(gate: Callable[[], None] | None) -> Iterator[None]:
    """Have each call through the receipt store pass ``gate`` before its receipt is written.

    A call the gate holds back, by raising, sends nothing and leaves no receipt, as one held
    back for TuShare's quotas leaves none: a request held back is no failed call (audit
    2026-10-10, ticket 11). Its error is read as one before the request went out (``start``).
    ``None`` lifts an outer gate for the calls made inside.
    """
    token = _start_gate.set(gate)
    try:
        yield
    finally:
        _start_gate.reset(token)


@contextmanager
def own_acquisitions(
    database: Path,
    run_id: str,
    phase: str,
    *,
    metric_ids: tuple[str, ...] = (),
    period: str | None = None,
) -> Iterator[None]:
    token = _acquisition_owner.set(
        AcquisitionOwner(database.resolve(), run_id, phase, metric_ids, period)
    )
    try:
        yield
    finally:
        _acquisition_owner.reset(token)


def reference_acquisitions(database: Path, run_id: str, acquisition_ids: Iterable[str]) -> None:
    """Tie stored receipts the run read, made by another or by none, to the run.

    Retention then keeps them while it keeps the run (ticket 30). A reference is no call:
    the run's own calls, whose they are, and its TuShare quota all leave it out. A receipt
    the run acquired itself stays under the phase it was acquired in; one no longer held is
    passed over.
    """
    with database_connection(database) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO full_run_acquisition SELECT ?, acquisition_id, ?, '[]', NULL "
            "FROM acquisition_request WHERE acquisition_id IN (SELECT value FROM json_each(?))",
            (run_id, REFERENCED, json.dumps(sorted(acquisition_ids))),
        )


def owning_run(database: Path) -> str | None:
    """The run whose acquisitions against ``database`` are being made now, if any."""
    owner = _acquisition_owner.get()
    return owner.run_id if owner is not None and owner.database == database.resolve() else None


@contextmanager
def acquisition_metrics(metric_ids: tuple[str, ...]) -> Iterator[None]:
    owner = _acquisition_owner.get()
    token = _acquisition_owner.set(replace(owner, metric_ids=metric_ids) if owner else None)
    try:
        yield
    finally:
        _acquisition_owner.reset(token)


class CandidateSkipped(ValueError):
    """A candidate passed over by design for another of its kind, not a rejected response.

    Its receipt records the structure check as ``skipped`` with the reason, so the gap list,
    which lists rejections, does not show it (run findings 04).
    """


@dataclass(frozen=True)
class AcquisitionReceipt:
    acquisition_id: str
    provider: str
    api_name: str
    parameters: dict[str, str]
    fields: str
    parser_version: str
    started_at: datetime
    received_at: datetime | None
    validated_at: datetime | None
    state: str
    raw_hash: str | None
    normalized_hash: str | None
    error_type: str | None


@dataclass(frozen=True)
class ReceiptCounts:
    """Three counts a receipt keeps apart (lookback 06); None where one is not defined.

    ``source_records`` are the records the source returned (a TuShare row, a CSV line, a
    listing's dated entry), none for a page, which has no record of its own;
    ``normalized_scalars`` the values its answer was read as; ``ingested_claims`` the claims
    linked to the call once its ingest said its result. A claim already on file counts as
    well, and one claim shared by several calls counts on each, so this is what the call's
    values became, not how many rows it added.
    """

    source_records: int | None
    normalized_scalars: int | None
    ingested_claims: int | None


def tushare_records(raw: bytes) -> int | None:
    """The rows a TuShare answer carries in ``data.items``, before any parser filters them."""
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    data = document.get("data") if isinstance(document, dict) else None
    items = data.get("items") if isinstance(data, dict) else None
    return len(items) if isinstance(items, list) else None


def receipt_key(receipt: AcquisitionReceipt) -> tuple[object, ...]:
    """A hashable identity of every receipt field, for caches of work derived from it."""
    return (
        receipt.acquisition_id,
        receipt.provider,
        receipt.api_name,
        tuple(sorted(receipt.parameters.items())),
        receipt.fields,
        receipt.parser_version,
        receipt.started_at,
        receipt.received_at,
        receipt.validated_at,
        receipt.state,
        receipt.raw_hash,
        receipt.normalized_hash,
        receipt.error_type,
    )


def batch_analysis_context(database: Path, run_id: str) -> dict[str, str]:
    """The run a processing batch is, and its target day when the run is on record."""
    with database_connection(database) as connection:
        row = (
            connection.execute(
                "SELECT target_business_date FROM parent_run WHERE run_id=?", (run_id,)
            ).fetchone()
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='parent_run'"
            ).fetchone()
            else None
        )
    return {"run_id": run_id, **({"target_business_date": str(row[0])} if row else {})}


def acquisition_analysis_context(
    database: Path, acquisition_ids: tuple[str, ...]
) -> dict[str, str]:
    """Use persisted ownership; mixed or unbound originals have no single analysis target."""
    if not acquisition_ids:
        return {}
    with database_connection(database) as connection:
        if (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='full_run_acquisition'"
            ).fetchone()
            is None
        ):
            return {}
        rows = connection.execute(
            """
            SELECT a.acquisition_id, a.run_id, r.target_business_date
            FROM full_run_acquisition a JOIN parent_run r ON r.run_id=a.run_id
            WHERE a.acquisition_id IN (SELECT value FROM json_each(?)) AND a.phase != ?
            """,
            (json.dumps(acquisition_ids), REFERENCED),
        ).fetchall()
    if {row[0] for row in rows} != set(acquisition_ids):
        return {}
    contexts = {(str(row[1]), str(row[2])) for row in rows}
    if len(contexts) != 1:
        return {}
    run_id, target = next(iter(contexts))
    return {"run_id": run_id, "target_business_date": target}


@dataclass(frozen=True)
class Acquired[T]:
    value: T
    receipt: AcquisitionReceipt


class AcquisitionRepository:
    def __init__(self, database: Path, artifacts: Path) -> None:
        self.database = database
        self.artifacts = artifacts

    def capture[T](
        self,
        *,
        provider: str,
        api_name: str,
        parameters: dict[str, str],
        fields: str,
        parser_version: str,
        fetch: Callable[[], bytes],
        parse: Callable[[bytes], T],
        normalize: Callable[[T], object],
        clock: Callable[[], datetime] = utc_now,
        defer_validation: bool = False,
        on_started: Callable[[str], None] | None = None,
        max_error_body_bytes: int | None = None,
        count_records: Callable[[T], int | None] | None = None,
        count_scalars: Callable[[T], int | None] | None = None,
    ) -> Acquired[T]:
        """``count_records`` reads how many records the source returned from the parsed
        answer, and ``count_scalars`` how many values it was read as (lookback 06); either
        is left unknown when not given. A TuShare answer's records are its rows, counted as
        received so that an answer its parser refuses still says how many it carried. A
        deferred validation states its own counts."""
        if max_error_body_bytes is not None and max_error_body_bytes <= 0:
            raise ValueError("acquisition_error_body_limit_must_be_positive")
        if defer_validation and (count_records is not None or count_scalars is not None):
            raise ValueError("acquisition_deferred_count_unsupported")
        if (gate := _start_gate.get()) is not None:
            try:
                gate()
            except Exception as error:
                error.acquisition_step = "start"  # type: ignore[attr-defined]
                raise
        if provider == "tushare":
            from pring_cycle.tushare_quota import admit

            # Its quotas first: a call held back writes no receipt and sends nothing.
            admit(self.database, api_name)
        acquisition_id = "acquisition-" + uuid4().hex
        started_at = clock()
        _check_time(started_at)
        owner = _acquisition_owner.get()
        with self._connect() as connection:
            if owner is not None:
                self._require_active_owner(connection, owner)
            connection.execute(
                """INSERT INTO acquisition_request(
                    acquisition_id, provider, api_name, parameters_json, fields,
                    parser_version, started_at, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'started')""",
                (
                    acquisition_id,
                    provider,
                    api_name,
                    json.dumps(parameters, sort_keys=True),
                    fields,
                    parser_version,
                    started_at.isoformat(),
                ),
            )
            if owner is not None:
                connection.execute(
                    "INSERT INTO full_run_acquisition VALUES (?, ?, ?, ?, ?)",
                    (
                        owner.run_id,
                        acquisition_id,
                        owner.phase,
                        json.dumps(owner.metric_ids),
                        owner.period,
                    ),
                )
        step = "start"
        try:
            if on_started is not None:
                on_started(acquisition_id)
            if owner is not None:
                with self._connect() as connection:
                    self._require_active_owner(connection, owner)
            step = "request"
            try:
                raw = fetch()
            except HTTPError as error:
                step = "response"
                raw_error = (
                    error.read()
                    if max_error_body_bytes is None
                    else error.read(max_error_body_bytes)
                )
                self._receive(acquisition_id, raw_error, clock(), started_at)
                raise
            received_at = clock()
            step = "store"
            self._receive(
                acquisition_id,
                raw,
                received_at,
                started_at,
                records=tushare_records(raw) if provider == "tushare" else None,
            )
            step = "parse"
            value = parse(raw)
            records = None if count_records is None else count_records(value)
            scalars = None if count_scalars is None else count_scalars(value)
            step = "normalize"
            if defer_validation:
                receipt = self.get(acquisition_id)
            else:
                receipt = self.complete_validation(
                    acquisition_id,
                    normalize(value),
                    clock=clock,
                    source_records=records,
                    normalized_scalars=scalars,
                )
        except Exception as error:
            # Only the response's own check refuses it; a failure before the request went
            # out, of the source, or of this system storing it is no refusal (ticket 18).
            self.fail_validation(
                acquisition_id,
                error,
                checked=refused_by_parse(error, step),
                reason=(
                    f"{DAILY_QUOTA_REFUSED}: {getattr(error, 'source_message', None) or ''}"[:300]
                    if provider == "tushare" and getattr(error, "quota", None) == "daily"
                    else None
                ),
            )
            error.acquisition_step = step  # type: ignore[attr-defined]
            raise
        return Acquired(value, receipt)

    def _require_active_owner(
        self, connection: sqlite3.Connection, owner: AcquisitionOwner
    ) -> None:
        if owner.database != self.database.resolve():
            raise ValueError("acquisition_owner_database_mismatch")
        row = connection.execute(
            "SELECT status FROM parent_run WHERE run_id=?", (owner.run_id,)
        ).fetchone()
        if row is None or row[0] not in {"queued", "running"}:
            raise ValueError("acquisition_run_not_running")

    def complete_validation(
        self,
        acquisition_id: str,
        normalized_value: object,
        *,
        clock: Callable[[], datetime] = utc_now,
        source_records: int | None = None,
        normalized_scalars: int | None = None,
    ) -> AcquisitionReceipt:
        """Close a received call as validated. A source record count kept when its answer was
        received stays unless ``source_records`` gives one."""
        receipt = self.get(acquisition_id)
        if receipt.state != "received" or receipt.received_at is None:
            raise ValueError("acquisition_not_awaiting_validation")
        normalized = json.dumps(
            normalized_value,
            default=str,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        artifact = store_artifact(
            self.database,
            self.artifacts,
            normalized,
            "application/json",
            f"{acquisition_id}:normalized",
        )
        validated_at = clock()
        _check_time(validated_at, receipt.received_at)
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET state='validated', normalized_hash=?,
                   validated_at=?, structure_check='passed',
                   source_record_count=COALESCE(?, source_record_count),
                   normalized_scalar_count=?
                   WHERE acquisition_id=? AND state='received'""",
                (
                    artifact.content_hash,
                    validated_at.isoformat(),
                    source_records,
                    normalized_scalars,
                    acquisition_id,
                ),
            )
        return self.get(acquisition_id)

    def fail_validation(
        self,
        acquisition_id: str,
        error: Exception,
        *,
        checked: bool = True,
        reason: str | None = None,
    ) -> None:
        """Close a call as failed; one that had answered was rejected by its structure check,
        or skipped when the caller passed it over for another candidate.

        An answer that was itself a failure (an HTTP error, a source's refusal code) was not
        a response to check, and ``checked`` false says the call failed elsewhere than in
        its response's check: either way its receipt names no structure check (ticket 18).
        Why it failed is kept either way: a call failing before its answer was recorded (a
        clock stepping back, an unreachable source) otherwise left only the exception class.
        """
        check = (
            "skipped"
            if isinstance(error, CandidateSkipped)
            else None
            if not checked or isinstance(error, HTTPError | SourceFailed)
            else "rejected"
        )
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET state='failed', error_type=?,
                   structure_check=CASE WHEN state='received' THEN ? END,
                   rejection_reason=?
                   WHERE acquisition_id=? AND state IN ('started', 'received')""",
                (type(error).__name__, check, reason or str(error)[:300], acquisition_id),
            )

    def record_ingest_result(self, acquisition_id: str, error: Exception | None) -> None:
        """Say once whether a validated call's values entered the evidence store, and if not why.

        The structure check and the ingest are separate: a response can pass the first and still
        be refused by the registered contract, which its receipt has to say (gap sources #03).
        It also counts the claims now linked to the call: fewer than its scalars when members
        were out of scope or already held, none when refused (lookback 06).
        """
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET ingest_result=?, ingest_rejection_reason=?,
                   ingested_claim_count=(
                       SELECT COUNT(*) FROM source_claim_acquisition WHERE acquisition_id=?
                   )
                   WHERE acquisition_id=? AND state='validated' AND ingest_result IS NULL""",
                (
                    "accepted" if error is None else "rejected",
                    None if error is None else str(error)[:300],
                    acquisition_id,
                    acquisition_id,
                ),
            )

    def ingest_result(self, acquisition_id: str) -> tuple[str | None, str | None]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ingest_result, ingest_rejection_reason FROM acquisition_request "
                "WHERE acquisition_id=?",
                (acquisition_id,),
            ).fetchone()
        if row is None:
            raise LookupError("acquisition_not_found")
        return row[0], row[1]

    @contextmanager
    def ingesting(self, acquisition_ids: Iterable[str]) -> Iterator[None]:
        """Record the ingest result of these calls once the block storing their values ends:
        refused if the registered contract refused them (a ValueError), else accepted."""
        ids = tuple(dict.fromkeys(acquisition_ids))
        try:
            yield
        except ValueError as error:
            for acquisition_id in ids:
                self.record_ingest_result(acquisition_id, error)
            raise
        for acquisition_id in ids:
            self.record_ingest_result(acquisition_id, None)

    def counts(self, acquisition_id: str) -> ReceiptCounts:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT source_record_count, normalized_scalar_count, ingested_claim_count "
                "FROM acquisition_request WHERE acquisition_id=?",
                (acquisition_id,),
            ).fetchone()
        if row is None:
            raise LookupError("acquisition_not_found")
        return ReceiptCounts(row[0], row[1], row[2])

    def _receive(
        self,
        acquisition_id: str,
        raw: bytes,
        received_at: datetime,
        started_at: datetime,
        *,
        records: int | None = None,
    ) -> None:
        _check_time(received_at, started_at)
        if not isinstance(raw, bytes):
            raise ValueError("acquisition_raw_response_bytes_required")
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET state='received', received_at=?
                   WHERE acquisition_id=? AND state='started'""",
                (received_at.isoformat(), acquisition_id),
            )
        artifact = store_artifact(
            self.database,
            self.artifacts,
            raw,
            "application/octet-stream",
            f"{acquisition_id}:raw",
        )
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET raw_hash=?, source_record_count=?
                   WHERE acquisition_id=? AND state='received'""",
                (artifact.content_hash, records, acquisition_id),
            )

    def get(self, acquisition_id: str) -> AcquisitionReceipt:
        with self._connect() as connection:
            if not _schema_available(connection):
                raise LookupError("acquisition_not_found")
            row = connection.execute(
                "SELECT * FROM acquisition_request WHERE acquisition_id=?", (acquisition_id,)
            ).fetchone()
        if row is None:
            raise LookupError("acquisition_not_found")
        return receipt_from_row(row)

    def history(self) -> tuple[AcquisitionReceipt, ...]:
        with self._connect() as connection:
            if not _schema_available(connection):
                return ()
            rows = connection.execute("SELECT * FROM acquisition_request ORDER BY rowid").fetchall()
        return tuple(receipt_from_row(row) for row in rows)

    def validated_receipts(
        self, *, api_names: tuple[str, ...], parser_version: str, parameters: Mapping[str, str]
    ) -> tuple[AcquisitionReceipt, ...]:
        """The validated calls of these APIs read by this parser whose parameters include
        ``parameters``, earliest received first."""
        clauses = ["state='validated'", "parser_version=?"]
        values: list[str] = [parser_version]
        clauses.append(f"api_name IN ({','.join('?' for _ in api_names)})")
        values.extend(api_names)
        for key, value in sorted(parameters.items()):
            clauses.append("json_extract(parameters_json, ?)=?")
            values.extend((f'$."{key}"', value))
        with self._connect() as connection:
            if not _schema_available(connection):
                return ()
            rows = connection.execute(
                f"SELECT * FROM acquisition_request WHERE {' AND '.join(clauses)} "
                "ORDER BY julianday(received_at), rowid",
                values,
            ).fetchall()
        return tuple(receipt_from_row(row) for row in rows)

    def read_content(self, acquisition_id: str, kind: str) -> bytes:
        return self.read_receipt_content(self.get(acquisition_id), kind)

    def read_receipt_content(
        self,
        receipt: AcquisitionReceipt,
        kind: str,
        verified: dict[str, bytes] | None = None,
    ) -> bytes:
        """Read one hash-checked artifact of a receipt the caller has already loaded.

        Receipt checks always run; ``verified`` only shares bytes already hash-checked by the
        same caller for an identical digest.
        """
        if kind not in {"raw", "normalized"}:
            raise ValueError("acquisition_artifact_kind_invalid")
        expiry = response_retention_deadline(
            receipt.provider, receipt.api_name, receipt.received_at
        )
        if kind == "raw" and expiry is not None and expiry <= utc_now():
            raise LookupError("search_response_expired")
        digest = receipt.raw_hash if kind == "raw" else receipt.normalized_hash
        if digest is None:
            raise LookupError("acquisition_artifact_unavailable")
        if verified is not None and digest in verified:
            return verified[digest]
        content = (self.artifacts / digest[:2] / digest).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("artifact_hash_mismatch")
        if verified is not None:
            verified[digest] = content
        return content

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self.database) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection


def _check_time(value: datetime, previous: datetime | None = None) -> None:
    if value.tzinfo is None or (previous is not None and value < previous):
        raise ValueError("acquisition_time_invalid")


def response_retention_deadline(
    provider: str, api_name: str, received_at: datetime | None
) -> datetime | None:
    if provider in {"tavily", "exa"} and api_name == "search" and received_at is not None:
        return received_at + timedelta(days=30)
    return None


def _schema_available(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='acquisition_request'"
        ).fetchone()
        is not None
    )


def receipt_from_row(row: sqlite3.Row) -> AcquisitionReceipt:
    def timestamp(value: Any) -> datetime | None:
        return datetime.fromisoformat(str(value)) if value is not None else None

    return AcquisitionReceipt(
        acquisition_id=str(row["acquisition_id"]),
        provider=str(row["provider"]),
        api_name=str(row["api_name"]),
        parameters=json.loads(row["parameters_json"]),
        fields=str(row["fields"]),
        parser_version=str(row["parser_version"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        received_at=timestamp(row["received_at"]),
        validated_at=timestamp(row["validated_at"]),
        state=str(row["state"]),
        raw_hash=row["raw_hash"],
        normalized_hash=row["normalized_hash"],
        error_type=row["error_type"],
    )


ACQUISITION_SCHEMA = """
CREATE TABLE IF NOT EXISTS acquisition_request (
    acquisition_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    api_name TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    fields TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    received_at TEXT,
    validated_at TEXT,
    state TEXT NOT NULL CHECK(state IN ('started', 'received', 'validated', 'failed')),
    raw_hash TEXT,
    normalized_hash TEXT,
    error_type TEXT
);
CREATE TABLE IF NOT EXISTS source_claim_acquisition (
    claim_id TEXT NOT NULL REFERENCES source_claim(claim_id),
    acquisition_id TEXT NOT NULL REFERENCES acquisition_request(acquisition_id),
    PRIMARY KEY(claim_id, acquisition_id)
);
CREATE TRIGGER IF NOT EXISTS acquisition_request_terminal_no_update
BEFORE UPDATE ON acquisition_request WHEN OLD.state IN ('validated', 'failed') BEGIN
    SELECT RAISE(ABORT, 'acquisition_receipt_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS acquisition_request_no_delete
BEFORE DELETE ON acquisition_request BEGIN
    SELECT RAISE(ABORT, 'acquisition_request_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS source_claim_acquisition_no_update
BEFORE UPDATE ON source_claim_acquisition BEGIN
    SELECT RAISE(ABORT, 'claim_acquisition_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS source_claim_acquisition_no_delete
BEFORE DELETE ON source_claim_acquisition BEGIN
    SELECT RAISE(ABORT, 'claim_acquisition_is_immutable');
END;
"""

# Every column but the ingest result: a terminal receipt never changes them. ``row_count`` is
# no longer written: it mixed source rows with normalized values (lookback 06).
_TERMINAL_COLUMNS = (
    "acquisition_id",
    "provider",
    "api_name",
    "parameters_json",
    "fields",
    "parser_version",
    "started_at",
    "received_at",
    "validated_at",
    "state",
    "raw_hash",
    "normalized_hash",
    "error_type",
    "row_count",
    "structure_check",
    "rejection_reason",
    "source_record_count",
    "normalized_scalar_count",
)
# Written once, together, on a validated receipt.
_INGEST_COLUMNS = ("ingest_result", "ingest_rejection_reason", "ingested_claim_count")
_COUNT_COLUMNS = ("source_record_count", "normalized_scalar_count", "ingested_claim_count")


def add_receipt_columns(connection: sqlite3.Connection) -> None:
    """Let a validated receipt record its ingest result once, and every receipt its counts;
    safe to repeat.

    The terminal guard is narrowed to the other columns, and a second guard lets the ingest
    columns be written only while still empty on a validated receipt.
    """
    existing = {str(row[1]) for row in connection.execute("PRAGMA table_info(acquisition_request)")}
    if not existing:
        return
    for column in ("ingest_result", "ingest_rejection_reason"):
        if column not in existing:
            connection.execute(f"ALTER TABLE acquisition_request ADD COLUMN {column} TEXT")
    for column in _COUNT_COLUMNS:
        if column not in existing:
            connection.execute(f"ALTER TABLE acquisition_request ADD COLUMN {column} INTEGER")
    guard = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='acquisition_request_terminal_no_update'"
    ).fetchone()
    once = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='acquisition_request_ingest_result_once'"
    ).fetchone()
    if (
        guard is not None
        and "normalized_scalar_count" in str(guard[0])
        and once is not None
        and "NEW.ingested_claim_count IS NULL" in str(once[0])
    ):
        return
    connection.execute("DROP TRIGGER IF EXISTS acquisition_request_terminal_no_update")
    connection.execute(
        "CREATE TRIGGER acquisition_request_terminal_no_update BEFORE UPDATE OF "
        + ", ".join(_TERMINAL_COLUMNS)
        + " ON acquisition_request WHEN OLD.state IN ('validated', 'failed') BEGIN "
        "SELECT RAISE(ABORT, 'acquisition_receipt_is_immutable'); END"
    )
    connection.execute("DROP TRIGGER IF EXISTS acquisition_request_ingest_result_once")
    connection.execute(
        "CREATE TRIGGER acquisition_request_ingest_result_once BEFORE UPDATE OF "
        + ", ".join(_INGEST_COLUMNS)
        + " ON acquisition_request "
        "WHEN OLD.state <> 'validated' OR OLD.ingest_result IS NOT NULL "
        "OR OLD.ingest_rejection_reason IS NOT NULL OR OLD.ingested_claim_count IS NOT NULL "
        "OR NEW.ingest_result IS NULL OR NEW.ingested_claim_count IS NULL BEGIN "
        "SELECT RAISE(ABORT, 'acquisition_ingest_result_is_immutable'); END"
    )
