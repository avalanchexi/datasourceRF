"""Count the retrieval attempt rows SQLite hands back, through every connection opened."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import pytest


class AttemptRowCounter:
    """Rows of ``run_retrieval_attempt`` read so far, whatever statement read them.

    ``install`` makes every ``sqlite3.connect`` hand out connections whose cursors count
    the rows they return when their statement reads that table.
    """

    def __init__(self) -> None:
        self.rows = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sqlite3, "connect", self._connect(sqlite3.connect))

    def _connect(self, real: Callable[..., sqlite3.Connection]) -> Callable[..., Any]:
        counter = self

        class Cursor(sqlite3.Cursor):
            reads_attempts = False

            def execute(self, sql: str, parameters: Any = (), /) -> Cursor:
                self.reads_attempts = "run_retrieval_attempt" in sql.lower()
                return super().execute(sql, parameters)

            def _count(self, rows: list[Any]) -> list[Any]:
                if self.reads_attempts:
                    counter.rows += len(rows)
                return rows

            def __next__(self) -> Any:
                return self._count([super().__next__()])[0]

            def fetchone(self) -> Any:
                row = super().fetchone()
                return row if row is None else self._count([row])[0]

            def fetchmany(self, size: int | None = None) -> list[Any]:
                rows = super().fetchmany() if size is None else super().fetchmany(size)
                return self._count(rows)

            def fetchall(self) -> list[Any]:
                return self._count(super().fetchall())

        class Connection(sqlite3.Connection):
            def cursor(self, factory: Any = Cursor) -> Any:
                return super().cursor(factory)

            def execute(self, sql: str, parameters: Any = (), /) -> sqlite3.Cursor:
                cursor: sqlite3.Cursor = self.cursor()
                return cursor.execute(sql, parameters)

        return lambda *args, **kwargs: real(*args, factory=Connection, **kwargs)
