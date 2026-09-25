"""Ticket 26: the two-exchange margin identity has a TuShare path; PMI spreads are monthly."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from typing import Any

import pytest

from pring_cycle.catalog import CNY030_OPTIONAL_MIGRATION, migrated_catalog
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.freshness import batch_freshness
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.worker import process_pending_run
from tests.integration.test_core_history_refresh import historical_response

TARGET = date(2026, 8, 3)
EXCHANGES = {"SSE": (1.0e12, 5.0e10), "SZSE": (0.9e12, 4.0e10), "BSE": (7.0e9, 3.0e8)}


def margin_response(payload: dict[str, Any]) -> bytes:
    start = datetime.strptime(payload["params"]["start_date"], "%Y%m%d").date()
    end = datetime.strptime(payload["params"]["end_date"], "%Y%m%d").date()
    items = [
        [(start + timedelta(days=i)).strftime("%Y%m%d"), exchange, balance, buy]
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
        for exchange, (balance, buy) in EXCHANGES.items()
    ]
    fields = ["trade_date", "exchange_id", "rzye", "rzmre"]
    return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()


@pytest.fixture(scope="module")
def completed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[RuntimePaths, str]]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "pring_cycle.eia_html.open_no_redirects",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")),
        )
        paths = RuntimePaths.discover(tmp_path_factory.mktemp("margin") / "runtime")
        initialize_runtime(paths)
        paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
        models = ModelRepository(paths.database)
        models.register(effective_model_manifest())
        models.activate("model-v0013", explicitly_approved=True)

        class FixtureOpener:
            def open(self, request: Any, *, timeout: int) -> BytesIO:
                payload = json.loads(request.data)
                if payload["api_name"] == "margin":
                    return BytesIO(margin_response(payload))
                code = payload["params"].get("ts_code")
                if payload["api_name"] != "trade_cal" and code not in {
                    "000985.CSI",
                    "000012.SH",
                    "NHII.NH",
                }:
                    raise OSError("fixture_context_unavailable")
                return BytesIO(historical_response(payload))

        monkeypatch.setattr("pring_cycle.source_adapters.build_opener", FixtureOpener)
        monkeypatch.setattr(
            "pring_cycle.tushare_context.build_opener", lambda *handlers: FixtureOpener()
        )
        run = RunRepository(paths.database).submit_manual_full(
            target_business_date=TARGET.isoformat(),
            client_request_id="margin-sse-szse",
            model_version_id="model-v0013",
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        yield paths, run.run_id


def test_two_exchange_margin_is_delivered_by_tushare_margin(
    completed: tuple[RuntimePaths, str],
) -> None:
    paths, _run_id = completed

    points = EvidenceRepository(paths.database).metric_series(
        "CN_MARGIN_BALANCE_SSE_SZSE",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=EFFECTIVE_CATALOG_VERSION,
    )
    latest = {
        p.dimensions["measure"]: p.selected_value for p in points if p.period_end == str(TARGET)
    }

    # Beijing is excluded: 1.0e12 + 0.9e12 yuan is 19,000 hundred million.
    assert latest == pytest.approx({"financing_balance": 19000.0, "financing_buy_amount": 900.0})
    assert {p.dimensions["scope"] for p in points} == {"sse_szse"}


def test_two_exchange_margin_is_judged_for_freshness(completed: tuple[RuntimePaths, str]) -> None:
    paths, run_id = completed

    row = batch_freshness(paths.database, run_id)["CN_MARGIN_BALANCE_SSE_SZSE"]

    # Judged against its registered cadence (the run's clock is today, well after 08-03).
    assert row["source"] == "tushare:margin"
    assert row["held_period"] == str(TARGET)
    assert row["status"] not in {"unconfigured", "missing"}


def test_pmi_spreads_are_monthly_in_the_effective_catalog() -> None:
    catalog = migrated_catalog({"metric_identity_migration": CNY030_OPTIONAL_MIGRATION})

    assert catalog["CN_ORDER_INVENTORY_SPREAD"].frequency == "monthly"
    assert catalog["CN_PRODUCTION_ORDER_SPREAD"].frequency == "monthly"
