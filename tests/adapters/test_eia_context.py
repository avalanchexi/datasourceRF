from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pring_cycle.context_projection import build_context_projection
from pring_cycle.eia_context import (
    EiaPetroleumAdapter,
    ingest_eia_spot_prices,
)
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import analytical_model_v0002_manifest
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def eia_response(*, units: str = "Dollars per Barrel") -> dict[str, object]:
    return {
        "response": {
            "frequency": "daily",
            "data": [
                {
                    "period": "2026-08-27",
                    "series": "RBRTE",
                    "series-description": "Europe Brent Spot Price FOB",
                    "value": "71.25",
                    "units": units,
                },
                {
                    "period": "2026-08-27",
                    "series": "RWTC",
                    "series-description": "Cushing, OK WTI Spot Price FOB",
                    "value": "66.50",
                    "units": units,
                },
            ],
        }
    }


def test_eia_v2_contract_freezes_route_series_units_and_daily_identity() -> None:
    calls: list[dict[str, object]] = []

    def transport(parameters: dict[str, object]) -> dict[str, object]:
        calls.append(parameters)
        return eia_response()

    adapter = EiaPetroleumAdapter("fixture-eia-key", transport=transport)
    prices = adapter.spot_prices(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )

    assert calls == [
        {
            "api_key": "fixture-eia-key",
            "data[]": "value",
            "end": "2026-08-27",
            "facets[series][]": ("RBRTE", "RWTC"),
            "frequency": "daily",
            "length": "5000",
            "offset": "0",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "start": "2026-08-27",
        }
    ]
    assert {(item.metric_id, item.series_id, item.value, item.unit) for item in prices} == {
        ("EIA_BRENT_RBRTE", "RBRTE", 71.25, "usd_per_barrel"),
        ("EIA_WTI_RWTC", "RWTC", 66.5, "usd_per_barrel"),
    }


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda response: response["response"].update(frequency="weekly"), "frequency"),
        (
            lambda response: response["response"]["data"][0].update(series="BRENT"),
            "series_identity",
        ),
        (
            lambda response: response["response"]["data"][0].update(units="USD/bbl"),
            "unit",
        ),
        (
            lambda response: response["response"]["data"].append(
                dict(response["response"]["data"][0])
            ),
            "duplicate",
        ),
    ],
)
def test_eia_contract_fails_closed_on_schema_or_identity_drift(mutate, error: str) -> None:  # type: ignore[no-untyped-def]
    response = eia_response()
    mutate(response)
    adapter = EiaPetroleumAdapter("fixture-eia-key", transport=lambda _params: response)

    with pytest.raises(ValueError, match=f"eia_{error}"):
        adapter.spot_prices(
            start_date=date(2026, 8, 27),
            end_date=date(2026, 8, 27),
        )


def test_eia_ingest_is_traceable_but_redacted_until_source_certification(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = EiaPetroleumAdapter(
        "fixture-eia-key",
        transport=lambda _params: eia_response(),
    )
    prices = adapter.spot_prices(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )
    fetched_at = datetime(2026, 8, 28, tzinfo=UTC)

    ingested = ingest_eia_spot_prices(paths, prices, fetched_at=fetched_at)
    repository = EvidenceRepository(paths.database)
    trace = repository.trace(
        ingested.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=fetched_at,
    )
    public_trace = repository.trace(
        ingested.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=fetched_at,
    )
    context = build_context_projection(
        repository,
        as_of=fetched_at,
        model_manifest=analytical_model_v0002_manifest(),
    )
    oil_rows = [
        item
        for item in context.macro["international_context"]  # type: ignore[union-attr]
        if item["metric_id"] in {"EIA_BRENT_RBRTE", "EIA_WTI_RWTC"}
    ]

    assert trace.claims[0].provider == "U.S. Energy Information Administration"
    assert trace.claims[0].source_reference.startswith("eia:v2:petroleum/pri/spt:")
    assert public_trace.claims == ()
    assert trace.claims[0].public_available_at is None
    assert {item["status"] for item in oil_rows} == {"awaiting_source_certification"}
    assert {item["value"] for item in oil_rows} == {None}


def test_eia_repeat_ingest_keeps_public_availability_unknown(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    prices = EiaPetroleumAdapter(
        "fixture-eia-key",
        transport=lambda _params: eia_response(),
    ).spot_prices(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )
    first_fetch = datetime(2026, 8, 28, tzinfo=UTC)
    second_fetch = datetime(2026, 8, 29, tzinfo=UTC)

    ingest_eia_spot_prices(paths, prices, fetched_at=first_fetch)
    repeated = ingest_eia_spot_prices(paths, prices, fetched_at=second_fetch)
    trace = EvidenceRepository(paths.database).trace(
        repeated.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=second_fetch,
    )

    assert trace.claims[0].public_available_at is None


def test_eia_same_value_can_be_reingested_under_a_new_definition_version(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    prices = EiaPetroleumAdapter(
        "fixture-eia-key",
        transport=lambda _params: eia_response(),
    ).spot_prices(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )
    first_fetch = datetime(2026, 8, 28, tzinfo=UTC)
    second_fetch = datetime(2026, 8, 29, tzinfo=UTC)

    ingest_eia_spot_prices(
        paths,
        prices,
        fetched_at=first_fetch,
        definition_version="metric-catalog-v0001",
    )
    reingested = ingest_eia_spot_prices(
        paths,
        prices,
        fetched_at=second_fetch,
        definition_version="metric-catalog-v0002",
    )
    trace = EvidenceRepository(paths.database).trace(
        reingested.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=second_fetch,
    )

    assert trace.definition_version == "metric-catalog-v0002"
    assert trace.claims[0].public_available_at is None


def test_eia_revision_is_not_backdated_to_first_observation(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    prices = EiaPetroleumAdapter(
        "fixture-eia-key",
        transport=lambda _params: eia_response(),
    ).spot_prices(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )
    first_fetch = datetime(2026, 8, 28, tzinfo=UTC)
    revision_fetch = datetime(2026, 8, 29, tzinfo=UTC)
    first = ingest_eia_spot_prices(paths, prices, fetched_at=first_fetch)
    revised_prices = tuple(
        replace(price, value=72.0) if price.metric_id == "EIA_BRENT_RBRTE" else price
        for price in prices
    )

    ingest_eia_spot_prices(paths, revised_prices, fetched_at=revision_fetch)
    repository = EvidenceRepository(paths.database)
    before_revision = repository.query(
        first.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 12, tzinfo=UTC),
    )
    after_revision = repository.query(
        first.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=revision_fetch,
    )

    assert before_revision.selected_value is None
    assert after_revision.selected_value is None
    assert (
        repository.query(
            first.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=first_fetch
        ).selected_value
        == 71.25
    )
    assert (
        repository.query(
            first.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=revision_fetch
        ).selected_value
        == 72.0
    )


def test_eia_smoke_is_sanitized_and_never_exposes_the_api_key() -> None:
    secret = "sentinel-eia-api-key"
    result = EiaPetroleumAdapter(
        secret,
        transport=lambda _params: eia_response(),
    ).smoke(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
    )

    assert result.status == "validated_candidate"
    assert result.series_ids == ("RBRTE", "RWTC")
    assert result.observation_count == 2
    assert len(result.normalized_hash) == 64
    assert secret not in repr(result)
