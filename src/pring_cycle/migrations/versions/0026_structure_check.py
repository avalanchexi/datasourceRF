"""Record each call's structure check and, when it rejects the response, why (gate ③)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.batches import add_batch_columns

revision = "0026_structure_check"
down_revision = "0025_drop_model_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_batch_columns(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
