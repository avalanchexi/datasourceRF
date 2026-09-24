"""Gate ①: one visible gap list per batch, and the P1/P2 freshness disposition behind it."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import EvidenceRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.integration.test_decertified_main_chain import claim, rows_for
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

TARGET = date(2026, 8, 28)
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


def run(paths: RuntimePaths) -> str:
    submitted = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
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
    # Index closes and money-market rates come from TuShare alone: no page to search.
    assert gaps["CN_EQ_CSI1000"]["category"] == "no_searchable_source"
    assert gaps["CN_EQ_CSI1000"]["reason"] == "two_or_more_periods_behind"
    assert gaps["CN_SHIBOR_ON_1W_3M"]["category"] == "no_searchable_source"
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


def test_one_period_behind_is_used_and_two_behind_is_not(
    published: tuple[RuntimePaths, Any],
) -> None:
    _paths, projection = published

    bond = next(rows_for(projection.datasets, "CN_BOND_10Y_930916"))
    dr007 = next(rows_for(projection.datasets, "CN_DR007"))

    assert (bond["status"], bond["period"]) == ("current", "2026-08-26")
    assert dr007["status"] == "stale"


def test_p1_gaps_do_not_withhold_the_formal_stage(published: tuple[RuntimePaths, Any]) -> None:
    _paths, projection = published

    assert projection.datasets["cycle_overview"]["current_stage"] is not None


def test_page_and_report_show_the_same_gap_list(published: tuple[RuntimePaths, Any]) -> None:
    paths, projection = published
    from pring_cycle.dashboard import _home_page

    report = ReportRepository(paths.database).history()[0]
    page = str(_home_page(projection))

    assert report.body["gap_list"] == projection.datasets["cycle_overview"]["gap_list"]
    for label in ("缺口清单", "无可检索来源", "时效缺口", "未配置时效", "CN_EQ_CSI500"):
        assert label in page


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
