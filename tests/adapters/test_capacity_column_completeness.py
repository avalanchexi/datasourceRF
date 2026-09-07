from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import (
    ingest_official_context_document,
    parse_official_context_document,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def capacity_document(quarter: int, *, missing: bool = False, duplicate: bool = False) -> bytes:
    quarter_name = {1: "一季度", 2: "二季度", 3: "三季度", 4: "四季度"}[quarter]
    cumulative_name = {1: "", 2: "上半年", 3: "前三季度", 4: "全年"}[quarter]
    groups = f"<th>{cumulative_name}</th>" if cumulative_name else ""
    numeric_headers = "<th>产能利用率（%）</th><th>比上年同期增减（百分点）</th>"
    headers = numeric_headers * (2 if cumulative_name else 1)
    values = "<td>73.0</td><td>-1.0</td>"
    if cumulative_name and not missing:
        values += "<td>73.3</td><td>-0.7</td>"
    rows = f"<tr><td>工业</td>{values}</tr>"
    if duplicate:
        rows += "<tr><td>工业</td><td>73.0</td><td>-1.0</td><td>73.3</td><td>-0.7</td></tr>"
    return (
        f"<html><body><h1>2026年{quarter_name}全国规模以上工业产能利用率为73.0%</h1>"
        "<p>2027/01/20 10:00</p><table>"
        f"<tr><th>行业</th><th>{quarter_name}</th>{groups}</tr>"
        f"<tr>{headers}</tr>{rows}</table></body></html>"
    ).encode()


@pytest.mark.parametrize("duplicate_valid_row", [False, True])
@pytest.mark.parametrize("quarter", [2, 3, 4])
def test_capacity_missing_columns_cannot_be_hidden_by_a_complete_duplicate(
    quarter: int, duplicate_valid_row: bool
) -> None:
    with pytest.raises(ValueError, match="^official_context_row_identity_mismatch$"):
        parse_official_context_document(
            capacity_document(quarter, missing=True, duplicate=duplicate_valid_row),
            family="nbs_capacity_utilization",
            source_url="https://www.stats.gov.cn/sj/zxfb/capacity.html",
            expected_period=f"2026-Q{quarter}",
            fetched_at=datetime(2027, 1, 20, 3, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "quarter,quarter_start,end,expected_ytd",
    [
        (1, "2026-01-01", "2026-03-31", 73.0),
        (2, "2026-04-01", "2026-06-30", 73.3),
        (3, "2026-07-01", "2026-09-30", 73.3),
        (4, "2026-10-01", "2026-12-31", 73.3),
    ],
)
def test_complete_capacity_layout_keeps_quarter_and_cumulative_periods(
    quarter: int, quarter_start: str, end: str, expected_ytd: float
) -> None:
    parsed = parse_official_context_document(
        capacity_document(quarter),
        family="nbs_capacity_utilization",
        source_url="https://www.stats.gov.cn/sj/zxfb/capacity.html",
        expected_period=f"2026-Q{quarter}",
        fetched_at=datetime(2027, 1, 20, 3, tzinfo=UTC),
    )
    assert len(parsed.scalars) == 3
    actual = {item.dimensions["measure"]: item for item in parsed.scalars}
    assert actual["quarter_rate"].value == 73.0
    assert actual["yoy_change"].value == -1.0
    assert actual["ytd_rate"].value == expected_ytd
    assert actual["quarter_rate"].period_start == quarter_start
    assert actual["yoy_change"].unit == "percentage_points"
    assert actual["ytd_rate"].period_start == "2026-01-01"
    assert actual["ytd_rate"].period_kind == "year_to_quarter"
    assert {item.period_end for item in parsed.scalars} == {end}


def test_rejected_capacity_import_keeps_raw_receipt_without_claims(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = capacity_document(2, missing=True)
    now = datetime(2027, 1, 20, 3, tzinfo=UTC)
    with pytest.raises(ValueError, match="^official_context_row_identity_mismatch$"):
        ingest_official_context_document(
            paths,
            raw,
            family="nbs_capacity_utilization",
            source_url="https://www.stats.gov.cn/sj/zxfb/capacity.html",
            expected_period="2026-Q2",
            fetched_at=now,
            clock=lambda: now,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert receipt.parser_version == "official-context-parser-v0004"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.validated_at is None
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_CAPACITY_UTILIZATION", mode=AsOfMode.SYSTEM, as_of=now
    )
