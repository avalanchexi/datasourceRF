"""The lease heartbeat overlapping another writer must not die silently.

A run holds its lease by writing a heartbeat every 30 seconds while its own work writes to the
same database. SQLite serialises writers, so a write that outlasts the connection's busy timeout
makes the heartbeat write fail. The run keeps its lease only if that failure is retried and
surfaced; a heartbeat thread that exits on the first lock error loses the lease silently.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pring_cycle.models import CALIBRATION_BASELINE, ModelRepository
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def prepared(tmp_path: Path) -> tuple[RuntimePaths, RunRepository]:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    models = ModelRepository(paths.database)
    models.record_acceptance("model-v0001", CALIBRATION_BASELINE)
    models.activate("model-v0001", explicitly_approved=True)
    return paths, RunRepository(paths.database)


def held_write(database: Path, seconds: float) -> tuple[threading.Thread, threading.Event]:
    """Hold the write lock for ``seconds``, the way a long evidence or output write does."""
    holding, release = threading.Event(), threading.Event()

    def writer() -> None:
        with sqlite3.connect(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE worker_lease SET heartbeat_at = heartbeat_at "
                "WHERE lease_name = 'worker:global-execution'"
            )
            holding.set()
            release.wait(seconds)

    thread = threading.Thread(target=writer, name="fixture-long-write")
    thread.start()
    assert holding.wait(5)
    return thread, release


@pytest.mark.usefixtures("runtime_clock")
def test_a_heartbeat_blocked_by_a_long_write_keeps_the_lease(tmp_path: Path) -> None:
    """The heartbeat loop retries a locked write inside the lease window instead of exiting."""
    from pring_cycle.worker import lease_heartbeat

    paths, runs = prepared(tmp_path)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="lease-heartbeat-overlap",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    runs.acquire_lease(run.run_id, owner_id="worker-overlap")
    # The overlap: another writer holds the lock past this connection's busy timeout.
    thread, release = held_write(paths.database, seconds=6.5)
    stopped = threading.Event()
    contention: list[str] = []

    beats = threading.Thread(
        target=lease_heartbeat,
        args=(runs, "worker-overlap", stopped),
        kwargs={"interval_seconds": 0.2, "on_contention": contention.append, "paths": paths},
        name="heartbeat-under-test",
    )
    beats.start()
    try:
        # Let at least one beat block on the other writer and fail, then release it.
        deadline = time.perf_counter() + 12
        while not contention and time.perf_counter() < deadline:
            time.sleep(0.2)
        release.set()
        thread.join()
        # After the long writer releases, a later beat must succeed and the lease must survive.
        time.sleep(1.0)
        decision = runs.audit_lease()
    finally:
        stopped.set()
        beats.join(5)

    assert not beats.is_alive(), "the heartbeat loop must end only when it is told to stop"
    assert contention, "a heartbeat blocked by another writer must be recorded, not swallowed"
    assert decision.owner_state == "active" and decision.run_id == run.run_id


@pytest.mark.usefixtures("runtime_clock")
def test_a_heartbeat_that_lost_ownership_still_stops(tmp_path: Path) -> None:
    from pring_cycle.worker import lease_heartbeat

    paths, runs = prepared(tmp_path)
    run = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="lease-heartbeat-lost",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    runs.acquire_lease(run.run_id, owner_id="worker-owner")
    stopped = threading.Event()

    beats = threading.Thread(
        target=lease_heartbeat,
        args=(runs, "worker-someone-else", stopped),
        kwargs={"interval_seconds": 0.1, "paths": paths},
        name="heartbeat-not-owner",
    )
    beats.start()
    beats.join(5)

    assert not beats.is_alive(), "losing ownership still ends the heartbeat immediately"


@pytest.mark.usefixtures("runtime_clock")
def test_a_run_under_write_contention_still_publishes_and_reports_its_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole path holds up while another writer keeps taking the lock.

    Public submission, the persisted run, the Worker's own execution, the published projection
    and the status query all have to survive a neighbour that writes throughout the run.
    """
    from pring_cycle.projections import ProjectionSetRepository
    from pring_cycle.worker import process_pending_run
    from tests.integration.test_full_run_retrieval import seed_core_history

    paths, runs = prepared(tmp_path)
    seed_core_history(paths)

    def page_offline(url: str) -> None:
        raise OSError("fixture history page offline")

    monkeypatch.setattr("pring_cycle.worker.fetch_eia_history", page_offline)
    submitted = runs.submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="contended-full-run",
        model_version_id="model-v0001",
        system_as_of=datetime.now(UTC),
    )
    assert runs.get(submitted.run_id).status == "queued"

    stop_writing = threading.Event()
    grabs = 0

    def neighbour() -> None:
        """Keep taking the write lock for short bursts, the way a second writer would."""
        nonlocal grabs
        while not stop_writing.wait(0.05):
            try:
                with sqlite3.connect(paths.database, timeout=0.2) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        "UPDATE worker_lease SET heartbeat_at = heartbeat_at "
                        "WHERE lease_name = 'worker:global-execution'"
                    )
                    grabs += 1
                    time.sleep(0.2)
            except sqlite3.OperationalError:
                continue

    writer = threading.Thread(target=neighbour, name="fixture-neighbour-writer", daemon=True)
    writer.start()
    try:
        process_pending_run(paths, report_adapters=())
    finally:
        stop_writing.set()
        writer.join(5)

    assert grabs > 0, "the fixture never actually contended for the write lock"
    stored = runs.get(submitted.run_id)
    assert stored.status == "completed", stored.error_classification
    assert stored.projection_set_id is not None
    published = ProjectionSetRepository(paths.database).current()
    assert published.envelope.projection_set_id == stored.projection_set_id
    assert published.envelope.target_business_date == "2026-08-28"
    # The lease is released in order once the run ends: no owner is left holding it.
    assert runs.audit_lease().owner_state in {"absent", "released"}
