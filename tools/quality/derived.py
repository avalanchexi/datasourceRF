"""Layer 1, part three: derived data. Is every derived value there, and does a second,
independent implementation of each frozen formula reproduce it from the raw claims?

Derived values live in three places, all checked:

- ``derived_observation`` rows the run stored for its target day (``batch_id`` = run id);
- the day projections of the window (one published projection per trading day; backfilled
  days carry their derived values only there), for the formulas stored as derived
  observations;
- derived series inside the run's own projection (``macro``): the rule-level formulas named in
  ``confirmation_rules`` (M1−M2, DR007 policy spread per block of sessions, …).

Each formula is re-implemented here from its written definition (GLOSSARY.md, ADRs, specs and
tickets, cited in ``docs/development/data-quality-audit.md``), never from production code. A
choice a definition leaves open is named in the report; what the definitions do not allow to
re-implement is listed as not independently checkable, with the reason.
"""

from __future__ import annotations

import bisect
import html
import itertools
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit

from common import Run, compress_days, iso_day, parse_time, table, unread_reason

# The formulas are exact arithmetic on decimal inputs: recomputing from the same inputs
# differs only by float noise (below 1e-13 relative). The tolerance leaves ample room for that
# noise; it does not promise to catch a tiny change in a large value.
TOLERANCE = 1e-6
BEIJING = timezone(timedelta(hours=8))

AGREE, DIFFER, NO_INPUT, UNCHECKABLE = "一致", "有差异", "原料不齐", "无法独立核对"
TICKET = "待开票"
# A stored value whose input claims retention has since deleted: nothing left to check against.
PRUNED = "原料已被留存删除，无法核对"
# ADR-0036 (reads across catalog versions that define a metric alike) took effect with commit
# 6fa8941 at this time. Before it, a run read only claims stored under its own catalog version.
# A day projection whose run was accepted earlier, and whose gap reading that way explains, is a
# fixed defect kept in history: published projections are not recomputed (ADR-0036, last
# point).
ADR_0036_IN_EFFECT = "2026-10-02T16:05:46+00:00"
# The new public cutoff (ADR-0041, 2026-10-13 addendum: a run's own target day reads what is
# public by the run's frozen cutoff, so next-morning data can enter it) first applied to
# run-25ac18e4…, accepted at this time (recurring-input-gaps residuals, ticket 10). A window
# day's projection published as its run's own target day by a run accepted at or after it is
# read as that run read it; any other window day by its own end.
NEW_CUTOFF_IN_EFFECT = "2026-10-14T03:40:33+00:00"
FIXED_HISTORY = "已修复、历史保留"
FIXED_HISTORY_WHY = (
    "生成该日投影的运行受理早于 ADR-0036 实施（6fa8941，2026-10-02 16:05Z），当时只读本目录版本下的"
    "声明；改按该日模型的目录版本严格读取，独立判断与投影相符。ADR-0036 已改为按相同定义"
    "跨版本读取，已发布历史不重算，不开票"
)

PMI, PMI_INVENTORY = "CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"
PMI_PRODUCTION = {"measure": "level", "series": "production"}
PMI_NEW_ORDERS = {"measure": "level", "series": "new_orders"}
PMI_FINISHED_GOODS = {"measure": "level", "series": "finished_goods"}
UST2, UST10 = "UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"
DR007, OMO_RATE, OMO_AMOUNT = "CN_DR007", "CN_OMO_7D_RATE", "CN_OMO_7D_AMOUNT"
INJECTION = {"measure": "injection"}
INVENTORY, NOMINAL_INVENTORY = "CN_FINISHED_GOODS_INVENTORY", {"measure": "nominal_end_level"}
PPI, PPI_YOY = "CN_PPI", {"category": "headline", "measure": "yoy"}
LOAN, SF, YTD = "CN_LOAN_STRUCTURE", "CN_SF_TOTAL", {"measure": "ytd_increment"}
GDP, GDP_YTD = "CN_GDP", {"aggregate": "total", "measure": "nominal_ytd_level"}
REPO_TENOR_DAYS = 7
# Several values of one observation (ADR-0033): within 0.5% of each other they are compatible,
# not a conflict.
COMPATIBLE = 0.005
COMPATIBLE_SPLIT, CONFLICT_SPLIT = "多源取值在相容范围内", "多源取值不一致"

# Market breadth (ADR-0030): computed by the system per stock from TuShare ``daily`` and
# ``stk_factor_pro`` and stored as source claims; re-implemented below from those raw answers.
BREADTH_DEFINITION = (
    "ADR-0030：普通 A 股（排除 B 股与 CDR），停牌或成交量为 0 不参与；涨跌按 close 对 pre_close；"
    "成交额占比用 daily.amount；N 日新高新低为 topdays／lowdays ≥ N；站上均线为前复权收盘价严格"
    "大于均线，分母为当天有交易且因子不为空的股票"
)
# The commodity basket's sleeve breadth, as written in the audit document (user interview
# 2026-10-11, Q7). The span's first session only anchors it; flat stands apart.
BASKET_DEFINITION = (
    "121 日跨度、首日作锚，累计其后 120 日；分项贡献直接相加；篮子按每日分项贡献合计复利；"
    "持平单列（分项容差 1e-12 个百分点，篮子水平容差 1e-9）"
)
BASKET_KNOWN = (
    "已知（篮子水平与分项贡献序列本身未从期货原件重建，以入库的分项贡献声明为原料，见文档）"
)
SLEEVE_TOLERANCE, BASKET_TOLERANCE = 1e-12, 1e-9
BREADTH = {
    "CN_EQ_ADV_DEC": "股市广度：上涨／下跌／平盘家数",
    "CN_EQ_AD_RATIO": "股市广度：涨跌比",
    "CN_EQ_ADV_AMOUNT_SHARE": "股市广度：上涨成交额占比",
    "CN_EQ_NEW_HIGH_LOW_90": "股市广度：90 日新高新低",
    "CN_EQ_NEW_HIGH_LOW_250": "股市广度：250 日新高新低",
    "CN_EQ_ABOVE_MA90": "股市广度：站上 90 日均线占比",
    "CN_EQ_ABOVE_MA250": "股市广度：站上 250 日均线占比",
}
# The members the definition asks for, per metric. (The system also stores a participant
# count; it is compared when present but not required.)
BREADTH_MEASURES = {
    ("CN_EQ_ADV_DEC", "advances"), ("CN_EQ_ADV_DEC", "declines"), ("CN_EQ_ADV_DEC", "flats"),
    ("CN_EQ_ADV_DEC", "net"), ("CN_EQ_AD_RATIO", "advance_decline_ratio"),
    ("CN_EQ_ADV_AMOUNT_SHARE", "advancing_amount_share"),
    ("CN_EQ_NEW_HIGH_LOW_90", "new_highs"), ("CN_EQ_NEW_HIGH_LOW_90", "new_lows"),
    ("CN_EQ_NEW_HIGH_LOW_250", "new_highs"), ("CN_EQ_NEW_HIGH_LOW_250", "new_lows"),
    ("CN_EQ_ABOVE_MA90", "above_ma_share"), ("CN_EQ_ABOVE_MA250", "above_ma_share"),
}  # fmt: skip
# Not A shares (this audit's reading of "排除 B 股与 CDR"; stock_basic carries no flag for it):
# Shenzhen B shares 200xxx, Shanghai B shares 900xxx, Shanghai CDRs 689xxx.
NOT_A_SHARE = (("SZ", "200"), ("SH", "900"), ("SH", "689"))
# Rule-level members read 3 periods (``.scratch/macro-semantics-20261006/issues/
# 04-monthly-official-key-indicators.md:35``), so M1−M2 covers the newest 3 months.
AUXILIARY_LOOKBACK = 3


def member_key(dims: dict) -> str:
    return json.dumps(dims, ensure_ascii=False, sort_keys=True)


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.10g}"


def _agrees(stored: float, recomputed: float) -> bool:
    return abs(stored - recomputed) <= TOLERANCE * max(1.0, abs(stored))


def day_end(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T23:59:59.999999").replace(tzinfo=BEIJING)


def _month_end(year: int, month: int) -> str:
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    following = date(year + month // 12, month % 12 + 1, 1)
    return (following - timedelta(days=1)).isoformat()


def shift_month(period: str, months: int) -> str:
    return _month_end(int(period[:4]), int(period[5:7]) + months)


def _shift_day(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


# --- the raw claims usable at a point in time -----------------------------------------------


@dataclass(frozen=True)
class Claim:
    claim_id: str
    value: float | None
    version: str
    public_at: datetime | None
    available_at: str
    supersedes: str | None


def _deviation(values: list[float]) -> float:
    """The largest relative deviation |a−b| / max(|a|, |b|) of any two values (ADR-0033);
    two zeros agree."""
    return max(
        (abs(a - b) / max(abs(a), abs(b)) for a, b in itertools.combinations(values, 2) if a or b),
        default=0.0,
    )


def split_note(values: list[float]) -> str:
    """The note on several distinct values of one observation: compatible when every two are
    within ADR-0033's 0.5%, a conflict otherwise; empty for one value or none."""
    if len(values) < 2:
        return ""
    shown, deviation = "／".join(_num(v) for v in values), _deviation(values)
    if deviation <= COMPATIBLE:
        within = f"相对偏差 {deviation * 100:.2g}%，ADR-0033 的 0.5% 以内"
        return f"{COMPATIBLE_SPLIT}（{shown}，{within}）"
    return f"{CONFLICT_SPLIT}（{shown}）"


@dataclass
class Observation:
    """The usable claims of one observation identity (metric, period, member), and of them
    the news claims the reading rules exclude (``excluded``: claim id to reason)."""

    claims: list[tuple[str, float | None]] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)

    def pick(self, lineage: frozenset[str]) -> tuple[float | None, str]:
        """The value to use and a note. Choosing between disagreeing sources is the selection
        rule's job, not checked here: the claim the system chose (in ``lineage``) is used even
        when its value is empty, and a disagreement is always reported.

        The value never depends on ``excluded`` (a frozen lineage is recomputed as it stands,
        and with no system choice every usable claim still counts); only the note leaves out
        the values of excluded news claims, which production reads as never stated."""
        values = sorted({v for _, v in self.claims if v is not None})
        listed = {v for cid, v in self.claims if v is not None and cid not in self.excluded}
        split = split_note(sorted(listed))
        chosen = next(((cid, v) for cid, v in self.claims if cid in lineage), None)
        if chosen is not None:
            reason = self.excluded.get(chosen[0])
            # A frozen choice of an excluded claim is named on its own, not as a source.
            why = f"该声明属按读取规则排除的资讯声明（{reason}）" if reason else ""
            if chosen[1] is None:
                return None, "；".join(x for x in ["系统所选声明的值为空", why] if x)
            if reason:
                own = f"按系统所选 {_num(chosen[1])}，{why}"
                return chosen[1], "；".join(x for x in [split, own] if x)
            return chosen[1], f"{split}，按系统所选 {_num(chosen[1])}" if split else ""
        if len(values) == 1:
            return values[0], ""
        if not values:
            return None, "值为空"
        if split:
            return None, f"{split}，无系统所选可依"
        # Only excluded news claims make the values differ: still no system choice to use,
        # but no sources in disagreement either.
        dropped = "／".join(_num(v) for v in sorted(set(values) - listed))
        shown = "／".join(_num(v) for v in values)
        return None, f"无系统所选可依：可用声明取值 {shown}，其中 {dropped} 属按读取规则排除的声明"


# --- news claims the reading rules exclude (audit ticket 17) --------------------------------
# Written from the rules in docs/development/data-quality-audit.md ("多源备注与资讯声明的读取
# 排除"): a news claim whose kept quote production no longer reads as stating its value is
# neither listed nor selected. Only the reasons decidable from the stored page title, address
# and subject clause are judged here; re-reading the quote itself is not.

WRONG_PERIOD, LOCAL_SUBJECT, SUSPECT = "错期", "地方主语", "缺主语嫌疑"
AI_WEBSEARCH_ROUTE = "ai_websearch"
_CN_NUMBER = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_NUMBER |= {"十": 10, "十一": 11, "十二": 12}
# A year with the period it names; the alternatives are tried in this order.
_DATED = re.compile(
    r"(?P<year>\d{4})年(?:"
    r"(?P<dm>\d{1,2})月(?P<dd>\d{1,2})日"
    r"|1[—–\-－~至](?P<ytd>\d{1,2})月份?"
    r"|前(?P<ytdn>\d{1,2}|十[一二]?|[一二三四五六七八九])个?月"
    r"|(?P<half>上半年)|(?P<q3>前三季度)|(?P<fy>全年)"
    r"|第?(?P<q>[一二三四])季度"
    r"|(?P<m>\d{1,2})月(?:份|末)?"
    r")"
)
# Dates in an address's path, tried in turn; the first that matches decides.
_PATH_DATES = (
    re.compile(r"/(20\d{2})-(\d{2})-(\d{2})/"),
    re.compile(r"/(20\d{2})(\d{2})(\d{2})/"),
    re.compile(r"/(20\d{2})(\d{2})/(\d{2})/"),
    re.compile(r"/(20\d{2})/(\d{2})/?(\d{2})/"),
    re.compile(r"/(20\d{2})(\d{2})/()"),
)
_COUNTRY = re.compile(r"全国|国家统计局|我国")
_LOCAL_WORD = re.compile(r"[全本我](?:市(?!场)|区(?![间域])|[省县州盟旗])")
_PROVINCE = (
    "北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|"
    "广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门"
)
_PLACE_NAME = re.compile(_PROVINCE + r"|[一-鿿](?:自治区|[省市州县])")
_NO_PLACE = re.compile(
    r"[上超股楼债车汇沪深牛熊两退开休收闭观后逆托稳油铜期]市|(?<![一-鿿])[城金]市"
    r"|市[场值价]|北京(?=时间|\d{1,2}月\d{1,2}日[电讯])"
)


def _claim_period(frequency: str | None, start: str, end: str) -> tuple[set[int], tuple]:
    """The months (year × 12 + month − 1) a claim's period covers, and the earliest a text of
    it is published: (month, day), day 0 when any day of that month will do."""
    year, month = int(end[:4]), int(end[5:7])
    if frequency == "quarterly":
        last = (month - 1) // 3 * 3 + 3
        months = {year * 12 + m - 1 for m in range(last - 2, last + 1)}
        earliest = (year * 12 + last - 1, 0)
    else:
        months = {year * 12 + month - 1}
        earliest = (year * 12 + month - 1, int(end[8:10]) if start == end else 0)
    if frequency == "event":
        months |= {m - 1 for m in months}
        earliest = (min(months), 0)
    return months, earliest


def _named_months(found: re.Match[str]) -> set[int]:
    year = int(found["year"]) * 12 - 1
    if found["ytd"] or found["m"]:
        return {year + int(found["ytd"] or found["m"])}
    if found["ytdn"]:
        count = found["ytdn"]
        return {year + (int(count) if count.isdigit() else _CN_NUMBER[count])}
    quarter = 2 if found["half"] else 3 if found["q3"] else 4 if found["fy"] else None
    quarter = quarter or _CN_NUMBER[found["q"]]
    return {year + m for m in range(quarter * 3 - 2, quarter * 3 + 1)}


def _compared_with(text: str, found: re.Match[str]) -> bool:
    """A period the text compares with ("较2025年8月", "2025年8月以来"), not its own."""
    before, after = text[max(0, found.start() - 4) : found.start()], text[found.end() :]
    return bool(re.search(r"[较比]\s*$", before) or re.match(r"\s*(?:以来|同期|相比)", after))


def _dated_otherwise(words: str, url: str | None, months: set[int], earliest: tuple) -> bool:
    """Rule 1: a title or subject clause names its own period and none of it is the claim's,
    or a full date in it or in the address is before the claim's period could be published."""

    def before(year: str, month: str, day: str) -> bool:
        published = int(year) * 12 + int(month) - 1
        return (published, int(day)) < earliest if day else published < earliest[0]

    stated = [f for f in _DATED.finditer(words) if not _compared_with(words, f)]
    periods = [f for f in stated if not f["dm"]]
    if periods and not any(_named_months(f) & months for f in periods):
        return True
    if any(before(f["year"], f["dm"], f["dd"]) for f in stated if f["dm"]):
        return True
    try:
        path = urlsplit(url).path if url else ""
    except ValueError:
        path = ""  # an address that does not parse dates nothing
    for pattern in _PATH_DATES:
        found = pattern.search(path)
        if found is not None and 1 <= int(found[2]) <= 12:
            return before(*found.groups())
    return False


def _names_place(words: str) -> bool:
    """Rule 2: a title or subject clause names a place and not the country."""
    if _COUNTRY.search(words):
        return False
    if _LOCAL_WORD.search(words):
        return True
    no_place = [w.span() for w in _NO_PLACE.finditer(words)]
    return any(
        not any(a < p.end() and p.start() < b for a, b in no_place)
        for p in _PLACE_NAME.finditer(words)
    )


def excluded_news_claims(run: Run) -> dict[str, str]:
    """The kept news claims (with a row in ``claim_matched_quote``) the reading rules exclude,
    to the first reason that applies: wrong period, local subject, suspect without subject."""
    kept = "SELECT 1 FROM sqlite_master WHERE name = 'claim_matched_quote'"
    if not run.db.execute(kept).fetchone():
        return {}
    rows = run.db.execute(
        "SELECT q.claim_id, q.title, q.url, q.subject, q.route,"
        " COALESCE(NULLIF(q.url, ''), q.body_hash), c.metric_id, c.period_start, c.period_end"
        " FROM claim_matched_quote q JOIN source_claim c ON c.claim_id = q.claim_id"
    ).fetchall()
    local_pages = {
        page for _, title, _, subject, _, page, *_ in rows
        if _names_place(title or "") or _names_place(subject or "")
    }  # fmt: skip
    found = {}
    for claim_id, title, url, subject, route, page, metric, start, end in rows:
        frequency = run.catalog.get(metric, {}).get("frequency")
        months, earliest = _claim_period(frequency, start, end)
        if _dated_otherwise(title or "", url, months, earliest) or _dated_otherwise(
            subject or "", None, months, earliest
        ):
            found[claim_id] = WRONG_PERIOD
        elif _names_place(title or "") or _names_place(subject or ""):
            found[claim_id] = LOCAL_SUBJECT
        elif subject is None and (route == AI_WEBSEARCH_ROUTE or page in local_pages):
            found[claim_id] = SUSPECT
    return found


class Claims:
    """Every stored claim of a metric, read once and shared by all point-in-time views."""

    def __init__(self, run: Run) -> None:
        self.run = run
        self._rows: dict[str, dict[str, dict[str, list[Claim]]]] = {}
        self._deliveries: dict[str, list[tuple]] = {}
        self._on_file: dict[str, list[tuple]] = {}
        # News claims the reading rules exclude, and of them those a recomputation read
        # among an observation's claims (for the report's list).
        self.excluded = excluded_news_claims(run)
        self.dropped: set[str] = set()

    def of(self, metric: str) -> dict[str, dict[str, list[Claim]]]:
        if metric not in self._rows:
            found: dict = defaultdict(lambda: defaultdict(list))
            rows = self.run.db.execute(
                "SELECT claim_id, period_end, dimensions_json, value, definition_version,"
                " COALESCE(public_available_at, inferred_public_at), available_at,"
                " supersedes_claim_id FROM source_claim WHERE metric_id = ?",
                (metric,),
            )
            for claim_id, period, dims, value, version, public, available, supersedes in rows:
                public_at = parse_time(public) if public else None
                claim = Claim(claim_id, value, version, public_at, available, supersedes)
                found[member_key(json.loads(dims))][period].append(claim)
            self._rows[metric] = found
        return self._rows[metric]

    def nbs_quarter(self, quarter: str, as_of: str) -> tuple[tuple[float, float] | None, str]:
        """The NBS announcement for ``quarter`` (a quarter end), newest answered by ``as_of``:
        its own quarter value and rounding step, and which receipt said so."""
        period = f"{quarter[:4]}-Q{int(quarter[5:7]) // 3}"
        rows = self.run.db.execute(
            "SELECT raw_hash, parameters_json FROM acquisition_request"
            " WHERE api_name = 'official_http_get' AND raw_hash IS NOT NULL"
            " AND received_at <= ? ORDER BY received_at DESC",
            (as_of,),
        )
        for raw_hash, parameters in rows:
            p = json.loads(parameters)
            if p.get("family") != "nbs_gdp" or p.get("period") != period:
                continue
            try:
                page = self.run.artifact(raw_hash).decode("utf-8", "replace")
            except OSError:
                continue
            return _nbs_quarter_value(page, quarter), f"统计局 {period} 公告"
        return None, f"截止前没有 {period} 的统计局公告原件"

    def deliveries(self, metric: str) -> list[tuple]:
        """(acquisition, period, member, value, catalog version, when both the claim and its
        acquisition's answer were in hand) of every claim of ``metric`` delivered by TuShare.
        Only a TuShare delivery makes a difference of two totals compatible as it stands; any
        other source still goes to the NBS check (user decision, run-findings-20260928/13)."""
        if metric not in self._deliveries:
            rows = self.run.db.execute(
                "SELECT x.acquisition_id, s.period_end, s.dimensions_json, s.value,"
                " s.definition_version, MAX(s.available_at, COALESCE(a.received_at, ''))"
                " FROM source_claim s JOIN source_claim_acquisition x USING (claim_id)"
                " JOIN acquisition_request a USING (acquisition_id)"
                " WHERE s.metric_id = ? AND a.provider = 'tushare'",
                (metric,),
            )
            self._deliveries[metric] = [
                (acquisition, period, member_key(json.loads(dims)), value, version, known)
                for acquisition, period, dims, value, version, known in rows
            ]
        return self._deliveries[metric]

    def delivered_on_file(self, metric: str) -> list[tuple]:
        """(acquisition, period, member, value, when validated) of every scalar of ``metric``
        in the normalized artifacts of validated TuShare receipts of the APIs that delivered
        its claims. Retention deletes claims no projection cites any more, and with them their
        links to receipts; the receipts and their artifacts stay, so what one delivery carried
        can still be read back. The artifacts carry no catalog version: a scalar counts when
        its unit is one the frozen definition allows."""
        if metric not in self._on_file:
            definition = self.run.catalog.get(metric, {})
            units = set(definition.get("allowed_units") or [definition.get("unit")])
            rows = self.run.db.execute(
                "SELECT acquisition_id, normalized_hash, validated_at FROM acquisition_request"
                " WHERE provider = 'tushare' AND state = 'validated'"
                " AND normalized_hash IS NOT NULL AND api_name IN"
                " (SELECT a.api_name FROM source_claim s"
                " JOIN source_claim_acquisition x USING (claim_id)"
                " JOIN acquisition_request a USING (acquisition_id)"
                " WHERE s.metric_id = ? AND a.provider = 'tushare')"
                " ORDER BY validated_at, acquisition_id",
                (metric,),
            )
            found = []
            for acquisition, normalized, validated in rows:
                try:
                    payload = json.loads(self.run.artifact(normalized))
                    if isinstance(payload, dict):
                        payload = payload.get("accepted_scalars") or payload.get("scalars") or []
                    carried = [
                        (s["period_end"], member_key(s["dimensions"]), s["value"])
                        for s in payload
                        if s.get("metric_id") == metric and s.get("unit") in units
                    ]
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    continue  # missing or another shape: nothing on file from this receipt
                found += [(acquisition, *scalar, validated) for scalar in carried]
            self._on_file[metric] = found
        return self._on_file[metric]


QUARTER_LABEL = {"03": "一季度", "06": "二季度", "09": "三季度", "12": "四季度"}


def _nbs_quarter_value(page: str, quarter: str) -> tuple[float, float] | None:
    """The quarter's nominal GDP (亿元) and its rounding step, from the first table of an NBS
    GDP announcement: the header names the quarter, the GDP row gives its absolute value."""
    table_html = re.search(r"<table.*?</table>", page, re.S)
    if table_html is None:
        return None
    rows = [
        [re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", cell)))
         for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html.group(0), re.S)
    ]  # fmt: skip
    labels = next((r for r in rows if QUARTER_LABEL[quarter[5:7]] in r), None)
    gdp = next((r for r in rows if r and r[0] in ("GDP", "国内生产总值")), None)
    if labels is None or gdp is None or len(gdp) < 2:
        return None
    text = gdp[1]
    try:
        value = float(text)
    except ValueError:
        return None
    step = 10.0 ** -len(text.split(".")[1]) if "." in text else 1.0
    return value, step


class Held:
    """Claims usable at one point in time: stored by ``as_of``, readable by the summary of
    ``day`` at the public cutoff ``until`` (the documented 公开截止: a window day reads what
    was public by its own end, the target day what was public by the run's cutoff, past its
    end only of periods ending by the day; a window day published as the target day of a run
    under the new public cutoff, by that run's cutoff), under a catalog version with the frozen
    definition, not superseded by another such claim. ``day`` defaults to the Beijing date of
    ``until``. ``exact_version`` narrows the catalog versions to that one alone: how reads
    worked before ADR-0036."""

    def __init__(
        self,
        claims: Claims,
        as_of: str,
        until: datetime,
        exact_version: str | None = None,
        day: str | None = None,
    ) -> None:
        self.claims, self.run, self.as_of, self.until = claims, claims.run, as_of, until
        self.day = day or until.astimezone(BEIJING).date().isoformat()
        self.exact_version = exact_version
        self._views: dict[str, dict[str, dict[str, Observation]]] = {}

    def _versions(self, metric: str) -> frozenset[str] | None:
        if self.exact_version:
            return frozenset({self.exact_version})
        return self.run.same_definition.get(metric)

    def _unread(self, period: str, claim: Claim) -> str:
        if claim.public_at is None:
            return ""
        return unread_reason(self.day, self.until, period, claim.public_at)

    def _usable(self, metric: str, claim: Claim, period: str) -> bool:
        versions = self._versions(metric)
        return (
            claim.available_at <= self.as_of
            and (not versions or claim.version in versions)
            and not self._unread(period, claim)
        )

    def _view(self, metric: str) -> dict[str, dict[str, Observation]]:
        if metric not in self._views:
            kept = [
                (member, period, c)
                for member, periods in self.claims.of(metric).items()
                for period, claims in periods.items()
                for c in claims
                if self._usable(metric, c, period)
            ]
            superseded = {c.supersedes for _, _, c in kept if c.supersedes}
            view: dict = defaultdict(lambda: defaultdict(Observation))
            excluded = self.claims.excluded
            for member, period, c in kept:
                if c.claim_id not in superseded:
                    view[member][period].claims.append((c.claim_id, c.value))
                    if c.claim_id in excluded:
                        view[member][period].excluded[c.claim_id] = excluded[c.claim_id]
            self._views[metric] = view
        return self._views[metric]

    def series(self, metric: str, member: dict) -> dict[str, Observation]:
        return self._view(metric).get(member_key(member), {})

    def members(self, metric: str) -> list[dict]:
        return [json.loads(key) for key in sorted(self._view(metric))]

    def obs(self, metric: str, period: str, member: dict) -> Observation | None:
        return self.series(metric, member).get(period)

    def why_unusable(self, claim_id: str) -> str | None:
        row = self.run.db.execute(
            "SELECT metric_id, period_end, dimensions_json FROM source_claim WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            return "库中已无此声明"
        metric, period, dims = row
        stored = self.claims.of(metric)[member_key(json.loads(dims))][period]
        claim = next(c for c in stored if c.claim_id == claim_id)
        versions = self._versions(metric)
        if claim.available_at > self.as_of:
            return "截止后入库"
        if versions and claim.version not in versions:
            return "目录定义不同"
        if self._unread(period, claim):
            return "公开晚于公开截止"
        obs = self.obs(metric, period, json.loads(dims))
        if obs is None or all(cid != claim_id for cid, _ in obs.claims):
            return "已被更新的声明取代"
        return None

    def same_delivery(
        self, metric: str, member: dict, ends: list[tuple[str, float]]
    ) -> tuple[bool, str]:
        """Did one acquisition, in hand here, deliver every (period, value) of ``ends``? First
        by the stored claims' links to their receipts; failing that, by the normalized
        artifacts on file (retention prunes claims and their links, not receipts). The note
        names the earliest receipt when only its artifact shows the delivery."""
        key, versions = member_key(member), self._versions(metric)

        def together(rows) -> str | None:
            delivered: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
            for acquisition, period, member_, value, known in rows:
                if member_ == key and known and known <= self.as_of:
                    delivered[acquisition][period].add(value)
            return next(
                (a for a, got in delivered.items() if all(v in got.get(p, ()) for p, v in ends)),
                None,
            )

        linked = [
            (*delivery, known)
            for *delivery, version, known in self.claims.deliveries(metric)
            if not versions or version in versions
        ]
        if together(linked):
            return True, ""
        on_file = together(self.claims.delivered_on_file(metric))
        if on_file:
            return True, f"声明关联未见共同交付，回执 {on_file} 的规范化制品同时载有两端累计值"
        return False, ""


class Sessions:
    """SSE open days, for daily formulas that count sessions or roll to the next session."""

    def __init__(self, run: Run) -> None:
        calendar = run.calendars["SSE"]
        self.covered = calendar.covered
        self.open = sorted(calendar.open_days)
        self.is_open = calendar.open_days.__contains__

    def ending(self, day: str, count: int) -> list[str] | None:
        """The ``count`` open days ending on ``day`` (an open day), or None if uncovered."""
        if not self.is_open(day):
            return None
        at = bisect.bisect_right(self.open, day)
        return self.open[at - count : at] if at >= count else None

    def previous(self, day: str) -> str | None:
        at = bisect.bisect_left(self.open, day)
        return self.open[at - 1] if at else None

    def up_to(self, day: str) -> list[str]:
        return self.open[: bisect.bisect_right(self.open, day)]


class Missing(Exception):
    """An input the formula needs is not usable at the point in time."""


# A formula that cannot be evaluated: an input is missing, or a divisor is zero.
UNAVAILABLE = (Missing, ZeroDivisionError)


class Calc:
    """One evaluation: reads inputs, remembers which it used, what it noted, and where a
    condition of the definition was not met (``flags``).

    ``presence_only`` asks only whether the inputs exist: where sources disagree and no
    system choice is at hand, any of their values will do."""

    def __init__(self, held: Held, sessions: Sessions, lineage=frozenset(), presence_only=False):
        self.held, self.sessions, self.lineage = held, sessions, lineage
        self.presence_only = presence_only
        self.used: set[tuple[str, str, str]] = set()
        self.notes: list[str] = []
        self.flags: list[str] = []

    def has(self, metric: str, period: str, member: dict) -> bool:
        obs = self.held.obs(metric, period, member)
        return obs is not None and any(v is not None for _, v in obs.claims)

    def get(self, metric: str, period: str, member: dict) -> float:
        obs = self.held.obs(metric, period, member)
        if obs is None:
            shown = f" {member_key(member)}" if member else ""
            raise Missing(f"缺 {metric} {period}{shown}")
        value, note = obs.pick(self.lineage)
        self.held.claims.dropped |= obs.excluded.keys()
        if value is None and self.presence_only:
            value = next((v for _, v in obs.claims if v is not None), None)
        self.used.add((metric, period, member_key(member)))
        if note:
            self.notes.append(f"{metric} {period}：{note}")
        if value is None:
            raise Missing(f"{metric} {period}：{note}")
        return value


# --- formulas, re-implemented from their definitions ----------------------------------------


def monthly_increment(c: Calc, metric: str, member: dict, period: str) -> float:
    """A month's flow from year-to-date totals: January is its own total, any other month is
    this total minus the previous month's in the same year (no differencing across years)."""
    total = c.get(metric, period, member)
    return total if period[5:7] == "01" else total - c.get(metric, shift_month(period, -1), member)


def quarterly_flow(c: Calc, metric: str, member: dict, period: str) -> float:
    """A quarter's flow from year-to-date totals; the first quarter is its own total. The two
    totals of a difference must come from one delivery (GLOSSARY.md, credit impulse)."""
    total = c.get(metric, period, member)
    if period[5:7] == "03":
        return total
    previous = shift_month(period, -3)
    before = c.get(metric, previous, member)
    flow = total - before
    if c.presence_only:
        return flow
    together, note = c.held.same_delivery(metric, member, [(period, total), (previous, before)])
    if together:
        if note:
            c.notes.append(f"GDP {period} 当季差分：{note}")
        return flow
    official, source = c.held.claims.nbs_quarter(period, c.held.as_of)
    if official is None:
        c.flags.append(
            f"GDP {period} 当季值（{previous}→{period} 累计差分）既不出自同一次交付，"
            f"也无法与统计局公布的当季值核对（{source}）"
        )
    elif abs(flow - official[0]) > official[1] / 2 + TOLERANCE:
        c.flags.append(
            f"GDP {period} 当季值：累计差分 {_num(flow)} 不出自同一次交付，"
            f"且与统计局公布的 {_num(official[0])} 不一致（{source}）"
        )
    else:
        c.notes.append(f"GDP {period} 当季差分与统计局公布值 {_num(official[0])} 一致")
    return flow


def policy_rate(c: Calc, day: str) -> float:
    """The 7-day reverse repo rate in force on ``day``: the latest announced on or before it.
    (The definitions say "the rate in force"; taking the latest announcement is this audit's
    reading of that.)"""
    days = sorted(p for p in c.held.series(OMO_RATE, {}) if p <= day)
    if not days:
        raise Missing(f"{day} 之前没有可用的 {OMO_RATE}")
    return c.get(OMO_RATE, days[-1], {})


def net_injection(c: Calc, day: str) -> float:
    """7-day reverse repo net injection on an open day: what was injected since the previous
    open day, minus what matures today. A repo matures 7 calendar days after injection,
    rolled to the first open day on or after that, so today's maturities are the injections
    whose due date falls after the previous open day and no later than today. On an open
    day an announcement is required (an explicit zero counts as zero); on a closed day one
    is used if held."""
    previous = c.sessions.previous(day)
    if previous is None or not c.sessions.is_open(day):
        raise Missing(f"上交所日历不覆盖 {day} 前后")

    def flow(on: str) -> float:
        if c.has(OMO_AMOUNT, on, INJECTION) or c.sessions.is_open(on):
            return c.get(OMO_AMOUNT, on, INJECTION)
        if on not in c.sessions.covered:
            raise Missing(f"上交所日历不覆盖 {on}，无法判断当天是否应有投放")
        return 0.0

    span = (date.fromisoformat(day) - date.fromisoformat(previous)).days
    days = [_shift_day(previous, k) for k in range(1, span + 1)]
    return sum(flow(d) for d in days) - sum(flow(_shift_day(d, -REPO_TENOR_DAYS)) for d in days)


def credit_impulse(c: Calc, period: str, _member: dict) -> float:
    """100 × (social financing flow of the last 12 months) ÷ (nominal GDP of the last 4
    quarters). Flows come from year-to-date totals. GDP: "the last 4 quarters available this
    month", read as the newest quarter usable at the point in time whose four quarters are
    all held."""
    flow = sum(monthly_increment(c, SF, YTD, shift_month(period, -k)) for k in range(12))
    quarters = sorted(p for p in c.held.series(GDP, GDP_YTD) if p[5:7] in ("03", "06", "09", "12"))
    for quarter in reversed(quarters):
        ends = [shift_month(quarter, -3 * k) for k in range(4)]
        needed = ends + [shift_month(q, -3) for q in ends if q[5:7] != "03"]
        if all(c.has(GDP, q, GDP_YTD) for q in needed):
            gdp = sum(quarterly_flow(c, GDP, GDP_YTD, q) for q in ends)
            c.notes.append(f"GDP 近 4 季取至 {quarter}")
            return 100 * flow / gdp
    raise Missing("没有齐全的近 4 季名义 GDP")


def block_mean(c: Calc, metric: str, member: dict, end: str, sessions: int) -> float:
    days = c.sessions.ending(end, sessions)
    if days is None:
        raise Missing(f"上交所日历不足以划出截至 {end} 的 {sessions} 个交易日")
    return sum(c.get(metric, d, member) for d in days) / sessions


def block_net_injection(c: Calc, end: str, sessions: int) -> float:
    days = c.sessions.ending(end, sessions)
    if days is None:
        raise Missing(f"上交所日历不足以划出截至 {end} 的 {sessions} 个交易日")
    return sum(net_injection(c, d) for d in days)


def increment_vs_year_ago(c: Calc, metric: str, member: dict, period: str) -> float:
    """This month's flow minus the same month's flow a year earlier."""
    now = monthly_increment(c, metric, member, period)
    return now - monthly_increment(c, metric, member, shift_month(period, -12))


@dataclass(frozen=True)
class Stored:
    """A formula whose result is stored as a derived observation."""

    metric: str
    anchor: tuple[str, dict | None]  # metric and member whose periods are candidates
    compute: Callable[[Calc, str, dict], float]
    definition: str
    newest_anchor_only: bool = False  # the formula anchors on the anchor's newest period


STORED: dict[str, Stored] = {
    "pmi-production-order-spread-v0001": Stored(
        "CN_PRODUCTION_ORDER_SPREAD",
        (PMI, PMI_PRODUCTION),
        lambda c, p, m: c.get(PMI, p, PMI_PRODUCTION) - c.get(PMI, p, PMI_NEW_ORDERS),
        "同月制造业 PMI 生产指数 − 新订单指数",
    ),
    "pmi-order-inventory-spread-v0001": Stored(
        "CN_ORDER_INVENTORY_SPREAD",
        (PMI, PMI_NEW_ORDERS),
        lambda c, p, m: c.get(PMI, p, PMI_NEW_ORDERS) - c.get(PMI_INVENTORY, p, PMI_FINISHED_GOODS),
        "同月新订单指数 − 产成品库存指数",
    ),
    "ust-2s10s-spread-v0001": Stored(
        "UST_2S10S_SPREAD",
        (UST10, {}),
        lambda c, p, m: 100 * (c.get(UST10, p, {}) - c.get(UST2, p, {})),
        "100 ×（同日 10 年期 − 2 年期美债收益率），基点",
    ),
    "dr007-policy-spread-v0001": Stored(
        "CN_DR007_POLICY_SPREAD",
        (DR007, {}),
        lambda c, p, m: 100 * (c.get(DR007, p, {}) - policy_rate(c, p)),
        "100 ×（当日 DR007 − 当日现行七天逆回购利率），基点；现行利率取当日或之前最近一次公告",
    ),
    "inventory-ppi-common-month-v0002": Stored(
        "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
        (INVENTORY, NOMINAL_INVENTORY),
        lambda c, p, m: c.get(INVENTORY, p, NOMINAL_INVENTORY) / (1 + c.get(PPI, p, PPI_YOY) / 100),
        "最新月名义产成品存货 ÷（1 + 同月 PPI 同比 / 100）；PPI 取总指数同比（定义未写明成员）",
        newest_anchor_only=True,
    ),
    "loan-ytd-monthly-change-v0002": Stored(
        LOAN,
        (LOAN, None),
        lambda c, p, m: monthly_increment(c, LOAN, m, p),
        "同成员年内累计增量差分；1 月取当月累计",
        newest_anchor_only=True,
    ),
    "credit-impulse-12m-flow-share-v0003": Stored(
        "CN_CREDIT_IMPULSE",
        (SF, YTD),
        credit_impulse,
        "100 × 近 12 个月社融增量 ÷ 近 4 季名义 GDP；GDP 取当时可得、四季齐全的最新一季；"
        "GDP 差分须出自同一次交付",
    ),
    "repo-net-injection-trading-calendar-v0002": Stored(
        OMO_AMOUNT,
        (OMO_AMOUNT, INJECTION),
        lambda c, p, m: net_injection(c, p),
        "当日七天逆回购投放 − 当日到期；到期 = 投放日 + 7 自然日顺延至上交所开市日",
    ),
}

# Rule-level formulas: computed inside the projection, not stored as derived observations.
RULE_FORMULAS = {
    "sf-monthly-increment-yoy-change-v0001": "社融当月增量 − 去年同月增量（1 月增量取累计）",
    "loan-monthly-increment-yoy-change-v0001": "贷款成员当月增量 − 去年同月增量",
    "m1-m2-yoy-spread-v0001": "同月 M1 同比 − M2 同比，百分点",
    "omo-7d-net-injection-v0001": "每期（N 个交易日）逐日净投放之和",
    "dr007-policy-spread-sessions-v0001": "100 ×（每期 DR007 均值 − 期末现行政策利率），基点",
    "return-difference-v0001": "100 ×（甲核心 120 日收益 − 乙核心 120 日收益），百分点",
    "ex-hog-calendar-settlement-v0003": "商品篮子（剔除生猪、按日历换月）及分项贡献广度",
}


# --- results ------------------------------------------------------------------------------


@dataclass
class Compared:
    """One stored derived value set against the recomputation."""

    formula: str
    reading: str
    period: str
    stored: float | None
    recomputed: float | None
    verdict: str
    note: str = ""
    flags: list[str] = field(default_factory=list)


@dataclass
class Item:
    """One derived indicator's conclusion. ``problems`` are findings that need a ticket;
    ``known`` explains a limitation that is already known."""

    formula: str
    label: str
    where: str
    used: bool
    presence: str = ""
    verdict: str = ""
    note: str = ""
    rows: list[Compared] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    known: str = ""
    # A subsection of its own (title, then Markdown lines), shown after the series tables.
    detail: list[str] = field(default_factory=list)


def _compare(formula, reading, period, stored, run_calc) -> Compared:
    """Recompute one value with ``run_calc`` and judge it against ``stored``."""
    try:
        value, notes, flags = run_calc()
    except UNAVAILABLE as reason:
        why = "除数为零" if isinstance(reason, ZeroDivisionError) else str(reason)
        return Compared(formula, reading, period, stored, None, NO_INPUT, why)
    note = "；".join(dict.fromkeys(notes))
    if stored is None:
        return Compared(formula, reading, period, None, value, DIFFER, "库中值为空；" + note)
    verdict = AGREE if _agrees(stored, value) else DIFFER
    return Compared(formula, reading, period, stored, value, verdict, note, list(flags))


def _verdict(item: Item) -> None:
    """Sum an item's compared values up into its verdict and problems."""
    for row in item.rows:
        if row.verdict == DIFFER:
            item.problems.append(
                f"{row.reading} {row.period} 库中 {_num(row.stored)}、重算 {_num(row.recomputed)}"
            )
        item.problems += [f for f in dict.fromkeys(row.flags) if f not in item.problems]
    if item.verdict:
        return
    counts = Counter(row.verdict for row in item.rows)
    total = len(item.rows)
    if counts[DIFFER]:
        item.verdict = f"{DIFFER}（{counts[DIFFER]}/{total}）"
    elif counts[AGREE]:
        item.verdict = f"重算一致（{counts[AGREE]}/{total}）"
    else:
        item.verdict = "无可比值" if not total else f"{NO_INPUT}（{total}）"
    if counts[NO_INPUT] and counts[AGREE] + counts[DIFFER]:
        item.verdict += f"；{counts[NO_INPUT]} 个原料不齐"
    if any(row.flags for row in item.rows):
        item.verdict += "；定义条件未满足"


# --- derived observations: the run's own rows and every day projection -----------------------


def _lineage(run: Run, ids: list[str]) -> dict[str, tuple[str, str, str]]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = run.db.execute(
        "SELECT claim_id, metric_id, period_end, dimensions_json FROM source_claim"
        f" WHERE claim_id IN ({marks})",
        ids,
    )
    return {r[0]: (r[1], r[2], member_key(json.loads(r[3]))) for r in rows}


@dataclass
class Record:
    """One stored derived value: from ``derived_observation`` or a day projection."""

    member: dict
    period: str | None
    value: float | None
    ids: list[str]
    lineage: dict


def _record(run: Run, spec: Stored, value, ids, dims=None, period=None) -> Record:
    """Member and period come from the lineage (the anchor metric's claims); a projection
    record's own dimensions and period are the fallback when the lineage is gone."""
    lineage = _lineage(run, ids)
    anchors = [v for v in lineage.values() if v[0] == spec.anchor[0]]
    if spec.anchor[1] is not None:
        member = {}
    elif anchors:
        member = json.loads(anchors[0][2])
    else:
        member = {**(dims or {}), "measure": "ytd_increment"}
    return Record(member, max((v[1] for v in anchors), default=period), value, ids, lineage)


def _members(held: Held, spec: Stored) -> list[dict]:
    if spec.anchor[1] is not None:
        return [{}]
    return [m for m in held.members(LOAN) if m.get("measure") == "ytd_increment"]


def _newest_complete(held, sessions, spec: Stored, member: dict, day: str):
    """The newest period, up to ``day``, whose inputs are all usable; else the reason."""
    metric, anchor = spec.anchor
    if metric == OMO_AMOUNT:
        candidates = list(reversed(sessions.up_to(day)))
    else:
        series = held.series(metric, anchor if anchor is not None else member)
        candidates = sorted((p for p in series if p <= day), reverse=True)
    if spec.newest_anchor_only:
        candidates = candidates[:1]
    first = None
    for period in candidates:
        try:
            spec.compute(Calc(held, sessions, presence_only=True), period, member)
            return period, ""
        except UNAVAILABLE as reason:
            first = first or f"{period}：{reason}"
    return None, first or "没有可用的锚定期"


def _lineage_notes(held: Held, c: Calc, record: Record) -> list[str]:
    reasons = Counter(r for r in map(held.why_unusable, record.ids) if r)
    notes = []
    if reasons:
        notes.append("血缘含不可用声明：" + "、".join(f"{k} {v}" for k, v in reasons.items()))
    lacking = c.used - set(record.lineage.values())
    if lacking:
        shown = "、".join(sorted(f"{m} {p}" for m, p, _ in lacking)[:4])
        notes.append(f"血缘未引用重算所需的 {len(lacking)} 项输入（{shown}）")
    return notes


def _judge(formula, spec, held, sessions, day, member, record: Record | None):
    """Presence status and the recomputation of one formula/member at one point in time."""
    reading = "—" if not member else "／".join(str(v) for v in member.values())
    newest, why = _newest_complete(held, sessions, spec, member, day)
    period = record.period if record else None
    pruned = record is not None and len(record.lineage) < len(set(record.ids))
    if record is None:
        status = "缺失" if newest else "原料不齐，无派生值"
    elif pruned and (period is None or newest is None):
        status = PRUNED
    elif period is None:
        status = "库中有值，血缘与期次无法解析"
    elif newest is None:
        status = "库中有值，独立判断原料不齐"
    elif period == newest:
        status = "存在"
    elif period < newest:
        status = f"期次落后（原料已齐至 {newest}）"
    else:
        status = f"库中期次晚于独立判断（{newest}）"
    if record is None or period is None:
        row = Compared(formula, reading, period or "—", record and record.value, None, "—")
    else:

        def run_calc():
            c = Calc(held, sessions, frozenset(record.ids))
            value = spec.compute(c, period, member)
            return value, c.notes + _lineage_notes(held, c, record), c.flags

        row = _compare(formula, reading, period, record.value, run_calc)
    if why and newest is None:
        row.note = "；".join(x for x in [row.note, why] if x)
    return status, newest, row


NOT_RECOMPUTED = "未重算（按设计）"
PRESENT_OR_NOT_DUE = ("存在", "原料不齐，无派生值", PRUNED, NOT_RECOMPUTED)
EXPLAINED = ("存在", "原料不齐，无派生值")


def stored_items(run: Run, claims: Claims, sessions: Sessions) -> tuple[list[Item], list[list]]:
    """The run's own ``derived_observation`` rows against the target day."""
    held = Held(claims, run.cutoff, run.cutoff_moment, day=run.target_date)
    rows = run.db.execute(
        "SELECT metric_id, formula_version, input_observation_version_ids_json, value"
        " FROM derived_observation WHERE batch_id = ? ORDER BY metric_id",
        (run.run_id,),
    ).fetchall()
    by_formula: dict[str, list] = defaultdict(list)
    for metric, formula, inputs, value in rows:
        by_formula[formula].append((metric, json.loads(inputs), value))

    items, detail = [], []
    for name, formula in run.manifest.get("derived_formula_versions", {}).items():
        spec = STORED.get(formula)
        if spec is None:
            why = "本脚本没有该公式的实现"
            items.append(Item(formula, name, "派生观测", False, "—", UNCHECKABLE, why))
            continue
        item = Item(formula, spec.metric, "派生观测", spec.metric in run.model_used)
        records = {}
        for _, ids, value in by_formula.pop(formula, []):
            record = _record(run, spec, value, ids)
            records[member_key(record.member)] = record
        statuses = Counter()
        keys = {member_key(m) for m in _members(held, spec)} | set(records)
        for key in sorted(keys):
            member = json.loads(key)
            status, newest, row = _judge(
                formula, spec, held, sessions, run.target_date, member, records.get(key)
            )
            statuses[status.split("（")[0]] += 1
            if not status.startswith(PRESENT_OR_NOT_DUE):
                item.problems.append(f"{row.reading}：{status}")
            if key in records:
                item.rows.append(row)
            cells = [row.period, newest or "—", status, _num(row.stored), _num(row.recomputed)]
            detail.append([formula, row.reading, *cells, row.verdict, row.note])
        item.presence = "、".join(f"{k} {v}" for k, v in statuses.items())
        item.note = spec.definition
        items.append(item)
    for formula, extra in by_formula.items():
        why = "公式版本不在冻结清单的 derived_formula_versions 中"
        found = f"存在 {len(extra)}"
        items.append(Item(formula, extra[0][0], "派生观测", False, found, UNCHECKABLE, why))
    return items, detail


def _derived_records(node, found: dict[str, dict]) -> None:
    """Every derived value inside a projection document, keyed by derived observation id."""
    if isinstance(node, dict):
        ref = str(node.get("source_reference") or "")
        formula = node.get("formula_version") or (ref[8:] if ref.startswith("formula:") else None)
        if node.get("derived_observation_id") and formula and "value" in node:
            key = node["derived_observation_id"]
            if key not in found or (node.get("period") and not found[key].get("period")):
                found[key] = {**node, "formula_version": formula}
        for value in node.values():
            _derived_records(value, found)
    elif isinstance(node, list):
        for value in node:
            _derived_records(value, found)


def _day_projections(run: Run) -> dict[str, tuple[str, dict]]:
    """Per window day, the projection to check: for the target day the run's own; for any
    other day the newest one whose data cutoff (``system_as_of``) is not after the run's."""
    cutoff, window = parse_time(run.cutoff), set(run.window)
    best: dict[str, tuple[str, dict]] = {}
    rows = run.db.execute("SELECT projection_set_id, envelope_json FROM projection_set")
    for projection, envelope in rows:
        e = json.loads(envelope)
        day, as_of = e.get("target_business_date"), e.get("system_as_of")
        if day not in window or not as_of or parse_time(as_of) > cutoff:
            continue
        if day not in best or parse_time(as_of) > parse_time(best[day][1]["system_as_of"]):
            best[day] = (projection, e)
    if run.projection_set_id and run.envelope:
        best[run.target_date] = (run.projection_set_id, run.envelope)
    return best


CONTEXTS = ("macro", "inventory")


def _core_only(run: Run, projection: str, contexts: dict, found: dict) -> tuple[bool, str]:
    """Is a day projection a core-only correction (``GLOSSARY.md``, day summary)? Only when
    its assessment ``corrects`` with scope ``core_only``, both contexts are
    ``not_recomputed`` and they hold no derived value. Returns that and the marks seen: for
    a recognized day its reasons, for a day with only some of the marks those it has, else
    empty."""
    row = run.db.execute(
        "SELECT document_json FROM p0_assessment WHERE projection_set_id = ?", (projection,)
    ).fetchone()
    assessment = json.loads(row[0]) if row else None
    corrects = assessment.get("corrects") if isinstance(assessment, dict) else None
    corrects = corrects if isinstance(corrects, dict) else {}
    scope = corrects.get("scope")
    documents = {name: contexts.get(name) for name in CONTEXTS}
    status = {
        name: d.get("context_status") if isinstance(d, dict) else None
        for name, d in documents.items()
    }
    flagged = [name for name in CONTEXTS if status[name] == "not_recomputed"]
    if scope == "core_only" and len(flagged) == len(CONTEXTS) and not found:
        reasons = sorted({str(d.get("not_recomputed_reason")) for d in documents.values()})
        return True, (
            f"corrects.reason={corrects.get('reason')}；not_recomputed_reason={'、'.join(reasons)}"
        )
    if scope == "core_only" or flagged:
        shown = "、".join(f"{name} {status[name]}" for name in CONTEXTS)
        return False, f"corrects.scope={scope}，{shown}，派生值 {len(found)} 个"
    return False, ""


class DailyTally:
    """Per formula, what the day-by-day check found."""

    def __init__(self) -> None:
        self.counts: dict[str, Counter] = defaultdict(Counter)
        self.bad: dict[str, list[str]] = defaultdict(list)
        self.fixed: dict[str, list[str]] = defaultdict(list)
        self.flags: dict[str, dict[str, list[str]]] = defaultdict(dict)

    def add(self, formula: str, day: str, status: str, row: Compared, fixed=False) -> None:
        """``fixed``: the status is a problem of a fixed defect kept in history."""
        self.counts[formula]["天×成员"] += 1
        label = status if status == NOT_RECOMPUTED else status.split("（")[0]
        self.counts[formula][f"{label}（{FIXED_HISTORY}）" if fixed else label] += 1
        if row.verdict in (AGREE, DIFFER, NO_INPUT):
            self.counts[formula][f"重算{row.verdict}"] += 1
        where = day if row.reading == "—" else f"{day} {row.reading}"
        if fixed:
            self.fixed[formula].append(f"{where}：{status}")
        elif not status.startswith(PRESENT_OR_NOT_DUE):
            self.bad[formula].append(f"{where}：{status}")
        if row.verdict == DIFFER:
            shown = f"库中 {_num(row.stored)}、重算 {_num(row.recomputed)}"
            self.bad[formula].append(f"{where}：{DIFFER}（{shown}）")
        for flag in row.flags:
            self.flags[formula].setdefault(flag, []).append(day)

    def problems(self, formula: str) -> list[str]:
        """Presence and value problems by day, then each unmet condition once with its days."""
        found = list(self.bad[formula])
        for flag, days in self.flags[formula].items():
            found.append(f"{flag}（{days[0]} 等 {len(days)} 天）")
        return found


def daily_checks(
    run: Run,
    claims: Claims,
    sessions: Sessions,
    items: list[Item],
    extra: list[str],
    history: list[str],
) -> list[list]:
    """Every day of the window: does that day's projection hold each stored-formula value
    whose inputs were complete that day (point in time: stored by the projection's
    ``system_as_of``, public by the end of the day, or by the frozen cutoff of the run that
    published the day as its target day under the new public cutoff), and does it recompute? Gaps of
    projections made before ADR-0036 that its fix explains go to ``history``, not to
    ``extra``."""
    projections = _day_projections(run)
    manifests = {run.model_version_id: run.manifest}
    tally = DailyTally()
    absent = [day for day in run.window if day not in projections]
    not_recomputed: dict[str, list[str]] = {}  # core-only correction days, by their marks
    mixed: list[str] = []  # days with only part of the core-only marks
    for day, (projection, envelope) in sorted(projections.items()):
        model = envelope.get("model_version_id")
        if model not in manifests:
            row = run.db.execute(
                "SELECT manifest_json FROM model_version WHERE model_version_id = ?", (model,)
            ).fetchone()
            manifests[model] = json.loads(row[0]) if row else {}
        as_of = envelope.get("system_as_of") or run.cutoff
        catalog = manifests[model].get("metric_catalog_version")
        maker = run.db.execute(
            "SELECT r.accepted_at, r.target_business_date, COALESCE(f.system_as_of, r.system_as_of)"
            " FROM projection_set s JOIN parent_run r ON r.run_id = s.batch_id"
            " LEFT JOIN run_cutoff_freeze f ON f.run_id = r.run_id"
            " WHERE s.projection_set_id = ?",
            (projection,),
        ).fetchone()
        accepted = maker and parse_time(maker[0])
        before_fix = bool(maker) and accepted < parse_time(ADR_0036_IN_EFFECT)
        own = projection == run.projection_set_id
        # The day was its run's own target day under the new public cutoff: read it by that
        # run's frozen cutoff, as production did.
        new_cutoff = (
            bool(maker)
            and maker[1] == day
            and accepted >= parse_time(NEW_CUTOFF_IN_EFFECT)
            and bool(maker[2])
        )
        # A projection made by a run accepted before ADR-0036 read only its own catalog
        # version: a problem that reading that way explains is the fixed defect, kept in history.
        strict = Held(claims, as_of, day_end(day), catalog) if catalog and before_fix else None
        strict = None if own else strict
        found: dict[str, dict] = {}
        contexts = {
            name: json.loads(document)
            for name, document in run.db.execute(
                "SELECT dataset_name, document_json FROM analytical_dataset"
                " WHERE projection_set_id = ? AND dataset_name IN ('macro', 'inventory')",
                (projection,),
            )
        }
        for document in contexts.values():
            _derived_records(document, found)
        core_only, marks = _core_only(run, projection, contexts, found)
        if core_only:
            not_recomputed.setdefault(marks, []).append(day)
        elif marks:
            mixed.append(f"{day}（{marks}）")
        # The run's own target day reads by the run's cutoff (公开截止); a window day published
        # as the target day of a run under the new public cutoff by that run's frozen cutoff;
        # any other window day by its own end.
        if own:
            until = run.cutoff_moment
        elif new_cutoff:
            until = parse_time(maker[2])
        else:
            until = day_end(day)
        held = Held(claims, as_of, until, day=day)
        for formula in manifests[model].get("derived_formula_versions", {}).values():
            spec = STORED.get(formula)
            if spec is None:
                tally.counts[formula]["该日模型的公式无独立实现"] += 1
                continue
            if core_only:
                # A core-only correction recomputes no context, so no derived value is due.
                for member in _members(held, spec):
                    reading = "／".join(str(v) for v in member.values()) or "—"
                    tally.add(
                        formula,
                        day,
                        NOT_RECOMPUTED,
                        Compared(formula, reading, "—", None, None, "—"),
                    )
                continue
            records = {}
            for node in found.values():
                if node["formula_version"] == formula:
                    ids = node.get("input_observation_version_ids") or []
                    dims, period = node.get("dimensions"), node.get("period")
                    record = _record(run, spec, node.get("value"), ids, dims, period)
                    records[member_key(record.member)] = record
            for key in sorted({member_key(m) for m in _members(held, spec)} | set(records)):
                member = json.loads(key)
                record = records.get(key)
                status, _, row = _judge(formula, spec, held, sessions, day, member, record)
                fixed = False
                if strict and not status.startswith(PRESENT_OR_NOT_DUE):
                    # Explained only when the strict reading agrees with the projection;
                    # "lineage pruned, cannot check" explains nothing.
                    again = _judge(formula, spec, strict, sessions, day, member, record)[0]
                    fixed = again in EXPLAINED
                tally.add(formula, day, status, row, fixed)

    by_formula = {i.formula: i for i in items}
    rows = []
    for formula, counts in tally.counts.items():
        bad, fixed = tally.problems(formula), tally.fixed[formula]
        where = (
            f"{formula}（{by_formula[formula].label}）"
            if formula in by_formula
            else f"{formula}（只出现在旧模型的日投影中）"
        )
        if bad:
            found = f"逐日核对有 {len(bad)} 处问题（{'；'.join(bad[:3])}）"
            if formula in by_formula:
                by_formula[formula].problems.append(found)
            else:
                extra.append(f"{where}：{found}")
        if fixed:
            shown = "；".join(fixed[:3])
            history.append(f"{where}：逐日核对有 {len(fixed)} 处旧投影问题（{shown}）")
        shown = "、".join(f"{k} {v}" for k, v in counts.items())
        examples = bad + [f"{f}（{FIXED_HISTORY}）" for f in fixed]
        rows.append([formula, shown, "；".join(examples[:4]) or "—"])
    models = Counter(e.get("model_version_id") for _, e in projections.values())
    sources = "、".join(f"{m} {n} 天" for m, n in sorted(models.items()))
    rows.append(["（各日投影的模型）", sources, f"无投影 {len(absent)} 天" if absent else "—"])
    for marks, days in not_recomputed.items():
        shown = f"{len(days)} 天：{compress_days(days, run.window)}"
        rows.append([f"（只更正核心的日子：{NOT_RECOMPUTED}）", shown, marks])
    if mixed:
        shown = "、".join(mixed[:3])
        extra.append(f"窗口内 {len(mixed)} 天只更正核心的标记不一致（{shown}）")
    if absent:
        extra.append(f"窗口内 {len(absent)} 个交易日没有汇总投影（{'、'.join(absent[:6])}）")
    return rows


# --- derived series inside the run's projection -----------------------------------------------


def _projection_indicators(macro: dict) -> dict[str, dict]:
    return {
        ki["key"]: ki
        for dimension in macro.get("confirmation", {}).get("dimensions", [])
        for ki in dimension.get("key_indicators", [])
    }


def _rule_entries(rule: dict) -> list[dict]:
    return [e for e in [rule.get("main"), *rule.get("auxiliary", [])] if e]


def _series_item(formula, label, reading, lineage, held, sessions, compute) -> Item:
    """Recompute every period of a projected series (``periods`` / ``values``)."""
    item = Item(formula, label, "投影（macro）", True)
    periods, values = reading.get("periods") or [], reading.get("values") or []
    if len(periods) != len(values):
        item.problems.append(f"期次 {len(periods)} 个、值 {len(values)} 个，个数不符")
    for period, value in zip(periods, values, strict=False):

        def run_calc(period=period):
            c = Calc(held, sessions, lineage)
            return compute(c, period), c.notes, c.flags

        item.rows.append(_compare(formula, label, period, value, run_calc))
    return item


def _missing_reading(formula: str, label: str, why: str) -> Item:
    item = Item(formula, label, "投影（macro）", True, "缺失", "无可比值")
    item.problems.append(why)
    return item


def _presence_by_newest(item: Item, held, sessions, compute, series, periods) -> None:
    """Rule readings keep the newest period: is it the newest one the raw claims complete?"""
    latest = max(periods, default=None)
    newest = None
    for period in sorted((p for p in series if p <= held.run.target_date), reverse=True):
        try:
            compute(Calc(held, sessions, presence_only=True), period)
            newest = period
            break
        except UNAVAILABLE:
            continue
    if newest is None:
        item.presence = "原料都不齐"
        if latest:
            item.problems.append(f"读数给出 {latest}，独立判断原料都不齐")
    elif latest is None:
        item.presence = "缺失"
        item.problems.append(f"原料已齐至 {newest}，读数却没有值")
    elif latest == newest:
        item.presence = "存在（最新期齐全）"
    else:
        item.presence = f"读数期次 {latest}，原料最新齐全期 {newest}"
        item.problems.append(item.presence)


def _block_grid(sessions: Sessions, rule: dict, target: str) -> list[str]:
    """The block ends the frozen rule asks for: ``lookback_periods`` blocks of
    ``period_sessions`` open days, the last one ending on the target day."""
    n, count = int(rule.get("period_sessions") or 5), int(rule.get("lookback_periods") or 0)
    return sorted(list(reversed(sessions.up_to(target)))[::n][:count])


def _expected_periods(item, shown, expected, computable) -> None:
    """Periods off the expected set are problems; expected periods missing although their
    inputs are complete are problems; missing ones without inputs are only counted."""
    off = sorted(set(shown) - set(expected))
    if off:
        item.problems.append(f"{len(off)} 期不在冻结规则的分期上（{'、'.join(off[:6])}）")
    absent = [p for p in expected if p not in shown]
    due = [p for p in absent if computable(p)]
    if due:
        item.problems.append(f"原料齐全却缺 {len(due)} 期（{'、'.join(due[:6])}）")
    note = f"，另 {len(absent) - len(due)} 期原料不齐" if len(absent) > len(due) else ""
    item.presence = f"应有 {len(expected)} 期、读数 {len(shown)} 期{note}"


def rule_items(run: Run, held: Held, sessions: Sessions) -> list[Item]:
    macro = run.datasets.get("macro")
    rules = run.manifest.get("confirmation_rules", {})
    if macro is None:
        return [_missing_reading(f, f, "本运行没有已发布的投影") for f in RULE_FORMULAS]
    projected = _projection_indicators(macro)
    items: list[Item] = []
    for rule in rules.get("key_indicators", []):
        ki = projected.get(rule["key"], {})
        readings = {m.get("name"): m for m in ki.get("members", [])}
        for entry in _rule_entries(rule):
            formula = entry.get("formula") or entry.get("session_formula")
            if not formula:
                continue
            label = f"{rule['key']}.{entry['name']}"
            reading = readings.get(entry["name"])
            if reading is None:
                items.append(_missing_reading(formula, label, "投影中没有这个成员读数"))
                continue
            items.append(_member_formula(run, rule, entry, formula, label, reading, held, sessions))
        for derived in rule.get("derived", []):
            items.append(_derived_reading(rule, ki, readings, derived, held, sessions, run))
    items += _price_items(run, macro, held, sessions)
    _merge_same_formula(items)
    return items


def _member_formula(run, rule, entry, formula, label, reading, held, sessions) -> Item:
    """A member read through a formula: per-block net injection, or a monthly increment
    against the same month a year earlier."""
    metric = entry.get("metric_id", rule["metric_id"])
    lineage = frozenset(reading.get("observation_version_ids", []))
    periods = reading.get("periods", [])
    if entry.get("session_formula"):
        n = int(rule.get("period_sessions") or 5)

        def blocks(c, p):
            return block_net_injection(c, p, n)

        item = _series_item(formula, label, reading, lineage, held, sessions, blocks)
        expected = _block_grid(sessions, rule, run.target_date)
        _expected_periods(item, periods, expected, _computable(held, sessions, blocks))
        return item
    member = entry.get("dimensions") or YTD

    def yoy(c, p):
        return increment_vs_year_ago(c, metric, member, p)

    item = _series_item(formula, label, reading, lineage, held, sessions, yoy)
    series = held.series(metric, member)
    _presence_by_newest(item, held, sessions, yoy, series, reading.get("periods") or [])
    return item


def _computable(held, sessions, compute, lineage=frozenset()) -> Callable[[str], bool]:
    def check(period: str) -> bool:
        try:
            compute(Calc(held, sessions, lineage, presence_only=True), period)
            return True
        except UNAVAILABLE:
            return False

    return check


def _derived_reading(rule, ki, readings, derived, held, sessions, run) -> Item:
    formula, name = derived["formula"], derived["name"]
    label = f"{rule['key']}.{name}"
    shown = next((d for d in ki.get("derived", []) if d.get("name") == name), None)
    if shown is None:
        return _missing_reading(formula, label, "投影中没有这个派生读数")
    absent = [n for n in derived["of"] if n not in readings]
    if absent:
        return _missing_reading(formula, label, f"投影中没有输入成员读数：{'、'.join(absent)}")
    entries = {e["name"]: e for e in _rule_entries(rule)}
    inputs = [entries[n] for n in derived["of"]]
    ids = [i for n in derived["of"] for i in readings[n].get("observation_version_ids", [])]
    metric = rule["metric_id"]
    if formula == "m1-m2-yoy-spread-v0001":
        first, second = (e.get("dimensions", {}) for e in inputs)

        def compute(c, p):
            return c.get(metric, p, first) - c.get(metric, p, second)

        months = sorted(held.series(metric, second), reverse=True)
        newest = next(
            (m for m in months if m <= run.target_date and _computable(held, sessions, compute)(m)),
            None,
        )
        expected = (
            []
            if newest is None
            else [shift_month(newest, -k) for k in range(AUXILIARY_LOOKBACK)][::-1]
        )
    elif formula == "dr007-policy-spread-sessions-v0001":
        n = int(rule.get("period_sessions") or 5)
        member = inputs[0].get("dimensions", {})

        def compute(c, p):
            return 100 * (block_mean(c, metric, member, p, n) - policy_rate(c, p))

        expected = _block_grid(sessions, rule, run.target_date)
    else:
        why = "本脚本没有该公式的实现"
        return Item(formula, label, "投影（macro）", True, "—", UNCHECKABLE, why)
    item = _series_item(formula, label, shown, frozenset(ids), held, sessions, compute)
    computable = _computable(held, sessions, compute, frozenset(ids))
    _expected_periods(item, shown.get("periods") or [], expected, computable)
    return item


def _core_values(held: Held, metric: str, day: str) -> list[float]:
    obs = held.obs(metric, day, {})
    return sorted({v for _, v in obs.claims if v is not None}) if obs else []


def _price_items(run: Run, macro: dict, held: Held, sessions: Sessions) -> list[Item]:
    rules = run.manifest.get("confirmation_rules", {}).get("price_consistency", {})
    shown = macro.get("price_consistency") or {}
    items = []
    momentum = rules.get("relative_momentum")
    if momentum:
        item = Item(momentum["formula"], "价格一致性：相对动量", "投影（macro）", True)
        readings = {r["key"]: r for r in shown.get("relative_momentum", [])}
        days = sessions.up_to(run.target_date)
        for pair in momentum.get("pairs", []):
            item.rows.append(_momentum(held, momentum, pair, readings.get(pair["key"]), days))
            if pair["key"] not in readings:
                item.problems.append(f"投影中没有 {pair['key']} 读数")
        item.presence = f"{len(readings)}/{len(momentum.get('pairs', []))} 对"
        items.append(item)
    breadth = rules.get("basket_breadth")
    if breadth:
        items.append(_basket_item(run, macro, held, sessions, breadth, momentum))
    return items


def _direction(value: float, against: float, tolerance: float) -> str:
    if value - against > tolerance:
        return "up"
    if against - value > tolerance:
        return "down"
    return "flat"


def _covered_span(sessions: Sessions, target: str, count: int) -> list[str] | None:
    """The ``count`` SSE sessions to the target day (or the open day before it), when the
    calendar speaks for every day from the first of them to the target day."""
    days = sessions.up_to(target)
    if len(days) < count:
        return None
    span = days[-count:]
    day = date.fromisoformat(span[0])
    while day.isoformat() <= target:
        if day.isoformat() not in sessions.covered:
            return None
        day += timedelta(days=1)
    return span


def _gaps(sleeve: str, absent: list[str], days: list[str]) -> list[str]:
    """``absent`` days of ``days``, neighbouring ones merged: ``sleeve:day`` or ``sleeve:a..b``."""
    lacking, out, first, last = set(absent), [], None, None
    for day in [*days, None]:  # a trailing None closes the last run
        if day is not None and day in lacking:
            first, last = first or day, day
            continue
        if first is not None:
            out.append(f"{sleeve}:{first}" if first == last else f"{sleeve}:{first}..{last}")
            first = last = None
    return out


def _basket_reading(sums: dict[str, float], level: float, texts: dict) -> dict:
    """The basket's direction, how many sleeves move with it, and the reading's word."""
    direction = _direction(level, 1.0, BASKET_TOLERANCE)
    sleeves = {s: _direction(v, 0.0, SLEEVE_TOLERANCE) for s, v in sums.items()}
    along, of = sum(d == direction for d in sleeves.values()), len(sums)
    if direction == "flat":
        reading = "flat"
    elif along == 0:
        reading = "unaligned"
    else:
        breadth = "broad" if along * 2 > of else "single_sleeve" if along == 1 else "few_sleeves"
        reading = f"{breadth}_{'rise' if direction == 'up' else 'fall'}"
    return {
        "status": "read",
        "direction": direction,
        "sleeve_directions": sleeves,
        "return_pct": (level - 1) * 100,
        "along": along,
        "of": of,
        "reading": reading,
        "text": texts.get(reading),
        "missing": [],
    }


def _basket_item(run: Run, macro: dict, held: Held, sessions: Sessions, rule, momentum) -> Item:
    """The commodity basket's sleeve breadth, recomputed from the sleeves' contribution claims
    by the rules written in the audit document, and set against the run's projection."""
    dims = rule.get("dimensions") or {}
    formula = dims.get("formula_version", "ex-hog-calendar-settlement")
    label = "价格一致性：商品篮子分项广度"
    shown = (macro.get("price_consistency") or {}).get("basket_breadth") or {}
    item = Item(formula, label, "投影（macro）；分项贡献以来源声明入库", True)
    item.presence = f"读数状态 {shown.get('status', '—')}"
    item.note, item.known = BASKET_DEFINITION, BASKET_KNOWN
    metric, sleeves = rule.get("metric_id"), list(rule.get("sleeves") or [])
    count = (momentum or {}).get("sessions")
    if not metric or not sleeves or type(count) is not int:
        item.verdict, item.known = UNCHECKABLE, ""
        item.note = "冻结规则缺分项贡献指标、分项清单或相对动量跨度"
        return item
    if not shown:
        item.problems.append("投影中没有商品篮子分项广度读数")
    lineage = frozenset(macro.get("model_input_observation_version_ids") or [])
    span = _covered_span(sessions, run.target_date, count + 1)
    days = span[1:] if span else []
    contributions: dict[str, dict[str, float]] = {}
    absent: dict[str, list[str]] = {}
    notes: list[str] = []
    cells, good = _contribution_cells(run, held, metric, dims, set(days))
    for sleeve in sleeves:
        for day in days:
            value, note = _pick_contribution(cells.get((sleeve, day), []), lineage, good)
            if note:
                notes.append(f"{sleeve} {day}：{note}")
            if value is None:
                absent.setdefault(sleeve, []).append(day)
            else:
                contributions.setdefault(sleeve, {})[day] = value
    if span is None:
        mine = {"status": "unconfirmed", "missing": ["trading_calendar_incomplete"]}
    elif absent:
        missing = [g for s in sleeves if s in absent for g in _gaps(s, absent[s], days)]
        mine = {"status": "unconfirmed", "missing": missing}
    else:
        sums = {s: sum(contributions[s][d] for d in days) for s in sleeves}
        level = 1.0
        for day in days:
            level *= 1 + sum(contributions[s][day] for s in sleeves) / 100
        mine = {**_basket_reading(sums, level, rule.get("texts") or {}), "sums": sums}

    period = span[-1] if span else run.target_date
    listed = [e.get("sleeve") for e in shown.get("sleeves") or []]
    stored_sleeves = {e.get("sleeve"): e for e in shown.get("sleeves") or []}
    if mine["status"] == "read":
        note = "；".join(dict.fromkeys(notes))
        for sleeve in sleeves:
            stored = (stored_sleeves.get(sleeve) or {}).get("sum_pp")
            item.rows.append(
                _against(formula, f"sum_pp:{sleeve}", period, stored, mine["sums"][sleeve], note)
            )
        item.rows.append(
            _against(
                formula, "return_pct", period, shown.get("return_pct"), mine["return_pct"], note
            )
        )
    elif shown.get("status") == "read":
        why = "缺 " + "、".join(mine["missing"]) + "（声明可能已被留存删除）"
        item.rows.append(
            Compared(formula, "return_pct", period, shown.get("return_pct"), None, NO_INPUT, why)
        )
        item.known = "已知（原料不齐：分项贡献声明可能已被留存删除，见文档）"
    else:
        same = shown.get("missing") == mine["missing"]
        item.rows.append(
            Compared(formula, "missing", period, None, None, AGREE if same else DIFFER,
                     "缺 " + "、".join(mine["missing"]) + "，按规则不读")
        )  # fmt: skip

    wanted = {
        "status": mine["status"],
        "direction": mine.get("direction"),
        "along": mine.get("along"),
        "of": len(sleeves),
        "reading": mine.get("reading"),
        "text": mine.get("text"),
        "missing": mine["missing"],
    }
    if mine["status"] != "read":
        wanted["return_pct"] = None
    if shown and (mine["status"] == "read" or shown.get("status") != "read"):
        for key, value in wanted.items():
            if shown.get(key) != value:
                item.problems.append(f"basket_breadth.{key} 库中 {shown.get(key)}、重算 {value}")
        for sleeve in sleeves:
            want = mine.get("sleeve_directions", {}).get(sleeve)
            got = stored_sleeves.get(sleeve) or {}
            if got.get("direction") != want:
                item.problems.append(
                    f"basket_breadth {sleeve} 方向 库中 {got.get('direction')}、重算 {want}"
                )
            if mine["status"] != "read" and got.get("sum_pp") is not None:
                item.problems.append(f"basket_breadth {sleeve} 按规则不读，库中却有累计")
        if sorted(map(str, listed)) != sorted(sleeves):
            item.problems.append(f"basket_breadth 分项 库中 {listed}、冻结 {sleeves}")
    inputs = _basket_inputs(run, metric, dims, sleeves, lineage, span, days, mine["status"])
    if inputs[1]:
        item.problems.append(inputs[1])
    item.detail = _basket_detail(span, sleeves, shown, mine, inputs[0], notes)
    return item


def _contribution_cells(run: Run, held: Held, metric: str, dims: dict, days: set[str]):
    """The candidate claims of each (sleeve, day): usable as ``held`` reads them, with every
    key of ``dims`` among their dimensions; and which claims a consumer may read (validated,
    a reported value, a number)."""
    cells: dict[tuple[str, str], list[tuple[str, float | None]]] = defaultdict(list)
    good: set[str] = set()
    rows = run.db.execute(
        "SELECT claim_id, period_end, dimensions_json, value, definition_version,"
        " COALESCE(public_available_at, inferred_public_at), available_at, supersedes_claim_id,"
        " quality_status, value_state FROM source_claim WHERE metric_id = ?",
        (metric,),
    )
    kept = []
    for claim_id, period, dimensions, value, version, public, available, supersedes, *q in rows:
        d = json.loads(dimensions)
        if period not in days or any(d.get(k) != v for k, v in dims.items()):
            continue
        claim = Claim(claim_id, value, version, parse_time(public) if public else None,
                      available, supersedes)  # fmt: skip
        if held._usable(metric, claim, period):
            kept.append((d.get("sleeve"), period, claim))
            if q == ["validated", "reported_value"] and _number(value):
                good.add(claim_id)
    superseded = {c.supersedes for _, _, c in kept if c.supersedes}
    for sleeve, period, c in kept:
        if c.claim_id not in superseded:
            cells[(sleeve, period)].append((c.claim_id, c.value))
    return cells, good


def _number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _pick_contribution(candidates, lineage, good) -> tuple[float | None, str]:
    """One cell's value: the system's choice among the candidates, else their only value; the
    claim used must be one a consumer may read. Choosing between sources is not checked."""
    # Only numbers are sorted and shown; any other value leaves its claim unreadable below.
    values = sorted({v for _, v in candidates if _number(v)})
    split = split_note(values)
    chosen = [(c, v) for c, v in candidates if c in lineage]
    if not chosen:
        if len(values) != 1:
            return None, f"{split}，无系统所选可依" if split else ""
        chosen = [(c, v) for c, v in candidates if v is not None]
    if any(c not in good for c, _ in chosen) or len({v for _, v in chosen}) != 1:
        return None, "所用声明不可读（未校验、非报告值或非数值）"
    value = chosen[0][1]
    return value, f"{split}，按系统所选 {_num(value)}" if split else ""


def _against(formula, reading, period, stored, value, note) -> Compared:
    if stored is None:
        return Compared(formula, reading, period, None, value, DIFFER, "原料齐全，读数却为空")
    return Compared(
        formula, reading, period, stored, value, AGREE if _agrees(stored, value) else DIFFER, note
    )


def _basket_inputs(run, metric, dims, sleeves, lineage, span, days, status) -> tuple[str, str]:
    """Which (sleeve, day) cells the run's frozen inputs cite a contribution claim for: when
    the breadth is read, each of the summed days once, the anchor and beyond the span never."""
    cells: Counter = Counter()
    rows = run.db.execute(
        "SELECT claim_id, period_end, dimensions_json FROM source_claim WHERE metric_id = ?",
        (metric,),
    )
    for claim_id, period, dimensions in rows:
        d = json.loads(dimensions)
        if claim_id in lineage and all(d.get(k) == v for k, v in dims.items()):
            cells[(d.get("sleeve"), period)] += 1
    summed = {(s, day) for s in sleeves for day in days}
    anchor = sum(n for (_, p), n in cells.items() if span and p == span[0])
    outside = sum(
        n for (s, p), n in cells.items() if (s, p) not in summed and not (span and p == span[0])
    )
    twice = sum(1 for c in summed if cells[c] > 1)
    lacking = sum(1 for c in summed if not cells[c])
    shown = (
        f"计入 {sum(cells.values())} 条声明；累计各日 {len(summed) - lacking}/{len(summed)} 格有，"
        f"重复 {twice} 格；跨度首日 {anchor} 条；跨度之外 {outside} 条"
    )
    if status != "read" or not (anchor or outside or twice or lacking):
        return shown, ""
    return shown, f"basket_breadth 计入输入不符：{shown}"


def _basket_detail(span, sleeves, shown, mine, inputs, notes) -> list[str]:
    stored = {e.get("sleeve"): e for e in shown.get("sleeves") or []}
    out = ["### 商品篮子分项广度", ""]
    if span:
        out.append(f"跨度 {span[0]}（锚点，不计入）～{span[-1]}，累计 {len(span) - 1} 日。")
    else:
        out.append("上交所日历不覆盖跨度，按规则不读。")
    out.append("")
    cells = []
    for sleeve in sleeves:
        e = stored.get(sleeve) or {}
        mine_sum = mine.get("sums", {}).get(sleeve)
        cells.append(
            [sleeve, _num(e.get("sum_pp")), _num(mine_sum), e.get("direction") or "—",
             mine.get("sleeve_directions", {}).get(sleeve) or "—"]
        )  # fmt: skip
    cells.append(
        ["篮子（复利收益 %）", _num(shown.get("return_pct")), _num(mine.get("return_pct")),
         shown.get("direction") or "—", mine.get("direction") or "—"]
    )  # fmt: skip
    out.append(table(["分项", "库中累计（百分点）", "重算累计", "库中方向", "重算方向"], cells))
    out.append("")
    pairs = [
        ("状态", shown.get("status"), mine["status"]),
        ("同向数", f"{shown.get('along')}/{shown.get('of')}",
         f"{mine.get('along')}/{mine.get('of')}" if mine["status"] == "read" else "—"),
        ("读法", shown.get("reading"), mine.get("reading")),
        ("文字", shown.get("text"), mine.get("text")),
        ("缺项", "、".join(shown.get("missing") or []) or "无", "、".join(mine["missing"]) or "无"),
    ]  # fmt: skip
    out.append(
        table(
            ["读数", "库中", "重算"],
            [[k, a if a is not None else "—", b if b is not None else "—"] for k, a, b in pairs],
        )
    )
    out += ["", f"系统计入模型输入的分项贡献声明：{inputs}。"]
    if notes:
        out.append(
            f"原料与选值备注 {len(notes)} 处：{'；'.join(notes[:5])}"
            + ("……" if len(notes) > 5 else "")
            + "。"
        )
    out.append("")
    return out


def _momentum(held, momentum, pair, reading, days) -> Compared:
    """One pair: 100 × (return of one core − return of the other) over ``sessions`` sessions
    ending on the target day. Every one of the sessions + 1 closes must be held for both
    cores. Where a close has several sources, every actual combination is tried; the stored
    value agrees when one of them reproduces it."""
    formula, count = momentum["formula"], int(momentum.get("sessions", 120))
    stored = reading.get("value_pp") if reading else None
    if len(days) <= count:
        why = f"上交所日历不足 {count + 1} 个交易日"
        return Compared(formula, pair["key"], "—", stored, None, NO_INPUT, why)
    base, last, inner = days[-count - 1], days[-1], days[-count:-1]
    ends, lacking, gaps = {}, [], []
    for side in (pair["of"], pair["against"]):
        metric = momentum["cores"][side]
        missed = [d for d in inner if not _core_values(held, metric, d)]
        if missed:
            gaps.append(f"{metric} 缺 {len(missed)} 日（{missed[0]} 起）")
        ends[side] = (_core_values(held, metric, base), _core_values(held, metric, last))
        lacking += [f"{metric} {d}" for d, v in zip((base, last), ends[side], strict=True) if not v]
    if gaps:
        # The definition leaves the pair unconfirmed when any close is missing.
        if stored is None:
            return Compared(
                formula, pair["key"], last, None, None, AGREE, "；".join(gaps) + "，按定义留空"
            )
        flag = "；".join(gaps) + "，按定义不应给出读数"
        return Compared(formula, pair["key"], last, stored, None, NO_INPUT, flag, [flag])
    if lacking:
        why = f"缺 {'、'.join(lacking)}（基日是窗口首日的前一交易日，可能已被留存删除）"
        return Compared(formula, pair["key"], last, stored, None, NO_INPUT, why)
    (a_base, a_last), (b_base, b_last) = ends[pair["of"]], ends[pair["against"]]
    results = [
        100 * ((a1 / a0 - 1) - (b1 / b0 - 1))
        for a0, a1, b0, b1 in itertools.product(a_base, a_last, b_base, b_last)
        if a0 and b0
    ]
    if not results:
        return Compared(formula, pair["key"], last, stored, None, NO_INPUT, "基日收盘为零")
    if stored is None:
        return Compared(
            formula, pair["key"], last, None, results[0], DIFFER, "原料齐全，读数却为空"
        )
    match = next((r for r in results if stored is not None and _agrees(stored, r)), None)
    note = f"基日 {base}" + (f"；多源价格共 {len(results)} 种组合" if len(results) > 1 else "")
    value, verdict = (match, AGREE) if match is not None else (results[0], DIFFER)
    return Compared(formula, pair["key"], last, stored, value, verdict, note)


def _merge_same_formula(items: list[Item]) -> None:
    """Members sharing one formula (the loan members) are reported as one item."""
    groups: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        groups[item.formula].append(item)
    for group in groups.values():
        if len(group) < 2:
            continue
        first = group[0]
        statuses = defaultdict(list)
        for item in group:
            statuses[item.presence].append(item.label.split(".")[-1])
        first.problems = [f"{first.label}：{p}" for p in first.problems]
        for item in group[1:]:
            first.rows += item.rows
            first.problems += [f"{item.label}：{p}" for p in item.problems]
            items.remove(item)
        first.label = f"{first.label.split('.')[0]}（{len(group)} 个成员）"
        first.presence = "；".join(
            status if len(statuses) == 1 else f"{status}：{'、'.join(names)}"
            for status, names in statuses.items()
        )


# --- report -------------------------------------------------------------------------------

ITEM_HEADERS = ["#", "公式版本", "指标／读数", "存放处", "模型用到", "存在性", "重算", "定义与说明"]
STORED_HEADERS = ["公式", "成员", "库中期次", "原料最新齐全期", "存在性", "库中值", "重算值"]
STORED_HEADERS += ["结论", "备注"]
DAILY_HEADERS = ["公式", "逐日计数（天×成员）", "问题示例"]
SERIES_HEADERS = ["公式", "读数", "期数", "一致", "有差异", "原料不齐", "期次范围"]
PERIOD_HEADERS = ["公式", "读数", "期次", "库中值", "重算值", "结论", "备注"]
DROPPED_HEADERS = ["指标", "期次", "成员", "值", "排除原因", "页面标题", "页面"]


def _raw_by_day(run: Run, api_name: str) -> dict[str, list[str]]:
    """Per trade date, the raw answers to use: for each distinct request (page), the newest
    answer received by the cutoff."""
    newest: dict[str, tuple[str, str]] = {}
    for parameters, raw_hash in run.db.execute(
        "SELECT parameters_json, raw_hash FROM acquisition_request WHERE api_name = ?"
        " AND raw_hash IS NOT NULL AND received_at <= ? ORDER BY received_at",
        (api_name, run.cutoff),
    ):
        newest[parameters] = (json.loads(parameters).get("trade_date", ""), raw_hash)
    found: dict[str, list[str]] = defaultdict(list)
    for day, raw_hash in newest.values():
        found[iso_day(day)].append(raw_hash) if day else None
    return found


def _rows(run: Run, hashes: list[str]) -> dict[str, dict] | None:
    rows: dict[str, dict] = {}
    for raw_hash in hashes:
        try:
            data = json.loads(run.artifact(raw_hash))["data"]
            rows.update({it[0]: dict(zip(data["fields"], it, strict=True)) for it in data["items"]})
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return None
    return rows


def _a_share(code: str) -> bool:
    number, _, exchange = code.partition(".")
    return not any(exchange == e and number.startswith(prefix) for e, prefix in NOT_A_SHARE)


def breadth_values(daily: dict[str, dict], factors: dict[str, dict] | None) -> dict:
    """{(metric, measure): value} for one day, by ADR-0030."""
    traded = {c: r for c, r in daily.items() if _a_share(c) and r.get("vol")}
    up = [r for r in traded.values() if r["close"] > r["pre_close"]]
    down = sum(r["close"] < r["pre_close"] for r in traded.values())
    flat = len(traded) - len(up) - down
    total = sum(r["amount"] or 0 for r in traded.values())
    out = {
        ("CN_EQ_ADV_DEC", "advances"): len(up),
        ("CN_EQ_ADV_DEC", "declines"): down,
        ("CN_EQ_ADV_DEC", "flats"): flat,
        ("CN_EQ_ADV_DEC", "net"): len(up) - down,
        ("CN_EQ_ADV_DEC", "participants"): len(traded),
    }
    if down:
        out[("CN_EQ_AD_RATIO", "advance_decline_ratio")] = len(up) / down
    if total:
        share = 100 * sum(r["amount"] or 0 for r in up) / total
        out[("CN_EQ_ADV_AMOUNT_SHARE", "advancing_amount_share")] = share
    if factors is None:
        return out
    usable = [factors[c] for c in traded if c in factors]
    for n in (90, 250):
        highs = sum((f.get("topdays") or 0) >= n for f in usable)
        lows = sum((f.get("lowdays") or 0) >= n for f in usable)
        out[(f"CN_EQ_NEW_HIGH_LOW_{n}", "new_highs")] = highs
        out[(f"CN_EQ_NEW_HIGH_LOW_{n}", "new_lows")] = lows
        line = f"ma_qfq_{n}"
        base = [f for f in usable if f.get(line) is not None and f.get("close_qfq") is not None]
        if base:
            above = sum(f["close_qfq"] > f[line] for f in base)
            out[(f"CN_EQ_ABOVE_MA{n}", "above_ma_share")] = 100 * above / len(base)
    return out


def breadth_items(run: Run, claims: Claims) -> list[Item]:
    """Every window day: recompute the breadth series from the raw answers and compare with
    the claims usable by the cutoff (and public by the target day's end)."""
    metrics = [m for m in BREADTH if m in run.catalog]
    if not metrics:
        return []
    held = Held(claims, run.cutoff, run.cutoff_moment, day=run.target_date)
    items = {
        m: Item("—", f"{m}：{BREADTH[m]}", "来源声明（逐日）", m in run.model_used) for m in metrics
    }
    daily, factors = _raw_by_day(run, "daily"), _raw_by_day(run, "stk_factor_pro")
    missing: dict[str, list[str]] = defaultdict(list)
    for day in run.window:
        rows = _rows(run, daily.get(day, [])) if daily.get(day) else None
        computed = (
            {}
            if rows is None
            else breadth_values(
                rows, _rows(run, factors.get(day, [])) if factors.get(day) else None
            )
        )
        for metric in metrics:
            members = held.members(metric)
            measures = {m for (k, m) in computed if k == metric}
            measures |= {k_m for (k, k_m) in BREADTH_MEASURES if k == metric}
            measures |= {m.get("measure") for m in members}
            for measure in sorted(x for x in measures if x):
                key = (metric, measure)
                found = [m for m in members if m.get("measure") == measure]
                obs = next((o for o in (held.obs(metric, day, m) for m in found) if o), None)
                stored = obs.pick(frozenset())[0] if obs else None
                if key not in computed:
                    if rows is None:
                        why = "当日原件缺失或无法解析"
                    elif key in BREADTH_MEASURES:
                        why = "因子原件缺失或分母为零"
                    else:
                        why = "本脚本不重算这个成员"
                    row = Compared("—", measure, day, stored, None, NO_INPUT, why)
                    items[metric].rows.append(row)
                elif obs is None:
                    if key in BREADTH_MEASURES:
                        missing[metric].append(f"{day} {measure}")
                else:
                    agrees = stored is not None and _agrees(stored, computed[key])
                    verdict = AGREE if agrees else DIFFER
                    row = Compared("—", measure, day, stored, computed[key], verdict)
                    items[metric].rows.append(row)
    for metric, item in items.items():
        if missing[metric]:
            shown = "、".join(missing[metric][:6])
            item.problems.append(f"原料齐全却缺 {len(missing[metric])} 个日值（{shown}）")
        item.presence = f"窗口 {len(run.window)} 日" + (
            "" if missing[metric] else "，原料齐全的日子都有值"
        )
        item.note = BREADTH_DEFINITION
    return list(items.values())


def _items(run: Run) -> tuple[list[Item], list[list], list[list], list[str], list[str], Claims]:
    claims, sessions = Claims(run), Sessions(run)
    held = Held(claims, run.cutoff, run.cutoff_moment, day=run.target_date)
    items, detail = stored_items(run, claims, sessions)
    extra: list[str] = []
    history: list[str] = []
    daily = daily_checks(run, claims, sessions, items, extra, history)
    items += rule_items(run, held, sessions) + breadth_items(run, claims)
    for item in items:
        _verdict(item)
        item.note = item.note or RULE_FORMULAS.get(item.formula, "")
        if item.known:
            pass  # the item names its own known limitation
        elif item.verdict == UNCHECKABLE:
            item.known = "已知（定义不足或本票未实现，记于票 02 与文档）"
        elif item.verdict.startswith(NO_INPUT):
            item.known = "已知（基日核心价格被留存删除，见文档“局限”）"
    return items, detail, daily, extra, history, claims


def _dropped_cells(run: Run, claims: Claims) -> list[list]:
    """The excluded news claims a recomputation read among an observation's claims."""
    if not claims.dropped:
        return []
    rows = run.db.execute(
        "SELECT c.claim_id, c.metric_id, c.period_end, c.dimensions_json, c.value, q.title,"
        " COALESCE(NULLIF(q.url, ''), '正文哈希 ' || substr(q.body_hash, 1, 12))"
        " FROM source_claim c JOIN claim_matched_quote q ON q.claim_id = c.claim_id"
        " WHERE c.claim_id IN (SELECT value FROM json_each(?))"
        " ORDER BY c.metric_id, c.period_end, c.dimensions_json, c.claim_id",
        (json.dumps(sorted(claims.dropped)),),
    )
    return [
        [metric, period, "／".join(json.loads(dims).values()) or "—", _num(value)]
        + [claims.excluded[claim_id], title or "—", page]
        for claim_id, metric, period, dims, value, title, page in rows
    ]


def section(run: Run) -> str:
    items, detail, daily, extra, history, claims = _items(run)
    differ = [i for i in items if i.verdict.startswith(DIFFER)]
    agree = [i for i in items if i.verdict.startswith("重算一致")]
    unchecked = [i for i in items if i.verdict == UNCHECKABLE]
    rows = [r for i in items for r in i.rows]
    # Per value: a conflict when any of its inputs has one, else compatible when any differs.
    split = sum(CONFLICT_SPLIT in r.note for r in rows)
    compatible = sum(COMPATIBLE_SPLIT in r.note and CONFLICT_SPLIT not in r.note for r in rows)
    dropped = _dropped_cells(run, claims)
    rest = len(items) - len(agree) - len(differ) - len(unchecked)

    out = ["## 第一层：派生数据（存在性与独立重算）", ""]
    out.append(
        f"**结论**：{len(items)} 项派生指标中，重算一致 {len(agree)} 项、有差异 {len(differ)} 项、"
        f"无法独立核对 {len(unchecked)} 项、其余 {rest} 项原料不齐或无可比值；"
        f"有问题待开票的 {sum(bool(i.problems) for i in items) + len(extra)} 项"
        + (f"；{FIXED_HISTORY}的旧投影问题 {len(history)} 项。" if history else "。")
    )
    out += [
        "",
        f"- 逐值比对 {len(rows)} 个（窗口内逐日核对另见下表）："
        f"一致 {sum(r.verdict == AGREE for r in rows)}、"
        f"有差异 {sum(r.verdict == DIFFER for r in rows)}、"
        f"原料不齐 {sum(r.verdict == NO_INPUT for r in rows)}。",
    ]
    if split or compatible:
        out.append(
            f"- 其中 {split + compatible} 个值的输入有多源取值不同：多源冲突 {split} 个、"
            f"数值不同但在相容范围内 {compatible} 个（ADR-0033：相对偏差不超过 0.5%）。"
            "一律按系统所选的声明重算，选值本身不在本节核对范围，明细备注列出候选值。"
        )
    if dropped:
        out.append(
            f"- 按读取规则排除的资讯声明 {len(dropped)} 条不列入备注的候选值，也不算作多源的一方"
            "（重算仍按系统所选的声明，见下文“按读取规则排除的资讯声明”）。"
        )
    out += ["", "**问题与分流**：", ""]
    out += [f"- {problem}。{TICKET}。" for problem in extra]
    out += [f"- {line}。{FIXED_HISTORY}：{FIXED_HISTORY_WHY}。" for line in history]
    for item in items:
        out += [f"- {item.formula}（{item.label}）：{p}。{TICKET}。" for p in item.problems]
        if item.known:
            out.append(f"- {item.formula}（{item.label}）：{item.verdict}。{item.known}。")
    out += ["", "### 逐项结论", ""]
    cells = [
        [n, i.formula, i.label, i.where, "是" if i.used else "否", i.presence or "—"]
        + [i.verdict + ("（有问题）" if i.problems else ""), i.note]
        for n, i in enumerate(items, 1)
    ]
    out.append(table(ITEM_HEADERS, cells))
    out += ["", "### 派生观测：目标日落库（`derived_observation`）", ""]
    out.append(table(STORED_HEADERS, detail) if detail else "本运行没有落库的派生观测。")
    out += ["", "### 派生观测：窗口内逐日（各日汇总投影）", "", table(DAILY_HEADERS, daily)]
    out += ["", "### 投影内派生序列与股市广度逐日", ""]
    series = [i for i in items if i.where != "派生观测" and i.rows]
    cells = [
        [i.formula, i.label, len(i.rows)]
        + [sum(r.verdict == v for r in i.rows) for v in (AGREE, DIFFER, NO_INPUT)]
        + [f"{min(r.period for r in i.rows)}～{max(r.period for r in i.rows)}"]
        for i in series
    ]
    out.append(table(SERIES_HEADERS, cells) if series else "无。")
    odd = [r for i in series for r in i.rows if r.verdict != AGREE or r.note]
    if odd:
        cells = [
            [r.formula, r.reading, r.period, _num(r.stored), _num(r.recomputed), r.verdict, r.note]
            for r in odd
        ]
        out += ["", "有差异、原料不齐或带备注的期次：", "", table(PERIOD_HEADERS, cells)]
    out += [
        "",
        f"_容差：|库中值 − 重算值| ≤ {TOLERANCE:g} × max(1, |库中值|)。原料只取当时已入库、"
        "当日结束前公开、目录定义与冻结定义相同、未被取代的来源声明。_",
        "",
    ]
    if dropped:
        out += ["### 按读取规则排除的资讯声明", "", table(DROPPED_HEADERS, dropped), ""]
    for item in items:
        out += item.detail
    return "\n".join(out)
