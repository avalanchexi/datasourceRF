"""The monthly official key indicators against each stage's cells (ADR-0037, ticket 04).

Industrial value added, PPI, CPI, the PMI's prices, social financing and M1/M2, read as
their official values: level, momentum, slope, and within a year where the value stands
and whether its change is marked.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.confirmation import DerivedInput, derived_points
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_context_projection import _v2_manifest

TARGET = "2026-09-15"
AS_OF = datetime(2026, 9, 16, tzinfo=UTC)
# A year of months to the newest, oldest first; and the months before it, never read.
YEAR = tuple(f"{2025 + (8 + i) // 12}-{(8 + i) % 12 + 1:02d}" for i in range(12))
BEFORE = ("2025-07", "2025-08")
METRICS = (
    "CN_PMI_ACTIVITY",
    "CN_PMI_PRICES",
    "CN_INDUSTRIAL_VA",
    "CN_PPI",
    "CN_CPI_HEADLINE",
    "CN_CORE_CPI",
    "CN_M1_M2",
    "CN_SF_TOTAL",
    "CN_SF_COMPONENTS",
)
# Each indicator's members as (metric, dimensions, unit), the main one first; the builtin
# catalog holds industrial value added as a scalar.
INDICATORS: dict[str, tuple[tuple[str, dict[str, str], str], ...]] = {
    "industrial_va": (
        ("CN_INDUSTRIAL_VA", {"measure": "current_month_real_yoy"}, "scalar"),
        ("CN_INDUSTRIAL_VA", {"measure": "ytd_real_yoy"}, "scalar"),
        ("CN_INDUSTRIAL_VA", {"measure": "mom_seasonally_adjusted"}, "scalar"),
    ),
    "ppi": (
        ("CN_PPI", {"category": "headline", "measure": "yoy"}, "percent"),
        ("CN_PPI", {"category": "headline", "measure": "mom"}, "percent"),
        ("CN_PPI", {"category": "means_of_production", "measure": "yoy"}, "percent"),
        ("CN_PPI", {"category": "consumer_goods", "measure": "yoy"}, "percent"),
    ),
    "cpi": (
        ("CN_CPI_HEADLINE", {"category": "headline", "measure": "yoy"}, "percent"),
        ("CN_CORE_CPI", {"category": "ex_food_energy", "measure": "yoy"}, "percent"),
    ),
    "pmi_prices": (
        (
            "CN_PMI_PRICES",
            {"series": "output_prices", "measure": "level"},
            "diffusion_index_points",
        ),
        (
            "CN_PMI_PRICES",
            {"series": "purchase_prices", "measure": "level"},
            "diffusion_index_points",
        ),
    ),
    "money": (
        ("CN_M1_M2", {"aggregate": "m1", "measure": "yoy"}, "percent"),
        ("CN_M1_M2", {"aggregate": "m2", "measure": "yoy"}, "percent"),
    ),
    "social_financing": (
        ("CN_SF_TOTAL", {"measure": "stock_yoy"}, "percent"),
        *(
            ("CN_SF_COMPONENTS", {"component": component, "measure": "stock_yoy"}, "percent")
            for component in (
                "government_bonds",
                "renminbi_loans",
                "foreign_currency_loans_rmb",
                "entrusted_loans",
                "trust_loans",
                "undiscounted_bank_acceptances",
                "corporate_bonds",
                "nonfinancial_enterprise_equity",
            )
        ),
    ),
}
# Social financing's seven non-government components, by their place among its members.
NON_GOVERNMENT = range(2, 9)
INDUSTRIAL_VA_YTD = {"measure": "ytd_real_yoy"}


def manifest() -> dict[str, Any]:
    return confirmation_manifest(_v2_manifest(*METRICS))


def append(
    repository: EvidenceRepository,
    metric_id: str,
    dimensions: dict[str, str],
    values: tuple[float | None, ...],
    *,
    months: tuple[str, ...] = YEAR,
    unit: str = "percent",
    definition_version: str = "metric-catalog-v0002",
) -> list[str]:
    """One member's values for ``months``, oldest first; None leaves a month out."""
    claim_ids = []
    for period, value in zip(months, values, strict=True):
        if value is None:
            continue
        year, month = (int(part) for part in period.split("-"))
        last = calendar.monthrange(year, month)[1]
        public = datetime(year, month, last, 2, tzinfo=UTC)
        claim_ids.append(
            repository.append_source_claim(
                SourceClaimInput(
                    metric_id=metric_id,
                    definition_version=definition_version,
                    period_kind="month",
                    period_start=f"{period}-01",
                    period_end=f"{period}-{last:02d}",
                    dimensions=dimensions,
                    value=value,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit=unit,
                    provider="certified-fixture",
                    source_reference=f"fixture:{metric_id}:{sorted(dimensions.items())}:{period}",
                    release_event_id=f"release:{metric_id}:{period}",
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


def year(*last: float, fill: float) -> tuple[float, ...]:
    """A year of values ending with ``last``, the months before it at ``fill``."""
    return (fill,) * (12 - len(last)) + last


def seed(
    repository: EvidenceRepository,
    key: str,
    values: tuple[float, ...],
    *,
    auxiliary: dict[int, tuple[float, ...]] | None = None,
) -> None:
    """``values`` of the main member; each other follows it unless given its own.

    Industrial value added has no January, and its February is the January-February
    cumulative growth.
    """
    for index, (metric_id, dimensions, unit) in enumerate(INDICATORS[key]):
        own: tuple[float | None, ...] = (auxiliary or {}).get(index, values)
        if key == "industrial_va":
            # No January; February's current month is not released, its cumulative is
            # the main member's February.
            own = tuple(
                None
                if month.endswith("-01") or (month.endswith("-02") and index == 0)
                else values[i]
                if month.endswith("-02") and dimensions == INDUSTRIAL_VA_YTD
                else value
                for i, (month, value) in enumerate(zip(YEAR, own, strict=True))
            )
        append(repository, metric_id, dimensions, own, unit=unit)


def project(repository: EvidenceRepository, stage: FormalStage | None) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
    )


def indicator(context: ContextProjection, key: str) -> dict[str, Any]:
    confirmation = context.macro["confirmation"]
    return next(
        item
        for dimension in confirmation["dimensions"]  # type: ignore[index]
        for item in dimension["key_indicators"]
        if item["key"] == key
    )


def read(
    tmp_path: Path, key: str, stage: str, values: tuple[float, ...], **seeded: Any
) -> dict[str, Any]:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, key, values, **seeded)
    return indicator(project(repository, FormalStage(stage)), key)


_GRACE = {"grace": "not_evaluated"}
# Changes of 0.3 to 0.4 through the year, the last two of 0.1 and 0.2 down: ordinary.
ZIGZAG = (8.0, 8.4, 8.1, 8.5, 8.2, 8.6, 8.3, 8.7, 8.4, 8.5, 8.3, 8.2)


# Each stage's cells (expectation-table.md), the main member's year oldest first.
@pytest.mark.parametrize(
    ("key", "stage", "values", "relation", "extra"),
    [
        # Industrial value added: no line, its place in the year instead.
        ("industrial_va", "stage_i", year(5.5, 5.2, 5.0, fill=6.0), "support", {}),
        ("industrial_va", "stage_i", year(5.0, 5.2, 5.5, fill=5.0), "counterevidence", {}),
        # Unchanged and low in its year still supports stage I; unchanged and high is
        # only observed.
        ("industrial_va", "stage_i", year(5.0, 5.0, 5.0, fill=7.0), "support", {"position": "low"}),
        ("industrial_va", "stage_i", year(5.0, 5.0, 5.0, fill=4.0), "observation_only", {}),
        ("industrial_va", "stage_ii", year(4.0, 4.5, 5.0, fill=7.0), "support", {}),
        (
            "industrial_va",
            "stage_ii",
            year(6.0, 5.0, 4.5, fill=5.0),
            "observation_only",
            {"grace": None},
        ),
        ("industrial_va", "stage_ii", year(6.0, 5.5, 4.5, fill=5.0), "observation_only", _GRACE),
        ("industrial_va", "stage_iii", year(5.0, 5.2, 5.5, fill=5.0), "support", {}),
        ("industrial_va", "stage_iii", year(5.5, 5.2, 5.0, fill=5.0), "observation_only", _GRACE),
        (
            "industrial_va",
            "stage_iv",
            year(6.0, 6.5, 6.2, fill=4.0),
            "support",
            {"position": "high"},
        ),
        ("industrial_va", "stage_iv", year(6.5, 6.2, 6.0, fill=7.0), "observation_only", {}),
        ("industrial_va", "stage_v", year(6.5, 6.2, 6.0, fill=6.0), "support", {}),
        ("industrial_va", "stage_v", year(6.0, 6.2, 6.5, fill=6.0), "observation_only", _GRACE),
        ("industrial_va", "stage_vi", year(6.5, 6.2, 6.0, fill=6.0), "support", {}),
        ("industrial_va", "stage_vi", year(6.0, 6.0, 6.0, fill=5.0), "observation_only", {}),
        # PPI: negative or positive against 0.
        ("ppi", "stage_i", year(-1.0, -1.2, -1.5, fill=-1.0), "support", {"level": "below"}),
        ("ppi", "stage_i", year(-1.5, -1.0, -0.8, fill=-1.0), "counterevidence", {}),
        ("ppi", "stage_i", year(1.0, 1.0, 1.0, fill=1.0), "observation_only", {}),
        ("ppi", "stage_ii", year(-1.0, -1.2, -1.2, fill=-1.0), "support", {}),
        ("ppi", "stage_ii", year(-1.5, -1.0, -0.8, fill=-1.0), "observation_only", _GRACE),
        ("ppi", "stage_iii", year(-1.2, -1.2, -1.2, fill=-1.0), "support", {}),
        ("ppi", "stage_iii", year(-1.0, -1.2, -1.5, fill=-1.0), "observation_only", _GRACE),
        ("ppi", "stage_iv", year(1.0, 1.5, 2.0, fill=0.0), "support", {}),
        ("ppi", "stage_iv", year(2.0, 1.5, 1.0, fill=0.0), "observation_only", _GRACE),
        # High in its year supports stage V even falling; falling from the middle hints VI.
        ("ppi", "stage_v", year(3.0, 2.8, 2.7, fill=0.0), "support", {"position": "high"}),
        (
            "ppi",
            "stage_v",
            year(1.6, 1.4, 1.2, fill=3.0),
            "observation_only",
            {"turn_hint": "stage_vi"},
        ),
        ("ppi", "stage_vi", year(1.0, 0.5, 0.0, fill=1.0), "support", {}),
        ("ppi", "stage_vi", year(0.0, 0.5, 1.0, fill=1.0), "observation_only", _GRACE),
        # CPI: lagging.
        ("cpi", "stage_i", year(1.0, 0.8, 0.5, fill=1.0), "support", {}),
        ("cpi", "stage_i", year(0.5, 0.8, 1.0, fill=1.0), "observation_only", _GRACE),
        ("cpi", "stage_ii", year(0.2, 0.2, 0.2, fill=1.5), "support", {"position": "low"}),
        ("cpi", "stage_ii", year(0.2, 0.2, 0.2, fill=0.0), "observation_only", {}),
        ("cpi", "stage_iii", year(0.2, 0.4, 0.4, fill=0.0), "support", {}),
        ("cpi", "stage_iii", year(0.6, 0.4, 0.2, fill=0.0), "observation_only", {}),
        ("cpi", "stage_iv", year(1.0, 1.5, 2.0, fill=0.0), "support", {}),
        ("cpi", "stage_iv", year(2.0, 2.0, 2.0, fill=0.0), "observation_only", {}),
        ("cpi", "stage_v", year(2.5, 2.4, 2.3, fill=0.0), "support", {"position": "high"}),
        ("cpi", "stage_vi", year(2.0, 1.5, 1.0, fill=1.0), "support", {}),
        # The PMI's output prices, against 50 over three months.
        ("pmi_prices", "stage_i", year(49.0, 48.5, 48.0, fill=50.0), "support", {}),
        ("pmi_prices", "stage_i", year(50.2, 50.5, 51.0, fill=50.0), "counterevidence", {}),
        ("pmi_prices", "stage_ii", year(48.0, 48.5, 49.0, fill=50.0), "support", {}),
        (
            "pmi_prices",
            "stage_ii",
            year(50.2, 50.5, 51.0, fill=50.0),
            "observation_only",
            {"turn_hint": "stage_iii"},
        ),
        ("pmi_prices", "stage_iii", year(51.0, 51.0, 50.5, fill=50.0), "support", {}),
        ("pmi_prices", "stage_iii", year(50.5, 50.0, 49.5, fill=50.0), "observation_only", _GRACE),
        ("pmi_prices", "stage_iv", year(50.2, 50.5, 51.0, fill=50.0), "support", {}),
        ("pmi_prices", "stage_iv", year(51.0, 51.5, 51.2, fill=50.0), "observation_only", {}),
        ("pmi_prices", "stage_v", year(51.0, 50.5, 50.2, fill=50.0), "support", {}),
        (
            "pmi_prices",
            "stage_v",
            year(50.5, 50.0, 49.5, fill=50.0),
            "observation_only",
            {"turn_hint": "stage_vi"},
        ),
        ("pmi_prices", "stage_vi", year(49.0, 48.5, 48.0, fill=50.0), "support", {}),
        ("pmi_prices", "stage_vi", year(50.2, 50.5, 51.0, fill=50.0), "observation_only", _GRACE),
        # M1, leading.
        ("money", "stage_i", year(2.0, 1.8, 1.5, fill=2.0), "support", {}),
        ("money", "stage_i", year(1.0, 1.0, 1.0, fill=3.0), "support", {"position": "low"}),
        ("money", "stage_i", year(1.5, 1.8, 2.0, fill=2.0), "observation_only", _GRACE),
        ("money", "stage_ii", year(1.0, 1.0, 1.0, fill=1.0), "support", {}),
        ("money", "stage_ii", year(2.0, 1.8, 1.5, fill=2.0), "observation_only", _GRACE),
        ("money", "stage_iii", year(1.0, 1.5, 2.0, fill=1.0), "support", {}),
        ("money", "stage_iv", year(5.0, 5.2, 5.1, fill=2.0), "support", {"position": "high"}),
        (
            "money",
            "stage_iv",
            year(3.5, 3.2, 3.0, fill=4.0),
            "observation_only",
            {"turn_hint": "stage_v"},
        ),
        ("money", "stage_v", year(5.0, 4.5, 4.0, fill=5.0), "support", {}),
        ("money", "stage_v", year(4.0, 4.5, 5.0, fill=5.0), "observation_only", {}),
        ("money", "stage_vi", year(5.0, 4.5, 4.0, fill=5.0), "support", {}),
        ("money", "stage_vi", year(4.0, 4.5, 5.0, fill=5.0), "observation_only", {}),
        # Social financing's official stock growth, leading.
        ("social_financing", "stage_i", year(8.5, 8.3, 8.0, fill=8.5), "support", {}),
        (
            "social_financing",
            "stage_i",
            year(8.0, 8.0, 8.0, fill=9.0),
            "support",
            {"position": "low"},
        ),
        (
            "social_financing",
            "stage_i",
            year(8.0, 8.0, 8.0, fill=7.0),
            "observation_only",
            {"turn_hint": "stage_ii"},
        ),
        ("social_financing", "stage_ii", year(8.0, 8.1, 8.2, fill=8.0), "support", {}),
        # Slowing as much as it usually moves is no marked slowing: within grace, observed.
        ("social_financing", "stage_ii", ZIGZAG, "observation_only", {"grace": None}),
        ("social_financing", "stage_iii", year(8.0, 8.2, 8.5, fill=8.0), "support", {}),
        (
            "social_financing",
            "stage_iii",
            year(8.5, 8.2, 8.0, fill=8.0),
            "observation_only",
            _GRACE,
        ),
        (
            "social_financing",
            "stage_iv",
            year(9.5, 9.4, 9.3, fill=8.0),
            "support",
            {"position": "high"},
        ),
        (
            "social_financing",
            "stage_iv",
            ZIGZAG,
            "observation_only",
            {"turn_hint": "stage_v", "position": "low"},
        ),
        # Quickening less is slowing enough for stage V (J3).
        ("social_financing", "stage_v", year(8.0, 8.5, 8.7, fill=8.0), "support", {}),
        ("social_financing", "stage_v", year(8.0, 8.2, 8.6, fill=8.0), "observation_only", _GRACE),
        ("social_financing", "stage_vi", year(8.5, 8.2, 8.0, fill=8.0), "support", {}),
        (
            "social_financing",
            "stage_vi",
            year(8.0, 8.0, 8.0, fill=8.0),
            "observation_only",
            {"turn_hint": "stage_i"},
        ),
    ],
)
def test_each_stage_reads_each_monthly_indicator_against_its_cells(
    tmp_path: Path,
    key: str,
    stage: str,
    values: tuple[float, ...],
    relation: str,
    extra: dict[str, Any],
) -> None:
    item = read(tmp_path, key, stage, values)

    assert item["relation"] == relation, item
    assert item["proposition"]
    assert item["consistency"] == "consistent"
    main = item["members"][0]
    assert main["role"] == "main"
    for name, expected in extra.items():
        actual = main[name] if name in {"position", "level", "momentum"} else item[name]
        assert actual == expected, name


def test_the_counts_cover_overheat_price_and_credit_and_no_derived_value(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "money", year(2.0, 1.8, 1.5, fill=2.0))
    seed(repository, "ppi", year(-1.0, -1.2, -1.5, fill=-1.0))

    context = project(repository, FormalStage.STAGE_I)

    dimensions = {
        item["dimension"]: item
        for item in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
    }
    keys = {name: [i["key"] for i in item["key_indicators"]] for name, item in dimensions.items()}
    assert keys == {
        "policy": [],
        "credit": ["social_financing", "money"],
        "overheat": ["pmi", "industrial_va"],
        "price": ["ppi", "cpi", "pmi_prices"],
        "inventory": [],
    }
    assert dimensions["credit"]["counts"]["support"] == 1
    assert dimensions["credit"]["counts"]["unconfirmed"] == 1
    assert dimensions["price"]["counts"]["support"] == 1
    assert dimensions["price"]["counts"]["unconfirmed"] == 2
    assert sum(dimensions["overheat"]["counts"].values()) == 2
    # M1-M2 is shown under M1/M2 with its formula; it is no member and counts nothing.
    money = indicator(context, "money")
    [spread] = money["derived"]
    assert spread["label"] == "M1−M2" and spread["counted"] is False
    assert spread["formula_version"] == "m1-m2-yoy-spread-v0001"
    assert spread["value"] == pytest.approx(0.0) and spread["inputs"] == ["m1", "m2"]
    assert [member["name"] for member in money["members"]] == ["m1", "m2"]


def test_social_financing_held_up_by_government_bonds_alone_is_only_observed(
    tmp_path: Path,
) -> None:
    # Stage II: the total steadies upward on government bonds, not one other component
    # rising (they hold, renminbi loans slow): capped, and split too (user, 2026-10-07).
    flat, slowing = year(6.0, 6.0, 6.0, fill=6.0), year(6.2, 6.1, 6.0, fill=6.2)
    item = read(
        tmp_path,
        "social_financing",
        "stage_ii",
        year(8.0, 8.1, 8.2, fill=8.0),
        auxiliary={i: flat for i in NON_GOVERNMENT} | {2: slowing},
    )

    assert item["relation"] == "observation_only"
    assert "实体传导未确认" in item["notes"]
    assert item["capped_by"] == ["实体传导未确认"]
    assert item["divergence_capped"] is True  # renminbi loans slowing against the total
    names = [member["name"] for member in item["members"]]
    assert names[1:9] == [
        "government_bonds",
        "renminbi_loans",
        "foreign_currency_loans_rmb",
        "entrusted_loans",
        "trust_loans",
        "undiscounted_bank_acceptances",
        "corporate_bonds",
        "nonfinancial_enterprise_equity",
    ]


def test_government_bonds_alone_without_a_split_is_still_capped(tmp_path: Path) -> None:
    flat = year(6.0, 6.0, 6.0, fill=6.0)
    item = read(
        tmp_path,
        "social_financing",
        "stage_iii",
        year(8.0, 8.2, 8.5, fill=8.0),
        auxiliary={i: flat for i in NON_GOVERNMENT},
    )

    assert item["divergence_capped"] is False
    assert item["capped_by"] == ["实体传导未确认"]
    assert item["relation"] == "observation_only"


def test_one_non_government_component_rising_is_no_government_bonds_alone(
    tmp_path: Path,
) -> None:
    flat = year(6.0, 6.0, 6.0, fill=6.0)
    item = read(
        tmp_path,
        "social_financing",
        "stage_ii",
        year(8.0, 8.1, 8.2, fill=8.0),
        auxiliary={i: flat for i in NON_GOVERNMENT if i != 7},
    )

    assert item["capped_by"] == [] and item["notes"] == []
    assert item["relation"] == "support"


def test_social_financing_with_every_member_rising_supports_without_the_note(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, "social_financing", "stage_ii", year(8.0, 8.1, 8.2, fill=8.0))

    assert item["relation"] == "support"
    assert item["notes"] == [] and item["capped_by"] == []
    assert item["consistency"] == "consistent"


def test_social_financing_without_its_official_stock_growth_is_unconfirmed(
    tmp_path: Path,
) -> None:
    # The components are held, the official growth of the total is not.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for metric_id, dimensions, unit in INDICATORS["social_financing"][1:]:
        append(repository, metric_id, dimensions, year(6.0, 6.1, 6.2, fill=6.0), unit=unit)

    item = indicator(project(repository, FormalStage.STAGE_II), "social_financing")

    assert item["relation"] == "unconfirmed"
    assert item["missing"] and item["missing"][0].startswith("measure=stock_yoy:")


def test_a_month_short_of_the_year_leaves_the_indicator_unconfirmed(tmp_path: Path) -> None:
    values: list[float | None] = list(year(2.0, 1.8, 1.5, fill=2.0))
    values[3] = None
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for metric_id, dimensions, unit in INDICATORS["money"]:
        append(repository, metric_id, dimensions, tuple(values), unit=unit)

    item = indicator(project(repository, FormalStage.STAGE_I), "money")

    assert item["relation"] == "unconfirmed"
    assert item["missing"] == [f"aggregate=m1,measure=yoy:{YEAR[3]}"]


def test_high_low_and_marked_read_a_year_and_nothing_before_it(tmp_path: Path) -> None:
    # A value far above the year in the month before it would make August low, and its
    # rises small: it is not read.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    main, m2 = INDICATORS["money"]
    values = (3.0, 3.1, 3.0, 3.1, 3.0, 3.1, 3.0, 3.1, 3.0, 3.1, 3.0, 4.0)
    append(repository, main[0], main[1], (20.0, 20.0, *values), months=(*BEFORE, *YEAR))
    append(repository, m2[0], m2[1], values)

    item = indicator(project(repository, FormalStage.STAGE_IV), "money")

    m1 = item["members"][0]
    assert m1["periods"] == [
        f"{month}-{calendar.monthrange(int(month[:4]), int(month[5:]))[1]:02d}" for month in YEAR
    ]
    assert m1["position"] == "high"
    assert m1["change_size"] == "marked"
    assert item["relation"] == "support"


def test_industrial_value_added_passes_over_january_and_reads_february_cumulatively(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, "industrial_va", "stage_iii", year(5.0, 5.2, 5.5, fill=5.0))

    main = item["members"][0]
    periods = [period[:7] for period in main["periods"]]
    assert "2026-01" not in periods and "2026-02" in periods and len(periods) == 11
    assert main["missing"] == []
    # February is read from the January-February cumulative growth, and says so.
    assert main["stand_ins"] == [{"period": "2026-02-28", "label": "1—2 月累计同比（累计口径）"}]
    assert item["relation"] == "support"


def test_ppi_month_on_month_turning_up_hints_at_stage_iii(tmp_path: Path) -> None:
    # Stage II: the year-on-year still falls while the month-on-month turns up.
    item = read(
        tmp_path,
        "ppi",
        "stage_ii",
        year(-1.0, -1.2, -1.5, fill=-1.0),
        auxiliary={1: year(-0.4, -0.3, -0.1, fill=-0.2)},
    )

    assert item["notes"] == ["环比开始回升"]
    assert item["turn_hint"] == "stage_iii"
    # Against a falling year-on-year it is a split: observed only.
    assert item["relation"] == "observation_only" and item["divergence_capped"] is True


def test_core_cpi_not_falling_is_noted_in_stage_i(tmp_path: Path) -> None:
    item = read(
        tmp_path,
        "cpi",
        "stage_i",
        year(1.0, 0.8, 0.5, fill=1.0),
        auxiliary={1: year(0.8, 0.8, 0.8, fill=0.8)},
    )

    assert item["relation"] == "support"
    assert item["notes"] == ["核心 CPI 黏性（滞后未转）"]


@pytest.mark.parametrize(
    ("stage", "relation"), [("stage_i", "counterevidence"), ("stage_ii", "observation_only")]
)
def test_ppi_rising_on_by_equal_steps_is_rising_on(
    tmp_path: Path, stage: str, relation: str
) -> None:
    item = read(tmp_path, "ppi", stage, year(-3.0, -2.0, -1.0, fill=-3.0))

    assert item["members"][0]["run"] == "up" and item["members"][0]["slope"] == "flat"
    assert item["relation"] == relation


def test_social_financing_quickening_markedly_in_stage_i_still_hints_at_stage_ii(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, "social_financing", "stage_i", year(8.0, 8.1, 8.5, fill=8.0))

    assert item["members"][0]["change_size"] == "marked"
    assert item["relation"] == "observation_only" and item["grace"] == "not_evaluated"
    assert item["turn_hint"] == "stage_ii"


def test_a_government_bond_member_out_of_date_caps_nothing(tmp_path: Path) -> None:
    # Government bonds last held in May, rising then: out of date, they say nothing now.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    main, government, *others = INDICATORS["social_financing"]
    append(repository, main[0], main[1], year(8.0, 8.1, 8.2, fill=8.0))
    append(
        repository,
        government[0],
        government[1],
        year(5.0, 6.0, 7.0, fill=5.0)[:-3],
        months=YEAR[:-3],
    )
    for metric_id, dimensions, unit in others:
        append(repository, metric_id, dimensions, year(6.0, 6.0, 6.0, fill=6.0), unit=unit)

    item = indicator(project(repository, FormalStage.STAGE_II), "social_financing")

    assert item["members"][1]["evidence_status"] == "stale"
    assert item["capped_by"] == [] and "实体传导未确认" not in item["notes"]
    assert item["relation"] == "support"


def test_government_bonds_flat_with_the_rest_slowing_is_a_split_not_the_cap(
    tmp_path: Path,
) -> None:
    item = read(
        tmp_path,
        "social_financing",
        "stage_ii",
        year(8.0, 8.1, 8.2, fill=8.0),
        auxiliary={1: year(6.0, 6.0, 6.0, fill=6.0)}
        | {i: year(6.2, 6.1, 6.0, fill=6.2) for i in NON_GOVERNMENT},
    )

    assert item["capped_by"] == [] and item["divergence_capped"] is True
    assert item["relation"] == "observation_only"


def test_a_monthly_flow_less_than_a_year_before_splits_from_a_quickening_stock(
    tmp_path: Path,
) -> None:
    # July's flow 100 against 150 the July before: less, while the stock growth quickens.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "social_financing", year(8.0, 8.1, 8.2, fill=8.0))
    ytd = {"measure": "ytd_increment"}
    unit = "hundred_million_cny"
    months = ("2025-07", "2025-08", "2026-07", "2026-08")
    append(
        repository, "CN_SF_TOTAL", ytd, (1000.0, 1150.0, 900.0, 1000.0), months=months, unit=unit
    )

    item = indicator(project(repository, FormalStage.STAGE_II), "social_financing")

    flow = next(member for member in item["members"] if member["name"] == "monthly_increment")
    assert flow["values"] == pytest.approx([-50.0])
    assert flow["direction"] == "down" and flow["consistency"] == "opposes"
    assert item["relation"] == "observation_only" and item["divergence_capped"] is True


def test_m1_less_m2_is_the_difference_of_the_same_month(tmp_path: Path) -> None:
    item = read(
        tmp_path,
        "money",
        "stage_v",
        year(5.0, 4.5, 4.0, fill=5.0),
        auxiliary={1: year(7.0, 7.2, 7.5, fill=7.0)},
    )

    [spread] = item["derived"]
    assert spread["values"][-3:] == pytest.approx([-2.0, -2.7, -3.5])
    assert spread["momentum"] == "down" and spread["period"] == "2026-08-31"
    # M2 rising against a falling M1 is a split; the spread itself splits nothing.
    assert item["consistency"] == "divergent"


def test_januarys_flow_is_its_own_total_and_needs_no_december() -> None:
    # Two Januaries' year-to-date totals, no December held: 100 against 150, less.
    held = {"2026-01": 100.0, "2025-01": 150.0}

    def value(item: DerivedInput, month: str) -> tuple[float, str] | None:
        return (held[month], f"claim:{month}") if month in held else None

    points, missing, inputs = derived_points(
        "sf-monthly-increment-yoy-change-v0001", ["2026-01"], value
    )

    assert points == (("2026-01-31", -50.0, "sf-monthly-increment-yoy-change-v0001"),)
    assert missing == () and set(inputs) == {"claim:2026-01", "claim:2025-01"}
    # A month after January takes the month before it: March's is held, February's not.
    held.update({"2026-03": 300.0, "2025-03": 320.0})
    _points, missing, _inputs = derived_points(
        "sf-monthly-increment-yoy-change-v0001", ["2026-03"], value
    )
    assert missing == ("2026-03",)
