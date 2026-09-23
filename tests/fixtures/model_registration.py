"""Register synthetic model manifests the way a maintainer would: directly (ADR-0022).

These manifests used to reach the database through source certification and candidate
admission. That path is gone; a version is registered and then explicitly activated. The
synthetic review and package artifacts are still written because some tests edit them to
shape the manifest they register, but nothing reads them as a gate any more.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pring_cycle.artifacts import store_artifact
from pring_cycle.cli import main
from pring_cycle.models import certified_120d_model_v0011_manifest
from pring_cycle.runtime import RuntimePaths
from pring_cycle.runtime_fingerprint import execution_fingerprint

ECB_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"


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
    """Register the request's manifest as a new model version and print it as JSON."""
    request = json.loads((paths.artifacts / request_hash[:2] / request_hash).read_bytes())
    manifest = dict(request["manifest"])
    manifest["model_version_id"] = f"model-reviewed-{hashlib.sha256(encode(manifest)).hexdigest()}"
    manifest_path = Path(paths.data) / f"{manifest['model_version_id']}.json"
    manifest_path.write_bytes(encode(manifest))
    main(
        [
            "model-register",
            "--runtime-root",
            str(paths.override_root),
            "--manifest",
            str(manifest_path),
            "--json",
        ]
    )


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


def migrated_request(paths: RuntimePaths) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    old = next(d for d in manifest["metric_definitions"] if d["metric_id"] == "CN_USDCNH_FXCM")
    replacement = {
        **old,
        "metric_id": "CN_USDCNH_TMA_SPOT_RATE",
        "name_cn": "TMA 美元兑离岸人民币即期参考汇率",
        "unit": "cnh_per_usd",
        "allowed_units": ["cnh_per_usd"],
        "dimensions": [],
        "source_codes": ["TMA_USD_CNY_HK_SPOT_RATE"],
        "source_candidates": [],
        "release_event_family": "tma_usd_cny_hk_spot_rate",
        "release_rule": "source_schedule_required",
        "release_timezone": "Asia/Hong_Kong",
    }
    removed = [
        "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
        "LBMA_GOLD_PRICE_PM_USD_OZT",
    ]
    manifest["metric_identity_migration"] = {
        "version": "p2-official-identity-v0001",
        "replacements": {"CN_USDCNH_FXCM": "CN_USDCNH_TMA_SPOT_RATE"},
        "removed_metric_ids": removed,
        "history_policy": "retain_separate",
    }
    manifest["metric_definitions"] = [
        replacement if d["metric_id"] == "CN_USDCNH_FXCM" else d
        for d in manifest["metric_definitions"]
        if d["metric_id"] not in removed
    ]
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    return request


def ecb_request(paths: RuntimePaths) -> dict[str, Any]:
    request = migrated_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] = "synthetic-metric-catalog-ecb-identity-v1"
    manifest["metric_identity_migration"] = {
        **manifest["metric_identity_migration"],
        "version": "p2-ecb-reference-cross-v0001",
        "replacements": {"CN_USDCNH_FXCM": "CN_USDCNY_ECB_REFERENCE_CROSS"},
    }
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] == "CN_USDCNH_TMA_SPOT_RATE":
            definition.update(
                metric_id="CN_USDCNY_ECB_REFERENCE_CROSS",
                name_cn="ECB 美元兑人民币参考交叉汇率",
                unit="cny_per_usd",
                allowed_units=["cny_per_usd"],
                source_codes=["ECB_EUR_REFERENCE_CNY_USD_CROSS_V0001"],
                source_candidates=[ECB_PAGE],
                release_event_family="ecb_eur_reference_cross",
                release_timezone="Europe/Berlin",
            )
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"] = {
        d["metric_id"]: hashlib.sha256(encode(d)).hexdigest()
        for d in manifest["metric_definitions"]
        if d["priority"] == "P1" or d["role"] == "core_barometer"
    }
    bind_synthetic_review(paths, request, package)
    return request
