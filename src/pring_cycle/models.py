from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from datetime import time as clock_time
from pathlib import Path
from typing import Any

from pring_cycle.catalog import (
    METRIC_CATALOG_V0001,
    METRIC_CATALOG_V0003,
    METRIC_CATALOG_VERSION,
    metric_catalog,
    metric_catalog_v0001,
    metric_catalog_v0003,
)
from pring_cycle.model_outputs import (
    MODEL_OUTPUT_SCHEMA,
    model_output_hash,
    read_model_output,
    store_model_output,
    validate_history_output,
    validate_replay_output,
)
from pring_cycle.source_contract_review import require_model_source_contract

CALIBRATION_BASELINE: dict[str, int] = {
    "asset_direction_changes": 21,
    "formal_stage_changes": 11,
    "fast_reversals_20d": 0,
    "median_confirmation_delay_days": 23,
}


@dataclass(frozen=True)
class ModelVersion:
    model_version_id: str
    manifest_hash: str
    status: str
    certified_replay_start: str


@dataclass(frozen=True)
class CalibrationAcceptance:
    model_version_id: str
    passed: bool
    asset_direction_changes: int
    formal_stage_changes: int
    fast_reversals_20d: int
    median_confirmation_delay_days: int
    result_hash: str
    range_start: str = "unspecified"
    range_end: str = "unspecified"
    evidence_hash: str = "unspecified"
    evaluated_days: int = 0
    input_range_start: str = "unspecified"
    input_days: int = 0
    core_output_hash: str | None = None


@dataclass(frozen=True)
class ReplayResult:
    replay_id: int
    model_version_id: str
    compared_with: str
    range_start: str
    range_end: str
    passed: bool
    stage_differences: int
    core_state_differences: int
    context_output_differences: int
    gaps: tuple[str, ...]
    evaluated_trading_days: int = 0
    calendar_hash: str = ""
    candidate_state_differences: int | None = None
    candidate_days_differences: int | None = None
    core_output_hash: str | None = None


def certified_model_v0001_manifest() -> dict[str, Any]:
    return {
        "model_version_id": "model-v0001",
        "certified_replay_start": "2018-06-01",
        "trend_rules": {
            "rule_version": "trend-v0001",
            "window_days": 120,
            "slope_days": 20,
            "volatility_days": 20,
            "noise_multiplier": 1.5,
            "persistence_days": 8,
            "candidate_window_days": 30,
        },
        "stage_mapping": {
            "bull,bear,bear": "stage_i",
            "bull,bull,bear": "stage_ii",
            "bull,bull,bull": "stage_iii",
            "bear,bull,bull": "stage_iv",
            "bear,bear,bull": "stage_v",
            "bear,bear,bear": "stage_vi",
        },
        "core_metrics": {
            "bond": "CN_BOND_CORE_000012",
            "stock": "CN_EQUITY_CORE_000985",
            "commodity": "CN_COMMODITY_CORE_NHII",
        },
        "source_certifications": {
            "000012.SH": "certified",
            "000985.CSI": "certified",
            "NHII.NH": "certified_from_2018-06-01",
        },
        "selection_rule_version": "selection-v0001",
        "derived_formula_versions": {
            "credit_impulse": "credit-impulse-v0001",
            "order_inventory_spread": "order-inventory-v0001",
            "real_inventory_approximation": "inventory-ppi-v0001",
        },
        "metric_catalog_version": METRIC_CATALOG_V0001,
        "metric_definitions": [asdict(item) for item in metric_catalog_v0001()],
    }


def analytical_model_v0002_manifest() -> dict[str, Any]:
    manifest = certified_model_v0001_manifest()
    definitions = [asdict(item) for item in metric_catalog()]
    for definition in definitions:
        if definition["metric_id"] == "CN_FUTURES_WARRANTS":
            definition["allowed_units"] = tuple(
                unit for unit in definition["allowed_units"] if unit != "barrel"
            )
    manifest.update(
        {
            "model_version_id": "model-v0002",
            "metric_catalog_version": METRIC_CATALOG_VERSION,
            "metric_definitions": definitions,
            "derived_formula_versions": {
                "credit_impulse": "credit-impulse-rolling-share-v0001",
                "dr007_policy_spread": "dr007-policy-spread-v0001",
                "loan_monthly_change": "loan-stock-monthly-change-v0001",
                "omo_net_injection": "repo-net-injection-v0001",
                "order_inventory_spread": "pmi-order-inventory-spread-v0001",
                "production_order_spread": "pmi-production-order-spread-v0001",
                "real_inventory_approximation": "inventory-ppi-v0001",
                "ust_2s10s_spread": "ust-2s10s-spread-v0001",
            },
        }
    )
    return manifest


def analytical_model_v0003_manifest() -> dict[str, Any]:
    manifest = analytical_model_v0002_manifest()
    manifest.update(
        {
            "model_version_id": "model-v0003",
            "history_input_start": "2017-01-01",
            "metric_definitions": [asdict(item) for item in metric_catalog()],
        }
    )
    return manifest


def certified_120d_model_v0006_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    if not source_certification_packages:
        raise ValueError("source_certification_packages_required")
    packages = sorted(
        (dict(package) for package in source_certification_packages),
        key=lambda package: str(package.get("package_id", "")),
    )
    if any(not package.get("package_id") for package in packages):
        raise ValueError("source_certification_package_id_required")
    manifest = analytical_model_v0003_manifest()
    manifest.update(
        {
            "model_version_id": "model-v0006",
            "certified_replay_start": "2026-03-09",
            "calibration_range_start": "2018-06-01",
            "history_input_start": "2017-01-01",
            "metric_catalog_version": METRIC_CATALOG_V0003,
            "metric_definitions": [asdict(item) for item in metric_catalog_v0003()],
            "source_certification_packages": packages,
            "visible_evidence_window_trading_days": 120,
            "hidden_preheat_policy": "minimum_formula_inputs_only",
        }
    )
    return manifest


def certified_120d_model_v0007_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0006_manifest(source_certification_packages)
    formulas = dict(manifest["derived_formula_versions"])
    formulas.update(
        {
            "credit_impulse": "credit-impulse-ytd-flow-v0002",
            "loan_monthly_change": "loan-ytd-monthly-change-v0002",
        }
    )
    manifest.update(
        {
            "model_version_id": "model-v0007",
            "derived_formula_versions": formulas,
        }
    )
    return manifest


def certified_120d_model_v0008_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0007_manifest(source_certification_packages)
    manifest["model_version_id"] = "model-v0008"
    return manifest


def certified_120d_model_v0009_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    manifest = certified_120d_model_v0008_manifest(source_certification_packages)
    manifest["model_version_id"] = "model-v0009"
    return manifest


def certified_120d_model_v0010_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    """Build a content-addressed immutable candidate with hardened trust boundaries."""
    manifest = certified_120d_model_v0009_manifest(source_certification_packages)
    manifest.update(
        {
            "model_version_id": "model-v0010-pending",
            "point_in_time_rule_version": "public-cutoff-v0002",
            "visible_context_window_rule_version": "exact-core-calendar-120-v0001",
            "replay_acceptance_rule_version": "active-baseline-exact-120-v0001",
        }
    )
    identity_document = dict(manifest)
    identity_document.pop("model_version_id", None)
    digest = hashlib.sha256(_canonical_json(identity_document).encode()).hexdigest()
    manifest["model_version_id"] = f"model-v0010-{digest[:16]}"
    return manifest


def certified_120d_model_v0011_manifest(
    source_certification_packages: tuple[Mapping[str, object], ...],
) -> dict[str, Any]:
    """Bind trading-calendar OMO maturity semantics to a new immutable model."""
    manifest = certified_120d_model_v0010_manifest(source_certification_packages)
    formulas = dict(manifest["derived_formula_versions"])
    formulas["omo_net_injection"] = "repo-net-injection-trading-calendar-v0002"
    manifest.update(
        {
            "model_version_id": "model-v0011-pending",
            "derived_formula_versions": formulas,
        }
    )
    identity_document = dict(manifest)
    identity_document.pop("model_version_id", None)
    digest = hashlib.sha256(_canonical_json(identity_document).encode()).hexdigest()
    manifest["model_version_id"] = f"model-v0011-{digest[:16]}"
    return manifest


class ModelRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @classmethod
    def create(cls, database_path: Path) -> ModelRepository:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        repository = cls(database_path)
        with repository._connect() as connection:
            connection.executescript(_MODEL_SCHEMA)
            connection.executescript(MODEL_OUTPUT_SCHEMA)
            _ensure_model_replay_context_column(connection)
        return repository

    def create_candidate(self, manifest: dict[str, Any]) -> ModelVersion:
        with self._connect() as connection:
            return self._store_candidate(connection, manifest)

    def _create_admitted_candidate(self, manifest: dict[str, Any]) -> ModelVersion:
        # Only the source-admission service calls this after reading and validating
        # its formal review. Generic historical/fixture candidates never register.
        from pring_cycle.catalog_registry import _register_admitted_catalog

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            candidate = self._store_candidate(connection, manifest)
            _register_admitted_catalog(connection, manifest)
        return candidate

    def _store_candidate(
        self,
        connection: sqlite3.Connection,
        manifest: dict[str, Any],
    ) -> ModelVersion:
        model_version_id = str(manifest.get("model_version_id", ""))
        certified_replay_start = str(manifest.get("certified_replay_start", ""))
        if not model_version_id or not certified_replay_start:
            raise ValueError("invalid_model_manifest")
        manifest_json = _canonical_json(manifest)
        manifest_hash = hashlib.sha256(manifest_json.encode()).hexdigest()
        existing = connection.execute(
            "SELECT * FROM model_version WHERE model_version_id = ?",
            (model_version_id,),
        ).fetchone()
        if existing is not None:
            if str(existing["manifest_hash"]) != manifest_hash:
                raise ValueError("model_version_is_immutable")
            return _model_version(existing)
        connection.execute(
            """
                INSERT INTO model_version(
                    model_version_id, manifest_hash, manifest_json, status,
                    certified_replay_start, created_at
                ) VALUES (?, ?, ?, 'candidate', ?, ?)
                """,
            (
                model_version_id,
                manifest_hash,
                manifest_json,
                certified_replay_start,
                datetime.now(UTC).isoformat(),
            ),
        )
        return ModelVersion(model_version_id, manifest_hash, "candidate", certified_replay_start)

    def record_acceptance(
        self, model_version_id: str, results: Mapping[str, object]
    ) -> CalibrationAcceptance:
        model = self.get(model_version_id)
        manifest = self.manifest(model_version_id)
        normalized = {key: _acceptance_integer(results[key]) for key in CALIBRATION_BASELINE}
        evidence_hash = str(results.get("evidence_hash", "unspecified"))
        evaluated_days = _acceptance_integer(results.get("evaluated_days", 0))
        input_days = _acceptance_integer(results.get("input_days", 0))
        input_range_start = str(results.get("input_range_start", "unspecified"))
        range_end = str(results.get("range_end", "unspecified"))
        range_start = str(results.get("range_start", "unspecified"))
        metadata: dict[str, object] = {
            "evidence_hash": evidence_hash,
            "evaluated_days": evaluated_days,
            "input_days": input_days,
            "input_range_start": input_range_start,
            "range_end": range_end,
            "range_start": range_start,
        }
        output_document = results.get("core_output_document")
        output_hash = None
        if output_document is not None:
            output_document = validate_history_output(
                output_document,
                manifest=manifest,
                manifest_hash=model.manifest_hash,
                range_start=range_start,
                range_end=range_end,
                evidence_hash=evidence_hash,
                evaluated_days=evaluated_days,
            )
            output_hash = model_output_hash(output_document)
            if results.get("core_output_hash") != output_hash:
                raise ValueError("model_output_hash_mismatch")
            metadata["core_output_hash"] = output_hash
        elif results.get("core_output_hash") is not None:
            raise ValueError("model_output_document_required")
        machine_result = any(key in results for key in metadata)
        metadata_complete = (
            len(evidence_hash) == 64
            and evaluated_days > 0
            and input_days >= evaluated_days
            and input_range_start != "unspecified"
            and range_start != "unspecified"
            and range_end != "unspecified"
        )
        hardened = manifest.get("replay_acceptance_rule_version") == (
            "active-baseline-exact-120-v0001"
        )
        passed = normalized == CALIBRATION_BASELINE and (
            metadata_complete or (not machine_result and not hardened)
        )
        if (
            hardened
            and manifest["trend_rules"].get("candidate_duration_rule_version")
            == ("candidate-duration-v0002")
            and output_hash is None
        ):
            passed = False
        result_document = {**normalized, **metadata}
        result_json = _canonical_json(result_document)
        result_hash = hashlib.sha256(result_json.encode()).hexdigest()
        with self._connect() as connection:
            if output_document is not None:
                assert isinstance(output_document, dict)
                store_model_output(connection, output_document)
            connection.execute(
                """
                INSERT OR IGNORE INTO model_acceptance(
                    model_version_id, result_hash, results_json, passed, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    result_hash,
                    result_json,
                    int(passed),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return CalibrationAcceptance(
            model_version_id=model_version_id,
            passed=passed,
            asset_direction_changes=normalized["asset_direction_changes"],
            formal_stage_changes=normalized["formal_stage_changes"],
            fast_reversals_20d=normalized["fast_reversals_20d"],
            median_confirmation_delay_days=normalized["median_confirmation_delay_days"],
            result_hash=result_hash,
            range_start=range_start,
            range_end=range_end,
            evidence_hash=evidence_hash,
            evaluated_days=evaluated_days,
            input_range_start=input_range_start,
            input_days=input_days,
            core_output_hash=output_hash,
        )

    def acceptance_details(self, model_version_id: str, result_hash: str) -> dict[str, Any]:
        model = self.get(model_version_id)
        manifest = self.manifest(model_version_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_acceptance WHERE model_version_id=? AND result_hash=?",
                (model_version_id, result_hash),
            ).fetchone()
            if row is None:
                raise LookupError("model_acceptance_not_found")
            content = str(row["results_json"])
            if hashlib.sha256(content.encode()).hexdigest() != result_hash:
                raise ValueError("model_acceptance_hash_mismatch")
            results = json.loads(content)
            output_hash = results.get("core_output_hash")
            output = None if output_hash is None else read_model_output(connection, output_hash)
        if output is not None:
            validate_history_output(
                output,
                manifest=manifest,
                manifest_hash=model.manifest_hash,
                range_start=results["range_start"],
                range_end=results["range_end"],
                evidence_hash=results["evidence_hash"],
                evaluated_days=results["evaluated_days"],
            )
        return {
            "model_version_id": model_version_id,
            "result_hash": result_hash,
            "passed": bool(row["passed"]),
            "results": results,
            "core_output_status": "not_recorded" if output is None else "recorded",
            "core_output_document": output,
        }

    def activate(self, model_version_id: str, *, explicitly_approved: bool) -> ModelVersion:
        model = self.get(model_version_id)
        manifest = self.manifest(model_version_id)
        required_days = int(manifest.get("visible_evidence_window_trading_days", 0))
        hardened = manifest.get("replay_acceptance_rule_version") == (
            "active-baseline-exact-120-v0001"
        )
        with self._connect() as connection:
            passed = connection.execute(
                """
                SELECT 1 FROM model_acceptance
                WHERE model_version_id = ? AND passed = 1 LIMIT 1
                """,
                (model_version_id,),
            ).fetchone()
            if passed is None:
                raise ValueError("model_acceptance_required")
            if hardened and not _hardened_machine_acceptance_matches(
                self._database_path,
                model_version_id,
            ):
                raise ValueError("model_machine_acceptance_required")
            if model_version_id != "model-v0001":
                current = connection.execute(
                    "SELECT model_version_id FROM active_model WHERE singleton = 1"
                ).fetchone()
                if current is None:
                    raise ValueError("active_model_unavailable")
                failed_replay = connection.execute(
                    """
                    SELECT 1 FROM model_replay
                    WHERE model_version_id=? AND passed=0 LIMIT 1
                    """,
                    (model_version_id,),
                ).fetchone()
                if failed_replay is not None:
                    raise ValueError("model_failed_replay_not_activatable")
                if hardened:
                    replay_rows = connection.execute(
                        """
                        SELECT replay_id, range_start, range_end, stage_differences,
                               core_state_differences, context_output_differences,
                               evaluated_trading_days, calendar_hash
                        FROM model_replay
                        WHERE model_version_id=?
                          AND compared_with=?
                          AND model_version_id<>compared_with
                          AND passed=1
                        ORDER BY replay_id DESC
                        """,
                        (model_version_id, str(current[0])),
                    ).fetchall()
                    comparison_manifest = self.manifest(str(current[0]))
                    replay_passed = next(
                        (
                            True
                            for row in replay_rows
                            if _hardened_replay_calendar_matches(
                                self._database_path,
                                candidate_manifest=manifest,
                                comparison_manifest=comparison_manifest,
                                range_start=str(row["range_start"]),
                                range_end=str(row["range_end"]),
                                evaluated_trading_days=int(row["evaluated_trading_days"]),
                                calendar_hash=str(row["calendar_hash"]),
                                required_days=required_days,
                                certified_replay_start=model.certified_replay_start,
                            )
                            and _hardened_machine_replay_matches(
                                self._database_path,
                                replay_id=int(row["replay_id"]),
                            )
                        ),
                        None,
                    )
                else:
                    replay_passed = connection.execute(
                        """
                        SELECT 1 FROM model_replay
                        WHERE model_version_id=? AND passed=1 LIMIT 1
                        """,
                        (model_version_id,),
                    ).fetchone()
                if replay_passed is None:
                    raise ValueError("model_replay_acceptance_required")
            if not explicitly_approved:
                raise ValueError("explicit_model_approval_required")
            connection.execute("BEGIN IMMEDIATE")
            if model_version_id != "model-v0001":
                locked_current = connection.execute(
                    "SELECT model_version_id FROM active_model WHERE singleton = 1"
                ).fetchone()
                if locked_current is None or str(locked_current[0]) != str(current[0]):
                    raise ValueError("active_model_changed_during_activation")
                locked_failed_replay = connection.execute(
                    """
                    SELECT 1 FROM model_replay
                    WHERE model_version_id=? AND passed=0 LIMIT 1
                    """,
                    (model_version_id,),
                ).fetchone()
                if locked_failed_replay is not None:
                    raise ValueError("model_failed_replay_not_activatable")
            require_model_source_contract(manifest)
            previous = connection.execute(
                "SELECT model_version_id FROM active_model WHERE singleton = 1"
            ).fetchone()
            if previous is not None and str(previous[0]) != model_version_id:
                connection.execute(
                    "UPDATE model_version SET status = 'superseded' WHERE model_version_id = ?",
                    (str(previous[0]),),
                )
            connection.execute(
                "UPDATE model_version SET status = 'active' WHERE model_version_id = ?",
                (model_version_id,),
            )
            connection.execute(
                """
                INSERT INTO active_model(singleton, model_version_id) VALUES (1, ?)
                ON CONFLICT(singleton) DO UPDATE SET model_version_id=excluded.model_version_id
                """,
                (model_version_id,),
            )
            connection.execute(
                """
                INSERT INTO model_activation(
                    model_version_id, previous_model_version_id, activated_at
                ) VALUES (?, ?, ?)
                """,
                (
                    model_version_id,
                    str(previous[0]) if previous is not None else None,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return ModelVersion(
            model.model_version_id,
            model.manifest_hash,
            "active",
            model.certified_replay_start,
        )

    def record_replay(
        self,
        model_version_id: str,
        *,
        compared_with: str,
        requested_start: str,
        requested_end: str,
        quality_passed: bool,
        regression_passed: bool,
        performance_passed: bool,
        stage_differences: int,
        core_state_differences: int,
        gaps: tuple[str, ...],
        context_output_differences: int = 0,
        evaluated_trading_days: int = 0,
        calendar_hash: str = "",
        candidate_state_differences: int | None = None,
        candidate_days_differences: int | None = None,
        core_output_hash: str | None = None,
        core_output_document: dict[str, Any] | None = None,
    ) -> ReplayResult:
        candidate = self.get(model_version_id)
        comparison = self.get(compared_with)
        range_start = max(
            requested_start,
            candidate.certified_replay_start,
            comparison.certified_replay_start,
        )
        if range_start > requested_end:
            raise ValueError("certified_replay_range_empty")
        normalized_gaps = list(gaps)
        candidate_manifest = self.manifest(model_version_id)
        if core_output_document is not None:
            validate_replay_output(
                core_output_document,
                candidate_manifest=candidate_manifest,
                comparison_manifest=self.manifest(compared_with),
                candidate_manifest_hash=candidate.manifest_hash,
                comparison_manifest_hash=comparison.manifest_hash,
                range_start=range_start,
                range_end=requested_end,
                evaluated_days=evaluated_trading_days,
                calendar_hash=calendar_hash,
                stage_differences=stage_differences,
                core_state_differences=core_state_differences,
                candidate_state_differences=candidate_state_differences,
                candidate_days_differences=candidate_days_differences,
            )
            if model_output_hash(core_output_document) != core_output_hash:
                raise ValueError("model_output_hash_mismatch")
        elif any(
            value is not None
            for value in (
                core_output_hash,
                candidate_state_differences,
                candidate_days_differences,
            )
        ):
            raise ValueError("model_output_document_required")
        if candidate_manifest.get("replay_acceptance_rule_version") == (
            "active-baseline-exact-120-v0001"
        ):
            if (
                core_output_document is None
                and candidate_manifest["trend_rules"].get("candidate_duration_rule_version")
                == "candidate-duration-v0002"
            ):
                normalized_gaps.append("core_candidate_outputs_incomplete")
            try:
                active_model = self.active()
            except LookupError:
                normalized_gaps.append("active_replay_baseline_unavailable")
            else:
                if compared_with != active_model.model_version_id:
                    normalized_gaps.append("replay_comparison_not_current_active")
                comparison_manifest = self.manifest(compared_with)
                required_days = int(
                    candidate_manifest.get("visible_evidence_window_trading_days", 0)
                )
                if not _hardened_replay_calendar_matches(
                    self._database_path,
                    candidate_manifest=candidate_manifest,
                    comparison_manifest=comparison_manifest,
                    range_start=range_start,
                    range_end=requested_end,
                    evaluated_trading_days=evaluated_trading_days,
                    calendar_hash=calendar_hash,
                    required_days=required_days,
                    certified_replay_start=candidate.certified_replay_start,
                ):
                    normalized_gaps.append("certified_replay_calendar_invalid")
        normalized_gaps = list(dict.fromkeys(normalized_gaps))
        passed = quality_passed and regression_passed and performance_passed and not normalized_gaps
        with self._connect() as connection:
            if core_output_document is not None:
                store_model_output(connection, core_output_document)
            cursor = connection.execute(
                """
                INSERT INTO model_replay(
                    model_version_id, compared_with, range_start, range_end,
                    quality_passed, regression_passed, performance_passed,
                    stage_differences, core_state_differences,
                    context_output_differences, gaps_json, passed, created_at,
                    evaluated_trading_days, calendar_hash,
                    candidate_state_differences, candidate_days_differences, core_output_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    compared_with,
                    range_start,
                    requested_end,
                    int(quality_passed),
                    int(regression_passed),
                    int(performance_passed),
                    stage_differences,
                    core_state_differences,
                    context_output_differences,
                    _canonical_json(tuple(normalized_gaps)),
                    int(passed),
                    datetime.now(UTC).isoformat(),
                    evaluated_trading_days,
                    calendar_hash,
                    candidate_state_differences,
                    candidate_days_differences,
                    core_output_hash,
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("model_replay_identity_missing")
            replay_id = int(cursor.lastrowid)
        return ReplayResult(
            replay_id=replay_id,
            model_version_id=model_version_id,
            compared_with=compared_with,
            range_start=range_start,
            range_end=requested_end,
            passed=passed,
            stage_differences=stage_differences,
            core_state_differences=core_state_differences,
            context_output_differences=context_output_differences,
            gaps=tuple(normalized_gaps),
            evaluated_trading_days=evaluated_trading_days,
            calendar_hash=calendar_hash,
            candidate_state_differences=candidate_state_differences,
            candidate_days_differences=candidate_days_differences,
            core_output_hash=core_output_hash,
        )

    def replay_details(self, replay_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_replay WHERE replay_id=?", (replay_id,)
            ).fetchone()
            if row is None:
                raise LookupError("model_replay_not_found")
            replay = {
                name: row[name] for name in ReplayResult.__dataclass_fields__ if name != "gaps"
            }
            replay["passed"] = bool(row["passed"])
            replay["gaps"] = json.loads(row["gaps_json"])
            digest = replay["core_output_hash"]
            document = read_model_output(connection, digest) if digest is not None else None
        if document is not None:
            validate_replay_output(
                document,
                candidate_manifest=self.manifest(replay["model_version_id"]),
                comparison_manifest=self.manifest(replay["compared_with"]),
                candidate_manifest_hash=self.get(replay["model_version_id"]).manifest_hash,
                comparison_manifest_hash=self.get(replay["compared_with"]).manifest_hash,
                range_start=replay["range_start"],
                range_end=replay["range_end"],
                evaluated_days=replay["evaluated_trading_days"],
                calendar_hash=replay["calendar_hash"],
                stage_differences=replay["stage_differences"],
                core_state_differences=replay["core_state_differences"],
                candidate_state_differences=replay["candidate_state_differences"],
                candidate_days_differences=replay["candidate_days_differences"],
            )
        return {
            "replay": replay,
            "core_output_status": "recorded" if document is not None else "not_recorded",
            "core_output_document": document,
        }

    def replay_matches_current_evidence(self, replay_id: int) -> bool:
        """Revalidate a saved result without rewriting its historical output."""
        from pring_cycle.model_evaluation import replay_models

        try:
            details = self.replay_details(replay_id)
            saved = details["replay"]
            if not saved["passed"] or details["core_output_status"] != "recorded":
                return False
            evaluation = replay_models(
                self._database_path,
                saved["model_version_id"],
                saved["compared_with"],
                requested_start=saved["range_start"],
                requested_end=saved["range_end"],
            )
            return (
                evaluation.quality_passed
                and evaluation.regression_passed
                and evaluation.performance_passed
                and not evaluation.gaps
                and evaluation.evaluated_range_start == saved["range_start"]
                and evaluation.evaluated_range_end == saved["range_end"]
                and evaluation.core_output_hash is not None
                and all(
                    getattr(evaluation, name) == saved[name]
                    for name in (
                        "stage_differences",
                        "core_state_differences",
                        "context_output_differences",
                        "evaluated_trading_days",
                        "calendar_hash",
                        "candidate_state_differences",
                        "candidate_days_differences",
                        "core_output_hash",
                    )
                )
            )
        except (KeyError, LookupError, TypeError, ValueError):
            return False

    def record_first_publication(self, model_version_id: str, target_business_date: str) -> None:
        if self.active().model_version_id != model_version_id:
            raise ValueError("publication_model_is_not_active")
        with self._connect() as connection:
            activation = connection.execute(
                """
                SELECT first_published_business_date FROM model_activation
                WHERE activation_id=(
                    SELECT MAX(activation_id) FROM model_activation
                    WHERE model_version_id=?
                )
                """,
                (model_version_id,),
            ).fetchone()
            if activation is None:
                raise ValueError("model_activation_missing")
            if activation["first_published_business_date"] is not None:
                return
            updated = connection.execute(
                """
                UPDATE model_activation SET first_published_business_date=?
                WHERE activation_id=(
                    SELECT MAX(activation_id) FROM model_activation
                    WHERE model_version_id=?
                ) AND first_published_business_date IS NULL
                """,
                (target_business_date, model_version_id),
            ).rowcount
        if updated != 1:
            raise ValueError("model_first_publication_not_recorded")

    def rollback(
        self,
        model_version_id: str,
        *,
        as_of_business_date: str,
        trading_calendar: tuple[str, ...],
        explicitly_confirmed: bool,
    ) -> ModelVersion:
        if not explicitly_confirmed:
            raise ValueError("explicit_model_rollback_confirmation_required")
        if self.active().model_version_id != model_version_id:
            raise ValueError("model_is_not_active")
        with self._connect() as connection:
            activation = connection.execute(
                """
                SELECT * FROM model_activation
                WHERE model_version_id=?
                ORDER BY activation_id DESC LIMIT 1
                """,
                (model_version_id,),
            ).fetchone()
            if (
                activation is None
                or activation["previous_model_version_id"] is None
                or activation["first_published_business_date"] is None
            ):
                raise ValueError("model_rollback_unavailable")
            first_date = str(activation["first_published_business_date"])
            try:
                first_index = trading_calendar.index(first_date)
                as_of_index = trading_calendar.index(as_of_business_date)
            except ValueError as error:
                raise ValueError("rollback_date_not_in_trading_calendar") from error
            if as_of_index < first_index or as_of_index - first_index >= 30:
                raise ValueError("model_rollback_window_expired")
            previous_model = str(activation["previous_model_version_id"])
            require_model_source_contract(self.manifest(previous_model))
            connection.execute(
                "UPDATE model_version SET status='candidate' WHERE model_version_id=?",
                (model_version_id,),
            )
            connection.execute(
                "UPDATE model_version SET status='active' WHERE model_version_id=?",
                (previous_model,),
            )
            connection.execute(
                "UPDATE active_model SET model_version_id=? WHERE singleton=1",
                (previous_model,),
            )
            connection.execute(
                """
                INSERT INTO model_rollback(
                    from_model_version_id, to_model_version_id,
                    as_of_business_date, rolled_back_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    model_version_id,
                    previous_model,
                    as_of_business_date,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return self.get(previous_model)

    def activation_history(self) -> tuple[dict[str, str | None], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_activation ORDER BY activation_id"
            ).fetchall()
        return tuple(
            {
                "model_version_id": str(row["model_version_id"]),
                "previous_model_version_id": (
                    str(row["previous_model_version_id"])
                    if row["previous_model_version_id"] is not None
                    else None
                ),
                "activated_at": str(row["activated_at"]),
                "first_published_business_date": (
                    str(row["first_published_business_date"])
                    if row["first_published_business_date"] is not None
                    else None
                ),
            }
            for row in rows
        )

    def get(self, model_version_id: str) -> ModelVersion:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
        if row is None:
            raise LookupError("model_version_not_found")
        return _model_version(row)

    def manifest(self, model_version_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM model_version WHERE model_version_id = ?",
                (model_version_id,),
            ).fetchone()
        if row is None:
            raise LookupError("model_version_not_found")
        document = json.loads(str(row["manifest_json"]))
        if not isinstance(document, dict):
            raise ValueError("model_manifest_invalid")
        return {str(key): value for key, value in document.items()}

    def active(self) -> ModelVersion:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT model_version.* FROM active_model
                JOIN model_version USING(model_version_id)
                WHERE singleton = 1
                """
            ).fetchone()
        if row is None:
            raise LookupError("active_model_unavailable")
        return _model_version(row)

    def list_versions(self) -> tuple[ModelVersion, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_version ORDER BY created_at, model_version_id"
            ).fetchall()
        return tuple(_model_version(row) for row in rows)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def _model_version(row: sqlite3.Row) -> ModelVersion:
    return ModelVersion(
        model_version_id=str(row["model_version_id"]),
        manifest_hash=str(row["manifest_hash"]),
        status=str(row["status"]),
        certified_replay_start=str(row["certified_replay_start"]),
    )


def _hardened_machine_acceptance_matches(
    database_path: Path,
    model_version_id: str,
) -> bool:
    from pring_cycle.model_evaluation import calibrate_model

    try:
        results = calibrate_model(database_path, model_version_id)
        normalized = {key: _acceptance_integer(results[key]) for key in CALIBRATION_BASELINE}
        metadata = {
            "evidence_hash": str(results["evidence_hash"]),
            "evaluated_days": _acceptance_integer(results["evaluated_days"]),
            "input_days": _acceptance_integer(results["input_days"]),
            "input_range_start": str(results["input_range_start"]),
            "range_end": str(results["range_end"]),
            "range_start": str(results["range_start"]),
            "core_output_hash": str(results["core_output_hash"]),
        }
    except (KeyError, LookupError, TypeError, ValueError):
        return False
    expected_hash = hashlib.sha256(_canonical_json({**normalized, **metadata}).encode()).hexdigest()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT 1 FROM model_acceptance
            WHERE model_version_id=? AND result_hash=? AND passed=1 LIMIT 1
            """,
            (model_version_id, expected_hash),
        ).fetchone()
    if row is None:
        return False
    try:
        details = ModelRepository(database_path).acceptance_details(model_version_id, expected_hash)
    except (KeyError, LookupError, TypeError, ValueError):
        return False
    return bool(details["core_output_status"] == "recorded")


def _hardened_machine_replay_matches(
    database_path: Path,
    *,
    replay_id: int,
) -> bool:
    return ModelRepository(database_path).replay_matches_current_evidence(replay_id)


def _hardened_replay_calendar_matches(
    database_path: Path,
    *,
    candidate_manifest: Mapping[str, object],
    comparison_manifest: Mapping[str, object],
    range_start: str,
    range_end: str,
    evaluated_trading_days: int,
    calendar_hash: str,
    required_days: int,
    certified_replay_start: str,
) -> bool:
    if range_start != certified_replay_start or required_days <= 0:
        return False
    days = _canonical_public_core_days(
        database_path,
        manifests=(candidate_manifest, comparison_manifest),
        range_start=range_start,
        range_end=range_end,
    )
    if (
        len(days) != required_days
        or evaluated_trading_days != required_days
        or not days
        or days[0] != range_start
        or days[-1] != range_end
    ):
        return False
    expected_hash = hashlib.sha256("\n".join(days).encode()).hexdigest()
    return calendar_hash == expected_hash


def _canonical_public_core_days(
    database_path: Path,
    *,
    manifests: tuple[Mapping[str, object], ...],
    range_start: str,
    range_end: str,
) -> tuple[str, ...]:
    from pring_cycle.evidence import AsOfMode, EvidenceRepository

    end_date = date.fromisoformat(range_end)
    cutoff = datetime.combine(end_date, clock_time.max, UTC)
    repository = EvidenceRepository(database_path)
    calendars: list[set[str]] = []
    for manifest in manifests:
        definition_version = str(manifest.get("metric_catalog_version", ""))
        core_metrics = manifest.get("core_metrics")
        if not definition_version or not isinstance(core_metrics, Mapping):
            return ()
        for asset in ("bond", "stock", "commodity"):
            metric_id = core_metrics.get(asset)
            if not isinstance(metric_id, str) or not metric_id:
                return ()
            days: set[str] = set()
            for point in repository.metric_series(
                metric_id,
                mode=AsOfMode.PUBLIC,
                as_of=cutoff,
                definition_version=definition_version,
            ):
                if (
                    point.selection_status != "selected"
                    or point.selected_value is None
                    or not (range_start <= point.period_end <= range_end)
                ):
                    continue
                selected = next(
                    (claim for claim in point.claims if claim.claim_id == point.selected_claim_id),
                    None,
                )
                if (
                    selected is not None
                    and selected.certification_status == "certified"
                    and selected.quality_status == "validated"
                ):
                    days.add(point.period_end)
            calendars.append(days)
    if not calendars:
        return ()
    return tuple(sorted(set.intersection(*calendars)))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _acceptance_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("model_acceptance_integer_invalid")
    return value


_MODEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_version (
    model_version_id TEXT PRIMARY KEY,
    manifest_hash TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_replay_start TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_acceptance (
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    result_hash TEXT NOT NULL,
    results_json TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(model_version_id, result_hash)
);
CREATE TABLE IF NOT EXISTS active_model (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id)
);
CREATE TABLE IF NOT EXISTS model_activation (
    activation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    previous_model_version_id TEXT,
    activated_at TEXT NOT NULL,
    first_published_business_date TEXT
);
CREATE TABLE IF NOT EXISTS model_replay (
    replay_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    compared_with TEXT NOT NULL REFERENCES model_version(model_version_id),
    range_start TEXT NOT NULL,
    range_end TEXT NOT NULL,
    quality_passed INTEGER NOT NULL,
    regression_passed INTEGER NOT NULL,
    performance_passed INTEGER NOT NULL,
    stage_differences INTEGER NOT NULL,
    core_state_differences INTEGER NOT NULL,
    gaps_json TEXT NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_rollback (
    rollback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    to_model_version_id TEXT NOT NULL REFERENCES model_version(model_version_id),
    as_of_business_date TEXT NOT NULL,
    rolled_back_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS model_manifest_no_update
BEFORE UPDATE OF manifest_hash, manifest_json, certified_replay_start ON model_version BEGIN
    SELECT RAISE(ABORT, 'model_manifest_is_immutable');
END;
CREATE TRIGGER IF NOT EXISTS model_version_no_delete
BEFORE DELETE ON model_version BEGIN SELECT RAISE(ABORT, 'model_version_is_immutable'); END;
"""


def _ensure_model_replay_context_column(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(model_replay)")}
    if "context_output_differences" not in columns:
        connection.execute(
            "ALTER TABLE model_replay "
            "ADD COLUMN context_output_differences INTEGER NOT NULL DEFAULT 0"
        )
    if "evaluated_trading_days" not in columns:
        connection.execute(
            "ALTER TABLE model_replay ADD COLUMN evaluated_trading_days INTEGER NOT NULL DEFAULT 0"
        )
    if "calendar_hash" not in columns:
        connection.execute(
            "ALTER TABLE model_replay ADD COLUMN calendar_hash TEXT NOT NULL DEFAULT ''"
        )
    for name, kind in (
        ("candidate_state_differences", "INTEGER"),
        ("candidate_days_differences", "INTEGER"),
        ("core_output_hash", "TEXT"),
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE model_replay ADD COLUMN {name} {kind}")
