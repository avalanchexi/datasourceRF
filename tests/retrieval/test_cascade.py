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
        for channel in ("local", "tushare", "official", "tavily", "exa", "ai_websearch")
    }


def test_retrieval_is_serial_cache_first_and_stops_after_a_hit() -> None:
    calls: list[str] = []

    result = run_retrieval_cascade(
        RetrievalRequest("release-cpi", ("CN_CPI_HEADLINE",), "P1"),
        adapters(calls, "official"),
        RetrievalBudget(),
    )

    assert result.status == "verified"
    assert calls == ["local", "tushare", "official"]
    assert result.channel == "official"


def test_p2_stops_at_exa_and_never_uses_ai_websearch() -> None:
    calls: list[str] = []

    result = run_retrieval_cascade(
        RetrievalRequest("release-vix", ("CBOE_VIX_INDEX",), "P2"),
        adapters(calls, None),
        RetrievalBudget(),
    )

    assert result.status == "unresolved"
    assert calls == ["local", "tushare", "official", "tavily", "exa"]


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
        adapters(calls, "exa"),
        budget,
    )

    assert calls == ["local", "tushare", "official", "exa"]
    assert result.status == "verified"
    assert result.attempts[-1].remaining_run_budget == 3


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
