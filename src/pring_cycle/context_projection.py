from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from pring_cycle.catalog import MetricDefinition, metric_catalog, metric_definition
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


def build_context_projection(
    repository: EvidenceRepository,
    *,
    as_of: datetime,
) -> ContextProjection:
    if as_of.tzinfo is None:
        raise ValueError("context_projection_as_of_must_be_timezone_aware")
    relevant = (
        set(_POLICY_ACTION)
        | set(_POLICY_TRANSMISSION)
        | set(_CREDIT)
        | set(_OVERHEAT)
        | set(_PRICE)
        | set(_INVENTORY)
        | {item.metric_id for item in metric_catalog() if item.priority == "P2"}
    )
    rows_by_metric = {
        metric_id: _metric_rows(repository, metric_definition(metric_id), as_of=as_of)
        for metric_id in sorted(relevant)
    }
    credit_impulse_row, credit_formula, credit_version_ids = _credit_impulse_proxy(
        repository,
        as_of=as_of,
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
    )
    international_context = _international_context(rows_by_metric)
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
        "cards": [
            _inventory_card_document(card, rows_by_metric) for card in inventory.cards
        ],
        "real_inventory_approximation": real_inventory,
        "semantics": {
            "pmi_inventory": "diffusion_index_not_inventory_quantity",
            "futures_warrants": "registered_receipts_not_total_industrial_inventory",
        },
        "score": None,
    }
    all_rows = [row for rows in rows_by_metric.values() for row in rows]
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
        )
    )
    warning_groups = {
        "policy": policy.state,
        "credit": credit.state,
        "overheat": overheat.state,
        "price": price.state,
        "inventory": inventory.quadrant or "insufficient_data",
    }
    warnings = tuple(
        f"{name}_context_degraded:{state}"
        for name, state in warning_groups.items()
        if state in {"insufficient_data", "transmission_conflict"}
    )
    if any(item["status"] != "current" for item in international_context):
        warnings += ("p2_context_degraded",)
    return ContextProjection(macro_document, inventory_document, versions, warnings)


def _metric_rows(
    repository: EvidenceRepository,
    definition: MetricDefinition,
    *,
    as_of: datetime,
) -> tuple[dict[str, object], ...]:
    series = repository.metric_series(definition.metric_id, mode=AsOfMode.SYSTEM, as_of=as_of)
    release_status = _release_status(repository, definition, as_of=as_of)
    grouped: dict[str, list[MetricSeriesPoint]] = {}
    for point in series:
        grouped.setdefault(json.dumps(point.dimensions, sort_keys=True), []).append(point)
    if not grouped:
        return (_gap_row(definition, release_status=release_status),)
    rows: list[dict[str, object]] = []
    for points in grouped.values():
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
        value = current.selected_value
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
                        "value": claim.value,
                        "value_state": claim.value_state.value,
                    }
                    for claim in current.claims
                ],
                "dimensions": current.dimensions,
                "direction": _raw_direction(
                    definition.metric_id,
                    value,
                    previous.selected_value if previous is not None else None,
                ),
                "metric_id": definition.metric_id,
                "observation_id": current.observation_id,
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
    return tuple(rows)


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
    period_date = date.fromisoformat(point.period_end)
    age = (as_of.date() - period_date).days
    limit = {"daily": 10, "monthly": 95, "quarterly": 190, "event": 370}.get(
        definition.frequency,
        95,
    )
    return "stale" if age > limit else "current"


def _release_status(
    repository: EvidenceRepository,
    definition: MetricDefinition,
    *,
    as_of: datetime,
) -> str | None:
    if definition.metric_id != "CN_LPR_1Y_5Y":
        return None
    from pring_cycle.release_calendar import current_lpr_period, lpr_release_calendar

    event = lpr_release_calendar(
        repository,
        period=current_lpr_period(as_of),
        as_of=as_of,
    )[0]
    return event.status


def _raw_direction(metric_id: str, value: float | None, previous: float | None) -> str:
    if value is None:
        return "unknown"
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
                direction = _policy_direction(metric_id, direction)
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


def _policy_direction(metric_id: str, raw: str) -> str:
    if raw not in {"up", "down", "flat"}:
        return "unknown"
    if raw == "flat":
        return "neutral"
    easing_when_up = metric_id in {
        "CN_OMO_7D_AMOUNT",
        "CN_TOOL_LIQUIDITY_MONTHLY",
        "CN_BOND_FULL_PRICE_CNY030",
    }
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
        item.direction
        for item in signals
        if item.freshness == "current" and not item.conflict
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
    return next(iter(directions)) if len(directions) == 1 else None


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
) -> list[dict[str, object]]:
    documents = []
    for definition in metric_catalog():
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
) -> tuple[dict[str, object], tuple[str, ...]]:
    nominal = next(
        (
            row
            for row in rows_by_metric["CN_FINISHED_GOODS_INVENTORY"]
            if row["status"] == "current"
        ),
        None,
    )
    ppi = next(
        (row for row in rows_by_metric["CN_PPI"] if row["status"] == "current"),
        None,
    )
    document: dict[str, object] = {
        "formula_version": "inventory-ppi-v0001",
        "formula": "nominal_finished_goods_inventory / (1 + ppi_yoy / 100)",
        "is_official_statistic": False,
        "label": "price_adjusted_inventory_approximation",
        "nominal_inventory": nominal,
        "ppi_input": ppi,
        "status": "missing_certified_inputs",
        "value": None,
    }
    if nominal is None or ppi is None:
        return document, ()
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
    derived = repository.append_derived_observation(
        metric_id="CN_REAL_FINISHED_GOODS_INVENTORY_PROXY",
        formula_version="inventory-ppi-v0001",
        input_observation_version_ids=inputs,
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=as_of,
        computed_at=as_of,
        value=value,
        unit=str(nominal["unit"]),
    )
    return (
        {
            **document,
            "derived_observation_id": derived.derived_observation_id,
            "input_observation_version_ids": list(inputs),
            "status": "available",
            "value": value,
        },
        (derived.derived_observation_id,),
    )


def _credit_impulse_proxy(
    repository: EvidenceRepository,
    *,
    as_of: datetime,
) -> tuple[dict[str, object] | None, dict[str, object], tuple[str, ...]]:
    formula_version = "credit-impulse-rolling-share-v0001"
    formula: dict[str, object] = {
        "metric_id": "CN_CREDIT_IMPULSE",
        "formula_version": formula_version,
        "formula": (
            "100 * (rolling_12m_social_financing / rolling_4q_nominal_gdp "
            "- prior_rolling_12m_social_financing / prior_rolling_4q_nominal_gdp)"
        ),
        "status": "missing_certified_inputs",
    }
    social_financing = [
        point
        for point in repository.metric_series(
            "CN_SF_TOTAL",
            mode=AsOfMode.SYSTEM,
            as_of=as_of,
        )
        if point.dimensions == {"measure": "monthly_increment"}
        and _certified_point(point)
    ]
    nominal_gdp = [
        point
        for point in repository.metric_series(
            "CN_GDP",
            mode=AsOfMode.SYSTEM,
            as_of=as_of,
        )
        if point.dimensions
        == {"aggregate": "total", "measure": "nominal_quarterly_level"}
        and _certified_point(point)
    ]
    if len(social_financing) < 24 or len(nominal_gdp) < 8:
        return None, formula, ()
    social_financing = social_financing[-24:]
    nominal_gdp = nominal_gdp[-8:]
    if not _periods_are_consecutive(social_financing, periods_per_year=12):
        return None, {**formula, "status": "nonconsecutive_social_financing_inputs"}, ()
    if not _periods_are_consecutive(nominal_gdp, periods_per_year=4):
        return None, {**formula, "status": "nonconsecutive_gdp_inputs"}, ()
    social_values = [point.selected_value for point in social_financing]
    gdp_values = [point.selected_value for point in nominal_gdp]
    social_numbers = [value for value in social_values if value is not None]
    gdp_numbers = [value for value in gdp_values if value is not None]
    if len(social_numbers) != len(social_values) or len(gdp_numbers) != len(gdp_values):
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
        for point in (*social_financing, *nominal_gdp)
        if point.selected_claim_id is not None
    )
    derived = repository.append_derived_observation(
        metric_id="CN_CREDIT_IMPULSE",
        formula_version=formula_version,
        input_observation_version_ids=input_claim_ids,
        as_of_mode=AsOfMode.SYSTEM,
        as_of_cutoff=as_of,
        computed_at=as_of,
        value=value,
        unit="percentage_points",
    )
    selected_claims = [
        selected
        for point in (*social_financing, *nominal_gdp)
        if (selected := _selected_claim(point)) is not None
    ]
    available_at = max(claim.available_at for claim in selected_claims)
    public_times = [
        claim.public_available_at
        for claim in selected_claims
        if claim.public_available_at is not None
    ]
    public_available_at = max(public_times) if public_times else None
    row: dict[str, object] = {
        "available_at": available_at.isoformat(),
        "certification_status": "derived_from_certified_inputs",
        "derived_observation_id": derived.derived_observation_id,
        "dimensions": {},
        "direction": "up" if value > 0 else "down" if value < 0 else "flat",
        "input_observation_version_ids": list(input_claim_ids),
        "metric_id": "CN_CREDIT_IMPULSE",
        "observation_id": derived.derived_observation_id,
        "period": social_financing[-1].period_end,
        "public_available_at": (
            public_available_at.isoformat() if public_available_at is not None else None
        ),
        "quality_status": "validated",
        "selected_claim_id": derived.derived_observation_id,
        "source_reference": f"formula:{formula_version}",
        "status": "current",
        "unit": "percentage_points",
        "value": value,
        "value_state": EvidenceValueState.REPORTED_VALUE.value,
    }
    formula.update(
        {
            "as_of_cutoff": as_of.isoformat(),
            "derived_observation_id": derived.derived_observation_id,
            "gdp_window": [nominal_gdp[0].period_start, nominal_gdp[-1].period_end],
            "input_observation_version_ids": list(input_claim_ids),
            "social_financing_window": [
                social_financing[0].period_start,
                social_financing[-1].period_end,
            ],
            "status": "available",
        }
    )
    return (
        row,
        formula,
        tuple((*input_claim_ids, derived.derived_observation_id)),
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
    return all(
        right - left == 1
        for left, right in zip(ordinals, ordinals[1:], strict=False)
    )


def _numeric_value(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _string_dimensions(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}
