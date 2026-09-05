from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import pring_cycle.worker as worker_module
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import (
    build_context_projection as actual_build_context_projection,
)
from pring_cycle.domain import CoreAssetState
from pring_cycle.domain.trend import TrendRules
from pring_cycle.eia_context import EiaSpotPrice
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.maintenance import MaintenanceRepository
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
)
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.tushare_context import ContextScalar
from pring_cycle.worker import process_pending_run, submit_schedule_if_crossed


def runtime(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    return paths


@pytest.mark.parametrize(
    "public_available_at",
    (datetime(2026, 8, 31, tzinfo=UTC), None),
)
def test_target_completeness_requires_a_reliable_public_time_by_target(
    public_available_at: datetime | None,
) -> None:
    claim = SimpleNamespace(public_available_at=public_available_at)
    point = SimpleNamespace(
        period_start="2026-08-28",
        period_end="2026-08-28",
        selected_claim_id="claim-late",
        claims=(SimpleNamespace(claim_id="claim-late", **vars(claim)),),
    )

    assert not worker_module._point_known_by_target(point, "2026-08-28")


def test_runtime_p1_completeness_requires_all_current_valuation_members() -> None:
    target = date(2026, 8, 28)
    trading_days: list[str] = []
    current = target
    while len(trading_days) < 120:
        if current.weekday() < 5:
            trading_days.append(current.isoformat())
        current -= timedelta(days=1)
    trading_days.reverse()
    required = tuple(
        (index, measure)
        for index in ("000300.SH", "000905.SH")
        for measure in ("price_earnings", "price_book", "turnover_rate")
    )
    points = []
    for period in trading_days:
        for index, measure in required:
            claim_id = f"claim:{period}:{index}:{measure}"
            points.append(
                SimpleNamespace(
                    period_start=period,
                    period_end=period,
                    dimensions={"index": index, "measure": measure},
                    selection_status="selected",
                    selected_claim_id=claim_id,
                    selected_value=10.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    claims=(
                        SimpleNamespace(
                            claim_id=claim_id,
                            certification_status="certified",
                            quality_status="validated",
                        ),
                    ),
                )
            )
    definition = metric_definition(
        "CN_INDEX_VALUATION",
        definition_version="metric-catalog-v0003",
    )

    assert worker_module._direct_metric_is_ready(
        tuple(points),  # type: ignore[arg-type]
        definition,
        target_business_date=target.isoformat(),
        target_trading_days=tuple(trading_days),
    )
    incomplete = tuple(
        point
        for point in points
        if not (
            point.period_end == target.isoformat()
            and point.dimensions == {"index": "000905.SH", "measure": "turnover_rate"}
        )
    )

    assert not worker_module._direct_metric_is_ready(
        incomplete,  # type: ignore[arg-type]
        definition,
        target_business_date=target.isoformat(),
        target_trading_days=tuple(trading_days),
    )


def test_runtime_p1_completeness_cannot_bypass_awaiting_release_status() -> None:
    definition = metric_definition(
        "CN_LPR_1Y_5Y",
        definition_version="metric-catalog-v0003",
    )

    assert not worker_module._context_status_allows_direct_metric(
        definition,
        {"awaiting_release"},
    )
    assert worker_module._context_status_allows_direct_metric(
        definition,
        {"current"},
    )


def test_runtime_policy_rate_does_not_require_duplicate_daily_claims() -> None:
    target = date(2026, 8, 28)
    claim_id = "claim-policy-rate"
    point = SimpleNamespace(
        period_start=target.isoformat(),
        period_end=target.isoformat(),
        dimensions={},
        selection_status="selected",
        selected_claim_id=claim_id,
        selected_value=1.4,
        value_state=EvidenceValueState.REPORTED_VALUE,
        claims=(
            SimpleNamespace(
                claim_id=claim_id,
                certification_status="certified",
                quality_status="validated",
            ),
        ),
    )
    definition = metric_definition(
        "CN_OMO_7D_RATE",
        definition_version="metric-catalog-v0003",
    )

    assert worker_module._direct_metric_is_ready(
        (point,),  # type: ignore[arg-type]
        definition,
        target_business_date=target.isoformat(),
        target_trading_days=(),
    )


def test_core_readiness_ignores_observations_after_historical_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    target = date(2026, 8, 3)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=target.isoformat(),
        client_request_id="historical-target-cutoff",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 31, 3, tzinfo=UTC),
    )
    series = tuple(
        SimpleNamespace(
            period_end=(target - timedelta(days=159 - index)).isoformat(),
            selection_status="selected",
            value_state=EvidenceValueState.REPORTED_VALUE,
            selected_value=100.0 + index,
            selected_claim_id=f"claim-{index}",
            claims=(),
        )
        for index in range(160)
    ) + (
        SimpleNamespace(
            period_end="2026-08-28",
            selection_status="selected",
            value_state=EvidenceValueState.REPORTED_VALUE,
            selected_value=300.0,
            selected_claim_id="future-claim",
            claims=(),
        ),
    )
    monkeypatch.setattr(EvidenceRepository, "metric_series", lambda *_args, **_kwargs: series)
    monkeypatch.setattr(worker_module, "_selected_core_claim_is_valid", lambda *_args: True)

    readiness = worker_module._core_readiness(
        paths,
        run,
        rules=TrendRules(),
        definition_version="metric-catalog-v0001",
    )

    assert {item.reason for item in readiness} == {"validated"}
    assert {item.latest_business_date for item in readiness} == {target.isoformat()}
    assert {item.observation_count for item in readiness} == {120}
    assert {item.evidence_window_start for item in readiness} == {
        (target - timedelta(days=119)).isoformat()
    }
    assert all(
        item.observation_version_ids == tuple(f"claim-{index}" for index in range(40, 160))
        for item in readiness
    )


def test_context_refresh_ingests_eia_independently_of_tushare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    paths.secrets.write_text("EIA_API_KEY=fixture-eia-key\n", encoding="utf-8")
    paths.secrets.chmod(0o600)

    class FixtureEiaAdapter:
        def spot_prices(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[EiaSpotPrice, ...]:
            assert start_date == date(2026, 1, 20)
            assert end_date == date(2026, 8, 28)
            return (
                EiaSpotPrice(
                    metric_id="EIA_BRENT_RBRTE",
                    series_id="RBRTE",
                    series_description="Europe Brent Spot Price FOB",
                    business_date=date(2026, 8, 27),
                    value=71.25,
                    unit="usd_per_barrel",
                ),
                EiaSpotPrice(
                    metric_id="EIA_WTI_RWTC",
                    series_id="RWTC",
                    series_description="Cushing, OK WTI Spot Price FOB",
                    business_date=date(2026, 8, 27),
                    value=66.5,
                    unit="usd_per_barrel",
                ),
            )

    monkeypatch.setattr(
        worker_module,
        "_eia_context_adapter",
        lambda api_key: FixtureEiaAdapter() if api_key == "fixture-eia-key" else None,
    )

    worker_module._refresh_context_sources(
        paths,
        "2026-08-28",
        definition_version="metric-catalog-v0002",
    )

    repository = EvidenceRepository(paths.database)
    cutoff = datetime.now(UTC)
    brent = repository.metric_series(
        "EIA_BRENT_RBRTE",
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
    )
    wti = repository.metric_series(
        "EIA_WTI_RWTC",
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
    )
    assert brent[-1].selected_value == 71.25
    assert wti[-1].selected_value == 66.5
    assert brent[-1].claims[0].certification_status == "awaiting_source_certification"


@pytest.mark.parametrize(
    ("failure", "expected_outcome"),
    (
        (OSError("fixture network failure"), "source_failed"),
        (TypeError("fixture adapter failure"), "adapter_failed"),
        (ValueError("fixture validation failure"), "validation_failed"),
    ),
)
def test_worker_classifies_optional_eia_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_outcome: str,
) -> None:
    paths = runtime(tmp_path)
    paths.secrets.write_text("EIA_API_KEY=fixture-eia-key\n", encoding="utf-8")
    paths.secrets.chmod(0o600)

    class FailingEiaAdapter:
        def spot_prices(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[EiaSpotPrice, ...]:
            raise failure

    monkeypatch.setattr(
        worker_module,
        "_eia_context_adapter",
        lambda _api_key: FailingEiaAdapter(),
    )

    worker_module._refresh_context_sources(
        paths,
        "2026-08-28",
        definition_version="metric-catalog-v0002",
    )

    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "EIA_BRENT_RBRTE",
        period="2026-08-28",
        as_of=datetime.now(UTC),
    )
    assert attempt is not None
    assert attempt.outcome == expected_outcome


def test_worker_fails_closed_when_a_manual_run_has_no_certified_p0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    captured_manifest: dict[str, object] = {}

    def model_bound_context(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        manifest = kwargs.get("model_manifest")
        assert isinstance(manifest, dict)
        captured_manifest.update(manifest)
        return actual_build_context_projection(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("pring_cycle.worker.build_context_projection", model_bound_context)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-p0-missing",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    processed = process_pending_run(paths, report_adapters=())

    assert processed == submitted.run_id
    assert runs.get(submitted.run_id).status == "action_required"
    assert runs.get(submitted.run_id).error_classification == "p0_unavailable"
    assert runs.next_queued() is None
    assert captured_manifest["model_version_id"] == "model-v0001"
    assert captured_manifest["metric_catalog_version"] == "metric-catalog-v0001"
    formulas = captured_manifest["derived_formula_versions"]
    assert isinstance(formulas, dict)
    assert "omo_net_injection" not in formulas


def test_worker_completes_a_valid_noncanonical_projection_and_report(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    evidence = EvidenceRepository(paths.database)
    days = []
    day = date(2026, 8, 28)
    while len(days) < 180:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    for index, observed in enumerate(reversed(days)):
        cutoff = datetime.combine(observed, datetime.min.time(), tzinfo=UTC)
        for metric_id, value in (
            ("CN_BOND_CORE_000012", 100.0 + index),
            ("CN_EQUITY_CORE_000985", 1000.0 - index),
            ("CN_COMMODITY_CORE_NHII", 100.0 + index),
        ):
            api_name, source_code = CORE_API_IDENTITIES[metric_id]
            evidence.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=observed.isoformat(),
                    period_end=observed.isoformat(),
                    dimensions={},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="tushare",
                    source_reference=f"tushare:{api_name}:{source_code}:{observed}",
                    release_event_id=f"fixture:{metric_id}:{observed}",
                    release_at=cutoff,
                    public_available_at=cutoff,
                    fetched_at=cutoff,
                    available_at=cutoff,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-p0-noncanonical",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    processed = process_pending_run(paths, report_adapters=())

    assert processed == submitted.run_id
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    assert stored.error_classification is None
    current = ProjectionSetRepository(paths.database).current()
    assert current.envelope.target_business_date == "2026-08-28"
    assert current.datasets["cycle_overview"]["current_stage"] is None
    assert current.datasets["cycle_overview"]["stage_reason"] == "noncanonical_combination"
    report = ReportRepository(paths.database).history()[0]
    assert report.projection_set_id == current.envelope.projection_set_id
    assert report.current_stage is None
    assert report.status == "completed_degraded"
    assert runs.next_queued() is None


def test_worker_fails_closed_and_classifies_context_validation_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-token\n", encoding="utf-8")
    paths.secrets.chmod(0o600)

    class FixtureContextAdapter:
        def market_indices(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_market_indices_source_failed")

        def market_breadth(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_market_breadth_source_failed")

        def margin_financing(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_margin_source_failed")

        def index_valuation(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_valuation_source_failed")

        def commodity_basket(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_commodity_basket_source_failed")

        def pmi(
            self,
            *,
            start_month: str,
            end_month: str,
        ) -> tuple[ContextScalar, ...]:
            assert start_month < end_month == "202608"
            return (
                ContextScalar(
                    metric_id="CN_PMI_ACTIVITY",
                    api_name="cn_pmi",
                    source_field="pmi010000",
                    period_kind="month",
                    period_start="2026-08-01",
                    period_end="2026-08-31",
                    dimensions={"series": "manufacturing", "measure": "level"},
                    value=49.3,
                    unit="diffusion_index_points",
                ),
            )

        def prices(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_price_source_failed")

        def money(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_money_source_failed")

        def social_financing(
            self,
            *,
            start_month: str,
            end_month: str,
        ) -> tuple[ContextScalar, ...]:
            assert start_month < end_month == "202608"
            return (
                ContextScalar(
                    metric_id="CN_SF_TOTAL",
                    api_name="sf_month",
                    source_field="inc_month",
                    period_kind="month",
                    period_start="2026-08-01",
                    period_end="2026-08-31",
                    dimensions={"measure": "monthly_increment"},
                    value=5000.0,
                    unit="hundred_million_cny",
                ),
            )

        def futures_warrants(
            self,
            *,
            start_date: date,
            end_date: date,
            symbol: str,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError(f"fixture_warrant_source_failed:{symbol}")

        def gdp(
            self,
            *,
            start_quarter: str,
            end_quarter: str,
        ) -> tuple[ContextScalar, ...]:
            assert start_quarter < end_quarter == "2026Q3"
            return (
                ContextScalar(
                    metric_id="CN_GDP",
                    api_name="cn_gdp",
                    source_field="gdp",
                    period_kind="year_to_quarter",
                    period_start="2026-01-01",
                    period_end="2026-09-30",
                    dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
                    value=1000000.0,
                    unit="hundred_million_cny",
                ),
            )

        def treasury_yields(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_treasury_source_failed")

        def transmission(
            self,
            *,
            start_date: date,
            end_date: date,
        ) -> tuple[ContextScalar, ...]:
            raise ValueError("fixture_transmission_source_failed")

    readiness = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    monkeypatch.setattr(
        worker_module,
        "_refresh_core_sources",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(worker_module, "_core_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(
        worker_module,
        "_context_adapter",
        lambda _token: FixtureContextAdapter(),
    )
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-candidate-context",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    evidence = EvidenceRepository(paths.database)
    assert stored.status == "action_required"
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()
    attempt = evidence.latest_retrieval_attempt(
        "CN_EQ_CSI300",
        period="2026-08-28",
        as_of=datetime.now(UTC),
    )
    assert attempt is not None
    assert attempt.outcome == "validation_failed"


def test_worker_rejects_a_formal_run_for_a_candidate_model(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-candidate-model",
        model_version_id="model-v0002",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.error_classification == "model_version_not_active"
    with pytest.raises(LookupError, match="current_projection_unavailable"):
        ProjectionSetRepository(paths.database).current()


def test_worker_does_not_mutate_a_runtime_that_requires_reinitialization(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-integrity-gate",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    MaintenanceRepository(paths.database).record_upgrade_failure("fixture_failure")

    assert process_pending_run(paths, report_adapters=()) is None
    assert runs.get(submitted.run_id).status == "queued"


def test_report_command_reads_the_published_projection_and_never_rewrites_it(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    projections = ProjectionSetRepository(paths.database)
    readiness = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    published = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=readiness,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="report_generation",
        target_business_date="2026-08-28",
        client_request_id="worker-report-1",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, 5, tzinfo=UTC),
    )

    process_pending_run(paths, report_adapters=())

    assert runs.get(submitted.run_id).status == "completed"
    assert projections.current().envelope.projection_set_id == published.projection_set_id
    reports = ReportRepository(paths.database).history()
    assert len(reports) == 1
    assert reports[0].status == "completed_degraded"


def test_resumed_run_reuses_its_published_projection_without_external_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    projections = ProjectionSetRepository(paths.database)
    readiness = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    published = P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=readiness,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )
    assert published.projection_set_id is not None
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="worker-resume-projection",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    runs.link_projection(submitted.run_id, published.projection_set_id)
    runs.mark_interrupted(submitted.run_id, "fixture_after_projection_publish")
    runs.resume(
        submitted.run_id,
        client_request_id="worker-resume-projection-confirmed",
        confirm_external_calls=True,
    )

    def unexpected_refresh(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("published_projection_must_skip_external_refresh")

    monkeypatch.setattr(worker_module, "_refresh_core_sources", unexpected_refresh)
    monkeypatch.setattr(worker_module, "_refresh_context_sources", unexpected_refresh)

    process_pending_run(paths, report_adapters=())

    stored = runs.get(submitted.run_id)
    reports = ReportRepository(paths.database).history()
    assert stored.status == "completed"
    assert stored.projection_set_id == published.projection_set_id
    assert reports[0].projection_set_id == published.projection_set_id


def test_report_run_reads_its_bound_projection_when_current_pointer_advances(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    projections = ProjectionSetRepository(paths.database)

    def publish(target: str, commodity: CoreAssetState) -> str:
        readiness = tuple(
            CoreAssetReadiness(
                asset=asset,
                metric_id=metric_id,
                state=state,
                reason="validated",
                observation_count=120,
                latest_business_date=target,
            )
            for asset, metric_id, state in (
                ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
                ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
                ("commodity", "CN_COMMODITY_CORE_NHII", commodity),
            )
        )
        result = P0ProjectionService(projections).publish(
            target_business_date=target,
            system_as_of=datetime.fromisoformat(f"{target}T13:00:00+00:00"),
            assets=readiness,  # type: ignore[arg-type]
            last_confirmed_stage=None,
        )
        assert result.projection_set_id is not None
        return result.projection_set_id

    bound_projection_id = publish("2026-08-27", CoreAssetState.BEAR)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="report_generation",
        target_business_date="2026-08-27",
        client_request_id="bound-report-projection",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 27, 13, 5, tzinfo=UTC),
    )
    runs.link_projection(submitted.run_id, bound_projection_id)
    current_projection_id = publish("2026-08-28", CoreAssetState.BULL)

    process_pending_run(paths, report_adapters=())

    report = ReportRepository(paths.database).history()[0]
    assert report.projection_set_id == bound_projection_id
    assert report.projection_set_id != current_projection_id
    assert report.target_business_date == "2026-08-27"


def test_scheduled_run_past_the_p0_deadline_makes_no_external_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit_scheduled_full(
        target_business_date="2026-08-28",
        client_request_id="scheduled-deadline-fixture",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 10, 30, tzinfo=UTC),
    )

    def unexpected_refresh(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("expired_schedule_must_not_refresh")

    monkeypatch.setattr(worker_module, "_refresh_core_sources", unexpected_refresh)

    process_pending_run(
        paths,
        report_adapters=(),
        execution_now=datetime(2026, 8, 28, 13, 1, tzinfo=UTC),
    )

    stored = runs.get(submitted.run_id)
    assert stored.status == "action_required"
    assert stored.error_classification == "scheduled_p0_deadline_elapsed"


def test_enabled_schedule_only_runs_when_a_live_worker_crosses_1830_shanghai(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    runs.configure_schedule(enabled=True, requested_by="test")

    missed_on_startup = submit_schedule_if_crossed(
        paths,
        datetime(2026, 8, 28, 11, tzinfo=UTC),
        datetime(2026, 8, 28, 12, tzinfo=UTC),
    )
    crossed = submit_schedule_if_crossed(
        paths,
        datetime(2026, 8, 28, 10, 29, 59, tzinfo=UTC),
        datetime(2026, 8, 28, 10, 30, 1, tzinfo=UTC),
    )

    assert missed_on_startup is None
    assert crossed is not None
    assert runs.get(crossed).target_business_date == "2026-08-28"


def test_targeted_refresh_runs_serial_retrieval_and_persists_auditable_attempts(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="targeted-lpr-1",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    calls: list[str] = []

    def adapter(channel: str) -> object:
        def retrieve(_event: str) -> str | None:
            calls.append(channel)
            return "claim:lpr:2026-08" if channel == "official" else None

        return retrieve

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters={
            channel: adapter(channel)  # type: ignore[dict-item]
            for channel in ("local", "tushare", "official")
        },
        retrieval_now=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )

    stored = runs.get(submitted.run_id)
    assert stored.status == "completed"
    assert calls == ["local", "tushare", "official"]
    assert [item["channel"] for item in stored.retrieval_attempts] == [
        "local",
        "tushare",
        "official",
    ]
    assert stored.retrieval_attempts[-1]["outcome"] == "verified"
    assert runs.reusable_checkpoints(submitted.run_id) == (
        {"kind": "verified_evidence", "reference": "claim:lpr:2026-08"},
    )


def test_targeted_official_context_refresh_keeps_uncertified_result_as_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    source_url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html"
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-07-09",
        client_request_id="targeted-core-cpi-candidate",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 7, 9, 2, tzinfo=UTC),
        release_event_id="nbs-core-cpi:2026-06",
        metric_ids=("CN_CORE_CPI",),
        period="2026-06",
        source_url=source_url,
    )
    calls: list[str] = []

    def refresh(*_args: object, **kwargs: object) -> object:
        calls.append(str(kwargs["family"]))
        return SimpleNamespace(
            claim_ids=("candidate-claim",),
            metric_ids=("CN_CORE_CPI",),
        )

    monkeypatch.setattr(
        "pring_cycle.official_context.refresh_official_context_document",
        refresh,
    )

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_now=datetime(2026, 7, 9, 2, tzinfo=UTC),
    )

    stored = runs.get(submitted.run_id)
    assert calls == ["nbs_core_cpi"]
    assert stored.status == "action_required"
    official = next(item for item in stored.retrieval_attempts if item["channel"] == "official")
    assert official["outcome"] == "candidate_source"
    assert official["candidate_source"] == source_url
    assert runs.reusable_checkpoints(submitted.run_id) == ()


def test_unreleased_targeted_refresh_and_active_negative_cache_make_no_calls(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    calls: list[str] = []
    adapters = {"official": lambda _event: calls.append("official")}
    future = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-09-01",
        client_request_id="future-lpr",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-09",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-09",
    )

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters=adapters,  # type: ignore[arg-type]
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert calls == []
    assert runs.get(future.run_id).next_action == "wait_for_release_or_cache_expiry"

    runs.store_negative_cache(
        "chinamoney-lpr:2026-08-20",
        ("CN_LPR_1Y_5Y",),
        reason="not_found",
        expires_at=datetime(2026, 8, 31, tzinfo=UTC),
        now=datetime(2026, 8, 30, tzinfo=UTC),
    )
    cached = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="cached-lpr",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters=adapters,  # type: ignore[arg-type]
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert calls == []
    assert runs.get(cached.run_id).retrieval_attempts[0]["cache_hit"] is True


def test_p2_stops_before_ai_and_manual_deep_search_records_budget_exemption(
    tmp_path: Path,
) -> None:
    paths = runtime(tmp_path)
    runs = RunRepository(paths.database)
    calls: list[str] = []

    with pytest.raises(ValueError, match="manual_deep_search_requires_one_explicit_metric"):
        runs.submit(
            command_type="manual_deep_search",
            target_business_date="2026-08-20",
            client_request_id="deep-invalid",
            model_version_id="model-v0001",
            system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
            release_event_id="release-p2",
            metric_ids=("CBOE_VIX_INDEX", "NASDAQ_SOX_INDEX"),
            period="2026-08",
        )

    deep = runs.submit(
        command_type="manual_deep_search",
        target_business_date="2026-08-20",
        client_request_id="deep-p2",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 30, tzinfo=UTC),
        release_event_id="release-p2",
        metric_ids=("CBOE_VIX_INDEX",),
        period="2026-08",
    )

    def miss(channel: str) -> object:
        def retrieve(_event: str) -> RetrievalAdapterResponse:
            calls.append(channel)
            return RetrievalAdapterResponse("not_found")

        return retrieve

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters={
            channel: miss(channel)  # type: ignore[dict-item]
            for channel in ("local", "tushare", "official", "tavily", "exa", "ai_websearch")
        },
        retrieval_now=datetime(2026, 8, 30, tzinfo=UTC),
        retrieval_release_resolver=lambda _scope, _now: True,
    )

    stored = runs.get(deep.run_id)
    assert calls == ["local", "tushare", "official", "tavily", "exa"]
    assert stored.consumed_budget == {"tavily": 0, "exa": 0, "ai_websearch": 0}
    assert all(item["manual_budget_exemption"] is True for item in stored.retrieval_attempts)
