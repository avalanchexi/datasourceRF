from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import (
    ContextScalar,
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
        (item.source_field, item.dimensions["measure"], item.value, item.unit) for item in scalars
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

    assert {(item.source_field, item.dimensions["measure"], item.value) for item in scalars} == {
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


@pytest.mark.parametrize("negative_field", ["pre_vol", "vol"])
def test_futures_warrant_rejects_negative_reported_quantity(negative_field: str) -> None:
    row = {
        "trade_date": "20260828",
        "symbol": "CU",
        "warehouse": "synthetic-warehouse",
        "pre_vol": 225,
        "vol": 225,
        "vol_chg": -10,
        "unit": "吨",
        "exchange": "SHFE",
    }
    row[negative_field] = -1
    adapter = TushareContextAdapter("fixture-token", transport=lambda _: response([row]))
    with pytest.raises(ValueError, match="tushare_warrant_quantity_negative"):
        adapter.futures_warrants(
            start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol="CU"
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
        raise AssertionError(f"unexpected symbol {requested_symbol}")

    adapter = TushareContextAdapter("fixture-token", transport=live_shape_transport)

    crude = adapter.futures_warrants(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        symbol="SC",
    )
    # TA and CF come from CZCE's own report (ADR-0032): TuShare is never asked for them.
    for czce_symbol in ("TA", "CF", "PTA"):
        with pytest.raises(ValueError, match="tushare_warrant_symbol_not_allowed"):
            adapter.futures_warrants(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28), symbol=czce_symbol
            )

    assert requested_symbols == ["SC"]
    assert {(item.source_field, item.value, item.unit) for item in crude} == {
        ("vol", 1200.0, "barrel"),
        ("vol_chg", -50.0, "barrel"),
    }


def test_futures_warrant_long_range_is_requested_in_non_overlapping_chunks() -> None:
    requested_ranges: list[tuple[date, date]] = []

    def chunk_transport(payload: dict[str, Any]) -> dict[str, Any]:
        params = payload["params"]
        chunk_start = datetime.strptime(str(params["start_date"]), "%Y%m%d").date()
        chunk_end = datetime.strptime(str(params["end_date"]), "%Y%m%d").date()
        requested_ranges.append((chunk_start, chunk_end))
        return response(
            [
                {
                    "trade_date": chunk_end.strftime("%Y%m%d"),
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

    adapter = TushareContextAdapter("fixture-token", transport=chunk_transport)
    scalars = adapter.futures_warrants(
        start_date=date(2026, 1, 20),
        end_date=date(2026, 8, 28),
        symbol="CU",
    )

    assert requested_ranges[0][0] == date(2026, 1, 20)
    assert requested_ranges[-1][1] == date(2026, 8, 28)
    assert all((end - start).days <= 30 for start, end in requested_ranges)
    assert all(
        current_start == previous_end + timedelta(days=1)
        for (_previous_start, previous_end), (current_start, _current_end) in zip(
            requested_ranges,
            requested_ranges[1:],
            strict=False,
        )
    )
    assert len(scalars) == len(requested_ranges) * 3


def test_futures_warrant_saturated_range_is_split_until_every_date_is_visible() -> None:
    def capped_transport(payload: dict[str, Any]) -> dict[str, Any]:
        params = payload["params"]
        start = str(params["start_date"])
        end = str(params["end_date"])
        if start != end:
            row: dict[str, object] = {
                "trade_date": start,
                "symbol": "PP",
                "warehouse": "大连商品交易所",
                "pre_vol": None,
                "vol": 800,
                "vol_chg": None,
                "unit": "吨",
                "exchange": "DCE",
            }
            return response([row] * 1_200)
        return response(
            [
                {
                    "trade_date": start,
                    "symbol": "PP",
                    "warehouse": "大连商品交易所",
                    "pre_vol": None,
                    "vol": 800,
                    "vol_chg": None,
                    "unit": "吨",
                    "exchange": "DCE",
                }
            ]
        )

    adapter = TushareContextAdapter("fixture-token", transport=capped_transport)

    scalars = adapter.futures_warrants(
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 28),
        symbol="PP",
    )

    assert {(item.period_end, item.source_field) for item in scalars} == {
        ("2026-08-27", "vol"),
        ("2026-08-28", "vol"),
    }
    assert adapter.network_requests == 3


def test_gdp_contract_keeps_levels_and_excludes_uncertified_yoy_semantics() -> None:
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

    assert len(scalars) == 4
    assert {(item.dimensions["aggregate"], item.dimensions["measure"]) for item in scalars} == {
        (aggregate, measure)
        for aggregate in ("total", "primary", "secondary", "tertiary")
        for measure in ("nominal_ytd_level",)
    }
    total_level = next(
        item
        for item in scalars
        if item.dimensions
        == {
            "aggregate": "total",
            "measure": "nominal_ytd_level",
        }
    )
    assert (total_level.period_start, total_level.period_end, total_level.unit) == (
        "2026-01-01",
        "2026-06-30",
        "hundred_million_cny",
    )


def test_treasury_contract_uses_nominal_two_and_ten_year_yields() -> None:
    adapter = TushareContextAdapter(
        "fixture-token",
        transport=transport({"us_tycr": response([{"date": "20260828", "y2": 3.62, "y10": 4.23}])}),
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


def test_market_index_margin_and_valuation_contracts_preserve_identity_and_units(
    tmp_path: Path,
) -> None:
    def market_transport(payload: dict[str, Any]) -> dict[str, Any]:
        api_name = str(payload["api_name"])
        params = payload["params"]
        if api_name in {"index_daily", "fut_index_daily"}:
            source_code = str(params["ts_code"])
            return response(
                [
                    {
                        "ts_code": source_code,
                        "trade_date": "20260828",
                        "close": 1234.5,
                    }
                ]
            )
        if api_name == "margin":
            return response(
                [
                    {
                        "trade_date": "20260828",
                        "exchange_id": exchange,
                        "rzye": balance,
                        "rzmre": buy_amount,
                    }
                    for exchange, balance, buy_amount in (
                        ("SSE", 100_000_000.0, 10_000_000.0),
                        ("SZSE", 200_000_000.0, 20_000_000.0),
                        ("BSE", 50_000_000.0, 5_000_000.0),
                    )
                ]
            )
        assert api_name == "index_dailybasic"
        return response(
            [
                {
                    "ts_code": str(params["ts_code"]),
                    "trade_date": "20260828",
                    "turnover_rate": 0.5,
                    "pe": 15.0,
                    "pb": 1.5,
                }
            ]
        )

    adapter = TushareContextAdapter("fixture-token", transport=market_transport)
    target = date(2026, 8, 28)

    indices = adapter.market_indices(start_date=target, end_date=target)
    margin = adapter.margin_financing(start_date=target, end_date=target)
    valuation = adapter.index_valuation(start_date=target, end_date=target)

    assert {item.metric_id for item in indices} == {
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_BOND_FULL_PRICE_CNY030",
        "CN_BOND_10Y_930916",
        "CN_COMMODITY_BROAD_NHCI",
    }
    assert {item.unit for item in indices} == {"index_points"}
    assert {(item.dimensions["measure"], item.value, item.unit) for item in margin} == {
        ("financing_balance", 3.5, "hundred_million_cny"),
        ("financing_buy_amount", 0.35, "hundred_million_cny"),
    }
    assert len(valuation) == 9
    assert {item.unit for item in valuation} == {"multiple", "percent"}

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        ingest_context_scalars(
            paths,
            indices,
            fetched_at=datetime(2026, 8, 28, 8, tzinfo=UTC),
            definition_version="metric-catalog-v0003",
        )


def test_candidate_context_repeat_ingest_preserves_unknown_public_time(
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

    assert trace.claims[0].parsed_public_available_at is None


def test_candidate_context_same_value_repairs_explicit_source_schedule(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    scalar = ContextScalar(
        metric_id="CN_EQUITY_CORE_000985",
        api_name="index_daily",
        source_field="close",
        period_kind="day",
        period_start="2026-08-28",
        period_end="2026-08-28",
        dimensions={},
        value=4450.1,
        unit="index_points",
    )
    first_fetch = datetime(2026, 8, 31, 4, tzinfo=UTC)
    scheduled_publication = datetime(2026, 8, 28, 7, 30, tzinfo=UTC)

    first = ingest_context_scalars(
        paths,
        (scalar,),
        fetched_at=first_fetch,
        definition_version="metric-catalog-v0003",
    )
    repaired = ingest_context_scalars(
        paths,
        (
            replace(
                scalar,
                release_at=scheduled_publication,
                public_available_at=scheduled_publication,
            ),
        ),
        fetched_at=first_fetch + timedelta(minutes=1),
        definition_version="metric-catalog-v0003",
    )
    repository = EvidenceRepository(paths.database)
    repaired_trace = repository.trace(
        repaired.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=scheduled_publication,
    )

    assert repaired.observation_ids == first.observation_ids
    assert repository.claim_count(first.observation_ids[0]) == 2
    assert repaired_trace.selected_value == 4450.1
    assert repaired_trace.claims[-1].public_available_at == scheduled_publication
    assert repaired_trace.claims[-1].supersedes_claim_id == first.claim_ids[0]


def test_explicit_source_schedule_does_not_reuse_conflicting_period_event(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    first_fetch = datetime(2026, 8, 31, 4, tzinfo=UTC)
    period = "2026-03-31"
    unscheduled = ContextScalar(
        metric_id="CN_FUTURES_WARRANTS",
        api_name="fut_wsr",
        source_field="vol",
        period_kind="business_day",
        period_start=period,
        period_end=period,
        dimensions={
            "symbol": "CU",
            "warehouse": "warehouse-a",
            "exchange": "SHFE",
            "measure": "registered_receipts",
        },
        value=100.0,
        unit="tonne",
    )
    scheduled_publication = datetime(2026, 4, 1, 0, tzinfo=UTC)
    scheduled = replace(
        unscheduled,
        dimensions={**unscheduled.dimensions, "warehouse": "warehouse-b"},
        value=200.0,
        release_at=scheduled_publication,
        public_available_at=scheduled_publication,
    )
    ingest_context_scalars(paths, (unscheduled,), fetched_at=first_fetch)

    result = ingest_context_scalars(
        paths,
        (scheduled,),
        fetched_at=first_fetch + timedelta(minutes=1),
    )
    trace = EvidenceRepository(paths.database).trace(
        result.observation_ids[0],
        mode=AsOfMode.PUBLIC,
        as_of=scheduled_publication,
    )

    assert result.observation_count == 1
    assert trace.claims[0].public_available_at == scheduled_publication


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
    assert trace.claims[0].parsed_public_available_at is None


def test_candidate_context_revision_without_new_time_remains_system_only(
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
    assert after_revision.selected_value == 49.3
    assert (
        repository.query(
            first.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=revision_fetch
        ).selected_value
        == 50.1
    )


def test_a_refused_call_is_a_source_failure_not_a_rejected_response() -> None:
    from pring_cycle.tushare_context import TushareSourceError

    adapter = TushareContextAdapter(
        "fixture-token", transport=lambda _: {"code": 2002, "msg": "权限不足", "data": None}
    )

    with pytest.raises(TushareSourceError, match="tushare_source_failed"):
        adapter.treasury_yields(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))


@pytest.mark.parametrize(
    ("code", "message", "reason", "classification"),
    [
        (2002, "拒绝", "tushare_source_failed:2002", None),
        (40203, "拒绝", "tushare_rate_limited", "rate_limited"),
        (
            40203,
            "抱歉，您访问接口(major_news)频率超限(40次/天)",
            "tushare_rate_limited",
            "rate_limited",
        ),
        # 40203 also answers a missing permission: no rate limit to wait out (ticket 22).
        (40203, "抱歉，您没有访问该接口的权限", "tushare_source_failed:40203", "forbidden"),
    ],
)
def test_a_refused_call_says_which_code_refused_it(
    code: int, message: str, reason: str, classification: str | None
) -> None:
    """Run findings 2026-09-28, ticket 02, and ticket 22: each refusal says its code, and
    40203 is told a rate limit or a missing permission by its message."""
    from pring_cycle.tushare_context import TushareSourceError

    adapter = TushareContextAdapter(
        "fixture-token", transport=lambda _: {"code": code, "msg": message, "data": None}
    )

    with pytest.raises(TushareSourceError) as refused:
        adapter.treasury_yields(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28))
    assert str(refused.value) == reason
    assert (refused.value.external_code, refused.value.classification) == (
        str(code),
        classification,
    )
