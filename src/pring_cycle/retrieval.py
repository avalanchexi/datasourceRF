from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic


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
    remaining_daily_budget: int | None = None
    latency_ms: int = 0
    classification: str | None = None
    candidate_source: str | None = None
    budget_charged: bool = False
    cache_hit: bool = False
    manual_budget_exemption: bool = False


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
    candidate_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class _AdapterAttempt:
    response: RetrievalAdapterResponse
    latency_ms: int


@dataclass(frozen=True)
class _BudgetDecision:
    allowed: bool
    remaining_run: int
    remaining_daily: int


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
    candidates: list[str] = []
    for channel in channels:
        adapter = adapters.get(channel)
        if adapter is None:
            attempts.append(
                RetrievalAttempt(
                    channel,
                    "not_configured",
                    None,
                    manual_budget_exemption=request.manual_deep_search,
                )
            )
            continue
        remaining = (
            None if request.manual_deep_search else _consume_budget(channel, budget)
        )
        if isinstance(remaining, _BudgetDecision) and not remaining.allowed:
            attempts.append(
                RetrievalAttempt(
                    channel,
                    "budget_exhausted",
                    remaining.remaining_run,
                    remaining.remaining_daily,
                )
            )
            continue
        responses = _adapter_attempts(adapter, request.release_event_id)
        for response_index, adapter_attempt in enumerate(responses):
            response = adapter_attempt.response
            if response.status == "candidate_source" and response.evidence is not None:
                candidates.append(response.evidence)
            attempts.append(
                RetrievalAttempt(
                    channel,
                    response.status,
                    remaining.remaining_run
                    if isinstance(remaining, _BudgetDecision)
                    else None,
                    remaining.remaining_daily
                    if isinstance(remaining, _BudgetDecision)
                    else None,
                    adapter_attempt.latency_ms,
                    response.classification,
                    response.evidence if response.status == "candidate_source" else None,
                    isinstance(remaining, _BudgetDecision) and response_index == 0,
                    False,
                    request.manual_deep_search,
                )
            )
        verified = next(
            (
                item.response.evidence
                for item in responses
                if item.response.status == "verified" and item.response.evidence is not None
            ),
            None,
        )
        if verified is not None:
            return RetrievalResult(
                "verified",
                channel,
                verified,
                tuple(attempts),
                "ingest_verified_evidence",
                tuple(dict.fromkeys(candidates)),
            )
    return RetrievalResult(
        "unresolved",
        None,
        None,
        tuple(attempts),
        "manual_review",
        tuple(dict.fromkeys(candidates)),
    )


def _adapter_attempts(
    adapter: Callable[[str], str | RetrievalAdapterResponse | None] | None,
    release_event_id: str,
) -> tuple[_AdapterAttempt, ...]:
    if adapter is None:
        return (_AdapterAttempt(RetrievalAdapterResponse("not_configured"), 0),)
    responses: list[_AdapterAttempt] = []
    for _attempt in range(3):
        started = monotonic()
        try:
            value = adapter(release_event_id)
            if isinstance(value, str):
                response = RetrievalAdapterResponse("verified", evidence=value)
            elif value is None:
                response = RetrievalAdapterResponse("not_found")
            else:
                response = value
        except (ConnectionError, TimeoutError, OSError):
            response = RetrievalAdapterResponse(
                "failed",
                classification="transient_transport_error",
            )
        except ValueError:
            response = RetrievalAdapterResponse(
                "failed",
                classification="semantic_validation_failed",
            )
        latency_ms = max(0, int((monotonic() - started) * 1000))
        responses.append(_AdapterAttempt(response, latency_ms))
        if response.classification != "transient_transport_error":
            break
    return tuple(responses)


def _consume_budget(
    channel: str,
    budget: RetrievalBudget,
) -> _BudgetDecision | None:
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
        return _BudgetDecision(False, max(0, run_remaining), max(0, daily_remaining))
    setattr(budget, run_field, run_remaining - 1)
    setattr(budget, daily_field, daily_remaining - 1)
    return _BudgetDecision(True, run_remaining - 1, daily_remaining - 1)
