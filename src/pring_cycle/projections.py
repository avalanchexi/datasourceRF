from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
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
        return repository

    def publish(
        self,
        envelope: ProjectionEnvelope,
        datasets: dict[str, dict[str, object]],
        *,
        fail_before_pointer: bool = False,
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
            connection.execute(
                """
                INSERT INTO current_projection(singleton, projection_set_id) VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET projection_set_id=excluded.projection_set_id
                """,
                (envelope.projection_set_id,),
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
