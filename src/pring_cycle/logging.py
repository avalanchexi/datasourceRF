from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from pring_cycle.runtime import RuntimePaths


def write_runtime_event(
    paths: RuntimePaths,
    component: str,
    event_code: str,
    level: str = "info",
) -> None:
    paths.logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    document = {
        "component": component,
        "error_code": None,
        "event_code": event_code,
        "job_id": None,
        "level": level,
        "run_id": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    log_path = paths.logs / f"{component}.jsonl"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    log_path.chmod(0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(document, sort_keys=True) + "\n")
