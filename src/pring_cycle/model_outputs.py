"""Immutable structured model outputs, separate from acquired source originals."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage

HISTORY_OUTPUT_SCHEMA = "core-history-output-v0001"
REPLAY_OUTPUT_SCHEMA = "core-replay-output-v0001"
CORE_ASSETS = ("bond", "stock", "commodity")
MODEL_OUTPUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_evaluation_output (
    output_hash TEXT PRIMARY KEY,
    document_json TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS model_evaluation_output_no_update
BEFORE UPDATE ON model_evaluation_output BEGIN
    SELECT RAISE(ABORT, 'model_evaluation_output_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_output_no_delete
BEFORE DELETE ON model_evaluation_output BEGIN
    SELECT RAISE(ABORT, 'model_evaluation_output_is_immutable');
END;
"""


def model_output_json(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def model_output_hash(document: object) -> str:
    return hashlib.sha256(model_output_json(document).encode()).hexdigest()


def store_model_output(connection: sqlite3.Connection, document: dict[str, Any]) -> str:
    """Share the caller's transaction with its acceptance or replay reference."""
    content = model_output_json(document)
    digest = hashlib.sha256(content.encode()).hexdigest()
    connection.execute(
        "INSERT OR IGNORE INTO model_evaluation_output VALUES (?, ?)", (digest, content)
    )
    row = connection.execute(
        "SELECT document_json FROM model_evaluation_output WHERE output_hash=?", (digest,)
    ).fetchone()
    if row is None or row[0] != content:
        raise ValueError("model_output_hash_collision")
    return digest


def read_model_output(connection: sqlite3.Connection, digest: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT document_json FROM model_evaluation_output WHERE output_hash=?", (digest,)
    ).fetchone()
    if row is None:
        raise LookupError("model_output_document_missing")
    content = str(row[0])
    if hashlib.sha256(content.encode()).hexdigest() != digest:
        raise ValueError("model_output_hash_mismatch")
    document = json.loads(content)
    if not isinstance(document, dict):
        raise ValueError("model_output_document_invalid")
    return document


def validate_history_output(
    document: object,
    *,
    manifest: Mapping[str, Any],
    manifest_hash: str,
    range_start: str,
    range_end: str,
    evidence_hash: str,
    evaluated_days: int,
) -> dict[str, Any]:
    """Check complete model-bound daily outputs; absence is never a zero candidate."""
    if not isinstance(document, dict) or document.get("schema_version") != HISTORY_OUTPUT_SCHEMA:
        raise ValueError("model_output_schema_invalid")
    if not isinstance(evidence_hash, str) or re.fullmatch(r"[0-9a-f]{64}", evidence_hash) is None:
        raise ValueError("model_output_evidence_hash_invalid")
    if type(evaluated_days) is not int or evaluated_days <= 0:
        raise ValueError("model_output_coverage_invalid")
    rules = manifest["trend_rules"]
    duration = rules.get("candidate_duration_rule_version", "candidate-duration-v0001")
    if duration not in {"candidate-duration-v0001", "candidate-duration-v0002"}:
        raise ValueError("candidate_duration_rule_version_unsupported")
    expected = {
        "model_version_id": manifest["model_version_id"],
        "manifest_hash": manifest_hash,
        "candidate_duration_rule_version": duration,
        "as_of_mode": "public_as_of",
        "range_start": range_start,
        "range_end": range_end,
        "evidence_hash": evidence_hash,
        "asset_days": evaluated_days * 3,
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise ValueError("model_output_identity_mismatch")
    days = document.get("days")
    if not isinstance(days, list) or len(days) != evaluated_days or not days:
        raise ValueError("model_output_coverage_invalid")
    calendar: list[str] = []
    for row in days:
        if not isinstance(row, dict) or set(row) != {"business_date", "cutoff", "assets", "stage"}:
            raise ValueError("model_output_day_invalid")
        if not isinstance(row["business_date"], str):
            raise ValueError("model_output_day_invalid")
        day = date.fromisoformat(row["business_date"])
        day_text = day.isoformat()
        cutoff = datetime.combine(day, time.max, ZoneInfo("Asia/Shanghai")).isoformat()
        if (
            row["business_date"] != day_text
            or not range_start <= day_text <= range_end
            or row.get("cutoff") != cutoff
        ):
            raise ValueError("model_output_cutoff_invalid")
        calendar.append(day_text)
        assets = row.get("assets")
        if not isinstance(assets, dict) or set(assets) != set(CORE_ASSETS):
            raise ValueError("model_output_assets_incomplete")
        for output in assets.values():
            if not isinstance(output, dict) or set(output) != {
                "stable_state",
                "candidate_state",
                "actual_candidate_days",
                "candidate_days",
                "confirmation_threshold_days",
            }:
                raise ValueError("model_output_fields_incomplete")
            stable, candidate = output["stable_state"], output["candidate_state"]
            actual, shown, threshold = (
                output["actual_candidate_days"],
                output["candidate_days"],
                output["confirmation_threshold_days"],
            )
            if (
                stable not in (None, "bull", "bear")
                or candidate not in (None, "bull", "bear")
                or any(type(value) is not int for value in (actual, shown, threshold))
                or threshold != rules["persistence_days"]
                or threshold <= 0
                or not 0 <= actual < threshold
                or (candidate is None) != (actual == 0)
                or (candidate is not None and candidate == stable)
                or shown
                != (
                    threshold
                    if duration == "candidate-duration-v0001" and stable is not None
                    else actual
                )
            ):
                raise ValueError("model_output_candidate_invalid")
        states = {
            asset: CoreAssetState(assets[asset]["stable_state"])
            if assets[asset]["stable_state"] is not None
            else None
            for asset in CORE_ASSETS
        }
        stage = derive_formal_stage(
            bond=states["bond"],
            stock=states["stock"],
            commodity=states["commodity"],
            last_confirmed_stage=None,
        ).current_stage
        if row.get("stage") != (stage.value if stage is not None else None):
            raise ValueError("model_output_stage_invalid")
    if (
        calendar != sorted(set(calendar))
        or document.get("calendar_hash") != hashlib.sha256("\n".join(calendar).encode()).hexdigest()
    ):
        raise ValueError("model_output_calendar_invalid")
    return document


def core_output_differences(
    candidate: dict[str, Any], comparison: dict[str, Any]
) -> list[dict[str, Any]]:
    left = {row["business_date"]: row for row in candidate["days"]}
    right = {row["business_date"]: row for row in comparison["days"]}
    if left.keys() != right.keys():
        raise ValueError("model_output_coverage_invalid")
    return [
        {
            "business_date": day,
            "asset": asset,
            "field": name,
            "candidate": left[day]["assets"][asset][name],
            "comparison": right[day]["assets"][asset][name],
        }
        for day in sorted(left)
        for asset in CORE_ASSETS
        for name in (
            "stable_state",
            "candidate_state",
            "actual_candidate_days",
            "candidate_days",
            "confirmation_threshold_days",
        )
        if left[day]["assets"][asset][name] != right[day]["assets"][asset][name]
    ]


def validate_replay_output(
    document: object,
    *,
    candidate_manifest: Mapping[str, Any],
    comparison_manifest: Mapping[str, Any],
    candidate_manifest_hash: str,
    comparison_manifest_hash: str,
    range_start: str,
    range_end: str,
    evaluated_days: int,
    calendar_hash: str,
    stage_differences: int,
    core_state_differences: int,
    candidate_state_differences: int | None,
    candidate_days_differences: int | None,
) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema_version") != REPLAY_OUTPUT_SCHEMA:
        raise ValueError("model_output_schema_invalid")
    if any(
        document.get(key) != value
        for key, value in {
            "range_start": range_start,
            "range_end": range_end,
            "calendar_hash": calendar_hash,
        }.items()
    ):
        raise ValueError("model_output_identity_mismatch")
    for side, manifest, manifest_hash in (
        ("candidate", candidate_manifest, candidate_manifest_hash),
        ("comparison", comparison_manifest, comparison_manifest_hash),
    ):
        output = document.get(side)
        if not isinstance(output, dict):
            raise ValueError("model_output_side_missing")
        validate_history_output(
            output,
            manifest=manifest,
            manifest_hash=manifest_hash,
            range_start=range_start,
            range_end=range_end,
            evidence_hash=output.get("evidence_hash", ""),
            evaluated_days=evaluated_days,
        )
        if output["calendar_hash"] != calendar_hash:
            raise ValueError("model_output_calendar_invalid")
    differences = core_output_differences(document["candidate"], document["comparison"])
    if document.get("differences") != differences:
        raise ValueError("model_output_differences_invalid")
    counts = {
        "stable_state": core_state_differences,
        "candidate_state": candidate_state_differences,
        "candidate_days": candidate_days_differences,
    }
    if any(
        type(count) is not int or count != sum(item["field"] == name for item in differences)
        for name, count in counts.items()
    ):
        raise ValueError("model_output_difference_count_invalid")
    if type(stage_differences) is not int or stage_differences != sum(
        left["stage"] != right["stage"]
        for left, right in zip(
            document["candidate"]["days"], document["comparison"]["days"], strict=True
        )
    ):
        raise ValueError("model_output_difference_count_invalid")
    return document
