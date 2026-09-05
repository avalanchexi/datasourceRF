from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pring_cycle.catalog import METRIC_CATALOG_V0003

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
