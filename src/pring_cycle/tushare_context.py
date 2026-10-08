from __future__ import annotations

import calendar
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any
from urllib.request import Request, build_opener

from pring_cycle.acquisition import (
    AcquisitionReceipt,
    AcquisitionRepository,
    SourceFailed,
    utc_now,
)
from pring_cycle.acquisition_outcome import (
    LOCAL_FAILED,
    SUCCEEDED,
    attempt_details,
    capture_failure,
    ingest_failure,
)
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
from pring_cycle.http_transport import NoRedirect
from pring_cycle.metric_contracts import CZCE_WARRANT_SYMBOLS, official_source_members
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import (
    TUSHARE_ENDPOINT,
    tushare_quota_refused,
    tushare_refusal,
)
from pring_cycle.source_families import (
    TUSHARE_CPI_FIELDS,
    TUSHARE_GDP_FIELDS,
    TUSHARE_MONEY_FIELDS,
    TUSHARE_OFFICIAL_DELIVERY_CODES,
    TUSHARE_PMI_FIELDS,
    TUSHARE_PPI_FIELDS,
    TUSHARE_SF_TOTAL_FIELDS,
)
from pring_cycle.tushare_quota import TushareCallNotAttempted

Transport = Callable[[dict[str, Any]], dict[str, Any] | bytes]

WARRANT_SYMBOLS = frozenset({"CU", "RB", "PP", "CF", "TA", "RU", "SP", "SC"})
# TA and CF come from CZCE's own report instead, with no TuShare fallback (ADR-0032).
TUSHARE_WARRANT_SYMBOLS = WARRANT_SYMBOLS - CZCE_WARRANT_SYMBOLS
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
_WARRANT_UNITS = {
    "吨": "tonne",
    "千克": "kilogram",
    "公斤": "kilogram",
    "张": "sheet",
    "手": "lot",
    "桶": "barrel",
}


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
class ContextDelivery:
    scalars: tuple[ContextScalar, ...]
    rejected_fields: tuple[dict[str, str], ...]


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
    period_kind: str = "month"


ContextRows = tuple[dict[str, object], ...]
ContextRequestOperation = Callable[[Callable[[str], None] | None], ContextRows]
ContextRequestWrapper = Callable[
    [str, dict[str, str], tuple[str, ...], ContextRequestOperation], ContextRows
]


class ContextObservationsMissingError(ValueError):
    """A structurally parsed delivery contains no scalar observations.

    ``completeness`` says why (ticket 18): ``nothing_new`` when its producer found every
    wanted day held already, ``source_empty`` when the source delivered none.
    """

    def __init__(self, completeness: str = "source_empty") -> None:
        super().__init__("tushare_context_observations_missing")
        self.completeness = completeness


class TushareSourceError(SourceFailed, ValueError):
    """TuShare answered without data: a non-zero code such as a permission or rate limit.

    A source failure carrying TuShare's code (ticket 18); still a ValueError to the callers
    that caught it as one.
    """


class ContextRequestFailed(Exception):
    """A request wrapper's own report that a request failed, raised in place of what the
    source or the response said; the adapter records that instead (ticket 18)."""


class OriginalUnreadable(RuntimeError):
    """This system could not read back an original it stored: its own failure, never the
    response's (ticket 18)."""


class ContextIngestRejectedError(ValueError):
    """The responses passed their structure check; the evidence store refused the values."""


class TushareContextAdapter:
    def __init__(self, token: str, *, transport: Transport | None = None) -> None:
        if not token:
            raise ValueError("tushare_token_required")
        self._token = token
        self._transport = transport or self._post
        self._network_requests = 0
        self._acquisitions: AcquisitionRepository | None = None
        self._receipts: list[AcquisitionReceipt] = []
        self._started: list[str] = []
        self._failure: Exception | None = None
        self._request_wrapper: ContextRequestWrapper | None = None
        self._field_rejections: list[dict[str, str]] = []

    def acquire_scalars(
        self,
        paths: RuntimePaths,
        retrieve: Callable[[], tuple[ContextScalar, ...]],
        *,
        definition_version: str = METRIC_CATALOG_VERSION,
        request_wrapper: ContextRequestWrapper | None = None,
        metric_ids: tuple[str, ...] = (),
        details: Mapping[str, str] | None = None,
    ) -> ContextIngestionResult:
        """Acquire, check and store one family's delivery.

        Given the ``metric_ids`` it was asked for, it also records how the acquisition ended
        for each where it ended (ticket 18): a failure at its step with the source's code or
        the refusing rule, an empty delivery, a metric the delivery left out. ``details`` go
        on each record (the family, a warrant symbol, the request's dates).
        """
        if self._acquisitions is not None:
            raise ValueError("context_acquisition_already_running")
        self._acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        self._receipts = []
        self._started = []
        self._failure = None
        self._request_wrapper = request_wrapper
        self._field_rejections = []
        stage = "acquire"
        try:
            scalars = retrieve()
            if not self._receipts:
                raise ValueError("context_acquisition_receipts_missing")
            if not scalars and self._field_rejections:
                # Nothing delivered because the rules refused every field: a refused
                # response, not an empty delivery (ticket 18).
                raise ValueError(
                    ",".join(sorted({item["reason"] for item in self._field_rejections}))
                )
            if definition_version not in BUILTIN_CATALOG_VERSIONS:
                family_contracts = (
                    ("margin", {"CN_MARGIN_BALANCE"}, {"margin"}, parse_margin_acquisition),
                    (
                        "margin_sse_szse",
                        {"CN_MARGIN_BALANCE_SSE_SZSE"},
                        {"margin"},
                        parse_margin_sse_szse_acquisition,
                    ),
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
                for family, family_metrics, api_names, parse_scalars in family_contracts:
                    outputs = tuple(
                        replace(
                            scalar,
                            release_at=None,
                            public_available_at=None,
                            definition_version=None,
                            acquisition_ids=(),
                        )
                        for scalar in scalars
                        if scalar.metric_id in family_metrics
                    )
                    if not outputs:
                        continue
                    parsed_inputs = tuple(
                        scalar
                        for receipt in self._receipts
                        if receipt.api_name in api_names
                        for scalar in parse_scalars(
                            receipt,
                            self._original(receipt),
                        )
                    )
                    if sorted(_canonical_json(asdict(s)) for s in parsed_inputs) != sorted(
                        _canonical_json(asdict(s)) for s in outputs
                    ):
                        raise ValueError(f"registered_{family}_acquisition_values_mismatch")
            warrant_inputs = self._warrant_receipt_inputs()
            gdp_deliveries = {
                receipt.acquisition_id: _gdp_delivery(
                    _gdp_acquisition_rows(receipt, self._original(receipt))
                )
                for receipt in self._receipts
                if receipt.api_name == "cn_gdp"
            }
            linked = []
            for scalar in scalars:
                matching = [r for r in self._receipts if r.api_name == scalar.api_name]
                inputs = matching or self._receipts
                if scalar.api_name == "cn_gdp":
                    inputs = [
                        receipt
                        for receipt in matching
                        if any(
                            output.period_end == scalar.period_end
                            for output in gdp_deliveries[receipt.acquisition_id].scalars
                        )
                    ]
                    if not inputs:
                        raise ValueError("registered_gdp_acquisition_member_missing")
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
                if scalar.api_name == "breadth":
                    # A day's figures come from the SSE calendar's responses, which the scalar
                    # names already, that day's deliveries and the listings.
                    day = scalar.period_end.replace("-", "")
                    inputs = [
                        receipt
                        for receipt in self._receipts
                        if receipt.api_name == "stock_basic"
                        or receipt.parameters.get("trade_date") == day
                    ]
                    linked.append(
                        replace(
                            scalar,
                            acquisition_ids=(
                                *scalar.acquisition_ids,
                                *(receipt.acquisition_id for receipt in inputs),
                            ),
                        )
                    )
                    continue
                if scalar.metric_id == "CN_FUTURES_WARRANTS" and scalar.api_name == "fut_wsr":
                    inputs = warrant_inputs.get(_warrant_input_identity(scalar), [])
                    if not inputs:
                        raise ValueError("tushare_warrant_acquisition_member_missing")
                linked.append(
                    replace(scalar, acquisition_ids=tuple(r.acquisition_id for r in inputs))
                )
            stage = "store"  # what the checks passed is stored: a failure here is local
            normalized: object = [asdict(s) for s in linked]
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
                accepted = [
                    asdict(s) for s in linked if receipt.acquisition_id in s.acquisition_ids
                ]
                receipt_document: object = accepted
                rejected = [
                    item for item in self._field_rejections if item["api_name"] == receipt.api_name
                ]
                if receipt.api_name == "cn_gdp":
                    rejected = list(gdp_deliveries[receipt.acquisition_id].rejected_fields)
                if rejected:
                    receipt_document = {
                        "accepted_scalars": accepted,
                        "rejected_fields": rejected,
                    }
                if receipt.api_name == "fut_wsr":
                    receipt_document = {
                        "accepted_scalars": accepted,
                        "warrant_reconciliation": _warrant_receipt_reconciliation(
                            receipt,
                            self._original(receipt),
                        ),
                    }
                self._acquisitions.complete_validation(
                    receipt.acquisition_id,
                    receipt_document,
                    normalized_scalars=len(accepted),
                )
            stage = "ingest"
            try:
                result = ingest_context_scalars(
                    paths,
                    tuple(linked),
                    fetched_at=utc_now(),
                    definition_version=definition_version,
                    rejected_fields=tuple(self._field_rejections),
                    details=details,
                )
            except ContextObservationsMissingError:
                raise
            except ValueError as error:
                # Only the registered contract refusing the values; a failure of this system
                # while storing them is no refusal (ticket 18).
                for receipt in self._receipts:
                    self._acquisitions.record_ingest_result(receipt.acquisition_id, error)
                raise ContextIngestRejectedError(str(error)) from error
            for receipt in self._receipts:
                self._acquisitions.record_ingest_result(receipt.acquisition_id, None)
            self._record(
                paths,
                tuple(item for item in metric_ids if item not in result.metric_ids),
                SUCCEEDED,
                attempt_details(step="structure", completeness="source_empty"),
                definition_version=definition_version,
                details=details,
            )
            return replace(result, rejected_field_count=len(self._field_rejections))
        except Exception as error:
            # A response its rules refused was checked; an empty delivery, or a failure of
            # the source or of this system (storing what passed included), was not.
            checked = (
                stage == "acquire"
                and isinstance(error, ValueError)
                and not isinstance(error, ContextObservationsMissingError | SourceFailed)
            )
            for receipt in self._receipts:
                self._acquisitions.fail_validation(receipt.acquisition_id, error, checked=checked)
            if isinstance(error, ContextObservationsMissingError):
                outcome, recorded = (
                    SUCCEEDED,
                    attempt_details(step="structure", completeness=error.completeness),
                )
            elif stage == "store" or isinstance(error, OriginalUnreadable):
                outcome, recorded = (
                    LOCAL_FAILED,
                    attempt_details(
                        step="local", error_type=type(error).__name__, reason=str(error)[:300]
                    ),
                )
            elif stage == "ingest":
                outcome, recorded = ingest_failure(
                    error.__cause__
                    if isinstance(error, ContextIngestRejectedError)
                    and isinstance(error.__cause__, Exception)
                    else error
                )
            else:
                # What the source or the response said, before a request wrapper translated
                # it into an exception of its own; any other error is read as it is.
                translated = self._failure is not None and (
                    error is self._failure or isinstance(error, ContextRequestFailed)
                )
                outcome, recorded = capture_failure(
                    self._failure if translated and self._failure is not None else error
                )
            self._record(
                paths,
                metric_ids,
                outcome,
                recorded,
                definition_version=definition_version,
                details=details,
            )
            raise
        finally:
            self._acquisitions = None
            self._receipts = []
            self._started = []
            self._failure = None
            self._request_wrapper = None
            self._field_rejections = []

    def _original(self, receipt: AcquisitionReceipt) -> bytes:
        assert self._acquisitions is not None
        try:
            return self._acquisitions.read_content(receipt.acquisition_id, "raw")
        except (LookupError, OSError, ValueError) as error:
            raise OriginalUnreadable(str(error)) from error

    def _record(
        self,
        paths: RuntimePaths,
        metric_ids: tuple[str, ...],
        outcome: str,
        recorded: Mapping[str, str],
        *,
        definition_version: str,
        details: Mapping[str, str] | None,
    ) -> None:
        repository = EvidenceRepository(paths.database)
        recorded_at = utc_now()
        for metric_id in metric_ids:
            repository.record_retrieval_attempt(
                metric_id=metric_id,
                channel="tushare",
                outcome=outcome,
                fetched_at=recorded_at,
                acquisition_ids=tuple(self._started),
                safe_metadata={
                    **(details or {}),
                    "definition_version": definition_version,
                    **recorded,
                },
            )

    @property
    def network_requests(self) -> int:
        return self._network_requests

    def _warrant_receipt_inputs(
        self,
    ) -> dict[tuple[str, str, str, str, str, str, float], list[AcquisitionReceipt]]:
        """Index only complete physical warrant responses by the warehouse totals they give."""
        result: dict[tuple[str, str, str, str, str, str, float], list[AcquisitionReceipt]] = {}
        assert self._acquisitions is not None
        for receipt in self._receipts:
            if receipt.api_name != "fut_wsr":
                continue
            document = json.loads(self._original(receipt))
            rows = _response_rows(document, required_fields=tuple(receipt.fields.split(",")))
            if len(rows) >= _FUTURES_WARRANT_RESPONSE_LIMIT:
                continue
            source_symbol = receipt.parameters["symbol"]
            symbol = "TA" if source_symbol == "PTA" else source_symbol
            for member in _warrant_members(rows, source_symbol, _WARRANT_FIELDS).values():
                for field, value in member.values.items():
                    identity = (
                        symbol,
                        member.business_date.isoformat(),
                        member.warehouse,
                        member.exchange,
                        field,
                        member.unit,
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
            *_official_ppi_members(_monthly_scalars("cn_ppi", ppi, ppi_fields)),
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

    def social_financing_total(
        self, *, start_month: str, end_month: str
    ) -> tuple[ContextScalar, ...]:
        """Collect the registered total's annual flow and month-end stock members."""
        fields = _social_financing_total_fields()
        rows = self._call(
            "sf_month",
            {"start_m": _month_value(start_month), "end_m": _month_value(end_month)},
            ("month", *(field.source_field for field in fields)),
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
        source_symbol = normalized_symbol = symbol.upper()
        if normalized_symbol not in TUSHARE_WARRANT_SYMBOLS:
            raise ValueError("tushare_warrant_symbol_not_allowed")
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
        rows = self._call(
            "cn_gdp",
            {"start_q": start_value, "end_q": end_value},
            (
                "quarter",
                *(field for _aggregate, level, yoy in TUSHARE_GDP_FIELDS for field in (level, yoy)),
            ),
        )
        delivery = _gdp_delivery(rows)
        if self._acquisitions is not None:
            self._field_rejections.extend(delivery.rejected_fields)
        return delivery.scalars

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
        totals: dict[date, dict[str, float]] = defaultdict(
            lambda: {"financing_balance": 0.0, "financing_buy_amount": 0.0}
        )
        seen: set[tuple[date, str]] = set()
        for row in rows:
            trading_day = _compact_date(row.get("trade_date"))
            exchange = _required_text(
                row.get("exchange_id"),
                "tushare_margin_exchange_missing",
            )
            if exchange not in {"SSE", "SZSE", "BSE"}:
                raise ValueError("tushare_margin_exchange_invalid")
            if (trading_day, exchange) in seen:
                raise ValueError("tushare_margin_duplicate_exchange_day")
            seen.add((trading_day, exchange))
            balance = _number(row.get("rzye"))
            buy_amount = _number(row.get("rzmre"))
            if balance is None or buy_amount is None:
                raise ValueError("tushare_margin_value_missing")
            totals[trading_day]["financing_balance"] += balance
            totals[trading_day]["financing_buy_amount"] += buy_amount
        published = _published_margin_days(seen, {"SSE", "SZSE", "BSE"}, requested_end=end_date)
        scalars: list[ContextScalar] = []
        for trading_day, measures in sorted(totals.items()):
            if trading_day not in published:
                continue
            for measure, value in measures.items():
                scalars.append(
                    _business_day_scalar(
                        metric_id="CN_MARGIN_BALANCE",
                        api_name="margin",
                        source_field=measure,
                        business_date=trading_day,
                        dimensions={"measure": measure, "scope": "all_exchanges"},
                        value=value / 100_000_000.0,
                        unit="hundred_million_cny",
                    )
                )
        return tuple(scalars)

    def margin_financing_sse_szse(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[ContextScalar, ...]:
        """Sum the SSE and SZSE margin totals; Beijing rows are not part of this identity."""
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
        return _sse_szse_margin_scalars(rows, requested_end=end_date)

    def margin_financing_candidate(
        self,
        *,
        trading_days: tuple[date, ...],
        publishing_day: date | None = None,
    ) -> tuple[ContextScalar, ...]:
        """Collect the new, uncertified three-exchange contract for source review.

        Every trading day must carry all three exchanges, except ``publishing_day``: the day a
        query asked up to, which some exchanges may not have published yet.
        """
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
        if publishing_day is None:
            if seen != {(day, e) for day in expected_dates for e in expected_exchanges}:
                raise ValueError("tushare_margin_exchange_coverage_incomplete")
            published = expected_dates
        else:
            published = _published_margin_days(
                seen, expected_exchanges, requested_end=publishing_day
            )
            if expected_dates - published - {publishing_day}:
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
            if trading_day in published
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

    def breadth(
        self,
        *,
        end_date: date,
        held_days: Iterable[date],
        sessions: tuple[date, ...],
        calendar_ids: tuple[str, ...],
    ) -> tuple[ContextScalar, ...]:
        """The seven breadth metrics of the window's days not yet held (ADR-0030).

        ``sessions`` and the responses they come from (``calendar_ids``) are the SSE
        calendar's: breadth asks TuShare for no calendar of its own.
        """
        from pring_cycle.breadth import breadth_scalars

        scalars = breadth_scalars(
            self._call,
            end_date=end_date,
            sessions=sessions,
            held_days=held_days,
            calendar_ids=calendar_ids,
        )
        if not scalars:
            # Every day of the window is held already: nothing new.
            raise ContextObservationsMissingError("nothing_new")
        return scalars

    def ex_hog_basket(
        self, *, end_date: date, held_levels: Mapping[date, float]
    ) -> tuple[ContextScalar, ...]:
        """The basket and its sleeves on the window's days not yet held (ADR-0030)."""
        from pring_cycle.basket import basket_scalars

        scalars = basket_scalars(self._call, end_date=end_date, held_levels=held_levels)
        if not scalars:
            # Every day of the window is held already: nothing new.
            raise ContextObservationsMissingError("nothing_new")
        return scalars

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
            code = int(document.get("code", -1)) if isinstance(document, dict) else -1
            if code != 0:
                # The code (and its message) tells a rate limit from a permission refusal,
                # and a day's quota from a minute's.
                message = document.get("msg") if isinstance(document, dict) else None
                refusal = tushare_refusal(code, message)
                raise TushareSourceError(
                    "tushare_rate_limited"
                    if refusal == "rate_limited"
                    else f"tushare_source_failed:{code}",
                    external_code=code,
                    classification=refusal,
                    quota=tushare_quota_refused(code, message),
                    source_message=message,
                )
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
            def started(acquisition_id: str) -> None:
                self._started.append(acquisition_id)
                if on_started is not None:
                    on_started(acquisition_id)

            earlier, self._failure = self._failure, None
            try:
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
                    on_started=started,
                )
            except Exception as error:
                # Kept as the source or the response said it, for the attempt this call ends
                # (a request wrapper may translate the exception it passes on). A retry held
                # back for TuShare's day leaves the request that failed before it (ticket 31).
                held = isinstance(error, TushareCallNotAttempted) and earlier is not None
                self._failure = earlier if held else error
                raise
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


def reviewed_delivery(paths: RuntimePaths, metric_id: str, definition_version: str) -> bool:
    """Whether the catalog registers TuShare's reviewed delivery of ``metric_id``.

    Such a metric is fetched with only the members its contract supports: social
    financing's annual flow and stock, M1/M2 without month-on-month changes. A full run's
    refresh and a gap's refetch ask alike (lookback L03).
    """
    return (
        TUSHARE_OFFICIAL_DELIVERY_CODES[metric_id]
        in metric_definition(
            metric_id, definition_version=definition_version, database_path=paths.database
        ).source_codes
    )


def ingest_context_scalars(
    paths: RuntimePaths,
    scalars: tuple[ContextScalar, ...],
    *,
    fetched_at: datetime,
    definition_version: str = METRIC_CATALOG_VERSION,
    rejected_fields: tuple[Mapping[str, str], ...] = (),
    details: Mapping[str, str] | None = None,
) -> ContextIngestionResult:
    """Store the delivered scalars and record each metric's (and warrant symbol's) outcome.

    ``rejected_fields`` are the response's fields its checks refused: a metric with any is
    delivered with those members missing (ticket 18). ``details`` go on each record.
    """
    if fetched_at.tzinfo is None:
        raise ValueError("tushare_context_fetched_at_must_be_timezone_aware")
    if not scalars:
        raise ContextObservationsMissingError()
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
    # A warrant symbol is acquired on its own, so its outcome names it, as its failure does
    # (ticket 17).
    members = sorted(
        {(item.metric_id, item.dimensions.get("symbol")) for item in scalars},
        key=lambda member: (member[0], member[1] or ""),
    )
    for metric_id, symbol in members:
        metric_scalars = [
            item
            for item in scalars
            if item.metric_id == metric_id and item.dimensions.get("symbol") == symbol
        ]
        refused = tuple(
            f"{item['api_name']}:{item['source_field']}:{item['period_end']}"
            for item in rejected_fields
            if item.get("metric_id") == metric_id
        )
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare",
            outcome=SUCCEEDED,
            fetched_at=utc_now()
            if any(item.acquisition_ids for item in metric_scalars)
            else fetched_at,
            acquisition_ids=tuple(
                sorted({identity for item in metric_scalars for identity in item.acquisition_ids})
            ),
            safe_metadata={
                **(details or {}),
                # TuShare's answers do not say which members they owe: only a field its
                # rules refused is known missing, so completeness is claimed no further.
                **attempt_details(
                    step="ingest",
                    completeness="partial_members_missing" if refused else None,
                    missing_members=refused,
                    api_names=",".join(sorted({item.api_name for item in metric_scalars})),
                    observations=str(len(metric_scalars)),
                    period_start=min(item.period_start for item in metric_scalars),
                    period_end=max(item.period_end for item in metric_scalars),
                    definition_version=definition_version,
                    rejected_fields=str(len(refused)),
                    **({"symbol": symbol} if symbol is not None else {}),
                ),
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
                    period_kind=field.period_kind,
                    period_start=(
                        f"{period_start[:4]}-01-01"
                        if field.period_kind == "year_to_month"
                        else period_start
                    ),
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


def _published_margin_days(
    seen: set[tuple[date, str]], exchanges: set[str], *, requested_end: date
) -> set[date]:
    """The days every exchange has reported, once each row has passed validation.

    The exchanges publish separately, so a query can catch one of them for the day it asked up
    to and not the others; that day is not yet published, as when none of them has it. Only the
    requested last day is waited for: a day before it missing an exchange is incomplete.
    """
    days = {day for day, _exchange in seen}
    incomplete = {day for day in days if any((day, e) not in seen for e in exchanges)}
    if incomplete - {requested_end}:
        raise ValueError("tushare_margin_exchange_coverage_incomplete")
    return days - incomplete


def _sse_szse_margin_scalars(
    rows: Iterable[Mapping[str, object]], *, requested_end: date
) -> tuple[ContextScalar, ...]:
    totals: dict[date, dict[str, float]] = defaultdict(
        lambda: {"financing_balance": 0.0, "financing_buy_amount": 0.0}
    )
    seen: set[tuple[date, str]] = set()
    for row in rows:
        exchange = str(row.get("exchange_id"))
        if exchange == "BSE":
            continue
        if exchange not in {"SSE", "SZSE"}:
            raise ValueError("tushare_margin_exchange_invalid")
        trading_day = _compact_date(row.get("trade_date"))
        if (trading_day, exchange) in seen:
            raise ValueError("tushare_margin_duplicate_exchange_day")
        seen.add((trading_day, exchange))
        for field, measure in (("rzye", "financing_balance"), ("rzmre", "financing_buy_amount")):
            value = _number(row.get(field))
            if value is None:
                raise ValueError("tushare_margin_value_missing")
            if value < 0:
                raise ValueError("tushare_margin_value_negative")
            totals[trading_day][measure] += value
    published = _published_margin_days(seen, {"SSE", "SZSE"}, requested_end=requested_end)
    return tuple(
        _business_day_scalar(
            metric_id="CN_MARGIN_BALANCE_SSE_SZSE",
            api_name="margin",
            source_field=measure,
            business_date=trading_day,
            dimensions={"measure": measure, "scope": "sse_szse"},
            value=value / 100_000_000.0,
            unit="hundred_million_cny",
        )
        for trading_day, measures in sorted(totals.items())
        if trading_day in published
        for measure, value in measures.items()
    )


def parse_margin_sse_szse_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
) -> tuple[ContextScalar, ...]:
    """Rebuild the two-exchange totals from a margin response, for rechecking its claims."""
    fields = ("trade_date", "exchange_id", "rzye", "rzmre")
    if (
        receipt.provider != "tushare"
        or receipt.api_name != "margin"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"start_date", "end_date"}
    ):
        raise ValueError("registered_margin_acquisition_identity_mismatch")
    rows = _response_rows(json.loads(raw), required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    return _sse_szse_margin_scalars(
        rows, requested_end=_compact_date(receipt.parameters["end_date"])
    )


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
        scalars = adapter.margin_financing_candidate(
            trading_days=days, publishing_day=_compact_date(receipt.parameters["end_date"])
        )
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


def parse_treasury_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
) -> tuple[ContextScalar, ...]:
    """Rebuild the 2Y and 10Y yields from one complete ``us_tycr`` delivery."""
    if (
        receipt.provider != "tushare"
        or receipt.api_name != "us_tycr"
        or receipt.parser_version != "tushare-context-parser-v0002"
        or receipt.fields != "date,y2,y10"
        or set(receipt.parameters) != {"start_date", "end_date"}
    ):
        raise ValueError("registered_treasury_acquisition_identity_mismatch")
    rows = _response_rows(json.loads(raw), required_fields=("date", "y2", "y10"))
    _validate_response_periods(rows, receipt.parameters)
    adapter = TushareContextAdapter("receipt-reparse", transport=lambda _: raw)
    return adapter.treasury_yields(
        start_date=_compact_date(receipt.parameters["start_date"]),
        end_date=_compact_date(receipt.parameters["end_date"]),
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
    return _official_ppi_members(
        _parse_monthly_acquisition(
            receipt,
            raw,
            api_name="cn_ppi",
            contract="ppi",
            scalar_fields=tuple(
                _Field("CN_PPI", field, {"category": category, "measure": measure}, "percent")
                for field, category, measure in TUSHARE_PPI_FIELDS
            ),
        )
    )


def _official_ppi_members(scalars: tuple[ContextScalar, ...]) -> tuple[ContextScalar, ...]:
    """Leave out the PPI fields the official release has no member for in their month.

    TuShare fills the cumulative columns for January as well, where the official table has
    none; that one value refused the whole CPI and PPI delivery (run findings 06).
    """
    return tuple(
        scalar
        for scalar in scalars
        if any(
            member.dimensions == scalar.dimensions
            for member in official_source_members("CN_PPI", scalar.period_end) or ()
        )
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


def _social_financing_total_fields() -> tuple[_Field, ...]:
    return tuple(
        _Field(
            "CN_SF_TOTAL",
            field,
            {"measure": measure},
            "hundred_million_cny",
            multiplier=multiplier,
            period_kind=period_kind,
        )
        for field, measure, multiplier, period_kind in TUSHARE_SF_TOTAL_FIELDS
    )


def parse_social_financing_total_acquisition(
    receipt: AcquisitionReceipt, raw: bytes
) -> tuple[ContextScalar, ...]:
    """Rebuild stock units and annual cumulative periods from the exact sf_month response."""
    return _parse_monthly_acquisition(
        receipt,
        raw,
        api_name="sf_month",
        contract="sf_total",
        scalar_fields=_social_financing_total_fields(),
    )


def _gdp_delivery(rows: ContextRows) -> ContextDelivery:
    scalars: list[ContextScalar] = []
    rejected: list[dict[str, str]] = []
    for row in rows:
        year_start, _quarter_start, quarter_end = _quarter_bounds(str(row.get("quarter")))
        for aggregate, level_field, yoy_field in TUSHARE_GDP_FIELDS:
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
                        dimensions={"aggregate": aggregate, "measure": "nominal_ytd_level"},
                        value=level,
                        unit="hundred_million_cny",
                    )
                )
            # Q2 delivery disagrees with the documented single-quarter meaning.
            # Do not relabel every vintage as cumulative either.
            if _number(row.get(yoy_field)) is not None:
                rejected.append(
                    {
                        "metric_id": "CN_GDP",
                        "api_name": "cn_gdp",
                        "source_field": yoy_field,
                        "period_end": quarter_end,
                        "reason": "gdp_yoy_period_semantics_unverified",
                    }
                )
    return ContextDelivery(tuple(scalars), tuple(rejected))


def _gdp_acquisition_rows(receipt: AcquisitionReceipt, raw: bytes) -> ContextRows:
    fields = (
        "quarter",
        *(f for _aggregate, level, yoy in TUSHARE_GDP_FIELDS for f in (level, yoy)),
    )
    if (
        receipt.state not in {"received", "validated"}
        or receipt.provider != "tushare"
        or receipt.api_name != "cn_gdp"
        or receipt.parser_version != "tushare-gdp-parser-v0003"
        or receipt.fields != ",".join(fields)
        or set(receipt.parameters) != {"start_q", "end_q"}
    ):
        raise ValueError("registered_gdp_acquisition_identity_mismatch")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("tushare_source_failed")
    rows = _response_rows(document, required_fields=fields)
    _validate_response_periods(rows, receipt.parameters)
    return rows


def parse_gdp_acquisition(receipt: AcquisitionReceipt, raw: bytes) -> ContextDelivery:
    """Rebuild the accepted GDP levels and rejected-growth audit from one original."""
    if receipt.state != "validated":
        raise ValueError("registered_gdp_acquisition_identity_mismatch")
    return _gdp_delivery(_gdp_acquisition_rows(receipt, raw))


def tushare_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points: tuple[MetricSeriesPoint, ...],
    *,
    definition_version: str,
    parse: Callable[
        [AcquisitionReceipt, bytes], tuple[ContextScalar, ...] | ContextDelivery
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
                    delivery = parse(item.receipt, item.raw)
                    scalars = (
                        delivery.scalars if isinstance(delivery, ContextDelivery) else delivery
                    )
                    normalized = json.loads(item.normalized)
                    rejected = (
                        list(delivery.rejected_fields)
                        if isinstance(delivery, ContextDelivery)
                        else []
                    )
                    if rejected:
                        if (
                            not isinstance(normalized, dict)
                            or set(normalized) != {"accepted_scalars", "rejected_fields"}
                            or normalized["rejected_fields"] != rejected
                        ):
                            raise ValueError("registered_tushare_rejected_fields_mismatch")
                        normalized = normalized["accepted_scalars"]
                    if not isinstance(normalized, list):
                        raise ValueError("registered_tushare_normalized_mismatch")
                    economic = []
                    for entry in normalized:
                        if (
                            not isinstance(entry, dict)
                            or not _entry_defined_alike(repository, entry, definition_version)
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
                            == getattr(claim, attribute)
                            for field, attribute in (
                                ("release_at", "release_at"),
                                ("public_available_at", "parsed_public_available_at"),
                            )
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


def _entry_defined_alike(
    repository: EvidenceRepository, entry: Mapping[str, Any], definition_version: str
) -> bool:
    """An unstamped scalar, or one stamped by a version defining its metric alike (ADR-0036)."""
    stamped = entry.get("definition_version")
    return stamped is None or repository.defined_alike(
        str(entry.get("metric_id")),
        stamped if isinstance(stamped, str) else None,
        definition_version,
    )


def parse_warrant_acquisition(
    receipt: AcquisitionReceipt,
    raw: bytes,
    normalized: bytes,
    *,
    period: str,
    definition_versions: frozenset[str],
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
    scalars = _warrant_scalars(rows, symbol, source_symbol, _WARRANT_FIELDS)
    normalized_scalars = json.loads(normalized)
    if isinstance(normalized_scalars, dict):
        # Deliveries since the warehouse totals also carry their reconciliation notes.
        if set(normalized_scalars) != {
            "accepted_scalars",
            "warrant_reconciliation",
        } or normalized_scalars["warrant_reconciliation"] != _warrant_receipt_reconciliation(
            receipt, raw
        ):
            raise ValueError("tushare_warrant_normalized_mismatch")
        normalized_scalars = normalized_scalars["accepted_scalars"]
    if not isinstance(normalized_scalars, list) or len(normalized_scalars) != len(scalars):
        raise ValueError("tushare_warrant_normalized_mismatch")
    expected = sorted(_canonical_json(asdict(scalar)) for scalar in scalars)
    actual = []
    verified: list[ContextScalar] = []
    for item in normalized_scalars:
        if not isinstance(item, dict):
            raise ValueError("tushare_warrant_normalized_mismatch")
        if item.get("definition_version") not in (None, *definition_versions):
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
        sum(
            identity[0].isoformat() == period
            for identity in _warrant_members(rows, source_symbol, _WARRANT_FIELDS)
        ),
    )


def _warrant_receipt_reconciliation(
    receipt: AcquisitionReceipt, raw: bytes
) -> dict[str, list[Any]]:
    rows = _response_rows(json.loads(raw), required_fields=tuple(receipt.fields.split(",")))
    return _warrant_reconciliation(
        _warrant_members(rows, receipt.parameters["symbol"], _WARRANT_FIELDS).values()
    )


@dataclass(frozen=True)
class _WarrantMember:
    """One warehouse's total for a day: TuShare drops the exchange's per-lot columns."""

    business_date: date
    warehouse: str
    exchange: str
    unit: str
    values: dict[str, float]


def _warrant_members(
    rows: ContextRows,
    source_symbol: str,
    fields: tuple[tuple[str, str], ...],
) -> dict[tuple[date, str, str], _WarrantMember]:
    """Sum each warehouse's rows for a day (ADR-0029); a field is kept only if every row has it."""
    grouped: dict[tuple[date, str, str], list[dict[str, object]]] = {}
    units: dict[tuple[date, str, str], str] = {}
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
        identity = (_compact_date(row.get("trade_date")), warehouse, exchange)
        if units.setdefault(identity, unit) != unit:
            raise ValueError("tushare_warrant_unit_conflict")
        for source_field in ("pre_vol", "vol"):
            value = _number(row.get(source_field))
            if value is not None and value < 0:
                raise ValueError("tushare_warrant_quantity_negative")
        grouped.setdefault(identity, []).append(row)
    members = {}
    for identity, member_rows in grouped.items():
        values = {}
        for source_field, _measure in fields:
            reported = [_number(row.get(source_field)) for row in member_rows]
            if all(value is None for value in reported):
                continue
            if any(value is None for value in reported):
                raise ValueError("tushare_warrant_member_field_partial")
            values[source_field] = float(sum(value for value in reported if value is not None))
        business_date, warehouse, exchange = identity
        members[identity] = _WarrantMember(
            business_date, warehouse, exchange, units[identity], values
        )
    return members


def _warrant_scalars(
    rows: ContextRows,
    normalized_symbol: str,
    source_symbol: str,
    fields: tuple[tuple[str, str], ...],
) -> tuple[ContextScalar, ...]:
    return tuple(
        _business_day_scalar(
            metric_id="CN_FUTURES_WARRANTS",
            api_name="fut_wsr",
            source_field=source_field,
            business_date=member.business_date,
            dimensions={
                "symbol": normalized_symbol,
                "warehouse": member.warehouse,
                "exchange": member.exchange,
                "measure": measure,
            },
            value=member.values[source_field],
            unit=member.unit,
        )
        for member in _warrant_members(rows, source_symbol, fields).values()
        for source_field, measure in fields
        if source_field in member.values
    )


def _warrant_reconciliation(members: Iterable[_WarrantMember]) -> dict[str, list[Any]]:
    """Note where a warehouse's summed change disagrees with its day-on-day totals.

    TuShare loses lot rows as well as columns, so the two disagree now and then. Such a day is
    kept and noted, not rejected (user decision 2026-09-25). The first day in a delivery has no
    earlier total in it to check against.
    """
    by_identity = {(m.business_date, m.warehouse, m.exchange): m for m in members}
    dates = sorted({identity[0] for identity in by_identity})
    # The previous delivered day stands for the previous session unless the delivery skips
    # more than a long holiday; then the day is left unchecked.
    previous_date = {
        day: earlier
        for day, earlier in zip(dates[1:], dates, strict=False)
        if (day - earlier).days <= 10
    }
    mismatches = []
    for (business_date, warehouse, exchange), member in sorted(by_identity.items()):
        earlier = previous_date.get(business_date)
        previous = by_identity.get((earlier, warehouse, exchange)) if earlier else None
        if (
            previous is None
            or "vol" not in previous.values
            or not {"vol", "vol_chg"} <= set(member.values)
        ):
            continue
        movement = member.values["vol"] - previous.values["vol"]
        if abs(movement - member.values["vol_chg"]) > 1e-9:
            mismatches.append(
                {
                    "business_date": business_date.isoformat(),
                    "warehouse": warehouse,
                    "exchange": exchange,
                    "total": member.values["vol"],
                    "previous_total": previous.values["vol"],
                    "change_sum": member.values["vol_chg"],
                }
            )
    unchecked = [day.isoformat() for day in dates if day not in previous_date]
    return {"unchecked_dates": unchecked, "mismatches": mismatches}


_WARRANT_FIELDS = (
    ("pre_vol", "previous_registered_receipts"),
    ("vol", "registered_receipts"),
    ("vol_chg", "registered_receipts_change"),
)


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
