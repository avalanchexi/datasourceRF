"""Profile the context replay over a short tail of the lifecycle runtime (read-only use of its database)."""
import cProfile, io, pstats, sys, time
from pathlib import Path
from pring_cycle.model_evaluation import evaluate_context_replay
from pring_cycle.models import ModelRepository
db = Path(sys.argv[1]); out = Path(sys.argv[2])
models = ModelRepository(db)
candidate = next(m.model_version_id for m in models.list_versions() if m.model_version_id.startswith('model-reviewed'))
days = ('2026-08-17','2026-08-18','2026-08-19','2026-08-20','2026-08-21','2026-08-24','2026-08-25','2026-08-26','2026-08-27','2026-08-28')
profile = cProfile.Profile(); started = time.monotonic(); profile.enable()
result = evaluate_context_replay(db, models.manifest(candidate), models.manifest('model-v0001'), requested_start=days[0], requested_end=days[-1], replay_days=days)
profile.disable()
print('seconds', round(time.monotonic() - started, 1), 'gaps', result.gaps[:5], flush=True)
stream = io.StringIO(); pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(45)
out.write_text(stream.getvalue())
