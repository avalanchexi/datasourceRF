"""Run the complete-window preflight, pinning software and material identity separately.

The software receipt (tools/inputs.py) says which code, tests, tools and build
declarations ran. The material receipt (material_identity) says which prepared
inputs were read. Earlier runs pinned only the materials, so nothing recorded the
software the result belongs to; whole-tree hashing would have recorded the evidence
notes as software instead.
"""
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
from tests.models.test_isolated_lifecycle import material_identity, _runtime_contents
from tools.inputs import inventory

root = Path("/tmp/datasourceRF-preflight-inputs-20260920-v4")
assert root.is_dir(), "preflight_inputs_missing"
output = project / ".scratch/pring-data-acquisition-repair"
preparation = json.loads((output / "verification-19-preflight-input-preparation-20260920-v4.json").read_text())
assert preparation["state"] == "finished" and preparation["exit_code"] == 0
assert preparation["reason"] is None and preparation["frozen_inputs_unchanged"]
candidate = json.loads((output / "verification-19-preflight-input-preparation-20260920-v4.txt").read_text().splitlines()[-1])["candidate_model_version_id"]
status = output / "verification-19-preflight-complete-inputs-terminal-20260920-v4.json"
assert not status.exists(), "preflight_run_already_recorded"
log = output / "verification-19-preflight-complete-inputs-result-20260920-v4.json"
paths = RuntimePaths.discover(root)

# Material identity: what the run reads. Prepared before the software was pinned,
# so it must still match what preparation recorded.
identity = material_identity(paths, profile="acquisition-repairs")
identity_path = output / "verification-19-preflight-input-identity-20260920-v4.json"
assert json.loads(identity_path.read_text()) == identity, "prepared_input_identity_changed"
contents_before = _runtime_contents(root)
(output / "verification-19-preflight-complete-inputs-runtime-before-20260920-v4.json").write_text(json.dumps(contents_before, indent=2, sort_keys=True))

# Software identity: what ran. Separate receipt, separate re-check.
software_started = time.monotonic()
software_inputs = inventory(project)
software_seconds = time.monotonic() - software_started
assert not [key for key in software_inputs if key.startswith(".scratch")], "evidence_pinned_as_software"

started = time.monotonic()
command = [sys.executable, "-m", "pring_cycle", "model-input-preflight", "--runtime-root", str(root), "--model", candidate, "--start", "2026-03-09", "--end", "2026-08-28", "--json"]
env = dict(os.environ, PYTHONPATH="src:.")
# The venv also holds a built copy of the package, so ask the child itself what it
# resolved rather than trusting this driver's own path setup.
probe = "import json; from tools.inputs import imported_package; print(json.dumps(imported_package()))"
imported_package_identity = json.loads(subprocess.run(
    [sys.executable, "-c", probe],
    cwd=project, env=env, capture_output=True, text=True, check=True).stdout)
imported = str(Path(imported_package_identity["path"]) / "material_preflight.py")
assert imported_package_identity["path"] == str(project / "src/pring_cycle"), imported_package_identity["path"]
assert imported_package_identity["files"]["material_preflight.py"], "material_preflight not in imported package"

def read_free_gib():
    result = subprocess.run([
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile", "-Command", "[math]::Round((Get-PSDrive C).Free / 1GB, 2)"
    ], capture_output=True, text=True, timeout=15, check=True)
    return float(result.stdout.strip())


def free_gib():
    """A flaky interop probe must not end a healthy run; only a real reading can."""
    for attempt in range(3):
        try:
            return read_free_gib()
        except Exception:
            if attempt == 2:
                return None
            time.sleep(5)


assert (free_gib() or 0) > 5, "preparation_disk_reserve_unavailable"
with log.open("w") as stream:
    child = subprocess.Popen(command, cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    reason = None
    record = {"command": command, "pid": child.pid, "runtime_root": str(root),
              "identity_file": str(identity_path), "imported_from": imported,
              "software_inputs": software_inputs, "software_inventory_seconds": software_seconds,
              "imported_package": imported_package_identity}
    try:
        while child.poll() is None:
            elapsed = time.monotonic() - started
            remaining = free_gib()
            record.update(state="running", elapsed_seconds=elapsed, c_free_gib=remaining)
            status.write_text(json.dumps(record, indent=2))
            if remaining is not None and remaining < 4:
                reason = "c_disk_reserve"
                break
            if elapsed > 3600:
                reason = "preflight_time_limit"
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
    material_unchanged = material_identity(paths, profile="acquisition-repairs") == identity
    software_unchanged = inventory(project) == software_inputs
    contents_after = _runtime_contents(root)
    changed = sorted(key for key in contents_before.keys() | contents_after.keys() if contents_before.get(key) != contents_after.get(key))
    record.update(runtime_contents_unchanged=not changed, changed_runtime_files=changed)
    record.update(state="finished", exit_code=child.returncode, reason=reason,
                  elapsed_seconds=time.monotonic()-started,
                  frozen_inputs_unchanged=material_unchanged,
                  software_inputs_unchanged=software_unchanged)
    status.write_text(json.dumps(record, indent=2))
    print(json.dumps({k: v for k, v in record.items() if k != "software_inputs"}), flush=True)
    sys.exit(0 if child.returncode == 0 and material_unchanged and software_unchanged
             and reason is None and not changed else 1)
