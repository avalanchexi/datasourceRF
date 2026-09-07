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
def test_january_loan_ytd_is_its_own_monthly_flow(
    tmp_path: Path, previous_december: float | None
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 2, 2, tzinfo=UTC)
    inputs = [("2026-01-01", "2026-01-31", 10.0)]
    if previous_december is not None:
        inputs.insert(0, ("2025-01-01", "2025-12-31", previous_december))
    for start, end, value in inputs:
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_LOAN_STRUCTURE",
                definition_version="metric-catalog-v0003",
                period_kind="year_to_month",
                period_start=start,
                period_end=end,
                dimensions={"borrower": "enterprise", "tenor": "long_term", "measure": "ytd_increment"},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="isolated_fixture",
                source_reference=f"fixture:loan:{end}",
                release_event_id=f"fixture:loan:{end}",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    cast(dict[str, str], manifest["derived_formula_versions"])["loan_monthly_change"] = (
        "loan-ytd-monthly-change-v0002"
    )
    context = build_context_projection(
        repository, as_of=timestamp, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    credit = cast(dict[str, object], context.macro["credit"])
    rows = cast(list[dict[str, object]], credit["evidence"])
    monthly = [
        row for row in rows
        if row["metric_id"] == "CN_LOAN_STRUCTURE"
        and row["dimensions"] == {"borrower": "enterprise", "tenor": "long_term", "measure": "monthly_change"}
    ]
    assert len(monthly) == 1
    assert monthly[0]["period"] == "2026-01-31"
    assert monthly[0]["value"] == 10.0
