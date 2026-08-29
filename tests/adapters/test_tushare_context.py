from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import (
    TushareContextAdapter,
    ingest_context_scalars,
)


def response(rows: list[dict[str, object]]) -> dict[str, Any]:
    fields = list(rows[0]) if rows else []
    return {
        "code": 0,
        "data": {"fields": fields, "items": [[row[key] for key in fields] for row in rows]},
    }


def transport(payloads: dict[str, dict[str, Any]]):  # type: ignore[no-untyped-def]
    def send(payload: dict[str, Any]) -> dict[str, Any]:
        return payloads[str(payload["api_name"])]

    return send


def test_pmi_contract_normalizes_activity_inventory_and_price_scalar_identities() -> None:
    payloads = {
        "cn_pmi": response(
            [
                {
                    "month": "202607",
                    "pmi010000": 49.3,
                    "pmi010400": 50.5,
                    "pmi010500": 49.8,
                    "pmi010700": 48.2,
                    "pmi011100": 50.1,
                    "pmi011200": 51.4,
                    "pmi011300": 49.5,
                    "pmi011400": 47.3,
                }
            ]
        )
    }
    adapter = TushareContextAdapter("fixture-token", transport=transport(payloads))

    scalars = adapter.pmi(start_month="202607", end_month="202607")

    assert len(scalars) == 8
    assert {
        (item.metric_id, tuple(sorted(item.dimensions.items())), item.source_field)
        for item in scalars
    } == {
        ("CN_PMI_ACTIVITY", (("measure", "level"), ("series", "manufacturing")), "pmi010000"),
        ("CN_PMI_ACTIVITY", (("measure", "level"), ("series", "production")), "pmi010400"),
        ("CN_PMI_ACTIVITY", (("measure", "level"), ("series", "new_orders")), "pmi010500"),
        ("CN_PMI_INVENTORY", (("measure", "level"), ("series", "raw_materials")), "pmi010700"),
        ("CN_PMI_ACTIVITY", (("measure", "level"), ("series", "purchase_volume")), "pmi011100"),
        ("CN_PMI_PRICES", (("measure", "level"), ("series", "purchase_prices")), "pmi011200"),
        ("CN_PMI_PRICES", (("measure", "level"), ("series", "output_prices")), "pmi011300"),
        ("CN_PMI_INVENTORY", (("measure", "level"), ("series", "finished_goods")), "pmi011400"),
    }
    assert {item.unit for item in scalars} == {"diffusion_index_points"}
    assert {item.period_end for item in scalars} == {"2026-07-31"}


def test_price_money_and_transmission_contracts_preserve_measure_dimensions() -> None:
    payloads = {
        "cn_cpi": response([{"month": "202607", "nt_yoy": 0.7, "nt_mom": 0.2, "nt_accu": 0.5}]),
        "cn_ppi": response(
            [
                {
                    "month": "202607",
                    "ppi_yoy": -0.6,
                    "ppi_mom": 0.1,
                    "ppi_accu": -1.2,
                    "ppi_mp_yoy": -0.4,
                    "ppi_mp_mom": 0.2,
                    "ppi_mp_accu": -1.0,
                    "ppi_cg_yoy": -0.9,
                    "ppi_cg_mom": 0.0,
                    "ppi_cg_accu": -1.4,
                }
            ]
        ),
        "cn_m": response(
            [
                {
                    "month": "202607",
                    "m1": 112.0,
                    "m1_yoy": 5.2,
                    "m1_mom": 0.8,
                    "m2": 350.0,
                    "m2_yoy": 8.1,
                    "m2_mom": 0.6,
                }
            ]
        ),
        "repo_daily": response(
            [
                {
                    "ts_code": "DR007.IB",
                    "trade_date": "20260828",
                    "repo_maturity": "DR007",
                    "weight": 1.42,
                }
            ]
        ),
        "shibor": response([{"date": "20260828", "on": 1.31, "1w": 1.45, "3m": 1.55}]),
    }
    adapter = TushareContextAdapter("fixture-token", transport=transport(payloads))

    prices = adapter.prices(start_month="202607", end_month="202607")
    money = adapter.money(start_month="202607", end_month="202607")
    transmission = adapter.transmission(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
    )

    assert len(prices) == 12
    assert {item.dimensions["measure"] for item in prices} == {
        "yoy",
        "mom",
        "cumulative_average_yoy",
    }
    assert len(money) == 6
    assert {item.dimensions["aggregate"] for item in money} == {"m1", "m2"}
    assert {item.unit for item in money} == {"hundred_million_cny", "percent"}
    assert {(item.metric_id, item.dimensions.get("tenor")) for item in transmission} == {
        ("CN_DR007", None),
        ("CN_SHIBOR_ON_1W_3M", "overnight"),
        ("CN_SHIBOR_ON_1W_3M", "1w"),
        ("CN_SHIBOR_ON_1W_3M", "3m"),
    }


def test_candidate_context_ingestion_is_system_visible_but_redacted_until_certified(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport(
            {
                "cn_pmi": response(
                    [
                        {
                            "month": "202607",
                            "pmi010000": 49.3,
                            "pmi010400": 50.5,
                            "pmi010500": 49.8,
                            "pmi010700": 48.2,
                            "pmi011100": 50.1,
                            "pmi011200": 51.4,
                            "pmi011300": 49.5,
                            "pmi011400": 47.3,
                        }
                    ]
                )
            }
        ),
    )
    fetched_at = datetime(2026, 8, 1, 4, tzinfo=UTC)

    result = ingest_context_scalars(
        paths,
        adapter.pmi(start_month="202607", end_month="202607"),
        fetched_at=fetched_at,
    )
    repository = EvidenceRepository(paths.database)
    system_series = repository.metric_series(
        "CN_PMI_ACTIVITY",
        mode=AsOfMode.SYSTEM,
        as_of=fetched_at,
    )
    public_series = repository.metric_series(
        "CN_PMI_ACTIVITY",
        mode=AsOfMode.PUBLIC,
        as_of=fetched_at,
    )
    context = build_context_projection(repository, as_of=fetched_at)
    pmi_rows = context.macro["overheat"]["gaps"]  # type: ignore[index]

    assert result.observation_count == 8
    assert len(system_series) == 4
    assert public_series == ()
    assert {row["freshness"] for row in pmi_rows if row["metric_id"] == "CN_PMI_ACTIVITY"} == {
        "awaiting_source_certification"
    }
    assert {row["value"] for row in pmi_rows if row["metric_id"] == "CN_PMI_ACTIVITY"} == {None}
