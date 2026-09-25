from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import pring_cycle.maintenance as maintenance_module
from pring_cycle.maintenance import (
    GIB,
    MaintenanceRepository,
    capacity_state,
)

NOW = datetime(2026, 8, 28, 10, tzinfo=UTC)


def test_cleanup_removes_only_expired_unreferenced_objects_and_is_idempotent(
    tmp_path: Path,
) -> None:
    maintenance = MaintenanceRepository.create(tmp_path / "maintenance.sqlite3")
    expired = tmp_path / "expired-response.bin"
    protected = tmp_path / "referenced-evidence.bin"
    recent = tmp_path / "recent-response.bin"
    for path in (expired, protected, recent):
        path.write_bytes(b"fixture")
    maintenance.register_object(
        "expired",
        expired,
        kind="unverified_response",
        created_at=NOW - timedelta(days=8),
        authoritative=False,
        referenced=False,
    )
    maintenance.register_object(
        "protected",
        protected,
        kind="unverified_response",
        created_at=NOW - timedelta(days=8),
        authoritative=True,
        referenced=True,
    )
    maintenance.register_object(
        "recent",
        recent,
        kind="unverified_response",
        created_at=NOW - timedelta(days=6),
        authoritative=False,
        referenced=False,
    )

    first = maintenance.cleanup(now=NOW)
    second = maintenance.cleanup(now=NOW)

    assert first.deleted_object_ids == ("expired",)
    assert second.deleted_object_ids == ()
    assert not expired.exists()
    assert protected.exists()
    assert recent.exists()
    assert maintenance.audit_events()[-1]["outcome"] == "completed"


def test_cleanup_evicts_oldest_unreferenced_object_until_size_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintenance = MaintenanceRepository.create(tmp_path / "maintenance.sqlite3")
    oldest = tmp_path / "oldest.bin"
    newest = tmp_path / "newest.bin"
    oldest.write_bytes(b"1234567")
    newest.write_bytes(b"7654321")
    for object_id, path, created_at in (
        ("oldest", oldest, NOW - timedelta(hours=2)),
        ("newest", newest, NOW - timedelta(hours=1)),
    ):
        maintenance.register_object(
            object_id,
            path,
            kind="fixture_size_limited",
            created_at=created_at,
            authoritative=False,
            referenced=False,
        )
    monkeypatch.setattr(
        maintenance_module,
        "_retention_policy",
        lambda _kind: (None, 10),
    )

    result = maintenance.cleanup(now=NOW)

    assert result.deleted_object_ids == ("oldest",)
    assert result.reclaimed_bytes == 7
    assert not oldest.exists()
    assert newest.exists()


def test_interrupted_cleanup_can_be_retried_without_losing_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintenance = MaintenanceRepository.create(tmp_path / "maintenance.sqlite3")
    expired = tmp_path / "expired.bin"
    expired.write_bytes(b"fixture")
    maintenance.register_object(
        "expired",
        expired,
        kind="unverified_response",
        created_at=NOW - timedelta(days=8),
        authoritative=False,
        referenced=False,
    )
    real_unlink = Path.unlink

    def interrupt_unlink(_path: Path, *_args: object, **_kwargs: object) -> None:
        raise OSError("fixture cleanup interruption")

    monkeypatch.setattr(Path, "unlink", interrupt_unlink)
    with pytest.raises(OSError, match="fixture cleanup interruption"):
        maintenance.cleanup(now=NOW)

    monkeypatch.setattr(Path, "unlink", real_unlink)
    retried = maintenance.cleanup(now=NOW)

    assert retried.deleted_object_ids == ("expired",)
    assert not expired.exists()


def test_capacity_watermarks_have_distinct_safe_actions() -> None:
    assert capacity_state(25 * GIB).state == "normal"
    assert capacity_state(20 * GIB).state == "warning"
    assert capacity_state(10 * GIB).state == "restrict_non_core"
    assert capacity_state(5 * GIB).state == "stop_worker_writes"
    assert capacity_state(5 * GIB).serve_reads is True
    assert capacity_state(5 * GIB).allow_worker_writes is False


def test_upgrade_failure_requires_reinitialization_without_destructive_recovery(
    tmp_path: Path,
) -> None:
    maintenance = MaintenanceRepository.create(tmp_path / "maintenance.sqlite3")

    maintenance.record_upgrade_failure("schema_validation_failed", now=NOW)
    status = maintenance.runtime_integrity()

    assert status == {
        "status": "reinitialize_required",
        "reason": "schema_validation_failed",
        "backup_mode": "none",
        "destructive_recovery_available": False,
    }


def test_cleanup_keeps_report_bodies_for_the_whole_retention_window(tmp_path: Path) -> None:
    """ADR-0022 (revised 2026-09-25): a report body is not cleared after 30 days."""
    import json

    from pring_cycle.reports import ReportRepository
    from pring_cycle.runtime import RuntimePaths, initialize_runtime
    from pring_cycle.storage import database_connection

    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    database = paths.database
    maintenance = MaintenanceRepository(database)
    ReportRepository(database)  # Creates the report tables.
    with database_connection(database) as connection:
        connection.execute(
            "INSERT INTO report_snapshot(report_snapshot_id, client_request_id, "
            "projection_set_id, target_business_date, version, status, adapter, current_stage, "
            "bundle_id, bundle_hash, model_version_id, schema_version, prompt_version, "
            "body_json, body_retained, created_at) VALUES ('report-old', 'old', "
            "'projection-old', '2026-06-30', 1, 'completed', 'deterministic', NULL, "
            "'bundle-old', 'hash', 'model-v0012', 'report-schema-v0003', 'report-prompt-v0003', "
            "?, 1, ?)",
            (json.dumps({"summary": "六十天前的报告"}), (NOW - timedelta(days=60)).isoformat()),
        )

    maintenance.cleanup(now=NOW)

    with database_connection(database) as connection:
        body, retained = connection.execute(
            "SELECT body_json, body_retained FROM report_snapshot WHERE report_snapshot_id=?",
            ("report-old",),
        ).fetchone()
    assert (json.loads(body), retained) == ({"summary": "六十天前的报告"}, 1)
