"""Commodity contract choices made from original-backed public information."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.evidence import (
    AsOfMode,
    EvidenceRepository,
    MetricSeriesPoint,
    SourceClaimAcquisition,
    SourceClaimInput,
)
from pring_cycle.futures_input_reads import (
    FuturesInputReader,
    futures_input_reader,
    shared_futures_input_reads,
)
from pring_cycle.futures_inputs import PRODUCT_EXCHANGES
from pring_cycle.read_scope import claims_checked_once
from pring_cycle.runtime import RuntimePaths

COMMODITY_FORMULA_VERSION = "ex-hog-calendar-settlement-v0002"
COMMODITY_BASE_DATE = date(2026, 3, 6)
COMMODITY_METRICS = frozenset({"CN_COMMODITY_EX_HOG_BASKET", "CN_COMMODITY_SLEEVE_CONTRIBUTION"})
COMMODITY_SOURCE_CODE = "tushare:fut_daily:" + COMMODITY_FORMULA_VERSION
COMMODITY_SLEEVES = (
    ("copper", ("CU",), Fraction(2, 15)),
    ("rebar", ("RB",), Fraction(2, 15)),
    ("polypropylene", ("PP",), Fraction(2, 15)),
    ("textiles", ("CF", "TA"), Fraction(2, 15)),
    ("rubber", ("RU",), Fraction(2, 15)),
    ("pulp", ("SP",), Fraction(2, 15)),
    ("crude_oil", ("SC",), Fraction(1, 5)),
)


def _frozen_session(
    paths: RuntimePaths,
    product: str,
    business_date: date,
    latest: dict[str, Any],
    system_as_of: datetime | None,
    reader: FuturesInputReader,
) -> dict[str, Any] | None:
    versions = [latest]
    current = latest
    while True:
        published = datetime.fromisoformat(current["public_available_at"])
        older = reader.select(
            products=(product,),
            business_date=business_date,
            mode=AsOfMode.PUBLIC,
            as_of=published - timedelta(microseconds=1),
            system_as_of=system_as_of,
        )
        previous = next((s for s in older["sessions"] if s["product"] == product), None)
        if previous is None:
            break
        versions.append(previous)
        current = previous
    selected = None
    for version in reversed(versions):
        published = datetime.fromisoformat(version["public_available_at"])
        if published >= datetime.fromisoformat(version["session_start_at"]):
            continue
        if selected is None or published < datetime.fromisoformat(selected["session_start_at"]):
            selected = version
    return selected


def select_commodity_contracts(
    paths: RuntimePaths,
    *,
    products: tuple[str, ...],
    business_date: date,
    as_of: datetime,
    mode: AsOfMode,
    reader: FuturesInputReader | None = None,
) -> dict[str, Any]:
    """Select the nearest expiry with over ten open days, before its T session.

    Later announcements cannot change the choice for T. SYSTEM also limits
    the input acquisitions and reviews to those validated before its cutoff.
    Returned contract, calendar and session facts retain their acquisition lineage.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("commodity_cutoff_timezone_required")
    reader = reader or futures_input_reader(paths)
    system_as_of = as_of if mode is AsOfMode.SYSTEM else None
    notice_cutoff = min(
        as_of,
        datetime.combine(business_date, time.min, ZoneInfo("Asia/Shanghai"))
        - timedelta(microseconds=1),
    )
    visible = reader.select(
        products=products,
        business_date=business_date,
        mode=AsOfMode.PUBLIC,
        as_of=notice_cutoff,
        system_as_of=system_as_of,
    )
    day = business_date.isoformat()
    selections = []
    missing = []
    for product in products:
        session = next((s for s in visible["sessions"] if s["product"] == product), None)
        if session is None:
            missing.append("commodity_session_missing:" + product)
            continue
        session = _frozen_session(paths, product, business_date, session, system_as_of, reader)
        if session is None:
            missing.append("commodity_session_not_known_before_start:" + product)
            continue
        # A notice on T itself only affects the next trading day's choice.
        cutoff = min(
            notice_cutoff,
            datetime.fromisoformat(session["session_start_at"]) - timedelta(microseconds=1),
        )
        known = reader.select(
            products=(product,),
            business_date=business_date,
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
            system_as_of=system_as_of,
        )
        failures = known["contract_failures"]
        if failures:
            missing.extend("commodity_contract_unavailable:" + f["contract_code"] for f in failures)
            continue
        exchange = PRODUCT_EXCHANGES[product]
        calendar = {
            item["business_date"]: item
            for item in known["calendar"]
            if item["exchange"] == exchange
        }
        if day not in calendar or calendar[day]["is_open"] is not True:
            missing.append("commodity_trading_day_unavailable:" + product)
            continue
        contracts = sorted(known["contracts"], key=lambda c: c["last_trade_date"])
        for contract in contracts:
            expiry = date.fromisoformat(contract["last_trade_date"])
            required_days = [
                (business_date + timedelta(days=offset)).isoformat()
                for offset in range(1, (expiry - business_date).days + 1)
            ]
            gaps = [d for d in required_days if d not in calendar or calendar[d]["is_open"] is None]
            if gaps:
                missing.extend("commodity_calendar_unavailable:" + exchange + ":" + d for d in gaps)
                break
            remaining = sum(calendar[d]["is_open"] is True for d in required_days)
            if remaining <= 10:
                continue
            if sum(c["last_trade_date"] == contract["last_trade_date"] for c in contracts) != 1:
                missing.append("commodity_expiry_ambiguous:" + product)
                break
            selections.append(
                {
                    "product": product,
                    "contract_code": contract["contract_code"],
                    "remaining_open_days": remaining,
                    "selection_cutoff": cutoff.isoformat(),
                    "contract": contract,
                    "session": session,
                    "calendar": [calendar[day], *(calendar[d] for d in required_days)],
                }
            )
            break
        else:
            missing.append("commodity_eligible_contract_missing:" + product)
    return {"selections": selections, "missing": sorted(set(missing))}


def calculate_commodity_returns(
    paths: RuntimePaths,
    *,
    products: tuple[str, ...],
    business_date: date,
    as_of: datetime,
    mode: AsOfMode,
    reader: FuturesInputReader | None = None,
) -> dict[str, Any]:
    """Read point-in-time returns using each frozen choice's own settle and pre_settle."""
    reader = reader or futures_input_reader(paths)
    choices = select_commodity_contracts(
        paths,
        products=products,
        business_date=business_date,
        as_of=as_of,
        mode=mode,
        reader=reader,
    )
    inputs = reader.select(products=products, business_date=business_date, mode=mode, as_of=as_of)
    settlements = {item["contract_code"]: item for item in inputs["settlements"]}
    missing = list(choices["missing"])
    returns = []
    for choice in choices["selections"]:
        code = choice["contract_code"]
        settlement = settlements.get(code)
        if settlement is None or settlement["status"] != "available":
            missing.append("commodity_settlement_unavailable:" + code)
            continue
        daily_return = Fraction(settlement["settle"]) / Fraction(settlement["pre_settle"]) - 1
        returns.append(
            {
                "product": choice["product"],
                "daily_return": float(daily_return),
                "selection": choice,
                "settlement": settlement,
            }
        )
    return {"returns": returns, "missing": sorted(set(missing))}


def calculate_commodity_basket(
    paths: RuntimePaths,
    *,
    business_date: date,
    as_of: datetime,
    mode: AsOfMode,
) -> dict[str, Any]:
    """Rebuild the fixed-base basket and contributions at a PUBLIC or SYSTEM cutoff."""
    if business_date < COMMODITY_BASE_DATE:
        raise ValueError("commodity_date_precedes_fixed_base")
    products = tuple(product for _, members, _ in COMMODITY_SLEEVES for product in members)
    exchanges = {PRODUCT_EXCHANGES[product] for product in products}
    result: dict[str, Any] = {
        "formula_version": COMMODITY_FORMULA_VERSION,
        "base_date": COMMODITY_BASE_DATE.isoformat(),
        "base_level": 1000,
        "weights": {sleeve: float(weight) for sleeve, _, weight in COMMODITY_SLEEVES},
        "base_inputs": [],
        "days": [],
        "missing": [],
    }
    # One consistent read of the captured inputs for the whole fixed-base chain.
    reader = futures_input_reader(paths)
    base_choices = select_commodity_contracts(
        paths,
        products=products,
        business_date=COMMODITY_BASE_DATE,
        as_of=as_of,
        mode=mode,
        reader=reader,
    )
    base_inputs = reader.select(
        products=products,
        business_date=COMMODITY_BASE_DATE,
        mode=mode,
        as_of=as_of,
    )
    base_prices = {item["contract_code"]: item for item in base_inputs["settlements"]}
    result["missing"].extend(base_choices["missing"])
    for choice in base_choices["selections"]:
        price = base_prices.get(choice["contract_code"])
        if price is None or price["settle"] is None:
            result["missing"].append("commodity_base_settlement_missing:" + choice["contract_code"])
        else:
            result["base_inputs"].append({"selection": choice, "settlement": price})
    if result["missing"] or len(result["base_inputs"]) != len(products):
        result["missing"].append("commodity_fixed_base_unavailable")
        return result
    level = Fraction(1000)
    for offset in range(1, (business_date - COMMODITY_BASE_DATE).days + 1):
        day = COMMODITY_BASE_DATE + timedelta(days=offset)
        inputs = reader.select(products=products, business_date=day, mode=mode, as_of=as_of)
        calendar = {
            item["exchange"]: item
            for item in inputs["calendar"]
            if item["business_date"] == day.isoformat()
        }
        if any(
            exchange not in calendar or calendar[exchange]["is_open"] is None
            for exchange in exchanges
        ):
            result["missing"].append("commodity_output_calendar_unavailable:" + day.isoformat())
            break
        if all(calendar[exchange]["is_open"] is False for exchange in exchanges):
            continue
        daily = calculate_commodity_returns(
            paths, products=products, business_date=day, as_of=as_of, mode=mode, reader=reader
        )
        if daily["missing"]:
            result["missing"].extend(reason + ":" + day.isoformat() for reason in daily["missing"])
            break
        product_returns = {
            item["product"]: Fraction(item["settlement"]["settle"])
            / Fraction(item["settlement"]["pre_settle"])
            - 1
            for item in daily["returns"]
        }
        contributions = {
            sleeve: weight * sum(product_returns[product] for product in members) / len(members)
            for sleeve, members, weight in COMMODITY_SLEEVES
        }
        basket_return = sum(contributions.values())
        level *= 1 + basket_return
        result["days"].append(
            {
                "business_date": day.isoformat(),
                "level": float(level),
                "daily_return": float(basket_return),
                "contributions": {
                    sleeve: float(value * 100) for sleeve, value in contributions.items()
                },
                "returns": daily["returns"],
                "calendar": list(calendar.values()),
            }
        )
    return result


def _commodity_facts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        if "kind" in value and "acquisition_ids" in value:
            return [value]
        return [fact for child in value.values() for fact in _commodity_facts(child)]
    if isinstance(value, list):
        return [fact for child in value for fact in _commodity_facts(child)]
    return []


def _commodity_members(result: dict[str, Any]) -> list[dict[str, Any]]:
    day = result["days"][-1]
    dimensions = {"formula_version": COMMODITY_FORMULA_VERSION}
    return [
        {
            "metric_id": "CN_COMMODITY_EX_HOG_BASKET",
            "dimensions": dimensions,
            "value": day["level"],
            "unit": "index_points",
            "field": "level",
        },
        *[
            {
                "metric_id": "CN_COMMODITY_SLEEVE_CONTRIBUTION",
                "dimensions": {**dimensions, "sleeve": sleeve},
                "value": contribution,
                "unit": "percentage_points",
                "field": sleeve,
            }
            for sleeve, contribution in day["contributions"].items()
        ],
    ]


def _commodity_meaning(value: Any) -> Any:
    """The meaning of a result, built. Kept as what ``_commodity_meaning_equal`` is checked against.

    Nothing in production builds this any more: deciding agreement walks both sides instead
    (see ``_commodity_meaning_equal``). It stays because the equivalence test needs a second,
    obviously-correct implementation to compare against -- a comparison that only checked
    itself would prove nothing.
    """
    if isinstance(value, dict):
        return {
            key: (
                Fraction(child)
                if key in {"settle", "pre_settle", "contract_multiplier"} and child is not None
                else _commodity_meaning(child)
            )
            for key, child in value.items()
            if key
            not in {
                "available_at",
                "acquisition_ids",
                "raw_hashes",
                "evidence_hashes",
                "source_symbol",
            }
        }
    if isinstance(value, list):
        return [_commodity_meaning(child) for child in value]
    return value


_COMMODITY_EXACT_FIELDS = {"settle", "pre_settle", "contract_multiplier"}
_COMMODITY_IDENTITY_FIELDS = {
    "available_at",
    "acquisition_ids",
    "raw_hashes",
    "evidence_hashes",
    "source_symbol",
}


def _commodity_meaning_equal(left: Any, right: Any) -> bool:
    """Decide agreement while walking, instead of building a structure to throw away.

    This answers exactly the question ``_commodity_meaning(left) == _commodity_meaning(right)``
    answers -- the same identity-only keys are ignored, the same three settlement fields are
    compared as exact Fractions rather than as the strings that spell them. What it does not do
    is materialise either side: one result is roughly 160k nodes, and a disagreement near the
    top makes every node below it irrelevant, so building them first spends most of its time
    on values no one reads.
    """
    if isinstance(left, dict):
        if not isinstance(right, dict):
            return False
        keys = {key for key in left if key not in _COMMODITY_IDENTITY_FIELDS}
        if keys != {key for key in right if key not in _COMMODITY_IDENTITY_FIELDS}:
            return False
        for key in keys:
            child, other = left[key], right[key]
            if key in _COMMODITY_EXACT_FIELDS and child is not None:
                # A None on one side only is a disagreement, as it is for the built structure.
                if other is None or Fraction(child) != Fraction(other):
                    return False
            elif not _commodity_meaning_equal(child, other):
                return False
        return True
    if isinstance(right, dict):
        return False
    if isinstance(left, list):
        return (
            isinstance(right, list)
            and len(left) == len(right)
            and all(_commodity_meaning_equal(a, b) for a, b in zip(left, right, strict=True))
        )
    if isinstance(right, list):
        return False
    return bool(left == right)


def _commodity_publication(result: dict[str, Any]) -> datetime | None:
    publications = [fact["public_available_at"] for fact in _commodity_facts(result)]
    if not publications or any(t is None for t in publications):
        return None
    return max(datetime.fromisoformat(t) for t in publications)


def _commodity_document(
    inputs: tuple[SourceClaimAcquisition, ...], artifacts: Path
) -> dict[str, Any]:
    snapshots = [i for i in inputs if i.receipt.api_name == "commodity_basket"]
    if len(snapshots) != 1 or any(i.receipt.state != "validated" for i in inputs):
        raise ValueError("commodity_result_original_required")
    snapshot = snapshots[0]
    document: dict[str, Any] = json.loads(snapshot.raw)
    if (
        document != json.loads(snapshot.normalized)
        or document["schema_version"] != "commodity-result-v0002"
        or snapshot.receipt.provider != "derived"
        or snapshot.receipt.parser_version != COMMODITY_FORMULA_VERSION
        or snapshot.receipt.parameters != {"result_hash": hashlib.sha256(snapshot.raw).hexdigest()}
    ):
        raise ValueError("commodity_result_original_mismatch")
    result = document["result"]
    if (
        result["missing"]
        or not result["days"]
        or result["days"][-1]["business_date"] != document["business_date"]
    ):
        raise ValueError("commodity_result_target_output_missing")
    facts = _commodity_facts(result)
    parents = {identity for fact in facts for identity in fact["acquisition_ids"]}
    if {i.receipt.acquisition_id for i in inputs} != parents | {snapshot.receipt.acquisition_id}:
        raise ValueError("commodity_result_parent_mismatch")
    for digest in {
        h for fact in facts for key in ("raw_hashes", "evidence_hashes") for h in fact.get(key, [])
    }:
        if hashlib.sha256((artifacts / digest[:2] / digest).read_bytes()).hexdigest() != digest:
            raise ValueError("commodity_result_parent_original_invalid")
    return document


def persist_commodity_basket(
    paths: RuntimePaths,
    *,
    business_date: date,
    as_of: datetime,
    mode: AsOfMode,
    definition_version: str,
) -> dict[str, Any]:
    """Publish original-backed fixed-base results without rewriting input receipts."""
    from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS

    if definition_version in BUILTIN_CATALOG_VERSIONS:
        raise ValueError("commodity_registered_definition_required")
    # The calculation and the pre-write recalculation read the same captured inputs; the
    # derived result captured in between is not a futures input.
    with shared_futures_input_reads():
        return _persist_commodity_basket(
            paths,
            business_date=business_date,
            as_of=as_of,
            mode=mode,
            definition_version=definition_version,
        )


def _persist_commodity_basket(
    paths: RuntimePaths,
    *,
    business_date: date,
    as_of: datetime,
    mode: AsOfMode,
    definition_version: str,
) -> dict[str, Any]:
    from pring_cycle.acquisition import AcquisitionRepository, utc_now
    from pring_cycle.catalog import metric_definition
    from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput

    result = calculate_commodity_basket(paths, business_date=business_date, as_of=as_of, mode=mode)
    if (
        result["missing"]
        or not result["days"]
        or result["days"][-1]["business_date"] != business_date.isoformat()
    ):
        return {
            "missing": result["missing"] or ["commodity_target_output_missing"],
            "claim_ids": [],
        }
    facts = _commodity_facts(result)
    parents = tuple(sorted({identity for fact in facts for identity in fact["acquisition_ids"]}))
    published = _commodity_publication(result)
    document = {
        "schema_version": "commodity-result-v0002",
        "business_date": business_date.isoformat(),
        "mode": mode.value,
        "as_of": as_of.isoformat(),
        "definition_version": definition_version,
        "result": result,
    }
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
    output = acquisitions.capture(
        provider="derived",
        api_name="commodity_basket",
        parameters={"result_hash": digest},
        fields="level,seven_sleeve_contributions",
        parser_version=COMMODITY_FORMULA_VERSION,
        fetch=lambda: raw,
        parse=json.loads,
        normalize=lambda value: value,
    )
    identities = (*parents, output.receipt.acquisition_id)
    receipts = [acquisitions.get(identity) for identity in identities]
    fetched = max(r.received_at for r in receipts if r.received_at is not None)
    available = max(r.validated_at for r in receipts if r.validated_at is not None)
    evidence = EvidenceRepository(paths.database)
    claims = []
    for member in _commodity_members(result):
        definition = metric_definition(
            member["metric_id"], definition_version=definition_version, database_path=paths.database
        )
        claims.append(
            SourceClaimInput(
                metric_id=member["metric_id"],
                definition_version=definition_version,
                period_kind="business_day",
                period_start=business_date.isoformat(),
                period_end=business_date.isoformat(),
                dimensions=member["dimensions"],
                value=member["value"],
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit=member["unit"],
                provider="tushare",
                source_reference=f"tushare:commodity_basket:{member['field']}:{business_date}",
                release_event_id="commodity:" + digest,
                release_at=published,
                public_available_at=published,
                fetched_at=fetched,
                available_at=available,
                certification_status=definition.certification_status,
                quality_status="validated",
                acquisition_ids=identities,
            )
        )
    stored = evidence.append_source_claims(tuple(claims), availability_clock=utc_now)
    return {"missing": [], "claim_ids": [claim.claim_id for claim in stored], "result_hash": digest}


def commodity_claims_matching_acquisitions(
    repository: EvidenceRepository,
    points: dict[str, tuple[MetricSeriesPoint, ...]],
    *,
    database_path: Path,
    artifacts: Path,
    definition_version: str,
    mode: AsOfMode,
    as_of: datetime,
) -> set[str]:
    """Recheck adopted inputs and computation at the caller's actual point in time."""
    paths = RuntimePaths(
        config=database_path.parent,
        data=database_path.parent,
        state=database_path.parent,
        cache=database_path.parent,
    )
    if paths.artifacts != artifacts:
        raise ValueError("commodity_artifact_root_mismatch")
    selected = {
        p.selected_claim_id: (metric, p)
        for metric, series in points.items()
        for p in series
        if p.selected_claim_id is not None
    }
    # The check reads the claim's immutable parents and the reviewed futures inputs at this
    # cutoff, so a shared read checks a claim once per cutoff.
    return claims_checked_once(
        "commodity_claim_checks",
        (str(database_path), definition_version, mode, as_of),
        set(selected),
        lambda claim_ids: _commodity_claims_valid(
            repository,
            {claim_id: selected[claim_id] for claim_id in claim_ids},
            paths,
            artifacts,
            definition_version,
            mode,
            as_of,
        ),
    )


def _commodity_claims_valid(
    repository: EvidenceRepository,
    selected: dict[str, tuple[str, MetricSeriesPoint]],
    paths: RuntimePaths,
    artifacts: Path,
    definition_version: str,
    mode: AsOfMode,
    as_of: datetime,
) -> set[str]:
    inputs_by_claim = repository.source_claim_acquisitions_many(tuple(selected))
    # The level and seven contribution claims of one day share one result snapshot. Groups are
    # checked one at a time in date order, so at most one snapshot and one day's recalculation
    # are held while every claim is still compared with its own day's recalculation.
    groups: dict[tuple[str, ...], list[str]] = {}
    for claim_id, inputs in inputs_by_claim.items():
        groups.setdefault(tuple(sorted(i.receipt.acquisition_id for i in inputs)), []).append(
            claim_id
        )
    valid = set()
    expected_day: str | None = None
    expected: Any = None
    for claim_ids in sorted(
        groups.values(), key=lambda ids: min(selected[i][1].period_end for i in ids)
    ):
        try:
            document = _commodity_document(inputs_by_claim[claim_ids[0]], artifacts)
        except (ValueError, KeyError, TypeError, LookupError, OSError):
            continue
        result = document["result"]
        agreement: bool | None = None
        # The publication time is a property of the group's result, not of a claim, and the
        # loop never rebinds or writes result. Computing it per claim walked the same ~160k
        # nodes four times over on average. It stays inside the try so that a malformed
        # result still invalidates the claim it was first reached from, exactly as before.
        published: datetime | None = None
        published_known = False
        for claim_id in claim_ids:
            metric, point = selected[claim_id]
            try:
                if (
                    document["definition_version"] != definition_version
                    or document["business_date"] != point.period_end
                ):
                    continue
                if expected_day != point.period_end:
                    # Release the previous day first; a failed recalculation is retried.
                    expected_day, expected = None, None
                    expected = calculate_commodity_basket(
                        paths,
                        business_date=date.fromisoformat(point.period_end),
                        mode=mode,
                        as_of=as_of,
                    )
                    expected_day = point.period_end
                # Equivalent later deliveries may have different receipt identities.
                # Preserve the historical claim's parents, validating their originals,
                # while comparing the facts selected at the caller's cutoff.
                if agreement is None:
                    agreement = _commodity_meaning_equal(result, expected) and not result[
                        "missing"
                    ]
                if not agreement:
                    continue
                claim = next(c for c in point.claims if c.claim_id == claim_id)
                if not published_known:
                    published = _commodity_publication(result)
                    published_known = True
                if any(
                    m["metric_id"] == metric
                    and m["dimensions"] == point.dimensions
                    and m["value"] == claim.value
                    and m["unit"] == claim.unit
                    and claim.provider == "tushare"
                    and claim.source_reference
                    == f"tushare:commodity_basket:{m['field']}:{point.period_end}"
                    and claim.release_at == published
                    and claim.public_available_at == published
                    for m in _commodity_members(result)
                ):
                    valid.add(claim_id)
            except (ValueError, KeyError, TypeError, LookupError, OSError):
                continue
    return valid


def require_commodity_results(database_path: Path, claims: tuple[SourceClaimInput, ...]) -> None:
    """Validate each derived batch against captured inputs before claiming validated values."""
    from pring_cycle.acquisition import AcquisitionRepository
    from pring_cycle.catalog_registry import BUILTIN_CATALOG_VERSIONS

    commodity = [
        c
        for c in claims
        if c.metric_id in COMMODITY_METRICS and c.definition_version not in BUILTIN_CATALOG_VERSIONS
    ]
    if not commodity:
        return
    paths = RuntimePaths(
        config=database_path.parent,
        data=database_path.parent,
        state=database_path.parent,
        cache=database_path.parent,
    )
    acquisitions = AcquisitionRepository(database_path, paths.artifacts)
    checked: dict[tuple[str, ...], dict[str, Any]] = {}
    for claim in commodity:
        ids = tuple(
            sorted(
                {*claim.acquisition_ids, *([claim.acquisition_id] if claim.acquisition_id else [])}
            )
        )
        try:
            if ids not in checked:
                inputs = tuple(
                    SourceClaimAcquisition(
                        receipt=acquisitions.get(identity),
                        raw=acquisitions.read_content(identity, "raw"),
                        normalized=acquisitions.read_content(identity, "normalized"),
                    )
                    for identity in ids
                )
                document = _commodity_document(inputs, paths.artifacts)
                result = document["result"]
                expected = calculate_commodity_basket(
                    paths,
                    business_date=date.fromisoformat(document["business_date"]),
                    mode=AsOfMode(document["mode"]),
                    as_of=datetime.fromisoformat(document["as_of"]),
                )
                if result != expected or result["missing"]:
                    raise ValueError("commodity_result_recalculation_mismatch")
                checked[ids] = document
            document = checked[ids]
            result = document["result"]
            published = _commodity_publication(result)
            if (
                document["definition_version"] != claim.definition_version
                or document["business_date"] != claim.period_end
                or claim.public_available_at != published
                or claim.release_at != published
                or not any(
                    m["metric_id"] == claim.metric_id
                    and m["dimensions"] == claim.dimensions
                    and m["value"] == claim.value
                    and m["unit"] == claim.unit
                    for m in _commodity_members(result)
                )
            ):
                raise ValueError("commodity_result_value_mismatch")
        except (ValueError, KeyError, TypeError, LookupError, OSError) as error:
            raise ValueError("commodity_result_original_or_value_invalid") from error
