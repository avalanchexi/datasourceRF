from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def record_explanation_review(
    connection: sqlite3.Connection,
    report_snapshot_id: str,
    *,
    output_hash: str,
    reviewer: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT s.body_json, s.bundle_hash, b.document_json FROM report_snapshot s "
        "JOIN evidence_bundle b USING(bundle_id) WHERE s.report_snapshot_id=?",
        (report_snapshot_id,),
    ).fetchone()
    if row is None:
        raise LookupError("report_snapshot_not_found")
    body, bundle = json.loads(row[0]), json.loads(row[2])
    if not body.get("ai_explanation"):
        raise ValueError("review_requires_ai_explanation")
    if body.get("explanation_verification", {}).get("output_hash") != output_hash:
        raise ValueError("review_output_mismatch")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200:
        raise ValueError("reviewer_required")
    if not isinstance(sections, list) or len(sections) != len(body["ai_explanation"]):
        raise ValueError("review_section_coverage_incomplete")
    for generated_section in body["ai_explanation"]:
        paragraph = generated_section.get("explanation")
        if (
            not isinstance(paragraph, str)
            or not paragraph.strip()
            or any(separator in paragraph for separator in "\r\n\u2028\u2029")
        ):
            raise ValueError("review_requires_single_paragraph_sections")
    for index, section in enumerate(sections):
        if (
            not isinstance(section, dict)
            or set(section) != {"index", "verdict", "assessment", "support", "counterevidence"}
            or type(section["index"]) is not int
            or section["index"] != index
            or not isinstance(section["verdict"], str)
            or section["verdict"] not in {"supported", "contradicted", "unsupported"}
            or not isinstance(section["assessment"], str)
            or not section["assessment"].strip()
        ):
            raise ValueError("review_section_invalid")
        for role in ("support", "counterevidence"):
            facts = section[role]
            if not isinstance(facts, list) or len(facts) > 30:
                raise ValueError("review_facts_invalid")
            for fact in facts:
                if not isinstance(fact, dict) or set(fact) != {"pointer", "value"}:
                    raise ValueError("review_fact_invalid")
                actual = _fact_at_pointer(bundle, fact["pointer"])
                if json.dumps(actual, sort_keys=True) != json.dumps(fact["value"], sort_keys=True):
                    raise ValueError("review_fact_mismatch")
        if section["verdict"] == "supported" and not section["support"]:
            raise ValueError("review_support_required")
        if section["verdict"] == "contradicted" and not section["counterevidence"]:
            raise ValueError("review_counterevidence_required")
    document = {
        "review_id": "report-review-" + uuid4().hex,
        "report_snapshot_id": report_snapshot_id,
        "output_hash": output_hash,
        "bundle_hash": str(row[1]),
        "reviewer": reviewer,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "method": "documented_paragraph_review_v1",
        "status": "passed"
        if all(s["verdict"] == "supported" for s in sections)
        else "needs_attention",
        "identity_and_references": "passed",
        "semantic_support": "reviewed",
        "sections": sections,
    }
    connection.execute(
        "INSERT INTO report_explanation_review(review_id, report_snapshot_id, document_json) "
        "VALUES (?, ?, ?)",
        (
            document["review_id"],
            report_snapshot_id,
            json.dumps(document, ensure_ascii=False, sort_keys=True),
        ),
    )
    return document


def explanation_reviews(
    connection: sqlite3.Connection, report_snapshot_id: str
) -> tuple[dict[str, Any], ...]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='report_explanation_review'"
    ).fetchone():
        return ()
    rows = connection.execute(
        "SELECT document_json FROM report_explanation_review "
        "WHERE report_snapshot_id=? ORDER BY rowid",
        (report_snapshot_id,),
    ).fetchall()
    return tuple(json.loads(row[0]) for row in rows)


def _fact_at_pointer(bundle: dict[str, Any], pointer: str) -> object:
    if not isinstance(pointer, str) or not pointer.startswith("/") or len(pointer) > 1024:
        raise ValueError("review_fact_pointer_invalid")
    keys = [key.replace("~1", "/").replace("~0", "~") for key in pointer[1:].split("/")]
    if keys[0] not in {
        "core_states",
        "current_stage",
        "stage_reason",
        "support",
        "counterevidence",
        "governance_gaps",
        "structured_context",
        "conclusions",
        "results",
        "report_cutoff",
        "target_business_date",
    }:
        raise ValueError("review_fact_pointer_invalid")
    value: Any = bundle
    try:
        for key in keys:
            if isinstance(value, list):
                if not key.isdecimal():
                    raise ValueError("invalid_list_index")
                value = value[int(key)]
            else:
                value = value[key]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError("review_fact_pointer_invalid") from error
    return value


REPORT_EXPLANATION_REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS report_explanation_review (
    review_id TEXT PRIMARY KEY,
    report_snapshot_id TEXT NOT NULL REFERENCES report_snapshot(report_snapshot_id),
    document_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS report_explanation_review_no_update
BEFORE UPDATE ON report_explanation_review
BEGIN SELECT RAISE(ABORT, 'report_review_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_explanation_review_no_delete
BEFORE DELETE ON report_explanation_review
BEGIN SELECT RAISE(ABORT, 'report_review_is_immutable'); END;
"""
