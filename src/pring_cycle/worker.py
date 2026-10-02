from __future__ import annotations

import contextlib
import hashlib
import os
import signal
import sqlite3
import threading
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
from time import monotonic
from zoneinfo import ZoneInfo

from pring_cycle import credit_impulse
from pring_cycle.acquisition_outcome import (
    LOCAL_FAILED,
    NOT_ATTEMPTED,
    SOURCE_FAILED_OUTCOMES,
    VALIDATION_FAILED_OUTCOMES,
    AcquisitionOutcomes,
    attempt_details,
)
from pring_cycle.ai_websearch import ai_websearch_adapter, ai_websearch_enabled
from pring_cycle.basket import BASKET_METRICS
from pring_cycle.batches import code_version, processing_batch
from pring_cycle.breadth import BREADTH_METRICS
from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.context_projection import (
    ContextProjection,
    ContextProjectionRules,
)
from pring_cycle.credit_impulse import InputPeriods
from pring_cycle.day_summary import (
    CORE_METRICS,
    DaySummaries,
    FailedDay,
    ModelRules,
    RunMaterials,
)
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
    gap_list,
    period_status,
    record_run_freshness,
    release_schedule_scope,
    use_release_schedule,
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
from pring_cycle.news_rules import rules_cover, rules_for
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
    preceding_periods,
    run_retrieval_cascade,
)
from pring_cycle.retrieval_registry import parser_for_scope
from pring_cycle.runs import LEASE_VALID_SECONDS, RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimeNotInitializedError, RuntimePaths
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.source_adapters import TushareCoreAdapter
from pring_cycle.source_contract_review import require_model_source_contract
from pring_cycle.storage import database_health, keep_database_open, record_worker_heartbeat
from pring_cycle.trading_calendar import (
    Sessions,
    SseCalendar,
    current_calendar,
    judging_calendar,
    run_calendar_scope,
    use_run_calendar,
)
from pring_cycle.tushare_context import (
    TUSHARE_WARRANT_SYMBOLS,
    ContextScalar,
    TushareContextAdapter,
    TushareSourceError,
)


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
            with (
                shared_read_scope(),
                processing_batch(queued.run_id),
                run_calendar_scope(),
                release_schedule_scope(),
            ):
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
        from pring_cycle.full_run_requirements import credit_inputs

        # The first plan reads the credit lookback as of the same instant (ticket 24).
        decided_at = datetime.now(UTC)
        _minimum, credit_coverage = credit_inputs(paths, model_rules, run, decided_at=decided_at)
        with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
            refresh_context_sources(
                paths,
                run.target_business_date,
                definition_version=definition_version,
                credit=credit_coverage,
                decided_at=decided_at,
            )
        full_retrieval.retrieve(run, decided_at=decided_at)
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
    # Freshness is judged at the cutoff, past the window: a holiday in between is closed.
    calendar = judging_calendar(
        paths,
        (date.fromisoformat(day) for day in plan["final"]["daily_window"].get("dates", ())),
        run.system_as_of,
    )
    use_run_calendar(calendar)
    use_release_schedule(batch_schedule(paths.database, run.run_id))
    # A formula the model turns off is not owed (ticket 24).
    turned_off = credit_impulse.metrics_off(model_rules.formula_versions)
    freshness = record_run_freshness(
        paths.database,
        run.run_id,
        [item for item in model_rules.metric_definitions if item.metric_id not in turned_off],
        run.system_as_of,
        calendar,
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
    summary_model = ModelRules.of(ModelRepository(paths.database), run.model_version_id)
    release_calendar_events = _release_calendar_documents(
        paths,
        run,
        definition_version=definition_version,
    )
    if ModelRepository(paths.database).active().model_version_id != run.model_version_id:
        runs.mark_action_required(run.run_id, "active_model_changed_during_run")
        return

    def explanatory_warnings(context: ContextProjection) -> tuple[str, ...]:
        return _explanatory_evidence_warnings(
            paths, run, definitions=model_rules.metric_definitions, context=context
        )

    run_steps = {
        "core_readiness": ("evaluating_core_readiness", "deriving_states"),
        "context": ("building_projection",),
        "backfill": ("publishing_projection",),
    }

    def step_done(step: str) -> None:
        # Advancing checks the run is still live, so a cancelled run publishes nothing.
        for run_step in run_steps[step]:
            runs.advance(run.run_id, run_step)

    def snapshot_frozen(snapshot_id: str) -> None:
        runs.record_checkpoint(run.run_id, "verified_evidence", snapshot_id, verified=True)

    def day_failed(failed: FailedDay) -> None:
        # One day that cannot be summarized stays missing (a later run retries it); it
        # never fails the target day's run.
        write_runtime_event(
            paths, "worker", f"backfill_day_failed:{failed.day}:{failed.error}", "warning"
        )

    # A backfilled day's gate ① counts its own sessions back to the core's first close,
    # before the target's window: the stretch covered at the cutoff, never weekdays.
    window_calendar = SseCalendar(paths, as_of=run.system_as_of).around(
        date.fromisoformat(run.target_business_date)
    )
    summary = DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        summary_model,
        calendar=calendar,
        window_calendar=window_calendar,
        release_schedule=batch_schedule(paths.database, run.run_id),
        batch_id=run.run_id,
    ).summarize_target(
        run.target_business_date,
        system_as_of=run.system_as_of,
        run_materials=RunMaterials(
            freshness_gaps=gaps,
            plan_gaps=tuple(plan["final"]["gaps"]),
            derived_requirements=tuple(plan["final"]["derived_requirements"]),
            release_calendar_events=release_calendar_events,
            explanatory_warnings=explanatory_warnings,
            step_done=step_done,
            snapshot_frozen=snapshot_frozen,
            day_failed=day_failed,
        ),
        backfill_window=tuple(plan["final"]["daily_window"].get("dates", ())),
    )
    result = summary.result
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


class SeriesReads:
    """Each metric's series read once per cutoff, for a loop that stores no claims.

    A full run's plan judges thousands of scopes against the same few series. Share one
    of these only where nothing is written between reads: retrieval stores claims between
    scopes, some with an availability earlier than their storage, so it reads afresh.
    """

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository
        self._series: dict[tuple[str, datetime, datetime, str], tuple[MetricSeriesPoint, ...]] = {}

    def __call__(
        self, metric_id: str, *, as_of: datetime, public_as_of: datetime, definition_version: str
    ) -> tuple[MetricSeriesPoint, ...]:
        key = (metric_id, as_of, public_as_of, definition_version)
        if key not in self._series:
            self._series[key] = self._repository.metric_series(
                metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=as_of,
                public_as_of=public_as_of,
                definition_version=definition_version,
            )
        return self._series[key]


def _retrieval_release_status(
    paths: RuntimePaths,
    scope: RetrievalScope,
    now: datetime,
    *,
    definition_version: str,
    public_as_of: datetime | None = None,
    latest_only: bool = False,
    reads: SeriesReads | None = None,
) -> str:
    """Whether the scope's period is published by ``now``; ``reads`` shares series reads."""
    series = reads or SeriesReads(EvidenceRepository(paths.database))
    public_cutoff = min(now, public_as_of) if public_as_of is not None else now
    states: list[str] = []
    for metric_id in scope.metric_ids:
        points = series(
            metric_id,
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
        latest_released_period,
        period_end,
        release_at,
    )
    from pring_cycle.trading_calendar import current_calendar

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
    if scope_run is not None and rules_for(scope.metric_ids) and scope.priority != "P0":
        # Only a full run pulls news; its gaps read that one pull (ADR-0026).
        adapters["tushare_news"] = lambda _event: _tushare_news_retrieval(
            paths, run_id, scope_run, definition_version=definition_version
        )
    parser = parser_for_scope(scope.metric_ids)
    if (
        parser is not None
        and scope.priority != "P0"
        and (parser == "lenient" or rules_cover(scope.metric_ids, scope.period))
        and ai_websearch_enabled(paths)
    ):
        # The last level: the AI CLIs' own web search, checked like news (ADR-0026).
        adapters["ai_websearch"] = ai_websearch_adapter(
            paths,
            run_id,
            scope_run or RunRepository(paths.database).get(run_id),
            definition_version=definition_version,
        )
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
    # Only a registered family has a release title to search for (phase two #05, #06).
    if parser is not None and ("TAVILY_API_KEY" in secrets or "EXA_API_KEY" in secrets):
        from pring_cycle.retrieval_registry import search_domains
        from pring_cycle.search_discovery import (
            build_search_query,
            search_discovery_adapter,
        )
        from pring_cycle.search_evidence import verify_search_candidates

        query = build_search_query(scope.metric_ids, period=scope.period)
        domains = search_domains(scope.metric_ids)
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
                domains=domains,
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
                domains=domains,
            )
    return adapters


def _tushare_news_retrieval(
    paths: RuntimePaths, run_id: str, scope_run: RunRecord, *, definition_version: str
) -> str | None:
    from pring_cycle.search_evidence import select_retrieval_input
    from pring_cycle.tushare_news import fill_from_news

    if not fill_from_news(paths, scope_run, definition_version=definition_version):
        return None
    selection = select_retrieval_input(paths, scope_run)
    if not selection.complete:
        return None
    digest = hashlib.sha256("\x1f".join(sorted(selection.selected_claim_ids)).encode()).hexdigest()
    return f"selected-evidence:{digest}"


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
    from pring_cycle.search_evidence import ModelInputSelector

    family = official_family_for_metrics(scope.metric_ids)
    # Not what another source delivered: a page fetched for GDP's real growth also states
    # the nominal levels in their first release, which would contest the revised levels
    # already held (run findings 2026-09-28, ticket 12).
    run = scope_run or RunRepository(paths.database).get(run_id)
    held = ModelInputSelector(paths, run).select(scope).held_members
    refresh_official_context_document(
        paths,
        family=family,
        source_url=scope.source_url,
        expected_period=scope.period,
        fetched_at=now,
        definition_version=definition_version,
        on_acquisition_started=on_acquisition_started,
        metric_ids=scope.metric_ids,
        held_members=frozenset(held),
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
) -> tuple[str, ...]:
    """The metrics the API delivered."""
    return (
        _eia_context_adapter(api_key)
        .acquire_spot_prices(
            paths, start_date=start_date, end_date=end_date, definition_version=definition_version
        )
        .metric_ids
    )


_SHANGHAI = ZoneInfo("Asia/Shanghai")
# A conservative fixed margin before the window's first day (ticket 30): room for the newest
# daily value out on that day and the one before it across a week-long holiday and a
# foreign market's own sessions. It is not checked against any calendar.
_DAILY_LEAD = timedelta(days=14)


@dataclass(frozen=True)
class ContextFetchStarts:
    """Where the context families' requests start, from the window's first day (ticket 30).

    A monthly or quarterly metric starts at the period before the newest one its release
    rule has out on that day, so the window's first day has its value and the one to
    compare it with; one without a rule, two periods before the day's own. Daily families
    start ``_DAILY_LEAD`` before the day. The credit impulse's longer lookback is its
    module's answer, joined in by the caller (ticket 24).
    """

    first_day: date
    calendar: Sessions

    @property
    def daily(self) -> date:
        return self.first_day - _DAILY_LEAD

    def period(self, *metric_ids: str) -> str:
        """The earliest start of ``metric_ids``, as TuShare asks it: ``YYYYMM`` or ``YYYYQn``."""
        return min(self._start(metric_id) for metric_id in metric_ids).replace("-", "")

    def _start(self, metric_id: str) -> str:
        from pring_cycle.freshness import FRESHNESS_REGISTRY, latest_released_period

        quarterly = metric_id == "CN_GDP"
        rule = FRESHNESS_REGISTRY.get(metric_id)
        if rule is not None and rule.frequency in {"monthly", "quarterly"}:
            day_end = datetime.combine(self.first_day, time.max, tzinfo=_SHANGHAI)
            newest = latest_released_period(rule, day_end, self.calendar)
            return preceding_periods(_period_label(newest, quarterly), 2)[0]
        return preceding_periods(_period_label(self.first_day, quarterly), 3)[0]


def _period_label(day: date, quarterly: bool) -> str:
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}" if quarterly else f"{day:%Y-%m}"


def context_fetch_starts(first_day: date, calendar: Sessions) -> ContextFetchStarts:
    return ContextFetchStarts(first_day, calendar)


def _window_fetch_starts(
    paths: RuntimePaths, target: date, as_of: datetime | None = None
) -> ContextFetchStarts:
    """The starts for the 120 SSE sessions to ``target``, from the target alone without them.

    ``as_of`` is when the run decided what to fetch, so a calendar revised meanwhile does
    not move the window under it (ticket 24).
    """
    sessions = SseCalendar(paths, as_of=as_of)
    window = sessions.window(target, 120)
    return context_fetch_starts(
        window[0] if window else target, sessions.around(target) or current_calendar()
    )


def refresh_eia_context(
    paths: RuntimePaths,
    *,
    secrets: Mapping[str, str],
    target: date,
    definition_version: str,
    record: Callable[..., None],
    start_date: date | None = None,
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
    start_date = start_date or _window_fetch_starts(paths, target).daily
    delivered: tuple[str, ...] = ()
    if api_key is None:
        record(
            EIA_METRICS,
            "eia_official_candidate",
            NOT_ATTEMPTED,
            **attempt_details(
                step="request", condition="EIA_API_KEY_not_configured", request_sent="false"
            ),
        )
    else:
        try:
            with acquisition_metrics(EIA_METRICS):
                delivered = acquire_eia_spot_prices(
                    paths,
                    api_key,
                    start_date=start_date,
                    end_date=target,
                    definition_version=definition_version,
                )
        except (OSError, TypeError, ValueError):
            pass  # the adapter recorded how it ended (ticket 18); the pages may still serve
        if set(delivered) == set(EIA_METRICS):
            return "verified_candidate"

    # Each page is its own acquisition of its own metric, and the adapter records how its
    # request turned out; one failing neither stops the other nor rewrites its outcome
    # (ticket 17). A series the API delivered needs no page.
    outcome = "verified_candidate"
    for metric_id, series_id in EIA_HISTORY_SERIES.items():
        if metric_id in delivered:
            continue
        try:
            with acquisition_metrics((metric_id,)):
                refresh_eia_history(
                    paths,
                    series_id=series_id,
                    start_date=start_date,
                    end_date=target,
                    definition_version=definition_version,
                    fetcher=fetch_eia_history,
                )
        except (OSError, TypeError, ValueError):
            outcome = "source_failed"
    return outcome


def refresh_context_sources(
    paths: RuntimePaths,
    target_business_date: str,
    *,
    definition_version: str,
    credit: InputPeriods | None = None,
    decided_at: datetime | None = None,
) -> None:
    """Refresh context sources for a frozen catalog, retaining each acquisition outcome.

    Each family starts before the 120-session window as the SSE calendar stood at
    ``decided_at`` (ticket 30); social financing and GDP are read back as far as ``credit``
    covers when the model's credit impulse needs more than their own range (ticket 24).
    """
    from pring_cycle.acquisition import acquisition_metrics
    from pring_cycle.catalog_registry import registered_definitions
    from pring_cycle.ecb_reference import ECB_HISTORY_URL, ECB_METRIC, refresh_ecb_reference_cross
    from pring_cycle.source_families import TUSHARE_OFFICIAL_DELIVERY_CODES

    secrets = parse_data_source_secrets(paths.secrets)
    target = date.fromisoformat(target_business_date)
    repository = EvidenceRepository(paths.database)
    # From before the window's first day, not two years back (ticket 30).
    starts = _window_fetch_starts(paths, target, decided_at)
    daily_start = starts.daily

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
        start_date=daily_start,
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
                    start_date=daily_start,
                    end_date=target,
                    definition_version=definition_version,
                    on_acquisition_started=acquisition_ids.append,
                )
        except (OSError, TypeError, ValueError) as error:
            # The adapter records how its call ended, at capture and at ingest (ticket 18).
            # Only a failure it did not record, before its call, is recorded here as this
            # system's own, so an older success cannot hide it.
            failed_at = datetime.now(UTC)
            latest = AcquisitionOutcomes(paths.database).latest(
                ECB_METRIC, as_of=failed_at, definition_version=definition_version
            )
            if (
                latest is None
                or latest.outcome not in SOURCE_FAILED_OUTCOMES | VALIDATION_FAILED_OUTCOMES
                or not acquisition_ids
                or latest.acquisition_ids != tuple(acquisition_ids)
            ):
                repository.record_retrieval_attempt(
                    metric_id=ECB_METRIC,
                    channel="ecb_reference_http",
                    outcome=LOCAL_FAILED,
                    fetched_at=failed_at,
                    acquisition_ids=tuple(acquisition_ids),
                    safe_metadata={
                        "source_url": ECB_HISTORY_URL,
                        "start_date": str(daily_start),
                        "period": target_business_date,
                        "target_business_date": target_business_date,
                        "definition_version": definition_version,
                        **attempt_details(
                            step="local", error_type=type(error).__name__, reason=str(error)[:300]
                        ),
                    },
                )

    # P2 quotes with an official file of their own (ADR-0029): fetched, never searched.
    if definition_version not in BUILTIN_CATALOG_VERSIONS:
        from pring_cycle.quote_sources import QUOTE_SOURCES, refresh_quote_source

        for source in QUOTE_SOURCES:
            if not _in_catalog(paths, source.metric_id, definition_version):
                continue
            # The source records its own outcome, the failure's reason code included.
            with contextlib.suppress(OSError, ValueError), acquisition_metrics((source.metric_id,)):
                refresh_quote_source(
                    paths,
                    source,
                    start_date=daily_start,
                    end_date=target,
                    definition_version=definition_version,
                )

    # TA and CF warrants from CZCE's own report (ADR-0032): each session of the window not
    # yet held, one serial request a day. Each symbol-day records its own outcome.
    if definition_version not in BUILTIN_CATALOG_VERSIONS and _in_catalog(
        paths, "CN_FUTURES_WARRANTS", definition_version
    ):
        from pring_cycle.czce_warrants import refresh_czce_warrants, window_trading_days

        with (
            contextlib.suppress(OSError, ValueError),
            acquisition_metrics(("CN_FUTURES_WARRANTS",)),
        ):
            refresh_czce_warrants(
                paths,
                days=window_trading_days(paths, target),
                definition_version=definition_version,
            )

    token = secrets.get("TUSHARE_TOKEN")
    if token is None:
        record(
            ("CN_GDP", "UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
            "tushare",
            NOT_ATTEMPTED,
            **attempt_details(
                step="request", condition="TUSHARE_TOKEN_not_configured", request_sent="false"
            ),
        )
        return
    end_month = target.strftime("%Y%m")
    target_quarter = f"{target.year}Q{(target.month - 1) // 3 + 1}"
    covered = credit or InputPeriods()
    own_financing, own_gdp = starts.period("CN_SF_TOTAL"), starts.period("CN_GDP")
    financing_start = min(
        (covered.start("CN_SF_TOTAL") or own_financing).replace("-", ""), own_financing
    )
    gdp_start = min((covered.start("CN_GDP") or own_gdp).replace("-", ""), own_gdp)
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

    def breadth() -> tuple[ContextScalar, ...]:
        sessions, calendar_ids = _breadth_calendar(paths, token, target)
        return adapter.breadth(
            end_date=target,
            # A day is done once all seven hold a value; otherwise it is fetched again.
            held_days=_held_days(paths, tuple(BREADTH_METRICS), definition_version),
            sessions=sessions,
            calendar_ids=calendar_ids,
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
            tuple(BREADTH_METRICS),
            breadth,
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
            tuple(sorted(BASKET_METRICS)),
            lambda: adapter.ex_hog_basket(
                end_date=target, held_levels=_held_basket_levels(paths, definition_version)
            ),
        ),
        (
            "pmi",
            ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
            lambda: adapter.pmi(
                start_month=starts.period("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
                end_month=end_month,
            ),
        ),
        (
            "prices",
            ("CN_CPI_HEADLINE", "CN_PPI"),
            lambda: adapter.prices(
                start_month=starts.period("CN_CPI_HEADLINE", "CN_PPI"), end_month=end_month
            ),
        ),
        (
            "money",
            ("CN_M1_M2",),
            lambda: adapter.money(
                start_month=starts.period("CN_M1_M2"),
                end_month=end_month,
                include_month_on_month=not reviewed_deliveries["CN_M1_M2"],
            ),
        ),
        (
            "social_financing",
            ("CN_SF_TOTAL",),
            lambda: financing(
                start_month=financing_start,
                end_month=end_month,
            ),
        ),
        # One acquisition a symbol: a symbol's refused delivery leaves the others held
        # (run findings 2026-09-26, ticket 01).
        *(
            (
                f"futures_warrants:{symbol}",
                ("CN_FUTURES_WARRANTS",),
                partial(
                    adapter.futures_warrants,
                    start_date=daily_start,
                    end_date=target,
                    symbol=symbol,
                ),
            )
            for symbol in sorted(TUSHARE_WARRANT_SYMBOLS)
        ),
        (
            "gdp",
            ("CN_GDP",),
            lambda: adapter.gdp(
                start_quarter=gdp_start,
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
        # The two margin identities are alternatives; only the one the catalog carries is
        # fetched. Breadth and the basket are computed only for the catalog registering them
        # from TuShare's own deliveries (ADR-0030).
        if family.startswith("margin_financing") and not all(
            _in_catalog(paths, metric_id, definition_version) for metric_id in metric_ids
        ):
            continue
        if family in INCREMENTAL_FAMILIES and not _registers_tushare_derived(
            paths, metric_ids, definition_version
        ):
            continue
        # A warrant symbol's outcome is its own: the gap list keeps one symbol's failure though
        # another symbol is fetched after it.
        details = {"family": family, "period": target_business_date}
        if family.startswith("futures_warrants:"):
            details.update(
                symbol=family.partition(":")[2],
                start_date=daily_start.isoformat(),
                end_date=target.isoformat(),
            )
        try:
            with acquisition_metrics(metric_ids):
                adapter.acquire_scalars(
                    paths,
                    retrieve,
                    definition_version=definition_version,
                    metric_ids=metric_ids,
                    details=details,
                )
        except (KeyError, OSError, TypeError, ValueError):
            # The adapter recorded how it ended where it ended: the source's code, the rule
            # that refused it, an empty delivery (ticket 18). Gate ③'s refusals become gaps
            # for retrieval, whatever their priority, and the run goes on.
            continue


def _breadth_calendar(
    paths: RuntimePaths, token: str, target: date
) -> tuple[tuple[date, ...], tuple[str, ...]]:
    """The SSE sessions breadth reads, 600 days to ``target``, and the responses they are from.

    The window, and before it enough sessions to tell any share's age up to 250. Read from
    the core calendar; when a day of the range is not covered, the whole range is fetched.
    TuShare refusing the call is a source failure, a rate limit told apart, as when breadth
    asked for its own calendar.
    """
    from pring_cycle.source_adapters import TushareRefused
    from pring_cycle.trading_calendar import acquire_sse_calendar

    first = target - timedelta(days=600)
    calendar = SseCalendar(paths)
    if calendar.sessions_between(first, target) is None:
        try:
            acquire_sse_calendar(paths, TushareCoreAdapter(token), first, target)
        except TushareRefused as refusal:
            raise TushareSourceError(
                "tushare_rate_limited"
                if refusal.classification == "rate_limited"
                else f"tushare_source_failed:{refusal.code}",
                external_code=refusal.code,
                classification=refusal.classification,
            ) from refusal
        calendar = SseCalendar(paths)
    sessions = calendar.sessions_between(first, target)
    if sessions is None:
        raise ValueError("breadth_calendar_unavailable")
    return sessions, calendar.sources(first, target)


# Families that compute only the window's days not yet held.
INCREMENTAL_FAMILIES = frozenset({"market_breadth", "commodity_basket"})


def _registers_tushare_derived(
    paths: RuntimePaths, metric_ids: tuple[str, ...], definition_version: str
) -> bool:
    """Whether the catalog registers these metrics as computed from TuShare (ADR-0030)."""
    from pring_cycle.basket import SOURCE_CODE as BASKET_SOURCE_CODE

    if definition_version in BUILTIN_CATALOG_VERSIONS:
        return False
    expected = {metric_id: code for metric_id, (code, _measures) in BREADTH_METRICS.items()}
    expected.update({metric_id: BASKET_SOURCE_CODE for metric_id in BASKET_METRICS})
    for metric_id in metric_ids:
        try:
            definition = metric_definition(
                metric_id, definition_version=definition_version, database_path=paths.database
            )
        except (KeyError, LookupError, ValueError):
            return False
        if definition.source_codes != (expected[metric_id],):
            return False
    return True


def _held_days(
    paths: RuntimePaths, metric_ids: tuple[str, ...], definition_version: str
) -> frozenset[date]:
    """The days every one of these metrics already holds a value for."""
    repository = EvidenceRepository(paths.database)
    held: frozenset[date] | None = None
    for metric_id in metric_ids:
        days = frozenset(
            date.fromisoformat(point.period_end)
            for point in repository.metric_series(
                metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=definition_version,
            )
            if point.selected_value is not None
        )
        held = days if held is None else held & days
    return held or frozenset()


def _held_basket_levels(paths: RuntimePaths, definition_version: str) -> dict[date, float]:
    return {
        date.fromisoformat(point.period_end): point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_COMMODITY_EX_HOG_BASKET",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=definition_version,
        )
        if point.selected_value is not None
    }


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
