"""Index point-in-time context replay lookups."""

from __future__ import annotations

from alembic import op

revision = "0010_context_replay_indexes"
down_revision = "0009_model_replay_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_source_claim_metric_definition_public",
        "source_claim",
        ("metric_id", "definition_version", "public_available_at", "period_end"),
    )
    op.create_index(
        "ix_source_claim_metric_definition_system",
        "source_claim",
        ("metric_id", "definition_version", "available_at", "period_end"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_claim_metric_definition_system",
        table_name="source_claim",
    )
    op.drop_index(
        "ix_source_claim_metric_definition_public",
        table_name="source_claim",
    )
