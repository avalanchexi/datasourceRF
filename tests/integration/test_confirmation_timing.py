"""Timing, grace and signal maturity in confirmation (ADR-0037, ticket 05).

A counterevidence cell waiting on grace is observation only while its signal has held no
longer than two months or one quarter, each period read as it stood; a lagging indicator
still in the previous stage's form, or a leading one already in the next's, waits on
grace whether or not the table marks it. A turn signal is a sprout, forming or confirmed,
and only confirmed counts. An indicator counts once for its newest period, however many
days read it.
"""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.confirmation import ConfirmationRules
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from tests.integration.test_confirmation_monthly_indicators import (
    BEFORE,
    INDICATORS,
    METRICS,
    YEAR,
    append,
    indicator,
    year,
)
from tests.integration.test_confirmation_projection import append_pmi, confirmation_manifest
from tests.integration.test_context_projection import _v2_manifest

TARGET = "2026-09-15"
# The PMI's lookback and the two months its grace reads back.
PMI_MONTHS = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08")
PMI_SERIES = ("manufacturing", "new_orders", "production", "purchase_volume")
QUARTERS = (("2025-07-01", "2025-09-30"), ("2025-10-01", "2025-12-31"))
QUARTERS += (("2026-01-01", "2026-03-31"), ("2026-04-01", "2026-06-30"))
CAPACITY = {"industry": "all_industry", "measure": "quarter_rate"}


def manifest(*extra: dict[str, Any]) -> dict[str, Any]:
    """The new model's rules, with any key indicator declared in the manifest alone."""
    built = confirmation_manifest(_v2_manifest(*METRICS, "CN_CAPACITY_UTILIZATION"))
    built["confirmation_rules"]["key_indicators"].extend(copy.deepcopy(item) for item in extra)
    return built


def project(
    repository: EvidenceRepository,
    stage: FormalStage,
    *,
    target: str = TARGET,
    rules: dict[str, Any] | None = None,
) -> ContextProjection:
    as_of = datetime.combine(date.fromisoformat(target) + timedelta(days=1), datetime.min.time())
    return build_context_projection(
        repository,
        as_of=as_of.replace(tzinfo=UTC),
        target_business_date=target,
        visible_evidence_start="2026-04-01",
        model_manifest=rules or manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
    )


def seed_pmi(repository: EvidenceRepository, values: tuple[float, ...]) -> None:
    for series in PMI_SERIES:
        append_pmi(repository, series, values, months=PMI_MONTHS[-len(values) :])


def seed_money(repository: EvidenceRepository, values: tuple[float, ...]) -> None:
    """M1 and M2 alike over the year and the two months before it."""
    for metric_id, dimensions, unit in INDICATORS["money"]:
        append(repository, metric_id, dimensions, values, months=(*BEFORE, *YEAR), unit=unit)


def counts(context: ContextProjection, dimension: str) -> dict[str, int]:
    return next(  # type: ignore[no-any-return]
        item["counts"]
        for item in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
        if item["dimension"] == dimension
    )


# Stage III waits on grace for a PMI below 50: the months below it, newest back.
@pytest.mark.parametrize(
    ("values", "relation", "periods", "since", "maturity"),
    [
        ((51.0, 51.0, 51.0, 50.5, 49.5), "observation_only", 1, "2026-08-31", "sprout"),
        ((51.0, 51.0, 50.5, 49.8, 49.5), "observation_only", 2, "2026-07-31", "forming"),
        # Past grace, held at least as far back as read: since a month not read.
        ((51.0, 49.9, 49.8, 49.6, 49.5), "counterevidence", 3, None, "confirmed"),
    ],
)
def test_a_monthly_signal_is_counterevidence_only_past_two_months(
    tmp_path: Path,
    values: tuple[float, ...],
    relation: str,
    periods: int,
    since: str | None,
    maturity: str,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_pmi(repository, values)

    context = project(repository, FormalStage.STAGE_III)

    pmi = indicator(context, "pmi")
    assert pmi["relation"] == relation
    assert pmi["timing"] == "coincident"
    assert pmi["grace"] == {
        "limit": 2,
        "unit": "month",
        "periods": periods,
        "at_least": since is None,
        "since": since,
        "past": relation == "counterevidence",
        "confirmed_by": "grace" if relation == "counterevidence" else None,
    }
    assert pmi["turn"]["maturity"] == maturity
    assert pmi["turn"]["toward"] is None and pmi["turn_hint"] is None
    # Only the confirmed signal counts.
    assert counts(context, "overheat")["counterevidence"] == (relation == "counterevidence")
    # The lookback is read as it was: three months, the two before them for grace alone.
    assert pmi["members"][0]["periods"] == ["2026-06-30", "2026-07-31", "2026-08-31"]


def test_the_months_grace_reads_back_are_model_inputs(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    claims = append_pmi(
        repository, "manufacturing", (51.0, 49.9, 49.8, 49.6, 49.5), months=PMI_MONTHS
    )

    context = project(repository, FormalStage.STAGE_III)

    assert set(claims) <= set(context.macro["model_input_observation_version_ids"])  # type: ignore[arg-type]


def capacity(timing: str) -> dict[str, Any]:
    """Capacity utilisation, quarterly, declared in the manifest alone: stage III expects
    it rising, stage II falling."""
    stages = ("stage_i", "stage_ii", "stage_iii", "stage_iv", "stage_v", "stage_vi")
    cells: dict[str, list[dict[str, Any]]] = {stage: [] for stage in stages}
    cells["stage_ii"] = [{"relation": "support", "when": [{"momentum": "down"}]}]
    cells["stage_iii"] = [
        {"relation": "counterevidence", "when": [{"momentum": ["down", "flat"]}]},
        {"relation": "support", "when": [{"momentum": "up"}]},
    ]
    return {
        "key": "capacity_utilization",
        "name": "产能利用率",
        "dimension": "overheat",
        "metric_id": "CN_CAPACITY_UTILIZATION",
        "timing": timing,
        "frequency": "quarterly",
        "main": {"name": "quarter_rate", "label": "全工业产能利用率", "dimensions": CAPACITY},
        "auxiliary": [],
        "level_line": None,
        "lookback_quarters": 3,
        "expectations": {
            stage: {"proposition": "产能趋紧", "cells": cells[stage]} for stage in stages
        },
    }


def seed_capacity(repository: EvidenceRepository, values: tuple[float, ...]) -> list[str]:
    claims = []
    for (start, end), value in zip(QUARTERS, values, strict=True):
        public = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(days=20)
        claims.append(
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_CAPACITY_UTILIZATION",
                    definition_version="metric-catalog-v0002",
                    period_kind="quarter",
                    period_start=start,
                    period_end=end,
                    dimensions=CAPACITY,
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="certified-fixture",
                    source_reference=f"fixture:capacity:{end}",
                    release_event_id=f"release:capacity:{end}",
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


@pytest.mark.parametrize(
    ("values", "relation", "periods", "maturity"),
    [
        # Falling in the newest quarter alone: still stage II's form, within grace.
        ((75.0, 75.0, 75.5, 74.0), "observation_only", 1, "sprout"),
        # Two quarters falling is past a quarter's grace.
        ((75.0, 75.5, 74.5, 74.0), "counterevidence", 2, "confirmed"),
    ],
)
def test_a_lagging_quarterly_indicator_in_the_previous_stages_form_waits_a_quarter(
    tmp_path: Path, values: tuple[float, ...], relation: str, periods: int, maturity: str
) -> None:
    # The cell is not marked as waiting on grace: the declared timing alone makes it wait.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_capacity(repository, values)

    context = project(repository, FormalStage.STAGE_III, rules=manifest(capacity("lagging")))

    item = indicator(context, "capacity_utilization")
    assert item["relation"] == relation
    assert item["timing"] == "lagging"
    assert item["statistical_period"] == "2026-06-30"
    assert item["members"][0]["periods"] == ["2025-12-31", "2026-03-31", "2026-06-30"]
    assert item["grace"]["limit"] == 1 and item["grace"]["unit"] == "quarter"
    assert item["grace"]["periods"] == periods
    assert item["turn"] == {
        "toward": "stage_ii",
        "basis": "lagging",
        "maturity": maturity,
        "confirmed_by": "grace" if maturity == "confirmed" else None,
        "periods": periods,
        # Two quarters is as far back as grace reads: held at least that long.
        "at_least": periods == 2,
        "since": "2026-06-30" if periods == 1 else None,
        "leading_signals": [],
        "missing": [],
    }
    # A lag is no turn ahead: no stage is said to be approached.
    assert item["turn_hint"] is None


def test_the_same_indicator_moving_with_the_cycle_is_counterevidence_at_once(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_capacity(repository, (75.0, 75.0, 75.0, 74.0))

    context = project(repository, FormalStage.STAGE_III, rules=manifest(capacity("coincident")))

    item = indicator(context, "capacity_utilization")
    assert item["relation"] == "counterevidence"
    assert item["grace"] is None and item["turn"] is None


def test_a_flat_lagging_reading_not_in_the_previous_form_is_counterevidence_at_once(
    tmp_path: Path,
) -> None:
    # Stage II's form is falling; a flat quarter is not it.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_capacity(repository, (75.0, 75.0, 75.5, 75.5))

    context = project(repository, FormalStage.STAGE_III, rules=manifest(capacity("lagging")))

    item = indicator(context, "capacity_utilization")
    assert item["relation"] == "counterevidence" and item["grace"] is None


def test_four_quarters_are_read_and_grace_reads_within_them(tmp_path: Path) -> None:
    # Four quarters to the newest; the quarter before, read for grace, reads its
    # momentum within them, and nothing before the third quarter of 2025.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_capacity(repository, (75.0, 75.5, 74.5, 74.0))
    four = capacity("lagging") | {"lookback_quarters": 4}

    item = indicator(
        project(repository, FormalStage.STAGE_III, rules=manifest(four)), "capacity_utilization"
    )

    assert item["members"][0]["periods"] == [end for _start, end in QUARTERS]
    assert item["relation"] == "counterevidence" and item["grace"]["periods"] == 2
    with pytest.raises(ValueError, match="confirmation_key_indicator_invalid"):
        ConfirmationRules.from_manifest(manifest(capacity("lagging") | {"lookback_quarters": 5}))


# M1 leads: rising in stage I is stage II's form already, and waits on grace.
@pytest.mark.parametrize(
    ("last", "relation", "maturity"),
    [
        ((2.0, 2.0, 2.2), "observation_only", "sprout"),
        ((2.0, 2.1, 2.2), "observation_only", "forming"),
        ((2.1, 2.2, 2.3), "counterevidence", "confirmed"),
    ],
)
def test_a_leading_signal_sprouts_forms_and_is_confirmed(
    tmp_path: Path, last: tuple[float, ...], relation: str, maturity: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_money(repository, (2.0, 2.0, *year(*last, fill=2.0)))

    context = project(repository, FormalStage.STAGE_I)

    money = indicator(context, "money")
    assert money["relation"] == relation
    assert money["turn"]["maturity"] == maturity
    assert money["turn"]["toward"] == "stage_ii" and money["turn"]["basis"] == "leading"
    assert money["turn_hint"] == "stage_ii"
    # Sprouting and forming are observed, never counted.
    assert counts(context, "credit")["counterevidence"] == (maturity == "confirmed")


def test_two_leading_indicators_turning_together_form(tmp_path: Path) -> None:
    # Stage I: M1 first rises, and social financing's stock growth rises a little, both
    # toward stage II.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_money(repository, (2.0, 2.0, *year(2.0, 2.0, 2.2, fill=2.0)))
    stock, *_others = INDICATORS["social_financing"]
    zigzag = (8.0, 8.4) * 6 + (8.0, 8.1)
    append(repository, stock[0], stock[1], zigzag, months=(*BEFORE, *YEAR))

    context = project(repository, FormalStage.STAGE_I)

    money, financing = indicator(context, "money"), indicator(context, "social_financing")
    assert financing["members"][0]["change_size"] == "ordinary"
    assert financing["turn"]["periods"] == money["turn"]["periods"] == 1
    assert money["turn"]["maturity"] == financing["turn"]["maturity"] == "forming"
    assert money["turn"]["leading_signals"] == ["social_financing"]
    assert financing["turn"]["leading_signals"] == ["money"]
    assert money["relation"] == financing["relation"] == "observation_only"


def test_a_lagging_reading_still_in_the_previous_form_is_told_so(tmp_path: Path) -> None:
    # Stage III: CPI still falling is stage II's form; the cell observes it.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for metric_id, dimensions, unit in INDICATORS["cpi"]:
        values = (0.8, 0.8, *year(0.6, 0.4, 0.2, fill=0.8))
        append(repository, metric_id, dimensions, values, months=(*BEFORE, *YEAR), unit=unit)

    cpi = indicator(project(repository, FormalStage.STAGE_III), "cpi")

    assert cpi["relation"] == "observation_only" and cpi["grace"] is None
    assert cpi["turn"]["toward"] == "stage_ii" and cpi["turn"]["basis"] == "lagging"
    assert cpi["turn"]["maturity"] == "confirmed"  # falling three months and more
    assert cpi["turn_hint"] is None


def test_a_period_grace_reads_back_not_held_leaves_it_unconfirmed(tmp_path: Path) -> None:
    # Stage II waits on grace for a marked slowing of social financing. Whether July's
    # slowing was marked needs the year to July, back to August 2025: not held.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    stock, *_others = INDICATORS["social_financing"]
    append(repository, stock[0], stock[1], year(8.4, 8.3, 7.5, fill=8.5))

    financing = indicator(project(repository, FormalStage.STAGE_II), "social_financing")

    assert financing["relation"] == "unconfirmed"
    assert financing["missing"] == ["measure=stock_yoy:2025-08"]
    assert financing["grace"]["past"] is None and financing["turn"]["maturity"] is None

    # Held, July and June slowed markedly too: past grace.
    append(repository, stock[0], stock[1], (8.5, 8.5), months=BEFORE)
    financing = indicator(project(repository, FormalStage.STAGE_II), "social_financing")
    assert financing["relation"] == "counterevidence"
    assert financing["grace"]["periods"] == 3 and financing["grace"]["past"] is True


def test_a_period_counts_once_whatever_day_reads_it(tmp_path: Path) -> None:
    # The PMI below 50 in July and August, then September. Every day of September reads
    # August's release: the same counting unit, the same grace, whichever runs saw it.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_pmi(repository, (51.0, 51.0, 50.5, 49.8, 49.5))
    for series in PMI_SERIES:
        append_pmi(repository, series, (49.4,), months=("2026-09",))

    september = [
        indicator(project(repository, FormalStage.STAGE_III, target=day), "pmi")
        for day in ("2026-09-15", "2026-09-22", "2026-09-29")
    ]
    october = indicator(project(repository, FormalStage.STAGE_III, target="2026-10-15"), "pmi")

    for pmi in september:
        assert pmi["statistical_period"] == "2026-08-31"
        assert pmi["grace"]["periods"] == 2 and pmi["grace"]["since"] == "2026-07-31"
        assert pmi["relation"] == "observation_only"
    # A new release is a new period: the grace runs on, past it now.
    assert october["statistical_period"] == "2026-09-30"
    assert october["grace"]["periods"] == 3 and october["grace"]["at_least"] is True
    assert october["relation"] == "counterevidence"


def test_a_period_the_stage_answered_otherwise_ends_the_signal(tmp_path: Path) -> None:
    # Stage V: social financing quickening less supports, quickening more waits on grace.
    # July still quickened less (support): August's quickening is a first month.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    stock, *_others = INDICATORS["social_financing"]
    append(repository, stock[0], stock[1], year(8.0, 8.4, 8.7, 8.9, 9.2, fill=8.0))

    financing = indicator(project(repository, FormalStage.STAGE_V), "social_financing")

    assert financing["relation"] == "observation_only"
    assert financing["grace"]["periods"] == 1 and financing["turn"]["maturity"] == "sprout"


def test_a_hints_own_condition_bounds_the_signal(tmp_path: Path) -> None:
    # Stage I: the PMI recovering below 50 since May, steepening in August alone: the hint
    # toward stage II first shows in August.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_pmi(repository, (47.0, 48.0, 48.5, 48.8, 49.4))

    pmi = indicator(project(repository, FormalStage.STAGE_I), "pmi")

    assert pmi["relation"] == "observation_only" and pmi["turn_hint"] == "stage_ii"
    assert pmi["turn"]["periods"] == 1 and pmi["turn"]["maturity"] == "sprout"
    assert pmi["grace"] is None


def test_a_stage_hint_matures_by_its_own_member_while_grace_counts_the_main(
    tmp_path: Path,
) -> None:
    # Stage II: PPI's year-on-year rising on for months is past grace; its month-on-month
    # turning up in August alone is a first sign toward stage III.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    rising = (0.0, 0.0, *year(1.0, 2.0, 3.0, 4.0, 5.0, fill=0.0))
    for index, (metric_id, dimensions, unit) in enumerate(INDICATORS["ppi"]):
        values = (0.1, 0.1, *year(0.1, 0.1, 0.1, 0.1, 0.3, fill=0.1)) if index == 1 else rising
        append(repository, metric_id, dimensions, values, months=(*BEFORE, *YEAR), unit=unit)

    ppi = indicator(project(repository, FormalStage.STAGE_II), "ppi")

    assert ppi["relation"] == "counterevidence" and ppi["grace"]["past"] is True
    assert ppi["turn_hint"] == "stage_iii" and ppi["turn"]["basis"] == "expectation"
    assert ppi["turn"]["periods"] == 1 and ppi["turn"]["maturity"] == "sprout"


def test_a_cell_naming_its_transmission_confirms_within_grace(tmp_path: Path) -> None:
    # A model whose stage III PMI cell is confirmed when new orders fall too: August below
    # 50 for the first month, new orders falling with it.
    rules = manifest()
    pmi_rules = rules["confirmation_rules"]["key_indicators"][0]
    pmi_rules["expectations"]["stage_iii"]["cells"][0]["confirmed_when"] = [
        {"member": "new_orders", "momentum": "down"}
    ]
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_pmi(repository, (51.0, 51.0, 51.0, 50.5, 49.5))

    pmi = indicator(project(repository, FormalStage.STAGE_III, rules=rules), "pmi")

    assert pmi["relation"] == "counterevidence"
    assert pmi["grace"]["periods"] == 1 and pmi["grace"]["past"] is True
    assert pmi["grace"]["confirmed_by"] == "transmission"
    assert pmi["turn"]["maturity"] == "confirmed"
