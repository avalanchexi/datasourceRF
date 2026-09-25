"""Gap sources 2026-09-25: repairs behind the remaining gaps of the effective catalog.

One manual full run on model-v0012 with offline TuShare and official doubles; each test
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


class FixtureOpener:
    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        api_name = payload["api_name"]
        if api_name == "us_tycr":
            return BytesIO(treasury_response(payload))
        if api_name == "fut_wsr":
            return BytesIO(warrant_response(payload))
        code = payload["params"].get("ts_code")
        if api_name == "fut_daily":
            # The retired close-return basket still computes; its claims no longer fit the
            # registered settlement contract (ticket 08) and are refused at ingest.
            return BytesIO(historical_response(payload))
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
        models.activate("model-v0012", explicitly_approved=True)
        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
        )
        run = RunRepository(paths.database).submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id="gap-source-repairs",
            model_version_id="model-v0012",
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


def test_values_refused_at_ingest_are_listed_with_the_reason_code(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    basket = gaps(paths)["CN_COMMODITY_EX_HOG_BASKET"]

    assert basket["category"] == "ingest_rejected"
    assert basket["reason"] == "registered_commodity_basket_source_identity_mismatch"
    # No web page carries a computed basket: a property of the gap, not why it is missing.
    assert basket["no_web_fallback"] is True


def test_a_source_that_did_not_answer_is_listed_as_fetch_failed(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    breadth = gaps(paths)["CN_EQ_ADV_DEC"]

    assert breadth["category"] == "fetch_failed"
    assert breadth["no_web_fallback"] is True
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
