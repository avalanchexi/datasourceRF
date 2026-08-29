from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pring_cycle.artifacts import store_artifact
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def run_fixture_recovery_rehearsal(paths: RuntimePaths) -> dict[str, Any]:
    paths.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fixture-rehearsal-", dir=paths.cache) as directory:
        fixture_paths = RuntimePaths.discover(Path(directory) / "runtime")
        initialize_runtime(fixture_paths)
        models = ModelRepository(fixture_paths.database)
        models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
        models.activate("model-v0001", explicitly_approved=True)
        runs = RunRepository(fixture_paths.database)
        cutoff = datetime(2026, 8, 28, 13, tzinfo=UTC)
        submitted = runs.submit_manual_full(
            target_business_date="2026-08-28",
            client_request_id="fixture-recovery-original",
            model_version_id="model-v0001",
            system_as_of=cutoff,
        )
        runs.acquire_lease(
            submitted.run_id,
            owner_id="fixture-dead-worker",
            process_id=999999,
            now=cutoff,
        )
        decision = runs.audit_lease(
            now=cutoff + timedelta(seconds=121),
            process_is_alive=lambda _process_id: False,
        )
        interrupted = runs.get(submitted.run_id)
        resumed = runs.resume(
            submitted.run_id,
            client_request_id="fixture-recovery-resume",
            confirm_external_calls=True,
        )
        document = {
            "acceptance_only": True,
            "attempt_count": resumed.attempt_count,
            "cutoffs_preserved": (
                resumed.system_as_of == submitted.system_as_of
                and resumed.report_cutoff == submitted.report_cutoff
            ),
            "interrupted_status": interrupted.status,
            "lease_audit": asdict(decision),
            "network_requests": 0,
            "publication_history_written": False,
            "resumed_status": resumed.status,
            "schema_version": "fixture-recovery-rehearsal-v0001",
            "status": "ok",
        }
    return _store_rehearsal(paths, "fixture-recovery", document)


def run_real_projection_rehearsal(
    paths: RuntimePaths,
    *,
    target_business_date: str,
) -> dict[str, Any]:
    projection = ProjectionSetRepository(paths.database).current()
    if projection.envelope.target_business_date != target_business_date:
        raise ValueError("real_rehearsal_target_is_not_current_projection")
    overview = projection.datasets["cycle_overview"]
    assets = projection.datasets["core_assets"].get("assets")
    if not isinstance(assets, list) or len(assets) != 3:
        raise ValueError("real_rehearsal_p0_manifest_incomplete")
    if any(
        not isinstance(item, dict)
        or item.get("reason") != "validated"
        or int(item.get("observation_count", 0)) < 140
        or item.get("latest_business_date") != target_business_date
        for item in assets
    ):
        raise ValueError("real_rehearsal_p0_not_ready")
    macro = projection.datasets["macro"]
    inventory = projection.datasets["inventory"]
    inventory_cards = inventory.get("cards")
    p1_samples = {
        "inventory_cards": isinstance(inventory_cards, list) and len(inventory_cards) > 0,
        "macro_schema_family": all(
            macro.get(key) not in {None, "insufficient_data"}
            for key in ("policy_direction", "overheat_state", "price_pressure")
        ),
    }
    if not all(p1_samples.values()):
        raise ValueError("real_rehearsal_p1_schema_sample_incomplete")
    reports = tuple(
        item
        for item in ReportRepository(paths.database).history()
        if item.projection_set_id == projection.envelope.projection_set_id
    )
    if not reports or reports[0].status not in {"completed", "completed_degraded"}:
        raise ValueError("real_rehearsal_report_missing")
    if overview.get("current_stage") is None and overview.get("stage_reason") not in {
        "noncanonical_combination",
        "core_state_unavailable",
    }:
        raise ValueError("real_rehearsal_stage_semantics_invalid")
    document = {
        "acceptance_only": True,
        "dashboard_projection_visible": True,
        "network_requests_during_validation": 0,
        "p0_assets": [str(item["metric_id"]) for item in assets if isinstance(item, dict)],
        "p1_schema_samples": p1_samples,
        "projection_set_id": projection.envelope.projection_set_id,
        "publication_history_written": False,
        "report_adapter": reports[0].adapter,
        "report_status": reports[0].status,
        "schema_version": "real-projection-rehearsal-v0001",
        "status": "ok",
        "target_business_date": target_business_date,
    }
    return _store_rehearsal(paths, "real-projection", document)


def _store_rehearsal(
    paths: RuntimePaths,
    kind: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    normalized_hash = hashlib.sha256(_canonical_json(document).encode()).hexdigest()
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        (_canonical_json(document) + "\n").encode(),
        media_type="application/json",
        source_reference=f"rehearsal:{kind}:{normalized_hash}",
    )
    return {
        **document,
        "artifact": {"hash": artifact.content_hash, "path": str(artifact.path)},
        "normalized_result_hash": normalized_hash,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
