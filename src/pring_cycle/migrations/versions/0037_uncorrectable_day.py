"""Record the window days whose summary cannot be corrected on a core history basis, so no
later run on it tries them again (ticket 08)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.projections import UNCORRECTABLE_DAY_SCHEMA

revision = "0037_uncorrectable_day"
down_revision = "0036_scheduled_run_t_plus_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(UNCORRECTABLE_DAY_SCHEMA)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
