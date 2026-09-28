from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from itertools import count
from time import monotonic

import pytest


def _clock_datetime(now: Callable[[], datetime]) -> type[datetime]:
    class ClockMeta(type):
        def __instancecheck__(cls, value: object) -> bool:
            return isinstance(value, datetime)

    class ClockDateTime(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None):
            value = now()
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    return ClockDateTime


@pytest.fixture
def acquisition_clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[], datetime]:
    """A controlled external clock for receipt and revision-ordering tests."""
    origin = datetime(2026, 9, 8, tzinfo=UTC)
    ticks = count()

    def now() -> datetime:
        return origin + timedelta(microseconds=next(ticks))

    # utc_now's existing callable defaults read this external clock boundary.
    # Do not replace acquisition, validation, persistence, or time-order guards.
    monkeypatch.setattr("pring_cycle.acquisition.datetime", _clock_datetime(now))
    return now


def install_runtime_clock(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, origin: datetime
) -> Callable[[], datetime]:
    """Run one test on an advancing UTC timeline starting at ``origin``.

    Tests whose fixtures are dated originals pin the origin, so that what they assert about
    evidence freshness stays the same on every day the suite runs.
    """
    started = monotonic()

    def now() -> datetime:
        return origin + timedelta(seconds=monotonic() - started)

    clock_type = _clock_datetime(now)
    for module in ("acquisition", "core_history", "worker", "runs", "retrieval_ledger"):
        monkeypatch.setattr(f"pring_cycle.{module}.datetime", clock_type)
    # Tests opting into this fixture must use the same time for before/after
    # queries and run acceptance. Explicit clocks in individual tests still win.
    if getattr(request.module, "datetime", None) is datetime:
        monkeypatch.setattr(request.module, "datetime", clock_type)
    return now


@pytest.fixture
def runtime_clock(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Callable[[], datetime]:
    """Keep a full run's external clocks on the same advancing UTC timeline."""
    return install_runtime_clock(monkeypatch, request, datetime.now(UTC))


@pytest.fixture(scope="session", autouse=True)
def _official_pages_offline() -> Iterator[None]:
    """The CSI page, NBS schedule page, official context pages (a first full run traces the
    RRR back through the PBC's chronicles) and CZCE's warrant report are never reached unless
    a test serves its own.

    Module-scoped runtime fixtures run before function-scoped patches, so the default has
    to be installed for the whole session.
    """

    def offline(url: str) -> bytes:
        raise OSError("official_page_offline_in_tests")

    def offline_request(request: object, *, timeout: float) -> bytes:
        raise OSError("official_page_offline_in_tests")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("pring_cycle.official_core._fetch", offline)
        patch.setattr("pring_cycle.release_schedule._fetch_page", offline)
        patch.setattr("pring_cycle.official_context.urlopen", offline_request)
        patch.setattr("pring_cycle.czce_warrants._fetch", offline)
        # A test serving CZCE's reports need not wait between them.
        patch.setattr("pring_cycle.czce_warrants._sleep", lambda seconds: None)
        yield


@pytest.fixture(scope="session", autouse=True)
def _ai_websearch_off() -> Iterator[None]:
    """No test reaches a real Codex or Claude CLI for AI WebSearch unless it opts in.

    AI WebSearch is on by default; a test that wants it deletes this variable and puts
    fake CLIs on PATH (tests/integration/test_ai_websearch.py).
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PRING_CYCLE_AI_WEBSEARCH", "off")
        yield
