"""Finalize terminal verification receipts; does not execute the application."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

here = Path(__file__).resolve().parent
repair = here.parent
root = here.parents[2]


def normalized(path: Path) -> str:
    raw = path.read_bytes()
    text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    text = text.replace("\r\n", "\n")
    path.write_bytes(text.encode("utf-8"))
    return text


# Call only after every recorded process has exited, including the full suite.
logs = sorted(repair.glob("verification-admission-*.txt")) + sorted(here.glob("checks-*.txt"))
for path in logs:
    normalized(path)
for path in here.glob("fingerprint-*.json"):
    normalized(path)
normalized(here / "research-verification.json")

full = (repair / "verification-admission-full.txt").read_text(encoding="utf-8")
focused = (repair / "verification-admission-final.txt").read_text(encoding="utf-8")
full_match = re.search(r"806 passed in ([0-9.]+)s", full)
focused_match = re.search(r"63 passed in ([0-9.]+)s", focused)
assert full_match and focused_match and "FAILED" not in full
assert "Success: no issues found in 83 source files" in (here / "checks-mypy.txt").read_text()
assert "All checks passed!" in (here / "checks-ruff.txt").read_text()
assert "3 files already formatted" in (here / "checks-format.txt").read_text()
before = json.loads((here / "fingerprint-final-before.json").read_text())
after = json.loads((here / "fingerprint-final-after.json").read_text())
assert before == after and before["matched_source_files"] == 82
for item in before["files"]:
    actual = (root / item["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(actual).hexdigest() == item["lf_sha256"], item["path"]

document = {
    "status": "completed_code_batch",
    "base_commit": "1cd2c00fc4be1a4fa599d5e45f8ca18fe284c2d1",
    "passed": 806, "failed": 0, "test_exit_code": 0, "full_suite_runs": 1,
    "duration_seconds": float(full_match.group(1)),
    "targeted_passed": 63, "targeted_duration_seconds": float(focused_match.group(1)),
    "new_regression_cases": 50, "installed_source_files": 82, "mypy_checked_files": 83,
    "runtime": "/home/tywin/.cache/pring-cycle/verification/admission-full-final",
    "spec_initial_findings": 3, "spec_followup_findings": 1, "spec_final_findings": 0,
    "standards_initial_findings": 1, "standards_final_findings": 0,
    "source_certification_grants": 0, "production_writes": 0, "model_activations": 0,
    "new_live_network_requests": 0, "real_candidate_models": 0,
    "ticket_19_execution": "in-progress", "goal_complete": False,
    "evidence": [],
}
for path in [*logs, here / "fingerprint-final-before.json", here / "fingerprint-final-after.json", here / "review.md", here / "research-verification.json", repair / "candidate-catalog-consumption-boundary.md"]:
    content = path.read_bytes()
    document["evidence"].append({"path": path.relative_to(repair).as_posix(), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
(here / "final.json").write_bytes((json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps({key: value for key, value in document.items() if key != "evidence"}, ensure_ascii=False))
