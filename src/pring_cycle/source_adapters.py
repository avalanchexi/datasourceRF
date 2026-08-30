from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from urllib.request import Request, build_opener

from pring_cycle.adapters import MarketBar, validate_core_market_bars

TUSHARE_ENDPOINT = "https://api.tushare.pro"

CORE_API_IDENTITIES = {
    "CN_EQUITY_CORE_000985": ("index_daily", "000985.CSI"),
    "CN_BOND_CORE_000012": ("index_daily", "000012.SH"),
    "CN_COMMODITY_CORE_NHII": ("fut_index_daily", "NHII.NH"),
}


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


Transport = Callable[[dict[str, Any]], dict[str, Any]]


class TushareCoreAdapter:
    def __init__(self, token: str, *, transport: Transport | None = None) -> None:
        if not token:
            raise ValueError("tushare_token_required")
        self._token = token
        self._transport = transport or self._post

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        response = self._call(
            "trade_cal",
            {"exchange": "SSE", "start_date": _compact(start), "end_date": _compact(end)},
            "cal_date,is_open",
        )
        rows = _rows(response)
        days = sorted(
            date.fromisoformat(str(row["cal_date"]))
            for row in rows
            if int(row["is_open"]) == 1
        )
        if not days:
            raise ValueError("china_trading_calendar_missing")
        return tuple(days)

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
        return_divisor = 1.0 if api_name == "fut_index_daily" else 100.0
        bars = tuple(
            sorted(
                (
                    MarketBar(
                        metric_id=metric_id,
                        source_code=str(row["ts_code"]),
                        business_date=_trade_date(row["trade_date"]),
                        close=float(row["close"]),
                        pre_close=float(row["pre_close"]),
                        official_return=float(row["pct_chg"]) / return_divisor,
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
            {
                "api_name": api_name,
                "fields": fields,
                "params": params,
                "token": self._token,
            }
        )
        if int(response.get("code", -1)) != 0:
            raise ValueError("tushare_source_failed")
        return response

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            TUSHARE_ENDPOINT,
            data=_canonical_json(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with build_opener().open(request, timeout=30) as response:
            document = json.load(response)
        if not isinstance(document, dict):
            raise ValueError("tushare_response_invalid")
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
