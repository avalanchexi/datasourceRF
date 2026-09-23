"""Ticket 24: the first run rebuilds the window's summaries; a later run fills missed days."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.integration.test_retention import Runner

FIRST, LATER = "2026-08-03", "2026-08-06"
# July's CPI became public on 5 August: the summary of the 4th must not see it.
CPI_PUBLIC = datetime(2026, 8, 5, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


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
        acquired = datetime.now(UTC)
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id="CN_CPI_HEADLINE",
                definition_version="metric-catalog-v0001",
                period_kind="month",
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions={"measure": "yoy", "category": "headline"},
                value=0.5,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="fixture",
                source_reference="fixture:cpi:2026-07",
                release_event_id="fixture:cpi:2026-07",
                release_at=CPI_PUBLIC,
                public_available_at=CPI_PUBLIC,
                fetched_at=acquired,
                available_at=acquired,
                quality_status="validated",
            )
        )
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


def test_a_backfilled_day_sees_only_what_was_public_by_its_end(runs: dict[str, Any]) -> None:
    paths = runs["paths"]

    assert "2026-07-31" not in cpi_periods(summary(paths, "2026-08-04"))
    assert "2026-07-31" in cpi_periods(summary(paths, "2026-08-05"))
