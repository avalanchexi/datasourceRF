from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run

URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
ANNOUNCEMENT = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()


def prepare(tmp_path: Path):
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    # Already-known publisher events establish eligibility without supplying usable values.
    from pring_cycle.catalog import metric_definition
    from pring_cycle.evidence import EvidenceValueState, SourceClaimInput

    known = datetime(2026, 8, 10, tzinfo=UTC)
    for metric, dimensions in (
        ("CN_CPI_HEADLINE", {"measure": "yoy", "category": "headline"}),
        ("CN_PMI_ACTIVITY", {"series": "manufacturing", "measure": "level"}),
        ("CN_M1_M2", {"aggregate": "m1", "measure": "balance"}),
    ):
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id=metric,
                definition_version="metric-catalog-v0001",
                period_kind="month",
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions=dimensions,
                value=None,
                value_state=EvidenceValueState.NOT_DISCLOSED,
                unit="hundred_million_cny"
                if metric == "CN_M1_M2"
                else metric_definition(metric, definition_version="metric-catalog-v0001").unit,
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
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    return paths, RunRepository(paths.database)


def test_unknown_publication_window_is_distinct_from_not_yet_released(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    calls = []
    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", lambda *a, **k: calls.append(1))
    now = datetime(2026, 7, 1, tzinfo=UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-07-01",
        client_request_id="unknown-window",
        model_version_id="model-v0001",
        system_as_of=now,
        release_event_id="gdp:2026-Q2",
        metric_ids=("CN_GDP",),
        period="2026-Q2",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert calls == []
    assert stored.error_classification == "unknown_release_configuration"


@pytest.mark.usefixtures("runtime_clock")
def test_targeted_tushare_redirect_is_one_failed_physical_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from email.message import Message
    from urllib.request import BaseHandler, build_opener
    from urllib.response import addinfourl

    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n")
    calls = []

    class Transport(BaseHandler):
        handler_order = 100

        def https_open(self, request):
            calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "https://api.waditu.com/redirect-target"
            status = 302 if len(calls) == 1 else 200
            response = addinfourl(BytesIO(b"redirect-original"), headers, request.full_url, status)
            response.msg = "Found" if status == 302 else "OK"
            return response

    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener",
        lambda *handlers: build_opener(*handlers, Transport()),
    )
    now = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="tushare-redirect",
        model_version_id="model-v0001",
        system_as_of=now,
        release_event_id="money:2026-07",
        metric_ids=("CN_M1_M2",),
        period="2026-07",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert len(calls) == 1
    assert stored.status == "action_required"
    request = stored.retrieval_ledger["requests"][0]
    assert request["http_status"] == 302
    assert (
        AcquisitionRepository(paths.database, paths.artifacts).read_content(
            request["acquisition_id"], "raw"
        )
        == b"redirect-original"
    )


@pytest.mark.usefixtures("runtime_clock")
def test_tushare_numeric_failure_is_cached_after_raw_fields_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n")
    now = datetime.now(UTC)
    calls = []

    class Opener:
        def open(self, request, **kwargs):
            payload = json.loads(request.data)
            calls.append(payload["api_name"])
            fields = payload["fields"].split(",")
            return BytesIO(
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "fields": fields,
                            "items": [["202607", *(["bad"] * (len(fields) - 1))]],
                        },
                    }
                ).encode()
            )

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *a: Opener())
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="pmi-bad-number",
        model_version_id="model-v0001",
        system_as_of=now,
        release_event_id="pmi:2026-07",
        metric_ids=("CN_PMI_ACTIVITY",),
        period="2026-07",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    request = stored.retrieval_ledger["requests"][0]
    assert request["classification"] == "semantic_validation_failed"
    assert request["outcome"] == "failed"
    assert request["cache_expires_at"] is not None
    runs.resume(submitted.run_id, client_request_id="pmi-bad-resume", confirm_external_calls=True)
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert calls == ["cn_pmi"]


@pytest.mark.parametrize("failure", ["partial", "redirect", "fourth_candidate", "future_window"])
@pytest.mark.usefixtures("runtime_clock")
def test_search_candidate_rejections_and_discovery_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime(2026, 8, 19, tzinfo=UTC) if failure == "future_window" else datetime.now(UTC)
    calls = []
    urls = (
        [f"https://untrusted.example/{i}" for i in range(3)] + [URL]
        if failure == "fourth_candidate"
        else [URL]
    )

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL.replace("3399885", "3399886") if failure == "redirect" else URL

    def search(request, **kwargs):
        calls.append("tavily")
        return Response(json.dumps({"results": [{"url": url} for url in urls]}).encode())

    def official(request, **kwargs):
        calls.append("official")
        body = (
            ANNOUNCEMENT.replace("5年期以上LPR为3.5%".encode(), b"")
            if failure == "partial"
            else ANNOUNCEMENT
        )
        return Response(body)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id=f"reject-{failure}",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    validations = stored.retrieval_ledger["candidate_validations"]
    if failure == "future_window":
        assert calls == []
        assert validations == []
    elif failure == "fourth_candidate":
        assert calls == ["tavily"]
        assert len(validations) == 3
        assert all(v["candidate_url"] != URL for v in validations)
    else:
        assert calls == ["tavily", "official"]
        assert validations[0]["claim_ids"] == []
        assert validations[0]["outcome"] == "not_model_usable"


@pytest.mark.parametrize("pp_failures", [0, 2, 3])
@pytest.mark.usefixtures("runtime_clock")
def test_targeted_warrants_records_each_of_eight_deliveries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pp_failures: int,
) -> None:
    from urllib.request import Request

    from pring_cycle.evidence import EvidenceValueState, SourceClaimInput
    from pring_cycle.models import analytical_model_v0002_manifest

    paths, runs = prepare(tmp_path)
    models = ModelRepository(paths.database)
    models.create_candidate(analytical_model_v0002_manifest())
    models.record_acceptance("model-v0002", CALIBRATION_BASELINE)
    models.record_replay(
        "model-v0002",
        compared_with="model-v0001",
        requested_start="2026-03-09",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
    )
    models.activate("model-v0002", explicitly_approved=True)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n")
    now = datetime.now(UTC)
    public_at = datetime(2026, 8, 28, 9, tzinfo=UTC)
    # This legacy harness exercises the task/Worker/request ledger seam only.
    # Its synthetic quantities and units are not source certification.
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_FUTURES_WARRANTS",
            definition_version="metric-catalog-v0002",
            period_kind="business_day",
            period_start="2026-08-28",
            period_end="2026-08-28",
            dimensions={
                "symbol": "CU",
                "warehouse": "publication-marker",
                "exchange": "synthetic",
                "measure": "registered_receipts",
            },
            value=None,
            value_state=EvidenceValueState.NOT_DISCLOSED,
            unit="tonne",
            provider="synthetic-publisher",
            source_reference="synthetic:known-warrant-publication",
            release_event_id="synthetic:known-warrant-publication",
            release_at=public_at,
            public_available_at=public_at,
            fetched_at=now,
            available_at=now,
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )
    calls: list[str] = []
    originals: dict[str, bytes] = {}

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}

    class Opener:
        def open(self, request: Request, **kwargs: object) -> Response:
            assert isinstance(request.data, bytes)
            payload = json.loads(request.data)
            assert payload["api_name"] == "fut_wsr"
            symbol = payload["params"]["symbol"]
            assert payload["params"] == {
                "symbol": symbol,
                "start_date": "20260828",
                "end_date": "20260828",
            }
            calls.append(symbol)
            if symbol == "PP" and calls.count("PP") <= pp_failures:
                raise TimeoutError("synthetic-warrants-transport-timeout")
            rows = [["20260828", symbol, "synthetic-first", 90, 100, 10, "吨", "synthetic"]]
            if symbol == "CU":
                rows.append(["20260828", symbol, "synthetic-second", 20, 25, 5, "吨", "synthetic"])
            raw = json.dumps(
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
                },
                ensure_ascii=False,
            ).encode()
            originals[symbol] = raw
            return Response(raw)

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: Opener())
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="targeted-eight-warrants",
        model_version_id="model-v0002",
        system_as_of=now + timedelta(days=1),
        release_event_id="synthetic:warrants:2026-08-28",
        metric_ids=("CN_FUTURES_WARRANTS",),
        period="2026-08-28",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    if pp_failures == 3:
        assert calls == ["CF", "CU", "PP", "PP", "PP"]
    else:
        assert calls == ["CF", "CU", *(["PP"] * (pp_failures + 1)), "RB", "RU", "SC", "SP", "PTA"]
    assert stored.status == "action_required"  # Raw delivery cannot establish PUBLIC time.
    physical = [r for r in stored.retrieval_ledger["requests"] if r["channel"] == "tushare"]
    assert len(physical) == (5 if pp_failures == 3 else 8 + pp_failures)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for item in physical:
        receipt = acquisitions.get(item["acquisition_id"])
        if receipt.raw_hash is not None:
            assert receipt.state == ("failed" if pp_failures == 3 else "validated")
            assert (
                acquisitions.read_content(receipt.acquisition_id, "raw")
                == originals[receipt.parameters["symbol"]]
            )
        else:
            assert receipt.state == "failed"
            assert item["classification"] == "transient_transport_error"
    evidence = EvidenceRepository(paths.database)
    points = [
        p
        for p in evidence.metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.SYSTEM,
            as_of=stored.system_as_of,
            definition_version="metric-catalog-v0002",
        )
        if any(c.provider == "tushare" for c in p.claims)
    ]
    assert len(points) == (0 if pp_failures == 3 else 27)
    for point in points:
        assert all(c.public_available_at is None for c in point.claims)
        (receipt,) = evidence.trace(
            point.observation_id, mode=AsOfMode.SYSTEM, as_of=stored.system_as_of
        ).acquisitions
        assert receipt.parameters["symbol"] == (
            "PTA" if point.dimensions["symbol"] == "TA" else point.dimensions["symbol"]
        )
    assert "fixture-secret" not in json.dumps(stored.retrieval_ledger)


@pytest.mark.parametrize("ppi_failures", [0, 2])
@pytest.mark.usefixtures("runtime_clock")
def test_targeted_tushare_traces_each_physical_response_before_search_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ppi_failures: int,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\nTAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    calls = []
    raw_by_api = {}

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "application/json"}

    class Opener:
        def open(self, request, **kwargs):
            payload = json.loads(request.data)
            api = payload["api_name"]
            calls.append(api)
            if api == "cn_ppi" and calls.count(api) <= ppi_failures:
                raise TimeoutError("fixture-transient-ppi")
            assert payload["params"] == {"start_m": "202607", "end_m": "202607"}
            fields = payload["fields"].split(",")
            raw = json.dumps(
                {
                    "code": 0,
                    "data": {"fields": fields, "items": [["202607", *([1.2] * (len(fields) - 1))]]},
                }
            ).encode()
            raw_by_api[api] = raw
            return Response(raw)

    def search(request, **kwargs):
        calls.append("tavily")
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: Opener())
    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="targeted-tushare",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="cpi:2026-07",
        metric_ids=("CN_CPI_HEADLINE",),
        period="2026-07",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert calls == ["cn_cpi", *(["cn_ppi"] * (ppi_failures + 1)), "tavily"]
    assert stored.status == "action_required"
    physical = [r for r in stored.retrieval_ledger["requests"] if r["channel"] == "tushare"]
    assert len(physical) == 2 + ppi_failures
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for request in physical:
        receipt = acquisitions.get(request["acquisition_id"])
        if receipt.state == "failed":
            assert request["classification"] == "transient_transport_error"
            continue
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw") == raw_by_api[receipt.api_name]
        )
    assert "fixture-secret" not in json.dumps(stored.retrieval_ledger)
    points = EvidenceRepository(paths.database).metric_series(
        "CN_CPI_HEADLINE",
        mode=AsOfMode.SYSTEM,
        as_of=stored.system_as_of,
        definition_version="metric-catalog-v0001",
    )
    assert len(points) == 3
    assert all(p.selected_value == 1.2 for p in points)


@pytest.mark.parametrize(
    "command, days, checkpoint",
    [
        ("targeted_refresh", 0, "candidate"),
        ("targeted_refresh", 1, "candidate"),
        ("manual_deep_search", 0, "candidate"),
        ("targeted_refresh", 0, "search_receipt"),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_resume_reuses_received_search_and_finishes_interrupted_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    days: int,
    checkpoint: str,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    current = [now]
    interrupt = [checkpoint == "search_receipt"]

    def clock():
        if interrupt[0] and any(
            r.state == "validated"
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        ):
            interrupt[0] = False
            raise KeyboardInterrupt("fixture-search-checkpoint")
        return current[0]

    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", clock)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL

    def search(request, **kwargs):
        calls.append(request.full_url)
        return Response(json.dumps({"results": [{"url": URL}]}).encode())

    def official(request, **kwargs):
        calls.append(request.full_url)
        if checkpoint == "candidate" and calls.count(URL) == 1:
            raise KeyboardInterrupt("fixture-candidate-interrupted")
        return Response(ANNOUNCEMENT)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    submitted = runs.submit(
        command_type=command,
        target_business_date="2026-08-20",
        client_request_id="resume-candidate",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=2),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    with pytest.raises(KeyboardInterrupt):
        process_pending_run(paths, report_adapters=(), retrieval_now=now)
    interrupted = runs.get(submitted.run_id)
    if checkpoint == "candidate":
        assert (
            interrupted.retrieval_ledger["candidate_validations"][0]["outcome"]
            == "unknown_completion"
        )
    current[0] += timedelta(days=days)
    runs.resume(
        submitted.run_id, client_request_id="resume-candidate-2", confirm_external_calls=True
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    assert calls == [
        "https://api.tavily.com/search",
        *([URL] * (2 if checkpoint == "candidate" else 1)),
    ]
    assert stored.consumed_budget["tavily"] == 1
    requests = stored.retrieval_ledger["requests"]
    assert len([r for r in requests if r["channel"] == "tavily"]) == 1
    assert [v["outcome"] for v in stored.retrieval_ledger["candidate_validations"]] == (
        ["unknown_completion", "model_usable"] if checkpoint == "candidate" else ["model_usable"]
    )


@pytest.mark.parametrize(
    "values, expected",
    [((3.0,), "action_required"), ((3.0, None), "action_required"), ((3.0, 3.5), "completed")],
)
def test_local_lpr_requires_both_reported_tenors(tmp_path: Path, values, expected: str) -> None:
    from pring_cycle.evidence import EvidenceValueState, SourceClaimInput

    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("")
    known = datetime(2026, 8, 21, tzinfo=UTC)
    for tenor, value in zip(("1y", "5y_plus"), values, strict=False):
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id="CN_LPR_1Y_5Y",
                definition_version="metric-catalog-v0001",
                period_kind="month",
                period_start="2026-08-01",
                period_end="2026-08-31",
                dimensions={"tenor": tenor},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE
                if value is not None
                else EvidenceValueState.NOT_DISCLOSED,
                unit="percent",
                provider="中国货币网",
                source_reference=URL,
                release_event_id="lpr:2026-08",
                release_at=known,
                public_available_at=known,
                fetched_at=known,
                available_at=known,
                certification_status="certified",
                quality_status="validated",
            )
        )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-21",
        client_request_id="local-members",
        model_version_id="model-v0001",
        system_as_of=known,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=known)
    assert runs.get(submitted.run_id).status == expected


@pytest.mark.parametrize("checkpoint", ["candidate", "search_receipt"])
@pytest.mark.usefixtures("runtime_clock")
def test_terminal_resume_does_not_permanently_reuse_old_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkpoint: str
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    calls = []
    interrupt = [checkpoint == "search_receipt"]
    second_url = URL.replace("3399885.html", "3399886.html")

    def clock():
        if interrupt[0] and any(
            r.state == "validated"
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        ):
            interrupt[0] = False
            raise KeyboardInterrupt("fixture-after-search-receipt")
        return now

    monkeypatch.setattr("pring_cycle.retrieval_ledger.utc_now", clock)

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return calls[-1]

    def search(request, **kwargs):
        calls.append(request.full_url)
        url = URL if calls.count(request.full_url) == 1 else second_url
        return Response(json.dumps({"results": [{"url": url}]}).encode())

    def official(request, **kwargs):
        calls.append(request.full_url)
        if checkpoint == "candidate" and calls.count(URL) == 1:
            raise KeyboardInterrupt("fixture-candidate-interrupted")
        return Response(
            b"<html>not a valid release</html>" if request.full_url == URL else ANNOUNCEMENT
        )

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    submitted = runs.submit(
        command_type="manual_deep_search",
        target_business_date="2026-08-20",
        client_request_id="terminal-resume",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    with pytest.raises(KeyboardInterrupt):
        process_pending_run(paths, report_adapters=(), retrieval_now=now)
    runs.resume(
        submitted.run_id, client_request_id="terminal-resume-2", confirm_external_calls=True
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert runs.get(submitted.run_id).status == "action_required"
    assert calls.count("https://api.tavily.com/search") == 1
    reused = [
        item
        for item in runs.get(submitted.run_id).retrieval_attempts
        if item["channel"] == "tavily"
    ]
    assert reused[-1]["cache_hit"] is True
    assert reused[-1]["budget_charged"] is False
    runs.resume(
        submitted.run_id, client_request_id="terminal-resume-3", confirm_external_calls=True
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert calls.count("https://api.tavily.com/search") == 2
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    assert stored.consumed_budget["tavily"] == 2
    history = stored.retrieval_ledger
    assert any(item["state"] == "unknown_completion" for item in history["requests"])
    assert any(item["outcome"] == "not_model_usable" for item in history["candidate_validations"])


@pytest.mark.parametrize("channel", ["local", "official"])
@pytest.mark.usefixtures("runtime_clock")
def test_existing_channels_respect_complete_input_and_frozen_cutoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
) -> None:
    from pring_cycle.official_lpr import refresh_lpr_release

    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("")
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=1)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL

    def official(request, **kwargs):
        calls.append(request.full_url)
        return Response(ANNOUNCEMENT)

    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    if channel == "local":
        refresh_lpr_release(
            paths,
            source_url=URL,
            expected_period="2026-08",
            fetched_at=now,
            definition_version="metric-catalog-v0001",
        )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id=f"frozen-{channel}",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
        source_url=URL if channel == "official" else None,
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now + timedelta(minutes=1))
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.system_as_of == cutoff
    assert calls == [URL]


@pytest.mark.usefixtures("runtime_clock")
def test_unknown_publication_is_system_visible_but_not_target_model_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=1)
    no_publication = ANNOUNCEMENT.replace(b"<time>2026-08-20 09:00</time>", b"")

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen",
        lambda *args, **kwargs: Response(json.dumps({"results": [{"url": URL}]}).encode()),
    )
    monkeypatch.setattr(
        "pring_cycle.official_lpr.urlopen", lambda *args, **kwargs: Response(no_publication)
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="unknown-publication",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    validation = stored.retrieval_ledger["candidate_validations"][0]
    assert validation["public_complete"] is False
    assert validation["public_selected_claim_ids"] == []
    assert validation["selected_claim_ids"] == []
    assert (
        len(
            EvidenceRepository(paths.database).metric_series(
                "CN_LPR_1Y_5Y",
                mode=AsOfMode.SYSTEM,
                as_of=cutoff,
                definition_version="metric-catalog-v0001",
            )
        )
        == 2
    )
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_LPR_1Y_5Y",
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
            definition_version="metric-catalog-v0001",
        )
        == ()
    )


@pytest.mark.usefixtures("runtime_clock")
def test_unknown_official_url_does_not_claim_old_period_is_unreleased(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def search(request, **kwargs):
        calls.append(request.full_url)
        return Response(b'{"results":[{"url":"https://untrusted.example/cpi"}]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="url-unknown",
        model_version_id="model-v0001",
        system_as_of=now,
        release_event_id="cpi:2026-07",
        metric_ids=("CN_CPI_HEADLINE",),
        period="2026-07",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert calls == ["https://api.tavily.com/search"]
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert (
        stored.retrieval_ledger["candidate_validations"][0]["reason"]
        == "official_context_source_url_not_official"
    )
    assert stored.retrieval_ledger["gaps"][0]["release_event_kind"] == "budget_family_period"


@pytest.mark.usefixtures("runtime_clock")
def test_candidate_parser_limit_preserves_original_without_claiming_complete_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    oversized = ANNOUNCEMENT.replace(
        b"</body>", ("<p>" + "附加内容" * 500 + "</p></body>").encode()
    )

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen",
        lambda *args, **kwargs: Response(
            json.dumps({"results": [{"url": URL, "content": "摘" * 2000}]}).encode()
        ),
    )
    monkeypatch.setattr(
        "pring_cycle.official_lpr.urlopen", lambda *args, **kwargs: Response(oversized)
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="parser-limit",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    validation = stored.retrieval_ledger["candidate_validations"][0]
    assert validation["reason"] == "official_parser_fragment_too_large"
    assert validation["claim_ids"] == []
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    official = next(r for r in acquisitions.history() if r.api_name == "official_http_get")
    assert acquisitions.read_content(official.acquisition_id, "raw") == oversized
    search = next(r for r in acquisitions.history() if r.api_name == "search")
    normalized = json.loads(acquisitions.read_content(search.acquisition_id, "normalized"))
    assert sum(len(s) for s in normalized["candidate_summaries"]) == 1800


@pytest.mark.usefixtures("runtime_clock")
def test_wrong_period_then_duplicate_candidate_does_not_block_valid_exa_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    now = datetime.now(UTC)
    old_url = URL.replace("20260820", "20260720")
    old_document = (
        ANNOUNCEMENT.decode()
        .replace("2026年8月20日", "2026年7月20日")
        .replace("2026-08-20", "2026-07-20")
        .encode()
    )
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def __init__(self, content, url):
            super().__init__(content)
            self.url = url

        def geturl(self):
            return self.url

    def search(request, **kwargs):
        calls.append(request.full_url)
        urls = [old_url] if "tavily" in request.full_url else [old_url, URL]
        return Response(
            json.dumps({"results": [{"url": url} for url in urls]}).encode(), request.full_url
        )

    def official(request, **kwargs):
        calls.append(request.full_url)
        return Response(
            old_document if request.full_url == old_url else ANNOUNCEMENT, request.full_url
        )

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="fallback-valid",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert calls == ["https://api.tavily.com/search", old_url, "https://api.exa.ai/search", URL]
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    validations = stored.retrieval_ledger["candidate_validations"]
    assert [v["reason"] for v in validations[:2]] == [
        "lpr_release_period_mismatch",
        "duplicate_candidate",
    ]
    assert validations[-1]["outcome"] == "model_usable"


@pytest.mark.usefixtures("runtime_clock")
def test_explicit_cutoff_does_not_move_to_adopt_new_search_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=1)

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self):
            return URL

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen",
        lambda *args, **kwargs: Response(json.dumps({"results": [{"url": URL}]}).encode()),
    )
    monkeypatch.setattr(
        "pring_cycle.official_lpr.urlopen", lambda *args, **kwargs: Response(ANNOUNCEMENT)
    )
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="historical-cutoff",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.system_as_of == cutoff
    validation = stored.retrieval_ledger["candidate_validations"][0]
    assert len(validation["claim_ids"]) == 2
    assert validation["selected_claim_ids"] == []
    assert validation["outcome"] == "not_model_usable"


@pytest.mark.usefixtures("runtime_clock")
def test_search_candidate_becomes_complete_model_input_with_original_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    runs = RunRepository(paths.database)
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=1)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="candidate-complete",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def geturl(self):
            return URL

    def search(request, **kwargs):
        calls.append(request.full_url)
        return Response(json.dumps({"results": [{"url": URL, "content": "官方LPR发布"}]}).encode())

    def official(request, **kwargs):
        calls.append(request.full_url)
        return Response(ANNOUNCEMENT)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    assert calls == ["https://api.tavily.com/search", URL]
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    ledger = stored.retrieval_ledger
    validation = ledger["candidate_validations"][0]
    assert validation["outcome"] == "model_usable"
    points = EvidenceRepository(paths.database).metric_series(
        "CN_LPR_1Y_5Y",
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
        definition_version="metric-catalog-v0001",
    )
    assert {tuple(sorted(p.dimensions.items())): p.selected_value for p in points} == {
        (("tenor", "1y"),): 3.0,
        (("tenor", "5y_plus"),): 3.5,
    }
    assert set(validation["selected_claim_ids"]) == {p.selected_claim_id for p in points}
    assert validation["gap_ids"] == [ledger["gaps"][0]["gap_id"]]
    for point in points:
        trace = EvidenceRepository(paths.database).trace(
            point.observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff
        )
        assert trace.acquisition_status == "linked"
        receipt = trace.acquisitions[0]
        assert receipt.api_name == "official_http_get"
        assert (
            AcquisitionRepository(paths.database, paths.artifacts).read_content(
                receipt.acquisition_id, "raw"
            )
            == ANNOUNCEMENT
        )
        assert any(r["acquisition_id"] == receipt.acquisition_id for r in ledger["requests"])
