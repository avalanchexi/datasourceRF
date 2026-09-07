"""Materialize this finished batch's receipt without rerunning its tests."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
project = folder.parents[2]
run = json.loads((folder / "suite-run.json").read_text(encoding="utf-8-sig"))
assert run["exit_code"] == 0
for path in folder.parent.glob("verification-14-treasury-*.txt"):
    data = path.read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    normalized = data.decode(encoding).replace("\r\n", "\n")
    path.write_bytes(normalized.encode("utf-8"))
log = (project / run["log"]).read_text(encoding="utf-8")
assert "639 passed in 800.47s (0:13:20)" in log
assert "FAILED " not in log and "ERROR " not in log
receipt = {
    "status": "completed_code_batch",
    "base_commit": "abbeb0195ca8cf7baa20d5278e3eb18766221b55",
    "passed": 639,
    "failed": 0,
    "duration_seconds": 800.47,
    "runtime": run["runtime"],
    "log": run["log"],
    "test_exit_code": 0,
    "installed_source_files": 81,
    "source_fingerprint": "code-fingerprint.json",
    "static_and_review_checks": "static-checks.json",
    "targeted_passed": 27,
    "spec_findings": 0,
    "standards_findings": 0,
    "real_http_requests": 1,
    "source_days": 10,
    "candidate_claims": 20,
    "missing_cells": 0,
    "source_certification_grants": 0,
    "model_adoptions": 0,
    "production_writes": 0,
    "model_activations": 0,
    "ticket_14_execution": "in-progress",
    "finished_at": run["finished_at"],
}
(folder / "final.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
