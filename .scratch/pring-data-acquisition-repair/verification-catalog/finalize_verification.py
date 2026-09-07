"""Finalize only terminal receipts; no application imports or database changes."""
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
    path.write_bytes(text.encode())
    return text

logs = sorted(repair.glob("verification-catalog-*.txt")) + sorted(here.glob("*.txt"))
for path in logs:
    normalized(path)
for path in here.glob("fingerprint-*.json"):
    normalized(path)
full = (repair / "verification-catalog-full-final-02.txt").read_text(encoding="utf-8")
match = re.search(r"819 passed in ([0-9.]+)s", full)
assert match and "FAILED" not in full
first = (repair / "verification-catalog-full-final.txt").read_text(encoding="utf-8")
assert "2 failed, 817 passed" in first
assert "126 passed in 91.31s" in (repair / "verification-catalog-focused-03.txt").read_text()
assert "5 passed, 58 deselected in 6.35s" in (repair / "verification-catalog-source-green-final.txt").read_text()
assert "34 passed in 36.70s" in (repair / "verification-catalog-migration-green.txt").read_text()
assert "Success: no issues found in 85 source files" in (here / "checks-mypy.txt").read_text()
assert "All checks passed!" in (here / "checks-ruff.txt").read_text()
assert "10 files already formatted" in (here / "checks-format.txt").read_text()
before = json.loads((here / "fingerprint-final-before.json").read_bytes())
after = json.loads((here / "fingerprint-final-after.json").read_bytes())
assert before == after and before["matched_source_files"] == 84
for item in before["files"]:
    content = (root / item["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == item["lf_sha256"]
legacy = json.loads((here / "legacy-typing.json").read_bytes())
assert legacy["legacy_diagnostics_unchanged"] and len(legacy["current_result"]["errors"]) == 29
imports = json.loads((here / "lpr-import-verification.json").read_bytes())
assert imports["validated_imports"] == 9 and imports["source_claims"] == 0
document = {
    "status": "completed_code_and_acquisition_preparation_batch",
    "base_commit": "0679a4758316bbeb520da9d79aafeb7572f5c6ce",
    "full_passed": 819, "full_failed": 0, "full_test_exit_code": 0,
    "full_duration_seconds": float(match.group(1)), "full_suite_runs": 2,
    "first_full_passed": 817, "first_full_failed": 2,
    "first_failures": ["legacy schema test retained new table", "one v1 test double lacked database_path"],
    "new_regression_cases": 13, "related_batch_passed": 126,
    "subsequent_source_checks_passed": 5, "migration_and_lifecycle_checks_passed": 34,
    "installed_source_files": 84, "mypy_checked_files": 85,
    "expanded_legacy_type_errors": 29, "new_legacy_type_errors": 0,
    "spec_final_findings": 0, "standards_final_findings": 0,
    "real_lpr_document_imports": 9, "real_lpr_values_verified": 18,
    "research_network_gets": 2, "tavily_exa_paired_samples": 0,
    "bse_official_search_queries": 2, "bse_new_document_reads": 0, "bse_target_samples": 0,
    "real_model_usable_search_completion_rate": None,
    "source_certification_grants": 0, "production_writes": 0,
    "real_candidate_models": 0, "model_activations": 0, "actual_cutovers": 0,
    "ticket_19_execution": "in-progress", "goal_complete": False,
    "evidence": [],
}
for path in [*logs, here / "fingerprint-final-before.json", here / "fingerprint-final-after.json",
             here / "review.md", here / "legacy-typing.json", here / "lpr-research-verification.json",
             here / "lpr-import-verification.json", repair / "lpr-certification-gap-matrix.md",
             repair / "evidence-lpr-import-20260908/receipts.json"]:
    content = path.read_bytes()
    document["evidence"].append({"path": path.relative_to(repair).as_posix(), "bytes": len(content),
                                 "sha256": hashlib.sha256(content).hexdigest()})
(here / "final.json").write_bytes((json.dumps(document, indent=2) + "\n").encode())
print(json.dumps({key: value for key, value in document.items() if key != "evidence"}))
