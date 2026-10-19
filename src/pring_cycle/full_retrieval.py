from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from pring_cycle import credit_impulse, lookback
from pring_cycle.acquisition import REFERENCED, own_acquisitions
from pring_cycle.basket import BASE_DATE as BASKET_BASE_DATE
from pring_cycle.basket import BASKET_METRICS
from pring_cycle.catalog import MetricDefinition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.freshness import (
    DERIVED_INPUTS,
    FRESHNESS_REGISTRY,
    latest_due_period,
    latest_released_period,
)
from pring_cycle.full_run_requirements import (
    formula_requirements,
    input_coverage_complete,
    required_calendar,
    run_lookback,
)
from pring_cycle.metric_contracts import evidence_frequency, required_dimension_members
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    ListingScan,
    official_family_for_metrics,
    read_listing_page,
    run_listings,
)
from pring_cycle.official_listing import (
    LISTING_NOT_COVERED,
    is_release_listing,
    period_last_day,
    reaches_back,
    release_listing,
)
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.retrieval import (
    RetrievalAdapterResponse,
    RetrievalBudget,
    RetrievalRequest,
    matches_retrieval_period,
    run_retrieval_cascade,
)
from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
from pring_cycle.retrieval_registry import is_searchable_gap
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository, member_key, member_keys
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector, select_retrieval_input
from pring_cycle.storage import database_connection
from pring_cycle.summary_cutoff import SummaryCutoff
from pring_cycle.trading_calendar import (
    SseCalendar,
    current_calendar,
    judging_calendar,
    use_run_calendar,
)

# A re-expansion of the plan, by its number: a newer period taken during the run moved its
# readings' t (go-live leftovers 03). Each asks only for what no earlier plan asked for, so a
# run's expansions end; the bound stops a source that kept delivering newer periods.
EXPANSION = "expansion:"
MAX_EXPANSIONS = 3


class FullRunRetrieval:
    """Persist the plan before calls, evaluate once, and link publication separately."""

    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths

    def retrieve(self, run: RunRecord, *, decided_at: datetime | None = None) -> None:
        """Plan the run's gaps, then retrieve them, re-expanding the plan while that takes a
        newer period than it read.

        ``decided_at`` is when the Worker decided what its direct fetch covers; the first
        plan reads the credit lookback as of then, so it asks for nothing that fetch left
        out (ticket 24).
        """
        plan = read_full_retrieval_plan(self.paths.database, run.run_id)
        if plan["final"] is not None:
            return
        if plan["initial"] is None:
            initial = self._plan(run, decided_at=decided_at)
            self._record(run.run_id, "initial", initial)
            self._pull_news(run)
        else:
            initial = plan["initial"]
        if plan.get("event_backtrack") is None:
            self._backtrack_events(run)
        version = str(initial["definition_version"])
        window = initial.get("daily_window", {}).get("dates", ())
        # A plan recorded before an interruption: its window judges the rest of the run.
        self._use_judging_calendar(run, window)
        asked: dict[tuple[str, str], set[str] | None] = {}
        scopes = initial["scopes"]
        for number in range(1, MAX_EXPANSIONS + 2):
            for document in scopes:
                _mark_asked(asked, document)
            reached = self._retrieve_scopes(run, scopes, version)
            if number <= len(plan["expansions"]):
                # Recorded before an interruption: retrieved again as planned.
                scopes = plan["expansions"][number - 1]["scopes"]
                continue
            if not reached or number > MAX_EXPANSIONS:
                return
            # A newer period taken moves its readings' t (ADR-0035's t-12 and t-13 with
            # it): what they add is asked for now, not first listed as a gap at the frozen
            # cutoff (go-live leftovers 03).
            scopes = [
                document
                for document in self._plan(run, decided_at=decided_at)["scopes"]
                if not _asked_for(asked, document)
            ]
            self._use_judging_calendar(run, window)
            if not scopes:
                return
            self._record(
                run.run_id,
                f"{EXPANSION}{number}",
                {"scopes": scopes, "created_at": utc_now().isoformat()},
            )

    def _retrieve_scopes(self, run: RunRecord, scopes: list[dict[str, Any]], version: str) -> bool:
        """Retrieve the planned scopes; whether any passed the release gate, so may have
        taken something."""
        from pring_cycle.worker import _production_retrieval_adapters

        runs = RunRepository(self.paths.database)
        reached = False
        self._read_listings(run, scopes, version)
        for document in scopes:
            scope = _scope(document)
            scoped = replace(run, retrieval_scope=scope)
            release, discover_release = self._gate(run, scope, version)
            if release != "released" and not discover_release:
                # Recorded also when the plan foresaw it: the final plan and the gap list
                # say why each period went unrequested (lookback L01).
                runs.record_retrieval_attempt(
                    run.run_id,
                    release_event_id=scope.release_event_id,
                    channel="release_gate",
                    outcome="not_attempted",
                    classification=release,
                    latency_ms=0,
                    remaining_run_budget=None,
                    remaining_daily_budget=None,
                    budget_charged=False,
                    cache_hit=False,
                    manual_budget_exemption=False,
                    candidate_source=None,
                    occurred_at=utc_now(),
                )
                continue
            reached = True
            if runs.status(run.run_id) != "running":
                raise ValueError("full_retrieval_run_not_running")
            ledger = RetrievalLedger(self.paths.database, scope_run=scoped)
            ledger.bind_run(scoped, version)
            if select_retrieval_input(self.paths, scoped).complete:
                continue
            # The ledger charges the run's persistent budget; this one is not consumed.
            budget = RetrievalBudget()
            with own_acquisitions(
                self.paths.database,
                run.run_id,
                "gap_retrieval",
                metric_ids=scope.metric_ids,
                period=scope.period,
            ):
                adapters = _production_retrieval_adapters(
                    self.paths,
                    scope,
                    utc_now(),
                    definition_version=version,
                    run_id=run.run_id,
                    scope_run=scoped,
                )
                if discover_release:
                    # A configured official listing can establish the release fact. Until
                    # its dated original is validated, unknown publication cannot open search.
                    adapters = {key: value for key, value in adapters.items() if key == "official"}
                result = run_retrieval_cascade(
                    RetrievalRequest(
                        release_event_id=scope.release_event_id,
                        metric_ids=scope.metric_ids,
                        priority=scope.priority,
                        released=True,
                        persistent_accounting=True,
                        searchable=all(is_searchable_gap(m) for m in scope.metric_ids),
                    ),
                    adapters,
                    budget,
                )
            for attempt in result.attempts:
                runs.record_retrieval_attempt(
                    run.run_id,
                    release_event_id=scope.release_event_id,
                    channel=attempt.channel,
                    outcome=attempt.outcome,
                    classification=attempt.classification,
                    latency_ms=attempt.latency_ms,
                    remaining_run_budget=attempt.remaining_run_budget,
                    remaining_daily_budget=attempt.remaining_daily_budget,
                    budget_charged=attempt.budget_charged,
                    cache_hit=attempt.cache_hit,
                    manual_budget_exemption=False,
                    candidate_source=attempt.candidate_source,
                    occurred_at=utc_now(),
                    physical_request_id=attempt.physical_request_id,
                )
        return reached

    def _gate(self, run: RunRecord, scope: RetrievalScope, version: str) -> tuple[str, bool]:
        """The scope's release status, and whether only its official listing may establish
        it: an earlier session is not searched, but its listing is still read. So is a
        release its estimate does not yet make due, once a run, in case it came out early
        (worker gaps 02: the PBC's financial statistics come out days before the estimate)."""
        from pring_cycle.worker import EARLIER_SESSION, _retrieval_release_status

        # Publication is bounded to what the target day's summary could know of.
        now = utc_now()
        release = _retrieval_release_status(
            self.paths,
            scope,
            SummaryCutoff.decision_as_of(run, now),
            definition_version=version,
            public_as_of=SummaryCutoff.target(run, now),
            latest_only=True,
        )
        discover_release = release in {
            "awaiting_release",
            "unknown_release_configuration",
            EARLIER_SESSION,
        } and _has_release_listing(scope)
        return release, discover_release

    def _read_listings(self, run: RunRecord, scopes: list[dict[str, Any]], version: str) -> None:
        """Read the official listings the run's periods are looked up on, before any period
        is: a site's listings in turn, a page each, each until it reaches back past the
        earliest period still missing on it, ends, or the site's pages of the run are spent
        (lookback L05).

        So the pages are shared out among the listings, newest first: one listing's long way
        back does not spend the pages another needs. Each page is a request of the newest
        period it is read for, as the scope's own reads are.
        """
        wanted: dict[str, list[RetrievalScope]] = {}
        for document in scopes:
            scope = _scope(document)
            listing = _scope_listing(scope)
            if listing is None:
                continue
            release, discover_release = self._gate(run, scope, version)
            scoped = replace(run, retrieval_scope=scope)
            if (release == "released" or discover_release) and not select_retrieval_input(
                self.paths, scoped
            ).complete:
                wanted.setdefault(listing, []).append(scope)
        listings = run_listings(self.paths, run.run_id)

        def unread(listing: str) -> RetrievalScope | None:
            """The newest period the listing has not yet been read back past, if any."""
            days = listings.days(listing)
            return next(
                (
                    scope
                    for scope in sorted(
                        wanted[listing], key=lambda item: period_last_day(item.period), reverse=True
                    )
                    if not reaches_back(days, scope.period)
                ),
                None,
            )

        held: set[str] = set()
        while pending := {
            listing: needed
            for listing in wanted
            if listing not in listings.ended
            and listing not in held
            and (needed := unread(listing)) is not None
        }:
            # In turn: the listing with the fewest pages read next, of those the one read
            # least far back (a listing not read yet, or listing no dates, comes first).
            listing = min(
                pending,
                key=lambda item: (
                    listings.reads.get(item, 0),
                    -int(min(listings.days(item), default="99999999")),
                ),
            )
            read = listings.reads.get(listing, 0)
            self._read_listing_page(run, listing, pending[listing], listings, version)
            if listings.reads.get(listing, 0) == read and listing not in listings.ended:
                # No request went out (the retrieval ledger held it back): its scopes ask
                # for it themselves.
                held.add(listing)

    def _read_listing_page(
        self,
        run: RunRecord,
        listing: str,
        scope: RetrievalScope,
        listings: ListingScan,
        version: str,
    ) -> None:
        """One more page of the listing, a request of the period it is read for."""
        scoped = replace(run, retrieval_scope=scope)
        if RunRepository(self.paths.database).status(run.run_id) != "running":
            raise ValueError("full_retrieval_run_not_running")
        ledger = RetrievalLedger(self.paths.database, scope_run=scoped)
        ledger.bind_run(scoped, version)

        def read(started: Callable[[str], None]) -> RetrievalAdapterResponse:
            stopped = read_listing_page(
                self.paths,
                family=official_family_for_metrics(scope.metric_ids),
                listing_url=listing,
                period=scope.period,
                listings=listings,
                on_acquisition_started=started,
            )
            return RetrievalAdapterResponse(
                "candidate_source", classification=stopped or "listing_page_read"
            )

        with own_acquisitions(
            self.paths.database,
            run.run_id,
            "gap_retrieval",
            metric_ids=scope.metric_ids,
            period=scope.period,
        ):
            # A failed read is the page's: counted against its tries, it is read again in
            # turn, or the listing ends there.
            ledger.trace_acquisition(run.run_id, "official", scope.release_event_id, listing, read)

    def _pull_news(self, run: RunRecord) -> None:
        """One TuShare news pull for every gap of the run, before any gap is retried."""
        from pring_cycle.secrets import parse_data_source_secrets
        from pring_cycle.tushare_news import NEWS_EVENT_METRICS, fill_events_from_news, pull_news

        token = parse_data_source_secrets(self.paths.secrets).get("TUSHARE_TOKEN")
        if not token:
            return
        # Up to what the target day's summary may know of: the run's cutoff (ticket 06).
        end = SummaryCutoff.target(run, utc_now()).public_as_of
        with own_acquisitions(self.paths.database, run.run_id, "tushare_news"):
            pulled = pull_news(self.paths, run, token, end=end)
        rules = ContextProjectionRules.from_manifest(
            ModelRepository(self.paths.database).manifest(run.model_version_id)
        )
        events = tuple(
            d.metric_id for d in rules.metric_definitions if d.metric_id in NEWS_EVENT_METRICS
        )
        if events:
            stored = fill_events_from_news(
                self.paths,
                run,
                metric_ids=events,
                definition_version=rules.metric_catalog_version,
            )
            # A news pull cut short read only part of its window: that is not "none stated".
            unread = "none_stated" if pulled == "verified_candidate" else "news_unavailable"
            self._record(
                run.run_id,
                "event_monitoring",
                {
                    "news_pull": pulled,
                    "metrics": {m: "new_event" if stored else unread for m in events},
                    "claim_ids": list(stored),
                },
            )

    def _backtrack_events(self, run: RunRecord) -> None:
        """Trace back an RRR never held to its latest change (ADR-0028), once per run.

        The PBC's policy chronicles are read back from the target month; AI WebSearch is
        asked for the days after the newest issue, or for the latest change when the column
        cannot be read. A column read to its end without one is "none found", which is not a
        gap; only a search that did not finish is.
        """
        from pring_cycle.ai_websearch import discover_event
        from pring_cycle.official_context import backtrack_rrr_chronicle
        from pring_cycle.official_listing import RRR_CHRONICLE_LISTING

        rules = ContextProjectionRules.from_manifest(
            ModelRepository(self.paths.database).manifest(run.model_version_id)
        )
        definition = next(
            (d for d in rules.metric_definitions if d.metric_id == "CN_RRR_EVENT"), None
        )
        if definition is None or any(
            point.period_start <= run.target_business_date
            for point in ModelInputSelector(self.paths, run).series(definition.metric_id)
        ):
            return
        # In force by the target day, and public by the run's cutoff (ticket 06).
        cutoff = SummaryCutoff.target(run, utc_now())
        until = cutoff.day
        version = rules.metric_catalog_version
        scope = RetrievalScope(
            f"backtrack:{definition.release_event_family}:{until.isoformat()}",
            (definition.metric_id,),
            until.isoformat(),
            definition.priority,
            RRR_CHRONICLE_LISTING,
        )
        scoped = replace(run, retrieval_scope=scope)
        RetrievalLedger(self.paths.database, scope_run=scoped).bind_run(scoped, version)
        found = None
        official = "not_configured"
        if _official_candidate((definition,)) is not None:

            def chronicles(started: Any) -> str:
                nonlocal found
                found = backtrack_rrr_chronicle(
                    self.paths,
                    until=until,
                    public_as_of=cutoff.public_as_of,
                    fetched_at=utc_now(),
                    definition_version=version,
                    on_acquisition_started=started,
                )
                return "chronicle:" + ",".join(found.claim_ids)

            with own_acquisitions(
                self.paths.database,
                run.run_id,
                "event_backtrack",
                metric_ids=scope.metric_ids,
            ):
                RetrievalLedger(self.paths.database, scope_run=scoped).trace_acquisition(
                    run.run_id,
                    "official",
                    scope.release_event_id,
                    RRR_CHRONICLE_LISTING,
                    chronicles,
                )
            official = (
                "source_failed" if found is None else "found" if found.claim_ids else "none_found"
            )
        claim_ids = list(found.claim_ids) if found is not None else []
        tail = None
        with own_acquisitions(
            self.paths.database, run.run_id, "event_backtrack", metric_ids=scope.metric_ids
        ):
            if found is None:
                _asked, stored = discover_event(
                    self.paths,
                    scoped,
                    since=None,
                    until=until,
                    public_as_of=cutoff.public_as_of,
                    definition_version=version,
                )
            elif found.covered_through is None or found.covered_through < until:
                asked, stored = discover_event(
                    self.paths,
                    scoped,
                    since=found.covered_through,
                    until=until,
                    public_as_of=cutoff.public_as_of,
                    definition_version=version,
                )
                tail = "unchecked" if asked == "unavailable" else asked
            else:
                stored, tail = (), "not_needed"
        claim_ids += stored
        self._record(
            run.run_id,
            "event_backtrack",
            {
                # A tail candidate turned down leaves the search unsettled, not "none".
                "metrics": {
                    definition.metric_id: "found"
                    if claim_ids
                    else "none_found"
                    if found is not None and tail != "rejected"
                    else "source_failed"
                },
                "official": official,
                "covered_through": found.covered_through.isoformat()
                if found is not None and found.covered_through is not None
                else None,
                "tail": tail,
                "claim_ids": claim_ids,
            },
        )

    def _plan(self, run: RunRecord, *, decided_at: datetime | None = None) -> dict[str, Any]:
        from pring_cycle.worker import SeriesReads, _retrieval_release_status

        rules = ContextProjectionRules.from_manifest(
            ModelRepository(self.paths.database).manifest(run.model_version_id)
        )
        groups: dict[tuple[str, str, str, str | None], list[str]] = defaultdict(list)
        # Of each group's metrics, the members a lookback named; None checks every one.
        named: dict[tuple[str, str, str, str | None], dict[str, set[str] | None]] = defaultdict(
            dict
        )

        def group(
            key: tuple[str, str, str, str | None], metric_id: str, members: tuple[str, ...] = ()
        ) -> None:
            groups[key].append(metric_id)
            known = named[key]
            if not members or (metric_id in known and known[metric_id] is None):
                known[metric_id] = None
            else:
                known[metric_id] = {*(known.get(metric_id) or ()), *members}

        requirements: list[dict[str, Any]] = []
        selector = ModelInputSelector(self.paths, run)
        delivered_periods: dict[str, dict[str, set[str]]] = {}

        def official_candidate(
            definition: MetricDefinition, period: str, missing: tuple[str, ...] = ()
        ) -> str | None:
            """The official page, unless TuShare delivered the period.

            A gap (``missing`` members) is still sent to the page for one TuShare does not
            deliver, named or not: social financing's official stock growth, GDP's real
            growth beside the levels held (lookback fetch gaps 04).
            """
            url = _official_candidate((definition,))
            if url is None:
                return None
            if definition.metric_id not in delivered_periods:
                # Freshness is whether TuShare delivered the period, independently of
                # PUBLIC eligibility. Missing publication proof is not a missing row.
                delivered_periods[definition.metric_id] = {}
                for point in EvidenceRepository(self.paths.database).metric_series(
                    definition.metric_id,
                    mode=AsOfMode.SYSTEM,
                    as_of=selector.as_of,
                    definition_version=rules.metric_catalog_version,
                ):
                    if any(
                        claim.provider == "tushare"
                        and claim.quality_status == "validated"
                        and claim.value_state is EvidenceValueState.REPORTED_VALUE
                        for claim in point.claims
                    ):
                        delivered_periods[definition.metric_id].setdefault(
                            point.period_end, set()
                        ).add(member_key(definition.metric_id, point.dimensions))
            delivered = {
                member
                for end, members in delivered_periods[definition.metric_id].items()
                if matches_retrieval_period(end, period)
                for member in members
            }
            if delivered and all(member in delivered for member in missing):
                return None
            return url

        calendar = required_calendar(self.paths, run, selector)
        daily_window = tuple(calendar["dates"])
        # A domestic period below is judged on the SSE calendar, the first plan's as the
        # final's (run-findings 11): weekdays took a holiday for a session released. A
        # foreign one keeps its own market's (``market_calendar``).
        self._use_judging_calendar(run, daily_window)
        period_by_metric = {
            definition.metric_id: self._period(
                run, definition, selector, due_first=rules.confirmation is not None
            )
            for definition in rules.metric_definitions
        }
        direct_held = credit_impulse.direct_periods(selector)
        read = run_lookback(
            self.paths,
            rules,
            run,
            # The window as the SSE calendar stood at the decision, as the Worker read it.
            decided_at=decided_at or utc_now(),
            direct_held=direct_held,
        )
        # A daily reading counts its sessions back past the window, as far as the SSE
        # calendar states them (macro semantics ticket 06).
        reach = lookback.session_reach(read.readings)
        last = date.fromisoformat(run.target_business_date)
        stretch = (
            SseCalendar(self.paths, as_of=selector.as_of).around(last)
            if reach > len(daily_window)
            else None
        )
        stated = (
            tuple(day.isoformat() for day in stretch.stated_to(last))[-reach:] if stretch else ()
        )
        sessions = stated if len(stated) > len(daily_window) else daily_window
        derived = formula_requirements(
            rules,
            read,
            anchors=period_by_metric,
            sessions=sessions,
            direct_held=direct_held,
            held=partial(_held, selector),
        )
        turned_off = credit_impulse.metrics_off(rules.formula_versions)
        derived_ids = {
            r["metric_id"] for r in derived if r["metric_id"] not in r["required_input_periods"]
        }
        for definition in rules.metric_definitions:
            if definition.role == "operational_evidence" or definition.metric_id in {
                "CN_TRADE_CALENDAR",
                "CN_RELEASE_SCHEDULE",
                "SOURCE_OBSERVED_AVAILABILITY",
            }:
                requirements.append(
                    {"metric_id": definition.metric_id, "status": "operational_evidence"}
                )
                continue
            if definition.metric_id in derived_ids or definition.metric_id in turned_off:
                continue
            if definition.metric_id in DERIVED_INPUTS:
                derived.append(
                    {
                        "metric_id": definition.metric_id,
                        "status": "required_input_rule_unavailable",
                        "required_input_periods": {},
                    }
                )
                continue
            period = period_by_metric[definition.metric_id]
            if period is None:
                requirements.append(
                    {"metric_id": definition.metric_id, "status": "event_presence_unknown"}
                )
                continue
            daily = (
                definition.priority in {"P0", "P1"}
                and evidence_frequency(definition.metric_id, definition.frequency) == "daily"
                and len(daily_window) == 120
            )
            required = read.required(
                definition.metric_id,
                period,
                sessions=sessions,
                window=daily_window,
                whole_window=daily,
                catalog_members=partial(
                    _catalog_members, definition.metric_id, rules.metric_catalog_version
                ),
            )
            if definition.metric_id in BASKET_METRICS:
                # The basket's first day is the one after its base: no earlier session of the
                # window is one of its periods, to request or to list as a gap (lookback 10).
                required = {
                    period: members
                    for period, members in required.items()
                    if date.fromisoformat(period) > BASKET_BASE_DATE
                }
            for required_period, members in required.items():
                scope = RetrievalScope(
                    f"full:{definition.release_event_family}:{required_period}",
                    (definition.metric_id,),
                    required_period,
                    definition.priority,
                    None,
                    members=member_keys(definition.metric_id, members),
                )
                selection = selector.select(scope)
                requirements.append(
                    {
                        "metric_id": definition.metric_id,
                        "period": required_period,
                        "status": "local_complete" if selection.complete else "model_input_missing",
                        "selected_claim_ids": list(selection.selected_claim_ids),
                        "missing_members": list(selection.missing_members),
                        **({"members": list(scope.members)} if scope.members else {}),
                    }
                )
                if not selection.complete:
                    group(
                        (
                            definition.release_event_family,
                            required_period,
                            definition.priority,
                            official_candidate(
                                definition, required_period, selection.missing_members
                            ),
                        ),
                        definition.metric_id,
                        scope.members,
                    )
        # Looking for a new release does not make it a required input. If the official
        # page has not published it, the existing latest period retains its old semantics.
        target = date.fromisoformat(run.target_business_date)
        quarter_end = date(target.year, (target.month - 1) // 3 * 3 + 1, 1) - timedelta(days=1)
        preceding_period = {
            "monthly": (target.replace(day=1) - timedelta(days=1)).isoformat()[:7],
            "quarterly": f"{quarter_end.year}-Q{(quarter_end.month - 1) // 3 + 1}",
        }
        for definition in rules.metric_definitions:
            period = period_by_metric[definition.metric_id]
            # A held event rate stays in force; the newest day's notice is still read, with
            # the day's other members, in case it changed (ADR-0028).
            if (
                evidence_frequency(definition.metric_id, definition.frequency) == "event"
                and period is not None
                and (latest := self._latest_released(run, definition, selector)) is not None
                and latest.isoformat() > period
            ):
                group(
                    (
                        definition.release_event_family,
                        latest.isoformat(),
                        definition.priority,
                        official_candidate(definition, latest.isoformat()),
                    ),
                    definition.metric_id,
                )
            preceding = preceding_period.get(definition.frequency)
            if (
                preceding is not None
                and period is not None
                and period < preceding
                and (candidate := official_candidate(definition, preceding)) is not None
                and is_release_listing(
                    official_family_for_metrics((definition.metric_id,)), candidate
                )
            ):
                group(
                    (definition.release_event_family, preceding, definition.priority, candidate),
                    definition.metric_id,
                )
        scopes = []
        for key, metrics in sorted(
            groups.items(), key=lambda item: (item[0][2], item[0][:3], item[0][3] or "")
        ):
            family, period, priority, source_url = key
            keys = sorted(item for known in named[key].values() for item in known or ())
            scopes.append(
                RetrievalScope(
                    f"full:{family}:{period}",
                    tuple(sorted(metrics)),
                    period,
                    priority,
                    source_url,
                    tuple(keys),
                ).document()
            )
        # Nothing is stored while the plan is judged, so each series is read once.
        reads = SeriesReads(EvidenceRepository(self.paths.database))
        for document in scopes:
            document["release_status"] = _retrieval_release_status(
                self.paths,
                _scope(document),
                selector.as_of,
                definition_version=rules.metric_catalog_version,
                public_as_of=selector.cutoff,
                latest_only=True,
                reads=reads,
            )
        return {
            "origin": "before_gap_retrieval",
            "pre_request_plan_available": True,
            "model_version_id": run.model_version_id,
            "definition_version": rules.metric_catalog_version,
            "target_business_date": run.target_business_date,
            "cutoff_mode": run.cutoff_mode,
            "initial_system_as_of": run.system_as_of.isoformat(),
            "requirements": requirements,
            "derived_requirements": derived,
            "scopes": scopes,
            "daily_window": calendar,
            "created_at": utc_now().isoformat(),
        }

    def _period(
        self,
        run: RunRecord,
        definition: MetricDefinition,
        selector: ModelInputSelector,
        *,
        due_first: bool = False,
    ) -> str | None:
        target = date.fromisoformat(run.target_business_date)
        frequency = evidence_frequency(definition.metric_id, definition.frequency)
        # Nothing held: the newest period the release gate will let through, by the release
        # rule at the gate's cutoff (a month's industrial finance comes out weeks later, a
        # day's VIX at 06:00 the next morning). Unregistered: the period before the target.
        rule = FRESHNESS_REGISTRY.get(definition.metric_id)
        latest = self._latest_released(run, definition, selector)
        released = latest if rule is not None and rule.frequency == frequency else None
        if definition.metric_id == "CN_LPR_1Y_5Y":
            # The month's fixing, held or not; before the 20th, last month's is in force.
            return (latest or target).isoformat()[:7]
        if frequency == "daily":
            return (released or target).isoformat()
        points = selector.series(definition.metric_id)
        published = [p.period_end for p in points if p.period_start <= run.target_business_date]
        if frequency == "event":
            # An event announced on every operation day (the OMO rate) is read from the
            # newest day's notice; one with no such rule is not looked for (ADR-0028).
            if published:
                return max(published)
            return latest.isoformat() if latest is not None else None
        # Held, the newest held. A model confirming the stage reads back from the newest
        # due by the release calendar when that is later: a period out and past its grace
        # is asked for, not left behind an older one held (macro semantics ticket 05). One
        # out but not yet due is looked for, not required; the models before keep their
        # plans.
        due = self._due(run, definition, selector) if due_first and released is not None else None
        if frequency == "quarterly":
            period = (
                max(date.fromisoformat(max(published)), due or date.min)
                if published
                else released
                or date(target.year, ((target.month - 1) // 3) * 3 + 1, 1) - timedelta(days=1)
            )
            return f"{period.year}-Q{(period.month - 1) // 3 + 1}"
        if frequency == "monthly":
            return (
                max(max(published)[:7], due.isoformat()[:7] if due is not None else "")
                if published
                else (released or target.replace(day=1) - timedelta(days=1)).isoformat()[:7]
            )
        return None

    def _use_judging_calendar(self, run: RunRecord, window: Iterable[str]) -> None:
        """Judge release times against the run's SSE calendar, not weekdays, on to its
        cutoff (a holiday after the target is closed)."""
        if dates := [date.fromisoformat(day) for day in window]:
            use_run_calendar(judging_calendar(self.paths, dates, run.system_as_of))

    def _due(
        self, run: RunRecord, definition: MetricDefinition, selector: ModelInputSelector
    ) -> date | None:
        """The newest period due at the release gate's cutoff: out and past its grace."""
        rule = FRESHNESS_REGISTRY.get(definition.metric_id)
        if rule is None or rule.frequency == "event":
            return None
        # Through the target: a period after it is never due, though due by the cutoff.
        return latest_due_period(rule, selector.cutoff, current_calendar())

    def _latest_released(
        self, run: RunRecord, definition: MetricDefinition, selector: ModelInputSelector
    ) -> date | None:
        """The newest period out at the release gate's cutoff, by the registered rule."""
        rule = FRESHNESS_REGISTRY.get(definition.metric_id)
        if rule is None or rule.frequency not in {"daily", "monthly", "quarterly"}:
            return None
        return latest_released_period(rule, selector.cutoff, current_calendar())

    def recover_legacy_plan(self, run: RunRecord) -> None:
        if not run.cutoffs_frozen:
            raise ValueError("legacy_recovery_requires_frozen_cutoff")
        if read_full_retrieval_plan(self.paths.database, run.run_id)["initial"] is not None:
            return
        checkpoints = RunRepository(self.paths.database).reusable_checkpoints(run.run_id)
        if not any(item["kind"] == "verified_evidence" for item in checkpoints):
            raise ValueError("legacy_recovery_requires_verified_evidence")
        initial = self._plan(run)
        initial.update(
            {
                "origin": "reconstructed_from_legacy_checkpoint",
                "pre_request_plan_available": False,
                "legacy_checkpoints": checkpoints,
            }
        )
        self._record(run.run_id, "initial", initial)

    def evaluate(self, run: RunRecord) -> None:
        if not run.cutoffs_frozen:
            raise ValueError("full_run_evaluation_requires_frozen_cutoff")
        plan = read_full_retrieval_plan(self.paths.database, run.run_id)
        if plan["final"] is not None:
            if plan["final"]["system_as_of"] != run.system_as_of.isoformat():
                raise ValueError("full_run_evaluation_cutoff_mismatch")
            return
        initial = plan["initial"]
        if initial is None:
            raise ValueError("full_run_gap_plan_missing")
        final_plan = self._plan(run)
        gaps = []
        ledger = RetrievalLedger(self.paths.database)
        selector = ModelInputSelector(self.paths, run)
        before = ledger.for_run(run.run_id)
        bound = {(g["metric_id"], g["period"]) for g in before["gaps"]} if before else set()
        planned = planned_scopes(plan)
        for document in planned:
            scope = _scope(document)
            scoped = replace(run, retrieval_scope=scope)
            if any((metric, scope.period) in bound for metric in scope.metric_ids):
                ledger.bind_run(scoped, initial["definition_version"])
        gated = _release_gated(self.paths.database, run.run_id, planned, bound)
        uncovered = _listing_uncovered(self.paths, run.run_id, planned)
        for requirement in final_plan["requirements"]:
            if "period" not in requirement:
                continue
            metric, period = requirement["metric_id"], requirement["period"]
            selection = selector.select(
                RetrievalScope(
                    "evaluation",
                    (metric,),
                    period,
                    "P1",
                    None,
                    tuple(requirement.get("members", ())),
                )
            )
            gaps.append(
                {
                    "metric_id": metric,
                    "period": period,
                    "complete": selection.complete,
                    "selected_claim_ids": list(selection.selected_claim_ids),
                    "missing_members": list(selection.missing_members),
                    # What of a period still missing is held, for the gap list to say.
                    **(
                        {"held_members": list(selection.held_members)}
                        if not selection.complete and selection.held_members
                        else {}
                    ),
                    **(
                        {"release_gate": gated[(metric, period)]}
                        if not selection.complete and (metric, period) in gated
                        else {}
                    ),
                    **(
                        {"listing_not_covered": uncovered[(metric, period)]}
                        if not selection.complete and (metric, period) in uncovered
                        else {}
                    ),
                }
            )
        snapshot = ledger.for_run(run.run_id)
        if snapshot is not None:
            with database_connection(self.paths.database) as connection:
                for request in snapshot["requests"]:
                    linked = [g for g in snapshot["gaps"] if g["gap_id"] in request["gap_ids"]]
                    for final_gap in snapshot["gaps"]:
                        if final_gap["as_of"] != run.system_as_of.isoformat():
                            continue
                        if any(
                            g["metric_id"] == final_gap["metric_id"]
                            and g["period"] == final_gap["period"]
                            for g in linked
                        ):
                            connection.execute(
                                "INSERT OR IGNORE INTO retrieval_request_gap VALUES (?, ?)",
                                (request["request_id"], final_gap["gap_id"]),
                            )
        acquisitions = read_full_retrieval_plan(self.paths.database, run.run_id)["acquisitions"]
        associations = []
        for request in acquisitions:
            initial_requirements = [
                {"metric_id": r["metric_id"], "period": r["period"]}
                for r in initial["requirements"]
                if "period" in r
                and r["metric_id"] in request["metric_ids"]
                and (request["period"] is None or request["period"] == r["period"])
            ]
            requirements = [
                {"metric_id": g["metric_id"], "period": g["period"]}
                for g in gaps
                if g["metric_id"] in request["metric_ids"]
                and (request["period"] is None or request["period"] == g["period"])
            ]
            associations.append(
                {
                    "acquisition_id": request["acquisition_id"],
                    "phase": request["phase"],
                    "initial_requirement_scope": initial_requirements,
                    "planned_requirement_scope": requirements,
                    "association_basis": "declared_acquisition_purpose",
                    "unmatched_reason": None
                    if requirements
                    else (
                        "initial_requirement_superseded_at_final_cutoff"
                        if initial_requirements
                        else "no_value_requirement_for_purpose"
                    ),
                }
            )
        self._record(
            run.run_id,
            "final",
            {
                "system_as_of": run.system_as_of.isoformat(),
                "daily_window": final_plan["daily_window"],
                "requirements": final_plan["requirements"],
                "gaps": gaps,
                "non_value_requirements": [
                    r for r in final_plan["requirements"] if "period" not in r
                ],
                "derived_requirements": [
                    {
                        **r,
                        "input_coverage_complete": input_coverage_complete(
                            r, partial(_held, selector)
                        ),
                        "computation_status": "pending_projection",
                    }
                    for r in final_plan.get("derived_requirements", [])
                ],
                "request_evaluations": associations,
            },
        )

    def record_adoption(self, run: RunRecord) -> None:
        if run.projection_set_id is None:
            raise ValueError("full_run_adoption_requires_projection")
        projection = ProjectionSetRepository(self.paths.database).get(run.projection_set_id)
        if (
            projection.envelope.system_as_of != run.system_as_of
            or projection.envelope.model_version_id != run.model_version_id
            or projection.envelope.target_business_date != run.target_business_date
        ):
            raise ValueError("full_run_adoption_projection_mismatch")
        selected: set[str] = set()
        core_inputs = projection.datasets["core_assets"].get("model_input_observation_version_ids")
        assets = projection.datasets["core_assets"].get("assets")
        if isinstance(core_inputs, list):
            selected.update(str(item) for item in core_inputs)
        elif isinstance(assets, list):
            for asset in assets:
                selected.update(asset["observation_version_ids"])
        inputs = projection.datasets["macro"].get("model_input_observation_version_ids")
        if isinstance(inputs, list):
            selected.update(str(item) for item in inputs)
        else:
            # Old immutable projections have no consumption manifest. Only explicit
            # qualified value rows can be recovered; never infer from audit claims.
            def walk(value: object) -> None:
                if isinstance(value, dict):
                    if (
                        value.get("status", value.get("freshness")) in {"current", "available"}
                        and value.get("value") is not None
                    ):
                        if isinstance(value.get("selected_claim_id"), str):
                            selected.add(value["selected_claim_id"])
                        for item in value.get("input_observation_version_ids", []):
                            selected.add(str(item))
                    for key, child in value.items():
                        if key != "claims":
                            walk(child)
                elif isinstance(value, list):
                    for child in value:
                        walk(child)

            walk(projection.datasets["macro"])
            walk(projection.datasets["inventory"])
        with database_connection(self.paths.database) as connection:
            snapshot = connection.execute(
                "SELECT observation_version_ids_json FROM evidence_snapshot "
                "WHERE evidence_snapshot_id=?",
                (projection.envelope.evidence_snapshot_id,),
            ).fetchone()
            references = sorted(set(json.loads(snapshot[0]))) if snapshot else []
            source_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT claim_id FROM source_claim WHERE claim_id IN "
                    "(SELECT value FROM json_each(?))",
                    (json.dumps(sorted(selected)),),
                )
            }
        self._record(
            run.run_id,
            "adoption",
            {
                "projection_set_id": run.projection_set_id,
                "system_as_of": run.system_as_of.isoformat(),
                "selected_claim_ids": sorted(selected & source_ids),
                "selected_observation_version_ids": sorted(selected),
                "referenced_observation_version_ids": references,
                "core_provenance": (
                    "frozen_input_manifest"
                    if isinstance(core_inputs, list)
                    else "legacy_display_rows_only"
                ),
                "context_provenance": (
                    "frozen_input_manifest"
                    if isinstance(inputs, list)
                    else "legacy_explicit_rows_only"
                ),
            },
        )

    def _record(self, run_id: str, phase: str, document: dict[str, Any]) -> None:
        encoded = json.dumps(document, ensure_ascii=False, sort_keys=True)
        with database_connection(self.paths.database) as connection:
            existing = connection.execute(
                "SELECT document_json FROM full_run_gap_plan WHERE run_id=? AND phase=?",
                (run_id, phase),
            ).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise ValueError("full_run_gap_plan_is_immutable")
                return
            connection.execute(
                "INSERT INTO full_run_gap_plan VALUES (?, ?, ?, ?)",
                (run_id, phase, encoded, hashlib.sha256(encoded.encode()).hexdigest()),
            )


def record_first_outcome(database: Path, run_id: str, phase: str, document: dict[str, Any]) -> None:
    """How a step of the run ended, under ``phase`` of its plan: the first time only, so a
    resumed run doing it again does not rewrite it."""
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True)
    with database_connection(database) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO full_run_gap_plan VALUES (?, ?, ?, ?)",
            (run_id, phase, encoded, hashlib.sha256(encoded.encode()).hexdigest()),
        )


def read_full_retrieval_plan(database: Path, run_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "initial": None,
        "expansions": [],
        "final": None,
        "adoption": None,
        "acquisitions": [],
    }
    expansions: dict[int, dict[str, Any]] = {}
    with database_connection(database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='full_run_gap_plan'"
        ).fetchone():
            return result
        for phase, document, digest in connection.execute(
            "SELECT phase, document_json, document_hash FROM full_run_gap_plan WHERE run_id=?",
            (run_id,),
        ):
            if hashlib.sha256(document.encode()).hexdigest() != digest:
                raise ValueError("full_run_gap_plan_hash_mismatch")
            if phase.startswith(EXPANSION):
                expansions[int(phase.removeprefix(EXPANSION))] = json.loads(document)
            else:
                result[phase] = json.loads(document)
        result["expansions"] = [expansions[number] for number in sorted(expansions)]
        connection.row_factory = sqlite3.Row
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='full_run_acquisition' "
            "AND EXISTS (SELECT 1 FROM sqlite_master WHERE name='acquisition_request')"
        ).fetchone():
            for row in connection.execute(
                "SELECT owner.*, a.provider, a.api_name, a.state, a.raw_hash, a.normalized_hash, "
                "a.error_type, a.source_record_count, a.normalized_scalar_count, "
                "a.ingest_result, a.ingested_claim_count, a.structure_check, "
                "a.started_at, a.received_at, a.validated_at FROM full_run_acquisition owner "
                "JOIN acquisition_request a USING(acquisition_id) "
                "WHERE owner.run_id=? AND owner.phase != ? ORDER BY owner.rowid",
                (run_id, REFERENCED),
            ):
                request = dict(row)
                request["metric_ids"] = json.loads(request.pop("metric_ids_json"))
                result["acquisitions"].append(request)
    return result


def _release_gated(
    database: Path, run_id: str, scopes: list[dict[str, Any]], bound: set[tuple[str, str]]
) -> dict[tuple[str, str], str]:
    """Each planned metric and period the release gate kept from being requested, with why.

    One that passed the gate was bound to the ledger (``bound``) before any channel ran.
    Scopes of one release can share its event, and attempts name only the event: of the
    gate's reasons recorded for it, a scope takes its own plan's when among them.
    """
    reasons: dict[str, list[str]] = {}
    with database_connection(database) as connection:
        for event, classification in connection.execute(
            "SELECT release_event_id, classification FROM run_retrieval_attempt "
            "WHERE run_id=? AND channel='release_gate' ORDER BY sequence",
            (run_id,),
        ):
            reasons.setdefault(event, []).append(str(classification))
    gated = {}
    for document in scopes:
        recorded = reasons.get(document["release_event_id"])
        if not recorded:
            continue
        reason = document["release_status"]
        for metric in document["metric_ids"]:
            if (metric, document["period"]) not in bound:
                gated[(metric, document["period"])] = reason if reason in recorded else recorded[-1]
    return gated


def _listing_uncovered(
    paths: RuntimePaths, run_id: str, scopes: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, object]]:
    """Each planned metric and period whose official listing stopped short of it: the
    listing, where its reading stopped (``page_limit``: the site's pages of the run were
    read), how many of its pages the run read, and the earliest entry they list.

    Its release may be listed further back: not found there says nothing of whether it was
    published, or (an OMO day) whether there was an operation (lookback L05). Attempts name
    only the event, which scopes of one release share: a scope read through a listing takes
    the event's, since its scopes read the one listing for the one period.
    """
    prefix = LISTING_NOT_COVERED + "_"
    stopped: dict[str, str] = {}
    with database_connection(paths.database) as connection:
        for event, classification in connection.execute(
            "SELECT release_event_id, classification FROM run_retrieval_attempt "
            "WHERE run_id=? AND channel='official' AND substr(classification, 1, ?)=? "
            "ORDER BY sequence",
            (run_id, len(prefix), prefix),
        ):
            stopped[str(event)] = str(classification).removeprefix(prefix)
    if not stopped:
        return {}
    scan = run_listings(paths, run_id)
    uncovered: dict[tuple[str, str], dict[str, object]] = {}
    for document in scopes:
        listing = _scope_listing(_scope(document))
        if listing is None or document["release_event_id"] not in stopped:
            continue
        for metric in document["metric_ids"]:
            uncovered[(metric, document["period"])] = {
                "listing": listing,
                "stopped": stopped[document["release_event_id"]],
                "pages_read": scan.reads.get(listing, 0),
                "oldest_entry": min(scan.days(listing), default=None),
            }
    return uncovered


def _members_of(document: dict[str, Any], metric_id: str) -> set[str] | None:
    """The members a scope asks of ``metric_id``: None for every one."""
    own = {key for key in document.get("members", ()) if key.startswith(f"{metric_id}:")}
    return own or None


def _asked_for(asked: dict[tuple[str, str], set[str] | None], document: dict[str, Any]) -> bool:
    """Whether every metric and period of the scope, with its members, was asked for."""
    for metric_id in document["metric_ids"]:
        key = (metric_id, document["period"])
        if key not in asked:
            return False
        held, wanted = asked[key], _members_of(document, metric_id)
        if held is not None and (wanted is None or not wanted <= held):
            return False
    return True


def _mark_asked(asked: dict[tuple[str, str], set[str] | None], document: dict[str, Any]) -> None:
    for metric_id in document["metric_ids"]:
        key = (metric_id, document["period"])
        wanted = _members_of(document, metric_id)
        if wanted is None or (key in asked and asked[key] is None):
            asked[key] = None
        else:
            asked[key] = {*(asked.get(key) or ()), *wanted}


def planned_scopes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The scopes the run planned: the first plan's, then each re-expansion's."""
    initial = plan.get("initial") or {}
    return [
        *initial.get("scopes", []),
        *(document for expansion in plan.get("expansions", []) for document in expansion["scopes"]),
    ]


def _scope(document: dict[str, Any]) -> RetrievalScope:
    return RetrievalScope(
        document["release_event_id"],
        tuple(document["metric_ids"]),
        document["period"],
        document["priority"],
        document["source_url"],
        tuple(document.get("members", ())),
    )


def _held(
    selector: ModelInputSelector, metric_id: str, period: str, members: list[str] | None
) -> bool:
    """Whether ``selector`` holds ``members`` of ``metric_id`` for ``period``, or every one."""
    scope = RetrievalScope("evaluation", (metric_id,), period, "P1", None, tuple(members or ()))
    return selector.select(scope).complete


def _catalog_members(
    metric_id: str, version: str, period: str
) -> tuple[dict[str, str], ...] | None:
    """The members the catalog requires of ``metric_id`` for ``period``."""
    return required_dimension_members(metric_id, definition_version=version, period=period)


def _official_candidate(definitions: tuple[MetricDefinition, ...]) -> str | None:
    # The frozen built-in catalogs predate reviewed fallback contracts. Candidate URLs
    # become operative through a newly admitted catalog, without rewriting those identities.
    if any(item.definition_version in BUILTIN_CATALOG_VERSIONS for item in definitions):
        return None
    try:
        family = official_family_for_metrics(tuple(item.metric_id for item in definitions))
    except ValueError:
        return None
    url = next(
        (
            url
            for url in definitions[0].source_candidates
            if url.startswith("https://")
            and all(url in item.source_candidates for item in definitions[1:])
        ),
        None,
    )
    if url is None:
        return None
    # The listing the release is read from: metrics one release states are one request.
    return release_listing(family, url) or url


def _has_release_listing(scope: RetrievalScope) -> bool:
    return _scope_listing(scope) is not None


def _scope_listing(scope: RetrievalScope) -> str | None:
    """The official listing the scope's release is looked up on, if it is read from one."""
    if scope.source_url is None:
        return None
    try:
        family = official_family_for_metrics(scope.metric_ids)
    except ValueError:
        return None
    return release_listing(family, scope.source_url)


FULL_RETRIEVAL_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS full_run_acquisition ("
    "run_id TEXT NOT NULL REFERENCES parent_run(run_id), "
    "acquisition_id TEXT NOT NULL REFERENCES acquisition_request(acquisition_id), "
    "phase TEXT NOT NULL, metric_ids_json TEXT NOT NULL, period TEXT, "
    "PRIMARY KEY(run_id, acquisition_id))",
    "CREATE TABLE IF NOT EXISTS full_run_gap_plan ("
    "run_id TEXT NOT NULL REFERENCES parent_run(run_id), phase TEXT NOT NULL, "
    "document_json TEXT NOT NULL, document_hash TEXT NOT NULL, PRIMARY KEY(run_id,phase))",
    *(
        f"CREATE TRIGGER IF NOT EXISTS full_run_gap_plan_no_{action.lower()} "
        f"BEFORE {action} ON full_run_gap_plan BEGIN "
        "SELECT RAISE(ABORT, 'full_run_gap_plan_is_immutable'); END"
        for action in ("UPDATE", "DELETE")
    ),
    *(
        f"CREATE TRIGGER IF NOT EXISTS full_run_acquisition_no_{action.lower()} "
        f"BEFORE {action} ON full_run_acquisition BEGIN "
        "SELECT RAISE(ABORT, 'acquisition_run_owner_is_immutable'); END"
        for action in ("UPDATE", "DELETE")
    ),
)
