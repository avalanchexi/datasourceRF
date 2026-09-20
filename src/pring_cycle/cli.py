from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pring_cycle.runtime import (
    RuntimeNotInitializedError,
    RuntimePaths,
    RuntimePolicyError,
    diagnose_runtime,
    initialize_runtime,
)

if TYPE_CHECKING:
    from pring_cycle.evidence import SourceClaimInput

_MUTATING_COMMANDS = {
    "model-accept",
    "model-activate",
    "model-replay",
    "model-source-certify",
    "model-source-refresh",
    "model-rollback",
    "fixture-project",
    "gap-notice",
    "lpr-refresh",
    "run-submit",
    "schedule",
    "evidence-ingest",
    "report-generate",
    "rehearse-fixture-recovery",
    "rehearse-real",
    "cutover-manifest",
    "cutover-record",
    "source-smoke",
    "context-source-smoke",
    "market-source-smoke",
    "official-context-smoke",
    "eia-smoke",
    "eia-html-refresh",
    "treasury-csv-refresh",
    "ecb-reference-import",
    "ecb-reference-refresh",
    "lpr-smoke",
    "core-history-refresh",
}


def main(arguments: Sequence[str] | None = None) -> None:
    parser = _parser()
    namespace = parser.parse_args(arguments)
    document: Mapping[str, object]
    try:
        paths = RuntimePaths.discover(namespace.runtime_root)
        if namespace.command == "init":
            document = initialize_runtime(paths)
        elif namespace.command == "doctor":
            document = diagnose_runtime(paths)
        elif namespace.command == "secrets-migrate":
            from pring_cycle.secrets import migrate_data_source_secrets

            if not paths.database.is_file():
                raise RuntimeNotInitializedError("runtime_not_initialized")
            document = migrate_data_source_secrets(namespace.source, paths.secrets)
        elif namespace.command == "web":
            from pring_cycle.web import run_web

            run_web(paths, namespace.port)
            return
        elif namespace.command == "worker":
            from pring_cycle.worker import run_worker

            run_worker(paths)
            return
        elif namespace.command in {"test", "verify"}:
            from pring_cycle.verification import VerificationError, verify_local_runtime

            try:
                document = verify_local_runtime(paths)
            except VerificationError as error:
                raise ValueError(str(error)) from error
        else:
            document = _v1_command(namespace, paths)
    except (
        KeyError,
        LookupError,
        RuntimeNotInitializedError,
        RuntimePolicyError,
        TypeError,
        ValueError,
    ) as error:
        parser.exit(2, f"error: {error}\n")

    _print_document(document, namespace.json)


def _v1_command(namespace: argparse.Namespace, paths: RuntimePaths) -> Mapping[str, object]:
    from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog
    from pring_cycle.evidence import AsOfMode, EvidenceRepository
    from pring_cycle.maintenance import (
        MaintenanceRepository,
        capacity_state,
        mutation_rejection,
    )
    from pring_cycle.models import ModelRepository
    from pring_cycle.projections import ProjectionSetRepository
    from pring_cycle.reports import (
        CliReportAdapter,
        ReportRepository,
        ReportService,
        evidence_bundle_from_projection,
    )
    from pring_cycle.runs import RunRepository

    if namespace.command in _MUTATING_COMMANDS:
        rejection = mutation_rejection(
            paths.database,
            paths.data,
            non_core_large_task=namespace.command
            in {"report-generate", "model-replay", "rehearse-real"},
        )
        if rejection is not None:
            raise ValueError(rejection)
    if namespace.command == "fixture-project":
        from pring_cycle.core_fixture import project_core_fixture

        fixture = json.loads(namespace.input.read_text(encoding="utf-8"))
        return asdict(project_core_fixture(paths, fixture))
    if namespace.command == "lpr-contract":
        from pring_cycle.official_lpr import parse_lpr_announcement

        parsed = parse_lpr_announcement(
            namespace.input.read_bytes(),
            source_url=namespace.url,
            fetched_at=datetime.fromisoformat(namespace.fetched_at),
            expected_period=namespace.period,
        )
        return {
            **asdict(parsed),
            "network_requests": 0,
            "observation_count": len(parsed.observations),
            "status": "validated",
        }
    if namespace.command == "official-context-contract":
        from pring_cycle.official_context import parse_official_context_document

        parsed_context = parse_official_context_document(
            namespace.input.read_bytes(),
            family=namespace.family,
            source_url=namespace.url,
            expected_period=namespace.period,
            fetched_at=datetime.fromisoformat(namespace.fetched_at),
        )
        return {
            **asdict(parsed_context),
            "network_requests": 0,
            "observation_count": len(parsed_context.scalars),
            "status": "validated_candidate",
        }
    if namespace.command == "official-context-smoke":
        from pring_cycle.official_context import smoke_official_context_document
        from pring_cycle.rehearsals import store_source_smoke_result

        result = asdict(
            smoke_official_context_document(
                family=namespace.family,
                source_url=namespace.url,
                expected_period=namespace.period,
                fetched_at=datetime.now(UTC),
            )
        )
        return store_source_smoke_result(
            paths,
            kind=f"official-context:{namespace.family}",
            result=result,
            target_scope={"period": namespace.period},
        )
    if namespace.command == "source-history-smoke":
        from pring_cycle.rehearsals import store_source_smoke_result
        from pring_cycle.source_history import smoke_source_history

        result = smoke_source_history(
            paths,
            target_business_date=namespace.target_date,
            browser_capture_root=namespace.browser_capture_root,
        )
        return store_source_smoke_result(
            paths,
            kind="source-history",
            result=result,
            target_scope={"target_business_date": namespace.target_date},
        )
    if namespace.command == "eia-html-refresh":
        from pring_cycle.eia_html import refresh_eia_history

        return asdict(
            refresh_eia_history(
                paths,
                series_id=namespace.series,
                start_date=date.fromisoformat(namespace.start),
                end_date=date.fromisoformat(namespace.end),
                definition_version=namespace.definition_version,
            )
        )
    if namespace.command == "treasury-csv-refresh":
        from pring_cycle.treasury_context import refresh_treasury_yields

        return asdict(
            refresh_treasury_yields(
                paths,
                start_date=date.fromisoformat(namespace.start),
                end_date=date.fromisoformat(namespace.end),
                definition_version=namespace.definition_version,
            )
        )
    if namespace.command in {"ecb-reference-import", "ecb-reference-refresh"}:
        from pring_cycle.ecb_reference import (
            import_ecb_reference_cross,
            refresh_ecb_reference_cross,
        )

        start_date, end_date = (
            date.fromisoformat(namespace.start),
            date.fromisoformat(namespace.end),
        )
        if namespace.command == "ecb-reference-import":
            return asdict(
                import_ecb_reference_cross(
                    paths,
                    namespace.input.read_bytes(),
                    source_url=namespace.url,
                    start_date=start_date,
                    end_date=end_date,
                    definition_version=namespace.definition_version,
                )
            )
        return asdict(
            refresh_ecb_reference_cross(
                paths,
                start_date=start_date,
                end_date=end_date,
                definition_version=namespace.definition_version,
            )
        )
    if namespace.command == "eia-contract":
        from pring_cycle.eia_context import EiaPetroleumAdapter

        response = json.loads(namespace.input.read_text(encoding="utf-8"))
        prices = EiaPetroleumAdapter(
            "offline-contract-key",
            transport=lambda _parameters: response,
        ).spot_prices(
            start_date=date.fromisoformat(namespace.start),
            end_date=date.fromisoformat(namespace.end),
        )
        return {
            "metric_ids": sorted({item.metric_id for item in prices}),
            "network_requests": 0,
            "observation_count": len(prices),
            "series_ids": sorted({item.series_id for item in prices}),
            "status": "validated_candidate",
        }
    if namespace.command == "eia-smoke":
        from pring_cycle.eia_context import EiaPetroleumAdapter
        from pring_cycle.rehearsals import store_source_smoke_result
        from pring_cycle.secrets import parse_data_source_secrets

        api_key = parse_data_source_secrets(paths.secrets).get("EIA_API_KEY")
        if api_key is None:
            raise ValueError("eia_api_key_required")
        result = asdict(
            EiaPetroleumAdapter(api_key).smoke(
                start_date=date.fromisoformat(namespace.start),
                end_date=date.fromisoformat(namespace.end),
            )
        )
        return store_source_smoke_result(
            paths,
            kind="eia",
            result=result,
            target_scope={"start": namespace.start, "end": namespace.end},
        )
    if namespace.command == "lpr-refresh":
        from pring_cycle.official_lpr import refresh_lpr_release

        refreshed = refresh_lpr_release(
            paths,
            source_url=namespace.url,
            expected_period=namespace.period,
            fetched_at=datetime.now(UTC),
            definition_version=_active_definition_version(paths),
        )
        return {**asdict(refreshed), "network_requests": 1}
    if namespace.command == "lpr-smoke":
        from pring_cycle.official_lpr import smoke_lpr_release
        from pring_cycle.rehearsals import store_source_smoke_result

        result = asdict(
            smoke_lpr_release(
                source_url=namespace.url,
                expected_period=namespace.period,
                fetched_at=datetime.now(UTC),
            )
        )
        return store_source_smoke_result(
            paths,
            kind="lpr",
            result=result,
            target_scope={"period": namespace.period},
        )
    if namespace.command == "release-calendar":
        from pring_cycle.release_calendar import lpr_release_calendar

        events = lpr_release_calendar(
            EvidenceRepository(paths.database),
            period=namespace.period,
            as_of=datetime.fromisoformat(namespace.as_of),
            holidays=tuple(namespace.holiday),
            definition_version=_active_definition_version(paths),
        )
        return {"events": [asdict(item) for item in events], "status": "ok"}
    if namespace.command == "stage-history":
        return {
            "events": list(ProjectionSetRepository(paths.database).stage_history()),
            "status": "ok",
        }
    if namespace.command == "gap-notice":
        return ProjectionSetRepository(paths.database).create_gap_notice(
            namespace.assessment_id,
            client_request_id=namespace.request_id,
        )
    if namespace.command == "gap-notices":
        return {
            "notices": list(ProjectionSetRepository(paths.database).gap_notices()),
            "status": "ok",
        }
    if namespace.command == "catalog":
        return {
            "catalog_version": METRIC_CATALOG_VERSION,
            "metrics": [asdict(item) for item in metric_catalog()],
            "network_requests": 0,
            "status": "ok",
        }
    if namespace.command == "models":
        return {
            "models": [asdict(item) for item in ModelRepository(paths.database).list_versions()],
            "status": "ok",
        }
    if namespace.command == "model-accept":
        from pring_cycle.model_evaluation import calibrate_model

        acceptance = ModelRepository(paths.database).record_acceptance(
            namespace.model,
            calibrate_model(paths.database, namespace.model),
        )
        return {
            **asdict(acceptance),
            "status": "accepted" if acceptance.passed else "rejected",
        }
    if namespace.command == "core-history-refresh":
        from pring_cycle.core_history import refresh_core_history
        from pring_cycle.secrets import parse_data_source_secrets
        from pring_cycle.source_adapters import TushareCoreAdapter

        token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
        if token is None:
            raise ValueError("tushare_not_configured")
        history_result = refresh_core_history(
            paths,
            TushareCoreAdapter(token),
            start=date.fromisoformat(namespace.start),
            end=date.fromisoformat(namespace.end),
            definition_version=namespace.definition_version,
        )
        return asdict(history_result)
    if namespace.command == "model-activate":
        activated = ModelRepository(paths.database).activate(
            namespace.model,
            explicitly_approved=namespace.confirm,
        )
        return asdict(activated)
    if namespace.command == "model-input-preflight":
        from pring_cycle.material_preflight import preflight_model_inputs

        return preflight_model_inputs(
            paths,
            namespace.model,
            requested_start=namespace.start,
            requested_end=namespace.end,
        )
    if namespace.command == "model-replay":
        from pring_cycle.model_evaluation import replay_models

        evaluation = replay_models(
            paths.database,
            namespace.model,
            namespace.compared_with,
            requested_start=namespace.start,
            requested_end=namespace.end,
        )
        replay = ModelRepository(paths.database).record_replay(
            namespace.model,
            compared_with=namespace.compared_with,
            requested_start=namespace.start,
            requested_end=namespace.end,
            quality_passed=evaluation.quality_passed,
            regression_passed=evaluation.regression_passed,
            performance_passed=evaluation.performance_passed,
            stage_differences=evaluation.stage_differences,
            core_state_differences=evaluation.core_state_differences,
            context_output_differences=evaluation.context_output_differences,
            gaps=evaluation.gaps,
            evaluated_trading_days=evaluation.evaluated_trading_days,
            calendar_hash=evaluation.calendar_hash,
            candidate_state_differences=evaluation.candidate_state_differences,
            candidate_days_differences=evaluation.candidate_days_differences,
            core_output_hash=evaluation.core_output_hash,
            core_output_document=evaluation.core_output_document,
            context_output_hash=evaluation.context_output_hash,
            context_output_document=evaluation.context_output_document,
        )
        return {**asdict(replay), "status": "passed" if replay.passed else "failed"}
    if namespace.command == "model-replay-show":
        return ModelRepository(paths.database).replay_details(namespace.replay_id)
    if namespace.command == "model-acceptance-show":
        return ModelRepository(paths.database).acceptance_details(
            namespace.model, namespace.result_hash
        )
    if namespace.command == "model-source-certify":
        if namespace.candidate_request_hash is not None:
            from pring_cycle.candidate_admission import admit_source_certified_candidate

            return admit_source_certified_candidate(
                paths,
                request_hash=namespace.candidate_request_hash,
                target_business_date=namespace.target_date,
                personal_noncommercial_use_approved=namespace.confirm_personal_noncommercial,
            )
        from pring_cycle.source_certification import create_source_certified_candidate

        return create_source_certified_candidate(
            paths,
            target_business_date=namespace.target_date,
            source_smoke_hashes=tuple(namespace.source_smoke_hash),
            personal_noncommercial_use_approved=namespace.confirm_personal_noncommercial,
        )
    if namespace.command == "model-source-refresh":
        from pring_cycle.source_certification import refresh_source_certified_candidate

        return refresh_source_certified_candidate(
            paths,
            model_version_id=namespace.model,
            target_business_date=namespace.target_date,
        )
    if namespace.command == "model-rollback":
        trading_calendar = tuple(
            line.strip()
            for line in namespace.calendar.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        rolled_back = ModelRepository(paths.database).rollback(
            namespace.model,
            as_of_business_date=namespace.as_of_date,
            trading_calendar=trading_calendar,
            explicitly_confirmed=namespace.confirm,
        )
        return asdict(rolled_back)
    if namespace.command == "run-submit":
        active_model_id = ModelRepository(paths.database).active().model_version_id
        if namespace.model is not None and namespace.model != active_model_id:
            raise ValueError("run_model_is_not_active")
        model_version_id = active_model_id
        submitted = RunRepository(paths.database).submit(
            command_type=namespace.type,
            target_business_date=namespace.target_date,
            client_request_id=namespace.request_id,
            model_version_id=model_version_id,
            system_as_of=(
                datetime.fromisoformat(namespace.as_of) if namespace.as_of else datetime.now(UTC)
            ),
            cutoff_mode="explicit" if namespace.as_of else None,
            release_event_id=namespace.release_event,
            metric_ids=tuple(namespace.metric),
            period=namespace.period,
            source_url=namespace.source_url,
        )
        return asdict(submitted)
    if namespace.command == "runs":
        return {
            "runs": [asdict(item) for item in RunRepository(paths.database).list_runs()],
            "status": "ok",
        }
    if namespace.command == "run-resume":
        resumed = RunRepository(paths.database).resume(
            namespace.run_id,
            client_request_id=namespace.request_id,
            confirm_external_calls=namespace.confirm_external_calls,
        )
        return asdict(resumed)
    if namespace.command == "run-cancel":
        return asdict(RunRepository(paths.database).cancel(namespace.run_id))
    if namespace.command == "schedule":
        repository = RunRepository(paths.database)
        if namespace.enabled is None:
            return repository.schedule()
        return repository.configure_schedule(
            enabled=namespace.enabled,
            requested_by="local-cli",
        )
    if namespace.command == "projection":
        projection = ProjectionSetRepository(paths.database).current()
        return {
            "datasets": projection.datasets,
            "envelope": asdict(projection.envelope),
            "status": "ok",
        }
    if namespace.command == "evidence-ingest":
        source = json.loads(namespace.input.read_text(encoding="utf-8"))
        if not isinstance(source, dict):
            raise ValueError("evidence_input_must_be_object")
        stored = EvidenceRepository(paths.database).append_source_claim(_source_claim_input(source))
        return {**asdict(stored), "status": "stored"}
    if namespace.command == "evidence-query":
        queried = EvidenceRepository(paths.database).query(
            namespace.observation_id,
            mode=AsOfMode(namespace.mode),
            as_of=datetime.fromisoformat(namespace.as_of),
            tolerance=namespace.tolerance,
        )
        return {**asdict(queried), "status": "ok"}
    if namespace.command == "report-generate":
        projection = ProjectionSetRepository(paths.database).current()
        bundle = evidence_bundle_from_projection(projection)
        adapters = (
            ()
            if namespace.deterministic_only
            else (CliReportAdapter("codex_cli"), CliReportAdapter("claude_code_cli"))
        )
        generated = ReportService(
            ReportRepository(paths.database),
            adapters,
        ).generate(bundle, client_request_id=namespace.request_id)
        return asdict(generated)
    if namespace.command == "reports":
        return {
            "reports": [asdict(item) for item in ReportRepository(paths.database).history()],
            "status": "ok",
        }
    if namespace.command == "report-read":
        return asdict(ReportRepository(paths.database).get(namespace.report_id))
    if namespace.command == "cleanup":
        cleaned = MaintenanceRepository(paths.database).cleanup()
        return {**asdict(cleaned), "status": "completed"}
    if namespace.command == "capacity":
        return asdict(capacity_state(namespace.free_bytes))
    if namespace.command == "acceptance":
        from pring_cycle.acceptance import run_v1_acceptance

        return run_v1_acceptance(paths)
    if namespace.command == "rehearse-fixture-recovery":
        from pring_cycle.rehearsals import run_fixture_recovery_rehearsal

        return run_fixture_recovery_rehearsal(paths)
    if namespace.command == "rehearse-real":
        from pring_cycle.rehearsals import run_real_projection_rehearsal

        return run_real_projection_rehearsal(
            paths,
            target_business_date=namespace.target_date,
            dashboard_port=namespace.dashboard_port,
            source_smoke_hashes=tuple(namespace.source_smoke_hash),
        )
    if namespace.command == "cutover-manifest":
        from pring_cycle.cutover import build_cutover_manifest

        return build_cutover_manifest(
            paths,
            acceptance_hash=namespace.acceptance_hash,
            real_rehearsal_hash=namespace.real_rehearsal_hash,
            fixture_rehearsal_hash=namespace.fixture_rehearsal_hash,
            legacy_system_read_only_stopped=namespace.legacy_system_read_only_stopped,
            suite_total_seconds=namespace.suite_total_seconds,
        )
    if namespace.command == "cutover-record":
        from pring_cycle.cutover import record_direct_cutover

        recorded = record_direct_cutover(
            paths,
            manifest_hash=namespace.manifest_hash,
            confirmation=namespace.confirm,
        )
        return {**asdict(recorded), "status": "recorded"}
    if namespace.command == "cutover-status":
        from pring_cycle.cutover import cutover_status

        record = cutover_status(paths)
        return {"cutover": asdict(record) if record is not None else None, "status": "ok"}
    if namespace.command == "source-smoke":
        from pring_cycle.rehearsals import store_source_smoke_result
        from pring_cycle.secrets import parse_data_source_secrets
        from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter

        token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
        if token is None:
            raise ValueError("tushare_not_configured")
        target = date.fromisoformat(namespace.target_date)
        start = target - timedelta(days=280)
        adapter = TushareCoreAdapter(token)
        calendar = adapter.trading_days(start, target)
        expected = calendar[-160:]
        if not expected or expected[-1] != target:
            raise ValueError("target_business_date_not_in_china_calendar")
        results = [
            asdict(
                adapter.smoke(
                    metric_id,
                    start=expected[0],
                    end=expected[-1],
                    expected_business_dates=expected,
                )
            )
            for metric_id in CORE_API_IDENTITIES
        ]
        return store_source_smoke_result(
            paths,
            kind="core",
            result={"network_requests": 4, "results": results, "status": "validated"},
            target_scope={"target_business_date": namespace.target_date},
        )
    if namespace.command == "context-source-smoke":
        from pring_cycle.rehearsals import store_source_smoke_result
        from pring_cycle.secrets import parse_data_source_secrets
        from pring_cycle.tushare_context import (
            TushareContextAdapter,
            smoke_context_sources,
        )

        token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
        if token is None:
            raise ValueError("tushare_not_configured")
        result = asdict(
            smoke_context_sources(
                TushareContextAdapter(token),
                target_business_date=date.fromisoformat(namespace.target_date),
            )
        )
        return store_source_smoke_result(
            paths,
            kind="tushare-context",
            result=result,
            target_scope={"target_business_date": namespace.target_date},
        )
    if namespace.command == "market-source-smoke":
        from pring_cycle.rehearsals import store_source_smoke_result
        from pring_cycle.secrets import parse_data_source_secrets
        from pring_cycle.tushare_context import (
            TushareContextAdapter,
            smoke_market_sources,
        )

        token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
        if token is None:
            raise ValueError("tushare_not_configured")
        result = asdict(
            smoke_market_sources(
                TushareContextAdapter(token),
                target_business_date=date.fromisoformat(namespace.target_date),
            )
        )
        return store_source_smoke_result(
            paths,
            kind="tushare-market",
            result=result,
            target_scope={"target_business_date": namespace.target_date},
        )
    raise ValueError("unsupported_command")


def _active_definition_version(paths: RuntimePaths) -> str:
    from pring_cycle.catalog import METRIC_CATALOG_VERSION
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.models import ModelRepository

    models = ModelRepository(paths.database)
    try:
        manifest = models.manifest(models.active().model_version_id)
    except LookupError:
        return METRIC_CATALOG_VERSION
    return ContextProjectionRules.from_manifest(manifest).metric_catalog_version


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pring-cycle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "init",
        "doctor",
        "secrets-migrate",
        "catalog",
        "models",
        "runs",
        "projection",
        "reports",
        "stage-history",
        "gap-notices",
        "cleanup",
        "rehearse-fixture-recovery",
        "cutover-status",
    ):
        _runtime_parser(subparsers, command)
    subparsers.choices["secrets-migrate"].add_argument(
        "--from",
        dest="source",
        type=Path,
        required=True,
    )
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--runtime-root", type=Path)
    web_parser.add_argument("--port", type=int, default=8050)
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--runtime-root", type=Path)
    for command in ("test", "verify"):
        _runtime_parser(subparsers, command)

    model_accept = _runtime_parser(subparsers, "model-accept")
    model_accept.add_argument("--model", required=True)
    core_history = _runtime_parser(subparsers, "core-history-refresh")
    core_history.add_argument("--start", required=True)
    core_history.add_argument("--end", required=True)
    core_history.add_argument(
        "--definition-version",
        default="metric-catalog-v0001",
    )
    model_activate = _runtime_parser(subparsers, "model-activate")
    model_activate.add_argument("--model", required=True)
    model_activate.add_argument("--confirm", action="store_true")
    model_preflight = _runtime_parser(subparsers, "model-input-preflight")
    model_preflight.add_argument("--model", required=True)
    model_preflight.add_argument("--start", required=True)
    model_preflight.add_argument("--end", required=True)
    model_replay = _runtime_parser(subparsers, "model-replay")
    model_replay.add_argument("--model", required=True)
    model_replay.add_argument("--compared-with", required=True)
    model_replay.add_argument("--start", required=True)
    model_replay.add_argument("--end", required=True)
    replay_show = _runtime_parser(subparsers, "model-replay-show")
    replay_show.add_argument("--replay-id", required=True, type=int)
    acceptance_show = _runtime_parser(subparsers, "model-acceptance-show")
    acceptance_show.add_argument("--model", required=True)
    acceptance_show.add_argument("--result-hash", required=True)
    model_source_certify = _runtime_parser(subparsers, "model-source-certify")
    model_source_certify.add_argument("--target-date", required=True)
    certification_input = model_source_certify.add_mutually_exclusive_group(required=True)
    certification_input.add_argument("--candidate-request-hash")
    certification_input.add_argument(
        "--source-smoke-hash",
        action="append",
    )
    model_source_certify.add_argument(
        "--confirm-personal-noncommercial",
        action="store_true",
    )
    model_source_refresh = _runtime_parser(subparsers, "model-source-refresh")
    model_source_refresh.add_argument("--model", required=True)
    model_source_refresh.add_argument("--target-date", required=True)
    model_rollback = _runtime_parser(subparsers, "model-rollback")
    model_rollback.add_argument("--model", required=True)
    model_rollback.add_argument("--as-of-date", required=True)
    model_rollback.add_argument("--calendar", type=Path, required=True)
    model_rollback.add_argument("--confirm", action="store_true")

    run_submit = _runtime_parser(subparsers, "run-submit")
    run_submit.add_argument(
        "--type",
        choices=("manual_full", "targeted_refresh", "manual_deep_search", "report_generation"),
        default="manual_full",
    )
    run_submit.add_argument("--target-date", required=True)
    run_submit.add_argument("--request-id", required=True)
    run_submit.add_argument("--model")
    run_submit.add_argument(
        "--as-of", help="Fixed SYSTEM cutoff (timezone required); omit for live acquisition"
    )
    run_submit.add_argument("--release-event")
    run_submit.add_argument("--metric", action="append", default=[])
    run_submit.add_argument("--period")
    run_submit.add_argument("--source-url")
    run_resume = _runtime_parser(subparsers, "run-resume")
    run_resume.add_argument("--run-id", required=True)
    run_resume.add_argument("--request-id", required=True)
    run_resume.add_argument("--confirm-external-calls", action="store_true")
    run_cancel = _runtime_parser(subparsers, "run-cancel")
    run_cancel.add_argument("--run-id", required=True)
    schedule = _runtime_parser(subparsers, "schedule")
    schedule_group = schedule.add_mutually_exclusive_group()
    schedule_group.add_argument("--enable", dest="enabled", action="store_true")
    schedule_group.add_argument("--disable", dest="enabled", action="store_false")
    schedule.set_defaults(enabled=None)

    evidence_ingest = _runtime_parser(subparsers, "evidence-ingest")
    evidence_ingest.add_argument("--input", type=Path, required=True)
    fixture_project = _runtime_parser(subparsers, "fixture-project")
    fixture_project.add_argument("--input", type=Path, required=True)
    gap_notice = _runtime_parser(subparsers, "gap-notice")
    gap_notice.add_argument("--assessment-id", required=True)
    gap_notice.add_argument("--request-id", required=True)
    lpr_contract = _runtime_parser(subparsers, "lpr-contract")
    lpr_contract.add_argument("--input", type=Path, required=True)
    lpr_contract.add_argument("--url", required=True)
    lpr_contract.add_argument("--period", required=True)
    lpr_contract.add_argument("--fetched-at", required=True)
    official_context_contract = _runtime_parser(subparsers, "official-context-contract")
    official_context_contract.add_argument("--input", type=Path, required=True)
    official_context_contract.add_argument("--family", required=True)
    official_context_contract.add_argument("--url", required=True)
    official_context_contract.add_argument("--period", required=True)
    official_context_contract.add_argument("--fetched-at", required=True)
    official_context_smoke = _runtime_parser(subparsers, "official-context-smoke")
    official_context_smoke.add_argument("--family", required=True)
    official_context_smoke.add_argument("--url", required=True)
    official_context_smoke.add_argument("--period", required=True)
    source_history_smoke = _runtime_parser(subparsers, "source-history-smoke")
    source_history_smoke.add_argument("--target-date", required=True)
    source_history_smoke.add_argument("--browser-capture-root", type=Path)
    eia_html = _runtime_parser(subparsers, "eia-html-refresh")
    eia_html.add_argument("--series", choices=("RBRTE", "RWTC"), required=True)
    eia_html.add_argument("--start", required=True)
    eia_html.add_argument("--end", required=True)
    eia_html.add_argument("--definition-version", default="metric-catalog-v0001")
    treasury_csv = _runtime_parser(subparsers, "treasury-csv-refresh")
    treasury_csv.add_argument("--start", required=True)
    treasury_csv.add_argument("--end", required=True)
    treasury_csv.add_argument("--definition-version", default="metric-catalog-v0001")
    for command in ("ecb-reference-import", "ecb-reference-refresh"):
        ecb_reference = _runtime_parser(subparsers, command)
        ecb_reference.add_argument("--start", required=True)
        ecb_reference.add_argument("--end", required=True)
        ecb_reference.add_argument("--definition-version", required=True)
        if command == "ecb-reference-import":
            ecb_reference.add_argument("--input", type=Path, required=True)
            ecb_reference.add_argument("--url", required=True)
    eia_contract = _runtime_parser(subparsers, "eia-contract")
    eia_contract.add_argument("--input", type=Path, required=True)
    eia_contract.add_argument("--start", required=True)
    eia_contract.add_argument("--end", required=True)
    eia_smoke = _runtime_parser(subparsers, "eia-smoke")
    eia_smoke.add_argument("--start", required=True)
    eia_smoke.add_argument("--end", required=True)
    lpr_refresh = _runtime_parser(subparsers, "lpr-refresh")
    lpr_refresh.add_argument("--url", required=True)
    lpr_refresh.add_argument("--period", required=True)
    lpr_smoke = _runtime_parser(subparsers, "lpr-smoke")
    lpr_smoke.add_argument("--url", required=True)
    lpr_smoke.add_argument("--period", required=True)
    release_calendar = _runtime_parser(subparsers, "release-calendar")
    release_calendar.add_argument("--period", required=True)
    release_calendar.add_argument("--as-of", required=True)
    release_calendar.add_argument("--holiday", action="append", default=[])
    evidence_query = _runtime_parser(subparsers, "evidence-query")
    evidence_query.add_argument("--observation-id", required=True)
    evidence_query.add_argument(
        "--mode",
        choices=("public_as_of", "system_as_of"),
        required=True,
    )
    evidence_query.add_argument("--as-of", required=True)
    evidence_query.add_argument("--tolerance", type=float, default=0.0)
    report_generate = _runtime_parser(subparsers, "report-generate")
    report_generate.add_argument("--request-id", required=True)
    report_generate.add_argument("--deterministic-only", action="store_true")
    report_read = _runtime_parser(subparsers, "report-read")
    report_read.add_argument("--report-id", required=True)
    capacity = _runtime_parser(subparsers, "capacity")
    capacity.add_argument("--free-bytes", type=int, required=True)
    _runtime_parser(subparsers, "acceptance")
    real_rehearsal = _runtime_parser(subparsers, "rehearse-real")
    real_rehearsal.add_argument("--target-date", required=True)
    real_rehearsal.add_argument("--dashboard-port", type=int, required=True)
    real_rehearsal.add_argument(
        "--source-smoke-hash",
        action="append",
        required=True,
    )
    cutover_manifest = _runtime_parser(subparsers, "cutover-manifest")
    cutover_manifest.add_argument("--acceptance-hash", required=True)
    cutover_manifest.add_argument("--real-rehearsal-hash", required=True)
    cutover_manifest.add_argument("--fixture-rehearsal-hash", required=True)
    cutover_manifest.add_argument("--legacy-system-read-only-stopped", action="store_true")
    # The whole test run's wall clock, reported beside the acceptance artifact's own phases.
    cutover_manifest.add_argument("--suite-total-seconds", type=float, default=None)
    cutover_record = _runtime_parser(subparsers, "cutover-record")
    cutover_record.add_argument("--manifest-hash", required=True)
    cutover_record.add_argument("--confirm", required=True)
    source_smoke = _runtime_parser(subparsers, "source-smoke")
    source_smoke.add_argument("--target-date", required=True)
    context_source_smoke = _runtime_parser(subparsers, "context-source-smoke")
    context_source_smoke.add_argument("--target-date", required=True)
    market_source_smoke = _runtime_parser(subparsers, "market-source-smoke")
    market_source_smoke.add_argument("--target-date", required=True)
    return parser


def _source_claim_input(source: dict[str, Any]) -> SourceClaimInput:
    from pring_cycle.catalog import metric_definition
    from pring_cycle.evidence import EvidenceValueState, SourceClaimInput

    definition = metric_definition(str(source["metric_id"]))
    if definition.priority == "P0":
        raise ValueError("p0_evidence_requires_certified_adapter")
    if source.get("certification_status") == "certified":
        raise ValueError("certified_evidence_requires_certified_adapter")
    dimensions = source["dimensions"]
    if not isinstance(dimensions, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in dimensions.items()
    ):
        raise ValueError("evidence_dimensions_must_be_string_map")
    return SourceClaimInput(
        metric_id=str(source["metric_id"]),
        definition_version=str(source["definition_version"]),
        period_kind=str(source["period_kind"]),
        period_start=str(source["period_start"]),
        period_end=str(source["period_end"]),
        dimensions=dimensions,
        value=float(source["value"]) if source.get("value") is not None else None,
        value_state=EvidenceValueState(str(source["value_state"])),
        unit=str(source["unit"]),
        provider=str(source["provider"]),
        source_reference=str(source["source_reference"]),
        release_event_id=str(source["release_event_id"]),
        release_at=_optional_datetime(source.get("release_at")),
        public_available_at=_optional_datetime(source.get("public_available_at")),
        fetched_at=datetime.fromisoformat(str(source["fetched_at"])),
        available_at=datetime.fromisoformat(str(source["available_at"])),
        certification_status=str(source["certification_status"]),
        quality_status=str(source["quality_status"]),
    )


def _optional_datetime(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value)) if value is not None else None


def _runtime_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command: str,
) -> argparse.ArgumentParser:
    command_parser = subparsers.add_parser(command)
    command_parser.add_argument("--runtime-root", type=Path)
    command_parser.add_argument("--json", action="store_true")
    return command_parser


def _print_document(document: Mapping[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(document, default=str, ensure_ascii=False, sort_keys=True))
        return
    print(f"status={document['status']}")
    for section, value in document.items():
        if section == "status":
            continue
        if isinstance(value, Mapping):
            print(f"{section}=" + ",".join(f"{key}:{item}" for key, item in value.items()))
        else:
            print(f"{section}={value}")
