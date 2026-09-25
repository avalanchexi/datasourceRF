"""Gap sources #06/#07: the Cboe VIX history and the CFETS 16:30 close, read as published."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pring_cycle.quote_sources import parse_cboe_vix_history, parse_chinamoney_close

FIXTURES = Path(__file__).parents[1] / "fixtures" / "quote_sources"
VIX = (FIXTURES / "VIX_History-20260925.csv").read_bytes()
CFETS = (FIXTURES / "rfx-sp-iday-chrt-20260925.json").read_bytes()


def test_vix_history_gives_each_session_close() -> None:
    rows = parse_cboe_vix_history(VIX, start_date=date(2026, 9, 18), end_date=date(2026, 9, 30))

    assert [(row.business_date, row.value) for row in rows] == [
        ("2026-09-18", 14.81),
        ("2026-09-21", 14.87),
        ("2026-09-22", 14.21),
    ]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (VIX.replace(b"DATE,OPEN,HIGH,LOW,CLOSE", b"DATE,CLOSE,OPEN,HIGH,LOW"), "columns"),
        (VIX + b"09/22/2026,14.64,14.95,14.19,14.30\n", "duplicate_date"),
        (VIX + b"2026-09-23,14.64,14.95,14.19,14.30\n", "row_invalid"),
        (VIX + b"09/23/2026,14.64,14.95,14.19,n/a\n", "row_invalid"),
        (b"<html>maintenance</html>", "columns"),
    ],
)
def test_a_changed_vix_history_is_refused_rather_than_read(content: bytes, reason: str) -> None:
    with pytest.raises(ValueError, match=f"cboe_vix_{reason}"):
        parse_cboe_vix_history(content, start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))


def test_cfets_close_is_the_1630_price_of_the_session_it_ended() -> None:
    # The file stood at 2026-09-25 03:00: the night session of the 24th had just closed.
    rows = parse_chinamoney_close(CFETS)

    assert [(row.business_date, row.value) for row in rows] == [("2026-09-24", 6.7131)]


def test_the_night_close_is_never_taken_for_the_1630_close() -> None:
    document = json.loads(CFETS)
    document["data"]["closeSpotPrice"] = document["data"]["spotPriceStr"]  # the 03:00 close

    with pytest.raises(ValueError, match="chinamoney_close_snapshot_mismatch"):
        parse_chinamoney_close(json.dumps(document).encode())


def test_no_close_is_taken_before_the_session_reaches_1630() -> None:
    document = json.loads(CFETS)
    document["data"].update(closeSpotPrice="", lastDate="2026-09-24 14:20")

    assert parse_chinamoney_close(json.dumps(document).encode()) == ()


def test_a_changed_cfets_document_is_refused() -> None:
    document = json.loads(CFETS)
    del document["data"]["lastDate"]

    with pytest.raises(ValueError, match="chinamoney_close_document_invalid"):
        parse_chinamoney_close(json.dumps(document).encode())
