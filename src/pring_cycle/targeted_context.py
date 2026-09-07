from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from functools import partial

from pring_cycle.models import ModelRepository
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import select_retrieval_input
from pring_cycle.tushare_context import (
    ContextRequestOperation,
    ContextRows,
    ContextScalar,
    TushareContextAdapter,
)


class _RequestFailed(Exception):
    def __init__(self, response: RetrievalAdapterResponse) -> None:
        self.response = response


def retrieve_tushare_context(
    paths: RuntimePaths, run_id: str, token: str, *, scope_run: RunRecord | None = None
) -> RetrievalAdapterResponse:
    run = scope_run or RunRepository(paths.database).get(run_id)
    scope = run.retrieval_scope
    if scope is None:
        raise ValueError("retrieval_scope_required")
    version = str(
        ModelRepository(paths.database).manifest(run.model_version_id)["metric_catalog_version"]
    )
    adapter = TushareContextAdapter(token)
    retrieve: Callable[[], tuple[ContextScalar, ...]] | None = None
    metrics = set(scope.metric_ids)
    if len(scope.period) == 7 and "-Q" not in scope.period:
        methods = (
            ({"CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"}, adapter.pmi),
            ({"CN_CPI_HEADLINE", "CN_PPI"}, adapter.prices),
            ({"CN_M1_M2"}, adapter.money),
            ({"CN_SF_TOTAL"}, adapter.social_financing),
        )
        for members, method in methods:
            if metrics <= members:
                retrieve = partial(method, start_month=scope.period, end_month=scope.period)
                break
    elif len(scope.period) == 7 and "-Q" in scope.period and metrics == {"CN_GDP"}:
        retrieve = partial(
            adapter.gdp,
            start_quarter=scope.period.replace("-", ""),
            end_quarter=scope.period.replace("-", ""),
        )
    elif len(scope.period) == 10:
        day = date.fromisoformat(scope.period)
        daily_methods = (
            ({"CN_DR007", "CN_SHIBOR_ON_1W_3M"}, adapter.transmission),
            ({"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"}, adapter.treasury_yields),
            ({"CN_MARGIN_BALANCE"}, adapter.margin_financing),
            ({"CN_INDEX_VALUATION"}, adapter.index_valuation),
            (
                {
                    "CN_EQ_CSI300",
                    "CN_EQ_CSI500",
                    "CN_EQ_CSI1000",
                    "CN_BOND_FULL_PRICE_CNY030",
                    "CN_BOND_10Y_930916",
                    "CN_COMMODITY_BROAD_NHCI",
                },
                adapter.market_indices,
            ),
        )
        for members, daily_method in daily_methods:
            if metrics <= members:
                retrieve = partial(daily_method, start_date=day, end_date=day)
                break
    if retrieve is None:
        return RetrievalAdapterResponse(
            "not_configured", classification="targeted_tushare_family_unavailable"
        )

    ledger = RetrievalLedger(paths.database, scope_run=scope_run)
    pending_requests: list[str] = []

    def finish(outcome: str, classification: str) -> None:
        for request_id in pending_requests:
            ledger.complete(request_id, outcome=outcome, classification=classification)

    def trace(
        api: str,
        params: dict[str, str],
        fields: tuple[str, ...],
        operation: ContextRequestOperation,
    ) -> ContextRows:
        rows: ContextRows = ()

        def acquire(started: Callable[[str], None]) -> RetrievalAdapterResponse:
            nonlocal rows
            rows = operation(started)
            return RetrievalAdapterResponse(
                "candidate_source", classification="raw_fields_validated"
            )

        for _attempt in range(3):
            response = ledger.trace_acquisition(
                run_id,
                "tushare",
                scope.release_event_id,
                json.dumps({"api_name": api, "params": params, "fields": fields}, sort_keys=True),
                acquire,
                defer_completion=True,
            )
            if response.classification != "transient_transport_error":
                break
        if response.status != "candidate_source":
            raise _RequestFailed(response)
        if response.physical_request_id is not None:
            pending_requests.append(response.physical_request_id)
        return rows

    try:
        adapter.acquire_scalars(
            paths,
            lambda: tuple(s for s in retrieve() if s.metric_id in metrics),
            definition_version=version,
            request_wrapper=trace,
        )
    except _RequestFailed as error:
        finish("failed", error.response.classification or "context_batch_incomplete")
        if error.response.classification == "transient_transport_error":
            return replace(error.response, classification="transient_retries_exhausted")
        return error.response
    except (TypeError, ValueError):
        finish("failed", "semantic_validation_failed")
        raise
    finish("candidate_source", "context_fields_validated")
    selection = select_retrieval_input(paths, run)
    if selection.complete:
        digest = hashlib.sha256(
            "\x1f".join(sorted(selection.selected_claim_ids)).encode()
        ).hexdigest()
        return RetrievalAdapterResponse(
            "verified",
            evidence=f"selected-evidence:{digest}",
            classification="complete_model_input",
        )
    return RetrievalAdapterResponse(
        "candidate_source", evidence="tushare:context", classification="incomplete_model_input"
    )
