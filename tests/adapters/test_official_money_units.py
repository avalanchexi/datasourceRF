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


def test_real_m2_balance_keeps_decimal_unit_conversion_exact() -> None:
    # PBC 2026-02 report, L359: M2 balance 349.22 trillion CNY.
    raw = (Path(__file__).parents[1] / "fixtures/pbc_money_202602.html").read_bytes()
    parsed = parse_official_context_document(
        raw,
        family="pbc_money",
        source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026031317020260950/index.html",
        expected_period="2026-02",
        fetched_at=datetime(2026, 9, 8, tzinfo=UTC),
    )
    balance = next(
        item
        for item in parsed.scalars
        if item.dimensions == {"aggregate": "m2", "measure": "balance"}
    )
    assert balance.value == 3492200.0
    assert balance.unit == "hundred_million_cny"
    assert balance.period_start == "2026-02-01"
    assert balance.period_end == "2026-02-28"
    assert {item.source_field: item.value for item in parsed.scalars} == {
        "m1": 1159300.0,
        "m1_yoy": 5.9,
        "m2": 3492200.0,
        "m2_yoy": 9.0,
    }


@pytest.mark.parametrize(
    "source_balance,expected", [("0", 0.0), ("349.22", 3492200.0), ("1.23456789", 12345.6789)]
)
def test_decimal_balance_scaling_keeps_zero_and_yoy_units(
    source_balance: str, expected: float
) -> None:
    content = (
        "<html><body><h1>2026年2月金融统计数据报告</h1>"
        "<p>文章来源：2026-03-13 17:00:01</p>"
        f"<p>广义货币(M2)余额{source_balance}万亿元，同比增长0%；"
        f"狭义货币(M1)余额{source_balance}万亿元，同比下降2%。</p></body></html>"
    ).encode()
    parsed = parse_official_context_document(
        content,
        family="pbc_money",
        source_url="https://www.pbc.gov.cn/diaochatongjisi/money.html",
        expected_period="2026-02",
        fetched_at=datetime(2026, 9, 8, tzinfo=UTC),
    )
    assert {item.source_field: (item.value, item.unit) for item in parsed.scalars} == {
        "m1": (expected, "hundred_million_cny"),
        "m1_yoy": (-2.0, "percent"),
        "m2": (expected, "hundred_million_cny"),
        "m2_yoy": (0.0, "percent"),
    }


def test_exact_money_balance_is_persisted_with_its_original(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    now = datetime(2026, 9, 8, tzinfo=UTC)
    raw = (Path(__file__).parents[1] / "fixtures/pbc_money_202602.html").read_bytes()
    result = ingest_official_context_document(
        paths,
        raw,
        family="pbc_money",
        source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026031317020260950/index.html",
        expected_period="2026-02",
        fetched_at=now,
        clock=lambda: now,
    )
    repository = EvidenceRepository(paths.database)
    traces = [
        repository.trace(identity, mode=AsOfMode.SYSTEM, as_of=now)
        for identity in result.observation_ids
    ]
    trace = next(
        item for item in traces if item.dimensions == {"aggregate": "m2", "measure": "balance"}
    )
    (claim,) = trace.claims
    assert claim.value == 3492200.0
    assert claim.certification_status == "awaiting_source_certification"
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.parser_version == "official-context-parser-v0004"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert tuple(item.acquisition_id for item in trace.acquisitions) == (receipt.acquisition_id,)
