from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from math import nan
from pathlib import Path

import pytest

from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)


def claim(
    *,
    value: float | None,
    public_at: str,
    system_at: str,
    provider: str = "official",
    value_state: EvidenceValueState = EvidenceValueState.REPORTED_VALUE,
) -> SourceClaimInput:
    return SourceClaimInput(
        metric_id="CN_CPI_HEADLINE",
        definition_version="metric-catalog-v0001",
        period_kind="interval",
        period_start="2026-06-01",
        period_end="2026-06-30",
        dimensions={"measure": "yoy", "category": "headline"},
        value=value,
        value_state=value_state,
        unit="percent",
        provider=provider,
        source_reference=f"fixture:{provider}:{system_at}",
        release_event_id=f"release:{provider}:{public_at}",
        release_at=datetime.fromisoformat(public_at),
        public_available_at=datetime.fromisoformat(public_at),
        fetched_at=datetime.fromisoformat(system_at),
        available_at=datetime.fromisoformat(system_at),
        certification_status="awaiting_source_certification",
        quality_status="validated",
    )


def repository(tmp_path: Path) -> EvidenceRepository:
    return EvidenceRepository.create(tmp_path / "evidence.sqlite3")


def test_public_and_system_as_of_are_explicit_and_distinct(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    stored = evidence.append_source_claim(
        claim(
            value=1.2,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:05:00+00:00",
        )
    )

    assert (
        evidence.query(
            stored.observation_id,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 7, 15, 2, 2, tzinfo=UTC),
        ).selected_value
        == 1.2
    )
    assert (
        evidence.query(
            stored.observation_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 7, 15, 2, 2, tzinfo=UTC),
        ).selection_status
        == "unavailable"
    )
    assert (
        evidence.query(
            stored.observation_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 7, 15, 2, 5, tzinfo=UTC),
        ).selected_value
        == 1.2
    )


def test_point_in_time_comparison_normalizes_equivalent_timezone_offsets(
    tmp_path: Path,
) -> None:
    evidence = repository(tmp_path)
    stored = evidence.append_source_claim(
        claim(
            value=1.2,
            public_at="2026-07-15T10:00:00+08:00",
            system_at="2026-07-15T10:05:00+08:00",
        )
    )

    result = evidence.query(
        stored.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 15, 2, 6, tzinfo=UTC),
    )

    assert result.selected_value == 1.2
    assert result.claims[0].available_at == datetime(2026, 7, 15, 2, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"metric_id": "CPI"}, "unknown_metric_id"),
        ({"unit": "basis_points"}, "evidence_unit_mismatch"),
        ({"value": nan}, "evidence_value_must_be_finite"),
        ({"dimensions": {}}, "evidence_dimensions_mismatch"),
    ),
)
def test_claims_must_match_the_frozen_metric_identity(
    tmp_path: Path,
    change: dict[str, object],
    message: str,
) -> None:
    evidence = repository(tmp_path)

    with pytest.raises((KeyError, ValueError), match=message):
        evidence.append_source_claim(
            replace(
                claim(
                    value=1.2,
                    public_at="2026-07-15T02:00:00+00:00",
                    system_at="2026-07-15T02:05:00+00:00",
                ),
                **change,
            )
        )


def test_revision_is_append_only_and_does_not_rewrite_old_as_of(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    first = evidence.append_source_claim(
        claim(
            value=1.2,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:05:00+00:00",
        )
    )
    revised = evidence.append_source_claim(
        claim(
            value=1.4,
            public_at="2026-08-15T02:00:00+00:00",
            system_at="2026-08-15T02:05:00+00:00",
        )
    )

    old_view = evidence.query(
        first.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 31, tzinfo=UTC),
    )
    current_view = evidence.query(
        first.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 16, tzinfo=UTC),
    )

    assert old_view.selected_value == 1.2
    assert current_view.selected_value == 1.4
    assert revised.supersedes_claim_id == first.claim_id
    assert evidence.claim_count(first.observation_id) == 2


def test_conflicting_sources_are_preserved_and_never_averaged(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    first = evidence.append_source_claim(
        claim(
            value=1.2,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:05:00+00:00",
        )
    )
    evidence.append_source_claim(
        claim(
            value=2.2,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:06:00+00:00",
            provider="certified_backup",
        )
    )

    result = evidence.query(
        first.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
        tolerance=0.1,
    )

    assert result.selection_status == "conflicted"
    assert {item.value for item in result.claims} == {1.2, 2.2}
    assert result.selected_value in {1.2, 2.2}
    assert result.selected_value != 1.7


def test_legal_non_numeric_value_states_are_not_zero(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    stored = evidence.append_source_claim(
        claim(
            value=None,
            value_state=EvidenceValueState.NOT_DISCLOSED,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:05:00+00:00",
        )
    )

    result = evidence.query(
        stored.observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 7, 16, tzinfo=UTC),
    )

    assert result.selected_value is None
    assert result.value_state is EvidenceValueState.NOT_DISCLOSED


def test_metric_series_preserves_period_order_and_conflict_status(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    first = claim(
        value=100.0,
        public_at="2026-07-01T01:00:00+00:00",
        system_at="2026-07-01T01:05:00+00:00",
    )
    second = replace(
        first,
        period_start="2026-08-28",
        period_end="2026-08-28",
        value=101.0,
        source_reference="fixture:official:2026-08-28",
        release_event_id="release:official:2026-08-28",
        public_available_at=datetime(2026, 8, 28, 1, tzinfo=UTC),
        release_at=datetime(2026, 8, 28, 1, tzinfo=UTC),
        available_at=datetime(2026, 8, 28, 1, 5, tzinfo=UTC),
        fetched_at=datetime(2026, 8, 28, 1, 5, tzinfo=UTC),
    )
    evidence.append_source_claim(first)
    evidence.append_source_claim(second)
    evidence.append_source_claim(
        replace(
            second,
            provider="certified_backup",
            value=99.0,
            source_reference="fixture:backup:2026-08-28",
            release_event_id="release:backup:2026-08-28",
        )
    )

    series = evidence.metric_series(
        first.metric_id,
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert [item.period_end for item in series] == ["2026-06-30", "2026-08-28"]
    assert series[0].selection_status == "selected"
    assert series[1].selection_status == "conflicted"


def test_trace_derived_lineage_attempts_and_snapshots_are_immutable_ledger_entries(
    tmp_path: Path,
) -> None:
    evidence = repository(tmp_path)
    stored = evidence.append_source_claim(
        claim(
            value=1.2,
            public_at="2026-07-15T02:00:00+00:00",
            system_at="2026-07-15T02:05:00+00:00",
        )
    )
    cutoff = datetime(2026, 7, 16, tzinfo=UTC)

    trace = evidence.trace(stored.observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff)
    derived = evidence.append_derived_observation(
        metric_id="CN_CREDIT_IMPULSE",
        formula_version="credit-impulse-v0001",
        input_observation_version_ids=(stored.claim_id,),
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=cutoff,
        computed_at=cutoff,
        value=0.2,
        unit="percentage_points",
    )
    attempt_id = evidence.record_retrieval_attempt(
        metric_id="CN_CPI_HEADLINE",
        channel="official",
        outcome="verified",
        fetched_at=cutoff,
        safe_metadata={"http_status": "200"},
    )
    snapshot = evidence.freeze_snapshot(
        (stored.claim_id, derived.derived_observation_id),
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
    )

    assert trace.metric_id == "CN_CPI_HEADLINE"
    assert trace.period_end == "2026-06-30"
    assert trace.claims[0].available_at == datetime(2026, 7, 15, 2, 5, tzinfo=UTC)
    assert derived.input_observation_version_ids == (stored.claim_id,)
    derived_trace = evidence.derived_trace(
        derived.derived_observation_id,
        mode=AsOfMode.SYSTEM,
        as_of=cutoff,
    )
    assert derived_trace.metric_id == "CN_CREDIT_IMPULSE"
    assert derived_trace.formula_version == "credit-impulse-v0001"
    assert derived_trace.input_observation_version_ids == (stored.claim_id,)
    assert derived_trace.value == 0.2
    assert len(attempt_id) == 64
    assert snapshot.observation_version_ids == tuple(
        sorted((stored.claim_id, derived.derived_observation_id))
    )


def test_multiscalar_catalog_group_accepts_only_its_frozen_units(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    base = SourceClaimInput(
        metric_id="CN_M1_M2",
        definition_version="metric-catalog-v0001",
        period_kind="month",
        period_start="2026-07-01",
        period_end="2026-07-31",
        dimensions={"aggregate": "m2", "measure": "balance"},
        value=320_000.0,
        value_state=EvidenceValueState.REPORTED_VALUE,
        unit="hundred_million_cny",
        provider="tushare",
        source_reference="tushare:cn_m:2026-07:m2:balance",
        release_event_id="release:cn_m:2026-07",
        release_at=datetime(2026, 8, 12, 2, tzinfo=UTC),
        public_available_at=datetime(2026, 8, 12, 2, tzinfo=UTC),
        fetched_at=datetime(2026, 8, 12, 3, tzinfo=UTC),
        available_at=datetime(2026, 8, 12, 3, tzinfo=UTC),
        certification_status="awaiting_source_certification",
        quality_status="validated",
    )

    stored = evidence.append_source_claim(base)
    assert stored.observation_id
    with pytest.raises(ValueError, match="evidence_unit_mismatch"):
        evidence.append_source_claim(replace(base, unit="index_points"))


def test_derived_trace_is_point_in_time_gated(tmp_path: Path) -> None:
    evidence = repository(tmp_path)
    cutoff = datetime(2026, 7, 16, tzinfo=UTC)
    derived = evidence.append_derived_observation(
        metric_id="CN_CREDIT_IMPULSE",
        formula_version="credit-impulse-v0001",
        input_observation_version_ids=("claim-input",),
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=cutoff,
        computed_at=cutoff,
        value=0.2,
        unit="percentage_points",
    )

    with pytest.raises(LookupError, match="derived_evidence_not_available"):
        evidence.derived_trace(
            derived.derived_observation_id,
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 7, 15, tzinfo=UTC),
        )
    with pytest.raises(LookupError, match="derived_evidence_not_available"):
        evidence.derived_trace(
            derived.derived_observation_id,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 7, 17, tzinfo=UTC),
        )
