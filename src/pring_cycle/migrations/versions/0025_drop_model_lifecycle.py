"""Drop calibration, replay, rollback and cutover records; a model is now a version pointer."""

from __future__ import annotations

from alembic import op

revision = "0025_drop_model_lifecycle"
down_revision = "0024_inferred_public_time"
branch_labels = None
depends_on = None

# ADR-0022 retires these records' meaning; their rows are not kept.
_RETIRED = (
    "model_evaluation_output",
    "model_acceptance",
    "model_replay",
    "model_rollback",
    "system_cutover",
)


def upgrade() -> None:
    for table in _RETIRED:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
