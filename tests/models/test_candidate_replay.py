from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.routing import APIRoute
from sqlalchemy import create_engine

import pring_cycle
from pring_cycle.cli import main
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.model_evaluation import calibrate_model, evaluate_history, replay_models
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository, certified_model_v0001_manifest
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.storage import database_health, migrate_database
from pring_cycle.web import create_web_application


def candidate_history(
    tmp_path: Path,
    prices: list[int],
    *,
    duration_version: str = "candidate-duration-v0002",
    database: Path | None = None,
) -> tuple[Path, str, list[date]]:
    # A small synthetic model using the legacy fixture catalog, never a certified live model.
    database = database or tmp_path / "candidate-history.sqlite3"
    models = ModelRepository.create(database)
    manifest = certified_model_v0001_manifest()
    manifest["model_version_id"] = "candidate-history-fixture"
    manifest["history_input_start"] = "2026-01-05"
    manifest["trend_rules"].update(
        window_days=2,
        slope_days=1,
        volatility_days=1,
        noise_multiplier=0,
        persistence_days=8,
        candidate_duration_rule_version=duration_version,
    )
    models.create_candidate(manifest)
    days: list[date] = []
    current = date(2026, 1, 5)
    while len(days) < len(prices):
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    evidence = EvidenceRepository.create(database)
    claims = []
    for metric_id, (api, code) in CORE_API_IDENTITIES.items():
        for i, day in enumerate(days):
            published = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
            claims.append(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version="metric-catalog-v0001",
                    period_kind="business_day",
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    dimensions={},
                    value=prices[i] if metric_id == "CN_EQUITY_CORE_000985" else 100 + i,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="index_points",
                    provider="tushare",
                    source_reference=f"tushare:{api}:{code}:{day.isoformat()}",
                    release_event_id=f"synthetic:{metric_id}:{day.isoformat()}",
                    release_at=published,
                    public_available_at=published,
                    fetched_at=published,
                    available_at=published,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    evidence.append_source_claims(tuple(claims))
    return database, manifest["model_version_id"], days


def test_public_history_returns_actual_seven_day_candidate_after_stable_bull(
    tmp_path: Path,
) -> None:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111), 100, 99, 98, 97, 96, 95, 94]
    )
    result = evaluate_history(
        database,
        model_id,
        requested_start=days[-1].isoformat(),
        requested_end=days[-1].isoformat(),
    )
    assert result.core_states_by_day == {days[-1].isoformat(): ("bull", "bull", "bull")}
    assert result.stages_by_day == {days[-1].isoformat(): "stage_iii"}
    assert set(result.core_outputs_by_day) == {days[-1].isoformat()}
    output = result.core_outputs_by_day[days[-1].isoformat()]
    assert asdict(output["stock"]) == {
        "stable_state": "bull",
        "candidate_state": "bear",
        "actual_candidate_days": 7,
        "candidate_days": 7,
        "confirmation_threshold_days": 8,
    }
    assert output["bond"].candidate_state is None and output["bond"].candidate_days == 0
    assert output["commodity"].candidate_state is None and output["commodity"].candidate_days == 0
    assert result.candidate_duration_rule_version == "candidate-duration-v0002"


@pytest.mark.parametrize(
    "duration_version", ["candidate-duration-v0001", "candidate-duration-v0002"]
)
@pytest.mark.parametrize(
    ("tail", "stable", "candidate", "actual", "stage"),
    [
        ([], "bull", None, 0, "stage_iii"),
        ([100, 99, 98, 97, 96, 95, 94], "bull", "bear", 7, "stage_iii"),
        ([100, 99, 98, 97, 96, 95, 94, 93], "bear", None, 0, None),
        ([100, 99, 100], "bull", None, 0, "stage_iii"),
        ([100, 99, 100, 98], "bull", "bear", 1, "stage_iii"),
        ([100, 99, 100, 101], "bull", None, 0, "stage_iii"),
        ([100, 99, 98, 97, 96, 95, 94, 93, 94, 95], "bear", "bull", 1, None),
    ],
)
def test_history_candidate_confirmation_interruption_and_legacy_display(
    tmp_path: Path,
    duration_version: str,
    tail: list[int],
    stable: str,
    candidate: str | None,
    actual: int,
    stage: str | None,
) -> None:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111), *tail], duration_version=duration_version
    )
    result = evaluate_history(
        database,
        model_id,
        requested_start=days[-1].isoformat(),
        requested_end=days[-1].isoformat(),
    )
    output = result.core_outputs_by_day[days[-1].isoformat()]["stock"]
    assert (output.stable_state, output.candidate_state, output.actual_candidate_days) == (
        stable,
        candidate,
        actual,
    )
    assert output.candidate_days == (
        8 if duration_version == "candidate-duration-v0001" else actual
    )
    assert result.stages_by_day[days[-1].isoformat()] == stage


def test_history_rejects_an_explicit_unsupported_duration_rule(tmp_path: Path) -> None:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111)], duration_version="candidate-duration-unknown"
    )
    with pytest.raises(ValueError, match="candidate_duration_rule_version_unsupported"):
        evaluate_history(
            database,
            model_id,
            requested_start=days[-1].isoformat(),
            requested_end=days[-1].isoformat(),
        )


def test_late_revision_changes_only_candidate_outputs_at_visible_cutoffs(tmp_path: Path) -> None:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111), 100, 99, 98, 97, 96, 95, 94, 93]
    )
    previous_day, last_day = days[-2].isoformat(), days[-1].isoformat()
    old = evaluate_history(database, model_id, requested_start=previous_day, requested_end=last_day)
    assert old.core_outputs_by_day[previous_day]["stock"].candidate_days == 7
    assert old.core_outputs_by_day[last_day]["stock"].stable_state == "bear"
    assert old.core_outputs_by_day[last_day]["stock"].candidate_days == 0
    published = datetime(days[-1].year, days[-1].month, days[-1].day, 8, tzinfo=UTC)
    EvidenceRepository(database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_EQUITY_CORE_000985",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start=days[15].isoformat(),
            period_end=days[15].isoformat(),
            dimensions={},
            value=100,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference=f"tushare:index_daily:000985.CSI:{days[15].isoformat()}",
            release_event_id="synthetic:late-revision",
            release_at=published,
            public_available_at=published,
            fetched_at=published,
            available_at=published,
            certification_status="certified",
            quality_status="validated",
        )
    )
    short = evaluate_history(
        database, model_id, requested_start=previous_day, requested_end=previous_day
    )
    revised = evaluate_history(
        database, model_id, requested_start=previous_day, requested_end=last_day
    )
    assert short.core_outputs_by_day[previous_day]["stock"].candidate_days == 7
    assert revised.core_outputs_by_day[previous_day]["stock"].candidate_days == 7
    output = revised.core_outputs_by_day[last_day]["stock"]
    assert (output.stable_state, output.candidate_state, output.candidate_days) == (
        "bull",
        "bear",
        3,
    )
    assert revised.evidence_hash != old.evidence_hash


def test_calibration_preserves_candidate_detail_and_old_unrecorded_acceptance(
    tmp_path: Path,
) -> None:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111), 100, 99, 98, 97, 96, 95, 94]
    )
    models = ModelRepository(database)
    # The pre-existing legacy fixture interface is not a candidate-field acceptance.
    legacy = models.record_acceptance(model_id, CALIBRATION_BASELINE)
    results = calibrate_model(
        database,
        model_id,
        requested_start=days[-1].isoformat(),
        requested_end=days[-1].isoformat(),
    )
    assert results["core_output_document"]["days"][0]["assets"]["stock"]["candidate_days"] == 7
    accepted = models.record_acceptance(model_id, results)
    assert not accepted.passed  # This short fixture does not match the full calibration baseline.
    assert accepted.core_output_hash is not None and len(accepted.core_output_hash) == 64
    saved = ModelRepository(database).acceptance_details(model_id, accepted.result_hash)
    assert saved["core_output_status"] == "recorded"
    assert saved["core_output_document"]["asset_days"] == 3
    assert (
        saved["core_output_document"]["candidate_duration_rule_version"]
        == "candidate-duration-v0002"
    )
    assert saved["core_output_document"]["days"][0]["assets"]["stock"]["candidate_days"] == 7
    old = models.acceptance_details(model_id, legacy.result_hash)
    assert old["core_output_status"] == "not_recorded"
    assert old["core_output_document"] is None
    assert old["result_hash"] == legacy.result_hash


def test_cli_replay_preserves_rule_differences_and_reads_saved_daily_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    database, candidate_id, days = candidate_history(
        tmp_path,
        [*range(100, 111), 100, 99, 98, 97, 96, 95, 94],
        database=paths.database,
    )
    models = ModelRepository(database)
    models.create_candidate(certified_model_v0001_manifest())
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    baseline = models.manifest(candidate_id)
    baseline_id = "legacy-display-fixture"
    baseline["model_version_id"] = baseline_id
    baseline["trend_rules"]["candidate_duration_rule_version"] = "candidate-duration-v0001"
    models.create_candidate(baseline)
    # Bootstrap only the isolated legacy fixture baseline. Both replays really compute.
    models.record_acceptance(baseline_id, CALIBRATION_BASELINE)
    day = days[-1].isoformat()
    common = ["--runtime-root", str(paths.override_root), "--start", day, "--end", day, "--json"]
    main(["model-replay", "--model", baseline_id, "--compared-with", "model-v0001", *common])
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
    models.activate(baseline_id, explicitly_approved=True)

    main(["model-replay", "--model", candidate_id, "--compared-with", baseline_id, *common])
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert result["stage_differences"] == result["core_state_differences"] == 0
    assert result["candidate_state_differences"] == 0
    assert result["candidate_days_differences"] == 3
    assert len(result["core_output_hash"]) == 64
    saved = ModelRepository(database).replay_details(result["replay_id"])
    assert saved["core_output_status"] == "recorded"
    document = saved["core_output_document"]
    assert document["candidate"]["days"][0]["assets"]["stock"]["candidate_days"] == 7
    assert document["comparison"]["days"][0]["assets"]["stock"]["candidate_days"] == 8
    assert len(document["differences"]) == 3
    main(
        [
            "model-replay-show",
            "--runtime-root",
            str(paths.override_root),
            "--replay-id",
            str(result["replay_id"]),
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out) == saved
    application = create_web_application(paths, 8877, eager_dashboard=False)
    route = next(
        route
        for route in application.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/model-replays/{replay_id}"
    )
    response = route.endpoint(result["replay_id"])
    assert response.status_code == 200 and json.loads(response.body) == saved
    assert models.get(candidate_id).status == "candidate"
    assert models.active().model_version_id == baseline_id


def replay_case(tmp_path: Path) -> tuple[ModelRepository, dict[str, Any], list[date]]:
    database, model_id, days = candidate_history(
        tmp_path, [*range(100, 111), 100, 99, 98, 97, 96, 95, 94]
    )
    models = ModelRepository(database)
    models.create_candidate(certified_model_v0001_manifest())
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    evaluation = replay_models(
        database,
        model_id,
        "model-v0001",
        requested_start=days[-1].isoformat(),
        requested_end=days[-1].isoformat(),
    )
    args = asdict(evaluation)
    args["model_version_id"] = model_id
    args["compared_with"] = "model-v0001"
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    return models, args, days


def test_replay_rejects_invalid_input_fingerprint_even_with_matching_document_hash(
    tmp_path: Path,
) -> None:
    models, args, _days = replay_case(tmp_path)
    document = args["core_output_document"]
    document["candidate"]["evidence_hash"] = "g" * 64
    args["core_output_hash"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="model_output_evidence_hash_invalid"):
        models.record_replay(**args)


def test_saved_replay_detects_late_evidence_even_when_candidate_counts_do_not_change(
    tmp_path: Path,
) -> None:
    models, args, days = replay_case(tmp_path)
    replay = models.record_replay(**args)
    saved = models.replay_details(replay.replay_id)
    assert models.replay_matches_current_evidence(replay.replay_id)
    day = days[-1]
    public = datetime(day.year, day.month, day.day, 9, tzinfo=UTC)
    acquired = public + timedelta(days=1)
    database = tmp_path / "candidate-history.sqlite3"
    EvidenceRepository(database).append_source_claim(
        SourceClaimInput(
            metric_id="CN_EQUITY_CORE_000985",
            definition_version="metric-catalog-v0001",
            period_kind="business_day",
            period_start=day.isoformat(),
            period_end=day.isoformat(),
            dimensions={},
            value=94,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="index_points",
            provider="tushare",
            source_reference=f"tushare:index_daily:000985.CSI:{day.isoformat()}",
            release_event_id="synthetic:same-price-late-acquisition",
            release_at=public,
            public_available_at=public,
            fetched_at=acquired,
            available_at=acquired,
            certification_status="certified",
            quality_status="validated",
        )
    )
    current = replay_models(
        database,
        args["model_version_id"],
        args["compared_with"],
        requested_start=day.isoformat(),
        requested_end=day.isoformat(),
    )
    assert current.quality_passed
    assert current.stage_differences == replay.stage_differences
    assert current.core_state_differences == replay.core_state_differences
    assert current.candidate_state_differences == replay.candidate_state_differences
    assert current.candidate_days_differences == replay.candidate_days_differences
    assert current.core_output_hash != replay.core_output_hash
    assert not models.replay_matches_current_evidence(replay.replay_id)
    assert ModelRepository(database).replay_details(replay.replay_id) == saved


@pytest.mark.parametrize(
    "damage",
    [
        "missing_asset",
        "missing_candidate_days",
        "missing_null_stage",
        "wrong_rule",
        "duplicate_day",
        "forged_count",
        "wrong_hash",
        "boolean_day_count",
    ],
)
def test_replay_does_not_record_partial_or_inconsistent_outputs(
    tmp_path: Path, damage: str
) -> None:
    models, args, _days = replay_case(tmp_path)
    document = args["core_output_document"]
    if damage == "missing_asset":
        del document["candidate"]["days"][0]["assets"]["stock"]
    elif damage == "missing_candidate_days":
        del document["candidate"]["days"][0]["assets"]["stock"]["candidate_days"]
    elif damage == "missing_null_stage":
        assert document["comparison"]["days"][0]["stage"] is None
        del document["comparison"]["days"][0]["stage"]
    elif damage == "wrong_rule":
        document["candidate"]["candidate_duration_rule_version"] = "candidate-duration-v0001"
    elif damage == "duplicate_day":
        document["candidate"]["days"].append(document["candidate"]["days"][0])
    elif damage == "forged_count":
        args["candidate_days_differences"] += 1
    elif damage == "boolean_day_count":
        args["evaluated_trading_days"] = True
    args["core_output_hash"] = (
        hashlib.sha256(
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if damage != "wrong_hash"
        else "f" * 64
    )
    expected_error = (
        "context_output_calendar_invalid" if damage == "boolean_day_count" else "model_output_"
    )
    with pytest.raises(ValueError, match=expected_error):
        models.record_replay(**args)
    with pytest.raises(LookupError, match="model_replay_not_found"):
        models.replay_details(1)


def test_calibration_detail_is_readable_from_cli_and_api(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    database, model_id, days = candidate_history(
        tmp_path,
        [*range(100, 111), 100, 99, 98, 97, 96, 95, 94],
        database=paths.database,
    )
    models = ModelRepository(database)
    results = calibrate_model(
        database,
        model_id,
        requested_start=days[-1].isoformat(),
        requested_end=days[-1].isoformat(),
    )
    acceptance = models.record_acceptance(model_id, results)
    expected = models.acceptance_details(model_id, acceptance.result_hash)
    main(
        [
            "model-acceptance-show",
            "--runtime-root",
            str(paths.override_root),
            "--model",
            model_id,
            "--result-hash",
            acceptance.result_hash,
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out) == expected
    app = create_web_application(paths, 8877, eager_dashboard=False)
    endpoint = next(
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/models/{model_version_id}/acceptances/{result_hash}"
    )
    response = endpoint(model_id, acceptance.result_hash)
    assert response.status_code == 200 and json.loads(response.body) == expected
    missing = endpoint(model_id, "0" * 64)
    assert missing.status_code == 404


def test_legacy_replay_without_daily_outputs_keeps_unknown_candidate_counts(tmp_path: Path) -> None:
    models, args, _days = replay_case(tmp_path)
    for name in (
        "core_output_document",
        "core_output_hash",
        "candidate_state_differences",
        "candidate_days_differences",
    ):
        del args[name]
    legacy = models.record_replay(**args)
    saved = models.replay_details(legacy.replay_id)
    assert saved["core_output_status"] == "not_recorded"
    assert saved["core_output_document"] is None
    assert saved["replay"]["candidate_state_differences"] is None
    assert saved["replay"]["candidate_days_differences"] is None
    assert not models.replay_matches_current_evidence(legacy.replay_id)


def test_hardened_v2_replay_cannot_pass_without_candidate_outputs(tmp_path: Path) -> None:
    models, args, days = replay_case(tmp_path)
    manifest = models.manifest(args["model_version_id"])
    manifest["model_version_id"] = "hardened-short-fixture"
    manifest["replay_acceptance_rule_version"] = "active-baseline-exact-120-v0001"
    # Isolated one-day contract test; never a real 120-day acceptance.
    manifest["visible_evidence_window_trading_days"] = 1
    manifest["certified_replay_start"] = days[-1].isoformat()
    models.create_candidate(manifest)
    args["model_version_id"] = manifest["model_version_id"]
    for name in (
        "core_output_document",
        "core_output_hash",
        "candidate_state_differences",
        "candidate_days_differences",
        "context_output_document",
        "context_output_hash",
    ):
        del args[name]
    rejected = models.record_replay(**args)
    assert not rejected.passed
    assert rejected.gaps == ("context_outputs_not_recorded", "core_candidate_outputs_incomplete")
    assert models.active().model_version_id == "model-v0001"


@pytest.mark.parametrize(
    "old_revision", ["0019_registered_metric_catalog", "0020_model_evaluation_outputs"]
)
def test_old_runtime_migrates_and_keeps_unrecorded_replay_readable(
    tmp_path: Path, old_revision: str
) -> None:
    database = tmp_path / "legacy.sqlite3"
    config = Config()
    config.set_main_option("script_location", str(Path(pring_cycle.__file__).parent / "migrations"))
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, old_revision)
    finally:
        engine.dispose()
    models = ModelRepository(database)
    models.create_candidate(certified_model_v0001_manifest())
    # A failed historical record in the old SQLite format, not a fabricated passed replay.
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO model_replay(
                model_version_id, compared_with, range_start, range_end,
                quality_passed, regression_passed, performance_passed,
                stage_differences, core_state_differences, gaps_json, passed, created_at
            ) VALUES ('model-v0001', 'model-v0001', '2026-01-05', '2026-01-05',
                0, 0, 1, 0, 0, '["historical_failed_fixture"]', 0, '2026-01-06T00:00:00+00:00')"""
        )
    migrate_database(database)
    saved = ModelRepository(database).replay_details(1)
    assert saved["core_output_status"] == "not_recorded"
    assert saved["context_output_status"] == "not_recorded"
    assert saved["context_output_document"] is None
    assert not models.replay_matches_current_evidence(1)
    assert saved["replay"]["gaps"] == ["historical_failed_fixture"]
    assert saved["replay"]["passed"] is False
    assert saved["replay"]["candidate_days_differences"] is None
    assert database_health(database)["migration"] == "current"
    migrate_database(database)
    assert ModelRepository(database).replay_details(1) == saved


def test_cli_saves_failed_replay_for_original_range_when_final_day_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    database, model_id, days = candidate_history(
        tmp_path,
        [*range(100, 111), 100, 99, 98, 97, 96, 95, 94],
        database=paths.database,
    )
    models = ModelRepository(database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    missing = (days[-1] + timedelta(days=1)).isoformat()
    main(
        [
            "model-replay",
            "--runtime-root",
            str(paths.override_root),
            "--model",
            model_id,
            "--compared-with",
            "model-v0001",
            "--start",
            days[-1].isoformat(),
            "--end",
            missing,
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "failed"
    assert result["range_end"] == missing
    assert "certified_replay_range_not_exact" in result["gaps"]
    saved = models.replay_details(result["replay_id"])
    assert saved["replay"]["range_end"] == missing
    assert (
        saved["core_output_document"]["candidate"]["days"][-1]["business_date"]
        == days[-1].isoformat()
    )


def lpr_replay_case(tmp_path: Path) -> tuple[RuntimePaths, ModelRepository, dict[str, Any]]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    database, template_id, days = candidate_history(
        tmp_path, list(range(100, 118)), database=paths.database
    )
    models = ModelRepository(database)
    models.create_candidate(certified_model_v0001_manifest())
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    manifest = models.manifest(template_id)
    manifest["model_version_id"] = "context-lpr-fixture"
    for definition in manifest["metric_definitions"]:
        if definition["metric_id"] == "CN_LPR_1Y_5Y":
            definition["source_candidates"] = ["candidate-lpr-source"]
    models.create_candidate(manifest)
    evidence = EvidenceRepository(database)

    published = datetime(2026, 1, 20, 1, tzinfo=UTC)
    append_lpr(evidence, "1y", 3.0, published, published)
    append_lpr(evidence, "5y_plus", 3.5, published, published)
    day = days[-1].isoformat()
    before = replay_models(
        database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start=day,
        requested_end=day,
    )
    assert before.quality_passed, before.gaps
    assert before.context_output_differences == 0
    args = asdict(before)
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    args["model_version_id"] = "context-lpr-fixture"
    args["compared_with"] = "model-v0001"
    return paths, models, args


def append_lpr(
    evidence: EvidenceRepository,
    tenor: str,
    value: float,
    public: datetime,
    acquired: datetime,
    *,
    quality: str = "validated",
) -> None:
    evidence.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start="2026-01-01",
            period_end="2026-01-31",
            dimensions={"tenor": tenor},
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider="中国货币网",
            source_reference=f"fixture:lpr:{tenor}",
            release_event_id=f"fixture:lpr:{tenor}:{public.isoformat()}",
            release_at=public,
            public_available_at=public,
            fetched_at=acquired,
            available_at=acquired,
            certification_status="certified",
            quality_status=quality,
        )
    )


def test_saved_replay_detects_lpr_vintage_change_with_unchanged_context_difference_count(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths, models, args = lpr_replay_case(tmp_path)
    replay = models.record_replay(**args)
    saved = models.replay_details(replay.replay_id)
    assert models.replay_matches_current_evidence(replay.replay_id)

    day = args["requested_end"]
    later_public = datetime.fromisoformat(f"{day}T09:00:00+00:00")
    assert saved["context_output_status"] == "recorded"
    context = saved["context_output_document"]["days"][0]["candidate"]
    inputs = context["source_inputs"]["CN_LPR_1Y_5Y"]
    assert {point["dimensions"]["tenor"]: point["selected_value"] for point in inputs} == {
        "1y": 3.0,
        "5y_plus": 3.5,
    }
    assert all(point["selected_claim_id"] for point in inputs)
    main(
        [
            "model-replay-show",
            "--runtime-root",
            str(paths.override_root),
            "--replay-id",
            str(replay.replay_id),
            "--json",
        ]
    )
    assert json.loads(capsys.readouterr().out) == saved
    app = create_web_application(paths, 8877, eager_dashboard=False)
    endpoint = next(
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/model-replays/{replay_id}"
    )
    response = endpoint(replay.replay_id)
    assert response.status_code == 200 and json.loads(response.body) == saved
    append_lpr(
        EvidenceRepository(paths.database),
        "1y",
        3.0,
        later_public,
        later_public + timedelta(days=1),
    )
    after = replay_models(
        paths.database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start=day,
        requested_end=day,
    )
    assert after.quality_passed, after.gaps
    assert after.context_output_differences == 0
    assert after.core_output_hash == args["core_output_hash"]
    assert not models.replay_matches_current_evidence(replay.replay_id)
    assert models.replay_details(replay.replay_id) == saved


def test_context_replay_rejects_snapshot_without_selected_source_identity(tmp_path: Path) -> None:
    _paths, models, args = lpr_replay_case(tmp_path)
    document = args["context_output_document"]
    point = document["days"][0]["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"][0]
    del point["selected_claim_id"]
    args["context_output_hash"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="context_output_inputs_incomplete"):
        models.record_replay(**args)
    with pytest.raises(LookupError, match="model_replay_not_found"):
        models.replay_details(1)


def test_required_context_cannot_be_recorded_as_not_applicable(tmp_path: Path) -> None:
    _paths, models, args = lpr_replay_case(tmp_path)
    document = args["context_output_document"]
    document.update(status="not_applicable", days=[], source_metrics=[], formula_keys=[])
    args["context_output_hash"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="context_output_scope_invalid"):
        models.record_replay(**args)
    with pytest.raises(LookupError, match="model_replay_not_found"):
        models.replay_details(1)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_tenor",
        "empty_inputs",
        "unknown_selected_claim",
        "null_selected_claim",
        "wrong_version",
        "value_mismatch",
        "future_public",
        "wrong_unit",
        "non_numeric_value",
    ],
)
def test_recorded_context_requires_complete_selected_inputs(tmp_path: Path, damage: str) -> None:
    _paths, models, args = lpr_replay_case(tmp_path)
    document = args["context_output_document"]
    points = document["days"][0]["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"]
    if damage == "missing_tenor":
        points.pop()
    elif damage == "empty_inputs":
        points.clear()
    elif damage == "unknown_selected_claim":
        points[0]["selected_claim_id"] = "unrelated-claim"
    elif damage == "null_selected_claim":
        points[0]["selected_claim_id"] = None
    elif damage == "wrong_version":
        points[0]["definition_version"] = "different-catalog"
    elif damage == "value_mismatch":
        points[0]["selected_value"] = 99.0
    elif damage == "future_public":
        points[0]["claims"][0]["public_available_at"] = "2026-01-29T00:00:00+08:00"
    elif damage == "wrong_unit":
        points[0]["claims"][0]["unit"] = "unrelated-unit"
    elif damage == "non_numeric_value":
        points[0]["selected_value"] = points[0]["claims"][0]["value"] = "3.0"
    args["context_output_hash"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="context_output_inputs_incomplete"):
        models.record_replay(**args)
    with pytest.raises(LookupError, match="model_replay_not_found"):
        models.replay_details(1)


def test_context_replay_rejects_empty_economic_output(tmp_path: Path) -> None:
    _paths, models, args = lpr_replay_case(tmp_path)
    document = args["context_output_document"]
    for side in ("candidate", "comparison"):
        document["days"][0][side].update(macro={}, inventory={})
    args["context_output_hash"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="context_output_fields_incomplete"):
        models.record_replay(**args)


def test_context_replay_keeps_daily_public_values_and_failed_input_status(tmp_path: Path) -> None:
    paths, models, _args = lpr_replay_case(tmp_path)
    public = datetime(2026, 1, 27, 9, tzinfo=UTC)
    append_lpr(EvidenceRepository(paths.database), "1y", 2.9, public, public + timedelta(days=2))
    evaluated = replay_models(
        paths.database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start="2026-01-26",
        requested_end="2026-01-28",
    )
    args = asdict(evaluated)
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    replay = models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)
    saved = models.replay_details(replay.replay_id)
    assert replay.passed
    rows = saved["context_output_document"]["days"]
    assert [
        (
            row["business_date"],
            next(
                p["selected_value"]
                for p in row["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"]
                if p["dimensions"]["tenor"] == "1y"
            ),
        )
        for row in rows
    ] == [("2026-01-26", 3.0), ("2026-01-27", 2.9), ("2026-01-28", 2.9)]
    # An earlier cutoff has no publicly available LPR: retain failure and gaps.
    earlier = replay_models(
        paths.database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start="2026-01-19",
        requested_end="2026-01-19",
    )
    assert not earlier.quality_passed and earlier.gaps
    args = asdict(earlier)
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    args.update(quality_passed=True, regression_passed=True, gaps=())
    failed = models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)
    assert not failed.passed and failed.gaps
    incomplete = models.replay_details(failed.replay_id)
    assert incomplete["context_output_status"] == "incomplete"
    assert incomplete["context_output_document"]["days"] == []
    assert models.replay_details(replay.replay_id) == saved


def test_core_only_legacy_replay_does_not_acquire_context_evidence_on_read(tmp_path: Path) -> None:
    _paths, models, args = lpr_replay_case(tmp_path)
    del args["context_output_document"], args["context_output_hash"]
    replay = models.record_replay(**args)
    saved = models.replay_details(replay.replay_id)
    assert saved["core_output_status"] == "recorded"
    assert saved["context_output_status"] == "not_recorded"
    assert saved["context_output_document"] is None
    assert not models.replay_matches_current_evidence(replay.replay_id)


def test_failed_context_snapshot_preserves_invalid_selected_input(tmp_path: Path) -> None:
    paths, models, _args = lpr_replay_case(tmp_path)
    public = datetime(2026, 1, 28, 9, tzinfo=UTC)
    append_lpr(EvidenceRepository(paths.database), "1y", 2.8, public, public, quality="invalid")
    evaluated = replay_models(
        paths.database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start="2026-01-28",
        requested_end="2026-01-28",
    )
    assert not evaluated.quality_passed and evaluated.gaps
    args = asdict(evaluated)
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    replay = models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)
    saved = models.replay_details(replay.replay_id)
    assert not replay.passed and saved["context_output_status"] == "incomplete"
    points = saved["context_output_document"]["days"][0]["candidate"]["source_inputs"][
        "CN_LPR_1Y_5Y"
    ]
    point = next(p for p in points if p["dimensions"]["tenor"] == "1y")
    assert point["selected_value"] == 2.8
    assert point["claims"][0]["quality_status"] == "invalid"
