"""The 03 overseas section as a grid of cards, each opening the shared right drawer (ticket 01).

Each case builds a small projection by hand and asserts what a reader sees on the card and
inside the drawer the card opens.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_dashboard_contract import _hrefs, _text


def _row(metric_id: str, value: float, unit: str, **fields: Any) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "name_cn": metric_id,
        "dimensions": {},
        "value": value,
        "unit": unit,
        "period": "2026-10-14",
        "frequency": "daily",
        "direction": "up",
        "status": "current",
        "acquisition_status": "succeeded",
        "selected_claim_id": f"claim-{metric_id}",
        "source_reference": f"tushare:{metric_id}:2026-10-14",
        **fields,
    }


def _overseas_projection(rows: list[dict[str, Any]]) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        macro={"international_context": rows},
    )


def _find(component: object, predicate: Any) -> list[Component]:
    if isinstance(component, (list, tuple)):
        return [found for child in component for found in _find(child, predicate)]
    if not isinstance(component, Component):
        return []
    here = [component] if predicate(component) else []
    return here + _find(getattr(component, "children", None), predicate)


def _by_id(component: object, identity: str) -> Component:
    (found,) = _find(component, lambda item: getattr(item, "id", None) == identity)
    return found


def _words(component: object) -> str:
    return " ".join(_text(component).split())


def _cards(projection: ProjectionSet) -> list[Component]:
    """The drawer triggers of section 03, in page order."""
    section = _by_id(dashboard_page("/", projection, (), ()), "overseas")
    return _find(section, lambda item: str(getattr(item, "href", "")).startswith("#drawer-"))


def test_overseas_cards_follow_the_page_list_order_and_show_only_the_core_reading() -> None:
    rows = [
        _row("EIA_WTI_RWTC", 61.2, "usd_per_barrel", direction="down"),
        _row(
            "UST10Y_NOMINAL_YIELD",
            5.19,
            "percent",
            direction="down",
            display={
                "change_5": {
                    "value": -8.0,
                    "unit": "basis_points",
                    "start_date": "2026-10-06",
                    "end_date": "2026-10-14",
                },
            },
        ),
        _row("CN_USDCNY_CENTRAL_PARITY", 7.1, "cny_per_usd", period="2026-10-15"),
    ]

    cards = [_words(card) for card in _cards(_overseas_projection(rows))]

    assert cards == [
        "美元兑人民币中间价 CN_USDCNY_CENTRAL_PARITY 7.10 元/美元 2026-10-15 ↑ 上升 近 5 日 —",
        "美国 10 年期国债收益率 UST10Y_NOMINAL_YIELD 5.19 % 2026-10-14 ↓ 下降 近 5 日 -8.00 基点",
        "WTI 原油 EIA_WTI_RWTC 61.20 美元/桶 2026-10-14 ↓ 下降 近 5 日 —",
    ]


def test_cny030_and_gdp_stay_out_while_unlisted_rows_go_to_other_background_metrics() -> None:
    rows = [
        _row("CN_BOND_FULL_PRICE_CNY030", 121.4, "index_points"),
        _row("CN_GDP", 4.3, "percent", dimensions={"aggregate": "total"}),
        _row("CN_GDP", 3.7, "percent", dimensions={"aggregate": "primary"}),
        _row("JP_10Y_YIELD", 1.62, "percent", period="2026-10-13"),
        _row("UST10Y_NOMINAL_YIELD", 5.19, "percent"),
    ]
    projection = _overseas_projection(rows)

    section = _words(_by_id(dashboard_page("/", projection, (), ()), "overseas"))
    cards = [_words(card) for card in _cards(projection)]

    assert "CN_BOND_FULL_PRICE_CNY030" not in section
    assert "CN_GDP" not in section
    assert len(cards) == 2
    assert cards[0].startswith("美国 10 年期国债收益率 UST10Y_NOMINAL_YIELD")
    assert section.index("UST10Y_NOMINAL_YIELD") < section.index("其他背景指标")
    assert section.index("其他背景指标") < section.index("JP_10Y_YIELD")
    assert cards[1] == "JP_10Y_YIELD 1.62 % 2026-10-13 ↑ 上升 近 5 日 —"


def test_without_unlisted_rows_there_is_no_other_background_card() -> None:
    projection = _overseas_projection([_row("CBOE_VIX_INDEX", 16.4, "index_points")])

    assert "其他背景指标" not in _words(_by_id(dashboard_page("/", projection, (), ()), "overseas"))


def _href(card: Component) -> str:
    return str(getattr(card, "href", ""))


def _drawer(page: object, card: Component) -> Component:
    """The panel a card opens: the page element whose id is the card's fragment."""
    return _by_id(page, _href(card).removeprefix("#"))


UST10Y = _row(
    "UST10Y_NOMINAL_YIELD",
    5.19,
    "percent",
    name_cn="美国 10 年期国债收益率",
    direction="down",
    direction_input_observation_version_ids=["claim-1013"],
    source_reference="https://home.treasury.gov/yield#sha256=abc",
    acquisition_status="verified_candidate",
    observation_id="observation-ust10y",
    display={
        "change_5": {
            "value": -8.0,
            "unit": "basis_points",
            "start_date": "2026-10-06",
            "end_date": "2026-10-14",
        },
        "change_120": {
            "value": 89.0,
            "unit": "basis_points",
            "start_date": "2026-04-22",
            "end_date": "2026-10-14",
        },
        "points": [
            {"date": "2026-10-13", "value": 5.21, "selected_claim_id": "claim-1013"},
            {"date": "2026-10-14", "value": 5.19, "selected_claim_id": "claim-UST10Y"},
        ],
    },
)


def test_a_card_opens_a_drawer_listing_every_field_of_its_row() -> None:
    projection = _overseas_projection([UST10Y])
    page = dashboard_page("/", projection, (), ())
    (card,) = _cards(projection)

    drawer = _drawer(page, card)
    text = _words(drawer)

    assert text.startswith("美国 10 年期国债收益率 UST10Y_NOMINAL_YIELD 关闭")
    for field in (
        "最新值 5.19 %",
        "统计期 / 频率 2026-10-14 / 日频",
        "较上期方向 ↓ 下降（2026-10-13 → 2026-10-14）",
        "近 5 日 -8.00 基点（2026-10-06 → 2026-10-14）",
        "近 120 日 89.00 基点（2026-04-22 → 2026-10-14）",
        "时效 当前有效",
        "最近获取 已取得候选数据",
        "采用来源 https://home.treasury.gov/yield",
        "证据 查看固定版本证据 → 观测 observation-ust10y",
        "走势与比较端点",
        "5 日：2026-10-06 → 2026-10-14；实际端点",
        "2026-10-13 5.21 %",
    ):
        assert field in text, field
    links = _hrefs(drawer)
    assert "https://home.treasury.gov/yield" in links
    assert (
        "/data-chain?projection=projection-board&version=claim-UST10Y&return=overseas#evidence"
        in links
    )
    assert (
        "/data-chain?projection=projection-board&version=claim-1013&return=overseas#evidence"
        in links
    )


def test_a_card_says_its_direction_is_against_the_previous_period_and_names_both_dates() -> None:
    (card,) = _cards(_overseas_projection([UST10Y]))
    (direction,) = _find(card, lambda item: getattr(item, "children", None) == "较上期 ↓ 下降")

    assert _words(card) == (
        "美国 10 年期国债收益率 UST10Y_NOMINAL_YIELD 5.19 % 2026-10-14 "
        "较上期 ↓ 下降 近 5 日 -8.00 基点"
    )
    assert direction.title == "较上期：2026-10-13 → 2026-10-14（非近 5 日）"


def test_the_treasury_spread_reads_its_sign_as_positive_or_inverted_never_as_rising() -> None:
    # The derived spread's projected direction is the sign of its value, not a comparison.
    rows = [
        _row("UST_2S10S_SPREAD", 35.0, "basis_points", direction="up"),
        _row("UST_2S10S_SPREAD", -12.0, "basis_points", direction="down", period="2026-10-13"),
    ]
    projection = _overseas_projection(rows)
    page = dashboard_page("/", projection, (), ())
    positive, inverted = _cards(projection)

    assert _words(positive) == (
        "美债 10 年减 2 年利差 UST_2S10S_SPREAD 35.00 基点 2026-10-14 正值（未倒挂） 近 5 日 —"
    )
    assert "2026-10-13 倒挂 近 5 日" in _words(inverted)
    for card in (positive, inverted):
        drawer = _words(_drawer(page, card))
        assert "上升" not in _words(card) + drawer
        assert "下降" not in _words(card) + drawer
    assert "利差正负 正值（10 年高于 2 年）" in _words(_drawer(page, positive))
    assert "利差正负 倒挂（10 年低于 2 年）" in _words(_drawer(page, inverted))


def test_every_card_and_other_row_has_its_own_drawer() -> None:
    rows = [
        UST10Y,
        _row("UST2Y_NOMINAL_YIELD", 4.6, "percent"),
        _row("JP_10Y_YIELD", 1.62, "percent", dimensions={"tenor": "10Y"}),
        _row("JP_10Y_YIELD", 1.1, "percent", dimensions={"tenor": "5Y"}),
    ]
    projection = _overseas_projection(rows)
    page = dashboard_page("/", projection, (), ())

    cards = _cards(projection)

    assert len({_href(card) for card in cards}) == 4
    for card in cards:
        assert _words(card).split()[0] in _words(_drawer(page, card))


def test_a_pinned_older_projection_fills_the_drawer_from_its_own_rows() -> None:
    current = _overseas_projection([UST10Y])
    older = replace(
        _overseas_projection([{**UST10Y, "value": 4.88, "selected_claim_id": "claim-older"}]),
        envelope=replace(current.envelope, projection_set_id="projection-older"),
    )

    page = dashboard_page("/", older, (), ())
    (card,) = _cards(older)
    drawer = _drawer(page, card)

    assert "最新值 4.88 %" in _words(drawer)
    assert "5.19 %" not in _words(card)
    evidence = [href for href in _hrefs(drawer) if href.startswith("/data-chain?")]
    assert evidence
    assert all("projection=projection-older" in href for href in evidence)
    assert "version=claim-older" in evidence[0]


def test_a_repeated_row_never_takes_the_key_of_another_row() -> None:
    # The third row repeats the first; numbering it by position would collide with the second.
    rows = [
        _row("JP_A", 1.11, "percent"),
        _row("JP_A-3", 2.22, "percent"),
        _row("JP_A", 3.33, "percent", period="2026-10-13"),
    ]
    projection = _overseas_projection(rows)
    page = dashboard_page("/", projection, (), ())

    cards = _cards(projection)

    assert len({_href(card) for card in cards}) == 3
    for card, value in zip(cards, ("1.11 %", "2.22 %", "3.33 %"), strict=True):
        assert f"最新值 {value}" in _words(_drawer(page, card))
