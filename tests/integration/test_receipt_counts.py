"""A receipt keeps three counts apart: the records the source returned, the scalars its
answer normalized into, and the claims that entered the evidence store (lookback 06)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository, ReceiptCounts, own_acquisitions
from pring_cycle.core_history import refresh_core_history
from pring_cycle.eia_context import EiaPetroleumAdapter
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    ingest_acquired_official_release,
    ingest_official_context_document,
    official_member,
    parse_official_context_document,
)
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter
from pring_cycle.tushare_context import TushareContextAdapter
from tests.integration.test_context_acquisition_receipts import cpi_document, index_response
from tests.integration.test_core_history_refresh import historical_response


def _runtime(tmp_path: Path) -> tuple[RuntimePaths, AcquisitionRepository]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    return paths, AcquisitionRepository(paths.database, paths.artifacts)


def _tushare(rows: list[dict[str, Any]]) -> Any:
    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[r[f] for f in fields] for r in rows]}}
        ).encode()

    return transport


@pytest.mark.usefixtures("runtime_clock")
def test_a_tushare_receipt_counts_source_rows_apart_from_their_scalars(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    values = [49.3, 50.5, 49.8, 48.2, 50.1, 51.4, 49.5, 47.3]
    fields = [
        "pmi010000",
        "pmi010400",
        "pmi010500",
        "pmi010700",
        "pmi011100",
        "pmi011200",
        "pmi011300",
        "pmi011400",
    ]
    rows = [
        {"month": month, **dict(zip(fields, values, strict=True))} for month in ("202606", "202607")
    ]
    adapter = TushareContextAdapter("fixture-secret", transport=_tushare(rows))

    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.pmi(start_month="202606", end_month="202607"),
        definition_version="metric-catalog-v0001",
    )

    (receipt,) = receipts.history()
    # Two source rows of eight fields each: neither number stands in for the other.
    assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
        source_records=2, normalized_scalars=16, ingested_claims=result.observation_count
    )
    assert result.observation_count == 16


@pytest.mark.usefixtures("runtime_clock")
def test_a_gdp_receipt_counts_its_accepted_scalars_not_the_wrapper(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    row = {
        "gdp": 695704.0,
        "gdp_yoy": 4.7,
        "pi": 31521.8,
        "pi_yoy": 3.7,
        "si": 250472.9,
        "si_yoy": 3.9,
        "ti": 413709.2,
        "ti_yoy": 5.2,
    }
    rows = [{"quarter": quarter, **row} for quarter in ("2026Q1", "2026Q2")]
    adapter = TushareContextAdapter("fixture-secret", transport=_tushare(rows))

    adapter.acquire_scalars(
        paths,
        lambda: adapter.gdp(start_quarter="2026Q1", end_quarter="2026Q2"),
        definition_version="metric-catalog-v0002",
    )

    (receipt,) = receipts.history()
    normalized = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))
    assert set(normalized) == {"accepted_scalars", "rejected_fields"}
    # The disputed growth fields are refused; the four nominal levels of each quarter remain.
    assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
        source_records=2, normalized_scalars=8, ingested_claims=8
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_refused_ingest_keeps_its_counts_and_stores_no_claim(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    adapter = TushareContextAdapter("fixture-secret", transport=index_response)

    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            ),
            definition_version="metric-catalog-v0003",
        )

    for receipt in receipts.history():
        assert receipts.ingest_result(receipt.acquisition_id)[0] == "rejected"
        normalized = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))
        assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
            source_records=1, normalized_scalars=len(normalized), ingested_claims=0
        )


@pytest.mark.usefixtures("runtime_clock")
def test_a_json_api_receipt_counts_its_records(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    rows = [
        {
            "period": "2026-08-27",
            "series": series,
            "series-description": label,
            "value": value,
            "units": "Dollars per Barrel",
        }
        for series, label, value in [
            ("RBRTE", "Europe Brent Spot Price FOB", "71.25"),
            ("RWTC", "Cushing, OK WTI Spot Price FOB", "66.50"),
        ]
    ]
    content = json.dumps({"response": {"frequency": "daily", "data": rows}}).encode()
    adapter = EiaPetroleumAdapter("fixture-secret", transport=lambda _: content)

    adapter.acquire_spot_prices(
        paths,
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
        definition_version="metric-catalog-v0001",
    )

    (receipt,) = receipts.history()
    assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
        source_records=2, normalized_scalars=2, ingested_claims=2
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_refused_tushare_answer_still_says_how_many_rows_it_carried(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)

    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        row = {**{field: 50.0 for field in fields}, "month": "202607", "pmi010000": "invalid"}
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields]]}}
        ).encode()

    adapter = TushareContextAdapter("fixture-secret", transport=transport)

    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="202607", end_month="202607"),
            definition_version="metric-catalog-v0001",
        )

    (receipt,) = receipts.history()
    assert receipt.state == "failed"
    assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
        source_records=1, normalized_scalars=None, ingested_claims=None
    )


@pytest.mark.parametrize("counted", ["records", "scalars"])
def test_a_deferred_validation_cannot_drop_a_count(tmp_path: Path, counted: str) -> None:
    paths, receipts = _runtime(tmp_path)

    with pytest.raises(ValueError, match="acquisition_deferred_count_unsupported"):
        receipts.capture(
            provider="fixture",
            api_name="fixture",
            parameters={},
            fields="",
            parser_version="v1",
            fetch=lambda: b"[]",
            parse=json.loads,
            normalize=lambda value: value,
            defer_validation=True,
            count_records=len if counted == "records" else None,
            count_scalars=len if counted == "scalars" else None,
        )
    assert receipts.history() == ()


@pytest.mark.usefixtures("runtime_clock")
def test_an_html_original_has_no_record_count_of_its_own(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)

    result = ingest_official_context_document(
        paths,
        cpi_document("发布时间：2026-08-09 09:30"),
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
        expected_period="2026-07",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )

    (receipt,) = receipts.history()
    normalized = json.loads(receipts.read_content(receipt.acquisition_id, "normalized"))
    # A page is no row: what it states is counted by the scalars read from it.
    assert receipts.counts(receipt.acquisition_id) == ReceiptCounts(
        source_records=None,
        normalized_scalars=len(normalized["scalars"]),
        ingested_claims=result.observation_count,
    )


@pytest.mark.usefixtures("runtime_clock")
def test_members_already_held_are_normalized_but_not_stored(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    content = cpi_document("发布时间：2026-08-09 09:30")
    source_url = "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html"
    acquired = receipts.capture(
        provider="nbs",
        api_name="document_import",
        parameters={"source_url": source_url, "period": "2026-07", "family": "nbs_core_cpi"},
        fields="",
        parser_version="official-context-parser-v0004",
        fetch=lambda: content,
        parse=lambda raw: parse_official_context_document(
            raw,
            family="nbs_core_cpi",
            source_url=source_url,
            expected_period="2026-07",
            fetched_at=datetime.now(UTC),
        ),
        normalize=asdict,
        count_scalars=lambda release: len(release.scalars),
    )
    scalars = acquired.value.scalars
    assert len(scalars) > 1
    held = frozenset({official_member(scalars[0].metric_id, scalars[0].dimensions)})

    ingest_acquired_official_release(
        paths, acquired, definition_version="metric-catalog-v0001", held_members=held
    )

    assert receipts.counts(acquired.receipt.acquisition_id) == ReceiptCounts(
        source_records=None, normalized_scalars=len(scalars), ingested_claims=len(scalars) - 1
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_run_audit_lists_each_calls_three_counts(tmp_path: Path) -> None:
    paths, _ = _runtime(tmp_path)
    ModelRepository(paths.database).activate("model-v0001", explicitly_approved=True)
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="receipt-counts",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    with own_acquisitions(paths.database, run.run_id, "gap_retrieval", metric_ids=("CN_GDP",)):
        ingest_official_context_document(
            paths,
            cpi_document("发布时间：2026-08-09 09:30"),
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
            expected_period="2026-07",
            fetched_at=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )

    (call,) = runs.full_retrieval_plan(run.run_id)["acquisitions"]
    assert call["source_record_count"] is None
    assert call["normalized_scalar_count"] >= call["ingested_claim_count"] > 0
    assert call["ingest_result"] == "accepted"


@pytest.mark.usefixtures("runtime_clock")
def test_a_core_dropped_after_a_later_failure_says_no_ingest_result(tmp_path: Path) -> None:
    paths, receipts = _runtime(tmp_path)
    dropped = next(iter(CORE_API_IDENTITIES))
    api_name, source_code = CORE_API_IDENTITIES[dropped]

    def transport(payload: dict[str, Any]) -> bytes:
        later = payload["params"].get("start_date", "").startswith("2026")
        if later and payload["params"].get("ts_code") == source_code:
            return b'{"code": 0, "data": {"fields": ["ts_code"], "items": [["broken"]]}}'
        return historical_response(payload)

    refresh_core_history(
        paths,
        TushareCoreAdapter("fixture-token", transport=transport),
        start=date(2025, 12, 30),
        end=date(2026, 1, 2),
        definition_version="metric-catalog-v0001",
    )

    bars = [r for r in receipts.history() if r.api_name != "trade_cal" and r.state == "validated"]
    ingested = {
        (r.parameters["ts_code"], r.parameters["start_date"]): receipts.ingest_result(
            r.acquisition_id
        )[0]
        for r in bars
    }
    # Its earlier year passed its check, but none of its bars were stored.
    assert ingested.pop((source_code, "20251230")) is None
    assert set(ingested.values()) == {"accepted"}


# The receipt table and its guards as revision 0031 left them, with one receipt on file.
_REVISION_0031 = """
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
INSERT INTO alembic_version VALUES ('0031_ingest_result');
ALTER TABLE acquisition_request ADD COLUMN row_count INTEGER;
ALTER TABLE acquisition_request ADD COLUMN structure_check TEXT;
ALTER TABLE acquisition_request ADD COLUMN rejection_reason TEXT;
ALTER TABLE acquisition_request ADD COLUMN ingest_result TEXT;
ALTER TABLE acquisition_request ADD COLUMN ingest_rejection_reason TEXT;
INSERT INTO acquisition_request VALUES (
    'acquisition-old', 'tushare', 'cn_cpi', '{}', 'month', 'v1',
    '2026-09-30T00:00:00+00:00', '2026-09-30T00:00:01+00:00', '2026-09-30T00:00:02+00:00',
    'validated', 'raw', 'normalized', NULL, 60, 'passed', NULL, NULL, NULL
), (
    'acquisition-failed', 'tushare', 'cn_ppi', '{}', 'month', 'v1',
    '2026-09-30T00:00:00+00:00', '2026-09-30T00:00:01+00:00', NULL,
    'failed', 'raw', NULL, 'ValueError', NULL, 'rejected', 'bad', NULL, NULL
);
DROP TRIGGER acquisition_request_terminal_no_update;
CREATE TRIGGER acquisition_request_terminal_no_update BEFORE UPDATE OF acquisition_id,
    provider, api_name, parameters_json, fields, parser_version, started_at, received_at,
    validated_at, state, raw_hash, normalized_hash, error_type, row_count, structure_check,
    rejection_reason ON acquisition_request WHEN OLD.state IN ('validated', 'failed') BEGIN
    SELECT RAISE(ABORT, 'acquisition_receipt_is_immutable'); END;
CREATE TRIGGER acquisition_request_ingest_result_once BEFORE UPDATE OF ingest_result,
    ingest_rejection_reason ON acquisition_request WHEN OLD.state <> 'validated'
    OR OLD.ingest_result IS NOT NULL OR OLD.ingest_rejection_reason IS NOT NULL
    OR NEW.ingest_result IS NULL BEGIN
    SELECT RAISE(ABORT, 'acquisition_ingest_result_is_immutable'); END;
"""


def test_the_counts_migration_keeps_old_receipts_and_guards_the_new_columns(
    tmp_path: Path,
) -> None:
    import sqlite3

    from pring_cycle.acquisition import ACQUISITION_SCHEMA, add_receipt_columns
    from pring_cycle.storage import SCHEMA_HEAD, migrate_database

    database = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(ACQUISITION_SCHEMA + _REVISION_0031)
    connection.close()

    migrate_database(database)
    with sqlite3.connect(database) as connection:
        add_receipt_columns(connection)  # safe to repeat
    connection.close()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            SCHEMA_HEAD,
        )
        # An old receipt's mixed count stays as it was; the counts it never had stay unknown.
        assert connection.execute(
            "SELECT row_count, source_record_count, normalized_scalar_count, "
            "ingested_claim_count FROM acquisition_request ORDER BY rowid"
        ).fetchall() == [(60, None, None, None), (None, None, None, None)]
        for column in ("source_record_count", "normalized_scalar_count"):
            for acquisition_id in ("acquisition-old", "acquisition-failed"):
                with pytest.raises(sqlite3.IntegrityError, match="receipt_is_immutable"):
                    connection.execute(
                        f"UPDATE acquisition_request SET {column}=20 WHERE acquisition_id=?",
                        (acquisition_id,),
                    )
        old = "UPDATE acquisition_request SET {} WHERE acquisition_id='acquisition-old'"
        # A validated receipt says its ingest result and claim count once, together.
        for partial in ("ingest_result='accepted'", "ingested_claim_count=3"):
            with pytest.raises(sqlite3.IntegrityError, match="ingest_result_is_immutable"):
                connection.execute(old.format(partial))
        connection.execute(old.format("ingest_result='accepted', ingested_claim_count=3"))
        with pytest.raises(sqlite3.IntegrityError, match="ingest_result_is_immutable"):
            connection.execute(old.format("ingested_claim_count=4"))
        with pytest.raises(sqlite3.IntegrityError, match="ingest_result_is_immutable"):
            connection.execute(
                "UPDATE acquisition_request SET ingest_result='accepted', "
                "ingested_claim_count=0 WHERE acquisition_id='acquisition-failed'"
            )
    connection.close()
