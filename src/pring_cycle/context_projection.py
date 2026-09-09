from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.catalog import MetricDefinition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.domain.macro import (
    EvidenceSignal,
    SignatureCard,
    calculate_credit_impulse,
    derive_credit_response,
    derive_inventory_cycle,
    derive_overheat_state,
    derive_policy_direction,
    derive_price_pressure,
)
from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
)
from pring_cycle.metric_contracts import evidence_max_age_days
from pring_cycle.official_lpr import lpr_claims_matching_acquisitions
from pring_cycle.published_events import select_published_rrr_events
from pring_cycle.warrant_inputs import WarrantHistoryCoverage, select_warrant_inputs

_POLICY_ACTION = {
    "CN_OMO_7D_RATE": "policy_action",
    "CN_OMO_7D_AMOUNT": "policy_action",
    "CN_RRR_EVENT": "policy_action",
    "CN_TOOL_LIQUIDITY_MONTHLY": "policy_action",
}
_POLICY_TRANSMISSION = {
    "CN_DR007": "transmission",
    "CN_DR007_POLICY_SPREAD": "transmission",
    "CN_SHIBOR_ON_1W_3M": "transmission",
    "CN_BOND_10Y_930916": "transmission",
    "CN_BOND_FULL_PRICE_CNY030": "transmission",
}
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


_SUPPORTED_FORMULA_VERSIONS = {
    "credit_impulse": {
        "credit-impulse-v0001",
        "credit-impulse-rolling-share-v0001",
        "credit-impulse-ytd-flow-v0002",
    },
    "dr007_policy_spread": {"dr007-policy-spread-v0001"},
    "loan_monthly_change": {
        "loan-stock-monthly-change-v0001",
        "loan-ytd-monthly-change-v0002",
    },
    "omo_net_injection": {
        "repo-net-injection-v0001",
        "repo-net-injection-trading-calendar-v0002",
    },
    "order_inventory_spread": {
        "order-inventory-v0001",
        "pmi-order-inventory-spread-v0001",
    },
    "production_order_spread": {"pmi-production-order-spread-v0001"},
    "real_inventory_approximation": {"inventory-ppi-v0001"},
    "ust_2s10s_spread": {"ust-2s10s-spread-v0001"},
}


@dataclass(frozen=True)
class ContextProjectionRules:
    metric_catalog_version: str
    metric_definitions: tuple[MetricDefinition, ...]
    formula_versions: Mapping[str, str]

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
        return cls(catalog_version, definitions, formulas)


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
) -> ContextProjection:
    if as_of.tzinfo is None:
        raise ValueError("context_projection_as_of_must_be_timezone_aware")
    rules = ContextProjectionRules.from_manifest(model_manifest)
    repository.validate_model_catalog(model_manifest)
    definitions = {item.metric_id: item for item in rules.metric_definitions}
    visible_repository: Any = repository
    if target_business_date is not None:
        try:
            target_date = date.fromisoformat(target_business_date)
        except ValueError as error:
            raise ValueError("context_projection_target_date_invalid") from error
        target_repository = TargetBoundEvidenceRepository(
            repository,
            target_date,
            {metric_id: definition.frequency for metric_id, definition in definitions.items()},
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
            )
        else:
            visible_repository = target_repository
    relevant = context_metric_ids(rules)
    missing = sorted(relevant - definitions.keys())
    if missing:
        raise ValueError(f"context_model_metric_missing:{','.join(missing)}")
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
    acquisition_period = (
        target_business_date or as_of.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    )
    for definition in definitions.values():
        if definition.priority != "P2":
            continue
        attempt = repository.latest_retrieval_attempt(
            definition.metric_id,
            period=None,
            as_of=as_of,
            definition_version=definition.definition_version,
            target_business_date=acquisition_period,
        )
        latest = (
            {
                "attempt_id": attempt.retrieval_attempt_id,
                "channel": attempt.channel,
                "outcome": attempt.outcome,
                "recorded_at": attempt.fetched_at.isoformat(),
                "definition_version": definition.definition_version,
                "condition": attempt.safe_metadata.get("condition"),
                "request_sent": False
                if attempt.safe_metadata.get("request_sent") == "false"
                else None,
                "rejected_fields": attempt.safe_metadata.get("rejected_fields"),
                "latest_source_period": attempt.safe_metadata.get("latest_source_period"),
                "source_timezone": attempt.safe_metadata.get("source_timezone"),
                "release_date": attempt.safe_metadata.get("release_date"),
                "next_release_date": attempt.safe_metadata.get("next_release_date"),
                "release_timezone": attempt.safe_metadata.get("release_timezone"),
            }
            if attempt is not None
            else None
        )
        rows_by_metric[definition.metric_id] = tuple(
            {
                **row,
                "acquisition_status": attempt.outcome if attempt else "no_attempt_for_target",
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
        if any(
            definitions[metric_id].certification_status != "certified"
            for metric_id in input_metrics
        ) or definitions[output_metric].certification_status not in {
            "certified",
            "derived_from_certified_inputs",
        }:
            formula_versions.pop(formula, None)
    trading_calendar_metric_id = _core_stock_metric_id(model_manifest)
    if trading_calendar_metric_id is not None and (
        trading_calendar_metric_id not in definitions
        or definitions[trading_calendar_metric_id].certification_status != "certified"
    ):
        trading_calendar_metric_id = None
    market_derived_rows, market_derived_ids = _derived_market_context_rows(
        repository,
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
    if "credit_impulse" in rules.formula_versions and "credit_impulse" not in formula_versions:
        credit_formula.update(
            formula_version=rules.formula_versions["credit_impulse"],
            status="uncertified_model_dependencies",
        )
    if credit_impulse_row is not None:
        rows_by_metric["CN_CREDIT_IMPULSE"] = (credit_impulse_row,)
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
    real_inventory, derived_ids = _real_inventory_proxy(
        repository,
        rows_by_metric,
        as_of=as_of,
        formula_version=rules.formula_versions.get("real_inventory_approximation"),
        as_of_mode=as_of_mode,
        persist_derived=persist_derived,
    )
    international_context = _international_context(rows_by_metric, rules.metric_definitions)
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
            "support": [asdict(item) for item in overheat.support],
            "counterevidence": [asdict(item) for item in overheat.counterevidence],
            "gaps": [asdict(item) for item in overheat.gaps],
        },
        "price_pressure": price.state,
        "price_chain": {
            "state": price.state,
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
    all_rows = [row for rows in rows_by_metric.values() for row in rows]
    model_inputs = set(derived_ids)
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
        )
    )
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
    if any(item["status"] != "current" for item in international_context):
        warnings += ("p2_context_degraded",)
    return ContextProjection(
        macro_document,
        inventory_document,
        versions,
        warnings,
        warrant_history=metric_results["CN_FUTURES_WARRANTS"].warrant_history,
    )


class TargetBoundEvidenceRepository:
    """Delegate evidence access while enforcing one historical period boundary."""

    def __init__(
        self,
        repository: Any,
        target_date: date,
        frequencies: Mapping[str, str],
        *,
        visible_start: date | None = None,
    ) -> None:
        self._repository = repository
        self._target_date = target_date
        self._frequencies = frequencies
        self._visible_start = visible_start

    def metric_series(self, *args: Any, **kwargs: Any) -> tuple[MetricSeriesPoint, ...]:
        tolerance = float(kwargs.get("tolerance", 0.0))
        query_kwargs = dict(kwargs)
        query_kwargs["public_as_of"] = datetime.combine(
            self._target_date,
            time.max,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        return tuple(
            bounded
            for point in self._repository.metric_series(*args, **query_kwargs)
            if (
                bounded := _point_at_target(
                    point,
                    self._target_date,
                    tolerance=tolerance,
                )
            )
            is not None
            if (
                self._visible_start is None
                or date.fromisoformat(bounded.period_end) >= self._visible_start
            )
        )

    @property
    def target_date(self) -> date:
        return self._target_date

    def has_target_history(self, *args: Any, **kwargs: Any) -> bool:
        query_kwargs = dict(kwargs)
        query_kwargs["public_as_of"] = datetime.combine(
            self._target_date,
            time.max,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
        return any(
            _certified_point(point) and date.fromisoformat(point.period_start) <= self._target_date
            for point in self._repository.metric_series(*args, **query_kwargs)
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._repository, name)


def _point_at_target(
    point: MetricSeriesPoint,
    target_date: date,
    *,
    tolerance: float,
) -> MetricSeriesPoint | None:
    if date.fromisoformat(point.period_start) > target_date:
        return None
    claims = tuple(
        claim
        for claim in point.claims
        if claim.public_available_at is not None
        and claim.public_available_at.astimezone(ZoneInfo("Asia/Shanghai")).date() <= target_date
    )
    if not claims:
        return None
    selected = sorted(
        claims,
        key=lambda claim: (
            claim.certification_status != "certified",
            claim.provider,
        ),
    )[0]
    reported_values = [
        claim.value
        for claim in claims
        if claim.certification_status == "certified"
        and claim.quality_status == "validated"
        and claim.value_state is EvidenceValueState.REPORTED_VALUE
        and claim.value is not None
    ]
    conflicted = bool(reported_values) and (max(reported_values) - min(reported_values) > tolerance)
    return MetricSeriesPoint(
        observation_id=point.observation_id,
        period_start=point.period_start,
        period_end=point.period_end,
        dimensions=point.dimensions,
        selected_value=selected.value,
        value_state=selected.value_state,
        selection_status="conflicted" if conflicted else "selected",
        selected_claim_id=selected.claim_id,
        claims=claims,
    )


def _derived_market_context_rows(
    repository: EvidenceRepository,
    *,
    as_of: datetime,
    formula_versions: Mapping[str, str],
    definition_version: str,
    trading_calendar_metric_id: str | None,
    as_of_mode: AsOfMode,
    persist_derived: bool,
) -> tuple[dict[str, tuple[dict[str, object], ...]], tuple[str, ...]]:
    rows: dict[str, tuple[dict[str, object], ...]] = {}
    version_ids: list[str] = []
    reported_amount_points = repository.metric_series(
        "CN_OMO_7D_AMOUNT",
        mode=as_of_mode,
        as_of=as_of,
        definition_version=definition_version,
    )
    amount_points = [point for point in reported_amount_points if _certified_point(point)]
    invalid_amount_points = [
        point
        for point in reported_amount_points
        if point.dimensions.get("measure") in {"injection", "maturity"}
        and not _certified_point(point)
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
    if complete_periods and omo_formula == "repo-net-injection-v0001":
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
    elif amount_by_period and omo_formula == "repo-net-injection-trading-calendar-v0002":
        trading_day_points = (
            _certified_trading_day_points(
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
            maturity_day = _repo_maturity_trading_day(
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
                maturity_day := _repo_maturity_trading_day(
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
        if (
            maturity_basis is not None
            and (injection is not None or maturity_points)
            and target_period not in invalid_amount_periods
            and not invalid_maturity_inputs
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

    dr007 = _latest_certified_point(
        repository,
        "CN_DR007",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    policy_rate = _latest_certified_point(
        repository,
        "CN_OMO_7D_RATE",
        as_of=as_of,
        no_later_than=dr007.period_end if dr007 is not None else None,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    dr007_formula = formula_versions.get("dr007_policy_spread")
    if dr007 is not None and policy_rate is not None and dr007_formula is not None:
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

    ust2 = _certified_points_by_period(
        repository,
        "UST2Y_NOMINAL_YIELD",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    ust10 = _certified_points_by_period(
        repository,
        "UST10Y_NOMINAL_YIELD",
        as_of=as_of,
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    common_periods = set(ust2) & set(ust10)
    ust_formula = formula_versions.get("ust_2s10s_spread")
    if common_periods and ust_formula is not None:
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

    pmi_new_orders = _certified_points_by_period(
        repository,
        "CN_PMI_ACTIVITY",
        as_of=as_of,
        dimensions={"series": "new_orders", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    pmi_production = _certified_points_by_period(
        repository,
        "CN_PMI_ACTIVITY",
        as_of=as_of,
        dimensions={"series": "production", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    pmi_finished_goods = _certified_points_by_period(
        repository,
        "CN_PMI_INVENTORY",
        as_of=as_of,
        dimensions={"series": "finished_goods", "measure": "level"},
        as_of_mode=as_of_mode,
        definition_version=definition_version,
    )
    order_inventory_periods = set(pmi_new_orders) & set(pmi_finished_goods)
    order_formula = formula_versions.get("order_inventory_spread")
    if order_inventory_periods and order_formula == "pmi-order-inventory-spread-v0001":
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
    if production_order_periods and production_formula is not None:
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
    loan_input_measure = (
        "ytd_increment" if loan_formula == "loan-ytd-monthly-change-v0002" else "stock_end"
    )
    loan_stock_points = [
        point
        for point in repository.metric_series(
            "CN_LOAN_STRUCTURE",
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if _certified_point(point) and point.dimensions.get("measure") == loan_input_measure
    ]
    loan_groups: dict[tuple[str, str], list[MetricSeriesPoint]] = {}
    for point in loan_stock_points:
        key = (point.dimensions.get("borrower", ""), point.dimensions.get("tenor", ""))
        loan_groups.setdefault(key, []).append(point)
    loan_rows: list[dict[str, object]] = []
    if loan_formula is not None:
        for (borrower, tenor), points in sorted(loan_groups.items()):
            ordered = sorted(points, key=lambda point: point.period_end)
            current = ordered[-1]
            previous: MetricSeriesPoint | None
            if (
                loan_formula == "loan-ytd-monthly-change-v0002"
                and date.fromisoformat(current.period_end).month == 1
            ):
                previous = None
            elif len(ordered) < 2 or not _consecutive_months(ordered[-2], current):
                continue
            else:
                previous = ordered[-2]
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


def _certified_trading_day_points(
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
                if _certified_point(point)
            ),
            key=lambda point: (point.period_end, point.observation_id),
        )
    )


def _repo_maturity_trading_day(
    operation_date: date,
    trading_days: tuple[date, ...],
) -> date | None:
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
        "certification_status": "derived_from_certified_inputs",
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
        "certification_status": "derived_from_certified_inputs",
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


def _certified_points_by_period(
    repository: EvidenceRepository,
    metric_id: str,
    *,
    as_of: datetime,
    dimensions: Mapping[str, str] | None = None,
    as_of_mode: AsOfMode,
    definition_version: str,
) -> dict[str, MetricSeriesPoint]:
    return {
        point.period_end: point
        for point in repository.metric_series(
            metric_id,
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if _certified_point(point) and (dimensions is None or point.dimensions == dimensions)
    }


def _consecutive_months(previous: MetricSeriesPoint, current: MetricSeriesPoint) -> bool:
    previous_date = date.fromisoformat(previous.period_end)
    current_date = date.fromisoformat(current.period_end)
    previous_ordinal = previous_date.year * 12 + previous_date.month
    current_ordinal = current_date.year * 12 + current_date.month
    return current_ordinal - previous_ordinal == 1


def _latest_certified_point(
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
        if _certified_point(point) and (no_later_than is None or point.period_end <= no_later_than)
    ]
    return points[-1] if points else None


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
    incomplete_source_claims = (
        set(select_published_rrr_events(repository, series).incomplete_claim_ids)
        if definition.metric_id == "CN_RRR_EVENT"
        and definition.definition_version not in BUILTIN_CATALOG_VERSIONS
        else set()
    )
    if (
        definition.metric_id == "CN_LPR_1Y_5Y"
        and definition.definition_version not in BUILTIN_CATALOG_VERSIONS
    ):
        claim_ids = tuple(
            point.selected_claim_id for point in series if point.selected_claim_id is not None
        )
        incomplete_source_claims.update(
            set(claim_ids) - lpr_claims_matching_acquisitions(repository, series)
        )
    warrant_latest_period = None
    warrant_history = None
    if (
        definition.metric_id == "CN_FUTURES_WARRANTS"
        and definition.definition_version not in BUILTIN_CATALOG_VERSIONS
    ):
        warrant_latest_period = max((point.period_end for point in series), default=None)
        complete_periods: dict[str, list[str]] = {}
        for period in {point.period_end for point in series}:
            selection = select_warrant_inputs(
                repository,
                series,
                period=period,
                mode=as_of_mode,
                definition_version=definition.definition_version,
            )
            selected_ids = set(selection.selected_claim_ids)
            for symbol in {
                point.dimensions["symbol"]
                for point in series
                if point.selected_claim_id in selected_ids
            }:
                complete_periods.setdefault(symbol, []).append(period)
            incomplete_source_claims.update(selection.incomplete_claim_ids)
            if selection.missing_members:
                incomplete_source_claims.update(
                    point.selected_claim_id
                    for point in series
                    if point.period_end == period and point.selected_claim_id is not None
                )
        if definition.certification_status == "certified":
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
        return _MetricRows((_gap_row(definition, release_status=release_status),), warrant_history)
    rows: list[dict[str, object]] = []
    for dimensions_key in sorted(grouped):
        points = grouped[dimensions_key]
        current = points[-1]
        previous = points[-2] if len(points) > 1 else None
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
        if (
            current.selected_claim_id in incomplete_source_claims
            and status != "awaiting_source_certification"
        ):
            status = "source_failed"
        candidate_value = current.selected_value
        value = None if status == "awaiting_source_certification" else candidate_value
        previous_value = (
            previous.selected_value
            if value is not None
            and previous is not None
            and _certified_point(previous)
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
                "certification_status": (
                    selected.certification_status
                    if selected is not None
                    else definition.certification_status
                ),
                "claim_ids": [claim.claim_id for claim in current.claims],
                "claims": [
                    {
                        "available_at": claim.available_at.isoformat(),
                        "certification_status": claim.certification_status,
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
                        "value": (
                            None if status == "awaiting_source_certification" else claim.value
                        ),
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
            }
        )
    return _MetricRows(tuple(rows), warrant_history)


def _gap_row(
    definition: MetricDefinition,
    *,
    release_status: str | None,
) -> dict[str, object]:
    return {
        "available_at": None,
        "certification_status": definition.certification_status,
        "claim_ids": [],
        "claims": [],
        "dimensions": {},
        "direction": "unknown",
        "metric_id": definition.metric_id,
        "observation_id": f"gap:{definition.metric_id}",
        "period_start": None,
        "period": None,
        "public_available_at": None,
        "quality_status": None,
        "selected_claim_id": None,
        "source_reference": None,
        "status": release_status
        or (
            "awaiting_source_certification"
            if definition.certification_status != "certified"
            else "missing"
        ),
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
    if definition.certification_status != "certified":
        return "awaiting_source_certification"
    if point.selection_status == "conflicted":
        return "conflicted"
    if selected is None:
        return "missing"
    if selected.certification_status != "certified":
        return "awaiting_source_certification"
    if selected.quality_status != "validated":
        return "source_failed"
    if point.value_state is not EvidenceValueState.REPORTED_VALUE:
        return point.value_state.value if point.value_state is not None else "missing"
    if release_status is not None and release_status != "current":
        return release_status
    return _period_freshness(definition, point.period_end, as_of=as_of)


def _period_freshness(definition: MetricDefinition, period_end: str, *, as_of: datetime) -> str:
    period_date = date.fromisoformat(period_end)
    age = (as_of.date() - period_date).days
    limit = evidence_max_age_days(definition.metric_id, definition.frequency)
    return "stale" if age > limit else "current"


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
    easing_when_up = metric_id in {
        "CN_OMO_7D_AMOUNT",
        "CN_TOOL_LIQUIDITY_MONTHLY",
        "CN_BOND_FULL_PRICE_CNY030",
    } or (metric_id == "CN_RRR_EVENT" and measure == "released_funds")
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
                    "role": "context_only_never_formal_stage",
                }
            )
    return documents


def _real_inventory_proxy(
    repository: EvidenceRepository,
    rows_by_metric: dict[str, tuple[dict[str, object], ...]],
    *,
    as_of: datetime,
    formula_version: str | None,
    as_of_mode: AsOfMode,
    persist_derived: bool,
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
        "status": (
            "missing_certified_inputs" if formula_version is not None else "disabled_by_model"
        ),
        "value": None,
    }
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
    formula_version = configured_formula_version
    formula: dict[str, object] = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "formula_version": formula_version,
        "formula": (
            "100 * (rolling_12m_social_financing / rolling_4q_nominal_gdp "
            "- prior_rolling_12m_social_financing / prior_rolling_4q_nominal_gdp)"
        ),
        "status": (
            "missing_certified_inputs" if formula_version is not None else "disabled_by_model"
        ),
    }
    if formula_version is None:
        return None, formula, ()
    reported_monthly_social_financing = [
        point
        for point in repository.metric_series(
            "CN_SF_TOTAL",
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if point.dimensions == {"measure": "monthly_increment"} and _certified_point(point)
    ]
    reported_ytd_social_financing = [
        point
        for point in repository.metric_series(
            "CN_SF_TOTAL",
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if point.dimensions == {"measure": "ytd_increment"} and _certified_point(point)
    ]
    reported_quarterly_gdp = [
        point
        for point in repository.metric_series(
            "CN_GDP",
            mode=as_of_mode,
            as_of=as_of,
            definition_version=definition_version,
        )
        if point.dimensions == {"aggregate": "total", "measure": "nominal_quarterly_level"}
        and _certified_point(point)
    ]
    allow_ytd_gdp = configured_formula_version in {
        "credit-impulse-rolling-share-v0001",
        "credit-impulse-ytd-flow-v0002",
    }
    reported_ytd_gdp = (
        [
            point
            for point in repository.metric_series(
                "CN_GDP",
                mode=as_of_mode,
                as_of=as_of,
                definition_version=definition_version,
            )
            if point.dimensions == {"aggregate": "total", "measure": "nominal_ytd_level"}
            and _certified_point(point)
        ]
        if allow_ytd_gdp
        else []
    )
    gdp_period_points: list[MetricSeriesPoint]
    gdp_input_points: list[MetricSeriesPoint]
    gdp_numbers: list[float]
    gdp_input_measure: str
    if len(reported_quarterly_gdp) >= 8:
        gdp_period_points = reported_quarterly_gdp[-8:]
        gdp_input_points = gdp_period_points
        gdp_numbers = [
            float(point.selected_value)
            for point in gdp_period_points
            if point.selected_value is not None
        ]
        gdp_input_measure = "nominal_quarterly_level"
    else:
        derived_quarters = _quarter_levels_from_ytd(reported_ytd_gdp)
        if len(derived_quarters) < 8:
            return None, formula, ()
        selected_quarters = derived_quarters[-8:]
        gdp_period_points = [point for point, _value, _inputs in selected_quarters]
        gdp_numbers = [value for _point, value, _inputs in selected_quarters]
        selected_input_ids = {
            input_point.selected_claim_id
            for _point, _value, inputs in selected_quarters
            for input_point in inputs
        }
        gdp_input_points = [
            point for point in reported_ytd_gdp if point.selected_claim_id in selected_input_ids
        ]
        gdp_input_measure = "nominal_ytd_level"
    social_input_points: list[MetricSeriesPoint]
    social_numbers: list[float]
    social_period_points: list[MetricSeriesPoint]
    if len(reported_monthly_social_financing) >= 24:
        social_period_points = reported_monthly_social_financing[-24:]
        if not _periods_are_consecutive(social_period_points, periods_per_year=12):
            return None, {**formula, "status": "nonconsecutive_social_financing_inputs"}, ()
        values = [point.selected_value for point in social_period_points]
        social_numbers = [value for value in values if value is not None]
        social_input_points = social_period_points
    elif configured_formula_version == "credit-impulse-ytd-flow-v0002":
        monthly_flows = _monthly_flows_from_ytd(reported_ytd_social_financing)
        if len(monthly_flows) < 24:
            return None, formula, ()
        selected_flows = monthly_flows[-24:]
        social_period_points = [point for point, _value, _inputs in selected_flows]
        social_numbers = [value for _point, value, _inputs in selected_flows]
        selected_ids = {
            input_point.selected_claim_id
            for _point, _value, inputs in selected_flows
            for input_point in inputs
        }
        social_input_points = [
            point
            for point in reported_ytd_social_financing
            if point.selected_claim_id in selected_ids
        ]
    else:
        return None, formula, ()
    if len(social_period_points) < 24 or len(gdp_period_points) < 8:
        return None, formula, ()
    if not _periods_are_consecutive(social_period_points, periods_per_year=12):
        return None, {**formula, "status": "nonconsecutive_social_financing_inputs"}, ()
    if not _periods_are_consecutive(gdp_period_points, periods_per_year=4):
        return None, {**formula, "status": "nonconsecutive_gdp_inputs"}, ()
    if len(social_numbers) != 24 or len(gdp_numbers) != 8:
        return None, formula, ()
    current_social_financing = sum(social_numbers[-12:])
    previous_social_financing = sum(social_numbers[:12])
    current_gdp = sum(gdp_numbers[-4:])
    previous_gdp = sum(gdp_numbers[:4])
    try:
        value = calculate_credit_impulse(
            current_rolling_social_financing=current_social_financing,
            previous_rolling_social_financing=previous_social_financing,
            current_rolling_nominal_gdp=current_gdp,
            previous_rolling_nominal_gdp=previous_gdp,
        )
    except ValueError:
        return None, {**formula, "status": "invalid_gdp_denominator"}, ()
    input_claim_ids = tuple(
        point.selected_claim_id
        for point in (*social_input_points, *gdp_input_points)
        if point.selected_claim_id is not None
    )
    derived_id = _derived_observation_identity(
        repository,
        metric_id="CN_CREDIT_IMPULSE",
        formula_version=formula_version,
        input_observation_version_ids=input_claim_ids,
        as_of_mode=as_of_mode,
        as_of_cutoff=as_of,
        value=value,
        unit="percentage_points",
        persist=persist_derived,
    )
    selected_claims = [
        selected
        for point in (*social_input_points, *gdp_input_points)
        if (selected := _selected_claim(point)) is not None
    ]
    available_at = max(claim.available_at for claim in selected_claims)
    public_times = [
        claim.public_available_at
        for claim in selected_claims
        if claim.public_available_at is not None
    ]
    public_available_at = (
        max(public_times) if public_times and len(public_times) == len(selected_claims) else None
    )
    stale_inputs = any(
        _period_freshness(definitions[metric_id], point.period_end, as_of=as_of) == "stale"
        for metric_id, point in (
            ("CN_SF_TOTAL", social_period_points[-1]),
            ("CN_GDP", gdp_period_points[-1]),
        )
    )
    row: dict[str, object] = {
        "available_at": available_at.isoformat(),
        "certification_status": "derived_from_certified_inputs",
        "derived_observation_id": derived_id,
        "dimensions": {},
        "direction": "up" if value > 0 else "down" if value < 0 else "flat",
        "input_observation_version_ids": list(input_claim_ids),
        "metric_id": "CN_CREDIT_IMPULSE",
        "observation_id": derived_id,
        "period_start": social_period_points[-1].period_start,
        "period": social_period_points[-1].period_end,
        "public_available_at": (
            public_available_at.isoformat() if public_available_at is not None else None
        ),
        "quality_status": "validated",
        "selected_claim_id": derived_id,
        "source_reference": f"formula:{formula_version}",
        "status": "stale" if stale_inputs else "current",
        "unit": "percentage_points",
        "value": value,
        "value_state": EvidenceValueState.REPORTED_VALUE.value,
    }
    formula.update(
        {
            "as_of_cutoff": as_of.isoformat(),
            "derived_observation_id": derived_id,
            "gdp_input_measure": gdp_input_measure,
            "gdp_window": [
                gdp_period_points[0].period_start,
                gdp_period_points[-1].period_end,
            ],
            "input_observation_version_ids": list(input_claim_ids),
            "social_financing_window": [
                social_period_points[0].period_start,
                social_period_points[-1].period_end,
            ],
            "status": "stale_inputs" if stale_inputs else "available",
        }
    )
    return (
        row,
        formula,
        tuple((*input_claim_ids, derived_id)),
    )


def _selected_claim(point: MetricSeriesPoint) -> Any:
    return next(
        (claim for claim in point.claims if claim.claim_id == point.selected_claim_id),
        None,
    )


def _certified_point(point: MetricSeriesPoint) -> bool:
    selected = _selected_claim(point)
    return bool(
        point.selection_status == "selected"
        and point.value_state is EvidenceValueState.REPORTED_VALUE
        and point.selected_value is not None
        and selected is not None
        and selected.certification_status == "certified"
        and selected.quality_status == "validated"
    )


def _periods_are_consecutive(
    points: list[MetricSeriesPoint],
    *,
    periods_per_year: int,
) -> bool:
    ordinals = []
    for point in points:
        period = date.fromisoformat(point.period_end)
        if periods_per_year == 12:
            ordinal = period.year * 12 + period.month
        else:
            ordinal = period.year * 4 + (period.month - 1) // 3
        ordinals.append(ordinal)
    return all(right - left == 1 for left, right in zip(ordinals, ordinals[1:], strict=False))


def _quarter_levels_from_ytd(
    points: list[MetricSeriesPoint],
) -> list[tuple[MetricSeriesPoint, float, tuple[MetricSeriesPoint, ...]]]:
    derived: list[tuple[MetricSeriesPoint, float, tuple[MetricSeriesPoint, ...]]] = []
    for index, point in enumerate(points):
        value = point.selected_value
        if value is None:
            continue
        period = date.fromisoformat(point.period_end)
        quarter = (period.month - 1) // 3 + 1
        if quarter == 1:
            derived.append((point, float(value), (point,)))
            continue
        if index == 0:
            continue
        previous = points[index - 1]
        previous_period = date.fromisoformat(previous.period_end)
        previous_quarter = (previous_period.month - 1) // 3 + 1
        previous_value = previous.selected_value
        if (
            previous_period.year != period.year
            or previous_quarter != quarter - 1
            or previous_value is None
        ):
            continue
        quarter_value = float(value) - float(previous_value)
        if quarter_value <= 0:
            continue
        derived.append((point, quarter_value, (previous, point)))
    return derived


def _monthly_flows_from_ytd(
    points: list[MetricSeriesPoint],
) -> list[tuple[MetricSeriesPoint, float, tuple[MetricSeriesPoint, ...]]]:
    derived: list[tuple[MetricSeriesPoint, float, tuple[MetricSeriesPoint, ...]]] = []
    for index, point in enumerate(points):
        value = point.selected_value
        if value is None:
            continue
        period = date.fromisoformat(point.period_end)
        if period.month == 1:
            derived.append((point, float(value), (point,)))
            continue
        if index == 0:
            continue
        previous = points[index - 1]
        previous_period = date.fromisoformat(previous.period_end)
        previous_value = previous.selected_value
        if (
            previous_period.year != period.year
            or previous_period.month != period.month - 1
            or previous_value is None
        ):
            continue
        derived.append((point, float(value) - float(previous_value), (previous, point)))
    return derived


def _numeric_value(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _string_dimensions(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}
