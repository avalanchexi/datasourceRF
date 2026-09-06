"""Independently verify preserved research bytes and links without network access."""
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
expected_reports = {
    "06": "955e25954a1a305d2b4aed42ea9de565a48164eb2785d92a9a686c0fd8fe43dc",
    "07": "148f13126e27d2e5dad77965991629981eabd353032beddabac78adbe437206b",
    "11": "a51e5ba29fbc0083b14d1f7021542d6bc02f7116d5dd38785200482afe26f80e",
}
results = []
for ticket, expected in expected_reports.items():
    report = folder / f"research-{ticket}.md"
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    assert digest == expected, (report, digest)
    evidence = folder / f"evidence-{ticket}"
    originals = []
    for path in evidence.rglob("*"):
        if path.is_file() and re.fullmatch(r"[0-9a-f]{64}", path.stem):
            content = path.read_bytes()
            assert hashlib.sha256(content).hexdigest() == path.stem, path
            originals.append(path.stem)
    indexes = {}
    for name in ("receipts.json", "imports.json"):
        path = evidence / name
        if not path.exists():
            continue
        records = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(records, list)
        verified = 0
        for record in records:
            if "local_file" not in record:
                continue
            artifact = (evidence / record["local_file"]).resolve()
            assert artifact.is_relative_to(evidence.resolve()), artifact
            content = artifact.read_bytes()
            assert hashlib.sha256(content).hexdigest() == record["sha256"], artifact
            assert len(content) == record.get("byte_count", record.get("bytes")), artifact
            verified += 1
        indexes[name] = {"records": len(records), "verified_originals": verified}
    links = 0
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", report.read_text(encoding="utf-8")):
        if not target.startswith(("http:", "https:", "#")):
            artifact = (folder / target.split("#", 1)[0]).resolve()
            assert artifact.exists(), (report, target)
            links += 1
    checks = []
    if ticket == "06":
        records = json.loads((evidence / "receipts.json").read_text(encoding="utf-8"))
        for record in records:
            if record["name"] in {f"csi-{code}-259d" for code in ("000300", "000905", "000852", "930916")}:
                rows = json.loads((evidence / record["local_file"]).read_bytes())["data"]
                assert len(rows) == len({r["tradeDate"] for r in rows}) == 259
                assert all(float(r["close"]) > 0 for r in rows)
                checks.append({"source": record["name"], "unique_dates": 259})
        assert len(checks) == 4
    results.append({"ticket": ticket, "report_sha256": digest,
        "hash_named_files_verified": len(originals), "unique_hashes": len(set(originals)),
        "indexes": indexes, "local_links_verified": links, "data_checks": checks})
output = {"verified_at": datetime.now(UTC).isoformat(), "results": results,
    "status": "preserved_files_verified", "certification_completed": False,
    "historical_publication_time_certified": False, "network_requests": 0, "production_writes": 0}
(folder / "research-06-07-11-verification.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(output, ensure_ascii=False))
