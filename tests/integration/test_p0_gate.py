from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository


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
    assert projections.current().envelope.projection_set_id == first.projection_set_id


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
    assert history["events"] == [
        {
            "business_date": "2026-08-28",
            "current_stage": None,
            "reason": "noncanonical_combination",
        }
    ]
