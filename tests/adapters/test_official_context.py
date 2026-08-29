from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import analytical_model_v0002_manifest
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    ingest_official_context_document,
    parse_official_context_document,
    refresh_official_context_document,
    smoke_official_context_document,
)
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def core_cpi_document(year: int, month: int, values: tuple[float, float, float]) -> bytes:
    mom, yoy, ytd = values
    release_year = year + month // 12
    release_month = month % 12 + 1
    return f"""
    <html><body>
      <h1>{year}年{month}月份居民消费价格</h1>
      <p>发布时间：{release_year}-{release_month:02d}-09 09:30</p>
      <table>
        <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
        <tr><td>不包括食品和能源</td><td>{mom}</td><td>{yoy}</td><td>{ytd}</td></tr>
      </table>
    </body></html>
    """.encode()


def official_table_document(
    *,
    title: str,
    release_at: str,
    header: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
) -> bytes:
    header_html = "".join(f"<th>{item}</th>" for item in header)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{item}</td>" for item in row) + "</tr>"
        for row in rows
    )
    return (
        f"<html><body><h1>{title}</h1><p>发布时间：{release_at}</p>"
        f"<table><tr>{header_html}</tr>{rows_html}</table></body></html>"
    ).encode()


def official_multi_table_document(
    *,
    title: str,
    release_at: str,
    tables: tuple[tuple[tuple[str, ...], tuple[tuple[object, ...], ...]], ...],
) -> bytes:
    table_html = ""
    for header, rows in tables:
        table_html += "<table><tr>" + "".join(f"<th>{item}</th>" for item in header) + "</tr>"
        table_html += "".join(
            "<tr>" + "".join(f"<td>{item}</td>" for item in row) + "</tr>"
            for row in rows
        )
        table_html += "</table>"
    return (
        f"<html><body><h1>{title}</h1><p>发布时间：{release_at}</p>"
        f"{table_html}</body></html>"
    ).encode()


@pytest.mark.parametrize(
    ("year", "month", "values"),
    [
        (2013, 12, (-0.1, 1.8, 1.7)),
        (2026, 6, (-0.1, 1.0, 1.2)),
    ],
)
def test_core_cpi_offline_contract_accepts_two_schema_years(
    year: int,
    month: int,
    values: tuple[float, float, float],
) -> None:
    period = f"{year:04d}-{month:02d}"
    release_year = year + month // 12
    release_month = month % 12 + 1
    parsed = parse_official_context_document(
        core_cpi_document(year, month, values),
        family="nbs_core_cpi",
        source_url=f"https://www.stats.gov.cn/sj/zxfb/{year}07/t{year}0709_1.html",
        expected_period=period,
        fetched_at=datetime(release_year, release_month, 9, 2, tzinfo=UTC),
    )

    assert parsed.family == "nbs_core_cpi"
    assert parsed.period == period
    assert parsed.release_at.isoformat() == (
        f"{release_year:04d}-{release_month:02d}-09T09:30:00+08:00"
    )
    assert {
        (item.dimensions["measure"], item.value, item.unit)
        for item in parsed.scalars
    } == {
        ("mom", values[0], "percent"),
        ("yoy", values[1], "percent"),
        ("cumulative_average_yoy", values[2], "percent"),
    }


def test_core_cpi_offline_contract_rejects_changed_header() -> None:
    malformed = core_cpi_document(2026, 6, (-0.1, 1.0, 1.2)).replace(
        "累计平均同比（%）".encode(),
        "累计指数".encode(),
    )

    with pytest.raises(ValueError, match="official_context_table_schema_mismatch"):
        parse_official_context_document(
            malformed,
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html",
            expected_period="2026-06",
            fetched_at=datetime(2026, 7, 9, 2, tzinfo=UTC),
        )


def test_official_context_ingest_is_traceable_but_redacted_until_certified(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = core_cpi_document(2026, 6, (-0.1, 1.0, 1.2))
    fetched_at = datetime(2026, 7, 9, 2, tzinfo=UTC)

    result = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html",
        expected_period="2026-06",
        fetched_at=fetched_at,
    )

    evidence = EvidenceRepository(paths.database)
    trace = evidence.trace(
        result.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=fetched_at,
    )
    context = build_context_projection(
        evidence,
        as_of=fetched_at,
        model_manifest=analytical_model_v0002_manifest(),
    )
    core_rows = [
        row
        for row in context.macro["price_chain"]["gaps"]  # type: ignore[index]
        if row["metric_id"] == "CN_CORE_CPI"
    ]

    assert result.observation_count == 3
    assert len(result.artifact_hash) == 64
    assert trace.claims[0].provider == "国家统计局"
    assert trace.claims[0].certification_status == "awaiting_source_certification"
    assert {row["freshness"] for row in core_rows} == {"awaiting_source_certification"}
    assert {row["value"] for row in core_rows} == {None}


def test_official_context_revision_is_public_only_from_the_revision_fetch(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    source_url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html"
    first_fetch = datetime(2026, 7, 9, 2, tzinfo=UTC)
    revision_fetch = datetime(2026, 7, 10, 2, tzinfo=UTC)
    first = ingest_official_context_document(
        paths,
        core_cpi_document(2026, 6, (-0.1, 1.0, 1.2)),
        family="nbs_core_cpi",
        source_url=source_url,
        expected_period="2026-06",
        fetched_at=first_fetch,
    )

    ingest_official_context_document(
        paths,
        core_cpi_document(2026, 6, (-0.1, 1.1, 1.2)),
        family="nbs_core_cpi",
        source_url=source_url,
        expected_period="2026-06",
        fetched_at=revision_fetch,
    )
    repository = EvidenceRepository(paths.database)
    yoy_observation_id = next(
        observation_id
        for observation_id in first.observation_ids
        if repository.trace(
            observation_id,
            mode=AsOfMode.SYSTEM,
            as_of=first_fetch,
        ).dimensions["measure"]
        == "yoy"
    )
    before_revision = repository.query(
        yoy_observation_id,
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 7, 9, 12, tzinfo=UTC),
    )
    after_revision = repository.query(
        yoy_observation_id,
        mode=AsOfMode.PUBLIC,
        as_of=revision_fetch,
    )

    assert before_revision.selected_value == 1.0
    assert after_revision.selected_value == 1.1


def test_official_context_smoke_returns_sanitized_contract_evidence() -> None:
    content = core_cpi_document(2026, 6, (-0.1, 1.0, 1.2))
    source_url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html"

    result = smoke_official_context_document(
        family="nbs_core_cpi",
        source_url=source_url,
        expected_period="2026-06",
        fetched_at=datetime(2026, 7, 9, 2, tzinfo=UTC),
        fetcher=lambda _url: FetchedOfficialContextDocument(
            content=content,
            media_type="text/html; charset=utf-8",
            final_url=source_url,
            http_status=200,
        ),
    )

    assert result.status == "validated_candidate"
    assert result.metric_ids == ("CN_CORE_CPI",)
    assert result.observation_count == 3
    assert result.network_requests == 1
    assert len(result.content_hash) == 64
    assert not hasattr(result, "content")


def test_official_context_refresh_records_family_failure_without_storing_values(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    fetched_at = datetime(2026, 7, 9, 2, tzinfo=UTC)

    with pytest.raises(OSError, match="fixture_official_unavailable"):
        refresh_official_context_document(
            paths,
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html",
            expected_period="2026-06",
            fetched_at=fetched_at,
            fetcher=lambda _url: (_ for _ in ()).throw(
                OSError("fixture_official_unavailable")
            ),
        )

    repository = EvidenceRepository(paths.database)
    attempt = repository.latest_retrieval_attempt(
        "CN_CORE_CPI",
        period="2026-06",
        as_of=fetched_at,
    )
    assert attempt is not None
    assert attempt.channel == "official_direct_candidate"
    assert attempt.outcome == "source_failed"
    assert repository.metric_series(
        "CN_CORE_CPI",
        mode=AsOfMode.SYSTEM,
        as_of=fetched_at,
    ) == ()


def test_pbc_omo_contract_separates_rate_injection_and_maturity() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026-08-28公开市场业务交易公告",
            release_at="2026-08-28 09:20",
            header=(
                "操作日",
                "品种",
                "期限",
                "中标利率（%）",
                "投放量（亿元）",
                "到期量（亿元）",
            ),
            rows=(("2026-08-28", "逆回购", "7天", 1.4, 3000, 2500),),
        ),
        family="pbc_omo_notice",
        source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/1.html",
        expected_period="2026-08-28",
        fetched_at=datetime(2026, 8, 28, 2, tzinfo=UTC),
    )

    assert {
        (item.metric_id, item.dimensions.get("measure"), item.value, item.unit)
        for item in parsed.scalars
    } == {
        ("CN_OMO_7D_RATE", None, 1.4, "percent"),
        ("CN_OMO_7D_AMOUNT", "injection", 3000.0, "hundred_million_cny"),
        ("CN_OMO_7D_AMOUNT", "maturity", 2500.0, "hundred_million_cny"),
    }
    assert {item.period_end for item in parsed.scalars} == {"2026-08-28"}


def test_pbc_rrr_contract_separates_announcement_and_effective_date() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026年8月降低金融机构存款准备金率公告",
            release_at="2026-08-20 17:00",
            header=(
                "生效日期",
                "调整（百分点）",
                "机构范围",
                "调整后准备金率（%）",
                "释放资金（亿元）",
            ),
            rows=(("2026-08-25", -0.5, "全面（部分机构例外）", 6.2, 10000),),
        ),
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/2.html",
        expected_period="2026-08",
        fetched_at=datetime(2026, 8, 20, 10, tzinfo=UTC),
    )

    assert parsed.release_at.isoformat() == "2026-08-20T17:00:00+08:00"
    assert {item.period_end for item in parsed.scalars} == {"2026-08-25"}
    assert {
        (item.dimensions["measure"], item.value, item.unit)
        for item in parsed.scalars
    } == {
        ("rrr_change", -0.5, "percentage_points"),
        ("post_change_rrr", 6.2, "percent"),
        ("released_funds", 10000.0, "hundred_million_cny"),
    }


def test_pbc_monthly_liquidity_contract_checks_official_net_identity() -> None:
    content = official_table_document(
        title="2026年7月各项工具流动性投放表",
        release_at="2026-08-05 17:30",
        header=("工具", "投放（亿元）", "回笼（亿元）", "净投放（亿元）"),
        rows=(("公开市场逆回购", 12000, 9500, 2500),),
    )
    parsed = parse_official_context_document(
        content,
        family="pbc_tool_liquidity_monthly",
        source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/3.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 5, 10, tzinfo=UTC),
    )

    assert {
        (item.dimensions["measure"], item.value)
        for item in parsed.scalars
    } == {("injection", 12000.0), ("withdrawal", 9500.0), ("net_injection", 2500.0)}
    with pytest.raises(ValueError, match="official_context_liquidity_identity_mismatch"):
        parse_official_context_document(
            content.replace(b"2500", b"2600"),
            family="pbc_tool_liquidity_monthly",
            source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/3.html",
            expected_period="2026-07",
            fetched_at=datetime(2026, 8, 5, 10, tzinfo=UTC),
        )


def test_pbc_social_financing_contract_keeps_total_and_components_separate() -> None:
    labels = (
        "社会融资规模",
        "人民币贷款",
        "外币贷款（折合人民币）",
        "委托贷款",
        "信托贷款",
        "未贴现银行承兑汇票",
        "企业债券",
        "政府债券",
        "非金融企业境内股票融资",
        "存款类金融机构资产支持证券",
        "贷款核销",
    )
    increments = tuple((label, 5000 + index) for index, label in enumerate(labels))
    stocks = tuple((label, 300.0 + index, 8.0 + index / 10) for index, label in enumerate(labels))
    parsed = parse_official_context_document(
        official_multi_table_document(
            title="2026年7月社会融资规模增量和存量统计数据",
            release_at="2026-08-13 17:00",
            tables=(
                (("分项", "当月增量（亿元）"), increments),
                (("分项", "期末存量（万亿元）", "同比（%）"), stocks),
            ),
        ),
        family="pbc_social_financing",
        source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116319/4.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 13, 10, tzinfo=UTC),
    )

    total = [item for item in parsed.scalars if item.metric_id == "CN_SF_TOTAL"]
    components = [item for item in parsed.scalars if item.metric_id == "CN_SF_COMPONENTS"]
    assert {(item.dimensions["measure"], item.value) for item in total} == {
        ("monthly_increment", 5000.0),
        ("stock_end", 3000000.0),
        ("stock_yoy", 8.0),
    }
    assert len(components) == 30
    government_stock = next(
        item
        for item in components
        if item.dimensions == {"component": "government_bonds", "measure": "stock_end"}
    )
    assert government_stock.value == 3070000.0


def test_pbc_loan_structure_contract_preserves_borrower_and_tenor() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026年7月金融机构人民币信贷收支统计",
            release_at="2026-08-13 17:01",
            header=("借款人", "期限", "月末存量（亿元）"),
            rows=(
                ("住户", "合计", 850000),
                ("住户", "短期", 210000),
                ("住户", "中长期", 640000),
                ("企（事）业单位", "合计", 1600000),
                ("企（事）业单位", "短期", 550000),
                ("企（事）业单位", "中长期", 900000),
                ("企（事）业单位", "票据融资", 150000),
                ("非银行业金融机构", "合计", 25000),
                ("人民币各项贷款", "合计", 2500000),
            ),
        ),
        family="pbc_loan_structure",
        source_url="https://www.pbc.gov.cn/diaochatongjisi/116219/116319/5.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 13, 10, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 9
    household_long = next(
        item
        for item in parsed.scalars
        if item.dimensions
        == {"borrower": "household", "tenor": "long_term", "measure": "stock_end"}
    )
    assert household_long.value == 640000.0
    assert household_long.unit == "hundred_million_cny"


def test_pbc_usdcny_central_parity_contract_preserves_quote_direction() -> None:
    content = """
    <html><body>
      <h1>2025年5月7日中国外汇交易中心受权公布人民币汇率中间价公告</h1>
      <p>文章来源： 2025-05-07 09:25:54</p>
      <p>中国人民银行授权中国外汇交易中心公布，2025年5月7日银行间外汇市场
      人民币汇率中间价为1美元对人民币7.2005元，1欧元对人民币8.1650元。</p>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="pbc_usdcny_central_parity",
        source_url=(
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/"
            "5699853/index.html"
        ),
        expected_period="2025-05-07",
        fetched_at=datetime(2025, 5, 7, 2, tzinfo=UTC),
    )

    assert parsed.release_at.isoformat() == "2025-05-07T09:25:54+08:00"
    assert len(parsed.scalars) == 1
    scalar = parsed.scalars[0]
    assert scalar.metric_id == "CN_USDCNY_CENTRAL_PARITY"
    assert scalar.dimensions == {
        "currency_pair": "USD/CNY",
        "quote_direction": "CNY per USD",
    }
    assert scalar.value == 7.2005
    assert scalar.unit == "cny_per_usd"


def test_pbc_usdcny_central_parity_rejects_reverse_or_ambiguous_quotes() -> None:
    content = """
    <html><body>
      <h1>2025年5月7日人民币汇率中间价公告</h1>
      <p>文章来源： 2025-05-07 09:25:54</p>
      <p>人民币1元对0.1389美元。</p>
    </body></html>
    """.encode()

    with pytest.raises(ValueError, match="official_context_usdcny_quote_missing"):
        parse_official_context_document(
            content,
            family="pbc_usdcny_central_parity",
            source_url=(
                "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/"
                "5699853/index.html"
            ),
            expected_period="2025-05-07",
            fetched_at=datetime(2025, 5, 7, 2, tzinfo=UTC),
        )


def test_nbs_industrial_value_added_contract_preserves_real_and_sa_measures() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026年6月份规模以上工业增加值",
            release_at="2026-07-15 10:00",
            header=("指标", "当月实际同比（%）", "累计实际同比（%）", "季调环比（%）"),
            rows=(("规模以上工业增加值", 5.1, 6.4, 0.42),),
        ),
        family="nbs_industrial_value_added",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_1.html",
        expected_period="2026-06",
        fetched_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
    )

    assert {
        (item.dimensions["measure"], item.value, item.period_start)
        for item in parsed.scalars
    } == {
        ("current_month_real_yoy", 5.1, "2026-06-01"),
        ("ytd_real_yoy", 6.4, "2026-01-01"),
        ("mom_seasonally_adjusted", 0.42, "2026-06-01"),
    }
    with pytest.raises(ValueError, match="official_context_january_monthly_value_not_reported"):
        parse_official_context_document(
            official_table_document(
                title="2026年1月份规模以上工业增加值",
                release_at="2026-02-15 10:00",
                header=("指标", "当月实际同比（%）", "累计实际同比（%）", "季调环比（%）"),
                rows=(("规模以上工业增加值", 5.1, 5.1, 0.42),),
            ),
            family="nbs_industrial_value_added",
            source_url="https://www.stats.gov.cn/sj/zxfbhjd/202602/t20260215_1.html",
            expected_period="2026-01",
            fetched_at=datetime(2026, 2, 15, 3, tzinfo=UTC),
        )


def test_nbs_industrial_finance_contract_keeps_nominal_inventory_and_turnover() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026年1—6月份规模以上工业企业利润",
            release_at="2026-07-27 09:30",
            header=("指标", "数值", "同比或变化", "数值单位", "同比或变化单位"),
            rows=(
                ("利润总额", 36500, 4.2, "亿元", "%"),
                ("营业收入", 680000, 3.8, "亿元", "%"),
                ("营业成本", 580000, 3.5, "亿元", "%"),
                ("产成品存货", 67000, 2.1, "亿元", "%"),
                ("产成品周转天数", 19.2, 0.3, "天", "天"),
            ),
        ),
        family="nbs_industrial_finance",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260727_1.html",
        expected_period="2026-06",
        fetched_at=datetime(2026, 7, 27, 2, tzinfo=UTC),
    )

    assert {item.metric_id for item in parsed.scalars} == {
        "CN_INDUSTRIAL_FINANCE",
        "CN_FINISHED_GOODS_INVENTORY",
        "CN_INVENTORY_TURNOVER",
    }
    inventory = [
        item for item in parsed.scalars if item.metric_id == "CN_FINISHED_GOODS_INVENTORY"
    ]
    assert {(item.dimensions["measure"], item.value, item.unit) for item in inventory} == {
        ("nominal_end_level", 67000.0, "hundred_million_cny"),
        ("official_yoy", 2.1, "percent"),
    }
    turnover = [item for item in parsed.scalars if item.metric_id == "CN_INVENTORY_TURNOVER"]
    assert {(item.dimensions["measure"], item.value, item.unit) for item in turnover} == {
        ("days", 19.2, "days"),
        ("official_yoy_change", 0.3, "days"),
    }


def test_nbs_capacity_contract_preserves_quarter_ytd_and_yoy_change() -> None:
    parsed = parse_official_context_document(
        official_table_document(
            title="2026年第二季度全国工业产能利用率",
            release_at="2026-07-15 10:00",
            header=("行业", "当季（%）", "同比变化（百分点）", "累计（%）"),
            rows=(("全国规模以上工业", 74.0, -0.2, 74.3),),
        ),
        family="nbs_capacity_utilization",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_2.html",
        expected_period="2026-Q2",
        fetched_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
    )

    assert {
        (item.dimensions["measure"], item.value, item.unit)
        for item in parsed.scalars
    } == {
        ("quarter_rate", 74.0, "percent"),
        ("yoy_change", -0.2, "percentage_points"),
        ("ytd_rate", 74.3, "percent"),
    }
    assert {item.period_end for item in parsed.scalars} == {"2026-06-30"}
