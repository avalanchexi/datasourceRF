"""A daily value that is already verified locally is not fetched a second time.

The agreed acquisition rule for daily series is T+1: the value for a session is fetched after
that session's publication, and once it has been checked it is never re-requested. Historical
originals that no daily fetch can produce stay recorded as their own gaps elsewhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.worker import process_pending_run
from tests.integration.test_full_run_retrieval import (
    prepare,
    record_core_calendar,
    seed_core_history,
)


def context_requests(monkeypatch: pytest.MonkeyPatch, requested: list[str]) -> None:
    """Record every TuShare context call; none of them may reach the network."""
    import json
    from io import BytesIO

    class Opener:
        def open(self, request: object, *, timeout: float) -> BytesIO:
            payload = json.loads(getattr(request, "data", b"{}"))
            requested.append(str(payload.get("api_name")))
            raise OSError("fixture source unavailable")

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *_headers: Opener())

    def page_offline(url: str) -> None:
        raise OSError("fixture history page offline")

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", page_offline)


@pytest.mark.usefixtures("runtime_clock")
def test_a_verified_daily_series_is_not_requested_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, runs = prepare(tmp_path)
    # The core daily history through the target session is already stored and verified.
    seed_core_history(paths)
    requested: list[str] = []
    context_requests(monkeypatch, requested)

    for index in (1, 2):
        if index > 1:
            # Each run fetches its calendar; the first run's retention dropped the response.
            record_core_calendar(paths)
        run = runs.submit_manual_full(
            target_business_date="2026-08-28",
            client_request_id=f"daily-reacquisition-{index}",
            model_version_id="model-v0001",
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        stored = runs.get(run.run_id)
        assert stored.status == "completed", stored.error_classification
        plan = runs.full_retrieval_plan(run.run_id)
        core = [
            item
            for item in plan["initial"]["requirements"]
            if item.get("metric_id") == "CN_EQUITY_CORE_000985"
            and item.get("period") == "2026-08-28"
        ]
        # The stored value satisfies the requirement, so the plan asks for nothing on it.
        assert core and all(item["status"] == "local_complete" for item in core)
        assert not [
            gap
            for gap in plan["final"]["gaps"]
            if gap["metric_id"] == "CN_EQUITY_CORE_000985" and not gap["complete"]
        ]
    # Neither run asked the daily core APIs again.
    assert "daily" not in requested and "index_daily" not in requested
