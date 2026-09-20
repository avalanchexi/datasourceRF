"""The ECB cross is auditable to both same-day reference rates in one original."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.ecb_reference import import_ecb_reference_cross
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.models.test_candidate_admission import bind_synthetic_review, encode, save, submit
from tests.models.test_ecb_identity_migration import ecb_request

METRIC = "CN_USDCNY_ECB_REFERENCE_CROSS"
SOURCE_URL = (
    "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip?b59ff8e198cf5d409c4b4adff1f9421a"
)
ZIP_SHA = "56a389450a063c0637462db6e33575b45048e181a8071adc9cef2438c97c9e51"
CSV_SHA = "9ee21621a088d3ad15247846e98d27bf4ac19c863e165f6817eff0e6e87770ae"


def zip_csv(content: str, member: str = "eurofxref-hist.csv") -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(member, content)
    return buffer.getvalue()


def certified_request(paths: RuntimePaths):
    """Synthetic certification only exercises software admission, never real-source approval."""
    request = ecb_request(paths)
    definition = next(
        d for d in request["manifest"]["metric_definitions"] if d["metric_id"] == METRIC
    )
    definition["certification_status"] = "certified"
    digest = request["package_hashes"][0]
    package = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
    package["definition_bindings"][METRIC] = hashlib.sha256(encode(definition)).hexdigest()
    bind_synthetic_review(paths, request, package)
    return request


@pytest.mark.usefixtures("runtime_clock")
def test_imported_ecb_cross_keeps_both_legs_formula_original_and_actual_system_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = (Path(__file__).parents[1] / "fixtures/ecb_reference/eurofxref-hist.zip").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ZIP_SHA
    before = datetime.now(UTC)
    imported = import_ecb_reference_cross(
        paths,
        raw,
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=version,
    )
    after = datetime.now(UTC)
    evidence = EvidenceRepository(paths.database)
    assert not evidence.metric_series(
        METRIC, mode=AsOfMode.SYSTEM, as_of=before, definition_version=version
    )
    (point,) = evidence.metric_series(
        METRIC, mode=AsOfMode.SYSTEM, as_of=after, definition_version=version
    )
    assert point.selected_value == pytest.approx(6.707516766832157, abs=1e-12)
    assert point.period_start == point.period_end == "2026-09-17"
    (claim,) = point.claims
    assert claim.provider == "European Central Bank" and claim.unit == "cny_per_usd"
    assert claim.certification_status == "awaiting_source_certification"
    assert claim.public_available_at is None and claim.release_at is None
    assert before <= claim.fetched_at <= claim.available_at <= after
    assert not evidence.metric_series(
        METRIC, mode=AsOfMode.PUBLIC, as_of=after, definition_version=version
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.get(imported.acquisition_id)
    assert receipt.api_name == "document_import" and receipt.raw_hash == ZIP_SHA
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["source_url"] == SOURCE_URL
    assert normalized["csv_sha256"] == CSV_SHA
    assert normalized["formula_version"] == "ecb-eur-reference-cny-usd-cross-v0001"
    assert normalized["base_currency"] == "EUR"
    assert normalized["decimal_precision"] == 34
    (row,) = normalized["rows"]
    assert row["date"] == "2026-09-17"
    assert row["cny_per_eur"] == "7.7009" and row["usd_per_eur"] == "1.1481"
    assert row["value"] == point.selected_value
    trace = evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=after)
    assert {r.acquisition_id for r in trace.acquisitions} == {receipt.acquisition_id}


@pytest.mark.usefixtures("runtime_clock")
def test_ecb_repeat_keeps_first_availability_and_changed_legs_create_a_vintage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = (Path(__file__).parents[1] / "fixtures/ecb_reference/eurofxref-hist.zip").read_bytes()

    def ingest(content):
        return import_ecb_reference_cross(
            paths,
            content,
            source_url=SOURCE_URL,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )

    original = ingest(raw)
    before = datetime.now(UTC)
    evidence = EvidenceRepository(paths.database)
    trace = evidence.trace(original.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=before)
    repeated = ingest(raw)
    assert repeated.claim_ids == original.claim_ids
    assert repeated.acquisition_id != original.acquisition_id
    repeated_trace = evidence.trace(
        original.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC)
    )
    assert repeated_trace.claims == trace.claims
    assert repeated_trace.acquisitions == trace.acquisitions

    with ZipFile(io.BytesIO(raw)) as archive:
        csv_bytes = archive.read("eurofxref-hist.csv")
    lines = csv_bytes.decode().splitlines(keepends=True)
    columns = lines[0].strip().split(",")
    cells = lines[1].strip().split(",")
    assert cells[0] == "2026-09-17"
    # Both reference legs double, so the output stays equal but its inputs have changed.
    cells[columns.index("CNY")] = "15.4018"
    cells[columns.index("USD")] = "2.2962"
    lines[1] = ",".join(cells) + "\n"
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("eurofxref-hist.csv", "".join(lines))
    revised = ingest(buffer.getvalue())
    assert revised.claim_ids != original.claim_ids
    assert revised.observation_ids == original.observation_ids
    (point,) = evidence.metric_series(
        METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    assert point.selected_value == trace.selected_value
    assert point.claims[0].supersedes_claim_id == original.claim_ids[0]
    assert evidence.trace(original.observation_ids[0], mode=AsOfMode.SYSTEM, as_of=before) == trace
    assert len(evidence.source_claim_vintages(METRIC, definition_version=version)) == 2


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("usd", ["N/A", "0"])
def test_ecb_missing_or_invalid_leg_retains_original_and_an_explained_gap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    usd: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv(f"Date,USD,CNY,\n2026-09-17,{usd},7.7009,\n")

    def ingest():
        return import_ecb_reference_cross(
            paths,
            raw,
            source_url=SOURCE_URL,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )

    if usd == "0":
        with pytest.raises(ValueError, match="ecb_reference_rate_invalid"):
            ingest()
    else:
        result = ingest()
        assert result.observation_count == 0 and result.claim_ids == ()
    evidence = EvidenceRepository(paths.database)
    assert not evidence.metric_series(
        METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    assert receipt.state == ("failed" if usd == "0" else "validated")
    attempt = evidence.latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None
    assert attempt.outcome == ("validation_failed" if usd == "0" else "missing_values")
    if usd == "N/A":
        assert attempt.safe_metadata["condition"] == "reference_legs_missing"
        normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
        assert normalized["rows"] == []
        assert normalized["missing"] == [
            {
                "date": "2026-09-17",
                "cny_per_eur": "7.7009",
                "usd_per_eur": "N/A",
                "reason": "reference_leg_missing",
            }
        ]


@pytest.mark.usefixtures("runtime_clock")
def test_ecb_http_refresh_records_transport_and_keeps_imported_first_availability(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.ecb_reference import (
        ECB_HISTORY_URL,
        FetchedEcbReferenceZip,
        refresh_ecb_reference_cross,
    )

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")
    original = import_ecb_reference_cross(
        paths,
        raw,
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=version,
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    seen = []

    def fetch(endpoint):
        assert endpoint == ECB_HISTORY_URL
        assert len(seen) == 1 and acquisitions.get(seen[0]).state == "started"
        return FetchedEcbReferenceZip(raw, endpoint, 200, "application/zip")

    refreshed = refresh_ecb_reference_cross(
        paths,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=version,
        fetcher=fetch,
        on_acquisition_started=seen.append,
    )
    assert refreshed.claim_ids == original.claim_ids
    assert refreshed.acquisition_id != original.acquisition_id
    assert seen == [refreshed.acquisition_id]
    receipt = acquisitions.get(refreshed.acquisition_id)
    assert receipt.api_name == "official_http_get" and receipt.state == "validated"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    normalized = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    assert normalized["http_response"] == {
        "response_final_url": ECB_HISTORY_URL,
        "response_http_status": "200",
        "response_media_type": "application/zip",
        "response_complete": "true",
        "response_content_length": "",
    }
    attempt = EvidenceRepository(paths.database).latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.channel == "ecb_reference_http"
    assert attempt.safe_metadata["acquisition_ids"] == refreshed.acquisition_id


@pytest.mark.usefixtures("runtime_clock")
def test_ecb_projection_rechecks_the_original_before_using_a_certified_cross(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from pring_cycle.ecb_reference import FetchedEcbReferenceZip, refresh_ecb_reference_cross

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, certified_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    manifest = ModelRepository(paths.database).manifest(candidate)
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")
    result = refresh_ecb_reference_cross(
        paths,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=manifest["metric_catalog_version"],
        fetcher=lambda url: FetchedEcbReferenceZip(raw, url, 200, "application/zip"),
    )
    evidence = EvidenceRepository(paths.database)

    def row():
        context = build_context_projection(
            evidence, as_of=datetime.now(UTC), model_manifest=manifest
        )
        return next(r for r in context.macro["international_context"] if r["metric_id"] == METRIC)

    assert row()["value"] == pytest.approx(6.707516766832157, rel=0, abs=1e-12)
    receipt = AcquisitionRepository(paths.database, paths.artifacts).get(result.acquisition_id)
    assert receipt.raw_hash is not None
    (paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash).write_bytes(b"damaged original")
    rejected = row()
    # Existing projections retain the recorded value for audit and mark it unusable.
    assert rejected["status"] == "source_failed"


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("command", ["ecb-reference-import", "ecb-reference-refresh"])
def test_ecb_cli_delivers_independent_candidates_with_an_explicit_catalog(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    from pring_cycle.cli import main

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")

    class Response(io.BytesIO):
        status = 200
        headers = {"Content-Type": "application/zip", "Content-Length": str(len(raw))}

        def geturl(self):
            return "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

    monkeypatch.setattr(
        "pring_cycle.ecb_reference.open_no_redirects", lambda *a, **k: Response(raw)
    )
    extra = []
    if command == "ecb-reference-import":
        document = tmp_path / "original.zip"
        document.write_bytes(raw)
        extra = ["--input", str(document), "--url", SOURCE_URL]
    main(
        [
            command,
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--start",
            "2026-09-17",
            "--end",
            "2026-09-17",
            "--definition-version",
            version,
            "--json",
            *extra,
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert result["observation_count"] == 1
    receipt = AcquisitionRepository(paths.database, paths.artifacts).get(result["acquisition_id"])
    assert receipt.api_name == ("document_import" if extra else "official_http_get")
    assert receipt.state == "validated"


@pytest.mark.usefixtures("runtime_clock")
def test_corrupted_ecb_zip_retains_the_failed_body_and_validation_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    damaged = bytearray(zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n"))
    # The first DEFLATE block has the reserved BTYPE=3, after the ZIP local header/name.
    offset = (
        30 + int.from_bytes(damaged[26:28], "little") + int.from_bytes(damaged[28:30], "little")
    )
    damaged[offset] = 6
    raw = bytes(damaged)
    with pytest.raises(ValueError, match="ecb_reference_zip_invalid"):
        import_ecb_reference_cross(
            paths,
            raw,
            source_url=SOURCE_URL,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "validation_failed"
    assert not evidence.source_claim_vintages(METRIC, definition_version=version)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("defect", ["formula", "leg", "decimal", "claim_value", "public_time"])
def test_ecb_claim_rejects_forged_formula_legs_result_or_publication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")
    original = import_ecb_reference_cross(
        paths,
        raw,
        source_url=SOURCE_URL,
        start_date=date(2026, 9, 17),
        end_date=date(2026, 9, 17),
        definition_version=version,
    )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = acquisitions.get(original.acquisition_id)
    document = json.loads(acquisitions.read_content(receipt.acquisition_id, "normalized"))
    if defect == "formula":
        document["expression"] = "USD_per_EUR / CNY_per_EUR"
    elif defect == "leg":
        document["rows"][0]["cny_per_eur"] = "7.01"
    elif defect == "decimal":
        document["rows"][0]["decimal_value"] = "7.01"
    forged = acquisitions.capture(
        provider=receipt.provider,
        api_name=receipt.api_name,
        parameters=receipt.parameters,
        fields=receipt.fields,
        parser_version=receipt.parser_version,
        fetch=lambda: raw,
        parse=lambda _: document,
        normalize=lambda value: value,
    ).receipt
    evidence = EvidenceRepository(paths.database)
    before = evidence.source_claim_vintages(METRIC, definition_version=version)
    (point,) = evidence.metric_series(
        METRIC, mode=AsOfMode.SYSTEM, as_of=datetime.now(UTC), definition_version=version
    )
    (claim,) = point.claims
    assert forged.received_at is not None and forged.validated_at is not None
    with pytest.raises(ValueError, match="registered_ecb_"):
        evidence.append_source_claim(
            SourceClaimInput(
                metric_id=METRIC,
                definition_version=version,
                period_kind="business_day",
                period_start="2026-09-17",
                period_end="2026-09-17",
                dimensions={},
                value=7.01 if defect == "claim_value" else claim.value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="cny_per_usd",
                provider=claim.provider,
                source_reference=claim.source_reference,
                release_event_id=f"synthetic:forged:{forged.acquisition_id}",
                release_at=forged.validated_at if defect == "public_time" else None,
                public_available_at=forged.validated_at if defect == "public_time" else None,
                fetched_at=forged.received_at,
                available_at=forged.validated_at,
                certification_status="awaiting_source_certification",
                quality_status="validated",
                acquisition_id=forged.acquisition_id,
            )
        )
    assert evidence.source_claim_vintages(METRIC, definition_version=version) == before


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize("defect", ["status", "url", "mime", "transport"])
def test_ecb_http_failure_is_audited_without_creating_a_claim(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    from pring_cycle.ecb_reference import FetchedEcbReferenceZip, refresh_ecb_reference_cross

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")

    def fetch(url):
        if defect == "transport":
            raise OSError("synthetic unavailable transport")
        return FetchedEcbReferenceZip(
            raw,
            "https://untrusted.example/changed.zip" if defect == "url" else url,
            403 if defect == "status" else 200,
            "text/html" if defect == "mime" else "application/zip",
        )

    with pytest.raises((OSError, ValueError)):
        refresh_ecb_reference_cross(
            paths,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
            fetcher=fetch,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    if defect == "transport":
        assert receipt.raw_hash is None
    else:
        assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == (
        "source_failed" if defect in {"transport", "status"} else "validation_failed"
    )
    assert not evidence.source_claim_vintages(METRIC, definition_version=version)


@pytest.mark.usefixtures("runtime_clock")
def test_ecb_truncated_http_response_retains_partial_bytes_and_failure_classification(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from http.client import IncompleteRead

    from pring_cycle.ecb_reference import refresh_ecb_reference_cross

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    partial = b"PK\x03\x04truncated archive"

    class Response(io.BytesIO):
        status = 200
        headers = {"Content-Type": "application/zip"}

        def geturl(self):
            return "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

        def read(self, size=-1):
            raise IncompleteRead(partial, 1024)

    monkeypatch.setattr("pring_cycle.ecb_reference.open_no_redirects", lambda *a, **k: Response())
    with pytest.raises(OSError, match="ecb_reference_response_incomplete"):
        refresh_ecb_reference_cross(
            paths,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == partial
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "source_failed"
    assert attempt.safe_metadata["response_http_status"] == "200"
    assert attempt.safe_metadata["response_complete"] == "false"
    assert not evidence.source_claim_vintages(METRIC, definition_version=version)


@pytest.mark.usefixtures("runtime_clock")
def test_ecb_short_content_length_response_is_not_adopted_even_if_the_zip_parses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pring_cycle.ecb_reference import refresh_ecb_reference_cross

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    raw = zip_csv("Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n")

    class Response(io.BytesIO):
        status = 200
        headers = {"Content-Type": "application/zip", "Content-Length": str(len(raw) + 1)}

        def geturl(self):
            return "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

    monkeypatch.setattr(
        "pring_cycle.ecb_reference.open_no_redirects", lambda *a, **k: Response(raw)
    )
    with pytest.raises(OSError, match="ecb_reference_response_incomplete"):
        refresh_ecb_reference_cross(
            paths,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    (receipt,) = acquisitions.history()
    assert receipt.state == "failed"
    assert acquisitions.read_content(receipt.acquisition_id, "raw") == raw
    evidence = EvidenceRepository(paths.database)
    attempt = evidence.latest_retrieval_attempt(
        METRIC, period="2026-09-17", as_of=datetime.now(UTC), definition_version=version
    )
    assert attempt is not None and attempt.outcome == "source_failed"
    assert attempt.safe_metadata["response_content_length"] == str(len(raw) + 1)
    assert attempt.safe_metadata["response_complete"] == "false"
    assert not evidence.source_claim_vintages(METRIC, definition_version=version)


@pytest.mark.usefixtures("runtime_clock")
@pytest.mark.parametrize(
    "document",
    [
        "Date,USD,CNH,\n2026-09-17,1.1481,7.7009,\n",
        "Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n2026-09-17,1.14,7.7,\n",
        "Date,USD,CNY,\n2026-09-17,1.1481,7.7009,\n2026-09-16,NaN,7.7,\n",
        "Date,USD,CNY,\n20260917,1.1481,7.7009,\n",
    ],
)
def test_ecb_rejects_wrong_currency_duplicate_dates_and_invalid_document_rows(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    document: str,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submit(paths, save(paths, ecb_request(paths)))
    candidate = json.loads(capsys.readouterr().out)["model_version_id"]
    version = ModelRepository(paths.database).manifest(candidate)["metric_catalog_version"]
    with pytest.raises(ValueError, match="ecb_reference_"):
        import_ecb_reference_cross(
            paths,
            zip_csv(document),
            source_url=SOURCE_URL,
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
            definition_version=version,
        )
    assert not EvidenceRepository(paths.database).source_claim_vintages(
        METRIC, definition_version=version
    )
