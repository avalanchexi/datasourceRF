"""Audit 06: a page whose title or address dates it otherwise than the gap's period.

The 中国政府网 page of 2025's August financial statistics was read for 2026-08: its sentences
say "前八个月" with no year, so only its title ("2025年8月…") and its address
(``/202509/12/``) told the year. Either now refuses every value of the page.
"""

from __future__ import annotations

import pytest

from pring_cycle.news_rules import PERIOD_MISMATCH, extract

LOANS = (
    "前八个月，分部门看，住户贷款增加7110亿元，其中，短期贷款减少3725亿元，"
    "中长期贷款增加1.08万亿元；"
)
GOV = "https://app.www.gov.cn/govdata/gov/202509/12/536583/article.html"
CAPACITY = "国家统计局数据显示，2026年二季度，全国规模以上工业产能利用率为73.0%。"
PARITY = (
    "中国人民银行授权中国外汇交易中心公布，9月30日银行间外汇市场人民币汇率中间价为"
    "1美元对人民币6.7351元。"
)


def taken(
    metric_id: str, period: str, text: str, *, title: str = "", url: str | None = None
) -> tuple[int, str | None]:
    extraction = extract((metric_id,), period, text, title=title, url=url)
    return len(extraction.values), extraction.reason


@pytest.mark.parametrize(
    ("title", "url"),
    [
        ("2025年8月金融统计数据报告", None),
        ("", GOV),
        # A title published before the period ended.
        ("8月金融统计数据（2026年7月31日）", None),
        ("", "https://finance.sina.com.cn/roll/2025-09-15/doc-inirxhzw3664291.shtml"),
        ("", "https://www.xinhuanet.com/fortune/20250914/47a41f1904504c27b22593b26aef5de0/c.html"),
        ("", "https://finance.people.com.cn/n1/2025/0914/c1004-40798571.html"),
        # A page of the period's year but titled another month's.
        ("2026年1—7月份金融统计数据", None),
    ],
    ids=[
        "title",
        "gov-url",
        "published-before",
        "sina-url",
        "xinhua-url",
        "people-url",
        "title-month",
    ],
)
def test_a_page_dated_otherwise_gives_no_value(title: str, url: str | None) -> None:
    assert taken("CN_LOAN_STRUCTURE", "2026-08", LOANS, title=title, url=url) == (
        0,
        PERIOD_MISMATCH,
    )


@pytest.mark.parametrize(
    ("title", "url"),
    [
        ("", None),
        ("【微头条】2026年8月金融统计数据报告_新浪财经_新浪网", None),
        ("8月金融统计数据出炉！前八个月人民币贷款增加10.44万亿元 _ 东方财富网", None),
        # Its own month among others: one wording of the period is enough.
        ("2026年8月金融数据：住户贷款较2025年8月少增", None),
        ("", "https://finance.sina.com.cn/roll/2026-09-15/doc-inirxhzw3664291.shtml?froms=ggmp"),
        ("", "https://app.www.gov.cn/govdata/gov/202609/14/536583/article.html"),
        # An article id that starts like a date is no date.
        ("", "https://wap.eastmoney.com/a/202509143873695615.html"),
        # Published a year on is not dated otherwise: a later text may restate a period.
        ("", "https://finance.sina.com.cn/roll/2027-09-15/doc-inirxhzw3664291.shtml"),
        # A full date in a title is the text's publication, here after the period.
        ("今日汇市晨报（2026年9月11日）：人民币兑美元中间价报6.7468", None),
        ("2025年8月以来最大降幅：8月金融数据（2026年9月14日）", None),
    ],
    ids=[
        "none",
        "title",
        "yearless-title",
        "title-also-names-another",
        "url",
        "gov-url",
        "article-id",
        "later-url",
        "publication-title",
        "comparison-and-publication",
    ],
)
def test_a_page_dated_the_period_or_not_at_all_gives_its_values(
    title: str, url: str | None
) -> None:
    assert taken("CN_LOAN_STRUCTURE", "2026-08", LOANS, title=title, url=url) == (3, None)


@pytest.mark.parametrize(
    ("title", "kept"),
    [
        ("国家统计局：2026年二季度全国规模以上工业产能利用率为73.0%", True),
        ("2026年1—6月份工业产能", True),
        ("国家统计局：2025年二季度全国规模以上工业产能利用率为74.0%", False),
        ("2026年一季度工业产能利用率", False),
    ],
)
def test_a_quarter_is_dated_by_its_quarter_or_a_month_of_it(title: str, kept: bool) -> None:
    count, reason = taken("CN_CAPACITY_UTILIZATION", "2026-Q2", CAPACITY, title=title)
    assert (count > 0, reason) == ((True, None) if kept else (False, PERIOD_MISMATCH))


@pytest.mark.parametrize(
    ("title", "url", "kept"),
    [
        ("2026年9月30日中国外汇交易中心受权公布人民币汇率中间价公告", None, True),
        ("2026年9月29日中国外汇交易中心受权公布人民币汇率中间价公告", None, False),
        ("2025年9月30日中国外汇交易中心受权公布人民币汇率中间价公告", None, False),
        ("", "https://finance.sina.com.cn/jjxw/2026-09-30/doc-initqkpm5764738.shtml", True),
        # A day's fixing is not published the day before.
        ("", "https://finance.sina.com.cn/jjxw/2026-09-29/doc-initqkpm5764738.shtml", False),
        # An address dated by its month only dates no day.
        ("", "https://www.gov.cn/lianbo/fabu/202609/content_7041000.htm", True),
        ("", "https://www.gov.cn/lianbo/fabu/202608/content_7041000.htm", False),
    ],
)
def test_a_day_is_dated_by_its_day(title: str, url: str | None, kept: bool) -> None:
    count, reason = taken("CN_USDCNY_CENTRAL_PARITY", "2026-09-30", PARITY, title=title, url=url)
    assert (count > 0, reason) == ((True, None) if kept else (False, PERIOD_MISMATCH))


@pytest.mark.parametrize(
    ("title", "url", "kept"),
    [
        ("2027年1月5日起降准0.5个百分点", None, True),
        # An event is announced before the day it takes effect.
        ("2026年12月25日央行宣布降准", None, True),
        ("", "https://finance.sina.com.cn/roll/2026-12-25/doc-inirxhzw3664291.shtml", True),
        ("2026年11月央行宣布降准", None, False),
        ("", "https://finance.sina.com.cn/roll/2026-11-25/doc-inirxhzw3664291.shtml", False),
    ],
)
def test_an_event_may_be_dated_by_the_month_before_its_day(
    title: str, url: str | None, kept: bool
) -> None:
    text = (
        "中国人民银行决定于1月5日下调金融机构存款准备金率0.5个百分点"
        "（不含已执行5%存款准备金率的金融机构）。"
    )

    count, reason = taken("CN_RRR_EVENT", "2027-01-05", text, title=title, url=url)
    assert (count > 0, reason) == ((True, None) if kept else (False, PERIOD_MISMATCH))


@pytest.mark.parametrize(
    ("text", "title", "kept"),
    [
        # The body's heading dates the yearless "前八个月" after it.
        ("2025年8月金融统计数据报告\n" + LOANS, "", False),
        ("2026年8月金融统计数据报告\n" + LOANS, "", True),
        # A compared period is no heading, nor is the dateline's day.
        ("住户贷款较2025年8月少增。" + LOANS, "", True),
        ("发布时间：2027年1月14日 17:00\n" + LOANS, "", True),
        # A compared period in the title is not its own.
        (LOANS, "8月金融数据：住户贷款创2025年8月以来最大降幅", True),
        # A later date in the title does not hide the year its period is written in.
        (LOANS, "2025年8月金融统计数据报告（2026年9月14日转载）", False),
        # A source named is no comparison.
        (LOANS, "数据来自2025年8月金融统计数据报告", False),
        # The text turns back to its own year: an earlier year written before does not hold.
        ("2025年8月基数偏高。今年" + LOANS, "", True),
        # Its title does not lift a year its body writes: rather lose the value (audit 06).
        ("历史数据回顾：2025年8月金融统计数据报告\n" + LOANS, "2026年8月金融统计数据报告", False),
    ],
    ids=[
        "heading-other-year",
        "heading-year",
        "compared",
        "dateline",
        "title-compared",
        "title-republished",
        "title-source",
        "own-year",
        "titled-history",
    ],
)
def test_a_text_s_own_written_year_dates_its_yearless_periods(
    text: str, title: str, kept: bool
) -> None:
    count, reason = taken("CN_LOAN_STRUCTURE", "2026-08", text, title=title)
    assert (count > 0, reason) == ((True, None) if kept else (False, PERIOD_MISMATCH))


@pytest.mark.parametrize(
    ("title", "kept"),
    [("2026年第二季度工业产能利用率", True), ("2025年第二季度工业产能利用率", False)],
)
def test_an_ordinal_quarter_keeps_its_year(title: str, kept: bool) -> None:
    count, reason = taken("CN_CAPACITY_UTILIZATION", "2026-Q2", CAPACITY, title=title)
    assert (count > 0, reason) == ((True, None) if kept else (False, PERIOD_MISMATCH))
