"""The 01 board's tendency and weak judgements (ADR-0043 revised, macro stage ticket 03).

A tendency names the stages it is tied with and their score; a weak judgement says which
dimensions it lacks and what it fell back on; an unknown dimension says what it lacks.
Neither is ever shown as explicit.
"""

from __future__ import annotations

from pathlib import Path

from pring_cycle.projections import ProjectionSet
from tests.integration.test_confirmation_publish import publish
from tests.integration.test_core_carry_forward import seed_cores, sessions
from tests.integration.test_macro_fallback import seed_policy_and_inventory, tied, weak_off_typical
from tests.integration.test_macro_judgement import MODEL, register_macro_model
from tests.integration.test_worker_execution import runtime
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


def cores_unavailable(tmp_path: Path, window: tuple[str, ...]) -> ProjectionSet:
    """test_macro_fallback's day: the commodity core lacks its last two sessions, two
    dimensions known; the ``window``'s days summarized with it."""
    paths = runtime(tmp_path)
    seed_cores(paths, commodity_missing=2)
    register_macro_model(paths)
    seed_policy_and_inventory(paths)
    return publish(paths, MODEL, window)


def test_with_the_cores_unavailable_the_board_says_it_took_the_last_confirmed_stage(
    tmp_path: Path,
) -> None:
    board = _board(cores_unavailable(tmp_path, (sessions()[-3].isoformat(),)))

    assert "宏观判断：第三阶段（弱，2 维中 2 维吻合）· 相对上次确认第三阶段 不变" in board
    assert (
        "弱判断：已知 2 维，缺信用、增长、物价，不足 3 维；三核心不可用，取上一确认阶段第三阶段"
    ) in board
    assert "价格验证 暂无价格阶段（债券牛市 · 股票牛市 · 商品不可用）" in board


def test_with_nothing_to_take_the_board_says_there_is_no_stage(tmp_path: Path) -> None:
    # Decision 49: the cores unavailable and no stage before them.
    board = _board(cores_unavailable(tmp_path, ()))

    assert "宏观判断：无可取阶段（证据不足、三核心不可用且无上一确认阶段）" in board
    assert "三核心不可用且无上一确认阶段，无可取阶段" in board
    assert "宏观判断无阶段，不比对" in board
