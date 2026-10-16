"""The report reading surface. Every number comes from the supplied immutable set."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode

from dash import dcc, html

from pring_cycle import dashboard as view
from pring_cycle.domain.trend import TrendRules
from pring_cycle.drawer import drawer_key, drawer_panel, drawer_trigger
from pring_cycle.page_identity import identity_fields
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.retrieval import RUN_SEARCH_LIMITS
from pring_cycle.run_health import REQUEST_FAILURES, ProducerRun
from pring_cycle.runs import RunRecord
from pring_cycle.wording import CORE_STATE_LABELS, core_state_label, stage_code

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
                    conclusion_left(projection, trend_rules),
                    conclusion_right(projection),
                ],
                className="conclusion-board",
            ),
            core_table(projection, trend_rules=trend_rules),
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
        [overseas_cards(macro, projection)],
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
            history_intervals(history_days(projection, stage_events)),
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
                                [
                                    html.H2(f"{index:02d} {title}"),
                                    html.P(BOARD_SUBTITLE, className="report-subtitle")
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
                        zip(SECTIONS, bodies, strict=True), 1
                    )
                ],
                className="report-body",
            ),
        ],
        className="report-layout",
    )


BOARD_SUBTITLE = "正式阶段 · 三核心 · 确认度 · 一致性 · 库存 · 归因，一板看完"
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
    lookback = overview.get("last_confirmed_lookback")
    last_confirmed = overview.get("last_confirmed_stage")
    rows = (
        ("原因", stage_reason_line(projection)),
        (
            "上次确认",
            view._last_confirmed_label(last_confirmed, lookback)
            if last_confirmed is not None or isinstance(lookback, dict)
            # A set without a lookback record never says none (spec: 不回填).
            else ("无" if projection is None else "未提供"),
        ),
        ("转折观察", transition_watch_line(projection)),
        ("核心沿用", carry_forward_line(projection)),
        ("判法", method_line(projection, trend_rules)),
    )
    return html.Div(
        [
            html.P("正式阶段", className="section-kicker"),
            html.H2(view._stage_label(overview.get("current_stage")), className="stage-value"),
            html.Dl(
                [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
                className="board-rows",
            ),
        ],
        className="board-left",
    )


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


def stage_reason_line(projection: ProjectionSet | None) -> str:
    """Why the board shows this stage, in the three cores' own states (spec: reason line)."""
    overview = view._dataset(projection, "cycle_overview")
    cores = _cores(projection)
    stage = overview.get("current_stage")
    if stage is not None:
        return f"典型组合：{_combination(cores)} → {stage_code(stage)}"
    reason = overview.get("stage_reason") or overview.get("stage_unavailable_reason")
    if reason == "noncanonical_combination":
        return f"非典型组合：{_combination(cores)}，不在六个典型组合内；不创建 Stage VII/VIII"
    if reason in BLOCKED_REASONS:
        gaps = _core_gaps(overview)
        carried = set(_carried(overview))
        readings = [
            _core_reading(asset, cores.get(asset, {}), gaps, carried) for asset in CORE_ORDER
        ]
        return f"{BLOCKED_REASONS[str(reason)]}：" + " · ".join(readings)
    return view._stage_explanation(overview)


def transition_watch_line(projection: ProjectionSet | None) -> str:
    """Each core whose 30-day candidate or asset candidate leans off its state; it never
    changes the formal stage (GLOSSARY: 转折观察, 30 日候选方向, 资产候选状态)."""
    published = view._dataset(projection, "cycle_overview").get("transition_watch")
    if isinstance(published, list) and published:
        return view._transition_watch(published) + " · 只作观察，不改变正式阶段"
    cores = _cores(projection)
    watched = []
    for asset in CORE_ORDER:
        core = cores.get(asset)
        if core is None or core.get("state") is None:
            continue
        signs = []
        direction = core.get("candidate_30d")
        if direction != core.get("state"):
            signs.append(
                "30 日候选方向"
                + (core_state_label(direction) if direction is not None else "无")
                + (
                    f"，与当前{core_state_label(core.get('state'))}相反"
                    if direction is not None
                    else ""
                )
            )
        if core.get("candidate_state") is not None:
            signs.append("资产候选状态" + asset_candidate(core))
        if signs:
            watched.append(f"{CORE_NAMES[asset]} " + "；".join(signs))
    if watched:
        return "；".join(watched) + " · 只作观察，不改变正式阶段"
    unread = [
        CORE_NAMES[asset] for asset in CORE_ORDER if cores.get(asset, {}).get("state") is None
    ]
    if not unread:
        return "无（三核心 30 日候选均与当前状态同向）"
    if len(unread) == len(CORE_ORDER):
        return "无（三核心尚无可用状态）"
    return "无（" + "、".join(unread) + "状态不可用；其余核心 30 日候选与当前状态同向）"


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
    return (
        f"MA{trend_rules.window_days} + {trend_rules.slope_days} 日斜率定稳定牛熊，"
        f"噪声带 {trend_rules.noise_multiplier:g}×{trend_rules.volatility_days} 日波动，"
        f"持续 {trend_rules.persistence_days} 日确认，"
        f"{trend_rules.candidate_window_days} 日候选只作转折观察；"
        f"宏观与库存只做事后确认，不改写阶段 · {model}"
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
LEGACY_MACRO_STATES = ("policy_direction", "credit_response", "overheat_state", "price_pressure")


def confirmation_heading(confirmation: dict[str, Any]) -> str:
    """Whether the confirmation is assessed, over how many key indicators, by which rules."""
    summary = obj(confirmation.get("summary"))
    if not summary:
        return "该版本未提供确认汇总"
    rules = confirmation.get("macro_rules_version") or "版本未提供"
    if summary.get("applicable"):
        return f"可评估 · {summary.get('total')} 项关键指标 · 规则 {rules}"
    return f"不适用 · {summary.get('total')} 项关键指标 · 无正式阶段，不计数 · 规则 {rules}"


def dimension_cell(dimension: dict[str, Any], *, applicable: bool) -> html.Div:
    """A dimension's key indicators and their relations; never a probability."""
    label = view._DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")
    counts = obj(dimension.get("counts"))
    if dimension.get("status") != "connected" or not counts:
        return html.Div([html.Strong(label), html.Span("尚未接入")], className="summary-cell")
    total = len(objects(dimension.get("key_indicators"))) or sum(
        view._integer(value) for value in counts.values()
    )
    return html.Div(
        [
            html.Strong(label),
            html.Span(f"{total} 项" + ("" if applicable else " · 不适用")),
            html.Span(
                " · ".join(
                    f"{view._RELATION_LABELS[relation]} {view._integer(counts.get(relation))}"
                    for relation in RELATION_COUNTED
                )
            ),
        ],
        className="summary-cell",
    )


def price_consistency_line(consistency: dict[str, Any]) -> str:
    """The three pairs' relative momentum, then the stock and basket breadth, in one line."""
    if not consistency:
        return "该版本未提供"
    pairs = " · ".join(
        f"{pair.get('label')} {value:+.2f} 个百分点"
        if isinstance(value := pair.get("value_pp"), (int, float))
        else f"{pair.get('label')} 未确认"
        for pair in objects(consistency.get("relative_momentum"))
    )
    breadths = []
    for key in ("stock_breadth", "basket_breadth"):
        item = obj(consistency.get(key))
        if not item:
            continue
        if not item.get("text"):
            missing = "、".join(str(gap) for gap in view._list_of(item.get("missing")))
            breadths.append(f"{item.get('label')} 未确认，缺：{missing or '未记录'}")
        elif key == "stock_breadth" and isinstance(item.get("share"), (int, float)):
            breadths.append(f"{item.get('label')} {item['share']:.1f}%（{item['text']}）")
        elif key == "basket_breadth" and item.get("along") is not None:
            breadths.append(
                f"{item.get('label')} {item['along']}/{item.get('of')} 个分项同向（{item['text']}）"
            )
        else:
            breadths.append(f"{item.get('label')} {item['text']}")
    return "；".join(part for part in (pairs, *breadths) if part)


UNCLASSIFIED_BY = {"insufficient": "三条线缺数或月份不齐", "inconsistent": "三条线方向不构成象限"}


def inventory_quadrant_line(confirmation: dict[str, Any], inventory: dict[str, object]) -> str:
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
    return f"{quadrant}（" + "；".join(parts) + "）"


def bond_attribution_line(note: dict[str, Any]) -> str:
    """What drives the bond, by each axis's reading; a note beside it, never counted."""
    if not note:
        return "该版本未提供"
    axes = "、".join(f"{axis.get('label')}{axis.get('text')}" for axis in objects(note.get("axes")))
    return f"{note.get('text')}" + (f"：{axes}" if axes else "") + "（附注，不计数）"


def data_boundary_line(gaps: object, coverage: dict[str, Any], pinned: str) -> list[str | html.A]:
    """The gap list's size and the final plan's model metric-periods not held, with the
    way on to section 07 and the data chain."""
    missing = (
        f"{view._integer(obj(obj(coverage.get('model')).get('counts')).get('missing'))} "
        "个历史期未取到（最终计划，模型所需口径）"
        if coverage.get("available")
        else "历史期未取到：该版本未提供"
    )
    return [
        f"{len(objects(gaps))} 项缺口 · {missing} · 详见 ",
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
    rows: tuple[tuple[str, Any], ...] = (
        ("价格一致性", price_consistency_line(obj(macro.get("price_consistency")))),
        (
            "库存象限",
            inventory_quadrant_line(confirmation, view._dataset(projection, "inventory")),
        ),
        ("债券归因", bond_attribution_line(obj(macro.get("bond_attribution")))),
        (
            "数据边界",
            data_boundary_line(
                view._dataset(projection, "cycle_overview").get("gap_list"),
                obj(macro.get("coverage")),
                "?" + urlencode({"projection": projection.envelope.projection_set_id}),
            ),
        ),
    )
    return html.Div(
        [
            html.P("确认度", className="section-kicker"),
            html.H3(confirmation_heading(confirmation)),
            html.Div(
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
            html.Dl(
                [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
                className="board-rows",
            ),
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
        failures = "；".join(
            f"{adapter} {ADAPTER_FAILURES.get(outcome, outcome)}"
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
    trend = context_trend(row, projection, section)
    if isinstance(trend, str):
        return trend
    return html.Details([html.Summary("走势 / 比较端点"), *trend])


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
    "noncanonical_combination": "非典型组合",
    "canonical_combination": "典型组合",
    "insufficient_core_evidence": "核心不足",
    **BLOCKED_REASONS,
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
    calendar = drawer_key("history-calendar")
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
            html.P(drawer_trigger(calendar, "交易日历与色带等价表格")),
            drawer_panel(
                calendar,
                "交易日历与色带等价表格",
                [
                    table(
                        ("交易日", *labels, "投影版本", "更正的版本"),
                        [
                            (
                                day["date"],
                                *(history_label(day[key]) for key in kinds),
                                projection_link(day.get("projection_set_id")),
                                projection_link(obj(day.get("corrects")).get("projection_set_id"))
                                if day.get("corrects")
                                else "—",
                            )
                            for day in days
                        ],
                    )
                ],
            ),
        ]
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


def history_intervals(days: Sequence[dict[str, Any]]) -> Any:
    """Consecutive days of one state, a stage or the reason for none, as one row each."""
    runs: list[list[dict[str, Any]]] = []
    for day in days:
        if runs and runs[-1][-1]["official"] == day["official"]:
            runs[-1].append(day)
        else:
            runs.append([day])
    heading = html.H3(f"阶段区间（最近 {HISTORY_WINDOW} 个交易日）")
    if not runs:
        return html.Div(
            [
                heading,
                html.P(
                    "尚无阶段事件；首次完整投影发布后，区间会显示在这里。", className="empty-note"
                ),
            ]
        )
    # Month and day read well while the window stays in one year.
    short = len({str(day["date"])[:4] for day in days}) == 1

    def span(run: list[dict[str, Any]]) -> str:
        first, last = (str(run[0]["date"]), str(run[-1]["date"]))
        if short:
            first, last = first[5:], last[5:]
        return first if len(run) == 1 else f"{first}～{last}"

    keys = [drawer_key("history-interval", run[0]["date"]) for run in runs]
    return html.Div(
        [
            heading,
            html.Ul(
                [
                    html.Li(
                        drawer_trigger(
                            key,
                            [
                                html.Strong(span(run)),
                                html.Span(history_label(run[0]["official"])),
                                html.Span(f"{len(run)} 日"),
                                *corrected_count(run),
                            ],
                            class_name="history-interval",
                        )
                    )
                    for key, run in zip(keys, runs, strict=True)
                ],
                className="history-intervals",
            ),
            *(
                drawer_panel(
                    key,
                    f"{history_label(run[0]['official'])} · {span(run)}",
                    [html.Ul([history_day(day) for day in run], className="record-list")],
                )
                for key, run in zip(keys, runs, strict=True)
            ),
        ]
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


def history_day(day: dict[str, Any]) -> html.Li:
    """One day of an interval: its state, its event's facts, the version it corrects and why."""
    corrects = day.get("corrects")
    gaps = day.get("gaps")
    facts = (
        [
            "上一确认 "
            + (
                view._stage_label(day["last_confirmed_stage"])
                if day.get("last_confirmed_stage")
                else "尚无"
            ),
            "原因 " + history_label(day.get("stage_reason") or "未记录"),
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
            html.Strong(f"{day['date']} · {history_label(day['official'])}"),
            html.Span(" · ".join(facts), className="secondary-copy") if facts else None,
            html.Span(
                [
                    "更正版本：更正 ",
                    projection_link(corrects.get("projection_set_id")),
                    "（"
                    + (view._stage_correction_note(corrects) or str(corrects.get("reason")))
                    + "）",
                ],
                className="secondary-copy",
            )
            if isinstance(corrects, dict)
            else None,
            html.Span(["投影 ", projection_link(day.get("projection_set_id"))]),
        ],
        className="record-row",
    )


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


def _overseas_card(item: dict[str, Any], key: str) -> Any:
    metric_id = str(item.get("metric_id") or "")
    name = str(item.get("name_cn") or metric_id)
    return drawer_trigger(
        key,
        [
            html.Strong(name),
            html.Small(metric_id) if name != metric_id else None,
            html.Span(number(item.get("value"), item.get("unit")), className="card-value"),
            html.Span(str(item.get("period") or "—")),
            html.Span(_direction_arrow(item.get("direction"))),
            html.Span(["近 5 日 ", change_cell(obj(item.get("display")).get("change_5"))]),
        ],
        class_name="overseas-card",
    )


def _change_text(value: object) -> str:
    change = obj(value)
    if change.get("value") is None:
        reason = str(change.get("reason") or "旧投影未提供")
        return f"—（{REASONS.get(reason, reason)}）"
    return (
        number(change["value"], change.get("unit"))
        + f"（{change.get('start_date') or '—'} → {change.get('end_date') or '—'}）"
    )


def _source_link(reference: object) -> Any:
    label = view._source_label(reference)
    return html.A(label, href=label) if label.startswith(("https://", "http://")) else label


def _overseas_drawer(item: dict[str, Any], key: str, projection: ProjectionSet | None) -> Any:
    metric_id = str(item.get("metric_id") or "")
    display = obj(item.get("display"))
    fields: list[tuple[str, Any]] = [
        (
            "最新值",
            value_link(
                item.get("value"),
                item.get("unit"),
                item.get("selected_claim_id"),
                projection,
                section="overseas",
            ),
        ),
        (
            "统计期 / 频率",
            f"{item.get('period') or '—'} / "
            + view._state_label(item.get("frequency") or "未提供"),
        ),
        ("方向", _direction_arrow(item.get("direction"))),
        ("近 5 日", _change_text(display.get("change_5"))),
        ("近 120 日", _change_text(display.get("change_120"))),
        ("时效", view._state_label(item.get("status"))),
        ("最近获取", view._state_label(item.get("acquisition_status"))),
        ("采用来源", _source_link(item.get("source_reference"))),
        (
            "证据",
            [
                html.A(
                    "查看固定版本证据 →",
                    href=evidence_href(
                        projection, str(item["selected_claim_id"]), section="overseas"
                    ),
                )
                if projection and item.get("selected_claim_id")
                else "该版本未提供",
                f" 观测 {item['observation_id']}" if item.get("observation_id") else None,
            ],
        ),
    ]
    trend = context_trend(item, projection, "overseas")
    return drawer_panel(
        key,
        str(item.get("name_cn") or metric_id),
        [
            html.Dl(
                [part for label, value in fields for part in (html.Dt(label), html.Dd(value))],
                className="drawer-fields",
            ),
            html.H3("走势与比较端点"),
            *([html.P(trend, className="empty-note")] if isinstance(trend, str) else trend),
        ],
        code=metric_id,
    )


def overseas_cards(macro: dict[str, object], projection: ProjectionSet | None) -> Any:
    rows = objects(macro.get("international_context"))
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
    keys = _overseas_keys([*listed, *others])
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


def _overseas_keys(rows: Sequence[dict[str, Any]]) -> list[str]:
    """One drawer key per row: the metric and its member dimensions, numbered if repeated."""
    keys: list[str] = []
    for item in rows:
        dimensions = obj(item.get("dimensions"))
        key = drawer_key(
            "overseas", item.get("metric_id"), *(dimensions[name] for name in sorted(dimensions))
        )
        keys.append(key if key not in keys else f"{key}-{len(keys) + 1}")
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
