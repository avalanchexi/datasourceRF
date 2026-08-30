from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock_time
from pathlib import Path
from typing import Any

from pring_cycle.context_projection import (
    ContextProjectionRules,
    build_context_projection,
    context_metric_ids,
)
from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend_history
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository

CALIBRATION_END = "2026-08-19"
CALIBRATION_INPUT_START = "2017-01-01"
CALIBRATION_EXPECTED_DAYS = 1995
CALIBRATION_EXPECTED_INPUT_DAYS = 2338


@dataclass(frozen=True)
class HistoricalEvaluation:
    asset_direction_changes: int
    formal_stage_changes: int
    fast_reversals_20d: int
    median_confirmation_delay_days: int
    evaluated_days: int
    duration_seconds: float
    core_states_by_day: dict[str, tuple[str | None, str | None, str | None]]
    stages_by_day: dict[str, str | None]
    evidence_hash: str = ""
    input_days: int = 0
    input_range_start: str = ""


@dataclass(frozen=True)
class ParallelReplayEvaluation:
    quality_passed: bool
    regression_passed: bool
    performance_passed: bool
    stage_differences: int
    core_state_differences: int
    context_output_differences: int
    gaps: tuple[str, ...]


@dataclass(frozen=True)
class ContextReplayEvaluation:
    context_output_differences: int
    evaluated_cutoffs: int
    duration_seconds: float
    gaps: tuple[str, ...]


def calibrate_model(
    database: Path,
    model_version_id: str,
    *,
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> dict[str, int | str]:
    model = ModelRepository(database).get(model_version_id)
    evaluated = evaluate_history(
        database,
        model_version_id,
        requested_start=requested_start or model.certified_replay_start,
        requested_end=requested_end or CALIBRATION_END,
    )
    if (
        requested_start is None
        and requested_end is None
        and (
            evaluated.evaluated_days != CALIBRATION_EXPECTED_DAYS
            or evaluated.input_days != CALIBRATION_EXPECTED_INPUT_DAYS
            or evaluated.input_range_start != "2017-01-03"
        )
    ):
        raise ValueError("calibration_evidence_incomplete")
    results: dict[str, int | str] = {
        key: int(getattr(evaluated, key))
        for key in CALIBRATION_BASELINE
    }
    results.update(
        {
            "evidence_hash": evaluated.evidence_hash,
            "evaluated_days": evaluated.evaluated_days,
            "input_days": evaluated.input_days,
            "input_range_start": evaluated.input_range_start,
            "range_end": requested_end or CALIBRATION_END,
            "range_start": requested_start or model.certified_replay_start,
        }
    )
    return results


def replay_models(
    database: Path,
    candidate_model_version_id: str,
    comparison_model_version_id: str,
    *,
    requested_start: str,
    requested_end: str,
) -> ParallelReplayEvaluation:
    models = ModelRepository(database)
    candidate = models.get(candidate_model_version_id)
    comparison = models.get(comparison_model_version_id)
    candidate_manifest = models.manifest(candidate_model_version_id)
    comparison_manifest = models.manifest(comparison_model_version_id)
    range_start = max(
        requested_start,
        candidate.certified_replay_start,
        comparison.certified_replay_start,
    )
    candidate_result = evaluate_history(
        database,
        candidate_model_version_id,
        requested_start=range_start,
        requested_end=requested_end,
    )
    comparison_result = evaluate_history(
        database,
        comparison_model_version_id,
        requested_start=range_start,
        requested_end=requested_end,
    )
    days = sorted(
        set(candidate_result.core_states_by_day)
        & set(comparison_result.core_states_by_day)
    )
    context_result = evaluate_context_replay(
        database,
        candidate_manifest,
        comparison_manifest,
        requested_start=range_start,
        requested_end=requested_end,
        replay_days=tuple(days),
    )
    gaps = list(context_result.gaps)
    if not days:
        gaps.append("certified_replay_has_no_common_complete_days")
    stage_differences = sum(
        candidate_result.stages_by_day[day] != comparison_result.stages_by_day[day]
        for day in days
    )
    core_state_differences = sum(
        left != right
        for day in days
        for left, right in zip(
            candidate_result.core_states_by_day[day],
            comparison_result.core_states_by_day[day],
            strict=True,
        )
    )
    quality_passed = bool(days) and not gaps
    regression_passed = (
        quality_passed
        and candidate_result.fast_reversals_20d
        <= comparison_result.fast_reversals_20d
    )
    performance_passed = (
        candidate_result.duration_seconds
        + comparison_result.duration_seconds
        + context_result.duration_seconds
        <= 900
    )
    return ParallelReplayEvaluation(
        quality_passed,
        regression_passed,
        performance_passed,
        stage_differences,
        core_state_differences,
        context_result.context_output_differences,
        tuple(gaps),
    )


def evaluate_history(
    database: Path,
    model_version_id: str,
    *,
    requested_start: str,
    requested_end: str | None,
) -> HistoricalEvaluation:
    started = time.perf_counter()
    models = ModelRepository(database)
    manifest = models.manifest(model_version_id)
    context_rules = ContextProjectionRules.from_manifest(manifest)
    definition_version = context_rules.metric_catalog_version
    rules = _rules(manifest)
    core_metrics = manifest.get("core_metrics")
    if not isinstance(core_metrics, dict):
        raise ValueError("model_core_metrics_missing")
    metric_ids = tuple(str(core_metrics.get(asset, "")) for asset in _ASSETS)
    if any(not metric_id for metric_id in metric_ids):
        raise ValueError("model_core_metrics_invalid")
    evidence = EvidenceRepository(database)
    evidence.preload_metric_series(
        {(metric_id, definition_version) for metric_id in metric_ids}
    )
    end_date = date.fromisoformat(requested_end) if requested_end is not None else date.max
    final_cutoff = datetime.combine(end_date, clock_time.max, UTC)
    final_series = {
        asset: evidence.metric_series(
            metric_id,
            mode=AsOfMode.PUBLIC,
            as_of=final_cutoff,
            definition_version=definition_version,
        )
        for asset, metric_id in zip(_ASSETS, metric_ids, strict=True)
    }
    all_common_days = sorted(
        set.intersection(
            *(set(point.period_end for point in final_series[asset]) for asset in _ASSETS)
        )
    )
    history_input_start = _history_input_start(manifest, requested_start)
    input_days = [
        day
        for day in all_common_days
        if history_input_start <= day <= end_date.isoformat()
    ]
    common_days = [day for day in input_days if requested_start <= day]
    if not input_days or not common_days:
        raise ValueError("calibration_evidence_incomplete")
    points_by_asset = {
        asset: {point.period_end: point for point in final_series[asset]}
        for asset in _ASSETS
    }
    if any(
        points_by_asset[asset][day].selection_status != "selected"
        or points_by_asset[asset][day].selected_value is None
        for asset in _ASSETS
        for day in input_days
    ):
        raise ValueError("calibration_evidence_incomplete")
    evidence_hash = hashlib.sha256(
        json.dumps(
            {
                "definition_version": definition_version,
                "input_range_end": input_days[-1],
                "input_range_start": input_days[0],
                "measurement_range_end": common_days[-1],
                "measurement_range_start": common_days[0],
                "series": {
                    asset: [
                        [day, points_by_asset[asset][day].selected_value]
                        for day in input_days
                    ]
                    for asset in _ASSETS
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    trend_history = {}
    for asset in _ASSETS:
        points: list[PricePoint] = []
        for day in input_days:
            selected_value = points_by_asset[asset][day].selected_value
            if selected_value is None:
                raise ValueError("calibration_evidence_incomplete")
            points.append(
                PricePoint(
                    date.fromisoformat(day),
                    float(selected_value),
                )
            )
        trend_history[asset] = evaluate_trend_history(points, rules)
    trend_by_day = {
        asset: {point.business_date.isoformat(): point for point in trend_history[asset]}
        for asset in _ASSETS
    }

    states_by_day: dict[str, tuple[str | None, str | None, str | None]] = {}
    stages_by_day: dict[str, str | None] = {}
    previous_states: dict[str, CoreAssetState | None] = {asset: None for asset in _ASSETS}
    last_change_index: dict[str, int] = {}
    crossing_onset: dict[tuple[str, CoreAssetState], int] = {}
    confirmation_delays: list[int] = []
    asset_changes = 0
    fast_reversals = 0
    stage_changes = 0
    previous_stage: str | None = None

    measurement_start_index = input_days.index(common_days[0])
    for index, day_text in enumerate(input_days):
        in_measurement_range = index >= measurement_start_index
        daily_states: list[CoreAssetState | None] = []
        for asset in _ASSETS:
            trend = trend_by_day[asset][day_text]
            state = trend.stable_state
            daily_states.append(state)
            position = _ma_position(trend.distance_pct)
            for direction in CoreAssetState:
                key = (asset, direction)
                if direction is not position:
                    crossing_onset.pop(key, None)
            if position is not None and position is not state:
                crossing_onset.setdefault((asset, position), index)
            previous = previous_states[asset]
            if state is not None and previous is not None and state is not previous:
                onset = crossing_onset.pop((asset, state), None)
                if in_measurement_range:
                    asset_changes += 1
                    previous_index = last_change_index.get(asset)
                    if previous_index is not None and index - previous_index <= 20:
                        fast_reversals += 1
                    last_change_index[asset] = index
                    if onset is not None:
                        confirmation_delays.append(index - onset)
            if state is not None:
                previous_states[asset] = state

        if not in_measurement_range:
            continue

        bond, stock, commodity = daily_states
        stage = derive_formal_stage(
            bond=bond,
            stock=stock,
            commodity=commodity,
            last_confirmed_stage=None,
        ).current_stage
        stage_value = stage.value if stage is not None else None
        if stage_value is not None and previous_stage is not None and stage_value != previous_stage:
            stage_changes += 1
        if stage_value is not None:
            previous_stage = stage_value
        states_by_day[day_text] = tuple(
            state.value if state is not None else None for state in daily_states
        )  # type: ignore[assignment]
        stages_by_day[day_text] = stage_value

    median_delay = (
        int(statistics.median(confirmation_delays)) if confirmation_delays else 0
    )
    return HistoricalEvaluation(
        asset_changes,
        stage_changes,
        fast_reversals,
        median_delay,
        len(common_days),
        time.perf_counter() - started,
        states_by_day,
        stages_by_day,
        evidence_hash,
        len(input_days),
        input_days[0],
    )


def _ma_position(distance_pct: float | None) -> CoreAssetState | None:
    if distance_pct is None:
        return None
    if distance_pct > 0:
        return CoreAssetState.BULL
    if distance_pct < 0:
        return CoreAssetState.BEAR
    return None


def _history_input_start(
    manifest: dict[str, object], requested_start: str
) -> str:
    if manifest.get("model_version_id") == "model-v0001":
        return min(CALIBRATION_INPUT_START, requested_start)
    return str(manifest.get("certified_replay_start", requested_start))


def _rules(manifest: dict[str, object]) -> TrendRules:
    document = manifest.get("trend_rules")
    if not isinstance(document, dict):
        raise ValueError("model_trend_rules_missing")
    try:
        return TrendRules(
            window_days=int(document["window_days"]),
            slope_days=int(document["slope_days"]),
            volatility_days=int(document["volatility_days"]),
            noise_multiplier=float(document["noise_multiplier"]),
            persistence_days=int(document["persistence_days"]),
            candidate_window_days=int(document["candidate_window_days"]),
            rule_version=str(document["rule_version"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_trend_rules_invalid") from error


def context_replay_gaps(
    candidate_manifest: dict[str, object],
    comparison_manifest: dict[str, object],
) -> tuple[str, ...]:
    candidate = ContextProjectionRules.from_manifest(candidate_manifest)
    comparison = ContextProjectionRules.from_manifest(comparison_manifest)
    candidate_definitions = {item.metric_id: item for item in candidate.metric_definitions}
    changed_metrics, changed_formulas = _context_changes(candidate, comparison)
    affected_formulas = _affected_context_formulas(changed_metrics, changed_formulas)
    formula_inputs = {
        metric_id
        for key in affected_formulas
        for metric_id in _CONTEXT_FORMULA_INPUTS.get(key, ())
    }
    requires_certification = (changed_metrics - _CONTEXT_DERIVED_OUTPUTS) | formula_inputs
    uncertified = sorted(
        metric_id
        for metric_id in requires_certification
        if (definition := candidate_definitions.get(metric_id)) is None
        or (
            definition.priority in {"P1", "P2"}
            and definition.certification_status != "certified"
        )
    )
    if not uncertified:
        return ()
    return ("candidate_context_sources_uncertified:" + ",".join(uncertified),)


def evaluate_context_replay(
    database: Path,
    candidate_manifest: dict[str, object],
    comparison_manifest: dict[str, object],
    *,
    requested_start: str,
    requested_end: str,
    replay_days: tuple[str, ...] | None = None,
) -> ContextReplayEvaluation:
    started = time.perf_counter()
    start_date = date.fromisoformat(requested_start)
    end_date = date.fromisoformat(requested_end)
    if start_date > end_date:
        raise ValueError("context_replay_range_empty")
    candidate = ContextProjectionRules.from_manifest(candidate_manifest)
    comparison = ContextProjectionRules.from_manifest(comparison_manifest)
    changed_metrics, changed_formulas = _context_changes(candidate, comparison)
    if not changed_metrics and not changed_formulas:
        return ContextReplayEvaluation(0, 0, time.perf_counter() - started, ())

    gaps = list(context_replay_gaps(candidate_manifest, comparison_manifest))
    affected_formulas = _affected_context_formulas(changed_metrics, changed_formulas)
    formula_inputs = {
        metric_id
        for key in affected_formulas
        for metric_id in _CONTEXT_FORMULA_INPUTS.get(key, ())
    }
    source_metrics = (changed_metrics | formula_inputs) - _CONTEXT_DERIVED_OUTPUTS
    candidate_definitions = {item.metric_id: item for item in candidate.metric_definitions}
    comparison_definitions = {
        item.metric_id: item for item in comparison.metric_definitions
    }
    evidence = EvidenceRepository(database)
    public_cutoffs: set[datetime] = set()
    coverage_gaps: list[str] = []
    replay_sources = (
        (
            "candidate",
            candidate.metric_catalog_version,
            candidate_definitions,
        ),
        (
            "comparison",
            comparison.metric_catalog_version,
            comparison_definitions,
        ),
    )
    for side, definition_version, definitions in replay_sources:
        for metric_id in sorted(source_metrics):
            definition = definitions.get(metric_id)
            if (
                definition is None
                or definition.priority not in {"P1", "P2"}
                or definition.certification_status != "certified"
            ):
                continue
            vintages = evidence.source_claim_vintages(
                metric_id,
                definition_version=definition_version,
            )
            coverage_gaps.extend(
                _context_coverage_gaps(
                    side,
                    metric_id,
                    definition.frequency,
                    vintages,
                    start_date=start_date,
                    end_date=end_date,
                    warmup_days=_metric_warmup_days(metric_id, affected_formulas),
                )
            )
            for vintage in vintages:
                public_at = vintage.public_available_at
                if public_at is not None and start_date <= public_at.date() <= end_date:
                    public_cutoffs.add(public_at)
    gaps.extend(coverage_gaps)

    candidate_formula_versions = {
        key: version
        for key in affected_formulas
        if (version := candidate.formula_versions.get(key)) is not None
    }
    if gaps:
        if candidate_formula_versions:
            gaps.append(
                "candidate_context_formula_output_missing:"
                + ",".join(sorted(candidate_formula_versions))
            )
        return ContextReplayEvaluation(
            context_output_differences=0,
            evaluated_cutoffs=0,
            duration_seconds=time.perf_counter() - started,
            gaps=tuple(dict.fromkeys(gaps)),
        )

    evidence.preload_metric_series(
        {
            (metric_id, definition_version)
            for definition_version, metric_ids in (
                (
                    candidate.metric_catalog_version,
                    context_metric_ids(candidate),
                ),
                (
                    comparison.metric_catalog_version,
                    context_metric_ids(comparison),
                ),
            )
            for metric_id in metric_ids
        }
    )

    days = (
        replay_days
        if replay_days is not None
        else _weekday_replay_days(start_date, end_date)
    )
    public_cutoffs.update(
        datetime.combine(date.fromisoformat(day), clock_time.max, UTC)
        for day in days
        if requested_start <= day <= requested_end
    )
    cutoffs = tuple(sorted(public_cutoffs))
    output_differences = 0
    for cutoff in cutoffs:
        for side, definition_version, definitions in replay_sources:
            for metric_id in sorted(source_metrics):
                definition = definitions.get(metric_id)
                if (
                    definition is None
                    or definition.priority not in {"P1", "P2"}
                    or definition.certification_status != "certified"
                ):
                    continue
                gaps.extend(
                    _context_selection_gaps(
                        evidence,
                        side=side,
                        metric_id=metric_id,
                        definition_version=definition_version,
                        frequency=definition.frequency,
                        cutoff=cutoff,
                    )
                )
        try:
            candidate_projection = build_context_projection(
                evidence,
                as_of=cutoff,
                model_manifest=candidate_manifest,
                as_of_mode=AsOfMode.PUBLIC,
                persist_derived=False,
            )
        except ValueError as error:
            gaps.append(f"candidate_context_projection_failed:{error}")
            continue
        try:
            comparison_projection = build_context_projection(
                evidence,
                as_of=cutoff,
                model_manifest=comparison_manifest,
                as_of_mode=AsOfMode.PUBLIC,
                persist_derived=False,
            )
        except ValueError as error:
            gaps.append(f"comparison_context_projection_failed:{error}")
            continue
        candidate_document = {
            "macro": candidate_projection.macro,
            "inventory": candidate_projection.inventory,
        }
        comparison_document = {
            "macro": comparison_projection.macro,
            "inventory": comparison_projection.inventory,
        }
        if _normalized_context(candidate_document) != _normalized_context(
            comparison_document
        ):
            output_differences += 1
        for key, version in candidate_formula_versions.items():
            formula_documents = _formula_documents(candidate_document, version)
            available = [
                item
                for item in formula_documents
                if item.get("status") in {"available", "current"}
            ]
            if not available:
                gaps.append(f"candidate_context_formula_output_missing:{key}")
            elif not any(
                isinstance(item.get("input_observation_version_ids"), list)
                and bool(item["input_observation_version_ids"])
                for item in available
            ):
                gaps.append(f"candidate_context_formula_lineage_missing:{key}")
    return ContextReplayEvaluation(
        context_output_differences=output_differences,
        evaluated_cutoffs=len(cutoffs),
        duration_seconds=time.perf_counter() - started,
        gaps=tuple(dict.fromkeys(gaps)),
    )


def _context_changes(
    candidate: ContextProjectionRules,
    comparison: ContextProjectionRules,
) -> tuple[set[str], set[str]]:
    candidate_definitions = {
        item.metric_id: item for item in candidate.metric_definitions
    }
    comparison_definitions = {
        item.metric_id: item for item in comparison.metric_definitions
    }
    relevant = context_metric_ids(candidate) | context_metric_ids(comparison)
    changed_metrics = {
        metric_id
        for metric_id in relevant
        if candidate_definitions.get(metric_id) != comparison_definitions.get(metric_id)
    }
    changed_formulas = {
        key
        for key in candidate.formula_versions.keys() | comparison.formula_versions.keys()
        if candidate.formula_versions.get(key) != comparison.formula_versions.get(key)
    }
    return changed_metrics, changed_formulas


def _affected_context_formulas(
    changed_metrics: set[str],
    changed_formulas: set[str],
) -> set[str]:
    return changed_formulas | {
        key
        for key, inputs in _CONTEXT_FORMULA_INPUTS.items()
        if changed_metrics & set(inputs)
    }


def _context_coverage_gaps(
    side: str,
    metric_id: str,
    frequency: str,
    vintages: tuple[Any, ...],
    *,
    start_date: date,
    end_date: date,
    warmup_days: int,
) -> list[str]:
    valid = [
        item
        for item in vintages
        if item.certification_status == "certified"
        and item.quality_status == "validated"
        and item.public_available_at is not None
    ]
    if not valid:
        return [f"{side}_context_evidence_missing:{metric_id}"]
    required_start = start_date - timedelta(days=warmup_days)
    earliest_period = min(date.fromisoformat(item.period_start) for item in valid)
    earliest_public = min(item.public_available_at.date() for item in valid)
    latest_period = max(date.fromisoformat(item.period_end) for item in valid)
    gaps = []
    if earliest_period > required_start or earliest_public > start_date:
        gaps.append(f"{side}_context_coverage_start_missing:{metric_id}")
    freshness_days = {"daily": 10, "monthly": 95, "quarterly": 190, "event": 370}.get(
        frequency,
        95,
    )
    if (end_date - latest_period).days > freshness_days:
        gaps.append(f"{side}_context_coverage_end_missing:{metric_id}")
    period_dates = sorted({date.fromisoformat(item.period_end) for item in valid})
    maximum_gap = {"daily": 10, "monthly": 62, "quarterly": 130}.get(frequency)
    if maximum_gap is not None and any(
        (current - previous).days > maximum_gap
        for previous, current in zip(period_dates, period_dates[1:], strict=False)
    ):
        gaps.append(f"{side}_context_coverage_gap:{metric_id}")
    return gaps


def _context_selection_gaps(
    repository: EvidenceRepository,
    *,
    side: str,
    metric_id: str,
    definition_version: str,
    frequency: str,
    cutoff: datetime,
) -> tuple[str, ...]:
    series = repository.metric_series(
        metric_id,
        mode=AsOfMode.PUBLIC,
        as_of=cutoff,
        definition_version=definition_version,
    )
    grouped: dict[str, list[Any]] = {}
    for point in series:
        grouped.setdefault(json.dumps(point.dimensions, sort_keys=True), []).append(point)
    if not grouped:
        return (f"{side}_context_selection_missing:{metric_id}",)
    statuses: set[str] = set()
    required_members = _CONTEXT_REQUIRED_DIMENSION_MEMBERS.get(metric_id, ())
    current_points = [points[-1] for points in grouped.values()]
    latest_period = max(
        (point.period_end, point.period_start) for point in current_points
    )
    observed_dimensions = [
        point.dimensions
        for point in current_points
        if (point.period_end, point.period_start) == latest_period
    ]
    if any(
        not any(
            all(dimensions.get(key) == value for key, value in required.items())
            for dimensions in observed_dimensions
        )
        for required in required_members
    ):
        statuses.add("members_missing")
    freshness_days = {"daily": 10, "monthly": 95, "quarterly": 190, "event": 370}.get(
        frequency,
        95,
    )
    for current in current_points:
        if current.selection_status != "selected":
            statuses.add(current.selection_status)
            continue
        selected = next(
            (
                claim
                for claim in current.claims
                if claim.claim_id == current.selected_claim_id
            ),
            None,
        )
        if (
            selected is None
            or selected.certification_status != "certified"
            or selected.quality_status != "validated"
            or current.value_state is not EvidenceValueState.REPORTED_VALUE
            or current.selected_value is None
        ):
            statuses.add("invalid")
            continue
        period_end = date.fromisoformat(current.period_end)
        if frequency == "daily" and period_end > cutoff.date():
            statuses.add("future")
        elif (cutoff.date() - period_end).days > freshness_days:
            statuses.add("stale")
    return tuple(
        f"{side}_context_selection_{status}:{metric_id}"
        for status in sorted(statuses)
    )


def _metric_warmup_days(metric_id: str, affected_formulas: set[str]) -> int:
    return max(
        (
            _CONTEXT_FORMULA_WARMUP_DAYS.get(key, 0)
            for key in affected_formulas
            if metric_id in _CONTEXT_FORMULA_INPUTS.get(key, ())
        ),
        default=0,
    )


def _weekday_replay_days(start_date: date, end_date: date) -> tuple[str, ...]:
    days = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return tuple(days)


_CONTEXT_VOLATILE_KEYS = {
    "available_at",
    "claim_id",
    "claim_ids",
    "claims",
    "derived_observation_id",
    "evidence_ids",
    "input_observation_version_ids",
    "latest_fetched_at",
    "observation_id",
    "public_available_at",
    "selected_claim_id",
    "source_reference",
}


def _normalized_context(value: object) -> str:
    def normalize(item: object) -> object:
        if isinstance(item, dict):
            return {
                str(key): normalize(child)
                for key, child in sorted(item.items())
                if key not in _CONTEXT_VOLATILE_KEYS
            }
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return item

    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _formula_documents(value: object, formula_version: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("formula_version") == formula_version:
            found.append(value)
        for child in value.values():
            found.extend(_formula_documents(child, formula_version))
    elif isinstance(value, list):
        for child in value:
            found.extend(_formula_documents(child, formula_version))
    return found


_ASSETS = ("bond", "stock", "commodity")

_CONTEXT_FORMULA_INPUTS = {
    "credit_impulse": ("CN_SF_TOTAL", "CN_GDP"),
    "dr007_policy_spread": ("CN_DR007", "CN_OMO_7D_RATE"),
    "loan_monthly_change": ("CN_LOAN_STRUCTURE",),
    "omo_net_injection": ("CN_OMO_7D_AMOUNT",),
    "order_inventory_spread": ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"),
    "production_order_spread": ("CN_PMI_ACTIVITY",),
    "real_inventory_approximation": ("CN_FINISHED_GOODS_INVENTORY", "CN_PPI"),
    "ust_2s10s_spread": ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
}

_CONTEXT_FORMULA_WARMUP_DAYS = {
    "credit_impulse": 730,
    "dr007_policy_spread": 10,
    "loan_monthly_change": 62,
    "omo_net_injection": 10,
    "order_inventory_spread": 62,
    "production_order_spread": 62,
    "real_inventory_approximation": 95,
    "ust_2s10s_spread": 10,
}

_CONTEXT_REQUIRED_DIMENSION_MEMBERS = {
    "CN_LPR_1Y_5Y": (
        {"tenor": "1y"},
        {"tenor": "5y_plus"},
    ),
    "CN_M1_M2": tuple(
        {"aggregate": aggregate, "measure": measure}
        for aggregate in ("m1", "m2")
        for measure in ("balance", "yoy", "mom")
    ),
    "CN_OMO_7D_AMOUNT": (
        {"measure": "injection"},
        {"measure": "maturity"},
    ),
    "CN_PMI_ACTIVITY": (
        {"series": "manufacturing", "measure": "level"},
        {"series": "production", "measure": "level"},
        {"series": "new_orders", "measure": "level"},
        {"series": "purchase_volume", "measure": "level"},
    ),
    "CN_PMI_INVENTORY": (
        {"series": "raw_materials", "measure": "level"},
        {"series": "finished_goods", "measure": "level"},
    ),
    "CN_PMI_PRICES": (
        {"series": "purchase_prices", "measure": "level"},
        {"series": "output_prices", "measure": "level"},
    ),
    "CN_SHIBOR_ON_1W_3M": tuple(
        {"tenor": tenor} for tenor in ("overnight", "1w", "3m")
    ),
    "CN_SF_TOTAL": tuple(
        {"measure": measure}
        for measure in ("monthly_increment", "ytd_increment", "stock_end")
    ),
}

_CONTEXT_DERIVED_OUTPUTS = {
    "CN_CREDIT_IMPULSE",
    "CN_DR007_POLICY_SPREAD",
    "CN_ORDER_INVENTORY_SPREAD",
    "CN_PRODUCTION_ORDER_SPREAD",
    "UST_2S10S_SPREAD",
}
