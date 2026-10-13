"""Confirmation: how far the key indicators bear out the formal stage's narrative (ADR-0037).

The formal stage is the three cores' alone and is decided first. Confirmation reads each
key indicator's members -- level against the indicator's line, momentum on the period
before, slope change over the three newest periods, and, over a year, where the value
stands in its range and whether its change is marked -- lists where they agree with the
main member or split from it, and has the main member's reading answer the current
stage's cells of the model's frozen expectation table: support, counterevidence,
observation only or unconfirmed, with the proposition it bears on. A member opposite to
the main one caps the relation at observation only, as does a cap the stage names (the
social financing held up by government bonds alone). A non-canonical combination or a
held stage has no narrative to confirm: every relation is not applicable and the readings
are still given. Each dimension counts its indicators' relations; one the model reads no
indicator of yet says so, with no label in its place. A derived value (M1-M2) is shown
under its indicator and never counted.

A reading not known is never a direction: a main member missing a month of its lookback
leaves the indicator unconfirmed with the months named, and an unchanged value is flat,
not an easing. A month a member is never released for is no gap: it is passed over, or
read from the official member standing in for it.

Timing and grace (ticket 05): each indicator leads, moves with or lags the cycle. A
counterevidence cell waiting on grace -- marked so in the table, or met by a lagging
indicator still in the previous stage's form or a leading one already in the next's -- is
observation only until the signal has held longer than its grace (two months, one
quarter), counted in independent periods back from the newest, each read as it stood:
never by how many runs saw it. A turn signal is told with its maturity: a sprout when it
first shows, forming once it holds two periods or leading indicators turn toward the same
stage together, confirmed past grace. Only confirmed counts. An indicator counts once for
its newest period, however many days read it.

Cumulative and quarterly indicators (ticket 07): a main member may be derived -- loans'
month's flow from year-to-date totals against the same month a year before, read from t,
t-1, t-12 and t-13 and nothing further back -- and a member may be cumulative (industrial
profits' official year-to-date growth, said so), shown without being compared (GDP's
nominal year-to-date level), or have its change read as its source states it (capacity
utilisation's on the same quarter a year before). A quarterly indicator's year is its four
quarters.
"""

from __future__ import annotations

import calendar
import copy
import statistics
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from pring_cycle.bond_attribution import AttributionRules
from pring_cycle.domain import FormalStage
from pring_cycle.price_consistency import PriceRules
from pring_cycle.registered_warrants import WarrantRules

OUTPUT_STRUCTURE = "confirmation-v0001"
MACRO_RULES_VERSION = "macro-confirmation-v0001"
# The manifest fields that hold confirmation; a manifest with none of them reads the four
# single-dimension labels of the models before it.
MANIFEST_FIELDS = ("macro_rules_version", "projection_output_structure", "confirmation_rules")
DIMENSIONS = ("policy", "credit", "overheat", "price", "inventory")
RELATIONS = ("support", "counterevidence", "observation_only", "unconfirmed", "not_applicable")
TIMINGS = ("leading", "coincident", "lagging")
MATURITIES = ("sprout", "forming", "confirmed")
# A period of a monthly or quarterly indicator spans months; a daily one's, its own number
# of sessions.
FREQUENCIES = ("monthly", "quarterly", "daily")
_MONTHS = {"monthly": 1, "quarterly": 3}
_UNITS = {"monthly": "month", "quarterly": "quarter", "daily": "sessions"}
_ADJACENT = {"next": 1, "previous": -1}
# A year of a monthly series: where a value stands in its range, and how large a change is,
# are read within it and nowhere further back (ADR-0035); a daily range spans 250 sessions.
# The rules state each frequency's year (``year_periods``, ``marked_periods``).
YEAR_MONTHS = 12
YEAR_SESSIONS = 250
# An auxiliary member shows agreement by its momentum, and its slope: never more months.
AUXILIARY_MONTHS = 3
_CELL_RELATIONS = frozenset({"support", "counterevidence", "observation_only"})
_STAGES = tuple(stage.value for stage in FormalStage)
_READINGS = {
    "level": frozenset({"above", "below", "at"}),
    "momentum": frozenset({"up", "down", "flat"}),
    "slope": frozenset({"steeper", "slower", "turn", "flat"}),
    "crossed": frozenset({"above", "below", "none"}),
    "position": frozenset({"high", "middle", "low"}),
    "change_size": frozenset({"marked", "ordinary"}),
    # The two newest changes alike: a run up (rising on) or down, or none.
    "run": frozenset({"up", "down", "none"}),
    # A policy member's latest action in the evidence window, or none there.
    "action": frozenset({"cut", "hike", "none"}),
    # The inventory quadrant its lines' directions name, or none of them: unclassified.
    "quadrant": frozenset(
        {
            "active_destocking",
            "passive_destocking",
            "active_restocking",
            "passive_restocking",
            "unclassified",
        }
    ),
}
# The inventory quadrant's lines: demand and inventory name the quadrant, production
# verifies it (GLOSSARY.md, 库存象限).
QUADRANT_LINES = ("demand", "production", "inventory")


@dataclass(frozen=True)
class DerivedInput:
    """One input of a derived member: a metric's member, ``offsets`` months back; the
    derived member's own dimensions when ``dimensions`` is None (each loan pair's totals)."""

    name: str
    metric_id: str
    dimensions: Mapping[str, str] | None
    offsets: tuple[int, ...]


def _monthly_increment_yoy_change(
    month: str, values: Mapping[tuple[str, int], float]
) -> float | None:
    """The month's flow against the same month a year before: more (positive) or less.

    Each month's flow is its year-to-date total less the month before's; January's is its
    own total, the year's first.
    """

    def flow(offset: int) -> float:
        if month_back(month, offset).endswith("-01"):
            return values[("ytd", offset)]
        return values[("ytd", offset)] - values[("ytd", offset + 1)]

    return flow(0) - flow(12)


def _monthly_increment_needs(month: str) -> tuple[tuple[str, int], ...]:
    """The totals a month's flow against a year before needs: January's, its own alone."""
    offsets = (0, 12) if month.endswith("-01") else (0, 1, 12, 13)
    return tuple(("ytd", offset) for offset in offsets)


@dataclass(frozen=True)
class DerivedFormula:
    """A derived member's frozen formula: its inputs, read at offsets from each month.

    ``months`` is how many months it is read for, within thirteen months back
    (ADR-0035); the inputs declare every offset any month needs, and ``compute`` takes
    those its month needs, raising KeyError for one not held. It agrees with the main
    member by its momentum, or by ``agrees_by`` its sign: a flow more than a year before
    rises, less falls.
    """

    inputs: tuple[DerivedInput, ...]
    compute: Callable[[str, Mapping[tuple[str, int], float]], float | None]
    months: int
    # The inputs (name, offset) a month needs, of those declared.
    needs: Callable[[str], tuple[tuple[str, int], ...]]
    agrees_by: str = "momentum"

    @property
    def farthest(self) -> int:
        """How many months back the farthest input lies: 13 for t-13."""
        return max(offset for item in self.inputs for offset in item.offsets)


_SF_YTD = {"measure": "ytd_increment"}
# Deterministic processing frozen with the model (spec: a month's flow from year-to-date
# totals).
DERIVED_FORMULAS: dict[str, DerivedFormula] = {
    "sf-monthly-increment-yoy-change-v0001": DerivedFormula(
        (DerivedInput("ytd", "CN_SF_TOTAL", _SF_YTD, (0, 1, 12, 13)),),
        _monthly_increment_yoy_change,
        months=1,
        needs=_monthly_increment_needs,
        agrees_by="sign",
    ),
    # A loan pair's month's flow, from its own year-to-date totals, more or less than the
    # same month a year before (ticket 07).
    "loan-monthly-increment-yoy-change-v0001": DerivedFormula(
        (DerivedInput("ytd", "CN_LOAN_STRUCTURE", None, (0, 1, 12, 13)),),
        _monthly_increment_yoy_change,
        months=1,
        needs=_monthly_increment_needs,
        agrees_by="sign",
    ),
}
# A shown derived value of two members of the same month: the first less the second.
SPREAD_FORMULAS = frozenset({"m1-m2-yoy-spread-v0001"})
# A shown derived value of one member against its level line, in basis points: DR007's
# period mean less the policy rate in force at its end.
LINE_SPREAD_FORMULAS = frozenset({"dr007-policy-spread-sessions-v0001"})


@dataclass(frozen=True)
class SessionFormula:
    """A daily member's frozen formula: a value for each session from one metric's member.

    ``lead_sessions`` are read before the periods' first session: what matures in them was
    put in earlier.
    """

    metric_id: str
    dimensions: Mapping[str, str]
    lead_sessions: int


# The seven-day reverse repo's net injection on a session: what was put in since the
# session before, less what matures -- reported for the session, or each injection seven
# days on, rolled to the next session (spec: deterministic processing; N14).
SESSION_FORMULAS: dict[str, SessionFormula] = {
    "omo-7d-net-injection-v0001": SessionFormula(
        "CN_OMO_7D_AMOUNT", {"measure": "injection"}, lead_sessions=10
    ),
}


@dataclass(frozen=True)
class Member:
    """A member of a key indicator, of its metric unless ``metric_id`` names another.

    ``unreleased_months`` are the calendar months it is never published for; a month in
    ``stand_ins`` is read from that member of the same metric in its place (an official
    value said of the same thing), shown as ``stand_in_label`` says. ``formula`` derives
    the member from its inputs instead.
    """

    name: str
    label: str
    metric_id: str
    dimensions: Mapping[str, str]
    unreleased_months: frozenset[int] = frozenset()
    stand_ins: Mapping[int, Mapping[str, str]] = field(default_factory=dict)
    formula: str | None = None
    stand_in_label: str | None = None
    # Of a daily indicator: each period's mean (a rate) or sum (a flow) of its sessions,
    # their values from ``session_formula`` when it names one; or read by month instead.
    aggregate: str | None = None
    session_formula: str | None = None
    frequency: str | None = None
    # Its dimensions are some of a point's: an RRR change of any scope.
    partial: bool = False
    # Each value is a year-to-date figure, said so wherever it is read (industrial profits'
    # cumulative growth: ticket 07).
    cumulative: bool = False
    # Shown beside the main member, its direction never compared with it: a nominal
    # year-to-date level rises each quarter of a year whatever growth does.
    compared: bool = True
    # Its change on the period before is read from this member of its metric instead, as
    # the source states it: capacity utilisation's on the same quarter a year before.
    change_from: Mapping[str, str] | None = None
    # The inventory quadrant's line the member reads (demand, production or inventory).
    line: str | None = None

    def matches(self, dimensions: Mapping[str, str]) -> bool:
        if self.partial:
            return all(dimensions.get(key) == value for key, value in self.dimensions.items())
        return dict(dimensions) == dict(self.dimensions)


@dataclass(frozen=True)
class Spread:
    """A value shown beside a key indicator, never counted: one member less another, or one
    less its level line."""

    name: str
    label: str
    formula: str
    of: tuple[str, ...]


@dataclass(frozen=True)
class Condition:
    """Readings that must all hold, of the main member unless ``member`` names another.

    A reading given several values holds for any of them. ``outpaces`` names a member
    this one must have risen more than since the period before. ``after_action`` asks the
    member's newest period to begin after the main member's latest action: a fall that
    came after the cut, not before it.
    """

    readings: Mapping[str, str | tuple[str, ...]]
    member: str | None = None
    outpaces: str | None = None
    after_action: bool = False


@dataclass(frozen=True)
class Annotation:
    """A note, turn hint or cap given when its conditions all hold (always without any)."""

    text: str
    when: tuple[Condition, ...] = ()


@dataclass(frozen=True)
class Cell:
    """One cell of a stage's expectations: the relation when any alternative holds.

    ``grace`` says its counterevidence needs the signal held past the indicator's grace.
    """

    relation: str
    when: tuple[Condition, ...]
    note: Annotation | None = None
    turn_hint: Annotation | None = None
    grace: bool = False
    # Confirms the turn within grace: the main member's substantial change passed on, as
    # the cell names it (none of the first rules does).
    confirmed_when: Annotation | None = None


@dataclass(frozen=True)
class Expectation:
    """A stage's expectations of a key indicator.

    Its cells are tried in order; ``notes`` and ``turn_hints`` are told whichever cell
    answers, and a cap holding takes support or counterevidence to observation only.
    """

    proposition: str
    cells: tuple[Cell, ...]
    notes: tuple[Annotation, ...] = ()
    turn_hints: tuple[Annotation, ...] = ()
    caps: tuple[Annotation, ...] = ()


@dataclass(frozen=True)
class QuadrantRule:
    """The inventory quadrant: each line's main member, and the quadrant each set of the
    lines' directions names (``quadrants``); any other set is unclassified.

    A line's direction is its main member's momentum, read at the newest month the three
    main members all hold against the month before it; the quadrant's months pass over
    those a main member is never released for (``skipped``: January), so the three lines
    read the same months. A line out sooner (the PMI, at month end) is read back
    ``align`` months more than the others: it waits on them.
    """

    mains: Mapping[str, str]
    quadrants: Mapping[str, Mapping[str, str]]
    align: int
    skipped: frozenset[int]

    def before(self, month: str) -> str:
        """The quadrant's month before ``month`` (``YYYY-MM``)."""
        earlier = month_back(month, 1)
        while int(earlier[5:7]) in self.skipped:
            earlier = month_back(earlier, 1)
        return earlier


@dataclass(frozen=True)
class KeyIndicator:
    """A key indicator: its members, its periods (months, quarters or runs of sessions) and
    its timing.

    ``lookback`` periods are read for its readings and ``grace`` more before them, so
    each of the newest ``grace`` + 1 periods reads as it stood: of the main member, and of
    any other a turn hint reads. A policy indicator read as ``actions`` reads its members'
    actions in the evidence window of ``window_sessions`` sessions, each month of grace as
    it stood at that month's end; a daily one, periods of ``period_sessions`` sessions,
    against the value ``line`` has in force at each period's end when it names one.
    """

    key: str
    name: str
    dimension: str
    metric_id: str
    main: Member
    auxiliary: tuple[Member, ...]
    # Shown, never counted nor agreeing: a value derived from the members.
    derived: tuple[Spread, ...]
    level_line: float | None
    lookback: int
    expectations: Mapping[str, Expectation]
    timing: str
    grace: int
    frequency: str = "monthly"
    # The farthest period back anything is read: grace reads no further (ADR-0035).
    horizon: int = 13
    # Read from the value in force before each action ("level") or each event's own
    # change ("change"); an event's released funds, of ``released``.
    actions: str | None = None
    window_sessions: int = 120
    released: Mapping[str, str] | None = None
    period_sessions: int | None = None
    line: Member | None = None
    # A rate announced in a notice each session: the notices that show a day was read.
    notices: Member | None = None
    # The periods a year's range spans, and those whose changes tell a marked one.
    year: int = YEAR_MONTHS
    marked: int = YEAR_MONTHS
    # The inventory quadrant, read of its lines' members (its auxiliary ones, each of its
    # line); its main member stands for the quadrant and is read of no evidence.
    quadrant: QuadrantRule | None = None

    @property
    def members(self) -> tuple[Member, ...]:
        return (self.main, *self.auxiliary)

    @property
    def step(self) -> int:
        """The months one period spans."""
        return _MONTHS[self.frequency]

    @property
    def unit(self) -> str:
        return _UNITS[self.frequency]

    def history(self, member: Member) -> int:
        """How many periods before the newest ``member`` is read as it stood then."""
        named = {
            condition.member
            for expectation in self.expectations.values()
            for hint in (
                *expectation.turn_hints,
                *(cell.turn_hint for cell in expectation.cells if cell.turn_hint is not None),
            )
            for condition in hint.when
        }
        if self.quadrant is not None:
            # A line's members are read at each month the quadrant is, as it stood.
            return self.grace if member is self.main else 0
        return self.grace if member is self.main or member.name in named else 0

    def reach(self, member: Member) -> int:
        """How many periods back ``member`` is read in all: its own and its grace's, up to
        the horizon. A period grace reads that needs one beyond reads that one unknown.

        A derived member's period reads its inputs back to their farthest offset: only
        the periods whose inputs all lie within the horizon are read (loans: t alone).
        A quadrant line's member reads the quadrant's months back from its own newest:
        its lookback and grace, the months it may wait on the other lines, and those the
        quadrant passes over.
        """
        if self.quadrant is not None:
            months = self.lookback + self.grace + self.quadrant.align + len(self.quadrant.skipped)
            return min(months, self.horizon + 1)
        read = min(self.periods(member) + self.history(member), self.horizon + 1)
        if member.formula is not None:
            read = min(read, self.horizon + 1 - DERIVED_FORMULAS[member.formula].farthest)
        return read

    def periods(self, member: Member) -> int:
        """How many periods back ``member`` is read: the indicator's, or an auxiliary's."""
        if member is self.main:
            return self.lookback
        if member.formula is not None:
            return DERIVED_FORMULAS[member.formula].months
        return min(self.lookback, AUXILIARY_MONTHS)


@dataclass(frozen=True)
class TimingRules:
    """How timing points a turn, and when a turn signal forms (ADR-0037).

    ``adjacent`` names, by timing, the stage whose support form tells a lag (the previous)
    or a lead (the next). A signal holding ``forming_periods`` periods, or the leading
    indicators turning toward one stage being ``forming_signals`` or more, is forming.
    """

    adjacent: Mapping[str, str]
    forming_periods: int
    forming_signals: int


@dataclass(frozen=True)
class ConfirmationRules:
    """A model's frozen confirmation rules: its key indicators and their expectations."""

    output_structure: str
    macro_rules_version: str
    indicators: tuple[KeyIndicator, ...]
    timing: TimingRules
    # The registered warrants' frozen conversions, read as a note on inventory.
    warrants: WarrantRules | None = None
    # What is shown beside the dimension summary, never counted: the observation
    # interfaces, the price internal consistency and the supply-demand note (ticket 09).
    prices: PriceRules | None = None
    # What drives the bond's trend, told beside its state, never counted (ticket 10).
    attribution: AttributionRules | None = None

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, object]) -> ConfirmationRules | None:
        """The manifest's rules; None for a manifest without them, read the old way."""
        if not any(field in manifest for field in MANIFEST_FIELDS):
            return None
        if (
            manifest.get("macro_rules_version") != MACRO_RULES_VERSION
            or manifest.get("projection_output_structure") != OUTPUT_STRUCTURE
        ):
            raise ValueError("confirmation_rules_version_unsupported")
        document = manifest.get("confirmation_rules")
        if not isinstance(document, Mapping):
            raise ValueError("confirmation_rules_invalid")
        raw = document.get("key_indicators")
        if not isinstance(raw, list) or not raw:
            raise ValueError("confirmation_rules_invalid")
        grace, horizon, scale, timing = _timing_rules(
            document.get("timing_rules"), document.get("maturity_rules")
        )
        keys = [item.get("key") for item in raw if isinstance(item, Mapping)]
        indicators = tuple(
            _indicator(item, grace, horizon, scale, [str(key) for key in keys]) for item in raw
        )
        if len({item.key for item in indicators}) != len(indicators):
            raise ValueError("confirmation_key_indicator_duplicate")
        conversions = document.get("warrant_conversions")
        warrants = WarrantRules.parse(conversions) if conversions is not None else None
        prices = (
            PriceRules.parse(
                document,
                stages=_STAGES,
                members={item.key: {member.name for member in item.members} for item in indicators},
            )
            # The three come together: none of them alone escapes the checks below.
            if any(name in document for name in _PRICE_BLOCKS)
            else None
        )
        attribution = (
            AttributionRules.parse(
                document["bond_attribution"],
                indicators={item.key: (item.name, item.dimension) for item in indicators},
                acting={item.key for item in indicators if item.actions is not None},
            )
            if "bond_attribution" in document
            else None
        )
        rules = cls(
            OUTPUT_STRUCTURE, MACRO_RULES_VERSION, indicators, timing, warrants, prices, attribution
        )
        if prices is not None and rules.metric_ids() & (
            prices.interface_metrics | set(prices.cores.values())
        ):
            # The cores' own kinds are shown under them, never counted (ADR-0037).
            raise ValueError("confirmation_observation_interface_counted")
        return rules

    def metric_ids(self) -> frozenset[str]:
        """Every metric the indicators read: their members', their formulas' inputs and
        their level lines'."""
        return frozenset(
            metric_id
            for indicator in self.indicators
            for member in (
                *indicator.members,
                *(item for item in (indicator.line, indicator.notices) if item is not None),
            )
            for metric_id in (
                [item.metric_id for item in DERIVED_FORMULAS[member.formula].inputs]
                if member.formula is not None
                else [SESSION_FORMULAS[member.session_formula].metric_id]
                if member.session_formula is not None
                else [member.metric_id]
            )
        )


@dataclass(frozen=True)
class MemberReading:
    """One member's readings over its newest periods, oldest first.

    ``points`` are (period end, value, observation version) of the periods held of the
    lookback, a month never released for the member passed over; ``missing`` the months
    (``YYYY-MM``) of it that are not held. ``months`` is how many periods back it was read:
    a year of months reads where the value stands and how large its change is. A derived
    member's points carry its formula for a version; ``inputs`` are the observations it
    was derived from. ``earlier`` is the member read as it stood at each period before the
    newest, the nearest first, as far as grace reaches.
    """

    member: Member
    role: str
    evidence_status: str
    points: tuple[tuple[str, float, str], ...]
    missing: tuple[str, ...]
    level_line: float | None
    months: int = AUXILIARY_MONTHS
    inputs: tuple[str, ...] = ()
    earlier: tuple[MemberReading, ...] = ()
    # The periods a year's range spans, and those whose changes tell a marked one.
    year: int = YEAR_MONTHS
    marked: int = YEAR_MONTHS

    def observation_versions(self) -> tuple[str, ...]:
        """Every observation the reading rests on, as it stands and as it stood before."""
        own = self.inputs or tuple(version for _period, _value, version in self.points)
        return tuple(
            dict.fromkeys(
                (*own, *(v for item in self.earlier for v in item.observation_versions()))
            )
        )

    def extra(self) -> dict[str, object]:
        """What a reading of its own kind shows beside the common readings."""
        return {}

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(value for _period, value, _version in self.points)

    @property
    def period(self) -> str | None:
        """The newest period held (its end), when the newest of the lookback is."""
        return self.points[-1][0] if self.points else None

    def before(self, periods: int) -> MemberReading | None:
        """The member as it stood ``periods`` periods before the newest; None past grace."""
        if periods == 0:
            return self
        return self.earlier[periods - 1] if periods <= len(self.earlier) else None

    @property
    def change(self) -> float | None:
        values = self.values
        return values[-1] - values[-2] if len(values) >= 2 else None

    @property
    def level(self) -> str | None:
        if not self.points or self.level_line is None:
            return None
        return _side(self.values[-1], self.level_line)

    @property
    def momentum(self) -> str | None:
        values = self.values
        return _direction(values[-1], values[-2]) if len(values) >= 2 else None

    @property
    def run(self) -> str | None:
        """Whether the two newest changes alike went up or down, as a rise kept on."""
        values = self.values
        if len(values) < 3:
            return None
        moves = {_direction(values[-2], values[-3]), _direction(values[-1], values[-2])}
        return moves.pop() if len(moves) == 1 and "flat" not in moves else "none"

    @property
    def direction(self) -> str | None:
        """What the member agrees with the main one by: its momentum, or its sign."""
        formula = DERIVED_FORMULAS.get(self.member.formula or "")
        if formula is None or formula.agrees_by == "momentum":
            return self.momentum
        if not self.points:
            return None
        return _direction(self.values[-1], 0.0)

    @property
    def slope(self) -> str | None:
        """The change against the one before: steeper, slower, a turn, or flat.

        Alike in sign and wider is steeper, narrower slower; opposite is a turn. With no
        change on either side, or the same one, the slope is flat.
        """
        values = self.values
        if len(values) < 3:
            return None
        earlier = _direction(values[-2], values[-3])
        later = _direction(values[-1], values[-2])
        if "flat" in {earlier, later}:
            return "flat"
        if earlier != later:
            return "turn"
        widened = _direction(abs(values[-1] - values[-2]), abs(values[-2] - values[-3]))
        return {"up": "steeper", "down": "slower", "flat": "flat"}[widened]

    @property
    def crossed(self) -> str | None:
        """Whether the newest period crossed the line from the one before: above, below.

        From on the line counts: 50.0 to 50.4 has just crossed above 50.
        """
        values = self.values
        if len(values) < 2 or self.level_line is None:
            return None
        before, now = _side(values[-2], self.level_line), _side(values[-1], self.level_line)
        if before != "above" and now == "above":
            return "above"
        if before != "below" and now == "below":
            return "below"
        return "none"

    @property
    def position(self) -> str | None:
        """Where the newest value stands in the year's range: its upper, middle or lower third.

        Only over a whole year held; a range with no width has no upper or lower third.
        """
        values = self._year(self.year)
        if values is None:
            return None
        low, high = min(values), max(values)
        if _direction(high, low) == "flat":
            return "middle"
        third = (high - low) / 3
        if _direction(values[-1], high - third) != "down":
            return "high"
        if _direction(values[-1], low + third) != "up":
            return "low"
        return "middle"

    @property
    def change_size(self) -> str | None:
        """Marked when the newest change is wider than the median change of the year's
        newest periods: twelve months or runs of sessions, four quarters."""
        values = self._year(self.marked)
        if values is None or len(values) < 3:
            return None
        sizes = [abs(after - before) for before, after in zip(values, values[1:], strict=False)]
        marked = _direction(sizes[-1], statistics.median(sizes)) == "up"
        return "marked" if marked else "ordinary"

    def _year(self, periods: int) -> tuple[float, ...] | None:
        """The newest ``periods`` periods' values, when the lookback reads and holds them all."""
        if self.months < periods or self.missing or not self.points:
            return None
        return self.values[-periods:]

    def reading(self, name: str) -> str | None:
        return getattr(self, name)  # type: ignore[no-any-return]

    def gaps(self) -> tuple[str, ...]:
        """What the reading misses, each named by the member it is missing of."""
        return tuple(f"{_member_label(self.member)}:{item}" for item in self.missing)


@dataclass(frozen=True)
class Action:
    """A cut or a hike on ``period``: its change, and for an RRR the funds it released."""

    period: str
    kind: str
    change: float
    released: float | None = None


_ACTION_DIRECTIONS = {"cut": "down", "hike": "up", "none": "flat"}


@dataclass(frozen=True)
class ActionReading(MemberReading):
    """A policy member read as its actions in the evidence window from ``window_start``.

    ``points`` are the values held from ``baseline``, the one in force before the window,
    on; ``actions`` each cut or hike in the window, oldest first. No action there is none,
    which needs the baseline (``missing`` says when it is not held): a value read on the
    window's first day may be a change from it. Its direction, for agreement, is the
    action's: a cut down, a hike up.
    """

    actions: tuple[Action, ...] = ()
    baseline: tuple[str, float, str] | None = None
    window_start: str | None = None

    @property
    def action(self) -> str | None:
        if self.evidence_status != "current" or self.missing:
            return None
        return self.actions[-1].kind if self.actions else "none"

    @property
    def momentum(self) -> str | None:
        return _ACTION_DIRECTIONS.get(self.action or "")

    @property
    def change(self) -> float | None:
        return None

    def extra(self) -> dict[str, object]:
        return {
            "action": self.action,
            "actions": [
                {
                    "period": item.period,
                    "action": item.kind,
                    "change": item.change,
                    "released": item.released,
                }
                for item in self.actions
            ],
            "baseline": (
                {"period": self.baseline[0], "value": self.baseline[1]}
                if self.baseline is not None
                else None
            ),
            "window_start": self.window_start,
        }

    # An action has no level, slope, run, crossing or range: those read values over periods.
    @property
    def level(self) -> str | None:
        return None

    @property
    def slope(self) -> str | None:
        return None

    @property
    def run(self) -> str | None:
        return None

    @property
    def crossed(self) -> str | None:
        return None

    @property
    def position(self) -> str | None:
        return None

    @property
    def change_size(self) -> str | None:
        return None


@dataclass(frozen=True)
class BlockReading(MemberReading):
    """A daily member read in periods of ``sessions`` sessions, oldest first.

    Each point is a period's mean (a rate) or sum (a flow), dated by its last session;
    ``inputs`` are the observations they rest on. ``lines`` are the level line in force at
    each period's end -- the policy rate DR007 is read against -- None where not known.
    """

    sessions: int = 5
    lines: tuple[float | None, ...] = ()
    # Each period's first session.
    starts: tuple[str, ...] = ()

    @property
    def level(self) -> str | None:
        if not self.points:
            return None
        line = self.lines[-1] if self.lines else self.level_line
        return _side(self.values[-1], line) if line is not None else None

    @property
    def crossed(self) -> str | None:
        return None

    def extra(self) -> dict[str, object]:
        return {
            "period_sessions": self.sessions,
            "aggregate": self.member.aggregate,
            "lines": list(self.lines),
        }


# Derived observations a note may read, outside any key indicator and never counted: the
# credit impulse, whose direction is its own (ADR-0035: the month against the month before).
OBSERVED_METRICS = frozenset({"CN_CREDIT_IMPULSE"})


@dataclass(frozen=True)
class ObservedReading(MemberReading):
    """A derived observation as the projection shows it: its newest value and the
    direction its formula states, which is its momentum."""

    stated: str | None = None

    @property
    def momentum(self) -> str | None:
        return self.stated if self.points else None


@dataclass(frozen=True)
class QuadrantReading(MemberReading):
    """The inventory quadrant at ``month``: each line's main member read there and at the
    quadrant's month before (``lines``), and the quadrant their directions name.

    ``missing`` is what each line misses, by its line: a month not held, or its evidence
    out of date. With any line's direction not known the quadrant is not known --
    unclassified for want of data, and the indicator unconfirmed; known directions no
    quadrant names are unclassified, and only observed.
    """

    month: str | None = None
    lines: Mapping[str, MemberReading] = field(default_factory=dict)
    table: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    @classmethod
    def of(
        cls,
        member: Member,
        month: str | None,
        lines: Mapping[str, MemberReading],
        table: Mapping[str, Mapping[str, str]],
    ) -> QuadrantReading:
        missing: list[str] = []
        for line, reading in lines.items():
            if reading.evidence_status != "current":
                missing.append(f"{line}:{_member_label(reading.member)}:{reading.evidence_status}")
            missing.extend(f"{line}:{gap}" for gap in reading.gaps())
        status = next(
            (item.evidence_status for item in lines.values() if item.evidence_status != "current"),
            "current",
        )
        return cls(
            member,
            "main",
            status,
            (),
            tuple(dict.fromkeys(missing)),
            None,
            2,
            tuple(dict.fromkeys(v for item in lines.values() for v in item.observation_versions())),
            month=month,
            lines=dict(lines),
            table=table,
        )

    @property
    def period(self) -> str | None:
        return month_end(self.month) if self.month is not None else None

    @property
    def quadrant(self) -> str | None:
        if self.missing or self.evidence_status != "current":
            return None
        directions = {line: reading.momentum for line, reading in self.lines.items()}
        if None in directions.values():
            return None
        return next(
            (name for name, named in self.table.items() if dict(named) == directions),
            "unclassified",
        )

    def gaps(self) -> tuple[str, ...]:
        return self.missing

    def extra(self) -> dict[str, object]:
        quadrant = self.quadrant
        return {
            # Unclassified for want of data, or for directions no quadrant names.
            "quadrant": quadrant or "unclassified",
            "unclassified_by": (
                "insufficient"
                if quadrant is None
                else "inconsistent"
                if quadrant == "unclassified"
                else None
            ),
            "lines": {
                line: {
                    "member": reading.member.name,
                    "label": reading.member.label,
                    "period": reading.period,
                    "direction": reading.momentum,
                }
                for line, reading in self.lines.items()
            },
        }


@dataclass(frozen=True)
class ChangeReading(MemberReading):
    """A member whose change is the one its source states: ``changes``, of the member
    ``change_from`` names, each the change of a point on the same period a year before.

    Its momentum is that change's sign, its run and slope those of the newest two, and a
    marked change is wider than the median of the year's. Its level and range read its own
    values. ``change_gaps`` are the months of ``missing`` the change is missing in.
    """

    changes: tuple[float, ...] = ()
    change_gaps: tuple[str, ...] = ()

    @property
    def change(self) -> float | None:
        return self.changes[-1] if self.changes else None

    @property
    def momentum(self) -> str | None:
        return _direction(self.changes[-1], 0.0) if self.changes else None

    @property
    def run(self) -> str | None:
        if len(self.changes) < 2:
            return None
        moves = {_direction(change, 0.0) for change in self.changes[-2:]}
        return moves.pop() if len(moves) == 1 and "flat" not in moves else "none"

    @property
    def slope(self) -> str | None:
        """Alike in sign and wider than the change before is steeper, narrower slower;
        opposite is a turn; with either no change, flat."""
        if len(self.changes) < 2:
            return None
        earlier, later = (_direction(change, 0.0) for change in self.changes[-2:])
        if "flat" in {earlier, later}:
            return "flat"
        if earlier != later:
            return "turn"
        widened = _direction(abs(self.changes[-1]), abs(self.changes[-2]))
        return {"up": "steeper", "down": "slower", "flat": "flat"}[widened]

    @property
    def change_size(self) -> str | None:
        if self._year(self.marked) is None or len(self.changes) < self.marked:
            return None
        sizes = [abs(change) for change in self.changes[-self.marked :]]
        return "marked" if _direction(sizes[-1], statistics.median(sizes)) == "up" else "ordinary"

    def extra(self) -> dict[str, object]:
        assert self.member.change_from is not None
        return {"change_from": dict(self.member.change_from), "changes": list(self.changes)}

    def gaps(self) -> tuple[str, ...]:
        assert self.member.change_from is not None
        changed = replace(self.member, dimensions=self.member.change_from)
        return tuple(
            f"{_member_label(changed if item in self.change_gaps else self.member)}:{item}"
            for item in self.missing
        )


def confirmation_document(
    rules: ConfirmationRules,
    readings: Mapping[str, Sequence[MemberReading]],
    *,
    current_stage: FormalStage | None,
    stage_reason: str,
    observed: Mapping[str, MemberReading] | None = None,
) -> dict[str, object]:
    """The dimension summary of the rules' indicators read as ``readings`` under the stage.

    ``readings`` holds each indicator's members by its key, the main one first;
    ``observed`` each derived observation a note may read, by its metric.
    """
    stage = current_stage.value if current_stage is not None else None
    # Another indicator a condition names is read by its main member, when its every
    # reading is known (DR007 passing on a cut).
    others = {
        _other(item.key): main
        for item in rules.indicators
        if (main := readings[item.key][0]).evidence_status == "current"
        and (main.points or isinstance(main, ActionReading))
        and not main.missing
    } | {_observed(metric_id): reading for metric_id, reading in (observed or {}).items()}
    documents = [
        _indicator_document(
            item, readings[item.key], stage=stage, timing=rules.timing, others=others
        )
        for item in rules.indicators
    ]
    _leading_together(rules, documents)
    dimensions = []
    for dimension in DIMENSIONS:
        own = [document for document in documents if document["dimension"] == dimension]
        dimensions.append(
            {
                "dimension": dimension,
                "status": "connected" if own else "not_connected",
                "counts": (
                    {
                        relation: sum(1 for item in own if item["relation"] == relation)
                        for relation in RELATIONS
                    }
                    if own
                    else None
                ),
                "key_indicators": own,
            }
        )
    return {
        "macro_rules_version": MACRO_RULES_VERSION,
        "stage": stage,
        "stage_reason": stage_reason,
        "applicable": stage is not None,
        "dimensions": dimensions,
    }


def derived_points(
    formula: str,
    months: Sequence[str],
    value: Callable[[DerivedInput, str], tuple[float, str] | None],
    *,
    oldest: str | None = None,
) -> tuple[tuple[tuple[str, float, str], ...], tuple[str, ...], tuple[str, ...]]:
    """``formula`` for each of ``months`` (``YYYY-MM``, oldest first), from its inputs.

    ``value`` gives an input's (value, observation version) of a month, or None. The
    points run from the newest back while every input a month needs is held. Missing are
    the input months (``YYYY-MM``) a month needs and are not held -- those before
    ``oldest`` alone when it needs any, as they are never read -- and the observations the
    points rest on are their inputs.
    """
    definition = DERIVED_FORMULAS[formula]
    points: list[tuple[str, float, str]] = []
    missing: list[str] = []
    inputs: list[str] = []
    for month in reversed(months):
        held: dict[tuple[str, int], float] = {}
        versions: list[str] = []
        needs = set(definition.needs(month))
        beyond = sorted(
            {
                month_back(month, offset)
                for _name, offset in needs
                if oldest is not None and month_back(month, offset) < oldest
            }
        )
        short: list[str] = []
        for item in definition.inputs:
            for offset in item.offsets:
                period = month_back(month, offset)
                found = value(item, period) if oldest is None or period >= oldest else None
                if found is not None:
                    held[(item.name, offset)] = found[0]
                    versions.append(found[1])
                elif (item.name, offset) in needs:
                    short.append(period)
        # The formula takes what the month needs of its inputs: January's flow is its own
        # year-to-date total, with no month before it.
        result = definition.compute(month, held) if not short else None
        if result is None:
            missing.extend(beyond or short or [month])
        elif not missing:
            points.insert(0, (month_end(month), result, formula))
            inputs.extend(versions)
    return tuple(points), tuple(sorted(set(missing))), tuple(dict.fromkeys(inputs))


def month_back(month: str, offset: int) -> str:
    """The month (``YYYY-MM``) ``offset`` months before ``month``."""
    year, number = (int(part) for part in month.split("-"))
    ordinal = year * 12 + number - 1 - offset
    return f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"


def month_end(month: str) -> str:
    """The last day (ISO) of ``month`` (``YYYY-MM``)."""
    year, number = (int(part) for part in month.split("-"))
    return f"{month}-{calendar.monthrange(year, number)[1]:02d}"


def _observed(metric_id: str) -> str:
    """How a condition names a derived observation: the credit impulse."""
    return f"#{metric_id}"


def _other(key: str) -> str:
    """How a condition names another key indicator among an indicator's own members."""
    return f"@{key}"


def _indicator_document(
    indicator: KeyIndicator,
    members: Sequence[MemberReading],
    *,
    stage: str | None,
    timing: TimingRules,
    others: Mapping[str, MemberReading],
) -> dict[str, object]:
    main, auxiliary = members[0], tuple(members[1:])
    if indicator.quadrant is not None:
        # A line's member agrees or not with its line's main member, which is the line's.
        mains = set(indicator.quadrant.mains.values())
        lines = {item.member.line: item for item in auxiliary if item.member.name in mains}
        agreement = [
            "main" if member.member.name in mains else _agreement(lines[member.member.line], member)
            for member in auxiliary
        ]
        known = main.reading("quadrant") is not None
    else:
        agreement = [_agreement(main, member) for member in auxiliary]
        known = main.direction is not None
    divergent = "opposes" in agreement
    by_member = {**others, **{member.member.name: member for member in members}}
    document: dict[str, object] = {
        "key": indicator.key,
        "name": indicator.name,
        "dimension": indicator.dimension,
        "metric_id": indicator.metric_id,
        "timing": indicator.timing,
        # What the indicator counts for: its newest period, however many days read it.
        "statistical_period": main.period,
        "level_line": indicator.level_line,
        "consistency": ("unknown" if not known else "divergent" if divergent else "consistent"),
        "members": [
            _member_document(main, "main"),
            *(
                _member_document(member, state)
                for member, state in zip(auxiliary, agreement, strict=True)
            ),
        ],
        "derived": [_derived_document(item, by_member) for item in indicator.derived],
        "relation": "not_applicable",
        "proposition": None,
        "matched": None,
        "notes": [],
        "turn_hint": None,
        "turn": None,
        "grace": None,
        "divergence_capped": False,
        "capped_by": [],
        "missing": [],
    }
    if stage is None:
        return document
    # An action read with nothing held is none: its events traced, none found (ADR-0028).
    # The quadrant holds no value of its own: its lines say what they miss.
    readable = bool(main.points) or isinstance(main, (ActionReading, QuadrantReading))
    if main.evidence_status != "current" or not readable or main.missing:
        # Every reading of the main member is known, or none is said: a month short of
        # its lookback leaves a momentum, a slope or a year's range unknown, never read
        # as a direction.
        status = (
            [main.evidence_status]
            if not isinstance(main, QuadrantReading)
            and (main.evidence_status != "current" or not (main.points or main.missing))
            else []
        )
        missing = [f"{_member_label(main.member)}:{item}" for item in status]
        return {**document, "relation": "unconfirmed", "missing": [*missing, *main.gaps()]}
    expectation = indicator.expectations[stage]
    cell, condition, known = _answer(expectation, main, by_member)
    if not known and cell is not None:
        # An earlier cell may hold: what it reads is not known, so nothing is said.
        missing = [f"{_member_label(main.member)}:{_unknown_readings(cell, main)}"]
        return {**document, "relation": "unconfirmed", "missing": missing}
    relation = cell.relation if cell is not None else "observation_only"
    # A lag or a lead: the reading is the support form of the stage its timing points to.
    adjacent = (
        _adjacent(indicator, stage, main, by_member, timing) if relation != "support" else None
    )
    graced = (
        cell is not None and relation == "counterevidence" and (cell.grace or adjacent is not None)
    )
    cell_hint = (
        cell.turn_hint
        if cell is not None
        and cell.turn_hint is not None
        and _annotated(cell.turn_hint, main, by_member)
        else None
    )
    stage_hint = next(
        (hint for hint in expectation.turn_hints if _annotated(hint, main, by_member)), None
    )
    toward, basis = (
        (cell_hint.text, "expectation")
        if cell_hint is not None
        else (stage_hint.text, "expectation")
        if stage_hint is not None
        else (adjacent, indicator.timing)
        if adjacent is not None
        else (None, None)
    )
    # A hint tells the stage approached; a lag, the stage still shown.
    document["turn_hint"] = toward if basis in {"expectation", "leading"} else None
    if graced or toward is not None:
        # How long each signal has held, read back period by period as each stood. The
        # grace counts the stage still answering with the cell met, and a lag or a lead
        # that makes it wait still in its form; the turn, the hint's own conditions too,
        # or the stage's hint alone, which reads a member of its own.
        def answered(main: MemberReading, by_member: Mapping[str, MemberReading]) -> bool | None:
            met, _condition, known = _answer(expectation, main, by_member)
            return met is cell if known else None

        def form(
            other: str, main: MemberReading, by_member: Mapping[str, MemberReading]
        ) -> bool | None:
            met, _condition, known = _answer(indicator.expectations[other], main, by_member)
            return met is not None and met.relation == "support" if known else None

        def grace_signal(
            main: MemberReading, by_member: Mapping[str, MemberReading]
        ) -> bool | None:
            parts = [answered(main, by_member)]
            if cell is not None and not cell.grace and adjacent is not None:
                parts.append(form(adjacent, main, by_member))
            return _all(parts)

        def turn_signal(main: MemberReading, by_member: Mapping[str, MemberReading]) -> bool | None:
            if stage_hint is not None and cell_hint is None:
                return _annotation_state(stage_hint, main, by_member)
            parts = [answered(main, by_member)]
            if cell_hint is not None:
                parts.append(_annotation_state(cell_hint, main, by_member))
            if basis in {"leading", "lagging"} and toward is not None:
                parts.append(form(toward, main, by_member))
            return _all(parts)

        # Confirmed within grace: the main indicator changed in substance and passed it on,
        # as the cell names (ADR-0037).
        transmitted = (
            cell is not None
            and cell.confirmed_when is not None
            and _annotated(cell.confirmed_when, main, by_member)
        )
        held, since, at_least, unknown = _run(turn_signal, members, indicator.grace)
        document["turn"] = {
            "toward": toward,
            "basis": basis,
            **_maturity(held, unknown, transmitted, indicator.grace, timing),
            # Read no further back than past grace: a signal held longer is held at least
            # that long, from a period not read.
            "periods": held,
            "at_least": at_least,
            "since": since,
            "leading_signals": [],
            "missing": list(unknown),
        }
        if graced:
            held, since, at_least, unknown = _run(grace_signal, members, indicator.grace)
            past = True if transmitted else None if unknown else held > indicator.grace
            document["grace"] = {
                "limit": indicator.grace,
                "unit": indicator.unit,
                "periods": held,
                "at_least": at_least,
                "since": since,
                "past": past,
                "confirmed_by": _maturity(held, unknown, transmitted, indicator.grace, timing)[
                    "confirmed_by"
                ],
            }
            if past is None:
                # Within grace or past it is not known: neither relation is said.
                return {**document, "relation": "unconfirmed", "missing": list(unknown)}
            relation = "counterevidence" if past else "observation_only"
    document["proposition"] = expectation.proposition
    caps = [cap for cap in expectation.caps if _annotated(cap, main, by_member)]
    notes = (cell.note,) if cell is not None and cell.note is not None else ()
    document["notes"] = [
        note.text
        for note in (*notes, *expectation.notes, *caps)
        if _annotated(note, main, by_member)
    ]
    if cell is None or condition is None:
        # Known, and no cell of the stage names it: related, not counted.
        return {**document, "relation": "observation_only"}
    if relation in {"support", "counterevidence"} and (divergent or caps):
        # Each says why the relation is no higher than observation only.
        document["divergence_capped"] = divergent
        document["capped_by"] = [cap.text for cap in caps]
        relation = "observation_only"
    document["matched"] = {
        name: list(value) if isinstance(value, tuple) else value
        for name, value in condition.readings.items()
    }
    return {**document, "relation": relation}


def _answer(
    expectation: Expectation, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> tuple[Cell | None, Condition | None, bool]:
    """The first cell that holds and the alternative met, and whether that is known.

    A cell whose reading is not known before one holds leaves the answer unknown, that
    cell given: an earlier cell may hold. None holding answers no cell.
    """
    for cell in expectation.cells:
        holds = [_holds(condition, main, by_member) for condition in cell.when]
        hit = next(
            (condition for condition, held in zip(cell.when, holds, strict=True) if held), None
        )
        if hit is not None:
            return cell, hit, True
        if None in holds:
            return cell, None, False
    return None, None, True


def _adjacent(
    indicator: KeyIndicator,
    stage: str,
    main: MemberReading,
    by_member: Mapping[str, MemberReading],
    timing: TimingRules,
) -> str | None:
    """The stage a lag or a lead shows, or None.

    A lagging indicator still in the previous stage's support form, a leading one already
    in the next's: that stage's cells answer support for the reading.
    """
    direction = timing.adjacent.get(indicator.timing)
    if direction is None:
        return None
    other = _STAGES[(_STAGES.index(stage) + _ADJACENT[direction]) % len(_STAGES)]
    cell, _condition, _known = _answer(indicator.expectations[other], main, by_member)
    return other if cell is not None and cell.relation == "support" else None


def _run(
    signal: Callable[[MemberReading, Mapping[str, MemberReading]], bool | None],
    members: Sequence[MemberReading],
    grace: int,
) -> tuple[int, str | None, bool, tuple[str, ...]]:
    """For how many periods, the newest back, ``signal`` held, each read as it stood.

    Read up to one period past ``grace``. Returns the periods held; the first of them, or
    None when the run reaches back past what was read, held at least that long; whether
    it does; and, when a period's reading is not known before the run ends, what the
    members read back miss there.
    """
    held, since = 0, None
    for back in range(grace + 1):
        shifted = [member.before(back) for member in members]
        main = shifted[0]
        holds = (
            signal(main, {item.member.name: item for item in shifted if item is not None})
            if main is not None
            else None
        )
        if holds is None:
            return held, since, False, _run_missing(members, back)
        if not holds:
            return held, since, False, ()
        held, since = held + 1, main.period if main is not None else None
    return held, None, True, ()


def _run_missing(members: Sequence[MemberReading], back: int) -> tuple[str, ...]:
    """What the members read back miss ``back`` periods before the newest."""
    missing: list[str] = []
    for member in members:
        if member is not members[0] and not member.earlier:
            continue
        shifted = member.before(back)
        if shifted is not None and shifted.missing:
            missing.extend(shifted.gaps())
            continue
        gap = shifted.evidence_status if shifted is not None else "not_read"
        missing.append(f"{_member_label(member.member)}:{gap}")
    return tuple(dict.fromkeys(missing))


def _maturity(
    held: int, unknown: Sequence[str], transmitted: bool, grace: int, timing: TimingRules
) -> dict[str, str | None]:
    """A turn signal's maturity, and what confirmed it: passed on, or held past grace."""
    if transmitted:
        return {"maturity": "confirmed", "confirmed_by": "transmission"}
    if unknown:
        return {"maturity": None, "confirmed_by": None}
    if held > grace:
        return {"maturity": "confirmed", "confirmed_by": "grace"}
    forming = held >= timing.forming_periods
    return {"maturity": "forming" if forming else "sprout", "confirmed_by": None}


def _all(parts: Sequence[bool | None]) -> bool | None:
    """True when every part holds: False wins over not known (None)."""
    return False if False in parts else None if None in parts else True


def _leading_together(rules: ConfirmationRules, documents: Sequence[dict[str, Any]]) -> None:
    """Leading indicators turning toward one stage together form, each a sprout or more."""
    together: dict[str, list[dict[str, Any]]] = {}
    for indicator, document in zip(rules.indicators, documents, strict=True):
        turn = document["turn"]
        if indicator.timing == "leading" and turn is not None and turn["toward"] is not None:
            together.setdefault(turn["toward"], []).append(document)
    for group in together.values():
        if len(group) < rules.timing.forming_signals:
            continue
        for document in group:
            turn = document["turn"]
            turn["leading_signals"] = [other["key"] for other in group if other is not document]
            if turn["maturity"] == "sprout":
                turn["maturity"] = "forming"


def _holds(
    condition: Condition, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> bool | None:
    """True, False, or None when a reading it needs is not known: False wins over None."""
    member = by_member.get(condition.member) if condition.member is not None else main
    if member is not None and member is not main and member.evidence_status != "current":
        # A member out of date says nothing of now: what it would read is not known.
        member = None
    results: list[bool | None] = []
    for name, expected in condition.readings.items():
        actual = member.reading(name) if member is not None else None
        accepted = expected if isinstance(expected, tuple) else (expected,)
        results.append(None if actual is None else actual in accepted)
    if condition.outpaces is not None:
        other = by_member.get(condition.outpaces)
        if other is not None and other.evidence_status != "current":
            other = None
        changes = (
            member.change if member is not None else None,
            other.change if other is not None else None,
        )
        results.append(
            None if None in changes else changes[0] > changes[1]  # type: ignore[operator]
        )
    if condition.after_action:
        begun = member.starts[-1] if isinstance(member, BlockReading) and member.starts else None
        acted = (
            main.actions[-1].period if isinstance(main, ActionReading) and main.actions else None
        )
        results.append(None if begun is None or acted is None else begun > acted)
    if False in results:
        return False
    return None if None in results else True


def _annotated(
    annotation: Annotation, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> bool:
    return _annotation_state(annotation, main, by_member) is True


def _annotation_state(
    annotation: Annotation, main: MemberReading, by_member: Mapping[str, MemberReading]
) -> bool | None:
    """Whether every condition holds: False wins over not known (None)."""
    return _all([_holds(condition, main, by_member) for condition in annotation.when])


def _agreement(main: MemberReading, member: MemberReading) -> str:
    """How a member's direction stands to the main one's: agrees, opposes, flat, unknown;
    or not compared, for a member shown alone."""
    if not member.member.compared:
        return "not_compared"
    direction = member.direction
    if member.evidence_status != "current" or direction is None or main.direction is None:
        return "unknown"
    if direction == main.direction:
        return "agrees"
    if "flat" in {direction, main.direction}:
        return "flat"
    return "opposes"


def _member_document(member: MemberReading, consistency: str) -> dict[str, object]:
    latest = member.points[-1] if member.points else None
    return {
        **member.extra(),
        "role": member.role,
        "name": member.member.name,
        "label": member.member.label,
        "metric_id": member.member.metric_id,
        "member": dict(member.member.dimensions),
        "formula_version": member.member.formula,
        # The quadrant's line it reads, when it reads one.
        **({"line": member.member.line} if member.member.line is not None else {}),
        "evidence_status": member.evidence_status,
        "period": member.period,
        "value": latest[1] if latest is not None else None,
        "periods": [period for period, _value, _version in member.points],
        "values": list(member.values),
        "observation_version_ids": (
            list(member.inputs)
            if member.member.formula is not None or member.inputs
            else [version for _period, _value, version in member.points]
        ),
        "level": member.level,
        "momentum": member.momentum,
        "direction": member.direction,
        "agrees_by": (
            DERIVED_FORMULAS[member.member.formula].agrees_by
            if member.member.formula is not None
            else "momentum"
        ),
        "slope": member.slope,
        "run": member.run,
        "crossed": member.crossed,
        "position": member.position,
        "change_size": member.change_size,
        "consistency": consistency,
        "cumulative": member.member.cumulative,
        "missing": list(member.missing),
        # The periods read from the member standing in, as its label says (cumulative).
        "stand_ins": [
            {"period": period, "label": member.member.stand_in_label}
            for period, _value, _version in member.points
            if int(period[5:7]) in member.member.stand_ins
        ],
    }


def _derived_document(derived: Spread, by_member: Mapping[str, MemberReading]) -> dict[str, object]:
    """A spread of two members over the periods both hold, newest last, or of one member
    against its level line where that is known, in basis points; never counted."""
    first = by_member[derived.of[0]]
    if len(derived.of) == 1:
        lines = first.lines if isinstance(first, BlockReading) else ()
        points = [
            (period, (value - line) * 100)
            for (period, value, _version), line in zip(first.points, lines, strict=True)
            if line is not None
        ]
        inputs = [first.member.name]
    else:
        second = by_member[derived.of[1]]
        others = {period: value for period, value, _version in second.points}
        points = [
            (period, value - others[period])
            for period, value, _version in first.points
            if period in others
        ]
        inputs = [first.member.name, second.member.name]
    values = [value for _period, value in points]
    return {
        "name": derived.name,
        "label": derived.label,
        "formula_version": derived.formula,
        "inputs": inputs,
        "counted": False,
        "period": points[-1][0] if points else None,
        "value": values[-1] if values else None,
        "periods": [period for period, _value in points],
        "values": values,
        "momentum": _direction(values[-1], values[-2]) if len(values) >= 2 else None,
    }


def _unknown_readings(cell: Cell, main: MemberReading) -> str:
    names = sorted(
        {name for condition in cell.when for name in condition.readings}
        - {name for name in _READINGS if main.reading(name) is not None}
    )
    return "unknown_" + "_".join(names)


def _member_label(member: Member) -> str:
    """The member's dimensions, or its name when its metric has none or it is derived."""
    dimensions = member.dimensions
    return ",".join(f"{key}={value}" for key, value in sorted(dimensions.items())) or member.name


def _side(value: float, line: float) -> str:
    return {"up": "above", "down": "below", "flat": "at"}[_direction(value, line)]


def _direction(value: float, previous: float) -> str:
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    if value - previous > tolerance:
        return "up"
    if previous - value > tolerance:
        return "down"
    return "flat"


def _timing_rules(
    timing: object, maturity: object
) -> tuple[dict[str, int], dict[str, int], dict[str, tuple[int, int]], TimingRules]:
    """Grace and the farthest period back by frequency; the periods a year's range spans
    and those a marked change is told against (a daily range in sessions); the stage each
    timing points to, and when a signal forms."""
    if not isinstance(timing, Mapping) or not isinstance(maturity, Mapping):
        raise ValueError("confirmation_timing_rules_invalid")
    grace, adjacent = timing.get("grace_periods"), timing.get("adjacent_stage")
    horizon = timing.get("horizon_periods")
    year, marked = timing.get("year_periods"), timing.get("marked_periods")
    counts = [
        item.get(name)
        for item in (grace, horizon, year, marked)
        if isinstance(item, Mapping)
        for name in FREQUENCIES
    ]
    counts += [maturity.get("forming_periods"), maturity.get("forming_signals")]
    if (
        not isinstance(grace, Mapping)
        or not isinstance(horizon, Mapping)
        or not isinstance(year, Mapping)
        or not isinstance(marked, Mapping)
        or any(set(item) != set(FREQUENCIES) for item in (grace, horizon, year, marked))
        or not all(
            isinstance(item, int) and not isinstance(item, bool) and item >= 1 for item in counts
        )
        or not isinstance(adjacent, Mapping)
        or not set(adjacent) <= set(TIMINGS)
        or not set(adjacent.values()) <= set(_ADJACENT)
    ):
        raise ValueError("confirmation_timing_rules_invalid")
    return (
        {str(name): int(grace[name]) for name in FREQUENCIES},
        {str(name): int(horizon[name]) for name in FREQUENCIES},
        {str(name): (int(year[name]), int(marked[name])) for name in FREQUENCIES},
        TimingRules(
            {str(name): str(item) for name, item in adjacent.items()},
            int(maturity["forming_periods"]),
            int(maturity["forming_signals"]),
        ),
    )


def _indicator(
    value: object,
    grace: Mapping[str, int],
    horizon: Mapping[str, int],
    scale: Mapping[str, tuple[int, int]],
    keys: Collection[str],
) -> KeyIndicator:
    """A key indicator; a condition of its own may name another of ``keys``."""
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_key_indicator_invalid")
    texts = {}
    for name in ("key", "name", "dimension", "metric_id", "timing"):
        raw = value.get(name)
        if not isinstance(raw, str) or not raw:
            raise ValueError("confirmation_key_indicator_invalid")
        texts[name] = raw
    if texts["dimension"] not in DIMENSIONS:
        raise ValueError("confirmation_dimension_unknown")
    if texts["timing"] not in TIMINGS:
        raise ValueError("confirmation_timing_unknown")
    frequency = value.get("frequency", "monthly")
    if frequency not in FREQUENCIES:
        raise ValueError("confirmation_frequency_unknown")
    frequency = str(frequency)
    actions, released, raw_notices = (
        value.get("actions"),
        value.get("released"),
        value.get("notices"),
    )
    sessions = _count(value.get("period_sessions"))
    window = _count(value.get("window_sessions", 120))
    if (
        actions not in {None, "level", "change"}
        # A month of grace for an action, as it stood at the month's end.
        or (actions is not None and frequency != "monthly")
        or (released is not None and actions != "change")
        or (
            raw_notices is not None and (actions != "level" or not isinstance(raw_notices, Mapping))
        )
        or window is None
        or (frequency == "daily") != (sessions is not None)
        or ("period_sessions" in value and sessions is None)
    ):
        raise ValueError("confirmation_key_indicator_invalid")
    # Months are read up to a year, quarters up to four, sessions' periods up to 250
    # sessions.
    own = {
        "monthly": "lookback_months",
        "quarterly": "lookback_quarters",
        "daily": "lookback_periods",
    }[frequency]
    year, marked = scale[frequency]
    if sessions is not None:
        # A daily range is a year of sessions, read in the indicator's periods.
        year //= sessions
    raw_line, lookback = value.get("level_line"), _count(value.get(own))
    raw_auxiliary = value.get("auxiliary")
    raw_derived = value.get("derived", [])
    expectations = value.get("expectations")
    if (
        (
            raw_line is not None
            and not isinstance(raw_line, Mapping)
            and (not isinstance(raw_line, (int, float)) or isinstance(raw_line, bool))
        )
        or (isinstance(raw_line, Mapping) and frequency != "daily")
        or lookback is None
        or lookback > year
        or any(name in value for name in _LOOKBACK_FIELDS - {own})
        or not isinstance(raw_auxiliary, list)
        or not isinstance(raw_derived, list)
        or not isinstance(expectations, Mapping)
        or set(expectations) != set(_STAGES)
    ):
        raise ValueError("confirmation_key_indicator_invalid")
    periods_grace, farthest = grace[frequency], horizon[frequency]
    if lookback - 1 > farthest:
        # Grace reads each period as it stood as far as the horizon; the readings never
        # beyond it.
        raise ValueError("confirmation_lookback_beyond_horizon")
    quadrant: QuadrantRule | None = None
    if "quadrant" in value:
        # The quadrant's lines are its members; it reads its month and the one before.
        if (
            "main" in value
            or raw_auxiliary
            or actions is not None
            or frequency != "monthly"
            or raw_line is not None
            or lookback != 2
        ):
            raise ValueError("confirmation_quadrant_invalid")
        quadrant, auxiliary = _quadrant(value["quadrant"], texts["metric_id"])
        main = Member("quadrant", texts["name"], texts["metric_id"], {})
    else:
        main = _member(value.get("main"), texts["metric_id"])
        auxiliary = tuple(_member(item, texts["metric_id"]) for item in raw_auxiliary)
    if main.formula is not None and (
        frequency != "monthly"
        or lookback > farthest + 1 - DERIVED_FORMULAS[main.formula].farthest
        or not main.compared
    ):
        # A derived main member reads its months, each with its inputs, within the horizon.
        raise ValueError("confirmation_main_member_derived")
    if not main.compared:
        raise ValueError("confirmation_member_invalid")
    names = {member.name for member in (main, *auxiliary)}
    if len(names) != 1 + len(auxiliary):
        raise ValueError("confirmation_member_duplicate")
    if frequency != "monthly" and any(
        member.unreleased_months or member.stand_ins or member.formula
        for member in (main, *auxiliary)
    ):
        raise ValueError("confirmation_member_months_need_monthly")
    if any(
        # A change the source states is read beside a member's own values, by period.
        member.change_from is not None
        and (frequency == "daily" or member.formula is not None or member.stand_ins)
        for member in (main, *auxiliary)
    ):
        raise ValueError("confirmation_member_invalid")
    if (
        any(
            # A member read by sessions, or a session formula's, belongs to a daily indicator,
            # and one there reads its sessions or its months.
            (frequency == "daily") != bool(member.aggregate or member.frequency == "monthly")
            or (member.session_formula is not None and member.aggregate is None)
            or (member.partial and actions is None)
            for member in (main, *auxiliary)
        )
        or main.frequency is not None
    ):
        raise ValueError("confirmation_member_invalid")
    line, notices = (
        _member({"name": name, "label": name, **raw}, texts["metric_id"])
        if isinstance(raw, Mapping)
        else None
        for name, raw in (("level_line", raw_line), ("notices", raw_notices))
    )
    derived = tuple(_spread(item, names) for item in raw_derived)
    if any(len(item.of) == 1 and line is None for item in derived):
        raise ValueError("confirmation_derived_invalid")
    others = {_other(key) for key in keys if key != texts["key"]} | {
        _observed(metric_id) for metric_id in OBSERVED_METRICS
    }
    stages = {stage: _expectation(expectations[stage], names, others) for stage in _STAGES}
    read = {
        name
        for expectation in stages.values()
        for cell in expectation.cells
        for condition in cell.when
        for name in condition.readings
    }
    if ("position" in read and lookback < year) or ("change_size" in read and lookback < marked):
        # A range or a change size read short of a year would read another scale.
        raise ValueError("confirmation_year_reading_needs_a_year")
    if ("action" in read) != (actions is not None):
        # A policy indicator read as its actions answers by them alone.
        raise ValueError("confirmation_action_reading_invalid")
    if (quadrant is not None) != ("quadrant" in read) or (
        quadrant is not None and read != {"quadrant"}
    ):
        # The quadrant answers by its quadrant alone, and nothing else does.
        raise ValueError("confirmation_quadrant_reading_invalid")
    return KeyIndicator(
        **texts,
        main=main,
        auxiliary=auxiliary,
        derived=derived,
        level_line=float(raw_line) if isinstance(raw_line, (int, float)) else None,
        lookback=lookback,
        expectations=stages,
        grace=periods_grace,
        frequency=frequency,
        horizon=farthest,
        actions=str(actions) if actions is not None else None,
        window_sessions=window,
        released=_dimensions(released) if released is not None else None,
        period_sessions=sessions,
        line=line,
        notices=notices,
        year=year,
        marked=marked,
        quadrant=quadrant,
    )


def _quadrant(value: object, metric_id: str) -> tuple[QuadrantRule, tuple[Member, ...]]:
    """The quadrant's rule, and its lines' members, each of its line: the main one first.

    Every member passes over the months the quadrant does, which any line's main member
    is never released for: the lines are read at the same months.
    """
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_quadrant_invalid")
    raw_lines, raw_table = value.get("lines"), value.get("quadrants")
    align = _count(value.get("align_months"))
    if (
        not isinstance(raw_lines, Mapping)
        or set(raw_lines) != set(QUADRANT_LINES)
        or not isinstance(raw_table, Mapping)
        or not raw_table
        or align is None
    ):
        raise ValueError("confirmation_quadrant_invalid")
    members: list[Member] = []
    mains: dict[str, Member] = {}
    for line in QUADRANT_LINES:
        raw = raw_lines[line]
        if not isinstance(raw, Mapping) or not isinstance(raw.get("auxiliary", []), list):
            raise ValueError("confirmation_quadrant_invalid")
        mains[line] = _member(raw.get("main"), metric_id)
        for member in (
            mains[line],
            *(_member(item, metric_id) for item in raw.get("auxiliary", [])),
        ):
            if (
                member.formula
                or member.change_from
                or member.aggregate
                or member.frequency
                or member.partial
                or not member.compared
            ):
                # A line reads each member's official value by month.
                raise ValueError("confirmation_quadrant_invalid")
            members.append(replace(member, line=line))
    table: dict[str, dict[str, str]] = {}
    for name, directions in raw_table.items():
        if (
            name not in _READINGS["quadrant"] - {"unclassified"}
            or not isinstance(directions, Mapping)
            or set(directions) != set(QUADRANT_LINES)
            or not set(directions.values()) <= _READINGS["momentum"]
        ):
            raise ValueError("confirmation_quadrant_invalid")
        table[str(name)] = {str(line): str(item) for line, item in directions.items()}
    if len({tuple(sorted(item.items())) for item in table.values()}) != len(table):
        # One set of directions names one quadrant.
        raise ValueError("confirmation_quadrant_invalid")
    skipped = frozenset().union(*(main.unreleased_months for main in mains.values()))
    rule = QuadrantRule({line: main.name for line, main in mains.items()}, table, align, skipped)
    return rule, tuple(
        replace(member, unreleased_months=member.unreleased_months | skipped) for member in members
    )


_LOOKBACK_FIELDS = frozenset({"lookback_months", "lookback_quarters", "lookback_periods"})


def _count(value: object) -> int | None:
    """A positive count, or None."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else None


def _expectation(value: object, names: set[str], others: set[str]) -> Expectation:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_expectation_invalid")
    proposition, raw_cells = value.get("proposition"), value.get("cells")
    lists = [value.get(name, []) for name in ("notes", "turn_hints", "caps")]
    if (
        not isinstance(proposition, str)
        or not proposition
        or not isinstance(raw_cells, list)
        or not all(isinstance(item, list) for item in lists)
    ):
        raise ValueError("confirmation_expectation_invalid")
    # A stage's hint is read back period by period, of the indicator's own members alone.
    notes, turn_hints, caps = (
        tuple(
            annotation
            for item in items
            if (annotation := _annotation(item, names, () if kind == 1 else others)) is not None
        )
        for kind, items in enumerate(lists)
    )
    if any(not hint.when or hint.text not in _STAGES for hint in turn_hints):
        # A stage's hint is a signal of its own: what it reads is how long it held.
        raise ValueError("confirmation_turn_hint_invalid")
    return Expectation(
        proposition,
        tuple(_cell(item, names, others) for item in raw_cells),
        notes,
        turn_hints,
        caps,
    )


def _cell(value: object, names: set[str], others: set[str]) -> Cell:
    if not isinstance(value, Mapping) or value.get("relation") not in _CELL_RELATIONS:
        raise ValueError("confirmation_cell_invalid")
    when = value.get("when")
    if not isinstance(when, list) or not when:
        raise ValueError("confirmation_cell_invalid")
    conditions = tuple(_condition(item, names) for item in when)
    if any(item.member is not None or item.outpaces is not None for item in conditions):
        # The main member gives the indicator's opinion; the others show agreement only.
        raise ValueError("confirmation_cell_reads_main_member_only")
    grace = value.get("grace", False)
    turn_hint = _annotation(value.get("turn_hint"), names)
    raw_confirmed = value.get("confirmed_when")
    confirmed_when = (
        # Passed on: the main member's change shows in another indicator (a cut, in DR007).
        _annotation({"text": "transmission", "when": raw_confirmed}, names, others)
        if raw_confirmed is not None
        else None
    )
    if (
        not isinstance(grace, bool)
        or (grace and value["relation"] != "counterevidence")
        or (turn_hint is not None and turn_hint.text not in _STAGES)
        or (
            confirmed_when is not None
            and (not confirmed_when.when or value["relation"] != "counterevidence")
        )
    ):
        raise ValueError("confirmation_cell_invalid")
    return Cell(
        relation=str(value["relation"]),
        when=conditions,
        note=_annotation(value.get("note"), names, others),
        turn_hint=turn_hint,
        grace=grace,
        confirmed_when=confirmed_when,
    )


def _annotation(value: object, names: set[str], others: Collection[str] = ()) -> Annotation | None:
    """An annotation's text and its conditions: one mapping, or a list all must hold.

    A condition may read another key indicator (``others``) where the annotation is read
    of the newest period alone: a note, a cap, a transmission.
    """
    if value is None:
        return None
    if not isinstance(value, Mapping) or not isinstance(value.get("text"), str):
        raise ValueError("confirmation_annotation_invalid")
    when = value.get("when")
    items = [] if when is None else when if isinstance(when, list) else [when]
    return Annotation(str(value["text"]), tuple(_condition(item, names, others) for item in items))


def _condition(value: object, names: set[str], others: Collection[str] = ()) -> Condition:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_condition_invalid")
    readings: dict[str, str | tuple[str, ...]] = {}
    for name, expected in value.items():
        if name in {"member", "outpaces", "indicator", "after_action", "observed"}:
            continue
        values = expected if isinstance(expected, list) else [expected]
        if name not in _READINGS or not values or not set(values) <= _READINGS[name]:
            raise ValueError(f"confirmation_condition_unknown:{name}")
        readings[name] = str(expected) if not isinstance(expected, list) else tuple(values)
    member, outpaces = value.get("member"), value.get("outpaces")
    if "observed" in value:
        # A derived observation's own reading, named as no member can be; never with
        # another indicator.
        if member is not None or outpaces is not None or "indicator" in value:
            raise ValueError("confirmation_condition_invalid")
        member = _observed(str(value["observed"]))
        if member not in others:
            raise ValueError(f"confirmation_observed_unknown:{value['observed']}")
    if "indicator" in value:
        # Another key indicator's main member, named as no member of its own can be.
        if member is not None or outpaces is not None:
            raise ValueError("confirmation_condition_invalid")
        member = _other(str(value["indicator"]))
        if member not in others:
            raise ValueError(f"confirmation_indicator_unknown:{value['indicator']}")
    if not readings and outpaces is None:
        raise ValueError("confirmation_condition_invalid")
    for reference in (member, outpaces):
        if reference is not None and reference not in names | set(others):
            raise ValueError(f"confirmation_member_unknown:{reference}")
    after_action = value.get("after_action", False)
    if not isinstance(after_action, bool) or (after_action and "indicator" not in value):
        raise ValueError("confirmation_condition_invalid")
    return Condition(
        readings,
        str(member) if member is not None else None,
        str(outpaces) if outpaces is not None else None,
        after_action,
    )


def _member(value: object, metric_id: str) -> Member:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_member_invalid")
    name, label = value.get("name"), value.get("label")
    own = value.get("metric_id", metric_id)
    formula, session_formula = value.get("formula"), value.get("session_formula")
    # A metric with no dimensions has its one member read with none; a derived member has
    # those its formula's inputs take as its own, or none.
    dimensions = (
        _dimensions(value.get("dimensions", {}) if formula else value.get("dimensions"), empty=True)
        if session_formula is None
        else {}
    )
    own_inputs = formula in DERIVED_FORMULAS and any(
        item.dimensions is None for item in DERIVED_FORMULAS[str(formula)].inputs
    )
    flags = [
        value.get(name, default) for name, default in (("cumulative", False), ("compared", True))
    ]
    raw_change = value.get("change_from")
    raw_months = value.get("unreleased_months", [])
    raw_stand_ins = value.get("stand_ins", {})
    stand_in_label = value.get("stand_in_label")
    aggregate, frequency = value.get("aggregate"), value.get("frequency")
    partial = value.get("partial", False)
    if (
        not isinstance(name, str)
        or not name
        # How a condition names another indicator or a derived observation, not a member.
        or name[0] in {"@", "#"}
        or not isinstance(label, str)
        or not label
        or not isinstance(own, str)
        or not isinstance(raw_months, list)
        or not all(isinstance(month, int) and 1 <= month <= 12 for month in raw_months)
        or not isinstance(raw_stand_ins, Mapping)
        or (bool(raw_stand_ins) != isinstance(stand_in_label, str))
        or (formula is not None and formula not in DERIVED_FORMULAS)
        or (session_formula is not None and session_formula not in SESSION_FORMULAS)
        or aggregate not in {None, "mean", "sum"}
        or frequency not in {None, "monthly"}
        or (frequency is not None and aggregate is not None)
        or not isinstance(partial, bool)
        or (partial and not dimensions)
        or (formula is not None and own_inputs != bool(dimensions))
        or not all(isinstance(flag, bool) for flag in flags)
    ):
        raise ValueError("confirmation_member_invalid")
    stand_ins: dict[int, Mapping[str, str]] = {}
    for month, stand_in in raw_stand_ins.items():
        if not str(month).isdigit() or not 1 <= int(month) <= 12:
            raise ValueError("confirmation_member_invalid")
        stand_ins[int(month)] = _dimensions(stand_in)
    return Member(
        name,
        label,
        own,
        dimensions,
        frozenset(raw_months),
        stand_ins,
        str(formula) if formula is not None else None,
        stand_in_label if isinstance(stand_in_label, str) else None,
        aggregate=str(aggregate) if aggregate is not None else None,
        session_formula=str(session_formula) if session_formula is not None else None,
        frequency=str(frequency) if frequency is not None else None,
        partial=partial,
        cumulative=bool(flags[0]),
        compared=bool(flags[1]),
        change_from=_dimensions(raw_change) if raw_change is not None else None,
    )


def _spread(value: object, names: set[str]) -> Spread:
    """A shown spread of two members, ``of`` naming them: the first less the second; or of
    one member against its level line."""
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_derived_invalid")
    name, label, formula, of = (value.get(key) for key in ("name", "label", "formula", "of"))
    if (
        not isinstance(name, str)
        or not isinstance(label, str)
        or not isinstance(of, list)
        or len(of) != (2 if formula in SPREAD_FORMULAS else 1)
        or formula not in SPREAD_FORMULAS | LINE_SPREAD_FORMULAS
        or not all(item in names for item in of)
    ):
        raise ValueError("confirmation_derived_invalid")
    return Spread(name, label, str(formula), tuple(str(item) for item in of))


def _dimensions(value: object, *, empty: bool = False) -> dict[str, str]:
    if not isinstance(value, Mapping) or (not value and not empty):
        raise ValueError("confirmation_member_invalid")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError("confirmation_member_invalid")
    return {str(k): str(v) for k, v in value.items()}


def _cell_data(relation: str, *when: dict[str, str], **extra: Any) -> dict[str, Any]:
    """A cell as the manifest holds it: ``when``'s alternatives, any note, hint or grace."""
    return {"relation": relation, "when": [dict(item) for item in when], **extra}


def _hint(stage: str, **when: str) -> dict[str, Any]:
    return {"text": stage, **({"when": when} if when else {})}


def _member_data(name: str, label: str, **dimensions: str) -> dict[str, Any]:
    return {"name": name, "label": label, "dimensions": dimensions}


_UP, _DOWN, _FLAT = {"momentum": "up"}, {"momentum": "down"}, {"momentum": "flat"}
_HIGH, _LOW = {"position": "high"}, {"position": "low"}
# Rising on: the newest two changes both up, by whatever steps.
_RISING_ON = ({"run": "up"},)
_ORDERS_IMPROVING = "订单先改善：只改动量描述，不宣布复苏"

# The stage narrative each dimension's indicators bear on (expectation-table.md).
_OVERHEAT_PROPOSITIONS = {
    "stage_i": "经济走弱，增长仍弱",
    "stage_ii": "增长仍低但不再恶化",
    "stage_iii": "经济自底部恢复，需求与生产扩张",
    "stage_iv": "经济充分扩张",
    "stage_v": "增长动量见顶回落",
    "stage_vi": "经济由扩张转向收缩",
}
_PRICE_PROPOSITIONS = {
    "stage_i": "物价仍弱",
    "stage_ii": "物价仍低，商品需求未恢复",
    "stage_iii": "商品需求恢复，周期偏向通胀一侧",
    "stage_iv": "价格压力上升",
    "stage_v": "价格压力仍强",
    "stage_vi": "物价动量下降",
}
_CREDIT_PROPOSITIONS = {
    "stage_i": "信用仍弱",
    "stage_ii": "宽松开始传导到融资",
    "stage_iii": "融资条件仍支持扩张",
    "stage_iv": "信用需求旺盛，信用量仍高",
    "stage_v": "信用边际收紧",
    "stage_vi": "信用需求走弱",
}


def _stages(
    propositions: Mapping[str, str], cells: Mapping[str, list[dict[str, Any]]], **extra: Any
) -> dict[str, Any]:
    """Each stage's proposition and cells, with any notes, hints or caps by stage."""
    return {
        stage: {
            "proposition": propositions[stage],
            "cells": cells[stage],
            **{name: by_stage[stage] for name, by_stage in extra.items() if stage in by_stage},
        }
        for stage in _STAGES
    }


def rules_v0001() -> dict[str, Any]:
    """The first confirmation rules (expectation-table.md, key-indicators.md).

    Each stage's cells are tried in order and the first that holds answers; a known
    reading no cell names is observation only. A cell's slope reads along the momentum it
    names: steepening is a quickening, slowing a slackening, of that move (user, 2026-10-07).
    Stabilising is no longer falling: flat or rising. An indicator read for its place in a
    year's range, or the size of its change, reads a year of months.
    """
    return {
        "key_indicators": copy.deepcopy(_KEY_INDICATORS),
        "timing_rules": copy.deepcopy(_TIMING_RULES),
        "maturity_rules": dict(_MATURITY_RULES),
        "warrant_conversions": copy.deepcopy(_WARRANT_CONVERSIONS),
        "observation_interfaces": copy.deepcopy(_OBSERVATION_INTERFACES),
        "price_consistency": copy.deepcopy(_PRICE_CONSISTENCY),
        "supply_demand": copy.deepcopy(_SUPPLY_DEMAND),
        "bond_attribution": copy.deepcopy(_BOND_ATTRIBUTION),
    }


# Grace in independent periods; the farthest period back a reading or its grace reaches,
# thirteen months (ADR-0035); the stage a lag still shows, the stage a lead already shows
# (expectation-table.md E3/D4, N4).
_TIMING_RULES = {
    # A daily indicator's period is a run of its sessions (five, a week's): two of them,
    # as two months for a monthly one (macro semantics ticket 06).
    "grace_periods": {"monthly": 2, "quarterly": 1, "daily": 2},
    # Fifty-two periods of five sessions: a year's 250 and the two grace reads before. A
    # quarterly indicator's four quarters and the one before them, twelve months back: the
    # quarter grace reads back reads its own year (ticket 07).
    "horizon_periods": {"monthly": 13, "quarterly": 4, "daily": 51},
    # The one-year scale (O4): a range of twelve months, four quarters or 250 sessions; a
    # change marked against those of twelve months, four quarters or twelve periods of
    # sessions (ticket 07: a quarterly indicator's year is its four quarters).
    "year_periods": {"monthly": YEAR_MONTHS, "quarterly": 4, "daily": YEAR_SESSIONS},
    "marked_periods": {"monthly": YEAR_MONTHS, "quarterly": 4, "daily": YEAR_MONTHS},
    "adjacent_stage": {"leading": "next", "lagging": "previous"},
}
# Forming: held two periods, or two leading indicators turning toward one stage (ADR-0037).
_MATURITY_RULES = {"forming_periods": 2, "forming_signals": 2}


_PMI_MEMBERS = {
    "main": _member_data("manufacturing", "制造业 PMI", measure="level", series="manufacturing"),
    "auxiliary": [
        _member_data("new_orders", "新订单", measure="level", series="new_orders"),
        _member_data("production", "生产", measure="level", series="production"),
        _member_data("purchase_volume", "采购量", measure="level", series="purchase_volume"),
    ],
}

_PMI_EXPECTATIONS: dict[str, Any] = {
    "stage_i": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_i"],
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "above", "momentum": "up"}]},
            # Below 50 and falling, a slowing fall included.
            {"relation": "support", "when": [{"level": "below", "momentum": "down"}]},
            {
                "relation": "observation_only",
                "when": [{"level": "below", "momentum": "up"}],
                "turn_hint": {"text": "stage_ii", "when": {"slope": "steeper"}},
            },
        ],
    },
    "stage_ii": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_ii"],
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"level": "below", "momentum": "down", "slope": "steeper"}],
            },
            {
                "relation": "support",
                "when": [{"level": "below", "momentum": "up"}, {"crossed": "above"}],
                "note": {
                    "text": "新订单领先生产",
                    "when": {"member": "new_orders", "outpaces": "production"},
                },
            },
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "steeper"}],
                "turn_hint": {"text": "stage_iii"},
            },
        ],
    },
    "stage_iii": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_iii"],
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "below"}], "grace": True},
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "slower"}],
                "note": {"text": "扩张仍在、动能减弱"},
            },
            {"relation": "support", "when": [{"level": "above", "momentum": "up"}]},
        ],
    },
    "stage_iv": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_iv"],
        "cells": [
            {"relation": "counterevidence", "when": [{"level": "below"}], "grace": True},
            {
                "relation": "observation_only",
                "when": [{"level": "above", "momentum": "up", "slope": "slower"}],
                "note": {"text": "扩张后段，斜率放缓"},
            },
            {"relation": "support", "when": [{"level": "above"}]},
        ],
    },
    "stage_v": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_v"],
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"momentum": "up", "slope": "steeper"}],
                "grace": True,
            },
            {
                "relation": "support",
                "when": [{"momentum": "down"}],
                "note": {"text": "水平仍高、动量下降", "when": {"level": "above"}},
            },
            {"relation": "observation_only", "when": [{"momentum": "flat"}]},
        ],
    },
    "stage_vi": {
        "proposition": _OVERHEAT_PROPOSITIONS["stage_vi"],
        "cells": [
            {
                "relation": "counterevidence",
                "when": [{"level": "above", "momentum": "up"}],
                "grace": True,
            },
            {"relation": "support", "when": [{"level": "below", "momentum": "down"}]},
        ],
        # Orders improving first is told whatever the PMI does; against a falling PMI it
        # is a split, and the relation is observation only.
        "notes": [{"text": _ORDERS_IMPROVING, "when": {"member": "new_orders", "momentum": "up"}}],
    },
}

# Industrial value added: no January release, and February's is the January-February
# cumulative growth, which the NBS itself compares March with ("比1—2月份加快").
_INDUSTRIAL_VA_MEMBERS: dict[str, Any] = {
    "main": {
        **_member_data("current_month", "当月实际同比", measure="current_month_real_yoy"),
        "unreleased_months": [1],
        "stand_ins": {"2": {"measure": "ytd_real_yoy"}},
        # Said wherever a February is read: the point is cumulative (user, 2026-10-07).
        "stand_in_label": "1—2 月累计同比（累计口径）",
    },
    "auxiliary": [
        {
            **_member_data("ytd", "累计实际同比", measure="ytd_real_yoy"),
            "unreleased_months": [1],
        },
        {
            **_member_data("mom_sa", "季调环比", measure="mom_seasonally_adjusted"),
            "unreleased_months": [1],
        },
    ],
}
_INDUSTRIAL_VA_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _UP),
        _cell_data("support", _DOWN, _LOW),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_ii": [
        # Falling faster waits on grace; slowing within it is only observed.
        _cell_data("counterevidence", {"momentum": "down", "slope": "steeper"}, grace=True),
        _cell_data("support", {**_LOW, **_FLAT}, {**_LOW, **_UP}),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _UP),
    ],
    "stage_iv": [
        _cell_data("support", _HIGH, _UP),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_v": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_vi": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
}

_PPI_MEMBERS = {
    "main": _member_data("headline", "PPI 同比", category="headline", measure="yoy"),
    "auxiliary": [
        _member_data("mom", "PPI 环比", category="headline", measure="mom"),
        _member_data(
            "means_of_production", "生产资料同比", category="means_of_production", measure="yoy"
        ),
        _member_data("consumer_goods", "生活资料同比", category="consumer_goods", measure="yoy"),
    ],
}
_BELOW = {"level": "below"}
_PPI_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", *_RISING_ON),
        _cell_data("support", _BELOW, _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_ii": [
        _cell_data("counterevidence", *_RISING_ON, grace=True),
        _cell_data("support", _BELOW, _DOWN),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _FLAT, _UP),
    ],
    "stage_iv": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _UP),
    ],
    "stage_v": [
        _cell_data("support", _HIGH, _UP),
        _cell_data("observation_only", _DOWN, turn_hint=_hint("stage_vi")),
    ],
    "stage_vi": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
}
# F4: month-on-month turning up while the year-on-year still falls hints at stage III.
_PPI_MOM_TURNING = {"member": "mom", "momentum": "up"}

_CORE_CPI = {
    **_member_data("core", "核心 CPI 同比", category="ex_food_energy", measure="yoy"),
    "metric_id": "CN_CORE_CPI",
}
_CPI_MEMBERS = {
    "main": _member_data("headline", "CPI 同比", category="headline", measure="yoy"),
    "auxiliary": [_CORE_CPI],
}
# Core CPI not falling: sticky, lagging the turn.
_CORE_STICKY = [
    {"text": "核心 CPI 黏性（滞后未转）", "when": {"member": "core", "momentum": "flat"}},
    {"text": "核心 CPI 黏性（滞后未转）", "when": {"member": "core", "momentum": "up"}},
]
_CPI_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
    ],
    "stage_ii": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _LOW, _DOWN),
    ],
    "stage_iii": [
        _cell_data("support", _FLAT, _UP),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_iv": [
        _cell_data("support", _UP),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_v": [
        _cell_data("support", _UP, _HIGH),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_vi": [_cell_data("support", _DOWN)],
}

_PMI_PRICE_MEMBERS = {
    "main": _member_data("output_prices", "出厂价格", measure="level", series="output_prices"),
    "auxiliary": [
        _member_data(
            "purchase_prices", "主要原材料购进价格", measure="level", series="purchase_prices"
        )
    ],
}
_ABOVE, _ABOVE_RISING = {"level": "above"}, {"level": "above", "momentum": "up"}
_PMI_PRICE_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _ABOVE_RISING),
        _cell_data("support", _BELOW, _DOWN),
    ],
    "stage_ii": [
        _cell_data("support", _BELOW),
        _cell_data("observation_only", _ABOVE_RISING, turn_hint=_hint("stage_iii")),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _BELOW, grace=True),
        _cell_data("support", _ABOVE),
    ],
    "stage_iv": [
        _cell_data("counterevidence", _BELOW, grace=True),
        _cell_data("support", _ABOVE_RISING),
    ],
    "stage_v": [
        _cell_data("support", _ABOVE),
        _cell_data("observation_only", _BELOW, turn_hint=_hint("stage_vi")),
    ],
    "stage_vi": [
        _cell_data("counterevidence", _ABOVE_RISING, grace=True),
        _cell_data("support", _BELOW),
    ],
}

_MONEY_MEMBERS = {
    "main": _member_data("m1", "M1 同比", aggregate="m1", measure="yoy"),
    "auxiliary": [_member_data("m2", "M2 同比", aggregate="m2", measure="yoy")],
    # Of the same month and measure; shown, never counted (ADR-0037).
    "derived": [
        {"name": "m1_m2", "label": "M1−M2", "formula": "m1-m2-yoy-spread-v0001", "of": ["m1", "m2"]}
    ],
}
_MONEY_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _LOW, _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_ii": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _FLAT, _UP),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _UP),
    ],
    "stage_iv": [
        _cell_data("support", _HIGH),
        _cell_data("observation_only", _DOWN, turn_hint=_hint("stage_v")),
    ],
    "stage_v": [
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _UP),
    ],
    "stage_vi": [
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _UP),
    ],
}

# The non-government components of the stock, each read by its official growth (user,
# 2026-10-07): any one against the total is a split.
_NON_GOVERNMENT_COMPONENTS = {
    "renminbi_loans": "人民币贷款",
    "foreign_currency_loans_rmb": "外币贷款（折人民币）",
    "entrusted_loans": "委托贷款",
    "trust_loans": "信托贷款",
    "undiscounted_bank_acceptances": "未贴现银行承兑汇票",
    "corporate_bonds": "企业债券",
    "nonfinancial_enterprise_equity": "非金融企业境内股票",
}
_SOCIAL_FINANCING_MEMBERS = {
    "main": _member_data("stock_yoy", "存量同比", measure="stock_yoy"),
    "auxiliary": [
        {
            **_member_data(component, f"{label}存量同比", component=component, measure="stock_yoy"),
            "metric_id": "CN_SF_COMPONENTS",
        }
        for component, label in {
            "government_bonds": "政府债券",
            **_NON_GOVERNMENT_COMPONENTS,
        }.items()
    ]
    + [
        # The month's flow from year-to-date totals, more or less than a year before.
        {
            "name": "monthly_increment",
            "label": "当月增量同比多增少增",
            "formula": "sf-monthly-increment-yoy-change-v0001",
        },
    ],
}
_MARKED_UP = {"momentum": "up", "change_size": "marked"}
_MARKED_DOWN = {"momentum": "down", "change_size": "marked"}
# F3: held up by government bonds alone -- they rise and not one non-government component
# does, each known -- transmission to the real economy is not confirmed, and support is
# only observed (expectation-table.md; user, 2026-10-07).
_GOVERNMENT_ONLY = [
    {
        "text": "实体传导未确认",
        "when": [
            {"member": "government_bonds", "momentum": "up"},
            *(
                {"member": component, "momentum": ["flat", "down"]}
                for component in _NON_GOVERNMENT_COMPONENTS
            ),
        ],
    }
]
_SOCIAL_FINANCING_CELLS = {
    "stage_i": [
        # Quickening, marked or within grace, or steadying, hints at stage II.
        _cell_data("counterevidence", _MARKED_UP, grace=True, turn_hint=_hint("stage_ii")),
        _cell_data("observation_only", _UP, turn_hint=_hint("stage_ii")),
        _cell_data("support", _DOWN, _LOW),
        _cell_data("observation_only", _FLAT, turn_hint=_hint("stage_ii")),
    ],
    "stage_ii": [
        _cell_data("counterevidence", _MARKED_DOWN, grace=True),
        _cell_data("support", _FLAT, _UP),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _DOWN, grace=True),
        _cell_data("support", _UP),
    ],
    "stage_iv": [
        # High, or slowing but still high (I2).
        _cell_data("support", _HIGH),
        _cell_data("counterevidence", _MARKED_DOWN, grace=True),
        _cell_data("observation_only", _DOWN, turn_hint=_hint("stage_v")),
    ],
    "stage_v": [
        # Slowing, or quickening less: contraction is not asked for (J3).
        _cell_data("support", _DOWN, {"momentum": "up", "slope": "slower"}),
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_vi": [
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
        # Steadying leads: toward stages I and II.
        _cell_data("observation_only", _FLAT, turn_hint=_hint("stage_i")),
    ],
}

# Loans: the month's flow of each pair, from its year-to-date totals, more (above zero)
# or less (below) than the same month a year before; the t, t-1, t-12 and t-13 totals and
# nothing further back (ADR-0035), so whether an earlier month was more is not read.
_LOAN_FORMULA = "loan-monthly-increment-yoy-change-v0001"


def _loan_member(borrower: str, tenor: str, label: str) -> dict[str, Any]:
    return {
        **_member_data(
            f"{borrower}_{tenor}", label, borrower=borrower, tenor=tenor, measure="ytd_increment"
        ),
        "formula": _LOAN_FORMULA,
    }


_LOAN_MEMBERS = {
    "main": _loan_member("enterprise", "long_term", "企业中长期贷款当月增量（较去年同月）"),
    # Every other tenor and borrower, each its month's flow against a year before.
    "auxiliary": [
        _loan_member(borrower, tenor, f"{label}当月增量（较去年同月）")
        for borrower, tenor, label in (
            ("household", "total", "住户贷款"),
            ("household", "short_term", "住户短期贷款"),
            ("household", "long_term", "住户中长期贷款"),
            ("enterprise", "total", "企（事）业单位贷款"),
            ("enterprise", "short_term", "企业短期贷款"),
            ("enterprise", "bill_financing", "票据融资"),
            ("nonbank_financial", "total", "非银行业金融机构贷款"),
            ("all_rmb_loans", "total", "人民币贷款"),
        )
    ],
}
_MORE, _LESS, _AS_MUCH = {"level": "above"}, {"level": "below"}, {"level": "at"}
_LOAN_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _MORE, grace=True),
        _cell_data("support", _LESS),
        _cell_data("observation_only", _AS_MUCH),
    ],
    "stage_ii": [
        # Less, and less again than the month before: widening.
        _cell_data("counterevidence", {**_LESS, **_DOWN}, grace=True),
        # Turned more, or less by less: narrowing.
        _cell_data("support", _MORE, {**_LESS, **_UP}),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _LESS, grace=True),
        _cell_data("support", _MORE),
    ],
    "stage_iv": [
        _cell_data("support", _MORE, _AS_MUCH),
        _cell_data("observation_only", _LESS, turn_hint=_hint("stage_v")),
    ],
    "stage_v": [
        _cell_data("counterevidence", _MORE, grace=True),
        # Bills more while long-term loans are less: the structure worsens.
        _cell_data(
            "support",
            _LESS,
            note={"text": "结构恶化", "when": {"member": "enterprise_bill_financing", **_MORE}},
        ),
        _cell_data("observation_only", _AS_MUCH),
    ],
    "stage_vi": [
        _cell_data("support", _LESS),
        _cell_data("observation_only", _MORE),
    ],
}
# The credit impulse up on the month before while long-term loans are less: a lead
# observed, a note alone, the relation as its cell says (user, 2026-10-07).
_IMPULSE_AHEAD_OF_LOANS = [
    {
        "text": "信用脉冲转强而贷款结构未改善（领先观察）",
        "when": [{"observed": "CN_CREDIT_IMPULSE", "momentum": "up"}, _LESS],
    }
]

# Industrial profits: the official cumulative growth (January to the month) quickening or
# slowing on the month before, said to be cumulative, never a month's growth computed
# from cumulative profits (N3). No January release: February's January-February is read
# against December's whole year, as industrial value added's is.
_PROFIT_MEMBERS = {
    "main": {
        **_member_data("profit", "利润累计同比（累计口径）", item="profit", measure="official_yoy"),
        "unreleased_months": [1],
        "cumulative": True,
    },
    "auxiliary": [
        {
            **_member_data(item, f"{label}累计同比（累计口径）", item=item, measure="official_yoy"),
            "unreleased_months": [1],
            "cumulative": True,
        }
        for item, label in (("revenue", "营业收入"), ("cost", "营业成本"))
    ],
}
_PROFIT_CELLS = {
    "stage_i": [
        # Still growing faster lags, within grace.
        _cell_data("counterevidence", _UP, grace=True),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_ii": [_cell_data("support", _UP), _cell_data("observation_only", _DOWN)],
    "stage_iii": [_cell_data("support", _UP), _cell_data("observation_only", _DOWN)],
    "stage_iv": [_cell_data("support", _UP), _cell_data("observation_only", _DOWN)],
    # Falling, or peaking (no longer rising); still strong lags (J2).
    "stage_v": [_cell_data("support", _DOWN, _FLAT), _cell_data("observation_only", _UP)],
    "stage_vi": [_cell_data("support", _DOWN), _cell_data("observation_only", _UP)],
}

# GDP: the real growth of each quarter on the same quarter a year before, read over four
# quarters; its year's range is theirs (ticket 07). The nominal year-to-date level is
# shown, never compared: it rises through each year whatever growth does.
_GDP_MEMBERS = {
    "main": _member_data(
        "real_quarter_yoy", "实际季度同比", aggregate="total", measure="real_quarter_yoy"
    ),
    "auxiliary": [
        {
            **_member_data(
                "nominal_ytd_level",
                "名义累计值（累计口径）",
                aggregate="total",
                measure="nominal_ytd_level",
            ),
            "cumulative": True,
            "compared": False,
        }
    ],
}
_GDP_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", _UP),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_ii": [
        # Falling faster.
        _cell_data("counterevidence", {**_DOWN, "slope": "steeper"}),
        _cell_data("support", _LOW, turn_hint=_hint("stage_iii", momentum="up")),
        _cell_data("observation_only", _UP, turn_hint=_hint("stage_iii")),
    ],
    "stage_iii": [
        _cell_data("counterevidence", _DOWN),
        _cell_data("support", _UP),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_iv": [
        # Strong: high in its year. Slowing markedly waits on grace.
        _cell_data("support", _HIGH),
        _cell_data("counterevidence", {**_DOWN, "change_size": "marked"}, grace=True),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_v": [
        _cell_data("counterevidence", _UP),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
    "stage_vi": [
        _cell_data("counterevidence", _UP),
        _cell_data("support", _DOWN),
        _cell_data("observation_only", _FLAT),
    ],
}

# Capacity utilisation, the whole industry's rate of each quarter: high or low in its four
# quarters; its momentum the official change on the same quarter a year before, which the
# seasons of a year do not move.
_CAPACITY_MEMBERS = {
    "main": {
        **_member_data(
            "quarter_rate", "全工业产能利用率", industry="all_industry", measure="quarter_rate"
        ),
        "change_from": {"industry": "all_industry", "measure": "yoy_change"},
    },
    "auxiliary": [],
}
_CAPACITY_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", {**_UP, **_HIGH}, grace=True),
        _cell_data("support", _DOWN, _LOW),
        # Still high: the previous stage's, lagging.
        _cell_data("observation_only", _HIGH),
    ],
    "stage_ii": [_cell_data("support", _LOW), _cell_data("observation_only", _UP)],
    "stage_iii": [_cell_data("support", _UP), _cell_data("observation_only", _LOW)],
    "stage_iv": [
        _cell_data("counterevidence", _LOW, grace=True),
        _cell_data("support", _HIGH, _UP),
    ],
    "stage_v": [_cell_data("support", _DOWN), _cell_data("observation_only", _HIGH)],
    "stage_vi": [_cell_data("support", _DOWN), _cell_data("observation_only", _HIGH)],
}

_POLICY_PROPOSITIONS = {
    "stage_i": "政策和资金价格转松",
    "stage_ii": "宽松延续并开始传导",
    "stage_iii": "政策未转紧，融资条件仍支持扩张",
    "stage_iv": "政策由宽松转向中性或收紧",
    "stage_v": "政策中性偏紧，利率维持较高",
    "stage_vi": "政策观望或刚开始宽松",
}
# The latest action in the 120-session evidence window: cut or raised there (a cut earlier
# in it, then held, still reads cut: F2), or none -- unchanged longer than the window.
_CUT, _HIKE, _NONE = {"action": "cut"}, {"action": "hike"}, {"action": "none"}
_POLICY_TURNING = "政策转向，接近Ⅵ→Ⅰ"


def _policy_action_cells(**cut_in_iv: Any) -> dict[str, list[dict[str, Any]]]:
    """A policy action's cells by stage; ``cut_in_iv`` qualifies stage IV's cut."""
    return {
        "stage_i": [
            _cell_data("counterevidence", _HIKE),
            _cell_data("support", _CUT),
            _cell_data("observation_only", _NONE),
        ],
        "stage_ii": [
            _cell_data("counterevidence", _HIKE),
            _cell_data("support", _CUT),
            _cell_data("observation_only", _NONE),
        ],
        "stage_iii": [
            # A hike is a sprout or forming of stage IV (G1/H1).
            _cell_data("observation_only", _HIKE, turn_hint=_hint("stage_iv")),
            _cell_data("support", _NONE, _CUT),
        ],
        "stage_iv": [
            _cell_data("counterevidence", _CUT, **cut_in_iv),
            _cell_data("support", _HIKE, _NONE),
        ],
        "stage_v": [
            # Whatever its maturity, a cut is only observed here (J1).
            _cell_data(
                "observation_only",
                _CUT,
                turn_hint=_hint("stage_vi"),
                note={"text": _POLICY_TURNING},
            ),
            _cell_data("support", _HIKE, _NONE),
        ],
        "stage_vi": [
            _cell_data("observation_only", _HIKE, note={"text": "政策滞后"}),
            # Waiting, or just easing: a cut hints at stage I (L1).
            _cell_data("support", _NONE, _CUT, turn_hint=_hint("stage_i", action="cut")),
        ],
    }


# A cut passed on: DR007, the funding price, falls after it -- the mean of a period begun
# after the cut lower than the one before (user, 2026-10-07).
_CUT_PASSED_ON = [{"indicator": "dr007", "momentum": "down", "after_action": True}]
_POLICY_RATE: dict[str, Any] = {
    "key": "policy_rate",
    "timing": "leading",
    "name": "政策利率",
    "dimension": "policy",
    "metric_id": "CN_OMO_7D_RATE",
    "main": _member_data("omo_7d", "七天逆回购利率"),
    "auxiliary": [],
    "level_line": None,
    "actions": "level",
    "window_sessions": 120,
    # Each session's operation notice, which states the rate: a day read, rate or not.
    "notices": {"metric_id": "CN_OMO_7D_AMOUNT", "dimensions": {"measure": "injection"}},
    # The rate in force before the window, then its days in it.
    "lookback_months": 1,
    "expectations": _stages(
        _POLICY_PROPOSITIONS,
        # A cut in stage IV is counterevidence confirmed: past grace, or passed on.
        _policy_action_cells(grace=True, confirmed_when=_CUT_PASSED_ON),
    ),
}
_LPR: dict[str, Any] = {
    "key": "lpr",
    "timing": "leading",
    "name": "LPR",
    "dimension": "policy",
    "metric_id": "CN_LPR_1Y_5Y",
    "main": _member_data("1y", "1 年期 LPR", tenor="1y"),
    "auxiliary": [_member_data("5y_plus", "5 年期以上 LPR", tenor="5y_plus")],
    "level_line": None,
    "actions": "level",
    "window_sessions": 120,
    # The window's months and the fixing in force before them.
    "lookback_months": 8,
    # A cut in stage IV is confirmed as the policy rate's is: past grace, or passed on.
    "expectations": _stages(
        _POLICY_PROPOSITIONS, _policy_action_cells(grace=True, confirmed_when=_CUT_PASSED_ON)
    ),
}
_RRR: dict[str, Any] = {
    "key": "rrr",
    "timing": "leading",
    "name": "降准",
    "dimension": "policy",
    "metric_id": "CN_RRR_EVENT",
    # Each event states its own change, of whichever institutions' scope.
    "main": {
        **_member_data("rrr_change", "存款准备金率调整", measure="rrr_change"),
        "partial": True,
    },
    "auxiliary": [],
    "level_line": None,
    "actions": "change",
    "window_sessions": 120,
    "released": {"measure": "released_funds"},
    "lookback_months": 1,
    "expectations": _stages(_POLICY_PROPOSITIONS, _policy_action_cells()),
}

# Net injection on a period: what was put in over its sessions, less what matured. Above
# zero a net injection, below it a net withdrawal; more or less than the period before.
_NET_INJECTION, _NET_WITHDRAWAL = {"level": "above"}, {"level": "below"}
_STEADY = {"change_size": "ordinary"}
_SURGING = {"level": "above", "momentum": "up", "change_size": "marked"}
_LIQUIDITY_CELLS = {
    "stage_i": [
        # Withdrawal widening on: net falling twice running, below zero.
        _cell_data("counterevidence", {**_NET_WITHDRAWAL, "run": "down"}),
        _cell_data("support", {**_NET_INJECTION, **_UP}),
    ],
    "stage_ii": [
        _cell_data("counterevidence", {**_NET_WITHDRAWAL, "run": "down"}),
        _cell_data("support", {**_NET_INJECTION, **_UP}, _STEADY),
    ],
    "stage_iii": [
        # Withdrawal widening: a sprout or forming of stage IV.
        _cell_data("observation_only", {**_NET_WITHDRAWAL, **_DOWN}, turn_hint=_hint("stage_iv")),
        _cell_data("support", _STEADY),
    ],
    "stage_iv": [
        _cell_data("observation_only", _SURGING),
        _cell_data("support", _NET_WITHDRAWAL),
    ],
    "stage_v": [
        _cell_data("observation_only", _SURGING),
        _cell_data("support", _NET_WITHDRAWAL, _STEADY),
    ],
    "stage_vi": [
        _cell_data("observation_only", {**_NET_WITHDRAWAL, **_DOWN}),
        _cell_data("support", {**_NET_INJECTION, **_UP}, _STEADY),
    ],
}
_LIQUIDITY: dict[str, Any] = {
    "key": "liquidity",
    "timing": "leading",
    "name": "流动性投放",
    "dimension": "policy",
    "metric_id": "CN_OMO_7D_AMOUNT",
    "main": {
        "name": "net_injection",
        "label": "七天逆回购净投放（每期合计）",
        "session_formula": "omo-7d-net-injection-v0001",
        "aggregate": "sum",
    },
    "auxiliary": [
        {
            **_member_data(
                "short_term_reverse_repo",
                "月度工具投放：短期逆回购净投放",
                tool="短期逆回购",
                measure="net_injection",
            ),
            "metric_id": "CN_TOOL_LIQUIDITY_MONTHLY",
            "frequency": "monthly",
        }
    ],
    "level_line": 0,
    "frequency": "daily",
    "period_sessions": 5,
    # Twelve periods: whether the newest change is marked.
    "lookback_periods": 12,
    "expectations": _stages(_POLICY_PROPOSITIONS, _LIQUIDITY_CELLS),
}

# DR007's period mean against the policy rate in force at its end.
_ABOVE_POLICY, _BELOW_POLICY = {"level": "above"}, {"level": "below"}
# The policy acted and DR007 did not fall: DR007 is observed, never support nor
# counterevidence, in every stage (D1; user, 2026-10-07); the action answers its own cell.
_ACTED_NOT_FALLEN = [
    {
        "text": text,
        "when": [{"indicator": indicator, "action": "cut"}, {"momentum": ["flat", "up"]}],
    }
    for indicator, text in (
        ("policy_rate", "政策利率已下调而 DR007 未降"),
        ("lpr", "LPR 已下调而 DR007 未降"),
        ("rrr", "已降准而 DR007 未降"),
    )
]
_DR007_CELLS = {
    "stage_i": [
        _cell_data("counterevidence", {**_UP, **_ABOVE_POLICY}),
        _cell_data("support", _DOWN, _BELOW_POLICY),
    ],
    "stage_ii": [
        _cell_data("counterevidence", {**_UP, **_ABOVE_POLICY}),
        _cell_data("support", _BELOW_POLICY, {**_LOW, **_STEADY}),
    ],
    "stage_iii": [
        _cell_data("observation_only", {**_UP, **_ABOVE_POLICY}, turn_hint=_hint("stage_iv")),
        _cell_data("support", _STEADY, _BELOW_POLICY),
    ],
    "stage_iv": [
        _cell_data("counterevidence", {**_DOWN, **_BELOW_POLICY}, grace=True),
        _cell_data("support", _UP, _ABOVE_POLICY),
    ],
    "stage_v": [
        _cell_data("support", _HIGH, _ABOVE_POLICY),
        _cell_data("observation_only", _DOWN),
    ],
    "stage_vi": [
        _cell_data("support", _DOWN, turn_hint=_hint("stage_i")),
        _cell_data("observation_only", _UP),
    ],
}
_DR007: dict[str, Any] = {
    "key": "dr007",
    "timing": "leading",
    "name": "DR007",
    "dimension": "policy",
    "metric_id": "CN_DR007",
    "main": {**_member_data("dr007", "DR007（每期均值）"), "aggregate": "mean"},
    "auxiliary": [
        {
            **_member_data("shibor_1w", "SHIBOR 1 周（每期均值）", tenor="1w"),
            "metric_id": "CN_SHIBOR_ON_1W_3M",
            "aggregate": "mean",
        }
    ],
    # Shown, never counted (ADR-0037).
    "derived": [
        {
            "name": "policy_spread",
            "label": "DR007 政策利差（基点）",
            "formula": "dr007-policy-spread-sessions-v0001",
            "of": ["dr007"],
        }
    ],
    "level_line": {"metric_id": "CN_OMO_7D_RATE", "dimensions": {}},
    "frequency": "daily",
    "period_sessions": 5,
    # Fifty periods of five sessions: a year's range.
    "lookback_periods": 50,
    "expectations": _stages(
        _POLICY_PROPOSITIONS,
        _DR007_CELLS,
        caps=dict.fromkeys(_STAGES, _ACTED_NOT_FALLEN),
    ),
}

_INVENTORY_PROPOSITIONS = {
    "stage_i": "需求走弱，库存随之去化或被动积压",
    "stage_ii": "需求回升快于生产，库存被动下降",
    "stage_iii": "需求与生产扩张，企业主动补库",
    "stage_iv": "经济充分扩张，企业主动补库",
    "stage_v": "需求转弱，产成品被动积压",
    "stage_vi": "需求恶化，企业主动去库",
}
# Demand (the PMI's new orders; industrial revenue), production (industrial value added;
# the PMI's production) and inventory (finished goods' nominal growth; the PMI's finished
# goods, finished goods' turnover days): each line's direction its main member's momentum
# (GLOSSARY.md, 库存象限). Industrial value added's February is its January-February
# cumulative growth, as its key indicator's is; no January of it, nor of the industrial
# finance figures.
_QUADRANT_LINES = {
    "demand": {
        "main": {
            **_member_data("new_orders", "需求：PMI 新订单", measure="level", series="new_orders"),
            "metric_id": "CN_PMI_ACTIVITY",
        },
        "auxiliary": [
            {
                **_member_data(
                    "revenue",
                    "需求：工业企业营业收入累计同比（累计口径）",
                    item="revenue",
                    measure="official_yoy",
                ),
                "metric_id": "CN_INDUSTRIAL_FINANCE",
                "unreleased_months": [1],
                "cumulative": True,
            }
        ],
    },
    "production": {
        "main": {
            **_INDUSTRIAL_VA_MEMBERS["main"],
            "name": "industrial_va",
            "label": "生产：工业增加值当月实际同比",
            "metric_id": "CN_INDUSTRIAL_VA",
        },
        "auxiliary": [
            {
                **_member_data(
                    "pmi_production", "生产：PMI 生产", measure="level", series="production"
                ),
                "metric_id": "CN_PMI_ACTIVITY",
            }
        ],
    },
    "inventory": {
        "main": {
            **_member_data("finished_goods", "库存：产成品存货名义同比", measure="official_yoy"),
            "metric_id": "CN_FINISHED_GOODS_INVENTORY",
            "unreleased_months": [1],
        },
        "auxiliary": [
            {
                **_member_data(
                    "pmi_finished_goods",
                    "库存：PMI 产成品库存",
                    measure="level",
                    series="finished_goods",
                ),
                "metric_id": "CN_PMI_INVENTORY",
            },
            {
                **_member_data(
                    "turnover",
                    "库存：产成品周转天数同比变化（累计口径）",
                    measure="official_yoy_change",
                ),
                "metric_id": "CN_INVENTORY_TURNOVER",
                "unreleased_months": [1],
                "cumulative": True,
            },
        ],
    },
}
# The quadrant demand and inventory name, production moving with demand to verify it; any
# other set of directions, a line flat among them, is unclassified (GLOSSARY.md, 库存象限).
_QUADRANTS = {
    "active_destocking": {"demand": "down", "production": "down", "inventory": "down"},
    "passive_destocking": {"demand": "up", "production": "up", "inventory": "down"},
    "active_restocking": {"demand": "up", "production": "up", "inventory": "up"},
    "passive_restocking": {"demand": "down", "production": "down", "inventory": "up"},
}


def _quadrant_cell(relation: str, *quadrants: str, **extra: Any) -> dict[str, Any]:
    return _cell_data(relation, *({"quadrant": name} for name in quadrants), **extra)


_UNCLASSIFIED = _quadrant_cell("observation_only", "unclassified")
# Orders up while production does not follow: the repair under way (stage VI).
_REPAIRING = {
    "text": "修复过渡：订单回升而生产未跟",
    "when": [
        {"member": "new_orders", "momentum": "up"},
        {"member": "industrial_va", "momentum": ["flat", "down"]},
    ],
}
# Each stage's quadrants (expectation-table.md, E4/D5): counterevidence waits on grace, the
# quadrant lagging; unclassified is only observed.
_QUADRANT_CELLS = {
    "stage_i": [
        _quadrant_cell("counterevidence", "active_restocking", grace=True),
        _quadrant_cell("support", "active_destocking", "passive_restocking"),
        _quadrant_cell("observation_only", "passive_destocking"),
        _UNCLASSIFIED,
    ],
    "stage_ii": [
        _quadrant_cell("counterevidence", "passive_restocking", grace=True),
        _quadrant_cell("support", "passive_destocking"),
        _quadrant_cell("observation_only", "active_destocking", note={"text": "阶段Ⅱ早段"}),
        _quadrant_cell("observation_only", "active_restocking", turn_hint=_hint("stage_iii")),
        _UNCLASSIFIED,
    ],
    "stage_iii": [
        _quadrant_cell("counterevidence", "active_destocking", "passive_restocking", grace=True),
        _quadrant_cell("support", "active_restocking"),
        _quadrant_cell("observation_only", "passive_destocking", note={"text": "阶段Ⅲ早段"}),
        _UNCLASSIFIED,
    ],
    "stage_iv": [
        _quadrant_cell("counterevidence", "active_destocking", "passive_destocking", grace=True),
        _quadrant_cell("support", "active_restocking"),
        _quadrant_cell(
            "observation_only",
            "passive_restocking",
            note={"text": "后段背离"},
            turn_hint=_hint("stage_v"),
        ),
        _UNCLASSIFIED,
    ],
    "stage_v": [
        _quadrant_cell("counterevidence", "passive_destocking", grace=True),
        _quadrant_cell("support", "passive_restocking"),
        _quadrant_cell("observation_only", "active_restocking", note={"text": "自Ⅳ过渡"}),
        _quadrant_cell("observation_only", "active_destocking", turn_hint=_hint("stage_vi")),
        _UNCLASSIFIED,
    ],
    "stage_vi": [
        _quadrant_cell("counterevidence", "active_restocking", grace=True),
        _quadrant_cell("support", "active_destocking"),
        _quadrant_cell("observation_only", "passive_restocking", note={"text": "自Ⅴ过渡早段"}),
        # Toward stages I and II: stage I, as social financing's steadying is (ticket 04).
        _quadrant_cell("observation_only", "passive_destocking", turn_hint=_hint("stage_i")),
        _quadrant_cell("observation_only", "unclassified", note=_REPAIRING),
    ],
}
_INVENTORY_QUADRANT: dict[str, Any] = {
    "key": "inventory_quadrant",
    "timing": "lagging",
    "name": "库存象限",
    "dimension": "inventory",
    "metric_id": "CN_FINISHED_GOODS_INVENTORY",
    "quadrant": {"lines": _QUADRANT_LINES, "quadrants": _QUADRANTS, "align_months": 2},
    "auxiliary": [],
    "level_line": None,
    # The month all three lines hold and the quadrant's month before it.
    "lookback_months": 2,
    "expectations": _stages(_INVENTORY_PROPOSITIONS, _QUADRANT_CELLS),
}

# The registered warrants' conversion to tonnes, frozen with the model (expectation-table.md
# O2; docs/research/futures-warrant-unit-conversion.md): no change found in 2025 to
# 2026-10-07, so each holds open-ended until a term in fact changes. Crude oil is counted in
# net barrels, with no fixed tonnes to a barrel, and stays in barrels.
_WARRANT_CONVERSIONS = [
    {
        "symbol": symbol,
        "input_unit": input_unit,
        "factor": factor,
        "unit": unit,
        "weight_basis": weight_basis,
        "basis": basis,
        "effective_from": None,
        "effective_until": None,
    }
    for symbol, input_unit, factor, unit, weight_basis, basis in (
        (
            "CF",
            "sheet",
            40,
            "tonne",
            "公定重量（名义）",
            "郑商所《棉花期货业务细则》第三条 5 吨/手、第十二条一张八手",
        ),
        ("TA", "sheet", 5, "tonne", "交割单位", "郑商所《PTA 期货业务细则》第十二条交割单位 5 吨"),
        ("PP", "lot", 5, "tonne", "交易单位", "大商所《聚丙烯期货业务细则》第八条 5 吨/手"),
        (
            "CU",
            "tonne",
            1,
            "tonne",
            "吨（上游按吨发布）",
            "上期所铜期货合约附件：每一仓单 25 吨为交割批量，非输入单位",
        ),
        ("RB", "tonne", 1, "tonne", "理论计重", "上期所螺纹钢期货合约附件第（6）项：理论计重"),
        (
            "RU",
            "tonne",
            1,
            "tonne",
            "吨（上游按吨发布）",
            "上期所天然橡胶业务细则第二十一条：每一仓单 10 吨，非输入单位",
        ),
        ("SP", "tonne", 1, "tonne", "风干重", "上期所纸浆期货业务细则第十八条：实测风干重"),
        (
            "SC",
            "barrel",
            1,
            "barrel",
            "净体积桶",
            "上期能源《交割细则》第一百五十二条：原油净体积桶数，无固定吨桶系数",
        ),
    )
]

_KEY_INDICATORS: list[dict[str, Any]] = [
    {
        "key": "pmi",
        "timing": "coincident",
        "name": "PMI",
        "dimension": "overheat",
        "metric_id": "CN_PMI_ACTIVITY",
        **_PMI_MEMBERS,
        "level_line": 50,
        # Level, momentum on the month before, slope change on the two before.
        "lookback_months": 3,
        "expectations": _PMI_EXPECTATIONS,
    },
    {
        "key": "industrial_va",
        "timing": "coincident",
        "name": "工业增加值",
        "dimension": "overheat",
        "metric_id": "CN_INDUSTRIAL_VA",
        **_INDUSTRIAL_VA_MEMBERS,
        "level_line": None,
        "lookback_months": YEAR_MONTHS,
        "expectations": _stages(_OVERHEAT_PROPOSITIONS, _INDUSTRIAL_VA_CELLS),
    },
    {
        "key": "gdp",
        "timing": "coincident",
        "name": "GDP",
        "dimension": "overheat",
        "metric_id": "CN_GDP",
        **_GDP_MEMBERS,
        "level_line": None,
        "frequency": "quarterly",
        # Level in the year, momentum and slope: four quarters (ADR-0035).
        "lookback_quarters": 4,
        "expectations": _stages(_OVERHEAT_PROPOSITIONS, _GDP_CELLS),
    },
    {
        "key": "capacity_utilization",
        "timing": "lagging",
        "name": "产能利用率",
        "dimension": "overheat",
        "metric_id": "CN_CAPACITY_UTILIZATION",
        **_CAPACITY_MEMBERS,
        "level_line": None,
        "frequency": "quarterly",
        "lookback_quarters": 4,
        "expectations": _stages(_OVERHEAT_PROPOSITIONS, _CAPACITY_CELLS),
    },
    {
        "key": "industrial_profit",
        "timing": "lagging",
        "name": "工业企业盈利",
        "dimension": "overheat",
        "metric_id": "CN_INDUSTRIAL_FINANCE",
        **_PROFIT_MEMBERS,
        "level_line": None,
        # The month and the one before; a January passed over, three back.
        "lookback_months": 3,
        "expectations": _stages(_OVERHEAT_PROPOSITIONS, _PROFIT_CELLS),
    },
    {
        "key": "ppi",
        "timing": "coincident",
        "name": "PPI",
        "dimension": "price",
        "metric_id": "CN_PPI",
        **_PPI_MEMBERS,
        # Positive or negative.
        "level_line": 0,
        "lookback_months": YEAR_MONTHS,
        "expectations": _stages(
            _PRICE_PROPOSITIONS,
            _PPI_CELLS,
            notes={"stage_ii": [{"text": "环比开始回升", "when": _PPI_MOM_TURNING}]},
            turn_hints={"stage_ii": [{"text": "stage_iii", "when": _PPI_MOM_TURNING}]},
        ),
    },
    {
        "key": "cpi",
        "timing": "lagging",
        "name": "CPI",
        "dimension": "price",
        "metric_id": "CN_CPI_HEADLINE",
        **_CPI_MEMBERS,
        "level_line": None,
        "lookback_months": YEAR_MONTHS,
        "expectations": _stages(
            _PRICE_PROPOSITIONS,
            _CPI_CELLS,
            notes={"stage_i": _CORE_STICKY, "stage_vi": _CORE_STICKY},
        ),
    },
    {
        "key": "pmi_prices",
        "timing": "coincident",
        "name": "PMI 价格",
        "dimension": "price",
        "metric_id": "CN_PMI_PRICES",
        **_PMI_PRICE_MEMBERS,
        "level_line": 50,
        "lookback_months": 3,
        "expectations": _stages(_PRICE_PROPOSITIONS, _PMI_PRICE_CELLS),
    },
    {
        "key": "social_financing",
        "timing": "leading",
        "name": "社融",
        "dimension": "credit",
        "metric_id": "CN_SF_TOTAL",
        **_SOCIAL_FINANCING_MEMBERS,
        "level_line": None,
        "lookback_months": YEAR_MONTHS,
        "expectations": _stages(
            _CREDIT_PROPOSITIONS,
            _SOCIAL_FINANCING_CELLS,
            caps={"stage_ii": _GOVERNMENT_ONLY, "stage_iii": _GOVERNMENT_ONLY},
        ),
    },
    {
        "key": "loans",
        "timing": "leading",
        "name": "贷款",
        "dimension": "credit",
        "metric_id": "CN_LOAN_STRUCTURE",
        **_LOAN_MEMBERS,
        # More or less than a year before: above or below zero.
        "level_line": 0,
        "lookback_months": 1,
        "expectations": _stages(
            _CREDIT_PROPOSITIONS, _LOAN_CELLS, notes={"stage_vi": _IMPULSE_AHEAD_OF_LOANS}
        ),
    },
    {
        "key": "money",
        "timing": "leading",
        "name": "M1/M2",
        "dimension": "credit",
        "metric_id": "CN_M1_M2",
        **_MONEY_MEMBERS,
        "level_line": None,
        "lookback_months": YEAR_MONTHS,
        "expectations": _stages(_CREDIT_PROPOSITIONS, _MONEY_CELLS),
    },
    _POLICY_RATE,
    _LPR,
    _RRR,
    _LIQUIDITY,
    _DR007,
    _INVENTORY_QUADRANT,
]


_PRICE_BLOCKS = ("observation_interfaces", "price_consistency", "supply_demand")
# Prices of each core's own kind, shown under it and never counted (GLOSSARY.md 观察接口;
# expectation-table.md E1/D2): NHII is the commodity core, no evidence of prices (N06).
_OBSERVATION_INTERFACES = [
    {
        "core": "bond",
        "core_metric_id": "CN_BOND_CORE_000012",
        "label": "债券核心（上证国债指数）",
        "members": [
            # Price indices: a rise is a stronger bond price (ticket 01).
            {
                "metric_id": "CN_BOND_10Y_930916",
                "label": "10 年国债价格指数",
                "reads_as": "bond_price",
            },
            {
                "metric_id": "CN_BOND_FULL_PRICE_CNY030",
                "label": "中债 030 全价",
                "reads_as": "bond_price",
            },
        ],
    },
    {
        "core": "stock",
        "core_metric_id": "CN_EQUITY_CORE_000985",
        "label": "股票核心（中证全指）",
        "members": [
            {"metric_id": "CN_EQ_CSI300", "label": "中证 300"},
            {"metric_id": "CN_EQ_CSI500", "label": "中证 500"},
            {"metric_id": "CN_EQ_CSI1000", "label": "中证 1000"},
            {"metric_id": "CN_EQ_ADV_DEC", "label": "市场广度：涨跌家数"},
            {"metric_id": "CN_EQ_AD_RATIO", "label": "市场广度：涨跌家数比"},
            {"metric_id": "CN_EQ_ADV_AMOUNT_SHARE", "label": "市场广度：上涨成交额占比"},
            {"metric_id": "CN_EQ_NEW_HIGH_LOW_90", "label": "市场广度：90 日新高新低"},
            {"metric_id": "CN_EQ_NEW_HIGH_LOW_250", "label": "市场广度：250 日新高新低"},
            {"metric_id": "CN_EQ_ABOVE_MA90", "label": "市场广度：站上 90 日均线占比"},
            {"metric_id": "CN_EQ_ABOVE_MA250", "label": "市场广度：站上 250 日均线占比"},
            {"metric_id": "CN_INDEX_VALUATION", "label": "估值"},
            {"metric_id": "CN_MARGIN_BALANCE_SSE_SZSE", "label": "融资余额"},
        ],
    },
    {
        "core": "commodity",
        "core_metric_id": "CN_COMMODITY_CORE_NHII",
        "label": "商品核心（南华工业品指数）",
        "members": [
            {"metric_id": "CN_COMMODITY_BROAD_NHCI", "label": "南华综合指数"},
            {"metric_id": "CN_COMMODITY_EX_HOG_BASKET", "label": "商品篮子"},
            {"metric_id": "CN_COMMODITY_SLEEVE_CONTRIBUTION", "label": "商品篮子分项贡献"},
            {"metric_id": "EIA_WTI_RWTC", "label": "WTI 原油"},
            {"metric_id": "EIA_BRENT_RBRTE", "label": "Brent 原油"},
        ],
    },
]
_RISE_ON_FEWER = "上涨集中于较少个股"
# The three cores' relative momentum over 120 sessions (O3), breadth (O1) and the basket's
# sleeves, and where each stage expects them (expectation-table.md, 价格内部一致性). A pair
# rising is its first core stronger over the sessions; turning is read from that alone, no
# shorter horizon (O3).
_PRICE_CONSISTENCY = {
    "relative_momentum": {
        "formula": "return-difference-v0001",
        "sessions": 120,
        "cores": {
            "bond": "CN_BOND_CORE_000012",
            "stock": "CN_EQUITY_CORE_000985",
            "commodity": "CN_COMMODITY_CORE_NHII",
        },
        "pairs": [
            {"key": "commodity_vs_bond", "label": "商品对债", "of": "commodity", "against": "bond"},
            {"key": "stock_vs_bond", "label": "股票对债", "of": "stock", "against": "bond"},
            {
                "key": "stock_vs_commodity",
                "label": "股票对商品",
                "of": "stock",
                "against": "commodity",
            },
        ],
    },
    # All A shares above their 90-session average against a majority: the window nearest
    # the momentum's 120 sessions. Fewer shares, never a sector or a weight (O1).
    "stock_breadth": {
        "metric_id": "CN_EQ_ABOVE_MA90",
        "dimensions": {"measure": "above_ma_share"},
        "line": 50,
        "label": "股市广度（站上 90 日均线个股占比）",
        "texts": {
            "broad_rise": "上涨普遍",
            "narrow_rise": _RISE_ON_FEWER,
            "broad_fall": "下跌普遍",
            "narrow_fall": "下跌集中于较少个股",
            "even": "涨跌个股各半",
            "index_flat": "指数持平",
        },
    },
    "basket_breadth": {
        "metric_id": "CN_COMMODITY_SLEEVE_CONTRIBUTION",
        "dimensions": {"formula_version": "ex-hog-calendar-settlement-v0003"},
        "sleeves": ["copper", "rebar", "polypropylene", "textiles", "rubber", "pulp", "crude_oil"],
        "label": "商品篮子分项广度",
        "texts": {
            "broad_rise": "上涨普遍",
            "single_sleeve_rise": "上涨集中于单一分项",
            "few_sleeves_rise": "上涨集中于少数分项",
            "broad_fall": "下跌普遍",
            "single_sleeve_fall": "下跌集中于单一分项",
            "few_sleeves_fall": "下跌集中于少数分项",
            "flat": "篮子持平",
            "unaligned": "分项累计方向与篮子不一致（逐日涨跌相互抵消）",
        },
    },
    "stages": {
        "stage_i": {
            "text": "预期债最强：商品对债、股票对债相对动量向下",
            "expect": {"commodity_vs_bond": "down", "stock_vs_bond": "down"},
            "turn_hints": [
                {
                    "text": "商品对债已回升，可能接近Ⅱ／Ⅲ",
                    "toward": ["stage_ii", "stage_iii"],
                    "when": {"commodity_vs_bond": "up"},
                }
            ],
        },
        "stage_ii": {
            "text": "预期股票对商品向上、股票对债回升、商品对债仍弱",
            "expect": {
                "stock_vs_commodity": "up",
                "stock_vs_bond": "up",
                "commodity_vs_bond": "down",
            },
            # F1, narrowed by O1.
            "breadth_notes": {
                "broad_rise": "上涨普遍",
                "narrow_rise": f"{_RISE_ON_FEWER}，阶段稳固度存疑",
            },
        },
        "stage_iii": {
            "text": "预期商品对债相对动量转强",
            "expect": {"commodity_vs_bond": "up"},
            "breadth_notes": {"broad_rise": "股市广度普遍改善"},
        },
        "stage_iv": {
            "text": "预期债最弱：股票对债、商品对债相对动量向上",
            "expect": {"stock_vs_bond": "up", "commodity_vs_bond": "up"},
            "breadth_notes": {"narrow_rise": _RISE_ON_FEWER},
        },
        "stage_v": {
            "text": "预期商品最强：商品对债向上、股票对商品向下",
            "expect": {"commodity_vs_bond": "up", "stock_vs_commodity": "down"},
            "breadth_notes": {"narrow_fall": "下跌集中于较少个股"},
        },
        "stage_vi": {
            "text": "预期三资产皆弱",
            "expect": {"bond": "down", "stock": "down", "commodity": "down"},
            "turn_hints": [
                {
                    "text": "债对商品相对动量转升，可能接近Ⅰ",
                    "toward": ["stage_i"],
                    "when": {"commodity_vs_bond": "down"},
                }
            ],
        },
    },
}
# The commodity rise's demand, tested in stages III to V (G2/K1; supply-demand
# separability): orders, purchases and production rising on with output following bear it
# out; orders and purchases falling leave it short, a supply suspicion beside it. The data
# cannot tell what drives prices.
_SUPPLY_DEMAND = {
    "stages": ["stage_iii", "stage_iv", "stage_v"],
    "improving": [
        {"indicator": "pmi", "member": "new_orders", "run": "up"},
        {"indicator": "pmi", "member": "purchase_volume", "run": "up"},
        {"indicator": "pmi", "member": "production", "run": "up"},
        {"indicator": "industrial_va", "member": "current_month", "momentum": "up"},
    ],
    "weakening": [
        {"indicator": "pmi", "member": "new_orders", "momentum": "down"},
        {"indicator": "pmi", "member": "purchase_volume", "momentum": "down"},
    ],
    "texts": {
        "label": "商品供需附注",
        "headline": "商品价格上涨，推动力未确认",
        "boundary": "现有数据只能做需求一致性检验与供给嫌疑提示，不能确认推动力",
        "demand_supported": "国内需求恢复获得支持（各关键指标各自计数，组合不另计）",
        "demand_insufficient": "需求恢复解释不足；供给、预期或晚周期因素待查",
        "mixed": "混合：需求读数不一致，不强行二选一",
        "unconfirmed": "未确认：需求读数不全，缺失不等于无供给冲击",
        "supply_suspicion": "供给嫌疑（只作附注）",
        "warrants_with_prices": "注册库存变化，来源未识别",
    },
}

# What drives the bond core's trend, by two axes (expectation-table.md, 债券归因; every
# stage, never counted). The policy axis: the window's actions and DR007, the funding
# price, agreeing -- none and flat silent, every one silent neutral; funding rates falling
# against a hike split it, so a bear market with them falling is never put down to policy
# (stage VI's note). Growth and inflation: the overheat and price dimensions' coincident
# key indicators, by the majority of all five; the lagging ones still tell the stage
# before.
_EASING_ACTION = {"cut": "easing", "hike": "tightening"}
_STRONGER = {"up": "stronger", "down": "weaker"}
_BOND_ATTRIBUTION = {
    "core": "bond",
    # The bond core is a price index: said as its price (ticket 01).
    "bond": {"bull": "债券价格走强", "bear": "债券价格走弱"},
    "axes": [
        {
            "key": "policy",
            "label": "政策维度",
            "combine": "agree",
            "signals": [
                {"indicator": "policy_rate", "reading": "action", "means": _EASING_ACTION},
                {"indicator": "lpr", "reading": "action", "means": _EASING_ACTION},
                {"indicator": "rrr", "reading": "action", "means": _EASING_ACTION},
                {
                    "indicator": "dr007",
                    "reading": "momentum",
                    "means": {"down": "easing", "up": "tightening"},
                },
            ],
            "otherwise": "neutral",
            "texts": {
                "easing": "宽松",
                "tightening": "收紧",
                "neutral": "中性",
                "mixed": "信号分化",
                "unconfirmed": "未确认",
            },
        },
        {
            "key": "growth_inflation",
            "label": "增长通胀（过热、物价）",
            "combine": "majority",
            "signals": [
                {"indicator": key, "reading": "momentum", "means": _STRONGER}
                for key in ("pmi", "industrial_va", "gdp", "ppi", "pmi_prices")
            ],
            "texts": {
                "stronger": "走强",
                "weaker": "走弱",
                "mixed": "无多数方向",
                "unconfirmed": "未确认",
            },
        },
    ],
    # The first row that holds names the driver; none holding, it is unclear.
    "table": [
        {
            "bond": "bear",
            "policy": ["tightening", "neutral"],
            "growth_inflation": ["stronger"],
            "driver": "fundamentals",
            "typical": "典型Ⅳ",
        },
        {
            "bond": "bear",
            "policy": ["tightening"],
            "growth_inflation": ["weaker"],
            "driver": "policy_liquidity",
        },
        {
            "bond": "bear",
            "policy": ["easing"],
            "growth_inflation": ["weaker"],
            "driver": "unclear",
            "suspicion": "财政供给、信用风险或期限溢价嫌疑",
        },
        {
            "bond": "bull",
            "policy": ["easing"],
            "growth_inflation": ["weaker"],
            "driver": "fundamentals_and_easing",
            "typical": "典型Ⅰ、Ⅵ→Ⅰ",
        },
        # Whatever growth and inflation do.
        {"bond": "bull", "policy": ["tightening"], "driver": "unclear", "suspicion": "避险嫌疑"},
    ],
    "drivers": {
        "fundamentals": "基本面推动",
        "policy_liquidity": "政策或流动性推动",
        "fundamentals_and_easing": "基本面加宽松推动",
        "unclear": "推动力不明",
    },
    "texts": {
        "label": "债券归因",
        "boundary": "债券状态旁的解释附注：不计入确认度，不由宽松程度推算或改写债券牛熊与正式阶段",
        "term_premium": "期限溢价归因未确认",
        "unclear_refinement": "收益率曲线与信用利差未接入，推动力不明暂不细分",
        "bond_unknown": "债券核心状态未定",
        "not_in_table": "两轴组合不在归因表中",
    },
}
