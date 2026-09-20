"""Affected heavy acceptance for the period-scoped family recheck, one file at a time."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

project = Path("/mnt/d/cursor/datasourceRF-integrated-20260918")
sys.path.insert(0, str(project))
sys.path.insert(0, str(project / "src"))
from tools.inputs import inventory

output = project / ".scratch/pring-data-acquisition-repair"
status = output / "verification-19-period-scope-heavy-20260920.json"
assert not status.exists(), "heavy_run_already_recorded"
HEAVY = (
    "tests/models/test_isolated_lifecycle.py",
    "tests/integration/test_worker_registered_catalog.py",
    "tests/integration/test_integrated_worker_delivery.py",
    "tests/integration/test_integrated_worker_core_gap.py",
)
env = dict(os.environ, PYTHONPATH="src:.", PYTHONUNBUFFERED="1")
software_before = inventory(project)
probe = "import json; from tools.inputs import imported_package; print(json.dumps(imported_package()))"
imported = json.loads(subprocess.run([sys.executable, "-c", probe], cwd=project, env=env,
                                     capture_output=True, text=True, check=True).stdout)
assert imported["path"] == str(project / "src/pring_cycle"), imported["path"]

record = {"imported_package_path": imported["path"], "files": []}
began = time.monotonic()
for name in HEAVY:
    log = output / ("verification-19-period-scope-heavy-%s-20260920.txt" % Path(name).stem)
    started = time.monotonic()
    with log.open("w") as stream:
        done = subprocess.run([sys.executable, "-m", "pytest", name, "-q", "--durations=10"],
                              cwd=project, env=env, stdout=stream, stderr=subprocess.STDOUT)
    summary = [line for line in log.read_text().splitlines() if line.strip()]
    record["files"].append({"file": name, "exit_code": done.returncode,
                            "seconds": time.monotonic() - started,
                            "summary": summary[-1] if summary else None})
    status.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record["files"][-1]), flush=True)
    if done.returncode != 0:
        record["stopped_after_failure"] = name
        break
record["total_seconds"] = time.monotonic() - began
record["software_inputs_unchanged"] = inventory(project) == software_before
status.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({k: v for k, v in record.items() if k != "files"}), flush=True)
