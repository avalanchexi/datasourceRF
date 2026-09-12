from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date
from uuid import uuid4

from pring_cycle.catalog import metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS, require_registered_manifest
from pring_cycle.context_projection import TargetBoundEvidenceRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, MetricSeriesPoint
from pring_cycle.market_breadth import DAILY_BREADTH_MEASURES, breadth_claims_matching_acquisitions
from pring_cycle.metric_contracts import (
    EFFECTIVE_UNTIL_CHANGED_METRICS,
    evidence_max_age_days,
    required_dimension_members,
)
from pring_cycle.models import ModelRepository
from pring_cycle.official_lpr import lpr_claims_matching_acquisitions
from pring_cycle.published_events import select_published_rrr_events
from pring_cycle.retrieval import RetrievalAdapterResponse, matches_retrieval_period
from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import (
    CORE_API_IDENTITIES,
    CoreInputValidator,
    selected_core_claim_is_valid,
)
from pring_cycle.storage import database_connection
from pring_cycle.tushare_context import (
    MARKET_INDEX_IDENTITIES,
    parse_market_index_acquisition,
    parse_valuation_acquisition,
    tushare_claims_matching_acquisitions,
)
from pring_cycle.warrant_inputs import select_warrant_inputs


@dataclass(frozen=True)
class ModelInputSelection:
    complete: bool
    selected_claim_ids: tuple[str, ...]
    missing_members: tuple[str, ...]


def select_retrieval_input(
    paths: RuntimePaths, run: RunRecord, *, mode: AsOfMode = AsOfMode.SYSTEM
) -> ModelInputSelection:
    scope = run.retrieval_scope
    if scope is None:
        raise ValueError("retrieval_scope_required")
    return ModelInputSelector(paths, run, mode=mode).select(scope)


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
            EvidenceRepository(paths.database), date.fromisoformat(run.target_business_date), {}
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

    def select(self, scope: RetrievalScope) -> ModelInputSelection:
        core_inputs = CoreInputValidator(
            self.core_evidence,
            tuple(
                point.selected_claim_id
                for metric_id in scope.metric_ids
                if metric_id in CORE_API_IDENTITIES and self.version not in BUILTIN_CATALOG_VERSIONS
                for point in self.series(metric_id)
                if point.selected_claim_id is not None
                and matches_retrieval_period(point.period_end, scope.period)
            ),
        )
        valid_lpr_claim_ids = lpr_claims_matching_acquisitions(
            self.core_evidence,
            tuple(
                point
                for metric_id in scope.metric_ids
                if metric_id == "CN_LPR_1Y_5Y" and self.version not in BUILTIN_CATALOG_VERSIONS
                for point in self.series(metric_id)
                if point.selected_claim_id is not None
            ),
        )
        valid_margin_claim_ids = tushare_claims_matching_acquisitions(
            self.core_evidence,
            self.series("CN_MARGIN_BALANCE")
            if "CN_MARGIN_BALANCE" in scope.metric_ids
            and self.version not in BUILTIN_CATALOG_VERSIONS
            else (),
            definition_version=self.version,
        )
        valid_market_claim_ids = tushare_claims_matching_acquisitions(
            self.core_evidence,
            tuple(
                point
                for metric_id in scope.metric_ids
                if metric_id in MARKET_INDEX_IDENTITIES
                and self.version not in BUILTIN_CATALOG_VERSIONS
                for point in self.series(metric_id)
            ),
            definition_version=self.version,
            parse=parse_market_index_acquisition,
        )
        valid_valuation_claim_ids = tushare_claims_matching_acquisitions(
            self.core_evidence,
            self.series("CN_INDEX_VALUATION")
            if "CN_INDEX_VALUATION" in scope.metric_ids
            and self.version not in BUILTIN_CATALOG_VERSIONS
            else (),
            definition_version=self.version,
            parse=parse_valuation_acquisition,
        )
        valid_breadth_claim_ids = breadth_claims_matching_acquisitions(
            self.core_evidence,
            tuple(
                point
                for metric in scope.metric_ids
                if metric in DAILY_BREADTH_MEASURES and self.version not in BUILTIN_CATALOG_VERSIONS
                for point in self.series(metric)
            ),
            definition_version=self.version,
            artifacts=self.database_path.parent / "artifacts" / "sha256",
        )
        selected_ids: list[str] = []
        missing = []
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
                if definition.certification_status != "certified":
                    missing.append("CN_FUTURES_WARRANTS:source_certification_required")
                else:
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
                if definition.certification_status != "certified":
                    missing.append("CN_RRR_EVENT:source_certification_required")
                else:
                    selected_ids.extend(result.selected_claim_ids)
                    missing.extend(result.missing_members)
                continue
            expected = required_dimension_members(
                metric_id, definition_version=self.version, period=scope.period
            )
            if expected is None:
                if definition.dimensions:
                    missing.append(f"{metric_id}:dimension_contract_unavailable")
                    continue
                expected = ({},)
            points = self.series(metric_id)
            for member in expected:
                event_metric = metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS
                event_limit = (
                    f"{scope.period[:4]}-{int(scope.period[-1]) * 3:02d}"
                    if "-Q" in scope.period
                    else scope.period
                )
                matches = [
                    p
                    for p in points
                    if (
                        (
                            p.period_end[: len(event_limit)] <= event_limit
                            if event_metric
                            else matches_retrieval_period(p.period_end, scope.period)
                        )
                        and p.dimensions == member
                    )
                ]
                if event_metric and matches:
                    # Pick the latest known event before checking quality. A bad
                    # newer event must not silently resurrect an older rate.
                    latest = max(p.period_end for p in matches)
                    matches = [p for p in matches if p.period_end == latest]
                    if (
                        date.fromisoformat(self.target_business_date) - date.fromisoformat(latest)
                    ).days > evidence_max_age_days(metric_id, definition.frequency):
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
                        and claim.certification_status == "certified"
                        and claim.quality_status == "validated"
                        and definition.certification_status == "certified"
                        and (
                            metric_id not in DAILY_BREADTH_MEASURES
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or claim.claim_id in valid_breadth_claim_ids
                        )
                        and (
                            metric_id != "CN_INDEX_VALUATION"
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or claim.claim_id in valid_valuation_claim_ids
                        )
                        and (
                            metric_id not in MARKET_INDEX_IDENTITIES
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or claim.claim_id in valid_market_claim_ids
                        )
                        and (
                            metric_id != "CN_MARGIN_BALANCE"
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or claim.claim_id in valid_margin_claim_ids
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
                        and (
                            metric_id != "CN_LPR_1Y_5Y"
                            or self.version in BUILTIN_CATALOG_VERSIONS
                            or claim.claim_id in valid_lpr_claim_ids
                        )
                    ):
                        accepted.append(claim.claim_id)
                if len(accepted) == 1:
                    selected_ids.extend(accepted)
                else:
                    missing.append(f"{metric_id}:{json.dumps(member, sort_keys=True)}")
        return ModelInputSelection(
            not missing and bool(selected_ids), tuple(selected_ids), tuple(missing)
        )


def verify_search_candidates(
    paths: RuntimePaths,
    run_id: str,
    search_request_id: str,
    urls: tuple[str, ...],
    *,
    scope_run: RunRecord | None = None,
) -> RetrievalAdapterResponse:
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
    gap_ids = [
        g["gap_id"]
        for g in snapshot["gaps"]
        if (
            g["metric_id"] in scope.metric_ids
            and g["period"] == scope.period
            and g["as_of"] == run.system_as_of.astimezone(UTC).isoformat()
        )
    ]
    for url in urls[:3]:
        validation_id = "candidate-validation-" + uuid4().hex
        with database_connection(paths.database) as connection:
            attempt = connection.execute(
                "SELECT COUNT(*) FROM run_attempt WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            duplicate = connection.execute(
                "SELECT validation_id FROM retrieval_candidate_validation "
                "WHERE run_id=? AND run_attempt=? AND candidate_url=? "
                "AND gap_ids_json=? LIMIT 1",
                (run_id, attempt, url, json.dumps(gap_ids)),
            ).fetchone()
            connection.execute(
                "INSERT INTO retrieval_candidate_validation(validation_id, run_id, "
                "search_request_id, candidate_url, outcome, checked_at, gap_ids_json, "
                "selected_claim_ids_json, claim_ids_json, run_attempt) "
                "VALUES (?, ?, ?, ?, 'checking', ?, ?, '[]', '[]', ?)",
                (
                    validation_id,
                    run_id,
                    search_request_id,
                    url,
                    utc_now().isoformat(),
                    json.dumps(gap_ids),
                    attempt,
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

        def acquire(
            on_started: Callable[[str], None],
            *,
            url: str = url,
            claim_ids: list[str] = claim_ids,
            errors: list[str] = errors,
        ) -> RetrievalAdapterResponse:
            try:
                if scope.metric_ids == ("CN_LPR_1Y_5Y",):
                    from pring_cycle.official_lpr import refresh_lpr_release

                    refreshed = refresh_lpr_release(
                        paths,
                        source_url=url,
                        expected_period=scope.period,
                        fetched_at=utc_now(),
                        definition_version=version,
                        on_acquisition_started=on_started,
                        parser_text_limit=1600,
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
                        on_acquisition_started=on_started,
                        parser_text_limit=1600,
                    )
                    claim_ids.extend(context_refreshed.claim_ids)
            except (OSError, TypeError, ValueError) as error:
                errors.append(str(error))
                raise
            return RetrievalAdapterResponse(
                "candidate_source", evidence=url, classification="document_validated"
            )

        response = ledger.trace_acquisition(
            run_id, "official", scope.release_event_id, url, acquire
        )
        selection = select_retrieval_input(paths, run)
        public_selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
        outcome = "model_usable" if claim_ids and selection.complete else "not_model_usable"
        reason = errors[0] if errors else response.classification
        with database_connection(paths.database) as connection:
            connection.execute(
                "UPDATE retrieval_candidate_validation SET outcome=?, reason=?, checked_at=?, "
                "download_request_id=?, claim_ids_json=?, selected_claim_ids_json=?, "
                "missing_members_json=?, "
                "public_complete=?, public_selected_claim_ids_json=? "
                "WHERE validation_id=? AND outcome='checking'",
                (
                    outcome,
                    reason,
                    utc_now().isoformat(),
                    response.physical_request_id,
                    json.dumps(claim_ids),
                    json.dumps(selection.selected_claim_ids),
                    json.dumps(selection.missing_members),
                    public_selection.complete,
                    json.dumps(public_selection.selected_claim_ids),
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
    run_attempt INTEGER NOT NULL,
    reused_validation_id TEXT REFERENCES retrieval_candidate_validation(validation_id),
    download_request_id TEXT REFERENCES retrieval_physical_request(request_id),
    gap_ids_json TEXT NOT NULL, claim_ids_json TEXT NOT NULL, selected_claim_ids_json TEXT NOT NULL,
    missing_members_json TEXT,
    public_complete INTEGER NOT NULL DEFAULT 0,
    public_selected_claim_ids_json TEXT NOT NULL DEFAULT '[]'
);
"""
