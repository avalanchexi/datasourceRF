"""SF delivery uses the registered total's periods and retains its physical evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.confirmation import MANIFEST_FIELDS
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository, model_v0015_manifest
from pring_cycle.official_context import (
    FetchedOfficialContextDocument,
    official_claims_matching_acquisitions,
)
from pring_cycle.retrieval_ledger import RetrievalLedger
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter
from tests.fixtures.delivery_assertions import assert_delivered_points, assert_delivered_rows
from tests.fixtures.model_registration import (
    bind_synthetic_review,
    encode,
    prepared_request,
    save,
    submit,
)

LISTING = "https://www.pbc.gov.cn/diaochatongjisi/116219/index.html"
ARTICLE = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/2026081416320925645/index.html"


def admit_sf_candidate(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str], *, confirmation: bool = False
) -> tuple[str, str]:
    """A candidate whose social financing falls back to the PBC's page; with
    ``confirmation``, one reading the stage narrative's key indicators (model-v0015)."""
    request, _ = prepared_request(paths)
    if confirmation:
        new = model_v0015_manifest()
        request["manifest"].update({field: new[field] for field in MANIFEST_FIELDS})
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    for definition in request["manifest"]["metric_definitions"]:
        if definition["metric_id"] != "CN_SF_TOTAL":
            continue
        definition["source_candidates"] = [LISTING]
        definition["source_codes"] = [
            *definition["source_codes"],
            "tushare:sf_month:official-sampled-v0001",
        ]
        package["definition_bindings"]["CN_SF_TOTAL"] = hashlib.sha256(
            encode(definition)
        ).hexdigest()
        version = definition["definition_version"]
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    return json.loads(capsys.readouterr().out)["model_version_id"], version


@pytest.mark.usefixtures("runtime_clock")
def test_sf_total_delivery_preserves_annual_flow_period_and_month_end_stock(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_sf_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        assert payload["api_name"] == "sf_month"
        assert payload["fields"] == "month,inc_cumval,stk_endval"
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["month", "inc_cumval", "stk_endval"],
                    "items": [["202607", 220000.0, 460.0]],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.social_financing_total(start_month="2026-07", end_month="2026-07"),
        definition_version=version,
    )
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert {
        p.dimensions["measure"]: (p.period_start, p.period_end, p.selected_value) for p in points
    } == {
        "ytd_increment": ("2026-01-01", "2026-07-31", 220000.0),
        "stock_end": ("2026-07-01", "2026-07-31", 4600000.0),
    }
    assert all(c.unit == "hundred_million_cny" for p in points for c in p.claims)
    assert official_claims_matching_acquisitions(
        evidence, {"CN_SF_TOTAL": points}, definition_version=version
    ) == {p.selected_claim_id for p in points}
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(r for r in acquisitions.history() if r.api_name == "sf_month")
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert {row["source_field"]: row["period_kind"] for row in normalized} == {
        "inc_cumval": "year_to_month",
        "stk_endval": "month",
    }


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("delivered", [True, False])
@pytest.mark.parametrize("official_state", ["available", "transport_failed", "no_matching_period"])
def test_sf_total_fallback_preserves_delivered_values_and_component_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    delivered: bool,
    official_state: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_sf_candidate(paths, capsys)
    evidence = EvidenceRepository(paths.database)

    def transport(payload: dict) -> bytes:
        assert payload["api_name"] == "sf_month"
        assert payload["fields"] == "month,inc_cumval,stk_endval"
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["month", "inc_cumval", "stk_endval"],
                    "items": [["202607", 220000.0, 460.0]] if delivered else [],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def acquire():
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.social_financing_total(start_month="2026-07", end_month="2026-07"),
            definition_version=version,
        )

    if delivered:
        acquire()
    else:
        with pytest.raises(ValueError, match="tushare_context_observations_missing"):
            acquire()

    def series():
        return tuple(
            evidence.metric_series(
                "CN_SF_TOTAL",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )

    before = series()
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url == LISTING:
            content = (
                b"<p>No matching release in this fixture</p>"
                if official_state == "no_matching_period"
                else f'<a href="{ARTICLE}">2026年7月金融统计数据报告</a>'.encode()
            )
        elif url == ARTICLE and official_state != "transport_failed":
            content = (
                Path(__file__).parents[1] / "fixtures/official_period_fallback/pbc_money.html"
            ).read_bytes()
        else:
            raise OSError("unrelated fixture unavailable")
        return FetchedOfficialContextDocument(content, "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="sf-total-fallback",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    assert (ARTICLE in requested) == (not delivered and official_state != "no_matching_period")
    points = series()
    expected = (
        {
            "stock_end": ("2026-07-01", "2026-07-31", 4600000.0),
            "ytd_increment": ("2026-01-01", "2026-07-31", 220000.0),
        }
        if delivered
        else {
            "stock_end": ("2026-07-01", "2026-07-31", 4632700.0),
            "stock_yoy": ("2026-07-01", "2026-07-31", 7.4),
            "ytd_increment": ("2026-01-01", "2026-07-31", 222500.0),
        }
        if official_state == "available"
        else {}
    )
    assert {
        p.dimensions["measure"]: (p.period_start, p.period_end, p.selected_value) for p in points
    } == expected
    if delivered:
        assert {p.selected_claim_id for p in points} == {p.selected_claim_id for p in before}
    assert official_claims_matching_acquisitions(
        evidence, {"CN_SF_TOTAL": points}, definition_version=version
    ) == {p.selected_claim_id for p in points}
    provider = "tushare" if delivered else "中国人民银行"
    assert all(c.provider == provider for p in points for c in p.claims)
    # The page fetched for the total states every component too: all of them are stored,
    # not only what the gap asked for (lookback fetch gaps 02).
    components = evidence.metric_series(
        "CN_SF_COMPONENTS",
        mode=AsOfMode.SYSTEM,
        as_of=datetime.now(UTC),
        definition_version=version,
    )
    assert len(components) == (24 if not delivered and official_state == "available" else 0)
    assert {c.provider for p in components for c in p.claims} <= {"中国人民银行"}
    if not delivered and official_state in {"transport_failed", "no_matching_period"}:
        transport_failed = official_state == "transport_failed"
        attempt = evidence.latest_retrieval_attempt(
            "CN_SF_TOTAL", period="2026-07", as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None
        assert attempt.outcome == ("source_failed" if transport_failed else "structure_rejected")
        assert attempt.safe_metadata["error_type"] == (
            "OSError" if transport_failed else "ValueError"
        )
        acquisitions = {
            r.acquisition_id
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.parameters.get("source_url") == (ARTICLE if transport_failed else LISTING)
            and r.parameters.get("period") == "2026-07"
        }
        ledger = RetrievalLedger(paths.database).for_run(run.run_id)
        assert ledger is not None
        physical = [r for r in ledger["requests"] if r["acquisition_id"] in acquisitions]
        assert physical and all(
            r["outcome"] == "failed"
            and r["classification"]
            == ("transient_transport_error" if transport_failed else "semantic_validation_failed")
            for r in physical
        )
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    rows = [r for r in context.macro["credit"]["evidence"] if r["metric_id"] == "CN_SF_TOTAL"]
    if not expected:
        assert len(rows) == 1 and rows[0]["claims"] == [] and rows[0]["value"] is None
        return
    assert len(rows) == len(expected)
    assert_delivered_points(points, provider)
    assert_delivered_rows(rows, provider)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("official_state", ["available", "transport_failed"])
def test_a_confirmation_model_takes_the_official_stock_growth_tushare_does_not_deliver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    official_state: str,
) -> None:
    # TuShare delivers July's stock and flow; the official stock growth, a required member
    # of the stage narrative's social financing (ticket 04), is the PBC's alone: its page
    # is fetched for it, the delivered values kept, or the growth is a named gap.
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_sf_candidate(paths, capsys, confirmation=True)

    def transport(payload: dict) -> bytes:
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["month", "inc_cumval", "stk_endval"],
                    "items": [["202607", 220000.0, 460.0]],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.social_financing_total(start_month="2026-07", end_month="2026-07"),
        definition_version=version,
    )
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url == LISTING:
            content = f'<a href="{ARTICLE}">2026年7月金融统计数据报告</a>'.encode()
        elif url == ARTICLE and official_state == "available":
            content = (
                Path(__file__).parents[1] / "fixtures/official_period_fallback/pbc_money.html"
            ).read_bytes()
        else:
            raise OSError("unrelated fixture unavailable")
        return FetchedOfficialContextDocument(content, "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    runs = RunRepository(paths.database)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="sf-stock-growth",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)

    assert ARTICLE in requested
    july = {
        p.dimensions["measure"]: (p.selected_value, {c.provider for c in p.claims})
        for p in EvidenceRepository(paths.database).metric_series(
            "CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
        if p.period_end == "2026-07-31"
    }
    # What TuShare delivered stands; only the growth it does not deliver is taken.
    assert july["stock_end"] == (4600000.0, {"tushare"})
    assert july["ytd_increment"] == (220000.0, {"tushare"})
    plan = runs.full_retrieval_plan(run.run_id)
    initial = next(
        item
        for item in plan["initial"]["requirements"]
        if item["metric_id"] == "CN_SF_TOTAL" and item.get("period") == "2026-07"
    )
    stock_yoy = 'CN_SF_TOTAL:{"measure": "stock_yoy"}'
    assert stock_yoy in initial["missing_members"]
    if official_state == "available":
        assert july["stock_yoy"] == (7.4, {"中国人民银行"})
    else:
        assert "stock_yoy" not in july


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "invalid_delivery", ["raw_bytes", "cumulative_period", "publication_time", "legacy_fields"]
)
def test_sf_total_rejects_legacy_semantics_and_unproven_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalid_delivery: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_sf_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        fields = payload["fields"].split(",")
        row = {"month": "202607", "inc_month": 10000.0, "inc_cumval": 220000.0, "stk_endval": 460.0}
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields]]}}
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def scalars():
        retrieve = (
            adapter.social_financing
            if invalid_delivery == "legacy_fields"
            else adapter.social_financing_total
        )
        parsed = retrieve(start_month="2026-07", end_month="2026-07")
        if invalid_delivery == "publication_time":
            published = datetime(2026, 8, 14, 8, 32, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in parsed
            )
        if invalid_delivery == "cumulative_period":
            return tuple(
                replace(s, period_kind="month", period_start="2026-07-01")
                if s.source_field == "inc_cumval"
                else s
                for s in parsed
            )
        return parsed

    if invalid_delivery != "raw_bytes":
        reason = (
            "registered_sf_total_publication_evidence_required"
            if invalid_delivery == "publication_time"
            else "registered_official_source_identity_mismatch"
        )
        with pytest.raises(ValueError, match=reason):
            adapter.acquire_scalars(paths, scalars, definition_version=version)
        return
    adapter.acquire_scalars(paths, scalars, definition_version=version)
    evidence = EvidenceRepository(paths.database)
    points = tuple(
        evidence.metric_series(
            "CN_SF_TOTAL", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert (
        len(
            official_claims_matching_acquisitions(
                evidence, {"CN_SF_TOTAL": points}, definition_version=version
            )
        )
        == 2
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(r for r in acquisitions.history() if r.api_name == "sf_month")
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")
    assert not official_claims_matching_acquisitions(
        evidence, {"CN_SF_TOTAL": points}, definition_version=version
    )


@pytest.mark.usefixtures("runtime_clock")
def test_a_page_fetched_for_the_components_leaves_out_the_total_tushare_delivered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The page states the total beside the components it was fetched for; the total TuShare
    delivered is held, so the page's own (another stock) does not contest it (ticket 12)."""
    from pring_cycle.worker import _official_context_retrieval

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_sf_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["month", "inc_cumval", "stk_endval"],
                    "items": [["202607", 220000.0, 460.0]],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)
    adapter.acquire_scalars(
        paths,
        lambda: adapter.social_financing_total(start_month="2026-07", end_month="2026-07"),
        definition_version=version,
    )
    page = (
        Path(__file__).parents[1] / "fixtures/official_period_fallback/pbc_money.html"
    ).read_bytes()
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="sf-components-only",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
        release_event_id="pbc_social_financing:2026-07",
        metric_ids=("CN_SF_COMPONENTS",),
        period="2026-07",
        source_url=ARTICLE,
    )
    assert run.retrieval_scope is not None

    def fetch(url: str) -> FetchedOfficialContextDocument:
        assert url == ARTICLE
        return FetchedOfficialContextDocument(page, "text/html", url, 200)

    monkeypatch.setattr("pring_cycle.official_context._fetch_official_context_document", fetch)
    _official_context_retrieval(
        paths, run.retrieval_scope, datetime.now(UTC), run_id=run.run_id, definition_version=version
    )

    evidence = EvidenceRepository(paths.database)

    def series(metric_id: str) -> dict[tuple[str, ...], tuple[float | None, set[str]]]:
        return {
            (p.period_end, *(p.dimensions[key] for key in sorted(p.dimensions))): (
                p.selected_value,
                {c.provider for c in p.claims},
            )
            for p in evidence.metric_series(
                metric_id, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
            )
        }

    components = series("CN_SF_COMPONENTS")
    assert len(components) == 24
    assert {key[0] for key in components} == {"2026-07-31"}
    assert {provider for _, providers in components.values() for provider in providers} == {
        "中国人民银行"
    }
    assert components[("2026-07-31", "government_bonds", "stock_yoy")][0] is not None
    # The stock growth TuShare does not deliver comes from the page; the rest stays TuShare's.
    assert series("CN_SF_TOTAL") == {
        ("2026-07-31", "stock_end"): (4600000.0, {"tushare"}),
        ("2026-07-31", "ytd_increment"): (220000.0, {"tushare"}),
        ("2026-07-31", "stock_yoy"): (7.4, {"中国人民银行"}),
    }
