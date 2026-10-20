"""The signal list under the macro judgement (ADR-0043, macro stage ticket 04).

Divergent key indicators (loans among them), the price signals of the price signal
table and the cores' own turn watch are listed together, each with the transition it
supports, grouped against the main conclusion, and its maturity. The table is frozen in
model-v0016; each case registers its own model in its own run's database.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.context_projection import ContextProjectionRules
from pring_cycle.core_history import refresh_core_history
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
from pring_cycle.official_lpr import FetchedOfficialDocument, refresh_lpr_release
from pring_cycle.projections import (
    ProjectionSet,
    ProjectionSetRepository,
)
from pring_cycle.runtime import RuntimePaths
from pring_cycle.source_adapters import CORE_API_IDENTITIES, TushareCoreAdapter
from pring_cycle.trading_calendar import TradingCalendar
from pring_cycle.tushare_context import MARKET_INDEX_IDENTITIES, TushareContextAdapter
from tests.conftest import install_runtime_clock
from tests.integration.test_backfill import summary
from tests.integration.test_confirmation_cumulative_quarterly import LESS, LOAN_PAIRS, MORE, loan
from tests.integration.test_confirmation_monthly_indicators import append
from tests.integration.test_confirmation_price_consistency import (
    BASKET,
    BREADTH,
    SLEEVES,
)
from tests.integration.test_confirmation_price_consistency import VERSION as V0006
from tests.integration.test_confirmation_price_consistency import claim as breadth_claim
from tests.integration.test_confirmation_projection import append_pmi, confirmation_manifest
from tests.integration.test_confirmation_publish import publish
from tests.integration.test_core_carry_forward import (
    CORES,
    CUTOFF,
    TARGET,
    seed_cores,
    sessions,
)
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
from tests.integration.test_worker_registered_catalog import macro_rows


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

    def held_set() -> ProjectionSet:
        [event] = [event for event in repository.stage_history() if event["business_date"] == held]
        return repository.get(str(event["projection_set_id"]))

    def held_judgement() -> dict[str, Any]:
        return judgement(held_set())

    def held_row() -> Any:
        """How the held day's stage history row tells the hysteresis left it (D2)."""
        history: dict[str, Any] = held_set().datasets["stage_history"]
        days = history["display"]["days"]
        return next(row for row in days if row["date"] == held).get("macro_hysteresis")

    summaries.backfill((held,), target=days[-1], system_as_of=CUTOFF)
    before = held_judgement()
    # No stage before it: the ties go to the first in Pring's order, stage III.
    assert (before["conclusion"]["stage"], before["hysteresis"]["basis"]) == ("stage_iii", "agrees")
    assert held_row() == {"basis": "agrees"}
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
    # Its row tells the relinked set's hysteresis, not the one it replaced.
    assert held_row() == {"basis": "held", "raw_stage": "stage_v", "raw_confidence": "tendency"}
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


def test_a_divergence_two_periods_running_is_formed(tmp_path: Path) -> None:
    # April too: the PMI's June diverges as its July does, manufacturing falling while new
    # orders rise. The rules take effect the day before July is out.
    paths = seeded(tmp_path)
    repository = EvidenceRepository(paths.database)
    append_pmi(
        repository, "manufacturing", (50.8,), months=("2026-04",), definition_version=CATALOG
    )
    append_pmi(repository, "new_orders", (49.5,), months=("2026-04",), definition_version=CATALOG)
    june, july, after = "2026-07-30", "2026-07-31", "2026-08-03"
    take_effect(paths, june)
    DaySummaries(
        repository,
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), MODEL),
        calendar=TradingCalendar(sessions()),
    ).backfill((july, after), target="2026-08-04", system_as_of=CUTOFF)

    def pmi(day: str) -> dict[str, Any]:
        return signals(summary(paths, day))["D-pmi"]

    # Decision 43 for a divergence: its second period divergent forms it, and a session of
    # the same period counts no more.
    assert [
        (pmi(day)["indicator"]["period"], pmi(day)["periods"], pmi(day)["maturity"])
        for day in (june, july, after)
    ] == [
        ("2026-06-30", 1, "sprout"),
        ("2026-07-31", 2, "forming"),
        ("2026-07-31", 2, "forming"),
    ]


# The day summary on catalog v0006: the stock breadth's and the basket's divergences.

V0006_MODEL = "model-macro-v0006-fixture"
# 19:00 in Shanghai on the target day: the cores' originals are fetched before the cutoff.
FETCHED = datetime(2026, 8, 28, 11, tzinfo=UTC)


def register_v0006(paths: RuntimePaths) -> None:
    """model-v0016 under a fixture's name: its rules, its signal table and catalog v0006,
    whose definitions hold the breadth's ``CN_EQ_ABOVE_MA90`` and the sleeves'
    contributions by ``formula_version`` and ``sleeve``."""
    manifest = model_v0016_manifest()
    manifest["model_version_id"] = V0006_MODEL
    ModelRepository(paths.database).register(manifest)


def core_originals(states: dict[str, str]) -> TushareCoreAdapter:
    """TuShare answering the SSE calendar, every weekday open, and each core's daily bars
    over ``sessions()``: rising by one a session from 100 (bull) or falling by one from
    1000 (bear)."""
    days = sessions()
    assets = {CORE_API_IDENTITIES[metric_id][1]: asset for asset, metric_id in CORES.items()}

    def close(asset: str, index: int) -> float:
        return 100.0 + index if states[asset] == "bull" else 1000.0 - index

    def transport(payload: dict[str, Any]) -> bytes:
        params = payload["params"]
        start = datetime.strptime(params["start_date"], "%Y%m%d").date()
        end = datetime.strptime(params["end_date"], "%Y%m%d").date()
        if payload["api_name"] == "trade_cal":
            fields = ["cal_date", "is_open"]
            items: list[list[object]] = [
                [day.strftime("%Y%m%d"), int(day.weekday() < 5)]
                for day in (start + timedelta(days=n) for n in range((end - start).days + 1))
            ]
        else:
            asset = assets[params["ts_code"]]
            # fut_index_daily states its change as a fraction, index_daily in percent.
            scale = 1.0 if payload["api_name"] == "fut_index_daily" else 100.0
            fields = ["ts_code", "trade_date", "close", "pre_close", "pct_chg"]
            items = [
                [
                    params["ts_code"],
                    day.strftime("%Y%m%d"),
                    close(asset, index),
                    close(asset, index - 1),
                    (close(asset, index) / close(asset, index - 1) - 1) * scale,
                ]
                for index, day in enumerate(days)
                if start <= day <= end
            ]
        return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

    return TushareCoreAdapter("fixture-token", transport=transport)


def v0006(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    **states: str,
) -> RuntimePaths:
    """A run's database under model-v0016's rules on catalog v0006, whose cores ``states``
    names, fetched from their originals: a registered catalog adopts a core close only
    while its original states it. No macro claim is held unless a case fetches its
    originals too (``seed_macro_originals``, ``seed_lpr``); without, the judgement falls
    back on the stage it is stated against (ticket 03)."""
    install_runtime_clock(monkeypatch, request, FETCHED)
    paths = runtime(tmp_path)
    register_v0006(paths)
    days = sessions()
    refresh_core_history(
        paths, core_originals(states), start=days[0], end=days[-1], definition_version=V0006
    )
    return paths


def seed_breadth(paths: RuntimePaths, share: float) -> None:
    """The share of A shares above their 90-session average on the target day."""
    breadth_claim(
        EvidenceRepository(paths.database),
        "CN_EQ_ABOVE_MA90",
        TARGET.isoformat(),
        BREADTH,
        share,
        unit="percent",
    )


def seed_sleeves(
    paths: RuntimePaths, signs: tuple[int, ...], recent: tuple[int, ...] | None = None
) -> None:
    """Each sleeve's daily contribution, 0.01 points a session times its sign, on each of
    the 120 sessions the basket's return spans to the target day, as TuShare's basket
    delivers them (test_confirmation_price_consistency), in one append; ``recent`` signs
    instead on the last 20."""
    claims = []
    for index, day in enumerate(last(120)):
        public = datetime.combine(date.fromisoformat(day), time(10), tzinfo=UTC)
        today = recent if recent is not None and index >= 100 else signs
        for sleeve, sign in zip(SLEEVES, today, strict=True):
            dimensions = {"formula_version": BASKET, "sleeve": sleeve}
            claims.append(
                SourceClaimInput(
                    metric_id="CN_COMMODITY_SLEEVE_CONTRIBUTION",
                    definition_version=V0006,
                    period_kind="business_day",
                    period_start=day,
                    period_end=day,
                    dimensions=dimensions,
                    value=0.01 * sign,
                    value_state=EvidenceValueState.REPORTED_VALUE,
                    unit="percentage_points",
                    provider="tushare",
                    source_reference=f"tushare:commodity_basket:{sleeve}:{day}",
                    release_event_id=f"release:sleeve:{sleeve}:{day}",
                    release_at=public,
                    public_available_at=public,
                    fetched_at=public,
                    available_at=public,
                    certification_status="certified",
                    quality_status="validated",
                )
            )
    EvidenceRepository(paths.database).append_source_claims(tuple(claims))


def breadth_signals(projection: ProjectionSet) -> dict[str, dict[str, Any]]:
    """The day's listed signals and sprouts of the breadth and the basket, by cell."""
    published = judgement(projection)
    return {
        item["id"]: {**item, "listed": item in published["signals"]}
        for item in (*published["signals"], *published["sprouts"])
        if item.get("source") in ("stock_breadth", "basket_breadth")
    }


def test_in_stage_iii_a_narrow_rise_is_b2_and_a_fall_on_few_sleeves_is_k4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths = v0006(tmp_path, monkeypatch, request, bond="bull", stock="bull", commodity="bull")
    # 38% of shares above their 90-session average while the stock core rises; the basket
    # falling on three of its seven sleeves.
    seed_breadth(paths, 38.0)
    seed_sleeves(paths, (-1, -1, 1, 1, 1, 1, -9))

    projection = publish(paths, V0006_MODEL)

    macro: dict[str, Any] = projection.datasets["macro"]
    read = macro["price_consistency"]
    assert (read["stock_breadth"]["reading"], read["basket_breadth"]["reading"]) == (
        "narrow_rise",
        "few_sleeves_fall",
    )
    # No macro claim: the judgement falls back on the day's price stage, III.
    assert judgement(projection)["conclusion"]["stage"] == "stage_iii"
    placed = breadth_signals(projection)
    assert set(placed) == {"B2", "K4"}
    b2, k4 = placed["B2"], placed["K4"]
    assert (b2["kind"], b2["same_source"], b2["breadth"]["share"]) == ("price", True, 38.0)
    # B2: IV to V, two steps forward of III; its first session and no other cell to V:
    # a sprout, not listed (decision 37).
    assert b2["transition"] == {"from": "stage_iv", "to": "stage_v"}
    assert (b2["group"], b2["steps"]) == ("forward", 2)
    assert (b2["sessions"], b2["maturity"], b2["listed"]) == (1, "sprout", False)
    # K4: II to III, the conclusion itself; III is the day's price stage: confirmed, listed
    # on its first session (decision 43).
    assert k4["transition"] == {"from": "stage_ii", "to": "stage_iii"}
    assert (k4["group"], k4["steps"]) == ("hold", 0)
    assert (k4["sessions"], k4["maturity"], k4["listed"]) == (1, "confirmed", True)


def test_in_stage_i_a_narrow_fall_is_b4_and_a_rise_on_one_sleeve_is_k2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths = v0006(tmp_path, monkeypatch, request, bond="bull", stock="bear", commodity="bear")
    # 58% of shares above their 90-session average while the stock core falls; the basket
    # rising on its crude oil alone.
    seed_breadth(paths, 58.0)
    seed_sleeves(paths, (-1, -1, -1, -1, -1, -1, 9))

    projection = publish(paths, V0006_MODEL)

    macro: dict[str, Any] = projection.datasets["macro"]
    read = macro["price_consistency"]
    assert (read["stock_breadth"]["reading"], read["basket_breadth"]["reading"]) == (
        "narrow_fall",
        "single_sleeve_rise",
    )
    assert judgement(projection)["conclusion"]["stage"] == "stage_i"
    placed = breadth_signals(projection)
    assert set(placed) == {"B4", "K2"}
    b4, k2 = placed["B4"], placed["K2"]
    # B4: I to II, a step forward. Stocks 88.22 points weaker than bonds, 10.60 less so
    # than 20 sessions before: R5 points from I to II too, so two cells form it on its
    # first session (decision 43).
    assert b4["transition"] == {"from": "stage_i", "to": "stage_ii"}
    assert (b4["group"], b4["steps"]) == ("forward", 1)
    r5 = signals(projection)["R5"]
    assert r5["momentum"]["value_pp"] == pytest.approx(-88.22, abs=0.01)
    assert r5["momentum"]["change_pp"] == pytest.approx(10.60, abs=0.01)
    assert r5["transition"] == {"from": "stage_i", "to": "stage_ii"}
    assert (b4["sessions"], b4["maturity"], b4["listed"]) == (1, "forming", True)
    # K2: V to VI, a step back from I round the ring; alone on its first session: a sprout.
    assert k2["transition"] == {"from": "stage_v", "to": "stage_vi"}
    assert (k2["group"], k2["steps"]) == ("back", -1)
    assert (k2["sessions"], k2["maturity"], k2["listed"]) == (1, "sprout", False)


def seed_macro_originals(paths: RuntimePaths) -> None:
    """TuShare's monthly and quarterly deliveries of the confirmation's official series,
    test_worker_registered_catalog's rows: every field rising from 2024, to July (the
    second quarter), out by the target day. Each is stored with its original, so catalog
    v0006 adopts it; policy and inventory have none."""

    def transport(payload: dict[str, Any]) -> bytes:
        fields = payload["fields"].split(",")
        items = macro_rows(payload["api_name"], payload["params"], fields)
        return json.dumps({"code": 0, "data": {"fields": fields, "items": items}}).encode()

    adapter = TushareContextAdapter("fixture-token", transport=transport)
    months = {"start_month": "2024-01", "end_month": "2026-07"}
    for retrieve in (
        lambda: adapter.pmi(**months),
        lambda: adapter.prices(**months),
        lambda: adapter.money(**months, include_month_on_month=False),
        lambda: adapter.social_financing_total(**months),
        lambda: adapter.gdp(start_quarter="2024Q1", end_quarter="2026Q2"),
    ):
        adapter.acquire_scalars(paths, retrieve, definition_version=V0006)


LPR_ANNOUNCEMENT = (
    Path(__file__).parents[1] / "fixtures/chinamoney_lpr_20260820.html"
).read_bytes()


def seed_lpr(paths: RuntimePaths, fixings: dict[str, tuple[float, float]]) -> None:
    """Each month's LPR announcement on the 20th, the 2026-08-20 original's wording with
    the month's date and its one-year and five-year-plus fixings, fetched before the
    target day's cutoff and stored as fetched."""
    for month, (one_year, five_year) in fixings.items():
        day = f"{month}-20"
        content = (
            LPR_ANNOUNCEMENT.decode()
            .replace("2026年8月20日", f"{month[:4]}年{int(month[5:])}月20日")
            .replace("2026-08-20", day)
            .replace("1年期LPR为3.0%", f"1年期LPR为{one_year}%")
            .replace("5年期以上LPR为3.5%", f"5年期以上LPR为{five_year}%")
            .encode()
        )

        def served(url: str, content: bytes = content) -> FetchedOfficialDocument:
            return FetchedOfficialDocument(content, "text/html", url, 200)

        refresh_lpr_release(
            paths,
            source_url=(
                f"https://www.chinamoney.com.cn/chinese/rdgz/{day.replace('-', '')}/3399885.html"
            ),
            expected_period=month,
            fetched_at=FETCHED,
            fetcher=served,
            definition_version=V0006,
        )


def test_on_its_macro_originals_a_stage_iv_groups_b2_and_k4_and_k4_confirms_on_stage_iii(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    # The first case's cores, breadth and basket, now with the macro data on catalog v0006
    # too: credit and prices rising, prices high, the LPR raised in July.
    paths = v0006(tmp_path, monkeypatch, request, bond="bull", stock="bull", commodity="bull")
    seed_macro_originals(paths)
    seed_lpr(paths, {f"2026-{m:02d}": ((3.0, 3.5) if m < 7 else (3.1, 3.6)) for m in range(1, 9)})
    seed_breadth(paths, 38.0)
    seed_sleeves(paths, (-1, -1, 1, 1, 1, 1, -9))

    projection = publish(paths, V0006_MODEL)

    # Tightening, credit up and prices up: stage IV on three dimensions of three known,
    # a step on from the day's price stage, III.
    assert projection.datasets["cycle_overview"]["current_stage"] == "stage_iii"
    published = judgement(projection)
    assert [(item["dimension"], item["value"]) for item in published["dimensions"]] == [
        ("policy", "tightening"),
        ("credit", "up"),
        ("overheat", None),
        ("price", "up"),
        ("inventory", None),
    ]
    assert (published["conclusion"]["stage"], published["conclusion"]["confidence"]) == (
        "stage_iv",
        "explicit",
    )
    placed = breadth_signals(projection)
    assert set(placed) == {"B2", "K4"}
    b2, k4 = placed["B2"], placed["K4"]
    # Grouped against the main conclusion, IV: B2 to V a step forward, K4 to III a step
    # back -- not two forward and a hold, as against the price stage.
    assert b2["transition"] == {"from": "stage_iv", "to": "stage_v"}
    assert (b2["group"], b2["steps"]) == ("forward", 1)
    assert k4["transition"] == {"from": "stage_ii", "to": "stage_iii"}
    assert (k4["group"], k4["steps"]) == ("back", -1)
    # Confirmed against the price stage, III: K4 on its first session, listed; B2 to V
    # is a sprout.
    assert (k4["sessions"], k4["maturity"], k4["listed"]) == (1, "confirmed", True)
    assert (b2["sessions"], b2["maturity"], b2["listed"]) == (1, "sprout", False)


@pytest.mark.parametrize(
    ("states", "share", "signs", "readings"),
    [
        # Stocks up with most shares above their average; the basket up on most sleeves.
        (("bull", "bull", "bull"), 62.0, (1, 1, 1, 1, 1, 1, -1), ("broad_rise", "broad_rise")),
        # Stocks down with most shares below; the basket down on every sleeve.
        (("bull", "bear", "bear"), 38.0, (-1,) * 7, ("broad_fall", "broad_fall")),
        # Half the shares above; the sleeves offsetting each other session by session.
        (("bull", "bull", "bull"), 50.0, (1, 1, 1, -1, -1, -1, 0), ("even", "flat")),
    ],
    ids=["broad_rise", "broad_fall", "even_and_flat"],
)
def test_a_breadth_or_basket_moving_broadly_or_evenly_is_in_no_cell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    states: tuple[str, str, str],
    share: float,
    signs: tuple[int, ...],
    readings: tuple[str, str],
) -> None:
    bond, stock, commodity = states
    paths = v0006(tmp_path, monkeypatch, request, bond=bond, stock=stock, commodity=commodity)
    seed_breadth(paths, share)
    seed_sleeves(paths, signs)

    projection = publish(paths, V0006_MODEL)

    macro: dict[str, Any] = projection.datasets["macro"]
    read = macro["price_consistency"]
    assert (read["stock_breadth"]["reading"], read["basket_breadth"]["reading"]) == readings
    # Signal table, sections 2 and 3: only a divergence is a cell.
    assert breadth_signals(projection) == {}


def test_the_basket_is_read_over_its_120_sessions_not_its_last_20(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    paths = v0006(tmp_path, monkeypatch, request, bond="bull", stock="bull", commodity="bull")
    seed_breadth(paths, 62.0)
    # Down on three sleeves over the 120 sessions; up on all seven over the last 20.
    seed_sleeves(paths, (-1, -1, 1, 1, 1, 1, -9), recent=(1,) * 7)

    projection = publish(paths, V0006_MODEL)

    macro: dict[str, Any] = projection.datasets["macro"]
    assert macro["price_consistency"]["basket_breadth"]["reading"] == "few_sleeves_fall"
    assert set(breadth_signals(projection)) == {"K4"}
