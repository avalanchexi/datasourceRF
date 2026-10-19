"""A newer period taken during the run is read back from before the cutoff is frozen
(go-live leftovers 03).

The formula's lookback reads t, t-1, t-12 and t-13 of a year-to-date loan total (ADR-0035).
When retrieval takes a newer t than the first plan read, the base periods it adds are
requested in the same run, not left to the final plan as gaps nobody asked for.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle import worker
from pring_cycle.models import model_v0015_manifest
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    refresh_official_context_document,
)
from pring_cycle.runtime import RuntimePaths
from tests.integration.test_lookback_declaration import _full_run, _periods

LOAN = "CN_LOAN_STRUCTURE"
MEMBERS = 9
COUNT = "一二三四五六七八九十"


def _report(month: str) -> bytes:
    """The PBC's financial statistics report of ``month``, its loans paragraph alone: out
    mid the month after, August's early, before the target day's end."""
    year, number = int(month[:4]), int(month[5:])
    released = (
        "2026-08-28 09:30:00"
        if month == "2026-08"
        else f"{year + number // 12}-{number % 12 + 1:02d}-14 16:30:05"
    )
    return f"""<html><body><h1>{year}年{number}月金融统计数据报告</h1>
    <p>文章来源： {released}</p>
    <p>五、前{COUNT[number - 1]}个月人民币贷款增加10.38万亿元。分部门看，住户贷款减少8271亿元，
    其中，短期贷款减少9281亿元，中长期贷款增加1010亿元；企（事）业单位贷款增加11万亿元，
    其中，短期贷款增加4.34万亿元，中长期贷款增加5.32万亿元，票据融资增加1.19万亿元；
    非银行业金融机构贷款减少3944亿元。</p></body></html>""".encode()


def _store_loans(paths: RuntimePaths, month: str, version: str) -> None:
    article = month.replace("-", "")
    url = f"https://www.pbc.gov.cn/diaochatongjisi/116219/116225/{article}/index.html"
    refresh_official_context_document(
        paths,
        family="pbc_loan_structure",
        source_url=url,
        expected_period=month,
        fetched_at=datetime.now(UTC),
        fetcher=lambda _url: FetchedOfficialContextDocument(_report(month), "text/html", url, 200),
        definition_version=version,
        metric_ids=(LOAN,),
    )


def _loan_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, serves_base: bool
) -> tuple[dict[str, Any], list[str]]:
    """A v0015 full run for 2026-08-28 holding no loans. Retrieval answers each loan period
    asked for; asked for July, it also takes August's early report. ``serves_base``: whether
    a base period August adds is answered too. Returns the whole plan and the loan periods
    asked for, in order."""
    version = str(model_v0015_manifest()["metric_catalog_version"])
    asked: list[str] = []

    def adapters(paths: RuntimePaths, scope: Any, now: datetime, **_: Any) -> dict[str, Any]:
        def local(_event: str) -> str | None:
            if LOAN not in scope.metric_ids:
                return None
            asked.append(scope.period)
            if scope.period == "2025-08" and not serves_base:
                return None
            _store_loans(paths, scope.period, version)
            if scope.period == "2026-07":
                _store_loans(paths, "2026-08", version)
            return f"fixture:loan:{scope.period}"

        return {"local": local}

    monkeypatch.setattr(worker, "_production_retrieval_adapters", adapters)
    plan, _requests = _full_run(tmp_path, monkeypatch, model_v0015_manifest())
    return plan, asked


def _loan_gaps(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {gap["period"]: gap for gap in plan["final"]["gaps"] if gap["metric_id"] == LOAN}


def test_a_newer_period_taken_during_the_run_has_its_base_periods_taken_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, asked = _loan_run(tmp_path, monkeypatch, serves_base=True)

    # The first plan read July; August, taken while July was asked for, reads August a year
    # before, which is asked for in the same run, once.
    assert _periods(plan["initial"])[LOAN] == ["2025-06", "2025-07", "2026-06", "2026-07"]
    assert asked.count("2025-08") == 1
    assert asked.index("2025-08") > asked.index("2026-07")
    gaps = _loan_gaps(plan)
    assert sorted(gaps) == ["2025-07", "2025-08", "2026-07", "2026-08"]
    assert all(gap["complete"] for gap in gaps.values()), gaps


def test_a_base_period_not_obtained_is_a_gap_asked_for_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, asked = _loan_run(tmp_path, monkeypatch, serves_base=False)

    # The run ends: what it could not obtain is listed with every member missing, not asked
    # for again and again.
    assert asked.count("2025-08") == 1
    gap = _loan_gaps(plan)["2025-08"]
    assert gap["complete"] is False
    assert len(gap["missing_members"]) == MEMBERS
