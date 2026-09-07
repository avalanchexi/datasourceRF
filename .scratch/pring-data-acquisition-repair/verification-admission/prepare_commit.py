"""Prepare only this batch's allowlist; never stage unrelated workspace changes."""
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
repair = here.parent
owned = {
    root / "src/pring_cycle/candidate_admission.py",
    root / "src/pring_cycle/cli.py",
    root / "tests/models/test_candidate_admission.py",
    repair / ".gitattributes",
    repair / "continuation-status.md",
    repair / "issues/19-immutable-candidate-catalog.md",
    repair / "implementation-19-admission.md",
    repair / "candidate-admission-contract.md",
    repair / "candidate-catalog-consumption-boundary.md",
}
owned.update(repair.glob("verification-admission-*.txt"))
owned.update(path for path in here.iterdir() if path.is_file())
allowlist = here / "commit-files.txt"
owned.add(allowlist)
assert all(path == allowlist or path.is_file() for path in owned)
names = sorted(path.relative_to(root).as_posix() for path in owned)
assert not any("assets/" in name or "inspect-16" in name for name in names)
allowlist.write_bytes(("\n".join(names) + "\n").encode())
print(f"Prepared exact owned file allowlist: {len(names)}")
