from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository, effective_model_manifest
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.storage import database_connection
from pring_cycle.worker import process_pending_run
from tests.integration.test_trading_calendar import record_sse_calendar


def prepare(tmp_path: Path) -> tuple[RuntimePaths, RunRepository]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    return paths, RunRepository(paths.database)


@pytest.fixture
def unavailable_optional_eia(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*args, **kwargs):
        raise OSError("fixture optional EIA source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)


@pytest.mark.parametrize(
    "failure", [None, OSError("fixture offline"), ValueError("fixture schema")]
)
@pytest.mark.usefixtures("runtime_clock")
def test_p2_projection_separates_acquisition_condition_from_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception | None
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    requests = []
    if failure is not None:
        paths.secrets.write_text("EIA_API_KEY=fixture-only\n", encoding="utf-8")
        paths.secrets.chmod(0o600)

    class Opener:
        def open(self, request, *, timeout):
            requests.append(request)
            assert failure is not None, "Missing credentials must not send a request"
            raise failure

    monkeypatch.setattr("pring_cycle.eia_context.build_opener", Opener)
    pages: list[str] = []

    def page_offline(url: str) -> None:
        pages.append(url)
        raise OSError("fixture history page offline")

    # The key-free fallback is exercised on its own; here it must not reach the network.
    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", page_offline)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="p2-acquisition-condition",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.projection_set_id is not None
    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id)
    row = next(
        row
        for row in projection.datasets["macro"]["international_context"]
        if row["metric_id"] == "EIA_BRENT_RBRTE"
    )
    # Every branch here ends at the key-free page, which is offline in this fixture, while
    # the API channel keeps its own recorded outcome. How the row shows the latest of them
    # is asked of the projection directly (test_acquisition_outcome).
    assert pages
    expected = (
        "missing_credentials"
        if failure is None
        else "source_failed"
        if isinstance(failure, OSError)
        else "validation_failed"
    )
    with database_connection(paths.database) as connection:
        outcomes = dict(
            connection.execute(
                "SELECT channel, outcome FROM retrieval_attempt WHERE metric_id=? "
                "AND fetched_at = (SELECT MAX(latest.fetched_at) FROM retrieval_attempt latest "
                "WHERE latest.metric_id = retrieval_attempt.metric_id "
                "AND latest.channel = retrieval_attempt.channel)",
                ("EIA_BRENT_RBRTE",),
            ).fetchall()
        )
    assert outcomes["eia_official_candidate"] == expected
    assert outcomes["eia_html_candidate"] == "source_failed"
    assert row["value"] is None
    assert row["role"] == "context_only_never_formal_stage"
    assert len(requests) == (0 if failure is None else 1)


@pytest.mark.parametrize("case", ["gdp_no_levels", "treasury_schema", "treasury_partial"])
def test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    runtime_clock: Callable[[], datetime],
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n", encoding="utf-8")
    paths.secrets.chmod(0o600)

    class Opener:
        def open(self, request, *, timeout):
            payload = json.loads(request.data)
            api = payload["api_name"]
            if api == "cn_gdp" and case == "gdp_no_levels":
                fields = payload["fields"].split(",")
                row = {field: None for field in fields}
                row.update(quarter="2026Q2", gdp_yoy=4.7, pi_yoy=3.7, si_yoy=3.9, ti_yoy=5.2)
            elif api == "us_tycr" and case.startswith("treasury"):
                fields = payload["fields"].split(",")
                row = {"date": "20260828", "y2": None, "y10": 4.2}
                if case == "treasury_schema":
                    return BytesIO(b'{"code":0,"data":{"fields":[],"items":[[]]}}')
            else:
                raise OSError("fixture source unavailable; keep preexisting core evidence")
            return BytesIO(
                json.dumps(
                    {
                        "code": 0,
                        "data": {"fields": fields, "items": [[row[field] for field in fields]]},
                    }
                ).encode()
            )

    class CoreOpener:
        def open(self, request, *, timeout):
            payload = json.loads(request.data)
            params = payload["params"]
            start = datetime.strptime(params["start_date"], "%Y%m%d").date()
            end = datetime.strptime(params["end_date"], "%Y%m%d").date()
            days = [
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if (start + timedelta(days=i)).weekday() < 5
            ]
            if payload["api_name"] == "trade_cal":
                fields = ["cal_date", "is_open"]
                items = [[day.strftime("%Y%m%d"), 1] for day in days]
            else:
                fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
                items = [
                    [
                        params["ts_code"],
                        day.strftime("%Y%m%d"),
                        100 + i,
                        99 + i,
                        0.01 if payload["api_name"] == "fut_index_daily" else 1.0,
                    ]
                    for i, day in enumerate(days)
                ]
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *handlers: CoreOpener())
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: Opener())
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id=case,
        model_version_id="model-v0001",
        system_as_of=runtime_clock(),
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.projection_set_id is not None
    rows = (
        ProjectionSetRepository(paths.database)
        .get(stored.projection_set_id)
        .datasets["macro"]["international_context"]
    )
    metric_id = "CN_GDP" if case == "gdp_no_levels" else "UST2Y_NOMINAL_YIELD"
    row = next(row for row in rows if row["metric_id"] == metric_id)
    assert row["acquisition_status"] == (
        "missing_fields" if case == "treasury_partial" else "validation_failed"
    )
    if case == "treasury_partial":
        # The spread showing its inputs' acquisitions is asked of the projection directly.
        ten_year = next(row for row in rows if row["metric_id"] == "UST10Y_NOMINAL_YIELD")
        assert ten_year["acquisition_status"] == "verified_candidate"


@pytest.mark.usefixtures("unavailable_optional_eia")
def test_full_run_preserves_explicit_historical_cutoff_even_when_executed_later(
    tmp_path: Path,
) -> None:
    paths, runs = prepare(tmp_path)
    cutoff = datetime(2026, 8, 28, 10, tzinfo=UTC)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="explicit-cutoff",
        model_version_id="model-v0001",
        system_as_of=cutoff,
        cutoff_mode="explicit",
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.system_as_of == stored.report_cutoff == cutoff
    assert stored.cutoff_mode == "explicit"
    assert stored.cutoffs_frozen is True
    assert stored.error_classification == "p0_required_calendar_unavailable"
    with pytest.raises(ValueError, match="run_cutoff_already_frozen"):
        runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC))


@pytest.mark.parametrize("entrypoint", ["cli", "api"])
def test_full_run_command_accepts_explicit_cutoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], entrypoint: str
) -> None:
    paths, runs = prepare(tmp_path)
    cutoff = "2026-08-28T10:00:00+00:00"
    if entrypoint == "cli":
        from pring_cycle.cli import main

        main(
            [
                "run-submit",
                "--runtime-root",
                str(tmp_path / "runtime"),
                "--target-date",
                "2026-08-28",
                "--request-id",
                "explicit-cli",
                "--as-of",
                cutoff,
            ]
        )
        document = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    else:
        from starlette.requests import Request

        from pring_cycle.web import create_web_application

        application = create_web_application(paths, 8050, eager_dashboard=False)
        endpoint = next(
            route.endpoint
            for route in application.routes
            if getattr(route, "name", None) == "append_command"
        )

        async def receive():
            return {
                "type": "http.request",
                "body": json.dumps(
                    {
                        "command": "manual_full",
                        "target_business_date": "2026-08-28",
                        "client_request_id": "explicit-api",
                        "system_as_of": cutoff,
                    }
                ).encode(),
            }

        request = Request(
            {
                "type": "http",
                "headers": [(b"host", b"127.0.0.1:8050"), (b"origin", b"http://127.0.0.1:8050")],
            },
            receive=receive,
        )
        response = asyncio.run(endpoint(request))
        assert response.status_code == 202
        document = json.loads(response.body)
    run = runs.get(document["run_id"])
    assert run.system_as_of == datetime.fromisoformat(cutoff)
    assert run.cutoff_mode == "explicit"


def seed_core_history(
    paths: RuntimePaths,
    *,
    definition_version: str = "metric-catalog-v0001",
    omit_stock_on: str | None = None,
    include_calendar: bool = True,
) -> None:
    evidence = EvidenceRepository(paths.database)
    days = core_history_days()
    claims: list[SourceClaimInput] = []
    for index, observed in enumerate(reversed(days)):
        known = datetime.combine(observed, datetime.min.time(), tzinfo=UTC)
        for metric_id, value in (
            ("CN_BOND_CORE_000012", 100.0 + index),
            ("CN_EQUITY_CORE_000985", 1000.0 - index),
            ("CN_COMMODITY_CORE_NHII", 100.0 + index),
        ):
            if metric_id == "CN_EQUITY_CORE_000985" and observed.isoformat() == omit_stock_on:
                continue
            api, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version=definition_version,
                    period_kind="business_day",
                    period_start=observed.isoformat(),
                    period_end=observed.isoformat(),
                    dimensions={},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="tushare",
                    source_reference=f"tushare:{api}:{code}:{observed}",
                    release_event_id=f"fixture:{metric_id}:{observed}",
                    release_at=known,
                    public_available_at=known,
                    fetched_at=known,
                    available_at=known,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    # One transaction for all 540 claims instead of one per claim.
    evidence.append_source_claims(tuple(claims))
    if include_calendar:
        record_core_calendar(paths)


def core_history_days() -> list[date]:
    """The 180 weekdays to 2026-08-28, newest first, that the core history holds."""
    day = date(2026, 8, 28)
    days = []
    while len(days) < 180:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return days


def record_core_calendar(paths: RuntimePaths) -> None:
    """The run's SSE calendar response; each run fetches its own, so retention drops it."""
    record_sse_calendar(paths, core_history_days())


@pytest.mark.usefixtures("runtime_clock")
def test_full_run_searches_real_gap_and_publishes_traceable_adoption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    url = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
    original = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    calls = []
    before_search = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def geturl(self) -> str:
            return url

    def search(request, *, timeout):
        calls.append(request.full_url)
        before_search.append(runs.full_retrieval_plan(run.run_id))
        # Every released gap is searched (ticket 19); only the LPR query finds its page.
        found = [{"url": url}] if "贷款市场报价利率" in json.loads(request.data)["query"] else []
        return Response(json.dumps({"results": found}).encode())

    class Opener:
        def open(self, request, *, timeout):
            calls.append(request.full_url)
            return Response(original)

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    monkeypatch.setattr("pring_cycle.official_lpr.urlopen", Opener().open)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="full-search-lpr",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    assert calls[0] == "https://api.tavily.com/search"
    assert calls.count(url) == 1
    assert before_search[0]["final"] is None
    initial = before_search[0]["initial"]
    assert initial["model_version_id"] == "model-v0001"
    assert initial["definition_version"] == "metric-catalog-v0001"
    assert initial["cutoff_mode"] == "acquisition_window"
    current = ProjectionSetRepository(paths.database).current()
    plan = runs.full_retrieval_plan(run.run_id)
    assert plan["initial"] == initial
    final = plan["final"]
    assert final["system_as_of"] == current.envelope.system_as_of.isoformat()
    lpr = next(g for g in final["gaps"] if g["metric_id"] == "CN_LPR_1Y_5Y")
    assert lpr["complete"] is True
    assert len(lpr["selected_claim_ids"]) == 2
    assert set(lpr["selected_claim_ids"]) <= set(plan["adoption"]["selected_claim_ids"])
    assert plan["adoption"]["projection_set_id"] == current.envelope.projection_set_id
    assert stored.consumed_budget["tavily"] == calls.count("https://api.tavily.com/search")
    assert stored.consumed_budget["exa"] == 0
    # All 180 prices per asset drive the stateful trend; only 120 are displayed.
    assert len(plan["adoption"]["selected_claim_ids"]) == 542
    assert set(plan["adoption"]["selected_observation_version_ids"]) <= set(
        plan["adoption"]["referenced_observation_version_ids"]
    )
    assert all(
        len(asset["observation_version_ids"]) == 120
        for asset in current.datasets["core_assets"]["assets"]
    )


def test_full_run_plan_includes_missing_historical_daily_members(
    tmp_path: Path,
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="historical-gap-plan",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    plan = runs.full_retrieval_plan(run.run_id)
    dr007 = [item for item in plan["initial"]["requirements"] if item["metric_id"] == "CN_DR007"]
    assert len(dr007) == 120
    assert len({item["period"] for item in dr007}) == 120
    assert max(item["period"] for item in dr007) == "2026-08-28"
    assert min(item["period"] for item in dr007) == "2026-03-16"


def test_full_run_adoption_excludes_uncertified_candidates(tmp_path: Path) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    known = datetime(2026, 8, 10, tzinfo=UTC)
    candidate = EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_CORE_CPI",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start="2026-07-01",
            period_end="2026-07-31",
            dimensions={"measure": "yoy", "category": "core"},
            value=1.1,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="fixture:uncertified",
            source_reference="fixture:candidate-core-cpi",
            release_event_id="fixture:core-cpi:2026-07",
            release_at=known,
            public_available_at=known,
            fetched_at=known,
            available_at=known,
            certification_status="awaiting_source_certification",
            quality_status="validated",
        )
    )
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="adoption-candidate",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(run.run_id).status == "completed"
    projection = ProjectionSetRepository(paths.database).current()
    assert candidate.claim_id in json.dumps(projection.datasets)
    adoption = runs.full_retrieval_plan(run.run_id)["adoption"]
    # An uncertified registered value is adopted like any other (ADR-0021).
    assert candidate.claim_id in adoption["selected_claim_ids"]
    assert candidate.claim_id in adoption["referenced_observation_version_ids"]


def test_upgrade_resumes_verified_evidence_at_original_cutoff(tmp_path: Path) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    cutoff = datetime(2026, 8, 28, 10, tzinfo=UTC)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="legacy-verified-evidence",
        model_version_id="model-v0001",
        system_as_of=cutoff,
    )
    evidence = EvidenceRepository(paths.database)
    claims = tuple(
        point.selected_claim_id
        for metric in CORE_API_IDENTITIES
        for point in evidence.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=cutoff, definition_version="metric-catalog-v0001"
        )
        if point.selected_claim_id is not None
    )
    snapshot = evidence.freeze_snapshot(claims, mode=AsOfMode.SYSTEM, as_of=cutoff)
    runs.record_checkpoint(
        run.run_id, "verified_evidence", snapshot.evidence_snapshot_id, verified=True
    )
    runs.mark_interrupted(run.run_id, "fixture:pre_upgrade_interrupt")
    runs.resume(run.run_id, client_request_id="legacy-resume", confirm_external_calls=True)
    initialize_runtime(paths)
    assert runs.get(run.run_id).cutoffs_frozen is True
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    assert stored.system_as_of == cutoff
    plan = runs.full_retrieval_plan(run.run_id)
    assert plan["initial"]["origin"] == "reconstructed_from_legacy_checkpoint"
    assert plan["initial"]["pre_request_plan_available"] is False
    assert plan["final"]["system_as_of"] == cutoff.isoformat()
    assert stored.consumed_budget == {"tavily": 0, "exa": 0, "ai_websearch": 0}


@pytest.mark.usefixtures("runtime_clock")
def test_full_run_shares_hard_search_budget_across_periods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    evidence = EvidenceRepository(paths.database)
    for number in range(12):
        day = date(2026, 8, 28) - timedelta(days=number)
        if day.weekday() >= 5:
            continue
        known = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        evidence.append_source_claim(
            SourceClaimInput(
                # A searchable daily gap (PBC notices): an unsearchable one is never searched.
                metric_id="CN_OMO_7D_AMOUNT",
                definition_version="metric-catalog-v0001",
                period_kind="business_day",
                period_start=day.isoformat(),
                period_end=day.isoformat(),
                dimensions={"measure": "injection"},
                value=None,
                value_state=EvidenceValueState.NOT_DISCLOSED,
                unit="hundred_million_cny",
                provider="fixture:official-release",
                source_reference=f"fixture:omo-amount:{day}",
                release_event_id=f"fixture:omo-amount:{day}",
                release_at=known,
                public_available_at=known,
                fetched_at=known,
                available_at=known,
                certification_status="awaiting_source_certification",
                quality_status="validated",
            )
        )
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def search(request, *, timeout):
        calls.append(request.full_url)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="shared-budget",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    # The budget is the retrieval's rule; the full run's link to it is covered by
    # test_full_run_searches_real_gap_and_publishes_traceable_adoption.
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    retrieval = FullRunRetrieval(paths)
    retrieval.retrieve(run)
    stored = runs.get(run.run_id)
    # Tavily's per-run cap is 16; Exa waits for Tavily's monthly quota (ticket 20).
    assert stored.consumed_budget == {"tavily": 16, "exa": 0, "ai_websearch": 0}
    assert calls.count("https://api.tavily.com/search") == 16
    assert calls.count("https://api.exa.ai/search") == 0
    assert any(attempt["classification"] == "run_limit" for attempt in stored.retrieval_attempts)
    assert any(attempt["outcome"] == "not_configured" for attempt in stored.retrieval_attempts)
    retrieval.evaluate(runs.freeze_cutoffs(run.run_id, system_as_of=datetime.now(UTC)))
    final = runs.full_retrieval_plan(run.run_id)["final"]
    core = [gap for gap in final["gaps"] if gap["metric_id"] == "CN_EQUITY_CORE_000985"]
    assert len(core) == 120
    assert all(gap["complete"] for gap in core)


@pytest.mark.usefixtures("runtime_clock")
def test_failed_direct_request_is_bound_before_http_and_visible_in_run_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.web import create_web_application

    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n")
    before = []

    class Response(BytesIO):
        def getcode(self):
            return 200

    class Opener:
        def open(self, request, *, timeout):
            before.append(runs.full_retrieval_plan(run.run_id))
            return Response(b'{"code":0,"data":{"fields":["cal_date","is_open"],"items":[]}}')

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *args: Opener())
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="direct-empty-calendar",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    # The core refresh asks for the calendar again on its one retry (ticket 22).
    assert len(before) == 2
    # The release pre-announcements (ticket 25) are fetched before the core refresh.
    core = [
        item
        for item in before[0]["acquisitions"]
        if item["api_name"] not in {"cn_schedule", "official_schedule_get"}
    ]
    assert len(core) == 1
    assert core[0]["state"] == "started"
    assert before[0]["initial"] is None
    app = create_web_application(paths, 8050, eager_dashboard=False)
    endpoint = next(
        route.endpoint for route in app.routes if getattr(route, "name", None) == "run_audit"
    )
    response = endpoint(run.run_id)
    assert response.status_code == 200
    audit = json.loads(response.body)
    request = next(
        item
        for item in audit["full_retrieval"]["acquisitions"]
        if item["phase"] == "direct_core_refresh"
    )
    assert request["run_id"] == run.run_id
    assert request["api_name"] == "trade_cal"
    assert request["phase"] == "direct_core_refresh"
    assert request["raw_hash"] is not None
    assert audit["run"]["status"] == "action_required"


# Uncertified prior values are no longer withheld (ADR-0021); only the labelled case remains.
@pytest.mark.parametrize("prior_certified", [True])
def test_lpr_direction_inputs_are_certified_and_in_frozen_snapshot(
    tmp_path: Path, prior_certified: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")

    class Response(BytesIO):
        status = 200
        headers = {}

    def unexpected_search(request, **kwargs):
        # Other released gaps are searched; the complete local LPR never is.
        if "贷款市场报价利率" in json.loads(request.data)["query"]:
            raise AssertionError("complete_local_lpr_must_not_call_search")
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", unexpected_search)
    prior_ids, current_ids = set(), set()
    for month, value in ((7, 3.0), (8, 2.9)):
        known = datetime(2026, month, 21, tzinfo=UTC)
        for tenor in ("1y", "5y_plus"):
            claim = EvidenceRepository(paths.database).append_source_claim(
                SourceClaimInput(
                    metric_id="CN_LPR_1Y_5Y",
                    definition_version="metric-catalog-v0001",
                    period_kind="month",
                    period_start=f"2026-{month:02d}-01",
                    period_end=f"2026-{month:02d}-31",
                    dimensions={"tenor": tenor},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percent",
                    provider="fixture:lpr-official",
                    source_reference=f"fixture:lpr:{month}:{tenor}",
                    release_event_id=f"fixture:lpr:2026-{month:02d}",
                    release_at=known,
                    public_available_at=known,
                    fetched_at=known,
                    available_at=known,
                    certification_status="certified"
                    if month == 8 or prior_certified
                    else "awaiting_source_certification",
                    quality_status="validated",
                )
            )
            (prior_ids if month == 7 else current_ids).add(claim.claim_id)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="lpr-direction-provenance",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(run.run_id).status == "completed"
    adoption = runs.full_retrieval_plan(run.run_id)["adoption"]
    projection = ProjectionSetRepository(paths.database).current()
    rows = [
        row
        for row in projection.datasets["macro"]["credit"]["evidence"]
        if row["metric_id"] == "CN_LPR_1Y_5Y"
    ]
    assert len(rows) == 2
    assert {row["direction"] for row in rows} == ({"down"} if prior_certified else {"unknown"})
    assert set(adoption["selected_observation_version_ids"]) <= set(
        adoption["referenced_observation_version_ids"]
    )
    assert current_ids <= set(adoption["selected_claim_ids"])
    if prior_certified:
        assert prior_ids <= set(adoption["selected_claim_ids"])
    else:
        assert prior_ids.isdisjoint(adoption["selected_claim_ids"])


@pytest.mark.usefixtures("runtime_clock")
def test_joint_publication_shares_one_request_for_multiple_full_run_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.models import analytical_model_v0002_manifest
    from pring_cycle.retrieval import RUN_SEARCH_LIMITS

    # Lift the run cap so earlier gaps cannot use it up before the pair is searched.
    monkeypatch.setitem(RUN_SEARCH_LIMITS, "tavily", 1000)

    paths, runs = prepare(tmp_path)
    models = ModelRepository(paths.database)
    # Isolated legacy model lifecycle fixture; no hardened v3 gate is patched.
    models.create_candidate(analytical_model_v0002_manifest())
    models.activate("model-v0002", explicitly_approved=True)
    seed_core_history(paths, definition_version="metric-catalog-v0002")
    known = datetime(2026, 8, 14, tzinfo=UTC)
    # Social financing's total and components come out in one PBC release.
    for metric, dimensions in (
        ("CN_SF_TOTAL", {"measure": "stock_end"}),
        ("CN_SF_COMPONENTS", {"component": "renminbi_loans", "measure": "stock_end"}),
    ):
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id=metric,
                definition_version="metric-catalog-v0002",
                period_kind="month",
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions=dimensions,
                value=None,
                value_state=EvidenceValueState.NOT_DISCLOSED,
                unit="hundred_million_cny",
                provider="fixture:pbc",
                source_reference=f"fixture:pbc:{metric}",
                release_event_id="fixture:pbc:2026-07",
                release_at=known,
                public_available_at=known,
                fetched_at=known,
                available_at=known,
                certification_status="awaiting_source_certification",
                quality_status="validated",
            )
        )
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\n")

    class Response(BytesIO):
        status = 200
        headers = {}

    monkeypatch.setattr(
        "pring_cycle.search_discovery.urlopen",
        lambda request, *, timeout: Response(b'{"results":[]}'),
    )
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="joint-sf-publication",
        model_version_id="model-v0002",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    ledger = stored.retrieval_ledger
    sf_ids = {
        gap["gap_id"]
        for gap in ledger["gaps"]
        if gap["metric_id"] in {"CN_SF_TOTAL", "CN_SF_COMPONENTS"} and gap["period"] == "2026-07"
    }
    requests = [
        request
        for request in ledger["requests"]
        if request["channel"] == "tavily" and sf_ids.intersection(request["gap_ids"])
    ]
    assert len(requests) == 1
    final = [
        g
        for g in ledger["gaps"]
        if g["gap_id"] in sf_ids and g["as_of"] == stored.system_as_of.isoformat()
    ]
    assert {g["metric_id"] for g in final} == {"CN_SF_TOTAL", "CN_SF_COMPONENTS"}
    assert {g["gap_id"] for g in final} <= set(requests[0]["gap_ids"])
    assert stored.consumed_budget["ai_websearch"] == 0


@pytest.mark.usefixtures("runtime_clock")
def test_cancel_during_tavily_stops_following_physical_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    paths.secrets.write_text("TAVILY_API_KEY=fixture-secret\nEXA_API_KEY=fixture-secret\n")
    calls = []

    class Response(BytesIO):
        status = 200
        headers = {}

    def search(request, *, timeout):
        calls.append(request.full_url)
        runs.cancel(run.run_id)
        return Response(b'{"results":[]}')

    monkeypatch.setattr("pring_cycle.search_discovery.urlopen", search)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="cancel-in-tavily",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(run.run_id).status == "cancelled"
    assert calls == ["https://api.tavily.com/search"]
    assert runs.get(run.run_id).cutoffs_frozen is False
    assert runs.full_retrieval_plan(run.run_id)["adoption"] is None


def test_a_core_session_missing_inside_the_window_holds_the_core_through_the_run(
    tmp_path: Path,
) -> None:
    # The window comes from the calendar, not the prices, so the missing session stays in
    # it as an incomplete plan gap, which the run hands the day summary as gate ①. The
    # stage that holds is asked of the day summary itself (test_day_summary).
    paths, runs = prepare(tmp_path)
    seed_core_history(paths, omit_stock_on="2026-08-20")
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="missing-core-day",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    plan = runs.full_retrieval_plan(run.run_id)
    assert "2026-08-20" in plan["initial"]["daily_window"]["dates"]
    gap = next(
        g
        for g in plan["final"]["gaps"]
        if g["metric_id"] == "CN_EQUITY_CORE_000985" and g["period"] == "2026-08-20"
    )
    assert gap["complete"] is False
    assert runs.get(run.run_id).status == "completed"
    assets = ProjectionSetRepository(paths.database).current().datasets["core_assets"]["assets"]
    stock = next(item for item in assets if item["asset"] == "stock")
    assert stock["reason"] == "window_session_missing"


def test_credit_formula_expands_required_history_in_full_run_plan(tmp_path: Path) -> None:
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="credit-history-demand",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    plan = runs.full_retrieval_plan(run.run_id)
    sf = {r["period"] for r in plan["initial"]["requirements"] if r["metric_id"] == "CN_SF_TOTAL"}
    gdp = {r["period"] for r in plan["initial"]["requirements"] if r["metric_id"] == "CN_GDP"}
    assert len(sf) == 24
    assert (min(sf), max(sf)) == ("2024-08", "2026-07")
    assert len(gdp) == 8
    assert (min(gdp), max(gdp)) == ("2024-Q3", "2026-Q2")
    assert any(
        r["metric_id"] == "CN_CREDIT_IMPULSE" for r in plan["initial"]["derived_requirements"]
    )


@pytest.mark.parametrize(
    "measure,last_year,last_quarter,expected",
    [
        ("nominal_ytd_level", 2026, 2, 9),
        ("nominal_ytd_level", 2025, 4, 8),
    ],
)
def test_credit_gdp_ytd_baseline_matches_required_window(
    tmp_path: Path, measure: str, last_year: int, last_quarter: int, expected: int
) -> None:
    from pring_cycle.models import analytical_model_v0002_manifest

    paths, runs = prepare(tmp_path)
    models = ModelRepository(paths.database)
    models.create_candidate(analytical_model_v0002_manifest())
    models.activate("model-v0002", explicitly_approved=True)
    seed_core_history(paths, definition_version="metric-catalog-v0002")
    last = last_year * 4 + last_quarter - 1
    for ordinal in range(last - 7, last + 1):
        year, quarter = ordinal // 4, ordinal % 4 + 1
        start = date(year, (quarter - 1) * 3 + 1, 1)
        end = (
            date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        ) - timedelta(days=1)
        known = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        EvidenceRepository(paths.database).append_source_claim(
            SourceClaimInput(
                metric_id="CN_GDP",
                definition_version="metric-catalog-v0002",
                period_kind="quarter",
                period_start=start.isoformat(),
                period_end=end.isoformat(),
                dimensions={"aggregate": "total", "measure": measure},
                value=100.0,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="fixture:gdp",
                source_reference=f"fixture:gdp:{end}",
                release_event_id=f"fixture:gdp:{end}",
                release_at=known,
                public_available_at=known,
                fetched_at=known,
                available_at=known,
                certification_status="awaiting_source_certification",
                quality_status="validated",
            )
        )
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="credit-gdp-branch",
        model_version_id="model-v0002",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(run.run_id).status == "completed"
    requirements = runs.full_retrieval_plan(run.run_id)["initial"]["requirements"]
    assert len([r for r in requirements if r["metric_id"] == "CN_GDP"]) == expected


@pytest.mark.parametrize("mode,complete", [(AsOfMode.PUBLIC, False), (AsOfMode.SYSTEM, True)])
def test_full_run_core_selection_preserves_explicit_as_of_mode(
    tmp_path: Path, mode: AsOfMode, complete: bool
) -> None:
    from pring_cycle.runs import RetrievalScope
    from pring_cycle.search_evidence import ModelInputSelector

    paths, runs = prepare(tmp_path)
    known = datetime(2026, 8, 29, tzinfo=UTC)
    EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_EQUITY_CORE_000985",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start="2026-08-28",
            period_end="2026-08-28",
            dimensions={},
            value=100.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference="tushare:index_daily:000985.CSI:2026-08-28",
            release_event_id="fixture:late-core-publication",
            release_at=known,
            public_available_at=known,
            fetched_at=known,
            available_at=known,
            certification_status="certified",
            quality_status="validated",
        )
    )
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="full-run-core-as-of",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 9, 7, tzinfo=UTC),
        cutoff_mode="explicit",
    )
    selection = ModelInputSelector(paths, run, mode=mode).select(
        RetrievalScope("fixture:late-core", ("CN_EQUITY_CORE_000985",), "2026-08-28", "P0", None)
    )
    assert selection.complete is complete


def test_full_run_plans_the_latest_released_period_of_a_metric_not_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real run of 2026-09-24: August's industrial finance comes out on 9/27 and 9/23's
    VIX at 06:00 the next morning, so what a run for 9/23 can fetch is July and 9/22."""
    # Cboe's file as it stood on 9/25, ending on 9/22. Unserved, VIX would rest on whether
    # the real host answered, and a missing VIX is planned like any other gap.
    url = "https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    vix = Path(__file__).parents[1] / "fixtures/quote_sources/VIX_History-20260925.csv"

    class Response(BytesIO):
        status = 200

        def geturl(self) -> str:
            return url

    def cboe(request, *, timeout):
        if request.full_url != url:
            raise OSError("official_page_offline_in_tests")
        return Response(vix.read_bytes())

    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", cboe)
    paths, runs = prepare(tmp_path)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate("model-v0013", explicitly_approved=True)
    run = runs.submit_manual_full(
        target_business_date="2026-09-23",
        client_request_id="latest-released-period",
        model_version_id="model-v0013",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    plan = runs.full_retrieval_plan(run.run_id)
    periods = {
        r["metric_id"]: r["period"]
        for r in plan["initial"]["requirements"]
        if r["metric_id"]
        in {"CN_INDUSTRIAL_FINANCE", "CN_INVENTORY_TURNOVER", "CBOE_VIX_INDEX", "NASDAQ_SOX_INDEX"}
    }
    assert periods == {
        "CN_INDUSTRIAL_FINANCE": "2026-07",
        "CN_INVENTORY_TURNOVER": "2026-07",
        "CBOE_VIX_INDEX": "2026-09-22",
        "NASDAQ_SOX_INDEX": "2026-09-22",
    }
    scopes = {s["release_event_id"]: s["release_status"] for s in plan["initial"]["scopes"]}
    assert scopes["full:nbs_industrial_finance:2026-07"] == "released"
    # VIX is read from Cboe's file and never searched (ADR-0029): no retrieval scope.
    assert "full:cboe_vix_index:2026-09-22" not in scopes


def test_full_run_before_the_fixing_day_plans_the_lpr_in_force(tmp_path: Path) -> None:
    """On 9/10 September's LPR is not fixed until the 20th: August's is the one in force."""
    paths, runs = prepare(tmp_path)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate("model-v0013", explicitly_approved=True)
    run = runs.submit_manual_full(
        target_business_date="2026-09-10",
        client_request_id="lpr-before-fixing",
        model_version_id="model-v0013",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    plan = runs.full_retrieval_plan(run.run_id)
    assert {
        r["period"] for r in plan["initial"]["requirements"] if r["metric_id"] == "CN_LPR_1Y_5Y"
    } == {"2026-08"}
