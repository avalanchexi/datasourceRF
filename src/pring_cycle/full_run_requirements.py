from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from pring_cycle import credit_impulse, lookback
from pring_cycle.context_projection import (
    LOAN_YTD_FORMULA,
    REPO_CALENDAR_FORMULA,
    ContextProjectionRules,
    repo_maturity_trading_day,
)
from pring_cycle.runs import RunRecord, member_key, member_keys
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.summary_cutoff import SummaryCutoff
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


def public_cutoff(run: RunRecord, decided_at: datetime) -> SummaryCutoff:
    """What the target day's summary can know of, as decided at ``decided_at``: what is
    public by the selector's instant, of periods through the target (ADR-0041 2026-10-13).
    """
    return SummaryCutoff.target(run, decided_at)


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
    sessions = SseCalendar(paths, as_of=SummaryCutoff.decision_as_of(run, decided_at))
    return lookback.resolve(
        lookback.declare(rules),
        formula_versions=rules.formula_versions,
        window=window or sessions.window(target, 120) or (target,),
        public_cutoff=public_cutoff(run, decided_at),
        calendar=sessions.around(target) or current_calendar(),
        direct_held=direct_held,
    )


def formula_requirements(
    rules: ContextProjectionRules,
    read: lookback.Lookback,
    *,
    anchors: Mapping[str, str | None] | None = None,
    sessions: Sequence[str] = (),
    direct_held: Mapping[str, Collection[str]] | None = None,
    held: Callable[[str, str, list[str] | None], bool] | None = None,
) -> list[dict[str, Any]]:
    """Each derived metric's entry: its formula version and how many periods each input needs.

    A formula read on every day of the window, the credit impulse's, lists its inputs by
    period instead: the target day's minimum, and the first and last periods the window's
    fetch covers.

    ``formula_inputs`` is what the formula computes from (lookback fetch gaps 16): of each
    input, the periods it reads and the members it reads of each, None for every member the
    catalog requires. The credit impulse reads its minimum, each parent by the measure its
    module reads it by (``direct_held``). Another formula reads back from the input's
    newest period as the plan requires it (``anchors``, sessions counted on ``sessions``),
    or from another input's where it reads that one's period. The repo's net injection
    reads what its version reads on the day (``_repo_inputs``, by what is ``held``).
    """
    derived = []
    anchors = anchors or {}
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
            members = credit_impulse.minimum_members(version, resolved.minimum, direct_held)
            entry["formula_inputs"] = {
                source: {period: [members[source]] for period in periods}
                for source, periods in resolved.minimum.periods.items()
            }
        else:
            entry["required_input_periods"] = {
                item.metric_id: len(item.periods.offsets)
                for item in read.readings
                if item.reading == name
            }
            own = lookback.Lookback(
                tuple(item for item in read.readings if item.reading == name), read.resolved
            )
            inputs: dict[str, dict[str, list[str] | None]] = {}
            for item in own.readings:
                source = item.metric_id
                anchor = anchors.get(lookback.FORMULA_ANCHORS.get(version, {}).get(source, source))
                if anchor is None:
                    continue
                periods = tuple(own.required(source, anchor, sessions=sessions))
                if version == LOAN_YTD_FORMULA and anchor.endswith("-01"):
                    # January's year-to-date figure is the month's change itself.
                    periods = (anchor,)
                named = lookback.FORMULA_MEMBERS.get(name, {}).get(source)
                inputs[source] = {
                    period: None if named is None else list(member_keys(source, named))
                    for period in periods
                }
            if name == "omo_net_injection" and (day := anchors.get("CN_OMO_7D_AMOUNT")):
                inputs = {"CN_OMO_7D_AMOUNT": _repo_inputs(version, day, sessions, held)}
            entry["formula_inputs"] = inputs
        derived.append(entry)
    return derived


def _repo_inputs(
    version: str,
    day: str,
    sessions: Sequence[str],
    held: Callable[[str, str, list[str] | None], bool] | None,
) -> dict[str, list[str] | None]:
    """What the repo's net injection reads on ``day``: the day's injection and maturity.

    The calendar version reads the day's maturity when reported (``held``), else the
    injections maturing then: those of the sessions a week before, rolled to the day.
    """
    injection, maturity = (
        member_key("CN_OMO_7D_AMOUNT", {"measure": measure})
        for measure in ("injection", "maturity")
    )
    if version != REPO_CALENDAR_FORMULA or (
        held is not None and held("CN_OMO_7D_AMOUNT", day, [maturity])
    ):
        return {day: [injection, maturity]}
    target = date.fromisoformat(day)
    days = tuple(date.fromisoformat(session) for session in sessions)
    maturing = (put_in for put_in in days if repo_maturity_trading_day(put_in, days) == target)
    return {**{put_in.isoformat(): [injection] for put_in in maturing}, day: [injection]}


def input_coverage_complete(
    requirement: Mapping[str, Any], held: Callable[[str, str, list[str] | None], bool]
) -> bool:
    """Whether a run holds what a formula computes from (lookback fetch gaps 16).

    Each period of each input it reads must be ``held`` in the members it reads: another
    member of the input's family, or another period, missing leaves its inputs whole. An
    input it reads no period of is not held, and a formula without an input rule never is.
    """
    reads = requirement.get("formula_inputs", {})
    return (
        bool(requirement["required_input_periods"])
        and all(reads.get(metric) for metric in requirement["required_input_periods"])
        and all(
            held(metric, period, members)
            for metric, periods in reads.items()
            for period, members in periods.items()
        )
    )
