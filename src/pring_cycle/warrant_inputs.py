from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from pring_cycle.acquisition import AcquisitionReceipt, receipt_key
from pring_cycle.evidence import (
    AsOfMode,
    ClaimView,
    EvidenceRepository,
    EvidenceValueState,
    MetricSeriesPoint,
)
from pring_cycle.tushare_context import (
    WARRANT_SYMBOLS,
    ContextScalar,
    WarrantAcquisition,
    parse_warrant_acquisition,
)

# Reparsing a delivery is a pure function of its receipt, the bytes just read and the period,
# so each cutoff of a replay reuses it. Keys include SHA-256 of both artifacts as read.
_WARRANT_PARSES: dict[tuple[object, ...], WarrantAcquisition | Exception] = {}
_WARRANT_PARSE_LIMIT = 8192


def _parsed_warrant_delivery(
    receipt: AcquisitionReceipt,
    raw: bytes,
    normalized: bytes,
    *,
    period: str,
    definition_version: str,
) -> WarrantAcquisition:
    key = (
        receipt_key(receipt),
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(normalized).hexdigest(),
        period,
        definition_version,
    )
    if key not in _WARRANT_PARSES:
        outcome: WarrantAcquisition | Exception
        try:
            outcome = parse_warrant_acquisition(
                receipt, raw, normalized, period=period, definition_version=definition_version
            )
        except (TypeError, ValueError, KeyError) as error:
            outcome = error
        if len(_WARRANT_PARSES) >= _WARRANT_PARSE_LIMIT:
            _WARRANT_PARSES.pop(next(iter(_WARRANT_PARSES)))
        _WARRANT_PARSES[key] = outcome
    outcome = _WARRANT_PARSES[key]
    if isinstance(outcome, Exception):
        raise outcome
    return outcome


@dataclass(frozen=True)
class WarrantInputSelection:
    selected_claim_ids: tuple[str, ...]
    incomplete_claim_ids: tuple[str, ...]
    missing_members: tuple[str, ...]


@dataclass(frozen=True)
class WarrantHistoryCoverage:
    complete_periods: dict[str, tuple[str, ...]]

    def is_ready(self, required_trading_days: tuple[str, ...]) -> bool:
        """Apply the existing 120-day, 95% rule to verified symbol-day deliveries."""
        required = set(required_trading_days)
        if len(required_trading_days) != 120 or len(required) != 120:
            return False
        minimum_observations = (len(required) * 95 + 99) // 100
        return all(
            len(required.intersection(self.complete_periods.get(symbol, ())))
            >= minimum_observations
            for symbol in WARRANT_SYMBOLS
        )


def select_warrant_inputs(
    repository: EvidenceRepository,
    points: tuple[MetricSeriesPoint, ...],
    *,
    period: str,
    mode: AsOfMode,
    definition_version: str,
) -> WarrantInputSelection:
    """Select all verified fields from each symbol's latest visible physical delivery."""
    points = tuple(point for point in points if point.period_end == period)
    parsed: dict[str, WarrantAcquisition] = {}
    deliveries: dict[str, AcquisitionReceipt] = {}
    delivery_ranks: dict[str, tuple[datetime, datetime]] = {}
    links: dict[str, set[str]] = {}
    invalid: set[str] = set()
    acquisitions = repository.source_claim_acquisitions_many(
        tuple(p.selected_claim_id for p in points if p.selected_claim_id is not None)
    )
    for point in points:
        claim = next((c for c in point.claims if c.claim_id == point.selected_claim_id), None)
        if claim is None:
            continue
        ordered_at = claim.public_available_at if mode is AsOfMode.PUBLIC else claim.available_at
        if ordered_at is None:
            invalid.add(claim.claim_id)
            continue
        rank = (ordered_at, claim.available_at)
        originals = acquisitions[claim.claim_id]
        if not originals:
            invalid.add(claim.claim_id)
        for original in originals:
            receipt = original.receipt
            try:
                if receipt.acquisition_id not in parsed:
                    parsed[receipt.acquisition_id] = _parsed_warrant_delivery(
                        receipt,
                        original.raw,
                        original.normalized,
                        period=period,
                        definition_version=definition_version,
                    )
                delivery = parsed[receipt.acquisition_id]
            except (TypeError, ValueError, KeyError):
                invalid.add(claim.claim_id)
                continue
            if not any(_matches_original(point, claim, scalar) for scalar in delivery.scalars):
                invalid.add(claim.claim_id)
                continue
            deliveries[receipt.acquisition_id] = receipt
            delivery_ranks[receipt.acquisition_id] = max(
                delivery_ranks.get(receipt.acquisition_id, rank), rank
            )
            links.setdefault(claim.claim_id, set()).add(receipt.acquisition_id)

    selected: set[str] = set()
    missing: set[str] = set()
    for symbol in sorted(WARRANT_SYMBOLS):
        receipts = [r for identity, r in deliveries.items() if parsed[identity].symbol == symbol]
        if not receipts:
            missing.add(f"CN_FUTURES_WARRANTS:symbol_missing:{symbol}")
            continue
        latest_rank = max(delivery_ranks[r.acquisition_id] for r in receipts)
        latest = [r for r in receipts if delivery_ranks[r.acquisition_id] == latest_rank]
        if len({r.raw_hash for r in latest}) != 1:
            missing.add(f"CN_FUTURES_WARRANTS:delivery_conflicted:{symbol}")
            continue
        receipt = latest[0]
        delivery = parsed[receipt.acquisition_id]
        same_original = {r.acquisition_id for r in receipts if r.raw_hash == receipt.raw_hash}
        current_ids: set[str] = set()
        accepted: set[str] = set()
        for scalar in delivery.scalars:
            matches = []
            for point in points:
                claim = next(
                    (c for c in point.claims if c.claim_id == point.selected_claim_id), None
                )
                if (
                    claim is not None
                    and claim.claim_id not in invalid
                    and links.get(claim.claim_id, set()) & same_original
                    and point.selection_status == "selected"
                    and point.value_state is EvidenceValueState.REPORTED_VALUE
                    and claim.certification_status == "certified"
                    and claim.quality_status == "validated"
                    and _matches_original(point, claim, scalar)
                ):
                    matches.append(claim.claim_id)
            if len(matches) == 1:
                accepted.update(matches)
                if scalar.dimensions.get("measure") == "registered_receipts":
                    current_ids.update(matches)
        if delivery.current_member_count and len(current_ids) == delivery.current_member_count:
            selected.update(accepted)
        else:
            missing.add(f"CN_FUTURES_WARRANTS:warehouse_member_missing:{symbol}")
    incomplete = {
        point.selected_claim_id
        for point in points
        if point.selected_claim_id is not None and point.selected_claim_id not in selected
    }
    return WarrantInputSelection(
        tuple(sorted(selected)), tuple(sorted(incomplete)), tuple(sorted(missing))
    )


def _matches_original(point: MetricSeriesPoint, claim: ClaimView, scalar: ContextScalar) -> bool:
    return (
        point.period_start == scalar.period_start
        and point.period_end == scalar.period_end
        and point.dimensions == scalar.dimensions
        and claim.provider == "tushare"
        and claim.source_reference == f"tushare:fut_wsr:{scalar.source_field}:{scalar.period_end}"
        and claim.unit == scalar.unit
        and (
            # Ingestion conservatively clears both times on a changed value.
            # Keep the captured assertion without granting it PUBLIC eligibility.
            (claim.release_at is None and claim.public_available_at is None)
            or (
                claim.release_at == scalar.release_at
                and claim.public_available_at == scalar.public_available_at
            )
        )
        and claim.value == scalar.value
    )
