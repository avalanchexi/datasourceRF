from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime


@pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("strace") is None,
    reason="Native SQLite scheduling regression requires Linux and strace",
)
def test_worker_queries_survive_heartbeat_close_checkpoint_delay(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="worker-sqlite-lifetime",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    trace = tmp_path / "worker.trace"
    child = Path(__file__).parents[1] / "fixtures/worker_sqlite_lifetime.py"
    # Delay a real sync, never replace its return value or change SQLite's timeout.
    # On the supported runtime the fourth sync in the heartbeat thread is WAL close.
    process = subprocess.Popen(
        [
            "/usr/bin/strace",
            "-f",
            "-ttt",
            "-yy",
            "-e",
            "trace=fcntl,fsync,fdatasync,write",
            "-e",
            "inject=fsync:delay_exit=6s:when=4",
            "-o",
            str(trace),
            sys.executable,
            "-B",
            str(child),
            str(paths.config.parent),
            submitted.run_id,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stat = paths.database.stat()
    lock_key = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}:{stat.st_ino}"
    messages: list[dict[str, object]] = []
    query_window = False
    trigger = ""
    buffered = b""
    reaped = False
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                if selector.select(timeout=0.005):
                    chunk = os.read(process.stdout.fileno(), 65536)
                    assert chunk, "Worker exited before the observation boundary"
                    buffered += chunk
                    while b"\n" in buffered:
                        line, buffered = buffered.split(b"\n", 1)
                        message = json.loads(line)
                        messages.append(message)
                        query_window |= message["event"] == "query_window"
                        if message["event"] == "heartbeat_finished":
                            trigger = "heartbeat_finished_without_close_lock"
                    if trigger:
                        break
                if query_window:
                    locks = Path("/proc/locks").read_text().splitlines()
                    if any(
                        lock_key in line and "WRITE" in line and "1073741826" in line
                        for line in locks
                    ):
                        trigger = "real_close_lock_observed"
                        break
            assert trigger, "Heartbeat did not reach a verifiable boundary"
        stdout, stderr = process.communicate(b"query\n", timeout=30)
        reaped = True
        messages.extend(json.loads(line) for line in (buffered + stdout).splitlines())
    finally:
        if not reaped:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=15)
    assert process.returncode == 0, stderr
    result = next(message for message in messages if message["event"] == "result")
    # The workload still has no evidence; availability must not turn the gap into success.
    assert result["run_status"] == "action_required", result
    assert result["status"] == "query_succeeded", {"trigger": trigger, **result}
    assert runs.get(submitted.run_id).status == "action_required"


@pytest.mark.skipif(sys.platform != "linux", reason="Requires the WSL native runtime")
def test_worker_retains_lease_until_periodic_heartbeat_has_closed(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    runs = RunRepository(paths.database)
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="worker-heartbeat-shutdown",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    read_gate, release_gate = os.pipe()
    child = Path(__file__).parents[1] / "fixtures/worker_heartbeat_shutdown.py"
    process = subprocess.Popen(
        [sys.executable, "-B", str(child), str(paths.config.parent), str(read_gate)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(read_gate,),
        start_new_session=True,
    )
    os.close(read_gate)
    reaped = False
    released = False
    try:
        assert process.stdout is not None and process.stdin is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=50), "Real periodic heartbeat did not reach close"
            assert json.loads(process.stdout.readline()) == {"event": "heartbeat_closing"}
        process.stdin.write(b"finish_run\n")
        process.stdin.flush()
        deadline = time.monotonic() + 15
        while runs.get(submitted.run_id).status != "action_required":
            assert process.poll() is None, "Worker exited before persisting the task result"
            assert time.monotonic() < deadline
            time.sleep(0.01)
        # A terminal task does not mean its outstanding heartbeat may lose ownership.
        # Exceed the old one-second join limit while the native connection is still open.
        time.sleep(2)
        with pytest.raises(ValueError, match="worker_lease_active"):
            runs.acquire_lease(submitted.run_id, owner_id="next-worker")
        assert process.poll() is None
        os.write(release_gate, b"1")
        released = True
        stdout, stderr = process.communicate(timeout=20)
        reaped = True
        assert process.returncode == 0, stderr
        assert json.loads(stdout) == {"event": "worker_returned"}
        # Both the execution lease and the retained database connection are releasable.
        runs.acquire_lease(submitted.run_id, owner_id="next-worker")
        runs.release_lease("next-worker")
    finally:
        if not released:
            with suppress(BrokenPipeError):
                os.write(release_gate, b"1")
        os.close(release_gate)
        if not reaped:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=15)
