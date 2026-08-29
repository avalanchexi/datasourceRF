from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
