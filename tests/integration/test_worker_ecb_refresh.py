"""The public direct-refresh stage owns ECB requests without certifying a real source.

Full process_pending_run activation and publication are a separate lifecycle acceptance.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository, own_acquisitions
from pring_cycle.ecb_reference import ECB_HISTORY_URL, ECB_METRIC
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.worker import refresh_context_sources
from tests.conftest import install_runtime_clock
from tests.fixtures.model_registration import bind_synthetic_review, migrated_request, save, submit
from tests.integration.test_ecb_reference_acquisition import certified_request, zip_csv


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Any:
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 1, tzinfo=UTC))


def system_request(paths: RuntimePaths) -> dict[str, Any]:
    request = certified_request(paths)
    request["manifest"]["point_in_time_rule_version"] = "dual-cutoff-v0003"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    return request


def context_http(monkeypatch: pytest.MonkeyPatch, content: bytes | OSError) -> list[str]:
    requested: list[str] = []

    class Response(BytesIO):
        status = 200
        headers = {
            "Content-Type": "application/zip",
            "Content-Length": str(len(content)) if isinstance(content, bytes) else "0",
        }

        def geturl(self) -> str:
            return ECB_HISTORY_URL

    def fetch(request: Any, *, timeout: int) -> Response:
        url = request.full_url
        requested.append(url)
        if url == ECB_HISTORY_URL:
            if isinstance(content, OSError):
                raise content
            return Response(content)
        if url.startswith("https://www.eia.gov/"):
            raise OSError("fixture EIA unavailable")
        raise AssertionError(f"unexpected external request: {url}")

    monkeypatch.setattr("pring_cycle.ecb_reference.open_no_redirects", fetch)
    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", fetch)
    return requested


def prepare_refresh(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], request_id: str
) -> tuple[RuntimePaths, RunRecord, str]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-09-18",
        client_request_id=request_id,
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    return paths, run, version


@pytest.mark.usefixtures("runtime_clock")
def test_direct_refresh_owns_ecb_original_and_selects_actual_system_without_tushare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run, version = prepare_refresh(tmp_path, capsys, "ecb-direct-refresh")
    runs = RunRepository(paths.database)
    raw = zip_csv("Date,USD,CNY,\n2026-01-01,1,7,\n2026-09-17,1.1481,7.7009,\n2026-09-19,1,8,\n")
    requested = context_http(monkeypatch, raw)
    scope = RetrievalScope("ecb:2026-09-17", (ECB_METRIC,), "2026-09-17", "P2", None)
    assert not ModelInputSelector(paths, run).select(scope).complete

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete, "the direct refresh never delivers the independent ECB input"
    assert requested.count(ECB_HISTORY_URL) == 1
    evidence = EvidenceRepository(paths.database)
    (point,) = evidence.metric_series(
        ECB_METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert point.period_end == "2026-09-17" and point.selected_value == pytest.approx(
        6.707516766832158
    )
    assert selected.selected_claim_ids == (point.selected_claim_id,)
    (claim,) = point.claims
    assert run.system_as_of < claim.available_at
    assert claim.release_at is None and claim.parsed_public_available_at is None
    acquired = [
        item
        for item in runs.full_retrieval_plan(run.run_id)["acquisitions"]
        if item["provider"] == "European Central Bank"
    ]
    (owned,) = acquired
    assert owned["phase"] == "direct_context_refresh" and owned["metric_ids"] == [ECB_METRIC]
    assert owned["state"] == "validated" and owned["api_name"] == "official_http_get"
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert acquisitions.read_content(owned["acquisition_id"], "raw") == raw
    attempt = evidence.latest_retrieval_attempt(
        ECB_METRIC, period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "verified_candidate"
    assert attempt.safe_metadata["run_id"] == run.run_id
    assert attempt.safe_metadata["target_business_date"] == run.target_business_date


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("failure", ["invalid_zip", "network"])
def test_invalid_optional_ecb_response_retains_failure_and_continues_other_sources(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    paths, run, version = prepare_refresh(tmp_path, capsys, "ecb-invalid-response")
    runs = RunRepository(paths.database)
    raw = b"not a ZIP archive" if failure == "invalid_zip" else OSError("fixture ECB unavailable")
    context_http(monkeypatch, raw)

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        ECB_METRIC, period=None, as_of=datetime.now(UTC), definition_version=version
    )
    expected = "validation_failed" if failure == "invalid_zip" else "source_failed"
    assert attempt is not None and attempt.outcome == expected
    if failure == "invalid_zip":
        assert attempt.safe_metadata["response_http_status"] == "200"
    acquired = [
        item
        for item in runs.full_retrieval_plan(run.run_id)["acquisitions"]
        if item["provider"] == "European Central Bank"
    ]
    (owned,) = acquired
    assert owned["state"] == "failed" and owned["metric_ids"] == [ECB_METRIC]
    assert attempt.safe_metadata["acquisition_ids"] == owned["acquisition_id"]
    assert attempt.safe_metadata["run_id"] == run.run_id
    if failure == "invalid_zip":
        assert (
            AcquisitionRepository(paths.database, paths.artifacts).read_content(
                owned["acquisition_id"], "raw"
            )
            == raw
        )
    else:
        assert owned["raw_hash"] is None
    assert not evidence.metric_series(
        ECB_METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    following = evidence.latest_retrieval_attempt(
        "CN_GDP", period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert following is not None and following.outcome == "missing_credentials"


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("catalog", ["builtin", "registered_tma"])
def test_old_catalog_refresh_never_requests_ecb_or_tma(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    catalog: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    version = "metric-catalog-v0002"
    if catalog == "registered_tma":
        submit(paths, save(paths, migrated_request(paths)))
        candidate = json.loads(capsys.readouterr().out)["model_version_id"]
        version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    requested = context_http(monkeypatch, b"must not be requested")

    refresh_context_sources(paths, "2026-09-18", definition_version=version)

    assert requested and all(url.startswith("https://www.eia.gov/") for url in requested)
    assert all(
        receipt.provider != "European Central Bank"
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_fresh_valid_original_recovers_damaged_prior_proof_with_a_new_vintage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run, version = prepare_refresh(tmp_path, capsys, "ecb-revalidation-failure")
    context_http(monkeypatch, zip_csv("Date,USD,CNY,\n2026-09-17,1,7.7,\n"))
    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)
    (first,) = [
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.provider == "European Central Bank"
    ]
    assert first.raw_hash is not None
    (paths.artifacts / first.raw_hash[:2] / first.raw_hash).write_bytes(b"damaged old original")
    # A fresh valid original with the same quotient cannot reuse damaged prior proof.
    context_http(monkeypatch, zip_csv("Date,USD,CNY,\n2026-09-17,2,15.4,\n"))

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        ECB_METRIC, period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "verified_candidate"
    receipts = [
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.provider == "European Central Bank"
    ]
    assert len(receipts) == 2 and all(receipt.state == "validated" for receipt in receipts)
    (new_id,) = {receipt.acquisition_id for receipt in receipts} - {first.acquisition_id}
    assert attempt.safe_metadata["acquisition_ids"] == new_id
    assert attempt.safe_metadata["run_id"] == run.run_id
    scope = RetrievalScope("ecb:2026-09-17", (ECB_METRIC,), "2026-09-17", "P2", None)
    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete and len(selected.selected_claim_ids) == 1
    (claim_id,) = selected.selected_claim_ids
    sources = evidence.source_claim_acquisitions_many((claim_id,))
    assert {item.receipt.acquisition_id for item in sources[claim_id]} == {new_id}
    (point,) = evidence.metric_series(
        ECB_METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    (claim,) = [c for c in point.claims if c.claim_id == claim_id]
    assert claim.supersedes_claim_id is not None
    assert claim.parsed_public_available_at is None
