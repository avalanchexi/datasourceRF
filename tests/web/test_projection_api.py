from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI

from pring_cycle.projections import ANALYTICAL_DATASETS, ProjectionEnvelope, ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.web import create_web_application


def _route(application: FastAPI, name: str) -> Any:
    return next(route for route in application.routes if getattr(route, "name", None) == name)


def test_current_projection_rest_preserves_the_atomic_envelope(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = ProjectionSetRepository(paths.database)
    envelope = ProjectionEnvelope(
        projection_set_id="projection-api-test",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        target_business_date="2026-08-28",
        evidence_snapshot_id="evidence-api-test",
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        evidence_window_start="2026-03-09",
        evidence_window_end="2026-08-28",
        generated_at=datetime(2026, 8, 28, 13, 1, tzinfo=UTC),
        completeness="complete",
        refresh_status="changed",
        warnings=(),
    )
    datasets = {
        name: {"projection_set_id": envelope.projection_set_id, "name": name}
        for name in ANALYTICAL_DATASETS
    }
    repository.publish(envelope, datasets)
    application = create_web_application(paths, 8050)

    current_response = _route(application, "current_projection").endpoint()
    dataset_response = _route(application, "current_projection_dataset").endpoint("macro")
    current = json.loads(cast(bytes, current_response.body))
    dataset = json.loads(cast(bytes, dataset_response.body))

    assert current_response.status_code == 200
    assert dataset_response.status_code == 200
    assert current["envelope"] == dataset["envelope"]
    assert dataset["dataset_name"] == "macro"
    assert dataset["data"] == datasets["macro"]


def test_runtime_init_bootstraps_the_candidate_model_without_activating_it(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")

    initialized = initialize_runtime(paths)
    application = create_web_application(paths, 8050)
    response = _route(application, "model_index").endpoint()

    assert initialized["network_requests"] == 0
    assert response == [
        {
            "model_version_id": "model-v0001",
            "manifest_hash": response[0]["manifest_hash"],
            "status": "candidate",
            "certified_replay_start": "2018-06-01",
        }
    ]
