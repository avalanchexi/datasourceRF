"""Replay context outputs store each visible source point once and reference it from every day."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_replay_scope import ContextReplayScope
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.model_evaluation import _context_source_snapshot, replay_models
from pring_cycle.model_outputs import (
    CONTEXT_OUTPUT_SCHEMA_V0001,
    compact_context_output,
    context_day_source_inputs,
    expand_context_output,
    model_output_hash,
    model_output_json,
    validate_context_output,
)
from tests.models.test_candidate_replay import append_lpr, lpr_replay_case


def three_day_replay(tmp_path: Path) -> tuple[Any, dict[str, Any]]:
    _paths, models, args, _snapshots = three_day_replay_with_snapshots(tmp_path)
    return models, args


def three_day_replay_with_snapshots(
    tmp_path: Path,
) -> tuple[Any, Any, dict[str, Any], dict[tuple[str, str], Any]]:
    """The replay arguments and each day's snapshot read directly from the evidence store."""
    paths, models, _args = lpr_replay_case(tmp_path)
    public = datetime(2026, 1, 27, 9, tzinfo=UTC)
    append_lpr(EvidenceRepository(paths.database), "1y", 2.9, public, public + timedelta(days=2))
    evaluated = replay_models(
        paths.database,
        "context-lpr-fixture",
        "model-v0001",
        requested_start="2026-01-26",
        requested_end="2026-01-28",
    )
    args = asdict(evaluated)
    args["requested_start"] = args.pop("evaluated_range_start")
    args["requested_end"] = args.pop("evaluated_range_end")
    scope = ContextReplayScope.from_manifests(
        models.manifest("context-lpr-fixture"), models.manifest("model-v0001")
    )
    document = args["context_output_document"]
    evidence = EvidenceRepository(paths.database)
    snapshots = {
        (row["business_date"], side): json.loads(
            model_output_json(
                _context_source_snapshot(
                    evidence,
                    getattr(scope, side),
                    set(document["source_metrics"]),
                    datetime.fromisoformat(row["cutoff"]),
                )
            )
        )
        for row in document["days"]
        for side in ("candidate", "comparison")
    }
    return paths, models, args, snapshots


def test_replay_stores_each_source_point_once_and_every_day_resolves_its_snapshot(
    tmp_path: Path,
) -> None:
    _paths, models, args, snapshots = three_day_replay_with_snapshots(tmp_path)
    document = args["context_output_document"]
    # Every day resolves exactly the snapshot visible at its own cutoff.
    for row in document["days"]:
        for side in ("candidate", "comparison"):
            assert (
                context_day_source_inputs(document, row, side)
                == (snapshots[(row["business_date"], side)])
            )
    assert document["schema_version"] == "context-replay-output-v0002"
    points, hashes = document["source_points"], document["source_point_hashes"]
    assert hashes == [model_output_hash(point) for point in points]
    assert len(set(hashes)) == len(hashes)
    references = [
        index
        for row in document["days"]
        for side in ("candidate", "comparison")
        for indexes in row[side]["source_inputs"].values()
        for index in indexes
    ]
    # The unchanged 5y point and the first 1y vintage repeat across days but are stored once.
    assert len(points) < len(references)
    assert set(references) == set(range(len(points)))

    replay = models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)
    saved = models.replay_details(replay.replay_id)["context_output_document"]
    assert saved == document
    one_year = [
        (
            row["business_date"],
            next(
                point["selected_value"]
                for point in context_day_source_inputs(saved, row, "candidate")["CN_LPR_1Y_5Y"]
                if point["dimensions"]["tenor"] == "1y"
            ),
        )
        for row in saved["days"]
    ]
    assert one_year == [("2026-01-26", 3.0), ("2026-01-27", 2.9), ("2026-01-28", 2.9)]
    # Expanding and compacting again is lossless.
    assert compact_context_output(expand_context_output(saved)) == saved


@pytest.mark.parametrize(
    "damage",
    [
        "changed_point",
        "orphan_point",
        "dangling_reference",
        "duplicate_point",
        "boolean_index",
        "missing_table",
        "length_mismatch",
        "unhashable_hash",
    ],
)
def test_replay_rejects_damaged_source_point_references(tmp_path: Path, damage: str) -> None:
    models, args = three_day_replay(tmp_path)
    document = args["context_output_document"]
    points, hashes = document["source_points"], document["source_point_hashes"]
    first_refs = document["days"][0]["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"]
    if damage == "changed_point":
        points[first_refs[0]]["selected_value"] = 99.0
    elif damage == "orphan_point":
        points.append({"synthetic": "unreferenced"})
        hashes.append(model_output_hash(points[-1]))
    elif damage == "dangling_reference":
        first_refs.append(len(points))
    elif damage == "duplicate_point":
        points.append(points[first_refs[0]])
        hashes.append(hashes[first_refs[0]])
        document["days"][-1]["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"][0] = len(points) - 1
    elif damage == "boolean_index":
        # JSON true equals index 1 in Python; a reference must be a real integer.
        first_refs[0] = True
    elif damage == "missing_table":
        del document["source_points"]
    elif damage == "length_mismatch":
        hashes.pop()
    elif damage == "unhashable_hash":
        hashes[0] = [hashes[0]]
    args["context_output_hash"] = hashlib.sha256(model_output_json(document).encode()).hexdigest()
    with pytest.raises(ValueError, match="context_output_references_invalid"):
        models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)
    with pytest.raises(LookupError, match="model_replay_not_found"):
        models.replay_details(1)


def test_resolved_snapshot_damage_is_still_rejected_by_the_input_checks(tmp_path: Path) -> None:
    models, args = three_day_replay(tmp_path)
    inline = expand_context_output(args["context_output_document"])
    del inline["days"][0]["candidate"]["source_inputs"]["CN_LPR_1Y_5Y"][0]["selected_claim_id"]
    document = compact_context_output(inline)
    args["context_output_document"] = document
    args["context_output_hash"] = hashlib.sha256(model_output_json(document).encode()).hexdigest()
    with pytest.raises(ValueError, match="context_output_inputs_incomplete"):
        models.record_replay("context-lpr-fixture", compared_with="model-v0001", **args)


def test_inline_v0001_is_read_and_matched_but_never_written_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _paths, models, args, snapshots = three_day_replay_with_snapshots(tmp_path)
    current = args["context_output_document"]
    # The inline form an earlier version stored: each day carries its own direct snapshot.
    legacy = json.loads(model_output_json(current))
    del legacy["source_points"], legacy["source_point_hashes"]
    legacy["schema_version"] = CONTEXT_OUTPUT_SCHEMA_V0001
    for row in legacy["days"]:
        for side in ("candidate", "comparison"):
            row[side]["source_inputs"] = snapshots[(row["business_date"], side)]
    legacy_args = {
        **args,
        "context_output_document": legacy,
        "context_output_hash": model_output_hash(legacy),
    }
    with pytest.raises(ValueError, match="context_output_schema_invalid"):
        models.record_replay("context-lpr-fixture", compared_with="model-v0001", **legacy_args)

    def earlier_version_validation(document: object, **kwargs: Any) -> dict[str, Any]:
        return validate_context_output(document, **{**kwargs, "accept_inline_v0001": True})

    with monkeypatch.context() as earlier:
        earlier.setattr("pring_cycle.models.validate_context_output", earlier_version_validation)
        replay = models.record_replay(
            "context-lpr-fixture", compared_with="model-v0001", **legacy_args
        )
    saved = models.replay_details(replay.replay_id)
    assert saved["context_output_document"] == legacy
    assert saved["replay"]["context_output_hash"] == model_output_hash(legacy)
    row = legacy["days"][0]
    assert context_day_source_inputs(legacy, row, "candidate") == row["candidate"]["source_inputs"]
    # Its v0002 form is exactly what the current version records for the same evidence.
    assert compact_context_output(legacy) == current
    assert models.replay_matches_current_evidence(replay.replay_id)
