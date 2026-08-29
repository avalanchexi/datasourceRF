"""Persist P0 assessments and deterministic data-gap notices."""

from __future__ import annotations

from alembic import op

revision = "0006_p0_assessment_history"
down_revision = "0005_run_step_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE p0_assessment (
            assessment_id TEXT PRIMARY KEY,
            target_business_date TEXT NOT NULL,
            system_as_of TEXT NOT NULL,
            event_kind TEXT NOT NULL CHECK(event_kind IN ('formal', 'gap')),
            projection_set_id TEXT REFERENCES projection_set(projection_set_id),
            document_json TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE data_gap_notice (
            notice_id TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL REFERENCES p0_assessment(assessment_id),
            client_request_id TEXT NOT NULL UNIQUE,
            document_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TRIGGER p0_assessment_no_update
        BEFORE UPDATE ON p0_assessment BEGIN
            SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER p0_assessment_no_delete
        BEFORE DELETE ON p0_assessment BEGIN
            SELECT RAISE(ABORT, 'p0_assessment_is_immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER data_gap_notice_no_update
        BEFORE UPDATE ON data_gap_notice BEGIN
            SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER data_gap_notice_no_delete
        BEFORE DELETE ON data_gap_notice BEGIN
            SELECT RAISE(ABORT, 'data_gap_notice_is_immutable');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS data_gap_notice_no_delete")
    op.execute("DROP TRIGGER IF EXISTS data_gap_notice_no_update")
    op.execute("DROP TRIGGER IF EXISTS p0_assessment_no_delete")
    op.execute("DROP TRIGGER IF EXISTS p0_assessment_no_update")
    op.execute("DROP TABLE IF EXISTS data_gap_notice")
    op.execute("DROP TABLE IF EXISTS p0_assessment")
