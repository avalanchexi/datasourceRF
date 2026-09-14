from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, fields
from datetime import datetime
from math import isfinite
from typing import Any

from pring_cycle.evidence import EvidenceRepository, MetricSeriesPoint
from pring_cycle.tushare_context import ContextScalar, parse_interbank_acquisition

INTERBANK_METRICS = frozenset({"CN_DR007", "CN_SHIBOR_ON_1W_3M"})
_METADATA = frozenset(
    {"release_at", "public_available_at", "definition_version", "acquisition_ids"}
)


def _economic_fields(scalar: dict[str, Any]) -> str:
    value = scalar["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("interbank_normalized_value_invalid")
    economic = {key: item for key, item in scalar.items() if key not in _METADATA}
    economic["value"] = float(value)
    return json.dumps(economic, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _time(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("interbank_normalized_time_invalid")
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("interbank_normalized_time_invalid")
    return result


def interbank_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points_by_metric: Mapping[str, tuple[MetricSeriesPoint, ...]],
    *,
    definition_version: str,
) -> set[str]:
    """Require exact selected claims to match the full linked API response batch."""
    selected = {
        point.selected_claim_id: (metric, point)
        for metric, points in points_by_metric.items()
        for point in points
        if point.selected_claim_id is not None
    }
    parsed: dict[str, tuple[tuple[ContextScalar, ...], list[dict[str, Any]]] | None] = {}
    valid_ids = set()
    scalar_fields = {field.name for field in fields(ContextScalar)}
    for claim_id, acquisitions in repository.source_claim_acquisitions_many(
        tuple(selected)
    ).items():
        if not acquisitions:
            continue
        metric, point = selected[claim_id]
        expected_api = {"CN_DR007": "repo_daily", "CN_SHIBOR_ON_1W_3M": "shibor"}.get(metric)
        if expected_api is None or any(
            item.receipt.api_name != expected_api for item in acquisitions
        ):
            continue
        claim = next((item for item in point.claims if item.claim_id == claim_id), None)
        if claim is None or claim.provider != "tushare" or claim.unit != "percent":
            continue
        ids = {item.receipt.acquisition_id for item in acquisitions}
        try:
            raw_values: Counter[str] = Counter()
            raw_members: set[str] = set()
            normalized_batch = None
            for acquisition in acquisitions:
                identity = acquisition.receipt.acquisition_id
                if identity not in parsed:
                    parsed[identity] = None
                    economic = parse_interbank_acquisition(acquisition.receipt, acquisition.raw)
                    normalized = json.loads(acquisition.normalized)
                    if not isinstance(normalized, list) or any(
                        not isinstance(item, dict) or set(item) != scalar_fields
                        for item in normalized
                    ):
                        raise ValueError("interbank_normalized_schema_invalid")
                    parsed[identity] = (economic, normalized)
                result = parsed[identity]
                if result is None:
                    raise ValueError("interbank_acquisition_invalid")
                raw_scalars, normalized = result
                for raw_scalar in raw_scalars:
                    scalar_document = asdict(raw_scalar)
                    member = json.dumps(
                        {
                            key: value
                            for key, value in scalar_document.items()
                            if key not in _METADATA and key != "value"
                        },
                        sort_keys=True,
                    )
                    if member in raw_members:
                        raise ValueError("interbank_conflicting_original_member")
                    raw_members.add(member)
                    raw_values.update((_economic_fields(scalar_document),))
                if normalized_batch is not None and normalized != normalized_batch:
                    raise ValueError("interbank_joint_normalized_mismatch")
                normalized_batch = normalized
            if normalized_batch is None:
                continue
            # A filtered metric/tenor may legitimately omit raw members. Retain
            # multiplicity so duplicate or conflicting source rows cannot vanish.
            if any(count != 1 for count in raw_values.values()):
                raise ValueError("interbank_duplicate_original_member")
            seen = set()
            matched = False
            for scalar in normalized_batch:
                identity = _economic_fields(scalar)
                if identity in seen or raw_values[identity] != 1:
                    raise ValueError("interbank_normalized_original_mismatch")
                seen.add(identity)
                linked = scalar["acquisition_ids"]
                if (
                    not isinstance(linked, list)
                    or any(not isinstance(item, str) for item in linked)
                    or len(linked) != len(ids)
                    or set(linked) != ids
                ):
                    raise ValueError("interbank_normalized_link_mismatch")
                if scalar["definition_version"] not in {None, definition_version}:
                    raise ValueError("interbank_normalized_definition_mismatch")
                release_at, public_at = (
                    _time(scalar["release_at"]),
                    _time(scalar["public_available_at"]),
                )
                if (
                    scalar["metric_id"] == metric
                    and scalar["period_start"] == point.period_start
                    and scalar["period_end"] == point.period_end
                    and scalar["dimensions"] == point.dimensions
                    and scalar["value"] == point.selected_value == claim.value
                    and claim.source_reference
                    == f"tushare:{scalar['api_name']}:{scalar['source_field']}:{point.period_end}"
                    and (
                        (claim.release_at is None and claim.public_available_at is None)
                        or (claim.release_at, claim.public_available_at) == (release_at, public_at)
                    )
                ):
                    matched = True
            if matched:
                valid_ids.add(claim_id)
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
    return valid_ids
