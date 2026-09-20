from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any

from pring_cycle.catalog import metric_catalog_v0003
from pring_cycle.models import (
    ModelRepository,
    certified_120d_model_v0011_manifest,
)
from pring_cycle.rehearsals import verify_source_smoke_artifacts
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_contract_review import require_source_contract

_DERIVED_P1 = {
    "CN_DR007_POLICY_SPREAD",
    "CN_ORDER_INVENTORY_SPREAD",
    "CN_PRODUCTION_ORDER_SPREAD",
    "CN_CREDIT_IMPULSE",
}
_TUSHARE_CONTEXT_P1 = {
    "CN_PMI_ACTIVITY",
    "CN_PMI_INVENTORY",
    "CN_PMI_PRICES",
    "CN_CPI_HEADLINE",
    "CN_PPI",
    "CN_M1_M2",
    "CN_SF_TOTAL",
    "CN_FUTURES_WARRANTS",
    "CN_DR007",
    "CN_SHIBOR_ON_1W_3M",
}
_TUSHARE_MARKET_P1 = {
    "CN_EQ_CSI300",
    "CN_EQ_CSI500",
    "CN_EQ_CSI1000",
    "CN_EQ_ADV_DEC",
    "CN_EQ_AD_RATIO",
    "CN_EQ_NEW_HIGH_LOW_120",
    "CN_EQ_ABOVE_MA120",
    "CN_EQ_ADV_AMOUNT_SHARE",
    "CN_MARGIN_BALANCE",
    "CN_INDEX_VALUATION",
    "CN_BOND_FULL_PRICE_CNY030",
    "CN_BOND_10Y_930916",
    "CN_COMMODITY_BROAD_NHCI",
    "CN_COMMODITY_EX_HOG_BASKET",
    "CN_COMMODITY_SLEEVE_CONTRIBUTION",
}
_OFFICIAL_DIRECT_P1 = {
    "CN_PMI_ACTIVITY",
    "CN_PMI_INVENTORY",
    "CN_PMI_PRICES",
    "CN_CPI_HEADLINE",
    "CN_PPI",
    "CN_M1_M2",
    "CN_LPR_1Y_5Y",
    "CN_OMO_7D_RATE",
    "CN_OMO_7D_AMOUNT",
    "CN_RRR_EVENT",
    "CN_TOOL_LIQUIDITY_MONTHLY",
    "CN_SF_TOTAL",
    "CN_SF_COMPONENTS",
    "CN_LOAN_STRUCTURE",
    "CN_CORE_CPI",
    "CN_INDUSTRIAL_VA",
    "CN_INDUSTRIAL_FINANCE",
    "CN_FINISHED_GOODS_INVENTORY",
    "CN_INVENTORY_TURNOVER",
    "CN_CAPACITY_UTILIZATION",
}
_TUSHARE_PUBLIC_P2 = {
    "CN_GDP",
    "UST10Y_NOMINAL_YIELD",
    "UST2Y_NOMINAL_YIELD",
}
_DERIVED_PUBLIC_P2 = {"UST_2S10S_SPREAD"}
_TUSHARE_REVIEW_EVIDENCE = (
    {
        "document": "docs/research/tushare-indicator-capability-audit.md",
        "sha256": "a1d8c8400b70e9a22444581645128dc245743968e69258e550315d2736631864",
    },
)
_MARKET_REVIEW_EVIDENCE = (
    {
        "document": "docs/research/china-equity-core-proxy.md",
        "sha256": "9e23afc84a7688c33020fe87b2322b5998d04f2711558e60e29975e1adf77317",
    },
    {
        "document": "docs/research/nhii-historical-constituents-and-methods.md",
        "sha256": "920ed9d6ab42b9c2a102f78fd6b78ba1abbc95b15b090effea7da2222d97fdf2",
    },
)
_OFFICIAL_REVIEW_EVIDENCE = (
    {
        "document": "docs/research/official-gap-source-audit.md",
        "sha256": "17e7f9c5bf94bbaf14c33a481064b868a7b51be22b90eef556fcb3d7bfe95a24",
    },
)


def create_source_certified_candidate(
    paths: RuntimePaths,
    *,
    target_business_date: str,
    source_smoke_hashes: tuple[str, ...],
    personal_noncommercial_use_approved: bool,
) -> dict[str, object]:
    if not personal_noncommercial_use_approved:
        raise ValueError("tushare_personal_noncommercial_use_must_be_confirmed")
    require_source_contract("metric-catalog-v0003")
    verified = verify_source_smoke_artifacts(
        paths,
        source_smoke_hashes,
        target_business_date=target_business_date,
    )
    if "tushare-market" not in verified:
        raise ValueError("source_certification_market_smoke_missing")
    if "source-history" not in verified:
        raise ValueError("source_certification_history_smoke_missing")
    direct_p1 = {
        item.metric_id
        for item in metric_catalog_v0003()
        if item.priority == "P1" and item.metric_id not in _DERIVED_P1
    }
    covered = _TUSHARE_CONTEXT_P1 | _TUSHARE_MARKET_P1 | _OFFICIAL_DIRECT_P1
    if covered != direct_p1:
        missing = ",".join(sorted(direct_p1 - covered))
        unexpected = ",".join(sorted(covered - direct_p1))
        raise ValueError(f"source_certification_p1_coverage_invalid:{missing}:{unexpected}")
    official_hashes = [
        content_hash
        for kind, content_hash in sorted(verified.items())
        if kind == "lpr" or kind.startswith("official-context:")
    ]
    history_hash = verified["source-history"]
    packages = (
        _package(
            "tushare-context-structured-delivery-v0001",
            metrics=sorted(_TUSHARE_CONTEXT_P1),
            smoke_hashes=[verified["tushare-context"]],
            terms={
                "agreement": "https://tushare.pro/document/1?doc_id=405",
                "scope": "local_personal_noncommercial_nontransferable",
                "redistribution": "prohibited_without_separate_permission",
            },
            review_evidence=_TUSHARE_REVIEW_EVIDENCE,
            official_direct_smoke_hashes=official_hashes,
        ),
        _package(
            "tushare-market-structured-delivery-v0001",
            metrics=sorted(_TUSHARE_MARKET_P1),
            smoke_hashes=[verified["core"], verified["tushare-market"]],
            terms={
                "agreement": "https://tushare.pro/document/1?doc_id=405",
                "scope": "local_personal_noncommercial_nontransferable",
                "redistribution": "prohibited_without_separate_permission",
            },
            review_evidence=_MARKET_REVIEW_EVIDENCE,
            official_direct_smoke_hashes=[],
        ),
        _package(
            "official-direct-delivery-v0001",
            metrics=sorted(_OFFICIAL_DIRECT_P1),
            smoke_hashes=[*official_hashes, history_hash],
            terms={
                "scope": "local_analysis_with_source_attribution",
                "source_identity": "publisher_official_https",
            },
            review_evidence=_OFFICIAL_REVIEW_EVIDENCE,
            official_direct_smoke_hashes=official_hashes,
        ),
        _package(
            "derived-from-certified-inputs-v0001",
            metrics=sorted(_DERIVED_P1),
            smoke_hashes=[],
            terms={"scope": "formula_outputs_only", "source_claims": "not_applicable"},
            review_evidence=(),
            official_direct_smoke_hashes=[],
        ),
        _package(
            "tushare-public-p2-delivery-v0001",
            metrics=sorted(_TUSHARE_PUBLIC_P2),
            smoke_hashes=[verified["tushare-context"]],
            terms={
                "agreement": "https://tushare.pro/document/1?doc_id=405",
                "scope": "local_personal_noncommercial_nontransferable",
                "redistribution": "prohibited_without_separate_permission",
            },
            review_evidence=_TUSHARE_REVIEW_EVIDENCE,
            official_direct_smoke_hashes=official_hashes,
        ),
        _package(
            "derived-public-p2-v0001",
            metrics=sorted(_DERIVED_PUBLIC_P2),
            smoke_hashes=[],
            terms={"scope": "formula_outputs_only", "source_claims": "not_applicable"},
            review_evidence=(),
            official_direct_smoke_hashes=[],
        ),
    )
    certified_scope = {
        item.metric_id
        for item in metric_catalog_v0003()
        if item.priority in {"P1", "P2"}
        and item.certification_status in {"certified", "derived_from_certified_inputs"}
    }
    packaged_scope: set[str] = set()
    for package in packages:
        package_metrics = package.get("metrics")
        if not isinstance(package_metrics, list) or not all(
            isinstance(metric_id, str) for metric_id in package_metrics
        ):
            raise ValueError("source_certification_package_metrics_invalid")
        packaged_scope.update(package_metrics)
    if packaged_scope != certified_scope:
        missing = ",".join(sorted(certified_scope - packaged_scope))
        unexpected = ",".join(sorted(packaged_scope - certified_scope))
        raise ValueError(f"source_certification_scope_invalid:{missing}:{unexpected}")
    manifest = certified_120d_model_v0011_manifest(packages)
    model = ModelRepository(paths.database).create_candidate(manifest)
    return {
        "certified_p1_count": len(covered | _DERIVED_P1),
        "metric_catalog_version": manifest["metric_catalog_version"],
        "model": asdict(model),
        "packages": list(packages),
        "status": "candidate_created",
        "target_business_date": target_business_date,
    }


def refresh_source_certified_candidate(
    paths: RuntimePaths,
    *,
    model_version_id: str,
    target_business_date: str,
) -> dict[str, object]:
    """Populate the immutable v3 catalog without changing the active model."""
    from pring_cycle.core_history import refresh_core_history
    from pring_cycle.official_context import refresh_official_context_document
    from pring_cycle.official_lpr import refresh_lpr_release
    from pring_cycle.secrets import parse_data_source_secrets
    from pring_cycle.source_adapters import TushareCoreAdapter
    from pring_cycle.worker import refresh_context_sources

    models = ModelRepository(paths.database)
    model = models.get(model_version_id)
    manifest = models.manifest(model_version_id)
    if model.status != "candidate":
        raise ValueError("source_refresh_requires_candidate_model")
    definition_version = str(manifest.get("metric_catalog_version", ""))
    if definition_version != "metric-catalog-v0003":
        raise ValueError("source_refresh_catalog_version_invalid")
    require_source_contract(definition_version)
    packages = manifest.get("source_certification_packages")
    if not isinstance(packages, list):
        raise ValueError("source_certification_packages_missing")
    smoke_hashes = tuple(sorted(_package_smoke_hashes(packages)))
    verified = verify_source_smoke_artifacts(
        paths,
        smoke_hashes,
        target_business_date=target_business_date,
    )
    token = parse_data_source_secrets(paths.secrets).get("TUSHARE_TOKEN")
    if token is None:
        raise ValueError("tushare_not_configured")
    target = date.fromisoformat(target_business_date)
    history = refresh_core_history(
        paths,
        TushareCoreAdapter(token),
        start=date(2017, 1, 1),
        end=target,
        definition_version=definition_version,
    )
    refresh_context_sources(
        paths,
        target_business_date,
        definition_version=definition_version,
    )
    official_results: list[dict[str, object]] = []
    history_result: dict[str, object] | None = None
    history_identities: set[tuple[str, str, str]] = set()
    if history_hash := verified.get("source-history"):
        from pring_cycle.source_history import refresh_source_history

        history_document = _smoke_document(paths, history_hash)
        history_result = refresh_source_history(
            paths,
            smoke_document=history_document,
            definition_version=definition_version,
        )
        history_identities = _source_history_identities(history_document)
    for kind, content_hash in sorted(verified.items()):
        document = _smoke_document(paths, content_hash)
        source_url = str(document.get("final_url", ""))
        period = str(document.get("period", ""))
        family = "lpr" if kind == "lpr" else kind.removeprefix("official-context:")
        if (kind == "lpr" or kind.startswith("official-context:")) and (
            source_url,
            period,
            family,
        ) in history_identities:
            official_results.append(
                {
                    "family": kind,
                    "source_url": source_url,
                    "status": "covered_by_source_history",
                }
            )
            continue
        fetched_at = datetime.now(UTC)
        if kind == "lpr":
            official_result = asdict(
                refresh_lpr_release(
                    paths,
                    source_url=source_url,
                    expected_period=str(document["period"]),
                    fetched_at=fetched_at,
                    definition_version=definition_version,
                )
            )
        elif kind.startswith("official-context:"):
            official_result = asdict(
                refresh_official_context_document(
                    paths,
                    family=kind.removeprefix("official-context:"),
                    source_url=source_url,
                    expected_period=str(document["period"]),
                    fetched_at=fetched_at,
                    definition_version=definition_version,
                )
            )
        else:
            continue
        official_results.append(official_result)
    return {
        "core_history": asdict(history),
        "model_version_id": model_version_id,
        "official_refreshes": official_results,
        "source_history": history_result,
        "status": "candidate_sources_refreshed",
        "target_business_date": target_business_date,
    }


def _package(
    name: str,
    *,
    metrics: list[str],
    smoke_hashes: list[str],
    terms: dict[str, str],
    review_evidence: tuple[dict[str, str], ...],
    official_direct_smoke_hashes: list[str],
) -> dict[str, object]:
    document: dict[str, object] = {
        "metrics": metrics,
        "name": name,
        "official_direct_smoke_hashes": sorted(set(official_direct_smoke_hashes)),
        "review_evidence": [dict(item) for item in review_evidence],
        "schema_version": "source-certification-package-v0001",
        "smoke_hashes": sorted(set(smoke_hashes)),
        "terms": terms,
    }
    digest = hashlib.sha256(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {"package_id": f"source-certification-{digest}", **document}


def _source_history_identities(document: dict[str, Any]) -> set[tuple[str, str, str]]:
    records = document.get("records")
    if not isinstance(records, list):
        raise ValueError("source_history_smoke_records_missing")
    identities: set[tuple[str, str, str]] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        source_url = str(record.get("source_url", ""))
        period = str(record.get("period", ""))
        if not source_url or not period:
            continue
        if record.get("lpr") is True:
            identities.add((source_url, period, "lpr"))
        families = record.get("families", [])
        if isinstance(families, list):
            identities.update(
                (source_url, period, family)
                for family in families
                if isinstance(family, str) and family
            )
    if not identities:
        raise ValueError("source_history_smoke_identities_missing")
    return identities


def _package_smoke_hashes(packages: list[Any]) -> set[str]:
    hashes: set[str] = set()
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError("source_certification_package_invalid")
        for key in ("smoke_hashes", "official_direct_smoke_hashes"):
            values = package.get(key, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError("source_certification_package_hashes_invalid")
            hashes.update(values)
    return hashes


def _smoke_document(paths: RuntimePaths, content_hash: str) -> dict[str, Any]:
    artifact_path = paths.artifacts / content_hash[:2] / content_hash
    document = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("source_smoke_artifact_invalid")
    return document
