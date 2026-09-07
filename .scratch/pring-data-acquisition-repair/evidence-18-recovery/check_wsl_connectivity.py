"""Corrected WSL argv boundary: --exec prevents shell wildcard expansion."""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

folder = Path(__file__).resolve().parent
destination = folder / "wsl-connectivity-corrected.json"
assert not destination.exists(), "preserve the prior attempt"
attempts = []
for route, options in (("direct", ["--noproxy", "*"]),
                        ("loopback_proxy", ["--proxy", "http://127.0.0.1:10809", "--noproxy", ""])):
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    command = ["wsl", "-d", "Ubuntu-22.04", "-u", "tywin", "--exec", "curl",
               "--silent", "--show-error", "--head", "--connect-timeout", "5",
               "--max-time", "8", "--write-out", "%{http_code}", "--output", "/dev/null",
               *options, "https://chatgpt.com/"]
    result = subprocess.run(command, capture_output=True, timeout=20)
    attempts.append({"route": route, "started_at": started,
                     "completed_at": datetime.now(timezone.utc).isoformat(),
                     "elapsed_seconds": round(time.monotonic() - clock, 3),
                     "exit_code": result.returncode,
                     "stdout": result.stdout.decode(errors="replace"),
                     "stderr": result.stderr.decode(errors="replace")})
output = {"corrects": "connectivity.json:attempts[0]",
          "prior_wsl_probe_valid": False,
          "prior_probe_issue": "WSL default shell expanded --noproxy * into workspace names; resulting multi-URL requests and combined output cannot measure a single ChatGPT probe.",
          "wsl_invocation": "--exec curl (no shell)", "attempts": attempts,
          "authentication_sent": False, "cli_generation_attempts": 0,
          "configuration_writes": 0, "production_writes": 0}
destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, indent=2))
