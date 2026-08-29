from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from pring_cycle.artifacts import store_artifact
from pring_cycle.catalog import METRIC_CATALOG_VERSION
from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.navigation import DASHBOARD_NAVIGATION
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.reports import ReportRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint, fingerprint_matches
from pring_cycle.source_families import OFFICIAL_CONTEXT_FAMILIES
from pring_cycle.storage import artifact_is_registered

_P1_SCHEMA_FAMILIES = {
    "chinamoney_lpr": (("CN_LPR_1Y_5Y",), "中国货币网"),
    **{
        family: (descriptor.metric_ids, descriptor.provider)
        for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
        if descriptor.required_p1_rehearsal
    },
    "tushare_pmi": (
        ("CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"),
        "tushare",
    ),
    "tushare_prices": (("CN_CPI_HEADLINE", "CN_PPI"), "tushare"),
    "tushare_money": (("CN_M1_M2",), "tushare"),
    "tushare_social_financing": (("CN_SF_TOTAL",), "tushare"),
    "tushare_futures_warrants": (("CN_FUTURES_WARRANTS",), "tushare"),
    "tushare_transmission": (
        ("CN_DR007", "CN_SHIBOR_ON_1W_3M"),
        "tushare",
    ),
}


def run_fixture_recovery_rehearsal(paths: RuntimePaths) -> dict[str, Any]:
    paths.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fixture-rehearsal-", dir=paths.cache) as directory:
        fixture_paths = RuntimePaths.discover(Path(directory) / "runtime")
        initialize_runtime(fixture_paths)
        models = ModelRepository(fixture_paths.database)
        models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
        models.activate("model-v0001", explicitly_approved=True)
        runs = RunRepository(fixture_paths.database)
        cutoff = datetime(2026, 8, 28, 13, tzinfo=UTC)
        submitted = runs.submit_manual_full(
            target_business_date="2026-08-28",
            client_request_id="fixture-recovery-original",
            model_version_id="model-v0001",
            system_as_of=cutoff,
        )
        runs.acquire_lease(
            submitted.run_id,
            owner_id="fixture-dead-worker",
            process_id=999999,
            now=cutoff,
        )
        decision = runs.audit_lease(
            now=cutoff + timedelta(seconds=121),
            process_is_alive=lambda _process_id: False,
        )
        interrupted = runs.get(submitted.run_id)
        resumed = runs.resume(
            submitted.run_id,
            client_request_id="fixture-recovery-resume",
            confirm_external_calls=True,
        )
        document = {
            "acceptance_only": True,
            "attempt_count": resumed.attempt_count,
            "cutoffs_preserved": (
                resumed.system_as_of == submitted.system_as_of
                and resumed.report_cutoff == submitted.report_cutoff
            ),
            "interrupted_status": interrupted.status,
            "lease_audit": asdict(decision),
            "network_requests": 0,
            "publication_history_written": False,
            "resumed_status": resumed.status,
            "schema_version": "fixture-recovery-rehearsal-v0001",
            "status": "ok",
            **execution_fingerprint(paths),
        }
    return _store_rehearsal(paths, "fixture-recovery", document)


def run_real_projection_rehearsal(
    paths: RuntimePaths,
    *,
    target_business_date: str,
    dashboard_port: int,
    source_smoke_hashes: tuple[str, ...],
) -> dict[str, Any]:
    projection = ProjectionSetRepository(paths.database).current()
    if projection.envelope.target_business_date != target_business_date:
        raise ValueError("real_rehearsal_target_is_not_current_projection")
    overview = projection.datasets["cycle_overview"]
    assets = projection.datasets["core_assets"].get("assets")
    if not isinstance(assets, list) or len(assets) != 3:
        raise ValueError("real_rehearsal_p0_manifest_incomplete")
    if any(
        not isinstance(item, dict)
        or item.get("reason") != "validated"
        or int(item.get("observation_count", 0)) < 140
        or item.get("latest_business_date") != target_business_date
        for item in assets
    ):
        raise ValueError("real_rehearsal_p0_not_ready")
    macro = projection.datasets["macro"]
    inventory = projection.datasets["inventory"]
    inventory_cards = inventory.get("cards")
    projection_evidence_ids = _projection_evidence_ids(projection.datasets)
    model_rules = ContextProjectionRules.from_manifest(
        ModelRepository(paths.database).manifest(projection.envelope.model_version_id)
    )
    verified_smokes = verify_source_smoke_artifacts(
        paths,
        source_smoke_hashes,
        target_business_date=target_business_date,
    )
    p1_samples = {
        "inventory_cards": isinstance(inventory_cards, list) and len(inventory_cards) > 0,
        "macro_schema_family": all(
            macro.get(key) not in {None, "insufficient_data"}
            for key in ("policy_direction", "overheat_state", "price_pressure")
        ),
        **_certified_p1_schema_samples(
            paths,
            as_of=projection.envelope.system_as_of,
            projection_evidence_ids=projection_evidence_ids,
            definition_version=model_rules.metric_catalog_version,
        ),
    }
    if not all(p1_samples.values()):
        raise ValueError("real_rehearsal_p1_schema_sample_incomplete")
    reports = tuple(
        item
        for item in ReportRepository(paths.database).history()
        if item.projection_set_id == projection.envelope.projection_set_id
    )
    if not reports or reports[0].status not in {"completed", "completed_degraded"}:
        raise ValueError("real_rehearsal_report_missing")
    if overview.get("current_stage") is None and overview.get("stage_reason") not in {
        "noncanonical_combination",
        "core_state_unavailable",
    }:
        raise ValueError("real_rehearsal_stage_semantics_invalid")
    if not _dashboard_projection_visible(
        dashboard_port,
        projection_set_id=projection.envelope.projection_set_id,
    ):
        raise ValueError("real_rehearsal_dashboard_projection_not_visible")
    document = {
        "acceptance_only": True,
        "dashboard_projection_visible": True,
        "loopback_requests_during_validation": 3,
        "network_requests_during_validation": 0,
        "p0_assets": [str(item["metric_id"]) for item in assets if isinstance(item, dict)],
        "p1_schema_samples": p1_samples,
        "projection_set_id": projection.envelope.projection_set_id,
        "publication_history_written": False,
        "report_adapter": reports[0].adapter,
        "report_status": reports[0].status,
        "schema_version": "real-projection-rehearsal-v0001",
        "status": "ok",
        "source_smoke_hashes": list(source_smoke_hashes),
        "source_smoke_kinds": sorted(verified_smokes),
        "target_business_date": target_business_date,
        **execution_fingerprint(
            paths,
            model_version_id=projection.envelope.model_version_id,
        ),
    }
    return _store_rehearsal(paths, "real-projection", document)


def _certified_p1_schema_samples(
    paths: RuntimePaths,
    *,
    as_of: datetime,
    projection_evidence_ids: set[str],
    definition_version: str = METRIC_CATALOG_VERSION,
) -> dict[str, bool]:
    repository = EvidenceRepository(paths.database)
    samples: dict[str, bool] = {}
    for family, (metric_ids, provider) in _P1_SCHEMA_FAMILIES.items():
        metrics_ready = []
        for metric_id in metric_ids:
            metrics_ready.append(
                any(
                    point.selection_status == "selected"
                    and point.selected_claim_id in projection_evidence_ids
                    and any(
                        claim.claim_id == point.selected_claim_id
                        and claim.provider == provider
                        and claim.certification_status == "certified"
                        and claim.quality_status == "validated"
                        for claim in point.claims
                    )
                    for point in repository.metric_series(
                        metric_id,
                        mode=AsOfMode.SYSTEM,
                        as_of=as_of,
                        definition_version=definition_version,
                    )
                )
            )
        samples[family] = all(metrics_ready)
    return samples


def required_real_smoke_kinds() -> frozenset[str]:
    return frozenset(
        {
            "core",
            "eia",
            "lpr",
            "tushare-context",
            *(
                f"official-context:{family}"
                for family, descriptor in OFFICIAL_CONTEXT_FAMILIES.items()
                if descriptor.required_p1_rehearsal
            ),
        }
    )


def store_source_smoke_result(
    paths: RuntimePaths,
    *,
    kind: str,
    result: dict[str, Any],
    target_scope: dict[str, str],
) -> dict[str, Any]:
    allowed_kinds = required_real_smoke_kinds() | {
        f"official-context:{family}" for family in OFFICIAL_CONTEXT_FAMILIES
    }
    if kind not in allowed_kinds:
        raise ValueError("source_smoke_kind_invalid")
    status = result.get("status")
    if status not in {"validated", "validated_candidate"}:
        raise ValueError("source_smoke_status_invalid")
    document: dict[str, Any] = {
        **_json_safe_document(result),
        "schema_version": "source-smoke-v0001",
        "smoke_kind": kind,
        "target_scope": target_scope,
        **execution_fingerprint(paths),
    }
    normalized_hash = hashlib.sha256(_canonical_json(document).encode()).hexdigest()
    artifact_document = {**document, "normalized_result_hash": normalized_hash}
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        (_canonical_json(artifact_document) + "\n").encode(),
        media_type="application/json",
        source_reference=f"source-smoke:{kind}:{normalized_hash}",
    )
    return {
        **artifact_document,
        "artifact": {"hash": artifact.content_hash, "path": str(artifact.path)},
    }


def verify_source_smoke_artifacts(
    paths: RuntimePaths,
    hashes: tuple[str, ...],
    *,
    target_business_date: str,
) -> dict[str, str]:
    if not hashes or len(set(hashes)) != len(hashes):
        raise ValueError("real_rehearsal_source_smoke_hashes_invalid")
    verified: dict[str, str] = {}
    for content_hash in hashes:
        if len(content_hash) != 64:
            raise ValueError("source_smoke_artifact_hash_invalid")
        artifact_path = paths.artifacts / content_hash[:2] / content_hash
        try:
            content = artifact_path.read_bytes()
        except OSError as error:
            raise ValueError("source_smoke_artifact_missing") from error
        if hashlib.sha256(content).hexdigest() != content_hash:
            raise ValueError("source_smoke_artifact_hash_mismatch")
        try:
            document = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("source_smoke_artifact_invalid") from error
        if not isinstance(document, dict):
            raise ValueError("source_smoke_artifact_invalid")
        kind = document.get("smoke_kind")
        result_hash = document.get("normalized_result_hash")
        expected_status = (
            "validated" if kind in {"core", "lpr"} else "validated_candidate"
        )
        normalized_document = {
            str(key): value
            for key, value in document.items()
            if key != "normalized_result_hash"
        }
        computed_result_hash = hashlib.sha256(
            _canonical_json(normalized_document).encode()
        ).hexdigest()
        if (
            document.get("schema_version") != "source-smoke-v0001"
            or document.get("status") != expected_status
            or type(document.get("network_requests")) is not int
            or int(document["network_requests"]) < 1
            or not isinstance(kind, str)
            or not isinstance(result_hash, str)
            or len(result_hash) != 64
            or result_hash != computed_result_hash
            or not fingerprint_matches(document, execution_fingerprint(paths))
            or not artifact_is_registered(
                paths.database,
                content_hash,
                f"source-smoke:{kind}:{result_hash}",
            )
        ):
            raise ValueError("source_smoke_artifact_provenance_invalid")
        if not _smoke_scope_matches(
            document.get("target_scope"),
            target_business_date,
            kind=kind,
        ):
            raise ValueError("source_smoke_target_scope_mismatch")
        if not _source_smoke_shape_valid(
            kind,
            document,
            target_business_date=target_business_date,
        ):
            raise ValueError("source_smoke_artifact_shape_invalid")
        if kind in verified:
            raise ValueError("source_smoke_kind_duplicate")
        verified[kind] = content_hash
    missing = sorted(required_real_smoke_kinds() - verified.keys())
    if missing:
        raise ValueError("real_rehearsal_source_smoke_kinds_missing:" + ",".join(missing))
    return verified


def _smoke_scope_matches(
    value: object,
    target_business_date: str,
    *,
    kind: str,
) -> bool:
    if not isinstance(value, dict):
        return False
    target = str(value.get("target_business_date", ""))
    if target:
        return target == target_business_date
    period = str(value.get("period", ""))
    if period:
        if kind == "lpr":
            return period == target_business_date[:7]
        family = kind.removeprefix("official-context:")
        return _period_is_fresh_for_target(
            period,
            target_business_date,
            family=family,
        )
    start = str(value.get("start", ""))
    end = str(value.get("end", ""))
    return bool(start and end and start <= target_business_date <= end)


def _period_is_fresh_for_target(
    period: str,
    target_business_date: str,
    *,
    family: str,
) -> bool:
    try:
        target = date.fromisoformat(target_business_date)
        if len(period) == 10:
            period_end = date.fromisoformat(period)
            freshness = 370 if family == "pbc_rrr_notice" else 10
        elif len(period) == 7 and period[4] == "-" and period[5:].isdigit():
            year, month = (int(item) for item in period.split("-"))
            next_month = date(year + (month == 12), month % 12 + 1, 1)
            period_end = next_month - timedelta(days=1)
            if period_end > target and (year, month) == (target.year, target.month):
                period_end = target
            freshness = 370 if family == "pbc_rrr_notice" else 95
        else:
            normalized = period.replace("-Q", "Q")
            if len(normalized) != 6 or normalized[4] != "Q":
                return False
            year = int(normalized[:4])
            quarter = int(normalized[5])
            if quarter not in {1, 2, 3, 4}:
                return False
            month = quarter * 3
            next_month = date(year + (month == 12), month % 12 + 1, 1)
            period_end = next_month - timedelta(days=1)
            freshness = 190
    except (TypeError, ValueError):
        return False
    return period_end <= target and (target - period_end).days <= freshness


def _source_smoke_shape_valid(
    kind: str,
    document: dict[str, Any],
    *,
    target_business_date: str,
) -> bool:
    if kind == "core":
        return _core_smoke_shape_valid(document, target_business_date)
    if kind == "eia":
        return _eia_smoke_shape_valid(document, target_business_date)
    if kind == "lpr":
        return _lpr_smoke_shape_valid(document, target_business_date)
    if kind == "tushare-context":
        return _tushare_smoke_shape_valid(document, target_business_date)
    if kind.startswith("official-context:"):
        return _official_smoke_shape_valid(kind, document, target_business_date)
    return False


def _core_smoke_shape_valid(document: dict[str, Any], target: str) -> bool:
    from pring_cycle.source_adapters import CORE_API_IDENTITIES

    results = document.get("results")
    if not isinstance(results, list) or len(results) != len(CORE_API_IDENTITIES):
        return False
    observed: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            return False
        metric_id = result.get("metric_id")
        if not isinstance(metric_id, str) or metric_id not in CORE_API_IDENTITIES:
            return False
        api_name, source_code = CORE_API_IDENTITIES[metric_id]
        if not (
            result.get("api_name") == api_name
            and result.get("source_code") == source_code
            and result.get("status") == "validated"
            and result.get("last_business_date") == target
            and isinstance(result.get("first_business_date"), str)
            and str(result["first_business_date"]) <= target
            and type(result.get("observations")) is int
            and int(result["observations"]) >= 140
            and _is_sha256(result.get("normalized_hash"))
        ):
            return False
        observed.add(metric_id)
    return observed == set(CORE_API_IDENTITIES)


def _eia_smoke_shape_valid(document: dict[str, Any], target: str) -> bool:
    return bool(
        document.get("endpoint")
        == "https://api.eia.gov/v2/petroleum/pri/spt/data/"
        and set(_string_list(document.get("series_ids"))) == {"RBRTE", "RWTC"}
        and type(document.get("observation_count")) is int
        and int(document["observation_count"]) >= 2
        and isinstance(document.get("first_business_date"), str)
        and isinstance(document.get("last_business_date"), str)
        and str(document["first_business_date"])
        <= target
        <= str(document["last_business_date"])
        and _is_sha256(document.get("normalized_hash"))
    )


def _lpr_smoke_shape_valid(document: dict[str, Any], target: str) -> bool:
    parsed = urlsplit(str(document.get("final_url", "")))
    scope = document.get("target_scope")
    return bool(
        document.get("source_identity") == "CHINAMONEY_LPR"
        and parsed.scheme == "https"
        and parsed.hostname == "www.chinamoney.com.cn"
        and document.get("period") == target[:7]
        and isinstance(scope, dict)
        and scope.get("period") == document.get("period")
        and set(_string_list(document.get("tenors"))) == {"1y", "5y_plus"}
        and document.get("observation_count") == 2
        and document.get("http_status") == 200
        and type(document.get("byte_count")) is int
        and int(document["byte_count"]) > 0
        and _is_timezone_aware(document.get("release_at"))
        and _is_sha256(document.get("content_hash"))
    )


def _official_smoke_shape_valid(
    kind: str,
    document: dict[str, Any],
    target: str,
) -> bool:
    family = kind.removeprefix("official-context:")
    descriptor = OFFICIAL_CONTEXT_FAMILIES.get(family)
    parsed = urlsplit(str(document.get("final_url", "")))
    period = str(document.get("period", ""))
    scope = document.get("target_scope")
    first_period = str(document.get("first_period", ""))
    last_period = str(document.get("last_period", ""))
    return bool(
        descriptor is not None
        and document.get("family") == family
        and document.get("provider") == descriptor.provider
        and isinstance(scope, dict)
        and scope.get("period") == period
        and parsed.scheme == "https"
        and parsed.hostname == descriptor.host
        and set(_string_list(document.get("metric_ids"))) == set(descriptor.metric_ids)
        and type(document.get("observation_count")) is int
        and int(document["observation_count"]) >= len(descriptor.metric_ids)
        and bool(first_period)
        and bool(last_period)
        and first_period <= last_period
        and document.get("http_status") == 200
        and type(document.get("byte_count")) is int
        and int(document["byte_count"]) > 0
        and _is_timezone_aware(document.get("release_at"))
        and _is_sha256(document.get("content_hash"))
        and _period_is_fresh_for_target(period, target, family=family)
        and (
            family != "pbc_rrr_notice"
            or _period_is_fresh_for_target(last_period, target, family=family)
        )
    )


def _tushare_smoke_shape_valid(document: dict[str, Any], target: str) -> bool:
    expected_metrics = {
        "pmi": {"CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_PMI_PRICES"},
        "prices": {"CN_CPI_HEADLINE", "CN_PPI"},
        "money": {"CN_M1_M2"},
        "social_financing": {"CN_SF_TOTAL"},
        "futures_warrants": {"CN_FUTURES_WARRANTS"},
        "gdp": {"CN_GDP"},
        "treasury_yields": {"UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"},
        "transmission": {"CN_DR007", "CN_SHIBOR_ON_1W_3M"},
    }
    families = document.get("families")
    if (
        document.get("target_business_date") != target
        or not isinstance(families, list)
        or len(families) != len(expected_metrics)
    ):
        return False
    observed: set[str] = set()
    request_count = 0
    for family in families:
        if not isinstance(family, dict):
            return False
        name = family.get("family")
        if not isinstance(name, str) or name not in expected_metrics:
            return False
        if not (
            family.get("status") == "validated_candidate"
            and set(_string_list(family.get("metric_ids"))) == expected_metrics[name]
            and bool(_string_list(family.get("api_names")))
            and isinstance(family.get("first_period"), str)
            and isinstance(family.get("last_period"), str)
            and str(family["first_period"]) <= str(family["last_period"])
            and type(family.get("observation_count")) is int
            and int(family["observation_count"]) > 0
            and type(family.get("network_requests")) is int
            and int(family["network_requests"]) > 0
            and _is_sha256(family.get("normalized_hash"))
        ):
            return False
        observed.add(name)
        request_count += int(family["network_requests"])
    return observed == set(expected_metrics) and document.get("network_requests") == request_count


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return ()
    return tuple(value)


def _is_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_timezone_aware(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _dashboard_projection_visible(port: int, *, projection_set_id: str) -> bool:
    if not 1 <= port <= 65535:
        raise ValueError("dashboard_port_invalid")
    base_url = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))
    try:
        root_request = Request(base_url + "/", headers={"Accept": "text/html"})
        with opener.open(root_request, timeout=5) as response:
            if response.geturl() != base_url + "/" or int(response.status) != 200:
                return False
            html = response.read(4_000_001)
        with opener.open(
            Request(
                base_url + "/api/v1/projections/current",
                headers={"Accept": "application/json"},
            ),
            timeout=5,
        ) as response:
            if (
                response.geturl() != base_url + "/api/v1/projections/current"
                or int(response.status) != 200
            ):
                return False
            api_content = response.read(4_000_001)
        with opener.open(
            Request(
                base_url + "/_dash-layout",
                headers={"Accept": "application/json"},
            ),
            timeout=5,
        ) as response:
            if response.geturl() != base_url + "/_dash-layout" or int(response.status) != 200:
                return False
            layout_content = response.read(4_000_001)
    except (OSError, ValueError):
        return False
    if (
        len(html) > 4_000_000
        or len(api_content) > 4_000_000
        or len(layout_content) > 4_000_000
    ):
        return False
    try:
        api_document = json.loads(api_content)
        layout_document = json.loads(layout_content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    envelope = api_document.get("envelope") if isinstance(api_document, dict) else None
    return bool(
        isinstance(envelope, dict)
        and envelope.get("projection_set_id") == projection_set_id
        and _dash_layout_valid(layout_document, projection_set_id)
        and b"data-pring-meaningful-content='true'" in html
        and "交互驾驶舱加载失败".encode() not in html
        and projection_set_id.encode() in html
    )


def _dash_layout_valid(value: object, projection_set_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    props = value.get("props")
    if not (
        isinstance(props, dict)
        and props.get("className") == "dashboard-app"
        and isinstance(value.get("type"), str)
        and isinstance(value.get("namespace"), str)
    ):
        return False
    identifiers: set[str] = set()
    text_values: set[str] = set()

    def collect(item: object) -> None:
        if isinstance(item, dict):
            item_props = item.get("props")
            if isinstance(item_props, dict) and isinstance(item_props.get("id"), str):
                identifiers.add(str(item_props["id"]))
            for child in item.values():
                collect(child)
        elif isinstance(item, list):
            for child in item:
                collect(child)
        elif isinstance(item, str):
            text_values.add(item)

    collect(value)
    required_ids = {
        "dashboard-location",
        "runtime-poll",
        "theme-state",
        "theme-toggle",
        "page-content",
        "command-feedback",
        *(
            f"nav-{path.strip('/').replace('/', '-') or 'home'}"
            for path, _label in DASHBOARD_NAVIGATION
        ),
    }
    return required_ids <= identifiers and projection_set_id in text_values


def _projection_evidence_ids(value: object) -> set[str]:
    identifiers: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "claim_id",
                "derived_observation_id",
                "observation_id",
                "selected_claim_id",
            } and isinstance(item, str):
                identifiers.add(item)
            elif key in {
                "claim_ids",
                "evidence_ids",
                "input_observation_version_ids",
                "observation_version_ids",
            } and isinstance(item, (list, tuple)):
                identifiers.update(
                    identifier for identifier in item if isinstance(identifier, str)
                )
            else:
                identifiers.update(_projection_evidence_ids(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            identifiers.update(_projection_evidence_ids(item))
    return identifiers


def _store_rehearsal(
    paths: RuntimePaths,
    kind: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    normalized_hash = hashlib.sha256(_canonical_json(document).encode()).hexdigest()
    artifact_document = {**document, "normalized_result_hash": normalized_hash}
    artifact = store_artifact(
        paths.database,
        paths.artifacts,
        (_canonical_json(artifact_document) + "\n").encode(),
        media_type="application/json",
        source_reference=f"rehearsal:{kind}:{normalized_hash}",
    )
    return {
        **artifact_document,
        "artifact": {"hash": artifact.content_hash, "path": str(artifact.path)},
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_safe_document(value: dict[str, Any]) -> dict[str, Any]:
    def convert(item: object) -> object:
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        if isinstance(item, dict):
            return {str(key): convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item

    return {str(key): convert(item) for key, item in value.items()}
