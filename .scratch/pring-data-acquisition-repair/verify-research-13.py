"""Root verification of the bounded ticket 13 handoff; no network or runtime writes."""
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
evidence = folder / "evidence-13"
report = folder / "research-13.md"
expected = "dcbdf9a07095e5bfb2110ff2f3a51e9049dc1bece87b3859207df1ece0f973e1"
assert hashlib.sha256(report.read_bytes()).hexdigest() == expected
manifest = json.loads((evidence / "artifact-verification.json").read_text(encoding="utf-8"))
originals = [p for p in evidence.iterdir() if re.fullmatch("[0-9a-f]{64}", p.name)]
assert len(originals) == 27
for path in originals:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name, path
for entry in manifest["original_records"]:
    path = (evidence / entry["local_file"]).resolve()
    assert path.is_relative_to(evidence.resolve()), path
    content = path.read_bytes()
    assert len(content) == entry["bytes"], path
    assert hashlib.sha256(content).hexdigest() == entry["sha256"], path
links = 0
for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
    if not target.startswith(("https:", "http:", "#")):
        assert (folder / target.split("#", 1)[0]).exists(), target
        links += 1
root = folder.parent.parent
deliveries = (evidence / "delivery-files.txt").read_text(encoding="utf-8").splitlines()
for relative in deliveries:
    path = (root / relative).resolve()
    assert path.is_relative_to(folder.resolve()) and path.is_file(), relative
output = {
    "verified_at": datetime.now(UTC).isoformat(), "report_sha256": expected,
    "original_files": len(originals), "original_bytes": sum(p.stat().st_size for p in originals),
    "local_links": links, "delivery_files": len(deliveries),
    "certification_completed": False, "network_requests": 0, "production_writes": 0,
}
(folder / "research-13-verification.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, ensure_ascii=False))
