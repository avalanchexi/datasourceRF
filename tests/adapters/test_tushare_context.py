from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import analytical_model_v0002_manifest
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import (
    ContextScalar,
    TushareContextAdapter,
    ingest_context_scalars,
    summarize_context_source_smoke,
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


def test_social_financing_contract_preserves_flow_and_normalizes_stock_unit() -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport(
            {
                "sf_month": response(
                    [
                        {
                            "month": "202607",
                            "inc_month": 5282.0,
                            "inc_cumval": 220800.0,
                            "stk_endval": 365.77,
                        }
                    ]
                )
            }
        ),
    )

    scalars = adapter.social_financing(start_month="202607", end_month="202607")

    assert {
        (item.source_field, item.dimensions["measure"], item.value, item.unit)
        for item in scalars
    } == {
        ("inc_month", "monthly_increment", 5282.0, "hundred_million_cny"),
        ("inc_cumval", "ytd_increment", 220800.0, "hundred_million_cny"),
        ("stk_endval", "stock_end", 3657700.0, "hundred_million_cny"),
    }
    assert {item.period_end for item in scalars} == {"2026-07-31"}


def test_futures_warrant_contract_preserves_three_measures_and_rejects_hog() -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport(
            {
                "fut_wsr": response(
                    [
                        {
                            "trade_date": "20260828",
                            "symbol": "CU",
                            "warehouse": "上海期货交易所",
                            "pre_vol": 5000,
                            "vol": 4800,
                            "vol_chg": -200,
                            "unit": "吨",
                            "exchange": "SHFE",
                        }
                    ]
                )
            }
        ),
    )

    scalars = adapter.futures_warrants(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        symbol="CU",
    )

    assert {
        (item.source_field, item.dimensions["measure"], item.value)
        for item in scalars
    } == {
        ("pre_vol", "previous_registered_receipts", 5000.0),
        ("vol", "registered_receipts", 4800.0),
        ("vol_chg", "registered_receipts_change", -200.0),
    }
    assert {item.unit for item in scalars} == {"tonne"}
    assert {item.dimensions["symbol"] for item in scalars} == {"CU"}
    with pytest.raises(ValueError, match="tushare_warrant_symbol_not_allowed"):
        adapter.futures_warrants(
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            symbol="LH",
        )


def test_futures_warrant_contract_accepts_live_exchange_shape_variants() -> None:
    requested_symbols: list[str] = []

    def live_shape_transport(payload: dict[str, Any]) -> dict[str, Any]:
        requested_symbol = str(payload["params"]["symbol"])
        requested_symbols.append(requested_symbol)
        if requested_symbol == "SC":
            return response(
                [
                    {
                        "trade_date": "20260828",
                        "symbol": "SC",
                        "warehouse": "中质含硫原油",
                        "pre_vol": None,
                        "vol": 1200,
                        "vol_chg": -50,
                        "unit": "桶",
                        "exchange": "INE",
                    }
                ]
            )
        assert requested_symbol == "PTA"
        return response(
            [
                {
                    "trade_date": "20260828",
                    "symbol": "PTA",
                    "warehouse": "郑州商品交易所",
                    "pre_vol": None,
                    "vol": 800,
                    "vol_chg": 20,
                    "unit": "张",
                    "exchange": "CZCE",
                }
            ]
        )

    adapter = TushareContextAdapter("fixture-token", transport=live_shape_transport)

    crude = adapter.futures_warrants(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        symbol="SC",
    )
    pta = adapter.futures_warrants(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        symbol="TA",
    )

    assert requested_symbols == ["SC", "PTA"]
    assert {(item.source_field, item.value, item.unit) for item in crude} == {
        ("vol", 1200.0, "barrel"),
        ("vol_chg", -50.0, "barrel"),
    }
    assert {item.dimensions["symbol"] for item in pta} == {"TA"}
    assert {item.source_field for item in pta} == {"vol", "vol_chg"}


def test_gdp_contract_keeps_reported_cumulative_levels_distinct_from_quarter_yoy() -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport(
            {
                "cn_gdp": response(
                    [
                        {
                            "quarter": "2026Q2",
                            "gdp": 660000.0,
                            "gdp_yoy": 5.2,
                            "pi": 30000.0,
                            "pi_yoy": 3.1,
                            "si": 230000.0,
                            "si_yoy": 4.8,
                            "ti": 400000.0,
                            "ti_yoy": 5.8,
                        }
                    ]
                )
            }
        ),
    )

    scalars = adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2")

    assert len(scalars) == 8
    assert {(item.dimensions["aggregate"], item.dimensions["measure"]) for item in scalars} == {
        (aggregate, measure)
        for aggregate in ("total", "primary", "secondary", "tertiary")
        for measure in ("nominal_ytd_level", "real_quarter_yoy")
    }
    total_level = next(
        item for item in scalars if item.dimensions == {
            "aggregate": "total",
            "measure": "nominal_ytd_level",
        }
    )
    total_yoy = next(
        item for item in scalars if item.dimensions == {
            "aggregate": "total",
            "measure": "real_quarter_yoy",
        }
    )
    assert (total_level.period_start, total_level.period_end, total_level.unit) == (
        "2026-01-01",
        "2026-06-30",
        "hundred_million_cny",
    )
    assert (total_yoy.period_start, total_yoy.period_end, total_yoy.unit) == (
        "2026-04-01",
        "2026-06-30",
        "percent",
    )


def test_treasury_contract_uses_nominal_two_and_ten_year_yields() -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport(
            {
                "us_tycr": response(
                    [{"date": "20260828", "y2": 3.62, "y10": 4.23}]
                )
            }
        ),
    )

    scalars = adapter.treasury_yields(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
    )

    assert {
        (item.metric_id, item.api_name, item.source_field, item.value, item.unit)
        for item in scalars
    } == {
        ("UST2Y_NOMINAL_YIELD", "us_tycr", "y2", 3.62, "percent"),
        ("UST10Y_NOMINAL_YIELD", "us_tycr", "y10", 4.23, "percent"),
    }
    assert {item.period_kind for item in scalars} == {"business_day"}


def test_candidate_context_uses_first_valid_fetch_as_conservative_public_availability(
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
    context = build_context_projection(
        repository,
        as_of=fetched_at,
        model_manifest=analytical_model_v0002_manifest(),
    )
    pmi_rows = context.macro["overheat"]["gaps"]  # type: ignore[index]

    assert result.observation_count == 8
    assert len(system_series) == 4
    assert len(public_series) == 4
    assert {
        claim.public_available_at
        for point in public_series
        for claim in point.claims
    } == {fetched_at}
    assert {row["freshness"] for row in pmi_rows if row["metric_id"] == "CN_PMI_ACTIVITY"} == {
        "awaiting_source_certification"
    }
    assert {row["value"] for row in pmi_rows if row["metric_id"] == "CN_PMI_ACTIVITY"} == {None}


def test_candidate_context_repeat_ingest_preserves_first_public_bound(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    scalar = ContextScalar(
        metric_id="CN_PMI_ACTIVITY",
        api_name="cn_pmi",
        source_field="pmi010000",
        period_kind="month",
        period_start="2026-07-01",
        period_end="2026-07-31",
        dimensions={"series": "manufacturing", "measure": "level"},
        value=49.3,
        unit="diffusion_index_points",
    )
    first_fetch = datetime(2026, 8, 1, 4, tzinfo=UTC)
    second_fetch = datetime(2026, 8, 2, 4, tzinfo=UTC)

    ingest_context_scalars(paths, (scalar,), fetched_at=first_fetch)
    repeated = ingest_context_scalars(paths, (scalar,), fetched_at=second_fetch)
    trace = EvidenceRepository(paths.database).trace(
        repeated.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=second_fetch,
    )

    assert trace.claims[0].public_available_at == first_fetch


def test_candidate_context_same_value_can_move_to_a_new_definition_version(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    scalar = ContextScalar(
        metric_id="CN_PMI_ACTIVITY",
        api_name="cn_pmi",
        source_field="pmi010000",
        period_kind="month",
        period_start="2026-07-01",
        period_end="2026-07-31",
        dimensions={"series": "manufacturing", "measure": "level"},
        value=49.3,
        unit="diffusion_index_points",
    )
    first_fetch = datetime(2026, 8, 1, 4, tzinfo=UTC)
    second_fetch = datetime(2026, 8, 2, 4, tzinfo=UTC)

    ingest_context_scalars(
        paths,
        (scalar,),
        fetched_at=first_fetch,
        definition_version="metric-catalog-v0001",
    )
    reingested = ingest_context_scalars(
        paths,
        (scalar,),
        fetched_at=second_fetch,
        definition_version="metric-catalog-v0002",
    )
    trace = EvidenceRepository(paths.database).trace(
        reingested.observation_ids[0],
        mode=AsOfMode.SYSTEM,
        as_of=second_fetch,
    )

    assert trace.definition_version == "metric-catalog-v0002"
    assert trace.claims[0].public_available_at == first_fetch


def test_candidate_context_revision_is_public_only_from_revision_fetch(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    scalar = ContextScalar(
        metric_id="CN_PMI_ACTIVITY",
        api_name="cn_pmi",
        source_field="pmi010000",
        period_kind="month",
        period_start="2026-07-01",
        period_end="2026-07-31",
        dimensions={"series": "manufacturing", "measure": "level"},
        value=49.3,
        unit="diffusion_index_points",
        public_available_at=datetime(2026, 8, 1, 3, tzinfo=UTC),
    )
    first_fetch = datetime(2026, 8, 1, 4, tzinfo=UTC)
    revision_fetch = datetime(2026, 8, 2, 4, tzinfo=UTC)
    first = ingest_context_scalars(paths, (scalar,), fetched_at=first_fetch)

    ingest_context_scalars(
        paths,
        (replace(scalar, value=50.1),),
        fetched_at=revision_fetch,
    )
    repository = EvidenceRepository(paths.database)
    before_revision = repository.query(
        first.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    after_revision = repository.query(
        first.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=revision_fetch,
    )

    assert before_revision.selected_value == 49.3
    assert after_revision.selected_value == 50.1


def test_context_source_smoke_summary_is_sanitized_and_content_addressed() -> None:
    sentinel = "secret-must-not-appear"
    result = summarize_context_source_smoke(
        "pmi",
        (
            ContextScalar(
                metric_id="CN_PMI_ACTIVITY",
                api_name="cn_pmi",
                source_field="pmi010000",
                period_kind="month",
                period_start="2026-07-01",
                period_end="2026-07-31",
                dimensions={"series": "manufacturing", "measure": "level"},
                value=49.3,
                unit="diffusion_index_points",
            ),
        ),
        network_requests=1,
    )

    assert result.status == "validated_candidate"
    assert result.api_names == ("cn_pmi",)
    assert result.metric_ids == ("CN_PMI_ACTIVITY",)
    assert result.first_period == result.last_period == "2026-07-31"
    assert result.observation_count == 1
    assert len(result.normalized_hash) == 64
    assert sentinel not in repr(result)
