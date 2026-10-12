from __future__ import annotations

import os
import sqlite3
import threading
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pring_cycle.health_types import DatabaseHealth, WorkerHealth

if TYPE_CHECKING:
    from alembic.config import Config

SCHEMA_HEAD = "0037_uncorrectable_day"


@contextmanager
def database_connection(database: Path | str, *, uri: bool = False) -> Iterator[sqlite3.Connection]:
    """Commit or roll back the operation, then close its connection or return it reset.

    Inside ``keep_database_open`` the thread's connections to that database are reused: a full
    run opened about 71 thousand, and each one's first statement parsed the whole schema again
    (ticket 24). A reused connection is handed out as a new one would be: no statement still
    reading, no transaction, default settings, and a file that is still the one at the path.
    """
    owner = os.getpid()
    pool = None if uri else _active_pool(database)
    pooled = pool.checkout(database) if pool is not None else None
    connection = pooled if pooled is not None else connect(database, uri=uri)
    try:
        try:
            yield connection
        except BaseException:
            if os.getpid() == owner:
                connection.rollback()
            raise
        if os.getpid() == owner:
            try:
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
    finally:
        if os.getpid() != owner:
            # A child forked inside the operation: the transaction and connection are the
            # parent's. Committing, rolling back or closing them here would act on its file.
            _INHERITED.append(connection)
        elif pool is not None and pooled is not None:
            pool.checkin(pooled)
        else:
            connection.close()


class _PooledConnection(sqlite3.Connection):
    """A connection that remembers its cursors and blobs, so returning it can finish them.

    A half-read SELECT or an open blob keeps its read transaction: reused as it is, the
    connection would go on reading the snapshot it started, not what others committed since.
    Statements started around these methods, through ``sqlite3.Cursor(connection)`` or the
    base class's own, are not seen; nothing here starts them that way.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.pool_generation = 0
        self._readers: weakref.WeakSet[Any] = weakref.WeakSet()

    def cursor(self, factory: Any = sqlite3.Cursor) -> Any:
        cursor = super().cursor(factory)
        self._readers.add(cursor)
        return cursor

    def blobopen(self, *args: Any, **kwargs: Any) -> sqlite3.Blob:
        blob = super().blobopen(*args, **kwargs)
        self._readers.add(blob)
        return blob

    def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
        cursor: sqlite3.Cursor = self.cursor()
        return cursor.execute(sql, parameters)

    def executemany(self, sql: str, parameters: Any, /) -> sqlite3.Cursor:
        cursor: sqlite3.Cursor = self.cursor()
        return cursor.executemany(sql, parameters)

    def executescript(self, script: str, /) -> sqlite3.Cursor:
        cursor: sqlite3.Cursor = self.cursor()
        return cursor.executescript(script)

    def reset(self) -> None:
        """Finish every read, end any transaction and restore what callers may have changed.

        As when the connection was closed, a cursor or blob kept past the operation is
        finished. Restored: transaction control, row and text factories, foreign keys; no
        caller sets functions, callbacks or other pragmas on these connections.
        """
        for reader in list(self._readers):
            reader.close()
        # Before the rollback: with autocommit off, a rollback opens the next transaction.
        self.autocommit = sqlite3.LEGACY_TRANSACTION_CONTROL
        if self.in_transaction:
            self.rollback()
        self.row_factory = None
        self.text_factory = str
        # The connect default; typeshed lists only the explicit modes.
        self.isolation_level = ""  # type: ignore[assignment]
        sqlite3.Connection.execute(self, "PRAGMA foreign_keys=OFF").close()


class _Pool:
    """One thread's idle connections to one kept database."""

    def __init__(self) -> None:
        self.owner = os.getpid()
        self.depth = 0
        self.closed = False
        self.generation = 0
        self.identity: tuple[int, int] | None = None
        self.idle: list[_PooledConnection] = []

    def checkout(self, database: Path | str) -> _PooledConnection:
        identity = _file_identity(database)
        if identity != self.identity:
            # Deleted or replaced: let go of the old file, and read the one at the path.
            self.close_idle()
            self.identity = identity
            self.generation += 1
        if self.idle:
            return self.idle.pop()
        connection = cast(_PooledConnection, connect(database, factory=_PooledConnection))
        connection.pool_generation = self.generation
        return connection

    def checkin(self, connection: _PooledConnection) -> None:
        if self.closed or connection.pool_generation != self.generation:
            connection.close()
            return
        try:
            connection.reset()
        except sqlite3.Error:
            # Closed by its caller, or broken: never handed out again.
            connection.close()
            return
        self.idle.append(connection)

    def close_idle(self) -> None:
        while self.idle:
            self.idle.pop().close()


# Each thread's pools by database, only while the thread keeps that database open. A child
# made by fork starts with none: the parent's connections stay the parent's (ticket 24).
_POOLS = threading.local()
_INHERITED: list[object] = []
_CONNECT = sqlite3.connect


def _forget_parent_connections() -> None:
    global _POOLS
    # Kept, never closed or used here: closing them in the child would touch the parent's.
    _INHERITED.append(_POOLS)
    _POOLS = threading.local()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_forget_parent_connections)


def _pool_key(database: Path | str) -> str | None:
    name = str(database)
    if not name or name == ":memory:" or name.startswith("file:"):
        return None
    return os.path.abspath(name)


def _active_pool(database: Path | str) -> _Pool | None:
    pools: dict[str, _Pool] | None = getattr(_POOLS, "pools", None)
    if not pools:
        return None
    if sqlite3.connect is not _CONNECT:
        # A replaced connect observes every connection opened (tests do): give it new ones.
        return None
    key = _pool_key(database)
    return pools.get(key) if key is not None else None


def _file_identity(database: Path | str) -> tuple[int, int] | None:
    try:
        stat = os.stat(database)
    except FileNotFoundError:
        return None
    return (stat.st_dev, stat.st_ino)


def connect(
    database: Path | str,
    *,
    uri: bool = False,
    factory: type[sqlite3.Connection] | None = None,
) -> sqlite3.Connection:
    """A new SQLite connection, syncing its WAL at checkpoints only, not on every commit.

    ``synchronous`` belongs to the connection, so every new one sets it (ADR-0038): under WAL
    the default, FULL, syncs on each commit, about 11 thousand times a full run (ticket 29).
    A power loss may undo the last commits, never corrupt the file.
    """
    # A factory only when asked for: tests that observe connections pass their own.
    connection = (
        sqlite3.connect(database, uri=uri)
        if factory is None
        else sqlite3.connect(database, uri=uri, factory=factory)
    )
    try:
        sqlite3.Connection.execute(connection, "PRAGMA synchronous=NORMAL").close()
    except BaseException:
        connection.close()
        raise
    return connection


# Databases this process has put in WAL mode. The mode is stored in the file, so setting it on
# every connection only repeats a statement; a full run opens tens of thousands of connections
# (run findings 2026-09-28, ticket 11).
_WAL_DATABASES: set[str] = set()


def ensure_wal(connection: sqlite3.Connection, database: Path | str) -> None:
    key = str(database)
    if key not in _WAL_DATABASES:
        connection.execute("PRAGMA journal_mode=WAL")
        _WAL_DATABASES.add(key)


@contextmanager
def keep_database_open(database: Path) -> Iterator[None]:
    """Defer last-connection WAL cleanup until concurrent work has stopped.

    Opening a Python connection alone does not open SQLite's pager. Read the
    journal mode and exhaust the cursor without starting a transaction; callers
    keep checking out their own connections for all reads and writes.

    Meanwhile this thread's checkouts of the database reuse pooled connections, all closed
    before this one, which stays the last to close (ticket 24). It also keeps a deleted
    database file open until the scope ends, as it always has.
    """
    key = _pool_key(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA journal_mode").fetchall()
        if key is None:
            yield
            return
        pools: dict[str, _Pool] | None = getattr(_POOLS, "pools", None)
        if pools is None:
            pools = _POOLS.pools = {}
        pool = pools.setdefault(key, _Pool())
        pool.depth += 1
        try:
            yield
        finally:
            pool.depth -= 1
            if pool.owner != os.getpid():
                # A child forked inside the scope: these connections are the parent's.
                _INHERITED.append(pool)
            elif pool.depth == 0:
                pool.closed = True
                pool.close_idle()
                del pools[key]


def migrate_database(database_path: Path) -> None:
    from alembic import command
    from sqlalchemy import create_engine, event

    configuration = _alembic_configuration()
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
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
    with database_connection(database_path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        yield connection


def _alembic_configuration() -> Config:
    from alembic.config import Config

    configuration = Config()
    configuration.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    return configuration
