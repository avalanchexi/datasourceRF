"""Keep 120 SSE sessions of details, summaries and batches; delete the rest (ADR-0022).

The window ends at the latest successful full run's target day and starts at the first
session of that run's validated 120-session calendar. Everything the application wrote for
an earlier day is deleted: source claims with their acquisition links and matched quotes
(details), derived observations, projections, assessments, gap notices and reports
(summaries), and the runs themselves with their ledgers (batches). An original is deleted
once no remaining call refers to it. The current projection is never deleted.

The tables were append-only by trigger. Their delete guards are lifted inside this one
transaction and put back before it commits, so every other writer still cannot delete.
Formula lookback older than the window is fetched by each run, used, and removed here at
the run's end; the run's own acquisition rows keep the call parameters and response hashes.
Three kinds of older claims stay: a metric in force until changed keeps its current baseline
(ADR-0028); a derived observation still kept keeps the claims it was computed from (ticket
29); and a projection still kept keeps the claims it cites until it expires (lookback 08),
except the three cores' prices, which go with the window as before. The last two keep them
with their acquisition links and originals, so what was computed or published can be read
back to its source.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pring_cycle.metric_contracts import EFFECTIVE_UNTIL_CHANGED_METRICS
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.storage import database_connection

RETENTION_SESSIONS = 120
# How long a TuShare call is kept for its day's quota to count it, whatever refers to it.
QUOTA_COUNTED = timedelta(days=2)

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


def prune_to_window(paths: RuntimePaths, *, now: datetime | None = None) -> RetentionResult:
    """Delete everything that falls before the retention window; safe to repeat."""
    deleted: dict[str, int] = {}
    with database_connection(paths.database) as connection:
        window = retention_window(connection)
        if window is None:
            short_lived = _expire_short_lived_originals(connection, now or datetime.now(UTC))
            reclaimed = _remove_files(paths.artifacts, short_lived)
            return RetentionResult(None, None, {}, len(short_lived), reclaimed)
        start, end = window
        connection.execute("BEGIN IMMEDIATE")
        short_lived = _expire_short_lived_originals(connection, now or datetime.now(UTC))
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
        delete("uncorrectable_day", "target_business_date < ?", start)
        delete("analytical_dataset", retired_projection)
        delete("publication_impact", retired_projection)
        delete(
            "publication_correction",
            retired_projection
            + " OR corrected_by_projection_set_id IN (SELECT projection_set_id FROM "
            "retired_projection)",
        )
        delete("projection_set", retired_projection)
        delete("derived_observation", "date(as_of_cutoff) < ?", start)
        # The evidence a kept projection froze goes only with the projection (lookback 08).
        delete(
            "evidence_snapshot",
            "date(as_of_cutoff) < ? AND evidence_snapshot_id NOT IN (SELECT "
            "json_extract(envelope_json, '$.evidence_snapshot_id') FROM projection_set "
            "WHERE json_extract(envelope_json, '$.evidence_snapshot_id') IS NOT NULL)",
            start,
        )
        # Details.
        # A metric in force until changed keeps each member's latest period: it is the
        # current baseline, however old (ADR-0028). A derived observation still kept keeps
        # the claims it was computed from; the expired ones are already gone (ticket 29).
        # A projection still kept keeps every claim it cites, in its datasets or in the
        # evidence it froze, until it expires itself (lookback 08). The three cores' prices
        # are the exception: their trend reads all the history held, so prices kept for
        # being cited would be read and cited again, and pile up run after run.
        baselines = sorted(EFFECTIVE_UNTIL_CHANGED_METRICS)
        connection.execute(
            "CREATE TEMP TABLE retired_claim AS SELECT claim_id FROM source_claim AS c "
            "WHERE period_end < ? AND NOT (metric_id IN (SELECT value FROM json_each(?)) "
            "AND period_end = (SELECT max(period_end) FROM source_claim AS latest "
            "WHERE latest.metric_id=c.metric_id AND latest.dimensions_json=c.dimensions_json)) "
            "AND claim_id NOT IN (SELECT parent.value FROM derived_observation AS d, "
            "json_each(d.input_observation_version_ids_json) AS parent "
            "WHERE parent.value IS NOT NULL) "
            "AND (metric_id IN (SELECT value FROM json_each(?)) "
            "OR claim_id NOT IN (SELECT cited.value FROM analytical_dataset AS a, "
            "json_tree(a.document_json) AS cited WHERE cited.type='text') "
            "AND claim_id NOT IN (SELECT frozen.value FROM projection_set AS p "
            "JOIN evidence_snapshot AS s "
            "ON s.evidence_snapshot_id=json_extract(p.envelope_json, '$.evidence_snapshot_id'), "
            "json_each(s.observation_version_ids_json) AS frozen WHERE frozen.value IS NOT NULL))",
            (start, json.dumps(baselines), json.dumps(sorted(CORE_API_IDENTITIES))),
        )
        delete("claim_matched_quote", "claim_id IN (SELECT claim_id FROM retired_claim)")
        delete("source_claim_acquisition", "claim_id IN (SELECT claim_id FROM retired_claim)")
        delete("source_claim", "claim_id IN (SELECT claim_id FROM retired_claim)")
        # A recheck verdict goes once none of the claims it judged is kept (ADR-0039).
        delete(
            "media_conflict_recheck",
            "NOT EXISTS (SELECT 1 FROM json_each(contested_claim_ids_json) AS judged "
            "JOIN source_claim AS kept ON kept.claim_id = judged.value)",
        )
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
        # Calls nothing still refers to: no remaining claim, batch or retrieval request. A
        # TuShare call of the last two days stays: it is what the day's quota counts (ticket 31).
        delete(
            "acquisition_request",
            "acquisition_id NOT IN (SELECT acquisition_id FROM source_claim_acquisition) "
            "AND acquisition_id NOT IN (SELECT acquisition_id FROM full_run_acquisition) "
            "AND acquisition_id NOT IN (SELECT acquisition_id FROM retrieval_physical_request "
            "WHERE acquisition_id IS NOT NULL) "
            "AND NOT (provider='tushare' AND julianday(started_at) >= julianday(?))",
            ((now or datetime.now(UTC)) - QUOTA_COUNTED).isoformat(),
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
    reclaimed = _remove_files(paths.artifacts, [*short_lived, *orphans])
    return RetentionResult(start, end, deleted, len(short_lived) + len(orphans), reclaimed)


def _expire_short_lived_originals(connection: sqlite3.Connection, now: datetime) -> list[str]:
    """Drop news and media page originals older than three days (ADR-0026).

    Only the stored bytes go: the acquisition keeps its hash, and each adopted value keeps
    its matched quote, which is what traces it from then on.
    """
    from pring_cycle.news_rules import MEDIA_PAGE_API
    from pring_cycle.tushare_news import NEWS_API, NEWS_ORIGINAL_RETENTION

    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='acquisition_request'"
    ).fetchone():
        return []
    expired = {
        str(row[0])
        for row in connection.execute(
            "SELECT acquisition_id FROM acquisition_request WHERE api_name IN (?, ?) "
            "AND received_at < ?",
            (NEWS_API, MEDIA_PAGE_API, (now - NEWS_ORIGINAL_RETENTION).astimezone(UTC).isoformat()),
        )
    }
    if not expired:
        return []
    references: dict[str, set[str]] = {}
    for content_hash, source_reference in connection.execute(
        "SELECT content_hash, source_reference FROM artifact_reference"
    ):
        references.setdefault(str(content_hash), set()).add(str(source_reference).split(":", 1)[0])
    hashes = [digest for digest, owners in references.items() if owners <= expired]
    for digest in hashes:
        connection.execute("DELETE FROM artifact_reference WHERE content_hash=?", (digest,))
        connection.execute("DELETE FROM artifact WHERE content_hash=?", (digest,))
    return hashes


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
