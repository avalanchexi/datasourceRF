"""Record context output differences in model replay results."""

from __future__ import annotations

from alembic import op

revision = "0009_model_replay_context"
down_revision = "0008_retrieval_run_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE model_replay "
        "ADD COLUMN context_output_differences INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE model_replay DROP COLUMN context_output_differences")
