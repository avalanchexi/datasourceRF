from __future__ import annotations

import hashlib
import os
import signal
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pring_cycle.context_projection import build_context_projection
from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
)
from pring_cycle.logging import write_runtime_event
from pring_cycle.maintenance import mutation_rejection
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
from pring_cycle.retrieval import (
    RetrievalAdapterResponse,
    RetrievalBudget,
    RetrievalRequest,
    run_retrieval_cascade,
)
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
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
    rejection = mutation_rejection(paths.database, paths.data)
    if rejection is not None:
        raise RuntimeNotInitializedError(rejection)

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
    retrieval_adapters: Mapping[
        str,
        Callable[[str], str | RetrievalAdapterResponse | None],
    ]
    | None = None,
    retrieval_now: datetime | None = None,
    retrieval_release_resolver: Callable[[RetrievalScope, datetime], bool] | None = None,
) -> str | None:
    if mutation_rejection(paths.database, paths.data) is not None:
        return None
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
        _execute_run(
            paths,
            runs,
            queued,
            report_adapters,
            retrieval_adapters=retrieval_adapters,
            retrieval_now=retrieval_now,
            retrieval_release_resolver=retrieval_release_resolver,
        )
    except (LookupError, OSError, TypeError, ValueError) as error:
        if runs.get(queued.run_id).status != "cancelled":
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
    *,
    retrieval_adapters: Mapping[
        str,
        Callable[[str], str | RetrievalAdapterResponse | None],
    ]
    | None,
    retrieval_now: datetime | None,
    retrieval_release_resolver: Callable[[RetrievalScope, datetime], bool] | None,
) -> None:
    if run.command_type != "report_generation":
        try:
            active_model = ModelRepository(paths.database).active()
        except LookupError:
            runs.mark_action_required(run.run_id, "active_model_unavailable")
            return
        if active_model.model_version_id != run.model_version_id:
            runs.mark_action_required(run.run_id, "model_version_not_active")
            return
    runs.advance(run.run_id, "preflight")
    if run.command_type == "report_generation":
        runs.advance(run.run_id, "generating_report")
        _generate_report(paths, runs, run, report_adapters)
        runs.advance(run.run_id, "completed")
        return
    if run.command_type in {"targeted_refresh", "manual_deep_search"}:
        _execute_retrieval_run(
            paths,
            runs,
            run,
            adapters=retrieval_adapters,
            now=retrieval_now or datetime.now(UTC),
            release_resolver=retrieval_release_resolver,
        )
        return

    runs.advance(run.run_id, "refreshing_evidence")
    _refresh_core_sources(paths, run.target_business_date)
    if run.attempt_count == 1:
        run = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
    else:
        run = runs.get(run.run_id)
    runs.advance(run.run_id, "validating_evidence")
    readiness = _core_readiness(
        paths,
        run,
        rules=_trend_rules_for_model(paths, run.model_version_id),
    )
    runs.advance(run.run_id, "evaluating_core_readiness")
    runs.advance(run.run_id, "deriving_states")
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=run.system_as_of,
    )
    release_calendar_events = _release_calendar_documents(paths, run)
    runs.advance(run.run_id, "building_projection")
    runs.advance(run.run_id, "publishing_projection")
    last_stage = _last_confirmed_stage(paths)
    observation_versions = tuple(
        version_id
        for item in readiness
        for version_id in item.observation_version_ids
    ) + context.observation_version_ids
    evidence_snapshot_id = None
    if observation_versions:
        evidence_snapshot_id = EvidenceRepository(paths.database).freeze_snapshot(
            observation_versions,
            mode=AsOfMode.SYSTEM,
            as_of=run.system_as_of,
        ).evidence_snapshot_id
    if ModelRepository(paths.database).active().model_version_id != run.model_version_id:
        runs.mark_action_required(run.run_id, "active_model_changed_during_run")
        return
    result = P0ProjectionService(ProjectionSetRepository(paths.database)).publish(
        target_business_date=run.target_business_date,
        system_as_of=run.system_as_of,
        assets=readiness,
        last_confirmed_stage=last_stage,
        model_version_id=run.model_version_id,
        warnings=tuple(
            dict.fromkeys(_explanatory_evidence_warnings(paths, run) + context.warnings)
        ),
        evidence_snapshot_id=evidence_snapshot_id,
        macro_document=context.macro,
        inventory_document=context.inventory,
        release_calendar_events=release_calendar_events,
    )
    if result.assessment_id is not None:
        runs.record_checkpoint(
            run.run_id,
            "p0_assessment",
            result.assessment_id,
            verified=True,
        )
    if result.status != "published" or result.projection_set_id is None:
        runs.mark_action_required(run.run_id, "p0_unavailable")
        return
    runs.link_projection(run.run_id, result.projection_set_id)
    ModelRepository(paths.database).record_first_publication(
        run.model_version_id,
        run.target_business_date,
    )
    runs.advance(run.run_id, "generating_report")
    generated = _generate_report(paths, runs, run, report_adapters)
    runs.record_checkpoint(run.run_id, "report_snapshot", generated, verified=True)
    runs.advance(run.run_id, "completed")


def _execute_retrieval_run(
    paths: RuntimePaths,
    runs: RunRepository,
    run: RunRecord,
    *,
    adapters: Mapping[
        str,
        Callable[[str], str | RetrievalAdapterResponse | None],
    ]
    | None,
    now: datetime,
    release_resolver: Callable[[RetrievalScope, datetime], bool] | None,
) -> None:
    if now.tzinfo is None:
        raise ValueError("retrieval_now_must_be_timezone_aware")
    scope = runs.retrieval_scope(run.run_id)
    runs.advance(run.run_id, "refreshing_evidence")
    released = (
        release_resolver(scope, now)
        if release_resolver is not None
        else _retrieval_release_ready(paths, scope, now)
    )
    cache_active = runs.negative_cache_active(
        scope.release_event_id,
        scope.metric_ids,
        now=now,
    )
    if not released or cache_active:
        channel = "negative_cache" if cache_active else "release_gate"
        classification = "negative_cache_active" if cache_active else "awaiting_release"
        runs.record_retrieval_attempt(
            run.run_id,
            release_event_id=scope.release_event_id,
            channel=channel,
            outcome="not_attempted",
            classification=classification,
            latency_ms=0,
            remaining_run_budget=None,
            remaining_daily_budget=None,
            budget_charged=False,
            cache_hit=cache_active,
            manual_budget_exemption=run.command_type == "manual_deep_search",
            candidate_source=None,
            occurred_at=now,
        )
        runs.mark_retrieval_action_required(
            run.run_id,
            classification,
            next_action="wait_for_release_or_cache_expiry",
        )
        return
    consumed = run.consumed_budget
    daily = runs.daily_budget_consumption(now)
    budget = RetrievalBudget(
        run_tavily_remaining=max(0, 8 - consumed["tavily"]),
        run_exa_remaining=max(0, 4 - consumed["exa"]),
        run_ai_remaining=max(0, 1 - consumed["ai_websearch"]),
        daily_tavily_remaining=max(0, 16 - daily["tavily"]),
        daily_exa_remaining=max(0, 8 - daily["exa"]),
        daily_ai_remaining=max(0, 2 - daily["ai_websearch"]),
    )
    initial_run_budget = (
        budget.run_tavily_remaining,
        budget.run_exa_remaining,
        budget.run_ai_remaining,
    )
    configured_adapters = adapters or _production_retrieval_adapters(paths, scope, now)
    result = run_retrieval_cascade(
        RetrievalRequest(
            release_event_id=scope.release_event_id,
            metric_ids=scope.metric_ids,
            priority=scope.priority,
            released=True,
            manual_deep_search=run.command_type == "manual_deep_search",
        ),
        configured_adapters,
        budget,
    )
    for attempt in result.attempts:
        runs.record_retrieval_attempt(
            run.run_id,
            release_event_id=scope.release_event_id,
            channel=attempt.channel,
            outcome=attempt.outcome,
            classification=attempt.classification,
            latency_ms=attempt.latency_ms,
            remaining_run_budget=attempt.remaining_run_budget,
            remaining_daily_budget=attempt.remaining_daily_budget,
            budget_charged=attempt.budget_charged,
            cache_hit=attempt.cache_hit,
            manual_budget_exemption=attempt.manual_budget_exemption,
            candidate_source=attempt.candidate_source,
            occurred_at=now,
        )
    if run.command_type != "manual_deep_search":
        runs.set_budget_consumption(
            run.run_id,
            tavily=consumed["tavily"] + initial_run_budget[0] - budget.run_tavily_remaining,
            exa=consumed["exa"] + initial_run_budget[1] - budget.run_exa_remaining,
            ai_websearch=(
                consumed["ai_websearch"]
                + initial_run_budget[2]
                - budget.run_ai_remaining
            ),
        )
    if result.status == "verified" and result.evidence is not None:
        runs.record_checkpoint(
            run.run_id,
            "verified_evidence",
            result.evidence,
            verified=True,
        )
        runs.advance(run.run_id, "completed")
        return
    cacheable = all(
        attempt.outcome in {"not_found", "not_configured", "candidate_source"}
        for attempt in result.attempts
    ) and any(
        attempt.outcome in {"not_found", "candidate_source"}
        for attempt in result.attempts
    )
    if cacheable and result.attempts:
        runs.store_negative_cache(
            scope.release_event_id,
            scope.metric_ids,
            reason="unresolved",
            expires_at=now + timedelta(minutes=30),
            now=now,
        )
    runs.mark_retrieval_action_required(
        run.run_id,
        "retrieval_unresolved",
        next_action=result.next_action,
    )


def _retrieval_release_ready(
    _paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
) -> bool:
    if scope.metric_ids == ("CN_LPR_1Y_5Y",):
        from pring_cycle.release_calendar import lpr_release_expectation

        expectation = lpr_release_expectation(scope.period)
        return now >= expectation.window_start
    return False


def _production_retrieval_adapters(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
) -> dict[str, Callable[[str], str | RetrievalAdapterResponse | None]]:
    adapters: dict[str, Callable[[str], str | RetrievalAdapterResponse | None]] = {
        "local": lambda _event: _local_retrieval(paths, scope, now),
    }
    if scope.metric_ids == ("CN_LPR_1Y_5Y",):
        adapters["official"] = lambda _event: _official_lpr_retrieval(paths, scope, now)
    secrets = parse_data_source_secrets(paths.secrets)
    if "TAVILY_API_KEY" in secrets or "EXA_API_KEY" in secrets:
        from pring_cycle.search_discovery import (
            build_search_query,
            search_discovery_adapter,
        )

        query = build_search_query(scope.metric_ids, period=scope.period)
        if token := secrets.get("TAVILY_API_KEY"):
            adapters["tavily"] = search_discovery_adapter("tavily", token, query)
        if token := secrets.get("EXA_API_KEY"):
            adapters["exa"] = search_discovery_adapter("exa", token, query)
    return adapters


def _local_retrieval(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
) -> str | None:
    evidence = EvidenceRepository(paths.database)
    selected_claim_ids: list[str] = []
    for metric_id in scope.metric_ids:
        points = evidence.metric_series(metric_id, mode=AsOfMode.SYSTEM, as_of=now)
        matching = [item for item in points if item.period_end.startswith(scope.period)]
        if not matching:
            return None
        for point in matching:
            selected = next(
                (claim for claim in point.claims if claim.claim_id == point.selected_claim_id),
                None,
            )
            if (
                point.selection_status != "selected"
                or selected is None
                or selected.certification_status != "certified"
                or selected.quality_status != "validated"
            ):
                return None
            selected_claim_ids.append(selected.claim_id)
    if not selected_claim_ids:
        return None
    digest = hashlib.sha256("\x1f".join(sorted(selected_claim_ids)).encode()).hexdigest()
    return f"local-evidence:{digest}"


def _official_lpr_retrieval(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
) -> str | RetrievalAdapterResponse:
    if scope.source_url is None:
        return RetrievalAdapterResponse(
            "failed",
            classification="official_url_required",
        )
    from pring_cycle.official_lpr import refresh_lpr_release

    refreshed = refresh_lpr_release(
        paths,
        source_url=scope.source_url,
        expected_period=scope.period,
        fetched_at=now,
    )
    return "official-evidence:" + hashlib.sha256(
        "\x1f".join(refreshed.claim_ids).encode()
    ).hexdigest()


def _release_calendar_documents(
    paths: RuntimePaths,
    run: RunRecord,
) -> tuple[dict[str, object], ...]:
    from pring_cycle.release_calendar import lpr_release_calendar

    events = lpr_release_calendar(
        EvidenceRepository(paths.database),
        period=run.target_business_date[:7],
        as_of=run.system_as_of,
    )
    return tuple(
        {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in vars(event).items()
        }
        for event in events
    )


def _core_readiness(
    paths: RuntimePaths,
    run: RunRecord,
    *,
    rules: TrendRules,
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
        elif any(not _selected_core_claim_is_valid(metric_id, point) for point in series):
            reason = "source_identity_not_certified"
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
            trend = evaluate_trend(points, rules)
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


def _trend_rules_for_model(paths: RuntimePaths, model_version_id: str) -> TrendRules:
    manifest = ModelRepository(paths.database).manifest(model_version_id)
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
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_trend_rules_invalid") from error


def _selected_core_claim_is_valid(metric_id: str, point: MetricSeriesPoint) -> bool:
    selected_claim_id = point.selected_claim_id
    claims = point.claims
    selected = next(
        (claim for claim in claims if claim.claim_id == selected_claim_id),
        None,
    )
    if selected is None:
        return False
    api_name, source_code = CORE_API_IDENTITIES[metric_id]
    expected_reference = f"tushare:{api_name}:{source_code}:{point.period_end}"
    return (
        selected.provider == "tushare"
        and selected.source_reference == expected_reference
        and selected.unit == "index_points"
        and selected.certification_status == "certified"
        and selected.quality_status == "validated"
    )


def _explanatory_evidence_warnings(
    paths: RuntimePaths,
    run: RunRecord,
) -> tuple[str, ...]:
    from pring_cycle.catalog import metric_catalog

    evidence = EvidenceRepository(paths.database)
    warnings: list[str] = []
    for priority in ("P1", "P2"):
        definitions = [item for item in metric_catalog() if item.priority == priority]
        available = 0
        for definition in definitions:
            series = evidence.metric_series(
                definition.metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=run.system_as_of,
            )
            if series and series[-1].selection_status == "selected":
                available += 1
        if available != len(definitions):
            warnings.append(
                f"{priority.lower()}_evidence_incomplete:{available}/{len(definitions)}"
            )
    return tuple(warnings)


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

    def cancel_requested() -> bool:
        return runs.get(run.run_id).status == "cancelled"

    adapters = (
        report_adapters
        if report_adapters is not None
        else (
            CliReportAdapter("codex_cli", cancel_requested=cancel_requested),
            CliReportAdapter("claude_code_cli", cancel_requested=cancel_requested),
        )
    )
    generated = ReportService(ReportRepository(paths.database), adapters).generate(
        evidence_bundle_from_projection(projection),
        client_request_id=f"{run.run_id}:report",
        cancel_requested=cancel_requested,
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
