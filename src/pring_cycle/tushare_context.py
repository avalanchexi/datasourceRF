from __future__ import annotations

import calendar
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import Any
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo

from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TUSHARE_ENDPOINT

Transport = Callable[[dict[str, Any]], dict[str, Any]]

WARRANT_SYMBOLS = frozenset({"CU", "RB", "PP", "CF", "TA", "RU", "SP", "SC"})
_WARRANT_UNITS = {
    "吨": "tonne",
    "千克": "kilogram",
    "公斤": "kilogram",
    "张": "sheet",
    "手": "lot",
    "桶": "barrel",
}
_WARRANT_SOURCE_SYMBOLS = {"TA": "PTA"}


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
class ContextFamilySmokeResult:
    family: str
    status: str
    api_names: tuple[str, ...]
    metric_ids: tuple[str, ...]
    first_period: str
    last_period: str
    observation_count: int
    normalized_hash: str
    network_requests: int


@dataclass(frozen=True)
class ContextSourceSmokeResult:
    status: str
    target_business_date: str
    families: tuple[ContextFamilySmokeResult, ...]
    network_requests: int


@dataclass(frozen=True)
class _Field:
    metric_id: str
    source_field: str
    dimensions: dict[str, str]
    unit: str
    multiplier: float = 1.0


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

    def social_financing(
        self,
        *,
        start_month: str,
        end_month: str,
    ) -> tuple[ContextScalar, ...]:
        fields = (
            _Field(
                "CN_SF_TOTAL",
                "inc_month",
                {"measure": "monthly_increment"},
                "hundred_million_cny",
            ),
            _Field(
                "CN_SF_TOTAL",
                "inc_cumval",
                {"measure": "ytd_increment"},
                "hundred_million_cny",
            ),
            _Field(
                "CN_SF_TOTAL",
                "stk_endval",
                {"measure": "stock_end"},
                "hundred_million_cny",
                multiplier=10_000.0,
            ),
        )
        rows = self._call(
            "sf_month",
            {"start_m": _month_value(start_month), "end_m": _month_value(end_month)},
            ("month", *(item.source_field for item in fields)),
        )
        return _monthly_scalars("sf_month", rows, fields)

    def futures_warrants(
        self,
        *,
        start_date: date,
        end_date: date,
        symbol: str,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        normalized_symbol = symbol.upper()
        if normalized_symbol not in WARRANT_SYMBOLS:
            raise ValueError("tushare_warrant_symbol_not_allowed")
        source_symbol = _WARRANT_SOURCE_SYMBOLS.get(
            normalized_symbol,
            normalized_symbol,
        )
        fields = (
            ("pre_vol", "previous_registered_receipts"),
            ("vol", "registered_receipts"),
            ("vol_chg", "registered_receipts_change"),
        )
        rows = self._call(
            "fut_wsr",
            {
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "symbol": source_symbol,
            },
            (
                "trade_date",
                "symbol",
                "warehouse",
                *(source_field for source_field, _measure in fields),
                "unit",
                "exchange",
            ),
        )
        scalars: list[ContextScalar] = []
        for row in rows:
            row_symbol = _required_text(row.get("symbol"), "tushare_warrant_symbol_invalid")
            if row_symbol != source_symbol:
                raise ValueError("tushare_warrant_symbol_mismatch")
            warehouse = _required_text(
                row.get("warehouse"),
                "tushare_warrant_warehouse_missing",
            )
            exchange = _required_text(
                row.get("exchange"),
                "tushare_warrant_exchange_missing",
            )
            source_unit = _required_text(row.get("unit"), "tushare_warrant_unit_missing")
            try:
                unit = _WARRANT_UNITS[source_unit]
            except KeyError as error:
                raise ValueError("tushare_warrant_unit_unknown") from error
            for source_field, measure in fields:
                if _number(row.get(source_field)) is None:
                    continue
                scalars.append(
                    _daily_scalar(
                        "CN_FUTURES_WARRANTS",
                        "fut_wsr",
                        source_field,
                        row,
                        date_field="trade_date",
                        dimensions={
                            "symbol": normalized_symbol,
                            "warehouse": warehouse,
                            "exchange": exchange,
                            "measure": measure,
                        },
                        unit=unit,
                    )
                )
        return tuple(scalars)

    def gdp(
        self,
        *,
        start_quarter: str,
        end_quarter: str,
    ) -> tuple[ContextScalar, ...]:
        start_value = _quarter_value(start_quarter)
        end_value = _quarter_value(end_quarter)
        if _quarter_ordinal(end_value) < _quarter_ordinal(start_value):
            raise ValueError("tushare_quarter_range_invalid")
        fields = (
            ("total", "gdp", "gdp_yoy"),
            ("primary", "pi", "pi_yoy"),
            ("secondary", "si", "si_yoy"),
            ("tertiary", "ti", "ti_yoy"),
        )
        rows = self._call(
            "cn_gdp",
            {"start_q": start_value, "end_q": end_value},
            (
                "quarter",
                *(field for _aggregate, level, yoy in fields for field in (level, yoy)),
            ),
        )
        scalars: list[ContextScalar] = []
        for row in rows:
            year_start, quarter_start, quarter_end = _quarter_bounds(
                str(row.get("quarter"))
            )
            for aggregate, level_field, yoy_field in fields:
                level = _number(row.get(level_field))
                if level is not None:
                    scalars.append(
                        ContextScalar(
                            metric_id="CN_GDP",
                            api_name="cn_gdp",
                            source_field=level_field,
                            period_kind="year_to_quarter",
                            period_start=year_start,
                            period_end=quarter_end,
                            dimensions={
                                "aggregate": aggregate,
                                "measure": "nominal_ytd_level",
                            },
                            value=level,
                            unit="hundred_million_cny",
                        )
                    )
                yoy = _number(row.get(yoy_field))
                if yoy is not None:
                    scalars.append(
                        ContextScalar(
                            metric_id="CN_GDP",
                            api_name="cn_gdp",
                            source_field=yoy_field,
                            period_kind="quarter",
                            period_start=quarter_start,
                            period_end=quarter_end,
                            dimensions={
                                "aggregate": aggregate,
                                "measure": "real_quarter_yoy",
                            },
                            value=yoy,
                            unit="percent",
                        )
                    )
        return tuple(scalars)

    def treasury_yields(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        rows = self._call(
            "us_tycr",
            {
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
            },
            ("date", "y2", "y10"),
        )
        return tuple(
            _daily_scalar(
                metric_id,
                "us_tycr",
                source_field,
                row,
                date_field="date",
                dimensions={},
                unit="percent",
            )
            for row in rows
            for metric_id, source_field in (
                ("UST2Y_NOMINAL_YIELD", "y2"),
                ("UST10Y_NOMINAL_YIELD", "y10"),
            )
            if _number(row.get(source_field)) is not None
        )

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
    definition_version: str = METRIC_CATALOG_VERSION,
) -> ContextIngestionResult:
    if fetched_at.tzinfo is None:
        raise ValueError("tushare_context_fetched_at_must_be_timezone_aware")
    if not scalars:
        raise ValueError("tushare_context_observations_missing")
    # TuShare's macro tables do not expose an announcement timestamp. The first
    # schema-valid retrieval is therefore the conservative public availability
    # bound; it must never be backdated to the statistical period.
    repository = EvidenceRepository(paths.database)
    claims: list[SourceClaimInput] = []
    stored_by_input: list[StoredSourceClaim | None] = []
    for scalar in scalars:
        definition = metric_definition(
            scalar.metric_id,
            definition_version=definition_version,
        )
        source_reference = (
            f"tushare:{scalar.api_name}:{scalar.source_field}:{scalar.period_end}"
        )
        base_event_id = f"tushare:{scalar.api_name}:{scalar.period_end}"
        existing = repository.latest_source_claim(
            metric_id=scalar.metric_id,
            definition_version=definition.definition_version,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            provider="tushare",
            source_reference=source_reference,
        )
        physical_existing = repository.latest_provider_claim(
            metric_id=scalar.metric_id,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            provider="tushare",
            source_reference=source_reference,
        )
        if (
            existing is not None
            and existing.value_state is EvidenceValueState.REPORTED_VALUE
            and existing.value == scalar.value
            and existing.unit == scalar.unit
        ):
            stored_by_input.append(
                StoredSourceClaim(
                    existing.claim_id,
                    existing.observation_id,
                    existing.supersedes_claim_id,
                )
            )
            continue
        physical_same = bool(
            physical_existing is not None
            and physical_existing.value_state is EvidenceValueState.REPORTED_VALUE
            and physical_existing.value == scalar.value
            and physical_existing.unit == scalar.unit
        )
        if existing is None and physical_same and physical_existing is not None:
            release_event_id = physical_existing.release_event_id
            release_at = physical_existing.release_at
            public_available_at = physical_existing.public_available_at
        else:
            release_event_id = (
                base_event_id
                if physical_existing is None
                else _revision_event_id(base_event_id, fetched_at)
            )
            release_at = scalar.release_at
            public_available_at = (
                scalar.public_available_at or fetched_at
                if physical_existing is None
                else fetched_at
            )
        claims.append(
            SourceClaimInput(
            metric_id=scalar.metric_id,
            definition_version=definition.definition_version,
            period_kind=scalar.period_kind,
            period_start=scalar.period_start,
            period_end=scalar.period_end,
            dimensions=scalar.dimensions,
            value=scalar.value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=scalar.unit,
            provider="tushare",
            source_reference=source_reference,
            release_event_id=release_event_id,
            release_at=release_at,
            public_available_at=public_available_at,
            fetched_at=fetched_at,
            available_at=fetched_at,
            certification_status=definition.certification_status,
            quality_status="validated",
        )
        )
        stored_by_input.append(None)
    newly_stored = iter(repository.append_source_claims(tuple(claims)) if claims else ())
    stored = tuple(item if item is not None else next(newly_stored) for item in stored_by_input)
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


def _revision_event_id(base_event_id: str, fetched_at: datetime) -> str:
    suffix = hashlib.sha256(fetched_at.isoformat().encode()).hexdigest()[:16]
    return f"{base_event_id}:revision:{suffix}"


def summarize_context_source_smoke(
    family: str,
    scalars: tuple[ContextScalar, ...],
    *,
    network_requests: int,
) -> ContextFamilySmokeResult:
    if not family:
        raise ValueError("tushare_context_smoke_family_required")
    if not scalars:
        raise ValueError(f"tushare_context_smoke_observations_missing:{family}")
    if network_requests < 1:
        raise ValueError("tushare_context_smoke_network_requests_invalid")
    normalized = [
        (
            scalar.metric_id,
            scalar.api_name,
            scalar.source_field,
            scalar.period_kind,
            scalar.period_start,
            scalar.period_end,
            tuple(sorted(scalar.dimensions.items())),
            scalar.value,
            scalar.unit,
            scalar.release_at.isoformat() if scalar.release_at is not None else None,
            (
                scalar.public_available_at.isoformat()
                if scalar.public_available_at is not None
                else None
            ),
        )
        for scalar in sorted(
            scalars,
            key=lambda item: (
                item.metric_id,
                item.period_end,
                item.api_name,
                item.source_field,
                tuple(sorted(item.dimensions.items())),
            ),
        )
    ]
    return ContextFamilySmokeResult(
        family=family,
        status="validated_candidate",
        api_names=tuple(sorted({scalar.api_name for scalar in scalars})),
        metric_ids=tuple(sorted({scalar.metric_id for scalar in scalars})),
        first_period=min(scalar.period_end for scalar in scalars),
        last_period=max(scalar.period_end for scalar in scalars),
        observation_count=len(scalars),
        normalized_hash=hashlib.sha256(_canonical_json(normalized).encode()).hexdigest(),
        network_requests=network_requests,
    )


def smoke_context_sources(
    adapter: TushareContextAdapter,
    *,
    target_business_date: date,
) -> ContextSourceSmokeResult:
    start_month = date(
        target_business_date.year - 2,
        target_business_date.month,
        1,
    ).strftime("%Y%m")
    end_month = target_business_date.strftime("%Y%m")
    quarter = (target_business_date.month - 1) // 3 + 1
    start_quarter = f"{target_business_date.year - 2}Q{quarter}"
    end_quarter = f"{target_business_date.year}Q{quarter}"
    start_date = target_business_date - timedelta(days=45)
    warrant_scalars = tuple(
        scalar
        for symbol in sorted(WARRANT_SYMBOLS)
        for scalar in adapter.futures_warrants(
            start_date=start_date,
            end_date=target_business_date,
            symbol=symbol,
        )
    )
    observed_warrant_symbols = {
        scalar.dimensions.get("symbol") for scalar in warrant_scalars
    }
    if observed_warrant_symbols != set(WARRANT_SYMBOLS):
        raise ValueError("tushare_context_smoke_warrant_symbols_incomplete")
    families = (
        summarize_context_source_smoke(
            "pmi",
            adapter.pmi(start_month=start_month, end_month=end_month),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "prices",
            adapter.prices(start_month=start_month, end_month=end_month),
            network_requests=2,
        ),
        summarize_context_source_smoke(
            "money",
            adapter.money(start_month=start_month, end_month=end_month),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "social_financing",
            adapter.social_financing(start_month=start_month, end_month=end_month),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "futures_warrants",
            warrant_scalars,
            network_requests=len(WARRANT_SYMBOLS),
        ),
        summarize_context_source_smoke(
            "gdp",
            adapter.gdp(start_quarter=start_quarter, end_quarter=end_quarter),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "treasury_yields",
            adapter.treasury_yields(
                start_date=start_date,
                end_date=target_business_date,
            ),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "transmission",
            adapter.transmission(
                start_date=start_date,
                end_date=target_business_date,
            ),
            network_requests=2,
        ),
    )
    return ContextSourceSmokeResult(
        status="validated_candidate",
        target_business_date=target_business_date.isoformat(),
        families=families,
        network_requests=sum(family.network_requests for family in families),
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
                    value=value * field.multiplier,
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


def _quarter_value(value: str) -> str:
    normalized = value.upper()
    if (
        len(normalized) != 6
        or normalized[4] != "Q"
        or not normalized[:4].isdigit()
        or normalized[5] not in "1234"
    ):
        raise ValueError("tushare_quarter_invalid")
    return normalized


def _quarter_ordinal(value: str) -> int:
    normalized = _quarter_value(value)
    return int(normalized[:4]) * 4 + int(normalized[5])


def _quarter_bounds(value: str) -> tuple[str, str, str]:
    normalized = _quarter_value(value)
    year = int(normalized[:4])
    quarter = int(normalized[5])
    first_month = (quarter - 1) * 3 + 1
    final_month = quarter * 3
    final_day = calendar.monthrange(year, final_month)[1]
    return (
        f"{year:04d}-01-01",
        f"{year:04d}-{first_month:02d}-01",
        f"{year:04d}-{final_month:02d}-{final_day:02d}",
    )


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


def _required_text(value: object, error_code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_code)
    return value.strip()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
