"""Finalize the combined CPI/official consumer batch only after a successful full run."""
import hashlib
import json
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parent
output = folder / "final.json"
archive = folder / "original-verification-records.zip"
assert sys.argv[1:] == ["--verified-suite-exit-code=0"]
assert not output.exists() and not archive.exists(), "Finalization is exclusive and one-time"


def decoded(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return raw.decode(encoding).replace("\r", "")


full = decoded(root / "verification-official-consumer-full-01.txt")
match = re.search(r"856 passed in ([0-9.]+)s", full)
assert match and "failed" not in full.lower() and "error" not in full.lower()
assert "174 passed in 859.55s" in decoded(root / "verification-official-consumer-clock-focused-01.txt")
assert "856 tests collected" in decoded(folder / "collected.txt")
assert "All checks passed!" in decoded(folder / "ruff.txt")
assert "Success: no issues found in 85 source files" in decoded(folder / "mypy.txt")
before = json.loads(decoded(folder / "source-before.json"))
after = json.loads(decoded(folder / "source-after.json"))
assert before == after and after["matched_source_files"] == 84
prior_results = (
    "2 failed, 644 passed, 371 errors in 788.63s",
    "1 failed, 618 passed in 1314.88s",
    "1 failed, 444 passed in 440.01s",
    "1 failed, 379 passed in 276.36s",
)
for index, result in enumerate(prior_results, 1):
    assert result in decoded(root / f"verification-cpi-consumer-full-{index:02d}.txt")
copied = []
for name in ("evidence-official-consumer-edge", "evidence-official-consumer-social"):
    receipt = json.loads((root / name / "copy-receipt.json").read_bytes())
    assert receipt["network_requests"] == receipt["acquisitions"] == 0
    for row in receipt["records"]:
        raw = (root / name / row["sha256"]).read_bytes()
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"]
        copied.append({"path": f'{name}/{row["sha256"]}', "bytes": len(raw), "sha256": row["sha256"]})
assert len(copied) == 7 and sum(row["bytes"] for row in copied) == 759872

records = sorted(set(root.glob("verification-cpi-consumer-*.txt"))
                 | set(root.glob("verification-cpi-history-*.txt"))
                 | set((root / "verification-cpi-consumer").glob("*.txt"))
                 | set(root.glob("verification-official-consumer-*.txt"))
                 | set(folder.glob("*.txt"))
                 | {folder / "source-before.json", folder / "source-after.json"})
identities = []
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as saved:
    for path in records:
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        saved.writestr(relative, raw)
        identities.append({"path": relative, "original_bytes": len(raw),
                           "original_sha256": hashlib.sha256(raw).hexdigest()})
for path, identity in zip(records, identities, strict=True):
    normalized = decoded(path).encode("utf-8")
    path.write_bytes(normalized)
    identity.update({"bytes": len(normalized), "sha256": hashlib.sha256(normalized).hexdigest()})
document = {
    "status": "cpi_and_official_consumer_code_batch_verified",
    "base_commit": "395dde73b93169d78374bb72a763641144c98dca",
    "recorded_at": datetime.now(UTC).isoformat(),
    "full_passed": 856, "full_failed": 0, "full_exit_code": 0,
    "full_seconds": float(match.group(1)), "new_cpi_cases": 12, "new_official_cases": 25,
    "clock_related_passed": 174, "clock_related_seconds": 859.55,
    "clock_opted_in_functions": 103, "clock_opted_in_files": 14,
    "installed_source_files": 84, "mypy_checked_files": 85,
    "prior_cpi_full_failures": list(prior_results),
    "reviews": {"spec_blocking_findings": 0, "standards_blocking_findings": 0,
                "nonblocking_maintenance_suggestions": ["duplicated_definition_comparison"]},
    "official_families_tested": 10, "official_metrics_tested": 16,
    "real_cpi_document_imports": 8, "real_cpi_scalars_verified": 46,
    "copied_test_originals": copied,
    "cny030_new_target_samples": 0, "tavily_exa_paired_samples": 0,
    "model_usable_search_completion_rate": None,
    "actual_source_certification_grants": 0, "actual_candidate_models": 0,
    "actual_qualified_ai_outputs": 0, "actual_cutovers": 0, "production_writes": 0,
    "ticket_19_status": "in-progress", "goal_complete": False,
    "original_record_archive": {"path": archive.relative_to(root).as_posix(),
                                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()},
    "verification_records": identities,
}
with output.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(document, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"full_passed": 856, "records_preserved": len(records), "goal_complete": False}))
