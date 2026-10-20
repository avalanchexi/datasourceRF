"""tools/quality/output_consistency.py: the report's structured conclusions against the projection.

From model-v0016 on, the frozen manifest carries ``macro_judgement_rules`` and the report states
the macro judgement's stage and confidence among its conclusions; the audit holds them to the
projection's ``cycle_overview.macro_judgement``. Earlier models have neither, and the check stays
as it was.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = "结构化结论"
PROJECTION = "projection-test"


def load_layer() -> ModuleType:
    """The audit's modules import each other by bare name, as audit.py runs them."""
    quality = str(ROOT / "tools" / "quality")
    if quality not in sys.path:
        sys.path.insert(0, quality)
    import output_consistency

    return output_consistency


def audited_run(*, macro_rules: bool, judgement: dict | None, conclusions: dict):
    """A run whose projection has a report stating ``conclusions``; nothing else is filled in."""
    layer = load_layer()
    db = sqlite3.connect(":memory:")
    db.executescript(
        """
        CREATE TABLE parent_run (run_id TEXT, projection_set_id TEXT);
        CREATE TABLE projection_set (projection_set_id TEXT, envelope_json TEXT);
        CREATE TABLE analytical_dataset (projection_set_id TEXT, dataset_name TEXT,
            document_json TEXT);
        CREATE TABLE p0_assessment (projection_set_id TEXT, document_json TEXT);
        CREATE TABLE report_snapshot (report_snapshot_id TEXT, version INTEGER, status TEXT,
            current_stage TEXT, bundle_id TEXT, bundle_hash TEXT, body_json TEXT,
            projection_set_id TEXT);
        CREATE TABLE evidence_bundle (bundle_id TEXT, bundle_hash TEXT, projection_set_id TEXT,
            document_json TEXT);
        """
    )
    overview = {"current_stage": None, "stage_reason": "noncanonical_combination"}
    if judgement is not None:
        overview["macro_judgement"] = {"conclusion": judgement}
    db.execute("INSERT INTO parent_run VALUES ('run-test', ?)", (PROJECTION,))
    db.execute("INSERT INTO projection_set VALUES (?, '{}')", (PROJECTION,))
    db.execute(
        "INSERT INTO analytical_dataset VALUES (?, 'cycle_overview', ?)",
        (PROJECTION, json.dumps(overview)),
    )
    db.execute(
        "INSERT INTO report_snapshot VALUES ('report-test', 1, 'completed_degraded', NULL,"
        " 'bundle-test', 'hash', ?, ?)",
        (json.dumps({"conclusions": conclusions}), PROJECTION),
    )
    manifest = {"stage_mapping": {}}
    if macro_rules:
        manifest["macro_judgement_rules"] = {}
    run = layer.Run(
        db=db,
        run_id="run-test",
        artifacts=Path("/nonexistent"),
        target_date="2026-10-19",
        cutoff="2026-10-20T01:00:00+00:00",
        model_version_id="model-test",
        manifest=manifest,
    )
    return layer, run


def conclusions_row(report: str) -> str:
    """The check's row in the details table (the summary line also names a failed check)."""
    [row] = [line for line in report.splitlines() if line.startswith("|") and CHECK in line]
    return row


def test_v0016_report_stating_the_projections_macro_judgement_is_consistent():
    layer, run = audited_run(
        macro_rules=True,
        judgement={"stage": "stage_iii", "confidence": "tendency"},
        conclusions={
            "confirmation_applicable": None,
            "macro_stage": "stage_iii",
            "macro_confidence": "tendency",
        },
    )

    row = conclusions_row(layer.section(run))

    assert row.rstrip(" |").endswith(layer.OK)


@pytest.mark.parametrize(
    ("key", "stated"),
    [("macro_stage", "stage_iv"), ("macro_confidence", "explicit")],
)
def test_v0016_report_stating_another_macro_stage_or_confidence_is_inconsistent(
    key: str, stated: str
):
    conclusions = {
        "confirmation_applicable": None,
        "macro_stage": "stage_iii",
        "macro_confidence": "tendency",
    }
    layer, run = audited_run(
        macro_rules=True,
        judgement={"stage": "stage_iii", "confidence": "tendency"},
        conclusions=conclusions | {key: stated},
    )

    row = conclusions_row(layer.section(run))

    assert f"值不同的键：{key}" in row
    assert row.rstrip(" |").endswith(layer.BAD)


def test_v0015_report_without_a_macro_judgement_stays_consistent():
    layer, run = audited_run(
        macro_rules=False, judgement=None, conclusions={"confirmation_applicable": None}
    )

    row = conclusions_row(layer.section(run))

    assert row.rstrip(" |").endswith(layer.OK)
