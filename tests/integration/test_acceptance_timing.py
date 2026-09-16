"""The acceptance suite's duration is a visible target, not a hard gate.

Every hard gate keeps blocking; only the ten-minute suite duration became a target that the
quality artifact and the cutover checklist both report without failing on it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acceptance import REGRESSION_IDS, SUITE_TARGET_SECONDS, run_v1_acceptance
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def test_acceptance_reports_a_missed_duration_target_without_failing(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    # A target no real run can meet, instead of waiting ten minutes for the real one.
    result = run_v1_acceptance(paths, include_process_probe=False, suite_target_seconds=0.001)

    assert result["status"] == "ok"
    assert all(item["passed"] for item in result["regressions"].values())
    assert all(item["passed"] for item in result["performance_gates"].values())
    # The duration is no longer one of the hard gates.
    assert "acceptance_suite_seconds" not in result["performance_gates"]
    timing = result["suite_timing"]
    assert timing["target_seconds"] == 0.001
    assert timing["measured_seconds"] > 0.001
    assert timing["target_met"] is False
    # The measured scope is stated: acceptance's own phases, without the failure injections.
    assert timing["scope"] == "acceptance_internal_phases"
    assert timing["includes_failure_injections"] is False


def test_a_real_acceptance_run_is_read_by_the_cutover_side_unchanged(tmp_path: Path) -> None:
    """The generating and consuming ends agree on one real artifact, not a handwritten one."""
    from pring_cycle.cutover import quality_gates_passed, suite_timing_summary

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = run_v1_acceptance(paths, include_process_probe=False)

    assert result["status"] == "ok"
    timing = result["suite_timing"]
    # The published target is ten minutes; a local run is far inside it.
    assert timing["target_seconds"] == SUITE_TARGET_SECONDS == 600
    assert timing["measured_seconds"] < 600 and timing["target_met"] is True
    assert quality_gates_passed(result) is True
    assert suite_timing_summary(result, total_seconds=None)["acceptance_internal_phases"] == timing


def cutover_ready_runtime(tmp_path: Path) -> RuntimePaths:
    """A runtime with an active model and a published projection, as the checklist requires."""
    from datetime import UTC, datetime

    from pring_cycle.domain import CoreAssetState
    from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
    from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
    from pring_cycle.projections import ProjectionSetRepository

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    P0ProjectionService(ProjectionSetRepository(paths.database)).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    return paths


def registered_rehearsals(paths: RuntimePaths) -> tuple[str, str]:
    """Minimal fixture and real rehearsal artifacts, registered under their own provenance."""
    from pring_cycle.artifacts import store_artifact

    hashes = []
    for schema, digest, source in (
        ("fixture-recovery-rehearsal-v0001", "b" * 64, "rehearsal:fixture-recovery:"),
        ("real-projection-rehearsal-v0001", "d" * 64, "rehearsal:real-projection:"),
    ):
        document = {"schema_version": schema, "status": "ok", "normalized_result_hash": digest}
        hashes.append(
            store_artifact(
                paths.database,
                paths.artifacts,
                json.dumps(document, sort_keys=True).encode(),
                media_type="application/json",
                source_reference=f"{source}{digest}",
            ).content_hash
        )
    return hashes[0], hashes[1]


def test_a_real_acceptance_artifact_reaches_the_real_checklist_build(tmp_path: Path) -> None:
    """The artifact the acceptance command stores is the one the checklist builder reads."""
    from pring_cycle.cutover import build_cutover_manifest

    paths = cutover_ready_runtime(tmp_path)
    fixture_hash, real_hash = registered_rehearsals(paths)
    result = run_v1_acceptance(paths, include_process_probe=False)
    acceptance_hash = str(result["artifact"]["hash"])

    manifest = build_cutover_manifest(
        paths,
        acceptance_hash=acceptance_hash,
        # The rehearsals here are minimal stand-ins; the checklist blocks on them, not on quality.
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=real_hash,
        legacy_system_read_only_stopped=False,
        suite_total_seconds=1975.0,
    )

    assert manifest["status"] == "blocked"
    assert manifest["checks"]["quality_and_performance"] is True
    assert manifest["references"]["acceptance"] == acceptance_hash
    timing = manifest["suite_timing"]
    assert timing["acceptance_internal_phases"] == result["suite_timing"]
    assert timing["pytest_total"]["measured_seconds"] == 1975.0


def test_a_failed_regression_blocks_the_real_checklist_quality_check(tmp_path: Path) -> None:
    """A functional failure reaches the same check through a stored artifact, not a stub."""
    from pring_cycle.artifacts import store_artifact
    from pring_cycle.cutover import build_cutover_manifest

    paths = cutover_ready_runtime(tmp_path)
    fixture_hash, real_hash = registered_rehearsals(paths)
    damaged = acceptance_document(
        regressions={item: {"passed": item != REGRESSION_IDS[0]} for item in REGRESSION_IDS},
        normalized_result_hash="c" * 64,
    )
    stored = store_artifact(
        paths.database,
        paths.artifacts,
        json.dumps(damaged, sort_keys=True).encode(),
        media_type="application/json",
        source_reference=f"acceptance:{'c' * 64}",
    )

    manifest = build_cutover_manifest(
        paths,
        acceptance_hash=stored.content_hash,
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=real_hash,
        legacy_system_read_only_stopped=False,
    )

    assert manifest["checks"]["quality_and_performance"] is False
    assert manifest["status"] == "blocked"


def acceptance_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": "v1-acceptance-v0001",
        "status": "ok",
        "performance_gates": {"idle_rss_bytes": {"passed": True}},
        "regressions": {item: {"passed": True} for item in REGRESSION_IDS},
        "suite_timing": {
            "scope": "acceptance_internal_phases",
            "includes_failure_injections": False,
            "target_seconds": 600,
            "measured_seconds": 812.5,
            "target_met": False,
        },
    }
    document.update(overrides)
    return document


def test_cutover_reads_a_missed_duration_target_as_reported_not_blocking() -> None:
    from pring_cycle.cutover import quality_gates_passed, suite_timing_summary

    document = acceptance_document()

    assert quality_gates_passed(document) is True
    summary = suite_timing_summary(document, total_seconds=1975.0)
    assert summary["acceptance_internal_phases"] == document["suite_timing"]
    # The whole test run from start to final state is reported separately, never conflated.
    assert summary["pytest_total"] == {"scope": "pytest_total", "measured_seconds": 1975.0}


@pytest.mark.parametrize(
    "damage",
    [
        # A functional regression, a product performance gate and missing evidence each block.
        {"regressions": {item: {"passed": item != REGRESSION_IDS[0]} for item in REGRESSION_IDS}},
        {"performance_gates": {"idle_rss_bytes": {"passed": False}}},
        {"regressions": {}},
    ],
)
def test_cutover_still_blocks_on_hard_gate_and_evidence_failures(damage: dict[str, Any]) -> None:
    from pring_cycle.cutover import quality_gates_passed

    assert quality_gates_passed(acceptance_document(**damage)) is False


def test_older_artifacts_without_timing_stay_readable() -> None:
    from pring_cycle.cutover import quality_gates_passed, suite_timing_summary

    historical = acceptance_document()
    del historical["suite_timing"]

    assert quality_gates_passed(historical) is True
    summary = suite_timing_summary(historical, total_seconds=None)
    assert summary["acceptance_internal_phases"] == {"scope": "acceptance_internal_phases"}
    assert summary["pytest_total"] == {"scope": "pytest_total"}


@pytest.mark.parametrize("invalid", [-1.0, float("inf")])
def test_a_reported_total_must_be_a_real_measurement(invalid: float) -> None:
    from pring_cycle.cutover import suite_timing_summary

    with pytest.raises(ValueError, match="cutover_suite_total_seconds_invalid"):
        suite_timing_summary(acceptance_document(), total_seconds=invalid)
