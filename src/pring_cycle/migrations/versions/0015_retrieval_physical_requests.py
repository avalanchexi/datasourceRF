"""Record retrieval gaps and requests before external calls."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.retrieval_ledger import RETRIEVAL_LEDGER_SCHEMA

revision = "0015_retrieval_physical_requests"
down_revision = "0014_acquisition_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    if "physical_request_id" not in {
        row[1] for row in connection.execute("PRAGMA table_info(run_retrieval_attempt)")
    }:
        connection.execute("ALTER TABLE run_retrieval_attempt ADD COLUMN physical_request_id TEXT")
    connection.executescript(RETRIEVAL_LEDGER_SCHEMA)


def downgrade() -> None:
    op.execute("ALTER TABLE run_retrieval_attempt DROP COLUMN physical_request_id")
    op.execute("DROP TABLE retrieval_query")
    op.execute("DROP TABLE retrieval_request_event")
    op.execute("DROP TABLE retrieval_request_gap")
    op.execute("DROP TABLE retrieval_physical_request")
    op.execute("DROP TABLE retrieval_run_gap")
    op.execute("DROP TABLE retrieval_gap")
