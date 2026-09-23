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
    sources: list[tuple[str, str, float | None, EvidenceValueState]] = [
        ("maturity", "fixture_a", 500.0, EvidenceValueState.REPORTED_VALUE)
    ]
    if invalid_injection == "not_disclosed":
        sources.append(("injection", "fixture_a", None, EvidenceValueState.NOT_DISCLOSED))
    else:
        sources.extend(
            [
                ("injection", "fixture_a", 100.0, EvidenceValueState.REPORTED_VALUE),
                ("injection", "fixture_b", 200.0, EvidenceValueState.REPORTED_VALUE),
            ]
        )
    for measure, provider, value, state in sources:
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_OMO_7D_AMOUNT",
                definition_version="metric-catalog-v0003",
                period_kind="business_day",
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions={"measure": measure},
                value=value,
                value_state=state,
                unit="hundred_million_cny",
                provider=provider,
                source_reference=f"fixture:{provider}:{measure}",
                release_event_id=f"fixture:{provider}:{measure}",
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
    cast(dict[str, str], manifest["derived_formula_versions"])["omo_net_injection"] = (
        "repo-net-injection-trading-calendar-v0002"
    )
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC,
    )
    policy = cast(dict[str, object], context.macro["policy_action"])
    rows = cast(list[dict[str, object]], policy["evidence"])
    injection = next(row for row in rows if row.get("dimensions") == {"measure": "injection"})
    assert injection["status"] == invalid_injection
    assert not [
        row
        for row in rows
        if row.get("dimensions") == {"measure": "net_injection"} and row["status"] == "current"
    ]


@pytest.mark.parametrize(
    "case",
    ["invalid_maturity", "invalid_preheat", "later_invalid_target", "later_invalid_maturity_date"],
)
def test_known_invalid_omo_inputs_cannot_disappear_from_period_selection(
    tmp_path: Path, case: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    if case == "invalid_maturity":
        amounts = [
            ("2026-08-21", "injection", 500.0),
            ("2026-08-28", "injection", 1000.0),
            ("2026-08-28", "maturity", None),
        ]
    elif case == "invalid_preheat":
        amounts = [("2026-08-21", "injection", None), ("2026-08-28", "injection", 1000.0)]
    elif case == "later_invalid_maturity_date":
        amounts = [("2026-08-20", "injection", 100.0), ("2026-08-21", "injection", None)]
    else:
        amounts = [
            ("2026-08-21", "injection", 500.0),
            ("2026-08-21", "maturity", 300.0),
            ("2026-08-28", "injection", None),
        ]
    for period, measure, value in amounts:
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_OMO_7D_AMOUNT",
                definition_version="metric-catalog-v0003",
                period_kind="business_day",
                period_start=period,
                period_end=period,
                dimensions={"measure": measure},
                value=value,
                value_state=EvidenceValueState.NOT_DISCLOSED
                if value is None
                else EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="isolated_fixture",
                source_reference=f"fixture:{period}:{measure}",
                release_event_id=f"fixture:{period}:{measure}",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
    if case != "later_invalid_target":
        periods = (
            ("2026-08-27", "2026-08-28")
            if case == "later_invalid_maturity_date"
            else ("2026-08-21", "2026-08-28")
        )
        for period in periods:
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_EQUITY_CORE_000985",
                    definition_version="metric-catalog-v0003",
                    period_kind="business_day",
                    period_start=period,
                    period_end=period,
                    dimensions={},
                    value=5000.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="isolated_fixture",
                    source_reference=f"fixture:calendar:{period}",
                    release_event_id=f"fixture:calendar:{period}",
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
    cast(dict[str, str], manifest["derived_formula_versions"])["omo_net_injection"] = (
        "repo-net-injection-trading-calendar-v0002"
    )
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC,
    )
    policy = cast(dict[str, object], context.macro["policy_action"])
    rows = cast(list[dict[str, object]], policy["evidence"])
    assert not [row for row in rows if row.get("dimensions") == {"measure": "net_injection"}]
    points = repository.metric_series(
        "CN_OMO_7D_AMOUNT",
        mode=AsOfMode.PUBLIC,
        as_of=timestamp,
        definition_version="metric-catalog-v0003",
    )
    assert any(point.value_state is EvidenceValueState.NOT_DISCLOSED for point in points)


@pytest.mark.parametrize("unknown_public_measure", [None, "injection", "maturity"])
def test_real_zero_and_explicit_maturity_use_only_their_actual_inputs(
    tmp_path: Path, unknown_public_measure: str | None
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    current_ids = []
    for period, measure, value in [
        ("2026-08-21", "injection", None),
        ("2026-08-28", "injection", 0.0),
        ("2026-08-28", "maturity", 500.0),
    ]:
        public = None if period == "2026-08-28" and measure == unknown_public_measure else timestamp
        stored = repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_OMO_7D_AMOUNT",
                definition_version="metric-catalog-v0003",
                period_kind="business_day",
                period_start=period,
                period_end=period,
                dimensions={"measure": measure},
                value=value,
                value_state=EvidenceValueState.NOT_DISCLOSED
                if value is None
                else EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="isolated_fixture",
                source_reference=f"fixture:{period}:{measure}",
                release_event_id=f"fixture:{period}:{measure}",
                release_at=public,
                public_available_at=public,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
        if period == "2026-08-28":
            current_ids.append(stored.claim_id)
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    cast(dict[str, str], manifest["derived_formula_versions"])["omo_net_injection"] = (
        "repo-net-injection-trading-calendar-v0002"
    )
    mode = AsOfMode.PUBLIC if unknown_public_measure is None else AsOfMode.SYSTEM
    context = build_context_projection(
        repository, as_of=timestamp, model_manifest=manifest, as_of_mode=mode
    )
    policy = cast(dict[str, object], context.macro["policy_action"])
    net = [
        row
        for row in cast(list[dict[str, object]], policy["evidence"])
        if row.get("dimensions") == {"measure": "net_injection"}
    ]
    assert len(net) == 1
    assert net[0]["value"] == -500.0
    assert net[0]["period"] == "2026-08-28"
    assert net[0]["status"] == "current"
    if unknown_public_measure is None:
        assert net[0]["public_available_at"] == timestamp.isoformat()
    trace = repository.derived_trace(
        str(net[0]["derived_observation_id"]), mode=mode, as_of=timestamp
    )
    assert set(trace.input_observation_version_ids) == set(current_ids)
    assert set(cast(list[str], net[0]["input_observation_version_ids"])) == set(current_ids)
