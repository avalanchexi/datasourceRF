"""Read-only diagnostics for an admitted candidate's lifecycle inputs."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS, require_registered_manifest
from pring_cycle.context_projection import ContextProjectionRules, build_context_projection
from pring_cycle.context_replay_scope import (
    CONTEXT_FORMULA_INPUTS,
    CONTEXT_FORMULA_OUTPUTS,
    ContextReplayScope,
    context_input_warmup_days,
    find_formula_documents,
)
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.full_run_requirements import (
    formula_requirements,
    preceding_periods,
    required_calendar,
)
from pring_cycle.futures_input_reads import shared_futures_input_reads
from pring_cycle.metric_contracts import (
    evidence_frequency,
    evidence_max_age_days,
    minimum_context_daily_observations,
)
from pring_cycle.model_evaluation import model_history_input_start
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RetrievalScope, RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.source_adapters import CoreInputValidator, TushareCoreAdapter


def public_cutoff(day: date | str) -> datetime:
    """The instant a session's public knowledge is read at, in the market's own zone."""
    session = date.fromisoformat(day) if isinstance(day, str) else day
    return datetime.combine(session, time.max, tzinfo=ZoneInfo("Asia/Shanghai"))


def preflight_model_inputs(
    paths: RuntimePaths, model_version_id: str, *, requested_start: str, requested_end: str
) -> dict[str, Any]:
    # This inspection neither captures nor changes inputs. Share their verified
    # contents across cutoffs, but release the scope before another inspection.
    with shared_futures_input_reads():
        return _preflight_model_inputs(
            paths, model_version_id, requested_start=requested_start, requested_end=requested_end
        )


def _preflight_model_inputs(
    paths: RuntimePaths, model_version_id: str, *, requested_start: str, requested_end: str
) -> dict[str, Any]:
    start, end = date.fromisoformat(requested_start), date.fromisoformat(requested_end)
    if start > end:
        raise ValueError("material_preflight_range_empty")
    models = ModelRepository(paths.database)
    model = models.get(model_version_id)
    manifest = models.manifest(model_version_id)
    require_registered_manifest(paths.database, manifest)
    rules = ContextProjectionRules.from_manifest(manifest)
    formula_scope = ContextReplayScope.from_manifests(manifest, manifest)
    evidence = EvidenceRepository(paths.database)
    gaps: list[dict[str, Any]] = []
    optional_gaps: list[dict[str, Any]] = []
    cutoff = public_cutoff(end)
    run = RunRecord(
        run_id="material-preflight",
        command_type="manual_full",
        target_business_date=end.isoformat(),
        model_version_id=model_version_id,
        system_as_of=cutoff,
        report_cutoff=cutoff,
        status="queued",
        current_step="preflight",
        outcome=None,
        recoverable=False,
        next_action="",
        attempt_count=0,
        consumed_budget={},
        projection_set_id=None,
        error_classification=None,
        retrieval_scope=None,
        retrieval_attempts=(),
        cutoffs_frozen=True,
    )
    observed_at = datetime.now(UTC)
    calendar_run = replace(run, system_as_of=observed_at)
    # The calendar is operational evidence captured by this inspection time.
    # Historical economic values below still use each day's PUBLIC cutoff.
    calendar = _calendar_material(
        paths, calendar_run, ModelInputSelector(paths, calendar_run), start=start, end=end
    )
    if calendar["status"] != "available":
        gaps.append({"metric_id": "CN_TRADE_CALENDAR", "reason": str(calendar["basis"])})
    checked_days = tuple(
        day for day in calendar["dates"] if start.isoformat() <= day <= end.isoformat()
    ) or (end.isoformat(),)
    present = []
    density_missing: dict[str, set[str]] = {}
    # These carry no scalar to score, but dropping them would make a P0 the preflight
    # never looked at read exactly like one that passed. The run planner lists them too.
    operational_evidence: list[dict[str, Any]] = []
    for definition in rules.metric_definitions:
        if definition.role == "operational_evidence" or definition.metric_id in {
            "CN_TRADE_CALENDAR",
            "CN_RELEASE_SCHEDULE",
            "SOURCE_OBSERVED_AVAILABILITY",
        }:
            operational_evidence.append(
                {"metric_id": definition.metric_id, "status": "operational_evidence"}
            )
            continue
        if definition.certification_status == "derived_from_certified_inputs":
            continue
        vintages = evidence.source_claim_vintages(
            definition.metric_id, definition_version=rules.metric_catalog_version
        )
        destination = (
            optional_gaps
            if definition.priority == "P2"
            and definition.metric_id not in formula_scope.requires_certification
            else gaps
        )
        if not vintages:
            destination.append(
                {"metric_id": definition.metric_id, "reason": "source_material_missing"}
            )
            continue
        warmup_days = context_input_warmup_days(definition.metric_id, set(rules.formula_versions))
        if warmup_days:
            required_start = start - timedelta(days=warmup_days)
            valid_history = [
                item
                for item in vintages
                if item.certification_status == "certified"
                and item.quality_status == "validated"
                and item.public_available_at is not None
            ]
            if (
                not valid_history
                or min(date.fromisoformat(item.period_start) for item in valid_history)
                > required_start
                or min(
                    item.public_available_at.date()
                    for item in valid_history
                    if item.public_available_at is not None
                )
                > start
            ):
                destination.append(
                    {
                        "metric_id": definition.metric_id,
                        "reason": "input_warmup_missing",
                        "required_start": required_start.isoformat(),
                        "business_date": start.isoformat(),
                    }
                )
        present.append(definition)
        if evidence_frequency(definition.metric_id, definition.frequency) == "daily":
            observed = {
                item.period_end
                for item in vintages
                if item.certification_status == "certified"
                and item.quality_status == "validated"
                and item.period_end in checked_days
                # Coverage is point in time: a value first published after its own
                # session was not observable that day, whatever time it carries.
                and item.public_available_at is not None
                and item.public_available_at <= public_cutoff(item.period_end)
            }
            minimum = (
                len(checked_days)
                if definition.role == "core_barometer"
                else minimum_context_daily_observations(len(checked_days))
            )
            if len(observed) < minimum:
                density_missing[definition.metric_id] = set(checked_days) - observed

    gaps.extend(
        _core_history_gaps(
            evidence,
            manifest,
            rules.metric_catalog_version,
            start=start,
            end=end,
            calendar_days=tuple(calendar.get("history_dates", ()))
            if calendar["status"] == "available"
            else (),
        )
    )

    # Keep only one day's cached series alive during a full window diagnostic.
    for day in checked_days:
        historical_cutoff = public_cutoff(day)
        historical_selector = ModelInputSelector(
            paths,
            replace(
                run,
                target_business_date=day,
                system_as_of=historical_cutoff,
                report_cutoff=historical_cutoff,
            ),
            mode=AsOfMode.PUBLIC,
        )
        for definition in present:
            destination = (
                optional_gaps
                if definition.priority == "P2"
                and definition.metric_id not in formula_scope.requires_certification
                else gaps
            )
            visible = historical_selector.series(definition.metric_id)
            period = max((point.period_end for point in visible), default=day)
            if day in density_missing.get(definition.metric_id, set()):
                destination.append(
                    {
                        "metric_id": definition.metric_id,
                        "reason": "daily_coverage_missing",
                        "business_date": day,
                    }
                )
            selected = historical_selector.select(
                RetrievalScope(
                    release_event_id="material-preflight",
                    metric_ids=(definition.metric_id,),
                    period=period,
                    priority=definition.priority,
                    source_url=None,
                )
            )
            if not selected.complete:
                destination.append(
                    {
                        "metric_id": definition.metric_id,
                        "reason": "input_selection_missing",
                        "business_date": day,
                        "period": period,
                        "missing_members": ";".join(selected.missing_members),
                    }
                )
            elif (
                date.fromisoformat(day) - date.fromisoformat(period)
            ).days > evidence_max_age_days(definition.metric_id, definition.frequency):
                destination.append(
                    {
                        "metric_id": definition.metric_id,
                        "reason": "input_stale",
                        "business_date": day,
                        "period": period,
                    }
                )

        formula_inputs = {
            metric
            for key in rules.formula_versions
            for metric in CONTEXT_FORMULA_INPUTS.get(key, ())
        }
        document: dict[str, Any] = {}
        projection_error = None
        if any(definition.metric_id in formula_inputs for definition in present):
            try:
                projection = build_context_projection(
                    evidence,
                    model_manifest=manifest,
                    target_business_date=day,
                    as_of=historical_cutoff,
                    as_of_mode=AsOfMode.PUBLIC,
                    persist_derived=False,
                )
                document = {"macro": projection.macro, "inventory": projection.inventory}
            except ValueError as error:
                projection_error = str(error)
        parent_diagnostics = None
        for key, version in rules.formula_versions.items():
            destination = gaps if key in formula_scope.required_formula_keys else optional_gaps
            documents = find_formula_documents(document, version)
            available = [
                item for item in documents if item.get("status") in {"available", "current"}
            ]
            reason = None
            if not available:
                reason = "formula_inputs_unavailable"
            elif not any(
                isinstance(item.get("input_observation_version_ids"), list)
                and item["input_observation_version_ids"]
                for item in available
            ):
                reason = "formula_lineage_missing"
            if reason is not None:
                if parent_diagnostics is None:
                    parent_diagnostics = _parent_material_diagnostics(
                        rules, historical_selector, evidence
                    )
                details = parent_diagnostics.get(version, {})
                gap: dict[str, Any] = {
                    "metric_id": CONTEXT_FORMULA_OUTPUTS[key],
                    "reason": reason,
                    "formula_version": version,
                    "business_date": day,
                    "missing_input_periods": details.get("missing_input_periods", {}),
                    "invalid_parent_claims": details.get("invalid_parent_claims", []),
                }
                if projection_error is not None:
                    gap["error"] = projection_error
                destination.append(gap)

    # Until all guards run, this diagnostic must never issue a readiness verdict.
    # In particular, existing rows alone prove neither original integrity nor
    # historical visibility, dimension coverage or complete derived parents.
    return {
        "model_version_id": model_version_id,
        "manifest_hash": model.manifest_hash,
        "inspected_at": observed_at.isoformat(),
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "status": "blocked" if gaps else "incomplete",
        "checks_complete": False,
        "checked_business_dates": checked_days,
        "pending_checks": ["calendar", "originals", "dimensions", "point_in_time", "parents"],
        "gaps": gaps,
        "optional_gaps": optional_gaps,
        "operational_evidence": sorted(operational_evidence, key=lambda item: item["metric_id"]),
        "calendar": calendar,
    }


def _core_history_gaps(
    evidence: EvidenceRepository,
    manifest: dict[str, Any],
    version: str,
    *,
    start: date,
    end: date,
    calendar_days: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Check the PUBLIC price prefixes calibration consumes, without computing trends."""
    metrics = tuple(str(metric) for metric in manifest["core_metrics"].values())
    history_start = model_history_input_start(manifest, start.isoformat())
    vintages = {
        metric: tuple(
            item
            for item in evidence.source_claim_vintages(metric, definition_version=version)
            if history_start <= item.period_end <= end.isoformat()
        )
        for metric in metrics
    }
    days = sorted(
        {item.period_end for values in vintages.values() for item in values}
        | {day for day in calendar_days if history_start <= day <= end.isoformat()}
    )
    evidence.preload_metric_series({(metric, version) for metric in metrics})
    originals = CoreInputValidator(
        evidence, tuple(item.claim_id for values in vintages.values() for item in values)
    )
    gaps: dict[tuple[str, str, str | None, str], dict[str, Any]] = {}
    for index, day in enumerate(days):
        cutoff = public_cutoff(day)
        for metric in metrics:
            if not vintages[metric]:
                continue  # The inventory check already reports this wholly missing source.
            visible = {
                point.period_end: point
                for point in evidence.metric_series(
                    metric, definition_version=version, mode=AsOfMode.PUBLIC, as_of=cutoff
                )
                if history_start <= point.period_end <= day
            }
            for period in days[: index + 1]:
                point = visible.get(period)
                reason = None
                if (
                    point is None
                    or point.selection_status != "selected"
                    or point.selected_value is None
                    or point.selected_value <= 0
                    or point.value_state is not EvidenceValueState.REPORTED_VALUE
                    or not any(
                        claim.claim_id == point.selected_claim_id
                        and claim.certification_status == "certified"
                        and claim.quality_status == "validated"
                        for claim in point.claims
                    )
                ):
                    reason = "core_history_input_missing"
                elif version not in BUILTIN_CATALOG_VERSIONS and not originals.is_valid(
                    metric, point
                ):
                    reason = "core_history_original_invalid"
                if reason is not None:
                    claim_id = point.selected_claim_id if point is not None else None
                    gaps.setdefault(
                        (metric, period, claim_id, reason),
                        {
                            "metric_id": metric,
                            "reason": reason,
                            "period": period,
                            "business_date": day,
                            "claim_id": claim_id,
                        },
                    )
    return list(gaps.values())


def _parent_material_diagnostics(
    rules: ContextProjectionRules, selector: ModelInputSelector, evidence: EvidenceRepository
) -> dict[str, dict[str, Any]]:
    """Explain unavailable formulas without treating existing rows as valid parents."""
    inputs = {
        metric for key in rules.formula_versions for metric in CONTEXT_FORMULA_INPUTS.get(key, ())
    }
    frequencies = {item.metric_id: item.frequency for item in rules.metric_definitions}
    observed: dict[str, set[str]] = {}
    claims: dict[str, dict[str, list[str]]] = {}
    for metric in inputs:
        periods = set()
        claims[metric] = {}
        for point in selector.series(metric):
            end = date.fromisoformat(point.period_end)
            frequency = evidence_frequency(metric, frequencies[metric])
            if frequency == "quarterly":
                period = f"{end.year}-Q{(end.month - 1) // 3 + 1}"
            elif frequency == "monthly":
                period = point.period_end[:7]
            else:
                period = point.period_end
            periods.add(period)
            if point.selected_claim_id is not None:
                claims[metric].setdefault(period, []).append(point.selected_claim_id)
        observed[metric] = periods
    latest = {metric: max(periods) if periods else None for metric, periods in observed.items()}
    _, requirements = formula_requirements(rules, selector, latest)
    result: dict[str, dict[str, Any]] = {}
    selected: dict[str, list[dict[str, str]]] = {}
    for requirement in requirements:
        version = requirement["formula_version"]
        selected[version] = []
        missing = {}
        for metric, count in requirement["required_input_periods"].items():
            latest_period = latest[metric]
            if latest_period is None:
                continue  # The metric-level diagnostic already names the wholly missing source.
            required = preceding_periods(latest_period, count)
            absent = [p for p in required if p not in observed[metric]]
            selected[version].extend(
                {"metric_id": metric, "period": p, "claim_id": claim_id}
                for p in required
                for claim_id in claims[metric].get(p, ())
            )
            if absent:
                missing[metric] = absent
        result[version] = {"missing_input_periods": missing}
    originals = evidence.source_claim_acquisitions_many(
        tuple({item["claim_id"] for rows in selected.values() for item in rows})
    )
    for version, rows in selected.items():
        result[version]["invalid_parent_claims"] = [
            item for item in rows if not originals.get(item["claim_id"])
        ]
    return result


def _calendar_material(
    paths: RuntimePaths, run: RunRecord, selector: ModelInputSelector, *, start: date, end: date
) -> dict[str, Any]:
    try:
        calendar = required_calendar(paths, run, selector)
        if calendar["status"] != "available":
            return calendar
        acquisition_id = calendar["provenance"]["acquisition_id"]
        if acquisition_id is not None:
            acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
            receipt = acquisitions.get(acquisition_id)
            raw = acquisitions.read_receipt_content(receipt, "raw")
            normalized = json.loads(acquisitions.read_receipt_content(receipt, "normalized"))
            parsed = TushareCoreAdapter(
                "archived-calendar", transport=lambda _request: raw
            ).trading_days(
                date.fromisoformat(str(receipt.parameters["start_date"])),
                date.fromisoformat(str(receipt.parameters["end_date"])),
            )
            if [day.isoformat() for day in parsed] != normalized:
                raise ValueError("calendar_normalized_original_mismatch")
            # Preserve the checked receipt's full history; required_calendar only
            # returns the final 120 report dates, which cannot prove warmup coverage.
            calendar["history_dates"] = [day.isoformat() for day in parsed if day <= end]
        if start.isoformat() not in calendar["dates"] or end.isoformat() not in calendar["dates"]:
            return {
                **calendar,
                "status": "unavailable",
                "basis": "calendar_range_not_covered",
                "dates": [],
            }
        return calendar
    except (ValueError, LookupError, OSError, TypeError) as error:
        return {
            "status": "unavailable",
            "basis": "calendar_material_invalid",
            "dates": [],
            "provenance": {},
            "error": str(error),
        }
