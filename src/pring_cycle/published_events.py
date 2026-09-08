from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, MetricSeriesPoint


@dataclass(frozen=True)
class PublishedEventSelection:
    selected_claim_ids: tuple[str, ...]
    incomplete_claim_ids: tuple[str, ...]
    missing_members: tuple[str, ...]


def select_published_rrr_events(
    repository: EvidenceRepository, points: tuple[MetricSeriesPoint, ...]
) -> PublishedEventSelection:
    """Require all members of each visible announcement, preserving separate events."""
    groups: dict[str, list[MetricSeriesPoint]] = {}
    for point in points:
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if claim is not None:
            groups.setdefault(claim.source_reference, []).append(point)
    selected: list[str] = []
    incomplete: list[str] = []
    missing: list[str] = []
    for source, members in groups.items():
        ids = [p.selected_claim_id for p in members if p.selected_claim_id is not None]
        publication = repository.source_claim_publication(ids[0])
        expected = publication.get("scalars") if publication is not None else None
        if (
            publication is None
            or publication.get("family") != "pbc_rrr_notice"
            or not isinstance(expected, list)
            or not expected
            or any(repository.source_claim_publication(claim_id) != publication for claim_id in ids)
        ):
            incomplete.extend(ids)
            missing.append(f"CN_RRR_EVENT:publication_contract_unavailable:{source}")
            continue
        matched: list[str] = []
        try:
            public_at = (
                datetime.fromisoformat(publication["public_available_at"])
                if publication.get("public_available_at") is not None
                else None
            )
            if public_at is not None and public_at.tzinfo is None:
                raise ValueError("publication_time_requires_timezone")
        except (TypeError, ValueError):
            incomplete.extend(ids)
            missing.append(f"CN_RRR_EVENT:publication_time_invalid:{source}")
            continue
        for member in expected:
            accepted = []
            if isinstance(member, dict) and member.get("metric_id") == "CN_RRR_EVENT":
                for point in members:
                    claim = next(c for c in point.claims if c.claim_id == point.selected_claim_id)
                    if (
                        point.period_start == member.get("period_start")
                        and point.period_end == member.get("period_end")
                        and point.dimensions == member.get("dimensions")
                        and point.selection_status == "selected"
                        and point.value_state is EvidenceValueState.REPORTED_VALUE
                        and claim.certification_status == "certified"
                        and claim.quality_status == "validated"
                        and claim.value is not None
                        and claim.value == member.get("value")
                        and claim.unit == member.get("unit")
                        and (
                            claim.public_available_at is None
                            or (public_at is not None and claim.public_available_at >= public_at)
                        )
                    ):
                        accepted.append(claim.claim_id)
            if len(accepted) == 1:
                matched.extend(accepted)
            else:
                missing.append(
                    f"CN_RRR_EVENT:published_member_missing:{json.dumps(member, sort_keys=True)}"
                )
        if len(set(matched)) == len(expected) == len(ids):
            selected.extend(matched)
        else:
            incomplete.extend(ids)
            missing.append(f"CN_RRR_EVENT:incomplete_publication:{source}")
    if not groups:
        missing.append("CN_RRR_EVENT:publication_contract_unavailable")
    return PublishedEventSelection(tuple(selected), tuple(incomplete), tuple(missing))
