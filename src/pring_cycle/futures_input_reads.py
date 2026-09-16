"""Point-in-time reads of the captured futures inputs.

Selection never captures or alters inputs; capture and evidence binding live in
pring_cycle.futures_inputs, which this module reads through.
"""

from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from collections import OrderedDict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository
from pring_cycle.evidence import AsOfMode
from pring_cycle.futures_inputs import (
    BATCH_SCHEMA,
    FACT_SOURCE_APIS,
    PARSER_VERSION,
    PRODUCT_EXCHANGES,
    input_facts,
    publication_time,
    read_artifact,
)
from pring_cycle.read_scope import scope_cache, shared_read_scope
from pring_cycle.runtime import RuntimePaths


def _meaning(fact: dict[str, Any]) -> dict[str, Any]:
    result = {
        k: v
        for k, v in fact.items()
        if k
        not in {
            "release_at",
            "public_available_at",
            "source_public_available_at",
            "available_at",
            "acquisition_ids",
            "raw_hashes",
            "evidence_hashes",
            "source_symbol",
        }
    }
    for field in ("pre_settle", "settle", "contract_multiplier"):
        if result.get(field) is not None:
            result[field] = Decimal(result[field])
    if "session_start_at" in result:
        result["session_start_at"] = publication_time(result["session_start_at"])
    return result


def fact_key(fact: dict[str, Any]) -> tuple[str, str, str]:
    return (
        fact["kind"],
        str(fact.get("contract_code", fact.get("product", fact.get("exchange", "")))),
        str(fact.get("business_date", "")),
    )


def damaged_review_contract_scope(
    repository: AcquisitionRepository,
    receipt: AcquisitionReceipt,
    history: tuple[AcquisitionReceipt, ...],
    artifacts: Path,
    products: tuple[str, ...],
) -> dict[str, Any]:
    """Recover version keys from originals solely to quarantine a damaged batch.

    Reconstructed facts remain invalid. Their original publication times let a
    superseding intact contract version recover without accepting the damaged one.
    """
    if receipt.api_name != "futures_input_evidence":
        raise ValueError("futures_input_normalization_invalid")
    packet = json.loads(repository.read_content(receipt.acquisition_id, "raw"))
    parents = []
    for publication in packet["publications"]:
        if (
            publication["api_name"] != "fut_basic"
            or publication["parameters"].get("fut_code") not in products
        ):
            continue
        matches = [
            r
            for r in history
            if r.api_name == "fut_basic"
            and r.raw_hash == publication["raw_hash"]
            and r.parameters == publication["parameters"]
            and r.validated_at is not None
            and receipt.validated_at is not None
            and r.validated_at <= receipt.validated_at
        ]
        if not matches:
            raise ValueError("futures_input_contract_scope_unknown")
        parents.append(
            max(matches, key=lambda r: r.validated_at.isoformat() if r.validated_at else "")
        )
    inputs = (*parents, receipt)
    facts = input_facts(
        tuple((r, repository.read_content(r.acquisition_id, "raw")) for r in inputs), artifacts
    )
    return {
        "schema_version": BATCH_SCHEMA,
        "acquisition_ids": [r.acquisition_id for r in inputs],
        "facts": [
            {**fact, "normalization_invalid": True} for fact in facts if fact["kind"] == "contract"
        ],
    }


def shared_futures_input_reads() -> AbstractContextManager[None]:
    """Share one consistent read of the captured futures inputs inside this scope.

    Use only around work that neither captures nor alters futures inputs, such as a replay.
    """
    return shared_read_scope()


def futures_input_reader(paths: RuntimePaths) -> FuturesInputReader:
    readers = scope_cache("futures_input_readers")
    if readers is None:
        return FuturesInputReader(paths)
    if paths.database not in readers:
        readers[paths.database] = FuturesInputReader(paths)
    reader: FuturesInputReader = readers[paths.database]
    return reader


def select_futures_inputs(
    paths: RuntimePaths,
    *,
    products: tuple[str, ...],
    business_date: date,
    mode: AsOfMode,
    as_of: datetime,
    system_as_of: datetime | None = None,
) -> dict[str, Any]:
    """Read input versions, optionally intersecting PUBLIC knowledge with system visibility."""
    return FuturesInputReader(paths).select(
        products=products,
        business_date=business_date,
        mode=mode,
        as_of=as_of,
        system_as_of=system_as_of,
    )


@dataclass(frozen=True)
class _BatchIndex:
    """Positions of one batch document's facts by the keys every selection filters on."""

    contracts: dict[str, list[tuple[int, dict[str, Any]]]]
    calendars: dict[str, list[tuple[int, dict[str, Any]]]]
    calendar_dates: dict[str, list[str]]
    dated: dict[tuple[str, str, str], list[tuple[int, dict[str, Any]]]]

    @classmethod
    def build(cls, document: dict[str, Any]) -> _BatchIndex:
        contracts: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        calendars: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        dated: dict[tuple[str, str, str], list[tuple[int, dict[str, Any]]]] = {}
        for position, fact in enumerate(document["facts"]):
            if fact["kind"] == "calendar":
                calendars.setdefault(fact["exchange"], []).append((position, fact))
            elif fact["kind"] in {"settlement", "session"}:
                dated.setdefault((fact["kind"], fact["product"], fact["business_date"]), []).append(
                    (position, fact)
                )
            else:
                contracts.setdefault(fact["product"], []).append((position, fact))
        for entries in calendars.values():
            entries.sort(key=lambda entry: (entry[1]["business_date"], entry[0]))
        calendar_dates = {
            exchange: [fact["business_date"] for _, fact in entries]
            for exchange, entries in calendars.items()
        }
        return cls(contracts, calendars, calendar_dates, dated)

    def relevant(
        self, products: tuple[str, ...], exchanges: set[str], day: str
    ) -> list[dict[str, Any]]:
        found = [entry for product in products for entry in self.contracts.get(product, [])]
        for exchange in exchanges:
            entries = self.calendars.get(exchange, [])
            found.extend(entries[bisect_left(self.calendar_dates.get(exchange, []), day) :])
        found.extend(
            entry
            for kind in ("settlement", "session")
            for product in products
            for entry in self.dated.get((kind, product, day), [])
        )
        return [fact for _, fact in sorted(found, key=lambda entry: entry[0])]


# Recently used selections stay cached; consecutive replay cutoffs keep reusing the same
# earlier chain steps, while older scopes are released to bound memory.
_SELECTION_CACHE_LIMIT = 8192


class FuturesInputReader:
    """Point-in-time selections over one consistent read of the captured futures inputs.

    Work derived from immutable, hash-checked contents is reused for the reader's lifetime,
    so a new reader is required to observe later deliveries, reviews or artifact damage.
    """

    def __init__(self, paths: RuntimePaths) -> None:
        self._paths = paths
        self._repository = AcquisitionRepository(paths.database, paths.artifacts)
        self._history = self._repository.history()
        self._receipts: dict[str, AcquisitionReceipt] = {}
        self._documents: dict[str, dict[str, Any]] = {}
        self._indexes: dict[int, tuple[dict[str, Any], _BatchIndex]] = {}
        self._reconstructed: dict[
            tuple[str, ...], dict[tuple[str, str, str], list[dict[str, Any]]] | Exception
        ] = {}
        self._verified: dict[int, tuple[dict[str, Any], Exception | None]] = {}
        self._proofs: dict[str, Exception | None] = {}
        self._damaged: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        self._thresholds: dict[tuple[tuple[str, ...], str], list[datetime]] = {}
        self._selections: OrderedDict[tuple[object, ...], dict[str, Any]] = OrderedDict()
        self._values: dict[int, tuple[dict[str, Any], datetime, dict[str, Any]]] = {}

    def _value(self, fact: dict[str, Any], available: datetime) -> dict[str, Any]:
        """One read-only output per stored fact, shared by every selection of this reader."""
        cached = self._values.get(id(fact))
        if cached is not None and cached[0] is fact and cached[1] == available:
            return cached[2]
        value = {**fact, "available_at": available.isoformat()}
        self._values[id(fact)] = fact, available, value
        return value

    def _receipt(self, identity: str) -> AcquisitionReceipt:
        if identity not in self._receipts:
            self._receipts[identity] = self._repository.get(identity)
        return self._receipts[identity]

    def _document(self, receipt: AcquisitionReceipt, products: tuple[str, ...]) -> dict[str, Any]:
        try:
            # One batch document is shared by every receipt in that batch. Only successful
            # hash-checked reads are reused; failures take the damaged-batch path each time.
            document = self._documents.get(receipt.normalized_hash or "")
            if document is None:
                document = json.loads(
                    self._repository.read_content(receipt.acquisition_id, "normalized")
                )
                if receipt.normalized_hash is not None:
                    self._documents[receipt.normalized_hash] = document
            return document
        except (ValueError, KeyError, TypeError, LookupError, OSError):
            key = receipt.acquisition_id, products
            if key not in self._damaged:
                self._damaged[key] = damaged_review_contract_scope(
                    self._repository, receipt, self._history, self._paths.artifacts, products
                )
            return self._damaged[key]

    def _index(self, document: dict[str, Any]) -> _BatchIndex:
        # Entries keep their document alive, so an object id is never reused while cached.
        cached = self._indexes.get(id(document))
        if cached is not None and cached[0] is document:
            return cached[1]
        index = _BatchIndex.build(document)
        self._indexes[id(document)] = document, index
        return index

    def _verify(self, fact: dict[str, Any]) -> None:
        cached = self._verified.get(id(fact))
        if cached is not None and cached[0] is fact:
            outcome = cached[1]
        else:
            try:
                self._check_against_originals(fact)
                outcome = None
            except (ValueError, KeyError, TypeError, LookupError, OSError) as error:
                outcome = error
            self._verified[id(fact)] = fact, outcome
        if outcome is not None:
            raise outcome

    def _check_against_originals(self, fact: dict[str, Any]) -> None:
        identities = tuple(fact["acquisition_ids"])
        if identities not in self._reconstructed:
            try:
                facts: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
                for item in input_facts(
                    tuple(
                        (self._receipt(identity), self._repository.read_content(identity, "raw"))
                        for identity in identities
                    ),
                    self._paths.artifacts,
                ):
                    facts.setdefault(fact_key(item), []).append(item)
                self._reconstructed[identities] = facts
            except (ValueError, KeyError, TypeError, LookupError, OSError) as error:
                self._reconstructed[identities] = error
        reconstructed = self._reconstructed[identities]
        if isinstance(reconstructed, Exception):
            raise reconstructed
        if fact not in reconstructed.get(fact_key(fact), []):
            raise ValueError("futures_input_normalized_mismatch")
        for digest in fact.get("evidence_hashes", []):
            if digest not in self._proofs:
                try:
                    read_artifact(self._paths.artifacts, digest)
                    self._proofs[digest] = None
                except (ValueError, OSError) as error:
                    self._proofs[digest] = error
            proof_error = self._proofs[digest]
            if proof_error is not None:
                raise proof_error

    def _visibility_thresholds(self, products: tuple[str, ...], day: str) -> list[datetime]:
        """Every instant a selection for this scope compares with its cutoffs."""
        key = products, day
        if key not in self._thresholds:
            exchanges = {PRODUCT_EXCHANGES[p] for p in products}
            instants: set[datetime] = set()
            for receipt in self._history:
                if receipt.parser_version != PARSER_VERSION or receipt.state != "validated":
                    continue
                if receipt.validated_at is not None:
                    instants.add(receipt.validated_at)
                try:
                    facts = self._index(self._document(receipt, products)).relevant(
                        products, exchanges, day
                    )
                except (ValueError, KeyError, TypeError, LookupError, OSError):
                    continue
                for fact in facts:
                    for field in ("public_available_at", "source_public_available_at"):
                        try:
                            instant = publication_time(fact.get(field))
                        except (ValueError, TypeError):
                            continue
                        if instant is not None:
                            instants.add(instant)
            self._thresholds[key] = sorted(instants)
        return self._thresholds[key]

    def select(
        self,
        *,
        products: tuple[str, ...],
        business_date: date,
        mode: AsOfMode,
        as_of: datetime,
        system_as_of: datetime | None = None,
    ) -> dict[str, Any]:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("futures_input_cutoff_timezone_required")
        if system_as_of is not None and (
            system_as_of.tzinfo is None or system_as_of.utcoffset() is None
        ):
            raise ValueError("futures_input_system_cutoff_timezone_required")
        day = business_date.isoformat()
        # Selection only compares cutoffs with these instants, so cutoffs between the same
        # neighbouring instants give the same result for this consistent read.
        thresholds = self._visibility_thresholds(products, day)
        key = (
            products,
            day,
            mode,
            bisect_right(thresholds, as_of),
            None if system_as_of is None else bisect_right(thresholds, system_as_of),
        )
        if key in self._selections:
            self._selections.move_to_end(key)
        else:
            if len(self._selections) >= _SELECTION_CACHE_LIMIT:
                self._selections.popitem(last=False)
            self._selections[key] = self._select(
                products=products,
                business_date=business_date,
                mode=mode,
                as_of=as_of,
                system_as_of=system_as_of,
            )
        cached = self._selections[key]
        return {name: list(value) for name, value in cached.items()}

    def _select(
        self,
        *,
        products: tuple[str, ...],
        business_date: date,
        mode: AsOfMode,
        as_of: datetime,
        system_as_of: datetime | None,
    ) -> dict[str, Any]:
        day = business_date.isoformat()
        exchanges = {PRODUCT_EXCHANGES[p] for p in products}
        seen: set[tuple[str, ...]] = set()
        selected: dict[tuple[str, str, str], tuple[datetime, list[dict[str, Any]]]] = {}
        sources: dict[int, dict[str, Any]] = {}
        missing = []
        contract_failures: list[dict[str, str]] = []
        for receipt in self._history:
            if receipt.parser_version != PARSER_VERSION or receipt.state != "validated":
                continue
            if mode is AsOfMode.SYSTEM and (
                receipt.validated_at is None or receipt.validated_at > as_of
            ):
                continue
            if system_as_of is not None and (
                receipt.validated_at is None or receipt.validated_at > system_as_of
            ):
                continue
            try:
                document = self._document(receipt, products)
                ids = tuple(document["acquisition_ids"])
                if ids in seen:
                    continue
                seen.add(ids)
                parents = tuple(self._receipt(identity) for identity in ids)
                if document["schema_version"] != BATCH_SCHEMA or any(
                    r.state != "validated" for r in parents
                ):
                    raise ValueError("futures_input_batch_invalid")
                by_id = {r.acquisition_id: r for r in parents}
                for fact in self._index(document).relevant(products, exchanges, day):
                    times = [by_id[identity].validated_at for identity in fact["acquisition_ids"]]
                    if not times or any(value is None for value in times):
                        raise ValueError("futures_input_validation_time_missing")
                    available = max(value for value in times if value is not None)
                    if system_as_of is not None and available > system_as_of:
                        continue
                    ordered: datetime | None
                    if mode is AsOfMode.SYSTEM:
                        if available > as_of:
                            continue
                        # Reviews and supporting metadata affect visibility, not the
                        # version order of the original that provides this fact.
                        source_times = [
                            by_id[identity].validated_at
                            for identity in fact["acquisition_ids"]
                            if by_id[identity].api_name == FACT_SOURCE_APIS[fact["kind"]]
                        ]
                        ordered = max(value for value in source_times if value is not None)
                    else:
                        public_available = publication_time(fact["public_available_at"])
                        if public_available is None or public_available > as_of:
                            continue
                        ordered = publication_time(fact["source_public_available_at"])
                    if ordered is None or ordered > as_of:
                        continue
                    key = (
                        fact["kind"],
                        fact.get("contract_code", fact.get("product", fact["exchange"])),
                        fact.get("business_date", ""),
                    )
                    value = self._value(fact, available)
                    sources[id(value)] = fact
                    if key not in selected or selected[key][0] < ordered:
                        selected[key] = ordered, [value]
                    elif selected[key][0] == ordered:
                        selected[key][1].append(value)
            except (ValueError, KeyError, TypeError, LookupError, OSError):
                missing.append("futures_input_delivery_invalid:" + receipt.acquisition_id)
                if receipt.api_name == "futures_input_evidence":
                    # Neither the batch nor its original can establish historical scope.
                    contract_failures.extend(
                        {"product": product, "contract_code": "unknown:" + receipt.acquisition_id}
                        for product in products
                    )
        facts = []
        for key, (_, candidates) in selected.items():
            verified = []
            for value in candidates:
                try:
                    self._verify(sources[id(value)])
                    verified.append(value)
                except (ValueError, KeyError, TypeError, LookupError, OSError):
                    missing.append("futures_input_delivery_invalid:" + value["acquisition_ids"][0])
            contract_unavailable = len(verified) != len(candidates) or any(
                _meaning(value) != _meaning(verified[0]) for value in verified[1:]
            )
            if (
                key[0] == "contract"
                and contract_unavailable
                and any(
                    value["listed_on"] <= day <= value["last_trade_date"] for value in candidates
                )
            ):
                contract_failures.append(
                    {"product": candidates[0]["product"], "contract_code": key[1]}
                )
            if not verified:
                continue
            if any(_meaning(value) != _meaning(verified[0]) for value in verified[1:]):
                missing.append("futures_input_conflict:" + ":".join(key))
            else:
                facts.append(verified[-1])
        contracts = [
            f
            for f in facts
            if f["kind"] == "contract"
            and f["product"] in products
            and f["listed_on"] <= day <= f["last_trade_date"]
        ]
        codes = {f["contract_code"] for f in contracts}
        calendar = [f for f in facts if f["kind"] == "calendar" and f["exchange"] in exchanges]
        settlements = [
            f
            for f in facts
            if f["kind"] == "settlement"
            and f["contract_code"] in codes
            and f["business_date"] == day
        ]
        sessions = [
            f
            for f in facts
            if f["kind"] == "session" and f["product"] in products and f["business_date"] == day
        ]
        for product in products:
            if not any(f["product"] == product for f in contracts):
                missing.append("futures_contract_inputs_missing:" + product)
        calendar_by_day = {(f["exchange"], f["business_date"]): f for f in calendar}
        for exchange in sorted(exchanges):
            current_days = [
                f for f in calendar if f["exchange"] == exchange and f["business_date"] == day
            ]
            if not current_days:
                missing.append("futures_calendar_missing:" + exchange)
            elif any(f["is_open"] is None for f in current_days):
                missing.append("futures_calendar_unknown:" + exchange)
            last_date = max(
                (
                    date.fromisoformat(f["last_trade_date"])
                    for f in contracts
                    if f["exchange"] == exchange
                ),
                default=business_date,
            )
            for offset in range(1, (last_date - business_date).days + 1):
                calendar_day = (business_date + timedelta(days=offset)).isoformat()
                entry = calendar_by_day.get((exchange, calendar_day))
                if entry is None:
                    missing.append(f"futures_calendar_missing:{exchange}:{calendar_day}")
                elif entry["is_open"] is None:
                    missing.append(f"futures_calendar_unknown:{exchange}:{calendar_day}")
        for product in products:
            if not any(f["product"] == product for f in sessions) and not any(
                f["exchange"] == PRODUCT_EXCHANGES[product]
                and f["business_date"] == day
                and f["is_open"] is False
                for f in calendar
            ):
                missing.append("futures_session_missing:" + product)
        for code in sorted(
            codes - {f["contract_code"] for f in settlements if f["status"] == "available"}
        ):
            missing.append("futures_settlement_missing:" + code)
        return {
            "contracts": contracts,
            "contract_failures": contract_failures,
            "calendar": calendar,
            "settlements": settlements,
            "sessions": sessions,
            "missing": missing,
        }
