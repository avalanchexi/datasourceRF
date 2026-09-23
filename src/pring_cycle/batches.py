"""A processing batch is one run: every detail and summary row it writes names that run.

There is no batch table. ``parent_run`` already records the target business day and the
model version, and ``full_run_acquisition`` already ties each interface call to its run;
this adds the code version and each call's row count, and a plain-text ``batch_id`` on the
summary tables. It is not a foreign key, so retention can delete runs and summaries in
either order (ADR-0022). Batches are for tracing only and never reach a page or report.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import cache
from pathlib import Path

SUMMARY_TABLES = (
    "derived_observation",
    "projection_set",
    "analytical_dataset",
    "current_projection",
    "p0_assessment",
    "data_gap_notice",
    "report_snapshot",
)
_COLUMNS = (
    ("parent_run", "code_version", "TEXT"),
    ("acquisition_request", "row_count", "INTEGER"),
    ("acquisition_request", "structure_check", "TEXT"),
    ("acquisition_request", "rejection_reason", "TEXT"),
    *((table, "batch_id", "TEXT") for table in SUMMARY_TABLES),
)

_current_batch: ContextVar[str | None] = ContextVar("processing_batch", default=None)


@contextmanager
def processing_batch(run_id: str) -> Iterator[None]:
    """Attribute every summary row written inside this block to ``run_id``."""
    token = _current_batch.set(run_id)
    try:
        yield
    finally:
        _current_batch.reset(token)


def current_batch_id() -> str | None:
    return _current_batch.get()


def add_batch_columns(connection: sqlite3.Connection) -> None:
    """Add the batch columns to whichever of their tables exist; safe to repeat."""
    for table, column, kind in _COLUMNS:
        existing = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        if existing and column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


@cache
def code_version() -> str:
    """A content hash of the running package's own source."""
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def row_count(normalized: object) -> int:
    """How many rows an interface call returned, read from its normalized value."""
    if normalized is None:
        return 0
    if isinstance(normalized, (list, tuple)):
        return len(normalized)
    if isinstance(normalized, dict):
        for key in ("items", "rows", "observations", "records"):
            if isinstance(normalized.get(key), (list, tuple)):
                return len(normalized[key])
        if isinstance(normalized.get("data"), (dict, list, tuple)):
            return row_count(normalized["data"])
    return 1
