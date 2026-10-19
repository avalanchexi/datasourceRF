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
from pring_cycle.macro_judgement import GROUPS
from pring_cycle.macro_signals import GROUPS as SIGNAL_GROUPS
from pring_cycle.macro_verification import ASSETS as VERIFIED_ASSETS
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
    stage_name,
)

_ACTIONS = {"cut": "下调", "hike": "上调"}
_UNREAD_POLICY = "政策利率、LPR、降准均无可读记录"
_NO_ACTION = "120 日内无降息、LPR 下调、降准或上调"
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
    actual = _combination(_mapping(verification.get("combination")))
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
    unread = [_asset(asset) for asset in VERIFIED_ASSETS if combination.get(asset) is None]
    deviations = "、".join(_asset(asset) for asset in verification.get("deviations") or ())
    found = [
        *([f"{deviations}偏离"] if deviations else []),
        *([f"{'、'.join(unread)}不可用，未比对"] if unread else []),
    ]
    return (
        f"{head} · {stage_name(verification.get('expected_stage'))}预期："
        f"{_combination(expected)} · " + ("；".join(found) or "一致")
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


def _combination(combination: Mapping[str, Any]) -> str:
    return " · ".join(
        _asset(asset) + CORE_STATE_LABELS.get(str(combination.get(asset)), "不可用")
        for asset in VERIFIED_ASSETS
    )


def title(conclusion: Mapping[str, Any], block: Mapping[str, Any]) -> str:
    """宏观判断：第 N 阶段（明确，5 维中 k 维吻合）· 相对上次确认第 M 阶段 前进 n 步."""
    stage = conclusion.get("stage")
    if stage is None:
        return f"{MACRO_JUDGEMENT}：未达明确判断（{_undecided(_mapping(block.get('raw')))}）"
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


def _undecided(raw: Mapping[str, Any]) -> str:
    if raw.get("basis") == "tied":
        tied = "、".join(stage_name(stage) for stage in raw.get("tied") or ())
        return f"{tied}并列，各 {raw.get('matched')} 维"
    return f"已知 {raw.get('known')} 维，最高 {raw.get('matched')} 维吻合"


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
            return f"{indicator.get('name') or '库存象限'}未分类"
        divergent = "（辅助成员分化）" if indicator.get("divergent") else ""
        return f"{indicator.get('name')} {indicator.get('period')}{divergent}"
    votes = "；".join(
        _spaced(
            str(indicator.get("name") or indicator.get("key")),
            MACRO_VALUES.get(str(indicator.get("vote")), MACRO_UNKNOWN),
        )
        + ("（分化）" if indicator.get("divergent") else "")
        for indicator in indicators
        if indicator.get("voting")
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
    lead = {"short_of_half": "明确者不足半数：", "tied": "多数决打平："}.get(reason, "")
    return lead + votes


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
    if item.get("kind") == "divergence":
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
