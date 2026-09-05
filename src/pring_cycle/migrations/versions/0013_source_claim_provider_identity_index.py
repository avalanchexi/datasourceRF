"""Index source-claim provider identity lookups used during source refresh.

Revision ID: 0013_source_claim_provider_identity_index
Revises: 0012_model_replay_exact_calendar
"""

from __future__ import annotations

from alembic import op

revision = "0013_source_claim_provider_identity_index"
down_revision = "0012_model_replay_exact_calendar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_source_claim_provider_identity",
        "source_claim",
        (
            "metric_id",
            "period_kind",
            "period_start",
            "period_end",
            "dimensions_json",
            "provider",
            "definition_version",
            "source_reference",
            "available_at",
        ),
    )


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
