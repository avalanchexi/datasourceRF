"""Keep on each call the records its source returned, the scalars they were read as and the
claims those entered the evidence store as (lookback 06)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.acquisition import add_receipt_columns

revision = "0032_receipt_counts"
down_revision = "0031_ingest_result"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_receipt_columns(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
