from __future__ import annotations

import json
import sqlite3
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from pring_cycle.adapters import CORE_SOURCE_CODES
from pring_cycle.catalog import METRIC_CATALOG_V0003, MetricDefinition, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.metric_contracts import official_source_members
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES, OFFICIAL_CONTEXT_FAMILY_BY_METRIC

# This is a dated rejection of the frozen v3 certification contract, not a
# replacement catalog or a modification of historical evidence. A corrected
# contract needs its own immutable definitions and official semantic samples.
_AUDIT = "docs/research/market-source-semantic-review-2026-09-05.md"
_AUDIT_SHA256 = "e6c027f2749f901526cc3deb10f6a855d993b3843ceae420d4fad40eaf618cc2"
_FAMILIES = (
    (
        "market_indices",
        (
            "CN_EQ_CSI300",
            "CN_EQ_CSI500",
            "CN_EQ_CSI1000",
            "CN_BOND_FULL_PRICE_CNY030",
            "CN_BOND_10Y_930916",
            "CN_COMMODITY_BROAD_NHCI",
        ),
        (
            "official_channel_comparison_missing",
            "cny030_numeric_sample_missing",
            "publication_rule_evidence_missing",
        ),
    ),
    (
        "market_breadth",
        (
            "CN_EQ_ADV_DEC",
            "CN_EQ_AD_RATIO",
            "CN_EQ_NEW_HIGH_LOW_120",
            "CN_EQ_ABOVE_MA120",
            "CN_EQ_ADV_AMOUNT_SHARE",
        ),
        ("raw_inputs_and_point_in_time_universe_review_missing",),
    ),
    (
        "margin_financing",
        ("CN_MARGIN_BALANCE",),
        (
            "publication_time_precedes_supported_release",
            "exchange_completeness_and_duplicate_checks_missing",
            "official_channel_comparison_missing",
        ),
    ),
    (
        "index_valuation",
        ("CN_INDEX_VALUATION",),
        (
            "provider_calculated_method_not_certified",
            "csi1000_coverage_and_publication_evidence_missing",
        ),
    ),
    (
        "commodity_basket",
        ("CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"),
        (
            "close_return_used_instead_of_settlement_return",
            "contract_mapping_roll_and_base_point_evidence_missing",
        ),
    ),
)
_AFFECTED_METRICS = frozenset(metric for _, metrics, _ in _FAMILIES for metric in metrics)


def source_contract_review(definition_version: str) -> dict[str, Any] | None:
    """Return a known audit rejection; absence is not a certification grant."""
    if definition_version != METRIC_CATALOG_V0003:
        return None
    return {
        "code": "source_certification_contract_unresolved",
        "metric_catalog_version": definition_version,
        "audit": {"document": _AUDIT, "sha256": _AUDIT_SHA256},
        "families": [
            {"family": family, "metric_ids": list(metrics), "reason_codes": list(reasons)}
            for family, metrics, reasons in _FAMILIES
        ],
        "status": "blocked",
        "historical_results": "readable_without_rewriting",
        "remediation": "new_immutable_definitions_and_official_semantic_samples_required",
    }


def require_source_contract(definition_version: str, *, metric_id: str | None = None) -> None:
    if definition_version == METRIC_CATALOG_V0003 and (
        metric_id is None or metric_id in _AFFECTED_METRICS
    ):
        raise ValueError(f"source_certification_contract_unresolved:{definition_version}")


def require_registered_source_contract(
    definition: MetricDefinition,
    *,
    provider: str,
    source_reference: str,
    period_kind: str,
    dimensions: Mapping[str, str],
    unit: str,
    period_start: str,
    period_end: str,
    database_path: Path,
    value: float | None,
    acquisition_ids: tuple[str, ...],
) -> None:
    """New catalog identity alone does not certify an existing parser's output."""
    if definition.definition_version in BUILTIN_CATALOG_VERSIONS:
        return
    if definition.metric_id in CORE_SOURCE_CODES:
        # Deferred because the adapter's selected-claim checks also use Evidence types.
        from pring_cycle.source_adapters import CORE_API_IDENTITIES

        supported = metric_definition(definition.metric_id, definition_version=METRIC_CATALOG_V0003)
        core_fields = (
            "priority",
            "role",
            "source_codes",
            "dimensions",
            "unit",
            "frequency",
            "release_event_family",
            "release_rule",
            "release_timezone",
        )
        if any(
            getattr(definition, field) != getattr(supported, field) for field in core_fields
        ) or set(definition.allowed_units or (definition.unit,)) != {"index_points"}:
            raise ValueError("registered_core_source_contract_unsupported")
        api, code = CORE_API_IDENTITIES[definition.metric_id]
        if (
            provider != "tushare"
            or period_kind != "business_day"
            or dimensions != {}
            or unit != "index_points"
            or source_reference != f"tushare:{api}:{code}:{period_end}"
        ):
            raise ValueError("registered_core_source_identity_mismatch")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_core_source_period_mismatch")
        return
    members = (
        None
        if definition.metric_id in {"CN_DR007", "CN_SHIBOR_ON_1W_3M"}
        else official_source_members(definition.metric_id, period_end)
    )
    if members is not None:
        supported = metric_definition(definition.metric_id, definition_version=METRIC_CATALOG_V0003)
        family = OFFICIAL_CONTEXT_FAMILY_BY_METRIC[definition.metric_id]
        fields = (
            "source_codes",
            "dimensions",
            "unit",
            "frequency",
            "release_event_family",
            "release_rule",
            "release_timezone",
        )
        if any(getattr(definition, field) != getattr(supported, field) for field in fields) or set(
            definition.allowed_units or (definition.unit,)
        ) != set(supported.allowed_units):
            raise ValueError("registered_official_source_contract_unsupported")
        if provider != OFFICIAL_CONTEXT_FAMILIES[family].provider or not any(
            member.dimensions == dimensions
            and member.unit == unit
            and member.period_kind == period_kind
            for member in members
        ):
            raise ValueError("registered_official_source_identity_mismatch")
        end = date.fromisoformat(period_end)
        start = date.fromisoformat(period_start)
        if period_kind == "business_day":
            valid_period = start == end
        else:
            start_month = (end.month - 1) // 3 * 3 + 1 if period_kind == "quarter" else end.month
            if period_kind.startswith("year_to_"):
                start_month = 1
            valid_period = (
                start == date(end.year, start_month, 1)
                and end.day == monthrange(end.year, end.month)[1]
            )
            if period_kind in {"quarter", "year_to_quarter"}:
                valid_period = valid_period and end.month % 3 == 0
        if not valid_period:
            raise ValueError("registered_official_source_period_mismatch")
        if end.month == 1 and definition.metric_id in {
            "CN_INDUSTRIAL_VA",
            "CN_INDUSTRIAL_FINANCE",
            "CN_FINISHED_GOODS_INVENTORY",
            "CN_INVENTORY_TURNOVER",
        }:
            raise ValueError("registered_official_source_unreported_month")
        if (
            definition.metric_id == "CN_CAPACITY_UTILIZATION"
            and end.month == 3
            and dimensions.get("measure") == "ytd_rate"
        ):
            raise ValueError("registered_capacity_q1_mapping_unresolved")
        return
    from pring_cycle.tushare_context import (
        MARKET_INDEX_IDENTITIES,
        VALUATION_FIELDS,
        VALUATION_INDEX_CODES,
    )

    contracts = {
        "CN_LPR_1Y_5Y": ("lpr", "中国货币网"),
        "CN_CPI_HEADLINE": ("cpi", "国家统计局"),
        "CN_CORE_CPI": ("cpi", "国家统计局"),
        "CN_RRR_EVENT": ("rrr", "中国人民银行"),
        "CN_DR007": ("interbank", "tushare"),
        "CN_SHIBOR_ON_1W_3M": ("interbank", "tushare"),
        "CN_FUTURES_WARRANTS": ("warrant", "tushare"),
        "CN_MARGIN_BALANCE": ("margin", "tushare"),
        "CN_INDEX_VALUATION": ("valuation", "tushare"),
    }
    contracts.update(
        {metric_id: ("market_index", "tushare") for metric_id in MARKET_INDEX_IDENTITIES}
    )
    if definition.metric_id not in contracts:
        raise ValueError(f"registered_source_contract_not_implemented:{definition.metric_id}")
    family, supported_provider = contracts[definition.metric_id]
    supported = metric_definition(definition.metric_id)
    if family in {"interbank", "rrr", "warrant", "margin", "market_index", "valuation"}:
        supported = metric_definition(definition.metric_id, definition_version=METRIC_CATALOG_V0003)
    if family == "cpi":
        # Headline and core values are fields of the same NBS publication.
        supported = replace(supported, release_event_family="nbs_core_cpi")
    fields = (
        "source_codes",
        "dimensions",
        "unit",
        "frequency",
        "release_event_family",
        "release_rule",
        "release_timezone",
    )
    if any(getattr(definition, field) != getattr(supported, field) for field in fields) or set(
        definition.allowed_units or (definition.unit,)
    ) != set(supported.allowed_units or (supported.unit,)):
        raise ValueError(f"registered_{family}_source_contract_unsupported")
    if family == "valuation":
        valuation_measure = dimensions.get("measure", "")
        measures = {measure: (field, unit) for field, measure, unit in VALUATION_FIELDS}
        source_field, expected_unit = measures.get(valuation_measure, ("", ""))
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or set(dimensions) != {"index", "measure"}
            or dimensions.get("index") not in VALUATION_INDEX_CODES
            or valuation_measure not in measures
            or unit != expected_unit
            or source_reference != f"tushare:index_dailybasic:{source_field}:{period_end}"
        ):
            raise ValueError("registered_valuation_source_identity_mismatch")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_valuation_source_period_mismatch")
        return
    if family == "market_index":
        api_name, source_code = MARKET_INDEX_IDENTITIES[definition.metric_id]
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions != {"source_code": source_code}
            or unit != "index_points"
            or source_reference != f"tushare:{api_name}:close:{period_end}"
        ):
            raise ValueError("registered_market_index_source_identity_mismatch")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_market_index_source_period_mismatch")
        return
    if family == "margin":
        measure = dimensions.get("measure")
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions != {"measure": measure, "scope": "all_exchanges"}
            or measure not in {"financing_balance", "financing_buy_amount"}
            or unit != "hundred_million_cny"
            or source_reference != f"tushare:margin:{measure}:{period_end}"
        ):
            raise ValueError("registered_margin_source_identity_mismatch")
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_margin_source_period_mismatch")
        from pring_cycle.acquisition import AcquisitionRepository
        from pring_cycle.tushare_context import parse_margin_acquisition

        if not acquisition_ids:
            raise ValueError("registered_margin_acquisition_missing")
        acquisitions = AcquisitionRepository(
            database_path, database_path.parent / "artifacts" / "sha256"
        )
        for identity in acquisition_ids:
            receipt = acquisitions.get(identity)
            if receipt.state != "validated":
                raise ValueError("registered_margin_acquisition_not_validated")
            scalars = parse_margin_acquisition(receipt, acquisitions.read_content(identity, "raw"))
            if not any(
                scalar.period_start == period_start
                and scalar.period_end == period_end
                and scalar.dimensions == dimensions
                and scalar.unit == unit
                and scalar.value == value
                for scalar in scalars
            ):
                raise ValueError("registered_margin_acquisition_value_mismatch")
        return
    if family == "warrant":
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or set(dimensions) != {"symbol", "warehouse", "exchange", "measure"}
            or dimensions.get("symbol") not in {"CF", "CU", "PP", "RB", "RU", "SC", "SP", "TA"}
            or not dimensions.get("warehouse", "").strip()
            or not dimensions.get("exchange", "").strip()
            or dimensions.get("measure")
            not in {
                "previous_registered_receipts",
                "registered_receipts",
                "registered_receipts_change",
            }
            or unit not in supported.allowed_units
        ):
            raise ValueError("registered_warrant_source_identity_mismatch")
        try:
            start = date.fromisoformat(period_start)
            end = date.fromisoformat(period_end)
        except ValueError:
            raise ValueError("registered_warrant_source_period_mismatch") from None
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_warrant_source_period_mismatch")
        return
    if family == "rrr":
        units = {
            "rrr_change": "percentage_points",
            "post_change_rrr": "percent",
            "released_funds": "hundred_million_cny",
        }
        if (
            provider != supported_provider
            or period_kind != "event"
            or set(dimensions) != {"scope", "measure"}
            or not dimensions.get("scope", "").strip()
            or unit != units.get(dimensions.get("measure", ""))
        ):
            raise ValueError("registered_rrr_source_identity_mismatch")
        try:
            start = date.fromisoformat(period_start)
            end = date.fromisoformat(period_end)
        except ValueError:
            raise ValueError("registered_rrr_source_period_mismatch") from None
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_rrr_source_period_mismatch")
        return
    if family == "interbank":
        valid_dimensions = (
            dimensions == {}
            if definition.metric_id == "CN_DR007"
            else dimensions in ({"tenor": "overnight"}, {"tenor": "1w"}, {"tenor": "3m"})
        )
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or not valid_dimensions
            or unit != "percent"
        ):
            raise ValueError("registered_interbank_source_identity_mismatch")
        try:
            start = date.fromisoformat(period_start)
            end = date.fromisoformat(period_end)
        except ValueError:
            raise ValueError("registered_interbank_source_period_mismatch") from None
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_interbank_source_period_mismatch")
        return
    if family == "lpr":
        valid_dimensions = dimensions in ({"tenor": "1y"}, {"tenor": "5y_plus"})
    else:
        category = "headline" if definition.metric_id == "CN_CPI_HEADLINE" else "ex_food_energy"
        valid_dimensions = any(
            dimensions == {"category": category, "measure": measure}
            for measure in ("mom", "yoy", "cumulative_average_yoy")
        )
    if provider != supported_provider or period_kind != "month" or not valid_dimensions:
        raise ValueError(f"registered_{family}_source_identity_mismatch")


def require_model_source_contract(manifest: Mapping[str, object]) -> None:
    require_source_contract(str(manifest.get("metric_catalog_version", "")))
    definitions = manifest.get("metric_definitions")
    if isinstance(definitions, (list, tuple)):
        for definition in definitions:
            if isinstance(definition, dict):
                require_source_contract(
                    str(definition.get("definition_version", "")),
                    metric_id=str(definition.get("metric_id", "")),
                )


def require_stored_model_source_contract(
    connection: sqlite3.Connection, model_version_id: str
) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='model_version'"
        ).fetchone()
        is None
    ):
        return
    model = connection.execute(
        "SELECT manifest_json FROM model_version WHERE model_version_id=?", (model_version_id,)
    ).fetchone()
    if model is not None:
        require_model_source_contract(json.loads(str(model[0])))


def active_source_contract_review(database: Path) -> dict[str, Any] | None:
    from pring_cycle.models import ModelRepository

    models = ModelRepository(database)
    try:
        model = models.active()
    except LookupError:
        return None
    return source_contract_review(
        str(models.manifest(model.model_version_id).get("metric_catalog_version", ""))
    )
