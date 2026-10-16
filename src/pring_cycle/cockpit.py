"""The report reading surface. Every number comes from the supplied immutable set."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dash import dcc, html

from pring_cycle import dashboard as view
from pring_cycle.domain.trend import TrendRules
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.run_health import ProducerRun
from pring_cycle.runs import RunRecord
from pring_cycle.wording import CORE_STATE_LABELS, core_state_label

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
}


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
    text = f"{value:,.2f}" if isinstance(value, (float, int)) else str(value)
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


def chart(display: dict[str, Any], projection: ProjectionSet, *, small: bool = False) -> Any:
    points = objects(display.get("points"))
    if not points:
        return html.P("旧投影未提供展示点列；新运行发布后可用。", className="empty-note")
    dates = [item["date"] for item in points]
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
    graph = dcc.Graph(
        figure={
            "data": traces,
            "layout": {
                "height": 74 if small else 275,
                "margin": {"l": 2 if small else 55, "r": 8, "t": 6, "b": 2 if small else 40},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#788c96", "size": 11},
                "showlegend": not small,
                "legend": {"orientation": "h", "y": 1.12},
                "xaxis": {"visible": not small, "type": "category", "nticks": 6},
                "yaxis": {"visible": not small, "title": UNITS.get(str(display.get("unit")), "")},
                "uirevision": projection.envelope.projection_set_id,
            },
        },
        config={"displayModeBar": not small, "responsive": True, "displaylogo": False},
        className="price-chart small-chart" if small else "price-chart",
    )
    if small:
        return graph
    missing = sorted({str(item["ma120_reason"]) for item in points if item.get("ma120_reason")})
    return html.Div(
        [
            graph,
            html.P(
                "实际价格与 MA120 · 120 个交易日展示窗口；均线缺值："
                + ("、".join(REASONS.get(reason, reason) for reason in missing) or "无"),
                className="secondary-copy",
            ),
            html.Details(
                [
                    html.Summary("逐日数值与证据（图表等价表格）"),
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
                                REASONS.get(
                                    str(item.get("ma120_reason")), item.get("ma120_reason") or "—"
                                ),
                            )
                            for item in points
                        ],
                    ),
                ]
            ),
        ]
    )


def change_cell(value: object) -> Any:
    change = obj(value)
    if change.get("value") is None:
        reason = str(change.get("reason") or "旧投影未提供")
        return html.Span("—", title=REASONS.get(reason, reason))
    return html.Span(
        number(change["value"], change.get("unit")),
        title=f"{change.get('start_date')} → {change.get('end_date')}",
    )


def state_tag(value: object) -> html.Span:
    """A core asset state as a 牛市 / 熊市 tag in the board's up / down state colours."""
    label = core_state_label(value)
    tone = {"牛市": "up", "熊市": "down"}.get(label, "warning")
    return html.Span(label, className=f"state-tag state-{tone}")


def candidate_cell(asset: dict[str, Any]) -> html.Div:
    """The 30-day direction and the asset candidate on two lines, never one merged duration."""
    direction = asset.get("candidate_30d")
    candidate = asset.get("candidate_state")
    days = asset.get("candidate_days")
    threshold = asset.get("persistence_required")
    return html.Div(
        [
            html.Div("30 日候选方向 " + (core_state_label(direction) if direction else "无")),
            html.Div(
                "资产候选状态 "
                + (
                    f"{core_state_label(candidate)} · "
                    f"持续 {'未提供' if days is None else f'{days} 日'} / "
                    f"门槛 {'未提供' if threshold is None else f'{threshold} 日'}"
                    if candidate
                    else "无"
                )
            ),
        ]
    )


def core_table(
    projection: ProjectionSet | None,
    *,
    section: str = "conclusion",
    trend_rules: TrendRules | None = None,
) -> Any:
    if projection is None:
        return html.P("等待首次完整运行。", className="empty-note")
    dataset = projection.datasets["core_assets"]
    displays = obj(dataset.get("display"))
    rows = []
    for asset in objects(dataset.get("assets")):
        display = obj(displays.get(str(asset.get("asset"))))
        latest = next(
            (
                point
                for point in reversed(objects(display.get("points")))
                if point.get("value") is not None
            ),
            {},
        )
        rows.append(
            (
                html.Div(
                    [
                        html.Strong(view._asset_label(str(asset.get("asset")))),
                        html.Small(str(asset.get("metric_id") or "")),
                    ]
                ),
                state_tag(asset.get("state")),
                html.Div(
                    [
                        value_link(
                            display.get("latest_value"),
                            display.get("unit"),
                            latest.get("selected_claim_id"),
                            projection,
                            section=section,
                        ),
                        html.Small(str(display.get("latest_date") or "旧投影未提供")),
                    ]
                ),
                number(asset.get("distance_pct"), "percent"),
                number(asset.get("slope_pct"), "percent"),
                candidate_cell(asset),
                change_cell(display.get("change_5")),
                change_cell(display.get("change_120")),
                chart(display, projection, small=True),
            )
        )
    return table(
        (
            "三核心",
            "状态",
            "最新",
            f"距 MA{trend_rules.window_days}" if trend_rules else "距均线",
            f"{trend_rules.slope_days} 日斜率" if trend_rules else "斜率",
            "候选",
            "近 5 日",
            "近 120 日",
            "120 日走势",
        ),
        rows,
        class_name="report-table core-table",
    )


def report_board(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
    stage_events: Sequence[dict[str, object]] = (),
    *,
    producer_run: ProducerRun | None = None,
    trend_rules: TrendRules | None = None,
) -> html.Div:
    """``producer_run`` carries the producing run's persisted health summary for the board's
    run facts; ``None`` (or a ``None`` summary) means the page must say it is unavailable."""
    overview = view._dataset(projection, "cycle_overview")
    macro = view._dataset(projection, "macro")
    displays = obj(view._dataset(projection, "core_assets").get("display"))
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
                    html.Div(
                        [
                            html.P("正式阶段", className="section-kicker"),
                            html.H2(
                                view._stage_label(overview.get("current_stage")),
                                className="stage-value",
                            ),
                            html.P(view._stage_explanation(overview)),
                            *view._carry_forward_notice(overview.get("core_carry_forward")),
                        ]
                    ),
                    html.Div(
                        [
                            html.P("上一确认阶段", className="section-kicker"),
                            html.Strong(
                                view._last_confirmed_label(
                                    overview.get("last_confirmed_stage"),
                                    overview.get("last_confirmed_lookback"),
                                )
                            ),
                            html.P("历史背景；正式结论以本次三核心稳定方向为准。"),
                        ]
                    ),
                ],
                className="conclusion-board",
            ),
            html.P(
                "转折观察 · 不改变正式阶段："
                + view._transition_watch(overview.get("transition_watch"))
            ),
            html.H3("五维确认度（关键指标计数，非概率）"),
            confirmation_summary(macro),
            html.P(
                "库存象限："
                + view._state_label(view._dataset(projection, "inventory").get("quadrant"))
            ),
            html.Details([html.Summary("价格内部一致性"), *view._price_sections(macro)]),
            *[
                html.P(line, className="secondary-copy")
                for line in view._attribution_lines(macro, brief=True)
            ],
            core_table(projection, trend_rules=trend_rules),
            html.P(
                [
                    "解读：",
                    html.A("阅读同投影报告", href=pinned + "#reading")
                    if report
                    else "报告尚未生成",
                ]
            ),
            html.A("查看运行摘要与数据边界 →", href="/runs" + pinned),
        ],
        [
            *[
                html.Article(
                    [
                        html.H3(view._asset_label(asset)),
                        chart(obj(displays.get(asset)), projection),
                        html.P(
                            "噪声带："
                            + " · ".join(
                                number(row.get("noise_band_pct"), "percent")
                                for row in objects(
                                    view._dataset(projection, "core_assets").get("assets")
                                )
                                if row.get("asset") == asset
                            )
                            + "；MA120 仅在完整 120 个实际交易日价格齐备时显示。"
                        ),
                        related_assets(macro, asset, projection),
                    ],
                    className="asset-block",
                )
                for asset in ("bond", "stock", "commodity")
                if projection
            ],
            *view._price_sections(macro),
            *view._attribution_sections(macro),
        ],
        [international_table(macro, projection)],
        [
            html.P(view._confirmation_scope(confirmation)),
            confirmation_tables(confirmation, projection),
        ]
        if confirmation
        else [view._macro_page(projection)],
        [
            inventory_lines(confirmation, projection),
            warrant_table(projection),
            view._inventory_page(projection),
        ],
        [
            html.P("正式阶段由债券、股票、商品的 120 日稳定方向映射；宏观事实只做事后确认。"),
            stage_bands(projection),
            view._stage_history_page(projection, stage_events if projection is None else ()),
            html.A("本投影解读 →", href=pinned + "#reading"),
        ],
        [
            html.H3("完整度与缺期"),
            coverage_table(obj(macro.get("coverage"))),
            *view._freshness_basis(projection),
            view._gap_list(overview.get("gap_list")) if projection else html.P("尚无分析投影。"),
            html.P(
                [
                    html.A("发布日历", href="/release-calendar" + pinned),
                    " · ",
                    html.A("数据链路与证据", href="/data-chain" + pinned),
                ]
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
            view._report_reader(report) if report else html.P("报告尚未生成，或旧投影未提供解读。"),
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
    return html.Div(
        [
            html.Nav(
                [
                    html.A([html.Span(f"{index:02d}"), title], href=pinned + "#" + key)
                    for index, (key, title) in enumerate(SECTIONS, 1)
                ],
                className="report-toc",
                **cast(Any, {"aria-label": "报告目录"}),
            ),
            html.Div(
                [
                    html.Section(
                        [
                            html.Header(
                                [html.H2(f"{index:02d} {title}")], className="report-heading"
                            ),
                            *body,
                        ],
                        id=key,
                        className="report-section",
                    )
                    for index, ((key, title), body) in enumerate(
                        zip(SECTIONS, bodies, strict=True), 1
                    )
                ],
                className="report-body",
            ),
        ],
        className="report-layout",
    )


def confirmation_summary(macro: dict[str, object]) -> Any:
    confirmation = obj(macro.get("confirmation"))
    summary = obj(confirmation.get("summary"))
    if not summary:
        return view._macro_summary(macro)
    counts = obj(summary.get("counts"))
    return html.Div(
        [
            html.P(
                "确认度不适用：本次无正式阶段；各项事实仍可阅读。"
                if not summary.get("applicable")
                else " · ".join(
                    f"{view._RELATION_LABELS.get(key, key)} {value} 项"
                    for key, value in counts.items()
                )
                + f" · 共 {summary.get('total')} 项"
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Strong(
                                view._DIMENSION_LABELS.get(str(item.get("dimension")), "维度")
                            ),
                            html.P(view._dimension_counts(item)),
                        ],
                        className="summary-cell",
                    )
                    for item in objects(confirmation.get("dimensions"))
                ],
                className="confirmation-summary",
            ),
            html.Details([html.Summary("逐项确认关系"), view._macro_summary(macro)]),
        ]
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
        config={"displayModeBar": False, "responsive": True},
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


def confirmation_tables(confirmation: dict[str, Any], projection: ProjectionSet | None) -> Any:
    groups = []
    for dimension in objects(confirmation.get("dimensions")):
        indicators = objects(dimension.get("key_indicators"))
        groups.append(
            html.Div(
                [
                    html.H3(view._DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")),
                    html.P(view._dimension_counts(dimension)),
                    table(
                        ("关键指标", "确认关系", "读取期", "依据与缺口"),
                        [
                            (
                                item.get("name"),
                                view._RELATION_LABELS.get(str(item.get("relation")), "未知"),
                                item.get("statistical_period") or "未提供",
                                html.Details(
                                    [
                                        html.Summary("展开主辅成员、命题与成熟度"),
                                        member_readings(
                                            objects(item.get("members")),
                                            projection,
                                            section="confirmation",
                                        ),
                                        view._indicator_card(item),
                                    ]
                                ),
                            )
                            for item in indicators
                        ],
                    ),
                ]
            )
        )
    return html.Div(groups)


def inventory_lines(confirmation: dict[str, Any], projection: ProjectionSet | None) -> Any:
    indicators = [
        item
        for dimension in objects(confirmation.get("dimensions"))
        if dimension.get("dimension") == "inventory"
        for item in objects(dimension.get("key_indicators"))
    ]
    if not indicators:
        return html.P("当前投影未提供三线读取结果。")
    members = [
        member
        for item in indicators
        for member in objects(item.get("members"))
        if member.get("line")
    ]
    return html.Div(
        [
            html.H3("需求、生产、库存三线 · 象限仅计一项"),
            *[
                html.Section(
                    [
                        html.H4(label),
                        member_readings(
                            [member for member in members if member.get("line") == key],
                            projection,
                            section="inventory",
                        ),
                    ]
                )
                for key, label in (
                    ("demand", "需求线"),
                    ("production", "生产线"),
                    ("inventory", "库存线"),
                )
            ],
        ]
    )


def related_assets(macro: dict[str, object], asset: str, projection: ProjectionSet) -> Any:
    cores = objects(obj(macro.get("observation_interfaces")).get("cores"))
    members = [
        member
        for core in cores
        if core.get("core") == asset
        for member in objects(core.get("members"))
    ]
    if not members:
        return html.P("当前模型未登记同类观察接口。", className="secondary-copy")
    rows = []
    for member in members:
        for evidence in objects(member.get("evidence")) or [{}]:
            rows.append(
                (
                    member.get("label"),
                    value_link(
                        evidence.get("value"),
                        evidence.get("unit"),
                        evidence.get("selected_claim_id"),
                        projection,
                    ),
                    evidence.get("period") or "—",
                    change_cell(obj(obj(evidence.get("display")).get("change_5"))),
                    change_cell(obj(obj(evidence.get("display")).get("change_120"))),
                    context_chart(evidence, projection, "assets"),
                    view._state_label(evidence.get("direction")),
                    view._state_label(evidence.get("status")),
                    view._state_label(member.get("reads_as"))
                    if member.get("reads_as")
                    else "仅观察，不计数",
                )
            )
    return table(
        (
            "同类观察",
            "值 / 单位",
            "统计期",
            "近 5 日",
            "近 120 日",
            "真实期次走势",
            "方向",
            "时效",
            "用途（不重复计数）",
        ),
        rows,
    )


def coverage_table(coverage: dict[str, Any]) -> Any:
    if not coverage.get("available"):
        return html.P("该版本未提供最终需求计划的两种完整度口径。")
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


def warrant_table(projection: ProjectionSet | None) -> Any:
    warrants = obj(view._dataset(projection, "inventory").get("registered_warrants"))
    if not warrants:
        return html.P("本投影未提供分品种仓单变化。")
    return html.Div(
        [
            html.H3("分品种注册仓单（附注，不重复计数）"),
            html.P(
                f"真实比较期：{warrants.get('first_day') or '—'} → "
                f"{warrants.get('last_day') or '—'}"
            ),
            table(
                ("品种", "起点 / 单位", "终点 / 单位", "变化", "状态", "原始输入"),
                [
                    (
                        item.get("symbol"),
                        number(item.get("first"), item.get("unit")),
                        number(item.get("last"), item.get("unit")),
                        f"{item['change_rate']:+.2%}"
                        if item.get("change_rate") is not None
                        else "—",
                        view._WARRANT_STATES.get(str(item.get("status")), str(item.get("status"))),
                        html.Div(
                            [
                                html.A(
                                    f"{label} {i + 1} ",
                                    href=evidence_href(projection, version, section="inventory"),
                                )
                                for key, label in (
                                    ("first_claim_ids", "起点"),
                                    ("last_claim_ids", "终点"),
                                )
                                for i, version in enumerate(item.get(key, []))
                            ]
                        )
                        if projection
                        else "—",
                    )
                    for item in objects(warrants.get("symbols"))
                ],
            ),
        ]
    )


def context_chart(row: dict[str, Any], projection: ProjectionSet | None, section: str) -> Any:
    display = obj(row.get("display"))
    points = objects(display.get("points"))
    if not points:
        return "尚无可用点列" if display else "该版本未提供"
    return html.Details(
        [
            html.Summary("走势 / 比较端点"),
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
                                evidence_href(
                                    projection, point["selected_claim_id"], section=section
                                )
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
    )


HISTORY_LABELS = {
    "unpublished": "未发布",
    "unavailable": "不可用",
    **CORE_STATE_LABELS,
    "undetermined": "待定",
    "unknown": "未知",
    "noncanonical_combination": "非典型组合",
    "insufficient_core_evidence": "核心不足",
}


def history_label(value: object) -> str:
    text = str(value)
    return HISTORY_LABELS.get(text, view._stage_label(value) if text.startswith("stage_") else text)


def stage_bands(projection: ProjectionSet | None) -> Any:
    display = obj(view._dataset(projection, "stage_history").get("display"))
    days = objects(display.get("days"))
    if not days:
        return html.P("旧投影未提供对齐的交易日色带；历史事件仍可阅读。")
    kinds = ("official", "bond", "stock", "commodity")
    labels = ("正式阶段", "债券", "股票", "商品")
    categories = list(dict.fromkeys(str(day[key]) for day in days for key in kinds))
    colors = [
        "#36566b",
        "#278a96",
        "#c58b42",
        "#747d9a",
        "#976269",
        "#668c7a",
        "#9c8b59",
        "#647487",
    ]
    graph = dcc.Graph(
        figure={
            "data": [
                {
                    "type": "heatmap",
                    "x": [day["date"] for day in days],
                    "y": labels,
                    "z": [[categories.index(str(day[key])) for day in days] for key in kinds],
                    "text": [[history_label(day[key]) for day in days] for key in kinds],
                    "colorscale": [
                        [i / max(1, len(categories) - 1), colors[i % len(colors)]]
                        for i in range(len(categories))
                    ],
                    "zmin": 0,
                    "zmax": max(1, len(categories) - 1),
                    "showscale": False,
                    "ygap": 5,
                    "hovertemplate": "%{x} · %{y}<br>%{text}<extra></extra>",
                }
            ],
            "layout": {
                "height": 210,
                "margin": {"l": 70, "r": 8, "t": 10, "b": 35},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#788c96"},
                "xaxis": {"type": "category", "nticks": 8},
                "yaxis": {"autorange": "reversed"},
            },
        },
        config={"displayModeBar": False},
    )
    return html.Div(
        [
            graph,
            html.P(
                "正式阶段日数："
                + " · ".join(
                    f"{history_label(key)} {value} 日"
                    for key, value in obj(display.get("counts")).items()
                )
            ),
            html.Details(
                [
                    html.Summary("交易日历与色带等价表格"),
                    table(
                        ("交易日", *labels, "投影版本", "修正记录"),
                        [
                            (
                                day["date"],
                                *(history_label(day[key]) for key in kinds),
                                html.A(
                                    day["projection_set_id"],
                                    href="/?"
                                    + urlencode({"projection": day["projection_set_id"]})
                                    + "#history",
                                )
                                if day.get("projection_set_id")
                                else "未发布",
                                str(day.get("corrects") or "—"),
                            )
                            for day in days
                        ],
                    ),
                ]
            ),
        ]
    )


def international_table(macro: dict[str, object], projection: ProjectionSet | None) -> Any:
    rows = objects(macro.get("international_context"))
    if not rows:
        return html.P("本投影尚无海外与汇率事实。", className="empty-note")
    return table(
        (
            "指标",
            "值 / 单位",
            "方向",
            "统计期 / 频率",
            "近 5 日",
            "近 120 日",
            "真实期次走势",
            "时效",
            "最近获取",
            "采用来源",
        ),
        [
            (
                item.get("name_cn", item.get("metric_id")),
                value_link(
                    item.get("value"),
                    item.get("unit"),
                    item.get("selected_claim_id"),
                    projection,
                    section="overseas",
                ),
                view._state_label(item.get("direction")),
                f"{item.get('period') or '—'} / "
                + view._state_label(item.get("frequency") or "未提供"),
                change_cell(obj(item.get("display")).get("change_5")),
                change_cell(obj(item.get("display")).get("change_120")),
                context_chart(item, projection, "overseas"),
                view._state_label(item.get("status")),
                view._state_label(item.get("acquisition_status")),
                view._source_label(item.get("source_reference")),
            )
            for item in rows
        ],
    )


def local_time(value: datetime) -> str:
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S 北京时间")


_COMPLETENESS = {"complete": "完整", "degraded": "降级"}


def identity_strip(
    projection: ProjectionSet | None,
    *,
    producer: ProducerRun | None,
    rendered_at: datetime,
) -> list[Any]:
    """The seven identity fields of the page; all belong to ``projection``, never the pointer."""
    run = producer.run_id if producer else "未提供"
    generated = local_time(rendered_at)
    if projection is None:
        return [
            view._metadata("目标交易日", "尚无"),
            view._metadata("模型版本", "尚无"),
            view._metadata("投影", "等待首次完整运行"),
            view._metadata("完整度", "尚无"),
            view._metadata("分析截止", "尚无"),
            view._metadata("运行", run),
            view._metadata("页面生成", generated),
        ]
    envelope = projection.envelope
    return [
        view._metadata("目标交易日", envelope.target_business_date),
        view._metadata("模型版本", envelope.model_version_id),
        view._metadata("投影", envelope.projection_set_id),
        view._metadata("完整度", _COMPLETENESS.get(envelope.completeness, envelope.completeness)),
        view._metadata("分析截止", local_time(envelope.system_as_of)),
        view._metadata("运行", run),
        view._metadata("页面生成", generated),
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
