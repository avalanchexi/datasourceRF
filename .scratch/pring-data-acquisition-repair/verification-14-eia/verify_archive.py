"""Check saved evidence on the host without starting WSL or importing the app."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


destination = Path(__file__).resolve().parent
repair = destination.parent
repository = repair.parents[1]
manifest = json.loads((destination / "code-fingerprint.json").read_text(encoding="utf-8"))
source_files = manifest["files"]
actual_files = {
    path.relative_to(repository).as_posix()
    for path in (repository / "src" / "pring_cycle").rglob("*.py")
}
assert actual_files == {item["path"] for item in source_files}
for item in source_files:
    content = (repository / item["path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(content).hexdigest() == item["lf_sha256"], item["path"]

evidence = repair / "evidence-14-live-eia"
report = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
expected = {
    "RBRTE": {"2026-08-24": 92.71, "2026-08-25": 88.24, "2026-08-26": 87.77,
              "2026-08-27": 90.18, "2026-08-28": 89.75, "2026-09-01": 96.02},
    "RWTC": {"2026-08-24": 86.34, "2026-08-25": 83.90, "2026-08-26": 83.46,
             "2026-08-27": 84.81, "2026-08-28": 84.57, "2026-08-31": 87.03,
             "2026-09-01": 91.48},
}
assert len(report["records"]) == 2
artifacts = {}
requests = set()
claims = set()
missing_cells = 0
for record in report["records"]:
    assert "error" not in record
    assert len(record["receipts"]) == 1
    receipt = record["receipts"][0]
    requests.add(receipt["acquisition_id"])
    for kind in ("raw_hash", "normalized_hash"):
        digest = receipt[kind]
        content = (evidence / digest).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        artifacts[digest] = len(content)
    batch = json.loads((evidence / receipt["normalized_hash"]).read_text(encoding="utf-8"))
    source_values = {
        cell["business_date"]: cell["value"]
        for cell in batch["cells"] if cell["value"] is not None
    }
    assert source_values == expected[record["series_id"]]
    assert len(batch["cells"]) == 10
    missing_cells += sum(cell["state"] == "blank" for cell in batch["cells"])
    trace_values = {}
    for trace in record["traces"]:
        assert trace["acquisition_status"] == "linked"
        assert {item["acquisition_id"] for item in trace["acquisitions"]} == {receipt["acquisition_id"]}
        assert len(trace["claims"]) == 1
        claim = trace["claims"][0]
        claims.add(claim["claim_id"])
        assert claim["release_at"] is None and claim["public_available_at"] is None
        assert claim["certification_status"] == "awaiting_source_certification"
        assert claim["fetched_at"] == receipt["received_at"]
        assert datetime.fromisoformat(claim["available_at"]) >= datetime.fromisoformat(receipt["validated_at"])
        trace_values[trace["period_end"]] = claim["value"]
    assert trace_values == source_values

assert len(requests) == 2 and len(artifacts) == 4 and len(claims) == 13
assert missing_cells == 7
for key in ("production_writes", "model_activations", "source_certification_grants", "model_adoptions"):
    assert report[key] == 0
output = {
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "scope": "saved D-drive archive and workspace source; no live database or installed package recheck",
    "workspace_source_matches_pre_failure_manifest": len(source_files),
    "artifacts": artifacts,
    "request_links": len(requests),
    "candidate_claims": len(claims),
    "missing_cells": missing_cells,
    "reference_values_match": True,
    "unknown_public_time_preserved": True,
    "requests_sent_by_this_verifier": 0,
    "database_writes_by_this_verifier": 0,
    "full_suite_accepted": False,
}
(destination / "archive-verification.json").write_text(
    json.dumps(output, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(output, indent=2))
