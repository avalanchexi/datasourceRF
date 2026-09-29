from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any
from urllib.request import Request, build_opener

from pring_cycle.acquisition import Acquired, AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.adapters import MarketBar, validate_core_market_bars
from pring_cycle.evidence import EvidenceRepository, MetricSeriesPoint

TUSHARE_ENDPOINT = "https://api.tushare.pro"
# The parser the core adapter records its receipts under; the SSE calendar is read by it.
CORE_PARSER_VERSION = "tushare-core-parser-v0002"

CORE_API_IDENTITIES = {
    "CN_EQUITY_CORE_000985": ("index_daily", "000985.CSI"),
    "CN_BOND_CORE_000012": ("index_daily", "000012.SH"),
    "CN_COMMODITY_CORE_NHII": ("fut_index_daily", "NHII.NH"),
}


def parse_core_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
    *,
    metric_id: str,
) -> tuple[MarketBar, ...]:
    """Rebuild the exact core bars described by a validated physical receipt."""
    if receipt.provider == "csindex":
        from pring_cycle.official_core import parse_csindex_acquisition

        return parse_csindex_acquisition(receipt, raw, metric_id=metric_id)
    api, code = CORE_API_IDENTITIES[metric_id]
    fields = "ts_code,trade_date,close,pre_close,pct_chg"
    if (
        receipt.state != "validated"
        or receipt.provider != "tushare"
        or receipt.api_name != api
        or receipt.parser_version != CORE_PARSER_VERSION
        or receipt.fields != fields
        or set(receipt.parameters) != {"ts_code", "start_date", "end_date"}
        or receipt.parameters.get("ts_code") != code
    ):
        raise ValueError("core_acquisition_identity_mismatch")
    start = date.fromisoformat(receipt.parameters["start_date"])
    end = date.fromisoformat(receipt.parameters["end_date"])
    if (
        start > end
        or receipt.parameters["start_date"] != _compact(start)
        or receipt.parameters["end_date"] != _compact(end)
    ):
        raise ValueError("core_acquisition_period_mismatch")
    document = _response_document(raw)
    data = document.get("data")
    if not isinstance(data, dict) or data.get("fields") != fields.split(","):
        raise ValueError("core_acquisition_fields_mismatch")
    bars = _core_bars_response(document, metric_id, None)
    if any(not start <= bar.business_date <= end for bar in bars):
        raise ValueError("core_acquisition_period_mismatch")
    normalized = json.dumps(
        [asdict(bar) for bar in bars],
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    if hashlib.sha256(normalized).hexdigest() != receipt.normalized_hash:
        raise ValueError("core_acquisition_normalized_mismatch")
    return bars


def selected_core_claim_is_valid(metric_id: str, point: MetricSeriesPoint) -> bool:
    selected = next(
        (claim for claim in point.claims if claim.claim_id == point.selected_claim_id), None
    )
    if selected is None:
        return False
    from pring_cycle.official_core import CSINDEX_CORES, csindex_source_reference

    api_name, source_code = CORE_API_IDENTITIES[metric_id]
    # TuShare, or the CSI official page for the two CSI cores (ticket 22).
    identities = {("tushare", f"tushare:{api_name}:{source_code}:{point.period_end}")}
    if metric_id in CSINDEX_CORES:
        identities.add(
            ("csindex", csindex_source_reference(metric_id, date.fromisoformat(point.period_end)))
        )
    return (
        (selected.provider, selected.source_reference) in identities
        and selected.unit == "index_points"
        and selected.quality_status == "validated"
    )


class CoreInputValidator:
    """Verify selected core originals within one consumer evaluation."""

    def __init__(self, evidence: EvidenceRepository, claim_ids: tuple[str, ...]) -> None:
        self._originals = evidence.source_claim_originals_many(claim_ids)
        self._prices: dict[tuple[str, str], dict[str, float]] = {}
        self._valid: dict[tuple[str, str], bool] = {}

    def is_valid(self, metric_id: str, point: MetricSeriesPoint) -> bool:
        if not selected_core_claim_is_valid(metric_id, point):
            return False
        claim_id = point.selected_claim_id
        if claim_id is None:
            return False
        key = (metric_id, claim_id)
        if key not in self._valid:
            originals = self._originals.get(claim_id, ())
            valid = bool(originals)
            for receipt, raw in originals:
                source = (metric_id, receipt.acquisition_id)
                if source not in self._prices:
                    try:
                        bars = parse_core_acquisition(receipt, raw, metric_id=metric_id)
                        self._prices[source] = {
                            bar.business_date.isoformat(): bar.close for bar in bars
                        }
                    except (ValueError, TypeError, KeyError):
                        self._prices[source] = {}
                prices = self._prices[source]
                if (
                    point.period_end not in prices
                    or prices[point.period_end] != point.selected_value
                ):
                    valid = False
                    break
            self._valid[key] = valid
        return self._valid[key]


@dataclass(frozen=True)
class CoreSourceSmokeResult:
    metric_id: str
    api_name: str
    source_code: str
    first_business_date: str
    last_business_date: str
    observations: int
    normalized_hash: str
    status: str


Transport = Callable[[dict[str, Any]], dict[str, Any] | bytes]


class TushareCoreAdapter:
    def __init__(
        self,
        token: str,
        *,
        transport: Transport | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not token:
            raise ValueError("tushare_token_required")
        self._token = token
        self._transport = transport or self._post
        self._clock = clock

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        response = self._call(
            "trade_cal",
            {"exchange": "SSE", "start_date": _compact(start), "end_date": _compact(end)},
            "cal_date,is_open",
        )
        return _calendar_rows(response, start, end)

    def acquire_calendar(
        self, repository: AcquisitionRepository, start: date, end: date
    ) -> Acquired[tuple[date, ...]]:
        return self._acquire(
            repository,
            "trade_cal",
            {"exchange": "SSE", "start_date": _compact(start), "end_date": _compact(end)},
            "cal_date,is_open",
            lambda response: _calendar_rows(response, start, end),
            lambda days: [day.isoformat() for day in days],
        )

    def acquire_core_bars(
        self,
        repository: AcquisitionRepository,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...],
    ) -> Acquired[tuple[MarketBar, ...]]:
        api_name, source_code = CORE_API_IDENTITIES[metric_id]
        return self._acquire(
            repository,
            api_name,
            {"ts_code": source_code, "start_date": _compact(start), "end_date": _compact(end)},
            "ts_code,trade_date,close,pre_close,pct_chg",
            lambda response: _core_bars_response(response, metric_id, expected_business_dates),
            lambda bars: [asdict(bar) for bar in bars],
        )

    def _acquire[T](
        self,
        repository: AcquisitionRepository,
        api_name: str,
        parameters: dict[str, str],
        fields: str,
        parse: Callable[[dict[str, Any]], T],
        normalize: Callable[[T], object],
    ) -> Acquired[T]:
        def fetch() -> bytes:
            response = self._transport(
                {
                    "api_name": api_name,
                    "params": parameters,
                    "fields": fields,
                    "token": self._token,
                }
            )
            if not isinstance(response, bytes):
                raise ValueError("acquisition_raw_response_bytes_required")
            return response

        return repository.capture(
            provider="tushare",
            api_name=api_name,
            parameters=parameters,
            fields=fields,
            parser_version=CORE_PARSER_VERSION,
            fetch=fetch,
            parse=lambda raw: parse(_response_document(raw)),
            normalize=normalize,
            clock=self._clock,
        )

    def core_bars(
        self,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...] | None = None,
    ) -> tuple[MarketBar, ...]:
        try:
            api_name, source_code = CORE_API_IDENTITIES[metric_id]
        except KeyError as error:
            raise ValueError("unknown_core_metric") from error
        response = self._call(
            api_name,
            {"ts_code": source_code, "start_date": _compact(start), "end_date": _compact(end)},
            "ts_code,trade_date,close,pre_close,pct_chg",
        )
        return _core_bars_response(response, metric_id, expected_business_dates)

    def smoke(
        self,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...] | None = None,
    ) -> CoreSourceSmokeResult:
        bars = self.core_bars(
            metric_id,
            start=start,
            end=end,
            expected_business_dates=expected_business_dates,
        )
        api_name, source_code = CORE_API_IDENTITIES[metric_id]
        normalized = [asdict(item) for item in bars]
        return CoreSourceSmokeResult(
            metric_id=metric_id,
            api_name=api_name,
            source_code=source_code,
            first_business_date=bars[0].business_date.isoformat(),
            last_business_date=bars[-1].business_date.isoformat(),
            observations=len(bars),
            normalized_hash=hashlib.sha256(_canonical_json(normalized).encode()).hexdigest(),
            status="validated",
        )

    def _call(self, api_name: str, params: dict[str, str], fields: str) -> dict[str, Any]:
        response = self._transport(
            {"api_name": api_name, "fields": fields, "params": params, "token": self._token}
        )
        return _response_document(response)

    def _post(self, payload: dict[str, Any]) -> bytes:
        request = Request(
            TUSHARE_ENDPOINT,
            data=_canonical_json(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with build_opener().open(request, timeout=30) as response:
            return bytes(response.read())


def _calendar_rows(response: dict[str, Any], start: date, end: date) -> tuple[date, ...]:
    rows = _rows(response)
    dates = [date.fromisoformat(str(row["cal_date"])) for row in rows]
    if len(dates) != len(set(dates)) or any(day < start or day > end for day in dates):
        raise ValueError("china_trading_calendar_invalid")
    days = sorted(
        date.fromisoformat(str(row["cal_date"])) for row in rows if int(row["is_open"]) == 1
    )
    if any(day.weekday() >= 5 for day in days):
        raise ValueError("china_trading_calendar_invalid")
    if not days:
        raise ValueError("china_trading_calendar_missing")
    return tuple(days)


def _core_bars_response(
    response: dict[str, Any],
    metric_id: str,
    expected_business_dates: tuple[date, ...] | None,
) -> tuple[MarketBar, ...]:
    api_name, _source_code = CORE_API_IDENTITIES[metric_id]
    return_divisor = 1.0 if api_name == "fut_index_daily" else 100.0
    bars = tuple(
        sorted(
            (
                MarketBar(
                    metric_id=metric_id,
                    source_code=str(row["ts_code"]),
                    business_date=_trade_date(row["trade_date"]),
                    close=_core_number(row["close"]),
                    pre_close=_core_number(row["pre_close"]),
                    official_return=_core_number(row["pct_chg"]) / return_divisor,
                    unit="index_points",
                    certification_status="certified",
                )
                for row in _rows(response)
            ),
            key=lambda item: item.business_date,
        )
    )
    validate_core_market_bars(
        metric_id,
        list(bars),
        expected_business_dates=expected_business_dates,
    )
    return bars


def _core_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("core_number_invalid")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("core_number_invalid") from error
    if not isfinite(number):
        raise ValueError("core_number_invalid")
    return number


def _response_document(response: bytes | dict[str, Any]) -> dict[str, Any]:
    document = json.loads(response) if isinstance(response, bytes) else response
    if not isinstance(document, dict):
        raise ValueError("tushare_response_invalid")
    if int(document.get("code", -1)) != 0:
        raise ValueError("tushare_source_failed")
    return {str(key): value for key, value in document.items()}


def _rows(response: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    data = response.get("data")
    if not isinstance(data, dict):
        raise ValueError("tushare_response_data_missing")
    fields = data.get("fields")
    items = data.get("items")
    if not isinstance(fields, list) or not isinstance(items, list):
        raise ValueError("tushare_response_schema_invalid")
    names = [str(item) for item in fields]
    rows = []
    for item in items:
        if not isinstance(item, list) or len(item) != len(names):
            raise ValueError("tushare_response_row_invalid")
        rows.append(dict(zip(names, item, strict=True)))
    return tuple(rows)


def _trade_date(value: object) -> date:
    compact = str(value)
    if len(compact) != 8 or not compact.isdigit():
        raise ValueError("tushare_trade_date_invalid")
    return date(int(compact[:4]), int(compact[4:6]), int(compact[6:]))


def _compact(value: date) -> str:
    return value.strftime("%Y%m%d")


def _canonical_json(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
