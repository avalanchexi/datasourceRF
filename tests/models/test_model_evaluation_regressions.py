from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.trend import TrendHistoryPoint, TrendResult
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.model_evaluation import (
    CALIBRATION_END,
    CALIBRATION_INPUT_START,
    HistoricalEvaluation,
    calibrate_model,
    evaluate_history,
)
from pring_cycle.models import ModelRepository, certified_model_v0001_manifest


def test_confirmation_delay_restarts_after_price_recrosses_120d_average(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    start = datetime(2026, 8, 3, tzinfo=UTC)
    metrics = {
        "CN_BOND_CORE_000012": 100.0,
        "CN_EQUITY_CORE_000985": 200.0,
        "CN_COMMODITY_CORE_NHII": 300.0,
    }
    for offset in range(6):
        observed = start + timedelta(days=offset)
        for metric_id, base in metrics.items():
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=observed.date().isoformat(),
                    period_end=observed.date().isoformat(),
                    dimensions={},
                    value=base + offset + 1,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="fixture",
                    source_reference=f"fixture:{metric_id}:{offset}",
                    release_event_id=f"fixture-release:{metric_id}:{offset}",
                    release_at=observed,
                    public_available_at=observed,
                    fetched_at=observed,
                    available_at=observed,
                    certification_status="certified",
                    quality_status="validated",
                )
            )

    def trend_for(points: list[object], _rules: object) -> TrendResult:
        latest = float(points[-1].value)  # type: ignore[attr-defined]
        asset_bucket = int(latest // 100)
        day_number = int(latest % 100)
        if asset_bucket == 1:
            state = CoreAssetState.BULL if day_number == 6 else CoreAssetState.BEAR
            distance = {1: -1.0, 2: -1.0, 3: 0.1, 4: -0.1, 5: 0.1, 6: 1.0}[
                day_number
            ]
            fast = CoreAssetState.BULL if day_number >= 3 else CoreAssetState.BEAR
        elif asset_bucket == 2:
            state = CoreAssetState.BULL
            distance = 1.0
            fast = CoreAssetState.BULL
        else:
            state = CoreAssetState.BEAR
            distance = -1.0
            fast = CoreAssetState.BEAR
        return TrendResult(
            stable_state=state,
            candidate_state=None,
            candidate_30d=fast,
            proxy_12m=None,
            reason="stable",
            persistence_days=8,
            distance_pct=distance,
            slope_pct=distance,
            noise_band_pct=0.05,
            rule_version="trend-v0001",
        )

    def trend_history_for(
        points: list[object],
        rules: object,
    ) -> tuple[TrendHistoryPoint, ...]:
        history = []
        for index, point in enumerate(points):
            result = trend_for(points[: index + 1], rules)
            history.append(
                TrendHistoryPoint(
                    point.business_date,  # type: ignore[attr-defined]
                    result.stable_state,
                    result.distance_pct,
                )
            )
        return tuple(history)

    monkeypatch.setattr(
        "pring_cycle.model_evaluation.evaluate_trend_history",
        trend_history_for,
    )

    evaluated = evaluate_history(
        database,
        "model-v0001",
        requested_start="2026-08-03",
        requested_end="2026-08-08",
    )

    assert evaluated.asset_direction_changes == 1
    assert evaluated.median_confirmation_delay_days == 1


def test_v0001_machine_acceptance_uses_the_frozen_calibration_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    observed: dict[str, str | None] = {}

    def fake_evaluate(
        _database: Path,
        _model_version_id: str,
        *,
        requested_start: str,
        requested_end: str | None,
    ) -> HistoricalEvaluation:
        observed["start"] = requested_start
        observed["end"] = requested_end
        return HistoricalEvaluation(
            21,
            11,
            0,
            23,
            1995,
            0.1,
            {},
            {},
            "a" * 64,
            2338,
            "2017-01-03",
        )

    monkeypatch.setattr("pring_cycle.model_evaluation.evaluate_history", fake_evaluate)

    result = calibrate_model(database, "model-v0001")

    assert observed == {"start": "2018-06-01", "end": CALIBRATION_END}
    assert result["evidence_hash"] == "a" * 64
    assert result["evaluated_days"] == 1995
    assert result["input_days"] == 2338
    assert result["input_range_start"] == "2017-01-03"


def test_acceptance_hash_is_bound_to_the_calibration_evidence_vintage(
    tmp_path: Path,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    common = {
        "asset_direction_changes": 21,
        "formal_stage_changes": 11,
        "fast_reversals_20d": 0,
        "median_confirmation_delay_days": 23,
        "evaluated_days": 1995,
        "input_days": 2338,
        "input_range_start": "2017-01-03",
        "range_start": "2018-06-01",
        "range_end": "2026-08-19",
    }

    first = models.record_acceptance(
        "model-v0001",
        {**common, "evidence_hash": "a" * 64},
    )
    second = models.record_acceptance(
        "model-v0001",
        {**common, "evidence_hash": "b" * 64},
    )

    assert first.passed is True
    assert second.passed is True
    assert first.result_hash != second.result_hash


def test_history_uses_v0001_warmup_but_only_counts_the_requested_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    days = [
        datetime(2017, 1, 3, tzinfo=UTC),
        datetime(2017, 1, 4, tzinfo=UTC),
        datetime(2018, 6, 1, tzinfo=UTC),
        datetime(2018, 6, 4, tzinfo=UTC),
    ]
    metrics = (
        "CN_BOND_CORE_000012",
        "CN_EQUITY_CORE_000985",
        "CN_COMMODITY_CORE_NHII",
    )
    for offset, observed in enumerate(days):
        for metric_id in metrics:
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=observed.date().isoformat(),
                    period_end=observed.date().isoformat(),
                    dimensions={},
                    value=100.0 + offset,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="fixture",
                    source_reference=f"fixture:{metric_id}:{offset}",
                    release_event_id=f"fixture-release:{metric_id}:{offset}",
                    release_at=observed,
                    public_available_at=observed,
                    fetched_at=observed,
                    available_at=observed,
                    certification_status="certified",
                    quality_status="validated",
                )
            )

    observed_inputs: list[tuple[str, ...]] = []

    def warm_history(
        points: list[object], _rules: object
    ) -> tuple[TrendHistoryPoint, ...]:
        observed_inputs.append(
            tuple(point.business_date.isoformat() for point in points)  # type: ignore[attr-defined]
        )
        return tuple(
            TrendHistoryPoint(
                point.business_date,  # type: ignore[attr-defined]
                CoreAssetState.BEAR if index < 3 else CoreAssetState.BULL,
                -1.0 if index < 3 else 1.0,
            )
            for index, point in enumerate(points)
        )

    monkeypatch.setattr(
        "pring_cycle.model_evaluation.evaluate_trend_history",
        warm_history,
    )

    evaluated = evaluate_history(
        database,
        "model-v0001",
        requested_start="2018-06-01",
        requested_end="2018-06-04",
    )

    expected_input = (
        "2017-01-03",
        "2017-01-04",
        "2018-06-01",
        "2018-06-04",
    )
    assert CALIBRATION_INPUT_START == "2017-01-01"
    assert observed_inputs == [expected_input, expected_input, expected_input]
    assert evaluated.input_days == 4
    assert evaluated.evaluated_days == 2
    assert tuple(evaluated.core_states_by_day) == ("2018-06-01", "2018-06-04")
    assert evaluated.asset_direction_changes == 3
