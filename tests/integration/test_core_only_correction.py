"""A correction day whose context details left retention corrects its cores only (ticket 08).

Correcting a window day summarized on the old core history (ticket 07) recomputes it whole
at its own public cutoff. When a source claim its summary cited in its context is no longer
held -- it has left retention -- its context cannot be summarized again as it was: the
day's three cores and formal stage are still corrected, its context and confirmation are
marked not recomputed. A day that cannot be corrected even so is recorded, with why, and no
later run tries it again.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

import pring_cycle.context_projection as context_projection
import pring_cycle.day_summary as day_summary
from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.context_projection import build_context_projection
from pring_cycle.dashboard import dashboard_page
from pring_cycle.day_summary import DaySummaries, ModelRules
from pring_cycle.evidence import EvidenceRepository, EvidenceValueState, SourceClaimInput
from pring_cycle.models import ModelRepository
from pring_cycle.projections import ProjectionSetRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.trading_calendar import TradingCalendar
from tests.integration.test_confirmation_publish import (
    MODEL,
    register_confirmation_model,
    seed_pmi,
)
from tests.integration.test_core_carry_forward import CUTOFF, TARGET, seed_cores, sessions
from tests.integration.test_core_history_correction import (
    FIRST,
    REASON,
    SECOND,
    THIRD,
    Runtime,
    short_of_history,
)
from tests.integration.test_worker_execution import runtime
from tests.web.test_dashboard_contract import _text

SHANGHAI = ZoneInfo("Asia/Shanghai")


def m1_claim(paths: RuntimePaths, period: date, public: datetime) -> str:
    """A month's M1, public at ``public``: the context of each day it is the latest of
    cites it."""
    receipt = (
        AcquisitionRepository(paths.database, paths.artifacts)
        .capture(
            provider="fixture",
            api_name="fixture_m1",
            parameters={"month": period.strftime("%Y%m")},
            fields="m1_yoy",
            parser_version="fixture-parser",
            fetch=lambda: f"m1 {period}".encode(),
            parse=lambda raw: raw,
            normalize=lambda raw: raw.decode(),
        )
        .receipt
    )
    assert receipt.received_at and receipt.validated_at
    [claim] = EvidenceRepository(paths.database).append_source_claims(
        (
            SourceClaimInput(
                metric_id="CN_M1_M2",
                definition_version="metric-catalog-v0001",
                period_kind="month",
                period_start=period.replace(day=1).isoformat(),
                period_end=period.isoformat(),
                dimensions={"aggregate": "m1", "measure": "yoy"},
                value=4.0,
                value_state=EvidenceValueState.REPORTED_VALUE,
                unit="percent",
                provider="fixture",
                source_reference=f"fixture:m1:{period}",
                release_event_id=f"fixture:m1:{period}",
                release_at=public,
                public_available_at=public,
                fetched_at=receipt.received_at,
                available_at=receipt.validated_at,
                quality_status="validated",
                acquisition_id=receipt.acquisition_id,
            ),
        )
    )
    return claim.claim_id


def leave_retention(paths: RuntimePaths, claim_id: str) -> None:
    """The claim goes as retention drops one: its originals' links with it."""
    connection = sqlite3.connect(paths.database)
    try:
        with connection:
            guards = connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE '%_no_delete'"
            ).fetchall()
            for name, _sql in guards:
                connection.execute(f"DROP TRIGGER {name}")
            for table in ("claim_matched_quote", "source_claim_acquisition", "source_claim"):
                connection.execute(f"DELETE FROM {table} WHERE claim_id=?", (claim_id,))
            for _name, sql in guards:
                connection.execute(sql)
    finally:
        connection.close()


class Months:
    """M1 for January, March and May. The window's early days show January; those after
    show March, compared with January, the month before held; the later ones show May,
    compared with March. January has left retention by the second run."""

    def __init__(self, runtime: Runtime) -> None:
        self.january, self.march, self.may = (
            m1_claim(runtime.paths, period, datetime.combine(public, time(17), SHANGHAI))
            for period, public in (
                (date(2026, 1, 31), date(2026, 2, 13)),
                (date(2026, 3, 31), date(2026, 4, 14)),
                (date(2026, 5, 31), date(2026, 6, 12)),
            )
        )
        self.runtime = runtime

    def cited(self, day: str, claim_id: str) -> bool:
        """Whether the context of the day's latest summary cites the claim."""
        datasets = published(self.runtime, self.runtime.latest()[day])
        return claim_id in json.dumps([datasets["macro"], datasets["inventory"]])


def read_contexts(monkeypatch: pytest.MonkeyPatch, read: list[str]) -> None:
    """Each day whose context is built is added to ``read``."""

    def context(*args: Any, **kwargs: Any) -> Any:
        read.append(str(kwargs["target_business_date"]))
        return build_context_projection(*args, **kwargs)

    monkeypatch.setattr("pring_cycle.day_summary.build_context_projection", context)


def published(runtime: Runtime, event: dict[str, Any]) -> dict[str, Any]:
    return runtime.repository.get(str(event["projection_set_id"])).datasets


@pytest.mark.usefixtures("runtime_clock")
def test_a_correction_day_whose_context_left_retention_corrects_its_cores_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime(tmp_path, monkeypatch)
    months = Months(runtime)
    first = runtime.run(FIRST, old_reach=True)
    old = runtime.latest()
    window = runtime.window(first)
    cites_january = [day for day in window if months.cited(day, months.january)]
    # Shown on the window's first day, compared with to the day before May is out.
    assert cites_january == [day for day in window if day < "2026-06-12"]
    leave_retention(runtime.paths, months.january)
    read: list[str] = []
    requests_before = len(runtime.requests)

    with monkeypatch.context() as patch:
        read_contexts(patch, read)
        second = runtime.run(SECOND)
        second_requests = len(runtime.requests) - requests_before

        corrected = [day for day in runtime.window(second) if day < SECOND.isoformat()]
        core_only = [day for day in corrected if day in cites_january]
        whole_day = [day for day in corrected if day not in cites_january]
        assert core_only and whole_day
        latest = runtime.latest()
        for day in corrected:
            event = latest[day]
            assert not short_of_history(event), day
            assert event["corrects"] == {
                "assessment_id": old[day]["assessment_id"],
                "projection_set_id": old[day]["projection_set_id"],
                "reason": REASON,
                "scope": "core_only" if day in core_only else "whole_day",
            }
        # The cores and the formal stage are recomputed on the new history ...
        assert any(latest[day]["current_stage"] == "stage_iii" for day in core_only)
        assert runtime.repository.last_confirmed_stage(on_or_before=core_only[-1]) == "stage_iii"
        # ... while the context is not read, marked not recomputed and shows nothing, not
        # another day's details; a day whose details are all held is recomputed whole.
        assert not set(read) & set(core_only)
        for day in core_only:
            datasets = published(runtime, latest[day])
            for name in ("macro", "inventory"):
                assert datasets[name]["context_status"] == "not_recomputed", (day, name)
                assert datasets[name]["not_recomputed_reason"] == "details_past_retention"
            assert "confirmation" not in datasets["macro"]
            assert months.march not in json.dumps([datasets["macro"], datasets["inventory"]])
            assert datasets["cycle_overview"]["macro_confirmation"] == []
        for day in whole_day:
            assert "context_status" not in published(runtime, latest[day])["macro"]
            assert months.cited(day, months.may) and months.cited(day, months.march)
        plan = runtime.runs.full_retrieval_plan(second)
        assert plan["summary_corrections"] == {
            "reason": REASON,
            "corrected_days": corrected,
            "count": len(corrected),
            "whole_day": {"days": whole_day, "count": len(whole_day)},
            "core_only": {"days": core_only, "count": len(core_only)},
            "uncorrectable": {"days": [], "count": 0},
        }
        assert not _backfill_failures(runtime)
        # The stage history and its page mark the days corrected on their cores only.
        current = runtime.repository.current()
        page = _text(
            dashboard_page("/stage-history", current, (), (), runtime.repository.stage_history())
        )
        assert page.count("只更正核心") == len(core_only)
        assert page.count("更正版本") == len(corrected)

        read.clear()
        requests_before = len(runtime.requests)
        third = runtime.run(THIRD)

        # Corrected days are not summarized again, nor is any call added for them.
        assert runtime.runs.full_retrieval_plan(third)["summary_corrections"]["count"] == 0
        assert [day for day in read if day < SECOND.isoformat()] == []
        assert len(runtime.requests) - requests_before == second_requests


@pytest.mark.usefixtures("runtime_clock")
def test_a_correction_day_that_cannot_be_corrected_is_recorded_and_not_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = Runtime(tmp_path, monkeypatch)
    months = Months(runtime)
    first = runtime.run(FIRST, old_reach=True)
    old = runtime.latest()
    window = runtime.window(first)
    lost = window[30]
    cites_january = [day for day in window if months.cited(day, months.january)]
    leave_retention(runtime.paths, months.january)
    # From the day on, the commodity's sources conflict on a close of its window: no
    # correction day's commodity can be read from its closes, whether its context details
    # are held or not.
    whole = next(day for day in window if day not in cites_january)
    lost_days = [*(day for day in cites_january if day >= lost), whole]
    tried: list[str] = []
    with monkeypatch.context() as patch:
        _cores_read(patch, tried, conflicted=set(lost_days))
        second = runtime.run(SECOND)

        plan = runtime.runs.full_retrieval_plan(second)["summary_corrections"]
        assert plan["uncorrectable"] == {
            "days": [
                {"day": day, "reason": "core_uncomputable:commodity:source_conflict"}
                for day in lost_days
            ],
            "count": len(lost_days),
        }
        assert not set(lost_days) & set(plan["corrected_days"])
        assert window[29] in plan["core_only"]["days"]
        # Each keeps its summary as it was: nothing is published for it.
        latest = runtime.latest()
        assert all(latest[day] == old[day] for day in lost_days)
        assert not _backfill_failures(runtime)

        tried.clear()
        third = runtime.run(THIRD)

        # Recorded once, on the run's core history: no later run tries a day again.
        plan = runtime.runs.full_retrieval_plan(third)["summary_corrections"]
        assert plan["count"] == 0
        assert plan["uncorrectable"] == {"days": [], "count": 0}
        assert not set(lost_days) & set(tried)
        assert all(runtime.latest()[day] == old[day] for day in lost_days)


@pytest.mark.usefixtures("runtime_clock")
def test_other_errors_of_a_correction_day_still_fail_it_for_a_later_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A day whose details are all held is corrected whole, as in ticket 07: an error doing
    # so fails it, and a later run tries it again.
    runtime = Runtime(tmp_path, monkeypatch)
    first = runtime.run(FIRST, old_reach=True)
    day = runtime.window(first)[30]

    def failing_on_the_day(*args: Any, **kwargs: Any) -> Any:
        if kwargs["target_business_date"] == day:
            raise ValueError("fixture_context_error")
        return build_context_projection(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr("pring_cycle.day_summary.build_context_projection", failing_on_the_day)
        second = runtime.run(SECOND)

    plan = runtime.runs.full_retrieval_plan(second)["summary_corrections"]
    assert day not in plan["corrected_days"]
    assert plan["uncorrectable"]["count"] == 0
    assert _backfill_failures(runtime) == [f"backfill_day_failed:{day}:ValueError"]

    third = runtime.run(THIRD)

    assert runtime.runs.full_retrieval_plan(third)["summary_corrections"]["corrected_days"] == [day]


@pytest.mark.usefixtures("runtime_clock")
def test_a_core_s_own_claims_gone_are_no_context_detail_left_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The target day shows the commodity core among its prices, current, and its model
    # inputs gather the row's claims: those gone, as a core's claims refetched are, its
    # context is still held all the same.
    runtime = Runtime(tmp_path, monkeypatch)
    status: Callable[..., str] = context_projection._evidence_status

    def current_core(definition: Any, *args: Any, **kwargs: Any) -> str:
        if definition.metric_id == "CN_COMMODITY_CORE_NHII":
            return "current"
        return status(definition, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(context_projection, "_evidence_status", current_core)
        runtime.run(FIRST)
    projection_set_id = str(runtime.latest()[FIRST.isoformat()]["projection_set_id"])
    macro = published_set(runtime, projection_set_id)["macro"]
    [row] = [
        row
        for row in macro["price_chain"]["evidence"]
        if row["metric_id"] == "CN_COMMODITY_CORE_NHII"
    ]
    own = {*row["claim_ids"], *row["direction_input_observation_version_ids"]}
    assert own & set(macro["model_input_observation_version_ids"])
    for claim_id in own:
        leave_retention(runtime.paths, claim_id)

    assert runtime.repository.context_details_held(projection_set_id)


def published_set(runtime: Runtime, projection_set_id: str) -> dict[str, Any]:
    return runtime.repository.get(projection_set_id).datasets


def test_a_correction_day_whose_confirmation_read_a_claim_now_gone_corrects_its_cores_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The confirmation reads months the day's rows do not show: one of them gone, the day's
    # context cannot be summarized again as it was either.
    paths = runtime(tmp_path)
    seed_cores(paths)
    register_confirmation_model(paths)
    seed_pmi(paths, (50.2, 50.5, 51.0))
    repository = ProjectionSetRepository(paths.database)
    days = tuple(day.isoformat() for day in sessions()[-3:-1])
    target = TARGET.isoformat()
    with monkeypatch.context() as patch:
        patch.setattr(day_summary, "CORE_HISTORY_BASIS", "core-history-v0001")
        assert confirming(paths).backfill(days, target=target, system_as_of=CUTOFF) == ()
    old = {event["business_date"]: event for event in repository.stage_history()}
    # All it cites held, derived rows' own identities being none of them.
    assert all(repository.context_details_held(old[day]["projection_set_id"]) for day in days)
    macro = repository.get(old[days[0]]["projection_set_id"]).datasets["macro"]
    shown = json.dumps([value for key, value in macro.items() if key not in CONFIRMATION_READS])
    read_only = sorted(
        version
        for dimension in macro["confirmation"]["dimensions"]
        for indicator in dimension["key_indicators"]
        for member in indicator["members"]
        for version in member["observation_version_ids"]
        if version not in shown
    )
    assert read_only
    leave_retention(paths, read_only[0])

    later = CUTOFF + timedelta(days=1)
    assert confirming(paths).backfill(days, target=target, system_as_of=later) == ()

    latest = {event["business_date"]: event for event in repository.stage_history()}
    for day in days:
        assert latest[day]["corrects"]["scope"] == "core_only", day
        datasets = repository.get(str(latest[day]["projection_set_id"])).datasets
        assert datasets["macro"]["context_status"] == "not_recomputed"
        assert "confirmation" not in datasets["macro"]


# What a day's macro document holds of what its confirmation read.
CONFIRMATION_READS = ("confirmation", "model_input_observation_version_ids")


def confirming(paths: RuntimePaths) -> DaySummaries:
    return DaySummaries(
        EvidenceRepository(paths.database),
        ProjectionSetRepository(paths.database),
        ModelRules.of(ModelRepository(paths.database), MODEL),
        calendar=TradingCalendar(sessions()),
    )


def _cores_read(
    monkeypatch: pytest.MonkeyPatch, read: list[str], *, conflicted: set[str] = frozenset()
) -> None:
    """Each window day whose cores are read is added to ``read``; on the ``conflicted``
    days, the commodity's closes are read as its sources conflicting, as its gate states."""
    readiness: Callable[..., Any] = DaySummaries._core_readiness

    def reading(self: DaySummaries, day: str, **kwargs: Any) -> Any:
        read.append(day)
        cores = readiness(self, day, **kwargs)
        if day not in conflicted:
            return cores
        return tuple(
            replace(item, state=None, reason="source_conflict")
            if item.asset == "commodity"
            else item
            for item in cores
        )

    monkeypatch.setattr(DaySummaries, "_core_readiness", reading)


def _backfill_failures(runtime: Runtime) -> list[str]:
    log = runtime.paths.logs / "worker.jsonl"
    if not log.exists():
        return []
    events = (json.loads(line)["event_code"] for line in log.read_text("utf-8").splitlines())
    return [event for event in events if event.startswith("backfill_day_failed:")]
