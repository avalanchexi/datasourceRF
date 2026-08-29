from __future__ import annotations

import hashlib
import os
import signal
import threading
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.logging import write_runtime_event
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import (
    CliReportAdapter,
    ReportAdapter,
    ReportRepository,
    ReportService,
    evidence_bundle_from_projection,
)
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimeNotInitializedError, RuntimePaths
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter
from pring_cycle.storage import database_health, record_worker_heartbeat

CORE_METRICS = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}


def run_worker(paths: RuntimePaths) -> None:
    if database_health(paths.database)["status"] != "ok":
        raise RuntimeNotInitializedError("runtime_not_initialized")

    stopped = threading.Event()

    def request_stop(_signal_number: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    started_at = datetime.now(UTC)
    write_runtime_event(paths, "worker", "worker_started")
    runs = RunRepository(paths.database)
    runs.audit_lease()
    previous_schedule_check = started_at
    try:
        while not stopped.is_set():
            observed_at = datetime.now(UTC)
            record_worker_heartbeat(
                paths.database,
                process_id=os.getpid(),
                started_at=started_at,
                heartbeat_at=observed_at,
            )
            submit_schedule_if_crossed(paths, previous_schedule_check, observed_at)
            previous_schedule_check = observed_at
            process_pending_run(paths)
            stopped.wait(1)
    finally:
        write_runtime_event(paths, "worker", "worker_stopped")


def submit_schedule_if_crossed(
    paths: RuntimePaths,
    previous_check: datetime,
    observed_at: datetime,
) -> str | None:
    if previous_check.tzinfo is None or observed_at.tzinfo is None:
        raise ValueError("schedule_check_times_must_be_timezone_aware")
    repository = RunRepository(paths.database)
    schedule = repository.schedule()
    if schedule["enabled"] is not True:
        return None
    timezone = ZoneInfo(str(schedule["timezone"]))
    previous_local = previous_check.astimezone(timezone)
    observed_local = observed_at.astimezone(timezone)
    if previous_local.date() != observed_local.date() or observed_local.weekday() >= 5:
        return None
    hour, minute = (int(value) for value in str(schedule["start_time"]).split(":"))
    scheduled_at = observed_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not previous_local < scheduled_at <= observed_local:
        return None
    try:
        model_version_id = ModelRepository(paths.database).active().model_version_id
    except LookupError:
        return None
    run = repository.submit_manual_full(
        target_business_date=observed_local.date().isoformat(),
        client_request_id=(
            f"scheduled-{observed_local.date().isoformat()}-v{schedule['version']}"
        ),
        model_version_id=model_version_id,
        system_as_of=observed_at,
    )
    return run.run_id


def process_pending_run(
    paths: RuntimePaths,
    *,
    report_adapters: tuple[ReportAdapter, ...] | None = None,
) -> str | None:
    runs = RunRepository(paths.database)
    queued = runs.next_queued()
    if queued is None:
        return None
    owner_id = f"worker-{os.getpid()}"
    runs.acquire_lease(queued.run_id, owner_id=owner_id)
    heartbeat_stop = threading.Event()
    heartbeat = threading.Thread(
        target=_lease_heartbeat,
        args=(runs, owner_id, heartbeat_stop),
        daemon=True,
        name="pring-run-lease-heartbeat",
    )
    heartbeat.start()
    try:
        _execute_run(paths, runs, queued, report_adapters)
    except (LookupError, OSError, TypeError, ValueError) as error:
        runs.mark_action_required(
            queued.run_id,
            f"worker_failure:{type(error).__name__}:{error}",
        )
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=1)
        runs.release_lease(owner_id)
    return queued.run_id


def _execute_run(
    paths: RuntimePaths,
    runs: RunRepository,
    run: RunRecord,
    report_adapters: tuple[ReportAdapter, ...] | None,
) -> None:
    runs.advance(run.run_id, "preflight")
    if run.command_type == "report_generation":
        runs.advance(run.run_id, "generating_report")
        _generate_report(paths, runs, run, report_adapters)
        runs.advance(run.run_id, "completed")
        return
    if run.command_type in {"targeted_refresh", "manual_deep_search"}:
        runs.mark_action_required(run.run_id, "configured_external_adapter_required")
        return

    runs.advance(run.run_id, "refreshing_evidence")
    _refresh_core_sources(paths, run.target_business_date)
    run = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
    runs.advance(run.run_id, "validating_evidence")
    readiness = _core_readiness(paths, run)
    runs.advance(run.run_id, "evaluating_core_readiness")
    runs.advance(run.run_id, "deriving_states")
    runs.advance(run.run_id, "building_projection")
    runs.advance(run.run_id, "publishing_projection")
    last_stage = _last_confirmed_stage(paths)
    observation_versions = tuple(
        version_id
        for item in readiness
        for version_id in item.observation_version_ids
    )
    evidence_snapshot_id = None
    if observation_versions:
        evidence_snapshot_id = EvidenceRepository(paths.database).freeze_snapshot(
            observation_versions,
            mode=AsOfMode.SYSTEM,
            as_of=run.system_as_of,
        ).evidence_snapshot_id
    result = P0ProjectionService(ProjectionSetRepository(paths.database)).publish(
        target_business_date=run.target_business_date,
        system_as_of=run.system_as_of,
        assets=readiness,
        last_confirmed_stage=last_stage,
        model_version_id=run.model_version_id,
        evidence_snapshot_id=evidence_snapshot_id,
    )
    if result.status != "published" or result.projection_set_id is None:
        runs.mark_action_required(run.run_id, "p0_unavailable")
        return
    runs.link_projection(run.run_id, result.projection_set_id)
    runs.advance(run.run_id, "generating_report")
    generated = _generate_report(paths, runs, run, report_adapters)
    runs.record_checkpoint(run.run_id, "report_snapshot", generated, verified=True)
    runs.advance(run.run_id, "completed")


def _core_readiness(
    paths: RuntimePaths,
    run: RunRecord,
) -> tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness]:
    evidence = EvidenceRepository(paths.database)
    results = []
    for asset, metric_id in CORE_METRICS.items():
        series = evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=run.system_as_of,
        )
        reason = "validated"
        state = None
        candidate_state = None
        candidate_days = 0
        candidate_30d = None
        proxy_12m = None
        distance_pct = None
        slope_pct = None
        noise_band_pct = None
        if not series:
            reason = "source_missing"
        elif any(item.selection_status == "conflicted" for item in series):
            reason = "source_conflict"
        elif series[-1].period_end != run.target_business_date:
            reason = "stale_for_target_business_date"
        elif any(
            claim.certification_status != "certified" or claim.quality_status != "validated"
            for point in series
            for claim in point.claims
        ):
            reason = "source_not_certified"
        elif any(
            item.value_state is not EvidenceValueState.REPORTED_VALUE
            or item.selected_value is None
            for item in series
        ):
            reason = "nonnumeric_core_observation"
        else:
            points = [
                PricePoint(date.fromisoformat(item.period_end), float(item.selected_value))
                for item in series
                if item.selected_value is not None
            ]
            trend = evaluate_trend(points, TrendRules())
            state = trend.stable_state
            candidate_state = trend.candidate_state
            candidate_days = trend.persistence_days
            candidate_30d = trend.candidate_30d
            proxy_12m = trend.proxy_12m
            distance_pct = trend.distance_pct
            slope_pct = trend.slope_pct
            noise_band_pct = trend.noise_band_pct
            if state is None:
                reason = trend.reason
        results.append(
            CoreAssetReadiness(
                asset=asset,
                metric_id=metric_id,
                state=state,
                reason=reason,
                observation_count=len(series),
                latest_business_date=series[-1].period_end if series else None,
                observation_version_ids=tuple(
                    item.selected_claim_id
                    for item in series
                    if item.selected_claim_id is not None
                ),
                evidence_window_start=series[-120].period_end if len(series) >= 120 else None,
                candidate_state=candidate_state,
                candidate_days=candidate_days,
                candidate_30d=candidate_30d,
                proxy_12m=proxy_12m,
                distance_pct=distance_pct,
                slope_pct=slope_pct,
                noise_band_pct=noise_band_pct,
            )
        )
    return tuple(results)  # type: ignore[return-value]


def _refresh_core_sources(paths: RuntimePaths, target_business_date: str) -> None:
    secrets = parse_data_source_secrets(paths.secrets)
    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        return
    adapter = TushareCoreAdapter(token)
    target = date.fromisoformat(target_business_date)
    start = target.fromordinal(target.toordinal() - 280)
    calendar = adapter.trading_days(start, target)
    expected = calendar[-160:]
    if not expected or expected[-1] != target:
        raise ValueError("target_business_date_not_in_china_calendar")
    evidence = EvidenceRepository(paths.database)
    fetched_at = datetime.now(UTC)
    for metric_id, (api_name, source_code) in CORE_API_IDENTITIES.items():
        bars = adapter.core_bars(
            metric_id,
            start=expected[0],
            end=expected[-1],
            expected_business_dates=expected,
        )
        for bar in bars:
            public_available_at = datetime(
                bar.business_date.year,
                bar.business_date.month,
                bar.business_date.day,
                7,
                30,
                tzinfo=UTC,
            )
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=bar.business_date.isoformat(),
                    period_end=bar.business_date.isoformat(),
                    dimensions={},
                    value=bar.close,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=bar.unit,
                    provider="tushare",
                    source_reference=(
                        f"tushare:{api_name}:{source_code}:{bar.business_date.isoformat()}"
                    ),
                    release_event_id=(
                        f"release:{api_name}:{source_code}:{bar.business_date.isoformat()}"
                    ),
                    release_at=public_available_at,
                    public_available_at=public_available_at,
                    fetched_at=fetched_at,
                    available_at=fetched_at,
                    certification_status=bar.certification_status,
                    quality_status="validated",
                )
            )
        normalized_hash = hashlib.sha256(
            repr(
                [
                    (bar.business_date.isoformat(), bar.close, bar.pre_close)
                    for bar in bars
                ]
            ).encode()
        ).hexdigest()
        evidence.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare",
            outcome="verified",
            fetched_at=fetched_at,
            safe_metadata={
                "api_name": api_name,
                "first_business_date": bars[0].business_date.isoformat(),
                "last_business_date": bars[-1].business_date.isoformat(),
                "normalized_hash": normalized_hash,
                "observations": str(len(bars)),
                "source_code": source_code,
            },
        )


def _last_confirmed_stage(paths: RuntimePaths) -> FormalStage | None:
    try:
        overview = ProjectionSetRepository(paths.database).current().datasets["cycle_overview"]
    except LookupError:
        return None
    value = overview.get("current_stage") or overview.get("last_confirmed_stage")
    return FormalStage(str(value)) if value is not None else None


def _generate_report(
    paths: RuntimePaths,
    runs: RunRepository,
    run: RunRecord,
    report_adapters: tuple[ReportAdapter, ...] | None,
) -> str:
    projection = ProjectionSetRepository(paths.database).current()
    adapters = (
        report_adapters
        if report_adapters is not None
        else (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
    )
    generated = ReportService(ReportRepository(paths.database), adapters).generate(
        evidence_bundle_from_projection(projection),
        client_request_id=f"{run.run_id}:report",
    )
    return generated.report_snapshot_id


def _lease_heartbeat(
    runs: RunRepository,
    owner_id: str,
    stopped: threading.Event,
) -> None:
    while not stopped.wait(30):
        try:
            runs.heartbeat_lease(owner_id)
        except ValueError:
            return
