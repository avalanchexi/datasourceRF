"""The SSE trading calendar: which days the market opens, read and fetched in one place.

The calendar comes only from TuShare ``trade_cal`` responses captured by the core adapter
(parser ``CORE_PARSER_VERSION``). Market breadth once asked the same API for open days
itself; those older receipts keep breadth figures, not sessions, and are never read as a
calendar. Breadth now reads its sessions here.

Responses are data versions of one source: where two cover the same day, the later one
wins, and each day it changes is kept as a revision (never a conflict that blocks a run).
This module says which sessions it knows and how far that knowledge reaches; what to do
when it is not enough (weekdays at submit, a strict 120-session window for a full run,
only the target day for CZCE warrants) is left to each caller.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from pring_cycle.acquisition import Acquired, AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_PARSER_VERSION
from pring_cycle.storage import database_connection


class TradingCalendar:
    """SSE sessions known from the calendar source, and weekdays beyond what it covers.

    The sessions alone cover only up to the last of them; ``through`` extends that when the
    source listed later days as closed (a range ending on a holiday).
    """

    def __init__(self, days: Iterable[date] = (), *, through: date | None = None) -> None:
        self._days = frozenset(days)
        self._first = min(self._days, default=None)
        self._last = max(self._days, default=None)
        if through is not None and self._last is not None:
            self._last = max(self._last, through)

    def is_trading(self, day: date) -> bool:
        if self._first is not None and self._last is not None and self._first <= day <= self._last:
            return day in self._days
        return day.weekday() < 5

    def nth_from(self, day: date, n: int) -> date:
        """The ``n``-th session counted from ``day``; the 0th is the first on or after it."""
        while not self.is_trading(day):
            day += timedelta(days=1)
        for _ in range(n):
            day += timedelta(days=1)
            while not self.is_trading(day):
                day += timedelta(days=1)
        return day

    def latest_on_or_before(self, day: date) -> date:
        while not self.is_trading(day):
            day -= timedelta(days=1)
        return day


class CalendarMaterialError(ValueError):
    """An unreadable calendar artifact, with the identity of the receipt it came from."""

    def __init__(self, error: Exception, receipt: AcquisitionReceipt) -> None:
        super().__init__(str(error))
        self.provenance: dict[str, Any] = {
            "claim_ids": [],
            "acquisition_id": receipt.acquisition_id,
            "raw_hash": receipt.raw_hash,
            "normalized_hash": receipt.normalized_hash,
        }


@dataclass(frozen=True)
class CalendarRevision:
    """A day a later response stated differently from an earlier one."""

    day: date
    was_open: bool
    is_open: bool
    acquisition_id: str

    def document(self) -> dict[str, object]:
        return {
            "day": self.day.isoformat(),
            "was_open": self.was_open,
            "is_open": self.is_open,
            "acquisition_id": self.acquisition_id,
        }


class SseCalendar:
    """What the validated core calendar responses say, as known at ``as_of``.

    ``as_of`` defaults to now on the clock receipts are validated by; a full run passes its
    frozen cutoff so a response validated later is not read.
    """

    def __init__(self, paths: RuntimePaths, *, as_of: datetime | None = None) -> None:
        cutoff = (as_of or utc_now()).astimezone(UTC)
        acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        with database_connection(paths.database) as connection:
            rows = connection.execute(
                "SELECT acquisition_id, validated_at FROM acquisition_request "
                "WHERE provider='tushare' AND api_name='trade_cal' AND state='validated' "
                "AND parser_version=?",
                (CORE_PARSER_VERSION,),
            ).fetchall()
        readable = []
        unreadable: list[tuple[Exception, AcquisitionReceipt]] = []
        for acquisition_id, validated_at in rows:
            validated = datetime.fromisoformat(validated_at)
            if validated > cutoff:
                continue
            receipt = acquisitions.get(acquisition_id)
            try:
                start = datetime.strptime(receipt.parameters["start_date"], "%Y%m%d").date()
                end = datetime.strptime(receipt.parameters["end_date"], "%Y%m%d").date()
                document = json.loads(acquisitions.read_receipt_content(receipt, "normalized"))
                if not isinstance(document, list) or not all(
                    isinstance(day, str) for day in document
                ):
                    continue
                sessions = frozenset(date.fromisoformat(day) for day in document)
            except (KeyError, ValueError, LookupError, OSError, TypeError) as error:
                unreadable.append((error, receipt))
                continue
            if "is_open" in receipt.parameters:
                # A filtered response lists open days only: it covers no day beyond them.
                if not sessions:
                    continue
                start, end = min(sessions), max(sessions)
            readable.append((validated, acquisition_id, start, end, sessions))
        self.unreadable = tuple(unreadable)
        opened: dict[date, bool] = {}
        stated_by: dict[date, str] = {}
        revisions: list[CalendarRevision] = []
        for _validated, acquisition_id, start, end, sessions in sorted(readable):
            day = start
            while day <= end:
                is_open = day in sessions
                if day in opened and opened[day] != is_open:
                    revisions.append(CalendarRevision(day, opened[day], is_open, acquisition_id))
                opened[day] = is_open
                stated_by[day] = acquisition_id
                day += timedelta(days=1)
        self._open = opened
        self._stated_by = stated_by
        self._validated = {acquisition_id: validated for validated, acquisition_id, *_ in readable}
        self.revisions = tuple(revisions)

    def _segment(self, day: date) -> tuple[date, date] | None:
        """The run of consecutive covered days that contains ``day``."""
        if day not in self._open:
            return None
        first = last = day
        while first - timedelta(days=1) in self._open:
            first -= timedelta(days=1)
        while last + timedelta(days=1) in self._open:
            last += timedelta(days=1)
        return first, last

    def around(self, day: date) -> TradingCalendar | None:
        """The sessions of the covered stretch holding ``day``, or None when it is uncovered."""
        segment = self._segment(day)
        if segment is None:
            return None
        first, last = segment
        return TradingCalendar(
            (d for d, is_open in self._open.items() if is_open and first <= d <= last),
            through=last,
        )

    def window(self, target: date, sessions: int) -> tuple[date, ...]:
        """The last ``sessions`` sessions to ``target``, or () unless all are known.

        Complete means ``target`` is itself a session and every day from the first of them
        to ``target`` is covered by some response.
        """
        segment = self._segment(target)
        if segment is None or not self._open[target]:
            return ()
        first = segment[0]
        days = sorted(d for d, is_open in self._open.items() if is_open and first <= d <= target)
        return tuple(days[-sessions:]) if len(days) >= sessions else ()

    def sessions_between(self, first: date, last: date) -> tuple[date, ...] | None:
        """The sessions from ``first`` to ``last``, or None unless every day is covered."""
        day = first
        while day <= last:
            if day not in self._open:
                return None
            day += timedelta(days=1)
        return tuple(
            sorted(d for d, is_open in self._open.items() if is_open and first <= d <= last)
        )

    def sources(self, first: date, last: date) -> tuple[str, ...]:
        """The responses whose statements the days from ``first`` to ``last`` rest on."""
        return tuple(
            sorted({source for day, source in self._stated_by.items() if first <= day <= last})
        )

    def unreadable_since(
        self, first: date, last: date
    ) -> tuple[tuple[Exception, AcquisitionReceipt], ...]:
        """Unreadable responses validated after every one the days ``first``..``last`` rest on.

        Such a response may have stated those days differently; an older one was superseded.
        """
        newest = max(
            (self._validated[source] for source in self.sources(first, last)), default=None
        )
        return tuple(
            (error, receipt)
            for error, receipt in self.unreadable
            if newest is None or receipt.validated_at is None or receipt.validated_at > newest
        )

    def revisions_between(self, first: date, last: date) -> tuple[CalendarRevision, ...]:
        return tuple(item for item in self.revisions if first <= item.day <= last)


class CalendarAdapter(Protocol):
    def acquire_calendar(
        self, repository: AcquisitionRepository, start: date, end: date
    ) -> Acquired[tuple[date, ...]]: ...


def acquire_sse_calendar(
    paths: RuntimePaths, adapter: CalendarAdapter, start: date, end: date
) -> tuple[date, ...]:
    """Fetch and keep the SSE sessions from ``start`` to ``end`` as one calendar response."""
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    return adapter.acquire_calendar(acquisitions, start, end).value


class _CalendarSlot:
    calendar: TradingCalendar | None = None


_run_calendar: ContextVar[_CalendarSlot | None] = ContextVar("run_calendar", default=None)


@contextmanager
def run_calendar_scope() -> Iterator[None]:
    """Open a slot for the run's SSE calendar, filled once the run has validated one."""
    token = _run_calendar.set(_CalendarSlot())
    try:
        yield
    finally:
        _run_calendar.reset(token)


def current_calendar() -> TradingCalendar:
    """The run's SSE calendar once known, else weekdays."""
    slot = _run_calendar.get()
    return (slot.calendar if slot is not None else None) or TradingCalendar()


def use_run_calendar(calendar: TradingCalendar) -> None:
    """Judge freshness for the rest of the run against ``calendar``."""
    slot = _run_calendar.get()
    if slot is not None:
        slot.calendar = calendar
