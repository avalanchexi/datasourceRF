from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dash import dcc, html

from pring_cycle.navigation import DASHBOARD_NAVIGATION
from pring_cycle.projections import ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.runs import RunRecord


def dashboard_shell(
    projection: ProjectionSet | None,
    runs: Sequence[RunRecord],
    reports: Sequence[ReportSnapshot],
    *,
    source_contract_notice: str | None = None,
) -> html.Div:
    envelope = projection.envelope if projection is not None else None
    system_as_of = envelope.system_as_of.isoformat() if envelope is not None else "尚无投影"
    projection_id = envelope.projection_set_id if envelope is not None else "等待首次完整运行"
    completeness = envelope.completeness if envelope is not None else "不可用"
    drawer_document = _projection_detail(projection, runs, reports)
    return html.Div(
        [
            dcc.Location(id="dashboard-location", refresh=False),
            dcc.Interval(
                id="runtime-poll",
                interval=_poll_interval_ms(runs),
                n_intervals=0,
            ),
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
            html.Aside(source_contract_notice, className="source-contract-notice", role="alert")
            if source_contract_notice is not None
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
        return _reports_page(reports, runs)
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
                    _macro_summary(macro),
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
    as_of = projection.envelope.system_as_of.isoformat() if projection is not None else None
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
    if international:
        if item.get("acquisition_status") is not None:
            details.append(f"最近获取 {_state_label(item['acquisition_status'])}")
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
                            f"证据包 {item.bundle_hash}",
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
                                "生成命令冻结当前证据包；AI 失败不会回滚分析投影。",
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
            _page_heading("运行状态", "PERSISTENT RUN LEDGER"),
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


def _report_reader(report: ReportSnapshot) -> html.Div:
    identity = html.Dl(
        [
            _compact_fact("报告身份", report.report_snapshot_id),
            _compact_fact("投影身份", report.projection_set_id),
            _compact_fact("正式阶段", _stage_label(report.current_stage)),
            _compact_fact("截止点", report.report_cutoff.isoformat()),
            _compact_fact("确定性输出", "已生成"),
            _compact_fact("AI解释", "不可用" if report.adapter == "deterministic" else "已生成"),
            _compact_fact(
                "解释证据核查",
                {
                    "passed": "已核查支持与反证",
                    "needs_attention": "存在无支持或矛盾叙述",
                    "pending_evidence_review": "结构与引用已校验，语义待核查",
                    "unavailable": "无AI解释",
                }.get(str(report.explanation_verification.get("status")), "未记录核查"),
            ),
        ],
        className="compact-facts",
    )
    if not report.body_retained:
        return html.Div(
            [identity, _empty_state("正文已不在保留期", "结构化身份与证据包清单仍长期保留。")],
            className="report-reader",
        )
    body = report.body
    sections = body.get("ai_explanation")
    if isinstance(sections, list):
        content = [
            html.Section(
                [
                    html.H3(str(section.get("title") or "未命名章节")),
                    html.P(str(section.get("explanation") or ""), className="body-copy"),
                    html.P(
                        "证据 " + "、".join(str(item) for item in section.get("evidence_ids", [])),
                        className="secondary-copy",
                    ),
                    html.P(
                        "治理引用 "
                        + "、".join(str(item) for item in section.get("governance_refs", [])),
                        className="secondary-copy",
                    ),
                ],
                className="report-section",
            )
            for section in sections
            if isinstance(section, dict)
        ]
    else:
        content = [
            _report_fact_section("三核心", body.get("core_states")),
            _report_fact_section("转折观察", body.get("transition_watch")),
            _report_fact_section("宏观事后确认", body.get("macro_confirmation")),
            _report_fact_section("政策与信用", body.get("policy_context")),
            _report_fact_section("库存解释", body.get("inventory_context")),
            _report_fact_section("物价传导", body.get("price_context")),
            _report_fact_section("变化原因", body.get("change_reasons")),
            _report_fact_section("支持证据", body.get("support")),
            _report_fact_section("反证", body.get("counterevidence")),
            _report_fact_section("数据缺口", body.get("governance_gaps")),
            _report_fact_section("绑定引用", body.get("evidence_references")),
        ]
    return html.Div([identity, *content], className="report-reader")


def _report_fact_section(title: str, value: object) -> html.Section:
    return html.Section(
        [html.H3(title), html.P(_display_value(value), className="body-copy")],
        className="report-section",
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
    actions: list[html.Button] = []
    if item.status in {"interrupted", "action_required"} and item.recoverable:
        actions.append(
            html.Button(
                "确认并继续",
                className="quiet-button run-action",
                type="button",
                **cast(Any, {"data-run-action": "resume", "data-run-id": item.run_id}),
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
            html.Strong(f"{item.target_business_date} · {item.status}"),
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
        "run_count": len(runs),
        "report_count": len(reports),
    }
