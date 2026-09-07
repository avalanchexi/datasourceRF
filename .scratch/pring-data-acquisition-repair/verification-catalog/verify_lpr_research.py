"""Independent read-only checks of the LPR research inputs and literal values."""
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

report = Path(".scratch/pring-data-acquisition-repair/lpr-certification-gap-matrix.md")
raw = report.read_bytes()
text = raw.decode("utf-8")
assert hashlib.sha256(raw).hexdigest() == "b132c53abeb9a6653de37b84cd6001877a58a2cdfa7d893c5d7ee43341bd8c21"

def local(target: str) -> Path:
    value = unquote(target.split("#", 1)[0])
    return Path(value) if value.startswith("//wsl.localhost/") else report.parent / value

links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
local_links = [target for target in links if not target.startswith(("https://", "http://"))]
for target in local_links:
    path = local(target)
    assert path.is_file(), path
    anchor = target.partition("#")[2]
    if anchor.startswith("L") and anchor[1:].isdigit():
        assert 1 <= int(anchor[1:]) <= len(path.read_text(encoding="utf-8").splitlines())
inputs = re.findall(r"^\| \[[^\]]+\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$", text, re.M)
originals = re.findall(r"\[原件\]\(([^)]+)\)；(\d+)；`([0-9a-f]{64})`", text)
assert len(inputs) == 13 and len(originals) == 9
for target, count, digest in [*inputs, *originals]:
    content = local(target).read_bytes()
    assert (len(content), hashlib.sha256(content).hexdigest()) == (int(count), digest), target
for target, _, _ in originals:
    source = html.unescape(re.sub(r"<[^>]+>", "", local(target).read_text(encoding="utf-8")))
    source = re.sub(r"\s+", "", source)
    assert "1年期LPR为3.0%，5年期以上LPR为3.5%" in source, target
    assert "以上LPR在下一次发布LPR之前有效" in source, target
    assert "09:00" in local(target).read_text(encoding="utf-8").splitlines()[59], target
assert sum(int(count) for _, count, _ in originals) == 92717
result = {"inputs": 13, "originals": 9, "literal_values_verified": 18,
          "original_bytes": 92717, "local_links": len(local_links),
          "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
          "new_network_requests_by_root_verifier": 0,
          "historical_first_publication_proven": False, "certification_grants": 0}
Path(__file__).with_name("lpr-research-verification.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
