from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.artifacts import store_artifact
from pring_cycle.evidence import AsOfMode
from pring_cycle.futures_inputs import bind_futures_input_evidence, select_futures_inputs
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.tushare_context import TushareContextAdapter


def encode_document(document: object) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def encode_rows(rows: list[dict[str, Any]]) -> bytes:
    fields = list(rows[0])
    return encode_document(
        {"code": 0, "data": {"fields": fields, "items": [[row[f] for f in fields] for row in rows]}}
    )


def calendar_roll_transport(payload: dict[str, Any]) -> bytes:
    """Synthetic weekday calendar; the two price pairs match research sample 535."""
    if payload["api_name"] == "fut_basic":
        return encode_rows(
            [
                {
                    "ts_code": code,
                    "symbol": code.split(".")[0],
                    "exchange": "INE",
                    "fut_code": "SC",
                    "d_month": month,
                    "list_date": "20250101",
                    "delist_date": expiry,
                    "quote_unit": "人民币元/桶",
                    "per_unit": 1000,
                    "trade_unit": "桶",
                }
                for code, month, expiry in (
                    ("SC2609.INE", "202609", "20260831"),
                    ("SC2610.INE", "202610", "20260930"),
                )
            ]
        )
    params = payload["params"]
    if payload["api_name"] == "fut_trade_cal":
        start, end = (
            date.fromisoformat(params["start_date"]),
            date.fromisoformat(params["end_date"]),
        )
        return encode_rows(
            [
                {"exchange": "INE", "cal_date": day.isoformat(), "is_open": int(day.weekday() < 5)}
                for offset in range((end - start).days + 1)
                for day in (start + timedelta(days=offset),)
            ]
        )
    assert payload["api_name"] == "fut_daily"
    return encode_rows(
        [
            {
                "ts_code": params["ts_code"],
                "trade_date": day,
                "pre_settle": previous,
                "settle": settle,
                "close": "999",  # Deliberately different from the settlement.
            }
            for day, previous, settle in {
                "SC2609.INE": [("20260814", "554.2", "554.9"), ("20260817", "554.9", "600")],
                "SC2610.INE": [("20260814", "540", "550.5"), ("20260817", "550.5", "559.6")],
            }[params["ts_code"]]
        ]
    )


def save_synthetic_document(paths: RuntimePaths, document: object) -> str:
    return store_artifact(
        paths.database,
        paths.artifacts,
        encode_document(document),
        "application/json",
        "synthetic:commodity-rule-test",
    ).content_hash


def capture_reviewed_roll_inputs(
    paths: RuntimePaths,
    *,
    transport: Callable[[dict[str, Any]], bytes] = calendar_roll_transport,
    metadata_public_at: str = "2026-01-01T08:00:00+00:00",
    monday_session_start: str = "2026-08-14T21:00:00+08:00",
    monday_session_public_at: str = "2026-01-01T08:00:00+00:00",
) -> None:
    adapter = TushareContextAdapter("synthetic-token", transport=transport)
    acquired = adapter.acquire_futures_inputs(
        paths, products=("SC",), start_date=date(2026, 8, 14), end_date=date(2026, 8, 17)
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    proof = save_synthetic_document(paths, {"synthetic": True, "purpose": "frozen roll rule test"})
    publications = []
    for identity in acquired.acquisition_ids:
        receipt = repository.get(identity)
        for day in ["2026-08-14", "2026-08-17"] if receipt.api_name == "fut_daily" else [None]:
            published = "2026-01-01T08:00:00+00:00" if day is None else day + "T08:00:00+00:00"
            if receipt.api_name == "fut_basic":
                published = metadata_public_at
            publications.append(
                {
                    "api_name": receipt.api_name,
                    "parameters": receipt.parameters,
                    "raw_hash": receipt.raw_hash,
                    "business_date": day,
                    "release_at": published,
                    "public_available_at": published,
                    "evidence": [proof],
                }
            )
    packet = {
        "schema_version": "futures-input-evidence-v0001",
        "evidence": [
            {"artifact_hash": proof, "source_reference": "synthetic:roll-calendar-notice"}
        ],
        "publications": publications,
        "sessions": [
            {
                "product": "SC",
                "exchange": "INE",
                "business_date": day,
                "session_start_at": start,
                "release_at": (
                    monday_session_public_at if day == "2026-08-17" else "2026-01-01T08:00:00+00:00"
                ),
                "public_available_at": (
                    monday_session_public_at if day == "2026-08-17" else "2026-01-01T08:00:00+00:00"
                ),
                "evidence": [proof],
            }
            for day, start in (
                ("2026-08-14", "2026-08-13T21:00:00+08:00"),
                ("2026-08-17", monday_session_start),
            )
        ],
    }
    review = save_synthetic_document(
        paths,
        {
            "schema_version": "futures-input-evidence-review-v0001",
            "subject_hash": hashlib.sha256(encode_document(packet)).hexdigest(),
            "reviewer": "synthetic commodity-rule reviewer",
            "reviewed_at": "2026-09-07T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    packet_hash = save_synthetic_document(paths, {**packet, "review_hash": review})
    bind_futures_input_evidence(
        paths, acquisition_ids=acquired.acquisition_ids, evidence_hash=packet_hash
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_public_contract_choice_rolls_at_ten_exchange_days_before_expiry(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)
    available = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 14),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 14, 9, tzinfo=UTC),
    )
    assert available["missing"] == []
    assert len(available["contracts"]) == 2

    from pring_cycle.commodity_basket import select_commodity_contracts

    # Aug 17-21, 24-28, 31: eleven open dates after Aug 14 through Aug 31.
    # On Aug 17 only ten remain, so the September 30 expiry (32 days) is selected.
    for day, expected, remaining in (
        (date(2026, 8, 14), "SC2609.INE", 11),
        (date(2026, 8, 17), "SC2610.INE", 32),
    ):
        result = select_commodity_contracts(
            paths,
            products=("SC",),
            business_date=day,
            as_of=datetime(2026, 8, 18, tzinfo=UTC),
            mode=AsOfMode.PUBLIC,
        )
        assert result["missing"] == []
        assert len(result["selections"]) == 1
        selected = result["selections"][0]
        assert (selected["contract_code"], selected["remaining_open_days"]) == (expected, remaining)
        assert selected["product"] == "SC"
        assert selected["contract"]["contract_code"] == expected
        assert selected["session"]["business_date"] == day.isoformat()
        assert selected["calendar"]
        for fact in [selected["contract"], selected["session"], *selected["calendar"]]:
            assert fact["acquisition_ids"] and fact["raw_hashes"] and fact["evidence_hashes"]
            assert datetime.fromisoformat(fact["public_available_at"]) < datetime.fromisoformat(
                selected["session"]["session_start_at"]
            )


@pytest.mark.parametrize(
    ("published", "expected"),
    [
        ("2026-08-14T20:59:59.999999+08:00", "SC2609.INE"),
        ("2026-08-14T21:00:00+08:00", "SC2610.INE"),
        ("2026-08-17T08:00:00+08:00", "SC2610.INE"),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_public_contract_choice_obeys_night_session_notice_boundary(
    tmp_path: Path, published: str, expected: str
) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)

    def expiry_notice(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            document["data"]["items"][0][fields.index("delist_date")] = "20260901"
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(paths, transport=expiry_notice, metadata_public_at=published)
    latest = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
    )
    assert (
        next(c for c in latest["contracts"] if c["contract_code"] == "SC2609.INE")[
            "last_trade_date"
        ]
        == "2026-09-01"
    )
    result = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert result["missing"] == []
    assert result["selections"][0]["contract_code"] == expected


@pytest.mark.usefixtures("acquisition_clock")
def test_later_session_revision_cannot_reopen_a_frozen_contract_choice(tmp_path: Path) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)

    def expiry_notice(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            document["data"]["items"][0][fields.index("delist_date")] = "20260901"
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(
        paths,
        transport=expiry_notice,
        metadata_public_at="2026-08-14T21:15:00+08:00",
        monday_session_start="2026-08-14T22:00:00+08:00",
        monday_session_public_at="2026-08-14T21:30:00+08:00",
    )
    before = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        as_of=datetime(2026, 8, 14, 13, 14, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert before["missing"] == []
    assert before["selections"][0]["contract_code"] == "SC2610.INE"
    latest = select_futures_inputs(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        mode=AsOfMode.PUBLIC,
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
    )
    assert latest["sessions"][0]["session_start_at"] == "2026-08-14T22:00:00+08:00"
    after = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert after["missing"] == []
    assert after["selections"][0]["contract_code"] == "SC2610.INE"
    assert after["selections"][0]["selection_cutoff"] == before["selections"][0]["selection_cutoff"]


@pytest.mark.usefixtures("acquisition_clock")
def test_session_delay_announced_before_open_changes_the_selection_deadline(tmp_path: Path) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)

    def expiry_notice(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            document["data"]["items"][0][fields.index("delist_date")] = "20260901"
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(
        paths,
        transport=expiry_notice,
        metadata_public_at="2026-08-14T21:15:00+08:00",
        monday_session_start="2026-08-14T22:00:00+08:00",
        monday_session_public_at="2026-08-14T20:00:00+08:00",
    )
    selected = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert selected["missing"] == []
    assert selected["selections"][0]["contract_code"] == "SC2609.INE"
    assert selected["selections"][0]["remaining_open_days"] == 11
    assert selected["selections"][0]["session"]["session_start_at"] == "2026-08-14T22:00:00+08:00"


@pytest.mark.parametrize(
    ("unknown_day", "expected_codes", "expected_missing"),
    [
        ("2026-08-31", [], ["commodity_calendar_unavailable:INE:2026-08-31"]),
        ("2026-09-30", ["SC2609.INE"], []),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_contract_selection_requires_only_its_necessary_calendar_interval(
    tmp_path: Path, unknown_day: str, expected_codes: list[str], expected_missing: list[str]
) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def incomplete_calendar(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_trade_cal":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("cal_date")] == unknown_day:
                    row[fields.index("is_open")] = None
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(paths, transport=incomplete_calendar)
    result = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 14),
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert [s["contract_code"] for s in result["selections"]] == expected_codes
    assert result["missing"] == expected_missing


@pytest.mark.usefixtures("acquisition_clock")
def test_commodity_roll_return_uses_selected_contract_settlement_and_own_previous_settlement(
    tmp_path: Path,
) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)

    from pring_cycle.commodity_basket import calculate_commodity_returns

    # Independently reduced research pairs: 0.7 / 554.2 and 9.1 / 550.5.
    for day, contract, expected in (
        (date(2026, 8, 14), "SC2609.INE", Fraction(7, 5542)),
        (date(2026, 8, 17), "SC2610.INE", Fraction(91, 5505)),
    ):
        result = calculate_commodity_returns(
            paths,
            products=("SC",),
            business_date=day,
            as_of=datetime(2026, 8, 18, tzinfo=UTC),
            mode=AsOfMode.PUBLIC,
        )
        assert result["missing"] == []
        assert len(result["returns"]) == 1
        value = result["returns"][0]
        assert value["product"] == "SC"
        assert value["daily_return"] == pytest.approx(float(expected), abs=1e-14)
        assert (
            value["selection"]["contract_code"] == value["settlement"]["contract_code"] == contract
        )
        assert value["settlement"]["business_date"] == day.isoformat()
        assert value["settlement"]["raw_hashes"] and value["settlement"]["acquisition_ids"]
        for identity in value["settlement"]["acquisition_ids"]:
            assert AcquisitionRepository(paths.database, paths.artifacts).read_content(
                identity, "raw"
            )


@pytest.mark.parametrize("field", ["settle", "pre_settle"])
@pytest.mark.usefixtures("acquisition_clock")
def test_commodity_return_keeps_gap_when_selected_contract_lacks_settlement(
    tmp_path: Path, field: str
) -> None:
    from pring_cycle.commodity_basket import calculate_commodity_returns

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def incomplete_settlement(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2610.INE":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("trade_date")] == "20260817":
                    row[fields.index(field)] = None
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(paths, transport=incomplete_settlement)
    result = calculate_commodity_returns(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert result["returns"] == []
    assert result["missing"] == ["commodity_settlement_unavailable:SC2610.INE"]
    assert all(
        r.state == "validated"
        for r in AcquisitionRepository(paths.database, paths.artifacts).history()
    )


BASKET_CONTRACTS = {
    "CU": ("CU2604.SHF", "SHFE", "202604"),
    "RB": ("RB2604.SHF", "SHFE", "202604"),
    "PP": ("PP2604.DCE", "DCE", "202604"),
    "CF": ("CF2605.ZCE", "CZCE", "202605"),
    "TA": ("TA2604.ZCE", "CZCE", "202604"),
    "RU": ("RU2604.SHF", "SHFE", "202604"),
    "SP": ("SP2604.SHF", "SHFE", "202604"),
    "SC": ("SC2604.INE", "INE", "202604"),
}


def fixed_weight_basket_transport(payload: dict[str, Any]) -> bytes:
    """Fully synthetic base and two output days, with hand-calculable sleeve changes."""
    params = payload["params"]
    if payload["api_name"] == "fut_basic":
        product = params["fut_code"]
        code, exchange, month = BASKET_CONTRACTS[product]
        unit = "桶" if product == "SC" else "吨"
        return encode_rows(
            [
                {
                    "ts_code": code,
                    "symbol": code.split(".")[0],
                    "exchange": exchange,
                    "fut_code": product,
                    "d_month": month,
                    "list_date": "20250101",
                    "delist_date": "20260430",
                    "quote_unit": "人民币元/" + unit,
                    "per_unit": 1000 if product == "SC" else 10,
                    "trade_unit": unit,
                }
            ]
        )
    if payload["api_name"] == "fut_trade_cal":
        start, end = (
            date.fromisoformat(params["start_date"]),
            date.fromisoformat(params["end_date"]),
        )
        return encode_rows(
            [
                {
                    "exchange": params["exchange"],
                    "cal_date": day.isoformat(),
                    "is_open": int(day.weekday() < 5),
                }
                for offset in range((end - start).days + 1)
                for day in (start + timedelta(days=offset),)
            ]
        )
    assert payload["api_name"] == "fut_daily"
    product = next(p for p, (code, _, _) in BASKET_CONTRACTS.items() if code == params["ts_code"])
    levels = {
        "SC": ("100", "110", "99"),
        "CF": ("100", "130", "130"),
        "TA": ("100", "90", "90"),
    }.get(product, ("100", "100", "100"))
    return encode_rows(
        [
            {
                "ts_code": params["ts_code"],
                "trade_date": day,
                "pre_settle": previous,
                "settle": settle,
                "close": "999",
            }
            for day, previous, settle in zip(
                ("20260306", "20260309", "20260310"),
                ("100", levels[0], levels[1]),
                levels,
                strict=True,
            )
        ]
    )


def capture_reviewed_basket_inputs(
    paths: RuntimePaths,
    *,
    transport: Callable[[dict[str, Any]], bytes] = fixed_weight_basket_transport,
    settlement_revision_at: str | None = None,
    unknown_settlement_public: bool = False,
) -> None:
    acquired = TushareContextAdapter("synthetic-token", transport=transport).acquire_futures_inputs(
        paths,
        products=tuple(BASKET_CONTRACTS),
        start_date=date(2026, 3, 6),
        end_date=date(2026, 3, 10),
    )
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    proof = save_synthetic_document(
        paths, {"synthetic": True, "purpose": "base and daily fixed weights"}
    )
    publications = []
    for identity in acquired.acquisition_ids:
        receipt = repository.get(identity)
        for day in (
            ["2026-03-06", "2026-03-09", "2026-03-10"]
            if receipt.api_name == "fut_daily"
            else [None]
        ):
            published: str | None = (
                "2026-01-01T08:00:00+00:00" if day is None else day + "T08:00:00+00:00"
            )
            if day == "2026-03-10" and settlement_revision_at is not None:
                published = settlement_revision_at
            if day == "2026-03-10" and unknown_settlement_public:
                published = None
            publications.append(
                {
                    "api_name": receipt.api_name,
                    "parameters": receipt.parameters,
                    "raw_hash": receipt.raw_hash,
                    "business_date": day,
                    "release_at": published,
                    "public_available_at": published,
                    "evidence": [proof],
                }
            )
    packet = {
        "schema_version": "futures-input-evidence-v0001",
        "evidence": [{"artifact_hash": proof, "source_reference": "synthetic:fixed-weight-basket"}],
        "publications": publications,
        "sessions": [
            {
                "product": product,
                "exchange": exchange,
                "business_date": day,
                "session_start_at": previous + "T21:00:00+08:00",
                "release_at": "2026-01-01T08:00:00+00:00",
                "public_available_at": "2026-01-01T08:00:00+00:00",
                "evidence": [proof],
            }
            for product, (_, exchange, _) in BASKET_CONTRACTS.items()
            for day, previous in (
                ("2026-03-06", "2026-03-05"),
                ("2026-03-09", "2026-03-06"),
                ("2026-03-10", "2026-03-09"),
            )
        ],
    }
    review = save_synthetic_document(
        paths,
        {
            "schema_version": "futures-input-evidence-review-v0001",
            "subject_hash": hashlib.sha256(encode_document(packet)).hexdigest(),
            "reviewer": "synthetic fixed-weight reviewer",
            "reviewed_at": "2026-09-07T00:00:00+00:00",
            "decision": "accepted",
        },
    )
    packet_hash = save_synthetic_document(paths, {**packet, "review_hash": review})
    bind_futures_input_evidence(
        paths, acquisition_ids=acquired.acquisition_ids, evidence_hash=packet_hash
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_basket_keeps_fixed_base_and_restores_seven_sleeve_weights_each_day(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_basket_inputs(paths)

    from pring_cycle.commodity_basket import calculate_commodity_basket

    result = calculate_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert result["missing"] == []
    assert result["base_date"] == "2026-03-06" and result["base_level"] == 1000
    assert result["formula_version"] == "ex-hog-calendar-settlement-v0002"
    assert {entry["selection"]["product"] for entry in result["base_inputs"]} == set(
        BASKET_CONTRACTS
    )
    days = result["days"]
    assert [day["business_date"] for day in days] == ["2026-03-09", "2026-03-10"]
    # Mar 9: crude +10% contributes 2 pp; CF +30% and TA -10% make textiles +10%,
    # contributing 4/3 pp. Mar 10: crude -10% contributes -2 pp at restored weight.
    assert days[0]["level"] == pytest.approx(float(Fraction(3100, 3)), abs=1e-10)
    assert days[1]["level"] == pytest.approx(float(Fraction(3038, 3)), abs=1e-10)
    expected_contributions = {
        "copper": 0,
        "rebar": 0,
        "polypropylene": 0,
        "rubber": 0,
        "pulp": 0,
        "textiles": float(Fraction(4, 3)),
        "crude_oil": 2,
    }
    assert days[0]["contributions"] == pytest.approx(expected_contributions, abs=1e-12)
    assert days[1]["contributions"] == pytest.approx(
        {**expected_contributions, "textiles": 0, "crude_oil": -2}, abs=1e-12
    )
    assert days[0]["daily_return"] == pytest.approx(float(Fraction(1, 30)), abs=1e-14)
    assert days[1]["daily_return"] == pytest.approx(-0.02, abs=1e-14)
    for day in days:
        assert len(day["returns"]) == 8
        assert {entry["product"] for entry in day["returns"]} == set(BASKET_CONTRACTS)
        assert all(
            entry["selection"]["contract"]["raw_hashes"] and entry["settlement"]["raw_hashes"]
            for entry in day["returns"]
        )


@pytest.mark.parametrize(
    ("field", "expected_dates", "expected_missing"),
    [
        (
            "settle",
            [],
            ["commodity_base_settlement_missing:SC2604.INE", "commodity_fixed_base_unavailable"],
        ),
        ("pre_settle", ["2026-03-09", "2026-03-10"], []),
    ],
)
@pytest.mark.usefixtures("acquisition_clock")
def test_fixed_base_requires_its_settlement_without_imposing_a_pre_base_return(
    tmp_path: Path, field: str, expected_dates: list[str], expected_missing: list[str]
) -> None:
    from pring_cycle.commodity_basket import calculate_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def base_input_gap(payload: dict[str, Any]) -> bytes:
        raw = fixed_weight_basket_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "SC2604.INE":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("trade_date")] == "20260306":
                    row[fields.index(field)] = None
            return encode_document(document)
        return raw

    capture_reviewed_basket_inputs(paths, transport=base_input_gap)
    result = calculate_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert [day["business_date"] for day in result["days"]] == expected_dates
    assert result["missing"] == expected_missing
    assert result["base_date"] == "2026-03-06"


@pytest.mark.usefixtures("acquisition_clock")
def test_basket_missing_polypropylene_breaks_chain_without_reweighting_or_rebasing(
    tmp_path: Path,
) -> None:
    from pring_cycle.commodity_basket import calculate_commodity_basket

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)

    def missing_polypropylene(payload: dict[str, Any]) -> bytes:
        raw = fixed_weight_basket_transport(payload)
        if payload["api_name"] == "fut_daily" and payload["params"]["ts_code"] == "PP2604.DCE":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            for row in document["data"]["items"]:
                if row[fields.index("trade_date")] == "20260309":
                    row[fields.index("settle")] = None
            return encode_document(document)
        return raw

    capture_reviewed_basket_inputs(paths, transport=missing_polypropylene)
    result = calculate_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        as_of=datetime(2026, 3, 10, 9, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert result["days"] == []
    assert result["missing"] == ["commodity_settlement_unavailable:PP2604.DCE:2026-03-09"]
    assert len(result["base_inputs"]) == 8
    assert result["base_date"] == "2026-03-06" and result["base_level"] == 1000


@pytest.mark.usefixtures("acquisition_clock")
def test_system_basket_waits_for_captured_and_validated_inputs(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_basket_inputs(paths)
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    assert all(
        r.validated_at is not None and r.validated_at > datetime(2026, 9, 7, tzinfo=UTC)
        for r in repository.history()
    )

    from pring_cycle.commodity_basket import calculate_commodity_basket

    before = calculate_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 7, tzinfo=UTC),
    )
    assert before["days"] == []
    assert "commodity_fixed_base_unavailable" in before["missing"]
    after = calculate_commodity_basket(
        paths,
        business_date=date(2026, 3, 10),
        mode=AsOfMode.SYSTEM,
        as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    assert after["missing"] == []
    assert [day["business_date"] for day in after["days"]] == ["2026-03-09", "2026-03-10"]
    assert after["days"][-1]["level"] == pytest.approx(float(Fraction(3038, 3)), abs=1e-10)


def test_system_contract_revision_preserves_the_earlier_system_snapshot(
    tmp_path: Path, acquisition_clock: Callable[[], datetime]
) -> None:
    from pring_cycle.commodity_basket import calculate_commodity_returns

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)
    old_cutoff = acquisition_clock()
    before = calculate_commodity_returns(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        mode=AsOfMode.SYSTEM,
        as_of=old_cutoff,
    )
    assert before["missing"] == []
    assert before["returns"][0]["selection"]["contract_code"] == "SC2610.INE"
    assert before["returns"][0]["daily_return"] == pytest.approx(
        float(Fraction(91, 5505)), abs=1e-14
    )

    def expiry_notice(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_basic":
            document = json.loads(raw)
            fields = document["data"]["fields"]
            document["data"]["items"][0][fields.index("delist_date")] = "20260901"
            return encode_document(document)
        return raw

    capture_reviewed_roll_inputs(
        paths, transport=expiry_notice, metadata_public_at="2026-08-14T20:00:00+08:00"
    )
    historical = calculate_commodity_returns(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        mode=AsOfMode.SYSTEM,
        as_of=old_cutoff,
    )
    assert historical == before
    current = calculate_commodity_returns(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 17),
        mode=AsOfMode.SYSTEM,
        as_of=acquisition_clock(),
    )
    assert current["missing"] == []
    assert current["returns"][0]["selection"]["contract_code"] == "SC2609.INE"
    assert current["returns"][0]["daily_return"] == pytest.approx(
        float(Fraction(451, 5549)), abs=1e-14
    )


@pytest.mark.usefixtures("acquisition_clock")
def test_conflicting_near_contract_does_not_silently_select_far_contract(tmp_path: Path) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)

    def conflicting_expiry(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] == "fut_basic":
            return raw.replace(b"20260831", b"20260901")
        return raw

    capture_reviewed_roll_inputs(paths, transport=conflicting_expiry)
    selected = select_commodity_contracts(
        paths,
        products=("SC",),
        business_date=date(2026, 8, 14),
        as_of=datetime(2026, 8, 14, 9, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    assert selected["selections"] == []
    assert any("SC2609" in gap for gap in selected["missing"])


@pytest.mark.usefixtures("acquisition_clock")
@pytest.mark.parametrize("damage", ["review_normalized", "contract_raw"])
def test_damaged_near_contract_batch_cannot_fall_back_to_far_month(
    tmp_path: Path, damage: str
) -> None:
    from pring_cycle.commodity_basket import select_commodity_contracts

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    capture_reviewed_roll_inputs(paths)
    repository = AcquisitionRepository(paths.database, paths.artifacts)
    reviewed = next(r for r in repository.history() if r.api_name == "futures_input_evidence")
    digest = reviewed.normalized_hash
    if damage == "contract_raw":
        digest = next(r.raw_hash for r in repository.history() if r.api_name == "fut_basic")
    assert digest is not None
    artifact = paths.artifacts / digest[:2] / digest
    original = artifact.read_bytes()

    def far_only(payload: dict[str, Any]) -> bytes:
        raw = calendar_roll_transport(payload)
        if payload["api_name"] != "fut_basic":
            return raw
        document = json.loads(raw)
        document["data"]["items"] = document["data"]["items"][1:]
        return encode_document(document)

    capture_reviewed_roll_inputs(paths, transport=far_only)
    arguments = dict(
        products=("SC",),
        business_date=date(2026, 8, 14),
        as_of=datetime(2026, 8, 14, 9, tzinfo=UTC),
        mode=AsOfMode.PUBLIC,
    )
    before = select_commodity_contracts(paths, **arguments)
    assert before["missing"] == []
    assert before["selections"][0]["contract_code"] == "SC2609.INE"
    artifact.write_bytes(b"damaged reviewed near-contract normalization")
    blocked = select_commodity_contracts(paths, **arguments)
    assert blocked["selections"] == []
    assert blocked["missing"]
    artifact.write_bytes(original)
    assert select_commodity_contracts(paths, **arguments) == before

    if damage == "review_normalized":
        artifact.write_bytes(b"damaged old review normalization")
        capture_reviewed_roll_inputs(paths, metadata_public_at="2026-01-02T08:00:00+00:00")
        superseding = select_commodity_contracts(paths, **arguments)
        assert superseding["missing"] == []
        assert superseding["selections"][0]["contract_code"] == "SC2609.INE"
