from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.official_context import parse_official_context_document


def test_real_rrr_chronicle_preserves_both_institution_scopes() -> None:
    repair = Path(__file__).resolve().parents[1]
    raw = (
        repair / "evidence-13/7c74949b8e34290d31b76c3fc11b70e783d8ccdd9c7fc321f6e38b4fd17285d5"
    ).read_bytes()
    parsed = parse_official_context_document(
        raw,
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
        expected_period="2025-05",
        fetched_at=datetime(2026, 9, 7, 14, tzinfo=UTC),
    )
    assert len(parsed.scalars) == 2
    assert {item.period_end for item in parsed.scalars} == {"2025-05-15"}
    assert {item.value for item in parsed.scalars} == {-0.5, -5.0}
    assert {item.dimensions["scope"]: item.value for item in parsed.scalars} == {
        "excluding_5_percent_institutions": -0.5,
        "auto_finance_and_financial_leasing_companies": -5.0,
    }
    assert {item.dimensions["measure"] for item in parsed.scalars} == {"rrr_change"}
    assert {item.unit for item in parsed.scalars} == {"percentage_points"}
    assert parsed.release_at == datetime.fromisoformat("2025-11-11T17:00:09+08:00")
