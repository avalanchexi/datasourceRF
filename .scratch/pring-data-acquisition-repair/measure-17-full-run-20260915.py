"""Run one registered full run to completion on a copy of the isolated material and report its outcome."""
import json, resource, shutil, sys, time
from datetime import UTC, datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
material, destination = Path(sys.argv[2]), Path(sys.argv[3])
shutil.rmtree(destination, ignore_errors=True)
shutil.copytree(material / 'runtime', destination)
paths = RuntimePaths.discover(destination)
candidate = json.loads((material / 'material.json').read_text())['candidate_model_version_id']
runs = RunRepository(paths.database)
run = runs.submit_manual_full(target_business_date='2026-08-28', client_request_id='measure-full-run', model_version_id=candidate, system_as_of=datetime.now(UTC))
started = time.monotonic()
process_pending_run(paths, report_adapters=())
stored = runs.get(run.run_id)
print(json.dumps({'seconds': round(time.monotonic() - started, 1), 'peak_rss_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, 'status': stored.status, 'step': stored.current_step, 'error': stored.error_classification, 'projection': stored.projection_set_id}, default=str))
