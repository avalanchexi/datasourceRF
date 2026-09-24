"""Phase two #07: the CPI and PPI news rules, on the real texts of the 8/2026 release day."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.news_rules import PERIOD_MISMATCH, RULE_NOT_MATCHED, extract, plain_text

SAMPLE = Path(__file__).parents[1] / "fixtures" / "news" / "major_news_20260909_cpi_ppi.json"


def item(source: str, title_part: str) -> dict[str, Any]:
    items = json.loads(SAMPLE.read_text())["items"]
    return next(i for i in items if i["src"] == source and title_part in i["title"])


def values(metric_id: str, period: str, text: str) -> dict[tuple[str, str], float]:
    return {
        (v.dimensions["category"], v.dimensions["measure"]): v.value
        for v in extract((metric_id,), period, plain_text(text)).values
    }


@pytest.mark.parametrize(
    ("source", "title_part"),
    [
        ("新华网", "2026年8月份居民消费价格"),
        ("财联社", "国家统计局"),
        ("中新经纬", "8月CPI"),
        ("华尔街见闻", "8月CPI"),
    ],
)
def test_cpi_rules_read_the_three_headline_members(source: str, title_part: str) -> None:
    assert values("CN_CPI_HEADLINE", "2026-08", item(source, title_part)["content"]) == {
        ("headline", "yoy"): 0.8,
        ("headline", "mom"): 0.4,
        ("headline", "cumulative_average_yoy"): 0.9,
    }


@pytest.mark.parametrize(
    ("source", "title_part"),
    [("新华网", "工业生产者出厂价格"), ("财联社", "国家统计局"), ("华尔街见闻", "8月CPI")],
)
def test_ppi_rules_read_the_members_the_text_states(source: str, title_part: str) -> None:
    # The component cumulative averages are only in the official table image.
    assert values("CN_PPI", "2026-08", item(source, title_part)["content"]) == {
        ("headline", "yoy"): 3.8,
        ("headline", "mom"): 0.4,
        ("headline", "cumulative_average_yoy"): 2.0,
        ("means_of_production", "yoy"): 5.0,
        ("means_of_production", "mom"): 0.4,
        ("consumer_goods", "yoy"): -0.5,
        ("consumer_goods", "mom"): 0.2,
    }


def test_an_interpretation_article_matches_no_rule() -> None:
    """The statistician's reading says "全国CPI上涨0.8%": not the release sentence."""
    text = plain_text(item("新华网", "解读")["content"])

    for metric_id in ("CN_CPI_HEADLINE", "CN_PPI"):
        extraction = extract((metric_id,), "2026-08", text)
        assert (extraction.values, extraction.reason) == ((), RULE_NOT_MATCHED)


def test_another_period_is_not_taken() -> None:
    text = plain_text(item("财联社", "国家统计局")["content"])

    extraction = extract(("CN_CPI_HEADLINE",), "2026-07", text)

    assert (extraction.values, extraction.reason) == ((), PERIOD_MISMATCH)


def test_the_quote_is_the_matched_sentence() -> None:
    text = plain_text(item("新华网", "2026年8月份居民消费价格")["content"])

    quotes = {
        v.dimensions["measure"]: v.quote
        for v in extract(("CN_CPI_HEADLINE",), "2026-08", text).values
    }

    assert quotes["yoy"] == "2026年8月份，全国居民消费价格同比上涨0.8%。"
    assert quotes["cumulative_average_yoy"] == "1—8月平均，全国居民消费价格比上年同期上涨0.9%。"


def test_a_contradicting_text_gives_no_value_for_that_member() -> None:
    text = "2026年8月份，全国居民消费价格同比上涨0.8%。更正：8月份，全国居民消费价格同比上涨0.9%。"

    assert extract(("CN_CPI_HEADLINE",), "2026-08", text).values == ()


def test_a_fall_is_negative_and_flat_is_zero() -> None:
    text = "2026年2月份，全国居民消费价格同比下降0.7%。2月份，全国居民消费价格环比持平。"

    assert values("CN_CPI_HEADLINE", "2026-02", text) == {
        ("headline", "yoy"): -0.7,
        ("headline", "mom"): 0.0,
    }
