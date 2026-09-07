"""Verify exact ownership and staged bytes for the history receipt batch."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[3]
expected = set(Path(__file__).with_name("commit-files.txt").read_text(encoding="utf-8").splitlines())
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().rstrip("\0").split("\0")
assert set(staged) == expected
exact = {"source-history-receipt-boundary.md", "ticket19-implementation-boundary.md", "pbc_social_financing_202501.html", "nbs_gdp_2023q4.html"}
for name in staged:
    raw = (root / name).read_bytes()
    blob = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    assert blob == (raw if Path(name).name in exact else raw.replace(b"\r\n", b"\n")), name
print(f"Verified staged paths and bytes: {len(staged)}")
