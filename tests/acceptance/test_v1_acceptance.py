from __future__ import annotations

import json
from pathlib import Path

from pring_cycle.acceptance import REGRESSION_IDS, run_v1_acceptance
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def test_unified_offline_acceptance_covers_all_35_regressions_and_hard_gates(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = run_v1_acceptance(paths, include_process_probe=False)

    assert result["status"] == "ok"
    assert result["network_requests"] == 0
    assert set(result["regressions"]) == set(REGRESSION_IDS)
    assert len(result["regressions"]) == 35
    assert all(item["passed"] for item in result["regressions"].values())
    assert all(item["passed"] for item in result["performance_gates"].values())
    artifact_path = Path(str(result["artifact"]["path"]))
    assert artifact_path.is_file()
    assert result["artifact"]["hash"] in str(artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert "credential" not in json.dumps(artifact).lower()


def test_acceptance_is_deterministic_for_the_same_frozen_inputs(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    first = run_v1_acceptance(paths, include_process_probe=False)
    second = run_v1_acceptance(paths, include_process_probe=False)

    assert first["normalized_result_hash"] == second["normalized_result_hash"]
