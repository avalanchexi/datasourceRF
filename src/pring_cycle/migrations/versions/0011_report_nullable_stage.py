"""Allow reports for valid noncanonical core-state combinations."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.reports import upgrade_report_snapshot_nullable_stage

revision = "0011_report_nullable_stage"
down_revision = "0010_context_replay_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    upgrade_report_snapshot_nullable_stage(connection)


def downgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    row = connection.execute(
        "SELECT COUNT(*) FROM report_snapshot WHERE current_stage IS NULL"
    ).fetchone()
    if row is not None and int(row[0]) > 0:
        raise RuntimeError("report_nullable_stage_downgrade_blocked")
    _rebuild_report_snapshot_stage_not_null(connection)


def _rebuild_report_snapshot_stage_not_null(connection: Any) -> None:
    from pring_cycle.reports import rebuild_report_snapshot_stage_column

    rebuild_report_snapshot_stage_column(connection, nullable=False)
