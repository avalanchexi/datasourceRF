"""Worker gaps 01: the media's wording of the day's central parity.

CLS wrote 10-15's fixing as "人民币兑美元中间价报6.7253" (tests/fixtures/central_parity), not
in the PBC's "1美元对人民币…元": the run of 10-15 refused it (rule_not_matched) and carried
10-14's value. The wording is read now, still only for the day it names, only for the US
dollar and only quoted in yuan per dollar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pring_cycle.news_rules import (
    PERIOD_MISMATCH,
    RULE_NOT_MATCHED,
    extract,
    page_title,
    plain_text,
)

PAGE = Path(__file__).parents[1] / "fixtures" / "central_parity" / "cls_2505221_20261015.html"
URL = "https://www.cls.cn/detail/2505221"
PARITY = ("CN_USDCNY_CENTRAL_PARITY",)


def read(period: str, content: str | None = None) -> tuple[list[float], str | None]:
    content = content if content is not None else PAGE.read_text()
    extraction = extract(PARITY, period, plain_text(content), title=page_title(content), url=URL)
    return [value.value for value in extraction.values], extraction.reason


def test_the_cls_page_of_10_15_gives_that_day_s_central_parity() -> None:
    extraction = extract(
        PARITY, "2026-10-15", plain_text(PAGE.read_text()), title=page_title(PAGE.read_text())
    )

    (value,) = extraction.values
    assert value.value == 6.7253
    assert value.dimensions == {"currency_pair": "USD/CNY", "quote_direction": "CNY per USD"}
    assert "人民币兑美元中间价报6.7253" in value.quote


def test_the_page_gives_no_other_day_s_central_parity() -> None:
    assert read("2026-10-14") == ([], PERIOD_MISMATCH)


@pytest.mark.parametrize(
    ("text", "taken"),
    [
        ("财联社9月30日电，人民币对美元中间价报6.7351，上调12点。", [6.7351]),
        ("财联社9月30日电，美元兑人民币中间价报6.7351。", [6.7351]),
        # Another currency's fixing.
        ("财联社9月30日电，人民币兑欧元中间价报7.8875，上调12点。", []),
        # A yuan's worth in dollars is the other direction.
        ("财联社9月30日电，人民币兑美元中间价报0.14848美元。", []),
    ],
)
def test_only_a_dollar_fixing_in_yuan_per_dollar_is_taken(text: str, taken: list[float]) -> None:
    values, reason = read("2026-09-30", f"<p>{text}</p>")
    assert values == taken
    assert reason == (None if taken else RULE_NOT_MATCHED)
