"""ADR-0030: breadth from TuShare's daily quotes and technical factors, no reviewed inputs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

import pring_cycle.breadth as breadth
from pring_cycle.breadth import breadth_scalars

DAY = date(2026, 9, 24)
# 2026-09-24: an old share, a new listing's first day, a suspended share, a share listed 100
# sessions ago, a B share and a CDR (both outside the members).
LISTINGS = {
    "L": [
        ("600000.SH", "19991110"),
        ("688999.SH", "20260924"),
        ("000002.SZ", "19910129"),
        ("920001.BJ", None),  # filled in with the 100th session back below
        ("900901.SH", "19920221"),
        ("689009.SH", "20201029"),
    ],
    "D": [("600001.SH", "19980101")],
    "P": [],
}
QUOTES = [
    # code, close, pre_close, vol, amount
    ("600000.SH", 10.5, 10.0, 1000.0, 5000.0),  # advance
    ("688999.SH", 30.0, 20.0, 800.0, 3000.0),  # first day: advance
    ("000002.SZ", 8.0, 8.0, 0.0, 0.0),  # no volume: suspended, not a participant
    ("920001.BJ", 4.0, 5.0, 100.0, 2000.0),  # decline
    ("900901.SH", 1.0, 0.5, 10.0, 99.0),  # B share: never counted
]
FACTORS = [
    # code, close_qfq, ma_qfq_90, ma_qfq_250, topdays, lowdays
    ("600000.SH", 10.5, 10.0, 11.0, 300.0, 0.0),
    ("688999.SH", 30.0, None, None, None, None),
    ("000002.SZ", 8.0, 7.0, 7.0, 400.0, 0.0),
    ("920001.BJ", 4.0, 4.5, 4.5, 0.0, 95.0),
    ("900901.SH", 1.0, 0.1, 0.1, 999.0, 0.0),
]


def sessions() -> list[date]:
    days, day = [], DAY
    while len(days) < 400:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return sorted(days)


def fake_call(calls: list[tuple[str, dict[str, str]]]):  # type: ignore[no-untyped-def]
    listed_100 = sessions()[-100].strftime("%Y%m%d")

    def call(api: str, params: dict[str, str], fields: tuple[str, ...]) -> Any:
        calls.append((api, params))
        if api == "stock_basic":
            status = params["list_status"]
            rows = [
                {"ts_code": code, "list_status": status, "list_date": listed or listed_100}
                for code, listed in LISTINGS[status]
            ]
        elif api == "trade_cal":
            rows = [{"cal_date": d.strftime("%Y%m%d"), "is_open": 1} for d in sessions()]
        elif api == "daily":
            rows = [
                dict(zip(("ts_code", "close", "pre_close", "vol", "amount"), q, strict=True))
                | {"trade_date": params["trade_date"]}
                for q in QUOTES
            ]
        else:
            assert api == "stk_factor_pro"
            names = ("ts_code", "close_qfq", "ma_qfq_90", "ma_qfq_250", "topdays", "lowdays")
            rows = [
                dict(zip(names, f, strict=True)) | {"trade_date": params["trade_date"]}
                for f in FACTORS
            ]
        start = int(params.get("offset", 0))
        return tuple(rows[start : start + int(params.get("limit", len(rows)))])

    return call


def values(scalars: Any) -> dict[tuple[str, str], float]:
    return {(s.metric_id, s.dimensions["measure"]): s.value for s in scalars}


def test_daily_breadth_counts_first_days_and_leaves_out_suspended_and_b_shares() -> None:
    result = values(breadth_scalars(fake_call([]), end_date=DAY, window=1))

    assert result[("CN_EQ_ADV_DEC", "advances")] == 2
    assert result[("CN_EQ_ADV_DEC", "declines")] == 1
    assert result[("CN_EQ_ADV_DEC", "flats")] == 0
    assert result[("CN_EQ_ADV_DEC", "participants")] == 3
    assert result[("CN_EQ_AD_RATIO", "advance_decline_ratio")] == 2.0
    # 5000 + 3000 of 10000 traded on the day.
    assert result[("CN_EQ_ADV_AMOUNT_SHARE", "advancing_amount_share")] == 80.0


def test_windows_count_only_shares_traded_listed_long_enough_and_with_the_factor() -> None:
    result = values(breadth_scalars(fake_call([]), end_date=DAY, window=1))

    # 90 days: the old share and the one listed 100 sessions ago (the first-day share has no
    # factor, the suspended one did not trade).
    assert result[("CN_EQ_NEW_HIGH_LOW_90", "new_highs")] == 1
    assert result[("CN_EQ_NEW_HIGH_LOW_90", "new_lows")] == 1
    assert result[("CN_EQ_ABOVE_MA90", "above_ma_share")] == 50.0
    # 250 days: only the old share is old enough.
    assert result[("CN_EQ_NEW_HIGH_LOW_250", "new_highs")] == 1
    assert result[("CN_EQ_NEW_HIGH_LOW_250", "new_lows")] == 0
    assert result[("CN_EQ_ABOVE_MA250", "above_ma_share")] == 0.0
    assert {s.source_field for s in breadth_scalars(fake_call([]), end_date=DAY, window=1)} >= {
        "new_highs_90",
        "above_ma_share_250",
        "advances",
    }


def test_a_full_page_is_followed_by_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(breadth, "PAGE_ROWS", 2)
    calls: list[tuple[str, dict[str, str]]] = []

    result = values(breadth_scalars(fake_call(calls), end_date=DAY, window=1))

    assert result[("CN_EQ_ADV_DEC", "participants")] == 3
    assert [p["offset"] for api, p in calls if api == "daily"] == ["0", "2", "4"]


def test_only_the_window_days_not_yet_held_are_fetched() -> None:
    calls: list[tuple[str, dict[str, str]]] = []
    previous = sessions()[-2]

    scalars = breadth_scalars(fake_call(calls), end_date=DAY, held_days={previous}, window=3)

    assert {s.period_end for s in scalars} == {sessions()[-3].isoformat(), DAY.isoformat()}
    assert [p["trade_date"] for api, p in calls if api == "daily"] == [
        sessions()[-3].strftime("%Y%m%d"),
        DAY.strftime("%Y%m%d"),
    ]


def test_nothing_left_to_compute_fetches_only_the_calendar() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    assert breadth_scalars(fake_call(calls), end_date=DAY, held_days={DAY}, window=1) == ()
    assert [api for api, _ in calls] == ["trade_cal"]


def test_an_unknown_security_code_refuses_the_delivery() -> None:
    LISTINGS["L"].append(("123456.SH", "20200101"))
    try:
        with pytest.raises(ValueError, match="tushare_breadth_security_scope_unknown"):
            breadth_scalars(fake_call([]), end_date=DAY, window=1)
    finally:
        LISTINGS["L"].pop()


@pytest.mark.parametrize(
    ("code", "member"),
    [
        ("302132.SZ", True),
        ("004001.SZ", True),
        ("920001.BJ", True),
        ("001001.SZ", False),  # Main-board depositary receipt.
        ("309800.SZ", False),  # ChiNext depositary receipt.
        ("689009.SH", False),  # STAR CDR.
        ("200002.SZ", False),  # B share.
    ],
)
def test_members_are_ordinary_a_shares_only(code: str, member: bool) -> None:
    assert breadth.ordinary_share(code) is member


@pytest.mark.parametrize("extra_field", ["close", 123, ""])
def test_ambiguous_response_fields_are_refused_before_rows_are_read(extra_field: object) -> None:
    from pring_cycle.tushare_context import TushareContextAdapter

    rows = fake_call([])

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        names = payload["fields"].split(",")
        selected = rows(payload["api_name"], payload["params"], tuple(names))
        document = {
            "code": 0,
            "data": {"fields": names, "items": [[row.get(n) for n in names] for row in selected]},
        }
        if payload["api_name"] == "daily":
            document["data"]["fields"].append(extra_field)
            for item in document["data"]["items"]:
                item.append(11.0)
        return document

    adapter = TushareContextAdapter("fixture-token", transport=transport)
    with pytest.raises(ValueError, match="response_schema_invalid"):
        adapter.breadth(end_date=DAY, held_days=())
