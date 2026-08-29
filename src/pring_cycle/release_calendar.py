from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pring_cycle.evidence import EvidenceRepository, ReleaseEventView


@dataclass(frozen=True)
class ReleaseExpectation:
    metric_id: str
    period: str
    window_start: datetime
    window_end: datetime
    grace_until: datetime
    timezone: str
    rule_version: str


@dataclass(frozen=True)
class ReleasedObservation:
    observation_id: str
    period: str
    public_available_at: datetime
    available_at: datetime


@dataclass(frozen=True)
class ReleaseState:
    metric_id: str
    status: str
    display_period: str | None
    observation_id: str | None
    should_retrieve: bool
    blocks_formal_stage: bool
    expected_window_start: datetime | None
    expected_window_end: datetime | None
    next_check_at: datetime | None


@dataclass(frozen=True)
class ReleaseCalendarEvent:
    release_event_family: str
    metric_id: str
    period: str
    timezone: str
    status: str
    carried_period: str | None
    expected_window_start: datetime
    expected_window_end: datetime
    grace_until: datetime
    release_at: datetime | None
    public_available_at: datetime | None
    available_at: datetime | None
    latest_fetched_at: datetime | None
    next_check_at: datetime | None
    observation_count: int
    source_reference: str | None


def assess_release_state(
    expectation: ReleaseExpectation | None,
    *,
    as_of: datetime,
    previous: ReleasedObservation | None = None,
    retrieval_outcome: str | None = None,
    observation_conflicted: bool = False,
    value_state: str | None = None,
    metric_id: str | None = None,
    priority: str = "P1",
) -> ReleaseState:
    if expectation is None:
        return ReleaseState(
            metric_id=metric_id or "unknown",
            status="unknown_release_configuration",
            display_period=previous.period if previous else None,
            observation_id=previous.observation_id if previous else None,
            should_retrieve=False,
            blocks_formal_stage=priority == "P0",
            expected_window_start=None,
            expected_window_end=None,
            next_check_at=None,
        )
    current_observation = (
        previous is not None
        and previous.period == expectation.period
        and previous.public_available_at <= as_of
        and previous.available_at <= as_of
    )
    if current_observation:
        status = "current"
    elif value_state in {"not_applicable", "not_disclosed"}:
        status = value_state
    elif observation_conflicted:
        status = "conflicted"
    elif retrieval_outcome in {"source_failed", "permission_denied", "rate_limited"}:
        status = retrieval_outcome
    elif as_of < expectation.window_start or as_of <= expectation.grace_until:
        status = "awaiting_release"
    else:
        status = "stale"
    should_retrieve = expectation.window_start <= as_of and status not in {
        "current",
        "not_applicable",
        "not_disclosed",
        "conflicted",
    }
    if as_of < expectation.window_start:
        next_check_at = expectation.window_start
    elif status in {"current", "not_applicable", "not_disclosed", "conflicted"}:
        next_check_at = None
    elif as_of < expectation.window_end:
        next_check_at = expectation.window_end
    elif as_of < expectation.grace_until:
        next_check_at = expectation.grace_until
    else:
        next_check_at = None
    return ReleaseState(
        metric_id=expectation.metric_id,
        status=status,
        display_period=previous.period if previous else expectation.period,
        observation_id=previous.observation_id if previous else None,
        should_retrieve=should_retrieve,
        blocks_formal_stage=priority == "P0" and status not in {"current"},
        expected_window_start=expectation.window_start,
        expected_window_end=expectation.window_end,
        next_check_at=next_check_at,
    )


def lpr_release_expectation(
    period: str,
    *,
    holidays: tuple[str, ...] = (),
) -> ReleaseExpectation:
    try:
        year_text, month_text = period.split("-", maxsplit=1)
        year, month = int(year_text), int(month_text)
        release_day = date(year, month, 20)
    except (TypeError, ValueError) as error:
        raise ValueError("lpr_period_must_be_yyyy_mm") from error
    if period != f"{year:04d}-{month:02d}":
        raise ValueError("lpr_period_must_be_yyyy_mm")
    frozen_holidays = _holiday_dates(holidays)
    while release_day.weekday() >= 5 or release_day in frozen_holidays:
        release_day += timedelta(days=1)
    timezone = ZoneInfo("Asia/Shanghai")
    window_start = datetime.combine(release_day, time(9), timezone)
    return ReleaseExpectation(
        metric_id="CN_LPR_1Y_5Y",
        period=period,
        window_start=window_start,
        window_end=window_start + timedelta(minutes=5),
        grace_until=window_start + timedelta(hours=3),
        timezone="Asia/Shanghai",
        rule_version="lpr-release-rule-v0001",
    )


def lpr_release_calendar(
    repository: EvidenceRepository,
    *,
    period: str,
    as_of: datetime,
    holidays: tuple[str, ...] = (),
) -> tuple[ReleaseCalendarEvent, ...]:
    if as_of.tzinfo is None:
        raise ValueError("release_calendar_as_of_must_be_timezone_aware")
    expectation = lpr_release_expectation(period, holidays=holidays)
    visible = tuple(
        event
        for event in repository.release_events(metric_id=expectation.metric_id)
        if event.available_at <= as_of
    )
    current_event = next((item for item in reversed(visible) if item.period == period), None)
    previous_event = current_event or (visible[-1] if visible else None)
    released = _released_observation(previous_event)
    attempt = repository.latest_retrieval_attempt(
        expectation.metric_id,
        period=period,
        as_of=as_of,
    )
    state = assess_release_state(
        expectation,
        as_of=as_of,
        previous=released,
        retrieval_outcome=attempt.outcome if attempt is not None else None,
        priority="P1",
    )
    return (
        ReleaseCalendarEvent(
            release_event_family="chinamoney_lpr",
            metric_id=expectation.metric_id,
            period=period,
            timezone=expectation.timezone,
            status=state.status,
            carried_period=(
                previous_event.period
                if previous_event is not None and previous_event.period != period
                else None
            ),
            expected_window_start=expectation.window_start,
            expected_window_end=expectation.window_end,
            grace_until=expectation.grace_until,
            release_at=current_event.release_at if current_event is not None else None,
            public_available_at=(
                current_event.public_available_at if current_event is not None else None
            ),
            available_at=current_event.available_at if current_event is not None else None,
            latest_fetched_at=(
                current_event.latest_fetched_at
                if current_event is not None
                else attempt.fetched_at
                if attempt is not None
                else previous_event.latest_fetched_at
                if previous_event is not None
                else None
            ),
            next_check_at=state.next_check_at,
            observation_count=current_event.observation_count if current_event is not None else 0,
            source_reference=(
                current_event.source_reference if current_event is not None else None
            ),
        ),
    )


def current_lpr_period(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("release_calendar_as_of_must_be_timezone_aware")
    local = now.astimezone(ZoneInfo("Asia/Shanghai"))
    return f"{local.year:04d}-{local.month:02d}"


def month_bounds(period: str) -> tuple[str, str]:
    expectation = lpr_release_expectation(period)
    year, month = (int(part) for part in expectation.period.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def _released_observation(event: ReleaseEventView | None) -> ReleasedObservation | None:
    if event is None or event.public_available_at is None:
        return None
    return ReleasedObservation(
        observation_id=event.release_event_id,
        period=event.period,
        public_available_at=event.public_available_at,
        available_at=event.available_at,
    )


def _holiday_dates(values: tuple[str, ...]) -> frozenset[date]:
    try:
        parsed = frozenset(date.fromisoformat(value) for value in values)
    except ValueError as error:
        raise ValueError("lpr_holidays_must_be_iso_dates") from error
    return parsed
