"""Validated daily inputs for a proposed ordinary A-share breadth definition.

Legacy inputs carry no publication claim. Reviewed historical pools support
versioned daily counts with evidence-bound times; neither path grants certification.
Missing after-hours amounts remain unknown, including before provider coverage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from pring_cycle.acquisition import AcquisitionReceipt
    from pring_cycle.evidence import EvidenceRepository, MetricSeriesPoint
    from pring_cycle.tushare_context import ContextScalar


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


class DailyBreadthResult(TypedDict):
    business_date: str
    members: list[dict[str, Any]]
    advances: int
    declines: int
    flats: int
    participants: int
    net: int
    advance_decline_ratio: float | None
    status: str
    zero_declines: bool
    release_at: str | None
    public_available_at: str | None


DAILY_BREADTH_SOURCE_CODE = "tushare:daily:breadth-v0002"
DAILY_BREADTH_MEASURES = {
    "CN_EQ_ADV_DEC": ("advances", "declines", "flats", "net", "participants"),
    "CN_EQ_AD_RATIO": ("advance_decline_ratio",),
}


def _breadth_artifact(root: Path, digest: str) -> bytes:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("breadth_evidence_hash_invalid")
    raw = (root / digest[:2] / digest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("breadth_evidence_hash_mismatch")
    return raw


def _breadth_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _breadth_time(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("breadth_publication_invalid")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("breadth_publication_invalid")
    return result


def load_breadth_universe(raw: bytes, artifacts: Path) -> dict[str, Any]:
    """Read an explicitly reviewed historical pool; current stock_basic is not a substitute.

    The review binds effective identity intervals and their original documents. It
    is an input review, never a source certification or a claim about review time
    being the historical publication time.
    """
    document = json.loads(raw)
    if (
        not isinstance(document, dict)
        or document["schema_version"] != "market-breadth-universe-v0001"
    ):
        raise ValueError("breadth_universe_schema_invalid")
    subject = {k: v for k, v in document.items() if k != "review_hash"}
    review = json.loads(_breadth_artifact(artifacts, document["review_hash"]))
    if (
        review["schema_version"] != "market-breadth-universe-review-v0001"
        or review["subject_hash"] != hashlib.sha256(_breadth_json(subject).encode()).hexdigest()
        or review["decision"] != "accepted"
        or not isinstance(review["reviewer"], str)
        or not review["reviewer"].strip()
        or _breadth_time(review["reviewed_at"]) is None
    ):
        raise ValueError("breadth_universe_review_invalid")
    proof_ids: set[str] = set()
    for proof in document["evidence"]:
        if proof["artifact_hash"] in proof_ids:
            raise ValueError("breadth_evidence_duplicate")
        proof_ids.add(proof["artifact_hash"])
        _breadth_artifact(artifacts, proof["artifact_hash"])
        release = _breadth_time(proof["release_at"])
        public = _breadth_time(proof["public_available_at"])
        if not proof["source_reference"]:
            raise ValueError("breadth_publication_invalid")
        if proof.get("published_date") is not None:
            from pring_cycle.evidence import publication_times

            published_date = date.fromisoformat(proof["published_date"])
            if published_date.isoformat() != proof["published_date"] or (
                release,
                public,
            ) != publication_times(published_date, ZoneInfo("Asia/Shanghai")):
                raise ValueError("breadth_publication_invalid")
        elif public is not None and (release is None or public < release):
            raise ValueError("breadth_publication_invalid")
    references = [
        document["coverage_evidence"],
        *[m["evidence"] for m in document["members"]],
        *[e["evidence"] for e in document["events"]],
    ]
    for reference in references:
        if (
            not isinstance(reference, list)
            or not reference
            or len(set(reference)) != len(reference)
            or not set(reference) <= proof_ids
        ):
            raise ValueError("breadth_evidence_missing")
    for reference in document["publications"].values():
        if (
            not isinstance(reference, list)
            or len(set(reference)) != len(reference)
            or not set(reference) <= proof_ids
        ):
            raise ValueError("breadth_publication_evidence_invalid")
    intervals: dict[tuple[str, str], list[tuple[date, date]]] = {}
    for member in document["members"]:
        code, identity = member["ts_code"], member["security_id"]
        kind = member["security_type"]
        if (
            not isinstance(identity, str)
            or not identity.strip()
            or kind not in {"ordinary_a", "b_share", "cdr"}
        ):
            raise ValueError("breadth_member_identity_invalid")
        if _ordinary_share(code) != (kind == "ordinary_a"):
            raise ValueError("breadth_member_identity_invalid")
        start = date.fromisoformat(member["valid_from"])
        end = (
            date.max if member["valid_until"] is None else date.fromisoformat(member["valid_until"])
        )
        first = date.fromisoformat(member["first_trading_day"])
        if start >= end or first > start or not member["evidence"]:
            raise ValueError("breadth_member_interval_invalid")
        for key in (("code", code), ("identity", identity)):
            intervals.setdefault(key, []).append((start, end))
    for group in intervals.values():
        ordered = sorted(group)
        if any(
            start < previous_end
            for (_, previous_end), (start, _) in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("breadth_member_interval_overlap")
    return document


def daily_breadth_day(
    day: date,
    universe: dict[str, Any],
    quotes: tuple[dict[str, object], ...],
    suspensions: tuple[dict[str, object], ...],
) -> DailyBreadthResult:
    """Version 2 daily counts use exact source prices and a reviewed effective pool."""
    if (
        not date.fromisoformat(universe["coverage_start"])
        <= day
        <= date.fromisoformat(universe["coverage_end"])
    ):
        raise ValueError("breadth_universe_coverage_missing")
    rows = _unique_rows(quotes, day)
    full_day, resumed, suspension_events = set(), set(), set()
    for row in suspensions:
        code, kind = _row_code(row, day), row["suspend_type"]
        timing = _suspension_timing(row["suspend_timing"])
        if kind not in {"S", "R"}:
            raise ValueError("breadth_suspension_invalid")
        event = (code, kind, timing)
        if event in suspension_events:
            raise ValueError("breadth_suspension_duplicate")
        suspension_events.add(event)
        if kind == "S" and not timing:
            full_day.add(code)
        if kind == "R":
            resumed.add(code)
    resolutions = {}
    for event in universe["events"]:
        if event["kind"] == "full_day_suspension" and event["business_date"] == day.isoformat():
            if event["ts_code"] in resolutions or not event["evidence"]:
                raise ValueError("breadth_suspension_evidence_invalid")
            resolutions[event["ts_code"]] = event["evidence"]
    if (full_day & resumed) - resolutions.keys():
        raise ValueError("breadth_suspension_conflict")
    active = {
        m["ts_code"]
        for m in universe["members"]
        if date.fromisoformat(m["valid_from"]) <= day
        and (m["valid_until"] is None or day < date.fromisoformat(m["valid_until"]))
    }
    ordinary = {code for code in active if _ordinary_share(code)}
    if {code for code in rows if _ordinary_share(code)} != ordinary - full_day:
        raise ValueError("breadth_quote_membership_mismatch")
    members = []
    quote_publication_proofs = universe["publications"].get(day.isoformat(), [])
    required_proofs = set(universe["coverage_evidence"]) | set(quote_publication_proofs)
    for member in universe["members"]:
        if date.fromisoformat(member["valid_from"]) > day:
            continue
        # An exit changes the denominator too. Its effective interval cannot
        # become PUBLIC before the evidence proving that interval is available.
        required_proofs.update(member["evidence"])
        if member["valid_until"] is not None and day >= date.fromisoformat(member["valid_until"]):
            continue
        code = member["ts_code"]
        state = "outside_ordinary_a"
        event_evidence: list[str] = []
        if member["security_type"] == "ordinary_a":
            if not _ordinary_share(code):
                raise ValueError("breadth_member_identity_invalid")
            if code in full_day:
                state = "full_day_suspension"
                event_evidence = resolutions.get(code, [])
                required_proofs.update(event_evidence)
            else:
                references = [
                    event
                    for event in universe["events"]
                    if event["kind"] == "first_day_reference"
                    and event["business_date"] == day.isoformat()
                    and event["ts_code"] == code
                ]
                row = rows[code]
                if member["first_trading_day"] == day.isoformat() and not references:
                    state = "first_day_reference_unproven"
                elif row["vol"] is None or _breadth_price(row["vol"], allow_zero=True) == 0:
                    state = "no_legal_trade"
                elif row["pre_close"] is None:
                    state = "reference_price_missing"
                elif row["close"] is None:
                    state = "close_price_missing"
                else:
                    close, previous = _breadth_price(row["close"]), _breadth_price(row["pre_close"])
                    if references:
                        if (
                            len(references) != 1
                            or references[0]["reference_semantics"] != "official_same_day_pre_close"
                            or _breadth_price(references[0]["reference_price"]) != previous
                        ):
                            raise ValueError("breadth_first_reference_mismatch")
                        event_evidence = references[0]["evidence"]
                        required_proofs.update(event_evidence)
                    state = (
                        "advance" if close > previous else "decline" if close < previous else "flat"
                    )
        members.append({**member, "state": state, "event_evidence": event_evidence})
    advances = sum(m["state"] == "advance" for m in members)
    declines = sum(m["state"] == "decline" for m in members)
    flats = sum(m["state"] == "flat" for m in members)
    proofs = {p["artifact_hash"]: p for p in universe["evidence"]}
    for digest in quote_publication_proofs:
        proof = proofs[digest]
        dated = proof.get("published_date")
        if dated is not None and date.fromisoformat(dated) < day:
            raise ValueError("breadth_quote_publication_precedes_period")
        for field in ("release_at", "public_available_at"):
            published = _breadth_time(proof[field])
            if (
                published is not None
                and published.astimezone(ZoneInfo("Asia/Shanghai")).date() < day
            ):
                raise ValueError("breadth_quote_publication_precedes_period")
    times = {}
    for field in ("release_at", "public_available_at"):
        values = [_breadth_time(proofs[digest][field]) for digest in required_proofs]
        times[field] = (
            max(v for v in values if v is not None).isoformat()
            if quote_publication_proofs and values and all(v is not None for v in values)
            else None
        )
    return {
        "business_date": day.isoformat(),
        "members": members,
        "advances": advances,
        "declines": declines,
        "flats": flats,
        "participants": advances + declines + flats,
        "net": advances - declines,
        "advance_decline_ratio": advances / max(declines, 1)
        if advances + declines + flats
        else None,
        "status": "available" if advances + declines + flats else "unavailable:no_participants",
        "zero_declines": declines == 0,
        "release_at": times["release_at"],
        "public_available_at": times["public_available_at"],
    }


def _breadth_price(value: object, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("breadth_price_invalid")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("breadth_price_invalid") from error
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise ValueError("breadth_price_invalid")
    return number


def parse_daily_breadth_acquisitions(
    inputs: tuple[tuple[AcquisitionReceipt, bytes], ...],
    artifacts: Path,
    *,
    period: str | None = None,
) -> list[DailyBreadthResult]:
    """Rebuild one day's adopted inputs, or a complete acquisition batch, from originals."""
    from pring_cycle.tushare_context import _response_rows

    universe = None
    calendar_days = None
    deliveries: dict[str, dict[date, tuple[dict[str, object], ...]]] = {
        "daily": {},
        "suspend_d": {},
    }
    fields = {
        "daily": ("ts_code", "trade_date", "close", "pre_close", "vol"),
        "suspend_d": ("ts_code", "trade_date", "suspend_type", "suspend_timing"),
        "trade_cal": ("cal_date", "is_open"),
    }
    for receipt, raw in inputs:
        api = receipt.api_name
        if api == "breadth_universe":
            if (
                universe is not None
                or receipt.provider != "reviewed_evidence"
                or receipt.fields
                or receipt.parser_version != "market-breadth-universe-v0001"
                or receipt.parameters != {"universe_hash": hashlib.sha256(raw).hexdigest()}
            ):
                raise ValueError("breadth_universe_receipt_invalid")
            universe = load_breadth_universe(raw, artifacts)
            continue
        if (
            api not in fields
            or receipt.provider != "tushare"
            or receipt.fields != ",".join(fields[api])
            or receipt.parser_version != "tushare-context-parser-v0002"
        ):
            raise ValueError("breadth_source_receipt_invalid")
        document = json.loads(raw, parse_float=Decimal)
        if document.get("code") != 0:
            raise ValueError("breadth_response_invalid")
        rows = _response_rows(document, required_fields=fields[api])
        if api == "trade_cal":
            params = receipt.parameters
            if (
                calendar_days is not None
                or set(params) != {"exchange", "start_date", "end_date", "is_open"}
                or params["exchange"] != "SSE"
                or params["is_open"] != "1"
            ):
                raise ValueError("breadth_calendar_invalid")
            calendar_days = [_date(row["cal_date"]) for row in rows if str(row["is_open"]) == "1"]
            if (
                not calendar_days
                or len(set(calendar_days)) != len(calendar_days)
                or any(
                    not _date(params["start_date"]) <= day <= _date(params["end_date"])
                    for day in calendar_days
                )
            ):
                raise ValueError("breadth_calendar_invalid")
        else:
            if set(receipt.parameters) != {"trade_date"}:
                raise ValueError("breadth_daily_parameters_invalid")
            day = _date(receipt.parameters["trade_date"])
            if day in deliveries[api] or len(rows) >= 6000:
                raise ValueError("breadth_daily_delivery_incomplete")
            deliveries[api][day] = rows
    if universe is None or calendar_days is None:
        raise ValueError("breadth_inputs_missing")
    days = set(calendar_days) if period is None else {date.fromisoformat(period)}
    if (
        not days <= set(calendar_days)
        or set(deliveries["daily"]) != days
        or set(deliveries["suspend_d"]) != days
    ):
        raise ValueError("breadth_daily_delivery_incomplete")
    return [
        daily_breadth_day(day, universe, deliveries["daily"][day], deliveries["suspend_d"][day])
        for day in sorted(days)
    ]


def daily_breadth_scalars(days: list[DailyBreadthResult]) -> tuple[ContextScalar, ...]:
    """Convert available daily results to the six versioned source scalars."""
    from pring_cycle.tushare_context import ContextScalar

    scalars = []
    for day in days:
        if not day["participants"]:
            continue
        values = (
            ("CN_EQ_ADV_DEC", "advances", day["advances"], "count"),
            ("CN_EQ_ADV_DEC", "declines", day["declines"], "count"),
            ("CN_EQ_ADV_DEC", "flats", day["flats"], "count"),
            ("CN_EQ_ADV_DEC", "net", day["net"], "count"),
            ("CN_EQ_ADV_DEC", "participants", day["participants"], "count"),
            ("CN_EQ_AD_RATIO", "advance_decline_ratio", day["advance_decline_ratio"], "ratio"),
        )
        for metric, measure, value, unit in values:
            if value is None:
                raise ValueError("breadth_available_value_missing")
            scalars.append(
                ContextScalar(
                    metric_id=metric,
                    api_name="daily_breadth",
                    source_field=measure,
                    period_kind="business_day",
                    period_start=day["business_date"],
                    period_end=day["business_date"],
                    dimensions={"measure": measure, "universe": "point_in_time_traded_a_shares"},
                    value=float(value),
                    unit=unit,
                    release_at=_breadth_time(day["release_at"]),
                    public_available_at=_breadth_time(day["public_available_at"]),
                )
            )
    return tuple(scalars)


def daily_breadth_scalar_documents(days: list[DailyBreadthResult]) -> list[dict[str, Any]]:
    """Canonical scalar JSON fields for provenance checks."""
    return [
        {
            **asdict(scalar),
            "acquisition_ids": [],
            "release_at": scalar.release_at.isoformat() if scalar.release_at else None,
            "public_available_at": scalar.public_available_at.isoformat()
            if scalar.public_available_at
            else None,
        }
        for scalar in daily_breadth_scalars(days)
    ]


def breadth_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points: tuple[MetricSeriesPoint, ...],
    *,
    definition_version: str,
    artifacts: Path,
) -> set[str]:
    """Recheck the complete adopted pool/quotes/events, including referenced review originals."""
    selected = {p.selected_claim_id: p for p in points if p.selected_claim_id is not None}
    cached: dict[tuple[frozenset[str], str], list[dict[str, Any]] | None] = {}
    valid = set()
    for claim_id, inputs in repository.source_claim_acquisitions_many(tuple(selected)).items():
        if not inputs:
            continue
        point = selected[claim_id]
        identities = frozenset(i.receipt.acquisition_id for i in inputs)
        key = identities, point.period_end
        try:
            if key not in cached:
                cached[key] = None
                days = parse_daily_breadth_acquisitions(
                    tuple((i.receipt, i.raw) for i in inputs), artifacts, period=point.period_end
                )
                expected = daily_breadth_scalar_documents(days)
                for item in inputs:
                    document = json.loads(item.normalized)
                    if [
                        d
                        for d in document["daily_breadth"]
                        if d["business_date"] == point.period_end
                    ] != days:
                        raise ValueError("breadth_normalized_day_mismatch")
                    economic = []
                    for entry in document["accepted_scalars"]:
                        if entry["period_end"] != point.period_end:
                            continue
                        if set(entry["acquisition_ids"]) != identities or entry[
                            "definition_version"
                        ] not in (None, definition_version):
                            raise ValueError("breadth_normalized_identity_mismatch")
                        times = {
                            field: _breadth_time(entry[field])
                            for field in ("release_at", "public_available_at")
                        }
                        economic.append(
                            {
                                **entry,
                                "definition_version": None,
                                "acquisition_ids": [],
                                **{
                                    field: value.isoformat() if value is not None else None
                                    for field, value in times.items()
                                },
                            }
                        )
                    if sorted(_breadth_json(d) for d in economic) != sorted(
                        _breadth_json(d) for d in expected
                    ):
                        raise ValueError("breadth_normalized_value_mismatch")
                cached[key] = expected
            validated = cached[key]
            if validated is None:
                continue
            claim = next(c for c in point.claims if c.claim_id == claim_id)
            matches = [
                d
                for d in validated
                if d["dimensions"] == point.dimensions
                and d["period_start"] == point.period_start
                and d["value"] == claim.value
                and d["unit"] == claim.unit
                and claim.source_reference
                == f"tushare:daily_breadth:{d['source_field']}:{point.period_end}"
                and claim.provider == "tushare"
                and all(
                    _breadth_time(d[field]) == getattr(claim, field)
                    for field in ("release_at", "public_available_at")
                )
            ]
            if len(matches) == 1:
                valid.add(claim_id)
        except (LookupError, TypeError, ValueError, OSError):
            continue
    return valid


def validate_daily_breadth_scalars(
    scalars: tuple[ContextScalar, ...], days: list[DailyBreadthResult], *, definition_version: str
) -> None:
    """A caller cannot alter the complete output batch or its proven publication times."""
    economic = []
    for scalar in scalars:
        if scalar.definition_version not in (None, definition_version):
            raise ValueError("breadth_scalar_definition_mismatch")
        economic.append(
            {
                **asdict(scalar),
                "definition_version": None,
                "acquisition_ids": [],
                "release_at": scalar.release_at.isoformat()
                if scalar.release_at is not None
                else None,
                "public_available_at": scalar.public_available_at.isoformat()
                if scalar.public_available_at is not None
                else None,
            }
        )
    if sorted(_breadth_json(d) for d in economic) != sorted(
        _breadth_json(d) for d in daily_breadth_scalar_documents(days)
    ):
        raise ValueError("breadth_scalar_values_mismatch")
