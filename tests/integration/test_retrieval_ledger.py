from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run


@pytest.mark.usefixtures("runtime_clock")
def test_official_provider_cache_isolated_by_source_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message
    from urllib.error import HTTPError

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    calls = []
    headers = Message()
    headers["Retry-After"] = "7200"

    def unavailable(url):
        calls.append(url)
        raise HTTPError(url, 429, "limited", headers, BytesIO(b"wait"))

    monkeypatch.setattr(
        "pring_cycle.official_context._fetch_official_context_document", unavailable
    )
    monkeypatch.setattr("pring_cycle.official_lpr.fetch_official_document", unavailable)
    for index, (metric, url) in enumerate(
        [
            ("CN_CPI_HEADLINE", "https://www.stats.gov.cn/sj/zxfb/202608/cpi.html"),
            ("CN_LPR_1Y_5Y", "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"),
            ("CN_PPI", "https://www.stats.gov.cn/sj/zxfb/202608/ppi.html"),
        ]
    ):
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-20",
            client_request_id=f"source-{index}",
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id=f"source-{index}",
            metric_ids=(metric,),
            period="2026-08",
            source_url=url,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert len(calls) == 2
    assert "chinamoney.com.cn" in calls[1]
    query = runs.get(submitted.run_id).retrieval_ledger["queries"][0]
    assert query["cache_hit"]
    assert datetime.fromisoformat(query["next_eligible_at"]) == cutoff + timedelta(hours=2)


def test_an_official_403_holds_back_only_its_own_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Event #06: a PBC column's nginx 403 held back every PBC page for a day (9/24)."""
    from email.message import Message
    from urllib.error import HTTPError

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    calls = []

    def forbidden(url):
        calls.append(url)
        raise HTTPError(url, 403, "Forbidden", Message(), BytesIO(b"403 Forbidden"))

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", forbidden)
    cpi = "https://www.stats.gov.cn/sj/zxfb/202608/cpi.html"
    ppi = "https://www.stats.gov.cn/sj/zxfb/202608/ppi.html"
    for index, (metric, url) in enumerate(
        [("CN_CPI_HEADLINE", cpi), ("CN_PPI", ppi), ("CN_CPI_HEADLINE", cpi)]
    ):
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-20",
            client_request_id=f"forbidden-{index}",
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id=f"forbidden-{index}",
            metric_ids=(metric,),
            period="2026-08",
            source_url=url,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)

    assert calls == [cpi, ppi]
    query = runs.get(submitted.run_id).retrieval_ledger["queries"][0]
    assert query["cache_hit"]


@pytest.mark.parametrize("legacy_kind", ["budget", "cache"])
@pytest.mark.usefixtures("runtime_clock")
def test_legacy_shared_release_family_is_bound_to_original_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy_kind: str,
) -> None:
    from pring_cycle.official_context import FetchedOfficialContextDocument

    paths, runs = prepared_runtime(tmp_path)
    models = ModelRepository(paths.database)
    models.activate("model-v0002", explicitly_approved=True)
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    old = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="legacy-sf",
        model_version_id="model-v0002",
        system_as_of=cutoff,
        release_event_id="old-sf-total",
        metric_ids=("CN_SF_TOTAL",),
        period="2026-07",
    )
    if legacy_kind == "budget":
        runs.record_retrieval_attempt(
            old.run_id,
            release_event_id="old-sf-total",
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
            occurred_at=cutoff,
        )
    else:
        runs.store_negative_cache(
            "old-sf-total",
            ("CN_SF_TOTAL",),
            reason="unresolved",
            expires_at=cutoff + timedelta(minutes=30),
            now=cutoff,
        )
    runs.mark_action_required(old.run_id, "legacy-unresolved")
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(*args, **kwargs):
        calls.append(1)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    monkeypatch.setattr(
        "pring_cycle.official_context._fetch_official_context_document",
        lambda url: FetchedOfficialContextDocument(b"unusable", "text/html", url, 200),
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="sf-components",
        model_version_id="model-v0002",
        system_as_of=cutoff,
        release_event_id="new-sf-components",
        metric_ids=("CN_SF_COMPONENTS",),
        period="2026-07",
        source_url="https://www.pbc.gov.cn/fixture/social-financing.html",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    query = runs.get(submitted.run_id).retrieval_ledger["queries"][-1]
    if legacy_kind == "budget":
        # Another run's old charge no longer holds this run back: no daily cap (ticket 20).
        assert calls == [1]
        assert query["physical_request_id"] is not None
    else:
        assert calls == []
        assert query["classification"] == "negative_cache_active"


@pytest.mark.usefixtures("runtime_clock")
def test_legacy_retries_preserve_run_limit_after_day_rollover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    old = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="legacy-resume",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="legacy-august",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    for index in range(17):
        runs.record_retrieval_attempt(
            old.run_id,
            release_event_id="legacy-august",
            channel="tavily",
            outcome="failed",
            classification="transient_transport_error",
            latency_ms=1,
            remaining_run_budget=5,
            remaining_daily_budget=13,
            budget_charged=index % 3 == 0,
            cache_hit=False,
            manual_budget_exemption=False,
            candidate_source=None,
            occurred_at=cutoff - timedelta(days=1),
        )
    runs.set_budget_consumption(old.run_id, tavily=3, exa=0, ai_websearch=0)
    runs.mark_action_required(old.run_id, "legacy-unresolved")
    runs.resume(old.run_id, client_request_id="upgrade-resume", confirm_external_calls=True)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(*args, **kwargs):
        calls.append(1)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert calls == []
    stored = runs.get(old.run_id)
    assert stored.consumed_budget["tavily"] == 17
    assert stored.retrieval_ledger["queries"][-1]["classification"] == "run_limit"


def prepared_runtime(tmp_path: Path) -> tuple[RuntimePaths, RunRepository]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    # These accounting scenarios concern known releases with missing values.
    from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput

    known = datetime(2026, 9, 1, tzinfo=UTC)
    for version in ("metric-catalog-v0001", "metric-catalog-v0002"):
        for metric, period_start, period_end, dimensions in (
            (
                "CN_CPI_HEADLINE",
                "2026-08-01",
                "2026-08-31",
                {"category": "headline", "measure": "yoy"},
            ),
            ("CN_PPI", "2026-08-01", "2026-08-31", {"category": "headline", "measure": "yoy"}),
            ("CN_SF_TOTAL", "2026-07-01", "2026-07-31", {"measure": "ytd_increment"}),
            (
                "CN_SF_COMPONENTS",
                "2026-07-01",
                "2026-07-31",
                {"component": "rmb_loans", "measure": "increment"},
            ),
            (
                "CN_GDP",
                "2026-04-01",
                "2026-06-30",
                {"aggregate": "total", "measure": "real_quarter_yoy"},
            ),
        ):
            EvidenceRepository(paths.database).append_source_claim(
                SourceClaimInput(
                    metric_id=metric,
                    definition_version=version,
                    period_kind="quarter" if metric == "CN_GDP" else "month",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions=dimensions,
                    value=None,
                    value_state=EvidenceValueState.NOT_DISCLOSED,
                    unit="hundred_million_cny"
                    if metric in {"CN_SF_TOTAL", "CN_SF_COMPONENTS"}
                    else "percent",
                    provider="已知发布机构",
                    source_reference="fixture:known-release:" + metric,
                    release_event_id="fixture-release:" + metric,
                    release_at=known,
                    public_available_at=known,
                    fetched_at=known,
                    available_at=known,
                    certification_status="awaiting_source_certification",
                    quality_status="validated",
                )
            )
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n", encoding="utf-8")
    return paths, RunRepository(paths.database)


@pytest.mark.usefixtures("runtime_clock")
def test_manual_search_has_no_daily_cap_across_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(request: object, **kwargs: object) -> Response:
        calls.append(request)
        return Response(b'{"results": []}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    for index in range(17):
        year, month = divmod(2024 * 12 + index, 12)
        period = f"{year:04d}-{month + 1:02d}"
        submitted = runs.submit(
            command_type="manual_deep_search",
            target_business_date="2026-08-20",
            client_request_id=f"daily-{index}",
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id=f"lpr:{period}",
            metric_ids=("CN_LPR_1Y_5Y",),
            period=period,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert len(calls) == 17
    last = runs.get(submitted.run_id)
    assert last.retrieval_ledger["queries"][-1]["physical_request_id"] is not None


@pytest.mark.usefixtures("runtime_clock")
def test_different_caller_event_labels_do_not_repeat_same_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(request: object, **kwargs: object) -> Response:
        calls.append(request)
        return Response(b'{"results": []}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    for label in ("caller-a", "caller-b"):
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-20",
            client_request_id=label,
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id=label,
            metric_ids=("CN_LPR_1Y_5Y",),
            period="2026-08",
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert len(calls) == 1
    ledger = runs.get(submitted.run_id).retrieval_ledger
    assert len(ledger["gaps"]) == 1
    assert ledger["gaps"][0]["dimensions"] == {"tenor": "*"}
    assert ledger["queries"][-1]["classification"] == "negative_cache_active"
    assert ledger["queries"][-1]["physical_request_id"] is None


@pytest.mark.usefixtures("runtime_clock")
def test_targeted_search_reserves_request_before_http_and_retains_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n", encoding="utf-8")
    runs = RunRepository(paths.database)
    cutoff = datetime(2026, 8, 20, 3, tzinfo=UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="ledger-lpr-1",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    raw = b'{  "results": [], "request_id": "fixture-physical-1" }\n'
    observed_during_http = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}

    def open_http(request: object, **kwargs: object) -> Response:
        observed_during_http.append(getattr(runs.get(submitted.run_id), "retrieval_ledger", None))
        return Response(raw)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    assert process_pending_run(paths, report_adapters=(), retrieval_now=cutoff) == submitted.run_id
    assert len(observed_during_http) == 1
    during = observed_during_http[0]
    assert during is not None
    pending = [r for r in during["requests"] if r["channel"] == "tavily"]
    assert len(pending) == 1 and pending[0]["state"] == "reserved"
    assert pending[0]["cost"] is None
    stored = runs.get(submitted.run_id)
    ledger = stored.retrieval_ledger
    assert ledger is not None
    assert len(ledger["gaps"]) == 1
    gap = ledger["gaps"][0]
    assert gap["model_version_id"] == "model-v0001"
    assert gap["metric_id"] == "CN_LPR_1Y_5Y"
    assert gap["as_of"] == cutoff.isoformat()
    request = next(r for r in ledger["requests"] if r["channel"] == "tavily")
    assert request["state"] == "completed" and request["outcome"] == "not_found"
    assert request["cost"] is None
    assert request["gap_ids"] == [gap["gap_id"]]
    receipt = AcquisitionRepository(paths.database, paths.artifacts)
    assert receipt.read_content(request["acquisition_id"], "raw") == raw
    assert "fixture-secret" not in json.dumps(ledger)
    assert stored.consumed_budget["tavily"] == 1
    assert stored.status == "action_required"


@pytest.mark.usefixtures("runtime_clock")
def test_interrupted_search_is_charged_and_not_silently_repeated_on_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n", encoding="utf-8")
    runs = RunRepository(paths.database)
    cutoff = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="ledger-interrupt-1",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    calls = []

    def interrupted_http(request: object, **kwargs: object) -> None:
        calls.append("tavily")
        raise KeyboardInterrupt("fixture-process-interruption")

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", interrupted_http)
    with pytest.raises(KeyboardInterrupt):
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    interrupted = runs.get(submitted.run_id)
    assert interrupted.status == "interrupted"
    assert interrupted.consumed_budget["tavily"] == 1
    assert interrupted.retrieval_ledger["requests"][0]["state"] == "unknown_completion"
    original_gap_id = interrupted.retrieval_ledger["gaps"][0]["gap_id"]
    runs.resume(
        submitted.run_id, client_request_id="ledger-explicit-resume", confirm_external_calls=True
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    resumed = runs.get(submitted.run_id)
    assert calls == ["tavily"]
    assert resumed.consumed_budget["tavily"] == 1
    assert resumed.retrieval_ledger["gaps"][0]["gap_id"] == original_gap_id
    assert resumed.retrieval_ledger["requests"][0]["state"] == "unknown_completion"
    assert resumed.status == "action_required"


@pytest.mark.parametrize(
    ("status", "raw", "headers", "classification", "cache_seconds"),
    [
        (200, b"{broken", {}, "semantic_validation_failed", 21600),
        (500, b"upstream unavailable", {}, "transient_transport_error", 900),
        (429, b'{"error":"rate limit"}', {"Retry-After": "7200"}, "rate_limited", 7200),
        (403, b'{"error":"forbidden"}', {}, "forbidden_unknown", 600),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_failed_response_keeps_receipt_cache_and_next_attempt_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    raw: bytes,
    headers: dict[str, str],
    classification: str,
    cache_seconds: int,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    current = [datetime(2026, 9, 6, 15, 55, tzinfo=UTC)]
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: current[0])
    calls = []

    class Response(BytesIO):
        pass

    def open_http(request: object, **kwargs: object) -> Response:
        calls.append(request)
        response = Response(raw)
        response.status = status
        response.headers = headers
        return response

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="failed-response",
        model_version_id="model-v0001",
        system_as_of=current[0],
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
    failed = runs.get(submitted.run_id)
    ledger = failed.retrieval_ledger
    assert len(calls) == 1
    request = ledger["requests"][0]
    assert request["state"] == "completed"
    assert request["classification"] == classification
    assert datetime.fromisoformat(request["cache_expires_at"]) == current[0] + timedelta(
        seconds=cache_seconds
    )
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            request["acquisition_id"], "raw"
        )
        == raw
    )
    # A new Shanghai day removes the event guard, but not an unexpired negative cache.
    current[0] += timedelta(minutes=6)
    runs.resume(submitted.run_id, client_request_id="cached-resume", confirm_external_calls=True)
    process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
    cached = runs.get(submitted.run_id).retrieval_ledger
    assert len(calls) == 1
    assert cached["queries"][-1]["cache_hit"]
    assert cached["queries"][-1]["classification"] == "negative_cache_active"
    current[0] += timedelta(seconds=cache_seconds)
    runs.resume(submitted.run_id, client_request_id="expired-resume", confirm_external_calls=True)
    process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("provider", "metadata", "expected"),
    [
        (
            "tavily",
            {"usage": {"credits": 1}},
            {"amount": 1, "unit": "credit", "basis": "provider_usage"},
        ),
        (
            "exa",
            {"costDollars": {"total": 0.007}},
            {"amount": 0.007, "unit": "USD", "basis": "provider_estimate"},
        ),
        ("tavily", {"usage": {"credits": 10**400}}, None),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_search_usage_preserves_units_and_does_not_claim_estimate_as_bill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    metadata: dict,
    expected: dict,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text(f"{provider.upper()}_API_KEY=fixture-secret\n")
    cutoff = datetime.now(UTC)

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(request, **kwargs) -> Response:
        if provider == "tavily":
            assert json.loads(request.data)["include_usage"] is True
        assert (
            json.loads(request.data)["max_results" if provider == "tavily" else "numResults"] == 3
        )
        return Response(json.dumps({"results": [], **metadata}).encode())

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="cost",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    ledger = runs.get(submitted.run_id).retrieval_ledger
    assert ledger["requests"][0]["cost"] == expected
    assert ledger["requests"][0]["billed_cost"] is None
    assert ledger["requests"][0]["state"] == "completed"


@pytest.mark.usefixtures("runtime_clock")
def test_expired_search_response_keeps_audit_identity_without_promising_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    current = [datetime.now(UTC)]
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: current[0])
    monkeypatch.setattr("pring_cycle.acquisition.utc_now", lambda: current[0])

    class Response(BytesIO):
        status = 200
        headers = {}

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen",
        lambda *a, **kw: Response(b'{"results":[],"usage":{"credits":1}}'),
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="retention",
        model_version_id="model-v0001",
        system_as_of=current[0],
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
    request = runs.get(submitted.run_id).retrieval_ledger["requests"][0]
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = repository.get(request["acquisition_id"])
    assert repository.read_content(receipt.acquisition_id, "raw")
    current[0] += timedelta(days=31)
    assert process_pending_run(paths, report_adapters=()) is None
    stored = runs.get(submitted.run_id).retrieval_ledger
    assert stored["requests"][0]["raw_status"] == "expired"
    assert stored["requests"][0]["raw_hash"] == receipt.raw_hash
    assert stored["requests"][0]["cost"]["amount"] == 1
    assert stored["requests"][0]["gap_ids"] == request["gap_ids"]
    with pytest.raises(LookupError, match="search_response_expired"):
        repository.read_content(receipt.acquisition_id, "raw")
    assert not (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).exists()


@pytest.mark.usefixtures("runtime_clock")
def test_dead_worker_lease_marks_inflight_request_unknown_before_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="dead-worker",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    observed = []

    def dead_http(*args, **kwargs):
        runs.audit_lease(process_is_alive=lambda process_id: False)
        observed.append(runs.get(submitted.run_id))
        raise KeyboardInterrupt

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", dead_http)
    with pytest.raises(KeyboardInterrupt):
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert observed[0].status == "interrupted"
    request = observed[0].retrieval_ledger["requests"][0]
    assert request["state"] == "unknown_completion"
    assert request["acquisition_id"] is not None
    assert observed[0].consumed_budget["tavily"] == 1


@pytest.mark.usefixtures("runtime_clock")
def test_same_release_links_new_frozen_gap_to_prior_request_without_new_charge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(*args, **kwargs):
        calls.append(1)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    for target in ("2026-08-20", "2026-08-21"):
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date=target,
            client_request_id=target,
            model_version_id="model-v0001",
            system_as_of=cutoff,
            release_event_id=target,
            metric_ids=("CN_LPR_1Y_5Y",),
            period="2026-08",
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    stored = runs.get(submitted.run_id)
    ledger = stored.retrieval_ledger
    assert len(calls) == 1
    assert stored.consumed_budget["tavily"] == 0
    query = ledger["queries"][0]
    assert query["physical_request_id"] is None
    assert query["reused_request_id"] == ledger["requests"][0]["request_id"]
    assert len(ledger["requests"][0]["gap_ids"]) == 2
    assert not ledger["requests"][0]["charged_to_run"]


@pytest.mark.usefixtures("runtime_clock")
def test_official_http_request_is_linked_to_gap_even_when_document_fails_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pring_cycle.official_lpr import FetchedOfficialDocument

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    url = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="official-failed",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
        source_url=url,
    )
    before_http = []

    def fetch(source_url: str):
        before_http.append(runs.get(submitted.run_id).retrieval_ledger)
        return FetchedOfficialDocument(
            content=b"<html>missing fields</html>",
            final_url=source_url,
            http_status=200,
            media_type="text/html",
        )

    monkeypatch.setattr("pring_cycle.official_lpr.fetch_official_document", fetch)
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert len(before_http) == 1
    assert before_http[0]["requests"][0]["state"] == "reserved"
    stored = runs.get(submitted.run_id)
    request = stored.retrieval_ledger["requests"][0]
    assert request["channel"] == "official"
    assert request["state"] == "completed"
    assert request["classification"] == "semantic_validation_failed"
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            request["acquisition_id"], "raw"
        )
        == b"<html>missing fields</html>"
    )
    assert stored.consumed_budget["tavily"] == 0


@pytest.mark.parametrize(("provider", "limit"), [("tavily", 16), ("exa", 8)])
@pytest.mark.usefixtures("runtime_clock")
def test_explicit_resume_keeps_run_cap_across_daily_resets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    limit: int,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text(f"{provider.upper()}_API_KEY=fixture-secret\n")
    current = [datetime.now(UTC)]
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: current[0])
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(*args, **kwargs):
        calls.append(1)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="run-cap",
        model_version_id="model-v0001",
        system_as_of=current[0],
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    for attempt in range(limit + 1):
        if attempt:
            current[0] += timedelta(days=1)
            runs.resume(
                submitted.run_id, client_request_id=f"resume-{attempt}", confirm_external_calls=True
            )
        process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
        if attempt == limit - 1:
            final_query = runs.get(submitted.run_id).retrieval_ledger["queries"][-1]
            assert final_query["physical_request_id"] is not None
            assert final_query["next_eligible_at"] is None
    stored = runs.get(submitted.run_id)
    assert len(calls) == limit
    assert stored.consumed_budget[provider] == limit
    assert stored.retrieval_ledger["queries"][-1]["classification"] == "run_limit"
    assert stored.retrieval_ledger["queries"][-1]["next_eligible_at"] is None


@pytest.mark.usefixtures("runtime_clock")
def test_p2_empty_response_waits_24_hours_and_exa_waits_for_tavily_quota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)

    class Response(BytesIO):
        status = 200
        headers = {}

    def unavailable(*args, **kwargs):
        raise OSError("fixture-network-error")

    monkeypatch.setattr(
        "pring_cycle.official_context._fetch_official_context_document", unavailable
    )
    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen", lambda *args, **kwargs: Response(b'{"results":[]}')
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="p2",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="gdp:2026-Q2",
        metric_ids=("CN_GDP",),
        period="2026-Q2",
        source_url="https://www.stats.gov.cn/sj/zxfb/202607/fixture.html",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    stored = runs.get(submitted.run_id)
    requests = stored.retrieval_ledger["requests"]
    assert {item["channel"] for item in requests} == {"official", "tavily"}
    for request in requests:
        if request["channel"] != "official":
            assert datetime.fromisoformat(request["cache_expires_at"]) == cutoff + timedelta(
                hours=24
            )
    attempts = {item["channel"]: item for item in stored.retrieval_attempts}
    assert attempts["exa"]["classification"] == "tavily_quota_available"
    # AI WebSearch is open to P2 now; it has no adapter configured here.
    assert attempts["ai_websearch"]["outcome"] == "not_configured"


@pytest.mark.usefixtures("runtime_clock")
def test_official_rate_limit_keeps_http_status_and_retry_after(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message
    from urllib.error import HTTPError

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", lambda: cutoff)
    url = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
    headers = Message()
    headers["Retry-After"] = "7200"

    def unavailable(source_url):
        raise HTTPError(source_url, 429, "too many requests", headers, BytesIO(b"wait"))

    monkeypatch.setattr("pring_cycle.official_lpr.fetch_official_document", unavailable)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="official-rate",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
        source_url=url,
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    request = runs.get(submitted.run_id).retrieval_ledger["requests"][0]
    assert request["http_status"] == 429
    assert request["classification"] == "rate_limited"
    assert datetime.fromisoformat(request["cache_expires_at"]) == cutoff + timedelta(hours=2)
    assert request["response_headers"]["retry-after"] == "7200"


def test_existing_unexpired_negative_cache_survives_new_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    runs.store_negative_cache(
        "legacy-august",
        ("CN_LPR_1Y_5Y",),
        reason="unresolved",
        expires_at=cutoff + timedelta(minutes=30),
        now=cutoff,
    )
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def open_http(*args, **kwargs):
        calls.append(1)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", open_http)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="legacy-cache",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="legacy-august",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert calls == []
    query = runs.get(submitted.run_id).retrieval_ledger["queries"][-1]
    assert query["cache_hit"]
    assert datetime.fromisoformat(query["next_eligible_at"]) == cutoff + timedelta(minutes=30)


@pytest.mark.usefixtures("runtime_clock")
def test_response_received_before_completion_interruption_still_expires(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepared_runtime(tmp_path)
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    current = [datetime.now(UTC)]
    interrupt_once = [True]

    def interrupted_clock():
        if interrupt_once[0] and any(
            receipt.state == "validated" for receipt in repository.history()
        ):
            interrupt_once[0] = False
            raise KeyboardInterrupt("fixture-interrupt-after-response")
        return current[0]

    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", interrupted_clock)
    monkeypatch.setattr("pring_cycle.acquisition.utc_now", lambda: current[0])

    class Response(BytesIO):
        status = 200
        headers = {}

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen", lambda *a, **kw: Response(b'{"results":[]}')
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="retention-interrupted",
        model_version_id="model-v0001",
        system_as_of=current[0],
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    with pytest.raises(KeyboardInterrupt):
        process_pending_run(paths, report_adapters=(), retrieval_now=current[0])
    request = runs.get(submitted.run_id).retrieval_ledger["requests"][0]
    assert request["state"] == "unknown_completion"
    assert repository.read_content(request["acquisition_id"], "raw") == b'{"results":[]}'
    current[0] += timedelta(days=31)
    process_pending_run(paths, report_adapters=())
    stored = runs.get(submitted.run_id).retrieval_ledger["requests"][0]
    assert stored["raw_status"] == "expired"
    with pytest.raises(LookupError, match="search_response_expired"):
        repository.read_content(stored["acquisition_id"], "raw")


@pytest.mark.usefixtures("runtime_clock")
def test_official_short_transport_retries_register_each_physical_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pring_cycle.official_lpr import FetchedOfficialDocument

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    cutoff = datetime.now(UTC)
    url = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
    calls = []

    def unavailable(source_url):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("fixture-network-error")
        return FetchedOfficialDocument(
            content=b"<html>missing fields</html>",
            final_url=source_url,
            http_status=200,
            media_type="text/html",
        )

    monkeypatch.setattr("pring_cycle.official_lpr.fetch_official_document", unavailable)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="official-retry",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
        source_url=url,
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    ledger = runs.get(submitted.run_id).retrieval_ledger
    assert len(calls) == 3
    assert len(ledger["requests"]) == 3
    assert [item["classification"] for item in ledger["requests"]] == [
        "transient_transport_error",
        "transient_transport_error",
        "semantic_validation_failed",
    ]
    assert all(item["state"] == "completed" for item in ledger["requests"])


@pytest.mark.usefixtures("runtime_clock")
def test_search_redirect_cannot_issue_an_unregistered_second_http_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message
    from urllib.response import addinfourl

    paths, runs = prepared_runtime(tmp_path)
    cutoff = datetime.now(UTC)
    calls = []

    def https_response(handler, request):
        calls.append(request.full_url)
        headers = Message()
        if len(calls) == 1:
            headers["Location"] = "https://api.tavily.com/redirected"
            response = addinfourl(BytesIO(b"moved"), headers, request.full_url, 302)
            response.msg = "Found"
        else:
            response = addinfourl(BytesIO(b'{"results":[]}'), headers, request.full_url, 200)
            response.msg = "OK"
        return response

    monkeypatch.setattr("urllib.request.HTTPSHandler.https_open", https_response)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="redirect",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    assert calls == ["https://api.tavily.com/search"]
    ledger = runs.get(submitted.run_id).retrieval_ledger
    assert len(ledger["requests"]) == 1
    assert ledger["requests"][0]["http_status"] == 302
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            ledger["requests"][0]["acquisition_id"], "raw"
        )
        == b"moved"
    )


@pytest.mark.usefixtures("runtime_clock")
def test_official_listing_and_article_have_separate_completed_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pring_cycle.official_context import FetchedOfficialContextDocument

    paths, runs = prepared_runtime(tmp_path)
    paths.secrets.write_text("")
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    article = listing + "202609/t20260909_1965262.html"
    documents = {
        listing: (
            '<a href="202609/t20260909_1965262.html">2026年8月份工业生产者出厂价格</a>'
        ).encode(),
        article: (
            Path(__file__).parents[1] / "fixtures/official_period_fallback/nbs_ppi.html"
        ).read_bytes(),
    }
    cutoff = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-11",
        client_request_id="official-listing-and-article",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="ppi:2026-08",
        metric_ids=("CN_PPI",),
        period="2026-08",
        source_url=listing,
    )
    before_http = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        before_http.append(runs.get(submitted.run_id).retrieval_ledger)
        return FetchedOfficialContextDocument(
            content=documents[url], media_type="text/html", final_url=url, http_status=200
        )

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    process_pending_run(paths, report_adapters=(), retrieval_now=cutoff)
    stored = runs.get(submitted.run_id)
    requests = stored.retrieval_ledger["requests"]
    assert len(before_http) == 2
    assert all(view["requests"][-1]["state"] == "reserved" for view in before_http)
    assert len(requests) == 2
    assert all(request["state"] == "completed" for request in requests)
    assert {
        query["query_text"]
        for query in stored.retrieval_ledger["queries"]
        if query["physical_request_id"] is not None
    } == {listing, article}
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    assert {
        acquisitions.get(request["acquisition_id"]).parameters["source_url"] for request in requests
    } == {listing, article}
