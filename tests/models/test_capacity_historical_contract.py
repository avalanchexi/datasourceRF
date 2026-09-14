from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import build_context_projection
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.search_evidence import select_retrieval_input


def historical_runtime(tmp_path: Path, fixture_name: str) -> tuple[RuntimePaths, dict[str, Any]]:
    # Preserve an actual pre-contract synthetic database. Do not obtain this
    # state by removing a marker from a model admitted by the current service.
    fixture = Path(__file__).parents[2] / ".scratch/pring-data-acquisition-repair" / fixture_name
    provenance: dict[str, Any] = json.loads((fixture / "provenance.json").read_text())
    assert (
        hashlib.sha256((fixture / "pring-cycle.sqlite3").read_bytes()).hexdigest()
        == (provenance["database_sha256"])
    )
    for artifact in provenance["verified_artifacts"]:
        digest = artifact["sha256"]
        raw = (fixture / "artifacts/sha256" / digest[:2] / digest).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == digest
    paths = RuntimePaths.discover(tmp_path / "runtime")
    shutil.copytree(fixture, paths.data)
    return paths, provenance


@pytest.mark.parametrize("dependency", ["mapping", "basis", "ordinary_fields"])
@pytest.mark.parametrize("fault", ["missing", "damaged"])
def test_historical_capacity_catalog_preserves_unclassified_dependencies(
    tmp_path: Path, dependency: str, fault: str
) -> None:
    paths, provenance = historical_runtime(tmp_path, "capacity-historical-fixture-178")
    historical = provenance["models"][0]
    model_id = historical["model_id"]
    models = ModelRepository(paths.database)
    manifest = models.manifest(model_id)
    assert "source_mapping_reference_contract" not in manifest
    model_before = models.get(model_id)
    assert model_before.manifest_hash == historical["manifest_sha256"]

    stored_package = manifest["source_certification_packages"][0]
    review_hash = stored_package["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    mappings = []
    ordinary_fields = []
    for reference in review["assessments"]["fields"]["evidence"]:
        digest = reference["artifact_hash"]
        document = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
        if document.get("schema_version") == "source-field-mapping-v0001":
            mappings.append((digest, document))
        else:
            ordinary_fields.append(digest)
    assert len(mappings) == 1 and ordinary_fields
    mapping_hash, mapping = mappings[0]
    damaged_hash = {
        "mapping": mapping_hash,
        "basis": mapping["basis"]["artifact_hash"],
        "ordinary_fields": ordinary_fields[0],
    }[dependency]
    as_of = datetime(2026, 8, 29, 0, 0, 1, tzinfo=UTC)
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=historical["catalog_version"],
        mode=AsOfMode.PUBLIC,
        as_of=as_of,
    )
    assert len(points) == 3
    claims = {point.selected_claim_id for point in points}
    assert None not in claims
    ytd = next(point for point in points if point.dimensions["measure"] == "ytd_rate")
    (event,) = evidence.release_events_for_definition(
        metric_id="CN_CAPACITY_UTILIZATION", definition_version=historical["catalog_version"]
    )
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-28",
        client_request_id="synthetic:historical-capacity-compatibility",
        model_version_id=model_id,
        system_as_of=as_of,
        release_event_id=event.release_event_id,
        metric_ids=("CN_CAPACITY_UTILIZATION",),
        period="2026-Q1",
    )
    before_selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert before_selection.complete and set(before_selection.selected_claim_ids) == claims
    before = build_context_projection(
        evidence, as_of=as_of, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    before_inputs = before.macro["model_input_observation_version_ids"]
    assert isinstance(before_inputs, list) and claims <= set(before_inputs)

    damaged_path = paths.artifacts / damaged_hash[:2] / damaged_hash
    if fault == "missing":
        damaged_path.unlink()
    else:
        damaged_path.write_bytes(b"synthetic damage to an unclassified historical dependency")
    selected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert not selected.complete and ytd.selected_claim_id not in selected.selected_claim_ids
    after = build_context_projection(
        evidence, as_of=as_of, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    after_inputs = after.macro["model_input_observation_version_ids"]
    assert isinstance(after_inputs, list) and ytd.selected_claim_id not in after_inputs
    assert claims <= set(after.observation_version_ids)
    assert models.get(model_id) == model_before
    assert models.manifest(model_id) == manifest


@pytest.mark.parametrize("dependency", ["unselected_mapping", "unselected_basis"])
@pytest.mark.parametrize("fault", ["missing", "damaged"])
def test_historical_capacity_catalog_still_requires_unselected_grant_dependencies(
    tmp_path: Path, dependency: str, fault: str
) -> None:
    paths, provenance = historical_runtime(tmp_path, "capacity-historical-multiple-fixture-181")
    historical = next(
        item for item in provenance["models"] if item["catalog_version"].endswith("-candidate")
    )
    model_id = historical["model_id"]
    models = ModelRepository(paths.database)
    model_before = models.get(model_id)
    manifest = models.manifest(model_id)
    assert model_before.manifest_hash == historical["manifest_sha256"]
    assert "source_mapping_reference_contract" not in manifest
    review_hash = manifest["source_certification_packages"][0]["review_hash"]
    review = json.loads((paths.artifacts / review_hash[:2] / review_hash).read_bytes())
    mappings = {}
    for reference in review["assessments"]["fields"]["evidence"]:
        digest = reference["artifact_hash"]
        document = json.loads((paths.artifacts / digest[:2] / digest).read_bytes())
        if document.get("schema_version") == "source-field-mapping-v0001":
            mappings[digest] = document
    assert len(mappings) == 2
    assert len({mapping["basis"]["artifact_hash"] for mapping in mappings.values()}) == 2
    # The second publication is later than this PUBLIC cutoff. Its grant is
    # deliberately unselected, yet an old catalog still requires that grant's basis.
    as_of = datetime(2026, 4, 16, 23, 59, 59, tzinfo=UTC)
    evidence = EvidenceRepository(paths.database)
    points = evidence.metric_series(
        "CN_CAPACITY_UTILIZATION",
        definition_version=historical["catalog_version"],
        mode=AsOfMode.PUBLIC,
        as_of=as_of,
    )
    assert len(points) == 3
    claims = {point.selected_claim_id for point in points}
    assert None not in claims
    ytd = next(point for point in points if point.dimensions["measure"] == "ytd_rate")
    assert ytd.selected_value == 73.6
    selected_claim = next(claim for claim in ytd.claims if claim.claim_id == ytd.selected_claim_id)
    selected_raw = selected_claim.source_reference.rsplit("#sha256=", 1)[1]
    (unselected,) = [
        (digest, mapping)
        for digest, mapping in mappings.items()
        if mapping["source_document"]["artifact_hash"] != selected_raw
    ]
    (event,) = [
        event
        for event in evidence.release_events_for_definition(
            metric_id="CN_CAPACITY_UTILIZATION", definition_version=historical["catalog_version"]
        )
        if event.public_available_at is not None and event.public_available_at <= as_of
    ]
    run = RunRepository(paths.database).submit(
        command_type="targeted_refresh",
        target_business_date="2026-04-16",
        client_request_id="synthetic:historical-unselected-grant",
        model_version_id=model_id,
        system_as_of=as_of,
        release_event_id=event.release_event_id,
        metric_ids=("CN_CAPACITY_UTILIZATION",),
        period="2026-Q1",
    )
    selected = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert selected.complete and set(selected.selected_claim_ids) == claims
    before = build_context_projection(
        evidence, as_of=as_of, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    before_inputs = before.macro["model_input_observation_version_ids"]
    assert isinstance(before_inputs, list) and claims <= set(before_inputs)
    damaged_hash = (
        unselected[0]
        if dependency == "unselected_mapping"
        else unselected[1]["basis"]["artifact_hash"]
    )
    damaged_path = paths.artifacts / damaged_hash[:2] / damaged_hash
    if fault == "missing":
        damaged_path.unlink()
    else:
        damaged_path.write_bytes(b"synthetic damage to the unselected legacy grant")
    after_selection = select_retrieval_input(paths, run, mode=AsOfMode.PUBLIC)
    assert not after_selection.complete
    assert ytd.selected_claim_id not in after_selection.selected_claim_ids
    after = build_context_projection(
        evidence, as_of=as_of, model_manifest=manifest, as_of_mode=AsOfMode.PUBLIC
    )
    after_inputs = after.macro["model_input_observation_version_ids"]
    assert isinstance(after_inputs, list) and ytd.selected_claim_id not in after_inputs
    assert claims <= set(after.observation_version_ids)
    assert models.get(model_id) == model_before
    assert models.manifest(model_id) == manifest
