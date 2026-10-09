"""pytest plugin: write every test phase's duration, one JSON line each (ticket 24).

``--durations=N`` prints only the slowest N phases and keeps nothing, so a long run that was
not asked for more cannot be ranked afterwards. ``tools/check.py`` loads this with
``-p tools.timings`` and summarizes the file once pytest exits.
"""

from __future__ import annotations

import json
from typing import IO

import pytest


class _Recorder:
    def __init__(self, handle: IO[str]) -> None:
        self._handle = handle

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        record = {"node": report.nodeid, "when": report.when, "duration": report.duration}
        self._handle.write(json.dumps(record) + "\n")

    def pytest_unconfigure(self) -> None:
        self._handle.close()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--timings-file",
        default=None,
        help="Write each test's setup, call and teardown duration here as JSON lines",
    )


def pytest_configure(config: pytest.Config) -> None:
    path = config.getoption("--timings-file")
    if path:
        # Line buffered: an interrupted run still leaves the phases it finished.
        handle = open(path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        config.pluginmanager.register(_Recorder(handle), "timings-recorder")
