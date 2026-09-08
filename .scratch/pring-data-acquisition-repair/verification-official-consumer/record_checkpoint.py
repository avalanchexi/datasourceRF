"""Preserve a non-green full run and its unchanged-timeout isolated retry honestly."""
import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parent
output = folder / "checkpoint.json"
archive = folder / "original-checkpoint-records.zip"
assert not output.exists() and not archive.exists()


def decoded(path):
    data = path.read_bytes()
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return data.decode(encoding).replace("\r", "")


assert "1 failed, 855 passed in 3229.99s" in decoded(root / "verification-official-consumer-full-01.txt")
assert "1 passed in 6.20s" in decoded(root / "verification-official-consumer-cli-repro-01.txt")
assert "174 passed in 859.55s" in decoded(root / "verification-official-consumer-clock-focused-01.txt")
assert "All checks passed!" in decoded(folder / "ruff.txt")
assert "Success: no issues found in 85 source files" in decoded(folder / "mypy.txt")
before = json.loads(decoded(folder / "source-before.json"))
after = json.loads(decoded(folder / "source-after-full-01.json"))
assert before == after and before["matched_source_files"] == 84
records = sorted(set(root.glob("verification-cpi-consumer-*.txt"))
                 | set(root.glob("verification-cpi-history-*.txt"))
                 | set((root / "verification-cpi-consumer").glob("*.txt"))
                 | set(root.glob("verification-official-consumer-*.txt"))
                 | set(folder.glob("*.txt"))
                 | {folder / "source-before.json", folder / "source-after-full-01.json"})
identities = []
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as saved:
    for path in records:
        data = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        saved.writestr(relative, data)
        identities.append({"path": relative, "original_bytes": len(data),
                           "original_sha256": hashlib.sha256(data).hexdigest()})
for path, identity in zip(records, identities, strict=True):
    data = decoded(path).encode("utf-8")
    path.write_bytes(data)
    identity.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
document = {
    "status": "implementation_checkpoint_full_gate_open", "goal_complete": False,
    "base_commit": "395dde73b93169d78374bb72a763641144c98dca",
    "recorded_at": datetime.now(UTC).isoformat(),
    "full_run": {"passed": 855, "failed": 1, "seconds": 3229.99, "exit_code": 1,
                 "failure": "offline_runtime_init_subprocess_exceeded_60_second_test_timeout"},
    "isolated_retry": {"passed": 1, "seconds": 6.20, "exit_code": 0,
                       "test_timeout_unchanged_seconds": 60, "application_changes_since_full": 0},
    "full_gate_passed": False,
    "clock_related": {"passed": 174, "failed": 0, "seconds": 859.55},
    "collected_tests": 856, "new_cpi_cases": 12, "new_official_cases": 25,
    "installed_source_files_matched_before_after": 84, "mypy_checked_files": 85,
    "review_blocking_findings": {"spec": 0, "standards": 0},
    "real_cpi_document_imports": 8, "real_cpi_scalars_verified": 46,
    "actual_source_certification_grants": 0, "actual_candidate_models": 0,
    "actual_qualified_ai_outputs": 0, "actual_cutovers": 0, "production_writes": 0,
    "tavily_exa_paired_samples": 0, "model_usable_search_completion_rate": None,
    "archive": {"path": archive.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()},
    "records": identities,
}
with output.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(document, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"records_preserved": len(records), "full_gate_passed": False,
                  "full_passed": 855, "retry_passed": 1, "goal_complete": False}))
