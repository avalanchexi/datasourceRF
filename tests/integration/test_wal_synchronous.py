"""ADR-0038: every connection to a runtime or test database commits with ``synchronous=NORMAL``.

Under WAL the default, FULL, syncs the log on every commit: a full run made about 11 thousand
fsyncs for 71 thousand commits (ticket 29). ``synchronous`` belongs to the connection, not
the file, so each new connection sets it, the pooled and forked ones included.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.freshness import batch_freshness
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection, database_health, keep_database_open

NORMAL = 1


def synchronous(connection: sqlite3.Connection) -> int:
    return int(sqlite3.Connection.execute(connection, "PRAGMA synchronous").fetchone()[0])


def make_database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY)")
    connection.close()
    return path


def test_a_new_connection_commits_with_normal_sync(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with database_connection(database) as connection:
        assert synchronous(connection) == NORMAL
    with database_connection(f"{database.as_uri()}?mode=ro", uri=True) as read_only:
        assert synchronous(read_only) == NORMAL


def test_every_connection_a_kept_database_pools_commits_with_normal_sync(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as outer, database_connection(database) as nested:
            assert outer is not nested
            assert (synchronous(outer), synchronous(nested)) == (NORMAL, NORMAL)
        with database_connection(database) as reused:
            assert reused in (outer, nested)
            assert synchronous(reused) == NORMAL


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is POSIX only")
def test_a_forked_child_opens_its_connections_with_normal_sync(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as parent:
            parent.execute("SELECT 1").fetchall()
        pid = os.fork()
        if pid == 0:  # pragma: no cover - the child reports through its exit status
            status = 1
            try:
                with database_connection(database) as child:
                    if child is not parent and synchronous(child) == NORMAL:
                        status = 0
            finally:
                os._exit(status)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0


class _Observed(sqlite3.Connection):
    """A connection that notes its ``synchronous`` as it is closed."""

    seen: list[int] = []

    def close(self) -> None:
        with contextlib.suppress(sqlite3.ProgrammingError):
            self.seen.append(synchronous(self))
        super().close()


def test_migration_health_and_direct_reads_open_with_normal_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The migration's own engine and the reads that open their own connection set it too."""
    original = sqlite3.connect
    seen: list[int] = []
    monkeypatch.setattr(_Observed, "seen", seen)

    def observed(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        if kwargs.get("factory", sqlite3.Connection) is sqlite3.Connection:
            kwargs["factory"] = _Observed
        connection: sqlite3.Connection = original(*args, **kwargs)
        return connection

    # SQLAlchemy connects through ``sqlite3.dbapi2``.
    monkeypatch.setattr(sqlite3, "connect", observed)
    monkeypatch.setattr(sqlite3.dbapi2, "connect", observed)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    for step in (
        lambda: initialize_runtime(paths),
        lambda: database_health(paths.database),
        lambda: batch_freshness(paths.database, "run-none"),
    ):
        observed_before = len(seen)
        step()
        assert len(seen) > observed_before

    assert set(seen) == {NORMAL}
