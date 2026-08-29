from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from dash.development.base_component import Component

from pring_cycle.dashboard import DASHBOARD_NAVIGATION, dashboard_page, dashboard_shell
from pring_cycle.projections import ProjectionEnvelope, ProjectionSet
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


def test_domain_pages_expose_fixed_sections_instead_of_generic_documents() -> None:
    macro = _text(dashboard_page("/macro", None, (), ()))
    inventory = _text(dashboard_page("/inventory", None, (), ()))
    history = _text(dashboard_page("/stage-history", None, (), ()))
    calendar = _text(dashboard_page("/release-calendar", None, (), ()))

    assert all(label in macro for label in ("政策方向", "过热程度", "物价压力", "国际环境"))
    assert "四象限解释" in inventory and "七张阶段特征卡" in inventory
    assert "正式区间与空档" in history
    assert all(label in calendar for label in ("预计窗口", "实际发布", "系统首次可用"))


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
