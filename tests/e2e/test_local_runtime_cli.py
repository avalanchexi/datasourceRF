from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def run_cli(
    *arguments: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    return subprocess.run(
        [sys.executable, "-m", "pring_cycle", *arguments],
        check=False,
        capture_output=True,
        cwd=cwd,
        env=environment,
        text=True,
        timeout=60,
    )


def start_cli(*arguments: str) -> subprocess.Popen[str]:
    environment = os.environ.copy()
    return subprocess.Popen(
        [sys.executable, "-m", "pring_cycle", *arguments],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def unused_loopback_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def wait_for_health(port: int) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=1) as response:
                document: dict[str, Any] = json.load(response)
            if document["services"]["worker"]["status"] == "healthy":
                return document
        except (ConnectionError, TimeoutError, URLError):
            pass
        time.sleep(0.1)
    raise AssertionError("Web and Worker did not become healthy within 15 seconds")


def wait_for_web(port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (ConnectionError, TimeoutError, URLError):
            pass
        time.sleep(0.1)
    raise AssertionError("Web did not become reachable within 15 seconds")


def stop_process(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    return stdout + stderr


def test_installed_cli_keeps_bytecode_outside_the_source_tree(tmp_path: Path) -> None:
    source_package = Path.cwd() / "src" / "pring_cycle"
    assert list(source_package.rglob("__pycache__")) == []

    runtime_root = tmp_path / "runtime"
    initialized = run_cli("init", "--runtime-root", str(runtime_root), "--json")
    diagnosed = run_cli("doctor", "--runtime-root", str(runtime_root), "--json")

    assert initialized.returncode == 0, initialized.stderr
    assert diagnosed.returncode == 0, diagnosed.stderr
    assert list(source_package.rglob("__pycache__")) == []


def test_user_can_initialize_and_diagnose_an_offline_runtime(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"

    initialized = run_cli("init", "--runtime-root", str(runtime_root), "--json")

    assert initialized.returncode == 0, initialized.stderr
    initialized_document = json.loads(initialized.stdout)
    assert initialized_document["status"] == "ok"
    assert initialized_document["network_requests"] == 0

    secrets_path = runtime_root / "config" / "secrets.env"
    assert secrets_path.is_file()
    assert stat.S_IMODE(secrets_path.stat().st_mode) == 0o600

    diagnosed = run_cli("doctor", "--runtime-root", str(runtime_root), "--json")

    assert diagnosed.returncode == 0, diagnosed.stderr
    diagnosis = json.loads(diagnosed.stdout)
    assert diagnosis["status"] == "ok"
    assert diagnosis["database"] == {
        "migration": "current",
        "status": "ok",
        "wal": "enabled",
    }
    assert diagnosis["artifacts"] == {"addressing": "sha256", "status": "ok"}
    assert diagnosis["credentials"] == {
        "exa": "disabled",
        "tavily": "disabled",
        "tushare": "disabled",
    }
    assert diagnosis["backup"] == {
        "mode": "none",
        "rpo": "not_guaranteed",
        "rto": "not_guaranteed",
    }
    assert diagnosis["backup_mode"] == "none"
    assert diagnosis["dependency_lock"] == {"status": "present"}
    assert diagnosis["python"]["required"] == ">=3.12,<3.13"
    assert diagnosis["python"]["running"].startswith("3.12.")
    assert diagnosis["python"]["status"] == "ok"
    assert diagnosis["offline_start_available"] is True
    assert diagnosis["network_requests"] == 0

    text_diagnosis = run_cli("doctor", "--runtime-root", str(runtime_root))
    assert text_diagnosis.returncode == 0, text_diagnosis.stderr
    assert "backup_mode=none\n" in text_diagnosis.stdout


def test_doctor_distinguishes_an_unobserved_project_lock(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    execution_root = tmp_path / "outside-project"
    execution_root.mkdir()
    initialized = run_cli(
        "init",
        "--runtime-root",
        str(runtime_root),
        "--json",
        cwd=execution_root,
    )

    diagnosed = run_cli(
        "doctor",
        "--runtime-root",
        str(runtime_root),
        "--json",
        cwd=execution_root,
    )

    assert initialized.returncode == 0, initialized.stderr
    assert diagnosed.returncode == 0, diagnosed.stderr
    assert json.loads(diagnosed.stdout)["dependency_lock"] == {"status": "not_observed"}


def test_web_and_worker_start_offline_as_independent_local_processes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    initialized = run_cli("init", "--runtime-root", str(runtime_root), "--json")
    assert initialized.returncode == 0, initialized.stderr
    sentinel_secret = "ticket-01-secret-must-not-leak"
    secrets_path = runtime_root / "config" / "secrets.env"
    secrets_path.write_text(f"TUSHARE_TOKEN={sentinel_secret}\n", encoding="utf-8")
    secrets_path.chmod(0o600)
    port = unused_loopback_port()
    worker = start_cli("worker", "--runtime-root", str(runtime_root))
    web = start_cli("web", "--runtime-root", str(runtime_root), "--port", str(port))
    worker_output = ""
    web_output = ""

    try:
        health = wait_for_health(port)

        assert health["status"] == "ok"
        assert health["binding"] == {"host": "127.0.0.1", "port": port}
        assert health["services"]["web"] == {"status": "healthy"}
        assert health["services"]["worker"]["status"] == "healthy"
        assert health["database"] == {
            "migration": "current",
            "status": "ok",
            "wal": "enabled",
        }
        assert health["artifacts"] == {"addressing": "sha256", "status": "ok"}
        assert health["startup_actions"] == {
            "automatic_runs": 0,
            "external_requests": 0,
        }
        with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            page = response.read().decode("utf-8")
        assert response.status == 200
        assert "Pring 本机运行状态" in page
        assert sentinel_secret not in page

        web_output = stop_process(web)
        time.sleep(0.2)
        assert worker.poll() is None
    finally:
        if web.poll() is None:
            web_output = stop_process(web)
        worker_output = stop_process(worker)

    assert sentinel_secret not in web_output
    assert sentinel_secret not in worker_output


def test_untrusted_origin_cannot_reach_the_command_append_boundary(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    initialized = run_cli("init", "--runtime-root", str(runtime_root), "--json")
    assert initialized.returncode == 0, initialized.stderr
    port = unused_loopback_port()
    web = start_cli("web", "--runtime-root", str(runtime_root), "--port", str(port))
    authorization_sentinel = "Bearer command-boundary-secret"
    web_output = ""

    try:
        wait_for_web(port)
        request = Request(
            f"http://127.0.0.1:{port}/api/v1/commands",
            data=b'{"command":"manual_full_run"}',
            headers={
                "Authorization": authorization_sentinel,
                "Content-Type": "application/json",
                "Origin": "https://untrusted.example",
            },
            method="POST",
        )
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            response_body = error.read().decode("utf-8")
            assert error.code == 403
        else:
            raise AssertionError("Untrusted Origin unexpectedly reached the command boundary")
    finally:
        web_output = stop_process(web)

    assert json.loads(response_body) == {
        "error": "untrusted_local_command_origin",
        "status": "rejected",
    }
    assert authorization_sentinel not in response_body
    assert authorization_sentinel not in web_output


def test_offline_verification_is_idempotent_and_stops_its_processes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"

    first = run_cli("verify", "--runtime-root", str(runtime_root), "--json")
    second = run_cli("test", "--runtime-root", str(runtime_root), "--json")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    expected = {
        "checks": {
            "alembic": "current",
            "artifact_round_trip": "ok",
            "artifacts": "ok",
            "database": "ok",
            "idempotent_initialization": "ok",
            "origin_boundary": "rejected",
            "runtime_location": "outside_windows_mount",
            "web": "healthy",
            "worker": "healthy",
        },
        "network_requests": 0,
        "processes": "stopped",
        "status": "ok",
    }
    assert json.loads(first.stdout) == expected
    assert json.loads(second.stdout) == expected

    diagnosis = run_cli("doctor", "--runtime-root", str(runtime_root), "--json")
    assert diagnosis.returncode == 0, diagnosis.stderr
    assert json.loads(diagnosis.stdout)["status"] == "ok"


def test_uninitialized_web_and_worker_fail_without_runtime_writes(tmp_path: Path) -> None:
    runtime_root = tmp_path / "not-initialized"

    web = run_cli("web", "--runtime-root", str(runtime_root), "--port", "49179")
    worker = run_cli("worker", "--runtime-root", str(runtime_root))

    assert web.returncode == 2
    assert worker.returncode == 2
    assert web.stderr == "error: runtime_not_initialized\n"
    assert worker.stderr == "error: runtime_not_initialized\n"
    assert "Traceback" not in web.stderr + worker.stderr
    assert not runtime_root.exists()


def test_offline_verification_uses_the_default_xdg_directory_split(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PRING_CYCLE_RUNTIME_ROOT", None)
    environment["XDG_CONFIG_HOME"] = str(tmp_path / "xdg-config")
    environment["XDG_DATA_HOME"] = str(tmp_path / "xdg-data")
    environment["XDG_STATE_HOME"] = str(tmp_path / "xdg-state")
    environment["XDG_CACHE_HOME"] = str(tmp_path / "xdg-cache")

    verified = subprocess.run(
        [sys.executable, "-m", "pring_cycle", "verify", "--json"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=60,
    )

    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "ok"
    assert (tmp_path / "xdg-config" / "pring-cycle" / "secrets.env").is_file()
    assert (tmp_path / "xdg-data" / "pring-cycle" / "pring-cycle.sqlite3").is_file()
    assert (tmp_path / "xdg-state" / "pring-cycle" / "logs").is_dir()
    assert (tmp_path / "xdg-cache" / "pring-cycle").is_dir()


def test_init_rejects_source_tree_and_windows_mount_runtime_locations() -> None:
    source_runtime = Path.cwd() / ".ticket-01-runtime-must-not-exist"
    mounted_runtime = Path("/mnt/d/pring-cycle-runtime-must-not-exist")

    source_result = run_cli("init", "--runtime-root", str(source_runtime), "--json")
    mounted_result = run_cli("init", "--runtime-root", str(mounted_runtime), "--json")

    assert source_result.returncode == 2
    assert source_result.stderr == "error: runtime_must_be_outside_source_tree\n"
    assert mounted_result.returncode == 2
    assert mounted_result.stderr == "error: runtime_must_use_wsl_native_filesystem\n"
    assert not source_runtime.exists()
    assert not mounted_runtime.exists()
