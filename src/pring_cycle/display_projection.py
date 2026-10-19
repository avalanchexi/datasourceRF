"""Display facts computed once beside the day summary, never by a Web reader.

Chart windows and formula windows are distinct. A missing session remains missing;
neither a short mean nor a carried close can stand in for an actual observation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pring_cycle.catalog import MetricDefinition
from pring_cycle.evidence import MetricSeriesPoint
from pring_cycle.trading_calendar import Sessions, TradingCalendar


def display_days(display: Mapping[str, object]) -> tuple[str, ...]:
    points = display.get("points")
    return (
        tuple(str(point["date"]) for point in points if isinstance(point, dict))
        if isinstance(points, list)
        else ()
    )


def display_versions(display: Mapping[str, object]) -> tuple[str, ...]:
    versions = display.get("input_claim_ids")
    return (
        tuple(item for item in versions if isinstance(item, str))
        if isinstance(versions, list)
        else ()
    )


def coverage_display(
    gaps: Sequence[Mapping[str, object]], model_metrics: set[str]
) -> dict[str, Any]:
    """Count recorded required metric-periods, retaining missing member identities."""

    def coverage(rows: Sequence[Mapping[str, object]]) -> dict[str, Any]:
        counts = Counter(
            "held"
            if row.get("complete")
            else "release_gated"
            # Gated, or let through and not out yet on its source's word (worker gaps 03).
            if row.get("release_gate") or row.get("awaiting_release")
            else "missing"
            for row in rows
        )
        return {
            "total": len(rows),
            "counts": dict(counts),
            "periods": [
                {
                    **{key: value for key, value in row.items() if key != "period"},
                    "required_period": row.get("period"),
                }
                for row in rows
            ],
        }

    return {
        "schema_version": "coverage-v0001",
        "available": bool(gaps),
        "counting_unit": "required_metric_period",
        "model_scope": "core_and_confirmation_requirements",
        "model": coverage([row for row in gaps if row.get("metric_id") in model_metrics]),
        "catalog": coverage(gaps),
    }


def macro_row(event: Mapping[str, Any]) -> tuple[str, str | None]:
    """A day's macro row from its stage history event: its main conclusion's stage and
    confidence; ``not_effective`` for a summary made without the rules, ``no_stage`` for
    one with no stage to take (decision 49), ``unpublished`` with no summary."""
    recorded = event.get("macro_conclusion")
    if not event:
        return "unpublished", None
    if not isinstance(recorded, Mapping):
        return "not_effective", None
    confidence = recorded.get("confidence")
    return str(recorded.get("stage") or "no_stage"), (
        str(confidence) if confidence is not None else None
    )


def history_display(events: Sequence[Mapping[str, Any]], days: Sequence[str]) -> dict[str, Any]:
    """Events are already the repository's daily winners, including correction precedence.

    A day's macro row is its own summary's main conclusion (ADR-0043): ``not_effective``
    when that summary was made without the macro judgement rules, ``no_stage`` when it had
    no stage to take (decision 49); never judged back from another day or the cores.
    """
    by_day = {str(event["business_date"]): event for event in events}
    rows = []
    for day in days:
        event = by_day.get(day, {})
        official = event.get("current_stage") or event.get("stage_reason") or "unpublished"
        assets = {item["asset"]: item for item in event.get("core_assets", [])}
        macro, macro_confidence = macro_row(event)
        recorded = event.get("macro_conclusion")
        note = recorded.get("context_status") if isinstance(recorded, Mapping) else None
        rows.append(
            {
                "date": day,
                "official": official,
                "macro": macro,
                "macro_confidence": macro_confidence,
                # A conclusion kept over a context not recomputed is marked so (F4).
                **({"macro_note": note} if note is not None else {}),
                **{
                    asset: assets.get(asset, {}).get("state") or "unavailable"
                    for asset in ("bond", "stock", "commodity")
                },
                "projection_set_id": event.get("projection_set_id"),
                "assessment_id": event.get("assessment_id"),
                "corrects": event.get("corrects"),
            }
        )
    return {
        "schema_version": "history-display-v0001",
        "days": rows,
        "counts": dict(Counter(item["official"] for item in rows)),
        # A stage counts at each confidence apart: "stage_v:explicit".
        "macro_counts": dict(
            Counter(
                ":".join(filter(None, (item["macro"], item["macro_confidence"]))) for item in rows
            )
        ),
    }


def core_display(
    definition: MetricDefinition,
    series: tuple[MetricSeriesPoint, ...],
    closes: tuple[tuple[str, float], ...],
    *,
    target: date,
    calendar: TradingCalendar,
    reason: str,
    carried: bool,
) -> dict[str, Any]:
    """The already selected, gate-checked core. No claims are reselected here."""
    values = dict(closes)
    observations = {point.period_end: point for point in series}
    known = calendar.stated_to(target)
    points = []
    for day in known[-120:]:
        key = day.isoformat()
        observation = observations.get(key)
        mean: float | None = None
        mean_reason: str | None = None
        try:
            span = calendar.sessions_back(day, 120)
        except LookupError:
            span = ()
            mean_reason = "insufficient_history"
        if span:
            if any(item.isoformat() not in values for item in span):
                mean_reason = "window_session_missing"
            else:
                mean = sum(values[item.isoformat()] for item in span) / 120
        points.append(
            {
                "date": key,
                "value": values.get(key),
                "reason": None if key in values else reason,
                "ma120": mean,
                "ma120_reason": mean_reason,
                "observation_id": observation.observation_id if observation else None,
                "selected_claim_id": observation.selected_claim_id if observation else None,
            }
        )

    def change(count: int) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": None,
            "kind": "return",
            "unit": "percent",
            "sessions": count,
            "start_date": None,
            "end_date": target.isoformat(),
            "reason": None,
            "input_claim_ids": [],
        }
        try:
            span = calendar.sessions_back(target, count + 1)
        except LookupError:
            return {**result, "reason": "trading_calendar_incomplete"}
        start, end = span[0].isoformat(), span[-1].isoformat()
        result["start_date"] = start
        if any(day.isoformat() not in values for day in span):
            return {**result, "reason": "carried_forward" if carried else reason}
        if values[start] == 0:
            return {**result, "reason": "zero_baseline"}
        return {
            **result,
            "value": (values[end] / values[start] - 1) * 100,
            "input_claim_ids": [
                observations[start].selected_claim_id,
                observations[end].selected_claim_id,
            ],
        }

    latest_day = closes[-1][0] if closes else None
    return {
        "schema_version": "display-v0001",
        "metric_id": definition.metric_id,
        "label": definition.name_cn,
        "unit": definition.unit,
        "frequency": definition.frequency,
        "dimensions": series[-1].dimensions if series else {},
        "target_date": target.isoformat(),
        "latest_date": latest_day,
        "latest_value": values.get(latest_day) if latest_day else None,
        "carried_forward": carried,
        "reason": reason,
        "calendar_status": "available" if known else "unavailable",
        "points": points,
        "input_claim_ids": [
            point.selected_claim_id
            for point in series
            if point.period_end in values and point.selected_claim_id
        ],
        "change_5": change(5),
        "change_120": change(120),
    }


def _sessions_back(calendar: Sessions, target: date, count: int) -> tuple[date, ...]:
    if isinstance(calendar, TradingCalendar):
        return calendar.sessions_back(target, count)
    days: list[date] = []
    day = target
    while len(days) < count:
        if calendar.is_trading(day):
            days.append(day)
        day -= timedelta(days=1)
    return tuple(reversed(days))


@dataclass(frozen=True)
class _Reading:
    """One period's shown value and the claims it was read from."""

    value: float
    claim_ids: tuple[str, ...]
    unit: str


def _valid(points: Sequence[MetricSeriesPoint], rejected: set[str]) -> dict[str, MetricSeriesPoint]:
    return {
        point.period_end: point
        for point in points
        if point.selected_value is not None
        and point.selected_claim_id
        and point.selected_claim_id not in rejected
        and point.selection_status == "selected"
    }


def _claim_unit(point: MetricSeriesPoint, default: str) -> str:
    return next(
        (claim.unit for claim in point.claims if claim.claim_id == point.selected_claim_id),
        default,
    )


def context_display(
    definition: MetricDefinition,
    points: Sequence[MetricSeriesPoint],
    *,
    target: date,
    calendar: Sessions | None,
    frequency: str,
    rejected: set[str],
) -> dict[str, Any]:
    """Show original periods; compare daily values only on the registered market calendar."""
    readings = {
        day: _Reading(
            point.selected_value,  # type: ignore[arg-type]
            (str(point.selected_claim_id),),
            _claim_unit(point, definition.unit),
        )
        for day, point in _valid(points, rejected).items()
    }
    return _display(
        definition,
        readings,
        sorted({point.period_end for point in points}),
        target=target,
        calendar=calendar,
        frequency=frequency,
    )


def difference_display(
    definition: MetricDefinition,
    left: Sequence[MetricSeriesPoint],
    right: Sequence[MetricSeriesPoint],
    *,
    multiplier: float,
    target: date,
    calendar: Sessions | None,
    rejected: set[str],
) -> dict[str, Any]:
    """A daily derived difference, ``(left - right) * multiplier`` in the definition's unit,
    shown on each session both inputs hold; its points read the two inputs' claims."""
    lefts, rights = _valid(left, rejected), _valid(right, rejected)
    readings = {
        day: _Reading(
            (float(lefts[day].selected_value) - float(rights[day].selected_value))  # type: ignore[arg-type]
            * multiplier,
            (str(lefts[day].selected_claim_id), str(rights[day].selected_claim_id)),
            definition.unit,
        )
        for day in lefts.keys() & rights.keys()
    }
    return _display(
        definition,
        readings,
        sorted(readings),
        target=target,
        calendar=calendar,
        frequency="daily",
    )


def _display(
    definition: MetricDefinition,
    valid: Mapping[str, _Reading],
    periods: Sequence[str],
    *,
    target: date,
    calendar: Sessions | None,
    frequency: str,
) -> dict[str, Any]:
    latest = max(valid, default=None)
    dates: Sequence[str] = periods[-120:]
    calendar_status = "not_daily" if frequency != "daily" else "unavailable"
    if frequency == "daily" and calendar:
        try:
            dates = [day.isoformat() for day in _sessions_back(calendar, target, 120)]
            calendar_status = "available"
        except LookupError:
            calendar_status = "unavailable"

    def change(count: int) -> dict[str, Any]:
        result: dict[str, Any] = {
            "value": None,
            "start_date": None,
            "end_date": latest,
            "reason": "not_daily" if frequency != "daily" else "trading_calendar_incomplete",
        }
        if frequency != "daily" or calendar is None or latest is None:
            return result
        try:
            span = [
                day.isoformat()
                for day in _sessions_back(calendar, date.fromisoformat(latest), count + 1)
            ]
        except LookupError:
            return result
        result["start_date"] = span[0]
        missing = [day for day in span if day not in valid]
        if missing:
            # Name the sessions the window lacks, so the reader sees which days a "—" waits on.
            return {**result, "reason": "window_session_missing", "missing_dates": missing}
        first, last = valid[span[0]], valid[span[-1]]
        baseline, value, unit = float(first.value), float(last.value), last.unit
        if unit in {"percent", "percentage_points", "basis_points"}:
            delta = (value - baseline) * (1 if unit == "basis_points" else 100)
            kind, shown_unit = "difference", "basis_points"
        elif unit in {"diffusion_index_points"}:
            delta, kind, shown_unit = value - baseline, "difference", unit
        elif baseline == 0:
            return {**result, "reason": "zero_baseline"}
        else:
            delta, kind, shown_unit = (value / baseline - 1) * 100, "return", "percent"
        return {
            **result,
            "value": delta,
            "kind": kind,
            "unit": shown_unit,
            "reason": None,
            "input_claim_ids": [*first.claim_ids, *last.claim_ids],
        }

    def point(day: str) -> dict[str, Any]:
        reading = valid.get(day)
        shown: dict[str, Any] = {
            "date": day,
            "value": reading.value if reading else None,
            "selected_claim_id": (
                reading.claim_ids[0] if reading and len(reading.claim_ids) == 1 else None
            ),
        }
        if reading and len(reading.claim_ids) > 1:
            shown["input_claim_ids"] = list(reading.claim_ids)
        return shown

    return {
        "schema_version": "context-display-v0001",
        "frequency": frequency,
        "unit": definition.unit,
        "calendar_status": calendar_status,
        "points": [point(day) for day in dates],
        "change_5": change(5),
        "change_120": change(120),
    }
