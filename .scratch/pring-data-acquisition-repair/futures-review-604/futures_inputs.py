"""Captured real-month contract, exchange-calendar and settlement inputs."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pring_cycle.acquisition import AcquisitionReceipt, AcquisitionRepository
from pring_cycle.evidence import AsOfMode, publication_times
from pring_cycle.runtime import RuntimePaths

PRODUCT_EXCHANGES = {
    "CU": "SHFE",
    "RB": "SHFE",
    "PP": "DCE",
    "CF": "CZCE",
    "TA": "CZCE",
    "RU": "SHFE",
    "SP": "SHFE",
    "SC": "INE",
}
PARSER_VERSION = "tushare-futures-inputs-v0001"
BATCH_SCHEMA = "futures-input-batch-v0001"
FACT_SOURCE_APIS = {
    "contract": "fut_basic",
    "calendar": "fut_trade_cal",
    "settlement": "fut_daily",
    "session": "futures_input_evidence",
}
CONTRACT_FIELDS = (
    "ts_code",
    "symbol",
    "exchange",
    "fut_code",
    "d_month",
    "list_date",
    "delist_date",
    "quote_unit",
    "per_unit",
    "trade_unit",
)


@dataclass(frozen=True)
class FuturesInputAcquisition:
    acquisition_ids: tuple[str, ...]


def _rows(raw: bytes, fields: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    from pring_cycle.tushare_context import _response_rows

    document = json.loads(raw, parse_float=Decimal)
    if not isinstance(document, dict) or document.get("code") != 0:
        raise ValueError("futures_input_response_invalid")
    return _response_rows(document, required_fields=fields)


def _day(value: object) -> str:
    return date.fromisoformat(str(value)).isoformat()


def _contract_data(row: dict[str, object], product: str) -> dict[str, Any]:
    exchange = PRODUCT_EXCHANGES[product]
    suffix = {"SHFE": "SHF", "DCE": "DCE", "CZCE": "ZCE", "INE": "INE"}[exchange]
    month = str(row["d_month"])
    if re.fullmatch(r"[0-9]{6}", month) is None:
        raise ValueError("futures_input_contract_identity_mismatch")
    date(int(month[:4]), int(month[4:]), 1)
    symbols = {product + month[2:]}
    if exchange == "CZCE":
        symbols.add(product + month[3:])
    if (
        row["exchange"] != exchange
        or row["fut_code"] != product
        or row["ts_code"] != product + month[2:] + "." + suffix
        or str(row["symbol"]).upper() not in symbols
    ):
        raise ValueError("futures_input_contract_identity_mismatch")
    unit = "桶" if product == "SC" else "吨"
    try:
        multiplier = Decimal(str(row["per_unit"]))
    except InvalidOperation as error:
        raise ValueError("futures_input_contract_unit_invalid") from error
    if (
        row["quote_unit"] != "人民币元/" + unit
        or row["trade_unit"] != unit
        or not multiplier.is_finite()
        or multiplier <= 0
    ):
        raise ValueError("futures_input_contract_unit_invalid")
    return {
        "contract_code": str(row["ts_code"]),
        "product": product,
        "exchange": str(row["exchange"]),
        "delivery_month": month[:4] + "-" + month[4:],
        "source_symbol": str(row["symbol"]),
        "listed_on": _day(row["list_date"]),
        "last_trade_date": _day(row["delist_date"]),
        "unit": str(row["quote_unit"]),
        "contract_multiplier": str(row["per_unit"]),
        "contract_unit": str(row["trade_unit"]),
    }


def _settlement(value: object) -> str | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("futures_input_settlement_invalid") from error
    if not number.is_finite() or number <= 0:
        raise ValueError("futures_input_settlement_invalid")
    return str(number)


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _artifact(root: Path, digest: str) -> bytes:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("futures_input_evidence_hash_invalid")
    raw = (root / digest[:2] / digest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("futures_input_evidence_hash_mismatch")
    return raw


def _time(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("futures_input_publication_invalid")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("futures_input_publication_invalid")
    return result


def _validate_publication(item: dict[str, Any], proof_ids: set[str]) -> None:
    references = item["evidence"]
    if (
        not references
        or len(set(references)) != len(references)
        or not set(references) <= proof_ids
    ):
        raise ValueError("futures_input_publication_evidence_missing")
    release, public = _time(item["release_at"]), _time(item["public_available_at"])
    if item.get("published_date") is not None:
        published = date.fromisoformat(item["published_date"])
        if published.isoformat() != item["published_date"] or (
            release,
            public,
        ) != publication_times(published, ZoneInfo("Asia/Shanghai")):
            raise ValueError("futures_input_publication_invalid")
    elif public is not None and (release is None or public < release):
        raise ValueError("futures_input_publication_invalid")


def _load_evidence(
    raw: bytes,
    root: Path,
    *,
    verify_originals: bool,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    document = json.loads(raw)
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != "futures-input-evidence-v0001"
    ):
        raise ValueError("futures_input_evidence_schema_invalid")
    review = json.loads(_artifact(root, document["review_hash"]))
    reviewed_at = _time(review.get("reviewed_at"))
    subject = {k: v for k, v in document.items() if k != "review_hash"}
    if (
        review.get("schema_version") != "futures-input-evidence-review-v0001"
        or review.get("subject_hash") != hashlib.sha256(_json(subject)).hexdigest()
        or review.get("decision") != "accepted"
        or not isinstance(review.get("reviewer"), str)
        or not review["reviewer"].strip()
        or reviewed_at is None
    ):
        raise ValueError("futures_input_evidence_review_invalid")
    if received_at is not None and reviewed_at > received_at:
        raise ValueError("futures_input_evidence_review_in_future")
    proof_ids: set[str] = set()
    for proof in document["evidence"]:
        digest = proof["artifact_hash"]
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or digest in proof_ids
            or not proof["source_reference"]
        ):
            raise ValueError("futures_input_evidence_invalid")
        proof_ids.add(digest)
        if verify_originals:
            _artifact(root, digest)
    identities = set()
    for item in document["publications"]:
        identity = _json(
            {
                k: item.get(k)
                for k in ("api_name", "parameters", "raw_hash", "contract_code", "business_date")
            }
        )
        if (
            identity in identities
            or item["api_name"] not in {"fut_basic", "fut_trade_cal", "fut_daily"}
            or not re.fullmatch(r"[0-9a-f]{64}", item["raw_hash"])
        ):
            raise ValueError("futures_input_publication_identity_invalid")
        identities.add(identity)
        _validate_publication(item, proof_ids)
    sessions: set[tuple[str, str]] = set()
    for item in document.get("sessions", []):
        key = item["product"], item["business_date"]
        day = date.fromisoformat(item["business_date"])
        start = _time(item["session_start_at"])
        if (
            key in sessions
            or item["product"] not in PRODUCT_EXCHANGES
            or item["exchange"] != PRODUCT_EXCHANGES[item["product"]]
            or day.isoformat() != item["business_date"]
            or start is None
            or start.astimezone(ZoneInfo("Asia/Shanghai")).date() > day
        ):
            raise ValueError("futures_input_session_invalid")
        sessions.add(key)
        _validate_publication(item, proof_ids)
    return document


def _bind_publications(
    facts: list[dict[str, Any]],
    inputs: tuple[tuple[AcquisitionReceipt, bytes], ...],
    root: Path,
) -> None:
    packets = [(r, raw) for r, raw in inputs if r.api_name == "futures_input_evidence"]
    if not packets:
        return
    if len(packets) != 1:
        raise ValueError("futures_input_evidence_ambiguous")
    packet, raw = packets[0]
    if (
        packet.provider != "reviewed_evidence"
        or packet.fields
        or packet.parameters != {"evidence_hash": hashlib.sha256(raw).hexdigest()}
    ):
        raise ValueError("futures_input_evidence_receipt_invalid")
    document = _load_evidence(raw, root, verify_originals=False, received_at=packet.received_at)
    publications: dict[bytes, list[dict[str, Any]]] = {}
    for item in document["publications"]:
        key = _json([item["api_name"], item["parameters"], item["raw_hash"]])
        publications.setdefault(key, []).append(item)
    receipts = {r.acquisition_id: r for r, _ in inputs}
    for fact in facts:
        adopted = []
        for identity in fact["acquisition_ids"]:
            parent = receipts[identity]
            key = _json([parent.api_name, parent.parameters, parent.raw_hash])
            matches = [
                item
                for item in publications.get(key, [])
                if all(
                    item.get(field) is None or item[field] == fact.get(field)
                    for field in ("contract_code", "business_date")
                )
            ]
            if len(matches) > 1:
                raise ValueError("futures_input_publication_ambiguous")
            adopted.append(matches[0] if matches else None)
        for field in ("release_at", "public_available_at"):
            times = [_time(item[field]) if item is not None else None for item in adopted]
            fact[field] = (
                max(value for value in times if value is not None).isoformat()
                if all(value is not None for value in times)
                else None
            )
        fact["evidence_hashes"] = sorted(
            {
                document["review_hash"],
                *(digest for item in adopted if item is not None for digest in item["evidence"]),
            }
        )
        fact["acquisition_ids"].append(packet.acquisition_id)
        fact["raw_hashes"].append(packet.raw_hash)


def _fact(
    kind: str, data: dict[str, Any], parents: tuple[AcquisitionReceipt, ...]
) -> dict[str, Any]:
    return {
        "kind": kind,
        **data,
        "release_at": None,
        "public_available_at": None,
        "acquisition_ids": [r.acquisition_id for r in parents],
        "raw_hashes": [r.raw_hash for r in parents],
    }


def _facts(
    inputs: tuple[tuple[AcquisitionReceipt, bytes], ...], artifacts: Path
) -> list[dict[str, Any]]:
    contracts: dict[str, tuple[dict[str, Any], AcquisitionReceipt]] = {}
    facts = []
    for receipt, raw in inputs:
        if receipt.api_name != "fut_basic":
            continue
        for row in _rows(raw, CONTRACT_FIELDS):
            data = _contract_data(row, receipt.parameters["fut_code"])
            contracts[data["contract_code"]] = data, receipt
            facts.append(_fact("contract", data, (receipt,)))
    for receipt, raw in inputs:
        if receipt.api_name == "fut_trade_cal":
            for row in _rows(raw, ("exchange", "cal_date", "is_open")):
                business_day = _day(row["cal_date"])
                if (
                    row["exchange"] != receipt.parameters["exchange"]
                    or row["is_open"] not in (0, 1, None)
                    or not (
                        _day(receipt.parameters["start_date"])
                        <= business_day
                        <= _day(receipt.parameters["end_date"])
                    )
                ):
                    raise ValueError("futures_input_calendar_invalid")
                facts.append(
                    _fact(
                        "calendar",
                        {
                            "exchange": str(row["exchange"]),
                            "business_date": business_day,
                            "is_open": None if row["is_open"] is None else bool(row["is_open"]),
                        },
                        (receipt,),
                    )
                )
        elif receipt.api_name == "fut_daily":
            for row in _rows(raw, ("ts_code", "trade_date", "pre_settle", "settle")):
                if str(row["ts_code"]) != receipt.parameters.get("ts_code"):
                    raise ValueError("futures_input_contract_identity_mismatch")
                business_day = _day(row["trade_date"])
                if not (
                    _day(receipt.parameters["start_date"])
                    <= business_day
                    <= _day(receipt.parameters["end_date"])
                ):
                    raise ValueError("futures_input_period_mismatch")
                contract, identity = contracts[str(row["ts_code"])]
                facts.append(
                    _fact(
                        "settlement",
                        {
                            "contract_code": str(row["ts_code"]),
                            "business_date": business_day,
                            "product": contract["product"],
                            "exchange": contract["exchange"],
                            "pre_settle": _settlement(row["pre_settle"]),
                            "settle": _settlement(row["settle"]),
                            "status": "unavailable:missing_settlement"
                            if row["pre_settle"] is None or row["settle"] is None
                            else "available",
                            "unit": contract["unit"],
                        },
                        (identity, receipt),
                    )
                )
    identities: set[tuple[str, str, str]] = set()
    for fact in facts:
        key = (
            fact["kind"],
            fact.get("contract_code", fact["exchange"]),
            fact.get("business_date", ""),
        )
        if key in identities:
            raise ValueError("futures_input_identity_duplicate")
        identities.add(key)
    _bind_publications(facts, inputs, artifacts)
    for receipt, raw in inputs:
        if receipt.api_name != "futures_input_evidence":
            continue
        document = _load_evidence(raw, artifacts, verify_originals=False)
        for item in document.get("sessions", []):
            facts.append(
                {
                    **_fact(
                        "session",
                        {
                            k: item[k]
                            for k in ("product", "exchange", "business_date", "session_start_at")
                        },
                        (receipt,),
                    ),
                    "release_at": item["release_at"],
                    "public_available_at": item["public_available_at"],
                    "evidence_hashes": sorted({document["review_hash"], *item["evidence"]}),
                }
            )
    return facts


def acquire_futures_inputs(
    paths: RuntimePaths,
    *,
    request: Callable[[dict[str, Any]], bytes | dict[str, Any]],
    products: tuple[str, ...],
    start_date: date,
    end_date: date,
    evidence_hash: str | None = None,
) -> FuturesInputAcquisition:
    """Capture the input deliveries; validation does not grant source certification."""
    if end_date < start_date or not products or len(set(products)) != len(products):
        raise ValueError("futures_input_scope_invalid")
    if any(product not in PRODUCT_EXCHANGES for product in products):
        raise ValueError("futures_input_product_unsupported")
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipts: list[AcquisitionReceipt] = []

    def call(
        api: str, parameters: dict[str, str], fields: tuple[str, ...]
    ) -> tuple[dict[str, object], ...]:
        def fetch() -> bytes:
            raw = request({"api_name": api, "params": parameters, "fields": ",".join(fields)})
            if not isinstance(raw, bytes):
                raise ValueError("acquisition_raw_response_bytes_required")
            return raw

        acquired = repository.capture(
            provider="tushare",
            api_name=api,
            parameters=parameters,
            fields=",".join(fields),
            parser_version=PARSER_VERSION,
            fetch=fetch,
            parse=lambda raw: _rows(raw, fields),
            normalize=lambda rows: rows,
            defer_validation=True,
        )
        receipts.append(acquired.receipt)
        return acquired.value

    try:
        if evidence_hash is not None:
            evidence = repository.capture(
                provider="reviewed_evidence",
                api_name="futures_input_evidence",
                parameters={"evidence_hash": evidence_hash},
                fields="",
                parser_version=PARSER_VERSION,
                fetch=lambda: _artifact(paths.artifacts, evidence_hash),
                parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True),
                normalize=lambda value: value,
                defer_validation=True,
            )
            receipts.append(evidence.receipt)
        contracts: list[dict[str, object]] = []
        for product in products:
            rows = call(
                "fut_basic",
                {"exchange": PRODUCT_EXCHANGES[product], "fut_type": "1", "fut_code": product},
                CONTRACT_FIELDS,
            )
            for row in rows:
                _contract_data(row, product)
            contracts.extend(
                row
                for row in rows
                if _day(row["list_date"]) <= end_date.isoformat()
                and _day(row["delist_date"]) >= start_date.isoformat()
            )
        calendar_end = max([end_date.isoformat(), *[_day(row["delist_date"]) for row in contracts]])
        for exchange in sorted({PRODUCT_EXCHANGES[p] for p in products}):
            call(
                "fut_trade_cal",
                {
                    "exchange": exchange,
                    "start_date": start_date.strftime("%Y%m%d"),
                    "end_date": calendar_end.replace("-", ""),
                },
                ("exchange", "cal_date", "is_open"),
            )
        for contract in contracts:
            call(
                "fut_daily",
                {
                    "ts_code": str(contract["ts_code"]),
                    "start_date": max(start_date.isoformat(), _day(contract["list_date"])).replace(
                        "-", ""
                    ),
                    "end_date": min(end_date.isoformat(), _day(contract["delist_date"])).replace(
                        "-", ""
                    ),
                },
                ("ts_code", "trade_date", "pre_settle", "settle"),
            )
        ids = tuple(r.acquisition_id for r in receipts)
        facts = _facts(
            tuple((r, repository.read_content(r.acquisition_id, "raw")) for r in receipts),
            paths.artifacts,
        )
        normalized = {"schema_version": BATCH_SCHEMA, "acquisition_ids": list(ids), "facts": facts}
        for receipt in receipts:
            repository.complete_validation(receipt.acquisition_id, normalized)
        return FuturesInputAcquisition(ids)
    except Exception as error:
        for receipt in receipts:
            if repository.get(receipt.acquisition_id).state == "received":
                repository.fail_validation(receipt.acquisition_id, error)
        raise


def bind_futures_input_evidence(
    paths: RuntimePaths,
    *,
    acquisition_ids: tuple[str, ...],
    evidence_hash: str,
) -> FuturesInputAcquisition:
    """Append reviewed times to captured originals without another network request."""
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = repository.capture(
        provider="reviewed_evidence",
        api_name="futures_input_evidence",
        parameters={"evidence_hash": evidence_hash},
        fields="",
        parser_version=PARSER_VERSION,
        fetch=lambda: _artifact(paths.artifacts, evidence_hash),
        parse=lambda raw: _load_evidence(raw, paths.artifacts, verify_originals=True),
        normalize=lambda value: value,
        defer_validation=True,
    )
    try:
        if not acquisition_ids or len(set(acquisition_ids)) != len(acquisition_ids):
            raise ValueError("futures_input_acquisition_scope_invalid")
        parents = tuple(repository.get(identity) for identity in acquisition_ids)
        if any(
            r.provider != "tushare"
            or r.api_name not in {"fut_basic", "fut_trade_cal", "fut_daily"}
            or r.parser_version != PARSER_VERSION
            or r.state != "validated"
            for r in parents
        ):
            raise ValueError("futures_input_acquisition_scope_invalid")
        inputs = (*parents, evidence.receipt)
        ids = tuple(r.acquisition_id for r in inputs)
        facts = _facts(
            tuple((r, repository.read_content(r.acquisition_id, "raw")) for r in inputs),
            paths.artifacts,
        )
        repository.complete_validation(
            evidence.receipt.acquisition_id,
            {"schema_version": BATCH_SCHEMA, "acquisition_ids": list(ids), "facts": facts},
        )
        return FuturesInputAcquisition(ids)
    except Exception as error:
        repository.fail_validation(evidence.receipt.acquisition_id, error)
        raise


def _meaning(fact: dict[str, Any]) -> dict[str, Any]:
    result = {
        k: v
        for k, v in fact.items()
        if k
        not in {
            "release_at",
            "public_available_at",
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
        result["session_start_at"] = _time(result["session_start_at"])
    return result


def select_futures_inputs(
    paths: RuntimePaths,
    *,
    products: tuple[str, ...],
    business_date: date,
    mode: AsOfMode,
    as_of: datetime,
) -> dict[str, Any]:
    """Read original-backed input versions at an explicit PUBLIC or SYSTEM cutoff."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("futures_input_cutoff_timezone_required")
    day = business_date.isoformat()
    exchanges = {PRODUCT_EXCHANGES[p] for p in products}
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    seen: set[tuple[str, ...]] = set()
    selected: dict[tuple[str, str, str], tuple[datetime, list[dict[str, Any]]]] = {}
    missing = []
    for receipt in repository.history():
        if receipt.parser_version != PARSER_VERSION or receipt.state != "validated":
            continue
        try:
            document = json.loads(repository.read_content(receipt.acquisition_id, "normalized"))
            ids = tuple(document["acquisition_ids"])
            if ids in seen:
                continue
            seen.add(ids)
            parents = tuple(repository.get(identity) for identity in ids)
            if document["schema_version"] != BATCH_SCHEMA or any(
                r.state != "validated" for r in parents
            ):
                raise ValueError("futures_input_batch_invalid")
            by_id = {r.acquisition_id: r for r in parents}
            for fact in document["facts"]:
                if fact["kind"] == "calendar":
                    if fact["exchange"] not in exchanges or fact["business_date"] < day:
                        continue
                elif fact["product"] not in products:
                    continue
                if fact["kind"] in {"settlement", "session"} and fact["business_date"] != day:
                    continue
                times = [by_id[identity].validated_at for identity in fact["acquisition_ids"]]
                if not times or any(value is None for value in times):
                    raise ValueError("futures_input_validation_time_missing")
                available = max(value for value in times if value is not None)
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
                    ordered = _time(fact["public_available_at"])
                if ordered is None or ordered > as_of:
                    continue
                key = (
                    fact["kind"],
                    fact.get("contract_code", fact.get("product", fact["exchange"])),
                    fact.get("business_date", ""),
                )
                value = {**fact, "available_at": available.isoformat()}
                if key not in selected or selected[key][0] < ordered:
                    selected[key] = ordered, [value]
                elif selected[key][0] == ordered:
                    selected[key][1].append(value)
        except (ValueError, KeyError, TypeError, LookupError, OSError):
            missing.append("futures_input_delivery_invalid:" + receipt.acquisition_id)
    facts = []
    reconstructed: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    verified_proofs: set[str] = set()
    for key, (_, candidates) in selected.items():
        verified = []
        for value in candidates:
            try:
                identities = tuple(value["acquisition_ids"])
                if identities not in reconstructed:
                    reconstructed[identities] = _facts(
                        tuple(
                            (repository.get(identity), repository.read_content(identity, "raw"))
                            for identity in identities
                        ),
                        paths.artifacts,
                    )
                expected = {k: v for k, v in value.items() if k != "available_at"}
                if expected not in reconstructed[identities]:
                    raise ValueError("futures_input_normalized_mismatch")
                for digest in value.get("evidence_hashes", []):
                    if digest not in verified_proofs:
                        _artifact(paths.artifacts, digest)
                        verified_proofs.add(digest)
                verified.append(value)
            except (ValueError, KeyError, TypeError, LookupError, OSError):
                missing.append("futures_input_delivery_invalid:" + value["acquisition_ids"][0])
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
        if f["kind"] == "settlement" and f["contract_code"] in codes and f["business_date"] == day
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
        "calendar": calendar,
        "settlements": settlements,
        "sessions": sessions,
        "missing": missing,
    }
