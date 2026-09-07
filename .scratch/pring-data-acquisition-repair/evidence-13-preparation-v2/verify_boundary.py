"""Verify the delivery-time source-contract boundary report inputs."""
import hashlib
import json
import re
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parent
raw = (base / "a18-certification-next-boundary.md").read_bytes()
assert len(raw) == 27280 and hashlib.sha256(raw).hexdigest() == "86e15e4c5ee601d2c06783a951ae588d559545510ed328b24c8e095125d26b35"
text = raw.decode("utf-8")
links = [url for url in re.findall(r"\]\(([^)]+)\)", text) if "://" not in url]
assert len(links) == 51
for url in links:
    assert (base / url.split("#", 1)[0]).is_file(), url
inputs = re.findall(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", text)
assert len(inputs) == 33
for path, length, sha in inputs:
    source = (base / path).read_bytes()
    assert len(source) == int(length) and hashlib.sha256(source).hexdigest() == sha, path
result = {"report_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "links": 51, "directly_matched_input_fingerprints": 33, "source_certification_or_model_operations": 0}
(here / "boundary-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
