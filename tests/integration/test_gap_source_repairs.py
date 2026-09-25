"""Gap sources 2026-09-25: repairs behind the remaining gaps of the effective catalog.

One manual full run on model-v0013 with offline TuShare and official doubles; each test
reads what that run holds, and how its gap list explains what it could not hold.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.integration.test_core_history_refresh import historical_response

TARGET = date(2026, 8, 3)
# Tuesday 09:00 in Shanghai: the Monday closes, US closes included, are all due.
CLOCK = datetime(2026, 8, 4, 1, tzinfo=UTC)


def _weekdays(payload: dict[str, Any]) -> list[date]:
    start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
    end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]


def _response(fields: list[str], items: list[list[object]]) -> bytes:
    return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()


def treasury_response(payload: dict[str, Any]) -> bytes:
    return _response(
        ["date", "y2", "y10"],
        [[day.strftime("%Y%m%d"), 3.5, 4.25] for day in _weekdays(payload)],
    )


WARRANT_UNITS = {"CF": "张", "TA": "张", "SC": "桶"}


def warrant_response(payload: dict[str, Any]) -> bytes:
    """Cotton comes back as several rows per warehouse, the others one row each."""
    symbol = payload["params"]["symbol"]
    exchange = {"CF": "CZCE", "PTA": "CZCE", "SC": "INE"}.get(symbol, "SHFE")
    unit = WARRANT_UNITS.get("TA" if symbol == "PTA" else symbol, "吨")
    lots = (10, 10, 5) if symbol == "CF" else (20,)
    return _response(
        ["trade_date", "symbol", "warehouse", "pre_vol", "vol", "vol_chg", "unit", "exchange"],
        [
            [day.strftime("%Y%m%d"), symbol, f"{symbol}-warehouse", None, lot, 0, unit, exchange]
            for day in _weekdays(payload)
            for lot in lots
        ],
    )


VIX_CSV = (
    b"DATE,OPEN,HIGH,LOW,CLOSE\n"
    b"07/30/2026,15.10,15.60,14.90,15.20\n"
    b"07/31/2026,15.20,16.10,15.00,16.05\n"
    b"08/03/2026,16.00,16.40,15.70,15.95\n"
)
# The CFETS intraday file as it stood after the night session of Monday 3 August closed.
CFETS_JSON = json.dumps(
    {
        "data": {
            "closeSpotPrice": "7.1802",
            "spotPriceStr": "7.1790",
            "lastDate": "2026-08-04 3:00",
            "chartsDataStr": '[ {"time" : "09:30",spotPrice : 7.1850} , '
            '{"time" : " ",spotPrice : 7.1802} , {"time" : "03:00",spotPrice : 7.1790}]',
        }
    }
).encode()


class OfficialFile(BytesIO):
    status = 200

    def __init__(self, url: str, content: bytes) -> None:
        super().__init__(content)
        self.url = url

    def geturl(self) -> str:
        return self.url


def official_quote(request: Any, *, timeout: float) -> OfficialFile:
    url = request.full_url
    if url.startswith("https://cdn.cboe.com/"):
        return OfficialFile(url, VIX_CSV)
    if url.startswith("https://www.chinamoney.com.cn/"):
        return OfficialFile(url, CFETS_JSON)
    raise OSError("offline")


# Breadth: three ordinary shares, all long listed, and a B share outside the members.
SHARES = {"600000.SH": 10.5, "000001.SZ": 9.5, "920001.BJ": 10.0, "900901.SH": 11.0}
SUFFIX = {"SHFE": "SHF", "DCE": "DCE", "CZCE": "ZCE", "INE": "INE"}


def breadth_response(payload: dict[str, Any]) -> bytes:
    api_name, params = payload["api_name"], payload["params"]
    if api_name == "stock_basic":
        listed = [code for code in SHARES if params["list_status"] == "L"]
        rows = [[code, params["list_status"], "20000104", None] for code in listed]
        return _response(["ts_code", "list_status", "list_date", "delist_date"], rows)
    day = params["trade_date"]
    if api_name == "daily":
        rows = [[code, day, close, 10.0, 100.0, 1000.0] for code, close in SHARES.items()]
        return _response(["ts_code", "trade_date", "close", "pre_close", "vol", "amount"], rows)
    rows = [[code, day, close, 10.0, 10.0, 300.0, 0.0] for code, close in SHARES.items()]
    return _response(
        ["ts_code", "trade_date", "close_qfq", "ma_qfq_90", "ma_qfq_250", "topdays", "lowdays"],
        rows,
    )


def futures_response(payload: dict[str, Any]) -> bytes:
    """One contract a month for each product, every settlement 0.5% above the last."""
    api_name, params = payload["api_name"], payload["params"]
    if api_name == "fut_basic":
        product, exchange = params["fut_code"], params["exchange"]
        unit = "桶" if product == "SC" else "吨"
        months = [f"{year}{month:02d}" for year in (2026, 2027) for month in range(1, 13)]
        return _response(
            [
                "ts_code",
                "symbol",
                "exchange",
                "fut_code",
                "d_month",
                "list_date",
                "delist_date",
                "quote_unit",
                "per_unit",
                "trade_unit",
            ],
            [
                [
                    f"{product}{m[2:]}.{SUFFIX[exchange]}",
                    f"{product}{m[2:]}",
                    exchange,
                    product,
                    m,
                    "20250101",
                    f"{m}15",
                    f"人民币元/{unit}",
                    10,
                    unit,
                ]
                for m in months
            ],
        )
    days = [
        datetime.strptime(params["start_date"], "%Y%m%d").date() + timedelta(days=n)
        for n in range(
            (
                datetime.strptime(params["end_date"], "%Y%m%d")
                - datetime.strptime(params["start_date"], "%Y%m%d")
            ).days
            + 1
        )
    ]
    if api_name == "fut_trade_cal":
        return _response(
            ["exchange", "cal_date", "is_open"],
            [[params["exchange"], d.strftime("%Y%m%d"), int(d.weekday() < 5)] for d in days],
        )
    return _response(
        ["ts_code", "trade_date", "pre_settle", "settle"],
        [[params["ts_code"], d.strftime("%Y%m%d"), 100.0, 100.5] for d in days if d.weekday() < 5],
    )


class FixtureOpener:
    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        api_name = payload["api_name"]
        if api_name == "us_tycr":
            return BytesIO(treasury_response(payload))
        if api_name == "fut_wsr":
            return BytesIO(warrant_response(payload))
        if api_name in {"stock_basic", "daily", "stk_factor_pro"}:
            return BytesIO(breadth_response(payload))
        if api_name in {"fut_basic", "fut_trade_cal", "fut_daily"}:
            return BytesIO(futures_response(payload))
        if api_name == "index_dailybasic":
            # A delivery for another period than asked: refused by its structure check.
            return BytesIO(
                _response(
                    ["ts_code", "trade_date", "turnover_rate", "pe", "pb"],
                    [[payload["params"]["ts_code"], "20200102", 1.0, 12.0, 1.2]],
                )
            )
        code = payload["params"].get("ts_code")
        if api_name != "trade_cal" and code not in {"000985.CSI", "000012.SH", "NHII.NH"}:
            raise OSError("fixture_context_unavailable")
        return BytesIO(historical_response(payload))


@pytest.fixture(scope="module")
def completed(
    tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest
) -> Iterator[tuple[RuntimePaths, str]]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        install_runtime_clock(monkeypatch, request, CLOCK)
        monkeypatch.setattr(
            "pring_cycle.eia_html.open_no_redirects",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
        )
        monkeypatch.setattr("pring_cycle.quote_sources.open_no_redirects", official_quote)
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("gap-sources") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        models = ModelRepository(paths.database)
        models.register(effective_model_manifest())
        models.activate("model-v0013", explicitly_approved=True)
        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
        )
        run = RunRepository(paths.database).submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id="gap-source-repairs",
            model_version_id="model-v0013",
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        yield paths, run.run_id


def latest_values(paths: RuntimePaths, metric_id: str) -> dict[str, float]:
    points = EvidenceRepository(paths.database).metric_series(
        metric_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    latest = max((p.period_end for p in points), default=None)
    return {
        json.dumps(p.dimensions, sort_keys=True): p.selected_value
        for p in points
        if p.period_end == latest and p.selected_value is not None
    }


def gaps(paths: RuntimePaths) -> dict[str, dict[str, object]]:
    projection = ProjectionSetRepository(paths.database).current()
    assert projection is not None
    return {
        str(item["metric_id"]): item for item in projection.datasets["cycle_overview"]["gap_list"]
    }


def test_treasury_yields_are_held_from_tushare_us_tycr(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    assert latest_values(paths, "UST2Y_NOMINAL_YIELD") == {"{}": 3.5}
    assert latest_values(paths, "UST10Y_NOMINAL_YIELD") == {"{}": 4.25}
    listed = gaps(paths)
    assert {"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD", "UST_2S10S_SPREAD"}.isdisjoint(listed)


def test_cotton_warrants_are_held_as_warehouse_totals(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    held = latest_values(paths, "CN_FUTURES_WARRANTS")
    cotton = {
        json.loads(key)["measure"]: value
        for key, value in held.items()
        if json.loads(key)["symbol"] == "CF"
    }
    assert cotton == {"registered_receipts": 25.0, "registered_receipts_change": 0.0}
    assert "CN_FUTURES_WARRANTS" not in gaps(paths)


def test_breadth_is_held_from_tushare_quotes_and_factors(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    universe = '"universe": "point_in_time_traded_a_shares"'
    advances = latest_values(paths, "CN_EQ_ADV_DEC")
    # 600000 advances, 000001 declines, 920001 is flat; the B share is not a member.
    assert advances['{"measure": "advances", ' + universe + "}"] == 1.0
    assert advances['{"measure": "participants", ' + universe + "}"] == 3.0
    assert latest_values(paths, "CN_EQ_ABOVE_MA250") == {
        '{"measure": "above_ma_share", ' + universe + "}": pytest.approx(100 / 3)
    }
    listed = gaps(paths)
    for metric_id in (
        "CN_EQ_ADV_DEC",
        "CN_EQ_AD_RATIO",
        "CN_EQ_ADV_AMOUNT_SHARE",
        "CN_EQ_NEW_HIGH_LOW_90",
        "CN_EQ_NEW_HIGH_LOW_250",
        "CN_EQ_ABOVE_MA90",
        "CN_EQ_ABOVE_MA250",
    ):
        assert metric_id not in listed, listed.get(metric_id)


def test_the_basket_is_chained_from_its_base_on_settlements(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    sessions = sum(
        (date(2026, 3, 6) + timedelta(days=n)).weekday() < 5
        for n in range(1, (TARGET - date(2026, 3, 6)).days + 1)
    )
    level = latest_values(paths, "CN_COMMODITY_EX_HOG_BASKET")
    assert level == {
        '{"formula_version": "ex-hog-calendar-settlement-v0003"}': pytest.approx(
            1000 * 1.005**sessions
        )
    }
    assert {"CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"}.isdisjoint(
        gaps(paths)
    )


def test_values_refused_at_ingest_are_listed_with_the_reason_code(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    valuation = gaps(paths)["CN_INDEX_VALUATION"]

    assert valuation["category"] == "ingest_rejected"
    assert valuation["reason"] == "tushare_response_period_mismatch"
    # No web page carries it: a property of the gap, not why it is missing.
    assert valuation["no_web_fallback"] is True


def test_a_source_that_did_not_answer_is_listed_as_fetch_failed(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    dr007 = gaps(paths)["CN_DR007"]

    assert dr007["category"] == "fetch_failed"
    assert dr007["no_web_fallback"] is True
    assert "no_searchable_source" not in {item["category"] for item in gaps(paths).values()}


def test_sox_is_a_license_gap_that_is_never_searched(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    sox = gaps(paths)["NASDAQ_SOX_INDEX"]

    assert (sox["category"], sox["reason"]) == ("license_missing", "restricted_license")
    with sqlite3.connect(paths.database) as connection:
        searched = connection.execute(
            "SELECT count(*) FROM retrieval_attempt WHERE metric_id='NASDAQ_SOX_INDEX' "
            "AND outcome <> 'not_attempted'"
        ).fetchone()[0]
    assert searched == 0


def test_vix_is_held_from_the_cboe_history_file(completed: tuple[RuntimePaths, str]) -> None:
    paths, _run_id = completed

    assert latest_values(paths, "CBOE_VIX_INDEX") == {"{}": 15.95}
    assert "CBOE_VIX_INDEX" not in gaps(paths)


def test_usdcny_1630_close_is_held_from_cfets_not_its_night_close(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    assert latest_values(paths, "CN_USDCNY_CLOSE_1630") == {"{}": 7.1802}
    assert "CN_USDCNY_CLOSE_1630" not in gaps(paths)
    with sqlite3.connect(paths.database) as connection:
        searched = connection.execute(
            "SELECT count(*) FROM retrieval_attempt WHERE metric_id IN "
            "('CN_USDCNY_CLOSE_1630', 'CBOE_VIX_INDEX') AND channel IN ('tavily', 'exa', "
            "'ai_websearch') AND outcome <> 'not_attempted'"
        ).fetchone()[0]
    assert searched == 0
