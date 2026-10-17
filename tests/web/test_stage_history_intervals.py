"""The 06 stage history as bands, day counts and a list of intervals (ticket 07).

Each case builds a small stage history by hand and asserts the intervals a reader sees and
what the drawer each interval opens says of its days.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_dashboard_contract import _hrefs, _text
from tests.web.test_overseas_cards import _by_id, _find, _words


def _day(day: str, official: str, **fields: Any) -> dict[str, Any]:
    return {
        "date": day,
        "official": official,
        "bond": "bull",
        "stock": "bear",
        "commodity": "bull",
        "projection_set_id": f"projection-{day}",
        "assessment_id": f"assessment-{day}",
        "corrects": None,
        **fields,
    }


def _history(days: list[dict[str, Any]], **document: Any) -> ProjectionSet:
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")]
    )
    counts: dict[str, int] = {}
    for day in days:
        counts[day["official"]] = counts.get(day["official"], 0) + 1
    return replace(
        projection,
        datasets={
            **projection.datasets,
            "stage_history": {"display": {"days": days, "counts": counts}, **document},
        },
    )


def _section(page: object) -> Component:
    return _by_id(page, "history")


def _intervals(projection: ProjectionSet | None, events: tuple[dict[str, Any], ...] = ()) -> Any:
    """The section's interval triggers in page order, each with the panel it opens."""
    page = dashboard_page("/", projection, (), (), events)
    triggers = [
        trigger
        for trigger in _find(
            _section(page), lambda item: str(getattr(item, "href", "")).startswith("#drawer-")
        )
        if "history-interval" in str(getattr(trigger, "href", ""))
    ]
    return [(trigger, _by_id(page, str(getattr(trigger, "href", ""))[1:])) for trigger in triggers]


def test_consecutive_days_of_one_state_merge_and_a_change_of_state_breaks_the_interval() -> None:
    projection = _history(
        [
            _day("2026-04-27", "stage_iii"),
            _day("2026-04-28", "stage_iii"),
            _day("2026-04-29", "stage_iii"),
            _day("2026-04-30", "noncanonical_combination"),
            _day("2026-05-06", "noncanonical_combination"),
            _day("2026-05-07", "stage_iii"),
        ]
    )

    rows = [_words(trigger) for trigger, _panel in _intervals(projection)]

    assert rows == [
        "04-27～04-29 第三阶段 3 日",
        "04-30～05-06 非典型组合，暂无正式阶段 2 日",
        "05-07 第三阶段 1 日",
    ]


def test_an_interval_drawer_lists_each_day_with_its_correction_version_and_projection() -> None:
    corrected = {
        "assessment_id": "assessment-old-04-28",
        "projection_set_id": "projection-old-04-28",
        "reason": "core_history_basis_changed",
        "scope": "core_only",
    }
    projection = _history(
        [
            _day("2026-04-27", "noncanonical_combination"),
            _day("2026-04-28", "noncanonical_combination", corrects=corrected),
        ],
        events=[
            {
                "business_date": "2026-04-28",
                "current_stage": None,
                "last_confirmed_stage": "stage_iii",
                "stage_reason": "noncanonical_combination",
                "gaps": ["commodity:source_conflict"],
                "model_version_id": "model-v0015",
                "corrects": corrected,
            }
        ],
    )

    ((trigger, panel),) = _intervals(projection)
    text = _words(panel)

    assert _words(trigger) == "04-27～04-28 非典型组合，暂无正式阶段 2 日 含更正 1 日"
    assert text.index("2026-04-27 · 非典型组合，暂无正式阶段") < text.index(
        "2026-04-28 · 非典型组合，暂无正式阶段"
    )
    assert text.count("更正版本") == 1
    assert "更正版本：更正 projection-old-04-28 （核心历史口径变更；只更正核心与正式阶段" in text
    assert "上一确认 第三阶段 · Stage III" in text
    assert "商品：来源冲突" in text
    assert "/?projection=projection-2026-04-27#history" in _hrefs(panel)
    assert "/?projection=projection-2026-04-28#history" in _hrefs(panel)
    assert "/?projection=projection-old-04-28#history" in _hrefs(panel)


def test_the_interval_list_covers_the_latest_120_trading_days() -> None:
    sessions = [date(2026, 3, 2) + timedelta(days=offset) for offset in range(182)]
    weekdays = [day.isoformat() for day in sessions if day.weekday() < 5][:125]
    projection = _history(
        [_day(day, "core_data_pending") for day in weekdays[:5]]
        + [_day(day, "stage_iii") for day in weekdays[5:]]
    )

    rows = [_words(trigger) for trigger, _panel in _intervals(projection)]

    assert rows == [f"{weekdays[5][5:]}～{weekdays[-1][5:]} 第三阶段 120 日"]
    section = _text(_section(dashboard_page("/", projection, (), ())))
    assert "阶段区间（最近 120 个交易日）" in section
    # The bands still count every day the set aligned, reasons in words.
    assert "核心数据待处理 5 日" in section


def test_the_trading_day_table_opens_in_a_drawer_and_the_page_lists_no_daily_events() -> None:
    corrected = {
        "assessment_id": "assessment-old-04-28",
        "projection_set_id": "projection-old-04-28",
        "reason": "core_history_basis_changed",
        "scope": "whole_day",
    }
    projection = _history(
        [
            _day("2026-04-27", "stage_iii"),
            _day("2026-04-28", "stage_iii", corrects=corrected),
        ]
    )
    page = dashboard_page("/", projection, (), ())
    section = _section(page)

    (trigger,) = _find(section, lambda item: "history-calendar" in str(getattr(item, "href", "")))
    panel = _by_id(page, str(getattr(trigger, "href", ""))[1:])
    text = _words(panel)

    assert _words(trigger) == "交易日历与色带等价表格"
    assert text.index("2026-04-27 第三阶段 牛市 熊市 牛市") < text.index("2026-04-28")
    assert "/?projection=projection-2026-04-28#history" in _hrefs(panel)
    assert "/?projection=projection-old-04-28#history" in _hrefs(panel)
    # No day opens in place, and the old daily event list is gone from the section.
    assert not _find(section, lambda item: type(item).__name__ == "Details")
    assert "正式区间与空档" not in _text(section)


def test_a_pinned_set_lists_its_own_history_not_the_read_models_later_days() -> None:
    pinned = _history(
        [_day("2026-04-27", "stage_iii"), _day("2026-04-28", "stage_iii")],
        events=[
            {
                "business_date": "2026-04-28",
                "current_stage": "stage_iii",
                "last_confirmed_stage": "stage_iii",
                "stage_reason": "canonical_combination",
                "gaps": [],
                "model_version_id": "model-v0015",
            }
        ],
    )
    later: tuple[dict[str, object], ...] = (
        {
            "business_date": "2026-04-28",
            "current_stage": None,
            "stage_reason": "noncanonical_combination",
            "projection_set_id": "projection-later-04-28",
            "corrects": {"projection_set_id": "projection-2026-04-28", "reason": "x"},
        },
        {
            "business_date": "2026-04-29",
            "current_stage": None,
            "stage_reason": "noncanonical_combination",
            "projection_set_id": "projection-2026-04-29",
        },
    )

    ((trigger, panel),) = _intervals(pinned, later)
    section = _section(dashboard_page("/", pinned, (), (), later))

    assert _words(trigger) == "04-27～04-28 第三阶段 2 日"
    assert "原因 典型组合" in _words(panel)
    assert "projection-later-04-28" not in _text(section)
    assert "2026-04-29" not in _text(section)


def test_the_lookback_before_the_window_sits_atop_the_trading_day_drawer() -> None:
    lookback = {
        "status": "found",
        "stage": "stage_ii",
        "stage_date": "2026-01-15",
        "years": 5,
        "core_requests": 3,
        "calendar_requests": 2,
    }
    projection = _history([_day("2026-04-27", "stage_iii")], last_confirmed_lookback=lookback)
    page = dashboard_page("/", projection, (), ())

    (trigger,) = _find(
        _section(page), lambda item: "history-calendar" in str(getattr(item, "href", ""))
    )
    text = _words(_by_id(page, str(getattr(trigger, "href", ""))[1:]))

    assert text.index("窗口前的上一确认阶段") < text.index("2026-04-27 第三阶段")
    assert "第二阶段 · Stage II（回溯得出，最近一次在 2026-01-15）" in text
    assert "回溯 5 年，区间请求 3 次、日历请求 2 次" in text
    assert _words(page).count("窗口前的上一确认阶段") == 1


def test_intervals_and_day_counts_name_a_stage_once_in_chinese_and_its_drawer_adds_the_code() -> (
    None
):
    projection = _history(
        [
            _day("2026-04-27", "core_data_pending"),
            _day("2026-04-28", "stage_iii"),
            _day("2026-04-29", "stage_iii"),
        ]
    )
    page = dashboard_page("/", projection, (), ())

    rows = [(_words(trigger), panel) for trigger, panel in _intervals(projection)]
    (stage_panel,) = [panel for words, panel in rows if "第三阶段" in words]
    (heading,) = _find(stage_panel, lambda item: type(item).__name__ == "H2")

    assert [words for words, _panel in rows] == [
        "04-27 核心数据待处理 1 日",
        "04-28～04-29 第三阶段 2 日",
    ]
    assert "正式阶段日数：核心数据待处理 1 日 · 第三阶段 2 日" in _words(_section(page))
    assert _words(heading) == "第三阶段 · 04-28～04-29"
    assert "Stage III" in _words(stage_panel.children[0])


def _is_panel(item: object) -> bool:
    return getattr(item, "role", None) == "dialog"


def _sides(projection: ProjectionSet | None, events: tuple[dict[str, Any], ...] = ()) -> Any:
    """Section 06's two sides, bands then intervals, and the drawers that follow them."""
    section = _section(dashboard_page("/", projection, (), (), events))
    _header, layout, *rest = section.children
    bands, intervals = layout.children
    return bands, intervals, rest


def test_the_bands_and_the_interval_list_sit_side_by_side_with_their_drawers_after_both() -> None:
    projection = _history([_day("2026-04-27", "stage_iii"), _day("2026-04-28", "stage_iii")])

    bands, intervals, rest = _sides(projection)

    assert _words(bands).startswith("正式阶段由债券、股票、商品的 120 日稳定方向映射")
    assert _words(bands).endswith("正式阶段日数：第三阶段 2 日 交易日历与色带等价表格")
    assert _words(intervals) == "阶段区间（最近 120 个交易日） 04-27～04-28 第三阶段 2 日"
    # The drawers sit outside both sides, so a fixed panel opens against the viewport.
    assert not _find(bands, _is_panel) and not _find(intervals, _is_panel)
    assert [_words(item.children[0]) for item in rest if _is_panel(item)] == [
        "交易日历与色带等价表格 关闭",
        "第三阶段 · 04-27～04-28 Stage III 关闭",
    ]
    assert _words(rest[-1]) == "本投影解读 →"


def test_a_set_without_bands_says_so_on_the_left_and_still_lists_its_intervals() -> None:
    projection = replace(
        _history([]),
        datasets={
            **_history([]).datasets,
            "stage_history": {
                "events": [
                    {
                        "business_date": "2026-10-14",
                        "current_stage": None,
                        "stage_reason": "noncanonical_combination",
                        "projection_set_id": "projection-2026-10-14",
                    },
                    {
                        "business_date": "2026-10-15",
                        "current_stage": None,
                        "stage_reason": "noncanonical_combination",
                        "projection_set_id": "projection-2026-10-15",
                    },
                ]
            },
        },
    )

    bands, intervals, _rest = _sides(projection)

    assert "旧投影未提供对齐的交易日色带；历史事件仍可阅读。" in _words(bands)
    assert (
        _words(intervals)
        == "阶段区间（最近 120 个交易日） 10-14～10-15 非典型组合，暂无正式阶段 2 日"
    )
