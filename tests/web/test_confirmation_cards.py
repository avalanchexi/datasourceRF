"""The 04 confirmation section as five dimension cards, one row per key indicator, each row
opening the shared right drawer (ticket 05).

Each case builds a small projection by hand and asserts what a reader sees on the cards and
inside the drawer a row opens.
"""

from __future__ import annotations

from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_dashboard_contract import _hrefs
from tests.web.test_overseas_cards import _by_id, _drawer, _find, _words

RELATIONS = ("support", "counterevidence", "observation_only", "unconfirmed", "not_applicable")


def _member(label: str, **fields: Any) -> dict[str, Any]:
    return {
        "label": label,
        "role": "main",
        "consistency": "main",
        "value": None,
        "unit": None,
        "period": None,
        "direction": None,
        "latest_source": None,
        **fields,
    }


def _indicator(
    key: str, name: str, metric_id: str, relation: str, members: list[dict[str, Any]], **fields: Any
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "metric_id": metric_id,
        "relation": relation,
        "statistical_period": members[0].get("period") if members else None,
        "consistency": "consistent",
        "members": members,
        **fields,
    }


def _dimension(dimension: str, indicators: list[dict[str, Any]]) -> dict[str, Any]:
    relations = [str(item["relation"]) for item in indicators]
    return {
        "dimension": dimension,
        "status": "connected",
        "counts": {relation: relations.count(relation) for relation in RELATIONS},
        "key_indicators": indicators,
    }


def _typical_indicators() -> dict[str, list[dict[str, Any]]]:
    return {
        "policy": [
            _indicator(
                "policy_rate",
                "政策利率",
                "CN_OMO_7D_RATE",
                "support",
                [_member("七天逆回购利率", value=1.4, unit="percent", period="2026-10-14")],
            ),
            _indicator(
                "lpr",
                "LPR",
                "CN_LPR_1Y_5Y",
                "unconfirmed",
                [_member("1 年期 LPR", value=3.0, unit="percent", period="2026-09-20")],
            ),
        ],
        "credit": [
            _indicator(
                "social_financing",
                "社融",
                "CN_SF_TOTAL",
                "counterevidence",
                [_member("存量同比", value=7.2, unit="percent", period="2026-08-31")],
            )
        ],
        "overheat": [
            _indicator(
                "gdp",
                "GDP",
                "CN_GDP",
                "observation_only",
                [_member("实际季度同比", value=4.3, unit="percent", period="2026-06-30")],
            )
        ],
        "price": [
            _indicator(
                "cpi",
                "CPI",
                "CN_CPI_HEADLINE",
                "support",
                [_member("CPI 同比", value=0.9, unit="percent", period="2026-09-30")],
            )
        ],
        "inventory": [],
    }


def _confirmation(
    indicators: dict[str, list[dict[str, Any]]], *, applicable: bool
) -> dict[str, Any]:
    return {
        "macro_rules_version": "macro-confirmation-v0001",
        "stage": "stage_ii" if applicable else None,
        "applicable": applicable,
        "dimensions": [
            _dimension(dimension, items)
            if items
            else {"dimension": dimension, "status": "not_connected", "counts": None}
            for dimension, items in indicators.items()
        ],
        "summary": {
            "applicable": applicable,
            "counting_unit": "key_indicator",
            "total": sum(len(items) for items in indicators.values()),
        },
    }


def _typical(**macro: Any) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
        current_stage="stage_ii",
        last_confirmed_stage="stage_ii",
        stage_reason="canonical_combination",
        macro={"confirmation": _confirmation(_typical_indicators(), applicable=True), **macro},
    )


def _section(projection: ProjectionSet) -> Component:
    return _by_id(dashboard_page("/", projection, (), ()), "confirmation")


def _cards(projection: ProjectionSet) -> list[str]:
    """Each dimension card's words, in page order."""
    return [
        _words(card)
        for card in _find(
            _section(projection),
            lambda item: "dimension-card" in str(getattr(item, "className", "")),
        )
    ]


def _rows(projection: ProjectionSet) -> list[Component]:
    """The drawer triggers of section 04, in page order."""
    return _find(
        _section(projection), lambda item: str(getattr(item, "href", "")).startswith("#drawer-")
    )


def test_each_dimension_card_heads_with_its_name_and_full_relation_counts() -> None:
    cards = _cards(_typical())

    assert [card.split(" ")[0] for card in cards] == ["政策", "信用", "过热", "物价", "库存"]
    assert cards[0].startswith("政策 支持 1 · 反证 0 · 仅观察 0 · 未确认 1")
    assert cards[1].startswith("信用 支持 0 · 反证 1 · 仅观察 0 · 未确认 0")
    assert cards[4] == "库存 尚未接入"


def test_with_a_formal_stage_each_row_reads_name_relation_and_period() -> None:
    rows = [_words(row) for row in _rows(_typical())]

    assert rows == [
        "政策利率 支持 读取期 2026-10-14",
        "LPR 未确认 读取期 2026-09-20",
        "社融 反证 读取期 2026-08-31",
        "GDP 仅观察 读取期 2026-06-30",
        "CPI 支持 读取期 2026-09-30",
    ]


def _noncanonical_indicators() -> dict[str, list[dict[str, Any]]]:
    return {
        "policy": [
            _indicator(
                "policy_rate",
                "政策利率",
                "CN_OMO_7D_RATE",
                "not_applicable",
                [
                    _member(
                        "七天逆回购利率",
                        value=1.4,
                        unit="percent",
                        period="2026-10-14",
                        direction="flat",
                    )
                ],
            ),
        ],
        "credit": [
            _indicator(
                "loans",
                "贷款",
                "CN_LOAN_STRUCTURE",
                "not_applicable",
                [
                    _member(
                        "企业中长期贷款当月增量（较去年同月）",
                        value=-1500.0,
                        unit="hundred_million_cny",
                        period="2026-08-31",
                        direction="down",
                    ),
                    _member("住户贷款当月增量（较去年同月）", role="auxiliary", value=12.0),
                ],
            )
        ],
        "overheat": [
            _indicator(
                "capacity",
                "产能利用率",
                "CN_CAPACITY_UTILIZATION",
                "not_applicable",
                [
                    _member(
                        "全工业产能利用率",
                        value=73.0,
                        period="2026-06-30",
                        direction="down",
                        latest_source={"value": 73.0, "unit": "percent", "period": "2026-06-30"},
                    )
                ],
            )
        ],
        "price": [],
        "inventory": [
            _indicator(
                "inventory_quadrant",
                "库存象限",
                "CN_FINISHED_GOODS_INVENTORY",
                "not_applicable",
                [
                    _member(
                        "库存象限",
                        period="2026-08-31",
                        quadrant="active_restocking",
                        latest_source={
                            "value": 73600.0,
                            "unit": "hundred_million_cny",
                            "period": "2026-08-31",
                        },
                    )
                ],
            )
        ],
    }


def _noncanonical(**macro: Any) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        stage_reason="noncanonical_combination",
        macro={
            "confirmation": _confirmation(_noncanonical_indicators(), applicable=False),
            **macro,
        },
    )


def test_a_noncanonical_row_reads_its_main_member_and_is_not_counted() -> None:
    projection = _noncanonical()
    rows = [_words(row) for row in _rows(projection)]

    assert rows == [
        "政策利率 七天逆回购利率 1.40 % 2026-10-14 → 持平 不计数",
        "贷款 企业中长期贷款当月增量（较去年同月） -1,500.00 亿元 2026-08-31 ↓ 下降 不计数",
        "产能利用率 全工业产能利用率 73.00 % 2026-06-30 ↓ 下降 不计数",
        "库存象限 73,600.00 亿元 2026-08-31 主动补库存 不计数",
    ]
    cards = _cards(projection)
    assert cards[0].startswith("政策 支持 0 · 反证 0 · 仅观察 0 · 未确认 0 · 不计数 1 ")
    assert "不适用" not in " ".join(cards)


def test_a_noncanonical_drawer_says_why_proposition_and_maturity_are_empty() -> None:
    projection = _noncanonical()
    page = dashboard_page("/", projection, (), ())
    drawers = [_words(_drawer(page, row)) for row in _rows(projection)]

    typical = _typical()
    typical_page = dashboard_page("/", typical, (), ())

    assert len(drawers) == 4
    assert all("非典型组合不判定命题与成熟度" in drawer for drawer in drawers)
    assert "非典型组合不判定命题与成熟度" not in " ".join(
        _words(_drawer(typical_page, row)) for row in _rows(typical)
    )


def test_a_drawer_without_a_formal_stage_for_another_reason_does_not_say_noncanonical() -> None:
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "unknown"), _asset("commodity", "bear")],
        stage_reason="insufficient_core_evidence",
        macro={"confirmation": _confirmation(_noncanonical_indicators(), applicable=False)},
    )
    page = dashboard_page("/", projection, (), ())
    drawers = [_words(_drawer(page, row)) for row in _rows(projection)]

    assert len(drawers) == 4
    assert all("无正式阶段，不判定命题与成熟度" in drawer for drawer in drawers)
    assert not any("非典型组合" in drawer for drawer in drawers)


def test_a_row_opens_a_drawer_with_members_derivation_basis_gaps_and_proposition() -> None:
    m1_m2 = _indicator(
        "m1_m2",
        "M1/M2",
        "CN_M1_M2",
        "support",
        [
            _member(
                "M1 同比",
                value=3.2,
                unit="percent",
                period="2026-09-30",
                direction="down",
                observation_version_ids=["version-m1"],
            ),
            _member(
                "M2 同比",
                role="auxiliary",
                consistency="agrees",
                value=8.4,
                unit="percent",
                period="2026-09-30",
            ),
        ],
        derived=[
            {
                "label": "M1−M2",
                "formula_version": "m1-m2-yoy-spread-v0001",
                "period": "2026-09-30",
                "value": -5.2,
            }
        ],
        missing=["M0 同比"],
        proposition="货币扩张",
        turn={"maturity": "forming", "basis": "leading"},
    )
    indicators = {**_typical_indicators(), "credit": [m1_m2]}
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
        current_stage="stage_ii",
        stage_reason="canonical_combination",
        macro={"confirmation": _confirmation(indicators, applicable=True)},
    )
    page = dashboard_page("/", projection, (), ())
    (row,) = [row for row in _rows(projection) if _words(row).startswith("M1/M2")]

    drawer = _drawer(page, row)
    text = _words(drawer)

    assert text.startswith("M1/M2 CN_M1_M2 关闭")
    assert text.index("主辅成员") < text.index("M1 同比") < text.index("M2 同比")
    for field in (
        "主要成员",
        "辅助成员",
        "M1−M2（派生，不计数，m1-m2-yoy-spread-v0001）：2026-09-30 值 -5.2",
        "缺：M0 同比",
        "命题：货币扩张",
        "转折观察：成形",
    ):
        assert field in text, field
    assert (
        "/data-chain?projection=projection-board&version=version-m1&return=confirmation#evidence"
        in _hrefs(drawer)
    )


def _gdp_row(aggregate: str, measure: str, value: float) -> dict[str, Any]:
    return {
        "metric_id": "CN_GDP",
        "name_cn": "CN_GDP",
        "dimensions": {"aggregate": aggregate, "measure": measure},
        "value": value,
        "unit": "percent" if measure == "real_quarter_yoy" else "hundred_million_cny",
        "period": "2026-06-30",
        "selected_claim_id": f"claim-{aggregate}-{measure}",
    }


def test_the_gdp_drawer_tabulates_the_sectors_from_the_projection_rows() -> None:
    rows = [
        _gdp_row("primary", "nominal_ytd_level", 31521.8),
        _gdp_row("primary", "real_quarter_yoy", 3.7),
        _gdp_row("secondary", "nominal_ytd_level", 250472.9),
        _gdp_row("secondary", "real_quarter_yoy", 3.0),
        _gdp_row("tertiary", "real_quarter_yoy", 5.1),
        _gdp_row("total", "nominal_ytd_level", 695704.0),
        _gdp_row("total", "real_quarter_yoy", 4.3),
    ]
    projection = _typical(international_context=rows)
    page = dashboard_page("/", projection, (), ())
    gdp, *others = sorted(_rows(projection), key=lambda row: not _words(row).startswith("GDP"))

    text = _words(_drawer(page, gdp))
    table = text[text.index("分产业") :]

    assert table.startswith(
        "分产业 口径 实际季度同比 名义累计值 "
        "GDP 总量 4.30 % 2026-06-30 695,704.00 亿元 2026-06-30 "
        "第一产业 3.70 % 2026-06-30 31,521.80 亿元 2026-06-30 "
        "第二产业 3.00 % 2026-06-30 250,472.90 亿元 2026-06-30 "
        "第三产业 5.10 % 2026-06-30 未提供"
    )
    assert (
        "/data-chain?projection=projection-board&version=claim-total-real_quarter_yoy"
        "&return=confirmation#evidence" in _hrefs(_drawer(page, gdp))
    )
    assert all("分产业" not in _words(_drawer(page, row)) for row in others)
