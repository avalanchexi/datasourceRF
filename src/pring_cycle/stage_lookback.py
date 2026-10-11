"""The last confirmed stage before the window, looked back for by year (ADR-0040).

A run whose target has no formal stage, and whose stage history holds none, reads the three
cores further back than the window: a year at a time, each core one range request, until the
most recent day with a formal stage before the window turns up, for five years at most. Each
year extends the closes the run holds, and the cores' states are read over the whole stretch
by the same trend rules and stage mapping as the formal track. Year N searches the days from
N years before the window's first day; its request reaches as many sessions before that day
as a state on it needs, by the SSE calendar, and stops before the closes all three cores
already hold (or the year after's), and no stage older than five years is ever returned.

The closes read back are no claims: they are computed with and dropped, so no model input,
evidence snapshot or macro confirmation ever reads them, and the run's own calls keep their
responses as any of its calls do. What was found, how far it searched and what it cost are
published with the stage history, and a lookback that fails leaves the stage empty and says
why without failing the run.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from http.client import HTTPException

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.core_history import CoreHistoryAdapter
from pring_cycle.domain import FormalStage
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend_history
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import acquire_sse_calendar
from pring_cycle.tushare_quota import TushareCallNotAttempted

LOOKBACK_YEARS = 5
FOUND = "found"
NOT_FOUND = "not_found"
FAILED = "failed"


@dataclass(frozen=True)
class HeldCore:
    """A core's closes as the run's gate passed them, oldest first (ISO day, value)."""

    metric_id: str
    closes: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class StageLookback:
    """A lookback's outcome; ``stage_date`` is the last day before the window it held.

    ``searched_from`` to ``searched_through`` are the days whose stage could be read, and
    the requests count the calls sent, a failed one included.
    """

    status: str
    stage: FormalStage | None = None
    stage_date: str | None = None
    searched_from: str | None = None
    searched_through: str | None = None
    years: int = 0
    core_requests: int = 0
    calendar_requests: int = 0
    failure: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "calendar_requests": self.calendar_requests,
            "core_requests": self.core_requests,
            "failure": self.failure,
            "searched_from": self.searched_from,
            "searched_through": self.searched_through,
            "source": "lookback",
            "stage": self.stage.value if self.stage is not None else None,
            "stage_date": self.stage_date,
            "status": self.status,
            "years": self.years,
        }


def look_back_for_stage(
    paths: RuntimePaths,
    adapter: CoreHistoryAdapter,
    held: Mapping[str, HeldCore],
    *,
    window_start: date,
    rules: TrendRules,
    years: int = LOOKBACK_YEARS,
) -> StageLookback:
    """The most recent formal stage before ``window_start``, held keyed by bond, stock and
    commodity; their requests go one at a time."""
    if set(held) != {"bond", "stock", "commodity"} or not all(
        core.closes for core in held.values()
    ):
        return StageLookback(FAILED, failure="core_history_unavailable")
    # Each core reaches back to its own first close: a year's request ends before the latest
    # of them, and a core held from earlier keeps its own closes where a year overlaps them.
    reach = max(date.fromisoformat(core.closes[0][0]) for core in held.values())
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    fetched: dict[str, dict[str, float]] = {asset: {} for asset in held}
    core_requests = calendar_requests = 0
    searched: tuple[str | None, str | None] = (None, None)
    for year in range(1, years + 1):
        floor = _years_before(window_start, year)
        sending = "calendar"
        try:
            calendar_requests += 1
            calendar = acquire_sse_calendar(
                paths,
                adapter,
                floor - timedelta(days=rules.history_required * 7 // 4),
                reach - timedelta(days=1),
            )
            # A state on the floor needs the closes of the sessions before it.
            first = bisect_left(calendar, floor) - (rules.history_required - 1)
            if first < 0:
                raise ValueError("core_lookback_calendar_short")
            sessions = calendar[first:]
            sending = "core"
            for asset, core in held.items():
                core_requests += 1
                acquired = adapter.acquire_core_bars(
                    acquisitions,
                    core.metric_id,
                    start=sessions[0],
                    end=sessions[-1],
                    expected_business_dates=sessions,
                )
                fetched[asset].update(
                    (bar.business_date.isoformat(), bar.close) for bar in acquired.value
                )
            reach = sessions[0]
        except (LookupError, TypeError, ValueError, OSError, HTTPException) as error:
            # A response cut short is no OSError (residual 02); any of them fails the lookback.
            if isinstance(error, TushareCallNotAttempted):
                # Held back for TuShare's day (ticket 31): never sent, so no request.
                if sending == "core":
                    core_requests -= 1
                else:
                    calendar_requests -= 1
            return StageLookback(
                FAILED,
                searched_from=searched[0],
                searched_through=searched[1],
                years=year,
                core_requests=core_requests,
                calendar_requests=calendar_requests,
                failure=_failure(error),
            )
        found, searched = _last_stage_before(fetched, held, (floor, window_start), rules)
        if found is not None:
            return StageLookback(
                FOUND,
                stage=found[1],
                stage_date=found[0],
                searched_from=searched[0],
                searched_through=searched[1],
                years=year,
                core_requests=core_requests,
                calendar_requests=calendar_requests,
            )
    return StageLookback(
        NOT_FOUND,
        searched_from=searched[0],
        searched_through=searched[1],
        years=years,
        core_requests=core_requests,
        calendar_requests=calendar_requests,
    )


def _last_stage_before(
    fetched: Mapping[str, Mapping[str, float]],
    held: Mapping[str, HeldCore],
    span: tuple[date, date],
    rules: TrendRules,
) -> tuple[tuple[str, FormalStage] | None, tuple[str | None, str | None]]:
    """The latest day of ``span`` (from its floor, up to the window) with a formal stage, and
    the days that were read."""
    states = {}
    for asset, core in held.items():
        closes = {**fetched[asset], **dict(core.closes)}
        history = evaluate_trend_history(
            [PricePoint(date.fromisoformat(day), value) for day, value in sorted(closes.items())],
            rules,
        )
        states[asset] = {
            point.business_date: point.stable_state
            for point in history[rules.history_required - 1 :]
            if span[0] <= point.business_date < span[1]
        }
    days = sorted(set(states["bond"]) & set(states["stock"]) & set(states["commodity"]))
    searched = (days[0].isoformat(), days[-1].isoformat()) if days else (None, None)
    for day in reversed(days):
        stage = derive_formal_stage(
            bond=states["bond"][day],
            stock=states["stock"][day],
            commodity=states["commodity"][day],
            last_confirmed_stage=None,
        ).current_stage
        if stage is not None:
            return (day.isoformat(), stage), searched
    return None, searched


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        # 29 February, in a year without one.
        return day.replace(year=day.year - years, day=28)


def _failure(error: Exception) -> str:
    detail = str(error)
    return f"{type(error).__name__}:{detail}" if detail else type(error).__name__
