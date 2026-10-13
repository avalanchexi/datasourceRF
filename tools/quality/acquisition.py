"""Layer 1: was the data acquired? Daily metrics day by day, low-frequency metrics by period.

Daily: every open day of the metric's market calendar in the run's window, for every member,
is one cell, classified as held, not fetched, not published upstream, or calendar uncovered.
Two kinds are checked under their own requirement instead: metrics read as a current value
from announcements (a day whose announcement carries no new value is not due), and metrics
needed only at the latest day and the value it is compared with (other days are not due).
Monthly, quarterly and weekly: is the latest period due by the cutoff held, and how long after
its official publication was each period first stored. A period published in the window with
no claim left is told apart by the run's frozen final plan and the stored receipts: stored and
later removed by retention, never in the plan's demand, or not fetched. Removed members are
listed one by one, also of periods other members of which are still held.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from common import Calendar, Receipt, Run, compress_days, iso_day, parse_time, table

HELD, NOT_FETCHED, NOT_PUBLISHED, UNCOVERED = "已持有", "未取到", "上游未发布", "日历未覆盖"
CLASSES = (HELD, NOT_FETCHED, NOT_PUBLISHED, UNCOVERED)
# Cells that are not due under the metric's own requirement: not counted among due cells.
NO_NEW_VALUE, OUT_OF_DEMAND = "公告无新值", "不在需求内"
NOT_DUE = (NO_NEW_VALUE, OUT_OF_DEMAND)
RECOVERABLE = "原件含值、未入库，待重处理（票 09 线 B）"
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
# Daily metrics needed only at the latest day plus the earlier value it is compared with, not
# over the whole window: P2 context (user decisions 2026-10-10, audit ticket 09: the central
# parity; 2026-10-11, residual ticket 04: the 16:30 close and SOX, the same way).
LATEST_ONLY = {
    "CN_USDCNY_CENTRAL_PARITY": (
        "P2 参考指标，只要最新值和比较上下文（用户 2026-10-10 决定，票 09）"
    ),
    "CN_USDCNY_CLOSE_1630": (
        "P2 参考指标，只要最新值和比较上下文，同人民币中间价（用户 2026-10-11 决定，残余 04）"
    ),
    "NASDAQ_SOX_INDEX": (
        "P2 参考指标，只要最新值和比较上下文，同人民币中间价（用户 2026-10-11 决定，残余 04）"
    ),
}
# Daily metrics with no acquisition path at all: wherever their cells are counted the report
# says so, so a narrower requirement does not hide the gap.
NO_PATH = {
    "NASDAQ_SOX_INDEX": "受限授权缺口（ADR-0029）：无取数路径、不检索，应有格照记未取到",
}

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
# A low-frequency period published in the window with no claim left by the time of the audit.
PURGED = "已入库后被清理"
ABSENT = (PURGED, OUT_OF_DEMAND, NOT_FETCHED)
UNKNOWN_MEMBER = "成员不明"  # a removed period nothing names a member of


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
    # Metrics checked under their own requirement (announcements, latest only): per
    # (metric, member) what that requirement is and what it found outside the cells.
    rules: dict[tuple[str, str], RuleNote] = field(default_factory=dict)
    # Missing cells whose announcement's stored parse holds the value: (cell, receipt, values).
    recoverable: list[tuple[Cell, str, str]] = field(default_factory=list)
    # Gaps outside a latest-only metric's demand: not due, but the class and evidence the day
    # would have had, keyed (metric, member, day). Information only; layer 2 reads it for the
    # final plan's periods.
    outside: dict[tuple[str, str, str], tuple[str, str]] = field(default_factory=dict)


@dataclass
class RuleNote:
    basis: str
    note: str


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
            " WHERE metric_ids_json LIKE ? AND phase != 'referenced')",
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


@dataclass(frozen=True)
class Answer:
    """One stored TuShare-shaped raw response: its fields, its row count, rows per day, and
    the rows themselves by day unless parsed for counting only. ``damaged``: some row is not
    a list as long as the fields or has no valid date, so no day's rows are known for sure."""

    fields: list[str]
    total: int
    counts: dict[str, int]
    by_day: dict[str, list[list]] | None
    damaged: bool

    def rows(self, day: str, symbol: str | None = None) -> list[list] | None:
        """The day's rows (of ``symbol``); None when a symbol is asked of an answer that has
        rows that day but no symbol column."""
        rows = (self.by_day or {}).get(day, [])
        if symbol is None or not rows:
            return rows
        if "symbol" not in self.fields:
            return None
        at = self.fields.index("symbol")
        return [row for row in rows if row[at] == symbol]


def _cut_short(receipt: Receipt, answer: Answer) -> bool:
    """The answer holds as many rows as the request's ``limit``: later rows may be missing."""
    try:
        limit = int(str(receipt.parameters.get("limit", "")).strip())
    except ValueError:
        return False  # no usable limit: the request was not paged
    return limit > 0 and answer.total >= limit


def _day_of(value) -> str | None:
    """A row's date as ``YYYY-MM-DD``, or None when it is not a valid date."""
    if not isinstance(value, (str, int)):
        return None
    day = iso_day(str(value))
    try:
        return date.fromisoformat(day).isoformat() if len(day) == 10 else None
    except ValueError:
        return None


class RawRows:
    """Stored TuShare-shaped raw responses, parsed once (rows kept only when asked for)."""

    def __init__(self, run: Run) -> None:
        self._run = run
        self._cache: dict[str, Answer | None] = {}

    def answer(self, receipt: Receipt, rows: bool = True) -> Answer | None:
        """The receipt's raw response; None when it is not TuShare-shaped."""
        cached = self._cache.get(receipt.raw_hash, False)
        if cached is False or (rows and cached is not None and cached.by_day is None):
            cached = self._cache[receipt.raw_hash] = self._parse(receipt.raw_hash, rows)
        return cached

    def _parse(self, raw_hash: str, keep: bool) -> Answer | None:
        try:
            payload = json.loads(self._run.artifact(raw_hash))
            fields, items = payload["data"]["fields"], payload["data"]["items"]
            day_field = next(f for f in ("trade_date", "cal_date", "date") if f in fields)
            day_at = fields.index(day_field)
            counts: dict[str, int] = defaultdict(int)
            by_day: dict[str, list[list]] = defaultdict(list)
            damaged = False
            for item in items:
                whole = isinstance(item, list) and len(item) == len(fields)
                day = _day_of(item[day_at]) if whole else None
                if day is None:
                    damaged = True
                    continue
                counts[day] += 1
                if keep:
                    by_day[day].append(item)
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            return None
        kept = dict(by_day) if keep else None
        return Answer(list(fields), len(items), dict(counts), kept, damaged)


# What one member needs from a day's rows, beyond "some row that day" (ticket 13): the field
# holding its value and, for a total over several row keys, the key field and the keys it
# needs. ``member`` maps the member's dimensions to (needed keys or None, value field).
@dataclass(frozen=True)
class RowRule:
    key_field: str | None
    member: Callable[[dict], tuple[tuple[str, ...] | None, str]]
    meaning: str


# Margin scopes and the exchanges each one totals (the current two-exchange member and the
# older all-exchange ones).
SCOPE_EXCHANGES = {
    "sse_szse": ("SSE", "SZSE"),
    "all_exchanges": ("SSE", "SZSE", "BSE"),
    "SSE+SZSE+BSE": ("SSE", "SZSE", "BSE"),
}
MARGIN_FIELDS = {"financing_balance": "rzye", "financing_buy_amount": "rzmre"}
SHIBOR_FIELDS = {"overnight": "on", "1w": "1w", "3m": "3m"}
VALUATION_FIELDS = {"price_earnings": "pe", "price_book": "pb", "turnover_rate": "turnover_rate"}
MEMBER_ROWS = {
    "CN_MARGIN_BALANCE_SSE_SZSE": RowRule(
        "exchange_id",
        lambda d: (SCOPE_EXCHANGES[d["scope"]], MARGIN_FIELDS[d["measure"]]),
        "两融合计：成员 scope 所含交易所各一行",
    ),
    "CN_SHIBOR_ON_1W_3M": RowRule(
        None, lambda d: (None, SHIBOR_FIELDS[d["tenor"]]), "SHIBOR：当日一行，各期限一列"
    ),
    "CN_INDEX_VALUATION": RowRule(
        "ts_code",
        lambda d: ((d["index"],), VALUATION_FIELDS[d["measure"]]),
        "指数估值：该指数一行，各估值字段一列",
    ),
}
# Members built from several raw answers per day. True: every answer the member was ever
# built from is needed every day (breadth: daily bars and factors). False: which answers a
# day needs changes over time (the basket's contracts roll), so the script does not infer it
# and only all of them empty counts as nothing published.
MULTI_RAW = {
    "CN_EQ_ADV_DEC": True,
    "CN_EQ_AD_RATIO": True,
    "CN_EQ_ADV_AMOUNT_SHARE": True,
    "CN_EQ_NEW_HIGH_LOW_90": True,
    "CN_EQ_NEW_HIGH_LOW_250": True,
    "CN_EQ_ABOVE_MA90": True,
    "CN_EQ_ABOVE_MA250": True,
    "CN_COMMODITY_EX_HOG_BASKET": False,
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": False,
}
CALENDAR_APIS = {"trade_cal", "fut_trade_cal"}  # cover every day, published or not
PAGING = {"limit", "offset"}


def _check_rows(metric: str, member: str, answer: Answer, rows: list[list]) -> tuple[str, str]:
    """The member's own rows and value field among a day's rows (``MEMBER_ROWS``).

    Some of the keys it needs absent: the answer lacks part of the member, published upstream
    only in part. Rows all there but the value empty, the key column missing, or no rule for
    the member: not fetched, since an empty value or a damaged answer says nothing about
    publication."""
    rule = MEMBER_ROWS.get(metric)
    try:
        keys, value_field = rule.member(json.loads(member)) if rule else (None, "")
    except (KeyError, ValueError, TypeError):
        rule = None  # a member the rule does not know: count rows only
    if rule and not (
        isinstance(value_field, str) and (keys is None or all(isinstance(k, str) for k in keys))
    ):
        rule = None
    if rule is None:
        return NOT_FETCHED, f"该日有 {len(rows)} 行，但无声明"
    own = rows
    if keys is not None:
        if rule.key_field not in answer.fields:
            return NOT_FETCHED, f"该日有行，但应答无行键字段 {rule.key_field}，无法核对成员"
        at = answer.fields.index(rule.key_field)
        if any(not isinstance(row[at], str) or not row[at] for row in rows):
            return NOT_FETCHED, f"该日有 {rule.key_field} 为空或无效的行，无法核对成员"
        present = {row[at] for row in rows}
        lacking = [k for k in keys if k not in present]
        if lacking:
            return NOT_PUBLISHED, (
                f"应答该日缺 {'、'.join(lacking)}（{rule.meaning}，需 {'、'.join(keys)}；"
                f"有 {'、'.join(sorted(present))}），上游部分未发布"
            )
        own = [row for row in rows if row[at] in keys]
    if value_field not in answer.fields:
        return NOT_FETCHED, f"该日有行，但应答无字段 {value_field}"
    at = answer.fields.index(value_field)
    empty = [row for row in own if row[at] is None or row[at] == ""]
    if empty:
        return NOT_FETCHED, (
            f"该日所需行齐全，但 {len(empty)} 行的 {value_field} 为空（空值不算上游未发布），无声明"
        )
    held = f"（{'、'.join(keys)}）" if keys else ""
    return NOT_FETCHED, f"该日所需行齐全{held}、{value_field} 有值，但无声明"


def _series(receipt: Receipt) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Which series a request asks for, its pages taken together: the endpoint and every
    parameter that neither chooses dates nor pages."""
    chosen = sorted(
        (k, str(v)) for k, v in receipt.parameters.items() if k not in DATE_PARAMETERS | PAGING
    )
    return receipt.api_name, tuple(chosen)


def _first_page(receipt: Receipt) -> bool:
    return str(receipt.parameters.get("offset", "0")) in ("0", "")


def _classify_multi(
    run: Run, metric: str, receipts: list[Receipt], raw: RawRows, day: str
) -> tuple[str, str]:
    """A member built from several answers per day (``MULTI_RAW``).

    Each series the member's receipts ask for by date (calendars aside) is judged by its
    newest first page that covers the day and reached the source: a first page not cut short
    holds every row of the request. A series the member always needs with no such page, or a
    page cut short with no row that day, leaves the member not fetched."""
    series: dict[tuple, list[Receipt]] = defaultdict(list)
    for receipt in receipts:  # newest first
        span = _span(receipt)
        if receipt.api_name in CALENDAR_APIS or span is None:
            continue
        found = series[_series(receipt)]  # known to the member, covering the day or not
        if span[0] <= day <= span[1] and _first_page(receipt):
            found.append(receipt)
    if not MULTI_RAW[metric]:  # needs only what covers the day
        series = defaultdict(list, {k: v for k, v in series.items() if v})
    if not series:
        return NOT_FETCHED, "无覆盖该日的取数回执（交易日历除外）"
    counts, unanswered = {}, []
    for key, covering in sorted(series.items()):
        label = " ".join([key[0], *(v for _, v in key[1])])
        receipt = next((r for r in covering if run.reached_source(r)), None)
        answer = raw.answer(receipt, rows=False) if receipt else None
        if not covering:
            unanswered.append(f"{label} 无覆盖该日的回执")
        elif receipt is None:
            unanswered.append(f"{label} 覆盖该日的 {len(covering)} 条回执截止前均未取得应答")
        elif answer is None:
            unanswered.append(f"{label}（{receipt.acquisition_id}）原件非 TuShare 结构")
        elif answer.damaged:
            unanswered.append(f"{label}（{receipt.acquisition_id}）原件有结构不全或日期无效的行")
        elif not answer.counts.get(day) and _cut_short(receipt, answer):
            unanswered.append(f"{label}（{receipt.acquisition_id}）达到 limit 行数（分页不全）")
        else:
            counts[key] = (label, answer.counts.get(day, 0))
    shown = "、".join(f"{label} {n} 行" for label, n in counts.values())
    if unanswered:
        return NOT_FETCHED, "；".join(unanswered) + (f"；{shown}" if shown else "")
    empty = [label for label, n in counts.values() if n == 0]
    if empty and len(empty) == len(counts):
        return NOT_PUBLISHED, f"所需原件该日均 0 行（{shown}）"
    if empty and MULTI_RAW[metric]:
        return NOT_PUBLISHED, f"应答该日缺 {'、'.join(empty)}（{shown}），上游部分未发布"
    if empty:
        return NOT_FETCHED, (
            f"部分原件该日 0 行（{shown}）；所需合约随换月而变，脚本不推断，不判上游未发布"
        )
    return NOT_FETCHED, f"所需原件该日均有行（{shown}），但无声明"


def _classify_missing(
    run: Run, receipts: list[Receipt], raw: RawRows, metric: str, member: str, day: str
) -> tuple[str, str]:
    """Decide from the newest receipt that covers the day and reached the source by the
    cutoff; newer attempts that never reached it (blocked, failed before sending) carry no
    upstream evidence and are only counted. Members needing several row keys or answers a
    day are judged by what they need (``MEMBER_ROWS``, ``MULTI_RAW``); an answer possibly cut
    short (``limit``) is never evidence that something was not published."""
    if metric in MULTI_RAW:
        return _classify_multi(run, metric, receipts, raw, day)
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
    answer = raw.answer(receipt)
    if answer is not None:
        rows = answer.rows(day, member if metric == WARRANTS else None)
        if answer.damaged or rows is None:
            flaw = "有结构不全或日期无效的行" if answer.damaged else "该日有行但缺 symbol 列"
            return NOT_FETCHED, f"原件 {stamp} {flaw}，无法逐日核对{later}"
        if rows:
            status, finding = _check_rows(metric, member, answer, rows)
            text = f"原件 {stamp} {finding}{later}"
        else:
            status, text = NOT_PUBLISHED, f"最近取得应答的原件 {stamp} 该日 0 行{later}"
        if status == NOT_PUBLISHED and _cut_short(receipt, answer):
            return NOT_FETCHED, (
                f"原件 {stamp} 行数达到请求的 limit，可能分页不全，该日缺行不作上游未发布的证据"
                f"{later}"
            )
        return status, text
    one_day = _span(receipt) == (day, day) and run.validated_by_cutoff(receipt)
    if one_day and receipt.source_record_count == 0:
        return NOT_PUBLISHED, f"当日回执 {stamp} 来源记录为 0{later}"
    return NOT_FETCHED, (
        f"最近取得应答的回执 {stamp}（{receipt.state}）未产出该日声明；"
        f"原件非 TuShare 结构，无法逐日核对{later}"
    )


# --- daily metrics read as a current value, or needed only at the latest day ----------------


@dataclass
class Announced:
    """A daily metric the frozen rules read as a current value: a new value comes only with
    an announcement, and the rule's ``notices`` metric marks the days that had one.

    ``documents`` maps a day to that day's receipts of the metric's release family, newest
    first, each with the hash of its stored parse (``None``: no parse in hand by the cutoff);
    the parse itself is read only for the days that need it."""

    family: str
    notice: tuple[str, dict]
    documents: dict[str, list[tuple[str, str | None]]]
    notice_days: frozenset[str]


def _announced_metrics(run: Run) -> dict[str, tuple[str, dict]]:
    """``{metric: (notice metric, notice dimensions)}`` for every confirmation rule that names
    the announcements its metric is read from (``notices``)."""
    found: dict[str, tuple[str, dict]] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            notices = node.get("notices")
            if isinstance(notices, dict) and node.get("metric_id") in run.catalog:
                found[node["metric_id"]] = (notices["metric_id"], notices.get("dimensions") or {})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(run.manifest["confirmation_rules"])
    return found


def _load_announced(run: Run, metric: str, notice: tuple[str, dict]) -> Announced:
    family = run.catalog[metric].get("release_event_family") or ""
    documents: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    rows = run.db.execute(
        "SELECT acquisition_id, json_extract(parameters_json, '$.period'), normalized_hash,"
        " validated_at FROM acquisition_request WHERE json_extract(parameters_json, '$.family') = ?"
        " AND started_at <= ? AND raw_hash IS NOT NULL AND received_at <= ?"
        " ORDER BY started_at DESC, acquisition_id",
        (family, run.cutoff, run.cutoff),
    )
    for acquisition, period, normalized, validated in rows:
        if not period:
            continue
        in_hand = normalized if validated and validated <= run.cutoff else None
        documents[iso_day(str(period))].append((acquisition, in_hand))
    notice_metric, notice_dims = notice
    notice_days = frozenset(
        day
        for day, dimensions in run.db.execute(
            "SELECT DISTINCT period_start, dimensions_json FROM source_claim"
            " WHERE metric_id = ? AND period_kind = 'business_day' AND available_at <= ?",
            (notice_metric, run.cutoff),
        )
        if json.loads(dimensions) == notice_dims
    )
    return Announced(family, notice, dict(documents), notice_days)


def _day_values(run: Run, scalars: list, metric: str, dims: dict | None, day: str) -> list[str]:
    """Values a stored parse gives ``metric`` for the member ``dims`` (``None``: any) on
    ``day``, in a unit the frozen definition allows."""
    definition = run.catalog.get(metric, {})
    units = set(definition.get("allowed_units") or [definition.get("unit")])
    return sorted(
        {
            str(s["value"])
            for s in scalars
            if isinstance(s, dict)
            and isinstance(s.get("unit"), str)
            and isinstance(s.get("value"), (int, float, str))
            and s.get("metric_id") == metric
            and str(s.get("period_start") or s.get("period_end") or "")[:10] == day
            and (dims is None or (s.get("dimensions") or {}) == dims)
            and s.get("unit") in units
        }
    )


def _is_zero(value: str) -> bool:
    try:
        return float(value) == 0
    except ValueError:
        return False


def _classify_announced(
    run: Run, rule: Announced, metric: str, member: str, day: str
) -> tuple[str, str, tuple[str, str] | None]:
    """A day without a claim of an announced metric, judged by that day's announcements.

    A stored parse holding the value: acquired, not stored. Every parse giving the
    ``notices`` metric zero: no operation, so no new value; the current value stands and the
    cell is not due. Anything else (a parse whose notice value is nonzero or missing, no
    parse, no announcement) leaves the cell not fetched."""
    dims = json.loads(member) if member.startswith("{") else None  # None: never held
    parsed = []
    for acquisition, normalized in rule.documents.get(day, []):
        scalars = run.scalars(normalized) if normalized else None
        if scalars is not None:
            parsed.append((acquisition, scalars))
    for acquisition, scalars in parsed:
        values = _day_values(run, scalars, metric, dims, day)
        if values:
            shown = "、".join(values)
            evidence = f"{RECOVERABLE}：当日公告的已存解析件含该值（{shown}），截止前无声明"
            return NOT_FETCHED, evidence, (acquisition, shown)
    notice_metric, notice_dims = rule.notice
    if parsed:
        per_parse = [_day_values(run, s, notice_metric, notice_dims, day) for _, s in parsed]
        notices = {v for values in per_parse for v in values}
        if all(values and all(_is_zero(v) for v in values) for values in per_parse):
            return (
                NO_NEW_VALUE,
                f"当日公告已解析：{notice_metric} 为 0，不含该指标的值；当日无操作、无新值，"
                "现行值沿用此前公告",
                None,
            )
        shown = "、".join(sorted(notices)) or "无"
        gaps = "（有解析件缺该值）" if not all(per_parse) else ""
        return (
            NOT_FETCHED,
            f"当日公告已解析，但不含该指标的值，{notice_metric} 为 {shown}{gaps}："
            "无法确认当日无新值",
            None,
        )
    others = len(rule.documents.get(day, []))
    if others:
        return (
            NOT_FETCHED,
            f"当日 {rule.family} 回执 {others} 条已取得应答，但截止前都没有可读的公告解析件",
            None,
        )
    if day in rule.notice_days:
        return (
            NOT_FETCHED,
            f"截止前无当日 {rule.family} 公告回执；当日有 {notice_metric} 声明，"
            "但其来源没有可逐项核对的公告解析件",
            None,
        )
    return NOT_FETCHED, f"截止前无当日 {rule.family} 公告回执，也无当日 {notice_metric} 声明", None


def _base_before(run: Run, metric: str, member: str, compatible: frozenset[str]) -> str:
    """The newest claim of the member dated before the window: the value current when the
    window opens, as ``day（values）``."""
    rows = run.db.execute(
        "SELECT period_start, dimensions_json, definition_version, value FROM source_claim"
        " WHERE metric_id = ? AND period_kind = 'business_day' AND period_start < ?"
        " AND available_at <= ?",
        (metric, run.window[0], run.cutoff),
    )
    found: dict[str, set[str]] = defaultdict(set)
    for day, dims, version, value in rows:
        if version in compatible and _member(metric, dims)[0] == member:
            found[day].add(str(value))
    if not found:
        return "窗口前无已持有的声明"
    day = max(found)
    return f"窗口前最近声明 {day}（{'、'.join(sorted(found[day]))}）"


def _demand_days(candidates: list[str], held: set[str]) -> dict[str, str]:
    """``{day: role}`` a latest-only metric needs among the days not known closed: the latest
    one, and the earlier value it is compared with (the newest earlier day held, else the
    day before)."""
    if not candidates:
        return {}
    latest, earlier = candidates[-1], candidates[:-1]
    days = {latest: "最新"}
    held_before = [d for d in earlier if d in held]
    compared = held_before[-1] if held_before else (earlier[-1] if earlier else None)
    if compared:
        days[compared] = "比较"
    return days


def _own_rule(
    run: Run,
    result: DailyResult,
    key: tuple[str, str],
    rule: Announced | None,
    calendar: Calendar | None,
    days: list[str],
    by_day: dict,
) -> tuple[Announced | None, dict[str, str] | None]:
    """The requirement a member is checked under when it is not "every open day": its
    announcements, or the days a latest-only metric needs. Records it for the report."""
    metric, member = key
    compatible = run.same_definition[metric]
    if rule is not None:
        notice_metric, notice_dims = rule.notice
        named = json.dumps(notice_dims, ensure_ascii=False, sort_keys=True)
        result.rules[key] = RuleNote(
            f"事件类（现行值）：冻结规则的 notices 指向 {notice_metric} {named}，"
            f"公告族 {rule.family}",
            _base_before(run, metric, member, compatible),
        )
        return rule, None
    if metric in LATEST_ONLY:
        # An uncovered day may be open: it stays a candidate (and is reported uncovered).
        candidates = [d for d in days if not calendar or calendar.classify(d) != "closed"]
        demand = _demand_days(candidates, {d for d, v in by_day.items() if v & compatible})
        roles = sorted(demand.items(), reverse=True)
        result.rules[key] = RuleNote(
            LATEST_ONLY[metric], "，".join(f"{role} {day}" for day, role in roles)
        )
        return None, demand
    return None, None


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
    announced = _announced_metrics(run)
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
        notice = announced.get(metric)
        announcements = _load_announced(run, metric, notice) if notice else None
        for member in sorted(members):
            name = holdings.exchange_of.get(member, "SHFE") if metric == WARRANTS else None
            name = name or MARKET.get(metric, "SSE")
            calendar = run.calendars.get(name)
            by_day = holdings.versions.get((metric, member), {})
            receipts: list[Receipt] | None = None
            rule, demand = _own_rule(
                run, result, (metric, member), announcements, calendar, days, by_day
            )
            for day in days:
                kind = calendar.classify(day) if calendar else "uncovered"
                if kind == "closed":
                    continue
                if kind == "uncovered":
                    result.cells.append(Cell(metric, member, day, UNCOVERED, f"{name} 日历"))
                    continue
                outside = demand is not None and day not in demand
                versions = by_day.get(day, set())
                if versions & compatible and outside:
                    result.cells.append(Cell(metric, member, day, OUT_OF_DEMAND, "已持有"))
                    continue
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
                found = None
                if rule is not None:
                    status, evidence, found = _classify_announced(run, rule, metric, member, day)
                else:
                    if receipts is None:
                        receipts = _member_receipts(run, metric, member, holdings)
                    status, evidence = _classify_missing(run, receipts, raw, metric, member, day)
                if versions:
                    listed = "、".join(sorted(versions))
                    evidence = f"仅有定义不同的目录版本 {listed} 的声明；{evidence}"
                if outside:
                    # Not due; what the gap would have been is kept apart as information.
                    result.outside[(metric, member, day)] = (status, evidence)
                    result.cells.append(Cell(metric, member, day, OUT_OF_DEMAND))
                    continue
                cell = Cell(metric, member, day, status, evidence)
                result.cells.append(cell)
                if found:
                    result.recoverable.append((cell, *found))
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
    purged: bool = False  # ``stored`` is the earliest receipt that stored it; no claim is left


@dataclass
class AbsentRow:
    """A period published in the window by the cutoff with no claim of it in the database."""

    metric: str
    period: str
    published: datetime
    status: str  # one of ABSENT
    evidence: str


@dataclass
class PurgedRow:
    """One member of a period published in the window that was stored and is now gone."""

    metric: str
    period: str
    member: str  # dimensions key, or UNKNOWN_MEMBER
    published: datetime
    evidence: str
    whole: bool  # no member of the period has a claim left


def _dimensions_key(dimensions) -> str:
    """A member as sorted-key JSON of its dimensions; ``{}`` for none."""
    if isinstance(dimensions, str):
        dimensions = json.loads(dimensions)
    return json.dumps(dimensions or {}, ensure_ascii=False, sort_keys=True)


def _plan_member(metric: str, member: str) -> str:
    """A final plan's ``METRIC:{dimensions}`` member as a dimensions key."""
    prefix = f"{metric}:"
    return _dimensions_key(member[len(prefix) :] if member.startswith(prefix) else member)


class StorageHistory:
    """What the run's frozen final plan and the stored receipts say about periods that have no
    claim left: the claims retention removes leave the plan and the receipts behind."""

    def __init__(self, run: Run) -> None:
        self._run = run
        self._demand: dict[str, dict[str, dict]] | None = None
        self._ingests: dict[str, list[tuple[str, str, str, str]]] = {}

    @property
    def demand(self) -> dict[str, dict[str, dict]]:
        """``{metric: {period: requirement}}`` of the final plan, frozen at the cutoff."""
        if self._demand is None:
            plan = self._run.gap_plan("final") or {}
            self._demand = defaultdict(dict)
            for requirement in plan.get("requirements") or []:
                if requirement.get("period"):
                    self._demand[requirement["metric_id"]][requirement["period"]] = requirement
        return self._demand

    def _receipts(self, metric: str) -> list[tuple[str, str, str, str]]:
        """``(acquisition, validated_at, normalized, runs)`` of receipts a run declared for the
        metric, validated and accepted for ingestion by the cutoff, oldest first."""
        if metric not in self._ingests:
            rows = self._run.db.execute(
                "SELECT a.acquisition_id, a.validated_at, a.normalized_hash,"
                " GROUP_CONCAT(DISTINCT f.run_id) FROM acquisition_request a"
                " JOIN full_run_acquisition f ON f.acquisition_id = a.acquisition_id"
                " WHERE f.metric_ids_json LIKE ? AND a.state = 'validated'"
                " AND a.ingest_result = 'accepted' AND a.normalized_hash IS NOT NULL"
                " AND a.validated_at <= ? GROUP BY a.acquisition_id"
                " ORDER BY a.validated_at, a.acquisition_id",
                (f'%"{metric}"%', self._run.cutoff),
            )
            self._ingests[metric] = rows.fetchall()
        return self._ingests[metric]

    def _stored_by(
        self, metric: str, frequency: str, period: str
    ) -> list[tuple[str, str, str, frozenset[str]]]:
        """``(acquisition, validated_at, runs, members)`` of those receipts whose accepted parse
        holds a value of the metric for the period, with the members it holds."""
        found = []
        for acquisition, validated, normalized, runs in self._receipts(metric):
            members = frozenset(
                _dimensions_key(s.get("dimensions"))
                for s in self._run.scalars(normalized) or []
                if isinstance(s, dict)
                and s.get("metric_id") == metric
                and s.get("period_kind") != "business_day"
                and isinstance(s.get("period_end"), str)
                and _period_label(frequency, s["period_end"]) == period
            )
            if members:
                found.append((acquisition, validated, runs, members))
        return found

    def _left(self, claim_ids: list[str]) -> int:
        """How many of the claims are still in ``source_claim``."""
        if not claim_ids:
            return 0
        marks = ",".join("?" * len(claim_ids))
        return self._run.db.execute(
            f"SELECT COUNT(*) FROM source_claim WHERE claim_id IN ({marks})", tuple(claim_ids)
        ).fetchone()[0]

    @staticmethod
    def _receipt_proof(receipts: list[tuple[str, str, str, frozenset[str]]], what: str) -> str:
        runs = {r for _, _, joined, _ in receipts for r in joined.split(",")}
        first, last = receipts[0], receipts[-1]
        return (
            f"截止前 {len(receipts)} 条回执（{len(runs)} 次运行）的已接受解析件含{what}，"
            f"最早 {first[0]}（{_fmt(parse_time(first[1]))}），最近 {last[0]}"
        )

    def purged(
        self, metric: str, frequency: str, period: str, held: set[str]
    ) -> list[tuple[str, str]]:
        """``(member, evidence)`` of the period's members stored once and held no longer.

        Stored by the plan (it names the member and some claim it selected for the period is
        gone) or by a receipt (an accepted parse holding the member for the period).
        """
        requirement = self.demand.get(metric, {}).get(period) or {}
        selected = requirement.get("selected_claim_ids") or []
        gone = len(selected) - self._left(selected)
        planned: set[str] = set()
        if gone:
            missing = {_plan_member(metric, m) for m in requirement.get("missing_members") or []}
            planned = {_plan_member(metric, m) for m in requirement.get("members") or []}
            planned -= missing
        receipts = self._stored_by(metric, frequency, period)
        found = []
        for member in sorted((planned | {m for *_, ms in receipts for m in ms}) - held):
            proof = []
            if member in planned:
                proof.append(
                    f"冻结计划该期列有该成员，选中的 {len(selected)} 条声明中 {gone} 条现已不在库"
                )
            mine = [r for r in receipts if member in r[3]]
            if mine:
                proof.append(self._receipt_proof(mine, "该成员该期"))
            found.append((member, "；".join(proof) + "；现存同定义声明已无该成员该期"))
        return found

    def classify(
        self, metric: str, frequency: str, period: str
    ) -> tuple[str, datetime | None, str]:
        """``(status, earliest stored time or None, evidence)`` of a period with no claim.

        Stored once, by the plan (claims it selected at the cutoff are gone) or by a receipt
        (an accepted parse holding the period): removed afterwards. Otherwise a plan that
        names the metric but not the period did not ask for it; anything else is not fetched.
        """
        wanted = self.demand.get(metric, {})
        requirement = wanted.get(period)
        selected = (requirement or {}).get("selected_claim_ids") or []
        receipts = self._stored_by(metric, frequency, period)
        proof = []
        if selected and not self._left(selected):
            proof.append(f"冻结计划选中该期 {len(selected)} 条声明，现已不在库")
        if receipts:
            proof.append(self._receipt_proof(receipts, "该期"))
        if proof:
            stored = parse_time(receipts[0][1]) if receipts else None
            return PURGED, stored, "；".join(proof) + "；现存声明已无该期"
        if wanted and requirement is None:
            return OUT_OF_DEMAND, None, f"冻结计划对该指标只要求 {_periods(sorted(wanted))}"
        if requirement is not None:
            return NOT_FETCHED, None, f"冻结计划要求该期（{requirement.get('status')}）"
        return NOT_FETCHED, None, "冻结计划没有该指标的需求行，无法判定需求"


def _periods(periods: list[str]) -> str:
    if len(periods) <= 6:
        return "、".join(periods)
    return f"{periods[0]}～{periods[-1]}（{len(periods)} 期）"


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


def low_frequency(
    run: Run,
) -> tuple[list[PeriodRow], list[DelayRow], list[AbsentRow], list[PurgedRow], list[str]]:
    cutoff = parse_time(run.cutoff)
    window_start = _beijing(run.window[0], "00:00:00")
    system_start = parse_time(run.system_start)
    history = StorageHistory(run)
    rows, delays, absent, events = [], [], [], []
    cleared: list[PurgedRow] = []
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
            first, purged = stored.get(period), False
            whole = first is None
            if whole:
                status, first, evidence = history.classify(metric, frequency, period)
                absent.append(AbsentRow(metric, period, when, status, evidence))
                purged = status == PURGED
            if not whole or purged:
                held = {_dimensions_key(d) for d in members.get(period, ())}
                gone_members = history.purged(metric, frequency, period, held)
                if purged and not gone_members:
                    gone_members = [(UNKNOWN_MEMBER, evidence)]
                cleared += [PurgedRow(metric, period, m, when, e, whole) for m, e in gone_members]
            if whole and (status == OUT_OF_DEMAND or (purged and first is None)):
                continue  # not due; or stored at an unknown time, so no delay to judge
            limit, note = _deadline(run, when)
            if limit is None:
                late = first is None or first > when
            elif first is None:
                late = cutoff > limit  # still inside the grace when the run froze
            else:
                late = first > limit
            if late:
                basis = ("官方日程" if period in official else "声明的公开可用时间") + note
                backfilled = when < system_start
                row = DelayRow(metric, period, when, first, limit, basis, backfilled, purged)
                delays.append(row)
    return rows, delays, absent, cleared, events


# --- report -------------------------------------------------------------------------------


def _counts(cells: list[Cell]) -> dict[str, int]:
    """Cells per class; cells not due under the metric's own requirement are left out."""
    counts = dict.fromkeys(CLASSES, 0)
    for cell in cells:
        if cell.status in counts:
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


def _stored(row: DelayRow) -> str:
    return f"{_fmt(row.stored)}（{PURGED}，见下表）" if row.purged else _fmt(row.stored)


def _overrun(row: DelayRow) -> str:
    if row.deadline is None:
        return "宽限无法判定（日历未覆盖）"
    if row.stored is None:
        return "到截止未入库，已超宽限"
    hours = (row.stored - row.deadline).total_seconds() / 3600
    return f"{hours / 24:.1f} 天" if hours >= 24 else f"{hours:.1f} 小时"


def _cleared_counts(cleared: list[PurgedRow]) -> str:
    periods = {(c.metric, c.period) for c in cleared}
    partial = {(c.metric, c.period) for c in cleared if not c.whole}
    return (
        f"{len(cleared)} 个成员、{len(periods)} 个指标期次"
        f"（其中 {len(partial)} 期仍有其他成员的声明）"
    )


def _conclusion(run: Run, result: DailyResult, periods, delays, absent, cleared) -> list[str]:
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
        gone = Counter(a.status for a in absent if keep(a.metric))
        out.append(
            f"- **{label}**：日频应有 {sum(counts.values())} 格，已持有 {counts[HELD]}，"
            f"未取到 {counts[NOT_FETCHED]}，上游未发布 {counts[NOT_PUBLISHED]}，"
            f"日历未覆盖 {counts[UNCOVERED]}（有缺格的指标 {missing} 项）；"
            f"低频 {len(lf)} 项中最新应有期缺 {sum(p.status == '缺' for p in lf)} 项、"
            f"无法判定 {sum(p.status == '无法判定' for p in lf)} 项；"
            f"超过宽限的期次 {len(late)} 个（其中发布早于系统启用 {run.system_start[:10]} 的"
            f" {sum(d.backfilled for d in late)} 个；到截止仍未入库"
            f" {sum(d.stored is None for d in late)} 个，{PURGED}"
            f" {sum(d.purged for d in late)} 个），宽限无法判定 {unknown} 个；"
            f"窗口内发布、现已无声明的期次 {sum(gone.values())} 个："
            + "，".join(f"{status} {gone[status]}" for status in ABSENT)
            + f"（{OUT_OF_DEMAND}的不算超过宽限）；按成员计{PURGED} "
            + _cleared_counts([c for c in cleared if keep(c.metric)])
            + "。"
        )
    if result.rules:
        parts = []
        for metric in dict.fromkeys(m for m, _ in result.rules):
            cells = [c for c in result.cells if c.metric == metric]
            skipped = Counter(c.status for c in cells if c.status in NOT_DUE)
            counted = "、".join(f"{status} {n} 格" for status, n in sorted(skipped.items()))
            again = sum(1 for c, *_ in result.recoverable if c.metric == metric)
            parts.append(
                f"{metric}（模型用到：{scope_label(run, metric)}）{counted or '无不计入的格'}"
                + (f"，{RECOVERABLE} {again} 格（计入未取到）" if again else "")
                + (f"，{NO_PATH[metric]}" if metric in NO_PATH else "")
            )
        out.append(
            "- **按事件与需求口径核对的指标**不按“每个交易日都应有观测”计应有格，"
            f"上面两种范围的日频计数已按各自口径计：{'；'.join(parts)}。"
            "见“日频：按事件与需求口径核对的指标”。"
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


def _new_rule(run: Run, day: str, public_at: datetime) -> str:
    """Whether the target day's summary reads a held cell under the documented 公开截止."""
    why = run.target_unread(day, public_at)
    return f"读不到（{why}）" if why else "读得到（公开不晚于运行冻结截止）"


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
        if cell.status != HELD and cell.status not in NOT_DUE:
            grouped[(cell.metric, cell.member, cell.status, cell.evidence)].append(cell.day)
    all_open = _all_open(run)
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
        f"已持有、但声明的公开时间晚于目标日 {run.target_date} 结束的格（“新口径下”一栏按"
        "体检文档“公开截止”注明目标日汇总能否读到；读不到的按时点规则不进模型；旧口径的运行"
        "中都不进模型；实际是否入选由第二层报告）：",
        "",
    ]
    late_public = [
        [
            cell.metric,
            _display(cell.member),
            cell.day,
            _fmt(parse_time(public_at)),
            _new_rule(run, cell.day, parse_time(public_at)),
        ]
        for cell, public_at in result.public_after_target
    ]
    headers = ["指标", "成员", "日期", "公开时间", "新口径下"]
    out.append(table(headers, late_public) if late_public else "无。")
    return [*out, ""]


def _all_open(run: Run) -> list[str]:
    """Consecutive means consecutive on the union of every calendar's open days."""
    return sorted(set().union(*(c.open_days for c in run.calendars.values())))


def _rule_tables(run: Run, result: DailyResult) -> list[str]:
    if not result.rules:
        return []
    out = [
        "### 日频：按事件与需求口径核对的指标",
        "",
        "以下指标不按“每个交易日都应有观测”核对。上表只计按各自口径应有的格；"
        "不计入的格及其日期列在这里。",
        "",
        "- 事件类（现行值）：冻结确认规则带 `notices` 的指标，只在公告给出新值的日子才有观测。"
        "没有声明的日子按当日公告判断：公告的已存解析件含该值，记未取到，"
        f"并注明“{RECOVERABLE}”；当日公告的每份解析件都不含该值、且 `notices` 指标的值都为 0"
        f"（当日无操作），记“{NO_NEW_VALUE}”，不计入应有格；`notices` 值非 0 或缺失、"
        "没有当日公告解析件的，都记未取到。",
        "- 只要最新值的指标（内置表 `LATEST_ONLY`）：只有最新开市日和与之比较的上一个值是应有格，"
        f"其余日子记“{OUT_OF_DEMAND}”，不计入应有格；日历未覆盖的日子仍记日历未覆盖。"
        "其中没有持有的日子仍照常分类，按类别计入“需求外缺格”一列，只作信息，不计入未取到。",
        "",
    ]
    rows = []
    for key, note in result.rules.items():
        metric, member = key
        cells = [c for c in result.cells if (c.metric, c.member) == key]
        counts = _counts(cells)
        skipped = Counter(c.status for c in cells if c.status in NOT_DUE)
        outside = Counter(
            status for (m, who, _), (status, _) in result.outside.items() if (m, who) == key
        )
        basis = note.basis + (f"；{NO_PATH[metric]}" if metric in NO_PATH else "")
        rows.append(
            [
                metric,
                scope_label(run, metric),
                _display(member),
                basis,
                len(cells),
                sum(counts.values()),
                counts[HELD],
                counts[NOT_FETCHED] + counts[NOT_PUBLISHED],
                "、".join(f"{s} {n}" for s, n in sorted(skipped.items())) or "0",
                sum(1 for c in cells if c.status == OUT_OF_DEMAND and c.evidence),
                "、".join(f"{s} {n}" for s, n in sorted(outside.items())) or "0",
                note.note,
            ]
        )
    headers = [
        "指标",
        "模型用到",
        "成员",
        "口径",
        "窗口开市日",
        "应有格",
        "已持有",
        "缺格",
        "不计入应有",
        "其中已持有",
        "需求外缺格",
        "说明",
    ]
    out += [table(headers, rows), "", "不计入应有的格：", ""]
    grouped: dict[tuple, list[str]] = defaultdict(list)
    for cell in result.cells:
        if cell.status in NOT_DUE:
            evidence = cell.evidence if cell.status == NO_NEW_VALUE else ""
            grouped[(cell.metric, cell.member, cell.status, evidence)].append(cell.day)
    all_open = _all_open(run)
    detail = [
        [metric, _display(member), status, compress_days(days, all_open), evidence or "—"]
        for (metric, member, status, evidence), days in sorted(grouped.items())
    ]
    out.append(table(["指标", "成员", "类别", "日期", "依据"], detail) if detail else "无。")
    out += ["", f"{RECOVERABLE}的格（逐日列出所依据的公告回执）：", ""]
    again = [
        [cell.metric, _display(cell.member), cell.day, acquisition, values]
        for cell, acquisition, values in sorted(
            result.recoverable, key=lambda r: (r[0].metric, r[0].day)
        )
    ]
    headers = ["指标", "成员", "日期", "公告回执", "解析件中的值"]
    out.append(table(headers, again) if again else "无。")
    return [*out, ""]


def _low_frequency_tables(
    run: Run,
    periods: list[PeriodRow],
    delays: list[DelayRow],
    absent: list[AbsentRow],
    cleared: list[PurgedRow],
) -> list[str]:
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
            _stored(d),
            _fmt(d.deadline) if d.deadline else "—",
            _overrun(d),
            "是" if d.backfilled else "否",
        ]
        for d in sorted(delays, key=lambda d: (d.backfilled, d.metric, d.period))
    ]
    out.append(table(headers, rows) if rows else "无。")
    out += [
        "",
        "窗口内发布、现已无声明的期次与已被清理的成员（按本运行的最终计划与截止前回执区分）。"
        f"{PURGED}逐成员列出，共 {_cleared_counts(cleared)}；另两类逐期列出：",
        "",
    ]
    headers = ["指标", "模型用到", "期次", "成员", "发布", "类别", "依据"]
    listed = [(a.metric, a.period, "整期", a.published, a.status, a.evidence) for a in absent]
    listed = [row for row in listed if row[4] != PURGED]
    listed += [
        (
            c.metric,
            c.period,
            c.member if c.member == UNKNOWN_MEMBER else _display(c.member),
            c.published,
            PURGED,
            c.evidence + ("；该期已无任何声明" if c.whole else "；该期仍有其他成员的声明"),
        )
        for c in cleared
    ]
    rows = [
        [metric, scope_label(run, metric), period, member, _fmt(published), status, evidence]
        for metric, period, member, published, status, evidence in sorted(
            listed, key=lambda r: r[:3]
        )
    ]
    out.append(table(headers, rows) if rows else "无。")
    return [*out, ""]


def section(run: Run) -> str:
    result = daily(run)
    periods, delays, absent, cleared, events = low_frequency(run)
    plan = _plan_window(run)
    judged = parse_time(run.cutoff).astimezone(BEIJING).date().isoformat()

    out = [
        "## 第一层：取数是否完整",
        "",
        *_conclusion(run, result, periods, delays, absent, cleared),
    ]
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
    out += _rule_tables(run, result)
    out += _low_frequency_tables(run, periods, delays, absent, cleared)
    out += [
        "### 不在本层核对范围",
        "",
        f"- 运维类：{'、'.join(sorted(OPERATIONAL & set(run.catalog)))}（日历本身见上表）。",
        f"- 仅有派生值（第一层第三条，票 02）：{'、'.join(sorted(run.derived_only))}。",
        f"- 事件型（无固定期次）：{'、'.join(events) or '无'}。",
        "",
    ]
    return "\n".join(out)
