from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
    if value_state in {"not_applicable", "not_disclosed"}:
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
        "not_applicable",
        "not_disclosed",
        "conflicted",
    }
    return ReleaseState(
        metric_id=expectation.metric_id,
        status=status,
        display_period=previous.period if previous else expectation.period,
        observation_id=previous.observation_id if previous else None,
        should_retrieve=should_retrieve,
        blocks_formal_stage=priority == "P0" and status not in {"current"},
        expected_window_start=expectation.window_start,
        expected_window_end=expectation.window_end,
        next_check_at=(expectation.window_start if as_of < expectation.window_start else None),
    )
