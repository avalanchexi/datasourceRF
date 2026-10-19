"""The 01 board's tendency and weak judgements (ADR-0043 revised, macro stage ticket 03).

A tendency names the stages it is tied with and their score; a weak judgement says which
dimensions it lacks and what it fell back on; an unknown dimension says what it lacks.
Neither is ever shown as explicit.
"""

from __future__ import annotations

from pathlib import Path

from tests.integration.test_macro_fallback import tied, weak_off_typical
from tests.web.test_conclusion_board import _board


def test_a_tendency_names_the_stages_it_is_tied_with_and_their_score(tmp_path: Path) -> None:
    board = _board(tied(tmp_path, "bull", "bull", "bear"))

    assert ("宏观判断：第三阶段（倾向，5 维中 3 维吻合）· 相对上次确认第二阶段 前进 1 步") in board
    assert "倾向第三阶段（与第五阶段、第六阶段并列，各 3 维）：取离上次确认第二阶段最近者" in board
    assert "（明确" not in board


def test_a_weak_judgement_says_what_it_lacks_and_what_it_fell_back_on(tmp_path: Path) -> None:
    board = _board(weak_off_typical(tmp_path))

    assert "宏观判断：第三阶段（弱，2 维中 2 维吻合）· 相对上次确认第三阶段 不变" in board
    assert (
        "弱判断：已知 2 维，缺信用、增长、物价，不足 3 维；"
        "退回价格组合推断：债券牛市 · 股票熊市 · 商品牛市与第一阶段、第三阶段、第五阶段各差 1 项，"
        "取离上次确认第三阶段最近者"
    ) in board
    assert "（明确" not in board


def test_an_unknown_dimension_says_what_it_lacks(tmp_path: Path) -> None:
    board = _board(weak_off_typical(tmp_path))

    assert "信用：不明 · 不计分 · 明确者不足半数（0/2）：缺当期读数：社融、M1/M2" in board
    assert (
        "增长：不明 · 不计分 · 明确者不足半数（1/5）：工业增加值上行；"
        "缺当期读数：PMI、GDP、产能利用率、工业企业盈利"
    ) in board
