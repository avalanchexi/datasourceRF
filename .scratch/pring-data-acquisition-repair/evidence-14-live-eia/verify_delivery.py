"""Verify the saved CLI acquisition against the independently reviewed source rows."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
report = json.loads((root / "result.json").read_text(encoding="utf-8"))
expected = {
    "RBRTE": {"2026-08-24": 92.71, "2026-08-25": 88.24, "2026-08-26": 87.77,
              "2026-08-27": 90.18, "2026-08-28": 89.75, "2026-09-01": 96.02},
    "RWTC": {"2026-08-24": 86.34, "2026-08-25": 83.90, "2026-08-26": 83.46,
             "2026-08-27": 84.81, "2026-08-28": 84.57, "2026-08-31": 87.03, "2026-09-01": 91.48},
}
assert len(report["records"]) == 2
request_ids = set()
hashes = set()
claim_ids = set()
missing = 0
for record in report["records"]:
    series = record["series_id"]
    assert "error" not in record
    assert record["result"]["status"] == "stored_candidate"
    assert record["result"]["observation_count"] == len(expected[series])
    assert len(record["receipts"]) == 1
    receipt = record["receipts"][0]
    request_ids.add(receipt["acquisition_id"])
    for key in ("raw_hash", "normalized_hash"):
        digest = receipt[key]
        assert hashlib.sha256((root / digest).read_bytes()).hexdigest() == digest
        hashes.add(digest)
    batch = json.loads((root / receipt["normalized_hash"]).read_text(encoding="utf-8"))
    assert batch["release_date"] == "2026-09-02" and batch["next_release_date"] == "2026-09-10"
    assert batch["release_timezone"] == "America/New_York" and batch["release_precision"] == "date"
    assert len(batch["cells"]) == 10
    assert {c["business_date"]: c["value"] for c in batch["cells"] if c["value"] is not None} == expected[series]
    blank_count = sum(c["state"] == "blank" for c in batch["cells"])
    assert blank_count == record["result"]["missing_cell_count"]
    missing += blank_count
    assert batch["http_response"]["response_http_status"] == "200"
    assert batch["http_response"]["response_final_url"] == batch["endpoint"]
    values = {}
    for trace in record["traces"]:
        assert trace["acquisition_status"] == "linked"
        assert {r["acquisition_id"] for r in trace["acquisitions"]} == {receipt["acquisition_id"]}
        assert len(trace["claims"]) == 1
        claim = trace["claims"][0]
        claim_ids.add(claim["claim_id"])
        values[trace["period_end"]] = claim["value"]
        assert claim["unit"] == "usd_per_barrel"
        assert claim["release_at"] is None and claim["public_available_at"] is None
        assert claim["certification_status"] == "awaiting_source_certification"
        assert claim["fetched_at"] == receipt["received_at"]
        assert datetime.fromisoformat(claim["available_at"]) >= datetime.fromisoformat(receipt["validated_at"])
        assert claim["source_reference"] == batch["endpoint"] + "#date=" + trace["period_end"]
    assert values == expected[series]
    attempt = record["latest_attempt"]
    assert attempt["outcome"] == "verified_candidate"
    assert attempt["safe_metadata"]["response_final_url"] == batch["endpoint"]
assert len(request_ids) == 2 and len(hashes) == 4 and len(claim_ids) == 13 and missing == 7
summary = {
    "verified_at": datetime.now().astimezone().isoformat(),
    "real_cli_commands": 2, "real_http_requests": 2, "verified_artifacts": 4,
    "candidate_claims": 13, "missing_calendar_cells": 7, "trace_links_verified": 13,
    "reference_values_match": True, "unknown_public_time_preserved": True,
    "system_time_not_backfilled": True, "source_certification_grants": 0,
    "model_adoptions": 0, "production_writes": 0, "verification_network_requests": 0,
}
(root / "delivery-verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary))
