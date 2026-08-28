from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError

from pring_cycle.health_types import DatabaseHealth, WorkerHealth


def migrate_database(database_path: Path) -> None:
    engine = _database_engine(database_path)
    configuration = _alembic_configuration()
    try:
        with engine.connect() as connection:
            configuration.attributes["connection"] = connection
            command.upgrade(configuration, "head")
    finally:
        engine.dispose()


def database_health(database_path: Path) -> DatabaseHealth:
    if not database_path.is_file():
        return {"migration": "missing", "status": "missing", "wal": "missing"}

    engine = _database_engine(database_path)
    try:
        with engine.connect() as connection:
            journal_mode = str(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one())
            current_revision = MigrationContext.configure(connection).get_current_revision()
        target_revision = ScriptDirectory.from_config(_alembic_configuration()).get_current_head()
    except (OSError, SQLAlchemyError, sqlite3.DatabaseError):
        return {"migration": "unknown", "status": "unavailable", "wal": "unknown"}
    finally:
        engine.dispose()

    return {
        "migration": "current" if current_revision == target_revision else "outdated",
        "status": (
            "ok" if current_revision == target_revision and journal_mode == "wal" else "degraded"
        ),
        "wal": "enabled" if journal_mode == "wal" else "disabled",
    }


def record_worker_heartbeat(
    database_path: Path,
    process_id: int,
    started_at: datetime,
    heartbeat_at: datetime,
) -> None:
    engine = _database_engine(database_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO service_heartbeat (service, process_id, started_at, heartbeat_at)
                    VALUES ('worker', :process_id, :started_at, :heartbeat_at)
                    ON CONFLICT(service) DO UPDATE SET
                        process_id = excluded.process_id,
                        started_at = excluded.started_at,
                        heartbeat_at = excluded.heartbeat_at
                    """
                ),
                {
                    "heartbeat_at": heartbeat_at.isoformat(),
                    "process_id": process_id,
                    "started_at": started_at.isoformat(),
                },
            )
    finally:
        engine.dispose()


def register_artifact(
    database_path: Path,
    content_hash: str,
    byte_count: int,
    media_type: str,
    source_reference: str,
    created_at: datetime,
) -> None:
    engine = _database_engine(database_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO artifact (content_hash, byte_count, media_type, created_at)
                    VALUES (:content_hash, :byte_count, :media_type, :created_at)
                    ON CONFLICT(content_hash) DO NOTHING
                    """
                ),
                {
                    "byte_count": byte_count,
                    "content_hash": content_hash,
                    "created_at": created_at.isoformat(),
                    "media_type": media_type,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO artifact_reference (content_hash, source_reference)
                    VALUES (:content_hash, :source_reference)
                    ON CONFLICT(content_hash, source_reference) DO NOTHING
                    """
                ),
                {"content_hash": content_hash, "source_reference": source_reference},
            )
    finally:
        engine.dispose()


def artifact_is_registered(
    database_path: Path,
    content_hash: str,
    source_reference: str,
) -> bool:
    engine = _database_engine(database_path)
    try:
        with engine.connect() as connection:
            registered = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM artifact AS artifact_record
                    JOIN artifact_reference AS reference
                      ON reference.content_hash = artifact_record.content_hash
                    WHERE artifact_record.content_hash = :content_hash
                      AND reference.source_reference = :source_reference
                    """
                ),
                {"content_hash": content_hash, "source_reference": source_reference},
            ).scalar_one_or_none()
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()
    return registered == 1


def artifact_registry_available(database_path: Path) -> bool:
    if not database_path.is_file():
        return False
    engine = _database_engine(database_path)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM artifact LIMIT 1"))
            connection.execute(text("SELECT 1 FROM artifact_reference LIMIT 1"))
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()
    return True


def worker_status(database_path: Path, now: datetime | None = None) -> WorkerHealth:
    if not database_path.is_file():
        return {"status": "not_initialized"}
    engine = _database_engine(database_path)
    try:
        with engine.connect() as connection:
            heartbeat_value = connection.execute(
                text("SELECT heartbeat_at FROM service_heartbeat WHERE service = 'worker'")
            ).scalar_one_or_none()
    except SQLAlchemyError:
        return {"status": "unavailable"}
    finally:
        engine.dispose()

    if not isinstance(heartbeat_value, str):
        return {"status": "stopped"}
    heartbeat_at = datetime.fromisoformat(heartbeat_value)
    observed_at = now or datetime.now(UTC)
    age_seconds = (observed_at - heartbeat_at).total_seconds()
    return {"status": "healthy" if age_seconds <= 5 else "stale"}


def _database_engine(database_path: Path) -> Engine:
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def _alembic_configuration() -> Config:
    configuration = Config()
    configuration.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    return configuration
