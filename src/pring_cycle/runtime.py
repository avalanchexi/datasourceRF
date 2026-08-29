from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from pring_cycle.artifacts import artifact_health
from pring_cycle.health_types import ArtifactHealth, DatabaseHealth, RuntimeHealthDocument
from pring_cycle.maintenance import MaintenanceRepository
from pring_cycle.models import ModelRepository, certified_model_v0001_manifest
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.secrets import DATA_SOURCE_SECRET_ADAPTERS, parse_data_source_secrets
from pring_cycle.storage import database_health, migrate_database, worker_status

APPLICATION_NAME = "pring-cycle"


class RuntimePolicyError(ValueError):
    """Raised when runtime data would cross the local storage boundary."""


class RuntimeNotInitializedError(RuntimeError):
    """Raised when a service is started before the explicit init command."""


@dataclass(frozen=True)
class RuntimePaths:
    config: Path
    data: Path
    state: Path
    cache: Path
    override_root: Path | None = None

    @classmethod
    def discover(cls, runtime_root: Path | None = None) -> RuntimePaths:
        override = runtime_root or _runtime_root_from_environment()
        if override is not None:
            root = override.expanduser().resolve()
            paths = cls(
                config=root / "config",
                data=root / "data",
                state=root / "state",
                cache=root / "cache",
                override_root=root,
            )
        else:
            home = Path.home()
            paths = cls(
                config=_xdg_path("XDG_CONFIG_HOME", home / ".config"),
                data=_xdg_path("XDG_DATA_HOME", home / ".local" / "share"),
                state=_xdg_path("XDG_STATE_HOME", home / ".local" / "state"),
                cache=_xdg_path("XDG_CACHE_HOME", home / ".cache"),
            )
        paths.ensure_wsl_native()
        return paths

    @property
    def database(self) -> Path:
        return self.data / "pring-cycle.sqlite3"

    @property
    def artifacts(self) -> Path:
        return self.data / "artifacts" / "sha256"

    @property
    def logs(self) -> Path:
        return self.state / "logs"

    @property
    def secrets(self) -> Path:
        return self.config / "secrets.env"

    @property
    def config_file(self) -> Path:
        return self.config / "config.toml"

    def ensure_wsl_native(self) -> None:
        for path in (self.config, self.data, self.state, self.cache):
            if _find_project_root(path) is not None:
                raise RuntimePolicyError("runtime_must_be_outside_source_tree")
            if path.is_relative_to(Path("/mnt")):
                raise RuntimePolicyError("runtime_must_use_wsl_native_filesystem")

    def as_document(self) -> dict[str, str]:
        return {
            "artifacts": str(self.artifacts),
            "cache": str(self.cache),
            "config": str(self.config),
            "data": str(self.data),
            "database": str(self.database),
            "logs": str(self.logs),
            "secrets": str(self.secrets),
            "state": str(self.state),
        }


class InitializationDocument(TypedDict):
    network_requests: int
    runtime: dict[str, str]
    status: str


class DiagnosisDocument(TypedDict):
    artifacts: ArtifactHealth
    backup: dict[str, str]
    backup_mode: str
    credentials: dict[str, str]
    database: DatabaseHealth
    dependency_lock: dict[str, str]
    network_requests: int
    offline_start_available: bool
    python: dict[str, str]
    runtime: dict[str, str]
    status: str


def initialize_runtime(paths: RuntimePaths) -> InitializationDocument:
    for directory in (
        paths.config,
        paths.data,
        paths.state,
        paths.cache,
        paths.artifacts,
        paths.logs,
    ):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)

    _create_private_file(
        paths.config_file,
        '[server]\nhost = "127.0.0.1"\nport = 8050\n',
    )
    _create_private_file(
        paths.secrets,
        "# TUSHARE_TOKEN=\n# TAVILY_API_KEY=\n# EXA_API_KEY=\n",
    )
    migrate_database(paths.database)
    _bootstrap_v1_repositories(paths)
    return {
        "network_requests": 0,
        "runtime": paths.as_document(),
        "status": "ok",
    }


def diagnose_runtime(paths: RuntimePaths) -> DiagnosisDocument:
    database = database_health(paths.database)
    credentials = _credential_states(paths.secrets)
    artifacts = artifact_health(paths.database, paths.artifacts)
    project_root = _find_project_root(Path.cwd().resolve())
    dependency_lock_status = (
        "not_observed"
        if project_root is None
        else "present"
        if (project_root / "uv.lock").is_file()
        else "missing"
    )
    status = (
        "ok" if database["status"] == "ok" and artifacts["status"] == "ok" else "action_required"
    )
    return {
        "artifacts": artifacts,
        "backup": {
            "mode": "none",
            "rpo": "not_guaranteed",
            "rto": "not_guaranteed",
        },
        "backup_mode": "none",
        "credentials": credentials,
        "database": database,
        "dependency_lock": {"status": dependency_lock_status},
        "network_requests": 0,
        "offline_start_available": database["status"] == "ok",
        "python": {
            "required": ">=3.12,<3.13",
            "running": ".".join(str(part) for part in sys.version_info[:3]),
            "status": "ok" if sys.version_info[:2] == (3, 12) else "unsupported",
        },
        "runtime": paths.as_document(),
        "status": status,
    }


def runtime_health(paths: RuntimePaths, port: int) -> RuntimeHealthDocument:
    database = database_health(paths.database)
    artifacts = artifact_health(paths.database, paths.artifacts)
    worker = worker_status(paths.database)
    is_healthy = (
        database["status"] == "ok" and artifacts["status"] == "ok" and worker["status"] == "healthy"
    )
    return {
        "artifacts": artifacts,
        "binding": {"host": "127.0.0.1", "port": port},
        "database": database,
        "services": {"web": {"status": "healthy"}, "worker": worker},
        "startup_actions": {"automatic_runs": 0, "external_requests": 0},
        "status": "ok" if is_healthy else "degraded",
    }


def _runtime_root_from_environment() -> Path | None:
    value = os.environ.get("PRING_CYCLE_RUNTIME_ROOT")
    return Path(value) if value else None


def _find_project_root(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "pring_cycle"
        ).is_dir():
            return candidate
    return None


def _xdg_path(variable: str, fallback: Path) -> Path:
    configured = Path(os.environ.get(variable, str(fallback))).expanduser().resolve()
    return configured / APPLICATION_NAME


def _create_private_file(path: Path, contents: str) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        path.chmod(0o600)
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as private_file:
        private_file.write(contents)
    path.chmod(0o600)


def _bootstrap_v1_repositories(paths: RuntimePaths) -> None:
    ProjectionSetRepository.create(paths.database)
    RunRepository.create(paths.database)
    ReportRepository.create(paths.database)
    MaintenanceRepository.create(paths.database)
    ModelRepository.create(paths.database).create_candidate(certified_model_v0001_manifest())


def _credential_states(secrets_path: Path) -> dict[str, str]:
    configured = parse_data_source_secrets(secrets_path)
    return {
        adapter: "enabled" if key in configured else "disabled"
        for key, adapter in sorted(DATA_SOURCE_SECRET_ADAPTERS.items(), key=lambda item: item[1])
    }
