"""Replay the 10-15 full run on an isolated copy with the worktree's code, offline.

Usage: python replay_1015.py <replay root> <worktree> <report json>

Every HTTP request is answered from the originals the 10-15 run (and earlier runs of the
copy) stored: TuShare by api_name and params, Tavily/Exa by query, any other address by its
URL. A request with no stored original fails as offline. Name resolution is loopback only,
the AI web search is off and no report adapter is given, so nothing leaves the machine and
no AI is called. The clock starts at the original run's acceptance.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from email.message import Message
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.error import URLError

ROOT = Path(sys.argv[1])
WORKTREE = Path(sys.argv[2])
REPORT = Path(sys.argv[3])
ORIGINAL_RUN = "run-2b21b77b4968f3bbcfc3"
ACCEPTED = datetime(2026, 10, 16, 7, 52, 4, tzinfo=UTC)
SYSTEM_AS_OF = datetime(2026, 10, 16, 8, 8, 36, 976822, tzinfo=UTC)
DATE_KEYS = {"start_date", "end_date", "start_m", "end_m", "start_q", "end_q", "trade_date"}
sys.path.insert(0, str(WORKTREE))

# --- offline guard ---------------------------------------------------------------------
_resolve = socket.getaddrinfo


def _loopback_only(host: Any, *args: Any, **kwargs: Any) -> Any:
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise socket.gaierror(socket.EAI_NONAME, f"replay_offline:{host}")
    return _resolve(host, *args, **kwargs)


socket.getaddrinfo = _loopback_only  # type: ignore[assignment]
_popen = subprocess.Popen


class _NoAiPopen(_popen):  # type: ignore[misc,valid-type]
    def __init__(self, args: Any, *rest: Any, **kwargs: Any) -> None:
        first = args[0] if isinstance(args, list | tuple) else str(args).split()[0]
        if Path(str(first)).name in {"codex", "claude"}:
            raise RuntimeError("replay_never_calls_ai")
        super().__init__(args, *rest, **kwargs)


subprocess.Popen = _NoAiPopen  # type: ignore[misc]

# --- stored originals -------------------------------------------------------------------
database = ROOT / "data" / "pring-cycle.sqlite3"
connection = sqlite3.connect(database)
connection.row_factory = sqlite3.Row
by_url: dict[str, str] = {}
by_tushare: dict[tuple[str, str], str] = {}
by_tushare_loose: dict[tuple[str, str], str] = {}
by_query: dict[str, str] = {}
# Oldest first, the original run's last, so the newest original wins.
for row in connection.execute(
    "SELECT a.provider, a.api_name, a.parameters_json, a.raw_hash, "
    "o.run_id = ? AS original FROM acquisition_request a "
    "LEFT JOIN full_run_acquisition o USING(acquisition_id) "
    "WHERE a.raw_hash IS NOT NULL ORDER BY original, a.started_at",
    (ORIGINAL_RUN,),
):
    params = json.loads(row["parameters_json"] or "{}")
    raw = str(row["raw_hash"])
    if row["provider"] == "tushare":
        by_tushare[(row["api_name"], json.dumps(params, sort_keys=True))] = raw
        loose = {k: v for k, v in params.items() if k not in DATE_KEYS}
        by_tushare_loose[(row["api_name"], json.dumps(loose, sort_keys=True))] = raw
    elif row["provider"] in {"tavily", "exa"} and "query" in params:
        by_query[str(params["query"])] = raw
    for key in ("source_url", "endpoint"):
        if isinstance(params.get(key), str):
            by_url[params[key]] = raw
connection.close()

served: list[dict[str, str]] = []


def _artifact(raw_hash: str) -> bytes:
    return (ROOT / "data" / "artifacts" / "sha256" / raw_hash[:2] / raw_hash).read_bytes()


def _media(url: str, content: bytes) -> str:
    lowered = url.lower().split("?")[0]
    for suffix, media in (
        (".zip", "application/zip"),
        (".csv", "text/csv"),
        (".json", "application/json"),
        (".txt", "text/plain"),
    ):
        if lowered.endswith(suffix):
            return media
    if content.lstrip()[:1] in {b"{", b"["}:
        return "application/json"
    return "text/html; charset=utf-8"


class _Response(BytesIO):
    status = 200
    reason = "OK"

    def __init__(self, content: bytes, url: str) -> None:
        super().__init__(content)
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = _media(url, content)

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return 200

    def info(self) -> Message:
        return self.headers


def _replay_open(self: Any, fullurl: Any, data: Any = None, timeout: Any = None) -> _Response:
    request = fullurl if isinstance(fullurl, urllib.request.Request) else None
    url = request.full_url if request is not None else str(fullurl)
    body = (request.data if request is not None else data) or b""
    raw = None
    key = url
    if url.startswith("https://api.tushare.pro"):
        payload = json.loads(body)
        params = payload.get("params") or {}
        key = f"tushare:{payload['api_name']}:{json.dumps(params, sort_keys=True)}"
        raw = by_tushare.get((payload["api_name"], json.dumps(params, sort_keys=True)))
        if raw is None:
            loose = {k: v for k, v in params.items() if k not in DATE_KEYS}
            raw = by_tushare_loose.get((payload["api_name"], json.dumps(loose, sort_keys=True)))
    elif url in {"https://api.tavily.com/search", "https://api.exa.ai/search"}:
        query = str(json.loads(body).get("query"))
        key = f"search:{query}"
        raw = by_query.get(query)
    else:
        raw = by_url.get(url)
    served.append({"request": key[:300], "served": raw or "offline"})
    if raw is None:
        raise URLError("replay_original_not_stored")
    return _Response(_artifact(raw), url)


urllib.request.OpenerDirector.open = _replay_open  # type: ignore[method-assign]

# --- clock ------------------------------------------------------------------------------
from tests.conftest import _clock_datetime, _skipping_pacing  # noqa: E402

started = monotonic()


def _now() -> datetime:
    return ACCEPTED + timedelta(seconds=monotonic() - started)


import pring_cycle.tushare_quota as tushare_quota  # noqa: E402

tushare_quota.PACING = _skipping_pacing()
clock = _clock_datetime(_now)
for module in ("acquisition", "core_history", "worker", "runs", "retrieval_ledger"):
    __import__(f"pring_cycle.{module}")
    setattr(sys.modules[f"pring_cycle.{module}"], "datetime", clock)

# --- the run ----------------------------------------------------------------------------
import pring_cycle  # noqa: E402
from pring_cycle.projections import ProjectionSetRepository  # noqa: E402
from pring_cycle.runs import RunRepository  # noqa: E402
from pring_cycle.runtime import RuntimePaths  # noqa: E402
from pring_cycle.worker import process_pending_run  # noqa: E402

paths = RuntimePaths.discover(ROOT)
assert paths.database == database, paths.database
runs = RunRepository(paths.database)
run = runs.submit_manual_full(
    target_business_date="2026-10-15",
    client_request_id="wg07-replay-1015",
    model_version_id="model-v0015",
    system_as_of=SYSTEM_AS_OF,
    cutoff_mode="explicit",
)
began = monotonic()
process_pending_run(paths, report_adapters=())
stored = runs.get(run.run_id)
projection = (
    ProjectionSetRepository(paths.database).get(stored.projection_set_id)
    if stored.projection_set_id
    else None
)
REPORT.write_text(
    json.dumps(
        {
            "code": str(Path(pring_cycle.__file__).parent),
            "run_id": run.run_id,
            "status": stored.status,
            "error": stored.error_classification,
            "projection_set_id": stored.projection_set_id,
            "seconds": round(monotonic() - began, 1),
            "gap_list": projection.datasets["cycle_overview"]["gap_list"] if projection else None,
            "coverage": projection.datasets["macro"].get("coverage") if projection else None,
            "served": served,
        },
        ensure_ascii=False,
        indent=1,
        default=str,
    ),
    encoding="utf-8",
)
print(run.run_id, stored.status, stored.error_classification, stored.projection_set_id)
