from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.models import (
    analytical_model_v0002_manifest,
    certified_model_v0001_manifest,
)
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime

OFFICIAL_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"


def _v2_manifest(*certified_metric_ids: str) -> dict[str, object]:
    manifest = analytical_model_v0002_manifest()
    certified = set(certified_metric_ids)
    manifest["metric_definitions"] = [
        {
            **definition,
            "certification_status": (
                "certified"
                if definition["metric_id"] in certified
                else definition["certification_status"]
            ),
        }
        for definition in manifest["metric_definitions"]
    ]
    return manifest


def test_context_formula_dispatch_is_bound_to_the_model_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_OMO_7D_AMOUNT"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for measure, value in (("injection", 3000.0), ("maturity", 2500.0)):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_OMO_7D_AMOUNT",
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions={"measure": measure},
                value=value,
                unit="hundred_million_cny",
            )
        )
    cutoff = datetime(2026, 8, 29, tzinfo=UTC)

    v1 = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=certified_model_v0001_manifest(),
    )
    v2 = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=analytical_model_v0002_manifest(),
    )

    v1_policy = v1.macro["policy_action"]["evidence"]  # type: ignore[index]
    v2_policy = v2.macro["policy_action"]["evidence"]  # type: ignore[index]
    assert not any(
        row.get("formula_version") == "repo-net-injection-v0001"
        for row in v1_policy
    )
    assert any(
        row.get("formula_version") == "repo-net-injection-v0001"
        for row in v2_policy
    )


def test_context_model_manifest_fails_closed_when_catalog_is_inconsistent(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    manifest = analytical_model_v0002_manifest()
    manifest["metric_catalog_version"] = "metric-catalog-tampered"

    with pytest.raises(ValueError, match="context_model_definition_version_mismatch"):
        build_context_projection(
            EvidenceRepository(paths.database),
            as_of=datetime(2026, 8, 30, tzinfo=UTC),
            model_manifest=manifest,
        )


def test_empty_context_is_structured_local_degradation_not_empty_placeholders(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 30, tzinfo=UTC),
        model_manifest=_v2_manifest(),
    )

    assert context.macro["policy_direction"] == "insufficient_data"
    assert context.macro["credit_response"] == "insufficient_data"
    assert context.macro["overheat_state"] == "insufficient_data"
    assert context.macro["price_pressure"] == "insufficient_data"
    assert context.macro["score"] is None
    assert len(context.macro["international_context"]) == 13  # type: ignore[arg-type]
    assert all(
        item["status"] == "awaiting_source_certification"
        for item in context.macro["international_context"]  # type: ignore[union-attr]
    )
    assert context.inventory["quadrant"] is None
    assert len(context.inventory["cards"]) == 7  # type: ignore[arg-type]
    assert context.inventory["score"] is None
    assert context.inventory["semantics"] == {
        "pmi_inventory": "diffusion_index_not_inventory_quantity",
        "futures_warrants": "registered_receipts_not_total_industrial_inventory",
    }


def test_v1_credit_formula_identity_is_not_rewritten_to_v2(tmp_path: Path) -> None:
    manifest = certified_model_v0001_manifest()
    context = build_context_projection(
        EvidenceRepository.create(tmp_path / "v1-formula.sqlite3"),
        as_of=datetime(2026, 8, 30, tzinfo=UTC),
        model_manifest=manifest,
    )

    assert context.macro["credit"]["formula"]["formula_version"] == (  # type: ignore[index]
        "credit-impulse-v0001"
    )


def test_certified_lpr_enters_credit_evidence_with_point_in_time_source_fields(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["dimensions"]["tenor"] for row in lpr_rows} == {"1y", "5y_plus"}
    assert {row["status"] for row in lpr_rows} == {"current"}
    assert {row["source_reference"].split("#", maxsplit=1)[0] for row in lpr_rows} == {
        OFFICIAL_URL
    }
    assert {row["available_at"] for row in lpr_rows} == {"2026-08-20T01:02:00+00:00"}
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    assert context.macro["credit_response"] == "insufficient_data"
    assert context.macro["policy_direction"] == "insufficient_data"


def test_lpr_carries_the_previous_period_as_awaiting_release_not_source_failure(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 9, 10, 2, tzinfo=UTC),
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["period"] for row in lpr_rows} == {"2026-08-31"}
    assert {row["status"] for row in lpr_rows} == {"awaiting_release"}


def test_lpr_gap_uses_a_recorded_source_failure_after_the_release_window(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    failed_at = datetime(2026, 8, 20, 5, tzinfo=UTC)
    repository.record_retrieval_attempt(
        metric_id="CN_LPR_1Y_5Y",
        channel="certified_official_direct",
        outcome="source_failed",
        fetched_at=failed_at,
        safe_metadata={"period": "2026-08"},
    )

    context = build_context_projection(
        repository,
        as_of=failed_at,
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:1]  # type: ignore[index]

    assert lpr_rows[0]["status"] == "source_failed"
    assert lpr_rows[0]["value"] is None


def test_public_context_release_status_uses_public_not_system_visibility(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    public_at = datetime(2026, 8, 20, 1, tzinfo=UTC)
    fetched_at = datetime(2026, 8, 20, 5, tzinfo=UTC)
    for tenor, value in (("1y", 3.0), ("5y_plus", 3.5)):
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_LPR_1Y_5Y",
                definition_version="metric-catalog-v0002",
                period_kind="month",
                period_start="2026-08-01",
                period_end="2026-08-31",
                dimensions={"tenor": tenor},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="中国货币网",
                source_reference=f"fixture:late-fetch:{tenor}",
                release_event_id="chinamoney-lpr:2026-08-20",
                release_at=public_at,
                public_available_at=public_at,
                fetched_at=fetched_at,
                available_at=fetched_at,
                certification_status="certified",
                quality_status="validated",
            )
        )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        as_of_mode=AsOfMode.PUBLIC,
        persist_derived=False,
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["status"] for row in lpr_rows} == {"current"}


def test_conflicted_certified_sources_keep_every_claim_and_do_not_drive_state(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    content = (
        Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
    ).read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )
    conflicting = repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0002",
            period_kind="month",
            period_start="2026-08-01",
            period_end="2026-08-31",
            dimensions={"tenor": "1y"},
            value=3.1,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="certified-secondary-fixture",
            source_reference="fixture:conflicting-lpr-1y",
            release_event_id="fixture:lpr:2026-08",
            release_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
            public_available_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
            fetched_at=datetime(2026, 8, 20, 1, 3, tzinfo=UTC),
            available_at=datetime(2026, 8, 20, 1, 3, tzinfo=UTC),
            certification_status="certified",
            quality_status="validated",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        model_manifest=_v2_manifest(),
    )
    lpr_1y = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["dimensions"] == {"tenor": "1y"}
    )

    assert lpr_1y["status"] == "conflicted"
    assert {claim["value"] for claim in lpr_1y["claims"]} == {3.0, 3.1}
    assert set(ingested.claim_ids) | {conflicting.claim_id} <= set(
        context.observation_version_ids
    )
    assert context.macro["credit_response"] == "insufficient_data"


def test_credit_impulse_is_persisted_with_exact_point_in_time_input_vintages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_SF_TOTAL", "CN_GDP"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    input_claim_ids = []
    for index in range(24):
        year = 2024 + index // 12
        month = index % 12 + 1
        end_day = calendar.monthrange(year, month)[1]
        value = 2.0 if year == 2024 else 3.0
        input_claim_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_SF_TOTAL",
                    period_start=f"{year:04d}-{month:02d}-01",
                    period_end=f"{year:04d}-{month:02d}-{end_day:02d}",
                    dimensions={"measure": "monthly_increment"},
                    value=value,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )
    for index, (period_start, period_end) in enumerate(
        (
            ("2024-01-01", "2024-03-31"),
            ("2024-04-01", "2024-06-30"),
            ("2024-07-01", "2024-09-30"),
            ("2024-10-01", "2024-12-31"),
            ("2025-01-01", "2025-03-31"),
            ("2025-04-01", "2025-06-30"),
            ("2025-07-01", "2025-09-30"),
            ("2025-10-01", "2025-12-31"),
        )
    ):
        input_claim_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_GDP",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                    value=25.0 if index < 4 else 30.0,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )

    cutoff = datetime(2026, 1, 31, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_v2_manifest(*certified_ids),
    )
    formula = context.macro["credit"]["formula"]  # type: ignore[index]
    impulse = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )

    assert formula["status"] == "available"
    assert formula["formula_version"] == "credit-impulse-rolling-share-v0001"
    assert impulse["value"] == pytest.approx(6.0)
    assert impulse["direction"] == "up"
    assert set(impulse["input_observation_version_ids"]) == set(input_claim_ids)
    derived_id = str(impulse["derived_observation_id"])
    assert derived_id in context.observation_version_ids
    trace = repository.derived_trace(derived_id, mode=AsOfMode.SYSTEM, as_of=cutoff)
    assert set(trace.input_observation_version_ids) == set(input_claim_ids)


def test_policy_and_treasury_spreads_are_derived_with_exact_input_vintages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {
        "CN_OMO_7D_RATE",
        "CN_OMO_7D_AMOUNT",
        "CN_DR007",
        "CN_DR007_POLICY_SPREAD",
        "UST2Y_NOMINAL_YIELD",
        "UST10Y_NOMINAL_YIELD",
        "UST_2S10S_SPREAD",
    }

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    inputs: dict[str, str] = {}
    for name, metric_id, dimensions, value, unit in (
        ("rate", "CN_OMO_7D_RATE", {}, 1.4, "percent"),
        ("injection", "CN_OMO_7D_AMOUNT", {"measure": "injection"}, 3000, "hundred_million_cny"),
        ("maturity", "CN_OMO_7D_AMOUNT", {"measure": "maturity"}, 2500, "hundred_million_cny"),
        ("dr007", "CN_DR007", {}, 1.55, "percent"),
        ("ust2", "UST2Y_NOMINAL_YIELD", {}, 3.6, "percent"),
        ("ust10", "UST10Y_NOMINAL_YIELD", {}, 4.2, "percent"),
    ):
        inputs[name] = repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions=dimensions,
                value=value,
                unit=unit,
            )
        ).claim_id

    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_v2_manifest(*certified_ids),
    )
    policy_rows = context.macro["policy_action"]["evidence"]  # type: ignore[index]
    transmission_rows = context.macro["transmission"]["evidence"]  # type: ignore[index]
    international_rows = context.macro["international_context"]  # type: ignore[assignment]
    net = next(row for row in policy_rows if row["dimensions"].get("measure") == "net_injection")
    dr_spread = next(
        row for row in transmission_rows if row["metric_id"] == "CN_DR007_POLICY_SPREAD"
    )
    treasury_spread = next(
        row for row in international_rows if row["metric_id"] == "UST_2S10S_SPREAD"
    )

    assert net["value"] == 500.0
    assert set(net["input_observation_version_ids"]) == {
        inputs["injection"],
        inputs["maturity"],
    }
    assert dr_spread["value"] == pytest.approx(15.0)
    assert set(dr_spread["input_observation_version_ids"]) == {
        inputs["dr007"],
        inputs["rate"],
    }
    assert treasury_spread["value"] == pytest.approx(60.0)
    assert set(treasury_spread["input_observation_version_ids"]) == {
        inputs["ust2"],
        inputs["ust10"],
    }
    for row in (net, dr_spread, treasury_spread):
        trace = repository.derived_trace(
            str(row["derived_observation_id"]),
            mode=AsOfMode.SYSTEM,
            as_of=cutoff,
        )
        assert set(trace.input_observation_version_ids) == set(
            row["input_observation_version_ids"]
        )


def test_credit_impulse_derives_quarter_levels_from_reported_ytd_gdp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_SF_TOTAL", "CN_GDP"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    input_claim_ids: list[str] = []
    for index in range(24):
        year = 2024 + index // 12
        month = index % 12 + 1
        end_day = calendar.monthrange(year, month)[1]
        input_claim_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_SF_TOTAL",
                    period_start=f"{year:04d}-{month:02d}-01",
                    period_end=f"{year:04d}-{month:02d}-{end_day:02d}",
                    dimensions={"measure": "monthly_increment"},
                    value=2.0 if year == 2024 else 3.0,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )
    for year, cumulative_values in (
        (2024, (20.0, 45.0, 70.0, 100.0)),
        (2025, (25.0, 55.0, 90.0, 130.0)),
    ):
        for quarter, cumulative in enumerate(cumulative_values, start=1):
            final_month = quarter * 3
            input_claim_ids.append(
                repository.append_source_claim(
                    _certified_claim(
                        metric_id="CN_GDP",
                        period_start=f"{year:04d}-01-01",
                        period_end=(
                            f"{year:04d}-{final_month:02d}-"
                            f"{calendar.monthrange(year, final_month)[1]:02d}"
                        ),
                        dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
                        value=cumulative,
                        unit="hundred_million_cny",
                    )
                ).claim_id
            )

    cutoff = datetime(2026, 1, 31, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_v2_manifest(*certified_ids),
    )
    formula = context.macro["credit"]["formula"]  # type: ignore[index]
    impulse = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_CREDIT_IMPULSE"
    )

    assert formula["gdp_input_measure"] == "nominal_ytd_level"
    assert impulse["value"] == pytest.approx(100 * (36 / 130 - 24 / 100))
    assert set(impulse["input_observation_version_ids"]) == set(input_claim_ids)


def test_inventory_spreads_and_loan_change_are_derived_without_duplicate_observations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {
        "CN_PMI_ACTIVITY",
        "CN_PMI_INVENTORY",
        "CN_ORDER_INVENTORY_SPREAD",
        "CN_PRODUCTION_ORDER_SPREAD",
        "CN_LOAN_STRUCTURE",
    }

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for metric_id, dimensions, value in (
        ("CN_PMI_ACTIVITY", {"series": "new_orders", "measure": "level"}, 52.0),
        ("CN_PMI_ACTIVITY", {"series": "production", "measure": "level"}, 51.0),
        ("CN_PMI_INVENTORY", {"series": "finished_goods", "measure": "level"}, 48.0),
    ):
        repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions=dimensions,
                value=value,
                unit="diffusion_index_points",
            )
        )
    loan_ids = []
    for period_start, period_end, value in (
        ("2026-06-01", "2026-06-30", 100.0),
        ("2026-07-01", "2026-07-31", 110.0),
    ):
        loan_ids.append(
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_LOAN_STRUCTURE",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions={
                        "borrower": "enterprise",
                        "tenor": "long_term",
                        "measure": "stock_end",
                    },
                    value=value,
                    unit="hundred_million_cny",
                )
            ).claim_id
        )

    cutoff = datetime(2026, 8, 15, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_v2_manifest(*certified_ids),
    )
    inventory_rows = [
        row
        for card in context.inventory["cards"]  # type: ignore[union-attr]
        for row in card["evidence"]
    ]
    order_spread = next(
        row for row in inventory_rows if row["metric_id"] == "CN_ORDER_INVENTORY_SPREAD"
    )
    production_spread = next(
        row for row in inventory_rows if row["metric_id"] == "CN_PRODUCTION_ORDER_SPREAD"
    )
    loan_change = next(
        row
        for row in context.macro["credit"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == "CN_LOAN_STRUCTURE"
        and row["dimensions"]["measure"] == "monthly_change"
    )

    assert order_spread["value"] == 4.0
    assert production_spread["value"] == -1.0
    assert loan_change["value"] == 10.0
    assert set(loan_change["input_observation_version_ids"]) == set(loan_ids)


def test_policy_gross_rows_do_not_double_vote_against_net_tightening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {
        "CN_OMO_7D_AMOUNT",
        "CN_TOOL_LIQUIDITY_MONTHLY",
        "CN_BOND_FULL_PRICE_CNY030",
    }

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for metric_id, dimensions, value in (
        ("CN_OMO_7D_AMOUNT", {"measure": "injection"}, 200.0),
        ("CN_OMO_7D_AMOUNT", {"measure": "maturity"}, 700.0),
        (
            "CN_TOOL_LIQUIDITY_MONTHLY",
            {"tool": "mlf", "measure": "injection"},
            500.0,
        ),
        (
            "CN_TOOL_LIQUIDITY_MONTHLY",
            {"tool": "mlf", "measure": "withdrawal"},
            600.0,
        ),
        (
            "CN_TOOL_LIQUIDITY_MONTHLY",
            {"tool": "mlf", "measure": "net_injection"},
            -100.0,
        ),
    ):
        repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start="2026-08-01",
                period_end="2026-08-28",
                dimensions=dimensions,
                value=value,
                unit="hundred_million_cny",
            )
        )
    for period_end, value in (("2026-08-27", 102.0), ("2026-08-28", 100.0)):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_BOND_FULL_PRICE_CNY030",
                period_start=period_end,
                period_end=period_end,
                dimensions={},
                value=value,
                unit="scalar",
            )
        )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_v2_manifest(*certified_ids),
    )

    assert context.macro["policy_direction"] == "tightening"


def test_first_rrr_event_uses_change_measures_not_level_differences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_RRR_EVENT", "CN_BOND_FULL_PRICE_CNY030"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for measure, value, unit in (
        ("rrr_change", -0.5, "percentage_points"),
        ("post_change_rrr", 6.5, "percent"),
        ("released_funds", 10000.0, "hundred_million_cny"),
    ):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_RRR_EVENT",
                period_start="2026-08-28",
                period_end="2026-08-28",
                dimensions={"scope": "financial_institutions", "measure": measure},
                value=value,
                unit=unit,
            )
        )
    for period_end, value in (("2026-08-27", 100.0), ("2026-08-28", 102.0)):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_BOND_FULL_PRICE_CNY030",
                period_start=period_end,
                period_end=period_end,
                dimensions={},
                value=value,
                unit="scalar",
            )
        )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_v2_manifest(*certified_ids),
    )

    assert context.macro["policy_direction"] == "easing"


def test_real_inventory_uses_nominal_level_not_official_yoy_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_FINISHED_GOODS_INVENTORY", "CN_PPI"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for dimensions, value, unit in (
        ({"measure": "official_yoy"}, 2.1, "percent"),
        ({"measure": "nominal_end_level"}, 67000.0, "hundred_million_cny"),
    ):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_FINISHED_GOODS_INVENTORY",
                period_start="2026-08-01",
                period_end="2026-08-28",
                dimensions=dimensions,
                value=value,
                unit=unit,
            )
        )
    repository.append_source_claim(
        _certified_claim(
            metric_id="CN_PPI",
            period_start="2026-08-01",
            period_end="2026-08-28",
            dimensions={"measure": "yoy", "category": "headline"},
            value=-2.0,
            unit="percent",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_v2_manifest(*certified_ids),
    )
    approximation = context.inventory["real_inventory_approximation"]  # type: ignore[index]

    assert approximation["value"] == pytest.approx(67000.0 / 0.98)
    assert approximation["nominal_inventory"]["dimensions"] == {  # type: ignore[index]
        "measure": "nominal_end_level"
    }


def _certified_claim(
    *,
    metric_id: str,
    period_start: str,
    period_end: str,
    dimensions: dict[str, str],
    value: float,
    unit: str,
) -> SourceClaimInput:
    available = datetime(2026, 1, 15, tzinfo=UTC)
    return SourceClaimInput(
        metric_id=metric_id,
        definition_version="metric-catalog-v0002",
        period_kind="quarter" if metric_id == "CN_GDP" else "month",
        period_start=period_start,
        period_end=period_end,
        dimensions=dimensions,
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit=unit,
        provider="certified-fixture",
        source_reference=f"fixture:{metric_id}:{period_end}:{sorted(dimensions.items())}",
        release_event_id=f"release:{metric_id}:{period_end}",
        release_at=available,
        public_available_at=available,
        fetched_at=available,
        available_at=available,
        certification_status="certified",
        quality_status="validated",
    )
