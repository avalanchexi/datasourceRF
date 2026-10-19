"""The macro judgement is never empty (ADR-0043 revised, macro stage ticket 03).

A tied top score is the tied stage fewest ring steps from the last confirmed stage, forward
on equal steps, as a tendency; too little evidence is the typical stage fewest assets off
the day's three cores, nearest the last confirmed stage, as a weak judgement; with the
cores unavailable it is the last confirmed stage itself, weak.

The tie cases share one macro day: the 10-15 shape with prices rising from the bottom of
their year, so stages III, V and VI each match three of five dimensions. The cores set the
last confirmed stage the tie is broken against.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.day_summary import DaySummaries, ModelRules
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
    validate_analytical_projection,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_confirmation_monthly_indicators import append, year
from tests.integration.test_confirmation_policy import claim as monthly_claim
from tests.integration.test_confirmation_projection import append_pmi
from tests.integration.test_confirmation_publish import MONTHS, publish
from tests.integration.test_core_carry_forward import CORES, CUTOFF, seed_cores, sessions
from tests.integration.test_day_summary import stock_conflict
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_macro_judgement import (
    CATALOG,
    LPR_MONTHS,
    MODEL,
    industrial_va,
    register_macro_model,
    seed_macro,
    take_effect,
)
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

# PPI rising from the bottom of its year: prices are up and low.
PPI_LOW = year(-1.0, -0.8, -0.6, fill=0.5)
TIED = {"stage_iii": 3, "stage_v": 3, "stage_vi": 3}
# The stock core's last rising session: from it on it falls six points a session.
STOCK_TURN = 145


def seed_combination(
    paths: RuntimePaths, bond: str, stock: str, commodity: str, *, stock_turn: int | None = None
) -> None:
    """Each core rising (bull) or falling (bear) through the 180 sessions; a ``stock_turn``
    keeps the stock core rising to that session, then falling steeply, so it is a bull
    the session before the target day and a bear on it."""
    days = sessions()
    seed_independent_calendar(paths, days)
    states = {"bond": bond, "stock": stock, "commodity": commodity}

    def close(asset: str, index: int) -> float:
        if asset == "stock" and stock_turn is not None:
            return 100.0 + min(index, stock_turn) - 6.0 * max(index - stock_turn, 0)
        return 100.0 + index if states[asset] == "bull" else 1000.0 - index

    EvidenceRepository(paths.database).append_source_claims(
        tuple(
            claim(
                metric_id,
                observed,
                close(asset, index),
                unit="index_points",
                provider="tushare",
                reference=f"tushare:{CORE_API_IDENTITIES[metric_id][0]}:"
                f"{CORE_API_IDENTITIES[metric_id][1]}:{observed}",
            )
            for index, observed in enumerate(days)
            for asset, metric_id in CORES.items()
        )
    )


def seed_policy_and_inventory(paths: RuntimePaths) -> None:
    """Only two dimensions read: the LPR unchanged all year (neutral), inventory actively
    restocked (its demand, production and inventory lines rising). Industrial value added
    is then growth's one clear voter of five, short of half."""
    repository = EvidenceRepository(paths.database)
    for month in LPR_MONTHS:
        monthly_claim(
            repository,
            "CN_LPR_1Y_5Y",
            month,
            {"tenor": "1y"},
            3.0,
            unit="percent",
            definition_version=CATALOG,
        )
    append_pmi(
        repository, "new_orders", (50.0, 50.5, 51.0), months=MONTHS, definition_version=CATALOG
    )
    industrial_va(repository)
    append(
        repository,
        "CN_FINISHED_GOODS_INVENTORY",
        {"measure": "official_yoy"},
        (3.0, 3.5, 4.0),
        months=MONTHS,
        definition_version=CATALOG,
    )


def tied(tmp_path: Path, bond: str, stock: str, commodity: str) -> ProjectionSet:
    paths = runtime(tmp_path)
    seed_combination(paths, bond, stock, commodity)
    register_macro_model(paths)
    seed_macro(paths, ppi=PPI_LOW)
    return publish(paths, MODEL)


def judgement(projection: ProjectionSet) -> dict[str, Any]:
    return projection.datasets["cycle_overview"]["macro_judgement"]  # type: ignore[no-any-return]


def test_a_tie_takes_the_stage_one_step_on_from_the_last_confirmed_stage(tmp_path: Path) -> None:
    # Bond and stock rise, commodities fall: Stage II, the last confirmed stage.
    published = judgement(tied(tmp_path, "bull", "bull", "bear"))

    assert {stage: published["scores"][stage] for stage in TIED} == TIED
    assert max(published["scores"].values()) == 3
    assert published["raw"]["basis"] == "tied"
    assert published["raw"]["tied"] == ["stage_iii", "stage_v", "stage_vi"]
    # III is one step on from II; V three on, VI two back.
    assert published["conclusion"] == {
        "stage": "stage_iii",
        "confidence": "tendency",
        "matched": 3,
        "known": 5,
        "reference_stage": "stage_ii",
        "steps": 1,
        "direction": "forward",
    }


def test_a_tie_takes_the_stage_one_step_back_when_that_is_nearer(tmp_path: Path) -> None:
    # Bonds rise, stocks and commodities fall: Stage I; VI is one step back, III two on.
    conclusion = judgement(tied(tmp_path, "bull", "bear", "bear"))["conclusion"]

    assert (conclusion["stage"], conclusion["confidence"]) == ("stage_vi", "tendency")
    assert (conclusion["reference_stage"], conclusion["steps"], conclusion["direction"]) == (
        "stage_i",
        -1,
        "back",
    )


def test_a_tie_as_near_either_way_goes_forward(tmp_path: Path) -> None:
    # Stocks and commodities rise, bonds fall: Stage IV, between the tied III and V.
    conclusion = judgement(tied(tmp_path, "bear", "bull", "bull"))["conclusion"]

    assert (conclusion["stage"], conclusion["confidence"]) == ("stage_v", "tendency")
    assert (conclusion["reference_stage"], conclusion["steps"], conclusion["direction"]) == (
        "stage_iv",
        1,
        "forward",
    )


def weak_off_typical(tmp_path: Path) -> ProjectionSet:
    """Two dimensions known on a bond bull, stock bear, commodity bull day, the session
    before it Stage III (summarized with it)."""
    paths = runtime(tmp_path)
    seed_combination(paths, "bull", "bull", "bull", stock_turn=STOCK_TURN)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)
    return publish(paths, MODEL, (sessions()[-2].isoformat(),))


def test_too_little_evidence_off_typical_cores_is_the_nearest_stage_one_asset_away(
    tmp_path: Path,
) -> None:
    projection = weak_off_typical(tmp_path)

    overview = projection.datasets["cycle_overview"]
    assert (overview["current_stage"], overview["stage_reason"]) == (
        None,
        "noncanonical_combination",
    )
    assert overview["last_confirmed_stage"] == "stage_iii"
    published = judgement(projection)
    # Two dimensions known: policy neutral, inventory restocking.
    assert [item["dimension"] for item in published["dimensions"] if item["value"]] == [
        "policy",
        "inventory",
    ]
    assert published["raw"]["basis"] == "insufficient"
    # I, III and V are each one asset off: III is the last confirmed stage itself.
    assert published["raw"]["fallback"] == {
        "source": "combination",
        "combination": {"bond": "bull", "stock": "bear", "commodity": "bull"},
        "differences": 1,
        "candidates": ["stage_i", "stage_iii", "stage_v"],
    }
    assert published["conclusion"] == {
        "stage": "stage_iii",
        "confidence": "weak",
        "matched": 2,
        "known": 2,
        "reference_stage": "stage_iii",
        "steps": 0,
        "direction": "same",
    }


def test_too_little_evidence_on_typical_cores_is_the_price_stage_itself(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)

    published = judgement(publish(paths, MODEL))

    # The cores all rise: Stage III, the one typical stage no asset off.
    assert published["raw"]["fallback"] == {
        "source": "combination",
        "combination": {"bond": "bull", "stock": "bull", "commodity": "bull"},
        "differences": 0,
        "candidates": ["stage_iii"],
    }
    conclusion = published["conclusion"]
    assert (conclusion["stage"], conclusion["confidence"], conclusion["matched"]) == (
        "stage_iii",
        "weak",
        2,
    )
    assert (conclusion["steps"], conclusion["direction"]) == (0, "same")


def test_with_the_cores_unavailable_it_is_the_last_confirmed_stage_weak(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    # The commodity core lacks its last two sessions: no stage on the target day.
    seed_cores(paths, commodity_missing=2)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)

    projection = publish(paths, MODEL, (sessions()[-3].isoformat(),))

    overview = projection.datasets["cycle_overview"]
    assert (overview["current_stage"], overview["stage_reason"]) == (None, "core_data_pending")
    published = judgement(projection)
    assert published["raw"]["fallback"] == {
        "source": "reference",
        "combination": None,
        "differences": None,
        "candidates": [],
    }
    conclusion = published["conclusion"]
    assert (conclusion["stage"], conclusion["confidence"], conclusion["reference_stage"]) == (
        "stage_iii",
        "weak",
        "stage_iii",
    )
    assert (conclusion["steps"], conclusion["direction"]) == (0, "same")


def _relabel(block: dict[str, Any], **fields: object) -> None:
    for judgement in (block["raw"], block["conclusion"]):
        judgement.update(fields)


@pytest.mark.parametrize(
    "tamper",
    [
        # A tie shown as explicit, or its tied stages cut to one.
        lambda block: _relabel(block, confidence="explicit"),
        lambda block: block["raw"].update(basis="unique_top", confidence="explicit"),
        lambda block: block["raw"].update(tied=["stage_iii", "stage_v"]),
        # The tied stage farther from the last confirmed one.
        lambda block: (
            _relabel(block, stage="stage_v")
            or block["conclusion"].update(steps=3, direction="forward")
        ),
    ],
)
def test_a_tie_out_of_keeping_with_its_scores_is_not_published(
    tmp_path: Path, tamper: Callable[[dict[str, Any]], None]
) -> None:
    projection = tied(tmp_path, "bull", "bull", "bear")
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        validate_analytical_projection(projection.envelope, datasets)


@pytest.mark.parametrize(
    "tamper",
    [
        # Weak shown as explicit or as a tendency.
        lambda block: _relabel(block, confidence="explicit"),
        lambda block: _relabel(block, confidence="tendency"),
        # A stage the cores' combination does not give, or a combination misstated.
        lambda block: (
            _relabel(block, stage="stage_iv", matched=1)
            or block["conclusion"].update(steps=1, direction="forward")
        ),
        lambda block: block["raw"]["fallback"].update(candidates=["stage_iii", "stage_iv"]),
        # Enough evidence for an explicit or tendency judgement.
        lambda block: block["raw"].update(threshold=2),
    ],
)
def test_a_weak_judgement_out_of_keeping_with_its_fallback_is_not_published(
    tmp_path: Path, tamper: Callable[[dict[str, Any]], None]
) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)
    projection = publish(paths, MODEL)
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        validate_analytical_projection(projection.envelope, datasets)


def test_a_correction_of_the_last_confirmed_stage_alone_takes_the_weak_stage_again(
    tmp_path: Path,
) -> None:
    # The relink of follow-up ticket 01: a held day summarized while the day before it had
    # no stage yet is corrected once that day has one, its scores judged nowhere again.
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)
    days = [day.isoformat() for day in sessions()]
    staged, held = days[-3], days[-2]
    EvidenceRepository(paths.database).append_source_claims((stock_conflict(sessions()[-2]),))
    summaries = DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), MODEL),
        calendar=TradingCalendar(sessions()),
    )
    repository = ProjectionSetRepository(paths.database)
    # The rules take effect on the held day: the first run with them targets it.
    take_effect(paths, held)

    def held_judgement() -> dict[str, Any]:
        [event] = [event for event in repository.stage_history() if event["business_date"] == held]
        return judgement(repository.get(str(event["projection_set_id"])))

    # The stock core held and no stage before it: nothing to take, said so.
    first = held_judgement()
    assert first["raw"]["fallback"]["source"] == "reference"
    assert (first["conclusion"]["stage"], first["conclusion"]["confidence"]) == (None, None)

    summaries.backfill((staged, held), target=days[-1], system_as_of=CUTOFF + timedelta(days=1))

    relinked = held_judgement()
    assert {key: relinked[key] for key in ("dimensions", "scores")} == {
        key: first[key] for key in ("dimensions", "scores")
    }
    assert relinked["conclusion"] == {
        "stage": "stage_iii",
        "confidence": "weak",
        "matched": 2,
        "known": 2,
        "reference_stage": "stage_iii",
        "steps": 0,
        "direction": "same",
    }
