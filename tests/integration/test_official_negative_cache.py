from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.worker import process_pending_run
from tests.integration.test_retrieval_ledger import prepared_runtime

PBC_LISTING = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"
# The monthly report's column, its releases listed page by page (lookback L05).
PBC_COLUMN = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html"


@pytest.mark.usefixtures("runtime_clock")
def test_same_official_release_reuses_negative_cache_across_target_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    released = datetime(2026, 9, 9, tzinfo=UTC)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_SF_TOTAL",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start="2026-08-01",
            period_end="2026-08-31",
            dimensions={"measure": "ytd_increment"},
            value=None,
            value_state=EvidenceValueState.NOT_DISCLOSED,
            unit="hundred_million_cny",
            provider="fixture:official-release",
            source_reference="fixture:sf-august-release",
            release_event_id="sf:2026-08",
            release_at=released,
            public_available_at=released,
            fetched_at=released,
            available_at=released,
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )
    calls = []

    def offline(request, *, timeout):
        calls.append(request.full_url)
        raise OSError("fixture official source unavailable")

    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    first_requests = []
    for target in ("2026-09-11", "2026-09-18"):
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date=target,
            client_request_id=f"same-release-{target}",
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id="sf:2026-08",
            metric_ids=("CN_SF_TOTAL",),
            period="2026-08",
            source_url=PBC_LISTING,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
        ledger = runs.get(submitted.run_id).retrieval_ledger
        assert ledger is not None
        assert calls == [PBC_COLUMN] * 3
        if target == "2026-09-11":
            first_requests = ledger["requests"]
            assert len(first_requests) == 3
            receipts = AcquisitionRepository(paths.database, paths.artifacts)
            for item in first_requests:
                assert item["classification"] == "transient_transport_error"
                assert item["state"] == "completed"
                receipt = receipts.get(item["acquisition_id"])
                assert receipt.state == "failed" and receipt.error_type == "OSError"
        else:
            query = ledger["queries"][0]
            assert len(ledger["queries"]) == 1
            assert query["classification"] == "negative_cache_active"
            assert query["cache_hit"]
            assert query["physical_request_id"] is None
            assert query["reused_request_id"] == first_requests[-1]["request_id"]
            assert datetime.fromisoformat(query["next_eligible_at"]) == cutoff + timedelta(
                minutes=15
            )
            assert all(item["run_id"] != submitted.run_id for item in ledger["requests"])


@pytest.mark.usefixtures("runtime_clock")
def test_a_changed_contract_is_not_held_back_by_the_old_contracts_negative_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gap sources #05: a repaired contract is tried again at once, not when the cache ends."""
    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    calls = []

    def offline(request, *, timeout):
        calls.append(request.full_url)
        raise OSError("fixture official source unavailable")

    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    for target, code in (("2026-09-11", "code-before-repair"), ("2026-09-18", "code-after")):
        # The code that parses and checks the release is part of the contract it is held to.
        monkeypatch.setattr("pring_cycle.retrieval_ledger.code_version", lambda code=code: code)
        runs.submit(
            command_type="targeted_refresh",
            target_business_date=target,
            client_request_id=f"contract-{target}",
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id="sf:2026-08",
            metric_ids=("CN_SF_TOTAL",),
            period="2026-08",
            source_url=PBC_LISTING,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)

    assert calls == [PBC_COLUMN] * 6
