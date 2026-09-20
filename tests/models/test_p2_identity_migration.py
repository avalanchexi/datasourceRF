"""Public candidate admission for the explicitly approved P2 identity migration."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import build_context_projection
from pring_cycle.domain import CoreAssetState
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    prepared_request,
    save,
    submit,
)


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


def test_migrated_candidate_keeps_p1_and_old_models_while_retiring_p2_identities(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    before = models.manifest("model-v0001")
    projections = ProjectionSetRepository(paths.database)
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-09-11",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    P0ProjectionService(projections).publish(
        target_business_date="2026-09-11",
        system_as_of=datetime(2026, 9, 17, 12, tzinfo=UTC),
        assets=(assets[0], assets[1], assets[2]),
        last_confirmed_stage=None,
    )
    previous_projection = projections.current()
    request = migrated_request(paths)
    migration = copy.deepcopy(request["manifest"]["metric_identity_migration"])

    submit(paths, save(paths, request))

    admitted = json.loads(capsys.readouterr().out)
    assert admitted["status"] == "candidate"
    stored = models.manifest(admitted["model_version_id"])
    assert stored["metric_identity_migration"] == migration
    assert len(stored["metric_definitions"]) == 59
    assert sum(d["priority"] == "P1" for d in stored["metric_definitions"]) == 42
    assert models.manifest("model-v0001") == before
    assert projections.current() == previous_projection
    assert projections.get(previous_projection.envelope.projection_set_id) == previous_projection
    assert len(before["metric_definitions"]) == 61
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 9, 17, 12, tzinfo=UTC),
        model_manifest=stored,
    )
    international = context.macro["international_context"]
    ids = {row["metric_id"] for row in international}
    assert "CN_USDCNH_TMA_SPOT_RATE" in ids
    assert not ids.intersection({"CN_USDCNH_FXCM", *migration["removed_metric_ids"]})
    assert all(
        row["value"] is None and row["status"] == "awaiting_source_certification"
        for row in international
        if row["metric_id"] == "CN_USDCNH_TMA_SPOT_RATE"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_codes", ["USDCNH.FXCM"]),
        ("unit", "index_points"),
        ("release_event_family", "CN_USDCNH_FXCM"),
        ("name_cn", "FXCM 美元兑离岸人民币"),
        ("source_candidates", ["https://www.fxcm.com/"]),
        ("release_rule", "broker_intraday_ticks"),
    ],
)
def test_tma_identity_cannot_relabel_the_previous_broker_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: Any,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = migrated_request(paths)
    definition = next(
        d
        for d in request["manifest"]["metric_definitions"]
        if d["metric_id"] == "CN_USDCNH_TMA_SPOT_RATE"
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
    assert "certification_tma_identity_mismatch" in capsys.readouterr().err
    assert models.list_versions() == before


def test_migration_retains_old_claims_and_rejects_copying_them_into_tma(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence = EvidenceRepository(paths.database)
    at = datetime(2026, 9, 17, 12, tzinfo=UTC)
    originals = []
    for metric_id, value, dimensions in (
        ("CN_USDCNH_FXCM", 7.01, {}),
        (
            "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
            2000.0,
            {
                "contract_month": "2026-12",
                "measure": "settlement",
                "roll_chain_version": "synthetic-old-roll",
            },
        ),
        ("LBMA_GOLD_PRICE_PM_USD_OZT", 1999.0, {"fixing": "PM", "measure": "price"}),
    ):
        definition = metric_definition(metric_id, definition_version="metric-catalog-v0001")
        claim = SourceClaimInput(
            metric_id=metric_id,
            definition_version=definition.definition_version,
            period_kind="business_day",
            period_start="2026-09-11",
            period_end="2026-09-11",
            dimensions=dimensions,
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=definition.unit,
            provider="tushare",
            source_reference=f"synthetic:legacy:{metric_id}",
            release_event_id=f"synthetic:legacy:{metric_id}:2026-09-11",
            release_at=None,
            public_available_at=None,
            fetched_at=at,
            available_at=at,
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
        stored = evidence.append_source_claim(claim)
        originals.append(
            (claim, stored, evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at))
        )
    request = migrated_request(paths)

    submit(paths, save(paths, request))

    admitted = json.loads(capsys.readouterr().out)
    manifest = ModelRepository(paths.database).manifest(admitted["model_version_id"])
    for claim, stored, before in originals:
        assert evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=at) == before
        assert before.claims[0].value == claim.value
        with pytest.raises(KeyError, match="unknown_metric_id"):
            evidence.append_source_claim(
                replace(claim, definition_version=manifest["metric_catalog_version"])
            )
    with pytest.raises(ValueError, match="registered_source_contract_not_implemented"):
        evidence.append_source_claim(
            replace(
                originals[0][0],
                metric_id="CN_USDCNH_TMA_SPOT_RATE",
                definition_version=manifest["metric_catalog_version"],
                unit="cnh_per_usd",
            )
        )
    assert (
        evidence.metric_series(
            "CN_USDCNH_TMA_SPOT_RATE",
            mode=AsOfMode.SYSTEM,
            as_of=at,
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.parametrize(
    ("defect", "error"),
    [
        ("undeclared", "certification_catalog_scope_mismatch"),
        ("mixed_old_id", "certification_catalog_scope_mismatch"),
        ("missing_p1", "certification_catalog_scope_mismatch"),
        ("missing_gdp", "certification_catalog_scope_mismatch"),
        ("rewrite_history", "certification_identity_migration_unsupported"),
        ("unreviewed_certification", "certification_coverage_missing:CN_USDCNH_TMA_SPOT_RATE"),
    ],
)
def test_migration_cannot_expand_its_scope_or_bypass_review(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    defect: str,
    error: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = migrated_request(paths)
    manifest = request["manifest"]
    if defect == "undeclared":
        manifest.pop("metric_identity_migration")
    elif defect == "mixed_old_id":
        definition = copy.deepcopy(
            next(
                d
                for d in manifest["metric_definitions"]
                if d["metric_id"] == "CN_USDCNH_TMA_SPOT_RATE"
            )
        )
        definition["metric_id"] = "CN_USDCNH_FXCM"
        manifest["metric_definitions"].append(definition)
    elif defect in {"missing_p1", "missing_gdp"}:
        metric_id = "CN_PPI" if defect == "missing_p1" else "CN_GDP"
        manifest["metric_definitions"] = [
            d for d in manifest["metric_definitions"] if d["metric_id"] != metric_id
        ]
    elif defect == "rewrite_history":
        manifest["metric_identity_migration"]["history_policy"] = "rewrite_old_claims"
    elif defect == "unreviewed_certification":
        next(
            d for d in manifest["metric_definitions"] if d["metric_id"] == "CN_USDCNH_TMA_SPOT_RATE"
        )["certification_status"] = "certified"
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
