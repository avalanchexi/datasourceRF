"""The day summary: one trading day's core readiness, context and published projection set.

The target day and each backfilled day go through the same steps -- core readiness, the
context projection, then publishing that day's analytical projection set -- and differ
only in what they are given. The target day is judged at the run's frozen cutoff and
carries the run's materials (its gap list, release calendar and explanatory warnings);
a backfilled day sees only details public by that day's end and carries none of them.

Everything a summary depends on is passed in: the batch id its rows are attributed to
(none when not given), the SSE calendar and the release schedule. Nothing is read from
the caller's scope. A run follows the target day's steps through ``RunMaterials``: it is
told as each step completes, when the evidence snapshot is frozen and when a backfilled
day fails, at the moment each happens.

Kept as they were, and so documented here: a day that fails to backfill leaves the days
after it on the stage confirmed before it (a later run fills only that day, and nothing
is recomputed in cascade); a degraded summary still counts as summarized and is never
recomputed, since published history is not rewritten. Some freshness labels of a
backfilled day follow the run's time rather than the day's; they are not displayed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pring_cycle.batches import processing_batch
from pring_cycle.catalog import MetricDefinition
from pring_cycle.claim_adoption import ClaimAdoption, core_identity_holds
from pring_cycle.context_projection import (
    ContextProjection,
    ContextProjectionRules,
    build_context_projection,
)
from pring_cycle.domain import FormalStage
from pring_cycle.domain.trend import PricePoint, TrendRules, evaluate_trend
from pring_cycle.evidence import AsOfMode, EvidenceRepository, EvidenceValueState, MetricSeriesPoint
from pring_cycle.freshness import add_projection_gaps, release_schedule_scope, use_release_schedule
from pring_cycle.models import ModelRepository
from pring_cycle.p0 import CARRIED_FORWARD, CoreAssetReadiness, P0ProjectionService, P0PublishResult
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.trading_calendar import TradingCalendar, run_calendar_scope, use_run_calendar

CORE_METRICS = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}
SHANGHAI = ZoneInfo("Asia/Shanghai")

CoreReadiness = tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness]


def _no_warnings(_context: ContextProjection) -> tuple[str, ...]:
    return ()


def _ignore(_value: object) -> None:
    return None


@dataclass(frozen=True)
class FailedDay:
    """A window day that could not be summarized; a later run tries it again."""

    day: str
    error: str


@dataclass(frozen=True)
class RunMaterials:
    """What only the target day's run brings, and how it follows the summary.

    ``explanatory_warnings`` reads the day's context for the
    explanatory evidence warnings; its result goes before the context's own.

    ``step_done`` hears ``core_readiness``, ``context`` and ``backfill`` as each completes
    (a run advances its own steps there, and a cancelled run stops the summary by
    raising); ``snapshot_frozen`` gets the evidence snapshot id before publishing, and
    ``day_failed`` each backfilled day that could not be summarized.
    """

    freshness_gaps: tuple[Mapping[str, object], ...] = ()
    plan_gaps: tuple[Mapping[str, object], ...] = ()
    derived_requirements: tuple[Mapping[str, object], ...] = ()
    release_calendar_events: tuple[dict[str, object], ...] = ()
    explanatory_warnings: Callable[[ContextProjection], tuple[str, ...]] = _no_warnings
    step_done: Callable[[str], None] = _ignore
    snapshot_frozen: Callable[[str], None] = _ignore
    day_failed: Callable[[FailedDay], None] = _ignore


@dataclass(frozen=True)
class TargetSummary:
    result: P0PublishResult
    evidence_snapshot_id: str | None
    failed_days: tuple[FailedDay, ...] = ()


@dataclass(frozen=True)
class ModelRules:
    """The active model as the summary reads it."""

    model_version_id: str
    manifest: Mapping[str, object]
    definition_version: str
    trend_rules: TrendRules
    definitions: tuple[MetricDefinition, ...] = field(default=())

    @classmethod
    def of(cls, models: ModelRepository, model_version_id: str) -> ModelRules:
        manifest = models.manifest(model_version_id)
        rules = ContextProjectionRules.from_manifest(manifest)
        return cls(
            model_version_id,
            manifest,
            rules.metric_catalog_version,
            _trend_rules(manifest),
            rules.metric_definitions,
        )


def _trend_rules(manifest: Mapping[str, object]) -> TrendRules:
    document = manifest.get("trend_rules")
    if not isinstance(document, dict):
        raise ValueError("model_trend_rules_missing")
    try:
        return TrendRules(
            window_days=int(document["window_days"]),
            slope_days=int(document["slope_days"]),
            volatility_days=int(document["volatility_days"]),
            noise_multiplier=float(document["noise_multiplier"]),
            persistence_days=int(document["persistence_days"]),
            candidate_window_days=int(document["candidate_window_days"]),
            candidate_duration_rule_version=str(
                document.get("candidate_duration_rule_version", "candidate-duration-v0001")
            ),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("model_trend_rules_invalid") from error


class DaySummaries:
    def __init__(
        self,
        evidence: EvidenceRepository,
        projections: ProjectionSetRepository,
        model: ModelRules,
        *,
        calendar: TradingCalendar,
        window_calendar: TradingCalendar | None = None,
        release_schedule: Mapping[str, tuple[datetime | date, ...]] | None = None,
        batch_id: str | None = None,
    ) -> None:
        """``window_calendar`` counts only gate ①'s windows, which for a backfilled day reach
        before the run's; ``calendar`` stays the run's, as its gap list reads it."""
        self._evidence = evidence
        self._projections = projections
        self._model = model
        self._calendar = calendar
        self._window_calendar = window_calendar or calendar
        self._schedule = release_schedule or {}
        self._batch_id = batch_id

    @contextmanager
    def _scope(self) -> Iterator[None]:
        """The batch, calendar and release schedule the summary's reads and writes use."""
        with (
            processing_batch(self._batch_id),
            run_calendar_scope(),
            release_schedule_scope(),
        ):
            use_run_calendar(self._calendar)
            use_release_schedule(self._schedule)
            yield

    def summarize_target(
        self,
        day: str,
        *,
        system_as_of: datetime,
        run_materials: RunMaterials,
        backfill_window: tuple[str, ...] = (),
    ) -> TargetSummary:
        """Summarize the target day at the run's cutoff, with the window's missed days.

        The target's readiness and context are computed first; the missed window days are
        then backfilled, and the target's stage is confirmed against the history they
        rebuilt before it is published.
        """
        with self._scope():
            readiness = self._core_readiness(day, system_as_of=system_as_of)
            run_materials.step_done("core_readiness")
            context = self._context(day, readiness, system_as_of=system_as_of)
            run_materials.step_done("context")
            failed = self._backfill(
                backfill_window,
                target=day,
                system_as_of=system_as_of,
                day_failed=run_materials.day_failed,
            )
            run_materials.step_done("backfill")
            last_stage = self._last_confirmed_stage(day)
            snapshot_id = self._freeze(readiness, context, system_as_of=system_as_of)
            if snapshot_id is not None:
                run_materials.snapshot_frozen(snapshot_id)
            result = P0ProjectionService(self._projections).publish(
                target_business_date=day,
                system_as_of=system_as_of,
                assets=readiness,
                last_confirmed_stage=last_stage,
                model_version_id=self._model.model_version_id,
                warnings=tuple(
                    dict.fromkeys(run_materials.explanatory_warnings(context) + context.warnings)
                ),
                evidence_snapshot_id=snapshot_id,
                macro_document=context.macro,
                inventory_document=context.inventory,
                release_calendar_events=run_materials.release_calendar_events,
                gap_list=tuple(
                    add_projection_gaps(
                        run_materials.freshness_gaps,
                        (context.macro, context.inventory),
                        derived_requirements=run_materials.derived_requirements,
                        plan_gaps=run_materials.plan_gaps,
                        definitions=self._model.definitions,
                    )
                ),
            )
        return TargetSummary(result, snapshot_id, failed)

    def backfill(
        self, window: tuple[str, ...], *, target: str, system_as_of: datetime
    ) -> tuple[FailedDay, ...]:
        """Summarize each window day before ``target`` that has no summary, in order.

        With no summary at all this is the first initialization: every earlier day of the
        window is summarized, which rebuilds the stage history. A daily run fills only the
        days it missed. A day that cannot be summarized is returned, and the rest go on.
        """
        with self._scope():
            return self._backfill(window, target=target, system_as_of=system_as_of)

    def _backfill(
        self,
        window: tuple[str, ...],
        *,
        target: str,
        system_as_of: datetime,
        day_failed: Callable[[FailedDay], None] = _ignore,
    ) -> tuple[FailedDay, ...]:
        summarized = self._projections.summarized_dates()
        failed: list[FailedDay] = []
        for day in (day for day in window if day < target and day not in summarized):
            try:
                self._summarize_day(day, system_as_of=system_as_of)
            except (KeyError, LookupError, TypeError, ValueError) as error:
                failed.append(FailedDay(day, type(error).__name__))
                day_failed(failed[-1])
        return tuple(failed)

    def _summarize_day(self, day: str, *, system_as_of: datetime) -> None:
        """Publish one earlier day's summary from what was public by that day's end."""
        public_end = datetime.combine(date.fromisoformat(day), time.max, tzinfo=SHANGHAI)
        readiness = self._core_readiness(day, system_as_of=system_as_of, public_as_of=public_end)
        context = self._context(day, readiness, system_as_of=system_as_of, persist_derived=False)
        P0ProjectionService(self._projections).publish(
            target_business_date=day,
            system_as_of=system_as_of,
            assets=readiness,
            last_confirmed_stage=self._last_confirmed_stage(day),
            model_version_id=self._model.model_version_id,
            warnings=context.warnings,
            evidence_snapshot_id=self._freeze(readiness, context, system_as_of=system_as_of),
            macro_document=context.macro,
            inventory_document=context.inventory,
        )

    def _freeze(
        self, readiness: CoreReadiness, context: ContextProjection, *, system_as_of: datetime
    ) -> str | None:
        """Freeze what the day read: the cores shown, their model inputs, the context's.

        At the run's cutoff, as the day's inputs were selected; a backfilled day's derived
        identities are listed though not stored. None when the day read nothing.
        """
        observation_versions = (
            tuple(version for item in readiness for version in item.observation_version_ids)
            + tuple(
                version
                for item in readiness
                for version in (item.model_input_observation_version_ids or ())
            )
            + context.observation_version_ids
        )
        if not observation_versions:
            return None
        return self._evidence.freeze_snapshot(
            observation_versions, mode=AsOfMode.SYSTEM, as_of=system_as_of
        ).evidence_snapshot_id

    def _context(
        self,
        day: str,
        readiness: CoreReadiness,
        *,
        system_as_of: datetime,
        persist_derived: bool = True,
    ) -> ContextProjection:
        return build_context_projection(
            self._evidence,
            as_of=system_as_of,
            model_manifest=self._model.manifest,
            target_business_date=day,
            visible_evidence_start=max(
                (
                    item.evidence_window_start
                    for item in readiness
                    if item.evidence_window_start is not None
                ),
                default=None,
            ),
            persist_derived=persist_derived,
        )

    def _last_confirmed_stage(self, day: str) -> FormalStage | None:
        value = self._projections.last_confirmed_stage(on_or_before=day)
        return FormalStage(str(value)) if value is not None else None

    def _core_readiness(
        self,
        day: str,
        *,
        system_as_of: datetime,
        public_as_of: datetime | None = None,
    ) -> CoreReadiness:
        """Each core's state on ``day``; ``public_as_of`` hides later publications.

        Gate ①: a session of the 120 to ``day`` that the visible series lacks holds the
        stage, ``day`` itself aside (the carry-forward case). Sessions before the series'
        first close are short history, left to the trend, and a window the calendar does
        not reach is a LookupError (ticket 11).
        """
        rules = self._model.trend_rules
        target = date.fromisoformat(day)
        previous_session = self._calendar.latest_on_or_before(target - timedelta(days=1))
        results = []
        for asset, metric_id in CORE_METRICS.items():
            series = tuple(
                point
                for point in self._evidence.metric_series(
                    metric_id,
                    mode=AsOfMode.SYSTEM,
                    as_of=system_as_of,
                    public_as_of=public_as_of,
                    definition_version=self._model.definition_version,
                )
                if point.period_end <= day
            )
            reason = "validated"
            state = None
            candidate_state = None
            candidate_days = 0
            candidate_30d = None
            proxy_12m = None
            distance_pct = None
            slope_pct = None
            noise_band_pct = None
            model_inputs: tuple[str, ...] = ()
            # One session behind is carried: the previous close stands in for the target in
            # the calculation only and is never stored as a claim. Two or more is a real gap.
            carried = bool(series) and series[-1].period_end == previous_session.isoformat()
            if not series:
                reason = "source_missing"
            elif self._window_missing(target, series):
                reason = "window_session_missing"
            elif any(item.selection_status == "conflicted" for item in series):
                reason = "source_conflict"
            elif series[-1].period_end != day and not carried:
                reason = "stale_for_target_business_date"
            elif any(not core_identity_holds(metric_id, point) for point in series):
                reason = "source_identity_invalid"
            elif any(
                item.value_state is not EvidenceValueState.REPORTED_VALUE
                or item.selected_value is None
                for item in series
            ):
                reason = "nonnumeric_core_observation"
            elif self._originals_disagree(metric_id, series):
                reason = "source_original_invalid"
            else:
                points = [
                    PricePoint(date.fromisoformat(item.period_end), float(item.selected_value))
                    for item in series
                    if item.selected_value is not None
                ]
                if carried:
                    points.append(PricePoint(target, points[-1].value))
                    reason = CARRIED_FORWARD
                trend = evaluate_trend(points, rules)
                model_inputs = tuple(
                    item.selected_claim_id for item in series if item.selected_claim_id is not None
                )
                state = trend.stable_state
                candidate_state = trend.candidate_state
                candidate_days = rules.candidate_days_for_output(trend)
                candidate_30d = trend.candidate_30d
                proxy_12m = trend.proxy_12m
                distance_pct = trend.distance_pct
                slope_pct = trend.slope_pct
                noise_band_pct = trend.noise_band_pct
                if state is None:
                    reason = trend.reason
            results.append(
                # Keep the price display at 120 observations. The separate input
                # manifest preserves the full preheat used by the stateful trend.
                CoreAssetReadiness(
                    asset=asset,
                    metric_id=metric_id,
                    state=state,
                    reason=reason,
                    observation_count=len(series[-120:]),
                    latest_business_date=series[-1].period_end if series else None,
                    observation_version_ids=tuple(
                        item.selected_claim_id
                        for item in series[-120:]
                        if item.selected_claim_id is not None
                    ),
                    evidence_window_start=(series[-120].period_end if len(series) >= 120 else None),
                    candidate_state=candidate_state,
                    candidate_days=candidate_days,
                    candidate_30d=candidate_30d,
                    proxy_12m=proxy_12m,
                    distance_pct=distance_pct,
                    slope_pct=slope_pct,
                    noise_band_pct=noise_band_pct,
                    model_input_observation_version_ids=model_inputs,
                    carried_forward=carried and state is not None,
                )
            )
        return tuple(results)  # type: ignore[return-value]

    def _window_missing(self, day: date, series: tuple[MetricSeriesPoint, ...]) -> bool:
        held = {point.period_end for point in series}
        window = self._window_calendar.sessions_to(
            day, 120, since=date.fromisoformat(series[0].period_end)
        )
        return any(session.isoformat() not in held for session in window if session != day)

    def _originals_disagree(self, metric_id: str, series: tuple[MetricSeriesPoint, ...]) -> bool:
        """Whether a registered core's originals no longer state the selected closes.

        Only asked once every cheaper reason has passed, since it reparses the originals.
        """
        adoption = ClaimAdoption(
            self._evidence, definition_version=self._model.definition_version
        ).check({metric_id: series})[metric_id]
        return adoption.rechecked and any(
            point.selected_claim_id not in adoption.adoptable for point in series
        )
