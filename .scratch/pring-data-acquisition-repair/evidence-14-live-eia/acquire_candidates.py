"""Run the public EIA HTML command with real HTTP in a fresh candidate runtime."""

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
root = Path("/home/tywin/.cache/pring-cycle/verification/repair-14-live-eia-20260907a")
if root.exists():
    raise RuntimeError("Refusing to reuse an existing candidate runtime")
paths = RuntimePaths.discover(root)
initialize_runtime(paths)
acquisitions = AcquisitionRepository(paths.database, paths.artifacts)
evidence = EvidenceRepository(paths.database)
report = {
    "scope": "real public CLI and HTTP; isolated candidate runtime",
    "runtime": str(root), "start_date": "2026-08-24", "end_date": "2026-09-04",
    "definition_version": "metric-catalog-v0002", "records": [],
    "production_writes": 0, "model_activations": 0, "source_certification_grants": 0,
    "api_keys_used": 0, "model_adoptions": 0,
}
for series, metric in (("RBRTE", "EIA_BRENT_RBRTE"), ("RWTC", "EIA_WTI_RWTC")):
    before = {r.acquisition_id for r in acquisitions.history()}
    arguments = [
        "eia-html-refresh", "--runtime-root", str(root), "--series", series,
        "--start", report["start_date"], "--end", report["end_date"],
        "--definition-version", report["definition_version"], "--json",
    ]
    record = {"series_id": series, "metric_id": metric, "command_arguments": arguments}
    try:
        captured = StringIO()
        with redirect_stdout(captured):
            main(arguments)
        record["result"] = json.loads(captured.getvalue())
    except (SystemExit, OSError, TypeError, ValueError) as error:
        record.update(error_type=type(error).__name__, error=str(error))
    receipts = [r for r in acquisitions.history() if r.acquisition_id not in before]
    record["receipts"] = [asdict(r) for r in receipts]
    for receipt in receipts:
        for kind, digest in (("raw", receipt.raw_hash), ("normalized", receipt.normalized_hash)):
            if digest is not None:
                content = acquisitions.read_content(receipt.acquisition_id, kind)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise RuntimeError("Artifact hash mismatch")
                (output / digest).write_bytes(content)
    cutoff = datetime.now(UTC)
    points = evidence.metric_series(metric, mode=AsOfMode.SYSTEM, as_of=cutoff,
                                    definition_version=report["definition_version"])
    record["traces"] = [asdict(evidence.trace(p.observation_id, mode=AsOfMode.SYSTEM, as_of=cutoff))
                        for p in points]
    attempt = evidence.latest_retrieval_attempt(metric, period=report["end_date"], as_of=cutoff,
                                               definition_version=report["definition_version"])
    record["latest_attempt"] = asdict(attempt) if attempt is not None else None
    report["records"].append(record)
    report["recorded_at"] = datetime.now(UTC)
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                                       encoding="utf-8")
    print(json.dumps({"series": series, "requests": len(receipts), "claims": len(points),
                      "result": record.get("result"), "error": record.get("error")},
                     ensure_ascii=False), flush=True)
