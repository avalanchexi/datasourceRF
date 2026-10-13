"""How an acquisition ended, as each source's adapter records it where it ended (ticket 18).

The step, the result, and why: the source's own code, the local rule that refused the
response, the contract that refused its values; and, for a delivery, what it held of what
was asked. An answer that was itself a failure is the source's, never a refused response.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.acquisition_outcome import AcquisitionOutcomes, AttemptView
from pring_cycle.basket import BASE_DATE, BASKET_METRICS
from pring_cycle.breadth import BREADTH_METRICS
from pring_cycle.eia_context import EiaPetroleumAdapter
from pring_cycle.models import EFFECTIVE_CATALOG_VERSION
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    refresh_official_context_document,
)
from pring_cycle.official_lpr import FetchedOfficialDocument, refresh_lpr_release
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import ContextObservationsMissingError, TushareContextAdapter
from tests.integration.test_gap_source_repairs import breadth_response, futures_response

TREASURY = ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD")


@pytest.fixture
def paths(tmp_path: Path) -> RuntimePaths:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths


def latest(paths: RuntimePaths, metric_id: str) -> AttemptView:
    attempt = AcquisitionOutcomes(paths.database).latest(metric_id, as_of=datetime.now(UTC))
    assert attempt is not None
    return attempt


def structure_check(paths: RuntimePaths, acquisition_id: str) -> str | None:
    with sqlite3.connect(paths.database) as connection:
        (check,) = connection.execute(
            "SELECT structure_check FROM acquisition_request WHERE acquisition_id=?",
            (acquisition_id,),
        ).fetchone()
    return None if check is None else str(check)


def rows(payload: dict[str, Any], items: list[dict[str, object]]) -> bytes:
    fields = payload["fields"].split(",")
    return json.dumps(
        {
            "code": 0,
            "data": {"fields": fields, "items": [[i.get(f) for f in fields] for i in items]},
        }
    ).encode()


def yields(payload: dict[str, Any], *, day: str = "20260828") -> bytes:
    return rows(payload, [{"date": day, "y2": 3.6, "y10": 4.2}])


def acquire_yields(paths: RuntimePaths, transport: Any) -> None:
    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.treasury_yields(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version="metric-catalog-v0002",
        metric_ids=TREASURY,
        details={"family": "treasury_yields"},
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_tushare_refusal_is_the_source_s_with_its_code(paths: RuntimePaths) -> None:
    def refused(_payload: dict[str, Any]) -> bytes:
        return json.dumps({"code": 40203, "msg": "rate limited"}).encode()

    with pytest.raises(ValueError, match="tushare_rate_limited"):
        acquire_yields(paths, refused)

    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipt.state == "failed" and structure_check(paths, receipt.acquisition_id) is None
    for metric_id in TREASURY:
        attempt = latest(paths, metric_id)
        assert (attempt.outcome, attempt.step, attempt.external_code) == (
            "source_failed",
            "response",
            "40203",
        )
        assert attempt.acquisition_ids == (receipt.acquisition_id,)


@pytest.mark.usefixtures("runtime_clock")
def test_a_response_its_rules_refuse_is_a_structure_rejection_with_the_rule(
    paths: RuntimePaths,
) -> None:
    with pytest.raises(ValueError) as refused:
        acquire_yields(paths, lambda payload: yields(payload, day="20260901"))

    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert structure_check(paths, receipt.acquisition_id) == "rejected"
    attempt = latest(paths, "UST2Y_NOMINAL_YIELD")
    assert (attempt.outcome, attempt.step) == ("structure_rejected", "structure")
    assert attempt.rule_reason == str(refused.value)


@pytest.mark.usefixtures("runtime_clock")
def test_the_contract_refusing_checked_values_is_an_ingest_rejection(paths: RuntimePaths) -> None:
    adapter = TushareContextAdapter(
        "fixture-secret",
        transport=lambda payload: rows(
            payload,
            [{"ts_code": payload["params"].get("ts_code"), "trade_date": "20260828", "close": 1.0}],
        ),
    )

    # The frozen v3 contract refuses these claims only once they reach the evidence store.
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            ),
            definition_version="metric-catalog-v0003",
            metric_ids=("CN_EQ_CSI300",),
        )

    attempt = latest(paths, "CN_EQ_CSI300")
    assert (attempt.outcome, attempt.step) == ("ingest_rejected", "ingest")
    assert attempt.rule_reason is not None
    assert attempt.rule_reason.startswith("source_certification_contract_unresolved")


@pytest.mark.usefixtures("runtime_clock")
def test_a_refused_field_is_a_member_the_delivery_misses(paths: RuntimePaths) -> None:
    adapter = TushareContextAdapter(
        "fixture-secret",
        transport=lambda payload: rows(
            payload, [{"quarter": "2026Q2", "gdp": 660000.0, "gdp_yoy": 5.2}]
        ),
    )

    adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
        definition_version="metric-catalog-v0002",
        metric_ids=("CN_GDP",),
    )

    attempt = latest(paths, "CN_GDP")
    assert (attempt.outcome, attempt.completeness) == ("succeeded", "partial_members_missing")
    assert attempt.missing_members == ("cn_gdp:gdp_yoy:2026-06-30",)


@pytest.mark.usefixtures("runtime_clock")
def test_nothing_new_is_told_apart_from_an_empty_delivery(paths: RuntimePaths) -> None:
    adapter = TushareContextAdapter("fixture-secret", transport=lambda payload: rows(payload, []))

    def all_held() -> tuple[Any, ...]:
        raise ContextObservationsMissingError("nothing_new")

    with pytest.raises(ContextObservationsMissingError):
        adapter.acquire_scalars(
            paths, all_held, definition_version="metric-catalog-v0002", metric_ids=("CN_GDP",)
        )
    with pytest.raises(ContextObservationsMissingError):
        acquire_yields(paths, adapter._transport)

    assert (latest(paths, "CN_GDP").outcome, latest(paths, "CN_GDP").completeness) == (
        "succeeded",
        "nothing_new",
    )
    for metric_id in TREASURY:
        attempt = latest(paths, metric_id)
        assert (attempt.outcome, attempt.completeness) == ("succeeded", "source_empty")


BASKET_END = date(2026, 8, 3)


def acquire_basket(paths: RuntimePaths, transport: Any, held_levels: dict[date, float]) -> None:
    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.ex_hog_basket(end_date=BASKET_END, held_levels=held_levels),
        definition_version=EFFECTIVE_CATALOG_VERSION,
        metric_ids=tuple(sorted(BASKET_METRICS)),
        details={"family": "commodity_basket"},
    )


def receipt_states(paths: RuntimePaths) -> dict[str, list[tuple[str, str | None]]]:
    with sqlite3.connect(paths.database) as connection:
        found: dict[str, list[tuple[str, str | None]]] = {}
        for api_name, state, check in connection.execute(
            "SELECT api_name, state, structure_check FROM acquisition_request ORDER BY rowid"
        ):
            found.setdefault(str(api_name), []).append((str(state), check))
    return found


def every_basket_day_held() -> dict[date, float]:
    days = (BASKET_END - BASE_DATE).days
    return {
        BASE_DATE + timedelta(days=n): 1000.0
        for n in range(1, days + 1)
        if (BASE_DATE + timedelta(days=n)).weekday() < 5
    }


@pytest.mark.usefixtures("runtime_clock")
def test_the_basket_s_inputs_end_checked_when_every_day_is_held(paths: RuntimePaths) -> None:
    # Residual 01: the calendars were answered and read; the window, all held already, added
    # nothing. Their receipts were failed although the attempt succeeded. Ticket 06: the four
    # calendars tell it alone, the contracts are not asked for.
    sent: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        sent.append(payload["api_name"])
        return futures_response(payload)

    with pytest.raises(ContextObservationsMissingError) as held:
        acquire_basket(paths, transport, every_basket_day_held())

    assert held.value.completeness == "nothing_new"
    assert sent == ["fut_trade_cal"] * 4
    states = receipt_states(paths)
    assert set(states) == {"fut_trade_cal"}  # no contract or settlement asked for
    assert states["fut_trade_cal"] == [("validated", "passed")] * 4
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    for receipt in acquisitions.history():
        assert acquisitions.ingest_result(receipt.acquisition_id) == ("accepted", None)
        counts = acquisitions.counts(receipt.acquisition_id)
        assert (counts.normalized_scalars, counts.ingested_claims) == (0, 0)
    for metric_id in BASKET_METRICS:
        attempt = latest(paths, metric_id)
        assert (attempt.outcome, attempt.completeness) == ("succeeded", "nothing_new")
        assert len(attempt.acquisition_ids) == 4


@pytest.mark.usefixtures("runtime_clock")
def test_storing_a_held_window_s_receipt_failing_is_this_system_s(
    paths: RuntimePaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unwritable(*_args: object) -> None:
        raise OSError("disk_full")

    monkeypatch.setattr(AcquisitionRepository, "record_ingest_result", unwritable)
    with pytest.raises(OSError, match="disk_full"):
        acquire_basket(paths, futures_response, every_basket_day_held())

    states = [state for receipts in receipt_states(paths).values() for state in receipts]
    # The first was closed before the store failed; none of them was refused.
    assert sorted(states) == sorted([("validated", "passed")] + [("failed", None)] * 3)
    attempt = latest(paths, "CN_COMMODITY_EX_HOG_BASKET")
    assert (attempt.outcome, attempt.step) == ("local_failed", "local")


def closed_calendars(payload: dict[str, Any]) -> bytes:
    if payload["api_name"] != "fut_trade_cal":
        return futures_response(payload)
    document = json.loads(futures_response(payload))
    for item in document["data"]["items"]:
        item[2] = 0
    return json.dumps(document).encode()


def foreign_contract(payload: dict[str, Any]) -> bytes:
    document = json.loads(futures_response(payload))
    if payload["api_name"] == "fut_basic" and payload["params"]["fut_code"] == "SC":
        document["data"]["items"][0][2] = "SHFE"  # an INE contract said to trade elsewhere
    return json.dumps(document).encode()


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    ("transport", "check", "completeness", "outcome"),
    [
        (closed_calendars, None, "source_empty", "succeeded"),
        (foreign_contract, "rejected", None, "structure_rejected"),
    ],
    ids=["no_basket_day", "contract_refused"],
)
def test_the_basket_s_inputs_still_fail_when_it_holds_no_day_or_refuses_one(
    paths: RuntimePaths, transport: Any, check: str | None, completeness: str | None, outcome: str
) -> None:
    # The last day not held: a window all held is told from the calendars alone, without
    # reading the contracts (ticket 06).
    held = every_basket_day_held()
    del held[BASKET_END]
    with pytest.raises(ValueError):
        acquire_basket(paths, transport, held)

    states = receipt_states(paths)
    assert {state for receipts in states.values() for state, _check in receipts} == {"failed"}
    assert {item for receipts in states.values() for _state, item in receipts} == {check}
    attempt = latest(paths, "CN_COMMODITY_EX_HOG_BASKET")
    assert (attempt.outcome, attempt.completeness) == (outcome, completeness)


@pytest.mark.usefixtures("runtime_clock")
def test_breadth_s_empty_quotes_for_a_day_not_held_still_fail(paths: RuntimePaths) -> None:
    # Breadth asks nothing once every day is held; an answer it read and found empty is no
    # sign of a held window, and its responses stay failed (residual 01).
    def transport(payload: dict[str, Any]) -> bytes:
        if payload["api_name"] == "stock_basic":
            return breadth_response(payload)
        return rows(payload, [])

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    with pytest.raises(ContextObservationsMissingError) as empty:
        adapter.acquire_scalars(
            paths,
            lambda: adapter.breadth(
                end_date=BASKET_END, held_days=(), sessions=(BASKET_END,), calendar_ids=()
            ),
            definition_version=EFFECTIVE_CATALOG_VERSION,
            metric_ids=tuple(BREADTH_METRICS),
        )

    states = receipt_states(paths)
    assert set(states) == {"stock_basic", "daily", "stk_factor_pro"}
    assert {state for receipts in states.values() for state, _check in receipts} == {"failed"}
    # Asked and answered with nothing: an empty delivery, not "all held" (ticket 06).
    assert empty.value.completeness == "source_empty"
    for metric_id in BREADTH_METRICS:
        attempt = latest(paths, metric_id)
        assert (attempt.outcome, attempt.completeness) == ("succeeded", "source_empty")


@pytest.mark.usefixtures("runtime_clock")
def test_breadth_with_every_day_held_asks_nothing_and_has_nothing_new(
    paths: RuntimePaths,
) -> None:
    sent: list[str] = []

    def transport(payload: dict[str, Any]) -> bytes:
        sent.append(payload["api_name"])
        return breadth_response(payload)

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    with pytest.raises(ContextObservationsMissingError) as held:
        adapter.acquire_scalars(
            paths,
            lambda: adapter.breadth(
                end_date=BASKET_END,
                held_days=(BASKET_END,),
                sessions=(BASKET_END,),
                calendar_ids=(),
            ),
            definition_version=EFFECTIVE_CATALOG_VERSION,
            metric_ids=tuple(BREADTH_METRICS),
        )

    assert held.value.completeness == "nothing_new" and sent == []
    for metric_id in BREADTH_METRICS:
        attempt = latest(paths, metric_id)
        assert (attempt.outcome, attempt.completeness) == ("succeeded", "nothing_new")


LPR_URL = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
NBS_URL = "https://www.stats.gov.cn/sj/zxfb/202607/t20260709_1.html"


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("family", ["lpr", "nbs_core_cpi"])
def test_an_http_error_page_is_the_source_s_not_a_refused_response(
    paths: RuntimePaths, family: str
) -> None:
    page = b"<html>403 Forbidden</html>"
    with pytest.raises(OSError, match="http_status_invalid"):
        if family == "lpr":
            refresh_lpr_release(
                paths,
                source_url=LPR_URL,
                expected_period="2026-08",
                fetched_at=datetime.now(UTC),
                fetcher=lambda url: FetchedOfficialDocument(page, "text/html", url, 403),
            )
        else:
            refresh_official_context_document(
                paths,
                family=family,
                source_url=NBS_URL,
                expected_period="2026-06",
                fetched_at=datetime.now(UTC),
                fetcher=lambda url: FetchedOfficialContextDocument(page, "text/html", url, 403),
            )

    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == page
    assert receipt.state == "failed" and structure_check(paths, receipt.acquisition_id) is None
    attempt = latest(paths, "CN_LPR_1Y_5Y" if family == "lpr" else "CN_CORE_CPI")
    assert (attempt.outcome, attempt.step, attempt.external_code) == (
        "source_failed",
        "response",
        "403",
    )


@pytest.mark.usefixtures("runtime_clock")
def test_every_field_refused_is_no_empty_delivery(paths: RuntimePaths) -> None:
    adapter = TushareContextAdapter(
        "fixture-secret",
        transport=lambda payload: rows(payload, [{"quarter": "2026Q2", "gdp_yoy": 5.2}]),
    )

    with pytest.raises(ValueError, match="gdp_yoy_period_semantics_unverified"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.gdp(start_quarter="2026Q2", end_quarter="2026Q2"),
            definition_version="metric-catalog-v0002",
            metric_ids=("CN_GDP",),
        )

    attempt = latest(paths, "CN_GDP")
    assert (attempt.outcome, attempt.rule_reason) == (
        "structure_rejected",
        "gdp_yoy_period_semantics_unverified",
    )
    # The receipt says the same as the attempt.
    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert structure_check(paths, receipt.acquisition_id) == "rejected"


@pytest.mark.usefixtures("runtime_clock")
def test_an_eia_answer_missing_a_series_delivers_the_other(paths: RuntimePaths) -> None:
    brent_only = {
        "response": {
            "frequency": "daily",
            "data": [
                {
                    "period": "2026-08-27",
                    "series": "RBRTE",
                    "series-description": "Europe Brent Spot Price FOB",
                    "value": "71.25",
                    "units": "Dollars per Barrel",
                }
            ],
        }
    }
    adapter = EiaPetroleumAdapter(
        "fixture-key", transport=lambda _: json.dumps(brent_only).encode()
    )

    result = adapter.acquire_spot_prices(
        paths,
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
        definition_version="metric-catalog-v0002",
    )

    assert result.metric_ids == ("EIA_BRENT_RBRTE",)
    brent, wti = latest(paths, "EIA_BRENT_RBRTE"), latest(paths, "EIA_WTI_RWTC")
    assert (brent.outcome, brent.completeness) == ("succeeded", "complete")
    assert (wti.outcome, wti.completeness) == ("succeeded", "source_empty")
