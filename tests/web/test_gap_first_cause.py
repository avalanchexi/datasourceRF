"""Worker gaps 01: section 07 tells a candidate the negative cache held back from its first
cause, as the run of 10-15 should have listed the PBC column."""

from __future__ import annotations

from pring_cycle.dashboard import dashboard_page
from tests.web.test_overseas_cards import _by_id
from tests.web.test_reading_section import _gaps_projection, _visible, _words

COLUMN = "https://www.pbc.gov.cn/zhengcehuobisi/125207/125217/125925/index.html"


def test_a_cache_hold_is_listed_with_the_first_cause_beside_other_reasons() -> None:
    gap = {
        "category": "retrieval_failed",
        "priority": "P1",
        "metric_id": "CN_USDCNY_CENTRAL_PARITY",
        "reason": "one_period_behind_carried",
        "due_period": "2026-10-15",
        "held_period": "2026-10-14",
        "candidates": [
            {"url": "https://www.cls.cn/detail/2505221", "reason": "rule_not_matched"},
            {
                "url": COLUMN,
                "reason": "negative_cache_active",
                "first_cause": "official_context_usdcny_quote_missing",
            },
        ],
    }

    page = dashboard_page("/", _gaps_projection([gap]), (), ())
    visible = _words(_visible(_by_id(page, "reading")))

    assert "https://www.cls.cn/detail/2505221（解析规则未命中）" in visible
    assert f"{COLUMN}（被负缓存拦下，首因 官方页未见美元中间价）" in visible
