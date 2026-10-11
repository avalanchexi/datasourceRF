"""One manual full run is one processing batch, traceable from every detail and summary row."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response

SUMMARY_TABLES = (
    "derived_observation",
    "projection_set",
    "analytical_dataset",
    "current_projection",
    "p0_assessment",
    "data_gap_notice",
    "report_snapshot",
)


def _weekdays(start: str, end: str) -> int:
    first = datetime.strptime(start, "%Y%m%d").date()
    last = datetime.strptime(end, "%Y%m%d").date()
    return sum((first + timedelta(days=i)).weekday() < 5 for i in range((last - first).days + 1))


def _days(start: str, end: str) -> int:
    first = datetime.strptime(start, "%Y%m%d").date()
    return (datetime.strptime(end, "%Y%m%d").date() - first).days + 1


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[RuntimePaths, str]]:
    """One Worker run shared by the read-only assertions below."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield _complete_run(tmp_path_factory.mktemp("batch"), monkeypatch)


def _complete_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[RuntimePaths, str]:
    def offline_optional(*args: Any, **kwargs: Any) -> Any:
        raise OSError("fixture optional source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline_optional)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            code = payload["params"].get("ts_code")
            if payload["api_name"] != "trade_cal" and code not in {
                "000985.CSI",
                "000012.SH",
                "NHII.NH",
            }:
                raise OSError("fixture_context_unavailable")
            return BytesIO(historical_response(payload))

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
    )
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id="batch-skeleton",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert RunRepository(paths.database).get(run.run_id).status == "completed"
    return paths, run.run_id


def _rows(paths: RuntimePaths, sql: str, *args: object) -> list[sqlite3.Row]:
    connection = sqlite3.connect(paths.database)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, args).fetchall()
    finally:
        connection.close()


def test_batch_registers_target_day_code_version_and_model_version(
    completed_run: tuple[RuntimePaths, str],
) -> None:
    paths, run_id = completed_run

    (batch,) = _rows(
        paths,
        "SELECT target_business_date, code_version, model_version_id "
        "FROM parent_run WHERE run_id=?",
        run_id,
    )

    assert batch["target_business_date"] == "2026-08-03"
    assert batch["model_version_id"] == "model-v0001"
    assert isinstance(batch["code_version"], str) and len(batch["code_version"]) == 64


def test_every_interface_call_records_parameters_counts_and_raw_hash(
    completed_run: tuple[RuntimePaths, str],
) -> None:
    paths, run_id = completed_run

    calls = _rows(
        paths,
        """
        SELECT r.api_name, r.parameters_json, r.row_count, r.source_record_count,
               r.normalized_scalar_count, r.ingest_result, r.ingested_claim_count,
               r.raw_hash, r.state
        FROM full_run_acquisition a JOIN acquisition_request r USING (acquisition_id)
        WHERE a.run_id=?
        """,
        run_id,
    )

    validated = [call for call in calls if call["state"] == "validated"]
    assert {call["api_name"] for call in validated} >= {"trade_cal", "index_daily"}
    for call in validated:
        parameters = json.loads(call["parameters_json"])
        assert parameters["start_date"] and parameters["end_date"]
        assert len(call["raw_hash"]) == 64
        # The source's rows and the values read from them are kept apart (lookback 06).
        expected = _weekdays(parameters["start_date"], parameters["end_date"])
        assert call["row_count"] is None, call["api_name"]
        # A calendar answer states every day of its range, closed ones too (ticket 02).
        assert call["source_record_count"] == (
            _days(parameters["start_date"], parameters["end_date"])
            if call["api_name"] == "trade_cal"
            else expected
        ), call["api_name"]
        # A calendar answer states no metric value; a day's bar states its close.
        assert call["normalized_scalar_count"] == (
            None if call["api_name"] == "trade_cal" else expected
        ), call["api_name"]
        if call["api_name"] != "trade_cal":
            assert (call["ingest_result"], call["ingested_claim_count"]) == ("accepted", expected)


def test_summary_rows_carry_the_run_as_their_batch(
    completed_run: tuple[RuntimePaths, str],
) -> None:
    paths, run_id = completed_run

    for table in SUMMARY_TABLES:
        batches = {row[0] for row in _rows(paths, f"SELECT batch_id FROM {table}")}
        assert batches <= {run_id}, table
    for table in ("projection_set", "analytical_dataset", "current_projection", "report_snapshot"):
        assert {row[0] for row in _rows(paths, f"SELECT batch_id FROM {table}")} == {run_id}


def test_batch_stays_out_of_the_page_and_the_report(
    completed_run: tuple[RuntimePaths, str],
) -> None:
    paths, run_id = completed_run

    projection = ProjectionSetRepository(paths.database).current()
    report = ReportRepository(paths.database).history()[0]
    published = json.dumps(
        [projection.datasets, str(projection.envelope), report.body], default=str
    )

    assert "batch" not in published
    assert date(2026, 8, 3).isoformat() in published
