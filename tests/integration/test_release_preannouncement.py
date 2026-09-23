"""Ticket 25: a release pre-announcement decides the release time before inference does."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import EvidenceRepository
from pring_cycle.freshness import batch_freshness
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_core_history_refresh import historical_response
from tests.integration.test_freshness_contract import monthly, runtime

SCHEDULE_PAGE = (
    Path(__file__).parents[1] / "fixtures" / "official_schedule" / "nbs_2026_release_schedule.html"
).read_bytes()
# Friday 18 September 21:00. A monthly period is due 7 trading days after its release. NBS
# announced August's CPI for 9 September 09:30, so it is due on the 18th; inferred as the
# 8th trading day after 31 August (10 September) it would be due on the 21st.
TARGET = date(2026, 9, 18)
CUTOFF = datetime(2026, 9, 18, 21, tzinfo=ZoneInfo("Asia/Shanghai"))


def cn_schedule(rows: list[tuple[str, str]]) -> bytes:
    fields = ["month", "publish_date", "title", "issuing_org", "data_api"]
    items = [[day[:6], day, "fixture", "国家统计局", api] for api, day in rows]
    return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()


def run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    *,
    schedule: bytes | None,
    page: Callable[[str], bytes],
) -> tuple[RuntimePaths, str, list[str]]:
    """A full run holding July's CPI; TuShare answers ``cn_schedule`` with ``schedule``."""
    install_runtime_clock(monkeypatch, request, CUTOFF.astimezone(UTC))
    calls: list[str] = []

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            api, code = payload["api_name"], payload["params"].get("ts_code")
            if api == "cn_schedule":
                calls.append("cn_schedule")
                if schedule is None:
                    raise OSError("fixture_cn_schedule_unavailable")
                return BytesIO(schedule)
            if api != "trade_cal" and code not in {"000985.CSI", "000012.SH", "NHII.NH"}:
                raise OSError("fixture_context_unavailable")
            return BytesIO(historical_response(payload))

    def schedule_page(url: str) -> bytes:
        calls.append("nbs_page")
        return page(url)

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *h: FixtureOpener())
    monkeypatch.setattr(
        "pring_cycle.eia_html.open_no_redirects",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    monkeypatch.setattr("pring_cycle.release_schedule._fetch_page", schedule_page)
    paths = runtime(tmp_path)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    monthly(
        EvidenceRepository(paths.database),
        "CN_CPI_HEADLINE",
        date(2026, 7, 31),
        unit="percent",
        dimensions={"measure": "yoy", "category": "headline"},
    )
    submitted = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="preannouncement",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = RunRepository(paths.database).get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    return paths, submitted.run_id, calls


def cpi(paths: RuntimePaths, run_id: str) -> dict[str, object]:
    return batch_freshness(paths.database, run_id)["CN_CPI_HEADLINE"]


def schedule_rows(paths: RuntimePaths) -> list[tuple[str, str, str]]:
    connection = sqlite3.connect(paths.database)
    try:
        return connection.execute(
            "SELECT origin, item, publish_date FROM release_schedule ORDER BY origin, item"
        ).fetchall()
    finally:
        connection.close()


def gap_metrics(paths: RuntimePaths) -> dict[str, str]:
    gaps = ProjectionSetRepository(paths.database).current().datasets["cycle_overview"]
    return {str(g["metric_id"]): str(g["category"]) for g in gaps["gap_list"]}


def test_cn_schedule_decides_when_august_cpi_is_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    # TuShare announces 15 September (due the 24th); it wins over the page's 9 September.
    paths, run_id, calls = run(
        tmp_path,
        monkeypatch,
        request,
        schedule=cn_schedule([("cn_cpi", "20260915")]),
        page=lambda url: SCHEDULE_PAGE,
    )

    assert calls[0] == "cn_schedule"
    assert cpi(paths, run_id)["status"] == "awaiting_release"
    assert "CN_CPI_HEADLINE" not in gap_metrics(paths)
    assert ("tushare:cn_schedule", "cn_cpi", "2026-09-15") in schedule_rows(paths)


def test_the_official_schedule_page_is_used_when_cn_schedule_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths, run_id, calls = run(
        tmp_path, monkeypatch, request, schedule=None, page=lambda url: SCHEDULE_PAGE
    )

    # The page says 9 September 09:30: August is due, and July is one period behind.
    assert calls == ["cn_schedule", "nbs_page"]
    row = cpi(paths, run_id)
    assert (row["status"], row["due_period"], row["periods_behind"]) == ("stale", "2026-08-31", 1)
    assert gap_metrics(paths)["CN_CPI_HEADLINE"] == "freshness_gap"
    assert ("nbs:schedule_page", "居民消费价格指数月度报告", "2026-09-09") in schedule_rows(paths)


def test_an_unparsed_announcement_is_discarded_and_inference_decides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths, run_id, _calls = run(
        tmp_path,
        monkeypatch,
        request,
        schedule=b'{"code": 40203, "msg": "no permission"}',
        page=lambda url: b"<html>moved</html>",
    )

    # Inferred: released 10 September, due 21 September, after the cutoff.
    assert cpi(paths, run_id)["status"] == "awaiting_release"
    assert schedule_rows(paths) == []
    assert "CN_CPI_HEADLINE" not in gap_metrics(paths)
