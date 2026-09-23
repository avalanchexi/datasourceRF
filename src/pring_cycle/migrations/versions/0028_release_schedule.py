"""Record each batch's release pre-announcements (ticket 25)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.release_schedule import RELEASE_SCHEDULE_SCHEMA

revision = "0028_release_schedule"
down_revision = "0027_candidate_validation_record"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(RELEASE_SCHEDULE_SCHEMA)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
