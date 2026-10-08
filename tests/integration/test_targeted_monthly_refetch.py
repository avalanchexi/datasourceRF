"""A gap's TuShare refetch asks for what the catalog registers from TuShare (lookback L03).

A full run's direct refresh takes social financing's annual flow and month-end stock, and
M1/M2's balances and growth without month-on-month changes, when the catalog registers
those reviewed deliveries. A gap's refetch of one month used the old methods instead: they
deliver a monthly increment and month-on-month changes no registered contract supports, so
each such delivery was refused whole (v0015's run refused all 13 of its single months).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import own_acquisitions
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION, ModelRepository, effective_model_manifest
from pring_cycle.retrieval import RetrievalAdapterResponse
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.targeted_context import retrieve_tushare_context
from tests.conftest import install_runtime_clock

CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])
CLOCK = datetime(2026, 8, 4, 1, tzinfo=UTC)
# Every field either method may ask for; a response carries just the ones asked.
VALUES = {
    "sf_month": {"inc_month": 51300.0, "inc_cumval": 70600.0, "stk_endval": 426.0},
    "cn_m": {
        "m1": 1100000.0,
        "m1_yoy": 4.5,
        "m1_mom": 0.3,
        "m2": 3300000.0,
        "m2_yoy": 7.0,
        "m2_mom": 0.6,
    },
}


class MonthlyOnly:
    asked: list[dict[str, Any]] = []

    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        self.asked.append(payload)
        fields = payload["fields"].split(",")
        row = {"month": payload["params"]["start_m"], **VALUES[payload["api_name"]]}
        return BytesIO(
            json.dumps(
                {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields]]}}
            ).encode()
        )


class PassThroughLedger:
    def __init__(self, database: Path, *, scope_run: RunRecord | None = None) -> None:
        pass

    def trace_acquisition(
        self,
        run_id: str,
        channel: str,
        release_event_id: str,
        query: str,
        operation: Callable[[Callable[[str], None]], RetrievalAdapterResponse],
        *,
        defer_completion: bool = False,
    ) -> RetrievalAdapterResponse:
        return operation(lambda acquisition_id: None)

    def complete(self, request_id: str, *, outcome: str, classification: str) -> None:
        pass


def refetch(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    root: Path,
    metric_id: str,
    period: str,
) -> tuple[RuntimePaths, RetrievalAdapterResponse]:
    install_runtime_clock(monkeypatch, request, CLOCK)
    MonthlyOnly.asked = []
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *_: MonthlyOnly())
    # What is under test is the refetch's acquisition, not the retrieval budget ledger.
    monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
    paths = RuntimePaths.discover(root / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=date(2026, 8, 3).isoformat(),
        client_request_id="targeted-monthly-refetch",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )
    family = "pbc_social_financing" if metric_id == "CN_SF_TOTAL" else "pbc_money"
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(f"{family}:{period}", (metric_id,), period, "P1", None),
    )
    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        response = retrieve_tushare_context(
            paths, run.run_id, "fixture-secret", scope_run=scope_run
        )
    return paths, response


def held(paths: RuntimePaths, metric_id: str) -> dict[tuple[str, ...], tuple[str, str, float]]:
    return {
        tuple(sorted(p.dimensions.values())): (p.period_start, p.period_end, p.selected_value)
        for p in EvidenceRepository(paths.database).metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        if p.selected_value is not None
    }


def ingest_results(paths: RuntimePaths) -> list[tuple[str, str | None]]:
    with sqlite3.connect(paths.database) as connection:
        return connection.execute(
            "SELECT ingest_result, ingest_rejection_reason FROM acquisition_request"
        ).fetchall()


@pytest.mark.parametrize(
    ("period", "year_start"),
    [
        # January's year to date is the month itself, still dated from the year's start.
        pytest.param("2026-01", "2026-01-01", id="january"),
        # December's closes the year before the target's.
        pytest.param("2025-12", "2025-01-01", id="december"),
        pytest.param("2026-06", "2026-01-01", id="mid-year"),
    ],
)
def test_a_social_financing_refetch_holds_the_annual_flow_and_the_stock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    period: str,
    year_start: str,
) -> None:
    paths, response = refetch(monkeypatch, request, tmp_path, "CN_SF_TOTAL", period)

    assert [payload["fields"] for payload in MonthlyOnly.asked] == ["month,inc_cumval,stk_endval"]
    assert ingest_results(paths) == [("accepted", None)]
    month_start = f"{period}-01"
    month_end = month_start[:8] + ("31" if period[5:] in {"01", "12"} else "30")
    assert held(paths, "CN_SF_TOTAL") == {
        ("ytd_increment",): (year_start, month_end, 70600.0),
        ("stock_end",): (month_start, month_end, 4260000.0),
    }
    # The stock's growth is the PBC's alone and not required of the total by itself.
    assert (response.status, response.classification) == ("verified", "complete_model_input")


def test_a_money_refetch_leaves_out_the_month_on_month_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths, response = refetch(monkeypatch, request, tmp_path, "CN_M1_M2", "2026-06")

    assert [payload["fields"] for payload in MonthlyOnly.asked] == ["month,m1,m1_yoy,m2,m2_yoy"]
    assert ingest_results(paths) == [("accepted", None)]
    assert set(held(paths, "CN_M1_M2")) == {
        ("balance", "m1"),
        ("m1", "yoy"),
        ("balance", "m2"),
        ("m2", "yoy"),
    }
    assert (response.status, response.classification) == ("verified", "complete_model_input")
