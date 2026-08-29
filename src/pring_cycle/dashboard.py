from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any, cast

from dash import dcc, html

from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.runs import RunRecord

DASHBOARD_NAVIGATION: tuple[tuple[str, str], ...] = (
    ("/", "首页"),
    ("/core-assets", "核心资产"),
    ("/macro", "宏观证据"),
    ("/inventory", "库存特征"),
    ("/stage-history", "阶段历史"),
    ("/release-calendar", "发布日历"),
    ("/reports", "报告"),
    ("/runs", "运行状态"),
)


def dashboard_shell(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
) -> html.Div:
    envelope = projection.envelope if projection is not None else None
    system_as_of = envelope.system_as_of.isoformat() if envelope is not None else "尚无投影"
    projection_id = envelope.projection_set_id if envelope is not None else "等待首次完整运行"
    completeness = envelope.completeness if envelope is not None else "不可用"
    drawer_document = _projection_detail(projection, runs, reports)
    return html.Div(
        [
            dcc.Location(id="dashboard-location", refresh=False),
            dcc.Store(id="theme-state", storage_type="local"),
            html.A("跳至主要内容", href="#page-content", className="skip-link"),
            html.Header(
                [
                    html.Div(
                        [
                            html.Span("PRING CYCLE", className="brand-eyebrow"),
                            html.Span("周期驾驶舱", className="brand-name"),
                        ],
                        className="brand-lockup",
                    ),
                    html.Div(
                        [
                            _metadata("SYSTEM AS OF", system_as_of),
                            _metadata("投影身份", projection_id),
                            _metadata("完整度", completeness),
                        ],
                        className="projection-strip",
                    ),
                    html.Button(
                        "切换明暗主题",
                        id="theme-toggle",
                        className="quiet-button",
                        type="button",
                        title="切换并记住主题",
                    ),
                ],
                className="topbar",
            ),
            html.Div(
                [
                    html.Nav(
                        [
                            dcc.Link(
                                label,
                                href=path,
                                className="nav-link",
                                id=f"nav-{path.strip('/').replace('/', '-') or 'home'}",
                            )
                            for path, label in DASHBOARD_NAVIGATION
                        ],
                        className="primary-nav",
                        **cast(Any, {"aria-label": "一级导航"}),
                    ),
                    html.Main(id="page-content", className="workspace", tabIndex=-1),
                    html.Div(
                        id="command-feedback",
                        className="command-feedback",
                        role="status",
                        **cast(Any, {"aria-live": "polite"}),
                    ),
                    html.Aside(
                        html.Details(
                            [
                                html.Summary("投影详情与证据追溯"),
                                html.P(
                                    "证据入口保留值、来源、发布时间、系统可用时间、修订与血缘。",
                                    className="body-copy",
                                ),
                                html.Pre(
                                    json.dumps(
                                        drawer_document,
                                        ensure_ascii=False,
                                        indent=2,
                                        sort_keys=True,
                                    ),
                                    className="detail-json",
                                ),
                            ]
                        ),
                        className="evidence-drawer",
                    ),
                ],
                className="application-grid",
            ),
        ],
        className="dashboard-app",
    )


def dashboard_page(
    pathname: str | None,
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
) -> html.Div:
    route = pathname or "/"
    if route == "/":
        return _home_page(projection)
    if route == "/core-assets":
        return _dataset_page(
            "核心资产",
            "CORE ASSET STATES",
            "三个核心价格序列共同决定正式阶段；确认指标只解释，不替代核心票。",
            projection,
            "core_assets",
        )
    if route == "/macro":
        return _dataset_page(
            "宏观证据",
            "MACRO POST-CONFIRMATION",
            "政策、过热、物价与国际环境保持独立结论，不汇总成阶段票。",
            projection,
            "macro",
        )
    if route == "/inventory":
        return _dataset_page(
            "库存特征",
            "INVENTORY CHARACTERISTICS",
            "七张特征卡解释库存行为；冲突与数据不足原样保留。",
            projection,
            "inventory",
        )
    if route == "/stage-history":
        return _dataset_page(
            "阶段历史",
            "FORMAL STAGE HISTORY",
            "正式区间、非典型组合与不可用空档均显式保留，不连续填充。",
            projection,
            "stage_history",
        )
    if route == "/release-calendar":
        return _dataset_page(
            "发布日历",
            "RELEASE CALENDAR",
            "预计窗口只用于调度；实际发布与本系统可用时间分别记录。",
            projection,
            "release_calendar",
        )
    if route == "/reports":
        return _reports_page(reports)
    if route == "/runs":
        return _runs_page(runs)
    return html.Div(
        [
            _page_heading("页面不存在", "NOT FOUND"),
            html.P("该本机路由不存在。请从一级导航重新进入。", className="body-copy"),
        ],
        className="page-stack",
    )


def _home_page(projection: ProjectionSet | None) -> html.Div:
    overview = _dataset(projection, "cycle_overview")
    current_stage = str(overview.get("current_stage") or "当前阶段暂不判定")
    stage_reason = str(
        overview.get("stage_unavailable_reason")
        or "等待三类 P0 核心资产形成同一截止点的可用组合。"
    )
    core_assets = _dataset(projection, "core_assets")
    macro = _dataset(projection, "macro")
    asset_rows = core_assets.get("assets")
    return html.Div(
        [
            _page_heading("周期总览", "FORMAL CYCLE OVERVIEW"),
            html.Section(
                [
                    html.Div(
                        [
                            html.P("正式阶段", className="section-kicker"),
                            html.H2(current_stage, className="stage-value"),
                            html.P(stage_reason, className="body-copy stage-explanation"),
                        ],
                        className="stage-primary",
                    ),
                    html.Div(
                        [
                            _compact_fact(
                                "上一确认阶段", str(overview.get("last_confirmed_stage") or "尚无")
                            ),
                            _compact_fact(
                                "业务日", str(overview.get("target_business_date") or "尚无")
                            ),
                            _compact_fact(
                                "映射口径", "债券 / 股票 / 商品 120 日稳定状态"
                            ),
                        ],
                        className="stage-facts",
                    ),
                ],
                className="stage-panel",
                **cast(Any, {"aria-labelledby": "page-title"}),
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("三核心资产", className="section-title"),
                            html.P("P0 CORE", className="section-kicker"),
                        ],
                        className="section-heading",
                    ),
                    _asset_table(asset_rows),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("转折观察", className="section-title"),
                            html.P("不改变正式阶段", className="warning-label"),
                        ],
                        className="section-heading",
                    ),
                    html.P(
                        str(overview.get("transition_watch") or "尚无已确认的资产候选方向。"),
                        className="body-copy",
                    ),
                ],
                className="content-section transition-section",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("宏观事后确认", className="section-title"),
                            html.P("CONTEXT ONLY", className="section-kicker"),
                        ],
                        className="section-heading",
                    ),
                    _definition_rows(macro),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _dataset_page(
    title: str,
    eyebrow: str,
    explanation: str,
    projection: ProjectionSet | None,
    dataset_name: str,
) -> html.Div:
    dataset = _dataset(projection, dataset_name)
    return html.Div(
        [
            _page_heading(title, eyebrow),
            html.P(explanation, className="body-copy page-intro"),
            html.Section(
                _definition_rows(dataset),
                className="data-workspace",
                **cast(Any, {"aria-label": f"{title}当前投影"}),
            ),
        ],
        className="page-stack",
    )


def _reports_page(reports: Sequence[ReportSnapshot]) -> html.Div:
    history = [
        html.Li(
            [
                html.Strong(f"{item.target_business_date} · v{item.version}"),
                html.Span(
                    f"{item.status} · {item.adapter} · {item.report_snapshot_id}",
                    className="secondary-copy",
                ),
            ],
            className="record-row",
        )
        for item in reports
    ]
    return html.Div(
        [
            _page_heading("报告", "IMMUTABLE REPORT WORKSPACE"),
            dcc.Tabs(
                [
                    dcc.Tab(
                        [
                            html.H2("报告生成", className="section-title"),
                            html.P(
                                "生成命令冻结当前证据包；AI 失败不会回滚分析投影。",
                                className="body-copy",
                            ),
                            html.Button(
                                "基于当前投影生成新版本",
                                id="generate-report-command",
                                className="primary-button",
                                type="button",
                            ),
                        ],
                        label="生成",
                        value="generate",
                    ),
                    dcc.Tab(
                        [
                            html.H2("报告历史", className="section-title"),
                            html.Ul(history, className="record-list")
                            if history
                            else _empty_state("尚无报告快照", "先完成一次完整投影，再生成报告。"),
                        ],
                        label="历史",
                        value="history",
                    ),
                    dcc.Tab(
                        [
                            html.H2("报告阅读", className="section-title"),
                            _empty_state(
                                "尚未选择报告",
                                "从“历史”选择一个不可变版本后在此阅读。",
                            ),
                        ],
                        label="阅读",
                        value="read",
                    ),
                ],
                value="generate",
                className="report-tabs",
            ),
        ],
        className="page-stack",
    )


def _runs_page(runs: Sequence[RunRecord]) -> html.Div:
    rows = [
        html.Li(
            [
                html.Strong(f"{item.target_business_date} · {item.status}"),
                html.Span(
                    f"{item.current_step} · 尝试 {item.attempt_count} · "
                    f"下一动作 {item.next_action}",
                    className="secondary-copy",
                ),
            ],
            className="record-row",
        )
        for item in runs
    ]
    return html.Div(
        [
            _page_heading("运行状态", "PERSISTENT RUN LEDGER"),
            html.Div(
                [
                    html.Button(
                        "发起手动完整运行",
                        id="manual-run-command",
                        className="primary-button",
                        type="button",
                    ),
                    html.P(
                        "命令仅在显式操作后联网；重复提交复用同一权威运行。",
                        className="secondary-copy",
                    ),
                ],
                className="command-row",
            ),
            html.Ul(rows, className="record-list")
            if rows
            else _empty_state("尚无运行记录", "发起手动完整运行后，步骤与恢复动作会显示在这里。"),
        ],
        className="page-stack",
    )


def _page_heading(title: str, eyebrow: str) -> html.Div:
    return html.Div(
        [
            html.P(eyebrow, className="page-eyebrow"),
            html.H1(title, id="page-title", className="page-title"),
        ],
        className="page-heading",
    )


def _metadata(label: str, value: str) -> html.Div:
    return html.Div(
        [
            html.Span(label, className="metadata-label"),
            html.Span(value, className="metadata-value"),
        ],
        className="metadata-pair",
    )


def _compact_fact(label: str, value: str) -> html.Div:
    return html.Div(
        [html.Dt(label, className="compact-label"), html.Dd(value, className="compact-value")],
        className="compact-fact",
    )


def _asset_table(value: object) -> html.Div:
    if not isinstance(value, list) or not value:
        return _empty_state("核心资产尚未发布", "P0 门禁通过后才会显示正式资产状态。")
    rows: list[html.Tr] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        state = str(item.get("stable_state") or "unavailable")
        rows.append(
            html.Tr(
                [
                    html.Th(str(item.get("name") or item.get("metric_id") or "未知资产")),
                    html.Td(_state_badge(state)),
                    html.Td(str(item.get("candidate_days") or "—")),
                    html.Td(str(item.get("freshness_status") or "未知")),
                ]
            )
        )
    return html.Div(
        html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th("资产"),
                            html.Th("120日状态"),
                            html.Th("候选持续"),
                            html.Th("时效"),
                        ]
                    )
                ),
                html.Tbody(rows),
            ],
            className="data-table",
        ),
        className="table-scroll",
    )


def _state_badge(value: str) -> html.Span:
    normalized = value.lower()
    state = "up" if normalized in {"bull", "bullish", "上涨", "支持"} else "down"
    if normalized not in {"bull", "bullish", "上涨", "支持", "bear", "bearish", "下跌", "矛盾"}:
        state = "warning"
    label = {"up": "偏多", "down": "偏空", "warning": "不可用"}[state]
    return html.Span(f"{label} · {value}", className=f"state-badge state-{state}")


def _definition_rows(document: dict[str, object]) -> html.Div:
    if not document:
        return _empty_state("当前投影暂无此数据", "完成通过门禁的完整运行后，此区域会自动更新。")
    rows = []
    for key, value in document.items():
        if key == "projection_set_id":
            continue
        rows.append(
            html.Div(
                [
                    html.Dt(str(key), className="technical-field"),
                    html.Dd(_display_value(value), className="field-value"),
                ],
                className="definition-row",
            )
        )
    return html.Div(rows, className="definition-list")


def _display_value(value: object) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return "不可用"
    return str(value)


def _empty_state(title: str, detail: str) -> html.Div:
    return html.Div(
        [html.Strong(title, className="empty-title"), html.P(detail, className="body-copy")],
        className="empty-state",
        role="status",
    )


def _dataset(projection: ProjectionSet | None, name: str) -> dict[str, object]:
    if projection is None:
        return {}
    return projection.datasets.get(name, {})


def _projection_detail(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
) -> dict[str, Any]:
    if projection is None:
        return {
            "projection": None,
            "status": "waiting_for_first_complete_projection",
            "run_count": len(runs),
            "report_count": len(reports),
        }
    envelope = asdict(projection.envelope)
    envelope["system_as_of"] = projection.envelope.system_as_of.isoformat()
    envelope["generated_at"] = projection.envelope.generated_at.isoformat()
    return {
        "projection": envelope,
        "datasets": sorted(projection.datasets),
        "run_count": len(runs),
        "report_count": len(reports),
    }
