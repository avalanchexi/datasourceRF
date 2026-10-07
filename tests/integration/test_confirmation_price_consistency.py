"""Price internal consistency, observation interfaces and the commodity supply-demand note
(ADR-0037, macro semantics ticket 09).

Prices of the cores' own kind hang under their core as observation interfaces, shown and
never counted; NHII is the commodity core, no evidence of prices. The three cores' 120-
session relative momentum needs 121 actual prices aligned on SSE sessions; with fewer it is
unconfirmed. Breadth says a move is broad or rests on fewer shares, never on sectors or
weights; the basket's sleeves say whether a move is broad. Each stage's expectations give
where the cores stand and any turn they hint. In stages III to V a note tests whether
demand bears out the commodity rise: it never names what drives it.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle import breadth
from pring_cycle.breadth import BREADTH_METRICS
from pring_cycle.confirmation import ConfirmationRules
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository, model_v0015_manifest
from pring_cycle.price_consistency import CorePrices
from pring_cycle.projections import validate_analytical_projection
from pring_cycle.reports import (
    AdapterResponse,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.tushare_context import MARKET_INDEX_IDENTITIES
from tests.integration.test_confirmation_monthly_indicators import YEAR, append
from tests.integration.test_confirmation_monthly_indicators import manifest as monthly_manifest
from tests.integration.test_confirmation_publish import _document, confirmed
from tests.integration.test_worker_execution import runtime
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text

VERSION = "metric-catalog-v0006"
TARGET = "2026-09-15"
AS_OF = datetime(2026, 9, 16, tzinfo=UTC)
# A weekday holiday inside the 121 sessions: no session, so no price is owed for it.
HOLIDAYS = frozenset(
    date.fromisoformat(day) for day in ("2026-05-01", "2026-05-04", "2026-05-05", "2026-06-19")
)
SESSIONS = tuple(
    day.isoformat()
    for day in (date(2025, 6, 2) + timedelta(days=offset) for offset in range(500))
    if day.weekday() < 5 and day not in HOLIDAYS and day <= date(2026, 9, 30)
)
CALENDAR = TradingCalendar(
    tuple(date.fromisoformat(day) for day in SESSIONS), through=date(2026, 9, 30)
)
# The 121 sessions to the target day: the 120-session evidence window and the one before.
SPAN = tuple(day for day in SESSIONS if day <= TARGET)[-121:]
WINDOW_START = SPAN[1]
CORES = {
    "bond": "CN_BOND_CORE_000012",
    "stock": "CN_EQUITY_CORE_000985",
    "commodity": "CN_COMMODITY_CORE_NHII",
}
SLEEVES = ("copper", "rebar", "polypropylene", "textiles", "rubber", "pulp", "crude_oil")
BASKET = "ex-hog-calendar-settlement-v0003"
BREADTH = {"measure": "above_ma_share", "universe": "point_in_time_traded_a_shares"}
# Observation interfaces, by core (CONTEXT.md 观察接口).
INTERFACES = {
    "bond": {"CN_BOND_10Y_930916", "CN_BOND_FULL_PRICE_CNY030"},
    "stock": {
        "CN_EQ_CSI300",
        "CN_EQ_CSI500",
        "CN_EQ_CSI1000",
        "CN_EQ_ADV_DEC",
        "CN_EQ_AD_RATIO",
        "CN_EQ_ADV_AMOUNT_SHARE",
        "CN_EQ_NEW_HIGH_LOW_90",
        "CN_EQ_NEW_HIGH_LOW_250",
        "CN_EQ_ABOVE_MA90",
        "CN_EQ_ABOVE_MA250",
        "CN_INDEX_VALUATION",
        "CN_MARGIN_BALANCE_SSE_SZSE",
    },
    "commodity": {
        "CN_COMMODITY_BROAD_NHCI",
        "CN_COMMODITY_EX_HOG_BASKET",
        "CN_COMMODITY_SLEEVE_CONTRIBUTION",
        "EIA_WTI_RWTC",
        "EIA_BRENT_RBRTE",
    },
}
# What breadth or a basket reading may never say: it reads all shares, never sectors or weights.
FORBIDDEN = ("行业", "板块", "权重", "大盘股", "龙头")


def registered(tmp_path: Path) -> tuple[RuntimePaths, EvidenceRepository]:
    paths = runtime(tmp_path)
    ModelRepository(paths.database).register(model_v0015_manifest())
    return paths, EvidenceRepository(paths.database)


def registered_manifest(repository: EvidenceRepository) -> dict[str, Any]:
    """v0015 as it was registered: the manifest a projection must be bound to."""
    return ModelRepository(repository.database_path).manifest("model-v0015")


def claim(
    repository: EvidenceRepository,
    metric_id: str,
    day: str,
    dimensions: dict[str, str],
    value: float,
    *,
    unit: str,
) -> str:
    """One claim as its registered source contract delivers it (TuShare's own)."""
    if metric_id in MARKET_INDEX_IDENTITIES:
        api_name, code = MARKET_INDEX_IDENTITIES[metric_id]
        dimensions, reference = {"source_code": code}, f"tushare:{api_name}:close:{day}"
    elif metric_id in BREADTH_METRICS:
        field = breadth.source_field(metric_id, dimensions["measure"])
        reference = f"tushare:breadth:{field}:{day}"
    else:
        reference = f"tushare:commodity_basket:{dimensions['sleeve']}:{day}"
    public = datetime.combine(date.fromisoformat(day), datetime.min.time(), tzinfo=UTC)
    return repository.append_source_claim(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version=VERSION,
            period_kind="business_day",
            period_start=day,
            period_end=day,
            dimensions=dimensions,
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=unit,
            provider="tushare",
            source_reference=reference,
            release_event_id=f"release:{metric_id}:{sorted(dimensions.items())}:{day}",
            release_at=public + timedelta(hours=10),
            public_available_at=public + timedelta(hours=10),
            fetched_at=public + timedelta(hours=10),
            available_at=public + timedelta(hours=10),
            certification_status="certified",
            quality_status="validated",
        )
    ).claim_id


def closes(start: float, end: float, days: Iterable[str] = SPAN) -> tuple[tuple[str, float], ...]:
    """Prices along ``days`` from ``start`` to ``end``, evenly."""
    days = tuple(days)
    step = (end - start) / (len(days) - 1)
    return tuple((day, start + step * index) for index, day in enumerate(days))


def cores(
    bond: tuple[float, float] | CorePrices = (100.0, 110.0),
    stock: tuple[float, float] | CorePrices = (100.0, 105.0),
    commodity: tuple[float, float] | CorePrices = (100.0, 100.0),
) -> dict[str, CorePrices]:
    """Each core's 121 actual closes, from its first to its last value, unless given."""
    return {
        asset: given
        if isinstance(given, CorePrices)
        else CorePrices(asset, CORES[asset], "validated", closes(*given))
        for asset, given in (("bond", bond), ("stock", stock), ("commodity", commodity))
    }


def project(
    repository: EvidenceRepository,
    stage: FormalStage | None,
    core_prices: dict[str, CorePrices] | None = None,
    *,
    manifest: dict[str, Any] | None = None,
) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start=WINDOW_START,
        model_manifest=manifest or registered_manifest(repository),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
        calendar=CALENDAR,
        core_prices=cores() if core_prices is None else core_prices,
    )


def consistency(context: ContextProjection) -> dict[str, Any]:
    return context.macro["price_consistency"]  # type: ignore[return-value]


def pairs(context: ContextProjection) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in consistency(context)["relative_momentum"]}


def texts(value: object) -> list[str]:
    """Every string a document holds, however deep."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in texts(item)]
    return []


def counted_metrics(context: ContextProjection) -> set[str]:
    """Every metric a key indicator's member reads: what confirmation counts."""
    confirmation = context.macro["confirmation"]
    metrics: set[str] = set()
    for dimension in confirmation["dimensions"]:  # type: ignore[index]
        for indicator in dimension["key_indicators"]:
            metrics.add(indicator["metric_id"])
            metrics.update(str(member.get("metric_id")) for member in indicator["members"])
    return metrics


# Observation interfaces.


def test_observation_interfaces_hang_under_their_cores_and_are_never_counted(
    tmp_path: Path,
) -> None:
    _paths, repository = registered(tmp_path)
    for day, value in zip(SPAN[-2:], (101.0, 101.5), strict=True):
        claim(repository, "CN_BOND_10Y_930916", day, {}, value, unit="index_points")
    claim(repository, "CN_COMMODITY_BROAD_NHCI", TARGET, {}, 1500.0, unit="index_points")

    context = project(repository, FormalStage.STAGE_III)

    interfaces = context.macro["observation_interfaces"]
    assert interfaces["counted"] is False  # type: ignore[index]
    by_core = {item["core"]: item for item in interfaces["cores"]}  # type: ignore[index]
    assert {core: item["core_metric_id"] for core, item in by_core.items()} == CORES
    for core, metrics in INTERFACES.items():
        assert {member["metric_id"] for member in by_core[core]["members"]} == metrics
        assert all(member["counted"] is False for member in by_core[core]["members"])
    # None of them, nor any core, is read by a key indicator.
    shown = set().union(*INTERFACES.values(), CORES.values())
    assert not shown & counted_metrics(context)
    # 930916 is a bond price: its rise is a stronger price, never a yield.
    bond = next(m for m in by_core["bond"]["members"] if m["metric_id"] == "CN_BOND_10Y_930916")
    assert bond["reads_as"] == "bond_price"
    assert [row["period"] for row in bond["evidence"]] == [TARGET]


def test_nhii_and_the_cores_own_kinds_are_no_evidence_of_prices_or_transmission(
    tmp_path: Path,
) -> None:
    _paths, repository = registered(tmp_path)

    context = project(repository, FormalStage.STAGE_III)

    price = {row["metric_id"] for row in context.macro["price_chain"]["evidence"]}  # type: ignore[index]
    assert price == {"CN_PMI_PRICES", "CN_PPI", "CN_CPI_HEADLINE", "CN_CORE_CPI"}
    transmission = {
        row["metric_id"]
        for row in context.macro["transmission"]["evidence"]  # type: ignore[index]
    }
    assert not transmission & INTERFACES["bond"]


def test_an_observation_interface_member_cannot_be_a_key_indicator_s(tmp_path: Path) -> None:
    manifest = model_v0015_manifest()
    rules = copy.deepcopy(manifest["confirmation_rules"])
    ppi = next(item for item in rules["key_indicators"] if item["key"] == "ppi")
    ppi["auxiliary"].append(
        {
            "name": "nhci",
            "label": "南华综合",
            "metric_id": "CN_COMMODITY_BROAD_NHCI",
            "dimensions": {},
        }
    )
    manifest["confirmation_rules"] = rules

    with pytest.raises(ValueError, match="confirmation_observation_interface_counted"):
        ConfirmationRules.from_manifest(manifest)


def _refused(change: Any) -> None:
    manifest = model_v0015_manifest()
    rules = copy.deepcopy(manifest["confirmation_rules"])
    change(rules)
    manifest["confirmation_rules"] = rules
    with pytest.raises(ValueError, match="confirmation_price_rules_invalid"):
        ConfirmationRules.from_manifest(manifest)


def test_price_rules_need_every_text_they_say() -> None:
    _refused(lambda rules: rules["supply_demand"].update(texts={}))
    _refused(lambda rules: rules["price_consistency"]["stock_breadth"]["texts"].pop("even"))


@pytest.mark.parametrize("line", [float("nan"), float("inf"), True, "50"])
def test_the_breadth_line_is_a_finite_number(line: object) -> None:
    _refused(lambda rules: rules["price_consistency"]["stock_breadth"].update(line=line))


def test_a_sleeve_is_read_once() -> None:
    _refused(lambda rules: rules["price_consistency"]["basket_breadth"]["sleeves"].append("copper"))


@pytest.mark.parametrize("block", ["observation_interfaces", "price_consistency", "supply_demand"])
def test_the_three_blocks_come_together(block: str) -> None:
    _refused(lambda rules: rules.pop(block))


def test_breadth_and_the_basket_are_read_of_observation_interfaces() -> None:
    def drop(rules: dict[str, Any]) -> None:
        stock = next(item for item in rules["observation_interfaces"] if item["core"] == "stock")
        stock["members"] = [m for m in stock["members"] if m["metric_id"] != "CN_EQ_ABOVE_MA90"]

    _refused(drop)


# Relative momentum.


def test_relative_momentum_is_the_difference_of_120_session_returns(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)

    context = project(repository, FormalStage.STAGE_I)

    document = consistency(context)
    assert document["counted"] is False
    assert (document["first_session"], document["last_session"]) == (SPAN[0], TARGET)
    returns = {item["asset"]: item["return_pct"] for item in document["cores"]}
    assert returns == pytest.approx({"bond": 10.0, "stock": 5.0, "commodity": 0.0})
    read = pairs(context)
    assert {key: item["value_pp"] for key, item in read.items()} == pytest.approx(
        {"commodity_vs_bond": -10.0, "stock_vs_bond": -5.0, "stock_vs_commodity": 5.0}
    )
    assert {key: item["direction"] for key, item in read.items()} == {
        "commodity_vs_bond": "down",
        "stock_vs_bond": "down",
        "stock_vs_commodity": "up",
    }
    assert all(item["status"] == "read" for item in read.values())


def test_fewer_than_121_actual_prices_leave_a_pair_unconfirmed(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)
    short = CorePrices("bond", CORES["bond"], "validated", closes(100.0, 110.0)[1:])
    gap = CorePrices(
        "commodity",
        CORES["commodity"],
        "validated",
        tuple(item for item in closes(100.0, 90.0) if item[0] != SPAN[60]),
    )

    read = pairs(project(repository, FormalStage.STAGE_I, cores(bond=short, commodity=gap)))

    assert read["stock_vs_bond"]["status"] == "unconfirmed"
    assert read["stock_vs_bond"]["value_pp"] is None
    assert read["stock_vs_bond"]["missing"] == [f"bond:{SPAN[0]}"]
    assert read["commodity_vs_bond"]["missing"] == [f"bond:{SPAN[0]}", f"commodity:{SPAN[60]}"]
    assert read["stock_vs_commodity"]["missing"] == [f"commodity:{SPAN[60]}"]


def test_prices_align_on_sse_sessions_not_on_weekdays(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)

    document = consistency(project(repository, FormalStage.STAGE_I))

    # The 121 sessions skip the May and June holidays: the span starts further back than
    # 121 weekdays would, and no price is owed on a holiday.
    weekdays = [
        day.isoformat()
        for day in (date.fromisoformat(TARGET) - timedelta(days=offset) for offset in range(200))
        if day.weekday() < 5
    ]
    assert document["first_session"] < weekdays[120]
    assert "2026-05-01" not in SPAN
    assert all(item["status"] == "read" for item in document["relative_momentum"])


def test_a_core_carried_forward_has_no_actual_price_on_the_target_day(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)
    carried = CorePrices(
        "stock", CORES["stock"], "carried_forward_one_session", closes(100.0, 105.0)[:-1]
    )

    read = pairs(project(repository, FormalStage.STAGE_II, cores(stock=carried)))

    assert read["stock_vs_bond"]["status"] == "unconfirmed"
    assert read["stock_vs_bond"]["missing"] == [
        "stock:carried_forward_one_session",
        f"stock:{TARGET}",
    ]
    assert read["commodity_vs_bond"]["status"] == "read"


def test_a_core_failing_its_gate_gives_no_prices(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)
    blocked = CorePrices("bond", CORES["bond"], "source_conflict", ())

    read = pairs(project(repository, FormalStage.STAGE_I, cores(bond=blocked)))

    assert read["commodity_vs_bond"]["missing"] == ["bond:source_conflict"]
    assert read["stock_vs_commodity"]["status"] == "read"


def test_without_the_calendar_s_sessions_nothing_is_aligned(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)

    document = consistency(
        build_context_projection(
            repository,
            as_of=AS_OF,
            target_business_date=TARGET,
            visible_evidence_start=WINDOW_START,
            model_manifest=registered_manifest(repository),
            formal_stage=StageResult(FormalStage.STAGE_I, FormalStage.STAGE_I, "x"),
            calendar=TradingCalendar(),
            core_prices=cores(),
        )
    )

    assert document["first_session"] is None
    assert all(
        item["missing"] == ["trading_calendar_incomplete"] for item in document["relative_momentum"]
    )


# Each stage's expected position and turn hints (expectation-table.md).
# (bond, stock, commodity) returns, what the stage expects, whether the cores bear it out,
# and the stages a turn hint points to.
POSITIONS = [
    # I: bonds strongest; commodities already rising against bonds hints II or III.
    (FormalStage.STAGE_I, (10.0, 5.0, 0.0), True, []),
    (FormalStage.STAGE_I, (2.0, 0.0, 6.0), False, [["stage_ii", "stage_iii"]]),
    # II: stocks against commodities and bonds up, commodities against bonds still weak.
    (FormalStage.STAGE_II, (5.0, 10.0, 0.0), True, []),
    (FormalStage.STAGE_II, (5.0, 0.0, 10.0), False, []),
    # III: commodities stronger than bonds.
    (FormalStage.STAGE_III, (2.0, 5.0, 8.0), True, []),
    # IV: bonds weakest.
    (FormalStage.STAGE_IV, (-5.0, 5.0, 8.0), True, []),
    (FormalStage.STAGE_IV, (5.0, 0.0, 8.0), False, []),
    # V: commodities strongest, stocks against commodities down.
    (FormalStage.STAGE_V, (-5.0, -2.0, 8.0), True, []),
    # VI: all three weak; bonds rising against commodities hints I.
    (FormalStage.STAGE_VI, (-1.0, -5.0, -3.0), True, [["stage_i"]]),
    (FormalStage.STAGE_VI, (-5.0, -6.0, -1.0), True, []),
]


@pytest.mark.parametrize(("stage", "returns", "agrees", "toward"), POSITIONS)
def test_each_stage_says_where_the_cores_stand_and_where_they_turn(
    tmp_path: Path,
    stage: FormalStage,
    returns: tuple[float, float, float],
    agrees: bool,
    toward: list[list[str]],
) -> None:
    _paths, repository = registered(tmp_path)
    bond, stock, commodity = ((100.0, 100.0 + item) for item in returns)

    position = consistency(
        project(repository, stage, cores(bond=bond, stock=stock, commodity=commodity))
    )["position"]

    assert position["applicable"] is True
    assert position["stage"] == stage.value
    assert position["text"]
    assert position["agrees"] is agrees
    assert all(item["observed"] is not None for item in position["expected"])
    assert [hint["toward"] for hint in position["turn_hints"]] == toward


def test_a_non_canonical_combination_reads_the_momentum_and_places_nothing(
    tmp_path: Path,
) -> None:
    _paths, repository = registered(tmp_path)

    document = consistency(project(repository, None))

    assert document["position"] == {
        "applicable": False,
        "stage": None,
        "text": None,
        "expected": [],
        "agrees": None,
        "turn_hints": [],
        "notes": [],
    }
    assert all(item["status"] == "read" for item in document["relative_momentum"])


# Breadth: of all shares, broad or on fewer of them, never sectors or weights.


@pytest.mark.parametrize(
    ("stock", "share", "reading", "text"),
    [
        ((100.0, 110.0), 62.0, "broad_rise", "上涨普遍"),
        ((100.0, 110.0), 38.0, "narrow_rise", "上涨集中于较少个股"),
        ((100.0, 90.0), 30.0, "broad_fall", "下跌普遍"),
        ((100.0, 90.0), 58.0, "narrow_fall", "下跌集中于较少个股"),
    ],
)
def test_breadth_says_a_move_is_broad_or_rests_on_fewer_shares(
    tmp_path: Path, stock: tuple[float, float], share: float, reading: str, text: str
) -> None:
    _paths, repository = registered(tmp_path)
    claim(repository, "CN_EQ_ABOVE_MA90", TARGET, BREADTH, share, unit="percent")

    breadth = consistency(project(repository, FormalStage.STAGE_IV, cores(stock=stock)))[
        "stock_breadth"
    ]

    assert (breadth["status"], breadth["reading"], breadth["text"]) == ("read", reading, text)
    assert breadth["share"] == share and breadth["line"] == 50
    assert not any(word in item for item in texts(breadth) for word in FORBIDDEN)


def test_a_rise_on_fewer_shares_in_stage_ii_doubts_how_firm_the_stage_is(
    tmp_path: Path,
) -> None:
    _paths, repository = registered(tmp_path)
    claim(repository, "CN_EQ_ABOVE_MA90", TARGET, BREADTH, 40.0, unit="percent")

    position = consistency(project(repository, FormalStage.STAGE_II, cores(stock=(100.0, 112.0))))[
        "position"
    ]

    assert position["notes"] == ["上涨集中于较少个股，阶段稳固度存疑"]


def test_breadth_not_held_for_the_target_day_is_unconfirmed(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)
    claim(repository, "CN_EQ_ABOVE_MA90", SPAN[-2], BREADTH, 60.0, unit="percent")

    breadth = consistency(project(repository, FormalStage.STAGE_III))["stock_breadth"]

    assert breadth["status"] == "unconfirmed"
    assert breadth["reading"] is None
    assert breadth["missing"] == [f"CN_EQ_ABOVE_MA90:{TARGET}"]


# The basket's sleeves: a move broad, or resting on one sleeve or a few.


def seed_sleeves(
    repository: EvidenceRepository,
    contributions: dict[str, float],
    *,
    skip: tuple[str, str] | None = None,
) -> None:
    """Each sleeve's daily contribution on each of the 120 sessions the return spans."""
    for day in SPAN[1:]:
        for sleeve, value in contributions.items():
            if (sleeve, day) == skip:
                continue
            claim(
                repository,
                "CN_COMMODITY_SLEEVE_CONTRIBUTION",
                day,
                {"formula_version": BASKET, "sleeve": sleeve},
                value,
                unit="percentage_points",
            )


@pytest.mark.parametrize(
    ("signs", "reading", "text"),
    [
        ((1, 1, 1, 1, 1, -1, 1), "broad_rise", "上涨普遍"),
        ((-1, -1, -1, -1, -1, -1, 9), "single_sleeve_rise", "上涨集中于单一分项"),
        ((1, 1, -1, -1, -1, -1, 9), "few_sleeves_rise", "上涨集中于少数分项"),
        ((-1, -1, -1, -1, 1, -1, -1), "broad_fall", "下跌普遍"),
    ],
)
def test_the_basket_s_sleeves_say_how_broad_its_move_is(
    tmp_path: Path, signs: tuple[int, ...], reading: str, text: str
) -> None:
    _paths, repository = registered(tmp_path)
    seed_sleeves(repository, {s: 0.01 * n for s, n in zip(SLEEVES, signs, strict=True)})

    basket = consistency(project(repository, FormalStage.STAGE_III))["basket_breadth"]

    assert (basket["status"], basket["reading"], basket["text"]) == ("read", reading, text)
    assert basket["of"] == 7
    assert {item["sleeve"] for item in basket["sleeves"]} == set(SLEEVES)
    assert not any(word in item for item in texts(basket) for word in FORBIDDEN)


def test_the_basket_compounds_its_days_as_its_level_does(tmp_path: Path) -> None:
    # Up 10% one day and down 9.5% the next: the sum of the days is up, the basket down.
    _paths, repository = registered(tmp_path)
    days = {SPAN[1]: 10.0, SPAN[2]: -9.5}
    for day in SPAN[1:]:
        for sleeve in SLEEVES:
            value = days.get(day, 0.0) if sleeve == "copper" else 0.0
            claim(
                repository,
                "CN_COMMODITY_SLEEVE_CONTRIBUTION",
                day,
                {"formula_version": BASKET, "sleeve": sleeve},
                value,
                unit="percentage_points",
            )

    basket = consistency(project(repository, FormalStage.STAGE_VI))["basket_breadth"]

    assert basket["direction"] == "down"
    assert basket["return_pct"] == pytest.approx(-0.45)
    copper = next(item for item in basket["sleeves"] if item["sleeve"] == "copper")
    assert copper["direction"] == "up"
    # No sleeve summed as the basket compounded: said so, never a fall on a few of them.
    assert (basket["along"], basket["reading"]) == (0, "unaligned")


def test_a_sleeve_s_session_not_held_leaves_the_basket_unconfirmed(tmp_path: Path) -> None:
    _paths, repository = registered(tmp_path)
    seed_sleeves(repository, dict.fromkeys(SLEEVES, 0.01), skip=("pulp", SPAN[40]))

    basket = consistency(project(repository, FormalStage.STAGE_III))["basket_breadth"]

    assert basket["status"] == "unconfirmed"
    assert basket["missing"] == [f"pulp:{SPAN[40]}"]


# The supply-demand note: in stages III to V alone, never naming the driver.

TO_AUGUST = ("2026-04", "2026-05", "2026-06", "2026-07", "2026-08")
PMI = "diffusion_index_points"


def seed_demand(
    repository: EvidenceRepository, *, orders: str, output: str, purchases: str = ""
) -> None:
    """The PMI's orders and production along ``orders``, its purchases along ``purchases``
    (``orders`` unless given); industrial value added's year along ``output``, with no
    January and February's cumulative growth in its place."""
    trends = {"up": (50.0, 50.5, 51.0, 51.5, 52.0), "down": (52.0, 51.5, 51.0, 50.5, 50.0)}
    for series, trend in (
        ("manufacturing", orders),
        ("new_orders", orders),
        ("production", orders),
        ("purchase_volume", purchases or orders),
    ):
        append(
            repository,
            "CN_PMI_ACTIVITY",
            {"series": series, "measure": "level"},
            trends[trend],
            months=TO_AUGUST,
            unit=PMI,
        )
    values = (5.0,) * 9 + {"up": (5.0, 5.5, 6.0), "down": (6.0, 5.5, 5.0)}[output]
    for measure, held in (
        ("current_month_real_yoy", lambda month: not month.endswith(("-01", "-02"))),
        ("ytd_real_yoy", lambda month: month.endswith("-02")),
    ):
        append(
            repository,
            "CN_INDUSTRIAL_VA",
            {"measure": measure},
            tuple(
                value if held(month) else None for month, value in zip(YEAR, values, strict=True)
            ),
            months=YEAR,
            unit="scalar",
        )


def demand_note(tmp_path: Path, stage: FormalStage, **seeded: str) -> Any:
    """The note on the builtin catalog's official months, ``seeded`` as ``seed_demand``."""
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    if seeded:
        seed_demand(repository, **seeded)
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start=WINDOW_START,
        model_manifest=monthly_manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
        calendar=CALENDAR,
        core_prices=cores(),
    ).macro["supply_demand"]


@pytest.mark.parametrize("stage", list(FormalStage))
def test_the_supply_demand_note_is_given_in_stages_iii_to_v_alone(
    tmp_path: Path, stage: FormalStage
) -> None:
    note = demand_note(tmp_path, stage, orders="up", output="up")

    if stage in {FormalStage.STAGE_III, FormalStage.STAGE_IV, FormalStage.STAGE_V}:
        assert note["counted"] is False
        assert note["outcome"] == "demand_supported"
    else:
        assert note is None


@pytest.mark.parametrize(
    ("orders", "output", "outcome", "text"),
    [
        ("up", "up", "demand_supported", "国内需求恢复获得支持"),
        ("down", "down", "demand_insufficient", "需求恢复解释不足；供给、预期或晚周期因素待查"),
        # Orders rising on while purchases fall: neither.
        ("up", "up", "mixed", "混合"),
    ],
)
def test_the_note_tests_demand_and_never_names_the_driver(
    tmp_path: Path, orders: str, output: str, outcome: str, text: str
) -> None:
    note = demand_note(
        tmp_path,
        FormalStage.STAGE_IV,
        orders=orders,
        output=output,
        purchases="down" if outcome == "mixed" else "",
    )

    assert (note["outcome"], note["driver"]) == (outcome, "unconfirmed")
    assert note["headline"] == "商品价格上涨，推动力未确认"
    assert text in note["text"]
    assert note["boundary"] == "现有数据只能做需求一致性检验与供给嫌疑提示，不能确认推动力"
    assert (note["supply_suspicion"] is not None) is (outcome == "demand_insufficient")
    for words in ("供给推动", "需求推动", "供给型上涨", "需求型上涨"):
        assert not any(words in item for item in texts(note))


def test_demand_not_known_leaves_the_note_unconfirmed(tmp_path: Path) -> None:
    note = demand_note(tmp_path, FormalStage.STAGE_III)

    assert (note["outcome"], note["driver"]) == ("unconfirmed", "unconfirmed")
    assert "pmi:new_orders" in note["missing"]


# Consumers.


def test_the_page_and_the_report_input_show_them(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)

    validate_analytical_projection(projection.envelope, projection.datasets)
    macro: dict[str, Any] = projection.datasets["macro"]
    assert {item["status"] for item in macro["price_consistency"]["relative_momentum"]} == {"read"}
    page = _text(dashboard_page("/macro", projection, (), ()))
    assert "价格内部一致性" in page and "不计数" in page
    assert "商品对债" in page and "股票对债" in page and "股票对商品" in page
    assert "观察接口" in page and "只展示" in page
    report = report_input_from_projection(projection)
    confirmation = report.results["confirmation"]
    assert [item["key"] for item in confirmation["price_consistency"]["relative_momentum"]] == [
        "commodity_vs_bond",
        "stock_vs_bond",
        "stock_vs_commodity",
    ]
    assert {item["core"] for item in confirmation["observation_interfaces"]["cores"]} == {
        "bond",
        "stock",
        "commodity",
    }
    # Shown in the report as read, without the evidence identifiers.
    assert "claim_id" not in json.dumps(confirmation["observation_interfaces"])
    assert "supply_demand" in confirmation


@pytest.mark.parametrize(
    ("text", "outcome"),
    [
        # Every pair is flat in the published cores: said so, or not said at all.
        ("商品对债相对动量持平，股票对债持平。", "succeeded"),
        ("三项相对动量都不向上。", "succeeded"),
        ("商品对债相对动量：向上。", "conclusion_mutation_rejected"),
        ("股票对商品走强，阶段位置符合预期。", "conclusion_mutation_rejected"),
        ("商品对债并非持平。", "conclusion_mutation_rejected"),
        # Into the next sentence when it speaks of the momentum, naming no pair.
        ("商品对债需要观察。其相对动量向下。", "conclusion_mutation_rejected"),
        ("商品对债需要观察。PPI 回升。", "succeeded"),
        # Another subject's clause in the same sentence is not the pair's.
        ("商品对债相对动量持平，PPI 回升。", "succeeded"),
        ("商品对债持平，但相对动量正在回升。", "conclusion_mutation_rejected"),
        ("商品对债相对动量，当前正在回升。", "conclusion_mutation_rejected"),
        ("商品对债相对动量持平，PPI 则不同，当前正在回升。", "succeeded"),
        # What drives commodity prices is never said as known.
        ("现有数据不能确认推动力，供给推动与需求推动均未确认。", "succeeded"),
        ("本轮商品上涨属于需求型上涨。", "conclusion_mutation_rejected"),
        ("商品上涨的推动力已确认。", "conclusion_mutation_rejected"),
    ],
)
def test_a_report_rewriting_the_price_consistency_or_naming_a_driver_is_rejected(
    tmp_path: Path, text: str, outcome: str
) -> None:
    assert report_outcome(tmp_path, "价格", text) == outcome


@pytest.mark.parametrize(
    ("text", "outcome"),
    [("向上。", "conclusion_mutation_rejected"), ("持平。", "succeeded")],
)
def test_a_pair_titled_runs_into_its_paragraph(tmp_path: Path, text: str, outcome: str) -> None:
    assert report_outcome(tmp_path, "商品对债：", text) == outcome


def report_outcome(tmp_path: Path, title: str, text: str) -> str:
    """How the report's check takes ``text`` under ``title``, of the published cores."""
    bundle = report_input_from_projection(confirmed(tmp_path))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter(
        "codex_cli", AdapterResponse.succeeded(_document(bundle, text, title=title))
    )
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(bundle)

    return reports.attempts(result.report_snapshot_id)[0].outcome
