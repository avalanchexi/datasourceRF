"""The 01 conclusion board under a noncanonical combination: the one-asset differences the
Worker published, the collapsed confirmation line and the transition watch (cockpit
layout ticket 03).

Each case builds a small projection by hand and asserts the reader-visible sentence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pring_cycle.evidence import EvidenceRepository
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from tests.integration.test_confirmation_publish import MODEL, publish, register_confirmation_model
from tests.integration.test_core_carry_forward import CORES, sessions
from tests.integration.test_decertified_main_chain import claim
from tests.integration.test_worker_execution import runtime, seed_independent_calendar
from tests.web.test_conclusion_board import _asset, _board, _conclusion, _projection
from tests.web.test_conclusion_board_right import (
    COVERAGE,
    GAPS,
    PRICE_CONSISTENCY,
    _inventory,
)
from tests.web.test_dashboard_contract import _text
from tests.web.test_overseas_cards import _by_id, _find, _words

# Bond bull · stock bear · commodity bull differs from three typical stages by one asset.
BASIS = {
    "version": "noncanonical-basis-v1",
    "last_confirmed_stage": "stage_iii",
    "comparisons": [
        {
            "stage": "stage_i",
            "asset": "commodity",
            "current_state": "bull",
            "required_state": "bear",
            "candidate_30d": "bear",
            "candidate_state": None,
            "candidate_days": 0,
            "persistence_required": 8,
        },
        {
            "stage": "stage_iii",
            "asset": "stock",
            "current_state": "bear",
            "required_state": "bull",
            "candidate_30d": None,
            "candidate_state": None,
            "candidate_days": 0,
            "persistence_required": 8,
        },
        {
            "stage": "stage_v",
            "asset": "bond",
            "current_state": "bull",
            "required_state": "bear",
            "candidate_30d": "bull",
            "candidate_state": None,
            "candidate_days": 0,
            "persistence_required": 8,
        },
    ],
}


def _noncanonical(**overview: Any) -> Any:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        stage_reason="noncanonical_combination",
        last_confirmed_stage="stage_iii",
        **overview,
    )


def test_the_one_asset_differences_are_read_from_the_published_basis() -> None:
    board = _board(_noncanonical(noncanonical_basis=BASIS))

    assert (
        "只差一项 Stage I 差商品：当前牛市 → 要求熊市，30 日候选熊市 "
        "Stage III 差股票：当前熊市 → 要求牛市，30 日候选无 "
        "Stage V 差债券：当前牛市 → 要求熊市，30 日候选牛市"
    ) in board
    rows = [" 原因 ", " 只差一项 ", " 上次确认 "]
    assert [board.index(row) for row in rows] == sorted(board.index(row) for row in rows)


def test_an_old_set_without_the_basis_shows_no_difference_row() -> None:
    board = _board(_noncanonical())

    assert "只差一项" not in board
    assert "要求熊市" not in board


def test_the_reason_reads_with_the_key_values_beside_it() -> None:
    confirmation = _inventory(
        "active_destocking", None, demand="down", production="down", inventory="down"
    )
    projection = _noncanonical(
        gap_list=GAPS,
        macro={
            "confirmation": {**confirmation, "applicable": False},
            "price_consistency": PRICE_CONSISTENCY,
            "coverage": COVERAGE,
        },
    )
    board = _board(projection)
    section = " ".join(_text(_conclusion(projection)).split())

    assert "非典型组合" in section
    for value in ("+1.23 个百分点", "-0.50 个百分点", "40.0%", "3/7", "主动去库存"):
        assert value in section
    # Still read in percentage points, never pp.
    assert "pp" not in board
    assert "原因 非典型组合 ：债券牛市 · 股票熊市 · 商品牛市" in board


def test_the_data_boundary_opens_the_full_gap_list_in_the_drawer() -> None:
    projection = _noncanonical(gap_list=GAPS, macro={"coverage": COVERAGE})
    section = _conclusion(projection)

    triggers = _find(section, lambda item: str(getattr(item, "href", "")).startswith("#drawer-"))
    (gaps,) = [item for item in triggers if _words(item) == "2 项缺口"]
    drawer = _words(_by_id(section, str(getattr(gaps, "href", "")).removeprefix("#")))
    assert drawer.startswith("全部缺口（2）")
    assert "P1 CN_DR007" in drawer and "P2 UST10Y_NOMINAL_YIELD" in drawer
    assert "时效缺口（1）" in drawer and "缺失（1）" in drawer
    # The board keeps the one line and its way on to section 07 and the data chain.
    assert "数据边界 2 项缺口 · 5 个历史期未取到（最终计划，模型所需口径） · 详见" in _board(
        projection
    )


def test_no_gap_leaves_nothing_to_open() -> None:
    section = _conclusion(_noncanonical(macro={"coverage": COVERAGE}))

    assert "数据边界 0 项缺口 · 5 个历史期未取到" in _words(section)
    assert not _find(section, lambda item: "gaps" in str(getattr(item, "href", "")))


def test_the_day_summary_publishes_the_basis_the_board_reads(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    days = sessions()
    seed_independent_calendar(paths, days)
    # Bond and commodity rise while the stock core falls: bull · bear · bull.
    EvidenceRepository(paths.database).append_source_claims(
        tuple(
            claim(
                metric_id,
                observed,
                1000.0 - index if asset == "stock" else 100.0 + index,
                unit="index_points",
                provider="tushare",
                reference=f"tushare:{CORE_API_IDENTITIES[metric_id][0]}:"
                f"{CORE_API_IDENTITIES[metric_id][1]}:{observed}",
            )
            for index, observed in enumerate(days)
            for asset, metric_id in CORES.items()
        )
    )
    register_confirmation_model(paths)

    projection = publish(paths, MODEL)
    board = _board(projection)

    overview: dict[str, Any] = projection.datasets["cycle_overview"]
    assert overview["stage_reason"] == "noncanonical_combination"
    assert [
        (item["stage"], item["asset"]) for item in overview["noncanonical_basis"]["comparisons"]
    ] == [("stage_i", "commodity"), ("stage_iii", "stock"), ("stage_v", "bond")]
    assert (
        "只差一项 Stage I 差商品：当前牛市 → 要求熊市，30 日候选牛市 "
        "Stage III 差股票：当前熊市 → 要求牛市，30 日候选熊市 "
        "Stage V 差债券：当前牛市 → 要求熊市，30 日候选牛市"
    ) in board
    assert "非典型组合无阶段叙事可比对，不计数" in board
    assert "转折观察 无（三核心 30 日候选均未与当前状态反向）" in board
