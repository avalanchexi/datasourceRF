"""AI WebSearch: the cascade's last level, through the CLIs' own live web search.

Codex CLI is asked first and Claude Code if Codex fails or times out, as for reports. Each
returns a fixed structure: candidates with URL, quote, value, period and publication
date. A candidate fills the gap only when its host is an official or whitelisted media
host, the family's news rule reads the same value from its quote, its period is the gap's,
and it was published by the run's cutoff; then its page is fetched once and read by the
rules as a media page is, title and subject clauses included, and must state the same
value as the country's (lookback 26). An adopted value keeps the page's sentence, subject
clause, title and original like any news value (ADR-0026).

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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from datetime import time as clock_time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from pring_cycle.cli_process import run_structured_cli
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RetrievalScope, RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.storage import database_connection

if TYPE_CHECKING:
    from pring_cycle.acquisition import AcquisitionReceipt
    from pring_cycle.media_recheck import MediaConflict
    from pring_cycle.search_evidence import ModelInputSelection, NewsPage

AI_ADAPTERS = ("codex_cli", "claude_code_cli")
AI_CALL_SECONDS = 300
AI_RUN_BUDGET = timedelta(minutes=60)
AI_TIME_EXHAUSTED = "ai_time_exhausted"
# Every member the gap misses is one whose media values a recheck left unsettled.
MEDIA_CONFLICT_UNSETTLED = "media_conflict_unsettled"
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


def _prompt(
    scope: RetrievalScope,
    query: str,
    domains: tuple[str, ...],
    asked: dict[str, tuple[dict[str, str], ...] | None] | None = None,
) -> str:
    from pring_cycle.news_rules import rules_for

    return json.dumps(
        {
            "instruction": (
                "用联网搜索查找下列指标在给定统计期的数值。"
                "只能采用 allowed_domains 中的网站（含其子域名）上的页面；"
                "quote 必须逐字摘录页面上陈述该数值的原句，且原句写明统计期；"
                "统计期须能从原句本身确定到年份，写法如 period_wording；"
                "日度数据只写“9月23日”而无年份的句子不可用，应另找写全日期的原句；"
                "members 为所缺的成员（为空时不限）；"
                "value 为原句中所缺成员的数值（百分数只写数字，金额按原句单位）；"
                "period 按 period 字段的格式写统计期；"
                "published_date 为页面发布日期（YYYY-MM-DD）。"
                "找不到可靠原句就返回空数组，不得推算或编造。"
            ),
            "metric_ids": list(scope.metric_ids),
            "members": [
                {"metric_id": metric_id, "dimensions": member}
                for metric_id, members in (asked or _asked_members(scope)).items()
                for member in members or ()
            ],
            "period": scope.period,
            "period_wording": _period_wording(scope.period),
            "search_query": query,
            "allowed_domains": list(domains),
            "sentence_patterns": [rule.pattern.pattern for rule in rules_for(scope.metric_ids)],
        },
        ensure_ascii=False,
    )


Asked = dict[str, tuple[dict[str, str], ...] | None]


def _asked_members(scope: RetrievalScope, missing: tuple[str, ...] | None = None) -> Asked:
    """Per metric, the members the AI is asked for: those the scope reads (its lookback's,
    else the catalog's required ones, as rules_cover decides whether to ask), of them only
    the ``missing`` when given; None when the notice decides its members."""
    from pring_cycle.metric_contracts import required_dimension_members
    from pring_cycle.runs import member_key

    asked: Asked = {}
    for metric_id in scope.metric_ids:
        members = scope.named_members(metric_id) or required_dimension_members(
            metric_id, definition_version="registered", period=scope.period
        )
        asked[metric_id] = (
            members
            if members is None or missing is None
            else tuple(m for m in members if member_key(metric_id, m) in missing)
        )
    return asked


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
) -> AiWebSearch:
    """The cascade adapter for one gap; it calls at most one CLI answer into the run."""
    return AiWebSearch(
        paths, run_id, scope_run, definition_version=definition_version, adapters=adapters
    )


class AiWebSearch:
    """The cascade adapter for one gap; it calls at most one CLI answer into the run.

    A gap whose media values of a member disagree is asked first (``rechecks_first``), the
    disagreeing members with those it misses, and the answer's page-read values settle them
    or not (``media_recheck``, ADR-0039). A member a recheck left unsettled for the same
    claims is not asked again.
    """

    def __init__(
        self,
        paths: RuntimePaths,
        run_id: str,
        scope_run: RunRecord,
        *,
        definition_version: str,
        adapters: tuple[str, ...] = AI_ADAPTERS,
    ) -> None:
        self.paths, self.run_id, self.scope_run = paths, run_id, scope_run
        self.definition_version, self.adapters = definition_version, adapters

    def rechecks_first(self) -> bool:
        """Whether the gap holds media values that disagree and no recheck has judged."""
        from pring_cycle.media_recheck import media_conflicts

        return bool(media_conflicts(self.paths, self.scope_run).pending)

    def __call__(self, release_event_id: str) -> RetrievalAdapterResponse:
        from pring_cycle.media_recheck import media_conflicts
        from pring_cycle.retrieval_ledger import RetrievalBudgetBlocked
        from pring_cycle.retrieval_registry import search_domains, search_query
        from pring_cycle.search_evidence import select_retrieval_input

        paths, run_id, scope_run = self.paths, self.run_id, self.scope_run
        scope = scope_run.retrieval_scope
        assert scope is not None
        remaining = AI_RUN_BUDGET.total_seconds() - ai_seconds_used(paths, run_id)
        if remaining <= 0:
            return RetrievalAdapterResponse("not_attempted", classification=AI_TIME_EXHAUSTED)
        conflicts = media_conflicts(paths, scope_run)
        missing = select_retrieval_input(paths, scope_run).missing_members
        if missing and set(missing) <= conflicts.unsettled:
            return RetrievalAdapterResponse(
                "not_attempted", classification=MEDIA_CONFLICT_UNSETTLED
            )
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
        # A scope reads every member of its period; the AI is asked for, and adopts, only
        # those the gap still misses: the stock held, the growth is what it wants (lookback 14).
        # A member whose media values disagree is missed too, unless a recheck already left
        # it unsettled for the same claims.
        asked = _asked_members(
            scope, tuple(member for member in missing if member not in conflicts.unsettled)
        )
        adapter, document = _ask(
            _prompt(scope, query, domains, asked), request_id, remaining, self.adapters
        )
        return _record_answer(
            paths,
            ledger,
            request_id,
            scope_run,
            adapter,
            document,
            asked,
            definition_version=self.definition_version,
            conflicts=conflicts.pending,
        )


def _ask(
    prompt: str, request_id: str, remaining: float, adapters: tuple[str, ...]
) -> tuple[str, dict[str, Any]]:
    """Each CLI in turn until one answers in the fixed structure: the one that answered (or
    the last tried) and the exchange, whose ``answer`` is None when none did."""
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
    document = {"adapters": attempts, "answer": answered[1] if answered else None}
    return (answered[0] if answered else _last_adapter(attempts, adapters)), document


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
    asked: Asked,
    *,
    definition_version: str,
    conflicts: tuple[MediaConflict, ...] = (),
) -> RetrievalAdapterResponse:
    """Keep the exchange as an acquisition, then check each candidate on its own. What its
    adopted values make of the ``conflicts`` asked about is kept before the gap is selected
    again (ADR-0039)."""
    from pring_cycle.media_recheck import record_rechecks
    from pring_cycle.runs import member_key
    from pring_cycle.search_evidence import select_retrieval_input

    scope = run.retrieval_scope
    assert scope is not None
    answer = document["answer"]
    acquired = _keep_exchange(paths, ledger, request_id, scope, adapter, document)
    if acquired is None:
        return RetrievalAdapterResponse("failed", classification="semantic_validation_failed")
    candidates = acquired.value or []
    if answer is None:
        ledger.complete(request_id, outcome="failed", classification="ai_websearch_unavailable")
        return RetrievalAdapterResponse(
            "failed", classification="ai_websearch_unavailable", physical_request_id=request_id
        )
    pages = _Pages(paths, run)
    with pages.settling():
        adopted = [
            (
                candidate,
                *_adopt(
                    paths,
                    run,
                    candidate,
                    pages,
                    adapter,
                    definition_version=definition_version,
                    asked=asked,
                ),
            )
            for candidate in candidates
        ]
    claim_ids = [claim_id for _candidate, _reason, stored in adopted for claim_id in stored]
    record_rechecks(
        paths.database,
        (
            conflict
            for conflict in conflicts
            if any(
                members is None or any(member_key(metric_id, m) == conflict.member for m in members)
                for metric_id, members in asked.items()
                if metric_id == conflict.metric_id
            )
        ),
        claim_ids,
        run_id=run.run_id,
        search_request_id=request_id,
    )
    selection = select_retrieval_input(paths, run)
    # Each is recorded against what the gap then holds, as a searched page is (lookback 14).
    for candidate, reason, stored in adopted:
        _record_validation(
            paths,
            run,
            request_id,
            candidate,
            reason,
            stored,
            pages.read_of(candidate),
            selection,
        )
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


def _keep_exchange(
    paths: RuntimePaths,
    ledger: RetrievalLedger,
    request_id: str,
    scope: RetrievalScope,
    adapter: str,
    document: dict[str, Any],
) -> Any:
    """The exchange kept as an acquisition, or None (the request failed) when it cannot be."""
    from pring_cycle.acquisition import AcquisitionRepository

    raw = json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
    answer = document["answer"]
    try:
        return AcquisitionRepository(paths.database, paths.artifacts).capture(
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
        return None


def discover_event(
    paths: RuntimePaths,
    scope_run: RunRecord,
    *,
    since: date | None,
    until: date,
    definition_version: str,
    adapters: tuple[str, ...] = AI_ADAPTERS,
) -> tuple[str, tuple[str, ...]]:
    """Ask for the latest event effective after ``since`` (or ever) and by ``until``.

    An event never held is traced back (ADR-0028): the scope names its metrics and the
    backtrack's gap. Each candidate is checked as a gap's is, on the effective day it
    gives, which must lie in the window; an adopted one is public by the end of the day its
    page was published. The outcome is ``new_event`` (claims stored), ``none_stated`` (the
    answer has no candidate), ``rejected`` (none usable) or ``unavailable`` (no answer, or
    AI WebSearch is off, out of time or held back by the ledger).
    """
    from pring_cycle.news_rules import rules_for
    from pring_cycle.retrieval_ledger import RetrievalBudgetBlocked
    from pring_cycle.retrieval_registry import search_domains, search_query
    from pring_cycle.search_evidence import DATE_AFTER_CUTOFF, PERIOD_MISMATCH

    scope = scope_run.retrieval_scope
    assert scope is not None
    remaining = AI_RUN_BUDGET.total_seconds() - ai_seconds_used(paths, scope_run.run_id)
    if not ai_websearch_enabled(paths) or remaining <= 0:
        return "unavailable", ()
    query = search_query(scope.metric_ids, until.isoformat()[:7])
    domains = search_domains(scope.metric_ids)
    ledger = RetrievalLedger(paths.database, scope_run=scope_run)
    try:
        request_id = ledger.reserve(
            scope_run.run_id, "ai_websearch", scope.release_event_id, query, domains=domains
        )
    except RetrievalBudgetBlocked:
        return "unavailable", ()
    prompt = json.dumps(
        {
            "instruction": (
                "用联网搜索查找下列指标在 effective_after 之后（为 null 时不限）、"
                "effective_by 当日及以前生效的最近一次调整。"
                "只能采用 allowed_domains 中的网站（含其子域名）上的页面；"
                "quote 必须逐字摘录页面上宣布该调整的原句，原句须写明生效日期（含年份）与调整幅度；"
                "适用范围不同的调整各给一条候选；"
                "value 为原句中的调整幅度（只写数字）；"
                "period 为生效日期（YYYY-MM-DD）；"
                "published_date 为页面发布日期（YYYY-MM-DD）。"
                "区间内没有调整就返回空数组，不得推算或编造。"
            ),
            "metric_ids": list(scope.metric_ids),
            "effective_after": since.isoformat() if since is not None else None,
            "effective_by": until.isoformat(),
            "search_query": query,
            "allowed_domains": list(domains),
            "sentence_patterns": [rule.pattern.pattern for rule in rules_for(scope.metric_ids)],
        },
        ensure_ascii=False,
    )
    adapter, document = _ask(prompt, request_id, remaining, adapters)
    acquired = _keep_exchange(paths, ledger, request_id, scope, adapter, document)
    if acquired is None:
        return "unavailable", ()
    if document["answer"] is None:
        ledger.complete(request_id, outcome="failed", classification="ai_websearch_unavailable")
        return "unavailable", ()
    candidates = acquired.value or []
    claim_ids: list[str] = []
    pages = _Pages(paths, scope_run)
    with pages.settling():
        for candidate in candidates:
            reason: str | None
            stored: tuple[str, ...]
            day = candidate["period"]
            try:
                effective = date.fromisoformat(day) if len(day) == 10 else None
            except ValueError:
                effective = None
            if effective is None or effective > until or (since is not None and effective <= since):
                reason, stored = PERIOD_MISMATCH, ()
            elif candidate["published_date"] > until.isoformat():
                # Out after the target day, it is not what the target day knew.
                reason, stored = DATE_AFTER_CUTOFF, ()
            else:
                on_day = replace(scope_run, retrieval_scope=replace(scope, period=day))
                reason, stored = _adopt(
                    paths,
                    on_day,
                    candidate,
                    pages,
                    adapter,
                    definition_version=definition_version,
                    public_by_published_day=True,
                )
            claim_ids.extend(stored)
            _record_validation(
                paths,
                scope_run,
                request_id,
                candidate,
                reason,
                stored,
                pages.read_of(candidate),
            )
    if claim_ids:
        ledger.complete(request_id, outcome="verified", classification="event_discovered")
        return "new_event", tuple(claim_ids)
    status = "candidate_source" if candidates else "not_found"
    ledger.complete(request_id, outcome=status, classification="candidate_validation_unresolved")
    return ("rejected" if candidates else "none_stated"), ()


@dataclass(frozen=True)
class _PageRead:
    """A candidate's page as read again: the page, or why it was not had."""

    page: NewsPage | None
    reason: str | None
    # The run's request that fetched it, when one was made.
    request_id: str | None


class _Pages:
    """The pages an answer's candidates name, each fetched once, one at a time, and traced
    on the run's ledger as a searched page is (lookback 26). A page is then read for the
    period each candidate asks: a backtrack's candidates may each name another day, and a
    day the page does not state leaves the others' reading as it is."""

    def __init__(self, paths: RuntimePaths, run: RunRecord) -> None:
        # ``run`` is the one the gap or backtrack was bound with: the fetch is on its ledger.
        self.paths, self.run = paths, run
        # Each address fetched: its receipt and content, or why not, and the request.
        self.fetched: dict[
            str, tuple[tuple[AcquisitionReceipt, str] | None, str | None, str | None]
        ]
        self.fetched = {}
        self.read: dict[tuple[str, str], _PageRead] = {}
        # Per page kept, why each candidate on it was not stored (None: it was).
        self.outcomes: dict[str, list[str | None]] = {}

    def read_of(self, candidate: dict[str, Any]) -> _PageRead | None:
        """The candidate's page as read for its period, if it was read."""
        return self.read.get((candidate["url"], candidate["period"]))

    def decided(self, read: _PageRead, reason: str | None) -> None:
        """What a candidate read on ``read`` came to: stored (None), or why not."""
        assert read.page is not None
        self.outcomes.setdefault(read.page.receipt.acquisition_id, []).append(reason)

    @contextmanager
    def settling(self) -> Iterator[None]:
        """Once the answer's candidates are decided, each page kept says once whether its
        values entered the evidence store, counting all its candidates' claims."""
        from pring_cycle.acquisition import AcquisitionRepository
        from pring_cycle.search_evidence import CandidateRejected

        try:
            yield
        finally:
            receipts = AcquisitionRepository(self.paths.database, self.paths.artifacts)
            for acquisition_id, reasons in self.outcomes.items():
                refused = None if None in reasons else next(r for r in reasons if r)
                receipts.record_ingest_result(
                    acquisition_id, None if refused is None else CandidateRejected(refused)
                )

    def page(self, url: str, source: str, metric_ids: tuple[str, ...], period: str) -> _PageRead:
        from pring_cycle.search_evidence import CandidateRejected, read_page_content

        if (url, period) not in self.read:
            kept, reason, request_id = self._fetch(url, source, metric_ids)
            page = None
            if kept is not None:
                try:
                    page = read_page_content(*kept, metric_ids, period, url=url)
                except CandidateRejected as error:
                    # Kept, but not stating the period: its receipt says so once settled.
                    reason = str(error)
                    self.outcomes.setdefault(kept[0].acquisition_id, []).append(reason)
            self.read[url, period] = _PageRead(page, reason, request_id)
        return self.read[url, period]

    def _fetch(
        self, url: str, source: str, metric_ids: tuple[str, ...]
    ) -> tuple[tuple[AcquisitionReceipt, str] | None, str | None, str | None]:
        from pring_cycle.search_evidence import (
            RETRIEVAL_BLOCKED,
            candidate_rejection_reason,
            fetch_news_page,
        )

        if url in self.fetched:
            return self.fetched[url]
        scope = self.run.retrieval_scope
        assert scope is not None
        found: list[tuple[AcquisitionReceipt, str]] = []
        errors: list[str] = []

        def acquire(on_started: Callable[[str], None]) -> RetrievalAdapterResponse:
            try:
                found.append(
                    fetch_news_page(
                        self.paths,
                        url,
                        source=source,
                        source_of=lambda final: _page_source(metric_ids, final),
                        on_acquisition_started=on_started,
                    )
                )
            except (OSError, TypeError, ValueError) as error:
                errors.append(candidate_rejection_reason(error))
                raise
            return RetrievalAdapterResponse(
                "candidate_source", evidence=url, classification="document_validated"
            )

        response = RetrievalLedger(self.paths.database, scope_run=self.run).trace_acquisition(
            self.run.run_id, "official", scope.release_event_id, url, acquire
        )
        reason = None if found else errors[0] if errors else RETRIEVAL_BLOCKED
        self.fetched[url] = (found[0] if found else None, reason, response.physical_request_id)
        return self.fetched[url]


def _page_source(metric_ids: tuple[str, ...], url: str) -> str | None:
    """The whitelisted outlet or the metrics' registered host ``url`` is on, or None."""
    from pring_cycle.retrieval_registry import media_outlet, registered_host

    return media_outlet(url) or next(
        (host for metric in metric_ids if (host := registered_host(metric, url))), None
    )


def _adopt(
    paths: RuntimePaths,
    run: RunRecord,
    candidate: dict[str, Any],
    pages: _Pages,
    adapter: str,
    *,
    definition_version: str,
    asked: Asked | None = None,
    public_by_published_day: bool = False,
) -> tuple[str | None, tuple[str, ...]]:
    """Why a candidate is not adopted (None when it is), and the claims it stored.

    The CLI's sentence is checked first, as it gave it: its host, the family's rules, its
    figure, period and publication date. Its page is then read again by the rules, as a
    media page is (lookback 26): the CLI gives a sentence alone, while a place may be named
    in the page's title or before the sentence in its paragraph. What the page states of
    the same members, with the same figures, is taken and kept with the page's sentence,
    subject clause, title and original; a page not had, or not stating them as the
    country's, gives nothing.

    ``asked``: the members it may fill (``_asked_members``), by default all the scope reads.
    ``public_by_published_day``: a past event found by a backtrack was public, at the
    latest, by the end of the day its page was published.
    """
    from pring_cycle.news_rules import (
        AI_WEBSEARCH,
        NewsValue,
        TakenValue,
        extract,
        parse_published_at,
        rules_for,
        store_news_values,
        text_hash,
    )
    from pring_cycle.search_evidence import (
        DATE_AFTER_CUTOFF,
        INCOMPLETE_MODEL_INPUT,
        NO_PUBLICATION_DATE,
        NOT_WHITELISTED,
        PERIOD_MISMATCH,
        RULE_NOT_MATCHED,
        SEARCH_VALUE_MISMATCH,
    )

    scope = run.retrieval_scope
    assert scope is not None
    url, quote, value = candidate["url"], candidate["quote"], float(candidate["value"])
    source = _page_source(scope.metric_ids, url)
    if source is None:
        return NOT_WHITELISTED, ()
    if not rules_for(scope.metric_ids):
        # No rule to read its page by, nor the subject of its figure.
        return RULE_NOT_MATCHED, ()
    extraction = extract(scope.metric_ids, scope.period, quote, url=url)
    if extraction.reason is not None:
        return extraction.reason, ()
    # The CLI reports the number as the sentence writes it ("437.5万亿元", "下降0.4%");
    # the rule also gives it in the member's unit and sign. Either is the same figure.
    reported = tuple(item for item in extraction.values if value in {item.value, item.stated})
    if not reported:
        return SEARCH_VALUE_MISMATCH, ()
    # The sentence is the one the CLI read; what it states of the members the gap misses
    # is taken, whichever figure the CLI gave (lookback 14: it gave the stock, the gap
    # was the growth written after it).
    wanted = asked if asked is not None else _asked_members(scope)
    values = tuple(
        item
        for item in extraction.values
        if item.metric_id in wanted
        and (wanted[item.metric_id] is None or item.dimensions in (wanted[item.metric_id] or ()))
    )
    if not values:
        # Read as the CLI said, but it states nothing the gap misses.
        return INCOMPLETE_MODEL_INPUT, ()
    if candidate["period"] != scope.period:
        return PERIOD_MISMATCH, ()
    try:
        published = date.fromisoformat(candidate["published_date"])
    except ValueError:
        return NO_PUBLICATION_DATE, ()
    if published > run.system_as_of.astimezone(_SHANGHAI).date():
        return DATE_AFTER_CUTOFF, ()
    read = pages.page(url, source, scope.metric_ids, scope.period)
    if read.page is None:
        assert read.reason is not None
        return read.reason, ()
    page = read.page
    on_page = {
        (item.metric_id, tuple(item.dimensions.items())): item for item in page.extraction.values
    }

    def why_not(item: NewsValue) -> str | None:
        """Why the page does not state ``item`` as the country's, or None when it does."""
        stated = on_page.get((item.metric_id, tuple(item.dimensions.items())))
        if stated is None:
            # Not stated there, or stated as a place's: its title or subject clause names one.
            return RULE_NOT_MATCHED
        return SEARCH_VALUE_MISMATCH if stated.value != item.value else None

    # The figure the CLI reported, and each one taken, must be the page's own.
    reason = next((r for item in values if (r := why_not(item))), None)
    if reason is None and all(why_not(item) for item in reported):
        reason = why_not(reported[0])
    page_published = parse_published_at(page.published_text)
    if reason is None and page_published is not None and page_published > run.system_as_of:
        reason = DATE_AFTER_CUTOFF
    if reason is not None:
        pages.decided(read, reason)
        return reason, ()
    taken = [on_page[item.metric_id, tuple(item.dimensions.items())] for item in values]
    receipt = page.receipt
    assert receipt.received_at is not None and receipt.validated_at is not None
    try:
        stored = store_news_values(
            paths.database,
            tuple(
                TakenValue(
                    value=item,
                    title=page.title,
                    source_name=source,
                    published_at=(page_published or published).isoformat(),
                    body_hash=text_hash(page.text),
                    url=url,
                    acquisition_id=receipt.acquisition_id,
                    fetched_at=receipt.received_at,
                    # The page's own time when it shows one; a date alone does not say when
                    # that day, so the time stays unknown.
                    release_at=page_published,
                    public_at=(
                        datetime.combine(published, clock_time.max, tzinfo=_SHANGHAI)
                        if public_by_published_day
                        else None
                    ),
                )
                for item in taken
            ),
            route=AI_WEBSEARCH,
            provider=f"{AI_WEBSEARCH}:{adapter}",
            source_reference=lambda _taken: f"{AI_WEBSEARCH}:{url}#sha256={receipt.raw_hash}",
            period=scope.period,
            definition_version=definition_version,
            available_at=receipt.validated_at,
        )
    except ValueError as error:
        # Refused by the registered contract: the page's receipt says so once settled.
        pages.decided(read, str(error)[:300])
        raise
    pages.decided(read, None)
    return None, stored


def _record_validation(
    paths: RuntimePaths,
    run: RunRecord,
    request_id: str,
    candidate: dict[str, Any],
    reason: str | None,
    claim_ids: tuple[str, ...],
    read: _PageRead | None,
    selection: ModelInputSelection | None = None,
) -> None:
    """One row per candidate on the run's search record, as for Tavily and Exa, with the
    request that read its page again and the original kept, when its page was read.

    With the gap's ``selection`` (a gap's answer, not a backtrack's), a candidate whose
    claims leave the model input incomplete is not model usable, as a searched page is not.
    """
    from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
    from pring_cycle.search_evidence import INCOMPLETE_MODEL_INPUT

    if reason is None and selection is not None and not selection.complete:
        reason = INCOMPLETE_MODEL_INPUT
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
            "selected_claim_ids_json, missing_members_json, claim_ids_json, parser_version, "
            "download_request_id, fetched_url, raw_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "candidate-validation-" + uuid.uuid4().hex,
                run.run_id,
                request_id,
                candidate["url"],
                "not_model_usable" if reason else "model_usable",
                reason,
                utc_now().isoformat(),
                json.dumps(gap_ids),
                json.dumps(list(selection.selected_claim_ids) if selection else []),
                json.dumps(list(selection.missing_members)) if selection else None,
                json.dumps(list(claim_ids)),
                AI_PARSER_VERSION,
                read.request_id if read else None,
                candidate["url"] if read and read.page else None,
                read.page.receipt.raw_hash if read and read.page else None,
            ),
        )
