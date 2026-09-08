"""Preserve original logs and record the completed CPI batch once, after all checks."""

import hashlib
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parent
output = folder / "final.json"
archive = folder / "original-logs.zip"
assert not output.exists() and not archive.exists(), "One-time finalization already started"


def log_text(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return raw.decode(encoding).replace("\r", "")


full = log_text(root / "verification-cpi-consumer-full-04.txt")
assert "17 passed, 63 deselected in " in full
assert "831 passed in " in full
duration = re.search(r"831 passed in ([0-9.]+)s", full)
assert duration is not None
assert "failed" not in full.lower() and "error" not in full.lower()
first = log_text(root / "verification-cpi-consumer-full-01.txt")
assert "2 failed, 644 passed, 371 errors in 788.63s" in first
second = log_text(root / "verification-cpi-consumer-full-02.txt")
assert "1 failed, 618 passed in 1314.88s" in second
third = log_text(root / "verification-cpi-consumer-full-03.txt")
assert "1 failed, 444 passed in 440.01s" in third
assert "All checks passed!" in log_text(folder / "checks-ruff.txt")
assert "Success: no issues found in 85 source files" in log_text(folder / "checks-mypy.txt")
before = json.loads((folder / "source-verified-before.json").read_bytes())
after = json.loads((folder / "source-verified-after.json").read_bytes())
assert before == after and after["matched_source_files"] == 84
recovered = json.loads((folder / "recovered-import-databases.json").read_bytes())
assert len(recovered["results"]) == 2
assert all(row["quick_check"] == "ok" for row in recovered["results"])

logs = sorted(set(root.glob("verification-cpi-consumer-*.txt"))
              | set(root.glob("verification-cpi-history-*.txt"))
              | set(folder.glob("*.txt")))
identities = []
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as saved:
    for path in logs:
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        saved.writestr(relative, raw)
        identities.append({"path": relative, "original_bytes": len(raw),
                           "original_sha256": hashlib.sha256(raw).hexdigest()})
for path, identity in zip(logs, identities, strict=True):
    normalized = log_text(path).encode("utf-8")
    path.write_bytes(normalized)
    identity.update({"bytes": len(normalized), "sha256": hashlib.sha256(normalized).hexdigest()})

document = {
    "status": "completed_cpi_code_and_acquisition_preparation_batch",
    "base_commit": "395dde7",
    "recorded_at": datetime.now(UTC).isoformat(),
    "full_passed": 831, "full_failed": 0,
    "full_duration_seconds": float(duration.group(1)),
    "new_cpi_regressions": 12, "recovery_focused_passed": 17,
    "test_clock_stabilizations": 5,
    "earlier_related_passed": 167,
    "first_full": {"passed": 644, "failed": 2, "errors": 371, "seconds": 788.63},
    "second_full": {"passed": 618, "failed": 1, "errors": 0, "seconds": 1314.88},
    "third_full": {"passed": 444, "failed": 1, "errors": 0, "seconds": 440.01},
    "installed_source_files": 84, "mypy_checked_files": 85,
    "test_storage": "isolated D-backed ext4; no production paths moved",
    "real_cpi_document_imports": 8, "real_cpi_scalars_verified": 46,
    "terms_http_gets": 1, "terms_http_status": 200,
    "actual_cpi_artifacts": 18,
    "cpi_and_lpr_recovered_database_integrity": "ok",
    "cny030_new_official_gets": 3, "cny030_new_target_samples": 0,
    "tavily_exa_paired_samples": 0, "model_usable_search_completion_rate": None,
    "source_certification_grants": 0, "real_candidate_models": 0,
    "production_writes": 0, "model_activations": 0, "actual_cutovers": 0,
    "ticket_19_execution": "in-progress", "goal_complete": False,
    "original_log_archive": {"path": "verification-cpi-consumer/original-logs.zip",
                             "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()},
    "logs": identities,
}
with output.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(document, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"status": document["status"], "full_passed": 831,
                  "logs_preserved": len(logs), "goal_complete": False}))
