from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pring_cycle.adapters import CORE_SOURCE_CODES
from pring_cycle.catalog import METRIC_CATALOG_V0003, MetricDefinition, metric_definition
from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS
from pring_cycle.metric_contracts import official_source_members
from pring_cycle.source_families import (
    OFFICIAL_CONTEXT_FAMILIES,
    OFFICIAL_CONTEXT_FAMILY_BY_METRIC,
    TUSHARE_CPI_FIELDS,
    TUSHARE_CPI_SOURCE_CODE,
    TUSHARE_GDP_FIELDS,
    TUSHARE_GDP_SOURCE_CODE,
    TUSHARE_MONEY_FIELDS,
    TUSHARE_MONEY_SOURCE_CODE,
    TUSHARE_PMI_FIELDS,
    TUSHARE_PMI_SOURCE_CODE,
    TUSHARE_PPI_FIELDS,
    TUSHARE_PPI_SOURCE_CODE,
    TUSHARE_SF_TOTAL_FIELDS,
    TUSHARE_SF_TOTAL_SOURCE_CODE,
)
from pring_cycle.storage import artifact_is_registered, database_connection

SOURCE_MAPPING_REFERENCE_CONTRACT_VERSION = "source-mapping-reference-v0001"
_MAPPING_REFERENCE_PREFIX = "source-field-mapping:"

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
    release_at: datetime | None = None,
    public_available_at: datetime | None = None,
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
        dual_ppi = definition.metric_id == "CN_PPI" and definition.source_codes == (
            *supported.source_codes,
            TUSHARE_PPI_SOURCE_CODE,
        )
        dual_pmi = definition.metric_id in {
            "CN_PMI_ACTIVITY",
            "CN_PMI_INVENTORY",
            "CN_PMI_PRICES",
        } and definition.source_codes == (*supported.source_codes, TUSHARE_PMI_SOURCE_CODE)
        dual_money = definition.metric_id == "CN_M1_M2" and definition.source_codes == (
            *supported.source_codes,
            TUSHARE_MONEY_SOURCE_CODE,
        )
        dual_sf = definition.metric_id == "CN_SF_TOTAL" and definition.source_codes == (
            *supported.source_codes,
            TUSHARE_SF_TOTAL_SOURCE_CODE,
        )
        dual_gdp = definition.metric_id == "CN_GDP" and definition.source_codes == (
            *supported.source_codes,
            TUSHARE_GDP_SOURCE_CODE,
        )
        if dual_ppi or dual_pmi or dual_money or dual_sf or dual_gdp:
            supported = replace(supported, source_codes=definition.source_codes)
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
        provider_matches = provider == OFFICIAL_CONTEXT_FAMILIES[family].provider
        if (dual_ppi or dual_pmi or dual_money or dual_sf or dual_gdp) and provider == "tushare":
            if dual_ppi:
                contract, api = "ppi", "cn_ppi"
                delivery_fields = tuple(
                    (field, {"category": category, "measure": measure})
                    for field, category, measure in TUSHARE_PPI_FIELDS
                )
            elif dual_pmi:
                contract, api = "pmi", "cn_pmi"
                delivery_fields = tuple(
                    (field, {"series": series, "measure": "level"})
                    for field, metric_id, series in TUSHARE_PMI_FIELDS
                    if metric_id == definition.metric_id
                )
            elif dual_money:
                contract, api = "money", "cn_m"
                delivery_fields = tuple(
                    (field, {"aggregate": aggregate, "measure": measure})
                    for field, aggregate, measure, _unit in TUSHARE_MONEY_FIELDS
                )
            elif dual_sf:
                contract, api = "sf_total", "sf_month"
                delivery_fields = tuple(
                    (field, {"measure": measure})
                    for field, measure, _multiplier, _kind in TUSHARE_SF_TOTAL_FIELDS
                )
            else:
                contract, api = "gdp", "cn_gdp"
                delivery_fields = tuple(
                    (field, {"aggregate": aggregate, "measure": "nominal_ytd_level"})
                    for aggregate, field, _yoy in TUSHARE_GDP_FIELDS
                )
            # These APIs contain values and a statistical period, not a publication fact.
            # Until independently bound publication evidence is supported, this delivery
            # is SYSTEM-only; normalized metadata cannot prove its own PUBLIC timestamp.
            if release_at is not None or public_available_at is not None:
                raise ValueError(f"registered_{contract}_publication_evidence_required")
            provider_matches = bool(acquisition_ids) and any(
                dimensions == member_dimensions
                and source_reference == f"tushare:{api}:{field}:{period_end}"
                for field, member_dimensions in delivery_fields
            )
        if not provider_matches or not any(
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
            _require_capacity_q1_mapping(
                database_path,
                definition,
                source_reference,
                period_start,
                period_end,
                value,
                acquisition_ids,
                release_at,
                public_available_at,
            )
        return
    from pring_cycle.commodity_basket import (
        COMMODITY_FORMULA_VERSION,
        COMMODITY_METRICS,
        COMMODITY_SLEEVES,
        COMMODITY_SOURCE_CODE,
    )
    from pring_cycle.market_amount import AMOUNT_BREADTH_MEASURES, AMOUNT_BREADTH_SOURCE_CODE
    from pring_cycle.market_breadth import (
        DAILY_BREADTH_MEASURES,
        DAILY_BREADTH_SOURCE_CODE,
        WINDOW_BREADTH_MEASURES,
        WINDOW_BREADTH_SOURCE_CODE,
    )
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
        "UST2Y_NOMINAL_YIELD": ("treasury", "U.S. Department of the Treasury"),
        "UST10Y_NOMINAL_YIELD": ("treasury", "U.S. Department of the Treasury"),
    }
    contracts.update(
        {metric_id: ("market_index", "tushare") for metric_id in MARKET_INDEX_IDENTITIES}
    )
    contracts.update({metric: ("daily_breadth", "tushare") for metric in DAILY_BREADTH_MEASURES})
    contracts.update({metric: ("window_breadth", "tushare") for metric in WINDOW_BREADTH_MEASURES})
    contracts.update({metric: ("amount_breadth", "tushare") for metric in AMOUNT_BREADTH_MEASURES})
    contracts.update({metric: ("commodity_basket", "tushare") for metric in COMMODITY_METRICS})
    if definition.metric_id not in contracts:
        raise ValueError(f"registered_source_contract_not_implemented:{definition.metric_id}")
    family, supported_provider = contracts[definition.metric_id]
    supported = metric_definition(definition.metric_id)
    if family in {
        "interbank",
        "rrr",
        "warrant",
        "margin",
        "market_index",
        "valuation",
        "daily_breadth",
        "window_breadth",
        "amount_breadth",
        "commodity_basket",
    }:
        supported = metric_definition(definition.metric_id, definition_version=METRIC_CATALOG_V0003)
    if family == "amount_breadth":
        supported = replace(supported, source_codes=(AMOUNT_BREADTH_SOURCE_CODE,))
    if family == "commodity_basket":
        supported = replace(supported, source_codes=(COMMODITY_SOURCE_CODE,))
    if family == "window_breadth":
        supported = replace(supported, source_codes=(WINDOW_BREADTH_SOURCE_CODE,))
    if family == "daily_breadth":
        supported = replace(supported, source_codes=(DAILY_BREADTH_SOURCE_CODE,))
    if family == "cpi":
        # Headline and core values are fields of the same NBS publication.
        supported = replace(supported, release_event_family="nbs_core_cpi")
    dual_cpi = definition.metric_id == "CN_CPI_HEADLINE" and definition.source_codes == (
        *supported.source_codes,
        TUSHARE_CPI_SOURCE_CODE,
    )
    if dual_cpi:
        supported = replace(supported, source_codes=definition.source_codes)
    if family == "treasury":
        # Keep the existing scalar economic definition, with an explicit official transport.
        from pring_cycle.treasury_context import TREASURY_SOURCE_CODES, treasury_yield_endpoint

        supported = replace(
            supported,
            source_codes=TREASURY_SOURCE_CODES[definition.metric_id],
            release_event_family="treasury_nominal_yields_csv",
            release_timezone="America/New_York",
        )
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
    if family == "commodity_basket":
        basket = definition.metric_id == "CN_COMMODITY_EX_HOG_BASKET"
        field = "level" if basket else dimensions.get("sleeve", "")
        expected = {"formula_version": COMMODITY_FORMULA_VERSION}
        if not basket:
            expected["sleeve"] = field
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions != expected
            or (not basket and field not in {s[0] for s in COMMODITY_SLEEVES})
            or unit != ("index_points" if basket else "percentage_points")
            or source_reference != f"tushare:commodity_basket:{field}:{period_end}"
            or period_start != period_end
            or date.fromisoformat(period_end).isoformat() != period_end
        ):
            raise ValueError("registered_commodity_basket_source_identity_mismatch")
        return
    if family == "amount_breadth":
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions
            != {"measure": "advancing_amount_share", "universe": "point_in_time_traded_a_shares"}
            or unit != "percent"
            or source_reference != f"tushare:amount_breadth:advancing_amount_share:{period_end}"
            or period_start != period_end
            or date.fromisoformat(period_end).isoformat() != period_end
        ):
            raise ValueError("registered_amount_breadth_source_identity_mismatch")
        return
    if family == "daily_breadth":
        breadth_measure = dimensions.get("measure")
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions
            != {"measure": breadth_measure, "universe": "point_in_time_traded_a_shares"}
            or breadth_measure not in DAILY_BREADTH_MEASURES[definition.metric_id]
            or unit != ("count" if definition.metric_id == "CN_EQ_ADV_DEC" else "ratio")
            or source_reference != f"tushare:daily_breadth:{breadth_measure}:{period_end}"
            or period_start != period_end
            or date.fromisoformat(period_end).isoformat() != period_end
        ):
            raise ValueError("registered_daily_breadth_source_identity_mismatch")
        return
    if family == "window_breadth":
        breadth_measure = dimensions.get("measure")
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions
            != {"measure": breadth_measure, "universe": "point_in_time_traded_a_shares"}
            or breadth_measure not in WINDOW_BREADTH_MEASURES[definition.metric_id]
            or unit != ("percent" if definition.metric_id == "CN_EQ_ABOVE_MA120" else "count")
            or source_reference != f"tushare:window_breadth:{breadth_measure}:{period_end}"
            or period_start != period_end
            or date.fromisoformat(period_end).isoformat() != period_end
        ):
            raise ValueError("registered_window_breadth_source_identity_mismatch")
        return
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
    if family == "treasury":
        try:
            start = date.fromisoformat(period_start)
            end = date.fromisoformat(period_end)
        except ValueError:
            raise ValueError("registered_treasury_source_period_mismatch") from None
        if start != end or start.isoformat() != period_start or end.isoformat() != period_end:
            raise ValueError("registered_treasury_source_period_mismatch")
        if (
            provider != supported_provider
            or period_kind != "business_day"
            or dimensions != {}
            or unit != "percent"
            or source_reference != f"{treasury_yield_endpoint(end.year)}#date={period_end}"
        ):
            raise ValueError("registered_treasury_source_identity_mismatch")
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
    provider_matches = provider == supported_provider
    if dual_cpi and provider == "tushare":
        # The statistical month in cn_cpi is not evidence of a publication timestamp.
        if release_at is not None or public_available_at is not None:
            raise ValueError("registered_cpi_publication_evidence_required")
        provider_matches = bool(acquisition_ids) and any(
            dimensions == {"category": "headline", "measure": measure}
            and source_reference == f"tushare:cn_cpi:{field}:{period_end}"
            for field, measure in TUSHARE_CPI_FIELDS
        )
        start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
        if start != date(end.year, end.month, 1) or end.day != monthrange(end.year, end.month)[1]:
            raise ValueError("registered_cpi_source_period_mismatch")
    if not provider_matches or period_kind != "month" or not valid_dimensions:
        raise ValueError(f"registered_{family}_source_identity_mismatch")


def _mapping_hash(document: object) -> str:
    return hashlib.sha256(
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _mapping_artifact(database: Path, digest: object, source_reference: str | None = None) -> bytes:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("capacity_mapping_artifact_hash_invalid")
    raw = (database.parent / "artifacts" / "sha256" / digest[:2] / digest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("capacity_mapping_artifact_hash_mismatch")
    if source_reference is not None and not artifact_is_registered(
        database, digest, source_reference
    ):
        raise ValueError("capacity_mapping_artifact_reference_mismatch")
    return raw


def _is_typed_mapping_reference(reference: Mapping[str, Any]) -> bool:
    source_reference = reference["source_reference"]
    if not source_reference.startswith(_MAPPING_REFERENCE_PREFIX):
        return False
    if source_reference != f"{_MAPPING_REFERENCE_PREFIX}{reference['artifact_hash']}":
        raise ValueError("capacity_mapping_reference_identity_mismatch")
    return True


def _has_admitted_mapping_reference_contract(database: Path, manifest: dict[str, Any]) -> bool:
    contract = manifest.get("source_mapping_reference_contract")
    if contract is None:
        return False  # Old catalogs never gain a new interpretation of their references.
    request_hash = manifest["certification_request_hash"]
    if contract != {
        "version": SOURCE_MAPPING_REFERENCE_CONTRACT_VERSION,
        "request_hash": request_hash,
    }:
        raise ValueError("capacity_mapping_reference_contract_invalid")
    request = json.loads(_mapping_artifact(database, request_hash))
    original = request["manifest"]
    if not isinstance(original, dict) or "source_mapping_reference_contract" in original:
        raise ValueError("capacity_mapping_reference_contract_self_declared")
    requested_manifest = {
        key: value
        for key, value in manifest.items()
        if key
        not in {
            "model_version_id",
            "source_certification_packages",
            "certification_request_hash",
            "source_mapping_reference_contract",
        }
    }
    if original != requested_manifest:
        raise ValueError("capacity_mapping_admission_request_mismatch")
    return True


def _registered_capacity_mappings(
    database: Path, definition: MetricDefinition
) -> list[dict[str, Any]]:
    # The first admitting model owns this catalog's grants; a later model using
    # the same definitions cannot expand the catalog's accepted source vintages.
    with database_connection(f"{database.resolve().as_uri()}?mode=ro", uri=True) as connection:
        row = connection.execute(
            """SELECT m.manifest_json FROM registered_metric_catalog c
            JOIN model_version m ON m.model_version_id=c.admitted_by_model_id
            WHERE c.catalog_version=?""",
            (definition.definition_version,),
        ).fetchone()
    if row is None:
        return []
    manifest = json.loads(row[0])
    typed_contract = _has_admitted_mapping_reference_contract(database, manifest)
    definition_hash = _mapping_hash(asdict(definition))
    mappings = []
    for stored in manifest["source_certification_packages"]:
        if stored["definition_bindings"].get(definition.metric_id) != definition_hash:
            continue
        package_hash = stored["package_id"].removeprefix("source-certification-")
        package = json.loads(_mapping_artifact(database, package_hash))
        if package != {key: value for key, value in stored.items() if key != "package_id"}:
            raise ValueError("capacity_mapping_package_binding_mismatch")
        review = json.loads(_mapping_artifact(database, package["review_hash"]))
        subject = {
            key: value
            for key, value in package.items()
            if key not in {"schema_version", "review_hash"}
        }
        if (
            review.get("schema_version") != "source-certification-review-v0001"
            or review.get("decision") != "accepted"
            or review.get("subject_hash") != _mapping_hash(subject)
        ):
            raise ValueError("capacity_mapping_review_binding_mismatch")
        by_criterion: dict[str, dict[str, dict[str, Any]]] = {}
        typed_by_criterion: dict[str, set[str]] = {}
        required_criteria = review["assessments"] if typed_contract else ("semantics", "fields")
        for criterion in required_criteria:
            documents = {}
            typed_hashes = set()
            for reference in review["assessments"][criterion]["evidence"]:
                typed = typed_contract and _is_typed_mapping_reference(reference)
                try:
                    raw = _mapping_artifact(
                        database, reference["artifact_hash"], reference["source_reference"]
                    )
                except (OSError, LookupError, TypeError, ValueError):
                    if typed:
                        continue  # This independent grant cannot qualify any selected claim.
                    raise  # Unclassified/common review evidence is still required.
                try:
                    document = json.loads(raw)
                except (UnicodeDecodeError, ValueError):
                    if typed:
                        raise ValueError("capacity_mapping_reference_requires_mapping") from None
                    continue  # Ordinary review evidence may be HTML, PDF, or Markdown.
                if (
                    isinstance(document, dict)
                    and document.get("schema_version") == "source-field-mapping-v0001"
                ):
                    documents[reference["artifact_hash"]] = document
                    if typed:
                        typed_hashes.add(reference["artifact_hash"])
                elif typed:
                    raise ValueError("capacity_mapping_reference_requires_mapping")
            by_criterion[criterion] = documents
            typed_by_criterion[criterion] = typed_hashes
        for digest in by_criterion["semantics"].keys() & by_criterion["fields"].keys():
            mapping = by_criterion["semantics"][digest]
            if (
                mapping.get("metric_id") == definition.metric_id
                and mapping.get("definition_version") == definition.definition_version
                and mapping.get("definition_hash") == definition_hash
                and mapping.get("rule_version") == "capacity_q1_same_interval_alias_v0001"
            ):
                typed = digest in typed_by_criterion["semantics"] & typed_by_criterion["fields"]
                if not typed:
                    # Preserve the complete legacy dependency chain. Only newly
                    # admitted typed grants can defer their independent basis.
                    basis = mapping["basis"]
                    if not _mapping_artifact(
                        database, basis["artifact_hash"], basis["source_reference"]
                    ):
                        raise ValueError("capacity_mapping_basis_empty")
                mappings.append(mapping)
    return mappings


def require_reviewed_source_mappings(
    database: Path,
    package: Mapping[str, Any],
    definitions: Mapping[str, dict[str, Any]],
) -> None:
    """Validate explicit mapping evidence before admitting its source package."""
    from pring_cycle.official_context import (
        capacity_q1_alias_value,
        parse_official_context_document,
    )

    try:
        review = json.loads(_mapping_artifact(database, package["review_hash"]))
        mappings: dict[str, dict[str, Any]] = {}
        criteria: dict[str, set[str]] = {}
        references: dict[str, dict[str, set[str]]] = {}
        for criterion, assessment in review["assessments"].items():
            for reference in assessment["evidence"]:
                typed = _is_typed_mapping_reference(reference)
                raw = _mapping_artifact(
                    database, reference["artifact_hash"], reference["source_reference"]
                )
                try:
                    document = json.loads(raw)
                except (UnicodeDecodeError, ValueError):
                    if typed:
                        raise ValueError("capacity_mapping_reference_requires_mapping") from None
                    continue
                is_mapping = isinstance(document, dict) and str(
                    document.get("schema_version", "")
                ).startswith("source-field-mapping-")
                if typed and not is_mapping:
                    raise ValueError("capacity_mapping_reference_requires_mapping")
                if is_mapping:
                    digest = reference["artifact_hash"]
                    mappings[digest] = document
                    criteria.setdefault(digest, set()).add(criterion)
                    references.setdefault(digest, {}).setdefault(criterion, set()).add(
                        reference["source_reference"]
                    )
        for digest, mapping in mappings.items():
            typed_reference = f"{_MAPPING_REFERENCE_PREFIX}{digest}"
            if any(typed_reference in items for items in references[digest].values()) and any(
                references[digest].get(criterion) != {typed_reference}
                for criterion in ("semantics", "fields")
            ):
                raise ValueError("capacity_mapping_reference_roles_mixed")
            definition = definitions[mapping["metric_id"]]
            parser = mapping["parser"]
            period = parser["period"]
            if (
                mapping["schema_version"] != "source-field-mapping-v0001"
                or mapping["rule_version"] != "capacity_q1_same_interval_alias_v0001"
                or mapping["metric_id"] != "CN_CAPACITY_UTILIZATION"
                or not {"semantics", "fields"} <= criteria[digest]
                or mapping["definition_version"] != definition["definition_version"]
                or mapping["definition_hash"] != _mapping_hash(definition)
                or package["definition_bindings"].get(mapping["metric_id"])
                != mapping["definition_hash"]
                or re.fullmatch(r"[0-9]{4}-Q1", period) is None
                or parser
                != {
                    "version": "official-context-parser-v0004",
                    "family": "nbs_capacity_utilization",
                    "period": period,
                }
            ):
                raise ValueError("capacity_mapping_review_identity_mismatch")
            source = mapping["source_document"]
            raw = _mapping_artifact(database, source["artifact_hash"], source["source_reference"])
            if source["bytes"] != len(raw):
                raise ValueError("capacity_mapping_source_size_mismatch")
            basis = mapping["basis"]
            if not _mapping_artifact(database, basis["artifact_hash"], basis["source_reference"]):
                raise ValueError("capacity_mapping_basis_empty")
            parsed = parse_official_context_document(
                raw,
                family="nbs_capacity_utilization",
                source_url=source["source_reference"],
                expected_period=period,
                fetched_at=datetime.fromisoformat(review["reviewed_at"]),
            )
            actual = capacity_q1_alias_value(raw, period)
            for name, measure in (("source", "quarter_rate"), ("target", "ytd_rate")):
                scalar = next(
                    s
                    for s in parsed.scalars
                    if s.dimensions == {"industry": "all_industry", "measure": measure}
                )
                expected = {
                    field: getattr(scalar, field)
                    for field in (
                        "source_field",
                        "dimensions",
                        "period_kind",
                        "period_start",
                        "period_end",
                        "unit",
                        "value",
                    )
                }
                if (
                    mapping[name] != expected
                    or scalar.value != actual
                    or isinstance(mapping[name]["value"], bool)
                ):
                    raise ValueError("capacity_mapping_source_cell_mismatch")
    except (OSError, LookupError, TypeError, ValueError, StopIteration) as error:
        raise ValueError("certification_source_mapping_invalid") from error


def _require_capacity_q1_mapping(
    database: Path,
    definition: MetricDefinition,
    source_reference: str,
    period_start: str,
    period_end: str,
    value: float | None,
    acquisition_ids: tuple[str, ...],
    release_at: datetime | None,
    public_available_at: datetime | None,
) -> None:
    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.official_context import capacity_q1_alias_value, parse_official_acquisition

    try:
        mappings = _registered_capacity_mappings(database, definition)
        if not mappings or not acquisition_ids:
            raise ValueError("capacity_mapping_evidence_missing")
        repository = AcquisitionRepository(database, database.parent / "artifacts" / "sha256")
        for acquisition_id in acquisition_ids:
            receipt = repository.get(acquisition_id)
            raw = repository.read_content(acquisition_id, "raw")
            repository.read_content(acquisition_id, "normalized")
            parsed = parse_official_acquisition(receipt, raw)
            if (
                receipt.validated_at is None
                or receipt.received_at is None
                or not receipt.started_at <= receipt.received_at <= receipt.validated_at
                or parsed.family != "nbs_capacity_utilization"
                or source_reference != f"{parsed.source_url}#sha256={receipt.raw_hash}"
                or (
                    (release_at is not None or public_available_at is not None)
                    and (release_at, public_available_at)
                    != (parsed.release_at, parsed.public_available_at)
                )
            ):
                raise ValueError("capacity_mapping_acquisition_mismatch")
            actual = capacity_q1_alias_value(raw, parsed.period)
            source = {
                "source_field": "industrial_capacity_utilization_pct",
                "dimensions": {"industry": "all_industry", "measure": "quarter_rate"},
                "period_kind": "quarter",
                "period_start": period_start,
                "period_end": period_end,
                "unit": "percent",
                "value": actual,
            }
            target = {
                **source,
                "source_field": "industrial_capacity_utilization_ytd_pct",
                "dimensions": {"industry": "all_industry", "measure": "ytd_rate"},
                "period_kind": "year_to_quarter",
            }
            if value != actual or not any(
                scalar.metric_id == definition.metric_id
                and scalar.period_start == period_start
                and scalar.period_end == period_end
                and scalar.dimensions == target["dimensions"]
                and scalar.value == actual
                for scalar in parsed.scalars
            ):
                raise ValueError("capacity_mapping_claim_mismatch")
            matching = [
                mapping
                for mapping in mappings
                if mapping["source_document"]
                == {
                    "artifact_hash": receipt.raw_hash,
                    "source_reference": parsed.source_url,
                    "bytes": len(raw),
                }
                and mapping["parser"]
                == {
                    "version": receipt.parser_version,
                    "family": parsed.family,
                    "period": parsed.period,
                }
                and mapping["source"] == source
                and mapping["target"] == target
                and not isinstance(mapping["source"]["value"], bool)
                and not isinstance(mapping["target"]["value"], bool)
            ]
            if not matching:
                raise ValueError("capacity_mapping_source_cell_mismatch")
            for mapping in matching:
                try:
                    basis = mapping["basis"]
                    if _mapping_artifact(
                        database, basis["artifact_hash"], basis["source_reference"]
                    ):
                        break
                except (OSError, LookupError, TypeError, ValueError):
                    continue
            else:
                raise ValueError("capacity_mapping_basis_unavailable")
    except (OSError, LookupError, TypeError, ValueError) as error:
        raise ValueError("registered_capacity_q1_mapping_unresolved") from error


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
