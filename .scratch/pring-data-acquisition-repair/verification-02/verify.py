"""Run ticket 02 gates against an installed package in isolated WSL storage."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path.cwd()
receipt_path = root / ".scratch/pring-data-acquisition-repair/verification-02/checks.json"
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env["PYTHONPYCACHEPREFIX"] = "/home/tywin/.cache/pring-cycle/bytecode"
env["UV_PROJECT_ENVIRONMENT"] = "/home/tywin/.local/share/pring-cycle/dev-venv"
commands = [
    ["/home/tywin/.local/bin/uv", "sync", "--locked", "--offline", "--extra", "dev",
     "--no-editable", "--reinstall-package", "pring-cycle"],
    [sys.executable, "-m", "ruff", "check", "src", "tests"],
    [sys.executable, "-m", "mypy"],
    [sys.executable, "-m", "pytest", "-q",
     "--basetemp=/home/tywin/.cache/pring-cycle/verification/repair-02-full"],
]
paths = ["src/pring_cycle/" + name for name in (
    "acquisition.py", "core_history.py", "evidence.py", "source_adapters.py",
    "storage.py", "web.py", "worker.py", "migrations/versions/0014_acquisition_receipts.py",
)] + ["tests/integration/test_core_history_refresh.py"]
receipt = {
    "implementation_base": "f5c88befe1a8ea4056ebc8aba54b735c2ccd6e59",
    "test_environment": "WSL Ubuntu-22.04, installed package, PYTHONPATH unset",
    "runtime_isolation": "WSL native verification cache; no live runtime writes",
    "file_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths},
    "checks": [],
}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
for command in commands:
    print("RUN " + " ".join(command), flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    receipt["checks"].append({
        "command": command, "exit_code": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 2),
        "stdout": result.stdout, "stderr": result.stderr,
    })
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout + result.stderr, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
