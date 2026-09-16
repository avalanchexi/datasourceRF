"""Profile a registered full run for 300 seconds on a copy of the isolated material (then stop)."""
import cProfile, io, pstats, shutil, signal, sys, time
from datetime import UTC, datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pring_cycle.runs import RunRepository
from pring_cycle.runtime import RuntimePaths
from pring_cycle.worker import process_pending_run
material, destination, out, seconds = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), int(sys.argv[5])
shutil.rmtree(destination, ignore_errors=True)
shutil.copytree(material / 'runtime', destination)
paths = RuntimePaths.discover(destination)
if len(sys.argv) > 6 and sys.argv[6] == 'tushare-gdp-invalid':
    # Same conditions as the optional TuShare failure test: token only, real core rows, GDP schema error.
    import json as _json
    from io import BytesIO
    import pring_cycle.source_adapters, pring_cycle.tushare_context
    from tests.integration.test_worker_registered_catalog import real_core_opener
    paths.secrets.write_text('TUSHARE_TOKEN=fixture-only\n', encoding='utf-8'); paths.secrets.chmod(0o600)
    class ContextOpener:
        def open(self, request, *, timeout):
            if _json.loads(request.data)['api_name'] == 'cn_gdp':
                return BytesIO(b'{"code":0,"data":{"fields":[],"items":[[]]}}')
            raise OSError('fixture source unavailable')
    pring_cycle.source_adapters.build_opener = lambda *h: real_core_opener()
    pring_cycle.tushare_context.build_opener = lambda *h: ContextOpener()
import json
candidate = json.loads((material / 'material.json').read_text())['candidate_model_version_id']
RunRepository(paths.database).submit_manual_full(target_business_date='2026-08-28', client_request_id='profile-full-run', model_version_id=candidate, system_as_of=datetime.now(UTC))
class Stop(Exception): pass
def stop(*_): raise Stop()
signal.signal(signal.SIGALRM, stop); signal.alarm(seconds)
profile = cProfile.Profile(); started = time.monotonic(); profile.enable()
try:
    process_pending_run(paths, report_adapters=())
    outcome = 'finished'
except Stop:
    outcome = 'stopped'
profile.disable()
stream = io.StringIO(); pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(60)
out.write_text(f'{outcome} after {time.monotonic()-started:.1f}s\n' + stream.getvalue())
print(outcome)
