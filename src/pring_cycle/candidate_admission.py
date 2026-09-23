"""Admission of reviewed source packages; never creates a review from a smoke."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from pring_cycle.catalog import validate_model_catalog
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.runtime_fingerprint import execution_fingerprint
from pring_cycle.source_contract_review import (
    SOURCE_MAPPING_REFERENCE_CONTRACT_VERSION,
    require_model_source_contract,
    require_reviewed_source_mappings,
)
from pring_cycle.storage import artifact_is_registered


def admit_source_certified_candidate(
    paths: RuntimePaths,
    *,
    request_hash: str,
    target_business_date: str,
    personal_noncommercial_use_approved: bool,
) -> dict[str, Any]:
    if not personal_noncommercial_use_approved:
        raise ValueError("tushare_personal_noncommercial_use_must_be_confirmed")
    request = _document(paths, request_hash)
    if request.get("schema_version") != "source-certified-candidate-request-v0001":
        raise ValueError("certification_request_schema_invalid")
    if request.get("target_business_date") != target_business_date:
        raise ValueError("certification_request_target_mismatch")
    target = date.fromisoformat(target_business_date)
    manifest = request.get("manifest")
    if not isinstance(manifest, dict):
        raise ValueError("certification_manifest_required")
    package_hashes = request.get("package_hashes")
    if not isinstance(package_hashes, list) or not package_hashes:
        raise ValueError("certification_packages_required")
    packages = []
    for package_hash in package_hashes:
        package = _reviewed_package(paths, package_hash)
        if package.get("manifest_hash") != _hash(manifest):
            raise ValueError(f"certification_package_manifest_mismatch:{package_hash}")
        packages.append({"package_id": f"source-certification-{package_hash}", **package})
    required, definitions = _validate_manifest(paths, manifest, target)
    covered: set[str] = set()
    for package in packages:
        bindings = package.get("definition_bindings")
        if not isinstance(bindings, dict) or not bindings:
            raise ValueError(f"certification_definition_bindings_required:{package['package_id']}")
        if date.fromisoformat(package["certified_from"]) > date.fromisoformat(
            manifest["certified_replay_start"]
        ):
            raise ValueError(f"certification_replay_precedes_source:{package['package_id']}")
        for metric_id, definition_hash in bindings.items():
            if metric_id not in definitions or definition_hash != _hash(definitions[metric_id]):
                raise ValueError(
                    f"certification_definition_mismatch:{package['package_id']}:{metric_id}"
                )
            covered.add(metric_id)
        require_reviewed_source_mappings(paths.database, package, definitions)
    if missing := required - covered:
        raise ValueError(f"certification_coverage_missing:{','.join(sorted(missing))}")
    manifest["source_certification_packages"] = packages
    manifest["certification_request_hash"] = request_hash
    manifest["source_mapping_reference_contract"] = {
        "version": SOURCE_MAPPING_REFERENCE_CONTRACT_VERSION,
        "request_hash": request_hash,
    }
    digest = _hash(manifest)
    manifest["model_version_id"] = f"model-reviewed-{digest}"
    return {
        **asdict(ModelRepository(paths.database)._create_admitted_candidate(manifest)),
        "network_requests": 0,
    }


def _validate_manifest(
    paths: RuntimePaths,
    manifest: dict[str, Any],
    target: date,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    require_model_source_contract(manifest)
    if any(
        key in manifest
        for key in (
            "model_version_id",
            "source_certification_packages",
            "source_certifications",
            "certification_request_hash",
            "source_mapping_reference_contract",
        )
    ):
        raise ValueError("certification_manifest_reserved_fields")
    if manifest.get("metric_catalog_version") in {"metric-catalog-v0001", "metric-catalog-v0002"}:
        raise ValueError("certification_new_catalog_required")
    rules = validate_model_catalog(manifest)
    definitions = {item["metric_id"]: item for item in manifest["metric_definitions"]}
    certified = {"certified", "derived_from_certified_inputs"}
    required = set()
    for definition in rules.metric_definitions:
        if definition.priority == "P1" or definition.role == "core_barometer":
            if definition.certification_status not in certified:
                raise ValueError(f"certification_metric_not_certified:{definition.metric_id}")
            required.add(definition.metric_id)
        elif definition.priority == "P2":
            if definition.certification_status in certified:
                required.add(definition.metric_id)
            elif definition.certification_status != "awaiting_source_certification":
                raise ValueError(f"certification_p2_status_invalid:{definition.metric_id}")
    if manifest.get("replay_acceptance_rule_version") != "active-baseline-exact-120-v0001":
        raise ValueError("certification_rule_version_unsupported:replay_acceptance_rule_version")
    if manifest.get("execution_fingerprint") != execution_fingerprint(paths):
        raise ValueError("certification_execution_fingerprint_mismatch")
    start = date.fromisoformat(manifest["certified_replay_start"])
    if start < date(2026, 3, 9) or start > target:
        raise ValueError("certification_replay_range_invalid")
    if manifest.get("calibration_range_start") != "2018-06-01":
        raise ValueError("certification_calibration_range_invalid")
    return required, definitions


def _reviewed_package(paths: RuntimePaths, package_hash: str) -> dict[str, Any]:
    package = _document(paths, package_hash)
    if package.get("schema_version") != "source-certification-package-v0002":
        raise ValueError(f"certification_package_schema_invalid:{package_hash}")
    if set(package) != {
        "schema_version",
        "definition_bindings",
        "manifest_hash",
        "certified_from",
        "review_hash",
    }:
        raise ValueError(f"certification_package_fields_invalid:{package_hash}")
    review_hash = package.get("review_hash")
    review = _document(paths, review_hash)
    subject = {
        key: value for key, value in package.items() if key not in {"schema_version", "review_hash"}
    }
    if (
        review.get("schema_version") != "source-certification-review-v0001"
        or review.get("decision") != "accepted"
        or not _text(review.get("reviewer"))
    ):
        raise ValueError(f"certification_review_incomplete:{review_hash}")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"])
        if reviewed_at.utcoffset() is None:
            raise ValueError("timezone_required")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"certification_review_time_invalid:{review_hash}") from error
    if review.get("subject_hash") != _hash(subject):
        raise ValueError(f"certification_review_subject_mismatch:{review_hash}")
    assessments = review.get("assessments")
    required = {"semantics", "fields", "history", "time", "permissions", "usage"}
    if not isinstance(assessments, dict) or set(assessments) != required:
        raise ValueError(f"certification_review_criteria_incomplete:{review_hash}")
    for criterion, assessment in assessments.items():
        if not isinstance(assessment, dict) or not _text(assessment.get("finding")):
            raise ValueError(f"certification_review_finding_missing:{review_hash}:{criterion}")
        evidence = assessment.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"certification_review_evidence_missing:{review_hash}:{criterion}")
        for reference in evidence:
            if not isinstance(reference, dict) or not _text(reference.get("source_reference")):
                raise ValueError(
                    f"certification_review_reference_invalid:{review_hash}:{criterion}"
                )
            if not _read(paths, reference.get("artifact_hash")):
                raise ValueError(f"certification_review_evidence_empty:{review_hash}:{criterion}")
            if not artifact_is_registered(
                paths.database, reference["artifact_hash"], reference["source_reference"]
            ):
                raise ValueError(
                    f"certification_reference_unregistered:{review_hash}:{criterion}:{reference['artifact_hash']}"
                )
    return package


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _hash(document: object) -> str:
    return hashlib.sha256(
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _document(paths: RuntimePaths, content_hash: Any) -> dict[str, Any]:
    document = json.loads(_read(paths, content_hash))
    if not isinstance(document, dict):
        raise ValueError(f"certification_document_invalid:{content_hash}")
    return document


def _read(paths: RuntimePaths, content_hash: object) -> bytes:
    if not isinstance(content_hash, str) or re.fullmatch(r"[0-9a-f]{64}", content_hash) is None:
        raise ValueError("certification_artifact_hash_invalid")
    try:
        content = (paths.artifacts / content_hash[:2] / content_hash).read_bytes()
    except OSError as error:
        raise ValueError(f"certification_artifact_unreadable:{content_hash}") from error
    if hashlib.sha256(content).hexdigest() != content_hash:
        raise ValueError(f"certification_artifact_hash_mismatch:{content_hash}")
    return content
