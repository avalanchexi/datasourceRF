from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Any

from pring_cycle.catalog import metric_definition


class AsOfMode(StrEnum):
    PUBLIC = "public_as_of"
    SYSTEM = "system_as_of"


class EvidenceValueState(StrEnum):
    REPORTED_VALUE = "reported_value"
    NOT_APPLICABLE = "not_applicable"
    NOT_DISCLOSED = "not_disclosed"


@dataclass(frozen=True)
class SourceClaimInput:
    metric_id: str
    definition_version: str
    period_kind: str
    period_start: str
    period_end: str
    dimensions: dict[str, str]
    value: float | None
    value_state: EvidenceValueState
    unit: str
    provider: str
    source_reference: str
    release_event_id: str
    release_at: datetime | None
    public_available_at: datetime | None
    fetched_at: datetime
    available_at: datetime
    certification_status: str
    quality_status: str


@dataclass(frozen=True)
class StoredSourceClaim:
    claim_id: str
    observation_id: str
    supersedes_claim_id: str | None


@dataclass(frozen=True)
class ClaimView:
    claim_id: str
    provider: str
    value: float | None
    value_state: EvidenceValueState
    unit: str
    source_reference: str
    release_at: datetime | None
    public_available_at: datetime | None
    fetched_at: datetime
    available_at: datetime
    certification_status: str
    quality_status: str
    supersedes_claim_id: str | None


@dataclass(frozen=True)
class EvidenceQueryResult:
    observation_id: str
    mode: AsOfMode
    as_of: datetime
    selection_status: str
    selected_claim_id: str | None
    selected_value: float | None
    value_state: EvidenceValueState | None
    claims: tuple[ClaimView, ...]


@dataclass(frozen=True)
class MetricSeriesPoint:
    observation_id: str
    period_end: str
    selected_value: float | None
    value_state: EvidenceValueState | None
    selection_status: str
    selected_claim_id: str | None
    claims: tuple[ClaimView, ...]


@dataclass(frozen=True)
class EvidenceTrace:
    observation_id: str
    metric_id: str
    definition_version: str
    period_kind: str
    period_start: str
    period_end: str
    dimensions: dict[str, str]
    mode: AsOfMode
    as_of: datetime
    selection_status: str
    selected_claim_id: str | None
    selected_value: float | None
    value_state: EvidenceValueState | None
    claims: tuple[ClaimView, ...]


@dataclass(frozen=True)
class StoredDerivedObservation:
    derived_observation_id: str
    input_observation_version_ids: tuple[str, ...]


@dataclass(frozen=True)
class FrozenEvidenceSnapshot:
    evidence_snapshot_id: str
    as_of_mode: AsOfMode
    as_of_cutoff: datetime
    observation_version_ids: tuple[str, ...]


class EvidenceRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> EvidenceRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        repository._initialize()
        return repository

    def append_source_claim(self, claim: SourceClaimInput) -> StoredSourceClaim:
        _validate_claim(claim)
        dimensions_json = json.dumps(claim.dimensions, ensure_ascii=False, sort_keys=True)
        observation_id = _stable_hash(
            claim.metric_id,
            claim.definition_version,
            claim.period_kind,
            claim.period_start,
            claim.period_end,
            dimensions_json,
        )
        claim_id = _stable_hash(
            observation_id,
            claim.provider,
            claim.source_reference,
            claim.value_state.value,
            repr(claim.value),
            _iso(claim.public_available_at) or "",
            _iso(claim.available_at) or "",
        )
        with self._connect() as connection:
            previous = connection.execute(
                """
                SELECT claim_id FROM source_claim
                WHERE observation_id = ? AND provider = ?
                ORDER BY julianday(available_at) DESC, claim_id DESC LIMIT 1
                """,
                (observation_id, claim.provider),
            ).fetchone()
            supersedes_claim_id = str(previous[0]) if previous is not None else None
            connection.execute(
                """
                INSERT OR IGNORE INTO release_event (
                    release_event_id, provider, release_at, public_available_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    claim.release_event_id,
                    claim.provider,
                    _iso(claim.release_at),
                    _iso(claim.public_available_at),
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO source_claim (
                    claim_id, observation_id, metric_id, definition_version,
                    period_kind, period_start, period_end, dimensions_json,
                    value, value_state, unit, provider, source_reference,
                    release_event_id, release_at, public_available_at, fetched_at,
                    available_at, certification_status, quality_status,
                    supersedes_claim_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    observation_id,
                    claim.metric_id,
                    claim.definition_version,
                    claim.period_kind,
                    claim.period_start,
                    claim.period_end,
                    dimensions_json,
                    claim.value,
                    claim.value_state.value,
                    claim.unit,
                    claim.provider,
                    claim.source_reference,
                    claim.release_event_id,
                    _iso(claim.release_at),
                    _iso(claim.public_available_at),
                    _iso(claim.fetched_at),
                    _iso(claim.available_at),
                    claim.certification_status,
                    claim.quality_status,
                    supersedes_claim_id,
                ),
            )
        return StoredSourceClaim(claim_id, observation_id, supersedes_claim_id)

    def query(
        self,
        observation_id: str,
        *,
        mode: AsOfMode,
        as_of: datetime,
        tolerance: float = 0.0,
    ) -> EvidenceQueryResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of_must_be_timezone_aware")
        time_column = {
            AsOfMode.PUBLIC: "public_available_at",
            AsOfMode.SYSTEM: "available_at",
        }[mode]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM source_claim
                WHERE observation_id = ?
                  AND {time_column} IS NOT NULL
                  AND julianday({time_column}) <= julianday(?)
                ORDER BY julianday({time_column}), julianday(available_at), claim_id
                """,
                (observation_id, _iso(as_of)),
            ).fetchall()
        newest_by_provider: dict[str, sqlite3.Row] = {}
        for row in rows:
            newest_by_provider[str(row["provider"])] = row
        claims = tuple(_claim_view(row) for row in newest_by_provider.values())
        if not claims:
            return EvidenceQueryResult(
                observation_id,
                mode,
                as_of,
                "unavailable",
                None,
                None,
                None,
                (),
            )
        selected = sorted(
            claims,
            key=lambda item: (item.certification_status != "certified", item.provider),
        )[0]
        reported_values = [
            item.value
            for item in claims
            if item.value_state is EvidenceValueState.REPORTED_VALUE and item.value is not None
        ]
        conflicted = bool(reported_values) and (
            max(reported_values) - min(reported_values) > tolerance
        )
        return EvidenceQueryResult(
            observation_id=observation_id,
            mode=mode,
            as_of=as_of,
            selection_status="conflicted" if conflicted else "selected",
            selected_claim_id=selected.claim_id,
            selected_value=selected.value,
            value_state=selected.value_state,
            claims=claims,
        )

    def claim_count(self, observation_id: str) -> int:
        with self._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM source_claim WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
        return int(count[0]) if count is not None else 0

    def metric_series(
        self,
        metric_id: str,
        *,
        mode: AsOfMode,
        as_of: datetime,
        tolerance: float = 0.0,
    ) -> tuple[MetricSeriesPoint, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT observation_id, period_end
                FROM source_claim
                WHERE metric_id=?
                GROUP BY observation_id, period_end
                ORDER BY period_end, observation_id
                """,
                (metric_id,),
            ).fetchall()
        points = []
        for row in rows:
            result = self.query(
                str(row["observation_id"]),
                mode=mode,
                as_of=as_of,
                tolerance=tolerance,
            )
            if result.selection_status == "unavailable":
                continue
            points.append(
                MetricSeriesPoint(
                    observation_id=result.observation_id,
                    period_end=str(row["period_end"]),
                    selected_value=result.selected_value,
                    value_state=result.value_state,
                    selection_status=result.selection_status,
                    selected_claim_id=result.selected_claim_id,
                    claims=result.claims,
                )
            )
        return tuple(points)

    def trace(
        self,
        observation_id: str,
        *,
        mode: AsOfMode,
        as_of: datetime,
        tolerance: float = 0.0,
    ) -> EvidenceTrace:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT metric_id, definition_version, period_kind, period_start,
                       period_end, dimensions_json
                FROM source_claim WHERE observation_id=?
                ORDER BY available_at LIMIT 1
                """,
                (observation_id,),
            ).fetchone()
        if row is None:
            raise LookupError("evidence_observation_not_found")
        queried = self.query(
            observation_id,
            mode=mode,
            as_of=as_of,
            tolerance=tolerance,
        )
        return EvidenceTrace(
            observation_id=observation_id,
            metric_id=str(row["metric_id"]),
            definition_version=str(row["definition_version"]),
            period_kind=str(row["period_kind"]),
            period_start=str(row["period_start"]),
            period_end=str(row["period_end"]),
            dimensions={
                str(key): str(value)
                for key, value in json.loads(str(row["dimensions_json"])).items()
            },
            mode=mode,
            as_of=as_of,
            selection_status=queried.selection_status,
            selected_claim_id=queried.selected_claim_id,
            selected_value=queried.selected_value,
            value_state=queried.value_state,
            claims=queried.claims,
        )

    def append_derived_observation(
        self,
        *,
        metric_id: str,
        formula_version: str,
        input_observation_version_ids: tuple[str, ...],
        as_of_mode: AsOfMode,
        as_of_cutoff: datetime,
        computed_at: datetime,
        value: float | None,
        unit: str,
    ) -> StoredDerivedObservation:
        if as_of_cutoff.tzinfo is None or computed_at.tzinfo is None:
            raise ValueError("derived_observation_times_must_be_timezone_aware")
        if not input_observation_version_ids:
            raise ValueError("derived_observation_inputs_required")
        inputs = tuple(sorted(input_observation_version_ids))
        derived_id = _stable_hash(
            metric_id,
            formula_version,
            *inputs,
            as_of_mode.value,
            as_of_cutoff.isoformat(),
            repr(value),
            unit,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO derived_observation(
                    derived_observation_id, metric_id, formula_version,
                    input_observation_version_ids_json, as_of_mode, as_of_cutoff,
                    computed_at, value, unit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    derived_id,
                    metric_id,
                    formula_version,
                    json.dumps(inputs, separators=(",", ":")),
                    as_of_mode.value,
                    as_of_cutoff.isoformat(),
                    computed_at.isoformat(),
                    value,
                    unit,
                ),
            )
        return StoredDerivedObservation(derived_id, inputs)

    def record_retrieval_attempt(
        self,
        *,
        metric_id: str,
        channel: str,
        outcome: str,
        fetched_at: datetime,
        safe_metadata: dict[str, str],
    ) -> str:
        if fetched_at.tzinfo is None:
            raise ValueError("retrieval_attempt_time_must_be_timezone_aware")
        metadata_json = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True)
        attempt_id = _stable_hash(
            metric_id,
            channel,
            outcome,
            fetched_at.isoformat(),
            metadata_json,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO retrieval_attempt(
                    retrieval_attempt_id, metric_id, channel, outcome,
                    fetched_at, safe_metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (attempt_id, metric_id, channel, outcome, fetched_at.isoformat(), metadata_json),
            )
        return attempt_id

    def freeze_snapshot(
        self,
        observation_version_ids: tuple[str, ...],
        *,
        mode: AsOfMode,
        as_of: datetime,
    ) -> FrozenEvidenceSnapshot:
        if as_of.tzinfo is None:
            raise ValueError("snapshot_as_of_must_be_timezone_aware")
        versions = tuple(sorted(set(observation_version_ids)))
        if not versions:
            raise ValueError("snapshot_observations_required")
        snapshot_id = "snapshot-" + _stable_hash(mode.value, as_of.isoformat(), *versions)[:20]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_snapshot(
                    evidence_snapshot_id, as_of_mode, as_of_cutoff,
                    observation_version_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    mode.value,
                    as_of.isoformat(),
                    json.dumps(versions, separators=(",", ":")),
                    datetime.now(as_of.tzinfo).isoformat(),
                ),
            )
        return FrozenEvidenceSnapshot(snapshot_id, mode, as_of, versions)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_EVIDENCE_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _validate_claim(claim: SourceClaimInput) -> None:
    definition = metric_definition(claim.metric_id)
    if claim.definition_version != definition.definition_version:
        raise ValueError("evidence_definition_version_mismatch")
    if claim.unit != definition.unit:
        raise ValueError("evidence_unit_mismatch")
    if set(claim.dimensions) != set(definition.dimensions):
        raise ValueError("evidence_dimensions_mismatch")
    if (
        claim.certification_status == "certified"
        and definition.certification_status != "certified"
    ):
        raise ValueError("evidence_source_not_certified_by_model")
    if claim.certification_status not in {
        "certified",
        "awaiting_source_certification",
    }:
        raise ValueError("evidence_certification_status_invalid")
    if claim.quality_status not in {"validated", "unverified", "invalid"}:
        raise ValueError("evidence_quality_status_invalid")
    if claim.available_at.tzinfo is None or claim.fetched_at.tzinfo is None:
        raise ValueError("evidence_times_must_be_timezone_aware")
    if claim.public_available_at is not None and claim.public_available_at.tzinfo is None:
        raise ValueError("evidence_times_must_be_timezone_aware")
    if claim.value_state is EvidenceValueState.REPORTED_VALUE and claim.value is None:
        raise ValueError("reported_value_requires_number")
    if claim.value is not None and not isfinite(claim.value):
        raise ValueError("evidence_value_must_be_finite")
    if claim.value_state is not EvidenceValueState.REPORTED_VALUE and claim.value is not None:
        raise ValueError("non_numeric_value_state_rejects_number")


def _claim_view(row: sqlite3.Row) -> ClaimView:
    return ClaimView(
        claim_id=str(row["claim_id"]),
        provider=str(row["provider"]),
        value=float(row["value"]) if row["value"] is not None else None,
        value_state=EvidenceValueState(str(row["value_state"])),
        unit=str(row["unit"]),
        source_reference=str(row["source_reference"]),
        release_at=_datetime(row["release_at"]),
        public_available_at=_datetime(row["public_available_at"]),
        fetched_at=_required_datetime(row["fetched_at"]),
        available_at=_required_datetime(row["available_at"]),
        certification_status=str(row["certification_status"]),
        quality_status=str(row["quality_status"]),
        supersedes_claim_id=(
            str(row["supersedes_claim_id"]) if row["supersedes_claim_id"] is not None else None
        ),
    )


def _stable_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _datetime(value: Any) -> datetime | None:
    return datetime.fromisoformat(str(value)).astimezone(UTC) if value is not None else None


def _required_datetime(value: Any) -> datetime:
    parsed = _datetime(value)
    if parsed is None:
        raise ValueError("required_evidence_time_missing")
    return parsed


_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS release_event (
    release_event_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    release_at TEXT,
    public_available_at TEXT
);
CREATE TABLE IF NOT EXISTS source_claim (
    claim_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    definition_version TEXT NOT NULL,
    period_kind TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    value REAL,
    value_state TEXT NOT NULL,
    unit TEXT NOT NULL,
    provider TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    release_event_id TEXT NOT NULL REFERENCES release_event(release_event_id),
    release_at TEXT,
    public_available_at TEXT,
    fetched_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    certification_status TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    supersedes_claim_id TEXT REFERENCES source_claim(claim_id)
);
CREATE INDEX IF NOT EXISTS ix_source_claim_observation
ON source_claim(observation_id, available_at);
CREATE TRIGGER IF NOT EXISTS source_claim_no_update
BEFORE UPDATE ON source_claim BEGIN SELECT RAISE(ABORT, 'source_claim_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_claim_no_delete
BEFORE DELETE ON source_claim BEGIN SELECT RAISE(ABORT, 'source_claim_is_immutable'); END;
CREATE TABLE IF NOT EXISTS derived_observation (
    derived_observation_id TEXT PRIMARY KEY,
    metric_id TEXT NOT NULL,
    formula_version TEXT NOT NULL,
    input_observation_version_ids_json TEXT NOT NULL,
    as_of_mode TEXT NOT NULL,
    as_of_cutoff TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS retrieval_attempt (
    retrieval_attempt_id TEXT PRIMARY KEY,
    metric_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    outcome TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    safe_metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_snapshot (
    evidence_snapshot_id TEXT PRIMARY KEY,
    as_of_mode TEXT NOT NULL,
    as_of_cutoff TEXT NOT NULL,
    observation_version_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS derived_observation_no_update
BEFORE UPDATE ON derived_observation BEGIN
    SELECT RAISE(ABORT, 'derived_observation_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS derived_observation_no_delete
BEFORE DELETE ON derived_observation BEGIN
    SELECT RAISE(ABORT, 'derived_observation_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS retrieval_attempt_no_update
BEFORE UPDATE ON retrieval_attempt BEGIN
    SELECT RAISE(ABORT, 'retrieval_attempt_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS retrieval_attempt_no_delete
BEFORE DELETE ON retrieval_attempt BEGIN
    SELECT RAISE(ABORT, 'retrieval_attempt_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_snapshot_no_update
BEFORE UPDATE ON evidence_snapshot BEGIN
    SELECT RAISE(ABORT, 'evidence_snapshot_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS evidence_snapshot_no_delete
BEFORE DELETE ON evidence_snapshot BEGIN
    SELECT RAISE(ABORT, 'evidence_snapshot_is_immutable');
END;
"""
