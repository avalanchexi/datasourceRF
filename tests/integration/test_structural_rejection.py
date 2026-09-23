"""Gate ③: a response that fails its cheap structure check is rejected, recorded, and a gap."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.freshness import batch_freshness
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response

CORES = {"000985.CSI", "000012.SH", "NHII.NH"}


def run_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: str
) -> tuple[RuntimePaths, str]:
    """One full run in which the TuShare series for ``malformed`` comes back without closes."""

    def offline_optional(*args: Any, **kwargs: Any) -> Any:
        raise OSError("fixture optional source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline_optional)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            code = payload["params"].get("ts_code")
            if payload["api_name"] != "trade_cal" and code not in CORES | {malformed}:
                raise OSError("fixture_context_unavailable")
            document = json.loads(historical_response(payload))
            if code == malformed:
                fields = document["data"]["fields"]
                close = fields.index("close")
                document["data"]["fields"] = fields[:close] + fields[close + 1 :]
                document["data"]["items"] = [
                    row[:close] + row[close + 1 :] for row in document["data"]["items"]
                ]
            return BytesIO(json.dumps(document).encode())

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id=f"reject-{malformed}",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    return paths, run.run_id


def rejected_calls(paths: RuntimePaths, run_id: str, code: str) -> list[sqlite3.Row]:
    connection = sqlite3.connect(paths.database)
    connection.row_factory = sqlite3.Row
    try:
        return [
            row
            for row in connection.execute(
                """
                SELECT r.state, r.structure_check, r.rejection_reason, r.parameters_json
                FROM full_run_acquisition a JOIN acquisition_request r USING (acquisition_id)
                WHERE a.run_id=?
                """,
                (run_id,),
            )
            if json.loads(row["parameters_json"]).get("ts_code") == code
        ]
    finally:
        connection.close()


def test_malformed_p1_response_is_rejected_and_the_run_still_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run_id = run_with(tmp_path, monkeypatch, "000300.SH")

    run = RunRepository(paths.database).get(run_id)
    assert run.status == "completed", run.error_classification
    calls = rejected_calls(paths, run_id, "000300.SH")
    assert calls
    assert {(call["state"], call["structure_check"]) for call in calls} == {("failed", "rejected")}
    assert all(call["rejection_reason"] for call in calls)
    assert batch_freshness(paths.database, run_id)["CN_EQ_CSI300"]["status"] == "missing"


def test_malformed_core_response_is_rejected_without_failing_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run_id = run_with(tmp_path, monkeypatch, "NHII.NH")

    run = RunRepository(paths.database).get(run_id)
    assert not (run.error_classification or "").startswith("worker_failure")
    [call] = rejected_calls(paths, run_id, "NHII.NH")
    assert (call["state"], call["structure_check"]) == ("failed", "rejected")
    held = batch_freshness(paths.database, run_id)
    assert held["CN_COMMODITY_CORE_NHII"]["status"] == "missing"
    assert held["CN_EQUITY_CORE_000985"]["status"] != "missing"
