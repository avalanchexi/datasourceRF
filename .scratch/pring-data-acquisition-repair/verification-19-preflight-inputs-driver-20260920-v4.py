import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

project = Path("/mnt/d/cursor/datasourceRF-integrated-20260918")
sys.path.insert(0, str(project))
sys.path.insert(0, str(project / "src"))
from pring_cycle.runtime import RuntimePaths
from tests.models.test_isolated_lifecycle import material_identity

root = Path("/tmp/datasourceRF-preflight-inputs-20260920-v4")
assert not root.exists(), "preflight_input_destination_exists"
output = project / ".scratch/pring-data-acquisition-repair"
status = output / "verification-19-preflight-input-preparation-20260920-v4.json"
log = output / "verification-19-preflight-input-preparation-20260920-v4.txt"
paths = RuntimePaths.discover(root)
identity = material_identity(paths, profile="acquisition-repairs")
identity_path = output / "verification-19-preflight-input-identity-20260920-v4.json"
identity_path.write_text(json.dumps(identity, indent=2, sort_keys=True))
started = time.monotonic()
command = [sys.executable, "tests/fixtures/isolated_lifecycle_inputs.py", str(root), "acquisition-repairs"]
env = dict(os.environ, PYTHONPATH="src:.")
def free_gib():
    result = subprocess.run([
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile", "-Command", "[math]::Round((Get-PSDrive C).Free / 1GB, 2)"
    ], capture_output=True, text=True, timeout=15, check=True)
    return float(result.stdout.strip())
assert free_gib() > 5, "preparation_disk_reserve_unavailable"
with log.open("w") as stream:
    child = subprocess.Popen(command, cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    reason = None
    record = {"command": command, "pid": child.pid, "runtime_root": str(root), "identity_file": str(identity_path)}
    try:
        while child.poll() is None:
            elapsed = time.monotonic() - started
            remaining = free_gib()
            record.update(state="running", elapsed_seconds=elapsed, c_free_gib=remaining)
            status.write_text(json.dumps(record, indent=2))
            if remaining < 4:
                reason = "c_disk_reserve"
                break
            if elapsed > 1800:
                reason = "preparation_time_limit"
                break
            time.sleep(15)
    except Exception as error:
        reason = f"supervisor_error:{type(error).__name__}:{error}"
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    unchanged = material_identity(paths, profile="acquisition-repairs") == identity
    record.update(state="finished", exit_code=child.returncode, reason=reason,
                  elapsed_seconds=time.monotonic()-started, frozen_inputs_unchanged=unchanged)
    status.write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    sys.exit(0 if child.returncode == 0 and unchanged and reason is None else 1)
