from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.evidence import AsOfMode
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter


def encoded_rows(rows: list[dict[str, Any]]) -> bytes:
    fields = list(rows[0]) if rows else []
    return json.dumps(
        {"code": 0, "data": {"fields": fields, "items": [[r[f] for f in fields] for r in rows]}},
        ensure_ascii=False,
        sort_keys=True,
    ).encode()


def futures_input_transport(payload: dict[str, Any]) -> bytes:
    """A synthetic two-contract delivery with independently checked SC prices."""
    if payload["api_name"] == "fut_basic":
        return encoded_rows(
            [
                {
                    "ts_code": code,
                    "symbol": code.split(".")[0],
                    "exchange": "INE",
                    "fut_code": "SC",
                    "d_month": month,
                    "list_date": listed,
                    "delist_date": expiry,
                    "quote_unit": "人民币元/桶",
                    "per_unit": 1000,
                    "trade_unit": "桶",
                }
                for code, month, listed, expiry in (
                    ("SC2609.INE", "202609", "20230901", "20260831"),
                    ("SC2610.INE", "202610", "20251009", "20260930"),
                )
            ]
        )
    if payload["api_name"] == "fut_trade_cal":
        start = date.fromisoformat(payload["params"]["start_date"])
        end = date.fromisoformat(payload["params"]["end_date"])
        # Weekday-only dates are a synthetic calendar, not historical certification.
        return encoded_rows(
            [
                {
                    "exchange": "INE",
                    "cal_date": day.strftime("%Y%m%d"),
                    "is_open": int(day.weekday() < 5),
                }
                for offset in range((end - start).days + 1)
                for day in (start + timedelta(days=offset),)
            ]
        )
    assert payload["api_name"] == "fut_daily"
    code = payload["params"]["ts_code"]
    previous, settle, close = {
        "SC2609.INE": ("640.1", "584.2", "581"),
        "SC2610.INE": ("573.7", "592.3", "596.5"),
    }[code]
    return encoded_rows(
        [
            {
                "ts_code": code,
                "trade_date": "20260828",
                "pre_settle": previous,
                "settle": settle,
                "close": close,
            }
        ]
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_keep_real_months_settlement_and_unknown_public_time(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("synthetic-token", transport=futures_input_transport)
    acquired = adapter.acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
    )
    from pring_cycle.futures_inputs import select_futures_inputs

    visible = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert visible["missing"] == ["futures_session_missing:SC"]
    assert {
        c["contract_code"]: (c["delivery_month"], c["last_trade_date"], c["exchange"])
        for c in visible["contracts"]
    } == {
        "SC2609.INE": ("2026-09", "2026-08-31", "INE"),
        "SC2610.INE": ("2026-10", "2026-09-30", "INE"),
    }
    assert {
        v["contract_code"]: (v["pre_settle"], v["settle"], v["unit"])
        for v in visible["settlements"]
    } == {
        "SC2609.INE": ("640.1", "584.2", "人民币元/桶"),
        "SC2610.INE": ("573.7", "592.3", "人民币元/桶"),
    }
    assert any(
        d["business_date"] == "2026-08-28" and d["exchange"] == "INE" and d["is_open"]
        for d in visible["calendar"]
    )
    facts = visible["contracts"] + visible["calendar"] + visible["settlements"]
    assert all(f["release_at"] is None and f["public_available_at"] is None for f in facts)
    assert all(f["acquisition_ids"] and f["raw_hashes"] for f in facts)
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert set(acquired.acquisition_ids) == {r.acquisition_id for r in receipts.history()}
    assert {r.api_name for r in receipts.history()} == {"fut_basic", "fut_trade_cal", "fut_daily"}
    assert all(r.state == "validated" for r in receipts.history())
    for receipt in receipts.history():
        assert json.loads(receipts.read_content(receipt.acquisition_id, "raw"))["code"] == 0
    unavailable = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 15, tzinfo=UTC),
    )
    assert unavailable["contracts"] == [] and unavailable["settlements"] == []
    assert unavailable["missing"]


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_another_month_in_requested_contract_response(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def wrong_month(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("ts_code")
            document["data"]["items"][0][column] = "SC2610.INE"
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=wrong_month)
    with pytest.raises(ValueError, match="futures_input_contract_identity_mismatch"):
        adapter.acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    bad = next(r for r in repository.history() if r.parameters.get("ts_code") == "SC2609.INE")
    assert bad.state == "failed"
    assert all(r.state == "failed" for r in repository.history())
    raw = json.loads(repository.read_content(bad.acquisition_id, "raw"))
    assert raw["data"]["items"][0][raw["data"]["fields"].index("ts_code")] == "SC2610.INE"


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_keep_missing_settlement_as_explicit_gap(tmp_path: Path) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def missing_settle(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("settle")
            document["data"]["items"][0][column] = None
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=missing_settle)
    adapter.acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    result = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert result["missing"] == [
        "futures_session_missing:SC",
        "futures_settlement_missing:SC2609.INE",
    ]
    by_code = {r["contract_code"]: r for r in result["settlements"]}
    assert (by_code["SC2609.INE"]["pre_settle"], by_code["SC2609.INE"]["settle"]) == ("640.1", None)
    assert by_code["SC2609.INE"]["status"] == "unavailable:missing_settlement"
    assert by_code["SC2610.INE"]["settle"] == "592.3"
    assert all(
        r.state == "validated"
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("pre_settle", "0"), ("settle", "-1"), ("settle", "NaN"), ("settle", "unknown")],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_invalid_settlement_numbers(
    tmp_path: Path, field: str, value: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def invalid_price(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index(field)
            document["data"]["items"][0][column] = value
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=invalid_price)
    with pytest.raises(ValueError, match="futures_input_settlement_invalid"):
        adapter.acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    receipts = AcquisitionRepository(paths.database, paths.artifacts).history()
    assert receipts and all(r.state == "failed" for r in receipts)


def save_futures_document(paths: RuntimePaths, document: dict[str, Any]) -> str:
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return store_artifact(
        paths.database, paths.artifacts, raw, "application/json", "synthetic:futures-input-evidence"
    ).content_hash


def synthetic_futures_publications(paths: RuntimePaths) -> dict[str, Any]:
    publications = []
    evidence = []
    for api, parameters, published in (
        (
            "fut_basic",
            {"exchange": "INE", "fut_type": "1", "fut_code": "SC"},
            "2026-01-01T08:00:00+00:00",
        ),
        (
            "fut_trade_cal",
            {"exchange": "INE", "start_date": "20260828", "end_date": "20260930"},
            "2026-01-01T08:00:00+00:00",
        ),
        (
            "fut_daily",
            {"ts_code": "SC2609.INE", "start_date": "20260828", "end_date": "20260828"},
            "2026-08-28T08:00:00+00:00",
        ),
        (
            "fut_daily",
            {"ts_code": "SC2610.INE", "start_date": "20260828", "end_date": "20260828"},
            "2026-08-28T08:00:00+00:00",
        ),
    ):
        raw = futures_input_transport({"api_name": api, "params": parameters})
        raw_hash = hashlib.sha256(raw).hexdigest()
        proof = save_futures_document(
            paths,
            {
                "synthetic": True,
                "raw_hash": raw_hash,
                "published_at": published,
                "scope": parameters,
            },
        )
        evidence.append(
            {
                "artifact_hash": proof,
                "source_reference": "synthetic:publication:" + api + ":" + raw_hash,
            }
        )
        publications.append(
            {
                "api_name": api,
                "parameters": parameters,
                "raw_hash": raw_hash,
                "release_at": published,
                "public_available_at": published,
                "evidence": [proof],
            }
        )
    session = {
        "product": "SC",
        "exchange": "INE",
        "business_date": "2026-08-28",
        "session_start_at": "2026-08-27T21:00:00+08:00",
        "release_at": "2026-01-01T08:00:00+00:00",
        "public_available_at": "2026-01-01T08:00:00+00:00",
    }
    proof = save_futures_document(paths, {"synthetic": True, "session_notice": session})
    evidence.append({"artifact_hash": proof, "source_reference": "synthetic:SC-session-schedule"})
    return {
        "schema_version": "futures-input-evidence-v0001",
        "publications": publications,
        "evidence": evidence,
        "sessions": [{**session, "evidence": [proof]}],
    }


def save_futures_evidence_review(
    paths: RuntimePaths,
    document: dict[str, Any],
    *,
    reviewed_at: str = "2026-09-07T00:00:00+00:00",
    decision: str = "accepted",
) -> str:
    subject = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    review = save_futures_document(
        paths,
        {
            "schema_version": "futures-input-evidence-review-v0001",
            "subject_hash": hashlib.sha256(subject).hexdigest(),
            "reviewer": "synthetic input publication reviewer",
            "reviewed_at": reviewed_at,
            "decision": decision,
        },
    )
    return save_futures_document(paths, {**document, "review_hash": review})


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_use_reviewed_publication_originals_at_exact_cutoff(tmp_path: Path) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    evidence_hash = save_futures_evidence_review(paths, synthetic_futures_publications(paths))
    adapter = TushareContextAdapter("synthetic-token", transport=futures_input_transport)
    adapter.acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=evidence_hash,
    )
    before = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 7, 59, 59, 999999, tzinfo=UTC),
    )
    assert len(before["contracts"]) == 2 and before["calendar"]
    assert before["settlements"] == []
    after = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert after["missing"] == []
    assert {f["contract_code"]: f["settle"] for f in after["settlements"]} == {
        "SC2609.INE": "584.2",
        "SC2610.INE": "592.3",
    }
    for fact in after["settlements"]:
        assert fact["public_available_at"] == "2026-08-28T08:00:00+00:00"
        assert fact["available_at"].startswith("2026-09-08")
        assert evidence_hash in fact["raw_hashes"]
        assert fact["evidence_hashes"]
    receipts = AcquisitionRepository(paths.database, paths.artifacts)
    assert any(
        r.api_name == "futures_input_evidence" and r.state == "validated"
        for r in receipts.history()
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_month_metadata_that_disagrees_with_contract_code(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def wrong_identity(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            column = document["data"]["fields"].index("d_month")
            document["data"]["items"][0][column] = "202610"
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=wrong_identity)
    with pytest.raises(ValueError, match="futures_input_contract_identity_mismatch"):
        adapter.acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    original = next(r for r in repository.history() if r.api_name == "fut_basic")
    assert original.state == "failed" and repository.read_content(original.acquisition_id, "raw")


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_keep_unknown_calendar_day_distinct_from_closed_day(tmp_path: Path) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def unknown_calendar(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_trade_cal":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            row = next(
                r for r in document["data"]["items"] if r[fields.index("cal_date")] == "20260828"
            )
            row[fields.index("is_open")] = None
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=unknown_calendar)
    adapter.acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    result = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert result["missing"] == ["futures_calendar_unknown:INE", "futures_session_missing:SC"]
    days = {r["business_date"]: r["is_open"] for r in result["calendar"]}
    assert days["2026-08-28"] is None and days["2026-08-29"] is False
    assert {r["contract_code"]: r["settle"] for r in result["settlements"]} == {
        "SC2609.INE": "584.2",
        "SC2610.INE": "592.3",
    }


@pytest.mark.parametrize("reported_day", ["20260827", "20260831"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_settlement_outside_requested_period(
    tmp_path: Path, reported_day: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def wrong_period(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("trade_date")
            document["data"]["items"][0][column] = reported_day
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=wrong_period)
    with pytest.raises(ValueError, match="futures_input_period_mismatch"):
        adapter.acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    bad = next(r for r in repository.history() if r.parameters.get("ts_code") == "SC2609.INE")
    assert bad.state == "failed"
    assert all(r.state == "failed" for r in repository.history())
    raw = json.loads(repository.read_content(bad.acquisition_id, "raw"))
    assert raw["data"]["items"][0][raw["data"]["fields"].index("trade_date")] == reported_day


@pytest.mark.parametrize("precision", ["exact", "date_only"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_preserve_pre_night_session_versions_after_later_revision(
    tmp_path: Path, precision: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    adapter = TushareContextAdapter("synthetic-token", transport=futures_input_transport)
    first_packet = save_futures_evidence_review(paths, synthetic_futures_publications(paths))
    first = adapter.acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=first_packet,
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    first_cutoff = repository.get(first.acquisition_ids[-1]).validated_at
    assert first_cutoff is not None
    originals = {
        identity: repository.read_content(identity, "raw") for identity in first.acquisition_ids
    }

    def revised_expiry(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            column = document["data"]["fields"].index("delist_date")
            document["data"]["items"][0][column] = "20260901"
            return json.dumps(document).encode()
        return raw

    document = synthetic_futures_publications(paths)
    publication = next(p for p in document["publications"] if p["api_name"] == "fut_basic")
    publication["raw_hash"] = hashlib.sha256(
        revised_expiry({"api_name": "fut_basic", "params": publication["parameters"]})
    ).hexdigest()
    # Synthetic expiry adjustment: exact night-open time, or only its local publication date.
    if precision == "exact":
        publication["release_at"] = "2026-08-27T13:00:00+00:00"
        publication["public_available_at"] = "2026-08-27T13:00:00+00:00"
        revision_cutoff = datetime(2026, 8, 27, 13, tzinfo=UTC)
    else:
        publication["published_date"] = "2026-08-27"
        publication["release_at"] = None
        publication["public_available_at"] = "2026-08-28T00:00:00+08:00"
        revision_cutoff = datetime(2026, 8, 27, 16, tzinfo=UTC)
    proof = save_futures_document(paths, {"synthetic": True, "adjustment": dict(publication)})
    publication["evidence"] = [proof]
    document["evidence"].append(
        {"artifact_hash": proof, "source_reference": "synthetic:expiry-adjustment"}
    )
    second_packet = save_futures_evidence_review(paths, document)
    TushareContextAdapter("synthetic-token", transport=revised_expiry).acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=second_packet,
    )
    # Aug 28's synthetic session starts Aug 27 at 21:00 in Shanghai.
    for mode, cutoff, expected, packet in (
        (
            AsOfMode.PUBLIC,
            datetime(2026, 8, 27, 12, 59, 59, 999999, tzinfo=UTC),
            "2026-08-31",
            first_packet,
        ),
        (AsOfMode.PUBLIC, revision_cutoff - timedelta(microseconds=1), "2026-08-31", first_packet),
        (AsOfMode.PUBLIC, revision_cutoff, "2026-09-01", second_packet),
        (AsOfMode.SYSTEM, first_cutoff, "2026-08-31", first_packet),
        (AsOfMode.SYSTEM, datetime(2026, 9, 9, tzinfo=UTC), "2026-09-01", second_packet),
    ):
        result = select_futures_inputs(
            paths, products=("SC",), business_date=date(2026, 8, 28), mode=mode, as_of=cutoff
        )
        contract = next(c for c in result["contracts"] if c["contract_code"] == "SC2609.INE")
        assert contract["last_trade_date"] == expected
        assert packet in contract["raw_hashes"]
    assert {
        identity: repository.read_content(identity, "raw") for identity in first.acquisition_ids
    } == originals


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_ignore_unadopted_later_price_original_and_recover_when_restored(
    tmp_path: Path,
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    packet = save_futures_evidence_review(paths, synthetic_futures_publications(paths))
    TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=packet,
    )

    def read(cutoff: datetime) -> dict[str, Any]:
        return select_futures_inputs(
            paths,
            products=("SC",),
            business_date=date(2026, 8, 28),
            mode=AsOfMode.PUBLIC,
            as_of=cutoff,
        )

    night_cutoff = datetime(2026, 8, 27, 12, 59, 59, 999999, tzinfo=UTC)
    price_cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    before = read(night_cutoff)
    complete = read(price_cutoff)
    assert len(before["contracts"]) == 2 and before["calendar"]
    assert complete["missing"] == []
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    receipt = next(r for r in repository.history() if r.parameters.get("ts_code") == "SC2610.INE")
    original = repository.read_content(receipt.acquisition_id, "raw")
    assert receipt.raw_hash is not None
    artifact = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
    artifact.write_bytes(b"damaged synthetic settlement original")
    try:
        assert read(night_cutoff) == before
        damaged = read(price_cutoff)
        assert {r["contract_code"]: r["settle"] for r in damaged["settlements"]} == {
            "SC2609.INE": "584.2"
        }
        assert "futures_settlement_missing:SC2610.INE" in damaged["missing"]
        assert any(m.startswith("futures_input_delivery_invalid:") for m in damaged["missing"])
    finally:
        artifact.write_bytes(original)
    assert read(price_cutoff) == complete


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quote_unit", None),
        ("quote_unit", ""),
        ("quote_unit", "美元/桶"),
        ("trade_unit", None),
        ("per_unit", None),
        ("per_unit", 0),
        ("per_unit", -1),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_missing_or_incompatible_contract_units(
    tmp_path: Path, field: str, value: object
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def invalid_units(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            column = document["data"]["fields"].index(field)
            document["data"]["items"][0][column] = value
            return json.dumps(document).encode()
        return raw

    with pytest.raises(ValueError, match="futures_input_contract_unit_invalid"):
        TushareContextAdapter("synthetic-token", transport=invalid_units).acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    bad = next(r for r in repository.history() if r.api_name == "fut_basic")
    assert all(r.state == "failed" for r in repository.history())
    raw = json.loads(repository.read_content(bad.acquisition_id, "raw"))
    assert raw["data"]["items"][0][raw["data"]["fields"].index(field)] == value


def four_exchange_transport(payload: dict[str, Any]) -> bytes:
    """Synthetic exchange schedules; month codes use the recorded channel conventions."""
    identities = {
        "CU": (
            "CU2609.SHF",
            "CU2609",
            "SHFE",
            "202609",
            "20200101",
            "20260915",
            "人民币元/吨",
            5,
            "吨",
        ),
        "PP": (
            "PP2609.DCE",
            "PP2609",
            "DCE",
            "202609",
            "20200101",
            "20260915",
            "人民币元/吨",
            5,
            "吨",
        ),
        "CF": (
            "CF2609.ZCE",
            "CF609",
            "CZCE",
            "202609",
            "20200101",
            "20260915",
            "人民币元/吨",
            5,
            "吨",
        ),
        "SC": (
            "SC2609.INE",
            "SC2609",
            "INE",
            "202609",
            "20200101",
            "20260831",
            "人民币元/桶",
            1000,
            "桶",
        ),
        "RU": (
            "RU2609.SHF",
            "RU2609",
            "SHFE",
            "202609",
            "20200101",
            "20260915",
            "人民币元/吨",
            10,
            "吨",
        ),
    }
    if payload["api_name"] == "fut_basic":
        product = payload["params"]["fut_code"]
        fields = (
            "ts_code",
            "symbol",
            "exchange",
            "d_month",
            "list_date",
            "delist_date",
            "quote_unit",
            "per_unit",
            "trade_unit",
        )
        rows = [{**dict(zip(fields, identities[product], strict=True)), "fut_code": product}]
        if product == "CU":
            rows.append(
                {
                    **rows[0],
                    "ts_code": "CU2610.SHF",
                    "symbol": "CU2610",
                    "d_month": "202610",
                    "list_date": "20260829",
                    "delist_date": "20261015",
                }
            )
        return encoded_rows(rows)
    if payload["api_name"] == "fut_trade_cal":
        start = date.fromisoformat(payload["params"]["start_date"])
        end = date.fromisoformat(payload["params"]["end_date"])
        exchange = payload["params"]["exchange"]
        return encoded_rows(
            [
                {
                    "exchange": exchange,
                    "cal_date": day.strftime("%Y%m%d"),
                    "is_open": int(
                        day.weekday() < 5 and not (exchange == "DCE" and day == date(2026, 8, 31))
                    ),
                }
                for offset in range((end - start).days + 1)
                for day in (start + timedelta(days=offset),)
            ]
        )
    assert payload["api_name"] == "fut_daily"
    code = payload["params"]["ts_code"]
    assert code in {"CU2609.SHF", "PP2609.DCE", "CF2609.ZCE", "SC2609.INE", "RU2609.SHF"}
    return encoded_rows(
        [{"ts_code": code, "trade_date": "20260828", "pre_settle": "100", "settle": "102"}]
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_keep_each_exchange_calendar_and_exclude_not_yet_listed_contracts(
    tmp_path: Path,
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    products = ("CU", "PP", "CF", "SC")
    TushareContextAdapter(
        "synthetic-token", transport=four_exchange_transport
    ).acquire_futures_inputs(
        paths, products=products, start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    result = select_futures_inputs(
        paths,
        products=products,
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert result["missing"] == [
        "futures_session_missing:CU",
        "futures_session_missing:PP",
        "futures_session_missing:CF",
        "futures_session_missing:SC",
    ]
    contracts = {r["contract_code"]: r for r in result["contracts"]}
    assert set(contracts) == {"CU2609.SHF", "PP2609.DCE", "CF2609.ZCE", "SC2609.INE"}
    assert contracts["CF2609.ZCE"]["source_symbol"] == "CF609"
    assert contracts["CF2609.ZCE"]["delivery_month"] == "2026-09"
    assert {
        r["exchange"]: r["is_open"]
        for r in result["calendar"]
        if r["business_date"] == "2026-08-31"
    } == {"SHFE": True, "DCE": False, "CZCE": True, "INE": True}
    assert {r["contract_code"]: r["settle"] for r in result["settlements"]} == {
        "CU2609.SHF": "102",
        "PP2609.DCE": "102",
        "CF2609.ZCE": "102",
        "SC2609.INE": "102",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exchange", "SHFE"),
        ("cal_date", "20260827"),
        ("cal_date", "20261001"),
        ("is_open", 2),
        ("is_open", "0"),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_calendar_with_wrong_scope_or_invalid_open_state(
    tmp_path: Path, field: str, value: object
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def invalid_calendar(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_trade_cal":
            document = json.loads(raw)
            column = document["data"]["fields"].index(field)
            document["data"]["items"][0][column] = value
            return json.dumps(document).encode()
        return raw

    with pytest.raises(ValueError, match="futures_input_calendar_invalid"):
        TushareContextAdapter("synthetic-token", transport=invalid_calendar).acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    original = next(r for r in repository.history() if r.api_name == "fut_trade_cal")
    assert original.state == "failed"
    assert all(r.state == "failed" for r in repository.history())
    raw = json.loads(repository.read_content(original.acquisition_id, "raw"))
    assert raw["data"]["items"][0][raw["data"]["fields"].index(field)] == value


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_query_reviewed_night_session_by_product_and_business_date(
    tmp_path: Path,
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    document = synthetic_futures_publications(paths)
    schedule = {
        "product": "SC",
        "exchange": "INE",
        "business_date": "2026-08-28",
        "session_start_at": "2026-08-27T21:00:00+08:00",
        "release_at": "2026-08-26T08:00:00+00:00",
        "public_available_at": "2026-08-26T08:00:00+00:00",
    }
    proof = save_futures_document(paths, {"synthetic": True, "session_notice": schedule})
    document["evidence"].append(
        {"artifact_hash": proof, "source_reference": "synthetic:SC-night-session"}
    )
    document["sessions"] = [{**schedule, "evidence": [proof]}]
    packet = save_futures_evidence_review(paths, document)
    acquired = TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=packet,
    )
    before = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 26, 7, 59, 59, 999999, tzinfo=UTC),
    )
    assert before["sessions"] == []
    known = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 27, 12, 59, 59, 999999, tzinfo=UTC),
    )
    assert len(known["sessions"]) == 1
    session = known["sessions"][0]
    assert {field: session[field] for field in schedule} == schedule
    assert session["available_at"].startswith("2026-09-08")
    assert packet in session["raw_hashes"] and proof in session["evidence_hashes"]
    assert set(session["acquisition_ids"]) <= set(acquired.acquisition_ids)
    previous_day = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 27),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert previous_day["sessions"] == []


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_report_missing_session_without_inventing_a_night_start(
    tmp_path: Path,
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    result = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert result["missing"] == ["futures_session_missing:SC"]
    assert result["sessions"] == []
    assert {r["contract_code"]: r["settle"] for r in result["settlements"]} == {
        "SC2609.INE": "584.2",
        "SC2610.INE": "592.3",
    }


@pytest.mark.parametrize("api", ["fut_basic", "fut_trade_cal", "fut_daily"])
@pytest.mark.parametrize("conflicting", [False, True])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_duplicate_identities_within_one_delivery(
    tmp_path: Path, api: str, conflicting: bool
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def duplicate_input(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == api and (
            api != "fut_daily" or payload["params"]["ts_code"] == "SC2609.INE"
        ):
            document = json.loads(raw)
            duplicate = list(document["data"]["items"][0])
            if conflicting:
                field, value = {
                    "fut_basic": ("delist_date", "20260901"),
                    "fut_trade_cal": ("is_open", 0),
                    "fut_daily": ("settle", "600"),
                }[api]
                duplicate[document["data"]["fields"].index(field)] = value
            document["data"]["items"].append(duplicate)
            return json.dumps(document).encode()
        return raw

    with pytest.raises(ValueError, match="futures_input_identity_duplicate"):
        TushareContextAdapter("synthetic-token", transport=duplicate_input).acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    assert all(r.state == "failed" for r in repository.history())
    bad = next(r for r in repository.history() if r.api_name == api)
    assert repository.read_content(bad.acquisition_id, "raw")


@pytest.mark.parametrize("outside_scope", ["other_product", "other_business_day"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_ignore_damaged_prices_outside_requested_product_or_day(
    tmp_path: Path, outside_scope: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def transport(payload: dict[str, Any]) -> bytes:
        if outside_scope == "other_product":
            return four_exchange_transport(payload)
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily":
            document = json.loads(raw)
            column = document["data"]["fields"].index("trade_date")
            document["data"]["items"][0][column] = payload["params"]["start_date"]
            return json.dumps(document).encode()
        return raw

    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    products = ("CU", "PP", "CF", "SC") if outside_scope == "other_product" else ("SC",)
    if outside_scope == "other_business_day":
        adapter.acquire_futures_inputs(
            paths, products=products, start_date=date(2026, 8, 27), end_date=date(2026, 8, 27)
        )
    adapter.acquire_futures_inputs(
        paths, products=products, start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )

    def read() -> dict[str, Any]:
        return select_futures_inputs(
            paths,
            products=("SC",),
            business_date=date(2026, 8, 28),
            mode=AsOfMode.SYSTEM,
            as_of=datetime(2026, 9, 9, tzinfo=UTC),
        )

    before = read()
    assert before["settlements"] and before["missing"] == ["futures_session_missing:SC"]
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    bad = next(
        r
        for r in repository.history()
        if r.api_name == "fut_daily"
        and (
            r.parameters["ts_code"] == "CU2609.SHF"
            if outside_scope == "other_product"
            else r.parameters["ts_code"] == "SC2609.INE"
            and r.parameters["start_date"] == "20260827"
        )
    )
    original = repository.read_content(bad.acquisition_id, "raw")
    assert bad.raw_hash is not None
    artifact = paths.artifacts / bad.raw_hash[:2] / bad.raw_hash
    artifact.write_bytes(b"damaged synthetic price outside requested scope")
    try:
        assert read() == before
    finally:
        artifact.write_bytes(original)


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_review_dated_after_evidence_was_received(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    packet = save_futures_evidence_review(
        paths, synthetic_futures_publications(paths), reviewed_at="2026-09-10T00:00:00+00:00"
    )
    with pytest.raises(ValueError, match="futures_input_evidence_review_in_future"):
        TushareContextAdapter(
            "synthetic-token", transport=futures_input_transport
        ).acquire_futures_inputs(
            paths,
            products=("SC",),
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            evidence_hash=packet,
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = next(r for r in repository.history() if r.api_name == "futures_input_evidence")
    assert evidence.received_at is not None and evidence.received_at < datetime(
        2026, 9, 9, tzinfo=UTC
    )
    assert all(r.state == "failed" for r in repository.history())
    assert json.loads(repository.read_content(evidence.acquisition_id, "raw"))["review_hash"]


@pytest.mark.parametrize("conflicting", [False, True])
@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_report_same_public_time_conflict_independently_of_capture_order(
    tmp_path: Path, conflicting: bool, reverse_order: bool
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    prices = ["584.2", "600" if conflicting else "584.2"]
    if reverse_order:
        prices.reverse()
    for price in prices:

        def revised_price(payload: dict[str, Any], settle: str = price) -> bytes:
            raw = futures_input_transport(payload)
            if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
                document = json.loads(raw)
                column = document["data"]["fields"].index("settle")
                document["data"]["items"][0][column] = settle
                return json.dumps(document).encode()
            return raw

        document = synthetic_futures_publications(paths)
        publication = next(
            p for p in document["publications"] if p["parameters"].get("ts_code") == "SC2609.INE"
        )
        publication["raw_hash"] = hashlib.sha256(
            revised_price({"api_name": "fut_daily", "params": publication["parameters"]})
        ).hexdigest()
        proof = save_futures_document(
            paths, {"synthetic": True, "settlement_notice": dict(publication), "settle": price}
        )
        publication["evidence"] = [proof]
        document["evidence"].append(
            {"artifact_hash": proof, "source_reference": "synthetic:settlement-notice:" + price}
        )
        packet = save_futures_evidence_review(paths, document)
        TushareContextAdapter("synthetic-token", transport=revised_price).acquire_futures_inputs(
            paths,
            products=("SC",),
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            evidence_hash=packet,
        )
    public = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    values = {r["contract_code"]: r["settle"] for r in public["settlements"]}
    if conflicting:
        assert "futures_input_conflict:settlement:SC2609.INE:2026-08-28" in public["missing"]
        assert values == {"SC2610.INE": "592.3"}
    else:
        assert public["missing"] == []
        assert values == {"SC2609.INE": "584.2", "SC2610.INE": "592.3"}
    system = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert system["missing"] == []
    assert {r["contract_code"]: r["settle"] for r in system["settlements"]} == {
        "SC2609.INE": prices[-1],
        "SC2610.INE": "592.3",
    }


@pytest.mark.parametrize("calendar_gap", ["missing", "unknown"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_report_calendar_gaps_between_target_day_and_expiry(
    tmp_path: Path, calendar_gap: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def incomplete_calendar(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_trade_cal":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            index = next(
                i
                for i, r in enumerate(document["data"]["items"])
                if r[fields.index("cal_date")] == "20260831"
            )
            if calendar_gap == "missing":
                del document["data"]["items"][index]
            else:
                document["data"]["items"][index][fields.index("is_open")] = None
            return json.dumps(document).encode()
        if payload["api_name"] == "fut_daily":
            # Explicit synthetic Aug 14 prices; this case tests the independently known calendar.
            return encoded_rows(
                [
                    {
                        "ts_code": payload["params"]["ts_code"],
                        "trade_date": "20260814",
                        "pre_settle": "100",
                        "settle": "102",
                    }
                ]
            )
        return raw

    TushareContextAdapter("synthetic-token", transport=incomplete_calendar).acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 14), end_date=date(2026, 8, 14)
    )
    result = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 14),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert f"futures_calendar_{calendar_gap}:INE:2026-08-31" in result["missing"]
    assert {
        r["business_date"]
        for r in result["calendar"]
        if "2026-08-14" < r["business_date"] <= "2026-08-31" and r["is_open"] is True
    } == {
        "2026-08-17",
        "2026-08-18",
        "2026-08-19",
        "2026-08-20",
        "2026-08-21",
        "2026-08-24",
        "2026-08-25",
        "2026-08-26",
        "2026-08-27",
        "2026-08-28",
    }
    assert any(
        r["contract_code"] == "SC2609.INE" and r["last_trade_date"] == "2026-08-31"
        for r in result["contracts"]
    )


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("rejected", "futures_input_evidence_review_invalid"),
        ("stale_review", "futures_input_evidence_review_invalid"),
        ("missing_reference", "futures_input_publication_evidence_missing"),
        ("date_only_early", "futures_input_publication_invalid"),
        ("session_after_business_date", "futures_input_session_invalid"),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_unaccepted_or_inconsistent_evidence_packets(
    tmp_path: Path, failure: str, reason: str
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    document = synthetic_futures_publications(paths)
    if failure == "missing_reference":
        document["publications"][0]["evidence"] = []
    elif failure == "date_only_early":
        document["publications"][2].update(
            published_date="2026-08-28",
            release_at=None,
            public_available_at="2026-08-28T00:00:00+08:00",
        )
    elif failure == "session_after_business_date":
        document["sessions"][0]["session_start_at"] = "2026-08-29T09:00:00+08:00"
    packet = save_futures_evidence_review(
        paths, document, decision="rejected" if failure == "rejected" else "accepted"
    )
    if failure == "stale_review":
        packet_document = json.loads((paths.artifacts / packet[:2] / packet).read_bytes())
        packet_document["publications"][0]["public_available_at"] = "2026-01-02T08:00:00+00:00"
        packet = save_futures_document(paths, packet_document)
    with pytest.raises(ValueError, match=reason):
        TushareContextAdapter(
            "synthetic-token", transport=futures_input_transport
        ).acquire_futures_inputs(
            paths,
            products=("SC",),
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            evidence_hash=packet,
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    evidence = next(r for r in repository.history() if r.api_name == "futures_input_evidence")
    assert all(r.state == "failed" for r in repository.history())
    assert evidence.raw_hash == packet
    assert repository.read_content(evidence.acquisition_id, "raw")


@pytest.mark.parametrize("material", ["price_proof", "review", "packet"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_withhold_damaged_adopted_evidence_and_restore_exact_results(
    tmp_path: Path, material: str, damage: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    document = synthetic_futures_publications(paths)
    packet = save_futures_evidence_review(paths, document)
    packet_document = json.loads((paths.artifacts / packet[:2] / packet).read_bytes())
    TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=packet,
    )

    def read(mode: AsOfMode, cutoff: datetime) -> dict[str, Any]:
        return select_futures_inputs(
            paths, products=("SC",), business_date=date(2026, 8, 28), mode=mode, as_of=cutoff
        )

    public_cutoff = datetime(2026, 8, 28, 8, tzinfo=UTC)
    system_cutoff = datetime(2026, 9, 9, tzinfo=UTC)
    night_cutoff = datetime(2026, 8, 27, 12, 59, 59, 999999, tzinfo=UTC)
    complete_public = read(AsOfMode.PUBLIC, public_cutoff)
    complete_system = read(AsOfMode.SYSTEM, system_cutoff)
    before_price = read(AsOfMode.PUBLIC, night_cutoff)
    assert complete_public["missing"] == [] and complete_system["missing"] == []
    digest = {
        "price_proof": document["publications"][3]["evidence"][0],
        "review": packet_document["review_hash"],
        "packet": packet,
    }[material]
    artifact = paths.artifacts / digest[:2] / digest
    original = artifact.read_bytes()
    if damage == "changed":
        artifact.write_bytes(b"damaged synthetic publication evidence")
    else:
        artifact.unlink()
    try:
        if material == "price_proof":
            assert read(AsOfMode.PUBLIC, night_cutoff) == before_price
        for mode, cutoff in ((AsOfMode.PUBLIC, public_cutoff), (AsOfMode.SYSTEM, system_cutoff)):
            unavailable = read(mode, cutoff)
            assert any(
                m.startswith("futures_input_delivery_invalid:") for m in unavailable["missing"]
            )
            assert {r["contract_code"]: r["settle"] for r in unavailable["settlements"]} == (
                {"SC2609.INE": "584.2"} if material == "price_proof" else {}
            )
    finally:
        artifact.write_bytes(original)
    assert read(AsOfMode.PUBLIC, public_cutoff) == complete_public
    assert read(AsOfMode.SYSTEM, system_cutoff) == complete_system


@pytest.mark.parametrize("binding", ["api_name", "parameters", "raw_hash"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_do_not_apply_publication_to_a_different_delivery(
    tmp_path: Path, binding: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    document = synthetic_futures_publications(paths)
    publication = document["publications"][2]
    publication[binding] = {
        "api_name": "fut_trade_cal",
        "parameters": {"ts_code": "SC2611.INE", "start_date": "20260828", "end_date": "20260828"},
        "raw_hash": "0" * 64,
    }[binding]
    packet = save_futures_evidence_review(paths, document)
    TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=packet,
    )
    public = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert public["missing"] == ["futures_settlement_missing:SC2609.INE"]
    assert {r["contract_code"]: r["settle"] for r in public["settlements"]} == {
        "SC2610.INE": "592.3"
    }
    system = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert system["missing"] == []
    affected = next(r for r in system["settlements"] if r["contract_code"] == "SC2609.INE")
    assert affected["settle"] == "584.2"
    assert affected["release_at"] is None and affected["public_available_at"] is None


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_close_when_settlement_column_is_absent(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def close_only(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("settle")
            document["data"]["fields"].pop(column)
            for row in document["data"]["items"]:
                row.pop(column)
            return json.dumps(document).encode()
        return raw

    with pytest.raises(ValueError, match="tushare_response_required_field_missing"):
        TushareContextAdapter("synthetic-token", transport=close_only).acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    assert all(r.state == "failed" for r in repository.history())
    failed = next(r for r in repository.history() if r.parameters.get("ts_code") == "SC2609.INE")
    document = json.loads(repository.read_content(failed.acquisition_id, "raw"))
    assert "settle" not in document["data"]["fields"]
    assert document["data"]["items"][0][document["data"]["fields"].index("close")] == "581"


@pytest.mark.parametrize("scenario", ["later_revision", "equivalent_representations"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_distinguish_later_revisions_from_equivalent_public_versions(
    tmp_path: Path, scenario: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    prices = ["584.2", "600", "601"] if scenario == "later_revision" else ["584.2", "584.200"]
    packets = []
    for index, price in enumerate(prices):
        alternate = scenario == "equivalent_representations" and index == 1

        def revised(payload: dict[str, Any], value: str = price, alt: bool = alternate) -> bytes:
            raw = futures_input_transport(payload)
            document = json.loads(raw)
            fields = document["data"]["fields"]
            if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
                document["data"]["items"][0][fields.index("settle")] = value
            elif alt and payload["api_name"] == "fut_basic":
                for row in document["data"]["items"]:
                    row[fields.index("per_unit")] = "1E+3"
            else:
                return raw
            return json.dumps(document).encode()

        document = synthetic_futures_publications(paths)
        for publication in document["publications"]:
            raw = revised(
                {"api_name": publication["api_name"], "params": publication["parameters"]}
            )
            publication["raw_hash"] = hashlib.sha256(raw).hexdigest()
            if index == 2 and publication["parameters"].get("ts_code") == "SC2609.INE":
                publication.update(
                    release_at="2026-08-28T09:00:00+00:00",
                    public_available_at="2026-08-28T09:00:00+00:00",
                )
            proof = save_futures_document(
                paths,
                {"synthetic": True, "publication": dict(publication), "response": json.loads(raw)},
            )
            publication["evidence"] = [proof]
            document["evidence"].append(
                {"artifact_hash": proof, "source_reference": "synthetic:revised-futures-notice"}
            )
        if alternate:
            document["sessions"][0]["session_start_at"] = "2026-08-27T13:00:00+00:00"
        packet = save_futures_evidence_review(paths, document)
        packets.append(packet)
        TushareContextAdapter("synthetic-token", transport=revised).acquire_futures_inputs(
            paths,
            products=("SC",),
            start_date=date(2026, 8, 28),
            end_date=date(2026, 8, 28),
            evidence_hash=packet,
        )
    before = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, 59, 59, 999999, tzinfo=UTC),
    )
    if scenario == "later_revision":
        assert "futures_input_conflict:settlement:SC2609.INE:2026-08-28" in before["missing"]
        assert {r["contract_code"] for r in before["settlements"]} == {"SC2610.INE"}
    else:
        assert before["missing"] == []
        assert len(before["contracts"]) == 2 and len(before["sessions"]) == 1
    after = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 9, tzinfo=UTC),
    )
    assert after["missing"] == []
    assert {r["contract_code"]: r["settle"] for r in after["settlements"]} == {
        "SC2609.INE": "601" if scenario == "later_revision" else "584.200",
        "SC2610.INE": "592.3",
    }
    selected = next(r for r in after["settlements"] if r["contract_code"] == "SC2609.INE")
    assert packets[-1] in selected["raw_hashes"]


@pytest.mark.parametrize("precision", ["exact", "date_only"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_preserve_product_specific_sessions_across_reviewed_revisions(
    tmp_path: Path, precision: str
) -> None:
    from pring_cycle.futures_inputs import select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    products = ("CU", "PP", "CF", "SC", "RU")
    adapter = TushareContextAdapter("synthetic-token", transport=four_exchange_transport)
    first_raw = adapter.acquire_futures_inputs(
        paths, products=products, start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    document: dict[str, Any] = {
        "schema_version": "futures-input-evidence-v0001",
        "publications": [],
        "sessions": [],
        "evidence": [],
    }
    for identity in first_raw.acquisition_ids:
        receipt = repository.get(identity)
        published = (
            "2026-08-28T08:00:00+00:00"
            if receipt.api_name == "fut_daily"
            else "2026-01-01T08:00:00+00:00"
        )
        publication = {
            "api_name": receipt.api_name,
            "parameters": receipt.parameters,
            "raw_hash": receipt.raw_hash,
            "release_at": published,
            "public_available_at": published,
        }
        proof = save_futures_document(paths, {"synthetic": True, "publication": publication})
        document["publications"].append({**publication, "evidence": [proof]})
        document["evidence"].append(
            {"artifact_hash": proof, "source_reference": "synthetic:five-product-inputs"}
        )
    # Deliberately distinct synthetic schedules, including two SHFE products.
    starts = {
        "CU": ("SHFE", "2026-08-27T21:00:00+08:00"),
        "PP": ("DCE", "2026-08-28T09:00:00+08:00"),
        "CF": ("CZCE", "2026-08-27T21:00:00+08:00"),
        "SC": ("INE", "2026-08-27T21:00:00+08:00"),
        "RU": ("SHFE", "2026-08-28T09:00:00+08:00"),
    }
    for product, (exchange, start) in starts.items():
        session = {
            "product": product,
            "exchange": exchange,
            "business_date": "2026-08-28",
            "session_start_at": start,
            "release_at": "2026-01-01T08:00:00+00:00",
            "public_available_at": "2026-01-01T08:00:00+00:00",
        }
        proof = save_futures_document(paths, {"synthetic": True, "session_notice": session})
        document["sessions"].append({**session, "evidence": [proof]})
        document["evidence"].append(
            {"artifact_hash": proof, "source_reference": "synthetic:product-session-notice"}
        )
    first_packet = save_futures_evidence_review(paths, document)
    first = adapter.acquire_futures_inputs(
        paths,
        products=products,
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=first_packet,
    )
    first_system_cutoff = repository.get(first.acquisition_ids[-1]).validated_at
    assert first_system_cutoff is not None
    revised = next(s for s in document["sessions"] if s["product"] == "RU")
    revised["session_start_at"] = "2026-08-27T21:00:00+08:00"
    if precision == "exact":
        revised.update(
            release_at="2026-08-27T13:00:00+00:00",
            public_available_at="2026-08-27T13:00:00+00:00",
        )
        revision_cutoff = datetime(2026, 8, 27, 13, tzinfo=UTC)
    else:
        revised.update(
            published_date="2026-08-27",
            release_at=None,
            public_available_at="2026-08-28T00:00:00+08:00",
        )
        revision_cutoff = datetime(2026, 8, 27, 16, tzinfo=UTC)
    proof = save_futures_document(paths, {"synthetic": True, "session_revision": dict(revised)})
    revised["evidence"] = [proof]
    document["evidence"].append(
        {"artifact_hash": proof, "source_reference": "synthetic:RU-session-revision"}
    )
    second_packet = save_futures_evidence_review(paths, document)
    adapter.acquire_futures_inputs(
        paths,
        products=products,
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=second_packet,
    )
    for mode, cutoff, ru_start, packet in (
        (
            AsOfMode.PUBLIC,
            revision_cutoff - timedelta(microseconds=1),
            "2026-08-28T09:00:00+08:00",
            first_packet,
        ),
        (AsOfMode.PUBLIC, revision_cutoff, "2026-08-27T21:00:00+08:00", second_packet),
        (AsOfMode.SYSTEM, first_system_cutoff, "2026-08-28T09:00:00+08:00", first_packet),
    ):
        result = select_futures_inputs(
            paths, products=products, business_date=date(2026, 8, 28), mode=mode, as_of=cutoff
        )
        sessions = {r["product"]: r for r in result["sessions"]}
        assert {p: r["session_start_at"] for p, r in sessions.items()} == {
            "CU": "2026-08-27T21:00:00+08:00",
            "PP": "2026-08-28T09:00:00+08:00",
            "CF": "2026-08-27T21:00:00+08:00",
            "SC": "2026-08-27T21:00:00+08:00",
            "RU": ru_start,
        }
        assert packet in sessions["RU"]["raw_hashes"]
    complete = select_futures_inputs(
        paths,
        products=products,
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert complete["missing"] == []
    assert {r["product"]: r["settle"] for r in complete["settlements"]} == {
        "CU": "102",
        "PP": "102",
        "CF": "102",
        "SC": "102",
        "RU": "102",
    }


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_attach_post_capture_review_without_requesting_new_responses(
    tmp_path: Path,
) -> None:
    from pring_cycle import futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    requests = []

    def per_request_response(payload: dict[str, Any]) -> bytes:
        requests.append(payload["api_name"])
        document = json.loads(futures_input_transport(payload))
        document["request_id"] = f"synthetic-request-{len(requests)}"
        return json.dumps(document).encode()

    adapter = TushareContextAdapter("synthetic-token", transport=per_request_response)
    first = adapter.acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    first_cutoff = repository.get(first.acquisition_ids[-1]).validated_at
    assert first_cutoff is not None
    before_system = futures_inputs.select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.SYSTEM,
        as_of=first_cutoff,
    )
    document = synthetic_futures_publications(paths)
    for publication in document["publications"]:
        receipt = next(
            repository.get(identity)
            for identity in first.acquisition_ids
            if repository.get(identity).api_name == publication["api_name"]
            and repository.get(identity).parameters == publication["parameters"]
        )
        publication["raw_hash"] = receipt.raw_hash
        proof = save_futures_document(
            paths, {"synthetic": True, "publication_after_capture": dict(publication)}
        )
        publication["evidence"] = [proof]
        document["evidence"].append(
            {"artifact_hash": proof, "source_reference": "synthetic:captured-publication-review"}
        )
    packet = save_futures_evidence_review(paths, document, reviewed_at=first_cutoff.isoformat())
    recollected = adapter.acquire_futures_inputs(
        paths,
        products=("SC",),
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        evidence_hash=packet,
    )
    # New request IDs change raw bytes. Refusing to transfer the old proof is correct.
    first_raw = repository.read_content(first.acquisition_ids[0], "raw")
    second_contract = next(
        repository.get(identity)
        for identity in recollected.acquisition_ids
        if repository.get(identity).api_name == "fut_basic"
    )
    assert (
        json.loads(first_raw)["request_id"]
        != json.loads(repository.read_content(second_contract.acquisition_id, "raw"))["request_id"]
    )
    before_public = futures_inputs.select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert before_public["contracts"] == [] and before_public["settlements"] == []
    old_receipts = repository.history()
    old_materials = {
        (r.acquisition_id, kind): repository.read_content(r.acquisition_id, kind)
        for r in old_receipts
        for kind in ("raw", "normalized")
    }
    requests_before_binding = list(requests)
    bound = futures_inputs.bind_futures_input_evidence(
        paths, acquisition_ids=first.acquisition_ids, evidence_hash=packet
    )
    assert requests == requests_before_binding
    after_public = futures_inputs.select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert after_public["missing"] == []
    assert {r["contract_code"]: r["settle"] for r in after_public["settlements"]} == {
        "SC2609.INE": "584.2",
        "SC2610.INE": "592.3",
    }
    assert all(
        set(f["acquisition_ids"]) <= set(bound.acquisition_ids)
        and set(f["acquisition_ids"]) & set(first.acquisition_ids)
        for f in after_public["contracts"] + after_public["settlements"] + after_public["calendar"]
    )
    assert (
        futures_inputs.select_futures_inputs(
            paths,
            products=("SC",),
            business_date=date(2026, 8, 28),
            mode=AsOfMode.SYSTEM,
            as_of=first_cutoff,
        )
        == before_system
    )
    assert all(repository.get(r.acquisition_id) == r for r in old_receipts)
    assert {key: repository.read_content(*key) for key in old_materials} == old_materials


@pytest.mark.parametrize("failure", ["failed_acquisition", "damaged_original"])
@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_reject_post_capture_review_of_unusable_originals(
    tmp_path: Path, failure: str
) -> None:
    from pring_cycle.futures_inputs import bind_futures_input_evidence, select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def failed_delivery(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2610.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("settle")
            document["data"]["items"][0][column] = "invalid"
            return json.dumps(document).encode()
        return raw

    if failure == "failed_acquisition":
        with pytest.raises(ValueError, match="futures_input_settlement_invalid"):
            TushareContextAdapter(
                "synthetic-token", transport=failed_delivery
            ).acquire_futures_inputs(
                paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
            )
    else:
        TushareContextAdapter(
            "synthetic-token", transport=futures_input_transport
        ).acquire_futures_inputs(
            paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
        )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    old = repository.history()
    packet = save_futures_evidence_review(paths, synthetic_futures_publications(paths))
    receipt = next(r for r in old if r.api_name == "fut_basic")
    assert receipt.raw_hash is not None
    artifact = paths.artifacts / receipt.raw_hash[:2] / receipt.raw_hash
    raw = artifact.read_bytes()
    if failure == "damaged_original":
        artifact.write_bytes(b"damaged original before post-capture review")
    try:
        with pytest.raises(
            ValueError,
            match="futures_input_acquisition_scope_invalid"
            if failure == "failed_acquisition"
            else "artifact_hash_mismatch",
        ):
            bind_futures_input_evidence(
                paths, acquisition_ids=tuple(r.acquisition_id for r in old), evidence_hash=packet
            )
    finally:
        artifact.write_bytes(raw)
    assert all(repository.get(r.acquisition_id) == r for r in old)
    rejected = next(r for r in repository.history() if r.api_name == "futures_input_evidence")
    assert rejected.state == "failed" and rejected.raw_hash == packet
    assert repository.read_content(rejected.acquisition_id, "raw")
    public = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 28),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 28, 8, tzinfo=UTC),
    )
    assert public["contracts"] == [] and public["settlements"] == []


@pytest.mark.usefixtures("acquisition_clock")
def test_futures_inputs_do_not_promote_old_prices_when_their_public_times_are_reviewed_later(
    tmp_path: Path,
) -> None:
    from pring_cycle.futures_inputs import bind_futures_input_evidence, select_futures_inputs

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    first = TushareContextAdapter(
        "synthetic-token", transport=futures_input_transport
    ).acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )

    def new_price(payload: dict[str, Any]) -> bytes:
        raw = futures_input_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2609.INE":
            document = json.loads(raw)
            column = document["data"]["fields"].index("settle")
            document["data"]["items"][0][column] = "600"
            return json.dumps(document).encode()
        return raw

    second = TushareContextAdapter("synthetic-token", transport=new_price).acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 28), end_date=date(2026, 8, 28)
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    second_cutoff = repository.get(second.acquisition_ids[-1]).validated_at
    assert second_cutoff is not None

    def read(mode: AsOfMode, cutoff: datetime) -> dict[str, Any]:
        return select_futures_inputs(
            paths, products=("SC",), business_date=date(2026, 8, 28), mode=mode, as_of=cutoff
        )

    before = read(AsOfMode.SYSTEM, second_cutoff)
    assert {r["contract_code"]: r["settle"] for r in before["settlements"]} == {
        "SC2609.INE": "600",
        "SC2610.INE": "592.3",
    }
    packet = save_futures_evidence_review(
        paths, synthetic_futures_publications(paths), reviewed_at=second_cutoff.isoformat()
    )
    bind_futures_input_evidence(paths, acquisition_ids=first.acquisition_ids, evidence_hash=packet)
    current = read(AsOfMode.SYSTEM, datetime(2026, 9, 9, tzinfo=UTC))
    assert {r["contract_code"]: r["settle"] for r in current["settlements"]} == {
        "SC2609.INE": "600",
        "SC2610.INE": "592.3",
    }
    assert read(AsOfMode.SYSTEM, second_cutoff) == before
    public = read(AsOfMode.PUBLIC, datetime(2026, 8, 28, 8, tzinfo=UTC))
    assert public["missing"] == []
    assert {r["contract_code"]: r["settle"] for r in public["settlements"]} == {
        "SC2609.INE": "584.2",
        "SC2610.INE": "592.3",
    }
    latest = next(r for r in current["settlements"] if r["contract_code"] == "SC2609.INE")
    assert set(latest["acquisition_ids"]) <= set(second.acquisition_ids)
