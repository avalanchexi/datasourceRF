"""The 05 inventory section: one quadrant card, three line cards, warrants in a drawer (ticket 06).

Each case builds a small projection by hand and asserts what a reader sees on the page and
inside the drawers the section opens.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dash import html
from dash.development.base_component import Component

from pring_cycle.confirmation import OUTPUT_STRUCTURE
from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_overseas_cards import _by_id, _find, _words

LINES = {
    "demand": "需求：PMI 新订单",
    "production": "生产：工业增加值当月实际同比",
    "inventory": "库存：产成品存货名义同比",
}


def _member(
    label: str,
    metric_id: str,
    line: str,
    role: str,
    value: float,
    unit: str,
    direction: str,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "label": label,
        "metric_id": metric_id,
        "member": {"measure": "level"},
        "line": line,
        "role": role,
        "consistency": "main" if role == "line" else "agrees",
        "value": value,
        "unit": unit,
        "period": "2026-08-31",
        "direction": direction,
        "momentum": direction,
        "periods": ["2026-07-31", "2026-08-31"],
        "values": [value - 1, value],
        "observation_version_ids": [f"version-{metric_id}-{line}-{role}"],
        "latest_source": {
            "value": value,
            "unit": unit,
            "period": "2026-09-30",
            "selected_claim_id": f"claim-{metric_id}-{line}-{role}",
        },
        **fields,
    }


MEMBERS = [
    _member(
        LINES["demand"], "CN_PMI_ACTIVITY", "demand", "line", 50.6, "diffusion_index_points", "up"
    ),
    _member(
        "需求：工业企业营业收入累计同比（累计口径）",
        "CN_INDUSTRIAL_FINANCE",
        "demand",
        "auxiliary",
        6.6,
        "percent",
        "up",
    ),
    _member(LINES["production"], "CN_INDUSTRIAL_VA", "production", "line", 5.2, "percent", "up"),
    _member(
        "生产：PMI 生产",
        "CN_PMI_ACTIVITY",
        "production",
        "auxiliary",
        50.4,
        "diffusion_index_points",
        "up",
    ),
    _member(
        LINES["inventory"],
        "CN_FINISHED_GOODS_INVENTORY",
        "inventory",
        "line",
        11.0,
        "percent",
        "down",
    ),
    _member(
        "库存：PMI 产成品库存",
        "CN_PMI_INVENTORY",
        "inventory",
        "auxiliary",
        48.4,
        "diffusion_index_points",
        "down",
    ),
]


def _quadrant(
    quadrant: str = "active_destocking",
    unclassified_by: str | None = None,
    directions: tuple[str | None, str | None, str | None] = ("up", "up", "down"),
) -> dict[str, Any]:
    return {
        "name": "quadrant",
        "label": "库存象限",
        "metric_id": "CN_FINISHED_GOODS_INVENTORY",
        "role": "main",
        "period": "2026-08-31",
        "quadrant": quadrant,
        "unclassified_by": unclassified_by,
        "lines": {
            line: {"label": LINES[line], "period": "2026-08-31", "direction": direction}
            for line, direction in zip(LINES, directions, strict=True)
        },
    }


def _inventory_projection(
    quadrant: dict[str, Any] | None = None,
    *,
    members: list[dict[str, Any]] = MEMBERS,
    relation: str = "support",
    **inventory: Any,
) -> ProjectionSet:
    board = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        macro={
            "confirmation": {
                "dimensions": [
                    {
                        "dimension": "inventory",
                        "status": "connected",
                        "key_indicators": [
                            {
                                "key": "inventory_quadrant",
                                "name": "库存象限",
                                "metric_id": "CN_FINISHED_GOODS_INVENTORY",
                                "relation": relation,
                                "statistical_period": "2026-08-31",
                                "members": [quadrant or _quadrant(), *members],
                            }
                        ],
                    }
                ]
            }
        },
    )
    return replace(
        board,
        datasets={
            **board.datasets,
            "inventory": {
                "output_structure": OUTPUT_STRUCTURE,
                "status": "connected",
                "cards": [
                    {
                        "label": member["label"],
                        "line": member["line"],
                        "availability": "available",
                        "evidence_status": "current",
                        "relation": relation,
                        "consistency": member["consistency"],
                    }
                    for member in members
                ],
                **inventory,
            },
        },
    )


def _section(projection: ProjectionSet) -> Component:
    return _by_id(dashboard_page("/", projection, (), ()), "inventory")


def _is_panel(item: object) -> bool:
    return getattr(item, "role", None) == "dialog"


def _shown(component: object) -> str:
    """The section's words a reader sees before opening any drawer."""
    if isinstance(component, (list, tuple)):
        return " ".join(_shown(child) for child in component)
    if isinstance(component, str):
        return component
    if not isinstance(component, Component) or _is_panel(component):
        return ""
    return " ".join(_shown(getattr(component, "children", None)).split())


def _triggers(section: Component) -> list[Component]:
    return _find(section, lambda item: str(getattr(item, "href", "")).startswith("#drawer-"))


def _drawer(section: Component, trigger: Component) -> Component:
    return _by_id(section, str(getattr(trigger, "href", "")).removeprefix("#"))


def test_the_quadrant_card_comes_first_then_the_three_lines_side_by_side() -> None:
    section = _section(_inventory_projection())
    shown = _shown(section)

    assert (
        "库存象限 主动去库存 统计期 2026-08-31 需求上升、生产上升、库存下降 "
        "确认关系：支持（象限仅计一项）"
    ) in shown
    cards = [_words(card) for card in _triggers(section)[:3]]
    assert cards == [
        "需求 PMI 新订单 CN_PMI_ACTIVITY · level 50.60 扩散指数点 ↑ 上升 2026-08-31",
        "生产 工业增加值当月实际同比 CN_INDUSTRIAL_VA · level 5.20 % ↑ 上升 2026-08-31",
        "库存 产成品存货名义同比 CN_FINISHED_GOODS_INVENTORY · level 11.00 % ↓ 下降 2026-08-31",
    ]
    assert shown.index("库存象限") < shown.index("需求 PMI 新订单")


def test_each_member_shows_once_and_auxiliaries_wait_in_the_line_drawer() -> None:
    section = _section(_inventory_projection())
    shown = _shown(section)

    for name in ("PMI 新订单", "工业增加值当月实际同比", "产成品存货名义同比"):
        assert shown.count(name) == 1
    for auxiliary in ("营业收入", "PMI 生产", "PMI 产成品库存"):
        assert auxiliary not in shown
    assert "库存卡" not in shown

    demand = _drawer(section, _triggers(section)[0])
    words = _words(demand)
    assert words.startswith("需求线 关闭 PMI 新订单 CN_PMI_ACTIVITY · level")
    assert words.count("PMI 新订单") == 1
    assert words.count("工业企业营业收入累计同比（累计口径）") == 1
    assert words.index("PMI 新订单") < words.index("工业企业营业收入累计同比")
    assert (
        "角色 主线成员 读取值 / 期 50.60 扩散指数点 2026-08-31 "
        "来源最新 / 期 50.60 扩散指数点 2026-09-30 方向 ↑ 上升 主辅关系 主要成员 数据 可用"
    ) in words
    assert "角色 辅助成员 读取值 / 期 6.60 % 2026-08-31" in words
    assert "主辅关系 与主要成员一致" in words
    hrefs = [
        str(getattr(link, "href", ""))
        for link in _find(demand, lambda item: isinstance(item, html.A))
    ]
    assert any("claim-CN_PMI_ACTIVITY-demand-line" in href for href in hrefs)
    assert any("version-CN_INDUSTRIAL_FINANCE-demand-auxiliary" in href for href in hrefs)
    assert "生产" not in words.removeprefix("需求线")


def test_an_unclassified_quadrant_says_why_and_without_a_stage_is_not_counted() -> None:
    projection = _inventory_projection(
        _quadrant("unclassified", "insufficient", ("up", None, "up")), relation="not_applicable"
    )

    shown = _shown(_section(projection))

    assert (
        "库存象限 未分类 统计期 2026-08-31 "
        "未分类原因：三条线缺数或月份不齐；需求上升、生产方向未知、库存上升 "
        "确认关系：不适用（无正式阶段，不计数）"
    ) in shown


def _warrant(symbol: str, first: float, last: float, **fields: Any) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "first": first,
        "last": last,
        "unit": "tonne",
        "input_unit": "sheet",
        "factor": 40.0,
        "weight_basis": "公定重量（名义）",
        "change_rate": last / first - 1,
        "status": "read",
        "first_claim_ids": [f"claim-{symbol}-first"],
        "last_claim_ids": [f"claim-{symbol}-last"],
        **fields,
    }


WARRANTS = {
    "first_day": "2026-04-16",
    "last_day": "2026-10-14",
    "median_change_rate": 0.2,
    "breadth": {"increase": 2, "flat": 0, "decrease": 1, "read": 3, "symbols": 3},
    "tonnes": {"first": 900.0, "last": 1000.0},
    "missing": [],
    "symbols": [
        _warrant("CF", 400.0, 480.0),
        _warrant("TA", 500.0, 400.0),
        _warrant("SC", 100.0, 120.0, unit="barrel", input_unit="barrel", factor=1.0),
    ],
}
APPROXIMATION = {
    "status": "available",
    "formula_version": "inventory-ppi-common-month-v0002",
    "value": 70905.58766859345,
    "derived_observation_id": "derived-real-inventory",
    "nominal_inventory": {
        "value": 73600.0,
        "unit": "hundred_million_cny",
        "period": "2026-08-31",
        "selected_claim_id": "claim-nominal-inventory",
    },
    "ppi_input": {
        "value": 3.8,
        "unit": "percent",
        "period": "2026-08-31",
        "selected_claim_id": "claim-ppi",
    },
    "counted": False,
}


def test_warrants_take_one_line_and_their_table_waits_in_a_drawer_in_chinese() -> None:
    section = _section(
        _inventory_projection(
            registered_warrants=WARRANTS, real_inventory_approximation=APPROXIMATION
        )
    )
    shown = _shown(section)
    (trigger,) = [item for item in _triggers(section) if "仓单" in _words(item)]
    drawer = _drawer(section, trigger)
    words = _words(drawer)

    assert "注册仓单（附注，不计数） 3 个品种 · 最新期 2026-10-14" in shown
    assert _words(trigger) == "分品种仓单与实际库存近似 →"
    assert "棉花" not in shown and "实际库存近似（" not in shown
    assert words.startswith("注册仓单与实际库存近似 关闭")
    rows = _find(_find(drawer, lambda item: isinstance(item, html.Table))[0], _is_row)[1:]
    assert [_words(row) for row in rows] == [
        "棉花 400 → 480 吨 +20.0% 每张 40 吨（公定重量（名义））",
        "PTA 500 → 400 吨 -20.0% 每张 40 吨（公定重量（名义））",
        "原油 100 → 120 桶 +20.0% 每桶 1 桶（公定重量（名义））",
    ]
    assert [str(getattr(_find(row, _titled)[0], "title", "")) for row in rows] == [
        "CN_FUTURES_WARRANTS · CF",
        "CN_FUTURES_WARRANTS · TA",
        "CN_FUTURES_WARRANTS · SC",
    ]
    assert "变化率中位数 20.0%" in words
    assert "棉花（CF） 起点 1 终点 1" in words
    assert (
        "实际库存近似（粗略价格调整代理） 值 70,905.59 亿元 统计期 2026-08-31 "
        "算法 名义产成品存货 ÷（1 + PPI 同比 ÷ 100） "
        "名义产成品存货 73,600.00 亿元 PPI 同比 3.80 % "
        "公式版本 inventory-ppi-common-month-v0002 派生证据 derived-real-inventory "
        "计数 不计数，不参与库存象限"
    ) in words
    assert "注册仓单不代表产业总库存" in words
    hrefs = [
        str(getattr(link, "href", ""))
        for link in _find(drawer, lambda item: isinstance(item, html.A))
    ]
    for claim in ("claim-CF-first", "claim-SC-last", "claim-nominal-inventory", "claim-ppi"):
        assert any(claim in href for href in hrefs)


def _is_row(item: object) -> bool:
    return isinstance(item, html.Tr)


def _titled(item: object) -> bool:
    return bool(getattr(item, "title", None))


def test_without_warrants_the_line_says_so_and_the_drawer_still_holds_the_approximation() -> None:
    section = _section(_inventory_projection(real_inventory_approximation=APPROXIMATION))
    shown = _shown(section)
    (trigger,) = [item for item in _triggers(section) if "仓单" in _words(item)]

    assert "注册仓单（附注，不计数） 本投影未提供分品种仓单变化" in shown
    assert "值 70,905.59 亿元" in _words(_drawer(section, trigger))
