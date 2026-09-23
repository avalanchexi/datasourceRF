"""Reviewed money delivery and archived PBC fallback through public repositories."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.full_retrieval import FullRunRetrieval
from pring_cycle.models import ModelRepository
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


def admit_money_candidate(
    paths: RuntimePaths, capsys: pytest.CaptureFixture[str]
) -> tuple[str, str]:
    request, _ = prepared_request(paths)
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    for definition in request["manifest"]["metric_definitions"]:
        if definition["metric_id"] != "CN_M1_M2":
            continue
        definition["source_candidates"] = [LISTING]
        definition["source_codes"] = [
            *definition["source_codes"],
            "tushare:cn_m:official-sampled-v0001",
        ]
        package["definition_bindings"]["CN_M1_M2"] = hashlib.sha256(encode(definition)).hexdigest()
        version = definition["definition_version"]
    bind_synthetic_review(paths, request, package)
    submit(paths, save(paths, request))
    return json.loads(capsys.readouterr().out)["model_version_id"], version


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("delivered", [True, False])
@pytest.mark.parametrize("official_available", [True, False])
def test_money_fallback_keeps_required_members_and_delivery_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    delivered: bool,
    official_available: bool,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    candidate, version = admit_money_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        assert payload["api_name"] == "cn_m"
        assert payload["fields"] == "month,m1,m1_yoy,m2,m2_yoy"
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "fields": ["month", "m1", "m1_yoy", "m2", "m2_yoy"],
                    "items": [["202607", 1_150_000.0, 4.1, 3_550_000.0, 7.6]] if delivered else [],
                },
            }
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def acquire():
        return adapter.acquire_scalars(
            paths,
            lambda: adapter.money(
                start_month="2026-07", end_month="2026-07", include_month_on_month=False
            ),
            definition_version=version,
        )

    if delivered:
        acquire()
    else:
        with pytest.raises(ValueError, match="tushare_context_observations_missing"):
            acquire()
    evidence = EvidenceRepository(paths.database)

    def series():
        return tuple(
            evidence.metric_series(
                "CN_M1_M2",
                mode=AsOfMode.SYSTEM,
                as_of=datetime.now(UTC),
                definition_version=version,
            )
        )

    before = series()
    delivered_values = {
        ("m1", "balance"): 1_150_000.0,
        ("m1", "yoy"): 4.1,
        ("m2", "balance"): 3_550_000.0,
        ("m2", "yoy"): 7.6,
    }
    assert {
        (p.dimensions["aggregate"], p.dimensions["measure"]): p.selected_value for p in before
    } == (delivered_values if delivered else {})
    selected = {p.selected_claim_id for p in before}
    assert (
        official_claims_matching_acquisitions(
            evidence, {"CN_M1_M2": before}, definition_version=version
        )
        == selected
    )
    requested: list[str] = []

    def fetch(url: str) -> FetchedOfficialContextDocument:
        requested.append(url)
        if url == LISTING:
            content = f'<a href="{ARTICLE}">2026年7月金融统计数据报告</a>'.encode()
        elif url == ARTICLE and official_available:
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
        client_request_id="money-fallback",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
    )
    run = runs.advance(submitted.run_id, "refreshing_evidence")
    FullRunRetrieval(paths).retrieve(run)
    assert (ARTICLE in requested) == (not delivered)
    after = series()
    if delivered:
        assert {p.selected_claim_id for p in after} == selected
    expected = (
        delivered_values
        if delivered
        else {
            ("m1", "balance"): 1_154_600.0,
            ("m1", "yoy"): 4.0,
            ("m2", "balance"): 3_555_100.0,
            ("m2", "yoy"): 7.7,
        }
        if official_available
        else {}
    )
    assert {
        (p.dimensions["aggregate"], p.dimensions["measure"]): p.selected_value for p in after
    } == expected
    assert official_claims_matching_acquisitions(
        evidence, {"CN_M1_M2": after}, definition_version=version
    ) == {p.selected_claim_id for p in after}
    if not delivered and not official_available:
        attempt = evidence.latest_retrieval_attempt(
            "CN_M1_M2", period="2026-07", as_of=datetime.now(UTC), definition_version=version
        )
        assert attempt is not None and attempt.outcome == "source_failed"
        assert attempt.safe_metadata["error_type"] == "OSError"
        acquisitions = {
            r.acquisition_id
            for r in AcquisitionRepository(paths.database, paths.artifacts).history()
            if r.parameters.get("source_url") == ARTICLE
        }
        ledger = RetrievalLedger(paths.database).for_run(run.run_id)
        assert ledger is not None
        physical = [r for r in ledger["requests"] if r["acquisition_id"] in acquisitions]
        assert physical and all(
            r["outcome"] == "failed" and r["classification"] == "transient_transport_error"
            for r in physical
        )
    context = build_context_projection(
        evidence,
        as_of=datetime.now(UTC),
        model_manifest=ModelRepository(paths.database).manifest(candidate),
    )
    rows = [r for r in context.macro["credit"]["evidence"] if r["metric_id"] == "CN_M1_M2"]
    if not expected:
        assert len(rows) == 1 and rows[0]["claims"] == []
        assert rows[0]["value"] is None
        return
    assert len(rows) == 4
    provider = "tushare" if delivered else "中国人民银行"
    assert_delivered_points(after, provider)
    assert_delivered_rows(rows, provider)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("invalid_delivery", ["raw_bytes", "publication_time", "legacy_fields"])
def test_money_delivery_rejects_unreviewed_fields_and_unproven_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], invalid_delivery: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    _, version = admit_money_candidate(paths, capsys)

    def transport(payload: dict) -> bytes:
        fields = payload["fields"].split(",")
        values = {
            "month": "202607",
            "m1": 1_150_000,
            "m1_yoy": 4.1,
            "m1_mom": 0.2,
            "m2": 3_550_000,
            "m2_yoy": 7.6,
            "m2_mom": 0.3,
        }
        return json.dumps(
            {"code": 0, "data": {"fields": fields, "items": [[values[f] for f in fields]]}}
        ).encode()

    adapter = TushareContextAdapter("fixture-only", transport=transport)

    def scalars():
        parsed = adapter.money(
            start_month="2026-07",
            end_month="2026-07",
            include_month_on_month=invalid_delivery == "legacy_fields",
        )
        if invalid_delivery == "publication_time":
            published = datetime(2026, 8, 14, 8, 32, tzinfo=UTC)
            return tuple(
                replace(s, release_at=published, public_available_at=published) for s in parsed
            )
        return parsed

    if invalid_delivery in {"publication_time", "legacy_fields"}:
        reason = (
            "registered_money_publication_evidence_required"
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
            "CN_M1_M2", mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
        )
    )
    assert (
        len(
            official_claims_matching_acquisitions(
                evidence, {"CN_M1_M2": points}, definition_version=version
            )
        )
        == 4
    )
    receipt = next(
        r
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
        if r.api_name == "cn_m"
    )
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"{}")
    assert not official_claims_matching_acquisitions(
        evidence, {"CN_M1_M2": points}, definition_version=version
    )
