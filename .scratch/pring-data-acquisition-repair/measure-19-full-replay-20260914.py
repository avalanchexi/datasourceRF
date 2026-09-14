"""Measure the full 120-day candidate replay on a built lifecycle runtime (reads its database)."""
import json, resource, sys, time
from pathlib import Path
from pring_cycle.model_evaluation import replay_models
from pring_cycle.models import ModelRepository
db = Path(sys.argv[1])
models = ModelRepository(db)
candidate = next(m.model_version_id for m in models.list_versions() if m.model_version_id.startswith('model-reviewed'))
started = time.monotonic()
result = replay_models(db, candidate, 'model-v0001', requested_start='2026-03-09', requested_end='2026-08-28')
print(json.dumps({
    'seconds': round(time.monotonic() - started, 1),
    'peak_rss_mb': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
    'quality_passed': result.quality_passed, 'regression_passed': result.regression_passed,
    'performance_passed': result.performance_passed, 'days': result.evaluated_trading_days,
    'gaps': list(result.gaps), 'stage_differences': result.stage_differences,
}, ensure_ascii=False), flush=True)
