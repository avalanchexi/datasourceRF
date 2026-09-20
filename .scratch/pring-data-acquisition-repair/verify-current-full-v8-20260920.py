"""Freeze this version, install it, and run the default full suite under supervision.

Software identity, the installed artifact and the material identities are recorded
separately, so the receipt says which code ran, which built artifact it ran from, and
which materials it read.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/mnt/d/cursor/datasourceRF-integrated-20260918")
sys.path.insert(0, str(ROOT))
from tools.inputs import IGNORED_PARTS, digest, inventory

RECORDS = ROOT / ".scratch/pring-data-acquisition-repair"
STAGE = Path("/tmp/datasourceRF-current-verify-20260920-v8")
FROZEN = STAGE / "project"
SITE = STAGE / "site"
RECEIPT = RECORDS / "verification-current-full-v8-20260920.json"
LOG = RECORDS / "verification-current-full-v8-20260920.txt"
COPY_IGNORES = (".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv")
TIME_LIMIT = 5 * 3600
DISK_FLOOR_GIB = 4


def package_inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(root).parts)
    }


def free_gib() -> float | None:
    for attempt in range(3):
        try:
            done = subprocess.run(
                ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile",
                 "-Command", "[math]::Round((Get-PSDrive C).Free / 1GB, 2)"],
                capture_output=True, text=True, timeout=20, check=True)
            return float(done.stdout.strip())
        except Exception:
            if attempt == 2:
                return None
            time.sleep(5)
    return None


assert not RECEIPT.exists(), "full_run_already_recorded"
assert not STAGE.exists(), "stage_exists"
start_free = free_gib()
assert start_free is not None and start_free > 10, f"c_disk_reserve_unavailable: {start_free}"

# The version under test, pinned before anything is copied.
software_inputs = inventory(ROOT)
assert not [key for key in software_inputs if key.startswith(".scratch")], "evidence_pinned_as_software"

STAGE.mkdir(parents=False, exist_ok=False)
shutil.copytree(ROOT, FROZEN, ignore=shutil.ignore_patterns(*COPY_IGNORES), symlinks=True)
assert inventory(FROZEN) == software_inputs, "frozen_copy_differs_from_source"

built = subprocess.run(
    ["uv", "pip", "install", "--no-deps", "--target", str(SITE), str(FROZEN)],
    capture_output=True, text=True, check=False)
assert built.returncode == 0, built.stderr[-2000:]
package_hashes = package_inventory(SITE / "pring_cycle")
assert package_hashes == package_inventory(FROZEN / "src/pring_cycle"), "installed_artifact_differs"

env = {**os.environ,
       "PYTHONPATH": os.pathsep.join((str(SITE), str(FROZEN))),
       "PYTHONUNBUFFERED": "1",
       "PRING_TEST_MATERIALS_ROOT": "/home/tywin/.cache/pring-cycle/test-materials",
       "CURRENT_VERIFICATION_RECORDS": str(RECORDS),
       "CURRENT_VERIFICATION_BASETEMP": str(STAGE / "pytest")}
env.pop("PYTEST_ADDOPTS", None)
env.pop("PYTEST_PLUGINS", None)

probe = '''import hashlib, json, pring_cycle
from pathlib import Path
from pring_cycle.runtime import RuntimePaths
from tests.models.test_isolated_lifecycle import material_identity, encode
result = {"imported": pring_cycle.__file__, "profiles": {}}
for profile in ("legacy", "acquisition-repairs"):
    identity = material_identity(RuntimePaths.discover(Path("/tmp/current-identity-only")), profile=profile)
    key = hashlib.sha256(encode(identity)).hexdigest()
    stored = Path("/home/tywin/.cache/pring-cycle/test-materials") / key
    result["profiles"][profile] = {"key": key, "identity": identity, "cache_exists": stored.is_dir()}
print(json.dumps(result))'''
identities = json.loads(subprocess.check_output([sys.executable, "-c", probe], cwd=FROZEN, env=env, text=True))
assert Path(identities["imported"]).is_relative_to(SITE), identities["imported"]

command = [sys.executable, "-m", "pytest", "-q", "--durations=30",
           "-o", "faulthandler_timeout=0", "--basetemp", str(STAGE / "pytest")]
document: dict[str, object] = {
    "state": "prepared", "started_at": datetime.now(UTC).isoformat(),
    "source": str(ROOT), "snapshot": str(FROZEN), "site": str(SITE),
    "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "source_includes_reviewed_uncommitted_work": True,
    "software_inputs": software_inputs, "package_hashes": package_hashes,
    "material_bindings": identities, "command": command,
    "scope": "default discovery, no selectors", "log": str(LOG),
    "c_free_gib_start": start_free,
}
RECEIPT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")

started = time.monotonic()
reason = None
with LOG.open("w") as stream:
    child = subprocess.Popen(command, cwd=FROZEN, env=env, stdout=stream,
                             stderr=subprocess.STDOUT, start_new_session=True)
    document.update(state="running", pid=child.pid)
    try:
        while child.poll() is None:
            elapsed = time.monotonic() - started
            remaining = free_gib()
            document.update(elapsed_seconds=elapsed, c_free_gib=remaining)
            RECEIPT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
            if remaining is not None and remaining < DISK_FLOOR_GIB:
                reason = "c_disk_reserve"
                break
            if elapsed > TIME_LIMIT:
                reason = "suite_time_limit"
                break
            time.sleep(30)
    except Exception as error:
        reason = f"supervisor_error:{type(error).__name__}:{error}"
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

lines = [line for line in LOG.read_text(errors="replace").splitlines() if line.strip()]
document.update(
    state="finished", exit_code=child.returncode, supervisor_reason=reason,
    elapsed_seconds=time.monotonic() - started,
    frozen_inputs_unchanged=inventory(FROZEN) == software_inputs,
    source_inputs_unchanged=inventory(ROOT) == software_inputs,
    installed_artifact_unchanged=package_inventory(SITE / "pring_cycle") == package_hashes,
    log_sha256=digest(LOG), summary=lines[-1] if lines else None,
    c_free_gib_end=free_gib(),
)
RECEIPT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({k: document[k] for k in (
    "state", "exit_code", "supervisor_reason", "elapsed_seconds", "frozen_inputs_unchanged",
    "source_inputs_unchanged", "installed_artifact_unchanged", "summary")}), flush=True)
