from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import _role_direction, build_context_projection
from pring_cycle.domain.macro import EvidenceSignal
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


def test_role_direction_distinguishes_conflict_from_missing_data() -> None:
    common = {
        "role": "production",
        "freshness": "current",
        "conflict": False,
    }
    signals = [
        EvidenceSignal("observation-up", "CN_INDUSTRIAL_VA", "up", **common),
        EvidenceSignal(
            "observation-down",
            "CN_CAPACITY_UTILIZATION",
            "down",
            **common,
        ),
    ]

    assert _role_direction(signals, "production") == "conflict"
    assert _role_direction(signals, "demand") is None


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


def _repo_maturity_manifest(*certified_metric_ids: str) -> dict[str, object]:
    manifest = _v2_manifest(*certified_metric_ids)
    formulas = dict(manifest["derived_formula_versions"])  # type: ignore[arg-type]
    formulas["omo_net_injection"] = "repo-net-injection-trading-calendar-v0002"
    manifest["derived_formula_versions"] = formulas
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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
        model_manifest=_v2_manifest(*certified_ids),
    )

    v1_policy = v1.macro["policy_action"]["evidence"]  # type: ignore[index]
    v2_policy = v2.macro["policy_action"]["evidence"]  # type: ignore[index]
    assert not any(row.get("formula_version") == "repo-net-injection-v0001" for row in v1_policy)
    assert any(row.get("formula_version") == "repo-net-injection-v0001" for row in v2_policy)


def test_repo_net_injection_derives_maturity_from_certified_operation_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    certified_ids = {"CN_OMO_7D_AMOUNT"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id in certified_ids
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    operation_ids: dict[str, str] = {}
    calendar_ids: dict[str, str] = {}
    for period_end, value in (("2026-08-21", 2500.0), ("2026-08-28", 3000.0)):
        operation_ids[period_end] = repository.append_source_claim(
            _certified_claim(
                metric_id="CN_OMO_7D_AMOUNT",
                period_start=period_end,
                period_end=period_end,
                dimensions={"measure": "injection"},
                value=value,
                unit="hundred_million_cny",
            )
        ).claim_id
        calendar_ids[period_end] = repository.append_source_claim(
            _certified_claim(
                metric_id="CN_EQUITY_CORE_000985",
                period_start=period_end,
                period_end=period_end,
                dimensions={},
                value=100.0,
                unit="index_points",
            )
        ).claim_id

    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_repo_maturity_manifest(*certified_ids),
    )
    net = next(
        row
        for row in context.macro["policy_action"]["evidence"]  # type: ignore[index]
        if row["dimensions"].get("measure") == "net_injection"
    )

    assert net["value"] == 500.0
    assert net["maturity_basis"] == "derived_7d_trading_calendar"
    expected_inputs = {*operation_ids.values(), calendar_ids["2026-08-28"]}
    assert set(net["input_observation_version_ids"]) == expected_inputs
    trace = repository.derived_trace(
        str(net["derived_observation_id"]),
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
    )
    assert set(trace.input_observation_version_ids) == expected_inputs


def test_repo_net_injection_v1_keeps_frozen_same_day_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    monkeypatch.setattr(
        evidence_module,
        "metric_definition",
        lambda metric_id, *, definition_version="metric-catalog-v0002", database_path=None: replace(
            metric_definition(
                metric_id, definition_version=definition_version, database_path=database_path
            ),
            certification_status=(
                "certified"
                if metric_id == "CN_OMO_7D_AMOUNT"
                else metric_definition(
                    metric_id,
                    definition_version=definition_version,
                ).certification_status
            ),
        ),
    )
    for metric_id, period_end, dimensions, value, unit in (
        (
            "CN_OMO_7D_AMOUNT",
            "2026-08-21",
            {"measure": "injection"},
            2500.0,
            "hundred_million_cny",
        ),
        ("CN_EQUITY_CORE_000985", "2026-08-28", {}, 100.0, "index_points"),
    ):
        repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start=period_end,
                period_end=period_end,
                dimensions=dimensions,
                value=value,
                unit=unit,
            )
        )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_v2_manifest("CN_OMO_7D_AMOUNT"),
    )

    assert not any(
        row["dimensions"].get("measure") == "net_injection"
        for row in context.macro["policy_action"]["evidence"]  # type: ignore[index]
    )


def test_repo_net_injection_emits_withdrawal_when_only_maturity_occurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id == "CN_OMO_7D_AMOUNT"
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    operation_id = repository.append_source_claim(
        _certified_claim(
            metric_id="CN_OMO_7D_AMOUNT",
            period_start="2026-08-21",
            period_end="2026-08-21",
            dimensions={"measure": "injection"},
            value=2500.0,
            unit="hundred_million_cny",
        )
    ).claim_id
    calendar_ids: dict[str, str] = {}
    for period_end in ("2026-08-21", "2026-08-28"):
        calendar_ids[period_end] = repository.append_source_claim(
            _certified_claim(
                metric_id="CN_EQUITY_CORE_000985",
                period_start=period_end,
                period_end=period_end,
                dimensions={},
                value=100.0,
                unit="index_points",
            )
        ).claim_id

    cutoff = datetime(2026, 8, 29, tzinfo=UTC)
    context = build_context_projection(
        repository,
        as_of=cutoff,
        model_manifest=_repo_maturity_manifest("CN_OMO_7D_AMOUNT"),
    )
    net = next(
        row
        for row in context.macro["policy_action"]["evidence"]  # type: ignore[index]
        if row["dimensions"].get("measure") == "net_injection"
    )

    assert net["period"] == "2026-08-28"
    assert net["value"] == -2500.0
    assert net["maturity_basis"] == "derived_7d_trading_calendar"
    assert set(net["input_observation_version_ids"]) == {
        operation_id,
        calendar_ids["2026-08-28"],
    }


def test_reported_repo_net_injection_cannot_bypass_certified_formula(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
        )
        return (
            replace(definition, certification_status="certified")
            if metric_id == "CN_OMO_7D_AMOUNT"
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for measure, value in (
        ("injection", 3000.0),
        ("maturity", 2500.0),
        ("net_injection", 9999.0),
    ):
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

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_repo_maturity_manifest("CN_OMO_7D_AMOUNT"),
    )
    net_rows = [
        row
        for row in context.macro["policy_action"]["evidence"]  # type: ignore[index]
        if row["dimensions"].get("measure") == "net_injection"
    ]

    assert len(net_rows) == 1
    assert net_rows[0]["value"] == 500.0
    assert net_rows[0]["formula_version"] == "repo-net-injection-trading-calendar-v0002"


def test_reported_repo_net_injection_is_hidden_without_formula_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    monkeypatch.setattr(
        evidence_module,
        "metric_definition",
        lambda metric_id, *, definition_version="metric-catalog-v0002", database_path=None: replace(
            metric_definition(
                metric_id, definition_version=definition_version, database_path=database_path
            ),
            certification_status=(
                "certified"
                if metric_id == "CN_OMO_7D_AMOUNT"
                else metric_definition(
                    metric_id,
                    definition_version=definition_version,
                ).certification_status
            ),
        ),
    )
    repository.append_source_claim(
        _certified_claim(
            metric_id="CN_OMO_7D_AMOUNT",
            period_start="2026-08-28",
            period_end="2026-08-28",
            dimensions={"measure": "net_injection"},
            value=9999.0,
            unit="hundred_million_cny",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
        model_manifest=_repo_maturity_manifest("CN_OMO_7D_AMOUNT"),
    )

    assert not any(
        row["dimensions"].get("measure") == "net_injection"
        for row in context.macro["policy_action"]["evidence"]  # type: ignore[index]
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
        item["status"] == "missing"
        for item in context.macro["international_context"]  # type: ignore[union-attr]
    )
    assert context.inventory["quadrant"] is None
    assert len(context.inventory["cards"]) == 7  # type: ignore[arg-type]
    assert context.inventory["score"] is None
    assert context.inventory["semantics"] == {
        "pmi_inventory": "diffusion_index_not_inventory_quantity",
        "futures_warrants": "registered_receipts_not_total_industrial_inventory",
    }


def test_historical_context_excludes_observations_after_target_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    metric_id = "CN_BOND_FULL_PRICE_CNY030"

    def certified_definition(  # type: ignore[no-untyped-def]
        requested_metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            requested_metric_id,
            definition_version=definition_version,
            database_path=database_path,
        )
        return (
            replace(definition, certification_status="certified")
            if requested_metric_id == metric_id
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    for period_end, value in (("2026-08-03", 100.0), ("2026-08-28", 200.0)):
        repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start=period_end,
                period_end=period_end,
                dimensions={},
                value=value,
                unit="scalar",
            )
        )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-03",
        model_manifest=_v2_manifest(metric_id),
    )
    rows = context.macro["transmission"]["evidence"]  # type: ignore[index]
    selected = next(row for row in rows if row["metric_id"] == metric_id)

    assert selected["period"] == "2026-08-03"
    assert selected["value"] == 100.0


def test_historical_context_excludes_period_ended_but_not_yet_public_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    metric_id = "CN_BOND_FULL_PRICE_CNY030"

    def certified_definition(  # type: ignore[no-untyped-def]
        requested_metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            requested_metric_id, definition_version=definition_version, database_path=database_path
        )
        return (
            replace(definition, certification_status="certified")
            if requested_metric_id == metric_id
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    earlier = _certified_claim(
        metric_id=metric_id,
        period_start="2026-06-30",
        period_end="2026-06-30",
        dimensions={},
        value=100.0,
        unit="scalar",
    )
    late_public = replace(
        _certified_claim(
            metric_id=metric_id,
            period_start="2026-07-31",
            period_end="2026-07-31",
            dimensions={},
            value=200.0,
            unit="scalar",
        ),
        release_at=datetime(2026, 8, 20, tzinfo=UTC),
        public_available_at=datetime(2026, 8, 20, tzinfo=UTC),
    )
    repository.append_source_claims((earlier, late_public))

    before_release = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-03",
        model_manifest=_v2_manifest(metric_id),
    )
    after_release = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-21",
        model_manifest=_v2_manifest(metric_id),
    )
    before = next(
        row
        for row in before_release.macro["transmission"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == metric_id
    )
    after = next(
        row
        for row in after_release.macro["transmission"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == metric_id
    )
    assert before["period"] == "2026-06-30"
    assert before["value"] == 100.0
    assert after["period"] == "2026-07-31"
    assert after["value"] == 200.0


def test_historical_context_reselects_same_provider_revision_visible_at_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    metric_id = "CN_BOND_FULL_PRICE_CNY030"

    def certified_definition(  # type: ignore[no-untyped-def]
        requested_metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            requested_metric_id, definition_version=definition_version, database_path=database_path
        )
        return (
            replace(definition, certification_status="certified")
            if requested_metric_id == metric_id
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    base = _certified_claim(
        metric_id=metric_id,
        period_start="2026-07-31",
        period_end="2026-07-31",
        dimensions={},
        value=100.0,
        unit="scalar",
    )
    fetched_at = datetime(2026, 8, 31, tzinfo=UTC)
    repository.append_source_claims(
        (
            replace(
                base,
                provider="official-publisher",
                source_reference="fixture:official-publisher",
                release_event_id="release:official-publisher:revision",
                release_at=datetime(2026, 8, 20, tzinfo=UTC),
                public_available_at=datetime(2026, 8, 20, tzinfo=UTC),
                fetched_at=fetched_at,
                available_at=fetched_at,
                value=101.0,
            ),
            replace(
                base,
                provider="official-publisher",
                source_reference="fixture:official-publisher",
                release_event_id="release:official-publisher",
                release_at=datetime(2026, 7, 31, tzinfo=UTC),
                public_available_at=datetime(2026, 7, 31, tzinfo=UTC),
                fetched_at=datetime(2026, 7, 31, 1, tzinfo=UTC),
                available_at=datetime(2026, 7, 31, 1, tzinfo=UTC),
            ),
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, 1, tzinfo=UTC),
        target_business_date="2026-08-03",
        model_manifest=_v2_manifest(metric_id),
    )
    selected = next(
        row
        for row in context.macro["transmission"]["evidence"]  # type: ignore[index]
        if row["metric_id"] == metric_id
    )

    assert selected["value"] == 100.0
    assert selected["source_reference"] == "fixture:official-publisher"


# Unknown publication is now inferred from the registered cadence (ADR-0021), so only the
# future-month case is still rejected.
@pytest.mark.parametrize("public_available", (True,))
def test_target_bound_context_rejects_future_month_or_unknown_public_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    public_available: bool,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    metric_id = "CN_INDUSTRIAL_VA"

    def certified_definition(  # type: ignore[no-untyped-def]
        requested_metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            requested_metric_id, definition_version=definition_version, database_path=database_path
        )
        return (
            replace(definition, certification_status="certified")
            if requested_metric_id == metric_id
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    public_at = datetime(2026, 8, 20, tzinfo=UTC)
    repository.append_source_claim(
        replace(
            _certified_claim(
                metric_id=metric_id,
                period_start="2026-09-01" if public_available else "2026-07-01",
                period_end="2026-09-30" if public_available else "2026-07-31",
                dimensions={"measure": "yoy"},
                value=5.0,
                unit="scalar",
            ),
            release_at=public_at,
            public_available_at=public_at if public_available else None,
            fetched_at=datetime(2026, 8, 31, tzinfo=UTC),
            available_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, 1, tzinfo=UTC),
        target_business_date="2026-08-28",
        model_manifest=_v2_manifest(metric_id),
    )
    row = next(
        item
        for item in context.macro["overheat"]["gaps"]  # type: ignore[index]
        if item["metric_id"] == metric_id
    )

    assert row["value"] is None
    assert row["freshness"] != "current"


def test_target_bound_lpr_status_uses_the_target_period_not_the_run_month(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 31, 16, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 31, 16, tzinfo=UTC),
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 31, 16, 30, tzinfo=UTC),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
        model_manifest=_v2_manifest("CN_LPR_1Y_5Y"),
    )
    rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["period"] for row in rows} == {"2026-08-31"}
    assert {row["status"] for row in rows} == {"current"}


def test_the_latest_event_before_the_visible_window_is_the_current_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    metric_id = "CN_RRR_EVENT"

    def certified_definition(  # type: ignore[no-untyped-def]
        requested_metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            requested_metric_id, definition_version=definition_version, database_path=database_path
        )
        return (
            replace(definition, certification_status="certified")
            if requested_metric_id == metric_id
            else definition
        )

    monkeypatch.setattr(evidence_module, "metric_definition", certified_definition)
    repository.append_source_claim(
        _certified_claim(
            metric_id=metric_id,
            period_start="2025-05-15",
            period_end="2025-05-15",
            dimensions={"measure": "rrr_change", "scope": "financial_institutions"},
            value=-0.5,
            unit="percentage_points",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
        model_manifest=_v2_manifest(metric_id),
    )
    row = next(
        item
        for item in context.macro["policy_action"]["evidence"]  # type: ignore[index]
        if item["metric_id"] == metric_id
    )

    # ADR-0028 (event #05): the change in force is shown however old, not "no event".
    assert (row["status"], row["value"]) == ("current", -0.5)


def test_uncertified_event_history_cannot_prove_no_event_in_visible_window(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    metric_id = "CN_RRR_EVENT"
    candidate = _certified_claim(
        metric_id=metric_id,
        period_start="2025-05-15",
        period_end="2025-05-15",
        dimensions={"measure": "rrr_change", "scope": "financial_institutions"},
        value=-0.5,
        unit="percentage_points",
    )
    repository.append_source_claim(
        replace(
            candidate,
            certification_status="awaiting_source_certification",
            quality_status="unverified",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
        model_manifest=_v2_manifest(metric_id),
    )
    row = next(
        item
        for item in context.macro["policy_action"]["evidence"]  # type: ignore[index]
        if item["metric_id"] == metric_id
    )

    assert row["status"] != "no_event_in_visible_window"


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
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )

    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:2]  # type: ignore[index]

    assert {row["dimensions"]["tenor"] for row in lpr_rows} == {"1y", "5y_plus"}
    assert {row["status"] for row in lpr_rows} == {"current"}
    assert {row["source_reference"].split("#", maxsplit=1)[0] for row in lpr_rows} == {OFFICIAL_URL}
    assert {row["available_at"] for row in lpr_rows} == {"2026-08-20T01:02:00+00:00"}
    assert set(ingested.claim_ids) <= set(context.observation_version_ids)
    assert context.macro["credit_response"] == "insufficient_data"
    assert context.macro["policy_direction"] == "insufficient_data"


def test_lpr_carries_the_previous_period_as_awaiting_release_not_source_failure(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
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
        # The catalog it was acquired for, as every writer names it (tickets 17 and 19).
        safe_metadata={"period": "2026-08", "definition_version": "metric-catalog-v0002"},
    )

    context = build_context_projection(
        repository,
        as_of=failed_at,
        model_manifest=_v2_manifest(),
    )
    lpr_rows = context.macro["credit"]["evidence"][:1]  # type: ignore[index]

    assert lpr_rows[0]["status"] == "source_failed"
    assert lpr_rows[0]["value"] is None
    # A failed fetch refused no claim: the gap list does not count it as one (ticket 09).
    assert "source_failure" not in lpr_rows[0]


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


@pytest.mark.parametrize(
    ("conflicting_value", "reason"),
    [(3.1, "value_disagreement"), (300.0, "unit_scale_mismatch")],
)
def test_conflicted_certified_sources_keep_every_claim_and_do_not_drive_state(
    tmp_path: Path,
    conflicting_value: float,
    reason: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingested = ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )
    conflicting = repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0002",
            period_kind="month",
            period_start="2026-08-01",
            period_end="2026-08-31",
            dimensions={"tenor": "1y"},
            value=conflicting_value,
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
    assert lpr_1y["conflict_reason"] == reason
    assert {claim["value"] for claim in lpr_1y["claims"]} == {3.0, conflicting_value}
    assert set(ingested.claim_ids) | {conflicting.claim_id} <= set(context.observation_version_ids)
    assert context.macro["credit_response"] == "insufficient_data"


def test_certified_sources_within_half_a_percent_agree(tmp_path: Path) -> None:
    """3.0 and 3.01 differ only in disclosed precision; neither is a conflict (ADR-0033)."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    ingest_lpr_document(
        paths,
        content,
        source_url=OFFICIAL_URL,
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
        clock=lambda: datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
    )
    repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0002",
            period_kind="month",
            period_start="2026-08-01",
            period_end="2026-08-31",
            dimensions={"tenor": "1y"},
            value=3.01,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="certified-secondary-fixture",
            source_reference="fixture:precise-lpr-1y",
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

    assert lpr_1y["status"] != "conflicted"
    assert "conflict_reason" not in lpr_1y
    assert {claim["value"] for claim in lpr_1y["claims"]} == {3.0, 3.01}


def test_credit_impulse_is_persisted_with_exact_point_in_time_input_vintages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    certified_ids = {"CN_SF_TOTAL", "CN_GDP", "CN_CREDIT_IMPULSE"}

    def certified_definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
    assert impulse["period_start"] == "2025-12-01"
    assert impulse["period"] == "2025-12-31"
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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
        assert set(trace.input_observation_version_ids) == set(row["input_observation_version_ids"])


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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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
        database_path: Path | None = None,
    ):
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
            database_path=database_path,
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


def _dr007_claim(provider: str, value: float, certification: str) -> SourceClaimInput:
    known = datetime(2026, 8, 27, 4, tzinfo=UTC)
    return SourceClaimInput(
        metric_id="CN_DR007",
        definition_version="metric-catalog-v0001",
        period_kind="business_day",
        period_start="2026-08-27",
        period_end="2026-08-27",
        dimensions={},
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="scalar",
        provider=provider,
        source_reference=f"{provider}:dr007:2026-08-27",
        release_event_id=f"{provider}:dr007:2026-08-27",
        release_at=known,
        public_available_at=known,
        fetched_at=known,
        available_at=known,
        certification_status=certification,
        quality_status="validated",
    )


@pytest.mark.parametrize(
    ("claims", "selected", "status"),
    [
        # A news value is compared with no registered source (ADR-0033): no conflict.
        (
            (("tushare", 1.50, "certified"), ("tushare_news", 1.60, "not_applicable")),
            1.50,
            "current",
        ),
        # A certified value wins over an uncertified one whatever the providers' names.
        (
            (("zz_registered", 1.50, "certified"), ("ai_websearch:x", 1.60, "not_applicable")),
            1.50,
            "current",
        ),
        # With no certified claim the provider order still picks one.
        (
            (("ai_websearch:x", 1.60, "not_applicable"), ("tushare_news", 1.50, "not_applicable")),
            1.60,
            "current",
        ),
        # A source awaiting certification (EIA, VIX, ECB...) still gives the value.
        ((("fixture:awaiting", 1.55, "awaiting_source_certification"),), 1.55, "current"),
        (
            (
                ("fixture:awaiting", 1.55, "awaiting_source_certification"),
                ("tushare_news", 1.70, "not_applicable"),
            ),
            1.55,
            "current",
        ),
        # Two registered sources apart by more than 0.5% still conflict on the target day.
        (
            (("tushare", 1.50, "certified"), ("official", 1.60, "certified")),
            1.60,
            "conflicted",
        ),
    ],
)
def test_the_target_day_selects_as_the_repository_does(
    tmp_path: Path,
    claims: tuple[tuple[str, float, str], ...],
    selected: float,
    status: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = EvidenceRepository(paths.database)
    repository.append_source_claims(
        tuple(_dr007_claim(provider, value, cert) for provider, value, cert in claims)
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        model_manifest=certified_model_v0001_manifest(),
        target_business_date="2026-08-28",
    )

    (row,) = [
        row
        for card in context.macro.values()
        if isinstance(card, dict)
        for row in card.get("evidence", ())
        if row["metric_id"] == "CN_DR007"
    ]
    assert (row["value"], row["status"]) == (selected, status)


def _rows_of(value: object, metric_id: str) -> list[dict[str, object]]:
    if isinstance(value, dict):
        own = (
            [value]
            if value.get("metric_id") == metric_id
            and "direction_input_observation_version_ids" in value
            else []
        )
        return own + [row for child in value.values() for row in _rows_of(child, metric_id)]
    if isinstance(value, list):
        return [row for child in value for row in _rows_of(child, metric_id)]
    return []


@pytest.mark.parametrize(
    ("earlier", "direction"),
    [
        ("2026-02", "up"),
        # Two months back is no previous period: an older value stands in for none.
        ("2026-01", "unknown"),
    ],
)
def test_the_window_s_first_month_compares_with_the_month_before_the_window(
    tmp_path: Path, earlier: str, direction: str
) -> None:
    # The window opens 2026-03-09; March is the first month shown, February only its
    # comparison, never a row of its own (ticket 30).
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    metric_id = "CN_PPI"
    dimensions = {"measure": "yoy", "category": "headline"}
    claims = {}
    for period, value in ((earlier, 1.0), ("2026-03", 2.0)):
        year, month = (int(part) for part in period.split("-"))
        claims[period] = repository.append_source_claim(
            _certified_claim(
                metric_id=metric_id,
                period_start=f"{period}-01",
                period_end=f"{period}-{calendar.monthrange(year, month)[1]:02d}",
                dimensions=dimensions,
                value=value,
                unit="percent",
            )
        ).claim_id

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 8, 31, tzinfo=UTC),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
        model_manifest=_v2_manifest(metric_id),
    )
    rows = _rows_of(context.macro, metric_id) + _rows_of(context.inventory, metric_id)

    assert rows
    assert {row["period"] for row in rows} == {"2026-03-31"}
    assert {row["direction"] for row in rows} == {direction}
    assert {tuple(row["direction_input_observation_version_ids"]) for row in rows} == {  # type: ignore[arg-type]
        (claims[earlier],) if direction != "unknown" else ()
    }


@pytest.mark.parametrize(
    ("case", "direction"),
    [
        # 2025-Q4 before the window compares with 2026-Q1, across the year.
        ("quarter_across_the_year", "up"),
        # Published after the target day: not known then, so not compared with.
        ("published_after_the_target", "unknown"),
        # Another member's period is no previous period of this one.
        ("another_member", "unknown"),
    ],
)
def test_the_period_before_the_window_is_compared_only_when_known_and_alike(
    tmp_path: Path, case: str, direction: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    metric_id = "CN_GDP" if case == "quarter_across_the_year" else "CN_PPI"
    dimensions = (
        {"aggregate": "total", "measure": "nominal_quarterly_level"}
        if metric_id == "CN_GDP"
        else {"measure": "yoy", "category": "headline"}
    )
    earlier_end, current_end = (
        ("2025-12-31", "2026-03-31") if metric_id == "CN_GDP" else ("2026-02-28", "2026-03-31")
    )
    earlier = _certified_claim(
        metric_id=metric_id,
        period_start=earlier_end[:8] + "01",
        period_end=earlier_end,
        dimensions=(
            {"measure": "mom", "category": "headline"} if case == "another_member" else dimensions
        ),
        value=1.0,
        unit="percent",
    )
    if case == "published_after_the_target":
        late = datetime(2026, 9, 15, tzinfo=UTC)
        earlier = replace(earlier, public_available_at=late, release_at=late)
    repository.append_source_claim(earlier)
    repository.append_source_claim(
        _certified_claim(
            metric_id=metric_id,
            period_start=current_end[:8] + "01",
            period_end=current_end,
            dimensions=dimensions,
            value=2.0,
            unit="percent",
        )
    )

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 9, 30, tzinfo=UTC),
        target_business_date="2026-08-28",
        visible_evidence_start="2026-03-09",
        model_manifest=_v2_manifest(metric_id),
    )
    rows = [
        row
        for row in _rows_of(context.macro, metric_id) + _rows_of(context.inventory, metric_id)
        if row["dimensions"] == dimensions
    ]

    assert rows and {row["period"] for row in rows} == {current_end}
    assert {row["direction"] for row in rows} == {direction}
