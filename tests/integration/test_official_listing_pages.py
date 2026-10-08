"""Phase two #12: a full run finds second-quarter GDP two pages back on the NBS listing."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

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
    reads = [
        (r.api_name, r.parameters["source_url"], r.state)
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "nbs_gdp" and r.parameters["period"] == "2026-Q2"
    ]
    assert reads == [
        ("official_listing_get", LISTING, "validated"),
        ("official_listing_get", LISTING + "index_1.html", "validated"),
        ("official_listing_get", LISTING + "index_2.html", "validated"),
        ("official_http_get", ARTICLE, "validated"),
    ]
    # A two-year-old history quarter is not on the recent pages: read once, not found.
    history = [
        r.parameters["source_url"]
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.parameters.get("family") == "nbs_gdp" and r.parameters["period"] == "2024-Q2"
    ]
    assert history == [LISTING]


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
