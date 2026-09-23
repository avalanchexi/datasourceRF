"""Official fallback during a full run's public acquisition phase.

The candidate admission uses synthetic review material; no real source is certified.
Worker publication and activation are verified by the isolated lifecycle tests separately.
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
    ingest_official_context_document,
)
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter
from tests.fixtures.delivery_assertions import assert_delivered_points, assert_delivered_rows
from tests.fixtures.model_registration import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "source_state",
    [
        "absent",
        "previous_official",
        "current_tushare",
        "not_released",
        "current_tushare_with_time",
        "current_tushare_corrupt",
    ],
)
def test_full_acquisition_discovers_missing_ppi_from_registered_official_listing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source_state: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    article = listing + "202609/t20260909_1965262.html"
    definition = next(
        item for item in request["manifest"]["metric_definitions"] if item["metric_id"] == "CN_PPI"
    )
    definition["source_candidates"] = [listing]
    definition["source_codes"] = [
        *definition["source_codes"],
        "tushare:cn_ppi:official-sampled-v0001",
    ]
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"]["CN_PPI"] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    requested: list[str] = []
    documents = {
        listing: f'<a href="{article}">2026年8月份工业生产者出厂价格</a>'.encode(),
        article: (
            Path(__file__).parents[1] / "fixtures/official_period_fallback/nbs_ppi.html"
        ).read_bytes(),
    }
    if source_state in {"previous_official", "not_released"}:
        # Synthetic July vintage: explicit rewritten dates, not an official historical claim.
        prior = documents[article].replace("2026年8月".encode(), "2026年7月".encode())
        prior = prior.replace(b"2026/09/09", b"2026/08/09")
        ingest_official_context_document(
            paths,
            prior,
            family="nbs_ppi",
            source_url=listing + "202608/synthetic-july.html",
            expected_period="2026-07",
            fetched_at=datetime.now(UTC),
            definition_version=definition["definition_version"],
        )
    if source_state == "not_released":
        documents[listing] = b"<html><body>No August release yet</body></html>"
    if source_state.startswith("current_tushare"):

        def transport(payload: dict) -> bytes:
            fields = payload["fields"].split(",")
            items = [] if payload["api_name"] == "cn_cpi" else [["202608", *([9.0] * 9)]]
            return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

        adapter = TushareContextAdapter("fixture-only", transport=transport)

        def delivered_scalars():
            scalars = adapter.prices(start_month="2026-08", end_month="2026-08")
            if not source_state.startswith("current_tushare_with_time"):
                return scalars
            # Normalized timestamps without independent source evidence must be rejected.
            published = datetime(2026, 9, 9, 1, 30, tzinfo=UTC)
            return tuple(
                replace(scalar, release_at=published, public_available_at=published)
                for scalar in scalars
            )

        if source_state == "current_tushare_with_time":
            with pytest.raises(ValueError, match="registered_ppi_publication_evidence_required"):
                adapter.acquire_scalars(
                    paths, delivered_scalars, definition_version=definition["definition_version"]
                )
            return
        adapter.acquire_scalars(
            paths, delivered_scalars, definition_version=definition["definition_version"]
        )
        if source_state.endswith("_corrupt"):
            receipt = next(
                r
                for r in AcquisitionRepository(paths.database, paths.artifacts).history()
                if r.api_name == "cn_ppi"
            )
            assert receipt.raw_hash is not None
            (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents:
            raise OSError("unrelated fixture source unavailable")
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-11",
        client_request_id="registered-ppi-acquisition",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")

    FullRunRetrieval(paths).retrieve(run)

    if source_state == "not_released":
        frozen = runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))
        FullRunRetrieval(paths).evaluate(frozen)
        requirements = runs.full_retrieval_plan(run.run_id)["final"]["requirements"]
        assert {item["period"] for item in requirements if item["metric_id"] == "CN_PPI"} == {
            "2026-07"
        }
        assert article not in requested
        return
    if source_state.startswith("current_tushare"):
        # This ticket does not compare values or repair unknown historical publication times.
        assert article not in requested
        assert not any(
            item["metric_ids"] == ["CN_PPI"] and item["api_name"] == "official_http_get"
            for item in runs.full_retrieval_plan(run.run_id)["acquisitions"]
        )
        from pring_cycle.official_context import official_claims_matching_acquisitions

        evidence = EvidenceRepository(paths.database)
        points = tuple(
            evidence.metric_series(
                "CN_PPI",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=definition["definition_version"],
            )
        )
        valid = official_claims_matching_acquisitions(
            evidence, {"CN_PPI": points}, definition_version=definition["definition_version"]
        )
        assert len(valid) == (0 if source_state.endswith("_corrupt") else 9)
        assert len(points) == 9
        assert_delivered_points(points, "tushare")
        assert all(claim.parsed_public_available_at is None for p in points for claim in p.claims)
        return
    assert article in requested
    initial = runs.full_retrieval_plan(run.run_id)["initial"]
    scope = next(item for item in initial["scopes"] if item["metric_ids"] == ["CN_PPI"])
    assert scope["period"] == "2026-08"
    assert scope["source_url"] == listing
    # The freshness registry says August's PPI was out by the target (ticket 19).
    assert scope["release_status"] == "released"
    series = EvidenceRepository(paths.database).metric_series(
        "CN_PPI",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=definition["definition_version"],
    )
    points = [point for point in series if point.period_end == "2026-08-31"]
    assert len(points) == 9
    assert all(claim.certification_status == "certified" for p in points for claim in p.claims)
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("source_url") == article
    )
    assert all(
        claim.source_reference == f"{article}#sha256={receipt.raw_hash}"
        for point in points
        for claim in point.claims
    )
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    rows = [row for row in context.macro["price_chain"]["evidence"] if row["metric_id"] == "CN_PPI"]
    assert_delivered_points(points, "国家统计局")
    assert_delivered_rows(rows, "国家统计局")
