from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI

from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ANALYTICAL_DATASETS, ProjectionEnvelope, ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.web import _initial_dashboard_html, _persist_command, create_web_application

LPR_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
LPR_ANNOUNCEMENT = (
    Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
).read_bytes()


def _route(application: FastAPI, name: str) -> Any:
    return next(route for route in application.routes if getattr(route, "name", None) == name)


def test_current_projection_rest_preserves_the_atomic_envelope(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = ProjectionSetRepository(paths.database)
    envelope = ProjectionEnvelope(
        projection_set_id="projection-api-test",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        target_business_date="2026-08-28",
        evidence_snapshot_id="evidence-api-test",
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        evidence_window_start="2026-03-09",
        evidence_window_end="2026-08-28",
        generated_at=datetime(2026, 8, 28, 13, 1, tzinfo=UTC),
        completeness="complete",
        refresh_status="changed",
        warnings=(),
    )
    datasets = {
        name: {"projection_set_id": envelope.projection_set_id, "name": name}
        for name in ANALYTICAL_DATASETS
    }
    repository.publish(envelope, datasets)
    application = create_web_application(paths, 8050)

    current_response = _route(application, "current_projection").endpoint()
    dataset_response = _route(application, "current_projection_dataset").endpoint("macro")
    current = json.loads(cast(bytes, current_response.body))
    dataset = json.loads(cast(bytes, dataset_response.body))

    assert current_response.status_code == 200
    assert dataset_response.status_code == 200
    assert current["envelope"] == dataset["envelope"]
    assert dataset["dataset_name"] == "macro"
    assert dataset["data"] == datasets["macro"]


def test_runtime_init_bootstraps_the_candidate_model_without_activating_it(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")

    initialized = initialize_runtime(paths)
    application = create_web_application(paths, 8050)
    response = _route(application, "model_index").endpoint()

    assert initialized["network_requests"] == 0
    assert [item["model_version_id"] for item in response] == [
        "model-v0001",
        "model-v0002",
    ]
    assert {item["status"] for item in response} == {"candidate"}
    assert {item["certified_replay_start"] for item in response} == {"2018-06-01"}


def test_release_calendar_api_reads_only_the_active_models_definition_version(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    for definition_version in ("metric-catalog-v0001", "metric-catalog-v0002"):
        ingest_lpr_document(
            paths,
            LPR_ANNOUNCEMENT,
            source_url=LPR_URL,
            fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
            expected_period="2026-08",
            definition_version=definition_version,
        )
    application = create_web_application(paths, 8050)

    response = _route(application, "release_calendar").endpoint(
        "2026-08",
        datetime(2026, 8, 20, 2, tzinfo=UTC),
    )

    assert len(response["events"]) == 1
    assert response["events"][0]["observation_count"] == 2


def test_deferred_dashboard_shell_is_meaningful_before_interactive_assets_load(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    document = _initial_dashboard_html(paths, failed=False)

    assert "data-pring-meaningful-content='true'" in document
    assert "周期驾驶舱" in document
    assert "投影身份" in document
    assert "等待首次完整运行" in document
    assert "核心资产" in document
    assert "运行状态" in document


def test_stage_history_rest_includes_a_p0_gap_without_replacing_current_projection(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = ProjectionSetRepository(paths.database)

    def asset(name: str, state: CoreAssetState | None, reason: str) -> CoreAssetReadiness:
        return CoreAssetReadiness(
            asset=name,
            metric_id={
                "bond": "CN_BOND_CORE_000012",
                "stock": "CN_EQUITY_CORE_000985",
                "commodity": "CN_COMMODITY_CORE_NHII",
            }[name],
            state=state,
            reason=reason,
            observation_count=160 if state is not None else 0,
            latest_business_date="2026-08-28" if state is not None else None,
        )

    P0ProjectionService(repository).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=(
            asset("bond", CoreAssetState.BULL, "validated"),
            asset("stock", CoreAssetState.BULL, "validated"),
            asset("commodity", CoreAssetState.BEAR, "validated"),
        ),
        last_confirmed_stage=None,
    )
    P0ProjectionService(repository).publish(
        target_business_date="2026-08-29",
        system_as_of=datetime(2026, 8, 29, 13, tzinfo=UTC),
        assets=(
            asset("bond", CoreAssetState.BULL, "validated"),
            asset("stock", CoreAssetState.BULL, "validated"),
            asset("commodity", None, "source_conflict"),
        ),
        last_confirmed_stage=FormalStage.STAGE_II,
    )
    application = create_web_application(paths, 8050)

    response = _route(application, "stage_history").endpoint()

    assert [event["event_kind"] for event in response["events"]] == ["formal", "gap"]
    assert response["events"][1]["projection_set_id"] is None
    assert repository.current().envelope.target_business_date == "2026-08-28"


def test_release_calendar_rest_reads_certified_release_event_and_observation_count(
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
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        fetched_at=datetime(2026, 8, 20, 1, 2, tzinfo=UTC),
        expected_period="2026-08",
    )
    application = create_web_application(paths, 8050)

    response = _route(application, "release_calendar").endpoint(
        "2026-08",
        datetime(2026, 8, 20, 2, tzinfo=UTC),
    )

    assert response["status"] == "ok"
    assert response["events"][0]["status"] == "current"
    assert response["events"][0]["observation_count"] == 2
    assert response["events"][0]["release_event_family"] == "chinamoney_lpr"


def test_evidence_trace_rest_resolves_derived_formula_lineage(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    cutoff = datetime(2026, 8, 28, 13, tzinfo=UTC)
    derived = EvidenceRepository(paths.database).append_derived_observation(
        metric_id="CN_CREDIT_IMPULSE",
        formula_version="credit-impulse-rolling-share-v0001",
        input_observation_version_ids=("claim-a", "claim-b"),
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=cutoff,
        computed_at=cutoff,
        value=1.25,
        unit="percentage_points",
    )
    application = create_web_application(paths, 8050)

    response = _route(application, "evidence_trace").endpoint(
        derived.derived_observation_id,
        AsOfMode.SYSTEM,
        cutoff,
    )
    document = json.loads(cast(bytes, response.body))

    assert document["derived_observation_id"] == derived.derived_observation_id
    assert document["formula_version"] == "credit-impulse-rolling-share-v0001"
    assert document["input_observation_version_ids"] == ["claim-a", "claim-b"]


def test_report_command_is_bound_to_the_current_projection_at_acceptance(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    repository = ProjectionSetRepository(paths.database)
    readiness = tuple(
        CoreAssetReadiness(
            asset=asset,
            metric_id=metric_id,
            state=state,
            reason="validated",
            observation_count=160,
            latest_business_date="2026-08-28",
        )
        for asset, metric_id, state in (
            ("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            ("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            ("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
        )
    )
    published = P0ProjectionService(repository).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=readiness,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )

    accepted = _persist_command(
        paths,
        {
            "command": "report_generation",
            "target_business_date": "2099-01-01",
            "client_request_id": "web-report-bound",
        },
    )

    run = RunRepository(paths.database).get(str(accepted["run_id"]))
    assert run.target_business_date == "2026-08-28"
    assert run.projection_set_id == published.projection_set_id
    assert accepted["target_projection_set_id"] == published.projection_set_id
