"""The credit impulse: how much it reads back, how it reads its inputs, and what it computes.

The impulse is the change in social financing's share of nominal GDP over rolling twelve
months (four quarters): 24 monthly and 8 quarterly periods. Each formula version is a
policy for reading those inputs -- whether nominal GDP may come from year-to-date levels
and social financing from year-to-date increments, each differenced into its periods. A
derivation says why it failed when it does, and which parent claims it stands on.

The periods it reads are answered here as well, from one cutoff: what a day's derivation
needs at least (``minimum_requirements``), and what a window's fetch must cover so every
day in it can be derived (``fetch_coverage``), both ending at the newest periods the
release rules have out by then, not at whatever happens to be held (ticket 24).

Not here: fetching the inputs, whether a parent claim can be adopted (asked of claim
adoption), the derived observation's identity and storage, and freshness labels.

Kept as they are, and so documented here (each has its own ticket): the direct inputs
are counted by held claims rather than usable ones, and a direct and a differenced
reading are not compared by their end; stale inputs still compute (the caller labels
them), and the gap list then counts ``stale_inputs`` as a failed derivation; several
failures are reported as ``missing_inputs``.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from pring_cycle.claim_adoption import ClaimAdoption
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceValueState,
    MetricSeriesPoint,
    selected_claim,
    usable_point,
)
from pring_cycle.official_context import official_gdp_quarters_matching_baselines
from pring_cycle.retrieval import preceding_periods

if TYPE_CHECKING:
    from pring_cycle.trading_calendar import Sessions

FORMULA = (
    "100 * (rolling_12m_social_financing / rolling_4q_nominal_gdp "
    "- prior_rolling_12m_social_financing / prior_rolling_4q_nominal_gdp)"
)
# Twelve months (four quarters) and the twelve (four) before them.
INPUT_PERIODS = {"CN_SF_TOTAL": 24, "CN_GDP": 8}
_SOCIAL_FINANCING = {"measure": "monthly_increment"}
_SOCIAL_FINANCING_YTD = {"measure": "ytd_increment"}
_GDP = {"aggregate": "total", "measure": "nominal_quarterly_level"}
_GDP_YTD = {"aggregate": "total", "measure": "nominal_ytd_level"}


@dataclass(frozen=True)
class _Version:
    """How a formula version may read its inputs besides the direct periods."""

    gdp_from_ytd: bool
    social_financing_from_ytd: bool


VERSIONS = {
    "credit-impulse-v0001": _Version(gdp_from_ytd=False, social_financing_from_ytd=False),
    "credit-impulse-rolling-share-v0001": _Version(
        gdp_from_ytd=True, social_financing_from_ytd=False
    ),
    "credit-impulse-ytd-flow-v0002": _Version(gdp_from_ytd=True, social_financing_from_ytd=True),
}
# A version outside the model's supported set is refused before it gets here.
_DIRECT_ONLY = VERSIONS["credit-impulse-v0001"]

Differenced = list[tuple[MetricSeriesPoint, float, tuple[MetricSeriesPoint, ...]]]


METRIC_ID = "CN_CREDIT_IMPULSE"
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def metrics_off(formula_versions: Mapping[str, str]) -> frozenset[str]:
    """The impulse's metric when the model configures no formula for it, else nothing.

    A model that turns the formula off neither fetches its long lookback nor lists it in
    freshness or the run plan (ticket 24).
    """
    return frozenset() if "credit_impulse" in formula_versions else frozenset({METRIC_ID})


@dataclass(frozen=True)
class InputPeriods:
    """The periods of each parent the impulse reads, oldest first, any base period included.

    Months read ``YYYY-MM`` and quarters ``YYYY-Qn``; a formula turned off reads none.
    """

    periods: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def start(self, metric_id: str) -> str | None:
        periods = self.periods.get(metric_id, ())
        return periods[0] if periods else None

    def counts(self) -> dict[str, int]:
        return {metric_id: len(periods) for metric_id, periods in self.periods.items()}


def latest_released(public_cutoff: datetime, calendar: Sessions) -> dict[str, str]:
    """The newest social financing month and GDP quarter out at ``public_cutoff``."""
    from pring_cycle.freshness import FRESHNESS_REGISTRY, latest_released_period

    month = latest_released_period(FRESHNESS_REGISTRY["CN_SF_TOTAL"], public_cutoff, calendar)
    quarter = latest_released_period(FRESHNESS_REGISTRY["CN_GDP"], public_cutoff, calendar)
    return {
        "CN_SF_TOTAL": f"{month:%Y-%m}",
        "CN_GDP": f"{quarter.year}-Q{(quarter.month - 1) // 3 + 1}",
    }


def minimum_requirements(
    formula_version: str | None,
    *,
    public_cutoff: datetime,
    calendar: Sessions,
    direct_held: Mapping[str, Collection[str]] | None = None,
) -> InputPeriods:
    """The periods a derivation at ``public_cutoff`` reads at least.

    Each window ends at the newest period released by then. An input the version may
    difference from year-to-date figures also needs the period before its window, unless
    the window opens a year or every period of it is held directly (``direct_held``).
    """
    if formula_version is None:
        return InputPeriods()
    if formula_version not in VERSIONS:
        raise ValueError(f"credit_impulse_formula_unknown:{formula_version}")
    version = VERSIONS[formula_version]
    held = direct_held or {}
    differenced = {"CN_SF_TOTAL": version.social_financing_from_ytd, "CN_GDP": version.gdp_from_ytd}
    periods: dict[str, tuple[str, ...]] = {}
    for metric_id, latest in latest_released(public_cutoff, calendar).items():
        window = preceding_periods(latest, INPUT_PERIODS[metric_id])
        if (
            differenced[metric_id]
            and not set(window) <= set(held.get(metric_id, ()))
            and not window[0].endswith(("-01", "-Q1"))
        ):
            window = (preceding_periods(window[0], 2)[0], *window)
        periods[metric_id] = window
    return InputPeriods(periods)


def fetch_coverage(
    formula_version: str | None,
    *,
    window: Collection[date],
    public_cutoff: datetime,
    calendar: Sessions,
) -> InputPeriods:
    """The periods to hold so each day of ``window`` can be derived as it stood that day.

    A day's derivation sees what was out by its own end (and never after
    ``public_cutoff``), so the window's first day reads back further than its last. A
    direct period held now may not have been out on an earlier day, so every base period
    a day may difference from is kept.
    """
    union: dict[str, set[str]] = {}
    for day in window:
        day_end = datetime.combine(day, time.max, tzinfo=_SHANGHAI)
        needs = minimum_requirements(
            formula_version,
            public_cutoff=min(public_cutoff, day_end),
            calendar=calendar,
        )
        for metric_id, periods in needs.periods.items():
            union.setdefault(metric_id, set()).update(periods)
    return InputPeriods({metric_id: tuple(sorted(periods)) for metric_id, periods in union.items()})


def direct_periods(selector: Any) -> dict[str, frozenset[str]]:
    """The periods held as validated direct flows and quarterly levels, by parent."""
    held: dict[str, frozenset[str]] = {}
    for metric_id, dimensions in (("CN_SF_TOTAL", _SOCIAL_FINANCING), ("CN_GDP", _GDP)):
        held[metric_id] = frozenset(
            _period_label(metric_id, point.period_end)
            for point in selector.series(metric_id)
            if point.dimensions == dimensions
            and point.selection_status == "selected"
            and point.value_state is EvidenceValueState.REPORTED_VALUE
            and point.selected_value is not None
            and any(
                claim.claim_id == point.selected_claim_id and claim.quality_status == "validated"
                for claim in point.claims
            )
        )
    return held


def _period_label(metric_id: str, period_end: str) -> str:
    end = date.fromisoformat(period_end)
    return f"{end.year}-Q{(end.month - 1) // 3 + 1}" if metric_id == "CN_GDP" else f"{end:%Y-%m}"


def calculate(
    *,
    current_rolling_social_financing: float,
    previous_rolling_social_financing: float,
    current_rolling_nominal_gdp: float,
    previous_rolling_nominal_gdp: float,
) -> float:
    """The change, in percentage points, of rolling social financing's share of nominal GDP.

    Either rolling GDP not positive leaves the share undefined and is refused.
    """
    if current_rolling_nominal_gdp <= 0 or previous_rolling_nominal_gdp <= 0:
        raise ValueError("credit_impulse_gdp_must_be_positive")
    current_share = current_rolling_social_financing / current_rolling_nominal_gdp
    previous_share = previous_rolling_social_financing / previous_rolling_nominal_gdp
    return (current_share - previous_share) * 100


@dataclass(frozen=True)
class CreditImpulseResult:
    """A derivation of the impulse: its value when ``status`` is ``available``, else why not.

    ``input_claim_ids`` are the parent claims, social financing's before GDP's; the windows
    run from the first period's start to the last period's end.
    """

    formula_version: str | None
    status: str
    value: float | None = None
    unit: str = "percentage_points"
    period_start: str | None = None
    period: str | None = None
    gdp_input_measure: str | None = None
    social_financing_window: tuple[str, str] | None = None
    gdp_window: tuple[str, str] | None = None
    latest_gdp_period: str | None = None
    input_claim_ids: tuple[str, ...] = ()
    available_at: datetime | None = None
    public_available_at: datetime | None = None


def derive(
    repository: Any,
    formula_version: str | None,
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
    definition_version: str,
) -> CreditImpulseResult:
    """The impulse at ``as_of`` from the repository's selected inputs."""
    if formula_version is None:
        return CreditImpulseResult(None, "disabled_by_model")
    version = VERSIONS.get(formula_version, _DIRECT_ONLY)

    def failed(status: str = "missing_inputs") -> CreditImpulseResult:
        return CreditImpulseResult(formula_version, status)

    def held(metric_id: str, dimensions: Mapping[str, str]) -> list[MetricSeriesPoint]:
        return [
            point
            for point in repository.metric_series(
                metric_id, mode=as_of_mode, as_of=as_of, definition_version=definition_version
            )
            if point.dimensions == dimensions and point.claims
        ]

    monthly_social_financing = held("CN_SF_TOTAL", _SOCIAL_FINANCING)
    ytd_social_financing = held("CN_SF_TOTAL", _SOCIAL_FINANCING_YTD)
    quarterly_gdp = held("CN_GDP", _GDP)
    ytd_gdp = held("CN_GDP", _GDP_YTD) if version.gdp_from_ytd else []

    quarter_values: dict[str, float] = {}
    one_delivery: set[str] = set()
    if len(quarterly_gdp) >= 8:
        gdp_period_points = quarterly_gdp[-8:]
        gdp_input_points = gdp_period_points
        gdp_numbers = [
            float(point.selected_value)
            for point in gdp_period_points
            if point.selected_value is not None
        ]
        gdp_input_measure = "nominal_quarterly_level"
    else:
        derived_quarters = _quarter_levels_from_ytd(ytd_gdp)
        if len(derived_quarters) < 8 or derived_quarters[-1][0].period_end != (
            ytd_gdp[-1].period_end
        ):
            return failed()
        selected_quarters = derived_quarters[-8:]
        gdp_period_points = [point for point, _value, _inputs in selected_quarters]
        gdp_numbers = [value for _point, value, _inputs in selected_quarters]
        gdp_input_points = _inputs_of(selected_quarters, ytd_gdp)
        gdp_input_measure = "nominal_ytd_level"
        quarter_values = {
            point.selected_claim_id: value
            for point, value, _inputs in selected_quarters
            if point.selected_claim_id is not None
        }
        one_delivery = _quarters_from_one_delivery(
            repository, selected_quarters, definition_version=definition_version, as_of=as_of
        )
    if len(monthly_social_financing) >= 24:
        social_period_points = monthly_social_financing[-24:]
        if not _periods_are_consecutive(social_period_points, periods_per_year=12):
            return failed("nonconsecutive_social_financing_inputs")
        social_numbers = [
            point.selected_value
            for point in social_period_points
            if point.selected_value is not None
        ]
        social_input_points = social_period_points
    elif version.social_financing_from_ytd:
        monthly_flows = _monthly_flows_from_ytd(ytd_social_financing)
        if len(monthly_flows) < 24 or monthly_flows[-1][0].period_end != (
            ytd_social_financing[-1].period_end
        ):
            return failed()
        selected_flows = monthly_flows[-24:]
        social_period_points = [point for point, _value, _inputs in selected_flows]
        social_numbers = [value for _point, value, _inputs in selected_flows]
        social_input_points = _inputs_of(selected_flows, ytd_social_financing)
    else:
        return failed()
    if len(social_period_points) < 24 or len(gdp_period_points) < 8:
        return failed()
    if not _periods_are_consecutive(social_period_points, periods_per_year=12):
        return failed("nonconsecutive_social_financing_inputs")
    if not _periods_are_consecutive(gdp_period_points, periods_per_year=4):
        return failed("nonconsecutive_gdp_inputs")
    if len(social_numbers) != 24 or len(gdp_numbers) != 8:
        return failed()
    parents = (*social_input_points, *gdp_input_points)
    if any(not usable_point(point) for point in parents):
        return failed()
    adoption = ClaimAdoption(repository, definition_version=definition_version).check(
        {"CN_SF_TOTAL": tuple(social_input_points), "CN_GDP": tuple(gdp_input_points)}
    )
    if adoption["CN_SF_TOTAL"].rechecked or adoption["CN_GDP"].rechecked:
        adoptable = adoption.adoptable("CN_SF_TOTAL") | adoption.adoptable("CN_GDP")
        if {point.selected_claim_id for point in parents} - adoptable:
            return failed("incomplete_source_artifacts")
        announced = {
            claim_id: value
            for claim_id, value in quarter_values.items()
            if claim_id not in one_delivery
        }
        if announced and set(announced) - official_gdp_quarters_matching_baselines(
            repository, announced
        ):
            return failed("incomparable_gdp_vintages")
    try:
        value = calculate(
            current_rolling_social_financing=sum(social_numbers[-12:]),
            previous_rolling_social_financing=sum(social_numbers[:12]),
            current_rolling_nominal_gdp=sum(gdp_numbers[-4:]),
            previous_rolling_nominal_gdp=sum(gdp_numbers[:4]),
        )
    except ValueError:
        return failed("invalid_gdp_denominator")
    claims = [claim for point in parents if (claim := selected_claim(point)) is not None]
    public_times = [
        claim.public_available_at for claim in claims if claim.public_available_at is not None
    ]
    return CreditImpulseResult(
        formula_version,
        "available",
        value=value,
        period_start=social_period_points[-1].period_start,
        period=social_period_points[-1].period_end,
        gdp_input_measure=gdp_input_measure,
        social_financing_window=(
            social_period_points[0].period_start,
            social_period_points[-1].period_end,
        ),
        gdp_window=(gdp_period_points[0].period_start, gdp_period_points[-1].period_end),
        latest_gdp_period=gdp_period_points[-1].period_end,
        input_claim_ids=tuple(
            point.selected_claim_id for point in parents if point.selected_claim_id is not None
        ),
        available_at=max(claim.available_at for claim in claims),
        public_available_at=(
            max(public_times) if public_times and len(public_times) == len(claims) else None
        ),
    )


def _inputs_of(derived: Differenced, held: list[MetricSeriesPoint]) -> list[MetricSeriesPoint]:
    """The held year-to-date points the differenced periods were taken from, in order."""
    used = {point.selected_claim_id for _period, _value, inputs in derived for point in inputs}
    return [point for point in held if point.selected_claim_id in used]


def _periods_are_consecutive(points: list[MetricSeriesPoint], *, periods_per_year: int) -> bool:
    ordinals = []
    for point in points:
        period = date.fromisoformat(point.period_end)
        if periods_per_year == 12:
            ordinal = period.year * 12 + period.month
        else:
            ordinal = period.year * 4 + (period.month - 1) // 3
        ordinals.append(ordinal)
    return all(right - left == 1 for left, right in zip(ordinals, ordinals[1:], strict=False))


def _quarters_from_one_delivery(
    repository: Any,
    quarters: Differenced,
    *,
    definition_version: str,
    as_of: datetime,
) -> set[str]:
    """Quarters whose year-to-date ends one TuShare delivery stated together, as selected.

    Differencing across official releases can mix vintages, so such a quarter must match the
    one its release announced. Levels TuShare delivered together are one vintage already:
    its census-revised series has no release of its own to check against. A quarter fetched
    again alone still counts while its value is unchanged; a revised end no longer matches
    any delivery of both and is reconciled as before (run findings 2026-09-28, ticket 13).
    """
    together: set[str] = set()
    for quarter, _value, inputs in quarters:
        if quarter.selected_claim_id is None or any(
            point.selected_value is None for point in inputs
        ):
            continue
        selected = {point.period_end: float(point.selected_value or 0.0) for point in inputs}
        deliveries = repository.delivered_values(
            "CN_GDP",
            quarter.dimensions,
            tuple(selected),
            provider="tushare",
            definition_version=definition_version,
            as_of=as_of,
        )
        if any(stated == selected for stated in deliveries.values()):
            together.add(quarter.selected_claim_id)
    return together


def _differenced(
    points: list[MetricSeriesPoint],
    *,
    opens_year: Callable[[date], bool],
    follows: Callable[[date, date], bool],
    difference: Callable[[float, float], float],
    positive_only: bool,
) -> Differenced:
    derived: Differenced = []
    for index, point in enumerate(points):
        value = point.selected_value
        if value is None:
            continue
        period = date.fromisoformat(point.period_end)
        if opens_year(period):
            derived.append((point, float(value), (point,)))
            continue
        if index == 0:
            continue
        previous = points[index - 1]
        previous_period = date.fromisoformat(previous.period_end)
        previous_value = previous.selected_value
        if (
            previous_period.year != period.year
            or not follows(previous_period, period)
            or previous_value is None
        ):
            continue
        amount = difference(float(value), float(previous_value))
        if positive_only and amount <= 0:
            continue
        derived.append((point, amount, (previous, point)))
    return derived


def _quarter(day: date) -> int:
    return (day.month - 1) // 3 + 1


def _quarter_levels_from_ytd(points: list[MetricSeriesPoint]) -> Differenced:
    # Decimal source levels must not gain binary subtraction tails before comparison with
    # the same release's announced quarterly amount.
    return _differenced(
        points,
        opens_year=lambda day: _quarter(day) == 1,
        follows=lambda previous, day: _quarter(previous) == _quarter(day) - 1,
        difference=lambda value, previous: float(Decimal(str(value)) - Decimal(str(previous))),
        positive_only=True,
    )


def _monthly_flows_from_ytd(points: list[MetricSeriesPoint]) -> Differenced:
    return _differenced(
        points,
        opens_year=lambda day: day.month == 1,
        follows=lambda previous, day: previous.month == day.month - 1,
        difference=lambda value, previous: value - previous,
        positive_only=False,
    )
