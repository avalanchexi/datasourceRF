"""Registered-source values reach the projection without certification or publication proof."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.worker import process_pending_run
from tests.integration.test_worker_execution import runtime, seed_independent_calendar

TARGET = date(2026, 8, 28)
SHANGHAI = ZoneInfo("Asia/Shanghai")


def claim(
    metric_id: str, day: date, value: float, *, unit: str, provider: str, reference: str
) -> SourceClaimInput:
    fetched = datetime.combine(day, time(20), SHANGHAI)
    # No certification label and no publication time: nothing a registered source owes.
    return SourceClaimInput(
        metric_id=metric_id,
        definition_version="metric-catalog-v0001",
        period_kind="business_day",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        dimensions={},
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=unit,
        provider=provider,
        source_reference=reference,
        release_event_id=f"fixture:{metric_id}:{day}",
        release_at=None,
        public_available_at=None,
        fetched_at=fetched,
        available_at=fetched,
        quality_status="validated",
    )


def rows_for(document: object, metric_id: str) -> Iterator[dict[str, Any]]:
    if isinstance(document, dict):
        if document.get("metric_id") == metric_id and "status" in document:
            yield document
        for child in document.values():
            yield from rows_for(child, metric_id)
    elif isinstance(document, list):
        for child in document:
            yield from rows_for(child, metric_id)


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> tuple[RuntimePaths, Any]:
    paths = runtime(tmp_path_factory.mktemp("decertified"))
    evidence = EvidenceRepository(paths.database)
    days: list[date] = []
    day = TARGET
    while len(days) < 180:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    seed_independent_calendar(paths, days)
    claims = []
    for index, observed in enumerate(days):
        for metric_id, value in (
            ("CN_BOND_CORE_000012", 100.0 + index),
            ("CN_EQUITY_CORE_000985", 1000.0 + index),
            ("CN_COMMODITY_CORE_NHII", 100.0 + index),
        ):
            api_name, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                claim(
                    metric_id,
                    observed,
                    value,
                    unit="index_points",
                    provider="tushare",
                    reference=f"tushare:{api_name}:{code}:{observed}",
                )
            )
        claims.append(
            claim(
                "CN_DR007",
                observed,
                1.5,
                unit="scalar",
                provider="fixture",
                reference=f"fixture:dr007:{observed}",
            )
        )
    evidence.append_source_claims(tuple(claims))
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="decertified",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        cutoff_mode="explicit",
    )
    process_pending_run(paths, report_adapters=())
    assert RunRepository(paths.database).get(run.run_id).status == "completed"
    return paths, ProjectionSetRepository(paths.database).current()


def test_uncertified_registered_values_reach_a_formal_stage(
    published: tuple[RuntimePaths, Any],
) -> None:
    paths, projection = published

    assert projection.datasets["cycle_overview"]["current_stage"] is not None
    assets = projection.datasets["core_assets"]["assets"]
    assert {asset["state"] for asset in assets} == {"bull"}
    dr007 = next(rows_for(projection.datasets, "CN_DR007"))
    assert (dr007["status"], dr007["value"]) == ("current", 1.5)
    report = ReportRepository(paths.database).history()[0]
    assert report.projection_set_id == projection.envelope.projection_set_id


def test_projection_carries_no_certification_labels(
    published: tuple[RuntimePaths, Any],
) -> None:
    _paths, projection = published

    document = json.dumps(projection.datasets, ensure_ascii=False)
    assert "certification" not in document
    assert "认证" not in document


def test_public_time_comes_from_the_registered_cadence(
    published: tuple[RuntimePaths, Any],
) -> None:
    paths, _projection = published
    target_end = datetime.combine(TARGET, time.max, SHANGHAI)

    [point] = [
        point
        for point in EvidenceRepository(paths.database).metric_series(
            "CN_EQUITY_CORE_000985",
            mode=AsOfMode.PUBLIC,
            as_of=target_end,
            definition_version="metric-catalog-v0001",
        )
        if point.period_end == TARGET.isoformat()
    ]
    # Held at 20:00, after the registered 17:00 close update: public at 17:00.
    assert point.claims[0].public_available_at == datetime.combine(TARGET, time(17), SHANGHAI)
