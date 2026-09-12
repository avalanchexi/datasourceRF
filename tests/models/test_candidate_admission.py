from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
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
from pring_cycle.model_evaluation import evaluate_context_replay
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_120d_model_v0011_manifest,
)
from pring_cycle.official_context import (
    ingest_official_context_document,
    parse_official_context_document,
)
from pring_cycle.official_lpr import ingest_lpr_document, parse_lpr_announcement
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint
from pring_cycle.search_discovery import (
    SearchHttpResponse,
    build_search_query,
    search_discovery_adapter,
)
from pring_cycle.search_evidence import ModelInputSelection, select_retrieval_input
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
@pytest.mark.parametrize("incomplete_scope", [False, True])
def test_registered_rrr_original_preserves_distinct_scopes_and_two_times(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], incomplete_scope: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    digest = "27d57bb20481abc714ea45c9d99dd532652df8ee92c263b1a15cc222c256a3d9"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair"
        / "evidence-search-preexperiment-20260908-n4-v1"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    # A new synthetic import clock; never the real pilot's acquisition timestamp.
    now = datetime(2026, 9, 8, 6, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554653911/index.html",
        expected_period="2025-05",
        fetched_at=now,
        clock=lambda: now,
        definition_version=version,
    )
    assert len(imported.claim_ids) == 2
    evidence = EvidenceRepository(paths.database)
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        points = evidence.metric_series(
            "CN_RRR_EVENT", mode=mode, as_of=now, definition_version=version
        )
        assert {(p.dimensions["scope"], p.selected_value) for p in points} == {
            ("excluding_5_percent_institutions", -0.5),
            ("auto_finance_and_financial_leasing_companies", -5.0),
        }
        for point in points:
            assert point.period_start == point.period_end == "2025-05-15"
            assert point.dimensions["measure"] == "rrr_change"
            (claim,) = point.claims
            assert claim.unit == "percentage_points"
            assert claim.public_available_at == datetime(2025, 5, 7, 2, tzinfo=UTC)
            assert claim.available_at >= now
    assert not evidence.metric_series(
        "CN_RRR_EVENT",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2025, 5, 7, 1, 59, 59, tzinfo=UTC),
        definition_version=version,
    )
    assert not evidence.metric_series(
        "CN_RRR_EVENT",
        mode=AsOfMode.SYSTEM,
        as_of=now - timedelta(seconds=1),
        definition_version=version,
    )
    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            receipt.acquisition_id, "raw"
        )
        == raw
    )

    if incomplete_scope:
        point = points[0]
        claim = point.claims[0]
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_RRR_EVENT",
                definition_version=version,
                period_kind="event",
                period_start=point.period_start,
                period_end=point.period_end,
                dimensions=point.dimensions,
                value=claim.value,
                value_state=claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id=imported.release_event_id + ":synthetic-quality-review",
                release_at=datetime(2025, 5, 8, 2, tzinfo=UTC),
                public_available_at=datetime(2025, 5, 8, 2, tzinfo=UTC),
                fetched_at=now,
                available_at=now + timedelta(seconds=1),
                certification_status="certified",
                quality_status="invalid",
                acquisition_id=receipt.acquisition_id,
            )
        )
        now += timedelta(seconds=1)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="rrr-original-members",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=imported.release_event_id,
        metric_ids=("CN_RRR_EVENT",),
        period="2025-05",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selection = select_retrieval_input(paths, run, mode=mode)
        assert selection.complete is not incomplete_scope
        assert set(selection.selected_claim_ids) == (
            set() if incomplete_scope else set(imported.claim_ids)
        )
    context = build_context_projection(
        evidence,
        as_of=now,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
        target_business_date="2026-08-28",
    )
    inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(inputs, list)
    if incomplete_scope:
        assert set(imported.claim_ids).isdisjoint(inputs)
    else:
        assert set(imported.claim_ids) <= set(inputs)


def admitted_source_variant(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    side: str,
    *,
    metric_id: str = "CN_RRR_EVENT",
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if side == "candidate" and definition["metric_id"] == metric_id:
            definition["source_candidates"] = [
                *definition["source_candidates"],
                "https://www.pbc.gov.cn/synthetic-review",
            ]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"] = {
        d["metric_id"]: hashlib.sha256(encode(d)).hexdigest()
        for d in manifest["metric_definitions"]
        if d["metric_id"] in package["definition_bindings"]
    }
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "candidate_count,fault",
    [
        (1, "none"),
        (2, "none"),
        (2, "missing_lineage"),
        (2, "uncertified"),
        (2, "early_public"),
        (1, "truncated_normalized"),
    ],
)
def test_rrr_component_replay_requires_complete_publication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    candidate_count: int,
    fault: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    digest = "27d57bb20481abc714ea45c9d99dd532652df8ee92c263b1a15cc222c256a3d9"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair"
        / "evidence-search-preexperiment-20260908-n4-v1"
        / digest
    ).read_bytes()
    now = datetime(2026, 9, 8, 6, tzinfo=UTC)
    url = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554653911/index.html"
    parsed = parse_official_context_document(
        raw, family="pbc_rrr_notice", source_url=url, expected_period="2025-05", fetched_at=now
    )
    assert len(parsed.scalars) == 2
    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=parsed.provider,
        api_name="document_import",
        parameters={"source_url": url, "period": "2025-05", "family": "pbc_rrr_notice"},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: raw,
        parse=lambda body: parse_official_context_document(
            body,
            family="pbc_rrr_notice",
            source_url=url,
            expected_period="2025-05",
            fetched_at=now,
        ),
        normalize=asdict,
        clock=lambda: now,
    )
    manifests = {}
    for side, count in (("comparison", 2), ("candidate", candidate_count)):
        manifest = admitted_source_variant(paths, capsys, side)
        model_id = manifest["model_version_id"]
        manifests[side] = manifest
        # Isolate the public component-replay seam. This does not execute the
        # complete package's 27-input acceptance or mutate either stored model.
        manifests[side].pop("source_certification_packages")
        receipt = acquired.receipt
        if side == "candidate" and fault == "truncated_normalized":
            receipt = (
                AcquisitionRepository(paths.database, paths.artifacts)
                .capture(
                    provider=parsed.provider,
                    api_name="document_import",
                    parameters={"source_url": url, "period": "2025-05", "family": "pbc_rrr_notice"},
                    fields="",
                    parser_version="official-context-parser-v0004",
                    fetch=lambda: raw,
                    parse=lambda body: parse_official_context_document(
                        body,
                        family="pbc_rrr_notice",
                        source_url=url,
                        expected_period="2025-05",
                        fetched_at=now,
                    ),
                    normalize=lambda document: {
                        **asdict(document),
                        "scalars": [asdict(document.scalars[0])],
                    },
                    clock=lambda: now,
                )
                .receipt
            )
        stored = EvidenceRepository(paths.database).append_source_claims(
            tuple(
                SourceClaimInput(
                    metric_id=s.metric_id,
                    definition_version=manifest["metric_catalog_version"],
                    period_kind=s.period_kind,
                    period_start=s.period_start,
                    period_end=s.period_end,
                    dimensions=s.dimensions,
                    value=s.value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=s.unit,
                    provider=parsed.provider,
                    source_reference=f"{url}#sha256={digest}",
                    release_event_id=parsed.release_event_id
                    + (
                        ":synthetic-early-public"
                        if side == "candidate" and fault == "early_public"
                        else ""
                    ),
                    release_at=(
                        datetime(2025, 5, 6, 2, tzinfo=UTC)
                        if side == "candidate" and fault == "early_public"
                        else parsed.release_at
                    ),
                    public_available_at=(
                        datetime(2025, 5, 6, 2, tzinfo=UTC)
                        if side == "candidate" and fault == "early_public"
                        else parsed.public_available_at
                    ),
                    fetched_at=now,
                    available_at=now,
                    certification_status=(
                        "awaiting_source_certification"
                        if side == "candidate" and fault == "uncertified"
                        else "certified"
                    ),
                    quality_status="validated",
                    acquisition_id=(
                        None
                        if side == "candidate" and fault == "missing_lineage" and index == 1
                        else receipt.acquisition_id
                    ),
                )
                for index, s in enumerate(parsed.scalars[:count])
            )
        )
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="rrr-members-" + side,
            model_version_id=model_id,
            system_as_of=now,
            release_event_id=parsed.release_event_id,
            metric_ids=("CN_RRR_EVENT",),
            period="2025-05",
        )
        selection = select_retrieval_input(paths, run)
        complete = count == 2 and not (side == "candidate" and fault != "none")
        assert selection.complete is complete
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=now,
            model_manifest=manifests[side],
            target_business_date="2026-08-28",
        )
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        ids = {item.claim_id for item in stored}
        assert (ids <= set(inputs)) is complete
        if side == "candidate" and fault == "uncertified":
            policy = context.macro["policy_action"]
            assert isinstance(policy, dict)
            rows = [row for row in policy["evidence"] if row["metric_id"] == "CN_RRR_EVENT"]
            assert len(rows) == 2
            for row in rows:
                assert row["status"] == "awaiting_source_certification"
                assert row["value"] is None
                assert all(claim["value"] is None for claim in row["claims"])
    replay = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    if fault == "uncertified":
        assert "candidate_context_evidence_missing:CN_RRR_EVENT" in replay.gaps
    else:
        assert ("candidate_context_selection_members_missing:CN_RRR_EVENT" in replay.gaps) is (
            candidate_count == 1 or fault != "none"
        )
    if candidate_count == 2 and fault == "none":
        assert not replay.gaps
        assert replay.evaluated_cutoffs == 1
        assert replay.context_output_differences == 0
        # Synthetic later announcement in the same month, with a single scope.
        # Before its effective date it must not change the public replay; after
        # that date the earlier announcement must still retain both members.
        later_raw = (
            "<html><body><h1>2025年5月准备金公告</h1>"
            "<p>发布时间：2025-05-20 10:00:00</p>"
            "<p>5月25日，中国人民银行下调金融机构存款准备金率0.25个百分点"
            "（不含已执行5%存款准备金率的金融机构）。</p></body></html>"
        ).encode()
        later = ingest_official_context_document(
            paths,
            later_raw,
            family="pbc_rrr_notice",
            source_url="https://www.pbc.gov.cn/synthetic-later-rrr-notice",
            expected_period="2025-05",
            fetched_at=now,
            clock=lambda: now,
            definition_version=manifests["candidate"]["metric_catalog_version"],
        )
        assert len(later.claim_ids) == 1
        for replay_day, expected_differences in (("2025-05-21", 0), ("2025-05-26", 1)):
            event_replay = evaluate_context_replay(
                paths.database,
                manifests["candidate"],
                manifests["comparison"],
                requested_start=replay_day,
                requested_end=replay_day,
            )
            assert not event_replay.gaps
            assert event_replay.evaluated_cutoffs == 1
            assert event_replay.context_output_differences == expected_differences


@pytest.mark.usefixtures("runtime_clock")
def test_rrr_direction_replay_compares_values_without_version_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    now = datetime(2026, 9, 8, 6, tzinfo=UTC)
    manifests = {}
    for side in ("candidate", "comparison"):
        manifests[side] = admitted_source_variant(paths, capsys, side)
        # Public component replay only; stored candidates retain their packages.
        manifests[side].pop("source_certification_packages")
        for day, after_rate in (("01", "2.0"), ("15", "1.75")):
            raw = (
                "<html><body><h1>2025年5月准备金公告</h1>"
                f"<p>发布时间：2025-05-{day} 10:00:00</p><table>"
                "<tr><th>生效日期</th><th>调整（百分点）</th><th>机构范围</th>"
                "<th>调整后准备金率（%）</th><th>释放资金（亿元）</th></tr>"
                f"<tr><td>2025-05-{day}</td><td>-0.25</td><td>all</td>"
                f"<td>{after_rate}</td><td>500</td></tr></table></body></html>"
            ).encode()
            ingest_official_context_document(
                paths,
                raw,
                family="pbc_rrr_notice",
                source_url=f"https://www.pbc.gov.cn/synthetic-rrr-rate-{day}",
                expected_period="2025-05",
                fetched_at=now,
                clock=lambda: now,
                definition_version=manifests[side]["metric_catalog_version"],
            )
    replay = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not replay.gaps
    assert replay.evaluated_cutoffs == 1
    assert replay.context_output_differences == 0


@pytest.mark.usefixtures("runtime_clock")
def test_rrr_direction_excludes_incomplete_previous_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    now = datetime(2026, 9, 8, 6, tzinfo=UTC)
    evidence = EvidenceRepository(paths.database)
    prior_ids: set[str] = set()
    for day, after_rate in (("01", "2.0"), ("15", "1.75")):
        # Synthetic table exercises the supported post-change-rate contract.
        raw = (
            "<html><body><h1>2025年5月准备金公告</h1>"
            f"<p>发布时间：2025-05-{day} 10:00:00</p><table>"
            "<tr><th>生效日期</th><th>调整（百分点）</th><th>机构范围</th>"
            "<th>调整后准备金率（%）</th><th>释放资金（亿元）</th></tr>"
            f"<tr><td>2025-05-{day}</td><td>-0.25</td><td>all</td>"
            f"<td>{after_rate}</td><td>500</td></tr></table></body></html>"
        ).encode()
        imported = ingest_official_context_document(
            paths,
            raw,
            family="pbc_rrr_notice",
            source_url=f"https://www.pbc.gov.cn/synthetic-rrr-rate-{day}",
            expected_period="2025-05",
            fetched_at=now,
            clock=lambda: now,
            definition_version=version,
        )
        if day == "01":
            prior_ids.update(imported.claim_ids)
            points = evidence.metric_series(
                "CN_RRR_EVENT", mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
            )
            point = next(p for p in points if p.dimensions["measure"] == "released_funds")
            claim = point.claims[0]
            (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_RRR_EVENT",
                    definition_version=version,
                    period_kind="event",
                    period_start=point.period_start,
                    period_end=point.period_end,
                    dimensions=point.dimensions,
                    value=claim.value,
                    value_state=claim.value_state,
                    unit=claim.unit,
                    provider=claim.provider,
                    source_reference=claim.source_reference,
                    release_event_id=imported.release_event_id + ":synthetic-quality-review",
                    release_at=datetime(2025, 5, 2, 2, tzinfo=UTC),
                    public_available_at=datetime(2025, 5, 2, 2, tzinfo=UTC),
                    fetched_at=now,
                    available_at=now + timedelta(seconds=1),
                    certification_status="certified",
                    quality_status="invalid",
                    acquisition_id=receipt.acquisition_id,
                )
            )
    context = build_context_projection(
        evidence,
        as_of=now + timedelta(seconds=1),
        model_manifest=manifest,
        target_business_date="2026-08-28",
    )
    inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(inputs, list)
    assert prior_ids.isdisjoint(inputs)
    policy = context.macro["policy_action"]
    assert isinstance(policy, dict)
    row = next(
        row
        for row in policy["evidence"]
        if row["metric_id"] == "CN_RRR_EVENT" and row["dimensions"]["measure"] == "post_change_rrr"
    )
    assert row["value"] == 1.75
    assert row["direction"] == "unknown"
    assert row["direction_input_observation_version_ids"] == []


@pytest.mark.parametrize(
    "fault",
    ["provider", "scope", "measure", "unit", "period_kind", "period_bounds", "invalid_date"],
)
def test_registered_rrr_identity_rejection_keeps_whole_batch_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    now = datetime(2026, 9, 8, 6, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_RRR_EVENT",
        definition_version=request["manifest"]["metric_catalog_version"],
        period_kind="event",
        period_start="2025-05-15",
        period_end="2025-05-15",
        dimensions={"scope": "excluding_5_percent_institutions", "measure": "rrr_change"},
        value=-0.5,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percentage_points",
        provider=OFFICIAL_CONTEXT_FAMILIES["pbc_rrr_notice"].provider,
        source_reference="synthetic:rrr-identity",
        release_event_id="synthetic:rrr-identity",
        release_at=now,
        public_available_at=now,
        fetched_at=now,
        available_at=now,
        certification_status="certified",
        quality_status="validated",
    )
    changes_by_fault: dict[str, dict[str, Any]] = {
        "provider": {"provider": "synthetic:wrong-provider"},
        "scope": {"dimensions": {"scope": " ", "measure": "rrr_change"}},
        "measure": {"dimensions": {"scope": "all", "measure": "unknown"}},
        "unit": {"unit": "percent"},
        "period_kind": {"period_kind": "month"},
        "period_bounds": {"period_start": "2025-05-01", "period_end": "2025-05-31"},
        "invalid_date": {"period_start": "2025-05-99", "period_end": "2025-05-99"},
    }
    repository = EvidenceRepository(paths.database)
    with pytest.raises(ValueError, match="registered_rrr_source_.*mismatch"):
        repository.append_source_claims((claim, replace(claim, **changes_by_fault[fault])))
    assert not repository.metric_series(
        claim.metric_id,
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version=claim.definition_version,
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_warrant_acquisition_preserves_sample_units_and_unknown_public(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    # Synthetic TuShare delivery shape, anchored to independent SHFE literals.
    # These are not historical TuShare receipts or a new source certification.
    raw_by_symbol = {
        symbol: encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [["20260828", symbol, warehouse, None, value, 0, unit, "SHFE"]],
                },
            }
        )
        for symbol, warehouse, value, unit in (
            ("CU", "国储天威", 225, "吨"),
            ("SC", "弘润油储", 1027000, "桶"),
        )
    }
    requests: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["api_name"] == "fut_wsr"
        symbol = str(payload["params"]["symbol"])
        requests.append(symbol)
        return raw_by_symbol[symbol]

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    imported = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            scalar
            for symbol in ("CU", "SC")
            for scalar in adapter.futures_warrants(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                symbol=symbol,
            )
        ),
        definition_version=version,
    )
    assert requests == ["CU", "SC"]
    assert len(imported.claim_ids) == 4
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    points = evidence.metric_series(
        "CN_FUTURES_WARRANTS", mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
    )
    assert {
        (p.dimensions["symbol"], p.selected_value, p.claims[0].unit)
        for p in points
        if p.dimensions["measure"] == "registered_receipts"
    } == {("CU", 225, "tonne"), ("SC", 1027000, "barrel")}
    assert all(p.dimensions["exchange"] == "SHFE" for p in points)
    for point in points:
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=now)
        assert len(trace.acquisitions) == 1
        (linked_receipt,) = trace.acquisitions
        assert linked_receipt.parameters["symbol"] == point.dimensions["symbol"]
    assert all(p.claims[0].public_available_at is None for p in points)
    assert not evidence.metric_series(
        "CN_FUTURES_WARRANTS", mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 2
    assert {
        acquisitions.read_content(r.acquisition_id, "raw") for r in acquisitions.history()
    } == set(raw_by_symbol.values())
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="warrant-two-sample-members",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:warrants",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    assert not select_retrieval_input(paths, run).complete


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "scenario",
    [
        "complete",
        "missing_current",
        "invalid_receipt",
        "prior_missing",
        "warehouse_removed",
        "forged_optional",
        "wrong_normalized",
        "wrong_normalized_public",
        "explicit_definition",
        "wrong_normalized_value",
        "wrong_normalized_unit",
        "wrong_normalized_period",
        "wrong_normalized_link",
        "wrong_normalized_definition",
        "normalized_removed",
        "normalized_changed",
    ],
)
def test_registered_warrant_selection_requires_all_returned_warehouses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
) -> None:
    missing_current = scenario == "missing_current"
    invalid_receipt = scenario == "invalid_receipt" or scenario.startswith(
        ("wrong_normalized", "normalized_")
    )
    prior_missing = scenario == "prior_missing"
    warehouse_removed = scenario == "warehouse_removed"
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    # All eight deliveries, units and publication times in this test are synthetic.
    # The fixture proves software completeness, not missing PP/CF/TA certification.
    symbols = ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = str(payload["params"]["symbol"])
        unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
        exchange = "CZCE" if symbol in {"CF", "PTA"} else "DCE" if symbol == "PP" else "SHFE"
        rows = [["20260828", symbol, "synthetic-first", None, 100, None, unit, exchange]]
        if symbol == "CU":
            rows.append(
                [
                    "20260828",
                    symbol,
                    "synthetic-second",
                    None,
                    None if missing_current else 25,
                    None,
                    unit,
                    exchange,
                ]
            )
        if prior_missing:
            rows = [
                [
                    "20260827",
                    *row[1:4],
                    None if symbol == "CU" and row[2] == "synthetic-second" else 80,
                    *row[5:],
                ]
                for row in rows
            ] + rows
        elif warehouse_removed:
            rows = [["20260827", *row[1:]] for row in rows] + [
                row for row in rows if row[2] != "synthetic-second"
            ]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": rows,
                },
            }
        )

    public_at = datetime(2026, 8, 28, 9, tzinfo=UTC)
    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    imported = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(
                scalar,
                release_at=public_at,
                public_available_at=public_at,
                definition_version=version if scenario == "explicit_definition" else None,
            )
            for symbol in symbols
            for scalar in adapter.futures_warrants(
                start_date=date(2026, 8, 27 if prior_missing or warehouse_removed else 28),
                end_date=date(2026, 8, 28),
                symbol=symbol,
            )
        ),
        definition_version=version,
    )
    assert adapter.network_requests == 8
    assert len(imported.claim_ids) == (
        17 if prior_missing or warehouse_removed else 8 if missing_current else 9
    )
    current_ids = {
        p.selected_claim_id
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.PUBLIC,
            as_of=public_at,
            definition_version=version,
        )
        if p.period_end == "2026-08-28"
    }
    forged_ids: tuple[str, ...] = ()
    if scenario == "forged_optional":
        forged_ids = ingest_context_scalars(
            paths,
            (
                ContextScalar(
                    metric_id="CN_FUTURES_WARRANTS",
                    api_name="fut_wsr",
                    source_field="pre_vol",
                    period_kind="business_day",
                    period_start="2026-08-28",
                    period_end="2026-08-28",
                    dimensions={
                        "symbol": "CU",
                        "warehouse": "synthetic-first",
                        "exchange": "SHFE",
                        "measure": "previous_registered_receipts",
                    },
                    value=9001,
                    unit="tonne",
                    release_at=public_at,
                    public_available_at=public_at,
                ),
            ),
            fetched_at=datetime.now(UTC),
            definition_version=version,
        ).claim_ids
    if invalid_receipt:
        evidence = EvidenceRepository(paths.database)
        point = next(
            p
            for p in evidence.metric_series(
                "CN_FUTURES_WARRANTS",
                mode=AsOfMode.PUBLIC,
                as_of=public_at,
                definition_version=version,
            )
            if p.dimensions["symbol"] == "CU" and p.dimensions["warehouse"] == "synthetic-first"
        )
        claim = next(c for c in point.claims if c.claim_id == point.selected_claim_id)
        (original,) = evidence.source_claim_originals(claim.claim_id)
        receipt, raw = original
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        malformed = acquisitions.capture(
            provider="tushare",
            api_name="fut_wsr",
            parameters=receipt.parameters,
            fields=receipt.fields,
            parser_version=(
                receipt.parser_version
                if scenario != "invalid_receipt"
                else "synthetic-invalid-parser"
            ),
            fetch=lambda: raw,
            parse=json.loads,
            normalize=lambda document: [] if scenario == "wrong_normalized" else document,
            clock=lambda: claim.fetched_at,
            defer_validation=True,
        ).receipt
        normalized: list[dict[str, Any]] = []
        if scenario not in {"invalid_receipt", "wrong_normalized"}:
            normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
            for item in normalized:
                item["acquisition_ids"] = [malformed.acquisition_id]
            changes = {
                "wrong_normalized_public": ("public_available_at", None),
                "wrong_normalized_value": ("value", 999),
                "wrong_normalized_unit": ("unit", "barrel"),
                "wrong_normalized_period": ("period_end", "2026-08-27"),
                "wrong_normalized_link": ("acquisition_ids", [receipt.acquisition_id]),
                "wrong_normalized_definition": ("definition_version", "wrong-catalog"),
            }
            if scenario in changes:
                field, value = changes[scenario]
                normalized[0][field] = value
        malformed = acquisitions.complete_validation(
            malformed.acquisition_id, normalized, clock=lambda: claim.fetched_at
        )
        if scenario in {"normalized_removed", "normalized_changed"}:
            assert malformed.normalized_hash is not None
            artifact = paths.artifacts / malformed.normalized_hash[:2] / malformed.normalized_hash
            if scenario == "normalized_removed":
                artifact.unlink()
            else:
                artifact.write_bytes(b"damaged normalized")
        revision = evidence.latest_provider_claim(
            metric_id="CN_FUTURES_WARRANTS",
            definition_version=version,
            period_kind="business_day",
            period_start=point.period_start,
            period_end=point.period_end,
            dimensions=point.dimensions,
            provider="tushare",
            source_reference=claim.source_reference,
        )
        assert revision is not None
        linked = evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_FUTURES_WARRANTS",
                definition_version=version,
                period_kind="business_day",
                period_start=point.period_start,
                period_end=point.period_end,
                dimensions=point.dimensions,
                value=claim.value,
                value_state=claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id=revision.release_event_id,
                release_at=claim.release_at,
                public_available_at=claim.public_available_at,
                fetched_at=claim.fetched_at,
                available_at=claim.available_at,
                certification_status=claim.certification_status,
                quality_status=claim.quality_status,
                acquisition_id=malformed.acquisition_id,
            )
        )
        assert linked.claim_id == claim.claim_id
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="warrant-all-warehouses",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:warrant-all-warehouses",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selection = select_retrieval_input(paths, run, mode=mode)
        assert selection.complete is not (missing_current or invalid_receipt)
        if not (missing_current or invalid_receipt):
            assert set(selection.selected_claim_ids) == current_ids
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=public_at,
        as_of_mode=AsOfMode.PUBLIC,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
        target_business_date="2026-08-28",
    )
    inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(inputs, list)
    assert set(forged_ids).isdisjoint(inputs)
    if missing_current or invalid_receipt:
        assert set(imported.claim_ids).isdisjoint(inputs)
    else:
        assert current_ids <= set(inputs)
        if prior_missing:
            assert (set(imported.claim_ids) - current_ids).isdisjoint(inputs)
        if warehouse_removed:
            removed_ids = {
                p.selected_claim_id
                for p in EvidenceRepository(paths.database).metric_series(
                    "CN_FUTURES_WARRANTS",
                    mode=AsOfMode.PUBLIC,
                    as_of=public_at,
                    definition_version=version,
                )
                if p.dimensions["warehouse"] == "synthetic-second"
            }
            assert removed_ids.isdisjoint(inputs)


@pytest.mark.usefixtures("runtime_clock")
def test_warrant_value_revision_remains_system_usable_with_unknown_public(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    public_at = datetime(2026, 8, 28, 9, tzinfo=UTC)
    copper = 100

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = payload["params"]["symbol"]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        [
                            "20260828",
                            symbol,
                            "synthetic",
                            None,
                            copper if symbol == "CU" else 100,
                            None,
                            "吨",
                            "synthetic",
                        ]
                    ],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def acquire(symbols: tuple[str, ...]) -> None:
        adapter.acquire_scalars(
            paths,
            lambda: tuple(
                replace(scalar, release_at=public_at, public_available_at=public_at)
                for symbol in symbols
                for scalar in adapter.futures_warrants(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
                )
            ),
            definition_version=version,
        )

    def select(name: str) -> ModelInputSelection:
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id=name,
            model_version_id=model_id,
            system_as_of=datetime.now(UTC),
            release_event_id="synthetic:warrant-revision",
            metric_ids=("CN_FUTURES_WARRANTS",),
            period="2026-08-28",
        )
        return select_retrieval_input(paths, run)

    acquire(("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA"))
    assert select("warrant-before-revision").complete
    copper = 101
    public_at += timedelta(hours=1)
    acquire(("CU",))
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    current = next(p for p in points if p.dimensions["symbol"] == "CU")
    claim = next(c for c in current.claims if c.claim_id == current.selected_claim_id)
    assert current.selected_value == 101
    assert claim.public_available_at is None and claim.release_at is None
    historical = evidence.metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.PUBLIC,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert next(p for p in historical if p.dimensions["symbol"] == "CU").selected_value == 100
    selection = select("warrant-after-revision")
    assert selection.complete
    # The historical target remains PUBLIC-bounded, even in a SYSTEM run.
    assert current.selected_claim_id not in selection.selected_claim_ids
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        as_of_mode=AsOfMode.SYSTEM,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
    )
    assert context.warrant_history is not None
    assert context.warrant_history.complete_periods["CU"] == ("2026-08-28",)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("retired_warehouse", [False, True])
def test_warrant_context_snapshot_binds_older_coverage_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], retired_warehouse: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    public_at = datetime(2026, 8, 28, 9, tzinfo=UTC)
    periods = ("20260824", "20260825", "20260826", "20260827", "20260828")

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = str(payload["params"]["symbol"])
        unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
        start, end = payload["params"]["start_date"], payload["params"]["end_date"]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        [period, symbol, "synthetic-warehouse", None, 100, None, unit, "synthetic"]
                        for period in periods
                        if start <= period <= end
                    ],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id="CN_FUTURES_WARRANTS")
        # Public component verification only, not a complete model admission/replay.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        adapter.acquire_scalars(
            paths,
            lambda: tuple(
                replace(s, release_at=public_at, public_available_at=public_at)
                for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
                for s in adapter.futures_warrants(
                    start_date=date(2026, 8, 24), end_date=date(2026, 8, 28), symbol=symbol
                )
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not before.gaps, before.gaps
    if retired_warehouse:
        evidence = EvidenceRepository(paths.database)
        current = next(
            p
            for p in evidence.metric_series(
                "CN_FUTURES_WARRANTS",
                mode=AsOfMode.PUBLIC,
                as_of=public_at,
                definition_version=manifests["candidate"]["metric_catalog_version"],
            )
            if p.period_end == "2026-08-24" and p.dimensions["symbol"] == "CU"
        )
        claim = current.claims[0]
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_FUTURES_WARRANTS",
                definition_version=manifests["candidate"]["metric_catalog_version"],
                period_kind="business_day",
                period_start="2026-08-24",
                period_end="2026-08-24",
                dimensions={**current.dimensions, "warehouse": "synthetic-retired"},
                value=100,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id="synthetic-retired-invalid",
                release_at=public_at,
                public_available_at=public_at,
                fetched_at=datetime.now(UTC),
                available_at=datetime.now(UTC),
                certification_status="certified",
                quality_status="invalid",
            )
        )
        models = ModelRepository(paths.database)
        for side, manifest in manifests.items():
            # Save a component-only fixture under its own identity. The missing
            # core/120-day evidence still prevents a passed model replay.
            manifest["model_version_id"] = f"warrant-context-storage-{side}"
            models.create_candidate(manifest)
        evaluated = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert not evaluated.gaps, evaluated.gaps
        document = evaluated.output_document
        replay = models.record_replay(
            manifests["candidate"]["model_version_id"],
            compared_with=manifests["comparison"]["model_version_id"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
            quality_passed=True,
            regression_passed=True,
            performance_passed=True,
            stage_differences=0,
            core_state_differences=0,
            gaps=(),
            evaluated_trading_days=1,
            calendar_hash=document["calendar_hash"],
            context_output_differences=evaluated.context_output_differences,
            context_output_document=document,
            context_output_hash=hashlib.sha256(encode(document)).hexdigest(),
        )
        saved = models.replay_details(replay.replay_id)
        assert not replay.passed and "core_candidate_outputs_incomplete" in replay.gaps
        assert saved["context_output_status"] == "recorded"
        points = saved["context_output_document"]["days"][0]["candidate"]["source_inputs"][
            "CN_FUTURES_WARRANTS"
        ]
        old = next(p for p in points if p["dimensions"]["warehouse"] == "synthetic-retired")
        assert old["claims"][0]["quality_status"] == "invalid"
        return
    revised_at = public_at + timedelta(hours=1)
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=revised_at, public_available_at=revised_at)
            for s in adapter.futures_warrants(
                start_date=date(2026, 8, 24), end_date=date(2026, 8, 24), symbol="CU"
            )
        ),
        definition_version=manifests["candidate"]["metric_catalog_version"],
    )
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not after.gaps, after.gaps
    assert before.context_output_differences == after.context_output_differences == 0
    assert before.output_document != after.output_document
    assert before.output_document is not None and after.output_document is not None
    old = before.output_document["days"][0]["candidate"]["source_inputs"]["CN_FUTURES_WARRANTS"]
    new = after.output_document["days"][0]["candidate"]["source_inputs"]["CN_FUTURES_WARRANTS"]
    old_point = next(
        p for p in old if p["period_end"] == "2026-08-24" and p["dimensions"]["symbol"] == "CU"
    )
    new_point = next(
        p for p in new if p["period_end"] == "2026-08-24" and p["dimensions"]["symbol"] == "CU"
    )
    assert old_point["selected_value"] == new_point["selected_value"] == 100
    assert old_point["selected_claim_id"] != new_point["selected_claim_id"]


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("missing_current", [False, True])
@pytest.mark.parametrize("redeliver_old", [False, True])
def test_warrant_same_day_revision_preserves_public_history_and_replaces_members(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], missing_current: bool, redeliver_old: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    old_public = datetime(2026, 8, 28, 9, tzinfo=UTC)
    new_public = datetime(2026, 8, 28, 10, tzinfo=UTC)

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = payload["params"]["symbol"]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        ["20260828", symbol, "synthetic-old", 90, 100, 10, "吨", "synthetic"]
                    ],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    original = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=old_public, public_available_at=old_public)
            for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
            for s in adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    old_cu_ids = {
        p.selected_claim_id
        for p in evidence.metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.PUBLIC,
            as_of=old_public,
            definition_version=version,
        )
        if p.dimensions["symbol"] == "CU"
    }
    revision_adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda payload: encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [
                        [
                            "20260828",
                            "CU",
                            "synthetic-new",
                            20,
                            None if missing_current else 25,
                            None,
                            "吨",
                            "synthetic",
                        ]
                    ],
                },
            }
        ),
    )
    revision = revision_adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=new_public, public_available_at=new_public)
            for s in revision_adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
            )
        ),
        definition_version=version,
    )
    revision_acquired_at = datetime.now(UTC)
    if redeliver_old:
        original = adapter.acquire_scalars(
            paths,
            lambda: tuple(
                replace(s, release_at=old_public, public_available_at=old_public)
                for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
                for s in adapter.futures_warrants(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
                )
            ),
            definition_version=version,
        )
        old_cu_ids = {
            p.selected_claim_id
            for p in evidence.metric_series(
                "CN_FUTURES_WARRANTS",
                mode=AsOfMode.PUBLIC,
                as_of=old_public,
                definition_version=version,
            )
            if p.dimensions["symbol"] == "CU"
        }
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="warrant-same-day-revision",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:warrant-same-day-revision",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    for cutoff in (old_public, new_public):
        selection = select_retrieval_input(
            paths, replace(run, system_as_of=cutoff, cutoffs_frozen=True), mode=AsOfMode.PUBLIC
        )
        assert selection.complete is not (cutoff == new_public and missing_current)
        context = build_context_projection(
            evidence,
            as_of=cutoff,
            as_of_mode=AsOfMode.PUBLIC,
            model_manifest=ModelRepository(paths.database).manifest(model_id),
            target_business_date="2026-08-28",
        )
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        if cutoff == old_public:
            assert set(original.claim_ids) <= set(inputs)
            assert set(revision.claim_ids).isdisjoint(inputs)
        elif missing_current:
            assert set((*original.claim_ids, *revision.claim_ids)).isdisjoint(inputs)
        else:
            assert old_cu_ids.isdisjoint(inputs)
            assert (set(original.claim_ids) - old_cu_ids) | set(revision.claim_ids) <= set(inputs)
    if redeliver_old:
        before = select_retrieval_input(
            paths,
            replace(run, system_as_of=revision_acquired_at, cutoffs_frozen=True),
            mode=AsOfMode.SYSTEM,
        )
        assert before.complete is not missing_current
        if not missing_current:
            assert set(revision.claim_ids) <= set(before.selected_claim_ids)
        after = select_retrieval_input(paths, run, mode=AsOfMode.SYSTEM)
        assert after.complete
        assert set(after.selected_claim_ids) == set(original.claim_ids)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("missing_current", [False, True])
def test_warrant_component_replay_requires_every_returned_warehouse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], missing_current: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    public_at = datetime(2026, 8, 28, 9, tzinfo=UTC)
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id="CN_FUTURES_WARRANTS")
        # Isolate the public component replay. Stored candidate packages are unchanged.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest

        def transport(payload: dict[str, Any], *, side: str = side) -> bytes:
            symbol = str(payload["params"]["symbol"])
            unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
            rows = [["20260828", symbol, "synthetic-first", None, 100, None, unit, "synthetic"]]
            if symbol == "CU":
                rows.append(
                    [
                        "20260828",
                        symbol,
                        "synthetic-second",
                        None,
                        None if side == "candidate" and missing_current else 25,
                        None,
                        unit,
                        "synthetic",
                    ]
                )
            return encode(
                {
                    "code": 0,
                    "data": {
                        "fields": [
                            "trade_date",
                            "symbol",
                            "warehouse",
                            "pre_vol",
                            "vol",
                            "vol_chg",
                            "unit",
                            "exchange",
                        ],
                        "items": rows,
                    },
                }
            )

        adapter = TushareContextAdapter("synthetic-token", transport=transport)

        def retrieve(adapter: TushareContextAdapter = adapter) -> tuple[ContextScalar, ...]:
            return tuple(
                replace(s, release_at=public_at, public_available_at=public_at)
                for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")
                for s in adapter.futures_warrants(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=symbol
                )
            )

        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
    replay = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    if missing_current:
        assert "candidate_context_selection_members_missing:CN_FUTURES_WARRANTS" in replay.gaps
    else:
        assert not replay.gaps
        assert replay.evaluated_cutoffs == 1
        assert replay.context_output_differences == 0


@pytest.mark.usefixtures("runtime_clock")
def test_registered_warrant_trace_uses_complete_leaf_requests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        start, end = payload["params"]["start_date"], payload["params"]["end_date"]
        row = [
            start,
            "CU",
            "synthetic-warehouse",
            None,
            224 if start == "20260827" else 225,
            None,
            "吨",
            "SHFE",
        ]
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": [row] * (1000 if start != end else 1),
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    imported = adapter.acquire_scalars(
        paths,
        lambda: adapter.futures_warrants(
            start_date=date(2026, 8, 27), end_date=date(2026, 8, 28), symbol="CU"
        ),
        definition_version=version,
    )
    assert len(imported.claim_ids) == 2
    assert adapter.network_requests == 3
    evidence = EvidenceRepository(paths.database)
    now = datetime.now(UTC)
    for point in evidence.metric_series(
        "CN_FUTURES_WARRANTS", mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
    ):
        (receipt,) = evidence.trace(
            point.observation_id, mode=AsOfMode.SYSTEM, as_of=now
        ).acquisitions
        assert receipt.parameters["start_date"] == receipt.parameters["end_date"]
        assert receipt.parameters["end_date"] == point.period_end.replace("-", "")
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    parent = next(
        r for r in acquisitions.history() if r.parameters["start_date"] != r.parameters["end_date"]
    )
    assert json.loads(acquisitions.read_content(parent.acquisition_id, "normalized")) == []


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("fault", ["api", "field", "duplicate", "conflicting"])
def test_registered_warrant_invalid_delivery_rejects_atomic_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]
    rows = [["20260828", "CU", "synthetic-warehouse", 225, 225, 0, "吨", "SHFE"]]
    if fault in {"duplicate", "conflicting"}:
        rows.append(
            [
                "20260828",
                "CU",
                "synthetic-warehouse",
                225,
                226 if fault == "conflicting" else 225,
                0,
                "吨",
                "SHFE",
            ]
        )
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": [
                    "trade_date",
                    "symbol",
                    "warehouse",
                    "pre_vol",
                    "vol",
                    "vol_chg",
                    "unit",
                    "exchange",
                ],
                "items": rows,
            },
        }
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.futures_warrants(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
        )
        if fault in {"duplicate", "conflicting"}:
            return scalars
        return tuple(
            (
                replace(s, api_name="synthetic_wrong_api")
                if fault == "api"
                else replace(s, source_field="pre_vol")
            )
            if s.source_field == "vol"
            else s
            for s in scalars
        )

    expected_error = (
        "tushare_warrant_duplicate_member"
        if fault in {"duplicate", "conflicting"}
        else "registered_warrant_source_field_mismatch"
    )
    with pytest.raises(ValueError, match=expected_error):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    if fault in {"duplicate", "conflicting"}:
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        (receipt,) = acquisitions.history()
        assert receipt.state == "failed"
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw


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


@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_search_binds_shared_gaps_and_preserves_both_responses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    metrics = ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES")
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-pair",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:pmi-search",
        metric_ids=metrics,
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, version)
    query = build_search_query(
        metrics, period="2026-07", definition_version=version, database_path=paths.database
    )
    assert all(metric in query for metric in metrics)
    assert "2026-07" in query
    original = encode(
        {
            "results": [
                {
                    "url": "https://www.stats.gov.cn/synthetic/pmi.html",
                    "content": "synthetic unverified candidate",
                }
            ]
        }
    )

    def transport(
        _endpoint: str, _headers: dict[str, str], _payload: dict[str, object]
    ) -> SearchHttpResponse:
        return SearchHttpResponse(200, None, original)

    for provider in ("tavily", "exa"):
        response = search_discovery_adapter(
            provider,
            "synthetic-key",
            query,
            transport=transport,
            paths=paths,
            run_id=run.run_id,
            ledger=ledger,
        )("synthetic:pmi-search")
        assert response.status == "candidate_source"
        assert response.classification == "unverified_candidate"
    recorded = ledger.for_run(run.run_id)
    assert recorded is not None
    assert len(recorded["gaps"]) == 3
    assert {g["definition_version"] for g in recorded["gaps"]} == {version}
    assert {g["model_version_id"] for g in recorded["gaps"]} == {model_id}
    assert len(recorded["requests"]) == 2
    assert {r["channel"] for r in recorded["requests"]} == {"tavily", "exa"}
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for physical in recorded["requests"]:
        assert acquisitions.read_content(physical["acquisition_id"], "raw") == original
    assert recorded["candidate_validations"] == []
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("legacy_kind", ["cache", "budget"])
def test_registered_catalog_retains_shared_family_legacy_search_limits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], legacy_kind: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    now = datetime.now(UTC)
    runs = RunRepository(paths.database)
    old = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-old",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:pmi-old",
        metric_ids=("CN_PMI_ACTIVITY",),
        period="2026-07",
    )
    if legacy_kind == "cache":
        runs.store_negative_cache(
            "synthetic:pmi-old",
            ("CN_PMI_ACTIVITY",),
            reason="unresolved",
            expires_at=now + timedelta(minutes=30),
            now=now,
        )
    else:
        runs.record_retrieval_attempt(
            old.run_id,
            release_event_id="synthetic:pmi-old",
            channel="tavily",
            outcome="failed",
            classification="transient_transport_error",
            latency_ms=1,
            remaining_run_budget=7,
            remaining_daily_budget=15,
            budget_charged=True,
            cache_hit=False,
            manual_budget_exemption=False,
            candidate_source=None,
            occurred_at=now,
        )
    runs.mark_action_required(old.run_id, "legacy-unresolved")
    run = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="registered-search-new",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:pmi-new",
        metric_ids=("CN_PMI_INVENTORY",),
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, version)
    query = build_search_query(
        ("CN_PMI_INVENTORY",),
        period="2026-07",
        definition_version=version,
        database_path=paths.database,
    )

    def transport(
        _endpoint: str, _headers: dict[str, str], _payload: dict[str, object]
    ) -> SearchHttpResponse:
        pytest.fail("shared family limit must prevent an external request")

    response = search_discovery_adapter(
        "tavily",
        "synthetic-key",
        query,
        transport=transport,
        paths=paths,
        run_id=run.run_id,
    )("synthetic:pmi-new")
    assert response.status == "not_attempted"
    assert response.classification == (
        "negative_cache_active" if legacy_kind == "cache" else "event_daily_limit"
    )
    assert not AcquisitionRepository(paths.database, paths.artifacts).history()
    recorded = ledger.for_run(run.run_id)
    assert recorded is not None
    assert recorded["requests"] == []


def test_registered_search_gap_cannot_use_a_different_catalog_than_its_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="catalog-mismatch",
        model_version_id=model_id,
        system_as_of=datetime(2026, 9, 8, tzinfo=UTC),
        release_event_id="synthetic:mismatch",
        metric_ids=("CN_PMI_ACTIVITY",),
        period="2026-07",
    )
    ledger = RetrievalLedger(paths.database)
    with pytest.raises(ValueError, match="retrieval_catalog_model_mismatch"):
        ledger.bind_run(run, "metric-catalog-v0001")
    assert ledger.for_run(run.run_id) is None


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


@pytest.mark.parametrize("saved_official", [False, True])
def test_admitted_catalog_consumes_lpr_through_evidence_selection_and_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], saved_official: bool
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
    if saved_official:
        # Real archived bytes and literal expected values; admission and clocks
        # remain synthetic, so this does not grant historical source certification.
        digest = "5b4ddec501ddfe52bfec15d471c8c6d4548b643da9a61f35f9a978825bc04bd5"
        content = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-lpr-import-20260908"
            / digest
        ).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
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
    assert all(row["status"] == "current" for row in rows)
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(model_inputs) == set(ingested.claim_ids)
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()


@pytest.mark.parametrize(
    ("consumer", "fault"),
    [
        ("selection", "damaged"),
        ("selection", "wrong_value"),
        ("context", "damaged"),
        ("selection", "claim_value"),
        ("selection", "claim_period"),
        ("selection", "claim_reference"),
        ("selection", "claim_public"),
    ],
)
def test_lpr_selection_rejects_normalized_damage_after_ingestion(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], consumer: str, fault: str
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
    source_url = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
    source_period = "2026-08"
    if fault == "claim_period":
        # Synthetic July release, intentionally associated with an August claim below.
        content = content.replace(b"2026-08-20", b"2026-07-20").replace(
            "2026年8月20日".encode(), "2026年7月20日".encode()
        )
        source_url = source_url.replace("20260820", "20260720")
        source_period = "2026-07"
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=source_url,
        fetched_at=acquired_at,
        expected_period=source_period,
        definition_version=version,
        clock=lambda: acquired_at,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="lpr-normalized-damage",
        model_version_id=model_id,
        system_as_of=acquired_at + timedelta(seconds=1),
        release_event_id=ingested.release_event_id,
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    before = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    if fault == "claim_period":
        # A valid July release does not fill the explicit August evidence gap.
        assert not before.complete
        assert before.selected_claim_ids == ()
    else:
        assert before.complete
        assert set(before.selected_claim_ids) == set(ingested.claim_ids)
    if consumer == "context":
        before_context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=acquired_at,
            model_manifest=manifest,
            as_of_mode=AsOfMode.PUBLIC,
        )
        assert set(ingested.claim_ids) <= set(before_context.observation_version_ids)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.normalized_hash is not None
    if fault == "damaged":
        artifact = paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash
        artifact.write_bytes(b"damaged normalized LPR")
    else:
        malformed = acquisitions.capture(
            provider=receipt.provider,
            api_name=receipt.api_name,
            parameters=receipt.parameters,
            fields=receipt.fields,
            parser_version=receipt.parser_version,
            fetch=lambda: acquisitions.read_content(receipt.acquisition_id, "raw"),
            parse=lambda raw: parse_lpr_announcement(
                raw,
                source_url=receipt.parameters["source_url"],
                fetched_at=acquired_at,
                expected_period=receipt.parameters["period"],
            ),
            normalize=lambda parsed: (
                asdict(parsed)
                if fault.startswith("claim_")
                else {
                    **asdict(parsed),
                    "observations": [
                        {"tenor": "1y", "value": 3.1},
                        {"tenor": "5y_plus", "value": 3.5},
                    ],
                }
            ),
            clock=lambda: acquired_at,
        ).receipt
        evidence = EvidenceRepository(paths.database)
        for point in evidence.metric_series(
            "CN_LPR_1Y_5Y", mode=AsOfMode.PUBLIC, as_of=acquired_at, definition_version=version
        ):
            claim = next(c for c in point.claims if c.claim_id == point.selected_claim_id)
            assert claim.public_available_at is not None
            linked = evidence.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_LPR_1Y_5Y",
                    definition_version=version,
                    period_kind="month",
                    period_start="2026-08-01" if fault == "claim_period" else point.period_start,
                    period_end="2026-08-31" if fault == "claim_period" else point.period_end,
                    dimensions=point.dimensions,
                    value=(
                        {"1y": 3.2, "5y_plus": 3.7}[point.dimensions["tenor"]]
                        if fault == "claim_value"
                        else claim.value
                    ),
                    value_state=claim.value_state,
                    unit=claim.unit,
                    provider=claim.provider,
                    source_reference=(
                        claim.source_reference + ":wrong"
                        if fault == "claim_reference"
                        else claim.source_reference
                    ),
                    release_event_id=ingested.release_event_id
                    + (":synthetic-public" if fault == "claim_public" else ""),
                    release_at=claim.release_at,
                    public_available_at=(
                        claim.public_available_at + timedelta(minutes=1)
                        if fault == "claim_public"
                        else claim.public_available_at
                    ),
                    fetched_at=claim.fetched_at,
                    available_at=(
                        claim.available_at + timedelta(seconds=1)
                        if fault.startswith("claim_")
                        else claim.available_at
                    ),
                    certification_status=claim.certification_status,
                    quality_status=claim.quality_status,
                    acquisition_id=malformed.acquisition_id,
                )
            )
            assert (linked.claim_id == claim.claim_id) is (not fault.startswith("claim_"))

    if consumer == "selection":
        after = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert not after.complete
        assert after.selected_claim_ids == ()
    else:
        after_context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=acquired_at,
            model_manifest=manifest,
            as_of_mode=AsOfMode.PUBLIC,
        )
        rows = [
            row
            for row in after_context.macro["credit"]["evidence"]  # type: ignore[index]
            if row["metric_id"] == "CN_LPR_1Y_5Y"
        ]
        assert {row["status"] for row in rows} == {"source_failed"}
        model_inputs = after_context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert not set(ingested.claim_ids) & set(model_inputs)
        # Diagnostic references remain visible without becoming model inputs.
        assert set(ingested.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
@pytest.mark.parametrize("later_revision", [False, True])
def test_lpr_public_replay_rechecks_selected_acquisition_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    artifact_kind: str,
    damage: str,
    later_revision: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    claims = {}
    acquisitions = {}
    acquired_at = datetime(2026, 8, 20, 2, tzinfo=UTC)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id="CN_LPR_1Y_5Y")
        # Exercise the public component replay; the full model still lacks its
        # core and 120-day evidence. The stored admitted manifest is unchanged.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        ingested = ingest_lpr_document(
            paths,
            content + b"<!-- synthetic candidate retrieval -->" if side == "candidate" else content,
            source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
            fetched_at=acquired_at,
            expected_period="2026-08",
            definition_version=manifest["metric_catalog_version"],
            clock=lambda: acquired_at,
        )
        claims[side] = set(ingested.claim_ids)
        (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (ingested.claim_ids[0],)
        )[ingested.claim_ids[0]]
        acquisitions[side] = acquisition.receipt
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not before.gaps, before.gaps
    assert before.evaluated_cutoffs == 1
    assert before.output_document is not None
    for side in ("comparison", "candidate"):
        day = before.output_document["days"][0][side]
        assert set(day["macro"]["model_input_observation_version_ids"]) == claims[side]
    current_claims = claims["candidate"]
    evaluation_day = "2026-08-28"
    if later_revision:
        revised_at = datetime(2026, 8, 31, 2, tzinfo=UTC)
        revised = ingest_lpr_document(
            paths,
            content.replace(b"3.0%", b"3.1%").replace(b"2026-08-20 09:00", b"2026-08-31 09:00"),
            source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
            fetched_at=revised_at,
            expected_period="2026-08",
            definition_version=manifests["candidate"]["metric_catalog_version"],
            clock=lambda: revised_at,
        )
        current_claims = set(revised.claim_ids)
        (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (revised.claim_ids[0],)
        )[revised.claim_ids[0]]
        acquisitions["candidate"] = acquisition.receipt
        evaluation_day = "2026-08-31"
    receipt = acquisitions["candidate"]
    content_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert content_hash is not None
    assert content_hash not in {
        acquisitions["comparison"].raw_hash,
        acquisitions["comparison"].normalized_hash,
    }
    artifact = paths.artifacts / content_hash[:2] / content_hash
    if damage == "changed":
        artifact.write_bytes(b"damaged-lpr-artifact")
    else:
        artifact.unlink()

    if later_revision:
        historical = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert not historical.gaps, historical.gaps
        assert historical.output_document is not None
        historical_ids = historical.output_document["days"][0]["candidate"]["macro"][
            "model_input_observation_version_ids"
        ]
        assert set(historical_ids) == claims["candidate"]
        assert set(historical_ids).isdisjoint(current_claims)

    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start=evaluation_day,
        requested_end=evaluation_day,
    )
    assert after.gaps == ("candidate_context_selection_invalid:CN_LPR_1Y_5Y",)
    assert after.output_document is not None
    day = after.output_document["days"][0]
    assert day["candidate"]["macro"]["model_input_observation_version_ids"] == []
    assert (
        set(day["comparison"]["macro"]["model_input_observation_version_ids"])
        == claims["comparison"]
    )
    assert current_claims <= set(day["candidate"]["observation_version_ids"])
    rows = day["candidate"]["macro"]["credit"]["evidence"]
    lpr_rows = [row for row in rows if row["metric_id"] == "CN_LPR_1Y_5Y"]
    assert len(lpr_rows) == 2 and all(row["status"] == "source_failed" for row in lpr_rows)
    assert {row["dimensions"]["tenor"]: row["value"] for row in lpr_rows} == {
        "1y": 3.1 if later_revision else 3.0,
        "5y_plus": 3.5,
    }


@pytest.mark.parametrize(
    "scenario",
    ["date_only", "unknown_public", "same_time_revision", "new_time_revision", "repeat"],
)
def test_registered_lpr_consumers_preserve_publication_precision_and_revisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], scenario: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    first_at = datetime(2026, 8, 20, 2, tzinfo=UTC)
    revised_at = datetime(2026, 8, 21, 2, tzinfo=UTC)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    if scenario == "date_only":
        content = content.replace(b"2026-08-20 09:00", b"2026-08-20")
    elif scenario == "unknown_public":
        content = content.replace(b"<time>2026-08-20 09:00</time>", b"")
    first = ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        fetched_at=first_at,
        expected_period="2026-08",
        definition_version=version,
        clock=lambda: first_at,
    )
    latest = first
    if scenario in {"same_time_revision", "new_time_revision", "repeat"}:
        if scenario != "repeat":
            content = content.replace(b"3.0%", b"3.1%")
        if scenario == "new_time_revision":
            content = content.replace(b"2026-08-20 09:00", b"2026-08-21 09:00")
        latest = ingest_lpr_document(
            paths,
            content,
            source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
            fetched_at=revised_at,
            expected_period="2026-08",
            definition_version=version,
            clock=lambda: revised_at,
        )
    public_ids = (
        set()
        if scenario == "unknown_public"
        else set(first.claim_ids if scenario == "same_time_revision" else latest.claim_ids)
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=revised_at,
            model_manifest=manifest,
            as_of_mode=mode,
        )
        rows = [
            row
            for row in context.macro["credit"]["evidence"]  # type: ignore[index]
            if row["metric_id"] == "CN_LPR_1Y_5Y" and row["value"] is not None
        ]
        expected_values = (
            {}
            if mode is AsOfMode.PUBLIC and scenario == "unknown_public"
            else {
                "1y": 3.1
                if scenario == "new_time_revision"
                or (scenario == "same_time_revision" and mode is AsOfMode.SYSTEM)
                else 3.0,
                "5y_plus": 3.5,
            }
        )
        assert {row["dimensions"]["tenor"]: row["value"] for row in rows} == expected_values
        assert all(row["status"] == "current" for row in rows), (
            mode.value,
            [(row["status"], row["public_available_at"]) for row in rows],
        )
        expected_ids = public_ids if mode is AsOfMode.PUBLIC else set(latest.claim_ids)
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert set(model_inputs) == expected_ids
        if mode is AsOfMode.SYSTEM and scenario in {"unknown_public", "same_time_revision"}:
            assert all(row["public_available_at"] is None for row in rows)
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="lpr-precision-" + mode.value,
            model_version_id=model_id,
            system_as_of=revised_at,
            release_event_id=latest.release_event_id,
            metric_ids=("CN_LPR_1Y_5Y",),
            period="2026-08",
        )
        selection = select_retrieval_input(paths, run, mode=mode)
        assert selection.complete is (scenario != "unknown_public")
        # A historical target still applies its PUBLIC upper bound in SYSTEM mode.
        assert set(selection.selected_claim_ids) == public_ids
    if scenario == "date_only":
        repository = EvidenceRepository(paths.database)
        system = build_context_projection(
            repository, as_of=first_at, model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
        )
        system_inputs = system.macro["model_input_observation_version_ids"]
        assert isinstance(system_inputs, list)
        assert set(system_inputs) == set(first.claim_ids)
        before = build_context_projection(
            repository,
            as_of=first_at - timedelta(microseconds=1),
            model_manifest=manifest,
            as_of_mode=AsOfMode.SYSTEM,
        )
        assert before.macro["model_input_observation_version_ids"] == []
        for cutoff, expected_count in (
            (datetime(2026, 8, 20, 15, 59, 59, tzinfo=UTC), 0),
            (datetime(2026, 8, 20, 16, tzinfo=UTC), 2),
        ):
            points = repository.metric_series(
                "CN_LPR_1Y_5Y", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
            )
            assert len(points) == expected_count


@pytest.mark.parametrize("consumer", ["selection", "context", "ledger"])
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
            if consumer == "ledger":
                RetrievalLedger(paths.database).bind_run(run, manifest["metric_catalog_version"])
            else:
                select_retrieval_input(paths, run)
    if consumer == "ledger":
        assert RetrievalLedger(paths.database).for_run(run.run_id) is None


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


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(("missing_days", "staggered"), [(6, False), (7, False), (6, True)])
def test_warrant_history_coverage_counts_only_complete_daily_warehouses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing_days: int,
    staggered: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    digest = "6e849804171177debebc666eabf63388c21066fe695a06f75f6c2cc47043f120"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-04"
        / f"{digest}.json"
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    required = tuple(
        sorted(
            {date.fromisoformat(row["tradeDate"]).isoformat() for row in json.loads(raw)["data"]}
        )
    )
    assert len(required) == 120
    assert (required[0], required[-1]) == ("2026-03-09", "2026-08-28")
    # Only the date set comes from the saved official index response.
    # All warrant values, publication times, and source certification are synthetic.
    missing = set(required[40 : 40 + missing_days])
    pp_missing = set(required[60:66]) if staggered else set()
    symbols = ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA")

    def transport(payload: dict[str, Any]) -> bytes:
        symbol = str(payload["params"]["symbol"])
        start = date.fromisoformat(payload["params"]["start_date"]).isoformat()
        end = date.fromisoformat(payload["params"]["end_date"]).isoformat()
        unit = "桶" if symbol == "SC" else "张" if symbol in {"CF", "PTA"} else "吨"
        rows = []
        for period in required:
            if start <= period <= end:
                day = period.replace("-", "")
                rows.append(
                    [
                        day,
                        symbol,
                        "synthetic-first",
                        None,
                        None if symbol == "PP" and period in pp_missing else 100,
                        None,
                        unit,
                        "synthetic",
                    ]
                )
                if symbol == "CU":
                    rows.append(
                        [
                            day,
                            symbol,
                            "synthetic-second",
                            None,
                            None if period in missing else 25,
                            None,
                            unit,
                            "synthetic",
                        ]
                    )
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": [
                        "trade_date",
                        "symbol",
                        "warehouse",
                        "pre_vol",
                        "vol",
                        "vol_chg",
                        "unit",
                        "exchange",
                    ],
                    "items": rows,
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        return tuple(
            replace(
                scalar,
                release_at=datetime.fromisoformat(f"{scalar.period_end}T09:00:00+00:00"),
                public_available_at=datetime.fromisoformat(f"{scalar.period_end}T09:00:00+00:00"),
            )
            for symbol in symbols
            for scalar in adapter.futures_warrants(
                start_date=date(2026, 3, 9), end_date=date(2026, 8, 28), symbol=symbol
            )
        )

    adapter.acquire_scalars(paths, retrieve, definition_version=version)
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 28, 9, tzinfo=UTC),
        as_of_mode=AsOfMode.PUBLIC,
        model_manifest=ModelRepository(paths.database).manifest(model_id),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
    )
    coverage = context.warrant_history
    assert coverage is not None
    assert len(coverage.complete_periods["CU"]) == (114 if missing_days == 6 else 113)
    assert len(coverage.complete_periods["PP"]) == (114 if staggered else 120)
    assert all(
        len(coverage.complete_periods[symbol]) == 120
        for symbol in symbols
        if symbol not in {"CU", "PP"}
    )
    if staggered:
        assert (
            len(set(coverage.complete_periods["CU"]) & set(coverage.complete_periods["PP"])) == 108
        )
    assert missing.isdisjoint(coverage.complete_periods["CU"])
    assert coverage.is_ready(required) is (missing_days == 6)
    assert not coverage.is_ready(required[:-1])
    assert not coverage.is_ready((*required[:-1], required[-2]))


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("fault", ["changed", "missing"])
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_core_history_preserves_originals_and_unknown_public(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fault: str,
    artifact_kind: str,
) -> None:
    from pring_cycle.core_history import refresh_core_history
    from pring_cycle.runs import RetrievalScope
    from pring_cycle.search_evidence import ModelInputSelector
    from pring_cycle.source_adapters import TushareCoreAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    identities = {
        "CN_EQUITY_CORE_000985": ("index_daily", "000985.CSI"),
        "CN_BOND_CORE_000012": ("index_daily", "000012.SH"),
        "CN_COMMODITY_CORE_NHII": ("fut_index_daily", "NHII.NH"),
    }
    originals: dict[str, bytes] = {}
    calls: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["params"]["start_date"] == payload["params"]["end_date"] == "20260828"
        if payload["api_name"] == "trade_cal":
            key = "calendar"
            fields = ["cal_date", "is_open"]
            rows = [["20260828", 1]]
        else:
            key = str(payload["params"]["ts_code"])
            fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
            rows = [[key, "20260828", 101, 100, 0.01 if key == "NHII.NH" else 1]]
        calls.append(key)
        raw = encode({"code": 0, "data": {"fields": fields, "items": rows}})
        originals[key] = raw
        return raw

    before = datetime.now(UTC)
    result = refresh_core_history(
        paths,
        TushareCoreAdapter("synthetic-core-token", transport=transport),
        start=date(2026, 8, 28),
        end=date(2026, 8, 28),
        definition_version=version,
    )
    assert result.status == "validated"
    assert result.network_requests == 4
    assert calls == ["calendar", "000985.CSI", "000012.SH", "NHII.NH"]
    after = datetime.now(UTC)
    evidence = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    selected_ids = set()
    for metric_id, (api, code) in identities.items():
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
            )
            == ()
        )
        (point,) = evidence.metric_series(
            metric_id, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
        )
        assert point.selected_value == 101
        (claim,) = point.claims
        selected_ids.add(claim.claim_id)
        assert claim.public_available_at is None and claim.release_at is None
        assert claim.source_reference == f"tushare:{api}:{code}:2026-08-28"
        (receipt,) = evidence.trace(
            point.observation_id, mode=AsOfMode.SYSTEM, as_of=after
        ).acquisitions
        assert receipt.parameters["ts_code"] == code and receipt.api_name == api
        assert receipt.state == "validated" and claim.fetched_at == receipt.received_at
        assert receipt.validated_at is not None and claim.available_at >= receipt.validated_at
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == originals[code]
        (normalized,) = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
        assert (normalized["close"], normalized["pre_close"], normalized["official_return"]) == (
            101,
            100,
            0.01,
        )
        assert "synthetic-core-token" not in repr(receipt)
    assert len(acquisitions.history()) == 4
    # Isolated candidate input evaluation; no activation, publication or actual calibration.
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="synthetic-new-core-inputs",
        model_version_id=model_id,
        system_as_of=after,
        cutoff_mode="explicit",
    )
    scope = RetrievalScope("synthetic:core", tuple(identities), "2026-08-28", "P0", None)
    selector = ModelInputSelector(paths, run, mode=AsOfMode.SYSTEM)
    system = selector.select(scope)
    assert system.complete and set(system.selected_claim_ids) == selected_ids
    public = ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope)
    assert not public.complete and public.selected_claim_ids == ()

    (stock,) = evidence.metric_series(
        "CN_EQUITY_CORE_000985", mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
    )
    assert stock.selected_claim_id is not None
    ((receipt, _),) = evidence.source_claim_originals(stock.selected_claim_id)
    artifact_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert artifact_hash is not None
    content = acquisitions.read_content(receipt.acquisition_id, artifact_kind)
    artifact = paths.artifacts / artifact_hash[:2] / artifact_hash
    if fault == "changed":
        artifact.write_bytes(b"damaged after admission")
    else:
        artifact.unlink()
    assert evidence.source_claim_originals(stock.selected_claim_id) == ()
    # Every new public selection must recheck originals, even on the same selector.
    for current in (selector, ModelInputSelector(paths, run, mode=AsOfMode.SYSTEM)):
        rejected = current.select(scope)
        assert not rejected.complete
        assert set(rejected.selected_claim_ids) == selected_ids - {stock.selected_claim_id}
    artifact.write_bytes(content)
    assert selector.select(scope).complete


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "missing_original",
        "wrong_original",
        "forged_value",
        "wrong_code",
        "missing_period_null",
        "wrong_normalized",
        "missing_normalized",
    ],
)
def test_registered_core_claim_requires_its_exact_original(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fault: str,
) -> None:
    from pring_cycle.core_history import refresh_core_history
    from pring_cycle.source_adapters import TushareCoreAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        if payload["api_name"] == "trade_cal":
            fields = ["cal_date", "is_open"]
            rows = [["20260828", 1]]
        else:
            code = payload["params"]["ts_code"]
            fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
            rows = [[code, "20260828", 101, 100, 0.01 if code == "NHII.NH" else 1]]
        return encode({"code": 0, "data": {"fields": fields, "items": rows}})

    refresh_core_history(
        paths,
        TushareCoreAdapter("synthetic-core-token", transport=transport),
        start=date(2026, 8, 28),
        end=date(2026, 8, 28),
        definition_version=version,
    )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    receipt = next(
        r
        for r in receipts
        if r.parameters.get("ts_code")
        == ("000012.SH" if fault == "wrong_original" else "000985.CSI")
    )
    if fault == "wrong_normalized":
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        raw = acquisitions.read_content(receipt.acquisition_id, "raw")
        receipt = acquisitions.capture(
            provider=receipt.provider,
            api_name=receipt.api_name,
            parameters=receipt.parameters,
            fields=receipt.fields,
            parser_version=receipt.parser_version,
            fetch=lambda: raw,
            parse=json.loads,
            normalize=lambda document: [],
        ).receipt
        assert acquisitions.read_content(receipt.acquisition_id, "normalized") == b"[]"
    elif fault == "missing_normalized":
        assert receipt.normalized_hash is not None
        (paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash).unlink()
    assert receipt.received_at is not None and receipt.validated_at is not None
    expected = (
        "registered_core_source_identity_mismatch"
        if fault == "wrong_code"
        else "registered_core_source_original_required"
        if fault == "missing_original"
        else "registered_core_source_original_mismatch"
    )
    evidence = EvidenceRepository(paths.database)
    period = "2026-08-27" if fault == "missing_period_null" else "2026-08-28"
    with pytest.raises(ValueError, match=expected):
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id="CN_EQUITY_CORE_000985",
                definition_version=version,
                period_kind="business_day",
                period_start=period,
                period_end=period,
                dimensions={},
                value=None
                if fault == "missing_period_null"
                else 999
                if fault == "forged_value"
                else 101,
                value_state=EvidenceValueState.NOT_DISCLOSED
                if fault == "missing_period_null"
                else EvidenceValueState.REPORTED_VALUE,
                unit="index_points",
                provider="tushare",
                source_reference=(
                    "tushare:index_daily:000012CNY030.CSI:2026-08-28"
                    if fault == "wrong_code"
                    else f"tushare:index_daily:000985.CSI:{period}"
                ),
                release_event_id=f"synthetic:invalid-core:{fault}",
                release_at=None,
                public_available_at=None,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_id=None if fault == "missing_original" else receipt.acquisition_id,
            )
        )
    (point,) = evidence.metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert point.selected_value == 101 and len(point.claims) == 1


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("fault", ["changed", "missing"])
@pytest.mark.parametrize("original_case", ["base", "late_revision", "one_of_two"])
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_core_public_replay_rechecks_selected_originals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    original_case: str,
    artifact_kind: str,
) -> None:
    from pring_cycle.model_evaluation import evaluate_history
    from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    days: list[date] = []
    current = date(2026, 1, 5)
    while len(days) < 168:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = EvidenceRepository(paths.database)
    claims: list[SourceClaimInput] = []
    damaged_hash = ""
    tracked_originals: set[Path] = set()
    late_revision = original_case == "late_revision"
    # Synthetic PUBLIC declarations and weekday calendar; no real source is certified.
    for metric_id, (api, code) in CORE_API_IDENTITIES.items():
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                    "items": [
                        [code, day.strftime("%Y%m%d"), 100 + i, 99 + i, 0]
                        for i, day in enumerate(days)
                    ],
                },
            }
        )

        def core_response(payload: dict[str, Any], body: bytes = raw) -> bytes:
            return body

        acquired = TushareCoreAdapter("synthetic-token", transport=core_response).acquire_core_bars(
            acquisitions,
            metric_id,
            start=days[0],
            end=days[-1],
            expected_business_dates=tuple(days),
        )
        receipt = acquired.receipt
        assert receipt.received_at is not None and receipt.validated_at is not None
        assert receipt.raw_hash is not None
        fetched_at = receipt.received_at
        tracked_originals.add(paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash)
        if metric_id == "CN_BOND_CORE_000012":
            selected_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
            assert selected_hash is not None
            damaged_hash = selected_hash
        extra_ids: tuple[str, ...] = ()
        if metric_id == "CN_BOND_CORE_000012" and original_case == "one_of_two":
            # Two distinct physical deliveries support each claim; both must stay valid.
            def second_response(payload: dict[str, Any], body: bytes = raw) -> bytes:
                document = json.loads(body)
                document["data"]["items"][0][3] = 98
                return encode(document)

            extra = (
                TushareCoreAdapter("synthetic-token", transport=second_response)
                .acquire_core_bars(
                    acquisitions,
                    metric_id,
                    start=days[0],
                    end=days[-1],
                    expected_business_dates=tuple(days),
                )
                .receipt
            )
            assert extra.raw_hash is not None and extra.validated_at is not None
            assert extra.received_at is not None
            fetched_at = extra.received_at
            extra_ids = (extra.acquisition_id,)
            selected_hash = extra.raw_hash if artifact_kind == "raw" else extra.normalized_hash
            assert selected_hash is not None
            assert extra.raw_hash != receipt.raw_hash
            assert extra.normalized_hash != receipt.normalized_hash
            damaged_hash = selected_hash
            tracked_originals.add(paths.artifacts / extra.raw_hash[:2] / extra.raw_hash)
        for i, day in enumerate(days):
            published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
            claims.append(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version=version,
                    period_kind="business_day",
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    dimensions={},
                    value=100 + i,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="tushare",
                    source_reference=f"tushare:{api}:{code}:{day.isoformat()}",
                    release_event_id=f"synthetic:core-public:{metric_id}:{day.isoformat()}",
                    release_at=published,
                    public_available_at=published,
                    fetched_at=fetched_at,
                    available_at=datetime.now(UTC),
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                    acquisition_ids=extra_ids,
                )
            )
    evidence.append_source_claims(tuple(claims))
    if late_revision:
        revised = next(
            c
            for c in claims
            if c.metric_id == "CN_BOND_CORE_000012" and c.period_end == days[20].isoformat()
        )
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                    "items": [["000012.SH", days[20].strftime("%Y%m%d"), 100000, 119, 0]],
                },
            }
        )
        receipt = (
            TushareCoreAdapter("synthetic-token", transport=lambda payload: raw)
            .acquire_core_bars(
                acquisitions,
                revised.metric_id,
                start=days[20],
                end=days[20],
                expected_business_dates=(days[20],),
            )
            .receipt
        )
        assert receipt.raw_hash is not None
        assert receipt.received_at is not None and receipt.validated_at is not None
        selected_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
        assert selected_hash is not None
        damaged_hash = selected_hash
        tracked_originals.add(paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash)
        published = datetime(days[-1].year, days[-1].month, days[-1].day, 8, tzinfo=UTC)
        evidence.append_source_claim(
            replace(
                revised,
                value=100000,
                release_event_id="synthetic:core-public:late-revision",
                release_at=published,
                public_available_at=published,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                acquisition_id=receipt.acquisition_id,
            )
        )
    reads = dict.fromkeys(tracked_originals, 0)
    real_read = Path.read_bytes

    def observed_read(path: Path) -> bytes:
        content = real_read(path)
        if path in reads:
            reads[path] += 1
        return content

    # Transparent filesystem counting; the actual bytes and parser still run.
    with monkeypatch.context() as boundary:
        boundary.setattr(Path, "read_bytes", observed_read)
        before = evaluate_history(
            paths.database,
            model_id,
            requested_start=days[-2].isoformat(),
            requested_end=days[-1].isoformat(),
        )
    assert before.evaluated_days == 2 and before.input_days == 168
    assert set(reads.values()) == {1}
    assert before.core_states_by_day[days[-2].isoformat()] == ("bull", "bull", "bull")
    artifact = paths.artifacts / damaged_hash[:2] / damaged_hash
    if fault == "changed":
        artifact.write_bytes(b"damaged after admission")
    else:
        artifact.unlink()
    if late_revision:
        earlier = evaluate_history(
            paths.database,
            model_id,
            requested_start=days[-2].isoformat(),
            requested_end=days[-2].isoformat(),
        )
        assert earlier.core_states_by_day[days[-2].isoformat()] == ("bull", "bull", "bull")
    with pytest.raises(ValueError, match="calibration_core_original_invalid"):
        evaluate_history(
            paths.database,
            model_id,
            requested_start=days[-2].isoformat(),
            requested_end=days[-1].isoformat(),
        )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_api_keeps_both_series_and_unknown_public_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.eia_context import EiaPetroleumAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    admitted = json.loads(capsys.readouterr().out)
    assert admitted["status"] == "candidate"
    manifest = models.manifest(admitted["model_version_id"])
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    raw = encode(
        {
            "response": {
                "frequency": "daily",
                "data": [
                    {
                        "period": "2026-08-27",
                        "series": series,
                        "series-description": label,
                        "value": value,
                        "units": "Dollars per Barrel",
                    }
                    for series, label, value in (
                        ("RBRTE", "Europe Brent Spot Price FOB", "71.25"),
                        ("RWTC", "Cushing, OK WTI Spot Price FOB", "66.50"),
                    )
                ],
            }
        }
    )
    adapter = EiaPetroleumAdapter("synthetic-api-key", transport=lambda _: raw)
    before = datetime.now(UTC)
    result = adapter.acquire_spot_prices(
        paths,
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
        definition_version=version,
    )
    after = datetime.now(UTC)
    assert result.observation_count == 2
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.api_name == "eia_spot_prices"
    assert receipt.state == "validated"
    assert "api_key" not in receipt.parameters
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert before <= receipt.started_at <= receipt.received_at <= receipt.validated_at <= after
    evidence = EvidenceRepository(paths.database)
    for metric, value in (("EIA_BRENT_RBRTE", 71.25), ("EIA_WTI_RWTC", 66.50)):
        assert (
            evidence.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        assert (
            evidence.metric_series(
                metric, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
            )
            == ()
        )
        (point,) = evidence.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
        )
        assert point.observation_id in result.observation_ids
        (claim,) = point.claims
        assert claim.value == value and claim.unit == "usd_per_barrel"
        assert claim.certification_status == "awaiting_source_certification"
        assert claim.release_at is None and claim.public_available_at is None
        assert claim.fetched_at == receipt.received_at
        assert receipt.validated_at <= claim.available_at <= after
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
        assert tuple(item.acquisition_id for item in trace.acquisitions) == (
            receipt.acquisition_id,
        )
    assert (
        next(
            model
            for model in models.list_versions()
            if model.model_version_id == admitted["model_version_id"]
        ).status
        == "candidate"
    )


@pytest.mark.parametrize(
    ("case", "exception_type", "message"),
    [
        ("missing_key", ValueError, "eia_api_key_required"),
        ("source_failed", OSError, "synthetic_eia_unavailable"),
        ("invalid_response", ValueError, "eia_response_json_invalid"),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_api_failure_keeps_receipt_without_claims(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
    exception_type: type[Exception],
    message: str,
) -> None:
    from pring_cycle.eia_context import EiaPetroleumAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = b"not JSON"

    def transport(parameters: dict[str, object]) -> bytes:
        if case == "source_failed":
            raise OSError("synthetic_eia_unavailable")
        return raw

    with pytest.raises(exception_type, match=message):
        adapter = EiaPetroleumAdapter(
            "" if case == "missing_key" else "synthetic-api-key", transport=transport
        )
        adapter.acquire_spot_prices(
            paths,
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 27),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    if case == "missing_key":
        assert acquisitions.history() == ()
    else:
        (receipt,) = acquisitions.history()
        assert receipt.api_name == "eia_spot_prices"
        assert receipt.state == "failed" and receipt.error_type == exception_type.__name__
        assert receipt.normalized_hash is None and receipt.validated_at is None
        assert "api_key" not in receipt.parameters
        if case == "source_failed":
            assert receipt.raw_hash is None and receipt.received_at is None
        else:
            assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
            assert receipt.received_at is not None
    evidence = EvidenceRepository(paths.database)
    for metric in ("EIA_BRENT_RBRTE", "EIA_WTI_RWTC"):
        assert (
            evidence.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_html_cli_keeps_receipt_and_unknown_public_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    admitted = json.loads(capsys.readouterr().out)
    assert admitted["status"] == "candidate"
    models = ModelRepository(paths.database)
    manifest = models.manifest(admitted["model_version_id"])
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    digest = "b078a362332a3d6b34ae2a5dc5a91b98ddfacc7979410b32081f07e9dadc243e"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-14" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def geturl(self) -> str:
            return "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"

    def fetch(request: Any, *, timeout: float) -> Response:
        assert request.full_url == "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
        assert timeout > 0
        return Response(raw)

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fetch)
    before = datetime.now(UTC)
    main(
        [
            "eia-html-refresh",
            "--runtime-root",
            str(paths.override_root),
            "--series",
            "RBRTE",
            "--start",
            "2026-08-31",
            "--end",
            "2026-09-04",
            "--definition-version",
            version,
            "--json",
        ]
    )
    after = datetime.now(UTC)
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "stored_candidate"
    assert result["observation_count"] == 1 and result["missing_cell_count"] == 4
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.api_name == "eia_history_html" and receipt.state == "validated"
    assert receipt.parameters["definition_version"] == version
    assert receipt.raw_hash == digest
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["release_date"] == "2026-09-02"
    assert normalized["next_release_date"] == "2026-09-10"
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert before <= receipt.started_at <= receipt.received_at <= receipt.validated_at <= after
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "EIA_BRENT_RBRTE", mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
        )
        == ()
    )
    assert (
        evidence.metric_series(
            "EIA_BRENT_RBRTE", mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
        )
        == ()
    )
    (point,) = evidence.metric_series(
        "EIA_BRENT_RBRTE", mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
    )
    assert point.period_start == point.period_end == "2026-09-01"
    (claim,) = point.claims
    assert claim.value == 96.02 and claim.unit == "usd_per_barrel"
    assert claim.certification_status == "awaiting_source_certification"
    assert claim.release_at is None and claim.public_available_at is None
    assert claim.fetched_at == receipt.received_at
    assert receipt.validated_at <= claim.available_at <= after
    trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
    assert tuple(item.acquisition_id for item in trace.acquisitions) == (receipt.acquisition_id,)
    assert (
        next(
            model
            for model in models.list_versions()
            if model.model_version_id == admitted["model_version_id"]
        ).status
        == "candidate"
    )


@pytest.mark.parametrize("outcome", ["source_failed", "validation_failed"])
@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_eia_html_cli_failure_keeps_classified_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = b"<html><body>Synthetic malformed history</body></html>"

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def geturl(self) -> str:
            return "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"

    def fetch(request: Any, *, timeout: float) -> Response:
        assert request.full_url == "https://www.eia.gov/dnav/pet/hist/RBRTED.htm"
        if outcome == "source_failed":
            raise OSError("synthetic_eia_unavailable")
        return Response(raw)

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fetch)
    with pytest.raises(OSError if outcome == "source_failed" else SystemExit) as failure:
        main(
            [
                "eia-html-refresh",
                "--runtime-root",
                str(paths.override_root),
                "--series",
                "RBRTE",
                "--start",
                "2026-08-31",
                "--end",
                "2026-09-04",
                "--definition-version",
                version,
                "--json",
            ]
        )
    if outcome == "source_failed":
        assert isinstance(failure.value, OSError)
        assert str(failure.value) == "synthetic_eia_unavailable"
    else:
        assert isinstance(failure.value, SystemExit)
        assert failure.value.code == 2
        assert "eia_history_" in capsys.readouterr().err
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.api_name == "eia_history_html" and receipt.state == "failed"
    assert receipt.normalized_hash is None and receipt.validated_at is None
    assert receipt.parameters["definition_version"] == version
    if outcome == "source_failed":
        assert receipt.error_type == "OSError"
        assert receipt.raw_hash is None and receipt.received_at is None
    else:
        assert receipt.error_type == "ValueError"
        assert receipt.received_at is not None
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "EIA_BRENT_RBRTE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )
    attempt = evidence.latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-09-04",
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert attempt is not None and attempt.outcome == outcome
    assert attempt.safe_metadata["acquisition_ids"] == receipt.acquisition_id
    assert attempt.safe_metadata["error_type"] == receipt.error_type


@pytest.mark.usefixtures("runtime_clock")
def test_registered_margin_acquisition_keeps_three_exchange_totals_and_raw_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    admitted = json.loads(capsys.readouterr().out)
    models = ModelRepository(paths.database)
    manifest = models.manifest(admitted["model_version_id"])
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    ["20260828", "SSE", 100_000_000, 10_000_000],
                    ["20260828", "SZSE", 200_000_000, 20_000_000],
                    ["20260828", "BSE", 300_000_000, 30_000_000],
                ],
            },
        }
    )
    requests = []

    def transport(payload: dict[str, Any]) -> bytes:
        requests.append(payload["api_name"])
        assert payload["api_name"] == "margin"
        assert payload["fields"] == "trade_date,exchange_id,rzye,rzmre"
        assert payload["params"] == {"start_date": "20260828", "end_date": "20260828"}
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    before = datetime.now(UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.margin_financing(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version=version,
    )
    after = datetime.now(UTC)
    assert requests == ["margin"]
    assert result.observation_count == 2
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "validated" and receipt.api_name == "margin"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "CN_MARGIN_BALANCE", mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
        )
        == ()
    )
    assert (
        evidence.metric_series(
            "CN_MARGIN_BALANCE", mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
        )
        == ()
    )
    points = evidence.metric_series(
        "CN_MARGIN_BALANCE", mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
    )
    assert {(p.dimensions["measure"], p.selected_value) for p in points} == {
        ("financing_balance", 6.0),
        ("financing_buy_amount", 0.6),
    }
    for point in points:
        assert point.dimensions["scope"] == "all_exchanges"
        (claim,) = point.claims
        assert claim.unit == "hundred_million_cny"
        assert claim.release_at is None and claim.public_available_at is None
        assert claim.fetched_at == receipt.received_at
        assert (
            receipt.validated_at is not None and receipt.validated_at <= claim.available_at <= after
        )
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
        assert tuple(r.acquisition_id for r in trace.acquisitions) == (receipt.acquisition_id,)
    assert (
        next(
            m for m in models.list_versions() if m.model_version_id == admitted["model_version_id"]
        ).status
        == "candidate"
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "missing_exchange",
        "duplicate_exchange",
        "wrong_unit",
        "wrong_value",
        "wrong_scope",
        "bad_response",
        "missing_value",
        "negative_value",
        "wrong_period",
        "wrong_exchange",
    ],
)
def test_registered_margin_rejects_invalid_delivery_with_failed_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    rows: list[list[Any]] = [
        ["20260828", "SSE", 100_000_000, 10_000_000],
        ["20260828", "SZSE", 200_000_000, 20_000_000],
        ["20260828", "BSE", 300_000_000, 30_000_000],
    ]
    if fault == "wrong_period":
        for row in rows:
            row[0] = "20260827"
    elif fault == "wrong_exchange":
        rows[-1][1] = "NYSE"
    elif fault == "missing_exchange":
        rows.pop()
    elif fault == "duplicate_exchange":
        rows.append(rows[-1].copy())
    elif fault == "missing_value":
        rows[-1][-1] = None
    elif fault == "negative_value":
        rows[-1][-1] = -30_000_000
    raw = (
        b"not JSON"
        if fault == "bad_response"
        else encode(
            {
                "code": 0,
                "data": {"fields": ["trade_date", "exchange_id", "rzye", "rzmre"], "items": rows},
            }
        )
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.margin_financing(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        if fault == "wrong_unit":
            return tuple(replace(s, unit="cny") for s in scalars)
        if fault == "wrong_value":
            return (replace(scalars[0], value=60), *scalars[1:])
        if fault == "wrong_scope":
            return tuple(
                replace(s, dimensions={**s.dimensions, "scope": "SSE+SZSE"}) for s in scalars
            )
        return scalars

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert receipt.error_type in {"ValueError", "JSONDecodeError"}
    assert receipt.validated_at is None
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_MARGIN_BALANCE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize("damage", ["corrupt", "missing"])
def test_registered_margin_selection_requires_readable_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damage: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    ["20260828", "SSE", 100_000_000, 10_000_000],
                    ["20260828", "SZSE", 200_000_000, 20_000_000],
                    ["20260828", "BSE", 300_000_000, 30_000_000],
                ],
            },
        }
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    # Explicit synthetic publication assertion; not evidence of a real exchange release.
    published = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.margin_financing(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-margin-original-integrity",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:margin",
        metric_ids=("CN_MARGIN_BALANCE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete
    assert set(selection.selected_claim_ids) == set(result.claim_ids)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged source delivery")
    rejected = select_retrieval_input(paths, run)
    assert not rejected.complete
    assert rejected.selected_claim_ids == ()


@pytest.mark.usefixtures("runtime_clock")
def test_registered_margin_public_replay_rejects_damaged_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    receipts = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id="CN_MARGIN_BALANCE")
        # Only the existing public component replay is scoped here. Stored full
        # candidate manifests retain their package bindings and all 61 definitions.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        raw = encode(
            {
                "code": 0,
                "synthetic_side": side,
                "data": {
                    "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                    "items": [
                        ["20260828", "SSE", 100_000_000, 10_000_000],
                        ["20260828", "SZSE", 200_000_000, 20_000_000],
                        ["20260828", "BSE", 300_000_000, 30_000_000],
                    ],
                },
            }
        )

        def transport(payload: dict[str, Any], body: bytes = raw) -> bytes:
            return body

        adapter = TushareContextAdapter("synthetic-token", transport=transport)
        published = datetime(2026, 8, 28, 8, tzinfo=UTC)

        def retrieve(
            source: TushareContextAdapter = adapter, public_at: datetime = published
        ) -> tuple[ContextScalar, ...]:
            return tuple(
                replace(s, release_at=public_at, public_available_at=public_at)
                for s in source.margin_financing(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
                )
            )

        result = adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
        (linked,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (result.claim_ids[0],)
        )[result.claim_ids[0]]
        receipts[side] = linked.receipt
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    digest = receipts["candidate"].raw_hash
    assert digest is not None and digest != receipts["comparison"].raw_hash
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged candidate margin source")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert "candidate_context_selection_invalid:CN_MARGIN_BALANCE" in after.gaps
    assert not any(gap.startswith("comparison_") for gap in after.gaps)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_margin_candidate_selection_respects_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["trade_date", "exchange_id", "rzye", "rzmre"],
                "items": [
                    ["20260828", "SSE", 100_000_000, 10_000_000],
                    ["20260828", "SZSE", 200_000_000, 20_000_000],
                    ["20260828", "BSE", 300_000_000, 30_000_000],
                ],
            },
        }
    )
    # These are synthetic time assertions to exercise the two existing query modes.
    published = (
        None
        if publication == "unknown"
        else datetime(2026, 8, 31 if publication == "future" else 28, 8, tzinfo=UTC)
    )
    adapter = TushareContextAdapter("synthetic-token", transport=lambda _: raw)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.margin_financing(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    assert (
        repository.metric_series(
            "CN_MARGIN_BALANCE",
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 7, tzinfo=UTC),
            definition_version=version,
        )
        == ()
    )
    visible = repository.metric_series(
        "CN_MARGIN_BALANCE",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=version,
    )
    assert len(visible) == (2 if publication == "known" else 0)
    assert (
        len(
            repository.metric_series(
                "CN_MARGIN_BALANCE",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )
        == 2
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-margin-publication",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:margin-publication",
        metric_ids=("CN_MARGIN_BALANCE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete is (publication == "known")
    assert set(selection.selected_claim_ids) == (
        set(result.claim_ids) if publication == "known" else set()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_market_indices_keep_each_identity_value_and_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    models = ModelRepository(paths.database)
    manifest = models.manifest(model_id)
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    # Independent synthetic identities and closing points, never real certification.
    expected = {
        "CN_EQ_CSI300": ("index_daily", "000300.SH", 3000.25),
        "CN_EQ_CSI500": ("index_daily", "000905.SH", 5000.5),
        "CN_EQ_CSI1000": ("index_daily", "000852.SH", 6000.75),
        "CN_BOND_FULL_PRICE_CNY030": ("index_daily", "000012CNY030.CSI", 123.45),
        "CN_BOND_10Y_930916": ("index_daily", "930916.CSI", 234.56),
        "CN_COMMODITY_BROAD_NHCI": ("fut_index_daily", "NHCI.NH", 2100.125),
    }
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        source_code = payload["params"]["ts_code"]
        api_name, _, value = next(row for row in expected.values() if row[1] == source_code)
        assert payload["api_name"] == api_name
        assert payload["fields"] == "ts_code,trade_date,close"
        assert payload["params"] == {
            "ts_code": source_code,
            "start_date": "20260828",
            "end_date": "20260828",
        }
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[source_code, "20260828", value]],
                },
            }
        )
        originals[source_code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    before = datetime.now(UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_indices(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version=version,
    )
    after = datetime.now(UTC)
    assert result.observation_count == 6
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 6
    evidence = EvidenceRepository(paths.database)
    for metric_id, (api_name, source_code, value) in expected.items():
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
            )
            == ()
        )
        (point,) = evidence.metric_series(
            metric_id, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
        )
        assert point.selected_value == value
        assert point.period_start == point.period_end == "2026-08-28"
        assert point.dimensions == {"source_code": source_code}
        (claim,) = point.claims
        assert claim.unit == "index_points"
        assert claim.source_reference == f"tushare:{api_name}:close:2026-08-28"
        assert claim.public_available_at is None and claim.release_at is None
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
        (receipt,) = trace.acquisitions
        assert receipt.state == "validated" and receipt.api_name == api_name
        assert receipt.parameters["ts_code"] == source_code
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == originals[source_code]
    assert models.manifest(model_id) == manifest


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("source_code", ["000905.SH", "NHCI.NH"])
def test_registered_market_indices_reject_duplicate_day_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source_code: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        rows = [[code, "20260828", 123.5]]
        if code == source_code:
            rows.append(rows[0].copy())
        raw = encode(
            {"code": 0, "data": {"fields": ["ts_code", "trade_date", "close"], "items": rows}}
        )
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            ),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert any(r.parameters["ts_code"] == source_code for r in receipts)
    for receipt in receipts:
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("source_code", ["000905.SH", "NHCI.NH"])
@pytest.mark.parametrize(
    "fault",
    [
        "wrong_unit",
        "wrong_value",
        "wrong_scope",
        "missing_member",
        "wrong_identity",
        "wrong_period",
        "missing_value",
        "bad_response",
    ],
)
def test_registered_market_indices_reject_invalid_delivery_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], source_code: str, fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        row: list[Any] = [code, "20260828", 123.5]
        if code == source_code:
            if fault == "wrong_identity":
                row[0] = "unexpected-index"
            elif fault == "wrong_period":
                row[1] = "20260827"
            elif fault == "missing_value":
                row[2] = None
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [row],
                },
            }
        )
        if code == source_code and fault == "bad_response":
            raw = b"not JSON"
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.market_indices(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        delivered = []
        for scalar in scalars:
            if scalar.dimensions["source_code"] == source_code:
                if fault == "missing_member":
                    continue
                if fault == "wrong_unit":
                    scalar = replace(scalar, unit="percent")
                elif fault == "wrong_value":
                    scalar = replace(scalar, value=1235.0)
                elif fault == "wrong_scope":
                    scalar = replace(scalar, dimensions={"source_code": "000300.SH"})
            delivered.append(scalar)
        return tuple(delivered)

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert any(r.parameters["ts_code"] == source_code for r in acquisitions.history())
    for receipt in acquisitions.history():
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
            == ()
        )


@pytest.mark.parametrize("damage", ["corrupt", "missing"])
@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "metric_id,source_code", [("CN_EQ_CSI500", "000905.SH"), ("CN_COMMODITY_BROAD_NHCI", "NHCI.NH")]
)
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_market_index_selection_requires_its_originals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    metric_id: str,
    source_code: str,
    artifact_kind: str,
    damage: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[payload["params"]["ts_code"], "20260828", 123.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic publication assertion, not historical official publication evidence.
    published = datetime(2026, 8, 28, 8, tzinfo=UTC)
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=published, public_available_at=published)
            for s in adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    runs = {}
    for selected in (metric_id, "CN_EQ_CSI300"):
        runs[selected] = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="synthetic-index-original-" + selected,
            model_version_id=model_id,
            system_as_of=datetime.now(UTC),
            release_event_id="synthetic:index",
            metric_ids=(selected,),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, runs[selected])
        assert selection.complete and len(selection.selected_claim_ids) == 1
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters["ts_code"] == source_code
    )
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged index original")
    rejected = select_retrieval_input(paths, runs[metric_id])
    assert not rejected.complete and rejected.selected_claim_ids == ()
    assert select_retrieval_input(paths, runs["CN_EQ_CSI300"]).complete


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "metric_id,source_code", [("CN_EQ_CSI500", "000905.SH"), ("CN_COMMODITY_BROAD_NHCI", "NHCI.NH")]
)
def test_registered_market_index_public_replay_rejects_damaged_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], metric_id: str, source_code: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    receipts = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id=metric_id)
        # Public component replay only; stored candidates retain all 61 definitions.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest

        def transport(payload: dict[str, Any], synthetic_side: str = side) -> bytes:
            return encode(
                {
                    "code": 0,
                    "synthetic_side": synthetic_side,
                    "data": {
                        "fields": ["ts_code", "trade_date", "close"],
                        "items": [[payload["params"]["ts_code"], "20260828", 123.5]],
                    },
                }
            )

        adapter = TushareContextAdapter("synthetic-token", transport=transport)
        published = datetime(2026, 8, 28, 8, tzinfo=UTC)

        def retrieve(
            source: TushareContextAdapter = adapter, public_at: datetime = published
        ) -> tuple[ContextScalar, ...]:
            return tuple(
                replace(s, release_at=public_at, public_available_at=public_at)
                for s in source.market_indices(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
                )
            )

        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
        receipts[side] = next(
            r
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.parameters["ts_code"] == source_code
            and side.encode()
            in AcquisitionRepository(paths.database, paths.artifacts).read_content(
                r.acquisition_id, "raw"
            )
        )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    digest = receipts["candidate"].raw_hash
    assert digest is not None and digest != receipts["comparison"].raw_hash
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged candidate index source")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert f"candidate_context_selection_invalid:{metric_id}" in after.gaps
    assert not any(gap.startswith("comparison_") for gap in after.gaps)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_market_indices_respect_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    before = datetime(2026, 8, 28, 7, tzinfo=UTC)
    cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    public_at = (
        None
        if publication == "unknown"
        else cutoff
        if publication == "known"
        else datetime(2026, 8, 28, 9, tzinfo=UTC)
    )

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[payload["params"]["ts_code"], "20260828", 123.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Explicitly synthetic publication metadata; official historical evidence remains open.
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    for metric_id in (
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    ):
        assert (
            evidence.metric_series(
                metric_id, mode=AsOfMode.PUBLIC, as_of=before, definition_version=version
            )
            == ()
        )
        visible = evidence.metric_series(
            metric_id, mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
        )
        assert len(visible) == (1 if publication == "known" else 0)
        assert (
            len(
                evidence.metric_series(
                    metric_id,
                    mode=AsOfMode.SYSTEM,
                    as_of=datetime.now(UTC),
                    definition_version=version,
                )
            )
            == 1
        )
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="synthetic-index-time-" + metric_id,
            model_version_id=model_id,
            system_as_of=cutoff,
            release_event_id="synthetic:index",
            metric_ids=(metric_id,),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert selection.complete is (publication == "known")
        assert len(selection.selected_claim_ids) == (1 if publication == "known" else 0)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_valuation_keeps_all_nine_static_members_and_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    models = ModelRepository(paths.database)
    manifest = models.manifest(model_id)
    assert len(manifest["metric_definitions"]) == 61
    version = manifest["metric_catalog_version"]
    expected = {
        "000300.SH": {"price_earnings": 12.0, "price_book": 1.2, "turnover_rate": 0.5},
        "000905.SH": {"price_earnings": 20.0, "price_book": 2.0, "turnover_rate": 0.8},
        "000852.SH": {"price_earnings": 30.0, "price_book": 3.0, "turnover_rate": 1.1},
    }
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["api_name"] == "index_dailybasic"
        assert payload["fields"] == "ts_code,trade_date,pe,pb,turnover_rate"
        code = payload["params"]["ts_code"]
        assert payload["params"] == {
            "ts_code": code,
            "start_date": "20260828",
            "end_date": "20260828",
        }
        values = expected[code]
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [
                        [
                            code,
                            "20260828",
                            values["price_earnings"],
                            values["price_book"],
                            values["turnover_rate"],
                        ]
                    ],
                },
            }
        )
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic publication assertion, not evidence of an official historical release.
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    assert result.observation_count == 9
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "CN_INDEX_VALUATION",
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 7, tzinfo=UTC),
            definition_version=version,
        )
        == ()
    )
    points = evidence.metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    assert len(points) == 9
    assert {(p.dimensions["index"], p.dimensions["measure"]) for p in points} == {
        (code, measure)
        for code in expected
        for measure in ("price_earnings", "price_book", "turnover_rate")
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 3
    for point in points:
        code, measure = point.dimensions["index"], point.dimensions["measure"]
        assert point.selected_value == expected[code][measure]
        assert point.period_start == point.period_end == "2026-08-28"
        (claim,) = point.claims
        assert claim.unit == ("percent" if measure == "turnover_rate" else "multiple")
        field = {"price_earnings": "pe", "price_book": "pb", "turnover_rate": "turnover_rate"}[
            measure
        ]
        assert claim.source_reference == f"tushare:index_dailybasic:{field}:2026-08-28"
        trace = evidence.trace(point.observation_id, mode=AsOfMode.PUBLIC, as_of=public_at)
        (receipt,) = trace.acquisitions
        assert receipt.state == "validated" and receipt.parameters["ts_code"] == code
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == originals[code]
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-nine-members",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete and set(selection.selected_claim_ids) == set(result.claim_ids)
    assert models.manifest(model_id) == manifest


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "ttm_measure",
        "duplicate_day",
        "ttm_column",
        "wrong_index",
        "wrong_period",
        "wrong_unit",
        "wrong_value",
        "bad_response",
    ],
)
def test_registered_valuation_rejects_invalid_delivery_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        fields = ["ts_code", "trade_date", "pe", "pb", "turnover_rate"]
        rows: list[list[Any]] = [[code, "20260828", 12.0, 1.2, 0.5]]
        if code == "000852.SH":
            if fault == "ttm_column":
                fields[2] = "pe_ttm"
            elif fault == "wrong_index":
                rows[0][0] = "000300.SH"
            elif fault == "wrong_period":
                rows[0][1] = "20260827"
        if code == "000852.SH" and fault == "duplicate_day":
            rows.append(rows[0].copy())
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": fields,
                    "items": rows,
                },
            }
        )
        if code == "000852.SH" and fault == "bad_response":
            raw = b"not JSON"
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.index_valuation(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        delivered = []
        for scalar in scalars:
            if scalar.dimensions == {"index": "000852.SH", "measure": "price_earnings"}:
                if fault == "ttm_measure":
                    scalar = replace(scalar, source_field="pe_ttm")
                elif fault == "wrong_unit":
                    scalar = replace(scalar, unit="percent")
                elif fault == "wrong_value":
                    scalar = replace(scalar, value=120.0)
            delivered.append(scalar)
        return tuple(delivered)

    with pytest.raises(ValueError):
        adapter.acquire_scalars(paths, retrieve, definition_version=version)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(acquisitions.history()) == 3
    for receipt in acquisitions.history():
        assert receipt.state == "failed" and receipt.validated_at is None
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_INDEX_VALUATION",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
        == ()
    )


@pytest.mark.parametrize("damage", ["corrupt", "missing"])
@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_registered_valuation_selection_rejects_damaged_index_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damage: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [[payload["params"]["ts_code"], "20260828", 12.0, 1.2, 0.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-original",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    before = select_retrieval_input(paths, run)
    assert before.complete and set(before.selected_claim_ids) == set(result.claim_ids)
    points = EvidenceRepository(paths.database).metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    unaffected = {p.selected_claim_id for p in points if p.dimensions["index"] != "000852.SH"}
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters["ts_code"] == "000852.SH"
    )
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged valuation original")
    after = select_retrieval_input(paths, run)
    assert not after.complete
    assert set(after.selected_claim_ids) == unaffected
    assert len(after.selected_claim_ids) == 6 and len(after.missing_members) == 3
    assert all("000852.SH" in missing for missing in after.missing_members)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_valuation_public_replay_rejects_damaged_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    receipts = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id="CN_INDEX_VALUATION")
        # Public component scope only; stored candidates keep all 61 definitions.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest

        def transport(payload: dict[str, Any], synthetic_side: str = side) -> bytes:
            return encode(
                {
                    "code": 0,
                    "synthetic_side": synthetic_side,
                    "data": {
                        "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                        "items": [[payload["params"]["ts_code"], "20260828", 12.0, 1.2, 0.5]],
                    },
                }
            )

        adapter = TushareContextAdapter("synthetic-token", transport=transport)
        published = datetime(2026, 8, 28, 8, tzinfo=UTC)

        def retrieve(
            source: TushareContextAdapter = adapter, public_at: datetime = published
        ) -> tuple[ContextScalar, ...]:
            return tuple(
                replace(s, release_at=public_at, public_available_at=public_at)
                for s in source.index_valuation(
                    start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
                )
            )

        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        receipts[side] = next(
            r
            for r in acquisitions.history()
            if r.parameters["ts_code"] == "000852.SH"
            and side.encode() in acquisitions.read_content(r.acquisition_id, "raw")
        )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    digest = receipts["candidate"].raw_hash
    assert digest is not None and digest != receipts["comparison"].raw_hash
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged candidate valuation source")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert "candidate_context_selection_invalid:CN_INDEX_VALUATION" in after.gaps
    assert not any(gap.startswith("comparison_") for gap in after.gaps)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault,expected_count", [("missing_static_pe", 8), ("ttm_only", 8), ("empty_index", 6)]
)
def test_registered_valuation_keeps_missing_members_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str, expected_count: int
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        code = payload["params"]["ts_code"]
        fields = ["ts_code", "trade_date", "pe", "pb", "turnover_rate"]
        row: list[Any] = [code, "20260828", 12.0, 1.2, 0.5]
        if code == "000852.SH":
            row[2] = None
            if fault == "ttm_only":
                fields.append("pe_ttm")
                row.append(40.0)
        rows = [] if code == "000852.SH" and fault == "empty_index" else [row]
        raw = encode({"code": 0, "data": {"fields": fields, "items": rows}})
        originals[code] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)
    result = adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    assert result.observation_count == expected_count
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-missing-" + fault,
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete and len(selection.selected_claim_ids) == expected_count
    assert len(selection.missing_members) == 9 - expected_count
    assert all("000852.SH" in member for member in selection.missing_members)
    if fault != "empty_index":
        assert "price_earnings" in selection.missing_members[0]
    points = EvidenceRepository(paths.database).metric_series(
        "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=public_at, definition_version=version
    )
    assert not any(
        p.dimensions == {"index": "000852.SH", "measure": "price_earnings"} for p in points
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for receipt in acquisitions.history():
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == originals[receipt.parameters["ts_code"]]
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["known", "unknown", "future"])
def test_registered_valuation_respects_publication_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    public_at = (
        None
        if publication == "unknown"
        else cutoff
        if publication == "known"
        else datetime(2026, 8, 28, 9, tzinfo=UTC)
    )

    def transport(payload: dict[str, Any]) -> bytes:
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "pe", "pb", "turnover_rate"],
                    "items": [[payload["params"]["ts_code"], "20260828", 12.0, 1.2, 0.5]],
                },
            }
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # Synthetic metadata verifies software boundaries, never historical source certification.
    adapter.acquire_scalars(
        paths,
        lambda: tuple(
            replace(s, release_at=public_at, public_available_at=public_at)
            for s in adapter.index_valuation(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        ),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    assert (
        evidence.metric_series(
            "CN_INDEX_VALUATION",
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 7, tzinfo=UTC),
            definition_version=version,
        )
        == ()
    )
    assert len(
        evidence.metric_series(
            "CN_INDEX_VALUATION", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
        )
    ) == (9 if publication == "known" else 0)
    assert (
        len(
            evidence.metric_series(
                "CN_INDEX_VALUATION",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )
        == 9
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-valuation-publication-" + publication,
        model_version_id=model_id,
        system_as_of=cutoff,
        release_event_id="synthetic:valuation",
        metric_ids=("CN_INDEX_VALUATION",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (publication == "known")
    assert len(selection.selected_claim_ids) == (9 if publication == "known" else 0)
