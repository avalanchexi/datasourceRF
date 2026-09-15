"""Immutable structured model outputs, separate from acquired source originals."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from datetime import date, datetime, time
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.context_replay_scope import (
    CONTEXT_FORMULA_INPUTS,
    CONTEXT_FORMULA_OUTPUTS,
    ContextReplayScope,
)
from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.metric_contracts import evidence_max_age_days, required_dimension_members

HISTORY_OUTPUT_SCHEMA = "core-history-output-v0001"
REPLAY_OUTPUT_SCHEMA = "core-replay-output-v0001"
CONTEXT_OUTPUT_SCHEMA_V0001 = "context-replay-output-v0001"
# Visible source points are stored once per document and referenced from each day.
CONTEXT_OUTPUT_SCHEMA = "context-replay-output-v0002"
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


_CONTEXT_VOLATILE_KEYS = {
    "available_at",
    "claim_id",
    "claim_ids",
    "claims",
    "derived_observation_id",
    "direction_input_observation_version_ids",
    "evidence_ids",
    "input_observation_version_ids",
    "latest_fetched_at",
    "model_input_observation_version_ids",
    "observation_id",
    "public_available_at",
    "selected_claim_id",
    "source_reference",
}


def normalized_context_output(value: object) -> str:
    def normalize(item: object) -> object:
        if isinstance(item, dict):
            return {
                str(key): normalize(child)
                for key, child in sorted(item.items())
                if key not in _CONTEXT_VOLATILE_KEYS
            }
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return item

    return model_output_json(normalize(value))


class ContextSourcePoints:
    """The distinct visible source points of one replay document, in first-reference order."""

    def __init__(self) -> None:
        self.points: list[dict[str, Any]] = []
        self.hashes: list[str] = []
        self._indexes: dict[str, int] = {}

    def references(self, snapshot: Mapping[str, list[dict[str, Any]]]) -> dict[str, list[int]]:
        """Store unseen points of one day's snapshot and return that day's point indexes."""
        references: dict[str, list[int]] = {}
        for metric_id, points in snapshot.items():
            indexes = []
            for point in points:
                content = model_output_json(point)
                digest = hashlib.sha256(content.encode()).hexdigest()
                if digest not in self._indexes:
                    self._indexes[digest] = len(self.points)
                    self.points.append(json.loads(content))
                    self.hashes.append(digest)
                indexes.append(self._indexes[digest])
            references[metric_id] = indexes
        return references


def context_day_source_inputs(
    document: Mapping[str, Any], row: Mapping[str, Any], side: str
) -> dict[str, list[dict[str, Any]]]:
    """One day's visible source snapshot, resolving point references of a v0002 document.

    Resolved points are the document's own shared objects: treat them as read-only.
    """
    inputs = row[side]["source_inputs"]
    if document["schema_version"] == CONTEXT_OUTPUT_SCHEMA_V0001:
        return dict(inputs)
    points = document["source_points"]
    return {
        metric_id: [points[index] for index in indexes] for metric_id, indexes in inputs.items()
    }


def _with_day_source_inputs(
    document: Mapping[str, Any],
    source_inputs: Callable[[Mapping[str, Any], str], object],
) -> list[dict[str, Any]]:
    return [
        {
            **row,
            **{
                side: {**row[side], "source_inputs": source_inputs(row, side)}
                for side in ("candidate", "comparison")
            },
        }
        for row in document["days"]
    ]


def compact_context_output(document: Mapping[str, Any]) -> dict[str, Any]:
    """The v0002 form of a context output document; a v0002 document is returned unchanged."""
    if document["schema_version"] == CONTEXT_OUTPUT_SCHEMA:
        return dict(document)
    table = ContextSourcePoints()
    days = _with_day_source_inputs(
        document, lambda row, side: table.references(row[side]["source_inputs"])
    )
    return {
        **document,
        "schema_version": CONTEXT_OUTPUT_SCHEMA,
        "days": days,
        "source_points": table.points,
        "source_point_hashes": table.hashes,
    }


def expand_context_output(document: Mapping[str, Any]) -> dict[str, Any]:
    """An independent inline v0001 copy, only for small documents such as test fixtures.

    Production code resolves one day at a time with ``context_day_source_inputs``.
    """
    if document["schema_version"] == CONTEXT_OUTPUT_SCHEMA:
        document = {
            **{
                key: value
                for key, value in document.items()
                if key not in {"source_points", "source_point_hashes"}
            },
            "schema_version": CONTEXT_OUTPUT_SCHEMA_V0001,
            "days": _with_day_source_inputs(
                document, lambda row, side: context_day_source_inputs(document, row, side)
            ),
        }
    expanded: dict[str, Any] = json.loads(model_output_json(document))
    return expanded


def context_output_document(
    candidate_manifest: Mapping[str, Any],
    comparison_manifest: Mapping[str, Any],
    *,
    range_start: str,
    range_end: str,
    expected_days: tuple[str, ...],
    days: list[dict[str, Any]],
    source_metrics: set[str],
    formula_keys: set[str],
    gaps: tuple[str, ...],
    not_applicable: bool = False,
    source_points: ContextSourcePoints | None = None,
) -> dict[str, Any]:
    """A v0002 document whose ``days`` reference points stored in ``source_points``."""
    table = source_points or ContextSourcePoints()
    return {
        "schema_version": CONTEXT_OUTPUT_SCHEMA,
        "source_points": table.points,
        "source_point_hashes": table.hashes,
        "as_of_mode": "public_as_of",
        "range_start": range_start,
        "range_end": range_end,
        "models": {
            side: {
                "model_version_id": manifest["model_version_id"],
                "manifest_hash": model_output_hash(manifest),
            }
            for side, manifest in (
                ("candidate", candidate_manifest),
                ("comparison", comparison_manifest),
            )
        },
        "expected_days": list(expected_days),
        "calendar_hash": hashlib.sha256("\n".join(expected_days).encode()).hexdigest()
        if expected_days
        else "",
        "source_metrics": sorted(source_metrics),
        "formula_keys": sorted(formula_keys),
        "status": "not_applicable" if not_applicable else "incomplete" if gaps else "recorded",
        "gaps": list(gaps),
        "days": days,
    }


def validate_context_output(
    document: object,
    *,
    candidate_manifest: Mapping[str, Any],
    comparison_manifest: Mapping[str, Any],
    range_start: str,
    range_end: str,
    calendar_hash: str,
    evaluated_days: int,
    context_output_differences: int,
    accept_inline_v0001: bool = False,
) -> dict[str, Any]:
    """Validate a context output; inline v0001 documents are accepted only when reading them."""
    schemas = {CONTEXT_OUTPUT_SCHEMA} | (
        {CONTEXT_OUTPUT_SCHEMA_V0001} if accept_inline_v0001 else set()
    )
    if not isinstance(document, dict) or document.get("schema_version") not in schemas:
        raise ValueError("context_output_schema_invalid")
    uses_point_table = document["schema_version"] == CONTEXT_OUTPUT_SCHEMA
    points: list[Any] = []
    if uses_point_table:
        stored, hashes = document.get("source_points"), document.get("source_point_hashes")
        if (
            not isinstance(stored, list)
            or not isinstance(hashes, list)
            or any(not isinstance(digest, str) for digest in hashes)
        ):
            raise ValueError("context_output_references_invalid")
        points = stored
        if (
            len(points) != len(hashes)
            or len(set(hashes)) != len(hashes)
            or any(
                not isinstance(point, dict) or digest != model_output_hash(point)
                for point, digest in zip(points, hashes, strict=True)
            )
        ):
            raise ValueError("context_output_references_invalid")
    used_points: set[int] = set()
    expected_models = {
        side: {
            "model_version_id": manifest["model_version_id"],
            "manifest_hash": model_output_hash(manifest),
        }
        for side, manifest in (
            ("candidate", candidate_manifest),
            ("comparison", comparison_manifest),
        )
    }
    if any(
        document.get(key) != value
        for key, value in {
            "models": expected_models,
            "as_of_mode": "public_as_of",
            "range_start": range_start,
            "range_end": range_end,
            "calendar_hash": calendar_hash,
        }.items()
    ):
        raise ValueError("context_output_identity_mismatch")
    expected_days = document.get("expected_days")
    if (
        not isinstance(expected_days, list)
        or type(evaluated_days) is not int
        or len(expected_days) != evaluated_days
    ):
        raise ValueError("context_output_calendar_invalid")
    if any(
        not isinstance(day, str) or not range_start <= day <= range_end for day in expected_days
    ):
        raise ValueError("context_output_calendar_invalid")
    if expected_days != sorted(set(expected_days)) or calendar_hash != (
        hashlib.sha256("\n".join(expected_days).encode()).hexdigest() if expected_days else ""
    ):
        raise ValueError("context_output_calendar_invalid")
    status, gaps, rows = document.get("status"), document.get("gaps"), document.get("days")
    if (
        status not in ("not_applicable", "recorded", "incomplete")
        or not isinstance(gaps, list)
        or not isinstance(rows, list)
    ):
        raise ValueError("context_output_status_invalid")
    if any(not isinstance(gap, str) or not gap for gap in gaps) or (status == "incomplete") != bool(
        gaps
    ):
        raise ValueError("context_output_status_invalid")
    for key in ("source_metrics", "formula_keys"):
        values = document.get(key)
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            or values != sorted(set(values))
        ):
            raise ValueError("context_output_scope_invalid")
    scope = ContextReplayScope.from_manifests(candidate_manifest, comparison_manifest)
    if (
        document["source_metrics"] != sorted(scope.source_metrics)
        or document["formula_keys"] != sorted(scope.formula_keys)
        or (status == "not_applicable") == scope.requires_replay
        or (status == "not_applicable" and rows)
    ):
        raise ValueError("context_output_scope_invalid")
    observed_days = []
    differences = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "business_date",
            "cutoff",
            "candidate",
            "comparison",
        }:
            raise ValueError("context_output_day_invalid")
        day = row["business_date"]
        if day not in expected_days:
            raise ValueError("context_output_day_invalid")
        cutoff = datetime.combine(
            date.fromisoformat(day), time.max, ZoneInfo("Asia/Shanghai")
        ).isoformat()
        if row["cutoff"] != cutoff:
            raise ValueError("context_output_cutoff_invalid")
        observed_days.append(day)
        economic = []
        for side in ("candidate", "comparison"):
            output = row[side]
            if not isinstance(output, dict) or any(
                not isinstance(output.get(key), dict) for key in ("macro", "inventory")
            ):
                raise ValueError("context_output_fields_incomplete")
            macro, inventory = output["macro"], output["inventory"]
            if (
                not {
                    "policy_direction",
                    "policy_action",
                    "transmission",
                    "credit_response",
                    "credit",
                    "overheat_state",
                    "overheat",
                    "price_pressure",
                    "price_chain",
                    "international_context",
                    "score",
                    "model_input_observation_version_ids",
                }
                <= macro.keys()
                or not {
                    "quadrant",
                    "directions",
                    "cards",
                    "real_inventory_approximation",
                    "semantics",
                    "score",
                }
                <= inventory.keys()
                or any(
                    not isinstance(macro[key], dict)
                    for key in (
                        "policy_action",
                        "transmission",
                        "credit",
                        "overheat",
                        "price_chain",
                    )
                )
                or any(
                    not isinstance(macro[key], list)
                    for key in ("international_context", "model_input_observation_version_ids")
                )
                or any(
                    not isinstance(identity, str)
                    for identity in macro["model_input_observation_version_ids"]
                )
                or not isinstance(inventory["cards"], list)
                or any(
                    not isinstance(inventory[key], dict)
                    for key in ("directions", "real_inventory_approximation", "semantics")
                )
            ):
                raise ValueError("context_output_fields_incomplete")
            for key in ("observation_version_ids", "warnings"):
                if not isinstance(output.get(key), list) or any(
                    not isinstance(item, str) for item in output[key]
                ):
                    raise ValueError("context_output_fields_incomplete")
            inputs = output.get("source_inputs")
            if not isinstance(inputs, dict) or set(inputs) != set(document["source_metrics"]):
                raise ValueError("context_output_inputs_incomplete")
            if uses_point_table:
                if any(
                    not isinstance(indexes, list)
                    or any(
                        type(index) is not int or not 0 <= index < len(points) for index in indexes
                    )
                    for indexes in inputs.values()
                ):
                    raise ValueError("context_output_references_invalid")
                used_points.update(index for indexes in inputs.values() for index in indexes)
                inputs = context_day_source_inputs(document, row, side)
            _validate_context_inputs(
                inputs,
                scope.candidate if side == "candidate" else scope.comparison,
                complete=status == "recorded",
                required_metrics=scope.requires_certification,
                cutoff=datetime.fromisoformat(cutoff),
                model_input_ids=set(macro["model_input_observation_version_ids"]),
            )
            _validate_optional_context_rows(
                macro["international_context"],
                inputs,
                scope=scope,
                rules=scope.candidate if side == "candidate" else scope.comparison,
                cutoff=datetime.fromisoformat(cutoff),
                model_input_ids=set(macro["model_input_observation_version_ids"]),
            )
            economic.append(
                normalized_context_output({key: output[key] for key in ("macro", "inventory")})
            )
        differences += economic[0] != economic[1]
    if observed_days != sorted(set(observed_days)) or (
        status == "recorded" and observed_days != expected_days
    ):
        raise ValueError("context_output_coverage_invalid")
    if uses_point_table and used_points != set(range(len(points))):
        raise ValueError("context_output_references_invalid")
    if type(context_output_differences) is not int or differences != context_output_differences:
        raise ValueError("context_output_difference_count_invalid")
    return document


def _validate_optional_context_rows(
    rows: list[Any],
    inputs: dict[str, Any],
    *,
    scope: ContextReplayScope,
    rules: ContextProjectionRules,
    cutoff: datetime,
    model_input_ids: set[str],
) -> None:
    optional_metrics = scope.optional_metrics
    optional_formulas = {
        CONTEXT_FORMULA_OUTPUTS[key]: key
        for key in scope.formula_keys - scope.required_formula_keys
    }
    definitions = {item.metric_id: item for item in rules.metric_definitions}
    expected_metrics = (optional_metrics | optional_formulas.keys()) & definitions.keys()
    present_metrics = {
        row["metric_id"]
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("metric_id"), str)
    }
    if not expected_metrics <= present_metrics:
        raise ValueError("context_output_inputs_incomplete")
    scoped_ids = {
        point["selected_claim_id"]
        for metric_id in optional_metrics
        for point in inputs.get(metric_id, [])
        if isinstance(point["selected_claim_id"], str)
    }
    referenced_ids: set[str] = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("metric_id"), str)
            or row["metric_id"] not in expected_metrics
        ):
            continue
        metric_id = row["metric_id"]
        claim_id = row.get("selected_claim_id")
        if isinstance(claim_id, str):
            scoped_ids.add(claim_id)
        if row.get("status") not in {"current", "available"}:
            continue
        allowed_certifications = (
            {"certified", "derived_from_certified_inputs"}
            if metric_id in optional_formulas
            else {"certified"}
        )
        if (
            definitions[metric_id].certification_status not in allowed_certifications
            or not isinstance(claim_id, str)
            or claim_id not in model_input_ids
            or type(row.get("value")) not in (int, float)
            or not isfinite(row["value"])
            or row.get("value_state") != "reported_value"
            or not isinstance(row.get("period"), str)
        ):
            raise ValueError("context_output_inputs_incomplete")
        try:
            age = (cutoff.date() - date.fromisoformat(row["period"])).days
        except ValueError as error:
            raise ValueError("context_output_inputs_incomplete") from error
        if not 0 <= age <= evidence_max_age_days(metric_id, definitions[metric_id].frequency):
            raise ValueError("context_output_inputs_incomplete")
        referenced_ids.add(claim_id)
        if metric_id in optional_formulas:
            formula_key = optional_formulas[metric_id]
            parent_ids = row.get("input_observation_version_ids")
            if (
                formula_key not in rules.formula_versions
                or row.get("formula_version") != rules.formula_versions[formula_key]
                or not isinstance(parent_ids, list)
                or not parent_ids
                or any(not isinstance(item, str) for item in parent_ids)
                or len(set(parent_ids)) != len(parent_ids)
                or not set(parent_ids) <= model_input_ids
            ):
                raise ValueError("context_output_inputs_incomplete")
            matched_ids: set[str] = set()
            parents = {}
            for parent_metric in CONTEXT_FORMULA_INPUTS[formula_key]:
                points = [
                    point
                    for point in inputs.get(parent_metric, [])
                    if point["selected_claim_id"] in parent_ids
                ]
                if not points or any(not _context_point_is_adoptable(point) for point in points):
                    raise ValueError("context_output_inputs_incomplete")
                parents[parent_metric] = points
                matched_ids.update(point["selected_claim_id"] for point in points)
            if matched_ids != set(parent_ids):
                raise ValueError("context_output_inputs_incomplete")
            referenced_ids.update(matched_ids)
            _validate_optional_formula_value(row, formula_key, parents)
            continue
        if not any(
            point["selected_claim_id"] == claim_id
            and point["selection_status"] == "selected"
            and point["selected_value"] is not None
            and point["selected_value"] == row.get("value")
            and point["dimensions"] == row.get("dimensions")
            and point["period_start"] == row.get("period_start")
            and point["period_end"] == row.get("period")
            and point["observation_id"] == row.get("observation_id")
            and any(
                claim.get("claim_id") == claim_id and claim.get("unit") == row.get("unit")
                for claim in point["claims"]
            )
            for point in inputs.get(metric_id, [])
        ):
            raise ValueError("context_output_inputs_incomplete")
        direction_ids = row.get("direction_input_observation_version_ids", [])
        if not isinstance(direction_ids, list) or any(
            not isinstance(item, str) or item not in model_input_ids for item in direction_ids
        ):
            raise ValueError("context_output_inputs_incomplete")
        for direction_id in direction_ids:
            if not any(
                point["selected_claim_id"] == direction_id
                and point["dimensions"] == row.get("dimensions")
                and point["period_end"] < row["period"]
                and _context_point_is_adoptable(point)
                for point in inputs.get(metric_id, [])
            ):
                raise ValueError("context_output_inputs_incomplete")
        referenced_ids.update(direction_ids)
    if (model_input_ids & scoped_ids) - referenced_ids:
        raise ValueError("context_output_inputs_incomplete")


def _validate_optional_formula_value(
    row: dict[str, Any], formula_key: str, parents: dict[str, list[dict[str, Any]]]
) -> None:
    # UST is the currently supported optional formula; other context formulas serve P1.
    if (
        formula_key != "ust_2s10s_spread"
        or row["formula_version"] != "ust-2s10s-spread-v0001"
        or row.get("unit") != "basis_points"
        or row.get("dimensions") != {}
        or any(len(points) != 1 for points in parents.values())
    ):
        raise ValueError("context_output_inputs_incomplete")
    two_year = parents["UST2Y_NOMINAL_YIELD"][0]
    ten_year = parents["UST10Y_NOMINAL_YIELD"][0]
    if (
        any(
            point["period_start"] != row.get("period")
            or point["period_end"] != row.get("period")
            or point["dimensions"] != {}
            for point in (two_year, ten_year)
        )
        or row["value"] != (ten_year["selected_value"] - two_year["selected_value"]) * 100.0
    ):
        raise ValueError("context_output_inputs_incomplete")


def _validate_context_inputs(
    inputs: dict[str, Any],
    rules: ContextProjectionRules,
    *,
    complete: bool,
    required_metrics: set[str],
    cutoff: datetime,
    model_input_ids: set[str],
) -> None:
    definitions = {item.metric_id: item for item in rules.metric_definitions}
    for metric_id, points in inputs.items():
        definition = definitions.get(metric_id)
        required = (
            complete
            and metric_id in required_metrics
            and definition is not None
            and definition.certification_status == "certified"
        )
        if not isinstance(points, list) or (
            required and not points and definition is not None and definition.frequency != "event"
        ):
            raise ValueError("context_output_inputs_incomplete")
        for point in points:
            if (
                not isinstance(point, dict)
                or not {
                    "definition_version",
                    "period_start",
                    "period_end",
                    "dimensions",
                    "observation_id",
                    "selected_claim_id",
                    "selected_value",
                    "selection_status",
                    "value_state",
                    "claims",
                }
                <= point.keys()
            ):
                raise ValueError("context_output_inputs_incomplete")
            if (
                point["definition_version"] != rules.metric_catalog_version
                or not isinstance(point["observation_id"], str)
                or not point["observation_id"]
                or not isinstance(point["dimensions"], dict)
                or not isinstance(point["claims"], list)
                or any(not isinstance(claim, dict) for claim in point["claims"])
            ):
                raise ValueError("context_output_inputs_incomplete")
            value = point["selected_value"]
            if value is not None and (type(value) not in (int, float) or not isfinite(value)):
                raise ValueError("context_output_inputs_incomplete")
            selected = [
                claim
                for claim in point["claims"]
                if claim.get("claim_id") == point["selected_claim_id"]
            ]
            if point["selection_status"] == "selected":
                if (
                    not point["selected_claim_id"]
                    or len(selected) != 1
                    or selected[0].get("value") != point["selected_value"]
                ):
                    raise ValueError("context_output_inputs_incomplete")
                claim = selected[0]
                try:
                    public = datetime.fromisoformat(claim["public_available_at"])
                    acquired = datetime.fromisoformat(claim["available_at"])
                    period_start = date.fromisoformat(point["period_start"])
                    period_end = date.fromisoformat(point["period_end"])
                    valid = (
                        public.tzinfo is not None
                        and acquired.tzinfo is not None
                        and public <= cutoff
                        and period_start <= period_end
                        and definition is not None
                        and claim["unit"] in (definition.allowed_units or (definition.unit,))
                    )
                except (KeyError, TypeError, ValueError):
                    valid = False
                if not valid:
                    raise ValueError("context_output_inputs_incomplete")
            if (
                isinstance(point["selected_claim_id"], str)
                and point["selected_claim_id"] in model_input_ids
                and (
                    definition is None
                    or definition.certification_status != "certified"
                    or not _context_point_is_adoptable(point)
                )
            ):
                raise ValueError("context_output_inputs_incomplete")
        if required and points:
            latest = max(point["period_end"] for point in points)
            latest_by_dimensions: dict[str, dict[str, Any]] = {}
            for point in points:
                key = model_output_json(point["dimensions"])
                if (
                    key not in latest_by_dimensions
                    or point["period_end"] > latest_by_dimensions[key]["period_end"]
                ):
                    latest_by_dimensions[key] = point
            current_points = [
                point
                for point in latest_by_dimensions.values()
                if (
                    point["selected_claim_id"] in model_input_ids
                    if metric_id == "CN_FUTURES_WARRANTS"
                    else point["period_end"] == latest
                )
            ]
            members = (
                required_dimension_members(
                    metric_id, definition_version=rules.metric_catalog_version, period=latest
                )
                or ()
            )
            if any(
                not any(
                    all(point["dimensions"].get(key) == value for key, value in member.items())
                    for point in current_points
                )
                for member in members
            ):
                raise ValueError("context_output_inputs_incomplete")
            for point in current_points:
                if members and not any(
                    all(point["dimensions"].get(key) == value for key, value in member.items())
                    for member in members
                ):
                    continue
                if not _context_point_is_adoptable(point):
                    raise ValueError("context_output_inputs_incomplete")


def _context_point_is_adoptable(point: dict[str, Any]) -> bool:
    selected_claim = next(
        (claim for claim in point["claims"] if claim.get("claim_id") == point["selected_claim_id"]),
        None,
    )
    return (
        point["selection_status"] == "selected"
        and selected_claim is not None
        and point["selected_value"] is not None
        and point["value_state"] == "reported_value"
        and selected_claim.get("certification_status") == "certified"
        and selected_claim.get("quality_status") == "validated"
    )
