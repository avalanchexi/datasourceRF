"""The hysteresis on the 01 board (ADR-0043, macro stage ticket 05).

While a new judgement is counted, the main conclusion keeps its stage and confidence,
noted as held with the day's raw judgement (decision 45), and the run is listed with the
signals: 倾向转向第 X 阶段（已 k/10 日）(decision 26).
"""

from __future__ import annotations

from pathlib import Path

from pring_cycle.dashboard import dashboard_page
from tests.integration.test_macro_hysteresis import SF_REVISED, last, macro_day, revise_credit
from tests.integration.test_macro_judgement import publish_from
from tests.web.test_dashboard_contract import _text


def test_a_held_conclusion_is_noted_and_its_run_listed_with_the_signals(tmp_path: Path) -> None:
    paths = macro_day(tmp_path)
    revise_credit(paths, SF_REVISED, on=-2)
    projection = publish_from(paths, last(3))

    text = " ".join(_text(dashboard_page("/", projection, (), ())).split())

    assert (
        "宏观判断：第五阶段（明确，5 维中 3 维吻合）· 相对上次确认第三阶段 前进 2 步 "
        "滞回保持，当日原始判断：第三阶段（倾向）"
    ) in text
    assert "信号清单 支持后退 倾向转向第三阶段（已 2/10 日）" in text
