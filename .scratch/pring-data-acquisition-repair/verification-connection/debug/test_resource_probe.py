"""Diagnostic-only probes; not part of the project regression suite."""

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

import pytest

from pring_cycle.runs import RunRepository


@pytest.mark.parametrize("mode", ["detail", "count", "detail_collect"])
def test_probe(tmp_path: Path, mode: str) -> None:
    database = tmp_path / "probe.sqlite3"
    submitted = RunRepository.create(database).submit_manual_full(
        target_business_date="2026-08-28",
        client_request_id="probe",
        model_version_id="model-v0001",
        system_as_of=datetime(2026, 9, 9, tzinfo=UTC),
    )
    result = subprocess.run(
        [sys.executable, "-c", dedent("""
            import gc, json, os, resource, sqlite3, sys
            from pathlib import Path
            from pring_cycle.runs import RunRepository
            runs = RunRepository(Path(sys.argv[1]))
            assert runs.get(sys.argv[2]).status == "queued"
            gc.collect()
            gc.disable()
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (min(128, soft), hard))
            before = len(os.listdir('/proc/self/fd'))
            completed = 0
            error = None
            try:
                for _ in range(64):
                    if sys.argv[3] == 'count':
                        assert runs.count() == 1
                    else:
                        assert runs.get(sys.argv[2]).status == 'queued'
                    completed += 1
                    if sys.argv[3] == 'detail_collect':
                        gc.collect()
            except sqlite3.Error as exc:
                error = str(exc)
            gc.collect()
            recovered = runs.get(sys.argv[2]).status == 'queued'
            gc.collect()
            after = len(os.listdir('/proc/self/fd'))
            print(json.dumps(dict(mode=sys.argv[3], completed=completed,
                error=error, before=before, after_gc=after, recovered=recovered)))
        """), str(database), submitted.run_id, mode],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    print("[DEBUG-db-lifetime]", result.stdout.strip())
