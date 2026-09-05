"""Validated daily inputs for a proposed ordinary A-share breadth definition.

These inputs carry no publication claim and do not certify a historical replay.
Missing after-hours amounts remain unknown, including before provider coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class MarketBreadthQuote:
    """CNY prices; regular and after-hours turnover are each in thousand CNY."""

    ts_code: str
    close: float
    pre_close: float
    amount: float
    after_hours_amount: float | None


@dataclass(frozen=True)
class FullDaySuspensionEvidence:
    """A reviewed document's dated assertion, not a source certification grant."""

    business_date: date
    ts_code: str
    document_sha256: str


@dataclass(frozen=True)
class MarketBreadthDay:
    business_date: date
    listed_on: tuple[tuple[str, date], ...]
    suspended_codes: tuple[str, ...]
    quotes: tuple[MarketBreadthQuote, ...]
    full_day_suspension_evidence: tuple[FullDaySuspensionEvidence, ...] = ()
    membership_basis: str = "current_stock_basic_listing_intervals_not_public_as_of"

    @property
    def listed_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.listed_on)


@dataclass(frozen=True)
class _Listing:
    ts_code: str
    listed_on: date
    delisted_on: date | None


def _listing_intervals(
    rows: tuple[dict[str, object], ...], *, first_day: date, last_day: date
) -> tuple[_Listing, ...]:
    result = []
    seen = set()
    for row in rows:
        code = row["ts_code"]
        if not isinstance(code, str):
            raise ValueError("tushare_breadth_code_invalid")
        if code in seen:
            raise ValueError("tushare_breadth_duplicate_code")
        seen.add(code)
        status = row["list_status"]
        if status not in ("L", "D", "P"):
            raise ValueError("tushare_breadth_listing_status_invalid")
        listed = _date(row["list_date"])
        delisted = None if row["delist_date"] in (None, "") else _date(row["delist_date"])
        if (status == "D") != (delisted is not None) or (
            delisted is not None and delisted <= listed
        ):
            raise ValueError("tushare_breadth_listing_interval_invalid")
        if listed > last_day or (delisted is not None and delisted <= first_day):
            continue
        if _ordinary_share(code):
            result.append(_Listing(code, listed, delisted))
    if not result:
        raise ValueError("tushare_breadth_members_missing")
    return tuple(result)


def _input_day(
    business_date: date,
    *,
    listings: tuple[_Listing, ...],
    quotes: tuple[dict[str, object], ...],
    suspensions: tuple[dict[str, object], ...],
    full_day_suspension_evidence: tuple[FullDaySuspensionEvidence, ...] = (),
) -> MarketBreadthDay:
    if len(quotes) >= 6_000:
        raise ValueError("tushare_breadth_response_incomplete")
    quote_rows = _unique_rows(quotes, business_date)
    listed = {
        item.ts_code: item.listed_on
        for item in listings
        if item.listed_on <= business_date
        and (item.delisted_on is None or business_date < item.delisted_on)
    }
    if not listed:
        raise ValueError("tushare_breadth_members_missing")
    suspended: set[str] = set()
    resumed: set[str] = set()
    suspension_events = set()
    for row in suspensions:
        code = _row_code(row, business_date)
        kind = row["suspend_type"]
        timing = _suspension_timing(row["suspend_timing"])
        if kind not in ("S", "R"):
            raise ValueError("tushare_breadth_suspension_invalid")
        event = (code, kind, timing)
        if event in suspension_events:
            raise ValueError("tushare_breadth_duplicate_suspension")
        suspension_events.add(event)
        if code in listed and kind == "S" and not timing:
            suspended.add(code)
        if code in listed and kind == "R":
            resumed.add(code)
    resolved: dict[str, FullDaySuspensionEvidence] = {}
    for evidence in full_day_suspension_evidence:
        if (
            evidence.business_date != business_date
            or evidence.ts_code in resolved
            or re.fullmatch(r"[0-9a-f]{64}", evidence.document_sha256) is None
        ):
            raise ValueError("tushare_breadth_suspension_evidence_invalid")
        resolved[evidence.ts_code] = evidence
    if resolved.keys() - (suspended & resumed):
        raise ValueError("tushare_breadth_suspension_evidence_not_applicable")
    if (suspended & resumed) - resolved.keys():
        raise ValueError("tushare_breadth_suspension_conflict")
    ordinary_quotes = {code: row for code, row in quote_rows.items() if _ordinary_share(code)}
    if ordinary_quotes.keys() != listed.keys() - suspended:
        raise ValueError("tushare_breadth_quote_membership_mismatch")
    normalized = []
    for code, row in sorted(ordinary_quotes.items()):
        amount = _number(row["amount"])
        after_hours = row["ah_amount"]
        normalized.append(
            MarketBreadthQuote(
                code,
                _number(row["close"], positive=True),
                _number(row["pre_close"], positive=True),
                amount,
                None if after_hours is None else _number(after_hours),
            )
        )
    return MarketBreadthDay(
        business_date,
        tuple(sorted(listed.items())),
        tuple(sorted(suspended)),
        tuple(normalized),
        tuple(resolved[code] for code in sorted(resolved)),
    )


def _unique_rows(
    rows: tuple[dict[str, object], ...], business_date: date
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        code = _row_code(row, business_date)
        if code in result:
            raise ValueError("tushare_breadth_duplicate_code")
        result[code] = row
    return result


def _row_code(row: dict[str, object], business_date: date) -> str:
    if _date(row["trade_date"]) != business_date:
        raise ValueError("tushare_breadth_trade_date_mismatch")
    code = row["ts_code"]
    if not isinstance(code, str):
        raise ValueError("tushare_breadth_code_invalid")
    _ordinary_share(code)
    return code


def _ordinary_share(code: str) -> bool:
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


def _suspension_timing(value: object) -> tuple[tuple[int, int], ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, str):
        raise ValueError("tushare_breadth_suspension_invalid")
    intervals = []
    for interval in value.split(","):
        edges = interval.split("-")
        if len(edges) != 2:
            raise ValueError("tushare_breadth_suspension_invalid")
        seconds = []
        for edge in edges:
            match = re.fullmatch(r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?", edge.strip())
            if match is None:
                raise ValueError("tushare_breadth_suspension_invalid")
            hour, minute, second = (int(item or 0) for item in match.groups())
            if hour > 23 or minute > 59 or second > 59:
                raise ValueError("tushare_breadth_suspension_invalid")
            seconds.append(hour * 3600 + minute * 60 + second)
        if seconds[1] <= seconds[0]:
            raise ValueError("tushare_breadth_suspension_invalid")
        intervals.append((seconds[0], seconds[1]))
    intervals.sort()
    if any(left[1] > right[0] for left, right in zip(intervals, intervals[1:], strict=False)):
        raise ValueError("tushare_breadth_suspension_invalid")
    return tuple(intervals)


def _date(value: object) -> date:
    if not isinstance(value, str) or len(value) != 8 or not value.isascii() or not value.isdigit():
        raise ValueError("tushare_breadth_date_invalid")
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError as error:
        raise ValueError("tushare_breadth_date_invalid") from error


def _number(value: object, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int, str)):
        raise ValueError("tushare_breadth_number_invalid")
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError("tushare_breadth_number_invalid") from error
    if not isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError("tushare_breadth_number_invalid")
    return number
