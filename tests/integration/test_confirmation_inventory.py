"""The inventory quadrant and the registered warrants (ADR-0037, macro semantics ticket 08).

Demand (the PMI's new orders), production (industrial value added) and inventory (finished
goods' nominal growth) are read at the newest month all three hold, against the month
before it: demand and inventory name the quadrant, production verifies it, and anything
else is unclassified. The quadrant counts once for the inventory dimension; a card says
whether its member's data is there apart from the relation the quadrant bears. The real
inventory approximation is a rough proxy beside it, never counted nor read into it. The
registered warrants are a note: each symbol's warehouses summed, converted by the frozen
table, read as the median change and the breadth of rises and falls.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.confirmation import ConfirmationRules
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.lookback import declare
from pring_cycle.metric_contracts import warrant_provider
from pring_cycle.models import model_v0015_manifest
from pring_cycle.projections import validate_analytical_projection
from pring_cycle.registered_warrants import WarrantRules, registered_warrant_change
from pring_cycle.reports import report_input_from_projection
from tests.integration.test_confirmation_monthly_indicators import (
    AS_OF,
    METRICS,
    TARGET,
    append,
    indicator,
)
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_confirmation_publish import confirmed
from tests.integration.test_context_projection import _v2_manifest
from tests.web.test_dashboard_contract import _text

INVENTORY_METRICS = (
    "CN_INDUSTRIAL_FINANCE",
    "CN_FINISHED_GOODS_INVENTORY",
    "CN_PMI_INVENTORY",
    "CN_INVENTORY_TURNOVER",
    "CN_FUTURES_WARRANTS",
)
PMI = "diffusion_index_points"
# Each line's members, the main one first: (metric, dimensions, unit).
LINES: dict[str, tuple[tuple[str, dict[str, str], str], ...]] = {
    "demand": (
        ("CN_PMI_ACTIVITY", {"series": "new_orders", "measure": "level"}, PMI),
        ("CN_INDUSTRIAL_FINANCE", {"item": "revenue", "measure": "official_yoy"}, "percent"),
    ),
    "production": (
        ("CN_INDUSTRIAL_VA", {"measure": "current_month_real_yoy"}, "scalar"),
        ("CN_PMI_ACTIVITY", {"series": "production", "measure": "level"}, PMI),
    ),
    "inventory": (
        ("CN_FINISHED_GOODS_INVENTORY", {"measure": "official_yoy"}, "percent"),
        ("CN_PMI_INVENTORY", {"series": "finished_goods", "measure": "level"}, PMI),
        ("CN_INVENTORY_TURNOVER", {"measure": "official_yoy_change"}, "days"),
    ),
}
# The PMI and industrial value added are out to August on the target day; the industrial
# finance release, finished goods among it, to July: the lines' common month is July.
TO_AUGUST = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08")
TO_JULY = TO_AUGUST[:-1]
OUT_TO_AUGUST = frozenset({"CN_PMI_ACTIVITY", "CN_PMI_INVENTORY", "CN_INDUSTRIAL_VA"})
TRENDS = {
    "up": (50.0, 50.5, 51.0, 51.5, 52.0),
    "down": (52.0, 51.5, 51.0, 50.5, 50.0),
    "flat": (50.0, 50.0, 50.0, 50.0, 50.0),
    # Up to June, then down in July: one month of it.
    "down_in_july": (50.0, 50.5, 51.0, 50.5, 50.0),
    "up_in_july": (52.0, 51.5, 51.0, 51.5, 52.0),
}


def manifest() -> dict[str, Any]:
    return confirmation_manifest(_v2_manifest(*METRICS, *INVENTORY_METRICS))


def project(repository: EvidenceRepository, stage: FormalStage | None) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start="2026-04-01",
        model_manifest=manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
    )


def seed(
    repository: EvidenceRepository,
    demand: str,
    production: str,
    inventory: str,
    *,
    members: dict[str, tuple[float | None, ...]] | None = None,
) -> dict[str, list[str]]:
    """Each line's members alike along its trend, unless a member (by its dimensions'
    series, item or measure) is given its own values. Returns the claims by metric."""
    claims: dict[str, list[str]] = {}
    for line, trend in (("demand", demand), ("production", production), ("inventory", inventory)):
        for metric_id, dimensions, unit in LINES[line]:
            months = TO_AUGUST if metric_id in OUT_TO_AUGUST else TO_JULY
            name = dimensions.get("series") or dimensions.get("item") or dimensions["measure"]
            values = (members or {}).get(name, TRENDS[trend])
            claims.setdefault(metric_id, []).extend(
                append(
                    repository,
                    metric_id,
                    dimensions,
                    values[: len(months)],
                    months=months,
                    unit=unit,
                )
            )
    return claims


def quadrant(context: ContextProjection) -> dict[str, Any]:
    return indicator(context, "inventory_quadrant")


def read(tmp_path: Path, stage: FormalStage, *lines: str, **members: Any) -> dict[str, Any]:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, *lines, members=members or None)
    return quadrant(project(repository, stage))


@pytest.mark.parametrize(
    ("lines", "stage", "named", "relation"),
    [
        (("down", "down", "down"), FormalStage.STAGE_VI, "active_destocking", "support"),
        (("up", "up", "down"), FormalStage.STAGE_II, "passive_destocking", "support"),
        (("up", "up", "up"), FormalStage.STAGE_III, "active_restocking", "support"),
        (("down", "down", "up"), FormalStage.STAGE_V, "passive_restocking", "support"),
        # Production against demand does not verify a quadrant; nor does a line flat.
        (("up", "down", "down"), FormalStage.STAGE_I, "unclassified", "observation_only"),
        (("flat", "flat", "down"), FormalStage.STAGE_I, "unclassified", "observation_only"),
    ],
)
def test_demand_and_inventory_name_the_quadrant_and_production_verifies_it(
    tmp_path: Path, lines: tuple[str, str, str], stage: FormalStage, named: str, relation: str
) -> None:
    item = read(tmp_path, stage, *lines)

    main = item["members"][0]
    assert main["quadrant"] == named
    assert main["unclassified_by"] == (None if named != "unclassified" else "inconsistent")
    assert {line: value["direction"] for line, value in main["lines"].items()} == {
        "demand": lines[0],
        "production": lines[1],
        "inventory": lines[2],
    }
    assert item["relation"] == relation
    # The month all three hold: July, the PMI's August waiting on finished goods.
    assert item["statistical_period"] == "2026-07-31"
    assert item["consistency"] == "consistent"
    assert item["timing"] == "lagging"


def test_the_lines_are_read_at_the_month_all_three_hold(tmp_path: Path) -> None:
    # New orders fall in August, a month finished goods have not reached: July is read.
    item = read(
        tmp_path,
        FormalStage.STAGE_III,
        "up",
        "up",
        "up",
        new_orders=(50.0, 50.5, 51.0, 51.5, 40.0),
    )

    assert item["members"][0]["quadrant"] == "active_restocking"
    assert item["relation"] == "support"
    new_orders = next(m for m in item["members"] if m["name"] == "new_orders")
    assert new_orders["period"] == "2026-07-31" and new_orders["periods"] == [
        "2026-06-30",
        "2026-07-31",
    ]


def test_lines_not_holding_the_same_months_are_unclassified_and_say_what_is_missing(
    tmp_path: Path,
) -> None:
    # Finished goods miss June: July's direction is not known, and no older month stands in.
    item = read(
        tmp_path, FormalStage.STAGE_III, "up", "up", "up", official_yoy=(50.0, 50.5, None, 51.5)
    )

    main = item["members"][0]
    assert main["quadrant"] == "unclassified" and main["unclassified_by"] == "insufficient"
    assert item["relation"] == "unconfirmed"
    assert item["missing"] == ["inventory:measure=official_yoy:2026-06"]
    assert item["consistency"] == "unknown"


def test_a_line_missing_the_common_month_is_not_read_at_an_older_one(tmp_path: Path) -> None:
    # New orders hold June and August, not July: the quadrant's July is not known.
    item = read(
        tmp_path,
        FormalStage.STAGE_III,
        "up",
        "up",
        "up",
        new_orders=(50.0, 50.5, 51.0, None, 52.0),
    )

    assert item["relation"] == "unconfirmed"
    assert "demand:measure=level,series=new_orders:2026-07" in item["missing"]
    assert item["statistical_period"] == "2026-07-31"


def test_the_quadrant_counts_once_for_the_inventory_dimension(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "up", "up", "up")

    context = project(repository, FormalStage.STAGE_III)

    dimension = next(
        item
        for item in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
        if item["dimension"] == "inventory"
    )
    assert dimension["status"] == "connected"
    assert [item["key"] for item in dimension["key_indicators"]] == ["inventory_quadrant"]
    assert dimension["counts"] == {
        "support": 1,
        "counterevidence": 0,
        "observation_only": 0,
        "unconfirmed": 0,
        "not_applicable": 0,
    }
    # Its seven members are listed, each of its line, none counted on its own.
    members = dimension["key_indicators"][0]["members"]
    assert [(m["name"], m.get("line"), m["consistency"]) for m in members] == [
        ("quadrant", None, "main"),
        ("new_orders", "demand", "main"),
        ("revenue", "demand", "agrees"),
        ("industrial_va", "production", "main"),
        ("pmi_production", "production", "agrees"),
        ("finished_goods", "inventory", "main"),
        ("pmi_finished_goods", "inventory", "agrees"),
        ("turnover", "inventory", "agrees"),
    ]
    assert context.inventory["quadrant"] == "active_restocking"
    assert context.inventory["relation"] == "support"


def test_an_auxiliary_member_against_its_line_caps_the_quadrant(tmp_path: Path) -> None:
    # Stage III: active restocking, while the PMI's finished goods fall.
    item = read(tmp_path, FormalStage.STAGE_III, "up", "up", "up", finished_goods=TRENDS["down"])

    assert item["members"][0]["quadrant"] == "active_restocking"
    assert item["consistency"] == "divergent"
    assert item["divergence_capped"] is True
    assert item["relation"] == "observation_only"
    pmi = next(m for m in item["members"] if m["name"] == "pmi_finished_goods")
    assert pmi["consistency"] == "opposes"


def test_a_card_with_data_tells_its_availability_apart_from_the_relation(tmp_path: Path) -> None:
    # Stage III expects active restocking: July's active destocking is counterevidence
    # waiting on grace, one month of it.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "down_in_july", "down_in_july", "down_in_july")

    context = project(repository, FormalStage.STAGE_III)

    item = quadrant(context)
    assert item["members"][0]["quadrant"] == "active_destocking"
    assert item["relation"] == "observation_only"
    assert item["grace"]["past"] is False and item["grace"]["periods"] == 1
    cards = context.inventory["cards"]
    assert [card["name"] for card in cards] == [  # type: ignore[union-attr]
        "new_orders",
        "revenue",
        "industrial_va",
        "pmi_production",
        "finished_goods",
        "pmi_finished_goods",
        "turnover",
    ]
    for card in cards:  # type: ignore[union-attr]
        assert card["availability"] == "available"
        assert card["relation"] == "observation_only" != "support"
        assert card["counted"] is False
        assert "status" not in card


def test_a_cards_data_is_its_own_whatever_the_other_lines_hold(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "up", "up", "up", members={"official_yoy": (None, None, None, None)})

    context = project(repository, FormalStage.STAGE_III)

    item = quadrant(context)
    assert item["relation"] == "unconfirmed"
    assert "inventory:measure=official_yoy:missing" in item["missing"]
    cards = {card["name"]: card for card in context.inventory["cards"]}  # type: ignore[union-attr]
    assert cards["finished_goods"]["availability"] == "unavailable"
    # New orders are held and current, read at no common month: available all the same.
    assert cards["new_orders"]["availability"] == "available"
    assert cards["new_orders"]["period"] == "2026-08-31"
    assert cards["new_orders"]["reading_period"] is None
    assert {card["relation"] for card in cards.values()} == {"unconfirmed"}


def test_february_is_read_against_december_with_its_cumulative_growth(tmp_path: Path) -> None:
    # The lines meet at February: January passed over, the PMI's too, and industrial
    # value added's February its January-February cumulative growth.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    months = ("2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03")
    rising = (50.0, 50.5, 51.0, 60.0, 51.5, 52.0)
    for metric_id, dimensions, unit in (*LINES["demand"], *LINES["inventory"]):
        out = months if metric_id in OUT_TO_AUGUST else months[:-1]
        values = tuple(
            None if m.endswith("-01") and metric_id not in OUT_TO_AUGUST else v
            for m, v in zip(out, rising, strict=False)
        )
        append(repository, metric_id, dimensions, values, months=out, unit=unit)
    production, pmi_production = LINES["production"]
    append(
        repository, production[0], production[1], (5.0, 5.2, 5.4), months=months[:3], unit="scalar"
    )
    append(
        repository,
        production[0],
        {"measure": "ytd_real_yoy"},
        (5.6,),
        months=("2026-02",),
        unit="scalar",
    )
    append(repository, pmi_production[0], pmi_production[1], rising, months=months, unit=PMI)

    context = build_context_projection(
        repository,
        as_of=datetime(2026, 4, 1, tzinfo=UTC),
        target_business_date="2026-03-31",
        visible_evidence_start="2025-10-01",
        model_manifest=manifest(),
        formal_stage=StageResult(
            FormalStage.STAGE_III, FormalStage.STAGE_III, "canonical_combination"
        ),
    )

    item = quadrant(context)
    assert item["statistical_period"] == "2026-02-28"
    assert item["members"][0]["quadrant"] == "active_restocking"
    by_name = {member["name"]: member for member in item["members"]}
    # Against December: the PMI's January high is passed over.
    assert by_name["new_orders"]["periods"] == ["2025-12-31", "2026-02-28"]
    assert by_name["industrial_va"]["stand_ins"] == [
        {"period": "2026-02-28", "label": "1—2 月累计同比（累计口径）"}
    ]
    assert item["relation"] == "support"


def test_active_destocking_held_past_grace_is_counterevidence_to_stage_iv(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, FormalStage.STAGE_IV, "down", "down", "down")

    assert item["relation"] == "counterevidence"
    assert item["grace"]["past"] is True and item["grace"]["limit"] == 2
    assert item["turn"]["maturity"] == "confirmed"


def test_orders_up_with_production_not_following_is_told_as_repair_in_stage_vi(
    tmp_path: Path,
) -> None:
    item = read(tmp_path, FormalStage.STAGE_VI, "up", "down", "down")

    assert item["members"][0]["quadrant"] == "unclassified"
    assert item["relation"] == "observation_only"
    assert item["notes"] == ["修复过渡：订单回升而生产未跟"]


def test_the_real_inventory_approximation_is_neither_counted_nor_read_into_the_quadrant(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "up", "up", "up")
    # July's nominal finished goods and PPI: the approximation is derived for July.
    append(
        repository,
        "CN_FINISHED_GOODS_INVENTORY",
        {"measure": "nominal_end_level"},
        (105.0,),
        months=("2026-07",),
        unit="hundred_million_cny",
    )
    append(
        repository,
        "CN_PPI",
        {"category": "headline", "measure": "yoy"},
        (5.0,),
        months=("2026-07",),
    )

    context = project(repository, FormalStage.STAGE_III)

    proxy = context.inventory["real_inventory_approximation"]
    assert proxy["status"] == "available" and proxy["value"] == 100.0  # type: ignore[index]
    assert proxy["semantics"] == "rough_price_adjusted_proxy"  # type: ignore[index]
    assert proxy["counted"] is False and proxy["quadrant_input"] is False  # type: ignore[index]
    item = quadrant(context)
    read_from = {v for member in item["members"] for v in member["observation_version_ids"]}
    assert proxy["derived_observation_id"] not in read_from  # type: ignore[index]
    assert proxy["nominal_inventory"]["selected_claim_id"] not in read_from  # type: ignore[index]
    assert item["relation"] == "support"
    dimension = context.macro["confirmation"]["dimensions"][4]  # type: ignore[index]
    assert sum(dimension["counts"].values()) == 1


def test_the_quadrant_reads_each_line_back_from_its_own_newest_month() -> None:
    readings = {
        item.reading: item
        for item in declare(_rules())
        if item.reading.startswith("confirmation:inventory_quadrant")
    }
    assert sorted(readings) == [
        "confirmation:inventory_quadrant:finished_goods",
        "confirmation:inventory_quadrant:industrial_va",
        "confirmation:inventory_quadrant:industrial_va:stand_in:2",
        "confirmation:inventory_quadrant:new_orders",
        "confirmation:inventory_quadrant:pmi_finished_goods",
        "confirmation:inventory_quadrant:pmi_production",
        "confirmation:inventory_quadrant:revenue",
        "confirmation:inventory_quadrant:turnover",
    ]
    # The month and the one before, two of grace, two the PMI may wait on the others, and
    # the January passed over: seven months back from each line's newest, none a year on.
    finished = readings["confirmation:inventory_quadrant:finished_goods"]
    assert finished.periods.offsets == tuple(range(7))
    assert finished.unreleased_months == frozenset({1})
    assert finished.members == ({"measure": "official_yoy"},)
    orders = readings["confirmation:inventory_quadrant:new_orders"]
    assert orders.periods.offsets == tuple(range(7)) and orders.unreleased_months == {1}
    # The real inventory approximation is no line's.
    assert not any(item.metric_id == "CN_PPI" for item in readings.values())


def _rules() -> Any:
    from pring_cycle.context_projection import ContextProjectionRules

    return ContextProjectionRules.from_manifest(model_v0015_manifest())


# The model's frozen conversions.
WARRANTS = ConfirmationRules.from_manifest(model_v0015_manifest()).warrants  # type: ignore[union-attr]
DAYS = ("2026-09-11", "2026-09-14", "2026-09-15")


def held(**symbols: tuple[tuple[float | None, ...], str]) -> dict[str, Any]:
    """Each symbol's warehouses' totals on ``DAYS`` (None not held) and their unit."""
    return {
        symbol: {
            day: (value, unit, (f"{symbol}:{day}",))
            for day, value in zip(DAYS, values, strict=True)
            if value is not None
        }
        for symbol, (values, unit) in symbols.items()
    }


EVERY = {
    "CF": ((100.0, 100.0, 110.0), "sheet"),
    "TA": ((200.0, 200.0, 180.0), "sheet"),
    "PP": ((50.0, 55.0, 60.0), "lot"),
    "CU": ((1000.0, 1000.0, 1000.0), "tonne"),
    "RB": ((3000.0, 3100.0, 3300.0), "tonne"),
    "RU": ((400.0, 400.0, 380.0), "tonne"),
    "SP": ((800.0, 800.0, 840.0), "tonne"),
    "SC": ((5000.0, 5000.0, 4500.0), "barrel"),
}


def test_warrants_convert_by_the_frozen_table_and_read_the_median_and_breadth() -> None:
    assert WARRANTS is not None
    note = registered_warrant_change(WARRANTS, held(**EVERY), window=("2026-04-01", DAYS[-1]))

    by_symbol = {item["symbol"]: item for item in note["symbols"]}  # type: ignore[union-attr]
    # A CF sheet is 40 tonnes, a TA sheet and a PP lot 5; CU, RB, RU and SP are tonnes.
    assert (by_symbol["CF"]["first"], by_symbol["CF"]["last"]) == (4000.0, 4400.0)
    assert (by_symbol["TA"]["first"], by_symbol["TA"]["last"]) == (1000.0, 900.0)
    assert (by_symbol["PP"]["first"], by_symbol["PP"]["last"]) == (250.0, 300.0)
    assert (by_symbol["CU"]["first"], by_symbol["CU"]["factor"]) == (1000.0, 1.0)
    assert by_symbol["CF"]["weight_basis"] and by_symbol["CF"]["basis"]
    # Crude oil stays in barrels: in the breadth and the median, never in the tonnes.
    assert (by_symbol["SC"]["unit"], by_symbol["SC"]["last"]) == ("barrel", 4500.0)
    assert note["tonnes"] == {
        "symbols": ["CF", "TA", "PP", "CU", "RB", "RU", "SP"],
        "unit": "tonne",
        "first": 4000.0 + 1000.0 + 250.0 + 1000.0 + 3000.0 + 400.0 + 800.0,
        "last": 4400.0 + 900.0 + 300.0 + 1000.0 + 3300.0 + 380.0 + 840.0,
        "change": 400.0 - 100.0 + 50.0 + 0.0 + 300.0 - 20.0 + 40.0,
        "missing": [],
    }
    assert note["breadth"] == {"increase": 4, "flat": 1, "decrease": 3, "read": 8, "symbols": 8}
    # Rates: CF 0.1, TA -0.1, PP 0.2, CU 0, RB 0.1, RU -0.05, SP 0.05, SC -0.1.
    assert note["median_change_rate"] == pytest.approx(0.025)
    assert (note["first_day"], note["last_day"]) == (DAYS[0], DAYS[-1])
    assert note["counted"] is False and note["label"] == "注册库存变化"


def test_a_symbol_missing_a_day_is_not_filled_with_nothing() -> None:
    assert WARRANTS is not None
    # RB misses the newest day: every symbol is read to the last day all hold, never RB's
    # September 15 as nothing.
    symbols = {**EVERY, "RB": ((3000.0, 3100.0, None), "tonne")}
    note = registered_warrant_change(WARRANTS, held(**symbols), window=(None, DAYS[-1]))

    assert note["last_day"] == "2026-09-14"
    by_symbol = {item["symbol"]: item for item in note["symbols"]}  # type: ignore[union-attr]
    assert by_symbol["RB"]["change_rate"] == pytest.approx(100.0 / 3000.0)
    assert by_symbol["CF"]["direction"] == "flat"


def test_a_symbol_not_held_or_held_on_nothing_has_no_change_rate() -> None:
    assert WARRANTS is not None
    symbols = {key: value for key, value in EVERY.items() if key != "SP"}
    symbols["RU"] = ((0.0, 0.0, 30.0), "tonne")
    # A TA day delivered in lots is not a sheet: it is not read, nor converted otherwise.
    symbols["TA"] = ((200.0, 200.0, 180.0), "lot")
    note = registered_warrant_change(WARRANTS, held(**symbols), window=(None, DAYS[-1]))

    by_symbol = {item["symbol"]: item for item in note["symbols"]}  # type: ignore[union-attr]
    assert by_symbol["SP"]["status"] == "missing" and by_symbol["SP"]["change_rate"] is None
    assert by_symbol["TA"]["status"] == "unit_refused"
    assert by_symbol["TA"]["days_refused"] == list(DAYS)
    # A base of nothing rose, with no rate of its change.
    assert by_symbol["RU"]["status"] == "zero_base"
    assert by_symbol["RU"]["direction"] == "up" and by_symbol["RU"]["change_rate"] is None
    assert note["missing"] == ["TA:unit_refused", "RU:zero_base", "SP:missing"]
    assert note["breadth"]["read"] == 6 and note["breadth"]["increase"] == 4
    # The seven are not all read: no total of their tonnes.
    assert note["tonnes"]["first"] is None and note["tonnes"]["missing"] == ["TA", "SP"]


def test_a_day_outside_the_evidence_window_is_not_read() -> None:
    assert WARRANTS is not None
    # The window opens on September 14: the 11th is not the base, whatever is held.
    note = registered_warrant_change(WARRANTS, held(**EVERY), window=(DAYS[1], DAYS[-1]))

    assert note["first_day"] == DAYS[1]
    pp = next(item for item in note["symbols"] if item["symbol"] == "PP")  # type: ignore[union-attr]
    assert (pp["first"], pp["days_held"]) == (275.0, 2)
    # Nor after its end.
    closed = registered_warrant_change(WARRANTS, held(**EVERY), window=(None, DAYS[1]))
    assert closed["last_day"] == DAYS[1]


@pytest.mark.parametrize(
    "edit",
    [
        {"factor": float("nan")},
        {"factor": float("inf")},
        {"factor": 0},
        {"effective_from": "2026-9-1"},
        {"effective_from": "2026-W01-1"},
        {"effective_until": "20260930"},
        {"effective_from": "2026-10-01", "effective_until": "2026-09-30"},
        {"unit": "kilogram"},
    ],
)
def test_a_conversion_out_of_its_terms_is_refused(edit: dict[str, Any]) -> None:
    assert WARRANTS is not None
    document = {**_document(WARRANTS.conversions[0]), **edit}

    with pytest.raises(ValueError, match="confirmation_warrant_conversions_invalid"):
        WarrantRules.parse([document])


def test_a_conversion_holds_only_where_its_terms_do() -> None:
    assert WARRANTS is not None
    # CF's sheet became 50 tonnes from September 14 (a term changed): each day converts
    # by the term in force on it.
    changed = WarrantRules(
        tuple(
            replacement
            for item in WARRANTS.conversions
            for replacement in (
                (
                    replace(item, effective_until="2026-09-13"),
                    replace(item, factor=50.0, effective_from="2026-09-14"),
                )
                if item.symbol == "CF"
                else (item,)
            )
        )
    )
    note = registered_warrant_change(changed, held(**EVERY), window=(None, DAYS[-1]))

    cf = next(item for item in note["symbols"] if item["symbol"] == "CF")  # type: ignore[union-attr]
    assert (cf["first"], cf["last"], cf["factor"]) == (4000.0, 5500.0, 50.0)
    with pytest.raises(ValueError, match="confirmation_warrant_conversions_overlap"):
        WarrantRules.parse(
            [
                *(
                    {**_document(item), "effective_from": None}
                    for item in changed.conversions
                    if item.symbol == "CF"
                ),
            ]
        )


def _document(item: Any) -> dict[str, Any]:
    return {
        "symbol": item.symbol,
        "input_unit": item.input_unit,
        "factor": item.factor,
        "unit": item.unit,
        "weight_basis": item.weight_basis,
        "basis": item.basis,
        "effective_from": item.effective_from,
        "effective_until": item.effective_until,
    }


def append_warrant(
    repository: EvidenceRepository,
    symbol: str,
    warehouse: str,
    day: str,
    value: float,
    unit: str,
) -> str:
    public = AS_OF.replace(month=int(day[5:7]), day=int(day[8:10]))
    return repository.append_source_claim(
        SourceClaimInput(
            metric_id="CN_FUTURES_WARRANTS",
            definition_version="metric-catalog-v0002",
            period_kind="business_day",
            period_start=day,
            period_end=day,
            dimensions={
                "symbol": symbol,
                "warehouse": warehouse,
                "exchange": "fixture",
                "measure": "registered_receipts",
            },
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=unit,
            # CZCE's own report for CF and TA, TuShare's taken no more (ADR-0032).
            provider=warrant_provider(symbol),
            source_reference=f"fixture:warrant:{symbol}:{warehouse}:{day}",
            release_event_id=f"release:warrant:{symbol}:{day}",
            release_at=public,
            public_available_at=public,
            fetched_at=public,
            available_at=public,
            certification_status="certified",
            quality_status="validated",
        )
    ).claim_id


def test_the_warrant_note_sums_each_symbols_warehouses_in_the_evidence_window(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "up", "up", "up")
    # Two warehouses of CF and of CU, summed day by day; a day before the window is not
    # read.
    claims: dict[tuple[str, str, str], str] = {}
    for day, (first, second) in zip(DAYS, ((10.0, 5.0), (10.0, 5.0), (12.0, 6.0)), strict=True):
        for symbol, unit, scale in (("CF", "sheet", 1.0), ("CU", "tonne", 100.0)):
            for warehouse, value in (("A", first), ("B", second)):
                claims[(symbol, warehouse, day)] = append_warrant(
                    repository, symbol, warehouse, day, scale * value, unit
                )
    append_warrant(repository, "CF", "A", "2026-03-31", 1.0, "sheet")
    # A day of RB's warehouses delivered in two units is held in neither.
    append_warrant(repository, "RB", "A", DAYS[0], 10.0, "tonne")
    append_warrant(repository, "RB", "B", DAYS[0], 10.0, "lot")

    context = project(repository, FormalStage.STAGE_III)

    note: Any = context.inventory["registered_warrants"]
    cf = next(item for item in note["symbols"] if item["symbol"] == "CF")
    assert (cf["first"], cf["last"]) == (600.0, 720.0)
    assert (note["window_start"], note["first_day"]) == ("2026-04-01", "2026-09-11")
    assert note["breadth"]["increase"] == 2 and note["counted"] is False
    assert sorted(note["missing"]) == [
        "PP:missing",
        "RB:unit_refused",
        "RU:missing",
        "SC:missing",
        "SP:missing",
        "TA:missing",
    ]
    # Only the first and last day read are what the note rests on.
    assert sorted(note["observation_version_ids"]) == sorted(
        claims[(symbol, warehouse, day)]
        for symbol in ("CF", "CU")
        for warehouse in ("A", "B")
        for day in (DAYS[0], DAYS[-1])
    )
    # The note is no key indicator's: the dimension still counts the quadrant alone.
    dimension = context.macro["confirmation"]["dimensions"][4]  # type: ignore[index]
    assert sum(dimension["counts"].values()) == 1


def test_the_inventory_page_and_the_report_carry_the_quadrant_and_the_warrant_note(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed(repository, "up", "up", "up")
    claims = [
        append_warrant(repository, "CF", "A", day, value, "sheet")
        for day, value in zip(DAYS, (10.0, 10.0, 12.0), strict=True)
    ]
    context = project(repository, FormalStage.STAGE_III)
    # A published stage III set, its macro and inventory read from this evidence.
    published = confirmed(tmp_path / "run")
    projection = replace(
        published,
        datasets={**published.datasets, "macro": context.macro, "inventory": context.inventory},
    )

    # Section 05: the quadrant and its relation on the page, the warrant table and the real
    # inventory approximation in the drawer the warrant line opens (cockpit layout ticket 06).
    page = " ".join(_text(dashboard_page("/", projection, (), ())).split())
    assert (
        "库存象限 主动补库存 统计期 2026-07-31 需求上升、生产上升、库存上升 "
        "确认关系：支持（象限仅计一项）"
    ) in page
    assert "需求 PMI 新订单" in page and "数据 可用" in page
    assert "注册仓单（附注，不计数） 8 个品种 · 最新期 2026-09-15" in page
    assert "变化率中位数 20.0%" in page
    assert "棉花 400 → 480 吨 +20.0% 每张 40 吨（公定重量（名义））" in page
    assert "原油 — 窗口内未持有 每桶 1 桶（净体积桶）" in page
    assert "实际库存近似（粗略价格调整代理）" in page and "不参与库存象限" in page
    bundle = report_input_from_projection(projection)
    assert bundle.conclusions["dimension:inventory"]["support"] == 1
    assert bundle.conclusions["key_indicator:inventory_quadrant"] == "support"
    reading = bundle.results["confirmation"]["key_indicators"]["inventory_quadrant"]
    assert reading["members"][0]["quadrant"] == "active_restocking"
    assert reading["members"][1]["line"] == "demand"
    notes = bundle.results["confirmation"]["inventory"]
    assert notes["registered_warrants"]["median_change_rate"] == pytest.approx(0.2)
    assert "observation_version_ids" not in notes["registered_warrants"]
    # The first and last day's figures are told; the claims they were read from are not.
    (cotton,) = (item for item in notes["registered_warrants"]["symbols"] if item["symbol"] == "CF")
    assert (cotton["first"], cotton["last"]) == (400.0, 480.0)
    assert cotton["change_rate"] == pytest.approx(0.2)
    assert not {"first_claim_ids", "last_claim_ids"} & set(cotton)
    assert not any(claim in json.dumps(bundle.prompt_document()) for claim in claims)
    assert notes["cards"][0] == {
        "label": "需求：PMI 新订单",
        "line": "demand",
        "availability": "available",
        "evidence_status": "current",
        "relation": "support",
    }
    assert notes["real_inventory_approximation"]["counted"] is False


@pytest.mark.parametrize(
    "edit",
    [
        # The seven cards' support for data held is not published in its place.
        lambda card: card.update(status="support"),
        lambda card: card.update(relation="support"),
        lambda card: card.update(availability=True),
        lambda card: card.update(availability=[]),
        lambda card: card.update(counted=True),
    ],
)
def test_a_card_telling_more_than_its_data_and_the_quadrant_is_not_published(
    tmp_path: Path, edit: Any
) -> None:
    projection = confirmed(tmp_path)
    datasets = copy.deepcopy(projection.datasets)
    edit(datasets["inventory"]["cards"][0])

    with pytest.raises(ValueError, match="projection_confirmation_inventory_card_invalid"):
        validate_analytical_projection(projection.envelope, datasets)


@pytest.mark.parametrize("cards", [None, []])
def test_a_connected_inventory_dimension_without_its_cards_is_not_published(
    tmp_path: Path, cards: list[Any] | None
) -> None:
    projection = confirmed(tmp_path)
    datasets = copy.deepcopy(projection.datasets)
    if cards is None:
        del datasets["inventory"]["cards"]
    else:
        datasets["inventory"]["cards"] = cards

    with pytest.raises(ValueError, match="projection_confirmation_inventory_card_invalid"):
        validate_analytical_projection(projection.envelope, datasets)
