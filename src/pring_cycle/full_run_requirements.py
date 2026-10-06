from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle import lookback
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.runs import RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.trading_calendar import CalendarMaterialError, SseCalendar, current_calendar


def required_calendar(
    paths: RuntimePaths, run: RunRecord, selector: ModelInputSelector
) -> dict[str, Any]:
    """The 120 SSE sessions to the target day, strictly: the calendar, never the prices.

    A full run takes no fewer sessions and no weekday stand-ins; an unreadable calendar
    response not superseded by a newer readable one stops it rather than being skipped. A
    day a later response revised is noted.
    """
    target = date.fromisoformat(run.target_business_date)
    calendar = SseCalendar(paths, as_of=selector.as_of)
    window = calendar.window(target, 120)
    # An unreadable response stops the run unless a newer readable one states the window.
    if (
        unreadable := calendar.unreadable_since(window[0], target)
        if window
        else calendar.unreadable
    ):
        error, receipt = unreadable[0]
        raise CalendarMaterialError(error, receipt) from error
    if not window:
        return {
            "dates": [],
            "basis": "independent_calendar_unavailable",
            "status": "unavailable",
            "provenance": {"claim_ids": [], "acquisition_id": None},
        }
    document: dict[str, Any] = {
        "dates": [day.isoformat() for day in window],
        "basis": "validated_independent_calendar_response",
        "status": "available",
        "provenance": {
            "claim_ids": [],
            "acquisition_id": calendar.sources(target, target)[0],
            "acquisition_ids": list(calendar.sources(window[0], target)),
        },
    }
    if revisions := calendar.revisions_between(window[0], target):
        document["revisions"] = [item.document() for item in revisions]
    return document


def _decision_as_of(run: RunRecord, decided_at: datetime) -> datetime:
    # The selector's instant: the decision's while the acquisition window is open.
    if run.cutoff_mode == "acquisition_window" and not run.cutoffs_frozen:
        return decided_at
    return run.system_as_of


def public_cutoff(run: RunRecord, decided_at: datetime) -> datetime:
    """What the target day's analysis can know of, as decided at ``decided_at``.

    The selector's instant, never past the target day's end.
    """
    target_end = datetime.combine(
        date.fromisoformat(run.target_business_date), time.max, tzinfo=ZoneInfo("Asia/Shanghai")
    )
    return min(_decision_as_of(run, decided_at), decided_at, target_end)


def run_lookback(
    paths: RuntimePaths,
    rules: ContextProjectionRules,
    run: RunRecord,
    *,
    decided_at: datetime,
    window: Collection[date] = (),
    direct_held: Mapping[str, Collection[str]] | None = None,
) -> lookback.Lookback:
    """The model's lookback declaration, resolved for the run's target day and window.

    From one cutoff and the SSE sessions known at ``decided_at``: the Worker's fetch and the
    run's first plan pass the same instant (ticket 24). ``window`` defaults to the 120
    sessions to the target day, or the target day alone while the calendar does not cover
    them. A formula turned off reads nothing.
    """
    target = date.fromisoformat(run.target_business_date)
    sessions = SseCalendar(paths, as_of=_decision_as_of(run, decided_at))
    return lookback.resolve(
        lookback.declare(rules),
        formula_versions=rules.formula_versions,
        window=window or sessions.window(target, 120) or (target,),
        public_cutoff=public_cutoff(run, decided_at),
        calendar=sessions.around(target) or current_calendar(),
        direct_held=direct_held,
    )


def formula_requirements(
    rules: ContextProjectionRules, read: lookback.Lookback
) -> list[dict[str, Any]]:
    """Each derived metric's entry: its formula version and how many periods each input needs.

    A formula read on every day of the window, the credit impulse's, lists its inputs by
    period instead: the target day's minimum, and the first and last periods the window's
    fetch covers.
    """
    derived = []
    for name, version in rules.formula_versions.items():
        metric, _inputs = lookback.FORMULA_INPUTS[name]
        entry: dict[str, Any] = {"metric_id": metric, "formula_version": version}
        if any(item.every_day for item in read.readings if item.reading == name):
            resolved = read.resolved.get(name, lookback.Resolved())
            entry["required_input_periods"] = resolved.minimum.counts()
            entry["covered_input_periods"] = {
                source: [periods[0], periods[-1]]
                for source, periods in resolved.covered.periods.items()
            }
        else:
            entry["required_input_periods"] = {
                item.metric_id: len(item.periods.offsets)
                for item in read.readings
                if item.reading == name
            }
        derived.append(entry)
    return derived
