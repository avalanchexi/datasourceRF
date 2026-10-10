"""Layer 3, first part: are the run's outputs consistent with each other?

SQL checks over the published projection and its report, not a recomputation of the trends
(ticket 04 does that): core states to formal stage through the frozen ``stage_mapping``, the
confirmation counts against the key indicators and their members, and the report's structured
conclusions against the projection. Each check states what it expects, independently derived
from the frozen manifest and the rules in ADR-0001, ADR-0037 and ``CONTEXT.md``, and what the
run stored.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

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
    for field in ("current_stage", "stage_reason", "last_confirmed_stage"):
        checks.append(
            Check(group, f"p0_assessment.{field} 与总览相同", overview.get(field), p0.get(field))
        )
    events = run.datasets.get("stage_history", {}).get("events", [])
    own = [e for e in events if e.get("projection_set_id") == run.projection_set_id]
    checks.append(Check(group, "阶段史中本投影的事件", 1, len(own)))
    if own:
        checks.append(Check(group, "阶段史中本投影的事件与 p0_assessment 相同", p0, own[0]))
    # The last confirmed stage: the current one, else the newest formal assessment on or
    # before the target date in the stage history.
    formal = [
        e
        for e in events
        if e.get("event_kind") == "formal" and e.get("business_date", "") <= run.target_date
    ]
    formal.sort(key=lambda e: (e["business_date"], e.get("system_as_of", ""), e["assessment_id"]))
    last = stage or (formal[-1].get("current_stage") if formal else None)
    checks.append(
        Check(
            group,
            "上一确认阶段（当前阶段，否则阶段史中最近的正式评估）",
            last,
            overview.get("last_confirmed_stage"),
        )
    )
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
    opposed = [
        ki
        for ki in indicators
        if any(m.get("consistency") == "opposes" for m in ki.get("members") or [])
    ]
    checks += [
        Check(
            group,
            "有成员与主要成员相反的关键指标未标为一致",
            [],
            [ki.get("key") for ki in opposed if ki.get("consistency") == "consistent"],
        ),
        Check(
            group,
            "分化的关键指标关系不是 support",
            [],
            [ki.get("key") for ki in opposed if ki.get("relation") == "support"],
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
    notes = []
    if any(ki.get("relation") == "counterevidence" for ki in opposed):
        notes.append(
            "有分化的关键指标记为 counterevidence。“不高于仅观察”是否也排除反证，规则文档"
            "没有写明，本脚本不判定。"
        )
    return checks, notes


def _member_id(metric, dims) -> tuple:
    return metric, json.dumps(dims or {}, sort_keys=True, ensure_ascii=False)


def _frozen_members(rule: dict) -> list[tuple]:
    """(metric, dimensions, is_main) of the members a frozen key indicator names; the
    inventory quadrant names them per line."""
    parts = [rule]
    parts += list((rule.get("quadrant") or {}).get("lines", {}).values())
    found = []
    for part in parts:
        for member, is_main in [(part.get("main"), True)] + [
            (a, False) for a in part.get("auxiliary") or []
        ]:
            if member:
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
        f"- 共 {len(checks)} 项检查，一致 {len(checks) - len(failed)}，不一致 {len(failed)}"
        + ("：" + "；".join(f"{c.group}／{c.name}" for c in failed) if failed else "")
        + "。",
        *(f"- {note}" for note in notes),
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
