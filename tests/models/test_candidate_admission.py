from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.candidate_admission import admit_source_certified_candidate
from pring_cycle.cli import main
from pring_cycle.context_projection import build_context_projection
from pring_cycle.domain import CoreAssetState
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_120d_model_v0011_manifest,
)
from pring_cycle.official_context import ingest_official_context_document
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint
from pring_cycle.search_evidence import select_retrieval_input
from pring_cycle.tushare_context import ContextScalar, TushareContextAdapter, ingest_context_scalars


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


def cpi_document() -> bytes:
    # Compact synthetic rendering of the six independently audited July literals.
    # Actual original: a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49.
    return """
    <html><body><h1>2026年7月份居民消费价格</h1>
    <p>发布时间：2026-08-09 09:30</p><table>
    <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
    <tr><td>居民消费价格</td><td>-0.1</td><td>0.5</td><td>0.9</td></tr>
    <tr><td>不包括食品和能源</td><td>0.3</td><td>0.9</td><td>1.1</td></tr>
    </table></body></html>
    """.encode()


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("public_known", [False, True])
def test_registered_interbank_acquisition_preserves_public_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], public_known: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    # Synthetic TuShare transport, with independent CFETS 2026-08-28 values.
    # The CFETS original is not a historical TuShare delivery receipt.
    responses = {
        "repo_daily": {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
                "items": [["DR007.IB", "20260828", "DR007", 1.3859]],
            },
        },
        "shibor": {
            "code": 0,
            "data": {
                "fields": ["date", "on", "1w", "3m"],
                "items": [["20260828", 1.339, 1.387, 1.43]],
            },
        },
    }

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(responses[payload["api_name"]])

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # This known publication instant tests software behavior only. The saved
    # historical CFETS response does not prove the day's first publication.
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC) if public_known else None

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.transmission(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        if not public_known:
            assert all(s.release_at is None and s.public_available_at is None for s in scalars)
            return scalars
        return tuple(
            replace(scalar, release_at=public_at, public_available_at=public_at)
            for scalar in scalars
        )

    imported = adapter.acquire_scalars(
        paths,
        retrieve,
        definition_version=version,
    )
    assert len(imported.claim_ids) == 4
    assert adapter.network_requests == 2
    now = datetime.now(UTC)
    repository = EvidenceRepository(paths.database)
    expected = {
        "CN_DR007": {None: 1.3859},
        "CN_SHIBOR_ON_1W_3M": {
            "overnight": 1.339,
            "1w": 1.387,
            "3m": 1.43,
        },
    }
    for metric, values in expected.items():
        points = repository.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
        )
        assert {p.dimensions.get("tenor"): p.selected_value for p in points} == values
        public_points = repository.metric_series(
            metric, mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
        )
        assert {p.dimensions.get("tenor"): p.selected_value for p in public_points} == (
            values if public_known else {}
        )
        assert not repository.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 7, tzinfo=UTC),
            definition_version=version,
        )
        for point in points:
            trace = repository.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=now)
            claim = next(c for c in trace.claims if c.claim_id == point.selected_claim_id)
            assert claim.unit == "percent"
            assert claim.provider == "tushare"
            assert claim.public_available_at == public_at
            assert trace.acquisition_status == "linked"
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(receipts.history()) == 2
    for receipt in receipts.history():
        assert receipt.state == "validated"
        assert (
            json.loads(receipts.read_content(receipt.acquisition_id, "raw"))
            == responses[receipt.api_name]
        )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="interbank-unknown-public",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:interbank",
        metric_ids=tuple(expected),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete is public_known
    assert set(selection.selected_claim_ids) == (set(imported.claim_ids) if public_known else set())
    assert len(selection.missing_members) == (0 if public_known else 4)
    context = build_context_projection(
        repository, as_of=now, target_business_date="2026-08-28", model_manifest=request["manifest"]
    )
    assert set(imported.claim_ids).intersection(context.observation_version_ids) == (
        set(imported.claim_ids) if public_known else set()
    )


@pytest.mark.parametrize(
    "fault",
    [
        "provider",
        "tenor",
        "unit",
        "period_kind",
        "period_bounds",
        "invalid_date",
        "noncanonical_date",
    ],
)
def test_registered_interbank_rejects_wrong_source_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 28, 8, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_SHIBOR_ON_1W_3M",
        definition_version=request["manifest"]["metric_catalog_version"],
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={"tenor": "3m"},
        value=1.43,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percent",
        provider="tushare",
        source_reference="synthetic:shibor-identity",
        release_event_id="synthetic:shibor",
        release_at=now,
        public_available_at=now,
        fetched_at=now,
        available_at=now,
        certification_status="certified",
        quality_status="validated",
    )
    if fault == "provider":
        claim = replace(claim, provider="中国货币网")
    elif fault == "tenor":
        claim = replace(claim, dimensions={"tenor": "1m"})
    elif fault == "unit":
        claim = replace(claim, unit="basis_points")
    elif fault == "period_kind":
        claim = replace(claim, period_kind="month")
    elif fault == "period_bounds":
        claim = replace(claim, period_start="2026-08-27")
    else:
        invalid_date = "2026-08-99" if fault == "invalid_date" else "2026-8-28"
        claim = replace(claim, period_start=invalid_date, period_end=invalid_date)
    repository = EvidenceRepository(paths.database)
    with pytest.raises(
        ValueError,
        match=(
            "registered_interbank_source_identity_mismatch|registered_interbank_source_period_mismatch"
            "|evidence_unit_mismatch"
        ),
    ):
        repository.append_source_claim(claim)
    assert not repository.metric_series(
        claim.metric_id,
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=claim.definition_version,
    )


@pytest.mark.parametrize("fault", ["dr_field", "dr_api", "shibor_field"])
def test_registered_interbank_rejects_wrong_delivery_field_atomically(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 29, tzinfo=UTC)
    dr = ContextScalar(
        metric_id="CN_DR007",
        api_name="repo_daily",
        source_field="weight",
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={},
        value=1.3859,
        unit="percent",
    )
    shibor = replace(
        dr,
        metric_id="CN_SHIBOR_ON_1W_3M",
        api_name="shibor",
        source_field="3m",
        dimensions={"tenor": "3m"},
        value=1.43,
    )
    if fault == "dr_field":
        dr = replace(dr, source_field="close")
    elif fault == "dr_api":
        dr = replace(dr, api_name="shibor")
    else:
        shibor = replace(shibor, source_field="1m")
    with pytest.raises(ValueError, match="registered_interbank_source_field_mismatch"):
        ingest_context_scalars(
            paths,
            (dr, shibor),
            fetched_at=now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )
    repository = EvidenceRepository(paths.database)
    for metric in ("CN_DR007", "CN_SHIBOR_ON_1W_3M"):
        assert not repository.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )


def test_registered_pmi_original_reaches_selection_and_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    digest = "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6"
    content = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    now = datetime(2026, 8, 1, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        content,
        family="nbs_pmi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
        expected_period="2026-07",
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    # Independently audited July table cells, not parser-derived expectations.
    expected = {
        "CN_PMI_ACTIVITY": {
            "manufacturing": 49.2,
            "production": 49.9,
            "new_orders": 48.5,
            "purchase_volume": 49.4,
        },
        "CN_PMI_INVENTORY": {"raw_materials": 48.3, "finished_goods": 48.6},
        "CN_PMI_PRICES": {"purchase_prices": 53.2, "output_prices": 47.8},
    }
    repository = EvidenceRepository(paths.database)
    for metric, values in expected.items():
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            points = repository.metric_series(
                metric, mode=mode, as_of=now, definition_version=version
            )
            assert {p.dimensions["series"]: p.selected_value for p in points} == values
            assert all(p.dimensions["measure"] == "level" for p in points)
            assert all(
                c.unit == "diffusion_index_points"
                for p in points
                for c in p.claims
                if c.claim_id == p.selected_claim_id
            )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-pmi",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=imported.release_event_id,
        metric_ids=tuple(expected),
        period="2026-07",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(imported.claim_ids)
    context = build_context_projection(repository, as_of=now, model_manifest=manifest)
    assert set(imported.claim_ids) <= set(context.observation_version_ids)


@pytest.mark.parametrize(
    ("family", "digest", "url", "period", "count", "anchors"),
    [
        (
            "nbs_ppi",
            "b323261248c08ecba00a96cf4401654896fd8a5709ce9bf81c2e38f7d5fbef09",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965007.html",
            "2026-07",
            9,
            {"CN_PPI": ({"category": "headline", "measure": "yoy"}, 3.5, "percent")},
        ),
        (
            "nbs_industrial_value_added",
            "d8a9cc4305ea657b6d9eeecc8633afcf6934bc05f7da72c9969c89e465833609",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html",
            "2026-07",
            3,
            {"CN_INDUSTRIAL_VA": ({"measure": "current_month_real_yoy"}, 4.5, "percent")},
        ),
        (
            "nbs_industrial_finance",
            "28388ca9b78a83ea1fe39c0b3d943ad982d34c7dd4e26fee96d78a18b7a7f986",
            "https://www.stats.gov.cn/sj/zxfb/202608/t20260827_1965126.html",
            "2026-07",
            10,
            {
                "CN_INDUSTRIAL_FINANCE": (
                    {"item": "revenue", "measure": "ytd_level"},
                    809230.7,
                    "hundred_million_cny",
                ),
                "CN_FINISHED_GOODS_INVENTORY": (
                    {"measure": "nominal_end_level"},
                    72700,
                    "hundred_million_cny",
                ),
                "CN_INVENTORY_TURNOVER": ({"measure": "official_yoy_change"}, 0.6, "days"),
            },
        ),
        (
            "nbs_capacity_utilization",
            "8d1eadceb1259df2a86975d3565de90488c8d9b0f14992ec14fd7f8f49ab70e8",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260715_1964130.html",
            "2026-Q2",
            3,
            {
                "CN_CAPACITY_UTILIZATION": (
                    {"industry": "all_industry", "measure": "yoy_change"},
                    -1.0,
                    "percentage_points",
                )
            },
        ),
        (
            "pbc_money",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            4,
            {
                "CN_M1_M2": (
                    {"aggregate": "m1", "measure": "balance"},
                    1154600,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_social_financing",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            27,
            {
                "CN_SF_TOTAL": ({"measure": "stock_end"}, 4632700, "hundred_million_cny"),
                "CN_SF_COMPONENTS": (
                    {"component": "government_bonds", "measure": "ytd_increment"},
                    77600,
                    "hundred_million_cny",
                ),
            },
        ),
        (
            "pbc_loan_structure",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            "2026-07",
            9,
            {
                "CN_LOAN_STRUCTURE": (
                    {"borrower": "enterprise", "tenor": "long_term", "measure": "ytd_increment"},
                    53200,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_tool_liquidity_monthly",
            "10ed3fb5822bcc74dd429325d8196b7bbda9ed2e732eaa957914cbe95d2452f0",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/2026080416515912098/index.html",
            "2026-07",
            24,
            {
                "CN_TOOL_LIQUIDITY_MONTHLY": (
                    {"tool": "7天期逆回购", "measure": "net_injection"},
                    -2495,
                    "hundred_million_cny",
                )
            },
        ),
        (
            "pbc_omo_notice",
            "ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html",
            "2026-08-28",
            2,
            {
                "CN_OMO_7D_AMOUNT": ({"measure": "injection"}, 200, "hundred_million_cny"),
                "CN_OMO_7D_RATE": ({}, 1.4, "percent"),
            },
        ),
    ],
    ids=[
        "ppi",
        "industrial-va",
        "industrial-finance",
        "capacity-q2",
        "money",
        "social-financing",
        "loans",
        "tools",
        "omo",
    ],
)
def test_registered_official_original_reaches_selection_and_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    family: str,
    digest: str,
    url: str,
    period: str,
    count: int,
    anchors: dict[str, tuple[dict[str, str], float, str]],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    now = datetime(2026, 8, 29, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family=family,
        source_url=url,
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    assert len(imported.claim_ids) == count
    repository = EvidenceRepository(paths.database)
    for metric, (dimensions, value, unit) in anchors.items():
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            points = repository.metric_series(
                metric, mode=mode, as_of=now, definition_version=version
            )
            (point,) = (p for p in points if p.dimensions == dimensions)
            assert point.selected_value == value
            (claim,) = (c for c in point.claims if c.claim_id == point.selected_claim_id)
            assert claim.unit == unit
            assert claim.source_reference == f"{url}#sha256={digest}"
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-official",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=imported.release_event_id,
        metric_ids=tuple(anchors),
        period=period,
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete, selection.missing_members
    assert set(selection.selected_claim_ids) <= set(imported.claim_ids)
    context = build_context_projection(repository, as_of=now, model_manifest=manifest)
    assert set(imported.claim_ids) <= set(context.observation_version_ids)


@pytest.mark.parametrize(
    ("family", "digest", "url", "period", "metric", "values"),
    [
        (
            "nbs_ppi",
            "e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943",
            "https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962587.html",
            "2026-01",
            "CN_PPI",
            {"mom", "yoy"},
        ),
        (
            "nbs_industrial_value_added",
            "2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e",
            "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html",
            "2026-02",
            "CN_INDUSTRIAL_VA",
            {"mom_seasonally_adjusted", "ytd_real_yoy"},
        ),
    ],
    ids=["january-ppi", "february-industrial-va"],
)
def test_registered_official_legitimate_missing_columns_are_complete(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    family: str,
    digest: str,
    url: str,
    period: str,
    metric: str,
    values: set[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-edge"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    now = datetime(2026, 8, 29, tzinfo=UTC)
    result = ingest_official_context_document(
        paths,
        raw,
        family=family,
        source_url=url,
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    points = EvidenceRepository(paths.database).metric_series(
        metric,
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=version,
    )
    assert {p.dimensions["measure"] for p in points} == values
    if metric == "CN_INDUSTRIAL_VA":
        assert {p.dimensions["measure"]: p.selected_value for p in points} == {
            "mom_seasonally_adjusted": 0.83,
            "ytd_real_yoy": 6.3,
        }
    else:
        assert len(points) == 6
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="missing-columns",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=result.release_event_id,
        metric_ids=(metric,),
        period=period,
    )
    assert select_retrieval_input(paths, run).complete


@pytest.mark.parametrize("fault", ["provider", "member", "unit", "period_kind", "period_bounds"])
def test_registered_official_claim_rejects_wrong_member_identity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fault: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 29, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_INVENTORY_TURNOVER",
        definition_version=request["manifest"]["metric_catalog_version"],
        period_kind="year_to_month",
        period_start="2026-01-01",
        period_end="2026-07-31",
        dimensions={"measure": "official_yoy_change"},
        value=0.6,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="days",
        provider="国家统计局",
        source_reference="synthetic:turnover-identity",
        release_event_id="synthetic:turnover",
        release_at=now,
        public_available_at=now,
        fetched_at=now,
        available_at=now,
        certification_status="certified",
        quality_status="validated",
    )
    changes: dict[str, dict[str, Any]] = {
        "provider": {"provider": "TuShare"},
        "member": {"dimensions": {"measure": "yoy"}},
        "unit": {"unit": "percent"},
        "period_kind": {"period_kind": "month"},
        "period_bounds": {"period_start": "2026-07-01"},
    }
    with pytest.raises(ValueError, match="registered_official_source_(identity|period)_mismatch"):
        EvidenceRepository(paths.database).append_source_claim(replace(claim, **changes[fault]))


@pytest.mark.parametrize(
    ("latest_invalid", "event_age"), [(False, 1), (True, 1), (False, 11), (False, 371)]
)
def test_registered_omo_zero_day_selects_prior_rate_event_without_fabricating_a_claim(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    latest_invalid: bool,
    event_age: int,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    now = datetime(2026, 6, 3, 2, tzinfo=UTC)
    digest = "632b1709e4c27aac9b2fd9135394f11efb530321c8a1960577f8a0a562ec65b0"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-edge"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    imported = ingest_official_context_document(
        paths,
        raw,
        family="pbc_omo_notice",
        source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026060308521286488/index.html",
        expected_period="2026-06-03",
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    assert len(imported.claim_ids) == 1  # Actual zero amount, with no rate cell.
    repository = EvidenceRepository(paths.database)
    selected_event = None
    latest_day = {1: "2026-06-02", 11: "2026-05-23", 371: "2025-05-28"}[event_age]
    for day, value in (("2025-04-01", 1.4), (latest_day, 1.5), ("2026-06-04", 1.6)):
        # Synthetic events isolate selection semantics, without certifying historical rates.
        event = repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_OMO_7D_RATE",
                definition_version=version,
                period_kind="business_day",
                period_start=day,
                period_end=day,
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="中国人民银行",
                source_reference=f"synthetic:omo:{day}",
                release_event_id=f"synthetic:omo:{day}",
                release_at=now,
                public_available_at=now,
                fetched_at=now,
                available_at=now,
                certification_status="certified",
                quality_status="invalid" if latest_invalid and day == latest_day else "validated",
            )
        )
        if day == latest_day:
            selected_event = event.claim_id
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-06-03",
        client_request_id="zero-omo",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=imported.release_event_id,
        metric_ids=("CN_OMO_7D_AMOUNT", "CN_OMO_7D_RATE"),
        period="2026-06-03",
    )
    selection = select_retrieval_input(paths, run)
    eligible = not latest_invalid and event_age <= 370
    context = build_context_projection(
        repository,
        as_of=now,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
        target_business_date="2026-06-03",
    )
    inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(inputs, list)
    assert (selected_event in inputs) is eligible
    assert selection.complete is eligible
    if eligible:
        assert set(selection.selected_claim_ids) == {*imported.claim_ids, selected_event}
    assert not any(
        p.period_end == "2026-06-03"
        for p in repository.metric_series(
            "CN_OMO_7D_RATE",
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=version,
        )
    )


@pytest.mark.parametrize("missing_count", [1, 8])
def test_registered_social_components_require_all_eight_stock_growth_members(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing_count: int,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    now = datetime(2026, 8, 29, tzinfo=UTC)
    public_at = datetime(2026, 8, 14, 9, tzinfo=UTC)
    repository = EvidenceRepository(paths.database)
    components = (
        "renminbi_loans",
        "foreign_currency_loans_rmb",
        "entrusted_loans",
        "trust_loans",
        "undiscounted_bank_acceptances",
        "corporate_bonds",
        "government_bonds",
        "nonfinancial_enterprise_equity",
    )
    for index, component in enumerate(components):
        for measure in ("stock_end", "ytd_increment", "stock_yoy"):
            if measure == "stock_yoy" and index < missing_count:
                continue
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_SF_COMPONENTS",
                    definition_version=version,
                    period_kind="year_to_month" if measure == "ytd_increment" else "month",
                    period_start="2026-01-01" if measure == "ytd_increment" else "2026-07-01",
                    period_end="2026-07-31",
                    dimensions={"component": component, "measure": measure},
                    value=10,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent" if measure == "stock_yoy" else "hundred_million_cny",
                    provider="中国人民银行",
                    source_reference="synthetic:partial-sf",
                    release_event_id="synthetic:partial-sf",
                    release_at=public_at,
                    public_available_at=public_at,
                    fetched_at=now,
                    available_at=now,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="partial-sf",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:partial-sf",
        metric_ids=("CN_SF_COMPONENTS",),
        period="2026-07",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete
    assert len(selection.selected_claim_ids) == 24 - missing_count
    assert len(selection.missing_members) == missing_count
    assert all('"measure": "stock_yoy"' in missing for missing in selection.missing_members)


def test_registered_social_financing_completes_only_after_both_original_announcements(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    selected_counts = []
    receipts = []
    for index, (digest, code) in enumerate(
        (
            (
                "42312d6054e2df029dfeeba68c7c60fc4bc45934cb72bdd739c143e1c9f02243",
                "29d3365dfab04cc0a1e50bf0df41bae4",
            ),
            (
                "d0ae83ced9ad510a057a853f51b185e729ed81c9cd5e958fa988c7b10a676d9d",
                "d3cea9a15135428c8ecb623c90117476",
            ),
        )
    ):
        now = datetime(2026, 8, 29, index, tzinfo=UTC)

        def fixed_clock(instant: datetime = now) -> datetime:
            return instant

        raw = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-social"
            / digest
        ).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        url = f"https://www.pbc.gov.cn/diaochatongjisi/116219/116225/{code}/index.html"
        result = ingest_official_context_document(
            paths,
            raw,
            family="pbc_social_financing",
            source_url=url,
            expected_period="2024-01",
            fetched_at=now,
            clock=fixed_clock,
            definition_version=version,
        )
        receipts.append(result)
        assert len(result.claim_ids) == (18 if index == 0 else 9)
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id=f"split-sf-{index}",
            model_version_id=model_id,
            system_as_of=now,
            release_event_id=result.release_event_id,
            metric_ids=("CN_SF_TOTAL", "CN_SF_COMPONENTS"),
            period="2024-01",
        )
        selection = select_retrieval_input(paths, run)
        selected_counts.append(len(selection.selected_claim_ids))
        assert selection.complete is (index == 1)
        if index == 0:
            assert len(selection.missing_members) == 9
            assert all("ytd_increment" in member for member in selection.missing_members)
    assert selected_counts == [17, 26]
    points = repository.metric_series(
        "CN_SF_TOTAL",
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 29, 1, tzinfo=UTC),
        definition_version=version,
    )
    assert {p.dimensions["measure"]: p.selected_value for p in points} == {
        "stock_end": 3842900,
        "stock_yoy": 9.5,
        "ytd_increment": 65000,
    }
    claims = [c for p in points for c in p.claims]
    assert len({c.source_reference for c in claims}) == 2
    assert len({c.public_available_at for c in claims}) == 2
    assert {c.fetched_at.hour for c in claims} == {0, 1}
    assert not set(receipts[0].claim_ids) & set(receipts[1].claim_ids)
    earlier = repository.metric_series(
        "CN_SF_TOTAL",
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        definition_version=version,
    )
    assert {p.dimensions["measure"] for p in earlier} == {"stock_end", "stock_yoy"}


def test_registered_capacity_q1_does_not_certify_an_unresolved_reused_cell(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]
    now = datetime(2026, 8, 29, tzinfo=UTC)
    digest = "0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-official-consumer-edge"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    with pytest.raises(ValueError, match="registered_capacity_q1_mapping_unresolved"):
        ingest_official_context_document(
            paths,
            raw,
            family="nbs_capacity_utilization",
            source_url="https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html",
            expected_period="2026-Q1",
            fetched_at=now,
            clock=lambda: now,
            definition_version=version,
        )
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_CAPACITY_UTILIZATION",
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=version,
    )


@pytest.mark.parametrize("document_kind", ["compact", "official_original"])
def test_admitted_catalog_consumes_cpi_with_separate_categories_and_public_system_times(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], document_kind: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    acquired_at = datetime(2026, 8, 9, 2, tzinfo=UTC)
    content = cpi_document()
    if document_kind == "official_original":
        digest = "a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49"
        content = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-13"
            / digest
        ).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
    ingested = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html",
        expected_period="2026-07",
        fetched_at=acquired_at,
        definition_version=version,
        clock=lambda: acquired_at,
    )
    repository = EvidenceRepository(paths.database)
    expected = {
        "CN_CPI_HEADLINE": ("headline", {"mom": -0.1, "yoy": 0.5, "cumulative_average_yoy": 0.9}),
        "CN_CORE_CPI": ("ex_food_energy", {"mom": 0.3, "yoy": 0.9, "cumulative_average_yoy": 1.1}),
    }
    selected: set[str | None] = set()
    for metric, (category, values) in expected.items():
        public = repository.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 9, 1, 45, tzinfo=UTC),
            definition_version=version,
        )
        assert {point.dimensions["measure"]: point.selected_value for point in public} == values
        assert {point.dimensions["category"] for point in public} == {category}
        selected.update(point.selected_claim_id for point in public)
        assert not repository.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 8, 9, 1, 45, tzinfo=UTC),
            definition_version=version,
        )
        assert (
            len(
                repository.metric_series(
                    metric,
                    mode=AsOfMode.SYSTEM,
                    as_of=acquired_at,
                    definition_version=version,
                )
            )
            == 3
        )
    assert selected == set(ingested.claim_ids)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-cpi",
        model_version_id=model_id,
        system_as_of=acquired_at,
        release_event_id=ingested.release_event_id,
        metric_ids=tuple(expected),
        period="2026-07",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)
    context = build_context_projection(repository, as_of=acquired_at, model_manifest=manifest)
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.parametrize("month", [1, 7])
def test_registered_cpi_requires_cumulative_only_outside_january(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], month: int
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    # Four January literals from the independently audited table. The July
    # variation is deliberately incomplete synthetic data, not an official page.
    release_day = 11 if month == 1 else 9
    period = f"2026-{month:02d}"
    content = f"""
    <h1>2026年{month}月份居民消费价格</h1>
    <p>发布时间：2026-{month + 1:02d}-{release_day:02d} 09:30</p>
    <table><tr><th></th><th>环比涨跌幅（%）</th><th>同比涨跌幅（%）</th></tr>
    <tr><td>居民消费价格</td><td>0.2</td><td>0.2</td></tr>
    <tr><td>不包括食品和能源</td><td>0.3</td><td>0.8</td></tr></table>
    """.encode()
    now = datetime(2026, month + 1, release_day, 2, tzinfo=UTC)
    ingested = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url=(
            "https://www.stats.gov.cn/sj/zxfb/202602/t20260211_1962588.html"
            if month == 1
            else "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html"
        ),
        expected_period=period,
        fetched_at=now,
        clock=lambda: now,
        definition_version=request["manifest"]["metric_catalog_version"],
    )
    assert len(ingested.claim_ids) == 4
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-09" if month == 1 else "2026-08-28",
        client_request_id="admitted-cpi-january",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=ingested.release_event_id,
        metric_ids=("CN_CPI_HEADLINE", "CN_CORE_CPI"),
        period=period,
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete is (month == 1)
    if month == 7:
        assert len(selection.missing_members) == 2
        assert all("cumulative_average_yoy" in member for member in selection.missing_members)
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)


@pytest.mark.parametrize("fault", ["provider", "category", "measure", "period_kind", "unit"])
def test_registered_cpi_rejects_claims_outside_its_supported_source_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 9, 2, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_CORE_CPI",
        definition_version=request["manifest"]["metric_catalog_version"],
        period_kind="month",
        period_start="2026-07-01",
        period_end="2026-07-31",
        dimensions={"category": "ex_food_energy", "measure": "yoy"},
        value=0.9,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percent",
        provider="国家统计局",
        source_reference="synthetic:cpi-identity",
        release_event_id="synthetic:cpi",
        release_at=now,
        public_available_at=now,
        fetched_at=now,
        available_at=now,
        certification_status="certified",
        quality_status="validated",
    )
    if fault == "provider":
        claim = replace(claim, provider="TuShare")
    elif fault == "category":
        claim = replace(claim, dimensions={"category": "headline", "measure": "yoy"})
    elif fault == "measure":
        claim = replace(claim, dimensions={"category": "ex_food_energy", "measure": "level"})
    elif fault == "period_kind":
        claim = replace(claim, period_kind="day")
    else:
        claim = replace(claim, unit="index_points")
    repository = EvidenceRepository(paths.database)
    with pytest.raises(
        ValueError, match="registered_cpi_source_identity_mismatch|evidence_unit_mismatch"
    ):
        repository.append_source_claim(claim)
    assert not repository.metric_series(
        "CN_CORE_CPI",
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=request["manifest"]["metric_catalog_version"],
    )


@pytest.mark.parametrize("field", ["source_codes", "release_event_family", "allowed_units"])
def test_cpi_parser_rejects_an_incompatible_registered_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    definition = next(
        item
        for item in request["manifest"]["metric_definitions"]
        if item["metric_id"] == "CN_CPI_HEADLINE"
    )
    definition[field] = {
        "source_codes": ["another-reviewed-source"],
        "release_event_family": "another-review-family",
        "allowed_units": ["percent", "index_points"],
    }[field]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_CPI_HEADLINE"] = hashlib.sha256(
        encode(definition)
    ).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 9, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="registered_cpi_source_contract_unsupported"):
        ingest_official_context_document(
            paths,
            cpi_document(),
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html",
            expected_period="2026-07",
            fetched_at=now,
            clock=lambda: now,
            definition_version=request["manifest"]["metric_catalog_version"],
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


def test_same_catalog_version_cannot_name_different_reviewed_definitions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    first, _ = prepared_request(paths)
    submit(paths, save(paths, first))
    admitted = json.loads(capsys.readouterr().out)
    versions_before = ModelRepository(paths.database).list_versions()
    manifest_before = ModelRepository(paths.database).manifest(admitted["model_version_id"])

    second, _ = prepared_request(paths)
    definition = next(
        item
        for item in second["manifest"]["metric_definitions"]
        if item["metric_id"] == "CN_LPR_1Y_5Y"
    )
    definition["name_cn"] = "a different, independently reviewed definition"
    package_hash = second["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_LPR_1Y_5Y"] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, second, package)

    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, second))

    assert failure.value.code == 2
    assert "metric_catalog_version_is_immutable" in capsys.readouterr().err
    assert ModelRepository(paths.database).list_versions() == versions_before
    assert ModelRepository(paths.database).manifest(admitted["model_version_id"]) == manifest_before


def test_admitted_catalog_consumes_lpr_through_evidence_selection_and_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    acquired_at = datetime(2026, 8, 20, 2, tzinfo=UTC)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        fetched_at=acquired_at,
        expected_period="2026-08",
        definition_version=version,
        clock=lambda: acquired_at,
    )
    repository = EvidenceRepository(paths.database)
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        points = repository.metric_series(
            "CN_LPR_1Y_5Y", mode=mode, as_of=acquired_at, definition_version=version
        )
        assert {p.dimensions["tenor"]: p.selected_value for p in points} == {
            "1y": 3.0,
            "5y_plus": 3.5,
        }
        assert {p.selected_claim_id for p in points} == set(ingested.claim_ids)
    before_acquisition = datetime(2026, 8, 20, 1, 30, tzinfo=UTC)
    assert not repository.metric_series(
        "CN_LPR_1Y_5Y", mode=AsOfMode.SYSTEM, as_of=before_acquisition, definition_version=version
    )
    assert (
        len(
            repository.metric_series(
                "CN_LPR_1Y_5Y",
                mode=AsOfMode.PUBLIC,
                as_of=before_acquisition,
                definition_version=version,
            )
        )
        == 2
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-lpr",
        model_version_id=model_id,
        system_as_of=acquired_at,
        release_event_id=ingested.release_event_id,
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(ingested.claim_ids)
    context = build_context_projection(repository, as_of=acquired_at, model_manifest=manifest)
    rows = [
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_LPR_1Y_5Y"
    ]
    assert {row["dimensions"]["tenor"]: row["value"] for row in rows} == {"1y": 3.0, "5y_plus": 3.5}
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.parametrize("consumer", ["selection", "context"])
@pytest.mark.parametrize("fault", ["unregistered", "different_definitions"])
def test_generic_model_creation_cannot_borrow_or_register_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], consumer: str, fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    if fault == "different_definitions":
        submit(paths, save(paths, request))
        capsys.readouterr()
        manifest["metric_definitions"][0]["name_cn"] = "unreviewed changed definition"
    manifest["model_version_id"] = "generic-unreviewed-model"
    ModelRepository(paths.database).create_candidate(manifest)
    expected = (
        "unknown_metric_definition_version"
        if fault == "unregistered"
        else "model_metric_catalog_binding_mismatch"
    )
    with pytest.raises((KeyError, ValueError), match=expected):
        if consumer == "context":
            build_context_projection(
                EvidenceRepository(paths.database),
                as_of=datetime(2026, 8, 28, tzinfo=UTC),
                model_manifest=manifest,
            )
        else:
            run = RunRepository(paths.database).submit(
                command_type="targeted_refresh",
                target_business_date="2026-08-28",
                client_request_id="unreviewed-lpr",
                model_version_id=manifest["model_version_id"],
                system_as_of=datetime(2026, 8, 28, tzinfo=UTC),
                release_event_id="synthetic:lpr",
                metric_ids=("CN_LPR_1Y_5Y",),
                period="2026-08",
            )
            select_retrieval_input(paths, run)


def test_unrecognized_definition_fields_cannot_be_admitted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    definition = request["manifest"]["metric_definitions"][0]
    definition["unsupported_rule"] = "cannot silently ignore a reviewed rule"
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    if definition["metric_id"] in package["definition_bindings"]:
        package["definition_bindings"][definition["metric_id"]] = hashlib.sha256(
            encode(definition)
        ).hexdigest()
    bind_synthetic_review(paths, request, package)
    with pytest.raises(SystemExit) as failure:
        submit(paths, save(paths, request))
    assert failure.value.code == 2
    assert "certification_definition_fields_unsupported" in capsys.readouterr().err


def test_reviewed_models_can_share_identical_catalog_in_different_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    first_id = json.loads(capsys.readouterr().out)["model_version_id"]
    request["manifest"]["metric_definitions"].reverse()
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    second_id = json.loads(capsys.readouterr().out)["model_version_id"]
    assert first_id != second_id
    for model_id in (first_id, second_id):
        manifest = ModelRepository(paths.database).manifest(model_id)
        build_context_projection(
            EvidenceRepository(paths.database),
            as_of=datetime(2026, 8, 28, tzinfo=UTC),
            model_manifest=manifest,
        )


def test_concurrent_conflicting_admissions_leave_only_one_complete_candidate(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requests = []
    for label in ("first reviewed name", "second reviewed name"):
        request, _ = prepared_request(paths)
        definition = next(
            item
            for item in request["manifest"]["metric_definitions"]
            if item["metric_id"] == "CN_LPR_1Y_5Y"
        )
        definition["name_cn"] = label
        package_hash = request["package_hashes"][0]
        package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
        package["definition_bindings"]["CN_LPR_1Y_5Y"] = hashlib.sha256(
            encode(definition)
        ).hexdigest()
        bind_synthetic_review(paths, request, package)
        requests.append(save(paths, request))
    before = ModelRepository(paths.database).list_versions()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                admit_source_certified_candidate,
                paths,
                request_hash=request_hash,
                target_business_date="2026-08-28",
                personal_noncommercial_use_approved=True,
            )
            for request_hash in requests
        ]
        successes = []
        failures = []
        for future in futures:
            try:
                successes.append(future.result())
            except ValueError as error:
                failures.append(str(error))
    assert len(successes) == 1
    assert failures == ["metric_catalog_version_is_immutable:synthetic-metric-catalog-admission-v1"]
    assert len(ModelRepository(paths.database).list_versions()) == len(before) + 1
    build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 28, tzinfo=UTC),
        model_manifest=ModelRepository(paths.database).manifest(successes[0]["model_version_id"]),
    )


@pytest.mark.parametrize("field", ["source_codes", "release_rule", "allowed_units"])
def test_lpr_parser_cannot_certify_an_incompatible_registered_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], field: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    definition = next(
        item
        for item in request["manifest"]["metric_definitions"]
        if item["metric_id"] == "CN_LPR_1Y_5Y"
    )
    definition[field] = {
        "source_codes": ["different-certified-source"],
        "release_rule": "different-release-rule",
        "allowed_units": ["percent", "basis_points"],
    }[field]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_LPR_1Y_5Y"] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 20, 2, tzinfo=UTC)
    if field == "allowed_units":
        with pytest.raises(ValueError, match="registered_lpr_source_contract_unsupported"):
            EvidenceRepository(paths.database).append_source_claim(
                SourceClaimInput(
                    metric_id="CN_LPR_1Y_5Y",
                    definition_version=request["manifest"]["metric_catalog_version"],
                    period_kind="month",
                    period_start="2026-08-01",
                    period_end="2026-08-31",
                    dimensions={"tenor": "1y"},
                    value=300.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="basis_points",
                    provider="中国货币网",
                    source_reference="synthetic:unsupported-unit",
                    release_event_id="synthetic:lpr",
                    release_at=now,
                    public_available_at=now,
                    fetched_at=now,
                    available_at=now,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    with pytest.raises(ValueError, match="registered_lpr_source_contract_unsupported"):
        ingest_lpr_document(
            paths,
            (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes(),
            source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
            fetched_at=now,
            expected_period="2026-08",
            clock=lambda: now,
            definition_version=request["manifest"]["metric_catalog_version"],
        )
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_LPR_1Y_5Y",
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=request["manifest"]["metric_catalog_version"],
    )


def test_registered_lpr_rejects_a_claim_from_another_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 8, 20, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="registered_lpr_source_identity_mismatch"):
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id="CN_LPR_1Y_5Y",
                definition_version=request["manifest"]["metric_catalog_version"],
                period_kind="month",
                period_start="2026-08-01",
                period_end="2026-08-31",
                dimensions={"tenor": "1y"},
                value=3.0,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="unreviewed provider",
                source_reference="synthetic:wrong-provider",
                release_event_id="synthetic:lpr",
                release_at=now,
                public_available_at=now,
                fetched_at=now,
                available_at=now,
                certification_status="certified",
                quality_status="validated",
            )
        )
