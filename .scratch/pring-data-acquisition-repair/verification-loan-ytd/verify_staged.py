"""Verify this batch's staged allowlist and bytes without changing the index."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
listed = (Path(__file__).with_name("commit-files.txt")).read_text().splitlines()
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "-z"], cwd=root
).decode().rstrip("\0").split("\0")
assert set(listed) == set(staged), (listed, staged)
exact = {"p1-ppi-full-value-audit.md", "p1-pmi-full-value-audit.md", "omo-missing-flow-boundary.md"}
for name in staged:
    raw = (root / name).read_bytes()
    index = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    expected = raw if Path(name).name in exact else raw.replace(b"\r\n", b"\n")
    assert index == expected, name
print(f"Verified staged paths and bytes: {len(staged)}")
