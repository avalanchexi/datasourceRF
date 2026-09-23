from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.batches import add_batch_columns
from pring_cycle.run_cutoffs import cutoff_contract, upgrade_run_cutoffs
from pring_cycle.storage import database_connection

# A lease is written with this lifetime past each heartbeat, and read back with it to decide
# whether an owner is still alive. The Worker's heartbeat loop needs the same number to know
# how long it may keep retrying, so it imports this rather than carrying its own copy.
LEASE_VALID_SECONDS = 120

RUN_STEPS = (
    "queued",
    "preflight",
    "refreshing_evidence",
    "validating_evidence",
    "evaluating_core_readiness",
    "deriving_states",
    "building_projection",
    "publishing_projection",
    "generating_report",
    "completed",
)


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    command_type: str
    target_business_date: str
    model_version_id: str
    system_as_of: datetime
    report_cutoff: datetime
    status: str
    current_step: str
    outcome: str | None
    recoverable: bool
    next_action: str
    attempt_count: int
    consumed_budget: dict[str, int]
    projection_set_id: str | None
    error_classification: str | None
    retrieval_scope: RetrievalScope | None
    retrieval_attempts: tuple[dict[str, object], ...]
    retrieval_ledger: dict[str, Any] | None = None
    cutoff_mode: str = "legacy_unknown"
    cutoffs_frozen: bool = False


@dataclass(frozen=True)
class RetrievalScope:
    release_event_id: str
    metric_ids: tuple[str, ...]
    period: str
    priority: str
    source_url: str | None


@dataclass(frozen=True)
class LeaseDecision:
    owner_state: str
    run_id: str | None
    next_action: str


class RunRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> RunRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_RUN_SCHEMA)
            connection.executescript(_RETRIEVAL_RUN_SCHEMA)
            upgrade_run_cutoffs(connection)
            add_batch_columns(connection)
            connection.execute(
                """
                INSERT OR IGNORE INTO schedule_configuration(
                    version, enabled, timezone, start_time, p0_deadline,
                    requested_by, created_at
                ) VALUES (1, 0, 'Asia/Shanghai', '18:30', '21:00', 'system-default', ?)
                """,
                (datetime.now(UTC).isoformat(),),
            )
        from pring_cycle.models import (
            ModelRepository,
            analytical_model_v0002_manifest,
            certified_model_v0001_manifest,
        )

        models = ModelRepository.create(database_path)
        models.create_candidate(certified_model_v0001_manifest())
        models.create_candidate(analytical_model_v0002_manifest())
        return repository

    def submit_manual_full(
        self,
        *,
        target_business_date: str,
        client_request_id: str,
        model_version_id: str,
        system_as_of: datetime,
        cutoff_mode: str = "acquisition_window",
    ) -> RunRecord:
        return self.submit(
            command_type="manual_full",
            target_business_date=target_business_date,
            client_request_id=client_request_id,
            model_version_id=model_version_id,
            system_as_of=system_as_of,
            cutoff_mode=cutoff_mode,
        )

    def submit_scheduled_full(
        self,
        *,
        target_business_date: str,
        client_request_id: str,
        model_version_id: str,
        system_as_of: datetime,
    ) -> RunRecord:
        return self.submit(
            command_type="scheduled_full",
            target_business_date=target_business_date,
            client_request_id=client_request_id,
            model_version_id=model_version_id,
            system_as_of=system_as_of,
        )

    def submit(
        self,
        *,
        command_type: str,
        target_business_date: str,
        client_request_id: str,
        model_version_id: str,
        system_as_of: datetime,
        release_event_id: str | None = None,
        metric_ids: tuple[str, ...] = (),
        period: str | None = None,
        source_url: str | None = None,
        cutoff_mode: str | None = None,
    ) -> RunRecord:
        allowed_commands = {
            "manual_full",
            "scheduled_full",
            "targeted_refresh",
            "manual_deep_search",
            "report_generation",
        }
        if command_type not in allowed_commands:
            raise ValueError("unsupported_run_command")
        if system_as_of.tzinfo is None:
            raise ValueError("system_as_of_must_be_timezone_aware")
        cutoff_mode = cutoff_mode or (
            "acquisition_window"
            if command_type in {"manual_full", "scheduled_full"}
            else "explicit"
        )
        if cutoff_mode not in {"explicit", "acquisition_window"}:
            raise ValueError("invalid_cutoff_mode")
        if command_type not in {"manual_full", "scheduled_full"} and cutoff_mode != "explicit":
            raise ValueError("acquisition_window_requires_full_run")
        scope = _validated_retrieval_scope(
            command_type,
            database_path=self._database_path,
            model_version_id=model_version_id,
            release_event_id=release_event_id,
            metric_ids=metric_ids,
            period=period,
            source_url=source_url,
        )
        with self._connect() as connection:
            existing_command = connection.execute(
                """
                SELECT run_id FROM run_command
                WHERE command_type = ? AND client_request_id = ?
                """,
                (command_type, client_request_id),
            ).fetchone()
            if existing_command is not None:
                run_id = str(existing_command["run_id"])
                if self._retrieval_scope(connection, run_id) != scope:
                    raise ValueError("retrieval_scope_idempotency_conflict")
                self._check_cutoff_identity(connection, run_id, cutoff_mode, system_as_of)
                return self.get(run_id)
            active = None
            if command_type == "manual_full":
                active = connection.execute(
                    """
                    SELECT run_id FROM parent_run
                    WHERE command_type = 'manual_full' AND target_business_date = ?
                      AND model_version_id = ?
                      AND status IN ('queued', 'running', 'interrupted', 'action_required')
                    ORDER BY accepted_at DESC LIMIT 1
                    """,
                    (target_business_date, model_version_id),
                ).fetchone()
            if active is not None:
                run_id = str(active["run_id"])
                self._check_cutoff_identity(connection, run_id, cutoff_mode, system_as_of)
                connection.execute(
                    """
                    INSERT INTO run_command(command_type, client_request_id, run_id, accepted_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (command_type, client_request_id, run_id, datetime.now(UTC).isoformat()),
                )
                connection.execute(
                    """
                    INSERT INTO run_attempt(run_id, reason, started_at)
                    VALUES (?, 'duplicate_manual_submission', ?)
                    """,
                    (run_id, datetime.now(UTC).isoformat()),
                )
                return self.get(run_id)
            run_id = (
                "run-"
                + hashlib.sha256(
                    (
                        f"{command_type}:{target_business_date}:{model_version_id}:"
                        f"{client_request_id}:{system_as_of.isoformat()}"
                    ).encode()
                ).hexdigest()[:20]
            )
            budget_json = json.dumps({"tavily": 0, "exa": 0, "ai_websearch": 0})
            connection.execute(
                """
                INSERT INTO parent_run(
                    run_id, command_type, target_business_date, model_version_id,
                    system_as_of, report_cutoff, status, current_step, recoverable,
                    next_action, consumed_budget_json, accepted_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', 'queued', 0,
                          'wait_for_worker', ?, ?)
                """,
                (
                    run_id,
                    command_type,
                    target_business_date,
                    model_version_id,
                    system_as_of.isoformat(),
                    system_as_of.isoformat(),
                    budget_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO run_cutoff_contract VALUES (?, ?, ?, 'submitted')",
                (run_id, cutoff_mode, system_as_of.isoformat()),
            )
            connection.execute(
                """
                INSERT INTO run_command(command_type, client_request_id, run_id, accepted_at)
                VALUES (?, ?, ?, ?)
                """,
                (command_type, client_request_id, run_id, datetime.now(UTC).isoformat()),
            )
            connection.execute(
                "INSERT INTO run_attempt(run_id, reason, started_at) VALUES (?, 'initial', ?)",
                (run_id, datetime.now(UTC).isoformat()),
            )
            if scope is not None:
                connection.execute(
                    """
                    INSERT INTO run_retrieval_scope(
                        run_id, release_event_id, metric_ids_json, period,
                        priority, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        scope.release_event_id,
                        json.dumps(scope.metric_ids, separators=(",", ":")),
                        scope.period,
                        scope.priority,
                        scope.source_url,
                    ),
                )
            connection.execute(
                """
                INSERT INTO run_step_event(run_id, step, event, occurred_at)
                VALUES (?, 'queued', 'entered', ?)
                """,
                (run_id, datetime.now(UTC).isoformat()),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> RunRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT parent_run.*,
                       (SELECT COUNT(*) FROM run_attempt WHERE run_id = parent_run.run_id)
                           AS attempt_count
                FROM parent_run WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if row is None:
                raise LookupError("run_not_found")
            return self._run_record(connection, row)

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM parent_run").fetchone()
        return int(row[0]) if row is not None else 0

    def list_runs(self, limit: int = 50) -> tuple[RunRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT parent_run.*,
                       (SELECT COUNT(*) FROM run_attempt WHERE run_id = parent_run.run_id)
                           AS attempt_count
                FROM parent_run ORDER BY accepted_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return tuple(self._run_record(connection, row) for row in rows)

    def next_queued(self) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT parent_run.*,
                       (SELECT COUNT(*) FROM run_attempt WHERE run_id = parent_run.run_id)
                           AS attempt_count
                FROM parent_run
                WHERE status='queued'
                ORDER BY
                    CASE command_type
                        WHEN 'manual_full' THEN 0
                        WHEN 'report_generation' THEN 1
                        WHEN 'targeted_refresh' THEN 1
                        WHEN 'manual_deep_search' THEN 1
                        WHEN 'scheduled_full' THEN 2
                        ELSE 3
                    END,
                    accepted_at,
                    run_id
                LIMIT 1
                """
            ).fetchone()
            return self._run_record(connection, row) if row is not None else None

    def acquire_lease(
        self,
        run_id: str,
        *,
        owner_id: str,
        process_id: int | None = None,
        now: datetime | None = None,
    ) -> None:
        observed_at = now or datetime.now(UTC)
        process = process_id if process_id is not None else os.getpid()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM worker_lease WHERE lease_name = 'worker:global-execution'"
            ).fetchone()
            if row is not None:
                heartbeat = _parse_time(row["heartbeat_at"])
                if (
                    str(row["owner_id"]) != owner_id
                    and (observed_at - heartbeat).total_seconds() <= LEASE_VALID_SECONDS
                ):
                    raise ValueError("worker_lease_active")
                if str(row["owner_id"]) != owner_id:
                    raise ValueError("stale_lease_requires_audit")
            connection.execute(
                """
                INSERT INTO worker_lease(
                    lease_name, run_id, owner_id, process_id, acquired_at,
                    heartbeat_at, expires_at
                ) VALUES ('worker:global-execution', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_name) DO UPDATE SET
                    run_id=excluded.run_id, owner_id=excluded.owner_id,
                    process_id=excluded.process_id, heartbeat_at=excluded.heartbeat_at,
                    expires_at=excluded.expires_at
                """,
                (
                    run_id,
                    owner_id,
                    process,
                    observed_at.isoformat(),
                    observed_at.isoformat(),
                    datetime.fromtimestamp(
                        observed_at.timestamp() + LEASE_VALID_SECONDS, UTC
                    ).isoformat(),
                ),
            )

    def heartbeat_lease(self, owner_id: str, *, now: datetime | None = None) -> None:
        observed_at = now or datetime.now(UTC)
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE worker_lease SET heartbeat_at = ?, expires_at = ?
                WHERE lease_name = 'worker:global-execution' AND owner_id = ?
                """,
                (
                    observed_at.isoformat(),
                    datetime.fromtimestamp(
                        observed_at.timestamp() + LEASE_VALID_SECONDS, UTC
                    ).isoformat(),
                    owner_id,
                ),
            ).rowcount
        if updated != 1:
            raise ValueError("worker_lease_not_owned")

    def release_lease(self, owner_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM worker_lease
                WHERE lease_name='worker:global-execution' AND owner_id=?
                """,
                (owner_id,),
            )

    def audit_lease(
        self,
        *,
        now: datetime | None = None,
        process_is_alive: Callable[[int], bool] | None = None,
    ) -> LeaseDecision:
        observed_at = now or datetime.now(UTC)
        is_alive = process_is_alive or _process_is_alive
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM worker_lease WHERE lease_name = 'worker:global-execution'"
            ).fetchone()
            if row is None:
                return LeaseDecision("absent", None, "worker_may_claim")
            run_id = str(row["run_id"])
            try:
                heartbeat = _parse_time(row["heartbeat_at"])
                age = (observed_at - heartbeat).total_seconds()
                alive = is_alive(int(row["process_id"]))
                owner_state = (
                    "stale" if age > LEASE_VALID_SECONDS else "active" if alive else "dead"
                )
            except (TypeError, ValueError, OSError):
                owner_state = "corrupt"
            if owner_state == "active":
                return LeaseDecision("active", run_id, "wait_for_active_owner")
            connection.execute(
                """
                UPDATE parent_run SET status='interrupted', recoverable=1,
                    next_action='explicit_resume', error_classification=?
                WHERE run_id=? AND status NOT IN ('completed', 'cancelled', 'failed')
                """,
                (f"worker_owner_{owner_state}", run_id),
            )
            connection.execute(
                "DELETE FROM worker_lease WHERE lease_name='worker:global-execution'"
            )
            from pring_cycle.retrieval_ledger import interrupt_retrieval_requests

            interrupt_retrieval_requests(connection, run_id)
        return LeaseDecision(owner_state, run_id, "explicit_resume_required")

    def mark_interrupted(self, run_id: str, classification: str) -> None:
        self._set_run_state(
            run_id,
            status="interrupted",
            recoverable=True,
            next_action="explicit_resume",
            error_classification=classification,
        )

    def resume(
        self,
        run_id: str,
        *,
        client_request_id: str,
        confirm_external_calls: bool,
    ) -> RunRecord:
        current = self.get(run_id)
        if current.status not in {"interrupted", "action_required"}:
            raise ValueError("run_not_recoverable")
        if not confirm_external_calls:
            raise ValueError("external_resume_confirmation_required")
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT 1 FROM run_command
                WHERE command_type='resume' AND client_request_id=?
                """,
                (client_request_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO run_command(command_type, client_request_id, run_id, accepted_at)
                    VALUES ('resume', ?, ?, ?)
                    """,
                    (client_request_id, run_id, datetime.now(UTC).isoformat()),
                )
                connection.execute(
                    "INSERT INTO run_attempt(run_id, reason, started_at) VALUES (?, 'resume', ?)",
                    (run_id, datetime.now(UTC).isoformat()),
                )
                connection.execute(
                    """
                    UPDATE parent_run SET status='queued', current_step='queued', recoverable=0,
                        next_action='wait_for_worker', error_classification=NULL
                    WHERE run_id=?
                    """,
                    (run_id,),
                )
                connection.execute(
                    """
                    INSERT INTO run_step_event(run_id, step, event, occurred_at)
                    VALUES (?, 'queued', 'resumed', ?)
                    """,
                    (run_id, datetime.now(UTC).isoformat()),
                )
        return self.get(run_id)

    def record_code_version(self, run_id: str, version: str) -> None:
        """Name the code that processes this run; a batch records what produced it."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE parent_run SET code_version=? WHERE run_id=?", (version, run_id)
            )

    def advance(self, run_id: str, step: str) -> RunRecord:
        if step not in RUN_STEPS:
            raise ValueError("unknown_run_step")
        current = self.get(run_id)
        if current.status in {"cancelled", "completed", "failed"}:
            raise ValueError("run_is_terminal")
        if RUN_STEPS.index(step) < RUN_STEPS.index(current.current_step):
            raise ValueError("invalid_run_step_transition")
        status = "completed" if step == "completed" else "running"
        outcome = "changed" if step == "completed" else current.outcome
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE parent_run SET current_step=?, status=?, outcome=?,
                    next_action=? WHERE run_id=?
                """,
                (
                    step,
                    status,
                    outcome,
                    "none" if step == "completed" else "worker_continue",
                    run_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO run_step_event(run_id, step, event, occurred_at)
                VALUES (?, ?, 'entered', ?)
                """,
                (run_id, step, datetime.now(UTC).isoformat()),
            )
            if step == "completed":
                connection.execute(
                    """
                    UPDATE run_attempt SET completed_at=?, outcome='completed'
                    WHERE attempt_id=(
                        SELECT MAX(attempt_id) FROM run_attempt WHERE run_id=?
                    )
                    """,
                    (datetime.now(UTC).isoformat(), run_id),
                )
        return self.get(run_id)

    def freeze_cutoffs(self, run_id: str, *, system_as_of: datetime) -> RunRecord:
        if system_as_of.tzinfo is None:
            raise ValueError("system_as_of_must_be_timezone_aware")
        current = self.get(run_id)
        if current.cutoffs_frozen or current.current_step not in {
            "queued",
            "preflight",
            "refreshing_evidence",
        }:
            raise ValueError("run_cutoff_already_frozen")
        if system_as_of < current.system_as_of:
            raise ValueError("run_cutoff_before_acquisition_window")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO run_cutoff_freeze VALUES (?, ?)",
                (run_id, system_as_of.isoformat()),
            )
            connection.execute(
                """
                UPDATE parent_run SET system_as_of=?, report_cutoff=? WHERE run_id=?
                """,
                (system_as_of.isoformat(), system_as_of.isoformat(), run_id),
            )
        return self.get(run_id)

    def step_history(self, run_id: str) -> tuple[dict[str, str], ...]:
        self.get(run_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT step, event, occurred_at FROM run_step_event
                WHERE run_id=? ORDER BY step_event_id
                """,
                (run_id,),
            ).fetchall()
        return tuple(
            {
                "step": str(row["step"]),
                "event": str(row["event"]),
                "occurred_at": str(row["occurred_at"]),
            }
            for row in rows
        )

    def mark_action_required(self, run_id: str, classification: str) -> RunRecord:
        self._set_run_state(
            run_id,
            status="action_required",
            recoverable=True,
            next_action="refresh_p0_or_create_gap_notice",
            error_classification=classification,
        )
        return self.get(run_id)

    def mark_retrieval_action_required(
        self,
        run_id: str,
        classification: str,
        *,
        next_action: str,
    ) -> RunRecord:
        self._set_run_state(
            run_id,
            status="action_required",
            recoverable=True,
            next_action=next_action,
            error_classification=classification,
        )
        return self.get(run_id)

    def set_budget_consumption(
        self, run_id: str, *, tavily: int, exa: int, ai_websearch: int
    ) -> None:
        document = {"tavily": tavily, "exa": exa, "ai_websearch": ai_websearch}
        with self._connect() as connection:
            connection.execute(
                "UPDATE parent_run SET consumed_budget_json=? WHERE run_id=?",
                (json.dumps(document, sort_keys=True), run_id),
            )

    def retrieval_scope(self, run_id: str) -> RetrievalScope:
        self.get(run_id)
        with self._connect() as connection:
            scope = self._retrieval_scope(connection, run_id)
        if scope is None:
            raise LookupError("run_retrieval_scope_missing")
        return scope

    def full_retrieval_plan(self, run_id: str) -> dict[str, Any]:
        from pring_cycle.full_retrieval import read_full_retrieval_plan

        self.get(run_id)
        return read_full_retrieval_plan(self._database_path, run_id)

    def record_retrieval_attempt(
        self,
        run_id: str,
        *,
        release_event_id: str,
        channel: str,
        outcome: str,
        classification: str | None,
        latency_ms: int,
        remaining_run_budget: int | None,
        remaining_daily_budget: int | None,
        budget_charged: bool,
        cache_hit: bool,
        manual_budget_exemption: bool,
        candidate_source: str | None,
        occurred_at: datetime,
        physical_request_id: str | None = None,
    ) -> None:
        if occurred_at.tzinfo is None:
            raise ValueError("retrieval_attempt_time_must_be_timezone_aware")
        if latency_ms < 0:
            raise ValueError("retrieval_attempt_latency_invalid")
        with self._connect() as connection:
            scope = self._retrieval_scope(connection, run_id)
            if scope is None:
                plan = connection.execute(
                    "SELECT document_json FROM full_run_gap_plan "
                    "WHERE run_id=? AND phase='initial'",
                    (run_id,),
                ).fetchone()
                planned = (
                    next(
                        (
                            item
                            for item in json.loads(plan[0])["scopes"]
                            if item["release_event_id"] == release_event_id
                        ),
                        None,
                    )
                    if plan
                    else None
                )
                if planned is None:
                    raise ValueError("retrieval_attempt_requires_scoped_run")
                scope = RetrievalScope(
                    planned["release_event_id"],
                    tuple(planned["metric_ids"]),
                    planned["period"],
                    planned["priority"],
                    planned["source_url"],
                )
            if scope.release_event_id != release_event_id:
                raise ValueError("retrieval_attempt_release_event_mismatch")
            sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), 0) + 1 FROM run_retrieval_attempt
                WHERE run_id=?
                """,
                (run_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO run_retrieval_attempt(
                    run_id, release_event_id, sequence, channel, outcome,
                    classification, latency_ms, remaining_run_budget,
                    remaining_daily_budget, budget_charged, cache_hit,
                    manual_budget_exemption, candidate_source, occurred_at, physical_request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    release_event_id,
                    int(sequence[0]),
                    channel,
                    outcome,
                    classification,
                    latency_ms,
                    remaining_run_budget,
                    remaining_daily_budget,
                    int(budget_charged),
                    int(cache_hit),
                    int(manual_budget_exemption),
                    candidate_source,
                    occurred_at.astimezone(UTC).isoformat(),
                    physical_request_id,
                ),
            )

    def daily_budget_consumption(self, observed_at: datetime) -> dict[str, int]:
        if observed_at.tzinfo is None:
            raise ValueError("retrieval_budget_time_must_be_timezone_aware")
        local = observed_at.astimezone(ZoneInfo("Asia/Shanghai"))
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        totals = {"tavily": 0, "exa": 0, "ai_websearch": 0}
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='retrieval_physical_request'"
            ).fetchone():
                from pring_cycle.retrieval_ledger import daily_consumption

                return daily_consumption(connection, observed_at)
            rows = connection.execute(
                """
                SELECT channel, COUNT(*) AS consumed
                FROM run_retrieval_attempt
                WHERE budget_charged=1 AND manual_budget_exemption=0
                  AND julianday(occurred_at) >= julianday(?)
                  AND julianday(occurred_at) < julianday(?)
                GROUP BY channel
                """,
                (start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()),
            ).fetchall()
        for row in rows:
            channel = str(row["channel"])
            if channel in totals:
                totals[channel] = int(row["consumed"])
        return totals

    def store_negative_cache(
        self,
        release_event_id: str,
        metric_ids: tuple[str, ...],
        *,
        reason: str,
        expires_at: datetime,
        now: datetime | None = None,
    ) -> None:
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None or expires_at.tzinfo is None:
            raise ValueError("negative_cache_times_must_be_timezone_aware")
        if expires_at <= observed_at:
            raise ValueError("negative_cache_expiry_must_be_future")
        identity = json.dumps(tuple(sorted(metric_ids)), separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO retrieval_negative_cache(
                    release_event_id, metric_ids_json, reason, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(release_event_id, metric_ids_json) DO UPDATE SET
                    reason=excluded.reason, expires_at=excluded.expires_at,
                    created_at=excluded.created_at
                """,
                (
                    release_event_id,
                    identity,
                    reason,
                    expires_at.astimezone(UTC).isoformat(),
                    observed_at.astimezone(UTC).isoformat(),
                ),
            )

    def negative_cache_active(
        self,
        release_event_id: str,
        metric_ids: tuple[str, ...],
        *,
        now: datetime,
    ) -> bool:
        if now.tzinfo is None:
            raise ValueError("negative_cache_time_must_be_timezone_aware")
        identity = json.dumps(tuple(sorted(metric_ids)), separators=(",", ":"))
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM retrieval_negative_cache
                WHERE release_event_id=? AND metric_ids_json=?
                  AND julianday(expires_at) > julianday(?)
                """,
                (release_event_id, identity, now.astimezone(UTC).isoformat()),
            ).fetchone()
        return row is not None

    def record_checkpoint(self, run_id: str, kind: str, reference: str, *, verified: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO run_checkpoint(
                    run_id, kind, reference, verified, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, kind, reference, int(verified), datetime.now(UTC).isoformat()),
            )

    def reusable_checkpoints(self, run_id: str) -> tuple[dict[str, str], ...]:
        reusable_kinds = (
            "verified_evidence",
            "verified_domain_result",
            "published_projection",
            "report_snapshot",
        )
        placeholders = ",".join("?" for _ in reusable_kinds)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT kind, reference FROM run_checkpoint
                WHERE run_id=? AND verified=1 AND kind IN ({placeholders})
                ORDER BY checkpoint_id
                """,
                (run_id, *reusable_kinds),
            ).fetchall()
        return tuple({"kind": str(row["kind"]), "reference": str(row["reference"])} for row in rows)

    def link_projection(self, run_id: str, projection_set_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE parent_run SET projection_set_id=? WHERE run_id=?",
                (projection_set_id, run_id),
            )
        self.record_checkpoint(run_id, "published_projection", projection_set_id, verified=True)

    def cancel(self, run_id: str) -> RunRecord:
        self._set_run_state(
            run_id,
            status="cancelled",
            recoverable=False,
            next_action="none",
            error_classification=None,
        )
        return self.get(run_id)

    def schedule(self) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM schedule_configuration ORDER BY version DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise LookupError("schedule_configuration_missing")
        return _schedule_document(row)

    def configure_schedule(
        self, *, enabled: bool, requested_by: str, now: datetime | None = None
    ) -> dict[str, object]:
        current = self.schedule()
        current_version = current["version"]
        if not isinstance(current_version, int):
            raise ValueError("schedule_version_invalid")
        version = current_version + 1
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO schedule_configuration(
                    version, enabled, timezone, start_time, p0_deadline,
                    requested_by, created_at
                ) VALUES (?, ?, 'Asia/Shanghai', '18:30', '21:00', ?, ?)
                """,
                (
                    version,
                    int(enabled),
                    requested_by,
                    (now or datetime.now(UTC)).isoformat(),
                ),
            )
        return self.schedule()

    def startup_actions(self) -> dict[str, int]:
        return {"automatic_runs": 0, "external_requests": 0}

    def _set_run_state(
        self,
        run_id: str,
        *,
        status: str,
        recoverable: bool,
        next_action: str,
        error_classification: str | None,
    ) -> None:
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE parent_run SET status=?, recoverable=?, next_action=?,
                    error_classification=? WHERE run_id=?
                """,
                (status, int(recoverable), next_action, error_classification, run_id),
            ).rowcount
        if updated != 1:
            raise LookupError("run_not_found")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection

    def _run_record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> RunRecord:
        from dataclasses import replace

        from pring_cycle.retrieval_ledger import RetrievalLedger

        mode, frozen = cutoff_contract(connection, str(row["run_id"]))
        return replace(
            _run_record(
                row,
                retrieval_scope=self._retrieval_scope(connection, str(row["run_id"])),
                retrieval_attempts=self._retrieval_attempts(connection, str(row["run_id"])),
            ),
            retrieval_ledger=RetrievalLedger(self._database_path).for_run(str(row["run_id"])),
            cutoff_mode=mode,
            cutoffs_frozen=frozen,
        )

    def _check_cutoff_identity(
        self, connection: sqlite3.Connection, run_id: str, mode: str, as_of: datetime
    ) -> None:
        row = connection.execute(
            "SELECT mode, initial_system_as_of FROM run_cutoff_contract WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is not None and (
            row[0] != mode or (mode == "explicit" and _parse_time(row[1]) != as_of)
        ):
            raise ValueError("run_cutoff_identity_conflict")

    def _retrieval_scope(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> RetrievalScope | None:
        row = connection.execute(
            "SELECT * FROM run_retrieval_scope WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return RetrievalScope(
            release_event_id=str(row["release_event_id"]),
            metric_ids=tuple(str(item) for item in json.loads(str(row["metric_ids_json"]))),
            period=str(row["period"]),
            priority=str(row["priority"]),
            source_url=str(row["source_url"]) if row["source_url"] is not None else None,
        )

    def _retrieval_attempts(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> tuple[dict[str, object], ...]:
        rows = connection.execute(
            """
            SELECT * FROM run_retrieval_attempt WHERE run_id=? ORDER BY sequence
            """,
            (run_id,),
        ).fetchall()
        return tuple(
            {
                "channel": str(row["channel"]),
                "outcome": str(row["outcome"]),
                "classification": (
                    str(row["classification"]) if row["classification"] is not None else None
                ),
                "latency_ms": int(row["latency_ms"]),
                "remaining_run_budget": (
                    int(row["remaining_run_budget"])
                    if row["remaining_run_budget"] is not None
                    else None
                ),
                "remaining_daily_budget": (
                    int(row["remaining_daily_budget"])
                    if row["remaining_daily_budget"] is not None
                    else None
                ),
                "budget_charged": bool(row["budget_charged"]),
                "cache_hit": bool(row["cache_hit"]),
                "manual_budget_exemption": bool(row["manual_budget_exemption"]),
                "candidate_source": (
                    str(row["candidate_source"]) if row["candidate_source"] is not None else None
                ),
                "occurred_at": str(row["occurred_at"]),
            }
            for row in rows
        )


def _validated_retrieval_scope(
    command_type: str,
    *,
    database_path: Path,
    model_version_id: str,
    release_event_id: str | None,
    metric_ids: tuple[str, ...],
    period: str | None,
    source_url: str | None,
) -> RetrievalScope | None:
    retrieval_command = command_type in {"targeted_refresh", "manual_deep_search"}
    if not retrieval_command:
        if (
            release_event_id is not None
            or metric_ids
            or period is not None
            or source_url is not None
        ):
            raise ValueError("retrieval_scope_not_allowed_for_command")
        return None
    if not release_event_id or not metric_ids or not period:
        raise ValueError("retrieval_scope_required")
    if len(set(metric_ids)) != len(metric_ids):
        raise ValueError("retrieval_scope_duplicate_metric")
    if command_type == "manual_deep_search" and len(metric_ids) != 1:
        raise ValueError("manual_deep_search_requires_one_explicit_metric")
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.models import ModelRepository

    model_rules = ContextProjectionRules.from_manifest(
        ModelRepository(database_path).manifest(model_version_id)
    )
    definitions_by_id = {
        definition.metric_id: definition for definition in model_rules.metric_definitions
    }
    try:
        definitions = tuple(definitions_by_id[metric_id] for metric_id in metric_ids)
    except KeyError as error:
        raise ValueError("retrieval_scope_metric_not_in_model") from error
    priorities = {definition.priority for definition in definitions}
    if len(priorities) != 1:
        raise ValueError("retrieval_scope_priority_mismatch")
    return RetrievalScope(
        release_event_id=release_event_id,
        metric_ids=metric_ids,
        period=period,
        priority=priorities.pop(),
        source_url=source_url,
    )


def _run_record(
    row: sqlite3.Row,
    *,
    retrieval_scope: RetrievalScope | None,
    retrieval_attempts: tuple[dict[str, object], ...],
) -> RunRecord:
    return RunRecord(
        run_id=str(row["run_id"]),
        command_type=str(row["command_type"]),
        target_business_date=str(row["target_business_date"]),
        model_version_id=str(row["model_version_id"]),
        system_as_of=_parse_time(row["system_as_of"]),
        report_cutoff=_parse_time(row["report_cutoff"]),
        status=str(row["status"]),
        current_step=str(row["current_step"]),
        outcome=str(row["outcome"]) if row["outcome"] is not None else None,
        recoverable=bool(row["recoverable"]),
        next_action=str(row["next_action"]),
        attempt_count=int(row["attempt_count"]),
        consumed_budget={
            str(key): int(value)
            for key, value in json.loads(str(row["consumed_budget_json"])).items()
        },
        projection_set_id=(
            str(row["projection_set_id"]) if row["projection_set_id"] is not None else None
        ),
        error_classification=(
            str(row["error_classification"]) if row["error_classification"] is not None else None
        ),
        retrieval_scope=retrieval_scope,
        retrieval_attempts=retrieval_attempts,
    )


def _schedule_document(row: sqlite3.Row) -> dict[str, object]:
    return {
        "enabled": bool(row["enabled"]),
        "timezone": str(row["timezone"]),
        "start_time": str(row["start_time"]),
        "p0_deadline": str(row["p0_deadline"]),
        "version": int(row["version"]),
    }


def _parse_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _process_is_alive(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


_RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_run (
    run_id TEXT PRIMARY KEY,
    command_type TEXT NOT NULL,
    target_business_date TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    system_as_of TEXT NOT NULL,
    report_cutoff TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step TEXT NOT NULL,
    outcome TEXT,
    recoverable INTEGER NOT NULL,
    next_action TEXT NOT NULL,
    consumed_budget_json TEXT NOT NULL,
    projection_set_id TEXT,
    error_classification TEXT,
    accepted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_command (
    command_id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT NOT NULL,
    client_request_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    accepted_at TEXT NOT NULL,
    UNIQUE(command_type, client_request_id)
);
CREATE TABLE IF NOT EXISTS run_attempt (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    reason TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    outcome TEXT
);
CREATE TABLE IF NOT EXISTS run_step_event (
    step_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    step TEXT NOT NULL,
    event TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS worker_lease (
    lease_name TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    owner_id TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    acquired_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_checkpoint (
    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    kind TEXT NOT NULL,
    reference TEXT NOT NULL,
    verified INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, kind, reference)
);
CREATE TABLE IF NOT EXISTS schedule_configuration (
    version INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL,
    timezone TEXT NOT NULL,
    start_time TEXT NOT NULL,
    p0_deadline TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_RETRIEVAL_RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_retrieval_scope (
    run_id TEXT PRIMARY KEY REFERENCES parent_run(run_id),
    release_event_id TEXT NOT NULL,
    metric_ids_json TEXT NOT NULL,
    period TEXT NOT NULL,
    priority TEXT NOT NULL,
    source_url TEXT
);
CREATE TABLE IF NOT EXISTS run_retrieval_attempt (
    retrieval_attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    release_event_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    channel TEXT NOT NULL,
    outcome TEXT NOT NULL,
    classification TEXT,
    latency_ms INTEGER NOT NULL,
    remaining_run_budget INTEGER,
    remaining_daily_budget INTEGER,
    budget_charged INTEGER NOT NULL,
    cache_hit INTEGER NOT NULL,
    manual_budget_exemption INTEGER NOT NULL,
    candidate_source TEXT,
    occurred_at TEXT NOT NULL,
    physical_request_id TEXT,
    UNIQUE(run_id, sequence)
);
CREATE TABLE IF NOT EXISTS retrieval_negative_cache (
    release_event_id TEXT NOT NULL,
    metric_ids_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(release_event_id, metric_ids_json)
);
CREATE TRIGGER IF NOT EXISTS run_retrieval_scope_no_update
BEFORE UPDATE ON run_retrieval_scope BEGIN
    SELECT RAISE(ABORT, 'run_retrieval_scope_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS run_retrieval_scope_no_delete
BEFORE DELETE ON run_retrieval_scope BEGIN
    SELECT RAISE(ABORT, 'run_retrieval_scope_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS run_retrieval_attempt_no_update
BEFORE UPDATE ON run_retrieval_attempt BEGIN
    SELECT RAISE(ABORT, 'run_retrieval_attempt_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS run_retrieval_attempt_no_delete
BEFORE DELETE ON run_retrieval_attempt BEGIN
    SELECT RAISE(ABORT, 'run_retrieval_attempt_is_immutable');
END;
"""
