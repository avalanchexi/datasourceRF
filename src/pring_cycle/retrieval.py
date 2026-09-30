from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic


def matches_retrieval_period(period_end: str, period: str) -> bool:
    prefix = f"{period[:4]}-{int(period[-1]) * 3:02d}" if "-Q" in period else period
    return period_end.startswith(prefix)


def preceding_periods(period: str, count: int) -> tuple[str, ...]:
    """The ``count`` monthly (or quarterly) periods ending with ``period``, oldest first."""
    if count == 1:
        return (period,)
    if "-Q" in period:
        year, quarter = period.split("-Q")
        last = int(year) * 4 + int(quarter) - 1
        return tuple(
            f"{ordinal // 4:04d}-Q{ordinal % 4 + 1}"
            for ordinal in range(last - count + 1, last + 1)
        )
    year, month = period[:7].split("-")
    last = int(year) * 12 + int(month) - 1
    return tuple(
        f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"
        for ordinal in range(last - count + 1, last + 1)
    )


@dataclass(frozen=True)
class RetrievalRequest:
    release_event_id: str
    metric_ids: tuple[str, ...]
    priority: str
    released: bool = True
    negative_cache_active: bool = False
    manual_deep_search: bool = False
    persistent_accounting: bool = False
    # False when no web page can carry the gap's value (not a registered retrieval family):
    # TuShare is still retried, but no search channel is called.
    searchable: bool = True


SEARCH_CHANNELS = frozenset({"tavily", "exa", "ai_websearch"})
NO_SEARCHABLE_SOURCE = "no_searchable_source"
# Paid search calls allowed per run (ticket 20). There is no daily cap; AI WebSearch has no
# count limit and is held to one call per gap per run by the ledger.
RUN_SEARCH_LIMITS: dict[str, int | None] = {"tavily": 16, "exa": 8, "ai_websearch": None}


@dataclass
class RetrievalBudget:
    run_tavily_remaining: int = 16
    run_exa_remaining: int = 8
    run_ai_remaining: int | None = None


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
    physical_request_id: str | None = None


@dataclass(frozen=True)
class RetrievalAdapterResponse:
    status: str
    evidence: str | None = None
    classification: str | None = None
    physical_request_id: str | None = None
    cache_hit: bool = False
    candidate_sources: tuple[str, ...] = ()
    candidate_summaries: tuple[str, ...] = ()


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
    remaining_run: int | None


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
    # TuShare news sits between TuShare's data interfaces and the official pages: once
    # TuShare has a value, no official or media page is needed (ADR-0026). Exa stands in
    # for Tavily only once Tavily's monthly quota is spent (or it has no key).
    channels = ["local", "tushare", "tushare_news", "official", "tavily", "exa", "ai_websearch"]
    attempts: list[RetrievalAttempt] = []
    candidates: list[str] = []
    for channel in channels:
        adapter = adapters.get(channel)
        if channel in SEARCH_CHANNELS and not request.searchable:
            attempts.append(
                RetrievalAttempt(
                    channel, "not_attempted", None, classification=NO_SEARCHABLE_SOURCE
                )
            )
            continue
        if (
            channel == "exa"
            and adapter is not None
            and "tavily" in adapters
            and not any(
                item.channel == "tavily" and item.classification == "quota_exhausted"
                for item in attempts
            )
        ):
            attempts.append(
                RetrievalAttempt(
                    channel,
                    "not_attempted",
                    None,
                    classification="tavily_quota_available",
                    manual_budget_exemption=request.manual_deep_search,
                )
            )
            continue
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
            None
            if request.manual_deep_search or request.persistent_accounting
            else _consume_budget(channel, budget)
        )
        if isinstance(remaining, _BudgetDecision) and not remaining.allowed:
            attempts.append(RetrievalAttempt(channel, "budget_exhausted", remaining.remaining_run))
            continue
        responses = _adapter_attempts(
            adapter,
            request.release_event_id,
            retry_limit=1
            if request.persistent_accounting and channel not in {"official", "tushare"}
            else 3,
        )
        for response_index, adapter_attempt in enumerate(responses):
            response = adapter_attempt.response
            if response.status == "candidate_source" and response.evidence is not None:
                candidates.append(response.evidence)
            attempts.append(
                RetrievalAttempt(
                    channel,
                    response.status,
                    remaining.remaining_run if isinstance(remaining, _BudgetDecision) else None,
                    None,
                    adapter_attempt.latency_ms,
                    response.classification,
                    response.evidence if response.status == "candidate_source" else None,
                    response.physical_request_id is not None
                    and not response.cache_hit
                    and channel in {"tavily", "exa", "ai_websearch"}
                    if request.persistent_accounting
                    else isinstance(remaining, _BudgetDecision) and response_index == 0,
                    response.cache_hit,
                    request.manual_deep_search,
                    response.physical_request_id,
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
    *,
    retry_limit: int = 3,
) -> tuple[_AdapterAttempt, ...]:
    if adapter is None:
        return (_AdapterAttempt(RetrievalAdapterResponse("not_configured"), 0),)
    responses: list[_AdapterAttempt] = []
    for _attempt in range(retry_limit):
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
    field_name = {
        "tavily": "run_tavily_remaining",
        "exa": "run_exa_remaining",
        "ai_websearch": "run_ai_remaining",
    }.get(channel)
    if field_name is None:
        return None
    remaining: int | None = getattr(budget, field_name)
    if remaining is None:
        return _BudgetDecision(True, None)
    if remaining <= 0:
        return _BudgetDecision(False, 0)
    setattr(budget, field_name, remaining - 1)
    return _BudgetDecision(True, remaining - 1)
