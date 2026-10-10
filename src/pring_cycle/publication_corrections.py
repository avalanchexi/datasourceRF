"""Publications computed on a value read for the wrong period, and what corrected them.

A projection whose frozen model input holds a news claim its page's title or address dates
otherwise than its period (``news_rules``, audit 06), or a derived value computed from one,
was computed on a wrong value. It stays as published, with its reports (ADR-0022,
ADR-0036): it is marked affected, and a later projection of the same business day whose
model input holds none of them is recorded as its correction. A projection of a day no run
publishes again stays marked, uncorrected: history is not recomputed. Reports follow their
projection. Rows are only appended, when a projection is published (and once, on the
projections kept when the marks were introduced), and go with their projection at
retention.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from pring_cycle.batches import current_batch_id

WRONG_PERIOD_VALUE = "wrong_period_value"

PUBLICATION_CORRECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS publication_impact (
    projection_set_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    claim_ids_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    batch_id TEXT,
    PRIMARY KEY (projection_set_id, reason)
);
CREATE TABLE IF NOT EXISTS publication_correction (
    projection_set_id TEXT NOT NULL,
    corrected_by_projection_set_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    batch_id TEXT,
    PRIMARY KEY (projection_set_id, corrected_by_projection_set_id, reason)
);
CREATE INDEX IF NOT EXISTS publication_correction_by
ON publication_correction(corrected_by_projection_set_id);
CREATE TRIGGER IF NOT EXISTS publication_impact_no_update
BEFORE UPDATE ON publication_impact
BEGIN SELECT RAISE(ABORT, 'publication_impact_is_append_only'); END;
CREATE TRIGGER IF NOT EXISTS publication_impact_no_delete
BEFORE DELETE ON publication_impact
BEGIN SELECT RAISE(ABORT, 'publication_impact_is_append_only'); END;
CREATE TRIGGER IF NOT EXISTS publication_correction_no_update
BEFORE UPDATE ON publication_correction
BEGIN SELECT RAISE(ABORT, 'publication_correction_is_append_only'); END;
CREATE TRIGGER IF NOT EXISTS publication_correction_no_delete
BEFORE DELETE ON publication_correction
BEGIN SELECT RAISE(ABORT, 'publication_correction_is_append_only'); END;
"""

# The claims dated otherwise and every derived value computed from one, however deep.
_TAINTED = (
    "WITH RECURSIVE tainted(id) AS (SELECT value FROM json_each(?) UNION "
    "SELECT d.derived_observation_id FROM derived_observation AS d, "
    "json_each(d.input_observation_version_ids_json) AS input "
    "JOIN tainted AS t ON input.value = t.id) "
)


def record_publication_corrections(
    connection: sqlite3.Connection, projection_set_id: str, target_business_date: str
) -> None:
    """Mark the kept projections computed on a value read for the wrong period, and record
    ``projection_set_id``, just published, as the correction of its day's marked ones when
    it is not marked itself."""
    if projection_set_id in mark_affected_publications(connection) or not _tables_exist(
        connection, "publication_impact"
    ):
        return
    connection.execute(
        "INSERT OR IGNORE INTO publication_correction (projection_set_id, "
        "corrected_by_projection_set_id, reason, recorded_at, batch_id) "
        "SELECT i.projection_set_id, ?, i.reason, ?, ? FROM publication_impact AS i "
        "JOIN projection_set AS p USING (projection_set_id) "
        "WHERE json_extract(p.envelope_json, '$.target_business_date') = ? "
        "AND i.projection_set_id <> ?",
        (
            projection_set_id,
            datetime.now(UTC).isoformat(),
            current_batch_id(),
            target_business_date,
            projection_set_id,
        ),
    )


def mark_affected_publications(connection: sqlite3.Connection) -> frozenset[str]:
    """Mark each kept projection whose model input holds a value read for the wrong period
    (a claim, or a value derived from one); the ones so held now. Run on each publication,
    and once on the projections kept when the marks were introduced."""
    from pring_cycle.news_rules import news_claims_dated_otherwise

    if not _tables_exist(
        connection,
        "publication_impact",
        "claim_matched_quote",
        "derived_observation",
        "analytical_dataset",
    ):
        return frozenset()
    wrong = news_claims_dated_otherwise(connection)
    if not wrong:
        return frozenset()
    rows = connection.execute(
        _TAINTED + "SELECT d.projection_set_id, input.value FROM analytical_dataset AS d, "
        "json_each(d.document_json, '$.model_input_observation_version_ids') AS input "
        "WHERE d.dataset_name='macro' AND input.value IN (SELECT id FROM tainted)",
        (json.dumps(sorted(wrong)),),
    ).fetchall()
    affected: dict[str, set[str]] = {}
    for affected_set, input_id in rows:
        affected.setdefault(str(affected_set), set()).add(str(input_id))
    now = datetime.now(UTC).isoformat()
    connection.executemany(
        "INSERT OR IGNORE INTO publication_impact "
        "(projection_set_id, reason, claim_ids_json, recorded_at, batch_id) VALUES (?, ?, ?, ?, ?)",
        [
            (affected_set, WRONG_PERIOD_VALUE, json.dumps(sorted(ids)), now, current_batch_id())
            for affected_set, ids in sorted(affected.items())
        ],
    )
    return frozenset(affected)


def publication_corrections(
    connection: sqlite3.Connection, projection_set_id: str
) -> dict[str, Any]:
    """What is recorded of a projection: why it was affected, which later projections
    corrected it, which earlier ones it corrects. Empty when nothing is."""
    if not _tables_exist(connection, "publication_impact"):
        return {}
    affected = [
        {"reason": str(reason), "claim_ids": json.loads(str(claim_ids))}
        for reason, claim_ids in connection.execute(
            "SELECT reason, claim_ids_json FROM publication_impact "
            "WHERE projection_set_id=? ORDER BY reason",
            (projection_set_id,),
        )
    ]
    corrected_by = _column(
        connection,
        "SELECT DISTINCT corrected_by_projection_set_id FROM publication_correction "
        "WHERE projection_set_id=? ORDER BY 1",
        projection_set_id,
    )
    corrects = _column(
        connection,
        "SELECT DISTINCT projection_set_id FROM publication_correction "
        "WHERE corrected_by_projection_set_id=? ORDER BY 1",
        projection_set_id,
    )
    if not (affected or corrected_by or corrects):
        return {}
    return {"affected": affected, "corrected_by": corrected_by, "corrects": corrects}


def report_corrections(connection: sqlite3.Connection, projection_set_id: str) -> dict[str, Any]:
    """A report's: its projection's, the projections it names given as their reports."""
    found = publication_corrections(connection, projection_set_id)
    if not found:
        return {}

    def reports(projection_set_ids: list[str]) -> list[str]:
        return _column(
            connection,
            "SELECT report_snapshot_id FROM report_snapshot "
            "WHERE projection_set_id IN (SELECT value FROM json_each(?)) "
            "ORDER BY target_business_date, version",
            json.dumps(projection_set_ids),
        )

    return {
        "affected": found["affected"],
        "corrected_by": reports(found["corrected_by"]),
        "corrects": reports(found["corrects"]),
    }


def _column(connection: sqlite3.Connection, sql: str, *parameters: object) -> list[str]:
    return [str(row[0]) for row in connection.execute(sql, parameters)]


def _tables_exist(connection: sqlite3.Connection, *names: str) -> bool:
    found = connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' "
        "AND name IN (SELECT value FROM json_each(?))",
        (json.dumps(names),),
    ).fetchone()
    return int(found[0]) == len(names)
