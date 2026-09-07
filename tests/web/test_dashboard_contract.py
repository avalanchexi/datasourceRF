from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dash.development.base_component import Component

from pring_cycle.dashboard import (
    DASHBOARD_NAVIGATION,
    _poll_interval_ms,
    dashboard_page,
    dashboard_shell,
)
from pring_cycle.projections import ProjectionEnvelope, ProjectionSet
from pring_cycle.reports import ReportSnapshot
from pring_cycle.runs import RunRepository


def _text(component: object) -> str:
    if isinstance(component, str):
        return component
    if isinstance(component, Component):
        children = getattr(component, "children", None)
        if isinstance(children, (list, tuple)):
            return " ".join(_text(child) for child in children)
        return _text(children)
    return ""


def _hrefs(component: object) -> list[str]:
    if isinstance(component, (list, tuple)):
        return [href for child in component for href in _hrefs(child)]
    if not isinstance(component, Component):
        return []
    href = getattr(component, "href", None)
    return ([href] if isinstance(href, str) else []) + _hrefs(getattr(component, "children", None))


def test_navigation_and_home_hierarchy_match_the_confirmed_eight_page_contract() -> None:
    assert tuple(label for _path, label in DASHBOARD_NAVIGATION) == (
        "首页",
        "核心资产",
        "宏观证据",
        "库存特征",
        "阶段历史",
        "发布日历",
        "报告",
        "运行状态",
    )
    assert "证据追溯" not in tuple(label for _path, label in DASHBOARD_NAVIGATION)

    home = _text(dashboard_page("/", None, (), ()))

    assert home.index("正式阶段") < home.index("转折观察") < home.index("宏观事后确认")
    assert "当前阶段暂不判定" in home
    assert "不改变正式阶段" in home


def test_report_workspace_has_generation_history_and_reading_areas() -> None:
    report = _text(dashboard_page("/reports", None, (), ()))

    assert all(label in report for label in ("生成", "历史", "阅读"))


def test_report_workspace_renders_immutable_metadata_and_selected_body() -> None:
    cutoff = datetime(2026, 8, 28, 13, tzinfo=UTC)
    snapshot = ReportSnapshot(
        report_snapshot_id="report-fixture",
        projection_set_id="projection-fixture",
        target_business_date="2026-08-28",
        version=2,
        status="completed",
        adapter="codex_cli",
        current_stage="stage_ii",
        bundle_id="bundle-fixture",
        bundle_hash="abc123",
        model_version_id="model-v0001",
        schema_version="report-schema-v0001",
        prompt_version="report-prompt-v0001",
        report_cutoff=cutoff,
        system_as_of=cutoff,
        created_at=cutoff,
        duration_ms=1250,
        body_retained=True,
        body={
            "ai_explanation": [
                {
                    "title": "政策传导",
                    "explanation": "政策证据只解释，不改变正式阶段。",
                    "evidence_ids": ["observation-policy"],
                    "governance_refs": ["ADR-0003"],
                }
            ]
        },
    )

    report = _text(dashboard_page("/reports", None, (), (snapshot,)))

    assert "截止 2026-08-28T13:00:00+00:00" in report
    assert "耗时 1250ms" in report
    assert "证据包 abc123" in report
    assert "报告身份 report-fixture" in report
    assert "政策证据只解释，不改变正式阶段。" in report
    assert "证据 observation-policy" in report


def test_dashboard_shell_exposes_projection_identity_and_evidence_drawer() -> None:
    shell = _text(dashboard_shell(None, (), ()))

    assert "SYSTEM AS OF" in shell
    assert "投影身份" in shell
    assert "完整度" in shell
    assert "投影详情与证据追溯" in shell


def test_visual_contract_covers_theme_state_type_focus_motion_and_narrow_windows() -> None:
    stylesheet = (
        Path(__file__).parents[2] / "src" / "pring_cycle" / "assets" / "dashboard.css"
    ).read_text(encoding="utf-8")
    script = (
        Path(__file__).parents[2] / "src" / "pring_cycle" / "assets" / "dashboard.js"
    ).read_text(encoding="utf-8")

    assert ':root[data-theme="light"]' in stylesheet
    assert ':root[data-theme="dark"]' in stylesheet
    assert "--state-up" in stylesheet and "--state-down" in stylesheet
    assert "--state-warning" in stylesheet and "--asset-" in stylesheet
    assert all(size in stylesheet for size in ("12px", "13px", "14px", "16px"))
    assert ":focus-visible" in stylesheet
    assert "prefers-reduced-motion" in stylesheet
    assert "@media (max-width:" in stylesheet
    assert "localStorage" in script and "pring-cycle-theme" in script
    assert 'aria-current", "page"' in script
    assert '.nav-link[aria-current="page"]' in stylesheet
    assert ".asset-card .section-title { overflow-wrap: anywhere; }" in stylesheet


def test_published_core_states_render_as_domain_ui_instead_of_raw_json() -> None:
    projection = ProjectionSet(
        ProjectionEnvelope(
            projection_set_id="projection-test",
            system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
            target_business_date="2026-08-28",
            evidence_snapshot_id="snapshot-test",
            model_version_id="model-v0001",
            trend_rule_version="trend-v0001",
            evidence_window_start="2026-03-01",
            evidence_window_end="2026-08-28",
            generated_at=datetime(2026, 8, 28, 13, tzinfo=UTC),
            completeness="complete",
            refresh_status="completed",
            warnings=(),
        ),
        {
            "cycle_overview": {
                "current_stage": "stage_ii",
                "last_confirmed_stage": "stage_ii",
                "stage_reason": "canonical_mapping",
                "transition_watch": [],
            },
            "core_assets": {
                "assets": [
                    {
                        "asset": "bond",
                        "metric_id": "CN_BOND_CORE_000012",
                        "state": "bull",
                        "reason": "validated",
                        "candidate_days": 8,
                        "candidate_state": "bear",
                        "latest_business_date": "2026-08-28",
                    }
                ]
            },
            "macro": {},
            "inventory": {},
            "release_calendar": {},
            "stage_history": {},
        },
    )

    home = _text(dashboard_page("/", projection, (), ()))
    detail = _text(dashboard_page("/core-assets", projection, (), ()))

    assert "第二阶段 · Stage II" in home
    assert "上证国债指数" in home
    assert "偏多 · bull" in home
    assert "2026-08-28" in home
    assert "等待三类 P0" not in home
    assert "120 日正式轨道" in detail
    assert "30 日转折观察" in detail
    assert '"asset": "bond"' not in detail


def test_home_summarizes_macro_states_without_dumping_nested_evidence_json() -> None:
    projection = ProjectionSet(
        ProjectionEnvelope(
            projection_set_id="projection-summary",
            system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
            target_business_date="2026-08-28",
            evidence_snapshot_id="snapshot-summary",
            model_version_id="model-v0001",
            trend_rule_version="trend-v0001",
            evidence_window_start="2026-03-09",
            evidence_window_end="2026-08-28",
            generated_at=datetime(2026, 8, 28, 13, tzinfo=UTC),
            completeness="degraded",
            refresh_status="completed",
            warnings=("p1_evidence_incomplete:0/42",),
        ),
        {
            "cycle_overview": {"current_stage": None, "stage_reason": "noncanonical_combination"},
            "core_assets": {"assets": []},
            "macro": {
                "policy_direction": "insufficient_data",
                "credit_response": "insufficient_data",
                "overheat_state": "insufficient_data",
                "price_pressure": "upstream_pressure",
                "credit": {
                    "evidence": [
                        {
                            "metric_id": "CN_M1_M2",
                            "observation_id": "must-not-appear-on-home",
                        }
                    ]
                },
            },
            "inventory": {},
            "release_calendar": {},
            "stage_history": {},
        },
    )

    home = _text(dashboard_page("/", projection, (), ()))

    assert all(label in home for label in ("政策方向", "信用响应", "过热程度", "物价压力"))
    assert "数据不足" in home and "上游压力" in home
    assert "CN_M1_M2" not in home
    assert "must-not-appear-on-home" not in home


def test_domain_pages_expose_fixed_sections_instead_of_generic_documents() -> None:
    macro = _text(dashboard_page("/macro", None, (), ()))
    inventory = _text(dashboard_page("/inventory", None, (), ()))
    history = _text(dashboard_page("/stage-history", None, (), ()))
    calendar = _text(dashboard_page("/release-calendar", None, (), ()))

    assert all(label in macro for label in ("政策方向", "过热程度", "物价压力", "国际环境"))
    assert "四象限解释" in inventory and "七张阶段特征卡" in inventory
    assert "正式区间与空档" in history
    assert all(label in calendar for label in ("预计窗口", "实际发布", "系统首次可用"))


def test_macro_and_inventory_pages_render_evidence_fields_and_semantic_boundaries() -> None:
    envelope = ProjectionEnvelope(
        projection_set_id="projection-context",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
        target_business_date="2026-08-28",
        evidence_snapshot_id="snapshot-context",
        model_version_id="model-v0001",
        trend_rule_version="trend-v0001",
        evidence_window_start="2026-03-01",
        evidence_window_end="2026-08-28",
        generated_at=datetime(2026, 8, 28, 13, tzinfo=UTC),
        completeness="degraded",
        refresh_status="completed",
        warnings=("p1_evidence_incomplete",),
    )
    evidence = {
        "metric_id": "CN_LPR_1Y_5Y",
        "observation_id": "observation-lpr-1y",
        "direction": "easing",
        "period": "2026-08-31",
        "status": "current",
        "value": 3.0,
        "unit": "percent",
        "certification_status": "certified",
        "source_reference": "https://www.chinamoney.com.cn/example#sha256=test",
        "claims": [
            {
                "provider": "中国货币网",
                "value": 3.0,
                "unit": "percent",
                "selected": True,
            }
        ],
    }
    projection = ProjectionSet(
        envelope,
        {
            "cycle_overview": {},
            "core_assets": {},
            "macro": {
                "policy_direction": "easing",
                "policy_action": {"direction": "easing", "evidence": [evidence]},
                "transmission": {"direction": "easing", "evidence": []},
                "credit_response": "insufficient_data",
                "credit": {"state": "insufficient_data", "evidence": [evidence]},
                "overheat_state": "insufficient_data",
                "overheat": {"support": [], "counterevidence": [], "gaps": []},
                "price_pressure": "upstream_pressure",
                "price_chain": {"support": [], "counterevidence": [], "gaps": []},
                "international_context": [
                    {
                        "metric_id": "UST10Y_NOMINAL_YIELD",
                        "name_cn": "美国10年期国债名义收益率",
                        "status": "awaiting_source_certification",
                        "direction": "unknown",
                        "period": None,
                        "certification_status": "awaiting_source_certification",
                        "acquisition_status": "missing_credentials",
                    },
                    {
                        "metric_id": "UST_2S10S_SPREAD",
                        "value": 39.00000000000006,
                        "unit": "basis_points",
                        "acquisition_status": "derived_from_inputs",
                    },
                ],
            },
            "inventory": {
                "quadrant": None,
                "directions": {
                    "demand": "up",
                    "production": "conflict",
                    "inventory": None,
                },
                "cards": [
                    {
                        "name": "materials_finished_goods",
                        "status": "stale",
                        "evidence_ids": ["observation-pmi-inventory"],
                    }
                ],
                "real_inventory_approximation": {
                    "status": "missing_certified_inputs",
                    "formula_version": "inventory-ppi-v0001",
                },
                "semantics": {
                    "pmi_inventory": "diffusion_index_not_inventory_quantity",
                    "futures_warrants": "registered_receipts_not_total_industrial_inventory",
                },
            },
            "release_calendar": {},
            "stage_history": {},
        },
    )

    macro = _text(dashboard_page("/macro", projection, (), ()))
    inventory = _text(dashboard_page("/inventory", projection, (), ()))

    assert "政策行动" in macro and "市场传导" in macro and "信用响应" in macro
    assert "CN_LPR_1Y_5Y" in macro
    assert "统计期 2026-08-31" in macro
    assert "认证 certified" in macro
    assert "收益率方向，不是债券价格" in macro
    assert "值 39.00 basis_points" in macro
    assert "39.00000000000006" not in macro
    assert "最近获取 由输入证据计算" in macro
    assert "证据 observation-lpr-1y" in macro
    assert "来源声明 中国货币网=3.0 percent（已选）" in macro
    assert "需求 up · 生产 矛盾 · 库存 数据不足" in inventory
    assert "PMI 库存是扩散指数，不是库存数量" in inventory
    assert "注册仓单不代表产业总库存" in inventory
    assert "证据 observation-pmi-inventory" in inventory
    for route in ("/macro", "/inventory"):
        links = [
            href
            for href in _hrefs(dashboard_page(route, projection, (), ()))
            if href.startswith("/api/v1/evidence/")
        ]
        assert links
        for href in links:
            query = parse_qs(urlsplit(href).query)
            assert query["mode"] == ["system_as_of"]
            assert datetime.fromisoformat(query["as_of"][0]) == envelope.system_as_of


def test_stage_history_page_can_show_an_unpublished_p0_gap_from_the_read_model() -> None:
    gap = {
        "business_date": "2026-08-31",
        "current_stage": None,
        "last_confirmed_stage": "stage_ii",
        "event_kind": "gap",
        "stage_reason": "p0_unavailable",
        "gaps": ["commodity:source_conflict"],
        "model_version_id": "model-v0001",
    }

    history = _text(dashboard_page("/stage-history", None, (), (), (gap,)))

    assert "2026-08-31" in history
    assert "当前阶段暂不判定" in history
    assert "上一确认 第二阶段 · Stage II" in history
    assert "商品：来源冲突" in history


def test_release_calendar_page_shows_operational_event_fields() -> None:
    event = {
        "release_event_family": "chinamoney_lpr",
        "metric_id": "CN_LPR_1Y_5Y",
        "period": "2026-08",
        "timezone": "Asia/Shanghai",
        "status": "current",
        "carried_period": None,
        "expected_window_start": "2026-08-20T09:00:00+08:00",
        "release_at": "2026-08-20T09:00:00+08:00",
        "available_at": "2026-08-20T01:02:00+00:00",
        "latest_fetched_at": "2026-08-20T01:02:00+00:00",
        "next_check_at": None,
        "observation_count": 2,
    }

    calendar = _text(dashboard_page("/release-calendar", None, (), (), (), (event,)))

    assert "chinamoney_lpr" in calendar
    assert "2026-08" in calendar
    assert "Asia/Shanghai" in calendar
    assert "最近获取 2026-08-20T01:02:00+00:00" in calendar
    assert "关联观测 2" in calendar


def test_run_page_shows_retrieval_latency_budget_cache_and_next_action(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    submitted = runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id="dashboard-retrieval",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    )
    runs.record_retrieval_attempt(
        submitted.run_id,
        release_event_id="chinamoney-lpr:2026-08-20",
        channel="tavily",
        outcome="candidate_source",
        classification=None,
        latency_ms=123,
        remaining_run_budget=7,
        remaining_daily_budget=15,
        budget_charged=True,
        cache_hit=False,
        manual_budget_exemption=False,
        candidate_source="https://example.invalid/safe-url-only",
        occurred_at=datetime(2026, 8, 20, 2, tzinfo=UTC),
    )
    runs.set_budget_consumption(submitted.run_id, tavily=1, exa=0, ai_websearch=0)

    page = _text(dashboard_page("/runs", None, runs.list_runs(), ()))

    assert "tavily candidate_source 123ms" in page
    assert "运行余量 7 日余量 15" in page
    assert "预算 Tavily 1/8、Exa 0/4、AI 0/1" in page
    assert "下一动作 wait_for_worker" in page
    assert "safe-url-only" not in page


def test_run_page_exposes_safe_actions_and_adaptive_polling(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="dashboard-run-actions",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 28, 13, tzinfo=UTC),
    )

    queued = runs.list_runs()
    assert _poll_interval_ms(queued) == 30_000
    assert "取消后续步骤" in _text(dashboard_page("/runs", None, queued, ()))

    runs.mark_interrupted(submitted.run_id, "fixture_worker_lost")
    interrupted = runs.list_runs()
    assert _poll_interval_ms(interrupted) == 300_000
    assert "确认并继续" in _text(dashboard_page("/runs", None, interrupted, ()))
