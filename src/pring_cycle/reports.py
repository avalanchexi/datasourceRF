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
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pring_cycle.projections import ProjectionSet

REPORT_SCHEMA_VERSION = "report-schema-v0001"
PROMPT_CONTRACT_VERSION = "report-prompt-v0001"


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    projection_set_id: str
    target_business_date: str
    report_cutoff: datetime
    system_as_of: datetime
    model_version_id: str
    trend_rule_version: str
    current_stage: str
    core_states: dict[str, str]
    allowed_evidence_ids: tuple[str, ...]
    allowed_governance_refs: tuple[str, ...]
    support: tuple[str, ...]
    counterevidence: tuple[str, ...]
    governance_gaps: tuple[str, ...]
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
        current_stage: str,
        core_states: dict[str, str],
        allowed_evidence_ids: tuple[str, ...],
        allowed_governance_refs: tuple[str, ...],
        support: tuple[str, ...],
        counterevidence: tuple[str, ...],
        governance_gaps: tuple[str, ...],
    ) -> EvidenceBundle:
        identity = {
            "projection_set_id": projection_set_id,
            "target_business_date": target_business_date,
            "report_cutoff": report_cutoff.isoformat(),
            "system_as_of": system_as_of.isoformat(),
            "model_version_id": model_version_id,
            "trend_rule_version": trend_rule_version,
            "current_stage": current_stage,
            "core_states": core_states,
            "allowed_evidence_ids": allowed_evidence_ids,
            "allowed_governance_refs": allowed_governance_refs,
            "support": support,
            "counterevidence": counterevidence,
            "governance_gaps": governance_gaps,
            "schema_version": REPORT_SCHEMA_VERSION,
            "prompt_version": PROMPT_CONTRACT_VERSION,
        }
        bundle_id = "bundle-" + _hash_document(identity)[:20]
        return cls(
            bundle_id=bundle_id,
            projection_set_id=projection_set_id,
            target_business_date=target_business_date,
            report_cutoff=report_cutoff,
            system_as_of=system_as_of,
            model_version_id=model_version_id,
            trend_rule_version=trend_rule_version,
            current_stage=current_stage,
            core_states=core_states,
            allowed_evidence_ids=allowed_evidence_ids,
            allowed_governance_refs=allowed_governance_refs,
            support=support,
            counterevidence=counterevidence,
            governance_gaps=governance_gaps,
        )

    def document(self) -> dict[str, Any]:
        document = asdict(self)
        document["report_cutoff"] = self.report_cutoff.isoformat()
        document["system_as_of"] = self.system_as_of.isoformat()
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
                "classification_source": "three_core_price_states_only",
            },
            "core_states": dict(self.core_states),
            "support": list(self.support),
            "counterevidence": list(self.counterevidence),
            "governance_gaps": list(self.governance_gaps),
            "evidence_references": list(self.allowed_evidence_ids),
        }


def evidence_bundle_from_projection(projection: ProjectionSet) -> EvidenceBundle:
    envelope = projection.envelope
    overview = projection.datasets["cycle_overview"]
    current_stage = overview.get("current_stage")
    if not isinstance(current_stage, str):
        raise ValueError("formal_stage_required_for_report")
    assets_value = projection.datasets["core_assets"].get("assets")
    if not isinstance(assets_value, list):
        raise ValueError("core_asset_projection_required_for_report")
    core_states = {
        str(item["asset"]): str(item["state"])
        for item in assets_value
        if isinstance(item, dict) and "asset" in item and "state" in item
    }
    if set(core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("core_asset_projection_required_for_report")
    evidence_ids = tuple(sorted(_collect_evidence_ids(projection.datasets)))
    return EvidenceBundle.create(
        projection_set_id=envelope.projection_set_id,
        target_business_date=envelope.target_business_date,
        report_cutoff=envelope.system_as_of,
        system_as_of=envelope.system_as_of,
        model_version_id=envelope.model_version_id,
        trend_rule_version=envelope.trend_rule_version,
        current_stage=current_stage,
        core_states=core_states,
        allowed_evidence_ids=evidence_ids,
        allowed_governance_refs=("ADR-0003", "ADR-0010", envelope.model_version_id),
        support=("三核心资产价格状态通过 P0 门禁。",),
        counterevidence=tuple(str(item) for item in envelope.warnings),
        governance_gaps=(),
    )


def _collect_evidence_ids(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "observation_id"} and isinstance(item, str):
                found.add(item)
            elif key in {"evidence_ids", "observation_version_ids"} and isinstance(
                item, (list, tuple)
            ):
                found.update(reference for reference in item if isinstance(reference, str))
            else:
                found.update(_collect_evidence_ids(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(_collect_evidence_ids(item))
    return found


@dataclass(frozen=True)
class AdapterResponse:
    status: str
    document: dict[str, Any] | None
    error_classification: str | None
    tool_events: int

    @classmethod
    def succeeded(cls, document: dict[str, Any], *, tool_events: int = 0) -> AdapterResponse:
        return cls("succeeded", document, None, tool_events)

    @classmethod
    def unavailable(cls, classification: str) -> AdapterResponse:
        return cls("unavailable", None, classification, 0)


class ReportAdapter(Protocol):
    name: str
    version: str

    def generate(self, bundle: EvidenceBundle) -> AdapterResponse: ...


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
    current_stage: str
    bundle_id: str
    bundle_hash: str
    model_version_id: str
    schema_version: str
    prompt_version: str
    created_at: datetime
    body_retained: bool
    body: dict[str, Any]


@dataclass(frozen=True)
class ReportAttempt:
    adapter: str
    adapter_version: str
    outcome: str
    tool_events: int
    output_hash: str | None


class ReportRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ReportRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_REPORT_SCHEMA)
        return repository

    def by_client_request(self, client_request_id: str) -> ReportSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM report_snapshot WHERE client_request_id=?",
                (client_request_id,),
            ).fetchone()
        return _report_snapshot(row) if row is not None else None

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

    def save_bundle(self, bundle: EvidenceBundle) -> str:
        document_json = _canonical_json(bundle.document())
        bundle_hash = hashlib.sha256(document_json.encode()).hexdigest()
        with self._connect() as connection:
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
        tool_events: int,
        output_hash: str | None,
    ) -> None:
        observed_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO report_attempt(
                    report_snapshot_id, adapter, adapter_version, started_at,
                    completed_at, outcome, tool_events, output_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_snapshot_id,
                    adapter,
                    adapter_version,
                    observed_at,
                    observed_at,
                    outcome,
                    tool_events,
                    output_hash,
                ),
            )

    def save_snapshot(
        self,
        *,
        report_snapshot_id: str,
        client_request_id: str,
        bundle: EvidenceBundle,
        bundle_hash: str,
        version: int,
        status: str,
        adapter: str,
        body: dict[str, Any],
    ) -> ReportSnapshot:
        body_json = _canonical_json(body)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO report_snapshot(
                    report_snapshot_id, client_request_id, projection_set_id,
                    target_business_date, version, status, adapter, current_stage,
                    bundle_id, bundle_hash, model_version_id, schema_version,
                    prompt_version, body_json, body_retained, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
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
                    bundle.schema_version,
                    bundle.prompt_version,
                    body_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return self.get(report_snapshot_id)

    def get(self, report_snapshot_id: str) -> ReportSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM report_snapshot WHERE report_snapshot_id=?",
                (report_snapshot_id,),
            ).fetchone()
        if row is None:
            raise LookupError("report_snapshot_not_found")
        return _report_snapshot(row)

    def history(self) -> tuple[ReportSnapshot, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM report_snapshot
                ORDER BY target_business_date DESC, version DESC
                """
            ).fetchall()
        return tuple(_report_snapshot(row) for row in rows)

    def attempts(self, report_snapshot_id: str) -> tuple[ReportAttempt, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM report_attempt WHERE report_snapshot_id=?
                ORDER BY attempt_id
                """,
                (report_snapshot_id,),
            ).fetchall()
        return tuple(
            ReportAttempt(
                adapter=str(row["adapter"]),
                adapter_version=str(row["adapter_version"]),
                outcome=str(row["outcome"]),
                tool_events=int(row["tool_events"]),
                output_hash=(str(row["output_hash"]) if row["output_hash"] is not None else None),
            )
            for row in rows
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


class ReportService:
    def __init__(self, repository: ReportRepository, adapters: tuple[ReportAdapter, ...]) -> None:
        self._repository = repository
        self._adapters = adapters

    def generate(
        self,
        bundle: EvidenceBundle,
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
        for adapter in self._adapters:
            if cancel_requested is not None and cancel_requested():
                raise ValueError("report_generation_cancelled")
            response = adapter.generate(bundle)
            if cancel_requested is not None and cancel_requested():
                raise ValueError("report_generation_cancelled")
            outcome = response.error_classification or response.status
            output_hash = (
                _hash_document(response.document) if response.document is not None else None
            )
            if response.status == "succeeded" and response.document is not None:
                outcome = _validate_ai_document(bundle, response)
            self._repository.record_attempt(
                report_snapshot_id,
                adapter=adapter.name,
                adapter_version=adapter.version,
                outcome=outcome,
                tool_events=response.tool_events,
                output_hash=output_hash,
            )
            if outcome == "succeeded" and response.document is not None:
                body = bundle.deterministic_skeleton()
                body["ai_explanation"] = response.document["sections"]
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

    def generate(self, bundle: EvidenceBundle) -> AdapterResponse:
        executable = "codex" if self.name == "codex_cli" else "claude"
        resolved = shutil.which(executable)
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
            }
        }
        prompt = _canonical_json(
            {
                "instruction": "仅解释证据包，输出共同报告 JSON；不得调用工具或给出交易建议。",
                "evidence_bundle": bundle.document(),
            }
        )
        with tempfile.TemporaryDirectory(prefix="pring-report-") as work_directory:
            work_path = Path(work_directory)
            schema_path = work_path / "report.schema.json"
            output_path = work_path / "report.output.json"
            schema = _report_output_schema(bundle)
            schema_path.write_text(_canonical_json(schema), encoding="utf-8")
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
                    "json",
                    "--json-schema",
                    _canonical_json(schema),
                ]
            )
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
            stdout, outcome = _communicate_with_limits(
                process,
                prompt,
                timeout_seconds=self._timeout_seconds,
                cancel_requested=self._cancel_requested,
            )
            if outcome is not None:
                return AdapterResponse.unavailable(outcome)
            if process.returncode != 0:
                return AdapterResponse.unavailable("nonzero_exit")
            try:
                document, tool_events = (
                    _codex_output(stdout, output_path)
                    if self.name == "codex_cli"
                    else _claude_output(stdout)
                )
            except (json.JSONDecodeError, OSError, ValueError):
                return AdapterResponse.unavailable("invalid_json_output")
        if not isinstance(document, dict):
            return AdapterResponse.unavailable("invalid_json_schema")
        return AdapterResponse.succeeded(document, tool_events=tool_events)


def _communicate_with_limits(
    process: subprocess.Popen[str],
    prompt: str,
    *,
    timeout_seconds: int,
    cancel_requested: Callable[[], bool] | None,
) -> tuple[str, str | None]:
    deadline = time.monotonic() + timeout_seconds
    first = True
    while True:
        if cancel_requested is not None and cancel_requested():
            _terminate_process_group(process)
            return "", "cancelled"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process_group(process)
            return "", "timed_out"
        try:
            stdout, _stderr = process.communicate(
                prompt if first else None,
                timeout=min(0.5, remaining),
            )
            return stdout, None
        except subprocess.TimeoutExpired:
            first = False


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()


def _report_output_schema(bundle: EvidenceBundle) -> dict[str, Any]:
    section = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "explanation": {"type": "string"},
            "evidence_ids": {
                "type": "array",
                "items": {"type": "string", "enum": list(bundle.allowed_evidence_ids)},
            },
            "governance_refs": {
                "type": "array",
                "items": {"type": "string", "enum": list(bundle.allowed_governance_refs)},
            },
        },
        "required": ["title", "explanation", "evidence_ids", "governance_refs"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "bundle_id": {"type": "string", "const": bundle.bundle_id},
            "current_stage": {"type": "string", "const": bundle.current_stage},
            "report_cutoff": {
                "type": "string",
                "const": bundle.report_cutoff.isoformat(),
            },
            "sections": {"type": "array", "minItems": 1, "items": section},
            "proxy_used": {"type": "boolean", "const": False},
        },
        "required": [
            "bundle_id",
            "current_stage",
            "report_cutoff",
            "sections",
            "proxy_used",
        ],
    }


def _codex_output(stdout: str, output_path: Path) -> tuple[dict[str, Any], int]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    tool_types = {
        "command_execution",
        "file_change",
        "mcp_tool_call",
        "web_search",
    }
    tool_events = sum(
        1
        for event in events
        if isinstance(event, dict)
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") in tool_types
    )
    document = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("codex_output_not_object")
    return document, tool_events


def _claude_output(stdout: str) -> tuple[dict[str, Any], int]:
    wrapper = json.loads(stdout)
    if not isinstance(wrapper, dict):
        raise ValueError("claude_output_not_object")
    document = wrapper.get("structured_output")
    if not isinstance(document, dict):
        raise ValueError("claude_structured_output_missing")
    return document, 0


def _preflight_bundle(bundle: EvidenceBundle) -> None:
    if bundle.current_stage not in {
        "stage_i",
        "stage_ii",
        "stage_iii",
        "stage_iv",
        "stage_v",
        "stage_vi",
    }:
        raise ValueError("report_preflight_stage_invalid")
    if set(bundle.core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("report_preflight_core_identity_invalid")
    if bundle.report_cutoff.tzinfo is None or bundle.system_as_of.tzinfo is None:
        raise ValueError("report_preflight_cutoff_invalid")
    if bundle.system_as_of > bundle.report_cutoff:
        raise ValueError("report_preflight_cutoff_mismatch")


def _validate_ai_document(bundle: EvidenceBundle, response: AdapterResponse) -> str:
    if response.tool_events:
        return "tool_use_rejected"
    document = response.document
    if not isinstance(document, dict):
        return "invalid_json_schema"
    if set(document) != {
        "bundle_id",
        "current_stage",
        "report_cutoff",
        "sections",
        "proxy_used",
    }:
        return "schema_validation_failed"
    if document["bundle_id"] != bundle.bundle_id:
        return "schema_validation_failed"
    if document["current_stage"] != bundle.current_stage:
        return "stage_mutation_rejected"
    if document["report_cutoff"] != bundle.report_cutoff.isoformat():
        return "schema_validation_failed"
    if document["proxy_used"] is not False:
        return "forbidden_content_rejected"
    sections = document["sections"]
    if not isinstance(sections, list) or not sections:
        return "schema_validation_failed"
    allowed_evidence = set(bundle.allowed_evidence_ids)
    allowed_governance = set(bundle.allowed_governance_refs)
    forbidden_terms = ("买入", "卖出", "目标价", "收益保证", "仓位建议")
    for section in sections:
        if not isinstance(section, dict) or set(section) != {
            "title",
            "explanation",
            "evidence_ids",
            "governance_refs",
        }:
            return "schema_validation_failed"
        if not isinstance(section["explanation"], str) or any(
            term in section["explanation"] for term in forbidden_terms
        ):
            return "forbidden_content_rejected"
        if not set(section["evidence_ids"]).issubset(allowed_evidence):
            return "evidence_reference_rejected"
        if not set(section["governance_refs"]).issubset(allowed_governance):
            return "evidence_reference_rejected"
    return "succeeded"


def _report_snapshot(row: sqlite3.Row) -> ReportSnapshot:
    body_retained = bool(row["body_retained"])
    return ReportSnapshot(
        report_snapshot_id=str(row["report_snapshot_id"]),
        projection_set_id=str(row["projection_set_id"]),
        target_business_date=str(row["target_business_date"]),
        version=int(row["version"]),
        status=str(row["status"]),
        adapter=str(row["adapter"]),
        current_stage=str(row["current_stage"]),
        bundle_id=str(row["bundle_id"]),
        bundle_hash=str(row["bundle_hash"]),
        model_version_id=str(row["model_version_id"]),
        schema_version=str(row["schema_version"]),
        prompt_version=str(row["prompt_version"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        body_retained=body_retained,
        body=json.loads(str(row["body_json"])) if body_retained else {},
    )


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
