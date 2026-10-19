"""A gap's refetch of one market index asks for that index alone (go-live leftovers 04).

The refetch asked TuShare for all six indices, then stored only the one it was after: the
check that the stored values are exactly what the originals hold compared six parsed
originals with one output, so every such refetch was refused as a value mismatch although
the index's value was the same on both sides (run-153de306, 2026-10-19). What is asked,
checked and stored is now one scope; a value differing from its original is still refused.
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
from pring_cycle.tushare_context import ContextScalar, TushareContextAdapter
from tests.conftest import install_runtime_clock

CURRENT_MODEL = str(effective_model_manifest()["model_version_id"])
CLOCK = datetime(2026, 8, 4, 1, tzinfo=UTC)
DAY = date(2026, 8, 3)
# The closes run-153de306's saved originals held for 2026-10-19.
CLOSES = {
    "000300.SH": 4174.5349,
    "000905.SH": 6800.6594,
    "000852.SH": 6698.3026,
    "000012CNY030.CSI": 111.6248,
    "930916.CSI": 185.8319,
    "NHCI.NH": 2949.2,
}


class EveryIndexAvailable:
    asked: list[dict[str, Any]] = []

    def open(self, request: Any, *, timeout: int) -> BytesIO:
        payload = json.loads(request.data)
        self.asked.append(payload)
        params = payload["params"]
        row = [params["ts_code"], params["start_date"], CLOSES[params["ts_code"]]]
        return BytesIO(
            json.dumps(
                {
                    "code": 0,
                    "data": {"fields": ["ts_code", "trade_date", "close"], "items": [row]},
                }
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
) -> tuple[RuntimePaths, RetrievalAdapterResponse]:
    install_runtime_clock(monkeypatch, request, CLOCK)
    EveryIndexAvailable.asked = []
    monkeypatch.setattr(
        "pring_cycle.tushare_context.build_opener", lambda *_: EveryIndexAvailable()
    )
    # What is under test is the refetch's acquisition, not the retrieval budget ledger.
    monkeypatch.setattr("pring_cycle.targeted_context.RetrievalLedger", PassThroughLedger)
    paths = RuntimePaths.discover(root / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.register(effective_model_manifest())
    models.activate(CURRENT_MODEL, explicitly_approved=True)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=DAY.isoformat(),
        client_request_id="targeted-market-index-refetch",
        model_version_id=CURRENT_MODEL,
        system_as_of=datetime.now(UTC),
    )
    day = DAY.isoformat()
    scope_run = replace(
        run,
        retrieval_scope=RetrievalScope(f"market_indices:{day}", (metric_id,), day, "P2", None),
    )
    with own_acquisitions(paths.database, run.run_id, "gap_retrieval"):
        response = retrieve_tushare_context(
            paths, run.run_id, "fixture-secret", scope_run=scope_run
        )
    return paths, response


def held(paths: RuntimePaths, metric_id: str) -> list[tuple[str, float]]:
    return [
        (p.period_end, p.selected_value)
        for p in EvidenceRepository(paths.database).metric_series(
            metric_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=EFFECTIVE_CATALOG_VERSION,
        )
        if p.selected_value is not None
    ]


def ingest_results(paths: RuntimePaths) -> list[tuple[str, str | None]]:
    with sqlite3.connect(paths.database) as connection:
        return connection.execute(
            "SELECT ingest_result, ingest_rejection_reason FROM acquisition_request"
        ).fetchall()


@pytest.mark.parametrize(
    ("metric_id", "source_code"),
    [
        pytest.param("CN_BOND_FULL_PRICE_CNY030", "000012CNY030.CSI", id="cny030"),
        pytest.param("CN_BOND_10Y_930916", "930916.CSI", id="930916"),
    ],
)
def test_a_bond_index_refetch_asks_for_and_holds_that_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    metric_id: str,
    source_code: str,
) -> None:
    paths, _ = refetch(monkeypatch, request, tmp_path, metric_id)

    assert [payload["params"]["ts_code"] for payload in EveryIndexAvailable.asked] == [source_code]
    assert ingest_results(paths) == [("accepted", None)]
    assert held(paths, metric_id) == [(DAY.isoformat(), CLOSES[source_code])]


def test_a_refetched_index_value_differing_from_its_original_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    delivered = TushareContextAdapter.market_indices

    def altered(self: TushareContextAdapter, **kwargs: Any) -> tuple[ContextScalar, ...]:
        return tuple(
            replace(scalar, value=scalar.value + 0.0001) for scalar in delivered(self, **kwargs)
        )

    monkeypatch.setattr(TushareContextAdapter, "market_indices", altered)

    with pytest.raises(ValueError, match="registered_market_index_acquisition_values_mismatch"):
        refetch(monkeypatch, request, tmp_path, "CN_BOND_10Y_930916")

    paths = RuntimePaths.discover(tmp_path / "runtime")
    assert held(paths, "CN_BOND_10Y_930916") == []
    assert all(result != "accepted" for result, _ in ingest_results(paths))
