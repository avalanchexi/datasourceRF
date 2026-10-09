"""Ticket 24: a Worker run reuses its thread's SQLite connections instead of reopening them.

A full run opened about 71 thousand connections, and each one's first statement parsed the
whole schema again (about 0.5 ms). Inside ``keep_database_open`` a thread's checkouts of that
database now come from a small pool; every checkout must still look like a new connection.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from pring_cycle.storage import database_connection, keep_database_open


def make_database(path: Path, rows: int = 3) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY, parent INTEGER)")
        connection.executemany("INSERT INTO item (id) VALUES (?)", [(i,) for i in range(rows)])
    connection.close()
    return path


def open_files(path: Path) -> list[str]:
    """What this process's descriptors point at for ``path``, deleted copies included."""
    targets = []
    for descriptor in os.listdir("/proc/self/fd"):
        try:
            target = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError:
            continue
        if target.startswith(str(path)) and not target.startswith(f"{path}-"):
            targets.append(target)
    return targets


def count(database: Path) -> int:
    with database_connection(database) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM item").fetchone()[0])


def test_outside_a_kept_database_every_checkout_is_a_new_connection(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with database_connection(database) as first:
        pass
    with database_connection(database) as second:
        pass

    assert first is not second
    with pytest.raises(sqlite3.ProgrammingError):
        first.execute("SELECT 1")


def test_a_kept_database_hands_the_thread_the_same_connection_again(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as first:
            first.execute("SELECT 1").fetchall()
        with database_connection(str(database)) as second:
            second.execute("SELECT 1").fetchall()

    assert first is second


def test_settings_a_caller_changed_are_reset_before_the_next_checkout(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as changed:
            changed.row_factory = sqlite3.Row
            changed.text_factory = bytes
            changed.isolation_level = None
            changed.execute("PRAGMA foreign_keys=ON")
        with database_connection(database) as connection:
            assert connection is changed
            assert connection.row_factory is None
            assert connection.text_factory is str
            assert connection.isolation_level == ""  # type: ignore[comparison-overlap]
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (0,)


def test_an_unfinished_cursor_does_not_pin_the_next_checkout_to_an_old_snapshot(
    tmp_path: Path,
) -> None:
    """A half-read SELECT keeps its read transaction; reused as is, the connection would not
    see what other connections committed since."""
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as connection:
            unfinished = connection.execute("SELECT id FROM item ORDER BY id")
            assert unfinished.fetchone() == (0,)
        writer = sqlite3.connect(database)
        with writer:
            writer.execute("INSERT INTO item (id) VALUES (100)")
        writer.close()

        assert count(database) == 4
        # As when the connection was closed: the cursor is finished, not resumed later.
        with pytest.raises(sqlite3.ProgrammingError):
            unfinished.fetchone()


def test_a_failed_operation_is_rolled_back_and_leaves_no_transaction(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with pytest.raises(RuntimeError), database_connection(database) as connection:
            connection.execute("INSERT INTO item (id) VALUES (100)")
            raise RuntimeError("stop")
        with database_connection(database) as connection:
            assert not connection.in_transaction
            assert connection.execute("SELECT COUNT(*) FROM item").fetchone() == (3,)


def test_a_nested_checkout_never_shares_the_outer_connection(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with pytest.raises(RuntimeError), database_connection(database) as outer:
            outer.row_factory = sqlite3.Row
            outer.execute("INSERT INTO item (id) VALUES (100)")
            with database_connection(database) as inner:
                assert inner is not outer
                # Not the outer transaction: its uncommitted row is not visible here.
                assert inner.execute("SELECT COUNT(*) FROM item").fetchone() == (3,)
            # The inner checkout's return reset its own connection, not this one.
            assert outer.row_factory is sqlite3.Row
            assert outer.in_transaction
            raise RuntimeError("roll the outer back")
        assert count(database) == 3


def test_leaving_the_kept_database_closes_every_connection_it_pooled(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as outer, database_connection(database) as inner:
            outer.execute("SELECT 1").fetchall()
            inner.execute("SELECT 1").fetchall()
        assert open_files(database)

    assert open_files(database) == []
    # The last connection's close checkpointed and removed the write-ahead log.
    assert not Path(f"{database}-wal").exists()
    with pytest.raises(sqlite3.ProgrammingError):
        outer.execute("SELECT 1")


def test_a_deleted_database_is_let_go_and_its_replacement_is_read(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as outer, database_connection(database) as inner:
            outer.execute("SELECT 1").fetchall()
            inner.execute("SELECT 1").fetchall()
        for suffix in ("", "-wal", "-shm"):
            Path(f"{database}{suffix}").unlink(missing_ok=True)
        make_database(database, rows=7)

        # Not the pooled connections to the deleted file: the file now at that path.
        assert count(database) == 7
    # While the keeping connection holds the old inode SQLite itself defers closing the
    # descriptors of that inode, closed or not; once it is gone nothing holds either file.
    assert open_files(database) == []


def test_a_process_that_exits_inside_a_kept_database_closes_its_connections(
    tmp_path: Path,
) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")
    script = (
        "import sys\n"
        "from pring_cycle.storage import database_connection, keep_database_open\n"
        f"database = {str(database)!r}\n"
        "with keep_database_open(database):\n"
        "    with database_connection(database) as connection:\n"
        "        connection.execute('INSERT INTO item (id) VALUES (100)')\n"
        "    sys.exit(0)\n"
    )

    finished = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )

    assert finished.returncode == 0, finished.stderr
    assert not Path(f"{database}-wal").exists()
    assert count(database) == 4


def test_a_child_process_inherits_none_of_the_pooled_connections(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")
    listing = (
        "import os\n"
        "print('\\n'.join(os.readlink(f'/proc/self/fd/{d}') for d in os.listdir('/proc/self/fd')"
        " if os.path.exists(f'/proc/self/fd/{d}')))\n"
    )

    with keep_database_open(database):
        with database_connection(database) as connection:
            connection.execute("SELECT 1").fetchall()
        child = subprocess.run(
            [sys.executable, "-c", listing], capture_output=True, text=True, check=True
        )

    assert str(database) not in child.stdout


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork is POSIX only")
def test_a_forked_child_opens_its_own_connections(tmp_path: Path) -> None:
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(database) as parent:
            parent.execute("SELECT 1").fetchall()
        pid = os.fork()
        if pid == 0:  # pragma: no cover - the child reports through its exit status
            status = 1
            try:
                with database_connection(database) as child:
                    if child is not parent:
                        child.execute("INSERT INTO item (id) VALUES (100)")
                        status = 0
            finally:
                os._exit(status)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        with database_connection(database) as again:
            assert again is parent
            assert again.execute("SELECT COUNT(*) FROM item").fetchone() == (4,)


def test_memory_and_uri_databases_are_never_pooled(tmp_path: Path) -> None:
    """Every :memory: connection is its own database; sharing one would share its tables."""
    database = make_database(tmp_path / "runtime.sqlite3")

    with keep_database_open(database):
        with database_connection(":memory:") as first:
            first.execute("CREATE TABLE scratch (x)")
        with database_connection(":memory:") as second:
            assert second is not first
            assert second.execute("SELECT COUNT(*) FROM sqlite_master").fetchone() == (0,)
        read_only = f"{database.as_uri()}?mode=ro"
        with database_connection(read_only, uri=True) as first_uri:
            pass
        with database_connection(read_only, uri=True) as second_uri:
            assert second_uri is not first_uri
