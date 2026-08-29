from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pring_cycle.runs import RunRepository

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
        "start_time": "18:30",
        "p0_deadline": "21:00",
        "version": 1,
    }
    assert enabled["enabled"] is True
    assert enabled["version"] == 2
    assert runs.startup_actions() == {"automatic_runs": 0, "external_requests": 0}
