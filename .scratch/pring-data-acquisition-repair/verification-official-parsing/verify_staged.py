"""Verify this batch's exact staged paths and bytes."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
listed = Path(__file__).with_name("commit-files.txt").read_text(encoding="utf-8").splitlines()
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().rstrip("\0").split("\0")
assert set(listed) == set(staged), (listed, staged)
exact = {"money-normalization-boundary.md", "p1-loan-structure-full-value-audit.md", "p1-social-financing-full-value-audit.md", "p1-omo-full-value-audit.md", "pbc_money_202602.html"}
for name in staged:
    raw = (root / name).read_bytes()
    blob = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    assert blob == (raw if Path(name).name in exact else raw.replace(b"\r\n", b"\n")), name
print(f"Verified staged paths and bytes: {len(staged)}")
