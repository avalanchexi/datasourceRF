"""Verify boundary research against its fixed Git baseline, not changing source."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parent
repo = base.parents[1]
raw = (base / "source-history-receipt-boundary.md").read_bytes()
assert len(raw) == 18569 and hashlib.sha256(raw).hexdigest() == "fad9efd185f74c14c12ab93cff5a09c8dc8f2d3a0c2510074bcc4dca98cdf55b"
text = raw.decode("utf-8")
links = [url for url in re.findall(r"\]\(([^)]+)\)", text) if "://" not in url]
assert len(links) == 25
for url in links:
    assert (base / url.split("#", 1)[0]).is_file()
baseline = "a569fd757c7d19a4ae95b980bd2b1c0c51cba973"
inputs = re.findall(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", text)
assert len(inputs) == 16
for path, length, sha in inputs:
    relative = (base / path).resolve().relative_to(repo).as_posix()
    blob = subprocess.check_output(["git", "show", baseline + ":" + relative], cwd=repo)
    assert len(blob) == int(length) and hashlib.sha256(blob).hexdigest() == sha
fixtures = {
    "pbc_social_financing_202501.html": (25006, "cc6625821fcecffb2042901fdac0db1b7f97391a6b845e1fb101134bda1a4257"),
    "nbs_gdp_2023q4.html": (322515, "7f583c54493030fb019cbd09de3c0a4323691125b3d72fc8627ab5425d2b6861"),
}
for name, (length, sha) in fixtures.items():
    source = (repo / "tests/fixtures" / name).read_bytes()
    assert len(source) == length and hashlib.sha256(source).hexdigest() == sha
next_raw = (base / "ticket19-implementation-boundary.md").read_bytes()
assert len(next_raw) == 10142 and hashlib.sha256(next_raw).hexdigest() == "fe43b6c3766779524b86a3629ecb3f72a74abc957239b20968cb0050c082e5bc"
next_text = next_raw.decode("utf-8")
next_links = [url for url in re.findall(r"\]\(([^)]+)\)", next_text) if "://" not in url]
assert len(next_links) == 25
for url in next_links:
    assert (base / url.split("#", 1)[0]).is_file()
next_inputs = re.findall(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", next_text)
assert len(next_inputs) == 13
for relative, length, sha in next_inputs:
    blob = subprocess.check_output(["git", "show", baseline + ":" + relative], cwd=repo)
    assert len(blob) == int(length) and hashlib.sha256(blob).hexdigest() == sha
result = {"report_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "local_links": len(links), "git_baseline": baseline, "matched_git_input_fingerprints": 16, "exact_fixtures": 2, "fixture_bytes": 347521, "ticket19_report_sha256": hashlib.sha256(next_raw).hexdigest(), "ticket19_report_bytes": len(next_raw), "ticket19_local_links": 25, "ticket19_matched_git_inputs": 13}
(here / "research-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result))
