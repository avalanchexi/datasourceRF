"""How an acquisition ended, as each source's adapter records it where it ended (ticket 18).

The step, the result, and why: the source's own code, the local rule that refused the
response, the contract that refused its values; and, for a delivery, what it held of what
was asked. An answer that was itself a failure is the source's, never a refused response.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.acquisition_outcome import AcquisitionOutcomes, AttemptView
from pring_cycle.eia_context import EiaPetroleumAdapter
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    refresh_official_context_document,
)
from pring_cycle.official_lpr import FetchedOfficialDocument, refresh_lpr_release
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import ContextObservationsMissingError, TushareContextAdapter

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
