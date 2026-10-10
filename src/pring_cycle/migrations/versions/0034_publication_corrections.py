"""Mark publications computed on a value read for the wrong period, and their corrections
(audit 06); the projections kept now are marked at once."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.publication_corrections import (
    PUBLICATION_CORRECTION_SCHEMA,
    mark_affected_publications,
)

revision = "0034_publication_corrections"
down_revision = "0033_matched_quote_subject"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(PUBLICATION_CORRECTION_SCHEMA)
    mark_affected_publications(connection)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
