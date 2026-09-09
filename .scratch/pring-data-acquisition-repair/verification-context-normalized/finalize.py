"""Bind the LPR batch only after matching-code tests have actually terminated."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

folder = Path(".scratch/pring-data-acquisition-repair")
destination = folder / "verification-context-normalized/checkpoint.json"
base = "bda795f566f60205fc443f3854a8e2eb1b13b76c"
assert not destination.exists()
assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == base


def read(path: Path) -> str:
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8-sig")


terminal = json.loads(read(folder / "verification-context-normalized/terminal.json"))
for kind, log_name in (
    ("targeted", "verification-context-normalized-targeted-22.txt"),
    ("full", "verification-context-normalized-full-22.txt"),
):
    result = terminal[kind]
    assert result["state"] == "completed" and result["exit_code"] == 0
    assert result["log"] == log_name
    log = read(folder / log_name)
    match = re.search(r"(\d+) passed in ([0-9.]+)s", log)
    assert match and result["tests"] == int(match.group(1))
    assert result["duration_seconds"] == float(match.group(2))
    assert not re.search(r"\d+ (failed|errors?|skipped|deselected)", log)
assert terminal["full"]["tests"] == 1053
assert "92 source files" in read(folder / "verification-context-normalized-mypy-22.txt")
assert "All checks passed!" in read(folder / "verification-context-normalized-ruff-22.txt")
assert "All checks passed!" in read(folder / "verification-context-normalized-helper-ruff-23.txt")
assert "7 files already formatted" in read(
    folder / "verification-context-normalized-format-final.txt"
)

inputs = json.loads(read(folder / "verification-context-normalized-run-inputs-22.json"))
assert inputs["base_commit"] == base and len(inputs["files"]) == 167
for item in inputs["files"]:
    content = Path(item["path"]).read_bytes()
    assert len(content) == item["bytes"]
    assert hashlib.sha256(content).hexdigest() == item["sha256"], item["path"]
fingerprint = json.loads(read(folder / "verification-context-normalized-fingerprint-final.json"))
assert fingerprint["matched_source_files"] == len(fingerprint["files"]) == 90
for item in fingerprint["files"]:
    content = Path(item["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == item["lf_sha256"], item["path"]

assert "21 passed" in read(folder / "verification-context-normalized-lpr-green-08.txt")
assert "2 failed" in read(folder / "verification-context-normalized-lpr-status-red-09.txt")
for suffix in ("replay-red-13", "calendar-red-18"):
    assert "1 failed" in read(folder / f"verification-context-normalized-lpr-{suffix}.txt")
assert "22 passed" in read(folder / "verification-context-normalized-lpr-calendar-green-19.txt")

owned = [
    Path("src/pring_cycle/official_lpr.py"),
    Path("src/pring_cycle/search_evidence.py"),
    Path("src/pring_cycle/context_projection.py"),
    Path("src/pring_cycle/release_calendar.py"),
    Path("src/pring_cycle/model_evaluation.py"),
    Path("tests/models/test_candidate_admission.py"),
    Path("tests/adapters/test_chinamoney_lpr.py"),
    folder / "continuation-status.md",
    folder / "issues/19-immutable-candidate-catalog.md",
    folder / "implementation-19-context-normalized-consumption.md",
    folder / "official-macro-normalized-next-step.md",
    folder / "official-macro-derived-selection-boundary.md",
    folder / "rrr-official-completeness-followup-20260909.md",
    folder / "pp-official-followup-20260909.md",
    *sorted(folder.glob("verification-context-normalized-*.txt")),
    *sorted(folder.glob("verification-context-normalized-*.json")),
    *sorted(folder.glob("verification-context-normalized-*.md")),
    folder / "verification-context-normalized/finalize.py",
    folder / "verification-context-normalized/terminal.json",
]
assert len(owned) == len(set(owned))
files = []
for path in owned:
    content = path.read_bytes()
    assert content, path
    files.append(
        {
            "path": path.as_posix(),
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    )
record = {
    "recorded_at": datetime.now(UTC).isoformat(),
    "base_commit": base,
    "scope": "LPR acquisition consumption, dual as-of release calendar and public component replay",
    "software_slice_passed": True,
    "default_suite_passed": True,
    "default_suite_tests": terminal["full"]["tests"],
    "default_suite_duration_seconds": terminal["full"]["duration_seconds"],
    "new_tests": 22,
    "mypy_source_files": 92,
    "installed_python_sources": 90,
    "spec_findings_remaining": 0,
    "standards_findings_remaining": 0,
    "lpr_normalized_consumer_integrity_verified": True,
    "lpr_public_component_replay_verified": True,
    "all_family_normalized_consumer_integrity_verified": False,
    "all_real_p1_p2_positive_consumption_verified": False,
    "new_catalog_active_worker_end_to_end_verified": False,
    "real_source_certification": False,
    "real_complete_candidate": False,
    "real_120_china_trading_day_replay": False,
    "real_qualified_ai_outputs": 0,
    "production_cutover": False,
    "project_full_gate_passed": False,
    "files": files,
}
with destination.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(record, stream, indent=2)
    stream.write("\n")
print(json.dumps({"checkpoint": destination.as_posix(), "bound_files": len(files)}))
