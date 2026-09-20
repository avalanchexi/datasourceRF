"""Where the complete-window preflight spends 30 minutes: cost against window length.

The capped run left no stage output, so measure bounded windows on the same prepared
inputs instead of rerunning the full window. Read-only: the capped run recorded
runtime_contents_unchanged, so reusing these inputs adds no material risk.
"""
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

project = Path("/mnt/d/cursor/datasourceRF-integrated-20260918")
sys.path.insert(0, str(project))
sys.path.insert(0, str(project / "src"))
from pring_cycle.runtime import RuntimePaths
from tests.models.test_isolated_lifecycle import material_identity, _runtime_contents

root = Path("/tmp/datasourceRF-preflight-inputs-20260919-v3")
output = project / ".scratch/pring-data-acquisition-repair"
capped = json.loads((output / "verification-19-preflight-complete-inputs-terminal-20260919-v3.json").read_text())
assert capped["state"] == "finished" and capped["reason"] == "preflight_time_limit"
assert capped["runtime_contents_unchanged"] and capped["frozen_inputs_unchanged"]
candidate = capped["command"][capped["command"].index("--model") + 1]
paths = RuntimePaths.discover(root)
identity = material_identity(paths, profile="acquisition-repairs")
assert json.loads((output / "verification-19-preflight-input-identity-20260919-v3.json").read_text()) == identity
contents_before = _runtime_contents(root)

env = dict(os.environ, PYTHONPATH="src:.")
WINDOWS = (("2026-08-28", "2026-08-28"), ("2026-08-24", "2026-08-28"),
           ("2026-08-14", "2026-08-28"), ("2026-07-31", "2026-08-28"))
records = []
for start, end in WINDOWS:
    command = [sys.executable, "-m", "pring_cycle", "model-input-preflight", "--runtime-root", str(root),
               "--model", candidate, "--start", start, "--end", end, "--json"]
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    began = time.monotonic()
    try:
        done = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=420)
        elapsed = time.monotonic() - began
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        payload = json.loads(done.stdout) if done.stdout.strip() else None
        records.append({
            "start": start, "end": end, "seconds": elapsed, "exit_code": done.returncode,
            "checked_business_dates": len(payload["checked_business_dates"]) if payload else None,
            "calendar_status": payload["calendar"]["status"] if payload else None,
            "calendar_dates": len(payload["calendar"]["dates"]) if payload else None,
            "gaps": len(payload["gaps"]) if payload else None,
            "optional_gaps": len(payload["optional_gaps"]) if payload else None,
            "status": payload["status"] if payload else None,
            "max_child_rss_kib": usage.ru_maxrss,
            "child_cpu_seconds": (usage.ru_utime + usage.ru_stime) - (usage_before.ru_utime + usage_before.ru_stime),
            "stderr_tail": done.stderr.strip()[-400:] or None,
        })
    except subprocess.TimeoutExpired:
        records.append({"start": start, "end": end, "seconds": time.monotonic() - began,
                        "exit_code": None, "timeout": 420})
    print(json.dumps(records[-1]), flush=True)

contents_after = _runtime_contents(root)
changed = sorted(key for key in contents_before.keys() | contents_after.keys()
                 if contents_before.get(key) != contents_after.get(key))
document = {"runtime_root": str(root), "model_version_id": candidate, "windows": records,
            "runtime_contents_unchanged": not changed, "changed_runtime_files": changed,
            "material_identity_unchanged": material_identity(paths, profile="acquisition-repairs") == identity}
(output / "verification-19-preflight-window-cost-20260919.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({k: v for k, v in document.items() if k != "windows"}), flush=True)
