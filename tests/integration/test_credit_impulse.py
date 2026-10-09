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
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState
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
TWELVE_MONTH = "credit-impulse-12m-flow-share-v0003"
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
        # Twelve months and the month before them, four quarters (ticket 25).
        (TWELVE_MONTH, 0, 0, date(2026, 9, 18), (("2025-07", 14), ("2025-Q2", 5))),
        (TWELVE_MONTH, 0, 0, date(2027, 2, 1), (("2025-11", 14), ("2026-Q1", 4))),
        (TWELVE_MONTH, 13, 4, date(2026, 9, 18), (("2025-08", 13), ("2025-Q3", 4))),
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


@pytest.mark.parametrize(
    ("version", "held_sf", "expected"),
    [
        # Read directly when the version may not difference, or every period is held so;
        # else from year-to-date figures, base period and all (lookback fetch gaps 16).
        (V1, 0, ("monthly_increment", "nominal_quarterly_level")),
        (SHARE, 0, ("monthly_increment", "nominal_ytd_level")),
        (TWELVE_MONTH, 0, ("ytd_increment", "nominal_ytd_level")),
        (TWELVE_MONTH, 13, ("monthly_increment", "nominal_ytd_level")),
    ],
)
def test_a_day_s_minimum_is_read_by_the_measure_its_rule_reads_it_by(
    version: str, held_sf: int, expected: tuple[str, str]
) -> None:
    held = {"CN_SF_TOTAL": frozenset(preceding_periods("2026-08", held_sf) if held_sf else ())}
    minimum = credit_impulse.minimum_requirements(
        version,
        public_cutoff=day_end(date(2026, 9, 18)),
        calendar=current_calendar(),
        direct_held=held,
    )

    members = credit_impulse.minimum_members(version, minimum, held)

    assert members == {
        "CN_SF_TOTAL": f'CN_SF_TOTAL:{{"measure": "{expected[0]}"}}',
        "CN_GDP": f'CN_GDP:{{"aggregate": "total", "measure": "{expected[1]}"}}',
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


SF_MONTHLY = 'CN_SF_TOTAL:{"measure": "monthly_increment"}'
SF_YTD = 'CN_SF_TOTAL:{"measure": "ytd_increment"}'
GDP_QUARTERLY = 'CN_GDP:{"aggregate": "total", "measure": "nominal_quarterly_level"}'
GDP_YTD_MEMBER = 'CN_GDP:{"aggregate": "total", "measure": "nominal_ytd_level"}'


def reasons(result: Any) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
    return [(f.metric_id, f.reason, f.periods, f.members) for f in result.failures]


def ytd_months(repository: EvidenceRepository, months: list[tuple[int, int]]) -> None:
    for year, month in months:
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_SF_TOTAL",
                period_start=f"{year:04d}-{month:02d}-01",
                period_end=month_end(year, month),
                dimensions={"measure": "ytd_increment"},
                value=2.0 * month,
                unit="hundred_million_cny",
            )
        )


def test_both_parents_short_are_told_at_once(repository: EvidenceRepository) -> None:
    # GDP used to be asked first and hid social financing's gap (ticket 28).
    social_financing(repository, "monthly_increment", skip=(2025, 3))
    gdp(repository, "nominal_quarterly_level", skip=(2024, 2))

    result = derive(repository, V1)

    assert result.status == "missing_inputs"
    assert reasons(result) == [
        ("CN_SF_TOTAL", "missing_periods", ("2025-03",), (SF_MONTHLY,)),
        ("CN_GDP", "missing_periods", ("2024-Q2",), (GDP_QUARTERLY,)),
    ]


def test_a_window_without_its_base_names_the_base_period(
    repository: EvidenceRepository,
) -> None:
    # 2024-02 to 2026-01 differenced needs 2024-01 to subtract from.
    ytd_months(repository, [(2024 + (m - 1) // 12, (m - 1) % 12 + 1) for m in range(2, 26)])
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, YTD_FLOW)

    assert result.status == "missing_inputs"
    assert reasons(result) == [
        ("CN_SF_TOTAL", "base_period_missing", ("2024-01",), (SF_MONTHLY, SF_YTD))
    ]


def test_a_newest_figure_that_cannot_be_differenced_is_not_aligned(
    repository: EvidenceRepository,
) -> None:
    ytd_months(
        repository,
        [
            (year, month)
            for year in (2023, 2024, 2025)
            for month in range(1, 13)
            if (year, month) != (2025, 11)
        ],
    )
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, YTD_FLOW)

    assert reasons(result) == [
        ("CN_SF_TOTAL", "missing_periods", ("2025-11",), (SF_MONTHLY, SF_YTD)),
        ("CN_SF_TOTAL", "latest_not_aligned", ("2025-12",), (SF_MONTHLY, SF_YTD)),
    ]


def test_a_period_held_without_a_value_or_not_usable_is_named(
    repository: EvidenceRepository,
) -> None:
    social_financing(repository, "monthly_increment", skip=(2025, 5))
    repository.append_source_claim(
        replace(
            _certified_claim(
                metric_id="CN_SF_TOTAL",
                period_start="2025-05-01",
                period_end=month_end(2025, 5),
                dimensions={"measure": "monthly_increment"},
                value=3.0,
                unit="hundred_million_cny",
            ),
            value=None,
            value_state=EvidenceValueState.NOT_DISCLOSED,
        )
    )
    gdp(repository, "nominal_quarterly_level", skip=(2025, 2))
    repository.append_source_claim(
        replace(
            _certified_claim(
                metric_id="CN_GDP",
                period_start="2025-04-01",
                period_end=month_end(2025, 6),
                dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                value=30.0,
                unit="hundred_million_cny",
            ),
            quality_status="unverified",
        )
    )

    result = derive(repository, V1)

    assert reasons(result) == [
        ("CN_SF_TOTAL", "value_missing", ("2025-05",), (SF_MONTHLY,)),
        ("CN_GDP", "parent_unusable", ("2025-Q2",), (GDP_QUARTERLY,)),
    ]


def test_figures_the_version_may_not_difference_are_named(
    repository: EvidenceRepository,
) -> None:
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, V1)

    ((metric, reason, periods, members),) = reasons(result)
    assert (metric, reason, members) == ("CN_GDP", "differencing_not_allowed", (GDP_QUARTERLY,))
    assert periods == preceding_periods("2025-Q4", 8)


def test_a_difference_refused_with_both_figures_held_is_no_missing_base(
    repository: EvidenceRepository,
) -> None:
    # 2025's second year-to-date level falls below its first: Q2 is held, its base too.
    social_financing(repository, "monthly_increment")
    for year, cumulative in {2024: GDP_YTD[2024], 2025: (25.0, 20.0, 90.0, 130.0)}.items():
        for quarter, level in enumerate(cumulative, start=1):
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_GDP",
                    period_start=f"{year:04d}-01-01",
                    period_end=month_end(year, quarter * 3),
                    dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
                    value=level,
                    unit="hundred_million_cny",
                )
            )

    result = derive(repository, SHARE)

    assert reasons(result) == [
        ("CN_GDP", "invalid_difference", ("2025-Q2",), (GDP_QUARTERLY, GDP_YTD_MEMBER))
    ]


def test_periods_read_by_different_measures_do_not_join(repository: EvidenceRepository) -> None:
    # 2024 only as year-to-date levels, 2025 only as quarterly ones: four quarters each.
    social_financing(repository, "monthly_increment")
    for quarter, level in enumerate(GDP_YTD[2024], start=1):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_GDP",
                period_start="2024-01-01",
                period_end=month_end(2024, quarter * 3),
                dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
                value=level,
                unit="hundred_million_cny",
            )
        )
    for quarter in range(1, 5):
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_GDP",
                period_start=f"2025-{quarter * 3 - 2:02d}-01",
                period_end=month_end(2025, quarter * 3),
                dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
                value=30.0,
                unit="hundred_million_cny",
            )
        )

    result = derive(repository, SHARE)

    assert result.status == "missing_inputs"
    assert reasons(result) == [
        (
            "CN_GDP",
            "measures_do_not_join",
            preceding_periods("2025-Q4", 8),
            (GDP_QUARTERLY, GDP_YTD_MEMBER),
        )
    ]


def test_a_figure_the_version_may_not_read_does_not_move_the_window(
    repository: EvidenceRepository,
) -> None:
    # Direct quarters to 2025-Q4 lacking 2024-Q2; a 2026-Q2 year-to-date level V1 never reads.
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_quarterly_level", skip=(2024, 2))
    repository.append_source_claim(
        _certified_claim(
            metric_id="CN_GDP",
            period_start="2026-01-01",
            period_end="2026-06-30",
            dimensions={"aggregate": "total", "measure": "nominal_ytd_level"},
            value=60.0,
            unit="hundred_million_cny",
        )
    )

    result = derive(repository, V1)

    assert reasons(result) == [("CN_GDP", "missing_periods", ("2024-Q2",), (GDP_QUARTERLY,))]


TWELVE_MONTH_VALUE = 100 * 36 / 130


@pytest.mark.parametrize(
    ("social_measure", "gdp_measure"),
    [
        ("monthly_increment", "nominal_quarterly_level"),
        ("ytd_increment", "nominal_quarterly_level"),
        ("monthly_increment", "nominal_ytd_level"),
    ],
)
def test_the_twelve_month_impulse_is_the_year_s_flow_share_of_gdp(
    repository: EvidenceRepository, social_measure: str, gdp_measure: str
) -> None:
    # 2025's flows of 3 a month over its four quarters of 130; December 2024 gives the
    # month a year before, and either input may be differenced (ticket 25).
    social_financing(repository, social_measure)
    gdp(repository, gdp_measure)

    result = derive(repository, TWELVE_MONTH)

    assert result.status == "available"
    assert result.value == pytest.approx(TWELVE_MONTH_VALUE)
    assert (result.unit, result.direction) == ("percent", "up")
    assert result.social_financing_window == ("2024-12-01", "2025-12-31")
    assert result.gdp_window == ("2025-01-01", "2025-12-31")
    assert result.formula == "100 * rolling_12m_social_financing / rolling_4q_nominal_gdp"


def test_a_new_gdp_quarter_moves_the_value_not_the_direction(
    repository: EvidenceRepository,
) -> None:
    # The month's flow against the same month a year before decides; a new quarter of
    # GDP only changes the denominator both share (ticket 25).
    social_financing(repository, "monthly_increment")
    gdp(repository, "nominal_quarterly_level")
    before = derive(repository, TWELVE_MONTH)
    repository.append_source_claim(
        _certified_claim(
            metric_id="CN_GDP",
            period_start="2026-01-01",
            period_end="2026-03-31",
            dimensions={"aggregate": "total", "measure": "nominal_quarterly_level"},
            value=1000.0,
            unit="hundred_million_cny",
        )
    )

    after = derive(repository, TWELVE_MONTH)

    assert (before.direction, after.direction) == ("up", "up")
    assert after.value == pytest.approx(100 * 36 / (30 + 35 + 40 + 1000))


def test_the_twelve_month_impulse_short_of_a_month_names_it(
    repository: EvidenceRepository,
) -> None:
    # Without December 2024 the last thirteen months held skip from November to January.
    social_financing(repository, "monthly_increment", skip=(2024, 12))
    gdp(repository, "nominal_quarterly_level")

    result = derive(repository, TWELVE_MONTH)

    assert result.status == "nonconsecutive_social_financing_inputs"
    assert result.unit == "percent"
    assert reasons(result) == [
        ("CN_SF_TOTAL", "missing_periods", ("2024-12",), (SF_MONTHLY, SF_YTD))
    ]


def test_a_positive_share_can_still_slow_down(repository: EvidenceRepository) -> None:
    # December 2025's flow of 1 falls short of December 2024's 2, whatever the share.
    for year, month, flow in [(2024, 12, 2.0)] + [
        (2025, month, 1.0 if month == 12 else 3.0) for month in range(1, 13)
    ]:
        repository.append_source_claim(
            _certified_claim(
                metric_id="CN_SF_TOTAL",
                period_start=f"{year:04d}-{month:02d}-01",
                period_end=month_end(year, month),
                dimensions={"measure": "monthly_increment"},
                value=flow,
                unit="hundred_million_cny",
            )
        )
    gdp(repository, "nominal_quarterly_level")

    result = derive(repository, TWELVE_MONTH)

    assert result.value == pytest.approx(100 * 34 / 130)
    assert result.direction == "down"


def test_equal_differenced_flows_hold_flat_without_a_binary_tail(
    repository: EvidenceRepository,
) -> None:
    # December's flows are 0.3 - 0.2 and 0.4 - 0.3: one tenth both, in decimal.
    for year, levels in {
        2024: [0.01 * month for month in range(1, 11)] + [0.2, 0.3],
        2025: [0.02 * month for month in range(1, 11)] + [0.3, 0.4],
    }.items():
        for month, level in enumerate(levels, start=1):
            repository.append_source_claim(
                _certified_claim(
                    metric_id="CN_SF_TOTAL",
                    period_start=f"{year:04d}-{month:02d}-01",
                    period_end=month_end(year, month),
                    dimensions={"measure": "ytd_increment"},
                    value=level,
                    unit="hundred_million_cny",
                )
            )
    gdp(repository, "nominal_ytd_level")

    assert derive(repository, TWELVE_MONTH).direction == "flat"


def test_the_two_year_versions_keep_their_unit_and_direction(
    repository: EvidenceRepository,
) -> None:
    social_financing(repository, "ytd_increment")
    gdp(repository, "nominal_ytd_level")

    result = derive(repository, YTD_FLOW)

    assert (result.unit, result.direction) == ("percentage_points", "up")
    assert result.formula == credit_impulse.FORMULA


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

    result = derive(repository, YTD_FLOW)

    assert result.status == "nonconsecutive_social_financing_inputs"
    # March cannot be differenced without February, which is told for itself.
    assert reasons(result) == [
        ("CN_SF_TOTAL", "missing_periods", ("2025-02",), (SF_MONTHLY, SF_YTD))
    ]


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

    result = derive(repository, V1)

    assert result.status == "nonconsecutive_gdp_inputs"
    assert reasons(result) == [("CN_GDP", "missing_periods", ("2024-Q3",), (GDP_QUARTERLY,))]


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

    result = derive(repository, V1)

    assert result.status == "invalid_gdp_denominator"
    assert reasons(result) == [
        ("CN_GDP", "invalid_gdp_denominator", preceding_periods("2025-Q4", 8), (GDP_QUARTERLY,))
    ]


def test_an_unconfigured_formula_is_disabled(repository: EvidenceRepository) -> None:
    result = derive(repository, None)

    assert (result.formula_version, result.status, result.value) == (
        None,
        "disabled_by_model",
        None,
    )
