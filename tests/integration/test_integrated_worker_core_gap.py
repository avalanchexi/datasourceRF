"""A missing P0 delivery cannot publish even with an accepted active synthetic model."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_integrated_worker_delivery import (
    core_through_current_target,
    serve_deliveries,
)
from tests.models.test_isolated_lifecycle import isolated_lifecycle_material


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 13, tzinfo=UTC))


@pytest.mark.usefixtures("runtime_clock")
def test_missing_core_delivery_blocks_a_full_run_and_keeps_its_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, material = isolated_lifecycle_material(
        tmp_path / "runtime", profile="acquisition-repairs"
    )
    candidate = material["candidate_model_version_id"]
    assert ModelRepository(paths.database).active().model_version_id == candidate
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n")
    paths.secrets.chmod(0o600)
    # All optional official sources are also unavailable. A successful independent calendar
    # and an empty, correctly shaped core delivery isolate missing values from invalid schema.
    serve_deliveries(monkeypatch, official_available=False)
    calendar = core_through_current_target()
    raw_deliveries: list[bytes] = []

    class MissingCore:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            if payload["api_name"] == "trade_cal":
                return calendar.open(request, timeout=timeout)
            content = json.dumps(
                {"code": 0, "data": {"fields": payload["fields"].split(","), "items": []}}
            ).encode()
            raw_deliveries.append(content)
            return BytesIO(content)

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *h: MissingCore())
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-11",
        client_request_id="integrated-missing-core",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.error_classification == "worker_failure:ValueError:core_series_missing"
    assert stored.projection_set_id is None
    assert not any(
        item["kind"] == "report_snapshot" for item in runs.reusable_checkpoints(stored.run_id)
    )
    owned = runs.full_retrieval_plan(stored.run_id)["acquisitions"]
    assert any(r["api_name"] == "trade_cal" and r["state"] == "validated" for r in owned)
    failed = [r for r in owned if r["api_name"] == "index_daily" and r["state"] == "failed"]
    assert failed and raw_deliveries
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for row in failed:
        assert row["phase"] == "direct_core_refresh"
        assert "CN_EQUITY_CORE_000985" in row["metric_ids"]
        assert acquisitions.read_content(row["acquisition_id"], "raw") in raw_deliveries
        assert acquisitions.get(row["acquisition_id"]).parameters["ts_code"] == "000985.CSI"
    points = EvidenceRepository(paths.database).metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=material["metric_catalog_version"],
    )
    assert points and not any(p.period_end == "2026-09-11" for p in points)
