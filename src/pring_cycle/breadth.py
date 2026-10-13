"""Market breadth computed from TuShare's own deliveries (ADR-0030).

The members are every ordinary A share of Shanghai, Shenzhen and Beijing, ST included, B
shares and CDRs excluded, with listing intervals rebuilt from ``stock_basic`` in its three
listing states. Each trading day takes one full-market ``daily`` and one ``stk_factor_pro``
delivery, paged when the market outgrows a page; a day already held is not fetched again.

- Advances, declines and the ratio compare ``close`` with ``pre_close``; a first trading day
  counts, a suspended share or one with no volume does not take part.
- The advancing amount share uses ``daily.amount`` above and below the line.
- The 90- and 250-day windows read TuShare's factors: ``topdays``/``lowdays`` of at least N
  is an N-day high/low, and a forward-adjusted close strictly above its moving average is
  above the line. Their members traded that day, have been listed for at least N trading
  days and have the factor.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from datetime import date
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pring_cycle.tushare_context import ContextScalar

DAILY_SOURCE_CODE = "tushare:daily:breadth-v0003"
AMOUNT_SOURCE_CODE = "tushare:daily:breadth-amount-v0003"
WINDOW_SOURCE_CODE = "tushare:stk_factor_pro:breadth-window-v0003"
UNIVERSE = "point_in_time_traded_a_shares"
API_NAME = "breadth"
WINDOWS = (90, 250)
# Metric: its registered source code and each (measure, unit) it reports.
BREADTH_METRICS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "CN_EQ_ADV_DEC": (
        DAILY_SOURCE_CODE,
        tuple(
            (measure, "count")
            for measure in ("advances", "declines", "flats", "net", "participants")
        ),
    ),
    "CN_EQ_AD_RATIO": (DAILY_SOURCE_CODE, (("advance_decline_ratio", "ratio"),)),
    "CN_EQ_ADV_AMOUNT_SHARE": (AMOUNT_SOURCE_CODE, (("advancing_amount_share", "percent"),)),
    **{
        f"CN_EQ_NEW_HIGH_LOW_{window}": (
            WINDOW_SOURCE_CODE,
            (("new_highs", "count"), ("new_lows", "count")),
        )
        for window in WINDOWS
    },
    **{
        f"CN_EQ_ABOVE_MA{window}": (WINDOW_SOURCE_CODE, (("above_ma_share", "percent"),))
        for window in WINDOWS
    },
}
PAGE_ROWS = 6000
_LISTING_FIELDS = ("ts_code", "list_status", "list_date", "delist_date")
_DAILY_FIELDS = ("ts_code", "trade_date", "close", "pre_close", "vol", "amount")
_FACTOR_FIELDS = (
    "ts_code",
    "trade_date",
    "close_qfq",
    *(f"ma_qfq_{window}" for window in WINDOWS),
    "topdays",
    "lowdays",
)

Rows = tuple[dict[str, object], ...]
Call = Callable[[str, dict[str, str], tuple[str, ...]], Rows]


def source_field(metric_id: str, measure: str) -> str:
    """The field a claim names in its source reference: window measures carry their N."""
    suffix = metric_id.rsplit("_", 1)[-1].removeprefix("MA")
    return f"{measure}_{suffix}" if suffix.isdigit() and int(suffix) in WINDOWS else measure


def ordinary_share(code: str) -> bool:
    """Whether ``code`` is an ordinary A share; an unrecognised code refuses the delivery."""
    symbol, separator, exchange = code.partition(".")
    if separator and len(symbol) == 6 and symbol.isascii() and symbol.isdigit():
        if exchange == "SH":
            if symbol.startswith(("600", "601", "603", "605", "688")):
                return True
            if symbol.startswith(("689", "900")):  # CDR and B shares are outside this scope.
                return False
        elif exchange == "SZ":
            # SZSE's March 2026 code allocation distinguishes ordinary shares
            # from main-board and ChiNext depositary receipts within 001/30.
            number = int(symbol)
            if (
                1 <= number <= 999
                or 1200 <= number <= 1999
                or 2000 <= number <= 4999
                or 300000 <= number <= 309799
            ):
                return True
            if symbol.startswith("200") or 1001 <= number <= 1199 or 309800 <= number <= 309999:
                return False
        elif exchange == "BJ" and symbol.startswith(("4", "8", "920")):
            return True
    raise ValueError("tushare_breadth_security_scope_unknown")


def paged(call: Call, api_name: str, params: dict[str, str], fields: tuple[str, ...]) -> Rows:
    """Every row of a full-market delivery, one page after another until a short page."""
    rows: list[dict[str, object]] = []
    while True:
        page = call(api_name, {**params, "limit": str(PAGE_ROWS), "offset": str(len(rows))}, fields)
        rows.extend(page)
        if len(page) < PAGE_ROWS:
            return tuple(rows)


def _day(value: object) -> date:
    text = str(value)
    if len(text) != 8 or not text.isdigit():
        raise ValueError("tushare_breadth_date_invalid")
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value):
        raise ValueError("tushare_breadth_value_invalid")
    return float(value)


def listing_intervals(rows: Rows) -> dict[str, tuple[date, date | None]]:
    """Each security's listing and delisting dates, from ``stock_basic``'s three states.

    Only a code that trades on a computed day is classified; the listings also carry codes
    retired long before the window, some in formats no current rule covers (``T600018.SH``).
    """
    intervals: dict[str, tuple[date, date | None]] = {}
    for row in rows:
        code = row.get("ts_code")
        if not isinstance(code, str):
            raise ValueError("tushare_breadth_listing_code_invalid")
        if code in intervals:
            raise ValueError("tushare_breadth_listing_duplicate")
        delisted = row.get("delist_date")
        intervals[code] = (_day(row.get("list_date")), _day(delisted) if delisted else None)
    return intervals


def _listed(interval: tuple[date, date | None], day: date) -> bool:
    listed, delisted = interval
    return listed <= day and (delisted is None or day < delisted)


def day_scalars(
    business_date: date,
    quotes: Rows,
    factors: Rows | None,
    *,
    listings: dict[str, tuple[date, date | None]],
    open_days: list[date],
) -> tuple[ContextScalar, ...]:
    """The seven metrics of one trading day; the four windows only when ``factors`` came."""
    from pring_cycle.tushare_context import ContextScalar

    traded: dict[str, tuple[float, float, float]] = {}
    for row in quotes:
        code = row.get("ts_code")
        if not isinstance(code, str) or _day(row.get("trade_date")) != business_date:
            raise ValueError("tushare_breadth_trade_date_mismatch")
        if not ordinary_share(code):
            continue
        if code not in listings:
            raise ValueError("tushare_breadth_listing_missing")
        if not _listed(listings[code], business_date):
            continue  # Outside its listing interval: not a member that day.
        if code in traded:
            raise ValueError("tushare_breadth_quote_duplicate")
        close, previous = _number(row.get("close")), _number(row.get("pre_close"))
        volume, amount = _number(row.get("vol")), _number(row.get("amount"))
        if not volume or close is None or previous is None or close <= 0 or previous <= 0:
            continue  # Suspended, or no trade: not a participant.
        if amount is None or amount < 0:
            raise ValueError("tushare_breadth_amount_invalid")
        traded[code] = (close, previous, amount)
    advances = sum(close > previous for close, previous, _ in traded.values())
    declines = sum(close < previous for close, previous, _ in traded.values())
    total_amount = sum(amount for *_, amount in traded.values())
    advancing_amount = sum(
        amount for close, previous, amount in traded.values() if close > previous
    )
    values: list[tuple[str, str, float]] = []
    if traded:
        values += [
            ("CN_EQ_ADV_DEC", "advances", advances),
            ("CN_EQ_ADV_DEC", "declines", declines),
            ("CN_EQ_ADV_DEC", "flats", len(traded) - advances - declines),
            ("CN_EQ_ADV_DEC", "net", advances - declines),
            ("CN_EQ_ADV_DEC", "participants", len(traded)),
        ]
    if declines:
        values.append(("CN_EQ_AD_RATIO", "advance_decline_ratio", advances / declines))
    if total_amount > 0:
        values.append(
            (
                "CN_EQ_ADV_AMOUNT_SHARE",
                "advancing_amount_share",
                100 * advancing_amount / total_amount,
            )
        )
    if factors is not None:
        values += _window_values(business_date, factors, traded, listings, open_days)
    units = {
        (metric_id, measure): unit
        for metric_id, (_code, measures) in BREADTH_METRICS.items()
        for measure, unit in measures
    }
    return tuple(
        ContextScalar(
            metric_id=metric_id,
            api_name=API_NAME,
            source_field=source_field(metric_id, measure),
            period_kind="business_day",
            period_start=business_date.isoformat(),
            period_end=business_date.isoformat(),
            dimensions={"measure": measure, "universe": UNIVERSE},
            value=float(value),
            unit=units[metric_id, measure],
        )
        for metric_id, measure, value in values
    )


def _window_values(
    business_date: date,
    factors: Rows,
    traded: dict[str, tuple[float, float, float]],
    listings: dict[str, tuple[date, date | None]],
    open_days: list[date],
) -> list[tuple[str, str, float]]:
    seen: set[str] = set()
    eligible: dict[int, list[dict[str, object]]] = {window: [] for window in WINDOWS}
    first_open = open_days[0]
    for row in factors:
        code = row.get("ts_code")
        if not isinstance(code, str) or _day(row.get("trade_date")) != business_date:
            raise ValueError("tushare_breadth_trade_date_mismatch")
        if code in seen:
            raise ValueError("tushare_breadth_factor_duplicate")
        seen.add(code)
        if code not in traded:
            continue
        listed = listings[code][0]
        # Listed before the calendar fetched: well over the longest window.
        age = len(open_days) + 1 if listed < first_open else _open_days_between(open_days, listed)
        for window in WINDOWS:
            if age >= window:
                eligible[window].append(row)
    values: list[tuple[str, str, float]] = []
    for window, rows in eligible.items():
        extremes = [
            (high, low)
            for row in rows
            if (high := _number(row.get("topdays"))) is not None
            and (low := _number(row.get("lowdays"))) is not None
        ]
        if extremes:
            metric_id = f"CN_EQ_NEW_HIGH_LOW_{window}"
            values.append((metric_id, "new_highs", sum(high >= window for high, _ in extremes)))
            values.append((metric_id, "new_lows", sum(low >= window for _, low in extremes)))
        averages = [
            (close, average)
            for row in rows
            if (close := _number(row.get("close_qfq"))) is not None
            and (average := _number(row.get(f"ma_qfq_{window}"))) is not None
        ]
        if averages:
            above = sum(close > average for close, average in averages)
            values.append(
                (f"CN_EQ_ABOVE_MA{window}", "above_ma_share", 100 * above / len(averages))
            )
    return values


def _open_days_between(open_days: list[date], listed: date) -> int:
    """Trading days from the listing date to the last day fetched, both included."""
    return sum(day >= listed for day in open_days)


def breadth_scalars(
    call: Call,
    *,
    end_date: date,
    sessions: Sequence[date],
    held_days: Iterable[date] = (),
    window: int = 120,
    calendar_ids: tuple[str, ...] = (),
) -> tuple[ContextScalar, ...]:
    """Each of the last ``window`` trading days to ``end_date`` not already held.

    ``sessions`` are the SSE's, from the trading calendar: the window, and before it enough
    to tell any share's age up to 250. Every figure names the calendar responses it counted
    on (``calendar_ids``). The listings are fetched only when a day is left to compute.
    Nothing is returned only when every day is held; days fetched that give no figure raise
    an empty delivery (``source_empty``).
    """
    sessions = sorted(day for day in sessions if day <= end_date)
    held = set(held_days)
    days = [day for day in sessions[-window:] if day not in held]
    if not days:
        return ()
    listings: list[dict[str, object]] = []
    for status in ("L", "D", "P"):
        rows = paged(call, "stock_basic", {"list_status": status}, _LISTING_FIELDS)
        if any(row.get("list_status") != status for row in rows):
            raise ValueError("tushare_breadth_listing_status_invalid")
        listings.extend(rows)
    members = listing_intervals(tuple(listings))
    scalars: list[ContextScalar] = []
    for day in days:
        params = {"trade_date": day.strftime("%Y%m%d")}
        quotes = paged(call, "daily", params, _DAILY_FIELDS)
        factors: Rows | None
        try:
            factors = paged(call, "stk_factor_pro", params, _FACTOR_FIELDS)
        except (OSError, ValueError):
            # The windows stay missing for the day; the daily figures do not depend on them.
            factors = None
        scalars.extend(
            day_scalars(
                day,
                quotes,
                factors,
                listings=members,
                open_days=[session for session in sessions if session <= day],
            )
        )
    if not scalars:
        from pring_cycle.tushare_context import ContextObservationsMissingError

        # Asked for and answered with nothing to compute: an empty delivery, which is not a
        # window all held (ticket 06).
        raise ContextObservationsMissingError("source_empty")
    return tuple(replace(scalar, acquisition_ids=calendar_ids) for scalar in scalars)
