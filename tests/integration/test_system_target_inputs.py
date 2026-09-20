"""A new immutable time rule lets actual SYSTEM evidence serve its target date."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.ecb_reference import import_ecb_reference_cross
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.official_lpr import ingest_lpr_document
from pring_cycle.runs import RetrievalScope, RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.tushare_context import TushareContextAdapter
from tests.conftest import install_runtime_clock
from tests.integration.test_ecb_reference_acquisition import (
    METRIC,
    SOURCE_URL,
    certified_request,
    zip_csv,
)
from tests.models.test_candidate_admission import bind_synthetic_review, save, submit


@pytest.fixture
def runtime_clock(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    return install_runtime_clock(monkeypatch, request, datetime(2026, 9, 18, 1, tzinfo=UTC))


def system_request(paths: RuntimePaths):
    request = certified_request(paths)
    request["manifest"]["point_in_time_rule_version"] = "dual-cutoff-v0003"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    bind_synthetic_review(paths, request, package)
    return request


@pytest.mark.usefixtures("runtime_clock")
def test_new_model_uses_ecb_only_after_actual_system_availability(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    assert manifest["point_in_time_rule_version"] == "dual-cutoff-v0003"
    version = manifest["metric_catalog_version"]
    before = datetime.now(UTC)
    imported = import_ecb_reference_cross(
        paths,
        zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n"),
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=version,
    )
    after = datetime.now(UTC)
    target = after.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    runs = RunRepository(paths.database)
    scope = RetrievalScope("ecb-reference:2026-09-17", (METRIC,), "2026-09-17", "P2", None)

    def selection(at):
        run = runs.submit(
            command_type="manual_full",
            target_business_date=target,
            client_request_id=at.isoformat(),
            model_version_id=candidate,
            system_as_of=at,
            cutoff_mode="explicit",
        )
        return ModelInputSelector(paths, run).select(scope)

    # Use two independent runs; submitting one active manual target twice preserves its cutoff.
    early = runs.submit(
        command_type="scheduled_full",
        target_business_date=target,
        client_request_id="before-acquisition",
        model_version_id=candidate,
        system_as_of=before,
        cutoff_mode="explicit",
    )
    assert not ModelInputSelector(paths, early).select(scope).complete
    selected = selection(after)
    assert selected.complete and selected.selected_claim_ids == imported.claim_ids
    context = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=after,
        model_manifest=manifest,
        target_business_date=target,
    )
    row = next(r for r in context.macro["international_context"] if r["metric_id"] == METRIC)
    assert row["value"] == pytest.approx(6.707516766832157, rel=0, abs=1e-12)
    public = build_context_projection(
        EvidenceRepository(paths.database),
        as_of=after,
        model_manifest=manifest,
        target_business_date=target,
        as_of_mode=AsOfMode.PUBLIC,
    )
    row = next(r for r in public.macro["international_context"] if r["metric_id"] == METRIC)
    assert row["value"] is None


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("direction", ["old_to_new", "new_to_old"])
def test_time_rule_changes_require_another_admitted_model(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    direction: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    submit(paths, save(paths, certified_request(paths)))
    old_id = json.loads(capsys.readouterr().out)["model_version_id"]
    old = models.manifest(old_id)
    submit(paths, save(paths, system_request(paths)))
    new_id = json.loads(capsys.readouterr().out)["model_version_id"]
    new = models.manifest(new_id)
    assert old_id != new_id
    import_ecb_reference_cross(
        paths,
        zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n"),
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=new["metric_catalog_version"],
    )

    def projection(manifest):
        return build_context_projection(
            EvidenceRepository(paths.database),
            as_of=datetime.now(UTC),
            model_manifest=manifest,
            target_business_date="2026-09-18",
        )

    old_row = next(
        r for r in projection(old).macro["international_context"] if r["metric_id"] == METRIC
    )
    new_row = next(
        r for r in projection(new).macro["international_context"] if r["metric_id"] == METRIC
    )
    assert old_row["value"] is None and new_row["value"] is not None
    forged = dict(old if direction == "old_to_new" else new)
    forged["point_in_time_rule_version"] = (
        "dual-cutoff-v0003" if direction == "old_to_new" else "public-cutoff-v0002"
    )
    with pytest.raises(ValueError, match="model_manifest_binding_mismatch"):
        projection(forged)
    assert models.manifest(old_id) == old and models.manifest(new_id) == new


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("artifact_kind", ["raw", "normalized"])
def test_system_input_rechecks_ecb_proof_after_it_becomes_available(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    artifact_kind: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    imported = import_ecb_reference_cross(
        paths,
        zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n"),
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=manifest["metric_catalog_version"],
    )
    run = RunRepository(paths.database).submit(
        command_type="manual_full",
        target_business_date="2026-09-18",
        client_request_id="proof",
        model_version_id=candidate,
        system_as_of=datetime.now(UTC),
        cutoff_mode="explicit",
    )
    scope = RetrievalScope("ecb-reference:2026-09-17", (METRIC,), "2026-09-17", "P2", None)
    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete and selected.selected_claim_ids == imported.claim_ids
    receipt = AcquisitionRepository(paths.database, paths.artifacts).get(imported.acquisition_id)
    digest = receipt.raw_hash if artifact_kind == "raw" else receipt.normalized_hash
    assert digest is not None
    (paths.artifacts / digest[:2] / digest).write_bytes(b"damaged source proof")
    failed = ModelInputSelector(paths, run).select(scope)
    assert not failed.complete and failed.selected_claim_ids == ()


def test_later_system_revision_keeps_the_earlier_target_and_historical_gap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    runtime_clock,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    version = manifest["metric_catalog_version"]

    def ingest(cny):
        return import_ecb_reference_cross(
            paths,
            zip_csv(f"Date,USD,CNY,\n2026-09-17,1,{cny},\n"),
            source_url=SOURCE_URL,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )

    original = ingest("7.70")
    before_revision = runtime_clock()
    later_clock = install_runtime_clock(monkeypatch, request, datetime(2026, 9, 19, 1, tzinfo=UTC))
    revision = ingest("7.80")
    after_revision = later_clock()
    assert revision.observation_ids == original.observation_ids
    assert revision.claim_ids != original.claim_ids
    runs = RunRepository(paths.database)
    scope = RetrievalScope("ecb-reference:2026-09-17", (METRIC,), "2026-09-17", "P2", None)

    for target, at, expected in (
        ("2026-09-17", after_revision, ()),
        ("2026-09-18", before_revision, original.claim_ids),
        ("2026-09-18", after_revision, original.claim_ids),
        ("2026-09-19", after_revision, revision.claim_ids),
    ):
        run = runs.submit(
            command_type="scheduled_full",
            target_business_date=target,
            client_request_id=f"{target}:{at.isoformat()}",
            model_version_id=candidate,
            system_as_of=at,
            cutoff_mode="explicit",
        )
        selected = ModelInputSelector(paths, run).select(scope)
        assert selected.selected_claim_ids == expected
        assert selected.complete == bool(expected)
        assert not ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope).complete
        context = build_context_projection(
            EvidenceRepository(paths.database),
            as_of=at,
            model_manifest=manifest,
            target_business_date=target,
            visible_evidence_start="2026-09-17",
        )
        row = next(r for r in context.macro["international_context"] if r["metric_id"] == METRIC)
        assert row["selected_claim_id"] == (expected[0] if expected else None)


@pytest.mark.usefixtures("runtime_clock")
def test_dr007_and_shibor_keep_public_gaps_but_use_certified_system_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    responses = {
        "repo_daily": {
            "code": 0,
            "data": {
                "fields": ["ts_code", "trade_date", "repo_maturity", "weight"],
                "items": [["DR007.IB", "20260917", "DR007", 1.3859]],
            },
        },
        "shibor": {
            "code": 0,
            "data": {
                "fields": ["date", "on", "1w", "3m"],
                "items": [["20260917", 1.339, 1.387, 1.43]],
            },
        },
    }
    adapter = TushareContextAdapter(
        "synthetic-token",
        transport=lambda payload: json.dumps(responses[payload["api_name"]]).encode(),
    )
    imported = adapter.acquire_scalars(
        paths,
        lambda: adapter.transmission(start_date=date(2026, 9, 17), end_date=date(2026, 9, 17)),
        definition_version=manifest["metric_catalog_version"],
    )
    assert len(imported.claim_ids) == 4
    metrics = ("CN_DR007", "CN_SHIBOR_ON_1W_3M")
    scope = RetrievalScope("synthetic:interbank", metrics, "2026-09-17", "P1", None)
    runs = RunRepository(paths.database)
    for target, expected in (("2026-09-17", False), ("2026-09-18", True)):
        run = runs.submit(
            command_type="scheduled_full",
            target_business_date=target,
            client_request_id=target,
            model_version_id=candidate,
            system_as_of=datetime.now(UTC),
            cutoff_mode="explicit",
        )
        selected = ModelInputSelector(paths, run).select(scope)
        assert selected.complete is expected
        assert set(selected.selected_claim_ids) == (set(imported.claim_ids) if expected else set())
        assert not ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope).complete
    evidence = EvidenceRepository(paths.database)
    for metric in metrics:
        points = evidence.metric_series(
            metric,
            mode=AsOfMode.SYSTEM,
            as_of=datetime.now(UTC),
            definition_version=manifest["metric_catalog_version"],
        )
        assert points and all(c.public_available_at is None for p in points for c in p.claims)


@pytest.mark.parametrize("date_only", [False, True])
def test_known_public_dates_keep_historical_context_and_actual_system_availability(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    date_only: bool,
) -> None:
    clock = install_runtime_clock(
        monkeypatch,
        request,
        datetime(2026, 8, 20, 4, tzinfo=UTC) if date_only else datetime(2026, 9, 18, 1, tzinfo=UTC),
    )
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, system_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    raw = (Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html").read_bytes()
    if date_only:
        raw = raw.replace(b"2026-08-20 09:00", b"2026-08-20")
    imported = ingest_lpr_document(
        paths,
        raw,
        source_url="https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html",
        fetched_at=clock(),
        expected_period="2026-08",
        definition_version=manifest["metric_catalog_version"],
        clock=clock,
    )
    target = "2026-08-20" if date_only else "2026-08-28"
    run = RunRepository(paths.database).submit(
        command_type="manual_full",
        target_business_date=target,
        client_request_id="known-public",
        model_version_id=candidate,
        system_as_of=clock(),
        cutoff_mode="explicit",
    )
    scope = RetrievalScope(imported.release_event_id, ("CN_LPR_1Y_5Y",), "2026-08", "P1", None)
    selected = ModelInputSelector(paths, run).select(scope)
    assert selected.complete and set(selected.selected_claim_ids) == set(imported.claim_ids)
    public = ModelInputSelector(paths, run, mode=AsOfMode.PUBLIC).select(scope)
    assert public.complete is (not date_only)
