from __future__ import annotations

from pathlib import Path

from dash.development.base_component import Component

from pring_cycle.dashboard import DASHBOARD_NAVIGATION, dashboard_page, dashboard_shell


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

