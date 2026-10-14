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
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, EVENING)
    refresh(paths, date(2026, 10, 13), date(2026, 10, 13))
    serve(monkeypatch, MORNING)

    added = refresh(paths, date(2026, 9, 1), date(2026, 10, 13))

    assert added == 0
    assert held(paths) == {"2026-10-13": 7.1250}
    attempt = last_attempt(paths)
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
    return datetime(day.year, day.month, day.day, hour - 8, minute, second, tzinfo=UTC)


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
