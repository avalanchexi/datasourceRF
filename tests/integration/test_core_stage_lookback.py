"""Without a formal stage in the window, a run looks back by year for the last one (ADR-0040)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from http.client import IncompleteRead
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_window_history import weekdays_back

TARGET = date(2026, 8, 3)
# The closes a run holds: the 120-session window and the 140 before its first day.
HELD = weekdays_back(TARGET, 260)
WINDOW_START = HELD[140]
CORE_CODES = {code for _api_name, code in CORE_API_IDENTITIES.values()}
STOCK = "000985.CSI"
EPOCH = date(2018, 1, 1)

Close = Callable[[date], float]


def rising(day: date) -> float:
    return 100.0 + 0.1 * (day - EPOCH).days


def falling(day: date) -> float:
    return 1000.0 - 0.1 * (day - EPOCH).days


def turning_down(turn: date) -> Close:
    def close(day: date) -> float:
        return rising(min(day, turn)) - 0.1 * max((day - turn).days, 0)

    return close


# The years read back close for a week around mid-February and in early October, so a
# year's sessions are not plain weekdays and a floor can fall on a closed day.
CLOSED = frozenset(
    day
    for year in range(2015, HELD[0].year + 1)
    for first, length in ((date(year, 2, 12), 7), (date(year, 10, 1), 7))
    for day in (first + timedelta(days=offset) for offset in range(length))
    if day < HELD[0]
)


def is_open(day: date) -> bool:
    return day.weekday() < 5 and day not in CLOSED


def open_days(start: date, end: date) -> list[date]:
    days = (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    return [day for day in days if is_open(day)]


def response(payload: dict[str, Any], stock: Close, *, short: bool = False) -> bytes:
    """The source's answer; a ``short`` calendar answer leaves its range's first day out."""
    start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
    end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
    calendar = open_days(start, end)
    if payload["api_name"] == "trade_cal":
        # Every day of the range is stated, closed ones too (residual 02).
        fields = ["cal_date", "is_open"]
        items: list[list[object]] = [
            [day.strftime("%Y%m%d"), int(is_open(day))]
            for day in (start + timedelta(days=offset) for offset in range((end - start).days + 1))
        ][int(short) :]
    else:
        code = payload["params"]["ts_code"]
        close = stock if code == STOCK else rising
        fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
        items = []
        for day in calendar:
            previous = open_days(day - timedelta(days=20), day - timedelta(days=1))[-1]
            change = close(day) / close(previous) - 1.0
            items.append(
                [
                    code,
                    day.strftime("%Y%m%d"),
                    round(close(day), 4),
                    round(close(previous), 4),
                    change if payload["api_name"] == "fut_index_daily" else change * 100.0,
                ]
            )
    return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()


class Run:
    def __init__(self, paths: RuntimePaths, run_id: str, requests: list[tuple[str, str, str]]):
        self.paths = paths
        self.run_id = run_id
        self.core_requests = requests
        self.most_in_flight = 0

    @property
    def projection(self) -> ProjectionSet:
        return ProjectionSetRepository(self.paths.database).current()

    @property
    def plan(self) -> dict[str, Any]:
        return RunRepository(self.paths.database).full_retrieval_plan(self.run_id)


def full_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stock: Close,
    fail_before: date | None = None,
    failure: Exception | None = None,
    calendar_short_before: date | None = None,
) -> Run:
    """A manual full run whose cores are priced by date; the stock core by ``stock``.

    ``fail_before``: core requests ending before that day fail with ``failure``, as a network
    fault would; ``calendar_short_before``: calendar answers ending before that day leave a
    day out.
    """
    monkeypatch.setattr(
        "pring_cycle.eia_html.open_no_redirects",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    requests: list[tuple[str, str, str]] = []
    active = [0, 0]  # in flight now, most at once
    lock = threading.Lock()

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            with lock:
                active[0] += 1
                active[1] = max(active)
            try:
                payload = json.loads(request.data)
                params = payload["params"]
                if payload["api_name"] == "trade_cal":
                    end = datetime.strptime(params["end_date"], "%Y%m%d").date()
                    short = calendar_short_before is not None and end < calendar_short_before
                    return BytesIO(response(payload, stock, short=short))
                if params.get("ts_code") not in CORE_CODES:
                    raise OSError("fixture_context_unavailable")
                requests.append((params["ts_code"], params["start_date"], params["end_date"]))
                end = datetime.strptime(params["end_date"], "%Y%m%d").date()
                if fail_before is not None and end < fail_before:
                    raise failure or OSError("fixture_lookback_unavailable")
                return BytesIO(response(payload, stock))
            finally:
                with lock:
                    active[0] -= 1

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
    )
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="core-stage-lookback",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = runs.get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    result = Run(paths, run.run_id, requests)
    result.most_in_flight = active[1]
    return result


def run_requests() -> list[tuple[str, str, str]]:
    return [(code, HELD[0].strftime("%Y%m%d"), TARGET.strftime("%Y%m%d")) for code in CORE_CODES]


def lookback_requests(years: int) -> list[tuple[str, str, str]]:
    """Year N asks the 139 sessions a state on its floor needs, and on to the closes held."""
    requests = []
    reach = HELD[0]
    for year in range(1, years + 1):
        warm_up = open_days(HELD[0].replace(year=2014), floor(year) - timedelta(days=1))[-139]
        days = open_days(warm_up, reach - timedelta(days=1))
        requests += [
            (code, days[0].strftime("%Y%m%d"), days[-1].strftime("%Y%m%d")) for code in CORE_CODES
        ]
        reach = days[0]
    return requests


def floor(years: int) -> date:
    """The first day searched once ``years`` were read back."""
    return WINDOW_START.replace(year=WINDOW_START.year - years)


def first_searched(years: int) -> str:
    return open_days(floor(years), floor(years) + timedelta(days=20))[0].isoformat()


def assert_isolated(run: Run) -> None:
    """The prices looked back at are no claim and no model input, and only the window stays."""
    core_inputs = run.projection.datasets["core_assets"]["model_input_observation_version_ids"]
    assert isinstance(core_inputs, list)
    assert len(core_inputs) == 3 * len(HELD)
    with sqlite3.connect(run.paths.database) as connection:
        # The run's calls, kept with the run as any of its calls are.
        owned = connection.execute(
            "SELECT count(*) FROM full_run_acquisition WHERE phase='core_lookback'"
        ).fetchone()[0]
        stored = connection.execute(
            "SELECT count(*) FROM source_claim_acquisition JOIN full_run_acquisition "
            "USING (acquisition_id) WHERE phase='core_lookback'"
        ).fetchone()[0]
    assert (owned > 0, stored) == (True, 0)
    window = run.plan["final"]["daily_window"]["dates"]
    evidence = EvidenceRepository(run.paths.database)
    for metric_id in CORE_API_IDENTITIES:
        series = evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        assert [point.period_end for point in series] == window


def pages(run: Run) -> tuple[str, str, str]:
    from pring_cycle.dashboard import _home_page, _report_reader, _stage_history_page

    report = ReportRepository(run.paths.database).history()[0]
    return (
        str(_home_page(run.projection)),
        str(_stage_history_page(run.projection, ())),
        str(_report_reader(report)),
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_stage_in_the_window_needs_no_lookback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The stock core turns down inside the window: Stage III first, then no stage.
    run = full_run(tmp_path, monkeypatch, stock=turning_down(date(2026, 4, 1)))

    overview = run.projection.datasets["cycle_overview"]
    assert (overview["current_stage"], overview["stage_reason"]) == (
        None,
        "noncanonical_combination",
    )
    assert overview["last_confirmed_stage"] == "stage_iii"
    assert overview.get("last_confirmed_lookback") is None
    assert sorted(run.core_requests) == sorted(run_requests())
    assert "core_lookback" not in run.plan
    assert all("回溯得出" not in page for page in pages(run))


@pytest.mark.usefixtures("runtime_clock")
def test_a_lookback_stops_at_the_first_year_that_finds_a_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stage III held until the stock core turned down, before the window began.
    run = full_run(tmp_path, monkeypatch, stock=turning_down(date(2025, 10, 1)))

    projection = run.projection
    overview = projection.datasets["cycle_overview"]
    assert (overview["current_stage"], overview["stage_reason"]) == (
        None,
        "noncanonical_combination",
    )
    assert overview["last_confirmed_stage"] == "stage_iii"
    lookback = overview["last_confirmed_lookback"]
    assert isinstance(lookback, dict)
    assert {key: lookback[key] for key in ("status", "stage", "stage_date", "years")} == {
        "status": "found",
        "stage": "stage_iii",
        "stage_date": "2026-01-15",
        "years": 1,
    }
    assert (lookback["core_requests"], lookback["calendar_requests"]) == (3, 1)
    assert lookback["searched_through"] == (WINDOW_START - timedelta(days=1)).isoformat()
    # The days searched start a year before the window, on its first session from then.
    assert lookback["searched_from"] == first_searched(1)
    # Published with the stage history, and the run's record states its reach and cost.
    assert projection.datasets["stage_history"]["last_confirmed_lookback"] == lookback
    assert run.plan["core_lookback"] == lookback
    # The window's assessments keep what each day computed: no stage before the lookback.
    events = projection.datasets["stage_history"]["events"]
    assert isinstance(events, list)
    assert all(event["last_confirmed_stage"] is None for event in events)
    # One year of each core, one request each, after the run's own; never two at once.
    assert sorted(run.core_requests) == sorted(run_requests() + lookback_requests(1))
    assert run.most_in_flight == 1
    # The macro confirmation reads no stage: the lookback's is history only.
    confirmation = projection.datasets["macro"].get("confirmation")
    assert not isinstance(confirmation, dict) or confirmation.get("stage") is None
    assert_isolated(run)
    home, history, report = pages(run)
    for page in (home, history, report):
        assert "回溯得出" in page
        assert "2026-01-15" in page


@pytest.mark.usefixtures("runtime_clock")
def test_five_years_without_a_stage_leave_it_empty_and_say_how_far_was_searched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = full_run(tmp_path, monkeypatch, stock=falling)

    overview = run.projection.datasets["cycle_overview"]
    assert overview["last_confirmed_stage"] is None
    lookback = overview["last_confirmed_lookback"]
    assert isinstance(lookback, dict)
    assert (lookback["status"], lookback["stage"], lookback["stage_date"]) == (
        "not_found",
        None,
        None,
    )
    assert (lookback["years"], lookback["core_requests"], lookback["calendar_requests"]) == (
        5,
        15,
        5,
    )
    assert lookback["searched_through"] == (WINDOW_START - timedelta(days=1)).isoformat()
    assert lookback["searched_from"] == first_searched(5)
    assert run.plan["core_lookback"] == lookback
    assert sorted(run.core_requests) == sorted(run_requests() + lookback_requests(5))
    assert run.most_in_flight == 1
    assert_isolated(run)
    home, history, report = pages(run)
    for page in (home, history, report):
        assert "已回溯 5 年" in page
        assert lookback["searched_from"] in page


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "failure", [OSError("fixture_lookback_unavailable"), IncompleteRead(b"")], ids=type
)
def test_a_failed_lookback_leaves_the_stage_empty_and_the_run_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    run = full_run(
        tmp_path,
        monkeypatch,
        stock=turning_down(date(2025, 10, 1)),
        fail_before=HELD[0],
        failure=failure,
    )

    overview = run.projection.datasets["cycle_overview"]
    assert overview["last_confirmed_stage"] is None
    lookback = overview["last_confirmed_lookback"]
    assert isinstance(lookback, dict)
    assert (lookback["status"], lookback["stage"], lookback["years"]) == ("failed", None, 1)
    assert (lookback["core_requests"], lookback["calendar_requests"]) == (1, 1)
    assert lookback["failure"]
    assert run.plan["core_lookback"] == lookback
    assert ReportRepository(run.paths.database).history()
    assert_isolated(run)
    home, history, report = pages(run)
    for page in (home, history, report):
        assert "回溯失败" in page


@pytest.mark.usefixtures("runtime_clock")
def test_a_lookback_whose_calendar_leaves_a_day_out_fails_before_any_core_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = full_run(
        tmp_path,
        monkeypatch,
        stock=turning_down(date(2025, 10, 1)),
        calendar_short_before=HELD[0],
    )

    lookback = run.projection.datasets["cycle_overview"]["last_confirmed_lookback"]
    assert isinstance(lookback, dict)
    assert (lookback["status"], lookback["years"]) == ("failed", 1)
    assert (lookback["core_requests"], lookback["calendar_requests"]) == (0, 1)
    assert lookback["failure"] == "ValueError:china_trading_calendar_incomplete"
    assert sorted(run.core_requests) == sorted(run_requests())
    assert run.plan["core_lookback"] == lookback
