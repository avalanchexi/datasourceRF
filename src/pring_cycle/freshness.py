"""Freshness by due period: each registered source's cadence says which period it owes.

The registry below is the only freshness configuration (ADR-0021). A metric's *due period*
is the latest period whose inferred release plus grace has passed at the run's cutoff:

- holding the latest released period (or newer) is ``current``;
- holding the due period but not a newer released one is ``awaiting_release``;
- holding anything older is ``stale``, ``periods_behind`` counting the missing periods;
- holding nothing is ``missing``; a metric with no registry row is ``unconfigured``.

Release time is the ``lag``-th SSE trading day counted from the period end (the 0th being
the first trading day on or after it) at the registered Shanghai update time. Every count
uses the SSE calendar, foreign sources included. Freshness is recorded, never enforced
here: rejecting data belongs to the structural gate alone.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from pring_cycle.catalog import MetricDefinition
    from pring_cycle.runtime import RuntimePaths

SHANGHAI = ZoneInfo("Asia/Shanghai")
_DEFAULT_GRACE = {"daily": 1, "weekly": 7, "monthly": 7, "quarterly": 7, "event": 0}
_ORDER = ("current", "awaiting_release", "stale", "missing", "unconfigured")


@dataclass(frozen=True)
class FreshnessRule:
    source: str
    frequency: str
    lag: int
    update_time: time
    basis: str
    grace: int | None = None
    day_of_month: int | None = None

    @property
    def grace_days(self) -> int:
        return self.grace if self.grace is not None else _DEFAULT_GRACE[self.frequency]


_TUSHARE_DOCS = "https://tushare.pro/document/1?doc_id=108"
_NBS_2026 = "https://www.stats.gov.cn/xw/tjxw/tzgg/202512/t20251224_1962137.html"
_PBC_FINANCIAL = "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html"


def _daily(source: str, at: time, basis: str, *, lag: int = 0) -> FreshnessRule:
    return FreshnessRule(source, "daily", lag, at, basis)


def _monthly(source: str, lag: int, at: time, basis: str) -> FreshnessRule:
    return FreshnessRule(source, "monthly", lag, at, basis)


def _quarterly(source: str, lag: int, at: time, basis: str) -> FreshnessRule:
    return FreshnessRule(source, "quarterly", lag, at, basis)


_INDEX_CLOSE = time(17, 0)
_AFTER_CLOSE = time(18, 0)
FRESHNESS_REGISTRY: dict[str, FreshnessRule] = {
    "CN_TRADE_CALENDAR": _daily("tushare:trade_cal", time(0, 0), _TUSHARE_DOCS),
    "CN_EQUITY_CORE_000985": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_BOND_CORE_000012": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_COMMODITY_CORE_NHII": _daily("tushare:fut_index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_EQ_CSI300": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_EQ_CSI500": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_EQ_CSI1000": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_BOND_10Y_930916": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_BOND_FULL_PRICE_CNY030": _daily("tushare:index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_COMMODITY_BROAD_NHCI": _daily("tushare:fut_index_daily", _INDEX_CLOSE, _TUSHARE_DOCS),
    "CN_EQ_ADV_DEC": _daily("tushare:daily", time(16, 0), _TUSHARE_DOCS),
    "CN_EQ_AD_RATIO": _daily("tushare:daily", time(16, 0), _TUSHARE_DOCS),
    "CN_EQ_NEW_HIGH_LOW_120": _daily("tushare:daily", time(16, 0), _TUSHARE_DOCS),
    "CN_EQ_ABOVE_MA120": _daily("tushare:daily", time(16, 0), _TUSHARE_DOCS),
    "CN_EQ_ADV_AMOUNT_SHARE": _daily("tushare:daily", time(16, 0), _TUSHARE_DOCS),
    # TuShare documents index_dailybasic only for 上证综指/深证成指/上证50/中证500/中小板指/
    # 创业板指 (doc_id=128), i.e. not 000300 or 000852; real requests on 2026-09-22 still
    # returned all 120 sessions for all three, so the path stays and an empty answer is a gap.
    "CN_INDEX_VALUATION": _daily(
        "tushare:index_dailybasic",
        _AFTER_CLOSE,
        "https://tushare.pro/document/2?doc_id=128",
    ),
    "CN_MARGIN_BALANCE": _daily(
        "tushare:margin", time(9, 5), "https://tushare.pro/document/2?doc_id=58", lag=1
    ),
    "CN_MARGIN_BALANCE_SSE_SZSE": _daily(
        "tushare:margin", time(9, 5), "https://tushare.pro/document/2?doc_id=58", lag=1
    ),
    "CN_DR007": _daily("tushare:repo_daily", time(12, 0), _TUSHARE_DOCS),
    "CN_SHIBOR_ON_1W_3M": _daily("tushare:shibor", time(12, 0), _TUSHARE_DOCS),
    "CN_OMO_7D_RATE": _daily("pbc:omo_notice", time(9, 15), "https://www.pbc.gov.cn/"),
    "CN_OMO_7D_AMOUNT": _daily("pbc:omo_notice", time(9, 15), "https://www.pbc.gov.cn/"),
    "CN_COMMODITY_EX_HOG_BASKET": _daily("tushare:fut_daily", _AFTER_CLOSE, _TUSHARE_DOCS),
    "CN_COMMODITY_SLEEVE_CONTRIBUTION": _daily("tushare:fut_daily", _AFTER_CLOSE, _TUSHARE_DOCS),
    "CN_FUTURES_WARRANTS": _daily("tushare:fut_wsr", _AFTER_CLOSE, _TUSHARE_DOCS),
    "CN_USDCNY_CENTRAL_PARITY": _daily(
        "pbc:central_parity", time(9, 15), "https://www.pbc.gov.cn/"
    ),
    "CN_USDCNY_ECB_REFERENCE_CROSS": _daily(
        "ecb:eurofxref", time(23, 0), "https://www.ecb.europa.eu/stats/"
    ),
    # P2 taken through the lenient search path (ticket 20); US closes land the next
    # Shanghai morning, the CFETS 16:30 close the same afternoon.
    "CN_USDCNY_CLOSE_1630": _daily(
        "search:chinamoney", time(16, 35), "https://www.chinamoney.com.cn/chinese/"
    ),
    "CBOE_VIX_INDEX": _daily("search:cboe", time(6, 0), "https://www.cboe.com/", lag=1),
    "NASDAQ_SOX_INDEX": _daily("search:nasdaq", time(6, 0), "https://www.nasdaq.com/", lag=1),
    "UST10Y_NOMINAL_YIELD": _daily("tushare:us_tycr", time(7, 0), _TUSHARE_DOCS, lag=1),
    "UST2Y_NOMINAL_YIELD": _daily("tushare:us_tycr", time(7, 0), _TUSHARE_DOCS, lag=1),
    "EIA_BRENT_RBRTE": FreshnessRule(
        "eia:petroleum_spot", "weekly", 2, time(23, 0), "https://www.eia.gov/dnav/pet/"
    ),
    "EIA_WTI_RWTC": FreshnessRule(
        "eia:petroleum_spot", "weekly", 2, time(23, 0), "https://www.eia.gov/dnav/pet/"
    ),
    "CN_LPR_1Y_5Y": FreshnessRule(
        "chinamoney:lpr",
        "monthly",
        0,
        time(9, 0),
        "https://www.chinamoney.com.cn/chinese/bklpr/",
        day_of_month=20,
    ),
    "CN_PMI_ACTIVITY": _monthly("tushare:cn_pmi", 0, time(9, 30), _NBS_2026),
    "CN_PMI_INVENTORY": _monthly("tushare:cn_pmi", 0, time(9, 30), _NBS_2026),
    "CN_PMI_PRICES": _monthly("tushare:cn_pmi", 0, time(9, 30), _NBS_2026),
    "CN_CPI_HEADLINE": _monthly("tushare:cn_cpi", 8, time(9, 30), _NBS_2026),
    "CN_CORE_CPI": _monthly("nbs:core_cpi", 8, time(9, 30), _NBS_2026),
    "CN_PPI": _monthly("tushare:cn_ppi", 8, time(9, 30), _NBS_2026),
    "CN_INDUSTRIAL_VA": _monthly("nbs:industrial_va", 12, time(10, 0), _NBS_2026),
    "CN_INDUSTRIAL_FINANCE": _monthly("nbs:industrial_finance", 19, time(9, 30), _NBS_2026),
    "CN_FINISHED_GOODS_INVENTORY": _monthly("nbs:industrial_finance", 19, time(9, 30), _NBS_2026),
    "CN_INVENTORY_TURNOVER": _monthly("nbs:industrial_finance", 19, time(9, 30), _NBS_2026),
    "CN_TOOL_LIQUIDITY_MONTHLY": _monthly("pbc:tool_liquidity", 5, _AFTER_CLOSE, _PBC_FINANCIAL),
    "CN_M1_M2": _monthly("tushare:cn_m", 10, _AFTER_CLOSE, _PBC_FINANCIAL),
    "CN_SF_TOTAL": _monthly("tushare:sf_month", 10, _AFTER_CLOSE, _PBC_FINANCIAL),
    "CN_SF_COMPONENTS": _monthly("pbc:social_financing", 10, _AFTER_CLOSE, _PBC_FINANCIAL),
    "CN_LOAN_STRUCTURE": _monthly("pbc:loan_structure", 10, _AFTER_CLOSE, _PBC_FINANCIAL),
    "CN_CAPACITY_UTILIZATION": _quarterly("nbs:capacity_utilization", 12, time(10, 0), _NBS_2026),
    "CN_GDP": _quarterly("tushare:cn_gdp", 12, time(10, 0), _NBS_2026),
    "CN_RRR_EVENT": FreshnessRule("pbc:rrr_notice", "event", 0, time(0, 0), "event"),
}
# Derived metrics are never registered; they take the worst status among their inputs.
DERIVED_INPUTS: dict[str, tuple[str, ...]] = {
    "CN_DR007_POLICY_SPREAD": ("CN_DR007", "CN_OMO_7D_RATE"),
    "CN_ORDER_INVENTORY_SPREAD": ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"),
    "CN_PRODUCTION_ORDER_SPREAD": ("CN_PMI_ACTIVITY",),
    "CN_CREDIT_IMPULSE": ("CN_SF_TOTAL", "CN_GDP"),
    "UST_2S10S_SPREAD": ("UST10Y_NOMINAL_YIELD", "UST2Y_NOMINAL_YIELD"),
}
# Operational evidence about the run itself, not a series a source owes. The trade
# calendar decides which sessions exist; the calendar gate checks it, not freshness.
NOT_ASSESSED = frozenset(
    {"CN_TRADE_CALENDAR", "CN_RELEASE_SCHEDULE", "SOURCE_OBSERVED_AVAILABILITY"}
)
CORE_METRICS = ("CN_EQUITY_CORE_000985", "CN_BOND_CORE_000012", "CN_COMMODITY_CORE_NHII")


class TradingCalendar:
    """SSE sessions known from the calendar source, and weekdays beyond what it covers."""

    def __init__(self, days: Iterable[date] = ()) -> None:
        self._days = frozenset(days)
        self._first = min(self._days, default=None)
        self._last = max(self._days, default=None)

    def is_trading(self, day: date) -> bool:
        if self._first is not None and self._last is not None and self._first <= day <= self._last:
            return day in self._days
        return day.weekday() < 5

    def nth_from(self, day: date, n: int) -> date:
        """The ``n``-th session counted from ``day``; the 0th is the first on or after it."""
        while not self.is_trading(day):
            day += timedelta(days=1)
        for _ in range(n):
            day += timedelta(days=1)
            while not self.is_trading(day):
                day += timedelta(days=1)
        return day

    def latest_on_or_before(self, day: date) -> date:
        while not self.is_trading(day):
            day -= timedelta(days=1)
        return day


@dataclass(frozen=True)
class FreshnessAssessment:
    metric_id: str
    source: str | None
    frequency: str | None
    status: str
    held_period: str | None
    released_period: str | None
    due_period: str | None
    periods_behind: int | None
    public_available_at: datetime | None
    basis: str | None


def period_end(frequency: str, day: date, calendar: TradingCalendar) -> date:
    """The end of the period ``day`` belongs to."""
    if frequency == "daily":
        return day
    if frequency == "weekly":
        return day + timedelta(days=6 - day.weekday())
    if frequency == "monthly":
        following = date(day.year + day.month // 12, day.month % 12 + 1, 1)
        return following - timedelta(days=1)
    if frequency == "quarterly":
        month = (day.month - 1) // 3 * 3 + 3
        following = date(day.year + month // 12, month % 12 + 1, 1)
        return following - timedelta(days=1)
    raise ValueError(f"freshness_frequency_unsupported:{frequency}")


def _previous_period(frequency: str, end: date, calendar: TradingCalendar) -> date:
    if frequency == "daily":
        return calendar.latest_on_or_before(end - timedelta(days=1))
    if frequency == "weekly":
        return end - timedelta(days=7)
    first = end.replace(day=1) if frequency == "monthly" else _quarter_start(end)
    return first - timedelta(days=1)


def _quarter_start(day: date) -> date:
    return date(day.year, (day.month - 1) // 3 * 3 + 1, 1)


def release_at(rule: FreshnessRule, end: date, calendar: TradingCalendar) -> datetime:
    """When a registered source is taken to publish the period ending on ``end``.

    A pre-announcement the batch received wins (ticket 25); otherwise the Nth SSE trading
    day after the period end at the registered update time.
    """
    announced = _announced_release(rule, end)
    if announced is not None:
        return announced
    if rule.day_of_month is not None:
        day = calendar.nth_from(end.replace(day=rule.day_of_month), 0)
    else:
        day = calendar.nth_from(end, rule.lag)
    return datetime.combine(day, rule.update_time, SHANGHAI)


def _due_at(rule: FreshnessRule, end: date, calendar: TradingCalendar) -> datetime:
    released = release_at(rule, end, calendar)
    day = calendar.nth_from(released.date(), rule.grace_days)
    return datetime.combine(day, rule.update_time, SHANGHAI)


def _periods_back(
    rule: FreshnessRule, cutoff: datetime, calendar: TradingCalendar
) -> Iterator[date]:
    end = period_end(rule.frequency, cutoff.astimezone(SHANGHAI).date(), calendar)
    if rule.frequency == "daily":
        end = calendar.latest_on_or_before(end)
    while True:
        yield end
        end = _previous_period(rule.frequency, end, calendar)


def latest_released_period(
    rule: FreshnessRule, cutoff: datetime, calendar: TradingCalendar
) -> date:
    """The end of the newest period whose registered release time has passed at ``cutoff``."""
    for end in _periods_back(rule, cutoff, calendar):
        if release_at(rule, end, calendar) <= cutoff:
            return end
    raise AssertionError("unreachable: release times fall behind any cutoff")


def assess(
    metric_id: str,
    held_period: date | None,
    cutoff: datetime,
    calendar: TradingCalendar,
    *,
    first_acquired_at: datetime | None = None,
) -> FreshnessAssessment:
    rule = FRESHNESS_REGISTRY.get(metric_id)
    if rule is None:
        return FreshnessAssessment(
            metric_id, None, None, "unconfigured", _text(held_period), None, None, None, None, None
        )
    public = public_available_at(metric_id, held_period, first_acquired_at, calendar)
    if held_period is None:
        # Nothing held still owes a period: the gap list names it (ticket 19).
        released = due = None
        for end in _periods_back(rule, cutoff, calendar) if rule.frequency != "event" else ():
            if released is None and release_at(rule, end, calendar) <= cutoff:
                released = end
            if _due_at(rule, end, calendar) <= cutoff:
                due = end
                break
        return _assessment(metric_id, rule, "missing", None, released, due, None, public)
    if rule.frequency == "event":
        return _assessment(metric_id, rule, "current", held_period, None, None, 0, public)
    held = period_end(rule.frequency, held_period, calendar)
    released = due = None
    behind = 0
    for end in _periods_back(rule, cutoff, calendar):
        if released is None and release_at(rule, end, calendar) <= cutoff:
            released = end
        if _due_at(rule, end, calendar) <= cutoff:
            due = end
            break
        if released is not None and end <= held:
            break
    if released is not None and held >= released:
        status = "current"
    elif due is None or held >= due:
        status = "awaiting_release"
    else:
        status = "stale"
        end = due
        while end > held:
            behind += 1
            end = _previous_period(rule.frequency, end, calendar)
    return _assessment(metric_id, rule, status, held_period, released, due, behind, public)


def _assessment(
    metric_id: str,
    rule: FreshnessRule,
    status: str,
    held: date | None,
    released: date | None,
    due: date | None,
    behind: int | None,
    public: datetime | None,
) -> FreshnessAssessment:
    return FreshnessAssessment(
        metric_id,
        rule.source,
        rule.frequency,
        status,
        _text(held),
        _text(released),
        _text(due),
        behind,
        public,
        rule.basis,
    )


def _text(day: date | None) -> str | None:
    return day.isoformat() if day is not None else None


def worst(assessments: Iterable[FreshnessAssessment]) -> str:
    return max((item.status for item in assessments), key=_ORDER.index, default="missing")


def public_available_at(
    metric_id: str,
    held_period: date | None,
    first_acquired_at: datetime | None,
    calendar: TradingCalendar,
) -> datetime | None:
    """The earlier of the registered release time and when the system first held the value."""
    rule = FRESHNESS_REGISTRY.get(metric_id)
    if held_period is None or rule is None or rule.frequency == "event":
        return first_acquired_at
    inferred = release_at(rule, period_end(rule.frequency, held_period, calendar), calendar)
    return inferred if first_acquired_at is None else min(inferred, first_acquired_at)


def target_business_date(launched_at: datetime, calendar: TradingCalendar) -> date:
    """The latest session whose three core sources have all passed their update time."""
    if launched_at.tzinfo is None:
        raise ValueError("launched_at_must_be_timezone_aware")
    local = launched_at.astimezone(SHANGHAI)
    update = max(FRESHNESS_REGISTRY[metric_id].update_time for metric_id in CORE_METRICS)
    day = calendar.latest_on_or_before(local.date())
    if datetime.combine(day, update, SHANGHAI) > local:
        day = calendar.latest_on_or_before(day - timedelta(days=1))
    return day


BATCH_FRESHNESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS batch_freshness (
    batch_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    source TEXT,
    frequency TEXT,
    status TEXT NOT NULL,
    held_period TEXT,
    released_period TEXT,
    due_period TEXT,
    periods_behind INTEGER,
    public_available_at TEXT,
    basis TEXT,
    assessed_at TEXT NOT NULL,
    PRIMARY KEY(batch_id, metric_id)
);
"""


def record_batch_freshness(
    connection: sqlite3.Connection,
    batch_id: str,
    assessments: Iterable[FreshnessAssessment],
    assessed_at: datetime,
) -> None:
    connection.executescript(BATCH_FRESHNESS_SCHEMA)
    connection.executemany(
        "INSERT OR REPLACE INTO batch_freshness VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                batch_id,
                item.metric_id,
                item.source,
                item.frequency,
                item.status,
                item.held_period,
                item.released_period,
                item.due_period,
                item.periods_behind,
                item.public_available_at.isoformat() if item.public_available_at else None,
                item.basis,
                assessed_at.astimezone(UTC).isoformat(),
            )
            for item in assessments
        ],
    )


def batch_freshness(database: Path, batch_id: str) -> dict[str, dict[str, object]]:
    """The freshness a batch recorded, by metric."""
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_freshness'"
        ).fetchone()
        rows = (
            connection.execute(
                "SELECT * FROM batch_freshness WHERE batch_id=? ORDER BY metric_id", (batch_id,)
            ).fetchall()
            if exists
            else []
        )
    finally:
        connection.close()
    return {str(row["metric_id"]): dict(row) for row in rows}


def assess_catalog(
    metric_ids: Iterable[str],
    held: Mapping[str, tuple[date | None, datetime | None]],
    cutoff: datetime,
    calendar: TradingCalendar,
) -> tuple[FreshnessAssessment, ...]:
    """Assess each catalog metric from its latest held period and first acquisition time."""
    ordered = [metric_id for metric_id in metric_ids if metric_id not in NOT_ASSESSED]

    def direct(metric_id: str) -> FreshnessAssessment:
        period, acquired = held.get(metric_id, (None, None))
        return assess(metric_id, period, cutoff, calendar, first_acquired_at=acquired)

    results = []
    for metric_id in ordered:
        parents = DERIVED_INPUTS.get(metric_id)
        if parents is None:
            results.append(direct(metric_id))
            continue
        inputs = [direct(parent) for parent in parents]
        status = worst(inputs)
        results.append(
            FreshnessAssessment(
                metric_id,
                "derived:" + "+".join(parents),
                None,
                status,
                _text(held.get(metric_id, (None, None))[0]),
                None,
                None,
                max((item.periods_behind or 0 for item in inputs), default=0)
                if status == "stale"
                else 0,
                None,
                json.dumps(parents),
            )
        )
    return tuple(results)


def record_run_freshness(
    database: Path,
    run_id: str,
    definitions: Iterable[MetricDefinition],
    cutoff: datetime,
    calendar: TradingCalendar,
) -> tuple[FreshnessAssessment, ...]:
    """Assess the catalog from what the system held at ``cutoff`` and record it in the batch."""
    from pring_cycle.evidence import AsOfMode, EvidenceRepository
    from pring_cycle.storage import database_connection

    evidence = EvidenceRepository(database)
    catalog = tuple(definitions)
    held: dict[str, tuple[date | None, datetime | None]] = {}
    for definition in catalog:
        if definition.metric_id in NOT_ASSESSED:
            continue
        points = [
            point
            for point in evidence.metric_series(
                definition.metric_id,
                mode=AsOfMode.SYSTEM,
                as_of=cutoff,
                definition_version=definition.definition_version,
            )
            if point.selected_value is not None
        ]
        if not points:
            continue
        latest = max(point.period_end for point in points)
        acquired = min(
            (
                claim.fetched_at
                for point in points
                if point.period_end == latest
                for claim in point.claims
            ),
            default=None,
        )
        held[definition.metric_id] = (date.fromisoformat(latest), acquired)
    assessments = assess_catalog(
        (definition.metric_id for definition in catalog), held, cutoff, calendar
    )
    with database_connection(database) as connection:
        record_batch_freshness(connection, run_id, assessments, cutoff)
    return assessments


def launch_calendar(paths: RuntimePaths, launched_at: datetime) -> TradingCalendar:
    """The SSE sessions around a launch: stored calendar, else TuShare, else weekdays."""
    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.secrets import parse_data_source_secrets
    from pring_cycle.source_adapters import TushareCoreAdapter
    from pring_cycle.storage import database_connection

    day = launched_at.astimezone(SHANGHAI).date()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    with database_connection(paths.database) as connection:
        rows = connection.execute(
            "SELECT acquisition_id FROM acquisition_request WHERE provider='tushare' "
            "AND api_name='trade_cal' AND state='validated' ORDER BY validated_at DESC"
        ).fetchall()
    for (acquisition_id,) in rows:
        receipt = acquisitions.get(acquisition_id)
        if receipt.parameters.get("end_date", "") < day.strftime("%Y%m%d"):
            continue
        try:
            document = json.loads(acquisitions.read_receipt_content(receipt, "normalized"))
        except (ValueError, LookupError, OSError):
            continue
        if isinstance(document, list):
            return TradingCalendar(date.fromisoformat(item) for item in document)
    token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
    if token is None:
        return TradingCalendar()
    acquired = TushareCoreAdapter(token).acquire_calendar(
        acquisitions, day - timedelta(days=30), day
    )
    return TradingCalendar(acquired.value)


class _CalendarSlot:
    calendar: TradingCalendar | None = None
    schedule: Mapping[str, tuple[datetime | date, ...]] = {}


_run_calendar: ContextVar[_CalendarSlot | None] = ContextVar("run_calendar", default=None)


@contextmanager
def run_calendar_scope() -> Iterator[None]:
    """Open a slot for the run's SSE calendar, filled once the run has validated one."""
    token = _run_calendar.set(_CalendarSlot())
    try:
        yield
    finally:
        _run_calendar.reset(token)


def current_calendar() -> TradingCalendar:
    """The run's SSE calendar once known, else weekdays."""
    slot = _run_calendar.get()
    return (slot.calendar if slot is not None else None) or TradingCalendar()


def use_release_schedule(schedule: Mapping[str, tuple[datetime | date, ...]]) -> None:
    """Take release times from these pre-announcements for the rest of the run."""
    slot = _run_calendar.get()
    if slot is not None:
        slot.schedule = schedule


def announced_period_end(source: str, frequency: str, published: date) -> date | None:
    """The end of the period an announced publication covers.

    Official schedules announce last month's (or last quarter's) data, except the PMI,
    which is published at the end of its own month (a February PMI slips into early March).
    Quarterly data comes out in January, April, July and October only.
    """
    month_start = published.replace(day=1)
    previous_end = month_start - timedelta(days=1)
    if frequency == "quarterly":
        return previous_end if published.month in {1, 4, 7, 10} else None
    if frequency != "monthly":
        return None
    if source == "tushare:cn_pmi" and published.day >= 25:
        following = date(published.year + published.month // 12, published.month % 12 + 1, 1)
        return following - timedelta(days=1)
    return previous_end


def _announced_release(rule: FreshnessRule, end: date) -> datetime | None:
    slot = _run_calendar.get()
    if slot is None:
        return None
    for announced in slot.schedule.get(rule.source, ()):
        day = announced.date() if isinstance(announced, datetime) else announced
        if announced_period_end(rule.source, rule.frequency, day) == end:
            if isinstance(announced, datetime):
                return announced
            return datetime.combine(announced, rule.update_time, SHANGHAI)
    return None


def use_run_calendar(calendar: TradingCalendar) -> None:
    """Judge freshness for the rest of the run against ``calendar``."""
    slot = _run_calendar.get()
    if slot is not None:
        slot.calendar = calendar


def period_status(metric_id: str, held_period_end: str, as_of: datetime) -> str:
    """``current`` or ``stale`` for a held period, derived metrics judged by their inputs."""
    calendar = current_calendar()
    held = date.fromisoformat(held_period_end)
    parents = DERIVED_INPUTS.get(metric_id, (metric_id,))
    assessments = [assess(parent, held, as_of, calendar) for parent in parents]
    if any(item.status == "unconfigured" for item in assessments):
        return "stale"
    # One period behind is carried forward and shown as a freshness gap; two or more is
    # treated as missing and kept out of the calculation (ticket 04).
    behind = max((item.periods_behind or 0 for item in assessments), default=0)
    return "stale" if behind >= 2 else "current"


def _failed_candidates(database: Path, run_id: str) -> dict[str, list[dict[str, str]]]:
    """Per metric, up to three distinct candidate URLs the batch rejected, with reasons."""
    from pring_cycle.storage import database_connection

    with database_connection(database) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='retrieval_candidate_validation'"
        ).fetchone():
            return {}
        rows = connection.execute(
            """
            SELECT json_extract(g.identity_json, '$.metric_id'), v.candidate_url, v.reason
            FROM retrieval_candidate_validation v, json_each(v.gap_ids_json) j
            JOIN retrieval_gap g ON g.gap_id = j.value
            WHERE v.run_id=? AND v.outcome='not_model_usable'
              AND coalesce(v.reason, '') <> 'duplicate_candidate'
            ORDER BY v.rowid
            """,
            (run_id,),
        ).fetchall()
    failed: dict[str, dict[str, str]] = {}
    for metric_id, url, reason in rows:
        failed.setdefault(str(metric_id), {})[str(url)] = str(reason)
    return {
        metric_id: [{"url": url, "reason": reason} for url, reason in list(urls.items())[:3]]
        for metric_id, urls in failed.items()
    }


_GAP_ORDER = ("missing", "retrieval_failed", "freshness_gap", "unconfigured", "rejected")


def gap_list(
    database: Path, run_id: str, definitions: Iterable[MetricDefinition]
) -> list[dict[str, object]]:
    """Gate ①'s visible gap list for one batch, grouped by what the maintainer should do.

    ``missing``: nothing held, or two or more periods behind (not used in calculation);
    ``freshness_gap``: one period behind, carried forward; ``unconfigured``: no freshness
    registry row; ``rejected``: a response failed its structure check (gate ③);
    ``retrieval_failed``: still missing or behind after search candidates were refetched
    and none passed, listing up to three URLs each with its reason (ticket 19).
    """
    from pring_cycle.storage import database_connection

    priorities = {item.metric_id: item.priority for item in definitions}
    failed_candidates = _failed_candidates(database, run_id)
    gaps: list[dict[str, object]] = []
    for metric_id, row in batch_freshness(database, run_id).items():
        status, behind = row["status"], row["periods_behind"]
        if status == "missing":
            category, reason = "missing", "not_held"
        elif status == "stale" and behind == 1:
            category, reason = "freshness_gap", "one_period_behind_carried"
        elif status == "stale":
            category, reason = "missing", "two_or_more_periods_behind"
        elif status == "unconfigured":
            category, reason = "unconfigured", "freshness_not_registered"
        else:
            continue
        gap: dict[str, object] = {
            "metric_id": metric_id,
            "priority": priorities.get(metric_id),
            "category": category,
            "reason": reason,
            "due_period": row["due_period"],
            "held_period": row["held_period"],
            "periods_behind": behind,
        }
        if metric_id in failed_candidates:
            # An unconfigured metric has no due period; it keeps its category.
            if category != "unconfigured":
                gap["category"] = "retrieval_failed"
            gap["candidates"] = failed_candidates[metric_id]
        gaps.append(gap)
    with database_connection(database) as connection:
        rejected = connection.execute(
            """
            SELECT a.metric_ids_json, r.api_name, r.rejection_reason
            FROM full_run_acquisition a JOIN acquisition_request r USING (acquisition_id)
            WHERE a.run_id=? AND r.structure_check='rejected'
            """,
            (run_id,),
        ).fetchall()
    # A rejected search candidate is already shown with its URL under retrieval_failed.
    seen = set(failed_candidates)
    for metric_ids_json, api_name, reason in rejected:
        for metric_id in json.loads(metric_ids_json or "[]"):
            if metric_id in seen or metric_id not in priorities or metric_id in NOT_ASSESSED:
                continue
            seen.add(metric_id)
            gaps.append(
                {
                    "metric_id": metric_id,
                    "priority": priorities.get(metric_id),
                    "category": "rejected",
                    "reason": f"{api_name}:{reason}",
                    "due_period": None,
                    "held_period": None,
                    "periods_behind": None,
                }
            )
    return sorted(
        gaps,
        key=lambda item: (
            str(item["priority"]),
            _GAP_ORDER.index(str(item["category"])),
            str(item["metric_id"]),
        ),
    )
