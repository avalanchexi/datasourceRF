from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import (
    ingest_official_context_document,
    parse_official_context_document,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime


@pytest.mark.parametrize("semicolon_variant", [False, True])
def test_real_rrr_chronicle_preserves_both_institution_scopes(semicolon_variant: bool) -> None:
    raw = (Path(__file__).parents[1] / "fixtures/pbc_rrr_chronicle_2025.html").read_bytes()
    if semicolon_variant:
        # A synthetic punctuation variant of the saved real original, not another official sample.
        changed = raw.replace("，下调汽车金融公司".encode(), "；下调汽车金融公司".encode())
        assert changed != raw
        raw = changed
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


@pytest.mark.parametrize(
    "extra_clause",
    [
        "下调其他金融机构存款准备金率1个百分点",
        "上调汽车金融公司和金融租赁公司存款准备金率1个百分点",
        "5月16日下调汽车金融公司和金融租赁公司存款准备金率5个百分点",
        "暂不下调汽车金融公司和金融租赁公司存款准备金率5个百分点",
        "次日，下调汽车金融公司和金融租赁公司存款准备金率5个百分点",
        "汽车金融公司和金融租赁公司存款准备金率下调5个百分点",
        "下调汽车金融公司和金融租赁公司存款准备金率5个百分点，"
        "下调汽车金融公司和金融租赁公司存款准备金率5个百分点",
    ],
)
def test_rrr_prose_rejects_unresolved_or_duplicate_scope_changes(extra_clause: str) -> None:
    content = (
        "<html><body><h1>2025年前三季度中国货币政策大事记</h1>"
        "<p>文章来源：2025-11-11 17:00:09</p>"
        "<p>5月15日，中国人民银行下调金融机构存款准备金率0.5个百分点"
        f"（不含已执行5%存款准备金率的金融机构），{extra_clause}。</p></body></html>"
    ).encode()
    with pytest.raises(ValueError, match="^official_context_rrr_scope_incomplete$"):
        parse_official_context_document(
            content,
            family="pbc_rrr_notice",
            source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
            expected_period="2025-05",
            fetched_at=datetime(2026, 9, 7, 14, tzinfo=UTC),
        )


def test_rrr_scopes_share_original_and_record_actual_system_acquisition(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    raw = (Path(__file__).parents[1] / "fixtures/pbc_rrr_chronicle_2025.html").read_bytes()
    now = datetime(2026, 9, 7, 14, tzinfo=UTC)
    ticks = count()

    def clock() -> datetime:
        return now + timedelta(seconds=next(ticks))

    result = ingest_official_context_document(
        paths,
        raw,
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
        expected_period="2025-05",
        fetched_at=now - timedelta(days=1),
        definition_version="metric-catalog-v0001",
        clock=clock,
    )
    assert len(result.observation_ids) == 2
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.parser_version == "official-context-parser-v0004"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.received_at is not None
    assert receipt.validated_at is not None
    assert receipt.started_at < receipt.received_at < receipt.validated_at
    repository = EvidenceRepository(paths.database)
    claims = []
    for observation_id in result.observation_ids:
        trace = repository.trace(
            observation_id, mode=AsOfMode.SYSTEM, as_of=now + timedelta(hours=1)
        )
        (claim,) = trace.claims
        claims.append(claim)
        assert claim.fetched_at == receipt.received_at
        assert claim.available_at >= receipt.validated_at
        assert claim.certification_status == "awaiting_source_certification"
        assert claim.public_available_at == datetime.fromisoformat("2025-11-11T17:00:09+08:00")
        assert tuple(item.acquisition_id for item in trace.acquisitions) == (
            receipt.acquisition_id,
        )
        before = repository.query(observation_id, mode=AsOfMode.SYSTEM, as_of=now)
        assert before.selected_value is None
    assert {claim.value for claim in claims} == {-0.5, -5.0}


def test_rrr_incomplete_scope_import_keeps_raw_without_partial_claims(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    original = (Path(__file__).parents[1] / "fixtures/pbc_rrr_chronicle_2025.html").read_bytes()
    raw = original.replace(
        "下调汽车金融公司和金融租赁公司存款准备金率5个百分点".encode(),
        "下调其他金融机构存款准备金率1个百分点".encode(),
    )
    assert raw != original
    now = datetime(2026, 9, 7, 14, tzinfo=UTC)
    with pytest.raises(ValueError, match="^official_context_rrr_scope_incomplete$"):
        ingest_official_context_document(
            paths,
            raw,
            family="pbc_rrr_notice",
            source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
            expected_period="2025-05",
            fetched_at=now,
            definition_version="metric-catalog-v0001",
            clock=lambda: now,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_RRR_EVENT",
        mode=AsOfMode.SYSTEM,
        as_of=now,
        definition_version="metric-catalog-v0001",
    )




def test_rrr_chronicle_cannot_supply_a_different_requested_year() -> None:
    raw = (Path(__file__).parents[1] / "fixtures/pbc_rrr_chronicle_2025.html").read_bytes()
    with pytest.raises(ValueError, match="^official_context_period_identity_mismatch$"):
        parse_official_context_document(
            raw,
            family="pbc_rrr_notice",
            source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
            expected_period="2026-05",
            fetched_at=datetime(2026, 9, 7, 14, tzinfo=UTC),
        )
