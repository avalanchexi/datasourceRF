"""Versioned run observations. Read paths do not create or repair historical summaries."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.storage import database_connection

SCHEMA = "run-health-v0001"
TERMINAL = {"completed", "cancelled", "failed", "action_required", "interrupted"}
# Request results that mean the call itself failed, as opposed to answered without a value.
REQUEST_FAILURES = {"failed", "interrupted", "timeout", "error"}


def _elapsed(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    return seconds if seconds >= 0 else None


@dataclass(frozen=True)
class ProducerRun:
    """The full run that produced a projection, as pages read it.

    ``summary`` is that run's persisted health summary, or ``None`` when the run has not
    finished or predates summaries; pages say so rather than inventing figures.
    """

    run_id: str
    summary: dict[str, Any] | None


class RunHealth:
    def __init__(self, database: Path) -> None:
        self.database = database

    def latest(self, run_id: str) -> dict[str, Any] | None:
        with database_connection(self.database) as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='run_health_summary'"
            ).fetchone():
                return None
            row = connection.execute(
                "SELECT document_json FROM run_health_summary WHERE run_id=? "
                "ORDER BY rowid DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def history(self) -> list[dict[str, Any]]:
        with database_connection(self.database) as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='run_health_summary'"
            ).fetchone():
                return []
            rows = connection.execute(
                "SELECT document_json FROM run_health_summary WHERE rowid IN "
                "(SELECT MAX(rowid) FROM run_health_summary GROUP BY run_id) "
                "ORDER BY rowid DESC"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def finish(self, run_id: str, *, now: datetime | None = None) -> None:
        from pring_cycle.runs import RunRepository

        with database_connection(self.database) as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='run_health_summary'"
            ).fetchone():
                return
        run = RunRepository(self.database).get(run_id)
        if run.status not in TERMINAL:
            return
        ended = (now or datetime.now(UTC)).isoformat()
        with database_connection(self.database) as connection:
            connection.execute(
                "UPDATE run_attempt SET completed_at=COALESCE(completed_at, ?), "
                "outcome=COALESCE(outcome, ?) WHERE attempt_id="
                "(SELECT MAX(attempt_id) FROM run_attempt WHERE run_id=? "
                "AND reason != 'duplicate_manual_submission')",
                (ended, run.status, run_id),
            )
        document = self.observe(run_id)
        with database_connection(self.database) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO run_health_summary VALUES (?, ?, ?, ?)",
                (
                    run_id,
                    document["attempt"],
                    run.status,
                    json.dumps(document, ensure_ascii=False, sort_keys=True),
                ),
            )

    def observe(self, run_id: str) -> dict[str, Any]:
        from pring_cycle.context_projection import ContextProjectionRules
        from pring_cycle.freshness import batch_freshness
        from pring_cycle.models import ModelRepository
        from pring_cycle.projections import ProjectionSetRepository
        from pring_cycle.reports import ReportRepository
        from pring_cycle.runs import RunRepository

        runs = RunRepository(self.database)
        run = runs.get(run_id)
        plan = runs.full_retrieval_plan(run_id)
        with database_connection(self.database) as connection:
            connection.row_factory = sqlite3.Row
            attempt = connection.execute(
                "SELECT * FROM run_attempt WHERE run_id=? "
                "AND reason != 'duplicate_manual_submission' ORDER BY attempt_id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            attempt_count = connection.execute(
                "SELECT COUNT(*) FROM run_attempt WHERE run_id=? "
                "AND reason != 'duplicate_manual_submission'",
                (run_id,),
            ).fetchone()[0]
        # Only this run's projection and report can describe its outcome.
        projection = (
            ProjectionSetRepository(self.database).get(run.projection_set_id)
            if run.projection_set_id
            else None
        )
        report_id = next(
            (
                item["reference"]
                for item in reversed(runs.reusable_checkpoints(run_id))
                if item["kind"] == "report_snapshot"
            ),
            None,
        )
        report = ReportRepository(self.database).get(report_id) if report_id else None
        started = str(attempt["started_at"]) if attempt else None
        ended = attempt["completed_at"] if attempt else None
        events = [
            event
            for event in runs.step_history(run_id)
            if started is None or event["occurred_at"] >= started
        ]
        segments: list[dict[str, Any]] = []
        for index, event in enumerate(events):
            if event["step"] == "completed":
                continue
            end = events[index + 1]["occurred_at"] if index + 1 < len(events) else ended
            segments.append(
                {
                    "step": event["step"],
                    "started_at": event["occurred_at"],
                    "ended_at": end,
                    "seconds": _elapsed(event["occurred_at"], end),
                }
            )
        try:
            catalog = ContextProjectionRules.from_manifest(
                ModelRepository(self.database).manifest(run.model_version_id)
            ).metric_catalog_version
        except (LookupError, ValueError):
            catalog = None
        requests = self.requests(run, plan)
        gaps = gap_diagnostics(run, plan, requests)
        return {
            "schema_version": SCHEMA,
            "run_id": run_id,
            "attempt": attempt_count,
            "command_type": run.command_type,
            "model_version_id": run.model_version_id,
            "catalog_version": catalog,
            "projection_set_id": run.projection_set_id,
            "target_business_date": run.target_business_date,
            "system_as_of": run.system_as_of.isoformat(),
            "status": run.status,
            "current_step": run.current_step,
            "next_action": run.next_action,
            "error_classification": run.error_classification,
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": _elapsed(started, ended),
            "segments": segments,
            "request_basis": "physical_dispatched_v1",
            "request_count": len(requests),
            "request_outcomes": dict(Counter(item["result"] for item in requests)),
            "requests": requests,
            "budget": run.consumed_budget,
            "completeness": projection.envelope.completeness if projection else None,
            "coverage": projection.datasets.get("macro", {}).get("coverage")
            if projection
            else None,
            "report_status": report.status if report else None,
            "gaps": gaps,
            "gap_counts": dict(Counter(item["diagnosis"] for item in gaps)),
            "freshness_counts": dict(
                Counter(
                    str(row["status"]) for row in batch_freshness(self.database, run_id).values()
                )
            ),
            "final_plan_available": plan.get("final") is not None,
        }

    def requests(self, run: Any, plan: dict[str, Any]) -> list[dict[str, Any]]:
        with database_connection(self.database) as connection:
            tracked = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='acquisition_dispatch'"
            ).fetchone()
            dispatched = (
                {
                    row[0]
                    for row in connection.execute("SELECT acquisition_id FROM acquisition_dispatch")
                }
                if tracked
                else None
            )
        ledger = run.retrieval_ledger or {}
        gaps = {item["gap_id"]: item for item in ledger.get("gaps", [])}
        # One physical request may deliver many claims or serve many gaps. Never count edges.
        rows: dict[str, dict[str, Any]] = {}
        for request in ledger.get("requests", []):
            if not request.get("charged_to_run"):
                continue
            if (
                dispatched is not None
                and request.get("acquisition_id")
                and request["acquisition_id"] not in dispatched
            ):
                continue
            key = request.get("acquisition_id") or request["request_id"]
            related = [gaps[key] for key in request.get("gap_ids", []) if key in gaps]
            rows[key] = {
                "request_id": request["request_id"],
                "acquisition_id": request.get("acquisition_id"),
                "channel": request["channel"],
                "phase": "retrieval",
                "result": request.get("outcome") or request["state"],
                "classification": request.get("classification"),
                "metric_ids": sorted({item["metric_id"] for item in related}),
                "periods": sorted({item["period"] for item in related}),
                "gap_ids": request.get("gap_ids", []),
                "started_at": request.get("started_at"),
                "ended_at": request.get("completed_at"),
            }
        for request in plan.get("acquisitions", []):
            key = request["acquisition_id"]
            if dispatched is not None and key not in dispatched:
                continue
            counts = {
                "source_record_count": request.get("source_record_count"),
                "claim_count": request.get("ingested_claim_count"),
            }
            if key in rows:
                rows[key]["metric_ids"] = sorted(
                    set(rows[key]["metric_ids"]) | set(request["metric_ids"])
                )
                rows[key].update(counts)
                rows[key]["structure_check"] = request.get("structure_check")
                continue
            rows[key] = {
                "request_id": key,
                "acquisition_id": key,
                "channel": request["provider"],
                "phase": request["phase"],
                "result": request.get("ingest_result") or request["state"],
                "classification": request.get("error_type"),
                "structure_check": request.get("structure_check"),
                "started_at": request.get("started_at"),
                "ended_at": request.get("validated_at") or request.get("received_at"),
                "metric_ids": request["metric_ids"],
                "periods": [request["period"]] if request.get("period") else [],
                "gap_ids": [],
                **counts,
            }
        return list(rows.values())


def gap_diagnostics(
    run: Any, plan: dict[str, Any], requests: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    final = plan.get("final") or {}
    source = final.get("gaps")
    if source is None:
        source = [
            item for item in (plan.get("initial") or {}).get("requirements", []) if "period" in item
        ]
    from pring_cycle.full_retrieval import planned_scopes

    adopted = set((plan.get("adoption") or {}).get("selected_claim_ids", []))
    planned = planned_scopes(plan)
    rows = []
    for gap in source:
        scopes = [
            scope
            for scope in planned
            if gap["metric_id"] in scope.get("metric_ids", [])
            and gap["period"] == scope.get("period")
        ]
        events = {scope["release_event_id"] for scope in scopes}
        attempts = [
            item for item in run.retrieval_attempts if item.get("release_event_id") in events
        ]
        linked = [
            item
            for item in requests
            if gap["metric_id"] in item["metric_ids"]
            and (not item["periods"] or gap["period"] in item["periods"])
        ]
        reasons = {str(item.get("classification")) for item in linked}
        if gap.get("complete") or (not final and gap.get("status") == "local_complete"):
            diagnosis = (
                "adopted" if adopted.intersection(gap.get("selected_claim_ids", [])) else "held"
            )
        elif gap.get("release_gate"):
            diagnosis = (
                "not_published"
                if gap["release_gate"]
                in {"not_due", "not_yet_published", "not_released", "awaiting_release"}
                else "release_gate"
            )
        elif any(
            item["result"] in {"rejected", "refused", "invalid"}
            or item.get("structure_check") == "rejected"
            for item in linked
        ) or any(item.get("classification") == "semantic_validation_failed" for item in attempts):
            diagnosis = "rejected"
        elif any(item["result"] in REQUEST_FAILURES for item in linked):
            diagnosis = "request_failed"
        elif any("budget" in reason or "quota" in reason for reason in reasons) or any(
            item.get("outcome") == "budget_exhausted"
            or item.get("classification") == "quota_exhausted"
            for item in attempts
        ):
            diagnosis = "budget_stopped"
        elif not final and run.status in TERMINAL:
            diagnosis = "flow_stopped"
        elif linked:
            diagnosis = "not_delivered"
        else:
            diagnosis = "reason_not_recorded"
        rows.append(
            {
                **gap,
                "diagnosis": diagnosis,
                "request_ids": [item["request_id"] for item in linked],
                "attempts": [
                    {
                        key: item.get(key)
                        for key in ("sequence", "channel", "outcome", "classification")
                    }
                    for item in attempts
                ],
            }
        )
    return rows


def filtered_flow(document: dict[str, Any], filters: dict[str, str]) -> dict[str, Any]:
    requests = [
        item
        for item in document.get("requests", [])
        if all(
            not filters.get(key) or str(item.get(key)) == filters[key]
            for key in ("channel", "phase", "result")
        )
        and (not filters.get("metric") or filters["metric"] in item.get("metric_ids", []))
    ]
    links: Counter[tuple[str, str]] = Counter()
    for item in requests:
        links[("来源:" + str(item["channel"]), "环节:" + str(item["phase"]))] += 1
        links[("环节:" + str(item["phase"]), "结果:" + str(item["result"]))] += 1
    return {
        "unit": "physical_request",
        "count": len(requests),
        "requests": requests,
        "links": [
            {"source": source, "target": target, "value": value}
            for (source, target), value in links.items()
        ],
    }


def comparison(document: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "schema_version",
        "command_type",
        "model_version_id",
        "catalog_version",
        "request_basis",
    )
    previous = next(
        (
            item
            for item in history
            if item["run_id"] != document["run_id"]
            and item.get("ended_at")
            and document.get("started_at")
            and item["ended_at"] <= document["started_at"]
            and all(item.get(key) == document.get(key) for key in keys)
        ),
        None,
    )
    if previous is None:
        return {"reason": "no_comparable_retained_summary"}
    before, after = previous.get("duration_seconds"), document.get("duration_seconds")
    return {
        "run_id": previous["run_id"],
        "duration_delta_seconds": after - before
        if before is not None and after is not None
        else None,
        "request_delta": document["request_count"] - previous["request_count"],
    }
