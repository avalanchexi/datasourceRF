from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_health

CUTOVER_CONFIRMATION = "DIRECT_CUTOVER_TO_PRING_V1"


@dataclass(frozen=True)
class CutoverRecord:
    manifest_hash: str
    recorded_at: datetime
    supported_path: str
    legacy_system_state: str


def build_cutover_manifest(
    paths: RuntimePaths,
    *,
    acceptance_hash: str,
    real_rehearsal_hash: str,
    fixture_rehearsal_hash: str,
    legacy_system_read_only_stopped: bool,
) -> dict[str, Any]:
    referenced = {
        "acceptance": _read_artifact(paths, acceptance_hash),
        "fixture_rehearsal": _read_artifact(paths, fixture_rehearsal_hash),
        "real_rehearsal": _read_artifact(paths, real_rehearsal_hash),
    }
    active_model = ModelRepository(paths.database).active()
    projection = ProjectionSetRepository(paths.database).current()
    package_root = Path(__file__).parent
    project_root = _project_root(package_root)
    dependency_file = project_root / "uv.lock"
    documentation_root = project_root / "docs"
    checks = {
        "acceptance": referenced["acceptance"].get("status") == "ok"
        and referenced["acceptance"].get("schema_version") == "v1-acceptance-v0001",
        "database_schema": database_health(paths.database)["migration"] == "current",
        "dependencies": dependency_file.is_file(),
        "documentation": documentation_root.is_dir(),
        "fixture_rehearsal": referenced["fixture_rehearsal"].get("status") == "ok"
        and referenced["fixture_rehearsal"].get("schema_version")
        == "fixture-recovery-rehearsal-v0001",
        "legacy_system_read_only_stopped": legacy_system_read_only_stopped,
        "model_matches_projection": active_model.model_version_id
        == projection.envelope.model_version_id,
        "quality_and_performance": _quality_gates_passed(referenced["acceptance"]),
        "real_rehearsal": referenced["real_rehearsal"].get("status") == "ok"
        and referenced["real_rehearsal"].get("schema_version")
        == "real-projection-rehearsal-v0001",
    }
    document = {
        "checks": checks,
        "code_hash": _tree_hash(package_root, ("*.py", "*.css", "*.js")),
        "configuration_version": "config-v0001",
        "database_revision": "0005_run_step_events",
        "dependency_hash": _file_hash(dependency_file) if dependency_file.is_file() else None,
        "documentation_hash": _tree_hash(documentation_root, ("*.md",)),
        "legacy_system_state": "read_only_stopped"
        if legacy_system_read_only_stopped
        else "not_attested",
        "metric_catalog_hash": hashlib.sha256(
            _canonical_json([asdict(item) for item in metric_catalog()]).encode()
        ).hexdigest(),
        "metric_catalog_version": METRIC_CATALOG_VERSION,
        "model_manifest_hash": active_model.manifest_hash,
        "model_version_id": active_model.model_version_id,
        "projection_set_id": projection.envelope.projection_set_id,
        "references": {
            "acceptance": acceptance_hash,
            "fixture_rehearsal": fixture_rehearsal_hash,
            "real_rehearsal": real_rehearsal_hash,
        },
        "schema_version": "direct-cutover-manifest-v0001",
        "status": "ready" if all(checks.values()) else "blocked",
    }
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        (_canonical_json(document) + "\n").encode(),
        media_type="application/json",
        source_reference="cutover:manifest-candidate",
    )
    return {
        **document,
        "artifact": {"hash": artifact.content_hash, "path": str(artifact.path)},
    }


def record_direct_cutover(
    paths: RuntimePaths,
    *,
    manifest_hash: str,
    confirmation: str,
) -> CutoverRecord:
    if confirmation != CUTOVER_CONFIRMATION:
        raise ValueError("explicit_direct_cutover_confirmation_required")
    manifest = _read_artifact(paths, manifest_hash)
    if manifest.get("schema_version") != "direct-cutover-manifest-v0001":
        raise ValueError("cutover_manifest_schema_invalid")
    if manifest.get("status") != "ready" or not all(manifest.get("checks", {}).values()):
        raise ValueError("cutover_manifest_blocked")
    recorded_at = datetime.now(UTC)
    with _connect(paths.database) as connection:
        existing = connection.execute("SELECT * FROM system_cutover WHERE singleton=1").fetchone()
        if existing is not None:
            if str(existing["manifest_hash"]) != manifest_hash:
                raise ValueError("direct_cutover_already_recorded")
            return _cutover_record(existing)
        connection.execute(
            """
            INSERT INTO system_cutover(
                singleton, manifest_hash, recorded_at, supported_path, legacy_system_state
            ) VALUES (1, ?, ?, 'pring-v1-only', 'read_only_stopped')
            """,
            (manifest_hash, recorded_at.isoformat()),
        )
    return CutoverRecord(manifest_hash, recorded_at, "pring-v1-only", "read_only_stopped")


def cutover_status(paths: RuntimePaths) -> CutoverRecord | None:
    with _connect(paths.database) as connection:
        row = connection.execute("SELECT * FROM system_cutover WHERE singleton=1").fetchone()
    return _cutover_record(row) if row is not None else None


def _read_artifact(paths: RuntimePaths, content_hash: str) -> dict[str, Any]:
    if len(content_hash) != 64:
        raise ValueError("artifact_hash_invalid")
    artifact_path = paths.artifacts / content_hash[:2] / content_hash
    try:
        content = artifact_path.read_bytes()
    except OSError as error:
        raise ValueError("required_cutover_artifact_missing") from error
    if hashlib.sha256(content).hexdigest() != content_hash:
        raise ValueError("required_cutover_artifact_hash_mismatch")
    document = json.loads(content)
    if not isinstance(document, dict):
        raise ValueError("required_cutover_artifact_invalid")
    return {str(key): item for key, item in document.items()}


def _tree_hash(root: Path, patterns: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    paths = sorted({path for pattern in patterns for path in root.rglob(pattern) if path.is_file()})
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _project_root(package_root: Path) -> Path:
    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents, *package_root.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "uv.lock").is_file():
            return candidate
    return package_root.parents[1]


def _quality_gates_passed(document: dict[str, Any]) -> bool:
    gates = document.get("performance_gates")
    regressions = document.get("regressions")
    return (
        isinstance(gates, dict)
        and bool(gates)
        and all(isinstance(item, dict) and item.get("passed") is True for item in gates.values())
        and isinstance(regressions, dict)
        and len(regressions) == 35
        and all(
            isinstance(item, dict) and item.get("passed") is True
            for item in regressions.values()
        )
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _connect(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def _cutover_record(row: sqlite3.Row) -> CutoverRecord:
    return CutoverRecord(
        manifest_hash=str(row["manifest_hash"]),
        recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        supported_path=str(row["supported_path"]),
        legacy_system_state=str(row["legacy_system_state"]),
    )
