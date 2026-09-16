"""The acceptance suite's duration is a visible target, not a hard gate.

Every hard gate keeps blocking; only the ten-minute suite duration became a target that the
quality artifact and the cutover checklist both report without failing on it.
"""

from __future__ import annotations

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
