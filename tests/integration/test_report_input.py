"""Phase two #03: a full run hands the AI CLI verified results only (ADR-0027)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.worker import process_pending_run
from tests.integration.test_gap_list import CUTOFF, TARGET, seed
from tests.integration.test_worker_execution import runtime
from tests.reports.test_cli_protocol import install_cli

# The first real run's evidence bundle (2026-09-23), before ADR-0027.
FIRST_REAL_BUNDLE_BYTES = 146_000


def test_full_run_report_prompt_holds_results_without_evidence_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_cli(tmp_path, monkeypatch, record_prompt=True)
    paths = runtime(tmp_path / "runtime")
    seed(paths)
    submitted = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="report-input",
        model_version_id="model-v0001",
        system_as_of=CUTOFF,
        cutoff_mode="explicit",
    )

    process_pending_run(paths)

    assert RunRepository(paths.database).get(submitted.run_id).status == "completed"
    raw = (calls.parent / "codex.prompt.json").read_text()
    prompt: dict[str, Any] = json.loads(raw)
    report_input = prompt["report_input"]
    projection = ProjectionSetRepository(paths.database).current()
    assert len(raw.encode()) < FIRST_REAL_BUNDLE_BYTES // 10
    assert not re.search(r"[0-9a-f]{64}", raw)
    for absent in ("observation_version_ids", "evidence_ids", "allowed_evidence_ids", "claims"):
        assert absent not in raw
    assert report_input["core_states"] == {
        item["asset"]: item["state"] for item in projection.datasets["core_assets"]["assets"]
    }
    assert set(report_input["results"]) >= {
        "formal_stage",
        "core_assets",
        "policy_direction",
        "credit_response",
        "overheat_state",
        "price_pressure",
        "inventory_quadrant",
        "core_carry_forward",
        "gap_summary",
    }
    report = ReportRepository(paths.database).history()[0]
    assert (report.status, report.adapter) == ("completed", "codex_cli")
    assert (report.schema_version, report.input_schema_version) == (
        "report-schema-v0004",
        "report-schema-v0004",
    )
    sections = report.body["ai_explanation"]
    assert all(set(section) == {"title", "explanation"} for section in sections)
    # The reader keeps the full gap list; the AI got its summary.
    assert report.body["gap_list"] == projection.datasets["cycle_overview"]["gap_list"]
    assert "gap_list" not in report_input
