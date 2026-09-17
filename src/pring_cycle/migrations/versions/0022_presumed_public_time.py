"""Record how each claim's public time was determined, observed or presumed."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0022_presumed_public_time"
down_revision = "0021_context_replay_outputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("source_claim")}
    if "public_time_basis" not in columns:
        # Every claim already stored carries a time the source actually published, so the
        # default states what was already true rather than relabelling anything.
        op.execute(
            "ALTER TABLE source_claim ADD COLUMN public_time_basis TEXT "
            "NOT NULL DEFAULT 'observed_release'"
        )


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
