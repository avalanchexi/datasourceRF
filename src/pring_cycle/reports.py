from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pring_cycle.batches import add_batch_columns, current_batch_id
from pring_cycle.projections import ProjectionSet
from pring_cycle.storage import database_connection

REPORT_SCHEMA_VERSION = "report-schema-v0004"
PROMPT_CONTRACT_VERSION = "report-prompt-v0004"


@dataclass(frozen=True)
class ReportInput:
    """The verified results an AI report may explain (ADR-0027).

    Each result carries only its value, the name of its data source and whether it is
    anomalous (carried forward, gap, lagging, conflict). No evidence rows, observation
    series or evidence identifiers: tracing is the projection's and the batch's job.
    ``conclusions`` is what the AI must echo unchanged; ``gap_list`` is kept for the
    report reader and is not sent to the AI, which sees the gap summary instead.
    It is stored in the ``evidence_bundle`` table under ``bundle_id``, as before.
    """

    bundle_id: str
    projection_set_id: str
    target_business_date: str
    report_cutoff: datetime
    system_as_of: datetime
    model_version_id: str
    trend_rule_version: str
    current_stage: str | None
    stage_reason: str
    core_states: dict[str, str]
    conclusions: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    gap_list: list[Any] = field(default_factory=list)
    schema_version: str = REPORT_SCHEMA_VERSION
    prompt_version: str = PROMPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_set_id: str,
        target_business_date: str,
        report_cutoff: datetime,
        system_as_of: datetime,
        model_version_id: str,
        trend_rule_version: str,
        current_stage: str | None,
        stage_reason: str,
        core_states: dict[str, str],
        conclusions: dict[str, Any] | None = None,
        results: dict[str, Any] | None = None,
        gap_list: list[Any] | None = None,
    ) -> ReportInput:
        identity = {
            "projection_set_id": projection_set_id,
            "target_business_date": target_business_date,
            "report_cutoff": report_cutoff.isoformat(),
            "system_as_of": system_as_of.isoformat(),
            "model_version_id": model_version_id,
            "trend_rule_version": trend_rule_version,
            "current_stage": current_stage,
            "stage_reason": stage_reason,
            "core_states": core_states,
            "conclusions": conclusions or {},
            "results": results or {},
            "gap_list": gap_list or [],
            "schema_version": REPORT_SCHEMA_VERSION,
            "prompt_version": PROMPT_CONTRACT_VERSION,
        }
        return cls(
            bundle_id="bundle-" + _hash_document(identity)[:20],
            projection_set_id=projection_set_id,
            target_business_date=target_business_date,
            report_cutoff=report_cutoff,
            system_as_of=system_as_of,
            model_version_id=model_version_id,
            trend_rule_version=trend_rule_version,
            current_stage=current_stage,
            stage_reason=stage_reason,
            core_states=core_states,
            conclusions=conclusions or {},
            results=results or {},
            gap_list=gap_list or [],
        )

    def document(self) -> dict[str, Any]:
        document = asdict(self)
        document["report_cutoff"] = self.report_cutoff.isoformat()
        document["system_as_of"] = self.system_as_of.isoformat()
        return document

    def prompt_document(self) -> dict[str, Any]:
        """What the AI is given: everything but the reader's full gap list."""
        document = self.document()
        del document["gap_list"]
        return document

    def deterministic_skeleton(self) -> dict[str, Any]:
        return {
            "report_identity": {
                "bundle_id": self.bundle_id,
                "projection_set_id": self.projection_set_id,
                "target_business_date": self.target_business_date,
                "report_cutoff": self.report_cutoff.isoformat(),
                "model_version_id": self.model_version_id,
                "trend_rule_version": self.trend_rule_version,
            },
            "formal_stage_basis": {
                "current_stage": self.current_stage,
                "stage_reason": self.stage_reason,
                "classification_source": "three_core_price_states_only",
            },
            "core_states": dict(self.core_states),
            "conclusions": dict(self.conclusions),
            "verified_results": dict(self.results),
            "gap_list": list(self.gap_list),
            "core_carry_forward": list(self.results.get("core_carry_forward", [])),
        }


# Which macro and inventory conclusions the report states, and the projection sections
# whose rows feed each one (for its source names and anomalies).
_MACRO_CONCLUSIONS = {
    "policy_direction": ("policy_action", "transmission"),
    "credit_response": ("credit",),
    "overheat_state": ("overheat",),
    "price_pressure": ("price_chain",),
}
_CORE_SOURCE_LABEL = "三核心价格状态"


def report_input_from_projection(projection: ProjectionSet) -> ReportInput:
    envelope = projection.envelope
    overview = projection.datasets["cycle_overview"]
    current_stage = overview.get("current_stage")
    stage_reason = overview.get("stage_reason")
    if current_stage is None and stage_reason not in {
        "noncanonical_combination",
        "core_data_pending",
    }:
        raise ValueError("formal_stage_required_for_report")
    if current_stage is not None and not isinstance(current_stage, str):
        raise ValueError("formal_stage_required_for_report")
    if not isinstance(stage_reason, str):
        raise ValueError("stage_reason_required_for_report")
    assets_value = projection.datasets["core_assets"].get("assets")
    if not isinstance(assets_value, list):
        raise ValueError("core_asset_projection_required_for_report")
    for item in assets_value:
        if not isinstance(item, dict):
            raise ValueError("core_asset_projection_required_for_report")
        observation_count = item.get("observation_count")
        observation_ids = item.get("observation_version_ids")
        exact_120_required = envelope.model_version_id.startswith(("model-v0010-", "model-v0011-"))
        if (
            not isinstance(observation_count, int)
            or (observation_count != 120 if exact_120_required else observation_count > 120)
            or not isinstance(observation_ids, list)
            or (len(observation_ids) != 120 if exact_120_required else len(observation_ids) > 120)
            or (
                exact_120_required
                and item.get("evidence_window_start") != envelope.evidence_window_start
            )
        ):
            raise ValueError(
                "report_evidence_window_must_equal_120_days"
                if exact_120_required
                else "report_evidence_window_exceeds_120_days"
            )
    core_states = {
        str(item["asset"]): str(item["state"])
        for item in assets_value
        if isinstance(item, dict) and "asset" in item and "state" in item
    }
    if set(core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("core_asset_projection_required_for_report")
    macro = projection.datasets["macro"]
    inventory = projection.datasets["inventory"]
    history = projection.datasets["stage_history"].get("events")
    latest_history = (
        next(
            (
                item
                for item in reversed(history)
                if isinstance(item, dict)
                and item.get("projection_set_id") == envelope.projection_set_id
            ),
            None,
        )
        if isinstance(history, list)
        else None
    )
    carried = [str(asset) for asset in _list(overview.get("core_carry_forward"))]
    gap_list = [item for item in _list(overview.get("gap_list")) if isinstance(item, dict)]
    conclusions: dict[str, Any] = {
        name: _text_or_none(macro.get(name)) for name in _MACRO_CONCLUSIONS
    }
    conclusions["inventory_quadrant"] = _text_or_none(inventory.get("quadrant"))
    results: dict[str, Any] = {
        "formal_stage": {
            "value": current_stage,
            "reason": stage_reason,
            "last_confirmed_stage": overview.get("last_confirmed_stage"),
            "change": latest_history.get("event_kind") if latest_history else None,
            "source": _CORE_SOURCE_LABEL,
            "anomaly": [f"carried_forward:{asset}" for asset in carried],
        },
        "core_assets": [_core_result(item, carried) for item in assets_value],
        **{
            name: _conclusion_result(
                conclusions[name],
                [row for section in sections for row in _section_rows(macro.get(section))],
            )
            for name, sections in _MACRO_CONCLUSIONS.items()
        },
        "inventory_quadrant": _conclusion_result(
            conclusions["inventory_quadrant"],
            [
                row
                for card in _list(inventory.get("cards"))
                if isinstance(card, dict)
                for row in _section_rows(card)
            ],
        ),
        "core_carry_forward": carried,
        "gap_summary": _gap_summary(gap_list),
    }
    return ReportInput.create(
        projection_set_id=envelope.projection_set_id,
        target_business_date=envelope.target_business_date,
        report_cutoff=envelope.system_as_of,
        system_as_of=envelope.system_as_of,
        model_version_id=envelope.model_version_id,
        trend_rule_version=envelope.trend_rule_version,
        current_stage=current_stage,
        stage_reason=stage_reason,
        core_states=core_states,
        conclusions=conclusions,
        results=results,
        gap_list=gap_list,
    )


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _core_result(item: dict[str, Any], carried: list[str]) -> dict[str, Any]:
    from pring_cycle.freshness import FRESHNESS_REGISTRY

    metric_id = str(item.get("metric_id"))
    rule = FRESHNESS_REGISTRY.get(metric_id)
    return {
        "asset": item["asset"],
        "value": item["state"],
        "metric_id": metric_id,
        "latest_business_date": item.get("latest_business_date"),
        "candidate_30d": item.get("candidate_30d"),
        "candidate_days": item.get("candidate_days"),
        "source": rule.source if rule is not None else None,
        "anomaly": ["carried_forward"] if item["asset"] in carried else [],
    }


def _section_rows(section: object) -> list[dict[str, Any]]:
    rows = section.get("evidence") if isinstance(section, dict) else None
    return [row for row in rows or [] if isinstance(row, dict)]


def _conclusion_result(value: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """A conclusion's value, the sources its inputs came from and what is anomalous."""
    sources: set[str] = set()
    anomalies: list[str] = []
    for row in rows:
        metric_id = str(row.get("metric_id"))
        for claim in row.get("claims") or []:
            if isinstance(claim, dict) and claim.get("selected") and claim.get("provider"):
                sources.add(str(claim["provider"]))
        if row.get("formula_version") and row.get("status") in {"current", "available"}:
            sources.add("derived")
        status = row.get("status")
        if status == "missing":
            anomalies.append(f"gap:{metric_id}")
        elif status == "stale":
            anomalies.append(f"lagging:{metric_id}")
        elif status == "conflict":
            anomalies.append(f"conflict:{metric_id}")
    if value == "conflict":
        anomalies.append("conflict")
    return {
        "value": value,
        "source": sorted(sources),
        "anomaly": sorted(dict.fromkeys(anomalies)),
    }


def _gap_summary(gap_list: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for gap in gap_list:
        category = str(gap.get("category"))
        counts[category] = counts.get(category, 0) + 1
    return {
        "counts": dict(sorted(counts.items())),
        "p0_p1": [
            {
                "metric_id": gap.get("metric_id"),
                "priority": gap.get("priority"),
                "category": gap.get("category"),
            }
            for gap in gap_list
            if gap.get("priority") in {"P0", "P1"}
        ],
    }


@dataclass(frozen=True)
class AdapterResponse:
    status: str
    document: dict[str, Any] | None
    error_classification: str | None
    tool_events: int
    process_audit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def succeeded(cls, document: dict[str, Any], *, tool_events: int = 0) -> AdapterResponse:
        return cls("succeeded", document, None, tool_events)

    @classmethod
    def unavailable(cls, classification: str) -> AdapterResponse:
        return cls("unavailable", None, classification, 0)


class ReportAdapter(Protocol):
    name: str
    version: str

    def generate(self, bundle: ReportInput) -> AdapterResponse: ...


@dataclass(frozen=True)
class ReportGenerationResult:
    report_snapshot_id: str
    status: str
    adapter: str
    version: int


@dataclass(frozen=True)
class ReportSnapshot:
    report_snapshot_id: str
    projection_set_id: str
    target_business_date: str
    version: int
    status: str
    adapter: str
    current_stage: str | None
    bundle_id: str
    bundle_hash: str
    model_version_id: str
    schema_version: str
    prompt_version: str
    report_cutoff: datetime
    system_as_of: datetime
    created_at: datetime
    duration_ms: int
    body_retained: bool
    body: dict[str, Any]
    explanation_verification: dict[str, Any] = field(default_factory=dict)
    input_schema_version: str = "not_recorded"
    input_prompt_version: str = "not_recorded"


@dataclass(frozen=True)
class ReportAttempt:
    adapter: str
    adapter_version: str
    outcome: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    tool_events: int
    output_hash: str | None
    process_audit: dict[str, Any] = field(default_factory=dict)


class ReportRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ReportRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_REPORT_SCHEMA)
            upgrade_report_snapshot_nullable_stage(connection)
            upgrade_report_process_audit(connection)
            add_batch_columns(connection)
        return repository

    def by_client_request(self, client_request_id: str) -> ReportSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                _REPORT_SNAPSHOT_SELECT + " WHERE report_snapshot.client_request_id=?",
                (client_request_id,),
            ).fetchone()
        return self._with_runtime_metadata(_report_snapshot(row)) if row is not None else None

    def next_version(self, target_business_date: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 FROM report_snapshot
                WHERE target_business_date=?
                """,
                (target_business_date,),
            ).fetchone()
        return int(row[0]) if row is not None else 1

    def save_bundle(self, bundle: ReportInput) -> str:
        from pring_cycle.source_contract_review import require_stored_model_source_contract

        document_json = _canonical_json(bundle.document())
        bundle_hash = hashlib.sha256(document_json.encode()).hexdigest()
        with self._connect() as connection:
            require_stored_model_source_contract(connection, bundle.model_version_id)
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_bundle(
                    bundle_id, bundle_hash, projection_set_id, document_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.bundle_id,
                    bundle_hash,
                    bundle.projection_set_id,
                    document_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return bundle_hash

    def record_attempt(
        self,
        report_snapshot_id: str,
        *,
        adapter: str,
        adapter_version: str,
        outcome: str,
        started_at: datetime,
        completed_at: datetime,
        tool_events: int,
        output_hash: str | None,
        process_audit: dict[str, Any] | None = None,
        elapsed_ms: int | None = None,
        report_elapsed_ms: int | None = None,
    ) -> None:
        if started_at.tzinfo is None or completed_at.tzinfo is None:
            raise ValueError("report_attempt_times_must_be_timezone_aware")
        audit = dict(process_audit or {})
        # Provider metadata cannot replace the report service's measured timing.
        audit.pop("timing", None)
        if elapsed_ms is not None:
            if (
                type(elapsed_ms) is not int
                or elapsed_ms < 0
                or type(report_elapsed_ms) is not int
                or report_elapsed_ms < elapsed_ms
            ):
                raise ValueError("report_attempt_elapsed_time_invalid")
            audit["timing"] = {
                "basis": "monotonic",
                "elapsed_ms": elapsed_ms,
                "report_elapsed_ms": report_elapsed_ms,
                "clock_went_backwards": completed_at < started_at,
            }
        elif report_elapsed_ms is not None:
            raise ValueError("report_attempt_elapsed_time_invalid")
        elif completed_at < started_at:
            raise ValueError("report_attempt_time_order_invalid")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO report_attempt(
                    report_snapshot_id, adapter, adapter_version, started_at,
                    completed_at, outcome, tool_events, output_hash, process_audit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_snapshot_id,
                    adapter,
                    adapter_version,
                    started_at.astimezone(UTC).isoformat(),
                    completed_at.astimezone(UTC).isoformat(),
                    outcome,
                    tool_events,
                    output_hash,
                    _canonical_json(audit),
                ),
            )

    def save_snapshot(
        self,
        *,
        report_snapshot_id: str,
        client_request_id: str,
        bundle: ReportInput,
        bundle_hash: str,
        version: int,
        status: str,
        adapter: str,
        body: dict[str, Any],
    ) -> ReportSnapshot:
        from pring_cycle.source_contract_review import require_stored_model_source_contract

        body_json = _canonical_json(body)
        with self._connect() as connection:
            require_stored_model_source_contract(connection, bundle.model_version_id)
            connection.execute(
                """
                INSERT INTO report_snapshot(
                    report_snapshot_id, client_request_id, projection_set_id,
                    target_business_date, version, status, adapter, current_stage,
                    bundle_id, bundle_hash, model_version_id, schema_version,
                    prompt_version, body_json, body_retained, created_at, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    report_snapshot_id,
                    client_request_id,
                    bundle.projection_set_id,
                    bundle.target_business_date,
                    version,
                    status,
                    adapter,
                    bundle.current_stage,
                    bundle.bundle_id,
                    bundle_hash,
                    bundle.model_version_id,
                    REPORT_SCHEMA_VERSION,
                    PROMPT_CONTRACT_VERSION,
                    body_json,
                    datetime.now(UTC).isoformat(),
                    current_batch_id(),
                ),
            )
        return self.get(report_snapshot_id)

    def get(self, report_snapshot_id: str) -> ReportSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                _REPORT_SNAPSHOT_SELECT + " WHERE report_snapshot.report_snapshot_id=?",
                (report_snapshot_id,),
            ).fetchone()
        if row is None:
            raise LookupError("report_snapshot_not_found")
        return self._with_runtime_metadata(_report_snapshot(row))

    def history(self) -> tuple[ReportSnapshot, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                _REPORT_SNAPSHOT_SELECT
                + """
                ORDER BY target_business_date DESC, version DESC
                """
            ).fetchall()
        return tuple(self._with_runtime_metadata(_report_snapshot(row)) for row in rows)

    def attempts(self, report_snapshot_id: str) -> tuple[ReportAttempt, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM report_attempt WHERE report_snapshot_id=?
                ORDER BY attempt_id
                """,
                (report_snapshot_id,),
            ).fetchall()
        return tuple(_report_attempt(row) for row in rows)

    def attempts_for_bundle(self, bundle_id: str) -> tuple[ReportAttempt, ...]:
        with self._connect() as connection:
            if "process_audit_json" not in {
                str(row[1]) for row in connection.execute("PRAGMA table_info(report_attempt)")
            }:
                return ()
            rows = connection.execute(
                "SELECT * FROM report_attempt "
                "WHERE json_extract(process_audit_json, '$.bundle_id')=? "
                "ORDER BY attempt_id",
                (bundle_id,),
            ).fetchall()
        return tuple(_report_attempt(row) for row in rows)

    def record_explanation_review(
        self,
        report_snapshot_id: str,
        *,
        output_hash: str,
        reviewer: str,
        sections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from pring_cycle.report_review import record_explanation_review

        with self._connect() as connection:
            return record_explanation_review(
                connection,
                report_snapshot_id,
                output_hash=output_hash,
                reviewer=reviewer,
                sections=sections,
            )

    def explanation_reviews(self, report_snapshot_id: str) -> tuple[dict[str, Any], ...]:
        from pring_cycle.report_review import explanation_reviews

        with self._connect() as connection:
            return explanation_reviews(connection, report_snapshot_id)

    def _with_runtime_metadata(self, snapshot: ReportSnapshot) -> ReportSnapshot:
        reviews = self.explanation_reviews(snapshot.report_snapshot_id)
        attempts = self.attempts(snapshot.report_snapshot_id)
        measured_duration = (
            _timing_duration(attempts[-1].process_audit, "report_elapsed_ms") if attempts else None
        )
        status = (
            reviews[-1]
            if reviews
            else snapshot.body.get(
                "explanation_verification",
                {
                    "status": "not_recorded"
                    if snapshot.adapter != "deterministic"
                    else "unavailable",
                    "semantic_support": "not_reviewed",
                },
            )
        )
        return replace(
            snapshot,
            explanation_verification=status,
            duration_ms=(
                measured_duration if measured_duration is not None else snapshot.duration_ms
            ),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection


class ReportService:
    def __init__(self, repository: ReportRepository, adapters: tuple[ReportAdapter, ...]) -> None:
        self._repository = repository
        self._adapters = adapters

    def generate(
        self,
        bundle: ReportInput,
        *,
        client_request_id: str | None = None,
        cancelled: bool = False,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> ReportGenerationResult:
        _preflight_bundle(bundle)
        if cancelled or (cancel_requested is not None and cancel_requested()):
            raise ValueError("report_generation_cancelled")
        request_id = client_request_id or f"automatic-{time.time_ns()}"
        existing = self._repository.by_client_request(request_id)
        if existing is not None:
            return ReportGenerationResult(
                existing.report_snapshot_id,
                existing.status,
                existing.adapter,
                existing.version,
            )
        version = self._repository.next_version(bundle.target_business_date)
        report_snapshot_id = (
            "report-" + hashlib.sha256(f"{bundle.bundle_id}:{request_id}".encode()).hexdigest()[:20]
        )
        bundle_hash = self._repository.save_bundle(bundle)
        report_started_ns = time.monotonic_ns()
        for adapter in self._adapters:
            if cancel_requested is not None and cancel_requested():
                raise ValueError("report_generation_cancelled")
            started_at = datetime.now(UTC)
            attempt_started_ns = time.monotonic_ns()
            response = adapter.generate(bundle)
            completed_at = datetime.now(UTC)
            completed_ns = time.monotonic_ns()
            cancelled_after = response.error_classification == "cancelled" or (
                cancel_requested is not None and cancel_requested()
            )
            outcome = response.error_classification or response.status
            output_hash = (
                _hash_document(response.document) if response.document is not None else None
            )
            if response.status == "succeeded" and response.document is not None:
                outcome = _validate_ai_document(bundle, response)
            if cancelled_after:
                outcome = "cancelled"
            self._repository.record_attempt(
                report_snapshot_id,
                adapter=adapter.name,
                adapter_version=adapter.version,
                outcome=outcome,
                started_at=started_at,
                completed_at=completed_at,
                tool_events=response.tool_events,
                output_hash=output_hash,
                process_audit={**response.process_audit, "bundle_id": bundle.bundle_id},
                elapsed_ms=(completed_ns - attempt_started_ns) // 1_000_000,
                report_elapsed_ms=(completed_ns - report_started_ns) // 1_000_000,
            )
            if cancelled_after:
                raise ValueError("report_generation_cancelled")
            if outcome == "succeeded" and response.document is not None:
                body = bundle.deterministic_skeleton()
                body["ai_explanation"] = response.document["sections"]
                body["explanation_verification"] = {
                    "status": "pending_evidence_review",
                    "identity_and_conclusions": "passed",
                    "semantic_support": "not_reviewed",
                    "output_hash": output_hash,
                }
                snapshot = self._repository.save_snapshot(
                    report_snapshot_id=report_snapshot_id,
                    client_request_id=request_id,
                    bundle=bundle,
                    bundle_hash=bundle_hash,
                    version=version,
                    status="completed",
                    adapter=adapter.name,
                    body=body,
                )
                return ReportGenerationResult(
                    snapshot.report_snapshot_id,
                    snapshot.status,
                    snapshot.adapter,
                    snapshot.version,
                )
        snapshot = self._repository.save_snapshot(
            report_snapshot_id=report_snapshot_id,
            client_request_id=request_id,
            bundle=bundle,
            bundle_hash=bundle_hash,
            version=version,
            status="completed_degraded",
            adapter="deterministic",
            body=bundle.deterministic_skeleton(),
        )
        return ReportGenerationResult(
            snapshot.report_snapshot_id,
            snapshot.status,
            snapshot.adapter,
            snapshot.version,
        )


class CliReportAdapter:
    def __init__(
        self,
        name: str,
        *,
        timeout_seconds: int = 300,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        if name not in {"codex_cli", "claude_code_cli"}:
            raise ValueError("unsupported_cli_report_adapter")
        self.name = name
        self.version = "runtime-detected"
        self._timeout_seconds = timeout_seconds
        self._cancel_requested = cancel_requested

    def generate(self, bundle: ReportInput) -> AdapterResponse:
        deadline = time.monotonic() + self._timeout_seconds
        executable = "codex" if self.name == "codex_cli" else "claude"
        resolved = shutil.which(executable)
        if resolved is None:
            resolved = next(
                (
                    str(candidate)
                    for directory in (Path.home() / ".local/bin", Path.home() / ".npm-global/bin")
                    if (candidate := directory / executable).is_file()
                    and os.access(candidate, os.X_OK)
                ),
                None,
            )
        if resolved is None:
            return AdapterResponse.unavailable("cli_not_installed")
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "HOME",
                "LANG",
                "LC_ALL",
                "TERM",
                "COLORTERM",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "NO_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
                "no_proxy",
                "SSL_CERT_FILE",
                "NODE_EXTRA_CA_CERTS",
            }
        }
        self.version = "unavailable"
        prompt = _canonical_json(
            {
                "instruction": (
                    "仅解释报告输入中的已验证结果，输出共同报告 JSON；不得调用工具或给出交易建议。"
                    "正式阶段、三核心状态与宏观、库存结论只能解释、不得改写，"
                    "conclusions 须与报告输入的 conclusions 完全一致。"
                    "涉及具体数值时写明数据来源；有异常（核心沿用、缺口、落后、冲突）时如实说明。"
                    "每个section的explanation必须是非空的单段文字，不含换行或段落分隔符；"
                    "多段解释须拆为多个section。"
                ),
                "report_input": bundle.prompt_document(),
                "execution_contract": {
                    "schema_version": REPORT_SCHEMA_VERSION,
                    "prompt_version": PROMPT_CONTRACT_VERSION,
                    "input_bundle_versions_are_historical": True,
                },
            }
        )
        with tempfile.TemporaryDirectory(prefix="pring-report-") as work_directory:
            work_path = Path(work_directory)
            schema_path = work_path / "report.schema.json"
            output_path = work_path / "report.output.json"
            schema = _report_output_schema(bundle)
            schema_path.write_text(_canonical_json(schema), encoding="utf-8")
            audit: dict[str, Any] = {
                "executable": resolved,
                "cli_version": self.version,
                "model_id": None,
                "model_reporting": "not_reported",
                "schema_version": REPORT_SCHEMA_VERSION,
                "prompt_version": PROMPT_CONTRACT_VERSION,
                "input_schema_version": bundle.schema_version,
                "input_prompt_version": bundle.prompt_version,
                "schema_sha256": _hash_document(schema),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt_bytes": len(prompt.encode()),
                "bundle_id": bundle.bundle_id,
                "exit_code": None,
                "process_phase": "version",
            }

            def failed(classification: str) -> AdapterResponse:
                return replace(
                    AdapterResponse.unavailable(classification),
                    tool_events=int(audit.get("tool_events", 0)),
                    process_audit=audit,
                )

            try:
                version_process = subprocess.Popen(
                    [resolved, "--version"],
                    cwd=work_directory,
                    env=environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    text=True,
                )
            except OSError:
                return failed("process_start_failed")
            version_stdout, version_stderr, version_outcome = _communicate_with_limits(
                version_process,
                "",
                deadline=min(deadline, time.monotonic() + 5),
                cancel_requested=self._cancel_requested,
            )
            audit["version_probe"] = {
                **_process_output_fingerprint(version_process, version_stdout, version_stderr),
                "outcome": version_outcome
                or ("succeeded" if version_process.returncode == 0 else "nonzero_exit"),
            }
            if version_outcome is not None:
                audit["exit_code"] = version_process.returncode
                return failed(version_outcome)
            if version_process.returncode == 0 and version_stdout.strip():
                self.version = version_stdout.strip()[:200]
            audit["cli_version"] = self.version
            if self._cancel_requested is not None and self._cancel_requested():
                return failed("cancelled")
            if time.monotonic() >= deadline:
                return failed("timed_out")
            audit["process_phase"] = "generation"
            command = (
                [
                    resolved,
                    "exec",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "--json",
                    "-",
                ]
                if self.name == "codex_cli"
                else [
                    resolved,
                    "--print",
                    "--safe-mode",
                    "--disable-slash-commands",
                    "--tools",
                    "",
                    "--permission-mode",
                    "dontAsk",
                    "--no-session-persistence",
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "--json-schema",
                    _canonical_json(schema),
                ]
            )
            try:
                process = subprocess.Popen(
                    command,
                    cwd=work_directory,
                    env=environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    text=True,
                )
            except OSError:
                return failed("process_start_failed")
            stdout, stderr, outcome = _communicate_with_limits(
                process,
                prompt,
                deadline=deadline,
                cancel_requested=self._cancel_requested,
            )
            audit.update(_process_output_fingerprint(process, stdout, stderr))
            models = _reported_cli_models(stdout)
            if models:
                audit["model_ids"] = models
                audit["model_id"] = models[0] if len(models) == 1 else None
                audit["model_reporting"] = "cli_output"
            audit.update(_cli_event_audit(self.name, stdout))
            if self.name == "codex_cli":
                try:
                    output_bytes = output_path.read_bytes()
                except OSError:
                    audit["output_file_status"] = "unavailable"
                else:
                    audit.update(
                        output_file_status="captured",
                        output_file_sha256=hashlib.sha256(output_bytes).hexdigest(),
                        output_file_bytes=len(output_bytes),
                    )
            if outcome is not None:
                return failed(outcome)
            if process.returncode != 0:
                return failed(_cli_failure_classification(stdout, stderr))
            try:
                document = (
                    _codex_output(stdout, output_path)
                    if self.name == "codex_cli"
                    else _claude_output(stdout)
                )
            except (json.JSONDecodeError, OSError, ValueError):
                return failed("invalid_json_output")
        if not isinstance(document, dict):
            return failed("invalid_json_schema")
        return replace(
            AdapterResponse.succeeded(document, tool_events=int(audit["tool_events"])),
            process_audit=audit,
        )


def _process_output_fingerprint(
    process: subprocess.Popen[str], stdout: str, stderr: str
) -> dict[str, Any]:
    return {
        "exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
    }


def _communicate_with_limits(
    process: subprocess.Popen[str],
    prompt: str,
    *,
    deadline: float,
    cancel_requested: Callable[[], bool] | None,
) -> tuple[str, str, str | None]:
    first = True
    while True:
        if cancel_requested is not None and cancel_requested():
            stdout, stderr = _terminate_process_group(process)
            return stdout, stderr, "cancelled"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stdout, stderr = _terminate_process_group(process)
            return stdout, stderr, "timed_out"
        try:
            stdout, stderr = process.communicate(
                prompt if first else None,
                timeout=min(0.5, remaining),
            )
            return stdout, stderr, None
        except subprocess.TimeoutExpired:
            first = False


def _terminate_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        return process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return process.communicate()


def _reported_cli_models(stdout: str) -> list[str]:
    models: set[str] = set()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if isinstance(event.get("model"), str):
            models.add(event["model"])
        if isinstance(event.get("modelUsage"), dict):
            models.update(str(model) for model in event["modelUsage"])
    return sorted(models)


def _cli_failure_classification(stdout: str, stderr: str) -> str:
    error = (stderr + "\n" + stdout).lower()
    if any(
        term in error
        for term in (
            "not logged in",
            "please log in",
            "authentication required",
            "unauthorized",
            "invalid authentication",
        )
    ):
        return "authentication_required"
    if any(
        term in error
        for term in ("rate limit", "quota exceeded", "usage limit", "insufficient credits")
    ):
        return "quota_or_rate_limited"
    if any(
        term in error
        for term in (
            "unexpected argument",
            "unknown option",
            "invalid json schema",
            "invalid schema",
        )
    ):
        return "cli_protocol_incompatible"
    return "nonzero_exit"


def _report_output_schema(bundle: ReportInput) -> dict[str, Any]:
    section = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "explanation": {"type": "string", "minLength": 1, "pattern": r"^[^\r\n\u2028\u2029]+$"},
        },
        "required": ["title", "explanation"],
    }
    conclusions = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: {"type": ["string", "null"], "const": value}
            for name, value in bundle.conclusions.items()
        },
        "required": list(bundle.conclusions),
    }
    core_states = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            asset: {"type": "string", "const": state} for asset, state in bundle.core_states.items()
        },
        "required": list(bundle.core_states),
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "bundle_id": {"type": "string", "const": bundle.bundle_id},
            "current_stage": {
                "type": ["string", "null"],
                "const": bundle.current_stage,
            },
            "report_cutoff": {
                "type": "string",
                "const": bundle.report_cutoff.isoformat(),
            },
            "core_states": core_states,
            "conclusions": conclusions,
            "sections": {"type": "array", "minItems": 1, "items": section},
            "proxy_used": {"type": "boolean", "const": False},
        },
        "required": list(_OUTPUT_FIELDS),
    }


_OUTPUT_FIELDS = (
    "bundle_id",
    "current_stage",
    "report_cutoff",
    "core_states",
    "conclusions",
    "sections",
    "proxy_used",
)


# Item types codex reports that are the CLI speaking about itself, not the model acting:
# its own notices ("error") and its visible thinking. Anything else counts as tool use, so an
# unknown type is rejected rather than quietly allowed.
CODEX_NON_TOOL_ITEMS = {"reasoning", "agent_message", "error"}


def _cli_event_audit(adapter: str, stdout: str) -> dict[str, Any]:
    """Count observable complete events independently of process/output acceptance."""
    tools, invalid_lines = 0, 0
    notices: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            invalid_lines += 1
            continue
        if not isinstance(event, dict):
            invalid_lines += 1
            continue
        if adapter == "codex_cli":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            if item.get("type") == "error" and isinstance(item.get("message"), str):
                notices.append(item["message"])
            tools += int(item.get("type") not in CODEX_NON_TOOL_ITEMS)
        elif event.get("type") == "assistant":
            message = event.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                invalid_lines += 1
                continue
            tools += sum(
                1
                for block in message["content"]
                if isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") != "StructuredOutput"
            )
    return {
        "tool_events": tools,
        "unparsed_event_lines": invalid_lines,
        "cli_notices": notices,
    }


def _codex_output(stdout: str, output_path: Path) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.strip() and not isinstance(json.loads(line), dict):
            raise ValueError("codex_event_not_object")
    document = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("codex_output_not_object")
    return document


def _claude_output(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not events or any(not isinstance(event, dict) for event in events):
        raise ValueError("claude_output_not_object")
    results = [
        event for event in events if event.get("type") == "result" or "structured_output" in event
    ]
    if len(results) != 1:
        raise ValueError("claude_result_missing_or_ambiguous")
    wrapper = results[0]
    if wrapper.get("is_error") is True or wrapper.get("subtype", "success") != "success":
        raise ValueError("claude_result_failed")
    document = wrapper.get("structured_output")
    if not isinstance(document, dict):
        raise ValueError("claude_structured_output_missing")
    for event in events:
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            raise ValueError("claude_assistant_event_invalid")
    return document


def _preflight_bundle(bundle: ReportInput) -> None:
    formal_stages = {
        "stage_i",
        "stage_ii",
        "stage_iii",
        "stage_iv",
        "stage_v",
        "stage_vi",
    }
    noncanonical = (
        bundle.current_stage is None
        and bundle.stage_reason == "noncanonical_combination"
        and (
            bundle.core_states.get("bond"),
            bundle.core_states.get("stock"),
            bundle.core_states.get("commodity"),
        )
        in {("bull", "bear", "bull"), ("bear", "bull", "bear")}
    )
    # A held stage (core data pending) still gets its report of the other outputs.
    core_pending = bundle.current_stage is None and bundle.stage_reason == "core_data_pending"
    if bundle.current_stage not in formal_stages and not noncanonical and not core_pending:
        raise ValueError("report_preflight_stage_invalid")
    if set(bundle.core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("report_preflight_core_identity_invalid")
    if bundle.report_cutoff.tzinfo is None or bundle.system_as_of.tzinfo is None:
        raise ValueError("report_preflight_cutoff_invalid")
    if bundle.system_as_of > bundle.report_cutoff:
        raise ValueError("report_preflight_cutoff_mismatch")


def _validate_ai_document(bundle: ReportInput, response: AdapterResponse) -> str:
    """The two post-checks (ADR-0027): the structure, and conclusions left as given."""
    if response.tool_events:
        return "tool_use_rejected"
    document = response.document
    if not isinstance(document, dict):
        return "invalid_json_schema"
    if set(document) != set(_OUTPUT_FIELDS):
        return "schema_validation_failed"
    if document["bundle_id"] != bundle.bundle_id:
        return "schema_validation_failed"
    if document["current_stage"] != bundle.current_stage:
        return "stage_mutation_rejected"
    if document["core_states"] != bundle.core_states or document["conclusions"] != (
        bundle.conclusions
    ):
        return "conclusion_mutation_rejected"
    if document["report_cutoff"] != bundle.report_cutoff.isoformat():
        return "schema_validation_failed"
    if document["proxy_used"] is not False:
        return "forbidden_content_rejected"
    sections = document["sections"]
    if not isinstance(sections, list) or not sections:
        return "schema_validation_failed"
    forbidden_terms = ("买入", "卖出", "目标价", "收益保证", "仓位建议")
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"title", "explanation"}:
            return "schema_validation_failed"
        if any(not isinstance(section[field], str) for field in ("title", "explanation")):
            return "schema_validation_failed"
        if any(term in section["explanation"] for term in forbidden_terms):
            return "forbidden_content_rejected"
        if not section["explanation"].strip() or any(
            separator in section["explanation"] for separator in "\r\n\u2028\u2029"
        ):
            return "paragraph_structure_invalid"
    return "succeeded"


def _report_snapshot(row: sqlite3.Row) -> ReportSnapshot:
    body_retained = bool(row["body_retained"])
    bundle = json.loads(str(row["bundle_document_json"]))
    if not isinstance(bundle, dict):
        raise ValueError("report_bundle_document_invalid")
    started_at = (
        datetime.fromisoformat(str(row["attempt_started_at"]))
        if row["attempt_started_at"] is not None
        else datetime.fromisoformat(str(row["created_at"]))
    )
    completed_at = (
        datetime.fromisoformat(str(row["attempt_completed_at"]))
        if row["attempt_completed_at"] is not None
        else started_at
    )
    return ReportSnapshot(
        report_snapshot_id=str(row["report_snapshot_id"]),
        projection_set_id=str(row["projection_set_id"]),
        target_business_date=str(row["target_business_date"]),
        version=int(row["version"]),
        status=str(row["status"]),
        adapter=str(row["adapter"]),
        current_stage=(str(row["current_stage"]) if row["current_stage"] is not None else None),
        bundle_id=str(row["bundle_id"]),
        bundle_hash=str(row["bundle_hash"]),
        model_version_id=str(row["model_version_id"]),
        schema_version=str(row["schema_version"]),
        prompt_version=str(row["prompt_version"]),
        input_schema_version=str(bundle["schema_version"]),
        input_prompt_version=str(bundle["prompt_version"]),
        report_cutoff=datetime.fromisoformat(str(bundle["report_cutoff"])),
        system_as_of=datetime.fromisoformat(str(bundle["system_as_of"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        duration_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        body_retained=body_retained,
        body=json.loads(str(row["body_json"])) if body_retained else {},
    )


def _report_attempt(row: sqlite3.Row) -> ReportAttempt:
    started_at = datetime.fromisoformat(str(row["started_at"]))
    completed_at = datetime.fromisoformat(str(row["completed_at"]))
    audit = json.loads(row["process_audit_json"]) if "process_audit_json" in set(row.keys()) else {}
    elapsed_ms = _timing_duration(audit, "elapsed_ms")
    return ReportAttempt(
        adapter=str(row["adapter"]),
        adapter_version=str(row["adapter_version"]),
        outcome=str(row["outcome"]),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=(
            elapsed_ms
            if elapsed_ms is not None
            else max(0, int((completed_at - started_at).total_seconds() * 1000))
        ),
        tool_events=int(row["tool_events"]),
        output_hash=(str(row["output_hash"]) if row["output_hash"] is not None else None),
        process_audit=audit,
    )


def _timing_duration(audit: dict[str, Any], field: str) -> int | None:
    timing = audit.get("timing")
    if not isinstance(timing, dict) or timing.get("basis") != "monotonic":
        return None
    value = timing.get(field)
    return value if type(value) is int and value >= 0 else None


def _hash_document(document: Any) -> str:
    return hashlib.sha256(_canonical_json(document).encode()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_REPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_bundle (
    bundle_id TEXT PRIMARY KEY,
    bundle_hash TEXT NOT NULL,
    projection_set_id TEXT NOT NULL,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_attempt (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_snapshot_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    tool_events INTEGER NOT NULL,
    output_hash TEXT
);
CREATE TABLE IF NOT EXISTS report_snapshot (
    report_snapshot_id TEXT PRIMARY KEY,
    client_request_id TEXT NOT NULL UNIQUE,
    projection_set_id TEXT NOT NULL,
    target_business_date TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    adapter TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    bundle_id TEXT NOT NULL REFERENCES evidence_bundle(bundle_id),
    bundle_hash TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    body_json TEXT NOT NULL,
    body_retained INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(target_business_date, version)
);
CREATE TRIGGER IF NOT EXISTS report_snapshot_identity_no_update
BEFORE UPDATE OF report_snapshot_id, projection_set_id, target_business_date,
    version, status, adapter, current_stage, bundle_id, bundle_hash,
    model_version_id, schema_version, prompt_version, created_at
ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_snapshot_no_delete
BEFORE DELETE ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
"""

_REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA = """
CREATE TABLE report_snapshot (
    report_snapshot_id TEXT PRIMARY KEY,
    client_request_id TEXT NOT NULL UNIQUE,
    projection_set_id TEXT NOT NULL,
    target_business_date TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    adapter TEXT NOT NULL,
    current_stage TEXT,
    bundle_id TEXT NOT NULL REFERENCES evidence_bundle(bundle_id),
    bundle_hash TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    body_json TEXT NOT NULL,
    body_retained INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(target_business_date, version)
);
"""

_REPORT_SNAPSHOT_IMMUTABILITY_TRIGGERS = """
CREATE TRIGGER report_snapshot_identity_no_update
BEFORE UPDATE OF report_snapshot_id, projection_set_id, target_business_date,
    version, status, adapter, current_stage, bundle_id, bundle_hash,
    model_version_id, schema_version, prompt_version, created_at
ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
CREATE TRIGGER report_snapshot_no_delete
BEFORE DELETE ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
"""


def upgrade_report_process_audit(connection: sqlite3.Connection) -> None:
    from pring_cycle.report_review import REPORT_EXPLANATION_REVIEW_SCHEMA

    if "process_audit_json" not in {
        str(row[1]) for row in connection.execute("PRAGMA table_info(report_attempt)")
    }:
        connection.execute(
            "ALTER TABLE report_attempt ADD COLUMN process_audit_json TEXT NOT NULL DEFAULT '{}'"
        )
    connection.executescript(REPORT_EXPLANATION_REVIEW_SCHEMA)


def upgrade_report_snapshot_nullable_stage(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(report_snapshot)").fetchall()
    stage_column = next((row for row in columns if str(row[1]) == "current_stage"), None)
    if stage_column is None:
        raise RuntimeError("report_snapshot_current_stage_missing")
    if int(stage_column[3]) == 0:
        return
    rebuild_report_snapshot_stage_column(connection, nullable=True)


def rebuild_report_snapshot_stage_column(
    connection: sqlite3.Connection,
    *,
    nullable: bool,
) -> None:
    connection.execute("DROP TRIGGER IF EXISTS report_snapshot_identity_no_update")
    connection.execute("DROP TRIGGER IF EXISTS report_snapshot_no_delete")
    connection.execute("ALTER TABLE report_snapshot RENAME TO report_snapshot_legacy")
    schema = (
        _REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA
        if nullable
        else _REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA.replace(
            "current_stage TEXT,",
            "current_stage TEXT NOT NULL,",
        )
    )
    connection.executescript(schema)
    connection.execute(
        """
        INSERT INTO report_snapshot(
            report_snapshot_id, client_request_id, projection_set_id,
            target_business_date, version, status, adapter, current_stage,
            bundle_id, bundle_hash, model_version_id, schema_version,
            prompt_version, body_json, body_retained, created_at
        )
        SELECT report_snapshot_id, client_request_id, projection_set_id,
            target_business_date, version, status, adapter, current_stage,
            bundle_id, bundle_hash, model_version_id, schema_version,
            prompt_version, body_json, body_retained, created_at
        FROM report_snapshot_legacy
        """
    )
    connection.execute("DROP TABLE report_snapshot_legacy")
    connection.executescript(_REPORT_SNAPSHOT_IMMUTABILITY_TRIGGERS)


_REPORT_SNAPSHOT_SELECT = """
SELECT report_snapshot.*, evidence_bundle.document_json AS bundle_document_json,
       (SELECT MIN(started_at) FROM report_attempt
        WHERE report_attempt.report_snapshot_id=report_snapshot.report_snapshot_id)
           AS attempt_started_at,
       (SELECT MAX(completed_at) FROM report_attempt
        WHERE report_attempt.report_snapshot_id=report_snapshot.report_snapshot_id)
           AS attempt_completed_at
FROM report_snapshot
JOIN evidence_bundle USING (bundle_id)
"""
