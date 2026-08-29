"""Add immutable evidence snapshots and ledger triggers."""

from __future__ import annotations

from alembic import op

revision = "0004_evidence_extensions"
down_revision = "0003_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_snapshot (
            evidence_snapshot_id TEXT PRIMARY KEY,
            as_of_mode TEXT NOT NULL,
            as_of_cutoff TEXT NOT NULL,
            observation_version_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    for name, table in (
        ("derived_observation", "derived_observation"),
        ("retrieval_attempt", "retrieval_attempt"),
        ("evidence_snapshot", "evidence_snapshot"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {name}_no_update
            BEFORE UPDATE ON {table} BEGIN
                SELECT RAISE(ABORT, '{name}_is_immutable');
            END
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS {name}_no_delete
            BEFORE DELETE ON {table} BEGIN
                SELECT RAISE(ABORT, '{name}_is_immutable');
            END
            """
        )


def downgrade() -> None:
    for name in ("evidence_snapshot", "retrieval_attempt", "derived_observation"):
        op.execute(f"DROP TRIGGER IF EXISTS {name}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS {name}_no_update")
    op.execute("DROP TABLE IF EXISTS evidence_snapshot")
