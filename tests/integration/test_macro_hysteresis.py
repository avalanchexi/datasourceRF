"""The 10-session hysteresis of the macro judgement (ADR-0043, macro stage ticket 05).

A raw judgement other than the main conclusion replaces it only once it has stood ten
sessions running; a run broken on the way starts again, the conclusion unchanged. The
first day without a conclusion before it takes its raw judgement, and a backfilled day
counts on from what the session before it published. The count is frozen in model-v0016.

The macro day is test_macro_judgement's 10-15 shape, stage V (explicit, four of five).
Social financing's July is revised up on a chosen session: from that session's end on,
credit is up, and stages III, IV and V tie at three, a tendency to stage III, the last
confirmed stage of the rising cores (the 10-16 target day's shape).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.day_summary import DaySummaries, ModelRules
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository, model_v0016_manifest
from pring_cycle.projections import ProjectionSetRepository, validate_analytical_projection
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import summary
from tests.integration.test_confirmation_publish import MODEL as CONFIRMATION_MODEL
from tests.integration.test_confirmation_publish import publish, register_confirmation_model
from tests.integration.test_core_carry_forward import CUTOFF, seed_cores, sessions
from tests.integration.test_macro_fallback import seed_combination
from tests.integration.test_macro_judgement import (
    CATALOG,
    MODEL,
    judgement,
    register_macro_model,
    seed_macro,
)
from tests.integration.test_worker_execution import runtime

# Social financing's stock growth in July: as first published, and as revised up.
SF_JULY, SF_REVISED = 8.0, 8.6


def revise_credit(paths: RuntimePaths, value: float, *, on: int) -> None:
    """Social financing's July restated as ``value``, public on ``sessions()[on]``."""
    public = datetime.combine(sessions()[on], time(2), tzinfo=UTC)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_SF_TOTAL",
            definition_version=CATALOG,
            period_kind="month",
            period_start="2026-07-01",
            period_end="2026-07-31",
            dimensions={"measure": "stock_yoy"},
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="certified-fixture",
            source_reference=f"fixture:CN_SF_TOTAL:revised:{on}",
            release_event_id=f"release:CN_SF_TOTAL:revised:{on}",
            release_at=public,
            public_available_at=public,
            fetched_at=public,
            available_at=public,
            certification_status="certified",
            quality_status="validated",
        )
    )


def withhold(paths: RuntimePaths, on: int) -> None:
    """Social financing's, the PPI's and the CPI's July restated as not disclosed, public
    on ``sessions()[on]``: credit and prices are not known, and three dimensions score
    two at most, too little evidence (weak, stage III of the rising cores)."""
    public = datetime.combine(sessions()[on], time(2), tzinfo=UTC)
    for metric_id, dimensions in (
        ("CN_SF_TOTAL", {"measure": "stock_yoy"}),
        ("CN_PPI", {"category": "headline", "measure": "yoy"}),
        ("CN_CPI_HEADLINE", {"category": "headline", "measure": "yoy"}),
    ):
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version=CATALOG,
                period_kind="month",
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions=dimensions,
                value=None,
                value_state=EvidenceValueState.NOT_DISCLOSED,
                unit="percent",
                provider="certified-fixture",
                source_reference=f"fixture:{metric_id}:withheld:{on}",
                release_event_id=f"release:{metric_id}:withheld:{on}",
                release_at=public,
                public_available_at=public,
                fetched_at=public,
                available_at=public,
                certification_status="certified",
                quality_status="validated",
            )
        )


def macro_day(tmp_path: Path) -> RuntimePaths:
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_macro_model(paths)
    seed_macro(paths)
    return paths


def last(count: int) -> tuple[str, ...]:
    return tuple(day.isoformat() for day in sessions()[-count:])


def state(paths: RuntimePaths, day: str) -> tuple[Any, ...]:
    """The day's raw stage, main conclusion and hysteresis, as it published them."""
    block = judgement(summary(paths, day))
    hysteresis = block["hysteresis"]
    return (
        block["raw"]["stage"],
        block["conclusion"]["stage"],
        block["conclusion"]["confidence"],
        hysteresis["basis"],
        hysteresis["candidate"],
        hysteresis["sessions"],
    )


def test_v0016_freezes_the_10_session_hysteresis(tmp_path: Path) -> None:
    v0016 = model_v0016_manifest()

    # Decision 26, the user's "for now": ten sessions, frozen in, changed by a new model.
    assert v0016["macro_judgement_rules"]["hysteresis_sessions"] == 10
    rules = ContextProjectionRules.from_manifest(v0016).macro_judgement
    assert rules is not None and rules.hysteresis_sessions == 10
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    models.create_candidate(v0016)
    edited = copy.deepcopy(v0016)
    edited["macro_judgement_rules"]["hysteresis_sessions"] = 5
    with pytest.raises(ValueError, match="model_version_is_immutable"):
        models.create_candidate(edited)
    edited["macro_judgement_rules"]["hysteresis_sessions"] = 0
    with pytest.raises(ValueError, match="macro_judgement_rules_invalid"):
        ContextProjectionRules.from_manifest(edited)


def test_a_new_judgement_replaces_the_conclusion_on_its_10th_session(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    window = last(12)
    revise_credit(paths, SF_REVISED, on=-10)
    # A first run summarizes the window's first six days; the next one counts on from
    # what they published, and summarizes the rest.
    DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), MODEL),
        calendar=TradingCalendar(sessions()),
    ).backfill(window[:6], target=window[6], system_as_of=CUTOFF)

    publish(paths, MODEL, window)

    assert [state(paths, day) for day in window] == [
        # No conclusion before it: the first day takes its raw judgement.
        ("stage_v", "stage_v", "explicit", "initial", None, 0),
        ("stage_v", "stage_v", "explicit", "agrees", None, 0),
        # Stage III, a tendency, nine sessions running: stage V stays, as it was.
        *(
            ("stage_iii", "stage_v", "explicit", "held", "stage_iii", sessions)
            for sessions in range(1, 10)
        ),
        # The tenth: stage III replaces it.
        ("stage_iii", "stage_iii", "tendency", "replaced", None, 0),
    ]
    ninth = judgement(summary(paths, window[-2]))
    # Held, the conclusion keeps its stage and confidence, scored on the day's dimensions.
    assert ninth["conclusion"] == {
        "stage": "stage_v",
        "confidence": "explicit",
        "matched": 3,
        "known": 5,
        "reference_stage": "stage_iii",
        "steps": 2,
        "direction": "forward",
    }
    assert ninth["hysteresis"]["sessions_required"] == 10
    # The run is listed with the day's signals, two steps back from stage V.
    [progress] = [item for item in ninth["signals"] if item["kind"] == "hysteresis"]
    assert progress == {
        "id": "H",
        "kind": "hysteresis",
        "source": "hysteresis",
        "transition": {"from": "stage_v", "to": "stage_iii"},
        "group": "back",
        "steps": -2,
        "sessions": 9,
        "sessions_required": 10,
    }
    assert not [
        item for item in judgement(summary(paths, window[-1]))["signals"] if item["id"] == "H"
    ]


def test_a_run_broken_on_its_9th_session_is_cleared_and_counts_again_from_one(
    tmp_path: Path,
) -> None:
    paths = macro_day(tmp_path)
    window = last(12)
    revise_credit(paths, SF_REVISED, on=-11)
    # Restated as first published on the ninth session's next, then revised up again.
    revise_credit(paths, SF_JULY, on=-2)
    revise_credit(paths, SF_REVISED, on=-1)

    publish(paths, MODEL, window)

    assert [state(paths, day) for day in window] == [
        ("stage_v", "stage_v", "explicit", "initial", None, 0),
        *(
            ("stage_iii", "stage_v", "explicit", "held", "stage_iii", sessions)
            for sessions in range(1, 10)
        ),
        # Back at stage V: the run is cleared, the conclusion as it was.
        ("stage_v", "stage_v", "explicit", "agrees", None, 0),
        ("stage_iii", "stage_v", "explicit", "held", "stage_iii", 1),
    ]


def test_the_first_day_with_the_rules_takes_its_raw_judgement_at_once(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    register_confirmation_model(paths)
    window = last(3)
    revise_credit(paths, SF_REVISED, on=-12)
    # The days before were summarized on a model without the rules: no judgement.
    DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), CONFIRMATION_MODEL),
        calendar=TradingCalendar(sessions()),
    ).backfill(window[:-1], target=window[-1], system_as_of=CUTOFF)

    published = judgement(publish(paths, MODEL, window))

    # Decision 32: no ten sessions waited for, the day's tendency is the conclusion.
    assert published["conclusion"]["stage"] == published["raw"]["stage"] == "stage_iii"
    assert published["conclusion"]["confidence"] == "tendency"
    assert published["hysteresis"] == {
        "sessions_required": 10,
        "basis": "initial",
        "candidate": None,
        "sessions": 0,
    }
    assert not [item for item in published["signals"] if item["id"] == "H"]


def test_a_change_of_confidence_alone_is_no_new_judgement(tmp_path: Path) -> None:
    # Bonds and stocks falling, commodities rising: stage V is the last confirmed stage,
    # and the tie the revision makes is broken toward it.
    paths = runtime(tmp_path)
    seed_combination(paths, "bear", "bear", "bull")
    register_macro_model(paths)
    seed_macro(paths)
    window = last(2)
    revise_credit(paths, SF_REVISED, on=-1)

    publish(paths, MODEL, window)

    assert [state(paths, day) for day in window] == [
        ("stage_v", "stage_v", "explicit", "initial", None, 0),
        # Stage V again, now tied with III and IV: the conclusion is the day's, at once.
        ("stage_v", "stage_v", "tendency", "agrees", None, 0),
    ]


def test_a_weak_judgement_never_replaces_an_explicit_one(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    window = last(12)
    withhold(paths, on=-11)

    publish(paths, MODEL, window)

    # Decision 44: eleven sessions of stage III, weak, count nothing against stage V.
    assert [state(paths, day) for day in window] == [
        ("stage_v", "stage_v", "explicit", "initial", None, 0),
        *(("stage_iii", "stage_v", "explicit", "held", None, 0) for _ in range(11)),
    ]
    assert not [
        item for item in judgement(summary(paths, window[-1]))["signals"] if item["id"] == "H"
    ]


def _progress(block: dict[str, Any]) -> dict[str, Any]:
    return next(item for item in block["signals"] if item["id"] == "H")  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    "tamper",
    [
        # Held past the sessions a candidate replaces the conclusion on.
        lambda block: block["hysteresis"].update(sessions=10),
        # Agreeing with a raw judgement at another stage, or counting another stage.
        lambda block: block["hysteresis"].update(basis="agrees"),
        lambda block: block["hysteresis"].update(candidate="stage_iv"),
        # Its run left out of the signal list, or listed at another count.
        lambda block: block.update(
            signals=[item for item in block["signals"] if item["id"] != "H"]
        ),
        lambda block: _progress(block).update(sessions=5),
    ],
)
def test_a_hysteresis_out_of_keeping_with_its_judgement_is_not_published(
    tmp_path: Path, tamper: Callable[[dict[str, Any]], None]
) -> None:
    paths = macro_day(tmp_path)
    revise_credit(paths, SF_REVISED, on=-2)
    projection = publish(paths, MODEL, last(3))
    assert state(paths, last(1)[0]) == ("stage_iii", "stage_v", "explicit", "held", "stage_iii", 2)
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        validate_analytical_projection(projection.envelope, datasets)
