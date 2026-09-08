"""Preserve structured calibration and replay outputs with immutable references."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0020_model_evaluation_outputs"
down_revision = "0019_registered_metric_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE IF NOT EXISTS model_evaluation_output (
            output_hash TEXT PRIMARY KEY,
            document_json TEXT NOT NULL
        )"""
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"""CREATE TRIGGER IF NOT EXISTS model_evaluation_output_no_{operation.lower()}
            BEFORE {operation} ON model_evaluation_output BEGIN
                SELECT RAISE(ABORT, 'model_evaluation_output_is_immutable');
            END"""
        )
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("model_replay")}
    for name, kind in (
        ("candidate_state_differences", "INTEGER"),
        ("candidate_days_differences", "INTEGER"),
        ("core_output_hash", "TEXT"),
    ):
        if name not in columns:
            op.execute(f"ALTER TABLE model_replay ADD COLUMN {name} {kind}")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
