"""What a model reads back: by metric, its members, the reading and the released periods.

One declaration answers both what the full run's retrieval plan requires and where the
direct fetch starts (macro semantics ticket 02). As the credit impulse first did (ticket
24), it tells apart what the target day needs at least from what the window's fetch must
cover so each day in it reads as it stood: a reading names the periods a day reads
(``Reading.periods``) and, when fewer, those a day must hold (``Reading.required``). One
read on every day of the window (``every_day``) has the plan require what each day must
hold, not the target day's alone, and the fetch cover it.

A reading's periods count back from the newest period out: one period, N consecutive ones,
four quarters, N trading sessions, or an explicit set such as t, t-1, t-12, t-13, whose
farthest point is t-13 and which holds four periods, not thirteen.

A reading reads every member the catalog requires of its metric unless it names its own;
a period only such readings require is then checked for those members alone.

A reading of more sessions than the fetch's fixed lead holds counts them on the SSE
calendar, back from each day of the window, and the fetch starts there (macro semantics
ticket 06); where the calendar does not state them, weekdays are counted with a margin for
holidays.

Not here: when a period is out (freshness's release rules), the credit impulse's base
periods (its module answers them; ``resolve`` asks it), and what a reading computes.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pring_cycle import credit_impulse
from pring_cycle.confirmation import DERIVED_FORMULAS, SESSION_FORMULAS, KeyIndicator
from pring_cycle.credit_impulse import InputPeriods
from pring_cycle.metric_contracts import evidence_frequency
from pring_cycle.retrieval import preceding_periods
from pring_cycle.trading_calendar import TradingCalendar

if TYPE_CHECKING:
    from pring_cycle.context_projection import ContextProjectionRules
    from pring_cycle.trading_calendar import Sessions

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_UNITS = {"monthly": "month", "quarterly": "quarter", "daily": "session", "event": "event"}


@dataclass(frozen=True)
class Periods:
    """Which released periods a reading takes, counted back from the newest one out.

    ``0`` is the newest; ``(0, 1, 12, 13)`` the month, the one before, and both a year
    before them. The unit is a month, a quarter, an SSE session, or an event, which is
    read alone.
    """

    offsets: tuple[int, ...]
    unit: str = "month"

    def __post_init__(self) -> None:
        if not self.offsets or min(self.offsets) < 0 or len(set(self.offsets)) < len(self.offsets):
            raise ValueError(f"lookback_offsets_invalid:{self.offsets}")
        if self.unit not in _UNITS.values():
            raise ValueError(f"lookback_unit_unknown:{self.unit}")
        if self.unit == "event" and self.offsets != (0,):
            raise ValueError("lookback_event_read_alone")
        object.__setattr__(self, "offsets", tuple(sorted(self.offsets)))

    @classmethod
    def consecutive(cls, count: int, unit: str = "month") -> Periods:
        """The newest ``count`` periods."""
        if count < 1:
            raise ValueError(f"lookback_count_invalid:{count}")
        return cls(tuple(range(count)), unit)

    @classmethod
    def explicit(cls, *offsets: int, unit: str = "month") -> Periods:
        """The periods ``offsets`` back from the newest, ``0`` for the newest itself."""
        return cls(offsets, unit)

    @classmethod
    def quarters(cls, count: int) -> Periods:
        return cls.consecutive(count, "quarter")

    @classmethod
    def sessions(cls, count: int) -> Periods:
        return cls.consecutive(count, "session")

    @property
    def farthest(self) -> int:
        """How far back the oldest period lies: 13 for t-13, whatever the count."""
        return self.offsets[-1]

    def back_from(self, newest: str, sessions: Sequence[str] = ()) -> tuple[str, ...]:
        """The periods back from ``newest``, oldest first.

        Months read ``YYYY-MM`` and quarters ``YYYY-Qn``; sessions are counted on
        ``sessions``, ISO days in order. The newest alone is ``newest`` as given.
        """
        if self.offsets == (0,):
            return (newest,)
        if self.unit == "session":
            held = [day for day in sessions if day <= newest]
            if len(held) <= self.farthest:
                raise ValueError(f"lookback_sessions_short:{newest}")
            return tuple(held[-1 - offset] for offset in reversed(self.offsets))
        span = preceding_periods(newest, self.farthest + 1)
        return tuple(span[-1 - offset] for offset in reversed(self.offsets))


@dataclass(frozen=True)
class Reading:
    """One reading of a metric: the periods each day reads, and which members.

    ``required`` is what a day must hold when that is fewer than it reads (a period to
    compare with, say); ``members`` None reads every member the catalog requires. A month
    in ``unreleased_months`` (1 for January) is never published for the members: it is
    counted back over, and neither read nor required.
    """

    metric_id: str
    reading: str
    periods: Periods
    required: Periods | None = None
    members: tuple[Mapping[str, str], ...] | None = None
    every_day: bool = False
    unreleased_months: frozenset[int] = frozenset()

    @property
    def minimum(self) -> Periods:
        return self.required or self.periods

    def released(self, periods: Iterable[str]) -> tuple[str, ...]:
        """``periods`` less the months never released for the members."""
        return tuple(
            period
            for period in periods
            if self.periods.unit != "month" or int(period[5:7]) not in self.unreleased_months
        )


# Each formula's derived metric and how many of each input's newest periods a day reads.
# The credit impulse's inputs are its version's, with any base period its module adds.
FORMULA_INPUTS: dict[str, tuple[str, dict[str, int]]] = {
    "credit_impulse": ("CN_CREDIT_IMPULSE", {}),
    "dr007_policy_spread": ("CN_DR007_POLICY_SPREAD", {"CN_DR007": 1, "CN_OMO_7D_RATE": 1}),
    "loan_monthly_change": ("CN_LOAN_STRUCTURE", {"CN_LOAN_STRUCTURE": 2}),
    "omo_net_injection": ("CN_OMO_7D_AMOUNT", {"CN_OMO_7D_AMOUNT": 1}),
    "order_inventory_spread": (
        "CN_ORDER_INVENTORY_SPREAD",
        {"CN_PMI_ACTIVITY": 1, "CN_PMI_INVENTORY": 1},
    ),
    "production_order_spread": ("CN_PRODUCTION_ORDER_SPREAD", {"CN_PMI_ACTIVITY": 1}),
    "real_inventory_approximation": (
        "CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
        {"CN_FINISHED_GOODS_INVENTORY": 1, "CN_PPI": 1},
    ),
    "ust_2s10s_spread": (
        "UST_2S10S_SPREAD",
        {"UST2Y_NOMINAL_YIELD": 1, "UST10Y_NOMINAL_YIELD": 1},
    ),
}
_CREDIT_INPUTS = {"CN_SF_TOTAL": "month", "CN_GDP": "quarter"}


def own_reading(metric_id: str, frequency: str, *, every_session: bool = False) -> Reading:
    """A series read as itself: its newest period, and the one before it to compare with.

    A daily series read on every session of the window (``every_session``, the P0 and P1
    ones) needs each session; an event is read alone.
    """
    unit = _UNITS.get(frequency, "month")
    if unit == "event":
        return Reading(metric_id, "own", Periods.consecutive(1, unit))
    return Reading(
        metric_id,
        "own",
        Periods.consecutive(2, unit),
        required=Periods.consecutive(1, unit),
        every_day=unit == "session" and every_session,
    )


def declare(rules: ContextProjectionRules) -> tuple[Reading, ...]:
    """The model's readings: each series as itself, each formula's inputs, then each key
    indicator's members over the months its confirmation reads (ADR-0037)."""
    frequencies = {
        item.metric_id: evidence_frequency(item.metric_id, item.frequency)
        for item in rules.metric_definitions
    }
    readings = [
        own_reading(
            item.metric_id,
            frequencies[item.metric_id],
            every_session=item.priority in {"P0", "P1"},
        )
        for item in rules.metric_definitions
    ]
    for name, version in rules.formula_versions.items():
        if name == "credit_impulse":
            periods = credit_impulse.VERSIONS[version].periods
            readings.extend(
                Reading(
                    metric_id,
                    name,
                    Periods.consecutive(periods[metric_id], unit),
                    every_day=True,
                )
                for metric_id, unit in _CREDIT_INPUTS.items()
            )
            continue
        _metric, inputs = FORMULA_INPUTS[name]
        readings.extend(
            Reading(
                source,
                name,
                Periods.consecutive(count, _UNITS.get(frequencies.get(source, ""), "month")),
            )
            for source, count in inputs.items()
        )
    if rules.confirmation is not None:
        for indicator in rules.confirmation.indicators:
            readings.extend(_confirmation_readings(indicator, frequencies))
        prices = rules.confirmation.prices
        if prices is not None:
            # The cores' relative momentum: a return over 120 sessions reads 121 actual
            # closes, one before the window (macro semantics ticket 09). The cores' fetch
            # holds more than the target day's; a day early in the window reads what it holds.
            readings.extend(
                Reading(
                    metric_id, "confirmation:price_consistency", Periods.sessions(prices.points)
                )
                for metric_id in prices.cores.values()
            )
    return tuple(readings)


def _confirmation_readings(
    indicator: KeyIndicator, frequencies: Mapping[str, str]
) -> list[Reading]:
    """What a key indicator reads of each member: its periods, and those before them its
    grace reads back of the main member or one a turn hint reads, less the months never
    released.

    The main member's months stood in for by another member are that member's alone; a
    derived member reads each input at its months and a year before them, none beyond the
    horizon; a member whose change its source states reads that change at its periods. A daily
    indicator's member reads its periods' sessions, a formula's input the lead before them
    too. A policy action reads the window and the value in force before it: an LPR its
    months, a rate the one in force on the session before the window and each session's
    notice from there; an RRR's events are traced back on their own (ADR-0028). An
    inventory quadrant's line reads the quadrant's months, and those it may wait on the
    other lines, back from its own newest (macro semantics ticket 08).
    """
    readings: list[Reading] = []
    every_month = frozenset(range(1, 13))
    for member in indicator.members:
        if indicator.quadrant is not None and member is indicator.main:
            # The quadrant is read of its lines' members, each back from its own newest.
            continue
        name = (
            f"confirmation:{indicator.key}"
            if member is indicator.main
            else f"confirmation:{indicator.key}:{member.name}"
        )
        members = (member.dimensions,) if member.dimensions else None
        if indicator.actions is not None:
            if frequencies.get(member.metric_id) == "monthly":
                readings.append(
                    Reading(
                        member.metric_id,
                        name,
                        Periods.consecutive(indicator.lookback),
                        members=members,
                    )
                )
            elif indicator.actions == "level":
                # The rate in force on the session before the window; the notices of it and
                # of each session in the window, which state the rate.
                readings.append(
                    Reading(
                        member.metric_id,
                        name,
                        Periods.explicit(indicator.window_sessions, unit="session"),
                        members=members,
                    )
                )
                if indicator.notices is not None and member is indicator.main:
                    readings.append(
                        Reading(
                            indicator.notices.metric_id,
                            f"{name}:notices",
                            Periods.sessions(indicator.window_sessions + 1),
                            members=(indicator.notices.dimensions,),
                        )
                    )
            continue
        if indicator.frequency == "daily" and member.frequency is None:
            assert indicator.period_sessions is not None
            formula = SESSION_FORMULAS.get(member.session_formula or "")
            readings.append(
                Reading(
                    formula.metric_id if formula is not None else member.metric_id,
                    name,
                    Periods.sessions(
                        indicator.reach(member) * indicator.period_sessions
                        + (formula.lead_sessions if formula is not None else 0)
                    ),
                    members=(formula.dimensions,) if formula is not None else members,
                )
            )
            continue
        if member.formula is not None:
            # Each month it is read for, its inputs within the horizon: loans' t, t-1, t-12
            # and t-13 alone.
            for item in DERIVED_FORMULAS[member.formula].inputs:
                offsets = {
                    month + offset
                    for month in range(indicator.reach(member))
                    for offset in item.offsets
                }
                readings.append(
                    Reading(
                        item.metric_id,
                        f"{name}:{item.name}",
                        Periods.explicit(*sorted(offsets)),
                        members=(
                            item.dimensions if item.dimensions is not None else member.dimensions,
                        ),
                    )
                )
            continue
        # Each period grace reaches back reads as it stood: its own lookback before it.
        periods = Periods.consecutive(
            indicator.reach(member), "month" if member.frequency == "monthly" else indicator.unit
        )
        readings.append(
            Reading(
                member.metric_id,
                name,
                periods,
                members=(member.dimensions,),
                unreleased_months=member.unreleased_months | frozenset(member.stand_ins),
            )
        )
        readings.extend(
            Reading(
                member.metric_id,
                f"{name}:stand_in:{month}",
                periods,
                members=(dimensions,),
                unreleased_months=every_month - {month},
            )
            for month, dimensions in sorted(member.stand_ins.items())
        )
        if member.change_from is not None:
            # The change its source states, of each period it reads.
            readings.append(
                Reading(member.metric_id, f"{name}:change", periods, members=(member.change_from,))
            )
    return readings


@dataclass(frozen=True)
class Resolved:
    """A reading resolved for a run, by metric: periods oldest first (ticket 24).

    ``minimum`` is what the target day needs and ``required`` what each day of the window
    needs, together; ``covered`` is what the window's fetch reads for it.
    """

    minimum: InputPeriods = field(default_factory=InputPeriods)
    required: InputPeriods = field(default_factory=InputPeriods)
    covered: InputPeriods = field(default_factory=InputPeriods)


@dataclass(frozen=True)
class Lookback:
    """A model's readings resolved for a run's target day and window, by reading.

    Every reading of months or quarters is resolved for the fetch; one read every day,
    for the plan as well. Another is required where the plan anchors it.
    """

    readings: tuple[Reading, ...] = ()
    resolved: Mapping[str, Resolved] = field(default_factory=dict)

    @property
    def coverage(self) -> InputPeriods:
        """What the window's fetch covers, by metric, whatever reads it."""
        union: dict[str, set[str]] = {}
        for resolved in self.resolved.values():
            for metric_id, periods in resolved.covered.periods.items():
                union.setdefault(metric_id, set()).update(periods)
        return InputPeriods({metric_id: tuple(sorted(p)) for metric_id, p in union.items()})

    def required(
        self,
        metric_id: str,
        anchor: str,
        *,
        sessions: Sequence[str] = (),
        window: Sequence[str] | None = None,
        whole_window: bool = False,
        catalog_members: Callable[[str], tuple[Mapping[str, str], ...] | None] | None = None,
    ) -> dict[str, tuple[Mapping[str, str], ...] | None]:
        """The periods a full run requires of ``metric_id``, and the members of each.

        Each reading requires its least at ``anchor``: the newest period held, or the
        newest due when later, or with none held the newest out (sessions counted on
        ``sessions``, as far back as the SSE calendar states them: those it does not are
        not named); one read every day, what each day of the window needs up to
        ``anchor`` instead, the target day's least among it (a release out but not yet
        due beside one held is looked for, not required). A daily series read on every
        session of a complete ``window`` (``sessions`` unless given; ``whole_window``)
        requires each of them, and of another reading what it reads back on the target day.
        A period some reading requires of every member is checked for every member, and
        for any other a reading names: those the catalog does not require of the period
        (``catalog_members``) are named beside them, not lost (ticket 04); with no member
        contract for the period, those named are checked.
        """
        readings = tuple(item for item in self.readings if item.metric_id == metric_id)
        named: dict[str, tuple[Mapping[str, str], ...]] = {}
        whole: set[str] = set()

        def add(periods: Iterable[str], members: tuple[Mapping[str, str], ...] | None) -> None:
            for period in periods:
                known = named.setdefault(period, ())
                if members is None:
                    whole.add(period)
                else:
                    named[period] = (*known, *(m for m in members if m not in known))

        def result() -> dict[str, tuple[Mapping[str, str], ...] | None]:
            required: dict[str, tuple[Mapping[str, str], ...] | None] = {}
            for period, members in sorted(named.items()):
                if period not in whole:
                    required[period] = members
                    continue
                if catalog_members is None or not members:
                    required[period] = None
                    continue
                every = catalog_members(period)
                if every is None:
                    # No contract to read every member by: those named are what is known.
                    required[period] = members
                    continue
                extra = tuple(m for m in members if m not in every)
                required[period] = (*every, *extra) if extra else None
            return required

        days = sessions if window is None else window

        def back(item: Reading) -> tuple[str, ...]:
            # Sessions counted back past the newest two count from the window's last, the
            # target day, whatever an event held last (the policy rate in force before the
            # window: macro semantics ticket 06).
            counted = item.periods.unit == "session" and item.periods.farthest > 1 and days
            return _stated(item.minimum, days[-1] if counted else anchor, sessions)

        if whole_window and any(
            item.every_day and item.periods.unit == "session" for item in readings
        ):
            # Each session of the window; a reading of the target day alone asks its own
            # members of its own sessions only.
            for item in readings:
                add(days if item.every_day else back(item), item.members)
            return result()
        for item in readings:
            if item.every_day and item.periods.unit != "session":
                resolved = self.resolved.get(item.reading, Resolved())
                each_day = resolved.required.periods.get(metric_id, ())
                add((period for period in each_day if period <= anchor), item.members)
            else:
                add(item.released(back(item)), item.members)
        return result()


def _stated(periods: Periods, anchor: str, sessions: Sequence[str]) -> tuple[str, ...]:
    """``periods`` back from ``anchor``; of sessions reaching before those ``sessions``
    state, the ones they do."""
    try:
        return periods.back_from(anchor, sessions)
    except ValueError:
        if periods.unit != "session":
            raise
    held = [day for day in sessions if day <= anchor]
    return tuple(held[-1 - offset] for offset in reversed(periods.offsets) if offset < len(held))


def resolve(
    readings: tuple[Reading, ...],
    *,
    formula_versions: Mapping[str, str],
    window: Collection[date],
    public_cutoff: datetime,
    calendar: Sessions,
    direct_held: Mapping[str, Collection[str]] | None = None,
) -> Lookback:
    """``readings`` for the target day at ``public_cutoff`` and each day of ``window``.

    Each day reads back from the newest period out by its own end, never after
    ``public_cutoff``. The credit impulse's inputs are its module's answer (ticket 24).
    A daily reading of the newest session and the one before is read off the window's
    sessions and the fetch's fixed margin; one of more is covered back from each day of
    the window, counted on ``calendar`` (macro semantics ticket 06). A daily reading of
    more on every day is refused: the plan does not require it day by day.
    """
    version = formula_versions.get("credit_impulse")
    minimum = credit_impulse.minimum_requirements(
        version, public_cutoff=public_cutoff, calendar=calendar, direct_held=direct_held
    )
    coverage = credit_impulse.fetch_coverage(
        version, window=window, public_cutoff=public_cutoff, calendar=calendar
    )
    collected: dict[str, dict[str, dict[str, set[str]]]] = {}

    def collect(reading: str, part: str, metric_id: str, periods: Iterable[str]) -> None:
        parts = collected.setdefault(reading, {"minimum": {}, "required": {}, "covered": {}})
        parts[part].setdefault(metric_id, set()).update(periods)

    for metric_id, periods in minimum.periods.items():
        collect("credit_impulse", "minimum", metric_id, periods)
    for metric_id, periods in coverage.periods.items():
        collect("credit_impulse", "required", metric_id, periods)
        collect("credit_impulse", "covered", metric_id, periods)
    declared = [(item.metric_id, item.reading) for item in readings]
    if len(set(declared)) < len(declared):
        # A reading's periods are kept by its name and metric, with its members.
        raise ValueError("lookback_reading_declared_twice")
    days = sorted(window)
    for item in readings:
        if item.periods.unit == "session":
            if item.every_day and item.minimum.farthest > 0:
                raise ValueError(f"lookback_sessions_beyond_daily_lead:{item.metric_id}")
            if item.periods.farthest > 1:
                for day in days:
                    collect(
                        item.reading,
                        "covered",
                        item.metric_id,
                        _sessions_back(calendar, day, item.periods),
                    )
            continue
        if item.periods.unit == "event" or item.reading == "credit_impulse":
            continue
        frequency = "quarterly" if item.periods.unit == "quarter" else "monthly"
        # Each day's newest, the target day's last: the window ends at the target day.
        newest = [
            newest_released(item.metric_id, min(public_cutoff, _day_end(day)), calendar, frequency)
            for day in days
        ]
        target = newest_released(item.metric_id, public_cutoff, calendar, frequency)
        if target is None:
            continue  # dated otherwise by its release rule: fetched by its own range
        for day_newest in (each for each in newest if each is not None):
            covered = item.released(item.periods.back_from(day_newest))
            collect(item.reading, "covered", item.metric_id, covered)
            if item.every_day:
                required = item.released(item.minimum.back_from(day_newest))
                collect(item.reading, "required", item.metric_id, required)
        if item.every_day:
            least = item.released(item.minimum.back_from(target))
            collect(item.reading, "minimum", item.metric_id, least)
    return Lookback(
        readings,
        {
            reading: Resolved(
                *(
                    InputPeriods(
                        {metric_id: tuple(sorted(p)) for metric_id, p in parts[part].items()}
                    )
                    for part in ("minimum", "required", "covered")
                )
            )
            for reading, parts in collected.items()
        },
    )


def session_reach(readings: Iterable[Reading]) -> int:
    """How many sessions back from a day the farthest daily reading reaches, itself one."""
    return max(
        (item.periods.farthest + 1 for item in readings if item.periods.unit == "session"),
        default=1,
    )


def _sessions_back(calendar: Sessions, day: date, periods: Periods) -> tuple[str, ...]:
    """The sessions ``periods`` reads back from ``day``, counted on the SSE calendar.

    Where it does not state them: from ``day`` back as many weekdays and a margin for the
    holidays among them -- what the fetch must start before, not which days are sessions.
    """
    if isinstance(calendar, TradingCalendar):
        try:
            sessions = calendar.sessions_back(
                calendar.latest_on_or_before(day), periods.farthest + 1
            )
        except LookupError:
            pass
        else:
            return periods.back_from(
                sessions[-1].isoformat(), [item.isoformat() for item in sessions]
            )
    first, counted = day, 0
    while counted < periods.farthest:
        first -= timedelta(days=1)
        counted += first.weekday() < 5
    return ((first - timedelta(days=7 + periods.farthest // 15)).isoformat(), day.isoformat())


def newest_released(
    metric_id: str, cutoff: datetime, calendar: Sessions, frequency: str = "monthly"
) -> str | None:
    """The newest ``frequency`` period out at ``cutoff``: ``YYYY-MM`` or ``YYYY-Qn``.

    By the metric's release rule; without a monthly or quarterly one, the period before
    the cutoff's own. None when the rule dates the metric by another frequency.
    """
    from pring_cycle.freshness import FRESHNESS_REGISTRY, latest_released_period

    rule = FRESHNESS_REGISTRY.get(metric_id)
    if rule is not None and rule.frequency in {"monthly", "quarterly"}:
        if rule.frequency != frequency:
            return None
        return period_label(latest_released_period(rule, cutoff, calendar), frequency)
    own = period_label(cutoff.astimezone(_SHANGHAI).date(), frequency)
    return preceding_periods(own, 2)[0]


def period_label(day: date, frequency: str) -> str:
    """The month (``YYYY-MM``) or quarter (``YYYY-Qn``) ``day`` falls in."""
    if frequency == "quarterly":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    return f"{day:%Y-%m}"


def _day_end(day: date) -> datetime:
    return datetime.combine(day, time.max, tzinfo=_SHANGHAI)
