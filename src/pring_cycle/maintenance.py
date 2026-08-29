from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

GIB = 1024**3
MIB = 1024**2


@dataclass(frozen=True)
class CapacityState:
    state: str
    free_bytes: int
    allow_non_core_large_tasks: bool
    allow_worker_writes: bool
    serve_reads: bool


@dataclass(frozen=True)
class CleanupResult:
    deleted_object_ids: tuple[str, ...]
    reclaimed_bytes: int
    expired_report_bodies: int


def capacity_state(free_bytes: int) -> CapacityState:
    if free_bytes <= 5 * GIB:
        state = "stop_worker_writes"
        allow_non_core = False
        allow_writes = False
    elif free_bytes <= 10 * GIB:
        state = "restrict_non_core"
        allow_non_core = False
        allow_writes = True
    elif free_bytes <= 20 * GIB:
        state = "warning"
        allow_non_core = True
        allow_writes = True
    else:
        state = "normal"
        allow_non_core = True
        allow_writes = True
    return CapacityState(state, free_bytes, allow_non_core, allow_writes, True)


class MaintenanceRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> MaintenanceRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_MAINTENANCE_SCHEMA)
        return repository

    def register_object(
        self,
        object_id: str,
        path: Path,
        *,
        kind: str,
        created_at: datetime,
        authoritative: bool,
        referenced: bool,
    ) -> None:
        resolved = path.resolve()
        byte_count = resolved.stat().st_size if resolved.is_file() else 0
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO retention_object(
                    object_id, path, kind, created_at, byte_count,
                    authoritative, referenced, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(object_id) DO NOTHING
                """,
                (
                    object_id,
                    str(resolved),
                    kind,
                    created_at.isoformat(),
                    byte_count,
                    int(authoritative),
                    int(referenced),
                ),
            )

    def cleanup(self, *, now: datetime | None = None) -> CleanupResult:
        observed_at = now or datetime.now(UTC)
        deleted: list[str] = []
        reclaimed_bytes = 0
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM retention_object
                WHERE deleted_at IS NULL AND authoritative=0 AND referenced=0
                ORDER BY created_at, object_id
                """
            ).fetchall()
            active_sizes: dict[str, int] = {}
            for row in rows:
                kind = str(row["kind"])
                active_sizes[kind] = active_sizes.get(kind, 0) + int(row["byte_count"])
            for row in rows:
                kind = str(row["kind"])
                created_at = datetime.fromisoformat(str(row["created_at"]))
                age_limit, size_limit = _retention_policy(kind)
                expired = age_limit is not None and observed_at - created_at >= age_limit
                over_capacity = size_limit is not None and active_sizes.get(kind, 0) > size_limit
                if not expired and not over_capacity:
                    continue
                object_path = Path(str(row["path"]))
                if object_path.is_file():
                    object_path.unlink()
                object_id = str(row["object_id"])
                byte_count = int(row["byte_count"])
                connection.execute(
                    "UPDATE retention_object SET deleted_at=? WHERE object_id=?",
                    (observed_at.isoformat(), object_id),
                )
                deleted.append(object_id)
                reclaimed_bytes += byte_count
                active_sizes[kind] = max(0, active_sizes.get(kind, 0) - byte_count)
            expired_report_bodies = 0
            report_table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='report_snapshot'
                """
            ).fetchone()
            if report_table is not None:
                expired_report_bodies = connection.execute(
                    """
                    UPDATE report_snapshot SET body_json='{}', body_retained=0
                    WHERE body_retained=1 AND created_at <= ?
                    """,
                    ((observed_at - timedelta(days=30)).isoformat(),),
                ).rowcount
            connection.execute(
                """
                INSERT INTO maintenance_audit(
                    operation, outcome, deleted_count, reclaimed_bytes, created_at
                ) VALUES ('cleanup', 'completed', ?, ?, ?)
                """,
                (len(deleted), reclaimed_bytes, observed_at.isoformat()),
            )
        return CleanupResult(tuple(deleted), reclaimed_bytes, expired_report_bodies)

    def audit_events(self) -> tuple[dict[str, object], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM maintenance_audit ORDER BY audit_id"
            ).fetchall()
        return tuple(
            {
                "operation": str(row["operation"]),
                "outcome": str(row["outcome"]),
                "deleted_count": int(row["deleted_count"]),
                "reclaimed_bytes": int(row["reclaimed_bytes"]),
            }
            for row in rows
        )

    def record_upgrade_failure(self, reason: str, *, now: datetime | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_integrity(singleton, status, reason, updated_at)
                VALUES (1, 'reinitialize_required', ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    status=excluded.status, reason=excluded.reason,
                    updated_at=excluded.updated_at
                """,
                (reason, (now or datetime.now(UTC)).isoformat()),
            )

    def runtime_integrity(self) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runtime_integrity WHERE singleton=1").fetchone()
        if row is None:
            status = "ok"
            reason: str | None = None
        else:
            status = str(row["status"])
            reason = str(row["reason"])
        return {
            "status": status,
            "reason": reason,
            "backup_mode": "none",
            "destructive_recovery_available": False,
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _retention_policy(kind: str) -> tuple[timedelta | None, int | None]:
    return {
        "unverified_response": (timedelta(days=7), GIB),
        "log": (timedelta(days=14), 200 * MIB),
        "orphan_artifact": (timedelta(days=7), None),
    }.get(kind, (None, None))


_MAINTENANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS retention_object (
    object_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    authoritative INTEGER NOT NULL,
    referenced INTEGER NOT NULL,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS maintenance_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    deleted_count INTEGER NOT NULL,
    reclaimed_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_integrity (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
