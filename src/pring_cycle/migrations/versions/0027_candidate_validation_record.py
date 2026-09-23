"""Record each search candidate's fetch, hash and parser; drop the replay and PUBLIC columns."""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "0027_candidate_validation_record"
down_revision = "0026_structure_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("retrieval_candidate_validation")
    }
    for retired in ("run_attempt", "public_complete", "public_selected_claim_ids_json"):
        if retired in columns:
            op.execute(f"ALTER TABLE retrieval_candidate_validation DROP COLUMN {retired}")
    for added in ("fetched_url", "raw_hash", "parser_version"):
        if added not in columns:
            op.execute(f"ALTER TABLE retrieval_candidate_validation ADD COLUMN {added} TEXT")


def downgrade() -> None:
    raise RuntimeError("immutable_runtime_schema_downgrade_forbidden")
