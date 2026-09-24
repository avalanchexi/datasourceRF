"""Ticket 20: the P2 lenient path, and Exa standing in only once Tavily's quota is spent."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from urllib.error import HTTPError

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import LENIENT_EXTRACTION
from pring_cycle.worker import process_pending_run
from tests.integration.test_retrieval_strict_path import Page
from tests.integration.test_search_evidence import ANNOUNCEMENT, URL, prepare

VIX_PAGE = "https://www.cboe.com/tradable_products/vix/"
VIX_DAY = "2026-08-27"


def vix_run(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, results: list[dict[str, str]]
) -> tuple[RunRecord, RuntimePaths, list[str]]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    calls: list[str] = []

    def search(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(json.dumps({"results": results}).encode(), request.full_url)

    def page(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(b"<html>VIX 15.23</html>", request.full_url)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.http_transport.open_no_redirects", page)
    runs = RunRepository(paths.database)
    now = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        # The US close of the 27th is published on the Shanghai morning of the 28th.
        target_business_date="2026-08-28",
        client_request_id="vix",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id=f"vix:{VIX_DAY}",
        metric_ids=("CBOE_VIX_INDEX",),
        period=VIX_DAY,
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    return runs.get(submitted.run_id), paths, calls


def vix_values(paths: RuntimePaths) -> list[float | None]:
    return [
        point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            "CBOE_VIX_INDEX",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(days=2),
            definition_version="metric-catalog-v0001",
        )
    ]


def test_p2_takes_the_search_value_from_a_registered_host_and_keeps_the_page(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored, paths, calls = vix_run(
        tmp_path,
        monkeypatch,
        [{"url": VIX_PAGE, "content": "Cboe VIX index closed at 15.23 on August 27, 2026."}],
    )

    assert stored.status == "completed"
    assert vix_values(paths) == [15.23]
    [validation] = stored.retrieval_ledger["candidate_validations"]
    page = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "search_page_get"
    )
    assert validation["outcome"] == "model_usable"
    assert (validation["fetched_url"], validation["raw_hash"], validation["parser_version"]) == (
        VIX_PAGE,
        page.raw_hash,
        LENIENT_EXTRACTION,
    )
    assert calls == ["https://api.tavily.com/search", VIX_PAGE]


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        pytest.param(
            {"url": "https://finance.example.com/vix", "content": "VIX 15.23 on 2026-08-27"},
            "not_whitelisted",
            id="unregistered-host",
        ),
        pytest.param(
            {"url": VIX_PAGE, "content": "VIX opened at 14.90 and closed 15.23"},
            "period_mismatch",
            id="no-date",
        ),
        pytest.param(
            {"url": VIX_PAGE, "content": "2026-08-27: VIX high 16.10, low 14.20, last 15.23"},
            "parse_failed",
            id="ambiguous-value",
        ),
    ],
)
def test_p2_lenient_candidate_is_rejected_with_its_reason(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, result: dict[str, str], reason: str
) -> None:
    stored, paths, _calls = vix_run(tmp_path, monkeypatch, [result])

    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == ("not_model_usable", reason)
    assert vix_values(paths) == []


def test_exa_stands_in_only_after_tavily_reports_its_monthly_quota_spent(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    now = datetime.now(UTC)
    calls: list[str] = []

    exa_payloads: list[dict[str, Any]] = []

    def search(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        if "exa" in request.full_url:
            exa_payloads.append(json.loads(request.data))
        if "tavily" in request.full_url:
            raise HTTPError(request.full_url, 432, "plan limit", {}, BytesIO(b"{}"))  # type: ignore[arg-type]
        return Page(json.dumps({"results": [{"url": URL}]}).encode(), request.full_url)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr(
        "pring_cycle.official_lpr.urlopen",
        lambda request, **kwargs: calls.append(request.full_url) or Page(ANNOUNCEMENT, URL),
    )

    def submit(label: str, period: str) -> RunRecord:
        submitted = runs.submit(
            command_type="targeted_refresh",
            target_business_date="2026-08-20",
            client_request_id=label,
            model_version_id="model-v0001",
            system_as_of=now + timedelta(days=1),
            release_event_id=f"lpr:{period}",
            metric_ids=("CN_LPR_1Y_5Y",),
            period=period,
        )
        process_pending_run(paths, report_adapters=(), retrieval_now=now)
        return runs.get(submitted.run_id)

    first = submit("quota-first", "2026-08")

    assert calls == ["https://api.tavily.com/search", "https://api.exa.ai/search", URL]
    assert first.status == "completed"
    # Exa searches the same title within the same domains, and returns the page text.
    assert exa_payloads[0]["query"] == "2026年8月贷款市场报价利率（LPR）公告"
    assert exa_payloads[0]["includeDomains"][0] == "www.chinamoney.com.cn"
    assert "contents" in exa_payloads[0]
    tavily = next(r for r in first.retrieval_ledger["requests"] if r["channel"] == "tavily")
    # The quota renews with the month: Tavily is not called again until then.
    assert datetime.fromisoformat(tavily["cache_expires_at"]).day == 1

    calls.clear()
    second = submit("quota-second", "2026-07")

    assert calls[0] == "https://api.exa.ai/search"
    attempts = {item["channel"]: item for item in second.retrieval_attempts}
    assert attempts["tavily"]["classification"] == "quota_exhausted"


def test_usdcny_1630_takes_a_whitelisted_media_page_on_the_lenient_path(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase two #10: the lenient hosts now include the media whitelist."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    media = "https://finance.sina.com.cn/money/forex/2026-08-27/usdcny-close.shtml"
    summary = "2026年8月27日，在岸人民币对美元16:30收盘报7.1234，较上一交易日上涨32个基点。"
    calls: list[str] = []

    def search(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(json.dumps({"results": [{"url": media, "content": summary}]}).encode(), media)

    def page(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(f"<html>{summary}</html>".encode(), request.full_url)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.http_transport.open_no_redirects", page)
    runs = RunRepository(paths.database)
    now = datetime.now(UTC)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="usdcny-1630-media",
        model_version_id="model-v0001",
        system_as_of=now + timedelta(days=1),
        release_event_id="usdcny-1630:2026-08-27",
        metric_ids=("CN_USDCNY_CLOSE_1630",),
        period="2026-08-27",
    )

    process_pending_run(paths, report_adapters=(), retrieval_now=now)

    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["fetched_url"]) == ("model_usable", media)
    [point] = EvidenceRepository(paths.database).metric_series(
        "CN_USDCNY_CLOSE_1630",
        mode=AsOfMode.SYSTEM,
        as_of=now + timedelta(days=2),
        definition_version="metric-catalog-v0001",
    )
    assert point.selected_value == 7.1234
    assert point.claims[0].provider == "finance.sina.com.cn"
