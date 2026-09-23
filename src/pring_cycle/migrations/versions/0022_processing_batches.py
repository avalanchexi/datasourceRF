"""Record each run as a processing batch: code version, call row counts, summary batch ids."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.batches import add_batch_columns

revision = "0022_processing_batches"
down_revision = "0021_context_replay_outputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_batch_columns(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
