from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import own_acquisitions
from pring_cycle.catalog import MetricDefinition
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.full_run_requirements import (
    formula_requirements,
    preceding_periods,
    required_calendar,
)
from pring_cycle.metric_contracts import evidence_frequency
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.retrieval import RetrievalBudget, RetrievalRequest, run_retrieval_cascade
from pring_cycle.retrieval_ledger import RetrievalLedger, utc_now
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector, select_retrieval_input


class FullRunRetrieval:
    """Persist the plan before calls, evaluate once, and link publication separately."""

    def __init__(self, paths: RuntimePaths) -> None:
        self.paths = paths

    def retrieve(self, run: RunRecord) -> None:
        from pring_cycle.worker import _production_retrieval_adapters, _retrieval_release_status

        plan = read_full_retrieval_plan(self.paths.database, run.run_id)
        if plan["final"] is not None:
            return
        if plan["initial"] is None:
            initial = self._plan(run)
            self._record(run.run_id, "initial", initial)
        else:
            initial = plan["initial"]
        version = str(initial["definition_version"])
        runs = RunRepository(self.paths.database)
        for document in initial["scopes"]:
            scope = _scope(document)
            scoped = replace(run, retrieval_scope=scope)
            # Publication is bounded to what the target market could have known.
            known_at = (
                utc_now()
                if run.cutoff_mode == "acquisition_window" and not run.cutoffs_frozen
                else run.system_as_of
            )
            release = _retrieval_release_status(
                self.paths,
                scope,
                known_at,
                definition_version=version,
                public_as_of=min(known_at, utc_now(), _target_end(run)),
            )
            if release != "released":
                if release == document["release_status"]:
                    continue
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
            if runs.get(run.run_id).status != "running":
                raise ValueError("full_retrieval_run_not_running")
            ledger = RetrievalLedger(self.paths.database, scope_run=scoped)
            ledger.bind_run(scoped, version)
            if select_retrieval_input(self.paths, scoped).complete:
                continue
            consumed = runs.get(run.run_id).consumed_budget
            daily = runs.daily_budget_consumption(utc_now())
            budget = RetrievalBudget(
                run_tavily_remaining=max(0, 8 - consumed["tavily"]),
                run_exa_remaining=max(0, 4 - consumed["exa"]),
                run_ai_remaining=max(0, 1 - consumed["ai_websearch"]),
                daily_tavily_remaining=max(0, 16 - daily["tavily"]),
                daily_exa_remaining=max(0, 8 - daily["exa"]),
                daily_ai_remaining=max(0, 2 - daily["ai_websearch"]),
            )
            with own_acquisitions(
                self.paths.database,
                run.run_id,
                "gap_retrieval",
                metric_ids=scope.metric_ids,
                period=scope.period,
            ):
                result = run_retrieval_cascade(
                    RetrievalRequest(
                        release_event_id=scope.release_event_id,
                        metric_ids=scope.metric_ids,
                        priority=scope.priority,
                        released=True,
                        persistent_accounting=True,
                    ),
                    _production_retrieval_adapters(
                        self.paths,
                        scope,
                        utc_now(),
                        definition_version=version,
                        run_id=run.run_id,
                        scope_run=scoped,
                    ),
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

    def _plan(self, run: RunRecord) -> dict[str, Any]:
        from pring_cycle.worker import _retrieval_release_status

        rules = ContextProjectionRules.from_manifest(
            ModelRepository(self.paths.database).manifest(run.model_version_id)
        )
        groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        requirements: list[dict[str, Any]] = []
        selector = ModelInputSelector(self.paths, run)
        calendar = required_calendar(self.paths, run, selector)
        daily_window = tuple(calendar["dates"])
        period_by_metric = {
            definition.metric_id: self._period(run, definition, selector)
            for definition in rules.metric_definitions
        }
        history_counts, derived = formula_requirements(rules, selector, period_by_metric)
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
            if definition.metric_id in derived_ids:
                continue
            if definition.certification_status == "derived_from_certified_inputs":
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
            periods = (
                daily_window
                if (
                    definition.priority in {"P0", "P1"}
                    and evidence_frequency(definition.metric_id, definition.frequency) == "daily"
                    and len(daily_window) == 120
                )
                else preceding_periods(period, history_counts.get(definition.metric_id, 1))
            )
            for required_period in periods:
                scope = RetrievalScope(
                    f"full:{definition.release_event_family}:{required_period}",
                    (definition.metric_id,),
                    required_period,
                    definition.priority,
                    None,
                )
                selection = selector.select(scope)
                requirements.append(
                    {
                        "metric_id": definition.metric_id,
                        "period": required_period,
                        "status": "local_complete" if selection.complete else "model_input_missing",
                        "selected_claim_ids": list(selection.selected_claim_ids),
                        "missing_members": list(selection.missing_members),
                    }
                )
                if not selection.complete:
                    groups[
                        (definition.release_event_family, required_period, definition.priority)
                    ].append(definition.metric_id)
        scopes = [
            asdict(
                RetrievalScope(
                    f"full:{family}:{period}", tuple(sorted(metrics)), period, priority, None
                )
            )
            for (family, period, priority), metrics in sorted(
                groups.items(), key=lambda item: (item[0][2], item[0])
            )
        ]
        for document in scopes:
            document["release_status"] = _retrieval_release_status(
                self.paths,
                _scope(document),
                selector.as_of,
                definition_version=rules.metric_catalog_version,
                public_as_of=min(selector.as_of, utc_now(), _target_end(run)),
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
        self, run: RunRecord, definition: MetricDefinition, selector: ModelInputSelector
    ) -> str | None:
        target = date.fromisoformat(run.target_business_date)
        frequency = evidence_frequency(definition.metric_id, definition.frequency)
        if definition.metric_id == "CN_LPR_1Y_5Y":
            return run.target_business_date[:7]
        if frequency == "daily":
            return run.target_business_date
        points = selector.series(definition.metric_id)
        published = [p.period_end for p in points if p.period_start <= run.target_business_date]
        if frequency == "event":
            return max(published) if published else None
        if frequency == "quarterly":
            period = (
                date.fromisoformat(max(published))
                if published
                else date(target.year, ((target.month - 1) // 3) * 3 + 1, 1) - timedelta(days=1)
            )
            return f"{period.year}-Q{(period.month - 1) // 3 + 1}"
        if frequency == "monthly":
            return (
                max(published)[:7]
                if published
                else (target.replace(day=1) - timedelta(days=1)).isoformat()[:7]
            )
        return None

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
        for document in initial["scopes"]:
            scope = _scope(document)
            scoped = replace(run, retrieval_scope=scope)
            if any((metric, scope.period) in bound for metric in scope.metric_ids):
                ledger.bind_run(scoped, initial["definition_version"])
        for requirement in final_plan["requirements"]:
            if "period" not in requirement:
                continue
            metric, period = requirement["metric_id"], requirement["period"]
            selection = selector.select(RetrievalScope("evaluation", (metric,), period, "P1", None))
            gaps.append(
                {
                    "metric_id": metric,
                    "period": period,
                    "complete": selection.complete,
                    "selected_claim_ids": list(selection.selected_claim_ids),
                    "missing_members": list(selection.missing_members),
                }
            )
        snapshot = ledger.for_run(run.run_id)
        if snapshot is not None:
            with sqlite3.connect(self.paths.database) as connection:
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
                        "input_coverage_complete": bool(r["required_input_periods"])
                        and all(
                            g["complete"]
                            for g in gaps
                            if g["metric_id"] in r["required_input_periods"]
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
        with sqlite3.connect(self.paths.database) as connection:
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
        with sqlite3.connect(self.paths.database) as connection:
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


def read_full_retrieval_plan(database: Path, run_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {"initial": None, "final": None, "adoption": None, "acquisitions": []}
    with sqlite3.connect(database) as connection:
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
            result[phase] = json.loads(document)
        connection.row_factory = sqlite3.Row
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='full_run_acquisition' "
            "AND EXISTS (SELECT 1 FROM sqlite_master WHERE name='acquisition_request')"
        ).fetchone():
            for row in connection.execute(
                "SELECT owner.*, a.provider, a.api_name, a.state, a.raw_hash, a.normalized_hash, "
                "a.error_type FROM full_run_acquisition owner JOIN acquisition_request a "
                "USING(acquisition_id) WHERE owner.run_id=? ORDER BY owner.rowid",
                (run_id,),
            ):
                request = dict(row)
                request["metric_ids"] = json.loads(request.pop("metric_ids_json"))
                result["acquisitions"].append(request)
    return result


def _scope(document: dict[str, Any]) -> RetrievalScope:
    return RetrievalScope(
        document["release_event_id"],
        tuple(document["metric_ids"]),
        document["period"],
        document["priority"],
        document["source_url"],
    )


def _target_end(run: RunRecord) -> datetime:
    return datetime.combine(
        date.fromisoformat(run.target_business_date), time.max, tzinfo=ZoneInfo("Asia/Shanghai")
    )


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
