"""Verify preserved breadth research originals and links, without network calls."""
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
evidence = folder / "evidence-08"
report = folder / "research-08.md"
digest = hashlib.sha256(report.read_bytes()).hexdigest()
assert digest == "2d4748cc4540a17ad94276002414bf4592eb07379dad0935d5334c76458d15b2"
originals = [p for p in evidence.iterdir() if re.fullmatch(r"[0-9a-f]{64}", p.name)]
for path in originals:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name, path
assert len(originals) == 34
counts = {}
for name in ("receipts.json", "imports.json"):
    records = json.loads((evidence / name).read_text(encoding="utf-8"))
    for record in records:
        path = (evidence / record["local_file"]).resolve()
        assert path.is_relative_to(evidence.resolve()), path
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == record["sha256"], path
        assert len(content) == record.get("byte_count", record.get("bytes")), path
    counts[name] = len(records)
links = 0
for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
    if not target.startswith(("http:", "https:", "#")):
        assert (folder / target.split("#", 1)[0]).exists(), target
        links += 1
output = {"verified_at": datetime.now(UTC).isoformat(), "report_sha256": digest,
    "originals_verified": len(originals), "index_entries_verified": counts,
    "local_links_verified": links, "historical_publication_certified": False,
    "certification_completed": False, "network_requests": 0, "production_writes": 0}
(folder / "research-08-verification.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, ensure_ascii=False))
