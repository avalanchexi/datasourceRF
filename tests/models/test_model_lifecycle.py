from __future__ import annotations

from pathlib import Path

import pytest

from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_model_v0001_manifest,
)


def test_model_v0001_requires_machine_acceptance_and_explicit_approval(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    candidate = models.create_candidate(certified_model_v0001_manifest())

    with pytest.raises(ValueError, match="model_acceptance_required"):
        models.activate(candidate.model_version_id, explicitly_approved=True)

    acceptance = models.record_acceptance(
        candidate.model_version_id,
        CALIBRATION_BASELINE,
    )
    assert acceptance.passed is True
    assert acceptance.asset_direction_changes == 21
    assert acceptance.formal_stage_changes == 11
    assert acceptance.fast_reversals_20d == 0
    assert acceptance.median_confirmation_delay_days == 23

    with pytest.raises(ValueError, match="explicit_model_approval_required"):
        models.activate(candidate.model_version_id, explicitly_approved=False)

    active = models.activate(candidate.model_version_id, explicitly_approved=True)
    assert active.status == "active"
    assert models.active().model_version_id == "model-v0001"


def test_manifest_is_immutable_and_same_input_has_same_hash(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    first = models.create_candidate(certified_model_v0001_manifest())
    second = models.create_candidate(certified_model_v0001_manifest())

    assert first.manifest_hash == second.manifest_hash
    assert first.model_version_id == second.model_version_id

    changed = certified_model_v0001_manifest()
    changed["trend_rules"]["persistence_days"] = 7  # type: ignore[index]
    with pytest.raises(ValueError, match="model_version_is_immutable"):
        models.create_candidate(changed)
