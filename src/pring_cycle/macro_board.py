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

from pring_cycle.drawer import drawer_key, drawer_panel, drawer_trigger
from pring_cycle.macro_judgement import ASSETS, GROUPS
from pring_cycle.macro_signals import GROUPS as SIGNAL_GROUPS
from pring_cycle.wording import (
    CORE_STATE_LABELS,
    MACRO_ASSETS,
    MACRO_CONFIDENCES,
    MACRO_DIMENSIONS,
    MACRO_GROUPS,
    MACRO_JUDGEMENT,
    MACRO_MATURITIES,
    MACRO_NO_SIGNALS,
    MACRO_POSITIONS,
    MACRO_SAME_SOURCE,
    MACRO_SIGNAL_GROUPS,
    MACRO_SIGNAL_LIST,
    MACRO_UNKNOWN,
    MACRO_VALUES,
    MACRO_VERIFICATION,
    UNAVAILABLE,
    stage_name,
)

_ACTIONS = {"cut": "下调", "hike": "上调"}
_NO_STAGE = "无可取阶段（证据不足、三核心不可用且无上一确认阶段）"
_NO_REFERENCE = "无上一确认阶段，按 Pring 顺序取首个"
_UNREAD_POLICY = "政策利率、LPR、降准均无可读记录"
_NO_ACTION = "120 日内无降息、LPR 下调、降准或上调"
_HELD = "滞回保持"
VERIFICATION_DRAWER = drawer_key("conclusion", "price-verification")


def judgement(overview: Mapping[str, object]) -> Mapping[str, Any] | None:
    """The set's published judgement; None for a set made before there was one."""
    block = overview.get("macro_judgement")
    return block if isinstance(block, Mapping) else None


def conclusion_left(block: Mapping[str, Any]) -> html.Div:
    """The board's left column: the judgement, its dimensions, its signals, then the price
    verification (decision 21)."""
    return html.Div(
        [
            html.P(MACRO_JUDGEMENT, className="section-kicker"),
            html.H2(
                title(_mapping(block.get("conclusion")), block), className="stage-value macro-title"
            ),
            *([html.P(line, className="macro-held")] if (line := held(block)) else []),
            *([html.P(line, className="macro-fallback")] if (line := fallback(block)) else []),
            *([html.P(line, className="macro-fallback")] if (line := raw_fallback(block)) else []),
            dimensions(block),
            signal_list(block),
            html.Dl(
                [
                    html.Dt(MACRO_VERIFICATION),
                    html.Dd(drawer_trigger(VERIFICATION_DRAWER, verification_line(block))),
                ],
                className="board-rows",
            ),
        ],
        className="board-left",
    )


def verification_line(block: Mapping[str, Any]) -> str:
    """价格阶段：第六阶段（债券熊市 · 股票熊市 · 商品熊市） · 第五阶段预期：… · 商品偏离 --
    the price stage or the noncanonical combination, what the judged stage expects, and
    whether they agree or which asset is off (decision 10)."""
    verification = _mapping(block.get("price_verification"))
    if not verification:
        return "该投影未提供价格验证"
    actual = _cores(_mapping(verification.get("combination")), unread=UNAVAILABLE)
    stage, reason = verification.get("price_stage"), verification.get("reason")
    if stage is not None:
        head = f"价格阶段：{stage_name(stage)}（{actual}）"
    elif reason == "noncanonical_combination":
        head = f"非典型组合（{actual}）"
    else:
        head = f"暂无价格阶段（{actual}）"
    expected = verification.get("expected")
    if not isinstance(expected, Mapping):
        return f"{head} · 宏观判断无阶段，不比对"
    combination = _mapping(verification.get("combination"))
    unread = [_asset(asset) for asset in ASSETS if combination.get(asset) is None]
    deviations = "、".join(_asset(asset) for asset in verification.get("deviations") or ())
    found = [
        *([f"{deviations}偏离"] if deviations else []),
        *([f"{'、'.join(unread)}不可用，未比对"] if unread else []),
    ]
    return (
        f"{head} · {stage_name(verification.get('expected_stage'))}预期："
        f"{_cores(expected, unread=UNAVAILABLE)} · " + ("；".join(found) or "一致")
    )


def verification_panel(
    block: Mapping[str, Any], rows: Sequence[tuple[str, Any]], counted: Sequence[Any]
) -> html.Div:
    """The verification row's drawer: the price stage's ``rows`` and, with a price stage, the
    confirmation ``counted`` against it (decision 11); the cockpit builds both."""
    return drawer_panel(
        VERIFICATION_DRAWER,
        MACRO_VERIFICATION,
        [
            html.P(verification_line(block)),
            html.Dl(
                [item for label, value in rows for item in (html.Dt(label), html.Dd(value))],
                className="board-rows",
            ),
            *counted,
        ],
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


def held(block: Mapping[str, Any]) -> str | None:
    """滞回保持，当日原始判断：第 X 阶段（倾向） -- under the title while the hysteresis
    holds the conclusion against the day's raw judgement (decision 45); None otherwise."""
    if _mapping(block.get("hysteresis")).get("basis") != "held":
        return None
    raw = _mapping(block.get("raw"))
    if raw.get("stage") is None:
        return f"{_HELD}，当日原始判断：{_NO_STAGE}"
    return (
        f"{_HELD}，当日原始判断：{stage_name(raw.get('stage'))}"
        f"（{MACRO_CONFIDENCES.get(str(raw.get('confidence')), '')}）"
    )


def fallback(block: Mapping[str, Any]) -> str | None:
    """How the main conclusion took its stage, under the title (decisions 18, 24, 35): the
    stages tied and their score, or the dimensions lacking and what the judgement fell back
    on. Held, it is told from the judgement it was taken from, with that day (decision 45).
    None for an explicit one."""
    if _mapping(block.get("hysteresis")).get("basis") == "held":
        taken = _mapping(_mapping(block.get("conclusion")).get("formed"))
        return _basis(taken, on=taken.get("on")) if taken else None
    return _basis(_raw_facts(block))


def raw_fallback(block: Mapping[str, Any]) -> str | None:
    """How the day's raw judgement took its stage, while the hysteresis holds the conclusion
    off it: told apart from the conclusion's own (decision 24). None otherwise."""
    if _mapping(block.get("hysteresis")).get("basis") != "held":
        return None
    line = _basis(_raw_facts(block))
    return f"当日原始判断依据：{line}" if line else None


def _raw_facts(block: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_mapping(block.get("raw")),
        "reference_stage": _mapping(block.get("conclusion")).get("reference_stage"),
        "scores": _mapping(block.get("scores")),
        "unknown": [
            item.get("dimension")
            for item in _mappings(block.get("dimensions"))
            if item.get("value") is None
        ],
    }


def _basis(facts: Mapping[str, Any], *, on: object = None) -> str | None:
    reference = facts.get("reference_stage")
    nearest = f"取离上次确认{stage_name(reference)}最近者" if reference else _NO_REFERENCE
    stage = facts.get("stage")
    if facts.get("basis") == "tied":
        others = "、".join(stage_name(item) for item in facts.get("tied") or () if item != stage)
        dated = f"，{on} 判断" if on else ""
        return (
            f"{MACRO_CONFIDENCES['tendency']}{stage_name(stage)}"
            f"（与{others}并列，各 {facts.get('matched')} 维{dated}）：{nearest}"
        )
    if facts.get("basis") != "insufficient":
        return None
    threshold, known = facts.get("threshold"), facts.get("known")
    if isinstance(known, int) and isinstance(threshold, int) and known < threshold:
        lacking = "、".join(
            MACRO_DIMENSIONS.get(str(item), str(item)) for item in facts.get("unknown") or ()
        )
        short = f"已知 {known} 维，缺{lacking}，不足 {threshold} 维"
    else:
        top = max(
            (v for v in _mapping(facts.get("scores")).values() if isinstance(v, int)), default=0
        )
        short = f"{known} 维已知，最高仅 {top} 维吻合，不足 {threshold} 维"
    taken = _mapping(facts.get("fallback"))
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
    dated = f"（{on} 判断）" if on else ""
    return f"{MACRO_CONFIDENCES['weak']}判断{dated}：{short}；{then}"


def _cores(combination: Mapping[str, Any], *, unread: str = "不明") -> str:
    return " · ".join(
        f"{MACRO_ASSETS[asset]}{CORE_STATE_LABELS.get(str(combination.get(asset)), unread)}"
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


def signal_list(block: Mapping[str, Any]) -> html.Div:
    """The signals by their groups against the main conclusion: forward, back and hold,
    then the open and the unmapped (decisions 35, 41); each its own anchor, which the
    same-source labels of 02 point to."""
    listed = _mappings(block.get("signals"))
    groups: list[Any] = [
        html.Div(
            [
                html.H3(MACRO_SIGNAL_GROUPS[group], className="macro-group-title"),
                html.Ul(
                    [
                        html.Li(describe(item), id=signal_anchor(item)[1:])
                        for item in listed
                        if item.get("group") == group
                    ],
                    className="macro-signal-list",
                ),
            ],
            className="macro-group",
        )
        for group in SIGNAL_GROUPS
        if any(item.get("group") == group for item in listed)
    ]
    return html.Div(
        [
            html.P(MACRO_SIGNAL_LIST, className="section-kicker"),
            *(groups or [html.P(MACRO_NO_SIGNALS, className="empty-note")]),
        ],
        className="macro-signals",
    )


def signal_anchor(item: Mapping[str, Any]) -> str:
    return f"#signal-{item.get('id')}"


def describe(item: Mapping[str, Any]) -> str:
    """A signal in one line: what it reads, the transition it supports, its maturity, and
    for one of the cores' own source that it never votes."""
    parts = [_reading(item)]
    transition = _transition(item)
    if transition:
        parts.append(transition)
    if item.get("maturity") in MACRO_MATURITIES:
        parts.append(MACRO_MATURITIES[str(item["maturity"])])
    if item.get("same_source"):
        parts.append(MACRO_SAME_SOURCE)
    return " · ".join(parts)


def pointer(item: Mapping[str, Any]) -> str:
    """How a same-source label of 02 names a signal: its subject and its group."""
    group = MACRO_SIGNAL_GROUPS.get(str(item.get("group")), "")
    momentum = _mapping(item.get("momentum"))
    if momentum:
        subject = str(momentum.get("label"))
    elif item.get("breadth"):
        subject = str(_mapping(item.get("breadth")).get("label"))
    else:
        turn = _mapping(item.get("asset_turn"))
        kind = "同类" if item.get("source") == "peers" else "核心候选"
        subject = f"{_asset(turn.get('asset'))}{kind}转{_state(turn.get('to'))}"
    return f"{subject}（{group}）"


def _reading(item: Mapping[str, Any]) -> str:
    source = item.get("source")
    if item.get("kind") == "divergence":
        return _divergence(item)
    if item.get("kind") == "hysteresis":
        # Decision 26: the run a new judgement stands, toward replacing the conclusion.
        return (
            f"倾向转向{stage_name(_mapping(item.get('transition')).get('to'))}"
            f"（已 {item.get('sessions')}/{item.get('sessions_required')} 日）"
        )
    if source == "relative_momentum":
        momentum = _mapping(item.get("momentum"))
        first, second = _pair_name(momentum.get("of")), _pair_name(momentum.get("against"))
        level = "强于" if momentum.get("level") == "up" else "弱于"
        moved = "走强" if momentum.get("turn") == "up" else "走弱"
        return (
            f"{momentum.get('label')}：{first}{level}{second} "
            f"{abs(float(momentum.get('value_pp') or 0)):.2f} 个百分点，"
            f"{momentum.get('turn_sessions')} 日{moved} "
            f"{abs(float(momentum.get('change_pp') or 0)):.2f} 个百分点"
        )
    if source in {"stock_breadth", "basket_breadth"}:
        breadth = _mapping(item.get("breadth"))
        detail = (
            f"站上 90 日均线 {float(breadth['share']):.1f}%"
            if isinstance(breadth.get("share"), (int, float))
            else f"{breadth.get('along')}/{breadth.get('of')} 个分项同向"
            if breadth.get("along") is not None
            else ""
        )
        return f"{breadth.get('label')}：{breadth.get('text')}" + (
            f"（{detail}）" if detail else ""
        )
    turn = _mapping(item.get("asset_turn"))
    asset, state = _asset(turn.get("asset")), CORE_STATE_LABELS.get(str(turn.get("state")), "")
    if source == "peers":
        peers = _mapping(item.get("peers"))
        against = [str(label) for label in peers.get("against") or ()]
        return (
            f"{asset}同类 {len(against)}/{peers.get('read')} 转{_state(turn.get('to'))}"
            f"（{'、'.join(against)}），与{asset}核心{state}背离"
        )
    candidates = _mapping(item.get("candidates"))
    named = []
    for kind in candidates.get("against") or ():
        if kind == "candidate_30d":
            named.append(f"30 日候选方向{_state(turn.get('to'))}")
        else:
            named.append(
                f"资产候选状态{_state(turn.get('to'))}（已 {candidates.get('candidate_days')} 日）"
            )
    return f"{asset}核心{'、'.join(named)}，与当前{state}相反"


def _transition(item: Mapping[str, Any]) -> str:
    """符合第三→第四阶段 for a cell's own transition; an asset flipped, what it makes."""
    if item.get("kind") in {"divergence", "hysteresis"}:
        return ""
    transition = _mapping(item.get("transition"))
    origin, target = transition.get("from"), transition.get("to")
    if target is None:
        return "翻转后为非典型组合"
    if origin is None:
        return f"翻转后为{stage_name(target)}"
    return f"符合{stage_name(origin).removesuffix('阶段')}→{stage_name(target)}"


def _divergence(item: Mapping[str, Any]) -> str:
    """PMI 分化：新订单上行（主成员下行）；若 PMI 改投少数方向，增长上行，判第三阶段（…）."""
    indicator, minority = _mapping(item.get("indicator")), _mapping(item.get("minority"))
    name = str(indicator.get("name"))
    head = (
        _spaced(name, "分化：")
        + "、".join(str(member) for member in minority.get("members") or ())
        + MACRO_VALUES.get(str(minority.get("direction")), MACRO_UNKNOWN)
        + f"（主成员{MACRO_VALUES.get(str(indicator.get('main_direction')), MACRO_UNKNOWN)}）"
    )
    rejudged = item.get("rejudged")
    if not isinstance(rejudged, Mapping):
        dimension = MACRO_DIMENSIONS.get(str(indicator.get("dimension")), "")
        return f"{head}；{dimension}维不由指标投票，不改判"
    recounted = _mapping(rejudged.get("dimension"))
    named = MACRO_DIMENSIONS.get(str(recounted.get("dimension")), "")
    joined = (
        f"若{name}按少数方向计入{named}维"
        if rejudged.get("joined")
        else "若" + (" " if name[:1].isascii() else "") + _spaced(name, "改投少数方向")
    )
    value = MACRO_VALUES.get(str(recounted.get("value")), MACRO_UNKNOWN)
    stage = rejudged.get("stage")
    judged = (
        f"判{stage_name(stage)}"
        f"（{MACRO_CONFIDENCES.get(str(rejudged.get('confidence')), '')}，"
        f"{rejudged.get('known')} 维中 {rejudged.get('matched')} 维吻合）"
        if stage is not None
        else "未达明确判断"
    )
    return f"{head}；{joined}，{named}{value}，{judged}"


def _pair_name(asset: object) -> str:
    """A pair's side as its label names it: 债 for the bond."""
    return "债" if asset == "bond" else _asset(asset)


def _asset(asset: object) -> str:
    return MACRO_ASSETS.get(str(asset), str(asset))


def _state(state: object) -> str:
    return CORE_STATE_LABELS.get(str(state), "")[:1]


def _spaced(name: str, word: str) -> str:
    """A name ending in Latin letters or digits takes a space before Chinese (PMI 下行)."""
    return f"{name} {word}" if name[-1:].isascii() else f"{name}{word}"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
