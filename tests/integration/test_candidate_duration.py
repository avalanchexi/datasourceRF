from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from dash.development.base_component import Component
from fastapi.routing import APIRoute

from pring_cycle.cli import main
from pring_cycle.core_fixture import CORE_FIXTURE_METRICS, project_core_fixture
from pring_cycle.dashboard import dashboard_page
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.web import create_web_application
from pring_cycle.worker import process_pending_run
from tests.integration.test_worker_execution import seed_independent_calendar


def rendered_text(component: object) -> str:
    if isinstance(component, str):
        return component
    if isinstance(component, (tuple, list)):
        return " ".join(rendered_text(child) for child in component)
    if isinstance(component, Component):
        return rendered_text(getattr(component, "children", None))
    return ""


def test_new_model_reports_actual_candidate_days_and_preserves_old_snapshots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable_optional_source(*_args: object, **_kwargs: object) -> None:
        raise OSError("fixture optional source unavailable")

    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", unavailable_optional_source)
    monkeypatch.setattr("pring_cycle.official_context.urlopen", unavailable_optional_source)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    calendar = []
    day = date(2026, 8, 3)
    while len(calendar) < 180:
        if day.weekday() < 5:
            calendar.append(day)
        day -= timedelta(days=1)
    calendar.reverse()
    seed_independent_calendar(paths, calendar)
    claims = []
    for index, observed in enumerate(calendar):
        cutoff = datetime.combine(observed, datetime.min.time(), tzinfo=UTC)
        for metric_id, (api_name, source_code) in CORE_API_IDENTITIES.items():
            # For MA2/slope1/no noise, the final seven stock prices 100..94
            # are seven bear signals after a long, independently obvious bull run.
            value = float(100 + index)
            if metric_id == "CN_EQUITY_CORE_000985" and index >= 173:
                value = float(100 - (index - 173))
            claims.append(
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
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))
    runs = RunRepository(paths.database)
    projections = ProjectionSetRepository(paths.database)
    reports = ReportRepository(paths.database)

    old_run = runs.submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id="legacy-duration",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 3, 13, tzinfo=UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(old_run.run_id).status == "completed"
    old_projection = projections.current()
    old_report = reports.history()[0]
    old_projection_bytes = json.dumps(old_projection.datasets, sort_keys=True)
    old_report_bytes = json.dumps(old_report.body, sort_keys=True)
    assert {a["candidate_days"] for a in old_projection.datasets["core_assets"]["assets"]} == {8}

    manifest = models.manifest("model-v0001")
    manifest["model_version_id"] = "model-duration-fixture-v2"
    manifest["trend_rules"].update(
        window_days=2,
        slope_days=1,
        volatility_days=1,
        noise_multiplier=0,
        candidate_duration_rule_version="candidate-duration-v0002",
    )
    candidate = models.create_candidate(manifest)
    # This isolated test model uses the existing fixture acceptance interface;
    # none of these records or synthetic source values enter the live runtime.
    models.record_acceptance(candidate.model_version_id, CALIBRATION_BASELINE)
    models.record_replay(
        candidate.model_version_id,
        compared_with="model-v0001",
        requested_start="2026-03-09",
        requested_end="2026-08-03",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
    )
    models.activate(candidate.model_version_id, explicitly_approved=True)
    new_run = runs.submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id="actual-duration",
        model_version_id=candidate.model_version_id,
        system_as_of=datetime(2026, 8, 3, 13, tzinfo=UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(new_run.run_id).status == "completed"
    current = projections.current()
    assets = {item["asset"]: item for item in current.datasets["core_assets"]["assets"]}
    assert assets["stock"]["candidate_days"] == 7
    assert assets["stock"]["candidate_state"] == "bear"
    assert assets["stock"]["state"] == "bull"
    assert assets["bond"]["candidate_days"] == assets["commodity"]["candidate_days"] == 0
    assert current.datasets["cycle_overview"]["current_stage"] == "stage_iii"

    main(["projection", "--runtime-root", str(paths.override_root), "--json"])
    cli = json.loads(capsys.readouterr().out)
    assert cli["datasets"]["core_assets"] == current.datasets["core_assets"]
    application = create_web_application(paths, 8877, eager_dashboard=False)
    route = next(
        route
        for route in application.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/projections/current"
    )
    response = route.endpoint()
    assert response.status_code == 200
    assert json.loads(response.body)["datasets"]["core_assets"] == current.datasets["core_assets"]
    assert "持续 7 日" in rendered_text(dashboard_page("/core-assets", current, (), ()))
    report = reports.history()[0]
    events = report.body["change_reasons"]["candidate_events"]
    assert next(item for item in events if item["asset"] == "stock")["candidate_days"] == 7
    assert (
        json.dumps(
            projections.get(old_projection.envelope.projection_set_id).datasets, sort_keys=True
        )
        == old_projection_bytes
    )
    assert (
        json.dumps(reports.get(old_report.report_snapshot_id).body, sort_keys=True)
        == old_report_bytes
    )


def test_acceptance_fixture_uses_the_candidate_models_duration_rule(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    manifest = models.manifest("model-v0001")
    manifest["model_version_id"] = "fixture-duration-v2"
    manifest["trend_rules"].update(
        window_days=2,
        slope_days=1,
        volatility_days=1,
        noise_multiplier=0,
        candidate_duration_rule_version="candidate-duration-v0002",
    )
    models.create_candidate(manifest)
    calendar = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(120)]
    result = project_core_fixture(
        paths,
        {
            "schema_version": "core-price-fixture-v0001",
            "target_business_date": calendar[-1],
            "system_as_of": f"{calendar[-1]}T13:00:00+00:00",
            "model_version_id": "fixture-duration-v2",
            "trading_calendar": calendar,
            "assets": {
                asset: {
                    "metric_id": metric,
                    "prices": [
                        {
                            "business_date": day,
                            "value": (
                                100 - (i - 113) if asset == "stock" and i >= 113 else 100 + i
                            ),
                        }
                        for i, day in enumerate(calendar)
                    ],
                }
                for asset, metric in CORE_FIXTURE_METRICS.items()
            },
        },
    )
    projection = ProjectionSetRepository(paths.database).current()
    assets = {item["asset"]: item for item in projection.datasets["core_assets"]["assets"]}

    assert result.acceptance_only is True
    assert result.current_stage == "stage_iii"
    assert assets["stock"]["candidate_days"] == 7
    assert assets["bond"]["candidate_days"] == assets["commodity"]["candidate_days"] == 0
