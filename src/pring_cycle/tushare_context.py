from __future__ import annotations

import calendar
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from math import isfinite
from typing import Any
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TUSHARE_ENDPOINT

Transport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ContextScalar:
    metric_id: str
    api_name: str
    source_field: str
    period_kind: str
    period_start: str
    period_end: str
    dimensions: dict[str, str]
    value: float
    unit: str
    release_at: datetime | None = None
    public_available_at: datetime | None = None


@dataclass(frozen=True)
class ContextIngestionResult:
    observation_count: int
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Field:
    metric_id: str
    source_field: str
    dimensions: dict[str, str]
    unit: str


class TushareContextAdapter:
    def __init__(self, token: str, *, transport: Transport | None = None) -> None:
        if not token:
            raise ValueError("tushare_token_required")
        self._token = token
        self._transport = transport or self._post

    def pmi(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
        fields = (
            _Field(
                "CN_PMI_ACTIVITY",
                "pmi010000",
                {"series": "manufacturing", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_ACTIVITY",
                "pmi010400",
                {"series": "production", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_ACTIVITY",
                "pmi010500",
                {"series": "new_orders", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_INVENTORY",
                "pmi010700",
                {"series": "raw_materials", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_ACTIVITY",
                "pmi011100",
                {"series": "purchase_volume", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_PRICES",
                "pmi011200",
                {"series": "purchase_prices", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_PRICES",
                "pmi011300",
                {"series": "output_prices", "measure": "level"},
                "diffusion_index_points",
            ),
            _Field(
                "CN_PMI_INVENTORY",
                "pmi011400",
                {"series": "finished_goods", "measure": "level"},
                "diffusion_index_points",
            ),
        )
        rows = self._call(
            "cn_pmi",
            {"start_m": _month_value(start_month), "end_m": _month_value(end_month)},
            ("month", *(item.source_field for item in fields)),
        )
        return _monthly_scalars("cn_pmi", rows, fields)

    def prices(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
        parameters = {
            "start_m": _month_value(start_month),
            "end_m": _month_value(end_month),
        }
        cpi_fields = tuple(
            _Field(
                "CN_CPI_HEADLINE", field, {"measure": measure, "category": "headline"}, "percent"
            )
            for field, measure in (
                ("nt_yoy", "yoy"),
                ("nt_mom", "mom"),
                ("nt_accu", "cumulative_average_yoy"),
            )
        )
        ppi_fields = tuple(
            _Field(
                "CN_PPI",
                f"ppi{suffix}_{measure_field}",
                {"measure": measure, "category": category},
                "percent",
            )
            for suffix, category in (
                ("", "headline"),
                ("_mp", "means_of_production"),
                ("_cg", "consumer_goods"),
            )
            for measure_field, measure in (
                ("yoy", "yoy"),
                ("mom", "mom"),
                ("accu", "cumulative_average_yoy"),
            )
        )
        cpi = self._call(
            "cn_cpi",
            parameters,
            ("month", *(item.source_field for item in cpi_fields)),
        )
        ppi = self._call(
            "cn_ppi",
            parameters,
            ("month", *(item.source_field for item in ppi_fields)),
        )
        return (
            *_monthly_scalars("cn_cpi", cpi, cpi_fields),
            *_monthly_scalars("cn_ppi", ppi, ppi_fields),
        )

    def money(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
        fields = tuple(
            _Field(
                "CN_M1_M2",
                aggregate if measure == "balance" else f"{aggregate}_{measure}",
                {"aggregate": aggregate, "measure": measure},
                "hundred_million_cny" if measure == "balance" else "percent",
            )
            for aggregate in ("m1", "m2")
            for measure in ("balance", "yoy", "mom")
        )
        rows = self._call(
            "cn_m",
            {"start_m": _month_value(start_month), "end_m": _month_value(end_month)},
            ("month", *(item.source_field for item in fields)),
        )
        return _monthly_scalars("cn_m", rows, fields)

    def transmission(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        parameters = {
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date": end_date.strftime("%Y%m%d"),
        }
        repo_rows = self._call(
            "repo_daily",
            {**parameters, "ts_code": "DR007.IB"},
            ("ts_code", "trade_date", "repo_maturity", "weight"),
        )
        shibor_rows = self._call(
            "shibor",
            parameters,
            ("date", "on", "1w", "3m"),
        )
        scalars = [
            _daily_scalar(
                "CN_DR007",
                "repo_daily",
                "weight",
                row,
                date_field="trade_date",
                dimensions={},
                unit="percent",
            )
            for row in repo_rows
            if str(row.get("ts_code")) == "DR007.IB" and str(row.get("repo_maturity")) == "DR007"
        ]
        for row in shibor_rows:
            for source_field, tenor in (("on", "overnight"), ("1w", "1w"), ("3m", "3m")):
                scalars.append(
                    _daily_scalar(
                        "CN_SHIBOR_ON_1W_3M",
                        "shibor",
                        source_field,
                        row,
                        date_field="date",
                        dimensions={"tenor": tenor},
                        unit="percent",
                        release_time=time(11),
                    )
                )
        return tuple(scalars)

    def _call(
        self,
        api_name: str,
        params: dict[str, str],
        fields: tuple[str, ...],
    ) -> tuple[dict[str, object], ...]:
        response = self._transport(
            {
                "api_name": api_name,
                "fields": ",".join(fields),
                "params": params,
                "token": self._token,
            }
        )
        if int(response.get("code", -1)) != 0:
            raise ValueError("tushare_source_failed")
        return _response_rows(response, required_fields=fields)

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


def ingest_context_scalars(
    paths: RuntimePaths,
    scalars: tuple[ContextScalar, ...],
    *,
    fetched_at: datetime,
) -> ContextIngestionResult:
    if fetched_at.tzinfo is None:
        raise ValueError("tushare_context_fetched_at_must_be_timezone_aware")
    if not scalars:
        raise ValueError("tushare_context_observations_missing")
    claims = tuple(
        SourceClaimInput(
            metric_id=scalar.metric_id,
            definition_version=metric_definition(scalar.metric_id).definition_version,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            value=scalar.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=scalar.unit,
            provider="tushare",
            source_reference=(
                f"tushare:{scalar.api_name}:{scalar.source_field}:{scalar.period_end}"
            ),
            release_event_id=f"tushare:{scalar.api_name}:{scalar.period_end}",
            release_at=scalar.release_at,
            public_available_at=scalar.public_available_at,
            fetched_at=fetched_at,
            available_at=fetched_at,
            certification_status=metric_definition(scalar.metric_id).certification_status,
            quality_status="validated",
        )
        for scalar in scalars
    )
    repository = EvidenceRepository(paths.database)
    stored = repository.append_source_claims(claims)
    metric_ids = tuple(sorted({scalar.metric_id for scalar in scalars}))
    for metric_id in metric_ids:
        metric_scalars = [item for item in scalars if item.metric_id == metric_id]
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare",
            outcome="verified_candidate",
            fetched_at=fetched_at,
            safe_metadata={
                "api_names": ",".join(sorted({item.api_name for item in metric_scalars})),
                "observations": str(len(metric_scalars)),
                "period_end": max(item.period_end for item in metric_scalars),
            },
        )
    return ContextIngestionResult(
        observation_count=len(stored),
        observation_ids=tuple(item.observation_id for item in stored),
        claim_ids=tuple(item.claim_id for item in stored),
        metric_ids=metric_ids,
    )


def _monthly_scalars(
    api_name: str,
    rows: tuple[dict[str, object], ...],
    fields: tuple[_Field, ...],
) -> tuple[ContextScalar, ...]:
    scalars = []
    for row in rows:
        period_start, period_end = _month_bounds(str(row.get("month")))
        for field in fields:
            value = _number(row.get(field.source_field))
            if value is None:
                continue
            scalars.append(
                ContextScalar(
                    metric_id=field.metric_id,
                    api_name=api_name,
                    source_field=field.source_field,
                    period_kind="month",
                    period_start=period_start,
                    period_end=period_end,
                    dimensions=field.dimensions,
                    value=value,
                    unit=field.unit,
                )
            )
    return tuple(scalars)


def _daily_scalar(
    metric_id: str,
    api_name: str,
    source_field: str,
    row: dict[str, object],
    *,
    date_field: str,
    dimensions: dict[str, str],
    unit: str,
    release_time: time | None = None,
) -> ContextScalar:
    business_date = _compact_date(row.get(date_field))
    value = _number(row.get(source_field))
    if value is None:
        raise ValueError("tushare_context_value_missing")
    released_at = (
        datetime.combine(
            business_date,
            release_time,
            ZoneInfo("Asia/Shanghai"),
        )
        if release_time is not None
        else None
    )
    return ContextScalar(
        metric_id=metric_id,
        api_name=api_name,
        source_field=source_field,
        period_kind="business_day",
        period_start=business_date.isoformat(),
        period_end=business_date.isoformat(),
        dimensions=dimensions,
        value=value,
        unit=unit,
        release_at=released_at,
        public_available_at=released_at,
    )


def _response_rows(
    response: dict[str, Any],
    *,
    required_fields: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    data = response.get("data")
    if not isinstance(data, dict):
        raise ValueError("tushare_response_data_missing")
    fields = data.get("fields")
    items = data.get("items")
    if not isinstance(fields, list) or not isinstance(items, list):
        raise ValueError("tushare_response_schema_invalid")
    names = [str(item) for item in fields]
    if any(name not in names for name in required_fields):
        raise ValueError("tushare_response_required_field_missing")
    rows = []
    for item in items:
        if not isinstance(item, list) or len(item) != len(names):
            raise ValueError("tushare_response_row_invalid")
        rows.append(dict(zip(names, item, strict=True)))
    return tuple(rows)


def _month_value(value: str) -> str:
    normalized = value.replace("-", "")
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("tushare_month_invalid")
    _month_bounds(normalized)
    return normalized


def _month_bounds(value: str) -> tuple[str, str]:
    normalized = _month_value_without_recursion(value)
    year, month = int(normalized[:4]), int(normalized[4:])
    try:
        final_day = calendar.monthrange(year, month)[1]
    except calendar.IllegalMonthError as error:
        raise ValueError("tushare_month_invalid") from error
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{final_day:02d}"


def _month_value_without_recursion(value: str) -> str:
    normalized = value.replace("-", "")
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("tushare_month_invalid")
    return normalized


def _compact_date(value: object) -> date:
    compact = str(value)
    if len(compact) != 8 or not compact.isdigit():
        raise ValueError("tushare_date_invalid")
    try:
        return date(int(compact[:4]), int(compact[4:6]), int(compact[6:]))
    except ValueError as error:
        raise ValueError("tushare_date_invalid") from error


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("tushare_context_value_invalid")
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError("tushare_context_value_invalid") from error
    if not isfinite(parsed):
        raise ValueError("tushare_context_value_invalid")
    return parsed


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
