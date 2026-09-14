"""Hold the real periodic heartbeat at the SQLite close boundary for a shutdown test."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run


def main() -> None:
    paths = RuntimePaths.discover(Path(sys.argv[1]))
    release_gate = int(sys.argv[2])
    closing = threading.Event()
    connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def close(self) -> None:
            if threading.current_thread() is not threading.main_thread():
                # SQL, commit and the eventual close remain real. Only scheduling at
                # the external database boundary is controlled, after the write lock ends.
                assert not self.in_transaction
                closing.set()
                print(json.dumps({"event": "heartbeat_closing"}), flush=True)
                assert os.read(release_gate, 1) == b"1"
            super().close()

    def observed_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        assert "factory" not in kwargs
        return connect(*args, factory=ObservedConnection, **kwargs)

    def retrieve(_event: str) -> None:
        assert closing.wait(timeout=40), "Periodic heartbeat did not reach real close"
        assert sys.stdin.readline().strip() == "finish_run"
        return None

    with patch("sqlite3.connect", side_effect=observed_connect):
        process_pending_run(
            paths,
            report_adapters=(),
            retrieval_adapters={"official": retrieve},
            retrieval_now=datetime(2026, 8, 20, 2, tzinfo=UTC),
            retrieval_release_resolver=lambda _scope, _now: True,
        )
    os.close(release_gate)
    print(json.dumps({"event": "worker_returned"}), flush=True)


if __name__ == "__main__":
    main()
