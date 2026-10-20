from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from itertools import takewhile
from pathlib import Path
from typing import Any, Protocol

from pring_cycle.artifacts import store_artifact
from pring_cycle.batches import add_batch_columns, current_batch_id
from pring_cycle.cli_process import run_structured_cli
from pring_cycle.confirmation import OUTPUT_STRUCTURE as CONFIRMATION_STRUCTURE
from pring_cycle.freshness import CALENDAR_FALLBACK_NOTE, freshness_statement
from pring_cycle.noncanonical import PROMPT_VERSION as NONCANONICAL_PROMPT_VERSION
from pring_cycle.noncanonical import TITLE as NONCANONICAL_TITLE
from pring_cycle.noncanonical import (
    fact_sentences,
    fallback_section,
    observation_sentences,
    reading_error,
)
from pring_cycle.projections import ProjectionSet
from pring_cycle.storage import database_connection, ensure_wal
from pring_cycle.wording import STAGE_TITLES, display_name, source_name, stage_name

REPORT_SCHEMA_VERSION = "report-schema-v0004"
# Prose names codes by their Chinese display names since v0008 (decision 5).
PROMPT_CONTRACT_VERSION = "report-prompt-v0008"
# A projection's dimension summary (ADR-0037) is reported under its own contract: its
# relations and counts are conclusions the AI must echo, as the labels before them were.
CONFIRMATION_REPORT_SCHEMA_VERSION = "report-schema-v0005"
CONFIRMATION_PROMPT_CONTRACT_VERSION = "report-prompt-v0009"
# A projection's macro judgement (ADR-0043) leads its report under its own contract: its
# stage and confidence are conclusions the AI must echo, and the prose explains the five
# dimensions, then the turn signals, then the price verification (macro stage ticket 09).
MACRO_REPORT_SCHEMA_VERSION = "report-schema-v0006"
MACRO_PROMPT_CONTRACT_VERSION = "report-prompt-v0011"


@dataclass(frozen=True)
class ReportInput:
    """The verified results an AI report may explain (ADR-0027).

    Each result carries only its value, the name of its data source and whether it is
    anomalous (carried forward, gap, lagging, conflict). No evidence rows, observation
    series or evidence identifiers: tracing is the projection's and the batch's job.
    ``conclusions`` is what the AI must echo unchanged; ``gap_list`` is kept for the
    report reader and is not sent to the AI, which sees the gap summary instead.
    ``display_names`` gives the Chinese name of each stage, metric and source code the
    input carries, for the prose; the codes themselves stay for validation (decision 5).
    It is stored in the ``evidence_bundle`` table under ``bundle_id``, as before.
    """

    bundle_id: str
    projection_set_id: str
    target_business_date: str
    report_cutoff: datetime
    system_as_of: datetime
    model_version_id: str
    trend_rule_version: str
    current_stage: str | None
    stage_reason: str
    core_states: dict[str, str]
    conclusions: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    gap_list: list[Any] = field(default_factory=list)
    display_names: dict[str, dict[str, str]] = field(default_factory=dict)
    schema_version: str = REPORT_SCHEMA_VERSION
    prompt_version: str = PROMPT_CONTRACT_VERSION

    @classmethod
    def create(
        cls,
        *,
        projection_set_id: str,
        target_business_date: str,
        report_cutoff: datetime,
        system_as_of: datetime,
        model_version_id: str,
        trend_rule_version: str,
        current_stage: str | None,
        stage_reason: str,
        core_states: dict[str, str],
        conclusions: dict[str, Any] | None = None,
        results: dict[str, Any] | None = None,
        gap_list: list[Any] | None = None,
    ) -> ReportInput:
        conclusions = _without_evidence_identifiers(conclusions or {})
        results = _without_evidence_identifiers(results or {})
        schema_version, prompt_version = _contract(conclusions, results)
        display_names = _display_names(current_stage, conclusions, results)
        identity = {
            "projection_set_id": projection_set_id,
            "target_business_date": target_business_date,
            "report_cutoff": report_cutoff.isoformat(),
            "system_as_of": system_as_of.isoformat(),
            "model_version_id": model_version_id,
            "trend_rule_version": trend_rule_version,
            "current_stage": current_stage,
            "stage_reason": stage_reason,
            "core_states": core_states,
            "conclusions": conclusions,
            "results": results,
            "gap_list": gap_list or [],
            "display_names": display_names,
            "schema_version": schema_version,
            "prompt_version": prompt_version,
        }
        return cls(
            bundle_id="bundle-" + _hash_document(identity)[:20],
            projection_set_id=projection_set_id,
            target_business_date=target_business_date,
            report_cutoff=report_cutoff,
            system_as_of=system_as_of,
            model_version_id=model_version_id,
            trend_rule_version=trend_rule_version,
            current_stage=current_stage,
            stage_reason=stage_reason,
            core_states=core_states,
            conclusions=conclusions,
            results=results,
            gap_list=gap_list or [],
            display_names=display_names,
            schema_version=schema_version,
            prompt_version=prompt_version,
        )

    def document(self) -> dict[str, Any]:
        document = asdict(self)
        document["report_cutoff"] = self.report_cutoff.isoformat()
        document["system_as_of"] = self.system_as_of.isoformat()
        return document

    def prompt_document(self) -> dict[str, Any]:
        """What the AI is given: everything but the reader's full gap list."""
        document = self.document()
        del document["gap_list"]
        return document

    def deterministic_skeleton(self) -> dict[str, Any]:
        body = {
            "report_identity": {
                "bundle_id": self.bundle_id,
                "projection_set_id": self.projection_set_id,
                "target_business_date": self.target_business_date,
                "report_cutoff": self.report_cutoff.isoformat(),
                "model_version_id": self.model_version_id,
                "trend_rule_version": self.trend_rule_version,
            },
            "formal_stage_basis": {
                "current_stage": self.current_stage,
                "stage_reason": self.stage_reason,
                "classification_source": "three_core_price_states_only",
            },
            "core_states": dict(self.core_states),
            "conclusions": dict(self.conclusions),
            "verified_results": dict(self.results),
            "gap_list": list(self.gap_list),
            # The gap list's timeliness is the cutoff's, also for an earlier target day.
            "freshness_basis": {
                "target_business_date": self.target_business_date,
                "assessed_at": self.report_cutoff.isoformat(),
                "statement": freshness_statement(self.target_business_date, self.report_cutoff),
                # Weekdays stood in for the calendar: said with the note (ticket 06).
                **(
                    {
                        "calendar": {
                            **self.results["freshness_calendar"],
                            "note": CALENDAR_FALLBACK_NOTE,
                        }
                    }
                    if isinstance(self.results.get("freshness_calendar"), dict)
                    else {}
                ),
            },
            "core_carry_forward": list(self.results.get("core_carry_forward", [])),
        }
        basis = self.results.get("noncanonical_basis")
        if isinstance(macro := self.results.get("macro_judgement"), dict):
            body["ai_explanation"] = macro_sections(macro)
            body["explanation_source"] = "deterministic_template"
        elif self.stage_reason == "noncanonical_combination" and isinstance(basis, dict):
            body["ai_explanation"] = [fallback_section(basis)]
            body["explanation_source"] = "deterministic_template"
        return body


# Which macro and inventory conclusions the report states, and the projection sections
# whose rows feed each one (for its source names and anomalies).
_MACRO_CONCLUSIONS = {
    "policy_direction": ("policy_action", "transmission"),
    "credit_response": ("credit",),
    "overheat_state": ("overheat",),
    "price_pressure": ("price_chain",),
}
_CORE_SOURCE_LABEL = "三核心价格状态"


def report_input_from_projection(projection: ProjectionSet) -> ReportInput:
    envelope = projection.envelope
    overview = projection.datasets["cycle_overview"]
    current_stage = overview.get("current_stage")
    stage_reason = overview.get("stage_reason")
    if current_stage is None and stage_reason not in {
        "noncanonical_combination",
        "core_data_pending",
    }:
        raise ValueError("formal_stage_required_for_report")
    if current_stage is not None and not isinstance(current_stage, str):
        raise ValueError("formal_stage_required_for_report")
    if not isinstance(stage_reason, str):
        raise ValueError("stage_reason_required_for_report")
    assets_value = projection.datasets["core_assets"].get("assets")
    if not isinstance(assets_value, list):
        raise ValueError("core_asset_projection_required_for_report")
    for item in assets_value:
        if not isinstance(item, dict):
            raise ValueError("core_asset_projection_required_for_report")
        observation_count = item.get("observation_count")
        observation_ids = item.get("observation_version_ids")
        exact_120_required = envelope.model_version_id.startswith(("model-v0010-", "model-v0011-"))
        if (
            not isinstance(observation_count, int)
            or (observation_count != 120 if exact_120_required else observation_count > 120)
            or not isinstance(observation_ids, list)
            or (len(observation_ids) != 120 if exact_120_required else len(observation_ids) > 120)
            or (
                exact_120_required
                and item.get("evidence_window_start") != envelope.evidence_window_start
            )
        ):
            raise ValueError(
                "report_evidence_window_must_equal_120_days"
                if exact_120_required
                else "report_evidence_window_exceeds_120_days"
            )
    core_states = {
        str(item["asset"]): str(item["state"])
        for item in assets_value
        if isinstance(item, dict) and "asset" in item and "state" in item
    }
    if set(core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("core_asset_projection_required_for_report")
    macro = projection.datasets["macro"]
    inventory = projection.datasets["inventory"]
    history = projection.datasets["stage_history"].get("events")
    latest_history = (
        next(
            (
                item
                for item in reversed(history)
                if isinstance(item, dict)
                and item.get("projection_set_id") == envelope.projection_set_id
            ),
            None,
        )
        if isinstance(history, list)
        else None
    )
    carried = [str(asset) for asset in _list(overview.get("core_carry_forward"))]
    gap_list = [item for item in _list(overview.get("gap_list")) if isinstance(item, dict)]
    confirmation = macro.get("confirmation")
    if macro.get("output_structure") == CONFIRMATION_STRUCTURE and isinstance(confirmation, dict):
        conclusions, outputs = _confirmation_conclusions(confirmation, macro)
        outputs["confirmation"]["inventory"] = _inventory_notes(inventory)
        outputs["confirmation"].update(_price_notes(macro))
    else:
        conclusions = {name: _text_or_none(macro.get(name)) for name in _MACRO_CONCLUSIONS}
        conclusions["inventory_quadrant"] = _text_or_none(inventory.get("quadrant"))
        outputs = {
            **{
                name: _conclusion_result(
                    conclusions[name],
                    [row for section in sections for row in _section_rows(macro.get(section))],
                )
                for name, sections in _MACRO_CONCLUSIONS.items()
            },
            "inventory_quadrant": _conclusion_result(
                conclusions["inventory_quadrant"],
                [
                    row
                    for card in _list(inventory.get("cards"))
                    if isinstance(card, dict)
                    for row in _section_rows(card)
                ],
            ),
        }
    results: dict[str, Any] = {
        "formal_stage": {
            "value": current_stage,
            "reason": stage_reason,
            "last_confirmed_stage": overview.get("last_confirmed_stage"),
            "change": latest_history.get("event_kind") if latest_history else None,
            "source": _CORE_SOURCE_LABEL,
            "anomaly": [f"carried_forward:{asset}" for asset in carried],
            # Looked back for before the window, said so with its reach (ADR-0040).
            **(
                {"last_confirmed_lookback": overview["last_confirmed_lookback"]}
                if isinstance(overview.get("last_confirmed_lookback"), dict)
                else {}
            ),
        },
        "core_assets": [_core_result(item, carried) for item in assets_value],
        **outputs,
        "core_carry_forward": carried,
        "gap_summary": _gap_summary(gap_list),
        # The gap list's freshness stood on weekdays its calendar did not cover (ticket 06).
        **(
            {"freshness_calendar": dict(calendar_basis)}
            if isinstance(calendar_basis := overview.get("freshness_calendar"), dict)
            else {}
        ),
    }
    block = overview.get("macro_judgement")
    if isinstance(block, dict):
        # A noncanonical day is read as the prices off the judgement: its one-asset
        # comparisons travel with the price verification, not as the old reading's basis.
        conclusions = {**conclusions, **_macro_conclusions(block)}
        results["macro_judgement"] = _macro_results(block)
    elif stage_reason == "noncanonical_combination" and isinstance(
        overview.get("noncanonical_basis"), dict
    ):
        results["noncanonical_basis"] = overview["noncanonical_basis"]
    return ReportInput.create(
        projection_set_id=envelope.projection_set_id,
        target_business_date=envelope.target_business_date,
        report_cutoff=envelope.system_as_of,
        system_as_of=envelope.system_as_of,
        model_version_id=envelope.model_version_id,
        trend_rule_version=envelope.trend_rule_version,
        current_stage=current_stage,
        stage_reason=stage_reason,
        core_states=core_states,
        conclusions=conclusions,
        results=results,
        gap_list=gap_list,
    )


_CONFIRMATION_SECTIONS = ("policy_action", "transmission", "credit", "overheat", "price_chain")
_READING_FIELDS = (
    "period",
    "value",
    "level",
    "momentum",
    "direction",
    "agrees_by",
    "slope",
    "run",
    "crossed",
    "position",
    "change_size",
    "consistency",
    "stand_ins",
    # Year-to-date figures; a change read as its source states it (ticket 07).
    "cumulative",
    "change_from",
    "changes",
    # A policy member's actions in the evidence window; a daily member's periods.
    "action",
    "actions",
    "baseline",
    "window_start",
    "period_sessions",
    "aggregate",
    "lines",
    # The inventory quadrant, and the line each of its members reads (ticket 08).
    "quadrant",
    "unclassified_by",
    "line",
)


def _confirmation_conclusions(
    confirmation: dict[str, Any], macro: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The dimension summary as conclusions to echo, and each key indicator's reading.

    Conclusions are flat, one per dimension and key indicator: whether confirmation
    applies, each dimension's counts (or that it is not connected), each indicator's
    relation. The readings say what each relation rests on, with no evidence identifiers.
    """
    rows = [row for section in _CONFIRMATION_SECTIONS for row in _section_rows(macro.get(section))]
    conclusions: dict[str, Any] = {"confirmation_applicable": confirmation.get("applicable")}
    readings: dict[str, Any] = {}
    for dimension in _list(confirmation.get("dimensions")):
        name = str(dimension.get("dimension"))
        counts = dimension.get("counts")
        conclusions[f"dimension:{name}"] = (
            dict(counts) if isinstance(counts, dict) else str(dimension.get("status"))
        )
        for indicator in _list(dimension.get("key_indicators")):
            key = str(indicator.get("key"))
            conclusions[f"key_indicator:{key}"] = indicator.get("relation")
            sourced = _conclusion_result(
                indicator.get("relation"),
                [row for row in rows if row.get("metric_id") == indicator.get("metric_id")],
            )
            readings[key] = {
                **{
                    field: indicator.get(field)
                    for field in (
                        "name",
                        "dimension",
                        "timing",
                        "statistical_period",
                        "relation",
                        "proposition",
                        "consistency",
                        "notes",
                        "turn_hint",
                        "turn",
                        "grace",
                        "divergence_capped",
                        "capped_by",
                        "missing",
                    )
                },
                "members": [
                    {
                        "role": member.get("role"),
                        "label": member.get("label"),
                        "formula_version": member.get("formula_version"),
                        "member": member.get("member"),
                        **{field: member.get(field) for field in _READING_FIELDS},
                    }
                    for member in _list(indicator.get("members"))
                    if isinstance(member, dict)
                ],
                # Shown beside the indicator, never counted.
                "derived": [
                    {
                        field: item.get(field)
                        for field in ("label", "formula_version", "period", "value", "momentum")
                    }
                    for item in _list(indicator.get("derived"))
                    if isinstance(item, dict)
                ],
                "source": sourced["source"],
                "anomaly": sourced["anomaly"],
            }
    return conclusions, {
        "confirmation": {
            "applicable": confirmation.get("applicable"),
            "stage": confirmation.get("stage"),
            "stage_reason": confirmation.get("stage_reason"),
            "key_indicators": readings,
        }
    }


def _inventory_notes(inventory: dict[str, Any]) -> dict[str, Any]:
    """What the inventory dimension tells beside its quadrant, never counted: each card's
    data apart from the quadrant's relation, the registered warrants' change and the real
    inventory approximation as the rough proxy it is; no evidence identifiers."""
    warrants = inventory.get("registered_warrants")
    proxy = inventory.get("real_inventory_approximation")
    return {
        "cards": [
            {
                field: card.get(field)
                for field in ("label", "line", "availability", "evidence_status", "relation")
            }
            for card in _list(inventory.get("cards"))
            if isinstance(card, dict)
        ],
        # Its evidence identifiers are left out with every other (ReportInput.create).
        "registered_warrants": dict(warrants) if isinstance(warrants, dict) else None,
        "real_inventory_approximation": (
            {
                field: proxy.get(field)
                for field in ("semantics", "counted", "quadrant_input", "status", "period", "value")
            }
            if isinstance(proxy, dict)
            else None
        ),
    }


def _price_notes(macro: dict[str, Any]) -> dict[str, Any]:
    """What is shown beside the dimension summary, never counted: the price internal
    consistency, the observation interfaces as read and the supply-demand note; no
    evidence identifiers (ticket 09). And what drives the bond's trend (ticket 10)."""
    interfaces = macro.get("observation_interfaces")
    return {
        "price_consistency": macro.get("price_consistency"),
        "observation_interfaces": (
            {
                "counted": interfaces.get("counted"),
                "cores": [
                    {
                        "core": core.get("core"),
                        "label": core.get("label"),
                        "members": [
                            {
                                "label": member.get("label"),
                                "reads_as": member.get("reads_as"),
                                "in_catalog": member.get("in_catalog"),
                                "readings": [
                                    {
                                        field: row.get(field)
                                        for field in (
                                            "dimensions",
                                            "period",
                                            "value",
                                            "unit",
                                            "direction",
                                            "status",
                                        )
                                    }
                                    for row in _list(member.get("evidence"))
                                    if isinstance(row, dict)
                                ],
                            }
                            for member in _list(core.get("members"))
                            if isinstance(member, dict)
                        ],
                    }
                    for core in _list(interfaces.get("cores"))
                    if isinstance(core, dict)
                ],
            }
            if isinstance(interfaces, dict)
            else None
        ),
        "supply_demand": macro.get("supply_demand"),
        "bond_attribution": macro.get("bond_attribution"),
    }


def _macro_conclusions(block: dict[str, Any]) -> dict[str, Any]:
    """The judgement's stage and confidence: the rules', for the AI to echo (ADR-0003)."""
    conclusion = block.get("conclusion")
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    return {
        "macro_stage": _text_or_none(conclusion.get("stage")),
        "macro_confidence": _text_or_none(conclusion.get("confidence")),
    }


_MACRO_PAIRS = ("stage", "confidence", "matched", "known")
# The report's order under the judgement (decision 12, spec story 36).
MACRO_SECTIONS = ("宏观判断与五维依据", "转折信号", "价格验证与偏离")


def _macro_results(block: dict[str, Any]) -> dict[str, Any]:
    """What the report says of the judgement, as the board words it: the title, how a
    tendency or a weak judgement took its stage, the five dimensions, the signals and the
    price verification. Only the fields the prose needs; no evidence identifiers."""
    # The board's wording, so the report says what the page says.
    from pring_cycle import macro_board

    conclusion = _mapping(block.get("conclusion"))
    raw = _mapping(block.get("raw"))
    taken = _mapping(raw.get("fallback"))
    hysteresis = block.get("hysteresis")
    verification = _mapping(block.get("price_verification"))
    return {
        "title": macro_board.title(conclusion, block),
        "held": _held(block),
        "fallback": macro_board.fallback(block),
        "raw_fallback": macro_board.raw_fallback(block),
        "conclusion": {
            **{
                field: conclusion.get(field)
                for field in (*_MACRO_PAIRS, "reference_stage", "steps", "direction")
            },
            # What a held conclusion was taken from (decision 24).
            "formed": (
                {
                    field: formed.get(field)
                    for field in ("on", "stage", "confidence", "basis", "tied", "reference_stage")
                }
                | {
                    "fallback": {
                        "candidates": _mapping(formed.get("fallback")).get("candidates") or []
                    }
                }
                if (formed := _mapping(conclusion.get("formed")))
                else None
            ),
        },
        "raw": {
            **{field: raw.get(field) for field in (*_MACRO_PAIRS, "basis", "tied", "threshold")},
            "fallback": (
                {
                    field: taken.get(field)
                    for field in ("source", "combination", "differences", "candidates")
                }
                if taken
                else None
            ),
        },
        # Scalars only: the counting state, never the judgements it was counted on.
        "hysteresis": (
            {key: value for key, value in hysteresis.items() if not isinstance(value, dict | list)}
            if isinstance(hysteresis, dict)
            else None
        ),
        "scores": dict(_mapping(block.get("scores"))),
        "dimensions": [
            {
                **{
                    field: item.get(field)
                    for field in ("dimension", "group", "value", "position", "matches")
                },
                "line": macro_board.dimension_line(item),
                "indicators": [
                    {
                        field: indicator.get(field)
                        for field in ("name", "voting", "vote", "divergent", "period")
                    }
                    for indicator in _list(item.get("indicators"))
                    if isinstance(indicator, dict)
                ],
            }
            for item in _list(block.get("dimensions"))
            if isinstance(item, dict)
        ],
        "signals": [
            {
                **{
                    field: item.get(field)
                    for field in ("id", "kind", "group", "transition", "maturity", "same_source")
                },
                # A divergence's recount judges a stage of its own (decision 47).
                "rejudged": (
                    {field: rejudged.get(field) for field in ("stage", "confidence", "tied")}
                    if isinstance(rejudged := item.get("rejudged"), dict)
                    else None
                ),
                "line": macro_board.describe(item),
            }
            for item in _list(block.get("signals"))
            if isinstance(item, dict)
        ],
        "price_verification": (
            {
                **{
                    field: verification.get(field)
                    for field in (
                        "price_stage",
                        "reason",
                        "combination",
                        "expected_stage",
                        "expected",
                        "deviations",
                        "verdict",
                    )
                },
                "comparisons": [
                    {
                        field: row.get(field)
                        for field in (
                            "stage",
                            "asset",
                            "current_state",
                            "required_state",
                            "candidate_30d",
                            "candidate_state",
                            "candidate_days",
                        )
                    }
                    for row in _list(verification.get("comparisons"))
                    if isinstance(row, dict)
                ],
                "line": macro_board.verification_line(block),
            }
            if verification
            else None
        ),
    }


def macro_sections(macro: dict[str, Any]) -> list[dict[str, str]]:
    """The template's reading under the judgement, in the report's order: why the five
    dimensions point to the stage and how sure it is, the turn signals, then the price
    verification read as the prices off the judgement. Each a single paragraph, saying only
    what the input's lines say."""
    from pring_cycle.wording import MACRO_ASSETS, MACRO_NO_SIGNALS, MACRO_SIGNAL_GROUPS

    judged = [
        str(macro.get("title")),
        *(str(macro[field]) for field in ("held", "fallback", "raw_fallback") if macro.get(field)),
        # A dimension a sentence: its own line joins its votes by semicolons.
        *(str(item.get("line")) for item in _list(macro.get("dimensions"))),
    ]
    signals = _list(macro.get("signals"))
    grouped = [
        f"{label}："
        + "；".join(str(item.get("line")) for item in signals if item.get("group") == group)
        for group, label in MACRO_SIGNAL_GROUPS.items()
        if any(item.get("group") == group for item in signals)
    ]
    verification = _mapping(macro.get("price_verification"))
    checked = [str(verification.get("line") or "该投影未提供价格验证")]
    if verification.get("verdict") == "consistent":
        checked.append("价格表象与宏观判断一致")
    elif verification.get("verdict") == "deviates":
        off = "、".join(
            MACRO_ASSETS.get(str(asset), str(asset)) for asset in verification["deviations"]
        )
        checked.append(
            f"价格偏离宏观判断：{off}与{stage_name(str(verification.get('expected_stage')))}预期相反"
        )
        if verification.get("reason") == "noncanonical_combination":
            near = "、".join(
                stage_name(str(row.get("stage")))
                for row in _list(verification.get("comparisons"))
                if isinstance(row, dict)
            )
            checked.append(
                "三核心为非典型组合，暂无价格阶段，宏观判断不因此改变"
                + (f"；价格组合与{near}各只差一项" if near else "")
            )
    return [
        {"title": title, "explanation": "。".join(sentences) + "。"}
        for title, sentences in zip(
            MACRO_SECTIONS, (judged, grouped or [MACRO_NO_SIGNALS], checked), strict=True
        )
    ]


def _held(block: dict[str, Any]) -> str | None:
    """滞回保持，当日原始判断：第三阶段（倾向） -- when the hysteresis keeps the conclusion
    from the day's raw judgement (decision 45); None otherwise."""
    from pring_cycle.wording import MACRO_CONFIDENCES

    conclusion, raw = _mapping(block.get("conclusion")), _mapping(block.get("raw"))
    if not isinstance(block.get("hysteresis"), dict) or all(
        raw.get(field) == conclusion.get(field) for field in ("stage", "confidence")
    ):
        return None
    confidence = MACRO_CONFIDENCES.get(str(raw.get("confidence")), "")
    judged = (
        f"{stage_name(str(raw['stage']))}（{confidence}）" if raw.get("stage") else "无可取阶段"
    )
    return f"滞回保持，当日原始判断：{judged}"


def _contract(
    conclusions: dict[str, Any], results: dict[str, Any] | None = None
) -> tuple[str, str]:
    """The schema and prompt contract a report's conclusions are written under."""
    if "macro_stage" in conclusions:
        return MACRO_REPORT_SCHEMA_VERSION, MACRO_PROMPT_CONTRACT_VERSION
    schema, prompt = (
        (CONFIRMATION_REPORT_SCHEMA_VERSION, CONFIRMATION_PROMPT_CONTRACT_VERSION)
        if "confirmation_applicable" in conclusions
        else (REPORT_SCHEMA_VERSION, PROMPT_CONTRACT_VERSION)
    )
    if results and isinstance(results.get("noncanonical_basis"), dict):
        prompt = NONCANONICAL_PROMPT_VERSION
    return schema, prompt


def _display_names(*values: Any) -> dict[str, dict[str, str]]:
    """The Chinese name of each stage, metric and source code among ``values``' strings;
    an anomaly (``gap:CN_X``) names its metric after the colon."""
    names: dict[str, dict[str, str]] = {"stages": {}, "metrics": {}, "sources": {}}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list | tuple):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            if value.lower() in STAGE_TITLES:
                names["stages"][value] = stage_name(value)
            for code in (value, value.partition(":")[2]):
                if (metric := display_name(code)).provided:
                    names["metrics"][code] = metric.name
            if source_name(value) != value and value not in names["metrics"]:
                names["sources"][value] = source_name(value)

    visit(values)
    return {kind: dict(sorted(codes.items())) for kind, codes in names.items()}


# What a fact rests on, not the fact: claim, observation and snapshot identifiers, at any
# depth, under any prefix (``first_claim_ids``, ``input_observation_version_ids``...).
_EVIDENCE_IDENTIFIER_SUFFIXES = (
    "claim_id",
    "claim_ids",
    "observation_id",
    "observation_ids",
    "observation_version_id",
    "observation_version_ids",
    "snapshot_id",
    "assessment_id",
    "attempt_id",
)


def _without_evidence_identifiers(value: Any) -> Any:
    """``value`` with every evidence identifier left out: tracing is the projection's and
    the batch's job, and hundreds of them only crowd the AI's input (go-live leftovers 02).
    Metric and stage codes stay, for the display names and the explanation checks."""
    if isinstance(value, dict):
        return {
            key: _without_evidence_identifiers(item)
            for key, item in value.items()
            if not str(key).endswith(_EVIDENCE_IDENTIFIER_SUFFIXES)
        }
    if isinstance(value, list | tuple):
        return [_without_evidence_identifiers(item) for item in value]
    return value


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _core_result(item: dict[str, Any], carried: list[str]) -> dict[str, Any]:
    from pring_cycle.freshness import FRESHNESS_REGISTRY

    metric_id = str(item.get("metric_id"))
    rule = FRESHNESS_REGISTRY.get(metric_id)
    return {
        "asset": item["asset"],
        "value": item["state"],
        "metric_id": metric_id,
        "latest_business_date": item.get("latest_business_date"),
        "candidate_state": item.get("candidate_state"),
        "candidate_30d": item.get("candidate_30d"),
        "candidate_days": item.get("candidate_days"),
        "source": rule.source if rule is not None else None,
        "anomaly": ["carried_forward"] if item["asset"] in carried else [],
    }


def _section_rows(section: object) -> list[dict[str, Any]]:
    rows = section.get("evidence") if isinstance(section, dict) else None
    return [row for row in rows or [] if isinstance(row, dict)]


def _conclusion_result(value: str | None, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """A conclusion's value, the sources its inputs came from and what is anomalous."""
    sources: set[str] = set()
    anomalies: list[str] = []
    for row in rows:
        metric_id = str(row.get("metric_id"))
        for claim in row.get("claims") or []:
            if isinstance(claim, dict) and claim.get("selected") and claim.get("provider"):
                sources.add(str(claim["provider"]))
        if row.get("formula_version") and row.get("status") in {"current", "available"}:
            sources.add("derived")
        status = row.get("status")
        if status == "missing":
            anomalies.append(f"gap:{metric_id}")
        elif status == "stale":
            anomalies.append(f"lagging:{metric_id}")
        elif status == "conflict":
            anomalies.append(f"conflict:{metric_id}")
    if value == "conflict":
        anomalies.append("conflict")
    return {
        "value": value,
        "source": sorted(sources),
        "anomaly": sorted(dict.fromkeys(anomalies)),
    }


def _gap_summary(gap_list: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for gap in gap_list:
        category = str(gap.get("category"))
        counts[category] = counts.get(category, 0) + 1
    return {
        "counts": dict(sorted(counts.items())),
        "p0_p1": [
            {
                "metric_id": gap.get("metric_id"),
                "priority": gap.get("priority"),
                "category": gap.get("category"),
            }
            for gap in gap_list
            if gap.get("priority") in {"P0", "P1"}
        ],
    }


@dataclass(frozen=True)
class AdapterResponse:
    status: str
    document: dict[str, Any] | None
    error_classification: str | None
    tool_events: int
    process_audit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def succeeded(cls, document: dict[str, Any], *, tool_events: int = 0) -> AdapterResponse:
        return cls("succeeded", document, None, tool_events)

    @classmethod
    def unavailable(cls, classification: str) -> AdapterResponse:
        return cls("unavailable", None, classification, 0)


class ReportAdapter(Protocol):
    name: str
    version: str

    def generate(self, bundle: ReportInput) -> AdapterResponse: ...


@dataclass(frozen=True)
class ReportGenerationResult:
    report_snapshot_id: str
    status: str
    adapter: str
    version: int


@dataclass(frozen=True)
class ReportSnapshot:
    report_snapshot_id: str
    projection_set_id: str
    target_business_date: str
    version: int
    status: str
    adapter: str
    current_stage: str | None
    bundle_id: str
    bundle_hash: str
    model_version_id: str
    schema_version: str
    prompt_version: str
    report_cutoff: datetime
    system_as_of: datetime
    created_at: datetime
    duration_ms: int
    body_retained: bool
    body: dict[str, Any]
    explanation_verification: dict[str, Any] = field(default_factory=dict)
    input_schema_version: str = "not_recorded"
    input_prompt_version: str = "not_recorded"
    # Read with it: whether its projection was computed on a value read for the wrong
    # period, and the reports that correct it or that it corrects (audit 06).
    corrections: dict[str, Any] = field(default_factory=dict)
    # Each recorded adapter attempt as (adapter, outcome), in order: why a template stood in.
    adapter_outcomes: tuple[tuple[str, str], ...] = ()
    # Beside each outcome, the check that refused its reading, None where the attempt was
    # not refused or its audit predates the rejection record (macro stage ticket 16).
    adapter_rejections: tuple[str | None, ...] = ()


@dataclass(frozen=True)
class ReportAttempt:
    adapter: str
    adapter_version: str
    outcome: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    tool_events: int
    output_hash: str | None
    process_audit: dict[str, Any] = field(default_factory=dict)


class ReportRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ReportRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_REPORT_SCHEMA)
            connection.executescript(_REPORT_ARTIFACT_SCHEMA)
            upgrade_report_snapshot_nullable_stage(connection)
            upgrade_report_process_audit(connection)
            add_batch_columns(connection)
        return repository

    def by_client_request(self, client_request_id: str) -> ReportSnapshot | None:
        with self._connect() as connection:
            row = connection.execute(
                _REPORT_SNAPSHOT_SELECT + " WHERE report_snapshot.client_request_id=?",
                (client_request_id,),
            ).fetchone()
        return self._with_runtime_metadata(_report_snapshot(row)) if row is not None else None

    def next_version(self, target_business_date: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 FROM report_snapshot
                WHERE target_business_date=?
                """,
                (target_business_date,),
            ).fetchone()
        return int(row[0]) if row is not None else 1

    def save_bundle(self, bundle: ReportInput) -> str:
        from pring_cycle.source_contract_review import require_stored_model_source_contract

        document_json = _canonical_json(bundle.document())
        bundle_hash = hashlib.sha256(document_json.encode()).hexdigest()
        with self._connect() as connection:
            require_stored_model_source_contract(connection, bundle.model_version_id)
            connection.execute(
                """
                INSERT OR IGNORE INTO evidence_bundle(
                    bundle_id, bundle_hash, projection_set_id, document_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.bundle_id,
                    bundle_hash,
                    bundle.projection_set_id,
                    document_json,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return bundle_hash

    def save_output(self, bundle: ReportInput, document: Any) -> str:
        """Keep CLI output as audit material, owned by its retained input bundle."""
        artifact = store_artifact(
            self._database_path,
            self._database_path.parent / "artifacts" / "sha256",
            _canonical_json(document).encode(),
            "application/json",
            f"report-output:{bundle.bundle_id}",
        )
        return artifact.content_hash

    def record_attempt(
        self,
        report_snapshot_id: str,
        *,
        adapter: str,
        adapter_version: str,
        outcome: str,
        started_at: datetime,
        completed_at: datetime,
        tool_events: int,
        output_hash: str | None,
        process_audit: dict[str, Any] | None = None,
        elapsed_ms: int | None = None,
        report_elapsed_ms: int | None = None,
    ) -> None:
        if started_at.tzinfo is None or completed_at.tzinfo is None:
            raise ValueError("report_attempt_times_must_be_timezone_aware")
        audit = dict(process_audit or {})
        # Provider metadata cannot replace the report service's measured timing.
        audit.pop("timing", None)
        if elapsed_ms is not None:
            if (
                type(elapsed_ms) is not int
                or elapsed_ms < 0
                or type(report_elapsed_ms) is not int
                or report_elapsed_ms < elapsed_ms
            ):
                raise ValueError("report_attempt_elapsed_time_invalid")
            audit["timing"] = {
                "basis": "monotonic",
                "elapsed_ms": elapsed_ms,
                "report_elapsed_ms": report_elapsed_ms,
                "clock_went_backwards": completed_at < started_at,
            }
        elif report_elapsed_ms is not None:
            raise ValueError("report_attempt_elapsed_time_invalid")
        elif completed_at < started_at:
            raise ValueError("report_attempt_time_order_invalid")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO report_attempt(
                    report_snapshot_id, adapter, adapter_version, started_at,
                    completed_at, outcome, tool_events, output_hash, process_audit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_snapshot_id,
                    adapter,
                    adapter_version,
                    started_at.astimezone(UTC).isoformat(),
                    completed_at.astimezone(UTC).isoformat(),
                    outcome,
                    tool_events,
                    output_hash,
                    _canonical_json(audit),
                ),
            )

    def save_snapshot(
        self,
        *,
        report_snapshot_id: str,
        client_request_id: str,
        bundle: ReportInput,
        bundle_hash: str,
        version: int,
        status: str,
        adapter: str,
        body: dict[str, Any],
    ) -> ReportSnapshot:
        from pring_cycle.source_contract_review import require_stored_model_source_contract

        body_json = _canonical_json(body)
        with self._connect() as connection:
            require_stored_model_source_contract(connection, bundle.model_version_id)
            connection.execute(
                """
                INSERT INTO report_snapshot(
                    report_snapshot_id, client_request_id, projection_set_id,
                    target_business_date, version, status, adapter, current_stage,
                    bundle_id, bundle_hash, model_version_id, schema_version,
                    prompt_version, body_json, body_retained, created_at, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    report_snapshot_id,
                    client_request_id,
                    bundle.projection_set_id,
                    bundle.target_business_date,
                    version,
                    status,
                    adapter,
                    bundle.current_stage,
                    bundle.bundle_id,
                    bundle_hash,
                    bundle.model_version_id,
                    *_contract(bundle.conclusions, bundle.results),
                    body_json,
                    datetime.now(UTC).isoformat(),
                    current_batch_id(),
                ),
            )
        return self.get(report_snapshot_id)

    def get(self, report_snapshot_id: str) -> ReportSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                _REPORT_SNAPSHOT_SELECT + " WHERE report_snapshot.report_snapshot_id=?",
                (report_snapshot_id,),
            ).fetchone()
        if row is None:
            raise LookupError("report_snapshot_not_found")
        return self._with_runtime_metadata(_report_snapshot(row))

    def history(self) -> tuple[ReportSnapshot, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                _REPORT_SNAPSHOT_SELECT
                + """
                ORDER BY target_business_date DESC, version DESC
                """
            ).fetchall()
        return tuple(self._with_runtime_metadata(_report_snapshot(row)) for row in rows)

    def attempts(self, report_snapshot_id: str) -> tuple[ReportAttempt, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM report_attempt WHERE report_snapshot_id=?
                ORDER BY attempt_id
                """,
                (report_snapshot_id,),
            ).fetchall()
        return tuple(_report_attempt(row) for row in rows)

    def attempts_for_bundle(self, bundle_id: str) -> tuple[ReportAttempt, ...]:
        with self._connect() as connection:
            if "process_audit_json" not in {
                str(row[1]) for row in connection.execute("PRAGMA table_info(report_attempt)")
            }:
                return ()
            rows = connection.execute(
                "SELECT * FROM report_attempt "
                "WHERE json_extract(process_audit_json, '$.bundle_id')=? "
                "ORDER BY attempt_id",
                (bundle_id,),
            ).fetchall()
        return tuple(_report_attempt(row) for row in rows)

    def record_explanation_review(
        self,
        report_snapshot_id: str,
        *,
        output_hash: str,
        reviewer: str,
        sections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from pring_cycle.report_review import record_explanation_review

        with self._connect() as connection:
            return record_explanation_review(
                connection,
                report_snapshot_id,
                output_hash=output_hash,
                reviewer=reviewer,
                sections=sections,
            )

    def explanation_reviews(self, report_snapshot_id: str) -> tuple[dict[str, Any], ...]:
        from pring_cycle.report_review import explanation_reviews

        with self._connect() as connection:
            return explanation_reviews(connection, report_snapshot_id)

    def _with_runtime_metadata(self, snapshot: ReportSnapshot) -> ReportSnapshot:
        from pring_cycle.publication_corrections import report_corrections

        reviews = self.explanation_reviews(snapshot.report_snapshot_id)
        with self._connect() as connection:
            corrections = report_corrections(connection, snapshot.projection_set_id)
        attempts = self.attempts(snapshot.report_snapshot_id)
        measured_duration = (
            _timing_duration(attempts[-1].process_audit, "report_elapsed_ms") if attempts else None
        )
        status = (
            reviews[-1]
            if reviews
            else snapshot.body.get(
                "explanation_verification",
                {
                    "status": "not_recorded"
                    if snapshot.adapter != "deterministic"
                    else "unavailable",
                    "semantic_support": "not_reviewed",
                },
            )
        )
        return replace(
            snapshot,
            explanation_verification=status,
            duration_ms=(
                measured_duration if measured_duration is not None else snapshot.duration_ms
            ),
            corrections=corrections,
            adapter_outcomes=tuple((item.adapter, item.outcome) for item in attempts),
            adapter_rejections=tuple(_rejection_check(item.process_audit) for item in attempts),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with database_connection(self._database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            ensure_wal(connection, self._database_path)
            yield connection


class ReportService:
    def __init__(self, repository: ReportRepository, adapters: tuple[ReportAdapter, ...]) -> None:
        self._repository = repository
        self._adapters = adapters

    def generate(
        self,
        bundle: ReportInput,
        *,
        client_request_id: str | None = None,
        cancelled: bool = False,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> ReportGenerationResult:
        _preflight_bundle(bundle)
        if cancelled or (cancel_requested is not None and cancel_requested()):
            raise ValueError("report_generation_cancelled")
        request_id = client_request_id or f"automatic-{time.time_ns()}"
        existing = self._repository.by_client_request(request_id)
        if existing is not None:
            return ReportGenerationResult(
                existing.report_snapshot_id,
                existing.status,
                existing.adapter,
                existing.version,
            )
        version = self._repository.next_version(bundle.target_business_date)
        report_snapshot_id = (
            "report-" + hashlib.sha256(f"{bundle.bundle_id}:{request_id}".encode()).hexdigest()[:20]
        )
        bundle_hash = self._repository.save_bundle(bundle)
        report_started_ns = time.monotonic_ns()
        for adapter in self._adapters:
            if cancel_requested is not None and cancel_requested():
                raise ValueError("report_generation_cancelled")
            started_at = datetime.now(UTC)
            attempt_started_ns = time.monotonic_ns()
            response = adapter.generate(bundle)
            completed_at = datetime.now(UTC)
            completed_ns = time.monotonic_ns()
            cancelled_after = response.error_classification == "cancelled" or (
                cancel_requested is not None and cancel_requested()
            )
            outcome = response.error_classification or response.status
            output_hash = (
                _hash_document(response.document) if response.document is not None else None
            )
            output_retention: dict[str, Any] = {}
            if response.document is not None:
                try:
                    self._repository.save_output(bundle, response.document)
                    output_retention = {"status": "retained"}
                except (OSError, sqlite3.Error, ValueError) as error:
                    # Audit storage must not suppress the CLI fallback or cancellation.
                    output_retention = {"status": "failed", "error_type": type(error).__name__}
            rejection: dict[str, Any] = {}
            if response.status == "succeeded" and response.document is not None:
                outcome = _validate_ai_document(bundle, response, rejection=rejection)
            if cancelled_after:
                outcome = "cancelled"
            self._repository.record_attempt(
                report_snapshot_id,
                adapter=adapter.name,
                adapter_version=adapter.version,
                outcome=outcome,
                started_at=started_at,
                completed_at=completed_at,
                tool_events=response.tool_events,
                output_hash=output_hash,
                process_audit={
                    **{k: v for k, v in response.process_audit.items() if k != "rejection"},
                    "bundle_id": bundle.bundle_id,
                    **({"output_retention": output_retention} if output_retention else {}),
                    **({"rejection": rejection} if rejection else {}),
                },
                elapsed_ms=(completed_ns - attempt_started_ns) // 1_000_000,
                report_elapsed_ms=(completed_ns - report_started_ns) // 1_000_000,
            )
            if cancelled_after:
                raise ValueError("report_generation_cancelled")
            if outcome == "succeeded" and response.document is not None:
                body = bundle.deterministic_skeleton()
                body["ai_explanation"] = response.document["sections"]
                body["explanation_source"] = "ai"
                body["explanation_verification"] = {
                    "status": "pending_evidence_review",
                    "identity_and_conclusions": "passed",
                    "semantic_support": "not_reviewed",
                    "output_hash": output_hash,
                }
                # Raw codes left in the prose are marked, never a failure (decision 5).
                if codes := _untranslated_codes(bundle, response.document["sections"]):
                    body["untranslated_codes"] = codes
                snapshot = self._repository.save_snapshot(
                    report_snapshot_id=report_snapshot_id,
                    client_request_id=request_id,
                    bundle=bundle,
                    bundle_hash=bundle_hash,
                    version=version,
                    status="completed",
                    adapter=adapter.name,
                    body=body,
                )
                return ReportGenerationResult(
                    snapshot.report_snapshot_id,
                    snapshot.status,
                    snapshot.adapter,
                    snapshot.version,
                )
        snapshot = self._repository.save_snapshot(
            report_snapshot_id=report_snapshot_id,
            client_request_id=request_id,
            bundle=bundle,
            bundle_hash=bundle_hash,
            version=version,
            status="completed_degraded",
            adapter="deterministic",
            body=bundle.deterministic_skeleton(),
        )
        return ReportGenerationResult(
            snapshot.report_snapshot_id,
            snapshot.status,
            snapshot.adapter,
            snapshot.version,
        )


class CliReportAdapter:
    def __init__(
        self,
        name: str,
        *,
        timeout_seconds: int = 300,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        if name not in {"codex_cli", "claude_code_cli"}:
            raise ValueError("unsupported_cli_report_adapter")
        self.name = name
        self.version = "runtime-detected"
        self._timeout_seconds = timeout_seconds
        self._cancel_requested = cancel_requested

    def generate(self, bundle: ReportInput) -> AdapterResponse:
        schema_version, prompt_version = _contract(bundle.conclusions, bundle.results)
        confirmation = (
            "确认度的各维度计数与各关键指标的确认关系同样只能解释、不得改写；"
            "正文提及时须与 conclusions 一致（如“PMI 记为支持”“过热维度支持 1、反证 0”），"
            "未确认须说明缺什么，不得把仅观察或未确认说成支持。"
            if "confirmation_applicable" in bundle.conclusions
            else ""
        )
        macro_contract = (
            {
                "sections_in_order": list(MACRO_SECTIONS),
                "instruction": (
                    "宏观判断阶段与把握程度由确定性规则算出（conclusions.macro_stage、"
                    "macro_confidence），AI 只解释、不得改写，也不另作判定。"
                    "按 sections_in_order 的顺序写：先解释五维为何指向该阶段、把握程度为何是明确、"
                    "倾向或弱；把握程度为倾向或弱时正文须如实写出“倾向”或“弱”，并写明并列的阶段与"
                    "得分，或缺了哪些维度、为何退回价格组合推断，不得写成明确或已确定的结论；"
                    "滞回保持时写明主结论保持原阶段与把握程度及当日原始判断。"
                    "再写信号清单中的转折信号及其支持的阶段转换与成熟度，同源价格信号只提示转换、"
                    "不参与投票。最后写价格验证：价格阶段或非典型组合，与宏观判断阶段预期的三资产"
                    "是否一致、哪项资产偏离；三核心为非典型组合时从“价格偏离宏观判断”的视角解读，"
                    "不推测价格阶段。写宏观判断用“宏观判断为第N阶段”，写价格阶段用“价格阶段为"
                    "第N阶段”，二者不得混同；“当前处于”只用于宏观判断阶段。"
                ),
            }
            if "macro_stage" in bundle.conclusions
            else None
        )
        basis = bundle.results.get("noncanonical_basis")
        reading_contract = (
            {
                "title": NONCANONICAL_TITLE,
                "required_fact_sentences": fact_sentences(basis),
                "observation_sentences": observation_sentences(basis),
                "instruction": (
                    "报告只含这个固定标题section，不得新增其他section。"
                    "宏观五维由确定性事实展示，不另写AI段。按给定顺序逐字保留全部事实句作为开头，"
                    "随后从给定观察句中选取至少一句，可选择次序，每句至多一次，不加其他文字。"
                    "不要自行改写资产、候选、天数或阶段对照，其他section不复述这些对照。"
                    "30日候选方向没有持续天数，资产候选状态另列。禁止最接近阶段、推测阶段、AI阶段，"
                    "禁止倾向/更像/可视为/实际处于某阶段，不预测下一阶段。"
                ),
            }
            if isinstance(basis, dict)
            else None
        )
        prompt = _canonical_json(
            {
                **({"noncanonical_reading_contract": reading_contract} if reading_contract else {}),
                **({"macro_reading_contract": macro_contract} if macro_contract else {}),
                "instruction": (
                    "仅解释报告输入中的已验证结果，输出共同报告 JSON；不得调用工具或给出交易建议。"
                    "正式阶段、三核心状态与宏观、库存结论只能解释、不得改写，"
                    "conclusions 须与报告输入的 conclusions 完全一致。"
                    + confirmation
                    + "涉及具体数值时写明数据来源；有异常（核心沿用、缺口、落后、冲突）时如实说明。"
                    "正文提及阶段、指标与数据来源时用 report_input.display_names 给出的中文名"
                    "（如“第三阶段”“中证全指”），"
                    "不写原始代号（如 stage_iii、tushare:index_daily）。"
                    "每个section的explanation必须是非空的单段文字，不含换行或段落分隔符；"
                    "多段解释须拆为多个section。"
                ),
                "report_input": bundle.prompt_document(),
                "execution_contract": {
                    "schema_version": schema_version,
                    "prompt_version": prompt_version,
                    "input_bundle_versions_are_historical": True,
                },
            }
        )
        schema = _report_output_schema(bundle)
        outcome = run_structured_cli(
            self.name,
            prompt,
            schema,
            timeout_seconds=self._timeout_seconds,
            cancel_requested=self._cancel_requested,
            audit={
                "schema_version": schema_version,
                "prompt_version": prompt_version,
                "input_schema_version": bundle.schema_version,
                "input_prompt_version": bundle.prompt_version,
                "bundle_id": bundle.bundle_id,
            },
        )
        self.version = outcome.version
        if outcome.document is None:
            return replace(
                AdapterResponse.unavailable(outcome.classification or "invalid_json_schema"),
                tool_events=int(outcome.audit.get("tool_events", 0)),
                process_audit=outcome.audit,
            )
        return replace(
            AdapterResponse.succeeded(outcome.document, tool_events=outcome.tool_events),
            process_audit=outcome.audit,
        )


def _report_output_schema(bundle: ReportInput) -> dict[str, Any]:
    section = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "explanation": {"type": "string", "minLength": 1, "pattern": r"^[^\r\n\u2028\u2029]+$"},
        },
        "required": ["title", "explanation"],
    }
    conclusions = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            name: (
                _const_schema(value)
                if _contract(bundle.conclusions, bundle.results)[0] != REPORT_SCHEMA_VERSION
                else {"type": ["string", "null"], "const": value}
            )
            for name, value in bundle.conclusions.items()
        },
        "required": list(bundle.conclusions),
    }
    core_states = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            asset: {"type": "string", "const": state} for asset, state in bundle.core_states.items()
        },
        "required": list(bundle.core_states),
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "bundle_id": {"type": "string", "const": bundle.bundle_id},
            "current_stage": {
                "type": ["string", "null"],
                "const": bundle.current_stage,
            },
            "report_cutoff": {
                "type": "string",
                "const": bundle.report_cutoff.isoformat(),
            },
            "core_states": core_states,
            "conclusions": conclusions,
            "sections": {"type": "array", "minItems": 1, "items": section},
            "proxy_used": {"type": "boolean", "const": False},
        },
        "required": list(_OUTPUT_FIELDS),
    }


def _const_schema(value: Any) -> dict[str, Any]:
    """A schema only ``value`` meets: counts are integers, not numbers or booleans."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {key: _const_schema(item) for key, item in value.items()},
            "required": list(value),
        }
    if value is None:
        return {"type": "null"}
    kind = (
        "boolean"
        if isinstance(value, bool)
        else "integer"
        if isinstance(value, int)
        else "number"
        if isinstance(value, float)
        else "string"
    )
    return {"type": kind, "const": value}


def _same(left: Any, right: Any) -> bool:
    """Equal, and of the same kinds all the way down: a count of 1 is not True."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(map(_same, left, right))
    return bool(left == right)


_OUTPUT_FIELDS = (
    "bundle_id",
    "current_stage",
    "report_cutoff",
    "core_states",
    "conclusions",
    "sections",
    "proxy_used",
)


def _preflight_bundle(bundle: ReportInput) -> None:
    formal_stages = {
        "stage_i",
        "stage_ii",
        "stage_iii",
        "stage_iv",
        "stage_v",
        "stage_vi",
    }
    noncanonical = (
        bundle.current_stage is None
        and bundle.stage_reason == "noncanonical_combination"
        and (
            bundle.core_states.get("bond"),
            bundle.core_states.get("stock"),
            bundle.core_states.get("commodity"),
        )
        in {("bull", "bear", "bull"), ("bear", "bull", "bear")}
    )
    # A held stage (core data pending) still gets its report of the other outputs.
    core_pending = bundle.current_stage is None and bundle.stage_reason == "core_data_pending"
    if bundle.current_stage not in formal_stages and not noncanonical and not core_pending:
        raise ValueError("report_preflight_stage_invalid")
    if set(bundle.core_states) != {"bond", "stock", "commodity"}:
        raise ValueError("report_preflight_core_identity_invalid")
    if bundle.report_cutoff.tzinfo is None or bundle.system_as_of.tzinfo is None:
        raise ValueError("report_preflight_cutoff_invalid")
    if bundle.system_as_of > bundle.report_cutoff:
        raise ValueError("report_preflight_cutoff_mismatch")


_ROMAN_STAGES = {"I": "stage_i", "II": "stage_ii", "III": "stage_iii"}
_ROMAN_STAGES |= {"IV": "stage_iv", "V": "stage_v", "VI": "stage_vi"}
# Prose names a stage by its Chinese name since the report prompt v0008 (decision 5).
_ROMAN_STAGES |= dict(zip("一二三四五六", _ROMAN_STAGES.values(), strict=True))
# "当前阶段为阶段II", "目前处于 Stage IV", "当前处于第三阶段": a paragraph stating the current
# formal stage.
_STATED_STAGE = re.compile(
    r"(?:当前|目前|现在)(?:正式)?(?:阶段(?:为|是)|处于)\s*(?:正式)?"
    r"(?:(?:阶段|Stage\s*)?(VI|IV|V|III|II|I)(?![A-Za-z])|第([一二三四五六])阶段)"
)


def _stated_stages(section: dict[str, Any]) -> set[str]:
    """The formal stages a paragraph says the market is in now."""
    text = f"{section['title']}。{section['explanation']}"
    return {_ROMAN_STAGES[roman or chinese] for roman, chinese in _STATED_STAGE.findall(text)}


_CONFIDENCE_WORDS = {"明确": "explicit", "倾向": "tendency", "弱": "weak"}
_STAGE_CODES = ("stage_i", "stage_ii", "stage_iii", "stage_iv", "stage_v", "stage_vi")
# A stage's number as the prose may write it: 五, 5, ５, Ⅴ or V.
_NUMBERS = {
    **{numeral: index for index, numeral in enumerate("一二三四五六", 1)},
    **{numeral: index for index, numeral in enumerate("123456", 1)},
    **{numeral: index for index, numeral in enumerate("１２３４５６", 1)},
    **{numeral: index for index, numeral in enumerate("ⅠⅡⅢⅣⅤⅥ", 1)},
    **{numeral: index for index, numeral in enumerate(("I", "II", "III", "IV", "V", "VI"), 1)},
}
_NUMBER = r"(?:VI|IV|V|III|II|I|[ⅠⅡⅢⅣⅤⅥ一二三四五六1-6１-６])"
# A stage however the prose names it: 第三阶段, 第5阶段, 第Ⅴ阶段, 阶段 III, 阶段Ⅴ, Stage 5,
# V 阶段, and 第三 before →、至 another ("第三→第四阶段"). "阶段 3 维", "阶段一致" are none.
_MENTION = re.compile(
    rf"第\s*(?P<a>{_NUMBER})\s*阶段"
    rf"|第\s*(?P<b>{_NUMBER})(?=\s*(?:→|->|～|~|至|到|、|和|与|或|及)\s*第)"
    rf"|(?:阶段|[Ss]tage)\s*(?P<c>{_NUMBER})"
    r"(?![A-Za-z0-9０-９]|\s*[维个日项步年月致样直般些起旦度])"
    rf"|(?<![A-Za-z])(?P<d>VI|IV|V|III|II|I|[ⅠⅡⅢⅣⅤⅥ])\s*阶段"
)
# What a stage is said of, by the nearest word before it in its sentence; a stage said of
# nothing is said of the judgement: under it, the stage the market is in now is the judged
# one. A dimension's name says what a confidence word is of, never a stage.
_SUBJECTS = tuple(
    (subject, re.compile(words))
    for subject, words in (
        ("raw", r"原始判断|当日判断"),
        ("price", r"价格阶段|价格表象"),
        ("candidate", r"价格组合|三核心组合|只差一项|各差|候选|兜底|退回"),
        ("reference", r"上次确认|上一确认|此前确认"),
        ("tied", r"并列|介于"),
        ("expected", r"预期"),
        (
            "signal",
            r"信号|转换|转向|符合|→|分化|改投|少数方向|重判|翻转|转折|萌芽|成形"
            r"|支持(?:前进|后退|维持)",
        ),
        ("conclusion", r"宏观(?:判断|阶段|周期)?|主结论|把握程度|当前|目前|现在|当下"),
        ("dimension", r"政策|信用|增长|过热|物价|库存|维度"),
    )
)
# Said right after a stage, or a list of them: what it expects, what it is tied with, or
# its score.
_FOLLOWING = (
    ("expected", re.compile(r"\s*(?:的)?预期")),
    ("tied", re.compile(r"\s*并列")),
    (
        "score",
        re.compile(
            r"\s*(?:同为|均为|都是|各得|各|得分为|得分|得|为|[:：])?\s*(?P<score>\d+)\s*(?:分|维)"
        ),
    ),
)
_LISTED = re.compile(r"\s*[、和与及或/]\s*")
# "如果 PMI 改按少数方向计票，判断会变为第五阶段，把握程度为明确": under a condition the
# judgement and its confidence are a signal's recount, until the prose says what is now.
_CONDITION = re.compile(r"如果|假如|倘若|假设|一旦|若(?!干)")
_ACTUAL = re.compile(r"主结论|当前|目前|现在|当下|实际")
# "走弱", "转弱", "偏弱" say a move and "弱于" a comparison, not a weak judgement.
_CONFIDENCE = re.compile(r"明确|倾向|(?<![走转偏减削较变衰增])弱(?![于势化小])")
_LINK = r"\s*(?:为|是|处于|属于|在|于|指向|落在|进入|[:：])?\s*"
# A confidence word denied right before it: "不是明确", "不能解释为明确", "并非倾向".
_DENIED_CONFIDENCE = re.compile(
    r"(?:不是|并非|不算|不属于?|不能|不应|无法)(?:被)?(?:解释|视|看|读|理解|算|称)?(?:作|成|为)?\s*$"
)
_CONFIDENCE_TO_STAGE = re.compile(r"(?:判断|判定)?" + _LINK)
# A judgement short of explicit said to be settled.
_STATED_CERTAINTY = re.compile(r"(?<![不未非没])(?:已经?确定|确定无疑|毫无疑问|可以确定|确定结论)")


@dataclass(frozen=True)
class _Stated:
    """What a paragraph says of the judgement: the first check it fails, if any, and whether
    it tells the main conclusion's confidence."""

    failed: str | None
    confidence_told: bool


def _macro_statements(bundle: ReportInput, text: str) -> _Stated:
    """Each stage the prose names, read against what it is said of: the main conclusion,
    the day's raw judgement, the price stage, the last confirmed stage, what the judged
    stage expects, the stages tied, a signal's transition or recount, or the stages the
    cores' combination is one asset off; a confidence word bound to the stage or subject
    it is said of (ADR-0003, spec stories 37, 39)."""
    macro = _mapping(bundle.results.get("macro_judgement"))
    conclusion, raw = _mapping(macro.get("conclusion")), _mapping(macro.get("raw"))
    formed = _mapping(conclusion.get("formed"))
    verification = _mapping(macro.get("price_verification"))
    signals = [_mapping(item) for item in _list(macro.get("signals"))]
    rejudged = [_mapping(item.get("rejudged")) for item in signals if item.get("rejudged")]
    taken = [_mapping(raw.get("fallback")), _mapping(formed.get("fallback"))]
    allowed: dict[str, set[object]] = {
        "conclusion": {conclusion.get("stage")},
        "raw": {raw.get("stage")},
        "price": {bundle.current_stage},
        "reference": {conclusion.get("reference_stage"), formed.get("reference_stage")},
        "expected": {verification.get("expected_stage"), conclusion.get("stage")},
        "tied": {
            *_list(raw.get("tied")),
            *_list(formed.get("tied")),
            *(stage for item in rejudged for stage in _list(item.get("tied"))),
        },
        "signal": {
            *(
                _mapping(item.get("transition")).get(end)
                for item in signals
                for end in ("from", "to")
            ),
            *(item.get("stage") for item in rejudged),
            *(stage for item in rejudged for stage in _list(item.get("tied"))),
        },
        "candidate": {
            bundle.current_stage,
            *(stage for item in taken for stage in _list(item.get("candidates"))),
            *(_mapping(row).get("stage") for row in _list(verification.get("comparisons"))),
        },
    }
    pairs = {
        (item.get("stage"), item.get("confidence")) for item in (conclusion, raw, formed, *rejudged)
    }
    told = False
    for sentence in re.split(r"[。；;！!？?]", text):
        mentions = list(_MENTION.finditer(sentence))
        scopes = _conditions(sentence)
        markers = sorted(
            [
                (
                    match.start(),
                    "signal"
                    if subject == "conclusion" and _scope(scopes, match.start())
                    else subject,
                )
                for subject, pattern in _SUBJECTS
                for match in pattern.finditer(sentence)
            ]
            + [(start, "signal") for start, _end in scopes]
        )
        said: list[str] = []
        for index, mention in enumerate(mentions):
            stage = _mention_stage(mention)
            subject = _following(sentence, mentions, index) or next(
                (
                    subject
                    for at, subject in reversed(markers)
                    if at < mention.start() and subject != "dimension"
                ),
                "conclusion",
            )
            said.append(subject)
            if subject == "score":
                score = _following_score(sentence, mentions, index)
                if score != _mapping(macro.get("scores")).get(stage):
                    return _Stated("macro_stated_score", told)
            elif stage not in allowed[subject]:
                return _Stated(
                    "price_stated_stage" if subject == "price" else "macro_stated_stage", told
                )
        for word in _CONFIDENCE.finditer(sentence):
            confidence = _CONFIDENCE_WORDS[word.group()]
            bound = _bound(sentence, word, mentions, markers)
            if bound is None:
                continue
            of, subject = bound
            if of is None and (scope := _scope(scopes, word.start())) is not None:
                # "把握程度为明确" under a condition: of the stage the recount is said to be.
                of = next(
                    (
                        index
                        for index, mention in reversed(list(enumerate(mentions)))
                        if scope[0] <= mention.start() and mention.end() <= word.start()
                    ),
                    None,
                )
            if of is not None:
                subject = said[of]
                stage = _mention_stage(mentions[of])
            # "不是明确的结论" says the judgement is anything but explicit: it holds when the
            # judged confidence is another, and never tells the conclusion's.
            denied = _DENIED_CONFIDENCE.search(sentence, 0, word.start()) is not None
            if subject == "conclusion":
                if (confidence == conclusion.get("confidence")) == denied:
                    return _Stated("macro_stated_confidence", told)
                told = told or not denied
            elif subject == "raw":
                if (confidence == raw.get("confidence")) == denied:
                    return _Stated("macro_stated_confidence", told)
            elif of is not None and subject != "dimension":
                judged = (
                    {(item.get("stage"), item.get("confidence")) for item in rejudged}
                    if subject == "signal"
                    else pairs
                )
                if ((stage, confidence) in judged) == denied:
                    return _Stated("macro_stated_confidence", told)
    if conclusion.get("confidence") != "explicit" and _STATED_CERTAINTY.search(text):
        return _Stated("macro_stated_confidence", told)
    return _Stated(None, told)


def _conditions(sentence: str) -> list[tuple[int, int]]:
    """Where each condition in a sentence holds: from its word to what is now, else the end."""
    scopes = []
    for condition in _CONDITION.finditer(sentence):
        actual = _ACTUAL.search(sentence, condition.end())
        scopes.append((condition.start(), actual.start() if actual else len(sentence)))
    return scopes


def _scope(scopes: list[tuple[int, int]], at: int) -> tuple[int, int] | None:
    return next((scope for scope in scopes if scope[0] <= at < scope[1]), None)


def _mention_stage(mention: re.Match[str]) -> str:
    return _STAGE_CODES[_NUMBERS[next(group for group in mention.groups() if group)] - 1]


def _chain_end(sentence: str, mentions: list[re.Match[str]], index: int) -> int:
    """Where the list a stage leads ends: 第五阶段、第六阶段."""
    while index + 1 < len(mentions) and _LISTED.fullmatch(
        sentence[mentions[index].end() : mentions[index + 1].start()]
    ):
        index += 1
    return mentions[index].end()


def _following(sentence: str, mentions: list[re.Match[str]], index: int) -> str | None:
    rest = sentence[_chain_end(sentence, mentions, index) :]
    return next((subject for subject, pattern in _FOLLOWING if pattern.match(rest)), None)


def _following_score(sentence: str, mentions: list[re.Match[str]], index: int) -> int | None:
    found = _FOLLOWING[-1][1].match(sentence[_chain_end(sentence, mentions, index) :])
    return int(found.group("score")) if found else None


def _bound(
    sentence: str,
    word: re.Match[str],
    mentions: list[re.Match[str]],
    markers: list[tuple[int, str]],
) -> tuple[int | None, str] | None:
    """What a confidence word is said of: the stage it leads into ("倾向第三阶段"), else the
    nearest stage or subject before it in its sentence; None for neither."""
    link = _CONFIDENCE_TO_STAGE.match(sentence, word.end())
    after = link.end() if link else word.end()
    for index, mention in enumerate(mentions):
        if mention.start() == after:
            return index, ""
    before: list[tuple[int, int | None, str]] = [
        *((mention.end(), index, "") for index, mention in enumerate(mentions)),
        *((at, None, subject) for at, subject in markers),
    ]
    earlier = [item for item in before if item[0] <= word.start()]
    if not earlier:
        return None
    _at, of, subject = max(earlier, key=lambda item: item[0])
    return of, subject


_RELATION_WORDS = {
    "仅观察": "observation_only",
    "未确认": "unconfirmed",
    "不适用": "not_applicable",
    "反证": "counterevidence",
    "支持": "support",
}
_DIMENSION_WORDS = {"政策": "policy", "信用": "credit", "过热": "overheat", "物价": "price"}
_DIMENSION_WORDS |= {"库存": "inventory"}
_RELATION = "(" + "|".join(_RELATION_WORDS) + ")"
# "不", "没有被", "并非": a negation, taken in the match so what it negates is not read
# again without it.
# "没有任何一项记为支持": denied of each indicator the sentence names.
_NEGATION = r"(?:没有|并非|不是|[不非未没])\s*(?:任何一?项|一项)?\s*被?\s*"
# "PMI 记为反证", "PMI 是支持", "PMI：反证", "PMI 没有被判为支持", "PMI 并非支持": a key
# indicator's relation said in so many words.
_VERB = r"(?:记为|判为|计为|构成|属于|为|是|[:：])"
# A negation itself negated ("并非不支持") is no denial of what follows it.
_STATED_RELATION = re.compile(
    "(?:(?<![不非未没])(" + _NEGATION + ")" + _VERB + "?|" + _VERB + r")\s*" + _RELATION
)
# "过热维度支持 1、反证 0", "支持：1", "并非支持 1", "支持不是 1": a dimension's counts.
_STATED_COUNT = re.compile(
    "("
    + _NEGATION
    + ")?"
    + _RELATION
    + r"\s*[:：]?\s*(不是|并非|不为|非)?\s*(?:为|是|共|计)?\s*(\d+)"
)


def _restates_confirmation(bundle: ReportInput, section: dict[str, Any]) -> bool:
    """Whether a paragraph says a relation or a count other than the report input's.

    Read sentence by sentence, the title first: what follows a key indicator's name is
    said of it, and what follows a dimension's name is counted for it, up to the next
    indicator or dimension named, and on into sentences naming none. A relation denied is
    said too: denying the input's own is saying another.
    """
    if "confirmation_applicable" not in bundle.conclusions:
        return False
    confirmation = bundle.results.get("confirmation")
    readings = confirmation.get("key_indicators") if isinstance(confirmation, dict) else None
    names = {
        str(reading["name"]): f"key_indicator:{key}"
        for key, reading in (readings or {}).items()
        if isinstance(reading, dict) and reading.get("name")
    }
    dimensions = {label: f"dimension:{name}" for label, name in _DIMENSION_WORDS.items()}
    # The title runs into its paragraph: "PMI：" over "反证。" says PMI is counterevidence.
    text = f"{section['title']} {section['explanation']}"
    sentences = re.split(r"[。；;！!？?]", text)
    subjects = {**dict.fromkeys(names), **dict.fromkeys(dimensions)}
    for conclusion, segment in _attributed(sentences, {**subjects, **names}):
        for negated, word in _STATED_RELATION.findall(segment):
            if (_RELATION_WORDS[word] == bundle.conclusions.get(conclusion)) == bool(negated):
                return True
    for conclusion, segment in _attributed(sentences, {**subjects, **dimensions}):
        counts = bundle.conclusions.get(conclusion)
        for before, word, after, number in _STATED_COUNT.findall(segment):
            negated = bool(before or after)
            if not isinstance(counts, dict):
                if not negated:
                    return True
            elif (counts.get(_RELATION_WORDS[word]) == int(number)) == negated:
                return True
    return False


# "商品对债向上", "股票对债相对动量：走弱", "商品对债并非向下": a pair's move said.
_MOVE_WORDS = {
    **dict.fromkeys(("向上", "上升", "走强", "回升", "转强", "转升"), "up"),
    **dict.fromkeys(("向下", "下降", "走弱", "回落", "转弱"), "down"),
    "持平": "flat",
}
_STATED_MOVE = re.compile("(" + _NEGATION + ")?(" + "|".join(_MOVE_WORDS) + ")")
# What drives commodity prices, said as known: the data never tells it (ticket 09).
_STATED_DRIVER = re.compile(r"(?:需求|供给)(?:型|推动|驱动|主导)|推动力(?:已经?)?(?:确认|明确)")
_DENIAL = re.compile(r"不|未|无法|并非|没有")


def _restates_prices(bundle: ReportInput, section: dict[str, Any]) -> bool:
    """Whether a paragraph says a relative momentum's move other than the report input's,
    or a move of one unconfirmed, or names what drives commodity prices.

    A pair's move is read in the sentence naming it, the title running into the paragraph,
    up to the clause naming a key indicator or a dimension, and on into a sentence naming no
    pair that speaks of relative momentum. A driver named
    in a sentence denying nothing is said as known.
    """
    if "confirmation_applicable" not in bundle.conclusions:
        return False
    confirmation = bundle.results.get("confirmation")
    consistency = confirmation.get("price_consistency") if isinstance(confirmation, dict) else None
    pairs = {
        str(item["label"]): item.get("direction")
        for item in (consistency or {}).get("relative_momentum") or []
        if isinstance(item, dict) and item.get("label")
    }
    readings = confirmation.get("key_indicators") if isinstance(confirmation, dict) else None
    others = [
        *(str(item["name"]) for item in (readings or {}).values() if isinstance(item, dict)),
        *_DIMENSION_WORDS,
    ]
    text = f"{section['title']} {section['explanation']}"
    sentences = re.split(r"[。；;！!？?]", text)
    if any(_STATED_DRIVER.search(item) and not _DENIAL.search(item) for item in sentences):
        return True
    if not pairs:
        return False
    pattern = re.compile("|".join(re.escape(label) for label in sorted(pairs, key=len)[::-1]))
    current: str | None = None
    for sentence in sentences:
        found = list(pattern.finditer(sentence))
        ends = [*(item.start() for item in found[1:]), len(sentence)]
        stretches = [
            (mention.group(), sentence[mention.end() : end])
            for mention, end in zip(found, ends, strict=False)
        ]
        if not found and current is not None and "相对动量" in sentence:
            stretches = [(current, sentence)]
        for label, stretch in stretches:
            current = label
            # From a clause naming a key indicator or a dimension on, what is said is of it.
            first, *rest = re.split(r"[，,]", stretch)
            said_of = "".join(
                [first, *takewhile(lambda item: not any(name in item for name in others), rest)]
            )
            for negated, word in _STATED_MOVE.findall(said_of):
                said = _MOVE_WORDS[word]
                if pairs[label] is None:
                    if not negated:
                        return True
                elif (said == pairs[label]) == bool(negated):
                    return True
    return False


# "债券由基本面推动", "债券推动力并非不明": what drives the bond's trend, said of it. A
# negation before a driver, or in "推动力……不明", is taken in the match (ticket 10).
_BOND_DRIVERS = {
    "fundamentals_and_easing": r"基本面(?:加|与|和|及)宽松(?:共同)?(?:推动|驱动)",
    "fundamentals": r"基本面(?:推动|驱动)",
    "policy_liquidity": r"(?:政策或流动性|政策|流动性)(?:推动|驱动)",
    "unclear": r"推动力(?P<within>" + _NEGATION + ")?不明",
}
_STATED_BOND_DRIVER = re.compile(
    "("
    + _NEGATION
    + ")?(?:由于?|是|属于|为)?(?:"
    + "|".join(f"(?P<{k}>{v})" for k, v in _BOND_DRIVERS.items())
    + ")"
)
_BOND = re.compile(r"债券|债牛|债熊|债市|国债")
_OTHER_ASSETS = ("股票", "股市", "A 股", "A股", "商品")


def _restates_bond_attribution(bundle: ReportInput, section: dict[str, Any]) -> bool:
    """Whether a paragraph says the bond's trend has a driver other than the report
    input's, or denies its own.

    A driver is said of the subject named last before it -- the bond, another asset or a
    key indicator -- the title running into the paragraph; with none before it in its
    sentence, of the one its sentence before ended on.
    """
    if "confirmation_applicable" not in bundle.conclusions:
        return False
    confirmation = bundle.results.get("confirmation")
    note = confirmation.get("bond_attribution") if isinstance(confirmation, dict) else None
    if not isinstance(note, dict):
        return False
    readings = confirmation.get("key_indicators") if isinstance(confirmation, dict) else None
    others = [
        *(str(item["name"]) for item in (readings or {}).values() if isinstance(item, dict)),
        *_OTHER_ASSETS,
    ]
    other = re.compile("|".join(re.escape(name) for name in others))
    of_bond = False
    for sentence in re.split(r"[。；;！!？?]", f"{section['title']} {section['explanation']}"):
        # Where each subject is named: True for the bond.
        subjects = sorted(
            [(item.start(), True) for item in _BOND.finditer(sentence)]
            + [(item.start(), False) for item in other.finditer(sentence)]
        )
        for match in _STATED_BOND_DRIVER.finditer(sentence):
            before = [bond for start, bond in subjects if start < match.start()]
            if not (before[-1] if before else of_bond):
                continue
            driver = next(name for name in _BOND_DRIVERS if match.group(name))
            negated = bool(match.group(1) or match.group("within"))
            if (driver == note.get("driver")) == negated:
                return True
        if subjects:
            of_bond = subjects[-1][1]
    return False


def _attributed(sentences: list[str], labels: Mapping[str, str | None]) -> list[tuple[str, str]]:
    """Each stretch of ``sentences`` with the conclusion it is said of.

    A stretch runs from a label to the next; one before any label in its sentence is of
    the last label named before it. A label of no conclusion (another kind of subject)
    ends what the one before it is said of when it leads its sentence ("政策维度尚未接入"),
    not where it qualifies a subject already named ("PMI 在过热维度中").
    """
    # The longest first: "PMI 价格" is not "PMI" followed by "价格".
    ordered = sorted(labels, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(label) for label in ordered)) if labels else None
    stretches: list[tuple[str, str]] = []
    current: str | None = None
    for sentence in sentences:
        found = list(pattern.finditer(sentence)) if pattern is not None else []
        mentions = [
            mention
            for index, mention in enumerate(found)
            if labels[mention.group()] is not None
            or not any(labels[earlier.group()] is not None for earlier in found[:index])
        ]
        lead = sentence[: mentions[0].start()] if mentions else sentence
        if current is not None and lead:
            stretches.append((current, lead))
        for index, mention in enumerate(mentions):
            end = mentions[index + 1].start() if index + 1 < len(mentions) else len(sentence)
            current = labels[mention.group()]
            if current is not None:
                stretches.append((current, sentence[mention.end() : end]))
    return stretches


def _first_difference(actual: Any, expected: Any, path: str) -> str:
    if isinstance(actual, dict) and isinstance(expected, dict):
        for key in sorted(actual.keys() | expected.keys()):
            child = f"{path}.{key}"
            if key not in actual or key not in expected:
                return child
            if not _same(actual[key], expected[key]):
                return _first_difference(actual[key], expected[key], child)
    elif isinstance(actual, list) and isinstance(expected, list):
        for index, (left, right) in enumerate(zip(actual, expected, strict=False)):
            if not _same(left, right):
                return _first_difference(left, right, f"{path}[{index}]")
        if len(actual) != len(expected):
            return f"{path}[{min(len(actual), len(expected))}]"
    return path


def _validate_ai_document(
    bundle: ReportInput, response: AdapterResponse, *, rejection: dict[str, Any] | None = None
) -> str:
    """Keep the result-code API; optionally describe the first failing check (zero-based)."""
    if rejection is not None:
        rejection.clear()

    def reject(code: str, check: str, path: str, index: int | None = None) -> str:
        if rejection is not None:
            rejection.update(check=check, path=path)
            if index is not None:
                rejection["section_index"] = index
                assert response.document is not None
                section = response.document["sections"][index]
                rejection["section_title"] = (
                    section.get("title") if isinstance(section, dict) else None
                )
        return code

    if response.tool_events:
        return reject("tool_use_rejected", "tool_events", "tool_events")
    document = response.document
    if not isinstance(document, dict):
        return reject("invalid_json_schema", "document_type", "$")
    if set(document) != set(_OUTPUT_FIELDS):
        return reject("schema_validation_failed", "document_fields", "$")
    if document["bundle_id"] != bundle.bundle_id:
        return reject("schema_validation_failed", "bundle_id", "bundle_id")
    if document["current_stage"] != bundle.current_stage:
        return reject("stage_mutation_rejected", "current_stage", "current_stage")
    if document["core_states"] != bundle.core_states:
        return reject(
            "conclusion_mutation_rejected",
            "core_states",
            _first_difference(document["core_states"], bundle.core_states, "core_states"),
        )
    if not _same(document["conclusions"], bundle.conclusions):
        return reject(
            "conclusion_mutation_rejected",
            "conclusions",
            _first_difference(document["conclusions"], bundle.conclusions, "conclusions"),
        )
    if document["report_cutoff"] != bundle.report_cutoff.isoformat():
        return reject("schema_validation_failed", "report_cutoff", "report_cutoff")
    if document["proxy_used"] is not False:
        return reject("forbidden_content_rejected", "proxy_used", "proxy_used")
    sections = document["sections"]
    if not isinstance(sections, list) or not sections:
        return reject("schema_validation_failed", "sections", "sections")
    forbidden_terms = ("买入", "卖出", "目标价", "收益保证", "仓位建议")
    macro = "macro_stage" in bundle.conclusions
    confidence_told = False
    for index, section in enumerate(sections):
        path = f"sections[{index}]"
        if not isinstance(section, dict) or set(section) != {"title", "explanation"}:
            return reject("schema_validation_failed", "section_fields", path, index)
        if any(not isinstance(section[field], str) for field in ("title", "explanation")):
            return reject("schema_validation_failed", "section_types", path, index)
        if any(term in section["explanation"] for term in forbidden_terms):
            return reject("forbidden_content_rejected", "forbidden_terms", path, index)
        if macro:
            # The judgement leads: its stage, its confidence and the price stage apart.
            stated = _macro_statements(bundle, f"{section['title']}。{section['explanation']}")
            if (check := stated.failed) is not None:
                code = (
                    "conclusion_mutation_rejected"
                    if check in {"macro_stated_confidence", "macro_stated_score"}
                    else "stage_mutation_rejected"
                )
                return reject(code, check, path, index)
            confidence_told = confidence_told or stated.confidence_told
        elif any(stage != bundle.current_stage for stage in _stated_stages(section)):
            return reject("stage_mutation_rejected", "stated_stage", path, index)
        basis = bundle.results.get("noncanonical_basis")
        if not macro and not isinstance(basis, dict) and section["title"] == NONCANONICAL_TITLE:
            return reject("schema_validation_failed", "noncanonical_basis_missing", path, index)
        if isinstance(basis, dict):
            text = section["title"] + "。" + section["explanation"]
            if re.search(
                r"最接近|最相似|推测阶段|AI\s*阶段|"
                r"(?:倾向|更像|可视为|实际|当前|目前|现在).{0,12}"
                r"(?:(?:阶段|Stage)\s*(?:[IVX]+|[ⅠⅡⅢⅣⅤⅥ]|[一二三四五六1-6])|第[一二三四五六]阶段)",
                text,
                re.IGNORECASE,
            ):
                return reject("stage_mutation_rejected", "noncanonical_stated_stage", path, index)
            if section["title"] == NONCANONICAL_TITLE:
                if (error := reading_error(basis, section)) is not None:
                    return reject("conclusion_mutation_rejected", error, path, index)
            else:
                return reject("schema_validation_failed", "noncanonical_extra_section", path, index)
        for check, restates in (
            ("restates_confirmation", _restates_confirmation),
            ("restates_prices", _restates_prices),
            ("restates_bond_attribution", _restates_bond_attribution),
        ):
            if restates(bundle, section):
                return reject("conclusion_mutation_rejected", check, path, index)
        if not section["explanation"].strip() or any(
            separator in section["explanation"] for separator in "\r\n\u2028\u2029"
        ):
            return reject("paragraph_structure_invalid", "paragraph_structure", path, index)
    if (
        isinstance(bundle.results.get("noncanonical_basis"), dict)
        and sum(section["title"] == NONCANONICAL_TITLE for section in sections) != 1
    ):
        return reject("schema_validation_failed", "noncanonical_section_count", "sections")
    confidence = _mapping(_mapping(bundle.results.get("macro_judgement")).get("conclusion")).get(
        "confidence"
    )
    if macro and confidence in {"tendency", "weak"} and not confidence_told:
        # A tendency or a weak conclusion told as such, of the conclusion (spec story 37).
        return reject("conclusion_mutation_rejected", "macro_confidence_unstated", "sections")
    return "succeeded"


def _untranslated_codes(bundle: ReportInput, sections: list[dict[str, Any]]) -> list[str]:
    """The stage, metric and source codes the prose writes as such, not by their names."""
    codes = {code for names in bundle.display_names.values() for code in names} | set(STAGE_TITLES)
    text = "。".join(section["title"] + "。" + section["explanation"] for section in sections)
    return sorted(
        code
        for code in codes
        if re.search(rf"(?<![A-Za-z0-9_:]){re.escape(code)}(?![A-Za-z0-9_:])", text)
    )


def _report_snapshot(row: sqlite3.Row) -> ReportSnapshot:
    body_retained = bool(row["body_retained"])
    bundle = json.loads(str(row["bundle_document_json"]))
    if not isinstance(bundle, dict):
        raise ValueError("report_bundle_document_invalid")
    started_at = (
        datetime.fromisoformat(str(row["attempt_started_at"]))
        if row["attempt_started_at"] is not None
        else datetime.fromisoformat(str(row["created_at"]))
    )
    completed_at = (
        datetime.fromisoformat(str(row["attempt_completed_at"]))
        if row["attempt_completed_at"] is not None
        else started_at
    )
    return ReportSnapshot(
        report_snapshot_id=str(row["report_snapshot_id"]),
        projection_set_id=str(row["projection_set_id"]),
        target_business_date=str(row["target_business_date"]),
        version=int(row["version"]),
        status=str(row["status"]),
        adapter=str(row["adapter"]),
        current_stage=(str(row["current_stage"]) if row["current_stage"] is not None else None),
        bundle_id=str(row["bundle_id"]),
        bundle_hash=str(row["bundle_hash"]),
        model_version_id=str(row["model_version_id"]),
        schema_version=str(row["schema_version"]),
        prompt_version=str(row["prompt_version"]),
        input_schema_version=str(bundle["schema_version"]),
        input_prompt_version=str(bundle["prompt_version"]),
        report_cutoff=datetime.fromisoformat(str(bundle["report_cutoff"])),
        system_as_of=datetime.fromisoformat(str(bundle["system_as_of"])),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        duration_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        body_retained=body_retained,
        body=json.loads(str(row["body_json"])) if body_retained else {},
    )


def _report_attempt(row: sqlite3.Row) -> ReportAttempt:
    started_at = datetime.fromisoformat(str(row["started_at"]))
    completed_at = datetime.fromisoformat(str(row["completed_at"]))
    audit = json.loads(row["process_audit_json"]) if "process_audit_json" in set(row.keys()) else {}
    elapsed_ms = _timing_duration(audit, "elapsed_ms")
    return ReportAttempt(
        adapter=str(row["adapter"]),
        adapter_version=str(row["adapter_version"]),
        outcome=str(row["outcome"]),
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=(
            elapsed_ms
            if elapsed_ms is not None
            else max(0, int((completed_at - started_at).total_seconds() * 1000))
        ),
        tool_events=int(row["tool_events"]),
        output_hash=(str(row["output_hash"]) if row["output_hash"] is not None else None),
        process_audit=audit,
    )


def _rejection_check(audit: dict[str, Any]) -> str | None:
    rejection = audit.get("rejection")
    check = rejection.get("check") if isinstance(rejection, dict) else None
    return check if isinstance(check, str) else None


def _timing_duration(audit: dict[str, Any], field: str) -> int | None:
    timing = audit.get("timing")
    if not isinstance(timing, dict) or timing.get("basis") != "monotonic":
        return None
    value = timing.get(field)
    return value if type(value) is int and value >= 0 else None


def _hash_document(document: Any) -> str:
    return hashlib.sha256(_canonical_json(document).encode()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_REPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_bundle (
    bundle_id TEXT PRIMARY KEY,
    bundle_hash TEXT NOT NULL,
    projection_set_id TEXT NOT NULL,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS report_attempt (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_snapshot_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    outcome TEXT NOT NULL,
    tool_events INTEGER NOT NULL,
    output_hash TEXT
);
CREATE TABLE IF NOT EXISTS report_snapshot (
    report_snapshot_id TEXT PRIMARY KEY,
    client_request_id TEXT NOT NULL UNIQUE,
    projection_set_id TEXT NOT NULL,
    target_business_date TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    adapter TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    bundle_id TEXT NOT NULL REFERENCES evidence_bundle(bundle_id),
    bundle_hash TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    body_json TEXT NOT NULL,
    body_retained INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(target_business_date, version)
);
CREATE TRIGGER IF NOT EXISTS report_snapshot_identity_no_update
BEFORE UPDATE OF report_snapshot_id, projection_set_id, target_business_date,
    version, status, adapter, current_stage, bundle_id, bundle_hash,
    model_version_id, schema_version, prompt_version, created_at
ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
CREATE TRIGGER IF NOT EXISTS report_snapshot_no_delete
BEFORE DELETE ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
"""

_REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA = """
CREATE TABLE report_snapshot (
    report_snapshot_id TEXT PRIMARY KEY,
    client_request_id TEXT NOT NULL UNIQUE,
    projection_set_id TEXT NOT NULL,
    target_business_date TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    adapter TEXT NOT NULL,
    current_stage TEXT,
    bundle_id TEXT NOT NULL REFERENCES evidence_bundle(bundle_id),
    bundle_hash TEXT NOT NULL,
    model_version_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    body_json TEXT NOT NULL,
    body_retained INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(target_business_date, version)
);
"""

_REPORT_SNAPSHOT_IMMUTABILITY_TRIGGERS = """
CREATE TRIGGER report_snapshot_identity_no_update
BEFORE UPDATE OF report_snapshot_id, projection_set_id, target_business_date,
    version, status, adapter, current_stage, bundle_id, bundle_hash,
    model_version_id, schema_version, prompt_version, created_at
ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
CREATE TRIGGER report_snapshot_no_delete
BEFORE DELETE ON report_snapshot BEGIN SELECT RAISE(ABORT, 'report_snapshot_is_immutable'); END;
"""


def upgrade_report_process_audit(connection: sqlite3.Connection) -> None:
    from pring_cycle.report_review import REPORT_EXPLANATION_REVIEW_SCHEMA

    if "process_audit_json" not in {
        str(row[1]) for row in connection.execute("PRAGMA table_info(report_attempt)")
    }:
        connection.execute(
            "ALTER TABLE report_attempt ADD COLUMN process_audit_json TEXT NOT NULL DEFAULT '{}'"
        )
    connection.executescript(REPORT_EXPLANATION_REVIEW_SCHEMA)


def upgrade_report_snapshot_nullable_stage(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(report_snapshot)").fetchall()
    stage_column = next((row for row in columns if str(row[1]) == "current_stage"), None)
    if stage_column is None:
        raise RuntimeError("report_snapshot_current_stage_missing")
    if int(stage_column[3]) == 0:
        return
    rebuild_report_snapshot_stage_column(connection, nullable=True)


def rebuild_report_snapshot_stage_column(
    connection: sqlite3.Connection,
    *,
    nullable: bool,
) -> None:
    connection.execute("DROP TRIGGER IF EXISTS report_snapshot_identity_no_update")
    connection.execute("DROP TRIGGER IF EXISTS report_snapshot_no_delete")
    connection.execute("ALTER TABLE report_snapshot RENAME TO report_snapshot_legacy")
    schema = (
        _REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA
        if nullable
        else _REPORT_SNAPSHOT_NULLABLE_STAGE_SCHEMA.replace(
            "current_stage TEXT,",
            "current_stage TEXT NOT NULL,",
        )
    )
    connection.executescript(schema)
    connection.execute(
        """
        INSERT INTO report_snapshot(
            report_snapshot_id, client_request_id, projection_set_id,
            target_business_date, version, status, adapter, current_stage,
            bundle_id, bundle_hash, model_version_id, schema_version,
            prompt_version, body_json, body_retained, created_at
        )
        SELECT report_snapshot_id, client_request_id, projection_set_id,
            target_business_date, version, status, adapter, current_stage,
            bundle_id, bundle_hash, model_version_id, schema_version,
            prompt_version, body_json, body_retained, created_at
        FROM report_snapshot_legacy
        """
    )
    connection.execute("DROP TABLE report_snapshot_legacy")
    connection.executescript(_REPORT_SNAPSHOT_IMMUTABILITY_TRIGGERS)


_REPORT_SNAPSHOT_SELECT = """
SELECT report_snapshot.*, evidence_bundle.document_json AS bundle_document_json,
       (SELECT MIN(started_at) FROM report_attempt
        WHERE report_attempt.report_snapshot_id=report_snapshot.report_snapshot_id)
           AS attempt_started_at,
       (SELECT MAX(completed_at) FROM report_attempt
        WHERE report_attempt.report_snapshot_id=report_snapshot.report_snapshot_id)
           AS attempt_completed_at
FROM report_snapshot
JOIN evidence_bundle USING (bundle_id)
"""


# Standalone report repositories use the runtime artifact registry (migration 0001).
_REPORT_ARTIFACT_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    content_hash TEXT PRIMARY KEY,
    byte_count INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_reference (
    content_hash TEXT NOT NULL REFERENCES artifact(content_hash),
    source_reference TEXT NOT NULL,
    PRIMARY KEY (content_hash, source_reference)
);

"""
