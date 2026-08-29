from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
        return repository

    def publish(
        self,
        envelope: ProjectionEnvelope,
        datasets: dict[str, dict[str, object]],
        *,
        fail_before_pointer: bool = False,
        p0_assessment: dict[str, object] | None = None,
    ) -> None:
        _validate_projection(envelope, datasets)
        envelope_json = _canonical_json(_envelope_document(envelope))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO projection_set(projection_set_id, envelope_json) VALUES (?, ?)",
                (envelope.projection_set_id, envelope_json),
            )
            for dataset_name in ANALYTICAL_DATASETS:
                connection.execute(
                    """
                    INSERT INTO analytical_dataset(projection_set_id, dataset_name, document_json)
                    VALUES (?, ?, ?)
                    """,
                    (
                        envelope.projection_set_id,
                        dataset_name,
                        _canonical_json(datasets[dataset_name]),
                    ),
                )
            if fail_before_pointer:
                connection.rollback()
                raise RuntimeError("injected_projection_failure")
            if p0_assessment is not None:
                self._insert_p0_assessment(connection, p0_assessment)
            connection.execute(
                """
                INSERT INTO current_projection(singleton, projection_set_id) VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET projection_set_id=excluded.projection_set_id
                """,
                (envelope.projection_set_id,),
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

    def stage_history(self) -> tuple[dict[str, object], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_json FROM p0_assessment
                ORDER BY julianday(system_as_of), assessment_id
                """
            ).fetchall()
        return tuple(
            {str(key): value for key, value in json.loads(str(row["document_json"])).items()}
            for row in rows
        )

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
        notice_id = "gap-notice-" + hashlib.sha256(
            f"{assessment_id}:{client_request_id}".encode()
        ).hexdigest()[:20]
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
                    notice_id, assessment_id, client_request_id, document_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    notice_id,
                    assessment_id,
                    client_request_id,
                    _canonical_json(document),
                    datetime.now(UTC).isoformat(),
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
                event_kind, projection_set_id, document_json
            ) VALUES (?, ?, ?, ?, ?, ?)
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
            ),
        )

    def current(self) -> ProjectionSet:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT projection_set.projection_set_id, projection_set.envelope_json
                FROM current_projection
                JOIN projection_set USING (projection_set_id)
                WHERE singleton = 1
                """
            ).fetchone()
            if row is None:
                raise LookupError("current_projection_unavailable")
            dataset_rows = connection.execute(
                """
                SELECT dataset_name, document_json FROM analytical_dataset
                WHERE projection_set_id = ?
                """,
                (row["projection_set_id"],),
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


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
    if any(state not in {"bull", "bear"} for state in states):
        raise ValueError("projection_core_asset_state_invalid")
    expected_stage = _FORMAL_STAGE_BY_STATES.get(states)
    if overview.get("current_stage") != expected_stage:
        raise ValueError("projection_formal_stage_invariant_failed")
    if macro.get("score") is not None or inventory.get("score") is not None:
        raise ValueError("projection_context_score_forbidden")
    cards = inventory.get("cards")
    if not isinstance(cards, list) or tuple(
        str(card.get("name")) for card in cards if isinstance(card, dict)
    ) != INVENTORY_CARD_NAMES:
        raise ValueError("projection_inventory_card_manifest_invalid")
    release_events = datasets["release_calendar"].get("events")
    stage_events = datasets["stage_history"].get("events")
    if not isinstance(release_events, list) or not isinstance(stage_events, list):
        raise ValueError("projection_event_dataset_invalid")


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
