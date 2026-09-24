"""Event #02: the RRR rule reads a cut on the effective day its sentence states (ADR-0028)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pring_cycle.news_rules import extract, plain_text, stated_event_days

CHRONICLE = Path(__file__).parents[1] / "fixtures" / "pbc_rrr_chronicle_2025.html"
RRR = ("CN_RRR_EVENT",)


def chronicle_cut() -> str:
    """The PBC's own line for the cut of 15 May 2025."""
    text = plain_text(CHRONICLE.read_text(encoding="utf-8"))
    return next(line for line in text.splitlines() if "下调金融机构存款准备金率" in line)


def scopes(day: str, text: str) -> dict[str, float]:
    return {v.dimensions["scope"]: v.value for v in extract(RRR, day, text).values}


def test_a_cut_is_read_on_the_effective_day_it_states() -> None:
    text = chronicle_cut()

    assert stated_event_days(RRR, text, published=date(2025, 5, 7)) == ("2025-05-15",)
    assert scopes("2025-05-15", text) == {
        "excluding_5_percent_institutions": -0.5,
        "auto_finance_and_financial_leasing_companies": -5.0,
    }


def test_a_sentence_that_names_no_day_is_not_read() -> None:
    text = "央行下调金融机构存款准备金率0.5个百分点（不含已执行5%存款准备金率的金融机构）。"

    assert stated_event_days(RRR, text, published=date(2026, 9, 22)) == ()


def test_a_day_in_an_earlier_sentence_does_not_date_the_cut() -> None:
    text = (
        "9月22日，国新办举行新闻发布会。"
        "央行下调金融机构存款准备金率0.5个百分点（不含已执行5%存款准备金率的金融机构）。"
    )

    assert stated_event_days(RRR, text, published=date(2026, 9, 22)) == ()
    assert scopes("2026-09-22", text) == {}


def test_a_day_without_its_year_is_the_one_nearest_the_text() -> None:
    text = (
        "中国人民银行决定于1月5日下调金融机构存款准备金率0.5个百分点"
        "（不含已执行5%存款准备金率的金融机构）。"
    )

    assert stated_event_days(RRR, text, published=date(2026, 12, 25)) == ("2027-01-05",)
