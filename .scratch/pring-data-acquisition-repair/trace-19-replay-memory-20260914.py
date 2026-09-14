"""Locate the replay's large allocations with tracemalloc over three late cutoffs (reads a built runtime)."""
import sys, tracemalloc
from pathlib import Path
import pring_cycle.commodity_basket as basket
import pring_cycle.context_projection as projection
from pring_cycle.model_evaluation import evaluate_context_replay
from pring_cycle.models import ModelRepository
db = Path(sys.argv[1])
models = ModelRepository(db)
candidate = next(m.model_version_id for m in models.list_versions() if m.model_version_id.startswith('model-reviewed'))
reports = []
def traced(name, function):
    def wrapper(*args, **kwargs):
        result = function(*args, **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        top = tracemalloc.take_snapshot().statistics('lineno')[:12]
        reports.append((name, current // 2**20, peak // 2**20, [(str(s.traceback), s.size // 2**20) for s in top]))
        print(name, 'current', current // 2**20, 'MB peak', peak // 2**20, 'MB', flush=True)
        return result
    return wrapper
basket.commodity_claims_matching_acquisitions = traced('commodity', basket.commodity_claims_matching_acquisitions)
import pring_cycle.model_evaluation as evaluation
evaluation.commodity_claims_matching_acquisitions = basket.commodity_claims_matching_acquisitions
projection.build_context_projection = traced('projection', projection.build_context_projection)
evaluation.build_context_projection = projection.build_context_projection
tracemalloc.start(1)
days = ('2026-08-26', '2026-08-27', '2026-08-28')
evaluate_context_replay(db, models.manifest(candidate), models.manifest('model-v0001'), requested_start=days[0], requested_end=days[-1], replay_days=days)
name, current, peak, top = max(reports, key=lambda r: r[2])
print('PEAK REPORT', name, current, peak)
for line, size in top: print(size, 'MB', line)
