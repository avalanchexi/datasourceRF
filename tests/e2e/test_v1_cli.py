from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.cli import main
from pring_cycle.domain import CoreAssetState
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths


def invoke(capsys: object, *arguments: str) -> dict[str, object]:
    main([*arguments, "--json"])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    return json.loads(captured.out)


def test_model_and_run_operations_share_the_public_cli_and_persistent_ledger(
    tmp_path: Path, capsys: object
) -> None:
    root = tmp_path / "runtime"
    common = ("--runtime-root", str(root))
    invoke(capsys, "init", *common)
    models = invoke(capsys, "models", *common)

    assert models["models"][0]["model_version_id"] == "model-v0001"
    assert models["models"][0]["status"] == "candidate"

    with pytest.raises(SystemExit):
        main(
            [
                "model-accept",
                *common,
                "--model",
                "model-v0001",
                "--json",
            ]
        )
    assert "calibration_evidence_incomplete" in capsys.readouterr().err  # type: ignore[attr-defined]
    ModelRepository(RuntimePaths.discover(root).database).record_acceptance(
        "model-v0001",
        CALIBRATION_BASELINE,
    )
    activated = invoke(
        capsys,
        "model-activate",
        *common,
        "--model",
        "model-v0001",
        "--confirm",
    )
    first = invoke(
        capsys,
        "run-submit",
        *common,
        "--target-date",
        "2026-08-28",
        "--request-id",
        "cli-contract-1",
    )
    duplicate = invoke(
        capsys,
        "run-submit",
        *common,
        "--target-date",
        "2026-08-28",
        "--request-id",
        "cli-contract-1",
    )

    assert activated["status"] == "active"
    assert first["run_id"] == duplicate["run_id"]
    assert invoke(capsys, "runs", *common)["runs"][0]["status"] == "queued"


def test_catalog_is_available_without_network_or_credentials(
    tmp_path: Path, capsys: object
) -> None:
    root = tmp_path / "runtime"
    invoke(capsys, "init", "--runtime-root", str(root))

    document = invoke(capsys, "catalog", "--runtime-root", str(root))

    assert document["status"] == "ok"
    assert document["network_requests"] == 0
    assert len(document["metrics"]) == 61


def test_evidence_query_and_deterministic_report_are_public_cli_operations(
    tmp_path: Path, capsys: object
) -> None:
    root = tmp_path / "runtime"
    common = ("--runtime-root", str(root))
    invoke(capsys, "init", *common)
    evidence_input = tmp_path / "evidence.json"
    evidence_input.write_text(
        json.dumps(
            {
                "metric_id": "CN_CPI_HEADLINE",
                "definition_version": "metric-catalog-v0001",
                "period_kind": "month",
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
                "dimensions": {"measure": "yoy", "category": "headline"},
                "value": 0.4,
                "value_state": "reported_value",
                "unit": "percent",
                "provider": "official-fixture",
                "source_reference": "fixture://cpi/2026-07",
                "release_event_id": "release-cpi-2026-07",
                "release_at": "2026-08-09T01:30:00+00:00",
                "public_available_at": "2026-08-09T01:30:00+00:00",
                "fetched_at": "2026-08-09T01:35:00+00:00",
                "available_at": "2026-08-09T01:35:00+00:00",
                "certification_status": "awaiting_source_certification",
                "quality_status": "validated",
            }
        ),
        encoding="utf-8",
    )

    stored = invoke(capsys, "evidence-ingest", *common, "--input", str(evidence_input))
    queried = invoke(
        capsys,
        "evidence-query",
        *common,
        "--observation-id",
        str(stored["observation_id"]),
        "--mode",
        "system_as_of",
        "--as-of",
        "2026-08-10T00:00:00+00:00",
    )
    assert queried["selected_value"] == 0.4
    assert queried["selection_status"] == "selected"

    paths = RuntimePaths.discover(root)
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
    P0ProjectionService(ProjectionSetRepository(paths.database)).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=readiness,  # type: ignore[arg-type]
        last_confirmed_stage=None,
    )

    generated = invoke(
        capsys,
        "report-generate",
        *common,
        "--request-id",
        "report-cli-contract-1",
        "--deterministic-only",
    )
    history = invoke(capsys, "reports", *common)

    assert generated["status"] == "completed_degraded"
    assert history["reports"][0]["report_snapshot_id"] == generated["report_snapshot_id"]


def test_public_evidence_ingest_cannot_self_certify_a_p0_core_series(
    tmp_path: Path,
    capsys: object,
) -> None:
    root = tmp_path / "runtime"
    invoke(capsys, "init", "--runtime-root", str(root))
    evidence_input = tmp_path / "forged-p0.json"
    evidence_input.write_text(
        json.dumps(
            {
                "metric_id": "CN_BOND_CORE_000012",
                "definition_version": "metric-catalog-v0001",
                "period_kind": "business_day",
                "period_start": "2026-08-28",
                "period_end": "2026-08-28",
                "dimensions": {},
                "value": 100.0,
                "value_state": "reported_value",
                "unit": "index_points",
                "provider": "manual",
                "source_reference": "fixture://forged-bond",
                "release_event_id": "forged-release",
                "release_at": "2026-08-28T07:30:00+00:00",
                "public_available_at": "2026-08-28T07:30:00+00:00",
                "fetched_at": "2026-08-28T08:00:00+00:00",
                "available_at": "2026-08-28T08:00:00+00:00",
                "certification_status": "certified",
                "quality_status": "validated",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        main(
            [
                "evidence-ingest",
                "--runtime-root",
                str(root),
                "--input",
                str(evidence_input),
                "--json",
            ]
        )

    assert "p0_evidence_requires_certified_adapter" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_model_replay_does_not_accept_self_attested_result_flags(capsys: object) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "model-replay",
                "--model",
                "model-v0001",
                "--compared-with",
                "model-v0000",
                "--start",
                "2026-01-01",
                "--end",
                "2026-08-28",
                "--quality-passed",
            ]
        )

    assert "unrecognized arguments: --quality-passed" in capsys.readouterr().err  # type: ignore[attr-defined]
