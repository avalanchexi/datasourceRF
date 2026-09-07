"""One real public Treasury CLI acquisition into a new isolated candidate store."""

import hashlib
import json
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.cli import main
from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.runtime import RuntimePaths, initialize_runtime

output = Path(__file__).resolve().parent
runtime = Path("/home/tywin/.cache/pring-cycle/verification/repair-14-live-treasury-20260907a")
if runtime.exists():
    raise RuntimeError("Refusing to reuse the real candidate runtime")
paths = RuntimePaths.discover(runtime)
initialize_runtime(paths)
acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
evidence = EvidenceRepository(paths.database)
arguments = ["treasury-csv-refresh", "--runtime-root", str(runtime), "--start", "2026-08-24",
             "--end", "2026-09-04", "--definition-version", "metric-catalog-v0002", "--json"]
report = {"scope": "one real public CLI and HTTP; isolated candidate runtime", "runtime": str(runtime),
          "command_arguments": arguments, "definition_version": "metric-catalog-v0002",
          "production_writes": 0, "model_activations": 0, "source_certification_grants": 0,
          "model_adoptions": 0, "api_keys_used": 0}
try:
    captured = StringIO()
    with redirect_stdout(captured):
        main(arguments)
    report["result"] = json.loads(captured.getvalue())
except (SystemExit, OSError, TypeError, ValueError) as error:
    report.update(error_type=type(error).__name__, error=str(error))
receipts = acquisitions.history()
report["receipts"] = [asdict(receipt) for receipt in receipts]
for receipt in receipts:
    for kind, digest in (("raw", receipt.raw_hash), ("normalized", receipt.normalized_hash)):
        if digest is not None:
            content = acquisitions.read_content(receipt.acquisition_id, kind)
            if hashlib.sha256(content).hexdigest() != digest:
                raise RuntimeError("Artifact hash mismatch")
            (output / digest).write_bytes(content)
cutoff = datetime.now(UTC)
report["metrics"] = {}
for metric in ("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD"):
    points = evidence.metric_series(metric, mode=AsOfMode.SYSTEM, as_of=cutoff,
                                    definition_version=report["definition_version"])
    attempt = evidence.latest_retrieval_attempt(metric, period="2026-09-04", as_of=cutoff,
                                               definition_version=report["definition_version"])
    public = evidence.metric_series(metric, mode=AsOfMode.PUBLIC, as_of=cutoff,
                                    definition_version=report["definition_version"])
    report["metrics"][metric] = {
        "traces": [asdict(evidence.trace(point.observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff)) for point in points],
        "latest_attempt": asdict(attempt) if attempt is not None else None,
        "public_points": len(public),
    }
report["recorded_at"] = cutoff
(output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({"requests": len(receipts), "result": report.get("result"), "error": report.get("error")}, ensure_ascii=False))
if "error" in report:
    raise RuntimeError("Real acquisition failed; saved the request evidence")
