from __future__ import annotations

import hashlib
import os
import signal
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.context_projection import (
    ContextProjection,
    ContextProjectionRules,
    build_context_projection,
)
from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.eia_context import (
    EiaPetroleumAdapter,
    ingest_eia_spot_prices,
)
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
)
from pring_cycle.logging import write_runtime_event
from pring_cycle.maintenance import mutation_rejection
from pring_cycle.metric_contracts import REQUIRED_DIMENSION_MEMBERS, evidence_frequency
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
from pring_cycle.source_contract_review import require_model_source_contract
from pring_cycle.storage import database_health, record_worker_heartbeat
from pring_cycle.tushare_context import (
    WARRANT_SYMBOLS,
    ContextScalar,
    TushareContextAdapter,
    ingest_context_scalars,
)

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
    run = repository.submit_scheduled_full(
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
    execution_now: datetime | None = None,
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
            execution_now=execution_now,
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
    execution_now: datetime | None,
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
    model_manifest = ModelRepository(paths.database).manifest(run.model_version_id)
    require_model_source_contract(model_manifest)
    model_rules = ContextProjectionRules.from_manifest(model_manifest)
    definition_version = model_rules.metric_catalog_version
    runs.advance(run.run_id, "preflight")
    checkpoints = {
        item["kind"]: item["reference"]
        for item in runs.reusable_checkpoints(run.run_id)
    }
    if report_snapshot_id := checkpoints.get("report_snapshot"):
        snapshot = ReportRepository(paths.database).get(report_snapshot_id)
        if (
            run.projection_set_id is None
            or snapshot.projection_set_id != run.projection_set_id
        ):
            raise ValueError("report_checkpoint_projection_mismatch")
        runs.advance(run.run_id, "completed")
        return
    if projection_set_id := checkpoints.get("published_projection"):
        if run.projection_set_id != projection_set_id:
            raise ValueError("projection_checkpoint_identity_mismatch")
        _validate_bound_projection(paths, run, projection_set_id)
        runs.advance(run.run_id, "generating_report")
        generated = _generate_report(paths, runs, run, report_adapters)
        runs.record_checkpoint(run.run_id, "report_snapshot", generated, verified=True)
        runs.advance(run.run_id, "completed")
        return
    observed_at = execution_now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        raise ValueError("execution_now_must_be_timezone_aware")
    if run.command_type == "scheduled_full" and _scheduled_p0_deadline_elapsed(
        runs,
        run,
        observed_at=observed_at,
    ):
        runs.mark_action_required(run.run_id, "scheduled_p0_deadline_elapsed")
        return
    if run.command_type == "report_generation":
        if run.projection_set_id is None:
            projection = ProjectionSetRepository(paths.database).current()
            _validate_projection_for_run(run, projection)
            runs.link_projection(run.run_id, projection.envelope.projection_set_id)
            run = runs.get(run.run_id)
        runs.advance(run.run_id, "generating_report")
        generated = _generate_report(paths, runs, run, report_adapters)
        runs.record_checkpoint(run.run_id, "report_snapshot", generated, verified=True)
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
    if "verified_evidence" not in checkpoints:
        _refresh_core_sources(
            paths,
            run.target_business_date,
            definition_version=definition_version,
        )
        _refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=definition_version,
        )
        run = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
    else:
        run = runs.get(run.run_id)
    runs.advance(run.run_id, "validating_evidence")
    readiness = _core_readiness(
        paths,
        run,
        rules=_trend_rules_for_model(paths, run.model_version_id),
        definition_version=definition_version,
    )
    runs.advance(run.run_id, "evaluating_core_readiness")
    runs.advance(run.run_id, "deriving_states")
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=run.system_as_of,
        model_manifest=model_manifest,
        target_business_date=run.target_business_date,
        visible_evidence_start=max(
            (
                item.evidence_window_start
                for item in readiness
                if item.evidence_window_start is not None
            ),
            default=None,
        ),
    )
    release_calendar_events = _release_calendar_documents(
        paths,
        run,
        definition_version=definition_version,
    )
    runs.advance(run.run_id, "building_projection")
    runs.advance(run.run_id, "publishing_projection")
    last_stage = _last_confirmed_stage(paths, run.target_business_date)
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
        runs.record_checkpoint(
            run.run_id,
            "verified_evidence",
            evidence_snapshot_id,
            verified=True,
        )
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
            dict.fromkeys(
                _explanatory_evidence_warnings(
                    paths,
                    run,
                    definitions=model_rules.metric_definitions,
                    context=context,
                )
                + context.warnings
            )
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
        runs.mark_action_required(run.run_id, result.stage_reason)
        return
    runs.link_projection(run.run_id, result.projection_set_id)
    run = runs.get(run.run_id)
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
    definition_version = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(run.model_version_id)
    ).metric_catalog_version
    configured_adapters = adapters or _production_retrieval_adapters(
        paths,
        scope,
        now,
        definition_version=definition_version,
    )
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
    if scope.source_url is not None:
        from pring_cycle.official_context import official_family_for_metrics

        try:
            official_family_for_metrics(scope.metric_ids)
        except ValueError:
            return False
        return True
    return False


def _production_retrieval_adapters(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    definition_version: str,
) -> dict[str, Callable[[str], str | RetrievalAdapterResponse | None]]:
    adapters: dict[str, Callable[[str], str | RetrievalAdapterResponse | None]] = {
        "local": lambda _event: _local_retrieval(
            paths,
            scope,
            now,
            definition_version=definition_version,
        ),
    }
    if scope.metric_ids == ("CN_LPR_1Y_5Y",):
        adapters["official"] = lambda _event: _official_lpr_retrieval(
            paths,
            scope,
            now,
            definition_version=definition_version,
        )
    elif scope.source_url is not None:
        from pring_cycle.official_context import official_family_for_metrics

        try:
            official_family_for_metrics(scope.metric_ids)
        except ValueError:
            pass
        else:
            adapters["official"] = lambda _event: _official_context_retrieval(
                paths,
                scope,
                now,
                definition_version=definition_version,
            )
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
    *,
    definition_version: str,
) -> str | None:
    evidence = EvidenceRepository(paths.database)
    selected_claim_ids: list[str] = []
    for metric_id in scope.metric_ids:
        points = evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=definition_version,
        )
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
    *,
    definition_version: str,
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
        definition_version=definition_version,
    )
    return "official-evidence:" + hashlib.sha256(
        "\x1f".join(refreshed.claim_ids).encode()
    ).hexdigest()


def _official_context_retrieval(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    definition_version: str,
) -> str | RetrievalAdapterResponse:
    if scope.source_url is None:
        return RetrievalAdapterResponse(
            "failed",
            classification="official_url_required",
        )
    from pring_cycle.official_context import (
        official_family_for_metrics,
        refresh_official_context_document,
    )

    family = official_family_for_metrics(scope.metric_ids)
    refreshed = refresh_official_context_document(
        paths,
        family=family,
        source_url=scope.source_url,
        expected_period=scope.period,
        fetched_at=now,
        definition_version=definition_version,
    )
    if not all(
        metric_definition(
            metric_id,
            definition_version=definition_version,
        ).certification_status
        == "certified"
        for metric_id in refreshed.metric_ids
    ):
        return RetrievalAdapterResponse(
            "candidate_source",
            evidence=scope.source_url,
            classification="awaiting_source_certification",
        )
    return "official-evidence:" + hashlib.sha256(
        "\x1f".join(refreshed.claim_ids).encode()
    ).hexdigest()


def _release_calendar_documents(
    paths: RuntimePaths,
    run: RunRecord,
    *,
    definition_version: str,
) -> tuple[dict[str, object], ...]:
    from pring_cycle.release_calendar import lpr_release_calendar

    events = lpr_release_calendar(
        EvidenceRepository(paths.database),
        period=run.target_business_date[:7],
        as_of=min(
            run.system_as_of,
            datetime.combine(
                date.fromisoformat(run.target_business_date),
                time.max,
                tzinfo=run.system_as_of.tzinfo,
            ),
        ),
        definition_version=definition_version,
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
    definition_version: str,
) -> tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness]:
    evidence = EvidenceRepository(paths.database)
    results = []
    for asset, metric_id in CORE_METRICS.items():
        series = tuple(
            point
            for point in evidence.metric_series(
                metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=run.system_as_of,
                definition_version=definition_version,
            )
            if point.period_end <= run.target_business_date
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
            candidate_days = rules.candidate_days_for_output(trend)
            candidate_30d = trend.candidate_30d
            proxy_12m = trend.proxy_12m
            distance_pct = trend.distance_pct
            slope_pct = trend.slope_pct
            noise_band_pct = trend.noise_band_pct
            if state is None:
                reason = trend.reason
        results.append(
            # The full preheat series remains an internal trend input. Only the
            # latest 120 observations may enter the page/report projection.
            CoreAssetReadiness(
                asset=asset,
                metric_id=metric_id,
                state=state,
                reason=reason,
                observation_count=len(series[-120:]),
                latest_business_date=series[-1].period_end if series else None,
                observation_version_ids=tuple(
                    item.selected_claim_id
                    for item in series[-120:]
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
            candidate_duration_rule_version=str(
                document.get("candidate_duration_rule_version", "candidate-duration-v0001")
            ),
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
    *,
    definitions: tuple[MetricDefinition, ...],
    context: ContextProjection,
) -> tuple[str, ...]:
    evidence = EvidenceRepository(paths.database)
    context_statuses = _context_metric_statuses(context)
    target_trading_days = _target_trading_days(
        evidence,
        run,
        definition_version=(definitions[0].definition_version if definitions else ""),
    )
    warnings: list[str] = []
    for priority in ("P1", "P2"):
        priority_definitions = [item for item in definitions if item.priority == priority]
        available = 0
        for definition in priority_definitions:
            statuses = context_statuses.get(definition.metric_id)
            if definition.certification_status == "derived_from_certified_inputs":
                if statuses is not None and "current" in statuses:
                    available += 1
                continue
            if definition.certification_status != "certified":
                continue
            if (
                definition.frequency == "event"
                and statuses == {"no_event_in_visible_window"}
            ):
                available += 1
                continue
            if not _context_status_allows_direct_metric(definition, statuses):
                continue
            series = evidence.metric_series(
                definition.metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=run.system_as_of,
                public_as_of=datetime.combine(
                    date.fromisoformat(run.target_business_date),
                    time.max,
                    tzinfo=ZoneInfo("Asia/Shanghai"),
                ),
                definition_version=definition.definition_version,
            )
            series = tuple(
                point
                for point in series
                if _point_known_by_target(point, run.target_business_date)
            )
            if _direct_metric_is_ready(
                series,
                definition,
                target_business_date=run.target_business_date,
                target_trading_days=target_trading_days,
            ):
                available += 1
        if available != len(priority_definitions):
            warnings.append(
                f"{priority.lower()}_evidence_incomplete:"
                f"{available}/{len(priority_definitions)}"
            )
    return tuple(warnings)


def _context_status_allows_direct_metric(
    definition: MetricDefinition,
    statuses: set[str] | None,
) -> bool:
    if statuses is None:
        return True
    if statuses == {"current"}:
        return True
    return bool(
        definition.metric_id == "CN_FUTURES_WARRANTS"
        and "current" in statuses
        and statuses <= {"current", "stale"}
    )


def _target_trading_days(
    evidence: EvidenceRepository,
    run: RunRecord,
    *,
    definition_version: str,
) -> tuple[str, ...]:
    if not definition_version:
        return ()
    points = evidence.metric_series(
        CORE_METRICS["stock"],
        mode=AsOfMode.SYSTEM,
        as_of=run.system_as_of,
        public_as_of=datetime.combine(
            date.fromisoformat(run.target_business_date),
            time.max,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        ),
        definition_version=definition_version,
    )
    days = sorted(
        {
            point.period_end
            for point in points
            if point.period_end <= run.target_business_date
            and _point_has_certified_value(point)
        }
    )
    if len(days) < 120 or days[-1] != run.target_business_date:
        return ()
    return tuple(days[-120:])


def _direct_metric_is_ready(
    series: tuple[MetricSeriesPoint, ...],
    definition: MetricDefinition,
    *,
    target_business_date: str,
    target_trading_days: tuple[str, ...],
) -> bool:
    effective_frequency = evidence_frequency(definition.metric_id, definition.frequency)
    if not series:
        return False
    latest_by_dimensions: dict[tuple[tuple[str, str], ...], MetricSeriesPoint] = {}
    for point in series:
        key = tuple(sorted(point.dimensions.items()))
        previous = latest_by_dimensions.get(key)
        if previous is None or point.period_end > previous.period_end:
            latest_by_dimensions[key] = point
    current_points = tuple(latest_by_dimensions.values())
    required_members = REQUIRED_DIMENSION_MEMBERS.get(definition.metric_id, ())
    validation_points: list[MetricSeriesPoint] = []
    if required_members and definition.metric_id == "CN_FUTURES_WARRANTS":
        for required in required_members:
            matching = [
                point
                for point in current_points
                if _dimensions_include(point.dimensions, required)
            ]
            if not matching:
                return False
            latest_period = max(point.period_end for point in matching)
            validation_points.extend(
                point for point in matching if point.period_end == latest_period
            )
    else:
        latest_period = max(point.period_end for point in current_points)
        validation_points = [
            point for point in current_points if point.period_end == latest_period
        ]
        if any(
            not any(_dimensions_include(point.dimensions, required) for point in validation_points)
            for required in required_members
        ):
            return False
        if required_members:
            validation_points = [
                point
                for point in validation_points
                if any(
                    _dimensions_include(point.dimensions, required)
                    for required in required_members
                )
            ]
    if not validation_points or any(
        not _point_has_certified_value(point)
        or not _point_is_current_for_target(
            point,
            definition,
            target_business_date=target_business_date,
        )
        for point in validation_points
    ):
        return False
    if definition.priority != "P1" or effective_frequency != "daily":
        return True
    if len(target_trading_days) != 120:
        return False
    required_dates = set(target_trading_days)
    minimum_observations = (len(required_dates) * 95 + 99) // 100
    density_members = required_members or ({},)
    for required in density_members:
        observed = {
            point.period_end
            for point in series
            if point.period_end in required_dates
            and _dimensions_include(point.dimensions, required)
            and _point_has_certified_value(point)
        }
        if len(observed) < minimum_observations:
            return False
    return True


def _dimensions_include(dimensions: dict[str, str], required: dict[str, str]) -> bool:
    return all(dimensions.get(key) == value for key, value in required.items())


def _point_has_certified_value(point: MetricSeriesPoint) -> bool:
    if (
        point.selection_status != "selected"
        or point.selected_claim_id is None
        or point.value_state is not EvidenceValueState.REPORTED_VALUE
        or point.selected_value is None
    ):
        return False
    selected = next(
        (claim for claim in point.claims if claim.claim_id == point.selected_claim_id),
        None,
    )
    return bool(
        selected is not None
        and selected.certification_status == "certified"
        and selected.quality_status == "validated"
    )


def _context_metric_statuses(context: ContextProjection) -> dict[str, set[str]]:
    statuses: dict[str, set[str]] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            metric_id = value.get("metric_id")
            status = value.get("status") or value.get("freshness")
            if isinstance(metric_id, str) and isinstance(status, str):
                statuses.setdefault(metric_id, set()).add(status)
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(context.macro)
    visit(context.inventory)
    return statuses


def _point_is_current_for_target(
    point: MetricSeriesPoint,
    definition: MetricDefinition,
    *,
    target_business_date: str,
) -> bool:
    effective_frequency = evidence_frequency(definition.metric_id, definition.frequency)
    target = date.fromisoformat(target_business_date)
    period = date.fromisoformat(point.period_end)
    if period > target:
        if effective_frequency == "daily":
            return False
        if not _point_known_by_target(point, target_business_date):
            return False
    max_age = {
        "daily": 10,
        "monthly": 95,
        "quarterly": 190,
        "event": 730 if definition.metric_id == "CN_RRR_EVENT" else 370,
    }.get(effective_frequency, 95)
    return (target - min(target, period)).days <= max_age


def _point_known_by_target(point: MetricSeriesPoint, target_business_date: str) -> bool:
    target = date.fromisoformat(target_business_date)
    if date.fromisoformat(point.period_start) > target:
        return False
    selected = next(
        (claim for claim in point.claims if claim.claim_id == point.selected_claim_id),
        None,
    )
    return (
        selected is not None
        and selected.public_available_at is not None
        and selected.public_available_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
        <= target
    )


def _context_adapter(token: str) -> TushareContextAdapter:
    return TushareContextAdapter(token)


def _eia_context_adapter(api_key: str) -> EiaPetroleumAdapter:
    return EiaPetroleumAdapter(api_key)


def _refresh_context_sources(
    paths: RuntimePaths,
    target_business_date: str,
    *,
    definition_version: str,
) -> None:
    secrets = parse_data_source_secrets(paths.secrets)
    target = date.fromisoformat(target_business_date)
    eia_key = secrets.get("EIA_API_KEY")
    if eia_key is not None:
        fetched_at = datetime.now(UTC)
        repository = EvidenceRepository(paths.database)
        try:
            prices = _eia_context_adapter(eia_key).spot_prices(
                start_date=target - timedelta(days=220),
                end_date=target,
            )
            ingest_eia_spot_prices(
                paths,
                prices,
                fetched_at=fetched_at,
                definition_version=definition_version,
            )
        except (OSError, TypeError, ValueError) as error:
            if isinstance(error, OSError):
                outcome = "source_failed"
            elif isinstance(error, TypeError):
                outcome = "adapter_failed"
            else:
                outcome = "validation_failed"
            for metric_id in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
                repository.record_retrieval_attempt(
                    metric_id=metric_id,
                    channel="eia_official_candidate",
                    outcome=outcome,
                    fetched_at=fetched_at,
                    safe_metadata={
                        "error_type": type(error).__name__,
                        "family": "spot_prices",
                        "period": target_business_date,
                        "target_business_date": target_business_date,
                    },
                )

    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        return
    start_month = date(target.year - 2, target.month, 1).strftime("%Y%m")
    end_month = target.strftime("%Y%m")
    target_quarter = f"{target.year}Q{(target.month - 1) // 3 + 1}"
    start_quarter = f"{target.year - 2}Q{(target.month - 1) // 3 + 1}"
    daily_start = target - timedelta(days=220)
    breadth_start = target - timedelta(days=420)
    adapter = _context_adapter(token)
    families: tuple[
        tuple[
            str,
            tuple[str, ...],
            Callable[[], tuple[ContextScalar, ...]],
        ],
        ...,
    ] = (
        (
            "market_indices",
            (
                "CN_EQ_CSI300",
                "CN_EQ_CSI500",
                "CN_EQ_CSI1000",
                "CN_BOND_FULL_PRICE_CNY030",
                "CN_BOND_10Y_930916",
                "CN_COMMODITY_BROAD_NHCI",
            ),
            lambda: adapter.market_indices(start_date=daily_start, end_date=target),
        ),
        (
            "market_breadth",
            (
                "CN_EQ_ADV_DEC",
                "CN_EQ_AD_RATIO",
                "CN_EQ_NEW_HIGH_LOW_120",
                "CN_EQ_ABOVE_MA120",
                "CN_EQ_ADV_AMOUNT_SHARE",
            ),
            lambda: adapter.market_breadth(
                start_date=breadth_start,
                end_date=target,
            ),
        ),
        (
            "margin_financing",
            ("CN_MARGIN_BALANCE",),
            lambda: adapter.margin_financing(start_date=daily_start, end_date=target),
        ),
        (
            "index_valuation",
            ("CN_INDEX_VALUATION",),
            lambda: adapter.index_valuation(start_date=daily_start, end_date=target),
        ),
        (
            "commodity_basket",
            (
                "CN_COMMODITY_EX_HOG_BASKET",
                "CN_COMMODITY_SLEEVE_CONTRIBUTION",
            ),
            lambda: adapter.commodity_basket(start_date=daily_start, end_date=target),
        ),
        (
            "pmi",
            ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
            lambda: adapter.pmi(start_month=start_month, end_month=end_month),
        ),
        (
            "prices",
            ("CN_CPI_HEADLINE", "CN_PPI"),
            lambda: adapter.prices(start_month=start_month, end_month=end_month),
        ),
        (
            "money",
            ("CN_M1_M2",),
            lambda: adapter.money(start_month=start_month, end_month=end_month),
        ),
        (
            "social_financing",
            ("CN_SF_TOTAL",),
            lambda: adapter.social_financing(
                start_month=start_month,
                end_month=end_month,
            ),
        ),
        (
            "futures_warrants",
            ("CN_FUTURES_WARRANTS",),
            lambda: tuple(
                scalar
                for symbol in sorted(WARRANT_SYMBOLS)
                for scalar in adapter.futures_warrants(
                    start_date=daily_start,
                    end_date=target,
                    symbol=symbol,
                )
            ),
        ),
        (
            "gdp",
            ("CN_GDP",),
            lambda: adapter.gdp(
                start_quarter=start_quarter,
                end_quarter=target_quarter,
            ),
        ),
        (
            "treasury_yields",
            ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
            lambda: adapter.treasury_yields(
                start_date=daily_start,
                end_date=target,
            ),
        ),
        (
            "transmission",
            ("CN_DR007", "CN_SHIBOR_ON_1W_3M"),
            lambda: adapter.transmission(
                start_date=daily_start,
                end_date=target,
            ),
        ),
    )
    repository = EvidenceRepository(paths.database)
    for family, metric_ids, retrieve in families:
        fetched_at = datetime.now(UTC)
        try:
            ingest_context_scalars(
                paths,
                retrieve(),
                fetched_at=fetched_at,
                definition_version=definition_version,
            )
        except OSError as error:
            for metric_id in metric_ids:
                repository.record_retrieval_attempt(
                    metric_id=metric_id,
                    channel="tushare",
                    outcome="source_failed",
                    fetched_at=fetched_at,
                    safe_metadata={
                        "error_type": type(error).__name__,
                        "family": family,
                        "period": target_business_date,
                        "target_business_date": target_business_date,
                    },
                )
        except (TypeError, ValueError) as error:
            outcome = "adapter_failed" if isinstance(error, TypeError) else "validation_failed"
            for metric_id in metric_ids:
                repository.record_retrieval_attempt(
                    metric_id=metric_id,
                    channel="tushare",
                    outcome=outcome,
                    fetched_at=fetched_at,
                    safe_metadata={
                        "error_type": type(error).__name__,
                        "family": family,
                        "period": target_business_date,
                        "target_business_date": target_business_date,
                    },
                )
            raise


def _scheduled_p0_deadline_elapsed(
    runs: RunRepository,
    run: RunRecord,
    *,
    observed_at: datetime,
) -> bool:
    schedule = runs.schedule()
    timezone = ZoneInfo(str(schedule["timezone"]))
    hour, minute = (int(value) for value in str(schedule["p0_deadline"]).split(":"))
    deadline = datetime.combine(
        date.fromisoformat(run.target_business_date),
        time(hour, minute),
        timezone,
    )
    return observed_at.astimezone(timezone) > deadline


def _refresh_core_sources(
    paths: RuntimePaths,
    target_business_date: str,
    *,
    definition_version: str,
) -> None:
    secrets = parse_data_source_secrets(paths.secrets)
    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        return
    from pring_cycle.core_history import refresh_core_history

    target = date.fromisoformat(target_business_date)
    refresh_core_history(
        paths,
        TushareCoreAdapter(token),
        start=target - timedelta(days=280),
        end=target,
        definition_version=definition_version,
        latest_observations=160,
    )


def _last_confirmed_stage(
    paths: RuntimePaths,
    target_business_date: str,
) -> FormalStage | None:
    value = ProjectionSetRepository(paths.database).last_confirmed_stage(
        on_or_before=target_business_date
    )
    return FormalStage(str(value)) if value is not None else None


def _generate_report(
    paths: RuntimePaths,
    runs: RunRepository,
    run: RunRecord,
    report_adapters: tuple[ReportAdapter, ...] | None,
) -> str:
    if run.projection_set_id is None:
        raise ValueError("report_projection_not_bound")
    projection = ProjectionSetRepository(paths.database).get(run.projection_set_id)
    _validate_projection_for_run(run, projection)

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


def _validate_bound_projection(
    paths: RuntimePaths,
    run: RunRecord,
    projection_set_id: str,
) -> None:
    projection = ProjectionSetRepository(paths.database).get(projection_set_id)
    _validate_projection_for_run(run, projection)


def _validate_projection_for_run(run: RunRecord, projection: object) -> None:
    from pring_cycle.projections import ProjectionSet

    if not isinstance(projection, ProjectionSet):
        raise TypeError("projection_set_required")
    if projection.envelope.target_business_date != run.target_business_date:
        raise ValueError("report_projection_target_mismatch")
    if projection.envelope.model_version_id != run.model_version_id:
        raise ValueError("report_projection_model_mismatch")


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
