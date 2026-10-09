"""Lookback 21: a capacity utilization quarter the NBS listing lacks, rescued by search.

Lookback 13 put the NBS's /zwfwck/sjfb/ copies of its releases on the search whitelist and
the release entry, tested a component at a time. One manual full run on the effective model
walks the whole chain: the listing reaches back past the quarter without listing it, Tavily
offers the release under /zwfwck/sjfb/, and the strict path fetches it, holds it to its
period and fills the gap. The same release offered for the other quarters is turned down.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository, MetricSeriesPoint
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.official_context import FetchedOfficialContextDocument
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.adapters.test_official_context import ZWFWCK_CAPACITY, zwfwck_capacity_fetch
from tests.adapters.test_official_listing_scan import NBS_READINGS, nbs_filler, nbs_page
from tests.conftest import install_runtime_clock

# The newest model, whatever it is numbered.
CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])
# nbs_capacity_utilization_zwfwck_q1.html, as registered in its fixture README.
RELEASE_SHA256 = "d038b999e708a80099d1bce73adb7a773bd75bfc8ccb42dc732e8a75baee750b"
CAPACITY = "CN_CAPACITY_UTILIZATION"
# Late May: the first quarter is the newest released; the run reads 2025 back as well.
TARGET = "2026-05-29"
EARLIER_QUARTERS = ("2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4")


class Response(BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}


class Rescued:
    """What the run asked of the NBS and of Tavily, and the run itself."""

    def __init__(self, paths: RuntimePaths, run: RunRecord) -> None:
        self.paths = paths
        self.run = run
        self.queries: list[str] = []
        self.requested: list[str] = []


@pytest.fixture(scope="module")
def rescued(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> Iterator[Rescued]:
    from pring_cycle.retrieval import RUN_SEARCH_LIMITS

    with pytest.MonkeyPatch.context() as monkeypatch:
        install_runtime_clock(monkeypatch, request, datetime.now(UTC))
        # The gaps searched before capacity utilization cannot use up the run's Tavily cap.
        monkeypatch.setitem(RUN_SEARCH_LIMITS, "tavily", 1000)
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("capacity-rescue") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n", encoding="utf-8")
        models = ModelRepository(paths.database)
        models.register(effective_model_manifest())
        models.activate(CURRENT_MODEL, explicitly_approved=True)
        run = RunRepository(paths.database).submit_manual_full(
            target_business_date=TARGET,
            client_request_id="capacity-search-rescue",
            model_version_id=CURRENT_MODEL,
            system_as_of=datetime.now(UTC),
        )
        state = Rescued(paths, run)
        # The readings list, one page: it reaches back past the first quarter's end and
        # lists other releases of the day the capacity release came out, not that one.
        listing = nbs_page(
            0,
            1,
            [
                nbs_filler(date(2026, 5, 19), 1),
                nbs_filler(date(2026, 4, 16), 2),
                nbs_filler(date(2026, 3, 16), 3),
            ],
        )

        def search(request: Any, *, timeout: float) -> Response:
            query = json.loads(request.data)["query"]
            state.queries.append(query)
            # The /zwfwck/sjfb/ address Tavily found in run-8a3779cff80f6bd586a0, offered
            # for every capacity quarter searched; every other search finds nothing.
            found = [{"url": ZWFWCK_CAPACITY}] if "产能利用率" in query else []
            return Response(json.dumps({"results": found}).encode())

        def fetch(url: str) -> FetchedOfficialContextDocument:
            state.requested.append(url)
            if url == NBS_READINGS:
                return FetchedOfficialContextDocument(listing, "text/html", url, 200)
            if url == ZWFWCK_CAPACITY:
                return zwfwck_capacity_fetch(url)
            raise OSError("fixture_official_page_unavailable")

        monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
        monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
        process_pending_run(paths, report_adapters=())
        yield state


def final_gaps(state: Rescued) -> dict[str, dict[str, Any]]:
    plan = RunRepository(state.paths.database).full_retrieval_plan(state.run.run_id)
    assert plan["final"] is not None
    return {g["period"]: g for g in plan["final"]["gaps"] if g["metric_id"] == CAPACITY}


def validations(state: Rescued) -> dict[str, list[dict[str, Any]]]:
    """The run's candidate validations of the capacity gaps, by period."""
    ledger = RunRepository(state.paths.database).get(state.run.run_id).retrieval_ledger
    assert ledger is not None
    period_of = {g["gap_id"]: g["period"] for g in ledger["gaps"] if g["metric_id"] == CAPACITY}
    by_period: dict[str, list[dict[str, Any]]] = {}
    for item in ledger["candidate_validations"]:
        periods = {period_of[gap_id] for gap_id in item["gap_ids"] if gap_id in period_of}
        for period in periods:
            by_period.setdefault(period, []).append(item)
    return by_period


def capacity_points(state: Rescued) -> dict[tuple[str, str], MetricSeriesPoint]:
    points = EvidenceRepository(state.paths.database).metric_series(
        CAPACITY,
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    return {(p.period_end, p.dimensions["measure"]): p for p in points}


def test_a_quarter_the_listing_lacks_is_filled_from_its_zwfwck_release(rescued: Rescued) -> None:
    # The readings list was read and had no link to follow: the only capacity page
    # fetched is the one search offered.
    assert rescued.requested.count(NBS_READINGS) == 1
    assert [url for url in rescued.requested if "/sj/zxfbhjd/2026" in url] == []
    assert "2026年一季度全国工业产能利用率" in rescued.queries
    with database_connection(rescued.paths.database) as connection:
        attempts = connection.execute(
            "SELECT channel, outcome, classification FROM run_retrieval_attempt "
            "WHERE run_id=? AND release_event_id=? ORDER BY sequence",
            (rescued.run.run_id, "full:nbs_capacity_utilization:2026-Q1"),
        ).fetchall()
    channels = [channel for channel, _outcome, _classification in attempts]
    # The listing was read through and named no release for the quarter: a semantic
    # failure, not an unread page (transient_transport_error) or a listing that stopped
    # short of it (listing_not_covered_*). Tavily's candidate then verified the gap.
    assert ("official", "failed", "semantic_validation_failed") in attempts
    assert attempts[-1] == ("tavily", "verified", "complete_model_input")
    assert channels.index("official") < channels.index("tavily")

    [validation] = validations(rescued)["2026-Q1"]
    assert (validation["outcome"], validation["fetched_url"], validation["raw_hash"]) == (
        "model_usable",
        ZWFWCK_CAPACITY,
        RELEASE_SHA256,
    )
    gap = final_gaps(rescued)["2026-Q1"]
    assert gap["complete"] is True
    assert gap["missing_members"] == []

    points = capacity_points(rescued)
    quarter = {measure: point for (end, measure), point in points.items() if end == "2026-03-31"}
    assert quarter["quarter_rate"].selected_value == 73.6
    assert quarter["yoy_change"].selected_value == -0.5
    selected = {point.selected_claim_id for point in quarter.values()}
    assert selected == set(gap["selected_claim_ids"])
    for point in quarter.values():
        [chosen] = [claim for claim in point.claims if claim.claim_id == point.selected_claim_id]
        assert chosen.source_reference == f"{ZWFWCK_CAPACITY}#sha256={RELEASE_SHA256}"


def test_the_same_release_offered_for_another_quarter_is_turned_down_by_its_period(
    rescued: Rescued,
) -> None:
    by_period = validations(rescued)
    gaps = final_gaps(rescued)
    for period in EARLIER_QUARTERS:
        [validation] = by_period[period]
        # Fetched and parsed, then held to the quarter the gap is due: no value stored.
        assert (validation["outcome"], validation["reason"]) == (
            "not_model_usable",
            "period_mismatch",
        ), period
        assert validation["fetched_url"] == ZWFWCK_CAPACITY
        assert validation["raw_hash"] == RELEASE_SHA256
        assert validation["claim_ids"] == []
        assert gaps[period]["complete"] is False
    with database_connection(rescued.paths.database) as connection:
        refused = connection.execute(
            "SELECT json_extract(parameters_json, '$.period'), rejection_reason "
            "FROM acquisition_request WHERE api_name='official_http_get' "
            "AND json_extract(parameters_json, '$.source_url')=? ORDER BY 1",
            (ZWFWCK_CAPACITY,),
        ).fetchall()
    assert refused == [
        *((period, "official_context_period_identity_mismatch") for period in EARLIER_QUARTERS),
        ("2026-Q1", None),
    ]
    # Only the first quarter is held: the page put no value on the quarters it is not.
    assert {end for end, _measure in capacity_points(rescued)} == {"2026-03-31"}
