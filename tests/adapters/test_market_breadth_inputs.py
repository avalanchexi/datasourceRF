from datetime import date
from typing import Any

import pytest

from pring_cycle.tushare_context import TushareContextAdapter


def response(rows: list[dict[str, object]], fields: str) -> dict[str, Any]:
    names = fields.split(",")
    return {
        "code": 0,
        "data": {"fields": names, "items": [[row[name] for name in names] for row in rows]},
    }


def test_breadth_inputs_use_historical_membership_and_explain_suspended_missing_quote() -> None:
    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        api = payload["api_name"]
        if api == "stock_basic":
            rows = [
                {"ts_code": code, "list_date": listed, "list_status": "L", "delist_date": None}
                for code, listed in [
                    ("000001.SZ", "19910403"),
                    ("002084.SZ", "20061124"),
                    ("301717.SZ", "20260811"),
                    ("689009.SH", "20201029"),
                    ("600999.SH", "20260820"),
                ]
            ]
            if payload["params"]["list_status"] != "L":
                rows = []
        elif api == "suspend_d":
            assert payload["params"]["trade_date"] == "20260819"
            rows = [
                {
                    "trade_date": "20260819",
                    "ts_code": "002084.SZ",
                    "suspend_type": "S",
                    "suspend_timing": None,
                }
            ]
        else:
            assert api == "daily"
            assert payload["params"]["trade_date"] == "20260819"
            rows = [
                {
                    "trade_date": "20260819",
                    "ts_code": code,
                    "close": 12.0,
                    "pre_close": 10.0,
                    "amount": 100.0,
                    "ah_amount": after_hours,
                }
                for code, after_hours in [
                    ("000001.SZ", 0.0),
                    ("301717.SZ", None),
                    ("689009.SH", 200.0),
                ]
            ]
        return response(rows, payload["fields"])

    result = TushareContextAdapter("fixture-token", transport=transport).market_breadth_inputs(
        trading_days=(date(2026, 8, 19),)
    )
    assert len(result) == 1
    day = result[0]
    assert day.listed_codes == ("000001.SZ", "002084.SZ", "301717.SZ")
    assert day.suspended_codes == ("002084.SZ",)
    assert tuple(quote.ts_code for quote in day.quotes) == ("000001.SZ", "301717.SZ")
    assert day.quotes[0].after_hours_amount == 0.0
    assert day.quotes[1].after_hours_amount is None
    assert day.membership_basis == "current_stock_basic_listing_intervals_not_public_as_of"


def day_rows() -> dict[str, list[dict[str, object]]]:
    return {
        "stock_basic": [
            {
                "ts_code": "000001.SZ",
                "list_date": "19910403",
                "list_status": "L",
                "delist_date": None,
            }
        ],
        "daily": [
            {
                "trade_date": "20260819",
                "ts_code": "000001.SZ",
                "close": 11.24,
                "pre_close": 10.94,
                "amount": 100.0,
                "ah_amount": None,
            }
        ],
        "suspend_d": [],
    }


def adapter(rows: dict[str, list[dict[str, object]]]) -> TushareContextAdapter:
    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        selected = rows[payload["api_name"]]
        if payload["api_name"] == "stock_basic":
            selected = [
                row for row in selected if row["list_status"] == payload["params"]["list_status"]
            ]
        return response(selected, payload["fields"])

    return TushareContextAdapter("fixture-token", transport=transport)


@pytest.mark.parametrize("api", ["daily", "suspend_d"])
def test_breadth_inputs_reject_duplicate_and_wrong_date_rows(api: str) -> None:
    rows = day_rows()
    if api == "suspend_d":
        rows[api] = [
            {
                "trade_date": "20260819",
                "ts_code": "000001.SZ",
                "suspend_type": "R",
                "suspend_timing": None,
            }
        ]
    rows[api].append(dict(rows[api][0]))
    with pytest.raises(ValueError, match="duplicate_"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))
    rows[api].pop()
    rows[api][0]["trade_date"] = "20260818"
    with pytest.raises(ValueError, match="tushare_response_period_mismatch"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


@pytest.mark.parametrize("suspension", [None, "R", "intraday"])
def test_missing_daily_quote_requires_explicit_full_day_suspension(suspension: str | None) -> None:
    rows = day_rows()
    rows["daily"] = []
    if suspension is not None:
        rows["suspend_d"] = [
            {
                "trade_date": "20260819",
                "ts_code": "000001.SZ",
                "suspend_type": "R" if suspension == "R" else "S",
                "suspend_timing": "09:30-10:30" if suspension == "intraday" else None,
            }
        ]
    with pytest.raises(ValueError, match="quote_membership_mismatch"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_full_day_suspended_member_cannot_also_supply_trading_quote() -> None:
    rows = day_rows()
    rows["suspend_d"] = [
        {
            "trade_date": "20260819",
            "ts_code": "000001.SZ",
            "suspend_type": "S",
            "suspend_timing": None,
        }
    ]
    with pytest.raises(ValueError, match="quote_membership_mismatch"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


@pytest.mark.parametrize(
    "field,value",
    [
        ("close", 0),
        ("pre_close", 0),
        ("amount", None),
        ("amount", -1),
        ("ah_amount", -1),
        ("close", float("nan")),
        ("close", True),
        ("amount", float("inf")),
    ],
)
def test_breadth_inputs_reject_invalid_numeric_inputs(field: str, value: object) -> None:
    rows = day_rows()
    rows["daily"][0][field] = value
    with pytest.raises(ValueError, match="number_invalid"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_breadth_inputs_reject_quotes_outside_historical_membership() -> None:
    rows = day_rows()
    rows["daily"].append({**rows["daily"][0], "ts_code": "600355.SH"})
    with pytest.raises(ValueError, match="quote_membership_mismatch"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


@pytest.mark.parametrize("days", [(), (date(2026, 8, 19), date(2026, 8, 19))])
def test_invalid_calendar_fails_before_network(days: tuple[date, ...]) -> None:
    source = adapter(day_rows())
    with pytest.raises(ValueError, match="calendar_invalid"):
        source.market_breadth_inputs(trading_days=days)
    assert source.network_requests == 0


def test_breadth_inputs_fail_closed_at_documented_response_limits() -> None:
    rows = day_rows()
    rows["daily"] *= 6_000
    with pytest.raises(ValueError, match="response_incomplete"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_breadth_inputs_preserve_ex_right_reference_and_real_zero() -> None:
    rows = day_rows()
    rows["daily"][0]["amount"] = 0.0
    rows["daily"][0]["ah_amount"] = 0.0
    quote = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))[0].quotes[0]
    assert quote.close == 11.24 and quote.pre_close == 10.94
    assert quote.amount == quote.after_hours_amount == 0.0


def test_breadth_reconstructs_delisting_interval_including_final_trading_day() -> None:
    rows = day_rows()
    rows["stock_basic"].append(
        {
            "ts_code": "300391.SZ",
            "list_date": "20140801",
            "list_status": "D",
            "delist_date": "20260413",
        }
    )
    rows["daily"] = [
        {**rows["daily"][0], "trade_date": "20260410"},
        {**rows["daily"][0], "trade_date": "20260410", "ts_code": "300391.SZ"},
    ]
    final_trading_day = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 4, 10),))[0]
    assert "300391.SZ" in final_trading_day.listed_codes
    rows["daily"] = [{**rows["daily"][0], "trade_date": "20260413"}]
    delisting_day = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 4, 13),))[0]
    assert "300391.SZ" not in delisting_day.listed_codes


def test_intraday_halt_and_resumption_are_distinct_valid_events() -> None:
    rows = day_rows()
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": "R",
            "suspend_timing": None,
        },
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": "S",
            "suspend_timing": "10:48-10:58,10:59-11:09",
        },
    ]
    result = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))[0]
    assert result.suspended_codes == ()
    assert len(result.quotes) == 1


def test_scope_includes_302_stock_and_excludes_depositary_receipts() -> None:
    rows = day_rows()
    for code in ("302132.SZ", "004001.SZ", "001001.SZ", "309800.SZ", "689009.SH"):
        rows["stock_basic"].append({**rows["stock_basic"][0], "ts_code": code})
        rows["daily"].append({**rows["daily"][0], "ts_code": code})
    result = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))[0]
    assert result.listed_codes == ("000001.SZ", "004001.SZ", "302132.SZ")
    assert tuple(quote.ts_code for quote in result.quotes) == result.listed_codes


@pytest.mark.parametrize(
    "field,value", [("list_date", "0"), ("list_date", None), ("delist_date", "20260819")]
)
def test_listing_dates_must_be_valid_and_consistent_with_status(field: str, value: object) -> None:
    rows = day_rows()
    rows["stock_basic"][0][field] = value
    with pytest.raises(ValueError, match="date_invalid|listing_interval_invalid"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_breadth_inputs_reject_duplicate_listing_identities() -> None:
    rows = day_rows()
    rows["stock_basic"].append(dict(rows["stock_basic"][0]))
    with pytest.raises(ValueError, match="duplicate_code"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_legacy_identity_delisted_before_window_does_not_require_current_code_classification() -> (
    None
):
    rows = day_rows()
    rows["stock_basic"].append(
        {
            "ts_code": "T600018.SH",
            "list_status": "D",
            "list_date": "20000719",
            "delist_date": "20061020",
        }
    )
    result = adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))[0]
    assert result.listed_codes == ("000001.SZ",)
    rows["stock_basic"][-1]["delist_date"] = "20260820"
    with pytest.raises(ValueError, match="security_scope_unknown"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_conflicting_full_day_halt_and_resumption_cannot_explain_missing_quote() -> None:
    rows = day_rows()
    rows["daily"] = []
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": kind,
            "suspend_timing": None,
        }
        for kind in ("S", "R")
    ]
    with pytest.raises(ValueError, match="suspension_conflict"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


@pytest.mark.parametrize("extra_field", ["close", 123, ""])
def test_ambiguous_response_fields_are_rejected_before_dictionary_conversion(
    extra_field: object,
) -> None:
    rows = day_rows()

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        selected = rows[payload["api_name"]]
        if payload["api_name"] == "stock_basic":
            selected = [
                row for row in selected if row["list_status"] == payload["params"]["list_status"]
            ]
        document = response(selected, payload["fields"])
        if payload["api_name"] == "daily":
            document["data"]["fields"].append(extra_field)
            document["data"]["items"][0].append(11.0)
            if extra_field == "close":
                document["data"]["items"][0][2] = -999.0
        return document

    source = TushareContextAdapter("fixture-token", transport=transport)
    with pytest.raises(ValueError, match="response_schema_invalid"):
        source.market_breadth_inputs(trading_days=(date(2026, 8, 19),))


@pytest.mark.parametrize(
    "timing", ["not-a-time", "25:00-26:00", "10:30-09:30", "09:30-09:40,09:35-09:45"]
)
def test_invalid_or_overlapping_suspension_times_are_rejected(timing: str) -> None:
    rows = day_rows()
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": "S",
            "suspend_timing": timing,
        }
    ]
    with pytest.raises(ValueError, match="suspension_invalid"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_null_and_empty_full_day_events_are_duplicates() -> None:
    rows = day_rows()
    rows["daily"] = []
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": "S",
            "suspend_timing": timing,
        }
        for timing in (None, "")
    ]
    with pytest.raises(ValueError, match="duplicate_suspension"):
        adapter(rows).market_breadth_inputs(trading_days=(date(2026, 8, 19),))


def test_reviewed_official_full_day_evidence_resolves_only_its_exact_conflict() -> None:
    from pring_cycle.market_breadth import FullDaySuspensionEvidence

    rows = day_rows()
    rows["daily"] = []
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": kind,
            "suspend_timing": None,
        }
        for kind in ("S", "R")
    ]
    evidence = FullDaySuspensionEvidence(date(2026, 8, 19), "000001.SZ", "a" * 64)
    result = adapter(rows).market_breadth_inputs(
        trading_days=(date(2026, 8, 19),), full_day_suspension_evidence=(evidence,)
    )[0]
    assert result.suspended_codes == ("000001.SZ",)
    assert result.quotes == ()
    assert result.full_day_suspension_evidence == (evidence,)


@pytest.mark.parametrize(
    "case", ["wrong_day", "wrong_code", "bad_hash", "duplicate", "has_quote", "no_conflict"]
)
def test_official_evidence_cannot_override_another_day_identity_or_valid_quote(case: str) -> None:
    from pring_cycle.market_breadth import FullDaySuspensionEvidence

    rows = day_rows()
    quote = rows["daily"][0]
    rows["daily"] = []
    rows["suspend_d"] = [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20260819",
            "suspend_type": kind,
            "suspend_timing": None,
        }
        for kind in ("S", "R")
    ]
    evidence = FullDaySuspensionEvidence(
        date(2026, 8, 18 if case == "wrong_day" else 19),
        "000002.SZ" if case == "wrong_code" else "000001.SZ",
        "invalid" if case == "bad_hash" else "a" * 64,
    )
    if case == "has_quote":
        rows["daily"] = [quote]
    if case == "no_conflict":
        rows["suspend_d"].pop()
    with pytest.raises(ValueError, match="suspension_evidence_|quote_membership_mismatch"):
        adapter(rows).market_breadth_inputs(
            trading_days=(date(2026, 8, 19),),
            full_day_suspension_evidence=(evidence, evidence)
            if case == "duplicate"
            else (evidence,),
        )
