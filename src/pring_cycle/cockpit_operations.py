"""Operational views of recorded requests and attempts, separate from analysis identity."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dash import dcc, html

from pring_cycle import dashboard as view
from pring_cycle.cockpit import coverage_table, name_cell, number, obj, objects, table
from pring_cycle.page_identity import local_time
from pring_cycle.run_health import comparison, filtered_flow
from pring_cycle.runs import RunRecord
from pring_cycle.wording import display_name, source_name

DIAGNOSES = {
    "adopted": "本投影已采用",
    "held": "已持有",
    "not_published": "等待发布",
    "release_gate": "发布门禁跳过",
    "flow_stopped": "流程终止前未完成",
    "rejected": "交付被拒收",
    "request_failed": "请求失败",
    "budget_stopped": "预算终止",
    "not_delivered": "已请求但未交付应有期",
    "reason_not_recorded": "原因未记录",
}

LABELS = {
    "manual_full": "手动完整运行",
    "scheduled_full": "计划完整运行",
    "report_generation": "报告生成",
    "targeted_refresh": "定向更新",
    "manual_deep_search": "人工深搜",
    "queued": "排队",
    "running": "运行中",
    "completed": "已完成",
    "cancelled": "已取消",
    "failed": "失败",
    "action_required": "需要处理",
    "interrupted": "已中断",
    "degraded": "降级可用",
    "completed_degraded": "确定性模板",
    "complete": "完整",
    "verified": "已验证",
    "ingested": "已入库",
    "received": "已接收",
    "accepted": "已接纳",
    "validated": "校验通过",
    "direct_core_refresh": "三核心取数",
    "direct_context_refresh": "背景指标取数",
    "release_schedule": "发布日历",
    "tushare_news": "资讯取数",
    "gap_retrieval": "缺期补取",
    "not_attempted": "未尝试",
    "budget_exhausted": "预算耗尽",
    "not_configured": "未配置",
    "retrieval": "补缺",
    "none": "无需操作",
    "resume_required": "确认后恢复",
}


def label_value(value: object) -> str:
    return LABELS.get(str(value), view._state_label(value))


# What a request came to, in Chinese, and the colour family its Sankey links take.
FLOW_RESULTS = {
    "accepted": ("已接纳", "success"),
    "verified": ("已验证", "success"),
    "validated": ("校验通过", "success"),
    "candidate_source": ("候选来源", "candidate"),
    "not_found": ("未找到", "neutral"),
    "started": ("已开始", "neutral"),
    "reserved": ("已预留", "neutral"),
    "unknown_completion": ("完成情况未知", "neutral"),
    "completed": ("已完成", "neutral"),
    "received": ("已接收", "neutral"),
    "failed": ("失败", "failure"),
    "interrupted": ("已中断", "failure"),
    "timeout": ("超时", "failure"),
    "error": ("出错", "failure"),
    "rejected": ("已拒绝", "failure"),
}


def flow_result(value: object) -> tuple[str, str]:
    """A request result's Chinese name and colour family; unmapped values stay raw and grey."""
    return FLOW_RESULTS.get(str(value), (str(value), "neutral"))


# Sources sending fewer than two requests share one node, so the chart does not splinter.
OTHER_SOURCE = "source"
# The figure starts in one neutral grey; dashboard.js paints each node and link from the
# theme's --flow-* variables (report.css), by the colour family recorded in the trace meta.
FLOW_FALLBACK = "rgba(128, 134, 138, 0.35)"


def flow_sankey(requests: Sequence[dict[str, Any]]) -> Any:
    """Requests as source → phase → result, each node named in Chinese with its count.

    Links are split by result so each takes the colour of what its requests came to.
    """
    sources = Counter(str(item["channel"]) for item in requests)
    small = {source for source, count in sources.items() if count < 2}
    folded = small if len(small) > 1 else set()
    columns: list[Counter[str]] = [Counter(), Counter(), Counter()]
    links: Counter[tuple[str, str, str]] = Counter()
    for item in requests:
        channel, result = str(item["channel"]), str(item["result"])
        path = (
            OTHER_SOURCE if channel in folded else "source:" + channel,
            "phase:" + str(item["phase"]),
            "result:" + result,
        )
        for column, node in zip(columns, path, strict=True):
            column[node] += 1
        links[path[0], path[1], result] += 1
        links[path[1], path[2], result] += 1
    names: dict[str, Callable[[object], str]] = {
        "source": source_name,
        "phase": label_value,
        "result": lambda value: flow_result(value)[0],
    }
    nodes = [
        node
        for column in columns
        for node, _ in sorted(
            column.items(), key=lambda entry: (entry[0] == OTHER_SOURCE, -entry[1], entry[0])
        )
    ]
    counts = {node: count for column in columns for node, count in column.items()}

    def label(node: str) -> str:
        if node == OTHER_SOURCE:
            return f"其他 {len(folded)} 个来源 · {counts[node]}"
        kind, _, value = node.partition(":")
        return f"{names[kind](value)} · {counts[node]}"

    def share(count: int) -> str:
        return f"{count} 次请求 · 占比 {count / len(requests):.1%}"

    def node_hover(node: str) -> str:
        if node != OTHER_SOURCE:
            return share(counts[node])
        members = "、".join(source_name(source) for source in sources if source in folded)
        return f"{members} · {share(counts[node])}"

    node_columns = [node.partition(":")[0] for node in nodes]
    link_tones = [flow_result(result)[1] for _, _, result in links]
    return dcc.Graph(
        figure={
            "data": [
                {
                    "type": "sankey",
                    "meta": {"node_columns": node_columns, "link_tones": link_tones},
                    "node": {
                        "label": [label(node) for node in nodes],
                        "color": [FLOW_FALLBACK] * len(nodes),
                        "customdata": [node_hover(node) for node in nodes],
                        "hovertemplate": "%{label}<br>%{customdata}<extra></extra>",
                        "pad": 16,
                    },
                    "link": {
                        "source": [nodes.index(source) for source, _, _ in links],
                        "target": [nodes.index(target) for _, target, _ in links],
                        "value": list(links.values()),
                        "color": [FLOW_FALLBACK] * len(link_tones),
                        "customdata": [
                            f"{flow_result(result)[0]} · {share(value)}"
                            for (_, _, result), value in links.items()
                        ],
                        "hovertemplate": (
                            "%{source.label} → %{target.label}<br>%{customdata}<extra></extra>"
                        ),
                    },
                }
            ],
            "layout": {
                "height": 420,
                "margin": {"l": 8, "r": 8, "t": 12, "b": 12},
                "paper_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#788c96"},
            },
        },
        config={"displayModeBar": False},
        className="flow-sankey",
    )


def metric_names(metric_ids: Sequence[str]) -> list[Any]:
    """Request metrics by Chinese name, each code on hover, joined as one cell."""
    names = [name_cell(display_name(metric_id)) for metric_id in metric_ids]
    return [
        part for index, name in enumerate(names) for part in (("、",) if index else ()) + (name,)
    ]


def filter_form(path: str, query: dict[str, str], options: dict[str, tuple[str, list[str]]]) -> Any:
    return html.Form(
        [
            *[
                dcc.Input(type="hidden", name=key, value=value)
                for key, value in query.items()
                if key not in options
                and key
                in {
                    "projection",
                    "version",
                    "return",
                    "run",
                    "type",
                    "status",
                    "channel",
                    "phase",
                    "result",
                    "metric",
                    "q",
                    "trail",
                }
            ],
            *[
                html.Label(
                    [
                        label,
                        html.Select(
                            [
                                html.Option("全部", value="", selected=not query.get(key)),
                                *[
                                    html.Option(
                                        label_value(value),
                                        value=value,
                                        selected=query.get(key) == value,
                                    )
                                    for value in values
                                ],
                            ],
                            name=key,
                        ),
                    ]
                )
                for key, (label, values) in options.items()
            ],
            html.Button("应用筛选", type="submit", className="quiet-button"),
            html.A(
                "清空",
                href=path
                + "?"
                + urlencode(
                    {key: value for key, value in query.items() if key in {"projection", "run"}}
                ),
            ),
        ],
        action=path,
        method="get",
        className="filter-bar",
    )


def run_picker(runs: Sequence[RunRecord], query: dict[str, str], path: str) -> Any:
    return filter_form(path, query, {"run": ("运行", [run.run_id for run in runs])})


def measure_bars(rows: Sequence[tuple[str, float | None]], unit: str) -> Any:
    longest = max((value for _, value in rows if value is not None), default=0) or 1
    return html.Ul(
        [
            html.Li(
                [
                    html.Span(label, className="measure-label"),
                    html.Span(
                        html.Span(
                            className="measure-fill",
                            style={"width": f"{max(0, value) / longest * 100:.4f}%"},
                        )
                        if value is not None
                        else None,
                        className="measure-track",
                        **cast(Any, {"aria-hidden": "true"}),
                    ),
                    html.Strong(
                        "未记录"
                        if value is None
                        else (f"{value:g}" if unit == "次" else number(value)) + " " + unit,
                        className="measure-value",
                    ),
                ],
                className="measure-row",
            )
            for label, value in rows
        ],
        className="measure-bars",
    )


def runs_workspace(
    runs: Sequence[RunRecord],
    summary: dict[str, Any] | None,
    history: list[dict[str, Any]],
    query: dict[str, str],
) -> Any:
    filtered = [
        run
        for run in runs
        if (not query.get("type") or run.command_type == query["type"])
        and (not query.get("status") or run.status == query["status"])
    ]
    trend = [
        item
        for item in history
        if (not query.get("type") or item["command_type"] == query["type"])
        and (not query.get("status") or item["status"] == query["status"])
    ]
    trend_times = [
        datetime.fromisoformat(str(item["started_at"]))
        .astimezone(ZoneInfo("Asia/Shanghai"))
        .replace(tzinfo=None)
        .isoformat()
        for item in reversed(trend)
    ]
    body: list[Any] = [
        html.H1("运行状态"),
        html.P("运行中约 30 秒刷新，空闲约 300 秒刷新。报告任务与完整取数分开比较。"),
        html.Div(
            [
                filter_form(
                    "/runs",
                    query,
                    {
                        "type": ("类型", sorted({run.command_type for run in runs})),
                        "status": ("状态", sorted({run.status for run in runs})),
                    },
                ),
                run_picker(filtered, query, "/runs"),
            ],
            className="run-filters",
        ),
    ]
    if summary:
        previous = comparison(summary, history)
        # The summary contains physical request identities, not one row per delivered metric.
        requests = {item["request_id"]: item for item in summary.get("requests", [])}
        phases = Counter(str(item.get("phase") or "环节未记录") for item in requests.values())
        body.extend(
            [
                html.Div(
                    [
                        html.P(
                            f"运行 {summary['run_id']} · 第 {summary['attempt']} 次尝试 · "
                            f"{label_value(summary['status'])}"
                        ),
                        html.P(
                            "本次投影：" + str(summary.get("projection_set_id") or "尚未发布新投影")
                        ),
                        html.P("下一步：" + label_value(summary.get("next_action") or "无需操作")),
                    ],
                    className="run-identity",
                ),
                html.Div(
                    [
                        html.Div(
                            [html.Small(label), html.Strong(str(value))], className="health-card"
                        )
                        for label, value in (
                            ("本次尝试耗时（秒，含排队）", number(summary.get("duration_seconds"))),
                            ("整次运行外部请求", summary["request_count"]),
                            ("运行状态", label_value(summary["status"])),
                            ("投影完整度", label_value(summary.get("completeness") or "未发布")),
                            ("报告状态", label_value(summary.get("report_status") or "未生成")),
                            (
                                "未完成期",
                                sum(
                                    value
                                    for key, value in summary.get("gap_counts", {}).items()
                                    if key not in {"held", "adopted"}
                                )
                                if summary.get("final_plan_available")
                                else "未形成最终计划",
                            ),
                        )
                    ],
                    className="health-grid",
                ),
                html.Details(
                    [
                        html.Summary("数据完整度与未完成期口径"),
                        coverage_table(obj(summary.get("coverage"))),
                    ],
                    className="operations-details",
                ),
                html.P(
                    "对比 "
                    + str(previous["run_id"])
                    + "：耗时变化 "
                    + number(previous.get("duration_delta_seconds"))
                    + " 秒；请求变化 "
                    + number(previous.get("request_delta"))
                    if previous.get("run_id")
                    else "无可比的留存摘要：须同类型、模型、目录和计数口径。"
                ),
                html.Section(
                    [
                        html.H2("本次运行各环节"),
                        html.P(
                            "条长按最长环节对齐；下方可展开起止时间。", className="secondary-copy"
                        ),
                        measure_bars(
                            [
                                (label_value(item["step"]), item.get("seconds"))
                                for item in summary.get("segments", [])
                            ],
                            "秒",
                        )
                        if summary.get("segments")
                        else html.P("本次未记录环节耗时。"),
                    ],
                    className="operations-panel",
                ),
                html.Details(
                    [
                        html.Summary("环节起止时间（北京时间）"),
                        table(
                            ("步骤", "开始", "结束", "秒"),
                            [
                                (
                                    label_value(item["step"]),
                                    local_time(datetime.fromisoformat(item["started_at"])),
                                    local_time(datetime.fromisoformat(item["ended_at"]))
                                    if item.get("ended_at")
                                    else "进行中 / 未记录",
                                    number(item.get("seconds")),
                                )
                                for item in summary.get("segments", [])
                            ],
                        ),
                    ],
                    className="operations-details",
                ),
                html.Section(
                    [
                        html.H2("请求按环节"),
                        html.P(
                            "一次外部请求只计一次；重试单列，缓存复用不计入。",
                            className="secondary-copy",
                        ),
                        measure_bars(
                            [
                                (label_value(phase), float(count))
                                for phase, count in phases.most_common()
                            ],
                            "次",
                        )
                        if phases
                        else html.P("本次没有已发送的外部请求。"),
                    ],
                    className="operations-panel",
                ),
                html.P(
                    "预算消耗："
                    + " · ".join(
                        f"{key} {value}" for key, value in summary.get("budget", {}).items()
                    )
                ),
                html.P(
                    "时效分布（指标数）："
                    + (
                        " · ".join(
                            f"{label_value(key)} {value}"
                            for key, value in summary.get("freshness_counts", {}).items()
                        )
                        or "本次未记录"
                    )
                ),
                html.A(
                    "查看这次运行的取数流向 →",
                    href="/data-chain?"
                    + urlencode(
                        {
                            **{key: value for key, value in query.items() if key == "projection"},
                            "run": summary["run_id"],
                        }
                    ),
                ),
            ]
        )
    else:
        body.append(html.P("尚无运行，或旧运行没有留存健康摘要；不回写推测历史。"))
    body.extend(
        [
            html.H2("留存期趋势"),
            dcc.Graph(
                figure={
                    "data": [
                        {
                            "type": "scatter",
                            "mode": "lines+markers",
                            "name": "尝试耗时（秒，含排队）",
                            "x": trend_times,
                            "y": [item.get("duration_seconds") for item in reversed(trend)],
                        },
                        {
                            "type": "scatter",
                            "mode": "lines+markers",
                            "name": "运行累计请求",
                            "yaxis": "y2",
                            "x": trend_times,
                            "y": [item.get("request_count") for item in reversed(trend)],
                        },
                    ],
                    "layout": {
                        "height": 240,
                        "paper_bgcolor": "rgba(0,0,0,0)",
                        "plot_bgcolor": "rgba(0,0,0,0)",
                        "font": {"color": "#788c96"},
                        "xaxis": {"title": "尝试开始（北京时间）"},
                        "yaxis": {"rangemode": "nonnegative"},
                        "yaxis2": {
                            "overlaying": "y",
                            "side": "right",
                            "rangemode": "nonnegative",
                            "tickformat": "d",
                            "dtick": 1
                            if max(item.get("request_count", 0) for item in trend) < 5
                            else None,
                        },
                    },
                },
                config={"displayModeBar": False},
            )
            if trend
            else None,
            table(
                ("运行 / 类型", "状态", "耗时（秒）", "外部请求", "模型 / 目录"),
                [
                    (
                        html.A(
                            item["run_id"] + " · " + label_value(item["command_type"]),
                            href="/runs?" + urlencode({**query, "run": item["run_id"]}),
                        ),
                        label_value(item["status"]),
                        number(item.get("duration_seconds")),
                        item["request_count"],
                        item["model_version_id"] + " / " + str(item.get("catalog_version")),
                    )
                    for item in trend
                ],
            )
            if trend
            else html.P("当前筛选无留存摘要。"),
            html.H2("操作与运行记录"),
            view._runs_page(filtered),
        ]
    )
    return html.Div(body, className="operations-workspace")


def data_chain(
    runs: Sequence[RunRecord],
    selected: RunRecord | None,
    summary: dict[str, Any] | None,
    query: dict[str, str],
    evidence: Any,
) -> Any:
    body: list[Any] = [html.H1("数据链路"), run_picker(runs, query, "/data-chain")]
    if selected is None or summary is None:
        body.append(
            html.P(
                "旧运行没有留存健康摘要，真实请求数口径不可用；以下保留原有尝试记录。"
                if selected
                else "当前没有可展示的运行记录。"
            )
        )
        if selected:
            body.append(view._runs_page([selected]))
        body.append(evidence)
        return html.Div(body, className="operations-workspace")
    requests = summary.get("requests", [])
    flow = filtered_flow(summary, query)
    request_ids = {item["request_id"] for item in flow["requests"]}
    scoped_requests = any(query.get(key) for key in ("phase", "result"))
    scoped_gaps = {gap_id for item in flow["requests"] for gap_id in item.get("gap_ids", [])}
    ledger_gaps = objects(obj(selected.retrieval_ledger).get("gaps"))
    if query.get("metric") and not any(query.get(key) for key in ("channel", "phase", "result")):
        scoped_gaps.update(
            item["gap_id"] for item in ledger_gaps if item["metric_id"] == query["metric"]
        )
    filtering = any(query.get(key) for key in ("channel", "phase", "result", "metric"))
    requirements = [
        item
        for item in summary.get("gaps", [])
        if (not query.get("metric") or item["metric_id"] == query["metric"])
        and (
            not any(query.get(key) for key in ("channel", "phase", "result"))
            or request_ids.intersection(item["request_ids"])
        )
    ]
    page_count = max(1, (len(requirements) + 99) // 100)
    try:
        gap_page = min(page_count, max(1, int(query.get("gap_page", "1"))))
    except ValueError:
        gap_page = 1
    page_requirements = requirements[(gap_page - 1) * 100 : gap_page * 100]
    body.extend(
        [
            html.P(
                f"运行 {selected.run_id} · {label_value(selected.status)} · 本次投影 "
                + str(selected.projection_set_id or "尚未发布")
                + "；下方分析证据沿用所选分析投影。"
            ),
            filter_form(
                "/data-chain",
                query,
                {
                    "channel": ("来源", sorted({item["channel"] for item in requests})),
                    "phase": ("环节", sorted({item["phase"] for item in requests})),
                    "result": ("结果", sorted({item["result"] for item in requests})),
                    "metric": (
                        "指标",
                        sorted(
                            {metric for item in requests for metric in item["metric_ids"]}
                            | {item["metric_id"] for item in summary.get("gaps", [])}
                        ),
                    ),
                },
            ),
            html.H2(f"取数流向 · {flow['count']} 次真实请求"),
            html.P(
                "一请求多声明只计一次；重试分别计数，缓存复用和未发请求不计入。零失败不代表数据完整。"
            ),
        ]
    )
    if flow["requests"]:
        body.append(flow_sankey(flow["requests"]))
    else:
        body.append(html.P("无匹配请求；清空筛选可返回全部记录。"))
    body.extend(
        [
            html.Div(
                table(
                    ("请求", "来源 / 环节", "结果", "指标", "来源行 / 入库声明"),
                    [
                        (
                            item["request_id"],
                            [
                                html.Span(source_name(item["channel"]), title=item["channel"]),
                                " / " + label_value(item["phase"]),
                            ],
                            flow_result(item["result"])[0]
                            + " · "
                            + str(item.get("classification") or "—"),
                            metric_names(item["metric_ids"]),
                            number(item.get("source_record_count"))
                            + " / "
                            + number(item.get("claim_count")),
                        )
                        for item in flow["requests"]
                    ],
                ),
                className="request-table",
            ),
            html.H2("实际降级过程"),
            html.P(
                "Exa 仅在 Tavily 月限额用尽时作为备用；下表展示真实发生的层级、跳过或终止原因。"
            ),
            table(
                ("顺序 / 事件", "渠道", "结果", "说明", "缓存", "关联请求"),
                [
                    (
                        str(item.get("sequence")) + " / " + str(item.get("release_event_id")),
                        item["channel"],
                        label_value(item["outcome"]),
                        item.get("classification") or "—",
                        "复用" if item.get("cache_hit") else "否",
                        item.get("physical_request_id") or "未发送 / 未记录",
                    )
                    for item in selected.retrieval_attempts
                    if (not query.get("channel") or item["channel"] == query["channel"])
                    and (
                        not query.get("metric")
                        or (
                            isinstance(metrics := item.get("metric_ids"), (list, tuple))
                            and query["metric"] in metrics
                        )
                        or item.get("physical_request_id") in request_ids
                    )
                    and (not scoped_requests or item.get("physical_request_id") in request_ids)
                ],
            ),
            html.H2("目录应有期与未完成原因"),
            html.P(
                f"需求明细 {len(requirements)} 条 · 第 {gap_page} / {page_count} 页 · 每页 100 条"
            ),
            html.Nav(
                [
                    html.A(
                        "上一页需求明细",
                        href="/data-chain?" + urlencode({**query, "gap_page": str(gap_page - 1)}),
                    )
                    if gap_page > 1
                    else None,
                    " · " if 1 < gap_page < page_count else None,
                    html.A(
                        "下一页需求明细",
                        href="/data-chain?" + urlencode({**query, "gap_page": str(gap_page + 1)}),
                    )
                    if gap_page < page_count
                    else None,
                ],
                **cast(Any, {"aria-label": "需求明细分页"}),
            ),
            html.P("最终计划尚未形成；以下为初始需求，不能视作最终完整度。")
            if not summary.get("final_plan_available")
            else None,
            html.Div(
                table(
                    ("指标", "期", "状态", "缺失维度", "门禁 / 原因", "关联请求数"),
                    [
                        (
                            item["metric_id"],
                            item["period"],
                            DIAGNOSES.get(item["diagnosis"], item["diagnosis"]),
                            ", ".join(item.get("missing_members", [])) or "—",
                            str(item.get("release_gate") or item.get("listing_not_covered") or "—"),
                            len(item["request_ids"]),
                        )
                        for item in page_requirements
                    ],
                ),
                className="requirement-table",
            ),
            html.Details(
                [
                    html.Summary("候选校验与时效"),
                    table(
                        ("候选", "结果", "说明", "采用声明"),
                        [
                            (
                                item.get("candidate_id") or item.get("validation_id"),
                                item.get("outcome"),
                                view.candidate_reason(item),
                                ", ".join(item.get("selected_claim_ids", [])),
                            )
                            for item in objects(
                                obj(selected.retrieval_ledger).get("candidate_validations")
                            )
                            if not filtering or scoped_gaps.intersection(item.get("gap_ids", []))
                        ],
                    ),
                ]
            ),
            evidence,
        ]
    )
    return html.Div(body, className="operations-workspace")
