from __future__ import annotations

import hashlib
import json
import sqlite3
from bisect import bisect_right
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from math import isfinite
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import (
    ACQUISITION_SCHEMA,
    AcquisitionReceipt,
    AcquisitionRepository,
    acquisition_analysis_context,
    receipt_from_row,
)
from pring_cycle.catalog import metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS, require_registered_manifest
from pring_cycle.source_contract_review import (
    require_registered_source_contract,
    require_source_contract,
)
from pring_cycle.storage import database_connection


class AsOfMode(StrEnum):
    PUBLIC = "public_as_of"
    SYSTEM = "system_as_of"


def publication_times(
    published_at: date | datetime | None, source_timezone: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Convert a source parser's reliable time; this does not authenticate evidence."""
    if published_at is None:
        return None, None
    if isinstance(published_at, datetime):
        if published_at.tzinfo is None:
            raise ValueError("publication_timezone_required")
        released = published_at.astimezone(UTC)
        return released, released
    public_at = datetime.combine(
        published_at + timedelta(days=1), time.min, source_timezone
    ).astimezone(UTC)
    return None, public_at


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
    acquisition_id: str | None = None
    acquisition_ids: tuple[str, ...] = ()


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
    acquisitions: tuple[AcquisitionReceipt, ...] = ()
    acquisition_status: str = "untraced"


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
    fetched_at: datetime


@dataclass(frozen=True)
class SourceClaimVintage:
    claim_id: str
    period_start: str
    period_end: str
    dimensions: dict[str, str]
    public_available_at: datetime | None
    certification_status: str
    quality_status: str


@dataclass(frozen=True)
class SourceClaimAcquisition:
    receipt: AcquisitionReceipt
    raw: bytes
    normalized: bytes


@dataclass
class _PreloadedSeriesState:
    visible_count: int
    rows_by_observation: dict[str, list[sqlite3.Row]]
    points_by_observation: dict[str, MetricSeriesPoint]
    tolerance: float | None = None


class EvidenceRepository:
    def _validate_core_originals(self, claims: tuple[SourceClaimInput, ...]) -> None:
        from pring_cycle.commodity_basket import require_commodity_results
        from pring_cycle.source_adapters import CORE_API_IDENTITIES, parse_core_acquisition

        require_commodity_results(self._database_path, claims)
        originals: dict[tuple[str, str], dict[str, float]] = {}
        acquisitions = AcquisitionRepository(
            self._database_path, self._database_path.parent / "artifacts" / "sha256"
        )
        for claim in claims:
            if (
                claim.metric_id not in CORE_API_IDENTITIES
                or claim.definition_version in BUILTIN_CATALOG_VERSIONS
                or claim.certification_status != "certified"
            ):
                continue
            identities = set(claim.acquisition_ids)
            if claim.acquisition_id is not None:
                identities.add(claim.acquisition_id)
            if not identities:
                raise ValueError("registered_core_source_original_required")
            for identity in identities:
                key = (claim.metric_id, identity)
                if key not in originals:
                    try:
                        receipt = acquisitions.get(identity)
                        raw = acquisitions.read_content(identity, "raw")
                        acquisitions.read_content(identity, "normalized")
                        bars = parse_core_acquisition(receipt, raw, metric_id=claim.metric_id)
                    except (LookupError, OSError, TypeError, ValueError) as error:
                        raise ValueError("registered_core_source_original_mismatch") from error
                    originals[key] = {bar.business_date.isoformat(): bar.close for bar in bars}
                if (
                    claim.period_end not in originals[key]
                    or originals[key][claim.period_end] != claim.value
                ):
                    raise ValueError("registered_core_source_original_mismatch")

    def source_claim_originals(self, claim_id: str) -> tuple[tuple[AcquisitionReceipt, bytes], ...]:
        """Return hash-checked originals attached to this exact immutable claim."""
        return self.source_claim_originals_many((claim_id,))[claim_id]

    def source_claim_originals_many(
        self, claim_ids: tuple[str, ...]
    ) -> dict[str, tuple[tuple[AcquisitionReceipt, bytes], ...]]:
        """Preserve the original-reading interface with both artifacts checked."""
        return {
            claim_id: tuple((item.receipt, item.raw) for item in items)
            for claim_id, items in self.source_claim_acquisitions_many(claim_ids).items()
        }

    def source_claim_acquisitions_many(
        self, claim_ids: tuple[str, ...]
    ) -> dict[str, tuple[SourceClaimAcquisition, ...]]:
        """Read each physical receipt once in this batch, preserving exact claim links."""
        identities = tuple(dict.fromkeys(claim_ids))
        rows = []
        with self._connect() as connection:
            for offset in range(0, len(identities), 500):
                batch = identities[offset : offset + 500]
                placeholders = ",".join("?" for _ in batch)
                rows.extend(
                    connection.execute(
                        f"""SELECT link.claim_id, request.* FROM source_claim_acquisition AS link
                            JOIN acquisition_request AS request USING(acquisition_id)
                            WHERE link.claim_id IN ({placeholders})
                            ORDER BY link.claim_id, request.started_at, request.acquisition_id""",
                        batch,
                    ).fetchall()
                )
        acquisitions = AcquisitionRepository(
            self._database_path, self._database_path.parent / "artifacts" / "sha256"
        )
        checked: dict[str, SourceClaimAcquisition | None] = {}
        content_by_hash: dict[str, bytes] = {}
        originals: dict[str, list[SourceClaimAcquisition]] = {
            claim_id: [] for claim_id in identities
        }
        invalid: set[str] = set()
        for row in rows:
            acquisition_id = row["acquisition_id"]
            if acquisition_id not in checked:
                checked[acquisition_id] = None
                if row["state"] == "validated":
                    try:
                        raw = acquisitions.read_content(acquisition_id, "raw")
                        normalized = acquisitions.read_content(acquisition_id, "normalized")
                        # Keep each receipt's validation, but share identical immutable payloads
                        # for the lifetime of this batch (including across different claims).
                        raw = content_by_hash.setdefault(row["raw_hash"], raw)
                        normalized = content_by_hash.setdefault(row["normalized_hash"], normalized)
                        checked[acquisition_id] = SourceClaimAcquisition(
                            receipt_from_row(row), raw, normalized
                        )
                    except (LookupError, ValueError, OSError):
                        pass
            original = checked[acquisition_id]
            if original is None:
                invalid.add(row["claim_id"])
            else:
                originals[row["claim_id"]].append(original)
        return {
            claim_id: () if claim_id in invalid else tuple(items)
            for claim_id, items in originals.items()
        }

    def source_claim_publication(self, claim_id: str) -> dict[str, Any] | None:
        """Read the complete validated publication linked to this exact claim version."""
        from pring_cycle.official_context import parse_official_context_document

        with self._connect() as connection:
            rows = connection.execute(
                """SELECT request.*, claim.source_reference, claim.provider AS claim_provider
                   FROM source_claim AS claim
                   JOIN source_claim_acquisition AS link USING(claim_id)
                   JOIN acquisition_request AS request USING(acquisition_id)
                   WHERE claim.claim_id=? AND request.state='validated'""",
                (claim_id,),
            ).fetchall()
        # RuntimePaths keeps the CAS beside the database in the same data directory.
        acquisitions = AcquisitionRepository(
            self._database_path, self._database_path.parent / "artifacts" / "sha256"
        )
        publications = []
        for row in rows:
            if row["parser_version"] != "official-context-parser-v0004":
                continue
            try:
                raw = acquisitions.read_content(row["acquisition_id"], "raw")
                document = json.loads(
                    acquisitions.read_content(row["acquisition_id"], "normalized")
                )
                parameters = json.loads(row["parameters_json"])
                if row["api_name"] not in {"document_import", "official_http_get"}:
                    continue
                parsed = parse_official_context_document(
                    raw,
                    family=parameters["family"],
                    source_url=parameters["source_url"],
                    expected_period=parameters["period"],
                    fetched_at=_required_datetime(row["received_at"]),
                )
                if document != json.loads(json.dumps(asdict(parsed), default=str)):
                    continue
            except (LookupError, ValueError, TypeError, OSError):
                continue
            if (
                isinstance(document, dict)
                and document.get("provider") == row["claim_provider"] == row["provider"]
                and f"{document.get('source_url')}#sha256={row['raw_hash']}"
                == row["source_reference"]
                and document not in publications
            ):
                publications.append(document)
        return publications[0] if len(publications) == 1 else None

    def validate_model_catalog(self, manifest: Mapping[str, object]) -> None:
        require_registered_manifest(self._database_path, manifest)

    def source_claims_matching_registered_contract(
        self, claim_ids: tuple[str, ...], *, definition_version: str
    ) -> set[str]:
        """Recheck stored claim identities and their admitted source contracts."""
        if not claim_ids:
            return set()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM source_claim WHERE claim_id IN (SELECT value FROM json_each(?))",
                (json.dumps(claim_ids),),
            ).fetchall()
            links = connection.execute(
                "SELECT claim_id, acquisition_id FROM source_claim_acquisition "
                "WHERE claim_id IN (SELECT value FROM json_each(?))",
                (json.dumps(claim_ids),),
            ).fetchall()
        acquisitions: dict[str, list[str]] = {}
        for link in links:
            acquisitions.setdefault(str(link[0]), []).append(str(link[1]))
        valid = set()
        for row in rows:
            if (
                row["definition_version"] != definition_version
                or row["certification_status"] != "certified"
                or row["quality_status"] != "validated"
            ):
                continue
            try:
                claim = SourceClaimInput(
                    metric_id=str(row["metric_id"]),
                    definition_version=definition_version,
                    period_kind=str(row["period_kind"]),
                    period_start=str(row["period_start"]),
                    period_end=str(row["period_end"]),
                    dimensions=json.loads(row["dimensions_json"]),
                    value=row["value"],
                    value_state=EvidenceValueState(row["value_state"]),
                    unit=str(row["unit"]),
                    provider=str(row["provider"]),
                    source_reference=str(row["source_reference"]),
                    release_event_id=str(row["release_event_id"]),
                    release_at=_datetime(row["release_at"]),
                    public_available_at=_datetime(row["public_available_at"]),
                    fetched_at=_required_datetime(row["fetched_at"]),
                    available_at=_required_datetime(row["available_at"]),
                    certification_status=str(row["certification_status"]),
                    quality_status=str(row["quality_status"]),
                    acquisition_ids=tuple(acquisitions.get(str(row["claim_id"]), ())),
                )
                _validate_claim(claim, self._database_path)
            except (OSError, LookupError, TypeError, ValueError):
                continue
            valid.add(str(row["claim_id"]))
        return valid

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._preloaded_series_rows: dict[
            tuple[str, str, AsOfMode],
            tuple[tuple[float, ...], tuple[sqlite3.Row, ...]],
        ] = {}
        self._preloaded_series_states: dict[
            tuple[str, str, AsOfMode],
            _PreloadedSeriesState,
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
        *,
        availability_clock: Callable[[], datetime] | None = None,
    ) -> tuple[StoredSourceClaim, ...]:
        if not claims:
            raise ValueError("evidence_claim_batch_required")
        for claim in claims:
            _validate_claim(claim, self._database_path)
            if claim.certification_status == "certified":
                require_source_contract(claim.definition_version, metric_id=claim.metric_id)
        self._validate_core_originals(claims)
        if availability_clock is not None:
            available_at = availability_clock()
            if available_at.tzinfo is None or any(
                not (claim.acquisition_id or claim.acquisition_ids)
                or available_at < claim.available_at
                for claim in claims
            ):
                raise ValueError("acquisition_availability_time_invalid")
            claims = tuple(replace(claim, available_at=available_at) for claim in claims)
        stored: list[StoredSourceClaim] = []
        with self._connect() as connection:
            for claim in claims:
                item = _append_source_claim(connection, claim)
                acquisition_ids = tuple(
                    dict.fromkeys(
                        (
                            *claim.acquisition_ids,
                            *((claim.acquisition_id,) if claim.acquisition_id else ()),
                        )
                    )
                )
                receipts = [
                    connection.execute(
                        "SELECT * FROM acquisition_request WHERE acquisition_id=?",
                        (acquisition_id,),
                    ).fetchone()
                    for acquisition_id in acquisition_ids
                ]
                if receipts and (
                    any(receipt is None or receipt["state"] != "validated" for receipt in receipts)
                    or claim.available_at
                    < max(_required_datetime(r["validated_at"]) for r in receipts)
                    or claim.fetched_at
                    != max(_required_datetime(r["received_at"]) for r in receipts)
                ):
                    raise ValueError("claim_acquisition_not_validated")
                for acquisition_id in acquisition_ids:
                    connection.execute(
                        "INSERT OR IGNORE INTO source_claim_acquisition VALUES (?, ?)",
                        (item.claim_id, acquisition_id),
                    )
                stored.append(item)
        self._preloaded_series_rows.clear()
        self._preloaded_series_states.clear()
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
        grouped: dict[tuple[str, str], list[sqlite3.Row]] = {pair: [] for pair in ordered}
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
                    _required_datetime(row[time_column]).timestamp() for row in visible_rows
                )
                self._preloaded_series_rows[(*pair, mode)] = (
                    timestamps,
                    tuple(visible_rows),
                )
                self._preloaded_series_states[(*pair, mode)] = _PreloadedSeriesState(
                    visible_count=0,
                    rows_by_observation={},
                    points_by_observation={},
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
                       public_available_at, fetched_at
                FROM source_claim
                WHERE {" AND ".join(clauses)}
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
                str(row["supersedes_claim_id"]) if row["supersedes_claim_id"] is not None else None
            ),
            value=float(row["value"]) if row["value"] is not None else None,
            value_state=EvidenceValueState(str(row["value_state"])),
            unit=str(row["unit"]),
            release_event_id=str(row["release_event_id"]),
            release_at=_datetime(row["release_at"]),
            public_available_at=_datetime(row["public_available_at"]),
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
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
                SELECT claim_id, period_start, period_end, dimensions_json,
                       public_available_at,
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
                dimensions={
                    str(key): str(value)
                    for key, value in json.loads(str(row["dimensions_json"])).items()
                },
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
        definition_clause = " AND definition_version=?" if definition_version is not None else ""
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
        period: str | None,
        as_of: datetime,
        definition_version: str | None = None,
        target_business_date: str | None = None,
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
        rows.sort(
            key=lambda row: (
                _required_datetime(row["fetched_at"]),
                str(row["retrieval_attempt_id"]),
            ),
            reverse=True,
        )
        for row in rows:
            if _required_datetime(row["fetched_at"]) > as_of:
                continue
            metadata = {
                str(key): str(value)
                for key, value in json.loads(str(row["safe_metadata_json"])).items()
            }
            if period is not None and metadata.get("period") != period:
                continue
            if (
                target_business_date is not None
                and metadata.get("target_business_date") != target_business_date
            ):
                continue
            if (
                definition_version is not None
                and metadata.get("definition_version") != definition_version
            ):
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
        public_as_of: datetime | None = None,
        tolerance: float = 0.0,
        definition_version: str | None = None,
    ) -> tuple[MetricSeriesPoint, ...]:
        if as_of.tzinfo is None:
            raise ValueError("as_of_must_be_timezone_aware")
        if public_as_of is not None and public_as_of.tzinfo is None:
            raise ValueError("public_as_of_must_be_timezone_aware")
        definition_clause = " AND definition_version=?" if definition_version is not None else ""
        time_column = {
            AsOfMode.PUBLIC: "public_available_at",
            AsOfMode.SYSTEM: "available_at",
        }[mode]
        public_clause = (
            " AND public_available_at IS NOT NULL"
            " AND julianday(public_available_at) <= julianday(?)"
            if public_as_of is not None
            else ""
        )
        parameters: tuple[object, ...] = (
            (metric_id, definition_version, _iso(as_of))
            if definition_version is not None
            else (metric_id, _iso(as_of))
        )
        if public_as_of is not None:
            parameters += (_iso(public_as_of),)
        cache_key = (
            (metric_id, definition_version, mode)
            if definition_version is not None and public_as_of is None
            else None
        )
        preloaded = self._preloaded_series_rows.get(cache_key) if cache_key is not None else None
        if preloaded is not None:
            assert cache_key is not None
            timestamps, cached_rows = preloaded
            visible_count = bisect_right(timestamps, as_of.timestamp())
            state = self._preloaded_series_states[cache_key]
            if visible_count < state.visible_count:
                state.visible_count = 0
                state.rows_by_observation.clear()
                state.points_by_observation.clear()
                state.tolerance = None
            changed_observations: set[str] = (
                set(state.rows_by_observation) if state.tolerance != tolerance else set()
            )
            for row in cached_rows[state.visible_count : visible_count]:
                observation_id = str(row["observation_id"])
                state.rows_by_observation.setdefault(observation_id, []).append(row)
                changed_observations.add(observation_id)
            for observation_id in changed_observations:
                observation_rows = state.rows_by_observation[observation_id]
                result = _select_claim_rows(
                    observation_id,
                    observation_rows,
                    mode=mode,
                    as_of=as_of,
                    tolerance=tolerance,
                )
                row = observation_rows[0]
                state.points_by_observation[observation_id] = MetricSeriesPoint(
                    observation_id=result.observation_id,
                    period_start=str(row["period_start"]),
                    period_end=str(row["period_end"]),
                    dimensions={
                        str(key): str(value)
                        for key, value in json.loads(str(row["dimensions_json"])).items()
                    },
                    selected_value=result.selected_value,
                    value_state=result.value_state,
                    selection_status=result.selection_status,
                    selected_claim_id=result.selected_claim_id,
                    claims=result.claims,
                )
            state.visible_count = visible_count
            state.tolerance = tolerance
            points = list(state.points_by_observation.values())
        else:
            with self._connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT * FROM source_claim
                    WHERE metric_id=?{definition_clause}
                      AND {time_column} IS NOT NULL
                      AND julianday({time_column}) <= julianday(?)
                      {public_clause}
                    ORDER BY period_end, observation_id, julianday({time_column}),
                             julianday(available_at), claim_id
                    """,
                    parameters,
                ).fetchall()
            rows_by_observation: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                if public_as_of is not None and (
                    row["public_available_at"] is None
                    or _required_datetime(row["public_available_at"]) > public_as_of
                ):
                    continue
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
                            for key, value in json.loads(str(row["dimensions_json"])).items()
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
        with self._connect() as connection:
            visible_ids = tuple(claim.claim_id for claim in queried.claims)
            schema_present = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='acquisition_request'"
            ).fetchone()
            receipts = []
            links = []
            if schema_present is not None:
                receipts = connection.execute(
                    """SELECT DISTINCT request.* FROM acquisition_request AS request
                       JOIN source_claim_acquisition AS link USING(acquisition_id)
                       WHERE link.claim_id IN (SELECT value FROM json_each(?))
                       ORDER BY request.started_at, request.acquisition_id""",
                    (json.dumps(visible_ids),),
                ).fetchall()
                links = connection.execute(
                    """SELECT claim_id FROM source_claim_acquisition
                       WHERE claim_id IN (SELECT value FROM json_each(?))
                       """,
                    (json.dumps(visible_ids),),
                ).fetchall()
        if not visible_ids:
            acquisition_status = "not_visible"
        elif not links:
            acquisition_status = "untraced"
        elif set(visible_ids) <= {str(link["claim_id"]) for link in links}:
            acquisition_status = "linked"
        else:
            acquisition_status = "partially_linked"
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
            acquisitions=tuple(receipt_from_row(receipt) for receipt in receipts),
            acquisition_status=acquisition_status,
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
                str(item) for item in json.loads(str(row["input_observation_version_ids_json"]))
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
        acquisition_ids: tuple[str, ...] = (),
    ) -> str:
        if fetched_at.tzinfo is None:
            raise ValueError("retrieval_attempt_time_must_be_timezone_aware")
        metadata = dict(safe_metadata)
        context = acquisition_analysis_context(self._database_path, acquisition_ids)
        if any(key in metadata and metadata[key] != value for key, value in context.items()):
            raise ValueError("retrieval_attempt_acquisition_context_mismatch")
        metadata.update(context)
        if acquisition_ids:
            metadata["acquisition_ids"] = ",".join(sorted(set(acquisition_ids)))
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
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
            connection.executescript(_EVIDENCE_INDEX_EXTENSIONS_SCHEMA)
            connection.executescript(ACQUISITION_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection


def _select_claim_rows(
    observation_id: str,
    rows: list[sqlite3.Row],
    *,
    mode: AsOfMode,
    as_of: datetime,
    tolerance: float,
) -> EvidenceQueryResult:
    time_column = "public_available_at" if mode == AsOfMode.PUBLIC else "available_at"
    # SQLite julianday is only a coarse index filter: it rounds sub-millisecond
    # timestamps. Preserve the exact cutoff and revision order here.
    rows = sorted(
        (row for row in rows if _required_datetime(row[time_column]) <= as_of),
        key=lambda row: (
            _required_datetime(row[time_column]),
            _required_datetime(row["available_at"]),
            str(row["claim_id"]),
        ),
    )
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
        if item.certification_status == "certified"
        and item.quality_status == "validated"
        and item.value_state is EvidenceValueState.REPORTED_VALUE
        and item.value is not None
    ]
    conflicted = bool(reported_values) and (max(reported_values) - min(reported_values) > tolerance)
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


def _validate_claim(claim: SourceClaimInput, database_path: Path) -> None:
    definition = metric_definition(
        claim.metric_id,
        definition_version=claim.definition_version,
        database_path=database_path,
    )
    if claim.definition_version != definition.definition_version:
        raise ValueError("evidence_definition_version_mismatch")
    allowed_units = definition.allowed_units or (definition.unit,)
    if claim.unit not in allowed_units:
        raise ValueError("evidence_unit_mismatch")
    if set(claim.dimensions) != set(definition.dimensions):
        raise ValueError("evidence_dimensions_mismatch")
    if claim.certification_status == "certified" and definition.certification_status != "certified":
        raise ValueError("evidence_source_not_certified_by_model")
    if claim.certification_status == "certified":
        require_registered_source_contract(
            definition,
            provider=claim.provider,
            source_reference=claim.source_reference,
            period_kind=claim.period_kind,
            dimensions=claim.dimensions,
            unit=claim.unit,
            period_start=claim.period_start,
            period_end=claim.period_end,
            database_path=database_path,
            value=claim.value,
            release_at=claim.release_at,
            public_available_at=claim.public_available_at,
            acquisition_ids=tuple(
                dict.fromkeys(
                    (
                        *claim.acquisition_ids,
                        *((claim.acquisition_id,) if claim.acquisition_id else ()),
                    )
                )
            ),
        )
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
        supersedes = str(existing_claim[0]) if existing_claim[0] is not None else None
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

_EVIDENCE_INDEX_EXTENSIONS_SCHEMA = """
CREATE INDEX IF NOT EXISTS ix_source_claim_provider_identity
ON source_claim(
    metric_id, period_kind, period_start, period_end, dimensions_json, provider,
    definition_version, source_reference, available_at
);
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
