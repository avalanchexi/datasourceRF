"""Add persistent run step history."""

from __future__ import annotations

from alembic import op

revision = "0005_run_step_events"
down_revision = "0004_evidence_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS run_step_event (
            step_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES parent_run(run_id),
            step TEXT NOT NULL,
            event TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_table("run_step_event")
