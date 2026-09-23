"""Keep 120 SSE sessions of details, summaries and batches; delete the rest (ADR-0022).

The window ends at the latest successful full run's target day and starts at the first
session of that run's validated 120-session calendar. Everything the application wrote for
an earlier day is deleted: source claims and their acquisition links (details), derived
observations, projections, assessments, gap notices and reports (summaries), and the runs
themselves with their ledgers (batches). An original is deleted once no remaining call
refers to it. The current projection is never deleted.

The tables were append-only by trigger. Their delete guards are lifted inside this one
transaction and put back before it commits, so every other writer still cannot delete.
Formula lookback older than the window is fetched by each run, used, and removed here at
the run's end; the run's own acquisition rows keep the call parameters and response hashes.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_connection

RETENTION_SESSIONS = 120

# Run-owned ledgers, deleted with their run.
_RUN_TABLES = (
    "run_step_event",
    "run_checkpoint",
    "run_command",
    "run_attempt",
    "run_cutoff_contract",
    "run_cutoff_freeze",
    "run_retrieval_attempt",
    "run_retrieval_scope",
    "full_run_gap_plan",
    "full_run_acquisition",
    "retrieval_candidate_validation",
    "retrieval_query",
    "retrieval_run_gap",
    "worker_lease",
)


@dataclass(frozen=True)
class RetentionResult:
    window_start: str | None
    window_end: str | None
    deleted_rows: dict[str, int]
    deleted_artifacts: int
    reclaimed_bytes: int


def retention_window(connection: sqlite3.Connection) -> tuple[str, str] | None:
    """The latest successful full run's target day and its calendar's first session."""
    row = connection.execute(
        """
        SELECT r.run_id, r.target_business_date FROM parent_run r
        WHERE r.status='completed' AND r.command_type IN ('manual_full', 'scheduled_full')
        ORDER BY r.target_business_date DESC, r.accepted_at DESC LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    run_id, end = str(row[0]), str(row[1])
    plan = connection.execute(
        "SELECT document_json FROM full_run_gap_plan WHERE run_id=? AND phase='final'",
        (run_id,),
    ).fetchone()
    dates = json.loads(plan[0]).get("daily_window", {}).get("dates", []) if plan else []
    if len(dates) < RETENTION_SESSIONS or dates[-1] != end:
        return None  # No validated calendar: nothing can be safely judged out of window.
    return str(dates[-RETENTION_SESSIONS]), end


def prune_to_window(paths: RuntimePaths) -> RetentionResult:
    """Delete everything that falls before the retention window; safe to repeat."""
    deleted: dict[str, int] = {}
    with database_connection(paths.database) as connection:
        window = retention_window(connection)
        if window is None:
            return RetentionResult(None, None, {}, 0, 0)
        start, end = window
        connection.execute("BEGIN IMMEDIATE")
        guards = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE '%_no_delete'"
            " AND name <> 'model_version_no_delete'"
        ).fetchall()
        for name, _sql in guards:
            connection.execute(f"DROP TRIGGER {name}")

        def delete(table: str, where: str, *args: object) -> None:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                return
            count = connection.execute(f"DELETE FROM {table} WHERE {where}", args).rowcount
            if count:
                deleted[table] = deleted.get(table, 0) + count

        connection.execute(
            "CREATE TEMP TABLE retired_run AS SELECT run_id FROM parent_run "
            "WHERE target_business_date < ? AND status NOT IN ('queued', 'running')",
            (start,),
        )
        retired = "run_id IN (SELECT run_id FROM retired_run)"
        # Summaries.
        connection.execute(
            "CREATE TEMP TABLE retired_projection AS SELECT projection_set_id FROM projection_set "
            "WHERE json_extract(envelope_json, '$.target_business_date') < ? "
            "AND projection_set_id NOT IN (SELECT projection_set_id FROM current_projection)",
            (start,),
        )
        retired_projection = (
            "projection_set_id IN (SELECT projection_set_id FROM retired_projection)"
        )
        delete(
            "report_explanation_review",
            "report_snapshot_id IN (SELECT report_snapshot_id FROM report_snapshot "
            "WHERE target_business_date < ?)",
            start,
        )
        delete(
            "report_attempt",
            "report_snapshot_id IN (SELECT report_snapshot_id FROM report_snapshot "
            "WHERE target_business_date < ?)",
            start,
        )
        delete("report_snapshot", "target_business_date < ?", start)
        delete("evidence_bundle", retired_projection)
        delete(
            "data_gap_notice",
            "assessment_id IN (SELECT assessment_id FROM p0_assessment "
            "WHERE target_business_date < ?)",
            start,
        )
        delete("p0_assessment", "target_business_date < ?", start)
        delete("analytical_dataset", retired_projection)
        delete("projection_set", retired_projection)
        delete("derived_observation", "date(as_of_cutoff) < ?", start)
        delete("evidence_snapshot", "date(as_of_cutoff) < ?", start)
        # Details.
        connection.execute(
            "CREATE TEMP TABLE retired_claim AS SELECT claim_id FROM source_claim "
            "WHERE period_end < ?",
            (start,),
        )
        delete("source_claim_acquisition", "claim_id IN (SELECT claim_id FROM retired_claim)")
        delete("source_claim", "claim_id IN (SELECT claim_id FROM retired_claim)")
        delete(
            "release_event",
            "release_event_id NOT IN (SELECT release_event_id FROM source_claim)",
        )
        delete("retrieval_attempt", "date(fetched_at) < ?", start)
        # Batches.
        for table in _RUN_TABLES:
            delete(table, retired)
        delete(
            "retrieval_request_gap",
            "request_id IN (SELECT request_id FROM retrieval_physical_request WHERE "
            + retired
            + ")",
        )
        delete(
            "retrieval_request_event",
            "request_id IN (SELECT request_id FROM retrieval_physical_request WHERE "
            + retired
            + ")",
        )
        delete("retrieval_physical_request", retired)
        delete("batch_freshness", "batch_id IN (SELECT run_id FROM retired_run)")
        delete("release_schedule", "batch_id IN (SELECT run_id FROM retired_run)")
        delete("parent_run", retired)
        # Calls nothing still refers to: no remaining claim, batch or retrieval request.
        delete(
            "acquisition_request",
            "acquisition_id NOT IN (SELECT acquisition_id FROM source_claim_acquisition) "
            "AND acquisition_id NOT IN (SELECT acquisition_id FROM full_run_acquisition) "
            "AND acquisition_id NOT IN (SELECT acquisition_id FROM retrieval_physical_request "
            "WHERE acquisition_id IS NOT NULL)",
        )
        orphans = _orphan_artifacts(connection)
        for content_hash in orphans:
            connection.execute(
                "DELETE FROM artifact_reference WHERE content_hash=?", (content_hash,)
            )
            connection.execute("DELETE FROM artifact WHERE content_hash=?", (content_hash,))
        for _name, sql in guards:
            connection.execute(sql)
        connection.execute("DROP TABLE retired_run")
        connection.execute("DROP TABLE retired_projection")
        connection.execute("DROP TABLE retired_claim")
    reclaimed = _remove_files(paths.artifacts, orphans)
    return RetentionResult(start, end, deleted, len(orphans), reclaimed)


def _orphan_artifacts(connection: sqlite3.Connection) -> list[str]:
    """Originals every reference of which names an acquisition that no longer exists."""
    remaining = {
        str(row[0]) for row in connection.execute("SELECT acquisition_id FROM acquisition_request")
    }
    references: dict[str, list[str]] = {}
    for content_hash, source_reference in connection.execute(
        "SELECT content_hash, source_reference FROM artifact_reference"
    ):
        references.setdefault(str(content_hash), []).append(str(source_reference))
    orphans = []
    for content_hash, sources in references.items():
        owners = [source.split(":", 1)[0] for source in sources]
        if all(owner.startswith("acquisition-") for owner in owners) and not any(
            owner in remaining for owner in owners
        ):
            orphans.append(content_hash)
    return orphans


def _remove_files(artifacts: Path, hashes: list[str]) -> int:
    reclaimed = 0
    for content_hash in hashes:
        path = artifacts / content_hash[:2] / content_hash
        if path.is_file():
            reclaimed += path.stat().st_size
            path.unlink()
    return reclaimed
