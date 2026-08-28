from __future__ import annotations

import json
import os
import subprocess
import sys


def test_domain_boundary_types_import_without_runtime_frameworks() -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    program = """
import json
import sys
from pring_cycle.domain import (
    CoreAssetState,
    EvidenceObservationId,
    FormalStage,
    ModelVersionId,
    ProjectionSetId,
    ReportId,
    RunId,
)

document = {
    "core_asset_state": CoreAssetState.BULL.value,
    "evidence_observation_id": EvidenceObservationId("evidence-1"),
    "formal_stage": FormalStage.STAGE_I.value,
    "model_version_id": ModelVersionId("model-v0001"),
    "projection_set_id": ProjectionSetId("projection-1"),
    "report_id": ReportId("report-1"),
    "run_id": RunId("run-1"),
    "runtime_frameworks_loaded": sorted(
        name for name in ("alembic", "dash", "fastapi", "sqlalchemy") if name in sys.modules
    ),
}
print(json.dumps(document, sort_keys=True))
"""

    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "core_asset_state": "bull",
        "evidence_observation_id": "evidence-1",
        "formal_stage": "stage_i",
        "model_version_id": "model-v0001",
        "projection_set_id": "projection-1",
        "report_id": "report-1",
        "run_id": "run-1",
        "runtime_frameworks_loaded": [],
    }
