"""Independently check the saved research bytes without network or runtime writes."""
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
evidence = folder / "evidence-04"
records = json.loads((evidence / "receipts.json").read_text(encoding="utf-8"))
records += json.loads((evidence / "nh-daily-batch-receipts.json").read_text(encoding="utf-8"))
verified = []
for record in records:
    if "local_file" not in record:
        continue
    path = (evidence / record["local_file"]).resolve()
    assert path.is_relative_to(evidence.resolve())
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == record["sha256"], path
    assert len(content) == record["byte_count"], path
    verified.append(record["sha256"])
report = (folder / "research-04.md").read_text(encoding="utf-8")
for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", report):
    if not target.startswith(("http:", "https:", "#")):
        assert (folder / target.split("#", 1)[0]).exists(), target
data_checks = []
for record in records:
    if record.get("name") in {"csi-000985-120d", "csi-000012-120d", "csi-000985-259d", "csi-000012-259d"}:
        rows = json.loads((evidence / record["local_file"]).read_bytes())["data"]
        expected = 259 if "259d" in record["name"] else 120
        assert len(rows) == len({row["tradeDate"] for row in rows}) == expected
        assert all(float(row["close"]) > 0 for row in rows)
        assert all(not any(key in row for key in ("publishedAt", "release_at", "public_available_at")) for row in rows)
        data_checks.append({"source": record["name"], "unique_trade_dates": expected, "publication_time_certified": False})
output = {"verified_at": datetime.now(UTC).isoformat(), "status": "evidence_files_verified",
    "responses_with_verified_originals": len(verified), "unique_originals": len(set(verified)),
    "report_sha256": hashlib.sha256((folder / "research-04.md").read_bytes()).hexdigest(),
    "csi_data_checks": data_checks, "certification_completed": False,
    "network_requests": 0, "production_writes": 0}
(folder / "research-04-verification.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, ensure_ascii=False))
