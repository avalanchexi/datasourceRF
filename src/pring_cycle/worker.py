from __future__ import annotations

import hashlib
import os
import signal
import sqlite3
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

from pring_cycle.batches import code_version, processing_batch
from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.context_projection import (
    ContextProjection,
    ContextProjectionRules,
    build_context_projection,
)
from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.eia_context import (
    EiaPetroleumAdapter,
)
from pring_cycle.eia_html import fetch_eia_history
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
)
from pring_cycle.freshness import (
    DERIVED_INPUTS,
    TradingCalendar,
    gap_list,
    period_status,
    record_run_freshness,
    run_calendar_scope,
    use_release_schedule,
    use_run_calendar,
)
from pring_cycle.logging import write_runtime_event
from pring_cycle.maintenance import mutation_rejection
from pring_cycle.metric_contracts import (
    china_business_day_end,
    evidence_frequency,
    minimum_context_daily_observations,
    required_dimension_members,
)
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import CARRIED_FORWARD, CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.read_scope import shared_read_scope
from pring_cycle.release_schedule import (
    batch_schedule,
    latest_schedule,
    refresh_release_schedule,
)
from pring_cycle.reports import (
    CliReportAdapter,
    ReportAdapter,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from pring_cycle.retrieval import (
    RetrievalAdapterResponse,
    RetrievalBudget,
    RetrievalRequest,
    matches_retrieval_period,
    run_retrieval_cascade,
)
from pring_cycle.retrieval_registry import parser_for_scope
from pring_cycle.runs import LEASE_VALID_SECONDS, RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimeNotInitializedError, RuntimePaths
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.source_adapters import (
    CoreInputValidator,
    TushareCoreAdapter,
    selected_core_claim_is_valid,
)
from pring_cycle.source_contract_review import require_model_source_contract
from pring_cycle.storage import database_health, keep_database_open, record_worker_heartbeat
from pring_cycle.tushare_context import (
    WARRANT_SYMBOLS,
    ContextObservationsMissingError,
    ContextScalar,
    TushareContextAdapter,
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
        with keep_database_open(paths.database):
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
        client_request_id=(f"scheduled-{observed_local.date().isoformat()}-v{schedule['version']}"),
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
    from pring_cycle.retrieval_ledger import RetrievalLedger

    RetrievalLedger(paths.database).expire_responses(paths.artifacts)
    if queued is None:
        return None
    with keep_database_open(paths.database):
        owner_id = f"worker-{os.getpid()}"
        runs.acquire_lease(queued.run_id, owner_id=owner_id)
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=lease_heartbeat,
            args=(runs, owner_id, heartbeat_stop),
            kwargs={"paths": paths},
            daemon=True,
            name="pring-run-lease-heartbeat",
        )
        heartbeat.start()
        try:
            # A Worker run never captures reviewed futures inputs (only their reviewed import
            # does) or alters stored claims' parents, so one run shares one read of those.
            runs.record_code_version(queued.run_id, code_version())
            with shared_read_scope(), processing_batch(queued.run_id), run_calendar_scope():
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
            RetrievalLedger(paths.database).interrupt(queued.run_id)
            if runs.get(queued.run_id).status != "cancelled":
                runs.mark_action_required(
                    queued.run_id,
                    f"worker_failure:{type(error).__name__}:{error}",
                )
        except BaseException:
            RetrievalLedger(paths.database).interrupt(queued.run_id)
            if runs.get(queued.run_id).status != "cancelled":
                runs.mark_interrupted(queued.run_id, "worker_process_interrupted")
            raise
        finally:
            heartbeat_stop.set()
            # The final connection and lease must outlive every heartbeat write.
            heartbeat.join()
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
        item["kind"]: item["reference"] for item in runs.reusable_checkpoints(run.run_id)
    }
    if report_snapshot_id := checkpoints.get("report_snapshot"):
        snapshot = ReportRepository(paths.database).get(report_snapshot_id)
        if run.projection_set_id is None or snapshot.projection_set_id != run.projection_set_id:
            raise ValueError("report_checkpoint_projection_mismatch")
        if run.command_type in {"manual_full", "scheduled_full"}:
            from pring_cycle.full_retrieval import FullRunRetrieval

            FullRunRetrieval(paths).record_adoption(run)
        runs.advance(run.run_id, "completed")
        return
    if projection_set_id := checkpoints.get("published_projection"):
        if run.projection_set_id != projection_set_id:
            raise ValueError("projection_checkpoint_identity_mismatch")
        _validate_bound_projection(paths, run, projection_set_id)
        if run.command_type in {"manual_full", "scheduled_full"}:
            from pring_cycle.full_retrieval import FullRunRetrieval

            FullRunRetrieval(paths).record_adoption(run)
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
        use_release_schedule(latest_schedule(paths.database))
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
    from pring_cycle.full_retrieval import FullRunRetrieval

    full_retrieval = FullRunRetrieval(paths)
    if (
        "verified_evidence" not in checkpoints
        and runs.full_retrieval_plan(run.run_id)["final"] is None
    ):
        from pring_cycle.acquisition import own_acquisitions

        # Pre-announcements first: claims stored below take their inferred public time
        # from the release time they announce (ticket 25).
        with own_acquisitions(paths.database, run.run_id, "release_schedule"):
            refresh_release_schedule(
                paths, run.run_id, date.fromisoformat(run.target_business_date)
            )
        use_release_schedule(batch_schedule(paths.database, run.run_id))
        with own_acquisitions(
            paths.database,
            run.run_id,
            "direct_core_refresh",
            metric_ids=("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012", "CN_COMMODITY_CORE_NHII"),
        ):
            _refresh_core_sources(
                paths, run.target_business_date, definition_version=definition_version
            )
        with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
            refresh_context_sources(
                paths, run.target_business_date, definition_version=definition_version
            )
        full_retrieval.retrieve(run)
        if runs.get(run.run_id).status != "running":
            return
        if not run.cutoffs_frozen:
            run = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
    else:
        run = runs.get(run.run_id)
        if "verified_evidence" in checkpoints:
            full_retrieval.recover_legacy_plan(run)
    full_retrieval.evaluate(run)
    plan = runs.full_retrieval_plan(run.run_id)
    calendar = TradingCalendar(
        date.fromisoformat(day) for day in plan["final"]["daily_window"].get("dates", ())
    )
    use_run_calendar(calendar)
    use_release_schedule(batch_schedule(paths.database, run.run_id))
    freshness = record_run_freshness(
        paths.database, run.run_id, model_rules.metric_definitions, run.system_as_of, calendar
    )
    priorities = {item.metric_id: item.priority for item in model_rules.metric_definitions}
    if any(
        item.status == "unconfigured" and priorities.get(item.metric_id) == "P0"
        for item in freshness
    ):
        runs.mark_action_required(run.run_id, "p0_freshness_unconfigured")
        return
    gaps = tuple(gap_list(paths.database, run.run_id, model_rules.metric_definitions))
    if plan["final"]["daily_window"]["status"] != "available":
        runs.mark_action_required(run.run_id, "p0_required_calendar_unavailable")
        return
    runs.advance(run.run_id, "validating_evidence")
    # A core day missing inside the window (other than the target itself, which is the
    # carry-forward case) is missing detail: it holds the formal stage (gate ①).
    window_gaps = {
        gap["metric_id"]
        for gap in plan["final"]["gaps"]
        if not gap["complete"]
        and gap["metric_id"] in model_manifest["core_metrics"].values()
        and gap.get("period") != run.target_business_date
    }
    readiness = _core_readiness(
        paths,
        run,
        rules=_trend_rules_for_model(paths, run.model_version_id),
        definition_version=definition_version,
        calendar=calendar,
        window_gaps=window_gaps,
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
    _backfill_missed_days(
        paths,
        run,
        window=tuple(plan["final"]["daily_window"].get("dates", ())),
        calendar=calendar,
        model_manifest=model_manifest,
        definition_version=definition_version,
    )
    runs.advance(run.run_id, "publishing_projection")
    last_stage = _last_confirmed_stage(paths, run.target_business_date)
    observation_versions = (
        tuple(version_id for item in readiness for version_id in item.observation_version_ids)
        + tuple(
            version_id
            for item in readiness
            for version_id in (item.model_input_observation_version_ids or ())
        )
        + context.observation_version_ids
    )
    evidence_snapshot_id = None
    if observation_versions:
        evidence_snapshot_id = (
            EvidenceRepository(paths.database)
            .freeze_snapshot(
                observation_versions,
                mode=AsOfMode.SYSTEM,
                as_of=run.system_as_of,
            )
            .evidence_snapshot_id
        )
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
        gap_list=gaps,
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
    full_retrieval.record_adoption(run)
    runs.advance(run.run_id, "generating_report")
    generated = _generate_report(paths, runs, run, report_adapters)
    runs.record_checkpoint(run.run_id, "report_snapshot", generated, verified=True)
    runs.advance(run.run_id, "completed")
    # Only a successful run moves the retention window; a failed one leaves everything.
    from pring_cycle.retention import prune_to_window

    prune_to_window(paths)


def _backfill_missed_days(
    paths: RuntimePaths,
    run: RunRecord,
    *,
    window: tuple[str, ...],
    calendar: TradingCalendar,
    model_manifest: Mapping[str, object],
    definition_version: str,
) -> None:
    """Summarize each window day before the target that has no summary (ticket 24).

    With no summary at all this is the first initialization: every earlier day of the
    120-session window is summarized in order, which rebuilds the stage history. A daily
    run fills only the days it missed. Each day sees only details public by that day's end,
    and none gets a report.
    """
    projections = ProjectionSetRepository(paths.database)
    summarized = projections.summarized_dates()
    missed = [day for day in window if day < run.target_business_date and day not in summarized]
    rules = _trend_rules_for_model(paths, run.model_version_id)
    service = P0ProjectionService(projections)
    for day in missed:
        try:
            _summarize_day(
                paths,
                run,
                day,
                service=service,
                rules=rules,
                calendar=calendar,
                model_manifest=model_manifest,
                definition_version=definition_version,
            )
        except (KeyError, LookupError, TypeError, ValueError) as error:
            # One day that cannot be summarized stays missing (a later run retries it);
            # it never fails the target day's run.
            write_runtime_event(
                paths, "worker", f"backfill_day_failed:{day}:{type(error).__name__}", "warning"
            )


def _summarize_day(
    paths: RuntimePaths,
    run: RunRecord,
    day: str,
    *,
    service: P0ProjectionService,
    rules: TrendRules,
    calendar: TradingCalendar,
    model_manifest: Mapping[str, object],
    definition_version: str,
) -> None:
    """Publish one earlier day's summary from what was public by that day's end."""
    day_run = replace(run, target_business_date=day)
    public_end = datetime.combine(
        date.fromisoformat(day), time.max, tzinfo=ZoneInfo("Asia/Shanghai")
    )
    readiness = _core_readiness(
        paths,
        day_run,
        rules=rules,
        definition_version=definition_version,
        calendar=calendar,
        public_as_of=public_end,
    )
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=run.system_as_of,
        model_manifest=model_manifest,
        target_business_date=day,
        visible_evidence_start=max(
            (
                item.evidence_window_start
                for item in readiness
                if item.evidence_window_start is not None
            ),
            default=None,
        ),
        persist_derived=False,
    )
    service.publish(
        target_business_date=day,
        system_as_of=run.system_as_of,
        assets=readiness,
        last_confirmed_stage=_last_confirmed_stage(paths, day),
        model_version_id=run.model_version_id,
        warnings=context.warnings,
        macro_document=context.macro,
        inventory_document=context.inventory,
    )


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
    definition_version = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(run.model_version_id)
    ).metric_catalog_version
    from pring_cycle.retrieval_ledger import RetrievalLedger

    RetrievalLedger(paths.database).bind_run(run, definition_version)
    runs.advance(run.run_id, "refreshing_evidence")
    release_status = (
        ("released" if release_resolver(scope, now) else "awaiting_release")
        if release_resolver is not None
        else _retrieval_release_status(paths, scope, now, definition_version=definition_version)
    )
    released = release_status == "released"
    cache_active = adapters is not None and runs.negative_cache_active(
        scope.release_event_id,
        scope.metric_ids,
        now=now,
    )
    if not released or cache_active:
        channel = "negative_cache" if cache_active else "release_gate"
        classification = "negative_cache_active" if cache_active else release_status
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
            next_action=(
                "resolve_release_configuration"
                if release_status == "unknown_release_configuration"
                else "wait_for_release_or_cache_expiry"
            ),
        )
        return
    consumed = run.consumed_budget
    budget = RetrievalBudget(
        run_tavily_remaining=max(0, RetrievalBudget.run_tavily_remaining - consumed["tavily"]),
        run_exa_remaining=max(0, RetrievalBudget.run_exa_remaining - consumed["exa"]),
    )
    configured_adapters = adapters or _production_retrieval_adapters(
        paths,
        scope,
        now,
        definition_version=definition_version,
        run_id=run.run_id,
    )
    result = run_retrieval_cascade(
        RetrievalRequest(
            release_event_id=scope.release_event_id,
            metric_ids=scope.metric_ids,
            priority=scope.priority,
            released=True,
            manual_deep_search=run.command_type == "manual_deep_search",
            persistent_accounting=adapters is None,
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
            physical_request_id=attempt.physical_request_id,
        )
    if adapters is not None and run.command_type != "manual_deep_search":
        charged = Counter(item.channel for item in result.attempts if item.budget_charged)
        runs.set_budget_consumption(
            run.run_id,
            tavily=consumed["tavily"] + charged["tavily"],
            exa=consumed["exa"] + charged["exa"],
            ai_websearch=consumed["ai_websearch"] + charged["ai_websearch"],
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
    ) and any(attempt.outcome in {"not_found", "candidate_source"} for attempt in result.attempts)
    if adapters is not None and cacheable and result.attempts:
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


def _retrieval_release_status(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    definition_version: str,
    public_as_of: datetime | None = None,
    latest_only: bool = False,
) -> str:
    repository = EvidenceRepository(paths.database)
    public_cutoff = min(now, public_as_of) if public_as_of is not None else now
    states: list[str] = []
    for metric_id in scope.metric_ids:
        points = repository.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=now,
            public_as_of=public_cutoff,
            definition_version=definition_version,
        )
        if any(
            matches_retrieval_period(point.period_end, scope.period)
            and any(
                claim.quality_status == "validated"
                and claim.public_available_at is not None
                and claim.public_available_at <= public_cutoff
                for claim in point.claims
            )
            for point in points
        ):
            states.append("released")
        elif metric_id == "CN_LPR_1Y_5Y":
            from pring_cycle.release_calendar import lpr_release_expectation

            expectation = lpr_release_expectation(scope.period)
            states.append(
                "released" if public_cutoff >= expectation.window_start else "awaiting_release"
            )
        else:
            states.append(
                _registered_release_state(
                    metric_id, scope.period, public_cutoff, latest_only=latest_only
                )
            )
    if "awaiting_release" in states:
        return "awaiting_release"
    return (
        "unknown_release_configuration" if "unknown_release_configuration" in states else "released"
    )


def _registered_release_state(
    metric_id: str, period: str, cutoff: datetime, *, latest_only: bool = False
) -> str:
    """Whether the freshness registry says ``period`` has been published by ``cutoff``.

    One not yet released is awaiting release and triggers nothing (ticket 19). A full run
    fills the gap list, which names each metric's newest released period, so with
    ``latest_only`` an older history period keeps the unknown state and is not searched
    day by day; a targeted run names its period and is judged on that period alone.
    """
    from pring_cycle.freshness import (
        FRESHNESS_REGISTRY,
        current_calendar,
        latest_released_period,
        period_end,
        release_at,
    )

    rule = FRESHNESS_REGISTRY.get(metric_id)
    if rule is None or rule.frequency == "event":
        return "unknown_release_configuration"
    if "-Q" in period:
        first = date(int(period[:4]), int(period[-1]) * 3 - 2, 1)
    elif len(period) == 7:
        first = date.fromisoformat(period + "-01")
    else:
        first = date.fromisoformat(period)
    calendar = current_calendar()
    end = period_end(rule.frequency, first, calendar)
    if release_at(rule, end, calendar) > cutoff:
        return "awaiting_release"
    if not latest_only or end == latest_released_period(rule, cutoff, calendar):
        return "released"
    return "unknown_release_configuration"


def _production_retrieval_adapters(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    definition_version: str,
    run_id: str,
    scope_run: RunRecord | None = None,
) -> dict[str, Callable[[str], str | RetrievalAdapterResponse | None]]:
    from pring_cycle.retrieval_ledger import RetrievalLedger

    adapters: dict[str, Callable[[str], str | RetrievalAdapterResponse | None]] = {
        "local": lambda _event: _local_retrieval(
            paths,
            run_id,
            scope_run=scope_run,
        ),
    }
    parser = parser_for_scope(scope.metric_ids)
    if parser == "lpr":
        adapters["official"] = lambda _event: _official_lpr_retrieval(
            paths,
            scope,
            now,
            run_id=run_id,
            scope_run=scope_run,
            definition_version=definition_version,
        )
    elif scope.source_url is not None and parser == "official_context":
        adapters["official"] = lambda _event: _official_context_retrieval(
            paths,
            scope,
            now,
            run_id=run_id,
            scope_run=scope_run,
            definition_version=definition_version,
        )
    if scope.source_url is not None and "official" in adapters:
        from pring_cycle.retrieval_ledger import RetrievalLedger

        adapters["official"] = lambda event: RetrievalLedger(
            paths.database, scope_run=scope_run
        ).trace_acquisition(
            run_id,
            "official",
            event,
            scope.source_url or "",
            lambda on_started: (
                _official_lpr_retrieval(
                    paths,
                    scope,
                    now,
                    run_id=run_id,
                    scope_run=scope_run,
                    definition_version=definition_version,
                    on_acquisition_started=on_started,
                )
                if parser == "lpr"
                else _official_context_retrieval(
                    paths,
                    scope,
                    now,
                    run_id=run_id,
                    scope_run=scope_run,
                    definition_version=definition_version,
                    on_acquisition_started=on_started,
                )
            ),
        )
    secrets = parse_data_source_secrets(paths.secrets)
    if tushare_token := secrets.get("TUSHARE_TOKEN"):
        from pring_cycle.targeted_context import retrieve_tushare_context

        adapters["tushare"] = lambda _event: retrieve_tushare_context(
            paths, run_id, tushare_token, scope_run=scope_run
        )
    if "TAVILY_API_KEY" in secrets or "EXA_API_KEY" in secrets:
        from pring_cycle.search_discovery import (
            build_search_query,
            search_discovery_adapter,
        )
        from pring_cycle.search_evidence import verify_search_candidates

        query = build_search_query(
            scope.metric_ids,
            period=scope.period,
            definition_version=definition_version,
            database_path=paths.database,
        )
        if token := secrets.get("TAVILY_API_KEY"):
            adapters["tavily"] = search_discovery_adapter(
                "tavily",
                token,
                query,
                paths=paths,
                run_id=run_id,
                ledger=RetrievalLedger(paths.database, scope_run=scope_run),
                verify_candidates=lambda request_id, urls, summaries: verify_search_candidates(
                    paths, run_id, request_id, urls, summaries, scope_run=scope_run
                ),
            )
        if token := secrets.get("EXA_API_KEY"):
            adapters["exa"] = search_discovery_adapter(
                "exa",
                token,
                query,
                paths=paths,
                run_id=run_id,
                ledger=RetrievalLedger(paths.database, scope_run=scope_run),
                verify_candidates=lambda request_id, urls, summaries: verify_search_candidates(
                    paths, run_id, request_id, urls, summaries, scope_run=scope_run
                ),
            )
    return adapters


def _local_retrieval(
    paths: RuntimePaths,
    run_id: str,
    *,
    scope_run: RunRecord | None = None,
) -> str | None:
    from pring_cycle.search_evidence import select_retrieval_input

    selection = select_retrieval_input(
        paths, scope_run or RunRepository(paths.database).get(run_id)
    )
    if not selection.complete:
        return None
    digest = hashlib.sha256("\x1f".join(sorted(selection.selected_claim_ids)).encode()).hexdigest()
    return f"selected-evidence:{digest}"


def _official_lpr_retrieval(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    run_id: str,
    scope_run: RunRecord | None = None,
    definition_version: str,
    on_acquisition_started: Callable[[str], None] | None = None,
) -> str | RetrievalAdapterResponse:
    if scope.source_url is None:
        return RetrievalAdapterResponse(
            "failed",
            classification="official_url_required",
        )
    from pring_cycle.official_lpr import refresh_lpr_release

    refresh_lpr_release(
        paths,
        source_url=scope.source_url,
        expected_period=scope.period,
        fetched_at=now,
        definition_version=definition_version,
        on_acquisition_started=on_acquisition_started,
    )
    return _local_retrieval(paths, run_id, scope_run=scope_run) or RetrievalAdapterResponse(
        "candidate_source", evidence=scope.source_url, classification="incomplete_model_input"
    )


def _official_context_retrieval(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    run_id: str,
    scope_run: RunRecord | None = None,
    definition_version: str,
    on_acquisition_started: Callable[[str], None] | None = None,
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
    refresh_official_context_document(
        paths,
        family=family,
        source_url=scope.source_url,
        expected_period=scope.period,
        fetched_at=now,
        definition_version=definition_version,
        on_acquisition_started=on_acquisition_started,
        metric_ids=scope.metric_ids,
    )
    return _local_retrieval(paths, run_id, scope_run=scope_run) or RetrievalAdapterResponse(
        "candidate_source", evidence=scope.source_url, classification="incomplete_model_input"
    )


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
    calendar: TradingCalendar | None = None,
    window_gaps: set[str] | frozenset[str] = frozenset(),
    public_as_of: datetime | None = None,
) -> tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness]:
    """Each core's state on the run's target day; ``public_as_of`` hides later publications."""
    evidence = EvidenceRepository(paths.database)
    target = date.fromisoformat(run.target_business_date)
    previous_session = (calendar or TradingCalendar()).latest_on_or_before(
        target - timedelta(days=1)
    )
    results = []
    for asset, metric_id in CORE_METRICS.items():
        series = tuple(
            point
            for point in evidence.metric_series(
                metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=run.system_as_of,
                public_as_of=public_as_of,
                definition_version=definition_version,
            )
            if point.period_end <= run.target_business_date
        )
        core_inputs = CoreInputValidator(
            evidence,
            tuple(
                point.selected_claim_id
                for point in series
                if definition_version not in BUILTIN_CATALOG_VERSIONS
                and point.selected_claim_id is not None
            ),
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
        model_inputs: tuple[str, ...] = ()
        # One session behind is carried: the previous close stands in for the target in the
        # calculation only and is never stored as a claim. Two or more is a real gap.
        carried = bool(series) and series[-1].period_end == previous_session.isoformat()
        if not series:
            reason = "source_missing"
        elif metric_id in window_gaps:
            reason = "window_session_missing"
        elif any(item.selection_status == "conflicted" for item in series):
            reason = "source_conflict"
        elif series[-1].period_end != run.target_business_date and not carried:
            reason = "stale_for_target_business_date"
        elif any(not selected_core_claim_is_valid(metric_id, point) for point in series):
            reason = "source_identity_invalid"
        elif any(
            item.value_state is not EvidenceValueState.REPORTED_VALUE or item.selected_value is None
            for item in series
        ):
            reason = "nonnumeric_core_observation"
        elif definition_version not in BUILTIN_CATALOG_VERSIONS and any(
            not core_inputs.is_valid(metric_id, point) for point in series
        ):
            reason = "source_original_invalid"
        else:
            points = [
                PricePoint(date.fromisoformat(item.period_end), float(item.selected_value))
                for item in series
                if item.selected_value is not None
            ]
            if carried:
                points.append(PricePoint(target, points[-1].value))
                reason = CARRIED_FORWARD
            trend = evaluate_trend(points, rules)
            model_inputs = tuple(
                item.selected_claim_id for item in series if item.selected_claim_id is not None
            )
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
            # Keep the price display at 120 observations. The separate input
            # manifest preserves the full preheat used by the stateful trend.
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
                model_input_observation_version_ids=model_inputs,
                carried_forward=carried and state is not None,
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
            if definition.metric_id in DERIVED_INPUTS:
                if statuses is not None and "current" in statuses:
                    available += 1
                continue
            if definition.frequency == "event" and statuses == {"no_event_in_visible_window"}:
                available += 1
                continue
            if not _context_status_allows_direct_metric(definition, statuses):
                continue
            if (
                definition.metric_id == "CN_FUTURES_WARRANTS"
                and definition.definition_version not in BUILTIN_CATALOG_VERSIONS
                and (
                    context.warrant_history is None
                    or not context.warrant_history.is_ready(target_trading_days)
                )
            ):
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
                point for point in series if _point_known_by_target(point, run.target_business_date)
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
                f"{priority.lower()}_evidence_incomplete:{available}/{len(priority_definitions)}"
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
            if point.period_end <= run.target_business_date and _point_has_validated_value(point)
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
    required_members = (
        required_dimension_members(
            definition.metric_id,
            definition_version=definition.definition_version,
            period=max(point.period_end for point in current_points),
        )
        or ()
    )
    validation_points: list[MetricSeriesPoint] = []
    if required_members and definition.metric_id == "CN_FUTURES_WARRANTS":
        for required in required_members:
            matching = [
                point for point in current_points if _dimensions_include(point.dimensions, required)
            ]
            if not matching:
                return False
            latest_period = max(point.period_end for point in matching)
            validation_points.extend(
                point for point in matching if point.period_end == latest_period
            )
    else:
        latest_period = max(point.period_end for point in current_points)
        validation_points = [point for point in current_points if point.period_end == latest_period]
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
                    _dimensions_include(point.dimensions, required) for required in required_members
                )
            ]
    if not validation_points or any(
        not _point_has_validated_value(point)
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
    minimum_observations = minimum_context_daily_observations(len(required_dates))
    density_members = required_members or ({},)
    for required in density_members:
        observed = {
            point.period_end
            for point in series
            if point.period_end in required_dates
            and _dimensions_include(point.dimensions, required)
            and _point_has_validated_value(point)
        }
        if len(observed) < minimum_observations:
            return False
    return True


def _dimensions_include(dimensions: dict[str, str], required: dict[str, str]) -> bool:
    return all(dimensions.get(key) == value for key, value in required.items())


def _point_has_validated_value(point: MetricSeriesPoint) -> bool:
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
    return bool(selected is not None and selected.quality_status == "validated")


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
    return (
        period_status(
            definition.metric_id,
            min(target, period).isoformat(),
            china_business_day_end(target),
        )
        == "current"
    )


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
        and selected.public_available_at.astimezone(ZoneInfo("Asia/Shanghai")).date() <= target
    )


def _context_adapter(token: str) -> TushareContextAdapter:
    return TushareContextAdapter(token)


def _eia_context_adapter(api_key: str) -> EiaPetroleumAdapter:
    return EiaPetroleumAdapter(api_key)


EIA_METRICS = ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC")
EIA_HISTORY_SERIES = {"EIA_BRENT_RBRTE": "RBRTE", "EIA_WTI_RWTC": "RWTC"}


def acquire_eia_spot_prices(
    paths: RuntimePaths, api_key: str, *, start_date: date, end_date: date, definition_version: str
) -> None:
    _eia_context_adapter(api_key).acquire_spot_prices(
        paths, start_date=start_date, end_date=end_date, definition_version=definition_version
    )


def refresh_eia_context(
    paths: RuntimePaths,
    *,
    secrets: Mapping[str, str],
    target: date,
    definition_version: str,
    record: Callable[..., None],
) -> str:
    """Read the optional Brent and WTI spot prices, by API key when usable and by page otherwise.

    The official history page needs no key but dates its releases to the day, so a value read
    there carries a coarser publication time than the API's. Both channels are recorded: a key
    that is absent or rejected stays visible as its own outcome instead of being hidden by the
    fallback. Either way the rows remain background-only and awaiting source certification.
    """
    from pring_cycle.acquisition import acquisition_metrics
    from pring_cycle.eia_html import refresh_eia_history

    api_key = secrets.get("EIA_API_KEY")
    if api_key is None:
        record(
            EIA_METRICS,
            "eia_official_candidate",
            "missing_credentials",
            condition="EIA_API_KEY_not_configured",
            request_sent="false",
        )
    else:
        try:
            with acquisition_metrics(EIA_METRICS):
                acquire_eia_spot_prices(
                    paths,
                    api_key,
                    start_date=target - timedelta(days=220),
                    end_date=target,
                    definition_version=definition_version,
                )
        except (OSError, TypeError, ValueError) as error:
            record(
                EIA_METRICS,
                "eia_official_candidate",
                "source_failed"
                if isinstance(error, OSError)
                else "adapter_failed"
                if isinstance(error, TypeError)
                else "validation_failed",
                error_type=type(error).__name__,
                family="spot_prices",
            )
        else:
            record(
                EIA_METRICS, "eia_official_candidate", "verified_candidate", family="spot_prices"
            )
            return "verified_candidate"

    try:
        with acquisition_metrics(EIA_METRICS):
            for metric_id, series_id in EIA_HISTORY_SERIES.items():
                refresh_eia_history(
                    paths,
                    series_id=series_id,
                    start_date=target - timedelta(days=220),
                    end_date=target,
                    definition_version=definition_version,
                    fetcher=fetch_eia_history,
                )
                del metric_id
    except (OSError, TypeError, ValueError) as error:
        record(
            EIA_METRICS,
            "eia_html_candidate",
            "source_failed"
            if isinstance(error, OSError)
            else "adapter_failed"
            if isinstance(error, TypeError)
            else "validation_failed",
            error_type=type(error).__name__,
            family="history_page",
        )
        return "source_failed"
    record(
        EIA_METRICS,
        "eia_html_candidate",
        "verified_candidate",
        family="history_page",
        publication_precision="release_date_only",
    )
    return "verified_candidate"


def refresh_context_sources(
    paths: RuntimePaths,
    target_business_date: str,
    *,
    definition_version: str,
) -> None:
    """Refresh context sources for a frozen catalog, retaining each acquisition outcome."""
    from pring_cycle.acquisition import acquisition_metrics
    from pring_cycle.catalog_registry import registered_definitions
    from pring_cycle.ecb_reference import ECB_HISTORY_URL, ECB_METRIC, refresh_ecb_reference_cross
    from pring_cycle.source_families import TUSHARE_OFFICIAL_DELIVERY_CODES

    secrets = parse_data_source_secrets(paths.secrets)
    target = date.fromisoformat(target_business_date)
    repository = EvidenceRepository(paths.database)

    def record(metric_ids: tuple[str, ...], channel: str, outcome: str, **details: str) -> None:
        recorded_at = datetime.now(UTC)
        for metric_id in metric_ids:
            repository.record_retrieval_attempt(
                metric_id=metric_id,
                channel=channel,
                outcome=outcome,
                fetched_at=recorded_at,
                safe_metadata={
                    "period": target_business_date,
                    "target_business_date": target_business_date,
                    "definition_version": definition_version,
                    **details,
                },
            )

    refresh_eia_context(
        paths,
        secrets=secrets,
        target=target,
        definition_version=definition_version,
        record=record,
    )

    if definition_version not in BUILTIN_CATALOG_VERSIONS and any(
        definition["metric_id"] == ECB_METRIC
        for definition in registered_definitions(paths.database, definition_version)
    ):
        acquisition_ids: list[str] = []
        try:
            with acquisition_metrics((ECB_METRIC,)):
                refresh_ecb_reference_cross(
                    paths,
                    start_date=target - timedelta(days=220),
                    end_date=target,
                    definition_version=definition_version,
                    on_acquisition_started=acquisition_ids.append,
                )
        except (OSError, TypeError, ValueError) as error:
            # The adapter normally records the detailed transport/validation failure. Preserve
            # that receipt; also cover errors after capture so an older success cannot hide one.
            failed_at = datetime.now(UTC)
            latest = repository.latest_retrieval_attempt(
                ECB_METRIC, period=None, as_of=failed_at, definition_version=definition_version
            )
            if (
                latest is None
                or latest.outcome not in {"source_failed", "validation_failed"}
                or not acquisition_ids
                or latest.safe_metadata.get("acquisition_ids") != ",".join(acquisition_ids)
            ):
                repository.record_retrieval_attempt(
                    metric_id=ECB_METRIC,
                    channel="ecb_reference_http",
                    outcome="source_failed" if isinstance(error, OSError) else "validation_failed",
                    fetched_at=failed_at,
                    acquisition_ids=tuple(acquisition_ids),
                    safe_metadata={
                        "source_url": ECB_HISTORY_URL,
                        "start_date": str(target - timedelta(days=220)),
                        "period": target_business_date,
                        "target_business_date": target_business_date,
                        "definition_version": definition_version,
                        "error_type": type(error).__name__,
                    },
                )

    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        record(
            ("CN_GDP", "UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
            "tushare",
            "missing_credentials",
            condition="TUSHARE_TOKEN_not_configured",
            request_sent="false",
        )
        return
    start_month = date(target.year - 2, target.month, 1).strftime("%Y%m")
    end_month = target.strftime("%Y%m")
    target_quarter = f"{target.year}Q{(target.month - 1) // 3 + 1}"
    start_quarter = f"{target.year - 2}Q{(target.month - 1) // 3 + 1}"
    daily_start = target - timedelta(days=220)
    breadth_start = target - timedelta(days=420)
    adapter = _context_adapter(token)
    reviewed_deliveries = {
        metric_id: source_code
        in metric_definition(
            metric_id, definition_version=definition_version, database_path=paths.database
        ).source_codes
        for metric_id, source_code in TUSHARE_OFFICIAL_DELIVERY_CODES.items()
    }
    financing = (
        adapter.social_financing_total
        if reviewed_deliveries["CN_SF_TOTAL"]
        else adapter.social_financing
    )
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
            "margin_financing_sse_szse",
            ("CN_MARGIN_BALANCE_SSE_SZSE",),
            lambda: adapter.margin_financing_sse_szse(start_date=daily_start, end_date=target),
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
            lambda: adapter.money(
                start_month=start_month,
                end_month=end_month,
                include_month_on_month=not reviewed_deliveries["CN_M1_M2"],
            ),
        ),
        (
            "social_financing",
            ("CN_SF_TOTAL",),
            lambda: financing(
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
    for family, metric_ids, retrieve in families:
        # The two margin identities are alternatives; only the one the catalog carries is fetched.
        if family.startswith("margin_financing") and not all(
            _in_catalog(paths, metric_id, definition_version) for metric_id in metric_ids
        ):
            continue
        try:
            with acquisition_metrics(metric_ids):
                result = adapter.acquire_scalars(
                    paths, retrieve, definition_version=definition_version
                )
        except OSError as error:
            record(
                metric_ids,
                "tushare",
                "source_failed",
                error_type=type(error).__name__,
                family=family,
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, ContextObservationsMissingError) and all(
                reviewed_deliveries.get(metric_id, False) for metric_id in metric_ids
            ):
                record(metric_ids, "tushare", "missing_values", family=family)
                continue
            # Gate ③ rejects the response; the metrics become gaps for retrieval, whatever
            # their priority, and the run goes on (ticket 17).
            outcome = "adapter_failed" if isinstance(error, TypeError) else "validation_failed"
            record(metric_ids, "tushare", outcome, error_type=type(error).__name__, family=family)
        else:
            record(
                result.metric_ids,
                "tushare",
                "partial_validation" if result.rejected_field_count else "verified_candidate",
                family=family,
                rejected_fields=str(result.rejected_field_count),
            )
            missing_metrics = tuple(
                metric_id for metric_id in metric_ids if metric_id not in result.metric_ids
            )
            if missing_metrics:
                record(missing_metrics, "tushare", "missing_fields", family=family)


def _in_catalog(paths: RuntimePaths, metric_id: str, definition_version: str) -> bool:
    try:
        metric_definition(
            metric_id, definition_version=definition_version, database_path=paths.database
        )
    except (KeyError, LookupError, ValueError):
        return False
    return True


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
    """Fill the three cores: TuShare, one TuShare retry of the cores it missed, then the CSI
    official page for the two CSI cores (ticket 22). What is still missing is left to the
    run's gap retrieval (search, then the registered parser) and then to carry-forward or
    blocking (ticket 21)."""
    from pring_cycle.core_history import refresh_core_history
    from pring_cycle.official_core import CSINDEX_CORES, refresh_csindex_core
    from pring_cycle.source_adapters import CORE_API_IDENTITIES

    secrets = parse_data_source_secrets(paths.secrets)
    token = secrets.get("TUSHARE_TOKEN")
    target = date.fromisoformat(target_business_date)
    start = target - timedelta(days=280)
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    # Without TuShare, the cores still to fill are those holding nothing for the target day.
    missing: tuple[str, ...] = tuple(
        metric_id
        for metric_id in CORE_API_IDENTITIES
        if token is not None
        or not any(
            point.period_end == target_business_date
            for point in evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=now, definition_version=definition_version
            )
        )
    )
    for _attempt in range(2 if token is not None else 0):
        assert token is not None
        try:
            result = refresh_core_history(
                paths,
                TushareCoreAdapter(token),
                start=start,
                end=target,
                definition_version=definition_version,
                latest_observations=160,
                metric_ids=missing,
            )
            missing = result.rejected_metrics
        except (KeyError, TypeError, ValueError, OSError):
            # Rejected responses stay recorded on their calls; the core gap is judged later.
            pass
        if not missing:
            return
    for metric_id in missing:
        if metric_id not in CSINDEX_CORES:
            continue
        try:
            refresh_csindex_core(
                paths, metric_id, start=start, end=target, definition_version=definition_version
            )
        except (KeyError, TypeError, ValueError, OSError):
            continue


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
        report_input_from_projection(projection),
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


# A beat blocked by another writer may retry inside the lease's own lifetime, which RunRepository
# owns. Giving up on the first lock error would drop the lease silently.
LEASE_HEARTBEAT_SECONDS = 30
# Only a busy write lock is contention. A full disk, an I/O error or a damaged database are
# also OperationalError, and retrying those for a whole lease window would hide them.
LOCK_CONTENTION_MESSAGES = ("database is locked", "database table is locked")


def _is_lock_contention(error: sqlite3.OperationalError) -> bool:
    return any(message in str(error) for message in LOCK_CONTENTION_MESSAGES)


def lease_heartbeat(
    runs: RunRepository,
    owner_id: str,
    stopped: threading.Event,
    *,
    interval_seconds: float = LEASE_HEARTBEAT_SECONDS,
    on_contention: Callable[[str], None] | None = None,
    paths: RuntimePaths | None = None,
) -> None:
    """Hold the lease until told to stop, or until it is lost or can no longer be written.

    SQLite serialises writers: a run's own long write can outlast this connection's busy
    timeout and make the beat fail with a lock error. That is contention, not lost ownership,
    so it is recorded and retried; only losing the lease, or failing for the whole lease
    window, ends the loop.
    """
    last_beat = monotonic()
    while not stopped.wait(interval_seconds):
        try:
            runs.heartbeat_lease(owner_id)
        except ValueError:
            return
        except sqlite3.OperationalError as error:
            if not _is_lock_contention(error):
                # Not contention: a full disk, an I/O error or a damaged database. It ends the
                # loop either way, but it must not end it silently the way the fixed bug did.
                if paths is not None:
                    write_runtime_event(paths, "worker", f"lease_heartbeat_failed:{error}", "error")
                raise
            detail = f"lease_heartbeat_contended:{error}"
            if on_contention is not None:
                on_contention(detail)
            if paths is not None:
                write_runtime_event(paths, "worker", detail, level="warning")
            # Give up before the lease lapses, so a lost lease is reported rather than hidden
            # while the run keeps executing on an expired one.
            if monotonic() - last_beat >= LEASE_VALID_SECONDS - interval_seconds:
                if paths is not None:
                    write_runtime_event(paths, "worker", "lease_heartbeat_abandoned", "error")
                return
            continue
        last_beat = monotonic()
