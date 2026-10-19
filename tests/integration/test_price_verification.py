"""The price verification under the macro judgement (ADR-0043, macro stage ticket 06): the
price stage, or the noncanonical combination, set against the three assets the judged stage
expects, as the day summary publishes it.

The macro evidence is the 10-15 hand calculation's (stage V, explicit 4/5), which expects
bond bear · stock bear · commodity bull; each case moves the cores alone.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import EvidenceRepository
from pring_cycle.projections import ProjectionSet, validate_analytical_projection
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from tests.integration.test_confirmation_publish import publish
from tests.integration.test_core_carry_forward import CORES, sessions
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_macro_judgement import MODEL, register_macro_model, seed_macro
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

STAGE_V = {"bond": "bear", "stock": "bear", "commodity": "bull"}


def verified(tmp_path: Path, *falling: str) -> ProjectionSet:
    """The 10-15 macro evidence over cores rising for 180 sessions, but ``falling``."""
    paths = runtime(tmp_path)
    days = sessions()
    seed_independent_calendar(paths, days)
    EvidenceRepository(paths.database).append_source_claims(
        tuple(
            claim(
                metric_id,
                observed,
                1000.0 - index if asset in falling else 100.0 + index,
                unit="index_points",
                provider="tushare",
                reference=f"tushare:{CORE_API_IDENTITIES[metric_id][0]}:"
                f"{CORE_API_IDENTITIES[metric_id][1]}:{observed}",
            )
            for index, observed in enumerate(days)
            for asset, metric_id in CORES.items()
        )
    )
    register_macro_model(paths)
    seed_macro(paths)
    return publish(paths, MODEL)


def verification(projection: ProjectionSet) -> dict[str, Any]:
    judgement = projection.datasets["cycle_overview"]["macro_judgement"]
    return judgement["price_verification"]  # type: ignore[index, no-any-return]


def test_a_price_stage_the_judged_stage_expects_is_consistent(tmp_path: Path) -> None:
    projection = verified(tmp_path, "bond", "stock")

    assert projection.datasets["cycle_overview"]["current_stage"] == "stage_v"
    assert verification(projection) == {
        "price_stage": "stage_v",
        "reason": "canonical_combination",
        "combination": STAGE_V,
        "expected_stage": "stage_v",
        "expected": STAGE_V,
        "deviations": [],
        "verdict": "consistent",
        "comparisons": [],
    }


def test_a_typical_price_stage_off_by_one_asset_names_it(tmp_path: Path) -> None:
    # All three fall: the price stage is VI, where V expects the commodity bull.
    projection = verified(tmp_path, "bond", "stock", "commodity")

    published = verification(projection)
    assert (published["price_stage"], published["reason"]) == ("stage_vi", "canonical_combination")
    assert published["combination"] == {"bond": "bear", "stock": "bear", "commodity": "bear"}
    assert (published["expected_stage"], published["expected"]) == ("stage_v", STAGE_V)
    assert (published["deviations"], published["verdict"]) == (["commodity"], "deviates")
    # The judgement stands as judged: the price stage verifies, it never votes.
    conclusion = projection.datasets["cycle_overview"]["macro_judgement"]["conclusion"]
    assert (conclusion["stage"], conclusion["confidence"]) == ("stage_v", "explicit")


def test_a_noncanonical_combination_names_the_asset_off_and_carries_its_comparisons(
    tmp_path: Path,
) -> None:
    # Bond bull · stock bear · commodity bull: no price stage, the bond off what V expects.
    projection = verified(tmp_path, "stock")

    overview = projection.datasets["cycle_overview"]
    published = verification(projection)
    assert overview["current_stage"] is None
    assert (published["price_stage"], published["reason"]) == (None, "noncanonical_combination")
    assert published["combination"] == {"bond": "bull", "stock": "bear", "commodity": "bull"}
    assert (published["expected_stage"], published["expected"]) == ("stage_v", STAGE_V)
    assert (published["deviations"], published["verdict"]) == (["bond"], "deviates")
    # The one-asset comparisons are the Worker's, as published beside the stage.
    assert [(item["stage"], item["asset"]) for item in published["comparisons"]] == [
        ("stage_i", "commodity"),
        ("stage_iii", "stock"),
        ("stage_v", "bond"),
    ]
    assert published["comparisons"] == overview["noncanonical_basis"]["comparisons"]


@pytest.mark.parametrize(
    "tamper",
    [
        lambda block: block["price_verification"].update(deviations=[]),
        lambda block: block["price_verification"].update(verdict="consistent"),
        lambda block: block["price_verification"]["combination"].update(commodity="bull"),
        lambda block: block["price_verification"].update(expected_stage="stage_vi"),
    ],
)
def test_a_verification_disagreeing_with_the_cores_or_the_conclusion_is_not_published(
    tmp_path: Path, tamper: Any
) -> None:
    projection = verified(tmp_path, "bond", "stock", "commodity")
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        validate_analytical_projection(projection.envelope, datasets)
