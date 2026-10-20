"""The 07 section kept compact: coverage, the gaps once, a reading summary (ticket 08).

Each case renders the home page from a small hand-built projection and reports, and asserts
what a reader sees in section 07 and inside the drawers it opens.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from pring_cycle.runs import RunRepository
from tests.integration.test_worker_execution import runtime
from tests.web.test_board_footer import CUTOFF, _report
from tests.web.test_board_footer import _reading as _ai_body
from tests.web.test_conclusion_board import _asset, _projection
from tests.web.test_dashboard_contract import _text
from tests.web.test_overseas_cards import _by_id, _find


def _gap(metric_id: str, category: str = "missing", priority: str = "P1") -> dict[str, Any]:
    return {
        "category": category,
        "priority": priority,
        "metric_id": metric_id,
        "reason": "period_not_requested",
    }


def _gaps_projection(gaps: list[dict[str, Any]]) -> ProjectionSet:
    return _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        gap_list=gaps,
    )


def _reading(
    projection: ProjectionSet | None,
    runs: tuple[Any, ...] = (),
    reports: tuple[Any, ...] = (),
    release_events: tuple[dict[str, object], ...] = (),
) -> Component:
    page = dashboard_page("/", projection, runs, reports, (), release_events)
    return _by_id(page, "reading")


def _visible(component: object) -> str:
    """Section text without the hidden drawer panels."""
    if isinstance(component, (list, tuple)):
        return " ".join(_visible(child) for child in component)
    if isinstance(component, Component):
        if getattr(component, "hidden", False):
            return ""
        return _visible(getattr(component, "children", None))
    return component if isinstance(component, str) else ""


def _words(text: str) -> str:
    return " ".join(text.split())


def _trigger(section: Component, label: str) -> Component:
    (found,) = _find(
        section,
        lambda item: str(getattr(item, "href", "")).startswith("#drawer-") and label in _text(item),
    )
    return found


def _panel(container: Component, trigger: Component) -> str:
    return _words(_text(_by_id(container, str(getattr(trigger, "href", ""))[1:])))


def test_gaps_are_listed_once_and_five_at_most_with_the_rest_in_a_drawer() -> None:
    gaps = [_gap(f"METRIC_{index}") for index in range(1, 8)]

    page = dashboard_page("/", _gaps_projection(gaps), (), ())
    section = _by_id(page, "reading")
    visible = _words(_visible(section))

    assert [visible.count(f"METRIC_{index}：") for index in range(1, 8)] == [1] * 5 + [0, 0]
    trigger = _trigger(section, "查看全部")
    assert "7" in _text(trigger)
    panel = _panel(page, trigger)
    assert all(f"P1 METRIC_{index}：未请求" in panel for index in range(1, 8))


def test_the_data_boundary_and_section_07_open_the_same_gap_drawer() -> None:
    gaps = [_gap(f"METRIC_{index}") for index in range(1, 8)]
    page = dashboard_page("/", _gaps_projection(gaps), (), ())

    boundary = _trigger(_by_id(page, "conclusion"), "7 项缺口")
    full = _trigger(_by_id(page, "reading"), "查看全部")
    panels = _find(
        page,
        lambda item: (
            "drawer-panel" in str(getattr(item, "className", "")) and "METRIC_7" in _text(item)
        ),
    )

    assert getattr(boundary, "href", None) == getattr(full, "href", None)
    assert len(panels) == 1
    assert _words(_text(panels[0])).startswith("全部缺口（7）")


def test_five_gaps_or_fewer_need_no_drawer() -> None:
    section = _reading(
        _gaps_projection([_gap("CN_SF_TOTAL"), _gap("EIA_WTI_RWTC", "fetch_failed")])
    )
    visible = _words(_visible(section))

    assert visible.count("CN_SF_TOTAL）：") == 1 and visible.count("EIA_WTI_RWTC）：") == 1
    assert "查看全部" not in visible


def test_historical_warrant_days_are_one_row_with_periods_and_symbols_in_the_drawer() -> None:
    """Worker gaps 04: the plan's historical days, one row a metric, details in the drawer."""
    warrants = {
        **_gap("CN_FUTURES_WARRANTS", priority="P2"),
        "reason": "historical_periods_missing",
        "missing_periods": [
            {
                "period": "2026-07-21",
                "missing_members": [
                    f"CN_FUTURES_WARRANTS:symbol_missing:{symbol}"
                    for symbol in ("CU", "RB", "RU", "SC", "SP")
                ],
            },
            {"period": "2026-09-09", "missing_members": ["CN_FUTURES_WARRANTS:symbol_missing:PP"]},
        ],
    }
    page = dashboard_page("/", _gaps_projection([warrants, _gap("CN_SF_TOTAL")]), (), ())
    section = _by_id(page, "reading")
    visible = _words(_visible(section))

    assert (
        "P2 期货注册仓单（CN_FUTURES_WARRANTS）：历史缺期 2 期共缺 6 个成员"
        "（2026-07-21 至 2026-09-09）"
    ) in visible
    assert "铜" not in visible
    panel = _panel(page, _trigger(section, "缺期明细"))
    assert (
        "历史缺期 2026-07-21 缺 铜（CU）、螺纹钢（RB）、天然橡胶（RU）、原油（SC）、纸浆（SP）；"
        "2026-09-09 缺 聚丙烯（PP）"
    ) in panel


def _template_report(projection: ProjectionSet, gaps: list[dict[str, Any]]) -> Any:
    return _report(
        projection.envelope.projection_set_id,
        status="completed_degraded",
        adapter="deterministic",
        adapter_outcomes=(("codex_cli", "timed_out"),),
        body={
            "ai_explanation": [
                {"title": "非典型组合解读", "explanation": "与阶段 V只差债券一项。"}
            ],
            "explanation_source": "deterministic_template",
            "core_states": {"bond": "bull", "stock": "bear", "commodity": "bull"},
            "verified_results": {"noncanonical_basis": {"comparisons": []}, "p0": "passed"},
            "gap_list": gaps,
        },
    )


def test_a_template_reading_does_not_repeat_the_gaps_its_report_bound() -> None:
    gaps = [_gap("CN_SF_TOTAL"), _gap("EIA_BRENT_RBRTE")]
    projection = _gaps_projection(gaps)

    section = _reading(projection, reports=(_template_report(projection, gaps),))

    assert _words(_text(section)).count("CN_SF_TOTAL）：") == 1


def test_a_template_report_summary_is_the_note_and_the_noncanonical_reading() -> None:
    projection = _gaps_projection([])

    section = _reading(projection, reports=(_template_report(projection, []),))
    visible = _words(_visible(section))

    assert (
        "本次报告为确定性模板，无 AI 解读（适配器失败原因：codex_cli 超时） "
        "非典型组合解读 与阶段 V只差债券一项。 查看报告详情"
    ) in visible
    assert "报告身份" not in visible and "noncanonical_basis" not in visible


def test_report_details_open_in_a_drawer_with_identity_cutoff_and_bound_facts() -> None:
    projection = _gaps_projection([])

    section = _reading(projection, reports=(_template_report(projection, []),))
    panel = _panel(section, _trigger(section, "查看报告详情"))

    assert "报告身份 report-projection-board-1" in panel
    assert "投影身份 projection-board" in panel
    assert "截止点 2026-08-28T13:00:00+00:00" in panel
    assert "时效判定 目标日 2026-08-28；时效截至 2026-08-28 21:00（北京）" in panel
    assert '三核心 {"bond": "bull", "commodity": "bull", "stock": "bear"}' in panel
    assert '已验证结果 {"noncanonical_basis": {"comparisons": []}, "p0": "passed"}' in panel


def test_an_ai_summary_is_the_first_paragraph_of_the_latest_same_projection_report() -> None:
    projection = _gaps_projection([])
    identity = projection.envelope.projection_set_id
    reports = (
        _report(identity, version=1, body=_ai_body("旧版首段。")),
        _report(
            identity, version=2, body=_ai_body("债券牛市而股票熊市。商品仍为牛市。", "第二段。")
        ),
        _report("projection-other", version=3, body=_ai_body("别的投影首段。")),
    )

    section = _reading(projection, reports=reports)
    visible = _words(_visible(section))

    assert "AI 解读 · codex_cli 债券牛市而股票熊市。商品仍为牛市。 查看报告详情" in visible
    assert "第二段" not in visible
    assert "旧版首段" not in _text(section) and "别的投影首段" not in _text(section)
    panel = _panel(section, _trigger(section, "查看报告详情"))
    assert "报告身份 report-projection-board-2" in panel and "第二段。" in panel


def test_report_details_mark_a_reading_that_kept_raw_codes() -> None:
    projection = _gaps_projection([])
    identity = projection.envelope.projection_set_id
    coded = {
        **_ai_body("沿 stage_iii 解读（来源：tushare:index_daily）。"),
        "untranslated_codes": ["stage_iii", "tushare:index_daily"],
    }

    marked = _reading(projection, reports=(_report(identity, body=coded),))
    clean = _reading(projection, reports=(_report(identity, body=_ai_body("沿第三阶段解读。")),))

    panel = _panel(marked, _trigger(marked, "查看报告详情"))
    assert "含未翻译代号：stage_iii、tushare:index_daily" in panel
    assert "未翻译代号" not in _panel(clean, _trigger(clean, "查看报告详情"))


def test_without_a_report_the_section_says_so_and_keeps_generate_and_history() -> None:
    section = _reading(_gaps_projection([]))
    visible = _words(_visible(section))

    assert (
        "报告尚未生成，或旧投影未提供解读。 为本投影生成报告 打开报告历史与生成工作区 →" in visible
    )
    assert not _find(
        section, lambda item: "查看报告详情" in _text(item) and getattr(item, "href", None)
    )
    assert "/reports?projection=projection-board" in [
        getattr(item, "href", None) for item in _find(section, lambda item: True)
    ]


def test_a_queued_report_task_is_stated_above_the_summary(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    projection = _gaps_projection([])
    runs = RunRepository(paths.database)
    runs.submit(
        command_type="report_generation",
        target_business_date="2026-09-30",
        client_request_id="reading-section-report",
        model_version_id=projection.envelope.model_version_id,
        system_as_of=CUTOFF,
        projection_set_id=projection.envelope.projection_set_id,
    )

    section = _reading(projection, runs=tuple(runs.list_runs(limit=-1, include_details=False)))
    visible = _words(_visible(section))

    assert "报告任务：排队" in visible and "完成后自动显示新版本" in visible
    assert "报告尚未生成，或旧投影未提供解读。" in visible


def test_the_release_calendar_opens_in_a_drawer_from_the_selected_projection() -> None:
    projection = replace(
        _gaps_projection([]),
        datasets={
            **_gaps_projection([]).datasets,
            "release_calendar": {
                "events": [{"release_event_family": "chinamoney_lpr", "period": "frozen-September"}]
            },
        },
    )

    section = _reading(projection, release_events=({"period": "live-October"},))
    panel = _panel(section, _trigger(section, "发布日历"))

    assert "chinamoney_lpr" in panel and "统计期 frozen-September" in panel
    assert "live-October" not in panel
    assert "projection-board" in panel
    assert "/data-chain?projection=projection-board" in [
        getattr(item, "href", None) for item in _find(section, lambda item: True)
    ]


def test_a_report_past_retention_keeps_its_identity_and_invents_no_reading() -> None:
    projection = _gaps_projection([])
    expired = replace(_template_report(projection, []), body_retained=False, body={})

    section = _reading(projection, reports=(expired,))
    visible = _words(_visible(section))

    assert "正文已不在保留期" in visible and "与阶段 V只差债券一项" not in _text(section)
    panel = _panel(section, _trigger(section, "查看报告详情"))
    assert "报告身份 report-projection-board-1" in panel


def _coverage_rows(section: Component) -> list[list[object]]:
    """Section 07's completeness rows, each cell as published (the counts are numbers)."""
    rows = _find(section, lambda item: type(item).__name__ == "Tr")
    return [
        [
            cell.children
            for cell in getattr(row, "children", [])
            if type(cell).__name__ in {"Th", "Td"}
        ]
        for row in rows
    ]


def test_the_gated_column_also_counts_periods_not_due_yet_and_says_why_no_gap() -> None:
    """Macro stage 15: a period later than the one due, the one held carried, is counted
    with the gated ones; the page says why the gap list does not name it. The total counts
    every period planned, those not due yet among them (review 2026-10-20 r2)."""
    coverage = {
        "available": True,
        "model": {"total": 1, "counts": {"held": 1}},
        "catalog": {"total": 4, "counts": {"held": 1, "release_gated": 2, "missing": 1}},
    }
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        macro={"coverage": coverage},
    )
    section = _reading(projection)

    assert _coverage_rows(section)[:3] == [
        ["口径", "计划期数", "已持有", "门禁 / 等待发布 / 未到应有期", "其他缺失"],
        ["模型所需", 1, 1, 0, 0],
        ["目录全部", 4, 1, 2, 1],
    ]
    assert (
        "晚于应有期、尚未持有的计划期还未到应有期（如已发布的下一期），计在门禁一列，不列为缺口；"
        "有已持有期的指标沿用其最新一期。"
    ) in _words(_visible(section))


def test_an_older_projection_shows_its_completeness_as_published() -> None:
    """A set published before macro stage 15 counted VIX 10-19 missing: shown as it is,
    never recounted on the reader's side."""
    vix = {"complete": False, "metric_id": "CBOE_VIX_INDEX", "required_period": "2026-10-19"}
    coverage = {
        "available": True,
        "model": {"total": 1, "counts": {"held": 1}, "periods": []},
        "catalog": {"total": 2, "counts": {"held": 1, "missing": 1}, "periods": [vix]},
    }
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        macro={"coverage": coverage},
    )
    section = _reading(projection)

    assert _coverage_rows(section)[2] == ["目录全部", 2, 1, 0, 1]
    assert "本次运行没有缺口。" in _words(_visible(section))
