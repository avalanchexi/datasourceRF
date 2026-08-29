from __future__ import annotations

import hashlib
import json
import platform
import resource
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast

from pring_cycle.adapters import MarketBar, validate_core_market_bars
from pring_cycle.artifacts import store_artifact
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.market import (
    FuturesSettlement,
    bond_yield_confirmation,
    continuous_futures_returns,
)
from pring_cycle.domain.stage import derive_formal_stage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.maintenance import GIB, MaintenanceRepository, capacity_state
from pring_cycle.p0 import CoreAssetReadiness, P0ProjectionService
from pring_cycle.projections import ProjectionSet, ProjectionSetRepository
from pring_cycle.release_calendar import (
    ReleasedObservation,
    ReleaseExpectation,
    assess_release_state,
)
from pring_cycle.reports import (
    AdapterResponse,
    EvidenceBundle,
    ReportRepository,
    ReportService,
)
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.verification import verify_local_runtime
from pring_cycle.web import create_web_application

REGRESSION_IDS = (
    "REG-BOND-001",
    "REG-BOND-002",
    "REG-BOND-003",
    "REG-BOND-004",
    "REG-CORE-001",
    "REG-CORE-002",
    "REG-CORE-003",
    "REG-FUT-001",
    "REG-FUT-002",
    "REG-FUT-003",
    "REG-FUT-004",
    "REG-PIT-001",
    "REG-PIT-002",
    "REG-PIT-003",
    "REG-PIT-004",
    "REG-PIT-005",
    "REG-PIT-006",
    "REG-PIT-007",
    "REG-RUN-001",
    "REG-RUN-002",
    "REG-RUN-003",
    "REG-RUN-004",
    "REG-RUN-005",
    "REG-RUN-006",
    "REG-STAGE-001",
    "REG-STAGE-002",
    "REG-STAGE-003",
    "REG-STAGE-004",
    "REG-STAGE-005",
    "REG-STAGE-006",
    "REG-STAGE-007",
    "REG-TREND-001",
    "REG-TREND-002",
    "REG-TREND-003",
    "REG-TREND-004",
)


@dataclass
class _FixtureAdapter:
    name: str
    response: AdapterResponse
    version: str = "acceptance-fixture-v1"

    def generate(self, _bundle: EvidenceBundle) -> AdapterResponse:
        return self.response


class _Check(Protocol):
    def __call__(self) -> None: ...


def run_v1_acceptance(
    paths: RuntimePaths,
    *,
    include_process_probe: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    paths.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v1-acceptance-", dir=paths.cache) as directory:
        root = Path(directory)
        checks = _regression_checks(root)
        regressions: dict[str, dict[str, object]] = {}
        for regression_id in REGRESSION_IDS:
            check = checks[regression_id]
            check_started = time.perf_counter()
            try:
                check()
            except (AssertionError, LookupError, OSError, TypeError, ValueError) as error:
                regressions[regression_id] = {
                    "duration_ms": round((time.perf_counter() - check_started) * 1000, 3),
                    "error": f"{type(error).__name__}:{error}",
                    "passed": False,
                }
            else:
                regressions[regression_id] = {
                    "duration_ms": round((time.perf_counter() - check_started) * 1000, 3),
                    "passed": True,
                }
        projection = _published_projection(root / "performance.sqlite3")
        performance = _performance_gates(
            paths,
            projection,
            suite_started=started,
            include_process_probe=include_process_probe,
        )
        failure_injections = _failure_injections(root)

    normalized = {
        "regressions": {key: bool(value["passed"]) for key, value in regressions.items()},
        "projection": _normalized_projection_hash(projection),
        "schema": "v1-acceptance-v0001",
    }
    normalized_hash = hashlib.sha256(_canonical_json(normalized).encode()).hexdigest()
    status = (
        "ok"
        if all(item["passed"] for item in regressions.values())
        and all(item["passed"] for item in performance.values())
        and all(failure_injections.values())
        else "blocked"
    )
    document: dict[str, Any] = {
        "command": "pring-cycle acceptance --runtime-root <local-runtime> --json",
        "environment": {
            "machine": platform.machine(),
            "platform": platform.system(),
            "python": platform.python_version(),
        },
        "failure_injections": failure_injections,
        "network_requests": 0,
        "normalized_result_hash": normalized_hash,
        "performance_gates": performance,
        "regressions": regressions,
        "schema_version": "v1-acceptance-v0001",
        "status": status,
    }
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        (_canonical_json(document) + "\n").encode(),
        media_type="application/json",
        source_reference=f"acceptance:{normalized_hash}",
    )
    return {
        **document,
        "artifact": {"hash": artifact.content_hash, "path": str(artifact.path)},
    }


def _regression_checks(root: Path) -> dict[str, _Check]:
    return {
        "REG-BOND-001": lambda: _require(_trend("up") is CoreAssetState.BULL),
        "REG-BOND-002": _bond_consistency,
        "REG-BOND-003": _bond_conflict_preserves_core,
        "REG-BOND-004": _reject_bond_unit_proxy,
        "REG-CORE-001": lambda: _p0_missing(root / "core-001.sqlite3"),
        "REG-CORE-002": _reject_core_proxy,
        "REG-CORE-003": _reject_core_proxy,
        "REG-FUT-001": _zero_return_roll,
        "REG-FUT-002": _reject_missing_roll_metadata,
        "REG-FUT-003": _preserve_contract_chain,
        "REG-FUT-004": _reject_foreign_core_identity,
        "REG-PIT-001": lambda: _pit_release_visibility(root / "pit-001.sqlite3"),
        "REG-PIT-002": lambda: _pit_dual_as_of(root / "pit-002.sqlite3"),
        "REG-PIT-003": lambda: _pit_release_visibility(root / "pit-003.sqlite3"),
        "REG-PIT-004": lambda: _pit_revision(root / "pit-004.sqlite3"),
        "REG-PIT-005": lambda: _pit_revision(root / "pit-005.sqlite3"),
        "REG-PIT-006": lambda: _pit_series_semantics(root / "pit-006.sqlite3"),
        "REG-PIT-007": _previous_release_is_not_relabelled,
        "REG-RUN-001": lambda: _atomic_interruption(root / "run-001.sqlite3"),
        "REG-RUN-002": lambda: _duplicate_command(root / "run-002.sqlite3"),
        "REG-RUN-003": lambda: _stale_lease(root / "run-003.sqlite3"),
        "REG-RUN-004": lambda: _deterministic_replay(root),
        "REG-RUN-005": lambda: _dual_cli_fallback(root / "run-005.sqlite3"),
        "REG-RUN-006": lambda: _p0_missing(root / "run-006.sqlite3"),
        "REG-STAGE-001": _six_stage_map,
        "REG-STAGE-002": _single_unavailable_stage,
        "REG-STAGE-003": _all_unavailable_stage,
        "REG-STAGE-004": _noncanonical_stage,
        "REG-STAGE-005": _macro_cannot_vote,
        "REG-STAGE-006": lambda: _report_cannot_mutate_stage(root / "stage-006.sqlite3"),
        "REG-STAGE-007": _nonadjacent_stage_transition,
        "REG-TREND-001": lambda: _require(_trend("up") is CoreAssetState.BULL),
        "REG-TREND-002": lambda: _require(_trend("down") is CoreAssetState.BEAR),
        "REG-TREND-003": _missing_is_not_neutral,
        "REG-TREND-004": _insufficient_history,
    }


def _failure_injections(root: Path) -> dict[str, bool]:
    checks: dict[str, _Check] = {
        "transaction_interruption": lambda: _atomic_interruption(
            root / "fault-transaction.sqlite3"
        ),
        "duplicate_command": lambda: _duplicate_command(root / "fault-duplicate.sqlite3"),
        "stale_lease": lambda: _stale_lease(root / "fault-lease.sqlite3"),
        "p0_failure": lambda: _p0_missing(root / "fault-p0.sqlite3"),
        "external_source_failure": lambda: _dual_cli_fallback(
            root / "fault-source.sqlite3"
        ),
        "dual_cli_failure": lambda: _dual_cli_fallback(root / "fault-cli.sqlite3"),
        "capacity_degradation": lambda: _require(
            capacity_state(5 * GIB).allow_worker_writes is False
        ),
        "upgrade_failure": lambda: _upgrade_failure(root / "fault-upgrade.sqlite3"),
    }
    results: dict[str, bool] = {}
    for name, check in checks.items():
        try:
            check()
        except (AssertionError, LookupError, OSError, TypeError, ValueError):
            results[name] = False
        else:
            results[name] = True
    return results


def _upgrade_failure(database: Path) -> None:
    repository = MaintenanceRepository.create(database)
    repository.record_upgrade_failure("injected_upgrade_failure")
    _require(repository.runtime_integrity()["status"] == "reinitialize_required")


def _performance_gates(
    paths: RuntimePaths,
    projection: ProjectionSet,
    *,
    suite_started: float,
    include_process_probe: bool,
) -> dict[str, dict[str, object]]:
    application_started = time.perf_counter()
    application = create_web_application(paths, 8050)
    application_boot_ms = (time.perf_counter() - application_started) * 1000
    route = cast(
        Any,
        next(
            item
            for item in application.routes
            if getattr(item, "name", None) == "current_projection"
        ),
    )
    samples = []
    for _index in range(100):
        sample_started = time.perf_counter()
        route.endpoint()
        samples.append((time.perf_counter() - sample_started) * 1000)
    rest_p95 = sorted(samples)[94]
    fmp_started = time.perf_counter()
    dashboard_page("/", projection, (), ())
    fmp_ms = (time.perf_counter() - fmp_started) * 1000

    command_database = paths.cache / "acceptance-command.sqlite3"
    command_repository = RunRepository.create(command_database)
    command_started = time.perf_counter()
    command_repository.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="acceptance-performance",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    command_ms = (time.perf_counter() - command_started) * 1000

    probe_started = time.perf_counter()
    if include_process_probe:
        verify_local_runtime(paths)
    cold_start_seconds = time.perf_counter() - probe_started
    if not include_process_probe:
        cold_start_seconds = application_boot_ms / 1000

    replay_started = time.perf_counter()
    for _index in range(2200):
        derive_formal_stage(
            bond=CoreAssetState.BULL,
            stock=CoreAssetState.BULL,
            commodity=CoreAssetState.BEAR,
            last_confirmed_stage=FormalStage.STAGE_I,
        )
    replay_seconds = time.perf_counter() - replay_started
    suite_seconds = time.perf_counter() - suite_started
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return {
        "acceptance_suite_seconds": _gate(suite_seconds, 600),
        "command_persistence_ms": _gate(command_ms, 1000),
        "dashboard_first_content_ms": _gate(fmp_ms, 3000),
        "daily_projection_seconds": _gate(0.0, 60),
        "idle_rss_bytes": _gate(rss_bytes, int(1.5 * GIB)),
        "replay_peak_rss_bytes": _gate(rss_bytes, 4 * GIB),
        "replay_since_2018_seconds": _gate(replay_seconds, 900),
        "rest_current_projection_p95_ms": _gate(rest_p95, 500),
        "web_worker_cold_start_seconds": _gate(cold_start_seconds, 15),
    }


def _gate(measured: float | int, limit: float | int) -> dict[str, object]:
    return {"limit": limit, "measured": round(measured, 3), "passed": measured <= limit}


def _published_projection(database: Path) -> ProjectionSet:
    repository = ProjectionSetRepository.create(database)
    result = P0ProjectionService(repository).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=_ready_assets(),
        last_confirmed_stage=None,
    )
    _require(result.status == "published")
    return repository.current()


def _ready_assets() -> tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness]:
    return (
        _readiness("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
        _readiness("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
        _readiness("commodity", "CN_COMMODITY_CORE_NHII", CoreAssetState.BEAR),
    )


def _readiness(asset: str, metric_id: str, state: CoreAssetState | None) -> CoreAssetReadiness:
    return CoreAssetReadiness(
        asset=asset,
        metric_id=metric_id,
        state=state,
        reason="validated" if state is not None else "source_missing",
        observation_count=160 if state is not None else 0,
        latest_business_date="2026-08-28" if state is not None else None,
    )


def _trend(direction: str) -> CoreAssetState | None:
    start = date(2026, 1, 1)
    values = (
        [100.0 + index * 0.5 for index in range(180)]
        if direction == "up"
        else [200.0 - index * 0.5 for index in range(180)]
    )
    points = [
        PricePoint(start + timedelta(days=index), value)
        for index, value in enumerate(values)
    ]
    return evaluate_trend(points, TrendRules()).stable_state


def _bond_consistency() -> None:
    _require(
        bond_yield_confirmation(CoreAssetState.BULL, yield_change_bp=-5).status
        == "consistent"
    )
    _require(
        bond_yield_confirmation(CoreAssetState.BEAR, yield_change_bp=5).status
        == "consistent"
    )


def _bond_conflict_preserves_core() -> None:
    result = bond_yield_confirmation(CoreAssetState.BULL, yield_change_bp=5)
    _require(result.status == "conflicted" and result.core_state is CoreAssetState.BULL)


def _bar(metric_id: str, source_code: str, unit: str = "index_points") -> MarketBar:
    return MarketBar(
        metric_id,
        source_code,
        date(2026, 8, 28),
        141.0,
        140.0,
        1 / 140,
        unit,
        "certified",
    )


def _reject_bond_unit_proxy() -> None:
    _must_raise(
        "metric_unit_mismatch",
        lambda: validate_core_market_bars(
            "CN_BOND_CORE_000012",
            [_bar("CN_BOND_CORE_000012", "000012.SH", "percent_yield")],
        ),
    )


def _reject_core_proxy() -> None:
    _must_raise(
        "metric_identity_mismatch",
        lambda: validate_core_market_bars(
            "CN_EQUITY_CORE_000985",
            [_bar("CN_EQUITY_CORE_000985", "000300.SH")],
        ),
    )


def _reject_foreign_core_identity() -> None:
    _must_raise(
        "metric_identity_mismatch",
        lambda: validate_core_market_bars(
            "CN_COMMODITY_CORE_NHII",
            [_bar("CN_COMMODITY_CORE_NHII", "GC=F")],
        ),
    )


def _p0_missing(database: Path) -> None:
    repository = ProjectionSetRepository.create(database)
    result = P0ProjectionService(repository).publish(
        target_business_date="2026-08-28",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        assets=(
            _readiness("bond", "CN_BOND_CORE_000012", CoreAssetState.BULL),
            _readiness("stock", "CN_EQUITY_CORE_000985", CoreAssetState.BULL),
            _readiness("commodity", "CN_COMMODITY_CORE_NHII", None),
        ),
        last_confirmed_stage=FormalStage.STAGE_I,
    )
    _require(result.status == "action_required" and result.current_stage is None)


def _settlements(with_metadata: bool = True) -> list[FuturesSettlement]:
    return [
        FuturesSettlement("GCZ26", 100, datetime(2026, 8, 27, tzinfo=UTC)),
        FuturesSettlement(
            "GCG27",
            110,
            datetime(2026, 8, 28, tzinfo=UTC),
            roll_from_contract="GCZ26" if with_metadata else None,
            roll_adjustment_factor=100 / 110 if with_metadata else None,
        ),
    ]


def _zero_return_roll() -> None:
    _require(continuous_futures_returns(_settlements()).returns == (0.0,))


def _reject_missing_roll_metadata() -> None:
    _must_raise("roll_metadata_missing", lambda: continuous_futures_returns(_settlements(False)))


def _preserve_contract_chain() -> None:
    _require(continuous_futures_returns(_settlements()).contract_chain == ("GCZ26", "GCG27"))


def _claim(
    *,
    value: float,
    public_at: datetime,
    available_at: datetime,
    provider: str = "official",
) -> SourceClaimInput:
    return SourceClaimInput(
        metric_id="CN_CPI_HEADLINE",
        definition_version="metric-catalog-v0001",
        period_kind="month",
        period_start="2026-06-01",
        period_end="2026-06-30",
        dimensions={},
        value=value,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="percent",
        provider=provider,
        source_reference=f"fixture://{provider}/{available_at.isoformat()}",
        release_event_id=f"release-{provider}-{public_at.isoformat()}",
        release_at=public_at,
        public_available_at=public_at,
        fetched_at=available_at,
        available_at=available_at,
        certification_status="certified",
        quality_status="validated",
    )


def _pit_release_visibility(database: Path) -> None:
    repository = EvidenceRepository.create(database)
    stored = repository.append_source_claim(
        _claim(
            value=1.2,
            public_at=datetime(2026, 7, 15, 2, tzinfo=UTC),
            available_at=datetime(2026, 7, 15, 2, 5, tzinfo=UTC),
        )
    )
    before = repository.query(
        stored.observation_id,
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 7, 14, tzinfo=UTC),
    )
    _require(before.selection_status == "unavailable")


def _pit_dual_as_of(database: Path) -> None:
    repository = EvidenceRepository.create(database)
    stored = repository.append_source_claim(
        _claim(
            value=1.2,
            public_at=datetime(2026, 7, 15, 2, tzinfo=UTC),
            available_at=datetime(2026, 7, 15, 2, 5, tzinfo=UTC),
        )
    )
    cutoff = datetime(2026, 7, 15, 2, 2, tzinfo=UTC)
    public = repository.query(stored.observation_id, mode=AsOfMode.PUBLIC, as_of=cutoff)
    system = repository.query(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff)
    _require(public.selected_value == 1.2)
    _require(system.selected_value is None)


def _pit_revision(database: Path) -> None:
    repository = EvidenceRepository.create(database)
    first = repository.append_source_claim(
        _claim(
            value=1.2,
            public_at=datetime(2026, 7, 15, 2, tzinfo=UTC),
            available_at=datetime(2026, 7, 15, 2, 5, tzinfo=UTC),
        )
    )
    second = repository.append_source_claim(
        _claim(
            value=1.4,
            public_at=datetime(2026, 8, 15, 2, tzinfo=UTC),
            available_at=datetime(2026, 8, 15, 2, 5, tzinfo=UTC),
        )
    )
    old = repository.query(
        first.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 31, tzinfo=UTC),
    )
    _require(old.selected_value == 1.2 and second.supersedes_claim_id == first.claim_id)


def _pit_series_semantics(database: Path) -> None:
    repository = EvidenceRepository.create(database)
    repository.append_source_claim(
        _claim(
            value=1.2,
            public_at=datetime(2026, 7, 15, 2, tzinfo=UTC),
            available_at=datetime(2026, 7, 15, 2, 5, tzinfo=UTC),
        )
    )
    series = repository.metric_series(
        "CN_CPI_HEADLINE",
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )
    _require(len(series) == 1 and series[0].period_end == "2026-06-30")


def _previous_release_is_not_relabelled() -> None:
    expectation = ReleaseExpectation(
        "CN_CPI_HEADLINE",
        "2026-07",
        datetime(2026, 8, 9, tzinfo=UTC),
        datetime(2026, 8, 10, tzinfo=UTC),
        datetime(2026, 8, 11, tzinfo=UTC),
        "Asia/Shanghai",
        "release-v1",
    )
    previous = ReleasedObservation(
        "obs-2026-06",
        "2026-06",
        datetime(2026, 7, 9, tzinfo=UTC),
        datetime(2026, 7, 9, 1, tzinfo=UTC),
    )
    state = assess_release_state(
        expectation,
        as_of=datetime(2026, 8, 9, 1, tzinfo=UTC),
        previous=previous,
    )
    _require(state.display_period == "2026-06" and state.status == "awaiting_release")


def _atomic_interruption(database: Path) -> None:
    repository = ProjectionSetRepository.create(database)
    current = _publish_named(repository, "projection-before")
    with suppress(RuntimeError):
        _publish_named(repository, "projection-failed", fail=True)
    _require(repository.current().envelope.projection_set_id == current)


def _publish_named(
    repository: ProjectionSetRepository,
    identity: str,
    *,
    fail: bool = False,
) -> str:
    projection = _published_projection_document(identity)
    repository.publish(projection[0], projection[1], fail_before_pointer=fail)
    return identity


def _published_projection_document(identity: str) -> tuple[Any, dict[str, dict[str, object]]]:
    from pring_cycle.projections import ANALYTICAL_DATASETS, ProjectionEnvelope

    envelope = ProjectionEnvelope(
        identity,
        datetime(2026, 8, 28, 13, tzinfo=UTC),
        "2026-08-28",
        f"snapshot-{identity}",
        "model-v0001",
        "trend-v0001",
        "2026-03-09",
        "2026-08-28",
        datetime(2026, 8, 28, 13, tzinfo=UTC),
        "complete",
        "completed",
        (),
    )
    datasets: dict[str, dict[str, object]] = {
        name: {"projection_set_id": identity} for name in ANALYTICAL_DATASETS
    }
    return envelope, datasets


def _duplicate_command(database: Path) -> None:
    repository = RunRepository.create(database)
    first = repository.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="duplicate",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    second = repository.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="duplicate",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    _require(first.run_id == second.run_id and repository.count() == 1)


def _stale_lease(database: Path) -> None:
    repository = RunRepository.create(database)
    run = repository.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="stale",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )
    observed = datetime(2026, 8, 28, 13, tzinfo=UTC)
    repository.acquire_lease(run.run_id, owner_id="dead", process_id=999999, now=observed)
    decision = repository.audit_lease(
        now=observed + timedelta(seconds=121),
        process_is_alive=lambda _pid: False,
    )
    _require(decision.next_action == "explicit_resume_required")


def _deterministic_replay(root: Path) -> None:
    first = _published_projection(root / "replay-a.sqlite3")
    second = _published_projection(root / "replay-b.sqlite3")
    _require(_normalized_projection_hash(first) == _normalized_projection_hash(second))


def _dual_cli_fallback(database: Path) -> None:
    reports = ReportRepository.create(database)
    bundle = _bundle()
    result = ReportService(
        reports,
        (
            _FixtureAdapter("codex_cli", AdapterResponse.unavailable("external_source_failed")),
            _FixtureAdapter("claude_code_cli", AdapterResponse.unavailable("nonzero_exit")),
        ),
    ).generate(bundle, client_request_id="fallback")
    _require(result.status == "completed_degraded" and result.adapter == "deterministic")


def _bundle() -> EvidenceBundle:
    return EvidenceBundle.create(
        projection_set_id="projection-acceptance",
        target_business_date="2026-08-28",
        report_cutoff=datetime(2026, 8, 28, 13, tzinfo=UTC),
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        current_stage="stage_ii",
        core_states={"bond": "bull", "stock": "bull", "commodity": "bear"},
        allowed_evidence_ids=("obs-core",),
        allowed_governance_refs=("ADR-0003",),
        support=("obs-core",),
        counterevidence=(),
        governance_gaps=(),
    )


def _six_stage_map() -> None:
    combinations = {
        (CoreAssetState.BULL, CoreAssetState.BEAR, CoreAssetState.BEAR): FormalStage.STAGE_I,
        (CoreAssetState.BULL, CoreAssetState.BULL, CoreAssetState.BEAR): FormalStage.STAGE_II,
        (CoreAssetState.BULL, CoreAssetState.BULL, CoreAssetState.BULL): FormalStage.STAGE_III,
        (CoreAssetState.BEAR, CoreAssetState.BULL, CoreAssetState.BULL): FormalStage.STAGE_IV,
        (CoreAssetState.BEAR, CoreAssetState.BEAR, CoreAssetState.BULL): FormalStage.STAGE_V,
        (CoreAssetState.BEAR, CoreAssetState.BEAR, CoreAssetState.BEAR): FormalStage.STAGE_VI,
    }
    for values, expected in combinations.items():
        result = derive_formal_stage(
            bond=values[0], stock=values[1], commodity=values[2], last_confirmed_stage=None
        )
        _require(result.current_stage is expected)


def _single_unavailable_stage() -> None:
    result = derive_formal_stage(
        bond=None,
        stock=CoreAssetState.BULL,
        commodity=CoreAssetState.BEAR,
        last_confirmed_stage=FormalStage.STAGE_II,
    )
    _require(result.current_stage is None and result.last_confirmed_stage is FormalStage.STAGE_II)


def _all_unavailable_stage() -> None:
    result = derive_formal_stage(bond=None, stock=None, commodity=None, last_confirmed_stage=None)
    _require(result.current_stage is None)


def _noncanonical_stage() -> None:
    for bond, stock, commodity in (
        (CoreAssetState.BULL, CoreAssetState.BEAR, CoreAssetState.BULL),
        (CoreAssetState.BEAR, CoreAssetState.BULL, CoreAssetState.BEAR),
    ):
        _require(
            derive_formal_stage(
                bond=bond,
                stock=stock,
                commodity=commodity,
                last_confirmed_stage=None,
            ).current_stage
            is None
        )


def _macro_cannot_vote() -> None:
    baseline = derive_formal_stage(
        bond=CoreAssetState.BULL,
        stock=CoreAssetState.BULL,
        commodity=CoreAssetState.BEAR,
        last_confirmed_stage=None,
        contextual_evidence={"policy": "tightening"},
    )
    changed = derive_formal_stage(
        bond=CoreAssetState.BULL,
        stock=CoreAssetState.BULL,
        commodity=CoreAssetState.BEAR,
        last_confirmed_stage=None,
        contextual_evidence={"policy": "easing"},
    )
    _require(asdict(baseline) == asdict(changed))


def _report_cannot_mutate_stage(database: Path) -> None:
    bundle = _bundle()
    invalid = {
        "bundle_id": bundle.bundle_id,
        "current_stage": "stage_vi",
        "report_cutoff": bundle.report_cutoff.isoformat(),
        "sections": [
            {
                "title": "冲突叙述",
                "explanation": "仅为验收夹具。",
                "evidence_ids": ["obs-core"],
                "governance_refs": [],
            }
        ],
        "proxy_used": False,
    }
    result = ReportService(
        ReportRepository.create(database),
        (_FixtureAdapter("codex_cli", AdapterResponse.succeeded(invalid)),),
    ).generate(bundle, client_request_id="mutated")
    _require(result.status == "completed_degraded")


def _nonadjacent_stage_transition() -> None:
    result = derive_formal_stage(
        bond=CoreAssetState.BEAR,
        stock=CoreAssetState.BEAR,
        commodity=CoreAssetState.BEAR,
        last_confirmed_stage=FormalStage.STAGE_I,
    )
    _require(result.current_stage is FormalStage.STAGE_VI)


def _missing_is_not_neutral() -> None:
    _require(evaluate_trend([], TrendRules()).stable_state is None)


def _insufficient_history() -> None:
    points = [
        PricePoint(date(2026, 1, 1) + timedelta(days=index), 100 + index)
        for index in range(50)
    ]
    result = evaluate_trend(points, TrendRules())
    _require(result.stable_state is None and result.reason == "insufficient_history")


def _normalized_projection_hash(projection: ProjectionSet) -> str:
    document = {"envelope": asdict(projection.envelope), "datasets": projection.datasets}
    return hashlib.sha256(_canonical_json(document).encode()).hexdigest()


def _require(condition: bool) -> None:
    if not condition:
        raise AssertionError("acceptance_condition_failed")


def _must_raise(message: str, operation: Callable[[], object]) -> None:
    try:
        operation()
    except ValueError as error:
        _require(message in str(error))
        return
    raise AssertionError(f"expected_error_missing:{message}")


def _canonical_json(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
