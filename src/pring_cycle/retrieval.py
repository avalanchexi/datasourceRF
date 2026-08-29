from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalRequest:
    release_event_id: str
    metric_ids: tuple[str, ...]
    priority: str
    released: bool = True
    negative_cache_active: bool = False
    manual_deep_search: bool = False


@dataclass
class RetrievalBudget:
    run_tavily_remaining: int = 8
    run_exa_remaining: int = 4
    run_ai_remaining: int = 1
    daily_tavily_remaining: int = 16
    daily_exa_remaining: int = 8
    daily_ai_remaining: int = 2


@dataclass(frozen=True)
class RetrievalAttempt:
    channel: str
    outcome: str
    remaining_run_budget: int | None


@dataclass(frozen=True)
class RetrievalAdapterResponse:
    status: str
    evidence: str | None = None
    classification: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    channel: str | None
    evidence: str | None
    attempts: tuple[RetrievalAttempt, ...]
    next_action: str


def run_retrieval_cascade(
    request: RetrievalRequest,
    adapters: Mapping[
        str,
        Callable[[str], str | RetrievalAdapterResponse | None],
    ],
    budget: RetrievalBudget,
) -> RetrievalResult:
    if not request.released or request.negative_cache_active:
        return RetrievalResult("not_attempted", None, None, (), "wait_for_release_or_cache_expiry")
    if request.manual_deep_search and len(request.metric_ids) != 1:
        raise ValueError("manual_deep_search_requires_one_explicit_metric")
    channels = ["local", "tushare", "official", "tavily", "exa"]
    if request.priority != "P2":
        channels.append("ai_websearch")
    attempts: list[RetrievalAttempt] = []
    for channel in channels:
        remaining = None if request.manual_deep_search else _consume_budget(channel, budget)
        if remaining is False:
            attempts.append(RetrievalAttempt(channel, "budget_exhausted", 0))
            continue
        adapter = adapters.get(channel)
        responses = _adapter_attempts(adapter, request.release_event_id)
        for response in responses:
            attempts.append(
                RetrievalAttempt(
                    channel,
                    response.status,
                    remaining if isinstance(remaining, int) else None,
                )
            )
        verified = next(
            (
                response.evidence
                for response in responses
                if response.status == "verified" and response.evidence is not None
            ),
            None,
        )
        if verified is not None:
            return RetrievalResult(
                "verified", channel, verified, tuple(attempts), "ingest_verified_evidence"
            )
    return RetrievalResult("unresolved", None, None, tuple(attempts), "manual_review")


def _adapter_attempts(
    adapter: Callable[[str], str | RetrievalAdapterResponse | None] | None,
    release_event_id: str,
) -> tuple[RetrievalAdapterResponse, ...]:
    if adapter is None:
        return (RetrievalAdapterResponse("not_found"),)
    responses = []
    for _attempt in range(3):
        value = adapter(release_event_id)
        if isinstance(value, str):
            response = RetrievalAdapterResponse("verified", evidence=value)
        elif value is None:
            response = RetrievalAdapterResponse("not_found")
        else:
            response = value
        responses.append(response)
        if response.classification != "transient_transport_error":
            break
    return tuple(responses)


def _consume_budget(channel: str, budget: RetrievalBudget) -> int | bool | None:
    fields = {
        "tavily": ("run_tavily_remaining", "daily_tavily_remaining"),
        "exa": ("run_exa_remaining", "daily_exa_remaining"),
        "ai_websearch": ("run_ai_remaining", "daily_ai_remaining"),
    }
    field_names = fields.get(channel)
    if field_names is None:
        return None
    run_field, daily_field = field_names
    run_remaining = int(getattr(budget, run_field))
    daily_remaining = int(getattr(budget, daily_field))
    if run_remaining <= 0 or daily_remaining <= 0:
        return False
    setattr(budget, run_field, run_remaining - 1)
    setattr(budget, daily_field, daily_remaining - 1)
    return run_remaining - 1
