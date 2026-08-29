from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from datetime import time as clock_time
from pathlib import Path

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository


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


@dataclass(frozen=True)
class ParallelReplayEvaluation:
    quality_passed: bool
    regression_passed: bool
    performance_passed: bool
    stage_differences: int
    core_state_differences: int
    gaps: tuple[str, ...]


def calibrate_model(
    database: Path,
    model_version_id: str,
    *,
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> dict[str, int]:
    model = ModelRepository(database).get(model_version_id)
    evaluated = evaluate_history(
        database,
        model_version_id,
        requested_start=requested_start or model.certified_replay_start,
        requested_end=requested_end,
    )
    results = {
        key: int(getattr(evaluated, key))
        for key in CALIBRATION_BASELINE
    }
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
    gaps: list[str] = []
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
        candidate_result.duration_seconds + comparison_result.duration_seconds <= 900
    )
    return ParallelReplayEvaluation(
        quality_passed,
        regression_passed,
        performance_passed,
        stage_differences,
        core_state_differences,
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
    rules = _rules(manifest)
    core_metrics = manifest.get("core_metrics")
    if not isinstance(core_metrics, dict):
        raise ValueError("model_core_metrics_missing")
    metric_ids = tuple(str(core_metrics.get(asset, "")) for asset in _ASSETS)
    if any(not metric_id for metric_id in metric_ids):
        raise ValueError("model_core_metrics_invalid")
    evidence = EvidenceRepository(database)
    end_date = date.fromisoformat(requested_end) if requested_end is not None else date.max
    final_cutoff = datetime.combine(end_date, clock_time.max, UTC)
    final_series = {
        asset: evidence.metric_series(metric_id, mode=AsOfMode.PUBLIC, as_of=final_cutoff)
        for asset, metric_id in zip(_ASSETS, metric_ids, strict=True)
    }
    common_days = sorted(
        set.intersection(
            *(set(point.period_end for point in final_series[asset]) for asset in _ASSETS)
        )
    )
    common_days = [
        day for day in common_days if requested_start <= day <= end_date.isoformat()
    ]
    if not common_days:
        raise ValueError("calibration_evidence_incomplete")

    states_by_day: dict[str, tuple[str | None, str | None, str | None]] = {}
    stages_by_day: dict[str, str | None] = {}
    previous_states: dict[str, CoreAssetState | None] = {asset: None for asset in _ASSETS}
    last_change_index: dict[str, int] = {}
    candidate_onset: dict[tuple[str, CoreAssetState], int] = {}
    confirmation_delays: list[int] = []
    asset_changes = 0
    fast_reversals = 0
    stage_changes = 0
    previous_stage: str | None = None

    for index, day_text in enumerate(common_days):
        day = date.fromisoformat(day_text)
        cutoff = datetime.combine(day, clock_time.max, UTC)
        daily_states: list[CoreAssetState | None] = []
        for asset, metric_id in zip(_ASSETS, metric_ids, strict=True):
            series = evidence.metric_series(metric_id, mode=AsOfMode.PUBLIC, as_of=cutoff)
            points = [
                PricePoint(date.fromisoformat(point.period_end), float(point.selected_value))
                for point in series
                if point.period_end <= day_text and point.selected_value is not None
            ]
            trend = evaluate_trend(points, rules)
            state = trend.stable_state
            daily_states.append(state)
            if trend.candidate_30d is not None and trend.candidate_30d is not state:
                candidate_onset.setdefault((asset, trend.candidate_30d), index)
            previous = previous_states[asset]
            if state is not None and previous is not None and state is not previous:
                asset_changes += 1
                previous_index = last_change_index.get(asset)
                if previous_index is not None and index - previous_index < 20:
                    fast_reversals += 1
                last_change_index[asset] = index
                onset = candidate_onset.pop((asset, state), None)
                if onset is not None:
                    confirmation_delays.append(index - onset)
            if state is not None:
                previous_states[asset] = state

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
    )


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


_ASSETS = ("bond", "stock", "commodity")
