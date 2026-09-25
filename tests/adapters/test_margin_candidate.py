from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionReceipt
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import (
    TushareContextAdapter,
    ingest_context_scalars,
    parse_margin_acquisition,
)


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
    assert all(claim.parsed_public_available_at is None for claim in revised_trace.claims)

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
            "tushare_response_period_mismatch",
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


# 2026-09-25 (Mid-Autumn, closed): TuShare carried SSE's 9/24 margin row while SZSE and BSE had
# not published yet. Hours earlier the same query returned no 9/24 rows at all and passed.
PARTIAL_LATEST_DAY = [
    ["20260923", "SSE", 100_000_000, 10_000_000],
    ["20260923", "SZSE", 200_000_000, 20_000_000],
    ["20260923", "BSE", 50_000_000, 5_000_000],
    ["20260924", "SSE", 110_000_000, 11_000_000],
]


def margin_adapter(rows: list[list[object]]) -> TushareContextAdapter:
    return TushareContextAdapter("fixture-token", transport=lambda payload: margin_response(rows))


def test_two_exchange_margin_waits_for_a_latest_day_only_one_exchange_published() -> None:
    scalars = margin_adapter(PARTIAL_LATEST_DAY).margin_financing_sse_szse(
        start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
    )

    assert {(item.period_end, item.dimensions["measure"], item.value) for item in scalars} == {
        ("2026-09-23", "financing_balance", 3.0),
        ("2026-09-23", "financing_buy_amount", 0.3),
    }


def test_all_exchange_margin_does_not_sum_a_latest_day_missing_exchanges() -> None:
    """A partial sum would halve the balance and pass for the day's value."""
    scalars = margin_adapter(PARTIAL_LATEST_DAY).margin_financing(
        start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
    )

    assert {item.period_end for item in scalars} == {"2026-09-23"}


def margin_receipt() -> AcquisitionReceipt:
    moment = datetime(2026, 9, 25, 6, tzinfo=UTC)
    return AcquisitionReceipt(
        acquisition_id="acquisition-fixture",
        provider="tushare",
        api_name="margin",
        parameters={"start_date": "20260923", "end_date": "20260924"},
        fields="trade_date,exchange_id,rzye,rzmre",
        parser_version="tushare-context-parser-v0002",
        started_at=moment,
        received_at=moment,
        validated_at=moment,
        state="validated",
        raw_hash=None,
        normalized_hash=None,
        error_type=None,
    )


def test_all_exchange_margin_receipt_recheck_waits_for_the_partial_latest_day() -> None:
    raw = json.dumps(margin_response(PARTIAL_LATEST_DAY)).encode()

    scalars = parse_margin_acquisition(margin_receipt(), raw)

    assert {item.period_end for item in scalars} == {"2026-09-23"}


def test_margin_receipt_recheck_still_requires_a_successful_response() -> None:
    raw = json.dumps({**margin_response(PARTIAL_LATEST_DAY[:3]), "code": 40203}).encode()

    with pytest.raises(ValueError, match="tushare_source_failed"):
        parse_margin_acquisition(margin_receipt(), raw)


def test_margin_validates_the_partial_latest_day_before_waiting_for_it() -> None:
    """Waiting is for exchanges yet to report, not for rows that are wrong."""
    rows = [*PARTIAL_LATEST_DAY, ["20260924", "SSE", 110, 11]]

    with pytest.raises(ValueError, match="tushare_margin_duplicate_exchange_day"):
        margin_adapter(rows).margin_financing_sse_szse(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
        )
    with pytest.raises(ValueError, match="tushare_margin_duplicate_exchange_day"):
        margin_adapter(rows).margin_financing(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
        )


def test_margin_waits_only_for_the_day_the_query_asked_up_to() -> None:
    """A partial day the source has stopped at, short of the requested end, is incomplete."""
    for fetch in ("margin_financing", "margin_financing_sse_szse"):
        with pytest.raises(ValueError, match="tushare_margin_exchange_coverage_incomplete"):
            getattr(margin_adapter(PARTIAL_LATEST_DAY), fetch)(
                start_date=date(2026, 9, 23), end_date=date(2026, 9, 25)
            )


def test_margin_still_rejects_an_earlier_day_missing_an_exchange() -> None:
    rows = [
        ["20260923", "SSE", 100, 10],
        ["20260924", "SSE", 110, 11],
        ["20260924", "SZSE", 210, 21],
        ["20260924", "BSE", 51, 5],
    ]

    for fetch in ("margin_financing", "margin_financing_sse_szse"):
        with pytest.raises(ValueError, match="tushare_margin_exchange_coverage_incomplete"):
            getattr(margin_adapter(rows), fetch)(
                start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
            )


def test_margin_still_rejects_an_unknown_exchange_on_the_latest_day() -> None:
    rows = [*PARTIAL_LATEST_DAY[:3], ["20260924", "NYSE", 110, 11]]

    with pytest.raises(ValueError, match="tushare_margin_exchange_invalid"):
        margin_adapter(rows).margin_financing_sse_szse(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
        )
    with pytest.raises(ValueError, match="tushare_margin_exchange_invalid"):
        margin_adapter(rows).margin_financing(
            start_date=date(2026, 9, 23), end_date=date(2026, 9, 24)
        )
