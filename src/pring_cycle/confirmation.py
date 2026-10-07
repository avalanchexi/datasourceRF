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
"""

from __future__ import annotations

import calendar
import copy
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pring_cycle.domain import FormalStage

OUTPUT_STRUCTURE = "confirmation-v0001"
MACRO_RULES_VERSION = "macro-confirmation-v0001"
# The manifest fields that hold confirmation; a manifest with none of them reads the four
# single-dimension labels of the models before it.
MANIFEST_FIELDS = ("macro_rules_version", "projection_output_structure", "confirmation_rules")
DIMENSIONS = ("policy", "credit", "overheat", "price", "inventory")
RELATIONS = ("support", "counterevidence", "observation_only", "unconfirmed", "not_applicable")
TIMINGS = ("leading", "coincident", "lagging")
MATURITIES = ("sprout", "forming", "confirmed")
# The months a period of each frequency spans.
FREQUENCIES = {"monthly": 1, "quarterly": 3}
_UNITS = {"monthly": "month", "quarterly": "quarter"}
_ADJACENT = {"next": 1, "previous": -1}
# A year of a monthly series: where a value stands in its range, and how large a change is,
# are read within it and nowhere further back (ADR-0035).
YEAR_MONTHS = 12
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
}
# The readings only a year of months answers.
_YEAR_READINGS = frozenset({"position", "change_size"})


@dataclass(frozen=True)
class DerivedInput:
    """One input of a derived member: a metric's member, ``offsets`` months back."""

    name: str
    metric_id: str
    dimensions: Mapping[str, str]
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
    agrees_by: str = "momentum"


_SF_YTD = {"measure": "ytd_increment"}
# Deterministic processing frozen with the model (spec: a month's flow from year-to-date
# totals).
DERIVED_FORMULAS: dict[str, DerivedFormula] = {
    "sf-monthly-increment-yoy-change-v0001": DerivedFormula(
        (DerivedInput("ytd", "CN_SF_TOTAL", _SF_YTD, (0, 1, 12, 13)),),
        _monthly_increment_yoy_change,
        months=1,
        agrees_by="sign",
    ),
}
# A shown derived value of two members of the same month: the first less the second.
SPREAD_FORMULAS = frozenset({"m1-m2-yoy-spread-v0001"})


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


@dataclass(frozen=True)
class Spread:
    """A value shown beside a key indicator, never counted: one member less another."""

    name: str
    label: str
    formula: str
    of: tuple[str, str]


@dataclass(frozen=True)
class Condition:
    """Readings that must all hold, of the main member unless ``member`` names another.

    A reading given several values holds for any of them. ``outpaces`` names a member
    this one must have risen more than since the period before.
    """

    readings: Mapping[str, str | tuple[str, ...]]
    member: str | None = None
    outpaces: str | None = None


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
class KeyIndicator:
    """A key indicator: its members, its periods (months or quarters) and its timing.

    ``lookback`` periods are read for its readings and ``grace`` more before them, so
    each of the newest ``grace`` + 1 periods reads as it stood: of the main member, and of
    any other a turn hint reads.
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

    @property
    def members(self) -> tuple[Member, ...]:
        return (self.main, *self.auxiliary)

    @property
    def step(self) -> int:
        """The months one period spans."""
        return FREQUENCIES[self.frequency]

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
        return self.grace if member is self.main or member.name in named else 0

    def reach(self, member: Member) -> int:
        """How many periods back ``member`` is read in all: its own and its grace's, up to
        the horizon. A period grace reads that needs one beyond reads that one unknown."""
        return min(self.periods(member) + self.history(member), self.horizon + 1)

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
        grace, horizon, timing = _timing_rules(
            document.get("timing_rules"), document.get("maturity_rules")
        )
        indicators = tuple(_indicator(item, grace, horizon) for item in raw)
        if len({item.key for item in indicators}) != len(indicators):
            raise ValueError("confirmation_key_indicator_duplicate")
        return cls(OUTPUT_STRUCTURE, MACRO_RULES_VERSION, indicators, timing)

    def metric_ids(self) -> frozenset[str]:
        """Every metric the indicators read: their members' and derived members' inputs."""
        return frozenset(
            metric_id
            for indicator in self.indicators
            for member in indicator.members
            for metric_id in (
                [item.metric_id for item in DERIVED_FORMULAS[member.formula].inputs]
                if member.formula is not None
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
        values = self._year()
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
        """Marked when the newest change is wider than the median change of the year."""
        values = self._year()
        if values is None or len(values) < 3:
            return None
        sizes = [abs(after - before) for before, after in zip(values, values[1:], strict=False)]
        marked = _direction(sizes[-1], statistics.median(sizes)) == "up"
        return "marked" if marked else "ordinary"

    def _year(self) -> tuple[float, ...] | None:
        if self.months < YEAR_MONTHS or self.missing or not self.points:
            return None
        return self.values

    def reading(self, name: str) -> str | None:
        return getattr(self, name)  # type: ignore[no-any-return]


def confirmation_document(
    rules: ConfirmationRules,
    readings: Mapping[str, Sequence[MemberReading]],
    *,
    current_stage: FormalStage | None,
    stage_reason: str,
) -> dict[str, object]:
    """The dimension summary of the rules' indicators read as ``readings`` under the stage.

    ``readings`` holds each indicator's members by its key, the main one first.
    """
    stage = current_stage.value if current_stage is not None else None
    documents = [
        _indicator_document(item, readings[item.key], stage=stage, timing=rules.timing)
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
) -> tuple[tuple[tuple[str, float, str], ...], tuple[str, ...], tuple[str, ...]]:
    """``formula`` for each of ``months`` (``YYYY-MM``, oldest first), from its inputs.

    ``value`` gives an input's (value, observation version) of a month, or None. The
    points run from the newest back while every input is held; the months short of one
    are missing, and the observations the points rest on are their inputs.
    """
    definition = DERIVED_FORMULAS[formula]
    points: list[tuple[str, float, str]] = []
    missing: list[str] = []
    inputs: list[str] = []
    for month in reversed(months):
        held: dict[tuple[str, int], float] = {}
        versions: list[str] = []
        for item in definition.inputs:
            for offset in item.offsets:
                found = value(item, month_back(month, offset))
                if found is not None:
                    held[(item.name, offset)] = found[0]
                    versions.append(found[1])
        try:
            # The formula takes what the month needs of its inputs: January's flow is its
            # own year-to-date total, with no month before it.
            result = definition.compute(month, held)
        except KeyError:
            result = None
        if result is None:
            missing.append(month)
        elif not missing:
            points.insert(0, (month_end(month), result, formula))
            inputs.extend(versions)
    return tuple(points), tuple(reversed(missing)), tuple(dict.fromkeys(inputs))


def month_back(month: str, offset: int) -> str:
    """The month (``YYYY-MM``) ``offset`` months before ``month``."""
    year, number = (int(part) for part in month.split("-"))
    ordinal = year * 12 + number - 1 - offset
    return f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"


def month_end(month: str) -> str:
    """The last day (ISO) of ``month`` (``YYYY-MM``)."""
    year, number = (int(part) for part in month.split("-"))
    return f"{month}-{calendar.monthrange(year, number)[1]:02d}"


def _indicator_document(
    indicator: KeyIndicator,
    members: Sequence[MemberReading],
    *,
    stage: str | None,
    timing: TimingRules,
) -> dict[str, object]:
    main, auxiliary = members[0], tuple(members[1:])
    agreement = [_agreement(main, member) for member in auxiliary]
    divergent = "opposes" in agreement
    by_member = {member.member.name: member for member in members}
    document: dict[str, object] = {
        "key": indicator.key,
        "name": indicator.name,
        "dimension": indicator.dimension,
        "metric_id": indicator.metric_id,
        "timing": indicator.timing,
        # What the indicator counts for: its newest period, however many days read it.
        "statistical_period": main.period,
        "level_line": indicator.level_line,
        "consistency": (
            "unknown" if main.momentum is None else "divergent" if divergent else "consistent"
        ),
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
    if main.evidence_status != "current" or not main.points or main.missing:
        # Every reading of the main member is known, or none is said: a month short of
        # its lookback leaves a momentum, a slope or a year's range unknown, never read
        # as a direction.
        status = (
            [main.evidence_status] if main.evidence_status != "current" or not main.points else []
        )
        missing = [f"{_member_label(main.member)}:{item}" for item in (*status, *main.missing)]
        return {**document, "relation": "unconfirmed", "missing": missing}
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
        gaps = (shifted.missing or (shifted.evidence_status,)) if shifted else ("not_read",)
        missing.extend(f"{_member_label(member.member)}:{gap}" for gap in gaps)
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
    """How a member's direction stands to the main one's momentum: agrees, opposes, flat,
    unknown."""
    direction = member.direction
    if member.evidence_status != "current" or direction is None or main.momentum is None:
        return "unknown"
    if direction == main.momentum:
        return "agrees"
    if "flat" in {direction, main.momentum}:
        return "flat"
    return "opposes"


def _member_document(member: MemberReading, consistency: str) -> dict[str, object]:
    latest = member.points[-1] if member.points else None
    return {
        "role": member.role,
        "name": member.member.name,
        "label": member.member.label,
        "metric_id": member.member.metric_id,
        "member": dict(member.member.dimensions),
        "formula_version": member.member.formula,
        "evidence_status": member.evidence_status,
        "period": latest[0] if latest is not None else None,
        "value": latest[1] if latest is not None else None,
        "periods": [period for period, _value, _version in member.points],
        "values": list(member.values),
        "observation_version_ids": (
            list(member.inputs)
            if member.member.formula is not None
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
        "missing": list(member.missing),
        # The periods read from the member standing in, as its label says (cumulative).
        "stand_ins": [
            {"period": period, "label": member.member.stand_in_label}
            for period, _value, _version in member.points
            if int(period[5:7]) in member.member.stand_ins
        ],
    }


def _derived_document(derived: Spread, by_member: Mapping[str, MemberReading]) -> dict[str, object]:
    """A spread of two members over the months both hold, newest last; never counted."""
    first, second = (by_member[name] for name in derived.of)
    others = {period: value for period, value, _version in second.points}
    points = [
        (period, value - others[period])
        for period, value, _version in first.points
        if period in others
    ]
    values = [value for _period, value in points]
    return {
        "name": derived.name,
        "label": derived.label,
        "formula_version": derived.formula,
        "inputs": [first.member.name, second.member.name],
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
    dimensions = member.dimensions
    return ",".join(f"{key}={value}" for key, value in sorted(dimensions.items()))


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
) -> tuple[dict[str, int], dict[str, int], TimingRules]:
    """Grace and the farthest period back by frequency, the stage each timing points to,
    and when a signal forms."""
    if not isinstance(timing, Mapping) or not isinstance(maturity, Mapping):
        raise ValueError("confirmation_timing_rules_invalid")
    grace, adjacent = timing.get("grace_periods"), timing.get("adjacent_stage")
    horizon = timing.get("horizon_periods")
    counts = [
        item.get(name)
        for item in (grace, horizon)
        if isinstance(item, Mapping)
        for name in FREQUENCIES
    ]
    counts += [maturity.get("forming_periods"), maturity.get("forming_signals")]
    if (
        not isinstance(grace, Mapping)
        or not isinstance(horizon, Mapping)
        or set(grace) != set(FREQUENCIES)
        or set(horizon) != set(FREQUENCIES)
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
        TimingRules(
            {str(name): str(item) for name, item in adjacent.items()},
            int(maturity["forming_periods"]),
            int(maturity["forming_signals"]),
        ),
    )


def _indicator(value: object, grace: Mapping[str, int], horizon: Mapping[str, int]) -> KeyIndicator:
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
    # Months are read up to a year, quarters up to four.
    own, other = (
        ("lookback_months", "lookback_quarters")
        if frequency == "monthly"
        else ("lookback_quarters", "lookback_months")
    )
    line, lookback = value.get("level_line"), value.get(own)
    raw_auxiliary = value.get("auxiliary")
    raw_derived = value.get("derived", [])
    expectations = value.get("expectations")
    if (
        (line is not None and (not isinstance(line, (int, float)) or isinstance(line, bool)))
        or not isinstance(lookback, int)
        or isinstance(lookback, bool)
        or not 1 <= lookback <= YEAR_MONTHS // FREQUENCIES[str(frequency)]
        or other in value
        or not isinstance(raw_auxiliary, list)
        or not isinstance(raw_derived, list)
        or not isinstance(expectations, Mapping)
        or set(expectations) != set(_STAGES)
    ):
        raise ValueError("confirmation_key_indicator_invalid")
    periods_grace, farthest = grace[str(frequency)], horizon[str(frequency)]
    if lookback - 1 > farthest:
        # Grace reads each period as it stood as far as the horizon; the readings never
        # beyond it.
        raise ValueError("confirmation_lookback_beyond_horizon")
    main = _member(value.get("main"), texts["metric_id"])
    if main.formula is not None:
        raise ValueError("confirmation_main_member_derived")
    auxiliary = tuple(_member(item, texts["metric_id"]) for item in raw_auxiliary)
    names = {member.name for member in (main, *auxiliary)}
    if len(names) != 1 + len(auxiliary):
        raise ValueError("confirmation_member_duplicate")
    if frequency != "monthly" and any(
        member.unreleased_months or member.stand_ins or member.formula
        for member in (main, *auxiliary)
    ):
        raise ValueError("confirmation_member_months_need_monthly")
    derived = tuple(_spread(item, names) for item in raw_derived)
    stages = {stage: _expectation(expectations[stage], names) for stage in _STAGES}
    if lookback < YEAR_MONTHS and any(
        _YEAR_READINGS & set(condition.readings)
        for expectation in stages.values()
        for cell in expectation.cells
        for condition in cell.when
    ):
        # A range or a change size read short of a year would read another scale.
        raise ValueError("confirmation_year_reading_needs_a_year")
    return KeyIndicator(
        **texts,
        main=main,
        auxiliary=auxiliary,
        derived=derived,
        level_line=float(line) if line is not None else None,
        lookback=lookback,
        expectations=stages,
        grace=periods_grace,
        frequency=str(frequency),
        horizon=farthest,
    )


def _expectation(value: object, names: set[str]) -> Expectation:
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
    notes, turn_hints, caps = (
        tuple(annotation for item in items if (annotation := _annotation(item, names)) is not None)
        for items in lists
    )
    if any(not hint.when or hint.text not in _STAGES for hint in turn_hints):
        # A stage's hint is a signal of its own: what it reads is how long it held.
        raise ValueError("confirmation_turn_hint_invalid")
    return Expectation(
        proposition,
        tuple(_cell(item, names) for item in raw_cells),
        notes,
        turn_hints,
        caps,
    )


def _cell(value: object, names: set[str]) -> Cell:
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
        _annotation({"text": "transmission", "when": raw_confirmed}, names)
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
        note=_annotation(value.get("note"), names),
        turn_hint=turn_hint,
        grace=grace,
        confirmed_when=confirmed_when,
    )


def _annotation(value: object, names: set[str]) -> Annotation | None:
    """An annotation's text and its conditions: one mapping, or a list all must hold."""
    if value is None:
        return None
    if not isinstance(value, Mapping) or not isinstance(value.get("text"), str):
        raise ValueError("confirmation_annotation_invalid")
    when = value.get("when")
    items = [] if when is None else when if isinstance(when, list) else [when]
    return Annotation(str(value["text"]), tuple(_condition(item, names) for item in items))


def _condition(value: object, names: set[str]) -> Condition:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_condition_invalid")
    readings: dict[str, str | tuple[str, ...]] = {}
    for name, expected in value.items():
        if name in {"member", "outpaces"}:
            continue
        values = expected if isinstance(expected, list) else [expected]
        if name not in _READINGS or not values or not set(values) <= _READINGS[name]:
            raise ValueError(f"confirmation_condition_unknown:{name}")
        readings[name] = str(expected) if not isinstance(expected, list) else tuple(values)
    member, outpaces = value.get("member"), value.get("outpaces")
    if not readings and outpaces is None:
        raise ValueError("confirmation_condition_invalid")
    for reference in (member, outpaces):
        if reference is not None and reference not in names:
            raise ValueError(f"confirmation_member_unknown:{reference}")
    return Condition(
        readings,
        str(member) if member is not None else None,
        str(outpaces) if outpaces is not None else None,
    )


def _member(value: object, metric_id: str) -> Member:
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_member_invalid")
    name, label = value.get("name"), value.get("label")
    own = value.get("metric_id", metric_id)
    formula = value.get("formula")
    dimensions = _dimensions(value.get("dimensions")) if formula is None else {}
    raw_months = value.get("unreleased_months", [])
    raw_stand_ins = value.get("stand_ins", {})
    stand_in_label = value.get("stand_in_label")
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(label, str)
        or not label
        or not isinstance(own, str)
        or not isinstance(raw_months, list)
        or not all(isinstance(month, int) and 1 <= month <= 12 for month in raw_months)
        or not isinstance(raw_stand_ins, Mapping)
        or (bool(raw_stand_ins) != isinstance(stand_in_label, str))
        or (formula is not None and formula not in DERIVED_FORMULAS)
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
    )


def _spread(value: object, names: set[str]) -> Spread:
    """A shown spread of two members, ``of`` naming them: the first less the second."""
    if not isinstance(value, Mapping):
        raise ValueError("confirmation_derived_invalid")
    name, label, formula, of = (value.get(key) for key in ("name", "label", "formula", "of"))
    if (
        not isinstance(name, str)
        or not isinstance(label, str)
        or formula not in SPREAD_FORMULAS
        or not isinstance(of, list)
        or len(of) != 2
        or not all(item in names for item in of)
    ):
        raise ValueError("confirmation_derived_invalid")
    return Spread(name, label, str(formula), (str(of[0]), str(of[1])))


def _dimensions(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
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
    }


# Grace in independent periods; the farthest period back a reading or its grace reaches,
# thirteen months and four quarters (ADR-0035); the stage a lag still shows, the stage a
# lead already shows (expectation-table.md E3/D4, N4).
_TIMING_RULES = {
    "grace_periods": {"monthly": 2, "quarterly": 1},
    "horizon_periods": {"monthly": 13, "quarterly": 3},
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
_INDUSTRIAL_VA_MEMBERS = {
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
]
