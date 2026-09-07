from __future__ import annotations

import calendar
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import analytical_model_v0002_manifest


@pytest.mark.parametrize("credit_enabled", [False, True])
def test_only_enabled_formulas_require_their_model_input_definitions(
    tmp_path: Path, credit_enabled: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [
        asdict(definition)
        for definition in metric_catalog_v0003()
        if definition.metric_id != "CN_GDP"
    ]
    if not credit_enabled:
        cast(dict[str, str], manifest["derived_formula_versions"]).pop("credit_impulse")
    if credit_enabled:
        with pytest.raises(ValueError, match="^context_model_metric_missing:CN_GDP$"):
            build_context_projection(
                repository, as_of=datetime(2026, 8, 29, tzinfo=UTC), model_manifest=manifest
            )
    else:
        context = build_context_projection(
            repository, as_of=datetime(2026, 8, 29, tzinfo=UTC), model_manifest=manifest
        )
        credit = cast(dict[str, object], context.macro["credit"])
        formula = cast(dict[str, object], credit["formula"])
        assert formula["status"] == "disabled_by_model"


@pytest.mark.parametrize("blocked_metric", ["CN_DR007", "CN_OMO_7D_RATE", "CN_DR007_POLICY_SPREAD"])
def test_uncertified_model_input_cannot_become_a_certified_policy_spread(
    tmp_path: Path, blocked_metric: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    input_ids = {}
    for metric_id, value in (("CN_DR007", 1.3859), ("CN_OMO_7D_RATE", 1.4)):
        stored = repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version="metric-catalog-v0003",
                period_kind="business_day",
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="isolated_fixture",
                source_reference=f"fixture:{metric_id}",
                release_event_id=f"fixture:{metric_id}:2026-08-28",
                release_at=timestamp,
                public_available_at=timestamp,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
        input_ids[metric_id] = stored.claim_id
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [
        {
            **asdict(definition),
            "certification_status": (
                "awaiting_source_certification"
                if definition.metric_id == blocked_metric
                else definition.certification_status
            ),
        }
        for definition in metric_catalog_v0003()
    ]

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.PUBLIC,
        persist_derived=False,
    )
    transmission = cast(dict[str, object], context.macro["transmission"])
    rows = cast(list[dict[str, object]], transmission["evidence"])
    dr007 = next(row for row in rows if row["metric_id"] == "CN_DR007")
    spread = next(row for row in rows if row["metric_id"] == "CN_DR007_POLICY_SPREAD")
    if blocked_metric == "CN_DR007":
        assert dr007["value"] is None
        assert dr007["status"] == "awaiting_source_certification"
    assert spread["value"] is None
    assert input_ids["CN_DR007"] in context.observation_version_ids
    adopted = cast(list[str], context.macro["model_input_observation_version_ids"])
    if blocked_metric in input_ids:
        assert input_ids[blocked_metric] not in adopted
    assert "derived_observation_id" not in spread


@pytest.mark.parametrize(
    "blocked_metric", [None, "UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD", "UST_2S10S_SPREAD"]
)
def test_treasury_spread_requires_both_inputs_and_output_certified_by_model(
    tmp_path: Path, blocked_metric: str | None
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 9, 5, tzinfo=UTC)
    for metric_id, value in (("UST2Y_NOMINAL_YIELD", 4.37), ("UST10Y_NOMINAL_YIELD", 4.78)):
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version="metric-catalog-v0003",
                period_kind="business_day",
                period_start="2026-09-04",
                period_end="2026-09-04",
                dimensions={},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="isolated_fixture",
                source_reference=f"fixture:{metric_id}",
                release_event_id=f"fixture:{metric_id}:2026-09-04",
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
    manifest["metric_definitions"] = [
        {
            **asdict(definition),
            "certification_status": (
                "awaiting_source_certification"
                if definition.metric_id == blocked_metric
                else definition.certification_status
            ),
        }
        for definition in metric_catalog_v0003()
    ]
    cutoff = datetime(2026, 9, 6, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=manifest,
        as_of_mode=AsOfMode.SYSTEM,
    )
    rows = cast(list[dict[str, object]], context.macro["international_context"])
    spread = next(row for row in rows if row["metric_id"] == "UST_2S10S_SPREAD")
    if blocked_metric is None:
        assert spread["value"] == pytest.approx(41.0)
        trace = repository.derived_trace(
            str(spread["derived_observation_id"]),
            mode=AsOfMode.SYSTEM,
            as_of=cutoff,
        )
        assert len(trace.input_observation_version_ids) == 2
    else:
        assert spread["value"] is None
        assert "derived_observation_id" not in spread


@pytest.mark.parametrize(
    "blocked_metric,unknown_omo_time",
    [
        (None, False),
        ("CN_PMI_ACTIVITY", False),
        ("CN_PMI_INVENTORY", False),
        ("CN_ORDER_INVENTORY_SPREAD", False),
        ("CN_PRODUCTION_ORDER_SPREAD", False),
        ("CN_LOAN_STRUCTURE", False),
        ("CN_OMO_7D_AMOUNT", False),
        (None, True),
    ],
)
def test_macro_derived_rows_do_not_bypass_model_certification(
    tmp_path: Path, blocked_metric: str | None, unknown_omo_time: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    for metric_id, start, end, dimensions, value, unit in (
        (
            "CN_PMI_ACTIVITY",
            "2026-07-01",
            "2026-07-31",
            {"series": "new_orders", "measure": "level"},
            52.0,
            "diffusion_index_points",
        ),
        (
            "CN_PMI_ACTIVITY",
            "2026-07-01",
            "2026-07-31",
            {"series": "production", "measure": "level"},
            51.0,
            "diffusion_index_points",
        ),
        (
            "CN_PMI_INVENTORY",
            "2026-07-01",
            "2026-07-31",
            {"series": "finished_goods", "measure": "level"},
            48.0,
            "diffusion_index_points",
        ),
        (
            "CN_LOAN_STRUCTURE",
            "2026-06-01",
            "2026-06-30",
            {"borrower": "enterprise", "tenor": "long_term", "measure": "stock_end"},
            100.0,
            "hundred_million_cny",
        ),
        (
            "CN_LOAN_STRUCTURE",
            "2026-07-01",
            "2026-07-31",
            {"borrower": "enterprise", "tenor": "long_term", "measure": "stock_end"},
            110.0,
            "hundred_million_cny",
        ),
        (
            "CN_OMO_7D_AMOUNT",
            "2026-08-28",
            "2026-08-28",
            {"measure": "injection"},
            3000.0,
            "hundred_million_cny",
        ),
        (
            "CN_OMO_7D_AMOUNT",
            "2026-08-28",
            "2026-08-28",
            {"measure": "maturity"},
            2500.0,
            "hundred_million_cny",
        ),
    ):
        public_time = (
            None
            if unknown_omo_time
            and metric_id == "CN_OMO_7D_AMOUNT"
            and dimensions == {"measure": "injection"}
            else timestamp
        )
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version="metric-catalog-v0003",
                period_kind="business_day" if start == end else "month",
                period_start=start,
                period_end=end,
                dimensions=dimensions,
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=unit,
                provider="isolated_fixture",
                source_reference=f"fixture:{metric_id}:{start}:{dimensions}",
                release_event_id=f"fixture:{metric_id}:{start}:{dimensions}",
                release_at=public_time,
                public_available_at=public_time,
                fetched_at=timestamp,
                available_at=timestamp,
                certification_status="certified",
                quality_status="validated",
            )
        )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [
        {
            **asdict(definition),
            "certification_status": (
                "awaiting_source_certification"
                if definition.metric_id == blocked_metric
                else definition.certification_status
            ),
        }
        for definition in metric_catalog_v0003()
    ]
    formulas = cast(dict[str, str], manifest["derived_formula_versions"])
    formulas["order_inventory_spread"] = "pmi-order-inventory-spread-v0001"
    formulas["production_order_spread"] = "pmi-production-order-spread-v0001"
    if unknown_omo_time:
        formulas["omo_net_injection"] = "repo-net-injection-trading-calendar-v0002"
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.SYSTEM if unknown_omo_time else AsOfMode.PUBLIC,
    )

    def documents(value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            return [value, *(row for child in value.values() for row in documents(child))]
        if isinstance(value, list):
            return [row for child in value for row in documents(child)]
        return []

    rows = documents(context.macro) + documents(context.inventory)
    for formula, blocked, expected in (
        (
            "pmi-order-inventory-spread-v0001",
            {"CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_ORDER_INVENTORY_SPREAD"},
            4.0,
        ),
        (
            "pmi-production-order-spread-v0001",
            {"CN_PMI_ACTIVITY", "CN_PRODUCTION_ORDER_SPREAD"},
            -1.0,
        ),
        ("loan-stock-monthly-change-v0001", {"CN_LOAN_STRUCTURE"}, 10.0),
        (formulas["omo_net_injection"], {"CN_OMO_7D_AMOUNT"}, 500.0),
    ):
        derived = [
            row
            for row in rows
            if row.get("formula_version") == formula and "derived_observation_id" in row
        ]
        if blocked_metric in blocked:
            assert not derived, (blocked_metric, formula)
        else:
            assert derived, formula
            assert all(row["value"] == expected for row in derived)
            if unknown_omo_time and formula == formulas["omo_net_injection"]:
                assert all(row["public_available_at"] is None for row in derived)


@pytest.mark.parametrize(
    "blocked_metric,unknown_public_metric",
    [
        (None, None),
        ("CN_SF_TOTAL", None),
        ("CN_GDP", None),
        ("CN_CREDIT_IMPULSE", None),
        (None, "CN_SF_TOTAL"),
        (None, "CN_GDP"),
    ],
)
def test_credit_impulse_requires_model_certification_for_gdp_and_social_financing(
    tmp_path: Path, blocked_metric: str | None, unknown_public_metric: str | None
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    for index in range(24):
        year, month0 = divmod(2024 * 12 + 6 + index, 12)
        month = month0 + 1
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
        specs = [
            (
                "CN_SF_TOTAL",
                start,
                end,
                {"measure": "monthly_increment"},
                2.0 if index < 12 else 3.0,
            )
        ]
        if month % 3 == 0:
            specs.append(
                (
                    "CN_GDP",
                    f"{year:04d}-{month - 2:02d}-01",
                    end,
                    {"aggregate": "total", "measure": "nominal_quarterly_level"},
                    25.0 if index < 12 else 30.0,
                )
            )
        for metric_id, period_start, period_end, dimensions, value in specs:
            public_time = (
                None
                if metric_id == unknown_public_metric
                and index == (2 if metric_id == "CN_GDP" else 0)
                else timestamp
            )
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0003",
                    period_kind="quarter" if metric_id == "CN_GDP" else "month",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions=dimensions,
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="hundred_million_cny",
                    provider="isolated_fixture",
                    source_reference=f"fixture:{metric_id}:{period_end}",
                    release_event_id=f"fixture:{metric_id}:{period_end}",
                    release_at=public_time,
                    public_available_at=public_time,
                    fetched_at=timestamp,
                    available_at=timestamp,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [
        {
            **asdict(definition),
            "certification_status": (
                "awaiting_source_certification"
                if definition.metric_id == blocked_metric
                else definition.certification_status
            ),
        }
        for definition in metric_catalog_v0003()
    ]
    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=manifest,
        as_of_mode=AsOfMode.SYSTEM if unknown_public_metric else AsOfMode.PUBLIC,
    )
    credit = cast(dict[str, object], context.macro["credit"])
    rows = cast(list[dict[str, object]], credit["evidence"])
    impulse = next(row for row in rows if row["metric_id"] == "CN_CREDIT_IMPULSE")
    formula = cast(dict[str, object], credit["formula"])
    if blocked_metric is None:
        # Independently worked example: 36/120 - 24/100 = 0.06 = 6 percentage points.
        assert impulse["value"] == pytest.approx(6.0)
        assert formula["status"] == "available"
        if unknown_public_metric:
            assert impulse["public_available_at"] is None
    else:
        assert impulse["value"] is None
        assert formula["status"] == "uncertified_model_dependencies"
        assert formula["formula_version"] == "credit-impulse-rolling-share-v0001"


@pytest.mark.parametrize("calendar_certified", [True, False])
def test_omo_maturity_does_not_use_an_uncertified_model_calendar(
    tmp_path: Path, calendar_certified: bool
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    timestamp = datetime(2026, 8, 28, 10, tzinfo=UTC)
    for period, amount in (("2026-08-21", 2500.0), ("2026-08-28", 3000.0)):
        for metric_id, dimensions, value, unit in (
            ("CN_OMO_7D_AMOUNT", {"measure": "injection"}, amount, "hundred_million_cny"),
            ("CN_EQUITY_CORE_000985", {}, 5000.0, "index_points"),
        ):
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0003",
                    period_kind="business_day",
                    period_start=period,
                    period_end=period,
                    dimensions=dimensions,
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=unit,
                    provider="isolated_fixture",
                    source_reference=f"fixture:{metric_id}:{period}",
                    release_event_id=f"fixture:{metric_id}:{period}",
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
    manifest["metric_definitions"] = [
        {
            **asdict(definition),
            "certification_status": (
                "awaiting_source_certification"
                if definition.metric_id == "CN_EQUITY_CORE_000985" and not calendar_certified
                else definition.certification_status
            ),
        }
        for definition in metric_catalog_v0003()
    ]
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
    net = [row for row in rows if row.get("dimensions") == {"measure": "net_injection"}]
    if calendar_certified:
        assert len(net) == 1
        assert net[0]["value"] == 500.0
    else:
        assert not net
