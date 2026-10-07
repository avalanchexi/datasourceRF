"""The policy dimension against each stage's cells (ADR-0037, ticket 06).

The policy rate, the LPR and the RRR are read as their actions in the 120-session evidence
window: the latest cut or hike there, from the value in force before the window (the RRR's
own change needs none), or none. DR007 is read in periods of five sessions against the
policy rate in force; the seven-day reverse repo's net injection, its injection less what
matures seven days on (rolled to the next session), in periods of five sessions, never a
day not held read as nothing done.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import pring_cycle.evidence as evidence_module
from pring_cycle.batches import processing_batch
from pring_cycle.catalog import metric_definition
from pring_cycle.context_projection import ContextProjection, build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.domain import FormalStage, StageResult
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.reports import report_input_from_projection
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_confirmation_monthly_indicators import indicator
from tests.integration.test_confirmation_projection import confirmation_manifest
from tests.integration.test_confirmation_publish import (
    _NONE,
    MODEL,
    publish,
    register_confirmation_model,
)
from tests.integration.test_context_projection import _v2_manifest
from tests.integration.test_core_carry_forward import seed_cores, sessions
from tests.integration.test_worker_execution import runtime
from tests.web.test_dashboard_contract import _text

TARGET = "2026-09-15"
AS_OF = datetime(2026, 9, 16, tzinfo=UTC)
# The 120-session evidence window's first day.
WINDOW_START = "2026-03-23"
POLICY_METRICS = (
    "CN_OMO_7D_RATE",
    "CN_OMO_7D_AMOUNT",
    "CN_LPR_1Y_5Y",
    "CN_RRR_EVENT",
    "CN_DR007",
    "CN_SHIBOR_ON_1W_3M",
    "CN_TOOL_LIQUIDITY_MONTHLY",
)
HOLIDAYS = frozenset(
    date.fromisoformat(day) for day in ("2026-05-01", "2026-05-04", "2026-05-05", "2026-06-19")
)
SESSIONS = tuple(
    day
    for day in (date(2025, 1, 2) + timedelta(days=offset) for offset in range(640))
    if day.weekday() < 5 and day not in HOLIDAYS and day <= date(2026, 9, 30)
)
CALENDAR = TradingCalendar(SESSIONS, through=date(2026, 9, 30))
STAGES = tuple(FormalStage)


@pytest.fixture(autouse=True)
def certified(monkeypatch: pytest.MonkeyPatch) -> None:
    """The policy metrics' definitions certified, as their claims are."""

    def definition(  # type: ignore[no-untyped-def]
        metric_id: str,
        *,
        definition_version: str = "metric-catalog-v0002",
        database_path: Path | None = None,
    ):
        found = metric_definition(
            metric_id, definition_version=definition_version, database_path=database_path
        )
        if metric_id in POLICY_METRICS:
            return replace(found, certification_status="certified")
        return found

    monkeypatch.setattr(evidence_module, "metric_definition", definition)


def manifest() -> dict[str, Any]:
    return confirmation_manifest(_v2_manifest(*POLICY_METRICS))


def project(
    repository: EvidenceRepository,
    stage: FormalStage,
    *,
    window_start: str | None = WINDOW_START,
    calendar: TradingCalendar | None = CALENDAR,
) -> ContextProjection:
    return build_context_projection(
        repository,
        as_of=AS_OF,
        target_business_date=TARGET,
        visible_evidence_start=window_start,
        model_manifest=manifest(),
        formal_stage=StageResult(stage, stage, "canonical_combination"),
        calendar=calendar,
    )


def claim(
    repository: EvidenceRepository,
    metric_id: str,
    period: str,
    dimensions: dict[str, str],
    value: float,
    *,
    unit: str,
    definition_version: str = "metric-catalog-v0002",
) -> str:
    """One certified claim: of a day (``YYYY-MM-DD``) or of a month (``YYYY-MM``)."""
    if len(period) == 7:
        start = date.fromisoformat(f"{period}-01")
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        kind = "month"
        # Published on the 20th at 09:00, as the LPR is fixed.
        public = datetime(start.year, start.month, 20, 1, tzinfo=UTC)
    else:
        start = end = date.fromisoformat(period)
        kind = "business_day"
        public = datetime.combine(end, datetime.min.time(), tzinfo=UTC) + timedelta(hours=2)
    return repository.append_source_claim(
        SourceClaimInput(
            metric_id=metric_id,
            definition_version=definition_version,
            period_kind=kind,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            dimensions=dimensions,
            value=value,
            value_state=EvidenceValueState.REPORTED_VALUE,
            unit=unit,
            provider="certified-fixture",
            source_reference=f"fixture:{metric_id}:{sorted(dimensions.items())}:{period}",
            release_event_id=f"release:{metric_id}:{period}",
            release_at=public,
            public_available_at=public,
            fetched_at=public,
            available_at=public,
            certification_status="certified",
            quality_status="validated",
        )
    ).claim_id


def seed_rate(
    repository: EvidenceRepository,
    changes: dict[str, float],
    *,
    skip: tuple[str, ...] = (),
    definition_version: str = "metric-catalog-v0002",
    sessions: tuple[date, ...] = SESSIONS,
    target: str = TARGET,
) -> list[str]:
    """Each session's operation notice from the first change to the target: its 1,000
    put in, and the policy rate, each change in force from its day; none on ``skip``."""
    days = [
        day
        for day in (item.isoformat() for item in sessions)
        if min(changes) <= day <= target and day not in skip
    ]
    for day in days:
        claim(
            repository,
            "CN_OMO_7D_AMOUNT",
            day,
            {"measure": "injection"},
            1000.0,
            unit="hundred_million_cny",
            definition_version=definition_version,
        )
    return [
        claim(
            repository,
            "CN_OMO_7D_RATE",
            day,
            {},
            changes[max(item for item in changes if item <= day)],
            unit="percent",
            definition_version=definition_version,
        )
        for day in days
    ]


def seed_lpr(repository: EvidenceRepository, tenor: str, rates: dict[str, float]) -> None:
    for month, value in rates.items():
        claim(repository, "CN_LPR_1Y_5Y", month, {"tenor": tenor}, value, unit="percent")


def seed_rrr(repository: EvidenceRepository, day: str, change: float, released: float) -> None:
    scope = {"scope": "all_eligible_financial_institutions"}
    claim(
        repository,
        "CN_RRR_EVENT",
        day,
        {**scope, "measure": "rrr_change"},
        change,
        unit="percentage_points",
    )
    claim(
        repository,
        "CN_RRR_EVENT",
        day,
        {**scope, "measure": "released_funds"},
        released,
        unit="hundred_million_cny",
    )


# The policy rate's changes, from before the window on.
RATE_HISTORIES = {
    "cut_this_month": {"2026-03-16": 1.5, "2026-09-08": 1.4},
    "cut_in_may": {"2026-03-16": 1.5, "2026-05-20": 1.4},
    "unchanged": {"2026-03-16": 1.5},
    # Cut before the window: in force throughout it, no action in it.
    "cut_before_window": {"2026-02-09": 1.5, "2026-02-10": 1.4},
    "hike_in_july": {"2026-03-16": 1.4, "2026-07-01": 1.5},
}
# The session before the window: the rate in force there is the baseline.
BASELINE = "2026-03-20"
# Each history's relation in stages I to VI (expectation-table.md).
RATE_RELATIONS = {
    "cut_this_month": (
        "support",
        "support",
        "support",
        # A cut in stage IV is a sprout until it holds past grace or passes on.
        "observation_only",
        "observation_only",
        "support",
    ),
    "cut_in_may": (
        "support",
        "support",
        "support",
        "counterevidence",
        "observation_only",
        "support",
    ),
    "unchanged": (
        "observation_only",
        "observation_only",
        "support",
        "support",
        "support",
        "support",
    ),
    "cut_before_window": (
        "observation_only",
        "observation_only",
        "support",
        "support",
        "support",
        "support",
    ),
    "hike_in_july": (
        "counterevidence",
        "counterevidence",
        "observation_only",
        "support",
        "support",
        "observation_only",
    ),
}


@pytest.mark.parametrize("history", sorted(RATE_HISTORIES))
@pytest.mark.parametrize("stage", STAGES, ids=lambda stage: stage.value)
def test_the_policy_rate_reads_its_latest_action_in_the_window(
    tmp_path: Path, history: str, stage: FormalStage
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES[history])

    policy_rate = indicator(project(repository, stage), "policy_rate")

    assert policy_rate["dimension"] == "policy"
    assert policy_rate["timing"] == "leading"
    assert policy_rate["relation"] == RATE_RELATIONS[history][STAGES.index(stage)]
    main = policy_rate["members"][0]
    expected_action = {
        "cut_this_month": "cut",
        "cut_in_may": "cut",
        "unchanged": "none",
        "cut_before_window": "none",
        "hike_in_july": "hike",
    }[history]
    assert main["action"] == expected_action
    assert main["window_start"] == WINDOW_START
    assert main["baseline"]["period"] == BASELINE


def test_a_cut_in_stage_iv_is_a_sprout_then_counterevidence_past_grace(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_this_month"])

    policy_rate = indicator(project(repository, FormalStage.STAGE_IV), "policy_rate")

    assert policy_rate["turn"]["maturity"] == "sprout"
    assert policy_rate["grace"]["past"] is False
    assert policy_rate["grace"]["unit"] == "month"
    assert policy_rate["members"][0]["actions"] == [
        {"period": "2026-09-08", "action": "cut", "change": pytest.approx(-0.1), "released": None}
    ]


def test_stage_vi_and_v_say_where_a_cut_points(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_in_may"])

    assert indicator(project(repository, FormalStage.STAGE_VI), "policy_rate")["turn_hint"] == (
        "stage_i"
    )
    assert indicator(project(repository, FormalStage.STAGE_V), "policy_rate")["turn_hint"] == (
        "stage_vi"
    )


def test_a_policy_rate_with_no_value_before_the_window_is_unconfirmed(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, {WINDOW_START: 1.5, "2026-09-10": 1.4})

    policy_rate = indicator(project(repository, FormalStage.STAGE_I), "policy_rate")

    assert policy_rate["relation"] == "unconfirmed"
    # Neither the rate in force nor the notice of the session before the window.
    assert policy_rate["missing"] == ["omo_7d:baseline_before:2026-03-23", "omo_7d:2026-03-20"]


def test_a_session_s_notice_not_held_leaves_the_policy_rate_unconfirmed(tmp_path: Path) -> None:
    # A gap may hide a cut and a hike: the history is whole or nothing is said.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(
        repository, RATE_HISTORIES["unchanged"], skip=("2026-06-09", "2026-06-10", "2026-07-01")
    )

    policy_rate = indicator(project(repository, FormalStage.STAGE_III), "policy_rate")

    assert policy_rate["relation"] == "unconfirmed"
    assert policy_rate["missing"] == ["omo_7d:2026-06-09..2026-06-10", "omo_7d:2026-07-01"]


def test_actions_are_unconfirmed_without_an_evidence_window(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_in_may"])

    policy_rate = indicator(
        project(repository, FormalStage.STAGE_I, window_start=None), "policy_rate"
    )

    assert policy_rate["relation"] == "unconfirmed"
    assert policy_rate["missing"] == ["omo_7d:evidence_window_unknown"]


LPR_MONTHS = ("2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08")
# Cut on 20 June, after the fixing in force before the window (20 March).
CUT_IN_JUNE = (3.1, 3.1, 3.1, 3.1, 3.0, 3.0, 3.0)


@pytest.mark.parametrize(
    ("five_year", "relation", "consistency"),
    [
        ((3.6, 3.6, 3.6, 3.6, 3.5, 3.5, 3.5), "support", "consistent"),
        # The five-year unchanged is flat, not a split.
        ((3.6,) * 7, "support", "consistent"),
        # The five-year raised against the one-year's cut splits them.
        ((3.6, 3.6, 3.6, 3.6, 3.7, 3.7, 3.7), "observation_only", "divergent"),
    ],
)
def test_the_lpr_reads_the_one_year_s_action_with_the_five_year_beside_it(
    tmp_path: Path,
    five_year: tuple[float, ...],
    relation: str,
    consistency: str,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_lpr(repository, "1y", dict(zip(LPR_MONTHS, CUT_IN_JUNE, strict=True)))
    seed_lpr(repository, "5y_plus", dict(zip(LPR_MONTHS, five_year, strict=True)))

    lpr = indicator(project(repository, FormalStage.STAGE_I), "lpr")

    assert lpr["relation"] == relation
    assert lpr["consistency"] == consistency
    main = lpr["members"][0]
    assert main["action"] == "cut"
    # Dated the day each fixing was published, not its month's end.
    assert main["baseline"]["period"] == "2026-03-20"
    assert [item["period"] for item in main["actions"]] == ["2026-06-20"]


@pytest.mark.parametrize("stage", STAGES, ids=lambda stage: stage.value)
def test_the_lpr_answers_each_stage_as_the_policy_rate_does(
    tmp_path: Path, stage: FormalStage
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for tenor, rates in (("1y", CUT_IN_JUNE), ("5y_plus", tuple(r + 0.5 for r in CUT_IN_JUNE))):
        seed_lpr(repository, tenor, dict(zip(LPR_MONTHS, rates, strict=True)))

    lpr = indicator(project(repository, stage), "lpr")

    # Held from June past two months' grace: stage IV's counterevidence.
    assert lpr["relation"] == RATE_RELATIONS["cut_in_may"][STAGES.index(stage)]


@pytest.mark.parametrize(
    ("window_start", "action"),
    [
        # Fixed on 20 March, before the window opens: the baseline, no action in it.
        (WINDOW_START, "none"),
        # A window opening before the 20th has the March cut in it.
        ("2026-03-16", "cut"),
    ],
)
def test_an_lpr_fixing_is_in_the_window_by_the_day_it_was_published(
    tmp_path: Path, window_start: str, action: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    cut_in_march = (3.1, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0)
    for tenor in ("1y", "5y_plus"):
        seed_lpr(repository, tenor, dict(zip(LPR_MONTHS, cut_in_march, strict=True)))

    lpr = indicator(project(repository, FormalStage.STAGE_I, window_start=window_start), "lpr")

    assert lpr["members"][0]["action"] == action


def test_an_lpr_month_due_and_not_held_leaves_it_unconfirmed(tmp_path: Path) -> None:
    # Fixed in August and due by the target day: not held, the cut may be undone.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for tenor in ("1y", "5y_plus"):
        seed_lpr(repository, tenor, dict(zip(LPR_MONTHS[:-1], CUT_IN_JUNE[:-1], strict=True)))

    lpr = indicator(project(repository, FormalStage.STAGE_I), "lpr")

    assert lpr["relation"] == "unconfirmed"
    assert lpr["missing"] == ["tenor=1y:2026-08"]


def test_an_lpr_month_not_held_leaves_it_unconfirmed(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for tenor in ("1y", "5y_plus"):
        seed_lpr(
            repository,
            tenor,
            {
                month: rate
                for month, rate in zip(LPR_MONTHS, CUT_IN_JUNE, strict=True)
                if month != "2026-05"
            },
        )

    lpr = indicator(project(repository, FormalStage.STAGE_I), "lpr")

    assert lpr["relation"] == "unconfirmed"
    assert lpr["missing"] == ["tenor=1y:2026-05"]


def test_an_lpr_with_no_quote_before_the_window_is_unconfirmed(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for tenor in ("1y", "5y_plus"):
        seed_lpr(repository, tenor, dict.fromkeys(LPR_MONTHS[2:], 3.0))

    lpr = indicator(project(repository, FormalStage.STAGE_I), "lpr")

    assert lpr["relation"] == "unconfirmed"
    assert lpr["missing"] == ["tenor=1y:baseline_before:2026-03-23"]


@pytest.mark.parametrize(
    ("events", "relations"),
    [
        # A cut in the window: counterevidence at once in stage IV, observed in stage V.
        (
            (("2026-05-15", -0.5, 10000.0),),
            ("support",) * 3 + ("counterevidence", "observation_only", "support"),
        ),
        # The latest change long before it: no action in the window.
        ((("2025-05-15", -0.5, 10000.0),), ("observation_only",) * 2 + ("support",) * 4),
        (
            (("2026-06-15", 0.5, -8000.0),),
            ("counterevidence",) * 2
            + ("observation_only",)
            + ("support",) * 2
            + ("observation_only",),
        ),
    ],
)
def test_the_rrr_reads_its_events_in_the_window(
    tmp_path: Path, events: tuple[tuple[str, float, float], ...], relations: tuple[str, ...]
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    for day, change, released in events:
        seed_rrr(repository, day, change, released)

    for stage, relation in zip(STAGES, relations, strict=True):
        rrr = indicator(project(repository, stage), "rrr")
        assert (stage, rrr["relation"]) == (stage, relation)
    actions = rrr["members"][0]["actions"]
    in_window = [day for day, *_rest in events if day >= WINDOW_START]
    assert [item["period"] for item in actions] == in_window
    if in_window:
        assert actions[0]["released"] == events[0][2]


def test_an_rrr_traced_to_the_source_s_end_with_none_found_is_no_action(
    tmp_path: Path,
) -> None:
    # The run read the chronicle to its end without a change: nothing is owed (ADR-0028).
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    with sqlite3.connect(tmp_path / "evidence.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE full_run_gap_plan (run_id TEXT, phase TEXT, document_json TEXT, "
            "document_hash TEXT)"
        )
        connection.execute(
            "INSERT INTO full_run_gap_plan VALUES ('run-traced', 'event_backtrack', ?, '')",
            (json.dumps({"metrics": {"CN_RRR_EVENT": "none_found"}}),),
        )

    with processing_batch("run-traced"):
        rrr = indicator(project(repository, FormalStage.STAGE_III), "rrr")

    assert rrr["relation"] == "support"
    assert rrr["members"][0]["action"] == "none"


def test_an_rrr_never_traced_is_unconfirmed(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")

    rrr = indicator(project(repository, FormalStage.STAGE_I), "rrr")

    assert rrr["relation"] == "unconfirmed"
    assert rrr["missing"] == ["measure=rrr_change:missing"]


def sessions_to(day: str, count: int) -> tuple[str, ...]:
    """The last ``count`` sessions to ``day``, oldest first."""
    return tuple(
        item.isoformat() for item in CALENDAR.sessions_back(date.fromisoformat(day), count)
    )


def seed_blocks(
    repository: EvidenceRepository,
    metric_id: str,
    dimensions: dict[str, str],
    blocks: tuple[float, ...],
    *,
    unit: str = "percent",
    skip: tuple[str, ...] = (),
) -> list[str]:
    """Each period of five sessions to the target at its value, oldest first."""
    days = sessions_to(TARGET, 5 * len(blocks))
    return [
        claim(repository, metric_id, day, dimensions, blocks[index // 5], unit=unit)
        for index, day in enumerate(days)
        if day not in skip
    ]


# Fifty-two periods: a year's range and the two grace reads before it.
def dr007_blocks(*newest: float, fill: float = 1.6) -> tuple[float, ...]:
    return (fill,) * (52 - len(newest)) + newest


@pytest.mark.parametrize(
    ("blocks", "policy_rate", "stage", "relation"),
    [
        # Falling below the policy rate.
        (dr007_blocks(1.5, 1.45, 1.35), 1.4, FormalStage.STAGE_I, "support"),
        # Rising above it.
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.4, FormalStage.STAGE_I, "counterevidence"),
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.4, FormalStage.STAGE_III, "observation_only"),
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.4, FormalStage.STAGE_IV, "support"),
        # High in its year: stage V's support.
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.6, FormalStage.STAGE_V, "support"),
        # Low and steady, above a lower policy rate: stage II's support all the same.
        (dr007_blocks(1.3, 1.3, 1.3, 1.3), 1.2, FormalStage.STAGE_II, "support"),
        # Falling below it in stage IV: a sprout, waiting on grace.
        (dr007_blocks(1.5, 1.45, 1.35), 1.4, FormalStage.STAGE_IV, "observation_only"),
        # Falling while still above the rate and high in its year: stage V's support.
        (dr007_blocks(1.8, 1.75, 1.7, fill=1.4), 1.6, FormalStage.STAGE_V, "support"),
        # Stage VI: a fall supports and points to stage I; a rise is observed.
        (dr007_blocks(1.5, 1.45, 1.35), 1.4, FormalStage.STAGE_VI, "support"),
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.4, FormalStage.STAGE_VI, "observation_only"),
        # Stage II: rising above the rate.
        (dr007_blocks(1.45, 1.5, 1.55, fill=1.4), 1.4, FormalStage.STAGE_II, "counterevidence"),
    ],
)
def test_dr007_reads_its_periods_against_the_policy_rate(
    tmp_path: Path,
    blocks: tuple[float, ...],
    policy_rate: float,
    stage: FormalStage,
    relation: str,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    # The policy rate in force over the newest periods.
    seed_rate(repository, {"2026-08-03": policy_rate})
    seed_blocks(repository, "CN_DR007", {}, blocks)

    dr007 = indicator(project(repository, stage), "dr007")

    assert dr007["relation"] == relation
    main = dr007["members"][0]
    assert main["period_sessions"] == 5
    assert main["period"] == TARGET
    assert main["value"] == pytest.approx(blocks[-1])
    assert main["lines"][-1] == policy_rate
    spread = dr007["derived"][0]
    assert spread["counted"] is False
    assert spread["value"] == pytest.approx((blocks[-1] - policy_rate) * 100)


def test_a_dr007_day_not_held_leaves_it_unconfirmed(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, {"2026-08-03": 1.4})
    gap = sessions_to(TARGET, 100)[0]
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35), skip=(gap,))

    dr007 = indicator(project(repository, FormalStage.STAGE_I), "dr007")

    assert dr007["relation"] == "unconfirmed"
    assert dr007["missing"] == [f"dr007:{gap}"]


def test_daily_indicators_need_the_sse_calendar(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, {"2026-08-03": 1.4})
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))

    context = project(repository, FormalStage.STAGE_I, calendar=TradingCalendar())

    assert indicator(context, "dr007")["missing"] == ["dr007:trading_calendar_incomplete"]
    assert indicator(context, "liquidity")["missing"] == [
        "net_injection:trading_calendar_incomplete"
    ]


def test_shibor_against_dr007_splits_them(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, {"2026-08-03": 1.4})
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))
    seed_blocks(repository, "CN_SHIBOR_ON_1W_3M", {"tenor": "1w"}, (1.4, 1.45, 1.5))

    dr007 = indicator(project(repository, FormalStage.STAGE_I), "dr007")

    assert dr007["consistency"] == "divergent"
    assert dr007["relation"] == "observation_only"
    assert dr007["members"][1]["momentum"] == "up"


@pytest.mark.parametrize("acted", ["policy_rate", "lpr"])
def test_dr007_not_falling_after_a_cut_is_observed_not_counted_against(
    tmp_path: Path, acted: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    if acted == "policy_rate":
        seed_rate(repository, RATE_HISTORIES["cut_in_may"])
    else:
        seed_rate(repository, {"2026-08-03": 1.4})
        for tenor in ("1y", "5y_plus"):
            seed_lpr(repository, tenor, dict(zip(LPR_MONTHS, CUT_IN_JUNE, strict=True)))
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.45, 1.5, 1.55, fill=1.4))

    context = project(repository, FormalStage.STAGE_I)

    # The action supports; DR007, risen above the rate, is observed only (D1).
    assert indicator(context, acted)["relation"] == "support"
    dr007 = indicator(context, "dr007")
    assert dr007["relation"] == "observation_only"
    assert dr007["capped_by"] == [
        {"policy_rate": "政策利率已下调而 DR007 未降", "lpr": "LPR 已下调而 DR007 未降"}[acted]
    ]


@pytest.mark.parametrize(
    ("stage", "policy_relation"),
    [
        # A cut held past grace is stage IV's counterevidence, a cut of any maturity stage
        # V's observation, as their cells say; DR007 risen above the rate is observed in
        # both, never support nor counterevidence (D1 in every stage: user, 2026-10-07).
        (FormalStage.STAGE_IV, "counterevidence"),
        (FormalStage.STAGE_V, "observation_only"),
    ],
)
def test_dr007_not_falling_after_a_cut_is_observed_in_stages_iv_and_v_too(
    tmp_path: Path, stage: FormalStage, policy_relation: str
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_in_may"])
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.45, 1.5, 1.55, fill=1.4))

    context = project(repository, stage)

    assert indicator(context, "policy_rate")["relation"] == policy_relation
    dr007 = indicator(context, "dr007")
    # Without the cut, rising above the rate is support in both stages.
    assert dr007["relation"] == "observation_only"
    assert dr007["capped_by"] == ["政策利率已下调而 DR007 未降"]


def test_dr007_rising_supports_stage_iv_with_no_cut(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["unchanged"])
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.45, 1.5, 1.55, fill=1.4))

    dr007 = indicator(project(repository, FormalStage.STAGE_IV), "dr007")

    assert dr007["relation"] == "support"
    assert dr007["capped_by"] == []


@pytest.mark.parametrize("key", ["policy_rate", "lpr"])
def test_a_cut_passed_on_to_dr007_confirms_the_policy_rate_and_the_lpr_alike(
    tmp_path: Path, key: str
) -> None:
    # A cut within two months' grace -- the policy rate's in September, the LPR's fixed on
    # 20 August -- confirmed by DR007's periods falling (user, 2026-10-07).
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_this_month" if key == "policy_rate" else "unchanged"])
    if key == "lpr":
        cut_in_august = (3.1, 3.1, 3.1, 3.1, 3.1, 3.1, 3.0)
        for tenor, offset in (("1y", 0.0), ("5y_plus", 0.5)):
            seed_lpr(
                repository,
                tenor,
                {
                    month: rate + offset
                    for month, rate in zip(LPR_MONTHS, cut_in_august, strict=True)
                },
            )
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))

    action = indicator(project(repository, FormalStage.STAGE_IV), key)

    assert action["relation"] == "counterevidence"
    assert action["turn"]["maturity"] == "confirmed"
    assert action["grace"]["confirmed_by"] == "transmission"


def test_dr007_falling_before_the_cut_does_not_pass_it_on(tmp_path: Path) -> None:
    # Cut on the target day, the last of DR007's newest period: its fall came before it.
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, {"2026-03-16": 1.5, TARGET: 1.4})
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))

    policy_rate = indicator(project(repository, FormalStage.STAGE_IV), "policy_rate")

    assert policy_rate["relation"] == "observation_only"
    assert policy_rate["turn"]["maturity"] == "sprout"
    assert policy_rate["grace"]["confirmed_by"] is None


def test_a_cut_passed_on_to_dr007_is_confirmed_within_grace(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_this_month"])
    seed_blocks(repository, "CN_DR007", {}, dr007_blocks(1.5, 1.45, 1.35))

    policy_rate = indicator(project(repository, FormalStage.STAGE_IV), "policy_rate")

    assert policy_rate["relation"] == "counterevidence"
    assert policy_rate["turn"]["maturity"] == "confirmed"
    assert policy_rate["grace"]["confirmed_by"] == "transmission"


def seed_injections(
    repository: EvidenceRepository,
    newest: tuple[float, ...],
    *,
    fill: float = 1000.0,
    skip: tuple[str, ...] = (),
) -> None:
    """Each session's seven-day injection, a period's five alike, the newest last; the
    periods before them, and the lead before those, at ``fill``."""
    blocks = (fill,) * (16 - len(newest)) + newest
    seed_blocks(
        repository,
        "CN_OMO_7D_AMOUNT",
        {"measure": "injection"},
        blocks,
        unit="hundred_million_cny",
        skip=skip,
    )


@pytest.mark.parametrize(
    ("newest", "stage", "relation", "level", "momentum"),
    [
        # Put in more, then less: withdrawal widening two periods running.
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_I, "counterevidence", "below", "down"),
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_III, "observation_only", "below", "down"),
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_IV, "support", "below", "down"),
        # A surge: a net injection, and markedly more.
        ((3000.0,), FormalStage.STAGE_I, "support", "above", "up"),
        ((3000.0,), FormalStage.STAGE_IV, "observation_only", "above", "up"),
        # Steady: neither, and no change.
        ((), FormalStage.STAGE_III, "support", "at", "flat"),
        ((), FormalStage.STAGE_I, "observation_only", "at", "flat"),
        ((), FormalStage.STAGE_II, "support", "at", "flat"),
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_II, "counterevidence", "below", "down"),
        ((3000.0,), FormalStage.STAGE_V, "observation_only", "above", "up"),
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_V, "support", "below", "down"),
        ((3000.0,), FormalStage.STAGE_VI, "support", "above", "up"),
        ((1200.0, 1100.0, 900.0), FormalStage.STAGE_VI, "observation_only", "below", "down"),
    ],
)
def test_net_injection_reads_both_layers(
    tmp_path: Path,
    newest: tuple[float, ...],
    stage: FormalStage,
    relation: str,
    level: str,
    momentum: str,
) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_injections(repository, newest)

    liquidity = indicator(project(repository, stage), "liquidity")

    assert liquidity["relation"] == relation
    main = liquidity["members"][0]
    # Net injection or withdrawal, and more or less than the period before.
    assert (main["level"], main["momentum"]) == (level, momentum)
    assert main["period"] == TARGET


def test_a_day_with_nothing_done_is_zero_and_a_day_not_held_is_unconfirmed(
    tmp_path: Path,
) -> None:
    done_nothing = EvidenceRepository.create(tmp_path / "zero.sqlite3")
    seed_injections(done_nothing, (0.0,))
    not_held = EvidenceRepository.create(tmp_path / "gap.sqlite3")
    gap = sessions_to(TARGET, 3)[0]
    seed_injections(not_held, (), skip=(gap,))

    zero = indicator(project(done_nothing, FormalStage.STAGE_IV), "liquidity")
    unknown = indicator(project(not_held, FormalStage.STAGE_IV), "liquidity")

    # Nothing put in while 5,000 matured: a net withdrawal, never a gap.
    assert zero["members"][0]["value"] == pytest.approx(-5000.0)
    assert zero["relation"] == "support"
    assert unknown["relation"] == "unconfirmed"
    assert unknown["missing"] == [f"net_injection:{gap}"]


def test_an_injection_maturing_in_the_periods_read_must_be_held(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    # Put in a week before the newest period's first session: it matures in that period.
    gap = sessions_to(TARGET, 10)[0]
    seed_injections(repository, (), skip=(gap,))

    liquidity = indicator(project(repository, FormalStage.STAGE_IV), "liquidity")

    assert liquidity["relation"] == "unconfirmed"
    assert gap in liquidity["members"][0]["missing"]


def test_a_maturity_the_notice_reports_is_read_before_one_rolled_on(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_injections(repository, ())
    claim(
        repository,
        "CN_OMO_7D_AMOUNT",
        TARGET,
        {"measure": "maturity"},
        3000.0,
        unit="hundred_million_cny",
    )

    liquidity = indicator(project(repository, FormalStage.STAGE_IV), "liquidity")

    # 1,000 put in on the target day against 3,000 reported maturing, the others even.
    assert liquidity["members"][0]["value"] == pytest.approx(-2000.0)


def test_a_make_up_working_day_s_injection_counts_with_the_next_session(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_injections(repository, ())
    # A Saturday worked: put in then, maturing after the target day.
    claim(
        repository,
        "CN_OMO_7D_AMOUNT",
        "2026-09-12",
        {"measure": "injection"},
        500.0,
        unit="hundred_million_cny",
    )

    liquidity = indicator(project(repository, FormalStage.STAGE_I), "liquidity")

    assert liquidity["members"][0]["value"] == pytest.approx(500.0)
    assert liquidity["relation"] == "support"


def test_the_monthly_tool_liquidity_shows_agreement_only(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_injections(repository, (3000.0,))
    tool = {"tool": "短期逆回购", "measure": "net_injection"}
    for month, value in (("2026-06", 900.0), ("2026-07", 600.0), ("2026-08", 300.0)):
        claim(
            repository, "CN_TOOL_LIQUIDITY_MONTHLY", month, tool, value, unit="hundred_million_cny"
        )

    liquidity = indicator(project(repository, FormalStage.STAGE_I), "liquidity")

    assert liquidity["members"][1]["momentum"] == "down"
    assert liquidity["consistency"] == "divergent"
    assert liquidity["relation"] == "observation_only"


def test_the_policy_dimension_counts_its_five_indicators(tmp_path: Path) -> None:
    repository = EvidenceRepository.create(tmp_path / "evidence.sqlite3")
    seed_rate(repository, RATE_HISTORIES["cut_in_may"])

    context = project(repository, FormalStage.STAGE_I)

    policy = next(
        item
        for item in context.macro["confirmation"]["dimensions"]  # type: ignore[index]
        if item["dimension"] == "policy"
    )
    assert policy["status"] == "connected"
    assert [item["key"] for item in policy["key_indicators"]] == [
        "policy_rate",
        "lpr",
        "rrr",
        "liquidity",
        "dr007",
    ]
    # The policy rate cut; its notices' steady injections, no net either way, observed;
    # the LPR, the RRR and DR007 not held.
    assert policy["counts"]["support"] == 1
    assert policy["counts"]["observation_only"] == 1
    assert policy["counts"]["unconfirmed"] == 3


def test_the_policy_dimension_reaches_the_pages_and_the_report(tmp_path: Path) -> None:
    # Stage III, the policy rate cut in June and held: support; the window's calendar
    # reaches no year back, so DR007 is not read.
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths, certified=("CN_PMI_ACTIVITY", "CN_OMO_7D_RATE"))
    seed_rate(
        EvidenceRepository(paths.database),
        {"2026-03-02": 1.5, "2026-06-15": 1.4},
        definition_version="metric-catalog-v0001",
        sessions=tuple(sessions()),
        target="2026-08-28",
    )

    projection = publish(paths, MODEL)

    bundle = report_input_from_projection(projection)
    assert bundle.conclusions["key_indicator:policy_rate"] == "support"
    # The notices' steady injections are stage III's steady liquidity too.
    assert bundle.conclusions["dimension:policy"] == {**_NONE, "support": 2, "unconfirmed": 3}
    reading = bundle.results["confirmation"]["key_indicators"]["policy_rate"]
    assert reading["members"][0]["action"] == "cut"
    # The rate on the session before the window (from 2026-03-16).
    assert reading["members"][0]["baseline"] == {"period": "2026-03-13", "value": 1.5}
    home = _text(dashboard_page("/", projection, (), ()))
    macro = _text(dashboard_page("/macro", projection, (), ()))
    assert "政策利率：支持" in home and "DR007：未确认" in home
    assert "窗口内最近动作：下调（2026-06-15" in macro
    assert "窗口前基准 2026-03-13 值 1.5" in macro
    assert "dr007:trading_calendar_incomplete" in macro
