"""The macro stage judgement (ADR-0043, macro stage ticket 02): its rules frozen in
model-v0016, judged in the day summary and published with the day's set.

Each case registers its own model in its own run's database; model-v0016 itself is never
registered in a shared or the live database (macro stage goal).
"""

from __future__ import annotations

import copy
import hashlib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.day_summary import SHANGHAI, DaySummaries, ModelRules, RunMaterials
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.macro_judgement import MANIFEST_FIELD, rules_v0001
from pring_cycle.models import (
    ModelRepository,
    _canonical_json,
    certified_model_v0001_manifest,
    effective_model_manifest,
    model_v0015_manifest,
    model_v0016_manifest,
)
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
    validate_analytical_projection,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import summary
from tests.integration.test_confirmation_monthly_indicators import append, year
from tests.integration.test_confirmation_policy import claim
from tests.integration.test_confirmation_projection import append_pmi, confirmation_manifest
from tests.integration.test_confirmation_publish import (
    MODEL as CONFIRMATION_MODEL,
)
from tests.integration.test_confirmation_publish import (
    MONTHS,
    TO_JULY,
    publish,
    register_confirmation_model,
)
from tests.integration.test_core_carry_forward import seed_cores, sessions
from tests.integration.test_worker_execution import runtime

# model-v0015's manifest hash as shipped before this batch: v0016 leaves it as it was.
V0015_HASH = "22c78856e67a000364cfe48a606d9f69e76bae9c5c16887b6cf368ca6282a5d1"
MODEL = "model-macro-fixture"
CATALOG = "metric-catalog-v0001"
SEEDED = (
    "CN_LPR_1Y_5Y",
    "CN_SF_TOTAL",
    "CN_PMI_ACTIVITY",
    "CN_INDUSTRIAL_VA",
    "CN_GDP",
    "CN_PPI",
    "CN_CPI_HEADLINE",
    "CN_FINISHED_GOODS_INVENTORY",
)
QUARTERS = ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")
LPR_MONTHS = tuple(f"2026-{month:02d}" for month in range(1, 9))


def register_macro_model(paths: RuntimePaths) -> None:
    """A confirmation model with v0016's macro judgement rules, in this run's database."""
    base = certified_model_v0001_manifest()
    base["metric_definitions"] = [
        {**item, "certification_status": "certified"} if item["metric_id"] in SEEDED else item
        for item in base["metric_definitions"]
    ]
    manifest = confirmation_manifest(base)
    manifest.update({"model_version_id": MODEL, MANIFEST_FIELD: rules_v0001()})
    ModelRepository(paths.database).register(manifest)


def take_effect(paths: RuntimePaths, day: str, model: str = MODEL) -> None:
    """The macro rules take effect on ``day``: the first run with them targets it, at that
    day's own evening, so it reads only what was public by then (ADR-0043)."""
    DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), model),
        calendar=TradingCalendar(sessions()),
    ).summarize_target(
        day,
        system_as_of=datetime.combine(date.fromisoformat(day), time(21), tzinfo=SHANGHAI),
        run_materials=RunMaterials(),
    )


def publish_from(paths: RuntimePaths, window: tuple[str, ...], model: str = MODEL) -> ProjectionSet:
    """The target's set after the rules took effect on the window's first day, the run
    filling the days between."""
    take_effect(paths, window[0], model)
    return publish(paths, model, window)


def quarter(repository: EvidenceRepository, values: tuple[float, ...]) -> None:
    """GDP's real growth for the five quarters to June, each out 20 days after it ends."""
    for end, value in zip(QUARTERS, values, strict=True):
        public = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(days=20)
        dimensions = {"aggregate": "total", "measure": "real_quarter_yoy"}
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_GDP",
                definition_version=CATALOG,
                period_kind="quarter",
                period_start=f"{end[:5]}{int(end[5:7]) - 2:02d}-01",
                period_end=end,
                dimensions=dimensions,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="certified-fixture",
                source_reference=f"fixture:CN_GDP:{end}",
                release_event_id=f"release:CN_GDP:{end}",
                release_at=public,
                public_available_at=public,
                fetched_at=public,
                available_at=public,
                certification_status="certified",
                quality_status="validated",
            )
        )


def industrial_va(repository: EvidenceRepository) -> None:
    """Industrial value added rising to the top of its year: never a January, and February
    its cumulative growth."""
    for measure, months in (("current_month_real_yoy", ("01", "02")), ("ytd_real_yoy", None)):
        append(
            repository,
            "CN_INDUSTRIAL_VA",
            {"measure": measure},
            tuple(
                value if (month[5:] not in months if months else month[5:] == "02") else None
                for month, value in zip(TO_JULY, year(5.3, 5.6, 6.0, fill=5.0), strict=True)
            ),
            months=TO_JULY,
            unit="scalar",
            definition_version=CATALOG,
        )


# PPI rising to the top of its year, so prices are up and high.
PPI_HIGH = year(-1.0, -0.4, 0.3, fill=-1.5)


def seed_macro(paths: RuntimePaths, *, ppi: tuple[float, ...] = PPI_HIGH) -> None:
    """The 10-15 hand calculation's shape, out by the target day (2026-08-28): no policy
    action, credit and growth down, prices rising high, inventory actively restocked.

    The PMI's manufacturing falls while its new orders rise, so it diverges; nothing of
    loans or M1/M2 is held. ``ppi`` is the PPI's year, whose place is the prices'.
    """
    repository = EvidenceRepository(paths.database)
    for month in LPR_MONTHS:
        claim(
            repository,
            "CN_LPR_1Y_5Y",
            month,
            {"tenor": "1y"},
            3.0,
            unit="percent",
            definition_version=CATALOG,
        )
    append(
        repository,
        "CN_SF_TOTAL",
        {"measure": "stock_yoy"},
        year(8.4, 8.2, 8.0, fill=8.5),
        months=TO_JULY,
        definition_version=CATALOG,
    )
    append_pmi(
        repository, "manufacturing", (50.6, 50.3, 49.9), months=MONTHS, definition_version=CATALOG
    )
    append_pmi(
        repository, "new_orders", (50.0, 50.5, 51.0), months=MONTHS, definition_version=CATALOG
    )
    industrial_va(repository)
    quarter(repository, (5.4, 5.3, 5.2, 5.0, 4.8))
    append(
        repository,
        "CN_PPI",
        {"category": "headline", "measure": "yoy"},
        ppi,
        months=TO_JULY,
        definition_version=CATALOG,
    )
    append(
        repository,
        "CN_CPI_HEADLINE",
        {"category": "headline", "measure": "yoy"},
        year(0.1, 0.3, 0.5, fill=0.0),
        months=TO_JULY,
        definition_version=CATALOG,
    )
    append(
        repository,
        "CN_FINISHED_GOODS_INVENTORY",
        {"measure": "official_yoy"},
        (3.0, 3.5, 4.0),
        months=MONTHS,
        definition_version=CATALOG,
    )


def judged(tmp_path: Path) -> ProjectionSet:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_macro(paths)
    return publish(paths, MODEL)


def judgement(projection: ProjectionSet) -> dict[str, Any]:
    return projection.datasets["cycle_overview"]["macro_judgement"]  # type: ignore[no-any-return]


def dimension(projection: ProjectionSet, name: str) -> dict[str, Any]:
    return next(item for item in judgement(projection)["dimensions"] if item["dimension"] == name)


def test_v0016_freezes_the_signature_threshold_and_positions_and_v0015_is_unchanged(
    tmp_path: Path,
) -> None:
    v0015, v0016 = model_v0015_manifest(), model_v0016_manifest()

    assert hashlib.sha256(_canonical_json(v0015).encode()).hexdigest() == V0015_HASH
    assert "macro_judgement_rules" not in v0015
    # Everything else is v0015's: the confirmation keeps its cells, caps and loan count.
    added = {"macro_judgement_rules", "macro_signal_rules"}
    assert {key: value for key, value in v0016.items() if key not in added} == {
        **v0015,
        "model_version_id": "model-v0016",
    }
    rules = v0016["macro_judgement_rules"]
    assert rules["threshold"] == 3
    # Loans do not vote in credit (decision 29); positions read one main indicator (25).
    assert rules["voters"] == {
        "credit": ["social_financing", "money"],
        "overheat": ["pmi", "industrial_va", "gdp", "capacity_utilization", "industrial_profit"],
        "price": ["ppi", "cpi", "pmi_prices"],
    }
    assert rules["positions"] == {
        "credit": "social_financing",
        "overheat": "industrial_va",
        "price": "ppi",
    }
    assert rules["policy"] == ["policy_rate", "lpr", "rrr"]
    # Decision 8, Pring's six stages, no cell added to tell I from VI (decision 28).
    assert rules["signature"]["stage_v"] == {
        "policy": {"values": ["tightening", "neutral"]},
        "credit": {"values": ["down"]},
        "overheat": {"values": ["down"], "positions": ["high", "middle"]},
        "price": {"positions": ["high"]},
        "inventory": {"values": ["passive_restocking"]},
    }
    assert rules["signature"]["stage_ii"] == {
        "policy": {"values": ["easing"]},
        "credit": {"values": ["flat", "up"]},
        "overheat": {"values": ["flat", "up"], "positions": ["low"]},
        "price": {"positions": ["low"]},
        "inventory": {"values": ["passive_destocking"]},
    }
    assert [
        {dimension: cell.get("values") for dimension, cell in rules["signature"][stage].items()}
        for stage in ("stage_i", "stage_vi")
    ] == [
        {
            "policy": ["easing"],
            "credit": ["down"],
            "overheat": ["down"],
            "price": ["down"],
            "inventory": ["active_destocking"],
        },
        {
            "policy": ["neutral", "easing"],
            "credit": ["down"],
            "overheat": ["down"],
            "price": ["down"],
            "inventory": ["active_destocking"],
        },
    ]
    assert ContextProjectionRules.from_manifest(v0015).macro_judgement is None
    assert ContextProjectionRules.from_manifest(v0016).macro_judgement is not None
    # The rules are part of the hash: another threshold under the same id is refused.
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    models.create_candidate(v0016)
    edited = copy.deepcopy(v0016)
    edited["macro_judgement_rules"]["threshold"] = 2
    with pytest.raises(ValueError, match="model_version_is_immutable"):
        models.create_candidate(edited)
    # Registered, it is not in effect: the newest model is still v0015, and only an
    # explicit approval moves the pointer.
    assert effective_model_manifest()["model_version_id"] == "model-v0015"
    with pytest.raises(ValueError, match="explicit_model_approval_required"):
        models.activate("model-v0016", explicitly_approved=False)


def test_rules_naming_an_indicator_the_confirmation_lacks_are_refused() -> None:
    manifest = model_v0016_manifest()
    manifest["macro_judgement_rules"]["voters"]["credit"].append("retail_sales")

    with pytest.raises(ValueError, match="macro_judgement_rules_invalid"):
        ContextProjectionRules.from_manifest(manifest)


def test_a_10_15_day_is_stage_v_explicit_four_of_five_two_steps_on_from_stage_iii(
    tmp_path: Path,
) -> None:
    projection = judged(tmp_path)

    overview = projection.datasets["cycle_overview"]
    # The cores rise together: the price stage is theirs, and the last confirmed one.
    assert overview["current_stage"] == overview["last_confirmed_stage"] == "stage_iii"
    published = judgement(projection)
    # Decision 8's hand calculation: I 2, II 0, III 2, IV 2, V 4, VI 3.
    assert published["scores"] == {
        "stage_i": 2,
        "stage_ii": 0,
        "stage_iii": 2,
        "stage_iv": 2,
        "stage_v": 4,
        "stage_vi": 3,
    }
    assert {key: value for key, value in published["conclusion"].items() if key != "formed"} == {
        "stage": "stage_v",
        "confidence": "explicit",
        "matched": 4,
        "known": 5,
        "reference_stage": "stage_iii",
        "steps": 2,
        "direction": "forward",
    }
    assert published["raw"]["stage"] == "stage_v"
    assert published["raw"]["confidence"] == "explicit"
    assert [
        (item["dimension"], item["group"], item["value"], item["position"], item["matches"])
        for item in published["dimensions"]
    ] == [
        ("policy", "monetary", "neutral", None, True),
        ("credit", "monetary", "down", "low", True),
        ("overheat", "economic", "down", "high", True),
        ("price", "economic", "up", "high", True),
        ("inventory", "inventory", "active_restocking", None, False),
    ]


def test_a_divergent_indicator_votes_by_its_main_member(tmp_path: Path) -> None:
    overheat = dimension(judged(tmp_path), "overheat")

    assert [(item["key"], item["vote"], item["divergent"]) for item in overheat["indicators"]] == [
        ("pmi", "down", True),
        ("industrial_va", "up", False),
        ("gdp", "down", False),
        ("capacity_utilization", None, False),
        ("industrial_profit", None, False),
    ]
    assert overheat["basis"] == "majority" and overheat["tally"] == {"down": 2, "up": 1}


def test_loans_stay_out_of_the_credit_vote_and_no_action_is_neutral(tmp_path: Path) -> None:
    projection = judged(tmp_path)
    credit, policy = dimension(projection, "credit"), dimension(projection, "policy")

    # Social financing is the one clear voter of two: loans, unread, are not a third.
    assert [(item["key"], item["voting"], item["vote"]) for item in credit["indicators"]] == [
        ("social_financing", True, "down"),
        ("money", True, None),
        ("loans", False, None),
    ]
    assert credit["value"] == "down" and credit["basis"] == "majority"
    # No cut, LPR cut, RRR cut or hike in the window: neutral, supporting neither side.
    assert policy["value"] == "neutral" and policy["basis"] == "no_action"
    lpr = next(item for item in policy["indicators"] if item["key"] == "lpr")
    assert lpr["action"] == "none" and lpr["actions"] == []


def test_a_backfilled_day_is_judged_by_the_same_rule_at_its_own_cutoff(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_macro(paths)
    window = tuple(day.isoformat() for day in sessions()[-4:])

    publish_from(paths, window)

    for day in window[:-1]:
        conclusion = judgement(summary(paths, day))["conclusion"]
        assert (conclusion["stage"], conclusion["confidence"], conclusion["matched"]) == (
            "stage_v",
            "explicit",
            4,
        )
        assert (conclusion["reference_stage"], conclusion["steps"]) == ("stage_iii", 2)


def test_a_model_without_the_rules_publishes_no_judgement(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths)

    projection = publish(paths, CONFIRMATION_MODEL)

    assert "macro_judgement" not in projection.datasets["cycle_overview"]


@pytest.mark.parametrize(
    "tamper",
    [
        # An explicit stage that is not the unique top score.
        lambda block: (
            block["raw"].update(stage="stage_vi")
            or block["conclusion"].update(stage="stage_vi", steps=3)
        ),
        # Steps the ring does not give from the last confirmed stage.
        lambda block: block["conclusion"].update(steps=-4),
        lambda block: block["conclusion"].update(direction="back"),
        # A score past the dimensions known, or a dimension out of its order.
        lambda block: block["scores"].update(stage_v=6),
        lambda block: block["dimensions"].reverse(),
        # Judged before the rules took effect, or stating no day they took effect on.
        lambda block: block.update(effective_from="2026-08-31"),
        lambda block: block.pop("effective_from"),
        # A dimension marked otherwise than against the conclusion, or one not known marked.
        lambda block: block["dimensions"][4].update(matches=True),
        lambda block: block["dimensions"][0].update(value=None),
        # A conclusion taken from the day's judgement, said to be from another.
        lambda block: block["conclusion"]["formed"].update(basis="tied"),
    ],
)
def test_a_judgement_disagreeing_with_its_own_scores_is_not_published(
    tmp_path: Path, tamper: Any
) -> None:
    projection = judged(tmp_path)
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        validate_analytical_projection(projection.envelope, datasets)
