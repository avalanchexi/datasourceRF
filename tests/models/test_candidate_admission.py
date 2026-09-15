from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
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
from pring_cycle.model_evaluation import context_replay_gaps, evaluate_context_replay
from pring_cycle.model_outputs import context_day_source_inputs
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_120d_model_v0011_manifest,
    certified_model_v0001_manifest,
)
from pring_cycle.official_context import (
    ParsedOfficialContextRelease,
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
from pring_cycle.treasury_context import FetchedTreasuryYieldCsv, refresh_treasury_yields
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


def admitted_gdp_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *, side: str = ""
) -> dict[str, Any]:
    # A full candidate with synthetic review bindings; no actual source is certified.
    request, _ = prepared_request(paths)
    definition = next(
        item for item in request["manifest"]["metric_definitions"] if item["metric_id"] == "CN_GDP"
    )
    definition["certification_status"] = "certified"
    if side:
        request["manifest"]["metric_catalog_version"] += "-" + side
        for item in request["manifest"]["metric_definitions"]:
            item["definition_version"] = request["manifest"]["metric_catalog_version"]
        if side == "candidate":
            definition["source_candidates"] = [
                *definition["source_candidates"],
                "https://www.stats.gov.cn/synthetic-review",
            ]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    package["definition_bindings"]["CN_GDP"] = hashlib.sha256(encode(definition)).hexdigest()
    if side:
        package["definition_bindings"] = {
            item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
            for item in request["manifest"]["metric_definitions"]
            if item["metric_id"] in package["definition_bindings"]
        }
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_candidate_allows_uncertified_optional_p2_at_replay_preflight(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate = admitted_gdp_manifest(paths, capsys)
    definitions = {item["metric_id"]: item for item in candidate["metric_definitions"]}
    assert len(definitions) == 61
    assert sum(item["priority"] == "P1" for item in definitions.values()) == 42
    assert len(candidate["derived_formula_versions"]) == 8
    assert definitions["CN_GDP"]["certification_status"] == "certified"
    for metric_id in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD", "UST_2S10S_SPREAD"):
        assert definitions[metric_id]["priority"] == "P2"
        assert definitions[metric_id]["certification_status"] == "awaiting_source_certification"
    models = ModelRepository(paths.database)
    baseline = models.create_candidate(certified_model_v0001_manifest())
    comparison = models.manifest(baseline.model_version_id)

    assert context_replay_gaps(candidate, comparison) == ()


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("damaged_artifact", [None, "raw", "normalized"])
def test_registered_gdp_original_preserves_eight_members_and_two_times(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_artifact: str | None
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    model_id = manifest["model_version_id"]
    version = manifest["metric_catalog_version"]
    digest = "60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-14" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html"
    before = datetime.now(UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_gdp",
        source_url=url,
        expected_period="2026-Q2",
        fetched_at=before,
        definition_version=version,
    )
    after = datetime.now(UTC)
    assert len(imported.claim_ids) == 8
    repository = EvidenceRepository(paths.database)
    assert (
        repository.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
        )
        == ()
    )
    release = datetime(2026, 7, 16, 1, 30, tzinfo=UTC)
    assert (
        repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.PUBLIC,
            as_of=release - timedelta(seconds=1),
            definition_version=version,
        )
        == ()
    )
    # These literals are independently read from the NBS Q2 table, not parser output.
    expected = {
        ("total", "nominal_ytd_level"): (
            695704,
            "hundred_million_cny",
            "year_to_quarter",
            "2026-01-01",
        ),
        ("primary", "nominal_ytd_level"): (
            31522,
            "hundred_million_cny",
            "year_to_quarter",
            "2026-01-01",
        ),
        ("secondary", "nominal_ytd_level"): (
            250473,
            "hundred_million_cny",
            "year_to_quarter",
            "2026-01-01",
        ),
        ("tertiary", "nominal_ytd_level"): (
            413709,
            "hundred_million_cny",
            "year_to_quarter",
            "2026-01-01",
        ),
        ("total", "real_quarter_yoy"): (4.3, "percent", "quarter", "2026-04-01"),
        ("primary", "real_quarter_yoy"): (3.7, "percent", "quarter", "2026-04-01"),
        ("secondary", "real_quarter_yoy"): (3.0, "percent", "quarter", "2026-04-01"),
        ("tertiary", "real_quarter_yoy"): (5.1, "percent", "quarter", "2026-04-01"),
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.raw_hash == digest
    assert receipt.parser_version == "official-context-parser-v0004"
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert before <= receipt.started_at <= receipt.received_at <= receipt.validated_at <= after
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert len(normalized["scalars"]) == 8
    for mode, cutoff in ((AsOfMode.SYSTEM, after), (AsOfMode.PUBLIC, release)):
        points = repository.metric_series(
            "CN_GDP", mode=mode, as_of=cutoff, definition_version=version
        )
        assert len(points) == 8
        assert {point.selected_claim_id for point in points} == set(imported.claim_ids)
        actual = {}
        for point in points:
            (claim,) = point.claims
            trace = repository.trace(point.observation_id, mode=mode, as_of=cutoff)
            assert point.period_end == "2026-06-30"
            assert claim.source_reference == f"{url}#sha256={digest}"
            assert tuple(item.acquisition_id for item in trace.acquisitions) == (
                receipt.acquisition_id,
            )
            assert claim.public_available_at == release
            assert claim.fetched_at == receipt.received_at
            assert receipt.validated_at <= claim.available_at <= after
            actual[(point.dimensions["aggregate"], point.dimensions["measure"])] = (
                point.selected_value,
                claim.unit,
                trace.period_kind,
                point.period_start,
            )
        assert actual == expected

    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="admitted-gdp",
        model_version_id=model_id,
        system_as_of=after,
        release_event_id=imported.release_event_id,
        metric_ids=("CN_GDP",),
        period="2026-Q2",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selected = select_retrieval_input(paths, run, mode=mode)
        assert selected.complete, selected.missing_members
        assert set(selected.selected_claim_ids) == set(imported.claim_ids)
        context = build_context_projection(
            repository, as_of=after, model_manifest=manifest, as_of_mode=mode
        )
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert set(imported.claim_ids) <= set(model_inputs)

        rows = context.macro["international_context"]
        assert isinstance(rows, list)
        gdp_rows = [row for row in rows if row["metric_id"] == "CN_GDP"]
        assert len(gdp_rows) == 8
        assert {row["role"] for row in gdp_rows} == {"context_only_never_formal_stage"}
        assert {row["status"] for row in gdp_rows} == {"current"}
        assert {
            (row["dimensions"]["aggregate"], row["dimensions"]["measure"]): (
                row["value"],
                row["unit"],
                row["period_start"],
            )
            for row in gdp_rows
        } == {member: (value, unit, start) for member, (value, unit, _, start) in expected.items()}

    if damaged_artifact is not None:
        content_hash = receipt.raw_hash if damaged_artifact == "raw" else receipt.normalized_hash
        assert content_hash is not None
        (paths.artifacts / content_hash[:2] / content_hash).write_bytes(b'{"damaged":true}\n')
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            selected = select_retrieval_input(paths, run, mode=mode)
            assert not selected.complete
            assert selected.selected_claim_ids == ()
            context = build_context_projection(
                repository, as_of=after, model_manifest=manifest, as_of_mode=mode
            )
            model_inputs = context.macro["model_input_observation_version_ids"]
            assert isinstance(model_inputs, list)
            assert set(imported.claim_ids).isdisjoint(model_inputs)
            assert set(imported.claim_ids) <= set(context.observation_version_ids)
            rows = context.macro["international_context"]
            assert isinstance(rows, list)
            assert {row["status"] for row in rows if row["metric_id"] == "CN_GDP"} == {
                "source_failed"
            }
    else:
        # Q1 shares the two start dates but still has eight distinct members.
        q1_hash = "61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18"
        q1_raw = (
            Path(__file__).parents[2]
            / ".scratch/pring-data-acquisition-repair/evidence-macro-normalized"
            / q1_hash
        ).read_bytes()
        assert hashlib.sha256(q1_raw).hexdigest() == q1_hash
        before_q1 = datetime.now(UTC)
        q1 = ingest_official_context_document(
            paths,
            q1_raw,
            family="nbs_gdp",
            source_url="https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html",
            expected_period="2026-Q1",
            fetched_at=before_q1,
            definition_version=version,
        )
        after_q1 = datetime.now(UTC)
        q1_release = datetime(2026, 4, 17, 1, 30, tzinfo=UTC)
        q1_expected = {
            ("total", "nominal_ytd_level"): 334193,
            ("primary", "nominal_ytd_level"): 11941,
            ("secondary", "nominal_ytd_level"): 116135,
            ("tertiary", "nominal_ytd_level"): 206117,
            ("total", "real_quarter_yoy"): 5.0,
            ("primary", "real_quarter_yoy"): 3.8,
            ("secondary", "real_quarter_yoy"): 4.9,
            ("tertiary", "real_quarter_yoy"): 5.2,
        }
        assert len(q1.claim_ids) == 8
        for mode, cutoff in ((AsOfMode.PUBLIC, q1_release), (AsOfMode.SYSTEM, after_q1)):
            points = repository.metric_series(
                "CN_GDP", mode=mode, as_of=cutoff, definition_version=version
            )
            assert len(points) == (8 if mode is AsOfMode.PUBLIC else 16)
            q1_points = [point for point in points if point.period_end == "2026-03-31"]
            assert {point.period_start for point in q1_points} == {"2026-01-01"}
            assert {point.selected_claim_id for point in q1_points} == set(q1.claim_ids)
            assert {
                (point.dimensions["aggregate"], point.dimensions["measure"]): point.selected_value
                for point in q1_points
            } == q1_expected
            for point in q1_points:
                trace = repository.trace(point.observation_id, mode=mode, as_of=cutoff)
                (acquisition,) = trace.acquisitions
                assert acquisition.raw_hash == q1_hash
                assert acquisitions.read_content(acquisition.acquisition_id, "raw") == q1_raw
                assert acquisition.validated_at is not None
                assert before_q1 <= acquisition.validated_at <= after_q1
                assert trace.period_kind == (
                    "quarter"
                    if point.dimensions["measure"] == "real_quarter_yoy"
                    else "year_to_quarter"
                )
        assert (
            repository.metric_series(
                "CN_GDP",
                mode=AsOfMode.PUBLIC,
                as_of=q1_release - timedelta(seconds=1),
                definition_version=version,
            )
            == ()
        )
        assert (
            len(
                repository.metric_series(
                    "CN_GDP", mode=AsOfMode.SYSTEM, as_of=before_q1, definition_version=version
                )
            )
            == 8
        )

        # A synthetic changed publication keeps the old header: its new public
        # time is unknown, while the historical public Q2 values stay intact.
        revised_raw = raw.replace(b"695704", b"695705")
        assert revised_raw != raw
        before_revision = datetime.now(UTC)
        revised = ingest_official_context_document(
            paths,
            revised_raw,
            family="nbs_gdp",
            source_url=url,
            expected_period="2026-Q2",
            fetched_at=before_revision,
            definition_version=version,
        )
        after_revision = datetime.now(UTC)
        assert len(revised.claim_ids) == 8
        assert set(revised.claim_ids).isdisjoint(imported.claim_ids)
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            points = repository.metric_series(
                "CN_GDP", mode=mode, as_of=after_revision, definition_version=version
            )
            q2_points = [point for point in points if point.period_end == "2026-06-30"]
            selected_ids = {point.selected_claim_id for point in q2_points}
            assert selected_ids == set(
                imported.claim_ids if mode is AsOfMode.PUBLIC else revised.claim_ids
            )
            total = next(
                point
                for point in q2_points
                if point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
            )
            assert total.selected_value == (695704 if mode is AsOfMode.PUBLIC else 695705)
            if mode is AsOfMode.SYSTEM:
                for point in q2_points:
                    selected_claim = next(
                        claim for claim in point.claims if claim.claim_id == point.selected_claim_id
                    )
                    assert selected_claim.public_available_at is None
                    assert selected_claim.release_at is None
                    assert selected_claim.available_at >= before_revision


def test_registered_gdp_rejects_unsupported_members_and_quarter_boundaries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    now = datetime(2026, 9, 9, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_GDP",
        definition_version=manifest["metric_catalog_version"],
        period_kind="year_to_quarter",
        period_start="2026-01-01",
        period_end="2026-06-30",
        dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
        value=695704,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="hundred_million_cny",
        provider="国家统计局",
        source_reference="synthetic:gdp-identity-rejection",
        release_event_id="synthetic:gdp",
        release_at=now,
        public_available_at=now,
        fetched_at=now,
        available_at=now,
        certification_status="certified",
        quality_status="validated",
    )
    invalid_identities: tuple[dict[str, Any], ...] = (
        {"provider": "tushare"},
        {"dimensions": {"aggregate": "other", "measure": "nominal_ytd_level"}},
        {"dimensions": {"aggregate": "total", "measure": "nominal_quarterly_level"}},
        {"dimensions": {"aggregate": "total", "measure": "real_ytd_yoy"}, "unit": "percent"},
        {"unit": "percent"},
        {"period_kind": "quarter"},
    )
    repository = EvidenceRepository(paths.database)
    for changes in invalid_identities:
        with pytest.raises(ValueError, match="registered_official_source_identity_mismatch"):
            repository.append_source_claim(replace(claim, **changes))
    invalid_periods: tuple[dict[str, Any], ...] = (
        {"period_start": "2026-04-01"},
        {"period_end": "2026-06-29"},
        {"period_end": "2026-05-31"},
        {
            "dimensions": {"aggregate": "total", "measure": "real_quarter_yoy"},
            "value": 4.3,
            "unit": "percent",
            "period_kind": "quarter",
        },
    )
    for changes in invalid_periods:
        with pytest.raises(ValueError, match="registered_official_source_period_mismatch"):
            repository.append_source_claim(replace(claim, **changes))
    assert (
        repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.SYSTEM,
            as_of=now,
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault", ["none", "missing_member", "missing_lineage", "invalid_quality", "wrong_value"]
)
def test_registered_gdp_requires_complete_current_quarter_and_matched_receipts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    model_id = manifest["model_version_id"]
    version = manifest["metric_catalog_version"]
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    q1_raw = (
        evidence_root
        / "evidence-macro-normalized"
        / "61f8de5fbdb2ca88130504d13a0af85ebb92004b04b85772ae3c619003767a18"
    ).read_bytes()
    q1 = ingest_official_context_document(
        paths,
        q1_raw,
        family="nbs_gdp",
        source_url="https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html",
        expected_period="2026-Q1",
        fetched_at=datetime.now(UTC),
        definition_version=version,
    )
    digest = "60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915"
    raw = (evidence_root / "evidence-14" / digest).read_bytes()
    url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html"
    now = datetime.now(UTC)
    # The acquisition, parser and normalized original remain complete; the
    # public claim boundary receives one missing, invalid or mismatched member.
    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="国家统计局",
        api_name="document_import",
        parameters={"family": "nbs_gdp", "source_url": url, "period": "2026-Q2"},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: raw,
        parse=lambda content: parse_official_context_document(
            content, family="nbs_gdp", source_url=url, expected_period="2026-Q2", fetched_at=now
        ),
        normalize=asdict,
    )
    receipt, parsed = acquired.receipt, acquired.value
    assert receipt.received_at is not None and receipt.validated_at is not None
    repository = EvidenceRepository(paths.database)
    claims = []
    for scalar in parsed.scalars:
        target = scalar.dimensions == {"aggregate": "secondary", "measure": "real_quarter_yoy"}
        if target and fault == "missing_member":
            continue
        claims.append(
            SourceClaimInput(
                metric_id="CN_GDP",
                definition_version=version,
                period_kind=scalar.period_kind,
                period_start=scalar.period_start,
                period_end=scalar.period_end,
                dimensions=scalar.dimensions,
                value=3.9 if target and fault == "wrong_value" else scalar.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=scalar.unit,
                provider=parsed.provider,
                source_reference=f"{url}#sha256={digest}",
                release_event_id=parsed.release_event_id,
                release_at=parsed.release_at,
                public_available_at=parsed.public_available_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="invalid" if target and fault == "invalid_quality" else "validated",
                acquisition_id=None
                if target and fault == "missing_lineage"
                else receipt.acquisition_id,
            )
        )
    stored = repository.append_source_claims(tuple(claims))
    cutoff = datetime.now(UTC)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="partial-gdp",
        model_version_id=model_id,
        system_as_of=cutoff,
        release_event_id=parsed.release_event_id,
        metric_ids=("CN_GDP",),
        period="2026-Q2",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selected = select_retrieval_input(paths, run, mode=mode)
        assert selected.complete is (fault == "none")
        assert len(selected.selected_claim_ids) == (8 if fault == "none" else 7)
        assert set(selected.selected_claim_ids) <= {claim.claim_id for claim in stored}
        assert set(selected.selected_claim_ids).isdisjoint(q1.claim_ids)
        assert len(selected.missing_members) == (0 if fault == "none" else 1)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("fault", ["unit", "quarter_columns", "price_basis"])
@pytest.mark.parametrize("boundary", ["ingestion", "consumption"])
def test_registered_gdp_rejects_mislabeled_official_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str, boundary: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14"
        / "60b12f6257d62842e7ea13e5c79bf868438fb382e7857bd6f88ab4110c588915"
    ).read_bytes()
    if fault == "unit":
        malformed = raw.replace("绝对额（亿元）".encode(), "绝对额（万亿元）".encode())
    elif fault == "quarter_columns":
        malformed = (
            raw.replace(">二季度<".encode(), b">quarter-placeholder<")
            .replace(">上半年<".encode(), ">二季度<".encode())
            .replace(b">quarter-placeholder<", ">上半年<".encode())
        )
    else:
        malformed = raw.replace("增长速度按不变价计算".encode(), "增长速度按现价计算".encode())
    assert malformed != raw
    url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html"
    version = manifest["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    if boundary == "ingestion":
        with pytest.raises(ValueError, match="registered_gdp_table_contract_mismatch"):
            ingest_official_context_document(
                paths,
                malformed,
                family="nbs_gdp",
                source_url=url,
                expected_period="2026-Q2",
                fetched_at=datetime.now(UTC),
                definition_version=version,
            )
        assert (
            repository.metric_series(
                "CN_GDP",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
            == ()
        )
        return
    now = datetime.now(UTC)
    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="国家统计局",
        api_name="document_import",
        parameters={"family": "nbs_gdp", "source_url": url, "period": "2026-Q2"},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: malformed,
        parse=lambda content: parse_official_context_document(
            content, family="nbs_gdp", source_url=url, expected_period="2026-Q2", fetched_at=now
        ),
        normalize=asdict,
    )
    receipt, parsed = acquired.receipt, acquired.value
    assert receipt.received_at is not None and receipt.validated_at is not None
    stored = repository.append_source_claims(
        tuple(
            SourceClaimInput(
                metric_id="CN_GDP",
                definition_version=version,
                period_kind=scalar.period_kind,
                period_start=scalar.period_start,
                period_end=scalar.period_end,
                dimensions=scalar.dimensions,
                value=scalar.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=scalar.unit,
                provider=parsed.provider,
                source_reference=f"{url}#sha256={receipt.raw_hash}",
                release_event_id=parsed.release_event_id,
                release_at=parsed.release_at,
                public_available_at=parsed.public_available_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
            for scalar in parsed.scalars
        )
    )
    assert len(stored) == 8
    cutoff = datetime.now(UTC)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="gdp-wrong-table",
        model_version_id=manifest["model_version_id"],
        system_as_of=cutoff,
        release_event_id=parsed.release_event_id,
        metric_ids=("CN_GDP",),
        period="2026-Q2",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selected = select_retrieval_input(paths, run, mode=mode)
        assert not selected.complete
        assert selected.selected_claim_ids == ()
        context = build_context_projection(
            repository, as_of=cutoff, model_manifest=manifest, as_of_mode=mode
        )
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert {claim.claim_id for claim in stored}.isdisjoint(model_inputs)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "period,digest,url,levels,growth",
    [
        (
            "2025-Q3",
            "0f7c85e52242f3e1905d3313aa744028f51d48f60bcff899b712da400f135a5c",
            "https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html",
            (1015036, 58061, 364020, 592955),
            (4.8, 4.0, 4.2, 5.4),
        ),
        (
            "2025-Q4",
            "9d9bc9ece5d52a9ba07d6d9ed01e0d865b4d72b385c1b2a9873501e2d5532765",
            "https://www.stats.gov.cn/sj/zxfb/202601/t20260120_1962349.html",
            (1401879, 93347, 499653, 808879),
            (4.5, 4.2, 3.4, 5.2),
        ),
    ],
)
def test_registered_gdp_preserves_q3_q4_official_table_layouts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    period: str,
    digest: str,
    url: str,
    levels: tuple[int, ...],
    growth: tuple[float, ...],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    version = manifest["metric_catalog_version"]
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-macro-normalized"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_gdp",
        source_url=url,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    points = repository.metric_series(
        "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert len(points) == 8
    assert {point.selected_claim_id for point in points} == set(imported.claim_ids)
    # Independently read table literals: cumulative levels and current-quarter growth.
    for aggregate, level, yoy in zip(
        ("total", "primary", "secondary", "tertiary"), levels, growth, strict=True
    ):
        assert {
            point.dimensions["measure"]: point.selected_value
            for point in points
            if point.dimensions["aggregate"] == aggregate
        } == {
            "nominal_ytd_level": level,
            "real_quarter_yoy": yoy,
        }


@pytest.mark.usefixtures("runtime_clock")
def test_registered_catalog_treasury_cli_keeps_real_receipt_and_unknown_public_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"]
    digest = "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/csv; charset=UTF-8"}

        def __init__(self, url: str) -> None:
            super().__init__(raw)
            self.url = url

        def geturl(self) -> str:
            return self.url

    def fetch(request: Any, *, timeout: float) -> Response:
        assert timeout > 0
        return Response(request.full_url)

    monkeypatch.setattr("pring_cycle.treasury_context.open_no_redirects", fetch)
    before = datetime.now(UTC)
    main(
        [
            "treasury-csv-refresh",
            "--runtime-root",
            str(paths.override_root),
            "--start",
            "2026-09-04",
            "--end",
            "2026-09-04",
            "--definition-version",
            version,
            "--json",
        ]
    )
    after = datetime.now(UTC)
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "stored_candidate" and result["observation_count"] == 2
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.raw_hash == digest
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert before <= receipt.started_at <= receipt.received_at <= receipt.validated_at <= after
    assert receipt.parameters["definition_version"] == version
    repository = EvidenceRepository(paths.database)
    for metric, value in (("UST2Y_NOMINAL_YIELD", 4.37), ("UST10Y_NOMINAL_YIELD", 4.78)):
        assert (
            repository.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        assert (
            repository.metric_series(
                metric, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
            )
            == ()
        )
        (point,) = repository.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
        )
        (claim,) = point.claims
        assert claim.value == value and claim.unit == "percent"
        assert claim.certification_status == "awaiting_source_certification"
        assert claim.public_available_at is None and claim.release_at is None
        assert claim.fetched_at == receipt.received_at
        assert receipt.validated_at <= claim.available_at <= after
        trace = repository.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
        assert tuple(item.acquisition_id for item in trace.acquisitions) == (
            receipt.acquisition_id,
        )


def admitted_treasury_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    # Synthetic source review binds the official CSV identity, never the old TuShare fields.
    request, _ = prepared_request(paths)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    columns = {"UST2Y_NOMINAL_YIELD": "2 Yr", "UST10Y_NOMINAL_YIELD": "10 Yr"}
    for definition in request["manifest"]["metric_definitions"]:
        metric = definition["metric_id"]
        if metric in columns:
            definition.update(
                certification_status="certified",
                source_codes=[f"treasury_nominal_yields_csv.{columns[metric]}"],
                source_candidates=["U.S. Department of the Treasury"],
                release_event_family="treasury_nominal_yields_csv",
                release_timezone="America/New_York",
            )
        elif metric == "UST_2S10S_SPREAD":
            definition["certification_status"] = "derived_from_certified_inputs"
        else:
            continue
        package["definition_bindings"][metric] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    return ModelRepository(paths.database).manifest(model_id)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_replay_missing_optional_sources_preserves_required_gdp_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate = admitted_treasury_manifest(paths, capsys)
    models = ModelRepository(paths.database)
    baseline = models.create_candidate(certified_model_v0001_manifest())
    comparison = models.manifest(baseline.model_version_id)

    replay = evaluate_context_replay(
        paths.database,
        candidate,
        comparison,
        requested_start="2026-08-28",
        requested_end="2026-08-28",
        replay_days=("2026-08-28",),
    )

    assert "candidate_context_sources_uncertified:CN_GDP" in replay.gaps
    assert "candidate_context_evidence_missing:CN_EQ_CSI500" in replay.gaps
    assert replay.evaluated_cutoffs == 0
    assert "ust_2s10s_spread" in replay.output_document["formula_keys"]
    assert {"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"} <= set(
        replay.output_document["source_metrics"]
    )
    assert not any(
        metric in gap
        for gap in replay.gaps
        for metric in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD", "ust_2s10s_spread")
    ), replay.gaps


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "damaged_artifact", [None, "raw", "normalized", "latest_quality", "latest_normalized"]
)
def test_registered_treasury_original_supports_system_context_without_inventing_public_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_artifact: str | None
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_treasury_manifest(paths, capsys)
    version = manifest["metric_catalog_version"]
    digest = "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    before = datetime.now(UTC)
    imported = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version=version,
        fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.get(imported.acquisition_id)
    assert receipt.received_at is not None and receipt.validated_at is not None
    repository = EvidenceRepository(paths.database)
    # The fixture review permits values; the real CSV proves no per-row PUBLIC time.
    claims = repository.append_source_claims(
        tuple(
            SourceClaimInput(
                metric_id=metric,
                definition_version=version,
                period_kind="business_day",
                period_start="2026-09-04",
                period_end="2026-09-04",
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="U.S. Department of the Treasury",
                source_reference=f"{receipt.parameters['endpoint']}#date=2026-09-04",
                release_event_id=f"synthetic:reviewed-treasury:{receipt.acquisition_id}",
                release_at=None,
                public_available_at=None,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
            for metric, value in (("UST2Y_NOMINAL_YIELD", 4.37), ("UST10Y_NOMINAL_YIELD", 4.78))
        ),
        availability_clock=lambda: datetime.now(UTC),
    )
    after = datetime.now(UTC)
    for metric in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"):
        assert (
            repository.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
            )
            == ()
        )
        assert (
            repository.metric_series(
                metric, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
            )
            == ()
        )
    context = build_context_projection(
        repository, as_of=after, model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
    )
    rows = context.macro["international_context"]
    assert isinstance(rows, list)
    (spread,) = [row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD"]
    assert spread["value"] == pytest.approx(41.0), spread
    assert spread["unit"] == "basis_points" and spread["period"] == "2026-09-04"
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert {claim.claim_id for claim in claims} <= set(model_inputs)
    # A historical target still requires reliable PUBLIC evidence; SYSTEM cannot backfill it.
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-04",
        client_request_id="treasury-public-unknown",
        model_version_id=manifest["model_version_id"],
        system_as_of=after,
        release_event_id="synthetic:treasury-source-review",
        metric_ids=("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
        period="2026-09-04",
    )
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        selected = select_retrieval_input(paths, run, mode=mode)
        assert not selected.complete and selected.selected_claim_ids == ()

    if damaged_artifact in {"raw", "normalized"}:
        content_hash = receipt.raw_hash if damaged_artifact == "raw" else receipt.normalized_hash
        assert content_hash is not None
        (paths.artifacts / content_hash[:2] / content_hash).write_bytes(b'{"damaged":true}\n')
        context = build_context_projection(
            repository, as_of=after, model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
        )
        rows = context.macro["international_context"]
        assert isinstance(rows, list)
        assert {
            row["status"]
            for row in rows
            if row["metric_id"] in {"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"}
        } == {"source_failed"}
        (spread,) = [row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD"]
        assert spread["value"] is None
        adopted = context.macro["model_input_observation_version_ids"]
        assert isinstance(adopted, list)
        assert {claim.claim_id for claim in claims}.isdisjoint(adopted)
        assert {claim.claim_id for claim in claims} <= set(context.observation_version_ids)

    if damaged_artifact in {"latest_quality", "latest_normalized"}:
        old = refresh_treasury_yields(
            paths,
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            definition_version=version,
            fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
        )
        old_receipt = acquisitions.get(old.acquisition_id)
        assert old_receipt.received_at is not None and old_receipt.validated_at is not None
        old_claims = repository.append_source_claims(
            tuple(
                SourceClaimInput(
                    metric_id=metric,
                    definition_version=version,
                    period_kind="business_day",
                    period_start="2026-08-28",
                    period_end="2026-08-28",
                    dimensions={},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="U.S. Department of the Treasury",
                    source_reference=f"{old_receipt.parameters['endpoint']}#date=2026-08-28",
                    release_event_id="synthetic:treasury-old-valid",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=old_receipt.received_at,
                    available_at=old_receipt.validated_at,
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=old_receipt.acquisition_id,
                )
                for metric, value in (("UST2Y_NOMINAL_YIELD", 4.34), ("UST10Y_NOMINAL_YIELD", 4.73))
            ),
            availability_clock=lambda: datetime.now(UTC),
        )
        if damaged_artifact == "latest_normalized":
            assert receipt.normalized_hash is not None
            assert receipt.normalized_hash != old_receipt.normalized_hash
            (paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash).write_bytes(
                b'{"damaged":true}\n'
            )
        else:
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="UST10Y_NOMINAL_YIELD",
                    definition_version=version,
                    period_kind="business_day",
                    period_start="2026-09-04",
                    period_end="2026-09-04",
                    dimensions={},
                    value=4.78,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="U.S. Department of the Treasury",
                    source_reference=f"{receipt.parameters['endpoint']}#date=2026-09-04",
                    release_event_id="synthetic:treasury-latest-invalid",
                    release_at=None,
                    public_available_at=None,
                    fetched_at=receipt.received_at,
                    available_at=datetime.now(UTC),
                    certification_status="certified",
                    quality_status="invalid",
                    acquisition_id=receipt.acquisition_id,
                )
            )
        assert all(repository.source_claim_originals(claim.claim_id) for claim in old_claims)
        context = build_context_projection(
            repository, as_of=datetime.now(UTC), model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
        )
        rows = context.macro["international_context"]
        assert isinstance(rows, list)
        (spread,) = [row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD"]
        assert spread["value"] is None, "A bad latest pair must not restore the older 39bp spread."


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "value",
        "unit",
        "window",
        "year",
        "http_status",
        "endpoint",
        "parser",
        "definition",
        "public_time",
    ],
)
def test_registered_treasury_context_rechecks_hash_consistent_receipts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_treasury_manifest(paths, capsys)
    version = manifest["metric_catalog_version"]
    digest = "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
    raw = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-14-treasury-followup"
        / digest
    ).read_bytes()
    imported = refresh_treasury_yields(
        paths,
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 4),
        definition_version=version,
        fetcher=lambda url: FetchedTreasuryYieldCsv(raw, url, 200, "text/csv"),
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    original = acquisitions.get(imported.acquisition_id)
    normalized = json.loads(acquisitions.read_content(original.acquisition_id, "normalized"))
    parameters = dict(original.parameters)
    parser_version = original.parser_version
    if fault == "value":
        normalized["cells"][0]["value"] = 99.0
    elif fault == "unit":
        normalized["unit"] = "basis_points"
    elif fault == "window":
        parameters["start_date"] = "2026-08-28"
    elif fault == "year":
        parameters["source_year"] = "2025"
    elif fault == "http_status":
        normalized["http_response"]["response_http_status"] = "403"
    elif fault == "endpoint":
        normalized["http_response"]["response_final_url"] = "https://example.invalid/yields.csv"
    elif fault == "parser":
        parser_version = "unsupported-treasury-parser"
    elif fault == "definition":
        parameters["definition_version"] = "metric-catalog-v0002"
    # A public receipt with valid physical hashes but an intentionally inconsistent batch.
    acquired = acquisitions.capture(
        provider=original.provider,
        api_name=original.api_name,
        parameters=parameters,
        fields=original.fields,
        parser_version=parser_version,
        fetch=lambda: raw,
        parse=lambda _: normalized,
        normalize=lambda value: value,
    )
    receipt = acquired.receipt
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized")) == normalized
    assert receipt.received_at is not None and receipt.validated_at is not None
    # An asserted timestamp is not publication evidence in this CSV protocol.
    public_at = datetime(2026, 9, 4, 8, tzinfo=UTC) if fault == "public_time" else None
    repository = EvidenceRepository(paths.database)
    claims = repository.append_source_claims(
        tuple(
            SourceClaimInput(
                metric_id=metric,
                definition_version=version,
                period_kind="business_day",
                period_start="2026-09-04",
                period_end="2026-09-04",
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="U.S. Department of the Treasury",
                source_reference=f"{original.parameters['endpoint']}#date=2026-09-04",
                release_event_id=f"synthetic:treasury-mismatch:{fault}",
                release_at=public_at,
                public_available_at=public_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
            for metric, value in (("UST2Y_NOMINAL_YIELD", 4.37), ("UST10Y_NOMINAL_YIELD", 4.78))
        ),
        availability_clock=lambda: datetime.now(UTC),
    )
    after = datetime.now(UTC)
    context = build_context_projection(
        repository, as_of=after, model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
    )
    rows = context.macro["international_context"]
    assert isinstance(rows, list)
    (spread,) = [row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD"]
    adopted = context.macro["model_input_observation_version_ids"]
    assert isinstance(adopted, list)
    claim_ids = {claim.claim_id for claim in claims}
    if fault == "none":
        assert spread["value"] == pytest.approx(41.0)
        assert claim_ids <= set(adopted)
    else:
        assert spread["value"] is None, spread
        assert claim_ids.isdisjoint(adopted)
        assert claim_ids <= set(context.observation_version_ids)
        assert {
            row["status"]
            for row in rows
            if row["metric_id"] in {"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"}
        } == {"source_failed"}
    if fault == "public_time":
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-09-04",
            client_request_id="treasury-unproven-public",
            model_version_id=manifest["model_version_id"],
            system_as_of=after,
            release_event_id="synthetic:treasury-unproven-public",
            metric_ids=("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
            period="2026-09-04",
        )
        for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
            selected = select_retrieval_input(paths, run, mode=mode)
            assert not selected.complete and selected.selected_claim_ids == ()


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
        context = saved["context_output_document"]
        points = context_day_source_inputs(context, context["days"][0], "candidate")[
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

    def warrant_points(document: dict[str, Any]) -> list[dict[str, Any]]:
        return context_day_source_inputs(document, document["days"][0], "candidate")[
            "CN_FUTURES_WARRANTS"
        ]

    old_point = next(
        point
        for point in warrant_points(before.output_document)
        if point["period_end"] == "2026-08-24" and point["dimensions"]["symbol"] == "CU"
    )
    new_point = next(
        point
        for point in warrant_points(after.output_document)
        if point["period_end"] == "2026-08-24" and point["dimensions"]["symbol"] == "CU"
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
@pytest.mark.parametrize(
    ("public_known", "wrong_dr_value", "conflicting_dr_row"),
    [(False, False, False), (True, False, False), (True, True, False), (True, False, True)],
)
def test_registered_interbank_acquisition_preserves_public_boundary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    public_known: bool,
    wrong_dr_value: bool,
    conflicting_dr_row: bool,
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
        if conflicting_dr_row and payload["api_name"] == "repo_daily":
            return encode(
                {
                    "code": 0,
                    "data": {
                        "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
                        "items": [
                            ["DR007.IB", "20260828", "DR007", 1.3859],
                            ["DR007.IB", "20260828", "DR007", 1.3806],
                        ],
                    },
                }
            )
        return encode(responses[payload["api_name"]])

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    # This known publication instant tests software behavior only. The saved
    # historical CFETS response does not prove the day's first publication.
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC) if public_known else None

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.transmission(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
        if conflicting_dr_row:
            scalars = tuple(
                s for s in scalars if not (s.metric_id == "CN_DR007" and s.value == 1.3806)
            )
        if not public_known:
            assert all(s.release_at is None and s.public_available_at is None for s in scalars)
            return scalars
        return tuple(
            replace(
                scalar,
                release_at=public_at,
                public_available_at=public_at,
                # Hash-correct normalized/claim with the wrong CFETS field:
                # 1.3806 is the close, while raw weight remains 1.3859.
                value=1.3806 if wrong_dr_value and scalar.metric_id == "CN_DR007" else scalar.value,
            )
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
        "CN_DR007": {None: 1.3806 if wrong_dr_value else 1.3859},
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
        assert receipts.read_content(receipt.acquisition_id, "raw") == transport(
            {"api_name": receipt.api_name}
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
    expected_selected = (
        {
            point.selected_claim_id
            for metric in expected
            if not ((wrong_dr_value or conflicting_dr_row) and metric == "CN_DR007")
            for point in repository.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=now, definition_version=version
            )
        }
        if public_known
        else set()
    )
    assert selection.complete is (public_known and not (wrong_dr_value or conflicting_dr_row))
    assert set(selection.selected_claim_ids) == expected_selected
    assert len(selection.missing_members) == (
        int(wrong_dr_value or conflicting_dr_row) if public_known else 4
    )
    context = build_context_projection(
        repository, as_of=now, target_business_date="2026-08-28", model_manifest=request["manifest"]
    )
    assert set(imported.claim_ids).intersection(context.observation_version_ids) == (
        set(imported.claim_ids) if public_known else set()
    )
    public_context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        as_of_mode=AsOfMode.PUBLIC,
        target_business_date="2026-08-28",
        model_manifest=request["manifest"],
    )
    actual_inputs = public_context.macro["model_input_observation_version_ids"]
    assert isinstance(actual_inputs, list)
    assert set(imported.claim_ids) & set(actual_inputs) == expected_selected


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize(
    ("dr_only", "damaged_api"), [(False, "repo_daily"), (False, "shibor"), (True, "shibor")]
)
def test_registered_interbank_joint_receipts_preserve_filtered_members(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    artifact_kind: str,
    dr_only: bool,
    damaged_api: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    metrics = ("CN_DR007",) if dr_only else ("CN_DR007", "CN_SHIBOR_ON_1W_3M")

    def transport(payload: dict[str, Any]) -> bytes:
        day = payload["params"]["start_date"]
        # Synthetic earlier-day control, independently fixed 08-28 CFETS values;
        # response columns are reordered and include a harmless extra field.
        if payload["api_name"] == "repo_daily":
            columns = ["weight", "repo_maturity", "trade_date", "ts_code", "fixture"]
            row = [1.39 if day == "20260827" else 1.3859, "DR007", day, "DR007.IB", "joint"]
        else:
            columns = ["3m", "on", "date", "1w", "fixture"]
            row = (
                [1.44, 1.34, day, 1.39, "joint"]
                if day == "20260827"
                else [1.43, 1.339, day, 1.387, "joint"]
            )
        return encode({"code": 0, "data": {"fields": columns, "items": [row]}})

    adapter = TushareContextAdapter("synthetic-token", transport=transport)

    def retrieve() -> tuple[ContextScalar, ...]:
        result = []
        for day in (date(2026, 8, 27), date(2026, 8, 28)):
            for scalar in adapter.transmission(start_date=day, end_date=day):
                if scalar.metric_id in metrics:
                    public_at = datetime.fromisoformat(scalar.period_end + "T08:00:00+00:00")
                    result.append(
                        replace(scalar, release_at=public_at, public_available_at=public_at)
                    )
        return tuple(result)

    imported = adapter.acquire_scalars(paths, retrieve, definition_version=version)
    assert len(imported.claim_ids) == (2 if dr_only else 8)
    assert adapter.network_requests == 4
    repository = EvidenceRepository(paths.database)
    associations = repository.source_claim_acquisitions_many(imported.claim_ids)
    for associated in associations.values():
        assert len(associated) == 2
        assert len({item.receipt.api_name for item in associated}) == 1
        assert {item.receipt.parameters["start_date"] for item in associated} == {
            "20260827",
            "20260828",
        }
    now = datetime.now(UTC)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="joint-interbank",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id="synthetic:joint-interbank",
        metric_ids=metrics,
        period="2026-08-28",
    )
    before = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert before.complete and len(before.selected_claim_ids) == (1 if dr_only else 4)

    def actual_inputs() -> set[str]:
        context = build_context_projection(
            repository,
            as_of=datetime(2026, 8, 29, tzinfo=UTC),
            as_of_mode=AsOfMode.PUBLIC,
            model_manifest=request["manifest"],
            target_business_date="2026-08-28",
        )
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return set(inputs)

    assert set(imported.claim_ids) <= actual_inputs()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = (
        item
        for item in acquisitions.history()
        if item.api_name == damaged_api and item.parameters["start_date"] == "20260828"
    )
    if dr_only:
        assert json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized")) == []
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged second API receipt")
    affected = "CN_DR007" if damaged_api == "repo_daily" else "CN_SHIBOR_ON_1W_3M"
    remaining = {
        point.selected_claim_id
        for metric in metrics
        if metric != affected
        for point in repository.metric_series(
            metric, mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
        )
    }
    after = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert after.complete is (affected not in metrics)
    assert set(after.selected_claim_ids) == set(before.selected_claim_ids) & remaining
    assert set(imported.claim_ids) & actual_inputs() == remaining


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("mixed_api", [False, True])
def test_registered_interbank_rejects_mixed_api_claim_links(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mixed_api: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = request["manifest"]["metric_catalog_version"]
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt_ids = []
    # Adversarial associations through public receipt APIs: valid responses from
    # two APIs are given the same delivered DR scalar and mixed acquisition IDs.
    responses = {
        "repo_daily": (
            ["ts_code", "trade_date", "repo_maturity", "weight"],
            ["DR007.IB", "20260828", "DR007", 1.3859],
        ),
        "shibor": (["date", "on", "1w", "3m"], ["20260828", 1.339, 1.387, 1.43]),
    }
    for api_name in ("repo_daily", "shibor") if mixed_api else ("repo_daily",):
        columns, row = responses[api_name]
        raw = encode({"code": 0, "data": {"fields": columns, "items": [row]}})

        def fetch(content: bytes = raw) -> bytes:
            return content

        acquired = acquisitions.capture(
            provider="tushare",
            api_name=api_name,
            parameters={
                "start_date": "20260828",
                "end_date": "20260828",
                **({"ts_code": "DR007.IB"} if api_name == "repo_daily" else {}),
            },
            fields=",".join(columns),
            parser_version="tushare-context-parser-v0002",
            fetch=fetch,
            parse=json.loads,
            normalize=lambda value: value,
            defer_validation=True,
        )
        receipt_ids.append(acquired.receipt.acquisition_id)
    scalar = ContextScalar(
        metric_id="CN_DR007",
        api_name="repo_daily",
        source_field="weight",
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={},
        value=1.3859,
        unit="percent",
        release_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
        public_available_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
        acquisition_ids=tuple(receipt_ids),
    )
    for receipt_id in receipt_ids:
        acquisitions.complete_validation(receipt_id, [asdict(scalar)])
    imported = ingest_context_scalars(
        paths, (scalar,), fetched_at=datetime.now(UTC), definition_version=version
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="interbank-mixed-api",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:interbank-mixed-api",
        metric_ids=("CN_DR007",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (not mixed_api)
    assert selection.selected_claim_ids == (() if mixed_api else imported.claim_ids)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("metric_id", ["CN_SHIBOR_ON_1W_3M", "CN_DR007"])
@pytest.mark.parametrize("artifact_kind", ["normalized", "raw"])
@pytest.mark.parametrize("artifact_state", ["damaged", "missing"])
@pytest.mark.parametrize("late_revision", [False, True])
def test_registered_interbank_public_replay_rejects_damaged_originals(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    metric_id: str,
    artifact_kind: str,
    artifact_state: str,
    late_revision: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, claims, receipts = {}, {}, {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id=metric_id)
        # Public component evaluation only; stored manifests retain admission gates.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        responses = {
            "repo_daily": {
                "code": 0,
                "fixture_side": side,
                "data": {
                    "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
                    "items": [
                        ["DR007.IB", "20260818", "DR007", 1.39],
                        ["DR007.IB", "20260828", "DR007", 1.3859],
                    ],
                },
            },
            "shibor": {
                "code": 0,
                "fixture_side": side,
                "data": {
                    "fields": ["date", "on", "1w", "3m"],
                    "items": [["20260828", 1.339, 1.387, 1.43]],
                },
            },
        }

        def transport(payload: dict[str, Any], data: dict[str, Any] = responses) -> bytes:
            return encode(data[payload["api_name"]])

        adapter = TushareContextAdapter("synthetic-token", transport=transport)

        def retrieve(source: TushareContextAdapter = adapter) -> tuple[ContextScalar, ...]:
            return tuple(
                replace(
                    scalar,
                    release_at=datetime.fromisoformat(scalar.period_end + "T08:00:00+00:00"),
                    public_available_at=datetime.fromisoformat(
                        scalar.period_end + "T08:00:00+00:00"
                    ),
                )
                for scalar in source.transmission(
                    start_date=date(2026, 8, 18), end_date=date(2026, 8, 28)
                )
                if scalar.metric_id == metric_id
            )

        imported = adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
        claims[side] = {
            point.selected_claim_id
            for point in EvidenceRepository(paths.database).metric_series(
                metric_id,
                mode=AsOfMode.PUBLIC,
                as_of=datetime(2026, 8, 29, tzinfo=UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            if point.period_end == "2026-08-28"
        }
        (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (imported.claim_ids[0],)
        )[imported.claim_ids[0]]
        receipts[side] = acquisition.receipt
        if metric_id == "CN_DR007":
            for day, folder, digest, suffix in (
                (
                    "2026-08-10",
                    "evidence-a18-import-20260909",
                    "80c4177bbf1d69c71e5fe3dc91b1fffbbdd41a30ebbe99947c3e58e53241861b",
                    "2026081008522023544",
                ),
                (
                    "2026-08-28",
                    "evidence-13",
                    "ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a",
                    "2026082808585347002",
                ),
            ):
                raw = (
                    Path(__file__).parents[2]
                    / ".scratch/pring-data-acquisition-repair"
                    / folder
                    / digest
                ).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == digest
                ingest_official_context_document(
                    paths,
                    raw,
                    family="pbc_omo_notice",
                    source_url=f"https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/{suffix}/index.html",
                    expected_period=day,
                    fetched_at=datetime.now(UTC),
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
    assert before.output_document is not None and before.evaluated_cutoffs == 1
    for side in ("comparison", "candidate"):
        actual = before.output_document["days"][0][side]["macro"][
            "model_input_observation_version_ids"
        ]
        assert claims[side] <= set(actual)
    receipt = receipts["candidate"]
    replay_day = "2026-08-28"
    original_candidate_ids = claims["candidate"].copy()
    next_day_claims: dict[str, set[str]] = {}
    if late_revision:
        # The later replay is a real daily cutoff, so both sides also need that
        # day's delivery. The revised August 28 value becomes a direction parent.
        for side in ("comparison", "candidate"):
            responses = {
                "repo_daily": {
                    "code": 0,
                    "fixture_side": side,
                    "data": {
                        "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
                        "items": [["DR007.IB", "20260831", "DR007", 1.45]],
                    },
                },
                "shibor": {
                    "code": 0,
                    "fixture_side": side,
                    "data": {
                        "fields": ["date", "on", "1w", "3m"],
                        "items": [["20260831", 1.4, 1.4, 1.45]],
                    },
                },
            }

            def next_transport(payload: dict[str, Any], data: dict[str, Any] = responses) -> bytes:
                return encode(data[payload["api_name"]])

            next_adapter = TushareContextAdapter("synthetic-token", transport=next_transport)

            def next_retrieve(
                source: TushareContextAdapter = next_adapter,
            ) -> tuple[ContextScalar, ...]:
                return tuple(
                    replace(
                        scalar,
                        release_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
                        public_available_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
                    )
                    for scalar in source.transmission(
                        start_date=date(2026, 8, 31), end_date=date(2026, 8, 31)
                    )
                    if scalar.metric_id == metric_id
                )

            next_import = next_adapter.acquire_scalars(
                paths,
                next_retrieve,
                definition_version=manifests[side]["metric_catalog_version"],
            )
            next_day_claims[side] = set(next_import.claim_ids)
        # A separately evidenced synthetic publication, not an API callback's
        # unproven claim that a changed value was publicly available earlier.
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        revised_raw = json.loads(acquisitions.read_content(receipt.acquisition_id, "raw"))
        revised_raw["fixture_revision"] = "explicit-public-20260831"
        fields = revised_raw["data"]["fields"]
        value_column = fields.index("weight" if metric_id == "CN_DR007" else "on")
        revised_raw["data"]["items"][-1][value_column] = 1.5
        raw_bytes = encode(revised_raw)
        acquired = acquisitions.capture(
            provider="tushare",
            api_name=receipt.api_name,
            parameters=receipt.parameters,
            fields=receipt.fields,
            parser_version=receipt.parser_version,
            fetch=lambda: raw_bytes,
            parse=json.loads,
            normalize=lambda value: value,
            defer_validation=True,
        )
        revised_scalars = json.loads(
            acquisitions.read_content(receipt.acquisition_id, "normalized")
        )
        public_at = datetime(2026, 8, 31, 9, tzinfo=UTC)
        for scalar in revised_scalars:
            scalar["acquisition_ids"] = [acquired.receipt.acquisition_id]
            if scalar["period_end"] == "2026-08-28":
                scalar["release_at"] = public_at.isoformat()
                scalar["public_available_at"] = public_at.isoformat()
                if scalar["source_field"] in {"weight", "on"}:
                    scalar["value"] = 1.5
        receipt = acquisitions.complete_validation(acquired.receipt.acquisition_id, revised_scalars)
        assert receipt.received_at is not None
        now = datetime.now(UTC)
        updated = EvidenceRepository(paths.database).append_source_claims(
            tuple(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version=manifests["candidate"]["metric_catalog_version"],
                    period_kind=scalar["period_kind"],
                    period_start=scalar["period_start"],
                    period_end=scalar["period_end"],
                    dimensions=scalar["dimensions"],
                    value=scalar["value"],
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=scalar["unit"],
                    provider="tushare",
                    source_reference=(
                        f"tushare:{scalar['api_name']}:{scalar['source_field']}:2026-08-28"
                    ),
                    release_event_id=f"synthetic:bank-revision:{metric_id}",
                    release_at=public_at,
                    public_available_at=public_at,
                    fetched_at=receipt.received_at,
                    available_at=now,
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                )
                for scalar in revised_scalars
                if scalar["period_end"] == "2026-08-28"
            )
        )
        claims["candidate"] = {claim.claim_id for claim in updated}
        assert original_candidate_ids.isdisjoint(claims["candidate"])
        replay_day = "2026-08-31"
        revised = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start=replay_day,
            requested_end=replay_day,
        )
        assert not revised.gaps, revised.gaps
        assert revised.output_document is not None
        adopted = set(
            revised.output_document["days"][0]["candidate"]["macro"][
                "model_input_observation_version_ids"
            ]
        )
        assert claims["candidate"] <= adopted
        assert next_day_claims["candidate"] <= adopted
        assert original_candidate_ids.isdisjoint(adopted)
    damaged_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert damaged_hash is not None
    damaged_path = paths.artifacts / damaged_hash[:2] / damaged_hash
    if artifact_state == "missing":
        damaged_path.unlink()
    else:
        damaged_path.write_bytes(b"damaged candidate interbank artifact")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start=replay_day,
        requested_end=replay_day,
    )
    if late_revision:
        # Current daily data remains complete; the damaged earlier direction
        # parent must be excluded rather than replaced by its superseded version.
        assert not after.gaps, after.gaps
    else:
        assert f"candidate_context_selection_invalid:{metric_id}" in after.gaps
    assert after.output_document is not None
    after_day = after.output_document["days"][0]
    assert not claims["candidate"] & set(
        after_day["candidate"]["macro"]["model_input_observation_version_ids"]
    )
    assert claims["comparison"] <= set(
        after_day["comparison"]["macro"]["model_input_observation_version_ids"]
    )
    assert original_candidate_ids.isdisjoint(
        after_day["candidate"]["macro"]["model_input_observation_version_ids"]
    )
    if late_revision:
        for side in ("comparison", "candidate"):
            assert next_day_claims[side] <= set(
                after_day[side]["macro"]["model_input_observation_version_ids"]
            )
        early = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert not early.gaps, early.gaps
        assert early.output_document is not None
        assert early.output_document["days"] == before.output_document["days"]


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


@pytest.mark.parametrize(
    ("normalized_fault", "consumer"),
    [
        ("none", "selection"),
        ("damaged", "selection"),
        ("wrong_value", "selection"),
        ("damaged", "context"),
        ("claim_value", "selection"),
        ("claim_period", "selection"),
        ("claim_reference", "selection"),
        ("claim_public", "selection"),
    ],
)
def test_registered_pmi_original_reaches_selection_and_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], normalized_fault: str, consumer: str
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
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(imported.claim_ids) <= set(model_inputs)
    cards = context.inventory["cards"]
    assert isinstance(cards, list)
    inventory_rows = [row for card in cards for row in card["evidence"]]
    derived_expected = {
        "CN_PRODUCTION_ORDER_SPREAD": 1.4,
        "CN_ORDER_INVENTORY_SPREAD": -0.1,
    }
    for metric_id, value in derived_expected.items():
        derived = next(row for row in inventory_rows if row["metric_id"] == metric_id)
        assert derived["value"] == pytest.approx(value)
        assert derived["status"] == "current"
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC).complete
    if normalized_fault != "none":
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        (receipt,) = acquisitions.history()
        assert receipt.raw_hash == digest
        assert receipt.normalized_hash is not None
        if normalized_fault == "damaged":
            normalized_path = (
                paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash
            )
            normalized_path.write_bytes(b'{"damaged":true}\n')
        else:
            wrong_normalized = json.loads(
                acquisitions.read_content(receipt.acquisition_id, "normalized")
            )
            manufacturing = next(
                scalar
                for scalar in wrong_normalized["scalars"]
                if scalar["metric_id"] == "CN_PMI_ACTIVITY"
                and scalar["dimensions"] == {"series": "manufacturing", "measure": "level"}
            )
            if normalized_fault == "wrong_value":
                manufacturing["value"] = 49.3
            malformed = acquisitions.capture(
                provider=receipt.provider,
                api_name=receipt.api_name,
                parameters=receipt.parameters,
                fields=receipt.fields,
                parser_version=receipt.parser_version,
                fetch=lambda: content,
                parse=lambda raw: parse_official_context_document(
                    raw,
                    family="nbs_pmi",
                    source_url=receipt.parameters["source_url"],
                    expected_period="2026-07",
                    fetched_at=now,
                ),
                normalize=lambda parsed: wrong_normalized,
                clock=lambda: now,
            ).receipt
            assert (
                json.loads(acquisitions.read_content(malformed.acquisition_id, "normalized"))
                == wrong_normalized
            )
            for metric_id in expected:
                for point in repository.metric_series(
                    metric_id, mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
                ):
                    claim = next(
                        item for item in point.claims if item.claim_id == point.selected_claim_id
                    )
                    assert claim.value is not None
                    assert claim.public_available_at is not None
                    linked = repository.append_source_claim(
                        SourceClaimInput(
                            metric_id=metric_id,
                            definition_version=version,
                            period_kind="month",
                            period_start=(
                                "2026-06-01"
                                if normalized_fault == "claim_period"
                                else point.period_start
                            ),
                            period_end=(
                                "2026-06-30"
                                if normalized_fault == "claim_period"
                                else point.period_end
                            ),
                            dimensions=point.dimensions,
                            value=(
                                claim.value + 0.1
                                if normalized_fault == "claim_value"
                                else claim.value
                            ),
                            value_state=claim.value_state,
                            unit=claim.unit,
                            provider=claim.provider,
                            source_reference=(
                                claim.source_reference + ":wrong"
                                if normalized_fault == "claim_reference"
                                else claim.source_reference
                            ),
                            release_event_id=imported.release_event_id
                            + (":synthetic-public" if normalized_fault == "claim_public" else ""),
                            release_at=claim.release_at,
                            public_available_at=(
                                claim.public_available_at + timedelta(minutes=1)
                                if normalized_fault == "claim_public"
                                else claim.public_available_at
                            ),
                            fetched_at=claim.fetched_at,
                            available_at=(
                                claim.available_at + timedelta(seconds=1)
                                if normalized_fault.startswith("claim_")
                                else claim.available_at
                            ),
                            certification_status=claim.certification_status,
                            quality_status=claim.quality_status,
                            acquisition_id=malformed.acquisition_id,
                        )
                    )
                    assert (linked.claim_id == claim.claim_id) is (
                        not normalized_fault.startswith("claim_")
                    )
        if consumer == "selection":
            if normalized_fault == "claim_period":
                run = RunRepository(paths.database).submit(
                    command_type="targeted_refresh",
                    target_business_date="2026-08-28",
                    client_request_id="pmi-wrong-period",
                    model_version_id=model_id,
                    system_as_of=now,
                    release_event_id=imported.release_event_id,
                    metric_ids=tuple(expected),
                    period="2026-06",
                )
            after = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
            assert not after.complete
            assert after.selected_claim_ids == ()
        else:
            after_context = build_context_projection(
                EvidenceRepository(paths.database),
                as_of=now,
                model_manifest=manifest,
                as_of_mode=AsOfMode.PUBLIC,
            )
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert not set(imported.claim_ids) & set(after_inputs)
            after_cards = after_context.inventory["cards"]
            assert isinstance(after_cards, list)
            after_rows = [row for card in after_cards for row in card["evidence"]]
            assert {
                row["status"] for row in after_rows if row["metric_id"] == "CN_PMI_INVENTORY"
            } == {"source_failed"}
            assert all(
                row["value"] is None or row["status"] not in {"current", "available"}
                for row in after_rows
                if row["metric_id"] in derived_expected
            )
            assert set(imported.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("metric_id", ["CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"])
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
@pytest.mark.parametrize("later_revision", [False, True])
def test_pmi_public_replay_reports_invalid_selected_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    metric_id: str,
    artifact_kind: str,
    later_revision: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    manifests = {}
    claims = {}
    receipts = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id=metric_id)
        # Public component seam only; stored manifests and full-model admission stay unchanged.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        for period, folder, digest, url, acquired_at in (
            (
                "2026-06",
                "evidence-macro-normalized",
                "f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c",
                "https://www.stats.gov.cn/sj/zxfb/202606/t20260630_1964032.html",
                datetime(2026, 7, 1, tzinfo=UTC),
            ),
            (
                "2026-07",
                "evidence-13",
                "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6",
                "https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
                datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ):
            raw = (evidence_root / folder / digest).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest

            def clock(value: datetime = acquired_at) -> datetime:
                return value

            imported = ingest_official_context_document(
                paths,
                raw + b"<!-- synthetic candidate receipt -->" if side == "candidate" else raw,
                family="nbs_pmi",
                source_url=url,
                expected_period=period,
                fetched_at=acquired_at,
                clock=clock,
                definition_version=manifest["metric_catalog_version"],
            )
            claims[side, period] = set(imported.claim_ids)
            (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
                (imported.claim_ids[0],)
            )[imported.claim_ids[0]]
            receipts[side, period] = acquisition.receipt
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not before.gaps, before.gaps
    assert before.evaluated_cutoffs == 1 and before.output_document is not None
    for side in ("comparison", "candidate"):
        day = before.output_document["days"][0][side]
        assert claims[side, "2026-07"] <= set(day["macro"]["model_input_observation_version_ids"])
    current_claims = claims["candidate", "2026-07"]
    evaluation_day = "2026-08-28"
    if later_revision:
        revised_at = datetime(2026, 8, 31, 2, tzinfo=UTC)
        july_original = (
            evidence_root
            / "evidence-13"
            / "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6"
        ).read_bytes()
        revised = ingest_official_context_document(
            paths,
            july_original.replace(b"49.9", b"50.0").replace(
                b"2026/07/31 09:30", b"2026/08/31 09:30"
            ),
            family="nbs_pmi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
            expected_period="2026-07",
            fetched_at=revised_at,
            clock=lambda: revised_at,
            definition_version=manifests["candidate"]["metric_catalog_version"],
        )
        current_claims = set(revised.claim_ids)
        (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (revised.claim_ids[0],)
        )[revised.claim_ids[0]]
        receipts["candidate", "2026-07"] = acquisition.receipt
        evaluation_day = "2026-08-31"
    receipt = receipts["candidate", "2026-07"]
    content_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert content_hash is not None
    assert content_hash not in {
        receipts["comparison", "2026-07"].raw_hash,
        receipts["comparison", "2026-07"].normalized_hash,
    }
    (paths.artifacts / content_hash[:2] / content_hash).write_bytes(b"damaged PMI artifact")
    if later_revision:
        historical = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert not historical.gaps, historical.gaps
        assert historical.evaluated_cutoffs == 1 and historical.output_document is not None
        historical_inputs = set(
            historical.output_document["days"][0]["candidate"]["macro"][
                "model_input_observation_version_ids"
            ]
        )
        assert claims["candidate", "2026-07"] <= historical_inputs
        assert historical_inputs.isdisjoint(current_claims)
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start=evaluation_day,
        requested_end=evaluation_day,
    )
    assert f"candidate_context_selection_invalid:{metric_id}" in after.gaps
    assert not any(gap.startswith("comparison_") for gap in after.gaps)
    assert after.evaluated_cutoffs == 1 and after.output_document is not None
    day = after.output_document["days"][0]
    candidate_inputs = set(day["candidate"]["macro"]["model_input_observation_version_ids"])
    assert candidate_inputs.isdisjoint(current_claims)
    assert candidate_inputs.isdisjoint(claims["candidate", "2026-07"])
    assert candidate_inputs.isdisjoint(claims["candidate", "2026-06"])
    assert claims["comparison", "2026-07"] <= set(
        day["comparison"]["macro"]["model_input_observation_version_ids"]
    )
    assert current_claims <= set(day["candidate"]["observation_version_ids"])


@pytest.mark.parametrize(
    "scenario", ["date_only", "unknown_public", "same_time_revision", "new_time_revision", "repeat"]
)
def test_registered_pmi_consumers_preserve_publication_precision_and_revisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], scenario: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    digest = "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6"
    original = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(original).hexdigest() == digest
    first_at = datetime(2026, 7, 31, 2, tzinfo=UTC)
    revised_at = datetime(2026, 8, 1, 2, tzinfo=UTC)
    content = original
    # Changes to the real archive are synthetic test inputs, never historical releases.
    if scenario == "date_only":
        content = content.replace(b"2026/07/31 09:30", "发布时间：2026-07-31".encode())
    elif scenario == "unknown_public":
        content = content.replace(b"2026/07/31 09:30", b"")
    first = ingest_official_context_document(
        paths,
        content,
        family="nbs_pmi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
        expected_period="2026-07",
        fetched_at=first_at,
        clock=lambda: first_at,
        definition_version=version,
    )
    latest = first
    if scenario in {"same_time_revision", "new_time_revision", "repeat"}:
        if scenario != "repeat":
            content = content.replace(b"49.9", b"50.0")
        if scenario == "new_time_revision":
            content = content.replace(b"2026/07/31 09:30", b"2026/08/01 09:30")
        latest = ingest_official_context_document(
            paths,
            content,
            family="nbs_pmi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
            expected_period="2026-07",
            fetched_at=revised_at,
            clock=lambda: revised_at,
            definition_version=version,
        )
    public_ids = (
        set()
        if scenario == "unknown_public"
        else set(first.claim_ids if scenario == "same_time_revision" else latest.claim_ids)
    )
    all_raw_ids = set(first.claim_ids) | set(latest.claim_ids)
    for mode in (AsOfMode.PUBLIC, AsOfMode.SYSTEM):
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=revised_at,
            model_manifest=manifest,
            as_of_mode=mode,
        )
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        expected_ids = public_ids if mode is AsOfMode.PUBLIC else set(latest.claim_ids)
        assert set(model_inputs) & all_raw_ids == expected_ids
        cards = context.inventory["cards"]
        assert isinstance(cards, list)
        rows = [row for card in cards for row in card["evidence"]]
        derived = [
            row
            for row in rows
            if row["metric_id"] == "CN_PRODUCTION_ORDER_SPREAD" and row["value"] is not None
        ]
        if mode is AsOfMode.PUBLIC and scenario == "unknown_public":
            assert derived == []
            assert model_inputs == []
        else:
            assert len(derived) == 1 and derived[0]["status"] == "current"
            revised_value = scenario == "new_time_revision" or (
                scenario == "same_time_revision" and mode is AsOfMode.SYSTEM
            )
            assert derived[0]["value"] == pytest.approx(1.5 if revised_value else 1.4)
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="pmi-precision-" + mode.value,
            model_version_id=model_id,
            system_as_of=revised_at,
            release_event_id=latest.release_event_id,
            metric_ids=("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
            period="2026-07",
        )
        selected = select_retrieval_input(paths, run, mode=mode)
        assert selected.complete is (scenario != "unknown_public")
        # Retrieval for a historical target also observes the PUBLIC bound in SYSTEM mode.
        assert set(selected.selected_claim_ids) == public_ids
    if scenario == "date_only":
        repository = EvidenceRepository(paths.database)
        for cutoff, expected_count in (
            (datetime(2026, 7, 31, 15, 59, 59, tzinfo=UTC), 0),
            (datetime(2026, 7, 31, 16, tzinfo=UTC), 4),
        ):
            points = repository.metric_series(
                "CN_PMI_ACTIVITY", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
            )
            assert len(points) == expected_count
            assert all(c.release_at is None for p in points for c in p.claims)
        system = build_context_projection(
            repository, as_of=first_at, model_manifest=manifest, as_of_mode=AsOfMode.SYSTEM
        )
        system_inputs = system.macro["model_input_observation_version_ids"]
        assert isinstance(system_inputs, list)
        assert set(first.claim_ids) <= set(system_inputs)


def test_pmi_invalid_latest_period_does_not_restore_older_derived_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    claims = {}
    for period, folder, digest, url, acquired_at in (
        (
            "2026-06",
            "evidence-macro-normalized",
            "f0cc6558252e9d754645aaaedcd8bd5f20f04cc1de5765ba2c6761d4222e159c",
            "https://www.stats.gov.cn/sj/zxfb/202606/t20260630_1964032.html",
            datetime(2026, 7, 1, tzinfo=UTC),
        ),
        (
            "2026-07",
            "evidence-13",
            "fff072e83f897a0a9e981e147105ecb81535958dfeaeafcf7881c24ede2a10d6",
            "https://www.stats.gov.cn/sj/zxfb/202607/t20260731_1964253.html",
            datetime(2026, 8, 1, tzinfo=UTC),
        ),
    ):
        raw = (evidence_root / folder / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest

        def clock(value: datetime = acquired_at) -> datetime:
            return value

        imported = ingest_official_context_document(
            paths,
            raw,
            family="nbs_pmi",
            source_url=url,
            expected_period=period,
            fetched_at=acquired_at,
            clock=clock,
            definition_version=manifest["metric_catalog_version"],
        )
        claims[period] = set(imported.claim_ids)

    def derived_rows(cutoff: datetime) -> tuple[dict[str, Any], list[str]]:
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=cutoff,
            model_manifest=manifest,
            as_of_mode=AsOfMode.PUBLIC,
        )
        cards = context.inventory["cards"]
        assert isinstance(cards, list)
        rows = {
            row["metric_id"]: row
            for card in cards
            for row in card["evidence"]
            if row["metric_id"] in {"CN_PRODUCTION_ORDER_SPREAD", "CN_ORDER_INVENTORY_SPREAD"}
        }
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return rows, inputs

    now = datetime(2026, 8, 1, tzinfo=UTC)
    current, current_inputs = derived_rows(now)
    # Independent July table arithmetic: 49.9 - 48.5 and 48.5 - 48.6.
    assert current["CN_PRODUCTION_ORDER_SPREAD"]["value"] == pytest.approx(1.4)
    assert current["CN_ORDER_INVENTORY_SPREAD"]["value"] == pytest.approx(-0.1)
    assert {row["period"] for row in current.values()} == {"2026-07-31"}
    assert claims["2026-07"] <= set(current_inputs)
    july = next(
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.parameters["period"] == "2026-07"
    )
    assert july.normalized_hash is not None
    (paths.artifacts / july.normalized_hash[:2] / july.normalized_hash).write_bytes(b"damaged")

    earlier, earlier_inputs = derived_rows(datetime(2026, 7, 30, tzinfo=UTC))
    # Independent June literals: 51.4 - 51.2 and 51.2 - 47.7.
    assert earlier["CN_PRODUCTION_ORDER_SPREAD"]["value"] == pytest.approx(0.2)
    assert earlier["CN_ORDER_INVENTORY_SPREAD"]["value"] == pytest.approx(3.5)
    assert {row["period"] for row in earlier.values()} == {"2026-06-30"}
    assert {row["status"] for row in earlier.values()} == {"current"}
    assert claims["2026-06"] <= set(earlier_inputs)
    assert not claims["2026-07"] & set(earlier_inputs)
    after, after_inputs = derived_rows(now)
    assert all(
        row["value"] is None or row["status"] not in {"current", "available"}
        for row in after.values()
    ), [(row["period"], row["status"], row["value"]) for row in after.values()]
    assert not (claims["2026-06"] | claims["2026-07"]) & set(after_inputs)


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
@pytest.mark.parametrize("consumer", ["none", "selection", "context"])
def test_registered_official_original_reaches_selection_and_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    family: str,
    digest: str,
    url: str,
    period: str,
    count: int,
    anchors: dict[str, tuple[dict[str, str], float, str]],
    consumer: str,
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
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(imported.claim_ids) <= set(model_inputs)

    if consumer != "none":
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        (receipt,) = acquisitions.history()
        assert receipt.raw_hash == digest
        assert receipt.normalized_hash is not None
        normalized_path = paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash
        normalized_path.write_bytes(b'{"damaged":true}\n')
        if consumer == "selection":
            invalid_selection = select_retrieval_input(paths, run)
            assert not invalid_selection.complete
            assert invalid_selection.selected_claim_ids == ()
        else:
            after_context = build_context_projection(repository, as_of=now, model_manifest=manifest)
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert set(imported.claim_ids).isdisjoint(after_inputs)
            assert set(imported.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("damaged_period", ["2026-05", "2026-06", "2026-07"])
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized", "invalid_quality"])
def test_registered_loan_monthly_change_checks_required_period_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_period: str, artifact_kind: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    now = datetime(2026, 8, 29, tzinfo=UTC)
    archive = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    claims = {}
    for period, directory, digest, url in (
        (
            "2026-05",
            "evidence-macro-derived",
            "8f71dd1e651d2e5d8e7120555a000c54a517c41fb01d94b39948183badab9769",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026061217051611931/index.html",
        ),
        (
            "2026-06",
            "evidence-macro-derived",
            "9ebce7e21c93d92980814be8f754dcc255ebe29dbbdf2531973e09361832c168",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026071515025183948/index.html",
        ),
        (
            "2026-07",
            "evidence-13",
            "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
        ),
    ):
        raw = (archive / directory / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        imported = ingest_official_context_document(
            paths,
            raw,
            family="pbc_loan_structure",
            source_url=url,
            expected_period=period,
            fetched_at=now,
            clock=lambda: now,
            definition_version=version,
        )
        claims[period] = set(imported.claim_ids)

    def monthly_rows(cutoff: datetime) -> tuple[list[dict[str, Any]], list[str]]:
        context = build_context_projection(
            repository, as_of=cutoff, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
        )
        credit = context.macro["credit"]
        assert isinstance(credit, dict)
        rows = [
            row
            for row in credit["evidence"]
            if row["metric_id"] == "CN_LOAN_STRUCTURE"
            and row["dimensions"].get("measure") == "monthly_change"
        ]
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return rows, inputs

    for cutoff, expected_period, expected_value in (
        (datetime(2026, 7, 31, tzinfo=UTC), "2026-06-30", 5600),
        (now, "2026-07-31", -2300),
    ):
        rows, inputs = monthly_rows(cutoff)
        (enterprise,) = (
            row
            for row in rows
            if row["dimensions"]["borrower"] == "enterprise"
            and row["dimensions"]["tenor"] == "long_term"
        )
        assert (enterprise["period"], enterprise["value"], enterprise["status"]) == (
            expected_period,
            expected_value,
            "current",
        )
        assert set(enterprise["input_observation_version_ids"]) <= set(inputs)

    (receipt,) = (
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.parameters["period"] == damaged_period
    )
    if artifact_kind == "invalid_quality":
        for point in repository.metric_series(
            "CN_LOAN_STRUCTURE", mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
        ):
            if point.period_end[:7] != damaged_period:
                continue
            claim = next(item for item in point.claims if item.claim_id == point.selected_claim_id)
            invalid = repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_LOAN_STRUCTURE",
                    definition_version=version,
                    period_kind="year_to_month",
                    period_start=point.period_start,
                    period_end=point.period_end,
                    dimensions=point.dimensions,
                    value=claim.value,
                    value_state=claim.value_state,
                    unit=claim.unit,
                    provider=claim.provider,
                    source_reference=claim.source_reference,
                    release_event_id=f"synthetic:loan-quality-review:{damaged_period}",
                    release_at=claim.release_at,
                    public_available_at=claim.public_available_at,
                    fetched_at=now,
                    available_at=now + timedelta(seconds=1),
                    certification_status="certified",
                    quality_status="invalid",
                    acquisition_id=receipt.acquisition_id,
                )
            )
            claims[damaged_period].add(invalid.claim_id)
    else:
        content_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
        assert content_hash is not None
        (paths.artifacts / content_hash[:2] / content_hash).write_bytes(b"damaged loan artifact")
    after_rows, after_inputs = monthly_rows(now + timedelta(seconds=1))
    if damaged_period == "2026-05":
        assert len(after_rows) == 9
        assert {row["period"] for row in after_rows} == {"2026-07-31"}
        (enterprise,) = (
            row
            for row in after_rows
            if row["dimensions"]["borrower"] == "enterprise"
            and row["dimensions"]["tenor"] == "long_term"
        )
        assert enterprise["value"] == -2300
    else:
        assert after_rows == []
    assert claims[damaged_period].isdisjoint(after_inputs)
    earlier_rows, earlier_inputs = monthly_rows(datetime(2026, 7, 31, tzinfo=UTC))
    if damaged_period == "2026-07":
        assert len(earlier_rows) == 9
        assert {row["period"] for row in earlier_rows} == {"2026-06-30"}
        assert claims["2026-05"] | claims["2026-06"] <= set(earlier_inputs)
    else:
        assert earlier_rows == []
    assert claims["2026-07"].isdisjoint(earlier_inputs)


@pytest.mark.parametrize(
    ("damaged_parent", "artifact_kind"),
    [
        ("maturing", "raw"),
        ("maturing", "normalized"),
        ("current", "raw"),
        ("current", "normalized"),
        ("calendar", "raw"),
        ("calendar", "normalized"),
        ("calendar", "invalid_quality"),
    ],
)
def test_registered_omo_net_injection_checks_operation_and_calendar_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_parent: str, artifact_kind: str
) -> None:
    from pring_cycle.source_adapters import TushareCoreAdapter

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    now = datetime(2026, 8, 29, tzinfo=UTC)
    archive = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    for period, directory, digest, url in (
        (
            "2026-08-21",
            "evidence-macro-derived",
            "d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082108525095972/index.html",
        ),
        (
            "2026-08-28",
            "evidence-13",
            "ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html",
        ),
    ):
        raw = (archive / directory / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        ingest_official_context_document(
            paths,
            raw,
            family="pbc_omo_notice",
            source_url=url,
            expected_period=period,
            fetched_at=now,
            clock=lambda: now,
            definition_version=version,
        )
    # A synthetic, explicitly public core delivery supplies this isolated calendar day.
    # This is not historical PUBLIC certification of a real index response.
    day = date(2026, 8, 28)
    calendar_days = (day, date(2026, 8, 31)) if artifact_kind == "invalid_quality" else (day,)
    core_raw = encode(
        {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "close", "pre_close", "pct_chg"],
                "items": [
                    ["000985.CSI", calendar_day.strftime("%Y%m%d"), 101, 100, 1]
                    for calendar_day in calendar_days
                ],
            },
        }
    )
    receipt = (
        TushareCoreAdapter("synthetic-token", transport=lambda payload: core_raw)
        .acquire_core_bars(
            acquisitions,
            "CN_EQUITY_CORE_000985",
            start=day,
            end=calendar_days[-1],
            expected_business_dates=calendar_days,
        )
        .receipt
    )
    assert receipt.received_at is not None and receipt.validated_at is not None
    published = datetime(2026, 8, 28, 8, tzinfo=UTC)
    calendar_input = SourceClaimInput(
        metric_id="CN_EQUITY_CORE_000985",
        definition_version=version,
        period_kind="business_day",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        dimensions={},
        value=101,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="index_points",
        provider="tushare",
        source_reference="tushare:index_daily:000985.CSI:2026-08-28",
        release_event_id="synthetic:omo-core-public-calendar:2026-08-28",
        release_at=published,
        public_available_at=published,
        fetched_at=receipt.received_at,
        available_at=receipt.validated_at,
        certification_status="certified",
        quality_status="validated",
        acquisition_id=receipt.acquisition_id,
    )
    calendar_claim = repository.append_source_claim(calendar_input)
    if artifact_kind == "invalid_quality":
        repository.append_source_claim(
            replace(
                calendar_input,
                period_start="2026-08-31",
                period_end="2026-08-31",
                source_reference="tushare:index_daily:000985.CSI:2026-08-31",
                release_event_id="synthetic:omo-core-public-calendar:2026-08-31",
                release_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
                public_available_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
            )
        )
        now = datetime(2026, 9, 1, tzinfo=UTC)
    calendar_run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-omo-calendar",
        model_version_id=model_id,
        system_as_of=receipt.validated_at + timedelta(seconds=1),
        release_event_id="synthetic:omo-core-public-calendar:2026-08-28",
        metric_ids=("CN_EQUITY_CORE_000985",),
        period="2026-08-28",
    )
    calendar_selection = select_retrieval_input(paths, calendar_run, mode=AsOfMode.PUBLIC)
    assert calendar_selection.complete
    assert calendar_selection.selected_claim_ids == (calendar_claim.claim_id,)
    injection_claims = {
        point.period_end: point.selected_claim_id
        for point in repository.metric_series(
            "CN_OMO_7D_AMOUNT", mode=AsOfMode.PUBLIC, as_of=now, definition_version=version
        )
        if point.dimensions == {"measure": "injection"}
    }

    def net_rows() -> tuple[list[dict[str, Any]], list[str]]:
        context = build_context_projection(
            repository, as_of=now, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
        )
        policy = context.macro["policy_action"]
        assert isinstance(policy, dict)
        rows = [
            row
            for row in policy["evidence"]
            if row["metric_id"] == "CN_OMO_7D_AMOUNT"
            and row["dimensions"] == {"measure": "net_injection"}
        ]
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return rows, inputs

    (before,), inputs = net_rows()
    assert (before["period"], before["value"], before["status"]) == ("2026-08-28", -750, "current")
    assert set(before["input_observation_version_ids"]) == {
        *injection_claims.values(),
        calendar_claim.claim_id,
    }
    assert set(before["input_observation_version_ids"]) <= set(inputs)
    excluded_id: str | None
    if damaged_parent == "calendar":
        damaged_receipt = receipt
        excluded_id = calendar_claim.claim_id
    else:
        damaged_day = "2026-08-21" if damaged_parent == "maturing" else "2026-08-28"
        (damaged_receipt,) = (
            item
            for item in acquisitions.history()
            if item.parameters.get("family") == "pbc_omo_notice"
            and item.parameters["period"] == damaged_day
        )
        excluded_id = injection_claims[damaged_day]
    assert excluded_id is not None
    if artifact_kind == "invalid_quality":
        repository.append_source_claim(
            replace(
                calendar_input,
                release_event_id=calendar_input.release_event_id + ":synthetic-quality-review",
                available_at=receipt.validated_at + timedelta(seconds=1),
                quality_status="invalid",
            )
        )
    else:
        damaged_hash = (
            damaged_receipt.raw_hash if artifact_kind == "raw" else damaged_receipt.normalized_hash
        )
        assert damaged_hash is not None
        (paths.artifacts / damaged_hash[:2] / damaged_hash).write_bytes(
            b"damaged OMO maturity parent"
        )
    after_rows, after_inputs = net_rows()
    assert after_rows == []
    assert excluded_id not in after_inputs


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


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["normalized", "raw", "invalid_quality"])
@pytest.mark.parametrize("damaged_parent", ["rate", "dr007"])
def test_registered_policy_spread_rejects_damaged_latest_rate_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damaged_parent: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    version = manifest["metric_catalog_version"]
    repository = EvidenceRepository(paths.database)
    # Synthetic TuShare deliveries carry independently audited CFETS values.
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
    adapter = TushareContextAdapter(
        "synthetic-token", transport=lambda payload: encode(responses[payload["api_name"]])
    )
    public_at = datetime(2026, 8, 28, 8, tzinfo=UTC)  # Explicit synthetic publication time.

    def retrieve() -> tuple[ContextScalar, ...]:
        return tuple(
            replace(scalar, release_at=public_at, public_available_at=public_at)
            for scalar in adapter.transmission(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
        )

    adapter.acquire_scalars(paths, retrieve, definition_version=version)
    now = datetime.now(UTC)
    archive = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    for day, directory, digest, url in (
        (
            "2026-08-21",
            "evidence-macro-derived",
            "d5673e8e4351bc2a1ff1afdcdd89da9ba2c3c7a8fe946c3cd463c164da0cd834",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082108525095972/index.html",
        ),
        (
            "2026-08-28",
            "evidence-13",
            "ee19f9d0ca925b95875448bda4f354558ee7c6f06c36d9a3a62eafb9d59e4a1a",
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/2026082808585347002/index.html",
        ),
    ):
        raw = (archive / directory / digest).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        ingest_official_context_document(
            paths,
            raw,
            family="pbc_omo_notice",
            source_url=url,
            expected_period=day,
            fetched_at=now,
            clock=lambda: now,
            definition_version=version,
        )
    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    (dr007,) = repository.metric_series(
        "CN_DR007", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
    )
    rates = repository.metric_series(
        "CN_OMO_7D_RATE", mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
    )
    assert [(point.period_end, point.selected_value) for point in rates] == [
        ("2026-08-21", 1.4),
        ("2026-08-28", 1.4),
    ]

    def policy_spread() -> tuple[list[dict[str, Any]], list[str]]:
        context = build_context_projection(
            repository,
            as_of=cutoff,
            as_of_mode=AsOfMode.PUBLIC,
            target_business_date="2026-08-28",
            model_manifest=manifest,
            persist_derived=True,
        )
        transmission = context.macro["transmission"]
        assert isinstance(transmission, dict)
        inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(inputs, list)
        return [
            row
            for row in transmission["evidence"]
            if row["metric_id"] == "CN_DR007_POLICY_SPREAD" and "derived_observation_id" in row
        ], inputs

    (before,), inputs = policy_spread()
    assert (before["period"], before["unit"], before["status"]) == (
        "2026-08-28",
        "basis_points",
        "current",
    )
    assert before["value"] == pytest.approx(-1.41, rel=0, abs=1e-12)
    parents = {dr007.selected_claim_id, rates[-1].selected_claim_id}
    assert set(before["input_observation_version_ids"]) == parents
    assert parents <= set(inputs)
    assert rates[0].selected_claim_id not in parents
    trace = repository.derived_trace(
        before["derived_observation_id"], mode=AsOfMode.PUBLIC, as_of=cutoff
    )
    assert set(trace.input_observation_version_ids) == parents

    (receipt,) = (
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if (
            receipt.api_name == "repo_daily"
            if damaged_parent == "dr007"
            else receipt.parameters.get("period") == "2026-08-28"
        )
    )
    damaged_metric = "CN_DR007" if damaged_parent == "dr007" else "CN_OMO_7D_RATE"
    damaged_point = dr007 if damaged_parent == "dr007" else rates[-1]
    excluded_id = damaged_point.selected_claim_id
    if artifact_kind == "invalid_quality":
        claim = next(item for item in damaged_point.claims if item.claim_id == excluded_id)
        invalid = repository.append_source_claim(
            SourceClaimInput(
                metric_id=damaged_metric,
                definition_version=version,
                period_kind="business_day",
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions={},
                value=claim.value,
                value_state=claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id="synthetic:policy-rate-quality-review",
                release_at=claim.release_at,
                public_available_at=claim.public_available_at,
                fetched_at=claim.fetched_at,
                available_at=now + timedelta(seconds=1),
                certification_status="certified",
                quality_status="invalid",
                acquisition_id=receipt.acquisition_id,
            )
        )
        excluded_id = invalid.claim_id
        assert (
            repository.metric_series(
                damaged_metric, mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
            )[-1].selected_claim_id
            == excluded_id
        )
    else:
        content_hash = (
            receipt.normalized_hash if artifact_kind == "normalized" else receipt.raw_hash
        )
        assert content_hash is not None
        (paths.artifacts / content_hash[:2] / content_hash).write_bytes(
            b"damaged policy rate artifact"
        )
    after, after_inputs = policy_spread()
    assert after == []
    assert excluded_id not in after_inputs
    assert damaged_point.selected_claim_id not in after_inputs
    if damaged_parent == "dr007":
        assert rates[-1].selected_claim_id in after_inputs
    assert before["derived_observation_id"] not in after_inputs


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
        # Synthetic documents isolate event selection; they are not official historical rates.
        url = f"https://www.pbc.gov.cn/synthetic-omo-{day}.html"
        event_raw = f"""
        <html><body><h1>{day} 公开市场业务交易公告（合成测试）</h1>
        <p>发布时间：2026-06-03 09:00</p><table>
        <tr><th>操作日</th><th>品种</th><th>期限</th><th>中标利率（%）</th>
        <th>投放量（亿元）</th><th>到期量（亿元）</th></tr>
        <tr><td>{day}</td><td>逆回购</td><td>7天</td><td>{value}</td>
        <td>10</td><td>0</td></tr></table></body></html>
        """.encode()

        def parse_event(
            content: bytes, event_day: str = day, event_url: str = url
        ) -> ParsedOfficialContextRelease:
            return parse_official_context_document(
                content,
                family="pbc_omo_notice",
                source_url=event_url,
                expected_period=event_day,
                fetched_at=now,
            )

        def fetch_event(content: bytes = event_raw) -> bytes:
            return content

        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider="中国人民银行",
            api_name="document_import",
            parameters={"source_url": url, "period": day, "family": "pbc_omo_notice"},
            fields="",
            parser_version="official-context-parser-v0004",
            fetch=fetch_event,
            parse=parse_event,
            normalize=asdict,
            clock=lambda: now,
        )
        receipt = acquired.receipt
        assert receipt.received_at is not None and receipt.validated_at is not None
        assert (
            next(
                item.value for item in acquired.value.scalars if item.metric_id == "CN_OMO_7D_RATE"
            )
            == value
        )
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
                source_reference=f"{url}#sha256={receipt.raw_hash}",
                release_event_id=f"synthetic:omo:{day}",
                release_at=acquired.value.release_at,
                public_available_at=acquired.value.public_available_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="invalid" if latest_invalid and day == latest_day else "validated",
                acquisition_id=receipt.acquisition_id,
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
    repository = EvidenceRepository(paths.database)
    digest = "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    url = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html"
    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="中国人民银行",
        api_name="document_import",
        parameters={"source_url": url, "period": "2026-07", "family": "pbc_social_financing"},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: raw,
        parse=lambda content: parse_official_context_document(
            content,
            family="pbc_social_financing",
            source_url=url,
            expected_period="2026-07",
            fetched_at=now,
        ),
        normalize=asdict,
        clock=lambda: now,
    )
    receipt = acquired.receipt
    assert receipt.received_at is not None and receipt.validated_at is not None
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
    # Retain the complete captured document, but submit an incomplete member set publicly.
    # The isolated review and acquisition clock do not certify a real production source.
    for scalar in acquired.value.scalars:
        if scalar.metric_id != "CN_SF_COMPONENTS" or (
            scalar.dimensions["measure"] == "stock_yoy"
            and scalar.dimensions["component"] in components[:missing_count]
        ):
            continue
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=scalar.metric_id,
                definition_version=version,
                period_kind=scalar.period_kind,
                period_start=scalar.period_start,
                period_end=scalar.period_end,
                dimensions=scalar.dimensions,
                value=scalar.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=scalar.unit,
                provider=acquired.value.provider,
                source_reference=f"{url}#sha256={receipt.raw_hash}",
                release_event_id=acquired.value.release_event_id,
                release_at=acquired.value.release_at,
                public_available_at=acquired.value.public_available_at,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                certification_status="certified",
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            )
        )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="partial-sf",
        model_version_id=model_id,
        system_as_of=now,
        release_event_id=acquired.value.release_event_id,
        metric_ids=("CN_SF_COMPONENTS",),
        period="2026-07",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete
    assert len(selection.selected_claim_ids) == 24 - missing_count
    assert len(selection.missing_members) == missing_count
    assert all('"measure": "stock_yoy"' in missing for missing in selection.missing_members)


def synthetic_coherent_gdp_release(period: str, *, fractional: bool = False) -> tuple[bytes, str]:
    # Deliberately synthetic public transport data. This tests the full formula
    # without asserting that mixed historical GDP releases share a vintage.
    year, quarter = int(period[:4]), int(period[-1])
    label = ("一季度", "二季度", "三季度", "四季度")[quarter - 1]
    release_year = year + 1 if quarter == 4 else year
    release_month = 1 if quarter == 4 else quarter * 3 + 1
    header = "<tr><td></td><td>绝对额（亿元）</td><td>比上年同期增长（%）</td></tr>"
    if quarter != 1:
        cumulative = ("", "上半年", "前三季度", "全年")[quarter - 1]
        header += (
            f"<tr><td>{label}</td><td>{cumulative}</td><td>{label}</td><td>{cumulative}</td></tr>"
        )
    rows = []
    for name, value in (
        ("GDP", 350000),
        ("第一产业", 10000),
        ("第二产业", 140000),
        ("第三产业", 200000),
    ):
        quarter_value = Decimal(value)
        if fractional and name in ("GDP", "第一产业"):
            quarter_value += Decimal("0.1")
        cells = (
            (name, quarter_value, 5)
            if quarter == 1
            else (name, quarter_value, quarter_value * quarter, 5, 5)
        )
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    document = (
        "<html><body><p>synthetic fixture; not official economic data</p>"
        f"<h1>{year}年{label}国内生产总值初步核算结果</h1>"
        f"<p>发布时间：{release_year}-{release_month:02d}-16 09:30</p>"
        f"<table>{header}{''.join(rows)}"
        "<tr><td>绝对额按现价计算，增长速度按不变价计算。</td></tr></table></body></html>"
    )
    return document.encode(), f"https://www.stats.gov.cn/sj/synthetic-credit-window-{period}.html"


def synthetic_prior_social_financing_release(month: int = 6) -> tuple[bytes, str]:
    # A deliberately synthetic extra month makes old-window fallback observable.
    months_label, total = {5: ("前五个月", 15), 6: ("前六个月", 18)}[month]
    document = f"""<html><body><p>synthetic fixture; not official economic data</p>
    <h1>2024年{month}月社会融资规模增量统计数据报告</h1>
    <p>发布时间：2024-{month + 1:02d}-13 17:00:00</p>
    <p>2024年{months_label}社会融资规模增量累计为{total}万亿元。
    其中，对实体经济发放的人民币贷款增加12.38万亿元；
    对实体经济发放的外币贷款折合人民币减少970亿元；委托贷款减少573亿元；
    信托贷款增加3072亿元；未贴现的银行承兑汇票减少3440亿元；
    企业债券净融资1.61万亿元；政府债券净融资4.03万亿元；
    非金融企业境内股票融资1445亿元。</p></body></html>"""
    return (
        document.encode(),
        f"https://www.pbc.gov.cn/synthetic-credit-window-2024-{month:02d}.html",
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "coherent",
        "coherent_decimal",
        "synthetic_inconsistent",
        "actual_revised",
        "damaged_social_raw",
        "damaged_social_normalized",
        "damaged_gdp_raw",
        "damaged_gdp_normalized",
        "unused_old_raw",
        "latest_nonpositive_gdp",
        "latest_quality_gdp",
        "latest_certification_gdp",
        "latest_quality_social",
        "latest_certification_social",
        "latest_nondisclosed_gdp",
        "latest_nondisclosed_social",
        "older_social_window",
        "latest_missing_social_baseline",
    ],
)
@pytest.mark.parametrize("mode", [AsOfMode.PUBLIC, AsOfMode.SYSTEM])
def test_registered_credit_window_requires_comparable_gdp_release_baselines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: AsOfMode, scenario: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    model_id = manifest["model_version_id"]
    version = manifest["metric_catalog_version"]
    model_before = ModelRepository(paths.database).get(model_id)
    has_older_gdp = scenario in (
        "unused_old_raw",
        "latest_nonpositive_gdp",
        "latest_quality_gdp",
        "latest_certification_gdp",
        "latest_nondisclosed_gdp",
    )
    has_older_social = scenario in (
        "latest_quality_social",
        "latest_certification_social",
        "latest_nondisclosed_social",
        "older_social_window",
        "latest_missing_social_baseline",
    )
    has_two_older_social = scenario in ("older_social_window", "latest_missing_social_baseline")
    missing_social_baseline = scenario == "latest_missing_social_baseline"
    root = Path(__file__).parents[2]
    fixture = json.loads(
        (
            root / ".scratch/pring-data-acquisition-repair/credit-window-inputs-186/manifest.json"
        ).read_text()
    )
    assert fixture["parent_count"] == {"social_financing": 25, "gdp": 9}
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    fixture_time = datetime(2026, 8, 29, tzinfo=UTC)

    def fixture_clock() -> datetime:
        return fixture_time

    for parent in fixture["parents"]:
        if (
            missing_social_baseline
            and parent["family"] == "pbc_social_financing"
            and parent["period"] == "2026-06"
        ):
            continue
        raw = (root / parent["raw_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == parent["raw_sha256"]
        source_url = parent["source_url"]
        if scenario != "actual_revised" and parent["family"] == "nbs_gdp":
            raw, source_url = synthetic_coherent_gdp_release(
                parent["period"], fractional=scenario == "coherent_decimal"
            )
            if scenario == "synthetic_inconsistent" and parent["period"] == "2025-Q4":
                # One changed input cell; URL, PUBLIC time and the other 33 parents stay equal.
                original_cell = b"<td>GDP</td><td>350000</td><td>1400000</td>"
                changed_cell = b"<td>GDP</td><td>350000</td><td>1401000</td>"
                assert raw.count(original_cell) == 1
                raw = raw.replace(original_cell, changed_cell, 1)
            if scenario == "latest_nonpositive_gdp" and parent["period"] == "2026-Q2":
                original_cell = b"<td>GDP</td><td>350000</td><td>700000</td>"
                changed_cell = b"<td>GDP</td><td>350000</td><td>350000</td>"
                assert raw.count(original_cell) == 1
                raw = raw.replace(original_cell, changed_cell, 1)
        result = ingest_official_context_document(
            paths,
            raw,
            family=parent["family"],
            source_url=source_url,
            expected_period=parent["period"],
            fetched_at=fixture_clock(),
            clock=fixture_clock,
            definition_version=version,
        )
        assert result.claim_ids
    if has_older_gdp:
        old_raw, old_url = synthetic_coherent_gdp_release("2024-Q1")
        old_result = ingest_official_context_document(
            paths,
            old_raw,
            family="nbs_gdp",
            source_url=old_url,
            expected_period="2024-Q1",
            fetched_at=fixture_clock(),
            clock=fixture_clock,
            definition_version=version,
        )
        assert old_result.claim_ids
    if has_older_social:
        for month in (5, 6) if has_two_older_social else (6,):
            old_raw, old_url = synthetic_prior_social_financing_release(month)
            old_result = ingest_official_context_document(
                paths,
                old_raw,
                family="pbc_social_financing",
                source_url=old_url,
                expected_period=f"2024-{month:02d}",
                fetched_at=fixture_clock(),
                clock=fixture_clock,
                definition_version=version,
            )
            assert old_result.claim_ids
    after = fixture_clock()
    cutoff = datetime(2026, 8, 28, 15, 59, tzinfo=UTC) if mode is AsOfMode.PUBLIC else after
    repository = EvidenceRepository(paths.database)
    for metric_id in ("CN_SF_TOTAL", "CN_GDP"):
        before_acquisition = repository.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=fixture_time - timedelta(microseconds=1),
            definition_version=version,
        )
        assert all(
            point.selected_claim_id is None and point.selected_value is None and point.claims == ()
            for point in before_acquisition
        )
    parent_ids: set[str | None] = set()
    baseline_ids: dict[str, str] = {}
    unused_gdp_id = None
    for metric, dimensions, count in (
        ("CN_SF_TOTAL", {"measure": "ytd_increment"}, 25),
        ("CN_GDP", {"aggregate": "total", "measure": "nominal_ytd_level"}, 9),
    ):
        selected = [
            point
            for point in repository.metric_series(
                metric, mode=mode, as_of=cutoff, definition_version=version
            )
            if point.dimensions == dimensions
        ]
        has_extra = (has_older_gdp and metric == "CN_GDP") or (
            has_older_social and metric == "CN_SF_TOTAL"
        )
        extra_count = (2 if has_two_older_social else 1) if has_extra else 0
        missing_count = int(missing_social_baseline and metric == "CN_SF_TOTAL")
        assert len(selected) == count + extra_count - missing_count
        assert all(point.selection_status == "selected" for point in selected)
        if has_older_gdp and metric == "CN_GDP":
            (unused,) = [point for point in selected if point.period_end == "2024-03-31"]
            unused_gdp_id = unused.selected_claim_id
            assert unused_gdp_id is not None
            selected = [point for point in selected if point.period_end != "2024-03-31"]
        if has_older_social and metric == "CN_SF_TOTAL":
            old_periods = {"2024-05-31", "2024-06-30"} if has_two_older_social else {"2024-06-30"}
            unused_points = [point for point in selected if point.period_end in old_periods]
            assert len(unused_points) == extra_count
            assert all(point.selected_claim_id is not None for point in unused_points)
            selected = [point for point in selected if point.period_end not in old_periods]
        if missing_count:
            assert not any(point.period_end == "2026-06-30" for point in selected)
            (latest,) = [point for point in selected if point.period_end == "2026-07-31"]
            assert latest.selected_value is not None and latest.selected_claim_id is not None
        parent_ids.update(point.selected_claim_id for point in selected)
        baseline = min(selected, key=lambda point: point.period_end)
        assert baseline.selected_claim_id is not None
        baseline_ids[metric] = baseline.selected_claim_id
    assert len(parent_ids) == 34 - int(missing_social_baseline)
    assert len(acquisitions.history()) == (
        34
        - int(missing_social_baseline)
        + int(has_older_gdp)
        + int(has_older_social)
        + int(has_two_older_social)
    )
    assert all(receipt.state == "validated" for receipt in acquisitions.history())
    if scenario == "unused_old_raw":
        assert unused_gdp_id is not None and unused_gdp_id not in parent_ids
        ((receipt, _),) = repository.source_claim_originals(unused_gdp_id)
        assert receipt.raw_hash is not None
        artifact = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == receipt.raw_hash
        artifact.write_bytes(b"damaged unused older GDP release")
    damaged_parent_id = None
    if scenario.startswith("damaged_"):
        _, family, artifact_kind = scenario.split("_")
        damaged_parent_id = baseline_ids["CN_SF_TOTAL" if family == "social" else "CN_GDP"]
        ((receipt, _),) = repository.source_claim_originals(damaged_parent_id)
        artifact_hash = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
        assert artifact_hash is not None
        artifact = paths.artifacts / artifact_hash[:2] / artifact_hash
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == artifact_hash
        artifact.write_bytes(b"damaged selected earliest cumulative baseline after ingestion")
    reviewed_ids: set[str] = set()
    if scenario.startswith(("latest_quality_", "latest_certification_", "latest_nondisclosed_")):
        _, fault, family = scenario.split("_")
        # This synthetic disqualified review is an adversarial source declaration,
        # not a fetch failure, actual disclosure revision, or real certification.
        nondisclosed = fault == "nondisclosed"
        metric = "CN_GDP" if family == "gdp" else "CN_SF_TOTAL"
        dimensions = (
            {"aggregate": "total", "measure": "nominal_ytd_level"}
            if family == "gdp"
            else {"measure": "ytd_increment"}
        )
        latest = max(
            (
                point
                for point in repository.metric_series(
                    metric, mode=mode, as_of=cutoff, definition_version=version
                )
                if point.dimensions == dimensions
            ),
            key=lambda point: point.period_end,
        )
        claim = next(item for item in latest.claims if item.claim_id == latest.selected_claim_id)
        ((receipt, _),) = repository.source_claim_originals(claim.claim_id)
        reviewed = repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric,
                definition_version=version,
                period_kind="year_to_quarter" if family == "gdp" else "year_to_month",
                period_start=latest.period_start,
                period_end=latest.period_end,
                dimensions=latest.dimensions,
                value=None if nondisclosed else claim.value,
                value_state=EvidenceValueState.NOT_DISCLOSED if nondisclosed else claim.value_state,
                unit=claim.unit,
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id=f"synthetic:credit-input-review:{scenario}",
                release_at=claim.release_at,
                public_available_at=claim.public_available_at,
                fetched_at=claim.fetched_at,
                available_at=after + timedelta(seconds=1),
                certification_status=(
                    "awaiting_source_certification"
                    if fault in ("certification", "nondisclosed")
                    else "certified"
                ),
                quality_status="invalid" if fault in ("quality", "nondisclosed") else "validated",
                acquisition_id=receipt.acquisition_id,
            )
        )
        reviewed_ids = {claim.claim_id, reviewed.claim_id}
        if mode is AsOfMode.SYSTEM:
            cutoff = after + timedelta(seconds=1)
        (reviewed_point,) = [
            point
            for point in repository.metric_series(
                metric, mode=mode, as_of=cutoff, definition_version=version
            )
            if point.dimensions == dimensions and point.period_end == latest.period_end
        ]
        assert reviewed_point.selected_claim_id == reviewed.claim_id
        assert reviewed_point.selected_value == (None if nondisclosed else latest.selected_value)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        as_of_mode=mode,
        target_business_date="2026-08-28",
        model_manifest=manifest,
    )
    # With the actual releases, Q4 differences 399338/386843 disagree
    # with the same announcements' quarterly values 373726/387911.
    # Source-field certification does not certify this cross-release difference.
    credit = context.macro["credit"]
    assert isinstance(credit, dict)
    formula = credit["formula"]
    assert isinstance(formula, dict)
    if scenario in ("coherent", "coherent_decimal", "unused_old_raw", "older_social_window"):
        assert formula["status"] == "available", formula
        impulse = next(row for row in credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE")
        # 24 real SF monthly differences total 338600/373800, with four
        # independently specified synthetic GDP quarters of 350000 or 350000.1.
        annual_gdp = 1400000.4 if scenario == "coherent_decimal" else 1400000
        assert impulse["value"] == pytest.approx(
            100 * (338600 - 373800) / annual_gdp, rel=1e-12, abs=1e-12
        )
        assert set(impulse["input_observation_version_ids"]) == parent_ids
        trace = repository.derived_trace(impulse["derived_observation_id"], mode=mode, as_of=cutoff)
        assert set(trace.input_observation_version_ids) == parent_ids
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert parent_ids <= set(model_inputs)
        if unused_gdp_id is not None:
            assert unused_gdp_id not in model_inputs
        assert ModelRepository(paths.database).get(model_id) == model_before
        return
    expected_status = (
        "incomplete_source_artifacts"
        if damaged_parent_id is not None
        else "incomparable_gdp_vintages"
    )
    if scenario == "latest_nonpositive_gdp" or reviewed_ids or missing_social_baseline:
        expected_status = "missing_certified_inputs"
    assert formula["status"] == expected_status, formula
    assert not any(
        row["metric_id"] == "CN_CREDIT_IMPULSE" and row["value"] is not None
        for row in credit["evidence"]
    )
    if damaged_parent_id is not None:
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert damaged_parent_id not in model_inputs
    if reviewed_ids:
        model_inputs = context.macro["model_input_observation_version_ids"]
        assert isinstance(model_inputs, list)
        assert reviewed_ids.isdisjoint(model_inputs)
    assert ModelRepository(paths.database).get(model_id) == model_before


def prepare_credit_component_pair(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    *,
    missing_candidate_social_baseline: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str | None]]]:
    repository = EvidenceRepository(paths.database)
    root = Path(__file__).parents[2]
    fixture = json.loads(
        (
            root / ".scratch/pring-data-acquisition-repair/credit-window-inputs-186/manifest.json"
        ).read_text()
    )
    fixture_time = datetime(2026, 8, 29, tzinfo=UTC)
    cutoff = datetime(2026, 8, 28, 15, 59, 59, 999999, tzinfo=UTC)
    manifests = {}
    parent_ids = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_gdp_manifest(paths, capsys, side=side)
        # The full admitted model stays immutable. This public component replay
        # exercises only credit inputs, not real certification or a 120-day gate.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        version = manifest["metric_catalog_version"]
        for parent in fixture["parents"]:
            if (
                missing_candidate_social_baseline
                and side == "candidate"
                and parent["family"] == "pbc_social_financing"
                and parent["period"] == "2026-06"
            ):
                continue
            raw = (root / parent["raw_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == parent["raw_sha256"]
            url = parent["source_url"]
            if parent["family"] == "nbs_gdp":
                raw, url = synthetic_coherent_gdp_release(parent["period"])
            if side == "candidate":
                raw += b"<!-- synthetic candidate component retrieval -->"
            imported = ingest_official_context_document(
                paths,
                raw,
                family=parent["family"],
                source_url=url,
                expected_period=parent["period"],
                fetched_at=fixture_time,
                clock=lambda: fixture_time,
                definition_version=version,
            )
            assert imported.claim_ids
        if missing_candidate_social_baseline:
            # Both catalogs have an older complete 24-month flow window. Only
            # the candidate lacks the baseline needed for its latest July flow.
            for month in (5, 6):
                old_raw, old_url = synthetic_prior_social_financing_release(month)
                older = ingest_official_context_document(
                    paths,
                    old_raw,
                    family="pbc_social_financing",
                    source_url=old_url,
                    expected_period=f"2024-{month:02d}",
                    fetched_at=fixture_time,
                    clock=lambda: fixture_time,
                    definition_version=version,
                )
                assert older.claim_ids
        # Replay also checks the complete latest SF publication: stock and flow
        # are separate official documents. Neither substitutes for the other.
        stock_hash = "933f3546fc3f8232014dc9e2cab854a331ff5da5a9509d3063ada2d3678dfcef"
        stock = (
            root / ".scratch/pring-data-acquisition-repair/evidence-13" / stock_hash
        ).read_bytes()
        assert hashlib.sha256(stock).hexdigest() == stock_hash
        imported_stock = ingest_official_context_document(
            paths,
            stock,
            family="pbc_social_financing",
            source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html",
            expected_period="2026-07",
            fetched_at=fixture_time,
            clock=lambda: fixture_time,
            definition_version=version,
        )
        assert imported_stock.claim_ids
        parent_ids[side] = {
            point.selected_claim_id
            for metric, dimensions in (
                ("CN_SF_TOTAL", {"measure": "ytd_increment"}),
                ("CN_GDP", {"aggregate": "total", "measure": "nominal_ytd_level"}),
            )
            for point in repository.metric_series(
                metric, mode=AsOfMode.PUBLIC, as_of=cutoff, definition_version=version
            )
            if point.dimensions == dimensions
        }
        expected_count = 36 - int(side == "candidate") if missing_candidate_social_baseline else 34
        assert len(parent_ids[side]) == expected_count and None not in parent_ids[side]
    return manifests, parent_ids


def test_credit_public_component_replay_requires_historical_window_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, parent_ids = prepare_credit_component_pair(paths, capsys)
    stored_models = {
        side: ModelRepository(paths.database).get(manifest["model_version_id"])
        for side, manifest in manifests.items()
    }
    repository = EvidenceRepository(paths.database)
    cutoff = datetime(2026, 8, 28, 15, 59, 59, 999999, tzinfo=UTC)
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
        macro = before.output_document["days"][0][side]["macro"]
        assert macro["credit"]["formula"]["status"] == "available"
        impulse = next(
            row for row in macro["credit"]["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
        )
        assert impulse["value"] == pytest.approx(-2.5142857142857142)
        assert set(impulse["input_observation_version_ids"]) == parent_ids[side]
        assert parent_ids[side] <= set(macro["model_input_observation_version_ids"])

    (historical,) = [
        point
        for point in repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
            definition_version=manifests["candidate"]["metric_catalog_version"],
        )
        if point.period_end == "2024-09-30"
        and point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
    ]
    assert historical.selected_claim_id in parent_ids["candidate"]
    assert historical.selected_claim_id is not None
    ((receipt, _),) = repository.source_claim_originals(historical.selected_claim_id)
    assert receipt.raw_hash is not None
    artifact = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == receipt.raw_hash
    artifact.write_bytes(b"damaged synthetic historical GDP release")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert after.gaps == ("candidate_context_formula_output_missing:credit_impulse",)
    assert after.evaluated_cutoffs == 1
    assert after.output_document is not None
    candidate = after.output_document["days"][0]["candidate"]["macro"]
    assert candidate["credit"]["formula"]["status"] == "incomplete_source_artifacts"
    assert historical.selected_claim_id not in candidate["model_input_observation_version_ids"]
    assert not any(
        row["metric_id"] == "CN_CREDIT_IMPULSE" and row["value"] is not None
        for row in candidate["credit"]["evidence"]
    )
    comparison = after.output_document["days"][0]["comparison"]["macro"]
    assert comparison == before.output_document["days"][0]["comparison"]["macro"]
    for side in ("comparison", "candidate"):
        assert (
            ModelRepository(paths.database).get(manifests[side]["model_version_id"])
            == stored_models[side]
        )


@pytest.mark.parametrize("known_public", [True, False], ids=["known-public", "unknown-public"])
def test_credit_public_component_replay_preserves_revision_cutoffs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], known_public: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, parent_ids = prepare_credit_component_pair(paths, capsys)
    stored_models = {
        side: ModelRepository(paths.database).get(manifest["model_version_id"])
        for side, manifest in manifests.items()
    }
    repository = EvidenceRepository(paths.database)
    version = manifests["candidate"]["metric_catalog_version"]
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
        credit = before.output_document["days"][0][side]["macro"]["credit"]
        assert credit["formula"]["status"] == "available"
        impulse = next(row for row in credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE")
        assert impulse["value"] == pytest.approx(-2.5142857142857142)
        assert set(impulse["input_observation_version_ids"]) == parent_ids[side]
    (old_ytd,) = [
        point
        for point in repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 15, 59, tzinfo=UTC),
            definition_version=version,
        )
        if point.period_end == "2026-06-30"
        and point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
    ]
    # Synthetic numerical revision: current four-quarter GDP is 1410000,
    # previous is 1400000; independent SF totals stay 338600 and 373800.
    raw, url = synthetic_coherent_gdp_release("2026-Q2")
    for original, revised in (
        (
            b"<td>GDP</td><td>350000</td><td>700000</td>",
            b"<td>GDP</td><td>360000</td><td>710000</td>",
        ),
        (b"<td>10000</td><td>20000</td>", b"<td>20000</td><td>30000</td>"),
    ):
        assert raw.count(original) == 1
        raw = raw.replace(original, revised, 1)
    if known_public:
        assert raw.count(b"2026-07-16 09:30") == 1
        raw = raw.replace(b"2026-07-16 09:30", b"2026-08-30 09:30", 1)
    revised_at = datetime(2026, 8, 31, tzinfo=UTC)
    revision = ingest_official_context_document(
        paths,
        raw,
        family="nbs_gdp",
        source_url=url,
        expected_period="2026-Q2",
        fetched_at=revised_at,
        clock=lambda: revised_at,
        definition_version=version,
    )
    (new_ytd,) = [
        claim
        for claim in repository.source_claim_vintages("CN_GDP", definition_version=version)
        if claim.claim_id in revision.claim_ids
        and claim.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
    ]
    assert new_ytd.public_available_at == (
        datetime(2026, 8, 30, 1, 30, tzinfo=UTC) if known_public else None
    )
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-31",
    )
    assert not after.gaps, after.gaps
    assert after.evaluated_cutoffs == 2
    assert after.output_document is not None
    assert [day["business_date"] for day in after.output_document["days"]] == [
        "2026-08-28",
        "2026-08-31",
    ]
    historical, current = after.output_document["days"]
    for side in ("comparison", "candidate"):
        assert historical[side]["macro"] == before.output_document["days"][0][side]["macro"]
        macro = current[side]["macro"]
        adopts_revision = side == "candidate" and known_public
        expected_ids = (
            (parent_ids[side] - {old_ytd.selected_claim_id}) | {new_ytd.claim_id}
            if adopts_revision
            else parent_ids[side]
        )
        assert macro["credit"]["formula"]["status"] == "available"
        impulse = next(
            row for row in macro["credit"]["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
        )
        assert impulse["value"] == pytest.approx(
            -2.6858156028368803 if adopts_revision else -2.5142857142857142
        )
        assert set(impulse["input_observation_version_ids"]) == expected_ids
        actual_inputs = set(macro["model_input_observation_version_ids"])
        assert expected_ids <= actual_inputs
        if adopts_revision:
            assert old_ytd.selected_claim_id not in actual_inputs
        else:
            assert set(revision.claim_ids).isdisjoint(actual_inputs)
        assert (
            ModelRepository(paths.database).get(manifests[side]["model_version_id"])
            == stored_models[side]
        )


def test_credit_public_component_replay_requires_latest_month_difference_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, parent_ids = prepare_credit_component_pair(
        paths, capsys, missing_candidate_social_baseline=True
    )
    stored_models = {
        side: ModelRepository(paths.database).get(manifest["model_version_id"])
        for side, manifest in manifests.items()
    }
    repository = EvidenceRepository(paths.database)
    cutoff = datetime(2026, 8, 28, 15, 59, 59, 999999, tzinfo=UTC)
    old_ids = {}
    for side in ("comparison", "candidate"):
        social = [
            point
            for point in repository.metric_series(
                "CN_SF_TOTAL",
                mode=AsOfMode.PUBLIC,
                as_of=cutoff,
                definition_version=manifests[side]["metric_catalog_version"],
            )
            if point.dimensions == {"measure": "ytd_increment"}
        ]
        periods = {point.period_end for point in social}
        assert "2026-07-31" in periods
        assert ("2026-06-30" in periods) is (side == "comparison")
        old_ids[side] = {
            point.selected_claim_id for point in social if point.period_end < "2024-07-31"
        }
        assert len(old_ids[side]) == 2
    incomplete = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert incomplete.gaps == ("candidate_context_formula_output_missing:credit_impulse",)
    assert incomplete.evaluated_cutoffs == 1
    assert incomplete.output_document is not None
    candidate = incomplete.output_document["days"][0]["candidate"]["macro"]
    assert candidate["credit"]["formula"]["status"] == "missing_certified_inputs"
    assert old_ids["candidate"].isdisjoint(candidate["model_input_observation_version_ids"])
    assert not any(
        row["metric_id"] == "CN_CREDIT_IMPULSE" and row["value"] is not None
        for row in candidate["credit"]["evidence"]
    )
    comparison = incomplete.output_document["days"][0]["comparison"]["macro"]
    assert comparison["credit"]["formula"]["status"] == "available"
    control = next(
        row for row in comparison["credit"]["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )
    assert control["value"] == pytest.approx(-2.5142857142857142)
    assert (
        set(control["input_observation_version_ids"])
        == parent_ids["comparison"] - old_ids["comparison"]
    )

    root = Path(__file__).parents[2]
    fixture = json.loads(
        (
            root / ".scratch/pring-data-acquisition-repair/credit-window-inputs-186/manifest.json"
        ).read_text()
    )
    baseline = next(
        parent
        for parent in fixture["parents"]
        if parent["family"] == "pbc_social_financing" and parent["period"] == "2026-06"
    )
    raw = (root / baseline["raw_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == baseline["raw_sha256"]
    fetched_at = datetime(2026, 8, 29, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw + b"<!-- synthetic candidate component retrieval -->",
        family="pbc_social_financing",
        source_url=baseline["source_url"],
        expected_period="2026-06",
        fetched_at=fetched_at,
        clock=lambda: fetched_at,
        definition_version=manifests["candidate"]["metric_catalog_version"],
    )
    (new_baseline,) = [
        claim
        for claim in repository.source_claim_vintages(
            "CN_SF_TOTAL", definition_version=manifests["candidate"]["metric_catalog_version"]
        )
        if claim.claim_id in imported.claim_ids and claim.dimensions == {"measure": "ytd_increment"}
    ]
    complete = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not complete.gaps, complete.gaps
    assert complete.evaluated_cutoffs == 1
    assert complete.output_document is not None
    for side in ("comparison", "candidate"):
        macro = complete.output_document["days"][0][side]["macro"]
        assert macro["credit"]["formula"]["status"] == "available"
        impulse = next(
            row for row in macro["credit"]["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
        )
        expected_ids = parent_ids[side] - old_ids[side]
        if side == "candidate":
            expected_ids |= {new_baseline.claim_id}
        assert len(expected_ids) == 34
        assert impulse["value"] == pytest.approx(-2.5142857142857142)
        assert set(impulse["input_observation_version_ids"]) == expected_ids
        assert expected_ids <= set(macro["model_input_observation_version_ids"])
        assert old_ids[side].isdisjoint(macro["model_input_observation_version_ids"])
        assert (
            ModelRepository(paths.database).get(manifests[side]["model_version_id"])
            == stored_models[side]
        )
    assert complete.output_document["days"][0]["comparison"]["macro"] == comparison


@pytest.mark.parametrize("mode", [AsOfMode.PUBLIC, AsOfMode.SYSTEM])
@pytest.mark.parametrize("known_public", [True, False], ids=["known-public", "unknown-public"])
def test_registered_credit_revision_preserves_as_of_and_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: AsOfMode, known_public: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_gdp_manifest(paths, capsys)
    model_id = manifest["model_version_id"]
    version = manifest["metric_catalog_version"]
    model_before = ModelRepository(paths.database).get(model_id)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    repository = EvidenceRepository(paths.database)
    root = Path(__file__).parents[2]
    fixture = json.loads(
        (
            root / ".scratch/pring-data-acquisition-repair/credit-window-inputs-186/manifest.json"
        ).read_text()
    )
    fixture_time = datetime(2026, 8, 29, tzinfo=UTC)
    for parent in fixture["parents"]:
        raw = (root / parent["raw_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == parent["raw_sha256"]
        url = parent["source_url"]
        if parent["family"] == "nbs_gdp":
            raw, url = synthetic_coherent_gdp_release(parent["period"])
        imported = ingest_official_context_document(
            paths,
            raw,
            family=parent["family"],
            source_url=url,
            expected_period=parent["period"],
            fetched_at=fixture_time,
            clock=lambda: fixture_time,
            definition_version=version,
        )
        assert imported.claim_ids
    assert len(acquisitions.history()) == 34
    cutoff = datetime(2026, 8, 28, 15, 59, tzinfo=UTC) if mode is AsOfMode.PUBLIC else fixture_time
    parent_ids = {
        point.selected_claim_id
        for metric, dimensions in (
            ("CN_SF_TOTAL", {"measure": "ytd_increment"}),
            ("CN_GDP", {"aggregate": "total", "measure": "nominal_ytd_level"}),
        )
        for point in repository.metric_series(
            metric, mode=mode, as_of=cutoff, definition_version=version
        )
        if point.dimensions == dimensions
    }
    assert len(parent_ids) == 34 and None not in parent_ids
    context = build_context_projection(
        repository,
        as_of=cutoff,
        as_of_mode=mode,
        target_business_date="2026-08-28",
        model_manifest=manifest,
    )
    credit = context.macro["credit"]
    assert isinstance(credit, dict)
    assert credit["formula"]["status"] == "available"
    impulse = next(row for row in credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE")
    assert impulse["value"] == pytest.approx(-2.5142857142857142)
    assert set(impulse["input_observation_version_ids"]) == parent_ids
    trace = repository.derived_trace(impulse["derived_observation_id"], mode=mode, as_of=cutoff)
    # A synthetic numerical revision, imported through the public parser.
    # It certifies neither an actual GDP revision nor historical PUBLIC coverage.
    raw, source_url = synthetic_coherent_gdp_release("2026-Q2")
    replacements = (
        (
            b"<td>GDP</td><td>350000</td><td>700000</td>",
            b"<td>GDP</td><td>360000</td><td>710000</td>",
        ),
        (b"<td>10000</td><td>20000</td>", b"<td>20000</td><td>30000</td>"),
    )
    for original, revised in replacements:
        assert raw.count(original) == 1
        raw = raw.replace(original, revised, 1)
    if known_public:
        assert raw.count(b"2026-07-16 09:30") == 1
        raw = raw.replace(b"2026-07-16 09:30", b"2026-08-30 09:30", 1)
    received_at = datetime(2026, 8, 31, tzinfo=UTC)
    tick = received_at - timedelta(seconds=2)

    def revision_clock() -> datetime:
        nonlocal tick
        tick += timedelta(seconds=1)
        return tick

    revision = ingest_official_context_document(
        paths,
        raw,
        family="nbs_gdp",
        source_url=source_url,
        expected_period="2026-Q2",
        fetched_at=received_at,
        clock=revision_clock,
        definition_version=version,
    )
    assert revision.claim_ids
    revision_receipt = acquisitions.history()[-1]
    assert revision_receipt.received_at is not None
    assert revision_receipt.validated_at is not None
    assert revision_receipt.received_at <= revision_receipt.validated_at
    public_at = datetime(2026, 8, 30, 1, 30, tzinfo=UTC) if known_public else None
    revision_claims = [
        claim
        for point in repository.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=tick, definition_version=version
        )
        for claim in point.claims
        if claim.claim_id in revision.claim_ids
    ]
    (available_at,) = {claim.available_at for claim in revision_claims}
    assert available_at >= revision_receipt.validated_at
    assert {claim.public_available_at for claim in revision_claims} == {public_at}
    visible_at = public_at if mode is AsOfMode.PUBLIC and public_at is not None else available_at
    old_latest = next(
        point
        for point in repository.metric_series(
            "CN_GDP", mode=mode, as_of=cutoff, definition_version=version
        )
        if point.period_end == "2026-06-30"
        and point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
    )
    for index, (instant, expected_gdp) in enumerate(
        (
            (visible_at - timedelta(microseconds=1), 700000),
            (visible_at, 710000 if known_public or mode is AsOfMode.SYSTEM else 700000),
        )
    ):
        latest = next(
            point
            for point in repository.metric_series(
                "CN_GDP", mode=mode, as_of=instant, definition_version=version
            )
            if point.period_end == "2026-06-30"
            and point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
        )
        assert latest.selected_value == expected_gdp
        selected_revision = expected_gdp == 710000
        assert (latest.selected_claim_id in revision.claim_ids) is selected_revision
        # Explicit target-day consumers additionally require known PUBLIC time.
        adopted_revision = selected_revision and known_public
        expected_parents = (
            (parent_ids - {old_latest.selected_claim_id}) | {latest.selected_claim_id}
            if adopted_revision
            else parent_ids
        )
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-31",
            client_request_id=f"credit-revision-{mode.value}-{index}",
            model_version_id=model_id,
            system_as_of=instant,
            release_event_id=revision.release_event_id,
            metric_ids=("CN_GDP",),
            period="2026-Q2",
        )
        selection = select_retrieval_input(paths, run, mode=mode)
        assert selection.complete
        expected_selected_id = (
            latest.selected_claim_id if adopted_revision else old_latest.selected_claim_id
        )
        assert expected_selected_id in selection.selected_claim_ids
        if not adopted_revision:
            assert set(revision.claim_ids).isdisjoint(selection.selected_claim_ids)
        for persist in (True, False):
            revised_context = build_context_projection(
                repository,
                as_of=instant,
                as_of_mode=mode,
                target_business_date="2026-08-31",
                model_manifest=manifest,
                persist_derived=persist,
            )
            revised_credit = revised_context.macro["credit"]
            assert isinstance(revised_credit, dict)
            assert revised_credit["formula"]["status"] == "available"
            revised_impulse = next(
                row for row in revised_credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
            )
            # Current GDP is 1,410,000, previous GDP remains 1,400,000;
            # current/previous SF totals remain 338,600 and 373,800.
            expected_value = -2.6858156028368803 if adopted_revision else -2.5142857142857142
            assert revised_impulse["value"] == pytest.approx(expected_value)
            assert set(revised_impulse["input_observation_version_ids"]) == expected_parents
            actual_inputs = revised_context.macro["model_input_observation_version_ids"]
            assert isinstance(actual_inputs, list)
            assert expected_parents <= set(actual_inputs)
            if adopted_revision:
                assert old_latest.selected_claim_id not in actual_inputs
            else:
                assert set(revision.claim_ids).isdisjoint(actual_inputs)
            if persist:
                revised_trace = repository.derived_trace(
                    revised_impulse["derived_observation_id"], mode=mode, as_of=instant
                )
                assert revised_trace.value == pytest.approx(expected_value)
                assert set(revised_trace.input_observation_version_ids) == expected_parents
                assert revised_trace.as_of_cutoff == instant
                if adopted_revision:
                    assert revised_trace.derived_observation_id != trace.derived_observation_id
        assert (
            repository.derived_trace(impulse["derived_observation_id"], mode=mode, as_of=instant)
            == trace
        )
    # Advancing SYSTEM/as-of must not move an explicitly historical target.
    historical = build_context_projection(
        repository,
        as_of=available_at,
        as_of_mode=mode,
        target_business_date="2026-08-28",
        model_manifest=manifest,
    )
    historical_credit = historical.macro["credit"]
    assert isinstance(historical_credit, dict)
    historical_impulse = next(
        row for row in historical_credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )
    assert historical_impulse["value"] == pytest.approx(-2.5142857142857142)
    assert set(historical_impulse["input_observation_version_ids"]) == parent_ids
    if not known_public:
        # A SYSTEM query without a historical target can use the verified revision;
        # PUBLIC still cannot. Neither query changes the saved old result.
        unbounded = build_context_projection(
            repository, as_of=available_at, as_of_mode=mode, model_manifest=manifest
        )
        unbounded_credit = unbounded.macro["credit"]
        assert isinstance(unbounded_credit, dict)
        assert unbounded_credit["formula"]["status"] == "available"
        unbounded_impulse = next(
            row for row in unbounded_credit["evidence"] if row["metric_id"] == "CN_CREDIT_IMPULSE"
        )
        uses_revision = mode is AsOfMode.SYSTEM
        expected_value = -2.6858156028368803 if uses_revision else -2.5142857142857142
        expected_parents = (
            (parent_ids - {old_latest.selected_claim_id}) | {latest.selected_claim_id}
            if uses_revision
            else parent_ids
        )
        assert unbounded_impulse["value"] == pytest.approx(expected_value)
        assert set(unbounded_impulse["input_observation_version_ids"]) == expected_parents
        actual_inputs = unbounded.macro["model_input_observation_version_ids"]
        assert isinstance(actual_inputs, list)
        assert expected_parents <= set(actual_inputs)
        if uses_revision:
            assert old_latest.selected_claim_id not in actual_inputs
        else:
            assert set(revision.claim_ids).isdisjoint(actual_inputs)
        unbounded_trace = repository.derived_trace(
            unbounded_impulse["derived_observation_id"], mode=mode, as_of=available_at
        )
        assert unbounded_trace.value == pytest.approx(expected_value)
        assert set(unbounded_trace.input_observation_version_ids) == expected_parents
        if uses_revision:
            assert unbounded_trace.derived_observation_id != trace.derived_observation_id
        assert (
            repository.derived_trace(
                impulse["derived_observation_id"], mode=mode, as_of=available_at
            )
            == trace
        )
    assert ModelRepository(paths.database).get(model_id) == model_before


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


def prepared_capacity_mapping_request(
    paths: RuntimePaths, *, side: str = ""
) -> tuple[dict[str, Any], str, bytes, str, str]:
    # Public candidate admission and document ingestion with a synthetic review.
    # This does not certify the real source, historical PUBLIC time, or a full replay.
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    if side:
        manifest["metric_catalog_version"] += "-" + side
        for item in manifest["metric_definitions"]:
            item["definition_version"] = manifest["metric_catalog_version"]
            if side == "candidate" and item["metric_id"] == "CN_CAPACITY_UTILIZATION":
                item["source_candidates"] = [
                    *item["source_candidates"],
                    "https://www.stats.gov.cn/synthetic-q1-review",
                ]
    version = manifest["metric_catalog_version"]
    definition = next(
        item
        for item in manifest["metric_definitions"]
        if item["metric_id"] == "CN_CAPACITY_UTILIZATION"
    )
    digest = "0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a"
    evidence_root = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair"
    raw = (evidence_root / "evidence-official-consumer-edge" / digest).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    url = "https://www.stats.gov.cn/sj/zxfb/202604/t20260416_1963322.html"
    store_artifact(paths.database, paths.artifacts, raw, "text/html", url)
    basis_path = evidence_root / "capacity-q1-source-mapping-decision.md"
    basis = store_artifact(
        paths.database,
        paths.artifacts,
        basis_path.read_bytes(),
        "text/markdown",
        "synthetic:q1-mapping-semantic-basis",
    )
    mapping_hash = save(
        paths,
        {
            "schema_version": "source-field-mapping-v0001",
            "rule_version": "capacity_q1_same_interval_alias_v0001",
            "metric_id": "CN_CAPACITY_UTILIZATION",
            "definition_version": version,
            "definition_hash": hashlib.sha256(encode(definition)).hexdigest(),
            "source_document": {
                "artifact_hash": digest,
                "source_reference": url,
                "bytes": 128195,
            },
            "parser": {
                "version": "official-context-parser-v0004",
                "family": "nbs_capacity_utilization",
                "period": "2026-Q1",
            },
            "source": {
                "source_field": "industrial_capacity_utilization_pct",
                "dimensions": {"industry": "all_industry", "measure": "quarter_rate"},
                "period_kind": "quarter",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "unit": "percent",
                "value": 73.6,
            },
            "target": {
                "source_field": "industrial_capacity_utilization_ytd_pct",
                "dimensions": {"industry": "all_industry", "measure": "ytd_rate"},
                "period_kind": "year_to_quarter",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "unit": "percent",
                "value": 73.6,
            },
            "basis": {
                "artifact_hash": basis.content_hash,
                "source_reference": "synthetic:q1-mapping-semantic-basis",
            },
        },
    )
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    for criterion in ("semantics", "fields"):
        review["assessments"][criterion]["evidence"].append(
            {
                "artifact_hash": mapping_hash,
                "source_reference": "synthetic:admission",
            }
        )
    package["review_hash"] = save(paths, review)
    package["definition_bindings"] = {
        item["metric_id"]: hashlib.sha256(encode(item)).hexdigest()
        for item in manifest["metric_definitions"]
        if item["metric_id"] in package["definition_bindings"]
    }
    bind_synthetic_review(paths, request, package)
    return request, mapping_hash, raw, digest, url


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        (("target", "value"), 73.7),
        (("source", "value"), 73.7),
        (("target", "value"), True),
        (("target", "unit"), "percentage_points"),
        (("target", "source_field"), "industrial_capacity_utilization_pct"),
        (("source", "source_field"), "industrial_capacity_utilization_yoy_change_pp"),
        (("target", "period_start"), "2026-02-01"),
        (("target", "dimensions", "measure"), "quarter_rate"),
        (("definition_hash",), "0" * 64),
        (("definition_version",), "unreviewed-catalog"),
        (("schema_version",), "source-field-mapping-v0002"),
        (("rule_version",), "unreviewed-mapping-rule"),
        (("parser", "version"), "official-context-parser-v0003"),
        (("parser", "family"), "nbs_gdp"),
        (("parser", "period"), "2026-Q2"),
        (("source_document", "bytes"), 128196),
        (("source_document", "artifact_hash"), "0" * 64),
        (("source_document", "source_reference"), "https://www.stats.gov.cn/wrong"),
        (("basis", "artifact_hash"), "0" * 64),
        (("review", "fields"), None),
    ],
)
def test_capacity_mapping_admission_rejects_a_reviewed_but_wrong_mapping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: tuple[str, ...],
    wrong_value: Any,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, _, _, _ = prepared_capacity_mapping_request(paths)
    submit(paths, save(paths, request))
    admitted = json.loads(capsys.readouterr().out)["model_version_id"]
    assert (
        ModelRepository(paths.database).manifest(admitted)["metric_catalog_version"]
        == (request["manifest"]["metric_catalog_version"])
    )
    mapping = json.loads((paths.artifacts / mapping_hash[:2] / mapping_hash).read_bytes())
    if field[0] != "review":
        parent = mapping
        for key in field[:-1]:
            parent = parent[key]
        parent[field[-1]] = wrong_value
    # Recompute all hashes: rejection must depend on semantics, not damaged JSON.
    wrong_mapping_hash = save(paths, mapping)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    for criterion in ("semantics", "fields"):
        for reference in review["assessments"][criterion]["evidence"]:
            if reference["artifact_hash"] == mapping_hash:
                reference["artifact_hash"] = wrong_mapping_hash
    if field == ("review", "fields"):
        review["assessments"]["fields"]["evidence"] = [
            reference
            for reference in review["assessments"]["fields"]["evidence"]
            if reference["artifact_hash"] != wrong_mapping_hash
        ]
    package["review_hash"] = save(paths, review)
    request["package_hashes"] = [save(paths, package)]
    versions_before = ModelRepository(paths.database).list_versions()
    with pytest.raises(SystemExit) as exited:
        submit(paths, save(paths, request))
    assert exited.value.code == 2
    assert ModelRepository(paths.database).list_versions() == versions_before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: certification_source_mapping_invalid\n"


@pytest.mark.parametrize(
    ("consumer", "damaged_artifact"),
    [("none", "none")]
    + [
        (consumer, artifact)
        for consumer in ("selection", "context")
        for artifact in ("mapping", "raw", "normalized")
    ],
)
def test_registered_capacity_q1_consumes_an_explicitly_reviewed_same_interval_mapping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    consumer: str,
    damaged_artifact: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, raw, digest, url = prepared_capacity_mapping_request(paths)
    version = request["manifest"]["metric_catalog_version"]
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    assert ModelRepository(paths.database).manifest(model_id)["metric_catalog_version"] == version

    start = datetime(2026, 8, 29, tzinfo=UTC)
    tick = start

    def clock() -> datetime:
        nonlocal tick
        tick += timedelta(milliseconds=1)
        return tick

    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_capacity_utilization",
        source_url=url,
        expected_period="2026-Q1",
        fetched_at=start,
        clock=clock,
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.raw_hash == digest
    assert receipt.parser_version == "official-context-parser-v0004"
    assert receipt.received_at is not None and receipt.validated_at is not None
    assert start < receipt.started_at <= receipt.received_at <= receipt.validated_at <= tick
    system = repository.metric_series(
        "CN_CAPACITY_UTILIZATION",
        mode=AsOfMode.SYSTEM,
        as_of=tick,
        definition_version=version,
    )
    assert len(system) == 3
    available_times = {claim.available_at for point in system for claim in point.claims}
    assert len(available_times) == 1
    available_at = available_times.pop()
    assert available_at >= receipt.validated_at
    # Independent literals from the industrial row: two identities share one 73.6 cell.
    expected = {
        "quarter_rate": (73.6, "percent", "quarter"),
        "yoy_change": (-0.5, "percentage_points", "quarter"),
        "ytd_rate": (73.6, "percent", "year_to_quarter"),
    }
    public_at = datetime(2026, 4, 16, 2, tzinfo=UTC)
    for mode, cutoff in ((AsOfMode.SYSTEM, available_at), (AsOfMode.PUBLIC, public_at)):
        before = repository.metric_series(
            "CN_CAPACITY_UTILIZATION",
            mode=mode,
            as_of=cutoff - timedelta(microseconds=1),
            definition_version=version,
        )
        assert all(
            not point.claims and point.selected_claim_id is None and point.selected_value is None
            for point in before
        )
        points = repository.metric_series(
            "CN_CAPACITY_UTILIZATION",
            mode=mode,
            as_of=cutoff,
            definition_version=version,
        )
        assert len(points) == 3
        assert {point.selected_claim_id for point in points} == set(imported.claim_ids)
        actual = {}
        for point in points:
            (claim,) = point.claims
            trace = repository.trace(point.observation_id, mode=mode, as_of=cutoff)
            assert trace.definition_version == version
            assert point.period_start == "2026-01-01" and point.period_end == "2026-03-31"
            assert point.dimensions["industry"] == "all_industry"
            assert claim.source_reference == f"{url}#sha256={digest}"
            assert claim.release_at == claim.public_available_at == public_at
            assert claim.fetched_at == receipt.received_at
            assert tuple(item.acquisition_id for item in trace.acquisitions) == (
                receipt.acquisition_id,
            )
            actual[point.dimensions["measure"]] = (
                point.selected_value,
                claim.unit,
                trace.period_kind,
            )
        assert actual == expected

    # A reviewed value does not authorize a caller to invent an earlier PUBLIC time.
    with pytest.raises(ValueError, match="registered_capacity_q1_mapping_unresolved"):
        repository.append_source_claims(
            (
                SourceClaimInput(
                    metric_id="CN_CAPACITY_UTILIZATION",
                    definition_version=version,
                    period_kind="year_to_quarter",
                    period_start="2026-01-01",
                    period_end="2026-03-31",
                    dimensions={"industry": "all_industry", "measure": "ytd_rate"},
                    value=73.6,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="国家统计局",
                    source_reference=f"{url}#sha256={digest}",
                    release_event_id="synthetic:q1-invented-earlier-public-time",
                    release_at=public_at - timedelta(days=1),
                    public_available_at=public_at - timedelta(days=1),
                    fetched_at=receipt.received_at,
                    available_at=tick,
                    certification_status="certified",
                    quality_status="validated",
                    acquisition_id=receipt.acquisition_id,
                ),
            )
        )

    if consumer in {"selection", "context"}:
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="synthetic:q1-mapping-selection",
            model_version_id=model_id,
            system_as_of=tick,
            release_event_id=imported.release_event_id,
            metric_ids=("CN_CAPACITY_UTILIZATION",),
            period="2026-Q1",
        )
        selected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert selected.complete
        assert set(selected.selected_claim_ids) == set(imported.claim_ids)
        ytd_claim_id = next(
            point.selected_claim_id for point in system if point.dimensions["measure"] == "ytd_rate"
        )
        manifest = ModelRepository(paths.database).manifest(model_id)
        if consumer == "context":
            before_context = build_context_projection(
                repository, as_of=tick, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
            )
            before_inputs = before_context.macro["model_input_observation_version_ids"]
            assert isinstance(before_inputs, list)
            assert set(imported.claim_ids) <= set(before_inputs)
        damaged_hash = {
            "mapping": mapping_hash,
            "raw": digest,
            "normalized": receipt.normalized_hash,
        }[damaged_artifact]
        assert damaged_hash is not None
        (paths.artifacts / damaged_hash[:2] / damaged_hash).write_bytes(b"damaged artifact")
        after = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert not after.complete
        assert ytd_claim_id not in after.selected_claim_ids
        assert any('"measure": "ytd_rate"' in item for item in after.missing_members)
        if damaged_artifact != "mapping":
            assert not set(imported.claim_ids) & set(after.selected_claim_ids)
        if consumer == "context":
            after_context = build_context_projection(
                EvidenceRepository(paths.database),
                as_of=tick,
                model_manifest=manifest,
                as_of_mode=AsOfMode.PUBLIC,
            )
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert ytd_claim_id not in after_inputs
            if damaged_artifact != "mapping":
                assert not set(imported.claim_ids) & set(after_inputs)
            assert set(imported.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("artifact", ["mapping", "raw", "normalized"])
@pytest.mark.parametrize("failure", ["damaged", "missing"])
def test_registered_capacity_q1_public_replay_rechecks_each_catalog_mapping(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    artifact: str,
    failure: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    mappings = {}
    claims = {}
    ytd_ids = {}
    acquired_at = datetime(2026, 8, 29, tzinfo=UTC)
    for side in ("comparison", "candidate"):
        request, mapping, raw, _, url = prepared_capacity_mapping_request(paths, side=side)
        submit(paths, save(paths, request))
        model_id = json.loads(capsys.readouterr().out)["model_version_id"]
        manifest = ModelRepository(paths.database).manifest(model_id)
        version = manifest["metric_catalog_version"]
        imported = ingest_official_context_document(
            paths,
            raw,
            family="nbs_capacity_utilization",
            source_url=url,
            expected_period="2026-Q1",
            fetched_at=acquired_at,
            clock=lambda: acquired_at,
            definition_version=version,
        )
        # This is a one-day component replay, not the full model's 120-day acceptance.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        mappings[side] = mapping
        claims[side] = set(imported.claim_ids)
        points = EvidenceRepository(paths.database).metric_series(
            "CN_CAPACITY_UTILIZATION",
            definition_version=version,
            as_of=acquired_at,
            mode=AsOfMode.PUBLIC,
        )
        ytd_ids[side] = next(
            p.selected_claim_id for p in points if p.dimensions["measure"] == "ytd_rate"
        )
    assert mappings["candidate"] != mappings["comparison"]
    repository = EvidenceRepository(paths.database)
    target_version = manifests["candidate"]["metric_catalog_version"]
    candidate_ytd_id = ytd_ids["candidate"]
    comparison_ytd_id = ytd_ids["comparison"]
    assert candidate_ytd_id is not None and comparison_ytd_id is not None
    assert repository.source_claims_matching_registered_contract(
        (candidate_ytd_id,), definition_version=target_version
    ) == {candidate_ytd_id}
    assert not repository.source_claims_matching_registered_contract(
        (comparison_ytd_id,), definition_version=target_version
    )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not before.gaps, before.gaps
    assert before.evaluated_cutoffs == 1 and before.output_document is not None
    for side in ("comparison", "candidate"):
        inputs = before.output_document["days"][0][side]["macro"][
            "model_input_observation_version_ids"
        ]
        assert set(inputs) == claims[side]
    damaged: str | None
    if artifact == "mapping":
        damaged = mappings["candidate"]
        affected = {"candidate"}
    else:
        receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
        hashes = {
            receipt.raw_hash if artifact == "raw" else receipt.normalized_hash
            for receipt in receipts
        }
        assert len(hashes) == 1  # Both catalogs deliberately use the same raw/normalized bytes.
        damaged = hashes.pop()
        affected = {"candidate", "comparison"}
    assert damaged is not None
    artifact_path = paths.artifacts / damaged[:2] / damaged
    if failure == "missing":
        artifact_path.unlink()
    else:
        artifact_path.write_bytes(b"damaged artifact")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert set(after.gaps) == {
        f"{side}_context_selection_invalid:CN_CAPACITY_UTILIZATION" for side in affected
    }
    assert after.evaluated_cutoffs == 1 and after.output_document is not None
    day = after.output_document["days"][0]
    for side in ("comparison", "candidate"):
        adopted = set(day[side]["macro"]["model_input_observation_version_ids"])
        if side not in affected:
            assert adopted == claims[side]
        elif artifact == "mapping":
            assert ytd_ids[side] not in adopted
        else:
            assert not claims[side] & adopted
        assert claims[side] <= set(day[side]["observation_version_ids"])


@pytest.mark.parametrize("artifact", ["raw", "normalized", "mapping", "basis"])
def test_capacity_q1_public_replay_keeps_old_cutoff_but_rejects_bad_latest_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests = {}
    original_claims = {}
    acquired_at = datetime(2026, 8, 29, tzinfo=UTC)
    revised_claims: set[str] = set()
    revised_digest = ""
    for side in ("comparison", "candidate"):
        request, mapping_hash, raw, _, url = prepared_capacity_mapping_request(paths, side=side)
        version = request["manifest"]["metric_catalog_version"]
        if side == "candidate":
            # Synthetic later publication; both exact mappings are explicitly in
            # the first admitting model's immutable grant set before ingestion.
            revised_raw = raw.replace(b"73.6", b"73.7").replace(
                b"2026/04/16 10:00", b"2026/04/17 10:00"
            )
            revised_digest = store_artifact(
                paths.database, paths.artifacts, revised_raw, "text/html", url
            ).content_hash
            mapping = json.loads((paths.artifacts / mapping_hash[:2] / mapping_hash).read_bytes())
            mapping["source_document"]["artifact_hash"] = revised_digest
            mapping["source_document"]["bytes"] = len(revised_raw)
            mapping["source"]["value"] = mapping["target"]["value"] = 73.7
            basis_reference = "synthetic:independent-later-mapping-basis"
            future_basis = store_artifact(
                paths.database,
                paths.artifacts,
                b"Synthetic independently reviewed basis for the later exact raw.",
                "text/markdown",
                basis_reference,
            ).content_hash
            mapping["basis"] = {
                "artifact_hash": future_basis,
                "source_reference": basis_reference,
            }
            added_mapping = save(paths, mapping)
            mapping_reference = f"source-field-mapping:{added_mapping}"
            store_artifact(
                paths.database,
                paths.artifacts,
                encode(mapping),
                "application/json",
                mapping_reference,
            )
            package_hash = request["package_hashes"][0]
            package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
            review_hash = package["review_hash"]
            review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
            for criterion in ("semantics", "fields"):
                review["assessments"][criterion]["evidence"].append(
                    {"artifact_hash": added_mapping, "source_reference": mapping_reference}
                )
            package["review_hash"] = save(paths, review)
            request["package_hashes"] = [save(paths, package)]
        submit(paths, save(paths, request))
        model_id = json.loads(capsys.readouterr().out)["model_version_id"]
        manifest = ModelRepository(paths.database).manifest(model_id)
        # Two-day component verification, not full 120-day model acceptance.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        imported = ingest_official_context_document(
            paths,
            raw,
            family="nbs_capacity_utilization",
            source_url=url,
            expected_period="2026-Q1",
            fetched_at=acquired_at,
            clock=lambda: acquired_at,
            definition_version=version,
        )
        original_claims[side] = set(imported.claim_ids)
        if side == "candidate":
            later = acquired_at + timedelta(hours=1)
            revised = ingest_official_context_document(
                paths,
                revised_raw,
                family="nbs_capacity_utilization",
                source_url=url,
                expected_period="2026-Q1",
                fetched_at=later,
                clock=lambda: acquired_at + timedelta(hours=1),
                definition_version=version,
            )
            revised_claims = set(revised.claim_ids)
            points = EvidenceRepository(paths.database).metric_series(
                "CN_CAPACITY_UTILIZATION",
                definition_version=version,
                as_of=later,
                mode=AsOfMode.SYSTEM,
            )
            assert {point.selected_claim_id for point in points} == revised_claims
            assert {p.dimensions["measure"]: p.selected_value for p in points} == {
                "quarter_rate": 73.7,
                "yoy_change": -0.5,
                "ytd_rate": 73.7,
            }
            assert {claim.public_available_at for point in points for claim in point.claims} == {
                datetime(2026, 4, 17, 2, tzinfo=UTC)
            }
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-04-16",
        requested_end="2026-04-17",
    )
    assert not before.gaps and before.evaluated_cutoffs == 2
    assert before.output_document is not None
    for index, expected in enumerate((original_claims["candidate"], revised_claims)):
        day = before.output_document["days"][index]
        assert set(day["candidate"]["macro"]["model_input_observation_version_ids"]) == expected
        assert (
            set(day["comparison"]["macro"]["model_input_observation_version_ids"])
            == (original_claims["comparison"])
        )
    (receipt,) = (
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.raw_hash == revised_digest
    )
    damaged = {
        "raw": revised_digest,
        "normalized": receipt.normalized_hash,
        "mapping": added_mapping,
        "basis": future_basis,
    }[artifact]
    assert damaged is not None
    (paths.artifacts / damaged[:2] / damaged).write_bytes(b"damaged later revision")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-04-16",
        requested_end="2026-04-17",
    )
    assert after.gaps == ("candidate_context_selection_invalid:CN_CAPACITY_UTILIZATION",)
    assert after.evaluated_cutoffs == 2 and after.output_document is not None
    earlier, latest = after.output_document["days"]
    assert (
        set(earlier["candidate"]["macro"]["model_input_observation_version_ids"])
        == (original_claims["candidate"])
    )
    latest_inputs = set(latest["candidate"]["macro"]["model_input_observation_version_ids"])
    assert not latest_inputs & original_claims["candidate"]
    if artifact in {"mapping", "basis"}:
        revised_ytd = next(
            point.selected_claim_id for point in points if point.dimensions["measure"] == "ytd_rate"
        )
        assert latest_inputs == revised_claims - {revised_ytd}
    else:
        assert not latest_inputs & revised_claims
    assert revised_claims <= set(latest["candidate"]["observation_version_ids"])
    for day in (earlier, latest):
        assert (
            set(day["comparison"]["macro"]["model_input_observation_version_ids"])
            == (original_claims["comparison"])
        )


@pytest.mark.parametrize(
    "fault",
    [
        "ordinary_json",
        "ordinary_markdown",
        "wrong_reference_hash",
        "mixed_roles",
        "self_declared_contract",
    ],
)
def test_capacity_mapping_reference_role_requires_actual_admission_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, _, _, _ = prepared_capacity_mapping_request(paths)
    submit(paths, save(paths, request))
    assert json.loads(capsys.readouterr().out)["model_version_id"]
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    if fault == "self_declared_contract":
        request["manifest"]["source_mapping_reference_contract"] = {
            "version": "source-mapping-reference-v0001",
            "request_hash": "0" * 64,
        }
        bind_synthetic_review(paths, request, package)
    else:
        content = (paths.artifacts / mapping_hash[:2] / mapping_hash).read_bytes()
        if fault == "ordinary_json":
            content = encode({"synthetic": True, "role": "ordinary-evidence"})
        elif fault == "ordinary_markdown":
            content = b"Synthetic ordinary review evidence, not a field mapping."
        digest = hashlib.sha256(content).hexdigest()
        reference = (
            f"source-field-mapping:{'0' * 64 if fault == 'wrong_reference_hash' else digest}"
        )
        store_artifact(
            paths.database, paths.artifacts, content, "application/octet-stream", reference
        )
        for criterion in ("semantics", "fields"):
            if fault == "mixed_roles" and criterion == "fields":
                continue
            for item in review["assessments"][criterion]["evidence"]:
                if item["artifact_hash"] == mapping_hash:
                    item.update(artifact_hash=digest, source_reference=reference)
        package["review_hash"] = save(paths, review)
        request["package_hashes"] = [save(paths, package)]
    versions = ModelRepository(paths.database).list_versions()
    with pytest.raises(SystemExit) as exited:
        submit(paths, save(paths, request))
    assert exited.value.code == 2
    assert ModelRepository(paths.database).list_versions() == versions
    expected = (
        "certification_manifest_reserved_fields"
        if fault == "self_declared_contract"
        else "certification_source_mapping_invalid"
    )
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == f"error: {expected}\n"


@pytest.mark.parametrize(
    "damaged_dependency",
    ["request", "package", "review", "history", "fields", "legacy_mapping", "legacy_basis"],
)
def test_capacity_q1_mapping_still_requires_common_and_legacy_dependencies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_dependency: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, raw, _, url = prepared_capacity_mapping_request(paths)
    version = request["manifest"]["metric_catalog_version"]
    mapping_bytes = (paths.artifacts / mapping_hash[:2] / mapping_hash).read_bytes()
    mapping = json.loads(mapping_bytes)
    package_hash = request["package_hashes"][0]
    package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
    review_hash = package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    if not damaged_dependency.startswith("legacy_"):
        reference = f"source-field-mapping:{mapping_hash}"
        store_artifact(
            paths.database, paths.artifacts, mapping_bytes, "application/json", reference
        )
        for criterion in ("semantics", "fields"):
            for evidence in review["assessments"][criterion]["evidence"]:
                if evidence["artifact_hash"] == mapping_hash:
                    evidence["source_reference"] = reference
    # Ordinary evidence remains a common prerequisite, including a criterion
    # outside semantics/fields and an attachment after the valid mapping grant.
    common_hashes = {}
    for criterion in ("history", "fields"):
        reference = f"synthetic:common-capacity-{criterion}-evidence"
        common_hash = store_artifact(
            paths.database,
            paths.artifacts,
            encode({"synthetic": True, "criterion": criterion}),
            "application/json",
            reference,
        ).content_hash
        common_hashes[criterion] = common_hash
        review["assessments"][criterion]["evidence"].append(
            {"artifact_hash": common_hash, "source_reference": reference}
        )
    review_hash = save(paths, review)
    package["review_hash"] = review_hash
    package_hash = save(paths, package)
    request["package_hashes"] = [package_hash]
    request_hash = save(paths, request)
    submit(paths, request_hash)
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_id)
    acquired_at = datetime(2026, 8, 29, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_capacity_utilization",
        source_url=url,
        expected_period="2026-Q1",
        fetched_at=acquired_at,
        clock=lambda: acquired_at,
        definition_version=version,
    )
    repository = EvidenceRepository(paths.database)
    points = repository.metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=version,
        as_of=acquired_at,
        mode=AsOfMode.SYSTEM,
    )
    ytd_claim_id = next(
        point.selected_claim_id for point in points if point.dimensions["measure"] == "ytd_rate"
    )
    assert ytd_claim_id is not None
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic:common-mapping-dependency",
        model_version_id=model_id,
        system_as_of=acquired_at,
        release_event_id=imported.release_event_id,
        metric_ids=("CN_CAPACITY_UTILIZATION",),
        period="2026-Q1",
    )
    selected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selected.complete and set(selected.selected_claim_ids) == set(imported.claim_ids)
    before = build_context_projection(
        repository, as_of=acquired_at, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    before_inputs = before.macro["model_input_observation_version_ids"]
    assert isinstance(before_inputs, list) and set(imported.claim_ids) <= set(before_inputs)
    damaged_hash = {
        "request": request_hash,
        "package": package_hash,
        "review": review_hash,
        "history": common_hashes["history"],
        "fields": common_hashes["fields"],
        "legacy_mapping": mapping_hash,
        "legacy_basis": mapping["basis"]["artifact_hash"],
    }[damaged_dependency]
    (paths.artifacts / damaged_hash[:2] / damaged_hash).write_bytes(b"damaged common prerequisite")
    after_selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert not after_selection.complete and ytd_claim_id not in after_selection.selected_claim_ids
    after = build_context_projection(
        repository, as_of=acquired_at, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    after_inputs = after.macro["model_input_observation_version_ids"]
    assert isinstance(after_inputs, list) and ytd_claim_id not in after_inputs
    assert set(imported.claim_ids) <= set(after.observation_version_ids)


def test_capacity_q1_new_raw_cannot_expand_an_existing_catalog_mapping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, raw, digest, url = prepared_capacity_mapping_request(paths)
    version = request["manifest"]["metric_catalog_version"]
    submit(paths, save(paths, request))
    first_model = json.loads(capsys.readouterr().out)["model_version_id"]
    acquired_at = datetime(2026, 8, 29, tzinfo=UTC)

    def ingest(content: bytes, catalog: str, at: datetime) -> Any:
        return ingest_official_context_document(
            paths,
            content,
            family="nbs_capacity_utilization",
            source_url=url,
            expected_period="2026-Q1",
            fetched_at=at,
            clock=lambda: at,
            definition_version=catalog,
        )

    first = ingest(raw, version, acquired_at)
    # Synthetic revision with the same URL and page timestamp, a changed literal,
    # and a new content hash. It is not evidence of an actual official revision.
    revised_raw = raw.replace(b"73.6", b"73.7")
    revised_digest = hashlib.sha256(revised_raw).hexdigest()
    assert revised_digest != digest
    revised_at = acquired_at + timedelta(hours=1)
    with pytest.raises(ValueError, match="registered_capacity_q1_mapping_unresolved"):
        ingest(revised_raw, version, revised_at)
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert len(receipts) == 2
    assert {receipt.raw_hash for receipt in receipts} == {digest, revised_digest}
    assert all(receipt.validated_at is not None for receipt in receipts)

    def bind_revised_mapping(candidate: dict[str, Any], original: str) -> None:
        mapping = json.loads((paths.artifacts / original[:2] / original).read_bytes())
        mapping["source_document"]["artifact_hash"] = revised_digest
        mapping["source_document"]["bytes"] = len(revised_raw)
        mapping["source"]["value"] = mapping["target"]["value"] = 73.7
        revised_mapping = save(paths, mapping)
        package_hash = candidate["package_hashes"][0]
        package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
        review_hash = package["review_hash"]
        review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
        for criterion in ("semantics", "fields"):
            for reference in review["assessments"][criterion]["evidence"]:
                if reference["artifact_hash"] == original:
                    reference["artifact_hash"] = revised_mapping
        package["review_hash"] = save(paths, review)
        candidate["package_hashes"] = [save(paths, package)]

    # A later candidate may reuse identical definitions, but the first admitting
    # model still owns this catalog's grants. Its original mapping stays immutable.
    bind_revised_mapping(request, mapping_hash)
    submit(paths, save(paths, request))
    later_model = json.loads(capsys.readouterr().out)["model_version_id"]
    assert later_model != first_model
    assert ModelRepository(paths.database).manifest(later_model)["metric_catalog_version"] == (
        version
    )
    with pytest.raises(ValueError, match="registered_capacity_q1_mapping_unresolved"):
        ingest(revised_raw, version, revised_at + timedelta(minutes=1))
    original_points = EvidenceRepository(paths.database).metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=version,
        as_of=revised_at + timedelta(minutes=2),
        mode=AsOfMode.SYSTEM,
    )
    assert {point.selected_claim_id for point in original_points} == set(first.claim_ids)

    # The explicitly reviewed new raw is usable under a separately registered
    # definition version. The unchanged old page timestamp cannot date the revision.
    revised_request, revised_mapping, _, _, _ = prepared_capacity_mapping_request(
        paths, side="revised"
    )
    bind_revised_mapping(revised_request, revised_mapping)
    submit(paths, save(paths, revised_request))
    revised_model = json.loads(capsys.readouterr().out)["model_version_id"]
    revised_version = revised_request["manifest"]["metric_catalog_version"]
    ingested_at = revised_at + timedelta(minutes=3)
    revised = ingest(revised_raw, revised_version, ingested_at)
    repository = EvidenceRepository(paths.database)
    system = repository.metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=revised_version,
        as_of=ingested_at,
        mode=AsOfMode.SYSTEM,
    )
    assert {point.selected_claim_id for point in system} == set(revised.claim_ids)
    assert {p.dimensions["measure"]: p.selected_value for p in system} == {
        "quarter_rate": 73.7,
        "yoy_change": -0.5,
        "ytd_rate": 73.7,
    }
    assert all(
        claim.public_available_at is None and claim.release_at is None
        for point in system
        for claim in point.claims
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic:q1-revision-selection",
        model_version_id=revised_model,
        system_as_of=ingested_at,
        release_event_id=revised.release_event_id,
        metric_ids=("CN_CAPACITY_UTILIZATION",),
        period="2026-Q1",
    )
    # A historical target always requires its PUBLIC boundary, even when the
    # retrieval query also uses SYSTEM. Direct SYSTEM evidence remains available.
    for mode in (AsOfMode.SYSTEM, AsOfMode.PUBLIC):
        selection = select_retrieval_input(paths, run, mode=mode)
        assert not selection.complete and not selection.selected_claim_ids
    manifest = ModelRepository(paths.database).manifest(revised_model)
    for mode, expected in (
        (AsOfMode.SYSTEM, set(revised.claim_ids)),
        (AsOfMode.PUBLIC, set()),
    ):
        context = build_context_projection(
            repository, as_of=ingested_at, model_manifest=manifest, as_of_mode=mode
        )
        actual = context.macro["model_input_observation_version_ids"]
        assert isinstance(actual, list)
        assert set(actual) == expected


@pytest.mark.parametrize(
    "fault",
    [
        "no_receipt",
        "wrong_receipt",
        "one_wrong_of_two_receipts",
        "raw_missing",
        "raw_damaged",
        "normalized_missing",
        "normalized_damaged",
        "normalized_wrong_value",
    ],
)
def test_capacity_q1_direct_append_requires_all_matching_receipts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _, raw, digest, url = prepared_capacity_mapping_request(paths)
    submit(paths, save(paths, request))
    capsys.readouterr()
    version = request["manifest"]["metric_catalog_version"]
    acquired_at = datetime(2026, 8, 29, tzinfo=UTC)
    imported = ingest_official_context_document(
        paths,
        raw,
        family="nbs_capacity_utilization",
        source_url=url,
        expected_period="2026-Q1",
        fetched_at=acquired_at,
        clock=lambda: acquired_at,
        definition_version=version,
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    repository = EvidenceRepository(paths.database)
    claim = SourceClaimInput(
        metric_id="CN_CAPACITY_UTILIZATION",
        definition_version=version,
        period_kind="year_to_quarter",
        period_start="2026-01-01",
        period_end="2026-03-31",
        dimensions={"industry": "all_industry", "measure": "ytd_rate"},
        value=73.6,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percent",
        provider="国家统计局",
        source_reference=f"{url}#sha256={digest}",
        release_event_id=imported.release_event_id,
        release_at=datetime(2026, 4, 16, 2, tzinfo=UTC),
        public_available_at=datetime(2026, 4, 16, 2, tzinfo=UTC),
        fetched_at=acquired_at,
        available_at=acquired_at,
        certification_status="certified",
        quality_status="validated",
        acquisition_id=receipt.acquisition_id,
    )
    # Even this public direct-write boundary accepts the complete positive first.
    (stored,) = repository.append_source_claims((claim,), availability_clock=lambda: acquired_at)
    assert stored.claim_id in imported.claim_ids
    if fault == "no_receipt":
        claim = replace(claim, acquisition_id=None)
    elif fault in {"wrong_receipt", "one_wrong_of_two_receipts", "normalized_wrong_value"}:
        other_raw = (
            raw if fault == "normalized_wrong_value" else raw + b"<!-- synthetic vintage -->"
        )

        def parse(content: bytes) -> ParsedOfficialContextRelease:
            return parse_official_context_document(
                content,
                family="nbs_capacity_utilization",
                source_url=url,
                expected_period="2026-Q1",
                fetched_at=acquired_at,
            )

        def normalize(parsed: ParsedOfficialContextRelease) -> dict[str, Any]:
            document = asdict(parsed)
            if fault == "normalized_wrong_value":
                for scalar in document["scalars"]:
                    if scalar["dimensions"]["measure"] == "ytd_rate":
                        scalar["value"] = 73.7
            return document

        other = acquisitions.capture(
            provider="国家统计局",
            api_name="document_import",
            parameters={
                "source_url": url,
                "period": "2026-Q1",
                "family": "nbs_capacity_utilization",
            },
            fields="",
            parser_version="official-context-parser-v0004",
            fetch=lambda: other_raw,
            parse=parse,
            normalize=normalize,
            clock=lambda: acquired_at,
        )
        assert other.receipt.validated_at == acquired_at
        # CAS checks alone pass for both receipts; their raw/normalized meaning differs.
        assert acquisitions.read_content(other.receipt.acquisition_id, "raw") == other_raw
        assert acquisitions.read_content(other.receipt.acquisition_id, "normalized")
        claim = (
            replace(claim, acquisition_ids=(other.receipt.acquisition_id,))
            if fault == "one_wrong_of_two_receipts"
            else replace(claim, acquisition_id=other.receipt.acquisition_id)
        )
    else:
        artifact_hash = receipt.raw_hash if fault.startswith("raw_") else receipt.normalized_hash
        assert artifact_hash is not None
        artifact_path = paths.artifacts / artifact_hash[:2] / artifact_hash
        if fault.endswith("missing"):
            artifact_path.unlink()
        else:
            artifact_path.write_bytes(b"damaged artifact")
    with pytest.raises(ValueError, match="registered_capacity_q1_mapping_unresolved"):
        repository.append_source_claims((claim,), availability_clock=lambda: acquired_at)
    points = repository.metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=version,
        as_of=acquired_at,
        mode=AsOfMode.SYSTEM,
    )
    assert {point.selected_claim_id for point in points} == set(imported.claim_ids)


@pytest.mark.parametrize(
    "fault",
    [
        "independent_ytd",
        "independent_equal_ytd",
        "missing_rate",
        "missing_industry",
        "industry_substitute",
        "duplicate_industry",
        "wrong_quarter",
        "wrong_year",
    ],
)
def test_capacity_q1_mapping_admission_requires_an_unambiguous_alias_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, mapping_hash, _, _, url = prepared_capacity_mapping_request(paths)
    mapping = json.loads((paths.artifacts / mapping_hash[:2] / mapping_hash).read_bytes())
    # Synthetic source-layout tests; the main positive separately uses archived raw.
    header = (
        "<tr><th>行业</th><th>一季度</th></tr>"
        "<tr><th>产能利用率（%）</th><th>比上年同期增减（百分点）</th></tr>"
    )
    row = "<tr><td>工业</td><td>73.6</td><td>-0.5</td></tr>"
    content = (
        "<html><body><h1>2026年一季度全国规模以上工业产能利用率</h1>"
        f"<p>2026-04-16 10:00</p><table>{header}{row}</table></body></html>"
    )

    def bind_raw(text: str, previous_mapping: str, ytd_value: float = 73.6) -> str:
        raw = text.encode()
        artifact = store_artifact(paths.database, paths.artifacts, raw, "text/html", url)
        mapping["source_document"] = {
            "artifact_hash": artifact.content_hash,
            "source_reference": url,
            "bytes": len(raw),
        }
        mapping["target"]["value"] = ytd_value
        current_mapping = save(paths, mapping)
        package_hash = request["package_hashes"][0]
        package = json.loads((paths.artifacts / package_hash[:2] / package_hash).read_bytes())
        review_hash = package["review_hash"]
        review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
        for criterion in ("semantics", "fields"):
            for reference in review["assessments"][criterion]["evidence"]:
                if reference["artifact_hash"] == previous_mapping:
                    reference["artifact_hash"] = current_mapping
        package["review_hash"] = save(paths, review)
        request["package_hashes"] = [save(paths, package)]
        return current_mapping

    mapping_hash = bind_raw(content, mapping_hash)
    submit(paths, save(paths, request))
    assert json.loads(capsys.readouterr().out)["model_version_id"]
    if fault.startswith("independent_"):
        ytd_value = 74.0 if fault == "independent_ytd" else 73.6
        altered = content.replace(
            header + row,
            "<tr><th>行业</th><th>当季（%）</th><th>同比变化（百分点）</th><th>累计（%）</th></tr>"
            f"<tr><td>全国规模以上工业</td><td>73.6</td><td>-0.5</td><td>{ytd_value}</td></tr>",
        )
        parsed = parse_official_context_document(
            altered.encode(),
            family="nbs_capacity_utilization",
            source_url=url,
            expected_period="2026-Q1",
            fetched_at=datetime(2026, 8, 29, tzinfo=UTC),
        )
        assert {item.dimensions["measure"]: item.value for item in parsed.scalars} == {
            "quarter_rate": 73.6,
            "yoy_change": -0.5,
            "ytd_rate": ytd_value,
        }
    else:
        ytd_value = 73.6
        altered = {
            "missing_rate": content.replace("<td>73.6</td>", ""),
            "missing_industry": content.replace(row, ""),
            "industry_substitute": content.replace("<td>工业</td>", "<td>制造业</td>"),
            "duplicate_industry": content.replace(row, row + row.replace("73.6", "73.7")),
            "wrong_quarter": content.replace("一季度", "二季度"),
            "wrong_year": content.replace("2026年", "2025年"),
        }[fault]
    assert altered != content
    bind_raw(altered, mapping_hash, ytd_value)
    versions = ModelRepository(paths.database).list_versions()
    with pytest.raises(SystemExit) as exited:
        submit(paths, save(paths, request))
    assert exited.value.code == 2
    assert ModelRepository(paths.database).list_versions() == versions
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: certification_source_mapping_invalid\n"


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


@pytest.mark.parametrize(
    ("document_kind", "consumer"),
    [
        ("compact", "none"),
        ("official_original", "none"),
        ("official_original", "selection"),
        ("official_original", "context"),
    ],
)
def test_admitted_catalog_consumes_cpi_with_separate_categories_and_public_system_times(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], document_kind: str, consumer: str
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
    model_inputs = context.macro["model_input_observation_version_ids"]
    assert isinstance(model_inputs, list)
    assert set(ingested.claim_ids) <= set(model_inputs)
    with pytest.raises(LookupError, match="active_model_unavailable"):
        ModelRepository(paths.database).active()
    if consumer != "none":
        (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
        assert receipt.normalized_hash is not None
        (paths.artifacts / receipt.normalized_hash[:2] / receipt.normalized_hash).write_bytes(
            b"damaged CPI normalized"
        )
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
            after_inputs = after_context.macro["model_input_observation_version_ids"]
            assert isinstance(after_inputs, list)
            assert set(ingested.claim_ids).isdisjoint(after_inputs)
            assert set(ingested.claim_ids) <= set(after_context.observation_version_ids)


@pytest.mark.parametrize("metric_id", ["CN_CPI_HEADLINE", "CN_CORE_CPI"])
def test_cpi_public_replay_reports_invalid_selected_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], metric_id: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    digest = "a4b8c84fa4b005807a9c30b4a41c06726f571bd203e753db81532be4dee54a49"
    raw = (
        Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair/evidence-13" / digest
    ).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    acquired_at = datetime(2026, 8, 9, 2, tzinfo=UTC)
    manifests = {}
    claims = {}
    receipts = {}
    for side in ("comparison", "candidate"):
        manifest = admitted_source_variant(paths, capsys, side, metric_id=metric_id)
        # Single-day component evidence, not the full model's certification or 120-day replay.
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        imported = ingest_official_context_document(
            paths,
            raw + b"<!-- synthetic candidate receipt -->" if side == "candidate" else raw,
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1965008.html",
            expected_period="2026-07",
            fetched_at=acquired_at,
            clock=lambda: acquired_at,
            definition_version=manifest["metric_catalog_version"],
        )
        claims[side] = set(imported.claim_ids)
        (acquisition,) = EvidenceRepository(paths.database).source_claim_acquisitions_many(
            (imported.claim_ids[0],)
        )[imported.claim_ids[0]]
        receipts[side] = acquisition.receipt
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert not before.gaps, before.gaps
    assert before.evaluated_cutoffs == 1 and before.output_document is not None
    for side in ("comparison", "candidate"):
        day = before.output_document["days"][0][side]
        assert set(day["macro"]["model_input_observation_version_ids"]) == claims[side]
    content_hash = receipts["candidate"].normalized_hash
    assert content_hash is not None and content_hash != receipts["comparison"].normalized_hash
    (paths.artifacts / content_hash[:2] / content_hash).write_bytes(b"damaged CPI normalized")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert after.gaps == (f"candidate_context_selection_invalid:{metric_id}",)
    assert after.evaluated_cutoffs == 1 and after.output_document is not None
    day = after.output_document["days"][0]
    assert day["candidate"]["macro"]["model_input_observation_version_ids"] == []
    assert (
        set(day["comparison"]["macro"]["model_input_observation_version_ids"])
        == claims["comparison"]
    )
    assert claims["candidate"] <= set(day["candidate"]["observation_version_ids"])


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


def admitted_daily_breadth_manifest(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    *,
    side: str = "daily",
    source_code: str = "tushare:daily:breadth-v0002",
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-breadth-v2-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] in {"CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"}:
            definition["source_codes"] = [source_code]
            if side == "candidate":
                definition["source_candidates"] = [
                    *definition["source_candidates"],
                    "https://www.sse.com.cn/synthetic-breadth-review",
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


def synthetic_breadth_universe(paths: RuntimePaths) -> dict[str, Any]:
    # A reviewed synthetic complete pool, not certification of a real exchange universe.
    original = save(paths, {"synthetic": True, "kind": "historical identity and publication"})
    return {
        "schema_version": "market-breadth-universe-v0001",
        "coverage_start": "2026-08-28",
        "coverage_end": "2026-08-28",
        "coverage_evidence": [original],
        "members": [
            {
                "security_id": identity,
                "ts_code": code,
                "security_type": kind,
                "valid_from": "2020-01-01",
                "valid_until": None,
                "first_trading_day": "2020-01-01",
                "evidence": [original],
            }
            for identity, code, kind in (
                ("ordinary-sh", "600000.SH", "ordinary_a"),
                ("st-delisting-sz", "000001.SZ", "ordinary_a"),
                ("ordinary-bj", "920001.BJ", "ordinary_a"),
                ("b-share", "900901.SH", "b_share"),
                ("cdr", "689009.SH", "cdr"),
            )
        ],
        "events": [],
        "publications": {"2026-08-28": [original]},
        "evidence": [
            {
                "artifact_hash": original,
                "source_reference": "synthetic:official-universe",
                "release_at": "2026-08-28T08:00:00+00:00",
                "public_available_at": "2026-08-28T08:00:00+00:00",
            }
        ],
    }


def save_breadth_review(paths: RuntimePaths, universe: dict[str, Any]) -> str:
    review = {
        "schema_version": "market-breadth-universe-review-v0001",
        "subject_hash": hashlib.sha256(encode(universe)).hexdigest(),
        "reviewer": "synthetic universe reviewer",
        "reviewed_at": "2026-09-13T00:00:00+00:00",
        "decision": "accepted",
    }
    return save(paths, {**universe, "review_hash": save(paths, review)})


@pytest.mark.usefixtures("runtime_clock")
def test_registered_daily_breadth_reads_daily_members_without_window_or_amount(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe_hash = save_breadth_review(paths, synthetic_breadth_universe(paths))
    originals = {}

    def transport(payload: dict[str, Any]) -> bytes:
        api = payload["api_name"]
        responses: dict[str, list[dict[str, Any]]] = {
            "trade_cal": [{"cal_date": "20260828", "is_open": 1}],
            "daily": [
                {
                    "ts_code": code,
                    "trade_date": "20260828",
                    "close": close,
                    "pre_close": "10.000000000000000",
                    "vol": "1",
                    "amount": None,
                }
                for code, close in (
                    ("600000.SH", "10.000000000000001"),
                    ("000001.SZ", "9.000000000000000"),
                    ("920001.BJ", "10.000000000000000"),
                    ("900901.SH", "20"),
                    ("689009.SH", "20"),
                )
            ],
            "suspend_d": [],
        }
        rows = responses[api]
        fields = payload["fields"].split(",")
        raw = encode(
            {
                "code": 0,
                "data": {
                    "fields": fields,
                    "items": [[row[field] for field in fields] for row in rows],
                },
            }
        )
        originals[api] = raw
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-daily-breadth",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:daily-breadth",
        metric_ids=("CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert selection.complete and set(selection.selected_claim_ids) == set(result.claim_ids)
    evidence = EvidenceRepository(paths.database)
    counts = evidence.metric_series(
        "CN_EQ_ADV_DEC",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert {p.dimensions["measure"]: p.selected_value for p in counts} == {
        "advances": 1.0,
        "declines": 1.0,
        "flats": 1.0,
        "net": 0.0,
        "participants": 3.0,
    }
    ratios = evidence.metric_series(
        "CN_EQ_AD_RATIO",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(ratios) == 1 and ratios[0].selected_value == 1.0
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == 4 and all(r.state == "validated" for r in receipts)
    for receipt in receipts:
        raw = acquisitions.read_content(receipt.acquisition_id, "raw")
        if receipt.api_name == "breadth_universe":
            assert hashlib.sha256(raw).hexdigest() == universe_hash
        else:
            assert raw == originals[receipt.api_name]
        normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
        day = normalized["daily_breadth"][0]
        assert day["participants"] == 3 and day["zero_declines"] is False
        assert {m["ts_code"]: m["state"] for m in day["members"]} == {
            "600000.SH": "advance",
            "000001.SZ": "decline",
            "920001.BJ": "flat",
            "900901.SH": "outside_ordinary_a",
            "689009.SH": "outside_ordinary_a",
        }
    links = evidence.source_claim_acquisitions_many(result.claim_ids)
    assert all(len(inputs) == 4 for inputs in links.values())


def breadth_transport(
    quotes: list[dict[str, Any]],
    suspensions: list[dict[str, Any]],
    *,
    days: tuple[str, ...] = ("20260828",),
) -> Any:
    def transport(payload: dict[str, Any]) -> bytes:
        api = payload["api_name"]
        rows = (
            [{"cal_date": day, "is_open": 1} for day in days]
            if api == "trade_cal"
            else [
                r
                for r in (quotes if api == "daily" else suspensions)
                if r["trade_date"] == payload["params"]["trade_date"]
            ]
        )
        fields = payload["fields"].split(",")
        return encode(
            {
                "code": 0,
                "data": {
                    "fields": fields,
                    "items": [[row[field] for field in fields] for row in rows],
                },
            }
        )

    return transport


@pytest.mark.usefixtures("runtime_clock")
def test_registered_daily_breadth_explains_halts_and_unproven_first_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    universe["members"].append(
        {
            **universe["members"][0],
            "security_id": "ipo",
            "ts_code": "002001.SZ",
            "valid_from": "2026-08-28",
            "first_trading_day": "2026-08-28",
        }
    )
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": close, "pre_close": "10", "vol": "1"}
        for code, close in (("000001.SZ", "11"), ("920001.BJ", "10"), ("002001.SZ", "20"))
    ]
    suspensions = [
        {"ts_code": code, "trade_date": "20260828", "suspend_type": kind, "suspend_timing": timing}
        for code, kind, timing in (
            ("600000.SH", "S", ""),
            ("000001.SZ", "S", "09:30-10:00"),
            ("000001.SZ", "R", ""),
        )
    ]
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, suspensions)
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.history()[0]
    document = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    day = document["daily_breadth"][0]
    assert (day["advances"], day["declines"], day["flats"], day["participants"]) == (1, 0, 1, 2)
    assert day["advance_decline_ratio"] == 1 and day["zero_declines"] is True
    states = {m["ts_code"]: m["state"] for m in day["members"]}
    assert states["600000.SH"] == "full_day_suspension"
    assert states["000001.SZ"] == "advance"
    assert states["002001.SZ"] == "first_day_reference_unproven"
    ratios = EvidenceRepository(paths.database).metric_series(
        "CN_EQ_AD_RATIO",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(ratios) == 1 and ratios[0].selected_value == 1


@pytest.mark.usefixtures("runtime_clock")
def test_registered_daily_breadth_zero_participants_stays_unavailable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    universe_hash = save_breadth_review(paths, universe)
    suspensions = [
        {
            "ts_code": m["ts_code"],
            "trade_date": "20260828",
            "suspend_type": "S",
            "suspend_timing": "",
        }
        for m in universe["members"]
        if m["security_type"] == "ordinary_a"
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport([], suspensions))
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 0 and result.claim_ids == ()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for receipt in acquisitions.history():
        assert receipt.state == "validated"
        document = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
        assert document["accepted_scalars"] == []
        assert document["daily_breadth"][0]["status"] == "unavailable:no_participants"
        assert document["daily_breadth"][0]["advance_decline_ratio"] is None
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-daily-breadth-empty",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:daily-breadth",
        metric_ids=("CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete and not selection.selected_claim_ids
    assert len(selection.missing_members) == 6


@pytest.mark.usefixtures("runtime_clock")
def test_registered_daily_breadth_keeps_code_continuity_and_proven_first_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    universe["coverage_start"] = "2026-08-27"
    proof = universe["coverage_evidence"][0]
    universe["publications"]["2026-08-27"] = [proof]
    before = {**universe["members"][2], "ts_code": "830001.BJ", "valid_until": "2026-08-28"}
    universe["members"][2]["valid_from"] = "2026-08-28"
    universe["members"].extend(
        [
            before,
            {
                **universe["members"][0],
                "security_id": "ipo",
                "ts_code": "002001.SZ",
                "valid_from": "2026-08-28",
                "first_trading_day": "2026-08-28",
            },
        ]
    )
    universe["events"] = [
        {
            "kind": "first_day_reference",
            "business_date": "2026-08-28",
            "ts_code": "002001.SZ",
            "reference_semantics": "official_same_day_pre_close",
            "reference_price": "10",
            "evidence": [proof],
        }
    ]
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": day, "close": close, "pre_close": "10", "vol": "1"}
        for day, entries in (
            ("20260827", (("600000.SH", "11"), ("000001.SZ", "9"), ("830001.BJ", "10"))),
            (
                "20260828",
                (("600000.SH", "11"), ("000001.SZ", "9"), ("920001.BJ", "10"), ("002001.SZ", "9")),
            ),
        )
        for code, close in entries
    ]
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, [], days=("20260827", "20260828"))
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 27), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_EQ_ADV_DEC",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert {
        (p.period_end, p.selected_value)
        for p in points
        if p.dimensions["measure"] == "participants"
    } == {
        ("2026-08-27", 3.0),
        ("2026-08-28", 4.0),
    }
    assert {
        (p.period_end, p.selected_value) for p in points if p.dimensions["measure"] == "declines"
    } == {
        ("2026-08-27", 1.0),
        ("2026-08-28", 2.0),
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(r for r in acquisitions.history() if r.api_name == "breadth_universe")
    days = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))[
        "daily_breadth"
    ]
    mapped = [next(m for m in day["members"] if m["state"] == "flat") for day in days]
    assert [(m["security_id"], m["ts_code"]) for m in mapped] == [
        ("ordinary-bj", "830001.BJ"),
        ("ordinary-bj", "920001.BJ"),
    ]
    links = evidence.source_claim_acquisitions_many(result.claim_ids)
    for point in points:
        assert point.selected_claim_id is not None
        inputs = links[point.selected_claim_id]
        assert len(inputs) == 4
        assert {
            i.receipt.parameters["trade_date"]
            for i in inputs
            if i.receipt.api_name in {"daily", "suspend_d"}
        } == {point.period_end.replace("-", "")}


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_member",
        "duplicate_subject",
        "unknown_identity",
        "missing_quote",
        "extra_quote",
        "conflicting_suspension",
        "duplicate_suspension",
        "reversed_interval",
        "unreviewed_change",
    ],
)
def test_registered_daily_breadth_rejects_unresolved_membership(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    suspensions = []
    if fault == "duplicate_member":
        universe["members"].append(dict(universe["members"][0]))
    elif fault == "duplicate_subject":
        universe["members"][1]["security_id"] = universe["members"][0]["security_id"]
    elif fault == "unknown_identity":
        universe["members"][0]["security_type"] = "unclassified"
    elif fault == "missing_quote":
        quotes.pop()
    elif fault == "extra_quote":
        quotes.append({**quotes[0], "ts_code": "002002.SZ"})
    elif fault == "conflicting_suspension":
        quotes.pop(0)
        suspensions = [
            {
                "ts_code": "600000.SH",
                "trade_date": "20260828",
                "suspend_type": kind,
                "suspend_timing": "",
            }
            for kind in ("S", "R")
        ]
    elif fault == "duplicate_suspension":
        suspensions = [
            {
                "ts_code": "600000.SH",
                "trade_date": "20260828",
                "suspend_type": "S",
                "suspend_timing": "09:30-10:00",
            }
        ] * 2
    elif fault == "reversed_interval":
        universe["members"][0]["valid_until"] = "2019-01-01"
    universe_hash = save_breadth_review(paths, universe)
    if fault == "unreviewed_change":
        document = json.loads((paths.artifacts / universe_hash[:2] / universe_hash).read_bytes())
        document["members"][0]["security_id"] = "changed-after-review"
        universe_hash = save(paths, document)
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, suspensions)
    )
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_DEC",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault,reason",
    [
        ("zero_volume", "no_legal_trade"),
        ("missing_reference", "reference_price_missing"),
        ("missing_close", "close_price_missing"),
    ],
)
def test_registered_daily_breadth_explains_unusable_trading_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str, reason: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe_hash = save_breadth_review(paths, synthetic_breadth_universe(paths))
    quotes: list[dict[str, Any]] = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    quotes[0][
        {"zero_volume": "vol", "missing_reference": "pre_close", "missing_close": "close"}[fault]
    ] = "0" if fault == "zero_volume" else None
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    document = json.loads(
        acquisitions.read_content(acquisitions.history()[0].acquisition_id, "normalized")
    )
    day = document["daily_breadth"][0]
    assert day["participants"] == 2 and day["advances"] == 2
    assert next(m["state"] for m in day["members"] if m["ts_code"] == "600000.SH") == reason


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("resolution", ["exact", "other_day", "other_code"])
def test_registered_daily_breadth_limits_official_suspension_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], resolution: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    universe["events"] = [
        {
            "kind": "full_day_suspension",
            "business_date": "2026-08-27" if resolution == "other_day" else "2026-08-28",
            "ts_code": "000001.SZ" if resolution == "other_code" else "600000.SH",
            "evidence": universe["coverage_evidence"],
        }
    ]
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("000001.SZ", "920001.BJ")
    ]
    suspensions = [
        {
            "ts_code": "600000.SH",
            "trade_date": "20260828",
            "suspend_type": kind,
            "suspend_timing": "",
        }
        for kind in ("S", "R")
    ]
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, suspensions)
    )

    def acquire() -> Any:
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )

    if resolution != "exact":
        with pytest.raises(ValueError, match="breadth_suspension_conflict"):
            acquire()
        assert all(
            r.state == "failed"
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        )
        return
    result = acquire()
    assert result.observation_count == 6
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    day = json.loads(
        acquisitions.read_content(acquisitions.history()[0].acquisition_id, "normalized")
    )["daily_breadth"][0]
    assert day["participants"] == 2
    member = next(m for m in day["members"] if m["ts_code"] == "600000.SH")
    assert member["state"] == "full_day_suspension"
    assert member["event_evidence"] == universe["coverage_evidence"]


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "artifact_kind",
    ["daily", "suspend_d", "trade_cal", "breadth_universe", "normalized", "review", "proof"],
)
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_registered_daily_breadth_selection_rejects_damaged_input_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], artifact_kind: str, damage: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-breadth-originals",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:daily-breadth",
        metric_ids=("CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"),
        period="2026-08-28",
    )
    before = select_retrieval_input(paths, run)
    assert before.complete and set(before.selected_claim_ids) == set(result.claim_ids)
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    if artifact_kind == "proof":
        digest = universe["coverage_evidence"][0]
    elif artifact_kind == "review":
        digest = json.loads((paths.artifacts / universe_hash[:2] / universe_hash).read_bytes())[
            "review_hash"
        ]
    elif artifact_kind == "normalized":
        digest = next(r for r in receipts if r.api_name == "daily").normalized_hash
    else:
        digest = next(r for r in receipts if r.api_name == artifact_kind).raw_hash
    assert digest is not None
    original = paths.artifacts / digest[:2] / digest
    if damage == "missing":
        original.unlink()
    else:
        original.write_bytes(b"damaged breadth input")
    after = select_retrieval_input(paths, run)
    assert not after.complete and not after.selected_claim_ids
    assert len(after.missing_members) == 6


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "wrong_value",
        "wrong_unit",
        "wrong_measure",
        "wrong_public_time",
        "missing_output",
        "foreign_definition",
    ],
)
def test_registered_daily_breadth_rejects_changed_scalars_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe_hash = save_breadth_review(paths, synthetic_breadth_universe(paths))
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        )
        first = scalars[0]
        if fault == "wrong_value":
            first = replace(first, value=30.0)
        elif fault == "wrong_unit":
            first = replace(first, unit="ratio")
        elif fault == "wrong_measure":
            first = replace(first, source_field="unsupported")
        elif fault == "wrong_public_time":
            first = replace(first, public_available_at=datetime(2026, 8, 28, 7, tzinfo=UTC))
        elif fault == "foreign_definition":
            first = replace(first, definition_version="metric-catalog-v0003")
        elif fault == "missing_output":
            return scalars[1:]
        return (first, *scalars[1:])

    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == 4 and all(
        r.state == "failed" and r.validated_at is None for r in receipts
    )
    assert all(acquisitions.read_content(r.acquisition_id, "raw") for r in receipts)
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_DEC",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "publication", ["known", "unknown", "future", "date_only", "quote_time_missing"]
)
def test_registered_daily_breadth_respects_publication_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    proof = universe["evidence"][0]
    if publication == "quote_time_missing":
        universe["publications"]["2026-08-28"] = []
    elif publication == "unknown":
        proof["release_at"] = proof["public_available_at"] = None
    elif publication == "future":
        proof["release_at"] = proof["public_available_at"] = "2026-08-28T09:00:00+00:00"
    elif publication == "date_only":
        proof["published_date"] = "2026-08-28"
        proof["release_at"] = None
        proof["public_available_at"] = "2026-08-28T16:00:00+00:00"
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    evidence = EvidenceRepository(paths.database)
    for metric, count in (("CN_EQ_ADV_DEC", 5), ("CN_EQ_AD_RATIO", 1)):
        assert (
            len(
                evidence.metric_series(
                    metric,
                    mode=AsOfMode.SYSTEM,
                    as_of=datetime.now(UTC),
                    definition_version=manifest["metric_catalog_version"],
                )
            )
            == count
        )
        for hour, expected in (
            (7, 0),
            (8, count if publication == "known" else 0),
            (16, 0 if publication in {"unknown", "quote_time_missing"} else count),
        ):
            points = evidence.metric_series(
                metric,
                mode=AsOfMode.PUBLIC,
                as_of=datetime(2026, 8, 28, hour, tzinfo=UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            assert len(points) == expected
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-breadth-publication",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:daily-breadth",
        metric_ids=("CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (publication == "known")
    assert len(selection.selected_claim_ids) == (6 if publication == "known" else 0)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("damaged_input", ["daily", "review"])
def test_registered_daily_breadth_public_replay_rechecks_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged_input: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, hashes = {}, {}
    for side in ("comparison", "candidate"):
        manifest = admitted_daily_breadth_manifest(paths, capsys, side=side)
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        universe = synthetic_breadth_universe(paths)
        universe["synthetic_side"] = side
        universe_hash = save_breadth_review(paths, universe)
        quotes = [
            {
                "ts_code": code,
                "trade_date": "20260828",
                "close": "11",
                "pre_close": "10",
                "vol": "1",
            }
            for code in ("600000.SH", "000001.SZ", "920001.BJ")
        ]
        source = breadth_transport(quotes, [])

        def transport(payload: dict[str, Any], delegate: Any = source, marker: str = side) -> bytes:
            response = json.loads(delegate(payload))
            response["synthetic_side"] = marker
            return encode(response)

        adapter = TushareContextAdapter("synthetic-token", transport=transport)

        def retrieve(
            adapter: TushareContextAdapter = adapter, universe_hash: str = universe_hash
        ) -> tuple[ContextScalar, ...]:
            return adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
            )

        adapter.acquire_scalars(
            paths,
            retrieve,
            definition_version=manifest["metric_catalog_version"],
        )
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        if damaged_input == "review":
            hashes[side] = json.loads(
                (paths.artifacts / universe_hash[:2] / universe_hash).read_bytes()
            )["review_hash"]
        else:
            hashes[side] = next(
                r.raw_hash
                for r in acquisitions.history()
                if r.api_name == "daily"
                and json.loads(acquisitions.read_content(r.acquisition_id, "raw"))["synthetic_side"]
                == side
            )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    assert hashes["candidate"] != hashes["comparison"]
    digest = hashes["candidate"]
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged candidate breadth original")
    after = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert "candidate_context_selection_invalid:CN_EQ_ADV_DEC" in after.gaps
    assert "candidate_context_selection_invalid:CN_EQ_AD_RATIO" in after.gaps
    assert not any(gap.startswith("comparison_") for gap in after.gaps)


@pytest.mark.usefixtures("runtime_clock")
def test_registered_daily_breadth_preserves_numeric_json_price_precision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe_hash = save_breadth_review(paths, synthetic_breadth_universe(paths))
    quotes = [
        {
            "ts_code": code,
            "trade_date": "20260828",
            "close": close,
            "pre_close": "10.0000000000000000",
            "vol": "1",
        }
        for code, close in (
            ("600000.SH", "10.0000000000000001"),
            ("000001.SZ", "10.0000000000000000"),
            ("920001.BJ", "10.0000000000000000"),
        )
    ]
    source = breadth_transport(quotes, [])

    def transport(payload: dict[str, Any]) -> bytes:
        raw: bytes = source(payload)
        return raw.replace(b'"10.0000000000000001"', b"10.0000000000000001").replace(
            b'"10.0000000000000000"', b"10.0000000000000000"
        )

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    points = EvidenceRepository(paths.database).metric_series(
        "CN_EQ_ADV_DEC",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert {p.dimensions["measure"]: p.selected_value for p in points} == {
        "advances": 1.0,
        "declines": 0.0,
        "flats": 2.0,
        "net": 1.0,
        "participants": 3.0,
    }


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault",
    [
        "coverage",
        "member",
        "first_reference",
        "duplicate_proof",
        "missing_reviewer",
        "prior_quote_publication",
    ],
)
def test_registered_daily_breadth_requires_unambiguous_reviewed_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    if fault == "coverage":
        universe["coverage_evidence"] = []
    elif fault == "member":
        universe["members"][0]["evidence"] = []
    elif fault == "first_reference":
        universe["members"][0]["valid_from"] = universe["members"][0]["first_trading_day"] = (
            "2026-08-28"
        )
        universe["events"] = [
            {
                "kind": "first_day_reference",
                "ts_code": "600000.SH",
                "business_date": "2026-08-28",
                "reference_semantics": "official_same_day_pre_close",
                "reference_price": "10",
                "evidence": [],
            }
        ]
    elif fault == "duplicate_proof":
        universe["evidence"].append(
            {**universe["evidence"][0], "release_at": None, "public_available_at": None}
        )
    elif fault == "prior_quote_publication":
        universe["evidence"][0]["release_at"] = universe["evidence"][0]["public_available_at"] = (
            "2026-08-27T08:00:00+00:00"
        )
    universe_hash = save_breadth_review(paths, universe)
    if fault == "missing_reviewer":
        document = json.loads((paths.artifacts / universe_hash[:2] / universe_hash).read_bytes())
        digest = document["review_hash"]
        review = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
        review["reviewer"] = None
        document["review_hash"] = save(paths, review)
        universe_hash = save(paths, document)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "fault", ["empty_calendar", "duplicate_calendar", "legacy_registered", "builtin"]
)
def test_registered_daily_breadth_rejects_unsupported_acquisition_contracts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(
        paths,
        capsys,
        source_code="tushare:daily:breadth-v0001"
        if fault == "legacy_registered"
        else "tushare:daily:breadth-v0002",
    )
    version = "metric-catalog-v0003" if fault == "builtin" else manifest["metric_catalog_version"]
    universe_hash = save_breadth_review(paths, synthetic_breadth_universe(paths))
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ", "920001.BJ")
    ]
    days = (
        ()
        if fault == "empty_calendar"
        else ("20260828", "20260828")
        if fault == "duplicate_calendar"
        else ("20260828",)
    )
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, [], days=days)
    )
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
            ),
            definition_version=version,
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("exit_publication", ["known", "future", "unknown"])
def test_registered_daily_breadth_requires_exit_publication_for_changed_denominator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], exit_publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_daily_breadth_manifest(paths, capsys)
    universe = synthetic_breadth_universe(paths)
    exited = universe["members"][2]
    exited["valid_until"] = "2026-08-28"
    exit_hash = save(paths, {"synthetic": True, "kind": "exit announcement"})
    exited["evidence"] = [exit_hash]
    published = {
        "known": "2026-08-28T08:00:00+00:00",
        "future": "2026-08-29T08:00:00+00:00",
        "unknown": None,
    }[exit_publication]
    universe["evidence"].append(
        {
            "artifact_hash": exit_hash,
            "source_reference": "synthetic:official-exit",
            "release_at": published,
            "public_available_at": published,
        }
    )
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {"ts_code": code, "trade_date": "20260828", "close": "11", "pre_close": "10", "vol": "1"}
        for code in ("600000.SH", "000001.SZ")
    ]
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), universe_hash=universe_hash
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_EQ_ADV_DEC",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert next(p.selected_value for p in points if p.dimensions["measure"] == "participants") == 2
    for cutoff, available in (
        (datetime(2026, 8, 28, 8, tzinfo=UTC), exit_publication == "known"),
        (datetime(2026, 8, 29, 8, tzinfo=UTC), exit_publication != "unknown"),
    ):
        public_points = evidence.metric_series(
            "CN_EQ_ADV_DEC",
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
            definition_version=manifest["metric_catalog_version"],
        )
        assert len(public_points) == (5 if available else 0)
        if cutoff.date() != date(2026, 8, 28):
            # Target-bound retrieval also enforces the target day's release fence.
            continue
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-28",
            client_request_id="exit-publication-" + cutoff.isoformat(),
            model_version_id=manifest["model_version_id"],
            system_as_of=cutoff,
            release_event_id="synthetic:exit-publication",
            metric_ids=("CN_EQ_ADV_DEC", "CN_EQ_AD_RATIO"),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert selection.complete is available
        assert len(selection.selected_claim_ids) == (6 if available else 0)


def admitted_window_breadth_manifest(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *, side: str = "candidate"
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-breadth-window-v2-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] in {"CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"}:
            definition["source_codes"] = ["tushare:daily:breadth-window-v0002"]
            if side == "candidate":
                definition["source_candidates"] = [
                    *definition["source_candidates"],
                    "https://www.sse.com.cn/synthetic-window-review",
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
    "new_listing,scenario",
    [
        (False, "none"),
        (True, "none"),
        (False, "historical"),
        (False, "window_start"),
        (False, "late_price"),
        (False, "cash_dividend"),
        (False, "late_action"),
        (False, "ex_day_halt"),
        (False, "target_halt"),
        (False, "zero_participants"),
        (False, "window_start_action"),
        (False, "duplicate_calendar"),
        (False, "duplicate_action"),
        (False, "prior_halt_chain"),
        (False, "public_before_release"),
        (False, "wrong_date_precision"),
        (False, "date_only"),
        (False, "ipo_full_window"),
        (False, "historical_reference_missing"),
        (False, "ipo_without_trade"),
        (False, "unknown_price"),
        (False, "changed_scalar"),
        (False, "damaged_before_validation"),
        (False, "damaged_before_selection"),
        (False, "damaged_before_replay"),
        (False, "builtin_zero"),
        (False, "missing_source_reference"),
    ],
)
def test_registered_window_breadth_uses_full_window_with_hidden_warmup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], new_listing: bool, scenario: str
) -> None:
    historical_halt = scenario in {
        "historical",
        "window_start",
        "late_price",
        "ex_day_halt",
        "target_halt",
        "zero_participants",
        "builtin_zero",
        "window_start_action",
        "prior_halt_chain",
    }
    halt_code = "000001.SZ" if scenario in {"ex_day_halt", "window_start_action"} else "600000.SH"
    halt_index = (
        2
        if scenario == "prior_halt_chain"
        else 1
        if scenario in {"window_start", "window_start_action"}
        else 119
        if scenario in {"target_halt", "zero_participants", "builtin_zero"}
        else 60
    )
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    # A synthetic exchange calendar, not the certified 2026 China replay calendar.
    days = tuple(
        reversed(
            [
                date(2026, 8, 28) - timedelta(days=i)
                for i in range(170)
                if (date(2026, 8, 28) - timedelta(days=i)).weekday() < 5
            ][:120]
        )
    )
    assert len(days) == 120
    if scenario in {"window_start", "window_start_action", "prior_halt_chain"}:
        for _ in range(2 if scenario == "prior_halt_chain" else 1):
            earlier = days[0] - timedelta(days=1)
            while earlier.weekday() >= 5:
                earlier -= timedelta(days=1)
            days = (earlier, *days)
    universe = synthetic_breadth_universe(paths)
    universe["coverage_start"] = days[0].isoformat()
    proof = universe["evidence"][0]["artifact_hash"]
    universe["publications"] = {day.isoformat(): [proof] for day in days}
    if new_listing:
        universe["members"][1]["valid_from"] = days[10].isoformat()
        universe["members"][1]["first_trading_day"] = days[10].isoformat()
    if scenario in {"ipo_full_window", "ipo_without_trade"}:
        universe["members"][1]["valid_from"] = days[0].isoformat()
        universe["members"][1]["first_trading_day"] = days[0].isoformat()
    if historical_halt:
        # The carried price and pool identity were already public on their own dates.
        before_window = datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), UTC)
        universe["evidence"][0]["release_at"] = before_window.isoformat()
        universe["evidence"][0]["public_available_at"] = before_window.isoformat()
        for day in days:
            daily_proof = save(
                paths, {"synthetic": True, "published_prices_and_suspensions": day.isoformat()}
            )
            published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC).isoformat()
            if scenario == "late_price" and day == days[halt_index - 1]:
                late = days[halt_index] + timedelta(days=1)
                published = datetime(late.year, late.month, late.day, 8, tzinfo=UTC).isoformat()
            universe["evidence"].append(
                {
                    "artifact_hash": daily_proof,
                    "source_reference": "synthetic:dated-market-publication",
                    "release_at": published,
                    "public_available_at": published,
                }
            )
            universe["publications"][day.isoformat()] = [daily_proof]
    universe_hash = save_breadth_review(paths, universe)
    coverage_hash = save(paths, {"synthetic": True, "kind": "complete corporate-action coverage"})
    window_inputs: dict[str, Any] = {
        "schema_version": "market-breadth-window-inputs-v0001",
        "coverage_start": days[0].isoformat(),
        "coverage_end": days[-1].isoformat(),
        "coverage_evidence": [coverage_hash],
        "adjustments": [],
        "evidence": [
            {
                "artifact_hash": coverage_hash,
                "source_reference": "synthetic:official-actions",
                "release_at": "2026-08-28T08:00:00+00:00",
                "public_available_at": "2026-08-28T08:00:00+00:00",
            }
        ],
    }
    action_index = 1 if scenario == "window_start_action" else 60
    if scenario in {
        "cash_dividend",
        "late_action",
        "ex_day_halt",
        "window_start_action",
        "duplicate_action",
    }:
        # Independent reference example: 11.30 -> 10.94 for 0.36 cash/share
        # (research-09-adjustment-sample-429). All dates/publication here are synthetic.
        action_hash = save(paths, {"synthetic": True, "cash_per_share": "0.36"})
        window_inputs["adjustments"] = [
            {
                "event_id": "synthetic:cash-distribution",
                "security_id": "st-delisting-sz",
                "effective_date": days[action_index].isoformat(),
                "method": "official-reference-ratio",
                "reference_before": "11.30",
                "reference_after": "10.94",
                "evidence": [action_hash],
            }
        ]
        published = (
            "2026-08-29T08:00:00+00:00"
            if scenario == "late_action"
            else "2026-08-28T12:00:00+00:00"
            if scenario == "window_start_action"
            else datetime.combine(days[action_index - 1], datetime.min.time(), UTC).isoformat()
        )
        window_inputs["evidence"].append(
            {
                "artifact_hash": action_hash,
                "source_reference": "synthetic:cash-implementation-reference",
                "release_at": published,
                "public_available_at": published,
            }
        )
    if scenario == "duplicate_action":
        window_inputs["adjustments"].append(dict(window_inputs["adjustments"][0]))
    if scenario == "missing_source_reference":
        window_inputs["evidence"][0]["source_reference"] = ""
    if scenario == "public_before_release":
        window_inputs["evidence"][0]["release_at"] = "2026-08-28T10:00:00+00:00"
    if scenario in {"wrong_date_precision", "date_only"}:
        window_inputs["evidence"][0].update(
            published_date="2026-08-28",
            release_at=None if scenario == "date_only" else "2026-08-27T16:00:00+00:00",
            public_available_at="2026-08-28T16:00:00+00:00"
            if scenario == "date_only"
            else "2026-08-27T16:00:00+00:00",
        )
    review_hash = save(
        paths,
        {
            "schema_version": "market-breadth-window-review-v0001",
            "subject_hash": hashlib.sha256(encode(window_inputs)).hexdigest(),
            "reviewer": "synthetic adjustment reviewer",
            "reviewed_at": "2026-09-13T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    window_hash = save(paths, {**window_inputs, "review_hash": review_hash})
    quotes: list[dict[str, Any]] = [
        {
            "ts_code": code,
            "trade_date": day.strftime("%Y%m%d"),
            "close": str(value),
            "pre_close": str(value),
            "vol": "1",
        }
        for index, day in enumerate(days)
        for code, value in (
            ("600000.SH", index + 1),
            ("000001.SZ", len(days) - index),
            ("920001.BJ", 10),
        )
        if not (new_listing and code == "000001.SZ" and index < 10)
        and not (historical_halt and code == halt_code and index == halt_index)
        and not (scenario in {"zero_participants", "builtin_zero"} and index == halt_index)
        and not (scenario == "prior_halt_chain" and code == "600000.SH" and index == 1)
    ]
    if scenario in {
        "cash_dividend",
        "late_action",
        "ex_day_halt",
        "window_start_action",
        "duplicate_action",
    }:
        for quote in quotes:
            if quote["ts_code"] == "000001.SZ":
                value = (
                    "11.30"
                    if quote["trade_date"] < days[action_index].strftime("%Y%m%d")
                    else "10.94"
                )
                quote.update(close=value, pre_close=value)
    for quote in quotes:
        if (
            scenario == "ipo_without_trade"
            and quote["ts_code"] == "000001.SZ"
            and quote["trade_date"] == days[0].strftime("%Y%m%d")
        ):
            quote["vol"] = "0"
        if (
            scenario == "historical_reference_missing"
            and quote["ts_code"] == "000001.SZ"
            and quote["trade_date"] == days[60].strftime("%Y%m%d")
        ):
            quote["pre_close"] = None
        if (
            scenario == "unknown_price"
            and quote["ts_code"] == "600000.SH"
            and quote["trade_date"] == days[60].strftime("%Y%m%d")
        ):
            quote["close"] = None
    suspensions = (
        [
            {
                "ts_code": halt_code,
                "trade_date": days[halt_index].strftime("%Y%m%d"),
                "suspend_type": "S",
                "suspend_timing": None,
            }
        ]
        if historical_halt
        else []
    )
    if scenario in {"zero_participants", "builtin_zero"}:
        suspensions = [
            {**suspensions[0], "ts_code": code} for code in ("600000.SH", "000001.SZ", "920001.BJ")
        ]
    if scenario == "prior_halt_chain":
        suspensions.append({**suspensions[0], "trade_date": days[1].strftime("%Y%m%d")})
    delivered_dates = tuple(day.strftime("%Y%m%d") for day in days)
    if scenario == "duplicate_calendar":
        # 120 rows containing only 119 distinct trading dates.
        delivered_dates = (delivered_dates[0], delivered_dates[0], *delivered_dates[2:])
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=breadth_transport(quotes, suspensions, days=delivered_dates),
    )
    retrieval_completed = False

    def retrieve() -> tuple[ContextScalar, ...]:
        nonlocal retrieval_completed
        scalars = adapter.market_breadth(
            start_date=days[-1],
            end_date=days[-1],
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
            output_days=1,
        )
        retrieval_completed = True
        if scenario == "builtin_zero":
            assert scalars == ()
        if scenario == "changed_scalar":
            return (replace(scalars[0], value=99.0), *scalars[1:])
        if scenario == "damaged_before_validation":
            (paths.artifacts / review_hash[:2] / review_hash).write_bytes(b"damaged window review")
        return scalars

    def acquire() -> Any:
        return adapter.acquire_scalars(
            paths,
            retrieve,
            definition_version=(
                "metric-catalog-v0003"
                if scenario == "builtin_zero"
                else manifest["metric_catalog_version"]
            ),
        )

    if scenario in {
        "duplicate_calendar",
        "duplicate_action",
        "public_before_release",
        "wrong_date_precision",
        "changed_scalar",
        "damaged_before_validation",
        "builtin_zero",
        "missing_source_reference",
    }:
        with pytest.raises(ValueError):
            acquire()
        if scenario == "builtin_zero":
            assert retrieval_completed
        receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
        assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
        assert (
            EvidenceRepository(paths.database).metric_series(
                "CN_EQ_NEW_HIGH_LOW_120",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            == ()
        )
        return
    result = acquire()
    if scenario == "zero_participants":
        assert result.observation_count == 0
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        receipts = acquisitions.history()
        assert len(receipts) == 243 and all(r.state == "validated" for r in receipts)
        output = json.loads(acquisitions.read_content(receipts[0].acquisition_id, "normalized"))
        assert output["accepted_scalars"] == []
        unavailable = output["window_breadth"][0]
        assert unavailable["status"] == "unavailable:no_participants"
        assert unavailable["participants"] == 0 and unavailable["excluded_participants"] == 3
        assert all(unavailable[m] is None for m in ("new_highs", "new_lows", "above_ma_share"))
        assert sum(m["state"] == "full_day_suspension" for m in unavailable["members"]) == 3
        evidence = EvidenceRepository(paths.database)
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"):
            assert (
                evidence.metric_series(
                    metric,
                    mode=AsOfMode.PUBLIC,
                    as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
                    definition_version=manifest["metric_catalog_version"],
                )
                == ()
            )
        return
    assert result.observation_count == 3
    evidence = EvidenceRepository(paths.database)
    if scenario in {"window_start_action", "date_only"}:
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"):
            assert (
                evidence.metric_series(
                    metric,
                    mode=AsOfMode.PUBLIC,
                    as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
                    definition_version=manifest["metric_catalog_version"],
                )
                == ()
            )
    points = tuple(
        point
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120")
        for point in evidence.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(
                2026,
                8,
                29 if scenario == "late_action" else 28,
                16 if scenario == "date_only" else 12 if scenario == "window_start_action" else 8,
                tzinfo=UTC,
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    )
    assert len(points) == 3 and all(p.period_end == "2026-08-28" for p in points)
    values = {p.dimensions["measure"]: p.selected_value for p in points}
    assert values["new_highs"] == (
        0 if scenario in {"late_price", "target_halt", "unknown_price"} else 1
    )
    assert values["new_lows"] == (
        0
        if new_listing
        or scenario == "ipo_without_trade"
        or scenario
        in {
            "cash_dividend",
            "late_action",
            "ex_day_halt",
            "window_start_action",
            "duplicate_action",
        }
        else 1
    )
    assert values["above_ma_share"] == pytest.approx(
        0
        if scenario in {"late_price", "target_halt", "unknown_price"}
        else 50
        if new_listing or scenario in {"late_action", "ipo_without_trade"}
        else 100 / 3
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == (
        247
        if scenario == "prior_halt_chain"
        else 245
        if scenario in {"window_start", "window_start_action"}
        else 243
    ) and all(r.state == "validated" for r in receipts)
    parent_sets = evidence.source_claim_acquisitions_many(
        tuple(p.selected_claim_id for p in points if p.selected_claim_id is not None)
    )
    assert len(parent_sets) == 3
    assert all(
        {i.receipt.acquisition_id for i in inputs} == {r.acquisition_id for r in receipts}
        for inputs in parent_sets.values()
    )
    terminal = next(
        r for r in receipts if r.api_name == "daily" and r.parameters["trade_date"] == "20260828"
    )
    normalized = json.loads(acquisitions.read_content(terminal.acquisition_id, "normalized"))
    window = normalized["window_breadth"][0]
    assert window["participants"] == (
        2
        if new_listing
        or scenario
        in {"late_price", "late_action", "target_halt", "unknown_price", "ipo_without_trade"}
        else 3
    )
    assert window["window_days"] == 120
    if new_listing or scenario == "ipo_without_trade":
        assert (
            next(m["state"] for m in window["members"] if m["security_id"] == "st-delisting-sz")
            == "insufficient_window"
        )
    if scenario in {"late_price", "unknown_price"}:
        assert (
            next(m["state"] for m in window["members"] if m["security_id"] == "ordinary-sh")
            == "insufficient_window"
        )
    if historical_halt and scenario not in {
        "late_price",
        "ex_day_halt",
        "target_halt",
        "window_start_action",
        "prior_halt_chain",
    }:
        carried = next(m for m in window["members"] if m["security_id"] == "ordinary-sh")
        assert carried["carried_dates"] == [days[halt_index].isoformat()]
        assert carried["prices"][
            0 if scenario in {"window_start", "window_start_action"} else 60
        ] == ("1" if scenario in {"window_start", "window_start_action"} else "60")
    if scenario == "prior_halt_chain":
        carried = next(m for m in window["members"] if m["security_id"] == "ordinary-sh")
        assert carried["carried_dates"] == [days[2].isoformat()]
        assert carried["prices"][0] == "1"
    if scenario == "target_halt":
        excluded = next(m for m in window["members"] if m["security_id"] == "ordinary-sh")
        assert excluded["state"] == "full_day_suspension"
        assert "prices" not in excluded
    if scenario == "late_action":
        adjusted = next(m for m in window["members"] if m["security_id"] == "st-delisting-sz")
        assert adjusted["state"] == "insufficient_adjustment_chain"
        assert "prices" not in adjusted
    if scenario in {"cash_dividend", "ex_day_halt", "window_start_action"}:
        adjusted = next(m for m in window["members"] if m["security_id"] == "st-delisting-sz")
        assert adjusted["state"] == "eligible"
        assert adjusted["prices"] == ["547/50"] * 120
        assert adjusted["adjustment_events"] == ["synthetic:cash-distribution"]
        if scenario in {"ex_day_halt", "window_start_action"}:
            assert adjusted["carried_dates"] == [days[action_index].isoformat()]
    assert window["formula_version"] == "ordinary-a-market-window-v0002"
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-window-breadth",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:window-breadth",
        metric_ids=("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (
        scenario not in {"late_action", "window_start_action", "date_only"}
    )
    assert len(selection.selected_claim_ids) == (
        0 if scenario in {"late_action", "window_start_action", "date_only"} else 3
    )

    if scenario == "damaged_before_selection":
        original = paths.artifacts / review_hash[:2] / review_hash
        saved = original.read_bytes()
        try:
            original.write_bytes(b"damaged after validation")
            rejected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
            assert not rejected.complete
            assert rejected.selected_claim_ids == ()
        finally:
            original.write_bytes(saved)
        recovered = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert recovered.complete and len(recovered.selected_claim_ids) == 3

    if scenario == "damaged_before_replay":
        comparison = admitted_window_breadth_manifest(paths, capsys, side="comparison")
        comparison_inputs = {**window_inputs, "synthetic_side": "comparison"}
        comparison_review = save(
            paths,
            {
                "schema_version": "market-breadth-window-review-v0001",
                "subject_hash": hashlib.sha256(encode(comparison_inputs)).hexdigest(),
                "reviewer": "synthetic adjustment reviewer",
                "reviewed_at": "2026-09-13T00:00:00+00:00",
                "decision": "accepted",
            },
        )
        comparison_hash = save(paths, {**comparison_inputs, "review_hash": comparison_review})
        comparison_adapter = TushareContextAdapter(
            "synthetic-token", transport=breadth_transport(quotes, [], days=delivered_dates)
        )
        comparison_adapter.acquire_scalars(
            paths,
            lambda: comparison_adapter.market_breadth(
                start_date=days[-1],
                end_date=days[-1],
                universe_hash=universe_hash,
                window_inputs_hash=comparison_hash,
                output_days=1,
            ),
            definition_version=comparison["metric_catalog_version"],
        )
        manifest.pop("source_certification_packages")
        comparison.pop("source_certification_packages")
        before = evaluate_context_replay(
            paths.database,
            manifest,
            comparison,
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
        assert review_hash != comparison_review
        original = paths.artifacts / review_hash[:2] / review_hash
        original.write_bytes(b"damaged candidate review for replay")
        after = evaluate_context_replay(
            paths.database,
            manifest,
            comparison,
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert "candidate_context_selection_invalid:CN_EQ_NEW_HIGH_LOW_120" in after.gaps
        assert "candidate_context_selection_invalid:CN_EQ_ABOVE_MA120" in after.gaps
        assert not any(gap.startswith("comparison_") for gap in after.gaps)


def china_window_input_dates() -> tuple[date, ...]:
    """239 SSE calendar dates, independently checked in research-09-calendar-warmup-470.

    Calendar response SHA256 2c8576c3d87cca2973053122683cd3ee48c1b29b3524f500179e123d40785705.
    The dates are real; the stock prices and publication evidence below are synthetic.
    """
    calendar_months: dict[tuple[int, int], tuple[int, ...]] = {
        (2025, 9): (3, 4, 5, 8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 29, 30),
        (2025, 10): (9, 10, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 27, 28, 29, 30, 31),
        (2025, 11): (3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28),
        (2025, 12): (
            1,
            2,
            3,
            4,
            5,
            8,
            9,
            10,
            11,
            12,
            15,
            16,
            17,
            18,
            19,
            22,
            23,
            24,
            25,
            26,
            29,
            30,
            31,
        ),
        (2026, 1): (5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 26, 27, 28, 29, 30),
        (2026, 2): (2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 24, 25, 26, 27),
        (2026, 3): (
            2,
            3,
            4,
            5,
            6,
            9,
            10,
            11,
            12,
            13,
            16,
            17,
            18,
            19,
            20,
            23,
            24,
            25,
            26,
            27,
            30,
            31,
        ),
        (2026, 4): (1, 2, 3, 7, 8, 9, 10, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24, 27, 28, 29, 30),
        (2026, 5): (6, 7, 8, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 25, 26, 27, 28, 29),
        (2026, 6): (1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 15, 16, 17, 18, 22, 23, 24, 25, 26, 29, 30),
        (2026, 7): (
            1,
            2,
            3,
            6,
            7,
            8,
            9,
            10,
            13,
            14,
            15,
            16,
            17,
            20,
            21,
            22,
            23,
            24,
            27,
            28,
            29,
            30,
            31,
        ),
        (2026, 8): (3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28),
    }
    return tuple(
        date(year, month, day)
        for (year, month), month_days in calendar_months.items()
        for day in month_days
    )


def synthetic_window_breadth_range(
    paths: RuntimePaths, days: tuple[date, ...]
) -> tuple[TushareContextAdapter, str, str]:
    """Create transparent transport inputs with a separate publication proof for each day."""
    universe = synthetic_breadth_universe(paths)
    universe["coverage_start"] = days[0].isoformat()
    universe["coverage_end"] = days[-1].isoformat()
    known_identity = datetime.combine(days[0] - timedelta(days=1), datetime.min.time(), UTC)
    universe["evidence"][0].update(
        release_at=known_identity.isoformat(), public_available_at=known_identity.isoformat()
    )
    universe["publications"] = {}
    for day in days:
        proof = save(
            paths, {"synthetic": True, "quote_and_suspension_publication": day.isoformat()}
        )
        published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC).isoformat()
        universe["evidence"].append(
            {
                "artifact_hash": proof,
                "source_reference": "synthetic:daily-price-publication",
                "release_at": published,
                "public_available_at": published,
            }
        )
        universe["publications"][day.isoformat()] = [proof]
    universe_hash = save_breadth_review(paths, universe)
    coverage = save(
        paths, {"synthetic": True, "assumption": "no corporate actions in fixture range"}
    )
    window = {
        "schema_version": "market-breadth-window-inputs-v0001",
        "coverage_start": days[0].isoformat(),
        "coverage_end": days[-1].isoformat(),
        "coverage_evidence": [coverage],
        "adjustments": [],
        "evidence": [
            {
                "artifact_hash": coverage,
                "source_reference": "synthetic:fixture-action-coverage",
                "release_at": known_identity.isoformat(),
                "public_available_at": known_identity.isoformat(),
            }
        ],
    }
    review = save(
        paths,
        {
            "schema_version": "market-breadth-window-review-v0001",
            "subject_hash": hashlib.sha256(encode(window)).hexdigest(),
            "reviewer": "synthetic window range reviewer",
            "reviewed_at": "2026-09-13T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    window_hash = save(paths, {**window, "review_hash": review})
    quotes = [
        {
            "ts_code": code,
            "trade_date": day.strftime("%Y%m%d"),
            "close": str(value),
            "pre_close": str(value),
            "vol": "1",
        }
        for index, day in enumerate(days)
        for code, value in (
            ("600000.SH", index + 1),
            ("000001.SZ", len(days) - index),
            ("920001.BJ", 10),
        )
    ]
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=breadth_transport(quotes, [], days=tuple(day.strftime("%Y%m%d") for day in days)),
    )
    return adapter, universe_hash, window_hash


@pytest.mark.usefixtures("runtime_clock")
def test_registered_window_breadth_limits_requested_visible_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-121:]
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
            output_days=1,
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 3
    points = tuple(
        point
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120")
        for point in EvidenceRepository(paths.database).metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
            definition_version=manifest["metric_catalog_version"],
        )
    )
    assert len(points) == 3 and {p.period_end for p in points} == {"2026-08-28"}
    assert {p.dimensions["measure"]: p.selected_value for p in points} == {
        "new_highs": 1.0,
        "new_lows": 1.0,
        "above_ma_share": pytest.approx(100 / 3),
    }


@pytest.mark.usefixtures("runtime_clock")
def test_registered_window_breadth_outputs_fixed_120_days_with_hidden_warmup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()
    assert len(days) == 239 and days[0] == date(2025, 9, 3)
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 3, 9),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 360
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        point
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120")
        for point in evidence.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
            definition_version=manifest["metric_catalog_version"],
        )
    )
    assert len(points) == 360
    visible = {day.isoformat() for day in days if day >= date(2026, 3, 9)}
    assert len(visible) == 120 and {p.period_end for p in points} == visible
    for day in sorted(visible):
        values = {p.dimensions["measure"]: p.selected_value for p in points if p.period_end == day}
        assert values == {
            "new_highs": 1.0,
            "new_lows": 1.0,
            "above_ma_share": pytest.approx(100 / 3),
        }
    first = tuple(
        point
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120")
        for point in evidence.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 3, 9, 8, tzinfo=UTC),
            definition_version=manifest["metric_catalog_version"],
        )
    )
    assert len(first) == 3 and {p.period_end for p in first} == {"2026-03-09"}
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-03-09",
        client_request_id="synthetic-window-first-visible-day",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 3, 9, 8, tzinfo=UTC),
        release_event_id="synthetic:window-first-visible-day",
        metric_ids=("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"),
        period="2026-03-09",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete and len(selection.selected_claim_ids) == 3


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "damaged_input,availability", [("future", (True, False)), ("older", (False, True))]
)
def test_registered_window_breadth_uses_only_each_outputs_required_quotes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    damaged_input: str,
    availability: tuple[bool, bool],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-121:]
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
            output_days=2,
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    runs = tuple(
        RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date=day.isoformat(),
            client_request_id="window-required-parents-" + day.isoformat(),
            model_version_id=manifest["model_version_id"],
            system_as_of=datetime(day.year, day.month, day.day, 8, tzinfo=UTC),
            release_event_id="synthetic:window-required-parents",
            metric_ids=("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"),
            period=day.isoformat(),
        )
        for day in (date(2026, 8, 27), date(2026, 8, 28))
    )
    before = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
    assert all(item.complete and len(item.selected_claim_ids) == 3 for item in before)
    bad_day = days[-1] if damaged_input == "future" else days[0]
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    receipt = next(
        r
        for r in receipts
        if r.api_name == "daily" and r.parameters["trade_date"] == bad_day.strftime("%Y%m%d")
    )
    assert receipt.raw_hash is not None
    artifact = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
    artifact.write_bytes(b"damaged independent quote outside one output window")
    after = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
    assert tuple(item.complete for item in after) == availability
    for initial, selected, available in zip(before, after, availability, strict=True):
        assert selected.selected_claim_ids == (initial.selected_claim_ids if available else ())


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("continuous_identity", [True, False])
def test_registered_window_breadth_requires_identity_continuity_across_code_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], continuous_identity: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-120:]
    _, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    universe = json.loads((paths.artifacts / universe_hash[:2] / universe_hash).read_bytes())
    universe.pop("review_hash")
    transition = days[60]
    previous = universe["members"][0]
    successor = {
        **previous,
        "ts_code": "600001.SH",
        "valid_from": transition.isoformat(),
        "security_id": previous["security_id"] if continuous_identity else "independent-sh",
    }
    previous["valid_until"] = transition.isoformat()
    universe["members"].append(successor)
    universe_hash = save_breadth_review(paths, universe)
    # The prices keep the same ascending path. Only reviewed identity continuity differs.
    quotes = [
        {
            "ts_code": code,
            "trade_date": day.strftime("%Y%m%d"),
            "close": str(value),
            "pre_close": str(value),
            "vol": "1",
        }
        for index, day in enumerate(days)
        for code, value in (
            ("600000.SH" if day < transition else "600001.SH", index + 1),
            ("000001.SZ", 120 - index),
            ("920001.BJ", 10),
        )
    ]
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=breadth_transport(quotes, [], days=tuple(day.strftime("%Y%m%d") for day in days)),
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=days[-1],
            end_date=days[-1],
            output_days=1,
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 3
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        point
        for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120")
        for point in evidence.metric_series(
            metric,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
            definition_version=manifest["metric_catalog_version"],
        )
    )
    assert {p.dimensions["measure"]: p.selected_value for p in points} == {
        "new_highs": 1.0 if continuous_identity else 0.0,
        "new_lows": 1.0,
        "above_ma_share": pytest.approx(100 / 3) if continuous_identity else 0.0,
    }
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    output = json.loads(
        acquisitions.read_content(acquisitions.history()[0].acquisition_id, "normalized")
    )["window_breadth"][0]
    assert output["participants"] == (3 if continuous_identity else 2)
    member = next(m for m in output["members"] if m["ts_code"] == "600001.SH")
    assert member["state"] == ("eligible" if continuous_identity else "insufficient_window")
    if continuous_identity:
        assert (
            len(member["prices"]) == 120
            and member["prices"][0] == "1"
            and member["prices"][-1] == "120"
        )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="window-code-continuity",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:window-code-continuity",
        metric_ids=("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete and len(selection.selected_claim_ids) == 3


def synthetic_window_adjustment(
    paths: RuntimePaths, window_hash: str, *, effective_date: str
) -> tuple[str, str]:
    """Add a reviewed synthetic 10-to-20 reference change for the constant BJ stock."""
    window = json.loads((paths.artifacts / window_hash[:2] / window_hash).read_bytes())
    window.pop("review_hash")
    coverage_hash = save(paths, {"synthetic": True, "kind": "complete fixture action coverage"})
    window["coverage_evidence"] = [coverage_hash]
    window["evidence"][0]["artifact_hash"] = coverage_hash
    action_hash = save(
        paths, {"synthetic": True, "reference_before": "10", "reference_after": "20"}
    )
    window["adjustments"] = [
        {
            "event_id": "synthetic:second-output-adjustment",
            "security_id": "ordinary-bj",
            "effective_date": effective_date,
            "method": "official-reference-ratio",
            "reference_before": "10",
            "reference_after": "20",
            "evidence": [action_hash],
        }
    ]
    window["evidence"].append(
        {
            "artifact_hash": action_hash,
            "source_reference": "synthetic:second-output-adjustment-reference",
            "release_at": "2026-08-27T08:00:00+00:00",
            "public_available_at": "2026-08-27T08:00:00+00:00",
        }
    )
    review_hash = save(
        paths,
        {
            "schema_version": "market-breadth-window-review-v0001",
            "subject_hash": hashlib.sha256(encode(window)).hexdigest(),
            "reviewer": "synthetic independent event reviewer",
            "reviewed_at": "2026-09-13T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    window_hash = save(paths, {**window, "review_hash": review_hash})
    return window_hash, action_hash


@pytest.mark.usefixtures("runtime_clock")
def test_registered_window_breadth_ignores_unused_future_action_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-121:]
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    window_hash, action_hash = synthetic_window_adjustment(
        paths, window_hash, effective_date="2026-08-28"
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
            output_days=2,
            universe_hash=universe_hash,
            window_inputs_hash=window_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 6
    evidence = EvidenceRepository(paths.database)
    lows = evidence.metric_series(
        "CN_EQ_NEW_HIGH_LOW_120",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    # First day: only SZ descends. Second day: BJ is 10 against 119 adjusted prices of 20.
    assert {
        p.period_end: p.selected_value for p in lows if p.dimensions["measure"] == "new_lows"
    } == {"2026-08-27": 1.0, "2026-08-28": 2.0}
    runs = tuple(
        RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date=day.isoformat(),
            client_request_id="window-independent-event-" + day.isoformat(),
            model_version_id=manifest["model_version_id"],
            system_as_of=datetime(day.year, day.month, day.day, 8, tzinfo=UTC),
            release_event_id="synthetic:window-independent-event",
            metric_ids=("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"),
            period=day.isoformat(),
        )
        for day in (date(2026, 8, 27), date(2026, 8, 28))
    )
    initial = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
    assert all(item.complete and len(item.selected_claim_ids) == 3 for item in initial)
    artifact = paths.artifacts / action_hash[:2] / action_hash
    original = artifact.read_bytes()
    try:
        artifact.write_bytes(b"damaged independent future event")
        after = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
        assert tuple(item.complete for item in after) == (True, False)
        assert after[0].selected_claim_ids == initial[0].selected_claim_ids
        assert after[1].selected_claim_ids == ()
    finally:
        artifact.write_bytes(original)
    restored = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
    assert restored == initial


@pytest.mark.usefixtures("runtime_clock")
def test_registered_window_breadth_rejects_noncanonical_adjustment_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-120:]
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    window_hash, _ = synthetic_window_adjustment(paths, window_hash, effective_date="20260828")
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=days[-1],
                end_date=days[-1],
                output_days=1,
                universe_hash=universe_hash,
                window_inputs_hash=window_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
    evidence = EvidenceRepository(paths.database)
    for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"):
        assert (
            evidence.metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            == ()
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("coverage_end", ["20260827", "2026-08-27"])
def test_registered_window_breadth_requires_adjustment_coverage_through_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], coverage_end: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_window_breadth_manifest(paths, capsys)
    days = china_window_input_dates()[-120:]
    adapter, universe_hash, window_hash = synthetic_window_breadth_range(paths, days)
    window = json.loads((paths.artifacts / window_hash[:2] / window_hash).read_bytes())
    window.pop("review_hash")
    window["coverage_end"] = coverage_end
    review = save(
        paths,
        {
            "schema_version": "market-breadth-window-review-v0001",
            "subject_hash": hashlib.sha256(encode(window)).hexdigest(),
            "reviewer": "synthetic coverage boundary reviewer",
            "reviewed_at": "2026-09-13T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    window_hash = save(paths, {**window, "review_hash": review})
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=days[-1],
                end_date=days[-1],
                output_days=1,
                universe_hash=universe_hash,
                window_inputs_hash=window_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
    evidence = EvidenceRepository(paths.database)
    for metric in ("CN_EQ_NEW_HIGH_LOW_120", "CN_EQ_ABOVE_MA120"):
        assert (
            evidence.metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            == ()
        )


def admitted_amount_breadth_manifest(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
    *,
    side: str = "amount",
    source_code: str = "tushare:daily:breadth-amount-v0002",
) -> dict[str, Any]:
    request, _ = prepared_request(paths)
    manifest = request["manifest"]
    manifest["metric_catalog_version"] += "-amount-breadth-v2-" + side
    for definition in manifest["metric_definitions"]:
        definition["definition_version"] = manifest["metric_catalog_version"]
        if definition["metric_id"] == "CN_EQ_ADV_AMOUNT_SHARE":
            definition["source_codes"] = [source_code]
            if side == "candidate":
                definition["source_candidates"] = [
                    *definition["source_candidates"],
                    "https://www.sse.com.cn/synthetic-amount-review",
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


def synthetic_amount_breadth_inputs(
    paths: RuntimePaths,
) -> tuple[TushareContextAdapter, str, dict[str, Any]]:
    universe = synthetic_breadth_universe(paths)
    universe["members"][2].update(valid_from="2026-08-28", first_trading_day="2026-08-28")
    universe_hash = save_breadth_review(paths, universe)
    quotes = [
        {
            "ts_code": code,
            "trade_date": "20260828",
            "close": close,
            "pre_close": reference,
            "vol": "1",
        }
        for code, close, reference in (
            ("600000.SH", "11", "10"),
            ("000001.SZ", "9", "10"),
            ("920001.BJ", "10", None),
        )
    ]
    # These raw fields and disjoint coverage are synthetic assumptions reviewed
    # for this fixture, not a certified decomposition of real TuShare amounts.
    daily_hash = save(
        paths,
        {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "amount", "ah_amount"],
                "items": [
                    ["600000.SH", "20260828", "100", "10"],
                    ["000001.SZ", "20260828", "200", "0"],
                    ["920001.BJ", "20260828", "40", "0"],
                ],
            },
        },
    )
    block_hash = save(
        paths,
        {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "amount"],
                "items": [
                    ["600000.SH", "20260828", "2"],
                    ["000001.SZ", "20260828", "3"],
                    ["920001.BJ", "20260828", "0"],
                ],
            },
        },
    )
    coverage_hash = save(
        paths,
        {
            "synthetic": True,
            "scope": "complete ordinary A exchange turnover for this fixture",
            "effective_from": "2026-08-28",
            "effective_until": "2026-08-29",
            "methods": ["auction", "after_hours", "block"],
            "disjoint": True,
            "daily_amount_unit": "thousand_yuan",
            "block_amount_unit": "ten_thousand_yuan",
        },
    )
    amount = {
        "schema_version": "market-breadth-amount-inputs-v0001",
        "coverage_start": "2026-08-28",
        "coverage_end": "2026-08-28",
        "coverage_evidence": [coverage_hash],
        "coverage_rules": [
            {
                "security_id": member["security_id"],
                "exchange": member["ts_code"].split(".")[1],
                "effective_from": "2026-08-28",
                "effective_until": "2026-08-29",
                "methods": ["auction", "after_hours", "block"],
                "evidence": [coverage_hash],
            }
            for member in universe["members"][:3]
        ],
        "evidence": [
            {
                "artifact_hash": digest,
                "source_reference": reference,
                "release_at": "2026-08-28T08:00:00+00:00",
                "public_available_at": "2026-08-28T08:00:00+00:00",
            }
            for digest, reference in (
                (coverage_hash, "synthetic:complete-disjoint-amount-coverage"),
                (daily_hash, "synthetic:tushare-daily-amounts"),
                (block_hash, "synthetic:tushare-block-amounts"),
            )
        ],
        "days": [
            {
                "business_date": "2026-08-28",
                "members": [
                    {
                        "security_id": member["security_id"],
                        "ts_code": member["ts_code"],
                        "required_methods": ["auction", "after_hours", "block"],
                        "components": [
                            {
                                "methods": [method],
                                "state": "reported",
                                "artifact_hash": digest,
                                "field": field,
                                "unit": unit,
                            }
                            for method, digest, field, unit in (
                                ("auction", daily_hash, "amount", "thousand_yuan"),
                                ("after_hours", daily_hash, "ah_amount", "thousand_yuan"),
                                ("block", block_hash, "amount", "ten_thousand_yuan"),
                            )
                        ],
                    }
                    for member in universe["members"][:3]
                ],
            }
        ],
    }
    adapter = TushareContextAdapter("synthetic-token", transport=breadth_transport(quotes, []))
    return adapter, universe_hash, amount


def save_amount_breadth_review(paths: RuntimePaths, amount: dict[str, Any]) -> str:
    review_hash = save(
        paths,
        {
            "schema_version": "market-breadth-amount-inputs-review-v0001",
            "subject_hash": hashlib.sha256(encode(amount)).hexdigest(),
            "reviewer": "synthetic amount coverage reviewer",
            "reviewed_at": "2026-09-13T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    return save(paths, {**amount, "review_hash": review_hash})


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_includes_nonparticipating_member_turnover(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    amount_hash = save_amount_breadth_review(paths, amount)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=amount_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 1
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-full-pool-amount",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:amount-breadth",
        metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete and selection.selected_claim_ids == result.claim_ids
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_EQ_ADV_AMOUNT_SHARE",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(points) == 1 and points[0].selected_value == 32.5
    parents = evidence.source_claim_acquisitions_many(result.claim_ids)[result.claim_ids[0]]
    assert {parent.receipt.api_name for parent in parents} == {
        "breadth_amount_inputs",
        "breadth_universe",
        "trade_cal",
        "daily",
        "suspend_d",
    }
    for parent in parents:
        output = json.loads(parent.normalized)["amount_breadth"][0]
        assert (output["advancing_amount_yuan"], output["total_amount_yuan"]) == (
            "130000",
            "400000",
        )
        assert {m["ts_code"]: (m["state"], m["amount_yuan"]) for m in output["members"]} == {
            "600000.SH": ("advance", "130000"),
            "000001.SZ": ("decline", "230000"),
            "920001.BJ": ("first_day_reference_unproven", "40000"),
        }
        assert set(output["input_evidence"]) == {p["artifact_hash"] for p in amount["evidence"]}


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_reports_unknown_amount_outside_advances(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    old_hash = amount["days"][0]["members"][2]["components"][1]["artifact_hash"]
    original = json.loads((paths.artifacts / old_hash[:2] / old_hash).read_bytes())
    original["data"]["items"][2][3] = None
    new_hash = save(paths, original)
    for member in amount["days"][0]["members"]:
        for component in member["components"]:
            if component["artifact_hash"] == old_hash:
                component["artifact_hash"] = new_hash
    for proof in amount["evidence"]:
        if proof["artifact_hash"] == old_hash:
            proof["artifact_hash"] = new_hash
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=save_amount_breadth_review(paths, amount),
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 0 and result.claim_ids == ()
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-nonparticipating-amount-gap",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime.now(UTC),
        release_event_id="synthetic:amount-gap",
        metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run)
    assert not selection.complete and selection.selected_claim_ids == ()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == 5 and all(r.state == "validated" for r in receipts)
    output = json.loads(acquisitions.read_content(receipts[0].acquisition_id, "normalized"))[
        "amount_breadth"
    ][0]
    assert output["status"] == "unavailable:required_amount_unknown"
    assert output["advancing_amount_share"] is None and output["total_amount_yuan"] is None
    assert output["missing_amounts"] == [
        {
            "security_id": "ordinary-bj",
            "ts_code": "920001.BJ",
            "methods": ["after_hours"],
            "reason": "required_amount_unknown",
        }
    ]
    assert {m["ts_code"]: m["amount_yuan"] for m in output["members"]} == {
        "600000.SH": "130000",
        "000001.SZ": "230000",
        "920001.BJ": None,
    }


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("rule", ["effective", "missing", "future"])
def test_registered_amount_breadth_requires_effective_nonapplicability_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rule: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    rule_hash = save(
        paths,
        {
            "synthetic": True,
            "scope": "ordinary-bj after_hours not applicable",
            "effective_from": "2026-08-29" if rule == "future" else "2026-08-28",
        },
    )
    amount["evidence"].append(
        {
            "artifact_hash": rule_hash,
            "source_reference": "synthetic:exchange-applicability-rule",
            "release_at": "2026-08-28T08:00:00+00:00",
            "public_available_at": "2026-08-28T08:00:00+00:00",
        }
    )
    amount["days"][0]["members"][2]["components"][1] = {
        "methods": ["after_hours"],
        "state": "not_applicable",
        "rule": {
            "effective_from": "2026-08-29" if rule == "future" else "2026-08-28",
            "effective_until": None,
            "evidence": [] if rule == "missing" else [rule_hash],
        },
    }
    amount_hash = save_amount_breadth_review(paths, amount)

    def acquire() -> Any:
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=amount_hash,
            ),
            definition_version=manifest["metric_catalog_version"],
        )

    if rule != "effective":
        with pytest.raises(ValueError, match="breadth_amount_applicability"):
            acquire()
        assert (
            EvidenceRepository(paths.database).metric_series(
                "CN_EQ_ADV_AMOUNT_SHARE",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=manifest["metric_catalog_version"],
            )
            == ()
        )
        return
    result = acquire()
    points = EvidenceRepository(paths.database).metric_series(
        "CN_EQ_ADV_AMOUNT_SHARE",
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 1 and points[0].selected_value == 32.5
    parents = EvidenceRepository(paths.database).source_claim_acquisitions_many(result.claim_ids)[
        result.claim_ids[0]
    ]
    output = json.loads(parents[0].normalized)["amount_breadth"][0]
    bj = next(m for m in output["members"] if m["ts_code"] == "920001.BJ")
    assert bj["amount_yuan"] == "40000"
    assert bj["components"][1]["state"] == "not_applicable"
    assert bj["components"][1]["amount_yuan"] is None
    assert rule_hash in output["input_evidence"]


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("extra_methods", [["auction"], []])
def test_registered_amount_breadth_rejects_amount_without_unique_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], extra_methods: list[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    components = amount["days"][0]["members"][0]["components"]
    components.append({**components[0], "methods": extra_methods})
    with pytest.raises(ValueError, match="breadth_amount_coverage"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("zero_total", [True, False])
def test_registered_amount_breadth_distinguishes_zero_total_from_zero_advances(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], zero_total: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    _, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    codes = ("600000.SH", "000001.SZ", "920001.BJ")
    quotes = (
        []
        if zero_total
        else [
            {"ts_code": code, "trade_date": "20260828", "close": "9", "pre_close": "10", "vol": "1"}
            for code in codes
        ]
    )
    suspensions = (
        [
            {"ts_code": code, "trade_date": "20260828", "suspend_type": "S", "suspend_timing": ""}
            for code in codes
        ]
        if zero_total
        else []
    )
    if zero_total:
        for proof in amount["evidence"][1:]:
            old_hash = proof["artifact_hash"]
            original = json.loads((paths.artifacts / old_hash[:2] / old_hash).read_bytes())
            for row in original["data"]["items"]:
                row[2:] = ["0"] * len(row[2:])
            new_hash = save(paths, original)
            proof["artifact_hash"] = new_hash
            for member in amount["days"][0]["members"]:
                for component in member["components"]:
                    if component["artifact_hash"] == old_hash:
                        component["artifact_hash"] = new_hash
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, suspensions)
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=save_amount_breadth_review(paths, amount),
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-zero-amount",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:zero-amount",
        metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
        period="2026-08-28",
    )
    selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selection.complete is (not zero_total)
    assert result.observation_count == (0 if zero_total else 1)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert receipts and all(r.state == "validated" for r in receipts)
    output = json.loads(acquisitions.read_content(receipts[0].acquisition_id, "normalized"))[
        "amount_breadth"
    ][0]
    assert output["total_amount_yuan"] == ("0" if zero_total else "400000")
    assert output["advancing_amount_share"] == (None if zero_total else 0)
    assert output["status"] == ("unavailable:zero_total_amount" if zero_total else "available")
    assert output["missing_amounts"] == []


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("publication", ["future", "unknown", "date_only"])
def test_registered_amount_breadth_waits_for_amount_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], publication: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    proof = amount["evidence"][2]
    proof["release_at"] = None if publication != "future" else "2026-08-28T09:00:00+00:00"
    proof["public_available_at"] = {
        "future": "2026-08-28T09:00:00+00:00",
        "unknown": None,
        "date_only": "2026-08-28T16:00:00+00:00",
    }[publication]
    if publication == "date_only":
        proof["published_date"] = "2026-08-28"
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=save_amount_breadth_review(paths, amount),
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 1
    for target, cutoff, complete in (
        ("2026-08-28", datetime(2026, 8, 28, 8, tzinfo=UTC), False),
        ("2026-08-28", datetime(2026, 8, 28, 16, tzinfo=UTC), publication == "future"),
        ("2026-08-31", datetime(2026, 8, 31, 8, tzinfo=UTC), publication != "unknown"),
    ):
        run = RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date=target,
            client_request_id=f"synthetic-amount-publication-{cutoff.isoformat()}",
            model_version_id=manifest["model_version_id"],
            system_as_of=cutoff,
            release_event_id="synthetic:amount-publication",
            metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
            period="2026-08-28",
        )
        selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert selection.complete is complete
        assert set(selection.selected_claim_ids) == (set(result.claim_ids) if complete else set())
    points = EvidenceRepository(paths.database).metric_series(
        "CN_EQ_ADV_AMOUNT_SHARE",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(points) == 1 and points[0].selected_value == 32.5


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("damaged", ["amount", "coverage", "review"])
def test_registered_amount_breadth_rechecks_adopted_originals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], damaged: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    amount_hash = save_amount_breadth_review(paths, amount)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=amount_hash,
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic-amount-integrity",
        model_version_id=manifest["model_version_id"],
        system_as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
        release_event_id="synthetic:amount-integrity",
        metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
        period="2026-08-28",
    )
    original_selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert original_selection.complete and original_selection.selected_claim_ids == result.claim_ids
    packet = json.loads((paths.artifacts / amount_hash[:2] / amount_hash).read_bytes())
    digest = {
        "amount": amount["evidence"][1]["artifact_hash"],
        "coverage": amount["coverage_evidence"][0],
        "review": packet["review_hash"],
    }[damaged]
    path = paths.artifacts / digest[:2] / digest
    raw = path.read_bytes()
    try:
        path.write_bytes(b"damaged adopted amount input")
        selected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        assert not selected.complete and selected.selected_claim_ids == ()
    finally:
        path.write_bytes(raw)
    assert select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) == original_selection


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("repeated_delivery", [False, True])
def test_registered_amount_breadth_rejects_same_fact_under_different_methods(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], repeated_delivery: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    # Keep disjoint method labels, but point after_hours at the very same
    # original amount field already adopted for auction.
    amount["days"][0]["members"][0]["components"][1]["field"] = "amount"
    if repeated_delivery:
        # A repeated delivery can change response metadata/hash without changing
        # the source's security/day/field fact. Its stable source reference stays.
        proof = amount["evidence"][1]
        old_hash = proof["artifact_hash"]
        original = json.loads((paths.artifacts / old_hash[:2] / old_hash).read_bytes())
        original["synthetic_delivery"] = "second response for the same source fact"
        duplicate_hash = save(paths, original)
        amount["evidence"].append({**proof, "artifact_hash": duplicate_hash})
        amount["days"][0]["members"][0]["components"][1]["artifact_hash"] = duplicate_hash
    with pytest.raises(ValueError, match="breadth_amount_fact_duplicate"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_cannot_shrink_reviewed_complete_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    # The independent effective exchange rule and its original still require
    # after_hours. Removing both declarations on the member must not hide it.
    member = amount["days"][0]["members"][2]
    member["required_methods"].remove("after_hours")
    del member["components"][1]
    with pytest.raises(ValueError, match="breadth_amount_scope"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_ignores_unadopted_future_amount_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    _, _, amount = synthetic_amount_breadth_inputs(paths)
    universe = synthetic_breadth_universe(paths)
    universe["coverage_start"] = "2026-08-27"
    universe["evidence"][0]["release_at"] = "2026-08-27T08:00:00+00:00"
    universe["evidence"][0]["public_available_at"] = "2026-08-27T08:00:00+00:00"
    for day in ("2026-08-27", "2026-08-28"):
        proof_hash = save(paths, {"synthetic": True, "quote_publication_day": day})
        universe["publications"][day] = [proof_hash]
        universe["evidence"].append(
            {
                "artifact_hash": proof_hash,
                "source_reference": "synthetic:quotes:" + day,
                "release_at": day + "T08:00:00+00:00",
                "public_available_at": day + "T08:00:00+00:00",
            }
        )
    universe_hash = save_breadth_review(paths, universe)
    amount["coverage_start"] = "2026-08-27"
    old_coverage = amount["coverage_evidence"][0]
    coverage = json.loads((paths.artifacts / old_coverage[:2] / old_coverage).read_bytes())
    coverage["effective_from"] = "2026-08-27"
    coverage_hash = save(paths, coverage)
    amount["coverage_evidence"] = [coverage_hash]
    amount["evidence"][0].update(
        artifact_hash=coverage_hash,
        release_at="2026-08-27T08:00:00+00:00",
        public_available_at="2026-08-27T08:00:00+00:00",
    )
    for rule in amount["coverage_rules"]:
        rule["effective_from"] = "2026-08-27"
        rule["evidence"] = [coverage_hash]
    earlier = json.loads(encode(amount["days"][0]))
    earlier["business_date"] = "2026-08-27"
    for proof in tuple(amount["evidence"][1:]):
        later_hash = proof["artifact_hash"]
        original = json.loads((paths.artifacts / later_hash[:2] / later_hash).read_bytes())
        for row in original["data"]["items"]:
            row[1] = "20260827"
        earlier_hash = save(paths, original)
        amount["evidence"].append(
            {
                **proof,
                "artifact_hash": earlier_hash,
                "release_at": "2026-08-27T08:00:00+00:00",
                "public_available_at": "2026-08-27T08:00:00+00:00",
            }
        )
        for member in earlier["members"]:
            for component in member["components"]:
                if component["artifact_hash"] == later_hash:
                    component["artifact_hash"] = earlier_hash
    amount["days"].insert(0, earlier)
    quotes = [
        {"ts_code": code, "trade_date": day, "close": close, "pre_close": "10", "vol": "1"}
        for day in ("20260827", "20260828")
        for code, close in (("600000.SH", "11"), ("000001.SZ", "9"), ("920001.BJ", "10"))
    ]
    adapter = TushareContextAdapter(
        "synthetic-token", transport=breadth_transport(quotes, [], days=("20260827", "20260828"))
    )
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.market_breadth(
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=save_amount_breadth_review(paths, amount),
        ),
        definition_version=manifest["metric_catalog_version"],
    )
    assert result.observation_count == 2
    runs = tuple(
        RunRepository(paths.database).submit(
            command_type="targeted_refresh",
            target_business_date=f"2026-08-{day}",
            client_request_id=f"synthetic-amount-parent-{day}",
            model_version_id=manifest["model_version_id"],
            system_as_of=datetime(2026, 8, day, 8, tzinfo=UTC),
            release_event_id="synthetic:amount-parent",
            metric_ids=("CN_EQ_ADV_AMOUNT_SHARE",),
            period=f"2026-08-{day}",
        )
        for day in (27, 28)
    )
    initial = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
    assert all(selected.complete and len(selected.selected_claim_ids) == 1 for selected in initial)
    later_hash = amount["days"][1]["members"][0]["components"][0]["artifact_hash"]
    artifact = paths.artifacts / later_hash[:2] / later_hash
    raw = artifact.read_bytes()
    try:
        artifact.write_bytes(b"damaged independent next day amount original")
        after = tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs)
        assert tuple(selected.complete for selected in after) == (True, False)
        assert after[0] == initial[0]
        assert after[1].selected_claim_ids == ()
    finally:
        artifact.write_bytes(raw)
    assert (
        tuple(select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC) for run in runs) == initial
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("precision", ["timestamp", "date_only"])
def test_registered_amount_breadth_rejects_publication_before_amount_day(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], precision: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    proof = amount["evidence"][2]
    proof["release_at"] = "2026-08-27T08:00:00+00:00" if precision == "timestamp" else None
    proof["public_available_at"] = (
        "2026-08-27T08:00:00+00:00" if precision == "timestamp" else "2026-08-27T16:00:00+00:00"
    )
    if precision == "date_only":
        proof["published_date"] = "2026-08-27"
    with pytest.raises(ValueError, match="breadth_amount_publication_precedes_period"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_public_replay_rechecks_candidate_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifests, original_hashes = {}, {}
    for side in ("comparison", "candidate"):
        manifest = admitted_amount_breadth_manifest(paths, capsys, side=side)
        manifest.pop("source_certification_packages")
        manifests[side] = manifest
        adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
        old_hash = amount["evidence"][1]["artifact_hash"]
        original = json.loads((paths.artifacts / old_hash[:2] / old_hash).read_bytes())
        original["synthetic_side"] = side
        digest = save(paths, original)
        amount["evidence"][1]["artifact_hash"] = digest
        for member in amount["days"][0]["members"]:
            for component in member["components"]:
                if component["artifact_hash"] == old_hash:
                    component["artifact_hash"] = digest
        original_hashes[side] = digest
        amount_hash = save_amount_breadth_review(paths, amount)

        def retrieve(
            adapter: TushareContextAdapter = adapter,
            universe_hash: str = universe_hash,
            amount_hash: str = amount_hash,
        ) -> tuple[ContextScalar, ...]:
            return adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=amount_hash,
            )

        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
    before = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert before.evaluated_cutoffs == 1 and not before.gaps, before.gaps
    assert original_hashes["candidate"] != original_hashes["comparison"]
    digest = original_hashes["candidate"]
    artifact = paths.artifacts / digest[:2] / digest
    raw = artifact.read_bytes()
    try:
        artifact.write_bytes(b"damaged candidate amount original")
        after = evaluate_context_replay(
            paths.database,
            manifests["candidate"],
            manifests["comparison"],
            requested_start="2026-08-28",
            requested_end="2026-08-28",
        )
        assert "candidate_context_selection_invalid:CN_EQ_ADV_AMOUNT_SHARE" in after.gaps
        assert not any(gap.startswith("comparison_") for gap in after.gaps)
    finally:
        artifact.write_bytes(raw)
    restored = evaluate_context_replay(
        paths.database,
        manifests["candidate"],
        manifests["comparison"],
        requested_start="2026-08-28",
        requested_end="2026-08-28",
    )
    assert restored.evaluated_cutoffs == 1 and not restored.gaps, restored.gaps


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_rejects_duplicate_original_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    old_hash = amount["evidence"][1]["artifact_hash"]
    original = json.loads((paths.artifacts / old_hash[:2] / old_hash).read_bytes())
    original["data"]["items"].append(original["data"]["items"][0][:])
    new_hash = save(paths, original)
    amount["evidence"][1]["artifact_hash"] = new_hash
    for member in amount["days"][0]["members"]:
        for component in member["components"]:
            if component["artifact_hash"] == old_hash:
                component["artifact_hash"] = new_hash
    with pytest.raises(ValueError, match="breadth_amount_fact_ambiguous"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_rejects_changed_scalar_before_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    amount_hash = save_amount_breadth_review(paths, amount)

    def retrieve() -> tuple[ContextScalar, ...]:
        scalars = adapter.market_breadth(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            universe_hash=universe_hash,
            amount_inputs_hash=amount_hash,
        )
        return (replace(scalars[0], value=99.0),)

    with pytest.raises(ValueError, match="breadth_amount_scalar_values_mismatch"):
        adapter.acquire_scalars(
            paths, retrieve, definition_version=manifest["metric_catalog_version"]
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == 5 and all(
        r.state == "failed" and r.validated_at is None for r in receipts
    )
    assert all(acquisitions.read_content(r.acquisition_id, "raw") for r in receipts)
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_registered_amount_breadth_rejects_legacy_definition_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(
        paths, capsys, source_code="tushare:daily:breadth-v0001"
    )
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    with pytest.raises(ValueError, match="registered_amount_breadth_source_contract_unsupported"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert len(receipts) == 5 and all(
        r.state == "failed" and r.validated_at is None for r in receipts
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("defect", ["unit", "missing_member", "wrong_security"])
def test_registered_amount_breadth_rejects_incompatible_input_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], defect: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = admitted_amount_breadth_manifest(paths, capsys)
    adapter, universe_hash, amount = synthetic_amount_breadth_inputs(paths)
    members = amount["days"][0]["members"]
    if defect == "unit":
        members[0]["components"][0]["unit"] = "unverified_yuan_multiplier"
    elif defect == "missing_member":
        members.pop()
    else:
        members[0]["ts_code"] = "600001.SH"
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_breadth(
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 28),
                universe_hash=universe_hash,
                amount_inputs_hash=save_amount_breadth_review(paths, amount),
            ),
            definition_version=manifest["metric_catalog_version"],
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" and r.validated_at is None for r in receipts)
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_EQ_ADV_AMOUNT_SHARE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        == ()
    )
