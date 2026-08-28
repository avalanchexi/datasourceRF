from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from pring_cycle.storage import database_health, migrate_database, worker_status

APPLICATION_NAME = "pring-cycle"
ALLOWED_CREDENTIALS = {
    "EXA_API_KEY": "exa",
    "TAVILY_API_KEY": "tavily",
    "TUSHARE_TOKEN": "tushare",
}


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
        source_root = Path(__file__).resolve().parents[2]
        for path in (self.config, self.data, self.state, self.cache):
            if (source_root / "pyproject.toml").is_file() and path.is_relative_to(source_root):
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
    artifacts: dict[str, str]
    backup: dict[str, str]
    credentials: dict[str, str]
    database: dict[str, str]
    network_requests: int
    offline_start_available: bool
    runtime: dict[str, str]
    status: str


class RuntimeHealthDocument(TypedDict):
    artifacts: dict[str, str]
    binding: dict[str, object]
    database: dict[str, str]
    services: dict[str, dict[str, str]]
    startup_actions: dict[str, int]
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

    _create_private_file(
        paths.config_file,
        '[server]\nhost = "127.0.0.1"\nport = 8050\n',
    )
    _create_private_file(
        paths.secrets,
        "# TUSHARE_TOKEN=\n# TAVILY_API_KEY=\n# EXA_API_KEY=\n",
    )
    migrate_database(paths.database)
    return {
        "network_requests": 0,
        "runtime": paths.as_document(),
        "status": "ok",
    }


def diagnose_runtime(paths: RuntimePaths) -> DiagnosisDocument:
    database = database_health(paths.database)
    credentials = _credential_states(paths.secrets)
    artifacts_ok = paths.artifacts.is_dir()
    status = "ok" if database["status"] == "ok" and artifacts_ok else "action_required"
    return {
        "artifacts": {
            "addressing": "sha256",
            "status": "ok" if artifacts_ok else "missing",
        },
        "backup": {
            "mode": "none",
            "rpo": "not_guaranteed",
            "rto": "not_guaranteed",
        },
        "credentials": credentials,
        "database": database,
        "network_requests": 0,
        "offline_start_available": database["status"] == "ok",
        "runtime": paths.as_document(),
        "status": status,
    }


def runtime_health(paths: RuntimePaths, port: int) -> RuntimeHealthDocument:
    database = database_health(paths.database)
    artifacts = {
        "addressing": "sha256",
        "status": "ok" if paths.artifacts.is_dir() else "missing",
    }
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


def _credential_states(secrets_path: Path) -> dict[str, str]:
    configured: set[str] = set()
    if secrets_path.is_file():
        for raw_line in secrets_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", maxsplit=1)
            if key in ALLOWED_CREDENTIALS and value.strip():
                configured.add(key)
    return {
        adapter: "enabled" if key in configured else "disabled"
        for key, adapter in sorted(ALLOWED_CREDENTIALS.items(), key=lambda item: item[1])
    }
