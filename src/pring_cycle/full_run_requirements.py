from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle import credit_impulse
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


def credit_inputs(
    paths: RuntimePaths,
    rules: ContextProjectionRules,
    run: RunRecord,
    *,
    decided_at: datetime,
    window: Collection[date] = (),
    direct_held: Mapping[str, Collection[str]] | None = None,
) -> tuple[credit_impulse.InputPeriods, credit_impulse.InputPeriods]:
    """The target day's minimum credit inputs and what the window's fetch must cover.

    Both come from the model's formula version, one cutoff and the SSE sessions known at
    ``decided_at``: the Worker's fetch and the run's first plan pass the same instant
    (ticket 24). ``window`` defaults to the 120 sessions to the target day, or the target
    day alone while the calendar does not cover them. A formula turned off asks for
    neither.
    """
    target = date.fromisoformat(run.target_business_date)
    sessions = SseCalendar(paths, as_of=_decision_as_of(run, decided_at))
    calendar = sessions.around(target) or current_calendar()
    version = rules.formula_versions.get("credit_impulse")
    cutoff = public_cutoff(run, decided_at)
    minimum = credit_impulse.minimum_requirements(
        version, public_cutoff=cutoff, calendar=calendar, direct_held=direct_held
    )
    coverage = credit_impulse.fetch_coverage(
        version,
        window=window or sessions.window(target, 120) or (target,),
        public_cutoff=cutoff,
        calendar=calendar,
    )
    return minimum, coverage


def formula_requirements(
    rules: ContextProjectionRules,
    credit: tuple[credit_impulse.InputPeriods, credit_impulse.InputPeriods],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """How many periods each formula's inputs need, and each derived metric's entry.

    The credit impulse's inputs are listed by period instead (``credit``: the target day's
    minimum and the window's coverage), so they add no counts here.
    """
    counts: dict[str, int] = {}
    derived = []
    mappings = {
        "credit_impulse": ("CN_CREDIT_IMPULSE", {}),
        "dr007_policy_spread": ("CN_DR007_POLICY_SPREAD", {"CN_DR007": 1, "CN_OMO_7D_RATE": 1}),
        "loan_monthly_change": ("CN_LOAN_STRUCTURE", {"CN_LOAN_STRUCTURE": 2}),
        "omo_net_injection": ("CN_OMO_7D_AMOUNT", {"CN_OMO_7D_AMOUNT": 1}),
        "order_inventory_spread": (
            "CN_ORDER_INVENTORY_SPREAD",
            {"CN_PMI_ACTIVITY": 1, "CN_PMI_INVENTORY": 1},
        ),
        "production_order_spread": ("CN_PRODUCTION_ORDER_SPREAD", {"CN_PMI_ACTIVITY": 1}),
        "real_inventory_approximation": (
            "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
            {"CN_FINISHED_GOODS_INVENTORY": 1, "CN_PPI": 1},
        ),
        "ust_2s10s_spread": (
            "UST_2S10S_SPREAD",
            {"UST2Y_NOMINAL_YIELD": 1, "UST10Y_NOMINAL_YIELD": 1},
        ),
    }
    for name, version in rules.formula_versions.items():
        metric, needs = mappings[name]
        entry: dict[str, Any] = {"metric_id": metric, "formula_version": version}
        if name == "credit_impulse":
            minimum, coverage = credit
            entry["required_input_periods"] = minimum.counts()
            entry["covered_input_periods"] = {
                source: [periods[0], periods[-1]] for source, periods in coverage.periods.items()
            }
        else:
            for source, count in needs.items():
                counts[source] = max(counts.get(source, 1), count)
            entry["required_input_periods"] = dict(needs)
        derived.append(entry)
    return counts, derived
