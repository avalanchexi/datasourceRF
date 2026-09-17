from __future__ import annotations

import calendar
import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import isfinite
from typing import Any
from urllib.request import Request, build_opener

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository, utc_now
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import MARGIN_FINANCING_V0002, METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.futures_inputs import FuturesInputAcquisition
from pring_cycle.http_transport import NoRedirect
from pring_cycle.market_breadth import (
    DailyBreadthResult,
    FullDaySuspensionEvidence,
    MarketBreadthDay,
    _input_day,
    _listing_intervals,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import TUSHARE_ENDPOINT
from pring_cycle.source_families import (
    TUSHARE_CPI_FIELDS,
    TUSHARE_MONEY_FIELDS,
    TUSHARE_PMI_FIELDS,
    TUSHARE_PPI_FIELDS,
)

Transport = Callable[[dict[str, Any]], dict[str, Any] | bytes]

WARRANT_SYMBOLS = frozenset({"CU", "RB", "PP", "CF", "TA", "RU", "SP", "SC"})
_FUTURES_WARRANT_CHUNK_DAYS = 31
_FUTURES_WARRANT_RESPONSE_LIMIT = 1_000
MARKET_INDEX_IDENTITIES = {
    "CN_EQ_CSI300": ("index_daily", "000300.SH"),
    "CN_EQ_CSI500": ("index_daily", "000905.SH"),
    "CN_EQ_CSI1000": ("index_daily", "000852.SH"),
    "CN_BOND_FULL_PRICE_CNY030": ("index_daily", "000012CNY030.CSI"),
    "CN_BOND_10Y_930916": ("index_daily", "930916.CSI"),
    "CN_COMMODITY_BROAD_NHCI": ("fut_index_daily", "NHCI.NH"),
}
VALUATION_INDEX_CODES = ("000300.SH", "000905.SH", "000852.SH")
VALUATION_FIELDS = (
    ("pe", "price_earnings", "multiple"),
    ("pb", "price_book", "multiple"),
    ("turnover_rate", "turnover_rate", "percent"),
)
FUTURES_SLEEVE_CODES = {
    "copper": ("CU.SHF",),
    "rebar": ("RB.SHF",),
    "polypropylene": ("PP.DCE",),
    "textiles": ("CF.ZCE", "TA.ZCE"),
    "rubber": ("RU.SHF",),
    "pulp": ("SP.SHF",),
    "crude_oil": ("SC.INE",),
}
FUTURES_SLEEVE_WEIGHTS = {
    "copper": 2.0 / 15.0,
    "rebar": 2.0 / 15.0,
    "polypropylene": 2.0 / 15.0,
    "textiles": 2.0 / 15.0,
    "rubber": 2.0 / 15.0,
    "pulp": 2.0 / 15.0,
    "crude_oil": 1.0 / 5.0,
}
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
    definition_version: str | None = None
    acquisition_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextIngestionResult:
    observation_count: int
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]
    rejected_field_count: int = 0


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


ContextRows = tuple[dict[str, object], ...]
ContextRequestOperation = Callable[[Callable[[str], None] | None], ContextRows]
ContextRequestWrapper = Callable[
    [str, dict[str, str], tuple[str, ...], ContextRequestOperation], ContextRows
]


class TushareContextAdapter:
    def __init__(self, token: str, *, transport: Transport | None = None) -> None:
        if not token:
            raise ValueError("tushare_token_required")
        self._token = token
        self._transport = transport or self._post
        self._network_requests = 0
        self._acquisitions: AcquisitionRepository | None = None
        self._receipts: list[AcquisitionReceipt] = []
        self._request_wrapper: ContextRequestWrapper | None = None
        self._field_rejections: list[dict[str, str]] = []
        self._daily_breadth: list[DailyBreadthResult] = []
        self._window_breadth: list[dict[str, Any]] = []
        self._amount_breadth: list[dict[str, Any]] = []

    def acquire_scalars(
        self,
        paths: RuntimePaths,
        retrieve: Callable[[], tuple[ContextScalar, ...]],
        *,
        definition_version: str = METRIC_CATALOG_VERSION,
        request_wrapper: ContextRequestWrapper | None = None,
    ) -> ContextIngestionResult:
        if self._acquisitions is not None:
            raise ValueError("context_acquisition_already_running")
        self._acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        self._receipts = []
        self._request_wrapper = request_wrapper
        self._field_rejections = []
        self._daily_breadth = []
        self._window_breadth = []
        self._amount_breadth = []
        try:
            scalars = retrieve()
            if not self._receipts:
                raise ValueError("context_acquisition_receipts_missing")
            has_amount_inputs = any(r.api_name == "breadth_amount_inputs" for r in self._receipts)
            has_window_inputs = any(r.api_name == "breadth_window_inputs" for r in self._receipts)
            if (
                has_amount_inputs
                or has_window_inputs
                or any(r.api_name == "breadth_universe" for r in self._receipts)
            ):
                from pring_cycle.market_amount import (
                    AMOUNT_BREADTH_MEASURES,
                    AMOUNT_BREADTH_SOURCE_CODE,
                    amount_breadth_scalars,
                    parse_amount_breadth_acquisitions,
                )
                from pring_cycle.market_breadth import (
                    DAILY_BREADTH_MEASURES,
                    DAILY_BREADTH_SOURCE_CODE,
                    WINDOW_BREADTH_MEASURES,
                    WINDOW_BREADTH_SOURCE_CODE,
                    parse_daily_breadth_acquisitions,
                    parse_window_breadth_acquisitions,
                    validate_daily_breadth_scalars,
                    window_breadth_scalars,
                )
                from pring_cycle.source_contract_review import require_registered_source_contract

                if definition_version in BUILTIN_CATALOG_VERSIONS:
                    raise ValueError("breadth_registered_definition_required")
                measures = WINDOW_BREADTH_MEASURES if has_window_inputs else DAILY_BREADTH_MEASURES
                source_code = (
                    WINDOW_BREADTH_SOURCE_CODE if has_window_inputs else DAILY_BREADTH_SOURCE_CODE
                )
                if has_amount_inputs:
                    measures = AMOUNT_BREADTH_MEASURES
                    source_code = AMOUNT_BREADTH_SOURCE_CODE
                definitions = {
                    metric: metric_definition(
                        metric, definition_version=definition_version, database_path=paths.database
                    )
                    for metric in measures
                }
                if any(d.source_codes != (source_code,) for d in definitions.values()):
                    family = (
                        "amount"
                        if has_amount_inputs
                        else "window"
                        if has_window_inputs
                        else "daily"
                    )
                    raise ValueError(f"registered_{family}_breadth_source_contract_unsupported")
                originals = tuple(
                    (r, self._acquisitions.read_content(r.acquisition_id, "raw"))
                    for r in self._receipts
                )
                if has_amount_inputs:
                    self._amount_breadth = parse_amount_breadth_acquisitions(
                        originals, paths.artifacts
                    )
                    _require_breadth_scalar_match(
                        scalars,
                        amount_breadth_scalars(self._amount_breadth),
                        definition_version=definition_version,
                        family="amount",
                    )
                elif has_window_inputs:
                    self._window_breadth = parse_window_breadth_acquisitions(
                        originals, paths.artifacts
                    )
                    _require_breadth_scalar_match(
                        scalars,
                        window_breadth_scalars(self._window_breadth),
                        definition_version=definition_version,
                        family="window",
                    )
                else:
                    days = parse_daily_breadth_acquisitions(originals, paths.artifacts)
                    if days != self._daily_breadth:
                        raise ValueError("breadth_daily_inputs_mismatch")
                    validate_daily_breadth_scalars(
                        scalars, days, definition_version=definition_version
                    )
                for scalar in scalars:
                    require_registered_source_contract(
                        definitions[scalar.metric_id],
                        provider="tushare",
                        source_reference=f"tushare:{scalar.api_name}:{scalar.source_field}:{scalar.period_end}",
                        period_kind=scalar.period_kind,
                        dimensions=scalar.dimensions,
                        unit=scalar.unit,
                        period_start=scalar.period_start,
                        period_end=scalar.period_end,
                        database_path=paths.database,
                        value=scalar.value,
                        acquisition_ids=(),
                    )
            if definition_version not in BUILTIN_CATALOG_VERSIONS:
                family_contracts = (
                    ("margin", {"CN_MARGIN_BALANCE"}, {"margin"}, parse_margin_acquisition),
                    (
                        "market_index",
                        set(MARKET_INDEX_IDENTITIES),
                        {"index_daily", "fut_index_daily"},
                        parse_market_index_acquisition,
                    ),
                    (
                        "valuation",
                        {"CN_INDEX_VALUATION"},
                        {"index_dailybasic"},
                        parse_valuation_acquisition,
                    ),
                )
                for family, metric_ids, api_names, parse_scalars in family_contracts:
                    outputs = tuple(
                        replace(
                            scalar,
                            release_at=None,
                            public_available_at=None,
                            definition_version=None,
                            acquisition_ids=(),
                        )
                        for scalar in scalars
                        if scalar.metric_id in metric_ids
                    )
                    if not outputs:
                        continue
                    parsed_inputs = tuple(
                        scalar
                        for receipt in self._receipts
                        if receipt.api_name in api_names
                        for scalar in parse_scalars(
                            receipt,
                            self._acquisitions.read_content(receipt.acquisition_id, "raw"),
                        )
                    )
                    if sorted(_canonical_json(asdict(s)) for s in parsed_inputs) != sorted(
                        _canonical_json(asdict(s)) for s in outputs
                    ):
                        raise ValueError(f"registered_{family}_acquisition_values_mismatch")
            warrant_inputs = self._warrant_receipt_inputs()
            linked = []
            for scalar in scalars:
                matching = [r for r in self._receipts if r.api_name == scalar.api_name]
                inputs = matching or self._receipts
                if self._window_breadth and scalar.api_name == "window_breadth":
                    output = next(
                        day
                        for day in self._window_breadth
                        if day["business_date"] == scalar.period_end
                    )
                    input_dates = {day.replace("-", "") for day in output["input_dates"]}
                    inputs = [
                        receipt
                        for receipt in self._receipts
                        if receipt.api_name
                        in {"breadth_window_inputs", "breadth_universe", "trade_cal"}
                        or receipt.api_name in {"daily", "suspend_d"}
                        and receipt.parameters.get("trade_date") in input_dates
                    ]
                if self._amount_breadth and scalar.api_name == "amount_breadth":
                    inputs = [
                        r
                        for r in self._receipts
                        if r.api_name in {"breadth_amount_inputs", "breadth_universe", "trade_cal"}
                        or r.parameters.get("trade_date") == scalar.period_end.replace("-", "")
                    ]
                if self._daily_breadth and scalar.api_name == "daily_breadth":
                    inputs = [
                        receipt
                        for receipt in self._receipts
                        if receipt.api_name in {"breadth_universe", "trade_cal"}
                        or receipt.parameters.get("trade_date")
                        == scalar.period_end.replace("-", "")
                    ]
                if (
                    definition_version not in BUILTIN_CATALOG_VERSIONS
                    and scalar.metric_id in MARKET_INDEX_IDENTITIES
                ):
                    inputs = [
                        receipt
                        for receipt in matching
                        if receipt.parameters.get("ts_code") == scalar.dimensions.get("source_code")
                    ]
                    if not inputs:
                        raise ValueError("registered_market_index_acquisition_missing")
                if (
                    definition_version not in BUILTIN_CATALOG_VERSIONS
                    and scalar.metric_id == "CN_INDEX_VALUATION"
                ):
                    inputs = [
                        receipt
                        for receipt in matching
                        if receipt.parameters.get("ts_code") == scalar.dimensions.get("index")
                    ]
                    if not inputs:
                        raise ValueError("registered_valuation_acquisition_missing")
                if scalar.metric_id == "CN_FUTURES_WARRANTS" and scalar.api_name == "fut_wsr":
                    inputs = warrant_inputs.get(_warrant_input_identity(scalar), [])
                    if not inputs:
                        raise ValueError("tushare_warrant_acquisition_member_missing")
                linked.append(
                    replace(scalar, acquisition_ids=tuple(r.acquisition_id for r in inputs))
                )
            normalized: object = [asdict(s) for s in linked]
            if self._window_breadth:
                normalized = {
                    "accepted_scalars": normalized,
                    "window_breadth": self._window_breadth,
                }
            if self._amount_breadth:
                normalized = {
                    "accepted_scalars": normalized,
                    "amount_breadth": self._amount_breadth,
                }
            if self._daily_breadth:
                normalized = {"accepted_scalars": normalized, "daily_breadth": self._daily_breadth}
            if self._field_rejections:
                normalized = {
                    "accepted_scalars": normalized,
                    "rejected_fields": self._field_rejections,
                }
            store_artifact(
                paths.database,
                paths.artifacts,
                _canonical_json(normalized).encode(),
                "application/json",
                f"context-acquisition:{self._receipts[0].acquisition_id}",
            )
            for receipt in self._receipts:
                receipt_document: object
                if self._window_breadth or self._amount_breadth:
                    # The immutable batch remains auditable; each scalar names its own parents.
                    receipt_document = normalized
                else:
                    receipt_document = [
                        asdict(s) for s in linked if receipt.acquisition_id in s.acquisition_ids
                    ]
                if self._daily_breadth:
                    receipt_document = {
                        "accepted_scalars": receipt_document,
                        "daily_breadth": [
                            day
                            for day in self._daily_breadth
                            if receipt.api_name in {"breadth_universe", "trade_cal"}
                            or day["business_date"].replace("-", "")
                            == receipt.parameters.get("trade_date")
                        ],
                    }
                rejected = [
                    item for item in self._field_rejections if item["api_name"] == receipt.api_name
                ]
                if rejected:
                    receipt_document = {
                        "accepted_scalars": receipt_document,
                        "rejected_fields": rejected,
                    }
                self._acquisitions.complete_validation(
                    receipt.acquisition_id,
                    receipt_document,
                )
            if (self._daily_breadth or self._window_breadth or self._amount_breadth) and not linked:
                return ContextIngestionResult(0, (), (), ())
            result = ingest_context_scalars(
                paths,
                tuple(linked),
                fetched_at=utc_now(),
                definition_version=definition_version,
            )
            return replace(result, rejected_field_count=len(self._field_rejections))
        except Exception as error:
            for receipt in self._receipts:
                self._acquisitions.fail_validation(receipt.acquisition_id, error)
            raise
        finally:
            self._acquisitions = None
            self._receipts = []
            self._request_wrapper = None
            self._field_rejections = []
            self._daily_breadth = []
            self._window_breadth = []
            self._amount_breadth = []

    @property
    def network_requests(self) -> int:
        return self._network_requests

    def _warrant_receipt_inputs(
        self,
    ) -> dict[tuple[str, str, str, str, str, str, float], list[AcquisitionReceipt]]:
        """Index only complete physical warrant responses by their actual scalar rows."""
        result: dict[tuple[str, str, str, str, str, str, float], list[AcquisitionReceipt]] = {}
        assert self._acquisitions is not None
        for receipt in self._receipts:
            if receipt.api_name != "fut_wsr":
                continue
            document = json.loads(self._acquisitions.read_content(receipt.acquisition_id, "raw"))
            rows = _response_rows(document, required_fields=tuple(receipt.fields.split(",")))
            if len(rows) >= _FUTURES_WARRANT_RESPONSE_LIMIT:
                continue
            for row in rows:
                source_symbol = str(row["symbol"]).strip()
                symbol = "TA" if source_symbol == "PTA" else source_symbol
                unit = _WARRANT_UNITS[str(row["unit"]).strip()]
                for field in ("pre_vol", "vol", "vol_chg"):
                    value = _number(row.get(field))
                    if value is None:
                        continue
                    identity = (
                        symbol,
                        _compact_date(row["trade_date"]).isoformat(),
                        str(row["warehouse"]).strip(),
                        str(row["exchange"]).strip(),
                        field,
                        unit,
                        value,
                    )
                    result.setdefault(identity, []).append(receipt)
        return result

    def pmi(self, *, start_month: str, end_month: str) -> tuple[ContextScalar, ...]:
        fields = tuple(
            _Field(metric, field, {"series": series, "measure": "level"}, "diffusion_index_points")
            for field, metric, series in TUSHARE_PMI_FIELDS
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
            for field, measure in TUSHARE_CPI_FIELDS
        )
        ppi_fields = tuple(
            _Field(
                "CN_PPI",
                source_field,
                {"measure": measure, "category": category},
                "percent",
            )
            for source_field, category, measure in TUSHARE_PPI_FIELDS
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

    def money(
        self, *, start_month: str, end_month: str, include_month_on_month: bool = True
    ) -> tuple[ContextScalar, ...]:
        fields = tuple(
            _Field(
                "CN_M1_M2",
                aggregate if measure == "balance" else f"{aggregate}_{measure}",
                {"aggregate": aggregate, "measure": measure},
                "hundred_million_cny" if measure == "balance" else "percent",
            )
            for aggregate in ("m1", "m2")
            for measure in ("balance", "yoy", "mom")
            if include_month_on_month or measure != "mom"
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
        requested_fields = (
            "trade_date",
            "symbol",
            "warehouse",
            *(source_field for source_field, _measure in fields),
            "unit",
            "exchange",
        )
        rows = tuple(
            row
            for chunk_start, chunk_end in _inclusive_date_chunks(
                start_date,
                end_date,
                chunk_days=_FUTURES_WARRANT_CHUNK_DAYS,
            )
            for row in self._complete_futures_warrant_range(
                chunk_start,
                chunk_end,
                source_symbol=source_symbol,
                requested_fields=requested_fields,
            )
        )
        return _warrant_scalars(rows, normalized_symbol, source_symbol, fields)

    def _complete_futures_warrant_range(
        self,
        start_date: date,
        end_date: date,
        *,
        source_symbol: str,
        requested_fields: tuple[str, ...],
    ) -> tuple[dict[str, object], ...]:
        rows = self._call(
            "fut_wsr",
            {
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "symbol": source_symbol,
            },
            requested_fields,
        )
        if len(rows) < _FUTURES_WARRANT_RESPONSE_LIMIT:
            return rows
        if start_date == end_date:
            raise ValueError("tushare_warrant_response_truncated")
        midpoint = start_date + (end_date - start_date) // 2
        return (
            *self._complete_futures_warrant_range(
                start_date,
                midpoint,
                source_symbol=source_symbol,
                requested_fields=requested_fields,
            ),
            *self._complete_futures_warrant_range(
                midpoint + timedelta(days=1),
                end_date,
                source_symbol=source_symbol,
                requested_fields=requested_fields,
            ),
        )

    def gdp(
        self,
        *,
        start_quarter: str,
        end_quarter: str,
    ) -> tuple[ContextScalar, ...]:
        """Keep nominal levels; disputed provider YoY fields require separate certification."""
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
            year_start, _quarter_start, quarter_end = _quarter_bounds(str(row.get("quarter")))
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
                if yoy is not None and self._acquisitions is not None:
                    # Q2 delivery disagrees with the documented single-quarter
                    # meaning. Do not relabel every vintage as cumulative either.
                    self._field_rejections.append(
                        {
                            "metric_id": "CN_GDP",
                            "api_name": "cn_gdp",
                            "source_field": yoy_field,
                            "period_end": quarter_end,
                            "reason": "gdp_yoy_period_semantics_unverified",
                        }
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
        return _transmission_scalars(repo_rows, shibor_rows)

    def market_indices(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        scalars: list[ContextScalar] = []
        for metric_id, (api_name, source_code) in MARKET_INDEX_IDENTITIES.items():
            rows = self._call(
                api_name,
                {
                    "ts_code": source_code,
                    "start_date": start_date.strftime("%Y%m%d"),
                    "end_date": end_date.strftime("%Y%m%d"),
                },
                ("ts_code", "trade_date", "close"),
            )
            scalars.extend(_market_index_scalars(metric_id, rows))
        return tuple(scalars)

    def margin_financing(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        rows = self._call(
            "margin",
            {
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
            },
            ("trade_date", "exchange_id", "rzye", "rzmre"),
        )
        totals: dict[str, dict[str, float]] = defaultdict(
            lambda: {"financing_balance": 0.0, "financing_buy_amount": 0.0}
        )
        exchanges: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            trade_date = _compact_date(row.get("trade_date")).isoformat()
            exchange = _required_text(
                row.get("exchange_id"),
                "tushare_margin_exchange_missing",
            )
            balance = _number(row.get("rzye"))
            buy_amount = _number(row.get("rzmre"))
            if balance is None or buy_amount is None:
                raise ValueError("tushare_margin_value_missing")
            totals[trade_date]["financing_balance"] += balance
            totals[trade_date]["financing_buy_amount"] += buy_amount
            exchanges[trade_date].add(exchange)
        scalars: list[ContextScalar] = []
        for trade_date, measures in sorted(totals.items()):
            if not exchanges[trade_date].issubset({"SSE", "SZSE", "BSE"}):
                raise ValueError("tushare_margin_exchange_invalid")
            for measure, value in measures.items():
                scalars.append(
                    _business_day_scalar(
                        metric_id="CN_MARGIN_BALANCE",
                        api_name="margin",
                        source_field=measure,
                        business_date=date.fromisoformat(trade_date),
                        dimensions={"measure": measure, "scope": "all_exchanges"},
                        value=value / 100_000_000.0,
                        unit="hundred_million_cny",
                    )
                )
        return tuple(scalars)

    def margin_financing_candidate(
        self,
        *,
        trading_days: tuple[date, ...],
    ) -> tuple[ContextScalar, ...]:
        """Collect the new, uncertified three-exchange contract for source review."""
        if not trading_days or len(set(trading_days)) != len(trading_days):
            raise ValueError("tushare_margin_calendar_invalid")
        rows = self._call(
            "margin",
            {
                "start_date": min(trading_days).strftime("%Y%m%d"),
                "end_date": max(trading_days).strftime("%Y%m%d"),
            },
            ("trade_date", "exchange_id", "rzye", "rzmre"),
        )
        totals: dict[date, dict[str, float]] = defaultdict(
            lambda: {"financing_balance": 0.0, "financing_buy_amount": 0.0}
        )
        expected_dates = set(trading_days)
        expected_exchanges = {"SSE", "SZSE", "BSE"}
        seen: set[tuple[date, str]] = set()
        for row in rows:
            trading_day = _compact_date(row.get("trade_date"))
            if trading_day not in expected_dates:
                raise ValueError("tushare_margin_unexpected_trading_day")
            exchange = str(row.get("exchange_id"))
            if exchange not in expected_exchanges:
                raise ValueError("tushare_margin_exchange_invalid")
            identity = (trading_day, exchange)
            if identity in seen:
                raise ValueError("tushare_margin_duplicate_exchange_day")
            seen.add(identity)
            for field, measure in (
                ("rzye", "financing_balance"),
                ("rzmre", "financing_buy_amount"),
            ):
                value = _number(row.get(field))
                if value is None:
                    raise ValueError("tushare_margin_value_missing")
                if value < 0:
                    raise ValueError("tushare_margin_value_negative")
                totals[trading_day][measure] += value
        if seen != {(day, exchange) for day in expected_dates for exchange in expected_exchanges}:
            raise ValueError("tushare_margin_exchange_coverage_incomplete")
        return tuple(
            ContextScalar(
                metric_id="CN_MARGIN_BALANCE",
                api_name="margin",
                source_field=measure,
                period_kind="business_day",
                period_start=trading_day.isoformat(),
                period_end=trading_day.isoformat(),
                dimensions={"measure": measure, "scope": "SSE+SZSE+BSE"},
                value=value / 100_000_000,
                unit="hundred_million_cny",
                definition_version=MARGIN_FINANCING_V0002,
            )
            for trading_day, measures in sorted(totals.items())
            for measure, value in measures.items()
        )

    def index_valuation(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        scalars: list[ContextScalar] = []
        for source_code in VALUATION_INDEX_CODES:
            rows = self._call(
                "index_dailybasic",
                {
                    "ts_code": source_code,
                    "start_date": start_date.strftime("%Y%m%d"),
                    "end_date": end_date.strftime("%Y%m%d"),
                },
                ("ts_code", "trade_date", *(field for field, _measure, _unit in VALUATION_FIELDS)),
            )
            scalars.extend(_valuation_scalars(source_code, rows))
        return tuple(scalars)

    def market_breadth_inputs(
        self,
        *,
        trading_days: tuple[date, ...],
        full_day_suspension_evidence: tuple[FullDaySuspensionEvidence, ...] = (),
    ) -> tuple[MarketBreadthDay, ...]:
        """Reconstruct listing intervals; these are not historical publication claims.

        Include currently delisted/suspended listings, not just current survivors.
        bak_basic is insufficient: it can omit still-trading delisting-period stocks.
        Dated, previously reviewed official evidence can resolve an S/R conflict;
        its hash is preserved in the frame and never establishes public availability.
        """
        if not trading_days or len(set(trading_days)) != len(trading_days):
            raise ValueError("tushare_breadth_calendar_invalid")
        evidence_keys = {
            (item.business_date, item.ts_code) for item in full_day_suspension_evidence
        }
        if len(evidence_keys) != len(full_day_suspension_evidence) or any(
            day not in trading_days for day, _ in evidence_keys
        ):
            raise ValueError("tushare_breadth_suspension_evidence_invalid")
        member_rows: list[dict[str, object]] = []
        for status in ("L", "D", "P"):
            rows = self._call(
                "stock_basic",
                {"list_status": status},
                ("ts_code", "list_status", "list_date", "delist_date"),
            )
            if len(rows) >= 6_000:
                raise ValueError("tushare_breadth_response_incomplete")
            if any(row["list_status"] != status for row in rows):
                raise ValueError("tushare_breadth_listing_status_invalid")
            member_rows.extend(rows)
        listings = _listing_intervals(
            tuple(member_rows), first_day=min(trading_days), last_day=max(trading_days)
        )
        result = []
        for trading_day in sorted(trading_days):
            params = {"trade_date": trading_day.strftime("%Y%m%d")}
            quotes = self._call(
                "daily",
                params,
                ("ts_code", "trade_date", "close", "pre_close", "amount", "ah_amount"),
            )
            suspensions = self._call(
                "suspend_d", params, ("ts_code", "trade_date", "suspend_type", "suspend_timing")
            )
            result.append(
                _input_day(
                    trading_day,
                    listings=listings,
                    quotes=quotes,
                    suspensions=suspensions,
                    full_day_suspension_evidence=tuple(
                        item
                        for item in full_day_suspension_evidence
                        if item.business_date == trading_day
                    ),
                )
            )
        return tuple(result)

    def _reviewed_daily_breadth(
        self, start: date, end: date, universe_hash: str
    ) -> tuple[ContextScalar, ...]:
        from pring_cycle.market_breadth import (
            _breadth_artifact,
            daily_breadth_day,
            daily_breadth_scalars,
            load_breadth_universe,
        )

        if self._acquisitions is None:
            raise ValueError("breadth_acquisition_required")
        acquisitions = self._acquisitions
        captured = acquisitions.capture(
            provider="reviewed_evidence",
            api_name="breadth_universe",
            parameters={"universe_hash": universe_hash},
            fields="",
            parser_version="market-breadth-universe-v0001",
            fetch=lambda: _breadth_artifact(acquisitions.artifacts, universe_hash),
            parse=lambda raw: load_breadth_universe(raw, acquisitions.artifacts),
            normalize=lambda document: document,
            defer_validation=True,
        )
        self._receipts.append(captured.receipt)
        calendar_rows = self._call(
            "trade_cal",
            {
                "exchange": "SSE",
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
                "is_open": "1",
            },
            ("cal_date", "is_open"),
        )
        days = sorted(
            _compact_date(row["cal_date"]) for row in calendar_rows if str(row["is_open"]) == "1"
        )
        for day in days:
            params = {"trade_date": day.strftime("%Y%m%d")}
            quotes = self._call(
                "daily", params, ("ts_code", "trade_date", "close", "pre_close", "vol")
            )
            # The generic API parser uses floats. Daily price classification must
            # retain every decimal digit delivered in the captured JSON number.
            quote_receipt = self._receipts[-1]
            if quote_receipt.api_name != "daily" or quote_receipt.parameters != params:
                raise ValueError("breadth_daily_receipt_missing")
            quotes = _response_rows(
                json.loads(
                    acquisitions.read_content(quote_receipt.acquisition_id, "raw"),
                    parse_float=Decimal,
                ),
                required_fields=("ts_code", "trade_date", "close", "pre_close", "vol"),
            )
            suspensions = self._call(
                "suspend_d", params, ("ts_code", "trade_date", "suspend_type", "suspend_timing")
            )
            result = daily_breadth_day(day, captured.value, quotes, suspensions)
            self._daily_breadth.append(result)
        return daily_breadth_scalars(self._daily_breadth)

    def _reviewed_window_breadth(
        self,
        start: date,
        end: date,
        universe_hash: str,
        window_inputs_hash: str,
        *,
        output_days: int,
    ) -> tuple[ContextScalar, ...]:
        from pring_cycle.market_breadth import (
            _breadth_artifact,
            load_breadth_window_inputs,
            parse_window_breadth_acquisitions,
            window_breadth_scalars,
        )

        if self._acquisitions is None:
            raise ValueError("breadth_acquisition_required")
        acquisitions = self._acquisitions
        captured = acquisitions.capture(
            provider="reviewed_evidence",
            api_name="breadth_window_inputs",
            parameters={
                "window_inputs_hash": window_inputs_hash,
                "output_start": start.isoformat(),
                "output_end": end.isoformat(),
                "output_days": str(output_days),
            },
            fields="",
            parser_version="market-breadth-window-inputs-v0001",
            fetch=lambda: _breadth_artifact(acquisitions.artifacts, window_inputs_hash),
            parse=lambda raw: load_breadth_window_inputs(raw, acquisitions.artifacts),
            normalize=lambda document: document,
            defer_validation=True,
        )
        self._receipts.append(captured.receipt)
        self._reviewed_daily_breadth(
            date.fromisoformat(captured.value["coverage_start"]), end, universe_hash
        )
        self._daily_breadth = []
        self._window_breadth = parse_window_breadth_acquisitions(
            tuple(
                (receipt, acquisitions.read_content(receipt.acquisition_id, "raw"))
                for receipt in self._receipts
            ),
            acquisitions.artifacts,
        )
        return window_breadth_scalars(self._window_breadth)

    def _reviewed_amount_breadth(
        self, start: date, end: date, universe_hash: str, amount_inputs_hash: str
    ) -> tuple[ContextScalar, ...]:
        from pring_cycle.market_amount import (
            amount_breadth_scalars,
            load_breadth_amount_inputs,
            parse_amount_breadth_acquisitions,
        )
        from pring_cycle.market_breadth import _breadth_artifact

        if self._acquisitions is None:
            raise ValueError("breadth_acquisition_required")
        acquisitions = self._acquisitions
        captured = acquisitions.capture(
            provider="reviewed_evidence",
            api_name="breadth_amount_inputs",
            parameters={"amount_inputs_hash": amount_inputs_hash},
            fields="",
            parser_version="market-breadth-amount-inputs-v0001",
            fetch=lambda: _breadth_artifact(acquisitions.artifacts, amount_inputs_hash),
            parse=lambda raw: load_breadth_amount_inputs(raw, acquisitions.artifacts),
            normalize=lambda document: document,
            defer_validation=True,
        )
        self._receipts.append(captured.receipt)
        self._reviewed_daily_breadth(start, end, universe_hash)
        self._daily_breadth = []
        self._amount_breadth = parse_amount_breadth_acquisitions(
            tuple((r, acquisitions.read_content(r.acquisition_id, "raw")) for r in self._receipts),
            acquisitions.artifacts,
        )
        return amount_breadth_scalars(self._amount_breadth)

    def market_breadth(
        self,
        *,
        start_date: date,
        end_date: date,
        window_days: int = 120,
        output_days: int = 120,
        universe_hash: str | None = None,
        window_inputs_hash: str | None = None,
        amount_inputs_hash: str | None = None,
    ) -> tuple[ContextScalar, ...]:
        if amount_inputs_hash is not None:
            if universe_hash is None or window_inputs_hash is not None:
                raise ValueError("breadth_amount_inputs_invalid")
            return self._reviewed_amount_breadth(
                start_date, end_date, universe_hash, amount_inputs_hash
            )
        if window_inputs_hash is not None:
            if (
                universe_hash is None
                or window_days != 120
                or type(output_days) is not int
                or output_days < 1
            ):
                raise ValueError("breadth_window_inputs_invalid")
            return self._reviewed_window_breadth(
                start_date, end_date, universe_hash, window_inputs_hash, output_days=output_days
            )
        if universe_hash is not None:
            return self._reviewed_daily_breadth(start_date, end_date, universe_hash)
        if end_date < start_date:
            raise ValueError("tushare_date_range_invalid")
        if window_days < 2 or output_days < 1:
            raise ValueError("tushare_breadth_window_invalid")
        calendar_rows = self._call(
            "trade_cal",
            {
                "exchange": "SSE",
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "is_open": "1",
            },
            ("cal_date", "is_open"),
        )
        trading_days = sorted(
            _compact_date(row.get("cal_date"))
            for row in calendar_rows
            if str(row.get("is_open")) == "1"
        )
        required_days = window_days + output_days - 1
        if len(trading_days) < required_days:
            raise ValueError("tushare_breadth_history_incomplete")
        trading_days = trading_days[-required_days:]
        normalized_prices: dict[str, float] = {}
        price_windows: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window_days))
        outputs: list[ContextScalar] = []
        output_dates = set(trading_days[-output_days:])
        for trading_day in trading_days:
            rows = self._call(
                "daily",
                {"trade_date": trading_day.strftime("%Y%m%d")},
                ("ts_code", "trade_date", "pct_chg", "amount"),
            )
            advances = declines = flats = 0
            advancing_amount = total_amount = 0.0
            new_highs = new_lows = above_ma = eligible_ma = 0
            for row in rows:
                if _compact_date(row.get("trade_date")) != trading_day:
                    raise ValueError("tushare_breadth_trade_date_mismatch")
                ts_code = _required_text(row.get("ts_code"), "tushare_breadth_code_missing")
                pct_change = _number(row.get("pct_chg"))
                amount = _number(row.get("amount"))
                if pct_change is None or amount is None or amount < 0:
                    continue
                if pct_change > 0:
                    advances += 1
                    advancing_amount += amount
                elif pct_change < 0:
                    declines += 1
                else:
                    flats += 1
                total_amount += amount
                previous = normalized_prices.get(ts_code, 1.0)
                normalized = previous * (1.0 + pct_change / 100.0)
                normalized_prices[ts_code] = normalized
                window = price_windows[ts_code]
                window.append(normalized)
                if len(window) == window_days:
                    eligible_ma += 1
                    tolerance = max(abs(normalized) * 1e-12, 1e-12)
                    if normalized >= max(window) - tolerance:
                        new_highs += 1
                    if normalized <= min(window) + tolerance:
                        new_lows += 1
                    if normalized > sum(window) / window_days:
                        above_ma += 1
            if trading_day not in output_dates:
                continue
            if advances + declines + flats == 0 or eligible_ma == 0 or total_amount <= 0:
                raise ValueError("tushare_breadth_observations_incomplete")
            measures = (
                ("CN_EQ_ADV_DEC", "advances", float(advances), "count"),
                ("CN_EQ_ADV_DEC", "declines", float(declines), "count"),
                ("CN_EQ_ADV_DEC", "flats", float(flats), "count"),
                ("CN_EQ_ADV_DEC", "net", float(advances - declines), "count"),
                ("CN_EQ_AD_RATIO", "advance_decline_ratio", advances / max(declines, 1), "ratio"),
                ("CN_EQ_NEW_HIGH_LOW_120", "new_highs", float(new_highs), "count"),
                ("CN_EQ_NEW_HIGH_LOW_120", "new_lows", float(new_lows), "count"),
                ("CN_EQ_ABOVE_MA120", "above_ma_share", 100.0 * above_ma / eligible_ma, "percent"),
                (
                    "CN_EQ_ADV_AMOUNT_SHARE",
                    "advancing_amount_share",
                    100.0 * advancing_amount / total_amount,
                    "percent",
                ),
            )
            for metric_id, measure, value, unit in measures:
                outputs.append(
                    _business_day_scalar(
                        metric_id=metric_id,
                        api_name="daily_breadth",
                        source_field=measure,
                        business_date=trading_day,
                        dimensions={
                            "measure": measure,
                            "universe": "point_in_time_traded_a_shares",
                        },
                        value=value,
                        unit=unit,
                    )
                )
        return tuple(outputs)

    def acquire_futures_inputs(
        self,
        paths: RuntimePaths,
        *,
        products: tuple[str, ...],
        start_date: date,
        end_date: date,
        evidence_hash: str | None = None,
    ) -> FuturesInputAcquisition:
        from pring_cycle.futures_inputs import acquire_futures_inputs

        return acquire_futures_inputs(
            paths,
            request=lambda payload: self._transport({**payload, "token": self._token}),
            products=products,
            start_date=start_date,
            end_date=end_date,
            evidence_hash=evidence_hash,
        )

    def commodity_basket(
        self,
        *,
        start_date: date,
        end_date: date,
        output_days: int = 120,
    ) -> tuple[ContextScalar, ...]:
        if end_date < start_date or output_days < 1:
            raise ValueError("tushare_date_range_invalid")
        returns_by_code: dict[str, dict[date, float]] = {}
        for source_code in sorted(
            code for codes in FUTURES_SLEEVE_CODES.values() for code in codes
        ):
            rows = self._call(
                "fut_daily",
                {
                    "ts_code": source_code,
                    "start_date": start_date.strftime("%Y%m%d"),
                    "end_date": end_date.strftime("%Y%m%d"),
                },
                ("ts_code", "trade_date", "close", "pre_close"),
            )
            code_returns: dict[date, float] = {}
            for row in rows:
                if str(row.get("ts_code")) != source_code:
                    raise ValueError("tushare_futures_basket_identity_mismatch")
                close = _number(row.get("close"))
                previous = _number(row.get("pre_close"))
                if close is None or previous is None or previous <= 0:
                    continue
                code_returns[_compact_date(row.get("trade_date"))] = close / previous - 1.0
            returns_by_code[source_code] = code_returns
        common_dates = sorted(
            set.intersection(*(set(values) for values in returns_by_code.values()))
        )
        if len(common_dates) < output_days:
            raise ValueError("tushare_futures_basket_history_incomplete")
        index_level = 1000.0
        scalars: list[ContextScalar] = []
        for trading_day in common_dates:
            sleeve_returns = {
                sleeve: sum(returns_by_code[code][trading_day] for code in codes) / len(codes)
                for sleeve, codes in FUTURES_SLEEVE_CODES.items()
            }
            basket_return = sum(
                FUTURES_SLEEVE_WEIGHTS[sleeve] * value for sleeve, value in sleeve_returns.items()
            )
            index_level *= 1.0 + basket_return
            if trading_day not in set(common_dates[-output_days:]):
                continue
            scalars.append(
                _business_day_scalar(
                    metric_id="CN_COMMODITY_EX_HOG_BASKET",
                    api_name="fut_daily_basket",
                    source_field="weighted_return_index",
                    business_date=trading_day,
                    dimensions={"formula_version": "ex-hog-basket-v0001"},
                    value=index_level,
                    unit="index_points",
                )
            )
            for sleeve, sleeve_return in sleeve_returns.items():
                scalars.append(
                    _business_day_scalar(
                        metric_id="CN_COMMODITY_SLEEVE_CONTRIBUTION",
                        api_name="fut_daily_basket",
                        source_field="weighted_daily_contribution",
                        business_date=trading_day,
                        dimensions={
                            "formula_version": "ex-hog-basket-v0001",
                            "sleeve": sleeve,
                        },
                        value=100.0 * FUTURES_SLEEVE_WEIGHTS[sleeve] * sleeve_return,
                        unit="percentage_points",
                    )
                )
        return tuple(scalars)

    def _call(
        self,
        api_name: str,
        params: dict[str, str],
        fields: tuple[str, ...],
    ) -> tuple[dict[str, object], ...]:
        self._network_requests += 1
        payload = {
            "api_name": api_name,
            "fields": ",".join(fields),
            "params": params,
            "token": self._token,
        }

        def parse(response: bytes | dict[str, Any]) -> tuple[dict[str, object], ...]:
            document = json.loads(response) if isinstance(response, bytes) else response
            if not isinstance(document, dict) or int(document.get("code", -1)) != 0:
                raise ValueError("tushare_source_failed")
            rows = _response_rows(document, required_fields=fields)
            _validate_response_periods(rows, params)
            return rows

        if self._acquisitions is None:
            return parse(self._transport(payload))

        def fetch() -> bytes:
            response = self._transport(payload)
            if not isinstance(response, bytes):
                raise ValueError("acquisition_raw_response_bytes_required")
            return response

        acquisitions = self._acquisitions

        def acquire(on_started: Callable[[str], None] | None) -> ContextRows:
            acquired = acquisitions.capture(
                provider="tushare",
                api_name=api_name,
                parameters=params,
                fields=",".join(fields),
                parser_version=(
                    "tushare-gdp-parser-v0003"
                    if api_name == "cn_gdp"
                    else "tushare-context-parser-v0002"
                ),
                fetch=fetch,
                parse=parse,
                normalize=lambda rows: rows,
                defer_validation=True,
                on_started=on_started,
            )
            self._receipts.append(acquired.receipt)
            return acquired.value

        if self._request_wrapper is not None:
            return self._request_wrapper(api_name, params, fields, acquire)
        return acquire(None)

    def _post(self, payload: dict[str, Any]) -> bytes:
        request = Request(
            TUSHARE_ENDPOINT,
            data=_canonical_json(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            return bytes(response.read())


def _require_breadth_scalar_match(
    scalars: tuple[ContextScalar, ...],
    expected: tuple[ContextScalar, ...],
    *,
    definition_version: str,
    family: str,
) -> None:
    if any(s.definition_version not in (None, definition_version) for s in scalars):
        raise ValueError(f"breadth_{family}_scalar_definition_mismatch")
    outputs = tuple(replace(s, definition_version=None, acquisition_ids=()) for s in scalars)
    if sorted(_canonical_json(asdict(s)) for s in outputs) != sorted(
        _canonical_json(asdict(s)) for s in expected
    ):
        raise ValueError(f"breadth_{family}_scalar_values_mismatch")


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
    # Missing publication evidence stays unknown. A fetch time cannot establish
    # when the market first had access to the observation or its revision.
    repository = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt_by_id = {
        identity: acquisitions.get(identity)
        for identity in {identity for scalar in scalars for identity in scalar.acquisition_ids}
    }
    claims: list[SourceClaimInput] = []
    stored_by_input: list[StoredSourceClaim | None] = []
    for scalar in scalars:
        if scalar.api_name == "cn_gdp" and scalar.source_field in {
            "gdp_yoy",
            "pi_yoy",
            "si_yoy",
            "ti_yoy",
        }:
            raise ValueError("gdp_yoy_period_semantics_unverified")
        if (
            scalar.definition_version is not None
            and scalar.definition_version != definition_version
        ):
            raise ValueError("tushare_context_definition_version_mismatch")
        margin_candidate = definition_version == MARGIN_FINANCING_V0002
        if margin_candidate and (
            scalar.definition_version != MARGIN_FINANCING_V0002
            or scalar.release_at is not None
            or scalar.public_available_at is not None
        ):
            raise ValueError("tushare_margin_candidate_contract_mismatch")
        definition = metric_definition(
            scalar.metric_id,
            definition_version=definition_version,
            database_path=paths.database,
        )
        if (
            definition_version not in BUILTIN_CATALOG_VERSIONS
            and scalar.metric_id == "CN_FUTURES_WARRANTS"
        ):
            expected_warrant_field = {
                "previous_registered_receipts": "pre_vol",
                "registered_receipts": "vol",
                "registered_receipts_change": "vol_chg",
            }.get(scalar.dimensions.get("measure", ""))
            if (scalar.api_name, scalar.source_field) != ("fut_wsr", expected_warrant_field):
                raise ValueError("registered_warrant_source_field_mismatch")
        if definition_version not in BUILTIN_CATALOG_VERSIONS and scalar.metric_id in {
            "CN_DR007",
            "CN_SHIBOR_ON_1W_3M",
        }:
            expected_field = (
                ("repo_daily", "weight")
                if scalar.metric_id == "CN_DR007"
                else (
                    "shibor",
                    {"overnight": "on", "1w": "1w", "3m": "3m"}.get(
                        scalar.dimensions.get("tenor", "")
                    ),
                )
            )
            if (scalar.api_name, scalar.source_field) != expected_field:
                raise ValueError("registered_interbank_source_field_mismatch")
        source_reference = f"tushare:{scalar.api_name}:{scalar.source_field}:{scalar.period_end}"
        base_event_id = f"tushare:{scalar.api_name}:{scalar.period_end}"
        if margin_candidate:
            source_reference = f"{source_reference}:{MARGIN_FINANCING_V0002}"
            base_event_id = f"{base_event_id}:{MARGIN_FINANCING_V0002}"
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
        same_in_definition = bool(
            existing is not None
            and existing.value_state is EvidenceValueState.REPORTED_VALUE
            and existing.value == scalar.value
            and existing.unit == scalar.unit
        )
        explicit_schedule_matches = (
            bool(
                scalar.release_at == existing.release_at
                and scalar.public_available_at == existing.public_available_at
            )
            if existing is not None
            else True
        )
        if (
            existing is not None
            and same_in_definition
            and explicit_schedule_matches
            and not scalar.acquisition_ids
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
        release_at: datetime | None
        public_available_at: datetime | None
        if margin_candidate:
            release_at = None
            public_available_at = None
            release_event_id = (
                base_event_id
                if physical_existing is None
                else _revision_event_id(base_event_id, fetched_at)
            )
        elif scalar.public_available_at is not None and (
            physical_existing is None or physical_same
        ):
            release_at = scalar.release_at
            public_available_at = scalar.public_available_at
            release_event_id = _schedule_event_id(
                base_event_id,
                release_at=release_at,
                public_available_at=public_available_at,
            )
        elif (
            existing is None
            and physical_same
            and physical_existing is not None
            and scalar.release_at == physical_existing.release_at
            and scalar.public_available_at == physical_existing.public_available_at
        ):
            release_event_id = physical_existing.release_event_id
            release_at = physical_existing.release_at
            public_available_at = physical_existing.public_available_at
        else:
            release_event_id = _revision_event_id(
                f"unresolved-publication:{base_event_id}", fetched_at
            )
            release_at = None
            public_available_at = None
        receipts = [receipt_by_id[identity] for identity in scalar.acquisition_ids]
        received_at = max((r.received_at for r in receipts if r.received_at), default=fetched_at)
        validated_at = max((r.validated_at for r in receipts if r.validated_at), default=fetched_at)
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
                fetched_at=received_at,
                available_at=validated_at,
                certification_status=definition.certification_status,
                quality_status="validated",
                acquisition_ids=scalar.acquisition_ids,
            )
        )
        stored_by_input.append(None)
    newly_stored = iter(
        repository.append_source_claims(
            tuple(claims),
            availability_clock=utc_now if all(c.acquisition_ids for c in claims) else None,
        )
        if claims
        else ()
    )
    stored = tuple(item if item is not None else next(newly_stored) for item in stored_by_input)
    metric_ids = tuple(sorted({scalar.metric_id for scalar in scalars}))
    for metric_id in metric_ids:
        metric_scalars = [item for item in scalars if item.metric_id == metric_id]
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare",
            outcome="verified_candidate",
            fetched_at=utc_now()
            if any(item.acquisition_ids for item in metric_scalars)
            else fetched_at,
            acquisition_ids=tuple(
                sorted({identity for item in metric_scalars for identity in item.acquisition_ids})
            ),
            safe_metadata={
                "api_names": ",".join(sorted({item.api_name for item in metric_scalars})),
                "observations": str(len(metric_scalars)),
                "period_end": max(item.period_end for item in metric_scalars),
                "definition_version": definition_version,
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


def _schedule_event_id(
    base_event_id: str,
    *,
    release_at: datetime | None,
    public_available_at: datetime,
) -> str:
    identity = "|".join(
        (
            release_at.isoformat() if release_at is not None else "",
            public_available_at.isoformat(),
        )
    )
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return f"{base_event_id}:schedule:{suffix}"


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
    start_date = target_business_date - timedelta(days=220)
    warrant_request_start = adapter.network_requests
    warrant_scalars = tuple(
        scalar
        for symbol in sorted(WARRANT_SYMBOLS)
        for scalar in adapter.futures_warrants(
            start_date=start_date,
            end_date=target_business_date,
            symbol=symbol,
        )
    )
    observed_warrant_symbols = {scalar.dimensions.get("symbol") for scalar in warrant_scalars}
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
            network_requests=adapter.network_requests - warrant_request_start,
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


def smoke_market_sources(
    adapter: TushareContextAdapter,
    *,
    target_business_date: date,
) -> ContextSourceSmokeResult:
    daily_start = target_business_date - timedelta(days=220)
    breadth_start = target_business_date - timedelta(days=420)
    families = (
        summarize_context_source_smoke(
            "market_indices",
            adapter.market_indices(
                start_date=daily_start,
                end_date=target_business_date,
            ),
            network_requests=len(MARKET_INDEX_IDENTITIES),
        ),
        summarize_context_source_smoke(
            "market_breadth",
            adapter.market_breadth(
                start_date=breadth_start,
                end_date=target_business_date,
            ),
            network_requests=240,
        ),
        summarize_context_source_smoke(
            "margin_financing",
            adapter.margin_financing(
                start_date=daily_start,
                end_date=target_business_date,
            ),
            network_requests=1,
        ),
        summarize_context_source_smoke(
            "index_valuation",
            adapter.index_valuation(
                start_date=daily_start,
                end_date=target_business_date,
            ),
            network_requests=len(VALUATION_INDEX_CODES),
        ),
        summarize_context_source_smoke(
            "commodity_basket",
            adapter.commodity_basket(
                start_date=daily_start,
                end_date=target_business_date,
            ),
            network_requests=sum(len(codes) for codes in FUTURES_SLEEVE_CODES.values()),
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


def _market_index_scalars(metric_id: str, rows: ContextRows) -> tuple[ContextScalar, ...]:
    api_name, source_code = MARKET_INDEX_IDENTITIES[metric_id]
    seen_dates = set()
    scalars = []
    for row in rows:
        if str(row.get("ts_code")) != source_code:
            raise ValueError("tushare_market_index_identity_mismatch")
        trading_day = _compact_date(row.get("trade_date"))
        if trading_day in seen_dates:
            raise ValueError("tushare_market_index_duplicate_day")
        seen_dates.add(trading_day)
        scalars.append(
            _daily_scalar(
                metric_id,
                api_name,
                "close",
                row,
                date_field="trade_date",
                dimensions={"source_code": source_code},
                unit="index_points",
            )
        )
    return tuple(scalars)


def parse_market_index_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> tuple[ContextScalar, ...]:
    """Read the exact index, day and closing points from its captured delivery."""
    identity = (receipt.api_name, receipt.parameters.get("ts_code"))
    metric_id = next(
        (metric for metric, source in MARKET_INDEX_IDENTITIES.items() if source == identity),
        None,
    )
    fields = ("ts_code", "trade_date", "close")
    if (
        metric_id is None
        or receipt.provider != "tushare"
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"ts_code", "start_date", "end_date"}
    ):
        raise ValueError("registered_market_index_acquisition_identity_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(document, required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    return _market_index_scalars(metric_id, rows)


def _valuation_scalars(source_code: str, rows: ContextRows) -> tuple[ContextScalar, ...]:
    seen_dates = set()
    scalars = []
    for row in rows:
        if str(row.get("ts_code")) != source_code:
            raise ValueError("tushare_index_valuation_identity_mismatch")
        trading_day = _compact_date(row.get("trade_date"))
        if trading_day in seen_dates:
            raise ValueError("registered_valuation_duplicate_day")
        seen_dates.add(trading_day)
        for source_field, measure, unit in VALUATION_FIELDS:
            if _number(row.get(source_field)) is None:
                continue
            scalars.append(
                _daily_scalar(
                    "CN_INDEX_VALUATION",
                    "index_dailybasic",
                    source_field,
                    row,
                    date_field="trade_date",
                    dimensions={"index": source_code, "measure": measure},
                    unit=unit,
                )
            )
    return tuple(scalars)


def parse_valuation_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> tuple[ContextScalar, ...]:
    """Rebuild static PE, PB and turnover from the identified index delivery."""
    fields = ("ts_code", "trade_date", *(field for field, _measure, _unit in VALUATION_FIELDS))
    source_code = receipt.parameters.get("ts_code")
    if (
        receipt.provider != "tushare"
        or receipt.api_name != "index_dailybasic"
        or source_code not in VALUATION_INDEX_CODES
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"ts_code", "start_date", "end_date"}
    ):
        raise ValueError("registered_valuation_acquisition_identity_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(document, required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    return _valuation_scalars(receipt.parameters["ts_code"], rows)


def parse_margin_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
) -> tuple[ContextScalar, ...]:
    """Rebuild the two totals only from complete, unique three-exchange deliveries."""
    fields = ("trade_date", "exchange_id", "rzye", "rzmre")
    if (
        receipt.provider != "tushare"
        or receipt.api_name != "margin"
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"start_date", "end_date"}
    ):
        raise ValueError("registered_margin_acquisition_identity_mismatch")
    document = json.loads(raw)
    rows = _response_rows(document, required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    days = tuple(sorted({_compact_date(row["trade_date"]) for row in rows}))
    adapter = TushareContextAdapter("receipt-reparse", transport=lambda _: raw)
    try:
        scalars = adapter.margin_financing_candidate(trading_days=days)
    except ValueError as error:
        if str(error) == "tushare_margin_exchange_coverage_incomplete":
            raise ValueError("registered_margin_exchange_coverage_incomplete") from error
        raise
    return tuple(
        replace(
            scalar,
            dimensions={"measure": scalar.dimensions["measure"], "scope": "all_exchanges"},
            definition_version=None,
        )
        for scalar in scalars
    )


def _parse_monthly_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
    *,
    api_name: str,
    contract: str,
    scalar_fields: tuple[_Field, ...],
) -> tuple[ContextScalar, ...]:
    fields = ("month", *(field.source_field for field in scalar_fields))
    if (
        receipt.state != "validated"
        or receipt.provider != "tushare"
        or receipt.api_name != api_name
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"start_m", "end_m"}
    ):
        raise ValueError(f"registered_{contract}_acquisition_identity_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(document, required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    return _monthly_scalars(api_name, rows, scalar_fields)


def parse_ppi_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> tuple[ContextScalar, ...]:
    """Rebuild the reviewed PPI delivery from its exact API, fields and period range."""
    return _parse_monthly_acquisition(
        receipt,
        raw,
        api_name="cn_ppi",
        contract="ppi",
        scalar_fields=tuple(
            _Field("CN_PPI", field, {"category": category, "measure": measure}, "percent")
            for field, category, measure in TUSHARE_PPI_FIELDS
        ),
    )


def parse_cpi_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> tuple[ContextScalar, ...]:
    """Rebuild headline CPI from cn_cpi without manufacturing publication evidence."""
    return _parse_monthly_acquisition(
        receipt,
        raw,
        api_name="cn_cpi",
        contract="cpi",
        scalar_fields=tuple(
            _Field(
                "CN_CPI_HEADLINE", field, {"category": "headline", "measure": measure}, "percent"
            )
            for field, measure in TUSHARE_CPI_FIELDS
        ),
    )


def parse_pmi_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> tuple[ContextScalar, ...]:
    """Rebuild all PMI siblings from the one exact physical cn_pmi response."""
    return _parse_monthly_acquisition(
        receipt,
        raw,
        api_name="cn_pmi",
        contract="pmi",
        scalar_fields=tuple(
            _Field(metric, field, {"series": series, "measure": "level"}, "diffusion_index_points")
            for field, metric, series in TUSHARE_PMI_FIELDS
        ),
    )


def parse_money_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> tuple[ContextScalar, ...]:
    """Rebuild the four money members shared with the registered PBC contract."""
    return _parse_monthly_acquisition(
        receipt,
        raw,
        api_name="cn_m",
        contract="money",
        scalar_fields=tuple(
            _Field("CN_M1_M2", field, {"aggregate": aggregate, "measure": measure}, unit)
            for field, aggregate, measure, unit in TUSHARE_MONEY_FIELDS
        ),
    )


def tushare_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points: tuple[MetricSeriesPoint, ...],
    *,
    definition_version: str,
    parse: Callable[
        [AcquisitionReceipt, bytes], tuple[ContextScalar, ...]
    ] = parse_margin_acquisition,
) -> set[str]:
    """Keep selected TuShare scalars bound to complete raw and normalized deliveries."""
    selected = {p.selected_claim_id: p for p in points if p.selected_claim_id is not None}
    parsed: dict[str, list[dict[str, Any]] | None] = {}
    valid = set()
    for claim_id, inputs in repository.source_claim_acquisitions_many(tuple(selected)).items():
        if not inputs:
            continue
        point = selected[claim_id]
        claim = next(c for c in point.claims if c.claim_id == claim_id)
        identities = {item.receipt.acquisition_id for item in inputs}
        try:
            for item in inputs:
                identity = item.receipt.acquisition_id
                if identity not in parsed:
                    parsed[identity] = None
                    scalars = parse(item.receipt, item.raw)
                    normalized = json.loads(item.normalized)
                    if not isinstance(normalized, list):
                        raise ValueError("registered_tushare_normalized_mismatch")
                    economic = []
                    for entry in normalized:
                        if (
                            not isinstance(entry, dict)
                            or entry.get("definition_version") not in (None, definition_version)
                            or not isinstance(entry.get("acquisition_ids"), list)
                            or identity not in entry["acquisition_ids"]
                        ):
                            raise ValueError("registered_tushare_normalized_mismatch")
                        economic.append(
                            _canonical_json(
                                {
                                    **entry,
                                    "release_at": None,
                                    "public_available_at": None,
                                    "acquisition_ids": [],
                                    "definition_version": None,
                                }
                            )
                        )
                    if sorted(economic) != sorted(_canonical_json(asdict(s)) for s in scalars):
                        raise ValueError("registered_tushare_normalized_mismatch")
                    parsed[identity] = normalized
                normalized = parsed[identity]
                if normalized is None:
                    raise ValueError("registered_tushare_normalized_mismatch")
                matches = [
                    entry
                    for entry in normalized
                    if (
                        entry["period_start"] == point.period_start
                        and entry["period_end"] == point.period_end
                        and entry["dimensions"] == point.dimensions
                        and entry["value"] == claim.value
                        and entry["unit"] == claim.unit
                        and set(entry["acquisition_ids"]) == identities
                        and claim.source_reference
                        == f"tushare:{entry['api_name']}:{entry['source_field']}:{point.period_end}"
                        and all(
                            (
                                datetime.fromisoformat(entry[field])
                                if entry[field] is not None
                                else None
                            )
                            == getattr(claim, field)
                            for field in ("release_at", "public_available_at")
                        )
                    )
                ]
                if len(matches) != 1 or claim.provider != "tushare":
                    raise ValueError("registered_tushare_claim_mismatch")
        except (LookupError, TypeError, ValueError, OSError):
            continue
        valid.add(claim_id)
    return valid


def parse_interbank_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> tuple[ContextScalar, ...]:
    """Rebuild the economic fields from one genuine bank-rate API response."""
    fields = {
        "repo_daily": ("ts_code", "trade_date", "repo_maturity", "weight"),
        "shibor": ("date", "on", "1w", "3m"),
    }
    if (
        receipt.state != "validated"
        or receipt.provider != "tushare"
        or receipt.api_name not in fields
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != ",".join(fields[receipt.api_name])
        or receipt.received_at is None
        or receipt.validated_at is None
    ):
        raise ValueError("interbank_acquisition_identity_mismatch")
    parameters = receipt.parameters
    expected = {"start_date", "end_date"}
    if receipt.api_name == "repo_daily":
        expected.add("ts_code")
        if parameters.get("ts_code") != "DR007.IB":
            raise ValueError("interbank_acquisition_identity_mismatch")
    if set(parameters) != expected:
        raise ValueError("interbank_acquisition_identity_mismatch")
    start, end = (_compact_date(parameters[field]) for field in ("start_date", "end_date"))
    if start > end or any(
        value.strftime("%Y%m%d") != parameters[field]
        for field, value in (("start_date", start), ("end_date", end))
    ):
        raise ValueError("interbank_acquisition_period_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or int(document.get("code", -1)) != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(document, required_fields=fields[receipt.api_name])
    _validate_response_periods(rows, parameters)
    return _transmission_scalars(
        rows if receipt.api_name == "repo_daily" else (),
        rows if receipt.api_name == "shibor" else (),
    )


def _transmission_scalars(
    repo_rows: tuple[dict[str, object], ...], shibor_rows: tuple[dict[str, object], ...]
) -> tuple[ContextScalar, ...]:
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
) -> ContextScalar:
    business_date = _compact_date(row.get(date_field))
    value = _number(row.get(source_field))
    if value is None:
        raise ValueError("tushare_context_value_missing")
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
    )


def _business_day_scalar(
    *,
    metric_id: str,
    api_name: str,
    source_field: str,
    business_date: date,
    dimensions: dict[str, str],
    value: float,
    unit: str,
) -> ContextScalar:
    if not isfinite(value):
        raise ValueError("tushare_context_value_invalid")
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
    )


@dataclass(frozen=True)
class WarrantAcquisition:
    symbol: str
    scalars: tuple[ContextScalar, ...]
    current_member_count: int


def parse_warrant_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
    normalized: bytes,
    *,
    period: str,
    definition_version: str,
) -> WarrantAcquisition:
    """Reparse one complete physical delivery, including its warehouse denominator."""
    if (
        receipt.provider != "tushare"
        or receipt.api_name != "fut_wsr"
        or receipt.parser_version != "tushare-context-parser-v0002"
        or set(receipt.parameters) != {"start_date", "end_date", "symbol"}
    ):
        raise ValueError("tushare_warrant_acquisition_contract_invalid")
    source_symbol = receipt.parameters["symbol"]
    symbol = "TA" if source_symbol == "PTA" else source_symbol
    if symbol not in WARRANT_SYMBOLS or source_symbol == "TA":
        raise ValueError("tushare_warrant_symbol_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(
        document,
        required_fields=(
            "trade_date",
            "symbol",
            "warehouse",
            "pre_vol",
            "vol",
            "vol_chg",
            "unit",
            "exchange",
        ),
    )
    _validate_response_periods(rows, receipt.parameters)
    if len(rows) >= _FUTURES_WARRANT_RESPONSE_LIMIT:
        raise ValueError("tushare_warrant_response_truncated")
    scalars = _warrant_scalars(
        rows,
        symbol,
        source_symbol,
        (
            ("pre_vol", "previous_registered_receipts"),
            ("vol", "registered_receipts"),
            ("vol_chg", "registered_receipts_change"),
        ),
    )
    normalized_scalars = json.loads(normalized)
    if not isinstance(normalized_scalars, list) or len(normalized_scalars) != len(scalars):
        raise ValueError("tushare_warrant_normalized_mismatch")
    expected = sorted(_canonical_json(asdict(scalar)) for scalar in scalars)
    actual = []
    verified: list[ContextScalar] = []
    for item in normalized_scalars:
        if not isinstance(item, dict):
            raise ValueError("tushare_warrant_normalized_mismatch")
        if item.get("definition_version") not in (None, definition_version):
            raise ValueError("tushare_warrant_normalized_mismatch")
        acquisition_ids = item.get("acquisition_ids")
        if (
            not isinstance(acquisition_ids, list)
            or not all(isinstance(identity, str) for identity in acquisition_ids)
            or receipt.acquisition_id not in acquisition_ids
        ):
            raise ValueError("tushare_warrant_normalized_mismatch")
        times: dict[str, datetime | None] = {}
        for field in ("release_at", "public_available_at"):
            if field not in item:
                raise ValueError("tushare_warrant_normalized_mismatch")
            value = item[field]
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("tushare_warrant_normalized_mismatch")
                value = datetime.fromisoformat(value)
                if value.tzinfo is None:
                    raise ValueError("tushare_warrant_normalized_mismatch")
            times[field] = value
        # Raw data determines economic fields. The recorded time assertions must
        # separately match the selected claim; they do not certify source timing.
        economic = {
            **item,
            "release_at": None,
            "public_available_at": None,
            "acquisition_ids": [],
            "definition_version": None,
        }
        actual.append(_canonical_json(economic))
        verified.append(
            ContextScalar(**{**item, **times, "acquisition_ids": tuple(acquisition_ids)})
        )
    if sorted(actual) != expected:
        raise ValueError("tushare_warrant_normalized_mismatch")
    return WarrantAcquisition(
        symbol,
        tuple(scalar for scalar in verified if scalar.period_end == period),
        sum(_compact_date(row.get("trade_date")).isoformat() == period for row in rows),
    )


def _warrant_scalars(
    rows: ContextRows,
    normalized_symbol: str,
    source_symbol: str,
    fields: tuple[tuple[str, str], ...],
) -> tuple[ContextScalar, ...]:
    scalars: list[ContextScalar] = []
    identities: set[tuple[date, str, str, str]] = set()
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
        identity = (_compact_date(row.get("trade_date")), row_symbol, warehouse, exchange)
        if identity in identities:
            raise ValueError("tushare_warrant_duplicate_member")
        identities.add(identity)
        source_unit = _required_text(row.get("unit"), "tushare_warrant_unit_missing")
        try:
            unit = _WARRANT_UNITS[source_unit]
        except KeyError as error:
            raise ValueError("tushare_warrant_unit_unknown") from error
        for source_field, measure in fields:
            value = _number(row.get(source_field))
            if value is None:
                continue
            if source_field in {"pre_vol", "vol"} and value < 0:
                raise ValueError("tushare_warrant_quantity_negative")
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


def _warrant_input_identity(scalar: ContextScalar) -> tuple[str, str, str, str, str, str, float]:
    return (
        scalar.dimensions.get("symbol", ""),
        scalar.period_end,
        scalar.dimensions.get("warehouse", ""),
        scalar.dimensions.get("exchange", ""),
        scalar.source_field,
        scalar.unit,
        scalar.value,
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
    if any(not isinstance(item, str) or not item for item in fields) or len(set(fields)) != len(
        fields
    ):
        raise ValueError("tushare_response_schema_invalid")
    names = fields
    if any(name not in names for name in required_fields):
        raise ValueError("tushare_response_required_field_missing")
    rows = []
    for item in items:
        if not isinstance(item, list) or len(item) != len(names):
            raise ValueError("tushare_response_row_invalid")
        rows.append(dict(zip(names, item, strict=True)))
    return tuple(rows)


def _validate_response_periods(
    rows: tuple[dict[str, object], ...], parameters: dict[str, str]
) -> None:
    if "start_m" in parameters:
        periods = [_month_value(str(row.get("month"))) for row in rows]
        if len(periods) != len(set(periods)) or any(
            period < parameters["start_m"] or period > parameters["end_m"] for period in periods
        ):
            raise ValueError("tushare_response_period_mismatch")
    elif "start_q" in parameters:
        periods = [_quarter_value(str(row.get("quarter"))) for row in rows]
        if len(periods) != len(set(periods)) or any(
            period < parameters["start_q"] or period > parameters["end_q"] for period in periods
        ):
            raise ValueError("tushare_response_period_mismatch")
    elif "start_date" in parameters or "trade_date" in parameters:
        start = _compact_date(parameters.get("start_date", parameters.get("trade_date")))
        end = _compact_date(parameters.get("end_date", parameters.get("trade_date")))
        for row in rows:
            for field in ("trade_date", "cal_date", "date"):
                if field in row and not start <= _compact_date(row[field]) <= end:
                    raise ValueError("tushare_response_period_mismatch")


def _inclusive_date_chunks(
    start_date: date,
    end_date: date,
    *,
    chunk_days: int,
) -> tuple[tuple[date, date], ...]:
    if chunk_days < 1:
        raise ValueError("tushare_date_chunk_days_invalid")
    chunks: list[tuple[date, date]] = []
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=chunk_days - 1), end_date)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return tuple(chunks)


def _date_chunk_count(start_date: date, end_date: date, *, chunk_days: int) -> int:
    return len(_inclusive_date_chunks(start_date, end_date, chunk_days=chunk_days))


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
    return json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
