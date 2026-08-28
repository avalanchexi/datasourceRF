from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from typing import TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from pring_cycle.runtime import RuntimeHealthDocument, RuntimePaths, initialize_runtime


class VerificationError(RuntimeError):
    """A stable, non-sensitive local verification failure."""


class VerificationDocument(TypedDict):
    checks: dict[str, str]
    network_requests: int
    processes: str
    status: str


def verify_local_runtime(paths: RuntimePaths) -> VerificationDocument:
    initialize_runtime(paths)
    initialize_runtime(paths)
    port = _unused_loopback_port()
    worker = _start_process("worker", paths)
    web = _start_process("web", paths, "--port", str(port))
    web_output = ""
    worker_output = ""
    try:
        health = _wait_for_health(port)
        origin_boundary = _verify_origin_boundary(port)
    finally:
        web_output = _stop_process(web)
        worker_output = _stop_process(worker)

    if _contains_configured_secret(paths, web_output + worker_output):
        raise VerificationError("sensitive_value_in_process_output")

    checks = {
        "alembic": health["database"]["migration"],
        "artifacts": health["artifacts"]["status"],
        "database": health["database"]["status"],
        "idempotent_initialization": "ok",
        "origin_boundary": origin_boundary,
        "runtime_location": "outside_windows_mount",
        "web": health["services"]["web"]["status"],
        "worker": health["services"]["worker"]["status"],
    }
    if set(checks.values()) != {"ok", "current", "rejected", "healthy", "outside_windows_mount"}:
        raise VerificationError("local_runtime_health_check_failed")
    return {
        "checks": checks,
        "network_requests": 0,
        "processes": "stopped",
        "status": "ok",
    }


def _start_process(command: str, paths: RuntimePaths, *arguments: str) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    if paths.override_root is not None:
        environment["PRING_CYCLE_RUNTIME_ROOT"] = str(paths.override_root)
    else:
        environment.pop("PRING_CYCLE_RUNTIME_ROOT", None)
        environment["XDG_CONFIG_HOME"] = str(paths.config.parent)
        environment["XDG_DATA_HOME"] = str(paths.data.parent)
        environment["XDG_STATE_HOME"] = str(paths.state.parent)
        environment["XDG_CACHE_HOME"] = str(paths.cache.parent)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pring_cycle",
            command,
            *arguments,
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _unused_loopback_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def _wait_for_health(port: int) -> RuntimeHealthDocument:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{port}/api/v1/health", timeout=1) as response:
                document = json.load(response)
            if (
                isinstance(document, Mapping)
                and document.get("status") == "ok"
                and isinstance(document.get("services"), Mapping)
            ):
                return cast(RuntimeHealthDocument, document)
        except (ConnectionError, TimeoutError, URLError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    raise VerificationError("web_worker_start_timeout")


def _verify_origin_boundary(port: int) -> str:
    request = Request(
        f"http://127.0.0.1:{port}/api/v1/commands",
        data=b"{}",
        headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"},
        method="POST",
    )
    try:
        build_opener(ProxyHandler({})).open(request, timeout=2)
    except HTTPError as error:
        if error.code == 403:
            return "rejected"
    except URLError as error:
        raise VerificationError("origin_boundary_unreachable") from error
    raise VerificationError("untrusted_origin_was_not_rejected")


def _stop_process(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    return stdout + stderr


def _contains_configured_secret(paths: RuntimePaths, output: str) -> bool:
    if not paths.secrets.is_file():
        return False
    for raw_line in paths.secrets.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        _key, value = line.split("=", maxsplit=1)
        if value and value in output:
            return True
    return False
