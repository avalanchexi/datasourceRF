from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    ingest_official_context_document,
    parse_official_context_document,
    refresh_official_context_document,
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
        "<tr>" + "".join(f"<td>{item}</td>" for item in row) + "</tr>" for row in rows
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
            "<tr>" + "".join(f"<td>{item}</td>" for item in row) + "</tr>" for row in rows
        )
        table_html += "</table>"
    return (
        f"<html><body><h1>{title}</h1><p>发布时间：{release_at}</p>{table_html}</body></html>"
    ).encode()


def live_pbc_financial_report_document() -> bytes:
    return """
    <html><body>
      <h1>2026年7月金融统计数据报告</h1>
      <p>文章来源： 2026-08-14 16:30:05</p>
      <p>一、社会融资规模存量同比增长7.4%</p>
      <p>初步统计，2026年7月末社会融资规模存量为463.27万亿元，同比增长7.4%。
      其中，对实体经济发放的人民币贷款余额278.57万亿元，同比增长5.2%；
      对实体经济发放的外币贷款折合人民币余额1.19万亿元，同比下降1.7%；
      委托贷款余额11.24万亿元，同比增长0.7%；信托贷款余额4.6万亿元，同比增长3.2%；
      未贴现的银行承兑汇票余额1.97万亿元，同比增长2.7%；
      企业债券余额36.47万亿元，同比增长9.2%；政府债券余额102.68万亿元，同比增长14.1%；
      非金融企业境内股票余额12.6万亿元，同比增长5.5%。</p>
      <p>二、前七个月社会融资规模增量累计为22.25万亿元。其中，对实体经济发放的人民币贷款增加10.17万亿元；
      对实体经济发放的外币贷款折合人民币增加1694亿元；委托贷款减少810亿元；信托贷款减少672亿元；
      未贴现的银行承兑汇票减少1786亿元；企业债券净融资2.52万亿元；政府债券净融资7.76万亿元；
      非金融企业境内股票融资4061亿元。</p>
      <p>五、前七个月人民币贷款增加10.38万亿元。分部门看，住户贷款减少8271亿元，
      其中，短期贷款减少9281亿元，中长期贷款增加1010亿元；企（事）业单位贷款增加11万亿元，
      其中，短期贷款增加4.34万亿元，中长期贷款增加5.32万亿元，票据融资增加1.19万亿元；
      非银行业金融机构贷款减少3944亿元。</p>
    </body></html>
    """.encode()


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
    assert {(item.dimensions["measure"], item.value, item.unit) for item in parsed.scalars} == {
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


def test_core_cpi_contract_accepts_live_nbs_table_and_slash_timestamp() -> None:
    content = """
    <html><body>
      <h1>2026年7月份居民消费价格同比上涨0.5%</h1>
      <p>2026/08/09 09:30</p>
      <table>
        <tr><th></th><th>环比涨跌幅（ % ）</th>
        <th>同比涨跌幅（ % ）</th><th>1 — 7 月 同比涨跌幅（ % ）</th></tr>
        <tr><td>其中：不包括食品和能源</td><td>0.3</td><td>0.9</td><td>1.1</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260809_1965008.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 9, 2, tzinfo=UTC),
    )

    assert parsed.release_at.isoformat() == "2026-08-09T09:30:00+08:00"
    assert {item.value for item in parsed.scalars} == {0.3, 0.9, 1.1}






@pytest.mark.usefixtures("runtime_clock")
def test_scoped_fallback_preserves_revision_time_for_the_whole_announcement(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    source_url = "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html"

    # Synthetic revisions keep the same printed publication time.
    def document(core_yoy: float) -> bytes:
        return official_table_document(
            title="2026年6月份居民消费价格",
            release_at="2026-07-09 09:30",
            header=("指标", "环比（%）", "同比（%）", "累计平均同比（%）"),
            rows=(("居民消费价格", 0.1, 0.8, 0.9), ("不包括食品和能源", 0.0, core_yoy, 1.2)),
        )

    for metric, core_yoy in (
        ("CN_CORE_CPI", 1.0),
        ("CN_CORE_CPI", 1.1),
        ("CN_CPI_HEADLINE", 1.1),
    ):
        refresh_official_context_document(
            paths,
            family="nbs_core_cpi",
            source_url=source_url,
            expected_period="2026-06",
            fetched_at=datetime.now(UTC),
            metric_ids=(metric,),
            fetcher=lambda url, core_yoy=core_yoy: FetchedOfficialContextDocument(
                document(core_yoy), "text/html", url, 200
            ),
        )
    evidence = EvidenceRepository(paths.database)
    headline = evidence.metric_series(
        "CN_CPI_HEADLINE", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
    )
    assert len(headline) == 3
    assert all(
        claim.parsed_public_available_at is None for point in headline for claim in point.claims
    )


@pytest.mark.usefixtures("runtime_clock")
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
            fetcher=lambda _url: (_ for _ in ()).throw(OSError("fixture_official_unavailable")),
        )

    repository = EvidenceRepository(paths.database)
    assert (
        repository.latest_retrieval_attempt("CN_CORE_CPI", period="2026-06", as_of=fetched_at)
        is None
    )
    completed_at = datetime.now(UTC)
    attempt = repository.latest_retrieval_attempt(
        "CN_CORE_CPI",
        period="2026-06",
        as_of=completed_at,
    )
    assert attempt is not None
    assert attempt.channel == "official_direct_candidate"
    assert attempt.outcome == "source_failed"
    assert (
        repository.metric_series(
            "CN_CORE_CPI",
            mode=AsOfMode.SYSTEM,
            as_of=completed_at,
        )
        == ()
    )


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


def test_pbc_omo_contract_accepts_live_notice_without_inventing_maturity() -> None:
    content = """
    <html><body>
      <h1>公开市场业务交易公告 [2026]第168号</h1>
      <p>文章来源： 2026-08-28 09:20:30</p>
      <p>2026年8月28日中国人民银行开展了200亿元7天期逆回购操作。</p>
      <table>
        <tr><th>7天期逆回购操作情况 期限</th><th>操作 利率</th><th>投标量</th><th>中标量</th></tr>
        <tr><td>7 天</td><td>1. 40 %</td><td>200 亿元</td><td>200 亿元</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="pbc_omo_notice",
        source_url=(
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/"
            "2026082808585347002/index.html"
        ),
        expected_period="2026-08-28",
        fetched_at=datetime(2026, 8, 28, 2, tzinfo=UTC),
    )

    assert {
        (item.metric_id, item.dimensions.get("measure"), item.value) for item in parsed.scalars
    } == {
        ("CN_OMO_7D_RATE", None, 1.4),
        ("CN_OMO_7D_AMOUNT", "injection", 200.0),
    }


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
    assert {(item.dimensions["measure"], item.value, item.unit) for item in parsed.scalars} == {
        ("rrr_change", -0.5, "percentage_points"),
        ("post_change_rrr", 6.2, "percent"),
        ("released_funds", 10000.0, "hundred_million_cny"),
    }


def test_pbc_rrr_contract_accepts_live_policy_chronicle_prose() -> None:
    content = """
    <html><body>
      <h1>2025年前三季度中国货币政策大事记</h1>
      <p>文章来源： 2025-10-15 17:00:00</p>
      <p>5月15日，中国人民银行下调金融机构存款准备金率0.5个百分点（不含已执行5%存款准备金率的金融机构）。</p>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="pbc_rrr_notice",
        source_url="https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/5896228/index.html",
        expected_period="2025-05",
        fetched_at=datetime(2025, 10, 15, 10, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 1
    assert parsed.scalars[0].period_end == "2025-05-15"
    assert parsed.scalars[0].value == -0.5
    assert parsed.scalars[0].dimensions == {
        "scope": "excluding_5_percent_institutions",
        "measure": "rrr_change",
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

    assert {(item.dimensions["measure"], item.value) for item in parsed.scalars} == {
        ("injection", 12000.0),
        ("withdrawal", 9500.0),
        ("net_injection", 2500.0),
    }
    with pytest.raises(ValueError, match="official_context_liquidity_identity_mismatch"):
        parse_official_context_document(
            content.replace(b"2500", b"2600"),
            family="pbc_tool_liquidity_monthly",
            source_url="https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/3.html",
            expected_period="2026-07",
            fetched_at=datetime(2026, 8, 5, 10, tzinfo=UTC),
        )


def test_pbc_monthly_liquidity_contract_accepts_live_rowspan_shape() -> None:
    content = """
    <html><body>
      <h1>2026年7月中央银行各项工具流动性投放情况</h1>
      <p>文章来源： 2026-08-04 17:00:00</p>
      <table>
        <tr><th>单位：亿元 工具类型</th><th>工具名称</th>
        <th>投放</th><th>回笼</th><th>净投放</th></tr>
        <tr><td rowspan="4">中央银行贷款</td><td>常备借贷便利（SLF）</td>
        <td>0</td><td>10</td><td>-10</td></tr>
        <tr><td>中期借贷便利（MLF）</td><td>5000</td><td>4000</td><td>1000</td></tr>
        <tr><td>抵押补充贷款（PSL）</td><td>0</td><td>1161</td><td>-1161</td></tr>
        <tr><td>其他结构性货币政策工具</td><td>6171</td><td>4427</td><td>1744</td></tr>
        <tr><td rowspan="3">公开市场业务</td><td>7天期逆回购</td>
        <td>47395</td><td>49890</td><td>-2495</td></tr>
        <tr><td>其他期限逆回购</td><td>42000</td><td>35000</td><td>7000</td></tr>
        <tr><td>公开市场国债买卖</td><td>500</td><td>0</td><td>500</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="pbc_tool_liquidity_monthly",
        source_url=(
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/"
            "2026080416515912098/index.html"
        ),
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 4, 10, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 21
    assert any(
        item.dimensions == {"tool": "短期逆回购", "measure": "net_injection"}
        and item.value == -2495
        for item in parsed.scalars
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


def test_pbc_social_financing_contract_accepts_live_combined_report_prose() -> None:
    parsed = parse_official_context_document(
        live_pbc_financial_report_document(),
        family="pbc_social_financing",
        source_url=(
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html"
        ),
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 14, 9, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 27
    total = [item for item in parsed.scalars if item.metric_id == "CN_SF_TOTAL"]
    assert {(item.dimensions["measure"], item.value) for item in total} == {
        ("stock_end", 4_632_700.0),
        ("stock_yoy", 7.4),
        ("ytd_increment", 222_500.0),
    }
    government = [
        item for item in parsed.scalars if item.dimensions.get("component") == "government_bonds"
    ]
    assert {(item.dimensions["measure"], item.value) for item in government} == {
        ("stock_end", 1_026_800.0),
        ("stock_yoy", 14.1),
        ("ytd_increment", 77_600.0),
    }


@pytest.mark.parametrize(
    ("section", "expected_count", "expected_measures"),
    [
        (
            """初步统计，2024年1月末社会融资规模存量为384.29万亿元，同比增长9.5%。
            其中，对实体经济发放的人民币贷款余额为240.32万亿元，同比增长10.1%；
            对实体经济发放的外币贷款折合人民币余额为1.76万亿元，同比下降0.9%；
            委托贷款余额为11.23万亿元，同比下降0.7%；信托贷款余额为3.98万亿元，同比增长6.3%；
            未贴现的银行承兑汇票余额为3.05万亿元，同比增长3%；企业债券余额为31.41万亿元，同比增长1.3%；
            政府债券余额为70.09万亿元，同比增长15.7%；非金融企业境内股票余额为11.47万亿元，同比增长6.9%。""",
            18,
            {"stock_end", "stock_yoy"},
        ),
        (
            """初步统计，2024年1月社会融资规模增量为6.5万亿元。其中，
            对实体经济发放的人民币贷款增加4.84万亿元；对实体经济发放的外币贷款折合人民币增加989亿元；
            委托贷款减少359亿元；信托贷款增加732亿元；未贴现的银行承兑汇票增加5635亿元；
            企业债券净融资4835亿元；政府债券净融资2947亿元；非金融企业境内股票融资422亿元。""",
            9,
            {"ytd_increment"},
        ),
    ],
)
def test_pbc_social_financing_accepts_separate_official_releases(
    section: str,
    expected_count: int,
    expected_measures: set[str],
) -> None:
    parsed = parse_official_context_document(
        (
            "<html><body><h1>2024年1月社会融资规模统计数据报告</h1>"
            "<p>文章来源： 2024-02-09 17:00:00</p><p>" + section + "</p></body></html>"
        ).encode(),
        family="pbc_social_financing",
        source_url=(
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/official-release/index.html"
        ),
        expected_period="2024-01",
        fetched_at=datetime(2024, 2, 9, 10, tzinfo=UTC),
    )

    assert len(parsed.scalars) == expected_count
    assert {item.dimensions["measure"] for item in parsed.scalars} == expected_measures


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


def test_pbc_loan_structure_contract_accepts_live_ytd_report_prose() -> None:
    parsed = parse_official_context_document(
        live_pbc_financial_report_document(),
        family="pbc_loan_structure",
        source_url=(
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html"
        ),
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 14, 9, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 9
    assert {
        (item.dimensions["borrower"], item.dimensions["tenor"], item.value)
        for item in parsed.scalars
    } == {
        ("household", "total", -8271.0),
        ("household", "short_term", -9281.0),
        ("household", "long_term", 1010.0),
        ("enterprise", "total", 110000.0),
        ("enterprise", "short_term", 43400.0),
        ("enterprise", "long_term", 53200.0),
        ("enterprise", "bill_financing", 11900.0),
        ("nonbank_financial", "total", -3944.0),
        ("all_rmb_loans", "total", 103800.0),
    }
    assert {item.dimensions["measure"] for item in parsed.scalars} == {"ytd_increment"}


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
            "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/5699853/index.html"
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
                "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/5699853/index.html"
            ),
            expected_period="2025-05-07",
            fetched_at=datetime(2025, 5, 7, 2, tzinfo=UTC),
        )


def test_nbs_industrial_value_added_contract_preserves_real_and_sa_measures(
    tmp_path: Path,
) -> None:
    content = official_table_document(
        title="2026年6月份规模以上工业增加值",
        release_at="2026-07-15 10:00",
        header=("指标", "当月实际同比（%）", "累计实际同比（%）", "季调环比（%）"),
        rows=(("规模以上工业增加值", 5.1, 6.4, 0.42),),
    )
    parsed = parse_official_context_document(
        content,
        family="nbs_industrial_value_added",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_1.html",
        expected_period="2026-06",
        fetched_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
    )

    assert {
        (item.dimensions["measure"], item.value, item.period_start) for item in parsed.scalars
    } == {
        ("current_month_real_yoy", 5.1, "2026-06-01"),
        ("ytd_real_yoy", 6.4, "2026-01-01"),
        ("mom_seasonally_adjusted", 0.42, "2026-06-01"),
    }
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    ingested = ingest_official_context_document(
        paths,
        content,
        family="nbs_industrial_value_added",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_1.html",
        expected_period="2026-06",
        fetched_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
        definition_version="metric-catalog-v0003",
        clock=lambda: datetime(2026, 7, 15, 3, tzinfo=UTC),
    )
    assert ingested.observation_count == 3
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


def test_nbs_industrial_value_added_contract_accepts_live_multilevel_tables() -> None:
    content = """
    <html><body>
      <h1>2026年7月份规模以上工业增加值增长4.5%</h1>
      <p>2026/08/17 15:00</p>
      <table>
        <tr><th>指标</th><th>7 月</th><th>1 — 7 月</th></tr>
        <tr><th>绝对量</th><th>同比增长（ % ）</th><th>绝对量</th><th>同比增长（ % ）</th></tr>
        <tr><td>规模以上工业增加值</td><td>…</td><td>4.5</td><td>…</td><td>5.3</td></tr>
      </table>
      <table>
        <tr><th>年份</th><th>月份</th><th>环比增速（ % ）</th></tr>
        <tr><td>2026 年</td><td>6 月</td><td>0.76</td></tr>
        <tr><td>7 月</td><td>0.11</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="nbs_industrial_value_added",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260817_1965055.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 17, 8, tzinfo=UTC),
    )

    assert {(item.dimensions["measure"], item.value) for item in parsed.scalars} == {
        ("current_month_real_yoy", 4.5),
        ("ytd_real_yoy", 5.3),
        ("mom_seasonally_adjusted", 0.11),
    }


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
    inventory = [item for item in parsed.scalars if item.metric_id == "CN_FINISHED_GOODS_INVENTORY"]
    assert {(item.dimensions["measure"], item.value, item.unit) for item in inventory} == {
        ("nominal_end_level", 67000.0, "hundred_million_cny"),
        ("official_yoy", 2.1, "percent"),
    }
    turnover = [item for item in parsed.scalars if item.metric_id == "CN_INVENTORY_TURNOVER"]
    assert {(item.dimensions["measure"], item.value, item.unit) for item in turnover} == {
        ("days", 19.2, "days"),
        ("official_yoy_change", 0.3, "days"),
    }


def test_nbs_industrial_finance_contract_accepts_live_tables_and_prose() -> None:
    content = """
    <html><body>
      <h1>2026年1—7月份全国规模以上工业企业利润增长17.6%</h1>
      <p>2026/08/27 09:30</p>
      <p>7 月末，规模以上工业企业应收账款 28.88 万亿元，同比增长 8.5% ；
      产成品存货 7.27 万亿元，增长 10.8% 。</p>
      <p>产成品存货周转天数为 21.3 天，比上年末增加 0.6 天。</p>
      <table>
        <tr><th>分 组</th><th>营业收入</th><th>营业成本</th><th>利润总额</th></tr>
        <tr><th>金额（亿元）</th><th>同比增长（ % ）</th>
        <th>金额（亿元）</th><th>同比增长（ % ）</th>
        <th>金额（亿元）</th><th>同比增长（ % ）</th></tr>
        <tr><td>总计</td><td>809230.7</td><td>6.5</td><td>687861.5</td><td>5.9</td><td>45820.6</td><td>17.6</td></tr>
      </table>
      <table>
        <tr><th>分 组</th><th>营业收入 利润率</th><th>每百元营业收入中的成本</th>
        <th>每百元营业收入中的费用</th><th>每百元资产实现的营业收入</th>
        <th>人均营业收入</th><th>资产负债率</th>
        <th>产成品 存货 周转天数</th><th>应收账款平均回收期</th></tr>
        <tr><th>1-7月</th><th>1-7月</th><th>1-7月</th><th>7月末</th><th>7月末</th><th>7月末</th><th>7月末</th><th>7月末</th></tr>
        <tr><td>（ % ）</td><td>（元）</td><td>（元）</td><td>（元）</td>
        <td>（万元 / 人）</td><td>（ % ）</td><td>（天）</td><td>（天）</td></tr>
        <tr><td>总计</td><td>5.66</td><td>85.00</td><td>8.41</td><td>72.2</td><td>191.3</td><td>58.4</td><td>21.3</td><td>71.9</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="nbs_industrial_finance",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202608/t20260827_1965126.html",
        expected_period="2026-07",
        fetched_at=datetime(2026, 8, 27, 2, tzinfo=UTC),
    )

    assert len(parsed.scalars) == 10
    inventory = [item for item in parsed.scalars if item.metric_id == "CN_FINISHED_GOODS_INVENTORY"]
    assert {(item.dimensions["measure"], item.value) for item in inventory} == {
        ("nominal_end_level", 72700.0),
        ("official_yoy", 10.8),
    }
    turnover = [item for item in parsed.scalars if item.metric_id == "CN_INVENTORY_TURNOVER"]
    assert {(item.dimensions["measure"], item.value) for item in turnover} == {
        ("days", 21.3),
        ("official_yoy_change", 0.6),
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

    assert {(item.dimensions["measure"], item.value, item.unit) for item in parsed.scalars} == {
        ("quarter_rate", 74.0, "percent"),
        ("yoy_change", -0.2, "percentage_points"),
        ("ytd_rate", 74.3, "percent"),
    }
    assert {item.period_end for item in parsed.scalars} == {"2026-06-30"}


def test_nbs_capacity_contract_accepts_live_multilevel_table() -> None:
    content = """
    <html><body>
      <h1>2026年二季度全国规模以上工业产能利用率为73.0%</h1>
      <p>2026/07/15 10:00</p>
      <table>
        <tr><th>行业</th><th>二季度</th><th>上半年</th></tr>
        <tr><th>产能利用率（ % ）</th><th>比上年同期增减（百分点）</th>
        <th>产能利用率（ % ）</th><th>比上年同期增减（百分点）</th></tr>
        <tr><td>工业</td><td>73.0</td><td>-1.0</td><td>73.3</td><td>-0.7</td></tr>
      </table>
    </body></html>
    """.encode()

    parsed = parse_official_context_document(
        content,
        family="nbs_capacity_utilization",
        source_url="https://www.stats.gov.cn/sj/zxfbhjd/202607/t20260715_1964130.html",
        expected_period="2026-Q2",
        fetched_at=datetime(2026, 7, 15, 3, tzinfo=UTC),
    )

    assert {(item.dimensions["measure"], item.value) for item in parsed.scalars} == {
        ("quarter_rate", 73.0),
        ("yoy_change", -1.0),
        ("ytd_rate", 73.3),
    }


def test_official_refresh_follows_listing_for_requested_period(tmp_path: Path) -> None:
    from pring_cycle.acquisition import AcquisitionRepository

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    article = listing + "202607/t20260709_1.html"
    documents = {article: core_cpi_document(2026, 6, (-0.1, 1.0, 1.2))}
    documents[listing] = """<html><body>
      <a href="202608/t20260809_2.html">2026年7月份居民消费价格</a>
      <a href="202607/t20260709_1.html">2026年6月份居民消费价格</a>
      <a href="202607/t20260709_1.html">2026年6月份居民消费价格</a>
    </body></html>""".encode()

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(
            content=documents[url], media_type="text/html", final_url=url, http_status=200
        )

    result = refresh_official_context_document(
        paths,
        family="nbs_core_cpi",
        source_url=listing,
        expected_period="2026-06",
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
    )
    evidence = EvidenceRepository(paths.database)
    trace = evidence.trace(result.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
    assert result.period == "2026-06"
    assert result.observation_count == 3
    assert trace.claims[0].value == -0.1
    assert trace.claims[0].source_reference.startswith(article + "#sha256=")
    assert trace.claims[0].provider == "国家统计局"
    assert trace.claims[0].certification_status == "awaiting_source_certification"
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert {r.parameters["source_url"] for r in receipts} == {listing, article}
    assert all(r.state == "validated" for r in receipts)
    for receipt in receipts:
        assert (
            acquisitions.read_content(receipt.acquisition_id, "raw")
            == documents[receipt.parameters["source_url"]]
        )


@pytest.mark.parametrize(
    ("family", "period", "listing", "title", "filename", "expected_count"),
    [
        (
            "nbs_core_cpi",
            "2026-08",
            "https://www.stats.gov.cn/sj/zxfb/",
            "2026年8月份居民消费价格同比上涨0.8%",
            "202609/t20260909_1965263.html",
            6,
        ),
        (
            "nbs_ppi",
            "2026-08",
            "https://www.stats.gov.cn/sj/zxfb/",
            "2026年8月份工业生产者出厂价格同比上涨3.8% 环比上涨0.4%",
            "202609/t20260909_1965262.html",
            9,
        ),
        (
            "nbs_pmi",
            "2026-08",
            "https://www.stats.gov.cn/sj/zxfb/",
            "2026年8月中国采购经理指数运行情况",
            "202608/t20260831_1965154.html",
            8,
        ),
        (
            "pbc_money",
            "2026-07",
            "https://www.pbc.gov.cn/diaochatongjisi/116219/",
            "2026年7月金融统计数据报告",
            "116225/2026081416320925645/index.html",
            4,
        ),
    ],
)
def test_official_refresh_resolves_family_period_from_listing(
    tmp_path: Path,
    family: str,
    period: str,
    listing: str,
    title: str,
    filename: str,
    expected_count: int,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    article_url = listing + filename
    article = (
        Path(__file__).parents[1] / "fixtures" / "official_period_fallback" / (family + ".html")
    ).read_bytes()
    listing_url = listing + ("index.html" if family == "pbc_money" else "")
    documents = {
        listing_url: f'<html><a href="{filename}">{title}</a></html>'.encode(),
        article_url: article,
    }

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(
            content=documents[url], media_type="text/html", final_url=url, http_status=200
        )

    result = refresh_official_context_document(
        paths,
        family=family,
        source_url=listing_url,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
    )
    assert result.observation_count == expected_count
    assert result.period == period
    evidence = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        trace = evidence.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.claims[0].source_reference.startswith(article_url + "#sha256=")


def test_listing_response_rejection_retains_original(tmp_path: Path) -> None:
    from pring_cycle.acquisition import AcquisitionRepository

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"
    body = b"not an HTML release listing"
    with pytest.raises(ValueError, match="official_context_response_media_type_invalid"):
        refresh_official_context_document(
            paths,
            family="nbs_core_cpi",
            source_url=listing,
            expected_period="2026-06",
            fetched_at=datetime.now(UTC),
            fetcher=lambda url: FetchedOfficialContextDocument(
                content=body, media_type="text/plain", final_url=url, http_status=200
            ),
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts = acquisitions.history()
    assert len(receipts) == 1
    assert acquisitions.read_content(receipts[0].acquisition_id, "raw") == body
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_CORE_CPI", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
    )


@pytest.mark.parametrize(
    ("anchors", "error"),
    [
        (
            '<a href="https://untrusted.example/value">2026年6月份居民消费价格</a>',
            "official_context_source_url_not_official",
        ),
        (
            '<a href="202607/first.html">2026年6月份居民消费价格</a>'
            '<a href="202607/second.html">2026年6月份居民消费价格</a>',
            "official_context_release_link_not_unique",
        ),
        # Only another period's release: nothing is listed for June (not ambiguous).
        (
            '<a href="202608/latest.html">2026年7月份居民消费价格</a>',
            "official_context_release_link_not_found",
        ),
    ],
)
def test_official_listing_rejects_untrusted_ambiguous_or_wrong_period_release(
    tmp_path: Path,
    anchors: str,
    error: str,
) -> None:
    from pring_cycle.acquisition import AcquisitionRepository

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    listing = "https://www.stats.gov.cn/sj/zxfb/"

    def fetch(url: str) -> FetchedOfficialContextDocument:
        assert url == listing
        return FetchedOfficialContextDocument(
            content=anchors.encode(), media_type="text/html", final_url=url, http_status=200
        )

    with pytest.raises(ValueError, match=error):
        refresh_official_context_document(
            paths,
            family="nbs_core_cpi",
            source_url=listing,
            expected_period="2026-06",
            fetched_at=datetime.now(UTC),
            fetcher=fetch,
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert len(receipts) == 1
    assert receipts[0].raw_hash is not None
    assert not EvidenceRepository(paths.database).metric_series(
        "CN_CORE_CPI", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
    )


@pytest.mark.parametrize(
    ("period", "label"),
    [
        ("2025-03", "一季度"),
        ("2025-06", "上半年"),
        ("2025-09", "前三季度"),
        ("2025-12", ""),
        ("2025-12", "全年"),
    ],
)
def test_official_money_listing_accepts_aggregate_period_titles(
    tmp_path: Path,
    period: str,
    label: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    listing = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"
    article = "https://www.pbc.gov.cn/diaochatongjisi/report.html"
    title = f"2025年{label}金融统计数据报告"
    # Synthetic values isolate title/period identity; this is not a historical source package.
    documents = {
        listing: f'<a href="{article}">{title}</a>'.encode(),
        article: (
            f"<h1>{title}</h1><p>文章来源：2026-01-15 09:30:00</p>"
            "<p>广义货币(M2)余额300万亿元，同比增长8%；"
            "狭义货币(M1)余额100万亿元，同比增长2%。</p>"
        ).encode(),
    }

    def fetch(url: str) -> FetchedOfficialContextDocument:
        return FetchedOfficialContextDocument(
            content=documents[url], media_type="text/html", final_url=url, http_status=200
        )

    result = refresh_official_context_document(
        paths,
        family="pbc_money",
        source_url=listing,
        expected_period=period,
        fetched_at=datetime.now(UTC),
        fetcher=fetch,
    )
    assert result.observation_count == 4
    assert result.period == period
