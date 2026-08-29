"""Establish the V1 evidence, model, projection, run, report, and maintenance schema."""

from __future__ import annotations

import hashlib
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

_FROZEN_SCHEMA_HASHES = (
    "b03ced2e9fc27629c0473a48f0f11a1581da567138b0457a56d892b6a10e2269",
    "77757c8340f8f9826f453395692965638977a997eccd7988064e7128fc98a430",
    "6fd0cb0c78f48e773a011cc6bf5e40ef79530a84aecf974e7bb61994831fcf79",
    "3faef5cc9c2eee5ad79202f87b91a9dcf4663f36923ab84b1f7734d44791867c",
    "100c405d786fb59b4f6b280210e95914acd80525d4e9edce506c55e7bb498c76",
    "3d7405ef66e80268733b53980a8681a5a6e0b49ecce74f46a9491a4cc5e69e29",
)


def upgrade() -> None:
    driver_connection = cast(Any, op.get_bind().connection).driver_connection
    schemas = (
        _EVIDENCE_SCHEMA,
        _MODEL_SCHEMA,
        _PROJECTION_SCHEMA,
        _RUN_SCHEMA,
        _REPORT_SCHEMA,
        _MAINTENANCE_SCHEMA,
    )
    observed_hashes = tuple(hashlib.sha256(schema.encode()).hexdigest() for schema in schemas)
    if observed_hashes != _FROZEN_SCHEMA_HASHES:
        raise RuntimeError("migration_0002_schema_snapshot_changed")
    for schema in schemas:
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
