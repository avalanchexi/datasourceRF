from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.artifacts import store_artifact
from pring_cycle.cli import main
from pring_cycle.domain import CoreAssetState
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_120d_model_v0011_manifest,
)
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint


def encode(document: object) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def save(paths: RuntimePaths, document: object) -> str:
    return store_artifact(
        paths.database, paths.artifacts, encode(document), "application/json", "synthetic:admission"
    ).content_hash


def prepared_request(paths: RuntimePaths) -> tuple[dict[str, Any], str]:
    # These are synthetic reviewed contracts, not certification of the frozen v3 data.
    manifest = certified_120d_model_v0011_manifest(({"package_id": "fixture-builder"},))
    manifest.pop("model_version_id")
    manifest.pop("source_certification_packages")
    manifest.pop("source_certifications")
    manifest["metric_catalog_version"] = "synthetic-metric-catalog-admission-v1"
    manifest["trend_rules"]["candidate_duration_rule_version"] = "candidate-duration-v0002"
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["priority"] == "P2":
            definition["certification_status"] = "awaiting_source_certification"
    manifest["execution_fingerprint"] = execution_fingerprint(paths)
    original_hash = save(paths, {"synthetic": True, "official_sample_value": 7, "unit": "percent"})
    bindings = {
        item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
        for item in manifest["metric_definitions"]
        if item["priority"] == "P1" or item["role"] == "core_barometer"
    }
    subject = {
        "definition_bindings": bindings,
        "manifest_hash": hashlib.sha256(encode(manifest)).hexdigest(),
        "certified_from": "2026-03-09",
    }
    review = {
        "schema_version": "source-certification-review-v0001",
        "subject_hash": hashlib.sha256(encode(subject)).hexdigest(),
        "reviewer": "synthetic contract reviewer",
        "reviewed_at": "2026-09-08T00:00:00+00:00",
        "decision": "accepted",
        "assessments": {
            criterion: {
                "finding": f"Synthetic {criterion} acceptance; no actual source is certified.",
                "evidence": [
                    {"artifact_hash": original_hash, "source_reference": "synthetic:admission"}
                ],
            }
            for criterion in ("semantics", "fields", "history", "time", "permissions", "usage")
        },
    }
    package_hash = save(
        paths,
        {
            "schema_version": "source-certification-package-v0002",
            **subject,
            "review_hash": save(paths, review),
        },
    )
    return {
        "schema_version": "source-certified-candidate-request-v0001",
        "target_business_date": "2026-08-28",
        "manifest": manifest,
        "package_hashes": [package_hash],
    }, original_hash


def submit(paths: RuntimePaths, request_hash: str) -> None:
    main(
        [
            "model-source-certify",
            "--runtime-root",
            str(paths.override_root),
            "--target-date",
            "2026-08-28",
            "--candidate-request-hash",
            request_hash,
            "--confirm-personal-noncommercial",
            "--json",
        ]
    )


@pytest.mark.parametrize("artifact_kind", ["request", "package", "review", "original"])
@pytest.mark.parametrize("fault", ["changed", "missing"])
def test_corrupted_referenced_original_cannot_create_a_candidate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    artifact_kind: str,
    fault: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, original_hash = prepared_request(paths)
    request_hash = save(paths, request)
    versions_before = ModelRepository(paths.database).list_versions()
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    content_hash = {
        "request": request_hash,
        "package": package_hash,
        "review": package["review_hash"],
        "original": original_hash,
    }[artifact_kind]
    artifact_path = paths.artifacts / content_hash[:2] / content_hash
    if fault == "changed":
        artifact_path.write_bytes(b"altered original")
        expected_error = "certification_artifact_hash_mismatch"
    else:
        artifact_path.unlink()
        expected_error = "certification_artifact_unreadable"

    with pytest.raises(SystemExit) as failure:
        submit(paths, request_hash)

    assert failure.value.code == 2
    assert f"{expected_error}:{content_hash}" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before


@pytest.mark.parametrize("changed", ["definition", "rule", "execution"])
def test_review_for_previous_manifest_cannot_certify_changed_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    changed: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    versions_before = ModelRepository(paths.database).list_versions()
    request, _ = prepared_request(paths)
    if changed == "definition":
        request["manifest"]["metric_definitions"][7]["unit"] = "changed-unit"
    elif changed == "rule":
        request["manifest"]["trend_rules"]["persistence_days"] = 9
    else:
        request["manifest"]["execution_fingerprint"]["code_hash"] = "0" * 64

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert "certification_package_manifest_mismatch" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()


@pytest.mark.parametrize(
    "defect",
    [
        "preparation",
        "pending",
        "missing_fields",
        "empty_finding",
        "empty_evidence",
        "wrong_subject",
    ],
)
def test_incomplete_or_unbound_review_cannot_certify_a_package(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    if defect == "preparation":
        package["schema_version"] = "source-preparation-v0002"
    elif defect == "pending":
        review["decision"] = "pending"
    elif defect == "missing_fields":
        review["assessments"].pop("fields")
    elif defect == "empty_finding":
        review["assessments"]["fields"]["finding"] = ""
    elif defect == "empty_evidence":
        review["assessments"]["fields"]["evidence"] = []
    else:
        review["subject_hash"] = "0" * 64
    package["review_hash"] = save(paths, review)
    request["package_hashes"] = [save(paths, package)]
    versions_before = ModelRepository(paths.database).list_versions()

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert "certification_" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before


def bind_synthetic_review(
    paths: RuntimePaths, request: dict[str, Any], package: dict[str, Any]
) -> None:
    package["manifest_hash"] = hashlib.sha256(encode(request["manifest"])).hexdigest()
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    subject = {
        key: value for key, value in package.items() if key not in {"schema_version", "review_hash"}
    }
    review["subject_hash"] = hashlib.sha256(encode(subject)).hexdigest()
    package["review_hash"] = save(paths, review)
    request["package_hashes"] = [save(paths, package)]


@pytest.mark.parametrize(
    "defect",
    [
        "no_packages",
        "missing_p1",
        "wrong_definition_hash",
        "wrong_definition_version",
        "missing_metric",
        "wrong_priority",
        "missing_duration",
        "missing_selection",
        "missing_time",
        "missing_formula",
        "stale_execution",
        "frozen_catalog",
        "target_mismatch",
        "replay_before_certification",
        "core_mismatch",
        "uncertified_p1",
        "uncovered_p2_certification",
        "legacy_acceptance",
        "unknown_selection",
        "old_public_time",
        "short_window_rule",
        "missing_one_formula",
        "negative_persistence",
        "boolean_window",
        "unknown_trend",
        "wrong_stage_mapping",
        "spoofed_package_id",
        "early_replay",
        "missing_calibration_start",
        "unsupported_frequency",
        "invalid_volatility_window",
    ],
)
def test_formal_review_does_not_override_candidate_completeness_and_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    versions_before = ModelRepository(paths.database).list_versions()
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    manifest = request["manifest"]
    if defect == "missing_p1":
        package["definition_bindings"].pop("CN_MARGIN_BALANCE")
    elif defect == "wrong_definition_hash":
        package["definition_bindings"]["CN_MARGIN_BALANCE"] = "0" * 64
    elif defect == "wrong_definition_version":
        manifest["metric_definitions"][7]["definition_version"] = "another-definition"
    elif defect == "missing_metric":
        manifest["metric_definitions"].pop()
    elif defect == "wrong_priority":
        manifest["metric_definitions"][7]["priority"] = "P2"
    elif defect == "missing_duration":
        manifest["trend_rules"].pop("candidate_duration_rule_version")
    elif defect == "missing_selection":
        manifest.pop("selection_rule_version")
    elif defect == "missing_time":
        manifest.pop("point_in_time_rule_version")
    elif defect == "missing_formula":
        manifest.pop("derived_formula_versions")
    elif defect == "stale_execution":
        manifest["execution_fingerprint"]["code_hash"] = "0" * 64
    elif defect == "frozen_catalog":
        manifest["metric_catalog_version"] = "metric-catalog-v0003"
    elif defect == "target_mismatch":
        request["target_business_date"] = "2026-08-27"
    elif defect == "replay_before_certification":
        package["certified_from"] = "2026-03-10"
    elif defect == "core_mismatch":
        manifest["core_metrics"]["stock"] = "CN_EQ_CSI300"
    elif defect == "uncertified_p1":
        manifest["metric_definitions"][7]["certification_status"] = "awaiting_source_certification"
    elif defect == "uncovered_p2_certification":
        manifest["metric_definitions"][-1]["certification_status"] = "certified"
    elif defect == "legacy_acceptance":
        manifest["replay_acceptance_rule_version"] = "legacy"
    elif defect == "unknown_selection":
        manifest["selection_rule_version"] = "unknown"
    elif defect == "old_public_time":
        manifest["point_in_time_rule_version"] = "public-cutoff-v0001"
    elif defect == "short_window_rule":
        manifest["visible_context_window_rule_version"] = "short"
    elif defect == "missing_one_formula":
        manifest["derived_formula_versions"].pop("credit_impulse")
    elif defect == "negative_persistence":
        manifest["trend_rules"]["persistence_days"] = -1
    elif defect == "boolean_window":
        manifest["trend_rules"]["window_days"] = True
    elif defect == "unknown_trend":
        manifest["trend_rules"]["rule_version"] = "unknown"
    elif defect == "wrong_stage_mapping":
        manifest["stage_mapping"]["bull,bull,bull"] = "stage_i"
    elif defect == "spoofed_package_id":
        package["package_id"] = "source-certification-spoofed"
    elif defect == "early_replay":
        manifest["certified_replay_start"] = "2020-01-01"
        package["certified_from"] = "2020-01-01"
    elif defect == "missing_calibration_start":
        manifest.pop("calibration_range_start")
    elif defect == "unsupported_frequency":
        definition = next(
            item
            for item in manifest["metric_definitions"]
            if item["metric_id"] == "CN_MARGIN_BALANCE"
        )
        definition["frequency"] = "unsupported_frequency"
        package["definition_bindings"]["CN_MARGIN_BALANCE"] = hashlib.sha256(
            encode(definition)
        ).hexdigest()
    elif defect == "invalid_volatility_window":
        manifest["trend_rules"]["volatility_days"] = 140
    bind_synthetic_review(paths, request, package)
    if defect == "no_packages":
        request["package_hashes"] = []

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert "error:" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before


def test_complete_synthetic_contract_creates_one_queryable_candidate_without_activation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    active_before = models.active()
    projections = ProjectionSetRepository(paths.database)
    assets = [
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    ]
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=(assets[0], assets[1], assets[2]),
        last_confirmed_stage=None,
    )
    published_before = projections.current()
    versions_before = ModelRepository(paths.database).list_versions()
    request, _ = prepared_request(paths)
    request_hash = save(paths, request)

    submit(paths, request_hash)
    admitted = json.loads(capsys.readouterr().out)
    submit(paths, request_hash)
    assert json.loads(capsys.readouterr().out) == admitted
    assert admitted["status"] == "candidate"
    assert admitted["network_requests"] == 0
    main(["models", "--runtime-root", str(paths.override_root), "--json"])
    queried = json.loads(capsys.readouterr().out)
    assert len(queried["models"]) == len(versions_before) + 1
    assert admitted["model_version_id"] in {item["model_version_id"] for item in queried["models"]}
    stored = ModelRepository(paths.database).manifest(admitted["model_version_id"])
    assert stored["certification_request_hash"] == request_hash
    assert stored["metric_definitions"] == json.loads(
        encode(request["manifest"]["metric_definitions"])
    )
    assert len(stored["metric_definitions"]) == 61
    assert sum(item["priority"] == "P1" for item in stored["metric_definitions"]) == 42
    assert (
        sum(
            item["certification_status"] == "awaiting_source_certification"
            for item in stored["metric_definitions"]
            if item["priority"] == "P2"
        )
        == 13
    )
    assert stored["trend_rules"]["candidate_duration_rule_version"] == "candidate-duration-v0002"
    assert models.active() == active_before
    assert projections.current() == published_before
    assert projections.get(published_before.envelope.projection_set_id) == published_before


def test_review_cannot_relabel_an_original_registered_to_another_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    review["assessments"]["fields"]["evidence"][0]["source_reference"] = (
        "https://official.example/unobserved"
    )
    package["review_hash"] = save(paths, review)
    request["package_hashes"] = [save(paths, package)]
    versions_before = ModelRepository(paths.database).list_versions()

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert "certification_reference_unregistered" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before
