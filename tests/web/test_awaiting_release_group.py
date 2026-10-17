"""Section 07 lists the periods awaiting release in a group of their own (worker gaps 03).

A batch-released metric whose next release has not come is not missing: its group says
when the release is out and where that date comes from, and the board's gap count leaves it
out. Each case renders the home page from a small hand-built projection.
"""

from __future__ import annotations

from typing import Any

from pring_cycle.dashboard import dashboard_page
from tests.web.test_dashboard_contract import _text
from tests.web.test_overseas_cards import _by_id
from tests.web.test_reading_section import _gaps_projection, _visible, _words

AWAITING: list[dict[str, Any]] = [
    {
        "category": "awaiting_release",
        "priority": "P2",
        "metric_id": "EIA_BRENT_RBRTE",
        "reason": "awaiting_release",
        "awaiting_release": [
            {
                "period": "2026-10-15",
                "next_release_date": "2026-10-21",
                "basis": "source_next_release_date",
            }
        ],
    },
    {
        "category": "awaiting_release",
        "priority": "P2",
        "metric_id": "EIA_WTI_RWTC",
        "reason": "awaiting_release",
        "awaiting_release": [
            {
                "period": "2026-10-15",
                "next_release_date": "2026-10-20",
                "basis": "registered_release_lag",
            }
        ],
    },
]
MISSING: dict[str, Any] = {
    "category": "missing",
    "priority": "P1",
    "metric_id": "CN_SF_TOTAL",
    "reason": "period_not_requested",
    "not_requested": [{"period": "2026-09", "reason": "unknown_release_configuration"}],
}


def _groups(text: str) -> dict[str, str]:
    """Each gap group's heading word with the rows under it, in the order shown."""
    groups: dict[str, str] = {}
    for label in ("缺失", "等待发布"):
        start = text.find(f"{label}（")
        if start >= 0:
            groups[label] = text[start:]
    if "缺失" in groups and "等待发布" in groups:
        groups["缺失"] = groups["缺失"][: groups["缺失"].find("等待发布（")]
    return groups


def test_section_07_lists_periods_awaiting_release_apart_from_the_missing() -> None:
    page = dashboard_page("/", _gaps_projection([MISSING, *AWAITING]), (), ())
    visible = _words(_visible(_by_id(page, "reading")))

    groups = _groups(visible)
    assert groups["等待发布"].startswith("等待发布（2）")
    assert (
        "P2 Brent 原油（EIA_BRENT_RBRTE）：等待发布 2026-10-15（下次发布 2026-10-21，来源原件写明）"
    ) in groups["等待发布"]
    assert (
        "P2 WTI 原油（EIA_WTI_RWTC）：等待发布 2026-10-15"
        "（下次发布 2026-10-20，按登记发布滞后推算）"
    ) in groups["等待发布"]
    assert groups["缺失"].startswith("缺失（1）")
    assert "EIA_" not in groups["缺失"]
    assert "未配置额外网页检索补缺" not in groups["等待发布"]


def test_the_board_gap_count_leaves_the_periods_awaiting_release_out() -> None:
    page = dashboard_page("/", _gaps_projection([MISSING, *AWAITING]), (), ())

    assert "1 项缺口（另 2 项等待发布）" in _words(_text(_by_id(page, "conclusion")))


def test_a_metric_also_missing_otherwise_notes_its_periods_awaiting_release() -> None:
    gap = {
        **MISSING,
        "awaiting_release": [
            {
                "period": "2026-10",
                "next_release_date": "2026-11-14",
                "basis": "registered_release_lag",
            }
        ],
    }
    visible = _words(
        _visible(_by_id(dashboard_page("/", _gaps_projection([gap]), (), ()), "reading"))
    )

    assert (
        "P1 社融存量（CN_SF_TOTAL）：未请求 2026-09（发布规则未登记）；"
        "等待发布 2026-10（下次发布 2026-11-14，按登记发布滞后推算）"
    ) in visible
    assert "等待发布（" not in visible
