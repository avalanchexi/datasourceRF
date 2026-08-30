from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from pring_cycle.adapters import MarketBar
from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES

CORE_HISTORY_SCHEMA_VERSION = "tushare-core-history-v0001"


@dataclass(frozen=True)
class CoreHistoryRefreshResult:
    artifact_hash: str
    definition_version: str
    first_business_date: str
    last_business_date: str
    network_requests: int
    observations_per_metric: int
    status: str


class CoreHistoryAdapter(Protocol):
    def trading_days(self, start: date, end: date) -> tuple[date, ...]: ...

    def core_bars(
        self,
        metric_id: str,
        *,
        start: date,
        end: date,
        expected_business_dates: tuple[date, ...] | None = None,
    ) -> tuple[MarketBar, ...]: ...


def refresh_core_history(
    paths: RuntimePaths,
    adapter: CoreHistoryAdapter,
    *,
    start: date,
    end: date,
    definition_version: str,
) -> CoreHistoryRefreshResult:
    if start > end:
        raise ValueError("core_history_range_invalid")
    calendars: list[date] = []
    collected: dict[str, list[MarketBar]] = {
        metric_id: [] for metric_id in CORE_API_IDENTITIES
    }
    network_requests = 0
    for year in range(start.year, end.year + 1):
        chunk_start = max(start, date(year, 1, 1))
        chunk_end = min(end, date(year, 12, 31))
        calendar = adapter.trading_days(chunk_start, chunk_end)
        network_requests += 1
        calendars.extend(calendar)
        for metric_id in CORE_API_IDENTITIES:
            collected[metric_id].extend(
                adapter.core_bars(
                    metric_id,
                    start=chunk_start,
                    end=chunk_end,
                    expected_business_dates=calendar,
                )
            )
            network_requests += 1
    expected = tuple(calendars)
    if not expected:
        raise ValueError("core_history_calendar_missing")
    if any(
        tuple(bar.business_date for bar in bars) != expected
        for bars in collected.values()
    ):
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
    fetched_at = datetime.now(UTC)
    evidence = EvidenceRepository(paths.database)
    claims: list[SourceClaimInput] = []
    for metric_id, bars in collected.items():
        definition = metric_definition(
            metric_id,
            definition_version=definition_version,
        )
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
                    f"release:{CORE_API_IDENTITIES[metric_id][0]}:"
                    f"{bar.source_code}:{bar.business_date.isoformat()}"
                ),
                release_at=_public_available_at(bar.business_date),
                public_available_at=_public_available_at(bar.business_date),
                fetched_at=fetched_at,
                available_at=fetched_at,
                certification_status=bar.certification_status,
                quality_status="validated",
            )
            for bar in bars
        )
    evidence.append_source_claims(tuple(claims))
    for metric_id, bars in collected.items():
        evidence.record_retrieval_attempt(
            metric_id=metric_id,
            channel="tushare-history",
            outcome="verified",
            fetched_at=fetched_at,
            safe_metadata={
                "first_business_date": expected[0].isoformat(),
                "last_business_date": expected[-1].isoformat(),
                "normalized_hash": hashlib.sha256(
                    _canonical_json([_bar_document(bar) for bar in bars]).encode()
                ).hexdigest(),
                "observations": str(len(bars)),
                "source_code": CORE_API_IDENTITIES[metric_id][1],
            },
        )
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        content,
        "application/json",
        f"{CORE_HISTORY_SCHEMA_VERSION}:{start.isoformat()}:{end.isoformat()}",
    )
    return CoreHistoryRefreshResult(
        artifact_hash=artifact.content_hash,
        definition_version=definition_version,
        first_business_date=expected[0].isoformat(),
        last_business_date=expected[-1].isoformat(),
        network_requests=network_requests,
        observations_per_metric=len(expected),
        status="validated",
    )


def _public_available_at(business_date: date) -> datetime:
    return datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        7,
        30,
        tzinfo=UTC,
    )


def _bar_document(bar: MarketBar) -> dict[str, object]:
    document = asdict(bar)
    document["business_date"] = bar.business_date.isoformat()
    return document


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
