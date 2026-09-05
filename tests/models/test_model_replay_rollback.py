from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import pring_cycle.models as models_module
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    certified_120d_model_v0011_manifest,
    certified_model_v0001_manifest,
)


def test_hardened_activation_requires_current_baseline_and_exact_120_day_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        models_module,
        "_hardened_machine_acceptance_matches",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        models_module,
        "_hardened_machine_replay_matches",
        lambda *args, **kwargs: True,
    )
    database = tmp_path / "models.sqlite3"
    models = ModelRepository.create(database)
    activate_v0001(models)
    days = business_calendar(date(2026, 3, 9), 120)
    append_core_calendars(database, days)
    manifest = certified_120d_model_v0011_manifest(({"package_id": "fixture-package"},))
    model_id = str(manifest["model_version_id"])
    models.create_candidate(manifest)
    models.record_acceptance(model_id, machine_acceptance_results())
    models.record_replay(
        model_id,
        compared_with="model-v0001",
        requested_start="2026-03-09",
        requested_end=days[-2],
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
        evaluated_trading_days=119,
        calendar_hash=hashlib.sha256("\n".join(days[:-1]).encode()).hexdigest(),
    )
    with pytest.raises(ValueError, match="model_failed_replay_not_activatable"):
        models.activate(model_id, explicitly_approved=True)

    models.record_replay(
        model_id,
        compared_with="model-v0001",
        requested_start="2026-03-09",
        requested_end=days[-1],
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
        evaluated_trading_days=120,
        calendar_hash=hashlib.sha256("\n".join(days).encode()).hexdigest(),
    )
    with pytest.raises(ValueError, match="model_failed_replay_not_activatable"):
        models.activate(model_id, explicitly_approved=True)

    clean_manifest = certified_120d_model_v0011_manifest(
        ({"package_id": "fixture-package-clean"},)
    )
    clean_id = str(clean_manifest["model_version_id"])
    models.create_candidate(clean_manifest)
    models.record_acceptance(clean_id, machine_acceptance_results())
    clean_replay = models.record_replay(
        clean_id,
        compared_with="model-v0001",
        requested_start=days[0],
        requested_end=days[-1],
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
        evaluated_trading_days=120,
        calendar_hash=hashlib.sha256("\n".join(days).encode()).hexdigest(),
    )

    assert clean_replay.passed is True
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        models.activate(clean_id, explicitly_approved=True)
    assert models.active().model_version_id == "model-v0001"


def business_calendar(start: date, count: int) -> tuple[str, ...]:
    days: list[str] = []
    candidate = start
    while len(days) < count:
        if candidate.weekday() < 5:
            days.append(candidate.isoformat())
        candidate += timedelta(days=1)
    return tuple(days)


def append_core_calendars(database: Path, days: tuple[str, ...]) -> None:
    repository = EvidenceRepository.create(database)
    metrics = (
        "CN_BOND_CORE_000012",
        "CN_EQUITY_CORE_000985",
        "CN_COMMODITY_CORE_NHII",
    )
    for definition_version in ("metric-catalog-v0001", "metric-catalog-v0003"):
        for offset, day in enumerate(days):
            observed = datetime.fromisoformat(f"{day}T12:00:00+00:00")
            for metric_id in metrics:
                repository.append_source_claim(
                    SourceClaimInput(
                        metric_id=metric_id,
                        definition_version=definition_version,
                        period_kind="business_day",
                        period_start=day,
                        period_end=day,
                        dimensions={},
                        value=100.0 + offset,
                        value_state=EvidenceValueState.REPORTED_VALUE,
                        unit="index_points",
                        provider="fixture",
                        source_reference=(
                            f"fixture:{definition_version}:{metric_id}:{day}"
                        ),
                        release_event_id=(
                            f"fixture:{definition_version}:{metric_id}:{day}"
                        ),
                        release_at=observed,
                        public_available_at=observed,
                        fetched_at=observed,
                        available_at=observed,
                        certification_status="certified",
                        quality_status="validated",
                    )
                )


def machine_acceptance_results() -> dict[str, int | str]:
    return {
        **CALIBRATION_BASELINE,
        "evidence_hash": "a" * 64,
        "evaluated_days": 1995,
        "input_days": 2338,
        "input_range_start": "2017-01-03",
        "range_end": "2026-08-19",
        "range_start": "2018-06-01",
    }


def activate_v0001(models: ModelRepository) -> None:
    models.create_candidate(certified_model_v0001_manifest())
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)


def test_any_failed_candidate_replay_permanently_blocks_activation(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    activate_v0001(models)
    candidate = certified_model_v0001_manifest()
    candidate["model_version_id"] = "model-v0009"
    models.create_candidate(candidate)
    models.record_acceptance("model-v0009", CALIBRATION_BASELINE)
    for gaps in (("fixture_replay_failed",), ()):
        models.record_replay(
            "model-v0009",
            compared_with="model-v0001",
            requested_start="2018-06-01",
            requested_end="2026-08-28",
            quality_passed=True,
            regression_passed=True,
            performance_passed=True,
            stage_differences=0,
            core_state_differences=0,
            gaps=gaps,
        )

    with pytest.raises(ValueError, match="model_failed_replay_not_activatable"):
        models.activate("model-v0009", explicitly_approved=True)


def test_hardened_activation_rechecks_active_baseline_under_write_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "models.sqlite3"
    models = ModelRepository.create(database)
    activate_v0001(models)
    days = business_calendar(date(2026, 3, 9), 120)
    append_core_calendars(database, days)
    candidate = certified_120d_model_v0011_manifest(
        ({"package_id": "fixture-toctou"},)
    )
    candidate_id = str(candidate["model_version_id"])
    models.create_candidate(candidate)
    models.record_acceptance(candidate_id, machine_acceptance_results())
    models.record_replay(
        candidate_id,
        compared_with="model-v0001",
        requested_start=days[0],
        requested_end=days[-1],
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
        evaluated_trading_days=120,
        calendar_hash=hashlib.sha256("\n".join(days).encode()).hexdigest(),
    )
    fallback = certified_model_v0001_manifest()
    fallback["model_version_id"] = "model-v0002"
    models.create_candidate(fallback)
    monkeypatch.setattr(
        models_module,
        "_hardened_machine_acceptance_matches",
        lambda *args, **kwargs: True,
    )

    def change_active(*args: object, **kwargs: object) -> bool:
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE active_model SET model_version_id='model-v0002' WHERE singleton=1"
            )
        return True

    monkeypatch.setattr(
        models_module,
        "_hardened_machine_replay_matches",
        change_active,
    )

    with pytest.raises(ValueError, match="active_model_changed_during_activation"):
        models.activate(candidate_id, explicitly_approved=True)


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
        context_output_differences=7,
    )

    assert replay.range_start == "2020-01-01"
    assert replay.range_end == "2026-08-28"
    assert replay.passed is True
    assert replay.context_output_differences == 7
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
