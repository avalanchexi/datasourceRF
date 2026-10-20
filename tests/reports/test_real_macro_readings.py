"""The first v0016 run's two AI readings (run-3ebbe323, target day 2026-10-19), refused by
the macro statement check and published as the template although each told the judged
stage, its scores and its confidence right (macro stage ticket 13). They are kept with the
frozen report input they were written against (bundle-612f01b4b419587fd525): stage III, a
tendency, tied with IV and V at 3 dimensions each, the PMI's recount stage V explicit.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.reports import AdapterResponse, ReportInput, ReportRepository, ReportService
from tests.reports.test_report_boundary import FakeAdapter

SAMPLE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/report_input/rejected-readings-20261019.json"
    ).read_text()
)


@pytest.fixture
def frozen() -> ReportInput:
    document = SAMPLE["bundle"]
    return ReportInput(
        **{
            **document,
            "report_cutoff": datetime.fromisoformat(document["report_cutoff"]),
            "system_as_of": datetime.fromisoformat(document["system_as_of"]),
        }
    )


def rejection(tmp_path: Path, source: ReportInput, adapter: str, reading: dict[str, Any]) -> Any:
    """The check the reading fails, None when it is accepted as the report."""
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter(adapter, AdapterResponse.succeeded(reading))

    result = ReportService(reports, (first,)).generate(source)

    (attempt,) = reports.attempts(result.report_snapshot_id)
    check = attempt.process_audit.get("rejection", {}).get("check")
    assert result.adapter == (adapter if check is None else "deterministic")
    return check


@pytest.mark.parametrize("adapter", ["codex_cli", "claude_code_cli"])
def test_the_first_v0016_readings_are_accepted_whole(
    tmp_path: Path, frozen: ReportInput, adapter: str
) -> None:
    # A tendency must be told as such, so being accepted says the confidence was told.
    reading = copy.deepcopy(SAMPLE["readings"][adapter])

    assert rejection(tmp_path, frozen, adapter, reading) is None


def told(text: str) -> dict[str, Any]:
    """The codex reading with ``text`` as its only paragraph."""
    reading: dict[str, Any] = copy.deepcopy(SAMPLE["readings"]["codex_cli"])
    reading["sections"] = [{"title": "宏观判断与五维依据", "explanation": text}]
    return reading


@pytest.mark.parametrize(
    ("text", "check"),
    [
        # Three stages listed, then the score each got.
        ("宏观判断为第三阶段（倾向），第三阶段、第四阶段、第五阶段各得 3 维。", None),
        (
            "宏观判断为第三阶段（倾向），第三阶段、第四阶段、第五阶段各得 4 维。",
            "macro_stated_score",
        ),
    ],
)
def test_the_scores_each_stage_got(
    tmp_path: Path, frozen: ReportInput, text: str, check: str | None
) -> None:
    assert rejection(tmp_path, frozen, "codex_cli", told(text)) == check


TOLD = "宏观判断为第三阶段，把握程度为倾向。"


@pytest.mark.parametrize(
    ("text", "check"),
    [
        # The two readings' own sentences: an explicit judgement denied of a tendency.
        (
            TOLD + "第三阶段、第四阶段、第五阶段各得 3 维，规则选择距离上次确认的第三阶段最近者，"
            "因此不能解释为明确结论。",
            None,
        ),
        (
            "宏观判断为第三阶段，把握程度为倾向，不是明确的结论：五个维度都有读数，其中 3 维与"
            "第三阶段吻合，但第三阶段、第四阶段、第五阶段各得 3 维、三者并列（第六阶段 2 维，"
            "第一阶段 1 维，第二阶段 0 维）。",
            None,
        ),
        # Denying the confidence the rules judged, or denying without telling it.
        ("宏观判断为第三阶段，把握程度不是倾向。", "macro_stated_confidence"),
        ("宏观判断为第三阶段，不是明确的结论。", "macro_confidence_unstated"),
        # Rewriting the stage or the confidence is still refused.
        ("宏观判断为第四阶段，把握程度为倾向。", "macro_stated_stage"),
        ("宏观判断为第三阶段，把握程度为明确。", "macro_stated_confidence"),
    ],
)
def test_a_confidence_denied_is_not_one_told(
    tmp_path: Path, frozen: ReportInput, text: str, check: str | None
) -> None:
    assert rejection(tmp_path, frozen, "codex_cli", told(text)) == check


RECOUNT = (
    "如果 PMI 改按少数方向计票，增长维度转为下行，判断会变为第五阶段，把握程度为明确（5 维中"
    " 4 维吻合），对应第三阶段向第五阶段转换，目前只是萌芽。"
)


@pytest.mark.parametrize(
    ("text", "check"),
    [
        # The claude reading's own sentence: the PMI's recount, stage V explicit.
        (TOLD + RECOUNT, None),
        # A recount told otherwise than the rules recounted it.
        (TOLD + RECOUNT.replace("把握程度为明确", "把握程度为倾向"), "macro_stated_confidence"),
        (TOLD + RECOUNT.replace("变为第五阶段", "变为第六阶段"), "macro_stated_stage"),
        (
            TOLD + RECOUNT.replace("变为第五阶段", "变为第四阶段"),
            "macro_stated_confidence",
        ),
        (TOLD + RECOUNT.replace("向第五阶段", "向第六阶段"), "macro_stated_stage"),
        # What the conclusion is now is read as the conclusion, after the condition too.
        (TOLD + RECOUNT.replace("目前只是萌芽", "目前宏观判断为第五阶段"), "macro_stated_stage"),
        (TOLD + RECOUNT.replace("目前只是萌芽", "当前把握程度为明确"), "macro_stated_confidence"),
    ],
)
def test_a_recount_under_a_condition_is_read_as_the_recount(
    tmp_path: Path, frozen: ReportInput, text: str, check: str | None
) -> None:
    assert rejection(tmp_path, frozen, "codex_cli", told(text)) == check


DENIED = (
    "全部 17 项关键指标也都记为不适用，包括 PMI、PPI、CPI、社融、DR007 和库存象限，没有任何一项"
    "记为支持或反证。"
)


@pytest.mark.parametrize(
    ("text", "check"),
    [
        # The claude reading's own sentence: no key indicator counted for or against.
        (TOLD + DENIED, None),
        # Every key indicator is not applicable: denying it is saying another relation.
        (TOLD + DENIED.replace("记为支持或反证", "记为不适用"), "restates_confirmation"),
        (
            TOLD + DENIED.replace("没有任何一项记为支持或反证", "库存象限记为支持"),
            "restates_confirmation",
        ),
    ],
)
def test_a_relation_denied_of_every_key_indicator(
    tmp_path: Path, frozen: ReportInput, text: str, check: str | None
) -> None:
    assert rejection(tmp_path, frozen, "codex_cli", told(text)) == check
