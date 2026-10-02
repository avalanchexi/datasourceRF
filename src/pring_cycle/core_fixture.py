from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any

from pring_cycle.context_projection import build_context_projection
from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend, proxy_12m_enabled
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths

CORE_FIXTURE_SCHEMA_VERSION = "core-price-fixture-v0001"
CORE_FIXTURE_METRICS = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}


@dataclass(frozen=True)
class CoreFixtureProjectionResult:
    acceptance_only: bool
    assessment_id: str | None
    current_stage: str | None
    evidence_snapshot_id: str
    network_requests: int
    projection_set_id: str | None
    status: str
    target_business_date: str


def project_core_fixture(
    paths: RuntimePaths,
    document: object,
) -> CoreFixtureProjectionResult:
    parsed = _parse_fixture(document)
    model_version_id = parsed["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(model_version_id)
    rules = _trend_rules(manifest)
    calendar = parsed["trading_calendar"]
    assets = tuple(
        _readiness(
            asset,
            CORE_FIXTURE_METRICS[asset],
            parsed["prices"][asset],
            calendar,
            rules,
        )
        for asset in ("bond", "stock", "commodity")
    )
    normalized = _canonical_json(parsed["normalized_document"])
    evidence_snapshot_id = "fixture-snapshot-" + hashlib.sha256(
        normalized.encode()
    ).hexdigest()[:20]
    previous_stage = _last_confirmed_stage(paths, parsed["target_business_date"])
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=parsed["system_as_of"],
        model_manifest=manifest,
        target_business_date=parsed["target_business_date"],
        visible_evidence_start=(calendar[-120] if len(calendar) >= 120 else calendar[0]),
    )
    service = P0ProjectionService(ProjectionSetRepository(paths.database))
    result = service.publish(
        target_business_date=parsed["target_business_date"],
        system_as_of=parsed["system_as_of"],
        assets=assets,  # type: ignore[arg-type]
        last_confirmed_stage=previous_stage,
        model_version_id=model_version_id,
        warnings=("acceptance_fixture_only", *context.warnings),
        evidence_snapshot_id=evidence_snapshot_id,
        macro_document=context.macro,
        inventory_document=context.inventory,
    )
    return CoreFixtureProjectionResult(
        acceptance_only=True,
        assessment_id=result.assessment_id,
        current_stage=(result.current_stage.value if result.current_stage is not None else None),
        evidence_snapshot_id=evidence_snapshot_id,
        network_requests=0,
        projection_set_id=result.projection_set_id,
        status=result.status,
        target_business_date=parsed["target_business_date"],
    )


def _parse_fixture(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("core_fixture_must_be_object")
    required = {
        "schema_version",
        "target_business_date",
        "system_as_of",
        "model_version_id",
        "trading_calendar",
        "assets",
    }
    if set(document) != required:
        raise ValueError("core_fixture_schema_invalid")
    if document["schema_version"] != CORE_FIXTURE_SCHEMA_VERSION:
        raise ValueError("core_fixture_schema_version_invalid")
    target = _date_text(document["target_business_date"], "core_fixture_target_date_invalid")
    system_as_of = _aware_datetime(document["system_as_of"])
    model_version_id = str(document["model_version_id"])
    if not model_version_id:
        raise ValueError("core_fixture_model_version_required")
    calendar_value = document["trading_calendar"]
    if not isinstance(calendar_value, list) or not calendar_value:
        raise ValueError("core_fixture_calendar_required")
    calendar = tuple(
        _date_text(item, "core_fixture_calendar_date_invalid") for item in calendar_value
    )
    if tuple(sorted(set(calendar))) != calendar:
        raise ValueError("core_fixture_calendar_must_be_strictly_increasing")
    if calendar[-1] != target:
        raise ValueError("core_fixture_target_must_end_calendar")
    assets_value = document["assets"]
    if not isinstance(assets_value, dict) or set(assets_value) != set(
        CORE_FIXTURE_METRICS
    ):
        raise ValueError("core_fixture_asset_manifest_invalid")
    prices: dict[str, tuple[PricePoint, ...]] = {}
    normalized_assets: dict[str, object] = {}
    for asset in ("bond", "stock", "commodity"):
        asset_value = assets_value[asset]
        if not isinstance(asset_value, dict) or set(asset_value) != {"metric_id", "prices"}:
            raise ValueError("core_fixture_asset_schema_invalid")
        if asset_value["metric_id"] != CORE_FIXTURE_METRICS[asset]:
            raise ValueError("core_fixture_metric_identity_invalid")
        points, normalized_points = _price_points(asset_value["prices"], calendar)
        prices[asset] = points
        normalized_assets[asset] = {
            "metric_id": CORE_FIXTURE_METRICS[asset],
            "prices": normalized_points,
        }
    normalized_document = {
        "assets": normalized_assets,
        "model_version_id": model_version_id,
        "schema_version": CORE_FIXTURE_SCHEMA_VERSION,
        "system_as_of": system_as_of.isoformat(),
        "target_business_date": target,
        "trading_calendar": list(calendar),
    }
    return {
        "model_version_id": model_version_id,
        "normalized_document": normalized_document,
        "prices": prices,
        "system_as_of": system_as_of,
        "target_business_date": target,
        "trading_calendar": calendar,
    }


def _price_points(
    value: object,
    calendar: tuple[str, ...],
) -> tuple[tuple[PricePoint, ...], list[dict[str, object]]]:
    if not isinstance(value, list):
        raise ValueError("core_fixture_prices_must_be_array")
    points: list[PricePoint] = []
    normalized: list[dict[str, object]] = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {"business_date", "value"}:
            raise ValueError("core_fixture_price_schema_invalid")
        business_date = _date_text(
            row["business_date"], "core_fixture_price_date_invalid"
        )
        raw_value = row["value"]
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise ValueError("core_fixture_price_value_invalid")
        price = float(raw_value)
        if not isfinite(price) or price <= 0:
            raise ValueError("core_fixture_price_value_invalid")
        points.append(PricePoint(date.fromisoformat(business_date), price))
        normalized.append({"business_date": business_date, "value": price})
    if tuple(point.business_date.isoformat() for point in points) != calendar:
        raise ValueError("core_fixture_prices_must_match_calendar")
    return tuple(points), normalized


def _readiness(
    asset: str,
    metric_id: str,
    points: tuple[PricePoint, ...],
    calendar: tuple[str, ...],
    rules: TrendRules,
) -> CoreAssetReadiness:
    trend = evaluate_trend(list(points), rules)
    versions = tuple(
        "fixture-version-"
        + hashlib.sha256(
            f"{metric_id}:{point.business_date.isoformat()}:{point.value:.12g}".encode()
        ).hexdigest()[:20]
        for point in points
    )
    return CoreAssetReadiness(
        asset=asset,
        metric_id=metric_id,
        state=trend.stable_state,
        reason="validated" if trend.stable_state is not None else trend.reason,
        observation_count=len(points),
        latest_business_date=calendar[-1],
        observation_version_ids=versions,
        evidence_window_start=(calendar[-120] if len(calendar) >= 120 else calendar[0]),
        candidate_state=trend.candidate_state,
        candidate_days=rules.candidate_days_for_output(trend),
        candidate_30d=trend.candidate_30d,
        proxy_12m=trend.proxy_12m,
        proxy_12m_enabled=rules.proxy_12m_enabled,
        distance_pct=trend.distance_pct,
        slope_pct=trend.slope_pct,
        noise_band_pct=trend.noise_band_pct,
    )


def _trend_rules(manifest: dict[str, object]) -> TrendRules:
    document = manifest.get("trend_rules")
    if not isinstance(document, dict):
        raise ValueError("model_trend_rules_missing")
    try:
        return TrendRules(
            window_days=int(document["window_days"]),
            slope_days=int(document["slope_days"]),
            volatility_days=int(document["volatility_days"]),
            noise_multiplier=float(document["noise_multiplier"]),
            persistence_days=int(document["persistence_days"]),
            candidate_window_days=int(document["candidate_window_days"]),
            rule_version=str(document["rule_version"]),
            candidate_duration_rule_version=str(
                document.get("candidate_duration_rule_version", "candidate-duration-v0001")
            ),
            proxy_12m_enabled=proxy_12m_enabled(document),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_trend_rules_invalid") from error


def _last_confirmed_stage(
    paths: RuntimePaths,
    target_business_date: str,
) -> FormalStage | None:
    value = ProjectionSetRepository(paths.database).last_confirmed_stage(
        on_or_before=target_business_date
    )
    return FormalStage(str(value)) if value is not None else None


def _date_text(value: object, classification: str) -> str:
    if not isinstance(value, str):
        raise ValueError(classification)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError(classification) from error


def _aware_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("core_fixture_system_as_of_invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("core_fixture_system_as_of_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("core_fixture_system_as_of_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
