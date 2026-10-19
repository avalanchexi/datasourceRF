"""Section 04 as the macro judgement's basis: five dimension cards (ADR-0043, decision 11,
macro stage ticket 07).

A set the day summary judged names 04 for the judgement's basis; each card heads with its
dimension's direction, position and match, and each key indicator reads its main member
and where it went in the dimension's vote. An older set without the judgement keeps 04 as
it was.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest
from dash import html

from pring_cycle.dashboard import dashboard_page
from pring_cycle.projections import ProjectionSet
from tests.integration.test_macro_judgement import judged
from tests.web.test_confirmation_cards import _cards, _typical
from tests.web.test_dashboard_contract import _text
from tests.web.test_overseas_cards import _by_id, _drawer, _find, _words


@pytest.fixture(scope="module")
def projection(tmp_path_factory: pytest.TempPathFactory) -> ProjectionSet:
    return judged(Path(tmp_path_factory.mktemp("judged")))


def _page(projection: ProjectionSet) -> str:
    return " ".join(_text(dashboard_page("/", projection, (), ())).split())


def test_section_04_is_named_for_the_judgements_basis(projection: ProjectionSet) -> None:
    page = _page(projection)

    assert "04 宏观判断依据" in page
    assert "宏观事后确认" not in page


def test_an_older_set_keeps_section_04_as_it_was() -> None:
    older = _typical()

    assert "04 宏观事后确认" in _page(older) and "宏观判断依据" not in _page(older)
    assert _cards(older)[0].startswith("政策 支持 1 · 反证 0 · 仅观察 0 · 未确认 1")


def _basis_cards(projection: ProjectionSet) -> list[str]:
    """Each card's words in section 04, in page order."""
    section = _by_id(dashboard_page("/", projection, (), ()), "confirmation")
    return [
        _words(card)
        for card in _find(
            section, lambda item: "macro-basis-card" in str(getattr(item, "className", ""))
        )
    ]


def test_five_cards_head_with_their_direction_position_match_and_how_they_were_decided(
    projection: ProjectionSet,
) -> None:
    cards = _basis_cards(projection)

    assert [card.split(" ")[0] for card in cards] == ["政策", "信用", "增长", "物价", "库存"]
    heads = (
        # Decision 51: neutral while a member was not read, which says so.
        "政策 中性 · 吻合 · 120 日内无降息、LPR 下调、降准或上调（政策利率、降准未读到）",
        "信用 下行 · 低位（社融） · 吻合 · 多数决：下行 1 票",
        "增长 下行 · 高位（工业增加值） · 吻合 · 多数决：下行 2 票、上行 1 票",
        "物价 上行 · 高位（PPI） · 吻合 · 多数决：上行 2 票",
        "库存 主动补库存 · 不吻合 · 库存象限即维度方向",
    )
    for card, head in zip(cards, heads, strict=True):
        assert card.startswith(head), card


def _rows(projection: ProjectionSet) -> dict[str, str]:
    """Each key indicator's row in section 04, its words by the name it heads with."""
    section = _by_id(dashboard_page("/", projection, (), ()), "confirmation")
    rows = _find(section, lambda item: "indicator-row" in str(getattr(item, "className", "")))
    return {
        _words(_find(row, lambda item: isinstance(item, html.Strong))[0]): _words(row)
        for row in rows
    }


def test_each_key_indicator_says_where_it_went_in_its_dimensions_decision(
    projection: ProjectionSet,
) -> None:
    rows = _rows(projection)

    went = {
        # Policy is read by its actions in 120 days; the liquidity and DR007 are notes.
        "政策利率": "未读到，不计动作",
        "LPR": "120 日内无动作 → 中性",
        "降准": "未读到，不计动作",
        "流动性投放": "附注，不参与判定",
        "DR007": "附注，不参与判定",
        "社融": "投下行",
        "M1/M2": "缺当期读数，不投票",
        # Loans never vote in credit (decision 29); their divergence is a signal.
        "贷款": "不参与信用维投票，分化见信号清单",
        # A divergent indicator votes by its main member (decision 19).
        "PMI": "分化 · 按主要成员投下行",
        "工业增加值": "投上行",
        "GDP": "投下行",
        "产能利用率": "缺当期读数，不投票",
        "工业企业盈利": "缺当期读数，不投票",
        "PPI": "投上行",
        "CPI": "投上行",
        "PMI 价格": "缺当期读数，不投票",
        "库存象限": "主动补库存",
    }
    assert set(rows) >= set(went)
    for name, words in went.items():
        assert rows[name].endswith(words), rows[name]
    # A row reads its main member before its vote: its value and its period.
    assert rows["PPI"].startswith("PPI ") and "2026-07-31" in rows["PPI"]
    assert "不计数" not in " ".join(rows.values())


def test_a_row_opens_the_drawer_of_its_members(projection: ProjectionSet) -> None:
    page = dashboard_page("/", projection, (), ())
    section = _by_id(page, "confirmation")
    (pmi,) = [
        row
        for row in _find(
            section, lambda item: "indicator-row" in str(getattr(item, "className", ""))
        )
        if _words(row).startswith("PMI 制造业")
    ]

    text = _words(_drawer(page, pmi))
    assert text.startswith("PMI CN_PMI_ACTIVITY 关闭")
    assert text.index("主辅成员") < text.index("制造业 PMI")


def _edited(projection: ProjectionSet, edit: dict[str, dict[str, object]]) -> ProjectionSet:
    """The set with some of its published dimensions edited, as another day publishes them."""
    datasets = copy.deepcopy(projection.datasets)
    block = datasets["cycle_overview"]["macro_judgement"]
    for item in block["dimensions"]:  # type: ignore[index]
        item.update(edit.get(item["dimension"], {}))
    return replace(projection, datasets=datasets)


def test_a_tie_broken_by_social_financing_a_vote_short_of_half_and_a_cut_are_stated(
    projection: ProjectionSet,
) -> None:
    published = {
        item["dimension"]: item
        for item in projection.datasets["cycle_overview"]["macro_judgement"]["dimensions"]  # type: ignore[index]
    }
    policy = copy.deepcopy(published["policy"]["indicators"])
    policy[1].update(
        action="cut", actions=[{"period": "2026-05-20", "action": "cut", "member": "1 年期 LPR"}]
    )
    credit = copy.deepcopy(published["credit"]["indicators"])
    credit[1].update(vote="up", evidence_status="current", period="2026-07-31")
    edited = _edited(
        projection,
        {
            "policy": {"value": "easing", "basis": "cut", "matches": False, "indicators": policy},
            # Decision 46: social financing and M1/M2 tied, social financing decides.
            "credit": {
                "tally": {"down": 1, "up": 1},
                "basis": "tie_broken",
                "tie_breaker": "social_financing",
                "indicators": credit,
            },
            "price": {"value": None, "basis": "short_of_half", "matches": None, "tally": {"up": 1}},
        },
    )
    cards = _basis_cards(edited)
    rows = _rows(edited)

    assert cards[0].startswith("政策 宽松 · 不吻合 · LPR 2026-05-20 下调")
    assert rows["LPR"].endswith("2026-05-20 下调 → 宽松")
    assert cards[1].startswith(
        "信用 下行 · 低位（社融） · 吻合 · 多数决打平（下行 1 票、上行 1 票），取社融"
    )
    assert rows["M1/M2"].endswith("投上行")
    assert cards[3].startswith("物价 不明 · 不计分 · 明确者不足半数（2/3），不明")
