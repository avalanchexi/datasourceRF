"""Worker gaps 01: a full run for 10-15 holds 10-15's central parity.

The run of 10-15 (run-2b21b77b…) held 10-14's and listed the parity as one period behind:
the PBC column was read as an announcement, CLS's "人民币兑美元中间价报6.7253" matched no
rule, and when search came back with the PBC address again the negative cache held it back,
listed only as "retrieval_blocked". Here the run's official and search routes are served
from that run's originals (tests/fixtures/central_parity); the 10-15 announcement, which the
run never opened, is written as test_central_parity_official_listing writes it.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.freshness import gap_list, record_run_freshness
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import FetchedOfficialContextDocument
from pring_cycle.retrieval import RUN_SEARCH_LIMITS
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.trading_calendar import TradingCalendar
from tests.conftest import install_runtime_clock
from tests.fixtures.model_registration import prepared_request, save, submit
from tests.integration.test_central_parity_official_listing import (
    ANNOUNCEMENT_1015,
    ANNOUNCEMENT_1015_BODY,
    COLUMN,
)
from tests.integration.test_retrieval_strict_path import Page
from tests.integration.test_trading_calendar import record_sse_calendar

FIXTURES = Path(__file__).parents[1] / "fixtures" / "central_parity"
LISTING = COLUMN + "index.html"
CLS = "https://www.cls.cn/detail/2505221"
PARITY = "CN_USDCNY_CENTRAL_PARITY"
MEMBER = {"currency_pair": "USD/CNY", "quote_direction": "CNY per USD"}
# The 10-15 run's frozen cutoff (10-16 16:08:36 Beijing).
RUN_CUTOFF = datetime(2026, 10, 16, 8, 8, 36, tzinfo=UTC)


@pytest.fixture
def run_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """The run's own cutoff: on a later day the parity due would be a later session than
    10-15, and holding 10-15 would list a freshness gap."""
    install_runtime_clock(monkeypatch, request, RUN_CUTOFF)


def sessions() -> list[date]:
    day, days = date(2026, 10, 15), []
    while len(days) < 60:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days


def parity_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    official: dict[str, bytes],
    search_results: list[str],
    pages: dict[str, bytes],
    throttled: bool = False,
) -> tuple[RuntimePaths, str, str]:
    """A full run for 10-15 holding 10-14's parity; its official pages, search results
    and media pages are the ones given, every other address fails as offline, or, with
    ``throttled``, a PBC page answers 429."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, _ = prepared_request(paths)
    submit(paths, save(paths, request))
    model_id = json.loads(capsys.readouterr().out)["model_version_id"]
    version = str(request["manifest"]["metric_catalog_version"])
    record_sse_calendar(paths, sessions())
    known = datetime(2026, 10, 14, 1, 15, tzinfo=UTC)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id=PARITY,
            definition_version=version,
            period_kind="business_day",
            period_start="2026-10-14",
            period_end="2026-10-14",
            dimensions=MEMBER,
            value=6.7249,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="cny_per_usd",
            provider="tushare_news",
            source_reference="fixture:central-parity:2026-10-14",
            release_event_id="fixture:central-parity:2026-10-14",
            release_at=known,
            public_available_at=known,
            fetched_at=known,
            available_at=known,
            # As the catalog's P2 parity is: its official claims carry the same.
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")

    def fetch_official(url: str) -> FetchedOfficialContextDocument:
        if url not in official:
            if throttled and "pbc.gov.cn" in url:
                return FetchedOfficialContextDocument(b"", "text/html", url, 429)
            raise OSError("fixture_official_page_unavailable")
        return FetchedOfficialContextDocument(official[url], "text/html", url, 200)

    def search(request: Any, *, timeout: float) -> Page:
        query = json.loads(request.data)["query"]
        found = [{"url": url} for url in search_results] if "中间价" in query else []
        return Page(json.dumps({"results": found}).encode(), request.full_url)

    def fetch_page(request: Any, **kwargs: Any) -> Page:
        if request.full_url not in pages:
            raise OSError("fixture_page_unavailable")
        return Page(pages[request.full_url], request.full_url)

    monkeypatch.setattr(
        "pring_cycle.official_context._fetch_official_context_document", fetch_official
    )
    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    # Nothing else is held here, so every other gap searches before the P2 parity; the real
    # run of 10-15 still had searches left for it.
    monkeypatch.setitem(RUN_SEARCH_LIMITS, "tavily", 1000)
    monkeypatch.setattr("pring_cycle.http_transport.open_no_redirects", fetch_page)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-10-15",
        client_request_id="central-parity-10-15",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    definitions = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(model_id)
    ).metric_definitions
    record_run_freshness(
        paths.database, run.run_id, definitions, datetime.now(UTC), TradingCalendar()
    )
    return paths, run.run_id, version


def held(paths: RuntimePaths, version: str) -> dict[str, float]:
    return {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            PARITY, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    }


def parity_gaps(paths: RuntimePaths, run_id: str) -> list[dict[str, object]]:
    definitions = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(
            RunRepository(paths.database).get(run_id).model_version_id
        )
    ).metric_definitions
    return [
        gap for gap in gap_list(paths.database, run_id, definitions) if gap["metric_id"] == PARITY
    ]


@pytest.mark.usefixtures("run_clock")
def test_the_day_s_announcement_on_the_pbc_column_completes_the_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths, run_id, version = parity_run(
        tmp_path,
        monkeypatch,
        capsys,
        official={
            LISTING: (FIXTURES / "pbc_125925_index_20261015.html").read_bytes(),
            ANNOUNCEMENT_1015: ANNOUNCEMENT_1015_BODY,
        },
        search_results=[],
        pages={},
    )

    assert held(paths, version)["2026-10-15"] == 6.7253
    assert parity_gaps(paths, run_id) == []


@pytest.mark.usefixtures("run_clock")
def test_cls_s_wording_found_by_search_completes_the_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The day's announcement does not answer; search finds CLS's page, as on 10-15."""
    paths, run_id, version = parity_run(
        tmp_path,
        monkeypatch,
        capsys,
        official={LISTING: (FIXTURES / "pbc_125925_index_20261015.html").read_bytes()},
        search_results=[CLS],
        pages={CLS: (FIXTURES / "cls_2505221_20261015.html").read_bytes()},
    )

    assert held(paths, version)["2026-10-15"] == 6.7253
    assert parity_gaps(paths, run_id) == []


@pytest.mark.usefixtures("run_clock")
def test_a_candidate_the_negative_cache_holds_back_names_the_first_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The announcement the column links for 10-15 is another day's (4-30's original): the
    direct request fails, and search coming back with the column is held back by the cache
    that failure set. Both are listed: the cache's hold and why the request first failed."""
    from pring_cycle.cockpit_operations import data_chain
    from tests.web.test_dashboard_contract import _text

    paths, run_id, version = parity_run(
        tmp_path,
        monkeypatch,
        capsys,
        official={
            LISTING: (FIXTURES / "pbc_125925_index_20261015.html").read_bytes(),
            ANNOUNCEMENT_1015: (FIXTURES / "pbc_125925_20260430.html").read_bytes(),
        },
        search_results=[LISTING],
        pages={},
    )

    assert "2026-10-15" not in held(paths, version)
    (gap,) = parity_gaps(paths, run_id)
    assert gap["category"] == "retrieval_failed"
    assert gap["candidates"] == [
        {
            "url": LISTING,
            "reason": "negative_cache_active",
            "first_cause": "official_context_period_identity_mismatch",
        }
    ]
    run = RunRepository(paths.database).get(run_id)
    page = _text(data_chain([run], run, {"gaps": [], "requests": []}, {"run": run_id}, None))
    assert "被负缓存拦下，首因 官方页日期与所需期不符" in page


@pytest.mark.usefixtures("run_clock")
def test_a_candidate_a_host_wide_cache_holds_back_names_the_first_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The PBC throttles a page another gap asked for first: its 429 holds back every PBC
    page for a while, the parity's own requests and the column search came back with among
    them. The column's hold still names why that earlier request failed."""
    paths, run_id, _ = parity_run(
        tmp_path,
        monkeypatch,
        capsys,
        official={},
        search_results=[LISTING],
        pages={},
        throttled=True,
    )

    from pring_cycle.cockpit_operations import data_chain
    from tests.web.test_dashboard_contract import _text

    (gap,) = parity_gaps(paths, run_id)
    assert gap["candidates"] == [
        {
            "url": LISTING,
            "reason": "negative_cache_active",
            "first_cause": "official_context_source_http_status_invalid",
        }
    ]
    run = RunRepository(paths.database).get(run_id)
    page = _text(data_chain([run], run, {"gaps": [], "requests": []}, {"run": run_id}, None))
    assert "被负缓存拦下，首因 官方页返回异常状态" in page
