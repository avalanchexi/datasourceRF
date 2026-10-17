"""Section 07 in the reader's words: reason codes in Chinese, metrics by their Chinese names,
and no misleading notes (ticket 13).

Each case renders the home page from a small hand-built projection and asserts what a reader
sees in section 07.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from tests.web.test_board_footer import _reading as _ai_body
from tests.web.test_board_footer import _report
from tests.web.test_reading_section import (
    _gaps_projection,
    _panel,
    _reading,
    _trigger,
    _visible,
    _words,
)


def test_gap_reasons_and_metrics_read_in_chinese_and_an_unmapped_code_stays_as_recorded() -> None:
    gaps: list[dict[str, Any]] = [
        {
            "category": "missing",
            "priority": "P1",
            "metric_id": "CN_SF_TOTAL",
            "reason": "period_not_requested",
            "not_requested": [{"period": "2026-09", "reason": "awaiting_release"}],
            "no_web_fallback": False,
        },
        {
            "category": "retrieval_failed",
            "priority": "P2",
            "metric_id": "CN_USDCNY_CENTRAL_PARITY",
            "reason": "one_period_behind_carried",
            "due_period": "2026-10-15",
            "held_period": "2026-10-14",
            "candidates": [
                {"url": "https://www.cls.cn/detail/2505221", "reason": "rule_not_matched"},
                {"url": "https://finance.sina.com.cn/a.shtml", "reason": "period_mismatch"},
                {"url": "https://www.pbc.gov.cn/b.html", "reason": "negative_cache_active"},
            ],
        },
        {
            "category": "missing",
            "priority": "P2",
            "metric_id": "METRIC_NEW",
            "reason": "reason_added_later",
        },
    ]

    visible = _words(_visible(_reading(_gaps_projection(gaps))))

    assert "P1 社融存量（CN_SF_TOTAL）：未请求 2026-09（等待发布）" in visible
    assert (
        "P2 美元兑人民币中间价（CN_USDCNY_CENTRAL_PARITY）：落后一期，沿用上一期"
        "（应有期 2026-10-15，持有 2026-10-14）；"
        "候选 https://www.cls.cn/detail/2505221（解析规则未命中）；"
        "https://finance.sina.com.cn/a.shtml（统计期不符）；"
        "https://www.pbc.gov.cn/b.html（被负缓存拦下）"
    ) in visible
    assert "P2 METRIC_NEW：reason_added_later" in visible
    assert "period_not_requested" not in visible
    assert "one_period_behind_carried" not in visible


def test_a_metric_without_a_search_family_says_no_extra_web_search_is_configured() -> None:
    gaps: list[dict[str, Any]] = [
        {
            "category": "missing",
            "priority": "P2",
            "metric_id": "EIA_BRENT_RBRTE",
            "reason": "period_not_requested",
            "not_requested": [{"period": "2026-10-15", "reason": "awaiting_release"}],
            "no_web_fallback": True,
        }
    ]

    visible = _words(_visible(_reading(_gaps_projection(gaps))))

    assert (
        "P2 Brent 原油（EIA_BRENT_RBRTE）：未请求 2026-10-15（等待发布）；未配置额外网页检索补缺"
    ) in visible
    assert "无网页补缺渠道" not in visible


def test_a_projection_without_coverage_says_it_predates_the_statistic() -> None:
    visible = _words(_visible(_reading(_gaps_projection([]))))

    assert "两种完整度口径：该投影生成时尚未提供此统计。" in visible
    assert "该版本未提供" not in visible


def test_the_target_day_and_the_timeliness_cutoff_are_explained_side_by_side() -> None:
    visible = _words(_visible(_reading(_gaps_projection([]))))

    assert (
        "目标日 2026-09-30；时效截至 2026-09-30 21:00（北京）。"
        "目标日决定分析日期，时效按运行冻结时点判断。"
    ) in visible


def test_a_noncanonical_ai_reading_is_stated_as_no_formal_stage_not_as_a_gap() -> None:
    projection = _gaps_projection([])
    body = {
        **_ai_body("该组合属于非标准组合，正式阶段为空，阶段变化记为缺口。"),
        "verified_results": {
            "formal_stage": {
                "value": None,
                "change": "gap",
                "reason": "noncanonical_combination",
                "last_confirmed_stage": "stage_iii",
            }
        },
    }

    section = _reading(
        projection, reports=(_report(projection.envelope.projection_set_id, body=body),)
    )
    visible = _words(_visible(section))

    assert "阶段变化：非典型组合，暂无正式阶段" in visible
    panel = _panel(section, _trigger(section, "查看报告详情"))
    assert "阶段变化 非典型组合，暂无正式阶段" in panel


def test_a_noncanonical_template_reading_is_stated_as_no_formal_stage() -> None:
    projection = _gaps_projection([])
    body = {
        "ai_explanation": [{"title": "非典型组合", "explanation": "模板事实句。"}],
        "explanation_source": "deterministic_template",
        "verified_results": {
            "formal_stage": {"value": None, "change": "gap", "reason": "noncanonical_combination"}
        },
    }

    section = _reading(
        projection,
        reports=(
            _report(projection.envelope.projection_set_id, adapter="deterministic", body=body),
        ),
    )

    assert "阶段变化：非典型组合，暂无正式阶段" in _words(_visible(section))


def test_a_canonical_ai_reading_adds_no_stage_change_note() -> None:
    projection = _gaps_projection([])
    body = {
        **_ai_body("三核心为典型组合。"),
        "verified_results": {"formal_stage": {"value": "stage_iii", "change": "formal"}},
    }

    section = _reading(
        projection, reports=(_report(projection.envelope.projection_set_id, body=body),)
    )

    assert "非典型组合，暂无正式阶段" not in _words(_visible(section))


def test_the_release_calendar_drawer_states_an_event_status_in_chinese() -> None:
    projection = _gaps_projection([])
    projection = replace(
        projection,
        datasets={
            **projection.datasets,
            "release_calendar": {
                "events": [
                    {
                        "release_event_family": "chinamoney_lpr",
                        "period": "2026-10",
                        "status": "awaiting_release",
                    }
                ]
            },
        },
    )

    section = _reading(projection)
    panel = _panel(section, _trigger(section, "发布日历"))

    assert "状态 等待发布" in panel and "awaiting_release" not in panel
