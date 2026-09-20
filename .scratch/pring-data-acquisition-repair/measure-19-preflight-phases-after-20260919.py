"""Phase attribution for one preflight day, without profiler distortion.

cProfile ran 20+ minutes against a 144-second run, so wrap the phase boundaries and
count calls instead. Read-only, same prepared inputs as the capped complete-window run.
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

project = Path("/mnt/d/cursor/datasourceRF-integrated-20260918")
sys.path.insert(0, str(project))
sys.path.insert(0, str(project / "src"))
from pring_cycle import material_preflight
from pring_cycle.search_evidence import ModelInputSelector
from pring_cycle.runtime import RuntimePaths
from pring_cycle.evidence import EvidenceRepository
from tests.models.test_isolated_lifecycle import material_identity, _runtime_contents

root = Path("/tmp/datasourceRF-preflight-inputs-20260919-v3")
output = project / ".scratch/pring-data-acquisition-repair"
capped = json.loads((output / "verification-19-preflight-complete-inputs-terminal-20260919-v3.json").read_text())
candidate = capped["command"][capped["command"].index("--model") + 1]
paths = RuntimePaths.discover(root)
identity = material_identity(paths, profile="acquisition-repairs")
contents_before = _runtime_contents(root)

phases: dict[str, list[float]] = defaultdict(list)


def timed(name, function):
    def wrapper(*args, **kwargs):
        began = time.monotonic()
        try:
            return function(*args, **kwargs)
        finally:
            phases[name].append(time.monotonic() - began)
    return wrapper


ModelInputSelector.series = timed("selector.series", ModelInputSelector.series)
ModelInputSelector.select = timed("selector.select", ModelInputSelector.select)
ModelInputSelector.__init__ = timed("selector.__init__", ModelInputSelector.__init__)
material_preflight.build_context_projection = timed(
    "build_context_projection", material_preflight.build_context_projection)
material_preflight._core_history_gaps = timed(
    "_core_history_gaps", material_preflight._core_history_gaps)
material_preflight._calendar_material = timed(
    "_calendar_material", material_preflight._calendar_material)
material_preflight._parent_material_diagnostics = timed(
    "_parent_material_diagnostics", material_preflight._parent_material_diagnostics)
EvidenceRepository.source_claim_vintages = timed(
    "evidence.source_claim_vintages", EvidenceRepository.source_claim_vintages)
EvidenceRepository.metric_series = timed(
    "evidence.metric_series", EvidenceRepository.metric_series)

began = time.monotonic()
result = material_preflight.preflight_model_inputs(
    paths, model_version_id=candidate, requested_start="2026-08-28", requested_end="2026-08-28")
total = time.monotonic() - began

changed_after = _runtime_contents(root)
changed = sorted(k for k in contents_before.keys() | changed_after.keys()
                 if contents_before.get(k) != changed_after.get(k))
document = {
    "imported_from": material_preflight.__file__,
    "window": ["2026-08-28", "2026-08-28"],
    "total_seconds": total,
    "phases": {name: {"calls": len(values), "seconds": sum(values), "max_seconds": max(values)}
               for name, values in sorted(phases.items(), key=lambda item: -sum(item[1]))},
    "checked_business_dates": result["checked_business_dates"],
    "gaps": len(result["gaps"]), "optional_gaps": len(result["optional_gaps"]),
    "material_identity_unchanged": material_identity(paths, profile="acquisition-repairs") == identity,
    "runtime_contents_unchanged": not changed, "changed_runtime_files": changed,
}
(output / "verification-19-preflight-phase-cost-after-20260919.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps(document, indent=2), flush=True)
