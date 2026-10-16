"""Chinese display names first, codes second, across the cockpit (ticket 02).

A name comes from the frozen catalog's ``name_cn`` when it is not the code, then from the
page's display-name table by metric and member dimensions, and otherwise falls back to the
code with a "未提供中文名" note in the drawer.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dash import html

from pring_cycle.cockpit_operations import data_chain
from pring_cycle.confirmation import OUTPUT_STRUCTURE
from pring_cycle.dashboard import dashboard_page
from pring_cycle.runs import RunRepository
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_overseas_cards import (
    _by_id,
    _cards,
    _drawer,
    _find,
    _overseas_projection,
    _row,
    _words,
)


def test_an_overseas_card_shows_the_table_name_first_and_its_code_second() -> None:
    projection = _overseas_projection([_row("UST10Y_NOMINAL_YIELD", 5.19, "percent")])

    (card,) = _cards(projection)

    assert _words(card).startswith("美国 10 年期国债收益率 UST10Y_NOMINAL_YIELD 5.19 %")


def test_a_catalog_chinese_name_wins_over_the_table() -> None:
    projection = _overseas_projection(
        [_row("UST10Y_NOMINAL_YIELD", 5.19, "percent", name_cn="美债十年期名义收益率")]
    )
    page = dashboard_page("/", projection, (), ())

    (card,) = _cards(projection)

    assert _words(card).startswith("美债十年期名义收益率 UST10Y_NOMINAL_YIELD")
    assert _words(_drawer(page, card)).startswith("美债十年期名义收益率 UST10Y_NOMINAL_YIELD 关闭")


def test_without_any_chinese_name_the_code_shows_once_and_the_drawer_says_so() -> None:
    projection = _overseas_projection([_row("JP_10Y_YIELD", 1.62, "percent")])
    page = dashboard_page("/", projection, (), ())

    (card,) = _cards(projection)
    drawer = _words(_drawer(page, card))

    assert _words(card).startswith("JP_10Y_YIELD 1.62 %")
    assert drawer.startswith("JP_10Y_YIELD 关闭 未提供中文名")
    assert "未提供中文名" not in _words(card)


def _is_td(item: object) -> bool:
    return isinstance(item, html.Td)


def _member(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"label": label, "reads_as": None, "evidence": rows}


def _observation_names(members: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """The 02 stock card's observation rows as (name shown, code on hover)."""
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        macro={"observation_interfaces": {"cores": [{"core": "stock", "members": members}]}},
    )
    section = _by_id(dashboard_page("/", projection, (), ()), "assets")
    rows = _find(section, lambda item: isinstance(item, html.Tr))
    names = [_find(row, lambda item: isinstance(item, html.Td))[0] for row in rows[1:]]
    return [
        (_words(cell), str(_find(cell, lambda item: getattr(item, "title", None))[0].title))
        for cell in names
    ]


def test_members_of_one_metric_get_names_that_tell_them_apart() -> None:
    valuation = [
        _row("CN_INDEX_VALUATION", 1.3, "multiple", dimensions={"index": i, "measure": m})
        for i, m in (("000300.SH", "price_book"), ("000905.SH", "turnover_rate"))
    ]
    breadth = [
        _row(
            "CN_EQ_ADV_DEC",
            978,
            "count",
            dimensions={"measure": m, "universe": "point_in_time_traded_a_shares"},
        )
        for m in ("advances", "declines")
    ]

    names = _observation_names([_member("估值", valuation), _member("市场广度：涨跌家数", breadth)])

    assert names == [
        ("沪深 300 市净率", "CN_INDEX_VALUATION · 000300.SH × price_book"),
        ("中证 500 换手率", "CN_INDEX_VALUATION · 000905.SH × turnover_rate"),
        ("上涨家数", "CN_EQ_ADV_DEC · advances"),
        ("下跌家数", "CN_EQ_ADV_DEC · declines"),
    ]


def test_the_financing_buy_amount_is_no_longer_called_the_balance() -> None:
    margin = [
        _row(
            "CN_MARGIN_BALANCE_SSE_SZSE",
            value,
            "hundred_million_cny",
            name_cn="沪深两所融资余额与买入额",
            dimensions={"measure": measure, "scope": "sse_szse"},
        )
        for measure, value in (("financing_balance", 24974.85), ("financing_buy_amount", 1122.85))
    ]

    names = _observation_names([_member("融资余额", margin)])

    assert names == [
        ("融资余额", "CN_MARGIN_BALANCE_SSE_SZSE · financing_balance"),
        ("融资买入额", "CN_MARGIN_BALANCE_SSE_SZSE · financing_buy_amount"),
    ]


def test_an_unmapped_observation_keeps_its_interface_label_before_the_code() -> None:
    names = _observation_names([_member("北向资金", [_row("CN_NORTHBOUND_FLOW", 12.0, "percent")])])

    assert names == [("北向资金", "CN_NORTHBOUND_FLOW")]


def test_the_1630_close_reads_in_yuan_per_dollar_rather_than_a_bare_scalar() -> None:
    projection = _overseas_projection([_row("CN_USDCNY_CLOSE_1630", 7.1, "scalar")])
    page = dashboard_page("/", projection, (), ())

    (card,) = _cards(projection)

    assert _words(card).startswith("美元兑人民币 16:30 收盘价 CN_USDCNY_CLOSE_1630 7.10 元/美元")
    assert "最新值 7.10 元/美元" in _words(_drawer(page, card))
    assert "scalar" not in _words(_by_id(page, "overseas"))


def _warrant(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "first": 100.0,
        "last": 120.0,
        "unit": "tonne",
        "input_unit": "tonne",
        "factor": 1.0,
        "weight_basis": "吨",
        "change_rate": 0.2,
        "status": "read",
        "first_claim_ids": [],
        "last_claim_ids": [],
    }


def test_warrant_symbols_read_in_chinese_with_the_symbol_beside_them() -> None:
    board = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")]
    )
    warrants = {
        "first_day": "2026-04-01",
        "last_day": "2026-09-30",
        "symbols": [_warrant("CF"), _warrant("TA"), _warrant("SC")],
    }
    projection = replace(
        board,
        datasets={
            **board.datasets,
            "inventory": {"output_structure": OUTPUT_STRUCTURE, "registered_warrants": warrants},
        },
    )
    section = _by_id(dashboard_page("/", projection, (), ()), "inventory")

    tables = _find(section, lambda item: isinstance(item, html.Table))
    rows = _find(tables[-1], lambda item: isinstance(item, html.Tr))[1:]
    cells = [_find(row, lambda item: isinstance(item, html.Td))[0] for row in rows]
    text = _words(section)

    assert [_words(cell) for cell in cells] == ["棉花", "PTA", "原油"]
    assert [
        str(_find(cell, lambda item: getattr(item, "title", None))[0].title) for cell in cells
    ] == ["CN_FUTURES_WARRANTS · CF", "CN_FUTURES_WARRANTS · TA", "CN_FUTURES_WARRANTS · SC"]
    assert "棉花（CF）" in text
    assert "原油（SC）" in text


def test_the_data_chain_request_table_names_metrics_and_sources_in_chinese(
    tmp_path: Path,
) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run = runs.submit_manual_full(
        target_business_date="2026-10-14",
        client_request_id="display-names",
        model_version_id="model-v0015",
        system_as_of=datetime(2026, 10, 14, 13, tzinfo=UTC),
    )
    summary = {
        "gaps": [],
        "requests": [
            {
                "request_id": "request-1",
                "channel": "tushare",
                "phase": "direct_context_refresh",
                "result": "accepted",
                "classification": None,
                "metric_ids": ["CN_EQ_CSI300", "CN_EQ_ADV_DEC", "JP_10Y_YIELD"],
                "gap_ids": [],
                "source_record_count": 3,
                "claim_count": 3,
            }
        ],
    }

    page = data_chain([run], run, summary, {"run": run.run_id}, None)
    (request_table,) = [
        found
        for found in _find(page, lambda item: isinstance(item, html.Table))
        if _words(found).startswith("请求 来源 / 环节")
    ]
    cells = _find(_find(request_table, lambda item: isinstance(item, html.Tr))[1], _is_td)

    assert _words(cells[1]) == "TuShare / 背景指标取数"
    assert _words(cells[3]).replace(" 、 ", "、") == "沪深 300、涨跌家数、JP_10Y_YIELD"
    assert [
        str(item.title) for item in _find(cells[3], lambda item: getattr(item, "title", None))
    ] == ["CN_EQ_CSI300", "CN_EQ_ADV_DEC", "JP_10Y_YIELD"]
