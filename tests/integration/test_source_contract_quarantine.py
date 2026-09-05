from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.domain import CoreAssetState
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    analytical_model_v0003_manifest,
)
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository, ReportService, evidence_bundle_from_projection
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, diagnose_runtime, initialize_runtime
from pring_cycle.source_certification import refresh_source_certified_candidate
from pring_cycle.web import create_web_application
from pring_cycle.worker import process_pending_run


def _candidate_runtime(tmp_path: Path) -> tuple[RuntimePaths, str]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    manifest = analytical_model_v0003_manifest()
    manifest["model_version_id"] = "historical-v3-candidate"
    manifest["metric_catalog_version"] = "metric-catalog-v0003"
    manifest["metric_definitions"] = [asdict(item) for item in metric_catalog_v0003()]
    candidate = models.create_candidate(manifest)
    return paths, candidate.model_version_id


def test_audited_candidate_cannot_activate_or_refresh_even_after_replay(tmp_path: Path) -> None:
    paths, candidate_id = _candidate_runtime(tmp_path)
    models = ModelRepository(paths.database)
    original = models.manifest(candidate_id)
    models.record_acceptance(candidate_id, CALIBRATION_BASELINE)
    models.record_replay(
        candidate_id,
        compared_with="model-v0001",
        requested_start="2018-06-01",
        requested_end="2026-08-28",
        quality_passed=True,
        regression_passed=True,
        performance_passed=True,
        stage_differences=0,
        core_state_differences=0,
        gaps=(),
    )
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        models.activate(candidate_id, explicitly_approved=True)
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        refresh_source_certified_candidate(
            paths, model_version_id=candidate_id, target_business_date="2026-08-28"
        )
    assert models.active().model_version_id == "model-v0001"
    assert models.get(candidate_id).status == "candidate"
    assert models.manifest(candidate_id) == original


def test_audited_market_claim_cannot_be_newly_ingested_as_certified(tmp_path: Path) -> None:
    paths, _ = _candidate_runtime(tmp_path)
    evidence = EvidenceRepository(paths.database)
    observed_at = datetime(2026, 8, 29, tzinfo=UTC)
    claim = SourceClaimInput(
        metric_id="CN_MARGIN_BALANCE",
        definition_version="metric-catalog-v0003",
        period_kind="business_day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={"measure": "financing_balance", "scope": "all_exchanges"},
        value=100.0,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="hundred_million_cny",
        provider="tushare",
        source_reference="tushare:margin:20260828",
        release_event_id="margin-sample",
        release_at=observed_at,
        public_available_at=observed_at,
        fetched_at=observed_at,
        available_at=observed_at,
        certification_status="certified",
        quality_status="validated",
    )
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        evidence.append_source_claim(claim)
    # An explicitly unapproved research sample can still be stored and traced.
    stored = evidence.append_source_claim(
        replace(claim, certification_status="awaiting_source_certification")
    )
    assert evidence.claim_count(stored.observation_id) == 1


def test_pre_audit_projection_stays_readable_but_cannot_be_republished(tmp_path: Path) -> None:
    paths, candidate_id = _candidate_runtime(tmp_path)
    projections = ProjectionSetRepository(paths.database)
    now = datetime(2026, 8, 28, 13, tzinfo=UTC)
    assets = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric,
            state=state,
            reason="validated",
            observation_count=120,
            latest_business_date="2026-08-28",
        )
        for asset, metric, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    P0ProjectionService(projections).publish(
        target_business_date="2026-08-28",
        system_as_of=now,
        assets=assets,
        last_confirmed_stage=None,
    )
    old = projections.current()
    # Seed a database as it existed before the audit. Production cannot create
    # this v3 publication through today's guarded public methods.
    with sqlite3.connect(paths.database) as connection:
        document = json.loads(
            connection.execute(
                "SELECT envelope_json FROM projection_set WHERE projection_set_id=?",
                (old.envelope.projection_set_id,),
            ).fetchone()[0]
        )
        document["model_version_id"] = candidate_id
        document["projection_set_id"] = "historical-v3-projection"
        connection.execute(
            "INSERT INTO projection_set(projection_set_id, envelope_json) VALUES (?, ?)",
            (document["projection_set_id"], json.dumps(document)),
        )
        for name, dataset in old.datasets.items():
            connection.execute(
                "INSERT INTO analytical_dataset(projection_set_id, dataset_name, document_json) "
                "VALUES (?, ?, ?)",
                (
                    document["projection_set_id"],
                    name,
                    json.dumps({**dataset, "projection_set_id": document["projection_set_id"]}),
                ),
            )
        connection.execute(
            "UPDATE current_projection SET projection_set_id=?", (document["projection_set_id"],)
        )
        connection.execute("UPDATE active_model SET model_version_id=?", (candidate_id,))
        connection.execute(
            "UPDATE model_version SET status='active' WHERE model_version_id=?", (candidate_id,)
        )
    historical = projections.current()
    assert historical.envelope.model_version_id == candidate_id
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        P0ProjectionService(projections).publish(
            target_business_date="2026-08-28",
            system_as_of=now,
            assets=assets,
            last_confirmed_stage=None,
            model_version_id=candidate_id,
        )
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        ReportService(ReportRepository(paths.database), ()).generate(
            evidence_bundle_from_projection(historical),
            client_request_id="blocked-new-report",
        )
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="audited-contract",
        model_version_id=candidate_id,
        system_as_of=now,
    )
    assert process_pending_run(paths, report_adapters=()) == run.run_id
    assert runs.get(run.run_id).status == "action_required"
    assert "source_certification_contract_unresolved" in str(
        runs.get(run.run_id).error_classification
    )
    assert projections.current() == historical
    assert ReportRepository(paths.database).history() == ()
    diagnosis = diagnose_runtime(paths)
    assert diagnosis["offline_start_available"] is True
    assert diagnosis["status"] == "action_required"
    assert diagnosis["source_contract_review"]["status"] == "blocked"

    prior_runs = runs.list_runs()
    for command in ("manual_full", "report_generation", "resume"):
        response = _command_response(
            paths,
            {
                "command": command,
                "client_request_id": f"blocked-web-{command}",
                "target_business_date": "2026-08-28",
                "run_id": run.run_id,
                "confirm_external_calls": True,
            },
        )
        assert response.status_code == 409
        assert "source_certification_contract_unresolved" in json.loads(response.body)["error"]
    assert runs.list_runs() == prior_runs
    assert projections.current() == historical
    assert ReportRepository(paths.database).history() == ()
    # Cancellation is still available while the source contract is blocked.
    response = _command_response(
        paths,
        {"command": "cancel", "client_request_id": "cancel-web", "run_id": run.run_id},
    )
    assert response.status_code == 202
    assert runs.get(run.run_id).status == "cancelled"


def test_web_command_checks_explicit_model_without_blocking_unaffected_active_model(
    tmp_path: Path,
) -> None:
    paths, candidate_id = _candidate_runtime(tmp_path)
    payload = {
        "command": "manual_full",
        "target_business_date": "2026-08-28",
        "client_request_id": "explicit-audited-model",
        "model_version_id": candidate_id,
    }
    response = _command_response(paths, payload)
    assert response.status_code == 409
    assert "source_certification_contract_unresolved" in json.loads(response.body)["error"]
    assert RunRepository(paths.database).list_runs() == ()
    del payload["model_version_id"]
    payload["client_request_id"] = "unaffected-active-model"
    response = _command_response(paths, payload)
    assert response.status_code == 202
    assert RunRepository(paths.database).get(
        json.loads(response.body)["run_id"]
    ).model_version_id == ("model-v0001")


def _command_response(paths: RuntimePaths, payload: dict[str, object]) -> JSONResponse:
    application = create_web_application(paths, 8877, eager_dashboard=False)
    endpoint = next(
        route.endpoint
        for route in application.routes
        if getattr(route, "name", None) == "append_command"
    )

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/commands",
            "headers": [(b"host", b"127.0.0.1:8877"), (b"origin", b"http://127.0.0.1:8877")],
        },
        receive=receive,
    )
    return asyncio.run(endpoint(request))
