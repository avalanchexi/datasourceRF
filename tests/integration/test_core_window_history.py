"""A run reads the cores far enough back that every window day has a core state (ADR-0040)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response
from tests.integration.test_core_official_fill import csindex_page, full_run
from tests.integration.test_worker_execution import seed_independent_calendar

TARGET = date(2026, 8, 3)
CORE_CODES = {code for _api_name, code in CORE_API_IDENTITIES.values()}


def weekdays_back(day: date, count: int) -> list[date]:
    days: list[date] = []
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return list(reversed(days))


@pytest.mark.usefixtures("runtime_clock")
def test_every_window_day_has_a_core_state_from_one_range_request_per_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline_optional(*args: object, **kwargs: object) -> None:
        raise OSError("fixture optional source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", offline_optional)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    core_requests: list[tuple[str, str, str]] = []
    active = [0, 0]  # in flight now, most at once
    lock = threading.Lock()

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            with lock:
                active[0] += 1
                active[1] = max(active)
            try:
                payload = json.loads(request.data)
                code = payload["params"].get("ts_code")
                if payload["api_name"] == "trade_cal":
                    return BytesIO(historical_response(payload))
                if code not in CORE_CODES:
                    raise OSError("fixture_context_unavailable")
                params = payload["params"]
                core_requests.append((code, params["start_date"], params["end_date"]))
                return BytesIO(historical_response(payload))
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
        client_request_id="core-window-history",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())

    assert runs.get(run.run_id).status == "completed"
    window = runs.full_retrieval_plan(run.run_id)["final"]["daily_window"]["dates"]
    assert len(window) == 120
    events = ProjectionSetRepository(paths.database).current().datasets["stage_history"]["events"]
    assert isinstance(events, list)
    assert [event["business_date"] for event in events] == window
    for event in events:
        for asset in event["core_assets"]:
            assert asset["reason"] != "insufficient_history", (event["business_date"], asset)
            assert asset["distance_pct"] is not None
    # The window's 120 sessions and, before its first, the 140 closes a trend reading needs.
    reach = weekdays_back(TARGET, 260)
    assert sorted(core_requests) == sorted(
        (code, reach[0].strftime("%Y%m%d"), TARGET.strftime("%Y%m%d")) for code in CORE_CODES
    )
    assert active[1] == 1
    # The closes before the window were read for the trend and cleaned at the run's end.
    evidence = EvidenceRepository(paths.database)
    for metric_id in CORE_API_IDENTITIES:
        series = evidence.metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        assert [point.period_end for point in series] == window


@pytest.mark.usefixtures("runtime_clock")
def test_the_official_page_fills_a_core_over_the_same_sessions_as_tushare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A longer page would hand the trend more history for that core than for the others.
    urls: list[str] = []

    def page(url: str) -> bytes:
        urls.append(url)
        return csindex_page(url)

    full_run(tmp_path, monkeypatch, tushare_fails={"000985.CSI"}, csindex=page)

    [url] = urls
    query = parse_qs(urlsplit(url).query)
    reach = weekdays_back(TARGET, 260)
    assert (query["startDate"], query["endDate"]) == (
        [reach[0].strftime("%Y%m%d")],
        [TARGET.strftime("%Y%m%d")],
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_held_calendar_sets_the_official_page_reach_when_tushare_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The calendar held covers the sessions wanted, not the margin a fetch would ask for.
    reach = weekdays_back(TARGET, 260)
    urls: list[str] = []

    class DownOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            raise OSError("fixture_unavailable")

    def page(url: str) -> bytes:
        urls.append(url)
        return csindex_page(url)

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", DownOpener)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *h: DownOpener())
    monkeypatch.setattr(
        "pring_cycle.eia_html.open_no_redirects",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    monkeypatch.setattr("pring_cycle.official_core._fetch", page)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    seed_independent_calendar(paths, reach)
    RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="core-fill-calendar-held",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())

    assert len(urls) == 2
    for url in urls:
        query = parse_qs(urlsplit(url).query)
        assert (query["startDate"], query["endDate"]) == (
            [reach[0].strftime("%Y%m%d")],
            [TARGET.strftime("%Y%m%d")],
        )
