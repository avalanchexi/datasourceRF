"""Phase two #12: a full run finds second-quarter GDP two pages back on the NBS listing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.official_context import FetchedOfficialContextDocument
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.fixtures.model_registration import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
LISTING = "https://www.stats.gov.cn/sj/zxfb/"
ARTICLE = LISTING + "202607/t20260716_1964142.html"


@pytest.mark.usefixtures("runtime_clock")
def test_full_run_follows_the_nbs_listing_back_to_the_gdp_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    definition = next(
        item for item in request["manifest"]["metric_definitions"] if item["metric_id"] == "CN_GDP"
    )
    definition["source_candidates"] = [LISTING]
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"]["CN_GDP"] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    documents = {
        LISTING: FIXTURES / "official_listing" / "nbs_zxfb_index.html",
        LISTING + "index_1.html": FIXTURES / "official_listing" / "nbs_zxfb_index_1.html",
        LISTING + "index_2.html": FIXTURES / "official_listing" / "nbs_zxfb_index_2.html",
        ARTICLE: FIXTURES / "official_period_fallback" / "nbs_gdp.html",
    }
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents:
            raise OSError("fixture_official_page_unavailable")
        return FetchedOfficialContextDocument(documents[url].read_bytes(), "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-10",
        client_request_id="gdp-listing-pages",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")

    FullRunRetrieval(paths).retrieve(run)

    assert ARTICLE in requested
    points = [
        point
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_GDP",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=request["manifest"]["metric_catalog_version"],
        )
        if point.period_end == "2026-06-30"
    ]
    assert len(points) == 8
    reads = [
        (r.api_name, r.parameters["source_url"], r.state)
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "nbs_gdp" and r.parameters["period"] == "2026-Q2"
    ]
    assert reads == [
        ("official_listing_get", LISTING, "validated"),
        ("official_listing_get", LISTING + "index_1.html", "validated"),
        ("official_listing_get", LISTING + "index_2.html", "validated"),
        ("official_http_get", ARTICLE, "validated"),
    ]
    # A two-year-old history quarter is not on the recent pages: read once, not found.
    history = [
        r.parameters["source_url"]
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "nbs_gdp" and r.parameters["period"] == "2024-Q2"
    ]
    assert history == [LISTING]
