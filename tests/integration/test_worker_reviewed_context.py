"""Worker acquisition uses the exact reviewed money and financing delivery contracts.

Candidates and HTTP rows here are synthetic software fixtures. Full publication is checked
separately through the activated isolated lifecycle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

import pring_cycle.tushare_context as tushare_context
from pring_cycle import credit_impulse
from pring_cycle.acquisition import AcquisitionRepository, ReceiptCounts, own_acquisitions
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.full_run_requirements import run_lookback
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RetrievalScope, RunRecord, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.worker import refresh_context_sources
from tests.conftest import install_runtime_clock
from tests.fixtures.model_registration import bind_synthetic_review, encode, save, submit
from tests.integration.test_ecb_reference_acquisition import certified_request

PBC_LISTING = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Any:
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 1, tzinfo=UTC))


def system_request(paths: RuntimePaths) -> dict[str, Any]:
    request = certified_request(paths)
    request["manifest"]["point_in_time_rule_version"] = "dual-cutoff-v0003"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    return request


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
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )

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


# 2024-Q2 to 2026-Q2, census-revised as TuShare delivers them (run findings 2026-09-28).
_GDP_YTD = {
    "2024Q2": 633599.4,
    "2024Q3": 974553.8,
    "2024Q4": 1348066.2,
    "2025Q1": 318466.4,
    "2025Q2": 659861.6,
    "2025Q3": 1013967.9,
    "2025Q4": 1401879.2,
    "2026Q1": 334192.9,
    "2026Q2": 695704.0,
}


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    ("refetched_level", "status"),
    [
        (None, "available"),
        # A gap refetches each quarter alone; the same level is still the same vintage.
        (659861.6, "available"),
        # A revised end matches no delivery of both, so its release must reconcile it.
        (662000.0, "incomparable_gdp_vintages"),
        # A parent whose original no longer agrees cannot be adopted.
        ("damaged_social_financing", "incomplete_source_artifacts"),
    ],
)
def test_credit_impulse_computes_from_levels_tushare_delivered_together(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    refetched_level: float | str | None,
    status: str,
) -> None:
    """One delivery is one vintage: its quarters need no release to reconcile (ticket 13).

    The check against each statistics bureau release stays for levels from different
    releases; TuShare's revised series has none, so it held the impulse missing for good.
    """
    from pring_cycle.context_projection import build_context_projection

    paths, run, version = reviewed_run(
        tmp_path, capsys, extra_markers={"CN_GDP": "tushare:cn_gdp:official-sampled-v0001"}
    )
    months = [f"{year}{month:02d}" for year in (2024, 2025, 2026) for month in range(1, 13)]
    months = months[months.index("202408") : months.index("202608") + 1]
    rows = {
        "sf_month": [
            {
                "month": month,
                "inc_cumval": 30000.0 * int(month[4:]),
                "stk_endval": 400.0 + index,
            }
            for index, month in enumerate(months)
        ],
        "cn_gdp": [
            {
                "quarter": quarter,
                "gdp": level,
                "gdp_yoy": 5.0,
                "pi": level * 0.07,
                "pi_yoy": 3.5,
                "si": level * 0.36,
                "si_yoy": 5.0,
                "ti": level * 0.57,
                "ti_yoy": 5.0,
            }
            for quarter, level in _GDP_YTD.items()
        ],
    }

    class Opener:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            fields = payload["fields"].split(",")
            items = [[row[field] for field in fields] for row in rows.get(payload["api_name"], [])]
            if not items:
                raise OSError("fixture source unavailable")
            return BytesIO(
                json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()
            )

    context_http(monkeypatch, {})
    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *args: Opener())

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )
    if refetched_level == "damaged_social_financing":
        (receipt,) = (
            receipt
            for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
            if receipt.api_name == "sf_month" and receipt.raw_hash is not None
        )
        (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged")
    elif refetched_level is not None:
        rows["cn_gdp"] = [dict(rows["cn_gdp"][4], gdp=refetched_level)]
        assert rows["cn_gdp"][0]["quarter"] == "2025Q2"
        adapter = tushare_context.TushareContextAdapter("fixture-only")
        adapter.acquire_scalars(
            paths,
            lambda: adapter.gdp(start_quarter="2025Q2", end_quarter="2025Q2"),
            definition_version=version,
        )

    manifest = ModelRepository(paths.database).manifest(run.model_version_id)
    derived = credit_impulse.derive(
        EvidenceRepository(paths.database),
        manifest["derived_formula_versions"]["credit_impulse"],
        as_of=datetime.now(UTC),
        as_of_mode=AsOfMode.SYSTEM,
        definition_version=version,
    )
    assert derived.status == status, derived
    # A failure names the parent and periods behind it (ticket 28).
    failures = [(f.metric_id, f.reason, f.periods, f.members) for f in derived.failures]
    if status == "incomparable_gdp_vintages":
        # Q2 fetched again alone changes Q2 and the Q3 differenced from it.
        assert failures == [
            (
                "CN_GDP",
                "incomparable_gdp_vintages",
                ("2025-Q2", "2025-Q3"),
                ('CN_GDP:{"aggregate": "total", "measure": "nominal_ytd_level"}',),
            )
        ]
    elif status == "incomplete_source_artifacts":
        # The damaged original carried every month, the base month too.
        assert failures == [
            (
                "CN_SF_TOTAL",
                "not_adoptable",
                tuple(f"{month[:4]}-{month[4:]}" for month in months),
                ('CN_SF_TOTAL:{"measure": "ytd_increment"}',),
            )
        ]
    else:
        assert derived.failures == ()
    if refetched_level is None:
        # The delivery reaches the analysis: the projection reads the same derivation.
        context = build_context_projection(
            EvidenceRepository(paths.database), as_of=datetime.now(UTC), model_manifest=manifest
        )
        assert context.macro["credit"]["formula"]["status"] == status  # type: ignore[index]


def credit_coverage(
    paths: RuntimePaths, run: RunRecord, *, turned_off: bool = False
) -> credit_impulse.InputPeriods:
    """What the Worker's fetch covers for the run's target day alone, as it decides it."""
    rules = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(run.model_version_id)
    )
    if turned_off:
        rules = replace(rules, formula_versions={})
    return run_lookback(
        paths,
        rules,
        run,
        decided_at=datetime.now(UTC),
        window=(date.fromisoformat(run.target_business_date),),
    ).coverage


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("formula", ["configured", "turned_off"])
def test_credit_inputs_are_fetched_back_to_the_differencing_baseline(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    formula: str,
) -> None:
    """The impulse differences 24 months and 8 quarters of year-to-date figures (ticket 09).

    On 2026-09-18 the newest released periods are 2026-08 and 2026-Q2, so the fetch must
    start at 2024-08 and 2024-Q2, the baselines before each window. Turned off, the
    formula adds nothing to the two series' own range (ticket 24).
    """
    paths, run, version = reviewed_run(tmp_path, capsys)
    coverage = credit_coverage(paths, run, turned_off=formula == "turned_off")
    context_http(monkeypatch, {})
    requested: dict[str, dict[str, str]] = {}
    original_open = tushare_context.build_opener().open

    class Recording:
        def open(self, request: Any, *, timeout: float) -> BytesIO:
            payload = json.loads(request.data)
            requested[payload["api_name"]] = payload["params"]
            return original_open(request, timeout=timeout)

    monkeypatch.setattr("pring_cycle.tushare_context.build_opener", lambda *args: Recording())

    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(
            paths, run.target_business_date, definition_version=version, covered=coverage
        )

    # Their own range starts at the period before the newest out on the window's first
    # day, here the target's own (no calendar holds a window): 2026-07, 2026-Q1 (ticket 30).
    starts = ("202408", "2024Q2") if formula == "configured" else ("202607", "2026Q1")
    assert requested["sf_month"] == {"start_m": starts[0], "end_m": "202609"}
    assert requested["cn_gdp"] == {"start_q": starts[1], "end_q": "2026Q3"}


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
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )

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
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        metric, period=None, as_of=datetime.now(UTC), definition_version=version
    )
    # The source delivered none: an empty delivery, no failure (ticket 18).
    assert attempt is not None and attempt.outcome == "succeeded"
    assert attempt.safe_metadata["completeness"] == "source_empty"

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
    # The direct refresh and the gap retrieval's TuShare step both received no rows.
    empties = [
        receipt
        for receipt in AcquisitionRepository(paths.database, paths.artifacts).history()
        if receipt.api_name == api
    ]
    assert empties
    for empty in empties:
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

    # Gate ③ rejects the response and records it; a P1 parse error no longer stops the run.
    with own_acquisitions(paths.database, run.run_id, "direct_context_refresh"):
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )

    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        "CN_M1_M2", period=None, as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "structure_rejected"


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
        refresh_context_sources(
            paths,
            run.target_business_date,
            definition_version=version,
            covered=credit_coverage(paths, run),
        )

    evidence = EvidenceRepository(paths.database)
    for metric in markers:
        attempt = evidence.latest_retrieval_attempt(
            metric, period=None, as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None and attempt.outcome == "succeeded"
        assert attempt.safe_metadata["completeness"] == "source_empty"
        assert not evidence.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )


@pytest.mark.usefixtures("runtime_clock")
def test_a_january_ppi_cumulative_field_refuses_neither_ppi_nor_cpi(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """TuShare fills January's cumulative PPI the official contract has no member for; it is
    left out, so CPI and PPI over a year boundary are both accepted (run findings 06)."""
    paths, _run, version = reviewed_run(
        tmp_path,
        capsys,
        extra_markers={
            "CN_CPI_HEADLINE": "tushare:cn_cpi:official-sampled-v0001",
            "CN_PPI": "tushare:cn_ppi:official-sampled-v0001",
        },
    )
    months = ("202512", "202601", "202602")

    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        # Every field of every month non-empty, January's cumulative columns included.
        items = [
            [month if field == "month" else round(-1.0 + index * 0.1, 1) for field in fields]
            for index, month in enumerate(months)
        ]
        return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

    adapter = tushare_context.TushareContextAdapter("fixture-only", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.prices(start_month="202512", end_month="202602"),
        definition_version=version,
    )

    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    by_api = {receipt.api_name: receipt for receipt in receipts.history()}
    for api, scalars in (("cn_cpi", 9), ("cn_ppi", 3 * 9 - 3)):
        identity = by_api[api].acquisition_id
        assert receipts.ingest_result(identity) == ("accepted", None)
        assert receipts.counts(identity) == ReceiptCounts(
            source_records=3, normalized_scalars=scalars, ingested_claims=scalars
        )
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_PPI", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert {
        (point.period_end[:7], point.dimensions["category"], point.dimensions["measure"])
        for point in points
    } == {
        (month, category, measure)
        for month in ("2025-12", "2026-01", "2026-02")
        for category in ("headline", "means_of_production", "consumer_goods")
        for measure in ("mom", "yoy", "cumulative_average_yoy")
        if month != "2026-01" or measure != "cumulative_average_yoy"
    }
    # Rebuilding from the original leaves out the same field, so every selected claim holds.
    assert tushare_context.tushare_claims_matching_acquisitions(
        evidence,
        points,
        definition_version=version,
        parse=tushare_context.parse_ppi_acquisition,
    ) == {point.selected_claim_id for point in points}
