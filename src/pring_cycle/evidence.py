from __future__ import annotations

import hashlib
import json
import sqlite3
from bisect import bisect_right
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
    period_start: str
    period_end: str
    dimensions: dict[str, str]
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
class DerivedEvidenceTrace:
    derived_observation_id: str
    metric_id: str
    formula_version: str
    input_observation_version_ids: tuple[str, ...]
    as_of_mode: AsOfMode
    as_of_cutoff: datetime
    computed_at: datetime
    value: float | None
    unit: str


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


@dataclass(frozen=True)
class ReleaseEventView:
    release_event_id: str
    metric_id: str
    provider: str
    period: str
    release_at: datetime | None
    public_available_at: datetime | None
    available_at: datetime
    latest_fetched_at: datetime
    observation_count: int
    source_reference: str


@dataclass(frozen=True)
class RetrievalAttemptView:
    retrieval_attempt_id: str
    metric_id: str
    channel: str
    outcome: str
    fetched_at: datetime
    safe_metadata: dict[str, str]


@dataclass(frozen=True)
class ReleaseEventIdentity:
    release_event_id: str
    provider: str
    release_at: datetime | None
    public_available_at: datetime | None


@dataclass(frozen=True)
class SourceClaimRevision:
    claim_id: str
    observation_id: str
    supersedes_claim_id: str | None
    value: float | None
    value_state: EvidenceValueState
    unit: str
    release_event_id: str
    release_at: datetime | None
    public_available_at: datetime | None


@dataclass(frozen=True)
class SourceClaimVintage:
    claim_id: str
    period_start: str
    period_end: str
    public_available_at: datetime | None
    certification_status: str
    quality_status: str


class EvidenceRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._preloaded_series_rows: dict[
            tuple[str, str, AsOfMode],
            tuple[tuple[float, ...], tuple[sqlite3.Row, ...]],
        ] = {}

    @classmethod
    def create(cls, database_path: Path) -> EvidenceRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        repository._initialize()
        return repository

    def append_source_claim(self, claim: SourceClaimInput) -> StoredSourceClaim:
        return self.append_source_claims((claim,))[0]

    def append_source_claims(
        self,
        claims: tuple[SourceClaimInput, ...],
    ) -> tuple[StoredSourceClaim, ...]:
        if not claims:
            raise ValueError("evidence_claim_batch_required")
        for claim in claims:
            _validate_claim(claim)
        stored: list[StoredSourceClaim] = []
        with self._connect() as connection:
            for claim in claims:
                stored.append(_append_source_claim(connection, claim))
        self._preloaded_series_rows.clear()
        return tuple(stored)

    def preload_metric_series(
        self,
        metric_versions: set[tuple[str, str]],
    ) -> None:
        if not metric_versions:
            return
        ordered = sorted(metric_versions)
        clauses = " OR ".join("(metric_id=? AND definition_version=?)" for _ in ordered)
        parameters = tuple(value for pair in ordered for value in pair)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM source_claim WHERE {clauses}",
                parameters,
            ).fetchall()
        grouped: dict[tuple[str, str], list[sqlite3.Row]] = {
            pair: [] for pair in ordered
        }
        for row in rows:
            grouped[(str(row["metric_id"]), str(row["definition_version"]))].append(row)
        for pair, pair_rows in grouped.items():
            for mode, time_column in (
                (AsOfMode.PUBLIC, "public_available_at"),
                (AsOfMode.SYSTEM, "available_at"),
            ):
                visible_rows = [row for row in pair_rows if row[time_column] is not None]
                visible_rows.sort(
                    key=lambda row: (
                        _required_datetime(row[time_column]).timestamp(),
                        _required_datetime(row["available_at"]).timestamp(),
                        str(row["claim_id"]),
                    )
                )
                timestamps = tuple(
                    _required_datetime(row[time_column]).timestamp()
                    for row in visible_rows
                )
                self._preloaded_series_rows[(*pair, mode)] = (
                    timestamps,
                    tuple(visible_rows),
                )

    def release_events(self, *, metric_id: str | None = None) -> tuple[ReleaseEventView, ...]:
        return self.release_events_for_definition(metric_id=metric_id)

    def release_events_for_definition(
        self,
        *,
        metric_id: str | None = None,
        definition_version: str | None = None,
    ) -> tuple[ReleaseEventView, ...]:
        clauses = []
        parameters: list[str] = []
        if metric_id is not None:
            clauses.append("claim.metric_id = ?")
            parameters.append(metric_id)
        if definition_version is not None:
            clauses.append("claim.definition_version = ?")
            parameters.append(definition_version)
        clause = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT event.release_event_id, claim.metric_id, event.provider,
                       substr(MIN(claim.period_start), 1, 7) AS period,
                       event.release_at, event.public_available_at,
                       MIN(claim.available_at) AS available_at,
                       MAX(claim.fetched_at) AS latest_fetched_at,
                       COUNT(DISTINCT claim.observation_id) AS observation_count,
                       MIN(claim.source_reference) AS source_reference
                FROM release_event AS event
                JOIN source_claim AS claim
                  ON claim.release_event_id = event.release_event_id
                {clause}
                GROUP BY event.release_event_id, claim.metric_id, event.provider,
                         event.release_at, event.public_available_at
                ORDER BY MIN(claim.period_start), event.release_event_id
                """,
                tuple(parameters),
            ).fetchall()
        return tuple(
            ReleaseEventView(
                release_event_id=str(row["release_event_id"]),
                metric_id=str(row["metric_id"]),
                provider=str(row["provider"]),
                period=str(row["period"]),
                release_at=_datetime(row["release_at"]),
                public_available_at=_datetime(row["public_available_at"]),
                available_at=_required_datetime(row["available_at"]),
                latest_fetched_at=_required_datetime(row["latest_fetched_at"]),
                observation_count=int(row["observation_count"]),
                source_reference=str(row["source_reference"]),
            )
            for row in rows
        )

    def release_event_identity(self, release_event_id: str) -> ReleaseEventIdentity | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT release_event_id, provider, release_at, public_available_at
                FROM release_event WHERE release_event_id=?
                """,
                (release_event_id,),
            ).fetchone()
        if row is None:
            return None
        return ReleaseEventIdentity(
            release_event_id=str(row["release_event_id"]),
            provider=str(row["provider"]),
            release_at=_datetime(row["release_at"]),
            public_available_at=_datetime(row["public_available_at"]),
        )

    def latest_source_claim(
        self,
        *,
        metric_id: str,
        definition_version: str,
        period_kind: str,
        period_start: str,
        period_end: str,
        dimensions: dict[str, str],
        provider: str,
        source_reference: str,
    ) -> SourceClaimRevision | None:
        return self.latest_provider_claim(
            metric_id=metric_id,
            definition_version=definition_version,
            period_kind=period_kind,
            period_start=period_start,
            period_end=period_end,
            dimensions=dimensions,
            provider=provider,
            source_reference=source_reference,
        )

    def latest_provider_claim(
        self,
        *,
        metric_id: str,
        period_kind: str,
        period_start: str,
        period_end: str,
        dimensions: dict[str, str],
        provider: str,
        definition_version: str | None = None,
        source_reference: str | None = None,
    ) -> SourceClaimRevision | None:
        clauses = [
            "metric_id=?",
            "period_kind=?",
            "period_start=?",
            "period_end=?",
            "dimensions_json=?",
            "provider=?",
        ]
        parameters = [
            metric_id,
            period_kind,
            period_start,
            period_end,
            json.dumps(dimensions, ensure_ascii=False, sort_keys=True),
            provider,
        ]
        if definition_version is not None:
            clauses.append("definition_version=?")
            parameters.append(definition_version)
        if source_reference is not None:
            clauses.append("source_reference=?")
            parameters.append(source_reference)
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT claim_id, observation_id, supersedes_claim_id, value,
                       value_state, unit, release_event_id, release_at,
                       public_available_at
                FROM source_claim
                WHERE {' AND '.join(clauses)}
                ORDER BY julianday(available_at) DESC, rowid DESC LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()
        if row is None:
            return None
        return SourceClaimRevision(
            claim_id=str(row["claim_id"]),
            observation_id=str(row["observation_id"]),
            supersedes_claim_id=(
                str(row["supersedes_claim_id"])
                if row["supersedes_claim_id"] is not None
                else None
            ),
            value=float(row["value"]) if row["value"] is not None else None,
            value_state=EvidenceValueState(str(row["value_state"])),
            unit=str(row["unit"]),
            release_event_id=str(row["release_event_id"]),
            release_at=_datetime(row["release_at"]),
            public_available_at=_datetime(row["public_available_at"]),
        )

    def source_claim_vintages(
        self,
        metric_id: str,
        *,
        definition_version: str,
    ) -> tuple[SourceClaimVintage, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT claim_id, period_start, period_end, public_available_at,
                       certification_status, quality_status
                FROM source_claim
                WHERE metric_id=? AND definition_version=?
                ORDER BY julianday(public_available_at), rowid
                """,
                (metric_id, definition_version),
            ).fetchall()
        return tuple(
            SourceClaimVintage(
                claim_id=str(row["claim_id"]),
                period_start=str(row["period_start"]),
                period_end=str(row["period_end"]),
                public_available_at=_datetime(row["public_available_at"]),
                certification_status=str(row["certification_status"]),
                quality_status=str(row["quality_status"]),
            )
            for row in rows
        )

    def claims_for_release_source(
        self,
        release_event_id: str,
        source_reference: str,
        *,
        definition_version: str | None = None,
    ) -> tuple[StoredSourceClaim, ...]:
        definition_clause = (
            " AND definition_version=?" if definition_version is not None else ""
        )
        parameters = (
            (release_event_id, source_reference, definition_version)
            if definition_version is not None
            else (release_event_id, source_reference)
        )
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT claim_id, observation_id, supersedes_claim_id
                FROM source_claim
                WHERE release_event_id=? AND source_reference=?{definition_clause}
                ORDER BY rowid
                """,
                parameters,
            ).fetchall()
        return tuple(
            StoredSourceClaim(
                claim_id=str(row["claim_id"]),
                observation_id=str(row["observation_id"]),
                supersedes_claim_id=(
                    str(row["supersedes_claim_id"])
                    if row["supersedes_claim_id"] is not None
                    else None
                ),
            )
            for row in rows
        )

    def latest_retrieval_attempt(
        self,
        metric_id: str,
        *,
        period: str,
        as_of: datetime,
    ) -> RetrievalAttemptView | None:
        if as_of.tzinfo is None:
            raise ValueError("retrieval_attempt_as_of_must_be_timezone_aware")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM retrieval_attempt
                WHERE metric_id=? AND julianday(fetched_at) <= julianday(?)
                ORDER BY julianday(fetched_at) DESC, retrieval_attempt_id DESC
                """,
                (metric_id, _iso(as_of)),
            ).fetchall()
        for row in rows:
            metadata = {
                str(key): str(value)
                for key, value in json.loads(str(row["safe_metadata_json"])).items()
            }
            if metadata.get("period") != period:
                continue
            return RetrievalAttemptView(
                retrieval_attempt_id=str(row["retrieval_attempt_id"]),
                metric_id=str(row["metric_id"]),
                channel=str(row["channel"]),
                outcome=str(row["outcome"]),
                fetched_at=_required_datetime(row["fetched_at"]),
                safe_metadata=metadata,
            )
        return None

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
        return _select_claim_rows(
            observation_id,
            rows,
            mode=mode,
            as_of=as_of,
            tolerance=tolerance,
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
        definition_version: str | None = None,
    ) -> tuple[MetricSeriesPoint, ...]:
        if as_of.tzinfo is None:
            raise ValueError("as_of_must_be_timezone_aware")
        definition_clause = (
            " AND definition_version=?" if definition_version is not None else ""
        )
        time_column = {
            AsOfMode.PUBLIC: "public_available_at",
            AsOfMode.SYSTEM: "available_at",
        }[mode]
        parameters = (
            (metric_id, definition_version, _iso(as_of))
            if definition_version is not None
            else (metric_id, _iso(as_of))
        )
        cache_key = (
            (metric_id, definition_version, mode)
            if definition_version is not None
            else None
        )
        preloaded = (
            self._preloaded_series_rows.get(cache_key)
            if cache_key is not None
            else None
        )
        if preloaded is not None:
            timestamps, cached_rows = preloaded
            rows = list(cached_rows[: bisect_right(timestamps, as_of.timestamp())])
        else:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT * FROM source_claim
                    WHERE metric_id=?{definition_clause}
                      AND {time_column} IS NOT NULL
                      AND julianday({time_column}) <= julianday(?)
                    ORDER BY period_end, observation_id, julianday({time_column}),
                             julianday(available_at), claim_id
                    """,
                    parameters,
                ).fetchall()
        rows_by_observation: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            rows_by_observation.setdefault(str(row["observation_id"]), []).append(row)
        points = []
        for observation_id, observation_rows in rows_by_observation.items():
            result = _select_claim_rows(
                observation_id,
                observation_rows,
                mode=mode,
                as_of=as_of,
                tolerance=tolerance,
            )
            row = observation_rows[0]
            points.append(
                MetricSeriesPoint(
                    observation_id=result.observation_id,
                    period_start=str(row["period_start"]),
                    period_end=str(row["period_end"]),
                    dimensions={
                        str(key): str(value)
                        for key, value in json.loads(
                            str(row["dimensions_json"])
                        ).items()
                    },
                    selected_value=result.selected_value,
                    value_state=result.value_state,
                    selection_status=result.selection_status,
                    selected_claim_id=result.selected_claim_id,
                    claims=result.claims,
                )
            )
        points.sort(key=lambda point: (point.period_end, point.observation_id))
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

    def derived_trace(
        self,
        derived_observation_id: str,
        *,
        mode: AsOfMode,
        as_of: datetime,
    ) -> DerivedEvidenceTrace:
        if as_of.tzinfo is None:
            raise ValueError("as_of_must_be_timezone_aware")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM derived_observation
                WHERE derived_observation_id=?
                  AND as_of_mode=?
                  AND julianday(as_of_cutoff) <= julianday(?)
                  AND julianday(computed_at) <= julianday(?)
                """,
                (derived_observation_id, mode.value, _iso(as_of), _iso(as_of)),
            ).fetchone()
        if row is None:
            raise LookupError("derived_evidence_not_available")
        return DerivedEvidenceTrace(
            derived_observation_id=str(row["derived_observation_id"]),
            metric_id=str(row["metric_id"]),
            formula_version=str(row["formula_version"]),
            input_observation_version_ids=tuple(
                str(item)
                for item in json.loads(str(row["input_observation_version_ids_json"]))
            ),
            as_of_mode=AsOfMode(str(row["as_of_mode"])),
            as_of_cutoff=_required_datetime(row["as_of_cutoff"]),
            computed_at=_required_datetime(row["computed_at"]),
            value=float(row["value"]) if row["value"] is not None else None,
            unit=str(row["unit"]),
        )

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
            connection.executescript(_RELEASE_EVENT_EXTENSIONS_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _select_claim_rows(
    observation_id: str,
    rows: list[sqlite3.Row],
    *,
    mode: AsOfMode,
    as_of: datetime,
    tolerance: float,
) -> EvidenceQueryResult:
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


def _validate_claim(claim: SourceClaimInput) -> None:
    definition = metric_definition(
        claim.metric_id,
        definition_version=claim.definition_version,
    )
    if claim.definition_version != definition.definition_version:
        raise ValueError("evidence_definition_version_mismatch")
    allowed_units = definition.allowed_units or (definition.unit,)
    if claim.unit not in allowed_units:
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


def _append_source_claim(
    connection: sqlite3.Connection,
    claim: SourceClaimInput,
) -> StoredSourceClaim:
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
    existing_claim = connection.execute(
        "SELECT supersedes_claim_id FROM source_claim WHERE claim_id=?",
        (claim_id,),
    ).fetchone()
    if existing_claim is not None:
        supersedes = (
            str(existing_claim[0]) if existing_claim[0] is not None else None
        )
        return StoredSourceClaim(claim_id, observation_id, supersedes)
    existing_event = connection.execute(
        """
        SELECT provider, release_at, public_available_at FROM release_event
        WHERE release_event_id=?
        """,
        (claim.release_event_id,),
    ).fetchone()
    event_identity = (
        claim.provider,
        _iso(claim.release_at),
        _iso(claim.public_available_at),
    )
    if existing_event is not None and tuple(existing_event) != event_identity:
        raise ValueError("release_event_identity_conflict")
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
        (claim.release_event_id, *event_identity),
    )
    connection.execute(
        """
        INSERT INTO source_claim (
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

_RELEASE_EVENT_EXTENSIONS_SCHEMA = """
CREATE TRIGGER IF NOT EXISTS release_event_no_update
BEFORE UPDATE ON release_event BEGIN
    SELECT RAISE(ABORT, 'release_event_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS release_event_no_delete
BEFORE DELETE ON release_event BEGIN
    SELECT RAISE(ABORT, 'release_event_is_immutable');
END;
"""
