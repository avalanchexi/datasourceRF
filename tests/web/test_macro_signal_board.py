"""The signal list on the 01 board and the same-source labels of 02 pointing to it (ADR-0043,
macro stage ticket 04).

The list is read from the published judgement: grouped forward, back and hold, then the
open and the unmapped, each signal with what it reads, the transition it supports, its
maturity and, for a price signal, that it is of the same source and does not vote. The
price consistency card and the peers in 02 point to their signals in the list.
"""

from __future__ import annotations

from pathlib import Path

from pring_cycle.dashboard import dashboard_page
from tests.integration.test_macro_signals import listed_day
from tests.web.test_conclusion_board import _asset, _board, _projection
from tests.web.test_dashboard_contract import _hrefs, _text

SAME_SOURCE = "同源，不参与投票"


def test_the_board_lists_the_signals_by_their_groups(tmp_path: Path) -> None:
    board = _board(listed_day(tmp_path))

    assert (
        "信号清单 "
        "支持后退 "
        "商品对债：商品强于债 29.53 个百分点，20 日走强 10.86 个百分点 · 符合第三→第四阶段"
        f" · 成形 · {SAME_SOURCE} "
        "债券同类 2/2 转熊（10 年国债价格指数、中债 030 全价），与债券核心牛市背离"
        f" · 符合第三→第四阶段 · 成形 · {SAME_SOURCE} "
    ) in board
    assert (
        "支持维持 "
        "股票对商品：股票弱于商品 29.53 个百分点，20 日走弱 10.86 个百分点 · 符合第四→第五阶段"
        f" · 成形 · {SAME_SOURCE} "
    ) in board
    assert (
        "资产转向（未映射阶段） "
        "股票同类 2/3 转熊（中证 300、中证 500），与股票核心牛市背离 · 翻转后为非典型组合"
        f" · 成形 · {SAME_SOURCE}"
    ) in board
    # A divergence is no price signal: it votes in its dimension, by its main member.
    pmi = board[board.index("PMI 分化：") :].split(" · 萌芽")[0]
    # Its tie is broken toward the last confirmed stage III (ticket 03): a step back.
    assert pmi == (
        "PMI 分化：新订单上行（主成员下行）；若 PMI 改投少数方向，增长上行，"
        "判第三阶段（倾向，5 维中 3 维吻合）"
    )
    assert board.index("支持后退") < board.index("PMI 分化：") < board.index("支持维持")
    # The groups keep their order; the turn watch row is merged into the list.
    assert board.index("支持后退") < board.index("支持维持") < board.index("资产转向（未映射阶段）")
    assert "转折观察 " not in board


def test_the_same_source_labels_of_02_point_to_their_signals(tmp_path: Path) -> None:
    projection = listed_day(tmp_path)
    page = dashboard_page("/", projection, (), ())
    text = " ".join(_text(page).split())

    assert "价格内部一致性（不计数）" not in text
    assert f"价格内部一致性（{SAME_SOURCE}） " in text
    # (Each link is its own element: the text reads them apart.)
    assert "见 01 信号清单： 商品对债（支持后退） 、 股票对商品（支持维持）" in text
    assert {"#signal-R2", "#signal-R11", "#signal-P1", "#signal-P3"} <= set(_hrefs(page))
    # The peers read as signals point to theirs; a peer not turning says it is of the
    # same source alone, and the old note is gone.
    assert "仅观察，不计数" not in text
    assert f"用途 债券价格观察； {SAME_SOURCE} · 见 01 信号清单： 债券同类转熊（支持后退）" in text
    assert f"用途 {SAME_SOURCE} · 见 01 信号清单： 股票同类转熊（资产转向（未映射阶段））" in text
    # 中证 1000 rises with its core: of the same source, pointing to nothing.
    assert f"用途 {SAME_SOURCE} 证据" in text


def test_an_older_set_keeps_its_labels_and_its_turn_watch_row() -> None:
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
        current_stage="stage_ii",
        last_confirmed_stage="stage_ii",
        stage_reason="canonical_combination",
    )

    assert "转折观察 " in _board(projection) and "信号清单" not in _board(projection)
