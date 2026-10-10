"""Layer 1: was the data acquired? Daily metrics day by day, low-frequency metrics by period.

Daily: every open day of the metric's market calendar in the run's window, for every member,
is one cell, classified as held, not fetched, not published upstream, or calendar uncovered.
Monthly, quarterly and weekly: is the latest period due by the cutoff held, and how long after
its official publication was each period first stored.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from common import Receipt, Run, compress_days, iso_day, parse_time, table

HELD, NOT_FETCHED, NOT_PUBLISHED, UNCOVERED = "已持有", "未取到", "上游未发布", "日历未覆盖"
CLASSES = (HELD, NOT_FETCHED, NOT_PUBLISHED, UNCOVERED)
BEIJING = timezone(timedelta(hours=8))

# Market calendar per daily metric; anything not listed is domestic and uses the SSE calendar.
MARKET = {
    "CBOE_VIX_INDEX": "US_EQUITY",
    "NASDAQ_SOX_INDEX": "US_EQUITY",
    "EIA_BRENT_RBRTE": "US_EQUITY",
    "EIA_WTI_RWTC": "US_EQUITY",
    "UST10Y_NOMINAL_YIELD": "US_TREASURY",
    "UST2Y_NOMINAL_YIELD": "US_TREASURY",
    "CN_USDCNY_ECB_REFERENCE_CROSS": "TARGET",
    "CN_COMMODITY_CORE_NHII": "SHFE",
    "CN_COMMODITY_BROAD_NHCI": "SHFE",
    "CN_COMMODITY_EX_HOG_BASKET": "SHFE",
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": "SHFE",
}
WARRANTS = "CN_FUTURES_WARRANTS"  # one member per symbol, on its own exchange's calendar
OPERATIONAL = {"CN_TRADE_CALENDAR", "CN_RELEASE_SCHEDULE", "SOURCE_OBSERVED_AVAILABILITY"}
# Request parameters that only choose dates; the rest say which series a request asks for.
DATE_PARAMETERS = {
    "start_date", "end_date", "trade_date", "period", "date", "start_m", "end_m", "start_q",
    "end_q", "year", "definition_version",
}  # fmt: skip

# Official NBS release items (``release_schedule`` origin ``nbs:schedule_page``) and how far the
# released period lags the publication month: -1 is the previous month or quarter.
NBS_SCHEDULE = {
    "CN_CPI_HEADLINE": ("居民消费价格指数月度报告", -1),
    "CN_CORE_CPI": ("居民消费价格指数月度报告", -1),
    "CN_PPI": ("工业生产者价格指数月度报告", -1),
    "CN_PMI_ACTIVITY": ("采购经理指数月度报告", 0),
    "CN_PMI_INVENTORY": ("采购经理指数月度报告", 0),
    "CN_PMI_PRICES": ("采购经理指数月度报告", 0),
    "CN_INDUSTRIAL_VA": ("规模以上工业生产月度报告", -1),
    "CN_INDUSTRIAL_FINANCE": ("工业经济效益月度报告", -1),
    "CN_FINISHED_GOODS_INVENTORY": ("工业经济效益月度报告", -1),
    "CN_INVENTORY_TURNOVER": ("工业经济效益月度报告", -1),
    "CN_GDP": ("国民经济运行情况", -1),
    "CN_CAPACITY_UTILIZATION": ("全国工业产能利用率季度报告", -1),
}
LPR_RULE = "monthly_day_20_holiday_roll_0900_asia_shanghai"
LOW_FREQUENCIES = ("monthly", "quarterly", "weekly")


def scope_label(run: Run, metric: str) -> str:
    return "是" if metric in run.model_used else "否"


def _beijing(day: str, clock: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=BEIJING)


# --- daily --------------------------------------------------------------------------------


@dataclass
class Cell:
    metric: str
    member: str
    day: str
    status: str
    evidence: str = ""


@dataclass
class DailyResult:
    cells: list[Cell] = field(default_factory=list)
    calendar_of: dict[str, str] = field(default_factory=dict)
    members_of: dict[str, int] = field(default_factory=dict)
    # Held cells whose earliest declared public time is after the target day ends: acquired,
    # but the point-in-time rule keeps them out of the model (layer 2 reports that).
    public_after_target: list[tuple[Cell, str]] = field(default_factory=list)


@dataclass
class Holdings:
    """Claims stored by the cutoff in the window, per (metric, member)."""

    versions: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    public: dict[tuple[str, str, str], str] = field(default_factory=dict)
    dimensions: dict = field(default_factory=lambda: defaultdict(set))
    exchange_of: dict[str, str] = field(default_factory=dict)


def _member(metric: str, dimensions: str) -> tuple[str, str | None]:
    """The member key and, for warrants, the exchange whose calendar applies."""
    dims = json.loads(dimensions)
    if metric == WARRANTS:
        return dims.get("symbol", "?"), dims.get("exchange")
    return json.dumps(dims, ensure_ascii=False, sort_keys=True), None


def _display(member: str) -> str:
    return "—" if member == "{}" else member


def _holdings(run: Run, metrics: list[str]) -> Holdings:
    found = Holdings()
    marks = ",".join("?" * len(metrics))
    rows = run.db.execute(
        "SELECT metric_id, period_start, dimensions_json, definition_version,"
        " MIN(COALESCE(public_available_at, inferred_public_at)) FROM source_claim"
        f" WHERE metric_id IN ({marks}) AND period_kind = 'business_day'"
        " AND period_start BETWEEN ? AND ? AND available_at <= ?"
        " GROUP BY metric_id, period_start, dimensions_json, definition_version",
        (*metrics, run.window[0], run.target_date, run.cutoff),
    )
    for metric, day, dimensions, version, public_at in rows:
        member, exchange = _member(metric, dimensions)
        found.versions[(metric, member)][day].add(version)
        found.dimensions[(metric, member)].add(dimensions)
        if public_at:
            key = (metric, member, day)
            found.public[key] = min(public_at, found.public.get(key, public_at), key=parse_time)
        if exchange:
            found.exchange_of[member] = exchange
    return found


def _span(receipt: Receipt) -> tuple[str, str] | None:
    p = receipt.parameters
    start = p.get("start_date") or p.get("trade_date") or p.get("period") or p.get("date")
    end = p.get("end_date") or p.get("trade_date") or p.get("period") or p.get("date")
    if not start or not end:
        return None
    return iso_day(str(start)), iso_day(str(end))


def _signature(receipt: Receipt) -> tuple:
    """Which series a request asks for: its endpoint and every non-date parameter."""
    chosen = {k: v for k, v in receipt.parameters.items() if k not in DATE_PARAMETERS}
    return receipt.api_name, json.dumps(chosen, sort_keys=True, ensure_ascii=False)


def _member_receipts(run: Run, metric: str, member: str, holdings: Holdings) -> list[Receipt]:
    """Receipts that asked for this member's series.

    A request counts when its signature matches a request that, by the cutoff, stored claims
    for this member in the window. A member never held falls back to the receipts that
    declared the metric in a run (``full_run_acquisition``), for warrants only those that
    asked for its symbol.
    """
    if metric == WARRANTS:
        member_filter, params = "json_extract(s.dimensions_json, '$.symbol') = ?", [member]
    else:
        dims = sorted(holdings.dimensions.get((metric, member), ()))
        member_filter = f"s.dimensions_json IN ({','.join('?' * len(dims))})"
        params = dims
    producing = []
    if params:
        producing = run.receipts(
            "a.acquisition_id IN (SELECT x.acquisition_id FROM source_claim s"
            " JOIN source_claim_acquisition x ON x.claim_id = s.claim_id"
            " WHERE s.metric_id = ? AND s.period_kind = 'business_day'"
            f" AND s.period_start BETWEEN ? AND ? AND s.available_at <= ? AND {member_filter})",
            (metric, run.window[0], run.target_date, run.cutoff, *params),
        )
    if not producing:
        declared = run.receipts(
            "a.acquisition_id IN (SELECT acquisition_id FROM full_run_acquisition"
            " WHERE metric_ids_json LIKE ?)",
            (f'%"{metric}"%',),
        )
        if metric != WARRANTS:
            return declared
        # A warrant request names its symbol; one for another symbol says nothing here.
        return [r for r in declared if r.parameters.get("symbol") == member]
    signatures = {_signature(r) for r in producing}
    apis = sorted({api for api, _ in signatures})
    candidates = run.receipts(f"a.api_name IN ({','.join('?' * len(apis))})", tuple(apis))
    return [r for r in candidates if _signature(r) in signatures]


class RawRows:
    """Rows per day (and per symbol) in stored TuShare-shaped raw responses, parsed once."""

    def __init__(self, run: Run) -> None:
        self._run = run
        self._cache: dict[str, dict | None] = {}

    def count(self, raw_hash: str, day: str, symbol: str | None) -> int | None:
        """Rows for the day (and symbol); None when the raw is not TuShare-shaped."""
        if raw_hash not in self._cache:
            self._cache[raw_hash] = self._parse(raw_hash)
        parsed = self._cache[raw_hash]
        if parsed is None:
            return None
        return parsed.get((day, symbol), 0)

    def _parse(self, raw_hash: str) -> dict | None:
        try:
            payload = json.loads(self._run.artifact(raw_hash))
            fields, items = payload["data"]["fields"], payload["data"]["items"]
            day_field = next(f for f in ("trade_date", "cal_date", "date") if f in fields)
            day_at = fields.index(day_field)
            symbol_at = fields.index("symbol") if "symbol" in fields else None
            counts: dict = defaultdict(int)
            for item in items:
                day = iso_day(str(item[day_at]))
                counts[(day, None)] += 1
                if symbol_at is not None:
                    counts[(day, item[symbol_at])] += 1
        except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration):
            return None
        return counts


def _classify_missing(
    run: Run, receipts: list[Receipt], raw: RawRows, metric: str, member: str, day: str
) -> tuple[str, str]:
    """Decide from the newest receipt that covers the day and reached the source by the
    cutoff; newer attempts that never reached it (blocked, failed before sending) carry no
    upstream evidence and are only counted."""
    covering = [r for r in receipts if (s := _span(r)) and s[0] <= day <= s[1]]
    if not covering:
        return NOT_FETCHED, "无覆盖该日的取数回执"
    reached = [r for r in covering if run.reached_source(r)]
    if not reached:
        latest = covering[0]
        reason = latest.rejection_reason or latest.error_type or latest.state
        return NOT_FETCHED, (
            f"覆盖该日的 {len(covering)} 条回执截止前均未取得来源应答"
            f"（最近 {latest.acquisition_id}，{reason}）"
        )
    receipt = reached[0]
    skipped = covering.index(receipt)
    later = f"；其后另有 {skipped} 次未取得应答的尝试" if skipped else ""
    stamp = f"{receipt.acquisition_id}（{receipt.api_name}，{receipt.started_at[:10]}）"
    rows = raw.count(receipt.raw_hash, day, member if metric == WARRANTS else None)
    if rows == 0:
        return NOT_PUBLISHED, f"最近取得应答的原件 {stamp} 该日 0 行{later}"
    if rows:
        return NOT_FETCHED, f"原件 {stamp} 该日有 {rows} 行，但无声明{later}"
    one_day = _span(receipt) == (day, day) and run.validated_by_cutoff(receipt)
    if one_day and receipt.source_record_count == 0:
        return NOT_PUBLISHED, f"当日回执 {stamp} 来源记录为 0{later}"
    return NOT_FETCHED, (
        f"最近取得应答的回执 {stamp}（{receipt.state}）未产出该日声明；"
        f"原件非 TuShare 结构，无法逐日核对{later}"
    )


def daily(run: Run) -> DailyResult:
    excluded = OPERATIONAL | run.derived_only
    metrics = [m for m, d in run.catalog.items() if d["frequency"] == "daily" and m not in excluded]
    holdings = _holdings(run, metrics)
    raw, result = RawRows(run), DailyResult()
    days = _all_days(run.window[0], run.target_date)
    target_end = _beijing(run.target_date, "23:59:59.999999")
    warrant_symbols = {
        c["symbol"] for c in run.manifest["confirmation_rules"].get("warrant_conversions", [])
    }
    for metric in metrics:
        compatible = run.same_definition[metric]
        members = {member for (m, member) in holdings.versions if m == metric}
        if metric == WARRANTS:
            members |= warrant_symbols
        if not members:
            members = {"{}"} if not run.catalog[metric]["dimensions"] else {"（无任何声明）"}
        result.members_of[metric] = len(members)
        result.calendar_of[metric] = (
            "各品种交易所" if metric == WARRANTS else MARKET.get(metric, "SSE")
        )
        for member in sorted(members):
            name = holdings.exchange_of.get(member, "SHFE") if metric == WARRANTS else None
            name = name or MARKET.get(metric, "SSE")
            calendar = run.calendars.get(name)
            by_day = holdings.versions.get((metric, member), {})
            receipts: list[Receipt] | None = None
            for day in days:
                kind = calendar.classify(day) if calendar else "uncovered"
                if kind == "closed":
                    continue
                if kind == "uncovered":
                    result.cells.append(Cell(metric, member, day, UNCOVERED, f"{name} 日历"))
                    continue
                versions = by_day.get(day, set())
                if versions & compatible:
                    # Held; cells held only under an older catalog version with the same
                    # definition are counted apart.
                    old_only = run.catalog_version not in versions
                    cell = Cell(metric, member, day, HELD, "旧目录版本" if old_only else "")
                    result.cells.append(cell)
                    public_at = holdings.public.get((metric, member, day))
                    if public_at and parse_time(public_at) > target_end:
                        result.public_after_target.append((cell, public_at))
                    continue
                if receipts is None:
                    receipts = _member_receipts(run, metric, member, holdings)
                status, evidence = _classify_missing(run, receipts, raw, metric, member, day)
                if versions:
                    listed = "、".join(sorted(versions))
                    evidence = f"仅有定义不同的目录版本 {listed} 的声明；{evidence}"
                result.cells.append(Cell(metric, member, day, status, evidence))
    return result


def _all_days(first: str, last: str) -> list[str]:
    day, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while day <= end:
        out.append(day.isoformat())
        day += timedelta(days=1)
    return out


# --- monthly, quarterly, weekly -----------------------------------------------------------


def _period_label(frequency: str, period_end: str) -> str:
    year, month = int(period_end[:4]), int(period_end[5:7])
    if frequency == "quarterly":
        return f"{year}-Q{(month - 1) // 3 + 1}"
    if frequency == "weekly":
        iso = date.fromisoformat(period_end[:10]).isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{year}-{month:02d}"


def _shift(frequency: str, year: int, month: int, offset: int) -> str:
    if frequency == "quarterly":
        quarter = (month - 1) // 3 + offset  # zero-based quarter index of the release month
        year, quarter = year + quarter // 4, quarter % 4
        return f"{year}-Q{quarter + 1}"
    index = year * 12 + (month - 1) + offset
    return f"{index // 12}-{index % 12 + 1:02d}"


def _official_releases(run: Run, metric: str, frequency: str) -> tuple[dict[str, datetime], str]:
    """``{period: official publication time}`` and where that came from."""
    rule = run.catalog[metric].get("release_rule")
    if metric in NBS_SCHEDULE:
        item, offset = NBS_SCHEDULE[metric]
        rows = run.db.execute(
            "SELECT publish_date, publish_time FROM release_schedule"
            " WHERE batch_id = ? AND origin = 'nbs:schedule_page' AND item = ?",
            (run.run_id, item),
        ).fetchall()
        releases: dict[str, datetime] = {}
        for publish_date, publish_time in rows:
            year, month = int(publish_date[:4]), int(publish_date[5:7])
            if frequency == "quarterly" and month not in (1, 4, 7, 10):
                continue
            period = _shift(frequency, year, month, offset)
            when = _beijing(publish_date, publish_time or "09:30:00")
            releases[period] = min(when, releases.get(period, when))
        return releases, f"国家统计局发布日程「{item}」"
    if rule == LPR_RULE:
        sse = run.calendars["SSE"]
        releases = {}
        for day in sorted(d for d in sse.covered if d.endswith("-20")):
            rolled = date.fromisoformat(day)
            while sse.classify(rolled.isoformat()) == "closed":
                rolled += timedelta(days=1)
            if sse.classify(rolled.isoformat()) == "open":
                releases[day[:7]] = _beijing(rolled.isoformat(), "09:00:00")
        return releases, f"冻结发布规则 {rule}（按上交所日历顺延）"
    return {}, "无官方日程：应有期以截止前入库声明的公开时间推定，漏掉整期时无法发现"


@dataclass
class PeriodRow:
    metric: str
    frequency: str
    source: str
    due: str
    latest_held: str
    status: str
    note: str = ""


@dataclass
class DelayRow:
    metric: str
    period: str
    published: datetime
    stored: datetime | None
    deadline: datetime | None  # None: no calendar covers the grace day
    basis: str
    backfilled: bool


def _deadline(run: Run, published: datetime) -> tuple[datetime | None, str]:
    """End of the first domestic open day after the publication day (Beijing time).

    The SSE calendar decides; past its coverage the SHFE calendar stands in (mainland
    exchanges share holidays) and the row says so; past both there is no deadline.
    """
    sse, stand_in = run.calendars["SSE"], run.calendars.get("SHFE")
    day, note = published.astimezone(BEIJING).date(), ""
    for _ in range(40):
        day += timedelta(days=1)
        kind = sse.classify(day.isoformat())
        if kind == "uncovered" and stand_in is not None:
            kind, note = stand_in.classify(day.isoformat()), "；上交所日历未覆盖，按 SHFE 代判"
        if kind == "uncovered":
            return None, "；日历未覆盖宽限日"
        if kind == "open":
            return _beijing(day.isoformat(), "23:59:59"), note
    return None, "；40 日内无开市日"


def low_frequency(run: Run) -> tuple[list[PeriodRow], list[DelayRow], list[str]]:
    cutoff = parse_time(run.cutoff)
    window_start = _beijing(run.window[0], "00:00:00")
    system_start = parse_time(run.system_start)
    rows, delays, events = [], [], []
    for metric, definition in run.catalog.items():
        frequency = definition["frequency"]
        if frequency == "event":
            if metric not in OPERATIONAL:
                events.append(metric)
            continue
        if frequency not in LOW_FREQUENCIES or metric in run.derived_only:
            continue
        compatible = sorted(run.same_definition[metric])
        claims = run.db.execute(
            "SELECT period_end, dimensions_json, available_at,"
            " COALESCE(public_available_at, inferred_public_at, release_at)"
            " FROM source_claim WHERE metric_id = ? AND period_kind != 'business_day'"
            f" AND available_at <= ? AND definition_version IN ({','.join('?' * len(compatible))})",
            (metric, run.cutoff, *compatible),
        ).fetchall()
        stored: dict[str, datetime] = {}
        declared: dict[str, datetime] = {}
        members: dict[str, set[str]] = defaultdict(set)
        for period_end, dimensions, available_at, public_at in claims:
            period = _period_label(frequency, period_end)
            at = parse_time(available_at)
            stored[period] = min(at, stored.get(period, at))
            members[period].add(dimensions)
            if public_at:
                when = parse_time(public_at)
                declared[period] = min(when, declared.get(period, when))
        official, source = _official_releases(run, metric, frequency)
        published = {**declared, **official}
        due_candidates = [p for p, when in published.items() if when <= cutoff]
        due = max(due_candidates) if due_candidates else "—"
        latest = max(stored) if stored else "—"
        status = "无法判定" if due == "—" else "在" if due in stored else "缺"
        note = ""
        previous = [p for p in members if p < due]
        if due in members and previous:
            gone = members[max(previous)] - members[due]
            if gone:
                note = f"上一期有、本期缺的成员 {len(gone)} 个"
        rows.append(PeriodRow(metric, frequency, source, due, latest, status, note))
        for period, when in sorted(published.items()):
            if not (window_start <= when <= cutoff):
                continue
            first = stored.get(period)
            limit, note = _deadline(run, when)
            if limit is None:
                late = first is None or first > when
            elif first is None:
                late = cutoff > limit  # still inside the grace when the run froze
            else:
                late = first > limit
            if late:
                basis = ("官方日程" if period in official else "声明的公开可用时间") + note
                delays.append(
                    DelayRow(metric, period, when, first, limit, basis, when < system_start)
                )
    return rows, delays, events


# --- report -------------------------------------------------------------------------------


def _counts(cells: list[Cell]) -> dict[str, int]:
    counts = dict.fromkeys(CLASSES, 0)
    for cell in cells:
        counts[cell.status] += 1
    return counts


def _plan_window(run: Run) -> list[str] | None:
    row = run.db.execute(
        "SELECT json_extract(document_json, '$.daily_window.dates') FROM full_run_gap_plan"
        " WHERE run_id = ? AND phase = 'final'",
        (run.run_id,),
    ).fetchone()
    return json.loads(row[0]) if row and row[0] else None


def _fmt(when: datetime | None) -> str:
    return when.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M") if when else "未入库"


def _overrun(row: DelayRow) -> str:
    if row.deadline is None:
        return "宽限无法判定（日历未覆盖）"
    if row.stored is None:
        return "到截止未入库，已超宽限"
    hours = (row.stored - row.deadline).total_seconds() / 3600
    return f"{hours / 24:.1f} 天" if hours >= 24 else f"{hours:.1f} 小时"


def _conclusion(run: Run, result: DailyResult, periods, delays) -> list[str]:
    out = ["### 结论", ""]
    for label, chosen in (("目录全部指标", None), ("仅模型用到的指标", run.model_used)):

        def keep(metric: str, chosen=chosen) -> bool:
            return chosen is None or metric in chosen

        cells = [c for c in result.cells if keep(c.metric)]
        counts = _counts(cells)
        missing = len({c.metric for c in cells if c.status in (NOT_FETCHED, NOT_PUBLISHED)})
        lf = [p for p in periods if keep(p.metric)]
        late = [d for d in delays if keep(d.metric) and d.deadline is not None]
        unknown = sum(1 for d in delays if keep(d.metric) and d.deadline is None)
        out.append(
            f"- **{label}**：日频应有 {sum(counts.values())} 格，已持有 {counts[HELD]}，"
            f"未取到 {counts[NOT_FETCHED]}，上游未发布 {counts[NOT_PUBLISHED]}，"
            f"日历未覆盖 {counts[UNCOVERED]}（有缺格的指标 {missing} 项）；"
            f"低频 {len(lf)} 项中最新应有期缺 {sum(p.status == '缺' for p in lf)} 项、"
            f"无法判定 {sum(p.status == '无法判定' for p in lf)} 项；"
            f"超过宽限的期次 {len(late)} 个（其中发布早于系统启用 {run.system_start[:10]} 的"
            f" {sum(d.backfilled for d in late)} 个），宽限无法判定 {unknown} 个。"
        )
    sse_end = max(run.calendars["SSE"].covered)
    judged = parse_time(run.cutoff).astimezone(BEIJING).date().isoformat()
    if sse_end < judged:
        out.append(
            f"- 上交所日历原件只覆盖到 {sse_end}，没有覆盖到判定日 {judged}。这是 lookback/30"
            " 的特征：生产的时效判定在这段会按工作日推定。本报告的宽限计算在这段改用 SHFE"
            " 日历代判。"
        )
    return [*out, ""]


def _daily_tables(run: Run, result: DailyResult) -> list[str]:
    out = ["### 日频：逐交易日 × 成员", ""]
    by_metric: dict[str, list[Cell]] = defaultdict(list)
    for cell in result.cells:
        by_metric[cell.metric].append(cell)
    summary = []
    for metric, cells in by_metric.items():
        counts = _counts(cells)
        old_only = sum(1 for c in cells if c.status == HELD and c.evidence)
        summary.append(
            [
                metric,
                scope_label(run, metric),
                result.calendar_of.get(metric, ""),
                result.members_of.get(metric, 0),
                sum(counts.values()),
                *(counts[c] for c in CLASSES),
                old_only,
            ]
        )
    headers = ["指标", "模型用到", "日历", "成员", "应有格", *CLASSES, "其中仅旧目录版本"]
    out += [table(headers, summary), "", "缺格明细（同一指标、成员、类别、依据的日期合并）：", ""]
    grouped: dict[tuple, list[str]] = defaultdict(list)
    for cell in result.cells:
        if cell.status != HELD:
            grouped[(cell.metric, cell.member, cell.status, cell.evidence)].append(cell.day)
    # Consecutive means consecutive on the union of every calendar's open days.
    all_open = sorted(set().union(*(c.open_days for c in run.calendars.values())))
    detail = [
        [
            metric,
            scope_label(run, metric),
            _display(member),
            status,
            compress_days(days, all_open),
            evidence,
        ]
        for (metric, member, status, evidence), days in sorted(grouped.items())
    ]
    headers = ["指标", "模型用到", "成员", "类别", "日期", "依据"]
    out.append(table(headers, detail) if detail else "无。")
    out += [
        "",
        f"已持有、但声明的公开时间晚于目标日 {run.target_date} 结束的格"
        "（按时点规则不进模型，由第二层报告）：",
        "",
    ]
    late_public = [
        [cell.metric, _display(cell.member), cell.day, _fmt(parse_time(public_at))]
        for cell, public_at in result.public_after_target
    ]
    out.append(table(["指标", "成员", "日期", "公开时间"], late_public) if late_public else "无。")
    return [*out, ""]


def _low_frequency_tables(run: Run, periods: list[PeriodRow], delays: list[DelayRow]) -> list[str]:
    out = ["### 月频、季频、周频：最新应有期", ""]
    headers = ["指标", "模型用到", "频率", "发布依据", "最新应有期", "最新持有期", "状态", "备注"]
    rows = [
        [
            p.metric,
            scope_label(run, p.metric),
            p.frequency,
            p.source,
            p.due,
            p.latest_held,
            p.status,
            p.note,
        ]
        for p in periods
    ]
    out += [table(headers, rows), ""]
    out += [
        "### 月频、季频、周频：发布到入库超过宽限的期次",
        "",
        "宽限截止为发布日后第 1 个国内开市日结束（北京时间）；到冻结截止仍在宽限内的不列。",
        "",
    ]
    headers = [
        "指标",
        "模型用到",
        "期次",
        "发布",
        "依据",
        "首次入库",
        "宽限截止",
        "超出",
        "启用前发布",
    ]
    rows = [
        [
            d.metric,
            scope_label(run, d.metric),
            d.period,
            _fmt(d.published),
            d.basis,
            _fmt(d.stored),
            _fmt(d.deadline) if d.deadline else "—",
            _overrun(d),
            "是" if d.backfilled else "否",
        ]
        for d in sorted(delays, key=lambda d: (d.backfilled, d.metric, d.period))
    ]
    out.append(table(headers, rows) if rows else "无。")
    return [*out, ""]


def section(run: Run) -> str:
    result = daily(run)
    periods, delays, events = low_frequency(run)
    plan = _plan_window(run)
    judged = parse_time(run.cutoff).astimezone(BEIJING).date().isoformat()

    out = ["## 第一层：取数是否完整", "", *_conclusion(run, result, periods, delays)]
    out += ["### 日历与窗口", ""]
    plan_note = (
        ""
        if plan is None
        else "与最终计划的 `daily_window` 一致。"
        if plan == run.window
        else "**与最终计划的 `daily_window` 不一致。**"
    )
    out.append(
        f"窗口：{run.window[0]}～{run.window[-1]}，上交所 {len(run.window)} 个交易日；"
        f"截止 {run.cutoff}（判定日 {judged}）。{plan_note}"
    )
    calendars = [
        [name, c.source, f"{min(c.covered)}～{max(c.covered)}"]
        for name, c in sorted(run.calendars.items())
    ]
    out += ["", table(["日历", "来源", "覆盖"], calendars), ""]
    out += _daily_tables(run, result)
    out += _low_frequency_tables(run, periods, delays)
    out += [
        "### 不在本层核对范围",
        "",
        f"- 运维类：{'、'.join(sorted(OPERATIONAL & set(run.catalog)))}（日历本身见上表）。",
        f"- 仅有派生值（第一层第三条，票 02）：{'、'.join(sorted(run.derived_only))}。",
        f"- 事件型（无固定期次）：{'、'.join(events) or '无'}。",
        "",
    ]
    return "\n".join(out)
