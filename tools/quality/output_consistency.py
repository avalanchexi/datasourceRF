"""Layer 3, first part: are the run's outputs consistent with each other?

SQL checks over the published projection and its report, not a recomputation of the trends
(ticket 04 does that): core states to formal stage through the frozen ``stage_mapping``, the
confirmation counts against the key indicators and their members, and the report's structured
conclusions against the projection. Each check states what it expects, independently derived
from the frozen manifest and the rules in ADR-0001, ADR-0037 and ``CONTEXT.md``, and what the
run stored. How by-sign members compare and how divergence caps a key indicator follow the
user's ruling on data quality audit ticket 12 (2026-10-10), recorded in ``CONTEXT.md``.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date

from common import Run, table

ASSETS = ("bond", "stock", "commodity")  # the order of ``stage_mapping`` keys
TRENDS = ("bull", "bear")
RELATIONS = ("support", "counterevidence", "observation_only", "unconfirmed", "not_applicable")
OK, BAD = "一致", "**不一致**"


@dataclass
class Check:
    group: str
    name: str
    expected: object
    actual: object

    @property
    def passed(self) -> bool:
        return self.expected == self.actual


def _short(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "…"


def _difference(expected, actual) -> str:
    """Where a failed comparison differs, so a long value is not cut before the difference."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        parts = [
            ("缺少的键", expected.keys() - actual.keys()),
            ("多出的键", actual.keys() - expected.keys()),
            (
                "值不同的键",
                {k for k in expected.keys() & actual.keys() if expected[k] != actual[k]},
            ),
        ]
        return "；".join(
            f"{label}：{'、'.join(sorted(map(str, keys)))}" for label, keys in parts if keys
        )
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"期望 {len(expected)} 项，实际 {len(actual)} 项：{_short(actual)}"
        at = [i for i, (e, a) in enumerate(zip(expected, actual, strict=True)) if e != a]
        return f"不同的位置：{'、'.join(map(str, at))}；第 {at[0]} 项实际为 {_short(actual[at[0]])}"
    return _short(actual)


def _p0(run: Run) -> dict:
    row = run.db.execute(
        "SELECT document_json FROM p0_assessment WHERE projection_set_id = ?",
        (run.projection_set_id,),
    ).fetchone()
    return json.loads(row[0]) if row else {}


def _report(run: Run) -> tuple[tuple, dict, dict] | None:
    """The newest report version bound to this projection, its body and frozen bundle."""
    row = run.db.execute(
        "SELECT report_snapshot_id, version, status, current_stage, bundle_id, bundle_hash,"
        " body_json FROM report_snapshot WHERE projection_set_id = ?"
        " ORDER BY version DESC LIMIT 1",
        (run.projection_set_id,),
    ).fetchone()
    if row is None:
        return None
    bundle = run.db.execute(
        "SELECT bundle_hash, projection_set_id, document_json FROM evidence_bundle"
        " WHERE bundle_id = ?",
        (row[4],),
    ).fetchone()
    document = json.loads(bundle[2]) if bundle else {}
    if bundle:
        document["_bundle_hash"], document["_projection_set_id"] = bundle[0], bundle[1]
    return row[:6], json.loads(row[6]), document


# --- formal stage -------------------------------------------------------------------------


def _stage_checks(run: Run, overview: dict, core: dict, p0: dict, macro: dict) -> list[Check]:
    group = "核心状态→正式阶段"
    assets = {a.get("asset"): a for a in core.get("assets", [])}
    states = tuple(assets.get(name, {}).get("state") for name in ASSETS)
    mapping = run.manifest.get("stage_mapping", {})
    if any(s not in TRENDS for s in states) or p0.get("gaps"):
        expected = (None, "core_data_pending")
    elif ",".join(states) in mapping:
        expected = (mapping[",".join(states)], "canonical_combination")
    else:
        expected = (None, "noncanonical_combination")
    stage = overview.get("current_stage")
    checks = [
        Check(
            group,
            "三核心资产与冻结的核心指标",
            run.manifest.get("core_metrics"),
            {name: assets.get(name, {}).get("metric_id") for name in ASSETS},
        ),
        Check(
            group,
            f"状态 {','.join(map(str, states))} 按 stage_mapping 得到的阶段与原因",
            list(expected),
            [stage, overview.get("stage_reason")],
        ),
        Check(
            group,
            "p0_assessment 的 event_kind（有当前阶段为 formal）",
            "formal" if stage else "gap",
            p0.get("event_kind"),
        ),
        Check(
            group,
            "沿用名单与资产 carried_forward 标记",
            [a for a in ASSETS if assets.get(a, {}).get("carried_forward")],
            overview.get("core_carry_forward"),
        ),
        Check(
            group,
            "沿用资产的 reason 都是沿用类（以 carried_forward 开头）",
            [],
            [
                a
                for a in ASSETS
                if assets.get(a, {}).get("carried_forward")
                and not str(assets[a].get("reason")).startswith("carried_forward")
            ],
        ),
        Check(
            group,
            "总览 core_assets 与核心数据集相同",
            core.get("assets"),
            overview.get("core_assets"),
        ),
        Check(
            group,
            "p0_assessment 的核心资产与核心数据集相同",
            core.get("assets"),
            p0.get("core_assets"),
        ),
    ]
    for field in ("current_stage", "stage_reason"):
        checks.append(
            Check(group, f"p0_assessment.{field} 与总览相同", overview.get(field), p0.get(field))
        )
    history = run.datasets.get("stage_history", {})
    events = history.get("events", [])
    own = [e for e in events if e.get("projection_set_id") == run.projection_set_id]
    checks.append(Check(group, "阶段史中本投影的事件", 1, len(own)))
    if own:
        checks.append(Check(group, "阶段史中本投影的事件与 p0_assessment 相同", p0, own[0]))
    # The assessed last confirmed stage: the current one, else the newest formal assessment
    # in the window's stage history, on or before the target date.
    formal = [
        e
        for e in events
        if e.get("event_kind") == "formal"
        and run.window[0] <= str(e.get("business_date", "")) <= run.target_date
    ]
    formal.sort(key=lambda e: (e["business_date"], e.get("system_as_of", ""), e["assessment_id"]))
    last = stage or (formal[-1].get("current_stage") if formal else None)
    checks.append(
        Check(
            group,
            "评估的上一确认阶段（当前阶段，否则窗口内阶段史中最近的正式评估）",
            last,
            p0.get("last_confirmed_stage"),
        )
    )
    checks += _lookback_checks(run, overview, history, last)
    conf = macro.get("confirmation", {})
    checks.append(
        Check(
            group,
            "确认度记录的阶段与原因同总览",
            [stage, overview.get("stage_reason")],
            [conf.get("stage"), conf.get("stage_reason")],
        )
    )
    envelope = run.envelope
    checks.append(
        Check(
            group,
            "投影信封的目标日、模型与截止同运行",
            [run.target_date, run.model_version_id, run.cutoff],
            [
                envelope.get("target_business_date"),
                envelope.get("model_version_id"),
                envelope.get("system_as_of"),
            ],
        )
    )
    return checks


LOOKBACK_STATUSES = ("found", "not_found", "failed")


def _lookback_checks(run: Run, overview: dict, history: dict, assessed) -> list[Check]:
    """The shown last confirmed stage and the lookback that may stand behind it (ADR-0040).

    The assessment keeps what the window's stage history says (``assessed``); the overview
    shows that, else the stage a lookback found. The lookback is published with both the
    overview and the stage history, and one that found nothing or failed gives no stage.
    """
    group = "核心状态→正式阶段"
    lookback = overview.get("last_confirmed_lookback")
    found = isinstance(lookback, dict) and lookback.get("status") == "found"
    checks = [
        Check(
            group,
            "回溯文档：总览与阶段史相同（或都没有）",
            lookback,
            history.get("last_confirmed_lookback"),
        ),
        Check(
            group,
            "展示的上一确认阶段（评估值，否则回溯找到的阶段）",
            assessed or (lookback.get("stage") if found else None),
            overview.get("last_confirmed_stage"),
        ),
    ]
    if lookback is None:
        return checks
    if not isinstance(lookback, dict):
        return [*checks, Check(group, "回溯文档是对象", "dict", type(lookback).__name__)]
    status = lookback.get("status")
    shape = []
    if lookback.get("source") != "lookback":
        shape.append(f"source={lookback.get('source')}")
    if status not in LOOKBACK_STATUSES:
        shape.append(f"status={status}")
    checks.append(Check(group, "回溯文档的来源为 lookback、状态为三种之一", [], shape))
    stage, day = lookback.get("stage"), lookback.get("stage_date")
    if found:
        start = run.window[0]
        low, high = lookback.get("searched_from"), lookback.get("searched_through")
        wrong = []
        stages = {v for v in run.manifest.get("stage_mapping", {}).values() if isinstance(v, str)}
        if not isinstance(stage, str) or stage not in stages:
            wrong.append(f"阶段 {stage} 不在 stage_mapping 中")
        if lookback.get("failure") is not None:
            wrong.append(f"failure={lookback.get('failure')}")
        if not all(_iso_date(d) for d in (day, low, high, start)):
            wrong.append(f"日期缺失或无效（阶段日 {day}、范围 {low}～{high}、窗口首日 {start}）")
        else:
            if not low <= day <= high:
                wrong.append(f"阶段日 {day} 不在搜索范围 {low}～{high} 内")
            if not day < start:
                wrong.append(f"阶段日 {day} 不早于窗口首日 {start}")
        checks.append(
            Check(group, "回溯找到的阶段：属于冻结映射、阶段日在搜索范围内且早于窗口", [], wrong)
        )
    elif status in LOOKBACK_STATUSES:
        given = [
            f"{k}={lookback.get(k)}" for k in ("stage", "stage_date") if lookback.get(k) is not None
        ]
        if status == "failed" and not lookback.get("failure"):
            given.append("failed 却没有 failure")
        checks.append(Check(group, f"回溯 {status} 时不给阶段（失败须注明原因）", [], given))
    return checks


def _iso_date(value) -> bool:
    """A calendar date written ``YYYY-MM-DD``, so such dates compare as text."""
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _lookback_note(overview: dict) -> str:
    lookback = overview.get("last_confirmed_lookback")
    if not isinstance(lookback, dict):
        return "本投影没有上一确认阶段的回溯文档（未触发回溯）。"
    g = lookback.get
    return (
        f"上一确认阶段回溯：{g('status')}，阶段 {g('stage') or '为空'}"
        f"（阶段日 {g('stage_date') or '—'}），搜索 {g('searched_from')}～{g('searched_through')}，"
        f"{g('years')} 年，核心请求 {g('core_requests')} 次、日历请求 {g('calendar_requests')} 次"
        + (f"，失败原因 {g('failure')}" if g("failure") else "")
        + "；年数与请求次数只列出，不核对。"
    )


# --- confirmation -------------------------------------------------------------------------


def _confirmation_checks(run: Run, overview: dict, macro: dict) -> tuple[list[Check], list[str]]:
    group = "确认度计数与成员读法"
    conf = macro.get("confirmation", {})
    dimensions = conf.get("dimensions", [])
    indicators = [ki for d in dimensions for ki in d.get("key_indicators") or []]
    frozen = run.manifest.get("confirmation_rules", {}).get("key_indicators", [])
    frozen_keys = sorted(str(k.get("key")) for k in frozen) if isinstance(frozen, list) else []
    stage = overview.get("current_stage")
    checks = [
        Check(
            group,
            "关键指标与冻结规则一致",
            frozen_keys,
            sorted(str(ki.get("key")) for ki in indicators),
        ),
        Check(group, "applicable 等于“当前阶段非空”", stage is not None, conf.get("applicable")),
        Check(
            group,
            "关系取值都在五种之内",
            [],
            sorted(map(str, {ki.get("relation") for ki in indicators} - set(RELATIONS))),
        ),
    ]
    if not conf.get("applicable"):
        checks.append(
            Check(
                group,
                "不适用时每个关键指标的关系都是 not_applicable",
                [],
                [ki.get("key") for ki in indicators if ki.get("relation") != "not_applicable"],
            )
        )
    for dimension in dimensions:
        tally = Counter(ki.get("relation") for ki in dimension.get("key_indicators") or [])
        expected = (
            None
            if dimension.get("status") == "not_connected"
            else {r: tally.get(r, 0) for r in RELATIONS}
        )
        checks.append(
            Check(
                group,
                f"维度 {dimension.get('dimension')} 的计数等于其关键指标关系的统计",
                expected,
                dimension.get("counts"),
            )
        )
    # Member readings. The frozen rule names each indicator's main and auxiliary members; a
    # member whose direction is opposite to the main one's opposes it, which makes the
    # indicator divergent, and a divergent indicator cannot rise above "observation only"
    # (CONTEXT, key indicator; ADR-0037).
    rules = {k.get("key"): k for k in frozen} if isinstance(frozen, list) else {}
    uncovered, unlabelled, mislabelled, extra_mains = [], [], [], []
    for ki in indicators:
        members = ki.get("members") or []
        have = {_member_id(m.get("metric_id"), m.get("member")) for m in members}
        for metric, dims, is_main in _frozen_members(rules.get(ki.get("key"), {})):
            if _member_id(metric, dims) not in have:
                uncovered.append(f"{ki.get('key')}:{metric}{_short(dims or {})}")
            elif is_main and not any(
                m.get("consistency") == "main"
                and _member_id(m.get("metric_id"), m.get("member")) == _member_id(metric, dims)
                for m in members
            ):
                unlabelled.append(f"{ki.get('key')}:{metric}")
        rule = rules.get(ki.get("key"), {})
        if rule.get("quadrant") or not rule.get("main"):
            continue  # the inventory quadrant reads three lines, each with its own main
        frozen_main = _member_id(
            rule["main"].get("metric_id") or rule.get("metric_id"), rule["main"].get("dimensions")
        )
        mains = [
            m for m in members if _member_id(m.get("metric_id"), m.get("member")) == frozen_main
        ]
        extra_mains += [
            f"{ki.get('key')}:{m.get('metric_id')}{_short(m.get('member') or {})}"
            for m in members
            if m.get("consistency") == "main" and m not in mains
        ]
        if not mains:
            continue
        main = mains[0].get("momentum")
        for m in members:
            if m is mains[0] or m.get("agrees_by") != "momentum":
                continue
            if m.get("evidence_status") != "current" or m.get("consistency") == "not_compared":
                continue
            opposite = {main, m.get("momentum")} == {"up", "down"}
            if opposite != (m.get("consistency") == "opposes"):
                mislabelled.append(
                    f"{ki.get('key')}:{m.get('metric_id')}{_short(m.get('member') or {})}"
                    f" 主 {main}／成员 {m.get('momentum')}／标 {m.get('consistency')}"
                )
    checks += [
        Check(group, "冻结的主要与辅助成员都已展开", [], uncovered),
        Check(group, "冻结的主要成员标为 main", [], unlabelled),
        Check(group, "冻结主要成员以外没有标为 main 的成员（库存象限除外）", [], extra_mains),
        Check(group, "按动量比较的成员：方向与主要成员相反当且仅当标为 opposes", [], mislabelled),
    ]
    readings = [_read_members(ki, rules.get(ki.get("key"), {})) for ki in indicators]
    checks += _sign_checks(group, indicators, readings)
    quadrant_checks, quadrant_notes = _quadrant_checks(group, indicators, rules)
    checks += quadrant_checks
    opposed = [
        ki
        for ki in indicators
        if any(m.get("consistency") == "opposes" for m in ki.get("members") or [])
    ]
    judged = [
        (ki, r)
        for ki, r in zip(indicators, readings, strict=True)
        if r is not None and r.divergent is not None
    ]
    found = sorted(ki.get("key") for ki, r in judged if r.divergent)
    divergent = set(found) | {ki.get("key") for ki in opposed}
    checks += [
        Check(
            group,
            "有成员与主要成员相反的关键指标未标为一致",
            [],
            [ki.get("key") for ki in opposed if ki.get("consistency") == "consistent"],
        ),
        Check(
            group,
            "分化（consistency = divergent）当且仅当按成员方向独立判为分化",
            found,
            sorted(ki.get("key") for ki, _ in judged if ki.get("consistency") == "divergent"),
        ),
        Check(
            group,
            "分化封顶：分化的关键指标既不算 support 也不算 counterevidence",
            [],
            [
                f"{ki.get('key')}:{ki.get('relation')}"
                for ki in indicators
                if ki.get("key") in divergent
                and ki.get("relation") in ("support", "counterevidence")
            ],
        ),
        Check(
            group,
            "计入（support／counterevidence）的关键指标没有指标级缺失",
            [],
            [
                ki.get("key")
                for ki in indicators
                if ki.get("relation") in ("support", "counterevidence") and ki.get("missing")
            ],
        ),
    ]
    signed = [m for r in readings if r for m in r.signed]
    notes = [
        f"按符号比较：{len(signed)} 个成员（贷款与社融的当月增量同比差），核对读法（同比差正负"
        "→方向、水平线上下）与成员比较标注；同比差的取值由第二层“规则级公式”重算核对，"
        "取值所依据的声明本身对不对（如票 06）不在核对之内。",
        *quadrant_notes,
    ]
    relations = {ki.get("relation") for ki in indicators if ki.get("key") in divergent}
    if not conf.get("applicable") and relations <= {"not_applicable"}:
        by_label = sorted(divergent - set(found))
        notes.append(
            f"分化封顶：确认度不适用（{conf.get('stage_reason')}），分化的关键指标关系都是"
            " not_applicable，封顶本身没有被触发，只核到分化识别这一层：独立判为分化的"
            f" {len(found)} 项（{'、'.join(found) or '无'}）"
            + (f"，另按成员标注计入 {'、'.join(by_label)}" if by_label else "")
            + "。"
        )
    return checks, notes


# Members read by the sign of a derived change of the month's increment against the same
# month a year earlier: the nine loan members and the social financing increment. Positive is
# up, negative down, zero flat (data quality audit ticket 12, user ruling 2026-10-10).
SIGN_FORMULAS = frozenset(
    {"loan-monthly-increment-yoy-change-v0001", "sf-monthly-increment-yoy-change-v0001"}
)
DIRECTIONS = ("up", "down", "flat")


def _sign(value) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return "up" if value > 0 else "down" if value < 0 else "flat"


@dataclass
class Reading:
    """One key indicator's members read independently against its frozen rule."""

    main_direction: str | None  # None also when the frozen main member is not among them
    divergent: bool | None  # None when the frozen main member is not among the members
    signed: list[tuple[dict, dict, bool]]  # (member, frozen entry, is_main), compared by sign
    level_line: float | None


def _read_members(ki: dict, rule: dict) -> Reading | None:
    """Each member's direction (momentum, or the sign of the derived change for a by-sign
    member; unknown unless current) against the frozen main member's. Members the rule marks
    ``compared: false`` take no part. The inventory quadrant compares by line instead."""
    if rule.get("quadrant"):
        found = _read_quadrant(ki, rule)
        known = found is not None and found.quadrant[3] != "insufficient"
        return Reading(None, "opposes" in found.labels.values() if known else None, [], None)
    if not rule.get("main"):
        return None
    entries = {}
    for entry, is_main in [(rule["main"], True)] + [(a, False) for a in rule.get("auxiliary", [])]:
        key = _member_id(entry.get("metric_id") or rule.get("metric_id"), entry.get("dimensions"))
        entries[key] = (entry, is_main)
    members = [
        (m, *entries[key])
        for m in ki.get("members") or []
        if (key := _member_id(m.get("metric_id"), m.get("member"))) in entries
    ]
    main = next(((m, e) for m, e, is_main in members if is_main), None)

    def direction(member: dict, entry: dict) -> str | None:
        if member.get("evidence_status") != "current":
            return None
        by_sign = entry.get("formula") in SIGN_FORMULAS
        found = _sign(member.get("value")) if by_sign else member.get("momentum")
        return found if found in DIRECTIONS else None

    main_direction = direction(*main) if main else None
    divergent = None
    if main:
        divergent = main_direction is not None and any(
            {main_direction, direction(m, e)} == {"up", "down"}
            for m, e, is_main in members
            if not is_main and e.get("compared") is not False
        )
    signed = [(m, e, is_main) for m, e, is_main in members if e.get("formula") in SIGN_FORMULAS]
    return Reading(main_direction, divergent, signed, rule.get("level_line"))


def _sign_checks(group: str, indicators: list[dict], readings: list) -> list[Check]:
    """By-sign members: which members they are, how the derived change reads, and how each
    compares with the main member (unknown or stale: ``not_compared``)."""
    expected_scope, scope, misread, level, mislabelled = [], [], [], [], []
    for ki, reading in zip(indicators, readings, strict=True):
        scope += [
            f"{ki.get('key')}:{m.get('name')}"
            for m in ki.get("members") or []
            if m.get("agrees_by") == "sign"
        ]
        if reading is None:
            continue
        for m, entry, is_main in reading.signed:
            name = f"{ki.get('key')}:{m.get('name')}"
            expected_scope.append(name)
            value, sign = m.get("value"), _sign(m.get("value"))
            stored = m.get("direction")
            if (sign and stored != sign) or (sign is None and stored in DIRECTIONS):
                misread.append(f"{name} 值 {value}／方向 {stored}")
            line = reading.level_line
            beside = sign and line is not None and value != line
            if beside and m.get("level") != ("above" if value > line else "below"):
                level.append(f"{name} 值 {value}／水平线 {line}／标 {m.get('level')}")
            if is_main or entry.get("compared") is False:
                continue  # the main member is labelled main; an uncompared member is shown only
            mine = sign if m.get("evidence_status") == "current" else None
            label = m.get("consistency")
            if mine is None:
                wrong = label != "not_compared"
            elif reading.main_direction is None:
                wrong = label == "opposes"
            else:
                opposite = {reading.main_direction, mine} == {"up", "down"}
                wrong = opposite != (label == "opposes") or label == "not_compared"
            if wrong:
                mislabelled.append(
                    f"{name} 主 {reading.main_direction}／成员 {mine}"
                    f"（{m.get('evidence_status')}）／标 {label}"
                )
    return [
        Check(
            group,
            "按符号比较的成员恰为冻结规则中当月增量同比差的成员（贷款、社融增量）",
            sorted(expected_scope),
            sorted(scope),
        ),
        Check(
            group, "按符号比较的成员：方向等于同比差的正负（正 up、负 down、零 flat）", [], misread
        ),
        Check(group, "按符号比较的成员：有水平线时 level 与同比差在线上下一致", [], level),
        Check(
            group,
            "按符号比较的成员：未知或过期标 not_compared；可比时与主要成员相反当且仅当标 opposes",
            [],
            mislabelled,
        ),
    ]


# --- inventory quadrant -------------------------------------------------------------------
# Three lines, each with a main member and auxiliary ones; demand and inventory name the
# quadrant, production verifies it. The rules as production reads them were written into
# the audit document from the 2026-10-11 interview (model rules ticket 05, Q10).

QUADRANT_LINES = ("demand", "production", "inventory")


def _momentum(values) -> str | None:
    """The newer of the two months against the older: up, down or flat; unknown with
    fewer than two numeric values."""
    if not isinstance(values, list) or len(values) < 2:
        return None
    previous, value = values[-2], values[-1]
    if any(
        isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v)
        for v in (previous, value)
    ):
        return None
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    return (
        "up" if value - previous > tolerance else "down" if previous - value > tolerance else "flat"
    )


def _auxiliary(part: dict) -> list:
    found = part.get("auxiliary") or []
    return found if isinstance(found, list) else []


def _month_back(month: str) -> str:
    year, number = int(month[:4]), int(month[5:7])
    return f"{year - 1:04d}-12" if number == 1 else f"{year:04d}-{number - 1:02d}"


@dataclass
class QuadrantRead:
    """The inventory quadrant read independently from its members' values."""

    month: str | None  # YYYY-MM, from the quadrant member's period
    before: str | None
    entries: dict[str, tuple[str, bool, dict]]  # member name -> (line, is_main, frozen entry)
    members: dict[str, dict]  # member name -> projected member
    directions: dict[str, str | None]  # member name -> recomputed momentum
    labels: dict[str, str]  # member name -> expected consistency
    quadrant: tuple  # expected (evidence_status, missing, quadrant, unclassified_by)
    head: dict | None  # the quadrant member itself


def _read_quadrant(ki: dict, rule: dict) -> QuadrantRead | None:
    """Each line's members read at the quadrant's month and the one before it; each
    auxiliary member against its line's main member; the quadrant the main members'
    directions name. None when the frozen rule does not name the three lines, each with a
    main member, and every member by a name of its own."""
    lines = (rule.get("quadrant") or {}).get("lines") or {}
    if set(lines) != set(QUADRANT_LINES) or not all(
        isinstance(part, dict)
        and isinstance(part.get("auxiliary", []), list)
        and all(isinstance(entry, dict) for entry in [part.get("main")] + _auxiliary(part))
        for part in lines.values()
    ):
        return None
    entries, by_id = {}, {}
    for line in QUADRANT_LINES:
        part = lines[line]
        for entry, is_main in [(part["main"], True)] + [(a, False) for a in _auxiliary(part)]:
            entries[entry.get("name")] = (line, is_main, entry)
            metric = entry.get("metric_id") or rule.get("metric_id")
            by_id[_member_id(metric, entry.get("dimensions"))] = entry.get("name")
    named = sum(1 + len(_auxiliary(lines[line])) for line in QUADRANT_LINES)
    if len(entries) != named or not all(isinstance(n, str) and n for n in entries):
        return None
    members = {}
    head = None
    for m in ki.get("members") or []:
        if m.get("name") == "quadrant" and not m.get("member"):
            head = m
        elif (name := by_id.get(_member_id(m.get("metric_id"), m.get("member")))) is not None:
            members.setdefault(name, m)
    period = (head or {}).get("period")
    month = period[:7] if isinstance(period, str) else None
    skipped = set()
    for line in QUADRANT_LINES:
        skipped |= set(lines[line]["main"].get("unreleased_months") or [])
    before = None
    if month is not None:
        before = _month_back(month)
        while int(before[5:7]) in skipped:
            before = _month_back(before)
    directions = {name: _momentum(m.get("values")) for name, m in members.items()}
    mains = {line: name for name, (line, is_main, _) in entries.items() if is_main}
    labels = {"quadrant": "main"}
    for name, (line, is_main, _) in entries.items():
        if name not in members:
            continue
        if is_main:
            labels[name] = "main"
            continue
        mine, main = directions[name], directions.get(mains[line])
        if members[name].get("evidence_status") != "current" or mine is None or main is None:
            labels[name] = "unknown"
        elif mine == main:
            labels[name] = "agrees"
        elif "flat" in (mine, main):
            labels[name] = "flat"
        else:
            labels[name] = "opposes"
    status, missing = "current", []
    for line in QUADRANT_LINES:
        m = members.get(mains[line], {})
        dims = ",".join(f"{k}={v}" for k, v in sorted((m.get("member") or {}).items()))
        label = dims or mains[line]
        own = m.get("evidence_status")
        if own != "current":
            missing.append(f"{line}:{label}:{own}")
            status = own if status == "current" else status
        missing += [f"{line}:{label}:{gap}" for gap in m.get("missing") or []]
    missing = list(dict.fromkeys(missing))
    named = {line: directions.get(mains[line]) for line in QUADRANT_LINES}
    if missing or status != "current" or None in named.values():
        quadrant = (status, missing, "unclassified", "insufficient")
    else:
        table_of = (rule.get("quadrant") or {}).get("quadrants") or {}
        name = next((q for q, d in table_of.items() if d == named), None)
        quadrant = (status, missing, name or "unclassified", None if name else "inconsistent")
    return QuadrantRead(month, before, entries, members, directions, labels, quadrant, head)


def _quadrant_checks(group: str, indicators: list[dict], rules: dict) -> tuple[list[Check], list]:
    """The inventory quadrant's lines: months, directions, the quadrant, how each auxiliary
    member compares with its line's main member, and whether the indicator is divergent."""
    checks, notes = [], []
    for ki in indicators:
        rule = rules.get(ki.get("key"), {})
        if not rule.get("quadrant"):
            continue
        q = _read_quadrant(ki, rule)
        key = ki.get("key")
        if q is None:
            name = f"库存象限 {key}：冻结规则恰有三条线、各有主成员、成员名称不重"
            checks.append(Check(group, name, True, False))
            continue
        expect_months = [q.before, q.month] if q.month else []
        misaligned = []
        for name, m in q.members.items():
            held = [str(p)[:7] for p in m.get("periods") or []] + list(m.get("missing") or [])
            if held and sorted(held) != expect_months:
                misaligned.append(f"{name} {sorted(held)}")
        misread = [
            f"{name} 值 {m.get('values')}／重算 {q.directions[name]}"
            f"／momentum {m.get('momentum')}／direction {m.get('direction')}"
            f"／agrees_by {m.get('agrees_by')}"
            for name, m in q.members.items()
            if m.get("momentum") != q.directions[name]
            or m.get("direction") != q.directions[name]
            or m.get("agrees_by") != "momentum"
        ]
        mains = {line: n for n, (line, is_main, _) in q.entries.items() if is_main}
        head = q.head or {}
        expected_lines = {
            line: {
                "member": mains[line],
                "label": q.entries[mains[line]][2].get("label"),
                "period": q.members.get(mains[line], {}).get("period"),
                "direction": q.directions.get(mains[line]),
            }
            for line in QUADRANT_LINES
        }
        stored = {name: [m.get("line"), m.get("consistency")] for name, m in q.members.items()} | {
            "quadrant": [head.get("line"), head.get("consistency")]
        }
        expected = {
            name: [q.entries[name][0] if name in q.entries else None, label]
            for name, label in q.labels.items()
        }
        known = q.quadrant[3] != "insufficient"
        opposes = sorted(n for n, label in q.labels.items() if label == "opposes")
        consistency = "unknown" if not known else "divergent" if opposes else "consistent"
        checks += [
            Check(
                group,
                f"库存象限 {key}：象限成员存在且不带取值",
                [True, []],
                [q.head is not None, head.get("values")],
            ),
            Check(
                group,
                f"库存象限 {key}：各线成员只读象限月 {q.month} 与前一象限月 {q.before}",
                [],
                misaligned,
            ),
            Check(
                group,
                f"库存象限 {key}：各成员按动量比较，动量按两期取值重算，"
                "与 momentum、direction 相同",
                [],
                misread,
            ),
            Check(group, f"库存象限 {key}：象限成员的三线读数", expected_lines, head.get("lines")),
            Check(
                group,
                f"库存象限 {key}：象限（证据状态、缺项、象限、未分类原因）",
                list(q.quadrant),
                [
                    head.get("evidence_status"),
                    head.get("missing"),
                    head.get("quadrant"),
                    head.get("unclassified_by"),
                ],
            ),
            Check(
                group,
                f"库存象限 {key}：辅成员与本线主成员比较（主成员与象限标 main）",
                expected,
                stored,
            ),
            Check(
                group,
                f"库存象限 {key}：分化识别（象限未知 unknown，有辅成员相反 divergent）",
                consistency,
                ki.get("consistency"),
            ),
        ]
        directions = "／".join(
            f"{line} {expected_lines[line]['direction']}" for line in QUADRANT_LINES
        )
        compared = "、".join(f"{n} {label}" for n, label in q.labels.items() if label != "main")
        notes.append(
            f"库存象限 {key}：象限月 {q.month or '无'}（前一象限月 {q.before or '无'}），"
            f"三线方向 {directions}，独立判为 {q.quadrant[2]}"
            + (f"（{q.quadrant[3]}）" if q.quadrant[3] else "")
            + f"；辅成员比较 {compared or '无'}；分化识别为 {consistency}，"
            "不沿用系统的成员标注。"
        )
    return checks, notes


def _member_id(metric, dims) -> tuple:
    return metric, json.dumps(dims or {}, sort_keys=True, ensure_ascii=False)


def _frozen_members(rule: dict) -> list[tuple]:
    """(metric, dimensions, is_main) of the members a frozen key indicator names; the
    inventory quadrant names them per line."""
    parts = [rule]
    parts += list(((rule.get("quadrant") or {}).get("lines") or {}).values())
    found = []
    for part in parts:
        if not isinstance(part, dict):
            continue  # a malformed quadrant line is reported by the quadrant checks
        for member, is_main in [(part.get("main"), True)] + [(a, False) for a in _auxiliary(part)]:
            if isinstance(member, dict) and member:
                metric = member.get("metric_id") or rule.get("metric_id")
                found.append((metric, member.get("dimensions"), is_main))
    return found


# --- report -------------------------------------------------------------------------------


def _report_checks(run: Run, overview: dict, core: dict, macro: dict, p0: dict) -> list[Check]:
    group = "报告与投影"
    found = _report(run)
    if found is None:
        return [Check(group, "本投影有报告快照", "有", "无")]
    (report_id, version, status, column_stage, bundle_id, bundle_hash), body, bundle = found
    conf = macro.get("confirmation", {})
    dimensions = conf.get("dimensions", [])
    indicators = [ki for d in dimensions for ki in d.get("key_indicators") or []]
    states = {a.get("asset"): str(a.get("state")) for a in core.get("assets", [])}
    conclusions = {"confirmation_applicable": conf.get("applicable")}
    for d in dimensions:
        conclusions[f"dimension:{d.get('dimension')}"] = (
            d.get("counts") if d.get("status") != "not_connected" else d.get("status")
        )
    conclusions |= {f"key_indicator:{ki.get('key')}": ki.get("relation") for ki in indicators}
    identity = body.get("report_identity", {})
    basis = body.get("formal_stage_basis", {})
    results = body.get("verified_results", {})
    formal = results.get("formal_stage", {})
    stage = overview.get("current_stage")
    gap_list = overview.get("gap_list") or []
    name = f"{report_id}（第 {version} 版，{status}）"
    checks = [
        Check(
            group,
            f"报告 {name} 已完成（completed 或降级完成 completed_degraded）",
            True,
            status in ("completed", "completed_degraded"),
        ),
        Check(
            group,
            "报告身份（投影、模型、目标日、趋势规则、截止）",
            [
                run.projection_set_id,
                run.model_version_id,
                run.target_date,
                run.envelope.get("trend_rule_version"),
                run.cutoff,
            ],
            [
                identity.get("projection_set_id"),
                identity.get("model_version_id"),
                identity.get("target_business_date"),
                identity.get("trend_rule_version"),
                identity.get("report_cutoff"),
            ],
        ),
        Check(
            group,
            "冻结证据包属于本投影、哈希相同",
            [run.projection_set_id, bundle_hash],
            [bundle.get("_projection_set_id"), bundle.get("_bundle_hash")],
        ),
        Check(group, "report_snapshot.current_stage 列与总览相同", stage, column_stage),
        Check(
            group,
            "formal_stage_basis 与总览相同",
            [stage, overview.get("stage_reason"), "three_core_price_states_only"],
            [
                basis.get("current_stage"),
                basis.get("stage_reason"),
                basis.get("classification_source"),
            ],
        ),
        Check(group, "core_states 与核心资产状态相同", states, body.get("core_states")),
        Check(
            group,
            "结构化结论（确认度适用、维度计数、关键指标关系）与投影相同",
            conclusions,
            body.get("conclusions"),
        ),
        Check(group, "gap_list 与总览相同", gap_list, body.get("gap_list")),
        Check(
            group,
            "core_carry_forward 与总览相同",
            overview.get("core_carry_forward"),
            body.get("core_carry_forward"),
        ),
        Check(
            group,
            "已验证结果的正式阶段（值、原因、上一确认、变化）",
            [
                stage,
                overview.get("stage_reason"),
                overview.get("last_confirmed_stage"),
                p0.get("event_kind"),
            ],
            [
                formal.get("value"),
                formal.get("reason"),
                formal.get("last_confirmed_stage"),
                formal.get("change"),
            ],
        ),
        Check(
            group,
            "已验证结果的核心资产状态",
            {a.get("asset"): a.get("state") for a in core.get("assets", [])},
            {a.get("asset"): a.get("value") for a in results.get("core_assets", [])},
        ),
        Check(
            group,
            "已验证结果的确认度（适用、阶段、原因、关键指标关系）",
            [
                conf.get("applicable"),
                conf.get("stage"),
                conf.get("stage_reason"),
                {ki.get("key"): ki.get("relation") for ki in indicators},
            ],
            [
                results.get("confirmation", {}).get("applicable"),
                results.get("confirmation", {}).get("stage"),
                results.get("confirmation", {}).get("stage_reason"),
                {
                    k: v.get("relation")
                    for k, v in results.get("confirmation", {}).get("key_indicators", {}).items()
                },
            ],
        ),
        Check(
            group,
            "已验证结果的缺口计数与总览 gap_list 分类统计",
            dict(Counter(g.get("category") for g in gap_list)),
            results.get("gap_summary", {}).get("counts"),
        ),
        Check(group, "已验证结果与冻结证据包的 results 相同", bundle.get("results"), results),
        Check(
            group,
            "冻结证据包的阶段、原因、核心状态与结论同报告",
            [stage, overview.get("stage_reason"), body.get("core_states"), body.get("conclusions")],
            [
                bundle.get("current_stage"),
                bundle.get("stage_reason"),
                bundle.get("core_states"),
                bundle.get("conclusions"),
            ],
        ),
    ]
    if status == "completed":  # a degraded report has no AI explanation to verify
        checks.append(
            Check(
                group,
                "报告自检的身份与结论校验",
                "passed",
                (body.get("explanation_verification") or {}).get("identity_and_conclusions"),
            )
        )
    return checks


def section(run: Run) -> str:
    out = ["## 第三层（一）：输出内部一致性", ""]
    if not run.projection_set_id:
        return "\n".join([*out, "本运行没有投影，无法核对。", ""])
    overview = run.datasets.get("cycle_overview", {})
    core = run.datasets.get("core_assets", {})
    macro = run.datasets.get("macro", {})
    p0 = _p0(run)
    confirmation, notes = _confirmation_checks(run, overview, macro)
    checks = [
        *_stage_checks(run, overview, core, p0, macro),
        *confirmation,
        *_report_checks(run, overview, core, macro, p0),
    ]
    failed = [c for c in checks if not c.passed]
    states = ", ".join(f"{a.get('asset')} {a.get('state')}" for a in core.get("assets", []))
    out += [
        "### 结论",
        "",
        f"- 投影 {run.projection_set_id}：{states}；当前阶段"
        f" {overview.get('current_stage') or '为空'}（{overview.get('stage_reason')}），"
        f"上一确认阶段 {overview.get('last_confirmed_stage') or '为空'}。",
        f"- {_lookback_note(overview)}",
        f"- 共 {len(checks)} 项检查，一致 {len(checks) - len(failed)}，不一致 {len(failed)}"
        + ("：" + "；".join(f"{c.group}／{c.name}" for c in failed) if failed else "")
        + "。",
        *(f"- {note}" for note in notes),
        "",
        "### 已知局限",
        "",
        "- 确认度在典型组合下尚无真实数据验证（2026-10-11 访谈 Q12）：到目前为止，真实运行都是"
        "非典型组合，确认度不适用。本节对确认度只核计数、成员读法、分化识别与封顶，不核关系是否"
        "符合各阶段的预期（预期表的格子、宽限、转折提示）。"
        + (
            "本运行确认度适用，以上各项照常核对，预期表的对应仍未核。"
            if macro.get("confirmation", {}).get("applicable")
            else f"本运行同样不适用（{macro.get('confirmation', {}).get('stage_reason')}）。"
        ),
        "",
        "### 明细",
        "",
    ]
    rows = [
        [
            c.group,
            c.name,
            _short(c.expected),
            _difference(c.expected, c.actual)
            if not c.passed
            else "同期望"
            if len(_short(c.expected)) > 40
            else _short(c.actual),
            OK if c.passed else BAD,
        ]
        for c in checks
    ]
    out += [table(["分组", "检查", "期望", "实际", "结论"], rows), ""]
    return "\n".join(out)
