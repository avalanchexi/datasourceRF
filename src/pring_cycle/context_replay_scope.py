"""Manifest-bound source and formula scope shared by replay and its saved output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from pring_cycle.context_projection import ContextProjectionRules

CONTEXT_FORMULA_INPUTS = {
    "credit_impulse": ("CN_SF_TOTAL", "CN_GDP"),
    "dr007_policy_spread": ("CN_DR007", "CN_OMO_7D_RATE"),
    "loan_monthly_change": ("CN_LOAN_STRUCTURE",),
    "omo_net_injection": ("CN_OMO_7D_AMOUNT",),
    "order_inventory_spread": ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY"),
    "production_order_spread": ("CN_PMI_ACTIVITY",),
    "real_inventory_approximation": ("CN_FINISHED_GOODS_INVENTORY", "CN_PPI"),
    "ust_2s10s_spread": ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"),
}
CONTEXT_DERIVED_OUTPUTS = {
    "CN_CREDIT_IMPULSE",
    "CN_DR007_POLICY_SPREAD",
    "CN_ORDER_INVENTORY_SPREAD",
    "CN_PRODUCTION_ORDER_SPREAD",
    "UST_2S10S_SPREAD",
}
CONTEXT_FORMULA_OUTPUTS = {
    "credit_impulse": "CN_CREDIT_IMPULSE",
    "dr007_policy_spread": "CN_DR007_POLICY_SPREAD",
    "loan_monthly_change": "CN_LOAN_STRUCTURE",
    "omo_net_injection": "CN_OMO_7D_AMOUNT",
    "order_inventory_spread": "CN_ORDER_INVENTORY_SPREAD",
    "production_order_spread": "CN_PRODUCTION_ORDER_SPREAD",
    "real_inventory_approximation": "CN_FINISHED_GOODS_INVENTORY",
    "ust_2s10s_spread": "UST_2S10S_SPREAD",
}


@dataclass(frozen=True)
class ContextReplayScope:
    candidate: ContextProjectionRules
    comparison: ContextProjectionRules
    requires_replay: bool
    formula_keys: set[str]
    required_formula_keys: set[str]
    optional_metrics: set[str]
    requires_certification: set[str]
    source_metrics: set[str]

    @classmethod
    def from_manifests(
        cls, candidate_manifest: Mapping[str, object], comparison_manifest: Mapping[str, object]
    ) -> ContextReplayScope:
        candidate = ContextProjectionRules.from_manifest(candidate_manifest)
        comparison = ContextProjectionRules.from_manifest(comparison_manifest)
        signatures = []
        for rules in (candidate, comparison):
            definitions = {}
            for definition in rules.metric_definitions:
                signature = asdict(definition)
                signature.pop("definition_version")
                definitions[definition.metric_id] = signature
            signatures.append(definitions)
        relevant = {
            item.metric_id
            for item in (*candidate.metric_definitions, *comparison.metric_definitions)
            if item.priority in {"P1", "P2"}
        }
        changed = {
            metric for metric in relevant if signatures[0].get(metric) != signatures[1].get(metric)
        }
        packages = candidate_manifest.get("source_certification_packages")
        if isinstance(packages, list) and packages:
            changed |= {
                item.metric_id for item in candidate.metric_definitions if item.priority == "P1"
            }
        if packages != comparison_manifest.get("source_certification_packages"):
            changed |= relevant
        configured_formulas = candidate.formula_versions.keys() | comparison.formula_versions.keys()
        changed_formulas = {
            key
            for key in configured_formulas
            if candidate.formula_versions.get(key) != comparison.formula_versions.get(key)
        }
        formulas = changed_formulas | {
            key
            for key, inputs in CONTEXT_FORMULA_INPUTS.items()
            if key in configured_formulas
            and (changed & set(inputs) or CONTEXT_FORMULA_OUTPUTS[key] in changed)
        }
        inputs = {metric for key in formulas for metric in CONTEXT_FORMULA_INPUTS.get(key, ())}
        required_metrics = {
            item.metric_id
            for item in (*candidate.metric_definitions, *comparison.metric_definitions)
            if item.priority == "P1" or item.role == "core_barometer"
        }
        required_formulas: set[str] = set()
        while True:
            dependencies = {
                key
                for key in formulas - required_formulas
                if CONTEXT_FORMULA_OUTPUTS.get(key) in required_metrics
            }
            if not dependencies:
                break
            required_formulas |= dependencies
            required_metrics.update(
                metric for key in dependencies for metric in CONTEXT_FORMULA_INPUTS.get(key, ())
            )
        required = ((changed - CONTEXT_DERIVED_OUTPUTS) | inputs) & required_metrics
        displayed = changed | inputs | {CONTEXT_FORMULA_OUTPUTS[key] for key in formulas}
        optional = {
            item.metric_id
            for item in (*candidate.metric_definitions, *comparison.metric_definitions)
            if item.priority == "P2"
            and item.metric_id in displayed
            and item.metric_id not in required_metrics
        }
        return cls(
            candidate,
            comparison,
            bool(changed or changed_formulas),
            formulas,
            required_formulas,
            optional,
            required,
            {
                item.metric_id
                for item in (*candidate.metric_definitions, *comparison.metric_definitions)
                if item.metric_id in (changed | inputs) - CONTEXT_DERIVED_OUTPUTS
                and (item.priority == "P1" or item.certification_status == "certified")
            },
        )
