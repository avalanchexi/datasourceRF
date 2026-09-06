from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pring_cycle.health_types import DatabaseHealth, WorkerHealth

if TYPE_CHECKING:
    from alembic.config import Config

SCHEMA_HEAD = "0014_acquisition_receipts"


def migrate_database(database_path: Path) -> None:
    from alembic import command
    from sqlalchemy import create_engine, event

    configuration = _alembic_configuration()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    try:
        connection = engine.connect()
        configuration.attributes["connection"] = connection
        try:
            command.upgrade(configuration, "head")
        finally:
            connection.close()
    finally:
        engine.dispose()


def database_health(database_path: Path) -> DatabaseHealth:
    if not database_path.is_file():
        return {"migration": "missing", "status": "missing", "wal": "missing"}

    try:
        with _sqlite_connection(database_path) as connection:
            row = connection.execute("PRAGMA journal_mode").fetchone()
            journal_mode = str(row[0]) if row is not None else "unknown"
            revision_row = connection.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
            current_revision = str(revision_row[0]) if revision_row is not None else None
    except (OSError, sqlite3.DatabaseError):
        return {"migration": "unknown", "status": "unavailable", "wal": "unknown"}

    return {
        "migration": "current" if current_revision == SCHEMA_HEAD else "outdated",
        "status": (
            "ok" if current_revision == SCHEMA_HEAD and journal_mode == "wal" else "degraded"
        ),
        "wal": "enabled" if journal_mode == "wal" else "disabled",
    }


def record_worker_heartbeat(
    database_path: Path,
    process_id: int,
    started_at: datetime,
    heartbeat_at: datetime,
) -> None:
    with _sqlite_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO service_heartbeat (service, process_id, started_at, heartbeat_at)
            VALUES ('worker', :process_id, :started_at, :heartbeat_at)
            ON CONFLICT(service) DO UPDATE SET
                process_id = excluded.process_id,
                started_at = excluded.started_at,
                heartbeat_at = excluded.heartbeat_at
            """,
            {
                "heartbeat_at": heartbeat_at.isoformat(),
                "process_id": process_id,
                "started_at": started_at.isoformat(),
            },
        )


def register_artifact(
    database_path: Path,
    content_hash: str,
    byte_count: int,
    media_type: str,
    source_reference: str,
    created_at: datetime,
) -> None:
    with _sqlite_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO artifact (content_hash, byte_count, media_type, created_at)
            VALUES (:content_hash, :byte_count, :media_type, :created_at)
            ON CONFLICT(content_hash) DO NOTHING
            """,
            {
                "byte_count": byte_count,
                "content_hash": content_hash,
                "created_at": created_at.isoformat(),
                "media_type": media_type,
            },
        )
        connection.execute(
            """
            INSERT INTO artifact_reference (content_hash, source_reference)
            VALUES (:content_hash, :source_reference)
            ON CONFLICT(content_hash, source_reference) DO NOTHING
            """,
            {"content_hash": content_hash, "source_reference": source_reference},
        )


def artifact_is_registered(
    database_path: Path,
    content_hash: str,
    source_reference: str,
) -> bool:
    try:
        with _sqlite_connection(database_path) as connection:
            registered = connection.execute(
                """
                SELECT 1
                FROM artifact AS artifact_record
                JOIN artifact_reference AS reference
                  ON reference.content_hash = artifact_record.content_hash
                WHERE artifact_record.content_hash = :content_hash
                  AND reference.source_reference = :source_reference
                """,
                {"content_hash": content_hash, "source_reference": source_reference},
            ).fetchone()
    except sqlite3.DatabaseError:
        return False
    return registered is not None and registered[0] == 1


def artifact_registry_available(database_path: Path) -> bool:
    if not database_path.is_file():
        return False
    try:
        with _sqlite_connection(database_path) as connection:
            connection.execute("SELECT 1 FROM artifact LIMIT 1")
            connection.execute("SELECT 1 FROM artifact_reference LIMIT 1")
    except sqlite3.DatabaseError:
        return False
    return True


def worker_status(database_path: Path, now: datetime | None = None) -> WorkerHealth:
    if not database_path.is_file():
        return {"status": "not_initialized"}
    try:
        with _sqlite_connection(database_path) as connection:
            heartbeat_value = connection.execute(
                "SELECT heartbeat_at FROM service_heartbeat WHERE service = 'worker'"
            ).fetchone()
    except sqlite3.DatabaseError:
        return {"status": "unavailable"}

    if heartbeat_value is None or not isinstance(heartbeat_value[0], str):
        return {"status": "stopped"}
    heartbeat_at = datetime.fromisoformat(heartbeat_value[0])
    observed_at = now or datetime.now(UTC)
    age_seconds = (observed_at - heartbeat_at).total_seconds()
    return {"status": "healthy" if age_seconds <= 5 else "stale"}


@contextmanager
def _sqlite_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=5)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        yield connection
        connection.commit()
    finally:
        connection.close()


def _alembic_configuration() -> Config:
    from alembic.config import Config

    configuration = Config()
    configuration.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    return configuration
