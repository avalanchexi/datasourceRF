"""Bond trend attribution beside the bond core's state (ADR-0037, macro semantics ticket 10).

The policy dimension and growth and inflation (the overheat and price dimensions) are read
from key indicators' main members into two axes; with the bond core's state they name what
drives its trend by the frozen table (expectation-table.md, 债券归因): fundamentals, policy
or liquidity, fundamentals and easing, or unclear. It is a note: never counted, never read
back into the bond's bull or bear or the formal stage. An axis not known leaves the driver
unclear and says why; funding rates falling while bonds stay bearish is unclear too.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from pring_cycle.batches import processing_batch
from pring_cycle.confirmation import ConfirmationRules
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository
from pring_cycle.models import model_v0015_manifest
from pring_cycle.price_consistency import CorePrices
from pring_cycle.projections import validate_analytical_projection
from pring_cycle.reports import (
    AdapterResponse,
    ReportRepository,
    ReportService,
    report_input_from_projection,
)
from tests.integration.test_confirmation_cumulative_quarterly import GDP, quarter
from tests.integration.test_confirmation_monthly_indicators import METRICS, year
from tests.integration.test_confirmation_monthly_indicators import seed as seed_monthly
from tests.integration.test_confirmation_policy import (
    AS_OF,
    CALENDAR,
    LPR_MONTHS,
    POLICY_METRICS,
    RATE_HISTORIES,
    TARGET,
    WINDOW_START,
    certified,  # noqa: F401 - the policy metrics certified, as their claims are
    dr007_blocks,
    seed_blocks,
    seed_lpr,
    seed_rate,
)
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_confirmation_projection import seed as seed_pmi
from tests.integration.test_confirmation_publish import _document, confirmed
from tests.integration.test_context_projection import _v2_manifest
from tests.reports.test_report_boundary import FakeAdapter
from tests.web.test_dashboard_contract import _text

BOND = "CN_BOND_CORE_000012"
FUNDAMENTALS = "基本面推动"
POLICY_OR_LIQUIDITY = "政策或流动性推动"
FUNDAMENTALS_AND_EASING = "基本面加宽松推动"
UNCLEAR = "推动力不明"


def manifest(*, attribution: bool = True) -> dict[str, Any]:
    document = confirmation_manifest(_v2_manifest(*METRICS, *POLICY_METRICS, "CN_GDP"))
    if not attribution:
        document = copy.deepcopy(document)
        del document["confirmation_rules"]["bond_attribution"]
    return document


def bond(state: str | None) -> dict[str, CorePrices]:
    """The bond core as its gate read it: ``state`` standing, or the gate failed."""
    if state is None:
        return {"bond": CorePrices("bond", BOND, "source_conflict")}
    return {"bond": CorePrices("bond", BOND, "validated", state=state)}


@contextmanager
def traced(repository: EvidenceRepository) -> Iterator[None]:
    """The run read the RRR chronicle to its end and found no change (ADR-0028)."""
    with sqlite3.connect(repository.database_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS full_run_gap_plan "
            "(run_id TEXT, phase TEXT, document_json TEXT, document_hash TEXT)"
        )
        connection.execute(
            "INSERT INTO full_run_gap_plan VALUES ('run-traced', 'event_backtrack', ?, '')",
            (json.dumps({"metrics": {"CN_RRR_EVENT": "none_found"}}),),
        )
    with processing_batch("run-traced"):
        yield


def project(
    repository: EvidenceRepository,
    stage: FormalStage | None,
    state: str | None,
    *,
    attribution: bool = True,
) -> ContextProjection:
    with traced(repository):
        return build_context_projection(
            repository,
            as_of=AS_OF,
            target_business_date=TARGET,
            visible_evidence_start=WINDOW_START,
            model_manifest=manifest(attribution=attribution),
            formal_stage=StageResult(
                stage, stage, "canonical_combination" if stage else "noncanonical_combination"
            ),
            calendar=CALENDAR,
            core_prices=bond(state),
        )


# The policy rate's history, and DR007's newest periods, by the policy axis they read.
POLICY = {
    "neutral": ("unchanged", dr007_blocks(1.6, 1.6, 1.6)),
    "tightening": ("hike_in_july", dr007_blocks(1.45, 1.5, 1.55, fill=1.4)),
    "easing": ("cut_in_may", dr007_blocks(1.5, 1.45, 1.35)),
    # No action, funding rates falling.
    "funding_falling": ("unchanged", dr007_blocks(1.5, 1.45, 1.35)),
    # A hike, funding rates falling all the same.
    "split": ("hike_in_july", dr007_blocks(1.5, 1.45, 1.35)),
}
GROWTH = ("pmi", "industrial_va", "gdp", "ppi", "pmi_prices")


def seed_policy(repository: EvidenceRepository, policy: str) -> None:
    history, blocks = POLICY[policy]
    seed_rate(repository, RATE_HISTORIES[history])
    for tenor, rate in (("1y", 3.0), ("5y_plus", 3.5)):
        seed_lpr(repository, tenor, dict.fromkeys(LPR_MONTHS, rate))
    seed_blocks(repository, "CN_DR007", {}, blocks)


def seed_growth(
    repository: EvidenceRepository, move: str, *, only: tuple[str, ...] = GROWTH
) -> None:
    """Each of ``only`` moving ``move`` over its newest period: up or down."""
    step = 0.5 if move == "up" else -0.5
    if "pmi" in only:
        seed_pmi(repository, (50.0, 50.0 + step, 50.0 + 2 * step))
    for key, fill in (("industrial_va", 5.0), ("ppi", -1.0), ("pmi_prices", 50.0)):
        if key in only:
            seed_monthly(repository, key, year(fill + step, fill + 2 * step, fill=fill))
    if "gdp" in only:
        quarter(repository, "CN_GDP", GDP, (5.0, 5.0, 5.0, 5.0 + step, 5.0 + 2 * step))


def attribution(context: ContextProjection) -> dict[str, Any]:
    return context.macro["bond_attribution"]  # type: ignore[return-value]


def axes(document: dict[str, Any]) -> dict[str, str]:
    return {item["axis"]: item["value"] for item in document["axes"]}


# The table, row by row (expectation-table.md, 债券归因).
@pytest.mark.parametrize(
    ("state", "stage", "policy", "growth", "driver", "text", "extra"),
    [
        (
            "bear",
            FormalStage.STAGE_IV,
            "neutral",
            "up",
            "fundamentals",
            FUNDAMENTALS,
            {"typical": "典型Ⅳ"},
        ),
        # Tightening or neutral alike.
        (
            "bear",
            FormalStage.STAGE_IV,
            "tightening",
            "up",
            "fundamentals",
            FUNDAMENTALS,
            {"typical": "典型Ⅳ"},
        ),
        (
            "bear",
            FormalStage.STAGE_V,
            "tightening",
            "down",
            "policy_liquidity",
            POLICY_OR_LIQUIDITY,
            {},
        ),
        (
            "bull",
            FormalStage.STAGE_I,
            "easing",
            "down",
            "fundamentals_and_easing",
            FUNDAMENTALS_AND_EASING,
            {"typical": "典型Ⅰ、Ⅵ→Ⅰ"},
        ),
        # Funding rates falling while bonds stay bearish (stage VI's note).
        (
            "bear",
            FormalStage.STAGE_VI,
            "funding_falling",
            "down",
            "unclear",
            UNCLEAR,
            {"suspicion": "财政供给、信用风险或期限溢价嫌疑"},
        ),
        # A bull under tightening, whatever growth and inflation do: not known here.
        (
            "bull",
            FormalStage.STAGE_II,
            "tightening",
            None,
            "unclear",
            UNCLEAR,
            {"suspicion": "避险嫌疑"},
        ),
    ],
)
def test_each_row_of_the_table_names_its_driver(
    tmp_path: Path,
    state: str,
    stage: FormalStage,
    policy: str,
    growth: str | None,
    driver: str,
    text: str,
    extra: dict[str, str],
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, policy)
    if growth is not None:
        seed_growth(repository, growth)

    document = attribution(project(repository, stage, state))

    assert document["counted"] is False
    assert document["bond_trend"] == state
    # The bond core is a price index: said as its price, never a yield.
    assert document["bond_text"] == {"bull": "债券价格走强", "bear": "债券价格走弱"}[state]
    assert (document["driver"], document["text"]) == (driver, text)
    assert {key: document[key] for key in extra} == extra
    # An axis the row takes as any is still said to be unconfirmed.
    assert [item["reason"] for item in document["reasons"]] == (
        [] if growth is not None else ["growth_inflation_unconfirmed"]
    )
    assert "期限溢价归因未确认" in document["notes"]
    read = axes(document)
    if growth is not None:
        assert read["growth_inflation"] == {"up": "stronger", "down": "weaker"}[growth]


def test_the_axes_say_what_each_signal_read(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "easing")
    seed_growth(repository, "down")

    document = attribution(project(repository, FormalStage.STAGE_I, "bull"))

    policy, growth = document["axes"]
    assert (policy["axis"], policy["value"], policy["text"]) == ("policy", "easing", "宽松")
    signals = {item["indicator"]: item for item in policy["signals"]}
    assert signals["policy_rate"]["value"] == "cut"
    assert signals["lpr"]["value"] == signals["rrr"]["value"] == "none"
    assert (signals["dr007"]["value"], signals["dr007"]["means"]) == ("down", "easing")
    assert (growth["axis"], growth["value"], growth["text"]) == (
        "growth_inflation",
        "weaker",
        "走弱",
    )
    assert [item["indicator"] for item in growth["signals"]] == list(GROWTH)
    assert {item["value"] for item in growth["signals"]} == {"down"}


def test_funding_rates_falling_against_a_hike_split_the_policy_axis(tmp_path: Path) -> None:
    # Bonds bearish while funding rates fall: never put down to policy (stage VI's note).
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "split")
    seed_growth(repository, "down")

    document = attribution(project(repository, FormalStage.STAGE_V, "bear"))

    assert axes(document)["policy"] == "mixed"
    assert document["driver"] == "unclear"
    assert [item["reason"] for item in document["reasons"]] == ["policy_mixed"]
    assert document["reasons"][0]["text"] == "政策维度信号分化"


def test_a_combination_the_table_does_not_name_is_unclear(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "neutral")
    seed_growth(repository, "down")

    document = attribution(project(repository, FormalStage.STAGE_VI, "bear"))

    assert axes(document) == {"policy": "neutral", "growth_inflation": "weaker"}
    assert document["driver"] == "unclear"
    assert document["reasons"] == [{"reason": "not_in_table", "text": "两轴组合不在归因表中"}]


def test_an_axis_not_known_leaves_the_driver_unclear_and_says_what_it_misses(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    # No LPR, no DR007; and nothing of growth or inflation.
    seed_rate(repository, RATE_HISTORIES["unchanged"])

    document = attribution(project(repository, FormalStage.STAGE_IV, "bear"))

    assert axes(document) == {"policy": "unconfirmed", "growth_inflation": "unconfirmed"}
    assert document["driver"] == "unclear"
    reasons = {item["reason"]: item["text"] for item in document["reasons"]}
    assert set(reasons) == {"policy_unconfirmed", "growth_inflation_unconfirmed"}
    assert reasons["policy_unconfirmed"].startswith("政策维度未确认，缺：")
    assert "LPR" in reasons["policy_unconfirmed"] and "DR007" in reasons["policy_unconfirmed"]
    assert "政策利率" not in reasons["policy_unconfirmed"]
    policy = document["axes"][0]
    assert {item["indicator"] for item in policy["signals"] if item["missing"]} == {"lpr", "dr007"}


def test_a_signal_known_against_the_others_splits_the_axis_however_many_are_unknown(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    # The hike against DR007 falling: no LPR read, but no value of it could agree them.
    seed_rate(repository, RATE_HISTORIES["hike_in_july"])
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))

    document = attribution(project(repository, FormalStage.STAGE_VI, "bear"))

    assert axes(document)["policy"] == "mixed"


@pytest.mark.parametrize(
    ("only", "value"),
    [
        # Three of five rising: a majority whatever the other two read.
        (("pmi", "industrial_va", "ppi"), "stronger"),
        # Two of five: the other three could tip it.
        (("pmi", "ppi"), "unconfirmed"),
    ],
)
def test_growth_and_inflation_follow_their_majority(
    tmp_path: Path, only: tuple[str, ...], value: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_growth(repository, "up", only=only)

    document = attribution(project(repository, FormalStage.STAGE_IV, "bear"))

    assert axes(document)["growth_inflation"] == value


def test_growth_and_inflation_known_without_a_majority_have_none(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_growth(repository, "up", only=("pmi", "industrial_va"))
    seed_growth(repository, "down", only=("gdp", "ppi"))
    # PMI prices flat.
    seed_monthly(repository, "pmi_prices", year(50.0, 50.0, fill=50.0))

    document = attribution(project(repository, FormalStage.STAGE_IV, "bear"))

    growth = document["axes"][1]
    assert (growth["value"], growth["text"]) == ("mixed", "无多数方向")


def test_a_bond_core_with_no_state_standing_leaves_the_driver_unclear(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "neutral")
    seed_growth(repository, "up")

    document = attribution(project(repository, None, None))

    assert document["bond_trend"] is None
    assert document["bond_text"] == "债券核心状态未定"
    assert document["driver"] == "unclear"
    assert [item["reason"] for item in document["reasons"]] == ["bond_unknown"]


def test_a_combination_off_the_stages_still_attributes_the_bond(tmp_path: Path) -> None:
    # Every stage alike, and a combination of none: the bond's own trend is attributed.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "neutral")
    seed_growth(repository, "up")

    document = attribution(project(repository, None, "bear"))

    assert document["driver"] == "fundamentals"


def test_the_attribution_is_never_counted_nor_read_back_into_the_stage(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_policy(repository, "neutral")
    seed_growth(repository, "up")

    with_note = project(repository, FormalStage.STAGE_IV, "bear")
    without = project(repository, FormalStage.STAGE_IV, "bear", attribution=False)

    assert attribution(with_note)["driver"] == "fundamentals"
    assert "bond_attribution" not in without.macro
    # The summary, its relations and counts, and the stage it confirms are the same.
    assert with_note.macro["confirmation"] == without.macro["confirmation"]
    assert with_note.macro["confirmation"]["stage"] == "stage_iv"  # type: ignore[index]


def test_the_rules_are_frozen_in_the_manifest() -> None:
    rules = model_v0015_manifest()["confirmation_rules"]

    table = rules["bond_attribution"]["table"]
    assert [(row["bond"], row["driver"]) for row in table] == [
        ("bear", "fundamentals"),
        ("bear", "policy_liquidity"),
        ("bear", "unclear"),
        ("bull", "fundamentals_and_easing"),
        ("bull", "unclear"),
    ]


def _with(change: Any) -> dict[str, Any]:
    document = copy.deepcopy(model_v0015_manifest())
    change(document["confirmation_rules"]["bond_attribution"])
    return document


@pytest.mark.parametrize(
    "change",
    [
        # Growth and inflation are the overheat and price dimensions' alone.
        lambda rules: rules["axes"][1]["signals"].append(
            {"indicator": "money", "reading": "momentum", "means": {"up": "stronger"}}
        ),
        # The policy axis reads the policy dimension alone.
        lambda rules: rules["axes"][0]["signals"].append(
            {"indicator": "pmi", "reading": "momentum", "means": {"down": "easing"}}
        ),
        # An action is read of a policy action.
        lambda rules: rules["axes"][0]["signals"].append(
            {"indicator": "dr007", "reading": "action", "means": {"cut": "easing"}}
        ),
        lambda rules: rules["axes"][0]["signals"].append(
            {"indicator": "unknown", "reading": "momentum", "means": {"down": "easing"}}
        ),
        lambda rules: rules["table"].append(
            {"bond": "bull", "policy": ["loose"], "driver": "fundamentals"}
        ),
        lambda rules: rules["table"].append({"bond": "bull", "driver": "sentiment"}),
        lambda rules: rules["table"].append({"bond": "flat", "driver": "unclear"}),
        # A field misspelt would leave its axis taken as any.
        lambda rules: rules["table"][1].update(
            growth_inflaton=rules["table"][1].pop("growth_inflation")
        ),
        lambda rules: rules["axes"].pop(),
        # A signal read twice would count twice.
        lambda rules: rules["axes"][1]["signals"].append(rules["axes"][1]["signals"][0]),
        # A value its reading never takes.
        lambda rules: rules["axes"][0]["signals"][3]["means"].update(falling="easing"),
        lambda rules: rules["drivers"].pop("unclear"),
        lambda rules: rules["texts"].pop("term_premium"),
    ],
)
def test_rules_out_of_shape_are_refused(change: Any) -> None:
    with pytest.raises(ValueError, match="confirmation_bond_attribution_invalid"):
        ConfirmationRules.from_manifest(_with(change))


# Consumers.


def test_the_pages_and_the_report_input_show_it_beside_the_bond(tmp_path: Path) -> None:
    projection = confirmed(tmp_path)

    validate_analytical_projection(projection.envelope, projection.datasets)
    note = projection.datasets["macro"]["bond_attribution"]
    # The cores rising: the bond's price stronger; the policy axis not read.
    assert (note["bond_trend"], note["driver"]) == ("bull", "unclear")
    home = _text(dashboard_page("/", projection, (), ()))
    assert "债券归因" in home and "债券价格走强" in home and UNCLEAR in home
    assert "期限溢价归因未确认" in home
    page = _text(dashboard_page("/macro", projection, (), ()))
    assert "债券归因（不计数）" in page
    assert "政策维度未确认" in page and "期限溢价归因未确认" in page
    section = page.split("债券归因（不计数）")[1].split("国际环境")[0]
    assert "债券价格走强" in section
    assert "收益率上" not in section and "收益率下" not in section
    report = report_input_from_projection(projection)
    attributed = report.results["confirmation"]["bond_attribution"]
    assert (attributed["driver"], attributed["counted"]) == ("unclear", False)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda note: note.update(counted=True), "projection_confirmation_price_notes_invalid"),
        # The bond's trend as the core states it, never another.
        (lambda note: note.update(bond_trend="bear"), "projection_bond_attribution_invalid"),
        (lambda note: note.update(driver="sentiment"), "projection_bond_attribution_invalid"),
        # No bond state standing names no driver.
        (
            lambda note: note.update(bond_trend=None, driver="fundamentals"),
            "projection_bond_attribution_invalid",
        ),
    ],
)
def test_a_projection_rewriting_the_attribution_is_refused(
    tmp_path: Path, change: Any, error: str
) -> None:
    projection = confirmed(tmp_path)
    datasets = copy.deepcopy(projection.datasets)
    change(datasets["macro"]["bond_attribution"])

    with pytest.raises(ValueError, match=error):
        validate_analytical_projection(projection.envelope, datasets)


@pytest.mark.parametrize(
    ("title", "text", "outcome"),
    [
        ("债券", "债券推动力不明：政策维度未确认。", "succeeded"),
        ("债券", "债券价格走强，但推动力不明，不是基本面推动。", "succeeded"),
        ("债券", "债券上涨由基本面加宽松推动。", "conclusion_mutation_rejected"),
        ("债券", "债券归因：政策或流动性推动。", "conclusion_mutation_rejected"),
        ("债券", "债牛的推动力并非不明。", "conclusion_mutation_rejected"),
        # A negation set apart from the driver by "由".
        ("债券", "债券并非由基本面推动。", "succeeded"),
        ("债券", "债券上涨并不是由推动力不明所致。", "conclusion_mutation_rejected"),
        # The title runs into its paragraph, and on into the next sentence.
        ("债券归因", "基本面推动。", "conclusion_mutation_rejected"),
        ("债券", "债券价格走强。其上涨属于基本面推动。", "conclusion_mutation_rejected"),
        # Another subject's driver is not the bond's.
        ("股票", "股票上涨由基本面推动。", "succeeded"),
        ("债券", "债券推动力不明，股票则是基本面推动。", "succeeded"),
        # Once another subject takes over, the sentences after it are not the bond's.
        ("债券", "债券推动力不明，股票上涨。上涨由基本面推动。", "succeeded"),
        # A title naming the bond, the paragraph opening on another subject.
        ("债券与股票", "股票上涨由基本面推动；债券推动力不明。", "succeeded"),
        # Back to the bond in the same sentence.
        ("债券", "债券推动力不明，股票上涨，而债券由基本面推动。", "conclusion_mutation_rejected"),
    ],
)
def test_a_report_rewriting_the_bond_attribution_is_rejected(
    tmp_path: Path, title: str, text: str, outcome: str
) -> None:
    bundle = report_input_from_projection(confirmed(tmp_path))
    reports = ReportRepository.create(tmp_path / "reports.sqlite3")
    first = FakeAdapter(
        "codex_cli", AdapterResponse.succeeded(_document(bundle, text, title=title))
    )
    second = FakeAdapter("claude_code_cli", AdapterResponse.unavailable("fixture"))

    result = ReportService(reports, (first, second)).generate(bundle)

    assert reports.attempts(result.report_snapshot_id)[0].outcome == outcome
