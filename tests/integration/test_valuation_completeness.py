from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run


def test_full_run_valuation_demand_keeps_all_three_indices(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="three-index-valuation-demand",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    final = runs.full_retrieval_plan(run.run_id)["final"]
    valuation = next(g for g in final["gaps"] if g["metric_id"] == "CN_INDEX_VALUATION")
    assert valuation["complete"] is False
    assert len(valuation["missing_members"]) == 9
    for index in ("000300.SH", "000905.SH", "000852.SH"):
        assert sum(index in member for member in valuation["missing_members"]) == 3
    assert runs.get(run.run_id).projection_set_id is None
