"""Explicit synthetic calibration-sized workload, outside the default test suite."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.model_evaluation import evaluate_history
from pring_cycle.models import ModelRepository, certified_model_v0001_manifest


def test_public_replay_full_calibration_workload(tmp_path: Path) -> None:
    database = tmp_path / "synthetic-calibration.sqlite3"
    models = ModelRepository.create(database)
    models.create_candidate(certified_model_v0001_manifest())
    evidence = EvidenceRepository.create(database)
    days: list[datetime] = []
    day = datetime(2017, 1, 2, 2, tzinfo=UTC)
    while len(days) < 2338:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
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
            provider="synthetic-performance-fixture",
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
    evidence.append_source_claims(claims)
    evidence.append_source_claim(
        replace(
            claims[950 * 3],
            value=100000.0,
            source_reference="fixture:historical-revision",
            release_event_id="fixture:historical-revision",
            release_at=days[1000],
            public_available_at=days[1000],
            fetched_at=days[1000] + timedelta(minutes=1),
            available_at=days[1000] + timedelta(minutes=2),
        )
    )
    result = evaluate_history(
        database,
        "model-v0001",
        requested_start=days[343].date().isoformat(),
        requested_end=days[-1].date().isoformat(),
    )
    assert result.input_days == 2338 and result.evaluated_days == 1995
    assert result.core_states_by_day[days[-1].date().isoformat()] == ("bull", "bull", "bull")
    assert len(result.evidence_hash) == 64
    assert result.duration_seconds < 900
    print(
        json.dumps(
            {
                "scope": "synthetic weekdays, values, certification and publication times",
                "input_days": result.input_days,
                "evaluated_days": result.evaluated_days,
                "source_claims": 7015,
                "historical_revisions": 1,
                "evaluation_seconds": result.duration_seconds,
                "evidence_hash": result.evidence_hash,
                "real_china_calendar_or_full_parallel_replay_acceptance": False,
            },
            sort_keys=True,
        )
    )
