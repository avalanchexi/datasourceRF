"""Keep what an AI WebSearch recheck made of media values that disagree (audit 06,
ADR-0039)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.media_recheck import MEDIA_RECHECK_SCHEMA

revision = "0035_media_conflict_recheck"
down_revision = "0034_publication_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(MEDIA_RECHECK_SCHEMA)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
