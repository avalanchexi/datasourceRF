from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import TargetBoundEvidenceRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.metric_contracts import REQUIRED_DIMENSION_MEMBERS
from pring_cycle.models import ModelRepository
from pring_cycle.retrieval import RetrievalAdapterResponse, matches_retrieval_period
from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
from pring_cycle.runs import RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths


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
    version = str(
        ModelRepository(paths.database).manifest(run.model_version_id)["metric_catalog_version"]
    )
    evidence = TargetBoundEvidenceRepository(
        EvidenceRepository(paths.database), date.fromisoformat(run.target_business_date), {}
    )
    selected_ids = []
    missing = []
    for metric_id in scope.metric_ids:
        definition = metric_definition(metric_id, definition_version=version)
        expected = REQUIRED_DIMENSION_MEMBERS.get(metric_id)
        if expected is None:
            if definition.dimensions:
                missing.append(f"{metric_id}:dimension_contract_unavailable")
                continue
            expected = ({},)
        points = evidence.metric_series(
            metric_id, mode=mode, as_of=run.system_as_of, definition_version=version
        )
        for member in expected:
            matches = [
                p
                for p in points
                if matches_retrieval_period(p.period_end, scope.period) and p.dimensions == member
            ]
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
) -> RetrievalAdapterResponse:
    run = RunRepository(paths.database).get(run_id)
    scope = run.retrieval_scope
    if scope is None:
        raise ValueError("retrieval_scope_required")
    version = str(
        ModelRepository(paths.database).manifest(run.model_version_id)["metric_catalog_version"]
    )
    ledger = RetrievalLedger(paths.database)
    snapshot = ledger.for_run(run_id)
    assert snapshot is not None
    gap_ids = [g["gap_id"] for g in snapshot["gaps"]]
    for url in urls[:3]:
        validation_id = "candidate-validation-" + uuid4().hex
        with sqlite3.connect(paths.database) as connection:
            attempt = connection.execute(
                "SELECT COUNT(*) FROM run_attempt WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            duplicate = connection.execute(
                "SELECT validation_id FROM retrieval_candidate_validation "
                "WHERE run_id=? AND run_attempt=? AND candidate_url=? LIMIT 1",
                (run_id, attempt, url),
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
        with sqlite3.connect(paths.database) as connection:
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
