from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acceptance import REGRESSION_IDS
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import metric_definition
from pring_cycle.cutover import (
    CUTOVER_CONFIRMATION,
    build_cutover_manifest,
    cutover_status,
    record_direct_cutover,
)
from pring_cycle.domain import CoreAssetState
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.rehearsals import (
    _certified_p1_schema_samples,
    _dashboard_projection_visible,
    _smoke_scope_matches,
    required_real_smoke_kinds,
    run_fixture_recovery_rehearsal,
    store_source_smoke_result,
    verify_source_smoke_artifacts,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint, model_manifest_hashes
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES
from pring_cycle.storage import SCHEMA_HEAD


def _artifact(paths: RuntimePaths, document: dict[str, object], source: str) -> str:
    content = json.dumps(document, sort_keys=True).encode()
    return store_artifact(
        paths.database,
        paths.artifacts,
        content,
        media_type="application/json",
        source_reference=source,
    ).content_hash


def _source_smoke_artifacts(
    paths: RuntimePaths,
    *,
    target_business_date: str,
) -> tuple[str, ...]:
    hashes = []
    for kind in sorted(required_real_smoke_kinds()):
        result = _source_smoke_result(kind, target_business_date)
        if kind in {"core", "tushare-context"}:
            scope = {"target_business_date": target_business_date}
        elif kind == "eia":
            scope = {"start": target_business_date, "end": target_business_date}
        else:
            scope = {"period": str(result["period"])}
        stored = store_source_smoke_result(
            paths,
            kind=kind,
            result=result,
            target_scope=scope,
        )
        hashes.append(str(stored["artifact"]["hash"]))
    return tuple(hashes)


def _source_smoke_result(kind: str, target: str) -> dict[str, object]:
    digest = "1" * 64
    if kind == "core":
        return {
            "network_requests": 4,
            "results": [
                {
                    "api_name": api_name,
                    "first_business_date": "2026-01-02",
                    "last_business_date": target,
                    "metric_id": metric_id,
                    "normalized_hash": digest,
                    "observations": 160,
                    "source_code": source_code,
                    "status": "validated",
                }
                for metric_id, (api_name, source_code) in CORE_API_IDENTITIES.items()
            ],
            "status": "validated",
        }
    if kind == "eia":
        return {
            "endpoint": "https://api.eia.gov/v2/petroleum/pri/spt/data/",
            "first_business_date": target,
            "last_business_date": target,
            "network_requests": 1,
            "normalized_hash": digest,
            "observation_count": 2,
            "series_ids": ["RBRTE", "RWTC"],
            "status": "validated_candidate",
        }
    if kind == "lpr":
        return {
            "byte_count": 1024,
            "content_hash": digest,
            "final_url": "https://www.chinamoney.com.cn/chinese/rdgz/20260820/1.html",
            "http_status": 200,
            "network_requests": 1,
            "observation_count": 2,
            "period": target[:7],
            "release_at": "2026-08-20T09:00:00+08:00",
            "source_identity": "CHINAMONEY_LPR",
            "status": "validated",
            "tenors": ["1y", "5y_plus"],
        }
    if kind == "tushare-context":
        metrics = {
            "pmi": ["CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"],
            "prices": ["CN_CPI_HEADLINE", "CN_PPI"],
            "money": ["CN_M1_M2"],
            "social_financing": ["CN_SF_TOTAL"],
            "futures_warrants": ["CN_FUTURES_WARRANTS"],
            "gdp": ["CN_GDP"],
            "treasury_yields": ["UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"],
            "transmission": ["CN_DR007", "CN_SHIBOR_ON_1W_3M"],
        }
        return {
            "families": [
                {
                    "api_names": [f"fixture_{family}"],
                    "family": family,
                    "first_period": "2026-01-01",
                    "last_period": target,
                    "metric_ids": metric_ids,
                    "network_requests": 1,
                    "normalized_hash": digest,
                    "observation_count": len(metric_ids),
                    "status": "validated_candidate",
                }
                for family, metric_ids in metrics.items()
            ],
            "network_requests": len(metrics),
            "status": "validated_candidate",
            "target_business_date": target,
        }
    family = kind.removeprefix("official-context:")
    descriptor = OFFICIAL_CONTEXT_FAMILIES[family]
    period = (
        "2026-Q2"
        if family == "nbs_capacity_utilization"
        else target
        if family == "pbc_omo_notice"
        else "2026-08"
        if family == "pbc_rrr_notice"
        else "2026-07"
    )
    return {
        "byte_count": 1024,
        "content_hash": digest,
        "family": family,
        "final_url": f"https://{descriptor.host}/fixture/{family}.html",
        "http_status": 200,
        "first_period": target if family == "pbc_rrr_notice" else "2026-07-01",
        "last_period": target if family == "pbc_rrr_notice" else "2026-07-31",
        "metric_ids": list(descriptor.metric_ids),
        "network_requests": 1,
        "observation_count": len(descriptor.metric_ids),
        "period": period,
        "provider": descriptor.provider,
        "release_at": "2026-08-28T09:00:00+08:00",
        "status": "validated_candidate",
    }


def _real_rehearsal_artifact(
    paths: RuntimePaths,
    *,
    projection_set_id: str,
    source_smoke_hashes: tuple[str, ...],
) -> str:
    normalized_hash = "b" * 64
    return _artifact(
        paths,
        {
            "acceptance_only": True,
            "dashboard_projection_visible": True,
            "loopback_requests_during_validation": 3,
            "network_requests_during_validation": 0,
            "p0_assets": [
                "CN_BOND_CORE_000012",
                "CN_EQUITY_CORE_000985",
                "CN_COMMODITY_CORE_NHII",
            ],
            "p1_schema_samples": {"fixture": True},
            "projection_set_id": projection_set_id,
            "publication_history_written": False,
            "report_adapter": "deterministic_fixture",
            "report_status": "completed_degraded",
            "schema_version": "real-projection-rehearsal-v0001",
            "source_smoke_hashes": list(source_smoke_hashes),
            "source_smoke_kinds": sorted(required_real_smoke_kinds()),
            "status": "ok",
            "target_business_date": "2026-08-28",
            "normalized_result_hash": normalized_hash,
            **execution_fingerprint(paths, model_version_id="model-v0002"),
        },
        f"rehearsal:real-projection:{normalized_hash}",
    )


def test_fixture_rehearsal_is_acceptance_only_and_preserves_cutoffs(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    result = run_fixture_recovery_rehearsal(paths)

    assert result["status"] == "ok"
    assert result["acceptance_only"] is True
    assert result["publication_history_written"] is False
    assert result["interrupted_status"] == "interrupted"
    assert result["resumed_status"] == "queued"
    assert result["cutoffs_preserved"] is True


def test_source_smoke_scope_accepts_daily_and_quarterly_official_periods() -> None:
    assert _smoke_scope_matches(
        {"period": "2026-08-28"},
        "2026-08-28",
        kind="official-context:pbc_omo_notice",
    )
    assert _smoke_scope_matches(
        {"period": "2026-Q2"},
        "2026-08-28",
        kind="official-context:nbs_capacity_utilization",
    )
    assert _smoke_scope_matches(
        {"period": "2025-09"},
        "2026-08-28",
        kind="official-context:pbc_rrr_notice",
    )
    assert _smoke_scope_matches(
        {"period": "2025-05"},
        "2026-08-28",
        kind="official-context:pbc_rrr_notice",
    )


def test_p2_eia_smoke_is_optional_for_real_rehearsal(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    assert "eia" not in required_real_smoke_kinds()
    stored = store_source_smoke_result(
        paths,
        kind="eia",
        result=_source_smoke_result("eia", "2026-08-28"),
        target_scope={"start": "2026-08-28", "end": "2026-08-28"},
    )

    assert stored["smoke_kind"] == "eia"


def test_content_poor_source_smoke_artifact_is_rejected(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    stored = store_source_smoke_result(
        paths,
        kind="core",
        result={"network_requests": 1, "status": "validated"},
        target_scope={"target_business_date": "2026-08-28"},
    )

    with pytest.raises(ValueError, match="source_smoke_artifact_shape_invalid"):
        verify_source_smoke_artifacts(
            paths,
            (str(stored["artifact"]["hash"]),),
            target_business_date="2026-08-28",
        )


def test_source_smoke_artifact_is_rejected_after_execution_fingerprint_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    stored = store_source_smoke_result(
        paths,
        kind="core",
        result=_source_smoke_result("core", "2026-08-28"),
        target_scope={"target_business_date": "2026-08-28"},
    )
    stale = execution_fingerprint(paths)
    stale["code_hash"] = "0" * 64
    monkeypatch.setattr(
        "pring_cycle.rehearsals.execution_fingerprint",
        lambda _paths: stale,
    )

    with pytest.raises(ValueError, match="source_smoke_artifact_provenance_invalid"):
        verify_source_smoke_artifacts(
            paths,
            (str(stored["artifact"]["hash"]),),
            target_business_date="2026-08-28",
        )


def test_real_rehearsal_requires_each_certified_p1_schema_family_in_projection(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    samples = _certified_p1_schema_samples(
        paths,
        as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        projection_evidence_ids=set(),
    )

    assert len(samples) == 16
    assert set(samples.values()) == {False}
    assert {
        "pbc_omo_notice",
        "nbs_industrial_finance",
        "tushare_pmi",
        "tushare_transmission",
    } <= set(samples)


def test_real_rehearsal_rejects_conflicted_or_unselected_certified_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    monkeypatch.setattr(
        "pring_cycle.evidence.metric_definition",
        lambda metric_id, *, definition_version="metric-catalog-v0002": replace(
            metric_definition(metric_id, definition_version=definition_version),
            certification_status="certified",
        ),
    )
    repository = EvidenceRepository(paths.database)
    claims = tuple(
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_RRR_EVENT",
                definition_version="metric-catalog-v0002",
                period_kind="event",
                period_start="2026-08-15",
                period_end="2026-08-15",
                dimensions={"scope": "all", "measure": "rrr_change"},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percentage_points",
                provider=provider,
                source_reference=f"fixture:{release_event_id}",
                release_event_id=release_event_id,
                release_at=datetime(2026, 8, 15, 1, tzinfo=UTC),
                public_available_at=datetime(2026, 8, 15, 1, tzinfo=UTC),
                fetched_at=datetime(2026, 8, 15, 2, tzinfo=UTC),
                available_at=datetime(2026, 8, 15, 2, tzinfo=UTC),
                certification_status="certified",
                quality_status="validated",
            )
        )
        for provider, release_event_id, value in (
            ("中国人民银行", "pbc-rrr", -0.5),
            ("certified-secondary", "secondary-rrr", -0.25),
        )
    )

    samples = _certified_p1_schema_samples(
        paths,
        as_of=datetime(2026, 8, 16, tzinfo=UTC),
        projection_evidence_ids={claim.claim_id for claim in claims},
    )

    assert samples["pbc_rrr_notice"] is False


def test_cutover_has_no_force_path_and_requires_the_exact_confirmation(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=160,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    projections = P0ProjectionService(ProjectionSetRepository(paths.database))
    projections.publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    acceptance_hash = _artifact(
        paths,
        {
            "schema_version": "v1-acceptance-v0001",
            "status": "ok",
            "normalized_result_hash": "a" * 64,
            "performance_gates": {"all": {"passed": True}},
            "regressions": {item: {"passed": True} for item in REGRESSION_IDS},
            **execution_fingerprint(paths),
            "model_manifest_hashes": model_manifest_hashes(paths),
        },
        f"acceptance:{'a' * 64}",
    )
    fixture_hash = str(run_fixture_recovery_rehearsal(paths)["artifact"]["hash"])
    minimal_real_hash = _artifact(
        paths,
        {
            "schema_version": "real-projection-rehearsal-v0001",
            "status": "ok",
            "normalized_result_hash": "b" * 64,
        },
        f"rehearsal:real-projection:{'b' * 64}",
    )
    v1_manifest = build_cutover_manifest(
        paths,
        acceptance_hash=acceptance_hash,
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=minimal_real_hash,
        legacy_system_read_only_stopped=True,
    )
    assert v1_manifest["status"] == "blocked"
    assert v1_manifest["checks"]["model_catalog_current"] is False
    assert v1_manifest["checks"]["real_rehearsal"] is False
    assert v1_manifest["metric_catalog_version"] == "metric-catalog-v0001"

    models.record_acceptance("model-v0002", CALIBRATION_BASELINE)
    models.record_replay(
        "model-v0002",
        compared_with="model-v0001",
        requested_start="2018-06-01",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
    )
    models.activate("model-v0002", explicitly_approved=True)
    v2_projection = projections.publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, 1, tzinfo=UTC),
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=None,
        model_version_id="model-v0002",
    )
    assert v2_projection.projection_set_id is not None
    smoke_hashes = _source_smoke_artifacts(
        paths,
        target_business_date="2026-08-28",
    )
    real_hash = _real_rehearsal_artifact(
        paths,
        projection_set_id=v2_projection.projection_set_id,
        source_smoke_hashes=smoke_hashes,
    )
    manifest = build_cutover_manifest(
        paths,
        acceptance_hash=acceptance_hash,
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=real_hash,
        legacy_system_read_only_stopped=True,
    )
    assert manifest["status"] == "ready"
    assert manifest["checks"]["model_catalog_current"] is True
    assert manifest["metric_catalog_version"] == "metric-catalog-v0002"
    assert manifest["database_revision"] == SCHEMA_HEAD

    stale_acceptance_hash = _artifact(
        paths,
        {
            "schema_version": "v1-acceptance-v0001",
            "status": "ok",
            "normalized_result_hash": "d" * 64,
            "performance_gates": {"all": {"passed": True}},
            "regressions": {item: {"passed": True} for item in REGRESSION_IDS},
            **execution_fingerprint(paths),
            "code_hash": "0" * 64,
            "model_manifest_hashes": model_manifest_hashes(paths),
        },
        f"acceptance:{'d' * 64}",
    )
    stale_manifest = build_cutover_manifest(
        paths,
        acceptance_hash=stale_acceptance_hash,
        fixture_rehearsal_hash=fixture_hash,
        real_rehearsal_hash=real_hash,
        legacy_system_read_only_stopped=True,
    )
    assert stale_manifest["status"] == "blocked"
    assert stale_manifest["checks"]["acceptance_fresh"] is False

    with pytest.raises(ValueError, match="explicit_direct_cutover_confirmation_required"):
        record_direct_cutover(
            paths,
            manifest_hash=str(manifest["artifact"]["hash"]),
            confirmation="yes",
        )

    recorded = record_direct_cutover(
        paths,
        manifest_hash=str(manifest["artifact"]["hash"]),
        confirmation=CUTOVER_CONFIRMATION,
    )
    assert recorded.supported_path == "pring-v1-only"
    assert cutover_status(paths) == recorded


def test_real_rehearsal_dashboard_probe_reads_shell_and_exact_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection_set_id = "projection-visible-fixture"
    responses = {
        "http://127.0.0.1:8877/": (
            b"<main data-pring-meaningful-content='true'>"
            + projection_set_id.encode()
            + b"</main>"
        ),
        "http://127.0.0.1:8877/api/v1/projections/current": json.dumps(
            {"envelope": {"projection_set_id": projection_set_id}}
        ).encode(),
        "http://127.0.0.1:8877/_dash-layout": json.dumps(
            {
                "namespace": "dash_html_components",
                "props": {
                    "className": "dashboard-app",
                    "children": [
                        *(
                            {
                                "namespace": "dash_html_components",
                                "props": {"id": identifier},
                                "type": "Div",
                            }
                            for identifier in (
                                "dashboard-location",
                                "runtime-poll",
                                "theme-state",
                                "theme-toggle",
                                "page-content",
                                "command-feedback",
                                "nav-home",
                                "nav-core-assets",
                                "nav-macro",
                                "nav-inventory",
                                "nav-stage-history",
                                "nav-release-calendar",
                                "nav-reports",
                                "nav-runs",
                            )
                        ),
                        projection_set_id,
                    ],
                },
                "type": "Div",
            }
        ).encode(),
    }

    class FixtureResponse:
        status = 200

        def __init__(self, url: str, content: bytes) -> None:
            self._url = url
            self._content = content

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return self._url

        def read(self, _limit: int) -> bytes:
            return self._content

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> FixtureResponse:
            assert timeout == 5
            url = str(request.full_url)
            return FixtureResponse(url, responses[url])

    monkeypatch.setattr(
        "pring_cycle.rehearsals.build_opener",
        lambda *_handlers: FixtureOpener(),
    )

    assert _dashboard_projection_visible(
        8877,
        projection_set_id=projection_set_id,
    )


def test_cutover_rejects_untrusted_artifact_provenance(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    forged = _artifact(
        paths,
        {
            "schema_version": "v1-acceptance-v0001",
            "status": "ok",
            "normalized_result_hash": "c" * 64,
        },
        "test:forged-acceptance",
    )

    with pytest.raises(ValueError, match="artifact_provenance_invalid"):
        build_cutover_manifest(
            paths,
            acceptance_hash=forged,
            fixture_rehearsal_hash=forged,
            real_rehearsal_hash=forged,
            legacy_system_read_only_stopped=True,
        )
