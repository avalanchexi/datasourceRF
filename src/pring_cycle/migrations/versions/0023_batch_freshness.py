"""Record each batch's per-metric freshness against its registered source cadence."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.freshness import BATCH_FRESHNESS_SCHEMA

revision = "0023_batch_freshness"
down_revision = "0022_processing_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cast(Any, op.get_bind().connection).driver_connection.executescript(BATCH_FRESHNESS_SCHEMA)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
