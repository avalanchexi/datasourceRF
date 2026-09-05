from __future__ import annotations

from typing import Literal, TypedDict


class ArtifactHealth(TypedDict):
    addressing: Literal["sha256"]
    status: Literal["ok", "missing"]


class DatabaseHealth(TypedDict):
    migration: Literal["current", "outdated", "missing", "unknown"]
    status: Literal["ok", "degraded", "missing", "unavailable"]
    wal: Literal["enabled", "disabled", "missing", "unknown"]


class WorkerHealth(TypedDict):
    status: Literal["healthy", "stale", "stopped", "not_initialized", "unavailable"]


class WebHealth(TypedDict):
    status: Literal["healthy"]


class ServicesHealth(TypedDict):
    web: WebHealth
    worker: WorkerHealth


class RuntimeBinding(TypedDict):
    host: Literal["127.0.0.1"]
    port: int


class StartupActions(TypedDict):
    automatic_runs: Literal[0]
    external_requests: Literal[0]


class RuntimeHealthDocument(TypedDict):
    artifacts: ArtifactHealth
    binding: RuntimeBinding
    database: DatabaseHealth
    services: ServicesHealth
    startup_actions: StartupActions
    source_contract_review: dict[str, object] | None
    status: Literal["ok", "degraded"]


class VerificationChecks(TypedDict):
    alembic: str
    artifact_round_trip: str
    artifacts: str
    database: str
    idempotent_initialization: str
    origin_boundary: str
    runtime_location: str
    web: str
    worker: str
