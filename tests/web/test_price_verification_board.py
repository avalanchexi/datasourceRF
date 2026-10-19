"""The price verification row under the macro judgement and its drawer (ADR-0043, macro
stage ticket 06).

The row states the price stage, or the noncanonical combination, the three assets the
judged stage expects and whether they agree or which asset is off; its drawer holds the
price stage's reason and rows, the one-asset comparisons and, with a price stage only, the
confirmation, which is still counted against the price stage.
"""

from __future__ import annotations

from pathlib import Path

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.integration.test_price_verification import verified
from tests.web.test_conclusion_board import _board
from tests.web.test_dashboard_contract import _hrefs
from tests.web.test_overseas_cards import _by_id, _find, _words

DRAWER = "drawer-conclusion-price-verification"
EXPECTED = "第五阶段预期：债券熊市 · 股票熊市 · 商品牛市"


def _drawer(projection: ProjectionSet) -> str:
    return _words(_by_id(dashboard_page("/", projection, (), ()), DRAWER))


def _columns(projection: ProjectionSet) -> str:
    """The board's two columns, without the drawers rendered beside them."""
    page = dashboard_page("/", projection, (), ())
    (board,) = _find(page, lambda item: getattr(item, "className", None) == "conclusion-board")
    assert isinstance(board, Component)
    return _words(board)


def test_the_row_names_the_asset_a_typical_price_stage_is_off_by(tmp_path: Path) -> None:
    projection = verified(tmp_path, "bond", "stock", "commodity")
    board = _board(projection)

    assert (
        f"价格验证 价格阶段：第六阶段（债券熊市 · 股票熊市 · 商品熊市） · {EXPECTED} · 商品偏离"
    ) in board
    # It follows the dimensions and the signal list (decision 21), and opens its drawer.
    assert board.index("库存周期") < board.index("信号清单") < board.index("价格验证 ")
    assert "#" + DRAWER in _hrefs(dashboard_page("/", projection, (), ()))


def test_the_drawer_holds_the_price_stage_rows_and_its_confirmation(tmp_path: Path) -> None:
    projection = verified(tmp_path, "bond", "stock", "commodity")
    drawer = _drawer(projection)

    assert "原因 典型组合：债券熊市 · 股票熊市 · 商品熊市 → Stage VI" in drawer
    assert "上次确认 " in drawer and "核心沿用 无" in drawer and "判法 " in drawer
    # The confirmation is still counted against the price stage, and is only here.
    assert "确认度（对价格阶段第六阶段） 可评估 · " in drawer
    assert "政策" in drawer[drawer.index("确认度（") :]
    columns = _columns(projection)
    assert "确认度" not in columns and "可评估 · " not in columns
    # The old rows under the price stage are gone from the board itself.
    assert "原因 典型组合" not in columns and "价格阶段 第六阶段" not in columns


def test_a_consistent_price_stage_says_so(tmp_path: Path) -> None:
    board = _board(verified(tmp_path, "bond", "stock"))

    assert (
        f"价格验证 价格阶段：第五阶段（债券熊市 · 股票熊市 · 商品牛市） · {EXPECTED} · 一致"
    ) in board


def test_a_noncanonical_combination_keeps_its_comparisons_and_shows_no_confirmation(
    tmp_path: Path,
) -> None:
    projection = verified(tmp_path, "stock")

    assert (
        f"价格验证 非典型组合（债券牛市 · 股票熊市 · 商品牛市） · {EXPECTED} · 债券偏离"
    ) in _board(projection)
    drawer = _drawer(projection)
    assert (
        "只差一项 Stage I 差商品：当前牛市 → 要求熊市，30 日候选牛市 "
        "Stage III 差股票：当前熊市 → 要求牛市，30 日候选熊市 "
        "Stage V 差债券：当前牛市 → 要求熊市，30 日候选牛市"
    ) in drawer
    assert "确认度" not in drawer and "确认度" not in _columns(projection)
