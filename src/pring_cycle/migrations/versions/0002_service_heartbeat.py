"""Add the operational Worker heartbeat."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_service_heartbeat"
down_revision = "0001_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_heartbeat",
        sa.Column("service", sa.String(length=32), primary_key=True),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("heartbeat_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_heartbeat")
