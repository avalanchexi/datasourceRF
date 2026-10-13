"""What one day's summary may know of: the public cutoff the plan, the release gate and the
projection share (GLOSSARY 单日汇总, ADR-0041 2026-10-13).

The target day's summary reads what is public by the run's cutoff, of periods through the
target day: the margin totals of the target, out at 9:05 the next session, are read on it.
A backfilled day reads what was public by its own end. One rule covers both, since a
backfilled day's cutoff is its own end: a claim is known when it is public by the cutoff,
and, past the day's end, only when its period ends by the day. A period still running on
the day (the month's LPR fixing) is known as it was by the day's end.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from pring_cycle.runs import RunRecord

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def day_end(day: date) -> datetime:
    """The last instant of an SSE session in Shanghai."""
    return datetime.combine(day, time.max, tzinfo=_SHANGHAI)


@dataclass(frozen=True)
class SummaryCutoff:
    """The day a summary is of, and the instant what it reads must be public by."""

    day: date
    public_as_of: datetime

    def __post_init__(self) -> None:
        if self.public_as_of.tzinfo is None:
            raise ValueError("summary_cutoff_must_be_timezone_aware")

    @classmethod
    def of(cls, cutoff: datetime | SummaryCutoff) -> SummaryCutoff:
        """``cutoff`` as a summary's: an instant alone is one of its own day, as before."""
        if isinstance(cutoff, SummaryCutoff):
            return cutoff
        return cls(cutoff.astimezone(_SHANGHAI).date(), cutoff)

    @classmethod
    def at_day_end(cls, day: date) -> SummaryCutoff:
        """A backfilled day's: what was public by its own end."""
        return cls(day, day_end(day))

    @classmethod
    def target(cls, run: RunRecord, decided_at: datetime) -> SummaryCutoff:
        """The run's target day as decided at ``decided_at``: its cutoff once frozen, the
        decision's own instant while the acquisition window is open."""
        if run.cutoff_mode == "acquisition_window" and not run.cutoffs_frozen:
            known = decided_at
        else:
            known = min(run.system_as_of, decided_at)
        return cls(date.fromisoformat(run.target_business_date), known)

    @property
    def day_end(self) -> datetime:
        return day_end(self.day)

    def on(self, day: date) -> SummaryCutoff:
        """The cutoff of a window ``day``: this one on its own day, the day's end before."""
        if day >= self.day:
            return self
        return SummaryCutoff(day, min(self.public_as_of, day_end(day)))

    def knows(self, period_end: date, public_at: datetime | None) -> bool:
        """Whether a claim of the period ending on ``period_end``, public at ``public_at``,
        is known to the summary."""
        if public_at is None or public_at > self.public_as_of:
            return False
        return period_end <= self.day or public_at <= self.day_end
