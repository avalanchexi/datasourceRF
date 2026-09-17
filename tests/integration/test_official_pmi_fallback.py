"""Synthetic reviewed PMI delivery, with archived official fallback through a full run's phase."""

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
from tests.models.test_candidate_admission import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)

PMI_FIELDS = {
    "CN_PMI_ACTIVITY": {"pmi010000", "pmi010400", "pmi010500", "pmi011100"},
    "CN_PMI_INVENTORY": {"pmi010700", "pmi011400"},
    "CN_PMI_PRICES": {"pmi011200", "pmi011300"},
}
OFFICIAL_VALUES = {
    "CN_PMI_ACTIVITY": {
        "manufacturing": 49.8,
        "production": 50.4,
        "new_orders": 50.6,
        "purchase_volume": 50.5,
    },
    "CN_PMI_INVENTORY": {"raw_materials": 48.1, "finished_goods": 48.4},
    "CN_PMI_PRICES": {"purchase_prices": 56.6, "output_prices": 50.4},
}


def admit_pmi_candidate(paths: RuntimePaths, capsys: pytest.CaptureFixture[str]) -> tuple[str, str]:
    request, _ = prepared_request(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    for definition in request["manifest"]["metric_definitions"]:
        metric = definition["metric_id"]
        if metric not in PMI_FIELDS:
            continue
        definition["source_candidates"] = [listing]
        definition["source_codes"] = [
            *definition["source_codes"],
            "tushare:cn_pmi:official-sampled-v0001",
        ]
        package["definition_bindings"][metric] = hashlib.sha256(encode(definition)).hexdigest()
        version = definition["definition_version"]
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    return candidate, version


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("missing_metric", [*PMI_FIELDS, "all", "none"])
@pytest.mark.parametrize("official_available", [True, False])
def test_pmi_official_fallback_preserves_other_delivered_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing_metric: str,
    official_available: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_pmi_candidate(paths, capsys)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    article = listing + "202608/t20260831_1965154.html"
    missing = set(PMI_FIELDS) if missing_metric == "all" else {missing_metric} & PMI_FIELDS.keys()
    missing_fields = {field for metric in missing for field in PMI_FIELDS[metric]}

    def transport(payload: dict) -> bytes:
        assert payload["api_name"] == "cn_pmi"
        fields = payload["fields"].split(",")
        values = [
            None if field in missing_fields else 80.0 + index
            for index, field in enumerate(fields[1:])
        ]
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [["202608", *values]]}}
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def acquire():
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="2026-08", end_month="2026-08"),
            definition_version=version,
        )

    if missing_metric == "all":
        with pytest.raises(ValueError, match="tushare_context_observations_missing"):
            acquire()
    else:
        acquire()
    evidence = EvidenceRepository(paths.database)

    def series():
        return {
            metric: tuple(
                evidence.metric_series(
                    metric,
                    mode=AsOfMode.SYSTEM,
                    as_of=datetime.now(UTC),
                    definition_version=version,
                )
            )
            for metric in PMI_FIELDS
        }

    before = series()
    delivered = {
        claim.claim_id for points in before.values() for point in points for claim in point.claims
    }
    assert (
        official_claims_matching_acquisitions(evidence, before, definition_version=version)
        == delivered
    )
    requested: list[str] = []
    documents = {
        listing: f'<a href="{article}">2026年8月中国采购经理指数运行情况</a>'.encode(),
        article: (
            Path(__file__).parents[1] / "fixtures/official_period_fallback/nbs_pmi.html"
        ).read_bytes(),
    }

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents or (url == article and not official_available):
            raise OSError("unrelated fixture unavailable")
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-11",
        client_request_id="pmi-metric-fallback",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)

    assert (article in requested) == bool(missing)
    if missing and not official_available:
        article_acquisitions = {
            receipt.acquisition_id
            for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
            if receipt.parameters.get("source_url") == article
        }
        ledger = RetrievalLedger(paths.database).for_run(run.run_id)
        assert ledger is not None
        attempts = [
            row for row in ledger["requests"] if row["acquisition_id"] in article_acquisitions
        ]
        assert attempts and all(
            row["outcome"] == "failed" and row["classification"] == "transient_transport_error"
            for row in attempts
        )
    after = series()
    for metric, points in after.items():
        if metric in missing:
            if not official_available:
                assert points == ()
                attempt = evidence.latest_retrieval_attempt(
                    metric, period="2026-08", as_of=datetime.now(UTC), definition_version=version
                )
                assert attempt is not None and attempt.outcome == "source_failed"
                assert attempt.safe_metadata["error_type"] == "OSError"
                continue
            assert {
                point.dimensions["series"]: point.selected_value for point in points
            } == OFFICIAL_VALUES[metric]
            assert all(claim.provider == "国家统计局" for point in points for claim in point.claims)
        else:
            assert {claim.claim_id for p in points for claim in p.claims} == {
                claim.claim_id for p in before[metric] for claim in p.claims
            }
            expected = {
                "CN_PMI_ACTIVITY": {
                    "manufacturing": 80.0,
                    "production": 81.0,
                    "new_orders": 82.0,
                    "purchase_volume": 84.0,
                },
                "CN_PMI_INVENTORY": {"raw_materials": 83.0, "finished_goods": 87.0},
                "CN_PMI_PRICES": {"purchase_prices": 85.0, "output_prices": 86.0},
            }
            assert {p.dimensions["series"]: p.selected_value for p in points} == expected[metric]
    expected_count = 8 if official_available else 8 - len(missing_fields)
    assert (
        len(official_claims_matching_acquisitions(evidence, after, definition_version=version))
        == expected_count
    )
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    groups = {
        "CN_PMI_ACTIVITY": context.macro["overheat"]["evidence"],
        "CN_PMI_PRICES": context.macro["price_chain"]["evidence"],
        "CN_PMI_INVENTORY": [
            row for card in context.inventory["cards"] for row in card["evidence"]
        ],
    }
    for metric, group in groups.items():
        if metric in missing and not official_available:
            continue
        rows = [row for row in group if row["metric_id"] == metric]
        assert len(rows) == len(PMI_FIELDS[metric])
        provider = "国家统计局" if metric in missing else "tushare"
        assert all(
            claim["provider"] == provider
            for row in rows
            for claim in row["claims"]
            if claim["selected"]
        )


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "invalid_delivery", ["raw_bytes", "sibling_normalized", "publication_time"]
)
def test_pmi_revalidation_checks_full_response_and_independent_publication(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalid_delivery: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_pmi_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        fields = payload["fields"].split(",")
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [["202608", *range(40, 48)]]}}
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def scalars():
        parsed = adapter.pmi(start_month="2026-08", end_month="2026-08")
        if invalid_delivery == "publication_time":
            published = datetime(2026, 8, 31, 1, 30, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in parsed
            )
        if invalid_delivery == "sibling_normalized":
            # Inventory itself is unmodified. Its shared response must still be checked
            # against an inconsistent activity scalar, even when selecting inventory alone.
            return tuple(
                replace(s, value=90.0) if s.source_field == "pmi010000" else s for s in parsed
            )
        return parsed

    if invalid_delivery == "publication_time":
        with pytest.raises(ValueError, match="registered_pmi_publication_evidence_required"):
            adapter.acquire_scalars(paths, scalars, definition_version=version)
        return
    adapter.acquire_scalars(paths, scalars, definition_version=version)
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_PMI_INVENTORY",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=version,
        )
    )
    assert len(points) == 2
    if invalid_delivery == "raw_bytes":
        assert (
            len(
                official_claims_matching_acquisitions(
                    evidence, {"CN_PMI_INVENTORY": points}, definition_version=version
                )
            )
            == 2
        )
        receipt = next(
            r
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.api_name == "cn_pmi"
        )
        assert receipt.raw_hash is not None
        (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")
    assert not official_claims_matching_acquisitions(
        evidence, {"CN_PMI_INVENTORY": points}, definition_version=version
    )
