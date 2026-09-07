"""Verify the exact owned files and their staged content before committing."""
import subprocess
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
expected = set((here / "commit-files.txt").read_text(encoding="utf-8").splitlines())
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().rstrip("\0").split("\0"))
assert staged == expected, (staged - expected, expected - staged)
for name in sorted(staged):
    content = (root / name).read_bytes()
    blob = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    expected_content = content if name.endswith("candidate-catalog-consumption-boundary.md") else content.replace(b"\r\n", b"\n")
    assert blob == expected_content, name
print(f"Verified exact staged paths and bytes: {len(staged)}")
