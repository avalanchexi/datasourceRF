from __future__ import annotations

import sqlite3


def upgrade_run_cutoffs(connection: sqlite3.Connection) -> None:
    from pring_cycle.full_retrieval import FULL_RETRIEVAL_SCHEMA

    for statement in FULL_RETRIEVAL_SCHEMA:
        connection.execute(statement)
    for statement in RUN_CUTOFF_SCHEMA:
        connection.execute(statement)
    connection.execute(
        "INSERT OR IGNORE INTO run_cutoff_contract "
        "SELECT run_id, CASE WHEN command_type IN ('manual_full','scheduled_full') "
        "THEN 'acquisition_window' ELSE 'explicit' END, system_as_of, 'legacy_stored_cutoff' "
        "FROM parent_run"
    )
    connection.execute(
        "INSERT OR IGNORE INTO run_cutoff_freeze "
        "SELECT run_id, system_as_of FROM parent_run "
        "WHERE current_step NOT IN ('queued','preflight','refreshing_evidence') "
        "OR EXISTS (SELECT 1 FROM run_checkpoint c WHERE c.run_id=parent_run.run_id "
        "AND c.verified=1 AND c.kind IN "
        "('verified_evidence','published_projection','report_snapshot'))"
    )


def cutoff_contract(connection: sqlite3.Connection, run_id: str) -> tuple[str, bool]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='run_cutoff_contract'"
    ).fetchone():
        return "legacy_unknown", False
    row = connection.execute(
        "SELECT c.mode, f.run_id FROM run_cutoff_contract c "
        "LEFT JOIN run_cutoff_freeze f USING(run_id) WHERE c.run_id=?",
        (run_id,),
    ).fetchone()
    if row is None:
        return "legacy_unknown", False
    return str(row[0]), row[0] == "explicit" or row[1] is not None


RUN_CUTOFF_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS run_cutoff_contract ("
    "run_id TEXT PRIMARY KEY REFERENCES parent_run(run_id), "
    "mode TEXT NOT NULL CHECK(mode IN ('explicit','acquisition_window')), "
    "initial_system_as_of TEXT NOT NULL, origin TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS run_cutoff_freeze ("
    "run_id TEXT PRIMARY KEY REFERENCES parent_run(run_id), system_as_of TEXT NOT NULL)",
    *(
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} "
        f"BEFORE {action} ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'run_cutoff_identity_is_immutable'); END"
        for table in ("run_cutoff_contract", "run_cutoff_freeze")
        for action in ("UPDATE", "DELETE")
    ),
)
