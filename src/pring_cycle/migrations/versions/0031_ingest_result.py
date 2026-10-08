"""Keep on each validated call whether its values entered the evidence store (gap sources #03)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.acquisition import add_receipt_columns

revision = "0031_ingest_result"
down_revision = "0030_claim_matched_quote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_receipt_columns(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
