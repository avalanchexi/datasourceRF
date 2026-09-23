from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter


@pytest.mark.usefixtures("runtime_clock")
def test_warrant_acquisition_recovers_rows_beyond_documented_1000_limit(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    originals = []

    def transport(payload):
        assert payload["api_name"] == "fut_wsr"
        params = payload["params"]
        fields = payload["fields"].split(",")
        rows = []
        for day in ("20260827", "20260828"):
            if not params["start_date"] <= day <= params["end_date"]:
                continue
            for warehouse in range(501):
                row = {
                    "trade_date": day,
                    "symbol": "CU",
                    "warehouse": f"fixture-warehouse-{warehouse}",
                    "pre_vol": None,
                    "vol": 10.0,
                    "vol_chg": None,
                    "unit": "吨",
                    "exchange": "SHFE",
                }
                rows.append([row[field] for field in fields])
        # The official endpoint caps a response at 1000 rows. Two dates contain
        # 501 distinct warehouses each: the initial response necessarily omits 2.
        content = json.dumps({"code": 0, "data": {"fields": fields, "items": rows[:1000]}}).encode()
        originals.append(content)
        return content

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.futures_warrants(
            start_date=date(2026, 8, 27), end_date=date(2026, 8, 28), symbol="CU"
        ),
        definition_version="metric-catalog-v0002",
    )
    assert result.observation_count == 1002
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    assert sum(p.period_end == "2026-08-27" for p in points) == 501
    assert sum(p.period_end == "2026-08-28" for p in points) == 501
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    history = receipts.history()
    assert len(history) == 3
    assert {receipts.read_content(r.acquisition_id, "raw") for r in history} == set(originals)
    assert all(r.state == "validated" for r in history)
    assert all(p.claims[0].parsed_public_available_at is None for p in points)


@pytest.mark.usefixtures("runtime_clock")
def test_saturated_single_day_warrant_response_remains_incomplete(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    fields = ["trade_date", "symbol", "warehouse", "pre_vol", "vol", "vol_chg", "unit", "exchange"]
    content = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": fields,
                "items": [
                    ["20260828", "CU", f"fixture-{index}", None, 10.0, None, "吨", "SHFE"]
                    for index in range(1000)
                ],
            },
        }
    ).encode()
    adapter = TushareContextAdapter("fixture-secret", transport=lambda _: content)
    with pytest.raises(ValueError, match="tushare_warrant_response_truncated"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
            ),
            definition_version="metric-catalog-v0002",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    history = receipts.history()
    assert len(history) == 1 and history[0].state == "failed"
    assert receipts.read_content(history[0].acquisition_id, "raw") == content
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_FUTURES_WARRANTS",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0002",
        )
        == ()
    )
