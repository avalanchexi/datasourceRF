"""Ticket 22: a core TuShare misses is filled from the CSI official page, or held."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.freshness import TradingCalendar, public_available_at
from pring_cycle.models import ModelRepository
from pring_cycle.official_core import parse_csindex_perf
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response

SAMPLES = Path(__file__).parents[1] / "fixtures" / "csindex"
TARGET = date(2026, 8, 3)
SHANGHAI = ZoneInfo("Asia/Shanghai")


def sample(code: str) -> bytes:
    return (SAMPLES / f"index_perf_{code}_20260820_20260831.json").read_bytes()


@pytest.mark.parametrize(
    ("metric_id", "code", "close"),
    [
        ("CN_EQUITY_CORE_000985", "000985", 5935.03),
        ("CN_BOND_CORE_000012", "000012", 230.11),
    ],
)
def test_parser_reads_value_period_and_publication_from_saved_pages(
    metric_id: str, code: str, close: float
) -> None:
    bars = parse_csindex_perf(
        sample(code), metric_id=metric_id, start=date(2026, 8, 20), end=date(2026, 8, 31)
    )
    friday = next(bar for bar in bars if bar.business_date == date(2026, 8, 28))

    assert len(bars) == 8
    assert friday.close == close
    assert friday.source_code == code
    # The page names trading days only; publication is the registered 17:00 index update.
    assert public_available_at(
        metric_id, friday.business_date, None, TradingCalendar()
    ) == datetime.combine(friday.business_date, time(17), SHANGHAI)


def test_parser_refuses_another_index_or_a_day_outside_the_request() -> None:
    with pytest.raises(ValueError, match="csindex_row_identity_mismatch"):
        parse_csindex_perf(
            sample("000012"),
            metric_id="CN_EQUITY_CORE_000985",
            start=date(2026, 8, 20),
            end=date(2026, 8, 31),
        )
    with pytest.raises(ValueError, match="csindex_period_mismatch"):
        parse_csindex_perf(
            sample("000985"),
            metric_id="CN_EQUITY_CORE_000985",
            start=date(2026, 8, 20),
            end=date(2026, 8, 27),
        )


def csindex_page(url: str, *, code: str | None = None) -> bytes:
    """A CSI page for the requested index and range, rising like the TuShare fixture."""
    from urllib.parse import parse_qs, urlsplit

    query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
    start = datetime.strptime(query["startDate"], "%Y%m%d").date()
    end = datetime.strptime(query["endDate"], "%Y%m%d").date()
    days = [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    rows = [
        {
            "tradeDate": day.strftime("%Y%m%d"),
            "indexCode": code or query["indexCode"],
            "close": 100.0 + i,
            "change": 1.0,
            "changePct": 1.0,
        }
        for i, day in enumerate(days)
    ]
    return json.dumps({"code": "200", "msg": "Success", "data": rows}).encode()


def full_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    tushare_fails: set[str],
    csindex: Callable[[str], bytes],
) -> tuple[RuntimePaths, Any, list[str]]:
    """A full run where TuShare never answers for ``tushare_fails`` and CSI serves ``csindex``."""
    calls: list[str] = []

    class FixtureOpener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            code = payload["params"].get("ts_code")
            if payload["api_name"] != "trade_cal":
                calls.append(f"tushare:{code}")
            if code in tushare_fails or (
                payload["api_name"] != "trade_cal"
                and code not in {"000985.CSI", "000012.SH", "NHII.NH"}
            ):
                raise OSError("fixture_unavailable")
            return BytesIO(historical_response(payload))

    def csindex_fetch(url: str) -> bytes:
        calls.append("csindex")
        return csindex(url)

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *h: FixtureOpener())
    monkeypatch.setattr(
        "pring_cycle.eia_html.open_no_redirects",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    monkeypatch.setattr("pring_cycle.official_core._fetch", csindex_fetch)
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=TARGET.isoformat(),
        client_request_id="core-fill",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    stored = RunRepository(paths.database).get(run.run_id)
    assert stored.status == "completed", stored.error_classification
    return paths, ProjectionSetRepository(paths.database).current(), calls


def test_a_csi_core_tushare_misses_is_filled_from_the_official_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, projection, calls = full_run(
        tmp_path, monkeypatch, tushare_fails={"000985.CSI"}, csindex=csindex_page
    )
    overview = projection.datasets["cycle_overview"]

    # TuShare is asked once more for the missing core only, then the CSI page once.
    assert calls.count("tushare:000985.CSI") == 2
    assert calls.count("tushare:000012.SH") == 1
    assert calls.count("csindex") == 1
    assert overview["current_stage"] is not None
    assert overview["core_carry_forward"] == []
    points = EvidenceRepository(paths.database).metric_series(
        "CN_EQUITY_CORE_000985",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    target = next(p for p in points if p.period_end == TARGET.isoformat())
    assert {claim.provider for claim in target.claims} == {"csindex"}


def test_an_unparsable_official_page_leaves_the_core_to_be_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _paths, projection, calls = full_run(
        tmp_path,
        monkeypatch,
        tushare_fails={"000985.CSI"},
        csindex=lambda url: csindex_page(url, code="000300"),
    )
    overview = projection.datasets["cycle_overview"]

    assert calls.count("csindex") == 1
    assert (overview["current_stage"], overview["stage_reason"]) == (None, "core_data_pending")


def test_the_commodity_core_has_no_official_page_and_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _paths, projection, calls = full_run(
        tmp_path, monkeypatch, tushare_fails={"NHII.NH"}, csindex=csindex_page
    )
    overview = projection.datasets["cycle_overview"]

    assert calls.count("tushare:NHII.NH") == 2
    assert calls.count("csindex") == 0
    assert (overview["current_stage"], overview["stage_reason"]) == (None, "core_data_pending")
