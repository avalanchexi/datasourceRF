from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import analytical_model_v0002_manifest


@pytest.mark.parametrize("same_period", [True, False])
def test_inventory_approximation_does_not_combine_different_months(
    tmp_path: Path, same_period: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    for metric_id, dimensions, value, unit in (
        ("CN_FINISHED_GOODS_INVENTORY", {"measure": "nominal_end_level"}, 105.0,
         "hundred_million_cny"),
        ("CN_PPI", {"measure": "yoy", "category": "headline"}, 5.0, "percent"),
    ):
        month = "06" if metric_id == "CN_PPI" and not same_period else "07"
        end = f"2026-{month}-" + ("30" if month == "06" else "31")
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id, definition_version="metric-catalog-v0003",
                period_kind="month", period_start=f"2026-{month}-01", period_end=end,
                dimensions=dimensions, value=value, value_state=EvidenceValueState.REPORTED_VALUE,
                unit=unit, provider="isolated_fixture", source_reference=f"fixture:{metric_id}",
                release_event_id=f"fixture:{metric_id}:{end}", release_at=timestamp,
                public_available_at=timestamp, fetched_at=timestamp, available_at=timestamp,
                certification_status="certified", quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(definition) for definition in metric_catalog_v0003()]
    context = build_context_projection(
        repository, as_of=datetime(2026, 8, 29, tzinfo=UTC), model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC, persist_derived=False,
    )
    proxy = cast(dict[str, object], context.inventory["real_inventory_approximation"])
    if same_period:
        # Independent worked example: a nominal 105 at +5% prices adjusts to 100.
        assert proxy["value"] == 100.0
        assert proxy["status"] == "available"
    else:
        assert proxy["value"] is None
        assert proxy["status"] == "period_mismatch"
