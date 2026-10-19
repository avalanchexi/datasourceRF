from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle import credit_impulse
from pring_cycle.acquisition_outcome import SUCCEEDED, AcquisitionOutcomes
from pring_cycle.batches import current_batch_id
from pring_cycle.bond_attribution import SignalReading, bond_attribution_document
from pring_cycle.catalog import MetricDefinition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS, SYSTEM_TARGET_CUTOFF_VERSION
from pring_cycle.claim_adoption import ClaimAdoption
from pring_cycle.confirmation import (
    DERIVED_FORMULAS,
    OBSERVED_METRICS,
    OUTPUT_STRUCTURE,
    SESSION_FORMULAS,
    Action,
    ActionReading,
    BlockReading,
    ChangeReading,
    ConfirmationRules,
    DerivedInput,
    KeyIndicator,
    Member,
    MemberReading,
    ObservedReading,
    QuadrantReading,
    confirmation_document,
    derived_points,
    month_back,
    month_end,
)
from pring_cycle.display_projection import context_display
from pring_cycle.domain import StageResult
from pring_cycle.domain.macro import (
    EvidenceSignal,
    SignatureCard,
    derive_credit_response,
    derive_inventory_cycle,
    derive_overheat_state,
    derive_policy_direction,
    derive_price_pressure,
)
from pring_cycle.evidence import (
    AsOfMode,
    ClaimView,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
    select_among,
)
from pring_cycle.evidence import selected_claim as _selected_claim
from pring_cycle.evidence import usable_point as _usable_point
from pring_cycle.freshness import FRESHNESS_REGISTRY, backtracked, period_status
from pring_cycle.freshness import assess as freshness_assess
from pring_cycle.macro_judgement import MacroJudgementRules
from pring_cycle.metric_contracts import EFFECTIVE_UNTIL_CHANGED_METRICS, evidence_frequency
from pring_cycle.price_consistency import (
    CorePrices,
    PriceRules,
    price_consistency_document,
    supply_demand_document,
)
from pring_cycle.registered_warrants import WarrantRules, registered_warrant_change
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES
from pring_cycle.summary_cutoff import SummaryCutoff
from pring_cycle.trading_calendar import TradingCalendar, current_calendar, market_calendar
from pring_cycle.treasury_context import TREASURY_METRICS
from pring_cycle.warrant_inputs import WarrantHistoryCoverage

_POLICY_ACTION = {
    "CN_OMO_7D_RATE": "policy_action",
    "CN_OMO_7D_AMOUNT": "policy_action",
    "CN_RRR_EVENT": "policy_action",
    "CN_TOOL_LIQUIDITY_MONTHLY": "policy_action",
}
# What a rise of each transmission member means. Every member declares it, so a new one
# cannot fall back to being read as a rate: the bond indices are prices and rise as yields fall.
_TRANSMISSION_RISE_MEANS = {
    "CN_DR007": "tightening",
    "CN_DR007_POLICY_SPREAD": "tightening",
    "CN_SHIBOR_ON_1W_3M": "tightening",
    "CN_BOND_10Y_930916": "easing",
    "CN_BOND_FULL_PRICE_CNY030": "easing",
}
_POLICY_TRANSMISSION = {metric_id: "transmission" for metric_id in _TRANSMISSION_RISE_MEANS}
_CREDIT = {
    "CN_LPR_1Y_5Y": "credit_price",
    "CN_M1_M2": "money",
    "CN_SF_TOTAL": "social_financing",
    "CN_SF_COMPONENTS": "social_financing",
    "CN_LOAN_STRUCTURE": "loan_structure",
    "CN_CREDIT_IMPULSE": "credit_impulse",
}
_OVERHEAT = {
    "CN_PMI_ACTIVITY": "demand",
    "CN_INDUSTRIAL_VA": "production",
    "CN_CAPACITY_UTILIZATION": "production",
    "CN_INDUSTRIAL_FINANCE": "production",
    "CN_CREDIT_IMPULSE": "credit",
}
_PRICE = {
    "CN_COMMODITY_CORE_NHII": "upstream",
    "CN_COMMODITY_BROAD_NHCI": "upstream",
    "EIA_BRENT_RBRTE": "upstream",
    "EIA_WTI_RWTC": "upstream",
    "CN_PMI_PRICES": "producer",
    "CN_PPI": "producer",
    "CN_CPI_HEADLINE": "consumer",
    "CN_CORE_CPI": "consumer",
}
_INVENTORY = {
    "CN_ORDER_INVENTORY_SPREAD": "orders_inventory_gap",
    "CN_PRODUCTION_ORDER_SPREAD": "orders_inventory_gap",
    "CN_PMI_INVENTORY": "materials_finished_goods",
    "CN_FINISHED_GOODS_INVENTORY": "physical_inventory",
    "CN_INVENTORY_TURNOVER": "inventory_sales_turnover",
    "CN_PPI": "prices_profits",
    "CN_INDUSTRIAL_FINANCE": "prices_profits",
    "CN_CAPACITY_UTILIZATION": "capacity",
    "CN_CREDIT_IMPULSE": "credit_physical_inventory",
    "CN_FUTURES_WARRANTS": "credit_physical_inventory",
}


@dataclass(frozen=True)
class ContextProjection:
    macro: dict[str, object]
    inventory: dict[str, object]
    observation_version_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    warrant_history: WarrantHistoryCoverage | None = None


@dataclass(frozen=True)
class _MetricRows:
    rows: tuple[dict[str, object], ...]
    warrant_history: WarrantHistoryCoverage | None = None
    # The warrants' claims the family adopts, whole symbol-days; None when it decides none.
    adoptable: frozenset[str] | None = None


# The loan change read off year-to-date increments: January's is the month's change itself.
LOAN_YTD_FORMULA = "loan-ytd-monthly-change-v0002"
# The repo's net injection on the newest day both measures are reported, or on the newest
# day with its maturity reported or derived from the injections a week before.
REPO_SAME_DAY_FORMULA = "repo-net-injection-v0001"
REPO_CALENDAR_FORMULA = "repo-net-injection-trading-calendar-v0002"
_SUPPORTED_FORMULA_VERSIONS = {
    "credit_impulse": set(credit_impulse.VERSIONS),
    "dr007_policy_spread": {"dr007-policy-spread-v0001"},
    "loan_monthly_change": {
        "loan-stock-monthly-change-v0001",
        LOAN_YTD_FORMULA,
    },
    "omo_net_injection": {
        REPO_SAME_DAY_FORMULA,
        REPO_CALENDAR_FORMULA,
    },
    "order_inventory_spread": {
        "order-inventory-v0001",
        "pmi-order-inventory-spread-v0001",
    },
    "production_order_spread": {"pmi-production-order-spread-v0001"},
    "real_inventory_approximation": {"inventory-ppi-v0001", "inventory-ppi-common-month-v0002"},
    "ust_2s10s_spread": {"ust-2s10s-spread-v0001"},
}


@dataclass(frozen=True)
class ContextProjectionRules:
    """A model's context rules; ``confirmation`` None reads the four labels (ADR-0037)."""

    metric_catalog_version: str
    metric_definitions: tuple[MetricDefinition, ...]
    formula_versions: Mapping[str, str]
    confirmation: ConfirmationRules | None = None
    # The macro stage judgement's rules (ADR-0043), read from the confirmation's indicators.
    macro_judgement: MacroJudgementRules | None = None

    @classmethod
    def from_manifest(cls, manifest: Mapping[str, object]) -> ContextProjectionRules:
        catalog_version = manifest.get("metric_catalog_version")
        raw_definitions = manifest.get("metric_definitions")
        raw_formulas = manifest.get("derived_formula_versions")
        if not isinstance(catalog_version, str) or not catalog_version:
            raise ValueError("context_model_catalog_version_invalid")
        if not isinstance(raw_definitions, list) or not raw_definitions:
            raise ValueError("context_model_metric_definitions_invalid")
        if not isinstance(raw_formulas, Mapping):
            raise ValueError("context_model_formula_versions_invalid")
        definitions = tuple(
            _metric_definition_from_manifest(item, catalog_version=catalog_version)
            for item in raw_definitions
        )
        metric_ids = [item.metric_id for item in definitions]
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("context_model_metric_id_duplicate")
        formulas: dict[str, str] = {}
        for raw_key, raw_version in raw_formulas.items():
            if not isinstance(raw_key, str) or not isinstance(raw_version, str):
                raise ValueError("context_model_formula_versions_invalid")
            supported = _SUPPORTED_FORMULA_VERSIONS.get(raw_key)
            if supported is None or raw_version not in supported:
                raise ValueError("context_model_formula_version_unsupported")
            formulas[raw_key] = raw_version
        confirmation = ConfirmationRules.from_manifest(manifest)
        if confirmation is not None and not confirmation.metric_ids() <= set(metric_ids):
            raise ValueError("confirmation_key_indicator_metric_missing")
        macro_judgement = MacroJudgementRules.from_manifest(
            manifest,
            {item.key: item.dimension for item in confirmation.indicators}
            if confirmation is not None
            else None,
        )
        return cls(catalog_version, definitions, formulas, confirmation, macro_judgement)


# The cores' rows skip the family recheck here: core readiness rechecks them.
_NOT_RECHECKED_IN_PROJECTION = frozenset(CORE_API_IDENTITIES)


def context_metric_ids(rules: ContextProjectionRules) -> frozenset[str]:
    return frozenset(
        set(_POLICY_ACTION)
        | set(_POLICY_TRANSMISSION)
        | set(_CREDIT)
        | set(_OVERHEAT)
        | set(_PRICE)
        | set(_INVENTORY)
        | {item.metric_id for item in rules.metric_definitions if item.priority == "P2"}
    )


def _metric_definition_from_manifest(
    value: object,
    *,
    catalog_version: str,
) -> MetricDefinition:
    if not isinstance(value, Mapping):
        raise ValueError("context_model_metric_definition_invalid")
    definition_version = value.get("definition_version")
    if definition_version != catalog_version:
        raise ValueError("context_model_definition_version_mismatch")
    text_fields = (
        "metric_id",
        "name_cn",
        "priority",
        "role",
        "unit",
        "frequency",
        "certification_status",
        "release_event_family",
        "release_rule",
        "release_timezone",
    )
    text_values: dict[str, str] = {}
    for field in text_fields:
        raw = value.get(field)
        if not isinstance(raw, str) or not raw:
            raise ValueError("context_model_metric_definition_invalid")
        text_values[field] = raw
    tuple_values: dict[str, tuple[str, ...]] = {}
    for field in ("dimensions", "source_codes", "source_candidates", "allowed_units"):
        raw = value.get(field)
        if not isinstance(raw, (list, tuple)) or not all(
            isinstance(item, str) and item for item in raw
        ):
            raise ValueError("context_model_metric_definition_invalid")
        tuple_values[field] = tuple(raw)
    return MetricDefinition(
        metric_id=text_values["metric_id"],
        name_cn=text_values["name_cn"],
        priority=text_values["priority"],
        role=text_values["role"],
        unit=text_values["unit"],
        frequency=text_values["frequency"],
        dimensions=tuple_values["dimensions"],
        source_codes=tuple_values["source_codes"],
        source_candidates=tuple_values["source_candidates"],
        certification_status=text_values["certification_status"],
        release_event_family=text_values["release_event_family"],
        release_rule=text_values["release_rule"],
        release_timezone=text_values["release_timezone"],
        definition_version=catalog_version,
        allowed_units=tuple_values["allowed_units"],
    )


def build_context_projection(
    repository: EvidenceRepository,
    *,
    as_of: datetime,
    model_manifest: Mapping[str, object],
    target_business_date: str | None = None,
    visible_evidence_start: str | None = None,
    as_of_mode: AsOfMode = AsOfMode.SYSTEM,
    persist_derived: bool = True,
    formal_stage: StageResult | None = None,
    calendar: TradingCalendar | None = None,
    core_prices: Mapping[str, CorePrices] | None = None,
    public_as_of: datetime | None = None,
) -> ContextProjection:
    """The day's context; a model with confirmation rules reads it against ``formal_stage``.

    The target day's summary reads what is public by the run's cutoff (``public_as_of``),
    of periods through the day; without it, what was public by the day's end, as a
    backfilled day does (``SummaryCutoff``, ADR-0041 2026-10-13).

    The formal stage is decided from the three cores before, and only shared here: a
    model reading the four labels needs none. Its daily key indicators count sessions on
    ``calendar``, the SSE's as known (the run's by default), and its policy actions are
    read in the window from ``visible_evidence_start``. Beside the dimension summary, never
    counted, it shows the cores' observation interfaces and their price internal
    consistency, read from the actual closes their gates passed (``core_prices``), and in
    the stages it is given for, the commodity supply-demand note (macro semantics 09); and
    beside the bond's state as its gate let it stand, what drives its trend (ticket 10).
    """
    if as_of.tzinfo is None:
        raise ValueError("context_projection_as_of_must_be_timezone_aware")
    rules = ContextProjectionRules.from_manifest(model_manifest)
    repository.validate_model_catalog(model_manifest)
    definitions = {item.metric_id: item for item in rules.metric_definitions}
    visible_repository: Any = repository
    visible_start: date | None = None
    if target_business_date is not None:
        try:
            target_date = date.fromisoformat(target_business_date)
        except ValueError as error:
            raise ValueError("context_projection_target_date_invalid") from error
        cutoff = (
            SummaryCutoff(target_date, public_as_of)
            if public_as_of is not None
            else SummaryCutoff.at_day_end(target_date)
        )
        target_repository = TargetBoundEvidenceRepository(
            repository,
            target_date,
            {metric_id: definition.frequency for metric_id, definition in definitions.items()},
            allow_system_at_target=(
                model_manifest.get("point_in_time_rule_version") == SYSTEM_TARGET_CUTOFF_VERSION
            ),
            cutoff=cutoff,
        )
        repository = target_repository  # type: ignore[assignment]
        if visible_evidence_start is not None:
            try:
                visible_start = date.fromisoformat(visible_evidence_start)
            except ValueError as error:
                raise ValueError("context_projection_visible_start_invalid") from error
            if visible_start > target_date:
                raise ValueError("context_projection_visible_window_invalid")
            visible_repository = TargetBoundEvidenceRepository(
                target_repository,
                target_date,
                {metric_id: definition.frequency for metric_id, definition in definitions.items()},
                visible_start=visible_start,
                allow_system_at_target=(
                    model_manifest.get("point_in_time_rule_version") == SYSTEM_TARGET_CUTOFF_VERSION
                ),
                cutoff=cutoff,
            )
        else:
            visible_repository = target_repository
    relevant = context_metric_ids(rules)
    missing = sorted(relevant - definitions.keys())
    if missing:
        raise ValueError(f"context_model_metric_missing:{','.join(missing)}")
    prices = rules.confirmation.prices if rules.confirmation is not None else None
    if prices is not None:
        # The observation interfaces the catalog holds; one it does not is shown as such.
        relevant = relevant | (prices.interface_metrics & definitions.keys())
    metric_results = {
        metric_id: _metric_rows(
            visible_repository,
            definitions[metric_id],
            as_of=as_of,
            as_of_mode=as_of_mode,
        )
        for metric_id in sorted(relevant)
    }
    rows_by_metric = {metric_id: result.rows for metric_id, result in metric_results.items()}
    display_inputs: set[str] = set()
    for metric_id in sorted(relevant):
        definition = definitions[metric_id]
        if definition.priority != "P2" and (
            prices is None or metric_id not in prices.interface_metrics
        ):
            continue
        series = repository.metric_series(
            metric_id,
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition.definition_version,
        )
        rejected = set(
            ClaimAdoption(
                repository, definition_version=definition.definition_version, mode=as_of_mode
            )
            .check({metric_id: series})[metric_id]
            .not_adoptable
        )
        freshness_rule = FRESHNESS_REGISTRY.get(metric_id)
        display_calendar = (
            market_calendar(freshness_rule.market, calendar or current_calendar())
            if freshness_rule
            else None
        )
        for row in rows_by_metric[metric_id]:
            display = context_display(
                definition,
                [point for point in series if point.dimensions == row.get("dimensions")],
                target=date.fromisoformat(target_business_date)
                if target_business_date
                else as_of.astimezone(ZoneInfo("Asia/Shanghai")).date(),
                calendar=display_calendar,
                frequency=evidence_frequency(metric_id, definition.frequency),
                rejected=rejected,
            )
            row["display"] = display
            display_inputs.update(
                point["selected_claim_id"]
                for point in display["points"]
                if point["selected_claim_id"]
            )
            for key in ("change_5", "change_120"):
                display_inputs.update(display[key].get("input_claim_ids", []))
    acquisition_period = (
        target_business_date or as_of.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    )
    outcomes = AcquisitionOutcomes(repository.database_path)
    for definition in definitions.values():
        if definition.priority != "P2":
            continue
        attempt = outcomes.latest(
            definition.metric_id,
            as_of=as_of,
            definition_version=definition.definition_version,
            target_business_date=acquisition_period,
        )
        latest = (
            {
                "attempt_id": attempt.attempt_id,
                "channel": attempt.channel,
                "outcome": attempt.outcome,
                "recorded_at": attempt.recorded_at.isoformat(),
                "definition_version": definition.definition_version,
                "condition": attempt.condition,
                "request_sent": False if attempt.request_sent is False else None,
                "rejected_fields": attempt.rejected_fields,
                "latest_source_period": attempt.latest_source_period,
                "source_timezone": attempt.source_timezone,
                "release_date": attempt.release_date,
                "next_release_date": attempt.next_release_date,
                "release_timezone": attempt.release_timezone,
                "step": attempt.step,
                "completeness": attempt.completeness,
                "external_code": attempt.external_code,
                "rule_reason": attempt.rule_reason,
                "error_type": attempt.error_type,
                "missing_members": list(attempt.missing_members),
            }
            if attempt is not None
            else None
        )
        rows_by_metric[definition.metric_id] = tuple(
            {
                **row,
                # A success says what it delivered (ticket 18); a failure, how it failed.
                "acquisition_status": (
                    attempt.completeness or attempt.outcome
                    if attempt is not None and attempt.outcome == SUCCEEDED
                    else attempt.outcome
                    if attempt is not None
                    else "no_attempt_for_target"
                ),
                "latest_acquisition": latest,
            }
            for row in rows_by_metric[definition.metric_id]
        )
    rows_by_metric["CN_OMO_7D_AMOUNT"] = tuple(
        row
        for row in rows_by_metric["CN_OMO_7D_AMOUNT"]
        if row.get("dimensions") != {"measure": "net_injection"}
    )
    formula_versions = dict(rules.formula_versions)
    for formula, output_metric, input_metrics in (
        ("dr007_policy_spread", "CN_DR007_POLICY_SPREAD", ("CN_DR007", "CN_OMO_7D_RATE")),
        ("ust_2s10s_spread", "UST_2S10S_SPREAD", ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD")),
        (
            "order_inventory_spread",
            "CN_ORDER_INVENTORY_SPREAD",
            ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"),
        ),
        ("production_order_spread", "CN_PRODUCTION_ORDER_SPREAD", ("CN_PMI_ACTIVITY",)),
        ("loan_monthly_change", "CN_LOAN_STRUCTURE", ("CN_LOAN_STRUCTURE",)),
        ("omo_net_injection", "CN_OMO_7D_AMOUNT", ("CN_OMO_7D_AMOUNT",)),
        ("credit_impulse", "CN_CREDIT_IMPULSE", ("CN_SF_TOTAL", "CN_GDP")),
    ):
        if formula not in formula_versions:
            continue
        missing_dependencies = sorted({output_metric, *input_metrics} - definitions.keys())
        if missing_dependencies:
            raise ValueError(f"context_model_metric_missing:{','.join(missing_dependencies)}")
    trading_calendar_metric_id = _core_stock_metric_id(model_manifest)
    if trading_calendar_metric_id not in definitions:
        trading_calendar_metric_id = None
    market_derived_rows, market_derived_ids = _derived_market_context_rows(
        repository,
        visible_start=visible_start,
        as_of=as_of,
        formula_versions=formula_versions,
        definition_version=rules.metric_catalog_version,
        trading_calendar_metric_id=trading_calendar_metric_id,
        as_of_mode=as_of_mode,
        persist_derived=persist_derived,
    )
    terminal_period_metrics = {
        "CN_DR007_POLICY_SPREAD": ("CN_DR007",),
        "UST_2S10S_SPREAD": ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
        "CN_ORDER_INVENTORY_SPREAD": ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"),
        "CN_PRODUCTION_ORDER_SPREAD": ("CN_PMI_ACTIVITY",),
        "CN_LOAN_STRUCTURE": ("CN_LOAN_STRUCTURE",),
        "CN_OMO_7D_AMOUNT": ("CN_OMO_7D_AMOUNT",),
    }
    for metric_id, rows in market_derived_rows.items():
        for row in rows:
            # Age the terminal period, not earlier policy-effective or preheat inputs.
            row["status"] = (
                "stale"
                if any(
                    _period_freshness(definitions[parent], str(row["period"]), as_of=as_of)
                    == "stale"
                    for parent in terminal_period_metrics[metric_id]
                )
                else "current"
            )
        existing = rows_by_metric[metric_id]
        rows_by_metric[metric_id] = (
            tuple(row for row in existing if not str(row["observation_id"]).startswith("gap:"))
            + rows
        )
    treasury_inputs = [
        {
            "metric_id": metric_id,
            "acquisition_status": row["acquisition_status"],
            "latest_acquisition": row["latest_acquisition"],
        }
        for metric_id in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD")
        for row in rows_by_metric[metric_id]
    ]
    rows_by_metric["UST_2S10S_SPREAD"] = tuple(
        {
            **row,
            "acquisition_status": "derived_from_inputs",
            "latest_acquisition": None,
            "input_acquisition": treasury_inputs,
        }
        for row in rows_by_metric["UST_2S10S_SPREAD"]
    )
    credit_impulse_row, credit_formula, credit_version_ids = _credit_impulse_proxy(
        repository,
        as_of=as_of,
        configured_formula_version=formula_versions.get("credit_impulse"),
        definition_version=rules.metric_catalog_version,
        definitions=definitions,
        as_of_mode=as_of_mode,
        persist_derived=persist_derived,
    )
    if credit_impulse_row is not None:
        rows_by_metric["CN_CREDIT_IMPULSE"] = (credit_impulse_row,)
    real_inventory, derived_ids = _real_inventory_proxy(
        repository,
        rows_by_metric,
        as_of=as_of,
        formula_version=rules.formula_versions.get("real_inventory_approximation"),
        as_of_mode=as_of_mode,
        persist_derived=persist_derived,
        series_repository=visible_repository,
        ppi_definition=definitions.get("CN_PPI"),
    )
    international_context = _international_context(rows_by_metric, rules.metric_definitions)
    confirmation_inputs: set[str] = set()
    if rules.confirmation is None:
        policy_actions = _signals(rows_by_metric, _POLICY_ACTION, transform="policy")
        transmission = _signals(rows_by_metric, _POLICY_TRANSMISSION, transform="policy")
        credit_signals = _signals(rows_by_metric, _CREDIT, transform="credit")
        overheat_signals = _signals(rows_by_metric, _OVERHEAT)
        price_signals = _signals(rows_by_metric, _PRICE)
        inventory_signals = _signals(rows_by_metric, _INVENTORY)
        policy = derive_policy_direction(actions=policy_actions, transmission=transmission)
        credit = derive_credit_response(credit_signals)
        overheat = derive_overheat_state(overheat_signals)
        price = derive_price_pressure(price_signals)
        demand = _role_direction(overheat_signals, "demand")
        production = _role_direction(overheat_signals, "production")
        inventory_direction = _inventory_direction(inventory_signals)
        inventory = derive_inventory_cycle(
            demand=demand,
            production=production,
            inventory=inventory_direction,
            observations=inventory_signals,
        )
        macro_document: dict[str, object] = {
            "policy_direction": policy.state,
            "policy_action": {
                "direction": _policy_component_direction(policy_actions),
                "evidence": _row_documents(rows_by_metric, _POLICY_ACTION),
            },
            "transmission": {
                "direction": _policy_component_direction(transmission),
                "evidence": _row_documents(rows_by_metric, _POLICY_TRANSMISSION),
            },
            "credit_response": credit.state,
            "credit": {
                "state": credit.state,
                "evidence": _row_documents(rows_by_metric, _CREDIT),
                "formula": credit_formula,
            },
            "overheat_state": overheat.state,
            "overheat": {
                "state": overheat.state,
                "evidence": _row_documents(rows_by_metric, _OVERHEAT),
                "support": [asdict(item) for item in overheat.support],
                "counterevidence": [asdict(item) for item in overheat.counterevidence],
                "gaps": [asdict(item) for item in overheat.gaps],
            },
            "price_pressure": price.state,
            "price_chain": {
                "state": price.state,
                "evidence": _row_documents(rows_by_metric, _PRICE),
                "support": [asdict(item) for item in price.support],
                "counterevidence": [asdict(item) for item in price.counterevidence],
                "gaps": [asdict(item) for item in price.gaps],
                "energy_boundary": "headline_cpi_ppi_input_not_core_cpi_component",
            },
            "international_context": international_context,
            "score": None,
        }
        inventory_document: dict[str, object] = {
            "quadrant": inventory.quadrant,
            "directions": {
                "demand": demand,
                "production": production,
                "inventory": inventory_direction,
            },
            "cards": [_inventory_card_document(card, rows_by_metric) for card in inventory.cards],
            "real_inventory_approximation": real_inventory,
            "semantics": {
                "pmi_inventory": "diffusion_index_not_inventory_quantity",
                "futures_warrants": "registered_receipts_not_total_industrial_inventory",
            },
            "score": None,
        }
        inventory_context_state = inventory.quadrant or (
            "conflict"
            if "conflict" in {demand, production, inventory_direction}
            else "insufficient_data"
        )
        warning_groups = {
            "policy": policy.state,
            "credit": credit.state,
            "overheat": overheat.state,
            "price": price.state,
            "inventory": inventory_context_state,
        }
        warnings = tuple(
            f"{name}_context_degraded:{state}"
            for name, state in warning_groups.items()
            if state in {"conflict", "insufficient_data", "transmission_conflict"}
        )
    else:
        if formal_stage is None:
            raise ValueError("confirmation_formal_stage_required")
        day = (
            date.fromisoformat(target_business_date)
            if target_business_date is not None
            else as_of.astimezone(ZoneInfo("Asia/Shanghai")).date()
        )
        # The cores and their own kinds are shown under the cores, no evidence of prices
        # or of transmission (N06).
        shown = (
            prices.interface_metrics | set(prices.cores.values())
            if prices is not None
            else frozenset()
        )
        readings = {
            indicator.key: _member_readings(
                repository,
                indicator,
                rows_by_metric,
                definitions,
                as_of=as_of,
                as_of_mode=as_of_mode,
                day=day,
                window_start=visible_evidence_start,
                calendar=calendar or current_calendar(),
            )
            for indicator in rules.confirmation.indicators
        }
        confirmation_inputs = {
            version
            for members in readings.values()
            for member in members
            if member.evidence_status == "current"
            for version in member.observation_versions()
        }
        display_inputs.update(
            version
            for members in readings.values()
            for member in members
            for version in member.observation_versions()
        )
        # The four labels are not given, nor stood in for: the dimension summary is.
        macro_document = {
            "output_structure": OUTPUT_STRUCTURE,
            "confirmation": confirmation_document(
                rules.confirmation,
                readings,
                current_stage=formal_stage.current_stage,
                stage_reason=formal_stage.reason,
                observed={
                    metric_id: _observed_reading(metric_id, rows_by_metric.get(metric_id, ()))
                    for metric_id in OBSERVED_METRICS
                },
            ),
            "policy_action": {"evidence": _row_documents(rows_by_metric, _POLICY_ACTION)},
            "transmission": {
                "evidence": _row_documents(rows_by_metric, _apart(_POLICY_TRANSMISSION, shown))
            },
            "credit": {
                "evidence": _row_documents(rows_by_metric, _CREDIT),
                "formula": credit_formula,
            },
            "overheat": {"evidence": _row_documents(rows_by_metric, _OVERHEAT)},
            "price_chain": {
                "evidence": _row_documents(rows_by_metric, _apart(_PRICE, shown)),
                "energy_boundary": "headline_cpi_ppi_input_not_core_cpi_component",
            },
            "international_context": international_context,
            "score": None,
        }
        _reading_display_metadata(
            macro_document["confirmation"],
            rows_by_metric,
            definitions,
            repository.version_units(display_inputs),
        )
        quadrant = next(
            (
                item
                for dimension in macro_document["confirmation"]["dimensions"]  # type: ignore[index]
                if dimension["dimension"] == "inventory"
                for item in dimension["key_indicators"]
            ),
            None,
        )
        # The inventory dimension's conclusion is its quadrant; its evidence is kept, the
        # real inventory approximation a rough proxy beside it, neither counted nor in the
        # quadrant (N12).
        inventory_document = {
            "output_structure": OUTPUT_STRUCTURE,
            "status": "not_connected" if quadrant is None else "connected",
            "evidence": _row_documents(rows_by_metric, _INVENTORY),
            "real_inventory_approximation": {
                **real_inventory,
                "semantics": "rough_price_adjusted_proxy",
                "counted": False,
                "quadrant_input": False,
            },
            "semantics": {
                "pmi_inventory": "diffusion_index_not_inventory_quantity",
                "futures_warrants": "registered_receipts_not_total_industrial_inventory",
                "real_inventory_approximation": "rough_price_adjusted_proxy_not_counted",
            },
            "score": None,
        }
        if quadrant is not None:
            rule = next(item for item in rules.confirmation.indicators if item.quadrant)
            inventory_document.update(_quadrant_document(quadrant, rule.auxiliary, rows_by_metric))
        if rules.confirmation.warrants is not None:
            warrants = _registered_warrants(
                visible_repository,
                definitions["CN_FUTURES_WARRANTS"],
                rules.confirmation.warrants,
                metric_results["CN_FUTURES_WARRANTS"].adoptable,
                as_of=as_of,
                as_of_mode=as_of_mode,
                window=(visible_evidence_start, day.isoformat()),
            )
            inventory_document["registered_warrants"] = warrants
            confirmation_inputs.update(warrants["observation_version_ids"])  # type: ignore[arg-type]
        if prices is not None:
            stage = formal_stage.current_stage.value if formal_stage.current_stage else None
            macro_document["observation_interfaces"] = _interface_documents(prices, rows_by_metric)
            consistency, used = _price_consistency(
                visible_repository,
                prices,
                definitions,
                as_of=as_of,
                as_of_mode=as_of_mode,
                stage=stage,
                cores=core_prices,
                span=_span(calendar or current_calendar(), day, prices.points),
            )
            macro_document["price_consistency"] = consistency
            confirmation_inputs.update(used)
            macro_document["supply_demand"] = supply_demand_document(
                prices.supply_demand,
                stage=stage,
                readings={
                    item.name: _demand_reading(readings[item.indicator], item.member)
                    for item in prices.supply_demand.readings
                },
                warrants=inventory_document.get("registered_warrants"),  # type: ignore[arg-type]
            )
        attribution = rules.confirmation.attribution
        if attribution is not None:
            bond = (core_prices or {}).get(attribution.core)
            macro_document["bond_attribution"] = bond_attribution_document(
                attribution,
                bond=bond.state if bond is not None else None,
                readings={
                    signal.name: _signal_reading(readings[signal.indicator][0], signal.reading)
                    for signal in attribution.signals
                },
            )
        warnings = ()
    all_rows = [row for rows in rows_by_metric.values() for row in rows]
    model_inputs = set(derived_ids) | confirmation_inputs
    for row in [*all_rows, real_inventory]:
        if row.get("status") not in {"current", "available"} or row.get("value") is None:
            continue
        selected_id = row.get("selected_claim_id")
        if isinstance(selected_id, str):
            model_inputs.add(selected_id)
        for key in (
            "input_observation_version_ids",
            "trading_calendar_observation_version_ids",
            "direction_input_observation_version_ids",
        ):
            inputs = row.get(key)
            if isinstance(inputs, list):
                model_inputs.update(str(item) for item in inputs)
    macro_document["model_input_observation_version_ids"] = sorted(model_inputs)
    versions = tuple(
        sorted(
            {
                str(claim["claim_id"])
                for row in all_rows
                for claim in _document_rows(row.get("claims"))
                if isinstance(claim.get("claim_id"), str)
            }
            | set(credit_version_ids)
            | set(derived_ids)
            | set(market_derived_ids)
            | model_inputs
            | display_inputs
        )
    )
    if any(item["status"] != "current" for item in international_context):
        warnings += ("p2_context_degraded",)
    return ContextProjection(
        macro_document,
        inventory_document,
        versions,
        warnings,
        warrant_history=metric_results["CN_FUTURES_WARRANTS"].warrant_history,
    )


def _reading_display_metadata(
    document: Any,
    rows: Mapping[str, tuple[dict[str, object], ...]],
    definitions: Mapping[str, MetricDefinition],
    version_units: Mapping[str, str],
) -> None:
    """Keep the latest source period separate from the period the model actually read."""
    if isinstance(document, dict):
        if "member" in document and "periods" in document:
            metric = str(document.get("metric_id") or "")
            definition = definitions.get(metric)
            units = {
                version_units[version]
                for version in document.get("observation_version_ids", [])
                if version in version_units
            }
            document["unit"] = next(iter(units)) if len(units) == 1 else None
            document["frequency"] = (
                evidence_frequency(metric, definition.frequency) if definition else None
            )
            dimensions = document["member"]
            matching = [
                row
                for row in rows.get(metric, ())
                if isinstance(row_dimensions := row.get("dimensions"), dict)
                and all(row_dimensions.get(key) == value for key, value in dimensions.items())
            ]
            latest = max(matching, key=lambda row: str(row.get("period") or ""), default=None)
            document["latest_source"] = (
                {
                    key: latest.get(key)
                    for key in ("value", "unit", "period", "selected_claim_id", "status")
                }
                if latest and not document.get("formula_version")
                else None
            )
            return
        for child in document.values():
            _reading_display_metadata(child, rows, definitions, version_units)
    elif isinstance(document, list):
        for child in document:
            _reading_display_metadata(child, rows, definitions, version_units)


def _member_readings(
    repository: Any,
    indicator: KeyIndicator,
    rows_by_metric: Mapping[str, tuple[dict[str, object], ...]],
    definitions: Mapping[str, MetricDefinition],
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
    day: date,
    window_start: str | None,
    calendar: TradingCalendar,
) -> tuple[MemberReading, ...]:
    """Each member's newest periods, the main member first.

    The newest is the member's evidence row as shown (or its stand-in's, when newer); the
    periods before it are read whether or not the visible window shows them, as a
    comparison is (ticket 30). A period not held is missing and ends the run: an older one
    held never stands in for it. A month the member is never released for is passed over.
    Each of the periods grace reaches back is read too, as the member stood then, from the
    periods the lookback declares and none before. A derived member is read for the main
    member's newest month and the one before. A policy indicator reads its members'
    actions in the evidence window; a daily one, its members' sessions on ``calendar`` to
    ``day`` (macro semantics ticket 06).
    """
    usable: dict[tuple[str, str], dict[str, MetricSeriesPoint]] = {}

    def points(metric_id: str, dimensions: Mapping[str, str]) -> dict[str, MetricSeriesPoint]:
        key = (metric_id, json.dumps(dict(dimensions), sort_keys=True))
        if key not in usable:
            usable[key] = _usable_points_by_period(
                repository,
                metric_id,
                as_of=as_of,
                dimensions=dict(dimensions),
                as_of_mode=as_of_mode,
                definition_version=definitions[metric_id].definition_version,
            )
        return usable[key]

    def matching(member: Member) -> list[MetricSeriesPoint]:
        """The member's usable points out by ``day``, oldest first; any of its scopes when
        partial."""
        held: Iterable[MetricSeriesPoint] = (
            points(member.metric_id, member.dimensions).values()
            if not member.partial
            else (
                point
                for point in repository.metric_series(
                    member.metric_id,
                    mode=as_of_mode,
                    as_of=as_of,
                    definition_version=definitions[member.metric_id].definition_version,
                )
                if _usable_point(point)
            )
        )
        return sorted(
            (point for point in held if member.matches(point.dimensions)),
            key=lambda point: (point.period_end, json.dumps(point.dimensions, sort_keys=True)),
        )

    if indicator.quadrant is not None:
        return _quadrant_readings(indicator, rows_by_metric, points)
    if indicator.actions is not None:
        return tuple(
            _action_reading(
                indicator,
                member,
                role,
                matching(member),
                _action_status(rows_by_metric[member.metric_id], member, repository.database_path),
                day=day,
                window_start=window_start,
                monthly=definitions[member.metric_id].frequency == "monthly",
                calendar=calendar,
                notices=(
                    {point.period_end for point in matching(indicator.notices)}
                    if indicator.notices is not None
                    else None
                ),
                released=(
                    matching(replace(member, dimensions=indicator.released, partial=True))
                    if indicator.released is not None
                    else []
                ),
            )
            for role, member in _roles(indicator)
        )
    readings: list[MemberReading] = []
    for role, member in _roles(indicator):
        months = indicator.periods(member)
        if indicator.frequency == "daily" and member.frequency is None:
            readings.append(
                _block_reading(
                    indicator,
                    member,
                    role,
                    rows_by_metric,
                    points,
                    matching,
                    day=day,
                    calendar=calendar,
                )
            )
            continue
        if member.formula is not None:
            readings.append(
                _derived_reading(
                    indicator,
                    member,
                    role,
                    readings[0] if readings else None,
                    rows_by_metric,
                    points,
                    day=day,
                    calendar=calendar,
                )
            )
            continue
        shown, status = _shown(rows_by_metric[member.metric_id], member)
        # A daily indicator's member read by month steps a month at a time.
        level_line = indicator.level_line if member.frequency is None else None
        if shown is None:
            readings.append(MemberReading(member, role, status, (), (), level_line, months))
            continue
        newest = shown[:7]
        step = indicator.step if member.frequency is None else 1
        # The farthest month the lookback declares: grace reads no further back.
        history = indicator.history(member)
        oldest = month_back(newest, (indicator.reach(member) - 1) * step)

        span = (months, step, oldest)
        earlier: list[MemberReading] = []
        end = newest
        for _ in range(history):
            end = month_back(end, step)
            while int(end[5:7]) in member.unreleased_months:
                end = month_back(end, step)
            earlier.append(
                _period_reading(indicator, member, role, status, points, end, span, level_line)
            )
        reading = _period_reading(indicator, member, role, status, points, newest, span, level_line)
        readings.append(replace(reading, earlier=tuple(earlier)))
    return tuple(readings)


def _apart(roles: dict[str, str], shown: Collection[str]) -> dict[str, str]:
    """``roles`` less the metrics shown under a core."""
    return {metric_id: role for metric_id, role in roles.items() if metric_id not in shown}


def _interface_documents(
    rules: PriceRules, rows_by_metric: Mapping[str, tuple[dict[str, object], ...]]
) -> dict[str, object]:
    """Each core's observation interfaces with their rows as shown, never counted; one the
    catalog does not hold is said to be absent."""
    return {
        "label": "观察接口",
        "counted": False,
        "cores": [
            {
                "core": item.core,
                "core_metric_id": item.core_metric_id,
                "label": item.label,
                "members": [
                    {
                        "metric_id": member.metric_id,
                        "label": member.label,
                        "reads_as": member.reads_as,
                        "counted": False,
                        "in_catalog": member.metric_id in rows_by_metric,
                        "evidence": list(rows_by_metric.get(member.metric_id, ())),
                    }
                    for member in item.members
                ],
            }
            for item in rules.interfaces
        ],
    }


def _span(calendar: TradingCalendar, day: date, count: int) -> tuple[str, ...] | None:
    """The ``count`` SSE sessions to ``day``, as the calendar states them; None when it does
    not reach back so far."""
    try:
        sessions = calendar.sessions_back(calendar.latest_on_or_before(day), count)
    except LookupError:
        return None
    return tuple(item.isoformat() for item in sessions)


def _price_consistency(
    repository: Any,
    rules: PriceRules,
    definitions: Mapping[str, MetricDefinition],
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
    stage: str | None,
    cores: Mapping[str, CorePrices] | None,
    span: tuple[str, ...] | None,
) -> tuple[dict[str, object], set[str]]:
    """The cores' price internal consistency over ``span``, with the breadth and the sleeves
    read in it; and the observations it read beside the cores' own."""
    used: set[str] = set()

    def held(metric_id: str, dimensions: Mapping[str, str]) -> list[MetricSeriesPoint]:
        """The usable points in ``span`` whose dimensions include ``dimensions``."""
        if metric_id not in definitions or span is None:
            return []
        return [
            point
            for point in repository.metric_series(
                metric_id,
                mode=as_of_mode,
                as_of=as_of,
                definition_version=definitions[metric_id].definition_version,
            )
            if _usable_point(point)
            and point.period_end in span
            and all(point.dimensions.get(key) == value for key, value in dimensions.items())
            and _numeric_value(point.selected_value) is not None
        ]

    breadth: dict[str, float] = {}
    for point in held(rules.breadth.metric_id, rules.breadth.dimensions):
        if span is not None and point.period_end == span[-1]:
            breadth[point.period_end] = float(point.selected_value)  # type: ignore[arg-type]
            used.add(str(point.selected_claim_id))
    sleeves: dict[str, dict[str, float]] = {}
    for point in held(rules.basket.metric_id, rules.basket.dimensions):
        sleeve = point.dimensions.get("sleeve")
        if sleeve in rules.basket.sleeves and span is not None and point.period_end != span[0]:
            sleeves.setdefault(sleeve, {})[point.period_end] = float(point.selected_value)  # type: ignore[arg-type]
            used.add(str(point.selected_claim_id))
    document = price_consistency_document(
        rules, stage=stage, cores=cores, span=span, breadth=breadth, sleeves=sleeves
    )
    return document, used


def _demand_reading(members: Sequence[MemberReading], name: str) -> dict[str, str | None] | None:
    """A member's momentum and run, when its every reading is known."""
    reading = next((item for item in members if item.member.name == name), None)
    if (
        reading is None
        or reading.evidence_status != "current"
        or not reading.points
        or reading.missing
    ):
        return None
    return {"momentum": reading.momentum, "run": reading.run}


def _signal_reading(main: MemberReading, name: str) -> SignalReading:
    """A key indicator's main member read as ``name``, when its every reading is known."""
    if main.evidence_status != "current":
        return SignalReading(None, (f"{main.member.label}:{main.evidence_status}",))
    if main.gaps():
        return SignalReading(None, main.gaps())
    value = getattr(main, name)
    return SignalReading(value, () if value is not None else (f"{main.member.label}:not_read",))


def _quadrant_document(
    indicator: Mapping[str, Any],
    members: Sequence[Member],
    rows_by_metric: Mapping[str, tuple[dict[str, object], ...]],
) -> dict[str, object]:
    """The inventory quadrant as the inventory dimension's conclusion, and a card of each
    of its lines' ``members``: whether the member's own evidence is there, as its rows
    show it whatever the other lines hold, apart from the relation the quadrant -- the one
    count -- bears (N07). Its reading is the quadrant month's."""
    readings = {item["name"]: item for item in indicator["members"][1:]}
    cards = []
    for member in members:
        shown, status = _shown(rows_by_metric[member.metric_id], member)
        reading = readings[member.name]
        cards.append(
            {
                "name": member.name,
                "label": member.label,
                "metric_id": member.metric_id,
                "line": member.line,
                "role": reading["role"],
                "availability": (
                    "available" if shown is not None and status == "current" else "unavailable"
                ),
                "evidence_status": status,
                "period": shown,
                "reading_period": reading["period"],
                "momentum": reading["momentum"],
                "consistency": reading["consistency"],
                "relation": indicator["relation"],
                "counted": False,
            }
        )
    main = indicator["members"][0]
    return {
        "quadrant": main["quadrant"],
        "unclassified_by": main["unclassified_by"],
        "relation": indicator["relation"],
        "statistical_period": indicator["statistical_period"],
        "cards": cards,
    }


def _registered_warrants(
    repository: Any,
    definition: MetricDefinition,
    rules: WarrantRules,
    adoptable: frozenset[str] | None,
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
    window: tuple[str | None, str],
) -> dict[str, object]:
    """The registered warrants in the evidence window, each symbol's warehouses summed by
    day: a symbol-day the family leaves out whole is not held, and one delivered in more
    than one unit is held in neither."""
    held: dict[str, dict[str, tuple[float, str, tuple[str, ...]]]] = {}
    for point in repository.metric_series(
        definition.metric_id,
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition.definition_version,
    ):
        value = _numeric_value(point.selected_value)
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if (
            point.dimensions.get("measure") != "registered_receipts"
            or not _usable_point(point)
            or value is None
            or claim is None
            or (adoptable is not None and claim.claim_id not in adoptable)
            or (window[0] is not None and point.period_end < window[0])
        ):
            continue
        symbol = point.dimensions["symbol"]
        total, unit, versions = held.setdefault(symbol, {}).get(
            point.period_end, (0.0, claim.unit, ())
        )
        held[symbol][point.period_end] = (
            total + value,
            unit if unit == claim.unit else "mixed",
            (*versions, claim.claim_id),
        )
    return registered_warrant_change(rules, held, window=window)


def _shown(rows: Sequence[dict[str, object]], member: Member) -> tuple[str | None, str]:
    """The newest period of the member's evidence rows as shown, its own or its stand-in's
    (a February of cumulative growth), and its status; with none, None and why."""
    shown = [
        row
        for row in rows
        if row.get("value") is not None
        and isinstance(row.get("period"), str)
        and (
            row.get("dimensions") == dict(member.dimensions)
            or any(
                row.get("dimensions") == dict(dimensions) and int(str(row["period"])[5:7]) == month
                for month, dimensions in member.stand_ins.items()
            )
        )
    ]
    row = max(shown, key=lambda item: str(item["period"]), default=None)
    if row is None:
        gap = next((row for row in rows if str(row["observation_id"]).startswith("gap:")), None)
        own = next(
            (item for item in rows if item.get("dimensions") == dict(member.dimensions)), None
        )
        return None, str((own or gap or {}).get("status") or "missing")
    return str(row["period"]), str(row["status"])


def _quadrant_readings(
    indicator: KeyIndicator,
    rows_by_metric: Mapping[str, tuple[dict[str, object], ...]],
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
) -> tuple[MemberReading, ...]:
    """The inventory quadrant at the newest month its three lines' main members all hold,
    then each line's members there (macro semantics ticket 08).

    That month is the earliest of the main members' newest shown: a line out sooner waits
    on the others, and one not holding it misses it -- never read at an older month in
    its place. Each member is read there and at the quadrant's month before, passing over
    a month a main member is never released for; each month grace reaches back is read as
    the lines stood then. Nothing before a member's declared months is read.
    """
    rule = indicator.quadrant
    assert rule is not None
    shown = {
        member.name: _shown(rows_by_metric[member.metric_id], member)
        for member in indicator.auxiliary
    }
    newest = [shown[name][0] for name in rule.mains.values()]
    month = min(item[:7] for item in newest if item is not None) if None not in newest else None
    by_name = {member.name: member for member in indicator.auxiliary}

    def read(member: Member, role: str, end: str | None) -> MemberReading:
        own, status = shown[member.name]
        if end is None or own is None:
            return MemberReading(member, role, status, (), (), None, indicator.lookback)
        oldest = month_back(own[:7], indicator.reach(member) - 1)
        held: list[tuple[str, float, str]] = []
        missing: list[str] = []
        for current in (rule.before(end), end):
            dimensions = member.stand_ins.get(int(current[5:7]), member.dimensions)
            point = (
                points(member.metric_id, dimensions).get(month_end(current))
                if current >= oldest
                else None
            )
            value = _numeric_value(point.selected_value) if point is not None else None
            if point is None or value is None or point.selected_claim_id is None:
                missing.append(current)
            else:
                held.append((month_end(current), value, point.selected_claim_id))
        return MemberReading(
            member, role, status, tuple(held), tuple(missing), None, indicator.lookback
        )

    def quadrant(end: str | None) -> QuadrantReading:
        lines = {line: read(by_name[name], "line", end) for line, name in rule.mains.items()}
        return QuadrantReading.of(indicator.main, end, lines, rule.quadrants)

    earlier: list[QuadrantReading] = []
    end = month
    for _ in range(indicator.history(indicator.main)):
        end = rule.before(end) if end is not None else None
        earlier.append(quadrant(end))
    lines = set(rule.mains.values())
    return (
        replace(quadrant(month), earlier=tuple(earlier)),
        *(
            read(member, "line" if member.name in lines else "auxiliary", month)
            for member in indicator.auxiliary
        ),
    )


def _period_reading(
    indicator: KeyIndicator,
    member: Member,
    role: str,
    status: str,
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
    end: str,
    span: tuple[int, int, str],
    level_line: float | None,
) -> MemberReading:
    """``member``'s ``span`` -- its periods, the months a period spans and the oldest month
    read -- to ``end``; with the change its source states of each period held beside it.

    That change is read newest back to the first period it is not stated for, which is
    missing (ticket 07).
    """
    months, step, oldest = span
    held, missing = _member_window(points, member, end, months, step, oldest)
    if member.change_from is None:
        return MemberReading(
            member,
            role,
            status,
            held,
            missing,
            level_line,
            months,
            year=indicator.year,
            marked=indicator.marked,
        )
    stated = points(member.metric_id, member.change_from)
    by_period = {
        period: (value, str(point.selected_claim_id))
        for period, _value, _version in held
        if (point := stated.get(period)) is not None
        and point.selected_claim_id is not None
        and (value := _numeric_value(point.selected_value)) is not None
    }
    gaps = tuple(period[:7] for period, _value, _version in held if period not in by_period)
    changes: list[tuple[float, str]] = []
    for period, _value, _version in reversed(held):
        if period not in by_period:
            break
        changes.insert(0, by_period[period])
    return ChangeReading(
        member,
        role,
        status,
        held,
        tuple(sorted({*missing, *gaps})),
        level_line,
        months,
        tuple(dict.fromkeys([*(version for _p, _v, version in held), *(v for _c, v in changes)])),
        year=indicator.year,
        marked=indicator.marked,
        changes=tuple(change for change, _version in changes),
        change_gaps=gaps,
    )


def _observed_reading(metric_id: str, rows: Sequence[dict[str, object]]) -> ObservedReading:
    """A derived observation's newest row as shown, with the direction its formula states."""
    member = Member(metric_id.lower(), metric_id, metric_id, {})
    row = next((item for item in rows if item.get("value") is not None), None)
    value = _numeric_value(row.get("value")) if row is not None else None
    if row is None or value is None:
        status = str((next(iter(rows), {})).get("status") or "missing")
        return ObservedReading(member, "observed", status, (), (), None, 1)
    direction = row.get("direction")
    return ObservedReading(
        member,
        "observed",
        str(row.get("status")),
        ((str(row.get("period")), value, str(row.get("selected_claim_id"))),),
        (),
        None,
        1,
        stated=str(direction) if direction in {"up", "down", "flat"} else None,
    )


def _derived_reading(
    indicator: KeyIndicator,
    member: Member,
    role: str,
    main: MemberReading | None,
    rows_by_metric: Mapping[str, tuple[dict[str, object], ...]],
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
    *,
    day: date,
    calendar: TradingCalendar,
) -> MemberReading:
    """A derived member at the main member's newest month, or, as the main member, at its
    first input's newest month shown or the newest due by ``day``, whichever is later: a
    month due and not held is missing, never passed over for the one before. Each month
    grace reads back is read as it stood.

    No input before the horizon is read: a month needing one is missing that one.
    """
    definition = DERIVED_FORMULAS[str(member.formula)]
    months = indicator.periods(member)
    first = definition.inputs[0]
    own = first.dimensions if first.dimensions is not None else member.dimensions
    if main is not None:
        newest = main.points[-1][0][:7] if main.points else None
        status = "current" if newest is not None else "missing"
    else:
        rows = [
            row
            for row in rows_by_metric[first.metric_id]
            if row.get("dimensions") == dict(own) and isinstance(row.get("period"), str)
        ]
        shown = [row for row in rows if row.get("value") is not None]
        row = max(shown, key=lambda item: str(item["period"]), default=None)
        status = str((row or next(iter(rows), {})).get("status") or "missing")
        due = freshness_assess(
            first.metric_id,
            None,
            datetime.combine(day, time.max, tzinfo=ZoneInfo("Asia/Shanghai")),
            calendar,
        ).due_period
        held = [str(row["period"])[:7]] if row is not None else []
        newest = max([*held, *([due[:7]] if due else [])], default=None)
    level_line = indicator.level_line
    if newest is None:
        return MemberReading(member, role, status, (), (), level_line, months)
    oldest = month_back(newest, indicator.horizon)

    def input_value(item: DerivedInput, month: str) -> tuple[float, str] | None:
        dimensions = item.dimensions if item.dimensions is not None else member.dimensions
        point = points(item.metric_id, dimensions).get(month_end(month))
        number = _numeric_value(point.selected_value) if point is not None else None
        if point is None or number is None or point.selected_claim_id is None:
            return None
        return number, point.selected_claim_id

    def window(end: str, *, aligned: bool) -> MemberReading:
        span = [month_back(end, offset) for offset in reversed(range(months))]
        derived, gaps, inputs = derived_points(
            str(member.formula), span, input_value, oldest=oldest
        )
        held = status if not aligned or (derived and derived[-1][0][:7] == end) else "missing"
        return MemberReading(member, role, held, derived, gaps, level_line, months, inputs)

    if main is not None:
        # An auxiliary derived member's month is the main member's, held or missing.
        return window(newest, aligned=True)
    earlier = tuple(
        window(month_back(newest, back), aligned=False)
        for back in range(1, indicator.history(member) + 1)
    )
    return replace(window(newest, aligned=False), earlier=earlier)


def _roles(indicator: KeyIndicator) -> tuple[tuple[str, Member], ...]:
    return (("main", indicator.main), *(("auxiliary", item) for item in indicator.auxiliary))


def _member_status(rows: tuple[dict[str, object], ...], member: Member) -> str:
    """The member's evidence status as shown: current when each of its rows is (an RRR's
    every scope), or when the events traced show none in the window."""
    own = [row for row in rows if member.matches(_string_dimensions(row.get("dimensions")))]
    if own:
        return next(
            (str(row.get("status")) for row in own if row.get("status") != "current"), "current"
        )
    gap = next((row for row in rows if str(row["observation_id"]).startswith("gap:")), None)
    if gap is not None and gap.get("status") == "no_event_in_visible_window":
        return "current"
    return str((gap or {}).get("status") or "missing")


def _action_status(rows: tuple[dict[str, object], ...], member: Member, database: Path) -> str:
    """The member's status as shown; the LPR fixed last stays in force while this month's
    is awaited, as a rate held does until changed. An event the run traced back to the
    source's end, none found, holds nothing and owes nothing (ADR-0028)."""
    status = _member_status(rows, member)
    run_id = current_batch_id()
    if (
        status == "missing"
        and run_id is not None
        and backtracked(database, run_id).get(member.metric_id) == "none_found"
    ):
        return "current"
    return "current" if status == "awaiting_release" else status


def _action_reading(
    indicator: KeyIndicator,
    member: Member,
    role: str,
    held: Sequence[MetricSeriesPoint],
    status: str,
    *,
    day: date,
    window_start: str | None,
    released: Sequence[MetricSeriesPoint],
    monthly: bool,
    calendar: TradingCalendar,
    notices: set[str] | None,
) -> ActionReading:
    """``member``'s actions in the evidence window from ``window_start`` to ``day``.

    A rate's each change from the value in force before it, from the one in force before
    the window on (its baseline, which a reading needs: a value read on the window's first
    day may be a change from it); an RRR event's own change, with the funds released that
    day. A rate's history is whole or nothing is said of it: a fixing each month from the
    baseline's to the newest due (the LPR, dated the day it was published), or a notice
    each session from the one before the window (the policy rate: the days of
    ``notices``, or of its own values) -- a gap may hide a cut and a hike. Grace reads each
    month back as it stood at its end, within the same window.
    """
    points = tuple(
        sorted(
            (_action_day(point, monthly), float(point.selected_value), point.selected_claim_id)
            for point in held
            if point.selected_value is not None and point.selected_claim_id is not None
        )
    )
    if window_start is None:
        return ActionReading(
            member, role, status, points, ("evidence_window_unknown",), None, indicator.lookback
        )
    before = [point for point in points if point[0] < window_start]
    baseline = before[-1] if before else None
    inside = tuple(point for point in points if point[0] >= window_start)
    gaps: list[str] = []
    if indicator.actions == "level" and monthly:
        months = {point.period_end[:7] for point in held}
        due = freshness_assess(
            member.metric_id,
            None,
            datetime.combine(day, time.max, tzinfo=ZoneInfo("Asia/Shanghai")),
            calendar,
        ).due_period
        if baseline is None:
            gaps.append(f"baseline_before:{window_start}")
        else:
            month = baseline[0][:7]
            while month < max([*months, (due or "")[:7]]):
                month = month_back(month, -1)
                if month not in months:
                    gaps.append(month)
    elif indicator.actions == "level":
        try:
            # The window's sessions, and the one before them.
            first = calendar.sessions_from(date.fromisoformat(window_start), day)
            sessions = [
                session.isoformat()
                for session in (*calendar.sessions_back(first[0], 2)[:1], *first)
            ]
        except (LookupError, IndexError):
            sessions = []
            gaps.append("trading_calendar_incomplete")
        if sessions:
            noticed = notices if notices is not None else {point[0] for point in points}
            # The rate in force on the session before the window, its notice read.
            baseline = next((point for point in reversed(before) if point[0] <= sessions[0]), None)
            if baseline is None:
                gaps.append(f"baseline_before:{window_start}")
            gaps.extend(_ranges([item for item in sessions if item not in noticed], sessions))
    funds: dict[str, float] = {}
    for point in released:
        if point.selected_value is not None and point.period_end >= window_start:
            funds[point.period_end] = funds.get(point.period_end, 0.0) + float(point.selected_value)

    def read(until: str) -> ActionReading:
        shown = [point for point in inside if point[0] <= until]
        actions: list[Action] = []
        if indicator.actions == "change":
            by_day: dict[str, list[float]] = {}
            for period, value, _version in shown:
                by_day.setdefault(period, []).append(value)
            for period, changes in sorted(by_day.items()):
                # One change a day, whichever institutions' scopes state it.
                change = max(changes, key=abs)
                if change != 0:
                    actions.append(
                        Action(period, "cut" if change < 0 else "hike", change, funds.get(period))
                    )
        else:
            previous = baseline[1] if baseline is not None else None
            for period, value, _version in shown:
                if previous is not None and value != previous:
                    actions.append(
                        Action(period, "cut" if value < previous else "hike", value - previous)
                    )
                previous = value
        return ActionReading(
            member,
            role,
            status,
            ((baseline,) if baseline is not None else ()) + tuple(shown),
            tuple(gaps),
            None,
            indicator.lookback,
            actions=tuple(actions),
            baseline=baseline,
            window_start=window_start,
        )

    # Each month grace reads back, as it stood at the month's end.
    earlier = tuple(
        read(month_end(month_back(f"{day:%Y-%m}", back)))
        for back in range(1, indicator.history(member) + 1)
    )
    return replace(read(day.isoformat()), earlier=earlier)


def _action_day(point: MetricSeriesPoint, monthly: bool) -> str:
    """The day an action took effect: a monthly fixing's the day it was published."""
    claim = _selected_claim(point)
    if not monthly or claim is None:
        return point.period_end
    published: datetime = claim.public_available_at or claim.available_at
    return published.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _ranges(days: Sequence[str], order: Sequence[str]) -> list[str]:
    """``days`` with each run of neighbours in ``order`` told as its first and last."""
    runs: list[list[str]] = []
    places = {item: index for index, item in enumerate(order)}
    for item in days:
        if runs and places.get(item) == places.get(runs[-1][-1], -2) + 1:
            runs[-1].append(item)
        else:
            runs.append([item])
    return [run[0] if len(run) == 1 else f"{run[0]}..{run[-1]}" for run in runs]


def _block_reading(
    indicator: KeyIndicator,
    member: Member,
    role: str,
    rows_by_metric: Mapping[str, tuple[dict[str, object], ...]],
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
    matching: Callable[[Member], list[MetricSeriesPoint]],
    *,
    day: date,
    calendar: TradingCalendar,
) -> BlockReading:
    """``member`` in periods of the indicator's sessions to ``day``, oldest first.

    A session's value is held or not: never a session not held read as nothing (N14). A
    period of a session not held is missing, with the days, and ends the run; each period
    grace reads back is read too, a period of sessions earlier each. With no calendar
    stating the sessions, none is read.
    """
    size = indicator.period_sessions
    assert size is not None
    formula = SESSION_FORMULAS.get(member.session_formula or "")
    count = indicator.reach(member) * size + (formula.lead_sessions if formula else 0)
    source = (
        Member(member.name, member.label, formula.metric_id, formula.dimensions)
        if formula is not None
        else member
    )
    status = _member_status(rows_by_metric[source.metric_id], source)
    # The periods its readings take, before those grace reads back.
    taken = indicator.periods(member)
    try:
        sessions = calendar.sessions_back(calendar.latest_on_or_before(day), count)
    except LookupError:
        return BlockReading(
            member,
            role,
            "trading_calendar_incomplete",
            (),
            (),
            indicator.level_line,
            taken,
            year=indicator.year,
            marked=indicator.marked,
            sessions=size,
        )
    days = [session.isoformat() for session in sessions]
    if formula is not None:
        values = _net_injections(points, days[formula.lead_sessions :], days)
    else:
        held = {
            point.period_end: point
            for point in matching(member)
            if point.selected_value is not None and point.selected_claim_id is not None
        }
        values = {
            session: (
                (float(held[session].selected_value), (str(held[session].selected_claim_id),))  # type: ignore[arg-type]
                if session in held
                else (None, (session,))
            )
            for session in days
        }
    read = days[len(days) - indicator.reach(member) * size :]
    line = matching(indicator.line) if indicator.line is not None else []

    def window(back: int) -> BlockReading:
        """The member as it stood ``back`` periods before the newest."""
        kept: list[tuple[str, float, str]] = []
        starts: list[str] = []
        missing: list[str] = []
        inputs: list[str] = []
        for period in range(taken):
            end = len(read) - (back + period) * size
            if end - size < 0:
                break
            block = read[end - size : end]
            gaps = [
                gap for session in block if values[session][0] is None for gap in values[session][1]
            ]
            if gaps:
                missing.extend(gaps)
            elif not missing:
                numbers = [values[session][0] for session in block]
                total = sum(number for number in numbers if number is not None)
                kept.insert(
                    0, (block[-1], total / size if member.aggregate == "mean" else total, "")
                )
                starts.insert(0, block[0])
                inputs.extend(item for session in block for item in values[session][1])
        lines = tuple(_in_force(line, period) for period, _value, _version in kept)
        return BlockReading(
            member,
            role,
            status,
            tuple(kept),
            # A run of sessions not held is told by its first and last.
            tuple(_ranges(sorted(set(missing)), days)),
            indicator.level_line,
            taken,
            tuple(dict.fromkeys(inputs)),
            year=indicator.year,
            marked=indicator.marked,
            sessions=size,
            lines=lines if indicator.line is not None else (),
            starts=tuple(starts),
        )

    earlier = tuple(window(back) for back in range(1, indicator.history(member) + 1))
    return replace(window(0), earlier=earlier)


def _in_force(points: Sequence[MetricSeriesPoint], day: str) -> float | None:
    """The value in force on ``day``: the latest held on or before it."""
    held = [
        point for point in points if point.period_end <= day and point.selected_value is not None
    ]
    return float(held[-1].selected_value) if held else None  # type: ignore[arg-type]


def _net_injections(
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
    sessions: Sequence[str],
    days: Sequence[str],
) -> dict[str, tuple[float | None, tuple[str, ...]]]:
    """The seven-day reverse repo's net injection on each of ``sessions``, and what it rests
    on; or None and the days whose injection is not held.

    Put in: the injections since the session before. Matured: what the session's notice
    reports, else each injection seven days on rolled to the next session -- every session
    it could come from held, its value zero when the notice says nothing was done, never
    when there is no notice (N14). ``days`` are the sessions read, the lead before
    ``sessions`` among them. A notice is owed on each SSE session, the calendar China's
    periods are told by; one of a make-up working day, held, counts with the next session,
    and one not held is not told apart from none.
    """
    injections = points("CN_OMO_7D_AMOUNT", {"measure": "injection"})
    reported = points("CN_OMO_7D_AMOUNT", {"measure": "maturity"})

    def amount(point: MetricSeriesPoint) -> float:
        return float(point.selected_value)  # type: ignore[arg-type]

    def between(first: date, last: date) -> list[MetricSeriesPoint]:
        """The injections put in after ``first`` up to ``last``."""
        return [
            point
            for period, point in injections.items()
            if first < date.fromisoformat(period) <= last
            and point.selected_value is not None
            and point.selected_claim_id is not None
        ]

    net: dict[str, tuple[float | None, tuple[str, ...]]] = {}
    for session in sessions:
        current = date.fromisoformat(session)
        before = date.fromisoformat(days[days.index(session) - 1])
        # The sessions an injection maturing here, or put in here, was put in on.
        due = (before - timedelta(days=7), current - timedelta(days=7))
        needed = [
            day for day in days if due[0] < date.fromisoformat(day) <= due[1] or day == session
        ]
        gaps = [day for day in needed if day not in injections]
        if due[0] < date.fromisoformat(days[0]) and session not in reported:
            # What matures here may have been put in before the sessions read.
            gaps.append(f"before:{days[0]}")
        maturity_point = reported.get(session)
        if maturity_point is not None:
            gaps = [day for day in gaps if day == session]
        if gaps:
            net[session] = (None, tuple(gaps))
            continue
        put_in = between(before, current)
        matured = [maturity_point] if maturity_point is not None else between(*due)
        net[session] = (
            sum(amount(point) for point in put_in) - sum(amount(point) for point in matured),
            tuple(str(point.selected_claim_id) for point in (*put_in, *matured)),
        )
    return net


def _member_window(
    points: Callable[[str, Mapping[str, str]], Mapping[str, MetricSeriesPoint]],
    member: Member,
    end: str,
    months: int,
    step: int,
    oldest: str,
) -> tuple[tuple[tuple[str, float, str], ...], tuple[str, ...]]:
    """``member``'s ``months`` periods to ``end``: those held to the first missing, and those
    missing (``YYYY-MM``); none before ``oldest`` is read."""
    held: list[tuple[str, float, str]] = []
    missing: list[str] = []
    for offset in range(months):
        month = month_back(end, offset * step)
        number = int(month[5:7])
        if number in member.unreleased_months:
            continue
        point = (
            points(member.metric_id, member.stand_ins.get(number, member.dimensions)).get(
                month_end(month)
            )
            if month >= oldest
            else None
        )
        value = _numeric_value(point.selected_value) if point is not None else None
        if point is None or value is None or point.selected_claim_id is None:
            missing.append(month)
        elif not missing:
            held.insert(0, (month_end(month), value, point.selected_claim_id))
    return tuple(held), tuple(reversed(missing))


def _adoptable_claims(
    repository: Any,
    points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]],
    *,
    definition_version: str,
) -> frozenset[str] | None:
    """The selected claims that pass their family recheck, or None when none ran."""
    adoption = ClaimAdoption(repository, definition_version=definition_version).check(
        points_by_metric
    )
    if not any(adoption[metric_id].rechecked for metric_id in points_by_metric):
        return None
    return frozenset().union(*(adoption.adoptable(metric_id) for metric_id in points_by_metric))


class TargetBoundEvidenceRepository:
    """Delegate evidence access while enforcing one historical period boundary.

    What the day knows of is ``cutoff``'s rule, the day's end by default (a backfilled
    day's); a target day's summary passes the run's cutoff.
    """

    def __init__(
        self,
        repository: Any,
        target_date: date,
        frequencies: Mapping[str, str],
        *,
        visible_start: date | None = None,
        allow_system_at_target: bool = False,
        cutoff: SummaryCutoff | None = None,
    ) -> None:
        self._repository = repository
        self._target_date = target_date
        self._frequencies = frequencies
        self._visible_start = visible_start
        self._allow_system_at_target = allow_system_at_target
        self._cutoff = cutoff or SummaryCutoff.at_day_end(target_date)
        if self._cutoff.day != target_date:
            raise ValueError("target_bound_cutoff_day_mismatch")

    def metric_series(self, *args: Any, **kwargs: Any) -> tuple[MetricSeriesPoint, ...]:
        tolerance = kwargs.get("tolerance")
        points = self._known(args, kwargs)
        metric_id = args[0] if args else kwargs.get("metric_id")
        if metric_id == "CN_RRR_EVENT":
            points = _official_days_whole(points, tolerance=tolerance)
        if self._visible_start is None:
            return points
        # A metric in force until changed shows each member's latest value however old:
        # it is the current baseline (ADR-0028).
        baselines = (
            {
                json.dumps(point.dimensions, sort_keys=True): point
                for point in sorted(points, key=lambda point: point.period_end)
            }
            if metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS
            else {}
        )
        return tuple(
            point
            for point in points
            if date.fromisoformat(point.period_end) >= self._visible_start
            or point in baselines.values()
        )

    def latest_before_window(self, *args: Any, **kwargs: Any) -> dict[str, MetricSeriesPoint]:
        """Each member's latest point before the visible window, to compare the first with.

        A comparison, never a row: the window shown stays where it is (ticket 30).
        """
        if self._visible_start is None:
            return {}
        before: dict[str, MetricSeriesPoint] = {}
        for bounded in self._known(args, kwargs):
            if date.fromisoformat(bounded.period_end) < self._visible_start:
                before[json.dumps(bounded.dimensions, sort_keys=True)] = bounded
        return before

    @property
    def target_date(self) -> date:
        return self._target_date

    def has_target_history(self, *args: Any, **kwargs: Any) -> bool:
        return any(_usable_point(point) for point in self._known(args, kwargs))

    def _known(
        self, args: tuple[Any, ...], kwargs: Mapping[str, Any]
    ) -> tuple[MetricSeriesPoint, ...]:
        """The series as the cutoff knows it, each point among its claims known by then.

        Past the day's end, a period still running on the day is read as it stood by the
        day's end: the repository folds a provider's later revision over the claim it
        revises, and the revision is not the day's to know (ADR-0041 2026-10-13).
        """
        query_kwargs = self._query_at_target(kwargs)
        use_system = query_kwargs["system_known_by"] is not None
        points = self._repository.metric_series(*args, **query_kwargs)
        cutoff = self._cutoff
        if cutoff.public_as_of > cutoff.day_end and not isinstance(
            self._repository, TargetBoundEvidenceRepository
        ):
            day = cutoff.day.isoformat()

            def key(point: MetricSeriesPoint) -> tuple[str, str, str]:
                return (
                    point.period_start,
                    point.period_end,
                    json.dumps(point.dimensions, sort_keys=True),
                )

            at_day_end = {
                key(point): point
                for point in self._repository.metric_series(
                    *args, **{**query_kwargs, "public_as_of": cutoff.day_end}
                )
                if point.period_end > day
            }
            points = tuple(
                point if point.period_end <= day else at_day_end.get(key(point)) for point in points
            )
        return tuple(
            bounded
            for point in points
            if point is not None
            and (
                bounded := _point_at_target(
                    point,
                    cutoff,
                    tolerance=kwargs.get("tolerance"),
                    allow_system_at_target=use_system,
                )
            )
            is not None
        )

    def _query_at_target(self, kwargs: Mapping[str, Any]) -> dict[str, Any]:
        """The repository query, its bounds those ``_point_at_target`` reads claims by: what
        is public by the cutoff, and with ``dual-cutoff-v0003`` what was held by the day's
        end. Both apply before a provider's revisions are chosen among."""
        query_kwargs = dict(kwargs)
        query_kwargs["public_as_of"] = self._cutoff.public_as_of
        query_kwargs["system_known_by"] = (
            self._cutoff.day_end
            if self._allow_system_at_target and kwargs["mode"] is AsOfMode.SYSTEM
            else None
        )
        return query_kwargs

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)


def _official_days_whole(
    points: tuple[MetricSeriesPoint, ...], *, tolerance: float | None
) -> tuple[MetricSeriesPoint, ...]:
    """On a day an official notice states the RRR, every member is read from the notice.

    News may state only some of a day's members; chosen member by member, they would split
    the notice, which must keep all it published (ADR-0028). A member the notice does not
    state is then left out of that day.
    """
    from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES

    provider = OFFICIAL_CONTEXT_FAMILIES["pbc_rrr_notice"].provider
    official_days = {
        point.period_end
        for point in points
        if any(claim.provider == provider for claim in point.claims)
    }
    kept = []
    for point in points:
        if point.period_end not in official_days:
            kept.append(point)
            continue
        claims = tuple(c for c in point.claims if c.provider == provider)
        if claims:
            kept.append(_selected_among(point, claims, tolerance=tolerance))
    return tuple(kept)


def _point_at_target(
    point: MetricSeriesPoint,
    cutoff: SummaryCutoff,
    *,
    tolerance: float | None,
    allow_system_at_target: bool = False,
) -> MetricSeriesPoint | None:
    """``point`` as ``cutoff`` knows it: among its claims public by then, of its period.

    A model that allows it (``dual-cutoff-v0003``) may know a claim by its system time
    instead, and only by the day's end.
    """
    if date.fromisoformat(point.period_start) > cutoff.day:
        return None
    period_end = date.fromisoformat(point.period_end)
    claims = tuple(
        claim
        for claim in point.claims
        if cutoff.knows(period_end, claim.public_available_at)
        or (allow_system_at_target and claim.available_at <= cutoff.day_end)
    )
    if not claims:
        return None
    return _selected_among(point, claims, tolerance=tolerance)


def _selected_among(
    point: MetricSeriesPoint, claims: tuple[ClaimView, ...], *, tolerance: float | None
) -> MetricSeriesPoint:
    # The target day selects as the repository does, among the claims public by then, with
    # the recheck verdicts on them (ADR-0039).
    selected, reason = select_among(claims, tolerance=tolerance, verdicts=point.verdicts)
    return MetricSeriesPoint(
        observation_id=point.observation_id,
        period_start=point.period_start,
        period_end=point.period_end,
        dimensions=point.dimensions,
        selected_value=selected.value,
        value_state=selected.value_state,
        selection_status="conflicted" if reason is not None else "selected",
        selected_claim_id=selected.claim_id,
        claims=claims,
        conflict_reason=reason,
        verdicts=point.verdicts,
    )


def _derived_market_context_rows(
    repository: EvidenceRepository,
    *,
    visible_start: date | None,
    as_of: datetime,
    formula_versions: Mapping[str, str],
    definition_version: str,
    trading_calendar_metric_id: str | None,
    as_of_mode: AsOfMode,
    persist_derived: bool,
) -> tuple[dict[str, tuple[dict[str, object], ...]], tuple[str, ...]]:
    """Each derived row of the day; its inputs may precede the window, as a formula's
    lookback does, but a row whose period ended before ``visible_start`` is none of the
    window's: its metric shows the window's own rows, its gap when it has none (ticket 08)."""

    def in_window(period_end: str) -> bool:
        return visible_start is None or date.fromisoformat(period_end) >= visible_start

    rows: dict[str, tuple[dict[str, object], ...]] = {}
    version_ids: list[str] = []
    reported_amount_points = repository.metric_series(
        "CN_OMO_7D_AMOUNT",
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition_version,
    )
    valid_amount_claim_ids = _adoptable_claims(
        repository,
        {"CN_OMO_7D_AMOUNT": reported_amount_points},
        definition_version=definition_version,
    )
    amount_points = [
        point
        for point in reported_amount_points
        if _usable_point(point)
        and (valid_amount_claim_ids is None or point.selected_claim_id in valid_amount_claim_ids)
    ]
    invalid_amount_points = [
        point
        for point in reported_amount_points
        if point.dimensions.get("measure") in {"injection", "maturity"}
        and (
            not _usable_point(point)
            or (
                valid_amount_claim_ids is not None
                and point.selected_claim_id not in valid_amount_claim_ids
            )
        )
    ]
    invalid_amount_periods = {point.period_end for point in invalid_amount_points}
    amount_by_period: dict[str, dict[str, MetricSeriesPoint]] = {}
    for point in amount_points:
        measure = point.dimensions.get("measure")
        if measure in {"injection", "maturity"}:
            amount_by_period.setdefault(point.period_end, {})[measure] = point
    omo_formula = formula_versions.get("omo_net_injection")
    injection_points = [
        point for point in amount_points if point.dimensions.get("measure") == "injection"
    ]
    complete_periods = [
        period
        for period, measures in amount_by_period.items()
        if set(measures) == {"injection", "maturity"}
    ]
    if (
        complete_periods
        and omo_formula == REPO_SAME_DAY_FORMULA
        and in_window(max(complete_periods))
    ):
        period = max(complete_periods)
        measures = amount_by_period[period]
        derived_row, derived_versions = _difference_row(
            repository,
            metric_id="CN_OMO_7D_AMOUNT",
            formula_version=omo_formula,
            left=measures["injection"],
            right=measures["maturity"],
            multiplier=1.0,
            dimensions={"measure": "net_injection"},
            unit="hundred_million_cny",
            as_of=as_of,
            as_of_mode=as_of_mode,
            persist_derived=persist_derived,
        )
        rows["CN_OMO_7D_AMOUNT"] = (derived_row,)
        version_ids.extend(derived_versions)
    elif amount_by_period and omo_formula == REPO_CALENDAR_FORMULA:
        trading_day_points = (
            _trading_day_candidates(
                repository,
                trading_calendar_metric_id,
                as_of=as_of,
                as_of_mode=as_of_mode,
                definition_version=definition_version,
            )
            if trading_calendar_metric_id is not None
            else ()
        )
        trading_days = tuple(date.fromisoformat(point.period_end) for point in trading_day_points)
        trading_points_by_day = {
            date.fromisoformat(point.period_end): point for point in trading_day_points
        }
        derived_maturities: dict[date, list[MetricSeriesPoint]] = {}
        for point in injection_points:
            maturity_day = repo_maturity_trading_day(
                date.fromisoformat(point.period_end),
                trading_days,
            )
            if maturity_day is not None:
                derived_maturities.setdefault(maturity_day, []).append(point)
        invalid_maturity_dates = {
            maturity_day
            for point in invalid_amount_points
            if point.dimensions.get("measure") == "injection"
            and (
                maturity_day := repo_maturity_trading_day(
                    date.fromisoformat(point.period_end), trading_days
                )
            )
            is not None
        }
        target_dates = (
            {
                date.fromisoformat(point.period_end)
                for point in reported_amount_points
                if point.dimensions.get("measure") in {"injection", "maturity"}
            }
            | set(derived_maturities)
            | invalid_maturity_dates
        )
        target_date = max(target_dates)
        target_period = target_date.isoformat()
        injection = amount_by_period.get(target_period, {}).get("injection")
        explicit_maturity = amount_by_period.get(target_period, {}).get("maturity")
        maturity_points: tuple[MetricSeriesPoint, ...] = ()
        calendar_points: tuple[MetricSeriesPoint, ...] = ()
        maturity_basis: str | None = None
        if explicit_maturity is not None:
            maturity_points = (explicit_maturity,)
            maturity_basis = "reported_source"
        elif target_date in trading_days:
            maturity_points = tuple(derived_maturities.get(target_date, ()))
            calendar_points = (trading_points_by_day[target_date],)
            maturity_basis = "derived_7d_trading_calendar"
        invalid_maturity_inputs = (
            maturity_basis == "derived_7d_trading_calendar"
            and target_date in invalid_maturity_dates
        )
        calendar_valid = True
        # Sessions come only from the core the calendar metric names.
        if calendar_points and trading_calendar_metric_id is not None:
            calendar_claims = _adoptable_claims(
                repository,
                {trading_calendar_metric_id: tuple(calendar_points)},
                definition_version=definition_version,
            )
            calendar_valid = calendar_claims is None or all(
                point.selected_claim_id in calendar_claims for point in calendar_points
            )
        if (
            maturity_basis is not None
            and (injection is not None or maturity_points)
            and target_period not in invalid_amount_periods
            and not invalid_maturity_inputs
            and calendar_valid
            and in_window(target_period)
        ):
            derived_row, derived_versions = _repo_net_injection_row(
                repository,
                formula_version=omo_formula,
                injection=injection,
                maturity_points=maturity_points,
                calendar_points=calendar_points,
                maturity_basis=maturity_basis,
                target_period=target_period,
                as_of=as_of,
                as_of_mode=as_of_mode,
                persist_derived=persist_derived,
            )
            rows["CN_OMO_7D_AMOUNT"] = (derived_row,)
            version_ids.extend(derived_versions)

    dr007 = _latest_usable_point(
        repository,
        "CN_DR007",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    if (
        dr007 is not None
        and (
            valid := _adoptable_claims(
                repository, {"CN_DR007": (dr007,)}, definition_version=definition_version
            )
        )
        is not None
        and dr007.selected_claim_id not in valid
    ):
        dr007 = None
    policy_rate = _latest_usable_point(
        repository,
        "CN_OMO_7D_RATE",
        as_of=as_of,
        no_later_than=dr007.period_end if dr007 is not None else None,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    if (
        policy_rate is not None
        and (
            valid := _adoptable_claims(
                repository,
                {"CN_OMO_7D_RATE": (policy_rate,)},
                definition_version=definition_version,
            )
        )
        is not None
        and policy_rate.selected_claim_id not in valid
    ):
        policy_rate = None
    dr007_formula = formula_versions.get("dr007_policy_spread")
    if (
        dr007 is not None
        and policy_rate is not None
        and dr007_formula is not None
        and in_window(dr007.period_end)
    ):
        derived_row, derived_versions = _difference_row(
            repository,
            metric_id="CN_DR007_POLICY_SPREAD",
            formula_version=dr007_formula,
            left=dr007,
            right=policy_rate,
            multiplier=100.0,
            dimensions={},
            unit="basis_points",
            as_of=as_of,
            as_of_mode=as_of_mode,
            persist_derived=persist_derived,
        )
        rows["CN_DR007_POLICY_SPREAD"] = (derived_row,)
        version_ids.extend(derived_versions)

    ust2 = _usable_points_by_period(
        repository,
        "UST2Y_NOMINAL_YIELD",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    ust10 = _usable_points_by_period(
        repository,
        "UST10Y_NOMINAL_YIELD",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    common_periods = set(ust2) & set(ust10)
    ust_formula = formula_versions.get("ust_2s10s_spread")
    if common_periods and ust_formula is not None and in_window(max(common_periods)):
        period = max(common_periods)
        derived_row, derived_versions = _difference_row(
            repository,
            metric_id="UST_2S10S_SPREAD",
            formula_version=ust_formula,
            left=ust10[period],
            right=ust2[period],
            multiplier=100.0,
            dimensions={},
            unit="basis_points",
            as_of=as_of,
            as_of_mode=as_of_mode,
            persist_derived=persist_derived,
        )
        rows["UST_2S10S_SPREAD"] = (derived_row,)
        version_ids.extend(derived_versions)

    pmi_new_orders = _usable_points_by_period(
        repository,
        "CN_PMI_ACTIVITY",
        as_of=as_of,
        dimensions={"series": "new_orders", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    pmi_production = _usable_points_by_period(
        repository,
        "CN_PMI_ACTIVITY",
        as_of=as_of,
        dimensions={"series": "production", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    pmi_finished_goods = _usable_points_by_period(
        repository,
        "CN_PMI_INVENTORY",
        as_of=as_of,
        dimensions={"series": "finished_goods", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    order_inventory_periods = set(pmi_new_orders) & set(pmi_finished_goods)
    order_formula = formula_versions.get("order_inventory_spread")
    if (
        order_inventory_periods
        and order_formula == "pmi-order-inventory-spread-v0001"
        and in_window(max(order_inventory_periods))
    ):
        period = max(order_inventory_periods)
        derived_row, derived_versions = _difference_row(
            repository,
            metric_id="CN_ORDER_INVENTORY_SPREAD",
            formula_version=order_formula,
            left=pmi_new_orders[period],
            right=pmi_finished_goods[period],
            multiplier=1.0,
            dimensions={},
            unit="diffusion_index_points",
            as_of=as_of,
            as_of_mode=as_of_mode,
            persist_derived=persist_derived,
        )
        rows["CN_ORDER_INVENTORY_SPREAD"] = (derived_row,)
        version_ids.extend(derived_versions)
    production_order_periods = set(pmi_production) & set(pmi_new_orders)
    production_formula = formula_versions.get("production_order_spread")
    if (
        production_order_periods
        and production_formula is not None
        and in_window(max(production_order_periods))
    ):
        period = max(production_order_periods)
        derived_row, derived_versions = _difference_row(
            repository,
            metric_id="CN_PRODUCTION_ORDER_SPREAD",
            formula_version=production_formula,
            left=pmi_production[period],
            right=pmi_new_orders[period],
            multiplier=1.0,
            dimensions={},
            unit="diffusion_index_points",
            as_of=as_of,
            as_of_mode=as_of_mode,
            persist_derived=persist_derived,
        )
        rows["CN_PRODUCTION_ORDER_SPREAD"] = (derived_row,)
        version_ids.extend(derived_versions)

    loan_formula = formula_versions.get("loan_monthly_change")
    loan_input_measure = "ytd_increment" if loan_formula == LOAN_YTD_FORMULA else "stock_end"
    loan_stock_points = [
        point
        for point in repository.metric_series(
            "CN_LOAN_STRUCTURE",
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if point.dimensions.get("measure") == loan_input_measure
        and (definition_version not in BUILTIN_CATALOG_VERSIONS or _usable_point(point))
    ]
    loan_groups: dict[tuple[str, str], list[MetricSeriesPoint]] = {}
    valid_loan_claim_ids = _adoptable_claims(
        repository,
        {"CN_LOAN_STRUCTURE": tuple(loan_stock_points)},
        definition_version=definition_version,
    )
    for point in loan_stock_points:
        key = (point.dimensions.get("borrower", ""), point.dimensions.get("tenor", ""))
        loan_groups.setdefault(key, []).append(point)
    loan_rows: list[dict[str, object]] = []
    if loan_formula is not None:
        for (borrower, tenor), points in sorted(loan_groups.items()):
            ordered = sorted(points, key=lambda point: point.period_end)
            current = ordered[-1]
            previous: MetricSeriesPoint | None
            if not in_window(current.period_end):
                continue
            if (
                loan_formula == LOAN_YTD_FORMULA
                and date.fromisoformat(current.period_end).month == 1
            ):
                previous = None
            elif len(ordered) < 2 or not _consecutive_months(ordered[-2], current):
                continue
            else:
                previous = ordered[-2]
            required_points = (current,) if previous is None else (current, previous)
            if valid_loan_claim_ids is not None and any(
                not _usable_point(point) or point.selected_claim_id not in valid_loan_claim_ids
                for point in required_points
            ):
                continue
            derived_row, derived_versions = _difference_row(
                repository,
                metric_id="CN_LOAN_STRUCTURE",
                formula_version=loan_formula,
                left=current,
                right=previous,
                multiplier=1.0,
                dimensions={
                    "borrower": borrower,
                    "tenor": tenor,
                    "measure": "monthly_change",
                },
                unit="hundred_million_cny",
                as_of=as_of,
                as_of_mode=as_of_mode,
                persist_derived=persist_derived,
            )
            loan_rows.append(derived_row)
            version_ids.extend(derived_versions)
    if loan_rows:
        rows["CN_LOAN_STRUCTURE"] = tuple(loan_rows)
    return rows, tuple(version_ids)


def _core_stock_metric_id(model_manifest: Mapping[str, object]) -> str | None:
    core_metrics = model_manifest.get("core_metrics")
    if not isinstance(core_metrics, Mapping):
        return None
    metric_id = core_metrics.get("stock")
    return metric_id if isinstance(metric_id, str) and metric_id else None


def _trading_day_candidates(
    repository: EvidenceRepository,
    metric_id: str,
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
    definition_version: str,
) -> tuple[MetricSeriesPoint, ...]:
    return tuple(
        sorted(
            (
                point
                for point in repository.metric_series(
                    metric_id,
                    mode=as_of_mode,
                    as_of=as_of,
                    definition_version=definition_version,
                )
                if definition_version not in BUILTIN_CATALOG_VERSIONS or _usable_point(point)
            ),
            key=lambda point: (point.period_end, point.observation_id),
        )
    )


def repo_maturity_trading_day(
    operation_date: date,
    trading_days: tuple[date, ...],
) -> date | None:
    """The session a seven-day repo put in on ``operation_date`` matures on: seven days on,
    rolled to the next of ``trading_days``."""
    nominal_maturity = operation_date + timedelta(days=7)
    return next((day for day in trading_days if day >= nominal_maturity), None)


def _repo_net_injection_row(
    repository: EvidenceRepository,
    *,
    formula_version: str,
    injection: MetricSeriesPoint | None,
    maturity_points: tuple[MetricSeriesPoint, ...],
    calendar_points: tuple[MetricSeriesPoint, ...],
    maturity_basis: str,
    target_period: str,
    as_of: datetime,
    as_of_mode: AsOfMode,
    persist_derived: bool,
) -> tuple[dict[str, object], tuple[str, ...]]:
    input_points = (
        *((injection,) if injection is not None else ()),
        *maturity_points,
        *calendar_points,
    )
    claims = tuple(_selected_claim(point) for point in input_points)
    if (
        (
            injection is not None
            and (injection.selected_value is None or injection.selected_claim_id is None)
        )
        or any(
            point.selected_value is None or point.selected_claim_id is None
            for point in maturity_points
        )
        or any(claim is None for claim in claims)
    ):
        raise ValueError("repo_net_injection_inputs_invalid")
    selected_claims = tuple(claim for claim in claims if claim is not None)
    inputs = tuple(
        sorted(
            point.selected_claim_id for point in input_points if point.selected_claim_id is not None
        )
    )
    maturity_amount = sum(
        float(point.selected_value) for point in maturity_points if point.selected_value is not None
    )
    injection_amount = (
        float(injection.selected_value)
        if injection is not None and injection.selected_value is not None
        else 0.0
    )
    value = injection_amount - maturity_amount
    unit = "hundred_million_cny"
    derived_id = _derived_observation_identity(
        repository,
        metric_id="CN_OMO_7D_AMOUNT",
        formula_version=formula_version,
        input_observation_version_ids=inputs,
        as_of_mode=as_of_mode,
        as_of_cutoff=as_of,
        value=value,
        unit=unit,
        persist=persist_derived,
    )
    public_times = tuple(
        claim.public_available_at
        for claim in selected_claims
        if claim.public_available_at is not None
    )
    row: dict[str, object] = {
        "available_at": max(claim.available_at for claim in selected_claims).isoformat(),
        "claim_ids": [],
        "claims": [],
        "derived_observation_id": derived_id,
        "dimensions": {"measure": "net_injection"},
        "direction": "up" if value > 0 else "down" if value < 0 else "flat",
        "formula_version": formula_version,
        "input_observation_version_ids": list(inputs),
        "maturity_amount": maturity_amount,
        "maturity_basis": maturity_basis,
        "trading_calendar_observation_version_ids": [
            point.selected_claim_id
            for point in calendar_points
            if point.selected_claim_id is not None
        ],
        "metric_id": "CN_OMO_7D_AMOUNT",
        "observation_id": derived_id,
        "period": target_period,
        "public_available_at": (
            max(public_times).isoformat()
            if public_times and len(public_times) == len(selected_claims)
            else None
        ),
        "quality_status": "validated",
        "selected_claim_id": derived_id,
        "semantic_field": "derived_repo_net_injection",
        "source_reference": f"formula:{formula_version}",
        "status": "current",
        "unit": unit,
        "value": value,
        "value_state": EvidenceValueState.REPORTED_VALUE.value,
    }
    return row, (*inputs, derived_id)


def _difference_row(
    repository: EvidenceRepository,
    *,
    metric_id: str,
    formula_version: str,
    left: MetricSeriesPoint,
    right: MetricSeriesPoint | None,
    multiplier: float,
    dimensions: dict[str, str],
    unit: str,
    as_of: datetime,
    as_of_mode: AsOfMode,
    persist_derived: bool,
) -> tuple[dict[str, object], tuple[str, ...]]:
    left_value = left.selected_value
    right_value = right.selected_value if right is not None else 0.0
    points = (left, right) if right is not None else (left,)
    claims = [_selected_claim(point) for point in points]
    if (
        left_value is None
        or right_value is None
        or any(claim is None for claim in claims)
        or any(point.selected_claim_id is None for point in points)
    ):
        raise ValueError("derived_difference_inputs_invalid")
    inputs = tuple(sorted(str(point.selected_claim_id) for point in points))
    value = (left_value - right_value) * multiplier
    derived_id = _derived_observation_identity(
        repository,
        metric_id=metric_id,
        formula_version=formula_version,
        input_observation_version_ids=inputs,
        as_of_mode=as_of_mode,
        as_of_cutoff=as_of,
        value=value,
        unit=unit,
        persist=persist_derived,
    )
    public_times = [
        claim.public_available_at for claim in claims if claim.public_available_at is not None
    ]
    public_available_at = max(public_times) if len(public_times) == len(claims) else None
    row: dict[str, object] = {
        "available_at": max(claim.available_at for claim in claims).isoformat(),
        "claim_ids": [],
        "claims": [],
        "derived_observation_id": derived_id,
        "dimensions": dimensions,
        "direction": "up" if value > 0 else "down" if value < 0 else "flat",
        "formula_version": formula_version,
        "input_observation_version_ids": list(inputs),
        "metric_id": metric_id,
        "observation_id": derived_id,
        "period": max(point.period_end for point in points),
        "public_available_at": (
            public_available_at.isoformat() if public_available_at is not None else None
        ),
        "quality_status": "validated",
        "selected_claim_id": derived_id,
        "source_reference": f"formula:{formula_version}",
        "status": "current",
        "unit": unit,
        "value": value,
        "value_state": EvidenceValueState.REPORTED_VALUE.value,
    }
    return row, (*inputs, derived_id)


def _derived_observation_identity(
    repository: EvidenceRepository,
    *,
    metric_id: str,
    formula_version: str,
    input_observation_version_ids: tuple[str, ...],
    as_of_mode: AsOfMode,
    as_of_cutoff: datetime,
    value: float | None,
    unit: str,
    persist: bool,
) -> str:
    inputs = tuple(sorted(input_observation_version_ids))
    if persist:
        return repository.append_derived_observation(
            metric_id=metric_id,
            formula_version=formula_version,
            input_observation_version_ids=inputs,
            as_of_mode=as_of_mode,
            as_of_cutoff=as_of_cutoff,
            computed_at=as_of_cutoff,
            value=value,
            unit=unit,
        ).derived_observation_id
    parts = (
        metric_id,
        formula_version,
        *inputs,
        as_of_mode.value,
        as_of_cutoff.isoformat(),
        repr(value),
        unit,
    )
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _usable_points_by_period(
    repository: EvidenceRepository,
    metric_id: str,
    *,
    as_of: datetime,
    dimensions: Mapping[str, str] | None = None,
    as_of_mode: AsOfMode,
    definition_version: str,
) -> dict[str, MetricSeriesPoint]:
    series = repository.metric_series(
        metric_id,
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition_version,
    )
    # Only the PMI and treasury yields hold their latest period to the recheck here.
    valid_claim_ids = (
        _adoptable_claims(repository, {metric_id: series}, definition_version=definition_version)
        if metric_id in OFFICIAL_CONTEXT_FAMILIES["nbs_pmi"].metric_ids
        or metric_id in TREASURY_METRICS
        else None
    )
    matching_points = tuple(
        point for point in series if dimensions is None or point.dimensions == dimensions
    )
    if valid_claim_ids is not None and matching_points:
        latest_period = max(point.period_end for point in matching_points)
        if any(
            not _usable_point(point) or point.selected_claim_id not in valid_claim_ids
            for point in matching_points
            if point.period_end == latest_period
        ):
            return {}
    return {
        point.period_end: point
        for point in matching_points
        if _usable_point(point)
        and (valid_claim_ids is None or point.selected_claim_id in valid_claim_ids)
    }


def _consecutive_months(previous: MetricSeriesPoint, current: MetricSeriesPoint) -> bool:
    previous_date = date.fromisoformat(previous.period_end)
    current_date = date.fromisoformat(current.period_end)
    previous_ordinal = previous_date.year * 12 + previous_date.month
    current_ordinal = current_date.year * 12 + current_date.month
    return current_ordinal - previous_ordinal == 1


def _latest_usable_point(
    repository: EvidenceRepository,
    metric_id: str,
    *,
    as_of: datetime,
    no_later_than: str | None = None,
    as_of_mode: AsOfMode,
    definition_version: str,
) -> MetricSeriesPoint | None:
    points = [
        point
        for point in repository.metric_series(
            metric_id,
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if (definition_version not in BUILTIN_CATALOG_VERSIONS or _usable_point(point))
        and (no_later_than is None or point.period_end <= no_later_than)
    ]
    return points[-1] if points and _usable_point(points[-1]) else None


def _metric_rows(
    repository: EvidenceRepository,
    definition: MetricDefinition,
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
) -> _MetricRows:
    series = repository.metric_series(
        definition.metric_id,
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition.definition_version,
    )
    incomplete_source_claims: set[str] = set()
    warrant_latest_period = None
    warrant_history = None
    adoptable = None
    if definition.metric_id not in _NOT_RECHECKED_IN_PROJECTION:
        adoption = ClaimAdoption(
            repository, definition_version=definition.definition_version, mode=as_of_mode
        ).check({definition.metric_id: series})[definition.metric_id]
        incomplete_source_claims.update(adoption.not_adoptable)
        if definition.metric_id == "CN_FUTURES_WARRANTS" and adoption.decides_members:
            # A symbol missing a warehouse member is left out alone (its claims are not
            # adoptable); the day's complete symbols stand, as in retrieval (ADR-0032).
            warrant_latest_period = max((point.period_end for point in series), default=None)
            adoptable = frozenset(adoption.adoptable)
            complete_periods: dict[str, list[str]] = {}
            for period in {point.period_end for point in series}:
                for symbol in {
                    point.dimensions["symbol"]
                    for point in series
                    if point.period_end == period and point.selected_claim_id in adoption.adoptable
                }:
                    complete_periods.setdefault(symbol, []).append(period)
            warrant_history = WarrantHistoryCoverage(
                {symbol: tuple(sorted(periods)) for symbol, periods in complete_periods.items()}
            )
    release_status = _release_status(
        repository,
        definition,
        as_of=as_of,
        as_of_mode=as_of_mode,
    )
    grouped: dict[str, list[MetricSeriesPoint]] = {}
    for point in series:
        grouped.setdefault(json.dumps(point.dimensions, sort_keys=True), []).append(point)
    if not grouped:
        history_lookup = getattr(repository, "has_target_history", None)
        if (
            definition.frequency == "event"
            and callable(history_lookup)
            and history_lookup(
                definition.metric_id,
                mode=as_of_mode,
                as_of=as_of,
                definition_version=definition.definition_version,
            )
        ):
            release_status = "no_event_in_visible_window"
        return _MetricRows(
            (_gap_row(definition, release_status=release_status),), warrant_history, adoptable
        )
    # The window's first month (quarter) is compared with the one before the window.
    earlier = _periods_before_window(
        repository, definition, grouped, as_of=as_of, as_of_mode=as_of_mode
    )
    if earlier and definition.metric_id not in _NOT_RECHECKED_IN_PROJECTION:
        adoption = ClaimAdoption(
            repository, definition_version=definition.definition_version, mode=as_of_mode
        ).check({definition.metric_id: tuple(earlier.values())})[definition.metric_id]
        incomplete_source_claims.update(adoption.not_adoptable)
    rows: list[dict[str, object]] = []
    for dimensions_key in sorted(grouped):
        points = grouped[dimensions_key]
        current = points[-1]
        previous = points[-2] if len(points) > 1 else earlier.get(dimensions_key)
        selected = next(
            (claim for claim in current.claims if claim.claim_id == current.selected_claim_id),
            None,
        )
        status = _evidence_status(
            definition,
            current,
            selected,
            as_of=as_of,
            release_status=release_status,
        )
        if (
            warrant_latest_period is not None
            and current.period_end != warrant_latest_period
            and status == "current"
        ):
            status = "stale"
        if current.selected_claim_id in incomplete_source_claims:
            status = "source_failed"
        value = current.selected_value
        previous_value = (
            previous.selected_value
            if value is not None
            and previous is not None
            and _usable_point(previous)
            and previous.selected_claim_id not in incomplete_source_claims
            else None
        )
        direction_inputs = []
        if (
            value is not None
            and previous is not None
            and previous_value is not None
            and previous.selected_claim_id is not None
            and not definition.metric_id.startswith("CN_PMI")
            and current.dimensions.get("measure")
            not in {
                "net_injection",
                "released_funds",
                "rrr_change",
            }
        ):
            direction_inputs.append(previous.selected_claim_id)
        rows.append(
            {
                "available_at": selected.available_at.isoformat() if selected is not None else None,
                "claim_ids": [claim.claim_id for claim in current.claims],
                "claims": [
                    {
                        "available_at": claim.available_at.isoformat(),
                        "claim_id": claim.claim_id,
                        "provider": claim.provider,
                        "public_available_at": (
                            claim.public_available_at.isoformat()
                            if claim.public_available_at is not None
                            else None
                        ),
                        "quality_status": claim.quality_status,
                        "selected": claim.claim_id == current.selected_claim_id,
                        "source_reference": claim.source_reference,
                        "unit": claim.unit,
                        "value": claim.value,
                        "value_state": claim.value_state.value,
                    }
                    for claim in current.claims
                ],
                "dimensions": current.dimensions,
                "direction_input_observation_version_ids": direction_inputs,
                "direction": _raw_direction(
                    definition.metric_id,
                    value,
                    previous_value,
                    current.dimensions,
                ),
                "metric_id": definition.metric_id,
                "observation_id": current.observation_id,
                "name_cn": definition.name_cn,
                "frequency": evidence_frequency(definition.metric_id, definition.frequency),
                "period_start": current.period_start,
                "period": current.period_end,
                "public_available_at": (
                    selected.public_available_at.isoformat()
                    if selected is not None and selected.public_available_at is not None
                    else None
                ),
                "quality_status": selected.quality_status if selected is not None else None,
                "selected_claim_id": current.selected_claim_id,
                "source_reference": selected.source_reference if selected is not None else None,
                "status": status,
                "unit": selected.unit if selected is not None else definition.unit,
                "value": value,
                "value_state": (
                    current.value_state.value if current.value_state is not None else None
                ),
                # A failed recheck outranks the conflict in the status, not in the row (#09).
                **(
                    {"conflict_reason": current.conflict_reason}
                    if current.conflict_reason is not None
                    else {}
                ),
                **(
                    {"source_failure": "not_adoptable"}
                    if current.selected_claim_id in incomplete_source_claims
                    else {}
                ),
            }
        )
    return _MetricRows(tuple(rows), warrant_history, adoptable)


def _gap_row(
    definition: MetricDefinition,
    *,
    release_status: str | None,
) -> dict[str, object]:
    return {
        "available_at": None,
        "claim_ids": [],
        "claims": [],
        "dimensions": {},
        "direction": "unknown",
        "metric_id": definition.metric_id,
        "observation_id": f"gap:{definition.metric_id}",
        "name_cn": definition.name_cn,
        "frequency": evidence_frequency(definition.metric_id, definition.frequency),
        "period_start": None,
        "period": None,
        "public_available_at": None,
        "quality_status": None,
        "selected_claim_id": None,
        "source_reference": None,
        "status": release_status or "missing",
        "unit": definition.unit,
        "value": None,
        "value_state": None,
    }


def _evidence_status(
    definition: MetricDefinition,
    point: MetricSeriesPoint,
    selected: Any,
    *,
    as_of: datetime,
    release_status: str | None,
) -> str:
    if point.selection_status == "conflicted":
        return "conflicted"
    if selected is None:
        return "missing"
    if selected.quality_status != "validated":
        return "source_failed"
    if point.value_state is not EvidenceValueState.REPORTED_VALUE:
        return point.value_state.value if point.value_state is not None else "missing"
    if release_status is not None and release_status != "current":
        return release_status
    return _period_freshness(definition, point.period_end, as_of=as_of)


def _period_freshness(definition: MetricDefinition, period_end: str, *, as_of: datetime) -> str:
    return period_status(definition.metric_id, period_end, as_of)


def _release_status(
    repository: EvidenceRepository,
    definition: MetricDefinition,
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
) -> str | None:
    if definition.metric_id != "CN_LPR_1Y_5Y":
        return None
    from pring_cycle.release_calendar import current_lpr_period, lpr_release_calendar

    target_date = getattr(repository, "target_date", None)
    period = (
        target_date.strftime("%Y-%m")
        if isinstance(target_date, date)
        else current_lpr_period(as_of)
    )
    event = lpr_release_calendar(
        repository,
        period=period,
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition.definition_version,
    )[0]
    return event.status


def _periods_before_window(
    repository: Any,
    definition: MetricDefinition,
    grouped: Mapping[str, list[MetricSeriesPoint]],
    *,
    as_of: datetime,
    as_of_mode: AsOfMode,
) -> dict[str, MetricSeriesPoint]:
    """The period right before a monthly (quarterly) member's only point in the window.

    The window trims what is shown, not what its first period is compared with (ticket
    30); only the adjacent period stands in, an older one is no previous period. A metric
    in force until changed keeps its baseline instead.
    """
    frequency = evidence_frequency(definition.metric_id, definition.frequency)
    lookup = getattr(repository, "latest_before_window", None)
    if (
        frequency not in {"monthly", "quarterly"}
        or definition.metric_id in EFFECTIVE_UNTIL_CHANGED_METRICS
        or not callable(lookup)
        or not any(len(points) == 1 for points in grouped.values())
    ):
        return {}
    before = lookup(
        definition.metric_id,
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition.definition_version,
    )
    step = 1 if frequency == "monthly" else 3
    adjacent = {}
    for key, points in grouped.items():
        point = before.get(key)
        if len(points) != 1 or point is None:
            continue
        first, prior = (
            date.fromisoformat(points[0].period_end),
            date.fromisoformat(point.period_end),
        )
        if (first.year * 12 + first.month) - (prior.year * 12 + prior.month) == step:
            adjacent[key] = point
    return adjacent


def _raw_direction(
    metric_id: str,
    value: float | None,
    previous: float | None,
    dimensions: Mapping[str, str],
) -> str:
    if value is None:
        return "unknown"
    measure = dimensions.get("measure")
    if measure in {"net_injection", "released_funds", "rrr_change"}:
        return "up" if value > 0 else "down" if value < 0 else "flat"
    if metric_id.startswith("CN_PMI"):
        return "up" if value > 50 else "down" if value < 50 else "flat"
    if previous is None:
        return "unknown"
    tolerance = max(abs(previous) * 1e-9, 1e-12)
    if value - previous > tolerance:
        return "up"
    if previous - value > tolerance:
        return "down"
    return "flat"


def _signals(
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
    roles: dict[str, str],
    *,
    transform: str | None = None,
) -> list[EvidenceSignal]:
    signals = []
    for metric_id, role in roles.items():
        for row in rows_by_metric[metric_id]:
            direction = str(row["direction"])
            if transform == "policy":
                policy_direction = _policy_direction(
                    metric_id,
                    direction,
                    _string_dimensions(row["dimensions"]),
                )
                if policy_direction is None:
                    continue
                direction = policy_direction
            elif transform == "credit":
                direction = _credit_direction(metric_id, direction)
            signals.append(
                EvidenceSignal(
                    observation_id=str(row["observation_id"]),
                    metric_id=metric_id,
                    direction=direction,
                    role=role,
                    freshness=str(row["status"]),
                    conflict=row["status"] == "conflicted",
                    period_start=(
                        str(row["period_start"]) if row.get("period_start") is not None else None
                    ),
                    period=str(row["period"]) if row["period"] is not None else None,
                    available_at=(
                        str(row["available_at"]) if row["available_at"] is not None else None
                    ),
                    selected_claim_id=(
                        str(row["selected_claim_id"])
                        if row["selected_claim_id"] is not None
                        else None
                    ),
                    source_reference=(
                        str(row["source_reference"])
                        if row["source_reference"] is not None
                        else None
                    ),
                    value=_numeric_value(row["value"]),
                    unit=str(row["unit"]),
                    dimensions=_string_dimensions(row["dimensions"]),
                    value_state=(
                        str(row["value_state"]) if row["value_state"] is not None else None
                    ),
                )
            )
    return signals


def _policy_direction(
    metric_id: str,
    raw: str,
    dimensions: Mapping[str, str],
) -> str | None:
    measure = dimensions.get("measure")
    if metric_id in {"CN_OMO_7D_AMOUNT", "CN_TOOL_LIQUIDITY_MONTHLY"} and (
        measure != "net_injection"
    ):
        return None
    if metric_id == "CN_RRR_EVENT" and measure not in {
        "released_funds",
        "rrr_change",
    }:
        return None
    if raw not in {"up", "down", "flat"}:
        return "unknown"
    if raw == "flat":
        return "neutral"
    if metric_id in _POLICY_TRANSMISSION:
        easing_when_up = _TRANSMISSION_RISE_MEANS[metric_id] == "easing"
    else:
        easing_when_up = metric_id in {"CN_OMO_7D_AMOUNT", "CN_TOOL_LIQUIDITY_MONTHLY"} or (
            metric_id == "CN_RRR_EVENT" and measure == "released_funds"
        )
    easing = raw == "up" if easing_when_up else raw == "down"
    return "easing" if easing else "tightening"


def _credit_direction(metric_id: str, raw: str) -> str:
    if raw not in {"up", "down", "flat"}:
        return "unknown"
    if raw == "flat":
        return "flat"
    expands_when_down = metric_id == "CN_LPR_1Y_5Y"
    expanding = raw == "down" if expands_when_down else raw == "up"
    return "expanding" if expanding else "contracting"


def _policy_component_direction(signals: list[EvidenceSignal]) -> str:
    valid = [
        item.direction for item in signals if item.freshness == "current" and not item.conflict
    ]
    directions = set(valid) - {"unknown"}
    if len(directions) == 1:
        return next(iter(directions))
    return "insufficient_data" if not directions else "conflict"


def _role_direction(signals: list[EvidenceSignal], role: str) -> str | None:
    directions = {
        item.direction
        for item in signals
        if item.role == role and item.freshness == "current" and not item.conflict
    } - {"unknown", "flat"}
    if len(directions) == 1:
        return next(iter(directions))
    return "conflict" if directions else None


def _inventory_direction(signals: list[EvidenceSignal]) -> str | None:
    preferred_roles = ("physical_inventory", "inventory_sales_turnover", "materials_finished_goods")
    for role in preferred_roles:
        direction = _role_direction(signals, role)
        if direction is not None:
            return direction
    return None


def _row_documents(
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
    roles: dict[str, str],
) -> list[dict[str, object]]:
    return [row for metric_id in roles for row in rows_by_metric[metric_id]]


def _document_rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _inventory_card_document(
    card: SignatureCard,
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
) -> dict[str, object]:
    document = asdict(card)
    name = str(document["name"])
    document["evidence"] = [
        row
        for metric_id, role in _INVENTORY.items()
        if role == name
        for row in rows_by_metric[metric_id]
    ]
    return document


def _international_context(
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
    definitions: tuple[MetricDefinition, ...],
) -> list[dict[str, object]]:
    documents = []
    for definition in definitions:
        if definition.priority != "P2":
            continue
        for row in rows_by_metric[definition.metric_id]:
            documents.append(
                {
                    **row,
                    "name_cn": definition.name_cn,
                    "frequency": evidence_frequency(definition.metric_id, definition.frequency),
                    "role": "context_only_never_formal_stage",
                }
            )
    return documents


_COMMON_MONTH_INVENTORY_FORMULA = "inventory-ppi-common-month-v0002"


class _PeriodBoundSeries:
    """Delegate evidence access, hiding one metric's periods after a bound."""

    def __init__(self, repository: Any, metric_id: str, period_end: str) -> None:
        self._repository = repository
        self._metric_id = metric_id
        self._period_end = period_end

    def metric_series(self, metric_id: str, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        series = self._repository.metric_series(metric_id, *args, **kwargs)
        if metric_id != self._metric_id:
            return tuple(series)
        return tuple(point for point in series if point.period_end <= self._period_end)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)


def _row_for_period(
    repository: Any,
    definition: MetricDefinition,
    *,
    period: str,
    dimensions: Mapping[str, str],
    as_of: datetime,
    as_of_mode: AsOfMode,
) -> dict[str, object] | None:
    # Duck-typed like TargetBoundEvidenceRepository: only the bounded metric changes.
    bounded: Any = _PeriodBoundSeries(repository, definition.metric_id, period)
    rows = _metric_rows(
        bounded,
        definition,
        as_of=as_of,
        as_of_mode=as_of_mode,
    ).rows
    return next(
        (
            row
            for row in rows
            # An older aligned period is judged by its own validity; freshness belongs to the
            # latest row, which the caller has already required to be current.
            if row["status"] in {"current", "stale"}
            and row["dimensions"] == dict(dimensions)
            and row["period"] == period
        ),
        None,
    )


def _real_inventory_proxy(
    repository: EvidenceRepository,
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
    *,
    as_of: datetime,
    formula_version: str | None,
    as_of_mode: AsOfMode,
    persist_derived: bool,
    series_repository: Any = None,
    ppi_definition: MetricDefinition | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    nominal = next(
        (
            row
            for row in rows_by_metric["CN_FINISHED_GOODS_INVENTORY"]
            if row["status"] == "current" and row["dimensions"] == {"measure": "nominal_end_level"}
        ),
        None,
    )
    ppi = next(
        (
            row
            for row in rows_by_metric["CN_PPI"]
            if row["status"] == "current"
            and row["dimensions"] == {"measure": "yoy", "category": "headline"}
        ),
        None,
    )
    document: dict[str, object] = {
        "formula_version": formula_version,
        "formula": "nominal_finished_goods_inventory / (1 + ppi_yoy / 100)",
        "is_official_statistic": False,
        "label": "price_adjusted_inventory_approximation",
        "nominal_inventory": nominal,
        "ppi_input": ppi,
        "status": ("missing_inputs" if formula_version is not None else "disabled_by_model"),
        "value": None,
    }
    if (
        formula_version == _COMMON_MONTH_INVENTORY_FORMULA
        and nominal is not None
        and ppi is not None
        and ppi["period"] != nominal["period"]
        and ppi_definition is not None
    ):
        # PPI for a month is released before that month's inventory, so the common month is
        # the inventory period. Its PPI must pass the same checks as a latest row.
        aligned = _row_for_period(
            series_repository if series_repository is not None else repository,
            ppi_definition,
            period=str(nominal["period"]),
            dimensions={"measure": "yoy", "category": "headline"},
            as_of=as_of,
            as_of_mode=as_of_mode,
        )
        if aligned is not None:
            ppi = aligned
            document["ppi_input"] = ppi
    if formula_version is None or nominal is None or ppi is None:
        return document, ()
    if nominal["period"] != ppi["period"]:
        return {**document, "status": "period_mismatch"}, ()
    nominal_value = _numeric_value(nominal["value"])
    ppi_value = _numeric_value(ppi["value"])
    nominal_claim_id = nominal["selected_claim_id"]
    ppi_claim_id = ppi["selected_claim_id"]
    if (
        nominal_value is None
        or ppi_value is None
        or not isinstance(nominal_claim_id, str)
        or not isinstance(ppi_claim_id, str)
    ):
        return document, ()
    denominator = 1 + ppi_value / 100
    if denominator <= 0:
        return {**document, "status": "invalid_price_adjustment"}, ()
    inputs = tuple(sorted((nominal_claim_id, ppi_claim_id)))
    value = nominal_value / denominator
    derived_id = _derived_observation_identity(
        repository,
        metric_id="CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
        formula_version=formula_version,
        input_observation_version_ids=inputs,
        as_of_mode=as_of_mode,
        as_of_cutoff=as_of,
        value=value,
        unit=str(nominal["unit"]),
        persist=persist_derived,
    )
    return (
        {
            **document,
            "derived_observation_id": derived_id,
            "input_observation_version_ids": list(inputs),
            "status": "available",
            "value": value,
        },
        (derived_id,),
    )


def _credit_impulse_proxy(
    repository: EvidenceRepository,
    *,
    as_of: datetime,
    configured_formula_version: str | None,
    definition_version: str,
    definitions: Mapping[str, MetricDefinition],
    as_of_mode: AsOfMode,
    persist_derived: bool,
) -> tuple[dict[str, object] | None, dict[str, object], tuple[str, ...]]:
    result = credit_impulse.derive(
        repository,
        configured_formula_version,
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    formula_version = result.formula_version
    formula: dict[str, object] = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "formula_version": formula_version,
        "formula": result.formula,
        "status": result.status,
    }
    if result.failures:
        formula["failures"] = [failure.document() for failure in result.failures]
    if (
        formula_version is None
        or result.status != "available"
        or result.value is None
        or result.period is None
        or result.latest_gdp_period is None
        or result.social_financing_window is None
        or result.gdp_window is None
        or result.available_at is None
    ):
        return None, formula, ()
    value = result.value
    input_claim_ids = result.input_claim_ids
    derived_id = _derived_observation_identity(
        repository,
        metric_id="CN_CREDIT_IMPULSE",
        formula_version=formula_version,
        input_observation_version_ids=input_claim_ids,
        as_of_mode=as_of_mode,
        as_of_cutoff=as_of,
        value=value,
        unit=result.unit,
        persist=persist_derived,
    )
    stale_inputs = any(
        _period_freshness(definitions[metric_id], period_end, as_of=as_of) == "stale"
        for metric_id, period_end in (
            ("CN_SF_TOTAL", result.period),
            ("CN_GDP", result.latest_gdp_period),
        )
    )
    row: dict[str, object] = {
        "available_at": result.available_at.isoformat(),
        "derived_observation_id": derived_id,
        "dimensions": {},
        # The module's direction: the twelve-month share's is not its value's sign.
        "direction": result.direction,
        "input_observation_version_ids": list(input_claim_ids),
        "metric_id": "CN_CREDIT_IMPULSE",
        "observation_id": derived_id,
        "period_start": result.period_start,
        "period": result.period,
        "public_available_at": (
            result.public_available_at.isoformat()
            if result.public_available_at is not None
            else None
        ),
        "quality_status": "validated",
        "selected_claim_id": derived_id,
        "source_reference": f"formula:{formula_version}",
        "status": "stale" if stale_inputs else "current",
        "unit": result.unit,
        "value": value,
        "value_state": EvidenceValueState.REPORTED_VALUE.value,
    }
    formula.update(
        {
            "as_of_cutoff": as_of.isoformat(),
            "derived_observation_id": derived_id,
            "gdp_input_measure": result.gdp_input_measure,
            "gdp_window": list(result.gdp_window),
            "input_observation_version_ids": list(input_claim_ids),
            "social_financing_window": list(result.social_financing_window),
            "status": "stale_inputs" if stale_inputs else "available",
        }
    )
    return (
        row,
        formula,
        tuple((*input_claim_ids, derived_id)),
    )


def _numeric_value(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _string_dimensions(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}
