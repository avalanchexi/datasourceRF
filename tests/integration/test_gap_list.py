"""Gate ①: one visible gap list per batch, and the P1/P2 freshness disposition behind it."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.day_summary import DaySummaries, ModelRules, RunMaterials
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.freshness import freshness_statement, gap_list
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.worker import process_pending_run
from tests.integration.test_decertified_main_chain import claim, rows_for
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

TARGET = date(2026, 8, 28)
# Thursday, re-run at Friday evening's cutoff: chosen as of its day, judged as of the cutoff.
EARLIER_TARGET = date(2026, 8, 27)
# Friday 21:00, after the 17:00 index update: the 28th is released, the 27th is due.
CUTOFF = datetime(2026, 8, 28, 21, tzinfo=ZoneInfo("Asia/Shanghai"))
# Last held session for each daily P1/P2 and the disposition it should get.
HELD = {
    "CN_EQ_CSI300": date(2026, 8, 27),  # awaiting release: carried, not a gap
    "CN_EQ_CSI500": date(2026, 8, 26),  # one period behind: carried, freshness gap
    "CN_EQ_CSI1000": date(2026, 8, 25),  # two behind: missing
    "CN_BOND_10Y_930916": date(2026, 8, 26),  # projected, one behind: still used
    "CN_DR007": date(2026, 8, 25),  # projected, two behind: kept out as stale
}


def sessions() -> list[date]:
    days: list[date] = []
    day = TARGET
    while len(days) < 180:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return list(reversed(days))


def seed(paths: RuntimePaths) -> None:
    days = sessions()
    seed_independent_calendar(paths, days)
    claims = []
    for index, observed in enumerate(days):
        for metric_id, value in (
            ("CN_BOND_CORE_000012", 100.0 + index),
            ("CN_EQUITY_CORE_000985", 1000.0 + index),
            ("CN_COMMODITY_CORE_NHII", 100.0 + index),
        ):
            api_name, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                claim(
                    metric_id,
                    observed,
                    value,
                    unit="index_points",
                    provider="tushare",
                    reference=f"tushare:{api_name}:{code}:{observed}",
                )
            )
        for metric_id, last in HELD.items():
            if observed <= last:
                claims.append(
                    claim(
                        metric_id,
                        observed,
                        2.0,
                        unit="scalar",
                        provider="fixture",
                        reference=f"fixture:{metric_id}:{observed}",
                    )
                )
        claims.append(
            claim(
                "CN_USDCNH_FXCM",
                observed,
                15.0,
                unit="index_points",
                provider="fixture",
                reference=f"fixture:usdcnh:{observed}",
            )
        )
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))


def run(paths: RuntimePaths, target: date = TARGET) -> str:
    submitted = RunRepository(paths.database).submit_manual_full(
        target_business_date=target.isoformat(),
        client_request_id="gap-list",
        model_version_id="model-v0001",
        system_as_of=CUTOFF,
        cutoff_mode="explicit",
    )
    process_pending_run(paths, report_adapters=())
    return submitted.run_id


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[RuntimePaths, Any]]:
    paths = runtime(tmp_path_factory.mktemp("gaps"))
    seed(paths)
    run_id = run(paths)
    assert RunRepository(paths.database).get(run_id).status == "completed"
    yield paths, ProjectionSetRepository(paths.database).current()


@pytest.fixture(scope="module")
def rerun(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[RuntimePaths, Any]]:
    """An earlier target day run at the same cutoff (lookback 27)."""
    paths = runtime(tmp_path_factory.mktemp("gaps-rerun"))
    seed(paths)
    run_id = run(paths, EARLIER_TARGET)
    assert RunRepository(paths.database).get(run_id).status == "completed"
    yield paths, ProjectionSetRepository(paths.database).current()


@pytest.fixture(scope="module")
def summarized(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """The target day's summary alone, without a run around it."""
    paths = runtime(tmp_path_factory.mktemp("gap-summary"))
    seed(paths)
    result = (
        DaySummaries(
            EvidenceRepository(paths.database),
            ProjectionSetRepository(paths.database),
            ModelRules.of(ModelRepository(paths.database), "model-v0001"),
            calendar=TradingCalendar(sessions()),
        )
        .summarize_target(TARGET.isoformat(), system_as_of=CUTOFF, run_materials=RunMaterials())
        .result
    )
    assert result.projection_set_id is not None
    return ProjectionSetRepository(paths.database).get(result.projection_set_id)


def by_metric(projection: Any) -> dict[str, dict[str, object]]:
    return {
        str(item["metric_id"]): item for item in projection.datasets["cycle_overview"]["gap_list"]
    }


def test_gap_list_classifies_each_freshness_disposition(
    published: tuple[RuntimePaths, Any],
) -> None:
    _paths, projection = published
    gaps = by_metric(projection)

    assert "CN_EQ_CSI300" not in gaps
    assert (gaps["CN_EQ_CSI500"]["category"], gaps["CN_EQ_CSI500"]["periods_behind"]) == (
        "freshness_gap",
        1,
    )
    # Index closes and money-market rates come from TuShare alone: no page to search. That
    # is a property of the gap, not why it is missing (gap sources #04).
    assert gaps["CN_EQ_CSI1000"]["category"] == "missing"
    assert gaps["CN_EQ_CSI1000"]["reason"] == "two_or_more_periods_behind"
    assert gaps["CN_EQ_CSI1000"]["no_web_fallback"] is True
    assert gaps["CN_SHIBOR_ON_1W_3M"]["no_web_fallback"] is True
    assert gaps["CN_EQ_CSI500"]["no_web_fallback"] is True
    assert gaps["CN_USDCNH_FXCM"]["category"] == "unconfigured"
    assert all(item["priority"] != "P0" for item in gaps.values())


def test_trade_calendar_is_operational_evidence_not_a_gap(
    published: tuple[RuntimePaths, Any],
) -> None:
    paths, projection = published
    from pring_cycle.storage import database_connection

    with database_connection(paths.database) as connection:
        assessed = {
            row[0]
            # The module's database holds this one run's batch.
            for row in connection.execute("SELECT metric_id FROM batch_freshness")
        }

    assert "CN_TRADE_CALENDAR" not in by_metric(projection)
    assert assessed and "CN_TRADE_CALENDAR" not in assessed


def test_one_period_behind_is_used_and_two_behind_is_not(summarized: Any) -> None:
    projection = summarized

    bond = next(rows_for(projection.datasets, "CN_BOND_10Y_930916"))
    dr007 = next(rows_for(projection.datasets, "CN_DR007"))

    assert (bond["status"], bond["period"]) == ("current", "2026-08-26")
    assert dr007["status"] == "stale"


def test_p1_gaps_do_not_withhold_the_formal_stage(summarized: Any) -> None:
    projection = summarized

    assert projection.datasets["cycle_overview"]["current_stage"] is not None


def test_page_and_report_show_the_same_gap_list(published: tuple[RuntimePaths, Any]) -> None:
    paths, projection = published
    from pring_cycle.dashboard import _home_page

    report = ReportRepository(paths.database).history()[0]
    page = str(_home_page(projection))

    assert report.body["gap_list"] == projection.datasets["cycle_overview"]["gap_list"]
    for label in ("缺口清单", "未配置额外网页检索补缺", "时效缺口", "未配置时效", "CN_EQ_CSI500"):
        assert label in page


@pytest.mark.parametrize(
    ("scenario", "statement"),
    [
        ("published", "目标日 2026-08-28；时效截至 2026-08-28 21:00（北京）"),
        ("rerun", "目标日 2026-08-27；时效截至 2026-08-28 21:00（北京）"),
    ],
)
def test_gap_list_report_and_page_state_the_target_and_the_freshness_cutoff(
    request: pytest.FixtureRequest, scenario: str, statement: str
) -> None:
    # Lookback 27: an earlier target keeps its freshness judged at the run's cutoff; the
    # gap list, the report and the page say both, at the same instant.
    from pring_cycle.dashboard import _home_page, _report_reader
    from pring_cycle.storage import database_connection

    paths, projection = request.getfixturevalue(scenario)
    overview = projection.datasets["cycle_overview"]
    report = ReportRepository(paths.database).history()[0]
    with database_connection(paths.database) as connection:
        assessed = {row[0] for row in connection.execute("SELECT assessed_at FROM batch_freshness")}

    assert {datetime.fromisoformat(item) for item in assessed} == {CUTOFF}
    assert datetime.fromisoformat(str(overview["gap_list_assessed_at"])) == CUTOFF
    assert report.body["freshness_basis"] == {
        "target_business_date": projection.envelope.target_business_date,
        "assessed_at": overview["gap_list_assessed_at"],
        "statement": statement,
    }
    assert statement in str(_home_page(projection))
    assert statement in str(_report_reader(report))


def test_the_statement_reads_the_cutoff_in_beijing_to_the_minute() -> None:
    # The third lookback round's cutoff, stored in UTC: frozen at 22:30:30 Beijing.
    assessed = datetime(2026, 10, 9, 14, 30, 30, 739894, tzinfo=UTC)

    assert freshness_statement("2026-09-30", assessed) == (
        "目标日 2026-09-30；时效截至 2026-10-09 22:30（北京）"
    )


def test_an_earlier_target_keeps_the_cutoffs_gap_categories(
    published: tuple[RuntimePaths, Any], rerun: tuple[RuntimePaths, Any]
) -> None:
    # Selection stops at the target day; timeliness is the cutoff's, the same for both.
    categories = {
        name: {metric_id: gap["category"] for metric_id, gap in by_metric(projection).items()}
        for name, (_paths, projection) in (("today", published), ("earlier", rerun))
    }

    assert categories["earlier"] == categories["today"]
    assert rerun[1].envelope.target_business_date == EARLIER_TARGET.isoformat()


def test_a_set_published_before_the_gap_list_carried_its_time_reads_the_cutoff(
    published: tuple[RuntimePaths, Any],
) -> None:
    from pring_cycle.dashboard import _home_page

    _paths, projection = published
    overview = dict(projection.datasets["cycle_overview"])
    del overview["gap_list_assessed_at"]
    older = replace(projection, datasets={**projection.datasets, "cycle_overview": overview})

    assert "目标日 2026-08-28；时效截至 2026-08-28 21:00（北京）" in str(_home_page(older))


@pytest.fixture
def batch_copy(published: tuple[RuntimePaths, Any], tmp_path: Path) -> tuple[Path, str]:
    """A copy of the published batch's database, to record rejected candidates in."""
    paths, _projection = published
    database = tmp_path / "batch.sqlite3"
    with sqlite3.connect(paths.database) as source, sqlite3.connect(database) as target:
        source.backup(target)
    with sqlite3.connect(database) as connection:
        [(run_id,)] = connection.execute("SELECT DISTINCT batch_id FROM batch_freshness")
    return database, run_id


def reject(database: Path, run_id: str, metric_id: str, period: str) -> str:
    """Record a search candidate the batch rejected for one period of a metric."""
    url = f"https://mirror.example/{metric_id}/{period}"
    gap_id = f"gap-fixture-{metric_id}-{period}"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO retrieval_gap VALUES (?, ?, 'fixture')",
            (gap_id, json.dumps({"metric_id": metric_id, "period": period})),
        )
        connection.execute(
            "INSERT INTO retrieval_candidate_validation(validation_id, run_id, "
            "search_request_id, candidate_url, outcome, reason, checked_at, gap_ids_json, "
            "claim_ids_json, selected_claim_ids_json) "
            "VALUES (?, ?, 'fixture', ?, 'not_model_usable', 'period_mismatch', ?, ?, '[]', '[]')",
            (f"validation-{gap_id}", run_id, url, CUTOFF.isoformat(), json.dumps([gap_id])),
        )
    return url


def listed(database: Path, run_id: str) -> dict[str, dict[str, object]]:
    rules = ContextProjectionRules.from_manifest(ModelRepository(database).manifest("model-v0001"))
    gaps = gap_list(database, run_id, rules.metric_definitions)
    return {str(gap["metric_id"]): gap for gap in gaps}


def test_candidate_rejected_for_a_period_held_since_leaves_the_metric_gap_alone(
    batch_copy: tuple[Path, str],
) -> None:
    # Run findings 1002 ticket 05: the 26th was searched, a candidate refused, then the
    # 26th was filled; the metric is still a session behind, which is no failed retrieval.
    database, run_id = batch_copy
    reject(database, run_id, "CN_EQ_CSI500", "2026-08-26")
    # A period outside the run's window that is held long since is resolved too.
    reject(database, run_id, "CN_EQ_CSI500", "2026-01-05")

    gap = listed(database, run_id)["CN_EQ_CSI500"]

    assert (gap["category"], gap["reason"]) == ("freshness_gap", "one_period_behind_carried")
    assert "candidates" not in gap


def test_candidate_rejected_for_a_period_still_missing_is_a_failed_retrieval(
    batch_copy: tuple[Path, str],
) -> None:
    database, run_id = batch_copy
    reject(database, run_id, "CN_EQ_CSI500", "2026-08-26")
    url = reject(database, run_id, "CN_EQ_CSI500", "2026-08-27")

    gap = listed(database, run_id)["CN_EQ_CSI500"]

    assert gap["category"] == "retrieval_failed"
    assert gap["candidates"] == [{"url": url, "reason": "period_mismatch"}]


def test_candidate_rejected_for_a_held_period_still_short_of_a_member_is_a_failed_retrieval(
    batch_copy: tuple[Path, str],
) -> None:
    # The final plan, member by member, outranks the period held: the 26th lacks a member.
    database, run_id = batch_copy
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER full_run_gap_plan_no_update")
        [(document,)] = connection.execute(
            "SELECT document_json FROM full_run_gap_plan WHERE run_id=? AND phase='final'",
            (run_id,),
        )
        plan = json.loads(document)
        for gap in plan["gaps"]:
            if (gap["metric_id"], gap["period"]) == ("CN_EQ_CSI500", "2026-08-26"):
                gap.update(complete=False, missing_members=["fixture-member"])
        connection.execute(
            "UPDATE full_run_gap_plan SET document_json=? WHERE run_id=? AND phase='final'",
            (json.dumps(plan), run_id),
        )
    url = reject(database, run_id, "CN_EQ_CSI500", "2026-08-26")

    gap = listed(database, run_id)["CN_EQ_CSI500"]

    assert gap["category"] == "retrieval_failed"
    assert gap["candidates"] == [{"url": url, "reason": "period_mismatch"}]


def test_candidate_rejected_for_a_metric_current_adds_no_gap(
    batch_copy: tuple[Path, str],
) -> None:
    database, run_id = batch_copy
    reject(database, run_id, "CN_EQ_CSI300", "2026-08-28")

    assert "CN_EQ_CSI300" not in listed(database, run_id)


def test_unconfigured_p0_blocks_the_run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import pring_cycle.freshness as freshness

    registry = dict(freshness.FRESHNESS_REGISTRY)
    registry.pop("CN_COMMODITY_CORE_NHII")
    monkeypatch.setattr(freshness, "FRESHNESS_REGISTRY", registry)
    paths = runtime(tmp_path)
    seed(paths)

    run_id = run(paths)

    stored = RunRepository(paths.database).get(run_id)
    assert (stored.status, stored.error_classification) == (
        "action_required",
        "p0_freshness_unconfigured",
    )
