"""The credit impulse module: its lookback, its reading of the inputs, and its arithmetic."""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle import credit_impulse
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from tests.integration.test_context_projection import _certified_claim

VERSION = "metric-catalog-v0002"
AS_OF = datetime(2026, 1, 31, tzinfo=UTC)
V1 = "credit-impulse-v0001"
SHARE = "credit-impulse-rolling-share-v0001"
YTD_FLOW = "credit-impulse-ytd-flow-v0002"


def test_the_impulse_is_the_change_in_rolling_flow_share_of_nominal_gdp() -> None:
    # Moved from tests/domain/test_macro_states with the function.
    result = credit_impulse.calculate(
        current_rolling_social_financing=38.0,
        previous_rolling_social_financing=32.0,
        current_rolling_nominal_gdp=140.0,
        previous_rolling_nominal_gdp=128.0,
    )

    assert result == pytest.approx(2.1428571428571423)


@pytest.mark.parametrize("denominator", (0.0, -1.0))
@pytest.mark.parametrize("which", ("current", "previous"))
def test_a_nonpositive_gdp_denominator_is_refused(denominator: float, which: str) -> None:
    with pytest.raises(ValueError, match="credit_impulse_gdp_must_be_positive"):
        credit_impulse.calculate(
            current_rolling_social_financing=38.0,
            previous_rolling_social_financing=32.0,
            current_rolling_nominal_gdp=denominator if which == "current" else 140.0,
            previous_rolling_nominal_gdp=denominator if which == "previous" else 128.0,
        )


def test_the_fetch_reads_back_to_the_differencing_baseline() -> None:
    # On 2026-09-18 the newest released periods are 2026-08 and 2026-Q2 (ticket 09).
    assert credit_impulse.lookback_start("CN_SF_TOTAL", "2026-08") == "2024-08"
    assert credit_impulse.lookback_start("CN_GDP", "2026-Q2") == "2024-Q2"


def held(metric_id: str, count: int) -> list[Any]:
    dimensions = (
        {"measure": "monthly_increment"}
        if metric_id == "CN_SF_TOTAL"
        else {"aggregate": "total", "measure": "nominal_quarterly_level"}
    )
    claim = SimpleNamespace(claim_id="claim", quality_status="validated")
    return [
        SimpleNamespace(
            dimensions=dimensions,
            selection_status="selected",
            value_state=EvidenceValueState.REPORTED_VALUE,
            selected_value=1.0,
            selected_claim_id="claim",
            claims=(claim,),
        )
    ] * count


@pytest.mark.parametrize(
    ("version", "held_sf", "held_gdp", "ends", "needs"),
    [
        (V1, 0, 0, ("2026-08", "2026-Q2"), (24, 8)),
        (YTD_FLOW, 0, 8, ("2026-08", "2026-Q2"), (25, 8)),
        (SHARE, 0, 0, ("2026-08", "2026-Q2"), (24, 9)),
        (YTD_FLOW, 0, 0, ("2026-08", "2026-Q2"), (25, 9)),
        # Enough direct periods held, or windows that open a year, need no base period.
        (YTD_FLOW, 24, 8, ("2026-08", "2026-Q2"), (24, 8)),
        (YTD_FLOW, 0, 0, ("2026-12", "2026-Q4"), (24, 8)),
    ],
)
def test_the_plan_asks_for_a_base_period_only_when_differencing_needs_one(
    version: str, held_sf: int, held_gdp: int, ends: tuple[str, str], needs: tuple[int, int]
) -> None:
    selector = SimpleNamespace(
        series=lambda metric: held(metric, held_sf if metric == "CN_SF_TOTAL" else held_gdp)
    )
    periods = {"CN_SF_TOTAL": ends[0], "CN_GDP": ends[1]}

    assert credit_impulse.requirements(version, selector, periods) == {
        "CN_SF_TOTAL": needs[0],
        "CN_GDP": needs[1],
    }


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> EvidenceRepository:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def certified(  # type: ignore[no-untyped-def]
        metric_id: str, *, definition_version: str = VERSION, database_path: Path | None = None
    ):
        definition = metric_definition(
            metric_id, definition_version=definition_version, database_path=database_path
        )
        return replace(definition, certification_status="certified")

    monkeypatch.setattr(evidence_module, "metric_definition", certified)
    return EvidenceRepository(paths.database)


def month_end(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def social_financing(
    repository: EvidenceRepository, measure: str, *, skip: tuple[int, int] | None = None
) -> set[str]:
    """24 monthly flows of 2 (2024) and 3 (2025), or their year-to-date sums from 2023.

    Returns the claims of the window (2024 and 2025), the ones the impulse reads.
    """
    window: set[str] = set()
    first = 2024 if measure == "monthly_increment" else 2023
    for index in range((2026 - first) * 12):
        year, month = first + index // 12, index % 12 + 1
        if (year, month) == skip:
            continue
        flow = 2.0 if year <= 2024 else 3.0
        claim = repository.append_source_claim(
            _certified_claim(
                metric_id="CN_SF_TOTAL",
                period_start=f"{year:04d}-{month:02d}-01",
                period_end=month_end(year, month),
                dimensions={"measure": measure},
                value=flow if measure == "monthly_increment" else flow * month,
                unit="hundred_million_cny",
            )
        )
        if year >= 2024:
            window.add(claim.claim_id)
    return window


GDP_YTD = {2024: (20.0, 45.0, 70.0, 100.0), 2025: (25.0, 55.0, 90.0, 130.0)}


def gdp(
    repository: EvidenceRepository, measure: str, *, skip: tuple[int, int] | None = None
) -> set[str]:
    """Eight quarters (2024, 2025) as year-to-date levels or the quarterly levels they give."""
    claims: set[str] = set()
    for year, cumulative in GDP_YTD.items():
        for quarter, level in enumerate(cumulative, start=1):
            if (year, quarter) == skip:
                continue
            quarterly = level - (cumulative[quarter - 2] if quarter > 1 else 0.0)
            stored = repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_GDP",
                    period_start=(
                        f"{year:04d}-01-01"
                        if measure == "nominal_ytd_level"
                        else f"{year:04d}-{quarter * 3 - 2:02d}-01"
                    ),
                    period_end=month_end(year, quarter * 3),
                    dimensions={"aggregate": "total", "measure": measure},
                    value=level if measure == "nominal_ytd_level" else quarterly,
                    unit="hundred_million_cny",
                )
            )
            claims.add(stored.claim_id)
    return claims


def derive(repository: EvidenceRepository, version: str | None) -> Any:
    return credit_impulse.derive(
        repository, version, as_of=AS_OF, as_of_mode=AsOfMode.SYSTEM, definition_version=VERSION
    )


EXPECTED = 100 * (36 / 130 - 24 / 100)


@pytest.mark.parametrize(
    ("version", "social_measure", "gdp_measure"),
    [
        (V1, "monthly_increment", "nominal_quarterly_level"),
        (SHARE, "monthly_increment", "nominal_ytd_level"),
        (YTD_FLOW, "ytd_increment", "nominal_ytd_level"),
    ],
)
def test_each_version_computes_from_the_inputs_it_may_read(
    repository: EvidenceRepository, version: str, social_measure: str, gdp_measure: str
) -> None:
    # Moved from test_context_projection: flows and levels differenced from year to date.
    parents = social_financing(repository, social_measure) | gdp(repository, gdp_measure)

    result = derive(repository, version)

    assert result.status == "available"
    assert result.value == pytest.approx(EXPECTED)
    assert result.gdp_input_measure == gdp_measure
    assert result.social_financing_window == ("2024-01-01", "2025-12-31")
    assert result.gdp_window[1] == "2025-12-31"
    # January opens its year, so no December before the window is read.
    assert set(result.input_claim_ids) == parents
    assert len(result.input_claim_ids) == len(parents)


def test_a_version_that_may_not_difference_does_not(repository: EvidenceRepository) -> None:
    social_financing(repository, "ytd_increment")
    gdp(repository, "nominal_ytd_level")

    assert derive(repository, V1).status == "missing_inputs"
    assert derive(repository, SHARE).status == "missing_inputs"


def test_a_break_in_the_social_financing_months_stops_the_impulse(
    repository: EvidenceRepository,
) -> None:
    social_financing(repository, "ytd_increment", skip=(2025, 2))
    gdp(repository, "nominal_ytd_level")

    assert derive(repository, YTD_FLOW).status == "nonconsecutive_social_financing_inputs"


def test_a_break_in_the_gdp_quarters_stops_the_impulse(repository: EvidenceRepository) -> None:
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_quarterly_level", skip=(2024, 3))
    # An eighth quarter after the break keeps the count but not the run of quarters.
    repository.append_source_claim(
        _certified_claim(
            metric_id="CN_GDP",
            period_start="2023-10-01",
            period_end="2023-12-31",
            dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
            value=25.0,
            unit="hundred_million_cny",
        )
    )

    assert derive(repository, V1).status == "nonconsecutive_gdp_inputs"


def test_a_gdp_denominator_that_is_not_positive_is_named(repository: EvidenceRepository) -> None:
    social_financing(repository, "monthly_increment")
    for year in (2024, 2025):
        for quarter in range(1, 5):
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_GDP",
                    period_start=f"{year:04d}-{quarter * 3 - 2:02d}-01",
                    period_end=month_end(year, quarter * 3),
                    dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                    value=0.0,
                    unit="hundred_million_cny",
                )
            )

    assert derive(repository, V1).status == "invalid_gdp_denominator"


def test_an_unconfigured_formula_is_disabled(repository: EvidenceRepository) -> None:
    result = derive(repository, None)

    assert (result.formula_version, result.status, result.value) == (
        None,
        "disabled_by_model",
        None,
    )
