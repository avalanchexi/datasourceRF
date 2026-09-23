from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.catalog import (
    METRIC_CATALOG_V0001,
    METRIC_CATALOG_V0003,
    METRIC_CATALOG_VERSION,
    metric_catalog,
    metric_catalog_v0001,
    metric_catalog_v0003,
)
from pring_cycle.source_contract_review import require_model_source_contract
from pring_cycle.storage import database_connection


@dataclass(frozen=True)
class ModelVersion:
    model_version_id: str
    manifest_hash: str
    status: str
    certified_replay_start: str


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
        "metric_catalog_version": METRIC_CATALOG_V0001,
        "metric_definitions": [asdict(item) for item in metric_catalog_v0001()],
    }


def analytical_model_v0002_manifest() -> dict[str, Any]:
    manifest = certified_model_v0001_manifest()
    definitions = [asdict(item) for item in metric_catalog()]
    for definition in definitions:
        if definition["metric_id"] == "CN_FUTURES_WARRANTS":
            definition["allowed_units"] = tuple(
                unit for unit in definition["allowed_units"] if unit != "barrel"
            )
    manifest.update(
        {
            "model_version_id": "model-v0002",
            "metric_catalog_version": METRIC_CATALOG_VERSION,
            "metric_definitions": definitions,
            "derived_formula_versions": {
                "credit_impulse": "credit-impulse-rolling-share-v0001",
                "dr007_policy_spread": "dr007-policy-spread-v0001",
                "loan_monthly_change": "loan-stock-monthly-change-v0001",
                "omo_net_injection": "repo-net-injection-v0001",
                "order_inventory_spread": "pmi-order-inventory-spread-v0001",
                "production_order_spread": "pmi-production-order-spread-v0001",
                "real_inventory_approximation": "inventory-ppi-v0001",
                "ust_2s10s_spread": "ust-2s10s-spread-v0001",
            },
        }
    )
    return manifest


def analytical_model_v0003_manifest() -> dict[str, Any]:
    manifest = analytical_model_v0002_manifest()
    manifest.update(
        {
            "model_version_id": "model-v0003",
            "history_input_start": "2017-01-01",
            "metric_definitions": [asdict(item) for item in metric_catalog()],
        }
    )
    return manifest


def certified_120d_model_v0006_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    if not source_certification_packages:
        raise ValueError("source_certification_packages_required")
    packages = sorted(
        (dict(package) for package in source_certification_packages),
        key=lambda package: str(package.get("package_id", "")),
    )
    if any(not package.get("package_id") for package in packages):
        raise ValueError("source_certification_package_id_required")
    manifest = analytical_model_v0003_manifest()
    manifest.update(
        {
            "model_version_id": "model-v0006",
            "certified_replay_start": "2026-03-09",
            "calibration_range_start": "2018-06-01",
            "history_input_start": "2017-01-01",
            "metric_catalog_version": METRIC_CATALOG_V0003,
            "metric_definitions": [asdict(item) for item in metric_catalog_v0003()],
            "source_certification_packages": packages,
            "visible_evidence_window_trading_days": 120,
            "hidden_preheat_policy": "minimum_formula_inputs_only",
        }
    )
    return manifest


def certified_120d_model_v0007_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0006_manifest(source_certification_packages)
    formulas = dict(manifest["derived_formula_versions"])
    formulas.update(
        {
            "credit_impulse": "credit-impulse-ytd-flow-v0002",
            "loan_monthly_change": "loan-ytd-monthly-change-v0002",
        }
    )
    manifest.update(
        {
            "model_version_id": "model-v0007",
            "derived_formula_versions": formulas,
        }
    )
    return manifest


def certified_120d_model_v0008_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0007_manifest(source_certification_packages)
    manifest["model_version_id"] = "model-v0008"
    return manifest


def certified_120d_model_v0009_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0008_manifest(source_certification_packages)
    manifest["model_version_id"] = "model-v0009"
    return manifest


def certified_120d_model_v0010_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    """Build a content-addressed immutable candidate with hardened trust boundaries."""
    manifest = certified_120d_model_v0009_manifest(source_certification_packages)
    manifest.update(
        {
            "model_version_id": "model-v0010-pending",
            "point_in_time_rule_version": "public-cutoff-v0002",
            "visible_context_window_rule_version": "exact-core-calendar-120-v0001",
            "replay_acceptance_rule_version": "active-baseline-exact-120-v0001",
        }
    )
    identity_document = dict(manifest)
    identity_document.pop("model_version_id", None)
    digest = hashlib.sha256(_canonical_json(identity_document).encode()).hexdigest()
    manifest["model_version_id"] = f"model-v0010-{digest[:16]}"
    return manifest


def certified_120d_model_v0011_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    """Bind trading-calendar OMO maturity semantics to a new immutable model."""
    manifest = certified_120d_model_v0010_manifest(source_certification_packages)
    formulas = dict(manifest["derived_formula_versions"])
    formulas["omo_net_injection"] = "repo-net-injection-trading-calendar-v0002"
    manifest.update(
        {
            "model_version_id": "model-v0011-pending",
            "derived_formula_versions": formulas,
        }
    )
    identity_document = dict(manifest)
    identity_document.pop("model_version_id", None)
    digest = hashlib.sha256(_canonical_json(identity_document).encode()).hexdigest()
    manifest["model_version_id"] = f"model-v0011-{digest[:16]}"
    return manifest


class ModelRepository:
    """Model versions and the one pointer that says which is active (ADR-0022).

    A version is registered once and never changes. Activating one only moves the
    pointer: nothing is replayed or accepted, and summaries already published stay as
    they are. Rolling back is activating the older version again.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ModelRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_MODEL_SCHEMA)
        return repository

    def register(self, manifest: dict[str, Any]) -> ModelVersion:
        """Store a version, with its catalog when that catalog is not built in."""
        from pring_cycle.catalog_registry import (
            BUILTIN_CATALOG_VERSIONS,
            _register_admitted_catalog,
        )

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = self._store(connection, manifest)
            if manifest.get("metric_catalog_version") not in BUILTIN_CATALOG_VERSIONS:
                _register_admitted_catalog(connection, manifest)
        return version

    def create_candidate(self, manifest: dict[str, Any]) -> ModelVersion:
        with self._connect() as connection:
            return self._store(connection, manifest)

    def _store(self, connection: sqlite3.Connection, manifest: dict[str, Any]) -> ModelVersion:
        model_version_id = str(manifest.get("model_version_id", ""))
        if not model_version_id:
            raise ValueError("invalid_model_manifest")
        certified_replay_start = str(manifest.get("certified_replay_start", ""))
        manifest_json = _canonical_json(manifest)
        manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
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
                ) VALUES (?, ?, ?, 'registered', ?, ?)
                """,
            (
                model_version_id,
                manifest_hash,
                manifest_json,
                certified_replay_start,
                datetime.now(UTC).isoformat(),
            ),
        )
        return ModelVersion(model_version_id, manifest_hash, "registered", certified_replay_start)

    def activate(self, model_version_id: str, *, explicitly_approved: bool) -> ModelVersion:
        """Point later runs at this version; only an explicit approval may move it."""
        model = self.get(model_version_id)
        manifest = self.manifest(model_version_id)
        if not explicitly_approved:
            raise ValueError("explicit_model_approval_required")
        require_model_source_contract(manifest)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection


def _model_version(row: sqlite3.Row) -> ModelVersion:
    return ModelVersion(
        model_version_id=str(row["model_version_id"]),
        manifest_hash=str(row["manifest_hash"]),
        status=str(row["status"]),
        certified_replay_start=str(row["certified_replay_start"]),
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_version (
    model_version_id TEXT PRIMARY KEY,
    manifest_hash TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_replay_start TEXT NOT NULL,
    created_at TEXT NOT NULL
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
CREATE TRIGGER IF NOT EXISTS model_manifest_no_update
BEFORE UPDATE OF manifest_hash, manifest_json, certified_replay_start ON model_version BEGIN
    SELECT RAISE(ABORT, 'model_manifest_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS model_version_no_delete
BEFORE DELETE ON model_version BEGIN SELECT RAISE(ABORT, 'model_version_is_immutable'); END;
"""
