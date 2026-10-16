from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dash import dcc, html

from pring_cycle.confirmation import OUTPUT_STRUCTURE as CONFIRMATION_STRUCTURE
from pring_cycle.domain.trend import TrendRules
from pring_cycle.freshness import CALENDAR_FALLBACK_NOTE, freshness_statement
from pring_cycle.navigation import DASHBOARD_NAVIGATION
from pring_cycle.page_identity import identity_fields
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.retrieval import RUN_SEARCH_LIMITS
from pring_cycle.run_health import ProducerRun
from pring_cycle.runs import RunRecord
from pring_cycle.wording import CORE_STATE_LABELS, core_state_label, display_name, stage_title


def dashboard_shell(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
    *,
    source_contract_notice: str | None = None,
    producer: ProducerRun | None = None,
) -> html.Div:
    drawer_document = _projection_detail(projection, runs, reports)
    projection_notes = _correction_notes(
        projection.corrections if projection is not None else {}, "当前投影", "投影"
    )
    return html.Div(
        [
            dcc.Location(id="dashboard-location", refresh=False),
            dcc.Interval(
                id="runtime-poll",
                interval=_poll_interval_ms(runs),
                n_intervals=0,
            ),
            dcc.Store(id="theme-state", storage_type="local"),
            dcc.Store(id="view-fingerprint"),
            dcc.Store(id="command-refresh"),
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
                            _metadata(label, value)
                            for label, value in identity_fields(
                                projection, producer=producer, rendered_at=datetime.now(UTC)
                            )
                        ],
                        className="projection-strip",
                        id="projection-strip",
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
            html.Aside(source_contract_notice, className="source-contract-notice", role="alert")
            if source_contract_notice is not None
            else None,
            html.Div(id="refresh-notice", role="status", className="refresh-notice"),
            html.Aside(projection_notes, className="source-contract-notice", role="status")
            if projection_notes
            else None,
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
    *,
    producer_run: ProducerRun | None = None,
    trend_rules: TrendRules | None = None,
) -> html.Div:
    """``producer_run`` is the full run that produced ``projection`` with its persisted
    health summary; ``None`` when no such run is known. ``trend_rules`` are the rules
    frozen in the projection's model; ``None`` when that model provides none."""
    route = pathname or "/"
    if route in {"/", "/core-assets", "/macro", "/inventory", "/stage-history"}:
        from pring_cycle.cockpit import report_board

        return report_board(
            projection,
            runs,
            reports,
            stage_events,
            release_events,
            producer_run=producer_run,
            trend_rules=trend_rules,
        )
    if route == "/release-calendar":
        return _release_calendar_page(projection, release_events)
    if route == "/reports":
        page = _reports_page(reports, runs)
        if projection:
            page.children.insert(
                1,
                html.Div(
                    projection.envelope.projection_set_id,
                    id="report-projection",
                    **cast(Any, {"data-projection-id": projection.envelope.projection_set_id}),
                ),
            )
        return page
    if route == "/runs":
        return _runs_page(runs)
    return html.Div(
        [
            _page_heading("页面不存在", "NOT FOUND"),
            html.P("该本机路由不存在。请从一级导航重新进入。", className="body-copy"),
        ],
        className="page-stack",
    )


def _home_page(
    projection: ProjectionSet | None, reports: Sequence[ReportSnapshot] = ()
) -> html.Div:
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
                            *_carry_forward_notice(overview.get("core_carry_forward")),
                        ],
                        className="stage-primary",
                    ),
                    html.Div(
                        [
                            _compact_fact(
                                "上一确认阶段",
                                _last_confirmed_label(
                                    overview.get("last_confirmed_stage"),
                                    overview.get("last_confirmed_lookback"),
                                ),
                            ),
                            _compact_fact(
                                "业务日",
                                projection.envelope.target_business_date
                                if projection is not None
                                else "尚无",
                            ),
                            _compact_fact("映射口径", "债券 / 股票 / 商品 120 日稳定状态"),
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
                    *(
                        html.P(f"债券归因（附注，不计数）：{line}", className="secondary-copy")
                        for line in _attribution_lines(macro, brief=True)
                    ),
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
            *_home_report_reading(projection, reports),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("宏观事后确认", className="section-title"),
                            html.P("CONTEXT ONLY", className="section-kicker"),
                        ],
                        className="section-heading",
                    ),
                    _macro_summary(macro),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    html.Div(
                        [
                            html.H2("缺口清单", className="section-title"),
                            html.P("GATE ①②③", className="section-kicker"),
                        ],
                        className="section-heading",
                    ),
                    *_freshness_basis(projection),
                    _gap_list(overview.get("gap_list")),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _home_report_reading(
    projection: ProjectionSet | None, reports: Sequence[ReportSnapshot]
) -> list[html.Section]:
    if projection is None:
        return []
    overview = projection.datasets.get("cycle_overview", {})
    if (
        overview.get("stage_reason") != "noncanonical_combination"
        or overview.get("current_stage") is not None
    ):
        return []
    matching = [
        report
        for report in reports
        if report.projection_set_id == projection.envelope.projection_set_id
    ]
    if not matching:
        return []
    report = max(matching, key=lambda item: item.version)
    if not report.body_retained:
        return []
    sections = report.body.get("ai_explanation")
    if not isinstance(sections, list):
        return []
    reading = [
        section
        for section in sections
        if isinstance(section, dict) and section.get("title") == "非典型组合解读"
    ]
    if not reading:
        return []
    source = "确定性模板" if report.adapter == "deterministic" else "AI 解读"
    return [
        html.Section(
            [
                html.H2("非典型组合解读", className="section-title"),
                html.P(source + " · 不构成阶段判断", className="secondary-copy"),
                html.P(str(reading[0].get("explanation", "")), className="body-copy"),
            ],
            className="content-section",
        )
    ]


def _carry_forward_notice(value: object) -> list[html.P]:
    """A prominent line naming each core priced at its previous session (ticket 21)."""
    assets = [str(item) for item in value] if isinstance(value, list) else []
    if not assets:
        return []
    names = "、".join(_asset_label(asset) for asset in assets)
    return [html.P(f"核心沿用上一期：{names}", className="warning-label carry-forward")]


GAP_CATEGORY_LABELS = {
    "missing": "缺失",
    "fetch_failed": "取数失败",
    "ingest_rejected": "入库校验失败",
    "retrieval_failed": "检索未通过",
    "license_missing": "授权缺失",
    "freshness_gap": "时效缺口",
    "unconfigured": "未配置时效",
    # Lists published before ticket 21 still carry a refused response of a metric not
    # otherwise listed.
    "rejected": "拒收",
    "derived_failed": "派生失败",
    "source_failed": "来源失败",
    "source_conflict": "来源冲突",
    # Lists published before gap sources #04 still carry the old category.
    "no_searchable_source": "无可检索来源",
}


CANDIDATE_REASON_LABELS = {
    "not_whitelisted": "不在白名单",
    "parse_failed": "解析失败",
    "period_mismatch": "统计期不符",
    "no_publication_date": "无发布日期",
    "date_after_cutoff": "日期晚于截止时点",
    "search_value_mismatch": "与搜索结果不一致",
    "fetch_failed": "抓取失败",
    "incomplete_model_input": "数值不完整",
    "retrieval_blocked": "请求被缓存或预算拦下",
    "rule_not_matched": "解析规则未命中",
}


def _candidate_reasons(value: object) -> str:
    """Each rejected candidate URL with why it was not adopted (ticket 19)."""
    candidates = _document_list(value)
    if not candidates:
        return ""
    return "；候选 " + "；".join(
        f"{item.get('url')}（"
        f"{CANDIDATE_REASON_LABELS.get(str(item.get('reason')), item.get('reason'))}）"
        for item in candidates
    )


def _failed_members(value: object) -> str:
    """Each warrant symbol (and day) that failed, with its own reason (ticket 20)."""
    members = _document_list(value)
    if not members:
        return ""
    return "；失败品种 " + "；".join(
        f"{item.get('symbol')}"
        + (f" {item['business_date']}" if item.get("business_date") else "")
        + f"（{item.get('reason')}）"
        for item in members
    )


RELEASE_GATE_LABELS = {
    "earlier_session_not_searched": "较早交易日不逐日检索",
    "unknown_release_configuration": "发布规则未登记",
    "awaiting_release": "等待发布",
}


def _not_requested(value: object) -> str:
    """The periods the release gate kept from being requested, by why (lookback L01): a
    daily series' earlier sessions are many, so several are given as a count and span."""
    by_reason: dict[str, list[str]] = {}
    for item in _document_list(value):
        by_reason.setdefault(str(item.get("reason")), []).append(str(item.get("period")))
    return "".join(
        "；未请求 "
        + (
            periods[0]
            if len(periods) == 1
            else f"{len(periods)} 期 {min(periods)} 至 {max(periods)}"
        )
        + f"（{RELEASE_GATE_LABELS.get(reason, reason)}）"
        for reason, periods in by_reason.items()
    )


LISTING_LABELS = {
    "https://www.stats.gov.cn/sj/zxfb/": "统计局最新发布",
    "https://www.stats.gov.cn/sj/zxfbhjd/": "统计局发布和解读",
    "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html": (
        "人民银行公开市场业务交易公告"
    ),
    "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html": "人民银行金融统计数据报告",
    "https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/5727710/index.html": (
        "人民银行各项工具流动性投放情况"
    ),
}
LISTING_STOP_LABELS = {
    "page_limit": "本轮该站列表页额度用完",
    "repeated_page": "翻到重复页",
    "unreadable_page": "列表页多次读取失败",
    "last_page": "栏目已到底",
}


def _not_covered(value: object) -> str:
    """The periods the official listing, as far as the run read it, did not reach, by
    listing and where its reading stopped, with the pages read and the earliest day they
    list: not listed there, which is not "none published" nor "no operation" (lookback
    L05)."""
    by_stop: dict[tuple[str, str, str, str], list[str]] = {}
    for item in _document_list(value):
        oldest = str(item.get("oldest_entry") or "")
        key = (
            str(item.get("listing")),
            str(item.get("stopped")),
            str(item.get("pages_read")),
            f"{oldest[:4]}-{oldest[4:6]}-{oldest[6:]}" if len(oldest) == 8 else "无带日期条目",
        )
        by_stop.setdefault(key, []).append(str(item.get("period")))
    return "".join(
        "；列表未覆盖 "
        + (
            periods[0]
            if len(periods) == 1
            else f"{len(periods)} 期 {min(periods)} 至 {max(periods)}"
        )
        + f"（{LISTING_LABELS.get(listing, listing)}，"
        + f"{LISTING_STOP_LABELS.get(stopped, stopped)}；已读 {pages} 页，最早读到 {oldest}）"
        for (listing, stopped, pages, oldest), periods in by_stop.items()
    )


def _freshness_basis(projection: ProjectionSet | None) -> list[html.P]:
    """The target day beside the instant its gap list was judged at (lookback 27)."""
    if projection is None:
        return []
    assessed = _dataset(projection, "cycle_overview").get("gap_list_assessed_at")
    # A set published before the list carried its time was judged at its cutoff all the same.
    judged = (
        datetime.fromisoformat(assessed)
        if isinstance(assessed, str)
        else projection.envelope.system_as_of
    )
    statement = freshness_statement(projection.envelope.target_business_date, judged)
    return [
        html.P(statement, className="secondary-copy"),
        *_calendar_fallback_notice(
            _dataset(projection, "cycle_overview").get("freshness_calendar")
        ),
    ]


def _calendar_fallback_notice(value: object) -> list[html.P]:
    """A prominent line when weekdays stood in for the calendar the gap list was judged on
    (ticket 06): a holiday among them may be counted owed."""
    if not isinstance(value, dict) or value.get("basis") != "weekday_inferred":
        return []
    return [
        html.P(
            f"{CALENDAR_FALLBACK_NOTE}：至判定日 {value.get('judged_on')} 有日子无交易日历应答，"
            "按工作日计应有期。",
            className="warning-label calendar-fallback",
        )
    ]


def _gap_list(value: object) -> html.Div:
    """One row per gap, grouped under its category, in the order the batch listed them."""
    gaps = _document_list(value)
    if not gaps:
        return html.Div(html.P("本次运行没有缺口。", className="body-copy"))
    groups = []
    for category, label in GAP_CATEGORY_LABELS.items():
        rows = [item for item in gaps if item.get("category") == category]
        if rows:
            groups.append(
                html.Div(
                    [
                        html.H3(f"{label}（{len(rows)}）"),
                        html.Ul(
                            [
                                html.Li(
                                    f"{item.get('priority')} {item.get('metric_id')}："
                                    f"{item.get('reason')}"
                                    + (
                                        f"（应有期 {item.get('due_period')}，"
                                        f"持有 {item.get('held_period')}）"
                                        if item.get("due_period")
                                        else ""
                                    )
                                    + _candidate_reasons(item.get("candidates"))
                                    + _failed_members(item.get("failed_members"))
                                    + _not_requested(item.get("not_requested"))
                                    + _not_covered(item.get("not_covered"))
                                    + (
                                        "；来源复核失败"
                                        if item.get("source_failures")
                                        and category != "source_failed"
                                        else ""
                                    )
                                    + (
                                        "；来源同时冲突"
                                        if item.get("conflicts") and category != "source_conflict"
                                        else ""
                                    )
                                    + ("；无网页补缺渠道" if item.get("no_web_fallback") else "")
                                )
                                for item in rows
                            ]
                        ),
                    ],
                    className="gap-group",
                )
            )
    return html.Div(groups, className="gap-list")


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
    as_of = projection.envelope.system_as_of.isoformat() if projection is not None else None
    if document.get("output_structure") == CONFIRMATION_STRUCTURE:
        return _confirmation_macro_page(document, as_of=as_of)
    policy_action = _object_document(document.get("policy_action"))
    transmission = _object_document(document.get("transmission"))
    credit = _object_document(document.get("credit"))
    overheat = _object_document(document.get("overheat"))
    price_chain = _object_document(document.get("price_chain"))
    international = _document_list(document.get("international_context"))
    return html.Div(
        [
            _page_heading("宏观证据", "MACRO POST-CONFIRMATION"),
            html.P(
                "政策、信用、过热、物价与国际环境保持独立结论，不汇总成阶段票。",
                className="body-copy page-intro",
            ),
            html.Section(
                [
                    _section_heading("政策方向", "POLICY DIRECTION · NO SCORE"),
                    html.Div(
                        [
                            _evidence_panel(
                                "政策行动",
                                "CENTRAL-BANK ACTION",
                                policy_action.get("direction"),
                                _document_list(policy_action.get("evidence")),
                                as_of=as_of,
                            ),
                            _evidence_panel(
                                "市场传导",
                                "MONEY-MARKET TRANSMISSION",
                                transmission.get("direction"),
                                _document_list(transmission.get("evidence")),
                                as_of=as_of,
                            ),
                        ],
                        className="evidence-card-grid",
                    ),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    _section_heading("信用响应", "CREDIT RESPONSE · SEPARATE LAYER"),
                    _evidence_panel(
                        "信用响应",
                        "MONEY / SOCIAL FINANCING / LOAN STRUCTURE",
                        document.get("credit_response"),
                        _document_list(credit.get("evidence")),
                        as_of=as_of,
                        note=_formula_summary(credit.get("formula")),
                    ),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    _section_heading("过热程度", "OVERHEAT STATE"),
                    _evidence_panel(
                        "过热程度",
                        "SUPPORT / COUNTEREVIDENCE / GAPS",
                        document.get("overheat_state"),
                        _grouped_evidence(overheat),
                        as_of=as_of,
                    ),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    _section_heading("物价压力", "PRICE TRANSMISSION"),
                    _evidence_panel(
                        "物价压力",
                        "UPSTREAM → PRODUCER → CONSUMER",
                        document.get("price_pressure"),
                        _grouped_evidence(price_chain),
                        as_of=as_of,
                        note="能源只解释广义 CPI、PPI 与投入成本，不是核心 CPI 直接组成。",
                    ),
                ],
                className="content-section",
            ),
            html.Section(
                [
                    _section_heading("国际环境", "P2 CONTEXT ONLY · NO SCORE"),
                    html.Ul(
                        [
                            _evidence_row(item, as_of=as_of, international=True)
                            for item in international
                        ],
                        className="record-list",
                    )
                    if international
                    else _empty_state(
                        "国际背景尚无目录数据",
                        "P2 缺失不影响中国正式阶段和页面整体可用性。",
                    ),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _inventory_page(projection: ProjectionSet | None) -> html.Div:
    document = _dataset(projection, "inventory")
    as_of = projection.envelope.system_as_of.isoformat() if projection is not None else None
    if document.get("output_structure") == CONFIRMATION_STRUCTURE:
        return _confirmation_inventory_page(document, _dataset(projection, "macro"))
    cards = document.get("cards")
    card_documents = (
        [item for item in cards if isinstance(item, dict)] if isinstance(cards, list) else []
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
                " · ".join(
                    (
                        _state_label(document.get("quadrant")),
                        _inventory_directions(document.get("directions")),
                    )
                ),
            ),
            html.Section(
                [
                    _section_heading("七张阶段特征卡", "NO AGGREGATE SCORE"),
                    html.Div(
                        [_inventory_card(item, as_of=as_of) for item in card_documents]
                        if card_documents
                        else _empty_state("特征卡待补齐", "当前投影尚无可用的库存特征证据。"),
                        className="evidence-card-grid",
                    ),
                ],
                className="content-section",
            ),
            _domain_panel(
                "价格调整后的近似实际库存",
                "DERIVED · NOT AN OFFICIAL STATISTIC",
                _formula_summary(document.get("real_inventory_approximation")),
            ),
            html.Section(
                [
                    _section_heading("口径边界", "SEMANTIC GUARDRAILS"),
                    html.P(
                        "PMI 库存是扩散指数，不是库存数量；注册仓单不代表产业总库存。",
                        className="body-copy",
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
    lookback = document.get("last_confirmed_lookback")
    return html.Div(
        [
            _page_heading("阶段历史", "FORMAL STAGE HISTORY"),
            html.P(
                "正式区间、非典型组合与不可用空档均显式保留，不连续填充。",
                className="body-copy page-intro",
            ),
            *([_lookback_section(lookback)] if isinstance(lookback, dict) else []),
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


def _lookback_section(lookback: dict[str, object]) -> html.Section:
    return html.Section(
        [
            _section_heading("窗口前的上一确认阶段", "LOOKBACK BEFORE THE WINDOW"),
            html.P(_last_confirmed_label(lookback.get("stage"), lookback), className="body-copy"),
            html.P(
                f"回溯 {lookback.get('years')} 年，区间请求 {lookback.get('core_requests')} 次、"
                f"日历请求 {lookback.get('calendar_requests')} 次；"
                "回溯的价格只用于找出上一确认阶段，不进入宏观确认度与模型输入。",
                className="secondary-copy",
            ),
        ],
        className="content-section",
    )


def _release_calendar_page(
    projection: ProjectionSet | None,
    release_events: Sequence[dict[str, object]],
) -> html.Div:
    return html.Div(
        [
            _page_heading("发布日历", "RELEASE CALENDAR"),
            *_release_calendar_body(projection, release_events),
        ],
        className="page-stack",
    )


def _release_calendar_body(
    projection: ProjectionSet | None,
    release_events: Sequence[dict[str, object]],
) -> list[Any]:
    """The calendar of the selected projection: its frozen events, else the retained ones
    read for its model and cutoff."""
    document = _dataset(projection, "release_calendar")
    projected_events = document.get("events")
    rows = (
        [item for item in projected_events if isinstance(item, dict)]
        if isinstance(projected_events, list)
        else list(release_events)
    )
    return [
        html.P(
            "日历上下文："
            + projection.envelope.projection_set_id
            + " · 分析截止 "
            + projection.envelope.system_as_of.isoformat()
            + (
                " · 使用投影内事件。"
                if isinstance(projected_events, list)
                else " · 按该模型与截止读取留存事件。"
            )
            if projection
            else "尚无分析投影；独立日历按当前模型与查询时点读取。"
        ),
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
    ]


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
                        " · ".join(f"{key}: {_display_value(document.get(key))}" for key in keys),
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


def _macro_summary(document: dict[str, object]) -> html.Div:
    if not document:
        return _empty_state(
            "宏观证据尚未发布",
            "P1/P2 缺口不影响三核心资产和正式阶段的读取。",
        )
    if document.get("output_structure") == CONFIRMATION_STRUCTURE:
        confirmation = _object_document(document.get("confirmation"))
        return html.Div(
            [
                html.P(_confirmation_scope(confirmation), className="body-copy"),
                html.Div(
                    [
                        _domain_panel(
                            _DIMENSION_LABELS.get(str(item.get("dimension")), "维度"),
                            str(item.get("dimension", "")).upper(),
                            _dimension_counts(item),
                        )
                        for item in _document_list(confirmation.get("dimensions"))
                    ],
                    className="evidence-card-grid macro-summary-grid",
                ),
                html.Ul(
                    [
                        html.Li(_indicator_line(indicator), className="record-row")
                        for item in _document_list(confirmation.get("dimensions"))
                        for indicator in _document_list(item.get("key_indicators"))
                    ],
                    className="record-list",
                ),
            ]
        )
    summaries = (
        ("政策方向", "POLICY", document.get("policy_direction")),
        ("信用响应", "CREDIT", document.get("credit_response")),
        ("过热程度", "OVERHEAT", document.get("overheat_state")),
        ("物价压力", "PRICE", document.get("price_pressure")),
    )
    return html.Div(
        [_domain_panel(title, kicker, _state_label(value)) for title, kicker, value in summaries],
        className="evidence-card-grid macro-summary-grid",
    )


_DIMENSION_LABELS = {
    "policy": "政策",
    "credit": "信用",
    "overheat": "过热",
    "price": "物价",
    "inventory": "库存",
}
_RELATION_LABELS = {
    "support": "支持",
    "counterevidence": "反证",
    "observation_only": "仅观察",
    "unconfirmed": "未确认",
    "not_applicable": "不适用",
}
_MEMBER_LABELS = {
    "manufacturing": "制造业 PMI",
    "new_orders": "新订单",
    "production": "生产",
    "purchase_volume": "采购量",
}
_READING_LABELS = {
    "momentum": {"up": "较上期上升", "down": "较上期下降", "flat": "较上期持平"},
    "slope": {"steeper": "斜率变陡", "slower": "斜率放缓", "turn": "斜率转向", "flat": "斜率持平"},
    "position": {"high": "一年区间高位", "middle": "一年区间中段", "low": "一年区间低位"},
    "change_size": {"marked": "变化明显", "ordinary": "变化不明显"},
    "consistency": {
        "main": "主要成员",
        "agrees": "与主要成员一致",
        "opposes": "与主要成员相反",
        "flat": "持平",
        "unknown": "方向未知",
        "not_compared": "仅展示，不比较方向",
    },
}
# A change the source states on the same period a year before: capacity utilisation's.
_STATED_CHANGE_LABELS = {"up": "较上年同期上升", "down": "较上年同期下降", "flat": "与上年同期持平"}


def _confirmation_scope(confirmation: dict[str, object]) -> str:
    if confirmation.get("applicable") is True:
        return f"对照{_stage_label(confirmation.get('stage'))}的预期计数；确认度不改变正式阶段。"
    return "当前没有正式阶段，确认度不适用；各关键指标读法照常列出。"


def _dimension_counts(dimension: dict[str, object]) -> str:
    counts = dimension.get("counts")
    if dimension.get("status") != "connected" or not isinstance(counts, dict):
        return "尚未接入"
    return " · ".join(
        f"{label} {_integer(counts.get(relation))}"
        for relation, label in _RELATION_LABELS.items()
        if relation != "not_applicable" or _integer(counts.get(relation))
    )


def _indicator_line(indicator: dict[str, object]) -> str:
    main = next(iter(_document_list(indicator.get("members"))), {})
    relation = _RELATION_LABELS.get(str(indicator.get("relation")), "不可用")
    parts = [
        f"{indicator.get('name')}：{relation}",
        _member_reading(main, indicator.get("level_line")),
    ]
    if indicator.get("proposition"):
        parts.append(f"命题：{indicator['proposition']}")
    return " · ".join(parts)


_ACTION_LABELS = {"cut": "下调", "hike": "上调"}


def _action_reading(member: dict[str, object]) -> str:
    """A policy member's actions in the evidence window, from the value in force before it."""
    actions = _document_list(member.get("actions"))
    latest = (
        "窗口内最近动作："
        + _ACTION_LABELS.get(str(actions[-1].get("action")), "未知")
        + f"（{actions[-1].get('period')}，变动 {_display_value(actions[-1].get('change'))}"
        + (
            f"，释放资金 {_display_value(actions[-1].get('released'))}"
            if actions[-1].get("released") is not None
            else ""
        )
        + "）"
        if actions
        else "窗口内无动作"
        if member.get("action") == "none"
        else "动作未知"
    )
    baseline = _object_document(member.get("baseline"))
    return "，".join(
        item
        for item in (
            f"{member.get('period')} 值 {_display_value(member.get('value'))}",
            latest,
            f"窗口自 {member.get('window_start')}",
            f"窗口前基准 {baseline.get('period')} 值 {_display_value(baseline.get('value'))}"
            if baseline
            else "",
        )
        if item
    )


_QUADRANT_LABELS = {
    "active_destocking": "主动去库存",
    "passive_destocking": "被动去库存",
    "active_restocking": "主动补库存",
    "passive_restocking": "被动补库存",
    "unclassified": "未分类",
}
_LINE_LABELS = {"demand": "需求", "production": "生产", "inventory": "库存"}
_DIRECTION_LABELS = {"up": "上升", "down": "下降", "flat": "持平"}


def _quadrant_reading(member: dict[str, object]) -> str:
    """The quadrant, why it is unclassified when it is, and each line's direction."""
    quadrant = _QUADRANT_LABELS.get(str(member.get("quadrant")), "未分类")
    reason = {"insufficient": "三条线缺数或月份不齐", "inconsistent": "三条线方向不构成象限"}
    because = reason.get(str(member.get("unclassified_by")))
    lines = _object_document(member.get("lines"))
    directions = "，".join(
        label
        + _DIRECTION_LABELS.get(str(_object_document(lines.get(line)).get("direction")), "方向未知")
        for line, label in _LINE_LABELS.items()
    )
    period = f"{member['period']} " if member.get("period") else ""
    return "，".join((f"{period}{quadrant}" + (f"（{because}）" if because else ""), directions))


def _member_reading(member: dict[str, object], line: object) -> str:
    if "quadrant" in member:
        return _quadrant_reading(member)
    if member.get("value") is None:
        return f"无可用读数（{_state_label(member.get('evidence_status'))}）"
    if "action" in member:
        return _action_reading(member)
    level = {"above": "高于", "below": "低于", "at": "等于"}.get(str(member.get("level")), "")
    # A daily member reads each period's mean or sum against the line in force at its end.
    lines = _list_of(member.get("lines"))
    if lines:
        line = lines[-1]
    sessions = (
        f"每期 {member.get('period_sessions')} 个交易日"
        + {"mean": "均值", "sum": "合计"}.get(str(member.get("aggregate")), "")
        if member.get("period_sessions")
        else ""
    )
    # A member shown alone has no direction said: a year-to-date level rises regardless.
    shown_alone = member.get("consistency") == "not_compared"
    readings = [
        f"{member.get('period')} 值 {_display_value(member.get('value'))}",
        sessions,
        f"{level} {_display_value(line)}" if level else "",
        # A flow read against a year before agrees by its sign: more or less.
        {"up": "较去年同月多增", "down": "较去年同月少增", "flat": "与去年同月持平"}.get(
            str(member.get("direction")), "方向未知"
        )
        if member.get("agrees_by") == "sign"
        else ""
        if shown_alone
        else _STATED_CHANGE_LABELS.get(str(member.get("momentum")), "动量未知")
        if member.get("change_from")
        else _READING_LABELS["momentum"].get(str(member.get("momentum")), "动量未知"),
        "" if shown_alone else _READING_LABELS["slope"].get(str(member.get("slope")), "斜率未知"),
        # A year's range and change size, for a member read over a year.
        *(
            _READING_LABELS[name].get(str(member.get(name)), "")
            for name in ("position", "change_size")
        ),
        # A period read from the member standing in says so: a cumulative February.
        *(
            f"{item.get('period')} 为{item.get('label')}"
            for item in _document_list(member.get("stand_ins"))
        ),
        # Year-to-date figures throughout: industrial profits, nominal GDP.
        "累计口径（年初至今）" if member.get("cumulative") is True else "",
    ]
    return "，".join(item for item in readings if item)


def _confirmation_macro_page(document: dict[str, object], *, as_of: str | None) -> html.Div:
    confirmation = _object_document(document.get("confirmation"))
    international = _document_list(document.get("international_context"))
    sections = []
    for dimension in _document_list(confirmation.get("dimensions")):
        name = _DIMENSION_LABELS.get(str(dimension.get("dimension")), "维度")
        indicators = _document_list(dimension.get("key_indicators"))
        sections.append(
            html.Section(
                [
                    _section_heading(name, _dimension_counts(dimension)),
                    html.Div(
                        [_indicator_card(item) for item in indicators],
                        className="evidence-card-grid",
                    )
                    if indicators
                    else _empty_state(f"{name}维度尚未接入", "该维度的关键指标尚未纳入当前模型。"),
                ],
                className="content-section",
            )
        )
    return html.Div(
        [
            _page_heading("宏观证据", "MACRO CONFIRMATION · DIMENSION SUMMARY"),
            html.P(_confirmation_scope(confirmation), className="body-copy page-intro"),
            *sections,
            *_price_sections(document),
            *_attribution_sections(document),
            html.Section(
                [
                    _section_heading("国际环境", "P2 CONTEXT ONLY · NO SCORE"),
                    html.Ul(
                        [
                            _evidence_row(item, as_of=as_of, international=True)
                            for item in international
                        ],
                        className="record-list",
                    )
                    if international
                    else _empty_state(
                        "国际背景尚无目录数据",
                        "P2 缺失不影响中国正式阶段和页面整体可用性。",
                    ),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _price_sections(document: dict[str, object]) -> list[html.Section]:
    """What is shown beside the dimension summary, never counted: the cores' price internal
    consistency, their observation interfaces and the supply-demand note (ticket 09)."""
    sections = []
    consistency = _object_document(document.get("price_consistency"))
    if consistency:
        sections.append(
            html.Section(
                [
                    _section_heading("价格内部一致性（不计数）", "PRICE CONSISTENCY · NOT COUNTED"),
                    html.Ul(
                        [
                            html.Li(line, className="record-row")
                            for line in _consistency_lines(consistency)
                        ],
                        className="record-list",
                    ),
                ],
                className="content-section",
            )
        )
    interfaces = _object_document(document.get("observation_interfaces"))
    if interfaces:
        sections.append(
            html.Section(
                [
                    _section_heading("观察接口（只展示，不计数）", "OBSERVATION INTERFACES"),
                    *(
                        html.Div(
                            [
                                html.P(
                                    f"{core.get('label')} {core.get('core_metric_id')}",
                                    className="secondary-copy",
                                ),
                                html.Ul(
                                    [
                                        html.Li(_interface_line(member), className="record-row")
                                        for member in _document_list(core.get("members"))
                                    ],
                                    className="record-list",
                                ),
                            ]
                        )
                        for core in _document_list(interfaces.get("cores"))
                    ),
                ],
                className="content-section",
            )
        )
    sections.extend(_supply_demand_sections(document))
    return sections


def _supply_demand_sections(document: dict[str, object]) -> list[html.Section]:
    """The commodity supply-demand note, never counted."""
    note = _object_document(document.get("supply_demand"))
    if not note:
        return []
    lines = [
        str(note.get("headline")),
        str(note.get("text")),
        *(str(note[key]) for key in ("supply_suspicion", "registered_warrants") if note.get(key)),
        str(note.get("boundary")),
    ]
    if note.get("missing"):
        lines.append("缺：" + "、".join(str(item) for item in _list_of(note["missing"])))
    return [
        html.Section(
            [
                _section_heading("商品供需附注（不计数）", "SUPPLY AND DEMAND · NOTE ONLY"),
                *(html.P(line, className="body-copy") for line in lines),
            ],
            className="content-section",
        )
    ]


def _attribution_sections(document: dict[str, object]) -> list[html.Section]:
    """What drives the bond's trend, beside its state, never counted (ticket 10)."""
    lines = _attribution_lines(document)
    if not lines:
        return []
    return [
        html.Section(
            [
                _section_heading("债券归因（不计数）", "BOND TREND ATTRIBUTION · NOTE ONLY"),
                *(html.P(line, className="body-copy") for line in lines),
            ],
            className="content-section",
        )
    ]


def _attribution_lines(document: dict[str, object], *, brief: bool = False) -> list[str]:
    """The driver with the bond's price and each axis first, then why it is unclear, the
    signals read and the notes; ``brief``, the driver and the notes alone. The bond core
    is a price index: said as its price."""
    note = _object_document(document.get("bond_attribution"))
    if not note:
        return []
    axes = _document_list(note.get("axes"))
    detail = "".join(f"（{note[key]}）" for key in ("typical", "suspicion") if note.get(key))
    lines = [
        "；".join(
            [
                str(note.get("bond_text")),
                *(f"{axis.get('label')}{axis.get('text')}" for axis in axes),
            ]
        )
        + f" → {note.get('text')}{detail}"
    ]
    if brief:
        return [lines[0] + "；" + "；".join(str(item) for item in _list_of(note.get("notes")))]
    lines.extend(str(item.get("text")) for item in _document_list(note.get("reasons")))
    for axis in axes:
        lines.append(
            f"{axis.get('label')}："
            + "、".join(
                f"{signal.get('label')} " + _SIGNAL_WORDS.get(str(signal.get("value")), "未知")
                for signal in _document_list(axis.get("signals"))
            )
        )
    lines.extend(str(item) for item in _list_of(note.get("notes")))
    lines.append(str(note.get("boundary")))
    return lines


_MOVES = {"up": "向上", "down": "向下", "flat": "持平"}
_SIGNAL_WORDS = {
    "cut": "下调",
    "hike": "上调",
    "none": "无动作",
    "up": "上升",
    "down": "下降",
    "flat": "持平",
}


def _consistency_lines(document: dict[str, object]) -> list[str]:
    """Each pair's 120-session return difference, the breadth and the sleeves, and where
    the stage expects the cores to stand."""
    span = (
        f"{document.get('first_session')}～{document.get('last_session')}"
        if document.get("first_session")
        else "交易日历未覆盖"
    )
    lines = [f"相对动量：{document.get('sessions')} 个交易日收益差，需对齐的实际价格点（{span}）"]
    for pair in _document_list(document.get("relative_momentum")):
        value = pair.get("value_pp")
        lines.append(
            f"{pair.get('label')}：{value:+.2f} 个百分点，"
            + _MOVES.get(str(pair.get("direction")), "")
            if isinstance(value, (int, float))
            else f"{pair.get('label')}：未确认，缺："
            + "、".join(str(item) for item in _list_of(pair.get("missing")))
        )
    for key in ("stock_breadth", "basket_breadth"):
        item = _object_document(document.get(key))
        if not item:
            continue
        reading = (
            str(item.get("text"))
            if item.get("text")
            else "未确认，缺：" + "、".join(str(gap) for gap in _list_of(item.get("missing")))
        )
        detail = (
            f"（占比 {_display_value(item.get('share'))}%，"
            f"以 {_display_value(item.get('line'))}% 为多数线）"
            if key == "stock_breadth" and item.get("share") is not None
            else f"（{item.get('along')}/{item.get('of')} 个分项同向）"
            if key == "basket_breadth" and item.get("along") is not None
            else ""
        )
        lines.append(f"{item.get('label')}：{reading}{detail}")
    position = _object_document(document.get("position"))
    if position.get("applicable"):
        agrees = position.get("agrees")
        held = "符合" if agrees is True else "不符" if agrees is False else "未定"
        lines.append(f"阶段位置：{position.get('text')}（{held}）")
        lines.extend(
            f"转折提示：{hint.get('text')}" for hint in _document_list(position.get("turn_hints"))
        )
        lines.extend(str(note) for note in _list_of(position.get("notes")))
    else:
        lines.append("阶段位置：非典型组合，不给出阶段位置")
    return lines


def _interface_line(member: dict[str, object]) -> str:
    """A member's rows as shown: a bond price says only which way the price moved."""
    if member.get("in_catalog") is False:
        return f"{member.get('label')}：当前目录未收录"
    rows = [
        " ".join(
            part
            for part in (
                str(row.get("period") or "无可用读数"),
                _display_value(row.get("value")),
                _bond_price_reading(str(member.get("metric_id")), row.get("direction"))
                if member.get("reads_as") == "bond_price"
                else "",
            )
            if part
        )
        for row in _document_list(member.get("evidence"))
    ]
    return f"{member.get('label')}：" + ("；".join(rows) if rows else "无可用读数")


def _indicator_card(indicator: dict[str, object]) -> html.Article:
    details = [
        {"consistent": "成员一致", "divergent": "成员分化", "unknown": "方向未知"}.get(
            str(indicator.get("consistency")), "方向未知"
        )
    ]
    if indicator.get("proposition"):
        details.append(f"命题：{indicator['proposition']}")
    capped = [str(cap) for cap in _list_of(indicator.get("capped_by"))]
    # A cap's note is said once, with what it does to the relation.
    details.extend(
        str(note) for note in _list_of(indicator.get("notes")) if str(note) not in capped
    )
    if indicator.get("timing") in _TIMING_LABELS:
        details.append(f"时序：{_TIMING_LABELS[str(indicator['timing'])]}")
    if indicator.get("turn_hint"):
        details.append(f"转折提示：接近{_stage_label(indicator['turn_hint'])}")
    details.extend(_turn_details(_object_document(indicator.get("turn"))))
    details.extend(_grace_details(_object_document(indicator.get("grace"))))
    if indicator.get("divergence_capped"):
        details.append("成员分化，不高于仅观察")
    details.extend(f"{cap}，不高于仅观察" for cap in capped)
    for derived in _document_list(indicator.get("derived")):
        reading = (
            f"{derived.get('period')} 值 {_display_value(derived.get('value'))}"
            if derived.get("value") is not None
            else "无可用读数"
        )
        details.append(
            f"{derived.get('label')}（派生，不计数，{derived.get('formula_version')}）：{reading}"
        )
    if indicator.get("missing"):
        details.append("缺：" + "、".join(str(item) for item in _list_of(indicator["missing"])))
    members = [
        html.Li(
            " · ".join(
                (
                    str(member.get("label"))
                    if member.get("label")
                    else _MEMBER_LABELS.get(
                        str(_object_document(member.get("member")).get("series")),
                        _display_value(member.get("member")),
                    ),
                    _READING_LABELS["consistency"].get(str(member.get("consistency")), "方向未知"),
                    _member_reading(member, indicator.get("level_line")),
                )
            ),
            className="record-row",
        )
        for member in _document_list(indicator.get("members"))
    ]
    return html.Article(
        [
            html.P(str(indicator.get("metric_id", "")), className="section-kicker"),
            html.H3(str(indicator.get("name", "")), className="card-title"),
            html.P(
                _RELATION_LABELS.get(str(indicator.get("relation")), "不可用"),
                className="body-copy domain-value",
            ),
            *(html.P(item, className="secondary-copy") for item in details),
            html.Ul(members, className="record-list"),
        ],
        className="domain-panel evidence-panel",
    )


_TIMING_LABELS = {"leading": "先行", "coincident": "同步", "lagging": "滞后"}
_MATURITY_LABELS = {"sprout": "萌芽", "forming": "成形", "confirmed": "确认"}
_GRACE_UNITS = {"month": "个月", "quarter": "个季度", "sessions": "期（按交易日分期）"}


def _turn_details(turn: dict[str, object]) -> list[str]:
    """A turn signal: the stage a lag still shows, its maturity and how long it held."""
    if not turn:
        return []
    details = []
    if turn.get("basis") == "lagging" and turn.get("toward"):
        details.append(f"滞后未转：仍呈{_stage_label(turn['toward'])}形态")
    maturity = _MATURITY_LABELS.get(str(turn.get("maturity")), "成熟度未定")
    if turn.get("confirmed_by") == "transmission":
        maturity += "，已传导"
    held = _held(turn)
    details.append(f"转折观察：{maturity}（{held}）" if held else f"转折观察：{maturity}")
    together = [str(key) for key in _list_of(turn.get("leading_signals"))]
    if together:
        details.append("与同向先行信号共同成形：" + "、".join(together))
    if turn.get("missing"):
        details.append("成熟度缺：" + "、".join(str(item) for item in _list_of(turn["missing"])))
    return details


def _grace_details(grace: dict[str, object]) -> list[str]:
    """How long a counterevidence waiting on grace has held, against its grace."""
    if not grace:
        return []
    past = grace.get("past")
    state = "已过宽限" if past is True else "未过宽限" if past is False else "是否过宽限未定"
    if grace.get("confirmed_by") == "transmission":
        state = "已传导确认"
    unit = _GRACE_UNITS.get(str(grace.get("unit")), "期")
    held = _held(grace) or f"已持续 {grace.get('periods')} 期"
    return [f"宽限：反证条件{held}，宽限 {grace.get('limit')} {unit}，{state}"]


def _held(run: dict[str, object]) -> str:
    """How long a signal held: since a period, or at least as far back as was read."""
    if run.get("at_least"):
        return f"至少已持续 {run.get('periods')} 期，起点早于所读历史"
    if run.get("since"):
        return f"已持续 {run.get('periods')} 期，自 {run.get('since')}"
    return ""


def _confirmation_inventory_page(document: dict[str, object], macro: dict[str, object]) -> html.Div:
    """The inventory dimension: its quadrant the one count, each card's data apart from the
    quadrant's relation, the registered warrants a note, the real inventory approximation a
    rough proxy beside them."""
    confirmation = _object_document(macro.get("confirmation"))
    quadrant = next(
        (
            item
            for dimension in _document_list(confirmation.get("dimensions"))
            if dimension.get("dimension") == "inventory"
            for item in _document_list(dimension.get("key_indicators"))
        ),
        None,
    )
    if document.get("status") != "connected" or quadrant is None:
        body: list[Any] = [
            _empty_state("库存维度尚未接入", "当前模型的库存象限规则尚未接入，不给出象限或特征卡。")
        ]
    else:
        body = [
            html.P(
                "库存维度以库存象限为结论，作为一项计数；单个库存指标不单独计数。",
                className="body-copy page-intro",
            ),
            html.Div([_indicator_card(quadrant)], className="evidence-card-grid"),
            html.Section(
                [
                    _section_heading("库存卡", "DATA AVAILABILITY · RELATION APART"),
                    html.Ul(
                        [
                            html.Li(_inventory_card_line(card), className="record-row")
                            for card in _document_list(document.get("cards"))
                        ],
                        className="record-list",
                    ),
                ],
                className="content-section",
            ),
        ]
    warrants = _object_document(document.get("registered_warrants"))
    return html.Div(
        [
            _page_heading("库存特征", "INVENTORY CHARACTERISTICS"),
            *body,
            *(
                [
                    html.Section(
                        [
                            _section_heading("注册库存变化（附注，不计数）", "FUTURES WARRANTS"),
                            html.P(_warrant_summary(warrants), className="body-copy"),
                            html.Ul(
                                [
                                    html.Li(_warrant_line(item), className="record-row")
                                    for item in _document_list(warrants.get("symbols"))
                                ],
                                className="record-list",
                            ),
                        ],
                        className="content-section",
                    )
                ]
                if warrants
                else []
            ),
            _domain_panel(
                "实际库存近似（粗略价格调整代理）",
                "DERIVED · ROUGH PROXY · NOT COUNTED",
                _formula_summary(document.get("real_inventory_approximation"))
                + " · 不计数，不参与库存象限",
            ),
            html.Section(
                [
                    _section_heading("口径边界", "SEMANTIC GUARDRAILS"),
                    html.P(
                        "PMI 库存是扩散指数，不是库存数量；注册仓单不代表产业总库存；"
                        "实际库存近似只是名义产成品存货按 PPI 的粗略调整，不是不变价库存。",
                        className="body-copy",
                    ),
                ],
                className="content-section",
            ),
        ],
        className="page-stack",
    )


def _inventory_card_line(card: dict[str, object]) -> str:
    """A card: its data there or not, and apart from it the relation the quadrant bears."""
    available = (
        "数据可用"
        if card.get("availability") == "available"
        else f"数据不可用（{_state_label(card.get('evidence_status'))}）"
    )
    relation = _RELATION_LABELS.get(str(card.get("relation")), "不可用")
    return " · ".join(
        (
            str(card.get("label")),
            available,
            f"确认关系（随库存象限）：{relation}",
            _READING_LABELS["consistency"].get(str(card.get("consistency")), "方向未知"),
        )
    )


def _warrant_summary(note: dict[str, object]) -> str:
    """The warrants' median change and breadth, the seven symbols' tonnes beside them."""
    breadth = _object_document(note.get("breadth"))
    tonnes = _object_document(note.get("tonnes"))
    median = note.get("median_change_rate")
    parts = [
        f"{note.get('first_day')} 至 {note.get('last_day')}"
        if note.get("first_day")
        else "窗口内无共同日期",
        f"变化率中位数 {median:.1%}" if isinstance(median, (int, float)) else "变化率中位数不可用",
        f"增加 {_integer(breadth.get('increase'))}、持平 {_integer(breadth.get('flat'))}、"
        f"减少 {_integer(breadth.get('decrease'))}（读到 {_integer(breadth.get('read'))}/"
        f"{_integer(breadth.get('symbols'))} 个品种）",
        (
            f"七品种折算吨数合计（辅助）{_display_value(tonnes.get('first'))} → "
            f"{_display_value(tonnes.get('last'))}"
            if tonnes.get("first") is not None
            else "七品种折算吨数合计不可用"
        ),
        "原油按桶数单列，不进吨数合计",
    ]
    if note.get("missing"):
        parts.append("缺：" + "、".join(str(item) for item in _list_of(note["missing"])))
    return " · ".join(parts)


_WARRANT_UNITS = {"sheet": "张", "lot": "手", "tonne": "吨", "barrel": "桶"}
_WARRANT_STATES = {
    "missing": "窗口内未持有",
    "unit_refused": "单位与换算表不符，未换算",
    "zero_base": "基期为零，无变化率",
    "no_common_span": "窗口内无共同日期",
}


def _warrant_line(item: dict[str, object]) -> str:
    """A symbol's warrants first and last, converted as the frozen table says."""
    unit = _WARRANT_UNITS.get(str(item.get("unit")), str(item.get("unit")))
    rate, factor = item.get("change_rate"), item.get("factor")
    reading = (
        f"{_display_value(item.get('first'))} → {_display_value(item.get('last'))} {unit}"
        if item.get("first") is not None
        else ""
    )
    name = display_name("CN_FUTURES_WARRANTS", {"symbol": item.get("symbol")}).name
    return " · ".join(
        part
        for part in (
            f"{name}（{item.get('symbol')}）" if name != item.get("symbol") else name,
            reading,
            f"{rate:+.1%}" if isinstance(rate, (int, float)) else "",
            _WARRANT_STATES.get(str(item.get("status")), ""),
            f"换算：每{_WARRANT_UNITS.get(str(item.get('input_unit')), '')} {factor:g} {unit}"
            f"（{item.get('weight_basis')}）"
            if isinstance(factor, (int, float))
            else "",
        )
        if part
    )


def _list_of(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _evidence_panel(
    title: str,
    kicker: str,
    state: object,
    evidence: list[dict[str, object]],
    *,
    as_of: str | None,
    note: str | None = None,
) -> html.Article:
    children: list[Any] = [
        html.P(kicker, className="section-kicker"),
        html.H3(title, className="card-title"),
        html.P(_state_label(state), className="body-copy domain-value"),
    ]
    if note:
        children.append(html.P(note, className="secondary-copy"))
    children.append(
        html.Ul(
            [_evidence_row(item, as_of=as_of) for item in evidence],
            className="record-list",
        )
        if evidence
        else _empty_state("当前没有可用证据", "待发布、陈旧和来源失败会在此明确显示。")
    )
    return html.Article(children, className="domain-panel evidence-panel")


def _evidence_row(
    item: dict[str, object],
    *,
    as_of: str | None,
    international: bool = False,
) -> html.Li:
    metric_id = str(item.get("metric_id") or "metric_identity_unavailable")
    status = item.get("status", item.get("freshness", "unknown"))
    value = item.get("value")
    unit = item.get("unit")
    source = item.get("source_reference")
    observation_id = item.get("observation_id")
    details = [
        f"方向 {_state_label(item.get('direction'))}",
        f"统计期 {_display_value(item.get('period'))}",
        f"状态 {_state_label(status)}",
        f"值 {_display_value(value, unit=unit)} {_display_value(unit)}",
        f"认证 {_display_value(item.get('certification_status'))}",
        f"来源 {_source_label(source)}",
    ]
    bond_price = _bond_price_reading(metric_id, item.get("direction"))
    if bond_price:
        details.append(bond_price)
    if international:
        if item.get("acquisition_status") is not None:
            details.append(f"最近获取 {_state_label(item['acquisition_status'])}")
        acquisition = item.get("latest_acquisition")
        if isinstance(acquisition, dict):
            for key, label in (
                ("latest_source_period", "来源已见最新期"),
                ("release_date", "当前批次发布日"),
                ("next_release_date", "下次计划发布日"),
                ("external_code", "来源返回码"),
                ("rule_reason", "拒收原因"),
                ("error_type", "异常类"),
            ):
                if acquisition.get(key) is not None:
                    details.append(f"{label} {_display_value(acquisition[key])}")
            if acquisition.get("missing_members"):
                details.append(f"缺失成员 {len(acquisition['missing_members'])} 项")
            timezone = acquisition.get("release_timezone") or acquisition.get("source_timezone")
            if timezone is not None:
                details.append(f"来源时区 {_display_value(timezone)}")
        boundary = _international_boundary(metric_id)
        if boundary:
            details.append(boundary)
    children: list[Any] = [
        html.Strong(str(item.get("name_cn") or metric_id)),
        html.Span(" · ".join(details), className="secondary-copy"),
    ]
    claims = _document_list(item.get("claims"))
    if claims:
        children.append(
            html.Div(
                [html.Span(_claim_summary(claim)) for claim in claims],
                className="claim-list secondary-copy",
            )
        )
    if (
        isinstance(observation_id, str)
        and not observation_id.startswith("gap:")
        and as_of is not None
    ):
        children.append(
            html.A(
                f"证据 {observation_id}",
                href=_evidence_href(observation_id, as_of),
                className="evidence-link",
            )
        )
    return html.Li(children, className="record-row")


def _evidence_links(value: object, *, as_of: str | None) -> html.Div:
    identifiers = (
        [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
    )
    if not identifiers:
        return html.Div("证据：当前缺失", className="secondary-copy")
    links: list[Any] = []
    for identifier in identifiers:
        if as_of is None or identifier.startswith("gap:"):
            links.append(html.Span(f"证据 {identifier}"))
        else:
            links.append(
                html.A(
                    f"证据 {identifier}",
                    href=_evidence_href(identifier, as_of),
                    className="evidence-link",
                )
            )
    return html.Div(links, className="evidence-links")


def _evidence_href(identifier: str, as_of: str) -> str:
    query = urlencode({"mode": "system_as_of", "as_of": as_of})
    return f"/api/v1/evidence/{identifier}?{query}"


def _grouped_evidence(document: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in ("support", "counterevidence", "gaps"):
        rows.extend(_document_list(document.get(key)))
    return rows


def _document_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _object_document(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _formula_summary(value: object) -> str:
    document = _object_document(value)
    if not document:
        return "公式状态：不可用"
    parts = [
        f"状态 {_state_label(document.get('status'))}",
        f"公式版本 {_display_value(document.get('formula_version'))}",
    ]
    if document.get("value") is not None:
        parts.append(f"值 {_display_value(document.get('value'))}")
    if document.get("derived_observation_id") is not None:
        parts.append(f"派生证据 {document['derived_observation_id']}")
    return " · ".join(parts)


def _inventory_directions(value: object) -> str:
    document = _object_document(value)
    return " · ".join(
        (
            f"需求 {_state_label(document.get('demand') or 'insufficient_data')}",
            f"生产 {_state_label(document.get('production') or 'insufficient_data')}",
            f"库存 {_state_label(document.get('inventory') or 'insufficient_data')}",
        )
    )


def _source_label(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "不可用"
    return value.split("#", maxsplit=1)[0]


def _claim_summary(document: dict[str, object]) -> str:
    selected = "（已选）" if document.get("selected") is True else ""
    return (
        f"来源声明 {_display_value(document.get('provider'))}="
        f"{_display_value(document.get('value'))} "
        f"{_display_value(document.get('unit'))}{selected}"
    )


# The bond indices are prices: say only which way the price moved. Whether policy eased
# is for the transmission group as a whole to tell.
def _bond_price_reading(metric_id: str, direction: object) -> str:
    if metric_id not in {"CN_BOND_10Y_930916", "CN_BOND_FULL_PRICE_CNY030"}:
        return ""
    return {"up": "债券价格走强", "down": "债券价格走弱"}.get(str(direction), "")


def _international_boundary(metric_id: str) -> str:
    if metric_id in {"UST10Y_NOMINAL_YIELD", "UST2Y_NOMINAL_YIELD"}:
        return "收益率方向，不是债券价格"
    if metric_id.startswith(("EIA_", "COMEX_", "LBMA_")):
        return "国际背景，不替代南华工业品指数"
    return ""


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
                    # A model without the proxy carries no field; shown only when it does.
                    *(
                        [_compact_fact("12 个月公开代理", _state_label(item.get("proxy_12m")))]
                        if "proxy_12m" in item
                        else []
                    ),
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


def _inventory_card(item: dict[str, object], *, as_of: str | None) -> html.Article:
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
            _evidence_links(item.get("evidence_ids"), as_of=as_of),
            html.Ul(
                [
                    _evidence_row(evidence, as_of=as_of)
                    for evidence in _document_list(item.get("evidence"))
                ],
                className="record-list",
            )
            if _document_list(item.get("evidence"))
            else None,
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
    note = _stage_correction_note(item.get("corrects"))
    correction = f" · 更正版本（{note}）" if note else ""
    return html.Li(
        [
            html.Strong(
                f"{item.get('business_date', '日期不可用')} · "
                f"{_stage_label(item.get('current_stage'))}{correction}"
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


def _stage_correction_note(corrects: object) -> str:
    """Why a day's correction version corrected the one before; empty for none."""
    note = _core_history_note(corrects)
    # A day whose last confirmed stage alone was corrected says so, and what the summary it
    # corrects said of itself (follow-up ticket 01).
    if isinstance(corrects, dict) and corrects.get("reason") == "stage_history_changed":
        carried = _core_history_note(corrects.get("carries"))
        note = "更早日的阶段历史已变，只更正上一确认阶段，核心、上下文与确认度沿用原汇总" + (
            f"；原汇总：{carried}" if carried else ""
        )
    return note


def _core_history_note(corrects: object) -> str:
    """A day summarized again on the cores' current history says so (ticket 07), and that
    its context was not, when its details had left retention (ticket 08)."""
    if not isinstance(corrects, dict) or corrects.get("reason") != "core_history_basis_changed":
        return ""
    if corrects.get("scope") == "core_only":
        return "核心历史口径变更；只更正核心与正式阶段，上下文与确认度未重算：明细已超出留存"
    return "核心历史口径变更"


def _gap_label(value: str) -> str:
    asset, separator, reason = value.partition(":")
    if not separator:
        return value
    asset_label = {
        "bond": "债券",
        "stock": "股票",
        "commodity": "商品",
    }.get(asset, asset)
    return f"{asset_label}：{CORE_GAP_REASON_LABELS.get(reason, reason)}"


# Why a core could not be read, as the P0 gate records it.
CORE_GAP_REASON_LABELS = {
    "insufficient_history": "历史不足",
    "source_conflict": "来源冲突",
    "source_missing": "来源缺失",
    "stale_for_target_business_date": "目标日数据陈旧",
    "source_identity_invalid": "来源身份不符",
    "nonnumeric_core_observation": "核心观测不是有效数值",
}


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


def _reports_page(
    reports: Sequence[ReportSnapshot],
    runs: Sequence[RunRecord],
) -> html.Div:
    history = [
        html.Li(
            [
                html.Strong(f"{item.target_business_date} · v{item.version}"),
                html.Span(
                    " · ".join(
                        (
                            f"状态 {item.status}",
                            f"适配器 {item.adapter}",
                            f"截止 {item.report_cutoff.isoformat()}",
                            f"耗时 {item.duration_ms}ms",
                            f"报告输入 {item.bundle_hash}",
                            f"模型 {item.model_version_id}",
                            f"提示 {item.prompt_version}",
                            f"Schema {item.schema_version}",
                            "正文保留" if item.body_retained else "正文已过保留期",
                            item.report_snapshot_id,
                        )
                    ),
                    className="secondary-copy",
                ),
            ],
            className="record-row",
        )
        for item in reports
    ]
    active = next(
        (
            item
            for item in runs
            if item.command_type in {"manual_full", "scheduled_full", "report_generation"}
            and item.current_step == "generating_report"
            and item.status not in {"completed", "cancelled", "failed"}
        ),
        None,
    )
    reading = (
        dcc.Tabs(
            [
                dcc.Tab(
                    _report_reader(item),
                    label=f"{item.target_business_date} · v{item.version}",
                    value=item.report_snapshot_id,
                )
                for item in reports
            ],
            value=reports[0].report_snapshot_id,
            className="report-reader-tabs",
        )
        if reports
        else _empty_state("尚未选择报告", "生成首个不可变报告后可在此阅读。")
    )
    return html.Div(
        [
            _page_heading("报告", "IMMUTABLE REPORT WORKSPACE"),
            dcc.Tabs(
                [
                    dcc.Tab(
                        [
                            html.H2("报告生成", className="section-title"),
                            html.P(
                                "生成命令冻结当前报告输入；AI 失败不会回滚分析投影。",
                                className="body-copy",
                            ),
                            html.P(
                                (
                                    f"当前任务：{active.status} · {active.current_step} · "
                                    f"{active.run_id}"
                                    if active is not None
                                    else "当前没有运行中的报告任务。"
                                ),
                                className="secondary-copy",
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
                            reading,
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
            html.P("持久运行记录", className="section-kicker"),
            html.Div(
                [
                    html.Button(
                        "发起手动完整运行",
                        id="manual-run-command",
                        className="primary-button",
                        type="button",
                    ),
                    dcc.DatePickerSingle(
                        id="manual-run-target",
                        date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
                        display_format="YYYY-MM-DD",
                        className="date-input",
                        persistence=True,
                        persistence_type="session",
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


_LEGACY_SECTION_REFERENCES = (("evidence_ids", "证据"), ("governance_refs", "治理引用"))


def _report_reader(report: ReportSnapshot) -> html.Div:
    head = _report_head(report)
    if not report.body_retained:
        return html.Div(
            [*head, _empty_state("正文已不在保留期", "结构化身份与报告输入仍在留存期内保留。")],
            className="report-reader",
        )
    body = report.body
    sections = body.get("ai_explanation")
    if isinstance(sections, list):
        content = [
            html.Section(
                [
                    html.H3(str(section.get("title") or "未命名章节")),
                    *(
                        [html.P("确定性模板", className="secondary-copy")]
                        if body.get("explanation_source") == "deterministic_template"
                        else []
                    ),
                    html.P(str(section.get("explanation") or ""), className="body-copy"),
                    # Reports before ADR-0027 cited evidence per paragraph; newer ones do not.
                    *(
                        html.P(
                            label + " " + "、".join(str(item) for item in section[key]),
                            className="secondary-copy",
                        )
                        for key, label in _LEGACY_SECTION_REFERENCES
                        if section.get(key)
                    ),
                ],
                className="report-section",
            )
            for section in sections
            if isinstance(section, dict)
        ]
    else:
        # A skeleton shows what its input held: verified results since ADR-0027, the
        # evidence context and references before it.
        facts = (
            ("三核心", "core_states"),
            ("已验证结果", "verified_results"),
            ("转折观察", "transition_watch"),
            ("宏观事后确认", "macro_confirmation"),
            ("政策与信用", "policy_context"),
            ("库存解释", "inventory_context"),
            ("物价传导", "price_context"),
            ("变化原因", "change_reasons"),
            ("支持证据", "support"),
            ("反证", "counterevidence"),
            ("数据缺口", "governance_gaps"),
        )
        content = [
            *(_report_fact_section(title, body[key]) for title, key in facts if key in body),
            html.Section([html.H3("缺口清单"), _gap_list(body.get("gap_list"))]),
            _report_fact_section("核心沿用上一期", body.get("core_carry_forward")),
            *(
                [_report_fact_section("绑定引用", body["evidence_references"])]
                if "evidence_references" in body
                else []
            ),
        ]
    results = body.get("verified_results")
    if isinstance(results, dict) and isinstance(results.get("noncanonical_basis"), dict):
        content.extend(
            [
                _report_fact_section("三核心", body.get("core_states")),
                _report_fact_section("已验证结果", body.get("verified_results")),
                html.Section([html.H3("缺口清单"), _gap_list(body.get("gap_list"))]),
            ]
        )
    return html.Div([*head, *content], className="report-reader")


def _report_head(report: ReportSnapshot) -> list[Any]:
    """A report's identity facts with its correction and calendar notes."""
    identity = html.Dl(
        [
            _compact_fact("报告身份", report.report_snapshot_id),
            _compact_fact("投影身份", report.projection_set_id),
            _compact_fact("正式阶段", _stage_label(report.current_stage)),
            *_report_last_confirmed(report.body),
            _compact_fact("截止点", report.report_cutoff.isoformat()),
            _compact_fact(
                "时效判定", freshness_statement(report.target_business_date, report.report_cutoff)
            ),
            _compact_fact("确定性输出", "已生成"),
            _compact_fact("AI解释", "不可用" if report.adapter == "deterministic" else "已生成"),
            _compact_fact(
                "解读来源",
                "确定性模板"
                if report.adapter == "deterministic"
                else "AI 解读 · " + report.adapter,
            ),
            _compact_fact(
                "解释证据核查",
                {
                    "passed": "已核查支持与反证",
                    "needs_attention": "存在无支持或矛盾叙述",
                    "pending_evidence_review": "结构与结论已校验，语义待核查",
                    "unavailable": "无AI解释",
                }.get(str(report.explanation_verification.get("status")), "未记录核查"),
            ),
        ],
        className="compact-facts",
    )
    basis = report.body.get("freshness_basis") if report.body_retained else None
    return [
        *_correction_notes(report.corrections, "本报告的投影", "报告"),
        identity,
        *_calendar_fallback_notice(basis.get("calendar") if isinstance(basis, dict) else None),
    ]


def _correction_notes(corrections: dict[str, Any], whose: str, kind: str) -> list[html.P]:
    """A projection or report computed on a value read for the wrong period stays as
    published, marked; a later one of its day says what it corrects (audit 06). ``whose``
    names the projection, ``kind`` what is shown."""
    notes = []
    if corrections.get("affected"):
        count = len({c for item in corrections["affected"] for c in item["claim_ids"]})
        corrected_by = corrections.get("corrected_by") or []
        notes.append(
            html.P(
                f"受错期值影响：{whose}有 {count} 项模型输入是期次不符的来源值或由其派生，"
                f"本{kind}按原样保留。"
                + (
                    "已由 " + "、".join(corrected_by) + " 更正。"
                    if corrected_by
                    else "尚无更正版本。"
                ),
                className="report-correction-note",
            )
        )
    if corrections.get("corrects"):
        notes.append(
            html.P(
                f"更正版本：本{kind}更正 "
                + "、".join(corrections["corrects"])
                + "（受错期值影响）。",
                className="report-correction-note",
            )
        )
    return notes


def _report_fact_section(title: str, value: object) -> html.Section:
    return html.Section(
        [
            html.H3(title),
            html.Details(
                [
                    html.Summary("展开报告绑定的结构化事实"),
                    html.Pre(_display_value(value), className="body-copy"),
                ]
            )
            if isinstance(value, (dict, list))
            else html.P(_display_value(value), className="body-copy"),
        ],
        className="report-section",
    )


def _run_row(item: RunRecord) -> html.Li:
    attempt_summary = "；".join(
        _retrieval_attempt_summary(attempt) for attempt in item.retrieval_attempts
    )
    budget = item.consumed_budget
    details = (
        f"{_state_label(item.current_step)} · 尝试 {item.attempt_count} · "
        f"预算 Tavily {budget['tavily']}/{RUN_SEARCH_LIMITS['tavily']}、"
        f"Exa {budget['exa']}/{RUN_SEARCH_LIMITS['exa']}、"
        f"AI {budget['ai_websearch']} · 下一动作 {_state_label(item.next_action)}"
    )
    if attempt_summary:
        details += f" · 检索 {attempt_summary}"
    actions: list[html.Button | html.Details] = []
    if item.status in {"interrupted", "action_required"} and item.recoverable:
        actions.append(
            html.Details(
                [
                    html.Summary("确认并继续"),
                    html.P("继续会恢复该运行，并允许尚未完成的外部调用。收起此处可放弃操作。"),
                    html.Button(
                        "允许外部调用并继续",
                        className="quiet-button run-action",
                        type="button",
                        **cast(Any, {"data-run-action": "resume", "data-run-id": item.run_id}),
                    ),
                ],
                className="resume-confirmation",
            )
        )
    if item.status in {"queued", "running"}:
        actions.append(
            html.Button(
                "取消后续步骤",
                className="quiet-button run-action",
                type="button",
                **cast(Any, {"data-run-action": "cancel", "data-run-id": item.run_id}),
            )
        )
    return html.Li(
        [
            html.Strong(f"{item.target_business_date} · {_state_label(item.status)}"),
            html.Span(details, className="secondary-copy"),
            *actions,
        ],
        className="record-row",
    )


def _poll_interval_ms(runs: Sequence[RunRecord]) -> int:
    return 30_000 if any(item.status in {"queued", "running"} for item in runs) else 300_000


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
    label = core_state_label(value)
    state = {"牛市": "up", "熊市": "down"}.get(label, "warning")
    return html.Span(f"{label} · {value}", className=f"state-badge state-{state}")


def _asset_label(asset: str) -> str:
    return {
        "bond": "债券 · 上证国债指数",
        "stock": "股票 · 中证全指",
        "commodity": "商品 · 南华工业品指数",
    }.get(asset, "未知核心资产")


def _stage_label(value: object) -> str:
    return stage_title(value)


def _last_confirmed_label(stage: object, lookback: object) -> str:
    """The last confirmed stage; one looked back for before the window says so (ADR-0040)."""
    if not isinstance(lookback, dict):
        return _stage_label(stage)
    if lookback.get("status") == "found":
        return f"{_stage_label(stage)}（回溯得出，最近一次在 {lookback.get('stage_date')}）"
    if lookback.get("status") == "not_found":
        reach = f"{lookback.get('searched_from')}～{lookback.get('searched_through')}"
        return f"尚无（已回溯 {lookback.get('years')} 年，{reach} 无正式阶段）"
    return f"尚无（回溯失败：{lookback.get('failure') or '未记录原因'}）"


def _report_last_confirmed(body: dict[str, Any]) -> list[html.Div]:
    results = body.get("verified_results")
    stage = results.get("formal_stage") if isinstance(results, dict) else None
    if not isinstance(stage, dict):
        return []
    return [
        _compact_fact(
            "上一确认阶段",
            _last_confirmed_label(
                stage.get("last_confirmed_stage"), stage.get("last_confirmed_lookback")
            ),
        )
    ]


def _stage_explanation(overview: dict[str, object]) -> str:
    if overview.get("current_stage") is not None:
        return "三类核心资产已形成规范组合；正式阶段由 120 日稳定状态机械映射确认。"
    reason = overview.get("stage_reason") or overview.get("stage_unavailable_reason")
    return {
        "noncanonical_combination": "当前三资产组合不属于六个规范阶段，系统保持空值。",
        "core_state_unavailable": "至少一类核心资产状态不可用，系统不会以宏观证据补票。",
        "p0_unavailable": "P0 核心证据未通过门禁，上一确认阶段仅作历史上下文。",
        "core_data_pending": (
            "核心数据待处理：三核心落后两期以上或来源冲突，本日不产出正式阶段；"
            "宏观、库存、缺口与报告照常发布。"
        ),
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
        **_QUADRANT_LABELS,
        "queued": "排队",
        "main": "主要成员",
        "primary": "主要成员",
        "auxiliary": "辅助成员",
        "preflight": "运行前检查",
        "refreshing_evidence": "获取证据",
        "validating_evidence": "校验证据",
        "evaluating_core_readiness": "检查三核心",
        "deriving_states": "识别状态",
        "building_projection": "构建分析投影",
        "publishing_projection": "发布投影与历史",
        "generating_report": "生成报告",
        "completed": "已完成",
        "running": "运行中",
        "failed": "失败",
        "cancelled": "已取消",
        "action_required": "需要处理",
        "interrupted": "已中断",
        "none": "无需操作",
        "resume_required": "确认后恢复",
        "refresh_p0_or_create_gap_notice": "补齐三核心或记录缺口说明",
        "wait_for_release_or_cache_expiry": "等待发布或缓存到期",
        **CORE_STATE_LABELS,
        "support": "支持",
        "supports": "支持",
        "conflict": "矛盾",
        "conflicted": "矛盾",
        "insufficient_data": "数据不足",
        "unclassified": "尚无法分类",
        "unknown": "未知",
        "missing": "缺失",
        "daily": "日频",
        "monthly": "月频",
        "quarterly": "季频",
        "bond_price": "债券价格观察",
        "stale_inputs": "输入数据已陈旧",
        "upstream_pressure": "上游压力",
        "producer_diffusion": "向生产端扩散",
        "consumer_diffusion": "向消费端扩散",
        "easing": "宽松",
        "tightening": "收紧",
        "neutral": "中性",
        "transmission_conflict": "传导冲突",
        "warming": "升温",
        "overheating": "过热",
        "cooling": "降温",
        "current": "当前有效",
        "stale": "陈旧",
        "awaiting_source_certification": "等待来源认证",
        "awaiting_release": "等待发布",
        "source_failed": "来源失败",
        "missing_credentials": "当前渠道未配置接入凭据",
        "adapter_failed": "适配器失败",
        "validation_failed": "数据校验失败",
        "verified_candidate": "已取得候选数据",
        "partial_validation": "部分字段未通过校验",
        "missing_fields": "请求已完成，缺少所需字段",
        "missing_values": "请求已完成，目标窗口无数值",
        "succeeded": "已取得",
        "complete": "已完整取得",
        "partial_members_missing": "已取得，部分成员缺失",
        "nothing_new": "已全部持有，无需新增",
        "source_empty": "来源空交付",
        "structure_rejected": "结构校验拒收",
        "ingest_rejected": "入库契约拒收",
        "local_failed": "本地处理失败",
        "not_attempted": "未发出请求",
        "tushare_daily_quota_exhausted": "当日配额用尽",
        "tushare_daily_quota_refused": "当日配额被来源拒绝，本轮停用该接口",
        "period_mismatch": "输入报告期不一致",
        "no_attempt_for_target": "未记录此目标日与定义的获取结果",
        "derived_from_inputs": "由输入证据计算",
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


def _display_value(value: object, *, unit: object = None) -> str:
    if unit == "basis_points" and isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.2f}"
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
        "corrections": projection.corrections,
        "run_count": len(runs),
        "report_count": len(reports),
    }
