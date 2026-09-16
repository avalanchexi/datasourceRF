from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from datetime import time as clock_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.context_projection import (
    ContextProjectionRules,
    TargetBoundEvidenceRepository,
    build_context_projection,
    context_metric_ids,
)
from pring_cycle.context_replay_scope import CONTEXT_FORMULA_INPUTS, ContextReplayScope
from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import (
    PricePoint,
    TrendHistoryPoint,
    TrendRules,
    evaluate_trend_history,
)
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.interbank_evidence import INTERBANK_METRICS, interbank_claims_matching_acquisitions
from pring_cycle.market_amount import AMOUNT_BREADTH_MEASURES
from pring_cycle.market_breadth import (
    DAILY_BREADTH_MEASURES,
    WINDOW_BREADTH_MEASURES,
    breadth_claims_matching_acquisitions,
)
from pring_cycle.metric_contracts import (
    REQUIRED_DIMENSION_MEMBERS,
    evidence_frequency,
    evidence_max_age_days,
    required_dimension_members,
)
from pring_cycle.model_outputs import (
    HISTORY_OUTPUT_SCHEMA,
    REPLAY_OUTPUT_SCHEMA,
    ContextSourcePoints,
    context_output_document,
    core_output_differences,
    model_output_hash,
    model_output_json,
    normalized_context_output,
    validate_replay_output,
)
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.official_context import (
    OFFICIAL_CONTEXT_INTEGRITY_METRICS,
    official_claims_matching_acquisitions,
)
from pring_cycle.official_lpr import lpr_claims_matching_acquisitions
from pring_cycle.published_events import select_published_rrr_events
from pring_cycle.source_adapters import CoreInputValidator
from pring_cycle.treasury_context import TREASURY_METRICS, treasury_claims_matching_acquisitions
from pring_cycle.tushare_context import (
    MARKET_INDEX_IDENTITIES,
    parse_market_index_acquisition,
    parse_valuation_acquisition,
    tushare_claims_matching_acquisitions,
)
from pring_cycle.warrant_inputs import select_warrant_inputs

CALIBRATION_END = "2026-08-19"
CALIBRATION_INPUT_START = "2017-01-01"
CALIBRATION_EXPECTED_DAYS = 1995
CALIBRATION_EXPECTED_INPUT_DAYS = 2338


@dataclass(frozen=True)
class CoreReplayPoint:
    stable_state: str | None
    candidate_state: str | None
    actual_candidate_days: int
    candidate_days: int
    confirmation_threshold_days: int


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
    core_outputs_by_day: dict[str, dict[str, CoreReplayPoint]] = field(default_factory=dict)
    candidate_duration_rule_version: str = "candidate-duration-v0001"


@dataclass(frozen=True)
class ParallelReplayEvaluation:
    quality_passed: bool
    regression_passed: bool
    performance_passed: bool
    stage_differences: int
    core_state_differences: int
    context_output_differences: int
    gaps: tuple[str, ...]
    evaluated_trading_days: int
    calendar_hash: str
    evaluated_range_start: str
    evaluated_range_end: str
    candidate_state_differences: int | None = None
    candidate_days_differences: int | None = None
    core_output_hash: str | None = None
    core_output_document: dict[str, Any] | None = None
    context_output_hash: str | None = None
    context_output_document: dict[str, Any] | None = None


@dataclass(frozen=True)
class ContextReplayEvaluation:
    context_output_differences: int
    evaluated_cutoffs: int
    duration_seconds: float
    gaps: tuple[str, ...]
    output_document: dict[str, Any]


def calibrate_model(
    database: Path,
    model_version_id: str,
    *,
    requested_start: str | None = None,
    requested_end: str | None = None,
) -> dict[str, Any]:
    models = ModelRepository(database)
    model = models.get(model_version_id)
    manifest = models.manifest(model_version_id)
    calibration_start = str(manifest.get("calibration_range_start", model.certified_replay_start))
    evaluated = evaluate_history(
        database,
        model_version_id,
        requested_start=requested_start or calibration_start,
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
    results: dict[str, Any] = {key: int(getattr(evaluated, key)) for key in CALIBRATION_BASELINE}
    results.update(
        {
            "evidence_hash": evaluated.evidence_hash,
            "evaluated_days": evaluated.evaluated_days,
            "input_days": evaluated.input_days,
            "input_range_start": evaluated.input_range_start,
            "range_end": requested_end or CALIBRATION_END,
            "range_start": requested_start or calibration_start,
        }
    )
    output = history_output_document(
        evaluated,
        manifest,
        manifest_hash=model.manifest_hash,
        range_start=str(results["range_start"]),
        range_end=str(results["range_end"]),
    )
    results["core_output_document"] = output
    results["core_output_hash"] = model_output_hash(output)
    return results


def history_output_document(
    evaluated: HistoricalEvaluation,
    manifest: Mapping[str, Any],
    *,
    manifest_hash: str,
    range_start: str,
    range_end: str,
) -> dict[str, Any]:
    days = sorted(evaluated.core_outputs_by_day)
    return {
        "schema_version": HISTORY_OUTPUT_SCHEMA,
        "model_version_id": manifest["model_version_id"],
        "manifest_hash": manifest_hash,
        "candidate_duration_rule_version": evaluated.candidate_duration_rule_version,
        "as_of_mode": "public_as_of",
        "range_start": range_start,
        "range_end": range_end,
        "evidence_hash": evaluated.evidence_hash,
        "calendar_hash": hashlib.sha256("\n".join(days).encode()).hexdigest(),
        "asset_days": len(days) * 3,
        "days": [
            {
                "business_date": day,
                "cutoff": _china_business_day_end(date.fromisoformat(day)).isoformat(),
                "assets": {
                    asset: asdict(point)
                    for asset, point in evaluated.core_outputs_by_day[day].items()
                },
                "stage": evaluated.stages_by_day[day],
            }
            for day in days
        ],
    }


def replay_models(
    database: Path,
    candidate_model_version_id: str,
    comparison_model_version_id: str,
    *,
    requested_start: str,
    requested_end: str,
) -> ParallelReplayEvaluation:
    if candidate_model_version_id == comparison_model_version_id:
        raise ValueError("model_replay_self_comparison_forbidden")
    models = ModelRepository(database)
    if models.active().model_version_id != comparison_model_version_id:
        raise ValueError("model_replay_comparison_must_be_active")
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
        set(candidate_result.core_states_by_day) & set(comparison_result.core_states_by_day)
    )
    calendar_hash = hashlib.sha256("\n".join(days).encode()).hexdigest() if days else ""
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
    required_days = int(candidate_manifest.get("visible_evidence_window_trading_days", 0))
    if required_days > 0 and len(days) != required_days:
        gaps.append(f"certified_replay_trading_days_invalid:{len(days)}:{required_days}")
    if days and (days[0] != range_start or days[-1] != requested_end):
        gaps.append("certified_replay_range_not_exact")
    stage_differences = sum(
        candidate_result.stages_by_day[day] != comparison_result.stages_by_day[day] for day in days
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
    core_output_document = None
    core_output_hash = None
    candidate_state_differences = None
    candidate_days_differences = None
    try:
        candidate_output = history_output_document(
            candidate_result,
            candidate_manifest,
            manifest_hash=candidate.manifest_hash,
            range_start=range_start,
            range_end=requested_end,
        )
        comparison_output = history_output_document(
            comparison_result,
            comparison_manifest,
            manifest_hash=comparison.manifest_hash,
            range_start=range_start,
            range_end=requested_end,
        )
        differences = core_output_differences(candidate_output, comparison_output)
        state_count = sum(item["field"] == "candidate_state" for item in differences)
        days_count = sum(item["field"] == "candidate_days" for item in differences)
        core_output_document = validate_replay_output(
            {
                "schema_version": REPLAY_OUTPUT_SCHEMA,
                "range_start": range_start,
                "range_end": requested_end,
                "calendar_hash": calendar_hash,
                "candidate": candidate_output,
                "comparison": comparison_output,
                "differences": differences,
            },
            candidate_manifest=candidate_manifest,
            comparison_manifest=comparison_manifest,
            candidate_manifest_hash=candidate.manifest_hash,
            comparison_manifest_hash=comparison.manifest_hash,
            range_start=range_start,
            range_end=requested_end,
            evaluated_days=len(days),
            calendar_hash=calendar_hash,
            stage_differences=stage_differences,
            core_state_differences=core_state_differences,
            candidate_state_differences=state_count,
            candidate_days_differences=days_count,
        )
        core_output_hash = model_output_hash(core_output_document)
        candidate_state_differences = state_count
        candidate_days_differences = days_count
    except (KeyError, TypeError, ValueError):
        gaps.append("core_candidate_outputs_incomplete")
    quality_passed = bool(days) and not gaps
    regression_passed = (
        quality_passed
        and candidate_result.fast_reversals_20d <= comparison_result.fast_reversals_20d
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
        len(days),
        calendar_hash,
        days[0] if days else range_start,
        days[-1] if days else requested_end,
        candidate_state_differences,
        candidate_days_differences,
        core_output_hash,
        core_output_document,
        model_output_hash(context_result.output_document),
        context_result.output_document,
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
    evidence.preload_metric_series({(metric_id, definition_version) for metric_id in metric_ids})
    end_date = date.fromisoformat(requested_end) if requested_end is not None else date.max
    # Discover expected recorded dates without hiding unknown or late PUBLIC claims.
    # Vintage metadata contributes dates only; all prices are selected at daily cutoffs.
    vintages = tuple(
        vintage
        for metric_id in metric_ids
        for vintage in evidence.source_claim_vintages(
            metric_id, definition_version=definition_version
        )
    )
    all_observed_days = sorted({vintage.period_end for vintage in vintages})
    history_input_start = _history_input_start(manifest, requested_start)
    input_days = [
        day for day in all_observed_days if history_input_start <= day <= end_date.isoformat()
    ]
    common_days = [day for day in input_days if requested_start <= day]
    if not input_days or not common_days:
        raise ValueError("calibration_evidence_incomplete")
    core_inputs = CoreInputValidator(
        evidence,
        tuple(
            vintage.claim_id
            for vintage in vintages
            if definition_version not in BUILTIN_CATALOG_VERSIONS
            and history_input_start <= vintage.period_end <= input_days[-1]
        ),
    )
    evidence_digest = hashlib.sha256(
        json.dumps(
            {
                "schema_version": "core-public-input-path-v0001",
                "definition_version": definition_version,
                "input_range_end": input_days[-1],
                "input_range_start": input_days[0],
                "measurement_range_end": common_days[-1],
                "measurement_range_start": common_days[0],
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    trend_by_day: dict[str, dict[str, TrendHistoryPoint]] = {}
    for asset, metric_id in zip(_ASSETS, metric_ids, strict=True):
        trend_by_day[asset] = {}
        previous_points: list[PricePoint] = []
        segment_start = 0
        for index, day in enumerate(input_days):
            cutoff = _china_business_day_end(date.fromisoformat(day))
            visible = {
                point.period_end: point
                for point in evidence.metric_series(
                    metric_id,
                    mode=AsOfMode.PUBLIC,
                    as_of=cutoff,
                    definition_version=definition_version,
                )
                if history_input_start <= point.period_end <= day
            }
            prefix = input_days[: index + 1]
            if any(
                prior not in visible
                or visible[prior].selection_status != "selected"
                or (value := visible[prior].selected_value) is None
                or value <= 0
                for prior in prefix
            ):
                raise ValueError("calibration_evidence_incomplete")
            selected = [visible[prior] for prior in prefix]
            if any(
                point.value_state is not EvidenceValueState.REPORTED_VALUE
                or not any(
                    claim.claim_id == point.selected_claim_id
                    and claim.certification_status == "certified"
                    and claim.quality_status == "validated"
                    for claim in point.claims
                )
                for point in selected
            ):
                raise ValueError("calibration_evidence_incomplete")
            if definition_version not in BUILTIN_CATALOG_VERSIONS and any(
                not core_inputs.is_valid(metric_id, point) for point in selected
            ):
                raise ValueError("calibration_core_original_invalid")
            evidence_digest.update(
                json.dumps(
                    {
                        "asset": asset,
                        "cutoff": cutoff.isoformat(),
                        "inputs": [
                            [
                                point.period_end,
                                point.observation_id,
                                point.selected_claim_id,
                                point.selected_value,
                            ]
                            for point in selected
                        ],
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
                + b"\n"
            )
            points = [
                PricePoint(date.fromisoformat(point.period_end), float(point.selected_value))
                for point in selected
                if point.selected_value is not None
            ]
            # Extending an unchanged positive price prefix cannot revise earlier trends.
            # Recompute the full prefix only across actual historical price revisions,
            # retaining outputs only for the cutoffs that selected that version.
            if previous_points and points[:-1] != previous_points:
                trend_by_day[asset].update(_trend_segment(previous_points, rules, segment_start))
                segment_start = index
            previous_points = points
        trend_by_day[asset].update(_trend_segment(previous_points, rules, segment_start))

    states_by_day: dict[str, tuple[str | None, str | None, str | None]] = {}
    stages_by_day: dict[str, str | None] = {}
    core_outputs_by_day: dict[str, dict[str, CoreReplayPoint]] = {}
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

        core_outputs_by_day[day_text] = {}
        for asset in _ASSETS:
            trend = trend_by_day[asset][day_text]
            core_outputs_by_day[day_text][asset] = CoreReplayPoint(
                stable_state=trend.stable_state.value if trend.stable_state is not None else None,
                candidate_state=trend.candidate_state.value
                if trend.candidate_state is not None
                else None,
                actual_candidate_days=trend.candidate_days,
                candidate_days=rules.candidate_days_for_output(trend),
                confirmation_threshold_days=rules.persistence_days,
            )

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

    median_delay = int(statistics.median(confirmation_delays)) if confirmation_delays else 0
    return HistoricalEvaluation(
        asset_changes,
        stage_changes,
        fast_reversals,
        median_delay,
        len(common_days),
        time.perf_counter() - started,
        states_by_day,
        stages_by_day,
        evidence_digest.hexdigest(),
        len(input_days),
        input_days[0],
        core_outputs_by_day,
        rules.candidate_duration_rule_version,
    )


def _trend_segment(
    points: list[PricePoint],
    rules: TrendRules,
    start_index: int,
) -> dict[str, TrendHistoryPoint]:
    return {
        point.business_date.isoformat(): point
        for point in evaluate_trend_history(points, rules)[start_index:]
    }


def _ma_position(distance_pct: float | None) -> CoreAssetState | None:
    if distance_pct is None:
        return None
    if distance_pct > 0:
        return CoreAssetState.BULL
    if distance_pct < 0:
        return CoreAssetState.BEAR
    return None


def _history_input_start(manifest: dict[str, object], requested_start: str) -> str:
    if manifest.get("model_version_id") == "model-v0001":
        return min(CALIBRATION_INPUT_START, requested_start)
    return min(
        str(manifest.get("history_input_start", manifest.get("certified_replay_start"))),
        requested_start,
    )


def _rules(manifest: dict[str, object]) -> TrendRules:
    document = manifest.get("trend_rules")
    if not isinstance(document, dict):
        raise ValueError("model_trend_rules_missing")
    duration_version = str(
        document.get("candidate_duration_rule_version", "candidate-duration-v0001")
    )
    if duration_version not in {"candidate-duration-v0001", "candidate-duration-v0002"}:
        raise ValueError("candidate_duration_rule_version_unsupported")
    try:
        return TrendRules(
            window_days=int(document["window_days"]),
            slope_days=int(document["slope_days"]),
            volatility_days=int(document["volatility_days"]),
            noise_multiplier=float(document["noise_multiplier"]),
            persistence_days=int(document["persistence_days"]),
            candidate_window_days=int(document["candidate_window_days"]),
            rule_version=str(document["rule_version"]),
            candidate_duration_rule_version=duration_version,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_trend_rules_invalid") from error


def context_replay_gaps(
    candidate_manifest: dict[str, object],
    comparison_manifest: dict[str, object],
) -> tuple[str, ...]:
    scope = ContextReplayScope.from_manifests(candidate_manifest, comparison_manifest)
    candidate = scope.candidate
    candidate_definitions = {item.metric_id: item for item in candidate.metric_definitions}
    uncertified = sorted(
        metric_id
        for metric_id in scope.requires_certification
        if (definition := candidate_definitions.get(metric_id)) is None
        or definition.certification_status != "certified"
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
    from pring_cycle.futures_input_reads import shared_futures_input_reads

    # A replay only reads captured futures inputs, so every cutoff shares one read of them.
    with shared_futures_input_reads():
        return _evaluate_context_replay(
            database,
            candidate_manifest,
            comparison_manifest,
            requested_start=requested_start,
            requested_end=requested_end,
            replay_days=replay_days,
        )


def _evaluate_context_replay(
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
    days = replay_days if replay_days is not None else _weekday_replay_days(start_date, end_date)
    scope = ContextReplayScope.from_manifests(candidate_manifest, comparison_manifest)
    candidate, comparison = scope.candidate, scope.comparison
    if not scope.requires_replay:
        return ContextReplayEvaluation(
            0,
            0,
            time.perf_counter() - started,
            (),
            context_output_document(
                candidate_manifest,
                comparison_manifest,
                range_start=requested_start,
                range_end=requested_end,
                expected_days=days,
                days=[],
                source_metrics=set(),
                formula_keys=set(),
                gaps=(),
                not_applicable=True,
            ),
        )

    gaps = list(context_replay_gaps(candidate_manifest, comparison_manifest))
    affected_formulas = scope.formula_keys
    candidate_definitions = {item.metric_id: item for item in candidate.metric_definitions}
    comparison_definitions = {item.metric_id: item for item in comparison.metric_definitions}
    source_metrics = scope.source_metrics
    evidence = EvidenceRepository(database)
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
        for metric_id in sorted(source_metrics & scope.requires_certification):
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
                    required_days=days,
                )
            )
    gaps.extend(coverage_gaps)

    candidate_formula_versions = {
        key: version
        for key in affected_formulas
        if (version := candidate.formula_versions.get(key)) is not None
    }
    if gaps:
        missing_formulas = scope.required_formula_keys & candidate_formula_versions.keys()
        if missing_formulas:
            gaps.append(
                "candidate_context_formula_output_missing:" + ",".join(sorted(missing_formulas))
            )
        return ContextReplayEvaluation(
            context_output_differences=0,
            evaluated_cutoffs=0,
            duration_seconds=time.perf_counter() - started,
            gaps=tuple(dict.fromkeys(gaps)),
            output_document=context_output_document(
                candidate_manifest,
                comparison_manifest,
                range_start=requested_start,
                range_end=requested_end,
                expected_days=days,
                days=[],
                source_metrics=source_metrics,
                formula_keys=affected_formulas,
                gaps=tuple(dict.fromkeys(gaps)),
            ),
        )

    preload_metrics = {
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
    for manifest, definition_version in (
        (candidate_manifest, candidate.metric_catalog_version),
        (comparison_manifest, comparison.metric_catalog_version),
    ):
        core_metrics = manifest.get("core_metrics")
        if isinstance(core_metrics, dict):
            stock_metric_id = core_metrics.get("stock")
            if isinstance(stock_metric_id, str) and stock_metric_id:
                preload_metrics.add((stock_metric_id, definition_version))
    evidence.preload_metric_series(preload_metrics)

    cutoffs = tuple(
        _china_business_day_end(date.fromisoformat(day))
        for day in days
        if requested_start <= day <= requested_end
    )
    output_differences = 0
    output_days: list[dict[str, Any]] = []
    # Each day's full visible history repeats earlier days; store each point once.
    source_points = ContextSourcePoints()
    for cutoff in cutoffs:
        for side, definition_version, definitions in replay_sources:
            for metric_id in sorted(source_metrics & scope.requires_certification):
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
                        database_path=database,
                        artifacts=database.parent / "artifacts" / "sha256",
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
                target_business_date=cutoff.astimezone(ZoneInfo("Asia/Shanghai"))
                .date()
                .isoformat(),
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
                target_business_date=cutoff.astimezone(ZoneInfo("Asia/Shanghai"))
                .date()
                .isoformat(),
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
        output_days.append(
            {
                "business_date": cutoff.date().isoformat(),
                "cutoff": cutoff.isoformat(),
                "candidate": {
                    **json.loads(model_output_json(asdict(candidate_projection))),
                    "source_inputs": source_points.references(
                        _context_source_snapshot(evidence, candidate, source_metrics, cutoff)
                    ),
                },
                "comparison": {
                    **json.loads(model_output_json(asdict(comparison_projection))),
                    "source_inputs": source_points.references(
                        _context_source_snapshot(evidence, comparison, source_metrics, cutoff)
                    ),
                },
            }
        )
        if normalized_context_output(candidate_document) != normalized_context_output(
            comparison_document
        ):
            output_differences += 1
        for key, version in candidate_formula_versions.items():
            formula_documents = _formula_documents(candidate_document, version)
            available = [
                item for item in formula_documents if item.get("status") in {"available", "current"}
            ]
            if not available:
                if key in scope.required_formula_keys:
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
        output_document=context_output_document(
            candidate_manifest,
            comparison_manifest,
            range_start=requested_start,
            range_end=requested_end,
            expected_days=days,
            days=output_days,
            source_metrics=source_metrics,
            formula_keys=affected_formulas,
            gaps=tuple(dict.fromkeys(gaps)),
            source_points=source_points,
        ),
    )


def _context_source_snapshot(
    evidence: EvidenceRepository,
    rules: ContextProjectionRules,
    metric_ids: set[str],
    cutoff: datetime,
) -> dict[str, list[dict[str, Any]]]:
    definitions = {item.metric_id: item for item in rules.metric_definitions}
    bounded = TargetBoundEvidenceRepository(
        evidence,
        cutoff.astimezone(ZoneInfo("Asia/Shanghai")).date(),
        {item.metric_id: item.frequency for item in rules.metric_definitions},
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for metric_id in sorted(metric_ids):
        result[metric_id] = []
        if metric_id not in definitions:
            continue
        series = bounded.metric_series(
            metric_id,
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
            definition_version=rules.metric_catalog_version,
        )
        # Coverage and derived inputs can depend on older periods even when
        # the current card and its direction are unchanged.
        for point in sorted(
            series,
            key=lambda p: (
                p.period_end,
                p.period_start,
                model_output_json(p.dimensions),
                p.observation_id,
            ),
        ):
            result[metric_id].append(
                {
                    "definition_version": rules.metric_catalog_version,
                    "period_start": point.period_start,
                    "period_end": point.period_end,
                    "dimensions": point.dimensions,
                    "observation_id": point.observation_id,
                    "selected_claim_id": point.selected_claim_id,
                    "selected_value": point.selected_value,
                    "selection_status": point.selection_status,
                    "value_state": point.value_state.value
                    if point.value_state is not None
                    else None,
                    "claims": [
                        {
                            "claim_id": claim.claim_id,
                            "provider": claim.provider,
                            "value": claim.value,
                            "unit": claim.unit,
                            "public_available_at": claim.public_available_at.isoformat()
                            if claim.public_available_at
                            else None,
                            "available_at": claim.available_at.isoformat(),
                            "source_reference": claim.source_reference,
                            "certification_status": claim.certification_status,
                            "quality_status": claim.quality_status,
                        }
                        for claim in point.claims
                    ],
                }
            )
    return result


def _china_business_day_end(day: date) -> datetime:
    return datetime.combine(day, clock_time.max, ZoneInfo("Asia/Shanghai"))


def _context_coverage_gaps(
    side: str,
    metric_id: str,
    frequency: str,
    vintages: tuple[Any, ...],
    *,
    start_date: date,
    end_date: date,
    warmup_days: int,
    required_days: tuple[str, ...] | None = None,
) -> list[str]:
    valid = [
        item
        for item in vintages
        if item.certification_status == "certified"
        and item.quality_status == "validated"
        and item.public_available_at is not None
    ]
    required_members = (
        REQUIRED_DIMENSION_MEMBERS.get(metric_id, ()) if metric_id == "CN_FUTURES_WARRANTS" else ()
    )
    if required_members:
        gaps: list[str] = []
        for required in required_members:
            member_vintages = tuple(
                item
                for item in valid
                if all(item.dimensions.get(key) == value for key, value in required.items())
            )
            member = ",".join(f"{key}={value}" for key, value in sorted(required.items()))
            gaps.extend(
                _single_context_coverage_gaps(
                    side,
                    metric_id,
                    frequency,
                    member_vintages,
                    start_date=start_date,
                    end_date=end_date,
                    warmup_days=warmup_days,
                    member=member,
                    required_days=required_days,
                )
            )
        return list(dict.fromkeys(gaps))
    return _single_context_coverage_gaps(
        side,
        metric_id,
        frequency,
        tuple(valid),
        start_date=start_date,
        end_date=end_date,
        warmup_days=warmup_days,
        required_days=required_days,
    )


def _single_context_coverage_gaps(
    side: str,
    metric_id: str,
    frequency: str,
    valid: tuple[Any, ...],
    *,
    start_date: date,
    end_date: date,
    warmup_days: int,
    member: str | None = None,
    required_days: tuple[str, ...] | None = None,
) -> list[str]:
    frequency = evidence_frequency(metric_id, frequency)
    suffix = f":[{member}]" if member is not None else ""
    if not valid:
        return [f"{side}_context_evidence_missing:{metric_id}{suffix}"]
    required_start = start_date - timedelta(days=warmup_days)
    earliest_period = min(date.fromisoformat(item.period_start) for item in valid)
    earliest_public = min(item.public_available_at.date() for item in valid)
    latest_period = max(date.fromisoformat(item.period_end) for item in valid)
    gaps = []
    if earliest_period > required_start or earliest_public > start_date:
        gaps.append(f"{side}_context_coverage_start_missing:{metric_id}{suffix}")
    freshness_days = evidence_max_age_days(metric_id, frequency)
    if (end_date - latest_period).days > freshness_days:
        gaps.append(f"{side}_context_coverage_end_missing:{metric_id}{suffix}")
    period_dates = sorted({date.fromisoformat(item.period_end) for item in valid})
    maximum_gap = {"daily": 14, "monthly": 62, "quarterly": 130}.get(frequency)
    if maximum_gap is not None and any(
        (current - previous).days > maximum_gap
        for previous, current in zip(period_dates, period_dates[1:], strict=False)
    ):
        gaps.append(f"{side}_context_coverage_gap:{metric_id}{suffix}")
    if frequency == "daily" and required_days:
        required = {
            day for day in required_days if start_date.isoformat() <= day <= end_date.isoformat()
        }
        observed = {item.period_end for item in valid if item.period_end in required}
        minimum_observations = (len(required) * 95 + 99) // 100
        if len(observed) < minimum_observations:
            gaps.append(f"{side}_context_coverage_density:{metric_id}{suffix}")
    return gaps


def _context_selection_gaps(
    repository: EvidenceRepository,
    *,
    database_path: Path,
    artifacts: Path,
    side: str,
    metric_id: str,
    definition_version: str,
    frequency: str,
    cutoff: datetime,
) -> tuple[str, ...]:
    frequency = evidence_frequency(metric_id, frequency)
    series = TargetBoundEvidenceRepository(
        repository, cutoff.astimezone(ZoneInfo("Asia/Shanghai")).date(), {metric_id: frequency}
    ).metric_series(
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
    current_points = [points[-1] for points in grouped.values()]
    if metric_id == "CN_RRR_EVENT" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        # Evaluate announcement membership before collapsing the event history:
        # a later event for one scope must not erase another event's members.
        publication = select_published_rrr_events(repository, series)
        if any(p.selected_claim_id in publication.incomplete_claim_ids for p in current_points):
            statuses.add("members_missing")
    latest_period_end = max(point.period_end for point in current_points)
    warrant_selection = None
    if metric_id == "CN_FUTURES_WARRANTS" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        warrant_selection = select_warrant_inputs(
            repository,
            series,
            period=latest_period_end,
            mode=AsOfMode.PUBLIC,
            definition_version=definition_version,
        )
        if warrant_selection.missing_members:
            statuses.add("members_missing")
    required_members = (
        required_dimension_members(
            metric_id, definition_version=definition_version, period=latest_period_end
        )
        or ()
    )
    validation_points: list[Any]
    if warrant_selection is not None:
        validation_points = [
            point
            for point in current_points
            if point.selected_claim_id in warrant_selection.selected_claim_ids
        ]
    elif metric_id == "CN_FUTURES_WARRANTS":
        validation_points = []
        for required in required_members:
            matching = [
                point
                for point in current_points
                if all(point.dimensions.get(key) == value for key, value in required.items())
            ]
            if not matching:
                statuses.add("members_missing")
                continue
            member_latest_period_end = max(point.period_end for point in matching)
            validation_points.extend(
                point for point in matching if point.period_end == member_latest_period_end
            )
    else:
        validation_points = [
            point for point in current_points if point.period_end == latest_period_end
        ]
        observed_dimensions = [point.dimensions for point in validation_points]
        if any(
            not any(
                all(dimensions.get(key) == value for key, value in required.items())
                for dimensions in observed_dimensions
            )
            for required in required_members
        ):
            statuses.add("members_missing")
        if required_members:
            validation_points = [
                point
                for point in validation_points
                if any(
                    all(point.dimensions.get(key) == value for key, value in required.items())
                    for required in required_members
                )
            ]
    if metric_id == "CN_LPR_1Y_5Y" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_lpr_claims = lpr_claims_matching_acquisitions(repository, tuple(validation_points))
        if any(point.selected_claim_id not in valid_lpr_claims for point in validation_points):
            statuses.add("invalid")
    if (
        metric_id in OFFICIAL_CONTEXT_INTEGRITY_METRICS
        and definition_version not in BUILTIN_CATALOG_VERSIONS
    ):
        valid_official_claims = official_claims_matching_acquisitions(
            repository, {metric_id: tuple(validation_points)}, definition_version=definition_version
        )
        if any(point.selected_claim_id not in valid_official_claims for point in validation_points):
            statuses.add("invalid")
    if metric_id in INTERBANK_METRICS and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_interbank_claims = interbank_claims_matching_acquisitions(
            repository,
            {metric_id: tuple(validation_points)},
            definition_version=definition_version,
        )
        if any(
            point.selected_claim_id not in valid_interbank_claims for point in validation_points
        ):
            statuses.add("invalid")
    if metric_id in TREASURY_METRICS and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_treasury_claims = treasury_claims_matching_acquisitions(
            repository, {metric_id: tuple(validation_points)}, definition_version=definition_version
        )
        if any(point.selected_claim_id not in valid_treasury_claims for point in validation_points):
            statuses.add("invalid")
    if metric_id == "CN_MARGIN_BALANCE" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_margin_claims = tushare_claims_matching_acquisitions(
            repository, tuple(validation_points), definition_version=definition_version
        )
        if any(point.selected_claim_id not in valid_margin_claims for point in validation_points):
            statuses.add("invalid")
    if metric_id in MARKET_INDEX_IDENTITIES and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_market_claims = tushare_claims_matching_acquisitions(
            repository,
            tuple(validation_points),
            definition_version=definition_version,
            parse=parse_market_index_acquisition,
        )
        if any(point.selected_claim_id not in valid_market_claims for point in validation_points):
            statuses.add("invalid")
    if metric_id == "CN_INDEX_VALUATION" and definition_version not in BUILTIN_CATALOG_VERSIONS:
        valid_valuation_claims = tushare_claims_matching_acquisitions(
            repository,
            tuple(validation_points),
            definition_version=definition_version,
            parse=parse_valuation_acquisition,
        )
        if any(
            point.selected_claim_id not in valid_valuation_claims for point in validation_points
        ):
            statuses.add("invalid")
    if (
        metric_id in (DAILY_BREADTH_MEASURES | WINDOW_BREADTH_MEASURES | AMOUNT_BREADTH_MEASURES)
        and definition_version not in BUILTIN_CATALOG_VERSIONS
    ):
        valid_breadth_claims = breadth_claims_matching_acquisitions(
            repository,
            tuple(validation_points),
            definition_version=definition_version,
            artifacts=artifacts,
        )
        if any(point.selected_claim_id not in valid_breadth_claims for point in validation_points):
            statuses.add("invalid")
    from pring_cycle.commodity_basket import (
        COMMODITY_METRICS,
        commodity_claims_matching_acquisitions,
    )

    if metric_id in COMMODITY_METRICS and definition_version not in BUILTIN_CATALOG_VERSIONS:
        commodity_ids = commodity_claims_matching_acquisitions(
            repository,
            {metric_id: tuple(validation_points)},
            database_path=database_path,
            artifacts=artifacts,
            definition_version=definition_version,
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
        )
        if any(point.selected_claim_id not in commodity_ids for point in validation_points):
            statuses.add("invalid")
    freshness_days = (
        730
        if metric_id == "CN_RRR_EVENT"
        else {"daily": 10, "monthly": 95, "quarterly": 190, "event": 370}.get(
            frequency,
            95,
        )
    )
    for current in validation_points:
        if current.selection_status != "selected":
            statuses.add(current.selection_status)
            continue
        selected = next(
            (claim for claim in current.claims if claim.claim_id == current.selected_claim_id),
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
    return tuple(f"{side}_context_selection_{status}:{metric_id}" for status in sorted(statuses))


def _metric_warmup_days(metric_id: str, affected_formulas: set[str]) -> int:
    return max(
        (
            _CONTEXT_FORMULA_WARMUP_DAYS.get(key, 0)
            for key in affected_formulas
            if metric_id in CONTEXT_FORMULA_INPUTS.get(key, ())
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
