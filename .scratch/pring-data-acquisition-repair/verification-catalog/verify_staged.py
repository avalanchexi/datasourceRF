"""Verify exact staged ownership and every staged file's intended bytes."""
import subprocess
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
expected = set((here / "commit-files.txt").read_text(encoding="utf-8").splitlines())
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=root).decode().rstrip("\0").split("\0"))
assert staged == expected, (staged - expected, expected - staged)
for name in sorted(staged):
    content = (root / name).read_bytes()
    attributes = subprocess.check_output(["git", "check-attr", "-z", "text", "--", name], cwd=root).split(b"\0")
    if attributes[2] != b"unset":
        content = content.replace(b"\r\n", b"\n")
    blob = subprocess.check_output(["git", "show", ":" + name], cwd=root)
    assert content == blob, name
print(f"Verified exact staged paths and bytes: {len(staged)}")
