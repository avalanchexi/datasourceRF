"""Ticket 24: the first run rebuilds the window's summaries; a later run fills missed days."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest

from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.integration.test_retention import Runner

FIRST, LATER = "2026-08-03", "2026-08-06"


def query(paths: RuntimePaths, sql: str, *args: object) -> list[tuple[Any, ...]]:
    connection = sqlite3.connect(paths.database)
    try:
        return connection.execute(sql, args).fetchall()
    finally:
        connection.close()


def summary(paths: RuntimePaths, day: str) -> ProjectionSet:
    [(projection_set_id,)] = query(
        paths,
        "SELECT projection_set_id FROM projection_set "
        "WHERE json_extract(envelope_json, '$.target_business_date')=?",
        day,
    )
    return ProjectionSetRepository(paths.database).get(projection_set_id)


def cpi_periods(projection: ProjectionSet) -> set[str]:
    rows = projection.datasets["macro"]["price_chain"]["evidence"]
    return {str(row.get("period")) for row in rows if row.get("metric_id") == "CN_CPI_HEADLINE"}


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("backfill") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
        runner = Runner(paths, monkeypatch)
        first = runner.run(FIRST, "first")
        first_days = {
            row[0] for row in query(paths, "SELECT target_business_date FROM p0_assessment")
        }
        later = runner.run(LATER, "later")
        yield {"paths": paths, "first": first, "later": later, "first_days": first_days}


def test_first_run_summarizes_every_window_day_and_reports_once(runs: dict[str, Any]) -> None:
    paths = runs["paths"]
    [(document,)] = query(
        paths,
        "SELECT document_json FROM full_run_gap_plan WHERE run_id=? AND phase='final'",
        runs["first"],
    )
    window = json.loads(document)["daily_window"]["dates"]

    assert len(window) == 120
    assert runs["first_days"] == set(window)
    history = summary(paths, FIRST).datasets["stage_history"]["events"]
    assert [event["business_date"] for event in history] == window
    assert query(
        paths,
        "SELECT target_business_date FROM report_snapshot WHERE target_business_date<=?",
        FIRST,
    ) == [(FIRST,)]


def test_missed_days_are_summarized_without_reports(runs: dict[str, Any]) -> None:
    paths = runs["paths"]

    days = {row[0] for row in query(paths, "SELECT target_business_date FROM p0_assessment")}
    assert {"2026-08-04", "2026-08-05", LATER} <= days
    reports = query(paths, "SELECT target_business_date FROM report_snapshot ORDER BY 1")
    assert reports == [(FIRST,), (LATER,)]
    assert ProjectionSetRepository(paths.database).current().envelope.target_business_date == LATER
