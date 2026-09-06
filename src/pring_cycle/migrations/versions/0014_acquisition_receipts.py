"""Retain request originals and immutable claim acquisition links."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.acquisition import ACQUISITION_SCHEMA

revision = "0014_acquisition_receipts"
down_revision = "0013_source_claim_provider_identity_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(ACQUISITION_SCHEMA)


def downgrade() -> None:
    op.execute("DROP TABLE source_claim_acquisition")
    op.execute("DROP TABLE acquisition_request")
