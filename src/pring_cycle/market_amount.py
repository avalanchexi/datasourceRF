"""Whole-pool turnover from reviewed, disjoint exchange amount inputs."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from pring_cycle.market_breadth import (
    _breadth_artifact,
    _breadth_price,
    _breadth_time,
    _validate_breadth_proof_metadata,
    _validate_breadth_review,
    parse_daily_breadth_acquisitions,
)

if TYPE_CHECKING:
    from pring_cycle.acquisition import AcquisitionReceipt
    from pring_cycle.tushare_context import ContextScalar

AMOUNT_BREADTH_MEASURES: dict[str, tuple[str, ...]] = {
    "CN_EQ_ADV_AMOUNT_SHARE": ("advancing_amount_share",)
}
AMOUNT_BREADTH_SOURCE_CODE = "tushare:daily:breadth-amount-v0002"


def _reviewed_breadth_amount_inputs(raw: bytes, artifacts: Path) -> dict[str, Any]:
    """Validate a review binding the chosen amount fields, units and complete coverage."""
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("schema_version") != (
        "market-breadth-amount-inputs-v0001"
    ):
        raise ValueError("breadth_amount_schema_invalid")
    _validate_breadth_review(document, artifacts, subject_kind="amount-inputs")
    proof_ids = _validate_breadth_proof_metadata(document["evidence"])
    coverage = document["coverage_evidence"]
    if not coverage or len(set(coverage)) != len(coverage) or not set(coverage) <= proof_ids:
        raise ValueError("breadth_amount_coverage_evidence_missing")
    start, end = document["coverage_start"], document["coverage_end"]
    if (
        date.fromisoformat(start).isoformat() != start
        or date.fromisoformat(end).isoformat() != end
        or start > end
    ):
        raise ValueError("breadth_amount_coverage_invalid")
    dates = [day["business_date"] for day in document["days"]]
    if len(dates) != len(set(dates)) or any(
        date.fromisoformat(day).isoformat() != day or not start <= day <= end for day in dates
    ):
        raise ValueError("breadth_amount_dates_invalid")
    rules = document.get("coverage_rules", [])
    if not isinstance(rules, list) or not rules:
        raise ValueError("breadth_amount_scope_missing")
    for rule in rules:
        start, end = rule["effective_from"], rule["effective_until"]
        methods, references = rule["methods"], rule["evidence"]
        if (
            not isinstance(rule["security_id"], str)
            or not rule["security_id"].strip()
            or rule["exchange"] not in {"SH", "SZ", "BJ"}
            or date.fromisoformat(start).isoformat() != start
            or (end is not None and (date.fromisoformat(end).isoformat() != end or start >= end))
            or not isinstance(methods, list)
            or not methods
            or any(not isinstance(method, str) or not method.strip() for method in methods)
            or len(set(methods)) != len(methods)
            or not references
            or len(set(references)) != len(references)
            or not set(references) <= proof_ids
        ):
            raise ValueError("breadth_amount_scope_invalid")
    return document


def load_breadth_amount_inputs(raw: bytes, artifacts: Path) -> dict[str, Any]:
    """Check all originals when accepting a complete reviewed delivery."""
    document = _reviewed_breadth_amount_inputs(raw, artifacts)
    for proof in document["evidence"]:
        _breadth_artifact(artifacts, proof["artifact_hash"])
    return document


def parse_amount_breadth_acquisitions(
    inputs: tuple[tuple[AcquisitionReceipt, bytes], ...],
    artifacts: Path,
    *,
    period: str | None = None,
) -> list[dict[str, Any]]:
    """Rebuild turnover and daily classification from adopted original inputs."""
    from pring_cycle.tushare_context import _response_rows

    packets = [
        (receipt, raw) for receipt, raw in inputs if receipt.api_name == "breadth_amount_inputs"
    ]
    if len(packets) != 1:
        raise ValueError("breadth_amount_inputs_missing")
    receipt, raw = packets[0]
    if (
        receipt.provider != "reviewed_evidence"
        or receipt.fields
        or receipt.parser_version != "market-breadth-amount-inputs-v0001"
        or receipt.parameters != {"amount_inputs_hash": hashlib.sha256(raw).hexdigest()}
    ):
        raise ValueError("breadth_amount_receipt_invalid")
    document = _reviewed_breadth_amount_inputs(raw, artifacts)
    days = parse_daily_breadth_acquisitions(
        tuple((r, original) for r, original in inputs if r.api_name != "breadth_amount_inputs"),
        artifacts,
        period=period,
    )
    amounts = {day["business_date"]: day for day in document["days"]}
    proofs = {proof["artifact_hash"]: proof for proof in document["evidence"]}
    rules_by_identity: dict[str, list[dict[str, Any]]] = {}
    for rule in document["coverage_rules"]:
        rules_by_identity.setdefault(rule["security_id"], []).append(rule)
    # These caches live only for this reconstruction. A later query must read
    # and hash its adopted originals again, including after a file is damaged.
    amount_rows: dict[str, dict[tuple[object, object], list[dict[str, object]]]] = {}
    amount_fields: dict[str, tuple[str, ...]] = {}
    checked_proofs: set[str] = set()
    units = {
        "yuan": Decimal(1),
        "thousand_yuan": Decimal(1000),
        "ten_thousand_yuan": Decimal(10000),
    }
    results = []
    for day in days:
        business_date = day["business_date"]
        if business_date not in amounts:
            raise ValueError("breadth_amount_day_missing")
        members = {
            m["security_id"]: m for m in day["members"] if m["security_type"] == "ordinary_a"
        }
        entries = amounts[business_date]["members"]
        if len(entries) != len(members) or {entry["security_id"] for entry in entries} != set(
            members
        ):
            raise ValueError("breadth_amount_membership_mismatch")
        required_proofs = set(document["coverage_evidence"])
        total = advancing = Decimal(0)
        ledger = []
        missing_amounts = []
        advancing_unknown = False
        for entry in entries:
            member = members[entry["security_id"]]
            if entry["ts_code"] != member["ts_code"]:
                raise ValueError("breadth_amount_identity_mismatch")
            rules = [
                rule
                for rule in rules_by_identity.get(member["security_id"], [])
                if rule["exchange"] == member["ts_code"].split(".")[1]
                and rule["effective_from"] <= business_date
                and (rule["effective_until"] is None or business_date < rule["effective_until"])
            ]
            if len(rules) != 1 or set(entry["required_methods"]) != set(rules[0]["methods"]):
                raise ValueError("breadth_amount_scope_mismatch")
            required_proofs.update(rules[0]["evidence"])
            methods = entry["required_methods"]
            covered = [
                method for component in entry["components"] for method in component["methods"]
            ]
            if (
                not methods
                or any(not component["methods"] for component in entry["components"])
                or len(set(methods)) != len(methods)
                or len(set(covered)) != len(covered)
                or set(methods) != set(covered)
            ):
                raise ValueError("breadth_amount_coverage_mismatch")
            member_total = Decimal(0)
            member_unknown = False
            components = []
            adopted_fields: set[tuple[str, str]] = set()
            adopted_source_fields: set[tuple[str, str]] = set()
            for component in entry["components"]:
                if component["state"] == "not_applicable":
                    rule = component.get("rule", {})
                    start, end = rule.get("effective_from"), rule.get("effective_until")
                    references = rule.get("evidence", [])
                    if (
                        not isinstance(start, str)
                        or date.fromisoformat(start).isoformat() != start
                        or start > business_date
                        or (
                            end is not None
                            and (
                                not isinstance(end, str)
                                or date.fromisoformat(end).isoformat() != end
                                or business_date >= end
                            )
                        )
                        or not references
                        or len(set(references)) != len(references)
                        or not set(references) <= proofs.keys()
                    ):
                        raise ValueError("breadth_amount_applicability_unproven")
                    required_proofs.update(references)
                    components.append({**component, "amount_yuan": None})
                    continue
                digest = component["artifact_hash"]
                fact = digest, component["field"]
                if fact in adopted_fields:
                    raise ValueError("breadth_amount_fact_duplicate")
                adopted_fields.add(fact)
                if component["state"] != "reported" or digest not in proofs:
                    raise ValueError("breadth_amount_required_value_missing")
                proof = proofs[digest]
                source_fact = proof["source_reference"], component["field"]
                if source_fact in adopted_source_fields:
                    raise ValueError("breadth_amount_fact_duplicate")
                adopted_source_fields.add(source_fact)
                published_date = proof.get("published_date")
                proof_times = [
                    _breadth_time(proof[field]) for field in ("release_at", "public_available_at")
                ]
                if (published_date is not None and published_date < business_date) or any(
                    value is not None
                    and value.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
                    < business_date
                    for value in proof_times
                ):
                    raise ValueError("breadth_amount_publication_precedes_period")
                if digest not in amount_rows:
                    original = json.loads(_breadth_artifact(artifacts, digest), parse_float=Decimal)
                    if original.get("code") != 0:
                        raise ValueError("breadth_amount_response_invalid")
                    rows = _response_rows(original, required_fields=("ts_code", "trade_date"))
                    indexed: dict[tuple[object, object], list[dict[str, object]]] = {}
                    for row in rows:
                        indexed.setdefault((row["ts_code"], row["trade_date"]), []).append(row)
                    amount_rows[digest] = indexed
                    amount_fields[digest] = tuple(original["data"]["fields"])
                    checked_proofs.add(digest)
                if component["field"] not in amount_fields[digest]:
                    raise ValueError("tushare_response_required_field_missing")
                matching = amount_rows[digest].get(
                    (member["ts_code"], business_date.replace("-", "")), []
                )
                if len(matching) != 1:
                    raise ValueError("breadth_amount_fact_ambiguous")
                raw_value = matching[0][component["field"]]
                required_proofs.add(digest)
                if raw_value is None:
                    member_unknown = True
                    missing_amounts.append(
                        {
                            "security_id": member["security_id"],
                            "ts_code": member["ts_code"],
                            "methods": component["methods"],
                            "reason": "required_amount_unknown",
                        }
                    )
                    components.append({**component, "state": "unknown", "amount_yuan": None})
                    continue
                value = _breadth_price(raw_value, allow_zero=True)
                if component["unit"] not in units:
                    raise ValueError("breadth_amount_unit_invalid")
                value *= units[component["unit"]]
                member_total += value
                required_proofs.add(digest)
                components.append({**component, "amount_yuan": str(value)})
            total += member_total
            if member["state"] == "advance":
                advancing += member_total
                advancing_unknown = advancing_unknown or member_unknown
            ledger.append(
                {
                    **member,
                    "amount_yuan": None if member_unknown else str(member_total),
                    "known_amount_yuan": str(member_total),
                    "components": components,
                }
            )
        for digest in required_proofs - checked_proofs:
            _breadth_artifact(artifacts, digest)
            checked_proofs.add(digest)
        times = {}
        for field in ("release_at", "public_available_at"):
            values = [
                _breadth_time(day[field]),
                *[_breadth_time(proofs[digest][field]) for digest in required_proofs],
            ]
            times[field] = (
                max(value for value in values if value is not None).isoformat()
                if all(value is not None for value in values)
                else None
            )
        results.append(
            {
                "business_date": business_date,
                "formula_version": "ordinary-a-full-amount-v0002",
                "members": ledger,
                "input_evidence": sorted(required_proofs),
                "advancing_amount_yuan": None if advancing_unknown else str(advancing),
                "missing_amounts": missing_amounts,
                "total_amount_yuan": None if missing_amounts else str(total),
                "known_amount_yuan": str(total),
                "advancing_amount_share": float(100 * advancing / total)
                if total and not missing_amounts
                else None,
                "status": "unavailable:required_amount_unknown"
                if missing_amounts
                else "available"
                if total
                else "unavailable:zero_total_amount",
                **times,
            }
        )
    return results


def amount_breadth_scalars(days: list[dict[str, Any]]) -> tuple[ContextScalar, ...]:
    from pring_cycle.tushare_context import ContextScalar

    return tuple(
        ContextScalar(
            metric_id="CN_EQ_ADV_AMOUNT_SHARE",
            api_name="amount_breadth",
            source_field="advancing_amount_share",
            period_kind="business_day",
            period_start=day["business_date"],
            period_end=day["business_date"],
            dimensions={
                "measure": "advancing_amount_share",
                "universe": "point_in_time_traded_a_shares",
            },
            value=day["advancing_amount_share"],
            unit="percent",
            release_at=_breadth_time(day["release_at"]),
            public_available_at=_breadth_time(day["public_available_at"]),
        )
        for day in days
        if day["advancing_amount_share"] is not None
    )
