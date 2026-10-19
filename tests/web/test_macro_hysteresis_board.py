"""The hysteresis on the 01 board (ADR-0043, macro stage ticket 05).

While a new judgement is counted, the main conclusion keeps its stage and confidence,
noted as held with the day's raw judgement (decision 45), and the run is listed with the
signals: 倾向转向第 X 阶段（已 k/10 日）(decision 26).
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

from pring_cycle.dashboard import dashboard_page
from tests.integration.test_macro_hysteresis import (
    SF_JULY,
    SF_REVISED,
    last,
    macro_day,
    revise_credit,
)
from tests.integration.test_macro_judgement import publish_from
from tests.web.test_dashboard_contract import _text


def test_a_held_conclusion_is_noted_and_its_run_listed_with_the_signals(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    revise_credit(paths, SF_REVISED, on=-2)
    projection = publish_from(paths, last(3))

    text = " ".join(_text(dashboard_page("/", projection, (), ())).split())

    assert (
        "宏观判断：第五阶段（明确，5 维中 3 维吻合）· 相对上次确认第三阶段 前进 2 步 "
        "滞回保持，当日原始判断：第三阶段（倾向）"
    ) in text
    assert "信号清单 支持后退 倾向转向第三阶段（已 2/10 日）" in text
    # The day's raw tendency says what it was tied with, apart; the dimensions are told
    # against the stage held, not the day's raw one.
    assert (
        "当日原始判断依据：倾向第三阶段（与第四阶段、第五阶段并列，各 3 维）："
        "取离上次确认第三阶段最近者"
    ) in text
    assert "信用：上行 · 高位 · 不吻合" in text
    assert "增长：下行 · 高位 · 吻合" in text


def test_a_held_tendency_is_told_with_the_tie_it_was_taken_from(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    window = last(3)
    revise_credit(paths, SF_REVISED, on=-12)
    revise_credit(paths, SF_JULY, on=-1)
    projection = publish_from(paths, window)

    text = " ".join(_text(dashboard_page("/", projection, (), ())).split())

    # Decision 24: the held tendency says what it was tied with, each stage's score and the
    # day; the day's own judgement, explicit, has no tie to tell.
    assert (
        "滞回保持，当日原始判断：第五阶段（明确） "
        f"倾向第三阶段（与第四阶段、第五阶段并列，各 3 维，{window[1]} 判断）："
        "取离上次确认第三阶段最近者"
    ) in text


def _divergence(key: str, name: str, value: str, stage: str, **joined: Any) -> dict[str, Any]:
    """A credit indicator diverging, recounted on its minority's direction as ``stage``
    (decision 47), grouped against the main conclusion: a step back."""
    return {
        "id": f"D-{key}",
        "kind": "divergence",
        "group": "back",
        "maturity": "forming",
        "indicator": {"key": key, "name": name, "dimension": "credit", "main_direction": "down"},
        "minority": {"members": ["新增"], "direction": "up"},
        "rejudged": {
            "dimension": {"dimension": "credit", "value": value},
            "stage": stage,
            "confidence": "tendency",
            "known": 5,
            "matched": 3,
            **joined,
        },
    }


def test_a_divergence_held_off_that_leaves_the_raw_judgement_as_it_is_says_so(
    tmp_path: Path,
) -> None:
    paths = macro_day(tmp_path)
    revise_credit(paths, SF_REVISED, on=-2)
    projection = publish_from(paths, last(3))
    datasets = copy.deepcopy(projection.datasets)
    block = datasets["cycle_overview"]["macro_judgement"]
    # Held at stage V against the day's raw stage III tendency: recounted, the loans still
    # judge III, social financing judges IV.
    block["signals"] = [  # type: ignore[index]
        *block["signals"],  # type: ignore[index]
        _divergence("loans", "贷款", "down", "stage_iii", joined=True),
        _divergence("social_financing", "社融", "up", "stage_iv"),
    ]

    text = " ".join(
        _text(dashboard_page("/", replace(projection, datasets=datasets), (), ())).split()
    )

    # Decision 60: both stay in their group; the one leaving the raw judgement says so.
    back = text[text.index("支持后退") : text.index("价格验证 ")]
    assert (
        "贷款分化：新增上行（主成员下行）；若贷款按少数方向计入信用维，信用下行，"
        "判第三阶段（倾向，5 维中 3 维吻合） · 不改变当日原始判断 · 成形"
    ) in back
    social = back[back.index("社融分化：") :]
    assert "判第四阶段（倾向，5 维中 3 维吻合） · 成形" in social
    assert "不改变当日原始判断" not in social
