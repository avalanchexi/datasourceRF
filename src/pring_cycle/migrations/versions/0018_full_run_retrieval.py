"""Persist full-run acquisition windows and immutable evaluation cutoffs."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.run_cutoffs import upgrade_run_cutoffs

revision = "0018_full_run_retrieval"
down_revision = "0017_report_process_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    upgrade_run_cutoffs(connection)


def downgrade() -> None:
    op.execute("DROP TABLE full_run_acquisition")
    op.execute("DROP TABLE full_run_gap_plan")
    op.execute("DROP TABLE run_cutoff_freeze")
    op.execute("DROP TABLE run_cutoff_contract")
