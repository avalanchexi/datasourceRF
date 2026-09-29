"""A core one session behind is carried forward; two behind or in conflict holds the stage."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

TARGET = date(2026, 8, 28)
CUTOFF = datetime(2026, 8, 28, 21, tzinfo=ZoneInfo("Asia/Shanghai"))
CORES = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}


def sessions() -> list[date]:
    days: list[date] = []
    day = TARGET
    while len(days) < 180:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return list(reversed(days))


def seed_cores(
    paths: RuntimePaths, *, commodity_missing: int = 0, stock_conflict: bool = False
) -> None:
    """Rising cores for 180 sessions; the commodity core lacks its last ``commodity_missing``."""
    days = sessions()
    seed_independent_calendar(paths, days)
    claims = []
    for index, observed in enumerate(days):
        for asset, metric_id in CORES.items():
            if asset == "commodity" and observed in days[len(days) - commodity_missing :]:
                continue
            api_name, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                claim(
                    metric_id,
                    observed,
                    100.0 + index,
                    unit="index_points",
                    provider="tushare",
                    reference=f"tushare:{api_name}:{code}:{observed}",
                )
            )
    if stock_conflict:
        api_name, code = CORE_API_IDENTITIES[CORES["stock"]]
        claims.append(
            replace(
                claim(
                    CORES["stock"],
                    TARGET,
                    1.0,
                    unit="index_points",
                    provider="official",
                    reference=f"official:{code}:{TARGET}",
                ),
                release_event_id=f"official:{code}:{TARGET}",
            )
        )
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))


def publish(tmp_path: Path, *, commodity_missing: int = 0) -> Any:
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=commodity_missing)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="carry",
        model_version_id="model-v0001",
        system_as_of=CUTOFF,
        cutoff_mode="explicit",
    )
    process_pending_run(paths, report_adapters=())
    stored = RunRepository(paths.database).get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    return paths, ProjectionSetRepository(paths.database).current()


def test_one_session_behind_is_carried_and_flagged(tmp_path: Path) -> None:
    paths, projection = publish(tmp_path, commodity_missing=1)
    overview = projection.datasets["cycle_overview"]
    assets = {item["asset"]: item for item in projection.datasets["core_assets"]["assets"]}
    report = ReportRepository(paths.database).history()[0]

    assert overview["current_stage"] == "stage_iii"
    assert overview["core_carry_forward"] == ["commodity"]
    assert assets["commodity"]["carried_forward"] is True
    assert assets["stock"]["carried_forward"] is False
    assert report.body["core_carry_forward"] == ["commodity"]
    from pring_cycle.dashboard import _home_page

    assert "核心沿用上一期：商品" in str(_home_page(projection))
    held = EvidenceRepository(paths.database).metric_series(
        CORES["commodity"],
        mode=AsOfMode.SYSTEM,
        as_of=datetime.combine(TARGET, time.max, ZoneInfo("Asia/Shanghai")),
        definition_version="metric-catalog-v0001",
    )
    assert held[-1].period_end == (TARGET - timedelta(days=1)).isoformat()


def test_two_sessions_behind_holds_the_stage_but_publishes_the_rest(tmp_path: Path) -> None:
    paths, projection = publish(tmp_path, commodity_missing=2)
    overview = projection.datasets["cycle_overview"]
    report = ReportRepository(paths.database).history()[0]

    assert projection.envelope.target_business_date == TARGET.isoformat()
    assert (overview["current_stage"], overview["stage_reason"]) == (None, "core_data_pending")
    assert projection.datasets["macro"] and projection.datasets["inventory"]
    assert "gap_list" in overview
    assert report.projection_set_id == projection.envelope.projection_set_id
    assert report.current_stage is None
