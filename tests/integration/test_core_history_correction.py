"""Window days summarized on the old core history get a correction in a run (ticket 07).

A run that reads the cores as ADR-0040 has them re-summarizes, from the history it already
holds, each window day whose latest summary was made on the old reach (the last 160
sessions), and appends it as a correction: the old summaries, sets and reports stay.
"""

from __future__ import annotations

import functools
import json
import sqlite3
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

import pring_cycle.worker as worker
from pring_cycle.dashboard import dashboard_page
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_stage_lookback import (
    CORE_CODES,
    Close,
    response,
    rising,
    turning_down,
)
from tests.integration.test_core_window_history import weekdays_back
from tests.web.test_dashboard_contract import _text

FIRST, SECOND, THIRD = date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 5)
REASON = "core_history_basis_changed"


class Runtime:
    """A runtime whose cores are priced by date and whose context sources are down."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, stock: Close = rising
    ) -> None:
        monkeypatch.setattr(
            "pring_cycle.eia_html.open_no_redirects",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
        )
        self.monkeypatch = monkeypatch
        self.paths = RuntimePaths.discover(tmp_path / "runtime")
        initialize_runtime(self.paths)
        self.paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        ModelRepository(self.paths.database).activate("model-v0001", explicitly_approved=True)
        self.requests: list[tuple[str, str]] = []
        requests = self.requests

        class FixtureOpener:
            def open(self, request: Any, *, timeout: int) -> BytesIO:
                payload = json.loads(request.data)
                requests.append((payload["api_name"], json.dumps(payload["params"])))
                if payload["api_name"] != "trade_cal" and (
                    payload["params"].get("ts_code") not in CORE_CODES
                ):
                    raise OSError("fixture_context_unavailable")
                return BytesIO(response(payload, stock))

        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
        )
        self.repository = ProjectionSetRepository(self.paths.database)
        self.runs = RunRepository(self.paths.database)

    def run(self, target: date, *, old_reach: bool = False) -> str:
        """One manual full run; ``old_reach`` reads the cores' last 160 sessions, as runs did
        before ADR-0040 (the run's own request, as it was then made)."""
        refresh = worker._refresh_core_sources
        with self.monkeypatch.context() as patch:
            if old_reach:
                patch.setattr(
                    worker,
                    "_refresh_core_sources",
                    functools.partial(_old_reach, refresh),
                )
            run = self.runs.submit_manual_full(
                target_business_date=target.isoformat(),
                client_request_id=f"core-history-correction-{target}-{len(self.requests)}",
                model_version_id="model-v0001",
                system_as_of=datetime.now(UTC),
            )
            process_pending_run(self.paths, report_adapters=())
        stored = self.runs.get(run.run_id)
        assert stored.status == "completed", stored.error_classification
        return run.run_id

    def window(self, run_id: str) -> list[str]:
        return list(self.runs.full_retrieval_plan(run_id)["final"]["daily_window"]["dates"])

    def latest(self) -> dict[str, dict[str, Any]]:
        """Each day's summary as the stage history lists it."""
        history = self.repository.stage_history()
        days = [str(event["business_date"]) for event in history]
        assert len(days) == len(set(days)), "a day is listed more than once"
        return {str(event["business_date"]): dict(event) for event in history}


def _old_reach(refresh: Any, *args: Any, **kwargs: Any) -> None:
    refresh(*args, **{**kwargs, "core_sessions": 160})


def short_of_history(event: dict[str, Any]) -> bool:
    return any(asset["reason"] == "insufficient_history" for asset in event["core_assets"])


@pytest.mark.usefixtures("runtime_clock")
def test_a_run_appends_a_correction_for_each_window_day_on_the_old_core_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime(tmp_path, monkeypatch)
    first = runtime.run(FIRST, old_reach=True)
    old = runtime.latest()
    # The old reach measures from the 140th close on: the window's first 99 days fall short.
    assert sum(short_of_history(event) for event in old.values()) == 99
    old_window = runtime.window(first)
    early = old_window[20]
    assert runtime.repository.last_confirmed_stage(on_or_before=early) is None
    old_sets = {
        day: runtime.repository.get(str(event["projection_set_id"])).datasets
        for day, event in old.items()
    }
    old_reports = ReportRepository(runtime.paths.database).history()
    requests_before = len(runtime.requests)

    second = runtime.run(SECOND)
    second_requests = runtime.requests[requests_before:]

    window = runtime.window(second)
    corrected = [day for day in window if day < SECOND.isoformat()]
    latest = runtime.latest()
    assert list(latest) == window
    for day in corrected:
        event = latest[day]
        assert not short_of_history(event), day
        assert event["corrects"] == {
            "assessment_id": old[day]["assessment_id"],
            "projection_set_id": old[day]["projection_set_id"],
            "reason": REASON,
        }
    assert not short_of_history(latest[SECOND.isoformat()])
    assert "corrects" not in latest[SECOND.isoformat()]
    assert runtime.repository.current().datasets["cycle_overview"]["current_stage"] == "stage_iii"
    # The stage before a day reads the corrected history, as the lookback's trigger does.
    assert runtime.repository.last_confirmed_stage(on_or_before=early) == "stage_iii"
    # The old summaries, their sets and the report stay as they were published (the first
    # window day's left with the window).
    for day in corrected:
        event = old[day]
        assert runtime.repository.p0_assessment(str(event["assessment_id"])) == event
        assert runtime.repository.get(str(event["projection_set_id"])).datasets == old_sets[day]
    reports = ReportRepository(runtime.paths.database).history()
    assert [report for report in reports if report in old_reports] == list(old_reports)
    assert [report.target_business_date for report in reports if report not in old_reports] == [
        SECOND.isoformat()
    ]
    # The run states what it corrected; the cores are one range request each, as ever.
    assert runtime.runs.full_retrieval_plan(second)["summary_corrections"] == {
        "reason": REASON,
        "corrected_days": corrected,
        "count": len(corrected),
    }
    reach = weekdays_back(SECOND, 260)[0].strftime("%Y%m%d")
    core_requests = sorted(
        json.loads(params)["ts_code"]
        for api_name, params in second_requests
        if json.loads(params).get("ts_code") in CORE_CODES
        and json.loads(params)["start_date"] == reach
    )
    assert core_requests == sorted(CORE_CODES)
    # Pages and the published history show each day once, at its latest summary.
    current = runtime.repository.current()
    events = current.datasets["stage_history"]["events"]
    assert isinstance(events, list)
    # (It was published before the run's end let the first window's first day go.)
    assert [event["business_date"] for event in events] == [old_window[0], *window]
    page = _text(
        dashboard_page("/stage-history", current, (), (), runtime.repository.stage_history())
    )
    assert all(page.count(f"{day} · ") == 1 for day in window)
    assert page.count("更正版本") == len(corrected)

    requests_before = len(runtime.requests)
    third = runtime.run(THIRD)

    # A day already on the new reach is not summarized again; no call is added for any.
    assert runtime.runs.full_retrieval_plan(third)["summary_corrections"] == {
        "reason": REASON,
        "corrected_days": [],
        "count": 0,
    }
    again = runtime.latest()
    assert {day: again[day] for day in latest if day in again} == {
        day: event for day, event in latest.items() if day in again
    }
    assert len(runtime.requests) - requests_before == len(second_requests)


@pytest.mark.usefixtures("runtime_clock")
def test_a_run_short_of_the_core_history_corrects_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Its history would leave the days as short as before; a later run holding it corrects them.
    runtime = Runtime(tmp_path, monkeypatch)
    runtime.run(FIRST, old_reach=True)
    old = runtime.latest()

    second = runtime.run(SECOND, old_reach=True)

    assert runtime.runs.full_retrieval_plan(second)["summary_corrections"] == {
        "reason": REASON,
        "corrected_days": [],
        "count": 0,
    }
    latest = runtime.latest()
    assert {day: latest[day] for day in old if day in latest} == {
        day: event for day, event in old.items() if day in latest
    }

    third = runtime.run(THIRD)

    assert runtime.runs.full_retrieval_plan(third)["summary_corrections"]["count"] == len(
        [day for day in runtime.window(third) if day < THIRD.isoformat()]
    )


class ProcessLost(BaseException):
    """The worker's process ends where it stands."""


@pytest.mark.usefixtures("runtime_clock")
def test_a_resumed_run_states_the_corrections_its_lost_attempt_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each correction is stored as it is made; the run states them all once it completes.
    runtime = Runtime(tmp_path, monkeypatch)
    runtime.run(FIRST, old_reach=True)
    advance = RunRepository.advance

    def lost_after_the_backfill(self: RunRepository, run_id: str, step: str) -> Any:
        if step == "publishing_projection":
            raise ProcessLost
        return advance(self, run_id, step)

    with monkeypatch.context() as patch:
        patch.setattr(RunRepository, "advance", lost_after_the_backfill)
        with pytest.raises(ProcessLost):
            runtime.run(SECOND)
    [lost] = [
        run for run in runtime.runs.list_runs() if run.target_business_date == SECOND.isoformat()
    ]
    runtime.runs.mark_interrupted(lost.run_id, "worker_process_lost")
    runtime.runs.resume(lost.run_id, client_request_id="resume-lost", confirm_external_calls=True)
    process_pending_run(runtime.paths, report_adapters=())

    assert runtime.runs.get(lost.run_id).status == "completed"
    corrected = [day for day in runtime.window(lost.run_id) if day < SECOND.isoformat()]
    plan = runtime.runs.full_retrieval_plan(lost.run_id)
    assert plan["summary_corrections"]["corrected_days"] == corrected
    # Made once each: the resumed attempt left the days the lost one corrected.
    latest = runtime.latest()
    assert all("corrects" in latest[day] for day in corrected)
    with sqlite3.connect(runtime.paths.database) as connection:
        made = connection.execute(
            "SELECT count(*) FROM p0_assessment WHERE json_extract(document_json, "
            "'$.corrects.reason') = ?",
            (REASON,),
        ).fetchone()[0]
    assert made == len(corrected)


@pytest.mark.usefixtures("runtime_clock")
def test_the_lookback_reads_the_corrected_stage_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The stock turns down early in the window: on the old reach no window day had a stage,
    # so the target looked back past the window; corrected, the early days have one.
    turn = weekdays_back(FIRST, 100)[0]
    runtime = Runtime(tmp_path, monkeypatch, stock=turning_down(turn))
    first = runtime.run(FIRST, old_reach=True)
    assert all(event["current_stage"] is None for event in runtime.latest().values())
    assert "core_lookback" in runtime.runs.full_retrieval_plan(first)

    second = runtime.run(SECOND)

    latest = runtime.latest()
    assert any(event["current_stage"] == "stage_iii" for event in latest.values())
    assert latest[SECOND.isoformat()]["current_stage"] is None
    assert "core_lookback" not in runtime.runs.full_retrieval_plan(second)
    overview = runtime.repository.current().datasets["cycle_overview"]
    assert overview["last_confirmed_stage"] == "stage_iii"
    assert "last_confirmed_lookback" not in overview
