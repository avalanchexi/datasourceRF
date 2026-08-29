"""Add the immutable direct-cutover record."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_cutover"
down_revision = "0002_v1_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_cutover",
        sa.Column("singleton", sa.Integer(), primary_key=True),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("supported_path", sa.String(length=32), nullable=False),
        sa.Column("legacy_system_state", sa.String(length=32), nullable=False),
        sa.CheckConstraint("singleton = 1"),
    )
    op.execute(
        """
        CREATE TRIGGER system_cutover_no_update
        BEFORE UPDATE ON system_cutover BEGIN
            SELECT RAISE(ABORT, 'system_cutover_is_immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER system_cutover_no_delete
        BEFORE DELETE ON system_cutover BEGIN
            SELECT RAISE(ABORT, 'system_cutover_is_immutable');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS system_cutover_no_delete")
    op.execute("DROP TRIGGER IF EXISTS system_cutover_no_update")
    op.drop_table("system_cutover")
