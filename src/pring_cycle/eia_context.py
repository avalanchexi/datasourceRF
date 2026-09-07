from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from math import isfinite
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from pring_cycle.acquisition import AcquisitionRepository, utc_now
from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    StoredSourceClaim,
)
from pring_cycle.runtime import RuntimePaths

EIA_SPOT_PRICE_ENDPOINT = "https://api.eia.gov/v2/petroleum/pri/spt/data/"
MAX_EIA_RESPONSE_BYTES = 4_000_000

_SERIES_METRICS = {
    "RBRTE": "EIA_BRENT_RBRTE",
    "RWTC": "EIA_WTI_RWTC",
}
_SERIES_DESCRIPTIONS = {
    "RBRTE": "Europe Brent Spot Price FOB",
    "RWTC": "Cushing, OK WTI Spot Price FOB",
}

Transport = Callable[[dict[str, object]], dict[str, object] | bytes]


@dataclass(frozen=True)
class EiaSpotPrice:
    metric_id: str
    series_id: str
    series_description: str
    business_date: date
    value: float
    unit: str
    acquisition_id: str | None = None


@dataclass(frozen=True)
class EiaIngestionResult:
    observation_count: int
    observation_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]


@dataclass(frozen=True)
class EiaSmokeResult:
    status: str
    endpoint: str
    series_ids: tuple[str, ...]
    first_business_date: str
    last_business_date: str
    observation_count: int
    normalized_hash: str
    network_requests: int


class EiaPetroleumAdapter:
    def __init__(self, api_key: str, *, transport: Transport | None = None) -> None:
        if not api_key:
            raise ValueError("eia_api_key_required")
        self._api_key = api_key
        self._transport = transport or self._get
        self._acquisitions: AcquisitionRepository | None = None
        self._http_metadata: tuple[str, int, str] | None = None

    def acquire_spot_prices(
        self,
        paths: RuntimePaths,
        *,
        start_date: date,
        end_date: date,
        definition_version: str = METRIC_CATALOG_VERSION,
    ) -> EiaIngestionResult:
        if self._acquisitions is not None:
            raise ValueError("eia_acquisition_already_running")
        self._acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
        try:
            prices = self.spot_prices(start_date=start_date, end_date=end_date)
            return ingest_eia_spot_prices(
                paths,
                prices,
                fetched_at=utc_now(),
                definition_version=definition_version,
            )
        finally:
            self._acquisitions = None

    def spot_prices(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[EiaSpotPrice, ...]:
        if end_date < start_date:
            raise ValueError("eia_date_range_invalid")
        parameters: dict[str, object] = {
            "api_key": self._api_key,
            "data[]": "value",
            "end": end_date.isoformat(),
            "facets[series][]": tuple(_SERIES_METRICS),
            "frequency": "daily",
            "length": "5000",
            "offset": "0",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "start": start_date.isoformat(),
        }
        self._http_metadata = None

        def parse(response: bytes | dict[str, object]) -> tuple[EiaSpotPrice, ...]:
            return _parse_spot_prices(
                self._decode_response(response),
                start_date=start_date,
                end_date=end_date,
            )

        if self._acquisitions is None:
            return parse(self._transport(parameters))

        def fetch() -> bytes:
            response = self._transport(parameters)
            if not isinstance(response, bytes):
                raise ValueError("acquisition_raw_response_bytes_required")
            return response

        acquired = self._acquisitions.capture(
            provider="U.S. Energy Information Administration",
            api_name="eia_spot_prices",
            parameters={k: str(v) for k, v in parameters.items() if k != "api_key"},
            fields="period,series,series-description,value,units",
            parser_version="eia-spot-parser-v0002",
            fetch=fetch,
            parse=parse,
            normalize=lambda prices: [asdict(p) for p in prices],
        )
        return tuple(
            replace(price, acquisition_id=acquired.receipt.acquisition_id)
            for price in acquired.value
        )

    def smoke(self, *, start_date: date, end_date: date) -> EiaSmokeResult:
        prices = self.spot_prices(start_date=start_date, end_date=end_date)
        normalized = [
            (
                item.metric_id,
                item.series_id,
                item.business_date.isoformat(),
                item.value,
                item.unit,
            )
            for item in prices
        ]
        return EiaSmokeResult(
            status="validated_candidate",
            endpoint=EIA_SPOT_PRICE_ENDPOINT,
            series_ids=tuple(sorted({item.series_id for item in prices})),
            first_business_date=min(item.business_date for item in prices).isoformat(),
            last_business_date=max(item.business_date for item in prices).isoformat(),
            observation_count=len(prices),
            normalized_hash=hashlib.sha256(
                json.dumps(normalized, ensure_ascii=True, separators=(",", ":")).encode()
            ).hexdigest(),
            network_requests=1,
        )

    def _get(self, parameters: dict[str, object]) -> bytes:
        query_items: list[tuple[str, object]] = []
        for key, value in parameters.items():
            if isinstance(value, tuple):
                query_items.extend((key, item) for item in value)
            else:
                query_items.append((key, value))
        url = f"{EIA_SPOT_PRICE_ENDPOINT}?{urlencode(query_items)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "pring-cycle/1.0 eia-source-adapter",
            },
            method="GET",
        )
        with build_opener().open(request, timeout=15) as response:
            content = response.read(MAX_EIA_RESPONSE_BYTES + 1)
            final_url = response.geturl()
            status = int(response.status)
            media_type = str(response.headers.get("Content-Type", ""))
        self._http_metadata = (final_url, status, media_type)
        return bytes(content)

    def _decode_response(self, content: bytes | dict[str, object]) -> dict[str, object]:
        if isinstance(content, dict):
            return content
        if len(content) > MAX_EIA_RESPONSE_BYTES:
            raise ValueError("eia_response_size_invalid")
        if self._http_metadata is not None:
            final_url, status, media_type = self._http_metadata
            parsed_url = urlsplit(final_url)
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname != "api.eia.gov"
                or parsed_url.path != "/v2/petroleum/pri/spt/data/"
            ):
                raise ValueError("eia_response_source_identity_invalid")
            if status != 200:
                raise ValueError("eia_response_http_status_invalid")
            if media_type.split(";", maxsplit=1)[0].strip().lower() != "application/json":
                raise ValueError("eia_response_media_type_invalid")
        try:
            document = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("eia_response_json_invalid") from error
        if not isinstance(document, dict):
            raise ValueError("eia_response_schema_invalid")
        return document


def ingest_eia_spot_prices(
    paths: RuntimePaths,
    prices: tuple[EiaSpotPrice, ...],
    *,
    fetched_at: datetime,
    definition_version: str = METRIC_CATALOG_VERSION,
) -> EiaIngestionResult:
    if fetched_at.tzinfo is None:
        raise ValueError("eia_fetched_at_must_be_timezone_aware")
    if not prices:
        raise ValueError("eia_observations_missing")
    repository = EvidenceRepository(paths.database)
    claims: list[SourceClaimInput] = []
    stored_by_input: list[StoredSourceClaim | None] = []
    for price in prices:
        definition = metric_definition(
            price.metric_id,
            definition_version=definition_version,
        )
        source_reference = (
            f"eia:v2:petroleum/pri/spt:{price.series_id}:{price.business_date.isoformat()}"
        )
        base_event_id = f"eia:{price.series_id}:{price.business_date.isoformat()}"
        existing = repository.latest_source_claim(
            metric_id=price.metric_id,
            definition_version=definition.definition_version,
            period_kind="business_day",
            period_start=price.business_date.isoformat(),
            period_end=price.business_date.isoformat(),
            dimensions={},
            provider="U.S. Energy Information Administration",
            source_reference=source_reference,
        )
        if (
            existing is not None
            and existing.value_state is EvidenceValueState.REPORTED_VALUE
            and existing.value == price.value
            and existing.unit == price.unit
            and existing.public_available_at is None
            and price.acquisition_id is None
        ):
            stored_by_input.append(
                StoredSourceClaim(
                    existing.claim_id,
                    existing.observation_id,
                    existing.supersedes_claim_id,
                )
            )
            continue
        release_event_id = _revision_event_id(f"unresolved-publication:{base_event_id}", fetched_at)
        release_at = None
        public_available_at = None
        receipt = (
            AcquisitionRepository(paths.database, paths.artifacts).get(price.acquisition_id)
            if price.acquisition_id
            else None
        )
        if receipt is not None and (receipt.received_at is None or receipt.validated_at is None):
            raise ValueError("eia_acquisition_incomplete")
        claims.append(
            SourceClaimInput(
                metric_id=price.metric_id,
                definition_version=definition.definition_version,
                period_kind="business_day",
                period_start=price.business_date.isoformat(),
                period_end=price.business_date.isoformat(),
                dimensions={},
                value=price.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=price.unit,
                provider="U.S. Energy Information Administration",
                source_reference=source_reference,
                release_event_id=release_event_id,
                release_at=release_at,
                # The v2 response has no reliable publication timestamp.
                public_available_at=public_available_at,
                fetched_at=receipt.received_at if receipt and receipt.received_at else fetched_at,
                available_at=receipt.validated_at
                if receipt and receipt.validated_at
                else fetched_at,
                certification_status=definition.certification_status,
                quality_status="validated",
                acquisition_id=price.acquisition_id,
            )
        )
        stored_by_input.append(None)
    newly_stored = iter(
        repository.append_source_claims(
            tuple(claims),
            availability_clock=utc_now if all(c.acquisition_id for c in claims) else None,
        )
        if claims
        else ()
    )
    stored = tuple(item if item is not None else next(newly_stored) for item in stored_by_input)
    metric_ids = tuple(sorted({price.metric_id for price in prices}))
    for metric_id in metric_ids:
        metric_prices = [price for price in prices if price.metric_id == metric_id]
        repository.record_retrieval_attempt(
            metric_id=metric_id,
            channel="eia_official_candidate",
            outcome="verified_candidate",
            fetched_at=utc_now()
            if any(price.acquisition_id for price in metric_prices)
            else fetched_at,
            acquisition_ids=tuple(
                sorted(
                    {
                        price.acquisition_id
                        for price in metric_prices
                        if price.acquisition_id is not None
                    }
                )
            ),
            safe_metadata={
                "endpoint": EIA_SPOT_PRICE_ENDPOINT,
                "observations": str(len(metric_prices)),
                "series_id": metric_prices[0].series_id,
                "definition_version": definition_version,
            },
        )
    return EiaIngestionResult(
        observation_count=len(stored),
        observation_ids=tuple(item.observation_id for item in stored),
        claim_ids=tuple(item.claim_id for item in stored),
        metric_ids=metric_ids,
    )


def _revision_event_id(base_event_id: str, fetched_at: datetime) -> str:
    suffix = hashlib.sha256(fetched_at.isoformat().encode()).hexdigest()[:16]
    return f"{base_event_id}:revision:{suffix}"


def _parse_spot_prices(
    document: Mapping[str, object],
    *,
    start_date: date,
    end_date: date,
) -> tuple[EiaSpotPrice, ...]:
    response = document.get("response")
    if not isinstance(response, dict):
        raise ValueError("eia_response_schema_invalid")
    if response.get("frequency") != "daily":
        raise ValueError("eia_frequency_identity_mismatch")
    raw_rows = response.get("data")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("eia_observations_missing")
    prices: list[EiaSpotPrice] = []
    identities: set[tuple[str, date]] = set()
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise ValueError("eia_response_row_invalid")
        series_id = raw_row.get("series")
        if not isinstance(series_id, str) or series_id not in _SERIES_METRICS:
            raise ValueError("eia_series_identity_mismatch")
        description = raw_row.get("series-description")
        if description != _SERIES_DESCRIPTIONS[series_id]:
            raise ValueError("eia_series_identity_mismatch")
        if raw_row.get("units") != "Dollars per Barrel":
            raise ValueError("eia_unit_identity_mismatch")
        try:
            business_date = date.fromisoformat(str(raw_row.get("period")))
        except ValueError as error:
            raise ValueError("eia_period_invalid") from error
        if not start_date <= business_date <= end_date:
            raise ValueError("eia_period_out_of_range")
        identity = (series_id, business_date)
        if identity in identities:
            raise ValueError("eia_duplicate_observation")
        identities.add(identity)
        try:
            value = float(raw_row.get("value"))  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise ValueError("eia_value_invalid") from error
        if not isfinite(value) or not 0 < value < 1000:
            raise ValueError("eia_value_invalid")
        prices.append(
            EiaSpotPrice(
                metric_id=_SERIES_METRICS[series_id],
                series_id=series_id,
                series_description=description,
                business_date=business_date,
                value=value,
                unit="usd_per_barrel",
            )
        )
    if {price.series_id for price in prices} != set(_SERIES_METRICS):
        raise ValueError("eia_series_identity_incomplete")
    return tuple(sorted(prices, key=lambda item: (item.business_date, item.series_id)))
