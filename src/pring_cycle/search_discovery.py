from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.http_transport import open_no_redirects as urlopen
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.retrieval_ledger import (
    RetrievalBudgetBlocked,
    RetrievalLedger,
    http_failure_classification,
)
from pring_cycle.runtime import RuntimePaths

MAX_SEARCH_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class SearchHttpResponse:
    status: int
    document: object
    raw: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)


SearchTransport = Callable[
    [str, dict[str, str], dict[str, object]],
    SearchHttpResponse,
]


def build_search_query(metric_ids: tuple[str, ...], *, period: str) -> str:
    """The family's release title with the period in Chinese (retrieval registry)."""
    from pring_cycle.retrieval_registry import search_query

    query = search_query(metric_ids, period)
    if len(query) > 800:
        raise ValueError("search_query_too_long")
    return query


def search_discovery_adapter(
    provider: str,
    api_key: str,
    query: str,
    *,
    transport: SearchTransport | None = None,
    paths: RuntimePaths | None = None,
    run_id: str | None = None,
    verify_candidates: Callable[[str, tuple[str, ...], tuple[str, ...]], RetrievalAdapterResponse]
    | None = None,
    ledger: RetrievalLedger | None = None,
    domains: tuple[str, ...] = (),
) -> Callable[[str], RetrievalAdapterResponse]:
    if not api_key:
        raise ValueError("search_api_key_required")
    if not query or len(query) > 800:
        raise ValueError("search_query_invalid")
    endpoint, headers, payload = _request_contract(provider, api_key, query, domains)
    request = transport or _post_json

    def interpret(response: SearchHttpResponse) -> RetrievalAdapterResponse:
        failure = http_failure_classification(response.status)
        if failure is not None:
            return RetrievalAdapterResponse("failed", classification=failure)
        document = response.document
        if response.raw is not None:
            if len(response.raw) > MAX_SEARCH_RESPONSE_BYTES:
                raise ValueError("search_response_too_large")
            try:
                document = json.loads(response.raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("search_response_invalid_json") from error
        candidates = _candidates(document)
        if not candidates:
            return RetrievalAdapterResponse("not_found")
        return RetrievalAdapterResponse(
            "candidate_source",
            evidence=candidates[0][0],
            classification="unverified_candidate",
            candidate_sources=tuple(item[0] for item in candidates),
            candidate_summaries=tuple(item[1] for item in candidates),
        )

    def retrieve(release_event_id: str) -> RetrievalAdapterResponse:
        if paths is None or run_id is None:
            return interpret(request(endpoint, headers, payload))
        active_ledger = ledger or RetrievalLedger(paths.database)

        def reuse(interrupted_only: bool) -> RetrievalAdapterResponse | None:
            reused = active_ledger.search_checkpoint(run_id, provider, query)
            if reused is None or verify_candidates is None:
                return None
            original_request_id, acquisition_id = reused
            try:
                acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
                normalized = json.loads(acquisitions.read_content(acquisition_id, "normalized"))
                if normalized.get("status") != "candidate_source":
                    return None
                raw = acquisitions.read_content(acquisition_id, "raw")
                candidate = interpret(SearchHttpResponse(200, None, raw))
            except (LookupError, OSError, ValueError):
                return None
            if not candidate.candidate_sources:
                return None
            if interrupted_only and not active_ledger.candidate_resume_pending(
                original_request_id, candidate.candidate_sources
            ):
                return None
            active_ledger.record_search_reuse(run_id, original_request_id)
            return replace(
                verify_candidates(
                    original_request_id,
                    candidate.candidate_sources,
                    candidate.candidate_summaries,
                ),
                cache_hit=True,
                physical_request_id=original_request_id,
            )

        if checkpoint := reuse(interrupted_only=True):
            return checkpoint
        try:
            request_id = active_ledger.reserve(
                run_id, provider, release_event_id, query, domains=domains
            )
        except RetrievalBudgetBlocked as error:
            if checkpoint := reuse(interrupted_only=False):
                return checkpoint
            return RetrievalAdapterResponse(
                "not_attempted", classification=str(error), cache_hit=error.cache_hit
            )
        responses = []

        def fetch() -> bytes:
            response = request(endpoint, headers, payload)
            responses.append(response)
            if response.raw is None:
                raise ValueError("acquisition_raw_response_bytes_required")
            return response.raw

        try:
            acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
                provider=provider,
                api_name="search",
                parameters={
                    "query": query,
                    "include_domains": ",".join(domains),
                    "retrieval_request_id": request_id,
                },
                fields="results",
                parser_version="search-discovery-v0002",
                fetch=fetch,
                parse=lambda raw: interpret(responses[0]),
                normalize=asdict,
                on_started=lambda acquisition_id: active_ledger.attach_acquisition(
                    request_id, acquisition_id
                ),
            )
            result = acquired.value
        except (OSError, TimeoutError):
            result = RetrievalAdapterResponse("failed", classification="transient_transport_error")
        except ValueError:
            result = RetrievalAdapterResponse("failed", classification="semantic_validation_failed")
        response = responses[0] if responses else None
        cost, provider_request_id = _response_usage(provider, response)
        active_ledger.complete(
            request_id,
            outcome=result.status,
            classification=result.classification,
            status=response.status if response else None,
            headers=response.headers if response else None,
            cost=cost,
            provider_request_id=provider_request_id,
        )
        if result.candidate_sources and verify_candidates is not None:
            result = verify_candidates(
                request_id, result.candidate_sources, result.candidate_summaries
            )
        return replace(result, physical_request_id=request_id)

    return retrieve


def _request_contract(
    provider: str,
    api_key: str,
    query: str,
    domains: tuple[str, ...] = (),
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
                "max_results": 3,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "include_usage": True,
                **({"include_domains": list(domains)} if domains else {}),
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
            {
                "query": query,
                "type": "auto",
                "numResults": 3,
                # The page text, so a media page's figure can be checked without a refetch.
                "contents": {"text": {"maxCharacters": 1500}},
                **({"includeDomains": list(domains)} if domains else {}),
            },
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
            response_headers = {str(key): str(value) for key, value in response.headers.items()}
    except HTTPError as error:
        return SearchHttpResponse(
            int(error.code), {}, error.read(MAX_SEARCH_RESPONSE_BYTES + 1), dict(error.headers)
        )
    return SearchHttpResponse(status, None, content, response_headers)


def _response_usage(
    provider: str, response: SearchHttpResponse | None
) -> tuple[dict[str, object] | None, str | None]:
    if response is None or response.raw is None or len(response.raw) > MAX_SEARCH_RESPONSE_BYTES:
        return None, None
    try:
        document = json.loads(response.raw)
    except (UnicodeDecodeError, ValueError):
        return None, None
    if not isinstance(document, dict):
        return None, None
    request_id = document.get("request_id" if provider == "tavily" else "requestId")
    if not isinstance(request_id, str) or len(request_id) > 128:
        request_id = None
    usage = document.get("usage" if provider == "tavily" else "costDollars")
    if not isinstance(usage, dict):
        return None, request_id
    amount = usage.get("credits" if provider == "tavily" else "total")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        return None, request_id
    try:
        if not math.isfinite(amount):
            return None, request_id
    except OverflowError:
        return None, request_id
    return {
        "amount": amount,
        "unit": "credit" if provider == "tavily" else "USD",
        "basis": "provider_usage" if provider == "tavily" else "provider_estimate",
    }, request_id


def _candidates(document: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(document, dict):
        raise ValueError("search_response_must_be_object")
    results: Any = document.get("results")
    if not isinstance(results, list):
        raise ValueError("search_results_must_be_list")
    candidates = []
    remaining_characters = 1800
    for item in results[:3]:
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
            summary = item.get("content", item.get("text", ""))
            summary = summary[:remaining_characters] if isinstance(summary, str) else ""
            remaining_characters -= len(summary)
            candidates.append((candidate, summary))
    return tuple(candidates)
