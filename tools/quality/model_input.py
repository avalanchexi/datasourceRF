"""Layer 2: was the model's input complete?

Lists every model input the run's final plan found missing, per metric x period x member, with
the reason from layer 1 and from the run's own receipts, and reports the four denominators the
system keeps apart: final plan rows, frozen input ids, confirmation members, batch freshness.
A value one period behind (carried forward) counts as complete. Core input ids that no longer
join a stored claim (the retention exception) are listed as a broken trace, not as missing;
those rebuilt exactly from the run's core receipts (``core_trace``) are marked verified.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

import acquisition
import core_trace
from acquisition import BEIJING, HELD, UNCOVERED, WARRANTS, scope_label
from common import Run, iso_day, parse_time, table

CONFIRMATION_STATUSES = ("current", "stale", "missing")
LATE_PUBLIC = "已持有，公开时间晚于目标日"
HELD_NO_PUBLIC = "已持有，无公开时间"
HELD_UNEXPLAINED = "已持有，原因不明"
NO_CLAIM = "无声明"
# Requests settled without a receipt (ticket 11): held back by the ledger, or not asked again.
NEGATIVE_CACHE = "negative_cache_active"
EMPTY_IN_ANSWER = "warrant_day_empty_in_run_answer"


@dataclass
class MissingItem:
    metric: str
    period: str
    member: str  # layer 1's member key: the symbol for warrants, sorted dimensions JSON else
    gate: str  # the plan's ``release_gate``, or "" when it set none
    layer1: str = ""
    kind: str = ""
    carried: str = ""  # why the item counts as complete: one period behind, carried forward
    reason: str = ""
    receipts: str = ""


def _member_key(metric: str, raw: str) -> str:
    """``CN_FUTURES_WARRANTS:symbol_missing:CU`` -> ``CU``; ``M:{"a": 1}`` -> sorted JSON."""
    rest = raw[len(metric) + 1 :] if raw.startswith(metric + ":") else raw
    if metric == WARRANTS:
        return rest.rsplit(":", 1)[-1]
    try:
        return json.dumps(json.loads(rest), ensure_ascii=False, sort_keys=True)
    except ValueError:
        return rest


def _tally(counts: Counter) -> str:
    return "、".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: str(kv[0])))


def _display(member: str) -> str:
    return "—" if member == "{}" else member


def _fmt(value: str | None) -> str:
    return parse_time(value).astimezone(BEIJING).strftime("%Y-%m-%d %H:%M") if value else "—"


# --- missing items ------------------------------------------------------------------------


def _missing_items(run: Run, final: dict) -> list[MissingItem]:
    gates = {(g["metric_id"], g.get("period")): g.get("release_gate", "") for g in final["gaps"]}
    items = []
    for row in final["requirements"]:
        if row.get("status") != "model_input_missing":
            continue
        metric, period = row["metric_id"], row.get("period", "")
        members = row.get("missing_members") or [f"{metric}:{{}}"]
        gate = gates.get((metric, period), "")
        items += [MissingItem(metric, period, _member_key(metric, m), gate) for m in members]
    return items


def _bounds(period: str) -> tuple[str, str]:
    """The days a plan period spans: ``2026-09-30`` one day, ``2026-08`` a month,
    ``2026-Q2`` a quarter."""
    if "-Q" in period:
        first = date(int(period[:4]), int(period[-1]) * 3 - 2, 1)
        months = 3
    elif len(period) == 7:
        first, months = date.fromisoformat(period + "-01"), 1
    else:
        return period, period
    month = first.month - 1 + months
    after = date(first.year + month // 12, month % 12 + 1, 1)
    return first.isoformat(), (after - timedelta(days=1)).isoformat()


def _previous_period(period: str) -> str:
    """The month or quarter before a low-frequency plan period."""
    year = int(period[:4])
    if "-Q" in period:
        quarter = int(period[-1]) - 1
        return f"{year - 1}-Q4" if quarter == 0 else f"{year}-Q{quarter}"
    month = int(period[5:7]) - 1
    return f"{year - 1}-12" if month == 0 else f"{year}-{month:02d}"


def _claims(run: Run, metric: str, member: str, period: str) -> list[tuple]:
    """Claims stored by the cutoff for the member in the period, newest first, only under
    catalog versions whose definition matches the frozen one (layer 1's ``same_definition``):
    (claim_id, available_at, public_available_at, inferred_public_at, quality_status)."""
    versions = sorted(run.same_definition.get(metric, {run.catalog_version}))
    if metric == WARRANTS:
        member_filter, params = "json_extract(dimensions_json, '$.symbol') = ?", [member]
    else:
        member_filter, params = "1", []
    first, last = _bounds(period)
    rows = run.db.execute(
        "SELECT claim_id, available_at, public_available_at, inferred_public_at,"
        " quality_status, dimensions_json FROM source_claim"
        " WHERE metric_id = ? AND period_end BETWEEN ? AND ? AND available_at <= ?"
        f" AND definition_version IN ({','.join('?' * len(versions))}) AND {member_filter}"
        " ORDER BY available_at DESC",
        (metric, first, last, run.cutoff, *versions, *params),
    ).fetchall()
    return [row[:5] for row in rows if metric == WARRANTS or _member_key(metric, row[5]) == member]


def _one_behind(
    run: Run, final: dict, item: MissingItem, series: dict, carried_core: set, selected: set
) -> str:
    """Why a missing item still counts as complete, or "". It must be the newest period the
    plan asks of the metric, and the model must have taken the period before it instead: a
    core asset says so itself (``carried_forward``); otherwise a claim of the member for the
    previous period (the previous open day in layer 1 for a daily metric) has to be among the
    run's frozen input ids."""
    periods = [
        r.get("period") or "" for r in final["requirements"] if r["metric_id"] == item.metric
    ]
    if item.period != max(periods, default=""):
        return ""
    if item.metric in run.manifest.get("core_metrics", {}).values():
        # A core asset says so itself; its earlier inputs alone prove nothing.
        carried = item.metric in carried_core and item.period == run.target_date
        return "核心沿用（上一交易日的值参与计算）" if carried else ""
    if len(item.period) == 10:  # a day: the member's previous open day in layer 1
        before = [c for c in series.get((item.metric, item.member), []) if c.day < item.period]
        if not before or before[-1].status == UNCOVERED:
            return ""
        previous = before[-1].day
    else:
        previous = _previous_period(item.period)
    taken = [c[0] for c in _claims(run, item.metric, item.member, previous) if c[0] in selected]
    if not taken:
        return ""
    return f"上一期 {previous} 的值已入选冻结输入（{taken[0][:12]}…），落后 1 期"


def _query_span(params: dict) -> tuple[str, str] | None:
    """The days a request's date parameters ask for, when they name days."""
    start = params.get("start_date") or params.get("trade_date") or params.get("date")
    end = params.get("end_date") or params.get("trade_date") or params.get("date")
    span = (iso_day(str(start)), iso_day(str(end))) if start and end else None
    return span if span and all(len(d) == 10 for d in span) else None


class Unsent:
    """Requests the run settled without a receipt (ticket 11), so the receipt count alone
    would read them as never asked.

    - Held back: a TuShare query the ledger (``retrieval_query``) recorded as
      ``negative_cache_active`` with no request sent. The older path left a failed receipt
      as well; a query with a matching receipt of the run (same endpoint and parameters,
      rejected ``negative_cache_active``) is already counted there and is not repeated.
    - Answered empty: the channel result ``warrant_day_empty_in_run_answer``
      (``run_retrieval_attempt`` of the release event ``full:<family>:<period>``): the run's
      own answer already held no row that day, so it did not ask again.
    """

    def __init__(self, run: Run) -> None:
        self._run = run
        self._apis: dict[str, set[str]] = {}
        self._notes: dict[tuple[str, str], list[str]] = {}
        failed: Counter = Counter()
        for api, params in run.db.execute(
            "SELECT a.api_name, a.parameters_json FROM full_run_acquisition f"
            " JOIN acquisition_request a USING (acquisition_id) WHERE f.run_id = ?"
            " AND f.phase != 'referenced' AND a.rejection_reason = ? AND a.started_at <= ?",
            (run.run_id, NEGATIVE_CACHE, run.cutoff),
        ):
            try:
                failed[(api, _canonical(params))] += 1
            except (ValueError, TypeError):
                continue
        self.held_back: list[tuple[str, tuple[str, str], str | None]] = []
        for text, eligible in run.db.execute(
            "SELECT query_text, next_eligible_at FROM retrieval_query WHERE run_id = ?"
            " AND channel = 'tushare' AND classification = ? AND physical_request_id IS NULL"
            " AND attempted_at <= ? ORDER BY attempted_at",
            (run.run_id, NEGATIVE_CACHE, run.cutoff),
        ):
            try:
                query = json.loads(text)
                api, params = query["api_name"], query.get("params") or {}
                key = (api, _canonical(json.dumps(params)))
                span = _query_span(params)
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            if failed[key]:
                failed[key] -= 1  # the older path's failed receipt already counts it
            elif span:
                self.held_back.append((api, span, eligible))

    def _metric_apis(self, metric: str) -> set[str]:
        """Endpoints of the receipts any run declared for the metric."""
        if metric not in self._apis:
            self._apis[metric] = {
                r[0]
                for r in self._run.db.execute(
                    "SELECT DISTINCT a.api_name FROM full_run_acquisition f"
                    " JOIN acquisition_request a USING (acquisition_id)"
                    " WHERE f.metric_ids_json LIKE ?",
                    (f'%"{metric}"%',),
                )
            }
        return self._apis[metric]

    def notes(self, metric: str, period: str) -> list[str]:
        if (metric, period) not in self._notes:
            self._notes[(metric, period)] = self._find(metric, period)
        return self._notes[(metric, period)]

    def _find(self, metric: str, period: str) -> list[str]:
        first, last = _bounds(period)
        apis = self._metric_apis(metric)
        held = [
            eligible
            for api, (start, end), eligible in self.held_back
            if api in apis and start <= last and first <= end
        ]
        notes = []
        if held:
            soonest = min((e for e in held if e), default=None)
            notes.append(
                f"暂缓、未发请求（{NEGATIVE_CACHE}，账本无回执"
                + (f"，最早 {_fmt(soonest)} 可再查" if soonest else "")
                + f"） {len(held)}"
            )
        family = self._run.catalog.get(metric, {}).get("release_event_family")
        if family:
            empty = self._run.db.execute(
                "SELECT COUNT(*) FROM run_retrieval_attempt WHERE run_id = ?"
                " AND release_event_id = ? AND classification = ? AND occurred_at <= ?",
                (self._run.run_id, f"full:{family}:{period}", EMPTY_IN_ANSWER, self._run.cutoff),
            ).fetchone()[0]
            if empty:
                notes.append(f"本轮应答已为空、未再请求（{EMPTY_IN_ANSWER}） {empty}")
        return notes


def _canonical(params: str) -> str:
    return json.dumps(json.loads(params), sort_keys=True, ensure_ascii=False)


def _explain(run: Run, final: dict, items: list[MissingItem], selected: set) -> None:
    """Attach layer 1's verdict and the run's own receipts to each missing item."""
    if not items:
        return
    result = acquisition.daily(run)
    cells = {(c.metric, c.member, c.day): c for c in result.cells}
    series: dict[tuple[str, str], list] = {}
    for cell in sorted(result.cells, key=lambda c: c.day):
        series.setdefault((cell.metric, cell.member), []).append(cell)
    carried_core = {
        a.get("metric_id")
        for a in run.datasets.get("core_assets", {}).get("assets", [])
        if a.get("carried_forward")
    }
    target_end = f"{run.target_date}T23:59:59.999999+08:00"
    public_cutoff = min(parse_time(run.cutoff), parse_time(target_end))
    markers = Unsent(run)
    for item in items:
        item.carried = _one_behind(run, final, item, series, carried_core, selected)
        cell = cells.get((item.metric, item.member, item.period))
        item.layer1 = cell.status if cell else "（第一层未逐格核对）"
        held = _claims(run, item.metric, item.member, item.period)
        if held:
            _, available, public, inferred, quality = held[0]
            # The production read view takes the stated public time, else the inferred one.
            effective = public or inferred
            stamp = f"已持有（{_fmt(available)} 入库，{quality}）"
            if effective and parse_time(effective) > public_cutoff:
                item.kind = LATE_PUBLIC
                item.reason = (
                    f"{stamp}，公开时间 {_fmt(effective)}{'' if public else '（推定）'}"
                    f"晚于公开截止 {_fmt(public_cutoff.isoformat())}"
                    "（目标日结束与运行截止取早者），按时点规则不进模型"
                )
            elif not effective:
                item.kind, item.reason = HELD_NO_PUBLIC, f"{stamp}，没有声明或推定的公开时间"
            else:
                item.kind = HELD_UNEXPLAINED
                item.reason = f"{stamp}，公开 {_fmt(effective)}；本脚本无法解释为何未进模型"
        elif cell and cell.status != HELD:
            item.kind, item.reason = cell.status, cell.evidence
        else:
            item.kind, item.reason = NO_CLAIM, "截止前没有该期该成员的声明"
        rows = run.db.execute(
            "SELECT a.state, COALESCE(a.rejection_reason, a.error_type, '') FROM"
            " full_run_acquisition f JOIN acquisition_request a USING (acquisition_id)"
            " WHERE f.run_id = ? AND f.phase != 'referenced' AND f.metric_ids_json LIKE ?"
            " AND (f.period IS NULL OR f.period = ?) AND a.started_at <= ?",
            (run.run_id, f'%"{item.metric}"%', item.period, run.cutoff),
        ).fetchall()
        tally = Counter(f"{state}{f'（{why}）' if why else ''}" for state, why in rows)
        notes = [_tally(tally)] if tally else []
        notes += markers.notes(item.metric, item.period)
        item.receipts = "；".join(notes) or "无"


# --- denominators -------------------------------------------------------------------------


def _plan_rows(run: Run, final: dict) -> list[list]:
    rows = []
    for label, chosen in (("目录全部指标", None), ("仅模型用到的指标", run.model_used)):
        picked = [r for r in final["requirements"] if chosen is None or r["metric_id"] in chosen]
        status = Counter(r.get("status") for r in picked)
        others = {k: v for k, v in status.items() if k not in _PLAN_STATUSES}
        rows.append(
            [
                label,
                len(picked),
                status["local_complete"],
                status["model_input_missing"],
                status["operational_evidence"],
                _tally(Counter(others)) or "0",
            ]
        )
    return rows


_PLAN_STATUSES = ("local_complete", "model_input_missing", "operational_evidence")


@dataclass
class InputIds:
    label: str
    ids: frozenset[str]
    claims: int = 0
    derived: int = 0
    broken: frozenset[str] = frozenset()


def _trace(run: Run, label: str, ids: list[str]) -> InputIds:
    found = InputIds(label, frozenset(ids))
    claims, derived = set(), set()
    chunk = 500
    listed = sorted(found.ids)
    for start in range(0, len(listed), chunk):
        part = listed[start : start + chunk]
        marks = ",".join("?" * len(part))
        claims |= {
            r[0]
            for r in run.db.execute(
                f"SELECT claim_id FROM source_claim WHERE claim_id IN ({marks})", part
            )
        }
        derived |= {
            r[0]
            for r in run.db.execute(
                "SELECT derived_observation_id FROM derived_observation"
                f" WHERE derived_observation_id IN ({marks})",
                part,
            )
        }
    found.claims, found.derived = len(claims), len(derived)
    found.broken = frozenset(found.ids - claims - derived)
    return found


def _confirmation(run: Run) -> tuple[list[list], list[list], Counter, int]:
    """Per key indicator: relation and member statuses, every member expanded; then the
    members that are not current or name missing periods."""
    macro = run.datasets.get("macro", {})
    summary, detail, statuses = [], [], Counter()
    empty_indicator_missing = 0
    for dimension in macro.get("confirmation", {}).get("dimensions", []):
        for indicator in dimension.get("key_indicators", []):
            members = indicator.get("members") or []
            counts = Counter(m.get("evidence_status") for m in members)
            statuses.update(counts)
            member_missing = sum(1 for m in members if m.get("missing"))
            if not indicator.get("missing") and (
                member_missing or any(m.get("evidence_status") != "current" for m in members)
            ):
                empty_indicator_missing += 1
            others = {k: v for k, v in counts.items() if k not in CONFIRMATION_STATUSES}
            summary.append(
                [
                    dimension.get("dimension"),
                    indicator.get("key"),
                    indicator.get("metric_id"),
                    indicator.get("relation"),
                    len(members),
                    *(counts.get(s, 0) for s in CONFIRMATION_STATUSES),
                    _tally(Counter(others)) or "0",
                    member_missing,
                    "、".join(map(str, indicator.get("missing") or [])) or "—",
                ]
            )
            for member in members:
                if member.get("evidence_status") == "current" and not member.get("missing"):
                    continue
                detail.append(
                    [
                        indicator.get("key"),
                        member.get("metric_id"),
                        _display(json.dumps(member.get("member") or {}, ensure_ascii=False)),
                        member.get("label", ""),
                        member.get("consistency", ""),
                        member.get("evidence_status"),
                        member.get("period", ""),
                        "、".join(map(str, member.get("missing") or [])) or "—",
                    ]
                )
    return summary, detail, statuses, empty_indicator_missing


def _freshness(run: Run) -> list[tuple]:
    return run.db.execute(
        "SELECT metric_id, status, frequency, held_period, released_period, due_period,"
        " periods_behind, public_available_at FROM batch_freshness WHERE batch_id = ?"
        " ORDER BY status, metric_id",
        (run.run_id,),
    ).fetchall()


# --- report -------------------------------------------------------------------------------


def section(run: Run) -> str:
    out = ["## 第二层：模型输入是否完整", ""]
    final = run.gap_plan("final")
    if final is None or not run.projection_set_id:
        return "\n".join([*out, "本运行没有最终取数计划或投影，无法核对。", ""])
    items = _missing_items(run, final)
    plan_rows = _plan_rows(run, final)
    core_ids = run.datasets.get("core_assets", {}).get("model_input_observation_version_ids", [])
    macro_ids = run.datasets.get("macro", {}).get("model_input_observation_version_ids", [])
    core, macro = _trace(run, "核心", core_ids), _trace(run, "宏观", macro_ids)
    recovery = core_trace.recover(run, core_ids)
    union = core.ids | macro.ids
    _explain(run, final, items, union)
    adoption = run.gap_plan("adoption") or {}
    adopted = set(adoption.get("selected_observation_version_ids") or [])
    summary, member_detail, member_status, empty_missing = _confirmation(run)
    freshness = _freshness(run)
    fresh_status = Counter(r[1] for r in freshness)
    one_behind = [r for r in freshness if r[6] == 1]
    carried = run.datasets.get("cycle_overview", {}).get("core_carry_forward") or []
    window_ids = {
        i
        for asset in run.datasets.get("core_assets", {}).get("assets", [])
        for i in asset.get("observation_version_ids", [])
    }

    # -- conclusion
    missing_periods = {(i.metric, i.period) for i in items}
    reasons = Counter(i.kind for i in items)
    carried_items = [i for i in items if i.carried]
    out += ["### 结论", ""]
    whole, used = plan_rows
    out.append(
        f"- **最终计划**：{whole[1]} 行，完整 {whole[2]}、缺失 {whole[3]}、运行证据 {whole[4]}"
        f"（仅模型用到的指标：{used[1]} 行，缺失 {used[3]}）；另有公式需求"
        f" {len(final.get('derived_requirements', []))} 条。缺失展开为 {len(items)} 个"
        f"“指标 × 期次 × 成员”，涉及 {len(missing_periods)} 个指标期、"
        f"{len({i.metric for i in items})} 个指标；原因：" + (_tally(reasons) or "无") + "。"
        f"其中落后 1 期、按沿用算完整的 {len(carried_items)} 个，真正缺失 "
        f"{len(items) - len(carried_items)} 个（仅模型用到的指标 "
        f"{sum(1 for i in items if not i.carried and i.metric in run.model_used)} 个）。"
    )
    out.append(
        f"- **冻结输入编号**：核心 {len(core.ids)}、宏观 {len(macro.ids)}，合并去重 {len(union)}"
        f"（与采纳记录 {'一致' if union == adopted else f'**不一致**，采纳 {len(adopted)}'}）。"
        f"核心追溯断链 {len(core.broken)} 个（已从原件精确恢复并核验"
        f" {len(core.broken & set(recovery.recovered))}、无法恢复且未核验"
        f" {len(core.broken - set(recovery.recovered))}），宏观 {len(macro.broken)} 个，单列，"
        "不算缺失。"
    )
    stage = run.datasets.get("cycle_overview", {}).get("current_stage")
    stage_note = (
        "当前阶段非空"
        if stage
        else "当前阶段为空，确认度不适用，生产在判关键指标缺失前就返回，指标级 `missing` 必为空"
    )
    out.append(
        f"- **确认度成员**：{len(summary)} 个关键指标、{sum(member_status.values())} 个成员，"
        + _tally(member_status)
        + f"；成员缺期 {sum(r[9] for r in summary)} 个。指标级 `missing` 为空、但成员不全是"
        f" current 或有缺期的关键指标 {empty_missing} 个（{stage_note}，所以逐个展开成员）。"
    )
    out.append(
        f"- **批次时效**：{len(freshness)} 项，"
        + _tally(fresh_status)
        + f"；其中落后 1 期 {len(one_behind)} 项，视为沿用、算完整。核心沿用 {len(carried)} 项。"
    )
    out += ["", "四个分母口径不同，不能互相换算：计划按“指标 × 期次”计行，输入编号按入选的观测计，"]
    out[-1] += "确认度按关键指标的成员计，批次时效按指标计且只看尾部落后。"
    out.append("")

    # -- missing detail
    out += ["### 缺失明细（指标 × 期次 × 成员）", ""]
    out += [
        "“算完整”一列：该项是计划对该指标要求的最新一期，且模型实际用了上一期的值（日频为该"
        "成员在第一层里的前一开市日，该期该成员的声明在本运行的冻结输入编号中；三核心以"
        " `carried_forward` 为准），即落后 1 期，按规格算完整。前一开市日日历未覆盖时不判。",
        "",
    ]
    headers = [
        "指标",
        "模型用到",
        "期次",
        "成员",
        "计划的发布判定",
        "第一层",
        "原因",
        "本运行回执",
        "算完整",
    ]
    rows = [
        [
            i.metric,
            scope_label(run, i.metric),
            i.period,
            _display(i.member),
            i.gate or "—",
            i.layer1,
            i.reason,
            i.receipts,
            i.carried or "否",
        ]
        for i in items
    ]
    out += [table(headers, rows) if rows else "无。", ""]

    # -- denominators
    out += ["### 分母一：最终计划行（`full_run_gap_plan` final.requirements）", ""]
    headers = ["范围", "行数", "完整", "缺失", "运行证据", "其他状态"]
    out += [table(headers, plan_rows), ""]
    derived = Counter(
        (d.get("computation_status"), d.get("input_coverage_complete"))
        for d in final.get("derived_requirements", [])
    )
    out += [
        "公式需求（不计入上表）："
        + (
            "、".join(f"{s}／原料齐全={c} {n}" for (s, c), n in sorted(derived.items(), key=str))
            or "无"
        )
        + "。",
        "",
    ]
    out += ["### 分母二：冻结输入编号（投影 `model_input_observation_version_ids`）", ""]
    headers = ["来源", "编号", "可联接来源声明", "可联接派生值", "追溯断链"]
    rows = [[t.label, len(t.ids), t.claims, t.derived, len(t.broken)] for t in (core, macro)]
    rows.append(["合并去重", len(union), "", "", len(core.broken | macro.broken)])
    out += [table(headers, rows), ""]
    out += ["### 分母三：确认度成员（展开 `members[]`）", ""]
    headers = [
        "维度",
        "关键指标",
        "指标",
        "关系",
        "成员",
        *CONFIRMATION_STATUSES,
        "其他",
        "成员缺期",
        "指标级 missing",
    ]
    out += [table(headers, summary) if summary else "无确认度数据。", ""]
    if member_detail:
        out += ["不是 current 或有缺期的成员：", ""]
        headers = ["关键指标", "指标", "成员", "名称", "一致性", "状态", "最新期", "缺期"]
        out += [table(headers, member_detail), ""]
    out += ["### 分母四：批次时效（`batch_freshness`）", ""]
    out.append(_tally(fresh_status) + "。落后 1 期视为沿用，算完整；下表列出非 current 的项。")
    out.append("")
    headers = [
        "指标",
        "状态",
        "频率",
        "持有期",
        "已发布期",
        "应有期",
        "落后期数",
        "公开时间",
        "备注",
    ]
    rows = [
        [*r[:7], _fmt(r[7]), "落后 1 期，算完整" if r[6] == 1 else ""]
        for r in freshness
        if r[1] != "current"
    ]
    out += [table(headers, rows) if rows else "无。", ""]

    # -- broken trace
    out += ["### 追溯断链（核心输入的留存例外）", ""]
    broken = core.broken | macro.broken
    if broken:
        outside = core.broken - window_ids
        out.append(
            f"{len(broken)} 个输入编号已无法联接来源声明或派生值（核心 {len(core.broken)}、"
            f"宏观 {len(macro.broken)}）。核心中 {len(outside)} 个不在三核心 120 日窗口的观测之内，"
            "是窗口前用于均线、斜率和持续确认的输入；按留存规则，三核心价格的窗口前声明即使被"
            "投影引用也可删除。这是追溯缺口，不说明当时没取到，不计入缺失。"
            + ("宏观断链不适用这条留存例外，需要单独查明。" if macro.broken else "")
            + "示例："
            + "、".join(sorted(broken)[:3])
            + "。"
        )
    else:
        out.append("无。")
    out.append("")
    if core.broken:
        out += _recovery(run, core.broken, recovery)
    return "\n".join(out)


def _recovery(run: Run, broken: frozenset[str], recovery: core_trace.Recovery) -> list[str]:
    """The core broken trace split by the exact recovery (residual ticket 03)."""
    recovered = broken & set(recovery.recovered)
    ambiguous, missed = broken & recovery.ambiguous, broken - recovered - recovery.ambiguous
    out = [
        "#### 核心断链的精确恢复",
        "",
        f"声明行已删除、已从原件精确恢复并核验 {len(recovered)} 个；无法恢复、未核验"
        f" {len(missed) + len(ambiguous)} 个（未命中 {len(missed)}、有歧义 {len(ambiguous)}）。"
        "规则见体检口径文档“三核心窗口前冻结编号的精确恢复”：校验原件哈希、来源身份、截止"
        "时间、原始件与规范化件取值一致，再按编号规则逐日重算，与冻结编号逐个匹配。",
        "",
    ]
    rows = []
    for metric in run.manifest["core_metrics"].values():
        days = [r.day for i, r in recovery.recovered.items() if i in broken and r.metric == metric]
        rows.append([
            metric, len(days), f"{min(days)}～{max(days)}" if days else "—",
            "、".join(recovery.receipts.get(metric, [])) or "—",
        ])  # fmt: skip
    headers = ["指标", "已恢复并核验", "恢复的首末日", "恢复所用回执"]
    out += [table(headers, rows), ""]
    if recovery.rejected:
        out += ["未用于恢复的回执：" + "；".join(recovery.rejected) + "。", ""]
    if missed or ambiguous:
        out += ["无法恢复的示例：" + "、".join(sorted(missed | ambiguous)[:3]) + "。", ""]
    return out
