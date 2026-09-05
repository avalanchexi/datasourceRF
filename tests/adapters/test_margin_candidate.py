from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter, ingest_context_scalars


def margin_response(rows: list[list[object]]) -> dict[str, Any]:
    return {
        "code": 0,
        "data": {"fields": ["trade_date", "exchange_id", "rzye", "rzmre"], "items": rows},
    }


def test_margin_candidate_keeps_verified_fetch_separate_from_unknown_publication(
    tmp_path: Path,
) -> None:
    # Worked three-market example: 100 + 200 + 50 million CNY, including BSE.
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=lambda payload: margin_response(
            [
                ["20260828", "SSE", 100_000_000, 10_000_000],
                ["20260828", "SZSE", 200_000_000, 20_000_000],
                ["20260828", "BSE", 50_000_000, 5_000_000],
            ]
        ),
    )
    scalars = adapter.margin_financing_candidate(trading_days=(date(2026, 8, 28),))
    assert {(item.dimensions["measure"], item.value) for item in scalars} == {
        ("financing_balance", 3.5),
        ("financing_buy_amount", 0.35),
    }
    assert {item.dimensions["scope"] for item in scalars} == {"SSE+SZSE+BSE"}
    assert all(item.release_at is None and item.public_available_at is None for item in scalars)

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    fetched_at = datetime(2026, 9, 5, 10, tzinfo=UTC)
    result = ingest_context_scalars(
        paths, scalars, fetched_at=fetched_at, definition_version="margin-financing-v0002"
    )
    repository = EvidenceRepository(paths.database)
    assert result.observation_count == 2
    events = repository.release_events_for_definition(
        metric_id="CN_MARGIN_BALANCE", definition_version="margin-financing-v0002"
    )
    assert len(events) == 1
    assert events[0].available_at == fetched_at
    assert events[0].public_available_at is None
    assert events[0].release_at is None
    assert (
        repository.metric_series(
            "CN_MARGIN_BALANCE",
            mode=AsOfMode.PUBLIC,
            as_of=fetched_at,
            definition_version="margin-financing-v0002",
        )
        == ()
    )
    trace = repository.trace(result.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=fetched_at)
    assert trace.claims[0].certification_status == "awaiting_source_certification"
    repeated = ingest_context_scalars(
        paths,
        scalars,
        fetched_at=fetched_at + timedelta(days=1),
        definition_version="margin-financing-v0002",
    )
    assert repeated.claim_ids == result.claim_ids
    revised = ingest_context_scalars(
        paths,
        (replace(scalars[0], value=4.0),),
        fetched_at=fetched_at + timedelta(days=2),
        definition_version="margin-financing-v0002",
    )
    assert revised.observation_ids == (result.observation_ids[0],)
    revised_trace = repository.trace(
        revised.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=fetched_at + timedelta(days=2)
    )
    assert revised_trace.selected_value == 4.0
    assert (
        repository.trace(
            result.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=fetched_at
        ).selected_value
        == 3.5
    )
    assert all(claim.public_available_at is None for claim in revised_trace.claims)

    with pytest.raises(ValueError, match="definition_version_mismatch"):
        ingest_context_scalars(
            paths, scalars, fetched_at=fetched_at, definition_version="metric-catalog-v0003"
        )
    with pytest.raises(ValueError, match="candidate_contract_mismatch"):
        ingest_context_scalars(
            paths,
            (replace(scalars[0], definition_version=None),),
            fetched_at=fetched_at,
            definition_version="margin-financing-v0002",
        )


@pytest.mark.parametrize(
    ("rows", "trading_days", "error"),
    [
        (
            [["20260828", "SSE", 100, 10], ["20260828", "SZSE", 200, 20]],
            (date(2026, 8, 28),),
            "tushare_margin_exchange_coverage_incomplete",
        ),
        (
            [
                ["20260828", "SSE", 100, 10],
                ["20260828", "SSE", 100, 10],
                ["20260828", "SZSE", 200, 20],
                ["20260828", "BSE", 50, 5],
            ],
            (date(2026, 8, 28),),
            "tushare_margin_duplicate_exchange_day",
        ),
        (
            [["20260827", "SSE", 100, 10]],
            (date(2026, 8, 28),),
            "tushare_margin_unexpected_trading_day",
        ),
        (
            [["20260828", "UNKNOWN", 100, 10]],
            (date(2026, 8, 28),),
            "tushare_margin_exchange_invalid",
        ),
        (
            [
                ["20260828", "SSE", 100, 10],
                ["20260828", "SZSE", 200, 20],
                ["20260828", "BSE", 50, 5],
            ],
            (date(2026, 8, 28), date(2026, 8, 31)),
            "tushare_margin_exchange_coverage_incomplete",
        ),
        ([], (date(2026, 8, 28),), "tushare_margin_exchange_coverage_incomplete"),
    ],
)
def test_margin_candidate_rejects_incomplete_or_ambiguous_exchange_date_matrix(
    rows: list[list[object]], trading_days: tuple[date, ...], error: str
) -> None:
    adapter = TushareContextAdapter(
        "fixture-token", transport=lambda payload: margin_response(rows)
    )
    with pytest.raises(ValueError, match=error):
        adapter.margin_financing_candidate(trading_days=trading_days)


@pytest.mark.parametrize("value", [-1, None, float("nan"), float("inf"), True])
def test_margin_candidate_rejects_invalid_balance_or_buy_amount(value: object) -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=lambda payload: margin_response(
            [
                ["20260828", "SSE", value, 10],
                ["20260828", "SZSE", 200, 20],
                ["20260828", "BSE", 50, 5],
            ]
        ),
    )
    with pytest.raises(ValueError):
        adapter.margin_financing_candidate(trading_days=(date(2026, 8, 28),))


@pytest.mark.parametrize("trading_days", [(), (date(2026, 8, 28),) * 2])
def test_margin_candidate_rejects_empty_or_duplicate_calendar_before_network(
    trading_days: tuple[date, ...],
) -> None:
    requests: list[dict[str, Any]] = []

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        requests.append(payload)
        return margin_response([])

    adapter = TushareContextAdapter("fixture-token", transport=transport)
    with pytest.raises(ValueError, match="tushare_margin_calendar_invalid"):
        adapter.margin_financing_candidate(trading_days=trading_days)
    assert requests == []
