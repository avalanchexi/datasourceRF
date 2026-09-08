"""Independent read-only check of the CNY030 research handoff and cited originals."""

import hashlib
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

note = Path(__file__).resolve().parents[1] / "cny030-official-next-boundary.md"
raw = note.read_bytes()
assert len(raw) == 14722
assert hashlib.sha256(raw).hexdigest() == (
    "cd983bcbdc398ad03d41a5f8c3190d01b5d40c538d8cf8137263d14377890f6f"
)
text = raw.decode("utf-8")
inputs = re.findall(
    r"^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M
)
assert len(inputs) == 10
for relative, size, digest in inputs:
    content = (note.parent / relative).read_bytes()
    assert len(content) == int(size) and hashlib.sha256(content).hexdigest() == digest
links = [link for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
         if not link.startswith(("http://", "https://"))]
for link in links:
    name, _, anchor = link.partition("#")
    path = note.parent / unquote(name)
    assert path.is_file(), link
    if re.fullmatch(r"L\d+", anchor):
        assert int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines())
assert len(links) == 22
folder = note.parent / "evidence-06"
empty = json.loads((folder / "8309cff714d5f872cea03bfa413b0270b30b5db6545e99d9dd2b59bc489344eb.json").read_bytes())
assert empty["data"] == []
basic = json.loads((folder / "38dbe39b0f3719e98c1e36d24dff52b4140f8cb1b5fd2037af745e4e025da643.json").read_bytes())["data"]
assert len(basic) == 29 and all(value is None for value in basic.values())
with zipfile.ZipFile(folder / "37bf6b5edaefd3d6e51ad28df98455d1ce1657dd59ce4de44570c53720239b07.xlsx") as archive:
    sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    assert len(sheet.findall(".//x:row", namespace)) == 1
    assert len(sheet.findall(".//x:c", namespace)) == 15
print(json.dumps({"inputs": len(inputs), "local_links": len(links),
                  "verified_official_numeric_samples": 0, "new_network_requests": 0,
                  "note_sha256": hashlib.sha256(raw).hexdigest()}))
