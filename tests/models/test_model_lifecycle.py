from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.model_evaluation import context_replay_gaps, evaluate_context_replay
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    analytical_model_v0002_manifest,
    certified_model_v0001_manifest,
)


def test_model_v0001_requires_machine_acceptance_and_explicit_approval(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    candidate = models.create_candidate(certified_model_v0001_manifest())

    with pytest.raises(ValueError, match="model_acceptance_required"):
        models.activate(candidate.model_version_id, explicitly_approved=True)

    acceptance = models.record_acceptance(
        candidate.model_version_id,
        CALIBRATION_BASELINE,
    )
    assert acceptance.passed is True
    assert acceptance.asset_direction_changes == 21
    assert acceptance.formal_stage_changes == 11
    assert acceptance.fast_reversals_20d == 0
    assert acceptance.median_confirmation_delay_days == 23

    with pytest.raises(ValueError, match="explicit_model_approval_required"):
        models.activate(candidate.model_version_id, explicitly_approved=False)

    active = models.activate(candidate.model_version_id, explicitly_approved=True)
    assert active.status == "active"
    assert models.active().model_version_id == "model-v0001"


def test_manifest_is_immutable_and_same_input_has_same_hash(tmp_path: Path) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    first = models.create_candidate(certified_model_v0001_manifest())
    second = models.create_candidate(certified_model_v0001_manifest())

    assert first.manifest_hash == second.manifest_hash
    assert first.model_version_id == second.model_version_id

    changed = certified_model_v0001_manifest()
    changed["trend_rules"]["persistence_days"] = 7  # type: ignore[index]
    with pytest.raises(ValueError, match="model_version_is_immutable"):
        models.create_candidate(changed)


def test_v1_manifest_hash_remains_upgrade_compatible_and_v2_is_a_new_candidate(
    tmp_path: Path,
) -> None:
    models = ModelRepository.create(tmp_path / "models.sqlite3")

    v1 = models.create_candidate(certified_model_v0001_manifest())
    v2 = models.create_candidate(analytical_model_v0002_manifest())

    assert v1.manifest_hash == (
        "87db11acfb184571b661b40e10b862927978e6e2e9954b22b5fe99882363e936"
    )
    assert v2.model_version_id == "model-v0002"
    assert v2.status == "candidate"
    assert v2.manifest_hash != v1.manifest_hash
    assert analytical_model_v0002_manifest()["metric_catalog_version"] == (
        "metric-catalog-v0002"
    )


def test_context_changes_cannot_pass_machine_replay_before_source_certification() -> None:
    v1 = certified_model_v0001_manifest()
    v2 = analytical_model_v0002_manifest()

    gaps = context_replay_gaps(v2, v1)

    assert len(gaps) == 1
    assert gaps[0].startswith("candidate_context_sources_uncertified:")
    assert "CN_OMO_7D_AMOUNT" in gaps[0]
    assert "CN_GDP" in gaps[0]
    assert "CN_EQ_CSI300" not in gaps[0]
    assert "CN_CREDIT_IMPULSE" not in gaps[0]
    assert "CN_DR007_POLICY_SPREAD" not in gaps[0]
    assert context_replay_gaps(v1, v1) == ()


def test_certification_labels_cannot_replace_public_context_replay_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    EvidenceRepository.create(database)
    v1 = certified_model_v0001_manifest()
    v2 = analytical_model_v0002_manifest()
    v2["metric_definitions"] = [
        {**definition, "certification_status": "certified"}
        for definition in v2["metric_definitions"]
    ]

    replay = evaluate_context_replay(
        database,
        v2,
        v1,
        requested_start="2026-01-01",
        requested_end="2026-08-30",
    )

    assert any(
        gap.startswith("candidate_context_evidence_missing:")
        for gap in replay.gaps
    )
    assert any(
        gap.startswith("candidate_context_formula_output_missing:")
        for gap in replay.gaps
    )
    assert replay.evaluated_cutoffs == 0
    assert replay.context_output_differences == 0


def test_context_replay_rejects_a_single_late_claim_for_a_long_certified_range(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    repository = EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {**definition, "source_candidates": ["candidate-lpr-source"]}
            if definition["metric_id"] == "CN_LPR_1Y_5Y"
            else definition
        )
        for definition in candidate["metric_definitions"]
    ]
    _append_lpr_claim(
        repository,
        provider="中国货币网",
        value=3.0,
        public_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2018-06-01",
        requested_end="2026-08-30",
    )

    assert "candidate_context_coverage_start_missing:CN_LPR_1Y_5Y" in replay.gaps
    assert replay.evaluated_cutoffs == 0


def test_formula_inputs_are_replayed_when_definition_changes_but_formula_does_not(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {
                **definition,
                "source_candidates": ["candidate-inventory-source"],
                "certification_status": "certified",
            }
            if definition["metric_id"] == "CN_FINISHED_GOODS_INVENTORY"
            else (
                {**definition, "certification_status": "certified"}
                if definition["metric_id"] == "CN_PPI"
                else definition
            )
        )
        for definition in candidate["metric_definitions"]
    ]

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-01-01",
        requested_end="2026-08-30",
    )

    assert any(
        gap.startswith("candidate_context_evidence_missing:")
        for gap in replay.gaps
    )
    assert (
        "candidate_context_formula_output_missing:real_inventory_approximation"
        in replay.gaps
    )


def test_context_replay_rejects_conflicted_canonical_public_selection(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    repository = EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {**definition, "source_candidates": ["candidate-lpr-source"]}
            if definition["metric_id"] == "CN_LPR_1Y_5Y"
            else definition
        )
        for definition in candidate["metric_definitions"]
    ]
    public_at = datetime(2026, 8, 20, 1, tzinfo=UTC)
    _append_lpr_claim(repository, provider="中国货币网", value=3.0, public_at=public_at)
    _append_lpr_claim(
        repository,
        provider="conflicting-certified-source",
        value=3.2,
        public_at=public_at,
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-20",
        requested_end="2026-08-20",
    )

    assert "candidate_context_selection_conflicted:CN_LPR_1Y_5Y" in replay.gaps
    assert replay.evaluated_cutoffs >= 1


def test_context_replay_rejects_an_incomplete_multidimensional_metric(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    repository = EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {**definition, "source_candidates": ["candidate-lpr-source"]}
            if definition["metric_id"] == "CN_LPR_1Y_5Y"
            else definition
        )
        for definition in candidate["metric_definitions"]
    ]
    _append_lpr_claim(
        repository,
        provider="中国货币网",
        value=3.0,
        public_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-20",
        requested_end="2026-08-20",
    )

    assert "candidate_context_selection_members_missing:CN_LPR_1Y_5Y" in replay.gaps


def test_context_replay_does_not_combine_dimension_members_across_periods(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    repository = EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {**definition, "source_candidates": ["candidate-lpr-source"]}
            if definition["metric_id"] == "CN_LPR_1Y_5Y"
            else definition
        )
        for definition in candidate["metric_definitions"]
    ]
    july_public_at = datetime(2026, 7, 20, 1, tzinfo=UTC)
    for tenor, value in (("1y", 3.0), ("5y_plus", 3.5)):
        _append_lpr_claim(
            repository,
            provider="中国货币网",
            value=value,
            public_at=july_public_at,
            tenor=tenor,
            period_start="2026-07-01",
            period_end="2026-07-31",
        )
    _append_lpr_claim(
        repository,
        provider="中国货币网",
        value=3.0,
        public_at=datetime(2026, 8, 20, 1, tzinfo=UTC),
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-20",
        requested_end="2026-08-20",
    )

    assert "candidate_context_selection_members_missing:CN_LPR_1Y_5Y" in replay.gaps


def _append_lpr_claim(
    repository: EvidenceRepository,
    *,
    provider: str,
    value: float,
    public_at: datetime,
    tenor: str = "1y",
    period_start: str = "2026-08-01",
    period_end: str = "2026-08-31",
) -> None:
    repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_LPR_1Y_5Y",
            definition_version="metric-catalog-v0001",
            period_kind="month",
            period_start=period_start,
            period_end=period_end,
            dimensions={"tenor": tenor},
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="percent",
            provider=provider,
            source_reference=f"fixture:{provider}",
            release_event_id=f"fixture:lpr:{period_start}:{provider}",
            release_at=public_at,
            public_available_at=public_at,
            fetched_at=public_at,
            available_at=public_at,
            certification_status="certified",
            quality_status="validated",
        )
    )
