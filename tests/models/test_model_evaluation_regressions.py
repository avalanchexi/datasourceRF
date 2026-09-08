from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.trend import TrendHistoryPoint, TrendResult
from pring_cycle.evidence import (
    AsOfMode,
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
    replay_models,
)
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    analytical_model_v0003_manifest,
    certified_120d_model_v0006_manifest,
    certified_model_v0001_manifest,
)


def test_legacy_model_replay_uses_its_certified_interval_without_an_exact_120_day_rule(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy-replay.sqlite3"
    models = ModelRepository.create(database)
    manifest = certified_model_v0001_manifest()
    models.create_candidate(manifest)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    manifest["model_version_id"] = "legacy-candidate"
    models.create_candidate(manifest)
    evidence = EvidenceRepository.create(database)
    days: list[datetime] = []
    day = datetime(2018, 1, 1, tzinfo=UTC)
    while len(days) < 170:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    for index, observed in enumerate(days):
        for metric_id in ("CN_BOND_CORE_000012", "CN_EQUITY_CORE_000985", "CN_COMMODITY_CORE_NHII"):
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=observed.date().isoformat(),
                    period_end=observed.date().isoformat(),
                    dimensions={},
                    value=100.0 + index,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="fixture",
                    source_reference=f"fixture:{metric_id}:{index}",
                    release_event_id=f"fixture:{metric_id}:{index}",
                    release_at=observed,
                    public_available_at=observed,
                    fetched_at=observed,
                    available_at=observed,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    result = replay_models(
        database,
        "legacy-candidate",
        "model-v0001",
        requested_start=days[-5].date().isoformat(),
        requested_end=days[-1].date().isoformat(),
    )
    assert result.quality_passed is True, result.gaps
    assert result.evaluated_trading_days == 5


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
            distance = {1: -1.0, 2: -1.0, 3: 0.1, 4: -0.1, 5: 0.1, 6: 1.0}[day_number]
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


def test_v0006_calibration_keeps_the_frozen_core_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(
        certified_120d_model_v0006_manifest(({"package_id": "source-certification-fixture"},))
    )
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
            "b" * 64,
            2338,
            "2017-01-03",
        )

    monkeypatch.setattr("pring_cycle.model_evaluation.evaluate_history", fake_evaluate)

    result = calibrate_model(database, "model-v0006")

    assert observed == {"start": "2018-06-01", "end": CALIBRATION_END}
    assert result["range_start"] == "2018-06-01"


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


@pytest.mark.parametrize(
    ("manifest", "definition_version"),
    (
        (certified_model_v0001_manifest(), "metric-catalog-v0001"),
        (analytical_model_v0003_manifest(), "metric-catalog-v0002"),
    ),
)
def test_history_uses_model_warmup_but_only_counts_the_requested_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict[str, object],
    definition_version: str,
) -> None:
    database = tmp_path / "model.sqlite3"
    models = ModelRepository.create(database)
    model = models.create_candidate(manifest)
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
                    definition_version=definition_version,
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

    def warm_history(points: list[object], _rules: object) -> tuple[TrendHistoryPoint, ...]:
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
        model.model_version_id,
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


@pytest.mark.parametrize(
    "publication",
    [
        "last_day",
        "unknown",
        "after_window",
        "just_after_early_cutoff",
    ],
)
def test_later_public_revision_cannot_rewrite_an_earlier_replay_day(
    tmp_path: Path,
    publication: str,
) -> None:
    database = tmp_path / "point-in-time-replay.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    days: list[datetime] = []
    day = datetime(2026, 1, 5, 2, tzinfo=UTC)
    while len(days) < 149:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    # Synthetic weekdays and releases, with the real frozen 120/20/8 trend rule.
    # This is a software counterexample, not the required China-calendar replay.
    claims = tuple(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start=observed.date().isoformat(),
            period_end=observed.date().isoformat(),
            dimensions={},
            value=100.0 + index,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="fixture",
            source_reference=f"fixture:{metric_id}:{index}",
            release_event_id=f"fixture:{metric_id}:{index}",
            release_at=observed,
            public_available_at=observed,
            fetched_at=observed + timedelta(minutes=1),
            available_at=observed + timedelta(minutes=2),
            certification_status="certified",
            quality_status="validated",
        )
        for index, observed in enumerate(days)
        for metric_id in ("CN_BOND_CORE_000012", "CN_EQUITY_CORE_000985", "CN_COMMODITY_CORE_NHII")
    )
    stored = evidence.append_source_claims(claims)
    old = stored[60]
    released = {
        "last_day": days[-1],
        "unknown": None,
        "after_window": days[-1] + timedelta(days=1),
        "just_after_early_cutoff": days[146].replace(hour=16),
    }[publication]
    received = max(days[-1], released) if released is not None else days[-1]
    revision = evidence.append_source_claim(
        replace(
            claims[60],
            value=100000.0,
            source_reference="fixture:bond:late-revision",
            release_event_id="fixture:bond:late-revision",
            release_at=released,
            public_available_at=released,
            fetched_at=received + timedelta(minutes=1),
            available_at=received + timedelta(minutes=2),
        )
    )
    assert revision.observation_id == old.observation_id
    assert revision.supersedes_claim_id == old.claim_id
    early = evidence.query(old.observation_id, mode=AsOfMode.PUBLIC, as_of=days[146])
    late = evidence.query(old.observation_id, mode=AsOfMode.PUBLIC, as_of=days[148])
    assert (early.selected_claim_id, early.selected_value) == (old.claim_id, 120.0)
    visible_at_end = publication in {"last_day", "just_after_early_cutoff"}
    assert (late.selected_claim_id, late.selected_value) == (
        (revision.claim_id, 100000.0) if visible_at_end else (old.claim_id, 120.0)
    )

    short = evaluate_history(
        database, "model-v0001", requested_start="2026-07-28", requested_end="2026-07-28"
    )
    long = evaluate_history(
        database, "model-v0001", requested_start="2026-07-28", requested_end="2026-07-30"
    )
    assert short.core_states_by_day["2026-07-28"] == ("bull", "bull", "bull")
    assert short.stages_by_day["2026-07-28"] == "stage_iii"
    assert long.core_states_by_day["2026-07-28"] == short.core_states_by_day["2026-07-28"]
    assert long.stages_by_day["2026-07-28"] == short.stages_by_day["2026-07-28"]
    assert long.core_states_by_day["2026-07-30"] == (
        (None, "bull", "bull") if visible_at_end else ("bull", "bull", "bull")
    )
    assert long.evaluated_days == 3
    if publication == "last_day":
        # An earlier release discovered later changes the daily path, while the
        # final selected claim and value remain identical. Bind that distinction.
        evidence.append_source_claim(
            replace(
                claims[60],
                value=100000.0,
                source_reference="fixture:bond:earlier-release",
                release_event_id="fixture:bond:earlier-release",
                release_at=days[146],
                public_available_at=days[146],
                fetched_at=days[-1] + timedelta(minutes=3),
                available_at=days[-1] + timedelta(minutes=4),
            )
        )
        final = evidence.query(old.observation_id, mode=AsOfMode.PUBLIC, as_of=days[148])
        assert (final.selected_claim_id, final.selected_value) == (revision.claim_id, 100000.0)
        changed_path = evaluate_history(
            database, "model-v0001", requested_start="2026-07-28", requested_end="2026-07-30"
        )
        assert changed_path.core_states_by_day["2026-07-28"] == (None, "bull", "bull")
        assert changed_path.evidence_hash != long.evidence_hash


@pytest.mark.parametrize("publication", ["within_end", "after_end", "unknown"])
@pytest.mark.parametrize("missing_assets", ["bond", "all"])
def test_public_replay_cannot_shorten_its_window_to_hide_a_missing_asset(
    tmp_path: Path,
    publication: str,
    missing_assets: str,
) -> None:
    database = tmp_path / "late-publication.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    start = datetime(2026, 8, 3, 2, tzinfo=UTC)
    claims = []
    for offset in range(2):
        observed = start + timedelta(days=offset)
        for metric_id in ("CN_BOND_CORE_000012", "CN_EQUITY_CORE_000985", "CN_COMMODITY_CORE_NHII"):
            released: datetime | None = observed
            if offset == 0 and (missing_assets == "all" or metric_id == "CN_BOND_CORE_000012"):
                released = (
                    None
                    if publication == "unknown"
                    else start + timedelta(days=1 if publication == "within_end" else 2)
                )
            claims.append(
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
                    release_event_id=f"fixture:{metric_id}:{offset}",
                    release_at=released,
                    public_available_at=released,
                    fetched_at=start + timedelta(days=3),
                    available_at=start + timedelta(days=3, minutes=1),
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    evidence.append_source_claims(tuple(claims))
    with pytest.raises(ValueError, match="calibration_evidence_incomplete"):
        evaluate_history(
            database, "model-v0001", requested_start="2026-08-03", requested_end="2026-08-04"
        )


@pytest.mark.parametrize(
    ("certification", "quality", "price"),
    [
        ("awaiting_source_certification", "validated", 100.0),
        ("certified", "invalid", 100.0),
        ("certified", "unverified", 100.0),
        ("certified", "validated", 0.0),
        ("certified", "validated", -1.0),
    ],
)
def test_public_replay_rejects_unqualified_history_before_a_valid_revision(
    tmp_path: Path,
    certification: str,
    quality: str,
    price: float,
) -> None:
    database = tmp_path / "unqualified-history.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    start = datetime(2026, 8, 3, 2, tzinfo=UTC)
    claims = tuple(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start=observed.date().isoformat(),
            period_end=observed.date().isoformat(),
            dimensions={},
            value=price if offset == 0 else 101.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="fixture",
            source_reference=f"fixture:{metric_id}:{offset}",
            release_event_id=f"fixture:{metric_id}:{offset}",
            release_at=observed,
            public_available_at=observed,
            fetched_at=observed,
            available_at=observed,
            certification_status=certification if offset == 0 else "certified",
            quality_status=quality if offset == 0 else "validated",
        )
        for offset in range(2)
        for observed in (start + timedelta(days=offset),)
        for metric_id in ("CN_BOND_CORE_000012", "CN_EQUITY_CORE_000985", "CN_COMMODITY_CORE_NHII")
    )
    evidence.append_source_claims(claims)
    # All first-day observations have qualified revisions at the later cutoff.
    evidence.append_source_claims(
        tuple(
            replace(
                claim,
                value=100.0,
                certification_status="certified",
                quality_status="validated",
                source_reference=claim.source_reference + ":revision",
                release_event_id=claim.release_event_id + ":revision",
                release_at=start + timedelta(days=1),
                public_available_at=start + timedelta(days=1),
                fetched_at=start + timedelta(days=1),
                available_at=start + timedelta(days=1),
            )
            for claim in claims[:3]
        )
    )
    with pytest.raises(ValueError, match="calibration_evidence_incomplete"):
        evaluate_history(
            database, "model-v0001", requested_start="2026-08-03", requested_end="2026-08-04"
        )
