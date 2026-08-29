from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acceptance import REGRESSION_IDS
from pring_cycle.artifacts import store_artifact
from pring_cycle.cutover import (
    CUTOVER_CONFIRMATION,
    build_cutover_manifest,
    cutover_status,
    record_direct_cutover,
)
from pring_cycle.domain import CoreAssetState
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.rehearsals import run_fixture_recovery_rehearsal
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def _artifact(paths: RuntimePaths, document: dict[str, object], source: str) -> str:
    content = json.dumps(document, sort_keys=True).encode()
    return store_artifact(
        paths.database,
        paths.artifacts,
        content,
        media_type="application/json",
        source_reference=source,
    ).content_hash


def test_fixture_rehearsal_is_acceptance_only_and_preserves_cutoffs(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = run_fixture_recovery_rehearsal(paths)

    assert result["status"] == "ok"
    assert result["acceptance_only"] is True
    assert result["publication_history_written"] is False
    assert result["interrupted_status"] == "interrupted"
    assert result["resumed_status"] == "queued"
    assert result["cutoffs_preserved"] is True


def test_cutover_has_no_force_path_and_requires_the_exact_confirmation(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    P0ProjectionService(ProjectionSetRepository(paths.database)).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=tuple(
            CoreAssetReadiness(
                asset=asset,
                metric_id=metric_id,
                state=state,
                reason="validated",
                observation_count=160,
                latest_business_date="2026-08-28",
            )
            for asset, metric_id, state in (
                ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
                ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
                ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
            )
        ),  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    acceptance_hash = _artifact(
        paths,
        {
            "schema_version": "v1-acceptance-v0001",
            "status": "ok",
            "performance_gates": {"all": {"passed": True}},
            "regressions": {item: {"passed": True} for item in REGRESSION_IDS},
        },
        "test:acceptance",
    )
    fixture_hash = str(run_fixture_recovery_rehearsal(paths)["artifact"]["hash"])
    real_hash = _artifact(
        paths,
        {"schema_version": "real-projection-rehearsal-v0001", "status": "ok"},
        "test:real-rehearsal",
    )
    manifest = build_cutover_manifest(
        paths,
        acceptance_hash=acceptance_hash,
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=real_hash,
        legacy_system_read_only_stopped=True,
    )
    assert manifest["status"] == "ready"

    with pytest.raises(ValueError, match="explicit_direct_cutover_confirmation_required"):
        record_direct_cutover(
            paths,
            manifest_hash=str(manifest["artifact"]["hash"]),
            confirmation="yes",
        )

    recorded = record_direct_cutover(
        paths,
        manifest_hash=str(manifest["artifact"]["hash"]),
        confirmation=CUTOVER_CONFIRMATION,
    )
    assert recorded.supported_path == "pring-v1-only"
    assert cutover_status(paths) == recorded
