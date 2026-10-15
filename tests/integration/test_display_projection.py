"""Frozen display facts through the day-summary boundary (ADR-0034)."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.day_summary import RunMaterials
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.trading_calendar import US_TREASURY
from tests.integration.test_confirmation_publish import confirmed
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
from tests.integration.test_day_summary import summaries, target_projection
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_worker_execution import runtime


def test_bond_chart_and_returns_use_real_sessions_and_frozen_versions(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)

    projection = target_projection(paths)
    display: dict[str, Any] = projection.datasets["core_assets"]["display"]["bond"]

    assert display["unit"] == "index_points"
    assert display["frequency"] == "daily"
    points = display["points"]
    assert len(points) == 120
    assert points[0]["date"] == sessions()[60].isoformat()
    assert points[0]["value"] == 160
    assert points[0]["ma120"] is None
    assert points[0]["ma120_reason"] == "insufficient_history"
    assert points[-1]["value"] == 279
    assert points[-1]["ma120"] == 219.5
    assert all(point["observation_id"] and point["selected_claim_id"] for point in points)
    assert display["change_5"]["value"] == pytest.approx(5 / 274 * 100)
    assert display["change_120"]["value"] == pytest.approx(120 / 159 * 100)
    assert display["change_120"]["start_date"] == sessions()[59].isoformat()
    assert display["change_120"]["end_date"] == sessions()[-1].isoformat()
    assert display["change_120"]["unit"] == "percent"
    assert display["change_120"]["kind"] == "return"
    # The first chart point is not the 120-session return's comparison endpoint.
    assert display["change_120"]["start_date"] != points[0]["date"]


def test_carried_close_is_never_drawn_or_used_as_a_return_endpoint(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=1)
    display: dict[str, Any] = target_projection(paths).datasets["core_assets"]["display"][
        "commodity"
    ]
    assert display["latest_date"] == sessions()[-2].isoformat()
    assert display["latest_value"] == 278
    assert display["carried_forward"] is True
    assert display["points"][-1]["value"] is None
    assert display["points"][-1]["selected_claim_id"] is None
    assert display["change_5"]["value"] is None
    assert display["change_120"]["reason"] == "carried_forward"


def test_revision_after_cutoff_cannot_change_chart_or_its_version(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    before = target_projection(paths)
    revision = replace(
        claim(
            "CN_BOND_CORE_000012",
            TARGET,
            999,
            unit="index_points",
            provider="tushare",
            reference=f"tushare:index_daily:000012.SH:{TARGET}",
        ),
        available_at=CUTOFF + timedelta(hours=1),
        fetched_at=CUTOFF + timedelta(hours=1),
    )
    EvidenceRepository(paths.database).append_source_claim(revision)
    after = target_projection(paths)
    assert before.datasets["core_assets"]["display"] == after.datasets["core_assets"]["display"]


def test_global_confirmation_counts_key_indicators_once(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)
    confirmation: Any = projection.datasets["macro"]["confirmation"]
    # Five dimensions contain 17 key indicators: PMI supports; the other 16 lack inputs.
    assert confirmation["summary"] == {
        "counting_unit": "key_indicator",
        "applicable": True,
        "total": 17,
        "counts": {"support": 1, "counterevidence": 0, "observation_only": 0, "unconfirmed": 16},
    }


def test_confirmation_reading_shows_member_unit_instead_of_generic_catalog_unit(
    tmp_path: Path,
) -> None:
    from tests.integration.test_confirmation_monthly_indicators import append
    from tests.integration.test_confirmation_publish import (
        TO_JULY,
        publish,
        register_confirmation_model,
    )

    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths, ("CN_M1_M2",))
    for aggregate in ("m1", "m2"):
        append(
            EvidenceRepository(paths.database),
            "CN_M1_M2",
            {"aggregate": aggregate, "measure": "yoy"},
            (5.0,) * 12,
            months=TO_JULY,
            unit="percent",
            definition_version="metric-catalog-v0001",
        )
    projection = publish(paths, "model-confirmation-fixture")
    confirmation: Any = projection.datasets["macro"]["confirmation"]
    money = next(
        item
        for group in confirmation["dimensions"]
        for item in group["key_indicators"]
        if item["key"] == "money"
    )
    assert money["members"][0]["value"] == 5.0
    assert money["members"][0]["unit"] == "percent"


def test_display_metadata_preserves_low_frequency_catalog_facts(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(paths)
    rows: Any = projection.datasets["macro"]["international_context"]
    gdp = next(item for item in rows if item["metric_id"] == "CN_GDP")
    vix = next(item for item in rows if item["metric_id"] == "CBOE_VIX_INDEX")
    assert gdp["frequency"] == "quarterly"
    assert vix["frequency"] == "daily"
    assert gdp["period"] is None and gdp["value"] is None
    assert gdp["name_cn"]


def test_stage_bands_keep_unpublished_calendar_slots(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    result = (
        summaries(paths)
        .summarize_target(
            TARGET.isoformat(),
            system_as_of=CUTOFF,
            run_materials=RunMaterials(),
            backfill_window=tuple(day.isoformat() for day in sessions()[-3:]),
        )
        .result
    )
    projection = ProjectionSetRepository(paths.database).get(str(result.projection_set_id))
    display: Any = projection.datasets["stage_history"]["display"]
    assert len(display["days"]) == 120
    assert display["days"][0]["date"] == sessions()[60].isoformat()
    assert display["days"][0]["official"] == "unpublished"
    assert display["days"][-1]["official"] == "stage_iii"
    assert display["days"][-1]["bond"] == "bull"
    assert display["days"][-1]["stock"] == "bull"
    assert display["days"][-1]["commodity"] == "bull"
    assert display["counts"] == {"unpublished": 117, "stage_iii": 3}


def test_treasury_change_is_basis_points_on_its_own_sessions(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    days = []
    day = TARGET
    while len(days) < 125:
        if US_TREASURY.is_trading(day):
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    evidence = EvidenceRepository(paths.database)
    for index, day in enumerate(days):
        evidence.append_source_claim(
            claim(
                "UST10Y_NOMINAL_YIELD",
                day,
                4 + index / 100,
                unit="percent",
                provider="treasury",
                reference=f"treasury:{day}",
            )
        )
    projection = target_projection(paths)
    rows: Any = projection.datasets["macro"]["international_context"]
    display = next(row["display"] for row in rows if row["metric_id"] == "UST10Y_NOMINAL_YIELD")
    assert display["change_5"]["value"] == pytest.approx(5)
    assert display["change_120"]["value"] == pytest.approx(120)
    assert display["change_5"]["unit"] == "basis_points"
    assert display["change_120"]["start_date"] == days[4].isoformat()
    assert len(display["points"]) == 120
    frozen = evidence.frozen_versions(projection.envelope.evidence_snapshot_id)
    assert set(display["change_120"]["input_claim_ids"]) <= set(frozen)
    gdp = next(row["display"] for row in rows if row["metric_id"] == "CN_GDP")
    assert gdp["change_5"]["reason"] == "not_daily"


def test_coverage_keeps_model_gaps_and_catalog_waiting_distinct(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    projection = target_projection(
        paths,
        RunMaterials(
            plan_gaps=(
                {"metric_id": "CN_BOND_CORE_000012", "period": "2026-08-28", "complete": True},
                {
                    "metric_id": "CN_EQUITY_CORE_000985",
                    "period": "2026-08-28",
                    "complete": False,
                    "missing_members": ["close"],
                },
                {
                    "metric_id": "CN_GDP",
                    "period": "2026-Q3",
                    "complete": False,
                    "release_gate": "awaiting_release",
                },
            )
        ),
    )
    coverage: Any = projection.datasets["macro"]["coverage"]
    assert coverage["counting_unit"] == "required_metric_period"
    assert coverage["model"]["total"] == 2
    assert coverage["model"]["counts"] == {"held": 1, "missing": 1}
    assert coverage["catalog"]["total"] == 3
    assert coverage["catalog"]["counts"] == {"held": 1, "missing": 1, "release_gated": 1}
    assert coverage["model"]["periods"][1]["missing_members"] == ["close"]


def test_one_missing_core_day_keeps_the_other_observed_prices_visible(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    missing = sessions()[-10]
    seed_cores(paths, stock_gap=missing)
    projection = target_projection(paths)
    display: Any = projection.datasets["core_assets"]["display"]["stock"]
    assert projection.datasets["cycle_overview"]["current_stage"] is None
    assert display["latest_value"] == 279
    assert sum(point["value"] is not None for point in display["points"]) == 119
    assert (
        next(point for point in display["points"] if point["date"] == missing.isoformat())["value"]
        is None
    )
    assert display["change_120"]["value"] is None
    assert display["change_5"]["value"] == pytest.approx(5 / 274 * 100)
