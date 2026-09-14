"""Subprocess for the Linux native Worker connection-lifetime regression."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.evidence import EvidenceRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run


def main() -> None:
    paths = RuntimePaths.discover(Path(sys.argv[1]))
    runs = RunRepository(paths.database)
    observation: dict[str, object] = {}

    def retrieve(_event: str) -> None:
        def heartbeat() -> None:
            # Same public lease operation and owner as the Worker's periodic thread.
            runs.heartbeat_lease(f"worker-{os.getpid()}")
            print(json.dumps({"event": "heartbeat_finished"}), flush=True)

        print(json.dumps({"event": "query_window"}), flush=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(heartbeat)
            assert sys.stdin.readline().strip() == "query"
            started = time.monotonic()
            try:
                result = EvidenceRepository(paths.database).source_claim_acquisitions_many(
                    ("absent",)
                )
                assert result == {"absent": ()}
                observation.update(status="query_succeeded")
            except sqlite3.OperationalError as error:
                observation.update(
                    status="query_failed",
                    message=str(error),
                    code=error.sqlite_errorcode,
                    name=error.sqlite_errorname,
                    traceback=traceback.format_exc(),
                )
            observation["query_seconds"] = time.monotonic() - started
            pending.result(timeout=15)
        # No evidence is returned: this must remain an auditable unresolved gap.
        return None

    process_pending_run(
        paths,
        report_adapters=(),
        retrieval_adapters={"official": retrieve},
        retrieval_now=datetime(2026, 8, 20, 2, tzinfo=UTC),
        retrieval_release_resolver=lambda _scope, _now: True,
    )
    stored = runs.get(sys.argv[2])
    observation.update(event="result", run_status=stored.status)
    print(json.dumps(observation), flush=True)


if __name__ == "__main__":
    main()
