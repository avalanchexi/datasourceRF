"""Add scoped retrieval runs, attempt audit, and negative cache."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.runs import _RETRIEVAL_RUN_SCHEMA

revision = "0008_retrieval_run_ledger"
down_revision = "0007_release_event_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    driver_connection = cast(Any, op.get_bind().connection).driver_connection
    driver_connection.executescript(_RETRIEVAL_RUN_SCHEMA)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS run_retrieval_attempt_no_delete")
    op.execute("DROP TRIGGER IF EXISTS run_retrieval_attempt_no_update")
    op.execute("DROP TRIGGER IF EXISTS run_retrieval_scope_no_delete")
    op.execute("DROP TRIGGER IF EXISTS run_retrieval_scope_no_update")
    op.execute("DROP TABLE IF EXISTS retrieval_negative_cache")
    op.execute("DROP TABLE IF EXISTS run_retrieval_attempt")
    op.execute("DROP TABLE IF EXISTS run_retrieval_scope")
