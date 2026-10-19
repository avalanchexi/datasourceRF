"""The signal list under the macro judgement (ADR-0043, macro stage ticket 04).

Divergent key indicators (loans among them), the price signals of the price signal
table and the cores' own turn watch are listed together, each with the transition it
supports, grouped against the main conclusion, and its maturity. The table is frozen in
model-v0016; each case registers its own model in its own run's database.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.day_summary import DaySummaries, ModelRules
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.macro_judgement import MANIFEST_FIELD, rules_v0001
from pring_cycle.macro_signals import MANIFEST_FIELD as SIGNALS_FIELD
from pring_cycle.macro_signals import table_v0001
from pring_cycle.models import (
    ModelRepository,
    certified_model_v0001_manifest,
    model_v0015_manifest,
    model_v0016_manifest,
)
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.tushare_context import MARKET_INDEX_IDENTITIES
from tests.integration.test_confirmation_cumulative_quarterly import LESS, LOAN_PAIRS, MORE, loan
from tests.integration.test_confirmation_monthly_indicators import append
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_confirmation_publish import publish
from tests.integration.test_core_carry_forward import CORES, CUTOFF, seed_cores, sessions
from tests.integration.test_day_summary import stock_conflict
from tests.integration.test_decertified_main_chain import claim as core_claim
from tests.integration.test_macro_fallback import STOCK_TURN, seed_combination
from tests.integration.test_macro_hysteresis import SF_REVISED, revise_credit
from tests.integration.test_macro_judgement import (
    CATALOG,
    MODEL,
    SEEDED,
    checked,
    judgement,
    publish_from,
    seed_macro,
    take_effect,
)
from tests.integration.test_worker_execution import runtime, seed_independent_calendar


def test_v0016_freezes_the_price_signal_table() -> None:
    v0016 = model_v0016_manifest()
    table = v0016["macro_signal_rules"]

    assert "macro_signal_rules" not in model_v0015_manifest()
    # Decision 37: only a forming signal is listed; formed in five sessions; the turn is
    # read over 20; the peers' candidates over 30, as the cores' own.
    assert (table["listed_from"], table["forming_sessions"], table["turn_sessions"]) == (
        "forming",
        5,
        20,
    )
    assert (table["candidate_sessions"], table["divergence_forming_periods"]) == (30, 2)
    # signal-table.md, one: decision 38 took out R6, R7, R8 and R12.
    assert {
        cell["cell"]: (cell["pair"], cell["level"], cell["turn"], cell["from"], cell["to"])
        for cell in table["relative_momentum"]
    } == {
        "R1": ("commodity_vs_bond", "down", "up", "stage_ii", "stage_iii"),
        "R2": ("commodity_vs_bond", "up", "up", "stage_iii", "stage_iv"),
        "R3": ("commodity_vs_bond", "up", "down", "stage_v", "stage_vi"),
        "R4": ("commodity_vs_bond", "down", "down", "stage_vi", "stage_i"),
        "R5": ("stock_vs_bond", "down", "up", "stage_i", "stage_ii"),
        "R9": ("stock_vs_commodity", "up", "up", "stage_i", "stage_ii"),
        "R10": ("stock_vs_commodity", "up", "down", "stage_ii", "stage_iii"),
        "R11": ("stock_vs_commodity", "down", "down", "stage_iv", "stage_v"),
    }
    # Two and three: the divergences alone (decisions 39, 40).
    assert {
        cell["cell"]: (cell["readings"], cell["from"], cell["to"])
        for key in ("stock_breadth", "basket_breadth")
        for cell in table[key]
    } == {
        "B2": (["narrow_rise"], "stage_iv", "stage_v"),
        "B4": (["narrow_fall"], "stage_i", "stage_ii"),
        "K2": (["single_sleeve_rise", "few_sleeves_rise"], "stage_v", "stage_vi"),
        "K4": (["single_sleeve_fall", "few_sleeves_fall"], "stage_ii", "stage_iii"),
    }
    # Four: each asset's peers, merged into one signal (decision 42); breadth, valuation
    # and margin financing are no peers.
    assert table["peers"] == {
        "bond": ["CN_BOND_10Y_930916", "CN_BOND_FULL_PRICE_CNY030"],
        "stock": ["CN_EQ_CSI300", "CN_EQ_CSI500", "CN_EQ_CSI1000"],
        "commodity": [
            "CN_COMMODITY_BROAD_NHCI",
            "CN_COMMODITY_EX_HOG_BASKET",
            "EIA_WTI_RWTC",
            "EIA_BRENT_RBRTE",
        ],
    }
    # Four and five: an asset turning, mapped by flipping it in the day's combination.
    assert table["flips"] == {
        "peers": {
            "bond": {"bear": "P1", "bull": "P2"},
            "stock": {"bear": "P3", "bull": "P4"},
            "commodity": {"bear": "P5", "bull": "P6"},
        },
        "cores": {
            "bond": {"bear": "C1", "bull": "C2"},
            "stock": {"bear": "C3", "bull": "C4"},
            "commodity": {"bear": "C5", "bull": "C6"},
        },
    }
    assert ContextProjectionRules.from_manifest(v0016).macro_signals is not None
    assert ContextProjectionRules.from_manifest(model_v0015_manifest()).macro_signals is None


@pytest.mark.parametrize(
    "change",
    [
        # A pair the price consistency does not read.
        lambda table: table["relative_momentum"][0].update(pair="bond_vs_cash"),
        # A breadth reading the price consistency never gives.
        lambda table: table["stock_breadth"][0].update(readings=["sector_rise"]),
        # A peer that is not one of its core's observation interfaces.
        lambda table: table["peers"]["bond"].append("CN_EQ_CSI300"),
        # One cell twice.
        lambda table: table["stock_breadth"][1].update(cell="B2"),
        lambda table: table["relative_momentum"][0].update(to="stage_vii"),
    ],
)
def test_a_table_the_price_consistency_cannot_read_is_refused(change: object) -> None:
    manifest = model_v0016_manifest()
    table = copy.deepcopy(manifest["macro_signal_rules"])
    change(table)  # type: ignore[operator]
    manifest["macro_signal_rules"] = table

    with pytest.raises(ValueError, match="macro_signal_rules_invalid"):
        ContextProjectionRules.from_manifest(manifest)


# The day summary: divergent key indicators.


def register(paths: RuntimePaths, *certified: str) -> None:
    """test_macro_judgement's model, ``certified`` held besides its own metrics."""
    base = certified_model_v0001_manifest()
    held = {*SEEDED, *certified}
    base["metric_definitions"] = [
        {**item, "certification_status": "certified"} if item["metric_id"] in held else item
        for item in base["metric_definitions"]
    ]
    manifest = confirmation_manifest(base)
    manifest.update(
        {
            "model_version_id": MODEL,
            MANIFEST_FIELD: rules_v0001(),
            SIGNALS_FIELD: table_v0001(),
        }
    )
    ModelRepository(paths.database).register(manifest)


def seeded(tmp_path: Path, *certified: str) -> RuntimePaths:
    """The 10-15 hand calculation's day (test_macro_judgement), on rising cores."""
    paths = runtime(tmp_path)
    seed_cores(paths)
    register(paths, *certified)
    seed_macro(paths)
    return paths


def signals(projection: ProjectionSet) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in judgement(projection)["signals"]}


def test_a_divergent_indicator_is_listed_with_its_minority_s_direction(tmp_path: Path) -> None:
    pmi = signals(publish(seeded(tmp_path), MODEL))["D-pmi"]

    assert (pmi["kind"], pmi["same_source"]) == ("divergence", False)
    assert pmi["indicator"] == {
        "key": "pmi",
        "name": "PMI",
        "dimension": "overheat",
        "period": "2026-07-31",
        "main_direction": "down",
    }
    # Manufacturing falls; its new orders rise.
    assert pmi["minority"] == {"direction": "up", "members": ["新订单"]}
    # Voted the minority's way the PMI turns growth up, and III, IV and V tie at three: the
    # tie is III, the last confirmed stage itself (ticket 03), two steps back from V.
    assert pmi["rejudged"]["dimension"] == {"dimension": "overheat", "value": "up"}
    assert (pmi["rejudged"]["basis"], pmi["rejudged"]["tied"], pmi["rejudged"]["matched"]) == (
        "tied",
        ["stage_iii", "stage_iv", "stage_v"],
        3,
    )
    assert (pmi["rejudged"]["stage"], pmi["rejudged"]["confidence"]) == ("stage_iii", "tendency")
    assert pmi["transition"] == {"from": "stage_v", "to": "stage_iii"}
    assert (pmi["group"], pmi["steps"]) == ("back", -2)
    # Its first period divergent: a sprout, listed all the same.
    assert (pmi["maturity"], pmi["periods"]) == ("sprout", 1)


def test_loans_diverging_are_listed_and_counted_in_credit_their_minority_s_way(
    tmp_path: Path,
) -> None:
    paths = seeded(tmp_path, "CN_LOAN_STRUCTURE")
    # July's enterprise long-term loans 50 less than a year before, households' 50 more.
    repository = EvidenceRepository(paths.database)
    for pair in LOAN_PAIRS:
        totals = MORE if pair == ("household", "total") else LESS
        append(
            repository,
            "CN_LOAN_STRUCTURE",
            loan(*pair),
            totals,
            months=("2025-06", "2025-07", "2026-06", "2026-07"),
            unit="hundred_million_cny",
            definition_version=CATALOG,
        )

    projection = publish(paths, MODEL)

    loans = signals(projection)["D-loans"]
    assert loans["indicator"]["main_direction"] == "down"
    assert loans["minority"]["direction"] == "up"
    assert loans["minority"]["members"] == ["住户贷款当月增量（较去年同月）"]
    # Loans never vote in credit (decision 29); counted their minority's way, credit ties
    # one to one and social financing decides it: still down, still stage V.
    credit = next(d for d in judgement(projection)["dimensions"] if d["dimension"] == "credit")
    assert [item["key"] for item in credit["indicators"] if item["voting"]] == [
        "social_financing",
        "money",
    ]
    assert loans["rejudged"]["dimension"] == {"dimension": "credit", "value": "down"}
    assert (loans["rejudged"]["stage"], loans["rejudged"]["confidence"]) == ("stage_v", "explicit")
    assert loans["transition"] == {"from": "stage_v", "to": "stage_v"}
    assert (loans["group"], loans["steps"]) == ("hold", 0)


# The day summary: the price signal table.


def seed_shaped_cores(
    paths: RuntimePaths,
    commodity: Callable[[int], float],
    bond: Callable[[int], float] = lambda i: 100.0 + i,
) -> None:
    """seed_cores's rising bond and stock (100 + i a session) with ``commodity``'s own path,
    and ``bond``'s when given; all three bull: the price stage is III."""
    days = sessions()
    seed_independent_calendar(paths, days)
    shapes = {"bond": bond, "stock": lambda i: 100.0 + i, "commodity": commodity}
    claims = []
    for index, observed in enumerate(days):
        for asset, metric_id in CORES.items():
            api_name, code = CORE_API_IDENTITIES[metric_id]
            claims.append(
                core_claim(
                    metric_id,
                    observed,
                    shapes[asset](index),
                    unit="index_points",
                    provider="tushare",
                    reference=f"tushare:{api_name}:{code}:{observed}",
                )
            )
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))


def shaped(tmp_path: Path) -> RuntimePaths:
    """Commodities compounding 0.6% a session against bonds and stocks rising by one."""
    paths = runtime(tmp_path)
    seed_shaped_cores(paths, lambda i: 100.0 * 1.006**i)
    register(paths)
    seed_macro(paths)
    return paths


def last(count: int) -> tuple[str, ...]:
    return tuple(day.isoformat() for day in sessions()[-count:])


def test_relative_momentum_maps_to_its_cell_s_transition_once_formed(tmp_path: Path) -> None:
    listed = signals(publish_from(shaped(tmp_path), last(5)))

    r2, r11 = listed["R2"], listed["R11"]
    assert (r2["kind"], r2["source"], r2["same_source"]) == ("price", "relative_momentum", True)
    # Over the 120 sessions to the day commodities return 105.00%, bonds 75.47%: commodities
    # stronger by 29.53 points, 10.86 more than 20 sessions before (18.67). R2: III to IV,
    # a step back from the main conclusion, stage V.
    assert r2["momentum"]["pair"] == "commodity_vs_bond"
    assert r2["momentum"]["value_pp"] == pytest.approx(29.53, abs=0.01)
    assert r2["momentum"]["change_pp"] == pytest.approx(10.86, abs=0.01)
    assert (r2["momentum"]["level"], r2["momentum"]["turn"]) == ("up", "up")
    assert r2["transition"] == {"from": "stage_iii", "to": "stage_iv"}
    assert (r2["group"], r2["steps"]) == ("back", -1)
    # Stocks weaker than commodities and weakening: R11, IV to V, supporting a hold.
    assert r11["momentum"]["pair"] == "stock_vs_commodity"
    assert r11["transition"] == {"from": "stage_iv", "to": "stage_v"}
    assert (r11["group"], r11["steps"]) == ("hold", 0)
    # Five sessions running: formed (decision 43).
    assert (r2["sessions"], r2["maturity"]) == (5, "forming")
    # Stocks and bonds move alike: no cell.
    assert [item["momentum"]["pair"] for item in listed.values() if "momentum" in item] == [
        "commodity_vs_bond",
        "stock_vs_commodity",
    ]


def test_a_cell_held_four_sessions_is_a_sprout_and_not_listed(tmp_path: Path) -> None:
    published = judgement(publish_from(shaped(tmp_path), last(4)))

    assert not {"R2", "R11"} & {item["id"] for item in published["signals"]}
    sprouts = {item["id"]: item for item in published["sprouts"]}
    assert (sprouts["R2"]["sessions"], sprouts["R2"]["maturity"]) == (4, "sprout")


BOND_PEERS = ("CN_BOND_10Y_930916", "CN_BOND_FULL_PRICE_CNY030")
STOCK_PEERS = ("CN_EQ_CSI300", "CN_EQ_CSI500", "CN_EQ_CSI1000")


def seed_peer(
    paths: RuntimePaths, metric_id: str, step: float, *, missing: tuple[int, ...] = ()
) -> None:
    """A peer index over the last 40 sessions, ``step`` a session from 1000; without the
    closes of the sessions ``missing`` (their places among the 40)."""
    api_name, _code = MARKET_INDEX_IDENTITIES[metric_id]
    repository = EvidenceRepository(paths.database)
    for index, observed in enumerate(sessions()[-40:]):
        if index in missing:
            continue
        public = datetime.combine(observed, time(10), tzinfo=UTC)
        repository.append_source_claim(
            SourceClaimInput(
                metric_id=metric_id,
                definition_version=CATALOG,
                period_kind="business_day",
                period_start=observed.isoformat(),
                period_end=observed.isoformat(),
                dimensions={},
                value=1000.0 + step * index,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="scalar",
                provider="tushare",
                source_reference=f"tushare:{api_name}:close:{observed}",
                release_event_id=f"release:{metric_id}:{observed}",
                release_at=public,
                public_available_at=public,
                fetched_at=public,
                available_at=public,
                certification_status="certified",
                quality_status="validated",
            )
        )


def with_peers(tmp_path: Path) -> RuntimePaths:
    """``shaped``'s day, with both bond peers falling under their falling 30-session average:
    bear against the bond's bull; and two of the three CSI indices falling, the third rising.
    """
    paths = runtime(tmp_path)
    seed_shaped_cores(paths, lambda i: 100.0 * 1.006**i)
    register(paths, *BOND_PEERS, *STOCK_PEERS)
    seed_macro(paths)
    for metric_id in BOND_PEERS:
        seed_peer(paths, metric_id, -2.0)
    for metric_id, step in zip(STOCK_PEERS, (-2.0, -1.0, 3.0), strict=True):
        seed_peer(paths, metric_id, step)
    return paths


def listed_day(tmp_path: Path) -> ProjectionSet:
    """``with_peers``'s day after four more sessions: every table signal formed."""
    return publish_from(with_peers(tmp_path), last(5))


def test_peers_turning_against_their_core_flip_it_in_the_day_s_combination(
    tmp_path: Path,
) -> None:
    published = judgement(publish(with_peers(tmp_path), MODEL))

    listed = {item["id"]: item for item in published["signals"]}
    bond = listed["P1"]
    assert (bond["kind"], bond["source"], bond["same_source"]) == ("price", "peers", True)
    assert bond["asset_turn"] == {"asset": "bond", "to": "bear", "state": "bull"}
    assert bond["peers"] == {"against": ["10 年国债价格指数", "中债 030 全价"], "read": 2}
    # The bond bear in bull stocks and commodities: stage IV, a step back from V.
    assert bond["transition"] == {"from": "stage_iii", "to": "stage_iv"}
    assert (bond["group"], bond["steps"]) == ("back", -1)
    # Its first session, but R2 points to IV too: two cells, formed (decision 43).
    assert (bond["sessions"], bond["maturity"]) == (1, "forming")
    assert (listed["R2"]["sessions"], listed["R2"]["maturity"]) == (1, "forming")
    # Stocks turning bear make bond bull, stock bear, commodity bull: no typical stage.
    stock = {item["id"]: item for item in published["sprouts"]}["P3"]
    assert stock["peers"] == {"against": ["中证 300", "中证 500"], "read": 3}
    assert stock["transition"] == {"from": "stage_iii", "to": None}
    assert (stock["group"], stock["maturity"]) == ("unmapped", "sprout")


@pytest.mark.parametrize(
    "tamper",
    [
        # A group its steps from the main conclusion do not give.
        lambda block: next(i for i in block["signals"] if i["id"] == "R2").update(group="forward"),
        lambda block: next(i for i in block["signals"] if i["id"] == "R2").update(steps=2),
        # A sprout of the table among the listed.
        lambda block: next(i for i in block["signals"] if i["id"] == "R2").update(
            maturity="sprout"
        ),
        lambda block: block["signals"].append(copy.deepcopy(block["signals"][0])),
    ],
)
def test_a_signal_list_disagreeing_with_itself_is_not_published(
    tmp_path: Path, tamper: Any
) -> None:
    projection = publish_from(shaped(tmp_path), last(5))
    datasets = copy.deepcopy(projection.datasets)
    tamper(datasets["cycle_overview"]["macro_judgement"])

    with pytest.raises(ValueError, match="projection_macro_judgement_invalid"):
        checked(projection.envelope, datasets)


def test_a_core_s_30_day_candidate_against_its_state_joins_the_list(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    # The bond core rises by one a session to 274, then falls back from 240 over the last
    # five: under its 30-session average, and the average falling, while its 120-session
    # trend stays bull.
    seed_shaped_cores(
        paths, lambda i: 100.0 + i, bond=lambda i: 100.0 + i if i < 175 else 240.0 - 2 * (i - 175)
    )
    register(paths)
    seed_macro(paths)

    projection = publish_from(paths, last(5))

    bond = next(
        item for item in projection.datasets["core_assets"]["assets"] if item["asset"] == "bond"
    )
    assert (bond["state"], bond["candidate_30d"]) == ("bull", "bear")
    watch = signals(projection)["C1"]
    assert (watch["kind"], watch["source"], watch["same_source"]) == (
        "observation",
        "core_candidate",
        True,
    )
    assert watch["asset_turn"] == {"asset": "bond", "to": "bear", "state": "bull"}
    assert watch["candidates"]["against"] == ["candidate_30d"]
    assert watch["transition"] == {"from": "stage_iii", "to": "stage_iv"}
    assert (watch["group"], watch["sessions"], watch["maturity"]) == ("back", 5, "forming")


def test_two_cells_to_one_stage_from_two_stages_are_no_transition_formed(tmp_path: Path) -> None:
    paths = runtime(tmp_path)
    # The commodity core rises by one a session to 274, then falls back from 240 over the
    # last five: its 30-day candidate bear against its bull, and stocks stronger than
    # commodities and strengthening.
    seed_shaped_cores(paths, lambda i: 100.0 + i if i < 175 else 240.0 - 2 * (i - 175))
    register(paths)
    seed_macro(paths)

    published = judgement(publish(paths, MODEL))

    sprouts = {item["id"]: item for item in published["sprouts"]}
    # R9 points from I to II, the commodity core's candidate from III to II: one stage, two
    # transitions, each on its first session -- sprouts both (decision 43).
    assert sprouts["R9"]["transition"] == {"from": "stage_i", "to": "stage_ii"}
    assert sprouts["C5"]["transition"] == {"from": "stage_iii", "to": "stage_ii"}
    assert [(sprouts[key]["sessions"], sprouts[key]["maturity"]) for key in ("R9", "C5")] == [
        (1, "sprout"),
        (1, "sprout"),
    ]
    assert not {"R9", "C5"} & {item["id"] for item in published["signals"]}


def test_a_relink_while_a_run_is_counted_judges_the_divergence_again(tmp_path: Path) -> None:
    # Bonds and commodities falling, stocks rising until two sessions before the held day:
    # the day the rules take effect is a noncanonical bond bear · stock bull · commodity
    # bear, without a stage before it; the day after, missed at first, stage VI; the held
    # day's stock close conflicts, so it has no stage of its own. Credit is up throughout:
    # stages III, IV and V tie at three, and the PMI's minority, voting, ties III and IV.
    paths = runtime(tmp_path)
    seed_combination(paths, "bear", "bull", "bear", stock_turn=STOCK_TURN - 2)
    register(paths)
    seed_macro(paths)
    revise_credit(paths, SF_REVISED, on=-12)
    days = [day.isoformat() for day in sessions()]
    first, staged, held = days[-4], days[-3], days[-2]
    EvidenceRepository(paths.database).append_source_claims((stock_conflict(sessions()[-2]),))
    take_effect(paths, first)
    summaries = DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), MODEL),
        calendar=TradingCalendar(sessions()),
    )
    repository = ProjectionSetRepository(paths.database)

    def held_judgement() -> dict[str, Any]:
        [event] = [event for event in repository.stage_history() if event["business_date"] == held]
        return judgement(repository.get(str(event["projection_set_id"])))

    summaries.backfill((held,), target=days[-1], system_as_of=CUTOFF)
    before = held_judgement()
    # No stage before it: the ties go to the first in Pring's order, stage III.
    assert (before["conclusion"]["stage"], before["hysteresis"]["basis"]) == ("stage_iii", "agrees")
    pmi = next(item for item in before["signals"] if item["id"] == "D-pmi")
    assert (pmi["rejudged"]["stage"], pmi["transition"], pmi["group"]) == (
        "stage_iii",
        {"from": "stage_iii", "to": "stage_iii"},
        "hold",
    )

    summaries.backfill((staged, held), target=days[-1], system_as_of=CUTOFF + timedelta(days=1))

    after = held_judgement()
    # Stated against stage VI, the day's raw tie goes to V, counted on from the day before:
    # the second session toward replacing stage III, still held.
    assert (after["raw"]["stage"], after["conclusion"]["stage"]) == ("stage_v", "stage_iii")
    assert (after["hysteresis"]["candidate"], after["hysteresis"]["sessions"]) == ("stage_v", 2)
    assert [item["matches"] for item in after["dimensions"]] == [True, True, False, False, True]
    # The PMI's recount is judged again against stage VI: its tie of III and IV goes to IV,
    # a step forward from the conclusion.
    pmi = next(item for item in after["signals"] if item["id"] == "D-pmi")
    assert (pmi["rejudged"]["stage"], pmi["rejudged"]["confidence"]) == ("stage_iv", "tendency")
    assert (pmi["transition"], pmi["group"], pmi["steps"]) == (
        {"from": "stage_iii", "to": "stage_iv"},
        "forward",
        1,
    )


@pytest.mark.parametrize(
    "missing",
    [
        # A close missing inside its 31 sessions: the window is not whole.
        (38,),
        # Its latest close not out: what it shows is not the day's.
        (39,),
    ],
)
def test_a_peer_short_of_its_sessions_reads_no_candidate(
    tmp_path: Path, missing: tuple[int, ...]
) -> None:
    paths = runtime(tmp_path)
    seed_shaped_cores(paths, lambda i: 100.0 * 1.006**i)
    register(paths, *BOND_PEERS)
    seed_macro(paths)
    seed_peer(paths, BOND_PEERS[0], -2.0, missing=missing)
    seed_peer(paths, BOND_PEERS[1], -2.0)

    published = judgement(publish(paths, MODEL))

    # The 10-year index's closes skip a session of the SSE calendar: it reads nothing,
    # and only the CNY030 full price turns bear against the bond core.
    bond = {item["id"]: item for item in (*published["signals"], *published["sprouts"])}["P1"]
    assert bond["peers"] == {"against": ["中债 030 全价"], "read": 1}
