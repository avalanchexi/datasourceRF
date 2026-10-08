"""Phase two #12: a full run finds second-quarter GDP two pages back on the NBS listing."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import effective_model_manifest
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
from tests.integration.test_trading_calendar import record_sse_calendar

# The newest model, whatever it is numbered.
CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])

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
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert [
        (r.parameters["source_url"], r.state)
        for r in receipts
        if r.parameters.get("family") == "nbs_gdp" and r.api_name == "official_http_get"
    ] == [(ARTICLE, "validated")]
    # The run reads each page of the list once, whichever period first needs it (lookback
    # L05); the fixture serves three, and the fourth fails each of its tries.
    pages = [
        (r.parameters["source_url"], r.state)
        for r in receipts
        if r.api_name == "official_listing_get" and r.parameters["source_url"].startswith(LISTING)
    ]
    assert pages[:3] == [
        (LISTING, "validated"),
        (LISTING + "index_1.html", "validated"),
        (LISTING + "index_2.html", "validated"),
    ]
    assert pages[3:] == [(LISTING + "index_3.html", "failed")] * 3


def test_the_day_s_reverse_repo_notice_is_read_from_the_omo_column(tmp_path: Path) -> None:
    """Event #04: the real run of 2026-09-25 parsed the OMO column itself as a notice. 9/23
    listed two notices; the central bank bills (no. 188) is passed over for no. 187."""
    from pring_cycle.catalog import METRIC_CATALOG_VERSION
    from pring_cycle.official_context import refresh_official_context_document

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    column = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
    bills, repo = (
        column + "2026092311141529051/index.html",
        column + "2026092308513432696/index.html",
    )
    documents = {
        column + "index.html": FIXTURES / "official_listing" / "pbc_125475_index_20260924.html",
        bills: FIXTURES / "pbc_omo_notice" / "2026092311141529051.html",
        repo: FIXTURES / "pbc_omo_notice" / "2026092308513432696.html",
    }
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        return FetchedOfficialContextDocument(documents[url].read_bytes(), "text/html", url, 200)

    refresh_official_context_document(
        paths,
        family="pbc_omo_notice",
        source_url=column + "index.html",
        expected_period="2026-09-23",
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
    )

    assert requested == [column + "index.html", bills, repo]
    evidence = EvidenceRepository(paths.database)
    values = {
        metric: [
            p.selected_value
            for p in evidence.metric_series(
                metric,
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=METRIC_CATALOG_VERSION,
            )
            if p.period_end == "2026-09-23"
        ]
        for metric in ("CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT")
    }
    assert values == {"CN_OMO_7D_RATE": [1.4], "CN_OMO_7D_AMOUNT": [80.0]}


def _omo_gaps(
    tmp_path: Path, source_url: str, documents: dict[str, Path]
) -> tuple[RuntimePaths, list[dict[str, object]]]:
    """Refresh the OMO notices of 9/23 inside a run, then read that run's gap list."""
    from pring_cycle.acquisition import own_acquisitions
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.freshness import gap_list, record_run_freshness
    from pring_cycle.models import (
        EFFECTIVE_CATALOG_VERSION,
        ModelRepository,
        effective_model_manifest,
    )
    from pring_cycle.official_context import refresh_official_context_document
    from pring_cycle.trading_calendar import TradingCalendar

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date="2026-09-23",
        client_request_id="omo-sibling-notice",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(documents[url].read_bytes(), "text/html", url, 200)

    with (
        own_acquisitions(
            paths.database, run.run_id, "direct_context_refresh", metric_ids=("CN_OMO_7D_AMOUNT",)
        ),
        contextlib.suppress(ValueError),
    ):
        refresh_official_context_document(
            paths,
            family="pbc_omo_notice",
            source_url=source_url,
            expected_period="2026-09-23",
            fetched_at=datetime.now(UTC),
            fetcher=fetch,
            # The run's own catalog: its batch reads only that catalog's attempts (ticket 19).
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
    definitions = ContextProjectionRules.from_manifest(
        models.manifest(CURRENT_MODEL)
    ).metric_definitions
    # What the batch holds decides what is missing (ticket 21).
    record_run_freshness(
        paths.database, run.run_id, definitions, datetime.now(UTC), TradingCalendar()
    )
    return paths, gap_list(paths.database, run.run_id, definitions)


OMO_COLUMN = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
OMO_BILLS = OMO_COLUMN + "2026092311141529051/index.html"
OMO_REPO = OMO_COLUMN + "2026092308513432696/index.html"
OMO_DOCUMENTS = {
    OMO_COLUMN + "index.html": FIXTURES / "official_listing" / "pbc_125475_index_20260924.html",
    OMO_BILLS: FIXTURES / "pbc_omo_notice" / "2026092311141529051.html",
    OMO_REPO: FIXTURES / "pbc_omo_notice" / "2026092308513432696.html",
}


def test_a_same_day_bills_notice_passed_over_is_skipped_not_rejected(tmp_path: Path) -> None:
    """Run findings 04: no. 188 (central bank bills) is passed over by design for no. 187;
    its receipt says so, and the gap list no longer shows it as a rejection."""
    paths, gaps = _omo_gaps(tmp_path, OMO_COLUMN + "index.html", OMO_DOCUMENTS)

    checks = {
        r.parameters["source_url"]: (r.state, r.acquisition_id)
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "official_http_get"
    }
    with sqlite3.connect(paths.database) as connection:
        structure = dict(
            connection.execute(
                "SELECT acquisition_id, structure_check || ':' || coalesce(rejection_reason, '') "
                "FROM acquisition_request"
            ).fetchall()
        )
    assert structure[checks[OMO_BILLS][1]] == "skipped:official_context_table_schema_mismatch"
    assert structure[checks[OMO_REPO][1]] == "passed:"
    assert [gap for gap in gaps if gap["category"] == "rejected"] == []


def test_a_day_with_only_a_bills_notice_is_still_rejected(tmp_path: Path) -> None:
    """With no reverse repo notice to fall back on, the mismatch is a real failure."""
    paths, gaps = _omo_gaps(tmp_path, OMO_BILLS, OMO_DOCUMENTS)

    (receipt,) = (
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "official_http_get"
    )
    with sqlite3.connect(paths.database) as connection:
        check = connection.execute(
            "SELECT structure_check FROM acquisition_request WHERE acquisition_id=?",
            (receipt.acquisition_id,),
        ).fetchone()[0]
    assert check == "rejected"
    # Still missing, it shows the refusal through its own category (ticket 21).
    (omo,) = (gap for gap in gaps if gap["metric_id"] == "CN_OMO_7D_AMOUNT")
    assert (omo["category"], omo["reason"]) == (
        "ingest_rejected",
        "official_context_table_schema_mismatch",
    )


def test_a_passed_over_notice_does_not_stop_the_next_under_the_retrieval_ledger(
    tmp_path: Path,
) -> None:
    """Searched candidates reach the notices through the retrieval ledger, which used to refuse
    to go on after an acquisition that did not validate."""
    from pring_cycle.catalog import METRIC_CATALOG_VERSION
    from pring_cycle.models import (
        EFFECTIVE_CATALOG_VERSION,
        ModelRepository,
        effective_model_manifest,
    )
    from pring_cycle.official_context import refresh_official_context_document
    from pring_cycle.retrieval import RetrievalAdapterResponse
    from pring_cycle.retrieval_ledger import RetrievalLedger

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-23",
        client_request_id="omo-sibling-ledger",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
        release_event_id="omo:2026-09-23",
        metric_ids=("CN_OMO_7D_AMOUNT",),
        period="2026-09-23",
    )

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(
            OMO_DOCUMENTS[url].read_bytes(), "text/html", url, 200
        )

    def operation(started: Callable[[str], None]) -> RetrievalAdapterResponse:
        refresh_official_context_document(
            paths,
            family="pbc_omo_notice",
            source_url=OMO_COLUMN + "index.html",
            expected_period="2026-09-23",
            fetched_at=datetime.now(UTC),
            fetcher=fetch,
            definition_version=METRIC_CATALOG_VERSION,
            on_acquisition_started=started,
        )
        return RetrievalAdapterResponse("candidate_source", classification="document_validated")

    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, EFFECTIVE_CATALOG_VERSION)
    response = ledger.trace_acquisition(
        run.run_id, "official", "omo:2026-09-23", OMO_COLUMN + "index.html", operation
    )

    assert response.status == "candidate_source", response
    with sqlite3.connect(paths.database) as connection:
        classifications = [
            row[0]
            for row in connection.execute(
                "SELECT classification FROM retrieval_physical_request ORDER BY rowid"
            )
        ]
    assert classifications[:2] == [
        "intermediate_acquisition_validated",
        "intermediate_candidate_skipped",
    ]


@pytest.mark.parametrize(
    "metric_ids", [("CN_OMO_7D_AMOUNT",), ("CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT")]
)
def test_the_day_s_notice_stores_its_rate_beside_the_amount_while_an_older_rate_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metric_ids: tuple[str, ...]
) -> None:
    """Run findings 10: 9/29's notice stated 1.4% and 905, and only the amount was stored, the
    rate in force from an earlier notice staying behind. A notice is stored whole, and a rate
    held from an earlier day does not keep the day's own out (ADR-0028)."""
    from pring_cycle.models import ModelRepository, effective_model_manifest
    from pring_cycle.official_context import refresh_official_context_document
    from pring_cycle.worker import _official_context_retrieval

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    version = str(effective_model_manifest()["metric_catalog_version"])
    previous, today = OMO_REPO, OMO_COLUMN + "2026092408454713496/index.html"
    documents = {
        previous: FIXTURES / "pbc_omo_notice" / "2026092308513432696.html",
        today: FIXTURES / "pbc_omo_notice" / "2026092408454713496.html",
    }

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(documents[url].read_bytes(), "text/html", url, 200)

    refresh_official_context_document(
        paths,
        family="pbc_omo_notice",
        source_url=previous,
        expected_period="2026-09-23",
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
        definition_version=version,
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-24",
        client_request_id="omo-rate-beside-amount",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
        release_event_id="omo:2026-09-24",
        metric_ids=metric_ids,
        period="2026-09-24",
        source_url=today,
    )
    assert run.retrieval_scope is not None
    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    _official_context_retrieval(
        paths, run.retrieval_scope, datetime.now(UTC), run_id=run.run_id, definition_version=version
    )

    evidence = EvidenceRepository(paths.database)
    assert {
        metric: {
            p.period_end: p.selected_value
            for p in evidence.metric_series(
                metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
        }
        for metric in ("CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT")
    } == {
        "CN_OMO_7D_RATE": {"2026-09-23": 1.4, "2026-09-24": 1.4},
        "CN_OMO_7D_AMOUNT": {"2026-09-23": 80.0, "2026-09-24": 515.0},
    }


TOOLS = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/"
TOOLS_JULY = TOOLS + "2026080416515912098/index.html"
TOOLS_AUGUST = TOOLS + "2026090214213398506/index.html"


def _confirmation_model(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> tuple[dict[str, Any], str]:
    """A registered model reading the stage narrative's key indicators (model-v0015)."""
    from pring_cycle.confirmation import MANIFEST_FIELDS
    from pring_cycle.models import model_v0015_manifest

    request, _ = prepared_request(paths)
    new = model_v0015_manifest()
    request["manifest"].update({field: new[field] for field in MANIFEST_FIELDS})
    submit(paths, save(paths, request))
    return request, json.loads(capsys.readouterr().out)["model_version_id"]


@pytest.mark.usefixtures("runtime_clock")
def test_a_history_month_the_lookback_reads_is_requested_through_its_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lookback L01: a month the stage narrative reads back to, older than the newest out,
    was held as unknown publication and never requested. It is out by its own release
    rule: its release is looked up on the column's listing, and what came back is kept."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request, model_id = _confirmation_model(paths, capsys)
    august_page = (
        Path(__file__).parents[2]
        / ".scratch/pring-data-acquisition-repair/evidence-13"
        / "4d104698df655c19c27e4a697ef4bd55cc1c0b30ad9aae265e7db3c955bc90c2"
    )
    documents = {
        TOOLS + "index.html": FIXTURES / "official_listing" / "pbc_5727710_index_20260925.html",
        TOOLS_AUGUST: august_page,
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
        client_request_id="tool-liquidity-history",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")

    FullRunRetrieval(paths).retrieve(run)

    plan = runs.full_retrieval_plan(run.run_id)["initial"]
    assert {
        s["period"]: s["release_status"]
        for s in plan["scopes"]
        if s["metric_ids"] == ["CN_TOOL_LIQUIDITY_MONTHLY"]
    } == {"2026-06": "released", "2026-07": "released", "2026-08": "released"}
    reads = [
        (r.parameters["period"], r.api_name, r.parameters["source_url"], r.state)
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "pbc_tool_liquidity_monthly"
    ]
    # The column is read once for the run's three months (lookback L05). July's release is
    # requested; the fixture does not serve it, and the receipt says so.
    assert [read[2:] for read in reads if read[1] == "official_listing_get"] == [
        (TOOLS + "index.html", "validated")
    ]
    assert ("2026-07", "official_http_get", TOOLS_JULY, "failed") in reads
    assert ("2026-08", "official_http_get", TOOLS_AUGUST, "validated") in reads
    # The column's directory, which answers 403, is never read.
    assert TOOLS not in requested
    august = EvidenceRepository(paths.database).metric_series(
        "CN_TOOL_LIQUIDITY_MONTHLY",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=request["manifest"]["metric_catalog_version"],
    )
    assert {point.period_end for point in august} == {"2026-08-31"}


@pytest.mark.usefixtures("runtime_clock")
def test_an_earlier_reverse_repo_day_is_still_looked_up_on_the_omo_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An earlier session is not searched day by day (ticket 19), but a release listing
    can still establish it: the OMO column is read for each, the cascade stays shut."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _request, model_id = _confirmation_model(paths, capsys)
    # The window's 120 sessions, so the OMO amount is read on every one of them.
    first = date(2026, 3, 2)
    record_sse_calendar(
        paths,
        (
            day
            for n in range((date(2026, 9, 24) - first).days + 1)
            if (day := first + timedelta(days=n)).weekday() < 5
        ),
    )

    def fetch(url: str) -> FetchedOfficialContextDocument:
        if url not in OMO_DOCUMENTS:
            raise OSError("fixture_official_page_unavailable")
        return FetchedOfficialContextDocument(
            OMO_DOCUMENTS[url].read_bytes(), "text/html", url, 200
        )

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-24",
        client_request_id="omo-earlier-session",
        model_version_id=model_id,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")

    FullRunRetrieval(paths).retrieve(run)

    plan = runs.full_retrieval_plan(run.run_id)["initial"]
    (earlier,) = (
        scope
        for scope in plan["scopes"]
        if "CN_OMO_7D_AMOUNT" in scope["metric_ids"] and scope["period"] == "2026-09-23"
    )
    assert earlier["release_status"] == "earlier_session_not_searched"
    reads = [
        (r.api_name, r.parameters["source_url"], r.parameters["period"], r.state)
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "pbc_omo_notice"
    ]
    assert ("official_http_get", OMO_REPO, "2026-09-23", "validated") in reads
    # The column's first page is read once for all of the run's days, not once each
    # (lookback L05: 100 days had read the one page 100 times). The fixture does not serve
    # the second page: it fails each of its tries, and is not asked for again day by day.
    listing = [read for read in reads if read[0] == "official_listing_get"]
    assert [read[1] for read in listing] == [OMO_COLUMN + "index.html"] + [
        OMO_COLUMN + "17081-2.html"
    ] * 3
    # The days before the first page are not covered by what was read; 9/23 was found.
    from pring_cycle.full_retrieval import _listing_uncovered

    uncovered = _listing_uncovered(paths, run.run_id, plan["scopes"])
    # Its second page failed each read: the gap says which listing and why it stopped.
    assert uncovered[("CN_OMO_7D_AMOUNT", "2026-08-31")] == {
        "listing": OMO_COLUMN + "index.html",
        "stopped": "unreadable_page",
        "pages_read": 4,
        "oldest_entry": "20260901",
    }
    assert ("CN_OMO_7D_AMOUNT", "2026-09-23") not in uncovered
    with sqlite3.connect(paths.database) as connection:
        outcomes = dict(
            connection.execute(
                "SELECT channel, outcome FROM run_retrieval_attempt "
                "WHERE run_id=? AND release_event_id=?",
                (run.run_id, earlier["release_event_id"]),
            ).fetchall()
        )
    # Only the official listing was open to it; no channel searched.
    assert outcomes.pop("official") == "verified"
    assert set(outcomes.values()) == {"not_configured"}
    # A day the listing read did not reach is not searched either: an earlier session is
    # not searched day by day (ticket 19), whatever stopped the listing.
    (uncovered_day,) = (
        scope
        for scope in plan["scopes"]
        if "CN_OMO_7D_AMOUNT" in scope["metric_ids"] and scope["period"] == "2026-08-31"
    )
    with sqlite3.connect(paths.database) as connection:
        channels = dict(
            connection.execute(
                "SELECT channel, classification FROM run_retrieval_attempt "
                "WHERE run_id=? AND release_event_id=? AND outcome <> 'not_configured'",
                (run.run_id, uncovered_day["release_event_id"]),
            ).fetchall()
        )
    assert channels == {"official": "listing_not_covered_unreadable_page"}


def test_a_listing_read_to_the_site_s_page_limit_hands_the_period_on_to_search(
    tmp_path: Path,
) -> None:
    """Lookback L05: a run reads at most 50 listing pages a site. A period they do not
    reach is not covered, which is no failure of the source to cache: search is next, on
    its own budget."""
    from pring_cycle.catalog import METRIC_CATALOG_VERSION
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository
    from pring_cycle.official_context import (
        LISTING_PAGES_PER_SITE,
        ListingScan,
        refresh_official_context_document,
    )
    from pring_cycle.retrieval import RetrievalBudget, RetrievalRequest, run_retrieval_cascade
    from pring_cycle.retrieval_ledger import RetrievalLedger

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-23",
        client_request_id="listing-page-limit",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
        release_event_id="cpi:2026-02",
        metric_ids=("CN_CORE_CPI",),
        period="2026-02",
    )
    # Every page lists September; the list goes on for 500 pages.
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        index = int(url.rsplit("_", 1)[1].removesuffix(".html")) if "index_" in url else 0
        page = (
            f'<a href="./202609/t202609{1 + index % 28:02d}_{index}.html">其他发布</a>'
            f'<script>createPageHTML(500, {index}, "index", "html");</script>'
        )
        return FetchedOfficialContextDocument(page.encode(), "text/html", url, 200)

    ledger = RetrievalLedger(paths.database)
    ledger.bind_run(run, EFFECTIVE_CATALOG_VERSION)

    def official(event: str) -> object:
        return ledger.trace_acquisition(
            run.run_id,
            "official",
            event,
            LISTING,
            lambda started: (
                refresh_official_context_document(
                    paths,
                    family="nbs_core_cpi",
                    source_url=LISTING,
                    expected_period="2026-02",
                    fetched_at=datetime.now(UTC),
                    fetcher=fetch,
                    definition_version=METRIC_CATALOG_VERSION,
                    on_acquisition_started=started,
                    listings=ListingScan(),
                ).release_event_id
            ),
        )

    searched: list[str] = []
    result = run_retrieval_cascade(
        RetrievalRequest("cpi:2026-02", ("CN_CORE_CPI",), "P1"),
        {"official": official, "tavily": lambda event: searched.append(event)},  # type: ignore[dict-item]
        RetrievalBudget(),
    )

    assert len(requested) == LISTING_PAGES_PER_SITE
    official_attempt = next(a for a in result.attempts if a.channel == "official")
    assert (official_attempt.outcome, official_attempt.classification) == (
        "failed",
        "listing_not_covered_page_limit",
    )
    assert searched == ["cpi:2026-02"]
    with sqlite3.connect(paths.database) as connection:
        (expires,) = connection.execute(
            "SELECT cache_expires_at FROM retrieval_physical_request "
            "WHERE classification='listing_not_covered_page_limit'"
        ).fetchall()
    # Not a source failure to wait out: nothing is held back by it.
    assert expires == (None,)


def _omo_run(paths: RuntimePaths, day: str) -> Any:
    from pring_cycle.models import ModelRepository

    models = ModelRepository(paths.database)
    try:
        models.active()
    except LookupError:
        models.register(effective_model_manifest())
        models.activate(CURRENT_MODEL, explicitly_approved=True)
    return RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-30",
        client_request_id=f"omo-{day}",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
        release_event_id=f"omo:{day}",
        metric_ids=("CN_OMO_7D_AMOUNT",),
        period=day,
    )


def test_a_resumed_run_reads_on_from_the_listing_pages_it_had_read(tmp_path: Path) -> None:
    """Lookback L05: a run reads a listing once. Resumed in another process, it reads the
    pages it kept from their receipts, and goes on from the last."""
    from pring_cycle import official_context
    from pring_cycle.acquisition import own_acquisitions
    from pring_cycle.official_context import refresh_official_context_document
    from tests.adapters.test_official_listing_scan import Site, omo_column, omo_url

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    run = _omo_run(paths, "2026-09-23")
    site = Site(omo_column())

    def refresh(day: str) -> None:
        with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
            refresh_official_context_document(
                paths,
                family="pbc_omo_notice",
                source_url=omo_url(1),
                expected_period=day,
                fetched_at=datetime.now(UTC),
                fetcher=site,
            )

    refresh("2026-09-23")
    official_context._RUN_LISTINGS.clear()  # Another process: nothing read in memory.
    refresh("2026-09-24")
    with pytest.raises(ValueError, match="official_context_release_link_not_found"):
        refresh("2026-09-18")

    listing = [url for url in site.requested if "/17081-" in url or url.endswith("5/index.html")]
    assert listing == [omo_url(1), omo_url(2), omo_url(3), omo_url(4)]


def test_a_day_s_notices_are_read_when_the_page_after_them_fails(tmp_path: Path) -> None:
    """9/23's notices end the first page: the next one, which could list more of them,
    fails. A failed read ends its retrieval; the retry reads the notices found. An earlier
    day waits on that page through the retrieval's own retries, and is then not covered,
    not found missing."""
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION
    from pring_cycle.official_context import ListingScan, refresh_official_context_document
    from pring_cycle.retrieval import (
        RetrievalBudget,
        RetrievalRequest,
        RetrievalResult,
        run_retrieval_cascade,
    )
    from pring_cycle.retrieval_ledger import RetrievalLedger
    from tests.adapters.test_official_listing_scan import omo_page, omo_url

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    documents = {
        omo_url(1): omo_page(
            1,
            [
                "2026092508450000001",
                "2026092408454713496",
                "2026092311141529051",
                "2026092308513432696",
            ],
            following=2,
        ),
        OMO_BILLS: OMO_DOCUMENTS[OMO_BILLS].read_bytes(),
        OMO_REPO: OMO_DOCUMENTS[OMO_REPO].read_bytes(),
    }
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url not in documents:
            raise OSError("fixture_official_page_unavailable")
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    scan = ListingScan()

    def retrieve(day: str) -> RetrievalResult:
        run = _omo_run(paths, day)
        ledger = RetrievalLedger(paths.database)
        ledger.bind_run(run, EFFECTIVE_CATALOG_VERSION)
        return run_retrieval_cascade(
            RetrievalRequest(f"omo:{day}", ("CN_OMO_7D_AMOUNT",), "P1"),
            {
                "official": lambda event: ledger.trace_acquisition(
                    run.run_id,
                    "official",
                    event,
                    omo_url(1),
                    lambda started: (
                        refresh_official_context_document(
                            paths,
                            family="pbc_omo_notice",
                            source_url=omo_url(1),
                            expected_period=day,
                            fetched_at=datetime.now(UTC),
                            fetcher=fetch,
                            on_acquisition_started=started,
                            listings=scan,
                        ).release_event_id
                    ),
                )
            },
            RetrievalBudget(),
        )

    found = retrieve("2026-09-23")
    assert [(a.outcome, a.classification) for a in found.attempts if a.channel == "official"] == [
        ("failed", "transient_transport_error"),
        ("verified", None),
    ]
    assert requested == [omo_url(1), omo_url(2), OMO_BILLS, OMO_REPO]

    earlier = retrieve("2026-09-01")
    assert [a.classification for a in earlier.attempts if a.channel == "official"] == [
        "transient_transport_error",
        "transient_transport_error",
        "listing_not_covered_unreadable_page",
    ]
    assert requested[4:] == [omo_url(2)] * 2


@pytest.mark.usefixtures("runtime_clock")
def test_a_site_s_listings_share_its_pages_newest_period_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lookback L05: the plan lists a family's periods oldest first, and the first listing
    read went back a year before the next was read at all, the site's 50 pages spent on it.
    A run reads its listings first, in turn, a page each: the readings list reaches back to
    its August while the release list is still on September."""
    from types import SimpleNamespace

    from pring_cycle import full_retrieval
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION
    from pring_cycle.official_context import LISTING_PAGES_PER_SITE, run_listings
    from tests.adapters.test_official_listing_scan import nbs_filler, nbs_page, nbs_url

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    run = _share_run(paths)
    readings = "https://www.stats.gov.cn/sj/zxfbhjd/"
    documents = {}
    for index in range(LISTING_PAGES_PER_SITE + 5):
        # The release list stays in September, page after page.
        documents[nbs_url(LISTING, index)] = nbs_page(
            index, 500, [nbs_filler(date(2026, 9, 30) - timedelta(days=index % 20), index)]
        )
        day = date(2026, 9, 20) if index == 0 else date(2026, 8, 20)
        documents[nbs_url(readings, index)] = nbs_page(index, 500, [nbs_filler(day, index)])
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        return FetchedOfficialContextDocument(documents[url], "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    # Every scope released and missing: what is read is the listings' turn alone.
    monkeypatch.setattr(
        full_retrieval.FullRunRetrieval, "_gate", lambda *_args: ("released", False)
    )
    monkeypatch.setattr(
        full_retrieval, "select_retrieval_input", lambda *_args: SimpleNamespace(complete=False)
    )

    def scope(metric: str, period: str, source: str) -> dict[str, Any]:
        return {
            "release_event_id": f"full:{metric}:{period}",
            "metric_ids": [metric],
            "period": period,
            "priority": "P1",
            "source_url": source,
        }

    full_retrieval.FullRunRetrieval(paths)._read_listings(
        run,
        [
            scope("CN_CORE_CPI", "2025-01", LISTING),
            scope("CN_CORE_CPI", "2026-08", LISTING),
            scope("CN_INDUSTRIAL_VA", "2026-08", readings),
        ],
        EFFECTIVE_CATALOG_VERSION,
    )

    # In turn, a page each: the readings list reaches August on its second page, before
    # the release list has spent the site's pages, which it then reads on with.
    assert requested[:4] == [LISTING, readings, LISTING + "index_1.html", readings + "index_1.html"]
    assert [url for url in requested if url.startswith(readings)] == [
        readings,
        readings + "index_1.html",
    ]
    assert len(requested) == LISTING_PAGES_PER_SITE
    listings = run_listings(paths, run.run_id)
    assert listings.ended == {LISTING: "page_limit"}
    assert listings.reads == {LISTING: LISTING_PAGES_PER_SITE - 2, readings: 2}


def _share_run(paths: RuntimePaths) -> Any:
    from pring_cycle.models import ModelRepository

    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-09-30",
        client_request_id="listing-shares",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )
    return runs.advance(submitted.run_id, "refreshing_evidence")


@pytest.mark.usefixtures("runtime_clock")
def test_listings_listing_no_dates_share_the_site_s_pages_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listing whose entries carry no date never reaches back to a period: it takes its
    turn like any other, and does not spend the site's pages alone."""
    from types import SimpleNamespace

    from pring_cycle import full_retrieval
    from pring_cycle.models import EFFECTIVE_CATALOG_VERSION
    from pring_cycle.official_context import LISTING_PAGES_PER_SITE, run_listings
    from tests.adapters.test_official_listing_scan import nbs_page, nbs_url

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    run = _share_run(paths)
    readings = "https://www.stats.gov.cn/sj/zxfbhjd/"
    documents = {
        nbs_url(listing, index): nbs_page(index, 500, [(f"./other_{index}.html", "其他")])
        for listing in (LISTING, readings)
        for index in range(LISTING_PAGES_PER_SITE)
    }
    monkeypatch.setattr(
        "pring_cycle.official_context._fetch_official_context_document",
        lambda url: FetchedOfficialContextDocument(documents[url], "text/html", url, 200),
    )
    monkeypatch.setattr(
        full_retrieval.FullRunRetrieval, "_gate", lambda *_args: ("released", False)
    )
    monkeypatch.setattr(
        full_retrieval, "select_retrieval_input", lambda *_args: SimpleNamespace(complete=False)
    )
    scopes = [
        {
            "release_event_id": f"full:{metric}:2026-08",
            "metric_ids": [metric],
            "period": "2026-08",
            "priority": "P1",
            "source_url": source,
        }
        for metric, source in (("CN_CORE_CPI", LISTING), ("CN_INDUSTRIAL_VA", readings))
    ]

    full_retrieval.FullRunRetrieval(paths)._read_listings(run, scopes, EFFECTIVE_CATALOG_VERSION)

    half = LISTING_PAGES_PER_SITE // 2
    assert run_listings(paths, run.run_id).reads == {LISTING: half, readings: half}


@pytest.mark.usefixtures("runtime_clock")
def test_a_page_held_back_is_no_read_and_the_chronicle_s_pages_count_to_their_site(
    tmp_path: Path,
) -> None:
    """The site's pages count what was sent: a request the retrieval ledger held back is
    none; the policy chronicle the RRR backtrack reads is the PBC's too."""
    from pring_cycle import official_context
    from pring_cycle.acquisition import own_acquisitions
    from pring_cycle.official_context import read_listing_page, run_listings
    from pring_cycle.official_listing import RRR_CHRONICLE_LISTING
    from pring_cycle.retrieval_ledger import RetrievalBudgetBlocked

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    run = _share_run(paths)
    chronicle = (FIXTURES / "official_listing" / "pbc_125963_index_20260925.html").read_bytes()

    def blocked(_acquisition_id: str) -> None:
        raise RetrievalBudgetBlocked("negative_cache_active", cache_hit=True)

    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        listings = run_listings(paths, run.run_id)
        with pytest.raises(RetrievalBudgetBlocked):
            read_listing_page(
                paths,
                family="pbc_omo_notice",
                listing_url=OMO_COLUMN + "index.html",
                period="2026-09-23",
                listings=listings,
                on_acquisition_started=blocked,
            )
        assert (listings.reads, listings.sites, listings.failures) == ({}, {}, {})
        official_context._read_chronicle_page(
            paths,
            RRR_CHRONICLE_LISTING,
            lambda url: FetchedOfficialContextDocument(chronicle, "text/html", url, 200),
            None,
        )
    official_context._RUN_LISTINGS.clear()  # Another process: rebuilt from the receipts.

    assert run_listings(paths, run.run_id).sites == {"www.pbc.gov.cn": 1}
