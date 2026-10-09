"""Keep with each matched quote the subject clause its figure was read under (lookback 22)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.news_rules import add_subject_column

revision = "0033_matched_quote_subject"
down_revision = "0032_receipt_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_subject_column(cast(Any, op.get_bind().connection).driver_connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
