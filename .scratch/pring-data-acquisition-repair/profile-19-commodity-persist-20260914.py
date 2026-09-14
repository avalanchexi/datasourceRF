"""Profile persist_commodity_basket on the lifecycle material inputs (isolated native runtime)."""
import contextlib, cProfile, io, json, pstats, sys, tempfile, time
from datetime import UTC, date, datetime
from pathlib import Path
sys.path.insert(0, '/mnt/d/cursor/datasourceRF')
import pring_cycle.commodity_basket as basket
from pring_cycle.evidence import AsOfMode
from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime
import tests.models.test_isolated_lifecycle as lifecycle
from tests.conftest import _clock_datetime

# Same advancing timeline as the runtime_clock fixture; the WSL wall clock can step backwards.
_origin, _started = datetime.now(UTC), time.monotonic()
_clock = _clock_datetime(lambda: _origin + __import__('datetime').timedelta(seconds=time.monotonic() - _started))
import importlib
for _module in ('acquisition', 'core_history', 'worker', 'runs', 'retrieval_ledger'):
    setattr(importlib.import_module(f'pring_cycle.{_module}'), 'datetime', _clock)
lifecycle.datetime = _clock

OUT = Path('/mnt/d/cursor/datasourceRF/.scratch/pring-data-acquisition-repair')
root = Path(tempfile.mkdtemp(dir='/home/tywin/.cache/pring-cycle/verification/lifecycle19-20260914'))
paths = RuntimePaths.discover(root / 'runtime'); initialize_runtime(paths)

class Capture:
    def __init__(self): self.buffer = io.StringIO()
    def readouterr(self):
        value = self.buffer.getvalue(); self.buffer = io.StringIO()
        return type('C', (), {'out': value, 'err': ''})()
capsys = Capture()
with contextlib.redirect_stdout(capsys.buffer):
    candidate = lifecycle.admit_complete_candidate(paths, capsys)
version = ModelRepository(paths.database).manifest(candidate)['metric_catalog_version']
real = basket.persist_commodity_basket
basket.persist_commodity_basket = lambda *a, **k: {'missing': []}
t = time.monotonic(); lifecycle.import_commodity_basket(paths, version); print('inputs', round(time.monotonic() - t, 1), flush=True)
basket.persist_commodity_basket = real
for day in (date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 13)):
    profile = cProfile.Profile(); t = time.monotonic()
    profile.enable()
    result = real(paths, business_date=day, as_of=datetime(day.year, day.month, day.day, 12, tzinfo=UTC), mode=AsOfMode.PUBLIC, definition_version=version)
    profile.disable()
    print(day, 'seconds', round(time.monotonic() - t, 1), 'missing', result['missing'], flush=True)
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(35)
    (OUT / f'profile-19-commodity-persist-{day}.txt').write_text(stream.getvalue())
