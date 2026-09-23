"""Persisted diagnostics for an admitted candidate's lifecycle inputs."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog_registry import require_registered_manifest
from pring_cycle.context_projection import ContextProjectionRules, build_context_projection
from pring_cycle.context_replay_scope import (
    CONTEXT_FORMULA_INPUTS,
    CONTEXT_FORMULA_OUTPUTS,
    ContextReplayScope,
    context_input_warmup_days,
    find_formula_documents,
)
from pring_cycle.core_input_requirements import (
    core_formula_requirements,
    inspect_core_formula_inputs,
)
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_run_requirements import (
    CalendarMaterialError,
    formula_requirements,
    preceding_periods,
    required_calendar,
)
from pring_cycle.futures_input_reads import shared_futures_input_reads
from pring_cycle.metric_contracts import (
    china_business_day_end,
    evidence_frequency,
    evidence_max_age_days,
    minimum_context_daily_observations,
    required_dimension_members,
)
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RetrievalScope, RunRecord
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.source_adapters import TushareCoreAdapter, calendar_coverage
from pring_cycle.storage import artifact_is_registered


def preflight_model_inputs(
    paths: RuntimePaths,
    model_version_id: str,
    *,
    requested_start: str,
    requested_end: str,
    expected_trading_days: int = 120,
) -> dict[str, Any]:
    # This inspection neither captures nor changes inputs. Share their verified
    # contents across cutoffs, but release the scope before another inspection.
    if expected_trading_days < 1:
        raise ValueError("material_preflight_day_count_invalid")
    with shared_futures_input_reads():
        result = _preflight_model_inputs(
            paths,
            model_version_id,
            requested_start=requested_start,
            requested_end=requested_end,
            expected_trading_days=expected_trading_days,
        )
    result["schema_version"] = "model-input-preflight-v0001"
    result["request"] = {
        "model_version_id": model_version_id,
        "manifest_hash": result["manifest_hash"],
        "requested_start": requested_start,
        "requested_end": requested_end,
        "target_business_date": requested_end,
    }
    result["request"]["expected_trading_days"] = expected_trading_days
    content = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    receipt = store_artifact(
        paths.database, paths.artifacts, content, "application/json", "model-input-preflight"
    )
    return {**result, "receipt_hash": receipt.content_hash}


def read_model_input_preflight(paths: RuntimePaths, receipt_hash: str) -> dict[str, Any]:
    """Read an immutable diagnostic without inspecting newer inputs."""
    if len(receipt_hash) != 64 or any(c not in "0123456789abcdef" for c in receipt_hash):
        raise ValueError("material_preflight_receipt_hash_invalid")
    if not artifact_is_registered(paths.database, receipt_hash, "model-input-preflight"):
        raise ValueError("material_preflight_receipt_not_found")
    try:
        content = (paths.artifacts / receipt_hash[:2] / receipt_hash).read_bytes()
    except OSError as error:
        raise ValueError("material_preflight_receipt_unreadable") from error
    if hashlib.sha256(content).hexdigest() != receipt_hash:
        raise ValueError("material_preflight_receipt_hash_mismatch")
    document = json.loads(content)
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != "model-input-preflight-v0001"
    ):
        raise ValueError("material_preflight_receipt_invalid")
    return {**document, "receipt_hash": receipt_hash}


def _preflight_model_inputs(
    paths: RuntimePaths,
    model_version_id: str,
    *,
    requested_start: str,
    requested_end: str,
    expected_trading_days: int = 120,
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
    cutoff = china_business_day_end(end)
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
    calendar["system_as_of"] = observed_at.isoformat()
    # Keep attempted originals identifiable even when parsing or integrity fails.
    # These receipts are evidence of acquisition, not a calendar acceptance verdict.
    calendar["acquisition_receipts"] = [
        {
            "acquisition_id": receipt.acquisition_id,
            "provider": receipt.provider,
            "api_name": receipt.api_name,
            "parameters": receipt.parameters,
            "parser_version": receipt.parser_version,
            "state": receipt.state,
            "error_type": receipt.error_type,
            "raw_hash": receipt.raw_hash,
            "normalized_hash": receipt.normalized_hash,
            "validated_at": receipt.validated_at.isoformat() if receipt.validated_at else None,
        }
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.provider == "tushare"
        and receipt.api_name == "trade_cal"
        and receipt.started_at <= observed_at
        and (receipt.received_at is None or receipt.received_at <= observed_at)
        and (receipt.validated_at is None or receipt.validated_at <= observed_at)
    ]
    if calendar["status"] == "available":
        window_dates = [day for day in calendar["dates"] if requested_start <= day <= requested_end]
        calendar["observed_trading_days"] = len(window_dates)
        if len(window_dates) != expected_trading_days:
            calendar.update(status="unavailable", basis="calendar_window_count_mismatch", dates=[])
            calendar.pop("ordered_dates_sha256", None)
    if calendar["status"] != "available":
        gaps.append({"metric_id": "CN_TRADE_CALENDAR", "reason": str(calendar["basis"])})
    checked_days = tuple(
        day for day in calendar["dates"] if start.isoformat() <= day <= end.isoformat()
    ) or (end.isoformat(),)
    present = []
    density_missing: dict[str, set[str]] = {}
    # These carry no scalar to score, but dropping them would make a P0 the preflight
    # never looked at read exactly like one that passed. Saying only what they are
    # would read as a verdict, so each says whether anything here examined it: the
    # calendar has its own section below, the rest are simply not checked yet.
    operational_evidence: list[dict[str, Any]] = []
    catalog_checks: dict[str, dict[str, Any]] = {}
    for definition in rules.metric_definitions:
        catalog_checks[definition.metric_id] = {
            "metric_id": definition.metric_id,
            "priority": definition.priority,
            "role": definition.role,
            "certification_status": definition.certification_status,
            "required": definition.priority != "P2"
            or definition.metric_id in formula_scope.requires_certification,
            "selection": {"status": "pending"},
            "checks": [],
        }
        if definition.role == "operational_evidence" or definition.metric_id in {
            "CN_TRADE_CALENDAR",
            "CN_RELEASE_SCHEDULE",
            "SOURCE_OBSERVED_AVAILABILITY",
        }:
            operational_evidence.append(
                {
                    "metric_id": definition.metric_id,
                    "role": "operational_evidence",
                    "status": (
                        "checked_separately"
                        if definition.metric_id == "CN_TRADE_CALENDAR"
                        else "not_checked"
                    ),
                }
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
            catalog_checks[definition.metric_id]["selection"] = {
                "status": "blocked",
                "reason": "source_material_missing",
            }
            # A missing delivery must not conceal a missing member contract.
            # These two families resolve members from their dedicated selectors.
            if (
                definition.dimensions
                and definition.metric_id not in {"CN_FUTURES_WARRANTS", "CN_RRR_EVENT"}
                and required_dimension_members(
                    definition.metric_id,
                    definition_version=rules.metric_catalog_version,
                    period=end.isoformat(),
                )
                is None
            ):
                catalog_checks[definition.metric_id]["selection"] = {
                    "status": "blocked",
                    "reason": "dimension_contract_unavailable",
                }
                destination.append(
                    {"metric_id": definition.metric_id, "reason": "dimension_contract_unavailable"}
                )
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
                # Coverage is point in time against the instant this inspection reads
                # at: a value first published after the window closed was never part
                # of it. It is deliberately not each session's own end, because a
                # source that publishes with date granularity is encoded as the next
                # midnight (evidence.publication_times), so demanding same-day
                # publication would report every legitimate session as missing.
                # Whether a given day could see a value is the per-day selection
                # below, which tolerates the freshness this check must not.
                and item.public_available_at is not None
                and item.public_available_at <= cutoff
            }
            minimum = (
                len(checked_days)
                if definition.role == "core_barometer"
                else minimum_context_daily_observations(len(checked_days))
            )
            if len(observed) < minimum:
                density_missing[definition.metric_id] = set(checked_days) - observed

    if (
        calendar["status"] == "available"
        and calendar.get("history_coverage", {}).get("status") != "complete"
    ):
        gaps.append(
            {
                "metric_id": "CN_TRADE_CALENDAR",
                "reason": "core_formula_calendar_coverage_unproven",
                **calendar.get("history_coverage", {}),
            }
        )
    core_requirements = core_formula_requirements(
        manifest,
        tuple(calendar.get("history_dates", ()))
        if calendar["status"] == "available"
        and calendar.get("history_coverage", {}).get("status") == "complete"
        else (),
        start.isoformat(),
        end.isoformat(),
    )
    gaps.extend(
        inspect_core_formula_inputs(evidence, manifest, core_requirements, start.isoformat(), paths)
    )

    # Keep only one day's cached series alive during a full window diagnostic.
    for day in checked_days:
        historical_cutoff = china_business_day_end(date.fromisoformat(day))
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
            selection_check = catalog_checks[definition.metric_id]["selection"]
            selection_check["status"] = "executed"
            selection_check["complete"] = (
                selection_check.get("complete", True) and selected.complete
            )
            selection_check.setdefault("checked_business_dates", []).append(day)
            for check in selected.material_checks:
                catalog_checks[check.metric_id]["checks"].append(
                    {
                        "business_date": day,
                        "period": period,
                        "originals": check.originals,
                        "dimensions": check.dimensions,
                        "invalid_original_claim_ids": check.invalid_original_claim_ids,
                    }
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
        "public_cutoffs": {
            day: china_business_day_end(date.fromisoformat(day)).astimezone(UTC).isoformat()
            for day in checked_days
        },
        "pending_checks": ["calendar", "originals", "dimensions", "point_in_time", "parents"],
        "gaps": gaps,
        "optional_gaps": optional_gaps,
        "catalog_checks": list(catalog_checks.values()),
        "operational_evidence": sorted(operational_evidence, key=lambda item: item["metric_id"]),
        "calendar": calendar,
        "core_formula_inputs": core_requirements,
    }


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
    calendar: dict[str, Any] = {}
    try:
        calendar = required_calendar(paths, run, selector)
        if calendar["status"] != "available":
            return calendar
        acquisition_id = calendar["provenance"]["acquisition_id"]
        if acquisition_id is not None:
            acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
            receipt = acquisitions.get(acquisition_id)
            calendar["provenance"].update(
                raw_hash=receipt.raw_hash, normalized_hash=receipt.normalized_hash
            )
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
            coverage = calendar_coverage(receipt, raw)
            calendar["history_coverage"] = coverage
            # Retain the original's dates for reconciliation even when coverage is
            # unproven; only the qualified range may become formula requirements.
            calendar["history_dates"] = [day.isoformat() for day in parsed if day <= end]
        if start.isoformat() not in calendar["dates"] or end.isoformat() not in calendar["dates"]:
            return {
                **calendar,
                "status": "unavailable",
                "basis": "calendar_range_not_covered",
                "dates": [],
            }
        calendar["ordered_dates_sha256"] = hashlib.sha256(
            "\n".join(calendar["dates"]).encode()
        ).hexdigest()
        return calendar
    except (ValueError, LookupError, OSError, TypeError) as error:
        return {
            "status": "unavailable",
            "basis": "calendar_material_invalid",
            "dates": [],
            "provenance": (
                error.provenance
                if isinstance(error, CalendarMaterialError)
                else calendar.get("provenance", {})
            ),
            "error": str(error),
        }
