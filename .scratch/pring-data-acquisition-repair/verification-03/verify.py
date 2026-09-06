"""Run ticket 03 final gates on the installed package in isolated WSL storage."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

root = Path.cwd()
folder = root / ".scratch/pring-data-acquisition-repair/verification-03"
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env["PYTHONPYCACHEPREFIX"] = "/home/tywin/.cache/pring-cycle/bytecode"
env["UV_PROJECT_ENVIRONMENT"] = "/home/tywin/.local/share/pring-cycle/dev-venv"
commands = [
    ["/home/tywin/.local/bin/uv", "sync", "--locked", "--offline", "--extra", "dev", "--no-editable", "--reinstall-package", "pring-cycle"],
    [sys.executable, "-m", "ruff", "check", "src", "tests"],
    [sys.executable, "-m", "mypy"],
    [sys.executable, "-m", "pytest", "-q", "--basetemp=/home/tywin/.cache/pring-cycle/verification/repair-03-full-" + uuid4().hex],
    [sys.executable, str(folder / "official_sample.py")],
]
paths = subprocess.check_output(["git", "diff", "--cached", "--name-only", "ff5e347"], text=True).splitlines()
receipt = {
    "implementation_base": "ff5e34781ccc91f65c4c279f16b6a6d98b7714df",
    "test_environment": "WSL Ubuntu-22.04, installed package, PYTHONPATH unset",
    "runtime_isolation": "WSL native verification cache; no live runtime writes",
    "file_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths if p.startswith(("src/", "tests/"))},
    "checks": [],
}
for command in commands:
    print("RUN " + " ".join(command), flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
    receipt["checks"].append({"command": command, "exit_code": result.returncode,
        "duration_seconds": round(time.monotonic() - started, 2), "stdout": result.stdout, "stderr": result.stderr})
    (folder / "checks.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout + result.stderr, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
