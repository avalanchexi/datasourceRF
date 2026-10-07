from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from pring_cycle.batches import current_batch_id
from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import StageResult, derive_formal_stage
from pring_cycle.projections import (
    ANALYTICAL_DATASETS,
    INVENTORY_CARD_NAMES,
    ProjectionEnvelope,
    ProjectionSetRepository,
    validate_analytical_projection,
)

# A core one session behind its target is priced at its previous session (ticket 21).
CARRIED_FORWARD = "carried_forward_one_session"


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
    # Off, the proxy is not shown at all; on with too short a history, it is unavailable.
    proxy_12m_enabled: bool = True
    distance_pct: float | None = None
    slope_pct: float | None = None
    noise_band_pct: float | None = None
    model_input_observation_version_ids: tuple[str, ...] | None = None
    carried_forward: bool = False
    # The actual closes (ISO day, value) the gate passed, oldest first: none when it failed,
    # and never the close carried forward. Read beside the stage, never published here.
    closes: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class P0PublishResult:
    status: str
    projection_set_id: str | None
    current_stage: FormalStage | None
    last_confirmed_stage: FormalStage | None
    stage_reason: str
    gaps: tuple[str, ...]
    assessment_id: str | None = None


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
        macro_document: dict[str, object] | None = None,
        inventory_document: dict[str, object] | None = None,
        release_calendar_events: tuple[dict[str, object], ...] = (),
        gap_list: tuple[dict[str, object], ...] = (),
        as_current: bool = True,
        decided: StageResult | None = None,
    ) -> P0PublishResult:
        """Publish the day's set; ``decided`` is its formal stage when already decided.

        The confirmation built before read that same stage (``formal_stage``); without
        one, it is decided here.
        """
        gaps = _core_gaps(assets)
        decided = decided or formal_stage(assets)
        # The cores' stage is the last confirmed one; without one, the one before stands.
        stage = replace(
            decided, last_confirmed_stage=decided.last_confirmed_stage or last_confirmed_stage
        )
        resolved_macro_document = macro_document or _default_macro_document()
        resolved_inventory_document = inventory_document or _default_inventory_document()
        asset_documents = [_asset_document(item) for item in assets]
        model_inputs = (
            sorted(
                {
                    version_id
                    for item in assets
                    for version_id in (item.model_input_observation_version_ids or ())
                }
            )
            if all(item.model_input_observation_version_ids is not None for item in assets)
            else None
        )
        resolved_snapshot_id = evidence_snapshot_id or (
            "snapshot-"
            + hashlib.sha256(json.dumps(asset_documents, sort_keys=True).encode()).hexdigest()[:20]
        )
        if gaps:
            warnings = (*warnings, "core_data_pending")
        carried = [item.asset for item in assets if item.carried_forward]
        if carried:
            warnings = (*warnings, *(f"core_carried_forward:{asset}" for asset in carried))
        identity_document = {
            "assets": asset_documents,
            "current_stage": stage.current_stage.value if stage.current_stage else None,
            "last_confirmed_stage": (
                stage.last_confirmed_stage.value if stage.last_confirmed_stage else None
            ),
            "model_version_id": model_version_id,
            "evidence_snapshot_id": resolved_snapshot_id,
            "stage_reason": stage.reason,
            "system_as_of": system_as_of.isoformat(),
            "target_business_date": target_business_date,
            "warnings": list(warnings),
            "macro": resolved_macro_document,
            "inventory": resolved_inventory_document,
            "release_calendar_events": list(release_calendar_events),
            "gap_list": list(gap_list),
        }
        if model_inputs is not None:
            identity_document["core_model_input_observation_version_ids"] = model_inputs
        if (batch_id := current_batch_id()) is not None:
            # A re-run of the same day is a new batch with its own summaries (ADR-0022).
            identity_document["batch_id"] = batch_id
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
            evidence_snapshot_id=resolved_snapshot_id,
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
        assessment = self._projections.prepare_p0_assessment(
            _assessment_document(
                target_business_date=target_business_date,
                system_as_of=system_as_of,
                evidence_snapshot_id=resolved_snapshot_id,
                model_version_id=model_version_id,
                assets=asset_documents,
                current_stage=stage.current_stage,
                last_confirmed_stage=stage.last_confirmed_stage,
                stage_reason=stage.reason,
                gaps=gaps,
                projection_set_id=projection_set_id,
            )
        )
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
                "macro_confirmation": _macro_confirmation(resolved_macro_document),
                "gap_list": list(gap_list),
                "core_carry_forward": carried,
            }
        )
        datasets["core_assets"]["assets"] = asset_documents
        if model_inputs is not None:
            datasets["core_assets"]["model_input_observation_version_ids"] = model_inputs
        datasets["macro"].update(resolved_macro_document)
        datasets["inventory"].update(resolved_inventory_document)
        datasets["release_calendar"]["events"] = list(release_calendar_events)
        # A set is the record as of its day: no later day's event, even one summarized
        # before this day was (ticket 14).
        history = list(self._projections.stage_history(through=target_business_date))
        if not any(item.get("assessment_id") == assessment["assessment_id"] for item in history):
            history.append(assessment)
        datasets["stage_history"]["events"] = history
        validate_analytical_projection(envelope, datasets)
        try:
            current = self._projections.current()
        except LookupError:
            current = None
        if current is not None and current.envelope.projection_set_id == projection_set_id:
            return P0PublishResult(
                "published",
                projection_set_id,
                stage.current_stage,
                stage.last_confirmed_stage,
                stage.reason,
                (),
                str(assessment["assessment_id"]),
            )
        self._projections.publish(
            envelope, datasets, p0_assessment=assessment, as_current=as_current
        )
        return P0PublishResult(
            "published",
            projection_set_id,
            stage.current_stage,
            stage.last_confirmed_stage,
            stage.reason,
            (),
            str(assessment["assessment_id"]),
        )


def formal_stage(
    assets: tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness],
) -> StageResult:
    """The day's formal stage, from its three cores alone, decided once for the day.

    The confirmation of the stage's narrative reads it, and publishing states it. Its
    last confirmed stage is the cores' own canonical one, held or not, else none: the
    history before the day is publishing's to add.
    """
    by_asset = {item.asset: item for item in assets}
    if set(by_asset) != {"bond", "stock", "commodity"}:
        raise ValueError("p0_asset_manifest_invalid")
    stage = derive_formal_stage(
        bond=by_asset["bond"].state,
        stock=by_asset["stock"].state,
        commodity=by_asset["commodity"].state,
        last_confirmed_stage=None,
    )
    if _core_gaps(assets):
        # Core data pending: no formal stage, but everything else is still published
        # and reported (ticket 07, item 3).
        stage = replace(stage, current_stage=None, reason="core_data_pending")
    return stage


def _core_gaps(assets: tuple[CoreAssetReadiness, ...]) -> tuple[str, ...]:
    return tuple(
        f"{item.asset}:{item.reason}"
        for item in assets
        if item.state is None or item.reason not in {"validated", CARRIED_FORWARD}
    )


def _macro_confirmation(document: dict[str, object] | None) -> list[dict[str, str]]:
    if document is None:
        return []
    confirmations = []
    for key in ("policy_direction", "credit_response", "overheat_state", "price_pressure"):
        state = document.get(key)
        if state not in {None, "insufficient_data"}:
            confirmations.append({"context": key, "state": str(state)})
    return confirmations


def _default_macro_document() -> dict[str, object]:
    return {
        "policy_direction": "insufficient_data",
        "policy_action": {"direction": "insufficient_data", "evidence": []},
        "transmission": {"direction": "insufficient_data", "evidence": []},
        "credit_response": "insufficient_data",
        "credit": {"state": "insufficient_data", "evidence": []},
        "overheat_state": "insufficient_data",
        "overheat": {
            "state": "insufficient_data",
            "support": [],
            "counterevidence": [],
            "gaps": [],
        },
        "price_pressure": "insufficient_data",
        "price_chain": {
            "state": "insufficient_data",
            "support": [],
            "counterevidence": [],
            "gaps": [],
        },
        "international_context": [],
        "score": None,
    }


def _default_inventory_document() -> dict[str, object]:
    return {
        "quadrant": None,
        "directions": {"demand": None, "production": None, "inventory": None},
        "cards": [
            {"name": name, "status": "missing", "evidence_ids": [], "evidence": []}
            for name in INVENTORY_CARD_NAMES
        ],
        "real_inventory_approximation": {
            "formula_version": "inventory-ppi-v0001",
            "status": "missing_inputs",
            "value": None,
        },
        "score": None,
    }


def _asset_document(item: CoreAssetReadiness) -> dict[str, object]:
    document: dict[str, object] = {
        "asset": item.asset,
        "carried_forward": item.carried_forward,
        "candidate_30d": (item.candidate_30d.value if item.candidate_30d is not None else None),
        "candidate_days": item.candidate_days,
        "candidate_state": (
            item.candidate_state.value if item.candidate_state is not None else None
        ),
        "distance_pct": item.distance_pct,
        "evidence_window_start": item.evidence_window_start,
        "latest_business_date": item.latest_business_date,
        "metric_id": item.metric_id,
        "noise_band_pct": item.noise_band_pct,
        "observation_count": item.observation_count,
        "observation_version_ids": list(item.observation_version_ids),
        "reason": item.reason,
        "slope_pct": item.slope_pct,
        "state": item.state.value if item.state else None,
    }
    if item.proxy_12m_enabled:
        document["proxy_12m"] = item.proxy_12m.value if item.proxy_12m is not None else None
    return document


def _assessment_document(
    *,
    target_business_date: str,
    system_as_of: datetime,
    evidence_snapshot_id: str,
    model_version_id: str,
    assets: list[dict[str, object]],
    current_stage: FormalStage | None,
    last_confirmed_stage: FormalStage | None,
    stage_reason: str,
    gaps: tuple[str, ...],
    projection_set_id: str | None,
) -> dict[str, object]:
    return {
        "business_date": target_business_date,
        "candidate_events": [
            {
                "asset": item["asset"],
                "candidate_30d": item["candidate_30d"],
                "candidate_days": item["candidate_days"],
                "candidate_state": item["candidate_state"],
                **({"proxy_12m": item["proxy_12m"]} if "proxy_12m" in item else {}),
            }
            for item in assets
        ],
        "core_assets": assets,
        "current_stage": current_stage.value if current_stage else None,
        "event_kind": "formal" if current_stage is not None else "gap",
        "evidence_snapshot_id": evidence_snapshot_id,
        "gaps": list(gaps),
        "last_confirmed_stage": (last_confirmed_stage.value if last_confirmed_stage else None),
        "model_version_id": model_version_id,
        "projection_set_id": projection_set_id,
        "stage_reason": stage_reason,
        "system_as_of": system_as_of.isoformat(),
        "trend_rule_version": "trend-v0001",
    }
