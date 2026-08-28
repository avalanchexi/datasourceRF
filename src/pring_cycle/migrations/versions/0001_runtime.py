"""Establish the local runtime schema revision."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_runtime"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact",
        sa.Column("content_hash", sa.String(length=64), primary_key=True),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "artifact_reference",
        sa.Column(
            "content_hash",
            sa.String(length=64),
            sa.ForeignKey("artifact.content_hash"),
            nullable=False,
        ),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("content_hash", "source_reference"),
    )
    op.create_table(
        "service_heartbeat",
        sa.Column("service", sa.String(length=32), primary_key=True),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("heartbeat_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("service_heartbeat")
    op.drop_table("artifact_reference")
    op.drop_table("artifact")
