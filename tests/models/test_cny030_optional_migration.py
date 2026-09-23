"""Public admission of ADR-0020, retaining the approved ECB and margin identities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.catalog_registry import registered_definitions
from pring_cycle.cli import main
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import bind_synthetic_review, encode, save
from tests.models.test_ecb_identity_migration import ecb_request
from tests.models.test_margin_scope_migration import migrated_request as margin_request

CNY030 = "CN_BOND_FULL_PRICE_CNY030"


def submit(paths: RuntimePaths, request_hash: str) -> None:
    request = json.loads((paths.artifacts / request_hash[:2] / request_hash).read_bytes())
    main(
        [
            "model-source-certify",
            "--runtime-root",
            str(paths.override_root),
            "--target-date",
            request["target_business_date"],
            "--candidate-request-hash",
            request_hash,
            "--confirm-personal-noncommercial",
            "--json",
        ]
    )


def rebind(paths: RuntimePaths, request: dict[str, Any]) -> None:
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"] = {
        d["metric_id"]: hashlib.sha256(encode(d)).hexdigest()
        for d in request["manifest"]["metric_definitions"]
        if d["priority"] == "P1" or d["role"] == "core_barometer"
    }
    bind_synthetic_review(paths, request, package)


def optional_request(paths: RuntimePaths) -> dict[str, Any]:
    request = ecb_request(paths)
    request["target_business_date"] = "2026-09-22"
    margin = next(
        d
        for d in margin_request(paths)["manifest"]["metric_definitions"]
        if d["metric_id"] == "CN_MARGIN_BALANCE_SSE_SZSE"
    )
    manifest = request["manifest"]
    manifest["metric_catalog_version"] = "synthetic-cny030-optional-v1"
    manifest["metric_identity_migration"] = {
        "version": "cny030-optional-ecb-margin-v0001",
        "replacements": {
            "CN_USDCNH_FXCM": "CN_USDCNY_ECB_REFERENCE_CROSS",
            "CN_MARGIN_BALANCE": "CN_MARGIN_BALANCE_SSE_SZSE",
        },
        "removed_metric_ids": [
            "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
            "LBMA_GOLD_PRICE_PM_USD_OZT",
        ],
        "priority_changes": {CNY030: {"from": "P1", "to": "P2"}},
        "history_policy": "retain_separate",
    }
    manifest["metric_definitions"] = [
        margin if d["metric_id"] == "CN_MARGIN_BALANCE" else d
        for d in manifest["metric_definitions"]
    ]
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] == CNY030:
            definition.update(priority="P2", certification_status="awaiting_source_certification")
    rebind(paths, request)
    return request


def test_cny030_optional_candidate_preserves_approved_identities(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    previous = models.manifest("model-v0001")
    request = optional_request(paths)
    declared = json.loads(encode(request["manifest"]))

    submit(paths, save(paths, request))

    admitted = json.loads(capsys.readouterr().out)
    assert admitted["status"] == "candidate"
    manifest = models.manifest(admitted["model_version_id"])
    definitions = registered_definitions(paths.database, manifest["metric_catalog_version"])
    by_id = {d["metric_id"]: d for d in definitions}
    assert sorted(definitions, key=lambda d: d["metric_id"]) == sorted(
        declared["metric_definitions"], key=lambda d: d["metric_id"]
    )
    assert (by_id[CNY030]["priority"], by_id[CNY030]["certification_status"]) == (
        "P2",
        "awaiting_source_certification",
    )
    assert len(definitions) == 59
    assert sum(d["priority"] == "P1" for d in definitions) == 41
    assert sum(d["priority"] == "P2" for d in definitions) == 12
    assert by_id["CN_MARGIN_BALANCE_SSE_SZSE"]["priority"] == "P1"
    assert by_id["CN_MARGIN_BALANCE_SSE_SZSE"]["source_codes"] == ["SSE_SZSE_MARGIN_BALANCE"]
    assert by_id["CN_USDCNY_ECB_REFERENCE_CROSS"]["source_codes"] == [
        "ECB_EUR_REFERENCE_CNY_USD_CROSS_V0001"
    ]
    assert not set(by_id).intersection(
        {
            "CN_MARGIN_BALANCE",
            "CN_USDCNH_FXCM",
            "CN_USDCNH_TMA_SPOT_RATE",
            "COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT",
            "LBMA_GOLD_PRICE_PM_USD_OZT",
        }
    )
    assert manifest["core_metrics"] == {
        "stock": "CN_EQUITY_CORE_000985",
        "bond": "CN_BOND_CORE_000012",
        "commodity": "CN_COMMODITY_CORE_NHII",
    }
    assert by_id["CN_EQUITY_CORE_000985"]["source_codes"] == ["000985.CSI"]
    assert by_id["CN_BOND_CORE_000012"]["source_codes"] == ["000012.SH"]
    assert by_id["CN_COMMODITY_CORE_NHII"]["source_codes"] == ["NHII.NH"]
    assert models.manifest("model-v0001") == previous


@pytest.mark.parametrize(
    ("metric_id", "replacement"),
    [
        ("CN_EQUITY_CORE_000985", "000300.SH"),
        ("CN_BOND_CORE_000012", "CNY030.CS"),
        ("CN_COMMODITY_CORE_NHII", "NHAI.NH"),
    ],
)
def test_cny030_migration_cannot_change_core_source_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], metric_id: str, replacement: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = optional_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == metric_id
    )
    # Keep the core mapping, role and certification; review the changed source afresh.
    definition["source_codes"] = [replacement]
    rebind(paths, request)
    before = ModelRepository(paths.database).list_versions()

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert f"certification_core_source_identity_mismatch:{metric_id}" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == before


def test_cny030_priority_change_cannot_change_its_source_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = optional_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == CNY030
    )
    definition["source_codes"] = ["CN_BOND_CORE_000012"]
    rebind(paths, request)
    before = ModelRepository(paths.database).list_versions()

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))

    assert failure.value.code == 2
    assert "certification_cny030_definition_mismatch" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name_cn", "renamed"),
        ("role", "core_barometer"),
        ("unit", "percent"),
        ("allowed_units", ["percent"]),
        ("dimensions", []),
        ("source_candidates", ["unreviewed"]),
        ("frequency", "monthly"),
        ("release_event_family", "different_release"),
        ("release_rule", "assumed_time"),
        ("release_timezone", "UTC"),
        ("certification_status", "certified"),
    ],
)
def test_cny030_migration_cannot_change_other_definition_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str, value: Any
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = optional_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == CNY030
    )
    definition[field] = value
    rebind(paths, request)
    with pytest.raises(SystemExit):
        submit(paths, save(paths, request))
    assert "certification_cny030_definition_mismatch" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("defect", "error"),
    [
        ("missing_declaration", "certification_catalog_scope_mismatch"),
        ("extra_demotion", "certification_metric_role_mismatch:CN_BOND_10Y_930916"),
        ("uncertified_p1", "certification_metric_not_certified:CN_MARGIN_BALANCE_SSE_SZSE"),
        ("uncertified_core", "certification_metric_not_certified:CN_BOND_CORE_000012"),
        ("core_mapping", "certification_core_roles_invalid"),
        ("margin_identity", "certification_margin_scope_identity_mismatch"),
        ("ecb_identity", "certification_ecb_identity_mismatch"),
        ("extra_priority_change", "certification_identity_migration_unsupported"),
        ("old_review", "certification_package_manifest_mismatch"),
    ],
)
def test_optional_cny030_keeps_other_admission_guards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], defect: str, error: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = optional_request(paths)
    manifest = request["manifest"]
    definitions = {d["metric_id"]: d for d in manifest["metric_definitions"]}
    if defect == "missing_declaration":
        manifest.pop("metric_identity_migration")
    elif defect == "extra_demotion":
        definitions["CN_BOND_10Y_930916"].update(
            priority="P2", certification_status="awaiting_source_certification"
        )
    elif defect == "uncertified_p1":
        definitions["CN_MARGIN_BALANCE_SSE_SZSE"]["certification_status"] = (
            "awaiting_source_certification"
        )
    elif defect == "uncertified_core":
        definitions["CN_BOND_CORE_000012"]["certification_status"] = "awaiting_source_certification"
    elif defect == "core_mapping":
        manifest["core_metrics"]["bond"] = CNY030
    elif defect == "margin_identity":
        definitions["CN_MARGIN_BALANCE_SSE_SZSE"]["source_codes"] = ["CN_MARGIN_BALANCE"]
    elif defect == "ecb_identity":
        definitions["CN_USDCNY_ECB_REFERENCE_CROSS"]["source_codes"] = ["USDCNH.FXCM"]
    elif defect == "extra_priority_change":
        manifest["metric_identity_migration"]["priority_changes"]["CN_MARGIN_BALANCE_SSE_SZSE"] = {
            "from": "P1",
            "to": "P2",
        }
    else:
        request["package_hashes"] = ecb_request(paths)["package_hashes"]
    if defect != "old_review":
        rebind(paths, request)
    before = ModelRepository(paths.database).list_versions()
    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))
    assert failure.value.code == 2
    assert error in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == before


def test_direct_priority_edit_without_migration_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = ecb_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == CNY030
    )
    definition.update(priority="P2", certification_status="awaiting_source_certification")
    rebind(paths, request)
    with pytest.raises(SystemExit):
        submit(paths, save(paths, request))
    assert f"certification_metric_role_mismatch:{CNY030}" in capsys.readouterr().err


def test_priority_migration_retains_old_registered_catalog_and_refuses_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    old_request = ecb_request(paths)
    old_hash = save(paths, old_request)
    submit(paths, old_hash)
    old_id = json.loads(capsys.readouterr().out)["model_version_id"]
    models = ModelRepository(paths.database)
    old_manifest = models.manifest(old_id)
    old_version = old_manifest["metric_catalog_version"]
    old_catalog = registered_definitions(paths.database, old_version)
    old_document = encode(old_manifest)

    request = optional_request(paths)
    request["manifest"]["metric_catalog_version"] = old_version
    for definition in request["manifest"]["metric_definitions"]:
        definition["definition_version"] = old_version
    rebind(paths, request)
    with pytest.raises(SystemExit):
        submit(paths, save(paths, request))
    assert "metric_catalog_version_is_immutable" in capsys.readouterr().err

    submit(paths, save(paths, optional_request(paths)))
    capsys.readouterr()
    assert encode(models.manifest(old_id)) == old_document
    assert registered_definitions(paths.database, old_version) == old_catalog
    assert (paths.artifacts / old_hash[:2] / old_hash).read_bytes() == encode(old_request)


@pytest.mark.parametrize("mode_name", ["PUBLIC", "SYSTEM"])
def test_uncertified_cny030_stays_a_visible_gap_and_is_not_selected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode_name: str
) -> None:
    from datetime import UTC, datetime

    from pring_cycle.context_projection import build_context_projection
    from pring_cycle.evidence import (
        AsOfMode,
        EvidenceRepository,
        EvidenceValueState,
        SourceClaimInput,
    )
    from pring_cycle.runs import RunRepository
    from pring_cycle.search_evidence import select_retrieval_input

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, optional_request(paths)))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    at = datetime(2026, 9, 22, 8, tzinfo=UTC)
    evidence = EvidenceRepository(paths.database)
    # A candidate value is allowed to be retained, but has no source certification.
    claim = evidence.append_source_claim(
        SourceClaimInput(
            metric_id=CNY030,
            definition_version=version,
            period_kind="business_day",
            period_start="2026-09-22",
            period_end="2026-09-22",
            dimensions={"source_code": "000012CNY030.CSI"},
            value=198.76,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference="synthetic:uncertified:cny030",
            release_event_id="synthetic:cny030:2026-09-22",
            release_at=at,
            public_available_at=at,
            fetched_at=at,
            available_at=at,
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )
    mode = AsOfMode[mode_name]
    assert evidence.trace(claim.observation_id, mode=mode, as_of=at).claims[0].value == 198.76
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-22",
        client_request_id="cny030-unreviewed",
        model_version_id=model_id,
        system_as_of=at,
        release_event_id="synthetic:cny030:2026-09-22",
        metric_ids=(CNY030,),
        period="2026-09-22",
    )
    selected = select_retrieval_input(paths, run, mode=mode)
    assert not selected.complete
    assert selected.selected_claim_ids == ()
    context = build_context_projection(
        evidence,
        as_of=at,
        as_of_mode=mode,
        model_manifest=manifest,
    )
    rows = context.macro["transmission"]["evidence"]
    (row,) = [r for r in rows if r["metric_id"] == CNY030]
    assert row["value"] is None
    assert row["status"] == "awaiting_source_certification"
    assert row["certification_status"] == "awaiting_source_certification"
    assert claim.claim_id in context.observation_version_ids
    assert claim.claim_id not in context.macro["model_input_observation_version_ids"]
