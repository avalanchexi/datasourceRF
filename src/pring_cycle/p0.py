from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from pring_cycle.batches import current_batch_id
from pring_cycle.display_projection import display_days, history_display
from pring_cycle.domain import CoreAssetState, FormalStage
from pring_cycle.domain.stage import StageResult, derive_formal_stage
from pring_cycle.macro_judgement import Earlier, MacroJudgementRules, judge, with_reference
from pring_cycle.macro_judgement import record as record_macro
from pring_cycle.macro_signals import regrouped, rejudged
from pring_cycle.macro_verification import combination_of, restated, verified
from pring_cycle.noncanonical import build_basis
from pring_cycle.projections import (
    ANALYTICAL_DATASETS,
    INVENTORY_CARD_NAMES,
    ProjectionEnvelope,
    ProjectionSetRepository,
    validate_analytical_projection,
)
from pring_cycle.stage_lookback import FOUND, StageLookback

# A core one session behind its target is priced at its previous session (ticket 21).
CARRIED_FORWARD = "carried_forward_one_session"


@dataclass(frozen=True)
class CoreAssetReadiness:
    asset: str
    metric_id: str
    state: CoreAssetState | None
    reason: str
    observation_count: int
    latest_business_date: str | None
    observation_version_ids: tuple[str, ...] = ()
    evidence_window_start: str | None = None
    candidate_state: CoreAssetState | None = None
    candidate_days: int = 0
    candidate_30d: CoreAssetState | None = None
    proxy_12m: CoreAssetState | None = None
    # Off, the proxy is not shown at all; on with too short a history, it is unavailable.
    proxy_12m_enabled: bool = True
    distance_pct: float | None = None
    slope_pct: float | None = None
    noise_band_pct: float | None = None
    model_input_observation_version_ids: tuple[str, ...] | None = None
    carried_forward: bool = False
    # The actual closes (ISO day, value) the gate passed, oldest first: none when it failed,
    # and never the close carried forward. Read beside the stage, never published here.
    closes: tuple[tuple[str, float], ...] = ()
    persistence_required: int | None = None
    # Kept outside assessment/history rows: the immutable set owns the chart once.
    display: dict[str, object] | None = None


# What a correction recomputed: the whole day, or its cores and formal stage only, when
# the context details the day would show have left retention (ticket 08).
WHOLE_DAY = "whole_day"
CORE_ONLY = "core_only"
DETAILS_PAST_RETENTION = "details_past_retention"
# A day without a stage of its own whose last confirmed stage the stage history before it no
# longer gives, an earlier day having been summarized since: that stage alone is corrected
# (follow-up ticket 01).
STAGE_HISTORY_CHANGED = "stage_history_changed"
LAST_CONFIRMED_ONLY = "last_confirmed_stage"


@dataclass(frozen=True)
class SummaryCorrection:
    """The summary a day's new one corrects, and why; the corrected one stays (ticket 07)."""

    assessment_id: str
    projection_set_id: str | None
    reason: str
    scope: str = WHOLE_DAY
    # The correction the corrected summary stated, kept by one that corrects its last
    # confirmed stage alone and so carries the rest of it (follow-up ticket 01).
    carries: Mapping[str, object] | None = None

    def document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "assessment_id": self.assessment_id,
            "projection_set_id": self.projection_set_id,
            "reason": self.reason,
            "scope": self.scope,
        }
        if self.carries is not None:
            document["carries"] = dict(self.carries)
        return document


def context_not_recomputed() -> tuple[dict[str, object], dict[str, object]]:
    """The macro and inventory documents of a day corrected on its cores only: shown as not
    recomputed, with no evidence and no confirmation (ticket 08)."""
    marker = {"context_status": "not_recomputed", "not_recomputed_reason": DETAILS_PAST_RETENTION}
    return (
        {**_default_macro_document(), **marker},
        {**_default_inventory_document(), **marker},
    )


@dataclass(frozen=True)
class P0PublishResult:
    status: str
    projection_set_id: str | None
    current_stage: FormalStage | None
    last_confirmed_stage: FormalStage | None
    stage_reason: str
    gaps: tuple[str, ...]
    assessment_id: str | None = None


class P0ProjectionService:
    def __init__(self, projections: ProjectionSetRepository) -> None:
        self._projections = projections

    def publish(
        self,
        *,
        target_business_date: str,
        system_as_of: datetime,
        assets: tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness],
        last_confirmed_stage: FormalStage | None,
        lookback: StageLookback | None = None,
        model_version_id: str = "model-v0001",
        warnings: tuple[str, ...] = (),
        evidence_snapshot_id: str | None = None,
        macro_document: dict[str, object] | None = None,
        inventory_document: dict[str, object] | None = None,
        release_calendar_events: tuple[dict[str, object], ...] = (),
        gap_list: tuple[dict[str, object], ...] = (),
        freshness_calendar: Mapping[str, str] | None = None,
        as_current: bool = True,
        decided: StageResult | None = None,
        core_history_basis: str | None = None,
        corrects: SummaryCorrection | None = None,
        macro_judgement: Mapping[str, object] | None = None,
        macro_rules: MacroJudgementRules | None = None,
    ) -> P0PublishResult:
        """Publish the day's set; ``decided`` is its formal stage when already decided.

        The confirmation built before read that same stage (``formal_stage``); without
        one, it is decided here. A ``lookback`` (ADR-0040) is published with the overview and
        the stage history, and the stage it found stands as the last confirmed one there; the
        day's assessment keeps what the window's history says. The assessment states the
        ``core_history_basis`` the cores were read on, and the summary it ``corrects``. A
        ``freshness_calendar`` says the gap list's freshness stood on weekdays (ticket 06).
        A ``macro_judgement`` (ADR-0043), judged before publishing under the model's
        ``macro_rules``, goes with the overview, its conclusion verified by the cores
        published here.
        """
        gaps = _core_gaps(assets)
        decided = decided or formal_stage(assets)
        # The cores' stage is the last confirmed one; without one, the one before stands.
        stage = replace(
            decided, last_confirmed_stage=decided.last_confirmed_stage or last_confirmed_stage
        )
        lookback_document = lookback.document() if lookback is not None else None
        shown_stage = stated_last_confirmed(decided, last_confirmed_stage, lookback)
        resolved_macro_document = macro_document or _default_macro_document()
        resolved_inventory_document = inventory_document or _default_inventory_document()
        asset_documents = [_asset_document(item) for item in assets]
        display = {item.asset: item.display for item in assets if item.display is not None}
        history = [
            item
            for item in self._projections.stage_history(through=target_business_date)
            if item.get("business_date") != target_business_date
        ]
        model_inputs = (
            sorted(
                {
                    version_id
                    for item in assets
                    for version_id in (item.model_input_observation_version_ids or ())
                }
            )
            if all(item.model_input_observation_version_ids is not None for item in assets)
            else None
        )
        resolved_snapshot_id = evidence_snapshot_id or (
            "snapshot-"
            + hashlib.sha256(json.dumps(asset_documents, sort_keys=True).encode()).hexdigest()[:20]
        )
        if gaps:
            warnings = (*warnings, "core_data_pending")
        carried = [item.asset for item in assets if item.carried_forward]
        if carried:
            warnings = (*warnings, *(f"core_carried_forward:{asset}" for asset in carried))
        identity_document: dict[str, object] = {
            "assets": asset_documents,
            "current_stage": stage.current_stage.value if stage.current_stage else None,
            "last_confirmed_stage": shown_stage.value if shown_stage else None,
            "model_version_id": model_version_id,
            "evidence_snapshot_id": resolved_snapshot_id,
            "stage_reason": stage.reason,
            "system_as_of": system_as_of.isoformat(),
            "target_business_date": target_business_date,
            "warnings": list(warnings),
            "macro": resolved_macro_document,
            "inventory": resolved_inventory_document,
            "release_calendar_events": list(release_calendar_events),
            "gap_list": list(gap_list),
        }
        noncanonical_basis = (
            build_basis(asset_documents, shown_stage.value if shown_stage else None)
            if stage.reason == "noncanonical_combination"
            else None
        )
        if noncanonical_basis is not None:
            identity_document["noncanonical_basis"] = noncanonical_basis
        if macro_judgement is not None:
            # The cores the set publishes verify the judgement's conclusion (ticket 06).
            macro_judgement = verified(
                macro_judgement,
                price_stage=stage.current_stage.value if stage.current_stage else None,
                reason=stage.reason,
                combination=combination_of(asset_documents),
                comparisons=(noncanonical_basis or {}).get("comparisons") or (),
            )
        if display:
            identity_document["core_display"] = display
            identity_document["prior_stage_history"] = [
                item.get("assessment_id") for item in history
            ]
        if model_inputs is not None:
            identity_document["core_model_input_observation_version_ids"] = model_inputs
        if lookback_document is not None:
            identity_document["last_confirmed_lookback"] = lookback_document
        if core_history_basis is not None:
            identity_document["core_history_basis"] = core_history_basis
        if freshness_calendar is not None:
            identity_document["freshness_calendar"] = dict(freshness_calendar)
        if macro_judgement is not None:
            identity_document["macro_judgement"] = dict(macro_judgement)
        if corrects is not None:
            # A correction is a set of its own, even computed as the one it corrects was.
            identity_document["corrects"] = corrects.document()
        if (batch_id := current_batch_id()) is not None:
            # A re-run of the same day is a new batch with its own summaries (ADR-0022).
            identity_document["batch_id"] = batch_id
        projection_set_id = (
            "projection-"
            + hashlib.sha256(json.dumps(identity_document, sort_keys=True).encode()).hexdigest()[
                :20
            ]
        )
        envelope = ProjectionEnvelope(
            projection_set_id=projection_set_id,
            system_as_of=system_as_of,
            target_business_date=target_business_date,
            evidence_snapshot_id=resolved_snapshot_id,
            model_version_id=model_version_id,
            trend_rule_version="trend-v0001",
            evidence_window_start=min(
                (
                    item.evidence_window_start
                    for item in assets
                    if item.evidence_window_start is not None
                ),
                default=(datetime.fromisoformat(target_business_date) - timedelta(days=180))
                .date()
                .isoformat(),
            ),
            evidence_window_end=target_business_date,
            generated_at=system_as_of,
            completeness="degraded" if warnings else "complete",
            refresh_status="completed",
            warnings=warnings,
        )
        assessment = self._projections.prepare_p0_assessment(
            _assessment_document(
                target_business_date=target_business_date,
                system_as_of=system_as_of,
                evidence_snapshot_id=resolved_snapshot_id,
                model_version_id=model_version_id,
                assets=asset_documents,
                current_stage=stage.current_stage,
                last_confirmed_stage=stage.last_confirmed_stage,
                stage_reason=stage.reason,
                gaps=gaps,
                projection_set_id=projection_set_id,
                core_history_basis=core_history_basis,
                corrects=corrects,
                macro_judgement=macro_judgement,
            )
        )
        datasets: dict[str, dict[str, object]] = {
            name: {"projection_set_id": projection_set_id} for name in ANALYTICAL_DATASETS
        }
        datasets["cycle_overview"].update(
            {
                "current_stage": stage.current_stage.value if stage.current_stage else None,
                "last_confirmed_stage": shown_stage.value if shown_stage else None,
                "stage_reason": stage.reason,
                "core_assets": asset_documents,
                "transition_watch": [],
                "macro_confirmation": _macro_confirmation(resolved_macro_document),
                "gap_list": list(gap_list),
                # Timeliness is judged at the cutoff, also for an earlier target (lookback 27).
                "gap_list_assessed_at": system_as_of.isoformat(),
                "core_carry_forward": carried,
            }
        )
        if noncanonical_basis is not None:
            datasets["cycle_overview"]["noncanonical_basis"] = noncanonical_basis
        if macro_judgement is not None:
            # Only a model with the macro judgement rules publishes one (ADR-0043).
            datasets["cycle_overview"]["macro_judgement"] = dict(macro_judgement)
        if freshness_calendar is not None:
            # Only when weekdays stood in for the calendar; a set without it states none.
            datasets["cycle_overview"]["freshness_calendar"] = dict(freshness_calendar)
        if lookback_document is not None:
            datasets["cycle_overview"]["last_confirmed_lookback"] = lookback_document
            datasets["stage_history"]["last_confirmed_lookback"] = lookback_document
        datasets["core_assets"]["assets"] = asset_documents
        if display:
            datasets["core_assets"]["display"] = display
        if model_inputs is not None:
            datasets["core_assets"]["model_input_observation_version_ids"] = model_inputs
        datasets["macro"].update(resolved_macro_document)
        datasets["inventory"].update(resolved_inventory_document)
        datasets["release_calendar"]["events"] = list(release_calendar_events)
        # A set is the record as of its day: no later day's event, even one summarized
        # before this day was (ticket 14). The day's own is this summary, which supersedes it.
        history.append(assessment)
        datasets["stage_history"]["events"] = history
        if display:
            datasets["stage_history"]["display"] = history_display(
                history,
                display_days(next(iter(display.values()))),
            )
        validate_analytical_projection(envelope, datasets, macro_rules=macro_rules)
        try:
            current = self._projections.current()
        except LookupError:
            current = None
        if current is not None and current.envelope.projection_set_id == projection_set_id:
            return P0PublishResult(
                "published",
                projection_set_id,
                stage.current_stage,
                shown_stage,
                stage.reason,
                (),
                str(assessment["assessment_id"]),
            )
        self._projections.publish(
            envelope, datasets, p0_assessment=assessment, as_current=as_current
        )
        return P0PublishResult(
            "published",
            projection_set_id,
            stage.current_stage,
            shown_stage,
            stage.reason,
            (),
            str(assessment["assessment_id"]),
        )

    def relink(
        self,
        held: Mapping[str, object],
        *,
        last_confirmed_stage: str | None,
        system_as_of: datetime,
        counted_from: Earlier | None,
        macro_rules: MacroJudgementRules | None = None,
    ) -> str:
        """Append a version of ``held``, its day's latest summary, that corrects the day's
        last confirmed stage alone (follow-up ticket 01); the new assessment's id.

        Its cores, context, confirmation and evidence are the summary's word for word, and
        nothing is read again; the summary and its set stay. Its set's overview and stage
        history state the stage, and a lookback the set showed in its place goes once the
        history gives one. Its macro judgement's hysteresis counts on from ``counted_from``, as
        the day summary reads it now, under the model's ``macro_rules``.
        """
        day = str(held["business_date"])
        kept = self._projections.get(str(held["projection_set_id"]))
        # A relinked summary carries what it carried itself, so the chain stays one deep.
        earlier = held.get("corrects")
        if isinstance(earlier, dict) and earlier.get("reason") == STAGE_HISTORY_CHANGED:
            earlier = earlier.get("carries")
        corrects = SummaryCorrection(
            str(held["assessment_id"]),
            kept.envelope.projection_set_id,
            STAGE_HISTORY_CHANGED,
            scope=LAST_CONFIRMED_ONLY,
            carries=earlier if isinstance(earlier, dict) else None,
        )
        history = [
            item
            for item in self._projections.stage_history(through=day)
            if item.get("business_date") != day
        ]
        identity_document = {
            "corrects": corrects.document(),
            "last_confirmed_stage": last_confirmed_stage,
            "stage_history": [item.get("assessment_id") for item in history],
            "system_as_of": system_as_of.isoformat(),
            "batch_id": current_batch_id(),
        }
        projection_set_id = (
            "projection-"
            + hashlib.sha256(json.dumps(identity_document, sort_keys=True).encode()).hexdigest()[
                :20
            ]
        )
        datasets = {
            name: {**document, "projection_set_id": projection_set_id}
            for name, document in kept.datasets.items()
        }
        overview = datasets["cycle_overview"]
        if last_confirmed_stage is not None or "last_confirmed_lookback" not in overview:
            overview["last_confirmed_stage"] = last_confirmed_stage
            if isinstance(basis := overview.get("noncanonical_basis"), dict):
                overview["noncanonical_basis"] = {
                    **basis,
                    "last_confirmed_stage": last_confirmed_stage,
                }
            overview.pop("last_confirmed_lookback", None)
            datasets["stage_history"].pop("last_confirmed_lookback", None)
            if isinstance(judgement := overview.get("macro_judgement"), dict):
                # Its conclusion is stated against that stage, its hysteresis counted on
                # from ``counted_from`` again, and its signals and price verification against
                # the conclusion; nothing is judged again.
                if macro_rules is None:
                    raise ValueError("macro_judgement_rules_missing")
                judgement = with_reference(
                    judgement,
                    last_confirmed_stage,
                    earlier=counted_from,
                    rules=macro_rules,
                    day=day,
                )
                if isinstance(confirmation := datasets["macro"].get("confirmation"), dict):
                    # Its divergences' recounts take their ties against that stage too.
                    reference = FormalStage(last_confirmed_stage) if last_confirmed_stage else None
                    cores = _cores_read(overview)
                    judgement = rejudged(
                        judgement,
                        macro_rules,
                        confirmation,
                        lambda rules, twin: judge(rules, twin, reference=reference, cores=cores),
                    )
                overview["macro_judgement"] = restated(regrouped(judgement))
        judgement = overview.get("macro_judgement")
        assessment = self._projections.prepare_p0_assessment(
            {
                **{key: value for key, value in held.items() if key != "assessment_id"},
                "corrects": corrects.document(),
                "last_confirmed_stage": last_confirmed_stage,
                "projection_set_id": projection_set_id,
                "system_as_of": system_as_of.isoformat(),
                # The stage history records the conclusion as restated (ticket 08).
                **(
                    {"macro_conclusion": record_macro(judgement)}
                    if isinstance(judgement, dict)
                    else {}
                ),
            }
        )
        datasets["stage_history"]["events"] = [*history, assessment]
        if isinstance(shown := datasets["stage_history"].get("display"), dict):
            datasets["stage_history"]["display"] = history_display(
                [*history, assessment],
                [str(point["date"]) for point in shown["days"]],
            )
        envelope = replace(
            kept.envelope,
            projection_set_id=projection_set_id,
            system_as_of=system_as_of,
            generated_at=system_as_of,
        )
        validate_analytical_projection(envelope, datasets, macro_rules=macro_rules)
        self._projections.publish(envelope, datasets, p0_assessment=assessment, as_current=False)
        return str(assessment["assessment_id"])


def _cores_read(overview: Mapping[str, object]) -> dict[str, str] | None:
    """The set's three core states when its combination was read, typical or not; None
    when a core was unavailable or pending -- what the day's weak judgement fell back on."""
    if overview.get("stage_reason") not in {"canonical_combination", "noncanonical_combination"}:
        return None
    assets = overview.get("core_assets")
    return {
        str(item["asset"]): str(item["state"])
        for item in (assets if isinstance(assets, list) else [])
        if isinstance(item, dict)
    }


def stated_last_confirmed(
    decided: StageResult,
    last_confirmed_stage: FormalStage | None,
    lookback: StageLookback | None = None,
) -> FormalStage | None:
    """The last confirmed stage a day's set states: the cores' own when typical, else the one
    the history before the day gives, else the one a lookback found (ADR-0040)."""
    return (
        decided.last_confirmed_stage
        or last_confirmed_stage
        or (lookback.stage if lookback is not None and lookback.status == FOUND else None)
    )


def formal_stage(
    assets: tuple[CoreAssetReadiness, CoreAssetReadiness, CoreAssetReadiness],
) -> StageResult:
    """The day's formal stage, from its three cores alone, decided once for the day.

    The confirmation of the stage's narrative reads it, and publishing states it. Its
    last confirmed stage is the cores' own canonical one, held or not, else none: the
    history before the day is publishing's to add.
    """
    by_asset = {item.asset: item for item in assets}
    if set(by_asset) != {"bond", "stock", "commodity"}:
        raise ValueError("p0_asset_manifest_invalid")
    stage = derive_formal_stage(
        bond=by_asset["bond"].state,
        stock=by_asset["stock"].state,
        commodity=by_asset["commodity"].state,
        last_confirmed_stage=None,
    )
    if _core_gaps(assets):
        # Core data pending: no formal stage, but everything else is still published
        # and reported (ticket 07, item 3).
        stage = replace(stage, current_stage=None, reason="core_data_pending")
    return stage


def _core_gaps(assets: tuple[CoreAssetReadiness, ...]) -> tuple[str, ...]:
    return tuple(
        f"{item.asset}:{item.reason}"
        for item in assets
        if item.state is None or item.reason not in {"validated", CARRIED_FORWARD}
    )


def _macro_confirmation(document: dict[str, object] | None) -> list[dict[str, str]]:
    if document is None:
        return []
    confirmations = []
    for key in ("policy_direction", "credit_response", "overheat_state", "price_pressure"):
        state = document.get(key)
        if state not in {None, "insufficient_data"}:
            confirmations.append({"context": key, "state": str(state)})
    return confirmations


def _default_macro_document() -> dict[str, object]:
    return {
        "policy_direction": "insufficient_data",
        "policy_action": {"direction": "insufficient_data", "evidence": []},
        "transmission": {"direction": "insufficient_data", "evidence": []},
        "credit_response": "insufficient_data",
        "credit": {"state": "insufficient_data", "evidence": []},
        "overheat_state": "insufficient_data",
        "overheat": {
            "state": "insufficient_data",
            "support": [],
            "counterevidence": [],
            "gaps": [],
        },
        "price_pressure": "insufficient_data",
        "price_chain": {
            "state": "insufficient_data",
            "support": [],
            "counterevidence": [],
            "gaps": [],
        },
        "international_context": [],
        "score": None,
    }


def _default_inventory_document() -> dict[str, object]:
    return {
        "quadrant": None,
        "directions": {"demand": None, "production": None, "inventory": None},
        "cards": [
            {"name": name, "status": "missing", "evidence_ids": [], "evidence": []}
            for name in INVENTORY_CARD_NAMES
        ],
        "real_inventory_approximation": {
            "formula_version": "inventory-ppi-v0001",
            "status": "missing_inputs",
            "value": None,
        },
        "score": None,
    }


def _asset_document(item: CoreAssetReadiness) -> dict[str, object]:
    document: dict[str, object] = {
        "asset": item.asset,
        "carried_forward": item.carried_forward,
        "candidate_30d": (item.candidate_30d.value if item.candidate_30d is not None else None),
        "candidate_days": item.candidate_days,
        "persistence_required": item.persistence_required,
        "candidate_state": (
            item.candidate_state.value if item.candidate_state is not None else None
        ),
        "distance_pct": item.distance_pct,
        "evidence_window_start": item.evidence_window_start,
        "latest_business_date": item.latest_business_date,
        "metric_id": item.metric_id,
        "noise_band_pct": item.noise_band_pct,
        "observation_count": item.observation_count,
        "observation_version_ids": list(item.observation_version_ids),
        "reason": item.reason,
        "slope_pct": item.slope_pct,
        "state": item.state.value if item.state else None,
    }
    if item.proxy_12m_enabled:
        document["proxy_12m"] = item.proxy_12m.value if item.proxy_12m is not None else None
    return document


def _assessment_document(
    *,
    target_business_date: str,
    system_as_of: datetime,
    evidence_snapshot_id: str,
    model_version_id: str,
    assets: list[dict[str, object]],
    current_stage: FormalStage | None,
    last_confirmed_stage: FormalStage | None,
    stage_reason: str,
    gaps: tuple[str, ...],
    projection_set_id: str | None,
    core_history_basis: str | None = None,
    corrects: SummaryCorrection | None = None,
    macro_judgement: Mapping[str, object] | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "business_date": target_business_date,
        "candidate_events": [
            {
                "asset": item["asset"],
                "candidate_30d": item["candidate_30d"],
                "candidate_days": item["candidate_days"],
                "candidate_state": item["candidate_state"],
                **({"proxy_12m": item["proxy_12m"]} if "proxy_12m" in item else {}),
            }
            for item in assets
        ],
        "core_assets": assets,
        "current_stage": current_stage.value if current_stage else None,
        "event_kind": "formal" if current_stage is not None else "gap",
        "evidence_snapshot_id": evidence_snapshot_id,
        "gaps": list(gaps),
        "last_confirmed_stage": (last_confirmed_stage.value if last_confirmed_stage else None),
        "model_version_id": model_version_id,
        "projection_set_id": projection_set_id,
        "stage_reason": stage_reason,
        "system_as_of": system_as_of.isoformat(),
        "trend_rule_version": "trend-v0001",
    }
    if core_history_basis is not None:
        document["core_history_basis"] = core_history_basis
    if corrects is not None:
        document["corrects"] = corrects.document()
    if macro_judgement is not None:
        document["macro_conclusion"] = record_macro(macro_judgement)
    return document
