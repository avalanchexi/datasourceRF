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


def save_futures_evidence_review(paths: RuntimePaths, document: dict[str, Any]) -> str:
    subject = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    review = save_futures_document(
        paths,
        {
            "schema_version": "futures-input-evidence-review-v0001",
            "subject_hash": hashlib.sha256(subject).hexdigest(),
            "reviewer": "synthetic input publication reviewer",
            "reviewed_at": "2026-09-07T00:00:00+00:00",
            "decision": "accepted",
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
    assert code in {"CU2609.SHF", "PP2609.DCE", "CF2609.ZCE", "SC2609.INE"}
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
