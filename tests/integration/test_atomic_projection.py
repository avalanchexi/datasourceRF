from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.projections import (
    ANALYTICAL_DATASETS,
    ProjectionEnvelope,
    ProjectionSetRepository,
)


def envelope(
    projection_set_id: str,
    *,
    target_business_date: str = "2026-08-28",
) -> ProjectionEnvelope:
    return ProjectionEnvelope(
        projection_set_id=projection_set_id,
        system_as_of=datetime(2026, 8, 28, 10, tzinfo=UTC),
        target_business_date=target_business_date,
        evidence_snapshot_id="snapshot-1",
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        evidence_window_start="2026-03-16",
        evidence_window_end="2026-08-28",
        generated_at=datetime(2026, 8, 28, 10, 1, tzinfo=UTC),
        completeness="complete",
        refresh_status="completed",
        warnings=(),
    )


def datasets(projection_set_id: str) -> dict[str, dict[str, object]]:
    return {
        name: {"projection_set_id": projection_set_id, "dataset": name}
        for name in ANALYTICAL_DATASETS
    }


def test_projection_set_is_visible_only_after_all_six_datasets_validate(tmp_path: Path) -> None:
    repository = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    repository.publish(envelope("projection-1"), datasets("projection-1"))

    with pytest.raises(ValueError, match="projection_dataset_identity_mismatch"):
        invalid = datasets("projection-2")
        invalid["macro"]["projection_set_id"] = "other"
        repository.publish(envelope("projection-2"), invalid)

    assert repository.current().envelope.projection_set_id == "projection-1"


def test_transaction_interruption_preserves_previous_current_projection(tmp_path: Path) -> None:
    repository = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    repository.publish(envelope("projection-1"), datasets("projection-1"))

    with pytest.raises(RuntimeError, match="injected_projection_failure"):
        repository.publish(
            envelope("projection-2"),
            datasets("projection-2"),
            fail_before_pointer=True,
        )

    current = repository.current()
    assert current.envelope.projection_set_id == "projection-1"
    assert set(current.datasets) == set(ANALYTICAL_DATASETS)


def test_historical_projection_is_stored_without_rewinding_current_pointer(
    tmp_path: Path,
) -> None:
    repository = ProjectionSetRepository.create(tmp_path / "projection.sqlite3")
    repository.publish(envelope("projection-current"), datasets("projection-current"))

    repository.publish(
        envelope("projection-history", target_business_date="2026-08-03"),
        datasets("projection-history"),
    )

    assert repository.get("projection-history").envelope.target_business_date == "2026-08-03"
    assert repository.current().envelope.projection_set_id == "projection-current"
