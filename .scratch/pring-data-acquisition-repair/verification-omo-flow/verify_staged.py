"""Verify exact batch ownership and staged bytes without changing the index."""

import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
listed = Path(__file__).with_name("commit-files.txt").read_text(encoding="utf-8").splitlines()
staged = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "-z"], cwd=root
).decode().rstrip("\0").split("\0")
assert set(listed) == set(staged), (listed, staged)
exact = {
    "p1-industrial-finance-full-value-audit.md",
    "p1-industrial-va-full-value-audit.md",
    "p1-tool-liquidity-full-value-audit.md",
    "p1-capacity-utilization-full-value-audit.md",
    "p1-money-full-value-audit.md",
}
for name in staged:
    raw = (root / name).read_bytes()
    index = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    expected = raw if Path(name).name in exact else raw.replace(b"\r\n", b"\n")
    assert index == expected, name
print(f"Verified staged paths and bytes: {len(staged)}")
