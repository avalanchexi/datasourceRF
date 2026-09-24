from __future__ import annotations

from collections.abc import Callable

from pring_cycle.retrieval import (
    RetrievalAdapterResponse,
    RetrievalBudget,
    RetrievalRequest,
    RetrievalResult,
    run_retrieval_cascade,
)


def adapters(calls: list[str], hit_at: str | None) -> dict[str, Callable[[str], str | None]]:
    def adapter(channel: str) -> Callable[[str], str | None]:
        def retrieve(_release_event_id: str) -> str | None:
            calls.append(channel)
            return "verified-evidence" if channel == hit_at else None

        return retrieve

    return {
        channel: adapter(channel)
        for channel in (
            "local",
            "tushare",
            "tushare_news",
            "official",
            "tavily",
            "exa",
            "ai_websearch",
        )
    }


def test_retrieval_is_serial_cache_first_and_stops_after_a_hit() -> None:
    calls: list[str] = []

    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"),
        adapters(calls, "official"),
        RetrievalBudget(),
    )

    assert result.status == "verified"
    assert calls == ["local", "tushare", "tushare_news", "official"]
    assert result.channel == "official"


def test_p2_reaches_ai_websearch_and_exa_waits_for_tavily_quota() -> None:
    calls: list[str] = []

    result = run_retrieval_cascade(
        RetrievalRequest("release-vix", ("CBOE_VIX_INDEX",), "P2"),
        adapters(calls, None),
        RetrievalBudget(),
    )

    assert result.status == "unresolved"
    assert calls == ["local", "tushare", "tushare_news", "official", "tavily", "ai_websearch"]
    exa = next(item for item in result.attempts if item.channel == "exa")
    assert (exa.outcome, exa.classification) == ("not_attempted", "tavily_quota_available")


def test_exa_stands_in_once_tavily_reports_its_quota_spent() -> None:
    calls: list[str] = []
    channels = adapters(calls, "exa")
    channels["tavily"] = lambda _event: (
        calls.append("tavily")
        or RetrievalAdapterResponse("failed", classification="quota_exhausted")
    )

    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"), channels, RetrievalBudget()
    )

    assert calls == ["local", "tushare", "tushare_news", "official", "tavily", "exa"]
    assert result.channel == "exa"


def test_not_yet_released_and_negative_cache_make_no_calls() -> None:
    for request in (
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1", released=False),
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1", negative_cache_active=True),
    ):
        calls: list[str] = []
        result = run_retrieval_cascade(request, adapters(calls, None), RetrievalBudget())

        assert result == RetrievalResult(
            status="not_attempted",
            channel=None,
            evidence=None,
            attempts=(),
            next_action="wait_for_release_or_cache_expiry",
        )
        assert calls == []


def test_event_metrics_share_one_channel_call_and_budget_is_hard() -> None:
    calls: list[str] = []
    budget = RetrievalBudget(run_tavily_remaining=0)

    result = run_retrieval_cascade(
        RetrievalRequest(
            "release-pmi",
            ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
            "P1",
        ),
        adapters(calls, "ai_websearch"),
        budget,
    )

    assert calls == ["local", "tushare", "tushare_news", "official", "ai_websearch"]
    assert result.status == "verified"
    tavily = next(item for item in result.attempts if item.channel == "tavily")
    assert (tavily.outcome, tavily.remaining_run_budget) == ("budget_exhausted", 0)


def test_only_transient_transport_errors_retry_and_unknown_sites_stay_candidates() -> None:
    calls = 0

    def transient_then_candidate(_event_id: str) -> RetrievalAdapterResponse:
        nonlocal calls
        calls += 1
        if calls < 3:
            return RetrievalAdapterResponse(
                "failed",
                classification="transient_transport_error",
            )
        return RetrievalAdapterResponse("candidate_source", evidence="unverified-page")

    result = run_retrieval_cascade(
        RetrievalRequest("release-unknown", ("CN_CORE_CPI",), "P1"),
        {"tavily": transient_then_candidate},
        RetrievalBudget(),
    )

    assert calls == 3
    assert result.status == "unresolved"
    assert result.evidence is None
    assert [item.outcome for item in result.attempts if item.channel == "tavily"] == [
        "failed",
        "failed",
        "candidate_source",
    ]


def test_authentication_failure_does_not_retry() -> None:
    calls = 0

    def denied(_event_id: str) -> RetrievalAdapterResponse:
        nonlocal calls
        calls += 1
        return RetrievalAdapterResponse("failed", classification="authentication_failed")

    run_retrieval_cascade(
        RetrievalRequest("release-denied", ("CN_CORE_CPI",), "P1"),
        {"official": denied},
        RetrievalBudget(),
    )

    assert calls == 1


def test_unconfigured_paid_channels_do_not_consume_budget() -> None:
    budget = RetrievalBudget()

    result = run_retrieval_cascade(
        RetrievalRequest("release-missing", ("CN_CORE_CPI",), "P1"),
        {},
        budget,
    )

    assert result.status == "unresolved"
    assert budget.run_tavily_remaining == 16
    assert budget.run_exa_remaining == 8
    assert budget.run_ai_remaining is None
    assert [attempt.outcome for attempt in result.attempts] == ["not_configured"] * 7


def test_attempts_capture_latency_classification_and_run_budget() -> None:
    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"),
        {
            "tavily": lambda _event: RetrievalAdapterResponse(
                "failed",
                classification="rate_limited",
            )
        },
        RetrievalBudget(),
    )

    attempt = next(item for item in result.attempts if item.channel == "tavily")
    assert attempt.classification == "rate_limited"
    assert attempt.latency_ms >= 0
    assert attempt.remaining_run_budget == 15
    assert attempt.remaining_daily_budget is None


def test_adapter_semantic_validation_failure_is_sanitized_and_not_retried() -> None:
    calls = 0

    def invalid(_event: str) -> object:
        nonlocal calls
        calls += 1
        raise ValueError("external-response-body-must-not-escape")

    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"),
        {"official": invalid},  # type: ignore[dict-item]
        RetrievalBudget(),
    )

    assert calls == 1
    attempt = next(item for item in result.attempts if item.channel == "official")
    assert attempt.classification == "semantic_validation_failed"
    assert "external-response-body" not in repr(result)


def test_a_value_from_tushare_news_stops_before_official_and_media_pages() -> None:
    calls: list[str] = []

    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"),
        adapters(calls, "tushare_news"),
        RetrievalBudget(),
    )

    assert (result.status, result.channel) == ("verified", "tushare_news")
    assert calls == ["local", "tushare", "tushare_news"]
