"""Build this batch's exact staging allowlist after final verification."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
repair = here.parent
receipt = json.loads((here / "final.json").read_bytes())
assert receipt["full_passed"] == 819 and receipt["full_failed"] == 0
assert receipt["goal_complete"] is False
names = {
    "src/pring_cycle/candidate_admission.py", "src/pring_cycle/catalog.py",
    "src/pring_cycle/catalog_registry.py", "src/pring_cycle/context_projection.py",
    "src/pring_cycle/evidence.py", "src/pring_cycle/models.py",
    "src/pring_cycle/official_context.py", "src/pring_cycle/search_evidence.py",
    "src/pring_cycle/source_contract_review.py", "src/pring_cycle/storage.py",
    "src/pring_cycle/migrations/versions/0019_registered_metric_catalog.py",
    "tests/models/test_candidate_admission.py", "tests/models/test_model_lifecycle.py",
    "tests/evidence/test_point_in_time.py", "tests/integration/test_context_projection.py",
    "tests/integration/test_core_history_refresh.py", "tests/integration/test_rehearsal_cutover.py",
}
for name in (".gitattributes", "continuation-status.md", "implementation-19-catalog.md",
             "lpr-certification-gap-matrix.md", "issues/19-immutable-candidate-catalog.md"):
    names.add((repair / name).relative_to(root).as_posix())
for folder in (here, repair / "evidence-lpr-import-20260908"):
    for path in folder.rglob("*"):
        if path.is_file():
            assert "__pycache__" not in path.parts
            names.add(path.relative_to(root).as_posix())
for path in repair.glob("verification-catalog-*.txt"):
    names.add(path.relative_to(root).as_posix())
names.add((here / "commit-files.txt").relative_to(root).as_posix())
for name in names:
    assert name != "src/pring_cycle/assets/dashboard.css" and name != "src/pring_cycle/assets/dashboard.js"
(here / "commit-files.txt").write_bytes(("\n".join(sorted(names)) + "\n").encode())
assert all((root / name).is_file() for name in names)
print(f"Prepared exact owned allowlist: {len(names)}")
