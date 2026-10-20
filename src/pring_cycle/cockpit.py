"""The report reading surface. Every number comes from the supplied immutable set."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode

from dash import dcc, html

from pring_cycle import dashboard as view
from pring_cycle import macro_basis, macro_board
from pring_cycle.confirmation import OUTPUT_STRUCTURE as CONFIRMATION_STRUCTURE
from pring_cycle.domain.trend import TrendRules
from pring_cycle.drawer import drawer_key, drawer_panel, drawer_trigger, unique_key
from pring_cycle.macro_judgement import NOT_RECOMPUTED
from pring_cycle.page_identity import identity_fields
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.retrieval import RUN_SEARCH_LIMITS
from pring_cycle.run_health import REQUEST_FAILURES, ProducerRun
from pring_cycle.runs import RunRecord
from pring_cycle.wording import (
    _GDP_AGGREGATES,
    _GDP_MEASURES,
    CORE_STATE_LABELS,
    FORMAL_TERM,
    MACRO_BOARD_NOTES,
    MACRO_CONFIDENCES,
    MACRO_HISTORY_BLANKS,
    MACRO_JUDGEMENT,
    MACRO_NOT_RECOMPUTED,
    MACRO_SAME_SOURCE,
    MACRO_SIGNAL_LIST,
    NO_CHINESE_NAME,
    NO_MACRO_JUDGEMENT,
    NO_MEMBER_NAME,
    NONCANONICAL_NO_STAGE,
    PRICE_TERM,
    DisplayName,
    core_state_label,
    display_name,
    noncanonical_stage_change,
    reason_label,
    stage_code,
    stage_name,
)

SECTIONS = (
    ("conclusion", "周期识别结论"),
    ("assets", "三核心与同类资产"),
    ("overseas", "海外与汇率"),
    ("confirmation", "宏观事后确认"),
    ("inventory", "库存周期"),
    ("history", "周期说明与阶段史"),
    ("reading", "数据说明与解读"),
)
REASONS = {
    "insufficient_history": "不足完整 120 交易日回看",
    "window_session_missing": "窗口缺少实际交易日观测",
    "trading_calendar_incomplete": "交易日历未覆盖比较窗口",
    "carried_forward": "目标日沿用，缺少实际收盘端点",
    "zero_baseline": "比较基线为零",
    "source_missing": "尚未取得来源数据",
    "source_conflict": "来源冲突",
    "validated": "已通过校验",
    "carried_forward_one_session": "沿用上一交易日",
    "not_daily": "非日频指标，不适用交易日变化",
}
UNITS = {
    "index_points": "点",
    "percent": "%",
    "percentage_points": "百分点",
    "basis_points": "基点",
    "tonnes": "吨",
    "barrels": "桶",
    "diffusion_index_points": "扩散指数点",
    "hundred_million_cny": "亿元",
    "trillion_cny": "万亿元",
    "days": "天",
    "cny_per_usd": "元/美元",
    "usd_per_barrel": "美元/桶",
    "usd_per_troy_ounce": "美元/盎司",
    "count": "家",
    "multiple": "倍",
    "ratio": "比值",
}
# A metric whose source records a generic unit reads in its catalog unit: the 16:30 close
# parser stamps "scalar" on a CNY-per-USD quote.
METRIC_UNITS = {("CN_USDCNY_CLOSE_1630", "scalar"): "cny_per_usd"}


def row_name(row: dict[str, Any], *, fallback: object = None) -> DisplayName:
    """A projection row's display name, from its metric, member dimensions and catalog name.

    ``fallback`` is a Chinese group label the projection already carries, used before the code.
    """
    name = display_name(row.get("metric_id"), obj(row.get("dimensions")), row.get("name_cn"))
    return (
        name
        if name.provided or not fallback
        else replace(name, name=str(fallback), provided=True, group=True)
    )


def name_cell(name: DisplayName) -> Any:
    """The Chinese name alone for compact places; hovering shows the code."""
    return html.Span(name.name, title=name.code)


def name_note(name: DisplayName) -> list[Any]:
    """The drawer's note when the name fell back to the code or to the member's group."""
    note = NO_CHINESE_NAME if not name.provided else NO_MEMBER_NAME if name.group else None
    return [html.P(note, className="empty-note")] if note else []


def with_metric_unit(row: dict[str, Any]) -> dict[str, Any]:
    unit = METRIC_UNITS.get((str(row.get("metric_id")), str(row.get("unit"))))
    return {**row, "unit": unit} if unit else row


def objects(value: object) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, (list, tuple))
        else []
    )


def obj(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def number(value: object, unit: object = None) -> str:
    if value is None:
        return "—"
    # A count of companies (家) reads in whole numbers.
    places = 0 if unit == "count" else 2
    text = f"{value:,.{places}f}" if isinstance(value, (float, int)) else str(value)
    return text + (f" {UNITS.get(str(unit), str(unit))}" if unit else "")


def table(
    headers: Sequence[str], rows: Sequence[Sequence[Any]], *, class_name: str = "report-table"
) -> html.Div:
    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([html.Th(label, scope="col") for label in headers])),
                html.Tbody([html.Tr([html.Td(value) for value in row]) for row in rows]),
            ],
            className=class_name,
        ),
        className="table-scroll",
        tabIndex=0,
    )


def evidence_href(projection: ProjectionSet, version: str, *, section: str = "assets") -> str:
    return (
        "/data-chain?"
        + urlencode(
            {
                "projection": projection.envelope.projection_set_id,
                "version": version,
                "return": section,
            }
        )
        + "#evidence"
    )


def value_link(
    value: object,
    unit: object,
    version: object,
    projection: ProjectionSet | None,
    *,
    section: str = "assets",
) -> Any:
    label = number(value, unit)
    return (
        html.A(label, href=evidence_href(projection, str(version), section=section))
        if version and projection
        else label
    )


def chart(display: dict[str, Any], projection: ProjectionSet) -> Any:
    """A card's 120-session price and MA120 lines, without the chart toolbar."""
    points = objects(display.get("points"))
    if not points:
        return html.P("旧投影未提供展示点列；新运行发布后可用。", className="empty-note")
    dates = [item["date"] for item in points]
    # One level tick on each month's first session; nticks alone would not land on months.
    # The window opens mid-month, so its first month's tick would sit off its first session
    # and crowd the next month's; it shows only when the window holds a single month.
    months: dict[str, Any] = {}
    for date in dates:
        months.setdefault(str(date)[:7], date)
    if len(months) > 1:
        del months[next(iter(months))]
    links = [
        evidence_href(projection, str(item["selected_claim_id"]))
        if item.get("selected_claim_id")
        else None
        for item in points
    ]
    traces = [
        {
            "type": "scatter",
            "mode": "lines",
            "name": "实际价格",
            "x": dates,
            "y": [item.get("value") for item in points],
            "customdata": links,
            "connectgaps": False,
            "line": {"color": "#278a96", "width": 2},
            "hovertemplate": "%{x}<br>价格 %{y:.2f}<extra></extra>",
        },
        {
            "type": "scatter",
            "mode": "lines",
            "name": "MA120",
            "x": dates,
            "y": [item.get("ma120") for item in points],
            "connectgaps": False,
            "line": {"color": "#c58b42", "width": 1.5, "dash": "dot"},
            "hovertemplate": "%{x}<br>MA120 %{y:.2f}<extra></extra>",
        },
    ]
    missing = sorted({str(item["ma120_reason"]) for item in points if item.get("ma120_reason")})
    return html.Div(
        [
            dcc.Graph(
                figure={
                    "data": traces,
                    "layout": {
                        "height": 240,
                        "margin": {"l": 44, "r": 6, "t": 6, "b": 24},
                        "paper_bgcolor": "rgba(0,0,0,0)",
                        "plot_bgcolor": "rgba(0,0,0,0)",
                        "font": {"color": "#788c96", "size": 10},
                        "showlegend": False,
                        "xaxis": {
                            "type": "category",
                            "tickmode": "array",
                            "tickvals": list(months.values()),
                            "ticktext": list(months),
                            "tickangle": 0,
                            "gridcolor": "rgba(120,140,150,0.18)",
                        },
                        "yaxis": {"gridcolor": "rgba(120,140,150,0.18)", "zeroline": False},
                        "uirevision": projection.envelope.projection_set_id,
                    },
                },
                config={"displayModeBar": False, "responsive": True, "displaylogo": False},
                # Responsive mode sets height 100%, which a stretched grid or flex card
                # resolves against its track and collapses; the card's chart is 240px.
                style={"height": "240px"},
                className="price-chart card-chart",
            ),
            html.P(
                "实际价格（实线）与 MA120（虚线）· 120 个交易日；均线缺值："
                + ("、".join(REASONS.get(reason, reason) for reason in missing) or "无"),
                className="secondary-copy",
            ),
        ]
    )


def daily_panel(
    key: str, asset: dict[str, Any], display: dict[str, Any], projection: ProjectionSet
) -> Any:
    """The chart's equivalent table with each price's frozen evidence, and the noise band."""
    points = objects(display.get("points"))
    return drawer_panel(
        key,
        view._asset_label(str(asset.get("asset"))) + " · 逐日数值与证据",
        [
            html.P(
                "噪声带："
                + number(asset.get("noise_band_pct"), "percent")
                + "；MA120 仅在完整 120 个实际交易日价格齐备时显示。"
            ),
            table(
                ("交易日", "实际价格", "MA120", "不可得原因"),
                [
                    (
                        item["date"],
                        value_link(
                            item.get("value"),
                            display.get("unit"),
                            item.get("selected_claim_id"),
                            projection,
                        ),
                        number(item.get("ma120")),
                        REASONS.get(str(item.get("ma120_reason")), item.get("ma120_reason") or "—"),
                    )
                    for item in points
                ],
            )
            if points
            else html.P("旧投影未提供展示点列；新运行发布后可用。", className="empty-note"),
        ],
        code=str(asset.get("metric_id") or "") or None,
    )


def window_change(row: dict[str, Any], window: str) -> dict[str, Any]:
    """A row's change over ``window`` (``change_5`` / ``change_120``) as the page reads it.

    A count of companies reads as the difference in 家 between the window's two ends, taken
    from the projection's own points, never as the projection's percent return.
    """
    display = obj(row.get("display"))
    change = obj(display.get(window))
    if (display.get("unit") or row.get("unit")) != "count" or not change:
        return change
    values = {point.get("date"): point.get("value") for point in objects(display.get("points"))}
    if window == "change_120" and change.get("start_date") and change["start_date"] not in values:
        # The points hold 120 sessions, so the 120-day window's start is never among them.
        return {**change, "value": None, "reason": "count_window_outside_points"}
    start, end = values.get(change.get("start_date")), values.get(change.get("end_date"))
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return {**change, "value": None, "reason": change.get("reason") or "window_session_missing"}
    return {**change, "value": end - start, "kind": "difference", "unit": "count"}


def change_number(change: dict[str, Any]) -> str:
    """A change's value with its unit; a difference in 家 carries its sign."""
    text = number(change["value"], change.get("unit"))
    return "+" + text if change.get("unit") == "count" and change["value"] > 0 else text


def missing_note(change: dict[str, Any]) -> str | None:
    """The sessions a change's window lacks, as 缺 MM-DD、MM-DD (a long list cut short)."""
    days = [str(day)[5:] for day in change.get("missing_dates") or () if day]
    if not days:
        return None
    return "缺 " + "、".join(days[:5]) + (f" 等 {len(days)} 日" if len(days) > 5 else "")


def change_cell(value: object) -> Any:
    change = obj(value)
    if change.get("value") is None:
        reason = str(change.get("reason") or "旧投影未提供")
        note = missing_note(change)
        return html.Span(
            f"—（{note}）" if note else "—", title=REASONS.get(reason) or reason_label(reason)
        )
    return html.Span(
        change_number(change),
        title=f"{change.get('start_date')} → {change.get('end_date')}",
    )


def state_tag(value: object) -> html.Span:
    """A core asset state as a 牛市 / 熊市 tag in the board's up / down state colours."""
    label = core_state_label(value)
    tone = {"牛市": "up", "熊市": "down"}.get(label, "warning")
    return html.Span(label, className=f"state-tag state-{tone}")


def asset_candidate(asset: dict[str, Any]) -> str:
    """The asset candidate with its duration and threshold; a missing one is never a zero."""
    candidate = asset.get("candidate_state")
    if not candidate:
        return "无"
    days = asset.get("candidate_days")
    threshold = asset.get("persistence_required")
    return (
        f"{core_state_label(candidate)} · "
        f"持续 {'未提供' if days is None else f'{days} 日'} / "
        f"门槛 {'未提供' if threshold is None else f'{threshold} 日'}"
    )


def candidate_cell(asset: dict[str, Any]) -> html.Div:
    """The 30-day direction and the asset candidate on two lines, never one merged duration."""
    direction = asset.get("candidate_30d")
    return html.Div(
        [
            html.Div("30 日候选方向 " + (core_state_label(direction) if direction else "无")),
            html.Div("资产候选状态 " + asset_candidate(asset)),
        ]
    )


def asset_cards(
    projection: ProjectionSet | None,
    macro: dict[str, object],
    trend_rules: TrendRules | None = None,
) -> Any:
    """Bond, stock and commodity side by side: each card heads with the asset's core reading,
    then its 120-session chart and its observations; details open in the drawer."""
    if projection is None:
        return html.P("等待首次完整运行。", className="empty-note")
    dataset = projection.datasets["core_assets"]
    displays = obj(dataset.get("display"))
    assets = sorted(
        objects(dataset.get("assets")),
        key=lambda item: (
            CORE_ORDER.index(item["asset"]) if item.get("asset") in CORE_ORDER else len(CORE_ORDER)
        ),
    )
    cards = []
    panels = []
    for asset in assets:
        name = str(asset.get("asset"))
        display = obj(displays.get(name))
        latest = next(
            (
                point
                for point in reversed(objects(display.get("points")))
                if point.get("value") is not None
            ),
            {},
        )
        daily = drawer_key("assets", name, "daily")
        observations, observation_panels = related_assets(macro, name, projection)
        cards.append(
            html.Article(
                [
                    html.Header(
                        [
                            html.Div(
                                [
                                    html.Strong(view._asset_label(name)),
                                    html.Small(str(asset.get("metric_id") or "")),
                                    state_tag(asset.get("state")),
                                ],
                                className="core-card-title",
                            ),
                            html.Div(
                                [
                                    value_link(
                                        display.get("latest_value"),
                                        display.get("unit"),
                                        latest.get("selected_claim_id"),
                                        projection,
                                    ),
                                    html.Small(str(display.get("latest_date") or "旧投影未提供")),
                                ],
                                className="card-value",
                            ),
                            _facts(
                                (
                                    f"距 MA{trend_rules.window_days}" if trend_rules else "距均线",
                                    number(asset.get("distance_pct"), "percent"),
                                ),
                                (
                                    f"{trend_rules.slope_days} 日斜率" if trend_rules else "斜率",
                                    number(asset.get("slope_pct"), "percent"),
                                ),
                            ),
                            candidate_cell(asset),
                            _facts(
                                ("近 5 日", change_cell(display.get("change_5"))),
                                ("近 120 日", change_cell(display.get("change_120"))),
                            ),
                            drawer_trigger(daily, "逐日数值与证据", class_name="card-button"),
                        ],
                        className="core-card-head",
                    ),
                    chart(display, projection),
                    html.H3("同类观察"),
                    html.Div(observations, className="card-observations"),
                ],
                id="asset-" + name,
                className=f"core-card core-{name}",
            )
        )
        panels += [daily_panel(daily, asset, display, projection), *observation_panels]
    # Panels sit outside the cards so the drawer is fixed to the viewport.
    return html.Div([html.Div(cards, className="core-cards"), *panels])


def _facts(*pairs: tuple[str, Any]) -> html.Dl:
    return html.Dl(
        [part for label, value in pairs for part in (html.Dt(label), html.Dd(value))],
        className="card-facts",
    )


def report_board(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
    stage_events: Sequence[dict[str, object]] = (),
    release_events: Sequence[dict[str, object]] = (),
    *,
    producer_run: ProducerRun | None = None,
    trend_rules: TrendRules | None = None,
) -> html.Div:
    """``producer_run`` carries the producing run's persisted health summary for the board's
    run facts; ``None`` (or a ``None`` summary) means the page must say it is unavailable."""
    overview = view._dataset(projection, "cycle_overview")
    macro = view._dataset(projection, "macro")
    confirmation = obj(macro.get("confirmation"))
    matching = [
        report
        for report in reports
        if projection and report.projection_set_id == projection.envelope.projection_set_id
    ]
    report = max(matching, key=lambda item: item.version) if matching else None
    report_run = next(
        (
            item
            for item in runs
            if projection
            and item.projection_set_id == projection.envelope.projection_set_id
            and (
                item.command_type == "report_generation" or item.current_step == "generating_report"
            )
        ),
        None,
    )
    report_pending = report_run is not None and report_run.status in {"queued", "running"}
    pinned = (
        "?" + urlencode({"projection": projection.envelope.projection_set_id}) if projection else ""
    )
    bodies: list[list[Any]] = [
        [
            html.Div(
                [
                    conclusion_left(projection, trend_rules),
                    conclusion_right(projection),
                ],
                className="conclusion-board",
            ),
            gaps_drawer(projection),
            price_verification_drawer(projection, trend_rules),
            html.P(
                ["解读：", *reading_line(report, pinned, pending=report_pending)]
                if projection
                else ["解读：报告尚未生成"],
                className="board-fact",
            ),
            html.P(
                "运行事实：" + run_facts_line(producer_run.summary if producer_run else None),
                className="board-fact",
            ),
            html.A("查看运行摘要与数据边界 →", href="/runs" + pinned),
            html.P(html.A("三核心详见 ② →", href=pinned + "#assets")),
        ],
        [
            asset_cards(projection, macro, trend_rules),
            *asset_notes(macro, macro_board.judgement(view._dataset(projection, "cycle_overview"))),
            *view._supply_demand_sections(macro),
        ],
        [overseas_cards(macro, projection)],
        macro_basis_section(judgement, confirmation, macro, projection)
        if (judgement := macro_board.judgement(overview)) is not None
        else [
            html.P(view._confirmation_scope(confirmation)),
            confirmation_cards(confirmation, macro, projection),
        ]
        if confirmation
        else [confirmation_cards(confirmation, macro, projection)]
        if projection is None
        else [view._macro_page(projection)],
        inventory_section(confirmation, projection),
        [
            *stage_history(projection, stage_events),
            html.A("本投影解读 →", href=pinned + "#reading"),
        ],
        [
            html.H3("完整度与缺期"),
            # A set published before coverage was projected cannot show it (ticket 13).
            coverage_table(
                obj(macro.get("coverage")), "两种完整度口径：该投影生成时尚未提供此统计。"
            ),
            *view._freshness_basis(projection),
            *(gap_preview(overview.get("gap_list")) if projection else [html.P("尚无分析投影。")]),
            html.P(
                [
                    drawer_trigger(drawer_key("reading", "calendar"), "发布日历"),
                    " · ",
                    html.A("数据链路与证据", href="/data-chain" + pinned),
                ]
            ),
            drawer_panel(
                drawer_key("reading", "calendar"),
                "发布日历",
                view._release_calendar_body(projection, release_events),
            ),
            html.H3("本投影解读"),
            html.P(
                "报告任务："
                + view._state_label(report_run.status)
                + " · "
                + view._state_label(report_run.current_step)
                + ("；完成后自动显示新版本。" if report_pending else "")
            )
            if report_run
            else None,
            *report_summary(report, pinned),
            html.Button(
                "为本投影生成报告",
                id="generate-report-command",
                type="button",
                className="quiet-button",
                disabled=projection is None or report_pending,
                **cast(
                    Any,
                    {
                        "data-projection-id": projection.envelope.projection_set_id
                        if projection
                        else ""
                    },
                ),
            ),
            html.A("打开报告历史与生成工作区 →", href="/reports" + pinned),
        ],
    ]
    sections = section_titles(macro_board.judgement(overview))
    return html.Div(
        [
            html.Nav(
                [
                    html.A([html.Span(f"{index:02d}"), title], href=pinned + "#" + key)
                    for index, (key, title) in enumerate(sections, 1)
                ],
                className="report-toc",
                **cast(Any, {"aria-label": "报告目录"}),
            ),
            html.Div(
                [
                    html.Section(
                        [
                            html.Header(
                                [
                                    html.H2(f"{index:02d} {title}"),
                                    html.P(
                                        MACRO_BOARD_SUBTITLE
                                        if stage_term(projection) == PRICE_TERM
                                        else BOARD_SUBTITLE,
                                        className="report-subtitle",
                                    )
                                    if key == "conclusion"
                                    else None,
                                ],
                                className="report-heading",
                            ),
                            *body,
                        ],
                        id=key,
                        className="report-section",
                    )
                    for index, ((key, title), body) in enumerate(
                        zip(sections, bodies, strict=True), 1
                    )
                ],
                className="report-body",
            ),
        ],
        className="report-layout",
    )


def section_titles(judgement: Mapping[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """The sections by their titles: under a judgement 04 is its basis (macro stage ticket
    07); an older set's 04 keeps its name."""
    if judgement is None:
        return SECTIONS
    return tuple(
        (key, macro_basis.TITLE if key == "confirmation" else title) for key, title in SECTIONS
    )


BOARD_SUBTITLE = "正式阶段 · 三核心 · 确认度 · 一致性 · 库存 · 归因，一板看完"
MACRO_BOARD_SUBTITLE = "五维定宏观阶段 · 价格表象作验证 · 库存 · 归因，一板看完"


def stage_term(projection: ProjectionSet | None) -> str:
    """What the page calls the cores' own stage: the price stage once the macro judgement
    leads the set (ADR-0043, GLOSSARY: 价格阶段), the formal stage on an older set."""
    overview = view._dataset(projection, "cycle_overview")
    return PRICE_TERM if macro_board.judgement(overview) is not None else FORMAL_TERM


CORE_ORDER = ("bond", "stock", "commodity")
CORE_NAMES = {"bond": "债券", "stock": "股票", "commodity": "商品"}
# A blocked stage reason, named before the board lists each core (spec: reason line).
BLOCKED_REASONS = {
    "core_data_pending": "核心数据待处理",
    "core_state_unavailable": "核心状态不可用",
    "p0_unavailable": "P0 未过门禁",
}
CORE_READABLE = {"validated", "carried_forward_one_session"}


def conclusion_left(projection: ProjectionSet | None, trend_rules: TrendRules | None) -> Any:
    """The board's left column: the formal stage and the five rows a reader checks it by."""
    overview = view._dataset(projection, "cycle_overview")
    if (judgement := macro_board.judgement(overview)) is not None:
        # The macro judgement heads the board; the price stage verifies it in one row, its
        # own rows in that row's drawer (ADR-0043, macro stage tickets 02, 06).
        return macro_board.conclusion_left(judgement)
    rows = price_stage_rows(
        projection,
        trend_rules,
        one_asset_difference_line(overview),
        watch=transition_watch_line(projection),
    )
    return html.Div(
        [
            html.P("正式阶段", className="section-kicker"),
            html.H2(view._stage_label(overview.get("current_stage")), className="stage-value"),
            # An older set is shown as it was: no judgement is made on the page.
            *([html.P(NO_MACRO_JUDGEMENT, className="empty-note")] if projection else []),
            html.Dl(
                [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
                className="board-rows",
            ),
        ],
        className="board-left",
    )


def price_stage_rows(
    projection: ProjectionSet | None,
    trend_rules: TrendRules | None,
    difference: list[html.Div] | None,
    *,
    watch: str | None = None,
) -> tuple[tuple[str, Any], ...]:
    """The rows a reader checks the price stage by: its reason, the one-asset ``difference``
    when there is one, the last confirmed stage, an older set's turn ``watch``, the cores
    carried forward and the method."""
    overview = view._dataset(projection, "cycle_overview")
    lookback = overview.get("last_confirmed_lookback")
    last_confirmed = overview.get("last_confirmed_stage")
    return (
        ("原因", stage_reason_line(projection)),
        *((("只差一项", difference),) if difference else ()),
        (
            "上次确认",
            view._last_confirmed_label(last_confirmed, lookback)
            if last_confirmed is not None or isinstance(lookback, dict)
            # A set without a lookback record never says none (spec: 不回填).
            else ("无" if projection is None else "未提供"),
        ),
        *((("转折观察", watch),) if watch is not None else ()),
        ("核心沿用", carry_forward_line(projection)),
        ("判法", method_line(projection, trend_rules)),
    )


def price_verification_drawer(
    projection: ProjectionSet | None, trend_rules: TrendRules | None
) -> Any:
    """The price verification row's drawer (macro stage ticket 06): the price stage's rows,
    the one-asset comparisons the verification carries and, with a price stage only, the
    confirmation, counted against that stage (decision 11). None for an older set."""
    judgement = macro_board.judgement(view._dataset(projection, "cycle_overview"))
    if judgement is None:
        return None
    verification = obj(judgement.get("price_verification"))
    rows = price_stage_rows(
        projection,
        trend_rules,
        one_asset_difference_rows(objects(verification.get("comparisons"))),
    )
    confirmation = obj(view._dataset(projection, "macro").get("confirmation"))
    stage = verification.get("price_stage")
    applicable = bool(obj(confirmation.get("summary")).get("applicable"))
    if stage is None:
        # 04 points here for the confirmation: with no price stage, say why there is none.
        counted: list[Any] = [html.H3("确认度"), html.P(NO_PRICE_STAGE_CONFIRMATION)]
    elif confirmation:
        counted = [
            html.H3(f"确认度（对价格阶段{stage_name(stage)}）"),
            html.P(confirmation_heading(confirmation, term=PRICE_TERM)),
            html.Div(
                [
                    dimension_cell(item, applicable=applicable)
                    for item in objects(confirmation.get("dimensions"))
                ],
                className="confirmation-summary",
            ),
        ]
    else:
        counted = []
    return macro_board.verification_panel(judgement, rows, counted)


NO_PRICE_STAGE_CONFIRMATION = "无价格阶段，确认度不适用：确认度只对价格阶段计算"


def _cores(projection: ProjectionSet | None) -> dict[str, dict[str, Any]]:
    assets = objects(view._dataset(projection, "core_assets").get("assets"))
    return {str(item.get("asset")): item for item in assets}


def _core_gaps(overview: dict[str, object]) -> dict[str, dict[str, Any]]:
    return {str(item.get("metric_id")): item for item in objects(overview.get("gap_list"))}


def _carried(overview: dict[str, object]) -> list[str]:
    value = overview.get("core_carry_forward")
    return [str(item) for item in value] if isinstance(value, list) else []


def _held(core: dict[str, Any], gaps: dict[str, dict[str, Any]]) -> str:
    """The period a core holds: its gap entry's, else its own latest business date."""
    gap = gaps.get(str(core.get("metric_id")), {})
    return str(gap.get("held_period") or core.get("latest_business_date") or "未提供")


def _combination(cores: dict[str, dict[str, Any]]) -> str:
    return " · ".join(
        CORE_NAMES[asset] + core_state_label(cores.get(asset, {}).get("state"))
        for asset in CORE_ORDER
    )


def is_noncanonical(projection: ProjectionSet | None) -> bool:
    """Whether the stage is empty because the three cores form a noncanonical combination."""
    overview = view._dataset(projection, "cycle_overview")
    reason = overview.get("stage_reason") or overview.get("stage_unavailable_reason")
    return reason == "noncanonical_combination"


def stage_reason_line(projection: ProjectionSet | None) -> str | list[Any]:
    """Why the board shows this stage, in the three cores' own states (spec: reason line)."""
    overview = view._dataset(projection, "cycle_overview")
    cores = _cores(projection)
    stage = overview.get("current_stage")
    if stage is not None:
        return f"典型组合：{_combination(cores)} → {stage_code(stage)}"
    reason = overview.get("stage_reason") or overview.get("stage_unavailable_reason")
    if reason == "noncanonical_combination":
        return [
            html.Strong("非典型组合"),
            f"：{_combination(cores)}，不在六个典型组合内；不创建 Stage VII/VIII",
        ]
    if reason in BLOCKED_REASONS:
        gaps = _core_gaps(overview)
        carried = set(_carried(overview))
        readings = [
            _core_reading(asset, cores.get(asset, {}), gaps, carried) for asset in CORE_ORDER
        ]
        return f"{BLOCKED_REASONS[str(reason)]}：" + " · ".join(readings)
    return view._stage_explanation(overview)


def one_asset_difference_line(overview: dict[str, object]) -> list[html.Div] | None:
    """Each typical stage the noncanonical combination misses by one asset, one per line, as
    the Worker published it; an older set without that basis shows no row and none is
    derived here."""
    return one_asset_difference_rows(
        objects(obj(overview.get("noncanonical_basis")).get("comparisons"))
    )


def one_asset_difference_rows(comparisons: list[dict[str, Any]]) -> list[html.Div] | None:
    """Each published one-asset comparison in one line; none without one."""
    if not comparisons:
        return None
    return [
        html.Div(
            f"{stage_code(item.get('stage'))} "
            f"差{CORE_NAMES.get(str(item.get('asset')), '未知资产')}："
            f"当前{core_state_label(item.get('current_state'))} → "
            f"要求{core_state_label(item.get('required_state'))}，30 日候选"
            + (core_state_label(item.get("candidate_30d")) if item.get("candidate_30d") else "无")
        )
        for item in comparisons
    ]


def transition_watch_line(projection: ProjectionSet | None) -> str:
    """Each core whose 30-day candidate points against its state, with its asset candidate;
    it never changes the formal stage, and no direction is no turn (GLOSSARY: 转折观察,
    30 日候选方向, 资产候选状态)."""
    published = view._dataset(projection, "cycle_overview").get("transition_watch")
    if isinstance(published, list) and published:
        return view._transition_watch(published) + " · 只作观察，不改变正式阶段"
    cores = _cores(projection)
    watched = []
    for asset in CORE_ORDER:
        core = cores.get(asset)
        if core is None or core.get("state") is None:
            continue
        direction = core.get("candidate_30d")
        if direction is None or direction == core.get("state"):
            continue
        signs = [
            f"30 日候选方向{core_state_label(direction)}，"
            f"与当前{core_state_label(core.get('state'))}相反"
        ]
        if core.get("candidate_state") is not None:
            signs.append("资产候选状态" + asset_candidate(core))
        watched.append(f"{CORE_NAMES[asset]} " + "；".join(signs))
    if watched:
        return "；".join(watched) + " · 只作观察，不改变正式阶段"
    unread = [
        CORE_NAMES[asset] for asset in CORE_ORDER if cores.get(asset, {}).get("state") is None
    ]
    if not unread:
        return "无（三核心 30 日候选均未与当前状态反向）"
    if len(unread) == len(CORE_ORDER):
        return "无（三核心尚无可用状态）"
    return "无（" + "、".join(unread) + "状态不可用；其余核心 30 日候选未与当前状态反向）"


def carry_forward_line(projection: ProjectionSet | None) -> str:
    """The cores priced at their previous session, each with the period it holds."""
    overview = view._dataset(projection, "cycle_overview")
    carried = _carried(overview)
    if not carried:
        return "无"
    cores, gaps = _cores(projection), _core_gaps(overview)
    return "、".join(
        f"{CORE_NAMES.get(asset, asset)}（沿用期 {_held(cores.get(asset, {}), gaps)}）"
        for asset in carried
    )


def method_line(projection: ProjectionSet | None, trend_rules: TrendRules | None) -> str:
    """How the stage is judged, in the trend rules frozen in the projection's model."""
    if projection is None:
        return "等待首次完整运行"
    model = projection.envelope.model_version_id
    if trend_rules is None:
        return f"该模型版本未提供趋势规则参数 · {model}"
    # Under the judgement the macro leads and the price stage verifies it (ADR-0043).
    macro = (
        "宏观判断为主结论，价格阶段作验证"
        if stage_term(projection) == PRICE_TERM
        else "宏观与库存只做事后确认，不改写阶段"
    )
    return (
        f"MA{trend_rules.window_days} + {trend_rules.slope_days} 日斜率定稳定牛熊，"
        f"噪声带 {trend_rules.noise_multiplier:g}×{trend_rules.volatility_days} 日波动，"
        f"持续 {trend_rules.persistence_days} 日确认，"
        f"{trend_rules.candidate_window_days} 日候选只作转折观察；{macro} · {model}"
    )


def _core_reading(
    asset: str,
    core: dict[str, Any],
    gaps: dict[str, dict[str, Any]],
    carried: set[str],
) -> str:
    """A core's state when it was read; else what blocked it, as its records say."""
    name = CORE_NAMES[asset]
    gap = gaps.get(str(core.get("metric_id")), {})
    if core.get("state") is not None and core.get("reason") in CORE_READABLE:
        reading = name + core_state_label(core.get("state"))
        if core.get("carried_forward") or asset in carried:
            reading += f"（核心沿用，沿用期 {_held(core, gaps)}）"
        return reading
    if gap.get("periods_behind"):
        return f"{name}受阻：落后 {gap['periods_behind']} 期，沿用期 {_held(core, gaps)}"
    if gap:
        category = str(gap.get("category"))
        cause = view.GAP_CATEGORY_LABELS.get(category, category)
    else:
        reason = str(core.get("reason") or "未记录原因")
        cause = REASONS.get(reason) or view.CORE_GAP_REASON_LABELS.get(reason, reason)
    latest = core.get("latest_business_date")
    return f"{name}受阻：{cause}" + (f"，最新 {latest}" if latest else "")


RELATION_COUNTED = ("support", "counterevidence", "observation_only", "unconfirmed")
# A cell's counts abbreviated so it never wraps; the full names stay on hover.
RELATION_SHORT = {
    "support": "支",
    "counterevidence": "反",
    "observation_only": "观",
    "unconfirmed": "未",
}
LEGACY_MACRO_STATES = ("policy_direction", "credit_response", "overheat_state", "price_pressure")


def confirmation_heading(confirmation: dict[str, Any], *, term: str = FORMAL_TERM) -> str:
    """Whether the confirmation is assessed, over how many key indicators, by which rules;
    ``term`` is what the page calls the stage it is assessed against."""
    summary = obj(confirmation.get("summary"))
    if not summary:
        return "该版本未提供确认汇总"
    rules = confirmation.get("macro_rules_version") or "版本未提供"
    if summary.get("applicable"):
        return f"可评估 · {summary.get('total')} 项关键指标 · 规则 {rules}"
    return f"不适用 · {summary.get('total')} 项关键指标 · 无{term}，不计数 · 规则 {rules}"


def _dimension_total(dimension: dict[str, Any]) -> int | None:
    """A connected dimension's key indicators; ``None`` while it is not connected."""
    counts = obj(dimension.get("counts"))
    if dimension.get("status") != "connected" or not counts:
        return None
    return len(objects(dimension.get("key_indicators"))) or sum(
        view._integer(value) for value in counts.values()
    )


def dimension_cell(dimension: dict[str, Any], *, applicable: bool) -> html.Div:
    """A dimension's key indicators and their relations; never a probability."""
    label = view._DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")
    counts = obj(dimension.get("counts"))
    total = _dimension_total(dimension)
    if total is None:
        return html.Div([html.Strong(label), html.Span("尚未接入")], className="summary-cell")

    def counted(labels: dict[str, str]) -> str:
        return " · ".join(
            f"{labels[relation]} {view._integer(counts.get(relation))}"
            for relation in RELATION_COUNTED
        )

    return html.Div(
        [
            html.Strong(label),
            html.Span(f"{total} 项" + ("" if applicable else " · 不适用")),
            html.Span(counted(RELATION_SHORT), title=counted(view._RELATION_LABELS)),
        ],
        className="summary-cell",
    )


def dimension_totals_line(dimensions: list[dict[str, Any]]) -> str:
    """A noncanonical combination's dimensions in one line: how many key indicators each
    holds, none counted since no stage narrative is there to compare against."""
    totals = [
        view._DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")
        + (" 尚未接入" if (total := _dimension_total(dimension)) is None else f" {total} 项")
        for dimension in dimensions
    ]
    return " · ".join([*totals, "非典型组合无阶段叙事可比对，不计数"])


def price_consistency_line(consistency: dict[str, Any]) -> str | list[Any]:
    """The three pairs' relative momentum, then the stock and basket breadth, in one line;
    each value read is set in bold."""
    if not consistency:
        return "该版本未提供"
    pairs: list[Any] = []
    for pair in objects(consistency.get("relative_momentum")):
        pairs += [" · "] if pairs else []
        value = pair.get("value_pp")
        pairs += (
            [f"{pair.get('label')} ", html.Strong(f"{value:+.2f} 个百分点")]
            if isinstance(value, (int, float))
            else [f"{pair.get('label')} 未确认"]
        )
    breadths: list[list[Any]] = []
    for key in ("stock_breadth", "basket_breadth"):
        item = obj(consistency.get(key))
        if not item:
            continue
        if not item.get("text"):
            missing = "、".join(str(gap) for gap in view._list_of(item.get("missing")))
            breadths.append([f"{item.get('label')} 未确认，缺：{missing or '未记录'}"])
        elif key == "stock_breadth" and isinstance(item.get("share"), (int, float)):
            breadths.append(
                [
                    f"{item.get('label')} ",
                    html.Strong(f"{item['share']:.1f}%"),
                    f"（{item['text']}）",
                ]
            )
        elif key == "basket_breadth" and item.get("along") is not None:
            breadths.append(
                [
                    f"{item.get('label')} ",
                    html.Strong(f"{item['along']}/{item.get('of')}"),
                    f" 个分项同向（{item['text']}）",
                ]
            )
        else:
            breadths.append([f"{item.get('label')} {item['text']}"])
    parts = [part for part in (pairs, *breadths) if part]
    return _merged(
        [piece for index, part in enumerate(parts) for piece in (["；"] if index else []) + part]
    )


def _merged(pieces: list[Any]) -> list[Any]:
    """Adjacent strings as one, so a line reads as one sentence around its bold values."""
    merged: list[Any] = []
    for piece in pieces:
        if isinstance(piece, str) and merged and isinstance(merged[-1], str):
            merged[-1] += piece
        else:
            merged.append(piece)
    return merged


def asset_notes(macro: dict[str, object], judgement: Mapping[str, Any] | None = None) -> list[Any]:
    """Below the cards, side by side: the cores' price internal consistency and the bond's
    attribution, each its core line on the page and its details in the drawer."""
    notes = [
        note
        for note in (
            consistency_card(obj(macro.get("price_consistency")), judgement),
            attribution_card(obj(macro.get("bond_attribution"))),
        )
        if note
    ]
    if not notes:
        return []
    # Panels sit outside the cards so the drawer is fixed to the viewport.
    return [
        html.Div([card for card, _panel in notes], className="asset-notes"),
        *(panel for _card, panel in notes),
    ]


def _note_card(name: str, title: str, line: Any, details: list[Any]) -> tuple[Any, Any]:
    key = drawer_key("assets", name)
    return (
        html.Div(
            [html.H3(title), html.P(line), drawer_trigger(key, "查看明细 →")],
            id="asset-" + name,
            className="note-card",
        ),
        drawer_panel(key, title, details),
    )


def consistency_card(
    consistency: dict[str, Any], judgement: Mapping[str, Any] | None = None
) -> tuple[Any, Any] | None:
    """The cores' price internal consistency: its line, details in the drawer. A set with a
    macro judgement says it is of the cores' own source and points to its signals in the
    01 list (macro stage ticket 04)."""
    if not consistency:
        return None
    if judgement is None:
        return _note_card(
            "consistency",
            "价格内部一致性（不计数）",
            price_consistency_line(consistency),
            [html.Ul([html.Li(line) for line in view._consistency_lines(consistency)])],
        )
    card, panel = _note_card(
        "consistency",
        f"价格内部一致性（{MACRO_SAME_SOURCE}）",
        price_consistency_line(consistency),
        [html.Ul([html.Li(line) for line in view._consistency_lines(consistency)])],
    )
    card.children.insert(
        2,
        signal_pointers(
            judgement, {"relative_momentum", "stock_breadth", "basket_breadth"}, empty=True
        ),
    )
    return card, panel


def signal_pointers(
    judgement: Mapping[str, Any],
    sources: set[str],
    *,
    empty: bool = False,
    asset: str | None = None,
) -> Any:
    """见 01 信号清单：each listed signal of ``sources`` (of ``asset``'s turn, if given),
    linked to its entry; with none, that none is listed, or nothing."""
    listed = [
        item
        for item in objects(judgement.get("signals"))
        if item.get("source") in sources
        and (asset is None or obj(item.get("asset_turn")).get("asset") == asset)
    ]
    if not listed:
        return html.P(f"01 {MACRO_SIGNAL_LIST}当日未列此类信号") if empty else None
    links: list[Any] = [f"见 01 {MACRO_SIGNAL_LIST}："]
    for index, item in enumerate(listed):
        links += (["、"] if index else []) + [
            html.A(macro_board.pointer(item), href=macro_board.signal_anchor(item))
        ]
    return html.P(links, className="signal-pointers")


def attribution_card(note: dict[str, Any]) -> tuple[Any, Any] | None:
    """What drives the bond: the driver with the bond's price and each axis on the page;
    why it is unclear, the signals read and the notes in the drawer."""
    lines = view._attribution_lines({"bond_attribution": note})
    if not lines:
        return None
    return _note_card(
        "attribution",
        "债券归因（不计数）",
        lines[0],
        [html.P(line) for line in lines],
    )


UNCLASSIFIED_BY = {"insufficient": "三条线缺数或月份不齐", "inconsistent": "三条线方向不构成象限"}


def inventory_quadrant_line(
    confirmation: dict[str, Any], inventory: dict[str, object]
) -> str | list[Any]:
    """The quadrant with its statistical period and the three lines' directions, or why it
    is unclassified; read from the confirmation's quadrant member, else the inventory set."""
    member = next(
        (
            member
            for dimension in objects(confirmation.get("dimensions"))
            if dimension.get("dimension") == "inventory"
            for item in objects(dimension.get("key_indicators"))
            for member in objects(item.get("members"))
            if "quadrant" in member
        ),
        dict(inventory),
    )
    if not member.get("quadrant"):
        return "该版本未提供"
    period = member.get("period") or member.get("statistical_period") or "未提供"
    parts = [f"统计期 {period}"]
    because = UNCLASSIFIED_BY.get(str(member.get("unclassified_by")))
    if because:
        parts.append(f"未分类原因：{because}")
    lines = obj(member.get("lines"))
    if lines:
        parts.append(
            "、".join(
                label
                + view._DIRECTION_LABELS.get(str(obj(lines.get(line)).get("direction")), "方向未知")
                for line, label in view._LINE_LABELS.items()
            )
        )
    quadrant = view._QUADRANT_LABELS.get(str(member.get("quadrant")), "未分类")
    return [html.Strong(quadrant), "（" + "；".join(parts) + "）"]


def bond_attribution_line(note: dict[str, Any]) -> str:
    """What drives the bond, by each axis's reading; a note beside it, never counted."""
    if not note:
        return "该版本未提供"
    axes = "、".join(f"{axis.get('label')}{axis.get('text')}" for axis in objects(note.get("axes")))
    return f"{note.get('text')}" + (f"：{axes}" if axes else "") + "（附注，不计数）"


GAPS_DRAWER = drawer_key("gaps")


def gaps_drawer(projection: ProjectionSet | None) -> Any:
    """The full gap list in one drawer, opened from the data boundary row and from section
    07; none when no gap."""
    gaps = view._document_list(view._dataset(projection, "cycle_overview").get("gap_list"))
    if not gaps:
        return None
    return drawer_panel(GAPS_DRAWER, f"全部缺口（{len(gaps)}）", [view._gap_list(gaps)])


def data_boundary_line(gaps: object, coverage: dict[str, Any], pinned: str) -> list[Any]:
    """The gap list's size and the final plan's model metric-periods not held, with the
    way on to section 07 and the data chain. A metric awaiting release is no gap: it is
    counted apart (worker gaps 03)."""
    missing: list[Any] = (
        [
            html.Strong(
                str(view._integer(obj(obj(coverage.get("model")).get("counts")).get("missing")))
            ),
            " 个历史期未取到（最终计划，模型所需口径）",
        ]
        if coverage.get("available")
        else ["历史期未取到：该版本未提供"]
    )
    awaiting = sum(item.get("category") == "awaiting_release" for item in objects(gaps))
    count = f"{len(objects(gaps)) - awaiting} 项缺口" + (
        f"（另 {awaiting} 项等待发布）" if awaiting else ""
    )
    return [
        drawer_trigger(GAPS_DRAWER, count) if objects(gaps) else count,
        " · ",
        *missing,
        " · 详见 ",
        html.A("⑦ 数据说明", href=pinned + "#reading"),
        " · ",
        html.A("数据链路", href="/data-chain" + pinned),
    ]


def conclusion_right(projection: ProjectionSet | None) -> Any:
    """The board's right column: the confirmation over the five dimensions, then the
    notes a reader sets against the stage, each in one line."""
    if projection is None:
        return html.Div(
            [html.P("确认度", className="section-kicker"), html.H3("等待首次完整运行")],
            className="board-right",
        )
    macro = view._dataset(projection, "macro")
    confirmation = obj(macro.get("confirmation"))
    applicable = bool(obj(confirmation.get("summary")).get("applicable"))
    noncanonical = is_noncanonical(projection)
    judgement = macro_board.judgement(view._dataset(projection, "cycle_overview"))
    attribution = obj(macro.get("bond_attribution"))
    apart = macro_board.bond_policy_apart(judgement, attribution) if judgement else None
    rows: tuple[tuple[str, Any], ...] = (
        ("价格一致性", price_consistency_line(obj(macro.get("price_consistency")))),
        (
            "库存象限",
            inventory_quadrant_line(confirmation, view._dataset(projection, "inventory")),
        ),
        ("债券归因", bond_attribution_line(attribution) + (f"；{apart}" if apart else "")),
        (
            "数据边界",
            data_boundary_line(
                view._dataset(projection, "cycle_overview").get("gap_list"),
                obj(macro.get("coverage")),
                "?" + urlencode({"projection": projection.envelope.projection_set_id}),
            ),
        ),
    )
    listed = html.Dl(
        [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
        className="board-rows",
    )
    if judgement is not None:
        # The confirmation is read in the price verification drawer (decision 11).
        return html.Div(
            [html.P(MACRO_BOARD_NOTES, className="section-kicker"), listed],
            className="board-right",
        )
    return html.Div(
        [
            html.P("确认度", className="section-kicker"),
            html.H3(confirmation_heading(confirmation)),
            html.P(dimension_totals_line(objects(confirmation.get("dimensions"))))
            if confirmation and noncanonical
            else html.Div(
                [
                    dimension_cell(item, applicable=applicable)
                    for item in objects(confirmation.get("dimensions"))
                ],
                className="confirmation-summary",
            )
            if confirmation
            # A model before the confirmation structure published four domain states.
            else view._macro_summary(macro)
            if any(key in macro for key in LEGACY_MACRO_STATES)
            else None,
            listed,
        ],
        className="board-right",
    )


# Why an AI adapter attempt produced no reading (reports.ReportService, cli_process).
ADAPTER_FAILURES = {
    "timed_out": "超时",
    "cancelled": "已取消",
    "process_start_failed": "进程未能启动",
    "nonzero_exit": "进程异常退出",
    "authentication_required": "未登录",
    "quota_or_rate_limited": "额度或限频",
    "cli_protocol_incompatible": "命令行协议不兼容",
    "invalid_json_output": "输出不是 JSON",
    "invalid_json_schema": "输出不合结构",
    "schema_validation_failed": "输出不合契约",
    "tool_use_rejected": "调用工具被拒",
    "stage_mutation_rejected": "输出改写正式阶段被拒",
    "conclusion_mutation_rejected": "输出改写结论被拒",
    "forbidden_content_rejected": "输出含禁用内容被拒",
    "paragraph_structure_invalid": "段落结构不合规",
}


def reading_line(
    report: ReportSnapshot | None, pinned: str, *, pending: bool
) -> list[str | html.A]:
    """The board's reading: an AI report's opening sentence, never a template as AI output.

    A queued or running report task says so, also over a report already read (spec).
    """
    if pending:
        return ["报告生成中"]
    if report is None:
        return [
            "报告尚未生成 ",
            html.A("生成报告", href=pinned + "#generate-report-command"),
        ]
    if report.adapter == "deterministic":
        term = view.report_stage_term(report.body if report.body_retained else {})
        failures = "；".join(
            f"{adapter} {ADAPTER_FAILURES.get(outcome, outcome).replace(FORMAL_TERM, term)}"
            for adapter, outcome in report.adapter_outcomes
            if outcome != "succeeded"
        )
        return [
            "本次报告为确定性模板，无 AI 解读"
            + (f"（适配器失败原因：{failures}）" if failures else "（未记录适配器尝试）")
        ]
    sections = objects(report.body.get("ai_explanation"))
    paragraph = str(sections[0].get("explanation") or "") if sections else ""
    sentence = re.match(r"[^。！？]*[。！？]?", paragraph)
    return [
        sentence.group(0) if sentence else paragraph,
        " ",
        html.A("全文", href=pinned + "#reading"),
    ]


def report_summary(report: ReportSnapshot | None, pinned: str) -> list[Any]:
    """Section 07's reading of the board's report: the AI reading's first paragraph, or the
    template note with the noncanonical reading; identity and facts open in a drawer."""
    if report is None:
        return [html.P("报告尚未生成，或旧投影未提供解读。")]
    body = report.body if report.body_retained else {}
    sections = objects(body.get("ai_explanation"))
    stage = obj(obj(body.get("verified_results")).get("formal_stage"))
    # A reading may call a noncanonical day's empty stage a gap; it is no data gap.
    stage_note = (
        html.P(
            "阶段变化：" + NONCANONICAL_NO_STAGE.replace(FORMAL_TERM, view.report_stage_term(body)),
            className="secondary-copy",
        )
        if noncanonical_stage_change(stage.get("change"), stage.get("reason"))
        else None
    )
    if report.adapter == "deterministic":
        summary: list[Any] = [
            html.P(reading_line(report, pinned, pending=False)),
            *(
                html.Div(
                    [
                        html.Strong(str(item.get("title") or "未命名章节")),
                        html.P(str(item.get("explanation") or ""), className="body-copy"),
                    ]
                )
                for item in sections
                if body.get("explanation_source") == "deterministic_template"
            ),
            stage_note,
        ]
    else:
        summary = [
            html.P("AI 解读 · " + report.adapter, className="secondary-copy"),
            html.P(str(sections[0].get("explanation") or ""), className="body-copy")
            if sections
            else None,
            stage_note,
        ]
    if not report.body_retained:
        summary.append(html.P("正文已不在保留期；报告身份仍可在详情中核对。"))
    key = drawer_key("reading", "report")
    return [
        *summary,
        html.P(drawer_trigger(key, "查看报告详情 →")),
        drawer_panel(key, "报告详情", report_details(report), code=report.report_snapshot_id),
    ]


def report_details(report: ReportSnapshot) -> list[Any]:
    """The report's identity, the projection it read, its cutoff and timeliness, the AI
    reading in full, and the structured facts it bound (three cores, verified results).
    A template reading is already whole on the page."""
    if not report.body_retained:
        return [*view._report_head(report), html.P("正文已不在保留期。")]
    body = report.body
    return [
        *view._report_head(report),
        *(
            html.Section(
                [
                    html.H3(str(item.get("title") or "未命名章节")),
                    html.P(str(item.get("explanation") or ""), className="body-copy"),
                ]
            )
            for item in objects(body.get("ai_explanation"))
            if report.adapter != "deterministic"
        ),
        *(
            html.Section(
                [
                    html.H3(title),
                    html.Pre(view._display_value(body[field]), className="body-copy")
                    if field in body
                    else html.P("该报告未提供。"),
                ]
            )
            for title, field in (("三核心", "core_states"), ("已验证结果", "verified_results"))
        ),
    ]


UNAVAILABLE = "口径不可用"


def run_facts_line(summary: dict[str, Any] | None) -> str:
    """Five facts of the producing run's persisted summary; a missing one is never a zero."""
    facts = obj(summary)
    outcomes = facts.get("request_outcomes")
    requests = (
        f"{facts['request_count']} 次，失败 "
        f"{sum(n for key, n in outcomes.items() if key in REQUEST_FAILURES)} 次"
        if isinstance(facts.get("request_count"), int) and isinstance(outcomes, dict)
        else UNAVAILABLE
    )
    budget = obj(facts.get("budget"))
    channels = (("tavily", "Tavily"), ("exa", "Exa"), ("ai_websearch", "AI"))
    spent = (
        "、".join(
            f"{name} {budget[key]}"
            + (f"/{RUN_SEARCH_LIMITS[key]}" if RUN_SEARCH_LIMITS[key] is not None else "")
            for key, name in channels
        )
        if all(key in budget for key, _name in channels)
        else UNAVAILABLE
    )
    duration = facts.get("duration_seconds")
    return " · ".join(
        (
            "目标交易日 " + str(facts.get("target_business_date") or UNAVAILABLE),
            "模型版本 " + str(facts.get("model_version_id") or UNAVAILABLE),
            "外部请求 " + requests,
            "检索预算 " + spent,
            "耗时 " + (number(duration) + " 秒" if duration is not None else UNAVAILABLE),
        )
    )


def reading_series(member: dict[str, Any], projection: ProjectionSet | None) -> Any:
    periods = member.get("periods") or []
    values = member.get("values") or []
    if not periods or len(periods) != len(values):
        return html.Span("读取期不足", className="empty-note")
    return dcc.Graph(
        figure={
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "x": periods,
                    "y": values,
                    "connectgaps": False,
                    "line": {"color": "#278a96", "width": 2},
                    "hovertemplate": "%{x}<br>%{y}<extra>模型实际读取值</extra>",
                }
            ],
            "layout": {
                "height": 85,
                "margin": {"l": 4, "r": 4, "t": 8, "b": 24},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#788c96", "size": 9},
                "showlegend": False,
                "xaxis": {"type": "category", "nticks": 2},
                "yaxis": {"visible": False},
                "uirevision": projection.envelope.projection_set_id if projection else "empty",
            },
        },
        config={"displayModeBar": False},
        className="small-chart",
    )


def member_readings(
    members: list[dict[str, Any]], projection: ProjectionSet | None, *, section: str
) -> Any:
    def inputs(member: dict[str, Any]) -> Any:
        versions = member.get("observation_version_ids") or []
        return html.Details(
            [
                html.Summary(f"实际输入 {len(versions)} 个版本"),
                html.Ul(
                    [
                        html.Li(
                            html.A(
                                str(version),
                                href=evidence_href(projection, str(version), section=section),
                            )
                        )
                        for version in versions
                    ]
                )
                if projection
                else html.P("尚无投影"),
                table(
                    ("实际读取期", "读取值"),
                    list(zip(member.get("periods") or [], member.get("values") or [], strict=True)),
                ),
            ]
        )

    return table(
        (
            "成员 / 角色",
            "来源最新 / 期",
            "读取值 / 期",
            "模型读取时序",
            "水平 / 动量 / 斜率",
            "主辅关系",
            "证据",
        ),
        [
            (
                html.Div(
                    [
                        html.Strong(str(member.get("label", member.get("name")))),
                        html.Small(view._state_label(member.get("role") or "—")),
                    ]
                ),
                html.Div(
                    [
                        value_link(
                            obj(member.get("latest_source")).get("value"),
                            obj(member.get("latest_source")).get("unit"),
                            obj(member.get("latest_source")).get("selected_claim_id"),
                            projection,
                            section=section,
                        ),
                        html.Small(
                            str(
                                obj(member.get("latest_source")).get("period") or "未提供单一来源值"
                            )
                        ),
                    ]
                ),
                html.Div(
                    [
                        number(member.get("value"), member.get("unit")),
                        html.Small(str(member.get("period") or "—")),
                    ]
                ),
                reading_series(member, projection),
                " / ".join(
                    view._READING_LABELS.get(key, {}).get(
                        str(member.get(key)),
                        "未知" if member.get(key) is None else str(member[key]),
                    )
                    for key in ("level", "momentum", "slope")
                ),
                view._READING_LABELS["consistency"].get(str(member.get("consistency")), "未知"),
                inputs(member),
            )
            for member in members
        ],
    )


def dimension_counts(dimension: dict[str, Any], *, applicable: bool) -> str:
    """A dimension card's head: each relation's count by its full name, or why there is none."""
    counts = obj(dimension.get("counts"))
    if dimension.get("status") != "connected" or not counts:
        return "尚未接入"
    text = " · ".join(
        f"{view._RELATION_LABELS[relation]} {view._integer(counts.get(relation))}"
        for relation in RELATION_COUNTED
    )
    return (
        text if applicable else f"{text} · 不计数 {len(objects(dimension.get('key_indicators')))}"
    )


def _main_member(item: dict[str, Any]) -> dict[str, Any]:
    members = objects(item.get("members"))
    return next((member for member in members if member.get("role") == "main"), None) or (
        members[0] if members else {}
    )


def _own_reading(item: dict[str, Any]) -> list[Any]:
    """A key indicator read through its main member alone: value, period and direction, each
    from the latest source when the member lacks it. No stage, so nothing is counted."""
    member = _main_member(item)
    if member.get("direction") is not None:
        direction = _direction_arrow(member["direction"])
    elif member.get("quadrant") is not None:
        direction = view._QUADRANT_LABELS.get(str(member["quadrant"]), "未分类")
    else:
        direction = "方向未提供"
    return [
        *_main_reading(item),
        html.Span(direction),
        html.Span("不计数", className="uncounted-tag"),
    ]


def _main_reading(item: dict[str, Any]) -> list[Any]:
    """The main member's name when it is not the indicator's, its value and its period, each
    from the latest source when the member lacks it."""
    member = _main_member(item)
    source = obj(member.get("latest_source"))

    def read(field: str) -> object:
        return member[field] if member.get(field) is not None else source.get(field)

    label = str(member.get("label") or "")
    return [
        html.Small(label) if label and label != item.get("name") else None,
        html.Span(number(read("value"), read("unit")), className="card-value"),
        html.Span(str(read("period") or "—")),
    ]


def _indicator_row(item: dict[str, Any], key: str, *, applicable: bool) -> Any:
    return drawer_trigger(
        key,
        [
            html.Strong(str(item.get("name") or item.get("metric_id") or "未命名指标")),
            *(
                [
                    html.Span(view._RELATION_LABELS.get(str(item.get("relation")), "未知")),
                    html.Span(f"读取期 {item.get('statistical_period') or '未提供'}"),
                ]
                if applicable
                else _own_reading(item)
            ),
        ],
        class_name="indicator-row",
    )


def gdp_sectors(macro: dict[str, object], projection: ProjectionSet | None) -> Any:
    """GDP by sector, each real quarterly growth and nominal year-to-date level as projected."""
    rows = {
        (
            str(obj(row.get("dimensions")).get("aggregate")),
            str(obj(row.get("dimensions")).get("measure")),
        ): row
        for row in objects(macro.get("international_context"))
        if row.get("metric_id") == "CN_GDP"
    }

    def cell(aggregate: str, measure: str) -> Any:
        row = rows.get((aggregate, measure))
        if row is None:
            return "未提供"
        return html.Div(
            [
                value_link(
                    row.get("value"),
                    row.get("unit"),
                    row.get("selected_claim_id"),
                    projection,
                    section="confirmation",
                ),
                html.Small(str(row.get("period") or "—")),
            ]
        )

    return table(
        ("口径", *_GDP_MEASURES.values()),
        [
            (name, *(cell(aggregate, measure) for measure in _GDP_MEASURES))
            for aggregate, name in _GDP_AGGREGATES.items()
        ],
    )


def _indicator_drawer(
    item: dict[str, Any],
    key: str,
    macro: dict[str, object],
    projection: ProjectionSet | None,
    *,
    applicable: bool,
) -> Any:
    return drawer_panel(
        key,
        str(item.get("name") or item.get("metric_id") or "未命名指标"),
        [
            *(
                []
                if applicable
                else [
                    html.P(
                        "非典型组合不判定命题与成熟度"
                        if is_noncanonical(projection)
                        else f"无{stage_term(projection)}，不判定命题与成熟度",
                        className="empty-note",
                    )
                ]
            ),
            html.H3("主辅成员"),
            member_readings(objects(item.get("members")), projection, section="confirmation"),
            html.H3("派生、依据与缺口、命题与成熟度"),
            view._indicator_card(item),
            *(
                [html.H3("分产业"), gdp_sectors(macro, projection)]
                if item.get("metric_id") == "CN_GDP"
                else []
            ),
        ],
        code=str(item.get("metric_id") or ""),
    )


def confirmation_cards(
    confirmation: dict[str, Any], macro: dict[str, object], projection: ProjectionSet | None
) -> Any:
    """Five dimension cards, one row per key indicator; each row opens its drawer.

    Before the first run there is no projection: each card waits for it under its name.
    """
    if projection is None:
        return html.Div(
            [
                html.Article([html.H3(label), html.P(FIRST_RUN)], className="dimension-card")
                for label in view._DIMENSION_LABELS.values()
            ],
            className="dimension-grid",
        )
    applicable = confirmation.get("applicable") is True
    dimensions = objects(confirmation.get("dimensions"))
    items: list[dict[str, Any]] = []
    keys: list[str] = []
    cards = []
    for dimension in dimensions:
        rows = []
        for item in objects(dimension.get("key_indicators")):
            key = unique_key(
                drawer_key("confirmation", item.get("metric_id"), item.get("key")), keys
            )
            items.append(item)
            keys.append(key)
            rows.append(_indicator_row(item, key, applicable=applicable))
        cards.append(
            html.Article(
                [
                    html.H3(view._DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")),
                    html.P(dimension_counts(dimension, applicable=applicable)),
                    *rows,
                ],
                className="dimension-card",
            )
        )
    return html.Div(
        [
            html.Div(cards, className="dimension-grid"),
            # Panels sit outside the cards so the drawer is fixed to the viewport.
            *[
                _indicator_drawer(item, key, macro, projection, applicable=applicable)
                for item, key in zip(items, keys, strict=True)
            ],
        ]
    )


def macro_basis_section(
    judgement: Mapping[str, Any],
    confirmation: dict[str, Any],
    macro: dict[str, object],
    projection: ProjectionSet | None,
) -> list[Any]:
    """Section 04 under a judgement (macro stage ticket 07): the five cards of its basis; a
    key indicator's row reads its main member, says where it went in the vote and opens the
    drawer of its members, as the confirmation reads them."""
    applicable = confirmation.get("applicable") is True
    readings = {
        (str(dimension.get("dimension")), str(item.get("key"))): item
        for dimension in objects(confirmation.get("dimensions"))
        for item in objects(dimension.get("key_indicators"))
    }
    keys: list[str] = []
    drawers: list[Any] = []

    def row(dimension: str, indicator: Mapping[str, Any], vote: str) -> Any:
        item = readings.get((dimension, str(indicator.get("key"))))
        name = html.Strong(str(indicator.get("name") or indicator.get("key")))
        went = html.Span(vote, className="macro-vote")
        if item is None:
            return html.Div([name, went], className="indicator-row")
        key = unique_key(drawer_key("confirmation", item.get("metric_id"), item.get("key")), keys)
        keys.append(key)
        drawers.append(_indicator_drawer(item, key, macro, projection, applicable=applicable))
        return drawer_trigger(key, [name, *_main_reading(item), went], class_name="indicator-row")

    grid = macro_basis.cards(judgement, row)
    # Panels sit outside the cards so the drawer is fixed to the viewport.
    return [html.P(macro_basis.SCOPE), grid, *drawers]


LINE_CARDS = (("demand", "需求"), ("production", "生产"), ("inventory", "库存"))
FIRST_RUN = "等待首次完整运行。"
LINE_ROLES = {"line": "主线成员", "auxiliary": "辅助成员"}


def inventory_section(confirmation: dict[str, Any], projection: ProjectionSet | None) -> list[Any]:
    """Section 05: the quadrant card, the three lines' cards, the warrants in one line; each
    member once, its auxiliaries and the warrant table in drawers."""
    if projection is None:
        return [
            html.Div(
                [
                    html.P("库存象限", className="section-kicker"),
                    html.Strong("—", className="card-value"),
                    html.Span(FIRST_RUN),
                ],
                className="quadrant-card",
            ),
            line_cards([], {}, None, missing=FIRST_RUN),
        ]
    document = view._dataset(projection, "inventory")
    if document.get("output_structure") != CONFIRMATION_STRUCTURE:
        return [view._inventory_page(projection)]
    indicator = next(
        (
            item
            for dimension in objects(confirmation.get("dimensions"))
            if dimension.get("dimension") == "inventory"
            for item in objects(dimension.get("key_indicators"))
        ),
        None,
    )
    if document.get("status") != "connected" or indicator is None:
        return [
            html.P("库存维度尚未接入：当前模型的库存象限规则尚未接入，不给出象限或三条线。"),
            *warrant_line(document, projection),
        ]
    members = objects(indicator.get("members"))
    available = {str(card.get("label")): card for card in objects(document.get("cards"))}
    return [
        quadrant_card(indicator, term=stage_term(projection)),
        line_cards(members, available, projection),
        *warrant_line(document, projection),
    ]


def quadrant_card(indicator: dict[str, Any], *, term: str = FORMAL_TERM) -> Any:
    member = next((item for item in objects(indicator.get("members")) if "quadrant" in item), {})
    relation = str(indicator.get("relation"))
    return html.Div(
        [
            html.P("库存象限", className="section-kicker"),
            html.Strong(
                view._QUADRANT_LABELS.get(str(member.get("quadrant")), "未分类"),
                className="card-value",
            ),
            html.Span(
                "统计期 "
                + str(member.get("period") or indicator.get("statistical_period") or "未提供")
            ),
            html.Span(quadrant_reading(member)),
            html.Span(
                f"确认关系：{view._RELATION_LABELS[relation]}（象限仅计一项）"
                if relation in RELATION_COUNTED
                else f"确认关系：不适用（无{term}，不计数）",
                className="secondary-copy",
            ),
        ],
        className="quadrant-card",
    )


def quadrant_reading(member: dict[str, Any]) -> str:
    """Why the quadrant is unclassified when it is, then each line's direction."""
    because = UNCLASSIFIED_BY.get(str(member.get("unclassified_by")))
    lines = obj(member.get("lines"))
    directions = "、".join(
        label + view._DIRECTION_LABELS.get(str(obj(lines.get(line)).get("direction")), "方向未知")
        for line, label in view._LINE_LABELS.items()
    )
    return "；".join(part for part in (because and f"未分类原因：{because}", directions) if part)


def _member_name(member: dict[str, Any], line_label: str) -> DisplayName:
    """A line member's own Chinese label without its line's prefix, its code beside it."""
    code = display_name(member.get("metric_id"), obj(member.get("member"))).code
    label = str(member.get("label") or member.get("name") or code)
    return DisplayName(label.removeprefix(line_label + "："), code, bool(member.get("label")))


def _line_member(
    member: dict[str, Any],
    name: DisplayName,
    card: dict[str, Any],
    projection: ProjectionSet | None,
) -> list[Any]:
    """A line member's every field in the drawer: its reading, the source's newest value,
    its role beside the main member, whether its data is held, and the inputs read."""
    source = obj(member.get("latest_source"))
    versions = [str(version) for version in member.get("observation_version_ids") or []]
    fields: list[tuple[str, Any]] = [
        ("角色", LINE_ROLES.get(str(member.get("role")), view._state_label(member.get("role")))),
        (
            "读取值 / 期",
            f"{number(member.get('value'), member.get('unit'))} {member.get('period') or '—'}",
        ),
        (
            "来源最新 / 期",
            [
                value_link(
                    source.get("value"),
                    source.get("unit"),
                    source.get("selected_claim_id"),
                    projection,
                    section="inventory",
                ),
                f" {source.get('period') or '未提供单一来源值'}",
            ],
        ),
        ("方向", _direction_arrow(member.get("direction") or member.get("momentum"))),
        (
            "主辅关系",
            view._READING_LABELS["consistency"].get(str(member.get("consistency")), "未知"),
        ),
        (
            "数据",
            "可用"
            if card.get("availability") == "available"
            else f"不可用（{view._state_label(card.get('evidence_status'))}）"
            if card
            else "该版本未提供",
        ),
        (
            "读取时序",
            " → ".join(
                f"{period} {number(value)}"
                for period, value in zip(
                    member.get("periods") or [], member.get("values") or [], strict=False
                )
            )
            or "读取期不足",
        ),
        (
            "实际输入",
            [
                html.A(
                    version[:12],
                    href=evidence_href(projection, version, section="inventory"),
                    title=version,
                )
                for version in versions
            ]
            if projection and versions
            else "—",
        ),
    ]
    return [
        html.H3([name.name, " ", html.Small(name.code, className="drawer-code")]),
        html.Dl(
            [part for label, value in fields for part in (html.Dt(label), html.Dd(value))],
            className="drawer-fields",
        ),
        reading_series(member, projection),
    ]


def line_cards(
    members: list[dict[str, Any]],
    cards_by_label: dict[str, dict[str, Any]],
    projection: ProjectionSet | None,
    *,
    missing: str = "本投影未提供该线读取",
) -> Any:
    """One card per line with its main member; the drawer holds every member of the line.

    A line without members says ``missing`` instead.
    """
    cards: list[Any] = []
    panels: list[Any] = []
    for line, label in LINE_CARDS:
        listed = sorted(
            (member for member in members if member.get("line") == line),
            key=lambda member: member.get("role") != "line",
        )
        if not listed:
            cards.append(html.Div([html.Strong(label), html.Span(missing)], className="line-card"))
            continue
        main = listed[0]
        name = _member_name(main, label)
        key = drawer_key("inventory", line)
        cards.append(
            drawer_trigger(
                key,
                [
                    html.Span(label, className="section-kicker"),
                    html.Strong(name.name),
                    html.Small(name.code),
                    html.Span(number(main.get("value"), main.get("unit")), className="card-value"),
                    html.Span(_direction_arrow(main.get("direction") or main.get("momentum"))),
                    html.Span(str(main.get("period") or "—")),
                ],
                class_name="line-card",
            )
        )
        panels.append(
            drawer_panel(
                key,
                f"{label}线",
                [
                    part
                    for member in listed
                    for part in _line_member(
                        member,
                        _member_name(member, label),
                        cards_by_label.get(str(member.get("label")), {}),
                        projection,
                    )
                ],
            )
        )
    return html.Div([*cards, *panels], className="line-cards")


def related_assets(
    macro: dict[str, object], asset: str, projection: ProjectionSet
) -> tuple[Any, list[Any]]:
    """A card's observations in four columns, and the drawer panel each row opens."""
    cores = objects(obj(macro.get("observation_interfaces")).get("cores"))
    members = [
        member
        for core in cores
        if core.get("core") == asset
        for member in objects(core.get("members"))
    ]
    if not members:
        return html.P("当前模型未登记同类观察接口。", className="secondary-copy"), []
    readings = [
        (member, evidence)
        for member in members
        for evidence in objects(member.get("evidence")) or [{}]
    ]
    keys = _row_keys("assets", [evidence for _member, evidence in readings], prefix=(asset,))
    judgement = macro_board.judgement(view._dataset(projection, "cycle_overview"))
    rows = []
    panels = []
    for (member, evidence), key in zip(readings, keys, strict=True):
        name = (
            row_name(evidence, fallback=member.get("label"))
            if evidence.get("metric_id")
            else DisplayName(str(member.get("label") or "—"), "", True)
        )
        rows.append(
            (
                # A long name is cut to one line; hovering shows it whole with its code.
                # The link covers its row, the direction cell too, so the title sits on the
                # link and names the periods the direction compares.
                drawer_trigger(
                    key,
                    name.name,
                    class_name="row-trigger",
                    title="\n".join(
                        part for part in (name.name, name.code, direction_hover(evidence)) if part
                    ),
                ),
                number(evidence.get("value"), evidence.get("unit")),
                change_cell(window_change(evidence, "change_5")),
                direction_cell(evidence),
            )
        )
        panels.append(
            _context_drawer(
                evidence,
                key,
                projection,
                name=name,
                section="assets",
                extra=(
                    (
                        "用途",
                        _peer_usage(member, judgement, asset)
                        if judgement is not None
                        else view._state_label(member.get("reads_as"))
                        if member.get("reads_as")
                        else "仅观察，不计数",
                    ),
                    *(
                        (("目录状态", "当前目录未收录"),)
                        if member.get("in_catalog") is False
                        else ()
                    ),
                ),
            )
        )
    return table(("名称", "值", "近 5 日", "较上期方向"), rows), panels


def _peer_usage(member: dict[str, Any], judgement: Mapping[str, Any], asset: str) -> list[Any]:
    """Of the cores' own source, never voting; a peer its asset's listed signal reads points
    to that signal in the 01 list (macro stage ticket 04)."""
    reads = [view._state_label(member.get("reads_as")) + "；"] if member.get("reads_as") else []
    pointed = [
        item
        for item in objects(judgement.get("signals"))
        if item.get("source") == "peers"
        and obj(item.get("asset_turn")).get("asset") == asset
        and member.get("label") in (obj(item.get("peers")).get("against") or ())
    ]
    links = signal_pointers({"signals": pointed}, {"peers"}) if pointed else None
    return [*reads, MACRO_SAME_SOURCE, *([" · ", *links.children] if links is not None else [])]


def coverage_table(
    coverage: dict[str, Any], absent: str = "该版本未提供最终需求计划的两种完整度口径。"
) -> Any:
    """The final plan's two coverage measures; ``absent`` says why a summary has none."""
    if not coverage.get("available"):
        return html.P(absent)
    return html.Div(
        [
            html.P(
                "按最终计划的指标 × 统计期计数；期内缺维度仍算缺失。"
                "模型口径为三核心与确认规则所需，目录口径包含纯观察指标。"
                "等待发布等门禁单列，不计作已持有。"
            ),
            table(
                ("口径", "应有期", "已持有", "门禁 / 等待发布", "其他缺失"),
                [
                    (
                        label,
                        obj(coverage.get(key)).get("total"),
                        *(
                            obj(obj(coverage.get(key)).get("counts")).get(state, 0)
                            for state in ("held", "release_gated", "missing")
                        ),
                    )
                    for key, label in (("model", "模型所需"), ("catalog", "目录全部"))
                ],
            ),
        ]
    )


GAP_PREVIEW = 5


def gap_preview(value: object) -> list[Any]:
    """The gap list once: its first rows on the page, every row in a drawer (spec 07); a
    historical period's members are in the drawer alone (worker gaps 04)."""
    listed = view._document_list(value)
    gaps = [
        item
        for category in view.GAP_CATEGORY_LABELS
        for item in listed
        if item.get("category") == category
    ]
    if len(gaps) <= GAP_PREVIEW:
        return [
            view._gap_list(gaps, detailed=False),
            *(
                [drawer_trigger(GAPS_DRAWER, "缺期明细 →")]
                if any(item.get("missing_periods") for item in gaps)
                else []
            ),
        ]
    return [
        html.P(f"缺口共 {len(gaps)} 条，以下为前 {GAP_PREVIEW} 条。", className="secondary-copy"),
        view._gap_list(gaps[:GAP_PREVIEW], detailed=False),
        # The panel is the one gaps_drawer renders beside the conclusion board.
        drawer_trigger(GAPS_DRAWER, f"查看全部 {len(gaps)} 条缺口 →"),
    ]


def warrant_line(document: dict[str, Any], projection: ProjectionSet | None) -> list[Any]:
    """The registered warrants in one line, their table by symbol and the real inventory
    approximation in a drawer; neither is counted."""
    warrants = obj(document.get("registered_warrants"))
    symbols = objects(warrants.get("symbols"))
    key = drawer_key("inventory", "warrants")
    return [
        html.P(
            [
                html.Strong("注册仓单（附注，不计数）"),
                " ",
                f"{len(symbols)} 个品种 · 最新期 {warrants.get('last_day') or '—'}"
                if warrants
                else "本投影未提供分品种仓单变化",
                " ",
                drawer_trigger(key, "分品种仓单与实际库存近似 →"),
            ],
            className="warrant-line",
        ),
        drawer_panel(
            key,
            "注册仓单与实际库存近似",
            [
                html.H3("分品种注册仓单"),
                *(
                    [
                        html.P(view._warrant_summary(warrants)),
                        table(
                            ("品种", "起点 → 终点", "变化", "换算"),
                            [_warrant_row(item) for item in symbols],
                            class_name="report-table warrant-table",
                        ),
                        *_warrant_inputs(symbols, projection),
                    ]
                    if warrants
                    else [html.P("本投影未提供分品种仓单变化。", className="empty-note")]
                ),
                *real_inventory_approximation(
                    obj(document.get("real_inventory_approximation")), projection
                ),
                html.P(
                    "PMI 库存是扩散指数，不是库存数量；注册仓单不代表产业总库存；"
                    "实际库存近似只是名义产成品存货按 PPI 的粗略调整，不是不变价库存。",
                    className="secondary-copy",
                ),
            ],
        ),
    ]


def _warrant_row(item: dict[str, Any]) -> tuple[Any, ...]:
    unit = view._WARRANT_UNITS.get(str(item.get("unit")), str(item.get("unit")))
    rate, factor = item.get("change_rate"), item.get("factor")
    state = view._WARRANT_STATES.get(str(item.get("status")), "")
    return (
        name_cell(display_name("CN_FUTURES_WARRANTS", {"symbol": item.get("symbol")})),
        f"{_count(item.get('first'))} → {_count(item.get('last'))} {unit}"
        if item.get("first") is not None
        else "—",
        f"{rate:+.1%}" if isinstance(rate, (int, float)) else state or "—",
        f"每{view._WARRANT_UNITS.get(str(item.get('input_unit')), '')} {factor:g} {unit}"
        f"（{item.get('weight_basis')}）"
        if isinstance(factor, (int, float))
        else "—",
    )


def _count(value: object) -> str:
    """Warrant amounts are whole sheets, lots, tonnes or barrels, read without decimals."""
    if isinstance(value, (int, float)) and float(value).is_integer():
        return f"{value:,.0f}"
    return number(value)


def _warrant_inputs(symbols: list[dict[str, Any]], projection: ProjectionSet | None) -> list[Any]:
    """Each symbol's raw inputs at either end, numbered, each opening its fixed evidence."""
    rows = []
    for item in symbols:
        if not (item.get("first_claim_ids") or item.get("last_claim_ids")):
            continue
        name = display_name("CN_FUTURES_WARRANTS", {"symbol": item.get("symbol")}).name
        symbol = str(item.get("symbol"))
        parts: list[Any] = [f"{name}（{symbol}）" if name != symbol else symbol]
        for field, label in (("first_claim_ids", "起点"), ("last_claim_ids", "终点")):
            parts.append(f" {label} ")
            parts.extend(
                html.A(
                    f"{i + 1} ", href=evidence_href(projection, str(version), section="inventory")
                )
                if projection
                else f"{i + 1} "
                for i, version in enumerate(item.get(field) or [])
            )
        rows.append(html.P(parts, className="secondary-copy"))
    return [html.H3("原始输入"), *rows] if rows else []


def real_inventory_approximation(
    document: dict[str, Any], projection: ProjectionSet | None
) -> list[Any]:
    """The nominal finished-goods inventory deflated by PPI: a rough proxy, never counted."""
    title = html.H3("实际库存近似（粗略价格调整代理）")
    if not document:
        return [title, html.P("本投影未提供实际库存近似。", className="empty-note")]
    nominal, ppi = obj(document.get("nominal_inventory")), obj(document.get("ppi_input"))

    def source(item: dict[str, Any]) -> Any:
        return value_link(
            item.get("value"),
            item.get("unit"),
            item.get("selected_claim_id"),
            projection,
            section="inventory",
        )

    fields: list[tuple[str, Any]] = [
        (
            "值",
            number(document.get("value"), nominal.get("unit"))
            if document.get("value") is not None
            else view._state_label(document.get("status")),
        ),
        ("统计期", str(nominal.get("period") or "—")),
        ("算法", "名义产成品存货 ÷（1 + PPI 同比 ÷ 100）"),
        ("名义产成品存货", source(nominal)),
        ("PPI 同比", source(ppi)),
        ("公式版本", str(document.get("formula_version") or "—")),
        ("派生证据", str(document.get("derived_observation_id") or "—")),
        ("计数", "不计数，不参与库存象限"),
    ]
    return [
        title,
        html.Dl(
            [part for label, value in fields for part in (html.Dt(label), html.Dd(value))],
            className="drawer-fields",
        ),
    ]


def context_trend(
    row: dict[str, Any], projection: ProjectionSet | None, section: str
) -> list[Any] | str:
    """A context row's real-period line, its comparison endpoints and the equivalent table."""
    display = obj(row.get("display"))
    points = objects(display.get("points"))
    if not points:
        return "尚无可用点列" if display else "该版本未提供"
    return [
        dcc.Graph(
            figure={
                "data": [
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "connectgaps": False,
                        "x": [point["date"] for point in points],
                        "y": [point["value"] for point in points],
                        "customdata": [
                            evidence_href(projection, point["selected_claim_id"], section=section)
                            if projection and point.get("selected_claim_id")
                            else None
                            for point in points
                        ],
                        "line": {"color": "#278a96"},
                    }
                ],
                "layout": {
                    "height": 180,
                    "margin": {"l": 45, "r": 8, "t": 8, "b": 35},
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "font": {"color": "#788c96"},
                },
            },
            config={"displayModeBar": False},
            className="price-chart",
        ),
        *[
            html.P(
                f"{count} 日："
                f"{obj(display.get('change_' + str(count))).get('start_date') or '—'} → "
                f"{obj(display.get('change_' + str(count))).get('end_date') or '—'}；"
                + REASONS.get(
                    str(obj(display.get("change_" + str(count))).get("reason")), "实际端点"
                )
            )
            for count in (5, 120)
        ],
        table(
            ("统计期", "值 / 单位"),
            [
                (
                    point["date"],
                    value_link(
                        point["value"],
                        row.get("unit"),
                        point.get("selected_claim_id"),
                        projection,
                        section=section,
                    ),
                )
                for point in points
            ],
        ),
    ]


HISTORY_LABELS = {
    "unpublished": "未发布",
    "unavailable": "不可用",
    **CORE_STATE_LABELS,
    "undetermined": "待定",
    "unknown": "未知",
    "noncanonical_combination": NONCANONICAL_NO_STAGE,
    "canonical_combination": "典型组合",
    "insufficient_core_evidence": "核心不足",
    **BLOCKED_REASONS,
}


def history_label(value: object, *, term: str = FORMAL_TERM) -> str:
    """A day's state in Chinese once: a stage's code stays in its drawer's title; ``term``
    is what the page calls the cores' stage."""
    text = str(value)
    label = HISTORY_LABELS.get(text, stage_name(value) if text.startswith("stage_") else text)
    return label.replace(FORMAL_TERM, term)


def lookback_note(lookback: object) -> list[Any]:
    """The last confirmed stage looked back for before the window, and what it cost."""
    if not isinstance(lookback, dict):
        return []
    return [
        html.H3("窗口前的上一确认阶段"),
        html.P(view._last_confirmed_label(lookback.get("stage"), lookback)),
        html.P(
            f"回溯 {lookback.get('years')} 年，区间请求 {lookback.get('core_requests')} 次、"
            f"日历请求 {lookback.get('calendar_requests')} 次；"
            "回溯的价格只用于找出上一确认阶段，不进入宏观确认度与模型输入。",
            className="secondary-copy",
        ),
    ]


def stage_history(
    projection: ProjectionSet | None, stage_events: Sequence[dict[str, object]]
) -> list[Any]:
    """Section 06: the bands beside their intervals, then the drawers both sides open."""
    bands, band_panels = stage_bands(projection)
    intervals, interval_panels = history_intervals(history_days(projection, stage_events))
    return [
        html.Div(
            [
                html.Div(bands, className="history-side"),
                html.Div(intervals, className="history-side history-list"),
            ],
            className="history-layout",
        ),
        *band_panels,
        *interval_panels,
    ]


def macro_recorded(days: Sequence[dict[str, Any]]) -> bool:
    """Whether the days show the macro row: a set published from ticket 08 on carries
    it, and it shows once a day records a conclusion, or that it had no stage to take."""
    return (
        bool(days)
        and all("macro" in day for day in days)
        and any(day["macro"] not in {"not_effective", "unpublished"} for day in days)
    )


def macro_history_label(day: Mapping[str, Any]) -> str:
    """A day's macro main conclusion, its stage with its confidence, or why there is none."""
    value = str(day.get("macro"))
    if value.startswith("stage_"):
        notes = [MACRO_CONFIDENCES.get(str(day.get("macro_confidence")), "")]
        if day.get("macro_note") == NOT_RECOMPUTED:
            notes.append(MACRO_NOT_RECOMPUTED)
        noted = "，".join(note for note in notes if note)
        return f"{stage_name(value)}（{noted}）" if noted else stage_name(value)
    return MACRO_HISTORY_BLANKS.get(value) or history_label(value)


# How the hysteresis left a day's main conclusion, as its interval's drawer tells it; the
# run counted toward replacing it is the day's signal list's, not the history's (decision 33).
MACRO_HYSTERESIS = {"initial": "无既往主结论，取当日原始判断", "agrees": "与当日原始判断一致"}


def macro_hysteresis_label(state: object) -> str:
    """滞回保持，当日原始判断：第 X 阶段（倾向） while held (decision 45); replaced, the
    sessions its raw judgement ran; a day that recorded none says so."""
    state = obj(state)
    basis = state.get("basis")
    if basis == "held":
        raw = state.get("raw_stage")
        if raw is None:
            return f"滞回保持，当日原始判断：{MACRO_HISTORY_BLANKS['no_stage']}"
        confidence = MACRO_CONFIDENCES.get(str(state.get("raw_confidence")), "")
        return f"滞回保持，当日原始判断：{stage_name(raw)}（{confidence}）"
    if basis == "replaced":
        return f"滞回替换：当日原始判断已连续 {state.get('sessions_required')} 日，取代原主结论"
    return MACRO_HYSTERESIS.get(str(basis), "滞回状态未记录")


def macro_history_day(day: dict[str, Any]) -> html.Li:
    """One day of a macro interval: its main conclusion with its confidence and how the
    hysteresis left it, the version it corrects; its price stage is the price drawer's (D2)."""
    recorded = str(day.get("macro")).startswith("stage_")
    return html.Li(
        [
            html.Strong(f"{day['date']} · {macro_history_label(day)}"),
            html.Span(
                macro_hysteresis_label(day.get("macro_hysteresis")), className="secondary-copy"
            )
            if recorded
            else None,
            *correction_note(day, term=PRICE_TERM),
            html.Span(["投影 ", projection_link(day.get("projection_set_id"))]),
        ],
        className="record-row",
    )


def macro_count_label(key: str) -> str:
    stage, _, confidence = key.partition(":")
    return macro_history_label({"macro": stage, "macro_confidence": confidence or None})


# A stage's colour on every row of the bands, whatever else they show; a macro conclusion
# less than explicit is a lighter shade of it.
STAGE_COLORS = {
    "stage_i": "#36566b",
    "stage_ii": "#278a96",
    "stage_iii": "#c58b42",
    "stage_iv": "#976269",
    "stage_v": "#668c7a",
    "stage_vi": "#747d9a",
}
OTHER_COLORS = ("#9c8b59", "#647487", "#8a7f74", "#5f7f8c", "#a07f86", "#7d8f6b")
_SHADES = {"explicit": 0.0, "tendency": 0.4, "weak": 0.65}
_SHADE_TOWARD = (0xD6, 0xDD, 0xE0)


def band_color(category: str, others: Sequence[str]) -> str:
    """``category``'s colour: a stage's own, shaded by a macro confidence after a colon;
    any other state one of the rest, by its place among ``others``."""
    stage, _, confidence = category.partition(":")
    if stage not in STAGE_COLORS:
        return OTHER_COLORS[others.index(category) % len(OTHER_COLORS)]
    base = STAGE_COLORS[stage]
    share = _SHADES.get(confidence, 0.0)
    channels = (int(base[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(
        f"{round(value + (toward - value) * share):02x}"
        for value, toward in zip(channels, _SHADE_TOWARD, strict=True)
    )


def _band_category(day: Mapping[str, Any], key: str) -> str | None:
    """The colour category of a day's cell; None leaves the macro row blank."""
    if key != "macro":
        return str(day[key])
    value = str(day.get("macro"))
    if value in MACRO_HISTORY_BLANKS:
        return None
    if value.startswith("stage_"):
        return f"{value}:{day.get('macro_confidence')}"
    return value


def stage_bands(projection: ProjectionSet | None) -> tuple[list[Any], list[Any]]:
    """The bands with their day counts, and the trading-day table's drawer; the macro
    judgement's row leads them on a set that records it (ticket 08)."""
    document = view._dataset(projection, "stage_history")
    display = obj(document.get("display"))
    days = objects(display.get("days"))
    if not days:
        return [
            html.P("正式阶段由债券、股票、商品的 120 日稳定方向映射；宏观事实只做事后确认。"),
            html.P("旧投影未提供对齐的交易日色带；历史事件仍可阅读。"),
        ], []
    macro = macro_recorded(days)
    term = PRICE_TERM if macro else FORMAL_TERM
    kinds = (("macro",) if macro else ()) + ("official", "bond", "stock", "commodity")
    labels = ((MACRO_JUDGEMENT,) if macro else ()) + (term, "债券", "股票", "商品")

    def label(day: Mapping[str, Any], key: str) -> str:
        return macro_history_label(day) if key == "macro" else history_label(day[key], term=term)

    calendar = drawer_key("history-calendar")
    cells = [[_band_category(day, key) for day in days] for key in kinds]
    categories = list(dict.fromkeys(item for row in cells for item in row if item is not None))
    others = [item for item in categories if item.partition(":")[0] not in STAGE_COLORS]
    colors = [band_color(item, others) for item in categories]
    top = max(1, len(categories) - 1)
    # A few upright ticks fit the bands' column at any width; within one year month and day
    # say enough, and the hover still names the full date.
    dates = [str(day["date"]) for day in days]
    one_year = len({date[:4] for date in dates}) == 1
    ticks = dates[:: -(-len(dates) // (6 if one_year else 4))]
    graph = dcc.Graph(
        figure={
            "data": [
                {
                    "type": "heatmap",
                    "x": [day["date"] for day in days],
                    "y": labels,
                    "z": [
                        [categories.index(item) if item is not None else None for item in row]
                        for row in cells
                    ],
                    "text": [[label(day, key) for day in days] for key in kinds],
                    # Each category's own colour at its index, also when there is one.
                    "colorscale": [[i / top, colors[i]] for i in range(len(categories))]
                    + ([[1, colors[0]]] if len(categories) == 1 else []),
                    "zmin": 0,
                    "zmax": top,
                    "showscale": False,
                    "ygap": 5,
                    "hovertemplate": "%{x} · %{y}<br>%{text}<extra></extra>",
                }
            ],
            "layout": {
                "height": 250 if macro else 210,
                "margin": {"l": 70, "r": 8, "t": 10, "b": 35},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#788c96"},
                "xaxis": {
                    "type": "category",
                    "tickvals": ticks,
                    "ticktext": [date[5:] if one_year else date for date in ticks],
                    "tickangle": 0,
                },
                "yaxis": {"autorange": "reversed"},
            },
        },
        config={"displayModeBar": False},
    )
    counts = [
        html.P(
            f"{term}日数："
            + " · ".join(
                f"{history_label(key, term=term)} {value} 日"
                for key, value in obj(display.get("counts")).items()
            )
        )
    ]
    if macro:
        counts.insert(
            0,
            html.P(
                "宏观判断日数："
                + " · ".join(
                    f"{macro_count_label(str(key))} {value} 日"
                    for key, value in obj(display.get("macro_counts")).items()
                )
            ),
        )
    return (
        [
            *(
                [
                    html.P(
                        "宏观判断由政策、信用、增长、物价、库存五维对照特征表得出，"
                        "每日记滞回后的主结论，色深为明确、渐浅为倾向与弱；"
                        "生效前与无可取阶段留空，不倒推。"
                        "价格阶段由债券、股票、商品的 120 日稳定方向映射，作价格验证。"
                    )
                ]
                if macro
                else [
                    html.P(
                        "正式阶段由债券、股票、商品的 120 日稳定方向映射；宏观事实只做事后确认。"
                    ),
                    html.P(NO_MACRO_JUDGEMENT, className="secondary-copy"),
                ]
            ),
            graph,
            *counts,
            html.P(drawer_trigger(calendar, "交易日历与色带等价表格")),
        ],
        [
            drawer_panel(
                calendar,
                "交易日历与色带等价表格",
                [
                    *lookback_note(document.get("last_confirmed_lookback")),
                    html.H3("交易日与色带"),
                    table(
                        ("交易日", *labels, "投影版本", "更正的版本"),
                        [
                            (
                                day["date"],
                                *(label(day, key) for key in kinds),
                                projection_link(day.get("projection_set_id")),
                                projection_link(obj(day.get("corrects")).get("projection_set_id"))
                                if day.get("corrects")
                                else "—",
                            )
                            for day in days
                        ],
                    ),
                ],
            )
        ],
    )


# The interval list covers the bands' window: the latest 120 trading days.
HISTORY_WINDOW = 120


def history_days(
    projection: ProjectionSet | None, stage_events: Sequence[dict[str, object]]
) -> list[dict[str, Any]]:
    """The latest window's days, oldest first, each with its day's event when there is one.

    The projection's aligned band days come first; a set without them (or no set, with the
    read model's events) lists its events, a day's state its stage or the reason it has none.
    """
    document = view._dataset(projection, "stage_history")
    events = {
        str(item.get("business_date")): item
        for item in objects(document.get("events") if projection else stage_events)
    }
    days = objects(obj(document.get("display")).get("days")) or [
        {
            "date": day,
            "official": item.get("current_stage") or item.get("stage_reason") or "unpublished",
            "projection_set_id": item.get("projection_set_id"),
            "corrects": item.get("corrects"),
        }
        for day, item in sorted(events.items())
    ]
    return [{**events.get(str(day["date"]), {}), **day} for day in days][-HISTORY_WINDOW:]


def history_intervals(days: Sequence[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    """Consecutive days of one state, a stage or the reason for none, as one row each, and
    the drawers listing each interval's days. On days that record the macro judgement, a
    switch lists them by its main conclusion instead (ticket 08)."""
    heading = html.H3(f"阶段区间（最近 {HISTORY_WINDOW} 个交易日）")
    if not days:
        return [
            heading,
            html.P("尚无阶段事件；首次完整投影发布后，区间会显示在这里。", className="empty-note"),
        ], []
    macro = macro_recorded(days)
    term = PRICE_TERM if macro else FORMAL_TERM
    official, official_panels = _interval_list(
        days,
        lambda day: (day["official"],),
        lambda day: history_label(day["official"], term=term),
        "history-interval",
        view="official" if macro else None,
        term=term,
    )
    if not macro:
        return [heading, official], official_panels
    by_macro, macro_panels = _interval_list(
        days,
        lambda day: (day.get("macro"), day.get("macro_confidence")),
        macro_history_label,
        "history-macro-interval",
        view="macro",
        row=macro_history_day,
    )
    views = (("official", term), ("macro", MACRO_JUDGEMENT))
    # Only the switch's script shows the other list; without it the formal one stays.
    switch = html.Div(
        [
            html.Button(
                label,
                type="button",
                className="history-view",
                **cast(
                    Any,
                    {
                        "data-history-view": view_name,
                        "aria-pressed": "true" if view_name == "official" else "false",
                    },
                ),
            )
            for view_name, label in views
        ],
        className="history-views",
        role="group",
        **cast(Any, {"aria-label": "区间按"}),
    )
    return [heading, switch, official, by_macro], [*official_panels, *macro_panels]


def _interval_list(
    days: Sequence[dict[str, Any]],
    state: Callable[[dict[str, Any]], tuple[object, ...]],
    label: Callable[[dict[str, Any]], str],
    prefix: str,
    *,
    view: str | None = None,
    term: str = FORMAL_TERM,
    row: Callable[[dict[str, Any]], html.Li] | None = None,
) -> tuple[html.Ul, list[Any]]:
    """The intervals of one ``state`` running over consecutive days, and their drawers; a
    ``view`` names the list for the switch between them, shown only for the formal stage.
    A drawer lists its days by ``row``, by default their stage, called ``term``."""
    if row is None:
        row = lambda day: history_day(day, term=term)  # noqa: E731
    runs: list[list[dict[str, Any]]] = []
    for day in days:
        if runs and state(runs[-1][-1]) == state(day):
            runs[-1].append(day)
        else:
            runs.append([day])
    # Month and day read well while the window stays in one year.
    short = len({str(day["date"])[:4] for day in days}) == 1

    def span(run: list[dict[str, Any]]) -> str:
        first, last = (str(run[0]["date"]), str(run[-1]["date"]))
        if short:
            first, last = first[5:], last[5:]
        return first if len(run) == 1 else f"{first}～{last}"

    keys = [drawer_key(prefix, run[0]["date"]) for run in runs]
    return (
        html.Ul(
            [
                html.Li(
                    drawer_trigger(
                        key,
                        [
                            html.Strong(span(run)),
                            html.Span(label(run[0])),
                            html.Span(f"{len(run)} 日"),
                            *corrected_count(run),
                        ],
                        class_name="history-interval",
                    )
                )
                for key, run in zip(keys, runs, strict=True)
            ],
            className="history-intervals",
            **cast(
                Any,
                {"data-history-view": view, "hidden": view == "macro"} if view is not None else {},
            ),
        ),
        [
            drawer_panel(
                key,
                f"{label(run[0])} · {span(run)}",
                [html.Ul([row(day) for day in run], className="record-list")],
                code=stage_code(state(run[0])[0])
                if str(state(run[0])[0]).startswith("stage_")
                else None,
            )
            for key, run in zip(keys, runs, strict=True)
        ],
    )


def corrected_count(run: Sequence[dict[str, Any]]) -> list[html.Span]:
    count = sum(isinstance(day.get("corrects"), dict) for day in run)
    return [html.Span(f"含更正 {count} 日")] if count else []


def projection_link(projection_set_id: object) -> Any:
    """A day's own set, opened at its stage history: the page then reads that set alone."""
    if not projection_set_id:
        return "未发布"
    return html.A(
        str(projection_set_id),
        href="/?" + urlencode({"projection": str(projection_set_id)}) + "#history",
    )


def history_day(day: dict[str, Any], *, term: str = FORMAL_TERM) -> html.Li:
    """One day of an interval: its state, its event's facts, the version it corrects and why;
    ``term`` is what the page calls the cores' stage."""
    gaps = day.get("gaps")
    facts = (
        [
            "上一确认 "
            + (
                view._stage_label(day["last_confirmed_stage"])
                if day.get("last_confirmed_stage")
                else "尚无"
            ),
            "原因 " + history_label(day.get("stage_reason") or "未记录", term=term),
            "；".join(view._gap_label(str(value)) for value in gaps)
            if isinstance(gaps, list) and gaps
            else "无 P0 缺口",
            f"模型 {day.get('model_version_id') or '见投影详情'}",
        ]
        if "business_date" in day
        else []
    )
    return html.Li(
        [
            html.Strong(f"{day['date']} · {history_label(day['official'], term=term)}"),
            html.Span(" · ".join(facts), className="secondary-copy") if facts else None,
            *correction_note(day, term=term),
            html.Span(["投影 ", projection_link(day.get("projection_set_id"))]),
        ],
        className="record-row",
    )


def correction_note(day: Mapping[str, Any], *, term: str) -> list[html.Span]:
    """The version a day corrects and why; none for a day that corrects none."""
    corrects = day.get("corrects")
    if not isinstance(corrects, dict):
        return []
    return [
        html.Span(
            [
                "更正版本：更正 ",
                projection_link(corrects.get("projection_set_id")),
                "（"
                + (
                    view._stage_correction_note(corrects).replace(FORMAL_TERM, term)
                    or str(corrects.get("reason"))
                )
                + "）",
            ],
            className="secondary-copy",
        )
    ]


# The page's "海外与汇率" list, in reading order: FX, US Treasuries, then risk and oil. The
# Worker groups every P2 metric as international context; CNY030 already sits on the bond
# card and GDP belongs to section 04, so neither shows here.
OVERSEAS_METRICS = (
    "CN_USDCNY_CENTRAL_PARITY",
    "CN_USDCNY_CLOSE_1630",
    "CN_USDCNY_ECB_REFERENCE_CROSS",
    "UST10Y_NOMINAL_YIELD",
    "UST2Y_NOMINAL_YIELD",
    "UST_2S10S_SPREAD",
    "CBOE_VIX_INDEX",
    "NASDAQ_SOX_INDEX",
    "EIA_BRENT_RBRTE",
    "EIA_WTI_RWTC",
)
OVERSEAS_ELSEWHERE = ("CN_BOND_FULL_PRICE_CNY030", "CN_GDP")
DIRECTION_ARROWS = {"up": "↑ 上升", "down": "↓ 下降", "flat": "→ 持平"}


def _direction_arrow(value: object) -> str:
    return DIRECTION_ARROWS.get(str(value), "— " + view._state_label(value))


def _compared_periods(item: dict[str, Any]) -> str | None:
    """The two periods a row's direction compares, latest against the previous available one
    (not the 5-day window): the earlier is the display point reading the direction's input.
    A row whose direction reads no earlier period has none."""
    inputs = item.get("direction_input_observation_version_ids") or ()
    if not inputs:
        return None
    previous = next(
        (
            point["date"]
            for point in objects(obj(item.get("display")).get("points"))
            if point.get("selected_claim_id") in inputs and point.get("date")
        ),
        None,
    )
    return f"{previous} → {item.get('period') or '—'}" if previous else "上期日期未提供"


def direction_hover(item: dict[str, Any]) -> str | None:
    """The two periods the direction compares, as hovering names them; None for none."""
    compared = _compared_periods(item)
    return f"较上期：{compared}（非近 5 日）" if compared else None


def direction_cell(item: dict[str, Any], *, label: str = "") -> Any:
    """The direction's arrow, after ``label`` when it compares two periods; hovering names
    them."""
    hover = direction_hover(item)
    arrow = _direction_arrow(item.get("direction"))
    return html.Span(label + arrow, title=hover) if hover else arrow


# The derived Treasury spread's projected direction is the sign of its value, not a
# comparison with an earlier period, so it reads as positive or inverted.
SPREAD_METRIC = "UST_2S10S_SPREAD"


def _spread_sign(item: dict[str, Any], *, short: bool) -> str:
    value = item.get("value")
    if not isinstance(value, int | float):
        return "—"
    if value > 0:
        return "正值（未倒挂）" if short else "正值（10 年高于 2 年）"
    if value < 0:
        return "倒挂" if short else "倒挂（10 年低于 2 年）"
    return "零" if short else "零（10 年等于 2 年）"


def _direction_field(item: dict[str, Any]) -> tuple[str, str]:
    if item.get("metric_id") == SPREAD_METRIC:
        return ("利差正负", _spread_sign(item, short=False))
    compared = _compared_periods(item)
    arrow = _direction_arrow(item.get("direction"))
    return ("较上期方向", f"{arrow}（{compared}）") if compared else ("方向", arrow)


def _overseas_card(item: dict[str, Any], key: str) -> Any:
    name = row_name(item)
    return drawer_trigger(
        key,
        [
            html.Strong(name.name),
            html.Small(name.code) if name.code != name.name else None,
            html.Span(number(item.get("value"), item.get("unit")), className="card-value"),
            html.Span(str(item.get("period") or "—")),
            html.Span(_spread_sign(item, short=True), title="按利差正负，不是较上期方向")
            if item.get("metric_id") == SPREAD_METRIC
            else html.Span(direction_cell(item, label="较上期 ")),
            html.Span(["近 5 日 ", change_cell(obj(item.get("display")).get("change_5"))]),
        ],
        class_name="overseas-card",
    )


def _change_text(value: object) -> str:
    change = obj(value)
    if change.get("value") is None:
        reason = str(change.get("reason") or "旧投影未提供")
        note = missing_note(change)
        return f"—（{REASONS.get(reason) or reason_label(reason)}{'：' + note if note else ''}）"
    return (
        change_number(change)
        + f"（{change.get('start_date') or '—'} → {change.get('end_date') or '—'}）"
    )


def _source_link(reference: object) -> Any:
    label = view._source_label(reference)
    return html.A(label, href=label) if label.startswith(("https://", "http://")) else label


def _context_drawer(
    item: dict[str, Any],
    key: str,
    projection: ProjectionSet | None,
    *,
    name: DisplayName,
    section: str,
    extra: Sequence[tuple[str, Any]] = (),
) -> Any:
    """Every field of one context row, its evidence and its trend, as a drawer panel."""
    fields: list[tuple[str, Any]] = [
        (
            "最新值",
            value_link(
                item.get("value"),
                item.get("unit"),
                item.get("selected_claim_id"),
                projection,
                section=section,
            ),
        ),
        (
            "统计期 / 频率",
            f"{item.get('period') or '—'} / "
            + view._state_label(item.get("frequency") or "未提供"),
        ),
        _direction_field(item),
        ("近 5 日", _change_text(window_change(item, "change_5"))),
        ("近 120 日", _change_text(window_change(item, "change_120"))),
        ("时效", view._state_label(item.get("status"))),
        *extra,
        (
            "证据",
            [
                html.A(
                    "查看固定版本证据 →",
                    href=evidence_href(projection, str(item["selected_claim_id"]), section=section),
                )
                if projection and item.get("selected_claim_id")
                else "该版本未提供",
                f" 观测 {item['observation_id']}" if item.get("observation_id") else None,
            ],
        ),
    ]
    trend = context_trend(item, projection, section)
    return drawer_panel(
        key,
        name.name,
        [
            *name_note(name),
            html.Dl(
                [part for label, value in fields for part in (html.Dt(label), html.Dd(value))],
                className="drawer-fields",
            ),
            html.H3("走势与比较端点"),
            *([html.P(trend, className="empty-note")] if isinstance(trend, str) else trend),
        ],
        code=name.code or None,
    )


def _overseas_drawer(item: dict[str, Any], key: str, projection: ProjectionSet | None) -> Any:
    return _context_drawer(
        item,
        key,
        projection,
        name=row_name(item),
        section="overseas",
        extra=(
            ("最近获取", view._state_label(item.get("acquisition_status"))),
            ("采用来源", _source_link(item.get("source_reference"))),
        ),
    )


def overseas_cards(macro: dict[str, object], projection: ProjectionSet | None) -> Any:
    rows = [with_metric_unit(item) for item in objects(macro.get("international_context"))]
    if not rows:
        return html.P("本投影尚无海外与汇率事实。", className="empty-note")
    listed = sorted(
        (item for item in rows if item.get("metric_id") in OVERSEAS_METRICS),
        key=lambda item: OVERSEAS_METRICS.index(str(item["metric_id"])),
    )
    others = [
        item
        for item in rows
        if item.get("metric_id") not in OVERSEAS_METRICS
        and item.get("metric_id") not in OVERSEAS_ELSEWHERE
    ]
    keys = _row_keys("overseas", [*listed, *others])
    return html.Div(
        [
            *[_overseas_card(item, key) for item, key in zip(listed, keys, strict=False)],
            html.Div(
                [
                    html.H3("其他背景指标"),
                    *[
                        _overseas_card(item, key)
                        for item, key in zip(others, keys[len(listed) :], strict=True)
                    ],
                ],
                className="overseas-others",
            )
            if others
            else None,
            # Panels sit outside the cards so the drawer is fixed to the viewport.
            *[
                _overseas_drawer(item, key, projection)
                for item, key in zip([*listed, *others], keys, strict=True)
            ],
        ],
        className="overseas-grid",
    )


def _row_keys(
    section: str, rows: Sequence[dict[str, Any]], *, prefix: Sequence[str] = ()
) -> list[str]:
    """One drawer key per row: the metric and its member dimensions, numbered if repeated."""
    keys: list[str] = []
    for item in rows:
        dimensions = obj(item.get("dimensions"))
        key = drawer_key(
            section,
            *prefix,
            item.get("metric_id"),
            *(dimensions[name] for name in sorted(dimensions)),
        )
        keys.append(unique_key(key, keys))
    return keys


def identity_strip(
    projection: ProjectionSet | None,
    *,
    producer: ProducerRun | None,
    rendered_at: datetime,
) -> list[Any]:
    """The topbar's seven identity fields as label / value pairs."""
    return [
        view._metadata(label, value)
        for label, value in identity_fields(projection, producer=producer, rendered_at=rendered_at)
    ]


def evidence_workspace(
    projection: ProjectionSet | None,
    document: dict[str, Any] | None,
    query: dict[str, str],
    search_results: list[dict[str, Any]] | None = None,
) -> html.Div:
    identity = projection.envelope.projection_set_id if projection else ""
    section = query.get("return", "assets")
    if section not in {key for key, _title in SECTIONS}:
        section = "assets"
    back = "/?" + urlencode({"projection": identity}) + "#" + section
    body: list[Any] = [
        html.H2("证据追溯", id="evidence"),
        html.P("分析证据固定于 " + (identity or "尚无投影")),
        html.A("← 返回报告原段落", href=back),
        html.Form(
            [
                dcc.Input(name="projection", type="hidden", value=identity),
                *[
                    dcc.Input(name=key, type="hidden", value=value)
                    for key, value in query.items()
                    if key in {"run", "return", "channel", "phase", "result", "metric"}
                ],
                html.Label(
                    [
                        "检索冻结指标 ID、维度、统计期或来源",
                        dcc.Input(name="q", type="search", value=query.get("q", ""), debounce=True),
                    ]
                ),
                html.Button("检索", type="submit", className="quiet-button"),
            ],
            action="/data-chain",
            method="get",
            className="filter-bar",
        ),
        html.Details(
            [
                html.Summary(f"冻结证据检索结果 · {len(search_results or [])} 项（最多 100 项）"),
                table(
                    ("指标 / 版本", "维度", "统计期", "值", "来源 / 公式"),
                    [
                        (
                            html.A(
                                str(item["metric_id"]),
                                href="/data-chain?"
                                + urlencode(
                                    {
                                        **{
                                            key: value
                                            for key, value in query.items()
                                            if key not in {"version", "trail"}
                                        },
                                        "projection": identity,
                                        "version": item["version_id"],
                                    }
                                )
                                + "#evidence",
                            ),
                            item.get("dimensions_json") or "—",
                            item.get("period_end") or "派生值",
                            number(item.get("value"), item.get("unit")),
                            item.get("provider") or item.get("formula_version"),
                        )
                        for item in search_results or []
                    ],
                )
                if search_results
                else html.P("没有匹配的留存明细。"),
            ]
        ),
    ]
    if document is None:
        body.append(html.P("从看板数值或图点进入对应证据。"))
    elif document.get("error"):
        body.append(html.P("证据不可用：" + str(document["error"]), role="alert"))
    else:
        trace = obj(document.get("trace"))
        body.extend(
            [
                html.P(
                    f"{trace.get('metric_id')} · {trace.get('period_start', '')} → "
                    f"{trace.get('period_end', '')}"
                ),
                html.P(
                    f"冻结选值 {number(trace.get('selected_value', trace.get('value')))} · "
                    f"版本 {trace.get('selected_claim_id', trace.get('derived_observation_id'))}"
                ),
                html.P("选值绑定已发布版本；其他来源与修订用于对照，不替换本投影。"),
                html.P("同定义目录归并：" + "、".join(document.get("same_definition_versions", [])))
                if document.get("same_definition_versions")
                else None,
                html.Div(
                    [
                        html.P("派生公式：" + str(trace.get("formula_version"))),
                        html.P(
                            "逐层展开实际输入版本；重复版本共用身份，异常环和缺失父节点会明确报错。"
                        ),
                        html.Ul(
                            [
                                html.Li(
                                    html.A(
                                        str(version),
                                        href="/data-chain?"
                                        + urlencode(
                                            {
                                                **query,
                                                "projection": identity,
                                                "version": version,
                                                "trail": ",".join(document.get("lineage_path", [])),
                                            }
                                        )
                                        + "#evidence",
                                    )
                                )
                                for version in trace.get("input_observation_version_ids", [])
                            ]
                        ),
                    ]
                )
                if document.get("kind") == "derived"
                else None,
                table(
                    ("声明版本 / 采用", "来源", "值 / 单位", "系统可用", "修订前版本"),
                    [
                        (
                            str(item.get("claim_id"))
                            + (
                                " · 本投影采用"
                                if item.get("claim_id") == trace.get("selected_claim_id")
                                else " · 其他来源/版本"
                            ),
                            item.get("provider"),
                            number(item.get("value"), item.get("unit")),
                            str(item.get("available_at")),
                            item.get("supersedes_claim_id") or "—",
                        )
                        for item in objects(trace.get("claims"))
                    ],
                ),
                html.H3("获取回执与原件"),
                *[
                    html.Details(
                        [
                            html.Summary(
                                f"{receipt.get('provider')} / {receipt.get('api_name')} · "
                                f"{receipt.get('state')}"
                            ),
                            html.P(str(receipt.get("acquisition_id"))),
                            *[
                                html.A(
                                    f"查看 {kind} 文本",
                                    target="_blank",
                                    rel="noopener",
                                    href=f"/api/v1/acquisitions/{receipt['acquisition_id']}/artifacts/{kind}?view=true",
                                )
                                for kind in ("raw", "normalized")
                                if receipt.get(kind + "_hash")
                            ],
                            *[
                                html.A(
                                    f"下载 {kind} 原件",
                                    download="",
                                    href=f"/api/v1/acquisitions/{receipt['acquisition_id']}/artifacts/{kind}",
                                )
                                for kind in ("raw", "normalized")
                                if receipt.get(kind + "_hash")
                            ],
                        ]
                    )
                    for receipt in objects(trace.get("acquisitions"))
                ],
                html.Details(
                    [
                        html.Summary("完整身份、冻结截止与来源详情"),
                        html.Pre(
                            json.dumps(document, ensure_ascii=False, indent=2, default=str),
                            className="detail-json",
                        ),
                    ]
                ),
            ]
        )
        if not trace.get("acquisitions"):
            body.append(html.P("此观测没有可用的获取回执链。"))
    return html.Div(body, className="page-stack evidence-workspace")
