"""Public Worker acceptance for the combined acquisition repairs.

All changed releases and HTTP rows are synthetic software fixtures. The isolated candidate
passes the public lifecycle; ECB intentionally remains uncertified. This is not a real-source
certification or an operational activation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.ecb_reference import ECB_HISTORY_URL, ECB_METRIC
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RetrievalScope, RunRepository
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.worker import process_pending_run
from tests.conftest import install_runtime_clock
from tests.fixtures.delivery_assertions import assert_certified_points, assert_certified_rows
from tests.integration.test_ecb_reference_acquisition import zip_csv
from tests.integration.test_worker_registered_catalog import (
    AUGUST_PPI_URL,
    august_ppi_document,
    extended_context_opener,
    extended_core_opener,
)
from tests.models.test_isolated_lifecycle import isolated_lifecycle_material

PBC_LISTING = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"
PBC_AUGUST = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026090916320925645/index.html"
NBS_LISTING = "https://www.stats.gov.cn/sj/zxfb/"


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    # After the new profile's fixed external acquisition clock, before Shanghai midnight.
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 13, tzinfo=UTC))


def august_money_document() -> bytes:
    """Synthetic August publication; the archived July values are deliberately unchanged."""
    content = (
        Path(__file__).parents[1] / "fixtures/official_period_fallback/pbc_money.html"
    ).read_text()
    for old, new in (
        ("2026年7月", "2026年8月"),
        ("7月末", "8月末"),
        ("前七个月", "前八个月"),
        ("2026-08-14", "2026-09-09"),
        ("2026年08月14日", "2026年09月09日"),
        ("2026081416320925645", "2026090916320925645"),
    ):
        content = content.replace(old, new)
    return content.encode()


def core_through_current_target() -> Any:
    archive = extended_core_opener()

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            params = payload["params"]
            document = json.loads(archive.open(request, timeout=timeout).read())
            fields = document["data"]["fields"]
            calendar = payload["api_name"] == "trade_cal"
            close = 0.0
            if not calendar:
                all_dates = {**payload, "params": {**params, "start_date": "20170101"}}
                rows = json.loads(
                    archive.open(
                        Request(request.full_url, json.dumps(all_dates).encode()), timeout=timeout
                    ).read()
                )["data"]["items"]
                close = max(rows, key=lambda item: item[1])[fields.index("close")]
            added = []
            for day in ("20260914", "20260915", "20260916", "20260917", "20260918"):
                if params["start_date"] <= day <= params["end_date"]:
                    row = (
                        {"cal_date": day, "is_open": 1}
                        if calendar
                        else {
                            "ts_code": params["ts_code"],
                            "trade_date": day,
                            "close": close,
                            "pre_close": close,
                            "pct_chg": 0.0,
                        }
                    )
                    added.append([row[field] for field in fields])
            document["data"]["items"] = added[::-1] + document["data"]["items"]
            return BytesIO(json.dumps(document).encode())

    return Opener()


def serve_deliveries(
    monkeypatch: pytest.MonkeyPatch, *, official_available: bool, invalid_money: bool = False
) -> tuple[list[str], bytes]:
    requested: list[str] = []
    archive = extended_context_opener(requested)
    ecb = zip_csv("Date,USD,CNY,\n2026-09-10,1.1,7.7,\n2026-09-17,1.1481,7.7009,\n")

    class Context:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            api = payload["api_name"]
            if api not in {"cn_m", "sf_month", "cn_cpi", "cn_ppi"}:
                return archive.open(request, timeout=timeout)
            requested.append(api)
            if api == "cn_m" and invalid_money:
                return BytesIO(b'{"code":0,"data":{"fields":[],"items":[[]]}}')
            fields = payload["fields"].split(",")
            row = {
                "month": "202608",
                "m1": 1_150_000.0,
                "m1_yoy": 4.1,
                "m2": 3_550_000.0,
                "m2_yoy": 7.6,
            }
            return BytesIO(
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "fields": fields,
                            "items": [[row[field] for field in fields]] if api == "cn_m" else [],
                        },
                    }
                ).encode()
            )

    class Response(BytesIO):
        status = 200

        def __init__(self, body: bytes, url: str, mime: str):
            super().__init__(body)
            self.url = url
            self.headers = {"Content-Type": mime, "Content-Length": str(len(body))}

        def geturl(self) -> str:
            return self.url

    def official(request: Any, *, timeout: float) -> Response:
        url = request.full_url
        requested.append(url)
        if url == ECB_HISTORY_URL:
            return Response(ecb, url, "application/zip")
        pages = {
            NBS_LISTING: f'<a href="{AUGUST_PPI_URL}">2026年8月份工业生产者出厂价格</a>'.encode(),
            AUGUST_PPI_URL: august_ppi_document(),
            PBC_LISTING: f'<a href="{PBC_AUGUST}">2026年8月金融统计数据报告</a>'.encode(),
            PBC_AUGUST: august_money_document(),
        }
        if not official_available or url not in pages:
            raise OSError("fixture official source unavailable")
        return Response(pages[url], url, "text/html")

    monkeypatch.setattr(
        "pring_cycle.source_adapters.build_opener", lambda *h: core_through_current_target()
    )
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *h: Context())
    monkeypatch.setattr("pring_cycle.official_context.urlopen", official)
    monkeypatch.setattr("pring_cycle.ecb_reference.open_no_redirects", official)
    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", official)
    return requested, ecb


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("official_available", [True, False])
def test_integrated_worker_preserves_delivery_time_and_source_in_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, official_available: bool
) -> None:
    paths, material = isolated_lifecycle_material(
        tmp_path / "runtime", profile="acquisition-repairs"
    )
    candidate = material["candidate_model_version_id"]
    version = material["metric_catalog_version"]
    models = ModelRepository(paths.database)
    assert models.active().model_version_id == candidate
    assert models.acceptance_details(candidate, material["acceptance_result_hash"])["passed"]
    assert material["replay_trading_days"] == 120
    manifest = models.manifest(candidate)
    assert manifest["point_in_time_rule_version"] == "dual-cutoff-v0003"
    assert len(manifest["metric_definitions"]) == 59
    assert sum(d["priority"] == "P1" for d in manifest["metric_definitions"]) == 42
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n")
    paths.secrets.chmod(0o600)
    requested, ecb_raw = serve_deliveries(monkeypatch, official_available=official_available)
    runs = RunRepository(paths.database)
    evidence = EvidenceRepository(paths.database)
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    previous_sf_failure = None

    # The historical acceptance target stays fixed. A separate present-day software case
    # demonstrates SYSTEM adoption; neither changes the real operational acceptance target.
    for target in ("2026-09-11", "2026-09-18"):
        pbc_calls_before = requested.count(PBC_LISTING)
        submitted = runs.submit_manual_full(
            target_business_date=target,
            client_request_id=f"integrated-delivery-{target}",
            model_version_id=candidate,
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        stored = runs.get(submitted.run_id)
        assert stored.status == "completed", stored.error_classification
        projection = ProjectionSetRepository(paths.database).get(stored.projection_set_id or "")
        assert stored.cutoffs_frozen
        assert stored.system_as_of == stored.report_cutoff == projection.envelope.system_as_of
        plan = runs.full_retrieval_plan(stored.run_id)
        assert plan["final"]["system_as_of"] == stored.system_as_of.isoformat()
        adopted = set(plan["adoption"]["selected_claim_ids"])
        snapshot = next(
            item["reference"]
            for item in runs.reusable_checkpoints(stored.run_id)
            if item["kind"] == "report_snapshot"
        )
        report = ReportRepository(paths.database).get(snapshot)
        assert report.projection_set_id == projection.envelope.projection_set_id
        scope = RetrievalScope("pbc-money:2026-08", ("CN_M1_M2",), "2026-08", "P1", None)
        assert not ModelInputSelector(paths, stored, mode=AsOfMode.PUBLIC).select(scope).complete
        selected = ModelInputSelector(paths, stored).select(scope)
        assert selected.complete is (target == "2026-09-18")
        money = [
            p
            for p in evidence.metric_series(
                "CN_M1_M2",
                mode=AsOfMode.SYSTEM,
                as_of=stored.system_as_of,
                definition_version=version,
            )
            if p.period_end == "2026-08-31"
        ]
        assert len(money) == 4
        assert_certified_points(money, "tushare")
        assert all(
            c.provider == "tushare" and c.public_available_at is None
            for p in money
            for c in p.claims
        )
        money_ids = {str(p.selected_claim_id) for p in money}
        if target == "2026-09-18":
            assert money_ids <= adopted
        else:
            assert not money_ids & adopted
        # The PBC shared page is only adopted for the missing SF delivery. Its different money
        # values cannot overwrite the TuShare delivery merely because PUBLIC is unavailable.
        for metric in ("CN_PPI", "CN_SF_TOTAL"):
            scope = RetrievalScope("official:2026-08", (metric,), "2026-08", "P1", None)
            result = ModelInputSelector(paths, stored).select(scope)
            assert result.complete is official_available
            if official_available:
                assert set(result.selected_claim_ids) <= adopted
        for prices in (projection.datasets["macro"]["price_chain"], report.body["price_context"]):
            ppi = [
                row
                for row in prices["evidence"]
                if row["metric_id"] == "CN_PPI" and row["period"] == "2026-08-31"
            ]
            assert bool(ppi) is official_available
            if official_available:
                assert_certified_rows(ppi, "国家统计局")
        for context in (
            projection.datasets["macro"]["credit"],
            report.body["policy_context"]["credit"],
        ):
            sf = [
                row
                for row in context["evidence"]
                if row["metric_id"] == "CN_SF_TOTAL" and row["period"] == "2026-08-31"
            ]
            assert bool(sf) is official_available
            if official_available:
                assert_certified_rows(sf, "中国人民银行")
            money_rows = [
                row
                for row in context["evidence"]
                if row["metric_id"] == "CN_M1_M2" and row["period"] == "2026-08-31"
            ]
            assert bool(money_rows) is (target == "2026-09-18")
            if target == "2026-09-18":
                assert_certified_rows(money_rows, "tushare")
        owned = plan["acquisitions"]
        if not official_available:
            # Both targets query the same release. A still-live negative cache reuses
            # the previous physical failure; its blocked acquisition sends no HTTP.
            failed_official = [
                r for r in owned if "CN_SF_TOTAL" in r["metric_ids"] and r["state"] == "failed"
            ]
            assert failed_official
            ledger = stored.retrieval_ledger
            assert ledger is not None
            if all(r["error_type"] == "OSError" for r in failed_official):
                assert len(failed_official) == 3
                assert requested.count(PBC_LISTING) - pbc_calls_before == 3
                acquisition_ids = {r["acquisition_id"] for r in failed_official}
                physical = [
                    r for r in ledger["requests"] if r["acquisition_id"] in acquisition_ids
                ]
                assert len(physical) == 3
                assert all(r["classification"] == "transient_transport_error" for r in physical)
                if previous_sf_failure is not None:
                    assert datetime.fromisoformat(physical[0]["started_at"]) >= (
                        datetime.fromisoformat(previous_sf_failure["cache_expires_at"])
                    )
                previous_sf_failure = physical[-1]
            else:
                assert len(failed_official) == 1
                assert failed_official[0]["error_type"] == "RetrievalBudgetBlocked"
                assert previous_sf_failure is not None
                cached = [q for q in ledger["queries"] if q["query_text"] == PBC_LISTING]
                assert len(cached) == 1
                query = cached[0]
                assert query["classification"] == "negative_cache_active"
                assert query["cache_hit"] and query["physical_request_id"] is None
                assert query["reused_request_id"] == previous_sf_failure["request_id"]
                assert query["next_eligible_at"] == previous_sf_failure["cache_expires_at"]
                assert datetime.fromisoformat(query["attempted_at"]) < datetime.fromisoformat(
                    query["next_eligible_at"]
                )
                assert requested.count(PBC_LISTING) == pbc_calls_before
        ecb = [r for r in owned if ECB_METRIC in r["metric_ids"]]
        assert ecb and all(r["state"] == "validated" for r in ecb)
        assert acquisitions.read_content(ecb[0]["acquisition_id"], "raw") == ecb_raw
        assert (
            not ModelInputSelector(paths, stored)
            .select(RetrievalScope("ecb:2026-09-10", (ECB_METRIC,), "2026-09-10", "P2", None))
            .complete
        )
        assert not any(
            row.selected_claim_id in adopted
            for row in evidence.metric_series(
                ECB_METRIC,
                mode=AsOfMode.SYSTEM,
                as_of=stored.system_as_of,
                definition_version=version,
            )
        )
        deliveries = [r for r in acquisitions.history() if r.api_name == "cn_m"]
        assert deliveries and all(r.fields == "month,m1,m1_yoy,m2,m2_yoy" for r in deliveries)
        empty = [r for r in acquisitions.history() if r.api_name == "sf_month"]
        assert empty and all(
            json.loads(acquisitions.read_content(r.acquisition_id, "raw"))["data"]["items"] == []
            for r in empty
        )

    assert ECB_HISTORY_URL in requested
    assert (PBC_AUGUST in requested) is official_available
    assert (AUGUST_PPI_URL in requested) is official_available

    if official_available:
        # Invalid delivered P1 schema is a failure, not an empty response eligible for fallback.
        published_id = ProjectionSetRepository(paths.database).current().envelope.projection_set_id
        serve_deliveries(monkeypatch, official_available=True, invalid_money=True)
        invalid = runs.submit_manual_full(
            target_business_date="2026-09-18",
            client_request_id="integrated-invalid-required-delivery",
            model_version_id=candidate,
            system_as_of=datetime.now(UTC),
        )
        process_pending_run(paths, report_adapters=())
        rejected = runs.get(invalid.run_id)
        assert rejected.status == "action_required"
        assert (rejected.error_classification or "").startswith("worker_failure:ValueError:")
        assert rejected.projection_set_id is None
        assert (
            ProjectionSetRepository(paths.database).current().envelope.projection_set_id
            == published_id
        )
        owned = runs.full_retrieval_plan(rejected.run_id)["acquisitions"]
        failed = [r for r in owned if r["api_name"] == "cn_m" and r["state"] == "failed"]
        assert failed and all(r["metric_ids"] == ["CN_M1_M2"] for r in failed)
        attempt = evidence.latest_retrieval_attempt(
            "CN_M1_M2", period=None, as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None and attempt.outcome == "validation_failed"
