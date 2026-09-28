from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.eia_context import EiaPetroleumAdapter
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.official_context import (
    ingest_official_context_document,
    refresh_official_context_document,
)
from pring_cycle.official_lpr import ingest_lpr_document, refresh_lpr_release
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter
from pring_cycle.worker import process_pending_run


def cpi_document(publication: str, value: float = 1.0) -> bytes:
    return f"""<html><body><h1>2026年7月份居民消费价格</h1>
    <p>{publication}</p><table>
    <tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
    <tr><td>不包括食品和能源</td><td>0.1</td><td>{value}</td><td>1.2</td></tr>
    </table></body></html>""".encode()


@pytest.mark.usefixtures("runtime_clock")
def test_official_future_publication_date_is_rejected_and_raw_retained(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = cpi_document("发布时间：2026-08-10")
    with pytest.raises(ValueError, match="official_context_fetched_before_release"):
        ingest_official_context_document(
            paths,
            content,
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260810_1.html",
            expected_period="2026-07",
            fetched_at=datetime(2026, 8, 9, tzinfo=UTC),
            definition_version="metric-catalog-v0001",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.history()[0]
    assert receipt.state == "failed"
    assert receipts.read_content(receipt.acquisition_id, "raw") == content


@pytest.mark.usefixtures("runtime_clock")
def test_official_revision_with_new_published_time_changes_public_at_that_time(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    for publication, value in (("09:30", 1.0), ("10:30", 1.1)):
        result = ingest_official_context_document(
            paths,
            cpi_document("发布时间：2026-08-09 " + publication, value),
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
            expected_period="2026-07",
            fetched_at=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        if trace.dimensions["measure"] != "yoy":
            continue
        before = repository.query(
            observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 9, 2, 29, tzinfo=UTC)
        )
        after = repository.query(
            observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 9, 2, 30, tzinfo=UTC)
        )
        assert before.selected_value == 1.0
        assert after.selected_value == 1.1


@pytest.mark.parametrize(
    ("publication", "public_at", "released_at"),
    [
        (
            "发布时间：2026-08-09 09:30",
            datetime(2026, 8, 9, 1, 30, tzinfo=UTC),
            datetime(2026, 8, 9, 1, 30, tzinfo=UTC),
        ),
        ("发布时间：2026-08-09", datetime(2026, 8, 9, 16, tzinfo=UTC), None),
        ("发布日期未提供", None, None),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_official_document_preserves_publication_precision_and_receipt(
    tmp_path: Path,
    publication: str,
    public_at: datetime | None,
    released_at: datetime | None,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = cpi_document(publication)
    result = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
        expected_period="2026-07",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.claims[0].release_at == released_at
        assert trace.claims[0].parsed_public_available_at == public_at
        assert trace.acquisition_status == "linked"
        receipt = trace.acquisitions[0]
        assert receipt.api_name == "document_import"
        assert (
            AcquisitionRepository(paths.database, paths.artifacts).read_content(
                receipt.acquisition_id, "raw"
            )
            == content
        )


@pytest.mark.usefixtures("runtime_clock")
def test_lpr_document_import_links_both_tenors_to_original(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    result = ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/10000001.html",
        expected_period="2026-08",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert result.observation_count == 2
    for observation_id in result.observation_ids:
        trace = EvidenceRepository(paths.database).trace(
            observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
        )
        assert trace.acquisition_status == "linked"
        assert trace.claims[0].public_available_at == datetime(2026, 8, 20, 1, tzinfo=UTC)
        receipt = trace.acquisitions[0]
        assert (
            AcquisitionRepository(paths.database, paths.artifacts).read_content(
                receipt.acquisition_id, "raw"
            )
            == content
        )


@pytest.mark.usefixtures("runtime_clock")
def test_eia_acquisition_retains_response_and_both_series(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = json.dumps(
        {
            "response": {
                "frequency": "daily",
                "data": [
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
                ],
            }
        },
        indent=2,
    ).encode()
    adapter = EiaPetroleumAdapter("fixture-secret", transport=lambda _: content)
    result = adapter.acquire_spot_prices(
        paths,
        start_date=date(2026, 8, 27),
        end_date=date(2026, 8, 27),
        definition_version="metric-catalog-v0001",
    )
    assert result.observation_count == 2
    for observation_id in result.observation_ids:
        trace = EvidenceRepository(paths.database).trace(
            observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
        )
        assert trace.acquisition_status == "linked"
        assert trace.claims[0].parsed_public_available_at is None
        receipt = trace.acquisitions[0]
        assert "api_key" not in receipt.parameters
        assert (
            AcquisitionRepository(paths.database, paths.artifacts).read_content(
                receipt.acquisition_id, "raw"
            )
            == content
        )


@pytest.mark.usefixtures("runtime_clock")
def test_manual_run_acquires_macro_receipts_and_keeps_uncertified_context_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-secret\n", encoding="utf-8")
    paths.secrets.chmod(0o600)
    models = ModelRepository(paths.database)
    models.activate("model-v0001", explicitly_approved=True)
    during_pmi = []

    class Opener:
        def open(self, request: Any, *, timeout: int) -> BytesIO:
            payload = json.loads(request.data)
            if payload["api_name"] == "cn_pmi":
                during_pmi.append(datetime.now(UTC))
                fields = payload["fields"].split(",")
                row = ["202607" if field == "month" else 49.3 for field in fields]
                return BytesIO(
                    json.dumps({"code": 0, "data": {"fields": fields, "items": [row]}}).encode()
                )
            params = payload["params"]
            if payload["api_name"] != "trade_cal" and params.get("ts_code") not in {
                "000985.CSI",
                "000012.SH",
                "NHII.NH",
            }:
                raise OSError("fixture_optional_source_unavailable")
            start = datetime.strptime(params["start_date"], "%Y%m%d").date()
            end = datetime.strptime(params["end_date"], "%Y%m%d").date()
            days = [
                start + timedelta(days=i)
                for i in range((end - start).days + 1)
                if (start + timedelta(days=i)).weekday() < 5
            ]
            if payload["api_name"] == "trade_cal":
                fields = ["cal_date", "is_open"]
                items = [[day.strftime("%Y%m%d"), 1] for day in days]
            else:
                fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
                items = [
                    [
                        params["ts_code"],
                        day.strftime("%Y%m%d"),
                        100 + i,
                        99 + i,
                        0.01 if payload["api_name"] == "fut_index_daily" else 1.0,
                    ]
                    for i, day in enumerate(days)
                ]
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    monkeypatch.setattr("pring_cycle.source_adapters.build_opener", Opener)
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *handlers: Opener())
    runs = RunRepository(paths.database)
    run = runs.submit_manual_full(
        target_business_date="2026-08-03",
        client_request_id="macro-receipts",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    process_pending_run(paths, report_adapters=())
    assert runs.get(run.run_id).status == "completed"
    assert (
        ProjectionSetRepository(paths.database).current().envelope.target_business_date
        == "2026-08-03"
    )
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_PMI_ACTIVITY",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    assert len(points) == 4
    for point in points:
        trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.acquisition_status == "linked"
        assert trace.claims[0].certification_status == "awaiting_source_certification"
        assert trace.claims[0].parsed_public_available_at is None
        assert (
            evidence.query(
                point.observation_id, mode=AsOfMode.SYSTEM, as_of=during_pmi[0]
            ).selected_value
            is None
        )


@pytest.mark.usefixtures("runtime_clock")
def test_macro_wrong_period_is_rejected_before_claim_ingestion(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": fields,
                    "items": [["202608" if field == "month" else 49.3 for field in fields]],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    with pytest.raises(ValueError, match="tushare_response_period_mismatch"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="202607", end_month="202607"),
            definition_version="metric-catalog-v0001",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert len(receipts) == 1 and receipts[0].state == "failed"
    assert receipts[0].raw_hash is not None
    assert (
        EvidenceRepository(paths.database).metric_series(
            "CN_PMI_ACTIVITY",
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version="metric-catalog-v0001",
        )
        == ()
    )


def test_context_index_does_not_assume_fixed_close_publication_time() -> None:
    def transport(payload: dict[str, Any]) -> bytes:
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["ts_code", "trade_date", "close"],
                    "items": [[payload["params"]["ts_code"], "20260828", 100.0]],
                },
            }
        ).encode()

    scalars = TushareContextAdapter("fixture-secret", transport=transport).market_indices(
        start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    assert scalars and all(s.public_available_at is None and s.release_at is None for s in scalars)


@pytest.mark.usefixtures("runtime_clock")
def test_macro_acquisition_links_all_dimensions_to_exact_response(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    fields = [
        "month",
        "pmi010000",
        "pmi010400",
        "pmi010500",
        "pmi010700",
        "pmi011100",
        "pmi011200",
        "pmi011300",
        "pmi011400",
    ]
    content = json.dumps(
        {
            "code": 0,
            "data": {
                "fields": fields,
                "items": [["202607", 49.3, 50.5, 49.8, 48.2, 50.1, 51.4, 49.5, 47.3]],
            },
        },
        indent=3,
    ).encode()
    during_request = []

    def transport(payload: dict[str, Any]) -> bytes:
        assert payload["api_name"] == "cn_pmi"
        during_request.append(datetime.now(UTC))
        return content

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    result = adapter.acquire_scalars(
        paths,
        lambda: adapter.pmi(start_month="202607", end_month="202607"),
        definition_version="metric-catalog-v0001",
    )
    assert result.observation_count == 8
    repository = EvidenceRepository(paths.database)
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert len(receipts.history()) == 1
    for observation_id in result.observation_ids:
        cutoff = datetime.now(UTC)
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff)
        assert trace.acquisition_status == "linked", (cutoff, receipts.history())
        assert len(trace.acquisitions) == 1
        assert receipts.read_content(trace.acquisitions[0].acquisition_id, "raw") == content
        assert trace.claims[0].parsed_public_available_at is None
        assert (
            repository.query(
                observation_id, mode=AsOfMode.SYSTEM, as_of=during_request[0]
            ).selected_value
            is None
        )


@pytest.mark.usefixtures("runtime_clock")
def test_context_invalid_scalar_keeps_failed_receipt_and_original(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    original = []

    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        values = {field: 50.0 for field in fields}
        values.update(month="202607", pmi010000="invalid-number")
        content = json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[values[f] for f in fields]]}}
        ).encode()
        original.append(content)
        return content

    adapter = TushareContextAdapter("fixture-secret", transport=transport)
    with pytest.raises(ValueError):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.pmi(start_month="202607", end_month="202607"),
            definition_version="metric-catalog-v0001",
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.history()[0]
    assert receipt.state == "failed"
    assert receipt.validated_at is None
    assert receipts.read_content(receipt.acquisition_id, "raw") == original[0]


def test_a_call_failing_before_its_answer_is_recorded_keeps_why(tmp_path: Path) -> None:
    """Run findings 2026-09-28, ticket 02: a clock stepping back while a call was in flight
    failed it before its answer was recorded, and the receipt kept only ``ValueError``."""
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    started = datetime(2026, 9, 28, 5, 9, 42, tzinfo=UTC)
    times = iter((started, started - timedelta(seconds=7)))
    receipts = AcquisitionRepository(paths.database, paths.artifacts)

    with pytest.raises(ValueError, match="acquisition_time_invalid"):
        receipts.capture(
            provider="tushare",
            api_name="fut_wsr",
            parameters={"symbol": "CU"},
            fields="vol",
            parser_version="fixture-parser",
            fetch=lambda: b"{}",
            parse=json.loads,
            normalize=lambda value: value,
            clock=lambda: next(times),
        )

    with sqlite3.connect(paths.database) as connection:
        row = connection.execute(
            "SELECT state, received_at, error_type, structure_check, rejection_reason "
            "FROM acquisition_request"
        ).fetchone()
    # No answer was recorded, so no structure check ran; the reason is kept all the same.
    assert row == ("failed", None, "ValueError", None, "acquisition_time_invalid")


def test_new_official_revision_recovers_from_previous_unknown_time(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    for publication, value, imported in (("09:30", 1.0, 1), ("09:30", 1.1, 2), ("11:30", 1.2, 4)):
        acquired_at = datetime(2026, 8, 9, imported, 45, tzinfo=UTC)
        result = ingest_official_context_document(
            paths,
            cpi_document("发布时间：2026-08-09 " + publication, value),
            family="nbs_core_cpi",
            source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
            expected_period="2026-07",
            fetched_at=acquired_at,
            definition_version="metric-catalog-v0001",
            clock=lambda acquired_at=acquired_at: acquired_at,
        )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        if trace.dimensions["measure"] == "yoy":
            assert trace.claims[0].public_available_at == datetime(2026, 8, 9, 3, 30, tzinfo=UTC)
            assert (
                repository.query(
                    observation_id,
                    mode=AsOfMode.PUBLIC,
                    as_of=datetime(2026, 8, 9, 3, 30, tzinfo=UTC),
                ).selected_value
                == 1.2
            )


@pytest.mark.parametrize(
    ("metadata", "public_at"),
    [
        (b"2026-08-20", datetime(2026, 8, 20, 16, tzinfo=UTC)),
        (b"", None),
        (b"2026-08-20 10:00", datetime(2026, 8, 20, 2, tzinfo=UTC)),
    ],
)
@pytest.mark.usefixtures("runtime_clock")
def test_lpr_import_preserves_actual_publication_precision(
    tmp_path: Path, metadata: bytes, public_at: datetime | None
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    result = ingest_lpr_document(
        paths,
        content.replace(b"2026-08-20 09:00", metadata),
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        expected_period="2026-08",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        assert trace.claims[0].parsed_public_available_at == public_at
        assert trace.acquisition_status == "linked"


@pytest.mark.usefixtures("runtime_clock")
def test_lpr_new_time_revision_has_independent_release_identity(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    results = []
    for body in (content, content.replace(b"09:00", b"10:00").replace(b"3.0%", b"3.1%")):
        results.append(
            ingest_lpr_document(
                paths,
                body,
                source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
                expected_period="2026-08",
                fetched_at=datetime.now(UTC),
                definition_version="metric-catalog-v0001",
            )
        )
    assert results[0].release_event_id != results[1].release_event_id
    repository = EvidenceRepository(paths.database)
    for observation_id in results[1].observation_ids:
        trace = repository.trace(observation_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))
        if trace.dimensions["tenor"] == "1y":
            assert (
                repository.query(
                    observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 20, 2, tzinfo=UTC)
                ).selected_value
                == 3.1
            )


@pytest.mark.parametrize("family", ["lpr", "nbs_core_cpi"])
@pytest.mark.usefixtures("runtime_clock")
def test_official_http_oversize_retains_received_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    limit = 1_000_000 if family == "lpr" else 4_000_000
    body = b"x" * (limit + 100)
    url = (
        "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
        if family == "lpr"
        else "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html"
    )

    class Response(BytesIO):
        headers = {"Content-Type": "text/html"}
        status = 200

        def geturl(self) -> str:
            return url

    module = "pring_cycle.official_lpr" if family == "lpr" else "pring_cycle.official_context"
    monkeypatch.setattr(module + ".urlopen", lambda *args, **kwargs: Response(body))
    with pytest.raises(ValueError, match="size_invalid"):
        if family == "lpr":
            refresh_lpr_release(
                paths,
                source_url=url,
                expected_period="2026-08",
                fetched_at=datetime.now(UTC),
                definition_version="metric-catalog-v0001",
            )
        else:
            refresh_official_context_document(
                paths,
                family=family,
                source_url=url,
                expected_period="2026-07",
                fetched_at=datetime.now(UTC),
                definition_version="metric-catalog-v0001",
            )
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = receipts.history()[0]
    assert receipt.state == "failed"
    assert receipt.received_at is not None
    assert receipts.read_content(receipt.acquisition_id, "raw") == body[: limit + 1]


def test_context_system_query_excludes_one_microsecond_before_validation(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    completed = datetime(2026, 8, 20, 2, 0, 0, 123456, tzinfo=UTC)
    result = ingest_official_context_document(
        paths,
        cpi_document("发布日期未提供"),
        family="nbs_core_cpi",
        source_url="https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html",
        expected_period="2026-07",
        fetched_at=completed,
        clock=lambda: completed,
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        assert (
            repository.query(
                observation_id, mode=AsOfMode.SYSTEM, as_of=completed - timedelta(microseconds=1)
            ).selected_value
            is None
        )
        assert (
            repository.query(observation_id, mode=AsOfMode.SYSTEM, as_of=completed).selected_value
            is not None
        )


@pytest.mark.usefixtures("runtime_clock")
def test_lpr_explicit_timezone_metadata_retains_its_instant(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    content = content.replace(
        b"<time>2026-08-20 09:00</time>",
        b'<meta name="PubDate" content="2026-08-20T01:00:00Z">'
        b'<meta name="PubDate" content="2026-08-20T09:00:00+08:00">',
    )
    result = ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        expected_period="2026-08",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    for observation_id in result.observation_ids:
        assert (
            repository.query(
                observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 20, 0, 59, tzinfo=UTC)
            ).selected_value
            is None
        )
        assert (
            repository.query(
                observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 20, 1, tzinfo=UTC)
            ).selected_value
            is not None
        )


@pytest.mark.usefixtures("runtime_clock")
def test_system_series_respects_exact_secondary_public_cutoff(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    content = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    content = content.replace(b"2026-08-20 09:00", b"2026-08-20T09:00:00.123456")
    ingest_lpr_document(
        paths,
        content,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        expected_period="2026-08",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    released = datetime(2026, 8, 20, 1, 0, 0, 123456, tzinfo=UTC)
    before = repository.metric_series(
        "CN_LPR_1Y_5Y",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        public_as_of=released - timedelta(microseconds=1),
        definition_version="metric-catalog-v0001",
    )
    after = repository.metric_series(
        "CN_LPR_1Y_5Y",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        public_as_of=released,
        definition_version="metric-catalog-v0001",
    )
    assert before == ()
    assert len(after) == 2 and all(point.selected_value is not None for point in after)


def index_response(payload: dict[str, Any]) -> bytes:
    fields = payload["fields"].split(",")
    row = {
        "ts_code": payload["params"].get("ts_code"),
        "trade_date": "20260828",
        "close": 1234.5,
        "date": "20260828",
        "y2": 3.6,
        "y10": 4.2,
    }
    return json.dumps(
        {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields]]}}
    ).encode()


@pytest.mark.usefixtures("runtime_clock")
def test_ingest_rejection_after_a_passed_structure_check_is_kept_on_the_receipt(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("fixture-secret", transport=index_response)

    # The frozen v3 contract refuses these claims only once they reach the evidence store.
    with pytest.raises(ValueError, match="source_certification_contract_unresolved"):
        adapter.acquire_scalars(
            paths,
            lambda: adapter.market_indices(
                start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            ),
            definition_version="metric-catalog-v0003",
        )

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    history = receipts.history()
    assert history and all(receipt.state == "validated" for receipt in history)
    assert {receipts.ingest_result(receipt.acquisition_id) for receipt in history} == {
        ("rejected", "source_certification_contract_unresolved:metric-catalog-v0003")
    }


@pytest.mark.usefixtures("runtime_clock")
def test_accepted_ingest_is_kept_on_the_receipt(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("fixture-secret", transport=index_response)

    adapter.acquire_scalars(
        paths,
        lambda: adapter.treasury_yields(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version="metric-catalog-v0002",
    )

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert {receipts.ingest_result(r.acquisition_id) for r in receipts.history()} == {
        ("accepted", None)
    }


@pytest.mark.usefixtures("runtime_clock")
def test_an_ingest_result_is_written_once_and_never_rewritten(tmp_path: Path) -> None:
    import sqlite3

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("fixture-secret", transport=index_response)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.treasury_yields(start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)),
        definition_version="metric-catalog-v0002",
    )
    (receipt,) = AcquisitionRepository(paths.database, paths.artifacts).history()

    for update in (
        "UPDATE acquisition_request SET ingest_rejection_reason='rewritten'",
        "UPDATE acquisition_request SET ingest_result='rejected'",
    ):
        with (
            pytest.raises(sqlite3.IntegrityError, match="acquisition_ingest_result_is_immutable"),
            sqlite3.connect(paths.database) as connection,
        ):
            connection.execute(update + " WHERE acquisition_id=?", (receipt.acquisition_id,))
