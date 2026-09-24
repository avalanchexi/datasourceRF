"""AI WebSearch: the cascade's last level, through the CLIs' own live web search.

Codex CLI is asked first and Claude Code if Codex fails or times out, as for reports. Each
returns a fixed structure: candidates with URL, quote, value, period and publication
date. A candidate fills the gap only when its host is an official or whitelisted media
host, the family's news rule reads the same value from its quote (a P2 lenient metric: the
quote states the value for the day), its period is the gap's, and it was published by the
run's cutoff. An adopted value keeps its quote like any news value (ADR-0026).

Bounds (loose, system-level): once per gap per run (the retrieval ledger), 300 seconds a
call, and 60 minutes for all calls of a run; past that, a gap is left with the reason
"AI time exhausted". It is asked only for a gap whose family's rules state every member
the catalog requires, so an answer can complete it. The runtime config can turn it off:
``[retrieval] ai_websearch = false``. No model vendor API key is ever used.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionReceipt
from pring_cycle.cli_process import run_structured_cli
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RetrievalScope, RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_connection

AI_ADAPTERS = ("codex_cli", "claude_code_cli")
AI_CALL_SECONDS = 300
AI_RUN_BUDGET = timedelta(minutes=60)
AI_TIME_EXHAUSTED = "ai_time_exhausted"
AI_PARSER_VERSION = "ai-websearch-v0001"
MAX_CANDIDATES = 5
_SHANGHAI = ZoneInfo("Asia/Shanghai")

CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "maxItems": MAX_CANDIDATES,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "quote": {"type": "string"},
                    "value": {"type": "number"},
                    "period": {"type": "string"},
                    "published_date": {"type": "string"},
                },
                "required": ["url", "quote", "value", "period", "published_date"],
            },
        }
    },
    "required": ["candidates"],
}


def ai_websearch_enabled(paths: RuntimePaths) -> bool:
    """On unless the runtime config says ``ai_websearch = false`` or the environment
    sets ``PRING_CYCLE_AI_WEBSEARCH=off`` (the test suite does, so no test reaches a real
    CLI unless it opts in)."""
    if os.environ.get("PRING_CYCLE_AI_WEBSEARCH", "").lower() == "off":
        return False
    try:
        config = tomllib.loads(paths.config_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return True
    return config.get("retrieval", {}).get("ai_websearch", True) is not False


def ai_seconds_used(paths: RuntimePaths, run_id: str) -> float:
    """What this run's AI WebSearch calls have taken so far."""
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT started_at, completed_at FROM retrieval_physical_request "
            "WHERE run_id=? AND channel='ai_websearch' AND completed_at IS NOT NULL",
            (run_id,),
        ).fetchall()
    return sum(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        for start, end in rows
    )


def _prompt(scope: RetrievalScope, query: str, domains: tuple[str, ...]) -> str:
    from pring_cycle.news_rules import rules_for

    return json.dumps(
        {
            "instruction": (
                "用联网搜索查找下列指标在给定统计期的数值。"
                "只能采用 allowed_domains 中的网站（含其子域名）上的页面；"
                "quote 必须逐字摘录页面上陈述该数值的原句，且原句写明统计期；"
                "统计期须能从原句本身确定到年份，写法如 period_wording；"
                "日度数据只写“9月23日”而无年份的句子不可用，应另找写全日期的原句；"
                "value 为原句中的数值（百分数只写数字，金额按原句单位）；"
                "period 按 period 字段的格式写统计期；"
                "published_date 为页面发布日期（YYYY-MM-DD）。"
                "找不到可靠原句就返回空数组，不得推算或编造。"
            ),
            "metric_ids": list(scope.metric_ids),
            "period": scope.period,
            "period_wording": _period_wording(scope.period),
            "search_query": query,
            "allowed_domains": list(domains),
            "sentence_patterns": [rule.pattern.pattern for rule in rules_for(scope.metric_ids)],
        },
        ensure_ascii=False,
    )


_QUARTERS = ("一", "二", "三", "四")


def _period_wording(period: str) -> str:
    """How a Chinese release writes the gap's period, year included."""
    year = int(period[:4])
    if "-Q" in period:
        return f"{year}年第{_QUARTERS[int(period[-1]) - 1]}季度"
    if len(period) == 10:
        day = date.fromisoformat(period)
        return f"{year}年{day.month}月{day.day}日"
    return f"{year}年{int(period[5:7])}月"


def ai_websearch_adapter(
    paths: RuntimePaths,
    run_id: str,
    scope_run: RunRecord,
    *,
    definition_version: str,
    adapters: tuple[str, ...] = AI_ADAPTERS,
) -> Callable[[str], RetrievalAdapterResponse]:
    """The cascade adapter for one gap; it calls at most one CLI answer into the run."""
    from pring_cycle.retrieval_ledger import RetrievalBudgetBlocked
    from pring_cycle.retrieval_registry import search_domains, search_query

    def retrieve(release_event_id: str) -> RetrievalAdapterResponse:
        scope = scope_run.retrieval_scope
        assert scope is not None
        remaining = AI_RUN_BUDGET.total_seconds() - ai_seconds_used(paths, run_id)
        if remaining <= 0:
            return RetrievalAdapterResponse("not_attempted", classification=AI_TIME_EXHAUSTED)
        query = search_query(scope.metric_ids, scope.period)
        domains = search_domains(scope.metric_ids)
        ledger = RetrievalLedger(paths.database, scope_run=scope_run)
        try:
            request_id = ledger.reserve(
                run_id, "ai_websearch", release_event_id, query, domains=domains
            )
        except RetrievalBudgetBlocked as error:
            return RetrievalAdapterResponse(
                "not_attempted", classification=str(error), cache_hit=error.cache_hit
            )
        prompt = _prompt(scope, query, domains)
        answered: tuple[str, dict[str, Any]] | None = None
        attempts: list[dict[str, Any]] = []
        for adapter in adapters:
            if remaining <= 0:
                break
            started = time.monotonic()
            outcome = run_structured_cli(
                adapter,
                prompt,
                CANDIDATE_SCHEMA,
                timeout_seconds=min(AI_CALL_SECONDS, remaining),
                audit={"retrieval_request_id": request_id, "adapter": adapter},
                web_search=True,
            )
            classification = outcome.classification
            if outcome.document is not None:
                if outcome.tool_events:
                    classification = "tool_use_rejected"
                elif _candidates(outcome.document) is None:
                    classification = "schema_validation_failed"
            attempts.append(
                {
                    "adapter": adapter,
                    "outcome": classification or "succeeded",
                    "tool_events": outcome.tool_events,
                    "cli_version": outcome.version,
                    "audit": outcome.audit,
                }
            )
            if classification is None and outcome.document is not None:
                answered = (adapter, outcome.document)
                break
            remaining -= time.monotonic() - started
        document = {
            "adapters": attempts,
            "answer": answered[1] if answered else None,
        }
        response = _record_answer(
            paths,
            ledger,
            request_id,
            scope_run,
            answered[0] if answered else _last_adapter(attempts, adapters),
            document,
            definition_version=definition_version,
        )
        return response

    return retrieve


def _last_adapter(attempts: list[dict[str, Any]], adapters: tuple[str, ...]) -> str:
    return str(attempts[-1]["adapter"]) if attempts else adapters[0]


def _candidates(document: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The answer's candidates when it has exactly the fixed structure, else None."""
    candidates = document.get("candidates")
    if set(document) != {"candidates"} or not isinstance(candidates, list):
        return None
    fields = {"url", "quote", "value", "period", "published_date"}
    for item in candidates:
        if (
            not isinstance(item, dict)
            or set(item) != fields
            or not all(isinstance(item[key], str) for key in fields - {"value"})
            or isinstance(item["value"], bool)
            or not isinstance(item["value"], int | float)
        ):
            return None
    return candidates[:MAX_CANDIDATES]


def _record_answer(
    paths: RuntimePaths,
    ledger: RetrievalLedger,
    request_id: str,
    run: RunRecord,
    adapter: str,
    document: dict[str, Any],
    *,
    definition_version: str,
) -> RetrievalAdapterResponse:
    """Keep the exchange as an acquisition, then check each candidate on its own."""
    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.search_evidence import select_retrieval_input

    scope = run.retrieval_scope
    assert scope is not None
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
    answer = document["answer"]
    try:
        acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
            provider=adapter,
            api_name="ai_websearch",
            parameters={
                "metric_ids": ",".join(scope.metric_ids),
                "period": scope.period,
                "retrieval_request_id": request_id,
            },
            fields="candidates",
            parser_version=AI_PARSER_VERSION,
            fetch=lambda: raw,
            parse=lambda _raw: _candidates(answer) if answer is not None else [],
            normalize=lambda candidates: {"candidates": candidates},
            on_started=lambda acquisition_id: ledger.attach_acquisition(request_id, acquisition_id),
        )
    except ValueError:
        ledger.complete(request_id, outcome="failed", classification="semantic_validation_failed")
        return RetrievalAdapterResponse("failed", classification="semantic_validation_failed")
    candidates = acquired.value or []
    if answer is None:
        ledger.complete(request_id, outcome="failed", classification="ai_websearch_unavailable")
        return RetrievalAdapterResponse(
            "failed", classification="ai_websearch_unavailable", physical_request_id=request_id
        )
    claim_ids: list[str] = []
    for candidate in candidates:
        reason, stored = _adopt(
            paths, run, candidate, acquired.receipt, adapter, definition_version=definition_version
        )
        claim_ids.extend(stored)
        _record_validation(paths, run, request_id, candidate, reason, stored)
    selection = select_retrieval_input(paths, run)
    if claim_ids and selection.complete:
        ledger.complete(request_id, outcome="verified", classification="complete_model_input")
        return RetrievalAdapterResponse(
            "verified",
            evidence=f"ai-websearch:{request_id}",
            classification="complete_model_input",
            physical_request_id=request_id,
        )
    status = "candidate_source" if candidates else "not_found"
    ledger.complete(request_id, outcome=status, classification="candidate_validation_unresolved")
    return RetrievalAdapterResponse(
        status,
        evidence=candidates[0]["url"] if candidates else None,
        classification="candidate_validation_unresolved",
        physical_request_id=request_id,
    )


def _adopt(
    paths: RuntimePaths,
    run: RunRecord,
    candidate: dict[str, Any],
    receipt: AcquisitionReceipt,
    adapter: str,
    *,
    definition_version: str,
) -> tuple[str | None, tuple[str, ...]]:
    """Why a candidate is not adopted (None when it is), and the claims it stored."""
    from pring_cycle.news_rules import (
        AI_WEBSEARCH,
        NewsValue,
        TakenValue,
        extract,
        rules_for,
        store_news_values,
        text_hash,
    )
    from pring_cycle.retrieval_registry import media_outlet, registered_host
    from pring_cycle.search_evidence import (
        DATE_AFTER_CUTOFF,
        NO_PUBLICATION_DATE,
        NOT_WHITELISTED,
        PERIOD_MISMATCH,
        RULE_NOT_MATCHED,
        SEARCH_VALUE_MISMATCH,
        CandidateRejected,
        lenient_value,
    )

    scope = run.retrieval_scope
    assert scope is not None
    url, quote, value = candidate["url"], candidate["quote"], float(candidate["value"])
    source = media_outlet(url) or next(
        (host for metric in scope.metric_ids if (host := registered_host(metric, url))), None
    )
    if source is None:
        return NOT_WHITELISTED, ()
    if rules_for(scope.metric_ids):
        extraction = extract(scope.metric_ids, scope.period, quote)
        if extraction.reason is not None:
            return extraction.reason, ()
        # The CLI reports the number as the sentence writes it ("437.5万亿元", "下降0.4%");
        # the rule also gives it in the member's unit and sign. Either is the same figure.
        values = tuple(item for item in extraction.values if value in {item.value, item.stated})
        if not values:
            return SEARCH_VALUE_MISMATCH, ()
    else:
        try:
            if lenient_value(quote, date.fromisoformat(scope.period)) != value:
                return SEARCH_VALUE_MISMATCH, ()
        except (CandidateRejected, ValueError) as error:
            return (str(error) if isinstance(error, CandidateRejected) else RULE_NOT_MATCHED), ()
        values = (NewsValue(scope.metric_ids[0], {}, value, quote),)
    if candidate["period"] != scope.period:
        return PERIOD_MISMATCH, ()
    try:
        published = date.fromisoformat(candidate["published_date"])
    except ValueError:
        return NO_PUBLICATION_DATE, ()
    if published > run.system_as_of.astimezone(_SHANGHAI).date():
        return DATE_AFTER_CUTOFF, ()
    stored = store_news_values(
        paths.database,
        tuple(
            TakenValue(
                value=item,
                title="",
                source_name=source,
                published_at=published.isoformat(),
                body_hash=text_hash(quote),
                url=url,
                acquisition_id=receipt.acquisition_id,
                fetched_at=receipt.received_at or receipt.started_at,
                # A date alone does not say when that day: the time stays unknown.
                release_at=None,
            )
            for item in values
        ),
        route=AI_WEBSEARCH,
        provider=f"{AI_WEBSEARCH}:{adapter}",
        source_reference=lambda _taken: f"{AI_WEBSEARCH}:{url}#{receipt.raw_hash}",
        period=scope.period,
        definition_version=definition_version,
        available_at=receipt.validated_at or receipt.started_at,
    )
    return None, stored


def _record_validation(
    paths: RuntimePaths,
    run: RunRecord,
    request_id: str,
    candidate: dict[str, Any],
    reason: str | None,
    claim_ids: tuple[str, ...],
) -> None:
    """One row per candidate on the run's search record, as for Tavily and Exa."""
    from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now

    scope = run.retrieval_scope
    assert scope is not None
    snapshot = RetrievalLedger(paths.database, scope_run=run).for_run(run.run_id)
    gap_ids = [
        gap["gap_id"]
        for gap in (snapshot or {}).get("gaps", [])
        if gap["metric_id"] in scope.metric_ids
        and gap["period"] == scope.period
        and gap["as_of"] == run.system_as_of.astimezone(UTC).isoformat()
    ]
    with database_connection(paths.database) as connection:
        connection.execute(
            "INSERT INTO retrieval_candidate_validation(validation_id, run_id, "
            "search_request_id, candidate_url, outcome, reason, checked_at, gap_ids_json, "
            "selected_claim_ids_json, claim_ids_json, parser_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)",
            (
                "candidate-validation-" + uuid.uuid4().hex,
                run.run_id,
                request_id,
                candidate["url"],
                "not_model_usable" if reason else "model_usable",
                reason,
                utc_now().isoformat(),
                json.dumps(gap_ids),
                json.dumps(list(claim_ids)),
                AI_PARSER_VERSION,
            ),
        )
