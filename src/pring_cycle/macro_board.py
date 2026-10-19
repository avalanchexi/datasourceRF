"""The board's macro stage judgement, as the day's set published it (ADR-0043).

The 01 conclusion board heads with the judgement and lists the five dimensions by their
three cycles; the price stage and the rows a reader checks it by follow. Everything is
read from ``cycle_overview.macro_judgement``: nothing is judged, scored or stated against
another stage here, and a set without the block keeps its own board. Later tickets add
their parts here (the fallbacks' ties and gaps, the signal list, the price verification,
section 04's five cards), so the cockpit's own sections stay apart from them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dash import html

from pring_cycle.macro_judgement import ASSETS, GROUPS
from pring_cycle.wording import (
    CORE_ASSET_NAMES,
    CORE_STATE_LABELS,
    MACRO_CONFIDENCES,
    MACRO_DIMENSIONS,
    MACRO_GROUPS,
    MACRO_JUDGEMENT,
    MACRO_POSITIONS,
    MACRO_UNKNOWN,
    MACRO_VALUES,
    stage_name,
)

_ACTIONS = {"cut": "下调", "hike": "上调"}
_NO_STAGE = "无可取阶段（证据不足、三核心不可用且无上一确认阶段）"
_NO_REFERENCE = "无上一确认阶段，按 Pring 顺序取首个"
_UNREAD_POLICY = "政策利率、LPR、降准均无可读记录"
_NO_ACTION = "120 日内无降息、LPR 下调、降准或上调"


def judgement(overview: Mapping[str, object]) -> Mapping[str, Any] | None:
    """The set's published judgement; None for a set made before there was one."""
    block = overview.get("macro_judgement")
    return block if isinstance(block, Mapping) else None


def conclusion_left(
    block: Mapping[str, Any], price_stage: str, rows: Sequence[tuple[str, Any]]
) -> html.Div:
    """The board's left column: the judgement, its dimensions, then the price stage."""
    return html.Div(
        [
            html.P(MACRO_JUDGEMENT, className="section-kicker"),
            html.H2(
                title(_mapping(block.get("conclusion")), block), className="stage-value macro-title"
            ),
            *([html.P(line, className="macro-fallback")] if (line := fallback(block)) else []),
            dimensions(block),
            html.P("价格阶段", className="section-kicker"),
            html.P(price_stage, className="price-stage-value"),
            html.Dl(
                [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
                className="board-rows",
            ),
        ],
        className="board-left",
    )


def title(conclusion: Mapping[str, Any], block: Mapping[str, Any]) -> str:
    """宏观判断：第 N 阶段（明确，5 维中 k 维吻合）· 相对上次确认第 M 阶段 前进 n 步."""
    stage = conclusion.get("stage")
    if stage is None:
        return f"{MACRO_JUDGEMENT}：{_NO_STAGE}"
    head = (
        f"{MACRO_JUDGEMENT}：{stage_name(stage)}"
        f"（{MACRO_CONFIDENCES.get(str(conclusion.get('confidence')), '')}，"
        f"{conclusion.get('known')} 维中 {conclusion.get('matched')} 维吻合）"
    )
    reference, steps = conclusion.get("reference_stage"), conclusion.get("steps")
    if reference is None or not isinstance(steps, int):
        return f"{head}· 无上一确认阶段"
    move = "不变" if steps == 0 else f"前进 {steps} 步" if steps > 0 else f"后退 {-steps} 步"
    return f"{head}· 相对上次确认{stage_name(reference)} {move}"


def fallback(block: Mapping[str, Any]) -> str | None:
    """How a tendency or a weak judgement took its stage, under the title (decisions 18,
    24, 35): the stages tied and their score, or the dimensions lacking and what the
    judgement fell back on. None for an explicit one."""
    raw = _mapping(block.get("raw"))
    reference = _mapping(block.get("conclusion")).get("reference_stage")
    nearest = f"取离上次确认{stage_name(reference)}最近者" if reference else _NO_REFERENCE
    stage = raw.get("stage")
    if raw.get("basis") == "tied":
        others = "、".join(stage_name(item) for item in raw.get("tied") or () if item != stage)
        return (
            f"{MACRO_CONFIDENCES['tendency']}{stage_name(stage)}"
            f"（与{others}并列，各 {raw.get('matched')} 维）：{nearest}"
        )
    if raw.get("basis") != "insufficient":
        return None
    threshold, known = raw.get("threshold"), raw.get("known")
    if isinstance(known, int) and isinstance(threshold, int) and known < threshold:
        lacking = "、".join(
            MACRO_DIMENSIONS.get(str(item.get("dimension")), str(item.get("dimension")))
            for item in _mappings(block.get("dimensions"))
            if item.get("value") is None
        )
        short = f"已知 {known} 维，缺{lacking}，不足 {threshold} 维"
    else:
        top = max(
            (v for v in _mapping(block.get("scores")).values() if isinstance(v, int)), default=0
        )
        short = f"{known} 维已知，最高仅 {top} 维吻合，不足 {threshold} 维"
    taken = _mapping(raw.get("fallback"))
    combination = _mapping(taken.get("combination"))
    if taken.get("source") != "combination":
        then = (
            f"三核心不可用，取上一确认阶段{stage_name(stage)}"
            if stage is not None
            else f"三核心不可用且无上一确认阶段，{_NO_STAGE}"
        )
    elif taken.get("differences") == 0:
        then = f"价格组合典型（{_cores(combination)}），取价格阶段{stage_name(stage)}"
    else:
        candidates = "、".join(stage_name(item) for item in taken.get("candidates") or ())
        then = (
            f"退回价格组合推断：{_cores(combination)}与{candidates}"
            f"各差 {taken.get('differences')} 项，{nearest}"
        )
    return f"{MACRO_CONFIDENCES['weak']}判断：{short}；{then}"


def _cores(combination: Mapping[str, Any]) -> str:
    return " · ".join(
        f"{CORE_ASSET_NAMES[asset]}{CORE_STATE_LABELS.get(str(combination.get(asset)), '不明')}"
        for asset in ASSETS
    )


def dimensions(block: Mapping[str, Any]) -> html.Div:
    """The five dimensions by their cycles: money, the economy, inventory (decision 10)."""
    by_name = {str(item.get("dimension")): item for item in _mappings(block.get("dimensions"))}
    return html.Div(
        [
            html.Div(
                [
                    html.H3(MACRO_GROUPS[group], className="macro-group-title"),
                    html.Ul(
                        [html.Li(dimension_line(by_name.get(name, {}))) for name in members],
                        className="macro-dimension-list",
                    ),
                ],
                className="macro-group",
            )
            for group, members in GROUPS
        ],
        className="macro-dimensions",
    )


def dimension_line(item: Mapping[str, Any]) -> str:
    """政策：中性 · 吻合 · 依据 -- the direction, its position, its match and its basis."""
    name = MACRO_DIMENSIONS.get(str(item.get("dimension")), str(item.get("dimension")))
    value = item.get("value")
    parts = [f"{name}：{MACRO_VALUES.get(str(value), MACRO_UNKNOWN) if value else MACRO_UNKNOWN}"]
    if value is not None and "position_from" in item:
        parts.append(MACRO_POSITIONS.get(str(item.get("position")), "位置不明"))
    matches = item.get("matches")
    parts.append("吻合" if matches is True else "不吻合" if matches is False else "不计分")
    parts.append(basis(item))
    return " · ".join(parts)


def basis(item: Mapping[str, Any]) -> str:
    """The dimension's key basis in one sentence, from its published indicators."""
    indicators = _mappings(item.get("indicators"))
    reason = str(item.get("basis"))
    if item.get("dimension") == "policy":
        actions = [
            f"{indicator.get('name')} {action.get('period')} {_ACTIONS[str(action.get('action'))]}"
            for indicator in indicators
            for action in _mappings(indicator.get("actions"))
            if action.get("action") in _ACTIONS
        ]
        if reason == "no_action":
            return _NO_ACTION
        if reason == "unread":
            return _UNREAD_POLICY
        prefix = "窗口内既有下调又有上调：" if reason == "cut_and_hike" else ""
        return prefix + "、".join(actions)
    if item.get("dimension") == "inventory":
        indicator = indicators[0] if indicators else {}
        if reason != "quadrant":
            lacking = "缺当期读数" if indicator.get("evidence_status") != "current" else "未分类"
            return f"{indicator.get('name') or '库存象限'}{lacking}"
        divergent = "（辅助成员分化）" if indicator.get("divergent") else ""
        return f"{indicator.get('name')} {indicator.get('period')}{divergent}"
    voters = [indicator for indicator in indicators if indicator.get("voting")]
    if reason == "short_of_half":
        clear = sum(each.get("vote") is not None for each in voters)
        return f"明确者不足半数（{clear}/{len(voters)}）：" + _lacking(voters)
    votes = "；".join(
        _spaced(
            str(indicator.get("name") or indicator.get("key")),
            MACRO_VALUES.get(str(indicator.get("vote")), MACRO_UNKNOWN),
        )
        + ("（分化）" if indicator.get("divergent") else "")
        for indicator in voters
    )
    if reason == "tie_broken":
        breaker = next(
            (
                str(each.get("name"))
                for each in indicators
                if each.get("key") == item.get("tie_breaker")
            ),
            str(item.get("tie_breaker")),
        )
        return f"打平取{breaker}：{votes}"
    lead = {"tied": "多数决打平："}.get(reason, "")
    return lead + votes


def _lacking(voters: Sequence[Mapping[str, Any]]) -> str:
    """An unknown dimension's clear votes, then what the others lack: a current reading, or
    with one, a direction (ticket 03)."""

    def named(each: Mapping[str, Any]) -> str:
        return str(each.get("name") or each.get("key"))

    parts = [
        _spaced(named(each), MACRO_VALUES[str(each["vote"])])
        + ("（分化）" if each.get("divergent") else "")
        for each in voters
        if each.get("vote") is not None
    ]
    unvoted = [each for each in voters if each.get("vote") is None]
    for status, lack in ((False, "缺当期读数："), (True, "方向未读出：")):
        names = [
            named(each) for each in unvoted if (each.get("evidence_status") == "current") == status
        ]
        if names:
            parts.append(lack + "、".join(names))
    return "；".join(parts)


def _spaced(name: str, word: str) -> str:
    """A name ending in Latin letters or digits takes a space before Chinese (PMI 下行)."""
    return f"{name} {word}" if name[-1:].isascii() else f"{name}{word}"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
