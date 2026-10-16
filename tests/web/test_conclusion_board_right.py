"""The 01 conclusion board's right column: the confirmation heading, the five dimension
cells and the four inline rows a reader sets against the stage (ticket 04).

Each case builds a small projection by hand and asserts the reader-visible sentence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.integration.test_confirmation_publish import confirmed
from tests.web.test_conclusion_board import _asset, _board, _conclusion, _projection
from tests.web.test_dashboard_contract import _hrefs, _text

DIMENSIONS = ("policy", "credit", "overheat", "price", "inventory")


def _dimension(dimension: str, relations: list[str]) -> dict[str, Any]:
    if not relations:
        return {"dimension": dimension, "status": "not_connected", "counts": None}
    return {
        "dimension": dimension,
        "status": "connected",
        "counts": {
            relation: relations.count(relation)
            for relation in (
                "support",
                "counterevidence",
                "observation_only",
                "unconfirmed",
                "not_applicable",
            )
        },
        "key_indicators": [{"relation": relation} for relation in relations],
    }


def _confirmation(applicable: bool) -> dict[str, Any]:
    if applicable:
        relations = {
            "policy": ["support", "support", "unconfirmed"],
            "credit": ["counterevidence", "observation_only"],
            "overheat": ["support"],
            "price": ["unconfirmed", "counterevidence"],
            "inventory": [],
        }
    else:
        relations = {
            "policy": ["not_applicable"] * 3,
            "credit": ["not_applicable"] * 2,
            "overheat": ["not_applicable"],
            "price": ["not_applicable"] * 2,
            "inventory": [],
        }
    return {
        "macro_rules_version": "macro-confirmation-v0001",
        "stage": "stage_ii" if applicable else None,
        "applicable": applicable,
        "dimensions": [_dimension(key, relations[key]) for key in DIMENSIONS],
        "summary": {
            "counting_unit": "key_indicator",
            "applicable": applicable,
            "total": 8,
            "counts": {"support": 3, "counterevidence": 2, "observation_only": 1, "unconfirmed": 2}
            if applicable
            else None,
        },
    }


def _titles(component: object) -> list[str]:
    """The hover texts under a component, as a reader sees them on pointing."""
    if isinstance(component, (list, tuple)):
        return [title for child in component for title in _titles(child)]
    if not isinstance(component, Component):
        return []
    title = getattr(component, "title", None)
    return ([title] if isinstance(title, str) else []) + _titles(
        getattr(component, "children", None)
    )


def _typical(**macro: Any) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
        current_stage="stage_ii",
        last_confirmed_stage="stage_ii",
        stage_reason="canonical_combination",
        macro={"confirmation": _confirmation(True), **macro},
    )


def _noncanonical(**macro: Any) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        stage_reason="noncanonical_combination",
        macro={"confirmation": _confirmation(False), **macro},
    )


def test_the_confirmation_heading_and_cells_count_key_indicators_for_a_typical_stage() -> None:
    board = _board(_typical())

    assert "确认度 可评估 · 8 项关键指标 · 规则 macro-confirmation-v0001" in board
    assert "政策 3 项 支 2 · 反 0 · 观 0 · 未 1" in board
    assert "信用 2 项 支 0 · 反 1 · 观 1 · 未 0" in board
    assert "过热 1 项 支 1 · 反 0 · 观 0 · 未 0" in board
    assert "物价 2 项 支 0 · 反 1 · 观 0 · 未 1" in board
    assert "库存 尚未接入" in board
    assert "不适用" not in board
    # The abbreviated counts keep their full names on hover.
    assert "支持 2 · 反证 0 · 仅观察 0 · 未确认 1" in _titles(_conclusion(_typical()))
    cells = ["政策 3 项", "信用 2 项", "过热 1 项", "物价 2 项", "库存 尚未接入"]
    assert [board.index(cell) for cell in cells] == sorted(board.index(cell) for cell in cells)


def test_a_noncanonical_combination_collapses_the_five_cells_into_one_uncounted_line() -> None:
    board = _board(_noncanonical())

    assert (
        "确认度 不适用 · 8 项关键指标 · 无正式阶段，不计数 · 规则 macro-confirmation-v0001"
    ) in board
    assert (
        "政策 3 项 · 信用 2 项 · 过热 1 项 · 物价 2 项 · 库存 尚未接入 · "
        "非典型组合无阶段叙事可比对，不计数"
    ) in board
    assert board.count("不适用") == 1
    assert "支 0" not in board and "支持 0" not in board


def test_a_day_held_for_core_data_keeps_the_five_cells_marked_not_applicable() -> None:
    board = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", None)],
            stage_reason="core_data_pending",
            macro={"confirmation": _confirmation(False)},
        )
    )

    assert "政策 3 项 · 不适用 支 0 · 反 0 · 观 0 · 未 0" in board
    assert "非典型组合无阶段叙事可比对" not in board


PRICE_CONSISTENCY = {
    "sessions": 120,
    "first_session": "2026-04-09",
    "last_session": "2026-09-30",
    "relative_momentum": [
        {"label": "商品对债", "value_pp": 1.234, "direction": "up"},
        {"label": "股票对债", "value_pp": -0.5, "direction": "down"},
        {"label": "股票对商品", "value_pp": None, "missing": ["CN_EQUITY_CORE_000985"]},
    ],
    "stock_breadth": {
        "label": "股市广度（站上 90 日均线个股占比）",
        "share": 40.029,
        "line": 50,
        "text": "上涨集中于较少个股",
    },
    "basket_breadth": {
        "label": "商品篮子分项广度",
        "along": 3,
        "of": 7,
        "text": "上涨集中于少数分项",
    },
    "position": {"applicable": False},
}


def test_the_price_consistency_row_inlines_momentum_and_both_breadths() -> None:
    board = _board(_typical(price_consistency=PRICE_CONSISTENCY))
    unconfirmed = _board(
        _typical(
            price_consistency={
                **PRICE_CONSISTENCY,
                "stock_breadth": {
                    "label": "股市广度（站上 90 日均线个股占比）",
                    "share": None,
                    "text": None,
                    "missing": ["CN_EQ_ABOVE_MA90"],
                },
            }
        )
    )

    assert (
        "价格一致性 商品对债 +1.23 个百分点 · 股票对债 -0.50 个百分点 · 股票对商品 未确认；"
        "股市广度（站上 90 日均线个股占比） 40.0% （上涨集中于较少个股）；"
        "商品篮子分项广度 3/7 个分项同向（上涨集中于少数分项）"
    ) in board
    assert "股市广度（站上 90 日均线个股占比） 未确认，缺：CN_EQ_ABOVE_MA90" in unconfirmed
    assert "价格一致性 该版本未提供" in _board(_typical())


def _inventory(
    quadrant: str, unclassified_by: str | None, **directions: str | None
) -> dict[str, Any]:
    confirmation = _confirmation(True)
    confirmation["dimensions"][-1] = {
        "dimension": "inventory",
        "status": "connected",
        "counts": {"support": 1},
        "key_indicators": [
            {
                "relation": "support",
                "statistical_period": "2026-08",
                "members": [
                    {
                        "name": "quadrant",
                        "period": "2026-08",
                        "quadrant": quadrant,
                        "unclassified_by": unclassified_by,
                        "lines": {
                            line: {"period": "2026-08", "direction": direction}
                            for line, direction in directions.items()
                        },
                    }
                ],
            }
        ],
    }
    return confirmation


def test_the_inventory_row_states_the_quadrant_its_period_and_three_lines() -> None:
    classified = _board(
        _typical(
            confirmation=_inventory(
                "active_destocking", None, demand="down", production="down", inventory="down"
            )
        )
    )
    unclassified = _board(
        _typical(
            confirmation=_inventory(
                "unclassified", "insufficient", demand="up", production=None, inventory="up"
            )
        )
    )

    assert "库存象限 主动去库存 （统计期 2026-08；需求下降、生产下降、库存下降）" in classified
    assert (
        "库存象限 未分类 （统计期 2026-08；未分类原因：三条线缺数或月份不齐；"
        "需求上升、生产方向未知、库存上升）"
    ) in unclassified
    assert "库存象限 该版本未提供" in _board(_typical())
    assert classified.index("价格一致性 ") < classified.index("库存象限 ")


def test_the_bond_attribution_row_names_the_driver_and_axes_as_an_uncounted_note() -> None:
    board = _board(
        _typical(
            bond_attribution={
                "label": "债券归因",
                "bond_text": "债券价格上行",
                "axes": [
                    {"label": "政策维度", "text": "宽松", "signals": []},
                    {"label": "基本面维度", "text": "走弱", "signals": []},
                ],
                "text": "基本面加宽松推动",
                "notes": ["期限溢价归因未确认"],
            }
        )
    )

    assert "债券归因 基本面加宽松推动：政策维度宽松、基本面维度走弱（附注，不计数）" in board
    assert "债券归因 该版本未提供" in _board(_typical())
    assert board.index("库存象限 ") < board.index("债券归因 ")


GAPS = [
    {"metric_id": "CN_DR007", "priority": "P1", "category": "freshness_gap"},
    {"metric_id": "UST10Y_NOMINAL_YIELD", "priority": "P2", "category": "missing"},
]
COVERAGE = {
    "available": True,
    "model": {"total": 40, "counts": {"held": 33, "release_gated": 2, "missing": 5}},
    "catalog": {"total": 60, "counts": {"held": 49, "release_gated": 2, "missing": 9}},
}


def _bounded(coverage: dict[str, Any] | None) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        stage_reason="noncanonical_combination",
        gap_list=GAPS,
        macro={"confirmation": _confirmation(False)}
        | ({"coverage": coverage} if coverage is not None else {}),
    )


def test_the_data_boundary_row_counts_gaps_and_missing_plan_periods_and_links_onward() -> None:
    projection = _bounded(COVERAGE)
    board = _board(projection)
    links = _hrefs(_conclusion(projection))

    assert (
        "数据边界 2 项缺口 · 5 个历史期未取到（最终计划，模型所需口径） · "
        "详见 ⑦ 数据说明 · 数据链路"
    ) in board
    assert "?projection=projection-board#reading" in links
    assert "/data-chain?projection=projection-board" in links
    assert board.index("债券归因 ") < board.index("数据边界 ")


def test_the_data_boundary_row_says_the_version_lacks_a_coverage_summary() -> None:
    for coverage in (None, {"available": False}):
        board = _board(_bounded(coverage))

        assert (
            "数据边界 2 项缺口 · 历史期未取到：该版本未提供 · 详见 ⑦ 数据说明 · 数据链路"
        ) in board


def test_the_board_drops_its_folded_blocks_while_the_details_stay_in_later_sections() -> None:
    projection = _typical(
        price_consistency=PRICE_CONSISTENCY,
        bond_attribution={
            "label": "债券归因",
            "bond_text": "债券价格上行",
            "axes": [{"label": "政策维度", "text": "宽松", "signals": []}],
            "text": "政策或流动性推动",
            "notes": [],
            "boundary": "债券状态旁的解释附注",
        },
    )
    board = _board(projection)
    page = " ".join(_text(dashboard_page("/", projection, (), ())).split())

    for folded in ("价格内部一致性", "逐项确认关系", "库存象限：", "五维确认度"):
        assert folded not in board
    assert "价格内部一致性（不计数）" in page
    assert "债券归因（不计数）" in page
    assert "完整度与缺期" in page


def test_the_right_column_reads_the_confirmation_the_day_summary_publishes(
    tmp_path: Path,
) -> None:
    board = _board(confirmed(tmp_path))

    assert "确认度 可评估 · 17 项关键指标 · 规则 macro-confirmation-v0001" in board
    # The PMI supports; the other four overheat indicators, held nowhere, are unconfirmed.
    assert "过热 5 项 支 1 · 反 0 · 观 0 · 未 4" in board
    assert "库存象限 未分类 （统计期 未提供；未分类原因：三条线缺数或月份不齐" in board
    assert "债券归因 推动力不明" in board
    assert "数据边界 0 项缺口 · 历史期未取到：该版本未提供" in board
    rows = ("确认度 ", "价格一致性 ", "库存象限 ", "债券归因 ", "数据边界 ")
    assert [board.index(row) for row in rows] == sorted(board.index(row) for row in rows)


def test_an_empty_runtime_right_column_waits_for_the_first_run() -> None:
    board = _board(None)

    assert "确认度 等待首次完整运行" in board
    assert "该版本未提供" not in board
