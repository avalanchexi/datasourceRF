"""Root read-only verification of the next catalog-consumption research snapshot."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[3]
report = root / ".scratch/pring-data-acquisition-repair/candidate-catalog-consumption-boundary.md"
raw = report.read_bytes()
assert len(raw) == 31750
assert hashlib.sha256(raw).hexdigest() == "67259c271373d9ea51da8677a2b95987966dfe790817dbb29f635b43f5e88d2d"
text = raw.decode("utf-8")
rows = re.findall(r"^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M)
assert len(rows) == 38
for target, count, expected in rows:
    path = (report.parent / unquote(target.split("#", 1)[0])).resolve()
    assert path.is_relative_to(root)
    content = path.read_bytes()
    assert (len(content), hashlib.sha256(content).hexdigest()) == (int(count), expected), path
links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
for target in links:
    file_part, _, anchor = target.partition("#")
    path = (report.parent / unquote(file_part)).resolve()
    assert path.is_relative_to(root) and path.is_file(), path
    if anchor.startswith("L") and anchor[1:].isdigit():
        assert 1 <= int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines()), target
assert len(links) == 114
print(json.dumps({"status": "passed", "input_files": len(rows), "local_links": len(links), "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(), "scope": "snapshot before ticket19 status comment changes"}))
