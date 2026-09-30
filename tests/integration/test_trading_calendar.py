"""The SSE trading calendar: what the core calendar responses say, read in one place."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.acquisition import AcquisitionRepository, utc_now
from pring_cycle.czce_warrants import window_trading_days
from pring_cycle.freshness import target_business_date
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_PARSER_VERSION, TushareCoreAdapter
from pring_cycle.trading_calendar import SseCalendar, acquire_sse_calendar

SHANGHAI = ZoneInfo("Asia/Shanghai")


def sse_adapter(*, closed: Iterable[date] = (), at: datetime | None = None) -> TushareCoreAdapter:
    """TuShare's ``trade_cal`` answering every day of a range: weekdays open unless closed."""
    closures = frozenset(closed)

    def transport(payload: dict[str, object]) -> bytes:
        assert payload["api_name"] == "trade_cal"
        params = payload["params"]
        assert isinstance(params, dict)
        start = datetime.strptime(params["start_date"], "%Y%m%d").date()
        end = datetime.strptime(params["end_date"], "%Y%m%d").date()
        items = [
            [day.strftime("%Y%m%d"), int(day.weekday() < 5 and day not in closures)]
            for day in (start + timedelta(days=n) for n in range((end - start).days + 1))
        ]
        document = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
        return json.dumps(document).encode()

    return TushareCoreAdapter(
        "fixture-token", transport=transport, clock=(lambda: at) if at is not None else utc_now
    )


def record_sse_calendar(
    paths: RuntimePaths, sessions: Iterable[date], *, at: datetime | None = None
) -> None:
    """Keep one core calendar response listing ``sessions``; other weekdays in range closed.

    ``at`` defaults to midnight UTC of the first session, so runs with any later cutoff
    read it.
    """
    days = sorted(set(sessions))
    first, last = days[0], days[-1]
    closed = {
        first + timedelta(days=n)
        for n in range((last - first).days + 1)
        if first + timedelta(days=n) not in days
    }
    moment = at or datetime.combine(first, datetime.min.time(), tzinfo=UTC)
    acquire_sse_calendar(paths, sse_adapter(closed=closed, at=moment), first, last)


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def capture_breadth_calendar(paths: RuntimePaths, output: list[object]) -> None:
    # Breadth asks trade_cal for open days too, but its receipt keeps the breadth figures the
    # whole group produced, not the sessions.
    AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="tushare",
        api_name="trade_cal",
        parameters={
            "exchange": "SSE",
            "start_date": "20250202",
            "end_date": "20260925",
            "is_open": "1",
        },
        fields="cal_date,is_open",
        parser_version="tushare-context-parser-v0002",
        fetch=lambda: b"{}",
        parse=lambda raw: output,
        normalize=lambda value: value,
    )


def test_holidays_are_read_from_the_calendar_response(paths: RuntimePaths) -> None:
    launched = datetime(2026, 10, 8, 10, tzinfo=SHANGHAI)
    holiday = {date(2026, 10, 1) + timedelta(days=n) for n in range(7)}
    acquire_sse_calendar(paths, sse_adapter(closed=holiday), date(2026, 9, 8), date(2026, 10, 8))

    calendar = SseCalendar(paths).around(date(2026, 10, 8))

    assert calendar is not None
    assert target_business_date(launched, calendar).isoformat() == "2026-09-30"


def test_a_range_ending_on_a_closure_covers_that_day(paths: RuntimePaths) -> None:
    # Mid-Autumn 2026-09-25 (Friday): TuShare lists it with is_open=0, so the range ends on a
    # closure and the last open session alone understates what the response covers.
    acquire_sse_calendar(
        paths, sse_adapter(closed={date(2026, 9, 25)}), date(2026, 8, 26), date(2026, 9, 25)
    )

    calendar = SseCalendar(paths).around(date(2026, 9, 25))

    assert calendar is not None
    assert not calendar.is_trading(date(2026, 9, 25))
    launched = datetime(2026, 9, 25, 18, 30, tzinfo=SHANGHAI)
    assert target_business_date(launched, calendar).isoformat() == "2026-09-24"


def test_an_uncovered_day_has_no_calendar(paths: RuntimePaths) -> None:
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 8, 26), date(2026, 9, 24))

    assert SseCalendar(paths).around(date(2026, 9, 25)) is None


@pytest.mark.parametrize(
    "breadth_output",
    [[], [{"metric_id": "CN_EQ_ADV_DEC", "period_end": "2026-09-25", "value": 1}]],
    ids=["nothing_new", "a_new_day"],
)
def test_the_breadth_calendar_request_is_not_a_calendar(
    paths: RuntimePaths, breadth_output: list[object]
) -> None:
    capture_breadth_calendar(paths, breadth_output)
    assert SseCalendar(paths).around(date(2026, 9, 25)) is None

    acquire_sse_calendar(
        paths, sse_adapter(closed={date(2026, 9, 25)}), date(2026, 8, 26), date(2026, 9, 25)
    )
    capture_breadth_calendar(paths, breadth_output)

    calendar = SseCalendar(paths).around(date(2026, 9, 25))
    assert calendar is not None
    assert not calendar.is_trading(date(2026, 9, 25))


def test_the_window_is_the_last_120_sessions_the_responses_cover(paths: RuntimePaths) -> None:
    target = date(2026, 9, 24)
    assert SseCalendar(paths).window(target, 120) == ()
    # CZCE keeps the SSE's sessions; with no complete window it knows only the target day.
    assert window_trading_days(paths, target) == (target,)

    acquire_sse_calendar(paths, sse_adapter(), date(2025, 8, 1), date(2025, 12, 31))
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 1, 1), target)

    window = SseCalendar(paths).window(target, 120)
    assert len(window) == 120
    assert window[-1] == target
    assert all(day.weekday() < 5 for day in window)
    assert window_trading_days(paths, target) == window


def test_the_window_does_not_depend_on_the_prices_being_checked(paths: RuntimePaths) -> None:
    # A core price missing on a session is missing detail inside the window, never a closure.
    target = date(2026, 8, 28)
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 1, 1), target)

    window = SseCalendar(paths).window(target, 120)

    assert date(2026, 8, 20) in window
    assert len(window) == 120


def test_the_breadth_calendar_request_does_not_cover_a_gap_between_responses(
    paths: RuntimePaths,
) -> None:
    target = date(2026, 9, 24)
    acquire_sse_calendar(paths, sse_adapter(), date(2025, 8, 1), date(2025, 12, 31))
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 6, 1), target)
    capture_breadth_calendar(paths, [])

    assert SseCalendar(paths).window(target, 120) == ()
    assert window_trading_days(paths, target) == (target,)


def test_a_later_response_revises_a_day_and_the_change_is_kept(paths: RuntimePaths) -> None:
    earlier = datetime(2026, 9, 1, tzinfo=UTC)
    later = datetime(2026, 9, 20, tzinfo=UTC)
    first, last = date(2026, 9, 1), date(2026, 9, 30)
    acquire_sse_calendar(paths, sse_adapter(at=earlier), first, last)
    acquire_sse_calendar(paths, sse_adapter(closed={date(2026, 9, 25)}, at=later), first, last)

    calendar = SseCalendar(paths)

    around = calendar.around(date(2026, 9, 25))
    assert around is not None
    assert not around.is_trading(date(2026, 9, 25))
    assert [(item.day, item.was_open, item.is_open) for item in calendar.revisions] == [
        (date(2026, 9, 25), True, False)
    ]
    assert calendar.revisions_between(date(2026, 9, 26), last) == ()


def test_a_response_validated_after_the_cutoff_is_not_read(paths: RuntimePaths) -> None:
    earlier = datetime(2026, 9, 1, tzinfo=UTC)
    later = datetime(2026, 9, 20, tzinfo=UTC)
    first, last = date(2026, 9, 1), date(2026, 9, 30)
    acquire_sse_calendar(paths, sse_adapter(at=earlier), first, last)
    acquire_sse_calendar(paths, sse_adapter(closed={date(2026, 9, 25)}, at=later), first, last)

    calendar = SseCalendar(paths, as_of=later - timedelta(microseconds=1))

    around = calendar.around(date(2026, 9, 25))
    assert around is not None
    assert around.is_trading(date(2026, 9, 25))
    assert calendar.revisions == ()
    assert SseCalendar(paths, as_of=earlier - timedelta(microseconds=1)).around(first) is None


def test_an_unreadable_response_is_reported_not_read(paths: RuntimePaths) -> None:
    AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="tushare",
        api_name="trade_cal",
        parameters={"exchange": "SSE", "end_date": "20260924"},
        fields="cal_date,is_open",
        parser_version=CORE_PARSER_VERSION,
        fetch=lambda: b"{}",
        parse=lambda raw: ["2026-09-24"],
        normalize=lambda value: value,
    )

    calendar = SseCalendar(paths)

    assert calendar.around(date(2026, 9, 24)) is None
    assert len(calendar.unreadable) == 1


def capture_unreadable_calendar(paths: RuntimePaths, at: datetime) -> None:
    AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider="tushare",
        api_name="trade_cal",
        parameters={"exchange": "SSE", "start_date": "20260101", "end_date": "20260924"},
        fields="cal_date,is_open",
        parser_version=CORE_PARSER_VERSION,
        fetch=lambda: b"{}",
        parse=lambda raw: ["not-a-date"],
        normalize=lambda value: value,
        clock=lambda: at,
    )


def test_only_an_unreadable_response_newer_than_the_window_s_sources_can_matter(
    paths: RuntimePaths,
) -> None:
    target = date(2026, 9, 24)
    capture_unreadable_calendar(paths, datetime(2026, 9, 1, tzinfo=UTC))
    acquire_sse_calendar(
        paths, sse_adapter(at=datetime(2026, 9, 10, tzinfo=UTC)), date(2026, 1, 1), target
    )

    superseded = SseCalendar(paths)
    window = superseded.window(target, 120)
    assert len(window) == 120
    assert len(superseded.unreadable) == 1
    assert superseded.unreadable_since(window[0], target) == ()

    capture_unreadable_calendar(paths, datetime(2026, 9, 20, tzinfo=UTC))

    assert len(SseCalendar(paths).unreadable_since(window[0], target)) == 1


def test_the_sessions_of_a_range_are_known_only_when_every_day_is_covered(
    paths: RuntimePaths,
) -> None:
    # Breadth reads 600 days of sessions; a range the responses leave a gap in is unknown.
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 1, 1), date(2026, 3, 31))
    acquire_sse_calendar(paths, sse_adapter(), date(2026, 5, 1), date(2026, 6, 30))
    calendar = SseCalendar(paths)

    sessions = calendar.sessions_between(date(2026, 2, 1), date(2026, 3, 31))
    assert sessions is not None and sessions[0] == date(2026, 2, 2)
    assert all(day.weekday() < 5 for day in sessions)
    assert calendar.sessions_between(date(2026, 3, 1), date(2026, 5, 31)) is None


class CalendarOpener:
    """TuShare's trade_cal over the network, or a refusal with ``code``."""

    def __init__(self, calls: list[dict[str, str]], code: int = 0) -> None:
        self.calls, self.code = calls, code

    def open(self, request: Any, *, timeout: float) -> Any:
        from io import BytesIO

        payload = json.loads(request.data)
        self.calls.append(payload["params"])
        if self.code:
            return BytesIO(json.dumps({"code": self.code, "msg": "refused"}).encode())
        start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
        end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
        items = [
            [day.strftime("%Y%m%d"), int(day.weekday() < 5)]
            for day in (start + timedelta(days=n) for n in range((end - start).days + 1))
        ]
        document = {"code": 0, "data": {"fields": ["cal_date", "is_open"], "items": items}}
        return BytesIO(json.dumps(document).encode())


def test_breadth_reads_its_sessions_from_the_calendar_and_fetches_only_what_is_missing(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.worker import _breadth_calendar

    calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        "pring_cycle.source_adapters.build_opener", lambda *handlers: CalendarOpener(calls)
    )
    target = date(2026, 9, 24)

    sessions, calendar_ids = _breadth_calendar(paths, "fixture-token", target)
    again, _ = _breadth_calendar(paths, "fixture-token", target)

    assert calls == [{"exchange": "SSE", "start_date": "20250201", "end_date": "20260924"}]
    assert sessions == again and sessions[-1] == target
    assert len(calendar_ids) == 1


def test_a_refused_breadth_calendar_is_a_source_failure_telling_a_rate_limit(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pring_cycle.tushare_context import TushareSourceError
    from pring_cycle.worker import _breadth_calendar

    for code, reason in ((40203, "tushare_rate_limited"), (40001, "tushare_source_failed:40001")):
        monkeypatch.setattr(
            "pring_cycle.source_adapters.build_opener",
            lambda *handlers, code=code: CalendarOpener([], code),
        )
        with pytest.raises(TushareSourceError, match=reason):
            _breadth_calendar(paths, "fixture-token", date(2026, 9, 24))
