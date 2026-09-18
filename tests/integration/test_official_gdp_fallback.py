"""GDP keeps nominal cumulative delivery separate from disputed growth fields."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval, read_full_retrieval_plan
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    ingest_official_context_document,
    official_claims_matching_acquisitions,
    refresh_official_context_document,
)
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RetrievalScope, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.tushare_context import TushareContextAdapter, ingest_context_scalars
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)

LISTING = "https://www.stats.gov.cn/sj/zxfb/"
ARTICLE = "https://www.stats.gov.cn/sj/zxfb/202607/t20260716_1964142.html"
Q2_TITLE = "2026年二季度和上半年国内生产总值初步核算结果"
FIELDS = ("quarter", "gdp", "gdp_yoy", "pi", "pi_yoy", "si", "si_yoy", "ti", "ti_yoy")


def admit_gdp_candidate(paths: RuntimePaths, capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    request, _ = prepared_request(paths)
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    for definition in request["manifest"]["metric_definitions"]:
        if definition["metric_id"] != "CN_GDP":
            continue
        # This reviewed fixture contract is isolated from actual source certification.
        definition["certification_status"] = "certified"
        definition["source_candidates"] = [LISTING]
        definition["source_codes"] = [
            *definition["source_codes"],
            "tushare:cn_gdp:official-sampled-v0001",
        ]
        package["definition_bindings"]["CN_GDP"] = hashlib.sha256(encode(definition)).hexdigest()
        version = definition["definition_version"]
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    return json.loads(capsys.readouterr().out)["model_version_id"], version


def delivery(payload: dict) -> bytes:
    assert payload["api_name"] == "cn_gdp"
    assert payload["fields"] == ",".join(FIELDS)
    return json.dumps(
        {
            "code": 0,
            "data": {
                "fields": FIELDS,
                "items": [["2026Q2", 690000.0, 4.6, 31000.0, 3.5, 250000.0, 3.8, 409000.0, 5.2]],
            },
        }
    ).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_gdp_delivery_keeps_cumulative_levels_and_audits_disputed_growth(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)
    adapter = TushareContextAdapter("fixture-only", transport=delivery)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
        definition_version=version,
    )
    assert result.rejected_field_count == 4
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert {
        p.dimensions["aggregate"]: (p.period_start, p.period_end, p.selected_value) for p in points
    } == {
        "total": ("2026-01-01", "2026-06-30", 690000.0),
        "primary": ("2026-01-01", "2026-06-30", 31000.0),
        "secondary": ("2026-01-01", "2026-06-30", 250000.0),
        "tertiary": ("2026-01-01", "2026-06-30", 409000.0),
    }
    assert all(p.dimensions["measure"] == "nominal_ytd_level" for p in points)
    assert all(c.unit == "hundred_million_cny" for p in points for c in p.claims)
    assert official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    ) == {p.selected_claim_id for p in points}
    assert not evidence.metric_series(
        "CN_GDP", mode=AsOfMode.PUBLIC, as_of=datetime.now(UTC), definition_version=version
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(r for r in acquisitions.history() if r.api_name == "cn_gdp")
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert {r["period_kind"] for r in normalized["accepted_scalars"]} == {"year_to_quarter"}
    assert {r["source_field"] for r in normalized["rejected_fields"]} == {
        "gdp_yoy",
        "pi_yoy",
        "si_yoy",
        "ti_yoy",
    }
    assert all(
        r["reason"] == "gdp_yoy_period_semantics_unverified" for r in normalized["rejected_fields"]
    )


@pytest.mark.usefixtures("runtime_clock")
def test_gdp_batch_links_each_quarter_and_rejection_to_its_physical_response(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        response = json.loads(delivery(payload))
        if payload["params"]["start_q"] == "2026Q1":
            response["data"]["items"] = [
                ["2026Q1", 330000, 4.8, 11000, 3.5, 118000, 4.4, 201000, 5.2]
            ]
        return json.dumps(response).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)
    result = adapter.acquire_scalars(
        paths,
        lambda: (
            *adapter.gdp(start_quarter="2026Q1", end_quarter="2026Q1"),
            *adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
        ),
        definition_version=version,
    )
    assert result.observation_count == 8 and result.rejected_field_count == 8
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    ) == set(result.claim_ids)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for receipt in acquisitions.history():
        if receipt.api_name != "cn_gdp":
            continue
        normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
        assert len(normalized["accepted_scalars"]) == len(normalized["rejected_fields"]) == 4
        end = "2026-03-31" if receipt.parameters["start_q"] == "2026Q1" else "2026-06-30"
        assert {r["period_end"] for r in normalized["accepted_scalars"]} == {end}
        assert {r["period_end"] for r in normalized["rejected_fields"]} == {end}
        assert all(
            r["acquisition_ids"] == [receipt.acquisition_id] for r in normalized["accepted_scalars"]
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("delivered", [False, True])
@pytest.mark.parametrize("official_state", ["available", "transport_failed", "no_matching_period"])
def test_gdp_fallback_respects_delivered_period_without_loosening_required_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    delivered: bool,
    official_state: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_gdp_candidate(paths, capsys)
    evidence = EvidenceRepository(paths.database)

    def transport(payload: dict) -> bytes:
        response = json.loads(delivery(payload))
        if not delivered:
            response["data"]["items"] = []
        return json.dumps(response).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def acquire():
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
            definition_version=version,
        )

    if delivered:
        acquire()
    else:
        with pytest.raises(ValueError, match="tushare_context_observations_missing"):
            acquire()

    def series():
        return tuple(
            evidence.metric_series(
                "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
        )

    before = series()
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url == LISTING:
            content = (
                b"<p>No matching release in this fixture</p>"
                if official_state == "no_matching_period"
                else f'<a href="{ARTICLE}">{Q2_TITLE}</a>'.encode()
            )
        elif url == ARTICLE and official_state != "transport_failed":
            content = (
                Path(__file__).parents[1] / "fixtures/official_period_fallback/nbs_gdp.html"
            ).read_bytes()
        else:
            raise OSError("unrelated fixture unavailable")
        return FetchedOfficialContextDocument(content, "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="gdp-fallback",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    assert (ARTICLE in requested) == (not delivered and official_state != "no_matching_period")
    points = series()
    if delivered:
        assert {p.selected_claim_id for p in points} == {p.selected_claim_id for p in before}
        assert len(points) == 4
    elif official_state == "available":
        assert {
            (p.dimensions["aggregate"], p.dimensions["measure"]): p.selected_value for p in points
        } == {
            ("total", "nominal_ytd_level"): 695704.0,
            ("primary", "nominal_ytd_level"): 31522.0,
            ("secondary", "nominal_ytd_level"): 250473.0,
            ("tertiary", "nominal_ytd_level"): 413709.0,
            ("total", "real_quarter_yoy"): 4.3,
            ("primary", "real_quarter_yoy"): 3.7,
            ("secondary", "real_quarter_yoy"): 3.0,
            ("tertiary", "real_quarter_yoy"): 5.1,
        }
        assert all(p.period_end == "2026-06-30" for p in points)
        assert all(
            p.period_start
            == ("2026-01-01" if p.dimensions["measure"] == "nominal_ytd_level" else "2026-04-01")
            for p in points
        )
    else:
        assert points == ()
        transport_failed = official_state == "transport_failed"
        attempt = evidence.latest_retrieval_attempt(
            "CN_GDP", period="2026-Q2", as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None
        assert attempt.outcome == ("source_failed" if transport_failed else "validation_failed")
        acquired = {
            r.acquisition_id
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.parameters.get("source_url") == (ARTICLE if transport_failed else LISTING)
            and r.parameters.get("period") == "2026-Q2"
        }
        ledger = RetrievalLedger(paths.database).for_run(run.run_id)
        assert ledger is not None
        physical = [r for r in ledger["requests"] if r["acquisition_id"] in acquired]
        assert physical and all(
            r["outcome"] == "failed"
            and r["classification"]
            == ("transient_transport_error" if transport_failed else "semantic_validation_failed")
            for r in physical
        )
    assert official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    ) == {p.selected_claim_id for p in points}
    selection = ModelInputSelector(paths, run).select(
        RetrievalScope("gdp-quarter", ("CN_GDP",), "2026-Q2", "P2", LISTING)
    )
    assert selection.complete == (not delivered and official_state == "available")
    if delivered:
        # The historical target still requires publication evidence. A SYSTEM row
        # prevents freshness fallback but does not supply missing PUBLIC eligibility.
        assert selection.selected_claim_ids == ()
        assert len(selection.missing_members) == 8
        assert sum("real_quarter_yoy" in member for member in selection.missing_members) == 4
    else:
        assert set(selection.selected_claim_ids) == {p.selected_claim_id for p in points}
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    rows = [r for r in context.macro["international_context"] if r["metric_id"] == "CN_GDP"]
    if not points:
        assert len(rows) == 1 and rows[0]["value"] is None and rows[0]["claims"] == []
        return
    assert len(rows) == len(points)
    provider = "tushare" if delivered else "国家统计局"
    assert all(c["provider"] == provider for r in rows for c in r["claims"] if c["selected"])


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "period,title,url,filename,end",
    [
        (
            "2026-Q1",
            "2026年一季度国内生产总值初步核算结果",
            "https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html",
            "nbs_gdp_q1.html",
            "2026-03-31",
        ),
        (
            "2025-Q3",
            "2025年三季度国内生产总值初步核算结果",
            "https://www.stats.gov.cn/sj/zxfb/202510/t20251021_1961646.html",
            "nbs_gdp_q3.html",
            "2025-09-30",
        ),
        (
            "2025-Q4",
            "2025年四季度和全年国内生产总值初步核算结果",
            "https://www.stats.gov.cn/sj/zxfb/202601/t20260120_1962349.html",
            "nbs_gdp_q4.html",
            "2025-12-31",
        ),
    ],
)
def test_gdp_listing_accepts_each_archived_quarter_title(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    period: str,
    title: str,
    url: str,
    filename: str,
    end: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)
    raw = (Path(__file__).parents[1] / "fixtures/official_period_fallback" / filename).read_bytes()

    def fetch(source_url: str) -> FetchedOfficialContextDocument:
        assert source_url in {LISTING, url}
        content = f'<a href="{url}">{title}</a>'.encode() if source_url == LISTING else raw
        return FetchedOfficialContextDocument(content, "text/html", source_url, 200)

    refreshed = refresh_official_context_document(
        paths,
        family="nbs_gdp",
        source_url=LISTING,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert len(points) == 8 and {p.period_end for p in points} == {end}
    assert official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    ) == set(refreshed.claim_ids)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("new_release_available", [False, True])
def test_gdp_discovers_next_completed_quarter_without_making_unpublished_values_required(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    new_release_available: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_gdp_candidate(paths, capsys)
    fixture_root = Path(__file__).parents[1] / "fixtures/official_period_fallback"
    q1 = ingest_official_context_document(
        paths,
        (fixture_root / "nbs_gdp_q1.html").read_bytes(),
        family="nbs_gdp",
        source_url="https://www.stats.gov.cn/sj/zxfb/202604/t20260417_1963336.html",
        expected_period="2026-Q1",
        fetched_at=datetime.now(UTC),
        definition_version=version,
    )

    def fetch(url: str) -> FetchedOfficialContextDocument:
        if url == LISTING:
            content = (
                f'<a href="{ARTICLE}">2026年二季度和上半年国内生产总值初步核算结果</a>'.encode()
                if new_release_available
                else b"<p>No matching release in this fixture</p>"
            )
        elif url == ARTICLE and new_release_available:
            content = (fixture_root / "nbs_gdp.html").read_bytes()
        else:
            raise OSError("unrelated fixture unavailable")
        return FetchedOfficialContextDocument(content, "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="gdp-new-quarter",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    plan = read_full_retrieval_plan(paths.database, run.run_id)
    assert any(
        s["period"] == "2026-Q2" and "CN_GDP" in s["metric_ids"] for s in plan["initial"]["scopes"]
    )
    assert not any(
        r.get("period") == "2026-Q2" and r["metric_id"] == "CN_GDP"
        for r in plan["initial"]["requirements"]
    )
    points = EvidenceRepository(paths.database).metric_series(
        "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert {p.selected_claim_id for p in points if p.period_end == "2026-03-31"} == set(
        q1.claim_ids
    )
    assert len([p for p in points if p.period_end == "2026-06-30"]) == (
        8 if new_release_available else 0
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("rejection_audit", ["intact", "omitted", "relabelled"])
def test_gdp_adoption_rechecks_rejected_fields_even_with_valid_artifact_hashes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    rejection_audit: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)
    raw = delivery({"api_name": "cn_gdp", "fields": ",".join(FIELDS)})
    adapter = TushareContextAdapter("fixture-only", transport=lambda _: raw)
    parsed = adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2")
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    acquired = acquisitions.capture(
        provider="tushare",
        api_name="cn_gdp",
        parameters={"start_q": "2026Q2", "end_q": "2026Q2"},
        fields=",".join(FIELDS),
        parser_version="tushare-gdp-parser-v0003",
        fetch=lambda: raw,
        parse=lambda content: json.loads(content),
        normalize=lambda d: d,
        defer_validation=True,
    )
    linked = tuple(replace(s, acquisition_ids=(acquired.receipt.acquisition_id,)) for s in parsed)
    rejected = [
        {
            "metric_id": "CN_GDP",
            "api_name": "cn_gdp",
            "source_field": field,
            "period_end": "2026-06-30",
            "reason": "gdp_yoy_period_semantics_unverified",
        }
        for field in ("gdp_yoy", "pi_yoy", "si_yoy", "ti_yoy")
    ]
    if rejection_audit == "omitted":
        rejected = []
    elif rejection_audit == "relabelled":
        rejected[0]["reason"] = "already_certified_real_quarter_growth"
    acquisitions.complete_validation(
        acquired.receipt.acquisition_id,
        {
            "accepted_scalars": [asdict(s) for s in linked],
            "rejected_fields": rejected,
        },
    )
    result = ingest_context_scalars(
        paths,
        linked,
        fetched_at=datetime.now(UTC),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    matched = official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    )
    assert matched == (set(result.claim_ids) if rejection_audit == "intact" else set())


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("invalid_delivery", ["raw_bytes", "normalized_level", "publication_time"])
def test_gdp_rejects_changed_originals_or_unproven_values_and_publication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_delivery: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)
    adapter = TushareContextAdapter("fixture-only", transport=delivery)

    def scalars():
        parsed = adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2")
        if invalid_delivery == "publication_time":
            published = datetime(2026, 7, 16, 1, 30, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in parsed
            )
        if invalid_delivery == "normalized_level":
            return tuple(replace(s, value=1.0) if s.source_field == "pi" else s for s in parsed)
        return parsed

    if invalid_delivery == "publication_time":
        with pytest.raises(ValueError, match="registered_gdp_publication_evidence_required"):
            adapter.acquire_scalars(paths, scalars, definition_version=version)
        return
    adapter.acquire_scalars(paths, scalars, definition_version=version)
    evidence = EvidenceRepository(paths.database)
    # Even an unchanged total cannot use a delivery with another forged normalized member.
    points = tuple(
        p
        for p in evidence.metric_series(
            "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
        if p.dimensions["aggregate"] == "total"
    )
    assert len(points) == 1
    if invalid_delivery == "raw_bytes":
        assert official_claims_matching_acquisitions(
            evidence, {"CN_GDP": points}, definition_version=version
        ) == {points[0].selected_claim_id}
        receipt = next(
            r
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.api_name == "cn_gdp"
        )
        assert receipt.raw_hash is not None
        (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")
    assert not official_claims_matching_acquisitions(
        evidence, {"CN_GDP": points}, definition_version=version
    )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("period", ["2026-Q5", "2026-Q2-extra"])
def test_invalid_gdp_quarter_retains_a_classified_failure_and_original(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    period: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_gdp_candidate(paths, capsys)
    content = f'<a href="{ARTICLE}">{Q2_TITLE}</a>'.encode()
    with pytest.raises(ValueError, match="official_context_period_invalid"):
        refresh_official_context_document(
            paths,
            family="nbs_gdp",
            source_url=LISTING,
            expected_period=period,
            fetched_at=datetime.now(UTC),
            definition_version=version,
            fetcher=lambda url: FetchedOfficialContextDocument(content, "text/html", url, 200),
        )
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        "CN_GDP", period=period, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "validation_failed"
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed" and receipt.error_type == "ValueError"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == content
    assert not evidence.metric_series(
        "CN_GDP", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
