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


@pytest.mark.parametrize("invalid_injection", ["not_disclosed", "conflicted"])
def test_known_invalid_injection_cannot_be_replaced_by_zero_in_net_flow(
    tmp_path: Path, invalid_injection: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    sources = [("maturity", "fixture_a", 500.0, EvidenceValueState.REPORTED_VALUE)]
    if invalid_injection == "not_disclosed":
        sources.append(("injection", "fixture_a", None, EvidenceValueState.NOT_DISCLOSED))
    else:
        sources.extend([
            ("injection", "fixture_a", 100.0, EvidenceValueState.REPORTED_VALUE),
            ("injection", "fixture_b", 200.0, EvidenceValueState.REPORTED_VALUE),
        ])
    for measure, provider, value, state in sources:
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_OMO_7D_AMOUNT", definition_version="metric-catalog-v0003",
                period_kind="business_day", period_start="2026-08-28", period_end="2026-08-28",
                dimensions={"measure": measure}, value=value, value_state=state,
                unit="hundred_million_cny", provider=provider,
                source_reference=f"fixture:{provider}:{measure}",
                release_event_id=f"fixture:{provider}:{measure}",
                release_at=timestamp, public_available_at=timestamp, fetched_at=timestamp,
                available_at=timestamp, certification_status="certified", quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    cast(dict[str, str], manifest["derived_formula_versions"])["omo_net_injection"] = (
        "repo-net-injection-trading-calendar-v0002"
    )
    context = build_context_projection(
        repository, as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC,
    )
    policy = cast(dict[str, object], context.macro["policy_action"])
    rows = cast(list[dict[str, object]], policy["evidence"])
    injection = next(row for row in rows if row.get("dimensions") == {"measure": "injection"})
    assert injection["status"] == invalid_injection
    assert not [
        row for row in rows
        if row.get("dimensions") == {"measure": "net_injection"}
        and row["status"] == "current"
    ]
