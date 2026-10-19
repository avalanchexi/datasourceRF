"""The stage history records each day's macro main conclusion (ADR-0043, macro stage ticket 08).

The rules take effect on the first run's target day with them. From that day on, each
day's stage history row carries that day's main conclusion: its stage and confidence, after
the hysteresis. A day before keeps none, and nothing is judged back for it, whether it was
summarized before, missed or corrected; the hysteresis's run is not recorded, only the
conclusion it leaves standing.

The days are test_macro_hysteresis's: stage V (explicit) until social financing's July is
revised up, then stage III (a tendency), which replaces it on its tenth session.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import pring_cycle.day_summary as day_summary
from pring_cycle.day_summary import DaySummaries, ModelRules
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
)
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_backfill import summary
from tests.integration.test_confirmation_publish import MODEL as CONFIRMATION_MODEL
from tests.integration.test_confirmation_publish import publish, register_confirmation_model
from tests.integration.test_core_carry_forward import CUTOFF, seed_cores, sessions
from tests.integration.test_day_summary import stock_conflict
from tests.integration.test_macro_fallback import seed_policy_and_inventory
from tests.integration.test_macro_hysteresis import SF_REVISED, last, macro_day, revise_credit
from tests.integration.test_macro_judgement import (
    MODEL,
    checked,
    judgement,
    publish_from,
    register_macro_model,
    take_effect,
)
from tests.integration.test_worker_execution import runtime


def macro_rows(projection: ProjectionSet, days: tuple[str, ...]) -> list[tuple[Any, Any]]:
    """Each of ``days``'s macro stage and confidence as the set's stage history shows them."""
    rows = {row["date"]: row for row in projection.datasets["stage_history"]["display"]["days"]}
    return [(rows[day]["macro"], rows[day]["macro_confidence"]) for day in days]


def test_each_day_from_the_rules_on_records_its_main_conclusion_and_none_before(
    tmp_path: Path,
) -> None:
    paths = macro_day(tmp_path)
    register_confirmation_model(paths)
    window = last(14)
    revise_credit(paths, SF_REVISED, on=-10)
    # The first two days were summarized on a model without the rules, which take effect
    # on the third.
    DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), CONFIRMATION_MODEL),
        calendar=TradingCalendar(sessions()),
    ).backfill(window[:2], target=window[2], system_as_of=CUTOFF)
    take_effect(paths, window[2])

    projection = publish(paths, MODEL, window)

    assert macro_rows(projection, window) == [
        # Before the rules: no record, nothing judged back.
        *(("not_effective", None) for _ in range(2)),
        # Stage V from the first day with the rules, also through the nine sessions stage
        # III was counted toward replacing it: the run is not the history's.
        *(("stage_v", "explicit") for _ in range(11)),
        # Its tenth session: stage III, a tendency.
        ("stage_iii", "tendency"),
    ]
    display = projection.datasets["stage_history"]["display"]
    earlier = len(display["days"]) - len(window)
    assert display["macro_counts"] == {
        "unpublished": earlier,
        "not_effective": 2,
        "stage_v:explicit": 11,
        "stage_iii:tendency": 1,
    }


def test_a_day_from_before_the_rules_corrected_with_them_is_still_not_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = macro_day(tmp_path)
    register_confirmation_model(paths)
    window = last(3)
    monkeypatch.setattr(day_summary, "CORE_HISTORY_BASIS", "core-history-v0001")
    DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), CONFIRMATION_MODEL),
        calendar=TradingCalendar(sessions()),
    ).backfill(window[:2], target=window[2], system_as_of=CUTOFF)
    # The first run with the rules holds another core history: both days are corrected.
    monkeypatch.setattr(day_summary, "CORE_HISTORY_BASIS", "core-history-v0002")

    projection = publish(paths, MODEL, window)

    events = {
        event["business_date"]: event for event in projection.datasets["stage_history"]["events"]
    }
    assert [events[day]["corrects"]["reason"] for day in window[:2]] == [
        "core_history_basis_changed"
    ] * 2
    # A correction is no judgement back: the target day is the first with the rules.
    assert macro_rows(projection, window) == [
        ("not_effective", None),
        ("not_effective", None),
        ("stage_v", "explicit"),
    ]
    assert projection.datasets["cycle_overview"]["macro_judgement"]["hysteresis"]["basis"] == (
        "initial"
    )


def test_a_first_run_judges_its_target_alone_and_nothing_before_it(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    window = last(4)

    projection = publish(paths, MODEL, window)

    # The rules take effect on the first run's target day: its missed days, summarized as it
    # initializes, are before it and judged by nothing (decision 5, spec story 33).
    assert macro_rows(projection, window) == [
        *(("not_effective", None) for _ in range(3)),
        ("stage_v", "explicit"),
    ]
    published = projection.datasets["cycle_overview"]["macro_judgement"]
    assert published["effective_from"] == window[-1]
    assert published["hysteresis"]["basis"] == "initial"
    assert all(
        "macro_judgement" not in summary(paths, day).datasets["cycle_overview"]
        for day in window[:-1]
    )


def test_a_day_missed_before_the_rules_took_effect_is_not_judged_back(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    window = last(5)
    take_effect(paths, window[2])

    # A later run fills the window's missed days: those before the rules took effect have no
    # summary yet, and still none is judged; those after count on from its first day.
    projection = publish(paths, MODEL, window)

    assert macro_rows(projection, window) == [
        *(("not_effective", None) for _ in range(2)),
        *(("stage_v", "explicit") for _ in range(3)),
    ]
    blocks = [judgement(summary(paths, day)) for day in window[2:]]
    assert [block["hysteresis"]["basis"] for block in blocks] == ["initial", "agrees", "agrees"]
    assert {block["effective_from"] for block in blocks} == {window[2]}


def _own(datasets: dict[str, Any]) -> dict[str, Any]:
    return datasets["stage_history"]["events"][-1]  # type: ignore[no-any-return]


def _row(datasets: dict[str, Any]) -> dict[str, Any]:
    return datasets["stage_history"]["display"]["days"][-1]  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    "tamper",
    [
        # The day's record states another stage, or another confidence, than its conclusion.
        lambda datasets: _own(datasets).update(
            macro_conclusion={"stage": "stage_iii", "confidence": "explicit"}
        ),
        lambda datasets: _own(datasets).update(
            macro_conclusion={"stage": "stage_v", "confidence": "tendency"}
        ),
        # The day judged, its record left without the conclusion.
        lambda datasets: _own(datasets).pop("macro_conclusion"),
        # A record without a judgement to state it.
        lambda datasets: datasets["cycle_overview"].pop("macro_judgement"),
        # The day's own event left out, so nothing records its conclusion.
        lambda datasets: datasets["stage_history"]["events"].pop(),
        # Its row on the band shows another stage or confidence than its record.
        lambda datasets: _row(datasets).update(macro="stage_iii"),
        lambda datasets: _row(datasets).update(macro_confidence="tendency"),
    ],
)
def test_a_day_recorded_otherwise_than_its_main_conclusion_is_not_published(
    tmp_path: Path, tamper: Callable[[dict[str, Any]], None]
) -> None:
    paths = macro_day(tmp_path)
    window = last(3)
    revise_credit(paths, SF_REVISED, on=-1)
    projection = publish_from(paths, window)
    # Held: stage V stands, though the day's raw judgement is stage III.
    assert macro_rows(projection, window[-1:]) == [("stage_v", "explicit")]
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets)

    with pytest.raises(ValueError, match="projection_stage_history_macro_mismatch"):
        checked(projection.envelope, datasets)


def test_a_day_with_no_stage_to_take_records_so_and_its_relink_records_the_stage_it_takes(
    tmp_path: Path,
) -> None:
    # test_macro_fallback's relink: the stock core held and no stage before it, then the
    # day before summarized with one.
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

    def held_set() -> ProjectionSet:
        [event] = [event for event in repository.stage_history() if event["business_date"] == held]
        return repository.get(str(event["projection_set_id"]))

    # The rules take effect on the held day: the first run with them targets it.
    take_effect(paths, held)
    # Decision 49: nothing to take, a blank of its own, not a day before the rules.
    assert macro_rows(held_set(), (held,)) == [("no_stage", None)]

    summaries.backfill((staged, held), target=days[-1], system_as_of=CUTOFF + timedelta(days=1))

    relinked = held_set()
    # The staged day, before the rules took effect, is not judged back; two dimensions
    # known, the relinked day is weak, on the stage the staged day gives it.
    assert macro_rows(relinked, (staged, held)) == [("not_effective", None), ("stage_iii", "weak")]
    assert relinked.datasets["stage_history"]["events"][-1]["macro_conclusion"] == {
        "stage": "stage_iii",
        "confidence": "weak",
    }
