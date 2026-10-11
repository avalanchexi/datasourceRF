"""Layer 3, second check: recompute the three core trend states and the formal stage.

The rules come only from documents; ticket 04 lists each with its source (the 120-day trend
calibration answer, ADR-0001, ADR-0035, ``CONTEXT.md``). Parameters are read from the frozen
manifest (``trend_rules``, ``stage_mapping``, ``core_metrics``). Production trend code is
neither imported nor mirrored.

Inputs are the run's frozen core inputs: the ``model_input_observation_version_ids`` of its
``core_assets`` dataset, resolved to source claims. Ids that no longer resolve are the
pre-window warm-up that retention deletes (ADR-0035); they are rebuilt exactly from the run's
own core receipts, whose raw responses are kept (``core_trace``, residual ticket 03), and only
ids that cannot be rebuilt are still inferred from those raw days by count.

Every day is recomputed from the observations up to that day and compared with the system's
day summaries (``stage_history``; for the target day also ``p0_assessment`` and
``cycle_overview``). A summary carried over from an earlier run is, where it differs, recomputed
again from that run's own raw responses: agreement there shows the difference comes from the
history the earlier run held, not from the rules. Where the documents allowed two readings,
the user's rulings of 2026-10-10 recorded in ticket 04 apply (A2, A3, A8).
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache

import core_trace
from common import Run, compress_days, iso_day, table

ASSETS = ("bond", "stock", "commodity")  # stage_mapping keys read bond,stock,commodity
NAMES = {"bond": "债", "stock": "股", "commodity": "商品"}
STATE_NAMES = {"bull": "牛", "bear": "熊", None: "—"}
# trend_rules keys this recomputation understands; any other key, or another rule version,
# means rules the documents do not describe, so nothing is recomputed.
KNOWN_RULE_KEYS = {
    "rule_version", "candidate_duration_rule_version", "window_days", "slope_days",
    "volatility_days", "noise_multiplier", "persistence_days", "candidate_window_days",
    "proxy_12m_enabled",
}  # fmt: skip
RULE_VERSIONS = {
    "rule_version": "trend-v0001",
    "candidate_duration_rule_version": "candidate-duration-v0002",
}
NONCANONICAL = "noncanonical_combination"  # CONTEXT: 非典型组合 (Noncanonical Combination)
TOLERANCE = 1e-9  # relative, for distance / noise band / slope

SAME, DIFFERENT = "一致", "有差异"
UNVERIFIED, NO_RECORD = "未核验（核心缺日或收益链中断）", "系统无记录"
OLDER = "未核验（可见历史之前的阶段）"


# --- inputs -------------------------------------------------------------------------------


@dataclass
class Series:
    asset: str
    metric: str
    closes: dict[str, float] = field(default_factory=dict)
    pre_closes: dict[str, float] = field(default_factory=dict)  # from raw rows
    from_claims: int = 0
    recovered: int = 0  # days rebuilt exactly from the raw response (core_trace)
    from_raw: int = 0  # days inferred from the raw response by count, not matched one by one
    duplicate_days: list[str] = field(default_factory=list)  # several frozen values, one day
    raw_mismatch: list[str] = field(default_factory=list)  # raw close != claim value
    receipts: list[str] = field(default_factory=list)

    @property
    def days(self) -> list[str]:
        return sorted(self.closes)

    def levels(self) -> tuple[list[float], list[str], list[str]]:
        """The official return chain ``change/pre_close`` (calibration answer, rule 1) as price
        levels, plus the days whose ``pre_close`` is not the previous close (breaks) and the
        days without a ``pre_close`` (their return falls back to the close ratio)."""
        days = self.days
        levels, breaks, missing = [], [], []
        for i, day in enumerate(days):
            close = self.closes[day]
            if i == 0:
                levels.append(close)
                continue
            before = self.closes[days[i - 1]]
            pre = self.pre_closes.get(day)
            if pre is None:
                missing.append(day)
                pre = before
            elif not math.isclose(pre, before, rel_tol=TOLERANCE):
                breaks.append(day)
            levels.append(levels[-1] * close / pre)
        return levels, breaks, missing

    def broken_from(self, open_days: list[str]) -> tuple[str, str] | None:
        """The first day from which the chain cannot be built as documented: an open day
        missing inside the series, or a day without ``pre_close``. Its return, and so every
        later measure and the state machine's memory, would rest on an undocumented
        carry-forward (A5), so those days are not recomputed."""
        days = self.days
        if not days:
            return None
        found = []
        missing_day = next(
            (d for d in open_days if days[0] < d < days[-1] and d not in self.closes), None
        )
        if missing_day:
            found.append((missing_day, f"{NAMES[self.asset]}缺 {missing_day}"))
        _, _, no_pre = self.levels()
        if no_pre:
            found.append((no_pre[0], f"{NAMES[self.asset]} {no_pre[0]} 缺 pre_close"))
        return min(found) if found else None


def _raw_rows(run: Run, receipt_ids: list[str], until: str) -> tuple[dict[str, dict], list[str]]:
    """TuShare rows by day (up to ``until``) from these receipts, newest receipt first."""
    rows: dict[str, dict] = {}
    used = []
    marks = ",".join("?" * len(receipt_ids))
    for receipt in run.receipts(f"a.acquisition_id IN ({marks})", tuple(receipt_ids)):
        if not (run.reached_source(receipt) and run.validated_by_cutoff(receipt)):
            continue
        try:
            payload = json.loads(run.artifact(receipt.raw_hash))
            fields, items = payload["data"]["fields"], payload["data"]["items"]
            parsed = [dict(zip(fields, item, strict=True)) for item in items]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        used.append(receipt.acquisition_id)
        for row in parsed:
            day = iso_day(str(row.get("trade_date", "")))
            if day <= until and row.get("close") is not None:
                rows.setdefault(day, row)
    return rows, used


def _fill_raw(series: Series, rows: dict[str, dict]) -> None:
    for day, row in rows.items():
        if row.get("pre_close") is not None:
            series.pre_closes[day] = float(row["pre_close"])


def frozen_series(run: Run, core: dict) -> tuple[dict[str, Series], int, core_trace.Recovery, str]:
    """Per asset the frozen series; also (frozen ids, the exact recovery, problem or "").

    Ids without a stored claim are first rebuilt exactly from the run's core receipts
    (``core_trace``); only those that cannot be are still inferred from the raw days before
    the first held day, by count."""
    ids = core["model_input_observation_version_ids"]
    recovery = core_trace.recover(run, ids)
    by_metric: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for chunk in range(0, len(ids), 500):
        part = ids[chunk : chunk + 500]
        for metric, day, value in run.db.execute(
            "SELECT metric_id, period_end, value FROM source_claim"
            f" WHERE claim_id IN ({','.join('?' * len(part))})",
            part,
        ):
            by_metric[metric][day].append(value)
    left = len(recovery.unresolved) - len(recovery.recovered)
    found = {}
    for asset in ASSETS:
        metric = run.manifest["core_metrics"][asset]
        series = Series(asset, metric)
        series.from_claims = len(by_metric[metric])
        for item in recovery.by_metric(metric):
            if item.day not in by_metric[metric]:
                series.recovered += 1
            by_metric[metric][item.day].append(item.close)
        for day, held in by_metric[metric].items():
            if len(set(held)) > 1:
                series.duplicate_days.append(day)
            series.closes[day] = held[-1]
        rows, series.receipts = _raw_rows(
            run, core_trace.core_receipts(run, metric), run.target_date
        )
        _fill_raw(series, rows)
        first_held = min(series.closes, default="")
        for day, row in rows.items():
            if day in series.closes:
                if not math.isclose(series.closes[day], float(row["close"]), rel_tol=TOLERANCE):
                    series.raw_mismatch.append(day)
            elif left and day < first_held:  # only ids not rebuilt exactly are inferred
                series.closes[day] = float(row["close"])
                series.from_raw += 1
        found[asset] = series
    from_raw = sum(s.from_raw for s in found.values())
    problem = ""
    if from_raw != left:
        problem = (
            f"原件推定补读 {from_raw} 条与未能精确恢复的追不到编号 {left} 个数目不符，"
            "无法确认冻结输入的集合"
        )
    return found, len(ids), recovery, problem


def batch_series(run: Run, batch: str, template: dict[str, Series]) -> dict[str, Series] | None:
    """What an earlier run held: its own core receipts with the same request as the audited
    run's (API and ``ts_code``), raw rows up to its target date; None if unreadable."""
    row = run.db.execute(
        "SELECT target_business_date FROM parent_run WHERE run_id = ?", (batch,)
    ).fetchone()
    if row is None:
        return None
    found = {}
    for asset, frozen in template.items():
        wanted = {
            (r.api_name, r.parameters.get("ts_code"))
            for r in run.receipts(
                f"a.acquisition_id IN ({','.join('?' * len(frozen.receipts))})",
                tuple(frozen.receipts),
            )
        }
        receipt_ids = [
            r.acquisition_id
            for r in run.receipts(
                "a.acquisition_id IN (SELECT acquisition_id FROM full_run_acquisition"
                " WHERE run_id = ? AND phase != 'referenced')",
                (batch,),
            )
            if (r.api_name, r.parameters.get("ts_code")) in wanted
        ]
        rows, used = _raw_rows(run, receipt_ids, row[0])
        if not rows:
            return None
        series = Series(asset, frozen.metric, receipts=used)
        series.closes = {d: float(r["close"]) for d, r in rows.items()}
        series.from_raw = len(rows)
        _fill_raw(series, rows)
        found[asset] = series
    return found


# --- the rules ----------------------------------------------------------------------------


@dataclass
class Measures:
    distance: float  # level / MA120 - 1
    band: float  # noise_multiplier x population stdev of the last 20 daily returns
    slope: float  # MA120(t) / MA120(t - 20) - 1

    def signal(self) -> str | None:
        """Bull or bear direction condition of the day (calibration answer, rule 4)."""
        if self.distance >= self.band and self.slope > 0:
            return "bull"
        if self.distance <= -self.band and self.slope < 0:
            return "bear"
        return None

    def conflict(self) -> bool:
        """Price outside the band on one side while the MA slope points the other way."""
        return (self.distance >= self.band and self.slope < 0) or (
            self.distance <= -self.band and self.slope > 0
        )


def measures(levels: list[float], t: int, rules: dict) -> Measures | None:
    window, slope_days = int(rules["window_days"]), int(rules["slope_days"])
    vol_days = int(rules["volatility_days"])
    if t < window - 1 + slope_days or t < vol_days:
        return None
    ma = sum(levels[t - window + 1 : t + 1]) / window
    ma_before = sum(levels[t - slope_days - window + 1 : t - slope_days + 1]) / window
    returns = [levels[i] / levels[i - 1] - 1 for i in range(t - vol_days + 1, t + 1)]
    band = float(rules["noise_multiplier"]) * statistics.pstdev(returns)
    return Measures(levels[t] / ma - 1, band, ma / ma_before - 1)


@dataclass
class Day:
    measures: Measures | None
    state: str | None
    candidate: str | None
    candidate_days: int
    confirmed: bool  # the stable direction changed today


def run_machine(steps: list[Measures | None], persistence: int) -> list[Day]:
    """The stable-direction state machine over consecutive valid observations.

    A direction condition differing from the stable direction is a candidate; it becomes the
    stable direction after ``persistence`` consecutive observations. A day without that
    condition clears the candidate and keeps the stable direction. Before the first
    confirmation the state is empty. On the confirmation day the candidate is cleared (A3).
    """
    stable, candidate, count = None, None, 0
    days = []
    for step in steps:
        signal = step.signal() if step else None
        confirmed = False
        if signal is not None and signal != stable:
            count = count + 1 if signal == candidate else 1
            candidate = signal
            if count >= persistence:
                stable, candidate, count, confirmed = signal, None, 0, True
        else:
            candidate, count = None, 0
        days.append(Day(step, stable, candidate, count, confirmed))
    return days


@dataclass
class Recompute:
    days: list[str]  # every SSE open day from the first held observation to ``until``
    per_asset: dict[str, dict[str, Day]]  # only days the asset has an observation
    kinds: dict[str, str]  # canonical / noncanonical / undetermined / gap
    stages: dict[str, tuple]  # (current_stage, last_confirmed_stage)
    seen_stage: dict[str, bool]  # a valid stage appeared in the visible history by that day
    broken: tuple[str, str] | None  # (first day not recomputed, why)


def recompute(run: Run, series: dict[str, Series], until: str) -> Recompute:
    rules = run.manifest["trend_rules"]
    persistence = int(rules["persistence_days"])
    per_asset: dict[str, dict[str, Day]] = {}
    for asset, s in series.items():
        levels, _, _ = s.levels()
        steps = [measures(levels, t, rules) for t in range(len(levels))]
        per_asset[asset] = dict(zip(s.days, run_machine(steps, persistence), strict=True))
    first = min((min(s.closes) for s in series.values() if s.closes), default=until)
    days = sorted(d for d in run.calendars["SSE"].open_days if first <= d <= until)
    broken = min(
        (b for s in series.values() if (b := s.broken_from(days)) is not None), default=None
    )
    mapping = run.manifest["stage_mapping"]
    # A trend conflict keeps the stable direction and maps as usual (A2); a valid stage is its
    # own last confirmed stage on that very day (A8).
    kinds, stages, seen, last = {}, {}, {}, None
    for day in days:
        held = [per_asset[a].get(day) for a in ASSETS]
        if any(d is None for d in held) or (broken and day >= broken[0]):
            kinds[day], stages[day], seen[day] = "gap", (None, last), last is not None
            continue
        states = [d.state for d in held]
        stage = None if None in states else mapping.get(",".join(states))
        kinds[day] = "undetermined" if None in states else "canonical" if stage else "noncanonical"
        last = stage or last
        stages[day], seen[day] = (stage, last), last is not None
    return Recompute(days, per_asset, kinds, stages, seen, broken)


# --- system output and comparison ---------------------------------------------------------


@dataclass
class Event:
    business_date: str
    source: str  # stage_history / p0_assessment / cycle_overview
    batch: str
    model: str
    document: dict

    def asset(self, asset: str) -> dict:
        return next((a for a in self.document.get("core_assets", []) if a["asset"] == asset), {})


def system_events(run: Run) -> list[Event]:
    events = []
    for event in (run.datasets.get("stage_history") or {}).get("events", []):
        batch = run.db.execute(
            "SELECT batch_id FROM projection_set WHERE projection_set_id = ?",
            (event.get("projection_set_id"),),
        ).fetchone()
        events.append(
            Event(
                event["business_date"],
                "stage_history",
                batch[0] if batch else "?",
                event.get("model_version_id", "?"),
                event,
            )
        )
    for (document,) in run.db.execute(
        "SELECT document_json FROM p0_assessment WHERE projection_set_id = ?",
        (run.projection_set_id,),
    ):
        doc = json.loads(document)
        events.append(
            Event(doc["business_date"], "p0_assessment", run.run_id, run.model_version_id, doc)
        )
    overview = run.datasets.get("cycle_overview")
    if overview:
        events.append(
            Event(run.target_date, "cycle_overview", run.run_id, run.model_version_id, overview)
        )
    return events


def _sys_measures(item: dict) -> Measures | None:
    """The system's published measures (percent) as fractions, if it published them."""
    values = [item.get(k) for k in ("distance_pct", "noise_band_pct", "slope_pct")]
    if any(v is None for v in values):
        return None
    return Measures(*(v / 100 for v in values))


def compare(day: str, rc: Recompute, event: Event) -> list[tuple]:
    """(field, recomputed, system, kind) for every field that does not agree; kind is
    DIFFERENT, or OLDER (a last confirmed stage older than the visible history)."""
    out = []
    for asset in ASSETS:
        got, item = rc.per_asset[asset][day], event.asset(asset)
        if not item:
            out.append((f"{NAMES[asset]}：记录", "有", "缺", DIFFERENT))
            continue
        if item.get("state") != got.state:
            out.append((f"{NAMES[asset]}：state", got.state, item.get("state"), DIFFERENT))
        mine = (got.candidate, got.candidate_days)
        theirs = (item.get("candidate_state"), item.get("candidate_days"))
        if theirs != mine:
            out.append((f"{NAMES[asset]}：候选", mine, theirs, DIFFERENT))
        published = _sys_measures(item)
        if (got.measures is None) != (published is None):
            text = "有" if got.measures else "无（历史不足）"
            out.append((f"{NAMES[asset]}：测量值", text, "有" if published else "无", DIFFERENT))
        elif got.measures and published:
            for key in ("distance", "band", "slope"):
                a, b = getattr(got.measures, key), getattr(published, key)
                if not math.isclose(a, b, rel_tol=TOLERANCE, abs_tol=1e-12):
                    out.append((f"{NAMES[asset]}：{key}", f"{a:.6%}", f"{b:.6%}", DIFFERENT))
    doc = event.document
    theirs, mine = (doc.get("current_stage"), doc.get("last_confirmed_stage")), rc.stages[day]
    if theirs != mine:
        older = not rc.seen_stage[day] and theirs[1] is not None and theirs[0] == mine[0]
        kind = OLDER if older else DIFFERENT
        out.append(("current_stage／last_confirmed_stage", mine, theirs, kind))
    noncanonical = rc.kinds[day] == "noncanonical"
    if noncanonical != (doc.get("stage_reason") == NONCANONICAL):
        out.append(("非典型组合", noncanonical, doc.get("stage_reason"), DIFFERENT))
    return out


@dataclass
class Finding:
    day: str
    event: Event
    items: list[tuple]
    cause: str = ""


def judge(run: Run, rc: Recompute, by_day: dict[str, list[Event]], series) -> dict:
    """Per window day a status, and the findings behind non-agreeing days."""

    @cache
    def batch_recompute(batch: str) -> tuple[Recompute, str] | None:
        """The earlier run's own recomputation, and how its inputs relate to the frozen
        ones: which starts earlier, and whether the shared days carry the same prices."""
        held = batch_series(run, batch, series)
        if held is None:
            return None
        until = run.db.execute(
            "SELECT target_business_date FROM parent_run WHERE run_id = ?", (batch,)
        ).fetchone()[0]
        earlier, differing = True, 0
        for asset, theirs in held.items():
            mine = series[asset]
            earlier &= min(theirs.closes) < min(mine.closes)
            for day in set(theirs.closes) & set(mine.closes):
                same = math.isclose(theirs.closes[day], mine.closes[day], rel_tol=TOLERANCE)
                a, b = theirs.pre_closes.get(day), mine.pre_closes.get(day)
                if a is not None and b is not None:
                    same &= math.isclose(a, b, rel_tol=TOLERANCE)
                differing += not same
        starts = "、".join(
            f"{NAMES[a]} {min(h.closes)}／{min(series[a].closes)}" for a, h in held.items()
        )
        category = "起算点不同" if earlier and not differing else "早先输入不同"
        text = (
            f"{category}（{batch} 的原件与冻结输入的首日：{starts}；重叠日价格"
            + ("相同" if not differing else f"不同 {differing} 处")
            + "；按其原件复算与该记录一致"
        )
        return recompute(run, held, until), text

    status, findings = {}, []
    for day in run.window:
        if rc.kinds.get(day, "gap") == "gap":
            status[day] = UNVERIFIED
            continue
        if not by_day.get(day):
            status[day] = NO_RECORD
            continue
        worst = SAME
        for event in by_day[day]:
            items = compare(day, rc, event)
            kinds = {i[3] for i in items}
            if DIFFERENT in kinds:
                cause = "未解释（待开票）"
                if event.batch != run.run_id:
                    found = batch_recompute(event.batch)
                    if found is None:
                        cause = f"未解释（{event.batch} 的原件不可读，无法复算）"
                    elif found[0].kinds.get(day, "gap") != "gap":
                        again = {i[3] for i in compare(day, found[0], event)}
                        if DIFFERENT not in again:
                            note = "，可见历史之前的阶段未核验" if again else ""
                            cause = f"{found[1]}{note}）"
                findings.append(Finding(day, event, items, cause))
                worst = DIFFERENT
            elif items:
                findings.append(Finding(day, event, items))
                if worst == SAME:
                    worst = OLDER
        status[day] = worst
    return {"status": status, "findings": findings}


# --- the section --------------------------------------------------------------------------


def section(run: Run) -> str:
    out = ["## 第三层（二）：三核心独立重算", ""]
    rules = run.manifest.get("trend_rules", {})
    unknown = set(rules) - KNOWN_RULE_KEYS
    wrong = {k: rules.get(k) for k, v in RULE_VERSIONS.items() if rules.get(k) != v}
    if unknown or wrong or set(run.manifest.get("core_metrics", {})) != set(ASSETS):
        out.append(f"**未重算**：冻结规则超出文档覆盖（未知键 {sorted(unknown)}，版本 {wrong}）。")
        return "\n".join(out + [""])
    core = run.datasets.get("core_assets")
    if not core:
        return "\n".join(out + ["**未重算**：被审运行没有 `core_assets` 数据集。", ""])
    series, total_ids, recovery, problem = frozen_series(run, core)
    if problem or any(not s.closes for s in series.values()):
        out.append(f"**未重算**：{problem or '有核心资产没有任何冻结输入'}。")
        return "\n".join(out + [""])

    rc = recompute(run, series, run.target_date)
    events = system_events(run)
    window = set(run.window)
    by_day: dict[str, list[Event]] = defaultdict(list)
    for event in events:
        if event.business_date in window:
            by_day[event.business_date].append(event)
    result = judge(run, rc, by_day, series)
    status, findings = result["status"], result["findings"]

    out += _conclusion(run, rc, series, events, status, findings, total_ids, recovery)
    out += _input_table(run, series)
    out += _target_tables(run, rc, events)
    out += _daily_table(run, rc, by_day, status)
    out += _finding_table(run, findings)
    out += _conflict_table(run, rc, by_day)
    return "\n".join(out)


def _conclusion(run, rc, series, events, status, findings, total_ids, recovery) -> list[str]:
    target = run.target_date
    sources = [e.source for e in events if e.business_date == target]
    missing = {"stage_history", "p0_assessment", "cycle_overview"} - set(sources)
    counts = defaultdict(int)
    for day in run.window:
        counts[status[day]] += 1
    causes = defaultdict(set)
    for f in findings:
        if f.cause:
            causes[f.cause.split("（")[0]].add(f.day)

    out = [
        f"- **目标日 {target}**：重算 {_label(rc, target)}。系统 {_sources(sources) or '无记录'}："
        f"{status.get(target)}"
        + (f"；**缺少 {'、'.join(sorted(missing))}**" if missing else "")
        + "。",
        f"- **逐日比对**（窗口 {len(run.window)} 日，系统记录 "
        f"{sum(1 for e in events if e.business_date in set(run.window))} 条）："
        + "，".join(f"{k} {counts[k]} 日" for k in (SAME, DIFFERENT, OLDER, UNVERIFIED, NO_RECORD))
        + "。",
    ]
    if counts[DIFFERENT]:
        out.append(
            "- **差异原因**："
            + "；".join(
                f"{name} {len(days)} 日（{compress_days(sorted(days), run.window)}）"
                for name, days in sorted(causes.items())
            )
            + "。“起算点不同”：这些日汇总由更早的运行算出（已汇总的日子不再重算），"
            "那次运行的原件起点早于冻结输入、重叠日价格相同，用它按同一规则复算即与记录一致。"
            "“早先输入不同”：复算也一致，但起点不早于冻结输入或重叠日价格不同，原因待查。"
        )
    if rc.broken:
        out.append(
            f"- **未重算**：{rc.broken[1]}，收益链无法按文档构造（A5），{rc.broken[0]} 起各日"
            "记为未核验。"
        )
    out.append(f"- **系统记录的模型**：{_models(run, events)}")
    from_raw = sum(s.from_raw for s in series.values())
    unresolved, recovered = len(recovery.unresolved), len(recovery.recovered)
    left = unresolved - recovered
    text = (
        f"- **冻结核心输入**：{total_ids} 个编号，{total_ids - unresolved} 个能追到来源声明；"
        f"{unresolved} 个追不到（窗口前预热已被留存删除，属追溯断链）。其中 {recovered} 个已从"
        "本运行自己的核心回执原件按编号规则逐个精确恢复并核验（见第二层“追溯断链”）"
    )
    if left:
        text += (
            f"；其余 {left} 个无法恢复，按日从同一批原件补读（只取已持有首日之前的日子），共"
            f" {from_raw} 条，与未恢复的数目吻合。这部分只能按条数与日期推定为被冻结的那批预热"
            "输入，无法逐一对应（未核验）"
        )
    out.append(
        text
        + "；与声明重叠的日子，原件收盘"
        + (
            "与声明值一致。"
            if not any(s.raw_mismatch for s in series.values())
            else "**与声明值不一致**。"
        )
    )
    breaks = {a: s.levels()[1:] for a, s in series.items()}
    out.append(
        "- **收益链**：按官方 `change/pre_close` 构造。"
        + "；".join(
            f"{NAMES[a]} 断点 {len(b)} 日、缺 `pre_close` {len(m)} 日"
            for a, (b, m) in breaks.items()
        )
        + "。"
    )
    out += [
        "- **未重算**：`candidate_30d`（30 日轨道），文档没有写明判定公式（A6）。核心沿用的计算"
        "细节文档也没有写明（A5），核心缺日只计为未核验。补算日按观测日期截取历史，各价格的历史"
        "公开可用时间没有独立核验。",
        "",
    ]
    return out


def _models(run: Run, events: list[Event]) -> str:
    """Day summaries carried over from earlier runs may come from older models: say whether
    their trend rules and stage mapping are the frozen ones (``proxy_12m_enabled`` aside)."""

    def rules(manifest: dict) -> tuple:
        trend = manifest.get("trend_rules", {})
        trend = {k: v for k, v in trend.items() if k != "proxy_12m_enabled"}
        return trend, manifest.get("stage_mapping"), manifest.get("core_metrics")

    frozen, same, differ = rules(run.manifest), [], []
    for model in sorted({e.model for e in events}):
        row = run.db.execute(
            "SELECT manifest_json FROM model_version WHERE model_version_id = ?", (model,)
        ).fetchone()
        (same if row and rules(json.loads(row[0])) == frozen else differ).append(model)
    text = f"{'、'.join(same)} 的趋势规则、阶段映射与核心指标与冻结清单相同。" if same else ""
    if differ:
        text += f"**{'、'.join(differ)} 不同**，其记录的差异可能来自规则本身。"
    return text


def _sources(sources: list[str]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for source in sources:
        counts[source] += 1
    return "、".join(f"{s}×{n}" if n > 1 else s for s, n in counts.items())


def _pct(value) -> str:
    return "—" if value is None else f"{value / 100:.4%}"


KIND_NAMES = {"canonical": "典型组合", "noncanonical": "非典型组合", "undetermined": "核心状态未定",
              "gap": "核心缺日"}  # fmt: skip


def _label(rc: Recompute, day: str) -> str:
    if rc.kinds.get(day, "gap") == "gap":
        return "核心缺日，未重算"
    parts = []
    for asset in ASSETS:
        d = rc.per_asset[asset][day]
        text = NAMES[asset] + STATE_NAMES[d.state]
        if d.measures is None:
            text += "（历史不足）"
        elif d.candidate:
            text += f"（候选{STATE_NAMES[d.candidate]} {d.candidate_days}）"
        elif d.confirmed:
            text += "（当日确认）"
        parts.append(text)
    return "、".join(parts) + f"；{rc.stages[day][0] or '空'}（{KIND_NAMES[rc.kinds[day]]}）"


def _system_label(event: Event) -> str:
    parts = []
    for asset in ASSETS:
        item = event.asset(asset)
        text = NAMES[asset] + STATE_NAMES.get(item.get("state"), str(item.get("state")))
        if _sys_measures(item) is None:
            text += "（无测量值）"
        elif item.get("candidate_state"):
            text += f"（候选{STATE_NAMES[item['candidate_state']]} {item['candidate_days']}）"
        parts.append(text)
    doc = event.document
    return "、".join(parts) + f"；{doc.get('current_stage') or '空'}（{doc.get('stage_reason')}）"


def _input_table(run: Run, series: dict[str, Series]) -> list[str]:
    open_days = sorted(run.calendars["SSE"].open_days)
    rows = []
    for s in series.values():
        days = s.days
        missing = sorted(set(d for d in open_days if days[0] <= d <= days[-1]) - set(days))
        _, breaks, no_pre = s.levels()
        rows.append([
            NAMES[s.asset], s.metric, len(days), f"{days[0]}～{days[-1]}", s.from_claims,
            s.recovered, s.from_raw, len(s.duplicate_days), len(s.raw_mismatch), len(breaks),
            len(no_pre), compress_days(missing, open_days) or "无", ", ".join(s.receipts) or "—",
        ])  # fmt: skip
    headers = ["资产", "指标", "条数", "首末日", "来自声明", "原件精确恢复", "原件推定补读",
               "同日多个冻结值", "原件≠声明", "收益链断点", "缺 pre_close", "比上交所开市日缺",
               "原件所用回执"]  # fmt: skip
    return ["### 冻结核心输入", "", table(headers, rows), ""]


def _target_tables(run: Run, rc: Recompute, events: list[Event]) -> list[str]:
    target = run.target_date
    target_events = [e for e in events if e.business_date == target]
    out = ["### 目标日对照", "", "系统各条记录取值相同的合并为一行，来源栏注明条数。", ""]
    if rc.kinds.get(target, "gap") == "gap":
        return out + ["核心缺日，未重算。", ""]
    rows = []
    for asset in ASSETS:
        d = rc.per_asset[asset][target]
        m = d.measures
        rows.append([
            NAMES[asset], "重算", STATE_NAMES[d.state], STATE_NAMES[d.candidate], d.candidate_days,
            f"{m.distance:.4%}" if m else "—", f"{m.band:.4%}" if m else "—",
            f"{m.slope:.4%}" if m else "—",
        ])  # fmt: skip
        same: dict[tuple, list[str]] = defaultdict(list)
        for e in target_events:
            item = e.asset(asset)
            same[(
                STATE_NAMES.get(item.get("state")), STATE_NAMES.get(item.get("candidate_state")),
                item.get("candidate_days"), _pct(item.get("distance_pct")),
                _pct(item.get("noise_band_pct")), _pct(item.get("slope_pct")),
            )].append(e.source)  # fmt: skip
        rows += [["", _sources(sources), *values] for values, sources in same.items()]
    headers = ["资产", "来源", "状态", "候选", "候选天数", "距 MA120", "噪声带", "20 日斜率"]
    out += [table(headers, rows), ""]
    stage_rows = [["重算", str(rc.stages[target]), KIND_NAMES[rc.kinds[target]]]]
    grouped: dict[tuple, list[str]] = defaultdict(list)
    for e in target_events:
        doc = e.document
        pair = (doc.get("current_stage"), doc.get("last_confirmed_stage"))
        grouped[(str(pair), str(doc.get("stage_reason")))].append(e.source)
    stage_rows += [[_sources(sources), *values] for values, sources in grouped.items()]
    headers = ["来源", "(current_stage, last_confirmed_stage)", "组合／原因"]
    return out + [table(headers, stage_rows), ""]


def _daily_table(run, rc, by_day, status) -> list[str]:
    rows: list[tuple[list[str], tuple]] = []
    for day in run.window:
        events = by_day.get(day, [])
        latest = max(events, key=lambda e: e.document.get("system_as_of", "")) if events else None
        key = (_label(rc, day), _system_label(latest) if latest else "无记录", status[day])
        if rows and rows[-1][1] == key:
            rows[-1][0].append(day)
        else:
            rows.append(([day], key))
    return [
        "### 逐日比对（相邻且结果相同的日子合并；系统列取当日最新一条记录）",
        "",
        table(
            ["日期", "重算", "系统", "比对"],
            [[compress_days(days, run.window), *key] for days, key in rows],
        ),
        "",
    ]


def _finding_table(run: Run, findings: list[Finding]) -> list[str]:
    out = [
        "### 差异明细",
        "",
        "同一字段、同一系统记录来源和结论的日子合并；逐日取值见上表。",
        "",
    ]
    grouped: dict[tuple, list[tuple]] = defaultdict(list)
    for f in findings:
        for name, mine, theirs, kind in f.items:
            note = f.cause if kind == DIFFERENT else kind
            key = (name, f"{f.event.batch}（{f.event.model}）", note)
            grouped[key].append((f.day, str(mine), str(theirs)))
    if not grouped:
        return out + ["无。", ""]
    rows = []
    for (name, source, note), found in sorted(grouped.items(), key=lambda kv: (min(kv[1]), kv[0])):
        pairs = sorted({(m, t) for _, m, t in found})
        values = "；".join(f"{m} → {t}" for m, t in pairs) if len(pairs) <= 2 else "逐日不同"
        days = sorted({d for d, _, _ in found})
        rows.append([compress_days(days, run.window), name, values, source, note])
    return out + [table(["日期", "字段", "重算 → 系统", "系统记录来自", "结论"], rows), ""]


def _conflict_table(run: Run, rc: Recompute, by_day) -> list[str]:
    """Observation only (A4): the documents ask for a ``transition_pending`` mark on these days
    but do not say which output field carries it."""
    rows = []
    for asset in ASSETS:
        groups: dict[tuple, list[str]] = defaultdict(list)
        for day in run.window:
            got = rc.per_asset[asset].get(day)
            if not (got and got.measures and got.measures.conflict()):
                continue
            reasons = sorted({str(e.asset(asset).get("reason")) for e in by_day.get(day, [])})
            groups[(STATE_NAMES[got.state], "、".join(reasons) or "无记录")].append(day)
        for (state, reasons), days in groups.items():
            rows.append([NAMES[asset], compress_days(days, run.window), state, reasons])
    if not rows:
        return []
    return [
        "### 位置与斜率反向的日子（只列观察，A4）",
        "",
        "文档要求这些日子保留稳定方向并标记 `transition_pending`，但没有写明哪个输出字段承载该"
        "标记，所以不比对，只列出系统 `reason` 的取值。",
        "",
        table(["资产", "日期", "重算稳定方向", "系统 reason"], rows),
        "",
    ]
