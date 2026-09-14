"""Subprocess: admit the complete isolated candidate and import its inputs in a fresh process.

The public lifecycle test keeps its own process small; this child exits after the inputs exist.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from pring_cycle.runtime import RuntimePaths  # noqa: E402
from tests.conftest import _clock_datetime  # noqa: E402


class _Capture:
    """The ``readouterr`` part of pytest's capsys, for the admission CLI output."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()

    def readouterr(self) -> object:
        value, self.buffer = self.buffer.getvalue(), io.StringIO()
        return type("Captured", (), {"out": value, "err": ""})()


def main() -> None:
    origin, started = datetime.now(UTC), time.monotonic()

    def now() -> datetime:
        return origin + timedelta(seconds=time.monotonic() - started)

    # The same advancing external timeline as the runtime_clock fixture; the WSL wall clock
    # can step backwards.
    clock_type = _clock_datetime(now)
    for module in ("acquisition", "core_history", "worker", "runs", "retrieval_ledger"):
        importlib.import_module(f"pring_cycle.{module}").datetime = clock_type  # type: ignore[attr-defined]
    lifecycle = importlib.import_module("tests.models.test_isolated_lifecycle")
    lifecycle.datetime = clock_type  # type: ignore[attr-defined]
    capture = _Capture()
    paths = RuntimePaths.discover(Path(sys.argv[1]))
    with contextlib.redirect_stdout(capture.buffer):
        candidate = lifecycle.prepare_isolated_candidate_inputs(paths, capture, now)
    print(json.dumps({"candidate_model_version_id": candidate}), flush=True)


if __name__ == "__main__":
    main()
