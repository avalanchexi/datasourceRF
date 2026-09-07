"""Read-only validation of the preceding P2 freshness research delivery."""

import hashlib
import json
import re
from pathlib import Path

base = Path(__file__).resolve().parents[1]
report = base / "p2-freshness-evidence-boundary.md"
raw = report.read_bytes()
expected = "eeadd850cc2035022ae0c25a9629d98fc6704e86fa02583a172731d15432895e"
assert len(raw) == 9295
assert hashlib.sha256(raw).hexdigest() == expected
links = []
originals = {}
for target in re.findall(r"\]\(([^)]+)\)", raw.decode("utf-8")):
    if "://" in target:
        continue
    path = (base / target.split("#", 1)[0]).resolve()
    assert path.is_file(), target
    links.append(target)
    if re.fullmatch(r"[a-f0-9]{64}", path.name):
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == path.name
        originals[target] = len(content)
assert len(links) == 14
assert len(originals) == 5
assert sum(originals.values()) == 1075543
print(json.dumps({
    "report_bytes": len(raw), "report_sha256": expected,
    "verified_local_links": links, "verified_original_bytes": originals,
    "network_requests": 0, "production_writes": 0,
}, indent=2))
