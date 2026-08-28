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


def migrate_database(database_path: Path) -> None:
    engine = _database_engine(database_path)
    configuration = _alembic_configuration()
    with engine.connect() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "head")
    engine.dispose()


def database_health(database_path: Path) -> dict[str, str]:
    if not database_path.is_file():
        return {"migration": "missing", "status": "missing", "wal": "missing"}

    try:
        engine = _database_engine(database_path)
        with engine.connect() as connection:
            journal_mode = str(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one())
            current_revision = MigrationContext.configure(connection).get_current_revision()
        target_revision = ScriptDirectory.from_config(_alembic_configuration()).get_current_head()
        engine.dispose()
    except (OSError, sqlite3.DatabaseError):
        return {"migration": "unknown", "status": "unavailable", "wal": "unknown"}

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
    engine.dispose()


def worker_status(database_path: Path, now: datetime | None = None) -> dict[str, str]:
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
