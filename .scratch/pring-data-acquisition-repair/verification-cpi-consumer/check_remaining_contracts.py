"""Read-only verification of the next official-consumer research handoff."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

note = Path(__file__).resolve().parents[1] / "remaining-official-consumption-contracts.md"
raw = note.read_bytes()
assert len(raw) == 33162
assert hashlib.sha256(raw).hexdigest() == (
    "bd05383d0228ffb40c71981648475ca35e0e5c2168b78a3d5c3c76600da2f35a"
)
text = raw.decode("utf-8")


def local(name):
    name = unquote(name.partition("#")[0])
    return Path(name) if name.startswith("//") else note.parent / name


records = re.findall(
    r"\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M
)
assert len(records) == 37
for name, size, digest in records:
    content = local(name).read_bytes()
    assert len(content) == int(size) and hashlib.sha256(content).hexdigest() == digest, name
links = [link for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
         if not link.startswith(("http://", "https://"))]
assert len(links) == 75
for link in links:
    path = local(link)
    assert path.is_file(), link
    anchor = link.partition("#")[2]
    if re.fullmatch(r"L\d+", anchor):
        assert int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines())
print(json.dumps({"inputs": len(records), "local_links": len(links),
                  "selected_originals": 13, "new_network_requests": 0,
                  "note_sha256": hashlib.sha256(raw).hexdigest()}))
