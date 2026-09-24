"""Backlog ⑤: the real run's AI candidates quoted "9月23日" with no year, which no day
check can place; the prompt now says how the period must be written."""

from __future__ import annotations

import json

from pring_cycle.ai_websearch import _prompt
from pring_cycle.runs import RetrievalScope


def prompt(period: str) -> dict[str, object]:
    scope = RetrievalScope("full:x", ("CN_USDCNY_CLOSE_1630",), period, "P2", None)
    return json.loads(_prompt(scope, "query", ("www.cls.cn",)))


def test_a_day_is_asked_for_with_its_year_written() -> None:
    asked = prompt("2026-09-23")

    assert asked["period_wording"] == "2026年9月23日"
    assert "年份" in str(asked["instruction"])


def test_a_month_is_asked_for_as_the_month_of_its_year() -> None:
    assert prompt("2026-08")["period_wording"] == "2026年8月"
    assert prompt("2026-Q2")["period_wording"] == "2026年第二季度"
