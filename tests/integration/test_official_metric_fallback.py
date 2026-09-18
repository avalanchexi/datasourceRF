"""Per-metric official fallback through public acquisition and projection boundaries.

Review packages and TuShare responses are synthetic; the NBS article is archived.
These tests exercise the full run's acquisition phase, not Worker activation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    official_claims_matching_acquisitions,
)
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter
from tests.fixtures.delivery_assertions import assert_certified_points, assert_certified_rows
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)


def admit_cpi_candidate(
    paths: RuntimePaths,
    capsys: pytest.CaptureFixture[str],
) -> tuple[str, str]:
    request, _ = prepared_request(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    for definition in request["manifest"]["metric_definitions"]:
        metric = definition["metric_id"]
        if metric not in {"CN_CPI_HEADLINE", "CN_CORE_CPI"}:
            continue
        definition["source_candidates"] = [listing]
        if metric == "CN_CPI_HEADLINE":
            definition["source_codes"] = [
                *definition["source_codes"],
                "tushare:cn_cpi:official-sampled-v0001",
            ]
        package["definition_bindings"][metric] = hashlib.sha256(encode(definition)).hexdigest()
        definition_version = definition["definition_version"]
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    return candidate, definition_version


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("headline_present", [True, False])
@pytest.mark.parametrize("official_available", [True, False])
def test_cpi_acquisition_falls_back_only_for_missing_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    headline_present: bool,
    official_available: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, definition_version = admit_cpi_candidate(paths, capsys)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    article = listing + "202609/t20260909_1965263.html"

    def transport(payload: dict) -> bytes:
        fields = payload["fields"].split(",")
        # Deliberately differs from NBS: fallback must not perform value reconciliation.
        items = (
            [["202608", 9.0, 9.0, 9.0]]
            if payload["api_name"] == "cn_cpi" and headline_present
            else []
        )
        return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def acquire():
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.prices(start_month="2026-08", end_month="2026-08"),
            definition_version=definition_version,
        )

    if headline_present:
        acquire()
    else:
        with pytest.raises(ValueError, match="tushare_context_observations_missing"):
            acquire()
    evidence = EvidenceRepository(paths.database)

    def series(metric: str):
        return tuple(
            evidence.metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=definition_version,
            )
        )

    before = series("CN_CPI_HEADLINE")
    assert len(before) == (3 if headline_present else 0)
    before_ids = {claim.claim_id for point in before for claim in point.claims}
    assert len(
        official_claims_matching_acquisitions(
            evidence, {"CN_CPI_HEADLINE": before}, definition_version=definition_version
        )
    ) == len(before)
    requested: list[str] = []
    documents = {
        listing: f'<a href="{article}">2026年8月份居民消费价格</a>'.encode(),
        article: (
            Path(__file__).parents[1] / "fixtures/official_period_fallback/nbs_core_cpi.html"
        ).read_bytes(),
    }

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents or (url == article and not official_available):
            raise OSError("unrelated fixture source unavailable")
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-11",
        client_request_id="cpi-metric-fallback",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)

    assert article in requested
    headline = series("CN_CPI_HEADLINE")
    if headline_present:
        assert {claim.claim_id for point in headline for claim in point.claims} == before_ids
        assert all(point.selected_value == 9.0 for point in headline)
        assert all(
            claim.public_available_at is None for point in headline for claim in point.claims
        )
    else:
        assert len(headline) == (3 if official_available else 0)
        assert all(point.selected_value != 9.0 for point in headline)
    if headline:
        assert_certified_points(headline, "tushare" if headline_present else "国家统计局")
    core = series("CN_CORE_CPI")
    if not official_available:
        assert core == ()
        attempt = evidence.latest_retrieval_attempt(
            "CN_CORE_CPI",
            period="2026-08",
            as_of=datetime.now(UTC),
            definition_version=definition_version,
        )
        assert attempt is not None and attempt.outcome == "source_failed"
        assert attempt.safe_metadata["error_type"] == "OSError"
        ledger = RetrievalLedger(paths.database).for_run(run.run_id)
        assert ledger is not None
        article_acquisitions = {
            item.acquisition_id
            for item in AcquisitionRepository(paths.database, paths.artifacts).history()
            if item.parameters.get("source_url") == article
        }
        official_attempts = [
            attempt
            for attempt in ledger["requests"]
            if attempt["acquisition_id"] in article_acquisitions
        ]
        assert official_attempts and all(
            attempt["outcome"] == "failed"
            and attempt["classification"] == "transient_transport_error"
            for attempt in official_attempts
        )
        frozen = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
        FullRunRetrieval(paths).evaluate(frozen)
        gaps = runs.full_retrieval_plan(run.run_id)["final"]["gaps"]
        missing_core = [gap for gap in gaps if gap["metric_id"] == "CN_CORE_CPI"]
        assert missing_core and all(not gap["complete"] for gap in missing_core)
        if not headline_present:
            missing_headline = [gap for gap in gaps if gap["metric_id"] == "CN_CPI_HEADLINE"]
            assert missing_headline and all(not gap["complete"] for gap in missing_headline)
        # Failure leaves an explicit gap; it never synthesizes an empty observation.
        return
    assert len(core) == 3
    assert_certified_points(core, "国家统计局")
    assert {point.dimensions["measure"]: point.selected_value for point in core} == {
        "mom": 0.1,
        "yoy": 1.0,
        "cumulative_average_yoy": 1.1,
    }
    assert (
        len(
            official_claims_matching_acquisitions(
                evidence, {"CN_CORE_CPI": core}, definition_version=definition_version
            )
        )
        == 3
    )
    receipt = next(
        item
        for item in AcquisitionRepository(paths.database, paths.artifacts).history()
        if item.parameters.get("source_url") == article
    )
    assert all(
        claim.source_reference == f"{article}#sha256={receipt.raw_hash}"
        for point in core
        for claim in point.claims
    )
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    headline_provider = "tushare" if headline_present else "国家统计局"
    for metric, provider in (("CN_CPI_HEADLINE", headline_provider), ("CN_CORE_CPI", "国家统计局")):
        rows = [
            row for row in context.macro["price_chain"]["evidence"] if row["metric_id"] == metric
        ]
        assert len(rows) == 3
        assert_certified_rows(rows, provider)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("invalid_delivery", ["publication_time", "raw_bytes"])
def test_cpi_delivery_requires_independent_raw_and_publication_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_delivery: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, definition_version = admit_cpi_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        fields = payload["fields"].split(",")
        items = [["202608", 9.0, 9.0, 9.0]] if payload["api_name"] == "cn_cpi" else []
        return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def scalars():
        result = adapter.prices(start_month="2026-08", end_month="2026-08")
        if invalid_delivery == "publication_time":
            published = datetime(2026, 9, 9, 1, 30, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in result
            )
        return result

    if invalid_delivery == "publication_time":
        with pytest.raises(ValueError, match="registered_cpi_publication_evidence_required"):
            adapter.acquire_scalars(paths, scalars, definition_version=definition_version)
        return
    adapter.acquire_scalars(paths, scalars, definition_version=definition_version)
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_CPI_HEADLINE",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=definition_version,
        )
    )
    assert len(points) == 3
    assert (
        len(
            official_claims_matching_acquisitions(
                evidence, {"CN_CPI_HEADLINE": points}, definition_version=definition_version
            )
        )
        == 3
    )
    receipt = next(
        item
        for item in AcquisitionRepository(paths.database, paths.artifacts).history()
        if item.api_name == "cn_cpi"
    )
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")
    assert not official_claims_matching_acquisitions(
        evidence, {"CN_CPI_HEADLINE": points}, definition_version=definition_version
    )
