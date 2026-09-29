from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date
from urllib.parse import urlsplit
from uuid import uuid4

from pring_cycle.catalog import metric_definition
from pring_cycle.catalog_registry import (
    BUILTIN_CATALOG_VERSIONS,
    SYSTEM_TARGET_CUTOFF_VERSION,
    require_registered_manifest,
)
from pring_cycle.context_projection import TargetBoundEvidenceRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, MetricSeriesPoint
from pring_cycle.freshness import period_status
from pring_cycle.interbank_evidence import INTERBANK_METRICS, interbank_claims_matching_acquisitions
from pring_cycle.metric_contracts import (
    EFFECTIVE_UNTIL_CHANGED_METRICS,
    china_business_day_end,
    event_period_limit,
    required_dimension_members,
)
from pring_cycle.models import ModelRepository
from pring_cycle.news_rules import news_claims_matching_quotes, rules_for
from pring_cycle.official_context import (
    OFFICIAL_CONTEXT_INTEGRITY_METRICS,
    ParsedOfficialContextRelease,
    official_claims_matching_acquisitions,
)
from pring_cycle.official_lpr import ParsedLprRelease, lpr_claims_matching_acquisitions
from pring_cycle.published_events import select_published_rrr_events
from pring_cycle.retrieval import RetrievalAdapterResponse, matches_retrieval_period
from pring_cycle.retrieval_ledger import RetrievalBudgetBlocked, RetrievalLedger, utc_now
from pring_cycle.retrieval_registry import (
    families_of,
    media_outlet,
    parser_for_scope,
    registered_host,
)
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import (
    CORE_API_IDENTITIES,
    CoreInputValidator,
    selected_core_claim_is_valid,
)
from pring_cycle.storage import database_connection
from pring_cycle.treasury_context import TREASURY_METRICS, treasury_claims_matching_acquisitions
from pring_cycle.tushare_context import (
    MARKET_INDEX_IDENTITIES,
    parse_market_index_acquisition,
    parse_valuation_acquisition,
    tushare_claims_matching_acquisitions,
)
from pring_cycle.warrant_inputs import select_warrant_inputs


@dataclass(frozen=True)
class MetricMaterialCheck:
    metric_id: str
    originals: str
    dimensions: str
    invalid_original_claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelInputSelection:
    complete: bool
    selected_claim_ids: tuple[str, ...]
    missing_members: tuple[str, ...]
    material_checks: tuple[MetricMaterialCheck, ...] = ()
    # Required members already held, each by exactly one selected claim.
    held_members: tuple[str, ...] = ()


def select_retrieval_input(
    paths: RuntimePaths, run: RunRecord, *, mode: AsOfMode = AsOfMode.SYSTEM
) -> ModelInputSelection:
    scope = run.retrieval_scope
    if scope is None:
        raise ValueError("retrieval_scope_required")
    return ModelInputSelector(paths, run, mode=mode).select(scope)


@dataclass(frozen=True)
class _ClaimFamily:
    """A family of registered metrics and the recheck that decides which claims stay valid."""

    owns: Callable[[str], bool]
    check: Callable[[tuple[str, ...]], set[str]]


class ModelInputSelector:
    """One fixed evaluation instant, with shared reads across periods and members."""

    def __init__(
        self, paths: RuntimePaths, run: RunRecord, *, mode: AsOfMode = AsOfMode.SYSTEM
    ) -> None:
        manifest = ModelRepository(paths.database).manifest(run.model_version_id)
        require_registered_manifest(paths.database, manifest)
        self.version = str(manifest["metric_catalog_version"])
        self.database_path = paths.database
        self.evidence = TargetBoundEvidenceRepository(
            EvidenceRepository(paths.database),
            date.fromisoformat(run.target_business_date),
            {},
            allow_system_at_target=(
                manifest.get("point_in_time_rule_version") == SYSTEM_TARGET_CUTOFF_VERSION
            ),
        )
        self.core_evidence = EvidenceRepository(paths.database)
        self.target_business_date = run.target_business_date
        self.full_run = run.command_type in {"manual_full", "scheduled_full"}
        self.as_of = (
            utc_now()
            if run.cutoff_mode == "acquisition_window" and not run.cutoffs_frozen
            else run.system_as_of
        )
        self.mode = mode
        self._points: dict[str, tuple[MetricSeriesPoint, ...]] = {}
        self._adoptable: dict[tuple[str, str], tuple[MetricSeriesPoint, ...]] = {}

    def series(self, metric_id: str) -> tuple[MetricSeriesPoint, ...]:
        if metric_id not in self._points:
            # Full-run core evaluation follows the bound model's SYSTEM path.
            # Unknown PUBLIC time remains unknown; it is not a transport error.
            repository = (
                self.core_evidence
                if self.full_run
                and self.mode is AsOfMode.SYSTEM
                and metric_id in CORE_API_IDENTITIES
                else self.evidence
            )
            self._points[metric_id] = tuple(
                point
                for point in repository.metric_series(
                    metric_id, mode=self.mode, as_of=self.as_of, definition_version=self.version
                )
                if metric_id not in CORE_API_IDENTITIES
                or point.period_end <= self.target_business_date
            )
        return self._points[metric_id]

    def adoptable(self, metric_id: str, period: str) -> tuple[MetricSeriesPoint, ...]:
        """The points this period can adopt, which is all a family recheck has to cover.

        A claim outside the period is never consulted below, so rechecking it reads
        originals no decision depends on; over a replay that repeats one full recheck of
        the whole stored series per day.
        """
        key = metric_id, period
        if key not in self._adoptable:
            points = self.series(metric_id)
            if metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS:
                # An event stays in force until changed, so the period reaches back past its
                # own end. Only the latest event each member knows of is ever adopted, and a
                # bad newer event never falls back to an older one, so the rest cannot matter.
                limit = event_period_limit(period)
                latest: dict[tuple[tuple[str, str], ...], str] = {}
                for point in points:
                    if point.period_end[: len(limit)] > limit:
                        continue
                    member = tuple(sorted(point.dimensions.items()))
                    if point.period_end > latest.get(member, ""):
                        latest[member] = point.period_end
                # A member may hold several points at that latest period; keep them all,
                # because the conflict between them is exactly what the caller must see.
                self._adoptable[key] = tuple(
                    point
                    for point in points
                    if point.period_end[: len(limit)] <= limit
                    and point.period_end == latest[tuple(sorted(point.dimensions.items()))]
                )
            else:
                self._adoptable[key] = tuple(
                    point for point in points if matches_retrieval_period(point.period_end, period)
                )
        return self._adoptable[key]

    def _claim_families(self, period: str) -> tuple[_ClaimFamily, ...]:
        """Each registered family's metrics and how its selected claims are rechecked.

        Every family has the same shape at the call site: take this family's metrics from the
        scope, recheck their selected claims against the acquired originals, and accept only
        the claims that came back valid. Adding a family means adding one entry here.
        """

        def points_of(metric_ids: tuple[str, ...]) -> tuple[MetricSeriesPoint, ...]:
            # A metric named twice in one scope still contributes its points once.
            return tuple(
                point
                for metric_id in dict.fromkeys(metric_ids)
                for point in self.adoptable(metric_id, period)
            )

        def series_by_metric(
            metric_ids: tuple[str, ...],
        ) -> dict[str, tuple[MetricSeriesPoint, ...]]:
            return {
                metric_id: self.adoptable(metric_id, period)
                for metric_id in dict.fromkeys(metric_ids)
            }

        return (
            _ClaimFamily(
                lambda metric_id: metric_id == "CN_USDCNY_ECB_REFERENCE_CROSS",
                lambda metric_ids: self.core_evidence.source_claims_matching_registered_contract(
                    tuple(
                        point.selected_claim_id
                        for point in points_of(metric_ids)
                        if point.selected_claim_id is not None
                    ),
                    definition_version=self.version,
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id == "CN_LPR_1Y_5Y",
                lambda metric_ids: (
                    lpr_claims_matching_acquisitions(
                        self.core_evidence,
                        tuple(
                            point
                            for point in points_of(metric_ids)
                            if point.selected_claim_id is not None
                        ),
                    )
                    | news_claims_matching_quotes(self.database_path, series_by_metric(metric_ids))
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id in OFFICIAL_CONTEXT_INTEGRITY_METRICS,
                # An official original, a TuShare delivery, or a news rule's matched quote.
                lambda metric_ids: (
                    official_claims_matching_acquisitions(
                        self.core_evidence,
                        series_by_metric(metric_ids),
                        definition_version=self.version,
                    )
                    | news_claims_matching_quotes(self.database_path, series_by_metric(metric_ids))
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id in INTERBANK_METRICS,
                lambda metric_ids: interbank_claims_matching_acquisitions(
                    self.core_evidence,
                    series_by_metric(metric_ids),
                    definition_version=self.version,
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id in TREASURY_METRICS,
                lambda metric_ids: treasury_claims_matching_acquisitions(
                    self.core_evidence,
                    series_by_metric(metric_ids),
                    definition_version=self.version,
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id == "CN_MARGIN_BALANCE",
                lambda metric_ids: tushare_claims_matching_acquisitions(
                    self.core_evidence,
                    points_of(metric_ids),
                    definition_version=self.version,
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id in MARKET_INDEX_IDENTITIES,
                lambda metric_ids: tushare_claims_matching_acquisitions(
                    self.core_evidence,
                    points_of(metric_ids),
                    definition_version=self.version,
                    parse=parse_market_index_acquisition,
                ),
            ),
            _ClaimFamily(
                lambda metric_id: metric_id == "CN_INDEX_VALUATION",
                lambda metric_ids: tushare_claims_matching_acquisitions(
                    self.core_evidence,
                    points_of(metric_ids),
                    definition_version=self.version,
                    parse=parse_valuation_acquisition,
                ),
            ),
        )

    def select(self, scope: RetrievalScope) -> ModelInputSelection:
        registered = self.version not in BUILTIN_CATALOG_VERSIONS
        core_inputs = CoreInputValidator(
            self.core_evidence,
            tuple(
                point.selected_claim_id
                for metric_id in scope.metric_ids
                if metric_id in CORE_API_IDENTITIES and registered
                for point in self.series(metric_id)
                if point.selected_claim_id is not None
                and matches_retrieval_period(point.period_end, scope.period)
            ),
        )
        families = self._claim_families(scope.period) if registered else ()
        checked_families = tuple(
            (
                family,
                family.check(metric_ids),
            )
            for family in families
            if (metric_ids := tuple(m for m in scope.metric_ids if family.owns(m)))
        )
        selected_ids: list[str] = []
        missing: list[str] = []
        held: list[str] = []
        dimension_checks: dict[str, str] = {}
        material_checks = []
        for metric_id in scope.metric_ids:
            definition = metric_definition(
                metric_id, definition_version=self.version, database_path=self.database_path
            )
            if metric_id == "CN_FUTURES_WARRANTS" and self.version not in BUILTIN_CATALOG_VERSIONS:
                warrants = select_warrant_inputs(
                    self.core_evidence,
                    self.series(metric_id),
                    period=scope.period,
                    mode=self.mode,
                    definition_version=self.version,
                )
                material_checks.append(
                    MetricMaterialCheck(
                        metric_id,
                        "executed"
                        if any(
                            p.selected_claim_id is not None
                            for p in self.adoptable(metric_id, scope.period)
                        )
                        else "blocked",
                        "executed",
                    )
                )
                selected_ids.extend(warrants.selected_claim_ids)
                missing.extend(warrants.missing_members)
                continue
            if metric_id == "CN_RRR_EVENT" and self.version not in BUILTIN_CATALOG_VERSIONS:
                result = select_published_rrr_events(
                    self.core_evidence,
                    tuple(
                        p
                        for p in self.series(metric_id)
                        if matches_retrieval_period(p.period_end, scope.period)
                    ),
                )
                material_checks.append(
                    MetricMaterialCheck(
                        metric_id,
                        "executed"
                        if any(
                            p.selected_claim_id is not None
                            for p in self.adoptable(metric_id, scope.period)
                        )
                        else "blocked",
                        "blocked"
                        if any(
                            "publication_contract_unavailable" in member
                            or "publication_time_invalid" in member
                            for member in result.missing_members
                        )
                        else "executed",
                    )
                )
                selected_ids.extend(result.selected_claim_ids)
                missing.extend(result.missing_members)
                continue
            expected = required_dimension_members(
                metric_id, definition_version=self.version, period=scope.period
            )
            if expected is None:
                if definition.dimensions:
                    dimension_checks[metric_id] = "blocked"
                    missing.append(f"{metric_id}:dimension_contract_unavailable")
                    continue
                expected = ({},)
            dimension_checks[metric_id] = "executed"
            # Exactly the points the family recheck covered, so nothing can be adopted
            # that was never rechecked.
            points = self.adoptable(metric_id, scope.period)
            event_metric = metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS
            for member in expected:
                matches = [p for p in points if p.dimensions == member]
                if event_metric and matches:
                    # Pick the latest known event before checking quality. A bad
                    # newer event must not silently resurrect an older rate.
                    latest = max(p.period_end for p in matches)
                    matches = [p for p in matches if p.period_end == latest]
                    target = date.fromisoformat(self.target_business_date)
                    if period_status(metric_id, latest, china_business_day_end(target)) == "stale":
                        matches = []
                accepted = []
                for point in matches:
                    claim = next(
                        (c for c in point.claims if c.claim_id == point.selected_claim_id), None
                    )
                    if (
                        point.selection_status == "selected"
                        and point.value_state == EvidenceValueState.REPORTED_VALUE
                        and point.selected_value is not None
                        and claim is not None
                        and claim.quality_status == "validated"
                        and all(
                            not family.owns(metric_id)
                            or not registered
                            or claim.claim_id in valid_claim_ids
                            for family, valid_claim_ids in checked_families
                        )
                        and (
                            metric_id not in CORE_API_IDENTITIES
                            or selected_core_claim_is_valid(metric_id, point)
                        )
                        and (
                            metric_id not in CORE_API_IDENTITIES
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or core_inputs.is_valid(metric_id, point)
                        )
                    ):
                        accepted.append(claim.claim_id)
                if len(accepted) == 1:
                    selected_ids.extend(accepted)
                    held.append(f"{metric_id}:{json.dumps(member, sort_keys=True)}")
                else:
                    missing.append(f"{metric_id}:{json.dumps(member, sort_keys=True)}")
        for metric_id in dict.fromkeys(scope.metric_ids):
            # Core history and financing retain their own checks; the dedicated
            # event/warrant paths recorded their execution above.
            if metric_id in CORE_API_IDENTITIES or metric_id in {
                "CN_MARGIN_BALANCE",
                "CN_MARGIN_BALANCE_SSE_SZSE",
                "CN_RRR_EVENT",
                "CN_FUTURES_WARRANTS",
            }:
                continue
            matching = [
                (family, valid) for family, valid in checked_families if family.owns(metric_id)
            ]
            claim_ids = {
                point.selected_claim_id
                for point in self.adoptable(metric_id, scope.period)
                if point.selected_claim_id is not None
            }
            invalid = {
                claim_id
                for claim_id in claim_ids
                if any(claim_id not in valid for _, valid in matching)
            }
            material_checks.append(
                MetricMaterialCheck(
                    metric_id,
                    "executed" if matching and claim_ids else "blocked" if matching else "pending",
                    dimension_checks.get(metric_id, "pending"),
                    tuple(sorted(invalid)),
                )
            )
        return ModelInputSelection(
            not missing and bool(selected_ids),
            tuple(selected_ids),
            tuple(missing),
            tuple(material_checks),
            tuple(held),
        )


# Why a search candidate was not adopted (ticket 19). Each one is shown per URL under
# the gap list's "retrieval failed" group.
NOT_WHITELISTED = "not_whitelisted"
PARSE_FAILED = "parse_failed"
PERIOD_MISMATCH = "period_mismatch"
NO_PUBLICATION_DATE = "no_publication_date"
DATE_AFTER_CUTOFF = "date_after_cutoff"
SEARCH_VALUE_MISMATCH = "search_value_mismatch"
FETCH_FAILED = "fetch_failed"
# The page parsed, but the model input for the gap is still not complete.
INCOMPLETE_MODEL_INPUT = "incomplete_model_input"
RETRIEVAL_BLOCKED = "retrieval_blocked"
# A whitelisted media page was found, but no sentence matched the family's news rules.
RULE_NOT_MATCHED = "rule_not_matched"
# Verdicts on the page itself: a later check in the same run would reach the same one.
# Fetch failures, blocked requests, a publication after a cutoff that still moves and an
# input incomplete only because another member was missing are checked again.
_FINAL_REASONS = (
    NOT_WHITELISTED,
    PARSE_FAILED,
    PERIOD_MISMATCH,
    NO_PUBLICATION_DATE,
    RULE_NOT_MATCHED,
)


class CandidateRejected(ValueError):
    """A parsed candidate the strict path does not adopt; the message is the reason."""


def candidate_rejection_reason(error: BaseException) -> str:
    """Map a registered parser's failure to the reason shown for its URL."""
    if isinstance(error, CandidateRejected):
        return str(error)
    if isinstance(error, OSError):
        return FETCH_FAILED
    if isinstance(error, RetrievalBudgetBlocked):
        # Never fetched: the ledger held the request back (cache or budget).
        return RETRIEVAL_BLOCKED
    message = str(error)
    if message.endswith(("_not_official", "_redirect_identity_changed")) or message in {
        "official_context_metric_family_unknown",
        "official_context_family_unsupported",
    }:
        return NOT_WHITELISTED
    if "period" in message and "mismatch" in message:
        return PERIOD_MISMATCH
    if message.endswith("release_date_missing"):
        return NO_PUBLICATION_DATE
    return PARSE_FAILED


_NUMBER = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?%?")


def search_value_conflicts(summary: str, values: tuple[float, ...]) -> bool:
    """Whether a search channel's own number looks like the parsed value misplaced.

    Only decimals and percentages count as the channel's values (years and days are
    integers). The candidate conflicts when none of those agrees with a parsed value
    within 5% but one of them is a parsed value shifted by ten to a thousandfold: a
    decimal-point slip. Unrelated numbers never reject a page on their own.
    """
    reported = [
        float(token.rstrip("%").replace(",", ""))
        for token in _NUMBER.findall(summary)
        if "." in token or token.endswith("%")
    ]
    parsed = [value for value in values if value]

    def near(left: float, right: float) -> bool:
        return abs(left - right) <= 0.05 * abs(right)

    if not reported or not parsed:
        return False
    if any(near(s, v) for s in reported for v in parsed):
        return False
    return any(
        near(s, v * 10.0**shift)
        for s in reported
        for v in parsed
        # Up to a thousandfold: a slipped decimal point or percent sign. Ten thousand is
        # how Chinese sources restate 亿 as 万亿 and is not a slip.
        for shift in (-3, -2, -1, 1, 2, 3)
    )


# The P2 lenient path (ticket 20): hosts registered per metric in the retrieval registry,
# and the whitelisted media (phase two #10). A candidate on one of them is accepted with
# the value the search channel extracted; the page is refetched so its original and hash
# are kept. No parser is required.
LENIENT_HOSTS: dict[str, tuple[tuple[str, str], ...]] = {
    metric_id: family.hosts
    for family in families_of("lenient").values()
    for metric_id in family.metric_ids
}
# Recorded in place of a parser version: how the lenient value was taken.
LENIENT_EXTRACTION = "search-summary-extraction-v0001"
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_CLOSE_VALUE = re.compile(
    r"(?:clos(?:e|ed|ing)(?:\s+(?:at|value|price))?|收盘(?:价)?|收于|报)\s*[:：为]?\s*"
    r"(-?\d+(?:,\d{3})*\.\d+)",
    re.IGNORECASE,
)


def _lenient_host(metric_id: str, url: str) -> str:
    """A host registered for the metric, or any whitelisted media host (ADR-0026)."""
    if metric_id not in LENIENT_HOSTS:
        raise CandidateRejected(NOT_WHITELISTED)
    host = registered_host(metric_id, url)
    if host is None and media_outlet(url) is not None:
        host = urlsplit(url).hostname
    if host is None:
        raise CandidateRejected(NOT_WHITELISTED)
    return host


def _period_spellings(day: date) -> tuple[str, ...]:
    month = _MONTHS[day.month - 1]
    return (
        day.isoformat(),
        day.strftime("%Y/%m/%d"),
        f"{day.year}年{day.month}月{day.day}日",
        f"{month} {day.day}, {day.year}",
        f"{month[:3]} {day.day}, {day.year}",
        f"{month[:3]} {day.day:02d}, {day.year}",
    )


def lenient_value(summary: str, day: date) -> float:
    """The one value the search channel reported for ``day``, or a rejection reason."""
    spellings = [text for text in _period_spellings(day) if text in summary]
    if not spellings:
        raise CandidateRejected(PERIOD_MISMATCH)
    text = summary
    for spelling in spellings:
        text = text.replace(spelling, " ")
    values = {float(token.replace(",", "")) for token in re.findall(r"-?\d+(?:,\d{3})*\.\d+", text)}
    if len(values) != 1:
        values = {float(token.replace(",", "")) for token in _CLOSE_VALUE.findall(text)}
    if len(values) != 1:
        raise CandidateRejected(PARSE_FAILED)
    return values.pop()


def _accept_lenient_candidate(
    paths: RuntimePaths,
    run: RunRecord,
    url: str,
    summary: str,
    *,
    definition_version: str,
    on_acquisition_started: Callable[[str], None],
) -> tuple[str, ...]:
    """Store the search channel's value for a P2 gap once its page original is kept."""
    from urllib.request import Request

    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.evidence import SourceClaimInput
    from pring_cycle.freshness import public_available_at
    from pring_cycle.http_transport import open_no_redirects
    from pring_cycle.trading_calendar import current_calendar

    scope = run.retrieval_scope
    assert scope is not None
    [metric_id] = scope.metric_ids
    host = _lenient_host(metric_id, url)
    day = date.fromisoformat(scope.period)
    value = lenient_value(summary, day)
    responses: list[tuple[int, str]] = []

    def fetch() -> bytes:
        request = Request(url, headers={"User-Agent": "pring-cycle/1.0 search-page"})
        with open_no_redirects(request, timeout=15) as response:
            responses.append((int(response.status), str(response.geturl())))
            return bytes(response.read(4_000_000))

    def parse(_raw: bytes) -> dict[str, object]:
        status, final_url = responses[0]
        if status != 200:
            raise CandidateRejected(FETCH_FAILED)
        _lenient_host(metric_id, final_url)
        return {"value": value, "extraction": LENIENT_EXTRACTION, "period": scope.period}

    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=host,
        api_name="search_page_get",
        parameters={"source_url": url, "period": scope.period, "metric_id": metric_id},
        fields="value",
        parser_version=LENIENT_EXTRACTION,
        fetch=fetch,
        parse=parse,
        normalize=lambda parsed: parsed,
        on_started=on_acquisition_started,
    )
    receipt = acquired.receipt
    assert receipt.received_at is not None and receipt.validated_at is not None
    public_at = public_available_at(metric_id, day, receipt.received_at, current_calendar())
    if public_at is not None and public_at > run.system_as_of:
        raise CandidateRejected(DATE_AFTER_CUTOFF)
    definition = metric_definition(
        metric_id, definition_version=definition_version, database_path=paths.database
    )
    stored = EvidenceRepository(paths.database).append_source_claim(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version=definition_version,
            period_kind="business_day",
            period_start=scope.period,
            period_end=scope.period,
            dimensions={},
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=definition.unit,
            provider=host,
            source_reference=f"search_page:{url}",
            release_event_id=f"search_page:{metric_id}:{scope.period}:{receipt.raw_hash}",
            release_at=None,
            public_available_at=None,
            fetched_at=receipt.received_at,
            available_at=receipt.validated_at,
            quality_status="validated",
            acquisition_id=receipt.acquisition_id,
        )
    )
    return (stored.claim_id,)


def _accept_media_candidate(
    paths: RuntimePaths,
    run: RunRecord,
    url: str,
    *,
    definition_version: str,
    on_acquisition_started: Callable[[str], None],
) -> tuple[str, ...]:
    """A P1/P2 value from a whitelisted media page, by the family's news rules (ADR-0026).

    The page is refetched and kept; only sentences the rules recognize give values, each
    for the gap's due period, and each value keeps its matched quote. P0 never takes one.
    """
    from urllib.request import Request

    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.freshness import public_available_at
    from pring_cycle.http_transport import open_no_redirects
    from pring_cycle.news_rules import (
        MEDIA_PAGE,
        MEDIA_PAGE_API,
        NEWS_RULES_VERSION,
        NewsExtraction,
        TakenValue,
        extract,
        member_period,
        page_published_at,
        page_title,
        parse_published_at,
        plain_text,
        store_news_values,
        text_hash,
    )
    from pring_cycle.trading_calendar import current_calendar

    scope = run.retrieval_scope
    assert scope is not None
    outlet = media_outlet(url)
    if outlet is None or scope.priority == "P0":
        raise CandidateRejected(NOT_WHITELISTED)
    responses: list[tuple[int, str, str]] = []

    def fetch() -> bytes:
        request = Request(url, headers={"User-Agent": "pring-cycle/1.0 media-page"})
        with open_no_redirects(request, timeout=15) as response:
            responses.append(
                (
                    int(response.status),
                    str(response.geturl()),
                    str(response.headers.get("Content-Type", "")),
                )
            )
            return bytes(response.read(4_000_000))

    def decode(raw: bytes) -> str:
        charset = re.search(r"charset=([\w-]+)", responses[0][2] if responses else "")
        for encoding in (charset.group(1) if charset else "utf-8", "utf-8", "gb18030"):
            try:
                return raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        raise CandidateRejected(PARSE_FAILED)

    def parse(raw: bytes) -> tuple[str, str, NewsExtraction, str | None]:
        status, final_url, _media_type = responses[0]
        if status != 200:
            raise CandidateRejected(FETCH_FAILED)
        if media_outlet(final_url) != outlet:
            raise CandidateRejected(NOT_WHITELISTED)
        content = decode(raw)
        text = plain_text(content)
        extraction = extract(scope.metric_ids, scope.period, text)
        if extraction.reason is not None:
            raise CandidateRejected(extraction.reason)
        return content, text, extraction, page_published_at(content)

    acquired = AcquisitionRepository(paths.database, paths.artifacts).capture(
        provider=outlet,
        api_name=MEDIA_PAGE_API,
        parameters={
            "source_url": url,
            "period": scope.period,
            "metric_ids": ",".join(scope.metric_ids),
        },
        fields="text",
        parser_version=NEWS_RULES_VERSION,
        fetch=fetch,
        parse=parse,
        normalize=lambda parsed: {
            "title": page_title(parsed[0]),
            "published_at": parsed[3],
            "text_sha256": text_hash(parsed[1]),
            "values": [
                {"metric_id": v.metric_id, "dimensions": v.dimensions, "value": v.value}
                for v in parsed[2].values
            ],
        },
        on_started=on_acquisition_started,
    )
    receipt = acquired.receipt
    content, text, extraction, published_text = acquired.value
    assert receipt.received_at is not None and receipt.validated_at is not None
    published = parse_published_at(published_text)
    for value in extraction.values:
        # The page's own time when it shows one, else the registered release time.
        _kind, _start, end = member_period(value.metric_id, value.dimensions, scope.period)
        known = published or public_available_at(
            value.metric_id, date.fromisoformat(end), receipt.received_at, current_calendar()
        )
        if known is not None and known > run.system_as_of:
            raise CandidateRejected(DATE_AFTER_CUTOFF)
    title = page_title(content)
    return store_news_values(
        paths.database,
        tuple(
            TakenValue(
                value=value,
                title=title,
                source_name=outlet,
                published_at=published.isoformat() if published else published_text,
                body_hash=text_hash(text),
                url=url,
                acquisition_id=receipt.acquisition_id,
                fetched_at=receipt.received_at,
                release_at=published,
            )
            for value in extraction.values
        ),
        route=MEDIA_PAGE,
        provider=outlet,
        source_reference=lambda _taken: f"{MEDIA_PAGE}:{url}#sha256={receipt.raw_hash}",
        period=scope.period,
        definition_version=definition_version,
        available_at=receipt.validated_at,
    )


def _refetch_csindex_candidate(
    paths: RuntimePaths,
    run: RunRecord,
    url: str,
    summary: str,
    *,
    definition_version: str,
    on_acquisition_started: Callable[[str], None],
) -> tuple[str, ...]:
    """A CSI core candidate is refetched from the registered CSI page and parsed there."""
    from pring_cycle.adapters import MarketBar
    from pring_cycle.freshness import public_available_at
    from pring_cycle.official_core import is_csindex_page, refresh_csindex_core
    from pring_cycle.trading_calendar import current_calendar

    scope = run.retrieval_scope
    assert scope is not None
    [metric_id] = scope.metric_ids
    if not is_csindex_page(metric_id, url):
        raise CandidateRejected(NOT_WHITELISTED)
    day = date.fromisoformat(scope.period)

    def admit(bars: tuple[MarketBar, ...]) -> None:
        if [bar.business_date for bar in bars] != [day]:
            raise CandidateRejected(PERIOD_MISMATCH)
        published = public_available_at(metric_id, day, None, current_calendar())
        if published is None:
            raise CandidateRejected(NO_PUBLICATION_DATE)
        if published > run.system_as_of:
            raise CandidateRejected(DATE_AFTER_CUTOFF)
        if search_value_conflicts(summary, tuple(bar.close for bar in bars)):
            raise CandidateRejected(SEARCH_VALUE_MISMATCH)

    return refresh_csindex_core(
        paths,
        metric_id,
        start=day,
        end=day,
        definition_version=definition_version,
        on_acquisition_started=on_acquisition_started,
        admit=admit,
    )


def verify_search_candidates(
    paths: RuntimePaths,
    run_id: str,
    search_request_id: str,
    urls: tuple[str, ...],
    summaries: tuple[str, ...] = (),
    *,
    scope_run: RunRecord | None = None,
) -> RetrievalAdapterResponse:
    """Refetch each candidate through its registered parser; adopt only what passes.

    The strict path (ticket 19): the host must belong to a registered parser family, the
    page must yield the due period and a publication date no later than the run's cutoff,
    and for P0/P1 the search channel's own number must not be the parsed value misplaced.
    A rejected candidate stores no value; its raw response and reason stay on the record.
    """
    run = scope_run or RunRepository(paths.database).get(run_id)
    scope = run.retrieval_scope
    if scope is None:
        raise ValueError("retrieval_scope_required")
    version = str(
        ModelRepository(paths.database).manifest(run.model_version_id)["metric_catalog_version"]
    )
    ledger = RetrievalLedger(paths.database, scope_run=scope_run)
    snapshot = ledger.for_run(run_id)
    assert snapshot is not None
    parser = parser_for_scope(scope.metric_ids)
    lenient = scope.priority == "P2" and len(scope.metric_ids) == 1 and parser == "lenient"
    gap_ids = [
        g["gap_id"]
        for g in snapshot["gaps"]
        if (
            g["metric_id"] in scope.metric_ids
            and g["period"] == scope.period
            and g["as_of"] == run.system_as_of.astimezone(UTC).isoformat()
        )
    ]
    strict = scope.priority in {"P0", "P1"}
    # An official page does not restate what another source delivered (run findings
    # 2026-09-28, ticket 12).
    held = frozenset(ModelInputSelector(paths, run).select(scope).held_members)
    for index, url in enumerate(urls[:3]):
        summary = summaries[index] if index < len(summaries) else ""
        validation_id = "candidate-validation-" + uuid4().hex
        with database_connection(paths.database) as connection:
            duplicate = connection.execute(
                "SELECT validation_id FROM retrieval_candidate_validation "
                "WHERE run_id=? AND candidate_url=? AND gap_ids_json=? "
                "AND (outcome='model_usable' OR reason IN (?, ?, ?, ?, ?, ?)) LIMIT 1",
                (run_id, url, json.dumps(gap_ids), *_FINAL_REASONS, SEARCH_VALUE_MISMATCH),
            ).fetchone()
            connection.execute(
                "INSERT INTO retrieval_candidate_validation(validation_id, run_id, "
                "search_request_id, candidate_url, outcome, checked_at, gap_ids_json, "
                "selected_claim_ids_json, claim_ids_json) "
                "VALUES (?, ?, ?, ?, 'checking', ?, ?, '[]', '[]')",
                (
                    validation_id,
                    run_id,
                    search_request_id,
                    url,
                    utc_now().isoformat(),
                    json.dumps(gap_ids),
                ),
            )
            if duplicate is not None:
                connection.execute(
                    "UPDATE retrieval_candidate_validation SET outcome='not_model_usable', "
                    "reason='duplicate_candidate', reused_validation_id=? WHERE validation_id=?",
                    (duplicate[0], validation_id),
                )
        if duplicate is not None:
            continue
        claim_ids: list[str] = []
        errors: list[str] = []
        acquisitions: list[str] = []

        def admit(
            parsed: ParsedLprRelease | ParsedOfficialContextRelease, *, summary: str = summary
        ) -> None:
            published = parsed.public_available_at or parsed.release_at
            if published is None:
                raise CandidateRejected(NO_PUBLICATION_DATE)
            if published > run.system_as_of:
                raise CandidateRejected(DATE_AFTER_CUTOFF)
            values = tuple(
                item.value
                for item in (
                    parsed.observations if isinstance(parsed, ParsedLprRelease) else parsed.scalars
                )
            )
            if strict and search_value_conflicts(summary, values):
                raise CandidateRejected(SEARCH_VALUE_MISMATCH)

        def acquire(
            on_started: Callable[[str], None],
            *,
            url: str = url,
            claim_ids: list[str] = claim_ids,
            errors: list[str] = errors,
            acquisitions: list[str] = acquisitions,
            summary: str = summary,
        ) -> RetrievalAdapterResponse:
            def started(acquisition_id: str) -> None:
                acquisitions.append(acquisition_id)
                on_started(acquisition_id)

            try:
                if parser == "csindex" and len(scope.metric_ids) == 1:
                    claim_ids.extend(
                        _refetch_csindex_candidate(
                            paths,
                            run,
                            url,
                            summary,
                            definition_version=version,
                            on_acquisition_started=started,
                        )
                    )
                elif lenient:
                    claim_ids.extend(
                        _accept_lenient_candidate(
                            paths,
                            run,
                            url,
                            summary,
                            definition_version=version,
                            on_acquisition_started=started,
                        )
                    )
                elif media_outlet(url) is not None and not rules_for(scope.metric_ids):
                    # A media page, but the family has no news rule to read it by.
                    raise CandidateRejected(RULE_NOT_MATCHED)
                elif media_outlet(url) is not None:
                    claim_ids.extend(
                        _accept_media_candidate(
                            paths,
                            run,
                            url,
                            definition_version=version,
                            on_acquisition_started=started,
                        )
                    )
                elif parser == "lpr":
                    from pring_cycle.official_lpr import refresh_lpr_release

                    refreshed = refresh_lpr_release(
                        paths,
                        source_url=url,
                        expected_period=scope.period,
                        fetched_at=utc_now(),
                        definition_version=version,
                        on_acquisition_started=started,
                        admit=admit,
                    )
                    claim_ids.extend(refreshed.claim_ids)
                else:
                    from pring_cycle.official_context import (
                        official_family_for_metrics,
                        refresh_official_context_document,
                    )

                    context_refreshed = refresh_official_context_document(
                        paths,
                        family=official_family_for_metrics(scope.metric_ids),
                        source_url=url,
                        expected_period=scope.period,
                        fetched_at=utc_now(),
                        definition_version=version,
                        on_acquisition_started=started,
                        admit=admit,
                        held_members=held,
                    )
                    claim_ids.extend(context_refreshed.claim_ids)
            except (OSError, TypeError, ValueError) as error:
                errors.append(candidate_rejection_reason(error))
                raise
            return RetrievalAdapterResponse(
                "candidate_source", evidence=url, classification="document_validated"
            )

        response = ledger.trace_acquisition(
            run_id, "official", scope.release_event_id, url, acquire
        )
        selection = select_retrieval_input(paths, run)
        outcome = "model_usable" if claim_ids and selection.complete else "not_model_usable"
        reason = (
            errors[0]
            if errors
            else INCOMPLETE_MODEL_INPUT
            if outcome == "not_model_usable"
            else response.classification
        )
        with database_connection(paths.database) as connection:
            fetched = (
                connection.execute(
                    "SELECT parameters_json, raw_hash, parser_version FROM acquisition_request "
                    "WHERE acquisition_id=?",
                    (acquisitions[-1],),
                ).fetchone()
                if acquisitions
                else None
            )
            connection.execute(
                "UPDATE retrieval_candidate_validation SET outcome=?, reason=?, checked_at=?, "
                "download_request_id=?, claim_ids_json=?, selected_claim_ids_json=?, "
                "missing_members_json=?, fetched_url=?, raw_hash=?, parser_version=? "
                "WHERE validation_id=? AND outcome='checking'",
                (
                    outcome,
                    reason,
                    utc_now().isoformat(),
                    response.physical_request_id,
                    json.dumps(claim_ids),
                    json.dumps(selection.selected_claim_ids),
                    json.dumps(selection.missing_members),
                    json.loads(fetched[0]).get("source_url") if fetched else None,
                    fetched[1] if fetched else None,
                    fetched[2] if fetched else None,
                    validation_id,
                ),
            )
        if outcome == "model_usable":
            digest = hashlib.sha256(
                "\x1f".join(sorted(selection.selected_claim_ids)).encode()
            ).hexdigest()
            return RetrievalAdapterResponse(
                "verified",
                evidence=f"selected-evidence:{digest}",
                classification="complete_model_input",
            )
    return RetrievalAdapterResponse(
        "candidate_source",
        evidence=urls[0],
        classification="candidate_validation_unresolved",
        candidate_sources=urls,
    )


SEARCH_VERIFICATION_SCHEMA = """
CREATE TABLE retrieval_candidate_validation (
    validation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES parent_run(run_id),
    search_request_id TEXT NOT NULL REFERENCES retrieval_physical_request(request_id),
    candidate_url TEXT NOT NULL, outcome TEXT NOT NULL, reason TEXT, checked_at TEXT NOT NULL,
    reused_validation_id TEXT REFERENCES retrieval_candidate_validation(validation_id),
    download_request_id TEXT REFERENCES retrieval_physical_request(request_id),
    gap_ids_json TEXT NOT NULL, claim_ids_json TEXT NOT NULL, selected_claim_ids_json TEXT NOT NULL,
    missing_members_json TEXT,
    fetched_url TEXT, raw_hash TEXT, parser_version TEXT
);
"""
