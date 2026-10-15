"""Keep immutable per-attempt cockpit summaries alongside their owning run."""

from alembic import op

revision = "0039_run_health"
down_revision = "0038_scheduled_run_at_0930"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE IF NOT EXISTS acquisition_dispatch (
        acquisition_id TEXT PRIMARY KEY
            REFERENCES acquisition_request(acquisition_id) ON DELETE CASCADE,
        dispatched_at TEXT NOT NULL
    )""")
    op.execute("""CREATE TABLE IF NOT EXISTS run_health_summary (
        run_id TEXT NOT NULL, attempt INTEGER NOT NULL, status TEXT NOT NULL,
        document_json TEXT NOT NULL, PRIMARY KEY (run_id, attempt, status)
    )""")
    op.execute("""CREATE TRIGGER IF NOT EXISTS run_health_summary_no_update
        BEFORE UPDATE ON run_health_summary
        BEGIN SELECT RAISE(ABORT, 'run_health_summary_is_immutable'); END""")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
