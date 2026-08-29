from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.projections import (
    ANALYTICAL_DATASETS,
    ProjectionEnvelope,
    ProjectionSetRepository,
)


@dataclass(frozen=True)
class CoreAssetReadiness:
    asset: str
    metric_id: str
    state: CoreAssetState | None
    reason: str
    observation_count: int
    latest_business_date: str | None
    observation_version_ids: tuple[str, ...] = ()
    evidence_window_start: str | None = None
    candidate_state: CoreAssetState | None = None
    candidate_days: int = 0
    candidate_30d: CoreAssetState | None = None
    proxy_12m: CoreAssetState | None = None
    distance_pct: float | None = None
    slope_pct: float | None = None
    noise_band_pct: float | None = None


@dataclass(frozen=True)
class P0PublishResult:
    status: str
    projection_set_id: str | None
    current_stage: FormalStage | None
    last_confirmed_stage: FormalStage | None
    stage_reason: str
    gaps: tuple[str, ...]


class P0ProjectionService:
    def __init__(self, projections: ProjectionSetRepository) -> None:
        self._projections = projections

    def publish(
        self,
        *,
        target_business_date: str,
        system_as_of: datetime,
        assets: tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness],
        last_confirmed_stage: FormalStage | None,
        model_version_id: str = "model-v0001",
        warnings: tuple[str, ...] = (),
        evidence_snapshot_id: str | None = None,
    ) -> P0PublishResult:
        by_asset = {item.asset: item for item in assets}
        if set(by_asset) != {"bond", "stock", "commodity"}:
            raise ValueError("p0_asset_manifest_invalid")
        gaps = tuple(
            f"{item.asset}:{item.reason}"
            for item in assets
            if item.state is None or item.reason != "validated"
        )
        stage = derive_formal_stage(
            bond=by_asset["bond"].state,
            stock=by_asset["stock"].state,
            commodity=by_asset["commodity"].state,
            last_confirmed_stage=last_confirmed_stage,
        )
        if gaps:
            return P0PublishResult(
                "action_required",
                None,
                None,
                stage.last_confirmed_stage,
                "p0_unavailable",
                gaps,
            )
        identity_document = {
            "assets": [
                {
                    "asset": item.asset,
                    "metric_id": item.metric_id,
                    "state": item.state.value if item.state else None,
                }
                for item in assets
            ],
            "model_version_id": model_version_id,
            "evidence_snapshot_id": evidence_snapshot_id,
            "system_as_of": system_as_of.isoformat(),
            "target_business_date": target_business_date,
        }
        projection_set_id = (
            "projection-"
            + hashlib.sha256(json.dumps(identity_document, sort_keys=True).encode()).hexdigest()[
                :20
            ]
        )
        envelope = ProjectionEnvelope(
            projection_set_id=projection_set_id,
            system_as_of=system_as_of,
            target_business_date=target_business_date,
            evidence_snapshot_id=evidence_snapshot_id
            or "snapshot-"
            + projection_set_id.removeprefix("projection-"),
            model_version_id=model_version_id,
            trend_rule_version="trend-v0001",
            evidence_window_start=min(
                (
                    item.evidence_window_start
                    for item in assets
                    if item.evidence_window_start is not None
                ),
                default=(datetime.fromisoformat(target_business_date) - timedelta(days=180))
                .date()
                .isoformat(),
            ),
            evidence_window_end=target_business_date,
            generated_at=system_as_of,
            completeness="degraded" if warnings else "complete",
            refresh_status="completed",
            warnings=warnings,
        )
        asset_documents = [
            {
                "asset": item.asset,
                "metric_id": item.metric_id,
                "state": item.state.value if item.state else None,
                "reason": item.reason,
                "observation_count": item.observation_count,
                "latest_business_date": item.latest_business_date,
                "observation_version_ids": list(item.observation_version_ids),
                "candidate_state": (
                    item.candidate_state.value if item.candidate_state is not None else None
                ),
                "candidate_days": item.candidate_days,
                "candidate_30d": (
                    item.candidate_30d.value if item.candidate_30d is not None else None
                ),
                "proxy_12m": item.proxy_12m.value if item.proxy_12m is not None else None,
                "distance_pct": item.distance_pct,
                "slope_pct": item.slope_pct,
                "noise_band_pct": item.noise_band_pct,
            }
            for item in assets
        ]
        datasets: dict[str, dict[str, object]] = {
            name: {"projection_set_id": projection_set_id} for name in ANALYTICAL_DATASETS
        }
        datasets["cycle_overview"].update(
            {
                "current_stage": stage.current_stage.value if stage.current_stage else None,
                "last_confirmed_stage": (
                    stage.last_confirmed_stage.value if stage.last_confirmed_stage else None
                ),
                "stage_reason": stage.reason,
                "core_assets": asset_documents,
                "transition_watch": [],
                "macro_confirmation": [],
            }
        )
        datasets["core_assets"]["assets"] = asset_documents
        datasets["macro"].update(
            {
                "policy_direction": "insufficient_data",
                "credit_response": "insufficient_data",
                "overheat_state": "insufficient_data",
                "price_pressure": "insufficient_data",
                "international_context": [],
            }
        )
        datasets["inventory"].update({"quadrant": None, "cards": []})
        datasets["release_calendar"]["events"] = []
        datasets["stage_history"]["events"] = [
            {
                "business_date": target_business_date,
                "current_stage": stage.current_stage.value if stage.current_stage else None,
                "reason": stage.reason,
            }
        ]
        self._projections.publish(envelope, datasets)
        return P0PublishResult(
            "published",
            projection_set_id,
            stage.current_stage,
            stage.last_confirmed_stage,
            stage.reason,
            (),
        )
