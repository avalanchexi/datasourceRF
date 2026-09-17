from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

import pytest

from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime


@pytest.mark.skipif(sys.platform != "linux", reason="Requires the WSL native runtime")
def test_repeated_run_reads_do_not_exhaust_open_files(tmp_path: Path) -> None:
    database = tmp_path / "runs.sqlite3"
    submitted = RunRepository.create(database).submit(
        command_type="manual_full",
        target_business_date="2026-08-28",
        client_request_id="repeated-reads",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    # Delay cyclic garbage collection and limit descriptors only in this child.
    # Repeated public reads must remain usable without depending on a GC cycle.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent(
                """
                import gc
                import json
                import resource
                import sys
                from pathlib import Path
                from pring_cycle.runs import RunRepository

                runs = RunRepository(Path(sys.argv[1]))
                assert runs.get(sys.argv[2]).status == "queued"
                gc.collect()
                gc.disable()
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(128, soft), hard))
                for _ in range(64):
                    try:
                        runs.get('missing-run')
                    except LookupError as exc:
                        assert exc.args == ('run_not_found',)
                    else:
                        raise AssertionError('missing run must remain unavailable')
                    record = runs.get(sys.argv[2])
                    assert record.status == "queued"
                    assert record.run_id == sys.argv[2]
                print(json.dumps({"reads": 64, "status": record.status}))
                """
            ),
            str(database),
            submitted.run_id,
        ],
        capture_output=True,
        text=True,
        # A guard against a hang, not a performance budget. Measured 2026-09-17 at one version:
        # ~4.5s with the repository on a WSL-native filesystem, ~25s with it on /mnt/d, where
        # 30s left so little room that a loaded full suite tripped it and reported a timeout
        # instead of the unavailability this test is about.
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"reads": 64, "status": "queued"}


@pytest.mark.skipif(sys.platform != "linux", reason="Requires the WSL native runtime")
def test_repeated_runtime_views_remain_available(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    submitted = RunRepository(paths.database).submit(
        command_type="manual_full",
        target_business_date="2026-08-28",
        client_request_id="runtime-views",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 9, 9, tzinfo=UTC),
        cutoff_mode="explicit",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            dedent(
                """
                import gc
                import json
                import resource
                import sys
                from datetime import UTC, datetime
                from pathlib import Path
                from pring_cycle.acquisition import (
                    AcquisitionRepository, acquisition_analysis_context,
                )
                from pring_cycle.catalog_registry import registered_definitions
                from pring_cycle.cutover import cutover_status
                from pring_cycle.evidence import AsOfMode, EvidenceRepository
                from pring_cycle.full_retrieval import read_full_retrieval_plan
                from pring_cycle.full_run_requirements import required_calendar
                from pring_cycle.maintenance import MaintenanceRepository
                from pring_cycle.models import ModelRepository
                from pring_cycle.projections import ProjectionSetRepository
                from pring_cycle.reports import ReportRepository
                from pring_cycle.runs import RunRepository
                from pring_cycle.runtime import RuntimePaths
                from pring_cycle.runtime_fingerprint import execution_fingerprint
                from pring_cycle.search_evidence import ModelInputSelector

                paths = RuntimePaths.discover(Path(sys.argv[1]))
                acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
                evidence = EvidenceRepository(paths.database)
                maintenance = MaintenanceRepository(paths.database)
                models = ModelRepository(paths.database)
                projections = ProjectionSetRepository(paths.database)
                reports = ReportRepository(paths.database)
                run = RunRepository(paths.database).get(sys.argv[2])
                selector = ModelInputSelector(paths, run)
                gc.collect()
                gc.disable()
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(128, soft), hard))
                for _ in range(64):
                    assert acquisitions.history() == ()
                    assert evidence.metric_series(
                        'CN_DR007', mode=AsOfMode.SYSTEM,
                        as_of=datetime(2026, 9, 9, tzinfo=UTC),
                    ) == ()
                    assert models.manifest('model-v0001')['model_version_id'] == 'model-v0001'
                    assert projections.stage_history() == ()
                    assert reports.history() == ()
                    assert maintenance.audit_events() == ()
                    assert cutover_status(paths) is None
                    assert acquisition_analysis_context(paths.database, ('absent',)) == {}
                    assert read_full_retrieval_plan(paths.database, run.run_id) == {
                        'initial': None, 'final': None, 'adoption': None, 'acquisitions': [],
                    }
                    assert required_calendar(paths, run, selector)['status'] == 'unavailable'
                    assert execution_fingerprint(paths)['database_revision'] == (
                        '0021_context_replay_outputs'
                    )
                    try:
                        registered_definitions(paths.database, 'unregistered')
                    except KeyError as exc:
                        assert exc.args == ('unknown_metric_definition_version',)
                    else:
                        raise AssertionError('unregistered catalog must remain unavailable')
                print(json.dumps({'view_cycles': 64, 'model': 'model-v0001'}))
                """
            ),
            str(tmp_path / "runtime"),
            submitted.run_id,
        ],
        capture_output=True,
        text=True,
        # A guard against a hang, not a performance budget. Measured 2026-09-17 at one version:
        # ~4.5s with the repository on a WSL-native filesystem, ~25s with it on /mnt/d, where
        # 30s left so little room that a loaded full suite tripped it and reported a timeout
        # instead of the unavailability this test is about.
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"view_cycles": 64, "model": "model-v0001"}
