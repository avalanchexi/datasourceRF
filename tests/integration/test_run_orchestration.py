from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.runs import RunRepository
from pring_cycle.storage import migrate_database
from tests.fixtures.attempt_reads import AttemptRowCounter
from tests.integration.test_receipt_counts import _upgrade

NOW = datetime(2026, 8, 28, 10, tzinfo=UTC)


def test_duplicate_manual_commands_share_one_authoritative_run(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")

    first = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    duplicate_request = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW + timedelta(minutes=1),
    )
    duplicate_click = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-2",
        model_version_id="model-v0001",
        system_as_of=NOW + timedelta(minutes=2),
    )

    assert first.run_id == duplicate_request.run_id == duplicate_click.run_id
    stored = runs.get(first.run_id)
    assert stored.system_as_of == NOW
    assert stored.attempt_count == 2
    assert runs.count() == 1


def test_active_lease_cannot_be_taken_and_stale_owner_only_interrupts(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    runs.acquire_lease(run.run_id, owner_id="worker-1", process_id=101, now=NOW)

    with pytest.raises(ValueError, match="worker_lease_active"):
        runs.acquire_lease(
            run.run_id,
            owner_id="worker-2",
            process_id=202,
            now=NOW + timedelta(seconds=119),
        )

    decision = runs.audit_lease(
        now=NOW + timedelta(seconds=121),
        process_is_alive=lambda _process_id: False,
    )

    assert decision.owner_state == "stale"
    assert decision.next_action == "explicit_resume_required"
    assert runs.get(run.run_id).status == "interrupted"
    assert runs.get(run.run_id).recoverable is True


def test_resume_preserves_run_identity_cutoff_and_budget(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    runs.set_budget_consumption(run.run_id, tavily=3, exa=1, ai_websearch=0)
    runs.advance(run.run_id, "preflight")
    runs.advance(run.run_id, "refreshing_evidence")
    runs.mark_interrupted(run.run_id, "worker_process_lost")

    with pytest.raises(ValueError, match="external_resume_confirmation_required"):
        runs.resume(run.run_id, client_request_id="resume-1", confirm_external_calls=False)

    resumed = runs.resume(
        run.run_id,
        client_request_id="resume-1",
        confirm_external_calls=True,
    )

    assert resumed.run_id == run.run_id
    assert resumed.system_as_of == NOW
    assert resumed.attempt_count == 2
    assert resumed.consumed_budget == {"tavily": 3, "exa": 1, "ai_websearch": 0}
    assert resumed.status == "queued"
    assert resumed.current_step == "queued"


def test_only_verified_checkpoints_are_reusable(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    runs.record_checkpoint(run.run_id, "verified_evidence", "artifact-1", verified=True)
    runs.record_checkpoint(run.run_id, "partial_download", "artifact-2", verified=False)
    runs.record_checkpoint(run.run_id, "unpublished_projection", "projection-1", verified=False)

    assert runs.reusable_checkpoints(run.run_id) == (
        {"kind": "verified_evidence", "reference": "artifact-1"},
    )


def test_cancel_preserves_an_already_published_projection(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="click-1",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    runs.link_projection(run.run_id, "projection-1")
    runs.cancel(run.run_id)

    cancelled = runs.get(run.run_id)
    assert cancelled.status == "cancelled"
    assert cancelled.projection_set_id == "projection-1"
    assert cancelled.next_action == "none"
    with pytest.raises(ValueError, match="run_is_terminal"):
        runs.advance(run.run_id, "completed")


def test_after_close_schedule_is_versioned_and_disabled_by_default(tmp_path: Path) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")

    default = runs.schedule()
    enabled = runs.configure_schedule(enabled=True, requested_by="local-user", now=NOW)

    assert default == {
        "enabled": False,
        "timezone": "Asia/Shanghai",
        "start_time": "09:00",
        "p0_deadline": "21:00",
        "version": 1,
    }
    assert enabled["enabled"] is True
    assert enabled["start_time"] == "09:00"
    assert enabled["version"] == 2
    assert runs.startup_actions() == {"automatic_runs": 0, "external_requests": 0}


@pytest.mark.parametrize("enabled", [True, False])
def test_an_upgraded_schedule_moves_to_the_next_morning_and_keeps_its_switch(
    tmp_path: Path, enabled: bool
) -> None:
    """A database whose schedule still starts at 18:30 gets a version starting at 9:00, on
    or off as it was (ADR-0041); its earlier versions are kept as they were."""
    database = tmp_path / "runtime.sqlite3"
    _upgrade(database, "0035_media_conflict_recheck")
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO schedule_configuration VALUES (?, ?, 'Asia/Shanghai', '18:30', "
            "'21:00', ?, '2026-08-28T10:00:00+00:00')",
            [(1, 0, "system-default"), (2, int(enabled), "local-user")],
        )
    connection.close()
    empty = tmp_path / "empty.sqlite3"
    _upgrade(empty, "0035_media_conflict_recheck")
    current = tmp_path / "current.sqlite3"
    _upgrade(current, "0035_media_conflict_recheck")
    with sqlite3.connect(current) as connection:
        connection.executemany(
            "INSERT INTO schedule_configuration VALUES (?, 1, 'Asia/Shanghai', ?, '21:00', "
            "'local-user', '2026-10-11T00:00:00+00:00')",
            [(1, "18:30"), (2, "09:00")],
        )
    connection.close()

    for upgraded in (database, empty, current):
        migrate_database(upgraded)

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT version, enabled, start_time, p0_deadline FROM schedule_configuration "
            "ORDER BY version"
        ).fetchall()
    connection.close()
    assert rows == [
        (1, 0, "18:30", "21:00"),
        (2, int(enabled), "18:30", "21:00"),
        (3, int(enabled), "09:00", "21:00"),
    ]
    assert RunRepository(database).schedule()["start_time"] == "09:00"
    with sqlite3.connect(empty) as connection:
        # A new database is given its first version when the runtime is bootstrapped.
        assert connection.execute("SELECT COUNT(*) FROM schedule_configuration").fetchone() == (0,)
    connection.close()
    # One whose latest version already starts at 9:00 is left as it is.
    with sqlite3.connect(current) as connection:
        assert connection.execute(
            "SELECT version, start_time FROM schedule_configuration ORDER BY version"
        ).fetchall() == [(1, "18:30"), (2, "09:00")]
    connection.close()


def test_explicit_manual_run_is_queued_ahead_of_an_unstarted_schedule(
    tmp_path: Path,
) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    scheduled = runs.submit_scheduled_full(
        target_business_date="2026-08-28",
        client_request_id="scheduled-first",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )
    manual = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="manual-second",
        model_version_id="model-v0001",
        system_as_of=NOW,
    )

    assert scheduled.run_id != manual.run_id
    assert runs.next_queued().run_id == manual.run_id  # type: ignore[union-attr]


def _record_attempt(runs: RunRepository, run_id: str, index: int) -> None:
    runs.record_retrieval_attempt(
        run_id,
        release_event_id="chinamoney-lpr:2026-08-20",
        channel="tavily",
        outcome="not_found",
        classification=None,
        latency_ms=index,
        remaining_run_budget=None,
        remaining_daily_budget=None,
        budget_charged=False,
        cache_hit=False,
        manual_budget_exemption=False,
        candidate_source=None,
        occurred_at=NOW + timedelta(seconds=index),
    )


def _targeted_run(runs: RunRepository, client_request_id: str) -> str:
    return runs.submit(
        command_type="targeted_refresh",
        target_business_date="2026-08-20",
        client_request_id=client_request_id,
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 8, 20, 2, tzinfo=UTC),
        release_event_id="chinamoney-lpr:2026-08-20",
        metric_ids=("CN_LPR_1Y_5Y",),
        period="2026-08",
    ).run_id


def test_polling_a_runs_status_after_each_attempt_reads_none_of_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A full run looks at its status after each of its thousands of attempts (lookback
    # ticket 11): reading the whole run for it reread every attempt, a cost growing with
    # their square.
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run_id = _targeted_run(runs, "attempts-polled")
    counter = AttemptRowCounter()
    counter.install(monkeypatch)
    polled = 0

    for index in range(200):
        _record_attempt(runs, run_id, index)
        before = counter.rows
        assert runs.status(run_id) == "queued"
        polled += counter.rows - before

    assert polled == 0
    # The whole run still reads them all, as it always did (and the count sees it).
    before = counter.rows
    assert [item["latency_ms"] for item in runs.get(run_id).retrieval_attempts] == list(range(200))
    assert counter.rows - before == 200


def test_a_run_read_after_its_database_is_restored_shows_the_restored_attempts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runs.sqlite3"
    runs = RunRepository.create(database)
    run_id = _targeted_run(runs, "attempts-restored")
    _record_attempt(runs, run_id, 0)
    with sqlite3.connect(database) as live, sqlite3.connect(tmp_path / "copy.sqlite3") as copy:
        live.backup(copy)
    _record_attempt(runs, run_id, 1)
    _record_attempt(runs, run_id, 2)
    assert [item["latency_ms"] for item in runs.get(run_id).retrieval_attempts] == [0, 1, 2]

    with sqlite3.connect(tmp_path / "copy.sqlite3") as copy, sqlite3.connect(database) as live:
        copy.backup(live)
    # The restored run goes on to the same sequences and row ids as the attempts it lost, and
    # to the very last of them.
    _record_attempt(runs, run_id, 7)
    _record_attempt(runs, run_id, 2)

    assert [item["latency_ms"] for item in runs.get(run_id).retrieval_attempts] == [0, 7, 2]


def test_a_run_read_in_steps_audits_as_one_read_whole_through_interruption_and_resume(
    tmp_path: Path,
) -> None:
    runs = RunRepository.create(tmp_path / "runs.sqlite3")
    run_id = _targeted_run(runs, "attempts-in-steps")
    other_id = _targeted_run(runs, "attempts-other-run")
    _record_attempt(runs, run_id, 0)
    earlier = runs.get(run_id)
    _record_attempt(runs, run_id, 1)
    _record_attempt(runs, other_id, 5)
    assert [item["latency_ms"] for item in runs.get(other_id).retrieval_attempts] == [5]
    runs.mark_interrupted(run_id, "worker_process_lost")
    runs.resume(run_id, client_request_id="resume-1", confirm_external_calls=True)
    _record_attempt(runs, run_id, 2)

    audited = runs.get(run_id)

    assert [item["latency_ms"] for item in earlier.retrieval_attempts] == [0]
    assert [item["latency_ms"] for item in audited.retrieval_attempts] == [0, 1, 2]
    assert audited.status == "queued"
    assert asdict(audited) == asdict(RunRepository(tmp_path / "runs.sqlite3").get(run_id))
