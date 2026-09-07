from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import analytical_model_v0002_manifest


@pytest.mark.parametrize("previous_december", [None, 100.0])
@pytest.mark.parametrize("january", [0.0, 10.0])
@pytest.mark.parametrize("public_known", [False, True])
def test_january_loan_ytd_is_its_own_monthly_flow(
    tmp_path: Path, previous_december: float | None, january: float, public_known: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 2, 2, tzinfo=UTC)
    inputs = [("2026-01-01", "2026-01-31", january)]
    if previous_december is not None:
        inputs.insert(0, ("2025-01-01", "2025-12-31", previous_december))
    ids = {}
    for start, end, value in inputs:
        public = timestamp if end == "2025-12-31" or public_known else None
        stored = repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_LOAN_STRUCTURE",
                definition_version="metric-catalog-v0003",
                period_kind="year_to_month",
                period_start=start,
                period_end=end,
                dimensions={
                    "borrower": "enterprise",
                    "tenor": "long_term",
                    "measure": "ytd_increment",
                },
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="isolated_fixture",
                source_reference=f"fixture:loan:{end}",
                release_event_id=f"fixture:loan:{end}",
                release_at=public,
                public_available_at=public,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
        ids[end] = stored.claim_id
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    cast(dict[str, str], manifest["derived_formula_versions"])["loan_monthly_change"] = (
        "loan-ytd-monthly-change-v0002"
    )
    mode = AsOfMode.PUBLIC if public_known else AsOfMode.SYSTEM
    context = build_context_projection(
        repository, as_of=timestamp, model_manifest=manifest, as_of_mode=mode
    )
    credit = cast(dict[str, object], context.macro["credit"])
    rows = cast(list[dict[str, object]], credit["evidence"])
    monthly = [
        row
        for row in rows
        if row["metric_id"] == "CN_LOAN_STRUCTURE"
        and row["dimensions"]
        == {"borrower": "enterprise", "tenor": "long_term", "measure": "monthly_change"}
    ]
    assert len(monthly) == 1
    assert monthly[0]["period"] == "2026-01-31"
    assert monthly[0]["value"] == january
    assert monthly[0]["status"] == "current"
    assert monthly[0]["public_available_at"] == (timestamp.isoformat() if public_known else None)
    derived_id = str(monthly[0]["derived_observation_id"])
    trace = repository.derived_trace(derived_id, mode=mode, as_of=timestamp)
    assert trace.input_observation_version_ids == (ids["2026-01-31"],)
    assert monthly[0]["input_observation_version_ids"] == [ids["2026-01-31"]]


@pytest.mark.parametrize(
    "measure,periods,expected",
    [
        ("ytd_increment", [("2026-01-31", 10.0), ("2026-02-28", 15.0)], 5.0),
        ("ytd_increment", [("2025-12-31", 100.0), ("2026-02-28", 15.0)], None),
        ("ytd_increment", [("2026-01-31", 10.0), ("2026-03-31", 20.0)], None),
        ("ytd_increment", [("2026-01-31", 10.0), ("2026-02-28", 8.0)], -2.0),
        ("stock_end", [("2025-12-31", 100.0), ("2026-01-31", 110.0)], 10.0),
        ("stock_end", [("2026-01-31", 10.0)], None),
    ],
)
def test_loan_flow_requires_the_correct_comparison_period(
    tmp_path: Path, measure: str, periods: list[tuple[str, float]], expected: float | None
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 4, 2, tzinfo=UTC)
    claim_ids = []
    for period, value in periods:
        stored = repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_LOAN_STRUCTURE",
                definition_version="metric-catalog-v0003",
                period_kind="year_to_month" if measure == "ytd_increment" else "month",
                period_start=period[:4] + "-01-01"
                if measure == "ytd_increment"
                else period[:7] + "-01",
                period_end=period,
                dimensions={"borrower": "enterprise", "tenor": "long_term", "measure": measure},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="isolated_fixture",
                source_reference=f"fixture:loan:{period}",
                release_event_id=f"fixture:loan:{period}",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
        claim_ids.append(stored.claim_id)
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    cast(dict[str, str], manifest["derived_formula_versions"])["loan_monthly_change"] = (
        "loan-ytd-monthly-change-v0002"
        if measure == "ytd_increment"
        else "loan-stock-monthly-change-v0001"
    )
    context = build_context_projection(
        repository, as_of=timestamp, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    credit = cast(dict[str, object], context.macro["credit"])
    monthly = [
        row
        for row in cast(list[dict[str, object]], credit["evidence"])
        if row["metric_id"] == "CN_LOAN_STRUCTURE"
        and row["dimensions"]
        == {"borrower": "enterprise", "tenor": "long_term", "measure": "monthly_change"}
    ]
    if expected is None:
        assert not monthly
    else:
        assert len(monthly) == 1
        assert monthly[0]["value"] == expected
        assert monthly[0]["period"] == periods[-1][0]
        trace = repository.derived_trace(
            str(monthly[0]["derived_observation_id"]), mode=AsOfMode.PUBLIC, as_of=timestamp
        )
        assert set(trace.input_observation_version_ids) == set(claim_ids)
