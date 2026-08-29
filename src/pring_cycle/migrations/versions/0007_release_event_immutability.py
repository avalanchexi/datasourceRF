"""Make official release events an immutable evidence ledger."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.evidence import _RELEASE_EVENT_EXTENSIONS_SCHEMA

revision = "0007_release_event_immutability"
down_revision = "0006_p0_assessment_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    driver_connection = cast(Any, op.get_bind().connection).driver_connection
    driver_connection.executescript(_RELEASE_EVENT_EXTENSIONS_SCHEMA)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS release_event_no_delete")
    op.execute("DROP TRIGGER IF EXISTS release_event_no_update")
