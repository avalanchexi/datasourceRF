"""Bounded, unauthenticated network recheck after WSL recovery; no config writes."""
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

folder = Path(__file__).resolve().parent
output = folder / "connectivity.json"
assert not output.exists(), "keep prior recheck; do not silently repeat requests"
common = ["--silent", "--show-error", "--head", "--connect-timeout", "5",
          "--max-time", "8", "--write-out", "%{http_code}"]
attempts = []
for label, command in (
    ("wsl_direct", ["wsl", "-d", "Ubuntu-22.04", "-u", "tywin", "--", "curl",
                    *common, "--noproxy", "*", "--output", "/dev/null", "https://chatgpt.com/"]),
    ("windows_direct", ["curl.exe", *common, "--noproxy", "*", "--output", "NUL", "https://chatgpt.com/"]),
    ("windows_previously_observed_proxy", ["curl.exe", *common, "--noproxy", "",
        "--proxy", "http://127.0.0.1:10809", "--output", "NUL", "https://chatgpt.com/"]),
):
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    completed = subprocess.run(command, capture_output=True, timeout=20)
    attempts.append({"route": label, "target": "https://chatgpt.com/", "method": "HEAD",
                     "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat(),
                     "elapsed_seconds": round(time.monotonic() - clock, 3),
                     "exit_code": completed.returncode,
                     "http_status": completed.stdout.decode("ascii", errors="replace").strip(),
                     "error_text": completed.stderr.decode("utf-8", errors="replace").strip(),
                     "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest()})
result = {"reason": "WSL restarted after host disk recovery", "attempts": attempts,
          "authentication_sent": False, "cli_generation_attempts": 0,
          "proxy_configuration_changed": False, "production_writes": 0}
output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
