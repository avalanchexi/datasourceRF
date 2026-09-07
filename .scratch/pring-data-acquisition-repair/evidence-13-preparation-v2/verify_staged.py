"""Verify exact new-preparation batch paths and preserved artifact bytes."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
expected = set(Path(__file__).with_name("commit-files.txt").read_text(encoding="utf-8").splitlines())
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().rstrip("\0").split("\0")
assert set(staged) == expected
for name in staged:
    raw = (root / name).read_bytes()
    exact = name.endswith(".json") or name.endswith("a18-certification-next-boundary.md")
    assert subprocess.check_output(["git", "show", ":" + name], cwd=root) == (raw if exact else raw.replace(b"\r\n", b"\n")), name
print(f"Verified staged paths and bytes: {len(staged)}")
