from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import (
    EvidenceRepository,
    EvidenceValueState,
    SourceClaimInput,
)
from pring_cycle.model_evaluation import (
    _context_coverage_gaps,
    _context_selection_gaps,
    _single_context_coverage_gaps,
    context_replay_gaps,
    evaluate_context_replay,
)
from pring_cycle.models import (
    CALIBRATION_BASELINE,
    ModelRepository,
    analytical_model_v0002_manifest,
    analytical_model_v0003_manifest,
    certified_120d_model_v0006_manifest,
    certified_120d_model_v0010_manifest,
    certified_120d_model_v0011_manifest,
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

    assert v1.manifest_hash == ("87db11acfb184571b661b40e10b862927978e6e2e9954b22b5fe99882363e936")
    assert v2.model_version_id == "model-v0002"
    assert v2.status == "candidate"
    assert v2.manifest_hash != v1.manifest_hash
    assert analytical_model_v0002_manifest()["metric_catalog_version"] == ("metric-catalog-v0002")
    assert v2.manifest_hash == ("91dde912ebc73f501f402cbd1f6c04a8efb1442050c513ded8ebb3c9613e7c19")
    v3 = models.create_candidate(analytical_model_v0003_manifest())
    assert v3.model_version_id == "model-v0003"
    assert v3.manifest_hash != v2.manifest_hash


def test_v6_separates_core_calibration_from_120d_source_replay() -> None:
    manifest = certified_120d_model_v0006_manifest(
        ({"package_id": "source-certification-fixture"},)
    )

    assert manifest["calibration_range_start"] == "2018-06-01"
    assert manifest["history_input_start"] == "2017-01-01"
    assert manifest["certified_replay_start"] == "2026-03-09"
    assert manifest["visible_evidence_window_trading_days"] == 120


def test_v6_unlicensed_p2_gaps_do_not_block_p1_certification_replay() -> None:
    manifest = certified_120d_model_v0006_manifest(
        ({"package_id": "source-certification-fixture"},)
    )

    assert context_replay_gaps(manifest, certified_model_v0001_manifest()) == ()


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

    assert any(gap.startswith("candidate_context_evidence_missing:") for gap in replay.gaps)
    assert any(gap.startswith("candidate_context_formula_output_missing:") for gap in replay.gaps)
    assert replay.evaluated_cutoffs == 0
    assert replay.context_output_differences == 0


def test_market_p1_certification_change_requires_replay_evidence(tmp_path: Path) -> None:
    database = tmp_path / "models.sqlite3"
    EvidenceRepository.create(database)
    comparison = certified_model_v0001_manifest()
    candidate = certified_model_v0001_manifest()
    candidate["metric_definitions"] = [
        (
            {
                **definition,
                "certification_status": "certified",
                "source_candidates": ["candidate-market-source"],
            }
            if definition["metric_id"] == "CN_EQ_CSI300"
            else definition
        )
        for definition in candidate["metric_definitions"]
    ]

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-28",
        requested_end="2026-08-28",
        replay_days=("2026-08-28",),
    )

    assert "candidate_context_evidence_missing:CN_EQ_CSI300" in replay.gaps
    assert replay.evaluated_cutoffs == 0


def test_source_certified_model_replays_unchanged_market_p1_metrics(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    EvidenceRepository.create(database)
    packages = ({"package_id": "fixture-certified-sources"},)
    comparison = certified_120d_model_v0010_manifest(packages)
    candidate = certified_120d_model_v0011_manifest(packages)

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-28",
        requested_end="2026-08-28",
        replay_days=("2026-08-28",),
    )

    assert "candidate_context_evidence_missing:CN_EQ_CSI500" in replay.gaps
    assert replay.evaluated_cutoffs == 0


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


def test_daily_context_coverage_requires_ninety_five_percent_of_replay_days() -> None:
    def vintage(period: str) -> SimpleNamespace:
        return SimpleNamespace(
            certification_status="certified",
            quality_status="validated",
            public_available_at=datetime.fromisoformat(f"{period}T00:00:00+00:00"),
            period_start=period,
            period_end=period,
        )

    required = tuple(f"2026-01-{day:02d}" for day in range(1, 21))
    dense = tuple(vintage(period) for period in required if period != required[9])
    sparse = tuple(vintage(period) for period in required[::4])

    assert (
        _context_coverage_gaps(
            "candidate",
            "CN_DAILY_FIXTURE",
            "daily",
            dense,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 20),
            warmup_days=0,
            required_days=required,
        )
        == []
    )
    assert "candidate_context_coverage_density:CN_DAILY_FIXTURE" in _context_coverage_gaps(
        "candidate",
        "CN_DAILY_FIXTURE",
        "daily",
        sparse,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 20),
        warmup_days=0,
        required_days=required,
    )


def test_policy_rate_is_carried_forward_between_official_change_events() -> None:
    def vintage(period: str) -> SimpleNamespace:
        return SimpleNamespace(
            certification_status="certified",
            quality_status="validated",
            public_available_at=datetime.fromisoformat(f"{period}T00:00:00+00:00"),
            period_start=period,
            period_end=period,
        )

    required = tuple(f"2026-01-{day:02d}" for day in range(1, 21))

    assert _context_coverage_gaps(
        "candidate",
        "CN_OMO_7D_RATE",
        "daily",
        (vintage(required[0]), vintage(required[-1])),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 20),
        warmup_days=0,
        required_days=required,
    ) == []


def test_warrant_coverage_requires_dense_120_day_history_but_allows_one_no_row_day() -> None:
    required: list[str] = []
    candidate = date(2026, 3, 9)
    while len(required) < 120:
        if candidate.weekday() < 5:
            required.append(candidate.isoformat())
        candidate += timedelta(days=1)

    def vintage(period: str) -> SimpleNamespace:
        return SimpleNamespace(
            certification_status="certified",
            quality_status="validated",
            public_available_at=datetime.fromisoformat(f"{period}T12:00:00+00:00"),
            period_start=period,
            period_end=period,
        )

    dense = tuple(vintage(period) for period in required if period != required[73])
    sparse = tuple(
        vintage(period)
        for index, period in enumerate(required)
        if index % 10 == 0 or index == len(required) - 1
    )
    kwargs = {
        "side": "candidate",
        "metric_id": "CN_FUTURES_WARRANTS",
        "frequency": "daily",
        "start_date": date.fromisoformat(required[0]),
        "end_date": date.fromisoformat(required[-1]),
        "warmup_days": 0,
        "member": "symbol=CF",
        "required_days": tuple(required),
    }

    assert _single_context_coverage_gaps(valid=dense, **kwargs) == []
    assert (
        "candidate_context_coverage_density:CN_FUTURES_WARRANTS:[symbol=CF]"
        in _single_context_coverage_gaps(valid=sparse, **kwargs)
    )


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

    assert any(gap.startswith("candidate_context_evidence_missing:") for gap in replay.gaps)
    assert "candidate_context_formula_output_missing:real_inventory_approximation" in replay.gaps


def test_context_replay_accepts_complete_registered_receipts_without_optional_fields(
    tmp_path: Path,
) -> None:
    database = tmp_path / "models.sqlite3"
    repository = EvidenceRepository.create(database)
    candidate = certified_120d_model_v0006_manifest(
        ({"package_id": "source-certification-fixture"},)
    )
    comparison = certified_120d_model_v0006_manifest(
        ({"package_id": "source-certification-fixture"},)
    )
    # This unit isolates the warrant member contract. Full source-certified
    # candidates are covered separately by the all-P1 replay test below.
    candidate.pop("source_certification_packages")
    comparison.pop("source_certification_packages")
    comparison["metric_definitions"] = [
        (
            {
                **definition,
                "certification_status": "awaiting_source_certification",
            }
            if definition["metric_id"] == "CN_FUTURES_WARRANTS"
            else definition
        )
        for definition in comparison["metric_definitions"]
    ]
    for day in (date(2026, 8, 27), date(2026, 8, 28)):
        observed = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
        for symbol in ("CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA"):
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_FUTURES_WARRANTS",
                    definition_version="metric-catalog-v0003",
                    period_kind="business_day",
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    dimensions={
                        "exchange": "fixture",
                        "measure": "registered_receipts",
                        "symbol": symbol,
                        "warehouse": "fixture",
                    },
                    value=100.0,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="tonne",
                    provider="tushare",
                    source_reference=f"tushare:fut_wsr:vol:{symbol}:{day}",
                    release_event_id=f"tushare:fut_wsr:{symbol}:{day}",
                    release_at=observed,
                    public_available_at=observed,
                    fetched_at=observed,
                    available_at=observed,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    inactive_day = date(2026, 8, 15)
    repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_FUTURES_WARRANTS",
            definition_version="metric-catalog-v0003",
            period_kind="business_day",
            period_start=inactive_day.isoformat(),
            period_end=inactive_day.isoformat(),
            dimensions={
                "exchange": "fixture",
                "measure": "registered_receipts",
                "symbol": "CF",
                "warehouse": "inactive-warehouse",
            },
            value=50.0,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit="tonne",
            provider="tushare",
            source_reference="tushare:fut_wsr:vol:CF:inactive",
            release_event_id="tushare:fut_wsr:CF:inactive",
            release_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
            public_available_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
            fetched_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
            available_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
            certification_status="certified",
            quality_status="validated",
        )
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-27",
        requested_end="2026-08-28",
        replay_days=("2026-08-27", "2026-08-28"),
    )

    assert replay.gaps == ()


def test_context_replay_uses_trading_day_cutoff_not_partial_same_day_release(
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
    for tenor, value, second in (("1y", 3.0, 0), ("5y_plus", 3.5, 30)):
        _append_lpr_claim(
            repository,
            provider=f"中国货币网-{tenor}",
            value=value,
            public_at=datetime(2026, 8, 20, 1, 0, second, tzinfo=UTC),
            tenor=tenor,
        )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-20",
        requested_end="2026-08-20",
        replay_days=("2026-08-20",),
    )

    assert replay.gaps == ()
    assert replay.evaluated_cutoffs == 1


def test_context_replay_excludes_claims_released_on_next_china_business_day(
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
    visible = datetime(2026, 8, 28, 10, tzinfo=ZoneInfo("Asia/Shanghai"))
    for tenor, value in (("1y", 3.0), ("5y_plus", 3.5)):
        _append_lpr_claim(
            repository,
            provider=f"中国货币网-{tenor}",
            value=value,
            public_at=visible,
            tenor=tenor,
        )
    _append_lpr_claim(
        repository,
        provider="next-day-conflicting-source",
        value=3.2,
        public_at=datetime(2026, 8, 29, 6, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    replay = evaluate_context_replay(
        database,
        candidate,
        comparison,
        requested_start="2026-08-28",
        requested_end="2026-08-28",
        replay_days=("2026-08-28",),
    )

    assert replay.gaps == ()
    assert replay.evaluated_cutoffs == 1


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


def test_context_selection_combines_members_with_same_period_end_and_distinct_starts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "models.sqlite3")
    monkeypatch.setattr(
        evidence_module,
        "metric_definition",
        lambda metric_id, *, definition_version="metric-catalog-v0001": replace(
            metric_definition(metric_id, definition_version=definition_version),
            certification_status="certified",
        ),
    )
    public_at = datetime(2026, 3, 13, 9, tzinfo=UTC)
    for measure, period_start, value in (
        ("ytd_increment", "2026-01-01", 96000.0),
        ("stock_end", "2026-02-01", 4514000.0),
    ):
        repository.append_source_claim(
            SourceClaimInput(
                metric_id="CN_SF_TOTAL",
                definition_version="metric-catalog-v0001",
                period_kind="month",
                period_start=period_start,
                period_end="2026-02-28",
                dimensions={"measure": measure},
                value=value,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="hundred_million_cny",
                provider="中国人民银行",
                source_reference=f"fixture:sf:{measure}",
                release_event_id="fixture:sf:2026-02",
                release_at=public_at,
                public_available_at=public_at,
                fetched_at=public_at,
                available_at=public_at,
                certification_status="certified",
                quality_status="validated",
            )
        )

    gaps = _context_selection_gaps(
        repository,
        side="candidate",
        metric_id="CN_SF_TOTAL",
        definition_version="metric-catalog-v0001",
        frequency="monthly",
        cutoff=datetime(2026, 3, 13, 23, tzinfo=UTC),
    )

    assert gaps == ()


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
