"""Read-only verification of the OMO follow-up research and its pinned inputs."""

import hashlib
import json
import re
from pathlib import Path

base = Path(__file__).resolve().parents[1]
root = base.parents[1]
raw = (base / "omo-missing-flow-boundary.md").read_bytes()
assert len(raw) == 12014
assert hashlib.sha256(raw).hexdigest() == "779adb873add825e68fe55fb65287295e1b1676077717e4a52b9a7c241913d55"
text = raw.decode("utf-8")
links = []
for target in re.findall(r"\]\(([^)]+)\)", text):
    if "://" in target:
        continue
    assert (base / target.split("#", 1)[0]).is_file(), target
    links.append(target)
inputs = []
for line in text.splitlines():
    match = re.match(r"\| `([^`]+)`[^|]*\| (\d+) \| `([a-f0-9]{64})` \|", line)
    if match is None:
        continue
    name, length, sha = match.groups()
    content = (root / name).read_bytes()
    assert len(content) == int(length), name
    assert hashlib.sha256(content).hexdigest() == sha, name
    inputs.append(name)
assert len(inputs) == 11
print(json.dumps({"report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "verified_local_links": len(links), "verified_input_fingerprints": inputs,
                  "network_requests": 0, "application_calls": 0}, indent=2))
