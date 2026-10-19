"""Section 06's macro judgement row (ADR-0043, macro stage ticket 08).

A set whose stage history records the macro main conclusion shows it as the bands' first
row, a stage's colour deeper the firmer its confidence, beside the formal stage and the
three cores; the left side keeps its bands and day counts, the right its intervals, which
can also be listed by the macro judgement. A day before the rules, or with no stage to
take, is a blank of the row. A set from before ticket 08 shows its four rows as it did.
"""

from __future__ import annotations

from typing import Any

from dash import dcc
from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.web.test_overseas_cards import _by_id, _find, _words
from tests.web.test_stage_history_intervals import _day, _history, _is_panel, _sides


def _macro(day: str, official: str, macro: str, confidence: str | None) -> dict[str, Any]:
    return _day(day, official, macro=macro, macro_confidence=confidence)


def _with_macro_counts(projection: ProjectionSet) -> ProjectionSet:
    display = projection.datasets["stage_history"]["display"]
    counts: dict[str, int] = {}
    for day in display["days"]:
        key = ":".join(filter(None, (day["macro"], day["macro_confidence"])))
        counts[key] = counts.get(key, 0) + 1
    display["macro_counts"] = counts
    return projection


def _projection() -> ProjectionSet:
    return _with_macro_counts(
        _history(
            [
                _macro("2026-10-12", "stage_iii", "not_effective", None),
                _macro("2026-10-13", "stage_iii", "stage_v", "explicit"),
                _macro("2026-10-14", "noncanonical_combination", "stage_v", "explicit"),
                _macro("2026-10-15", "noncanonical_combination", "stage_v", "tendency"),
                _macro("2026-10-16", "core_data_pending", "no_stage", None),
            ]
        )
    )


def _bands(projection: ProjectionSet) -> dict[str, Any]:
    bands, _intervals, _rest = _sides(projection)
    [graph] = _find(bands, lambda item: isinstance(item, dcc.Graph))
    return graph.figure["data"][0]  # type: ignore[no-any-return]


def _colour(trace: dict[str, Any], row: int, column: int) -> str | None:
    """The colour a cell is painted, None for a blank."""
    index = trace["z"][row][column]
    if index is None:
        return None
    scale = dict((round(stop * trace["zmax"]), colour) for stop, colour in trace["colorscale"])
    return scale[index]  # type: ignore[no-any-return]


def test_the_macro_judgement_is_the_bands_first_row_its_confidence_told_apart() -> None:
    trace = _bands(_projection())

    assert list(trace["y"]) == ["宏观判断", "价格阶段", "债券", "股票", "商品"]
    assert trace["text"][0] == [
        "生效前",
        "第五阶段（明确）",
        "第五阶段（明确）",
        "第五阶段（倾向）",
        "无可取阶段",
    ]
    # A day before the rules and one with no stage to take are blanks of the row.
    assert _colour(trace, 0, 0) is None and _colour(trace, 0, 4) is None
    # One stage, one colour; a tendency is a lighter shade of it than an explicit day.
    assert _colour(trace, 0, 1) == _colour(trace, 0, 2)
    assert _colour(trace, 0, 3) not in {None, _colour(trace, 0, 2)}


def test_a_stage_keeps_its_colour_whatever_else_the_bands_show() -> None:
    # Stage III explicit on the macro row is the formal row's stage III.
    projection = _with_macro_counts(
        _history(
            [
                _macro("2026-10-13", "stage_iii", "stage_iii", "explicit"),
                _macro("2026-10-14", "stage_v", "stage_iii", "explicit"),
            ]
        )
    )
    other = _with_macro_counts(
        _history([_macro("2026-10-13", "noncanonical_combination", "stage_iii", "weak")])
    )

    trace = _bands(projection)

    assert _colour(trace, 0, 0) == _colour(trace, 1, 0)
    assert _colour(trace, 1, 1) != _colour(trace, 1, 0)
    assert _colour(trace, 1, 0) == _colour(_bands(_projection()), 1, 0)
    assert _colour(_bands(other), 0, 0) not in {None, _colour(trace, 0, 0)}


def test_the_left_side_counts_the_macro_days_and_its_table_lists_them_the_layout_kept() -> None:
    bands, intervals, rest = _sides(_projection())

    text = _words(bands)
    assert text.startswith("宏观判断由政策、信用、增长、物价、库存五维对照特征表得出")
    assert (
        "宏观判断日数：生效前 1 日 · 第五阶段（明确） 2 日 · 第五阶段（倾向） 1 日 · "
        "无可取阶段 1 日" in text
    )
    assert "价格阶段日数：第三阶段 2 日 · 非典型组合，暂无价格阶段 2 日" in text
    # The drawers still follow both sides; the table's columns lead with the macro row.
    assert not _find(bands, _is_panel) and not _find(intervals, _is_panel)
    [calendar] = [item for item in rest if _is_panel(item) and "色带" in _words(item.children[0])]
    table = _words(calendar)
    assert "交易日 宏观判断 价格阶段 债券 股票 商品" in table
    assert "2026-10-15 第五阶段（倾向） 非典型组合，暂无价格阶段" in table


def _views(intervals: Component) -> tuple[list[Component], list[Component]]:
    buttons = _find(intervals, lambda item: getattr(item, "data-history-view", None) is not None)
    switches = [item for item in buttons if type(item).__name__ == "Button"]
    lists = [item for item in buttons if type(item).__name__ == "Ul"]
    return switches, lists


def test_the_intervals_can_be_listed_by_the_macro_judgement() -> None:
    page = dashboard_page("/", _projection(), (), ())
    _bands_side, intervals, _rest = _sides(_projection())

    switches, lists = _views(intervals)

    assert [(_words(item), getattr(item, "aria-pressed")) for item in switches] == [
        ("价格阶段", "true"),
        ("宏观判断", "false"),
    ]
    official, macro = lists
    assert (official.hidden, macro.hidden) == (False, True)
    assert [_words(item) for item in official.children] == [
        "10-12～10-13 第三阶段 2 日",
        "10-14～10-15 非典型组合，暂无价格阶段 2 日",
        "10-16 核心数据待处理 1 日",
    ]
    # By the macro judgement: a confidence changed breaks the interval, as a stage does.
    assert [_words(item) for item in macro.children] == [
        "10-12 生效前 1 日",
        "10-13～10-14 第五阶段（明确） 2 日",
        "10-15 第五阶段（倾向） 1 日",
        "10-16 无可取阶段 1 日",
    ]
    [trigger] = _find(macro.children[1], lambda item: getattr(item, "href", None))
    panel = _by_id(page, str(trigger.href)[1:])
    assert _words(panel.children[0]).startswith("第五阶段（明确） · 10-13～10-14")
    assert "2026-10-13" in _words(panel) and "2026-10-14" in _words(panel)


def test_a_set_from_before_the_macro_row_shows_its_four_rows_and_says_why() -> None:
    projection = _history([_day("2026-04-27", "stage_iii"), _day("2026-04-28", "stage_iii")])

    bands, intervals, _rest = _sides(projection)

    assert list(_bands(projection)["y"]) == ["正式阶段", "债券", "股票", "商品"]
    assert _words(bands).startswith("正式阶段由债券、股票、商品的 120 日稳定方向映射")
    assert "该投影生成时尚无宏观判断" in _words(bands)
    assert _views(intervals) == ([], [])


def test_a_set_whose_days_all_precede_the_rules_shows_its_four_rows() -> None:
    # A model without the rules publishes the row's field, every day before them.
    projection = _with_macro_counts(
        _history(
            [
                _macro("2026-10-13", "stage_iii", "unpublished", None),
                _macro("2026-10-14", "stage_iii", "not_effective", None),
            ]
        )
    )

    bands, intervals, _rest = _sides(projection)

    assert list(_bands(projection)["y"]) == ["正式阶段", "债券", "股票", "商品"]
    assert "该投影生成时尚无宏观判断" in _words(bands)
    assert _views(intervals) == ([], [])
