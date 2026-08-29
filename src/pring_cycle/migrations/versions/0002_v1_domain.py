"""Establish the V1 evidence, model, projection, run, report, and maintenance schema."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.evidence import _EVIDENCE_SCHEMA
from pring_cycle.maintenance import _MAINTENANCE_SCHEMA
from pring_cycle.models import _MODEL_SCHEMA
from pring_cycle.projections import _PROJECTION_SCHEMA
from pring_cycle.reports import _REPORT_SCHEMA
from pring_cycle.runs import _RUN_SCHEMA

revision = "0002_v1_domain"
down_revision = "0001_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    driver_connection = cast(Any, op.get_bind().connection).driver_connection
    for schema in (
        _EVIDENCE_SCHEMA,
        _MODEL_SCHEMA,
        _PROJECTION_SCHEMA,
        _RUN_SCHEMA,
        _REPORT_SCHEMA,
        _MAINTENANCE_SCHEMA,
    ):
        driver_connection.executescript(schema)


def downgrade() -> None:
    for trigger in (
        "model_version_no_delete",
        "model_manifest_no_update",
        "analytical_dataset_no_delete",
        "analytical_dataset_no_update",
        "projection_set_no_delete",
        "projection_set_no_update",
        "source_claim_no_delete",
        "source_claim_no_update",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    for table in (
        "runtime_integrity",
        "maintenance_audit",
        "retention_object",
        "report_snapshot",
        "report_attempt",
        "evidence_bundle",
        "schedule_configuration",
        "run_checkpoint",
        "worker_lease",
        "run_attempt",
        "run_command",
        "parent_run",
        "model_rollback",
        "model_replay",
        "model_activation",
        "active_model",
        "model_acceptance",
        "model_version",
        "current_projection",
        "analytical_dataset",
        "projection_set",
        "retrieval_attempt",
        "derived_observation",
        "source_claim",
        "release_event",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
