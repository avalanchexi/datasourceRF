"""Bind runtime catalog identities to reviewed model admission."""

from __future__ import annotations

from alembic import op

from pring_cycle.catalog_registry import CATALOG_REGISTRY_SCHEMA

revision = "0019_registered_metric_catalog"
down_revision = "0018_full_run_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(CATALOG_REGISTRY_SCHEMA)


def downgrade() -> None:
    op.execute("DROP TABLE registered_metric_catalog")
