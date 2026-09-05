from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import (
    METRIC_CATALOG_V0003,
    METRIC_CATALOG_VERSION,
    metric_catalog,
    metric_catalog_v0003,
)
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.rehearsals import verify_source_smoke_artifacts
from pring_cycle.runtime import RuntimePaths
from pring_cycle.runtime_fingerprint import execution_fingerprint, fingerprint_matches
from pring_cycle.source_contract_review import source_contract_review
from pring_cycle.storage import artifact_is_registered, database_health

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
        "acceptance": _read_artifact(paths, acceptance_hash, kind="acceptance"),
        "fixture_rehearsal": _read_artifact(
            paths,
            fixture_rehearsal_hash,
            kind="fixture_rehearsal",
        ),
        "real_rehearsal": _read_artifact(
            paths,
            real_rehearsal_hash,
            kind="real_rehearsal",
        ),
    }
    models = ModelRepository(paths.database)
    active_model = models.active()
    active_manifest = models.manifest(active_model.model_version_id)
    contract_review = source_contract_review(str(active_manifest.get("metric_catalog_version")))
    try:
        active_rules = ContextProjectionRules.from_manifest(active_manifest)
    except ValueError:
        active_rules = None
    active_catalog_document = active_manifest.get("metric_definitions")
    supported_catalogs = {
        METRIC_CATALOG_VERSION: metric_catalog,
        METRIC_CATALOG_V0003: metric_catalog_v0003,
    }
    catalog_factory = supported_catalogs.get(str(active_manifest.get("metric_catalog_version")))
    current_catalog_document = (
        [asdict(item) for item in catalog_factory()] if catalog_factory is not None else None
    )
    active_catalog_hash = (
        hashlib.sha256(_canonical_json(active_catalog_document).encode()).hexdigest()
        if active_rules is not None
        else None
    )
    current_catalog_hash = hashlib.sha256(
        _canonical_json(current_catalog_document).encode()
    ).hexdigest()
    active_catalog_current = (
        active_rules is not None
        and catalog_factory is not None
        and active_catalog_hash == current_catalog_hash
    )
    projection = ProjectionSetRepository(paths.database).current()
    common_fingerprint = execution_fingerprint(paths)
    model_fingerprint = execution_fingerprint(
        paths,
        model_version_id=active_model.model_version_id,
    )
    package_root = Path(__file__).parent
    project_root = _project_root(package_root)
    dependency_file = project_root / "uv.lock"
    documentation_root = project_root / "docs"
    checks = {
        "acceptance": referenced["acceptance"].get("status") == "ok"
        and referenced["acceptance"].get("schema_version") == "v1-acceptance-v0001",
        "acceptance_fresh": _acceptance_fingerprint_matches(
            referenced["acceptance"],
            common_fingerprint,
            model_version_id=active_model.model_version_id,
            model_manifest_hash=active_model.manifest_hash,
        ),
        "database_schema": database_health(paths.database)["migration"] == "current",
        "dependencies": dependency_file.is_file(),
        "documentation": documentation_root.is_dir(),
        "fixture_rehearsal": referenced["fixture_rehearsal"].get("status") == "ok"
        and referenced["fixture_rehearsal"].get("schema_version")
        == "fixture-recovery-rehearsal-v0001",
        "fixture_rehearsal_fresh": fingerprint_matches(
            referenced["fixture_rehearsal"],
            common_fingerprint,
        ),
        "legacy_system_read_only_stopped": legacy_system_read_only_stopped,
        "model_catalog_current": active_catalog_current,
        "model_catalog_manifest_valid": active_rules is not None,
        "model_source_contract_review": contract_review is None,
        "model_matches_projection": active_model.model_version_id
        == projection.envelope.model_version_id,
        "quality_and_performance": _quality_gates_passed(referenced["acceptance"]),
        "real_rehearsal": _real_rehearsal_passed(
            paths,
            referenced["real_rehearsal"],
            projection_set_id=projection.envelope.projection_set_id,
            target_business_date=projection.envelope.target_business_date,
            expected_fingerprint=model_fingerprint,
        ),
    }
    document = {
        "checks": checks,
        **model_fingerprint,
        "documentation_hash": _tree_hash(documentation_root, ("*.md",)),
        "legacy_system_state": "read_only_stopped"
        if legacy_system_read_only_stopped
        else "not_attested",
        "metric_catalog_hash": active_catalog_hash,
        "metric_catalog_version": (
            active_rules.metric_catalog_version if active_rules is not None else None
        ),
        "projection_set_id": projection.envelope.projection_set_id,
        "source_contract_review": contract_review,
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
    manifest = _read_artifact(paths, manifest_hash, kind="cutover_manifest")
    if manifest.get("schema_version") != "direct-cutover-manifest-v0001":
        raise ValueError("cutover_manifest_schema_invalid")
    if manifest.get("status") != "ready" or not all(manifest.get("checks", {}).values()):
        raise ValueError("cutover_manifest_blocked")
    references = manifest.get("references")
    if not isinstance(references, dict):
        raise ValueError("cutover_manifest_references_invalid")
    rebuilt = build_cutover_manifest(
        paths,
        acceptance_hash=str(references.get("acceptance", "")),
        fixture_rehearsal_hash=str(references.get("fixture_rehearsal", "")),
        real_rehearsal_hash=str(references.get("real_rehearsal", "")),
        legacy_system_read_only_stopped=(
            manifest.get("legacy_system_state") == "read_only_stopped"
        ),
    )
    rebuilt_artifact = rebuilt.get("artifact")
    if (
        not isinstance(rebuilt_artifact, dict)
        or rebuilt_artifact.get("hash") != manifest_hash
        or rebuilt.get("status") != "ready"
    ):
        raise ValueError("cutover_manifest_stale")
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


def _read_artifact(
    paths: RuntimePaths,
    content_hash: str,
    *,
    kind: str,
) -> dict[str, Any]:
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
    normalized = {str(key): item for key, item in document.items()}
    result_hash = normalized.get("normalized_result_hash")
    source_reference = {
        "acceptance": f"acceptance:{result_hash}",
        "fixture_rehearsal": f"rehearsal:fixture-recovery:{result_hash}",
        "real_rehearsal": f"rehearsal:real-projection:{result_hash}",
        "cutover_manifest": "cutover:manifest-candidate",
    }[kind]
    if (
        kind != "cutover_manifest"
        and (not isinstance(result_hash, str) or len(result_hash) != 64)
    ) or not artifact_is_registered(paths.database, content_hash, source_reference):
        raise ValueError("artifact_provenance_invalid")
    return normalized


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


def _real_rehearsal_passed(
    paths: RuntimePaths,
    document: dict[str, Any],
    *,
    projection_set_id: str,
    target_business_date: str,
    expected_fingerprint: dict[str, Any],
) -> bool:
    p0_assets = document.get("p0_assets")
    p1_samples = document.get("p1_schema_samples")
    source_hashes = document.get("source_smoke_hashes")
    if not (
        document.get("status") == "ok"
        and document.get("schema_version") == "real-projection-rehearsal-v0001"
        and document.get("acceptance_only") is True
        and document.get("publication_history_written") is False
        and document.get("dashboard_projection_visible") is True
        and document.get("loopback_requests_during_validation") == 3
        and document.get("network_requests_during_validation") == 0
        and document.get("projection_set_id") == projection_set_id
        and document.get("target_business_date") == target_business_date
        and document.get("report_status") in {"completed", "completed_degraded"}
        and isinstance(document.get("report_adapter"), str)
        and isinstance(p0_assets, list)
        and len(p0_assets) == 3
        and all(isinstance(item, str) and item for item in p0_assets)
        and isinstance(p1_samples, dict)
        and bool(p1_samples)
        and all(value is True for value in p1_samples.values())
        and isinstance(source_hashes, list)
        and all(isinstance(item, str) for item in source_hashes)
        and fingerprint_matches(document, expected_fingerprint)
    ):
        return False
    try:
        verified = verify_source_smoke_artifacts(
            paths,
            tuple(source_hashes),
            target_business_date=target_business_date,
        )
    except ValueError:
        return False
    return sorted(verified) == sorted(document.get("source_smoke_kinds", ()))


def _acceptance_fingerprint_matches(
    document: dict[str, Any],
    expected: dict[str, Any],
    *,
    model_version_id: str,
    model_manifest_hash: str,
) -> bool:
    manifests = document.get("model_manifest_hashes")
    return bool(
        fingerprint_matches(document, expected)
        and isinstance(manifests, dict)
        and manifests.get(model_version_id) == model_manifest_hash
    )


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
