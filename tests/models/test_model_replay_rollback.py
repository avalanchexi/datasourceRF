from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_model_v0001_manifest,
)


def business_calendar(start: date, count: int) -> tuple[str, ...]:
    days: list[str] = []
    candidate = start
    while len(days) < count:
        if candidate.weekday() < 5:
            days.append(candidate.isoformat())
        candidate += timedelta(days=1)
    return tuple(days)


def activate_v0001(models: ModelRepository) -> None:
    models.create_candidate(certified_model_v0001_manifest())
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)


def test_candidate_replay_uses_certified_range_intersection_without_switching_active(
    tmp_path: Path,
) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    activate_v0001(models)
    candidate = certified_model_v0001_manifest()
    candidate["model_version_id"] = "model-v0002"
    candidate["certified_replay_start"] = "2020-01-01"
    candidate["trend_rules"]["noise_multiplier"] = 1.6  # type: ignore[index]
    models.create_candidate(candidate)

    replay = models.record_replay(
        "model-v0002",
        compared_with="model-v0001",
        requested_start="2018-06-01",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=3,
        core_state_differences=5,
        gaps=(),
    )

    assert replay.range_start == "2020-01-01"
    assert replay.range_end == "2026-08-28"
    assert replay.passed is True
    assert models.active().model_version_id == "model-v0001"


def test_activation_and_30_business_day_rollback_only_switch_pointers(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    activate_v0001(models)
    candidate = certified_model_v0001_manifest()
    candidate["model_version_id"] = "model-v0002"
    candidate["certified_replay_start"] = "2020-01-01"
    candidate["trend_rules"]["noise_multiplier"] = 1.6  # type: ignore[index]
    models.create_candidate(candidate)
    models.record_replay(
        "model-v0002",
        compared_with="model-v0001",
        requested_start="2020-01-01",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=3,
        core_state_differences=5,
        gaps=(),
    )
    models.record_acceptance("model-v0002", CALIBRATION_BASELINE)
    models.activate("model-v0002", explicitly_approved=True)
    models.record_first_publication("model-v0002", "2026-09-01")
    calendar = business_calendar(date(2026, 9, 1), 31)

    rolled_back = models.rollback(
        "model-v0002",
        as_of_business_date=calendar[29],
        trading_calendar=calendar,
        explicitly_confirmed=True,
    )

    assert rolled_back.model_version_id == "model-v0001"
    assert models.active().model_version_id == "model-v0001"
    assert models.get("model-v0002").status == "candidate"
    assert {item["model_version_id"] for item in models.activation_history()} == {
        "model-v0001",
        "model-v0002",
    }


def test_rollback_after_30_business_days_is_not_guaranteed(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    activate_v0001(models)
    candidate = certified_model_v0001_manifest()
    candidate["model_version_id"] = "model-v0002"
    models.create_candidate(candidate)
    models.record_replay(
        "model-v0002",
        compared_with="model-v0001",
        requested_start="2018-06-01",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
    )
    models.record_acceptance("model-v0002", CALIBRATION_BASELINE)
    models.activate("model-v0002", explicitly_approved=True)
    models.record_first_publication("model-v0002", "2026-09-01")
    calendar = business_calendar(date(2026, 9, 1), 31)

    with pytest.raises(ValueError, match="model_rollback_window_expired"):
        models.rollback(
            "model-v0002",
            as_of_business_date=calendar[30],
            trading_calendar=calendar,
            explicitly_confirmed=True,
        )
