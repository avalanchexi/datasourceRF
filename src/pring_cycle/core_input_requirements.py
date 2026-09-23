"""Frozen core formula requirements, separate from state initialization history."""

import json
from datetime import UTC, date, datetime
from typing import Any

from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.metric_contracts import china_business_day_end
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CoreInputValidator
from pring_cycle.storage import database_connection


def core_formula_requirements(
    manifest: dict[str, Any], calendar_days: tuple[str, ...], start: str, end: str
) -> dict[str, Any]:
    rules = manifest["trend_rules"]
    required = max(
        int(rules["window_days"]) + int(rules["slope_days"]),
        int(rules["volatility_days"]) + 1,
        int(rules["candidate_window_days"]),
    )
    days = sorted(set(day for day in calendar_days if day <= end))
    consumers: list[dict[str, Any]] = []
    for index, day in enumerate(days):
        if day < start:
            continue
        inputs = days[max(0, index - required + 1) : index + 1]
        consumers.append(
            {
                "business_date": day,
                "public_cutoff": china_business_day_end(date.fromisoformat(day))
                .astimezone(UTC)
                .isoformat(),
                "input_dates": inputs,
                "missing_calendar_observations": required - len(inputs),
            }
        )
    inputs = sorted({day for consumer in consumers for day in consumer["input_dates"]})
    return {
        "rule_version": rules["rule_version"],
        "definition_version": manifest["metric_catalog_version"],
        "metrics": manifest["core_metrics"],
        "dimensions": {},
        "frequency": "business_day",
        "lookback_unit": "china_trading_sessions",
        "required_observations_per_result": required,
        "input_start": inputs[0] if inputs else None,
        "input_end": inputs[-1] if inputs else None,
        "input_observations": len(inputs),
        "pre_window_observations": sum(day < start for day in inputs),
        "consumers": consumers,
        "state_initialization": {
            "status": "not_evaluated",
            "history_input_start": manifest.get("history_input_start"),
            "persistence_days": rules["persistence_days"],
            "candidate_duration_rule_version": rules.get("candidate_duration_rule_version"),
        },
    }


def inspect_core_formula_inputs(
    evidence: EvidenceRepository,
    manifest: dict[str, Any],
    requirements: dict[str, Any],
    start: str,
    paths: RuntimePaths,
) -> list[dict[str, Any]]:
    """Select every required date at the result's cutoff and retain exact vintages."""
    version = str(manifest["metric_catalog_version"])
    metrics = tuple(str(metric) for metric in manifest["core_metrics"].values())
    required_dates = {
        day for consumer in requirements["consumers"] for day in consumer["input_dates"]
    }
    vintages = {
        metric: tuple(
            item
            for item in evidence.source_claim_vintages(metric, definition_version=version)
            if item.period_end in required_dates
            and item.period_start == item.period_end
            and not item.dimensions
        )
        for metric in metrics
    }
    claim_ids = tuple(item.claim_id for items in vintages.values() for item in items)
    # Metadata remains diagnostic even when original content fails integrity checks.
    # Do not obtain it through validated-original readers, which intentionally omit failures.
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            """SELECT link.claim_id, request.acquisition_id, request.raw_hash,
                      request.normalized_hash
               FROM source_claim_acquisition AS link
               JOIN acquisition_request AS request USING(acquisition_id)
               WHERE link.claim_id IN (SELECT value FROM json_each(?))
               ORDER BY link.claim_id, request.acquisition_id""",
            (json.dumps(claim_ids),),
        ).fetchall()
    diagnostic_originals: dict[str, list[dict[str, Any]]] = {}
    for claim_id, acquisition_id, raw_hash, normalized_hash in rows:
        diagnostic_originals.setdefault(claim_id, []).append(
            {
                "acquisition_id": acquisition_id,
                "raw_hash": raw_hash,
                "normalized_hash": normalized_hash,
            }
        )
    candidates_by_period = {
        (metric, period): tuple(item for item in items if item.period_end == period)
        for metric, items in vintages.items()
        for period in required_dates
    }
    validator = CoreInputValidator(evidence, claim_ids)
    originals = evidence.source_claim_originals_many(claim_ids)
    evidence.preload_metric_series({(metric, version) for metric in metrics})
    gaps = []
    versions: dict[str, Any] = {}
    for consumer in requirements["consumers"]:
        day = consumer["business_date"]
        cutoff = datetime.fromisoformat(consumer["public_cutoff"])
        consumer["inputs"] = {}
        if consumer["missing_calendar_observations"]:
            gaps.append(
                {
                    "metric_id": "CN_TRADE_CALENDAR",
                    "reason": "core_formula_calendar_history_missing",
                    "business_date": day,
                    "missing_observations": consumer["missing_calendar_observations"],
                }
            )
        for metric in metrics:
            visible = {
                point.period_end: point
                for point in evidence.metric_series(
                    metric, definition_version=version, mode=AsOfMode.PUBLIC, as_of=cutoff
                )
                if not point.dimensions and point.period_start == point.period_end
            }
            inputs = []
            for period in consumer["input_dates"]:
                point = visible.get(period)
                selected = (
                    next(
                        (
                            claim
                            for claim in point.claims
                            if claim.claim_id == point.selected_claim_id
                        ),
                        None,
                    )
                    if point
                    else None
                )
                covering_packages = [
                    package["package_id"]
                    for package in manifest.get("source_certification_packages", ())
                    if metric in package["definition_bindings"]
                    and package["certified_from"] <= period
                ]
                reason = None
                causes = []
                candidates = candidates_by_period[metric, period]
                if selected is None:
                    if not candidates:
                        causes.append("value_missing")
                    else:
                        for candidate in candidates:
                            if candidate.public_available_at is None:
                                causes.append("public_time_unknown")
                            elif candidate.public_available_at > cutoff:
                                causes.append("public_time_after_cutoff")
                        if not causes:
                            causes.append("selection_unavailable")
                else:
                    assert point is not None
                    if point.selection_status != "selected":
                        causes.append("selection_conflicted")
                    if (
                        point.selected_value is None
                        or point.selected_value <= 0
                        or point.value_state is not EvidenceValueState.REPORTED_VALUE
                    ):
                        causes.append("value_missing")
                    if selected.certification_status != "certified":
                        causes.append("source_uncertified")
                    if selected.quality_status != "validated":
                        causes.append("quality_invalid")
                if causes:
                    reason = "core_history_input_missing"
                elif not covering_packages:
                    reason = "core_formula_certification_not_covering_period"
                    causes.append("certification_period_uncovered")
                elif point is not None and not validator.is_valid(metric, point):
                    reason = "core_history_original_invalid"
                    causes.append("original_invalid")
                if reason:
                    gaps.append(
                        {
                            "metric_id": metric,
                            "reason": reason,
                            "period": period,
                            "business_date": day,
                            "public_cutoff": consumer["public_cutoff"],
                            "claim_id": point.selected_claim_id if point else None,
                            "causes": sorted(set(causes)),
                            "diagnostic_candidates": [
                                {
                                    "claim_id": candidate.claim_id,
                                    "public_available_at": candidate.public_available_at.isoformat()
                                    if candidate.public_available_at
                                    else None,
                                    "certification_status": candidate.certification_status,
                                    "quality_status": candidate.quality_status,
                                    "originals": diagnostic_originals.get(candidate.claim_id, []),
                                }
                                for candidate in candidates
                            ],
                        }
                    )
                    continue
                assert selected is not None and point is not None
                inputs.append(
                    {
                        "period": period,
                        "claim_id": selected.claim_id,
                        "purpose": "formula_warmup" if period < start else "window_input",
                    }
                )
                versions[selected.claim_id] = {
                    "metric_id": metric,
                    "definition_version": version,
                    "period": period,
                    "observation_id": point.observation_id,
                    "value": point.selected_value,
                    "unit": selected.unit,
                    "provider": selected.provider,
                    "source_reference": selected.source_reference,
                    "public_available_at": selected.public_available_at.isoformat()
                    if selected.public_available_at
                    else None,
                    "release_at": selected.release_at.isoformat() if selected.release_at else None,
                    "available_at": selected.available_at.isoformat(),
                    "certification_status": selected.certification_status,
                    "certification_packages": covering_packages,
                    "quality_status": selected.quality_status,
                    "supersedes_claim_id": selected.supersedes_claim_id,
                    "originals": [
                        {
                            "acquisition_id": receipt.acquisition_id,
                            "raw_hash": receipt.raw_hash,
                            "normalized_hash": receipt.normalized_hash,
                        }
                        for receipt, _ in originals[selected.claim_id]
                    ],
                }
            consumer["inputs"][metric] = inputs
    requirements["versions"] = versions
    requirements["status"] = "blocked" if gaps or not requirements["consumers"] else "available"
    return gaps
