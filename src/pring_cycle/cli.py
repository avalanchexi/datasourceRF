from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.maintenance import MaintenanceRepository, capacity_state
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import (
    CliReportAdapter,
    ReportRepository,
    ReportService,
    evidence_bundle_from_projection,
)
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import (
    RuntimeNotInitializedError,
    RuntimePaths,
    RuntimePolicyError,
    diagnose_runtime,
    initialize_runtime,
)
from pring_cycle.verification import VerificationError, verify_local_runtime


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
        elif namespace.command == "web":
            from pring_cycle.web import run_web

            run_web(paths, namespace.port)
            return
        elif namespace.command == "worker":
            from pring_cycle.worker import run_worker

            run_worker(paths)
            return
        elif namespace.command in {"test", "verify"}:
            document = verify_local_runtime(paths)
        else:
            document = _v1_command(namespace, paths)
    except (
        KeyError,
        LookupError,
        RuntimeNotInitializedError,
        RuntimePolicyError,
        TypeError,
        ValueError,
        VerificationError,
    ) as error:
        parser.exit(2, f"error: {error}\n")

    _print_document(document, namespace.json)


def _v1_command(namespace: argparse.Namespace, paths: RuntimePaths) -> Mapping[str, object]:
    if namespace.command == "catalog":
        return {
            "catalog_version": METRIC_CATALOG_VERSION,
            "metrics": [asdict(item) for item in metric_catalog()],
            "network_requests": 0,
            "status": "ok",
        }
    if namespace.command == "models":
        return {
            "models": [
                asdict(item) for item in ModelRepository(paths.database).list_versions()
            ],
            "status": "ok",
        }
    if namespace.command == "model-accept":
        acceptance = ModelRepository(paths.database).record_acceptance(
            namespace.model,
            CALIBRATION_BASELINE,
        )
        return {
            **asdict(acceptance),
            "status": "accepted" if acceptance.passed else "rejected",
        }
    if namespace.command == "model-activate":
        activated = ModelRepository(paths.database).activate(
            namespace.model,
            explicitly_approved=namespace.confirm,
        )
        return asdict(activated)
    if namespace.command == "model-replay":
        replay = ModelRepository(paths.database).record_replay(
            namespace.model,
            compared_with=namespace.compared_with,
            requested_start=namespace.start,
            requested_end=namespace.end,
            quality_passed=namespace.quality_passed,
            regression_passed=namespace.regression_passed,
            performance_passed=namespace.performance_passed,
            stage_differences=namespace.stage_differences,
            core_state_differences=namespace.core_state_differences,
            gaps=tuple(namespace.gap),
        )
        return {**asdict(replay), "status": "passed" if replay.passed else "failed"}
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
        model_version_id = (
            namespace.model
            if namespace.model is not None
            else ModelRepository(paths.database).active().model_version_id
        )
        submitted = RunRepository(paths.database).submit(
            command_type=namespace.type,
            target_business_date=namespace.target_date,
            client_request_id=namespace.request_id,
            model_version_id=model_version_id,
            system_as_of=datetime.now(UTC),
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
        stored = EvidenceRepository(paths.database).append_source_claim(
            _source_claim_input(source)
        )
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

        return run_v1_acceptance(
            paths,
            include_process_probe=not namespace.skip_process_probe,
        )
    if namespace.command == "rehearse-fixture-recovery":
        from pring_cycle.rehearsals import run_fixture_recovery_rehearsal

        return run_fixture_recovery_rehearsal(paths)
    if namespace.command == "rehearse-real":
        from pring_cycle.rehearsals import run_real_projection_rehearsal

        return run_real_projection_rehearsal(
            paths,
            target_business_date=namespace.target_date,
        )
    if namespace.command == "cutover-manifest":
        from pring_cycle.cutover import build_cutover_manifest

        return build_cutover_manifest(
            paths,
            acceptance_hash=namespace.acceptance_hash,
            real_rehearsal_hash=namespace.real_rehearsal_hash,
            fixture_rehearsal_hash=namespace.fixture_rehearsal_hash,
            legacy_system_read_only_stopped=namespace.legacy_system_read_only_stopped,
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
        from datetime import date, timedelta

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
        return {"network_requests": 4, "results": results, "status": "validated"}
    raise ValueError("unsupported_command")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pring-cycle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "init",
        "doctor",
        "catalog",
        "models",
        "runs",
        "projection",
        "reports",
        "cleanup",
        "rehearse-fixture-recovery",
        "cutover-status",
    ):
        _runtime_parser(subparsers, command)
    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--runtime-root", type=Path)
    web_parser.add_argument("--port", type=int, default=8050)
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--runtime-root", type=Path)
    for command in ("test", "verify"):
        _runtime_parser(subparsers, command)

    model_accept = _runtime_parser(subparsers, "model-accept")
    model_accept.add_argument("--model", required=True)
    model_activate = _runtime_parser(subparsers, "model-activate")
    model_activate.add_argument("--model", required=True)
    model_activate.add_argument("--confirm", action="store_true")
    model_replay = _runtime_parser(subparsers, "model-replay")
    model_replay.add_argument("--model", required=True)
    model_replay.add_argument("--compared-with", required=True)
    model_replay.add_argument("--start", required=True)
    model_replay.add_argument("--end", required=True)
    model_replay.add_argument("--quality-passed", action="store_true")
    model_replay.add_argument("--regression-passed", action="store_true")
    model_replay.add_argument("--performance-passed", action="store_true")
    model_replay.add_argument("--stage-differences", type=int, default=0)
    model_replay.add_argument("--core-state-differences", type=int, default=0)
    model_replay.add_argument("--gap", action="append", default=[])
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
    evidence_query = _runtime_parser(subparsers, "evidence-query")
    evidence_query.add_argument("--observation-id", required=True)
    evidence_query.add_argument("--mode", choices=tuple(AsOfMode), required=True)
    evidence_query.add_argument("--as-of", required=True)
    evidence_query.add_argument("--tolerance", type=float, default=0.0)
    report_generate = _runtime_parser(subparsers, "report-generate")
    report_generate.add_argument("--request-id", required=True)
    report_generate.add_argument("--deterministic-only", action="store_true")
    report_read = _runtime_parser(subparsers, "report-read")
    report_read.add_argument("--report-id", required=True)
    capacity = _runtime_parser(subparsers, "capacity")
    capacity.add_argument("--free-bytes", type=int, required=True)
    acceptance = _runtime_parser(subparsers, "acceptance")
    acceptance.add_argument("--skip-process-probe", action="store_true")
    real_rehearsal = _runtime_parser(subparsers, "rehearse-real")
    real_rehearsal.add_argument("--target-date", required=True)
    cutover_manifest = _runtime_parser(subparsers, "cutover-manifest")
    cutover_manifest.add_argument("--acceptance-hash", required=True)
    cutover_manifest.add_argument("--real-rehearsal-hash", required=True)
    cutover_manifest.add_argument("--fixture-rehearsal-hash", required=True)
    cutover_manifest.add_argument("--legacy-system-read-only-stopped", action="store_true")
    cutover_record = _runtime_parser(subparsers, "cutover-record")
    cutover_record.add_argument("--manifest-hash", required=True)
    cutover_record.add_argument("--confirm", required=True)
    source_smoke = _runtime_parser(subparsers, "source-smoke")
    source_smoke.add_argument("--target-date", required=True)
    return parser


def _source_claim_input(source: dict[str, Any]) -> SourceClaimInput:
    dimensions = source["dimensions"]
    if not isinstance(dimensions, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in dimensions.items()
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
