from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from uuid import uuid4

from pring_cycle.artifacts import store_artifact


def utc_now() -> datetime:
    return datetime.now(UTC)


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
    ) -> Acquired[T]:
        acquisition_id = "acquisition-" + uuid4().hex
        started_at = clock()
        _check_time(started_at)
        with self._connect() as connection:
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
        try:
            if on_started is not None:
                on_started(acquisition_id)
            try:
                raw = fetch()
            except HTTPError as error:
                self._receive(acquisition_id, error.read(), clock(), started_at)
                raise
            received_at = clock()
            self._receive(acquisition_id, raw, received_at, started_at)
            value = parse(raw)
            receipt = (
                self.get(acquisition_id)
                if defer_validation
                else self.complete_validation(acquisition_id, normalize(value), clock=clock)
            )
            return Acquired(value, receipt)
        except Exception as error:
            self.fail_validation(acquisition_id, error)
            raise

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
                   validated_at=? WHERE acquisition_id=? AND state='received'""",
                (artifact.content_hash, validated_at.isoformat(), acquisition_id),
            )
        return self.get(acquisition_id)

    def fail_validation(self, acquisition_id: str, error: Exception) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE acquisition_request SET state='failed', error_type=?
                   WHERE acquisition_id=? AND state IN ('started', 'received')""",
                (type(error).__name__, acquisition_id),
            )

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
        receipt = self.get(acquisition_id)
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
        content = (self.artifacts / digest[:2] / digest).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("artifact_hash_mismatch")
        return content

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


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
