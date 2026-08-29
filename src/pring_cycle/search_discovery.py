from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pring_cycle.catalog import metric_definition
from pring_cycle.retrieval import RetrievalAdapterResponse

MAX_SEARCH_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class SearchHttpResponse:
    status: int
    document: object


SearchTransport = Callable[
    [str, dict[str, str], dict[str, object]],
    SearchHttpResponse,
]


def build_search_query(metric_ids: tuple[str, ...], *, period: str) -> str:
    if not metric_ids:
        raise ValueError("search_metric_ids_required")
    identities = []
    for metric_id in metric_ids:
        definition = metric_definition(metric_id)
        identities.append(
            " ".join((definition.metric_id, definition.name_cn, *definition.source_codes))
        )
    query = f"{' ; '.join(identities)} {period} 官方 发布"
    if len(query) > 800:
        raise ValueError("search_query_too_long")
    return query


def search_discovery_adapter(
    provider: str,
    api_key: str,
    query: str,
    *,
    transport: SearchTransport | None = None,
) -> Callable[[str], RetrievalAdapterResponse]:
    if not api_key:
        raise ValueError("search_api_key_required")
    if not query or len(query) > 800:
        raise ValueError("search_query_invalid")
    endpoint, headers, payload = _request_contract(provider, api_key, query)
    request = transport or _post_json

    def retrieve(_release_event_id: str) -> RetrievalAdapterResponse:
        response = request(endpoint, headers, payload)
        failure = _failure_classification(response.status)
        if failure is not None:
            return RetrievalAdapterResponse("failed", classification=failure)
        candidate = _first_candidate_url(response.document)
        if candidate is None:
            return RetrievalAdapterResponse("not_found")
        return RetrievalAdapterResponse(
            "candidate_source",
            evidence=candidate,
            classification="unverified_candidate",
        )

    return retrieve


def _request_contract(
    provider: str,
    api_key: str,
    query: str,
) -> tuple[str, dict[str, str], dict[str, object]]:
    if provider == "tavily":
        return (
            "https://api.tavily.com/search",
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            {
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
        )
    if provider == "exa":
        return (
            "https://api.exa.ai/search",
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            {"query": query, "type": "auto", "numResults": 5},
        )
    raise ValueError("unsupported_search_provider")


def _post_json(
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, object],
) -> SearchHttpResponse:
    if endpoint not in {"https://api.tavily.com/search", "https://api.exa.ai/search"}:
        raise ValueError("search_endpoint_not_allowed")
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed endpoint allowlist
            content = response.read(MAX_SEARCH_RESPONSE_BYTES + 1)
            status = int(response.status)
    except HTTPError as error:
        return SearchHttpResponse(int(error.code), {})
    if len(content) > MAX_SEARCH_RESPONSE_BYTES:
        raise ValueError("search_response_too_large")
    try:
        document: object = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("search_response_invalid_json") from error
    return SearchHttpResponse(status, document)


def _failure_classification(status: int) -> str | None:
    if status == 200:
        return None
    if status in {401, 403}:
        return "authentication_failed"
    if status == 402:
        return "quota_exhausted"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "transient_transport_error"
    return "semantic_validation_failed"


def _first_candidate_url(document: object) -> str | None:
    if not isinstance(document, dict):
        raise ValueError("search_response_must_be_object")
    results: Any = document.get("results")
    if not isinstance(results, list):
        raise ValueError("search_results_must_be_list")
    for item in results[:10]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        candidate = str(item["url"])
        parsed = urlsplit(candidate)
        if (
            len(candidate) <= 2048
            and parsed.scheme == "https"
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
        ):
            return candidate
    return None
