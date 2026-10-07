"""Confirmation in the context projection: the PMI against each stage's cells (ADR-0037)."""

from __future__ import annotations

import calendar
import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.confirmation import MANIFEST_FIELDS
from pring_cycle.context_projection import (
    ContextProjection,
    ContextProjectionRules,
    build_context_projection,
)
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository, model_v0014_manifest, model_v0015_manifest
from tests.integration.test_context_projection import _v2_manifest

TARGET = "2026-09-15"
AS_OF = datetime(2026, 9, 16, tzinfo=UTC)
MONTHS = ("2026-06", "2026-07", "2026-08")
SERIES = ("manufacturing", "new_orders", "production", "purchase_volume")


def confirmation_manifest(base: dict[str, Any] | None = None) -> dict[str, Any]:
    """``base`` (a builtin-catalog model reading the PMI) with v0015's confirmation rules."""
    manifest = dict(base or _v2_manifest("CN_PMI_ACTIVITY"))
    new = model_v0015_manifest()
    manifest.update({field: new[field] for field in MANIFEST_FIELDS})
    manifest["model_version_id"] = "model-confirmation-fixture"
    return manifest


def append_pmi(
    repository: EvidenceRepository,
    series: str,
    values: tuple[float | None, ...],
    *,
    months: tuple[str, ...] = MONTHS,
    definition_version: str = "metric-catalog-v0002",
) -> list[str]:
    """One PMI member's values for ``months``, oldest first; None leaves a month out."""
    claim_ids = []
    for period, value in zip(months, values, strict=True):
        if value is None:
            continue
        year, month = (int(part) for part in period.split("-"))
        end = f"{period}-{calendar.monthrange(year, month)[1]:02d}"
        public = datetime(year, month, calendar.monthrange(year, month)[1], 2, tzinfo=UTC)
        claim_ids.append(
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id="CN_PMI_ACTIVITY",
                    definition_version=definition_version,
                    period_kind="month",
                    period_start=f"{period}-01",
                    period_end=end,
                    dimensions={"series": series, "measure": "level"},
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="diffusion_index_points",
                    provider="certified-fixture",
                    source_reference=f"fixture:pmi:{series}:{period}",
                    release_event_id=f"release:pmi:{period}",
                    release_at=public,
                    public_available_at=public,
                    fetched_at=public,
                    available_at=public,
                    certification_status="certified",
                    quality_status="validated",
                )
            ).claim_id
        )
    return claim_ids


def project(
    repository: EvidenceRepository,
    stage: FormalStage | None,
    *,
    reason: str = "canonical_combination",
    manifest: dict[str, Any] | None = None,
) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=manifest or confirmation_manifest(),
        formal_stage=StageResult(stage, stage, reason),
    )


def pmi(context: ContextProjection) -> dict[str, Any]:
    confirmation = context.macro["confirmation"]
    overheat = next(
        item
        for item in confirmation["dimensions"]  # type: ignore[index]
        if item["dimension"] == "overheat"
    )
    return next(item for item in overheat["key_indicators"] if item["key"] == "pmi")  # type: ignore[no-any-return]


def seed(repository: EvidenceRepository, main: tuple[float | None, ...], **auxiliary: Any) -> None:
    """The main member's values; each other member follows it unless given its own."""
    for series in SERIES:
        append_pmi(
            repository, series, auxiliary.get(series, main) if series != "manufacturing" else main
        )


# Each stage's cells (expectation-table.md), with the manufacturing PMI's last three months.
@pytest.mark.parametrize(
    ("stage", "values", "relation", "extra"),
    [
        # I: below 50 and falling supports; above and rising refutes; below and rising,
        # steepening, is observed with a turn toward II.
        ("stage_i", (49.5, 49.2, 48.8), "support", {}),
        ("stage_i", (49.6, 49.0, 48.8), "support", {"slope": "slower"}),
        ("stage_i", (50.5, 50.8, 51.2), "counterevidence", {}),
        ("stage_i", (48.0, 48.2, 48.9), "observation_only", {"turn_hint": "stage_ii"}),
        # II: recovering below 50 or just crossing it supports; falling faster refutes;
        # above and steepening is observed with a turn toward III.
        ("stage_ii", (49.0, 49.3, 49.5), "support", {}),
        ("stage_ii", (49.6, 49.8, 50.4), "support", {"crossed": "above"}),
        ("stage_ii", (49.8, 50.0, 50.4), "support", {"crossed": "above"}),
        ("stage_ii", (49.5, 49.2, 48.5), "counterevidence", {}),
        ("stage_ii", (50.5, 50.8, 51.4), "observation_only", {"turn_hint": "stage_iii"}),
        # A slope reads along its cell's momentum: above 50 and falling faster is no turn.
        ("stage_ii", (53.0, 52.5, 51.0), "observation_only", {"turn_hint": None}),
        # III: above and rising supports, slowing only observed; below 50 waits on grace.
        ("stage_iii", (50.2, 50.5, 51.0), "support", {}),
        ("stage_iii", (50.2, 50.8, 51.0), "observation_only", {"notes": ["扩张仍在、动能减弱"]}),
        # A fall narrowing is no slowing of the expansion: no cell names it.
        ("stage_iii", (52.0, 51.0, 50.5), "observation_only", {"notes": [], "matched": None}),
        ("stage_iii", (49.8, 49.5, 49.2), "observation_only", {"grace": "not_evaluated"}),
        # IV: above 50 supports; rising slower is the late phase.
        ("stage_iv", (51.0, 51.5, 51.2), "support", {}),
        ("stage_iv", (50.5, 51.2, 51.4), "observation_only", {"notes": ["扩张后段，斜率放缓"]}),
        ("stage_iv", (52.0, 51.0, 50.5), "support", {"notes": []}),
        ("stage_iv", (50.5, 50.2, 49.6), "observation_only", {"grace": "not_evaluated"}),
        # V: momentum down supports, the level still high noted; flat is only observed.
        ("stage_v", (51.5, 51.2, 50.8), "support", {"notes": ["水平仍高、动量下降"]}),
        ("stage_v", (51.0, 51.2, 51.2), "observation_only", {"momentum": "flat"}),
        ("stage_v", (50.0, 50.2, 50.8), "observation_only", {"grace": "not_evaluated"}),
        # VI: below 50 and falling supports; above and rising waits on grace.
        ("stage_vi", (49.5, 49.2, 48.8), "support", {}),
        ("stage_vi", (50.0, 50.4, 51.0), "observation_only", {"grace": "not_evaluated"}),
    ],
)
def test_each_stage_reads_the_pmi_against_its_own_cells(
    tmp_path: Path,
    stage: str,
    values: tuple[float, ...],
    relation: str,
    extra: dict[str, Any],
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, values)

    indicator = pmi(project(repository, FormalStage(stage)))

    assert indicator["relation"] == relation
    assert indicator["proposition"]
    assert indicator["consistency"] == "consistent"
    main = indicator["members"][0]
    assert main["role"] == "main" and main["member"]["series"] == "manufacturing"
    assert main["values"] == list(values)
    assert main["periods"] == ["2026-06-30", "2026-07-31", "2026-08-31"]
    for key, expected in extra.items():
        actual = main[key] if key in {"slope", "crossed", "momentum"} else indicator[key]
        assert actual == expected


def test_the_dimensions_count_and_the_others_are_not_connected(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.5, 49.2, 48.8))

    context = project(repository, FormalStage.STAGE_I)

    confirmation = context.macro["confirmation"]
    assert confirmation["stage"] == "stage_i" and confirmation["applicable"] is True  # type: ignore[index]
    by_dimension = {item["dimension"]: item for item in confirmation["dimensions"]}  # type: ignore[index]
    assert list(by_dimension) == ["policy", "credit", "overheat", "price", "inventory"]
    # The PMI supports; industrial value added, with nothing held, is unconfirmed.
    assert by_dimension["overheat"]["counts"] == {
        "support": 1,
        "counterevidence": 0,
        "observation_only": 0,
        "unconfirmed": 1,
        "not_applicable": 0,
    }
    for name in ("credit", "price"):
        assert by_dimension[name]["status"] == "connected"
        assert by_dimension[name]["counts"]["unconfirmed"] == len(
            by_dimension[name]["key_indicators"]
        )
    for name in ("policy", "inventory"):
        assert by_dimension[name] == {
            "dimension": name,
            "status": "not_connected",
            "counts": None,
            "key_indicators": [],
        }
    # No label stands in for the dimension summary, nor the seven cards for inventory.
    for label in ("policy_direction", "credit_response", "overheat_state", "price_pressure"):
        assert label not in context.macro
    assert "cards" not in context.inventory and "quadrant" not in context.inventory
    assert context.inventory["status"] == "not_connected"


def test_an_unknown_month_leaves_the_pmi_unconfirmed_and_says_which(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.5, None, 48.8))

    indicator = pmi(project(repository, FormalStage.STAGE_I))

    assert indicator["relation"] == "unconfirmed"
    assert indicator["proposition"] is None
    assert indicator["missing"] == ["measure=level,series=manufacturing:2026-07"]
    main = indicator["members"][0]
    assert main["momentum"] is None and main["slope"] is None
    # The month before the gap is no previous month: it is not read over the gap.
    assert main["values"] == [48.8] and main["missing"] == ["2026-07"]


@pytest.mark.parametrize(
    ("stage", "values", "missing"),
    [
        # The slope's earliest month: momentum is known, the slope is not.
        (FormalStage.STAGE_I, (None, 49.2, 48.8), ["2026-06"]),
        # Below 50 alone would meet stage III's cell waiting on grace: still unknown.
        (FormalStage.STAGE_III, (None, None, 48.8), ["2026-06", "2026-07"]),
    ],
)
def test_a_reading_short_of_its_months_is_unconfirmed_whatever_the_cell(
    tmp_path: Path, stage: FormalStage, values: tuple[float | None, ...], missing: list[str]
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, values)

    indicator = pmi(project(repository, stage))

    assert indicator["relation"] == "unconfirmed"
    assert indicator["grace"] is None
    assert indicator["missing"] == [
        f"measure=level,series=manufacturing:{month}" for month in missing
    ]


def test_no_pmi_at_all_is_unconfirmed_not_a_direction(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")

    indicator = pmi(project(repository, FormalStage.STAGE_III))

    assert indicator["relation"] == "unconfirmed"
    assert indicator["consistency"] == "unknown"
    assert indicator["missing"] and indicator["missing"][0].startswith(
        "measure=level,series=manufacturing:"
    )


def test_a_flat_pmi_is_not_read_as_easing(tmp_path: Path) -> None:
    # Stage I expects a falling PMI: an unchanged one is no support, only observed.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.0, 49.0, 49.0))

    indicator = pmi(project(repository, FormalStage.STAGE_I))

    assert indicator["members"][0]["momentum"] == "flat"
    assert indicator["members"][0]["slope"] == "flat"
    assert indicator["relation"] == "observation_only"


def test_a_member_against_the_main_one_caps_the_relation_at_observation(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.5, 49.2, 48.8), new_orders=(48.0, 48.2, 48.6))

    indicator = pmi(project(repository, FormalStage.STAGE_VI))

    assert indicator["consistency"] == "divergent"
    assert indicator["relation"] == "observation_only"
    assert indicator["divergence_capped"] is True
    assert indicator["notes"] == ["订单先改善：只改动量描述，不宣布复苏"]
    consistency = {
        member["member"]["series"]: member["consistency"] for member in indicator["members"]
    }
    assert consistency == {
        "manufacturing": "main",
        "new_orders": "opposes",
        "production": "agrees",
        "purchase_volume": "agrees",
    }


def test_orders_improving_first_is_noted_in_stage_vi_whatever_the_pmi_does(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.0, 49.0, 49.0), new_orders=(48.5, 48.8, 49.2))

    indicator = pmi(project(repository, FormalStage.STAGE_VI))

    assert indicator["relation"] == "observation_only"
    assert indicator["notes"] == ["订单先改善：只改动量描述，不宣布复苏"]


def test_new_orders_leading_production_is_noted_in_stage_ii(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(
        repository,
        (49.0, 49.3, 49.5),
        new_orders=(49.0, 49.4, 50.2),
        production=(49.0, 49.2, 49.3),
    )

    indicator = pmi(project(repository, FormalStage.STAGE_II))

    assert indicator["relation"] == "support"
    assert indicator["notes"] == ["新订单领先生产"]


@pytest.mark.parametrize("reason", ["noncanonical_combination", "core_data_pending"])
def test_without_a_formal_stage_confirmation_is_not_applicable_and_still_reads(
    tmp_path: Path, reason: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.5, 49.2, 48.8))

    context = project(repository, None, reason=reason)

    confirmation = context.macro["confirmation"]
    assert confirmation["applicable"] is False and confirmation["stage"] is None  # type: ignore[index]
    assert confirmation["stage_reason"] == reason  # type: ignore[index]
    indicator = pmi(context)
    assert indicator["relation"] == "not_applicable"
    assert indicator["members"][0]["momentum"] == "down"
    assert indicator["members"][0]["level"] == "below"
    overheat = confirmation["dimensions"][2]  # type: ignore[index]
    assert overheat["counts"]["not_applicable"] == 2


def test_the_months_read_are_model_inputs(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    main = append_pmi(repository, "manufacturing", (49.5, 49.2, 48.8))

    context = project(repository, FormalStage.STAGE_I)

    assert set(main) <= set(context.macro["model_input_observation_version_ids"])  # type: ignore[arg-type]
    assert set(main) <= set(context.observation_version_ids)


def test_a_confirmation_model_needs_the_formal_stage(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")

    with pytest.raises(ValueError, match="confirmation_formal_stage_required"):
        build_context_projection(
            repository,
            as_of=AS_OF,
            target_business_date=TARGET,
            model_manifest=confirmation_manifest(),
        )


def test_the_same_evidence_reads_the_old_way_under_the_old_model(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, (49.5, 49.2, 48.8))

    old = build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=_v2_manifest("CN_PMI_ACTIVITY"),
    )
    new = project(repository, FormalStage.STAGE_I)

    for label in ("policy_direction", "credit_response", "overheat_state", "price_pressure"):
        assert label in old.macro and label not in new.macro
    assert "output_structure" not in old.macro and "output_structure" not in old.inventory
    assert "confirmation" not in old.macro
    assert len(old.inventory["cards"]) == 7  # type: ignore[arg-type]
    assert (
        new.macro["output_structure"] == new.inventory["output_structure"] == ("confirmation-v0001")
    )
    # Both show the same evidence rows; only what is concluded from them differs.
    assert old.macro["overheat"]["evidence"] == new.macro["overheat"]["evidence"]  # type: ignore[index]


def test_the_rules_are_frozen_in_the_new_manifest_alone(tmp_path: Path) -> None:
    old, new = model_v0014_manifest(), model_v0015_manifest()

    assert not set(MANIFEST_FIELDS) & set(old)
    assert ContextProjectionRules.from_manifest(old).confirmation is None
    rules = ContextProjectionRules.from_manifest(new).confirmation
    assert rules is not None and [item.key for item in rules.indicators] == [
        "pmi",
        "industrial_va",
        "ppi",
        "cpi",
        "pmi_prices",
        "social_financing",
        "money",
    ]
    # The rules are part of the manifest's hash: the same model with other cells is refused.
    models = ModelRepository.create(tmp_path / "models.sqlite3")
    models.create_candidate(new)
    edited = copy.deepcopy(new)
    edited["confirmation_rules"]["key_indicators"][0]["expectations"]["stage_i"]["cells"].pop()
    with pytest.raises(ValueError, match="model_version_is_immutable"):
        models.create_candidate(edited)
    # Each manifest holds its own rules: changing one changes no other built after it.
    built = model_v0015_manifest()
    built["confirmation_rules"]["key_indicators"][0]["expectations"]["stage_i"]["cells"].clear()
    assert model_v0015_manifest() == new
