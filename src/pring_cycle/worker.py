from __future__ import annotations

import os
import signal
import threading
from datetime import UTC, datetime

from pring_cycle.logging import write_runtime_event
from pring_cycle.runtime import RuntimeNotInitializedError, RuntimePaths
from pring_cycle.storage import database_health, record_worker_heartbeat


def run_worker(paths: RuntimePaths) -> None:
    if database_health(paths.database)["status"] != "ok":
        raise RuntimeNotInitializedError("runtime_not_initialized")

    stopped = threading.Event()

    def request_stop(_signal_number: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    started_at = datetime.now(UTC)
    write_runtime_event(paths, "worker", "worker_started")
    try:
        while not stopped.is_set():
            record_worker_heartbeat(
                paths.database,
                process_id=os.getpid(),
                started_at=started_at,
                heartbeat_at=datetime.now(UTC),
            )
            stopped.wait(1)
    finally:
        write_runtime_event(paths, "worker", "worker_stopped")
