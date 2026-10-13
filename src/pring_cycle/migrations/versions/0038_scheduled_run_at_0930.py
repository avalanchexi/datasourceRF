"""Move the scheduled run to 9:30, once the session before's margin totals are out at 9:05
(ADR-0041, 2026-10-13).

A schedule whose latest version starts at another time is given a new version starting at
9:30, switched on or off as it was, its time zone kept; its earlier versions are kept. A new
database has no version yet: the runtime's bootstrap writes its first. A database without
the table has nothing to move.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from alembic import op

revision = "0038_scheduled_run_at_0930"
down_revision = "0037_uncorrectable_day"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedule_configuration'"
    ).fetchone():
        return
    latest = connection.execute(
        "SELECT version, enabled, timezone, start_time FROM schedule_configuration "
        "ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if latest is None or latest[3] == "09:30":
        return
    version, enabled, timezone, _start_time = latest
    connection.execute(
        "INSERT INTO schedule_configuration(version, enabled, timezone, start_time, "
        "p0_deadline, requested_by, created_at) VALUES (?, ?, ?, '09:30', '21:00', ?, ?)",
        (
            version + 1,
            enabled,
            timezone,
            "migration-0038-scheduled-run-at-0930",
            datetime.now(UTC).isoformat(),
        ),
    )


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
