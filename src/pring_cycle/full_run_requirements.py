from __future__ import annotations

from datetime import date
from typing import Any

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import EvidenceValueState
from pring_cycle.runs import RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.trading_calendar import CalendarMaterialError, SseCalendar


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


# Twelve months (four quarters) and the twelve (four) before them.
CREDIT_IMPULSE_INPUT_PERIODS = {"CN_SF_TOTAL": 24, "CN_GDP": 8}


def credit_lookback_start(metric_id: str, latest_period: str) -> str:
    """The first period the credit impulse reads when its newest is ``latest_period``.

    Flows are differenced from year-to-date figures, so the window needs the period before
    it as well (run findings 2026-09-28, ticket 09).
    """
    return preceding_periods(latest_period, CREDIT_IMPULSE_INPUT_PERIODS[metric_id] + 1)[0]


def formula_requirements(
    rules: ContextProjectionRules,
    selector: ModelInputSelector,
    periods: dict[str, str | None],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: dict[str, int] = {}
    derived = []
    mappings = {
        "credit_impulse": ("CN_CREDIT_IMPULSE", CREDIT_IMPULSE_INPUT_PERIODS),
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
        needs = dict(needs)
        if name == "credit_impulse":
            gdp_end = periods.get("CN_GDP")
            if (
                version in {"credit-impulse-rolling-share-v0001", "credit-impulse-ytd-flow-v0002"}
                and _reported_count(
                    selector, "CN_GDP", {"aggregate": "total", "measure": "nominal_quarterly_level"}
                )
                < 8
                and gdp_end is not None
                and not preceding_periods(gdp_end, 8)[0].endswith("Q1")
            ):
                needs["CN_GDP"] += 1
            sf_end = periods.get("CN_SF_TOTAL")
            if (
                version == "credit-impulse-ytd-flow-v0002"
                and _reported_count(selector, "CN_SF_TOTAL", {"measure": "monthly_increment"}) < 24
                and sf_end is not None
                and not preceding_periods(sf_end, 24)[0].endswith("-01")
            ):
                needs["CN_SF_TOTAL"] += 1
        for source, count in needs.items():
            counts[source] = max(counts.get(source, 1), count)
        derived.append(
            {"metric_id": metric, "formula_version": version, "required_input_periods": needs}
        )
    return counts, derived


def _reported_count(selector: ModelInputSelector, metric: str, dimensions: dict[str, str]) -> int:
    return sum(
        point.dimensions == dimensions
        and point.selection_status == "selected"
        and point.value_state is EvidenceValueState.REPORTED_VALUE
        and point.selected_value is not None
        and any(
            claim.claim_id == point.selected_claim_id and claim.quality_status == "validated"
            for claim in point.claims
        )
        for point in selector.series(metric)
    )


def preceding_periods(period: str, count: int) -> tuple[str, ...]:
    if count == 1:
        return (period,)
    if "-Q" in period:
        year, quarter = period.split("-Q")
        last = int(year) * 4 + int(quarter) - 1
        return tuple(
            f"{ordinal // 4:04d}-Q{ordinal % 4 + 1}"
            for ordinal in range(last - count + 1, last + 1)
        )
    year, month = period[:7].split("-")
    last = int(year) * 12 + int(month) - 1
    return tuple(
        f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"
        for ordinal in range(last - count + 1, last + 1)
    )
