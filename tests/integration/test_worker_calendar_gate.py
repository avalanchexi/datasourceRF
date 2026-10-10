"""Independent calendar evidence is required before publishing a new full run."""

import json
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle import worker as worker_module
from pring_cycle.domain import CoreAssetState
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.p0 import P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.storage import database_connection
from pring_cycle.trading_calendar import SseCalendar
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_full_run_retrieval import prepare, seed_core_history
from tests.integration.test_p0_gate import readiness
from tests.integration.test_trading_calendar import record_sse_calendar


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 13, tzinfo=UTC))


@pytest.mark.parametrize("has_previous_projection", [False, True])
def test_missing_independent_calendar_blocks_publication_and_preserves_previous_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    runtime_clock,
    has_previous_projection: bool,
) -> None:
    def offline(*args, **kwargs):
        raise OSError("fixture external source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    paths, runs = prepare(tmp_path)
    seed_core_history(paths, include_calendar=False)
    projections = ProjectionSetRepository(paths.database)
    previous_id = None
    if has_previous_projection:
        previous = P0ProjectionService(projections).publish(
            target_business_date="2026-08-28",
            system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
            assets=(
                readiness("bond", CoreAssetState.BULL),
                readiness("stock", CoreAssetState.BULL),
                readiness("commodity", CoreAssetState.BEAR),
            ),
            last_confirmed_stage=None,
        )
        previous_id = previous.projection_set_id
        assert previous_id is not None
        report_run = runs.submit(
            command_type="report_generation",
            target_business_date="2026-08-28",
            client_request_id="previous-report",
            model_version_id="model-v0001",
            system_as_of=datetime(2026, 8, 28, 13, 5, tzinfo=UTC),
        )
        process_pending_run(paths, report_adapters=())
        assert runs.get(report_run.run_id).status == "completed"
    before_history = projections.stage_history()
    before_reports = ReportRepository(paths.database).history()
    assert bool(before_reports) is has_previous_projection
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="missing-independent-calendar",
        model_version_id="model-v0001",
        system_as_of=runtime_clock(),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    window = runs.full_retrieval_plan(submitted.run_id)["final"]["daily_window"]
    assert window["status"] == "unavailable"
    assert window["basis"] == "independent_calendar_unavailable"
    assert stored.status == "action_required"
    assert stored.error_classification == "p0_required_calendar_unavailable"
    assert stored.projection_set_id is None
    assert ReportRepository(paths.database).history() == before_reports
    assert projections.stage_history() == before_history
    if previous_id is None:
        with pytest.raises(LookupError):
            projections.current()
    else:
        assert projections.current().envelope.projection_set_id == previous_id


@pytest.mark.usefixtures("runtime_clock")
def test_an_independent_calendar_lets_the_run_publish_what_the_assets_say(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime_clock
) -> None:
    """The mirror of the gate above: with the calendar present, the run gets to answer.

    Blocking publication when the calendar is missing is only half of #28. The other half is
    that a run holding one publishes a projection whose core assets are populated and whose
    stage is whatever the trend rules make of them -- including empty, when three assets
    genuinely do not form a typical combination. An empty stage is a conclusion here, not the
    silence that a missing calendar produced.
    """

    def offline(*args, **kwargs):
        raise OSError("fixture external source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", offline)
    paths, runs = prepare(tmp_path)
    seed_core_history(paths)

    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="independent-calendar-present",
        model_version_id="model-v0001",
        system_as_of=runtime_clock(),
    )
    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    window = runs.full_retrieval_plan(submitted.run_id)["final"]["daily_window"]
    assert window["status"] == "available"
    assert len(window["dates"]) == 120

    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id or "")
    assets = projection.datasets["core_assets"]["assets"]
    assert {asset["asset"] for asset in assets} == {"bond", "stock", "commodity"}
    overview = projection.datasets["cycle_overview"]
    # These three assets do not form a canonical combination, so an empty stage is the answer
    # -- and it arrives with a reason, which is what separates it from the gate's silence.
    assert overview["current_stage"] is None
    assert overview["stage_reason"] == "noncanonical_combination"


NATIONAL_DAY = frozenset(date(2026, 10, day) for day in range(1, 8))
HOLIDAY_TARGET = date(2026, 9, 30)
# 22:00 in Shanghai on 2026-10-09: 10-08's close is due, 10-09's still within its grace.
AFTER_NATIONAL_DAY = datetime(2026, 10, 9, 14, tzinfo=UTC)


def sse_days(first: date, last: date) -> list[date]:
    days = (first + timedelta(days=n) for n in range((last - first).days + 1))
    return [day for day in days if day.weekday() < 5 and day not in NATIONAL_DAY]


class CalendarOnlyTushare:
    """TuShare answering ``trade_cal`` alone, National Day closed; ``fail_past`` refuses a
    range ending after that day."""

    def __init__(self, *, fail_past: date | None = None) -> None:
        self.fail_past = fail_past
        self.calendar_ranges: list[tuple[date, date]] = []

    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        if payload["api_name"] != "trade_cal":
            raise OSError("fixture_source_unavailable")
        start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
        end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
        self.calendar_ranges.append((start, end))
        if self.fail_past is not None and end > self.fail_past:
            raise OSError("fixture_calendar_unavailable")
        open_days = set(sse_days(start, end))
        items = [
            [day.strftime("%Y%m%d"), int(day in open_days)]
            for day in (start + timedelta(days=n) for n in range((end - start).days + 1))
        ]
        document = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
        return BytesIO(json.dumps(document).encode())

    def past_target(self) -> list[tuple[date, date]]:
        return [item for item in self.calendar_ranges if item[1] > HOLIDAY_TARGET]


def run_after_national_day(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    tushare: CalendarOnlyTushare,
    *,
    stored_through: date = HOLIDAY_TARGET,
    judged_at: datetime = AFTER_NATIONAL_DAY,
) -> tuple[RuntimePaths, str]:
    """A rerun of 2026-09-30 judged after National Day, its cores held to the target.

    The stored calendar reaches ``stored_through``: by default only the window, to the
    target, as after retention pruned what the earlier runs had read (ticket 30).
    """
    install_runtime_clock(monkeypatch, request, judged_at)
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *handlers: tushare)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: tushare)
    monkeypatch.setattr(
        "pring_cycle.eia_html.open_no_redirects",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    sessions = sse_days(HOLIDAY_TARGET - timedelta(days=280), HOLIDAY_TARGET)
    record_sse_calendar(paths, sse_days(sessions[0], stored_through))
    claims = []
    for index, observed in enumerate(sessions):
        for metric_id in CORE_API_IDENTITIES:
            api_name, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                claim(
                    metric_id,
                    observed,
                    100.0 + index,
                    unit="index_points",
                    provider="tushare",
                    reference=f"tushare:{api_name}:{code}:{observed}",
                )
            )
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))
    submitted = runs.submit_manual_full(
        target_business_date=HOLIDAY_TARGET.isoformat(),
        client_request_id="after-national-day",
        model_version_id="model-v0001",
        system_as_of=judged_at,
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    return paths, submitted.run_id


def core_freshness(paths: RuntimePaths, run_id: str) -> dict[str, tuple[str, int | None]]:
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT metric_id, status, periods_behind FROM batch_freshness WHERE batch_id=? "
            "AND metric_id IN (SELECT value FROM json_each(?))",
            (run_id, json.dumps(sorted(CORE_API_IDENTITIES))),
        ).fetchall()
    return {str(row[0]): (str(row[1]), row[2]) for row in rows}


def core_gaps(paths: RuntimePaths, run_id: str) -> set[tuple[str, str]]:
    """How the published run's gap list reads each core: carried, or missing."""
    stored = RunRepository(paths.database).get(run_id)
    projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id or "")
    gaps = projection.datasets["cycle_overview"]["gap_list"]
    assert isinstance(gaps, list)
    return {
        (gap["category"], gap["reason"]) for gap in gaps if gap["metric_id"] in CORE_API_IDENTITIES
    }


def calendar_calls(paths: RuntimePaths, run_id: str, phase: str) -> set[str]:
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT acquisition_id FROM full_run_acquisition JOIN acquisition_request "
            "USING (acquisition_id) WHERE run_id=? AND phase=? AND api_name='trade_cal'",
            (run_id, phase),
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_a_rerun_after_a_long_holiday_fetches_the_calendar_to_the_judging_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Only the window's calendar stored: National Day was judged six weekdays owed and
    each daily metric dropped out as missing (ticket 30). Fetched on to the cutoff, a core
    held to the last session before the holiday is one session behind, and carried."""
    tushare = CalendarOnlyTushare()
    paths, run_id = run_after_national_day(tmp_path, monkeypatch, request, tushare)

    assert tushare.past_target() == [(HOLIDAY_TARGET, date(2026, 10, 9))]
    assert set(core_freshness(paths, run_id).values()) == {("stale", 1)}
    assert core_gaps(paths, run_id) == {("freshness_gap", "one_period_behind_carried")}
    assert len(calendar_calls(paths, run_id, "judging_calendar")) == 1
    plan = RunRepository(paths.database).full_retrieval_plan(run_id)
    assert [fetch["outcome"] for fetch in plan["judging_calendar"]["fetches"]] == ["fetched"]


def test_a_calendar_already_reaching_the_judging_day_is_not_fetched_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    tushare = CalendarOnlyTushare()
    paths, run_id = run_after_national_day(
        tmp_path, monkeypatch, request, tushare, stored_through=date(2026, 10, 9)
    )

    assert tushare.past_target() == []
    assert set(core_freshness(paths, run_id).values()) == {("stale", 1)}
    assert core_gaps(paths, run_id) == {("freshness_gap", "one_period_behind_carried")}
    assert "judging_calendar" not in RunRepository(paths.database).full_retrieval_plan(run_id)
    with database_connection(paths.database) as connection:
        [(stored,)] = connection.execute(
            "SELECT acquisition_id FROM acquisition_request WHERE api_name='trade_cal' "
            "AND json_extract(parameters_json, '$.end_date')='20261009'"
        ).fetchall()
        [(calls,)] = connection.execute(
            "SELECT count(*) FROM acquisition_request WHERE api_name='trade_cal'"
        ).fetchall()
    # The stored response it judged by, made by no run, is kept with this one, and
    # referencing it is no call: the stored one, and those the run made, are all there are.
    assert stored in calendar_calls(paths, run_id, "referenced")
    assert calls == len(tushare.calendar_ranges) + 1
    plan = RunRepository(paths.database).full_retrieval_plan(run_id)
    assert stored not in {call["acquisition_id"] for call in plan["acquisitions"]}


def test_a_failed_calendar_fetch_leaves_weekdays_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    tushare = CalendarOnlyTushare(fail_past=HOLIDAY_TARGET)
    paths, run_id = run_after_national_day(tmp_path, monkeypatch, request, tushare)

    assert len(tushare.past_target()) == 1
    # As before ticket 30: the holiday counted as the weekdays it fell on.
    assert set(core_freshness(paths, run_id).values()) == {("stale", 6)}
    assert core_gaps(paths, run_id) == {("missing", "two_or_more_periods_behind")}
    plan = RunRepository(paths.database).full_retrieval_plan(run_id)
    assert plan["judging_calendar"] == {
        "fetches": [
            {
                "first": "2026-09-30",
                "last": "2026-10-09",
                "outcome": "unavailable:OSError:fixture_calendar_unavailable",
            }
        ]
    }


def test_a_judging_day_inside_the_holiday_is_fetched_with_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Every day after the target a holiday: asked alone, they would be a response with no
    session, which the calendar's parser refuses. Asked with the target, nothing is owed."""
    tushare = CalendarOnlyTushare()
    paths, run_id = run_after_national_day(
        tmp_path, monkeypatch, request, tushare, judged_at=datetime(2026, 10, 7, 14, tzinfo=UTC)
    )

    assert tushare.past_target() == [(HOLIDAY_TARGET, date(2026, 10, 7))]
    assert set(core_freshness(paths, run_id).values()) == {("current", 0)}
    assert core_gaps(paths, run_id) == set()
    plan = RunRepository(paths.database).full_retrieval_plan(run_id)
    assert [fetch["outcome"] for fetch in plan["judging_calendar"]["fetches"]] == ["fetched"]


def test_a_day_turning_while_the_calendar_is_checked_is_asked_after_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stored to 10-08 and checked a moment before midnight, the cutoff falls on 10-09: the
    calendar is asked for again, so the day the run is judged on is stated too."""
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    tushare = CalendarOnlyTushare()
    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *handlers: tushare)
    record_sse_calendar(paths, sse_days(date(2026, 9, 1), date(2026, 10, 8)))
    run = runs.submit_manual_full(
        target_business_date=HOLIDAY_TARGET.isoformat(),
        client_request_id="across-midnight",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 10, 8, 15, 59, tzinfo=UTC),
    )
    # 23:59:59 in Shanghai on 10-08, then the next day.
    moments = iter([datetime(2026, 10, 8, 15, 59, 59, tzinfo=UTC)])
    after = datetime(2026, 10, 8, 16, 0, 1, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return next(moments, after)

    # One time line for the run and the receipts it validates.
    monkeypatch.setattr("pring_cycle.worker.datetime", Clock)
    monkeypatch.setattr("pring_cycle.acquisition.datetime", Clock)

    frozen_at = worker_module._reach_judging_day(paths, run)

    assert frozen_at == after
    assert tushare.past_target() == [(HOLIDAY_TARGET, date(2026, 10, 9))]
    # What the run is judged by at that cutoff states the day it falls on.
    stated = SseCalendar(paths, as_of=frozen_at).stated_between(
        date(2026, 10, 9), date(2026, 10, 9)
    )
    assert stated == {date(2026, 10, 9): True}
    plan = RunRepository(paths.database).full_retrieval_plan(run.run_id)
    assert plan["judging_calendar"] == {
        "fetches": [{"first": "2026-09-30", "last": "2026-10-09", "outcome": "fetched"}]
    }


def test_each_fetch_of_a_turning_day_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fetched, then refused once the day turned: the plan keeps both, the refusal too."""
    paths, runs = prepare(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    tushare = CalendarOnlyTushare(fail_past=date(2026, 10, 8))
    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", lambda *handlers: tushare)
    record_sse_calendar(paths, sse_days(date(2026, 9, 1), HOLIDAY_TARGET))
    run = runs.submit_manual_full(
        target_business_date=HOLIDAY_TARGET.isoformat(),
        client_request_id="fetched-then-refused",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 10, 8, 15, 59, tzinfo=UTC),
    )

    class Clock(datetime):
        """A moment before midnight in Shanghai until the first answer, then just after."""

        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return (
                datetime(2026, 10, 8, 16, 0, 1, tzinfo=UTC)
                if tushare.calendar_ranges
                else (datetime(2026, 10, 8, 15, 59, 59, tzinfo=UTC))
            )

    monkeypatch.setattr("pring_cycle.worker.datetime", Clock)
    monkeypatch.setattr("pring_cycle.acquisition.datetime", Clock)

    worker_module._reach_judging_day(paths, run)

    plan = RunRepository(paths.database).full_retrieval_plan(run.run_id)
    assert plan["judging_calendar"] == {
        "fetches": [
            {"first": "2026-09-30", "last": "2026-10-08", "outcome": "fetched"},
            {
                "first": "2026-09-30",
                "last": "2026-10-09",
                "outcome": "unavailable:OSError:fixture_calendar_unavailable",
            },
        ]
    }
