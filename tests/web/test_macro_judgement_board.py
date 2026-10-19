"""The 01 board headed by the macro stage judgement (ADR-0043, macro stage ticket 02).

A set the day summary judged heads the board with the judgement and lists the five
dimensions by their three cycles; an older set without one keeps its board and says so,
with nothing judged on the page.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

from pring_cycle.projections import ProjectionSet
from tests.integration.test_macro_judgement import judged
from tests.web.test_conclusion_board import _asset, _board, _projection

NO_JUDGEMENT = "该投影生成时尚无宏观判断"


def test_the_board_heads_with_the_judgement_and_its_step_from_the_last_confirmed_stage(
    tmp_path: Path,
) -> None:
    board = _board(judged(tmp_path))

    assert (
        "宏观判断 宏观判断：第五阶段（明确，5 维中 4 维吻合）· 相对上次确认第三阶段 前进 2 步"
    ) in board
    # The price stage verifies it below (ticket 06), its rows in the row's drawer.
    assert (
        "价格验证 价格阶段：第三阶段（债券牛市 · 股票牛市 · 商品牛市） · "
        "第五阶段预期：债券熊市 · 股票熊市 · 商品牛市 · 债券、股票偏离"
    ) in board
    assert "原因 典型组合：债券牛市 · 股票牛市 · 商品牛市 → Stage III" in board
    assert NO_JUDGEMENT not in board


def test_the_five_dimensions_are_listed_by_their_three_cycles(tmp_path: Path) -> None:
    board = _board(judged(tmp_path))

    assert (
        "货币周期 "
        "政策：中性 · 吻合 · 120 日内无降息、LPR 下调、降准或上调 "
        "信用：下行 · 低位 · 吻合 · 社融下行；M1/M2 不明 "
        "经济周期 "
        "增长：下行 · 高位 · 吻合 · PMI 下行（分化）；工业增加值上行；GDP 下行；"
        "产能利用率不明；工业企业盈利不明 "
        "物价：上行 · 高位 · 吻合 · PPI 上行；CPI 上行；PMI 价格不明 "
        "库存周期 "
        "库存：主动补库存 · 不吻合 · 库存象限 2026-07-31"
    ) in board


def test_an_older_set_keeps_its_board_and_says_it_has_no_judgement() -> None:
    board = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
            current_stage="stage_ii",
            last_confirmed_stage="stage_ii",
            stage_reason="canonical_combination",
        )
    )

    assert "正式阶段 第二阶段 · Stage II" in board and NO_JUDGEMENT in board
    assert "宏观判断：" not in board
    # Nothing is published, so nothing is said to be missing.
    assert NO_JUDGEMENT not in _board(None)


def test_the_right_column_beside_the_judgement_is_named_further_notes(tmp_path: Path) -> None:
    board = _board(judged(tmp_path))

    # Decision 59: the notes a reader sets beside the judgement, not its confirmation.
    assert "补充说明 价格一致性 " in board
    assert "旁注" not in board


def _bond_policy(projection: ProjectionSet, value: str, text: str) -> ProjectionSet:
    """The set with its bond attribution's policy axis read as ``value``."""
    datasets = copy.deepcopy(projection.datasets)
    note = datasets["macro"]["bond_attribution"]
    for axis in note["axes"]:  # type: ignore[index]
        if axis["axis"] == "policy":
            axis.update(value=value, text=text)
    return replace(projection, datasets=datasets)


def test_a_bond_attribution_policy_read_apart_from_the_policy_dimension_says_why(
    tmp_path: Path,
) -> None:
    projection = judged(tmp_path)
    eased = _board(_bond_policy(projection, "easing", "宽松"))

    # The policy dimension is neutral: no cut or hike in 120 days.
    assert (
        "政策维度宽松、增长通胀（过热、物价）未确认（附注，不计数）；"
        "与宏观政策维中性口径不同：债券归因的政策维度兼看 DR007 流动性走势，"
        "宏观政策维只按 120 日内降息、LPR 下调、降准等动作判定"
    ) in eased
    # Read alike, or the axis not read, there is nothing to tell apart.
    assert "口径不同" not in _board(_bond_policy(projection, "neutral", "中性"))
    assert "口径不同" not in _board(projection)
