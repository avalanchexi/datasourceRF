"""Record exact trading-calendar evidence for model replay activation.

Revision ID: 0012_model_replay_exact_calendar
Revises: 0011_report_nullable_stage
"""

from __future__ import annotations

from alembic import op

revision = "0012_model_replay_exact_calendar"
down_revision = "0011_report_nullable_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE model_replay "
        "ADD COLUMN evaluated_trading_days INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE model_replay ADD COLUMN calendar_hash TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
