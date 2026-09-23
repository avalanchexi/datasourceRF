"""Store each claim's public time inferred from its registered cadence (ADR-0021)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.evidence import add_inferred_public_time

revision = "0024_inferred_public_time"
down_revision = "0023_batch_freshness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_inferred_public_time(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
