from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter, parse_warrant_acquisition


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


# Shanghai rubber in the shape TuShare delivered Zhengzhou cotton in, 2026-09-23/24
# (ADR-0029): the exchange report lists a warehouse per year, grade and origin, which
# TuShare drops, so one warehouse comes back as several rows, some identical in every field.
# Cotton itself now comes from CZCE's own report (ADR-0032).
WARRANT_FIELDS = [
    "trade_date",
    "symbol",
    "warehouse",
    "pre_vol",
    "vol",
    "vol_chg",
    "unit",
    "exchange",
]
COTTON_ROWS = [
    # 衡水棉麻: 422 then 419 in total; -4 reported where the totals moved by -3.
    ["20260923", "RU", "衡水棉麻", None, 301, 0, "吨", "SHFE"],
    ["20260923", "RU", "衡水棉麻", None, 79, -1, "吨", "SHFE"],
    ["20260923", "RU", "衡水棉麻", None, 42, 0, "吨", "SHFE"],
    ["20260924", "RU", "衡水棉麻", None, 298, -3, "吨", "SHFE"],
    ["20260924", "RU", "衡水棉麻", None, 78, -1, "吨", "SHFE"],
    ["20260924", "RU", "衡水棉麻", None, 43, 0, "吨", "SHFE"],
    # 豫棉物流: two identical rows each day; the change agrees with the totals.
    ["20260923", "RU", "豫棉物流", None, 12, 0, "吨", "SHFE"],
    ["20260923", "RU", "豫棉物流", None, 12, 0, "吨", "SHFE"],
    ["20260924", "RU", "豫棉物流", None, 12, 0, "吨", "SHFE"],
    ["20260924", "RU", "豫棉物流", None, 12, 0, "吨", "SHFE"],
    ["20260924", "RU", "豫棉物流", None, 5, 5, "吨", "SHFE"],
]


def cotton_response(payload: dict[str, object]) -> bytes:
    fields = str(payload["fields"]).split(",")
    rows = [dict(zip(WARRANT_FIELDS, row, strict=True)) for row in COTTON_ROWS]
    return json.dumps(
        {"code": 0, "data": {"fields": fields, "items": [[r[f] for f in fields] for r in rows]}}
    ).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_warehouse_rows_are_held_as_warehouse_totals(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("fixture-secret", transport=cotton_response)

    adapter.acquire_scalars(
        paths,
        lambda: adapter.futures_warrants(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24), symbol="RU"
        ),
        definition_version="metric-catalog-v0002",
    )

    points = EvidenceRepository(paths.database).metric_series(
        "CN_FUTURES_WARRANTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0002",
    )
    held = {
        (p.period_end, p.dimensions["warehouse"], p.dimensions["measure"]): p.selected_value
        for p in points
    }
    assert held == {
        ("2026-09-23", "衡水棉麻", "registered_receipts"): 422.0,
        ("2026-09-23", "衡水棉麻", "registered_receipts_change"): -1.0,
        ("2026-09-23", "豫棉物流", "registered_receipts"): 24.0,
        ("2026-09-23", "豫棉物流", "registered_receipts_change"): 0.0,
        ("2026-09-24", "衡水棉麻", "registered_receipts"): 419.0,
        ("2026-09-24", "衡水棉麻", "registered_receipts_change"): -4.0,
        ("2026-09-24", "豫棉物流", "registered_receipts"): 29.0,
        ("2026-09-24", "豫棉物流", "registered_receipts_change"): 5.0,
    }


@pytest.mark.usefixtures("runtime_clock")
def test_warehouse_change_that_disagrees_with_the_totals_is_noted_not_rejected(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("fixture-secret", transport=cotton_response)

    adapter.acquire_scalars(
        paths,
        lambda: adapter.futures_warrants(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24), symbol="RU"
        ),
        definition_version="metric-catalog-v0002",
    )

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = receipts.history()
    assert receipt.state == "validated"
    notes = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))[
        "warrant_reconciliation"
    ]
    # The first delivered day has no earlier total in the delivery to check against.
    assert notes["unchecked_dates"] == ["2026-09-23"]
    assert notes["mismatches"] == [
        {
            "business_date": "2026-09-24",
            "warehouse": "衡水棉麻",
            "exchange": "SHFE",
            "total": 419.0,
            "previous_total": 422.0,
            "change_sum": -4.0,
        }
    ]
    delivery = parse_warrant_acquisition(
        receipt,
        receipts.read_content(receipt.acquisition_id, "raw"),
        receipts.read_content(receipt.acquisition_id, "normalized"),
        period="2026-09-24",
        definition_version="metric-catalog-v0002",
    )
    assert delivery.current_member_count == 2
