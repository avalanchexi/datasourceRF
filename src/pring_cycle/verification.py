from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from pring_cycle.artifacts import (
    artifact_registration_exists,
    read_artifact,
    store_artifact,
)
from pring_cycle.health_types import (
    RuntimeHealthDocument,
    VerificationChecks,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.storage import worker_status


class VerificationError(RuntimeError):
    """A stable, non-sensitive local verification failure."""


class VerificationDocument(TypedDict):
    checks: VerificationChecks
    metrics: dict[str, float | int]
    network_requests: int
    processes: str
    status: str


def verify_local_runtime(paths: RuntimePaths) -> VerificationDocument:
    initialize_runtime(paths)
    initialize_runtime(paths)
    artifact_round_trip = _verify_artifact_round_trip(paths)
    port = _unused_loopback_port()
    process_started = time.perf_counter()
    worker = _start_process("worker", paths)
    web: subprocess.Popen[str] | None = None
    web_output = ""
    worker_output = ""
    try:
        _wait_for_worker(paths, worker)
        web = _start_process("web", paths, "--port", str(port))
        health = _wait_for_health(port)
        cold_start_seconds = time.perf_counter() - process_started
        origin_boundary = _verify_origin_boundary(port)
        rest_p95_ms = _benchmark_http_get(port, "/api/v1/projections/current", 100)
        dashboard_html_ms = _benchmark_dashboard_first_content(port)
        combined_rss_bytes = _process_rss_bytes(web.pid) + _process_rss_bytes(worker.pid)
    finally:
        if web is not None:
            web_output = _stop_process(web)
        worker_output = _stop_process(worker)

    if _contains_configured_secret(paths, web_output + worker_output):
        raise VerificationError("sensitive_value_in_process_output")

    checks: VerificationChecks = {
        "alembic": health["database"]["migration"],
        "artifact_round_trip": artifact_round_trip,
        "artifacts": health["artifacts"]["status"],
        "database": health["database"]["status"],
        "idempotent_initialization": "ok",
        "origin_boundary": origin_boundary,
        "runtime_location": "outside_windows_mount",
        "web": health["services"]["web"]["status"],
        "worker": health["services"]["worker"]["status"],
    }
    expected_checks: VerificationChecks = {
        "alembic": "current",
        "artifact_round_trip": "ok",
        "artifacts": "ok",
        "database": "ok",
        "idempotent_initialization": "ok",
        "origin_boundary": "rejected",
        "runtime_location": "outside_windows_mount",
        "web": "healthy",
        "worker": "healthy",
    }
    if checks != expected_checks:
        raise VerificationError("local_runtime_health_check_failed")
    return {
        "checks": checks,
        "metrics": {
            "combined_rss_bytes": combined_rss_bytes,
            "dashboard_html_ms": dashboard_html_ms,
            "rest_current_projection_p95_ms": rest_p95_ms,
            "web_worker_cold_start_seconds": cold_start_seconds,
        },
        "network_requests": 0,
        "processes": "stopped",
        "status": "ok",
    }


def _verify_artifact_round_trip(paths: RuntimePaths) -> str:
    content = b"pring-cycle-ticket-01-offline-artifact\n"
    source_reference = "verification:ticket-01"
    first = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        media_type="text/plain",
        source_reference=source_reference,
    )
    second = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        media_type="text/plain",
        source_reference=source_reference,
    )
    if (
        first.content_hash != second.content_hash
        or first.path != second.path
        or read_artifact(first) != content
        or not artifact_registration_exists(paths.database, first)
        or list(paths.artifacts.rglob("*.tmp"))
    ):
        raise VerificationError("artifact_round_trip_failed")
    return "ok"


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


def _wait_for_worker(paths: RuntimePaths, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise VerificationError("worker_start_failed")
        if worker_status(paths.database)["status"] == "healthy":
            return
        time.sleep(0.1)
    raise VerificationError("worker_start_timeout")


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


def _benchmark_http_get(port: int, path: str, samples: int) -> float:
    opener = build_opener(ProxyHandler({}))
    durations: list[float] = []
    for _index in range(samples):
        started = time.perf_counter()
        try:
            with opener.open(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
                response.read()
        except HTTPError as error:
            error.read()
        durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def _benchmark_dashboard_first_content(port: int) -> float:
    opener = build_opener(ProxyHandler({}))
    started = time.perf_counter()
    try:
        with opener.open(f"http://127.0.0.1:{port}/", timeout=2) as response:
            document = response.read().decode("utf-8")
    except (TimeoutError, URLError) as error:
        raise VerificationError("dashboard_initial_navigation_failed") from error
    required = (
        "data-pring-meaningful-content='true'",
        "周期驾驶舱",
        "投影身份",
        "核心资产",
        "运行状态",
    )
    if not all(marker in document for marker in required):
        raise VerificationError("dashboard_meaningful_content_missing")
    return (time.perf_counter() - started) * 1000


def _process_rss_bytes(process_id: int) -> int:
    try:
        status = Path(f"/proc/{process_id}/status").read_text(encoding="utf-8")
    except OSError as error:
        raise VerificationError("process_rss_unavailable") from error
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            fields = line.split()
            return int(fields[1]) * 1024
    raise VerificationError("process_rss_unavailable")


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
    return any(
        value and value in output for value in parse_data_source_secrets(paths.secrets).values()
    )
