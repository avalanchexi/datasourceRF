"""The credit impulse module: its lookback, its reading of the inputs, and its arithmetic."""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle import credit_impulse
from pring_cycle.catalog import metric_definition
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.freshness import FRESHNESS_REGISTRY, release_at
from pring_cycle.retrieval import preceding_periods
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.trading_calendar import current_calendar
from tests.integration.test_context_projection import _certified_claim

VERSION = "metric-catalog-v0002"
AS_OF = datetime(2026, 1, 31, tzinfo=UTC)
V1 = "credit-impulse-v0001"
SHARE = "credit-impulse-rolling-share-v0001"
YTD_FLOW = "credit-impulse-ytd-flow-v0002"
SHANGHAI = ZoneInfo("Asia/Shanghai")


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


def day_end(day: date) -> datetime:
    return datetime.combine(day, time.max, tzinfo=SHANGHAI)


def needs(version: str | None, cutoff: datetime, **held: frozenset[str]) -> dict[str, Any]:
    result = credit_impulse.minimum_requirements(
        version, public_cutoff=cutoff, calendar=current_calendar(), direct_held=held
    )
    return {
        metric: (periods[0], periods[-1], len(periods))
        for metric, periods in result.periods.items()
    }


@pytest.mark.parametrize(
    ("version", "held_sf", "held_gdp", "day", "expected"),
    [
        # On 2026-09-18 the newest released periods are 2026-08 and 2026-Q2 (ticket 09).
        (V1, 0, 0, date(2026, 9, 18), (("2024-09", 24), ("2024-Q3", 8))),
        (YTD_FLOW, 0, 8, date(2026, 9, 18), (("2024-08", 25), ("2024-Q3", 8))),
        (SHARE, 0, 0, date(2026, 9, 18), (("2024-09", 24), ("2024-Q2", 9))),
        (YTD_FLOW, 0, 0, date(2026, 9, 18), (("2024-08", 25), ("2024-Q2", 9))),
        # Every period held directly, or windows that open a year, need no base period.
        (YTD_FLOW, 24, 8, date(2026, 9, 18), (("2024-09", 24), ("2024-Q3", 8))),
        (YTD_FLOW, 0, 0, date(2027, 2, 1), (("2025-01", 24), ("2025-Q1", 8))),
    ],
)
def test_a_day_needs_a_base_period_only_when_differencing_needs_one(
    version: str,
    held_sf: int,
    held_gdp: int,
    day: date,
    expected: tuple[tuple[str, int], tuple[str, int]],
) -> None:
    held = {
        "CN_SF_TOTAL": frozenset(preceding_periods("2026-08", held_sf) if held_sf else ()),
        "CN_GDP": frozenset(preceding_periods("2026-Q2", held_gdp) if held_gdp else ()),
    }
    result = needs(version, day_end(day), **held)

    assert {metric: (first, count) for metric, (first, _last, count) in result.items()} == {
        "CN_SF_TOTAL": expected[0],
        "CN_GDP": expected[1],
    }


def test_a_day_s_need_ends_at_the_release_rule_not_at_what_is_held() -> None:
    # Held only to 2026-06 / 2026-Q1, the need still ends at what was out (ticket 24).
    held = {
        "CN_SF_TOTAL": frozenset(preceding_periods("2026-06", 24)),
        "CN_GDP": frozenset(preceding_periods("2026-Q1", 8)),
    }
    result = needs(YTD_FLOW, day_end(date(2026, 9, 18)), **held)

    assert result == {
        "CN_SF_TOTAL": ("2024-08", "2026-08", 25),
        "CN_GDP": ("2024-Q2", "2026-Q2", 9),
    }


def test_the_fetch_covers_what_each_day_of_the_window_needs() -> None:
    window = tuple(
        date(2026, 4, 6) + timedelta(days=offset)
        for offset in range(166)
        if (date(2026, 4, 6) + timedelta(days=offset)).weekday() < 5
    )
    cutoff = day_end(window[-1])
    coverage = credit_impulse.fetch_coverage(
        YTD_FLOW, window=window, public_cutoff=cutoff, calendar=current_calendar()
    )

    # The first day reads back to 2024-02 (its window opens 2024-03) and 2024-Q1.
    assert coverage.start("CN_SF_TOTAL") == "2024-02"
    assert coverage.start("CN_GDP") == "2024-Q1"
    assert coverage.periods["CN_SF_TOTAL"][-1] == "2026-08"
    for day in window:
        day_needs = credit_impulse.minimum_requirements(
            YTD_FLOW, public_cutoff=day_end(day), calendar=current_calendar()
        )
        for metric, periods in day_needs.periods.items():
            assert set(periods) <= set(coverage.periods[metric]), (day, metric)


def test_a_formula_turned_off_reads_nothing() -> None:
    cutoff = day_end(date(2026, 9, 18))

    assert (
        credit_impulse.minimum_requirements(
            None, public_cutoff=cutoff, calendar=current_calendar()
        ).periods
        == {}
    )
    assert (
        credit_impulse.fetch_coverage(
            None, window=(date(2026, 9, 18),), public_cutoff=cutoff, calendar=current_calendar()
        ).periods
        == {}
    )
    assert credit_impulse.metrics_off({}) == {"CN_CREDIT_IMPULSE"}
    assert credit_impulse.metrics_off({"credit_impulse": YTD_FLOW}) == frozenset()


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


WINDOW = tuple(
    day
    for day in (date(2026, 4, 6) + timedelta(days=offset) for offset in range(166))
    if day.weekday() < 5
)


def released_inputs(repository: EvidenceRepository, coverage: Any) -> None:
    """Year-to-date inputs over ``coverage``, each public from its registered release."""
    for metric, periods in coverage.periods.items():
        rule = FRESHNESS_REGISTRY[metric]
        for period in periods:
            if metric == "CN_GDP":
                year, quarter = (int(part) for part in period.split("-Q"))
                end, start, value = month_end(year, quarter * 3), f"{year}-01-01", 25.0 * quarter
                dimensions = {"aggregate": "total", "measure": "nominal_ytd_level"}
            else:
                year, month = (int(part) for part in period.split("-"))
                end, start, value = month_end(year, month), f"{period}-01", 2.0 * month
                dimensions = {"measure": "ytd_increment"}
            known = release_at(rule, date.fromisoformat(end), current_calendar())
            claim = _certified_claim(
                metric_id=metric,
                period_start=start,
                period_end=end,
                dimensions=dimensions,
                value=value,
                unit="hundred_million_cny",
            )
            repository.append_source_claim(
                replace(
                    claim,
                    release_at=known,
                    public_available_at=known,
                    fetched_at=known,
                    available_at=known,
                )
            )


@pytest.mark.parametrize("held", ["window", "target_day"])
def test_the_window_s_first_day_derives_from_what_the_fetch_covers(
    repository: EvidenceRepository, held: str
) -> None:
    # Measured before ticket 24: inputs for the target day alone leave 115 of 120 backfilled
    # days without the impulse; covering the window derives every one.
    cutoff = day_end(WINDOW[-1])
    coverage = (
        credit_impulse.fetch_coverage(
            YTD_FLOW, window=WINDOW, public_cutoff=cutoff, calendar=current_calendar()
        )
        if held == "window"
        else credit_impulse.minimum_requirements(
            YTD_FLOW, public_cutoff=cutoff, calendar=current_calendar()
        )
    )
    released_inputs(repository, coverage)

    def status(day: date) -> str:
        return credit_impulse.derive(
            repository,
            YTD_FLOW,
            as_of=day_end(day),
            as_of_mode=AsOfMode.PUBLIC,
            definition_version=VERSION,
        ).status

    assert status(WINDOW[-1]) == "available"
    assert status(WINDOW[0]) == ("available" if held == "window" else "missing_inputs")


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


def test_a_direct_reading_with_an_unusable_point_gives_way_to_a_complete_ytd_one(
    repository: EvidenceRepository,
) -> None:
    # Counted by claims held, the direct quarters were taken and then refused (ticket 26).
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_ytd_level")
    for year in (2024, 2025):
        for quarter in range(1, 5):
            claim = _certified_claim(
                metric_id="CN_GDP",
                period_start=f"{year:04d}-{quarter * 3 - 2:02d}-01",
                period_end=month_end(year, quarter * 3),
                dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                value=30.0,
                unit="hundred_million_cny",
            )
            if (year, quarter) == (2025, 2):
                claim = replace(claim, quality_status="unverified")
            repository.append_source_claim(claim)

    result = derive(repository, SHARE)

    assert result.status == "available"
    assert result.gdp_input_measure == "nominal_ytd_level"
    assert result.value == pytest.approx(EXPECTED)


def test_a_newer_ytd_reading_wins_over_an_older_direct_one(
    repository: EvidenceRepository,
) -> None:
    # Direct flows end a month earlier (2023-12 to 2025-11) than the year-to-date ones.
    for index in range(24):
        year, month = 2023 + (index + 11) // 12, (index + 11) % 12 + 1
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_SF_TOTAL",
                period_start=f"{year:04d}-{month:02d}-01",
                period_end=month_end(year, month),
                dimensions={"measure": "monthly_increment"},
                value=9.0,
                unit="hundred_million_cny",
            )
        )
    social_financing(repository, "ytd_increment")
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, YTD_FLOW)

    assert result.status == "available"
    assert result.social_financing_window == ("2024-01-01", "2025-12-31")
    assert result.value == pytest.approx(EXPECTED)


def test_on_the_same_end_the_direct_reading_wins(repository: EvidenceRepository) -> None:
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_quarterly_level")
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, SHARE)

    assert result.status == "available"
    assert result.gdp_input_measure == "nominal_quarterly_level"


@pytest.mark.parametrize("unusable", [None, (2025, 2)])
def test_the_plan_asks_for_a_base_period_by_the_rule_the_derivation_reads_by(
    repository: EvidenceRepository, unusable: tuple[int, int] | None
) -> None:
    # Direct quarters 2024-Q2 to 2026-Q1; one not usable sends GDP to its year-to-date
    # reading, which differences 2024-Q2 from 2024-Q1 (ticket 26).
    for year, quarter in (
        [(2024, q) for q in (2, 3, 4)] + [(2025, q) for q in (1, 2, 3, 4)] + [(2026, 1)]
    ):
        claim = _certified_claim(
            metric_id="CN_GDP",
            period_start=f"{year:04d}-{quarter * 3 - 2:02d}-01",
            period_end=month_end(year, quarter * 3),
            dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
            value=30.0,
            unit="hundred_million_cny",
        )
        if (year, quarter) == unusable:
            claim = replace(claim, quality_status="unverified")
        repository.append_source_claim(claim)
    selector = SimpleNamespace(
        series=lambda metric: repository.metric_series(
            metric, mode=AsOfMode.SYSTEM, as_of=AS_OF, definition_version=VERSION
        )
    )
    held = credit_impulse.direct_periods(selector)

    result = needs(SHARE, day_end(date(2026, 4, 30)), **held)

    assert result["CN_GDP"][:2] == (("2024-Q1", "2026-Q1") if unusable else ("2024-Q2", "2026-Q1"))


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
