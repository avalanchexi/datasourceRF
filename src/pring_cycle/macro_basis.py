"""Section 04 under a macro stage judgement: the five dimensions' basis (ADR-0043, decision
11, macro stage ticket 07).

Five cards in the dimensions' order, each heading with the dimension's direction, its
position, whether it matches the judged stage and how it was decided; each key indicator
then says where it went in that decision. Everything is read from the published
judgement: nothing is voted again here, and the confirmation's relations are not read for
a vote. The rows' readings and drawers are the cockpit's own, made by ``row``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from dash import html

from pring_cycle.macro_board import basis
from pring_cycle.macro_judgement import DIMENSIONS
from pring_cycle.wording import (
    MACRO_BASIS,
    MACRO_DIMENSIONS,
    MACRO_POSITIONS,
    MACRO_UNKNOWN,
    MACRO_VALUES,
)

TITLE = MACRO_BASIS
SCOPE = (
    "五维方向由关键指标读法得出（政策按 120 日内动作，库存即象限，其余多数决），"
    "与宏观周期特征表比对；确认度对价格阶段计算，见 01 价格验证。"
)
UNREAD = "未读到"
_ACTIONS = {"cut": "下调", "hike": "上调"}
_POLICY_VALUES = {"cut": "easing", "hike": "tightening"}

# ``row(dimension, indicator, vote)``: one key indicator's row, its published entry and
# where it went in its dimension's decision.
Row = Callable[[str, Mapping[str, Any], str], Any]


def cards(block: Mapping[str, Any], row: Row) -> html.Div:
    """The five cards: policy, credit, growth, prices, inventory."""
    by_name = {str(item.get("dimension")): item for item in _mappings(block.get("dimensions"))}
    return html.Div(
        [card(by_name.get(name, {"dimension": name}), row) for name in DIMENSIONS],
        className="dimension-grid",
    )


def card(item: Mapping[str, Any], row: Row) -> html.Article:
    name = str(item.get("dimension"))
    return html.Article(
        [
            html.H3(MACRO_DIMENSIONS[name]),
            html.P(head(item)),
            *[
                row(name, indicator, vote(name, indicator))
                for indicator in _mappings(item.get("indicators"))
            ],
        ],
        className="dimension-card macro-basis-card",
    )


def head(item: Mapping[str, Any]) -> str:
    """下行 · 低位（社融） · 吻合 · 多数决：下行 1 票 -- the direction, its position, its
    match and how it was decided."""
    value = item.get("value")
    parts = [MACRO_VALUES.get(str(value), MACRO_UNKNOWN) if value else MACRO_UNKNOWN]
    if value is not None and "position_from" in item:
        source = next(
            (
                str(each.get("name"))
                for each in _mappings(item.get("indicators"))
                if each.get("key") == item.get("position_from")
            ),
            str(item.get("position_from")),
        )
        parts.append(f"{MACRO_POSITIONS.get(str(item.get('position')), '位置不明')}（{source}）")
    matches = item.get("matches")
    parts.append("吻合" if matches is True else "不吻合" if matches is False else "不计分")
    parts.append(decided(item))
    return " · ".join(parts)


def decided(item: Mapping[str, Any]) -> str:
    """How the dimension took its direction: the policy rule, the quadrant, or the vote."""
    reason = item.get("basis")
    if item.get("dimension") == "policy":
        # Decision 51: a member not read adds no action; the card says which were not.
        unread = [
            str(each.get("name") or each.get("key"))
            for each in _mappings(item.get("indicators"))
            if each.get("voting") and each.get("action") is None and not each.get("actions")
        ]
        missing = f"（{'、'.join(unread)}{UNREAD}）" if unread and reason != "unread" else ""
        return basis(item) + missing
    if item.get("dimension") == "inventory":
        return "库存象限即维度方向" if reason == "quadrant" else basis(item)
    tally = sorted(_mapping(item.get("tally")).items(), key=lambda pair: (-int(pair[1]), pair[0]))
    counted = "、".join(f"{MACRO_VALUES.get(str(key), key)} {count} 票" for key, count in tally)
    if reason == "short_of_half":
        voters = [each for each in _mappings(item.get("indicators")) if each.get("voting")]
        clear = sum(each.get("vote") is not None for each in voters)
        return f"明确者不足半数（{clear}/{len(voters)}），不明"
    if reason == "tied":
        return f"多数决打平（{counted}），不明"
    if reason == "tie_broken":
        breaker = next(
            (
                str(each.get("name"))
                for each in _mappings(item.get("indicators"))
                if each.get("key") == item.get("tie_breaker")
            ),
            str(item.get("tie_breaker")),
        )
        return f"多数决打平（{counted}），取{breaker}"
    return f"多数决：{counted}"


def vote(dimension: str, indicator: Mapping[str, Any]) -> str:
    """Where a key indicator went in its dimension's decision, or why it went nowhere."""
    current = indicator.get("evidence_status") == "current"
    if not indicator.get("voting"):
        if dimension == "policy":
            return "附注，不参与判定"
        return f"不参与{MACRO_DIMENSIONS[dimension]}维投票，分化见信号清单"
    if dimension == "policy":
        actions = _mappings(indicator.get("actions"))
        if actions:
            return "、".join(
                f"{action.get('period')} {_ACTIONS[str(action.get('action'))]}"
                f" → {MACRO_VALUES[_POLICY_VALUES[str(action.get('action'))]]}"
                for action in actions
            )
        if indicator.get("action") == "none":
            return f"120 日内无动作 → {MACRO_VALUES['neutral']}"
        return f"{UNREAD}，不计动作"
    if dimension == "inventory":
        quadrant = indicator.get("quadrant")
        if not current:
            return "缺当期读数，不明"
        if str(quadrant) not in MACRO_VALUES:
            return "未分类，不明"
        return MACRO_VALUES[str(quadrant)] + (
            "（辅助成员分化）" if indicator.get("divergent") else ""
        )
    direction = indicator.get("vote")
    if direction is None:
        return "方向未读出，不投票" if current else "缺当期读数，不投票"
    lead = "分化 · 按主要成员投" if indicator.get("divergent") else "投"
    return lead + MACRO_VALUES.get(str(direction), MACRO_UNKNOWN)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
