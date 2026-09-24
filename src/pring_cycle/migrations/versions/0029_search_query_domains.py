"""Record the domains each search was limited to (phase two #06)."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0029_search_query_domains"
down_revision = "0028_release_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("retrieval_query")}
    if "domains_json" not in columns:
        op.execute("ALTER TABLE retrieval_query ADD COLUMN domains_json TEXT NOT NULL DEFAULT '[]'")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
