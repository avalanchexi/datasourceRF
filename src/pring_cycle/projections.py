from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pring_cycle.batches import add_batch_columns, current_batch_id
from pring_cycle.confirmation import DIMENSIONS as CONFIRMATION_DIMENSIONS
from pring_cycle.confirmation import OUTPUT_STRUCTURE as CONFIRMATION_STRUCTURE
from pring_cycle.confirmation import RELATIONS as CONFIRMATION_RELATIONS
from pring_cycle.metric_contracts import EFFECTIVE_UNTIL_CHANGED_METRICS
from pring_cycle.source_contract_review import require_stored_model_source_contract
from pring_cycle.storage import database_connection, ensure_wal

ANALYTICAL_DATASETS = (
    "cycle_overview",
    "core_assets",
    "macro",
    "inventory",
    "release_calendar",
    "stage_history",
)
INVENTORY_CARD_NAMES = (
    "orders_inventory_gap",
    "materials_finished_goods",
    "physical_inventory",
    "inventory_sales_turnover",
    "prices_profits",
    "capacity",
    "credit_physical_inventory",
)
_FORMAL_STAGE_BY_STATES = {
    ("bull", "bear", "bear"): "stage_i",
    ("bull", "bull", "bear"): "stage_ii",
    ("bull", "bull", "bull"): "stage_iii",
    ("bear", "bull", "bull"): "stage_iv",
    ("bear", "bear", "bull"): "stage_v",
    ("bear", "bear", "bear"): "stage_vi",
}


@dataclass(frozen=True)
class ProjectionEnvelope:
    projection_set_id: str
    system_as_of: datetime
    target_business_date: str
    evidence_snapshot_id: str
    model_version_id: str
    trend_rule_version: str
    evidence_window_start: str
    evidence_window_end: str
    generated_at: datetime
    completeness: str
    refresh_status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProjectionSet:
    envelope: ProjectionEnvelope
    datasets: dict[str, dict[str, object]]


class ProjectionSetRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ProjectionSetRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_PROJECTION_SCHEMA)
            connection.executescript(_P0_ASSESSMENT_SCHEMA)
            add_batch_columns(connection)
        return repository

    def publish(
        self,
        envelope: ProjectionEnvelope,
        datasets: dict[str, dict[str, object]],
        *,
        fail_before_pointer: bool = False,
        p0_assessment: dict[str, object] | None = None,
        as_current: bool = True,
    ) -> None:
        """Store the set; ``as_current`` lets it take the current pointer, never back in time.

        A backfilled day's set is kept as history only: the page stays on the last whole
        set until the run publishes its target (ADR-0008). A set already stored under its id
        is not written again; with ``as_current`` it may still take the pointer.
        """
        _validate_projection(envelope, datasets)
        envelope_json = _canonical_json(_envelope_document(envelope))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            require_stored_model_source_contract(connection, envelope.model_version_id)
            stored = connection.execute(
                "SELECT 1 FROM projection_set WHERE projection_set_id=?",
                (envelope.projection_set_id,),
            ).fetchone()
            if stored is None:
                self._insert_set(connection, envelope, envelope_json, datasets)
            if fail_before_pointer:
                connection.rollback()
                raise RuntimeError("injected_projection_failure")
            if p0_assessment is not None:
                self._insert_p0_assessment(connection, p0_assessment)
            if as_current:
                self._take_current(connection, envelope)

    def _insert_set(
        self,
        connection: sqlite3.Connection,
        envelope: ProjectionEnvelope,
        envelope_json: str,
        datasets: dict[str, dict[str, object]],
    ) -> None:
        connection.execute(
            "INSERT INTO projection_set(projection_set_id, envelope_json, batch_id) "
            "VALUES (?, ?, ?)",
            (envelope.projection_set_id, envelope_json, current_batch_id()),
        )
        for dataset_name in ANALYTICAL_DATASETS:
            connection.execute(
                """
                INSERT INTO analytical_dataset(
                    projection_set_id, dataset_name, document_json, batch_id
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    envelope.projection_set_id,
                    dataset_name,
                    _canonical_json(datasets[dataset_name]),
                    current_batch_id(),
                ),
            )

    def _take_current(self, connection: sqlite3.Connection, envelope: ProjectionEnvelope) -> None:
        current_row = connection.execute(
            """
            SELECT projection_set.envelope_json
            FROM current_projection
            JOIN projection_set USING (projection_set_id)
            WHERE current_projection.singleton=1
            """
        ).fetchone()
        current_target = None
        if current_row is not None:
            current_document = json.loads(str(current_row["envelope_json"]))
            current_target = str(current_document["target_business_date"])
        if current_target is None or envelope.target_business_date >= current_target:
            connection.execute(
                """
                INSERT INTO current_projection(singleton, projection_set_id, batch_id)
                VALUES (1, ?, ?)
                ON CONFLICT(singleton) DO UPDATE
                SET projection_set_id=excluded.projection_set_id, batch_id=excluded.batch_id
                """,
                (envelope.projection_set_id, current_batch_id()),
            )

    def prepare_p0_assessment(self, document: dict[str, object]) -> dict[str, object]:
        normalized = _canonical_json(document)
        assessment_id = "p0-assessment-" + hashlib.sha256(normalized.encode()).hexdigest()[:20]
        return {"assessment_id": assessment_id, **document}

    def record_p0_assessment(self, assessment: dict[str, object]) -> str:
        with self._connect() as connection:
            self._insert_p0_assessment(connection, assessment)
        return str(assessment["assessment_id"])

    def p0_assessment(self, assessment_id: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM p0_assessment WHERE assessment_id=?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            raise LookupError("p0_assessment_not_found")
        value = json.loads(str(row["document_json"]))
        if not isinstance(value, dict):
            raise ValueError("p0_assessment_document_invalid")
        return {str(key): item for key, item in value.items()}

    def stage_history(self, *, through: str | None = None) -> tuple[dict[str, object], ...]:
        """Every assessment in day order; ``through`` keeps those dated on or before it."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM p0_assessment
                WHERE ? IS NULL OR target_business_date <= ?
                ORDER BY target_business_date, julianday(system_as_of), assessment_id
                """,
                (through, through),
            ).fetchall()
        return tuple(
            {str(key): value for key, value in json.loads(str(row["document_json"])).items()}
            for row in rows
        )

    def summarized_dates(self) -> frozenset[str]:
        """Target days that already have a summary (a P0 assessment)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT target_business_date FROM p0_assessment"
            ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def last_confirmed_stage(self, *, on_or_before: str) -> str | None:
        date.fromisoformat(on_or_before)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT document_json FROM p0_assessment
                WHERE event_kind='formal' AND target_business_date <= ?
                ORDER BY target_business_date DESC, julianday(system_as_of) DESC,
                         assessment_id DESC
                LIMIT 1
                """,
                (on_or_before,),
            ).fetchone()
        if row is None:
            return None
        document = json.loads(str(row["document_json"]))
        value = document.get("current_stage")
        return str(value) if value is not None else None

    def create_gap_notice(
        self,
        assessment_id: str,
        *,
        client_request_id: str,
    ) -> dict[str, object]:
        if not client_request_id:
            raise ValueError("gap_notice_request_id_required")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT document_json FROM data_gap_notice WHERE client_request_id=?",
                (client_request_id,),
            ).fetchone()
            if existing is not None:
                value = json.loads(str(existing["document_json"]))
                return {str(key): item for key, item in value.items()}
        assessment = self.p0_assessment(assessment_id)
        if assessment.get("event_kind") != "gap" or assessment.get("current_stage") is not None:
            raise ValueError("gap_notice_requires_p0_gap_assessment")
        notice_id = (
            "gap-notice-"
            + hashlib.sha256(f"{assessment_id}:{client_request_id}".encode()).hexdigest()[:20]
        )
        document: dict[str, object] = {
            "ai_calls": 0,
            "assessment_id": assessment_id,
            "client_request_id": client_request_id,
            "current_stage": None,
            "gaps": assessment.get("gaps", []),
            "last_confirmed_stage": assessment.get("last_confirmed_stage"),
            "model_version_id": assessment.get("model_version_id"),
            "notice_id": notice_id,
            "notice_type": "data_gap_notice",
            "statement": "目标交易日核心数据未通过 P0 门禁，未发布新的正式阶段。",
            "status": "completed",
            "system_as_of": assessment.get("system_as_of"),
            "target_business_date": assessment.get("business_date"),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO data_gap_notice(
                    notice_id, assessment_id, client_request_id, document_json, created_at,
                    batch_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    notice_id,
                    assessment_id,
                    client_request_id,
                    _canonical_json(document),
                    datetime.now(UTC).isoformat(),
                    current_batch_id(),
                ),
            )
        return document

    def gap_notices(self) -> tuple[dict[str, object], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT document_json FROM data_gap_notice ORDER BY notice_id DESC"
            ).fetchall()
        return tuple(
            {str(key): value for key, value in json.loads(str(row["document_json"])).items()}
            for row in rows
        )

    def _insert_p0_assessment(
        self,
        connection: sqlite3.Connection,
        assessment: dict[str, object],
    ) -> None:
        required = {
            "assessment_id",
            "business_date",
            "system_as_of",
            "event_kind",
        }
        if not required <= set(assessment):
            raise ValueError("p0_assessment_identity_incomplete")
        connection.execute(
            """
            INSERT OR IGNORE INTO p0_assessment(
                assessment_id, target_business_date, system_as_of,
                event_kind, projection_set_id, document_json, batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(assessment["assessment_id"]),
                str(assessment["business_date"]),
                str(assessment["system_as_of"]),
                str(assessment["event_kind"]),
                (
                    str(assessment["projection_set_id"])
                    if assessment.get("projection_set_id") is not None
                    else None
                ),
                _canonical_json(assessment),
                current_batch_id(),
            ),
        )

    def current(self) -> ProjectionSet:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT projection_set.projection_set_id
                FROM current_projection
                JOIN projection_set USING (projection_set_id)
                WHERE singleton = 1
                """
            ).fetchone()
            if row is None:
                raise LookupError("current_projection_unavailable")
        return self.get(str(row["projection_set_id"]))

    def get(self, projection_set_id: str) -> ProjectionSet:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT projection_set_id, envelope_json FROM projection_set
                WHERE projection_set_id = ?
                """,
                (projection_set_id,),
            ).fetchone()
            if row is None:
                raise LookupError("projection_set_not_found")
            dataset_rows = connection.execute(
                """
                SELECT dataset_name, document_json FROM analytical_dataset
                WHERE projection_set_id = ?
                """,
                (projection_set_id,),
            ).fetchall()
        document = json.loads(str(row["envelope_json"]))
        envelope = ProjectionEnvelope(
            projection_set_id=str(document["projection_set_id"]),
            system_as_of=datetime.fromisoformat(str(document["system_as_of"])),
            target_business_date=str(document["target_business_date"]),
            evidence_snapshot_id=str(document["evidence_snapshot_id"]),
            model_version_id=str(document["model_version_id"]),
            trend_rule_version=str(document["trend_rule_version"]),
            evidence_window_start=str(document["evidence_window_start"]),
            evidence_window_end=str(document["evidence_window_end"]),
            generated_at=datetime.fromisoformat(str(document["generated_at"])),
            completeness=str(document["completeness"]),
            refresh_status=str(document["refresh_status"]),
            warnings=tuple(str(item) for item in document["warnings"]),
        )
        return ProjectionSet(
            envelope,
            {
                str(item["dataset_name"]): json.loads(str(item["document_json"]))
                for item in dataset_rows
            },
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            ensure_wal(connection, self._database_path)
            yield connection


def _validate_projection(
    envelope: ProjectionEnvelope, datasets: dict[str, dict[str, object]]
) -> None:
    if set(datasets) != set(ANALYTICAL_DATASETS):
        raise ValueError("projection_dataset_manifest_incomplete")
    if any(
        document.get("projection_set_id") != envelope.projection_set_id
        for document in datasets.values()
    ):
        raise ValueError("projection_dataset_identity_mismatch")


def validate_analytical_projection(
    envelope: ProjectionEnvelope,
    datasets: dict[str, dict[str, object]],
) -> None:
    _validate_projection(envelope, datasets)
    if envelope.system_as_of.tzinfo is None or envelope.generated_at.tzinfo is None:
        raise ValueError("projection_envelope_times_must_be_timezone_aware")
    if envelope.evidence_window_end != envelope.target_business_date:
        raise ValueError("projection_evidence_window_target_mismatch")
    if envelope.completeness not in {"complete", "degraded"}:
        raise ValueError("projection_completeness_invalid")
    if bool(envelope.warnings) != (envelope.completeness == "degraded"):
        raise ValueError("projection_completeness_warning_mismatch")
    overview = datasets["cycle_overview"]
    core = datasets["core_assets"]
    macro = datasets["macro"]
    inventory = datasets["inventory"]
    assets = core.get("assets")
    overview_assets = overview.get("core_assets")
    if not isinstance(assets, list) or overview_assets != assets:
        raise ValueError("projection_core_asset_reference_mismatch")
    by_asset = {
        str(item.get("asset")): item
        for item in assets
        if isinstance(item, dict) and item.get("asset") is not None
    }
    if set(by_asset) != {"bond", "stock", "commodity"}:
        raise ValueError("projection_core_asset_manifest_invalid")
    states = (
        str(by_asset["bond"].get("state")),
        str(by_asset["stock"].get("state")),
        str(by_asset["commodity"].get("state")),
    )
    if overview.get("stage_reason") == "core_data_pending":
        # A held stage publishes the rest of the run; it may not claim a formal stage.
        if overview.get("current_stage") is not None:
            raise ValueError("projection_formal_stage_invariant_failed")
    else:
        if any(state not in {"bull", "bear"} for state in states):
            raise ValueError("projection_core_asset_state_invalid")
        expected_stage = _FORMAL_STAGE_BY_STATES.get(states)
        if overview.get("current_stage") != expected_stage:
            raise ValueError("projection_formal_stage_invariant_failed")
    if macro.get("score") is not None or inventory.get("score") is not None:
        raise ValueError("projection_context_score_forbidden")
    _validate_visible_context_window(
        (macro, inventory),
        window_start=envelope.evidence_window_start,
        window_end=envelope.evidence_window_end,
    )
    structure = macro.get("output_structure")
    if inventory.get("output_structure") != structure:
        raise ValueError("projection_output_structure_mismatch")
    if structure == CONFIRMATION_STRUCTURE:
        _validate_confirmation(macro, inventory, overview)
    elif structure is not None:
        raise ValueError("projection_output_structure_unknown")
    else:
        cards = inventory.get("cards")
        if (
            not isinstance(cards, list)
            or tuple(str(card.get("name")) for card in cards if isinstance(card, dict))
            != INVENTORY_CARD_NAMES
        ):
            raise ValueError("projection_inventory_card_manifest_invalid")
    release_events = datasets["release_calendar"].get("events")
    stage_events = datasets["stage_history"].get("events")
    if not isinstance(release_events, list) or not isinstance(stage_events, list):
        raise ValueError("projection_event_dataset_invalid")


_RETIRED_MACRO_LABELS = ("policy_direction", "credit_response", "overheat_state", "price_pressure")


def _validate_confirmation(
    macro: dict[str, object], inventory: dict[str, object], overview: dict[str, object]
) -> None:
    """A dimension summary of the published stage, with no label standing in (ADR-0037).

    It confirms the stage the set states, or none; each dimension's counts are its key
    indicators' relations, and a dimension not read yet has neither.
    """
    if any(label in macro for label in _RETIRED_MACRO_LABELS) or "cards" in inventory:
        raise ValueError("projection_confirmation_retired_label_present")
    confirmation = macro.get("confirmation")
    if not isinstance(confirmation, dict):
        raise ValueError("projection_confirmation_invalid")
    stage = overview.get("current_stage")
    if (
        confirmation.get("stage") != stage
        or confirmation.get("stage_reason") != overview.get("stage_reason")
        or confirmation.get("applicable") is not (stage is not None)
    ):
        raise ValueError("projection_confirmation_stage_mismatch")
    dimensions = confirmation.get("dimensions")
    if (
        not isinstance(dimensions, list)
        or not all(isinstance(item, dict) for item in dimensions)
        or [item.get("dimension") for item in dimensions] != list(CONFIRMATION_DIMENSIONS)
    ):
        raise ValueError("projection_confirmation_invalid")
    for dimension in dimensions:
        indicators = dimension.get("key_indicators")
        counts = dimension.get("counts")
        if not isinstance(indicators, list) or not all(
            isinstance(item, dict) for item in indicators
        ):
            raise ValueError("projection_confirmation_invalid")
        relations = [item.get("relation") for item in indicators]
        if dimension.get("status") == "not_connected":
            if indicators or counts is not None:
                raise ValueError("projection_confirmation_invalid")
            continue
        if (
            dimension.get("status") != "connected"
            or not indicators
            or any(relation not in CONFIRMATION_RELATIONS for relation in relations)
            or any((relation == "not_applicable") is (stage is not None) for relation in relations)
            or not isinstance(counts, dict)
            or set(counts) != set(CONFIRMATION_RELATIONS)
            or any(
                type(counts[relation]) is not int or counts[relation] != relations.count(relation)
                for relation in CONFIRMATION_RELATIONS
            )
        ):
            raise ValueError("projection_confirmation_invalid")


def _validate_visible_context_window(
    documents: tuple[dict[str, object], ...],
    *,
    window_start: str,
    window_end: str,
) -> None:
    try:
        visible_start = date.fromisoformat(window_start)
        visible_end = date.fromisoformat(window_end)
    except ValueError as error:
        raise ValueError("projection_context_visible_window_invalid") from error
    if visible_start > visible_end:
        raise ValueError("projection_context_visible_window_invalid")

    def walk(value: object) -> None:
        if isinstance(value, dict):
            period = value.get("period")
            if value.get("metric_id") is not None and period is not None:
                period_start = value.get("period_start", period)
                try:
                    evidence_start = date.fromisoformat(str(period_start))
                    evidence_end = date.fromisoformat(str(period))
                except ValueError as error:
                    raise ValueError(
                        "projection_context_evidence_outside_visible_window"
                    ) from error
                # A metric in force until changed is shown however old (ADR-0028).
                baseline = value["metric_id"] in EFFECTIVE_UNTIL_CHANGED_METRICS
                if (
                    not isinstance(period, str)
                    or not isinstance(period_start, str)
                    or evidence_start > evidence_end
                    or (evidence_end < visible_start and not baseline)
                    or evidence_start > visible_end
                ):
                    raise ValueError("projection_context_evidence_outside_visible_window")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for document in documents:
        walk(document)


def _envelope_document(envelope: ProjectionEnvelope) -> dict[str, object]:
    document = asdict(envelope)
    document["system_as_of"] = envelope.system_as_of.isoformat()
    document["generated_at"] = envelope.generated_at.isoformat()
    document["warnings"] = list(envelope.warnings)
    return document


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_PROJECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_set (
    projection_set_id TEXT PRIMARY KEY,
    envelope_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytical_dataset (
    projection_set_id TEXT NOT NULL REFERENCES projection_set(projection_set_id),
    dataset_name TEXT NOT NULL,
    document_json TEXT NOT NULL,
    PRIMARY KEY(projection_set_id, dataset_name)
);
CREATE TABLE IF NOT EXISTS current_projection (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    projection_set_id TEXT NOT NULL REFERENCES projection_set(projection_set_id)
);
CREATE TRIGGER IF NOT EXISTS projection_set_no_update
BEFORE UPDATE ON projection_set BEGIN SELECT RAISE(ABORT, 'projection_set_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS projection_set_no_delete
BEFORE DELETE ON projection_set BEGIN SELECT RAISE(ABORT, 'projection_set_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS analytical_dataset_no_update
BEFORE UPDATE ON analytical_dataset BEGIN
    SELECT RAISE(ABORT, 'analytical_dataset_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS analytical_dataset_no_delete
BEFORE DELETE ON analytical_dataset BEGIN
    SELECT RAISE(ABORT, 'analytical_dataset_is_immutable');
END;
"""

_P0_ASSESSMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS p0_assessment (
    assessment_id TEXT PRIMARY KEY,
    target_business_date TEXT NOT NULL,
    system_as_of TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK(event_kind IN ('formal', 'gap')),
    projection_set_id TEXT REFERENCES projection_set(projection_set_id),
    document_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS data_gap_notice (
    notice_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES p0_assessment(assessment_id),
    client_request_id TEXT NOT NULL UNIQUE,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS p0_assessment_no_update
BEFORE UPDATE ON p0_assessment BEGIN
    SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS p0_assessment_no_delete
BEFORE DELETE ON p0_assessment BEGIN
    SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS data_gap_notice_no_update
BEFORE UPDATE ON data_gap_notice BEGIN
    SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS data_gap_notice_no_delete
BEFORE DELETE ON data_gap_notice BEGIN
    SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
END;
"""
