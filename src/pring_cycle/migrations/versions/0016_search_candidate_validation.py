"""Link discovered candidates to downloaded sources and selected model evidence."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.search_evidence import SEARCH_VERIFICATION_SCHEMA

revision = "0016_search_candidate_validation"
down_revision = "0015_retrieval_physical_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(SEARCH_VERIFICATION_SCHEMA)


def downgrade() -> None:
    op.execute("DROP TABLE retrieval_candidate_validation")
