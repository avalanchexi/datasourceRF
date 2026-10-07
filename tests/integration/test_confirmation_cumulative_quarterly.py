"""Cumulative and quarterly key indicators against each stage's cells (ADR-0037, ticket 07).

Loans read the month's flow of enterprise long-term loans, differenced from year-to-date
totals, against the same month a year before: more or less (t, t-1, t-12 and t-13).
Industrial profits read the official cumulative growth quickening or slowing, said to be
cumulative, never a monthly growth computed from cumulative profits. GDP and capacity
utilisation read four quarters for level, momentum and slope, the year's range of a
quarterly indicator its four quarters; capacity utilisation's momentum is its official
change on the same quarter a year before. A quarter's grace is one.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import TWELVE_MONTH_CREDIT_IMPULSE
from pring_cycle.reports import report_input_from_projection
from tests.integration.test_confirmation_monthly_indicators import (
    AS_OF,
    METRICS,
    TARGET,
    append,
    indicator,
)
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_confirmation_publish import confirmed
from tests.integration.test_context_projection import _v2_manifest
from tests.web.test_dashboard_contract import _text

NEW_METRICS = ("CN_LOAN_STRUCTURE", "CN_INDUSTRIAL_FINANCE", "CN_GDP", "CN_CAPACITY_UTILIZATION")
AMOUNT = "hundred_million_cny"
# The newest month out, the one before, and both a year before them.
ENDPOINTS = ("2025-07", "2025-08", "2026-07", "2026-08")
LOAN_PAIRS = (
    ("enterprise", "long_term"),
    ("household", "total"),
    ("household", "short_term"),
    ("household", "long_term"),
    ("enterprise", "total"),
    ("enterprise", "short_term"),
    ("enterprise", "bill_financing"),
    ("nonbank_financial", "total"),
    ("all_rmb_loans", "total"),
)
# Five quarters to the second of 2026: the four read and the one before them, which the
# quarter before the newest reads for its own year.
QUARTERS = ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")
GDP = {"aggregate": "total", "measure": "real_quarter_yoy"}
GDP_NOMINAL = {"aggregate": "total", "measure": "nominal_ytd_level"}
CAPACITY = {"industry": "all_industry", "measure": "quarter_rate"}
CAPACITY_CHANGE = {"industry": "all_industry", "measure": "yoy_change"}
PROFIT = {"item": "profit", "measure": "official_yoy"}
# A year of months to July, the newest industrial profits out on the target day.
TO_JULY = tuple(f"{2025 + (7 + i) // 12}-{(7 + i) % 12 + 1:02d}" for i in range(12))


def manifest() -> dict[str, Any]:
    return confirmation_manifest(_v2_manifest(*METRICS, *NEW_METRICS))


def project(repository: EvidenceRepository, stage: FormalStage | None) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
    )


def loan(borrower: str, tenor: str) -> dict[str, str]:
    return {"borrower": borrower, "tenor": tenor, "measure": "ytd_increment"}


def seed_loans(
    repository: EvidenceRepository,
    totals: tuple[float | None, ...],
    *,
    others: dict[tuple[str, str], tuple[float | None, ...]] | None = None,
) -> list[str]:
    """Year-to-date totals at the four endpoints, oldest first, of enterprise long-term
    loans; every other pair alike unless given its own. Returns the main member's claims."""
    claims: list[str] = []
    for pair in LOAN_PAIRS:
        own = (others or {}).get(pair, totals)
        made = append(
            repository, "CN_LOAN_STRUCTURE", loan(*pair), own, months=ENDPOINTS, unit=AMOUNT
        )
        if pair == LOAN_PAIRS[0]:
            claims = made
    return claims


def quarter(
    repository: EvidenceRepository,
    metric_id: str,
    dimensions: dict[str, str],
    values: tuple[float | None, ...],
    *,
    unit: str = "percent",
) -> list[str]:
    """One member's values for the five quarters, oldest first; None leaves one out."""
    claims = []
    for end, value in zip(QUARTERS, values, strict=True):
        if value is None:
            continue
        start = f"{end[:5]}{int(end[5:7]) - 2:02d}-01"
        public = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(days=20)
        claims.append(
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0002",
                    period_kind="quarter",
                    period_start=start,
                    period_end=end,
                    dimensions=dimensions,
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=unit,
                    provider="certified-fixture",
                    source_reference=f"fixture:{metric_id}:{sorted(dimensions.items())}:{end}",
                    release_event_id=f"release:{metric_id}:{end}",
                    release_at=public,
                    public_available_at=public,
                    fetched_at=public,
                    available_at=public,
                    certification_status="certified",
                    quality_status="validated",
                )
            ).claim_id
        )
    return claims


def seed_profit(
    repository: EvidenceRepository,
    values: tuple[float | None, ...],
    *,
    months: tuple[str, ...] = TO_JULY,
) -> None:
    """Profits', revenue's and cost's official cumulative growth alike; no January."""
    own = tuple(
        None if month.endswith("-01") else value
        for month, value in zip(months, values, strict=True)
    )
    for item in ("profit", "revenue", "cost"):
        append(
            repository,
            "CN_INDUSTRIAL_FINANCE",
            {"item": item, "measure": "official_yoy"},
            own,
            months=months,
        )


def read(tmp_path: Path, stage: FormalStage, key: str, **seeded: Any) -> dict[str, Any]:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    if "loans" in seeded:
        seed_loans(repository, seeded["loans"], others=seeded.get("others"))
    if "profit" in seeded:
        seed_profit(repository, seeded["profit"])
    if "gdp" in seeded:
        quarter(repository, "CN_GDP", GDP, seeded["gdp"])
    if "capacity" in seeded:
        rate, change = seeded["capacity"]
        quarter(repository, "CN_CAPACITY_UTILIZATION", CAPACITY, rate)
        quarter(
            repository, "CN_CAPACITY_UTILIZATION", CAPACITY_CHANGE, change, unit="percentage_points"
        )
    return indicator(project(repository, stage), key)


# August 2025's flow 150 (1150 - 1000), August 2026's 200 (1100 - 900): 50 more.
MORE = (1000.0, 1150.0, 900.0, 1100.0)
# 150 against 100 (1000 - 900): 50 less.
LESS = (1000.0, 1150.0, 900.0, 1000.0)
SAME = (1000.0, 1150.0, 900.0, 1050.0)


@pytest.mark.parametrize(
    ("stage", "totals", "relation", "direction"),
    [
        # Stage III expects more, stage I less; stage IV either more or as much.
        (FormalStage.STAGE_III, MORE, "support", "up"),
        (FormalStage.STAGE_I, LESS, "support", "down"),
        (FormalStage.STAGE_IV, SAME, "support", "flat"),
        (FormalStage.STAGE_VI, MORE, "observation_only", "up"),
    ],
)
def test_loans_read_the_month_s_flow_more_or_less_than_a_year_before(
    tmp_path: Path,
    stage: FormalStage,
    totals: tuple[float, ...],
    relation: str,
    direction: str,
) -> None:
    item = read(tmp_path, stage, "loans", loans=totals)

    assert item["relation"] == relation
    assert item["dimension"] == "credit" and item["timing"] == "leading"
    main = item["members"][0]
    assert main["formula_version"] == "loan-monthly-increment-yoy-change-v0001"
    assert main["member"] == loan("enterprise", "long_term")
    assert main["direction"] == direction and main["agrees_by"] == "sign"
    assert main["values"] == pytest.approx([{"up": 50.0, "down": -50.0, "flat": 0.0}[direction]])
    assert main["periods"] == ["2026-08-31"] and item["statistical_period"] == "2026-08-31"
    # Every other tenor and borrower alike agrees.
    assert {member["consistency"] for member in item["members"][1:]} == {"agrees"}


@pytest.mark.parametrize(("missing", "month"), [(1, "2026-07"), (2, "2025-08"), (3, "2025-07")])
def test_loans_missing_an_endpoint_are_unconfirmed_and_name_it(
    tmp_path: Path, missing: int, month: str
) -> None:
    totals: list[float | None] = list(MORE)
    totals[3 - missing] = None

    item = read(tmp_path, FormalStage.STAGE_III, "loans", loans=tuple(totals))

    assert item["relation"] == "unconfirmed"
    assert item["missing"] == [f"borrower=enterprise,measure=ytd_increment,tenor=long_term:{month}"]


def test_loans_due_and_not_held_name_the_month_not_the_one_before(tmp_path: Path) -> None:
    # On 20 October August's loans are due; July's are held, August's not. August is read,
    # missing its own totals, never July passed off in its place.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_loans(repository, (*MORE[:3], None))
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 10, 20, 12, tzinfo=UTC),
        target_business_date="2026-10-20",
        visible_evidence_start="2026-05-01",
        model_manifest=manifest(),
        formal_stage=StageResult(
            FormalStage.STAGE_III, FormalStage.STAGE_III, "canonical_combination"
        ),
    )

    item = indicator(context, "loans")
    assert item["relation"] == "unconfirmed"
    assert item["missing"] == ["borrower=enterprise,measure=ytd_increment,tenor=long_term:2026-08"]


def test_loans_read_no_further_back_than_t_13_so_grace_is_not_known(tmp_path: Path) -> None:
    # More in stage I is counterevidence only past two months' grace; whether July held
    # more needs June 2025, beyond thirteen months: not known, never assumed.
    item = read(tmp_path, FormalStage.STAGE_I, "loans", loans=MORE)

    assert item["relation"] == "unconfirmed"
    assert item["missing"] == ["borrower=enterprise,measure=ytd_increment,tenor=long_term:2025-06"]


def test_a_household_flow_against_enterprise_loans_is_a_split(tmp_path: Path) -> None:
    item = read(
        tmp_path,
        FormalStage.STAGE_III,
        "loans",
        loans=MORE,
        others={("household", "total"): LESS},
    )

    household = next(m for m in item["members"] if m["member"] == loan("household", "total"))
    assert household["consistency"] == "opposes"
    assert item["relation"] == "observation_only" and item["divergence_capped"] is True


def test_bills_more_while_long_term_loans_less_notes_a_worsening_structure(
    tmp_path: Path,
) -> None:
    item = read(
        tmp_path,
        FormalStage.STAGE_V,
        "loans",
        loans=LESS,
        others={("enterprise", "bill_financing"): MORE},
    )

    assert "结构恶化" in item["notes"]
    # The bills against the long-term loans are a split all the same.
    assert item["relation"] == "observation_only" and item["divergence_capped"] is True


def seed_impulse(repository: EvidenceRepository, august: float) -> None:
    """Social financing's year-to-date totals, 100 a month from July 2025 and ``august``
    in August 2026, and nominal GDP's five quarters: the twelve-month impulse's inputs."""
    months = tuple(f"{2025 + (6 + i) // 12}-{(6 + i) % 12 + 1:02d}" for i in range(14))
    flows = [100.0] * 13 + [august]
    totals = []
    for month, flow in zip(months, flows, strict=True):
        before = totals[-1] if totals and not month.endswith("-01") else 0.0
        totals.append(before + flow)
    append(
        repository,
        "CN_SF_TOTAL",
        {"measure": "ytd_increment"},
        tuple(totals),
        months=months,
        unit=AMOUNT,
    )
    quarter(
        repository,
        "CN_GDP",
        GDP_NOMINAL,
        (660000.0, 1000000.0, 1340000.0, 320000.0, 660000.0),
        unit=AMOUNT,
    )


@pytest.mark.parametrize(
    ("august", "totals", "noted"),
    [
        # August's flow 200 against 100 a year before: the impulse up, long-term loans less.
        (200.0, LESS, True),
        # The impulse down: no lead to observe.
        (50.0, LESS, False),
        # Long-term loans more: their structure is not unimproved.
        (200.0, MORE, False),
    ],
)
def test_stage_vi_notes_the_credit_impulse_turning_up_ahead_of_long_term_loans(
    tmp_path: Path, august: float, totals: tuple[float, ...], noted: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_loans(repository, totals)
    seed_impulse(repository, august)
    rules = manifest()
    rules["derived_formula_versions"] = {
        **rules["derived_formula_versions"],
        "credit_impulse": TWELVE_MONTH_CREDIT_IMPULSE,
    }
    context = build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=rules,
        formal_stage=StageResult(
            FormalStage.STAGE_VI, FormalStage.STAGE_VI, "canonical_combination"
        ),
    )

    impulse = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )
    assert impulse["direction"] == ("up" if august > 100.0 else "down")
    item = indicator(context, "loans")
    assert ("信用脉冲转强而贷款结构未改善（领先观察）" in item["notes"]) is noted
    # A note alone: the relation is the cell's, and the counts with it.
    assert item["relation"] == ("support" if totals == LESS else "observation_only")
    credit = next(
        dimension
        for dimension in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
        if dimension["dimension"] == "credit"
    )
    assert credit["counts"]["support"] == (totals == LESS)
    assert credit["counts"]["observation_only"] == (totals == MORE)


def test_loans_with_nothing_held_name_the_months_due(tmp_path: Path) -> None:
    # Nothing held: July, due on the target day, is still read, and every endpoint it
    # needs is named beside the status, never the status alone.
    item = read(tmp_path, FormalStage.STAGE_III, "loans", loans=(None, None, None, None))

    assert item["relation"] == "unconfirmed"
    assert item["missing"] == [
        f"borrower=enterprise,measure=ytd_increment,tenor=long_term:{gap}"
        for gap in ("missing", "2025-06", "2025-07", "2026-06", "2026-07")
    ]


@pytest.mark.parametrize(
    ("stage", "values", "relation", "momentum"),
    [
        # January to June against January to July: slowing supports stage I.
        (
            FormalStage.STAGE_I,
            (3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.5, 2.5),
            "support",
            "down",
        ),
        (
            FormalStage.STAGE_III,
            (3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.5, 3.5),
            "support",
            "up",
        ),
        # Still strong in stage V lags: only observed.
        (
            FormalStage.STAGE_V,
            (3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.5, 3.5),
            "observation_only",
            "up",
        ),
        # Peaking supports stage V.
        (
            FormalStage.STAGE_V,
            (3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 2.5, 2.5),
            "support",
            "flat",
        ),
    ],
)
def test_industrial_profits_read_the_official_cumulative_growth(
    tmp_path: Path,
    stage: FormalStage,
    values: tuple[float, ...],
    relation: str,
    momentum: str,
) -> None:
    item = read(tmp_path, stage, "industrial_profit", profit=values)

    assert item["relation"] == relation
    assert item["timing"] == "lagging" and item["dimension"] == "overheat"
    main = item["members"][0]
    # The official cumulative growth itself, said to be cumulative: no growth of a month
    # computed from cumulative profits.
    assert main["member"] == PROFIT and main["formula_version"] is None
    assert main["cumulative"] is True and "累计口径" in main["label"]
    assert main["values"][-2:] == list(values[-2:]) and main["momentum"] == momentum
    assert main["periods"][-1] == "2026-07-31"
    assert {member["member"]["item"] for member in item["members"][1:]} == {"revenue", "cost"}


def test_february_s_cumulative_profits_are_read_against_december_passing_over_january(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    months = tuple(f"{2025 + (i + 2) // 12}-{(i + 2) % 12 + 1:02d}" for i in range(12))
    assert months[-1] == "2026-02"
    seed_profit(repository, (4.0,) * 10 + (3.0, 2.0), months=months)
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 3, 30, tzinfo=UTC),
        target_business_date="2026-03-27",
        visible_evidence_start="2025-11-01",
        model_manifest=manifest(),
        formal_stage=StageResult(FormalStage.STAGE_I, FormalStage.STAGE_I, "canonical_combination"),
    )

    item = indicator(context, "industrial_profit")
    main = item["members"][0]
    assert main["periods"][-2:] == ["2025-12-31", "2026-02-28"] and main["missing"] == []
    assert main["momentum"] == "down" and item["relation"] == "support"


@pytest.mark.parametrize(
    ("stage", "values", "relation"),
    [
        # Slowing on and low in the year: stage I's, and stage II's low.
        (FormalStage.STAGE_I, (6.0, 5.4, 5.2, 5.0, 4.6), "support"),
        (FormalStage.STAGE_II, (6.0, 5.4, 5.3, 5.2, 5.1), "support"),
        # Falling faster in stage II is counterevidence at once: GDP moves with the cycle.
        (FormalStage.STAGE_II, (6.0, 5.4, 5.2, 5.0, 4.6), "counterevidence"),
        (FormalStage.STAGE_III, (6.0, 4.6, 5.0, 5.2, 5.4), "support"),
        (FormalStage.STAGE_IV, (6.0, 4.6, 5.0, 5.2, 5.4), "support"),
        (FormalStage.STAGE_V, (6.0, 4.6, 5.0, 5.4, 5.2), "support"),
        (FormalStage.STAGE_VI, (6.0, 5.0, 5.0, 5.0, 5.0), "observation_only"),
    ],
)
def test_gdp_reads_four_quarters_for_level_momentum_and_slope(
    tmp_path: Path, stage: FormalStage, values: tuple[float, ...], relation: str
) -> None:
    item = read(tmp_path, stage, "gdp", gdp=values)

    assert item["relation"] == relation
    main = item["members"][0]
    assert main["periods"] == list(QUARTERS[1:])
    assert item["statistical_period"] == "2026-06-30" and item["timing"] == "coincident"
    if values == (6.0, 5.4, 5.2, 5.0, 4.6):
        assert main["momentum"] == "down" and main["slope"] == "steeper"
        assert main["position"] == "low"


def test_gdp_s_year_is_its_four_quarters_and_a_marked_change_is_against_their_changes(
    tmp_path: Path,
) -> None:
    # Flat for three quarters, then a full point down: marked, and low in the year.
    item = read(tmp_path, FormalStage.STAGE_IV, "gdp", gdp=(5.9, 6.0, 6.0, 6.0, 5.0))

    main = item["members"][0]
    assert main["position"] == "low" and main["change_size"] == "marked"
    # Stage IV's marked slowing waits a quarter's grace: the quarter before was flat.
    assert item["relation"] == "observation_only"
    assert item["grace"]["limit"] == 1 and item["grace"]["unit"] == "quarter"
    assert item["grace"]["periods"] == 1 and item["grace"]["past"] is False
    assert item["turn"]["maturity"] == "sprout"


def test_a_marked_slowing_held_two_quarters_is_past_grace(tmp_path: Path) -> None:
    # The quarter before read its own year, back to the second quarter of 2025.
    item = read(tmp_path, FormalStage.STAGE_IV, "gdp", gdp=(6.1, 6.0, 6.0, 5.6, 5.0))

    assert item["relation"] == "counterevidence"
    assert item["grace"]["periods"] == 2 and item["grace"]["past"] is True


def test_the_quarter_before_reading_its_year_needs_the_one_before_the_four(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, FormalStage.STAGE_IV, "gdp", gdp=(None, 6.0, 6.0, 5.6, 5.0))

    assert item["relation"] == "unconfirmed"
    assert item["missing"] == ["aggregate=total,measure=real_quarter_yoy:2025-06"]


def test_gdp_s_nominal_cumulative_level_is_shown_not_compared(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    quarter(repository, "CN_GDP", GDP, (6.0, 5.4, 5.2, 5.0, 4.6))
    # A year-to-date level rises each quarter of a year and resets in the first.
    quarter(
        repository,
        "CN_GDP",
        GDP_NOMINAL,
        (660000.0, 1000000.0, 1340000.0, 320000.0, 660000.0),
        unit=AMOUNT,
    )

    item = indicator(project(repository, FormalStage.STAGE_I), "gdp")

    nominal = item["members"][1]
    assert nominal["member"] == GDP_NOMINAL and nominal["cumulative"] is True
    assert nominal["value"] == 660000.0 and nominal["consistency"] == "not_compared"
    assert item["consistency"] == "consistent" and item["relation"] == "support"


@pytest.mark.parametrize(
    ("stage", "rate", "change", "relation", "momentum", "slope"),
    [
        # Up on the quarter before but below the same quarter a year before: falling.
        (
            FormalStage.STAGE_V,
            (74.0, 73.0, 74.0, 73.5, 74.2),
            (0.1, -0.5, -0.4, -0.6, -0.3),
            "support",
            "down",
            "slower",
        ),
        (
            FormalStage.STAGE_III,
            (74.0, 73.0, 74.0, 73.5, 74.2),
            (0.1, 0.5, 0.4, 0.6, 0.3),
            "support",
            "up",
            "slower",
        ),
        # Below a year before, then above it: a turn.
        (
            FormalStage.STAGE_III,
            (74.0, 73.0, 74.0, 73.5, 74.2),
            (0.1, 0.5, 0.4, -0.2, 0.3),
            "support",
            "up",
            "turn",
        ),
        # Still high in the year in stage VI lags: only observed.
        (
            FormalStage.STAGE_VI,
            (74.0, 73.0, 73.5, 73.8, 74.2),
            (0.1, 0.5, 0.4, 0.0, 0.0),
            "observation_only",
            "flat",
            "flat",
        ),
        (
            FormalStage.STAGE_II,
            (74.0, 74.2, 74.0, 73.8, 73.0),
            (0.1, 0.5, 0.4, 0.0, 0.0),
            "support",
            "flat",
            "flat",
        ),
    ],
)
def test_capacity_utilisation_reads_its_official_change_on_a_year_before(
    tmp_path: Path,
    stage: FormalStage,
    rate: tuple[float, ...],
    change: tuple[float, ...],
    relation: str,
    momentum: str,
    slope: str,
) -> None:
    item = read(tmp_path, stage, "capacity_utilization", capacity=(rate, change))

    assert item["relation"] == relation and item["timing"] == "lagging"
    main = item["members"][0]
    assert main["member"] == CAPACITY and main["change_from"] == CAPACITY_CHANGE
    # Its momentum and slope are the stated changes', never the quarter on quarter's.
    assert main["momentum"] == momentum and main["slope"] == slope
    assert main["periods"] == list(QUARTERS[1:])
    assert main["changes"] == list(change[1:])


@pytest.mark.parametrize(
    ("change", "relation", "periods"),
    [
        # High and rising in stage I: counterevidence only past a quarter's grace.
        ((0.1, 0.5, 0.4, -0.2, 0.3), "observation_only", 1),
        ((0.1, 0.5, 0.4, 0.2, 0.3), "counterevidence", 2),
    ],
)
def test_capacity_utilisation_waits_a_quarter_s_grace(
    tmp_path: Path, change: tuple[float, ...], relation: str, periods: int
) -> None:
    rate = (73.0, 73.2, 73.4, 74.6, 74.8)
    item = read(tmp_path, FormalStage.STAGE_I, "capacity_utilization", capacity=(rate, change))

    assert item["members"][0]["position"] == "high"
    assert item["relation"] == relation
    assert item["grace"]["periods"] == periods and item["grace"]["unit"] == "quarter"


def test_capacity_utilisation_without_its_official_change_is_unconfirmed(tmp_path: Path) -> None:
    rate = (73.0, 73.2, 73.4, 74.6, 74.8)
    change = (0.1, 0.5, 0.4, 0.2, None)

    item = read(tmp_path, FormalStage.STAGE_III, "capacity_utilization", capacity=(rate, change))

    assert item["relation"] == "unconfirmed"
    # The official change is what is missing, not the rate.
    assert item["missing"] == ["industry=all_industry,measure=yoy_change:2026-06"]


def test_the_four_indicators_are_counted_in_their_dimensions(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_loans(repository, MORE)
    seed_profit(repository, (3.0,) * 10 + (2.5, 3.5))
    quarter(repository, "CN_GDP", GDP, (6.0, 4.6, 5.0, 5.2, 5.4))
    quarter(repository, "CN_CAPACITY_UTILIZATION", CAPACITY, (74.0, 73.0, 74.0, 73.5, 74.2))
    quarter(
        repository,
        "CN_CAPACITY_UTILIZATION",
        CAPACITY_CHANGE,
        (0.1, 0.5, 0.4, 0.6, 0.3),
        unit="percentage_points",
    )

    context = project(repository, FormalStage.STAGE_III)

    dimensions = {
        item["dimension"]: item
        for item in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
    }
    credit = {item["key"]: item["relation"] for item in dimensions["credit"]["key_indicators"]}
    overheat = {item["key"]: item["relation"] for item in dimensions["overheat"]["key_indicators"]}
    assert credit["loans"] == "support"
    assert {key: overheat[key] for key in ("industrial_profit", "gdp", "capacity_utilization")} == {
        "industrial_profit": "support",
        "gdp": "support",
        "capacity_utilization": "support",
    }
    # Four of the eight overheat and credit indicators are held here, the rest not.
    assert dimensions["overheat"]["counts"]["support"] == 3
    assert dimensions["credit"]["counts"]["support"] == 1


def test_the_pages_and_the_report_read_the_four_indicators(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_loans(repository, MORE)
    seed_profit(repository, (3.0,) * 10 + (2.5, 3.5))
    quarter(repository, "CN_GDP", GDP, (6.0, 4.6, 5.0, 5.2, 5.4))
    quarter(repository, "CN_CAPACITY_UTILIZATION", CAPACITY, (74.0, 73.0, 74.0, 73.5, 74.2))
    quarter(
        repository,
        "CN_CAPACITY_UTILIZATION",
        CAPACITY_CHANGE,
        (0.1, 0.5, 0.4, 0.6, 0.3),
        unit="percentage_points",
    )
    read = {
        key: indicator(project(repository, FormalStage.STAGE_III), key)
        for key in ("loans", "industrial_profit", "gdp", "capacity_utilization")
    }
    projection = confirmed(tmp_path / "published")
    datasets = copy.deepcopy(projection.datasets)
    for dimension in datasets["macro"]["confirmation"]["dimensions"]:
        dimension["key_indicators"] = [
            read.get(item["key"], item) for item in dimension["key_indicators"]
        ]
    shown = replace(projection, datasets=datasets)

    macro = _text(dashboard_page("/macro", shown, (), ()))
    bundle = report_input_from_projection(shown)

    assert "贷款" in macro and "企业中长期贷款当月增量" in macro and "较去年同月多增" in macro
    assert "工业企业盈利" in macro and "累计口径" in macro
    assert "GDP" in macro and "一年区间" in macro
    assert "产能利用率" in macro and "较上年同期上升" in macro
    readings = bundle.results["confirmation"]["key_indicators"]
    assert readings["loans"]["members"][0]["direction"] == "up"
    assert readings["industrial_profit"]["members"][0]["cumulative"] is True
    assert readings["capacity_utilization"]["members"][0]["change_from"] == CAPACITY_CHANGE
    assert readings["capacity_utilization"]["members"][0]["changes"] == [0.5, 0.4, 0.6, 0.3]
