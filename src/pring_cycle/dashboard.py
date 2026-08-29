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
    stage_events: Sequence[dict[str, object]] = (),
    release_events: Sequence[dict[str, object]] = (),
) -> html.Div:
    route = pathname or "/"
    if route == "/":
        return _home_page(projection)
    if route == "/core-assets":
        return _core_assets_page(projection)
    if route == "/macro":
        return _macro_page(projection)
    if route == "/inventory":
        return _inventory_page(projection)
    if route == "/stage-history":
        return _stage_history_page(projection, stage_events)
    if route == "/release-calendar":
        return _release_calendar_page(projection, release_events)
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
    current_stage = _stage_label(overview.get("current_stage"))
    stage_reason = _stage_explanation(overview)
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
                                "上一确认阶段", _stage_label(overview.get("last_confirmed_stage"))
                            ),
                            _compact_fact(
                                "业务日",
                                projection.envelope.target_business_date
                                if projection is not None
                                else "尚无",
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
                        _transition_watch(overview.get("transition_watch")),
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


def _core_assets_page(projection: ProjectionSet | None) -> html.Div:
    assets = _asset_documents(_dataset(projection, "core_assets").get("assets"))
    return html.Div(
        [
            _page_heading("核心资产", "CORE ASSET STATES"),
            html.P(
                "三个核心价格序列共同决定正式阶段；确认指标只解释，不替代核心票。",
                className="body-copy page-intro",
            ),
            html.Div(
                [_asset_card(item) for item in assets]
                if assets
                else _empty_state("核心资产尚未发布", "P0 门禁通过后才会显示资产轨道。"),
                className="asset-card-grid",
            ),
        ],
        className="page-stack",
    )


def _macro_page(projection: ProjectionSet | None) -> html.Div:
    document = _dataset(projection, "macro")
    sections = (
        ("政策方向", "POLICY DIRECTION", ("policy_direction", "policy_action", "transmission")),
        ("过热程度", "OVERHEAT STATE", ("overheat_state", "credit_response")),
        ("物价压力", "PRICE PRESSURE", ("price_pressure",)),
        ("国际环境", "P2 CONTEXT ONLY", ("international_context",)),
    )
    return _fixed_section_page(
        "宏观证据",
        "MACRO POST-CONFIRMATION",
        "政策、过热、物价与国际环境保持独立结论，不汇总成阶段票。",
        document,
        sections,
    )


def _inventory_page(projection: ProjectionSet | None) -> html.Div:
    document = _dataset(projection, "inventory")
    cards = document.get("cards")
    card_documents = (
        [item for item in cards if isinstance(item, dict)]
        if isinstance(cards, list)
        else []
    )
    return html.Div(
        [
            _page_heading("库存特征", "INVENTORY CHARACTERISTICS"),
            html.P(
                "四象限解释与七张特征卡保持独立；冲突和数据不足不会被压成总分。",
                className="body-copy page-intro",
            ),
            _domain_panel(
                "四象限解释",
                "INVENTORY QUADRANT",
                _display_value(document.get("quadrant")),
            ),
            html.Section(
                [
                    _section_heading("七张阶段特征卡", "NO AGGREGATE SCORE"),
                    html.Div(
                        [_inventory_card(item) for item in card_documents]
                        if card_documents
                        else _empty_state("特征卡待补齐", "当前投影尚无可用的库存特征证据。"),
                        className="evidence-card-grid",
                    ),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _stage_history_page(
    projection: ProjectionSet | None,
    stage_events: Sequence[dict[str, object]],
) -> html.Div:
    document = _dataset(projection, "stage_history")
    projection_events = document.get("events")
    rows = (
        list(stage_events)
        if stage_events
        else [item for item in projection_events if isinstance(item, dict)]
        if isinstance(projection_events, list)
        else []
    )
    return html.Div(
        [
            _page_heading("阶段历史", "FORMAL STAGE HISTORY"),
            html.P(
                "正式区间、非典型组合与不可用空档均显式保留，不连续填充。",
                className="body-copy page-intro",
            ),
            html.Section(
                [
                    _section_heading("正式区间与空档", "IMMUTABLE EVENTS"),
                    html.Ul(
                        [_stage_event_row(item) for item in rows],
                        className="record-list",
                    )
                    if rows
                    else _empty_state(
                        "尚无阶段事件",
                        "首次完整投影发布后，区间和空档会显示在这里。",
                    ),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _release_calendar_page(
    projection: ProjectionSet | None,
    release_events: Sequence[dict[str, object]],
) -> html.Div:
    document = _dataset(projection, "release_calendar")
    projected_events = document.get("events")
    rows = list(release_events)
    if not rows and isinstance(projected_events, list):
        rows = [item for item in projected_events if isinstance(item, dict)]
    return html.Div(
        [
            _page_heading("发布日历", "RELEASE CALENDAR"),
            html.P(
                "预计窗口只用于调度；实际发布与系统首次可用时间分别记录。",
                className="body-copy page-intro",
            ),
            html.Div(
                [
                    _compact_fact("预计窗口", "expected window"),
                    _compact_fact("实际发布", "release_at"),
                    _compact_fact("系统首次可用", "available_at"),
                ],
                className="calendar-legend",
            ),
            html.Ul(
                [_release_event_row(item) for item in rows],
                className="record-list",
            )
            if rows
            else _empty_state(
                "当前窗口没有发布事件",
                "预计窗口到达后，观察与等待状态会显示在这里。",
            ),
        ],
        className="page-stack",
    )


def _fixed_section_page(
    title: str,
    eyebrow: str,
    explanation: str,
    document: dict[str, object],
    sections: Sequence[tuple[str, str, tuple[str, ...]]],
) -> html.Div:
    return html.Div(
        [
            _page_heading(title, eyebrow),
            html.P(explanation, className="body-copy page-intro"),
            html.Div(
                [
                    _domain_panel(
                        label,
                        kicker,
                        " · ".join(
                            f"{key}: {_display_value(document.get(key))}" for key in keys
                        ),
                    )
                    for label, kicker, keys in sections
                ],
                className="evidence-card-grid",
            ),
        ],
        className="page-stack",
    )


def _domain_panel(title: str, kicker: str, value: str) -> html.Article:
    return html.Article(
        [
            html.P(kicker, className="section-kicker"),
            html.H2(title, className="section-title"),
            html.P(value, className="body-copy domain-value"),
        ],
        className="domain-panel",
    )


def _asset_card(item: dict[str, object]) -> html.Article:
    asset = str(item.get("asset") or "unknown")
    candidate = item.get("candidate_30d") or item.get("candidate_state")
    candidate_days = _integer(item.get("candidate_days"))
    return html.Article(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.P(_asset_label(asset), className="section-kicker"),
                            html.H2(
                                str(item.get("metric_id") or "指标未绑定"),
                                className="section-title",
                            ),
                        ]
                    ),
                    _state_badge(str(item.get("state") or "unavailable")),
                ],
                className="asset-card-heading",
            ),
            html.Dl(
                [
                    _compact_fact("120 日正式轨道", _state_label(item.get("state"))),
                    _compact_fact(
                        "30 日转折观察",
                        f"{_state_label(candidate)} · 持续 {candidate_days} 日"
                        if candidate is not None
                        else "尚无候选",
                    ),
                    _compact_fact("12 个月公开代理", _state_label(item.get("proxy_12m"))),
                    _compact_fact("最新业务日", str(item.get("latest_business_date") or "不可用")),
                ],
                className="asset-track-grid",
            ),
            html.P(
                " · ".join(
                    (
                        f"样本 {item.get('observation_count', 0)}",
                        f"距均线 {_display_value(item.get('distance_pct'))}",
                        f"斜率 {_display_value(item.get('slope_pct'))}",
                        f"噪声带 {_display_value(item.get('noise_band_pct'))}",
                    )
                ),
                className="secondary-copy",
            ),
        ],
        className=f"asset-card asset-{asset}",
    )


def _inventory_card(item: dict[str, object]) -> html.Article:
    title = str(item.get("title") or item.get("name") or item.get("signature") or "未命名特征")
    state = str(item.get("state") or item.get("status") or "insufficient_data")
    return html.Article(
        [
            html.H3(title, className="card-title"),
            html.P(_state_label(state), className="body-copy"),
            html.P(
                str(item.get("explanation") or item.get("reason") or "当前没有进一步解释。"),
                className="secondary-copy",
            ),
        ],
        className="domain-panel",
    )


def _stage_event_row(item: dict[str, object]) -> html.Li:
    gaps = item.get("gaps")
    gap_text = (
        "；".join(_gap_label(str(value)) for value in gaps)
        if isinstance(gaps, list) and gaps
        else "无 P0 缺口"
    )
    last_confirmed = item.get("last_confirmed_stage")
    return html.Li(
        [
            html.Strong(
                f"{item.get('business_date', '日期不可用')} · "
                f"{_stage_label(item.get('current_stage'))}"
            ),
            html.Span(
                f"上一确认 {_stage_label(last_confirmed) if last_confirmed else '尚无'} · "
                f"原因 {item.get('stage_reason', item.get('reason', '未记录'))} · "
                f"{gap_text} · 模型 {item.get('model_version_id', '见投影详情')}",
                className="secondary-copy",
            ),
        ],
        className="record-row",
    )


def _gap_label(value: str) -> str:
    asset, separator, reason = value.partition(":")
    if not separator:
        return value
    asset_label = {
        "bond": "债券",
        "stock": "股票",
        "commodity": "商品",
    }.get(asset, asset)
    reason_label = {
        "insufficient_history": "历史不足",
        "source_conflict": "来源冲突",
        "source_missing": "来源缺失",
        "stale_for_target_business_date": "目标日数据陈旧",
        "source_identity_not_certified": "来源身份未认证",
        "nonnumeric_core_observation": "核心观测不是有效数值",
    }.get(reason, reason)
    return f"{asset_label}：{reason_label}"


def _release_event_row(item: dict[str, object]) -> html.Li:
    identity = (
        item.get("release_event_family")
        or item.get("metric_id")
        or item.get("release_event_id")
        or "发布事件"
    )
    expected = item.get("expected_window_start", item.get("expected_window", "未记录"))
    carried = item.get("carried_period") or "无"
    next_check = item.get("next_check_at") or "无需检查"
    return html.Li(
        [
            html.Strong(str(identity)),
            html.Span(
                " · ".join(
                    (
                        f"统计期 {item.get('period', '未记录')}",
                        f"时区 {item.get('timezone', '未记录')}",
                        f"预计 {expected}",
                        f"发布 {item.get('release_at', '尚未发布')}",
                        f"可用 {item.get('available_at', '尚不可用')}",
                        f"沿用上一期 {carried}",
                        f"最近获取 {item.get('latest_fetched_at', '尚未获取')}",
                        f"下一检查 {next_check}",
                        f"关联观测 {item.get('observation_count', 0)}",
                        f"状态 {item.get('status', 'unknown')}",
                    )
                ),
                className="secondary-copy",
            ),
        ],
        className="record-row",
    )


def _section_heading(title: str, kicker: str) -> html.Div:
    return html.Div(
        [html.H2(title, className="section-title"), html.P(kicker, className="section-kicker")],
        className="section-heading",
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
    rows = [_run_row(item) for item in runs]
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


def _run_row(item: RunRecord) -> html.Li:
    attempt_summary = "；".join(
        _retrieval_attempt_summary(attempt) for attempt in item.retrieval_attempts
    )
    budget = item.consumed_budget
    details = (
        f"{item.current_step} · 尝试 {item.attempt_count} · "
        f"预算 Tavily {budget['tavily']}/8、Exa {budget['exa']}/4、"
        f"AI {budget['ai_websearch']}/1 · 下一动作 {item.next_action}"
    )
    if attempt_summary:
        details += f" · 检索 {attempt_summary}"
    return html.Li(
        [
            html.Strong(f"{item.target_business_date} · {item.status}"),
            html.Span(details, className="secondary-copy"),
        ],
        className="record-row",
    )


def _retrieval_attempt_summary(attempt: dict[str, object]) -> str:
    details = f"{attempt['channel']} {attempt['outcome']} {attempt['latency_ms']}ms"
    if attempt.get("classification"):
        details += f" 分类 {attempt['classification']}"
    if attempt.get("remaining_run_budget") is not None:
        details += f" 运行余量 {attempt['remaining_run_budget']}"
    if attempt.get("remaining_daily_budget") is not None:
        details += f" 日余量 {attempt['remaining_daily_budget']}"
    if attempt.get("cache_hit") is True:
        details += " 负缓存命中"
    if attempt.get("manual_budget_exemption") is True:
        details += " 人工预算豁免"
    return details


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


def _asset_documents(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _asset_table(value: object) -> html.Div:
    documents = _asset_documents(value)
    if not documents:
        return _empty_state("核心资产尚未发布", "P0 门禁通过后才会显示正式资产状态。")
    rows: list[html.Tr] = []
    for item in documents:
        state = str(item.get("state") or "unavailable")
        candidate_days = _integer(item.get("candidate_days"))
        rows.append(
            html.Tr(
                [
                    html.Th(_asset_label(str(item.get("asset") or "unknown"))),
                    html.Td(_state_badge(state)),
                    html.Td(f"{candidate_days} 日"),
                    html.Td(
                        "已验证"
                        if item.get("reason") == "validated"
                        else str(item.get("reason") or "未知")
                    ),
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


def _asset_label(asset: str) -> str:
    return {
        "bond": "债券 · 上证国债指数",
        "stock": "股票 · 中证全指",
        "commodity": "商品 · 南华工业品指数",
    }.get(asset, "未知核心资产")


def _stage_label(value: object) -> str:
    labels = {
        "stage_i": "第一阶段 · Stage I",
        "stage_ii": "第二阶段 · Stage II",
        "stage_iii": "第三阶段 · Stage III",
        "stage_iv": "第四阶段 · Stage IV",
        "stage_v": "第五阶段 · Stage V",
        "stage_vi": "第六阶段 · Stage VI",
    }
    if value is None:
        return "当前阶段暂不判定"
    return labels.get(str(value).lower(), str(value))


def _stage_explanation(overview: dict[str, object]) -> str:
    if overview.get("current_stage") is not None:
        return "三类核心资产已形成规范组合；正式阶段由 120 日稳定状态机械映射确认。"
    reason = overview.get("stage_reason") or overview.get("stage_unavailable_reason")
    return {
        "noncanonical_combination": "当前三资产组合不属于六个规范阶段，系统保持空值。",
        "core_state_unavailable": "至少一类核心资产状态不可用，系统不会以宏观证据补票。",
        "p0_unavailable": "P0 核心证据未通过门禁，上一确认阶段仅作历史上下文。",
    }.get(str(reason), "等待三类 P0 核心资产形成同一截止点的可用组合。")


def _transition_watch(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "尚无已确认的资产候选方向。"
    labels = []
    for item in value:
        if isinstance(item, dict):
            labels.append(
                f"{_asset_label(str(item.get('asset') or 'unknown'))}："
                f"{_state_label(item.get('state') or item.get('candidate_state'))}"
            )
        else:
            labels.append(str(item))
    return "；".join(labels)


def _state_label(value: object) -> str:
    if value is None:
        return "不可用"
    return {
        "bull": "偏多",
        "bullish": "偏多",
        "bear": "偏空",
        "bearish": "偏空",
        "support": "支持",
        "supports": "支持",
        "conflict": "矛盾",
        "conflicted": "矛盾",
        "insufficient_data": "数据不足",
    }.get(str(value).lower(), str(value))


def _integer(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


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
