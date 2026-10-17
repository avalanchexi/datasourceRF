"""Section 07 names what of a release the run holds and what it still lacks (worker gaps 02).

The PBC's September social financing came out on 10-14; the run held the stock and the flow
from TuShare and lacked only the official stock growth, yet section 07 said the whole period
was never requested. Each case renders the home page from a hand-built projection.
"""

from __future__ import annotations

from typing import Any

from tests.web.test_reading_section import _gaps_projection, _reading, _visible, _words

STOCK_END = 'CN_SF_TOTAL:{"measure": "stock_end"}'
YTD_INCREMENT = 'CN_SF_TOTAL:{"measure": "ytd_increment"}'
STOCK_YOY = 'CN_SF_TOTAL:{"measure": "stock_yoy"}'


def test_a_release_partly_held_names_the_members_taken_and_those_still_missing() -> None:
    gaps: list[dict[str, Any]] = [
        {
            "category": "missing",
            "priority": "P1",
            "metric_id": "CN_SF_TOTAL",
            "reason": "members_missing",
            "members_missing": [
                {
                    "period": "2026-09",
                    "held_members": [STOCK_END, YTD_INCREMENT],
                    "missing_members": [STOCK_YOY],
                }
            ],
            "no_web_fallback": False,
        }
    ]

    visible = _words(_visible(_reading(_gaps_projection(gaps))))

    assert (
        "P1 社融存量（CN_SF_TOTAL）：2026-09 已取得 期末存量、累计增量，仍缺 存量同比"
    ) in visible
    assert "未请求" not in visible
    assert "members_missing" not in visible and "stock_yoy" not in visible
