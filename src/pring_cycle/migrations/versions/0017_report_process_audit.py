"""Persist CLI version, process outcome, model and protocol fingerprints."""

from __future__ import annotations

from typing import Any, cast

from alembic import op

from pring_cycle.reports import upgrade_report_process_audit

revision = "0017_report_process_audit"
down_revision = "0016_search_candidate_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = cast(Any, op.get_bind().connection).driver_connection
    upgrade_report_process_audit(connection)


def downgrade() -> None:
    op.execute("DROP TABLE report_explanation_review")
    op.execute("ALTER TABLE report_attempt DROP COLUMN process_audit_json")
