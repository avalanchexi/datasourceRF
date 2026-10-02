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
        observation_count=120 if state is not None else 0,
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

    # A core conflict holds the stage but still publishes the rest (ticket 21).
    assert first.status == "published"
    assert blocked.status == "published"
    assert blocked.current_stage is None
    assert blocked.last_confirmed_stage is FormalStage.STAGE_II
    assert blocked.stage_reason == "core_data_pending"
    assert blocked.assessment_id is not None
    assert projections.current().envelope.projection_set_id == blocked.projection_set_id
    history = projections.stage_history()
    assert [event["event_kind"] for event in history] == ["formal", "gap"]
    assert history[1]["stage_reason"] == "core_data_pending"
    assert history[1]["gaps"] == ["commodity:source_conflict"]
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


def test_context_window_accepts_a_published_month_that_overlaps_the_target_window(
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
    monthly = deepcopy(current.datasets)
    monthly["macro"]["credit"]["evidence"] = [  # type: ignore[index]
        {
            "metric_id": "CN_LPR_1Y_5Y",
            "period_start": "2026-08-01",
            "period": "2026-08-31",
        }
    ]

    validate_analytical_projection(current.envelope, monthly)

    future_daily = deepcopy(current.datasets)
    future_daily["macro"]["credit"]["evidence"] = [  # type: ignore[index]
        {
            "metric_id": "CN_DR007",
            "period_start": "2026-08-31",
            "period": "2026-08-31",
        }
    ]
    with pytest.raises(
        ValueError,
        match="projection_context_evidence_outside_visible_window",
    ):
        validate_analytical_projection(current.envelope, future_daily)


def test_context_window_accepts_a_current_baseline_from_before_it(tmp_path: Path) -> None:
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

    def policy(metric_id: str, day: str) -> dict[str, object]:
        datasets = deepcopy(current.datasets)
        datasets["macro"]["policy_action"]["evidence"] = [  # type: ignore[index]
            {"metric_id": metric_id, "period_start": day, "period": day}
        ]
        return datasets

    # An RRR in force until changed is shown however old (ADR-0028).
    validate_analytical_projection(current.envelope, policy("CN_RRR_EVENT", "2025-05-15"))
    for stale in (policy("CN_DR007", "2025-05-15"), policy("CN_RRR_EVENT", "2026-08-31")):
        with pytest.raises(
            ValueError,
            match="projection_context_evidence_outside_visible_window",
        ):
            validate_analytical_projection(current.envelope, stale)


def test_noncanonical_valid_combination_publishes_current_states_and_preserves_history(
    tmp_path: Path,
) -> None:
    projections = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-27",
        system_as_of=datetime(2026, 8, 27, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BULL),
            readiness("commodity", CoreAssetState.BEAR),
        ),
        last_confirmed_stage=None,
    )
    previous_projection_id = projections.current().envelope.projection_set_id
    result = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BEAR),
            readiness("commodity", CoreAssetState.BULL),
        ),
        last_confirmed_stage=FormalStage.STAGE_II,
    )

    assert result.status == "published"
    assert result.projection_set_id != previous_projection_id
    assert result.current_stage is None
    assert result.last_confirmed_stage is FormalStage.STAGE_II
    assert result.stage_reason == "noncanonical_combination"
    current = projections.current()
    assert current.envelope.projection_set_id == result.projection_set_id
    assert current.envelope.target_business_date == "2026-08-28"
    assert current.datasets["cycle_overview"]["current_stage"] is None
    assert current.datasets["cycle_overview"]["last_confirmed_stage"] == "stage_ii"
    assert (
        projections.get(previous_projection_id).datasets["cycle_overview"]["current_stage"]
        == "stage_ii"
    )
    history = projections.stage_history()
    gap = next(item for item in history if item["business_date"] == "2026-08-28")
    assert gap["current_stage"] is None
    assert gap["last_confirmed_stage"] == "stage_ii"
    assert gap["event_kind"] == "gap"
    assert gap["stage_reason"] == "noncanonical_combination"

    blocked = P0ProjectionService(projections).publish(
        target_business_date="2026-08-31",
        system_as_of=datetime(2026, 8, 31, 10, tzinfo=UTC),
        assets=(
            readiness("bond", CoreAssetState.BULL),
            readiness("stock", CoreAssetState.BEAR),
            readiness("commodity", None, "source_conflict"),
        ),
        last_confirmed_stage=FormalStage.STAGE_II,
    )
    # Held stage, published anyway (ticket 21).
    assert (blocked.status, blocked.stage_reason) == ("published", "core_data_pending")
    assert projections.current().envelope.projection_set_id == blocked.projection_set_id


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


@pytest.mark.parametrize("enabled", [True, False])
def test_a_model_without_the_12_month_proxy_publishes_no_proxy_field(enabled: bool) -> None:
    # Off, neither the core asset nor its candidate event carries the field; on with too
    # short a history, both say it is unavailable (ticket 25).
    from pring_cycle.p0 import _assessment_document, _asset_document

    asset = _asset_document(
        CoreAssetReadiness(
            "bond",
            "CN_BOND_CORE_000012",
            CoreAssetState.BULL,
            "validated",
            120,
            "2026-08-28",
            proxy_12m_enabled=enabled,
        )
    )
    assessment = _assessment_document(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        evidence_snapshot_id="snapshot",
        model_version_id="model-v0014",
        assets=[asset],
        current_stage=None,
        last_confirmed_stage=None,
        stage_reason="gap",
        gaps=(),
        projection_set_id=None,
    )

    event = assessment["candidate_events"][0]  # type: ignore[index]
    assert ("proxy_12m" in asset, "proxy_12m" in event) == (enabled, enabled)
    if enabled:
        assert asset["proxy_12m"] is None and event["proxy_12m"] is None
