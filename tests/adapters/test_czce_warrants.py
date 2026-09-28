"""Run findings 02: TA and CF warrants read from CZCE's own daily report (ADR-0032)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from pring_cycle.czce_warrants import parse_czce_warrants

FIXTURES = Path(__file__).parents[1] / "fixtures" / "czce_warrants"
MAY_19 = (FIXTURES / "FutureDataWhsheet-20260519.txt").read_bytes()
SEP_02 = (FIXTURES / "FutureDataWhsheet-20260902.txt").read_bytes()


def test_pta_members_are_the_warehouse_subtotals_of_may_19() -> None:
    # TuShare doubled each warehouse's last brand row that day and added a misplaced row.
    members = parse_czce_warrants(MAY_19, business_date=date(2026, 5, 19), symbol="TA")

    assert len(members) == 27
    (changjiang,) = (m for m in members if m.warehouse == "长江国际")
    assert (changjiang.registered_receipts, changjiang.registered_receipts_change) == (1176, -144)
    assert sum(m.registered_receipts for m in members) == 180755
    assert sum(m.registered_receipts_change for m in members) == -4944
    # A warehouse holding none is still a member.
    assert any(m.registered_receipts == 0 for m in members)


def test_pta_and_cotton_members_of_sep_02_add_up_to_their_totals() -> None:
    pta = parse_czce_warrants(SEP_02, business_date=date(2026, 9, 2), symbol="TA")
    cotton = parse_czce_warrants(SEP_02, business_date=date(2026, 9, 2), symbol="CF")

    assert len(pta) == 26
    assert sum(m.registered_receipts for m in pta) == 1069
    assert (
        sum(m.registered_receipts for m in cotton),
        sum(m.registered_receipts_change for m in cotton),
    ) == (8858, -52)


def test_pta_quantity_is_duty_paid_and_bonded_together() -> None:
    bonded = (
        MAY_19.replace(
            "0541      |长江国际              |海伦石化      |1176            |0      ".encode(),
            "0541      |长江国际              |海伦石化      |1176            |4      ".encode(),
        )
        .replace(
            "小计      |                  |          |1176            |0      ".encode(),
            "小计      |                  |          |1176            |4      ".encode(),
        )
        .replace(
            "总计      |                  |          |180755          |0      ".encode(),
            "总计      |                  |          |180755          |4      ".encode(),
        )
    )
    assert bonded != MAY_19

    members = parse_czce_warrants(bonded, business_date=date(2026, 5, 19), symbol="TA")

    (changjiang,) = (m for m in members if m.warehouse == "长江国际")
    assert changjiang.registered_receipts == 1180


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            ("|仓单数量(完税)  |仓单数量(保税)  |", "|仓单数量  |仓单数量(保税)  |"),
            "czce_warrant_header_mismatch",
        ),
        (("品种：PTA", "品种：精对苯二甲酸"), "czce_warrant_symbol_block_missing"),
        (
            (
                "总计      |                  |          |180755",
                "总计      |                  |          |180756",
            ),
            "czce_warrant_total_mismatch",
        ),
        (("(2026-05-19)", "(2026-05-20)"), "czce_warrant_date_mismatch"),
    ],
)
def test_a_changed_pta_block_is_refused_with_its_reason_and_cotton_still_reads(
    change: tuple[str, str], code: str
) -> None:
    old, new = change
    changed = MAY_19.replace(old.encode(), new.encode(), 1)
    assert changed != MAY_19

    with pytest.raises(ValueError, match=code):
        parse_czce_warrants(changed, business_date=date(2026, 5, 19), symbol="TA")
    if code != "czce_warrant_date_mismatch":
        assert parse_czce_warrants(changed, business_date=date(2026, 5, 19), symbol="CF")


def test_a_row_that_belongs_to_no_warehouse_is_refused() -> None:
    orphan = MAY_19.replace(
        "0314      |江阴协丰              |".encode(), b"          |                  |", 1
    )

    with pytest.raises(ValueError, match="czce_warrant_row_invalid"):
        parse_czce_warrants(orphan, business_date=date(2026, 5, 19), symbol="TA")
