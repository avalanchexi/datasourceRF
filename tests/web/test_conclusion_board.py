"""The 01 conclusion board's left column: its title and five labelled rows (ticket 03).

Everything is read from a published projection and the frozen model's trend rules, so
each case builds a small projection by hand and asserts the reader-visible sentence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dash.development.base_component import Component

from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain.trend import TrendRules
from pring_cycle.projections import ProjectionEnvelope, ProjectionSet
from tests.web.test_dashboard_contract import _text

METRICS = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}


def _asset(asset: str, state: str | None, **fields: Any) -> dict[str, Any]:
    return {
        "asset": asset,
        "metric_id": METRICS[asset],
        "state": state,
        "reason": "validated" if state else "source_missing",
        "carried_forward": False,
        "candidate_30d": state,
        "candidate_state": None,
        "candidate_days": 0,
        "persistence_required": 8,
        "latest_business_date": "2026-09-30",
        **fields,
    }


def _projection(
    assets: list[dict[str, Any]],
    *,
    model_version_id: str = "model-v0015",
    macro: dict[str, Any] | None = None,
    **overview: Any,
) -> ProjectionSet:
    moment = datetime(2026, 9, 30, 13, tzinfo=UTC)
    return ProjectionSet(
        ProjectionEnvelope(
            projection_set_id="projection-board",
            system_as_of=moment,
            target_business_date="2026-09-30",
            evidence_snapshot_id="snapshot-board",
            model_version_id=model_version_id,
            trend_rule_version="trend-v0001",
            evidence_window_start="2026-04-09",
            evidence_window_end="2026-09-30",
            generated_at=moment,
            completeness="complete",
            refresh_status="completed",
            warnings=(),
        ),
        {
            "cycle_overview": {
                "current_stage": None,
                "last_confirmed_stage": None,
                "transition_watch": [],
                "core_carry_forward": [],
                "gap_list": [],
                **overview,
            },
            "core_assets": {"assets": assets},
            "macro": macro or {},
            "inventory": {},
            "release_calendar": {},
            "stage_history": {},
        },
    )


def _conclusion(projection: ProjectionSet | None, trend_rules: TrendRules | None = None) -> object:
    page = dashboard_page("/", projection, (), (), trend_rules=trend_rules)

    def section(component: object) -> object:
        if isinstance(component, Component):
            if getattr(component, "id", None) == "conclusion":
                return component
            children = getattr(component, "children", None)
            for child in children if isinstance(children, (list, tuple)) else [children]:
                found = section(child)
                if found is not None:
                    return found
        return None

    return section(page)


def _board(projection: ProjectionSet | None, trend_rules: TrendRules | None = None) -> str:
    return " ".join(_text(_conclusion(projection, trend_rules)).split())


def test_a_typical_combination_names_the_three_states_and_the_stage_they_map_to() -> None:
    board = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bull"), _asset("commodity", "bear")],
            current_stage="stage_ii",
            last_confirmed_stage="stage_ii",
            stage_reason="canonical_combination",
        )
    )

    assert "第二阶段 · Stage II" in board
    assert "原因 典型组合：债券牛市 · 股票牛市 · 商品熊市 → Stage II" in board


def test_a_noncanonical_combination_is_named_and_creates_no_extra_stage() -> None:
    board = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
            stage_reason="noncanonical_combination",
        )
    )

    assert "暂无正式阶段" in board
    assert (
        "原因 非典型组合：债券牛市 · 股票熊市 · 商品牛市，不在六个典型组合内；不创建 Stage VII/VIII"
    ) in board


def test_core_data_pending_lists_each_core_with_the_blockage_its_gap_records() -> None:
    gaps = [
        {
            "metric_id": METRICS["commodity"],
            "priority": "P0",
            "category": "missing",
            "reason": "two_or_more_periods_behind",
            "due_period": "2026-09-30",
            "held_period": "2026-09-25",
            "periods_behind": 3,
        },
        {
            "metric_id": METRICS["stock"],
            "priority": "P0",
            "category": "freshness_gap",
            "reason": "one_period_behind_carried",
            "due_period": "2026-09-30",
            "held_period": "2026-09-29",
            "periods_behind": 1,
        },
    ]
    board = _board(
        _projection(
            [
                _asset("bond", "bull"),
                _asset(
                    "stock",
                    "bear",
                    reason="carried_forward_one_session",
                    carried_forward=True,
                    latest_business_date="2026-09-29",
                ),
                _asset("commodity", None, reason="stale_for_target_business_date"),
            ],
            stage_reason="core_data_pending",
            core_carry_forward=["stock"],
            gap_list=gaps,
        )
    )

    assert (
        "原因 核心数据待处理：债券牛市 · 股票熊市（核心沿用，沿用期 2026-09-29） · "
        "商品受阻：落后 3 期，沿用期 2026-09-25"
    ) in board


def test_a_blocked_core_without_a_gap_entry_states_only_its_published_reason() -> None:
    for reason, label in (
        ("core_state_unavailable", "核心状态不可用"),
        ("p0_unavailable", "P0 未过门禁"),
    ):
        board = _board(
            _projection(
                [
                    _asset("bond", "bull"),
                    _asset("stock", "bear"),
                    _asset(
                        "commodity",
                        None,
                        reason="window_session_missing",
                        latest_business_date="2026-09-26",
                    ),
                ],
                stage_reason=reason,
            )
        )

        assert (
            f"原因 {label}：债券牛市 · 股票熊市 · 商品受阻：窗口缺少实际交易日观测，最新 2026-09-26"
        ) in board
        assert "落后" not in board


def test_an_unknown_reason_keeps_the_waiting_sentence() -> None:
    board = _board(_projection([], stage_reason="something_new"))

    assert "原因 等待三类 P0 核心资产形成同一截止点的可用组合。" in board


def test_transition_watch_says_none_only_when_every_30_day_candidate_agrees() -> None:
    agreed = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
            stage_reason="noncanonical_combination",
        )
    )
    turning = _board(
        _projection(
            [
                _asset("bond", "bull"),
                _asset(
                    "stock",
                    "bear",
                    candidate_30d="bull",
                    candidate_state="bull",
                    candidate_days=3,
                ),
                _asset("commodity", "bull", candidate_30d=None),
            ],
            stage_reason="noncanonical_combination",
        )
    )

    assert "转折观察 无（三核心 30 日候选均与当前状态同向）" in agreed
    assert (
        "转折观察 股票 30 日候选方向牛市，与当前熊市相反；资产候选状态牛市 · 持续 3 日 / 门槛 8 日"
        "；商品 30 日候选方向无 · 只作观察，不改变正式阶段"
    ) in turning
    assert "同向" not in turning


def test_last_confirmed_keeps_its_lookback_note_and_carry_forward_names_the_held_core() -> None:
    carried = _board(
        _projection(
            [
                _asset("bond", "bull"),
                _asset("stock", "bull"),
                _asset(
                    "commodity",
                    "bull",
                    reason="carried_forward_one_session",
                    carried_forward=True,
                    latest_business_date="2026-09-29",
                ),
            ],
            current_stage="stage_iii",
            last_confirmed_stage="stage_iii",
            last_confirmed_lookback={"status": "found", "stage_date": "2026-03-31"},
            stage_reason="canonical_combination",
            core_carry_forward=["commodity"],
        )
    )
    plain = _board(
        _projection(
            [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
            stage_reason="noncanonical_combination",
        )
    )

    assert "上次确认 第三阶段 · Stage III（回溯得出，最近一次在 2026-03-31）" in carried
    assert "核心沿用 商品（沿用期 2026-09-29）" in carried
    assert "上次确认 无" in plain
    assert "核心沿用 无" in plain
    for board in (carried, plain):
        rows = ["原因", "上次确认", "转折观察", "核心沿用"]
        assert [board.index(f" {row} ") for row in rows] == sorted(
            board.index(f" {row} ") for row in rows
        )


def test_the_method_row_reads_the_frozen_trend_rules_and_never_defaults_them() -> None:
    projection = _projection(
        [_asset("bond", "bull"), _asset("stock", "bear"), _asset("commodity", "bull")],
        stage_reason="noncanonical_combination",
    )
    certified = _board(
        projection,
        TrendRules(
            window_days=120,
            slope_days=20,
            volatility_days=20,
            noise_multiplier=1.5,
            persistence_days=8,
            candidate_window_days=30,
        ),
    )
    other = _board(
        projection,
        TrendRules(
            window_days=60,
            slope_days=10,
            volatility_days=40,
            noise_multiplier=2.0,
            persistence_days=5,
            candidate_window_days=15,
        ),
    )
    missing = _board(projection)

    assert (
        "判法 MA120 + 20 日斜率定稳定牛熊，噪声带 1.5×20 日波动，持续 8 日确认，"
        "30 日候选只作转折观察；宏观与库存只做事后确认，不改写阶段 · model-v0015"
    ) in certified
    assert (
        "判法 MA60 + 10 日斜率定稳定牛熊，噪声带 2×40 日波动，持续 5 日确认，"
        "15 日候选只作转折观察；宏观与库存只做事后确认，不改写阶段 · model-v0015"
    ) in other
    assert "判法 该模型版本未提供趋势规则参数 · model-v0015" in missing
    assert "日斜率定稳定牛熊" not in missing
    assert certified.index(" 核心沿用 ") < certified.index(" 判法 ")


def test_an_empty_runtime_board_stays_readable_without_a_stage_or_rules() -> None:
    board = _board(None)

    assert "暂无正式阶段" in board
    assert "原因 等待三类 P0 核心资产形成同一截止点的可用组合。" in board
    assert "上次确认 无" in board
    assert "核心沿用 无" in board
    assert "判法 等待首次完整运行" in board


def test_the_conclusion_heading_says_what_the_board_holds() -> None:
    board = _board(None)

    assert board.startswith(
        "01 周期识别结论 正式阶段 · 三核心 · 确认度 · 一致性 · 库存 · 归因，一板看完"
    )


def test_the_board_stacks_its_columns_on_narrow_windows_without_widening_the_page() -> None:
    stylesheet = (
        Path(__file__).parents[2] / "src" / "pring_cycle" / "assets" / "report.css"
    ).read_text(encoding="utf-8")
    narrow = stylesheet[stylesheet.index("@media (max-width: 1000px)") :]
    narrow = narrow[: narrow.index("\n}")]

    assert ".conclusion-board { grid-template-columns: minmax(0,1fr); }" in narrow
    assert ".conclusion-board > div { min-width: 0; }" in stylesheet
    assert "overflow-wrap: anywhere" in stylesheet[stylesheet.index(".board-rows dd") :]
