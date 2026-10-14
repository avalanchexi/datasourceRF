"""Ticket 08 (residuals 2026-10-14): the 09:30 run holds the previous session's 16:30 close.

CFETS publishes no dated history of the 16:30 close; its intraday file covers the current
session only. The close is fetched once the session has passed 16:30, so the next morning's
run, which finds the new session not yet closed, holds the session before it.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition_outcome import SOURCE_FAILED, SUCCEEDED, AcquisitionOutcomes
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.quote_sources import CHINAMONEY_USDCNY_1630, refresh_quote_source
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import CloseCheck, fetch_close_if_due
from tests.conftest import install_runtime_clock
from tests.integration.test_trading_calendar import record_sse_calendar

METRIC = "CN_USDCNY_CLOSE_1630"
VERSION = "metric-catalog-v0001"


def cfets_file(last_date: str, close: str, points: list[tuple[str, float]]) -> bytes:
    """The CFETS intraday file: its 16:30 point is the one whose time is a blank."""
    snapshot = ", ".join(f'{{"time" : "{time}",spotPrice : {price}}}' for time, price in points)
    return json.dumps(
        {
            "data": {
                "closeSpotPrice": close,
                "spotPriceStr": str(points[-1][1]),
                "lastDate": last_date,
                "chartsDataStr": f"[ {snapshot} ]",
            }
        }
    ).encode()


# Tuesday 13 October past 16:30, its night session still trading.
EVENING = cfets_file(
    "2026-10-13 17:10", "7.1250", [("09:30", 7.1302), (" ", 7.1250), ("17:10", 7.1244)]
)
# Wednesday 14 October at 09:40: the new session has no close yet.
MORNING = cfets_file("2026-10-14 9:40", "---", [("09:30", 7.1238), ("09:40", 7.1236)])


class OfficialFile(BytesIO):
    status = 200

    def __init__(self, url: str, content: bytes) -> None:
        super().__init__(content)
        self.url = url

    def geturl(self) -> str:
        return self.url


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def serve(monkeypatch: pytest.MonkeyPatch, content: bytes) -> list[str]:
    asked: list[str] = []

    def official(request: Any, *, timeout: float) -> OfficialFile:
        asked.append(request.full_url)
        return OfficialFile(request.full_url, content)

    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", official)
    return asked


def refresh(paths: RuntimePaths, start: date, end: date) -> int:
    return refresh_quote_source(
        paths, CHINAMONEY_USDCNY_1630, start_date=start, end_date=end, definition_version=VERSION
    )


def held(paths: RuntimePaths) -> dict[str, float | None]:
    return {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            METRIC,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(minutes=1),
            definition_version=VERSION,
        )
    }


def last_attempt(paths: RuntimePaths) -> Any:
    return AcquisitionOutcomes(paths.database).latest(
        METRIC, as_of=datetime.now(UTC) + timedelta(minutes=1)
    )


def test_a_run_past_0930_holds_the_close_fetched_the_evening_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    # Tuesday 17:10 in Shanghai: the evening fetch.
    install_runtime_clock(monkeypatch, request, datetime(2026, 10, 13, 9, 10, tzinfo=UTC))
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    serve(monkeypatch, EVENING)
    refresh(paths, date(2026, 10, 13), date(2026, 10, 13))
    # Wednesday 9:40 in Shanghai: the scheduled run for Tuesday fetches the file again.
    morning = datetime(2026, 10, 14, 1, 40, tzinfo=UTC)
    install_runtime_clock(monkeypatch, request, morning)
    serve(monkeypatch, MORNING)

    added = refresh(paths, date(2026, 9, 1), date(2026, 10, 13))

    by_cutoff = {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            METRIC,
            mode=AsOfMode.SYSTEM,
            as_of=morning + timedelta(minutes=5),
            definition_version=VERSION,
        )
    }
    assert added == 0
    assert by_cutoff == {"2026-10-13": 7.1250}
    attempt = AcquisitionOutcomes(paths.database).latest(
        METRIC, as_of=morning + timedelta(minutes=5)
    )
    assert attempt is not None
    assert (attempt.outcome, attempt.metadata["completeness"]) == (SUCCEEDED, "source_empty")


def test_a_file_of_the_current_session_only_is_source_empty_not_an_error(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, MORNING)

    added = refresh(paths, date(2026, 9, 1), date(2026, 10, 13))

    assert (added, held(paths)) == (0, {})
    attempt = last_attempt(paths)
    assert (attempt.outcome, attempt.metadata["completeness"]) == (SUCCEEDED, "source_empty")


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(
            # The 03:00 night close standing where the 16:30 close should be.
            cfets_file(
                "2026-10-14 3:00", "7.1231", [("09:30", 7.1302), (" ", 7.1250), ("03:00", 7.1231)]
            ),
            "chinamoney_close_snapshot_mismatch",
            id="night-close",
        ),
        pytest.param(b"<html>maintenance</html>", "chinamoney_close_document_invalid", id="html"),
    ],
)
def test_a_close_that_does_not_read_as_the_1630_close_is_a_source_failure(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch, content: bytes, reason: str
) -> None:
    serve(monkeypatch, content)

    with pytest.raises(ValueError, match=reason):
        refresh(paths, date(2026, 10, 13), date(2026, 10, 13))

    assert held(paths) == {}
    attempt = last_attempt(paths)
    assert (attempt.outcome, attempt.metadata["reason"]) == (SOURCE_FAILED, reason)


# The Worker's evening fetch: one source, no run (ticket 08's fallback, spec "16:30 收盘价").

TUESDAY = date(2026, 10, 13)


def at(hour: int, minute: int, second: int = 0, *, day: date = TUESDAY) -> datetime:
    """``hour:minute`` in Shanghai on ``day``."""
    local = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)
    return local - timedelta(hours=8)


@pytest.fixture
def scheduled(paths: RuntimePaths) -> RuntimePaths:
    """The effective model active, the schedule on, Monday and Tuesday stated SSE sessions."""
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(str(effective_model_manifest()["model_version_id"]), explicitly_approved=True)
    RunRepository(paths.database).configure_schedule(enabled=True, requested_by="test")
    record_sse_calendar(paths, [date(2026, 10, 12), TUESDAY])
    return paths


def held_effective(paths: RuntimePaths) -> dict[str, float | None]:
    return {
        point.period_end: point.selected_value
        for point in EvidenceRepository(paths.database).metric_series(
            METRIC,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC) + timedelta(minutes=1),
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
    }


def test_the_worker_fetches_the_days_close_once_from_its_update_time(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From 16:35, the close's registered update time, the first check takes the session's
    close; later checks that day ask nothing more. The next morning's run then holds it."""
    asked = serve(monkeypatch, EVENING)
    check = CloseCheck()

    before = fetch_close_if_due(scheduled, at(16, 34, 59), check)
    first = fetch_close_if_due(scheduled, at(16, 35), check)
    later = [fetch_close_if_due(scheduled, at(16, 35, n), check) for n in range(1, 4)]
    evening = fetch_close_if_due(scheduled, at(20, 0), check)

    assert (before, first, later, evening) == (False, True, [False] * 3, False)
    assert len(asked) == 1
    assert held_effective(scheduled) == {"2026-10-13": 7.1250}


def test_a_worker_restarted_after_the_close_is_held_does_not_ask_again(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serve(monkeypatch, EVENING)
    fetch_close_if_due(scheduled, at(16, 35), CloseCheck())

    restarted = fetch_close_if_due(scheduled, at(18, 0), CloseCheck())

    assert (restarted, len(asked)) == (False, 1)


def test_a_file_without_the_close_yet_is_asked_again_ten_minutes_later_until_2100(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    not_yet = cfets_file("2026-10-13 16:30", "---", [("09:30", 7.1302), ("16:30", 7.1250)])
    asked = serve(monkeypatch, not_yet)
    check = CloseCheck()

    first = fetch_close_if_due(scheduled, at(16, 35), check)
    waiting = fetch_close_if_due(scheduled, at(16, 44, 59), check)
    asked_again = fetch_close_if_due(scheduled, at(16, 45), check)
    asked_after = serve(monkeypatch, EVENING)
    at_the_deadline = fetch_close_if_due(scheduled, at(21, 0), check)

    assert (first, waiting, asked_again, at_the_deadline) == (True, False, True, True)
    assert (len(asked), len(asked_after)) == (2, 1)
    assert held_effective(scheduled) == {"2026-10-13": 7.1250}


def test_a_failed_fetch_is_recorded_and_asked_again_but_not_past_2100(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serve(monkeypatch, b"<html>maintenance</html>")
    check = CloseCheck()

    failed = fetch_close_if_due(scheduled, at(20, 55), check)
    past_deadline = fetch_close_if_due(scheduled, at(21, 5, 1), check)

    assert (failed, past_deadline) == (True, False)
    assert len(asked) == 1
    attempt = last_attempt(scheduled)
    assert (attempt.outcome, attempt.metadata["reason"]) == (
        SOURCE_FAILED,
        "chinamoney_close_document_invalid",
    )


def test_an_unforeseen_failure_does_not_stop_the_worker_and_is_asked_again(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(request: Any, *, timeout: float) -> OfficialFile:
        raise RuntimeError("fixture_transport_broken")

    monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", broken)
    check = CloseCheck()

    failed = fetch_close_if_due(scheduled, at(17, 0), check)
    asked = serve(monkeypatch, EVENING)
    waiting = fetch_close_if_due(scheduled, at(17, 9, 59), check)
    retried = fetch_close_if_due(scheduled, at(17, 10), check)

    assert (failed, waiting, retried, len(asked)) == (True, False, True, 1)
    events = (scheduled.logs / "worker.jsonl").read_text(encoding="utf-8")
    assert "close_fetch_failed:RuntimeError:fixture_transport_broken" in events
    assert held_effective(scheduled) == {"2026-10-13": 7.1250}


@pytest.mark.parametrize(
    "unfit",
    ["schedule_off", "sse_closed", "day_not_stated", "builtin_catalog"],
)
def test_no_close_is_fetched_off_schedule_or_off_an_sse_session(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch, unfit: str
) -> None:
    """Fetched only to feed the scheduled run (ADR-0010: off, the Worker asks nothing of
    its own), on a day the stored SSE calendar states open, for a catalog that registers it."""
    asked = serve(monkeypatch, EVENING)
    day = TUESDAY
    if unfit == "schedule_off":
        RunRepository(scheduled.database).configure_schedule(enabled=False, requested_by="test")
    elif unfit == "sse_closed":
        record_sse_calendar(scheduled, [date(2026, 10, 15), date(2026, 10, 19)])
        day = date(2026, 10, 16)  # A Friday the response states closed.
    elif unfit == "day_not_stated":
        day = date(2026, 10, 14)
    else:
        ModelRepository(scheduled.database).activate("model-v0001", explicitly_approved=True)

    fetched = fetch_close_if_due(scheduled, at(17, 0, day=day), CloseCheck())

    assert (fetched, asked) == (False, [])


# The next morning's make-up (user's decision 2026-10-14): before 9:30 the file still
# covers the session before, so a close missed that evening is fetched then.

WEDNESDAY = date(2026, 10, 14)
# Wednesday before 9:30: the file still stands at the close of Tuesday's night session.
NEXT_MORNING = cfets_file(
    "2026-10-14 3:00", "7.1250", [("09:30", 7.1302), (" ", 7.1250), ("03:00", 7.1231)]
)


def test_a_close_missed_in_the_evening_is_fetched_the_next_morning_before_0930(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serve(monkeypatch, NEXT_MORNING)
    check = CloseCheck()

    first = fetch_close_if_due(scheduled, at(8, 0, day=WEDNESDAY), check)
    later = fetch_close_if_due(scheduled, at(8, 30, day=WEDNESDAY), check)

    assert (first, later, len(asked)) == (True, False, 1)
    assert held_effective(scheduled) == {"2026-10-13": 7.1250}


def test_the_next_morning_asks_nothing_when_the_evening_held_the_close(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serve(monkeypatch, EVENING)
    check = CloseCheck()
    fetch_close_if_due(scheduled, at(16, 35), check)

    morning = fetch_close_if_due(scheduled, at(8, 0, day=WEDNESDAY), check)

    assert (morning, len(asked)) == (False, 1)


@pytest.mark.parametrize(
    ("observed", "asks"),
    [
        pytest.param(at(21, 0, 1), False, id="past-the-deadline"),
        pytest.param(at(0, 0, day=WEDNESDAY), True, id="at-midnight"),
        pytest.param(at(9, 29, 59, day=WEDNESDAY), True, id="at-0929"),
        pytest.param(at(9, 30, day=WEDNESDAY), False, id="at-0930"),
        pytest.param(at(16, 34, 59, day=WEDNESDAY), False, id="before-the-evening"),
    ],
)
def test_the_morning_make_up_ends_when_the_session_opens_at_0930(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch, observed: datetime, *, asks: bool
) -> None:
    """From 9:30 the file covers the new session: the session before has left it."""
    asked = serve(monkeypatch, NEXT_MORNING)

    fetched = fetch_close_if_due(scheduled, observed, CloseCheck())

    assert (fetched, len(asked)) == (asks, int(asks))


@pytest.mark.parametrize(
    "sessions",
    [
        pytest.param([date(2026, 10, 9), date(2026, 10, 12)], id="weekend-stated-closed"),
        pytest.param([date(2026, 10, 8), date(2026, 10, 9)], id="weekend-left-unstated"),
    ],
)
def test_the_monday_morning_makes_up_the_friday_close_across_the_weekend(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch, sessions: list[date]
) -> None:
    """The session before is the latest the stored SSE calendar states open before today; a
    Worker asleep over the weekend has left Saturday and Sunday unstated."""
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(str(effective_model_manifest()["model_version_id"]), explicitly_approved=True)
    RunRepository(paths.database).configure_schedule(enabled=True, requested_by="test")
    record_sse_calendar(paths, sessions)
    # The file has stood at the close of Friday's night session since Saturday 03:00.
    asked = serve(monkeypatch, FRIDAYS_CLOSE)

    fetched = fetch_close_if_due(paths, at(8, 0, day=date(2026, 10, 12)), CloseCheck())

    assert (fetched, len(asked)) == (True, 1)
    assert held_effective(paths) == {"2026-10-09": 7.1310}


FRIDAYS_CLOSE = cfets_file(
    "2026-10-10 3:00", "7.1310", [("09:30", 7.1355), (" ", 7.1310), ("03:00", 7.1302)]
)


def test_an_older_held_close_does_not_stand_for_a_session_the_calendar_leaves_unstated(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The calendar is stored through Tuesday, whose close is held; the Worker slept through
    Wednesday. On Thursday morning the file holds Wednesday's close, which is fetched."""
    serve(monkeypatch, EVENING)
    fetch_close_if_due(scheduled, at(16, 35), CloseCheck())
    asked = serve(
        monkeypatch,
        cfets_file(
            "2026-10-15 3:00", "7.1200", [("09:30", 7.1250), (" ", 7.1200), ("03:00", 7.1190)]
        ),
    )

    fetched = fetch_close_if_due(scheduled, at(8, 0, day=date(2026, 10, 15)), CloseCheck())

    assert (fetched, len(asked)) == (True, 1)
    assert held_effective(scheduled) == {"2026-10-13": 7.1250, "2026-10-14": 7.1200}


def test_an_empty_morning_answer_is_asked_again_while_the_calendar_leaves_a_day_unstated(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thursday morning, the calendar stored through Tuesday: a file that has not reached
    Wednesday's 16:30 is the source empty, not the close made up. Ten minutes on, the file
    gives Wednesday's close."""
    serve(monkeypatch, EVENING)
    fetch_close_if_due(scheduled, at(16, 35), CloseCheck())
    thursday = date(2026, 10, 15)
    asked_empty = serve(
        monkeypatch, cfets_file("2026-10-14 16:00", "---", [("09:30", 7.1250), ("16:00", 7.1220)])
    )
    check = CloseCheck()

    empty = fetch_close_if_due(scheduled, at(8, 0, day=thursday), check)
    attempt = last_attempt(scheduled)
    asked = serve(
        monkeypatch,
        cfets_file(
            "2026-10-15 3:00", "7.1200", [("09:30", 7.1250), (" ", 7.1200), ("03:00", 7.1190)]
        ),
    )
    retried = fetch_close_if_due(scheduled, at(8, 10, day=thursday), check)

    assert (attempt.outcome, attempt.metadata["completeness"]) == (SUCCEEDED, "source_empty")
    assert (empty, retried, len(asked_empty), len(asked)) == (True, True, 1, 1)
    assert held_effective(scheduled) == {"2026-10-13": 7.1250, "2026-10-14": 7.1200}


def test_a_morning_without_a_stated_session_before_reads_the_calendar_again_later(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monday 12 October is the first day the stored calendar states: no session before it
    is known yet. Ten minutes on, a calendar stored meanwhile (a manual run's) is read."""
    asked = serve(monkeypatch, FRIDAYS_CLOSE)
    check = CloseCheck()
    monday = date(2026, 10, 12)

    unknown = fetch_close_if_due(scheduled, at(8, 0, day=monday), check)
    record_sse_calendar(scheduled, [date(2026, 10, 9), monday])
    later = fetch_close_if_due(scheduled, at(8, 10, day=monday), check)

    assert (unknown, later, len(asked)) == (False, True, 1)
    assert held_effective(scheduled) == {"2026-10-09": 7.1310}


def test_a_morning_make_up_leaves_that_evenings_fetch_to_its_own_window(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    record_sse_calendar(scheduled, [TUESDAY, WEDNESDAY])
    asked = serve(monkeypatch, NEXT_MORNING)
    check = CloseCheck()
    morning = fetch_close_if_due(scheduled, at(8, 0, day=WEDNESDAY), check)
    serve(
        monkeypatch,
        cfets_file(
            "2026-10-14 17:00", "7.1200", [("09:30", 7.1238), (" ", 7.1200), ("17:00", 7.1195)]
        ),
    )

    evening = fetch_close_if_due(scheduled, at(16, 35, day=WEDNESDAY), check)

    assert (morning, evening, len(asked)) == (True, True, 1)
    assert held_effective(scheduled) == {"2026-10-13": 7.1250, "2026-10-14": 7.1200}


def test_a_failed_morning_make_up_is_asked_again_ten_minutes_later_but_not_from_0930(
    scheduled: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serve(monkeypatch, b"<html>maintenance</html>")
    check = CloseCheck()

    failed = fetch_close_if_due(scheduled, at(9, 15, day=WEDNESDAY), check)
    waiting = fetch_close_if_due(scheduled, at(9, 24, 59, day=WEDNESDAY), check)
    retried = fetch_close_if_due(scheduled, at(9, 25, day=WEDNESDAY), check)
    opened = fetch_close_if_due(scheduled, at(9, 35, day=WEDNESDAY), check)

    assert (failed, waiting, retried, opened, len(asked)) == (True, False, True, False, 2)
    attempt = last_attempt(scheduled)
    assert (attempt.outcome, attempt.metadata["reason"]) == (
        SOURCE_FAILED,
        "chinamoney_close_document_invalid",
    )
    assert held_effective(scheduled) == {}
