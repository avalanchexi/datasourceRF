from __future__ import annotations

from pring_cycle.search_discovery import (
    SearchHttpResponse,
    build_search_query,
    search_discovery_adapter,
)


def test_tavily_and_exa_contracts_only_return_sanitized_candidate_urls() -> None:
    calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def transport(
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> SearchHttpResponse:
        calls.append((endpoint, headers, payload))
        return SearchHttpResponse(
            200,
            {
                "results": [
                    {
                        "title": "untrusted result body must not persist",
                        "url": "https://unknown.example/release",
                        "content": "full external response sentinel",
                    }
                ]
            },
        )

    tavily = search_discovery_adapter(
        "tavily",
        "tavily-secret",
        "LPR 2026-08 official release",
        transport=transport,
    )("release-lpr")
    exa = search_discovery_adapter(
        "exa",
        "exa-secret",
        "LPR 2026-08 official release",
        transport=transport,
    )("release-lpr")

    assert tavily.status == exa.status == "candidate_source"
    assert tavily.evidence == exa.evidence == "https://unknown.example/release"
    assert tavily.classification == exa.classification == "unverified_candidate"
    assert calls[0][0] == "https://api.tavily.com/search"
    assert calls[0][1]["Authorization"] == "Bearer tavily-secret"
    assert calls[0][2]["include_raw_content"] is False
    assert calls[1][0] == "https://api.exa.ai/search"
    assert calls[1][1]["x-api-key"] == "exa-secret"
    assert "full external response sentinel" not in repr((tavily, exa))
    assert "secret" not in repr((tavily, exa))


def test_search_failures_are_classified_without_returning_response_bodies() -> None:
    def response(status: int) -> object:
        return search_discovery_adapter(
            "tavily",
            "secret",
            "query",
            transport=lambda _endpoint, _headers, _payload: SearchHttpResponse(
                status,
                {"detail": "provider-response-sentinel"},
            ),
        )("release")

    assert response(401).classification == "authentication_failed"  # type: ignore[union-attr]
    assert response(429).classification == "rate_limited"  # type: ignore[union-attr]
    assert response(500).classification == "transient_transport_error"  # type: ignore[union-attr]
    assert "provider-response-sentinel" not in repr(response(400))


def test_query_uses_frozen_metric_identity_and_joint_event_members() -> None:
    query = build_search_query(
        ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
        period="2026-08",
    )

    assert "CN_PMI_ACTIVITY" in query
    assert "CN_PMI_INVENTORY" in query
    assert "CN_PMI_PRICES" in query
    assert "2026-08" in query
