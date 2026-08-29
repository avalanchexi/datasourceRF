from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog

CALIBRATION_BASELINE: dict[str, int] = {
    "asset_direction_changes": 21,
    "formal_stage_changes": 11,
    "fast_reversals_20d": 0,
    "median_confirmation_delay_days": 23,
}


@dataclass(frozen=True)
class ModelVersion:
    model_version_id: str
    manifest_hash: str
    status: str
    certified_replay_start: str


@dataclass(frozen=True)
class CalibrationAcceptance:
    model_version_id: str
    passed: bool
    asset_direction_changes: int
    formal_stage_changes: int
    fast_reversals_20d: int
    median_confirmation_delay_days: int
    result_hash: str


@dataclass(frozen=True)
class ReplayResult:
    replay_id: int
    model_version_id: str
    compared_with: str
    range_start: str
    range_end: str
    passed: bool
    stage_differences: int
    core_state_differences: int
    gaps: tuple[str, ...]


def certified_model_v0001_manifest() -> dict[str, Any]:
    return {
        "model_version_id": "model-v0001",
        "certified_replay_start": "2018-06-01",
        "trend_rules": {
            "rule_version": "trend-v0001",
            "window_days": 120,
            "slope_days": 20,
            "volatility_days": 20,
            "noise_multiplier": 1.5,
            "persistence_days": 8,
            "candidate_window_days": 30,
        },
        "stage_mapping": {
            "bull,bear,bear": "stage_i",
            "bull,bull,bear": "stage_ii",
            "bull,bull,bull": "stage_iii",
            "bear,bull,bull": "stage_iv",
            "bear,bear,bull": "stage_v",
            "bear,bear,bear": "stage_vi",
        },
        "core_metrics": {
            "bond": "CN_BOND_CORE_000012",
            "stock": "CN_EQUITY_CORE_000985",
            "commodity": "CN_COMMODITY_CORE_NHII",
        },
        "source_certifications": {
            "000012.SH": "certified",
            "000985.CSI": "certified",
            "NHII.NH": "certified_from_2018-06-01",
        },
        "selection_rule_version": "selection-v0001",
        "derived_formula_versions": {
            "credit_impulse": "credit-impulse-v0001",
            "order_inventory_spread": "order-inventory-v0001",
            "real_inventory_approximation": "inventory-ppi-v0001",
        },
        "metric_catalog_version": METRIC_CATALOG_VERSION,
        "metric_definitions": [asdict(item) for item in metric_catalog()],
    }


class ModelRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ModelRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_MODEL_SCHEMA)
        return repository

    def create_candidate(self, manifest: dict[str, Any]) -> ModelVersion:
        model_version_id = str(manifest.get("model_version_id", ""))
        certified_replay_start = str(manifest.get("certified_replay_start", ""))
        if not model_version_id or not certified_replay_start:
            raise ValueError("invalid_model_manifest")
        manifest_json = _canonical_json(manifest)
        manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["manifest_hash"]) != manifest_hash:
                    raise ValueError("model_version_is_immutable")
                return _model_version(existing)
            connection.execute(
                """
                INSERT INTO model_version(
                    model_version_id, manifest_hash, manifest_json, status,
                    certified_replay_start, created_at
                ) VALUES (?, ?, ?, 'candidate', ?, ?)
                """,
                (
                    model_version_id,
                    manifest_hash,
                    manifest_json,
                    certified_replay_start,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return ModelVersion(model_version_id, manifest_hash, "candidate", certified_replay_start)

    def record_acceptance(
        self, model_version_id: str, results: dict[str, int]
    ) -> CalibrationAcceptance:
        self.get(model_version_id)
        normalized = {key: int(results[key]) for key in CALIBRATION_BASELINE}
        passed = normalized == CALIBRATION_BASELINE
        result_json = _canonical_json(normalized)
        result_hash = hashlib.sha256(result_json.encode()).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO model_acceptance(
                    model_version_id, result_hash, results_json, passed, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    result_hash,
                    result_json,
                    int(passed),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return CalibrationAcceptance(
            model_version_id, passed, result_hash=result_hash, **normalized
        )

    def activate(self, model_version_id: str, *, explicitly_approved: bool) -> ModelVersion:
        model = self.get(model_version_id)
        with self._connect() as connection:
            passed = connection.execute(
                """
                SELECT 1 FROM model_acceptance
                WHERE model_version_id = ? AND passed = 1 LIMIT 1
                """,
                (model_version_id,),
            ).fetchone()
            if passed is None:
                raise ValueError("model_acceptance_required")
            if model_version_id != "model-v0001":
                replay_passed = connection.execute(
                    """
                    SELECT 1 FROM model_replay
                    WHERE model_version_id=? AND passed=1 LIMIT 1
                    """,
                    (model_version_id,),
                ).fetchone()
                if replay_passed is None:
                    raise ValueError("model_replay_acceptance_required")
            if not explicitly_approved:
                raise ValueError("explicit_model_approval_required")
            previous = connection.execute(
                "SELECT model_version_id FROM active_model WHERE singleton = 1"
            ).fetchone()
            if previous is not None and str(previous[0]) != model_version_id:
                connection.execute(
                    "UPDATE model_version SET status = 'superseded' WHERE model_version_id = ?",
                    (str(previous[0]),),
                )
            connection.execute(
                "UPDATE model_version SET status = 'active' WHERE model_version_id = ?",
                (model_version_id,),
            )
            connection.execute(
                """
                INSERT INTO active_model(singleton, model_version_id) VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET model_version_id=excluded.model_version_id
                """,
                (model_version_id,),
            )
            connection.execute(
                """
                INSERT INTO model_activation(
                    model_version_id, previous_model_version_id, activated_at
                ) VALUES (?, ?, ?)
                """,
                (
                    model_version_id,
                    str(previous[0]) if previous is not None else None,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return ModelVersion(
            model.model_version_id,
            model.manifest_hash,
            "active",
            model.certified_replay_start,
        )

    def record_replay(
        self,
        model_version_id: str,
        *,
        compared_with: str,
        requested_start: str,
        requested_end: str,
        quality_passed: bool,
        regression_passed: bool,
        performance_passed: bool,
        stage_differences: int,
        core_state_differences: int,
        gaps: tuple[str, ...],
    ) -> ReplayResult:
        candidate = self.get(model_version_id)
        comparison = self.get(compared_with)
        range_start = max(
            requested_start,
            candidate.certified_replay_start,
            comparison.certified_replay_start,
        )
        if range_start > requested_end:
            raise ValueError("certified_replay_range_empty")
        passed = quality_passed and regression_passed and performance_passed and not gaps
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO model_replay(
                    model_version_id, compared_with, range_start, range_end,
                    quality_passed, regression_passed, performance_passed,
                    stage_differences, core_state_differences, gaps_json,
                    passed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    compared_with,
                    range_start,
                    requested_end,
                    int(quality_passed),
                    int(regression_passed),
                    int(performance_passed),
                    stage_differences,
                    core_state_differences,
                    _canonical_json(gaps),
                    int(passed),
                    datetime.now(UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("model_replay_identity_missing")
            replay_id = int(cursor.lastrowid)
        return ReplayResult(
            replay_id,
            model_version_id,
            compared_with,
            range_start,
            requested_end,
            passed,
            stage_differences,
            core_state_differences,
            gaps,
        )

    def record_first_publication(self, model_version_id: str, target_business_date: str) -> None:
        if self.active().model_version_id != model_version_id:
            raise ValueError("publication_model_is_not_active")
        with self._connect() as connection:
            activation = connection.execute(
                """
                SELECT first_published_business_date FROM model_activation
                WHERE activation_id=(
                    SELECT MAX(activation_id) FROM model_activation
                    WHERE model_version_id=?
                )
                """,
                (model_version_id,),
            ).fetchone()
            if activation is None:
                raise ValueError("model_activation_missing")
            if activation["first_published_business_date"] is not None:
                return
            updated = connection.execute(
                """
                UPDATE model_activation SET first_published_business_date=?
                WHERE activation_id=(
                    SELECT MAX(activation_id) FROM model_activation
                    WHERE model_version_id=?
                ) AND first_published_business_date IS NULL
                """,
                (target_business_date, model_version_id),
            ).rowcount
        if updated != 1:
            raise ValueError("model_first_publication_not_recorded")

    def rollback(
        self,
        model_version_id: str,
        *,
        as_of_business_date: str,
        trading_calendar: tuple[str, ...],
        explicitly_confirmed: bool,
    ) -> ModelVersion:
        if not explicitly_confirmed:
            raise ValueError("explicit_model_rollback_confirmation_required")
        if self.active().model_version_id != model_version_id:
            raise ValueError("model_is_not_active")
        with self._connect() as connection:
            activation = connection.execute(
                """
                SELECT * FROM model_activation
                WHERE model_version_id=?
                ORDER BY activation_id DESC LIMIT 1
                """,
                (model_version_id,),
            ).fetchone()
            if (
                activation is None
                or activation["previous_model_version_id"] is None
                or activation["first_published_business_date"] is None
            ):
                raise ValueError("model_rollback_unavailable")
            first_date = str(activation["first_published_business_date"])
            try:
                first_index = trading_calendar.index(first_date)
                as_of_index = trading_calendar.index(as_of_business_date)
            except ValueError as error:
                raise ValueError("rollback_date_not_in_trading_calendar") from error
            if as_of_index < first_index or as_of_index - first_index >= 30:
                raise ValueError("model_rollback_window_expired")
            previous_model = str(activation["previous_model_version_id"])
            connection.execute(
                "UPDATE model_version SET status='candidate' WHERE model_version_id=?",
                (model_version_id,),
            )
            connection.execute(
                "UPDATE model_version SET status='active' WHERE model_version_id=?",
                (previous_model,),
            )
            connection.execute(
                "UPDATE active_model SET model_version_id=? WHERE singleton=1",
                (previous_model,),
            )
            connection.execute(
                """
                INSERT INTO model_rollback(
                    from_model_version_id, to_model_version_id,
                    as_of_business_date, rolled_back_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    previous_model,
                    as_of_business_date,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return self.get(previous_model)

    def activation_history(self) -> tuple[dict[str, str | None], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_activation ORDER BY activation_id"
            ).fetchall()
        return tuple(
            {
                "model_version_id": str(row["model_version_id"]),
                "previous_model_version_id": (
                    str(row["previous_model_version_id"])
                    if row["previous_model_version_id"] is not None
                    else None
                ),
                "activated_at": str(row["activated_at"]),
                "first_published_business_date": (
                    str(row["first_published_business_date"])
                    if row["first_published_business_date"] is not None
                    else None
                ),
            }
            for row in rows
        )

    def get(self, model_version_id: str) -> ModelVersion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
        if row is None:
            raise LookupError("model_version_not_found")
        return _model_version(row)

    def manifest(self, model_version_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
        if row is None:
            raise LookupError("model_version_not_found")
        document = json.loads(str(row["manifest_json"]))
        if not isinstance(document, dict):
            raise ValueError("model_manifest_invalid")
        return {str(key): value for key, value in document.items()}

    def active(self) -> ModelVersion:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT model_version.* FROM active_model
                JOIN model_version USING(model_version_id)
                WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            raise LookupError("active_model_unavailable")
        return _model_version(row)

    def list_versions(self) -> tuple[ModelVersion, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_version ORDER BY created_at, model_version_id"
            ).fetchall()
        return tuple(_model_version(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _model_version(row: sqlite3.Row) -> ModelVersion:
    return ModelVersion(
        model_version_id=str(row["model_version_id"]),
        manifest_hash=str(row["manifest_hash"]),
        status=str(row["status"]),
        certified_replay_start=str(row["certified_replay_start"]),
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_version (
    model_version_id TEXT PRIMARY KEY,
    manifest_hash TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_replay_start TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_acceptance (
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    result_hash TEXT NOT NULL,
    results_json TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(model_version_id, result_hash)
);
CREATE TABLE IF NOT EXISTS active_model (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id)
);
CREATE TABLE IF NOT EXISTS model_activation (
    activation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    previous_model_version_id TEXT,
    activated_at TEXT NOT NULL,
    first_published_business_date TEXT
);
CREATE TABLE IF NOT EXISTS model_replay (
    replay_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    compared_with TEXT NOT NULL REFERENCES model_version(model_version_id),
    range_start TEXT NOT NULL,
    range_end TEXT NOT NULL,
    quality_passed INTEGER NOT NULL,
    regression_passed INTEGER NOT NULL,
    performance_passed INTEGER NOT NULL,
    stage_differences INTEGER NOT NULL,
    core_state_differences INTEGER NOT NULL,
    gaps_json TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_rollback (
    rollback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    to_model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    as_of_business_date TEXT NOT NULL,
    rolled_back_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS model_manifest_no_update
BEFORE UPDATE OF manifest_hash, manifest_json, certified_replay_start ON model_version BEGIN
    SELECT RAISE(ABORT, 'model_manifest_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS model_version_no_delete
BEFORE DELETE ON model_version BEGIN SELECT RAISE(ABORT, 'model_version_is_immutable'); END;
"""
