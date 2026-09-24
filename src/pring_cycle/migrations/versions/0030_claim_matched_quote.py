"""Keep the matched quote of each value taken by a news rule (phase two #07)."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.news_rules import MATCHED_QUOTE_SCHEMA

revision = "0030_claim_matched_quote"
down_revision = "0029_search_query_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    connection.executescript(MATCHED_QUOTE_SCHEMA)


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
