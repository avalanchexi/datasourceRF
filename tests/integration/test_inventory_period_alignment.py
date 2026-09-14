from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import analytical_model_v0002_manifest


@pytest.mark.parametrize("ppi_month,inventory_month", [("07", "07"), ("06", "07"), ("07", "06")])
def test_inventory_approximation_does_not_combine_different_months(
    tmp_path: Path, ppi_month: str, inventory_month: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    for metric_id, dimensions, value, unit in (
        (
            "CN_FINISHED_GOODS_INVENTORY",
            {"measure": "nominal_end_level"},
            105.0,
            "hundred_million_cny",
        ),
        ("CN_PPI", {"measure": "yoy", "category": "headline"}, 5.0, "percent"),
    ):
        month = ppi_month if metric_id == "CN_PPI" else inventory_month
        end = f"2026-{month}-" + ("30" if month == "06" else "31")
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version="metric-catalog-v0003",
                period_kind="month",
                period_start=f"2026-{month}-01",
                period_end=end,
                dimensions=dimensions,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=unit,
                provider="isolated_fixture",
                source_reference=f"fixture:{metric_id}",
                release_event_id=f"fixture:{metric_id}:{end}",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(definition) for definition in metric_catalog_v0003()]
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC,
        persist_derived=False,
    )
    proxy = cast(dict[str, object], context.inventory["real_inventory_approximation"])
    if ppi_month == inventory_month:
        # Independent worked example: a nominal 105 at +5% prices adjusts to 100.
        assert proxy["value"] == 100.0
        assert proxy["status"] == "available"
    else:
        assert proxy["value"] is None
        assert proxy["status"] == "period_mismatch"
        assert "derived_observation_id" not in proxy
        nominal = cast(dict[str, object], proxy["nominal_inventory"])
        ppi = cast(dict[str, object], proxy["ppi_input"])
        assert nominal["period"] != ppi["period"]
        assert nominal["selected_claim_id"]
        assert ppi["selected_claim_id"]


@pytest.mark.parametrize(
    ("formula_version", "ppi_months", "inventory_month", "expected"),
    [
        ("inventory-ppi-common-month-v0002", ("06", "07"), "06", ("available", 100.0, "06")),
        ("inventory-ppi-common-month-v0002", ("06",), "07", ("period_mismatch", None, "06")),
        ("inventory-ppi-v0001", ("06", "07"), "06", ("period_mismatch", None, "07")),
    ],
)
def test_common_month_inventory_uses_the_visible_ppi_for_the_inventory_period(
    tmp_path: Path,
    formula_version: str,
    ppi_months: tuple[str, ...],
    inventory_month: str,
    expected: tuple[str, float | None, str],
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    # PPI for a month is released before that month's finished-goods inventory.
    inputs = [
        ("CN_PPI", {"measure": "yoy", "category": "headline"}, value, "percent", month)
        for month, value in zip(ppi_months, (5.0, 9.0), strict=False)
    ]
    inputs.append(
        (
            "CN_FINISHED_GOODS_INVENTORY",
            {"measure": "nominal_end_level"},
            105.0,
            "hundred_million_cny",
            inventory_month,
        )
    )
    for metric_id, dimensions, value, unit, month in inputs:
        end = f"2026-{month}-" + ("30" if month == "06" else "31")
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version="metric-catalog-v0003",
                period_kind="month",
                period_start=f"2026-{month}-01",
                period_end=end,
                dimensions=dimensions,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=unit,
                provider="isolated_fixture",
                source_reference=f"fixture:{metric_id}:{month}",
                release_event_id=f"fixture:{metric_id}:{end}",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(definition) for definition in metric_catalog_v0003()]
    manifest["derived_formula_versions"] = {
        **manifest["derived_formula_versions"],
        "real_inventory_approximation": formula_version,
    }
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC,
        persist_derived=False,
    )
    proxy = cast(dict[str, object], context.inventory["real_inventory_approximation"])
    status, value, ppi_month = expected
    assert (proxy["status"], proxy["value"]) == (status, value)
    assert proxy["formula_version"] == formula_version
    ppi = cast(dict[str, object], proxy["ppi_input"])
    assert str(ppi["period"]).startswith(f"2026-{ppi_month}-")
    if status == "available":
        # Independent worked example: June nominal 105 at the June +5% PPI adjusts to 100.
        nominal = cast(dict[str, object], proxy["nominal_inventory"])
        assert proxy["input_observation_version_ids"] == sorted(
            [nominal["selected_claim_id"], ppi["selected_claim_id"]]
        )


@pytest.mark.parametrize("damage", [None, "raw", "normalized"])
def test_registered_common_month_inventory_rechecks_the_aligned_ppi_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damage: str | None
) -> None:
    import hashlib
    import json

    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.models import ModelRepository
    from pring_cycle.official_context import ingest_official_context_document
    from pring_cycle.runtime import RuntimePaths, initialize_runtime
    from tests.models.test_candidate_admission import (
        bind_synthetic_review,
        prepared_request,
        save,
        submit,
    )

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["derived_formula_versions"]["real_inventory_approximation"] = (
        "inventory-ppi-common-month-v0002"
    )
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model = ModelRepository(paths.database).manifest(
        json.loads(capsys.readouterr().out)["model_version_id"]
    )
    archive = Path(__file__).parents[2] / (
        ".scratch/pring-data-acquisition-repair/evidence-a18-import-20260909"
    )
    fetched = datetime(2026, 8, 10, tzinfo=UTC)
    # Real archived NBS releases: June PPI (Jul 9), July PPI (Aug 9), June inventory (Jul 27).
    for family, period, digest, url in (
        (
            "nbs_ppi",
            "2026-06",
            "abc018326fbd23f3194c6ba3c6e82d6d14b5689ea1ccd3770009968fea583c98",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1964083.html",
        ),
        (
            "nbs_ppi",
            "2026-07",
            "b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965007.html",
        ),
        (
            "nbs_industrial_finance",
            "2026-06",
            "15c5f2247073e3e0b6c2c35ca4281885aa929b3b9ceb0bd7b8fd8275cbba5047",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260727_1964194.html",
        ),
    ):
        raw = (archive / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        ingest_official_context_document(
            paths,
            raw,
            family=family,
            source_url=url,
            expected_period=period,
            fetched_at=fetched,
            clock=lambda: fetched,
            definition_version=model["metric_catalog_version"],
        )
    june_ppi = next(
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.raw_hash == "abc018326fbd23f3194c6ba3c6e82d6d14b5689ea1ccd3770009968fea583c98"
    )
    evidence = EvidenceRepository(paths.database)

    def proxy() -> dict[str, object]:
        # After July PPI, before July inventory: the common month is June.
        context = build_context_projection(
            evidence,
            as_of=datetime(2026, 8, 15, 12, tzinfo=UTC),
            model_manifest=model,
            as_of_mode=AsOfMode.PUBLIC,
            persist_derived=False,
        )
        return cast(dict[str, object], context.inventory["real_inventory_approximation"])

    available = proxy()
    assert available["status"] == "available"
    # Independent literals: June-end finished goods 7.11 trillion yuan, June PPI +4.1% YoY.
    assert available["value"] == pytest.approx(71100 / 1.041)
    assert str(cast(dict[str, object], available["ppi_input"])["period"]) == "2026-06-30"
    if damage is None:
        return
    digest = june_ppi.raw_hash if damage == "raw" else june_ppi.normalized_hash
    assert digest is not None
    artifact = paths.artifacts / digest[:2] / digest
    original = artifact.read_bytes()
    artifact.write_bytes(b"damaged aligned PPI original")
    damaged = proxy()
    assert damaged["status"] != "available"
    assert damaged["value"] is None and "derived_observation_id" not in damaged
    artifact.write_bytes(original)
    assert proxy()["status"] == "available"
