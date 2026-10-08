from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import (
    Acquired,
    AcquisitionReceipt,
    AcquisitionRepository,
    SourceFailed,
)
from pring_cycle.acquisition_outcome import SUCCEEDED, attempt_details, capture_failure
from pring_cycle.adapters import MarketBar
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
    publication_times,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.trading_calendar import CalendarAdapter, acquire_sse_calendar
from pring_cycle.tushare_quota import TushareCallNotAttempted

CORE_HISTORY_SCHEMA_VERSION = "tushare-core-history-v0001"
# The sessions each run fetches for a core and its stateful trend reads: the 120-session
# window plus the preheat before it. Older history a kept projection still cites stays
# held (lookback 08), but the trend never reads further back than this.
CORE_TREND_SESSIONS = 160


@dataclass(frozen=True)
class CoreHistoryRefreshResult:
    artifact_hash: str
    definition_version: str
    first_business_date: str
    last_business_date: str
    network_requests: int
    observations_per_metric: int
    status: str
    rejected_metrics: tuple[str, ...] = ()


class CoreHistoryAdapter(CalendarAdapter, Protocol):
    def acquire_core_bars(
        self,
        repository: AcquisitionRepository,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...],
    ) -> Acquired[tuple[MarketBar, ...]]: ...


def refresh_core_history(
    paths: RuntimePaths,
    adapter: CoreHistoryAdapter,
    *,
    start: date,
    end: date,
    definition_version: str,
    latest_observations: int | None = None,
    metric_ids: tuple[str, ...] | None = None,
) -> CoreHistoryRefreshResult:
    """Fetch and store the cores' daily bars; ``metric_ids`` narrows a retry to some cores."""
    cores = tuple(metric_ids) if metric_ids is not None else tuple(CORE_API_IDENTITIES)
    if start > end:
        raise ValueError("core_history_range_invalid")
    if latest_observations is not None and latest_observations < 1:
        raise ValueError("core_history_observation_limit_invalid")
    definitions = {
        metric_id: metric_definition(
            metric_id, definition_version=definition_version, database_path=paths.database
        )
        for metric_id in cores
    }
    calendars: list[date] = []
    collected: dict[str, list[MarketBar]] = {metric_id: [] for metric_id in cores}
    network_requests = 0
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipts: dict[tuple[str, date], AcquisitionReceipt] = {}
    rejected: list[str] = []
    first_rejection: Exception | None = None
    ranges = (
        [(start, end)]
        if latest_observations is not None
        else [
            (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)))
            for year in range(start.year, end.year + 1)
        ]
    )
    for chunk_start, chunk_end in ranges:
        calendar = acquire_sse_calendar(paths, adapter, chunk_start, chunk_end)
        if latest_observations is not None:
            calendar = calendar[-latest_observations:]
            if not calendar or calendar[-1] != end:
                raise ValueError("target_business_date_not_in_china_calendar")
        network_requests += 1
        calendars.extend(calendar)
        for metric_id in cores:
            if metric_id in rejected:
                continue
            try:
                acquired = adapter.acquire_core_bars(
                    acquisitions,
                    metric_id,
                    start=calendar[0],
                    end=calendar[-1],
                    expected_business_dates=calendar,
                )
            except TushareCallNotAttempted as error:
                # Held back for TuShare's day (ticket 31): nothing sent, said so for the core.
                outcome, details = capture_failure(error)
                EvidenceRepository(paths.database).record_retrieval_attempt(
                    metric_id=metric_id,
                    channel="tushare-history",
                    outcome=outcome,
                    fetched_at=datetime.now(UTC),
                    safe_metadata=details,
                )
                first_rejection = first_rejection or error
                rejected.append(metric_id)
                collected.pop(metric_id, None)
                continue
            except (KeyError, TypeError, ValueError, OSError) as error:
                if isinstance(error, SourceFailed):
                    # TuShare's refusal, its code and words, for the core (ticket 31).
                    outcome, details = capture_failure(error)
                    EvidenceRepository(paths.database).record_retrieval_attempt(
                        metric_id=metric_id,
                        channel="tushare-history",
                        outcome=outcome,
                        fetched_at=datetime.now(UTC),
                        safe_metadata=details,
                    )
                first_rejection = first_rejection or error
                # Gate ③: this core's response failed its structure check (or never came)
                # and was recorded on its call; the other cores are still kept.
                rejected.append(metric_id)
                collected.pop(metric_id, None)
                network_requests += 1
                continue
            collected[metric_id].extend(acquired.value)
            receipts.update(
                {(metric_id, bar.business_date): acquired.receipt for bar in acquired.value}
            )
            network_requests += 1
    expected = tuple(calendars)
    if not expected:
        raise ValueError("core_history_calendar_missing")
    if not collected:
        assert first_rejection is not None
        raise first_rejection
    if any(tuple(bar.business_date for bar in bars) != expected for bars in collected.values()):
        raise ValueError("core_history_common_calendar_mismatch")

    normalized = {
        "definition_version": definition_version,
        "end": end.isoformat(),
        "schema_version": CORE_HISTORY_SCHEMA_VERSION,
        "series": {
            metric_id: [_bar_document(bar) for bar in bars]
            for metric_id, bars in sorted(collected.items())
        },
        "start": start.isoformat(),
    }
    content = _canonical_json(normalized).encode()
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        "application/json",
        f"{CORE_HISTORY_SCHEMA_VERSION}:{start.isoformat()}:{end.isoformat()}",
    )
    evidence = EvidenceRepository(paths.database)
    claims: list[SourceClaimInput] = []
    # TuShare core responses have no reliable publication field.
    release_at, public_at = publication_times(None, ZoneInfo("Asia/Shanghai"))
    for metric_id, bars in collected.items():
        definition = definitions[metric_id]
        claims.extend(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version=definition.definition_version,
                period_kind="business_day",
                period_start=bar.business_date.isoformat(),
                period_end=bar.business_date.isoformat(),
                dimensions={},
                value=bar.close,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=bar.unit,
                provider="tushare",
                source_reference=(
                    f"tushare:{CORE_API_IDENTITIES[metric_id][0]}:"
                    f"{bar.source_code}:{bar.business_date.isoformat()}"
                ),
                release_event_id=(
                    "unresolved-publication:"
                    f"{receipts[metric_id, bar.business_date].acquisition_id}:"
                    f"{bar.business_date.isoformat()}"
                ),
                release_at=release_at,
                public_available_at=public_at,
                fetched_at=_receipt_received_at(receipts[metric_id, bar.business_date]),
                available_at=_receipt_validated_at(receipts[metric_id, bar.business_date]),
                certification_status=bar.certification_status,
                quality_status="validated",
                acquisition_id=receipts[metric_id, bar.business_date].acquisition_id,
            )
            for bar in bars
        )
    # Only the calls whose bars are stored: a core dropped after a later failure keeps none.
    with acquisitions.ingesting(
        receipts[metric_id, bar.business_date].acquisition_id
        for metric_id, bars in collected.items()
        for bar in bars
    ):
        evidence.append_source_claims(tuple(claims), availability_clock=lambda: datetime.now(UTC))
    fetched_at = datetime.now(UTC)
    for metric_id, bars in collected.items():
        evidence.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare-history",
            outcome=SUCCEEDED,
            fetched_at=fetched_at,
            acquisition_ids=tuple(
                sorted(
                    {
                        receipt.acquisition_id
                        for (m, _), receipt in receipts.items()
                        if m == metric_id
                    }
                )
            ),
            safe_metadata={
                # Every session of the calendar delivered, or the refresh had failed.
                **attempt_details(step="ingest", completeness="complete"),
                "first_business_date": expected[0].isoformat(),
                "last_business_date": expected[-1].isoformat(),
                "normalized_hash": artifact.content_hash,
                "observations": str(len(bars)),
                "source_code": CORE_API_IDENTITIES[metric_id][1],
                "definition_version": definition_version,
            },
        )
    return CoreHistoryRefreshResult(
        artifact_hash=artifact.content_hash,
        definition_version=definition_version,
        first_business_date=expected[0].isoformat(),
        last_business_date=expected[-1].isoformat(),
        network_requests=network_requests,
        observations_per_metric=len(expected),
        status="partially_rejected" if rejected else "validated",
        rejected_metrics=tuple(rejected),
    )


def _receipt_received_at(receipt: AcquisitionReceipt) -> datetime:
    if receipt.received_at is None:
        raise ValueError("core_acquisition_receipt_incomplete")
    return receipt.received_at


def _receipt_validated_at(receipt: AcquisitionReceipt) -> datetime:
    if receipt.validated_at is None:
        raise ValueError("core_acquisition_receipt_incomplete")
    return receipt.validated_at


def _bar_document(bar: MarketBar) -> dict[str, object]:
    document = asdict(bar)
    document["business_date"] = bar.business_date.isoformat()
    return document


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
