"""Bind the completed RRR software slice without asserting project acceptance."""
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[3]
directory = root / ".scratch/pring-data-acquisition-repair"


def read_text(path: Path) -> str:
    content = path.read_bytes()
    return content.decode("utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


assert "246 passed in 287.17s" in read_text(directory / "verification-rrr-members-associated-01.txt")
assert "41 passed, 115 deselected in 83.69s" in read_text(directory / "verification-rrr-members-final-01.txt")
assert "no issues found in 86 source files" in read_text(directory / "verification-rrr-members-mypy.txt")
assert "All checks passed!" in read_text(directory / "verification-rrr-members-ruff.txt")
fingerprint = json.loads(read_text(directory / "verification-rrr-members-fingerprint.json"))
assert fingerprint["matched_source_files"] == 85
for item in fingerprint["files"]:
    body = (root / item["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(body).hexdigest() == item["lf_sha256"], item["path"]
paths = [root / "src/pring_cycle" / name for name in (
    "evidence.py", "published_events.py", "search_evidence.py",
    "context_projection.py", "model_evaluation.py",
)] + [root / "tests/models/test_candidate_admission.py"]
paths += list(directory.glob("verification-rrr-members-*.txt"))
paths += [directory / name for name in (
    "verification-rrr-members-fingerprint.json", "implementation-19-rrr-members.md",
    "warrants-consumption-next-slice.md",
)]
records = []
for path in sorted(paths):
    body = path.read_bytes()
    records.append({"path": path.relative_to(root).as_posix(), "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()})
document = {
    "recorded_at": datetime.now(UTC).isoformat(),
    "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "scope": "registered RRR complete publication consumption and component replay",
    "software_slice_passed": True,
    "associated_tests_before_final_identity_exclusion": 246,
    "final_focused_tests": 41,
    "mypy_checked_files": 86,
    "installed_python_sources_matched": 85,
    "spec_findings_remaining": 0,
    "standards_findings_remaining": 0,
    "project_full_gate_passed": False,
    "real_certification_or_candidate_created": False,
    "real_120_day_replay_executed": False,
    "production_cutover": False,
    "files": records,
}
destination = Path(__file__).with_name("checkpoint.json")
with destination.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(document, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"checkpoint": str(destination), "bound_files": len(records)}))
