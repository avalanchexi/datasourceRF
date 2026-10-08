from __future__ import annotations

import calendar
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.context_projection import build_context_projection
from pring_cycle.dashboard import _gap_list
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.freshness import add_projection_gaps
from pring_cycle.models import analytical_model_v0002_manifest


def append_input(
    repository: EvidenceRepository,
    metric_id: str,
    period: str,
    value: float,
    *,
    start: str | None = None,
    dimensions: dict[str, str] | None = None,
    unit: str = "percent",
    period_kind: str = "business_day",
    timestamp: datetime = datetime(2026, 8, 28, 10, tzinfo=UTC),
) -> str:
    return repository.append_source_claim(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version="metric-catalog-v0003",
            period_kind=period_kind,
            period_start=start or period,
            period_end=period,
            dimensions=dimensions or {},
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=unit,
            provider="isolated_fixture",
            source_reference=f"fixture:{metric_id}:{period}:{dimensions}",
            release_event_id=f"fixture:{metric_id}:{period}:{dimensions}",
            release_at=timestamp,
            public_available_at=timestamp,
            fetched_at=timestamp,
            available_at=timestamp,
            certification_status="certified",
            quality_status="validated",
        )
    ).claim_id


def fixture_manifest() -> dict[str, object]:
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    return manifest


def documents(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        return [value, *(row for child in value.values() for row in documents(child))]
    if isinstance(value, list):
        return [row for child in value for row in documents(child)]
    return []


@pytest.mark.parametrize("period,status", [("2026-08-28", "current"), ("2025-08-28", "stale")])
def test_treasury_spread_retains_old_value_without_adopting_it_as_current(
    tmp_path: Path, period: str, status: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    inputs = {
        append_input(repository, "UST2Y_NOMINAL_YIELD", period, 4.34),
        append_input(repository, "UST10Y_NOMINAL_YIELD", period, 4.73),
    }
    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    context = build_context_projection(
        repository, as_of=cutoff, model_manifest=fixture_manifest(), as_of_mode=AsOfMode.PUBLIC
    )
    rows = cast(list[dict[str, object]], context.macro["international_context"])
    spread = next(row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD")
    assert spread["value"] == pytest.approx(39.0)
    assert spread["period"] == period
    assert spread["status"] == status
    derived_id = str(spread["derived_observation_id"])
    trace = repository.derived_trace(derived_id, mode=AsOfMode.PUBLIC, as_of=cutoff)
    assert set(trace.input_observation_version_ids) == inputs
    assert inputs | {derived_id} <= set(context.observation_version_ids)
    adopted = set(cast(list[str], context.macro["model_input_observation_version_ids"]))
    if status == "stale":
        assert not (inputs | {derived_id}) & adopted
    else:
        assert inputs | {derived_id} <= adopted


@pytest.mark.parametrize("year,status", [(2026, "current"), (2025, "stale")])
@pytest.mark.parametrize(
    "family,formula,expected",
    [
        ("dr007", "dr007-policy-spread-v0001", 70.0),
        ("pmi", "pmi-order-inventory-spread-v0001", 4.0),
        ("pmi", "pmi-production-order-spread-v0001", -1.0),
        ("loan", "loan-stock-monthly-change-v0001", 10.0),
        ("omo", "repo-net-injection-v0001", 500.0),
        ("omo", "repo-net-injection-trading-calendar-v0002", 500.0),
    ],
)
def test_macro_derivation_cannot_refresh_old_terminal_periods(
    tmp_path: Path, year: int, status: str, family: str, formula: str, expected: float
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    manifest = fixture_manifest()
    formulas = cast(dict[str, str], manifest["derived_formula_versions"])
    if family == "dr007":
        append_input(repository, "CN_DR007", f"{year}-08-28", 2.2)
        # An earlier effective policy rate is not the daily spread's terminal period.
        append_input(repository, "CN_OMO_7D_RATE", "2024-08-28", 1.5)
    elif family == "pmi":
        formulas["order_inventory_spread"] = "pmi-order-inventory-spread-v0001"
        formulas["production_order_spread"] = "pmi-production-order-spread-v0001"
        for metric, series, value in (
            ("CN_PMI_ACTIVITY", "new_orders", 52.0),
            ("CN_PMI_ACTIVITY", "production", 51.0),
            ("CN_PMI_INVENTORY", "finished_goods", 48.0),
        ):
            append_input(
                repository,
                metric,
                f"{year}-07-31",
                value,
                start=f"{year}-07-01",
                dimensions={"series": series, "measure": "level"},
                unit="diffusion_index_points",
                period_kind="month",
            )
    elif family == "loan":
        for month, day, value in ((6, 30, 100.0), (7, 31, 110.0)):
            append_input(
                repository,
                "CN_LOAN_STRUCTURE",
                f"{year}-{month:02d}-{day}",
                value,
                start=f"{year}-{month:02d}-01",
                dimensions={"borrower": "enterprise", "tenor": "long_term", "measure": "stock_end"},
                unit="hundred_million_cny",
                period_kind="month",
            )
    else:
        formulas["omo_net_injection"] = formula
        for measure, value in (("injection", 3000.0), ("maturity", 2500.0)):
            append_input(
                repository,
                "CN_OMO_7D_AMOUNT",
                f"{year}-08-28",
                value,
                dimensions={"measure": measure},
                unit="hundred_million_cny",
            )
    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    context = build_context_projection(
        repository, as_of=cutoff, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    derived = [
        row
        for row in documents(context.macro) + documents(context.inventory)
        if row.get("formula_version") == formula and "derived_observation_id" in row
    ]
    assert derived
    adopted = set(cast(list[str], context.macro["model_input_observation_version_ids"]))
    for row in derived:
        assert row["value"] == pytest.approx(expected)
        assert str(row["period"]).startswith(str(year))
        assert row["status"] == status
        derived_id = str(row["derived_observation_id"])
        trace = repository.derived_trace(derived_id, mode=AsOfMode.PUBLIC, as_of=cutoff)
        assert trace.input_observation_version_ids
        assert derived_id in context.observation_version_ids
        assert (derived_id in adopted) == (status == "current")


@pytest.mark.parametrize("mode", [AsOfMode.PUBLIC, AsOfMode.SYSTEM])
@pytest.mark.parametrize(
    "social_start_year,gdp_start_year,status",
    [(2024, 2024, "current"), (2023, 2024, "stale"), (2024, 2023, "stale")],
)
def test_credit_impulse_checks_both_terminal_periods_without_rejecting_preheat(
    tmp_path: Path, mode: AsOfMode, social_start_year: int, gdp_start_year: int, status: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for metric, first_year, count, step in (
        ("CN_SF_TOTAL", social_start_year, 24, 1),
        ("CN_GDP", gdp_start_year, 8, 3),
    ):
        for index in range(count):
            year, month0 = divmod(first_year * 12 + 6 + index * step, 12)
            end_month = month0 + step
            is_gdp = metric == "CN_GDP"
            append_input(
                repository,
                metric,
                f"{year}-{end_month:02d}-{calendar.monthrange(year, end_month)[1]}",
                (25.0 if index < 4 else 30.0) if is_gdp else (2.0 if index < 12 else 3.0),
                start=f"{year}-{month0 + 1:02d}-01",
                dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"}
                if is_gdp
                else {"measure": "monthly_increment"},
                unit="hundred_million_cny",
                period_kind="quarter" if is_gdp else "month",
                timestamp=datetime(2026, 7, 20, 10, tzinfo=UTC),
            )
    # June social financing and Q2 GDP are both the latest released periods here.
    cutoff = datetime(2026, 7, 20, 12, tzinfo=UTC)
    context = build_context_projection(
        repository, as_of=cutoff, model_manifest=fixture_manifest(), as_of_mode=mode
    )
    credit = cast(dict[str, object], context.macro["credit"])
    rows = cast(list[dict[str, object]], credit["evidence"])
    impulse = next(row for row in rows if row["metric_id"] == "CN_CREDIT_IMPULSE")
    formula = cast(dict[str, object], credit["formula"])
    # Worked example: 36/120 - 24/100 = 0.06, or 6 percentage points.
    assert impulse["value"] == pytest.approx(6.0)
    assert impulse["status"] == status
    assert formula["status"] == ("available" if status == "current" else "stale_inputs")
    assert impulse["period"] == f"{social_start_year + 2}-06-30"
    assert formula["gdp_window"] == [f"{gdp_start_year}-07-01", f"{gdp_start_year + 2}-06-30"]
    derived_id = str(impulse["derived_observation_id"])
    trace = repository.derived_trace(derived_id, mode=mode, as_of=cutoff)
    assert len(trace.input_observation_version_ids) == 32
    assert derived_id in context.observation_version_ids
    adopted = set(cast(list[str], context.macro["model_input_observation_version_ids"]))
    assert (derived_id in adopted) == (status == "current")
    overheat = cast(dict[str, object], context.macro["overheat"])
    support = cast(list[dict[str, object]], overheat["support"])
    gaps = cast(list[dict[str, object]], overheat["gaps"])
    assert (derived_id in {str(row["observation_id"]) for row in support}) == (status == "current")
    assert (derived_id in {str(row["observation_id"]) for row in gaps}) == (status == "stale")


_CREDIT_REQUIREMENT = {
    "metric_id": "CN_CREDIT_IMPULSE",
    "formula_version": "credit-impulse-ytd-flow-v0002",
    "required_input_periods": {"CN_SF_TOTAL": 25, "CN_GDP": 9},
}


def _credit_documents(formula_status: str, sf_status: str = "current") -> tuple[object, ...]:
    """The shapes a macro projection carries: evidence rows and the formula document."""
    sf_row = {
        "metric_id": "CN_SF_TOTAL",
        "period": "2026-08-31",
        "dimensions": {"measure": "ytd_increment"},
        "status": sf_status,
        "claims": [{"metric_id": "CN_SF_TOTAL", "status": "conflicted"}],
        **({"conflict_reason": "unit_scale_mismatch"} if sf_status == "conflicted" else {}),
    }
    macro = {
        "credit": {
            "evidence": [sf_row, {"metric_id": "CN_CREDIT_IMPULSE", "status": "missing"}],
            "formula": {
                "metric_id": "CN_CREDIT_IMPULSE",
                "formula_version": "credit-impulse-ytd-flow-v0002",
                "formula": "100 * (...)",
                "status": formula_status,
            },
        },
        # The same row shown again under another card is one gap.
        "overheat": {"evidence": [sf_row]},
    }
    inventory = {
        "real_inventory_approximation": {
            "formula_version": "inventory-ppi-common-month-v0002",
            "formula": "nominal / (1 + ppi / 100)",
            "status": "available",
        }
    }
    return macro, inventory


def test_a_formula_missing_inputs_is_a_gap_naming_the_parent_periods() -> None:
    """Freshness follows the parents: a formula that never computes looked current (#09)."""
    gaps = add_projection_gaps(
        (),
        _credit_documents("missing_inputs"),
        derived_requirements=(
            _CREDIT_REQUIREMENT,
            {
                "metric_id": "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
                "required_input_periods": {"CN_FINISHED_GOODS_INVENTORY": 1, "CN_PPI": 1},
            },
            # A change of the metric's own series is shown with its own rows.
            {"metric_id": "CN_LOAN_STRUCTURE", "required_input_periods": {"CN_LOAN_STRUCTURE": 2}},
        ),
        plan_gaps=(
            {
                "complete": False,
                "metric_id": "CN_SF_TOTAL",
                "period": "2024-08",
                "missing_members": ['CN_SF_TOTAL:{"measure": "ytd_increment"}'],
            },
            {"complete": True, "metric_id": "CN_SF_TOTAL", "period": "2024-09"},
            {"complete": False, "metric_id": "CN_PPI", "period": "2026-08"},
        ),
        definitions=metric_catalog_v0003(),
    )

    (gap,) = gaps
    assert gap["metric_id"] == "CN_CREDIT_IMPULSE"
    assert gap["category"] == "derived_failed"
    assert gap["reason"] == gap["formula_status"] == "missing_inputs"
    assert gap["missing_inputs"] == [
        {
            "metric_id": "CN_SF_TOTAL",
            "period": "2024-08",
            "missing_members": ['CN_SF_TOTAL:{"measure": "ytd_increment"}'],
        }
    ]


def test_a_conflicted_metric_is_one_gap_listing_each_conflict() -> None:
    gaps = add_projection_gaps(
        (),
        _credit_documents("available", sf_status="conflicted"),
        derived_requirements=(_CREDIT_REQUIREMENT,),
        plan_gaps=(),
        definitions=metric_catalog_v0003(),
    )

    (gap,) = gaps
    assert gap["metric_id"] == "CN_SF_TOTAL"
    assert gap["category"] == "source_conflict"
    assert gap["reason"] == "unit_scale_mismatch"
    assert gap["held_period"] == "2026-08-31"
    assert gap["conflicts"] == [
        {
            "period": "2026-08-31",
            "dimensions": {"measure": "ytd_increment"},
            "reason": "unit_scale_mismatch",
        }
    ]


def test_a_metric_already_listed_keeps_one_row_with_what_the_projection_adds() -> None:
    listed = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "priority": "P1",
        "category": "missing",
        "reason": "not_held",
        "due_period": "2026-08-31",
        "held_period": None,
        "periods_behind": None,
        "no_web_fallback": True,
    }

    gaps = add_projection_gaps(
        (listed,),
        _credit_documents("missing_inputs"),
        derived_requirements=(_CREDIT_REQUIREMENT,),
        plan_gaps=(),
        definitions=metric_catalog_v0003(),
    )

    (gap,) = gaps
    assert gap["category"] == "missing" and gap["reason"] == "not_held"
    assert gap["formula_status"] == "missing_inputs"
    assert gap["missing_inputs"] == []


def test_only_a_refused_claim_is_a_source_failure_shown_on_its_listed_gap() -> None:
    """A failed fetch hides no conflict and stays out; a refused claim joins its gap (#09)."""
    listed = {
        "metric_id": "CN_SF_TOTAL",
        "priority": "P1",
        "category": "freshness_gap",
        "reason": "one_period_behind_carried",
        "due_period": "2026-09-30",
        "held_period": "2026-08-31",
        "periods_behind": 1,
        "no_web_fallback": False,
    }
    refused = {
        "metric_id": "CN_SF_TOTAL",
        "period": "2026-08-31",
        "dimensions": {"measure": "ytd_increment"},
        "status": "source_failed",
        "source_failure": "not_adoptable",
    }
    fetch_failed = {"metric_id": "CN_LPR_1Y_5Y", "status": "source_failed", "dimensions": {}}

    gaps = add_projection_gaps(
        (listed,),
        ({"credit": {"evidence": [refused, fetch_failed]}},),
        derived_requirements=(),
        plan_gaps=(),
        definitions=metric_catalog_v0003(),
    )

    (gap,) = gaps
    assert gap["category"] == "freshness_gap" and gap["held_period"] == "2026-08-31"
    assert gap["source_failures"] == [
        {
            "period": "2026-08-31",
            "dimensions": {"measure": "ytd_increment"},
            "reason": "not_adoptable",
        }
    ]
    assert "conflicts" not in gap
    page = str(_gap_list(gaps))
    assert "时效缺口（1）" in page and "来源复核失败" in page and "来源同时冲突" not in page


def test_a_computed_formula_leaves_no_gap() -> None:
    assert (
        add_projection_gaps(
            (),
            _credit_documents("available"),
            derived_requirements=(_CREDIT_REQUIREMENT,),
            plan_gaps=(),
            definitions=metric_catalog_v0003(),
        )
        == []
    )


def test_stale_inputs_computed_the_formula_and_only_annotate_its_timeliness() -> None:
    """Stale inputs still compute; timeliness says they are stale, not a failure (#27)."""
    assert (
        add_projection_gaps(
            (),
            _credit_documents("stale_inputs"),
            derived_requirements=(_CREDIT_REQUIREMENT,),
            plan_gaps=(),
            definitions=metric_catalog_v0003(),
        )
        == []
    )
    listed = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "priority": "P1",
        "category": "freshness_gap",
        "reason": "one_period_behind_carried",
        "due_period": "2026-08-31",
        "held_period": "2026-07-31",
        "periods_behind": 1,
        "no_web_fallback": True,
    }

    (gap,) = add_projection_gaps(
        (listed,),
        _credit_documents("stale_inputs"),
        derived_requirements=(_CREDIT_REQUIREMENT,),
        plan_gaps=(),
        definitions=metric_catalog_v0003(),
    )

    assert gap == {**listed, "formula_status": "stale_inputs"}


def test_a_failed_credit_impulse_lists_only_what_the_formula_could_not_read() -> None:
    """The formula's own failures, not every unfinished member of its parents (#28)."""
    macro, inventory = _credit_documents("incomparable_gdp_vintages")
    formula = cast(dict[str, object], cast(dict[str, object], macro)["credit"])["formula"]
    gdp_ytd = 'CN_GDP:{"aggregate": "total", "measure": "nominal_ytd_level"}'
    cast(dict[str, object], formula)["failures"] = [
        {
            "metric_id": "CN_GDP",
            "reason": "incomparable_gdp_vintages",
            "periods": ["2025-Q2", "2025-Q3"],
            "members": [gdp_ytd],
        }
    ]

    (gap,) = add_projection_gaps(
        (),
        (macro, inventory),
        derived_requirements=(_CREDIT_REQUIREMENT,),
        # GDP's year-on-year growth is a member the formula does not read.
        plan_gaps=(
            {
                "complete": False,
                "metric_id": "CN_GDP",
                "period": "2026-Q2",
                "missing_members": ['CN_GDP:{"measure": "yoy"}'],
            },
        ),
        definitions=metric_catalog_v0003(),
    )

    assert gap["category"] == "derived_failed"
    assert gap["missing_inputs"] == [
        {
            "metric_id": "CN_GDP",
            "period": period,
            "missing_members": [gdp_ytd],
            "reason": "incomparable_gdp_vintages",
        }
        for period in ("2025-Q2", "2025-Q3")
    ]


def test_a_parent_held_not_at_all_takes_its_periods_from_the_plan() -> None:
    """Nothing held names no period; the plan's do, with the members the formula reads."""
    macro, inventory = _credit_documents("missing_inputs")
    formula = cast(dict[str, object], cast(dict[str, object], macro)["credit"])["formula"]
    sf_ytd = 'CN_SF_TOTAL:{"measure": "ytd_increment"}'
    cast(dict[str, object], formula)["failures"] = [
        {
            "metric_id": "CN_SF_TOTAL",
            "reason": "missing_periods",
            "periods": [],
            "members": [sf_ytd],
        }
    ]

    (gap,) = add_projection_gaps(
        (),
        (macro, inventory),
        derived_requirements=(_CREDIT_REQUIREMENT,),
        plan_gaps=(
            {
                "complete": False,
                "metric_id": "CN_SF_TOTAL",
                "period": "2024-08",
                "missing_members": [sf_ytd, 'CN_SF_TOTAL:{"measure": "month_end_stock"}'],
            },
            # Only a member the formula does not read.
            {
                "complete": False,
                "metric_id": "CN_SF_TOTAL",
                "period": "2024-09",
                "missing_members": ['CN_SF_TOTAL:{"measure": "month_end_stock"}'],
            },
        ),
        definitions=metric_catalog_v0003(),
    )

    assert gap["missing_inputs"] == [
        {
            "metric_id": "CN_SF_TOTAL",
            "period": "2024-08",
            "missing_members": [sf_ytd],
            "reason": "missing_periods",
        }
    ]


def test_a_period_the_release_gate_kept_from_being_requested_is_listed_with_why() -> None:
    """Lookback L01: a history period planned and never requested was skipped silently.
    Each such period is named on its metric's gap with the gate's reason, a metric listed
    for another reason keeping its row."""
    listed = {
        "metric_id": "CN_PPI",
        "priority": "P1",
        "category": "freshness_gap",
        "reason": "one_period_behind_carried",
        "due_period": "2026-08-31",
        "held_period": "2026-07-31",
        "periods_behind": 1,
        "no_web_fallback": False,
    }

    gaps = add_projection_gaps(
        (listed,),
        (),
        derived_requirements=(),
        plan_gaps=(
            {
                "complete": False,
                "metric_id": "CN_DR007",
                "period": "2026-08-24",
                "release_gate": "earlier_session_not_searched",
            },
            {"complete": False, "metric_id": "CN_DR007", "period": "2026-08-25"},
            {
                "complete": False,
                "metric_id": "CN_DR007",
                "period": "2026-08-21",
                "release_gate": "earlier_session_not_searched",
            },
            {
                "complete": False,
                "metric_id": "CN_PPI",
                "period": "2025-08",
                "release_gate": "unknown_release_configuration",
            },
            # Complete after all: nothing is owed.
            {
                "complete": True,
                "metric_id": "CN_M1_M2",
                "period": "2026-07",
                "release_gate": "unknown_release_configuration",
            },
        ),
        definitions=metric_catalog_v0003(),
    )

    by_metric = {gap["metric_id"]: gap for gap in gaps}
    assert set(by_metric) == {"CN_DR007", "CN_PPI"}
    dr007 = by_metric["CN_DR007"]
    assert (dr007["category"], dr007["reason"]) == ("missing", "period_not_requested")
    assert dr007["not_requested"] == [
        {"period": "2026-08-24", "reason": "earlier_session_not_searched"},
        {"period": "2026-08-21", "reason": "earlier_session_not_searched"},
    ]
    ppi = by_metric["CN_PPI"]
    assert (ppi["category"], ppi["reason"]) == ("freshness_gap", "one_period_behind_carried")
    assert ppi["not_requested"] == [
        {"period": "2025-08", "reason": "unknown_release_configuration"}
    ]
    page = str(_gap_list(gaps))
    assert "未请求 2 期 2026-08-21 至 2026-08-24（较早交易日不逐日检索）" in page
    assert "未请求 2025-08（发布规则未登记）" in page


def test_a_period_its_listing_was_not_read_back_to_is_listed_as_not_covered() -> None:
    """Lookback L05: 100 OMO days not on the listing pages read were left as if the column
    had nothing for them. Each is named on its metric as not covered, not as "none"."""
    gaps = add_projection_gaps(
        (),
        (),
        derived_requirements=(),
        plan_gaps=(
            *(
                {
                    "complete": False,
                    "metric_id": "CN_OMO_7D_AMOUNT",
                    "period": period,
                    "official_listing": "listing_not_covered",
                }
                for period in ("2026-04-09", "2026-08-31", "2026-06-01")
            ),
            # Found by search after the listing stopped: nothing is owed.
            {
                "complete": True,
                "metric_id": "CN_INDUSTRIAL_PROFIT",
                "period": "2026-02",
                "official_listing": "listing_not_covered",
            },
        ),
        definitions=metric_catalog_v0003(),
    )

    (omo,) = gaps
    assert (omo["metric_id"], omo["category"], omo["reason"]) == (
        "CN_OMO_7D_AMOUNT",
        "missing",
        "listing_not_covered",
    )
    assert [item["period"] for item in omo["not_covered"]] == [
        "2026-04-09",
        "2026-08-31",
        "2026-06-01",
    ]
    page = str(_gap_list(gaps))
    assert "列表未覆盖 3 期 2026-04-09 至 2026-08-31" in page
    assert "无操作" not in page
