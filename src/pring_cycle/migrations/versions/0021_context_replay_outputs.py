"""Reference immutable context output snapshots from model replays."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0021_context_replay_outputs"
down_revision = "0020_model_evaluation_outputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "model_replay" not in inspector.get_table_names():
        return  # dropped by 0025_drop_model_lifecycle
    columns = {column["name"] for column in inspector.get_columns("model_replay")}
    if "context_output_hash" not in columns:
        op.execute("ALTER TABLE model_replay ADD COLUMN context_output_hash TEXT")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
