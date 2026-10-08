from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import SourceFailed, response_retention_deadline
from pring_cycle.batches import code_version
from pring_cycle.catalog import MetricDefinition, metric_definition
from pring_cycle.catalog_registry import require_registered_manifest
from pring_cycle.models import ModelRepository
from pring_cycle.official_listing import LISTING_NOT_COVERED, ListingNotCovered
from pring_cycle.retrieval import RUN_SEARCH_LIMITS, RetrievalAdapterResponse
from pring_cycle.same_definition import family_identity
from pring_cycle.storage import database_connection
from pring_cycle.tushare_quota import TushareCallNotAttempted

if TYPE_CHECKING:
    from pring_cycle.runs import RunRecord


class RetrievalBudgetBlocked(ValueError):
    def __init__(self, classification: str, *, cache_hit: bool = False) -> None:
        super().__init__(classification)
        self.cache_hit = cache_hit


def utc_now() -> datetime:
    return datetime.now(UTC)


LIMITS = RUN_SEARCH_LIMITS
# A spent plan quota: the provider is not called again until the quota renews.
QUOTA_STATUSES = frozenset({402, 432, 433})


@dataclass(frozen=True)
class _RequestDecision:
    gaps: list[sqlite3.Row]
    event_keys: set[str]
    budget: dict[str, int]
    run_attempt: int
    blocked: str | None
    cache_hit: bool
    next_eligible: datetime | None
    reused_request_id: str | None
    reused_event_keys: set[str]


class RetrievalLedger:
    """Persistent gap identity and physical request accounting for a run."""

    def __init__(self, database: Path, *, scope_run: RunRecord | None = None) -> None:
        self.database = database
        self.scope_run = scope_run

    def bind_run(self, run: RunRecord, definition_version: str) -> None:
        scope = run.retrieval_scope
        if scope is None:
            raise ValueError("retrieval_scope_required")
        manifest = ModelRepository(self.database).manifest(run.model_version_id)
        if manifest["metric_catalog_version"] != definition_version:
            raise ValueError("retrieval_catalog_model_mismatch")
        require_registered_manifest(self.database, manifest)
        with self._connect() as connection:
            for metric_id in scope.metric_ids:
                definition = metric_definition(
                    metric_id, definition_version=definition_version, database_path=self.database
                )
                event_key = _event_key(definition, scope.period, database_path=self.database)
                identity = {
                    "model_version_id": run.model_version_id,
                    "definition_version": definition_version,
                    "metric_id": metric_id,
                    "period": scope.period,
                    "dimensions": {dimension: "*" for dimension in definition.dimensions},
                    "target_business_date": run.target_business_date,
                    "as_of": run.system_as_of.astimezone(UTC).isoformat(),
                }
                encoded = json.dumps(
                    identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                gap_id = "gap-" + hashlib.sha256(encoded.encode()).hexdigest()
                connection.execute(
                    "INSERT OR IGNORE INTO retrieval_gap VALUES (?, ?, ?)",
                    (gap_id, encoded, event_key),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO retrieval_run_gap VALUES (?, ?)", (run.run_id, gap_id)
                )

    def reserve(
        self,
        run_id: str,
        channel: str,
        release_event_id: str,
        query: str = "",
        *,
        domains: tuple[str, ...] = (),
    ) -> str:
        request_id = "retrieval-request-" + uuid4().hex
        now = utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            decision = self._decision(connection, run_id, channel, release_event_id, query, now)
            logical_id = hashlib.sha256(
                json.dumps([channel, sorted(decision.event_keys), query]).encode()
            ).hexdigest()
            connection.execute(
                "UPDATE parent_run SET consumed_budget_json=? WHERE run_id=?",
                (json.dumps(decision.budget), run_id),
            )
            connection.execute(
                """INSERT INTO retrieval_query(query_id, logical_query_id, run_id, channel,
                   query_text, attempted_at, physical_request_id, classification,
                   next_eligible_at, cache_hit, reused_request_id, domains_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "retrieval-query-" + uuid4().hex,
                    logical_id,
                    run_id,
                    channel,
                    query,
                    now.isoformat(),
                    None if decision.blocked else request_id,
                    decision.blocked,
                    decision.next_eligible.isoformat() if decision.next_eligible else None,
                    int(decision.cache_hit),
                    decision.reused_request_id if decision.blocked else None,
                    json.dumps(list(domains)),
                ),
            )
            if decision.blocked and decision.reused_request_id:
                connection.executemany(
                    "INSERT OR IGNORE INTO retrieval_request_gap VALUES (?, ?)",
                    [
                        (decision.reused_request_id, item["gap_id"])
                        for item in decision.gaps
                        if item["event_key"] in decision.reused_event_keys
                    ],
                )
            if not decision.blocked:
                connection.execute(
                    """INSERT INTO retrieval_physical_request(request_id, run_id, channel,
                       release_event_id, state, started_at, run_attempt, provider_key)
                       VALUES (?, ?, ?, ?, 'reserved', ?, ?, ?)""",
                    (
                        request_id,
                        run_id,
                        channel,
                        release_event_id,
                        now.isoformat(),
                        decision.run_attempt,
                        _provider_key(channel, query),
                    ),
                )
                connection.executemany(
                    "INSERT INTO retrieval_request_gap VALUES (?, ?)",
                    [(request_id, item[0]) for item in decision.gaps],
                )
                connection.executemany(
                    "INSERT INTO retrieval_request_event VALUES (?, ?)",
                    [(request_id, key) for key in decision.event_keys],
                )
                if channel in LIMITS:
                    decision.budget[channel] = int(decision.budget.get(channel, 0)) + 1
                connection.execute(
                    "UPDATE parent_run SET consumed_budget_json=? WHERE run_id=?",
                    (json.dumps(decision.budget), run_id),
                )
        if decision.blocked:
            raise RetrievalBudgetBlocked(decision.blocked, cache_hit=decision.cache_hit)
        return request_id

    def _decision(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        channel: str,
        release_event_id: str,
        query: str,
        now: datetime,
    ) -> _RequestDecision:
        blocked = None
        cache_hit = False
        quota_spent = False
        next_eligible = None
        reused_request_id = None
        reused_event_keys: set[str] = set()
        gaps = connection.execute(
            "SELECT gap_id, event_key, identity_json FROM retrieval_run_gap "
            "JOIN retrieval_gap USING(gap_id) WHERE run_id=?",
            (run_id,),
        ).fetchall()
        if self.scope_run is not None:
            scope = self.scope_run.retrieval_scope
            if scope is None or self.scope_run.run_id != run_id:
                raise ValueError("retrieval_scope_identity_mismatch")
            gaps = [
                row
                for row in gaps
                if (
                    (identity := json.loads(row["identity_json"]))["metric_id"] in scope.metric_ids
                    and identity["period"] == scope.period
                    and identity["as_of"] == self.scope_run.system_as_of.astimezone(UTC).isoformat()
                )
            ]
        if not gaps:
            raise ValueError("retrieval_gaps_not_bound")
        parent = connection.execute(
            "SELECT consumed_budget_json, command_type, status, priority, period, metric_ids_json, "
            "(SELECT COUNT(*) FROM run_attempt a WHERE a.run_id=parent_run.run_id) "
            "AS attempt_count FROM parent_run "
            "LEFT JOIN run_retrieval_scope USING(run_id) WHERE run_id=?",
            (run_id,),
        ).fetchone()
        row = dict(parent)
        if self.scope_run is not None and self.scope_run.retrieval_scope is not None:
            row.update(
                priority=self.scope_run.retrieval_scope.priority,
                period=self.scope_run.retrieval_scope.period,
                metric_ids_json=json.dumps(self.scope_run.retrieval_scope.metric_ids),
            )
        budget = json.loads(row["consumed_budget_json"])
        all_legacy = _legacy_requests(connection)
        for provider in LIMITS:
            owned_count = connection.execute(
                "SELECT COUNT(*) FROM retrieval_physical_request WHERE run_id=? AND channel=?",
                (run_id, provider),
            ).fetchone()[0]
            legacy_count = sum(
                item["run_id"] == run_id and item["channel"] == provider for item in all_legacy
            )
            budget[provider] = max(budget.get(provider, 0), owned_count + legacy_count)
        previous = connection.execute(
            "SELECT p.*, q.query_text FROM retrieval_physical_request p "
            "JOIN retrieval_query q ON q.physical_request_id=p.request_id "
            "WHERE p.channel=? AND p.provider_key=?",
            (channel, _provider_key(channel, query)),
        ).fetchall()
        # There is no daily cap. Within a run, AI WebSearch is called at most once per gap,
        # and no channel repeats a request whose completion is unknown (it may have been
        # answered and charged); a completed one is held back only by its negative cache.
        this_run = [
            item
            for item in previous
            if item["run_id"] == run_id
            and (channel == "ai_websearch" or item["state"] == "unknown_completion")
        ]
        event_keys = {item["event_key"] for item in gaps}
        legacy_requests = [item for item in all_legacy if item["run_id"] == run_id]
        same_attempt = [
            item
            for item in previous
            if item["run_id"] == run_id
            and item["run_attempt"] == row["attempt_count"]
            and (channel not in {"official", "tushare"} or item["query_text"] == query)
        ]
        for cached in connection.execute("SELECT * FROM retrieval_negative_cache"):
            if datetime.fromisoformat(cached["expires_at"]) <= now:
                continue
            cached_keys: set[str] = set()
            for prior_scope in connection.execute(
                "SELECT s.*, m.manifest_json FROM run_retrieval_scope s "
                "JOIN parent_run p USING(run_id) JOIN model_version m USING(model_version_id) "
                "WHERE s.release_event_id=?",
                (cached["release_event_id"],),
            ):
                cached_keys.update(
                    _legacy_event_keys(
                        prior_scope, cached["metric_ids_json"], database_path=self.database
                    )
                )
            exact_legacy_identity = cached["release_event_id"] == release_event_id and set(
                json.loads(cached["metric_ids_json"])
            ) & set(json.loads(row["metric_ids_json"]))
            if cached_keys & event_keys or exact_legacy_identity:
                cache_hit = True
                next_eligible = max(
                    next_eligible or now, datetime.fromisoformat(cached["expires_at"])
                )
        for item in previous:
            if (
                channel in {"official", "tushare"}
                and item in same_attempt
                and len(same_attempt) < 3
                and item["classification"] == "transient_transport_error"
            ):
                continue
            expiry = item["cache_expires_at"]
            if expiry is None or datetime.fromisoformat(expiry) <= now:
                continue
            prior_keys = {
                entry[0]
                for entry in connection.execute(
                    "SELECT event_key FROM retrieval_request_event WHERE request_id=?",
                    (item["request_id"],),
                )
            }
            same_source = channel not in {"official", "tushare"} or item["query_text"] == query
            # An official 403 holds back its own page, whichever gap asks for it, and no
            # other page: also one stored with the host-wide flag this used to set.
            official_403 = channel == "official" and item["http_status"] == 403
            forbidden_page = official_403 and item["query_text"] == query
            host_wide = bool(item["provider_cache"]) and not official_403
            if host_wide and item["http_status"] in QUOTA_STATUSES:
                quota_spent = True
            same_gap = bool(prior_keys & event_keys) and same_source
            if host_wide or forbidden_page or same_gap:
                cache_hit = True
                next_eligible = max(next_eligible or now, datetime.fromisoformat(expiry))
                if prior_keys & event_keys:
                    reused_request_id = item["request_id"]
                    reused_event_keys = prior_keys
        event_counts = dict.fromkeys(event_keys, 0)
        for item in this_run:
            prior_keys = {
                entry[0]
                for entry in connection.execute(
                    "SELECT event_key FROM retrieval_request_event WHERE request_id=?",
                    (item["request_id"],),
                )
            }
            if prior_keys & event_keys:
                for key in prior_keys & event_keys:
                    event_counts[key] += 1
                reused_request_id = item["request_id"]
                reused_event_keys = prior_keys
        for prior in legacy_requests:
            if prior["channel"] == channel:
                for key in _legacy_event_keys(prior, database_path=self.database) & event_keys:
                    event_counts[key] += 1
        # An explicit manual deep search may repeat Tavily/Exa; AI stays once per gap.
        repeat_allowed = row["command_type"] == "manual_deep_search" and channel != "ai_websearch"
        if (
            channel in LIMITS
            and not repeat_allowed
            and any(count >= 1 for count in event_counts.values())
        ):
            blocked = "event_run_limit"
        run_limit = LIMITS.get(channel)
        if (
            run_limit is not None
            and row["command_type"] != "manual_deep_search"
            and budget.get(channel, 0) >= run_limit
        ):
            blocked = "run_limit"
        if blocked is None and quota_spent:
            # Tavily's monthly quota is spent: the cascade lets Exa stand in.
            blocked = "quota_exhausted"
        if blocked is None and cache_hit:
            blocked = "negative_cache_active"
        if blocked in {"run_limit", "event_run_limit"}:
            next_eligible = None
        if row["status"] in {"cancelled", "interrupted", "action_required", "failed", "completed"}:
            blocked = "run_not_running"
            next_eligible = None
        return _RequestDecision(
            gaps,
            event_keys,
            budget,
            int(row["attempt_count"]),
            blocked,
            cache_hit,
            next_eligible,
            reused_request_id,
            reused_event_keys,
        )

    def trace_acquisition(
        self,
        run_id: str,
        channel: str,
        release_event_id: str,
        query: str,
        operation: Callable[[Callable[[str], None]], str | RetrievalAdapterResponse],
        *,
        defer_completion: bool = False,
    ) -> RetrievalAdapterResponse:
        request_id: str | None = None
        http_status = None
        response_headers = None

        def started(acquisition_id: str) -> None:
            nonlocal request_id
            with self._connect() as connection:
                acquisition = connection.execute(
                    "SELECT parameters_json FROM acquisition_request WHERE acquisition_id=?",
                    (acquisition_id,),
                ).fetchone()
                previous = (
                    connection.execute(
                        "SELECT a.state, a.structure_check FROM retrieval_physical_request p "
                        "JOIN acquisition_request a USING(acquisition_id) WHERE p.request_id=?",
                        (request_id,),
                    ).fetchone()
                    if request_id is not None
                    else None
                )
            if request_id is not None:
                # A candidate passed over for the next of the day's notices (run findings 04)
                # is done with, like one that validated.
                skipped = (
                    previous is not None
                    and previous["state"] == "failed"
                    and previous["structure_check"] == "skipped"
                )
                if previous is None or (previous["state"] != "validated" and not skipped):
                    raise ValueError("retrieval_previous_acquisition_not_validated")
                self.complete(
                    request_id,
                    outcome="candidate_source",
                    classification=(
                        "intermediate_candidate_skipped"
                        if skipped
                        else "intermediate_acquisition_validated"
                    ),
                )
                request_id = None
            parameters = json.loads(acquisition["parameters_json"]) if acquisition else {}
            request_query = parameters.get("source_url", query) if channel == "official" else query
            request_id = self.reserve(run_id, channel, release_event_id, request_query)
            self.attach_acquisition(request_id, acquisition_id)

        try:
            value = operation(started)
            result = (
                RetrievalAdapterResponse("verified", evidence=value)
                if isinstance(value, str)
                else value
            )
        except RetrievalBudgetBlocked as error:
            return RetrievalAdapterResponse(
                "not_attempted", classification=str(error), cache_hit=error.cache_hit
            )
        except TushareCallNotAttempted as error:
            # Held back for TuShare's day (ticket 31): nothing sent, nothing to retry.
            return RetrievalAdapterResponse("not_attempted", classification=error.condition)
        except HTTPError as error:
            http_status = error.code
            response_headers = dict(error.headers)
            result = RetrievalAdapterResponse(
                "failed", classification=http_failure_classification(error.code)
            )
        except SourceFailed as error:
            # The source answered with a failure (ticket 18). What the adapter read its code
            # as decides the backoff (ticket 22: TuShare's rate limit); else an HTTP status
            # says how, kept for its backoff as an HTTP error's is; any other code is no
            # transport fault to retry at once.
            code = error.external_code
            classification: str | None
            if code is not None and code.isdigit() and 100 <= int(code) < 600:
                http_status = int(code)
            if error.classification == "rate_limited":
                classification = "rate_limited"
            elif error.classification == "forbidden":
                classification = "forbidden_unknown"
            elif http_status is not None:
                classification = http_failure_classification(http_status)
            else:
                classification = "semantic_validation_failed"
            result = RetrievalAdapterResponse("failed", classification=classification)
        except OSError:
            result = RetrievalAdapterResponse("failed", classification="transient_transport_error")
        except ListingNotCovered as error:
            # The listing read did not reach the period: no word on its release (lookback L05).
            result = RetrievalAdapterResponse(
                "failed", classification=f"{LISTING_NOT_COVERED}_{error.stopped}"
            )
        except (TypeError, ValueError):
            result = RetrievalAdapterResponse("failed", classification="semantic_validation_failed")
        if request_id is not None and not (
            defer_completion and result.status == "candidate_source"
        ):
            self.complete(
                request_id,
                outcome=result.status,
                classification=result.classification,
                status=http_status,
                headers=response_headers,
            )
        return replace(result, physical_request_id=request_id)

    def interrupt(self, run_id: str) -> None:
        with self._connect() as connection:
            interrupt_retrieval_requests(connection, run_id)

    def search_checkpoint(self, run_id: str, channel: str, query: str) -> tuple[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT p.request_id, p.acquisition_id FROM retrieval_query q "
                "JOIN retrieval_physical_request p ON p.request_id=q.physical_request_id "
                "JOIN acquisition_request a ON a.acquisition_id=p.acquisition_id "
                "WHERE q.run_id=? AND q.channel=? AND q.query_text=? AND a.state='validated' "
                "AND p.state IN ('completed', 'unknown_completion') "
                "AND p.run_attempt < (SELECT COUNT(*) FROM run_attempt WHERE run_id=q.run_id) "
                "ORDER BY q.rowid DESC LIMIT 1",
                (run_id, channel, query),
            ).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def candidate_resume_pending(self, request_id: str, candidates: tuple[str, ...]) -> bool:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT candidate_url, outcome FROM retrieval_candidate_validation "
                "WHERE search_request_id=? ORDER BY rowid",
                (request_id,),
            ).fetchall()
        latest = {str(row[0]): str(row[1]) for row in rows}
        # Preserve historical unknown receipts, but only unfinished work from
        # the latest validation of each raw-response candidate is resumable.
        return any(
            latest.get(url) in {None, "checking", "unknown_completion"} for url in candidates
        )

    def record_search_reuse(self, run_id: str, request_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO retrieval_query(query_id, logical_query_id, run_id, channel, "
                "query_text, attempted_at, classification, cache_hit, reused_request_id, "
                "domains_json) SELECT ?, logical_query_id, ?, channel, query_text, ?, "
                "'verified_search_checkpoint', "
                "1, ?, domains_json FROM retrieval_query WHERE physical_request_id=? LIMIT 1",
                (
                    "retrieval-query-" + uuid4().hex,
                    run_id,
                    utc_now().isoformat(),
                    request_id,
                    request_id,
                ),
            )

    def consumption(self, run_id: str) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT channel, COUNT(*) FROM retrieval_physical_request "
                "WHERE run_id=? GROUP BY channel",
                (run_id,),
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def attach_acquisition(self, request_id: str, acquisition_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE retrieval_physical_request SET acquisition_id=? "
                "WHERE request_id=? AND state='reserved'",
                (acquisition_id, request_id),
            )

    def complete(
        self,
        request_id: str,
        *,
        outcome: str,
        classification: str | None,
        status: int | None = None,
        headers: dict[str, str] | None = None,
        cost: dict[str, object] | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        now = utc_now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT s.priority, p.channel, p.run_id, p.release_event_id, q.query_text "
                "FROM retrieval_physical_request p LEFT JOIN run_retrieval_scope s USING(run_id) "
                "JOIN retrieval_query q ON q.physical_request_id=p.request_id WHERE p.request_id=?",
                (request_id,),
            ).fetchone()
            expiry = _cache_expiry(
                now,
                outcome,
                classification,
                self.scope_run.retrieval_scope.priority
                if self.scope_run is not None and self.scope_run.retrieval_scope is not None
                else row["priority"],
                status,
                headers or {},
                channel=row["channel"],
            )
            connection.execute(
                """UPDATE retrieval_physical_request SET state='completed', completed_at=?,
                   outcome=?, classification=?, http_status=?, cache_expires_at=?, provider_cache=?,
                   cost_json=?, provider_request_id=?, response_headers_json=?
                   WHERE request_id=? AND state='reserved'""",
                (
                    now.isoformat(),
                    outcome,
                    classification,
                    status,
                    expiry.isoformat() if expiry else None,
                    # An official page's 403 speaks for that page, not its whole site: an
                    # nginx 403 on one PBC column once held back every PBC page for a day.
                    int(
                        status in {401, 402, 429, 432, 433}
                        or (status == 403 and row["channel"] != "official")
                    ),
                    json.dumps(cost),
                    provider_request_id,
                    json.dumps(
                        {
                            key.lower(): value
                            for key, value in (headers or {}).items()
                            if key.lower() in {"retry-after", "date", "content-type"}
                        }
                    ),
                    request_id,
                ),
            )
            decision = self._decision(
                connection,
                row["run_id"],
                row["channel"],
                row["release_event_id"],
                row["query_text"],
                now,
            )
            next_eligible = decision.next_eligible if decision.blocked else now
            connection.execute(
                "UPDATE retrieval_query SET classification=?, next_eligible_at=? "
                "WHERE physical_request_id=?",
                (classification, next_eligible.isoformat() if next_eligible else None, request_id),
            )

    def expire_responses(self, artifacts: Path) -> None:
        """Remove only expired search bodies with no other registered owner."""
        with self._connect() as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='retrieval_physical_request'"
            ).fetchone():
                return
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("""SELECT p.acquisition_id, a.raw_hash, a.provider,
                a.api_name, a.received_at
                FROM retrieval_physical_request p JOIN acquisition_request a USING(acquisition_id)
                WHERE p.channel IN ('tavily', 'exa') AND a.raw_hash IS NOT NULL""").fetchall()
            expired = [
                row
                for row in rows
                if (expiry := _response_expiry(row)) is not None and expiry <= utc_now()
            ]
            expired_references = {f"{row['acquisition_id']}:raw" for row in expired}
            for digest in {row["raw_hash"] for row in expired}:
                references = {
                    row[0]
                    for row in connection.execute(
                        "SELECT source_reference FROM artifact_reference WHERE content_hash=?",
                        (digest,),
                    )
                }
                if not references or not references <= expired_references:
                    continue
                if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                    raise ValueError("invalid_artifact_hash")
                path = artifacts / digest[:2] / digest
                if path.is_symlink() or not path.resolve().is_relative_to(artifacts.resolve()):
                    raise ValueError("artifact_path_outside_root")
                path.unlink(missing_ok=True)

    def for_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='retrieval_gap'"
                ).fetchone()
                is None
            ):
                return None
            gap_rows = connection.execute(
                """SELECT gap_id, identity_json, event_key FROM retrieval_gap
                   JOIN retrieval_run_gap USING(gap_id)
                   WHERE run_id=? ORDER BY gap_id""",
                (run_id,),
            ).fetchall()
            if not gap_rows:
                return None
            requests = []
            for row in connection.execute(
                "SELECT p.*, a.raw_hash, a.provider, a.api_name, a.received_at "
                "FROM retrieval_physical_request p LEFT JOIN "
                "acquisition_request a USING(acquisition_id) WHERE run_id=? OR request_id IN "
                "(SELECT reused_request_id FROM retrieval_query WHERE run_id=?) ORDER BY p.rowid",
                (run_id, run_id),
            ):
                gaps = [
                    item[0]
                    for item in connection.execute(
                        "SELECT gap_id FROM retrieval_request_gap WHERE request_id=? "
                        "ORDER BY gap_id",
                        (row["request_id"],),
                    )
                ]
                request = dict(row)
                cost = json.loads(request.pop("cost_json") or "null")
                response_headers = json.loads(request.pop("response_headers_json") or "{}")
                expiry = _response_expiry(row)
                expired = expiry is not None and expiry <= utc_now()
                requests.append(
                    {
                        **request,
                        "cost": cost,
                        "response_headers": response_headers,
                        "raw_expires_at": expiry.isoformat() if expiry is not None else None,
                        "billed_cost": None,
                        "gap_ids": gaps,
                        "charged_to_run": row["run_id"] == run_id,
                        "raw_status": "expired"
                        if expired
                        else "retained"
                        if row["raw_hash"]
                        else "unavailable",
                    }
                )
            return {
                "gaps": [
                    {
                        "gap_id": row["gap_id"],
                        **json.loads(row["identity_json"]),
                        "release_event_key": row["event_key"],
                        "release_event_kind": "budget_family_period",
                    }
                    for row in gap_rows
                ],
                "requests": requests,
                "candidate_validations": self._candidate_validations(connection, run_id),
                "queries": [
                    {**dict(row), "domains": json.loads(row["domains_json"])}
                    for row in connection.execute(
                        "SELECT * FROM retrieval_query WHERE run_id=? ORDER BY rowid", (run_id,)
                    )
                ],
            }

    def _candidate_validations(
        self, connection: sqlite3.Connection, run_id: str
    ) -> list[dict[str, Any]]:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='retrieval_candidate_validation'"
        ).fetchone():
            return []
        results = []
        for row in connection.execute(
            "SELECT * FROM retrieval_candidate_validation WHERE run_id=? ORDER BY rowid", (run_id,)
        ):
            item = dict(row)
            for field in (
                "gap_ids",
                "claim_ids",
                "selected_claim_ids",
                "missing_members",
            ):
                item[field] = json.loads(item.pop(field + "_json") or "[]")
            results.append(item)
        return results

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self.database) as connection:
            connection.row_factory = sqlite3.Row
            yield connection


RETRIEVAL_LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS retrieval_gap (
    gap_id TEXT PRIMARY KEY, identity_json TEXT NOT NULL, event_key TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS retrieval_run_gap (
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    gap_id TEXT NOT NULL REFERENCES retrieval_gap(gap_id),
    PRIMARY KEY(run_id, gap_id)
);
CREATE TABLE IF NOT EXISTS retrieval_physical_request (
    request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    channel TEXT NOT NULL, provider_key TEXT NOT NULL,
    release_event_id TEXT NOT NULL, state TEXT NOT NULL,
    started_at TEXT NOT NULL, completed_at TEXT, run_attempt INTEGER NOT NULL,
    acquisition_id TEXT REFERENCES acquisition_request(acquisition_id),
    outcome TEXT, classification TEXT, http_status INTEGER,
    cache_expires_at TEXT, provider_cache INTEGER NOT NULL DEFAULT 0,
    cost_json TEXT, provider_request_id TEXT, response_headers_json TEXT
);
CREATE TABLE IF NOT EXISTS retrieval_request_gap (
    request_id TEXT NOT NULL REFERENCES retrieval_physical_request(request_id),
    gap_id TEXT NOT NULL REFERENCES retrieval_gap(gap_id), PRIMARY KEY(request_id, gap_id)
);
CREATE TABLE IF NOT EXISTS retrieval_request_event (
    request_id TEXT NOT NULL REFERENCES retrieval_physical_request(request_id),
    event_key TEXT NOT NULL, PRIMARY KEY(request_id, event_key)
);
CREATE TABLE IF NOT EXISTS retrieval_query (
    query_id TEXT PRIMARY KEY, logical_query_id TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id), channel TEXT NOT NULL,
    query_text TEXT NOT NULL, attempted_at TEXT NOT NULL, physical_request_id TEXT,
    classification TEXT, next_eligible_at TEXT, cache_hit INTEGER NOT NULL DEFAULT 0,
    reused_request_id TEXT REFERENCES retrieval_physical_request(request_id),
    domains_json TEXT NOT NULL DEFAULT '[]'
);
"""


def _cache_expiry(
    now: datetime,
    outcome: str,
    classification: str | None,
    priority: str,
    status: int | None,
    headers: dict[str, str],
    *,
    channel: str = "",
) -> datetime | None:
    headers = {key.lower(): value for key, value in headers.items()}
    if status == 429:
        retry_after = headers.get("retry-after", "")
        try:
            seconds = int(retry_after)
            if seconds >= 0:
                return now + timedelta(seconds=seconds)
        except (ValueError, OverflowError):
            pass
        try:
            parsed = parsedate_to_datetime(retry_after)
            if parsed.tzinfo is not None and parsed >= now:
                return parsed
        except (ValueError, TypeError, OverflowError):
            pass
        return now + timedelta(minutes=60)
    if status in QUOTA_STATUSES and channel == "tavily":
        # Tavily's plan quota is monthly; Exa stands in until it renews (ticket 20).
        local = now.astimezone(ZoneInfo("Asia/Shanghai"))
        following = local.replace(day=1) + timedelta(days=32)
        return following.replace(day=1, hour=0, minute=5, second=0, microsecond=0)
    if status in {401, 402, 403, 432, 433} or classification == "forbidden_unknown":
        # A missing permission, by status or as the source's own code says, waits until
        # 00:05 the next day in Shanghai.
        return now.astimezone(ZoneInfo("Asia/Shanghai")).replace(
            hour=0, minute=5, second=0, microsecond=0
        ) + timedelta(days=1)
    if classification == "rate_limited":
        # A rate limit the source said in its own code, with no Retry-After (ticket 22).
        return now + timedelta(minutes=60)
    if classification == "transient_transport_error":
        return now + timedelta(minutes=15)
    if outcome == "not_found" or classification == "semantic_validation_failed":
        return now + timedelta(hours=24 if priority == "P2" else 6)
    return None


def interrupt_retrieval_requests(connection: sqlite3.Connection, run_id: str) -> None:
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='retrieval_physical_request'"
    ).fetchone():
        connection.execute(
            "UPDATE retrieval_physical_request SET state='unknown_completion' "
            "WHERE run_id=? AND state='reserved'",
            (run_id,),
        )
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='retrieval_candidate_validation'"
    ).fetchone():
        connection.execute(
            "UPDATE retrieval_candidate_validation SET outcome='unknown_completion', "
            "reason='worker_process_interrupted' WHERE run_id=? AND outcome='checking'",
            (run_id,),
        )


def http_failure_classification(status: int) -> str | None:
    if status == 200:
        return None
    if status == 401:
        return "authentication_failed"
    if status == 403:
        return "forbidden_unknown"
    if status in {402, 432, 433}:
        return "quota_exhausted"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "transient_transport_error"
    return "semantic_validation_failed"


def _response_expiry(row: sqlite3.Row) -> datetime | None:
    return response_retention_deadline(
        row["provider"],
        row["api_name"],
        datetime.fromisoformat(row["received_at"]) if row["received_at"] else None,
    )


def _legacy_requests(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    # Old retry rows are conservative reservations, not proof of exact HTTP or billing.
    rows = connection.execute("""SELECT a.run_id, a.channel, a.occurred_at,
        s.period, s.metric_ids_json, m.manifest_json
        FROM run_retrieval_attempt a JOIN run_retrieval_scope s USING(run_id)
        JOIN parent_run p USING(run_id) JOIN model_version m USING(model_version_id)
        WHERE a.physical_request_id IS NULL AND a.channel IN ('tavily', 'exa', 'ai_websearch')
        AND (a.budget_charged=1
             OR a.outcome IN ('not_found', 'candidate_source', 'verified', 'failed'))
        """).fetchall()
    return list(rows)


def _legacy_event_keys(
    row: sqlite3.Row, metric_ids_json: str | None = None, *, database_path: Path
) -> set[str]:
    manifest = json.loads(row["manifest_json"])
    return {
        _event_key(
            metric_definition(
                metric_id,
                definition_version=manifest["metric_catalog_version"],
                database_path=database_path,
            ),
            row["period"],
            database_path=database_path,
        )
        for metric_id in json.loads(metric_ids_json or row["metric_ids_json"])
    }


def _event_key(definition: MetricDefinition, period: str, *, database_path: Path) -> str:
    """A gap's release event, under the contract it is fetched and checked against.

    A negative cache holds back the same event under the same contract only: what the family's
    metrics mean (not the catalog's version label, ADR-0036) and the code that parses and
    checks the event, shared by every metric of its family. A repair lets the next run try
    again at once (gap sources #05); older keys name no contract and match none.
    """
    meaning = family_identity(
        database_path, definition.definition_version, definition.release_event_family
    )
    contract = hashlib.sha256(json.dumps([meaning, code_version()]).encode()).hexdigest()[:16]
    return json.dumps([definition.release_event_family, period, contract])


def _provider_key(channel: str, query: str) -> str:
    return (
        (urlsplit(query).hostname or "unknown_official_source")
        if channel == "official"
        else channel
    )
