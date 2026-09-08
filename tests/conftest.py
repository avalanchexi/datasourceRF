from collections.abc import Callable
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


@pytest.fixture
def runtime_clock(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Callable[[], datetime]:
    """Keep a full run's external clocks on the same advancing UTC timeline."""
    origin = datetime.now(UTC)
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
