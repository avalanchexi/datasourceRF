"""The approved ECB reference cross is a new identity, with prior candidates retained."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import bind_synthetic_review, encode, save, submit
from tests.models.test_p2_identity_migration import migrated_request

ECB_PAGE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"


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


def test_ecb_candidate_keeps_old_tma_model_and_p1_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        models.active()
    legacy = models.manifest("model-v0001")
    submit(paths, save(paths, migrated_request(paths)))
    tma_id = json.loads(capsys.readouterr().out)["model_version_id"]
    tma = models.manifest(tma_id)

    request = ecb_request(paths)
    submit(paths, save(paths, request))

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "candidate"
    ecb = models.manifest(result["model_version_id"])
    assert models.manifest(tma_id) == tma
    assert models.manifest("model-v0001") == legacy
    with pytest.raises(LookupError, match="active_model_unavailable"):
        models.active()
    assert len(ecb["metric_definitions"]) == 59
    assert {d["metric_id"] for d in ecb["metric_definitions"] if d["priority"] == "P1"} == {
        d["metric_id"] for d in tma["metric_definitions"] if d["priority"] == "P1"
    }
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 9, 17, 12, tzinfo=UTC),
        model_manifest=ecb,
    )
    rows = context.macro["international_context"]
    assert not {"CN_USDCNH_FXCM", "CN_USDCNH_TMA_SPOT_RATE"}.intersection(
        r["metric_id"] for r in rows
    )
    (row,) = [r for r in rows if r["metric_id"] == "CN_USDCNY_ECB_REFERENCE_CROSS"]
    assert row["value"] is None and row["status"] == "awaiting_source_certification"


def test_old_broker_quote_cannot_be_copied_into_ecb_cross(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence = EvidenceRepository(paths.database)
    at = datetime(2026, 9, 17, 12, tzinfo=UTC)
    old = metric_definition("CN_USDCNH_FXCM", definition_version="metric-catalog-v0001")
    claim = SourceClaimInput(
        metric_id=old.metric_id,
        definition_version=old.definition_version,
        period_kind="business_day",
        period_start="2026-09-11",
        period_end="2026-09-11",
        dimensions={},
        value=7.01,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=old.unit,
        provider="tushare",
        source_reference="synthetic:legacy:CN_USDCNH_FXCM",
        release_event_id="synthetic:legacy:fx:2026-09-11",
        release_at=None,
        public_available_at=None,
        fetched_at=at,
        available_at=at,
        certification_status="awaiting_source_certification",
        quality_status="validated",
    )
    stored = evidence.append_source_claim(claim)
    before = evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at)
    request = ecb_request(paths)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    with pytest.raises(ValueError, match="registered_source_contract_not_implemented"):
        evidence.append_source_claim(
            replace(
                claim,
                metric_id="CN_USDCNY_ECB_REFERENCE_CROSS",
                definition_version=version,
                unit="cny_per_usd",
            )
        )
    assert evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at) == before
    assert not evidence.metric_series(
        "CN_USDCNY_ECB_REFERENCE_CROSS", mode=AsOfMode.SYSTEM, as_of=at, definition_version=version
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name_cn", "TMA 美元兑离岸人民币即期参考汇率"),
        ("unit", "cnh_per_usd"),
        ("source_codes", ["TMA_USD_CNY_HK_SPOT_RATE"]),
        ("source_candidates", ["https://benchmark.tma.org.hk/benchmark/history/usd-cny-spot-rate"]),
        ("release_timezone", "Asia/Hong_Kong"),
        ("release_event_family", "tma_usd_cny_hk_spot_rate"),
        ("release_rule", "broker_intraday_ticks"),
        ("frequency", "monthly"),
    ],
)
def test_ecb_identity_rejects_mixed_source_and_timing_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str, value: Any
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = ecb_request(paths)
    definition = next(
        d
        for d in request["manifest"]["metric_definitions"]
        if d["metric_id"] == "CN_USDCNY_ECB_REFERENCE_CROSS"
    )
    definition[field] = value
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    models = ModelRepository(paths.database)
    before = models.list_versions()
    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))
    assert failure.value.code == 2
    assert "certification_ecb_identity_mismatch" in capsys.readouterr().err
    assert models.list_versions() == before


@pytest.mark.parametrize("defect", ["history_policy", "unreviewed_certification"])
def test_ecb_migration_does_not_authorize_history_rewrite_or_source_certification(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = ecb_request(paths)
    manifest = request["manifest"]
    if defect == "history_policy":
        manifest["metric_identity_migration"]["history_policy"] = "rewrite_old_claims"
        error = "certification_identity_migration_unsupported"
    else:
        next(
            d
            for d in manifest["metric_definitions"]
            if d["metric_id"] == "CN_USDCNY_ECB_REFERENCE_CROSS"
        )["certification_status"] = "certified"
        error = "certification_coverage_missing:CN_USDCNY_ECB_REFERENCE_CROSS"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    models = ModelRepository(paths.database)
    before = models.list_versions()
    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))
    assert failure.value.code == 2
    assert error in capsys.readouterr().err
    assert models.list_versions() == before
