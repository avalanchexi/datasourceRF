from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from uuid import uuid4

from pring_cycle.artifacts import store_artifact
from pring_cycle.batches import row_count
from pring_cycle.storage import database_connection


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
    ``external_code`` is the source's own code, when it gave one.
    """

    def __init__(self, reason: str, *, external_code: int | str | None = None) -> None:
        super().__init__(reason)
        self.external_code = None if external_code is None else str(external_code)


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
            WHERE a.acquisition_id IN (SELECT value FROM json_each(?))
            """,
            (json.dumps(acquisition_ids),),
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
    ) -> Acquired[T]:
        if max_error_body_bytes is not None and max_error_body_bytes <= 0:
            raise ValueError("acquisition_error_body_limit_must_be_positive")
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
            self._receive(acquisition_id, raw, received_at, started_at)
            step = "parse"
            value = parse(raw)
            step = "normalize"
            receipt = (
                self.get(acquisition_id)
                if defer_validation
                else self.complete_validation(acquisition_id, normalize(value), clock=clock)
            )
        except Exception as error:
            # Only the response's own check refuses it; a failure before the request went
            # out, of the source, or of this system storing it is no refusal (ticket 18).
            self.fail_validation(acquisition_id, error, checked=refused_by_parse(error, step))
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
    ) -> AcquisitionReceipt:
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
                   validated_at=?, row_count=?, structure_check='passed'
                   WHERE acquisition_id=? AND state='received'""",
                (
                    artifact.content_hash,
                    validated_at.isoformat(),
                    row_count(normalized_value),
                    acquisition_id,
                ),
            )
        return self.get(acquisition_id)

    def fail_validation(
        self, acquisition_id: str, error: Exception, *, checked: bool = True
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
                (type(error).__name__, check, str(error)[:300], acquisition_id),
            )

    def record_ingest_result(self, acquisition_id: str, error: Exception | None) -> None:
        """Say once whether a validated call's values entered the evidence store, and if not why.

        The structure check and the ingest are separate: a response can pass the first and still
        be refused by the registered contract, which its receipt has to say (gap sources #03).
        """
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET ingest_result=?, ingest_rejection_reason=?
                   WHERE acquisition_id=? AND state='validated' AND ingest_result IS NULL""",
                (
                    "accepted" if error is None else "rejected",
                    None if error is None else str(error)[:300],
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

    def _receive(
        self, acquisition_id: str, raw: bytes, received_at: datetime, started_at: datetime
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
                """UPDATE acquisition_request SET raw_hash=?
                   WHERE acquisition_id=? AND state='received'""",
                (artifact.content_hash, acquisition_id),
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

# Every column but the ingest result: a terminal receipt never changes them.
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
)


def add_ingest_result_columns(connection: sqlite3.Connection) -> None:
    """Let a validated receipt record its ingest result once; safe to repeat.

    The terminal guard is narrowed to the other columns, and a second guard lets the two
    ingest columns be written only while still empty on a validated receipt.
    """
    existing = {str(row[1]) for row in connection.execute("PRAGMA table_info(acquisition_request)")}
    if not existing:
        return
    for column in ("ingest_result", "ingest_rejection_reason"):
        if column not in existing:
            connection.execute(f"ALTER TABLE acquisition_request ADD COLUMN {column} TEXT")
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
        and "UPDATE OF" in str(guard[0])
        and once is not None
        and "NEW.ingest_result IS NULL" in str(once[0])
    ):
        return
    connection.execute("DROP TRIGGER IF EXISTS acquisition_request_terminal_no_update")
    connection.execute(
        "CREATE TRIGGER acquisition_request_terminal_no_update BEFORE UPDATE OF "
        + ", ".join(_TERMINAL_COLUMNS)
        + " ON acquisition_request WHEN OLD.state IN ('validated', 'failed') BEGIN "
        "SELECT RAISE(ABORT, 'acquisition_receipt_is_immutable'); END"
    )
    # Both ingest columns are written once, together, and only on a validated receipt.
    connection.execute("DROP TRIGGER IF EXISTS acquisition_request_ingest_result_once")
    connection.execute(
        "CREATE TRIGGER acquisition_request_ingest_result_once BEFORE UPDATE OF "
        "ingest_result, ingest_rejection_reason ON acquisition_request "
        "WHEN OLD.state <> 'validated' OR OLD.ingest_result IS NOT NULL "
        "OR OLD.ingest_rejection_reason IS NOT NULL OR NEW.ingest_result IS NULL BEGIN "
        "SELECT RAISE(ABORT, 'acquisition_ingest_result_is_immutable'); END"
    )
