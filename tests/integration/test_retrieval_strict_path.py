"""Ticket 19: a search candidate is adopted only through its registered parser, strictly."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
from tests.integration.test_search_evidence import ANNOUNCEMENT, URL, prepare

UNTRUSTED = "https://mirror.example/lpr/2026-08"
OLD_URL = URL.replace("20260820", "20260720")
OLD_ANNOUNCEMENT = (
    ANNOUNCEMENT.decode()
    .replace("2026年8月20日", "2026年7月20日")
    .replace("2026-08-20", "2026-07-20")
    .encode()
)


class Page(BytesIO):
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, content: bytes, url: str) -> None:
        super().__init__(content)
        self.url = url

    def geturl(self) -> str:
        return self.url


def lpr_run(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    results: list[dict[str, str]],
    pages: dict[str, bytes],
    system_as_of: datetime | None = None,
) -> tuple[RunRecord, list[str], Any]:
    """Submit a targeted LPR refresh; Tavily returns ``results``, pages come from ``pages``."""
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")
    now = datetime.now(UTC)
    calls: list[str] = []

    def search(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(json.dumps({"results": results}).encode(), request.full_url)

    def official(request: Any, **kwargs: Any) -> Page:
        calls.append(request.full_url)
        return Page(pages[request.full_url], request.full_url)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", official)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="strict-path",
        model_version_id="model-v0001",
        system_as_of=system_as_of or now + timedelta(days=1),
        release_event_id="lpr:2026-08",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(paths, report_adapters=(), retrieval_now=now)
    return runs.get(submitted.run_id), calls, paths


def lpr_values(paths: Any) -> dict[str, float | None]:
    points = EvidenceRepository(paths.database).metric_series(
        "CN_LPR_1Y_5Y",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC) + timedelta(days=2),
        definition_version="metric-catalog-v0001",
    )
    return {p.dimensions["tenor"]: p.selected_value for p in points if p.period_end >= "2026-08"}


def test_whitelisted_host_with_parser_fills_the_gap_and_records_the_fetch(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored, calls, paths = lpr_run(
        tmp_path,
        monkeypatch,
        results=[{"url": URL, "content": "1年期LPR为3.0%，5年期以上LPR为3.5%"}],
        pages={URL: ANNOUNCEMENT},
    )

    assert stored.status == "completed"
    assert lpr_values(paths) == {"1y": 3.0, "5y_plus": 3.5}
    [validation] = stored.retrieval_ledger["candidate_validations"]
    official = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "official_http_get"
    )
    assert validation["outcome"] == "model_usable"
    assert (validation["fetched_url"], validation["raw_hash"], validation["parser_version"]) == (
        URL,
        official.raw_hash,
        "chinamoney-lpr-parser-v0002",
    )
    assert not {"run_attempt", "public_complete", "public_selected_claim_ids"} & set(validation)
    assert calls == ["https://api.tavily.com/search", URL]


@pytest.mark.parametrize(
    ("results", "pages", "reason"),
    [
        pytest.param([{"url": UNTRUSTED}], {}, "not_whitelisted", id="not-whitelisted"),
        pytest.param(
            [{"url": URL}], {URL: b"<html>not a release</html>"}, "parse_failed", id="parse"
        ),
        pytest.param(
            [{"url": OLD_URL}], {OLD_URL: OLD_ANNOUNCEMENT}, "period_mismatch", id="period"
        ),
        pytest.param(
            [{"url": URL}],
            {URL: ANNOUNCEMENT.replace(b"<time>2026-08-20 09:00</time>", b"")},
            "no_publication_date",
            id="no-date",
        ),
    ],
)
def test_each_rejected_candidate_names_its_reason_and_stores_no_value(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    results: list[dict[str, str]],
    pages: dict[str, bytes],
    reason: str,
) -> None:
    stored, _calls, paths = lpr_run(tmp_path, monkeypatch, results=results, pages=pages)

    assert stored.status == "action_required"
    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert (validation["outcome"], validation["reason"]) == ("not_model_usable", reason)
    assert validation["claim_ids"] == []
    assert lpr_values(paths) == {}


def test_page_dated_after_the_run_cutoff_is_not_adopted(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The run's cutoff is 09:05 Shanghai; the page says it was published at 10:00.
    cutoff = datetime(2026, 8, 20, 1, 5, tzinfo=UTC)
    later = ANNOUNCEMENT.replace(b"2026-08-20 09:00", b"2026-08-20 10:00")

    stored, calls, paths = lpr_run(
        tmp_path, monkeypatch, results=[{"url": URL}], pages={URL: later}, system_as_of=cutoff
    )

    assert calls == ["https://api.tavily.com/search", URL]
    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert validation["reason"] == "date_after_cutoff"
    assert lpr_values(paths) == {}


def test_search_value_a_decimal_shift_away_from_the_parsed_value_is_not_adopted(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The page says 3.0% and 3.5%; the search channel reported 30.0 and 35.0.
    stored, _calls, paths = lpr_run(
        tmp_path,
        monkeypatch,
        results=[{"url": URL, "content": "2026年8月20日 1年期LPR为30.0，5年期以上LPR为35.0"}],
        pages={URL: ANNOUNCEMENT},
    )

    [validation] = stored.retrieval_ledger["candidate_validations"]
    assert validation["reason"] == "search_value_mismatch"
    assert lpr_values(paths) == {}
    # The original stays on the record even though nothing was adopted.
    assert validation["raw_hash"]


@pytest.fixture(scope="module")
def searched(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[RuntimePaths, Any]]:
    """A full run whose every search candidate sits on a host no parser is registered for."""
    from tests.integration.test_gap_list import run, seed
    from tests.integration.test_worker_execution import runtime

    with pytest.MonkeyPatch.context() as monkeypatch:

        def offline(*args: Any, **kwargs: Any) -> Any:
            raise OSError("fixture offline")

        def search(request: Any, **kwargs: Any) -> Page:
            return Page(json.dumps({"results": [{"url": UNTRUSTED}]}).encode(), request.full_url)

        monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
        monkeypatch.setattr("pring_cycle.official_lpr.urlopen", offline)
        monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
        monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
        paths = runtime(tmp_path_factory.mktemp("retrieval-failed"))
        paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n", encoding="utf-8")
        seed(paths)
        run_id = run(paths)
        assert RunRepository(paths.database).get(run_id).status == "completed"
        yield paths, ProjectionSetRepository(paths.database).current()


def test_gap_list_names_each_failed_candidate_under_retrieval_failed(
    searched: tuple[RuntimePaths, Any],
) -> None:
    _paths, projection = searched
    gaps = projection.datasets["cycle_overview"]["gap_list"]

    failed = [gap for gap in gaps if gap["category"] == "retrieval_failed"]
    # Offline, the RRR backtrack cannot read the PBC column: unfinished, with no period
    # owed and no candidate to name (ADR-0028).
    backtrack = [gap for gap in failed if gap["reason"] == "backtrack_incomplete"]
    assert [gap["metric_id"] for gap in backtrack] == ["CN_RRR_EVENT"]
    failed = [gap for gap in failed if gap not in backtrack]
    assert failed
    for gap in failed:
        assert gap["due_period"]
        assert gap["candidates"] == [{"url": UNTRUSTED, "reason": "not_whitelisted"}]
    assert all(
        gap["candidates"] == [{"url": UNTRUSTED, "reason": "not_whitelisted"}]
        for gap in gaps
        if gap["category"] == "unconfigured" and "candidates" in gap
    )
    # A metric shown with its failed candidates is not listed again as plainly missing.
    listed = [gap["metric_id"] for gap in gaps]
    assert len(listed) == len(set(listed))


def test_page_shows_retrieval_failed_with_urls_and_reasons(
    searched: tuple[RuntimePaths, Any],
) -> None:
    from pring_cycle.dashboard import _home_page

    _paths, projection = searched
    page = str(_home_page(projection))

    for label in ("检索未通过", UNTRUSTED, "不在白名单"):
        assert label in page
