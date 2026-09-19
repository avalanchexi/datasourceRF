"""Worker acquisition uses the exact reviewed money and financing delivery contracts.

Candidates and HTTP rows here are synthetic software fixtures. Full publication is checked
separately through the activated isolated lifecycle.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository, own_acquisitions
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.worker import refresh_context_sources
from tests.integration.test_system_target_inputs import runtime_clock as runtime_clock
from tests.integration.test_system_target_inputs import system_request
from tests.models.test_candidate_admission import bind_synthetic_review, encode, save, submit

PBC_LISTING = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"


def reviewed_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    target: str = "2026-09-18",
    extra_markers: dict[str, str] | None = None,
) -> tuple[RuntimePaths, RunRecord, str]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    request = system_request(paths)
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    markers = {
        "CN_M1_M2": "tushare:cn_m:official-sampled-v0001",
        "CN_SF_TOTAL": "tushare:sf_month:official-sampled-v0001",
        **(extra_markers or {}),
    }
    for definition in request["manifest"]["metric_definitions"]:
        metric = definition["metric_id"]
        if metric in markers:
            if metric in {"CN_M1_M2", "CN_SF_TOTAL"}:
                definition["source_candidates"] = [PBC_LISTING]
            if metric == "CN_GDP":
                definition["certification_status"] = "certified"
            definition["source_codes"] = [*definition["source_codes"], markers[metric]]
            package["definition_bindings"][metric] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n")
    paths.secrets.chmod(0o600)
    run = RunRepository(paths.database).submit_manual_full(
        target_business_date=target,
        client_request_id="reviewed-context-refresh",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    return paths, run, version


def context_http(
    monkeypatch: pytest.MonkeyPatch, deliveries: dict[str, dict[str, Any] | None]
) -> None:
    """Respond at the HTTP boundary; unprovided APIs are unavailable, never stubbed services."""

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            if payload["api_name"] not in deliveries:
                raise OSError("fixture source unavailable")
            fields = payload["fields"].split(",")
            row = deliveries[payload["api_name"]]
            return BytesIO(
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "fields": fields,
                            "items": [[row[field] for field in fields]] if row else [],
                        },
                    }
                ).encode()
            )

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise OSError("fixture official source unavailable")

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *args: Opener())
    monkeypatch.setattr("pring_cycle.ecb_reference.open_no_redirects", unavailable)
    monkeypatch.setattr("pring_cycle.eia_html.open_no_redirects", unavailable)


@pytest.mark.usefixtures("runtime_clock")
def test_worker_money_delivery_satisfies_the_new_four_member_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run, version = reviewed_run(tmp_path, capsys)
    context_http(
        monkeypatch,
        {
            "cn_m": {
                "month": "202608",
                "m1": 1_150_000.0,
                "m1_yoy": 4.1,
                "m1_mom": 0.1,
                "m2": 3_550_000.0,
                "m2_yoy": 7.6,
                "m2_mom": 0.2,
            }
        },
    )

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    scope = RetrievalScope("pbc-money:2026-08", ("CN_M1_M2",), "2026-08", "P1", None)
    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete and len(selected.selected_claim_ids) == 4
    points = EvidenceRepository(paths.database).metric_series(
        "CN_M1_M2", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert {
        (p.dimensions["aggregate"], p.dimensions["measure"]): p.selected_value for p in points
    } == {
        ("m1", "balance"): 1_150_000.0,
        ("m1", "yoy"): 4.1,
        ("m2", "balance"): 3_550_000.0,
        ("m2", "yoy"): 7.6,
    }
    assert not ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope).complete
    (receipt,) = [
        item
        for item in AcquisitionRepository(paths.database, paths.artifacts).history()
        if item.api_name == "cn_m"
    ]
    assert receipt.fields == "month,m1,m1_yoy,m2,m2_yoy"
    (owned,) = [
        item
        for item in RunRepository(paths.database).full_retrieval_plan(run.run_id)["acquisitions"]
        if item["acquisition_id"] == receipt.acquisition_id
    ]
    assert owned["metric_ids"] == ["CN_M1_M2"] and owned["state"] == "validated"


@pytest.mark.usefixtures("runtime_clock")
def test_worker_sf_delivery_preserves_annual_flow_and_month_end_stock(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run, version = reviewed_run(tmp_path, capsys)
    context_http(
        monkeypatch,
        {
            "sf_month": {
                "month": "202608",
                "inc_month": 3500.0,
                "inc_cumval": 220000.0,
                "stk_endval": 460.0,
            }
        },
    )

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    scope = RetrievalScope("pbc-sf:2026-08", ("CN_SF_TOTAL",), "2026-08", "P1", None)
    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete and len(selected.selected_claim_ids) == 2
    points = EvidenceRepository(paths.database).metric_series(
        "CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert {
        p.dimensions["measure"]: (p.period_start, p.period_end, p.selected_value) for p in points
    } == {
        "ytd_increment": ("2026-01-01", "2026-08-31", 220000.0),
        "stock_end": ("2026-08-01", "2026-08-31", 4600000.0),
    }
    assert all(c.unit == "hundred_million_cny" for p in points for c in p.claims)
    assert not ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope).complete
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = [r for r in acquisitions.history() if r.api_name == "sf_month"]
    assert receipt.fields == "month,inc_cumval,stk_endval"
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert {r["source_field"]: r["period_kind"] for r in normalized} == {
        "inc_cumval": "year_to_month",
        "stk_endval": "month",
    }
    (owned,) = [
        item
        for item in RunRepository(paths.database).full_retrieval_plan(run.run_id)["acquisitions"]
        if item["acquisition_id"] == receipt.acquisition_id
    ]
    assert owned["metric_ids"] == ["CN_SF_TOTAL"] and owned["state"] == "validated"


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "metric,api,members", [("CN_M1_M2", "cn_m", 4), ("CN_SF_TOTAL", "sf_month", 2)]
)
def test_missing_rows_reach_official_fallback_instead_of_stopping_the_refresh(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    metric: str,
    api: str,
    members: int,
) -> None:
    paths, submitted, version = reviewed_run(tmp_path, capsys, target="2026-08-28")
    context_http(monkeypatch, {api: None})
    article = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html"
    requested: list[str] = []

    class Response(BytesIO):
        status = 200
        headers = {"Content-Type": "text/html"}

        def __init__(self, content: bytes, url: str):
            super().__init__(content)
            self.url = url

        def geturl(self) -> str:
            return self.url

    def official(request: Any, *, timeout: float) -> Response:
        url = request.full_url
        requested.append(url)
        if url == PBC_LISTING:
            content = f'<a href="{article}">2026年7月金融统计数据报告</a>'.encode()
        elif url == article:
            content = (
                Path(__file__).parents[1] / "fixtures/official_period_fallback/pbc_money.html"
            ).read_bytes()
        else:
            raise OSError("fixture official unavailable")
        return Response(content, url)

    monkeypatch.setattr("pring_cycle.official_context.urlopen", official)
    runs = RunRepository(paths.database)
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        metric, period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "missing_values"

    FullRunRetrieval(paths).retrieve(run)

    assert article in requested
    scope = RetrievalScope("pbc-statistics:2026-07", (metric,), "2026-07", "P1", None)
    selected = ModelInputSelector(paths, runs.get(run.run_id)).select(scope)
    assert selected.complete and len(selected.selected_claim_ids) == members
    assert (
        ModelInputSelector(paths, runs.get(run.run_id), mode=AsOfMode.PUBLIC).select(scope).complete
    )
    points = evidence.metric_series(
        metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert all(claim.provider == "中国人民银行" for p in points for claim in p.claims)
    (empty,) = [
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.api_name == api
    ]
    raw = AcquisitionRepository(paths.database, paths.artifacts).read_content(
        empty.acquisition_id, "raw"
    )
    assert json.loads(raw)["data"]["items"] == []


@pytest.mark.usefixtures("runtime_clock")
def test_legacy_catalog_keeps_six_money_and_three_financing_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    paths.secrets.write_text("TUSHARE_TOKEN=fixture-only\n")
    paths.secrets.chmod(0o600)
    context_http(
        monkeypatch,
        {
            "cn_m": {
                "month": "202608",
                "m1": 1150000,
                "m1_yoy": 4.1,
                "m1_mom": 0.1,
                "m2": 3550000,
                "m2_yoy": 7.6,
                "m2_mom": 0.2,
            },
            "sf_month": {
                "month": "202608",
                "inc_month": 3500,
                "inc_cumval": 220000,
                "stk_endval": 460,
            },
        },
    )

    refresh_context_sources(paths, "2026-09-18", definition_version="metric-catalog-v0002")

    receipts = {
        r.api_name: r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name in {"cn_m", "sf_month"}
    }
    assert receipts["cn_m"].fields == "month,m1,m1_yoy,m1_mom,m2,m2_yoy,m2_mom"
    assert receipts["sf_month"].fields == "month,inc_month,inc_cumval,stk_endval"
    assert all(r.state == "validated" for r in receipts.values())
    evidence = EvidenceRepository(paths.database)
    assert (
        len(evidence.metric_series("CN_M1_M2", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC))) == 6
    )
    assert (
        len(evidence.metric_series("CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)))
        == 3
    )


@pytest.mark.usefixtures("runtime_clock")
def test_reviewed_delivery_does_not_treat_invalid_month_as_missing_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paths, run, version = reviewed_run(tmp_path, capsys)
    context_http(
        monkeypatch,
        {
            "cn_m": {
                "month": "not-a-month",
                "m1": 1150000,
                "m1_yoy": 4.1,
                "m2": 3550000,
                "m2_yoy": 7.6,
            }
        },
    )

    with (
        pytest.raises(ValueError),
        own_acquisitions(paths.database, run.run_id, "direct_context_refresh"),
    ):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "CN_M1_M2", period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "validation_failed"


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "apis,markers",
    [
        (
            ("cn_cpi", "cn_ppi"),
            {
                "CN_CPI_HEADLINE": "tushare:cn_cpi:official-sampled-v0001",
                "CN_PPI": "tushare:cn_ppi:official-sampled-v0001",
            },
        ),
        (
            ("cn_pmi",),
            {
                "CN_PMI_ACTIVITY": "tushare:cn_pmi:official-sampled-v0001",
                "CN_PMI_INVENTORY": "tushare:cn_pmi:official-sampled-v0001",
                "CN_PMI_PRICES": "tushare:cn_pmi:official-sampled-v0001",
            },
        ),
        (("cn_gdp",), {"CN_GDP": "tushare:cn_gdp:official-sampled-v0001"}),
    ],
)
def test_other_reviewed_families_keep_empty_delivery_as_an_acquisition_gap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    apis: tuple[str, ...],
    markers: dict[str, str],
) -> None:
    paths, run, version = reviewed_run(tmp_path, capsys, extra_markers=markers)
    context_http(monkeypatch, {api: None for api in apis})

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(paths, run.target_business_date, definition_version=version)

    evidence = EvidenceRepository(paths.database)
    for metric in markers:
        attempt = evidence.latest_retrieval_attempt(
            metric, period=None, as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None and attempt.outcome == "missing_values"
        assert not evidence.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
