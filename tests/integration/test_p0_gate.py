from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import (
    INVENTORY_CARD_NAMES,
    ProjectionSetRepository,
    validate_analytical_projection,
)


def readiness(
    asset: str,
    state: CoreAssetState | None,
    reason: str = "validated",
) -> CoreAssetReadiness:
    return CoreAssetReadiness(
        asset=asset,
        metric_id={
            "bond": "CN_BOND_CORE_000012",
            "stock": "CN_EQUITY_CORE_000985",
            "commodity": "CN_COMMODITY_CORE_NHII",
        }[asset],
        state=state,
        reason=reason,
        observation_count=160 if state is not None else 0,
        latest_business_date="2026-08-28" if state is not None else None,
    )


def test_missing_p0_does_not_replace_the_previous_complete_projection(tmp_path: Path) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    service = P0ProjectionService(projections)
    first = service.publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BULL),
            readiness("commodity", CoreAssetState.BEAR),
        ),
        last_confirmed_stage=None,
    )

    blocked = service.publish(
        target_business_date="2026-08-29",
        system_as_of=datetime(2026, 8, 29, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BULL),
            readiness("commodity", None, "source_conflict"),
        ),
        last_confirmed_stage=FormalStage.STAGE_II,
    )

    assert first.status == "published"
    assert blocked.status == "action_required"
    assert blocked.current_stage is None
    assert blocked.last_confirmed_stage is FormalStage.STAGE_II
    assert blocked.gaps == ("commodity:source_conflict",)
    assert blocked.assessment_id is not None
    assert projections.current().envelope.projection_set_id == first.projection_set_id
    history = projections.stage_history()
    assert [event["event_kind"] for event in history] == ["formal", "gap"]
    assert history[1]["stage_reason"] == "p0_unavailable"
    assert history[1]["core_assets"][2]["reason"] == "source_conflict"


def test_complete_projection_validator_enforces_cross_dataset_domain_invariants(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BULL),
            readiness("commodity", CoreAssetState.BEAR),
        ),
        last_confirmed_stage=None,
    )
    current = projections.current()

    assert len(current.datasets["inventory"]["cards"]) == 7
    invalid_stage = deepcopy(current.datasets)
    invalid_stage["cycle_overview"]["current_stage"] = "stage_vi"
    with pytest.raises(ValueError, match="projection_formal_stage_invariant_failed"):
        validate_analytical_projection(current.envelope, invalid_stage)

    invalid_score = deepcopy(current.datasets)
    invalid_score["macro"]["score"] = 1
    with pytest.raises(ValueError, match="projection_context_score_forbidden"):
        validate_analytical_projection(current.envelope, invalid_score)


def test_noncanonical_valid_combination_publishes_an_explained_history_gap(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    result = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BEAR),
            readiness("commodity", CoreAssetState.BULL),
        ),
        last_confirmed_stage=FormalStage.STAGE_I,
    )

    assert result.status == "published"
    assert result.current_stage is None
    assert result.last_confirmed_stage is FormalStage.STAGE_I
    assert result.stage_reason == "noncanonical_combination"
    history = projections.current().datasets["stage_history"]
    assert history["events"][0]["business_date"] == "2026-08-28"
    assert history["events"][0]["current_stage"] is None
    assert history["events"][0]["last_confirmed_stage"] == "stage_i"
    assert history["events"][0]["event_kind"] == "gap"
    assert history["events"][0]["stage_reason"] == "noncanonical_combination"


def test_macro_and_inventory_documents_change_context_but_never_formal_stage(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    service = P0ProjectionService(projections)
    assets = (
        readiness("bond", CoreAssetState.BULL),
        readiness("stock", CoreAssetState.BULL),
        readiness("commodity", CoreAssetState.BEAR),
    )
    easing = service.publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        assets=assets,
        last_confirmed_stage=None,
        macro_document={
            "policy_direction": "easing",
            "credit_response": "expanding",
            "overheat_state": "heating",
            "price_pressure": "upstream_pressure",
            "international_context": [],
        },
        inventory_document={
            "quadrant": "active_restocking",
            "cards": [
                {"name": name, "status": "support", "evidence_ids": []}
                for name in INVENTORY_CARD_NAMES
            ],
            "score": None,
        },
    )
    tightening = service.publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, 1, tzinfo=UTC),
        assets=assets,
        last_confirmed_stage=FormalStage.STAGE_II,
        macro_document={
            "policy_direction": "tightening",
            "credit_response": "contracting",
            "overheat_state": "cooling",
            "price_pressure": "easing",
            "international_context": [],
        },
        inventory_document={
            "quadrant": "active_destocking",
            "cards": [
                {"name": name, "status": "support", "evidence_ids": []}
                for name in INVENTORY_CARD_NAMES
            ],
            "score": None,
        },
    )

    assert easing.current_stage is tightening.current_stage is FormalStage.STAGE_II
    assert easing.projection_set_id != tightening.projection_set_id
    current = projections.current()
    assert current.datasets["cycle_overview"]["current_stage"] == "stage_ii"
    assert current.datasets["macro"]["policy_direction"] == "tightening"
    assert current.datasets["inventory"]["quadrant"] == "active_destocking"
