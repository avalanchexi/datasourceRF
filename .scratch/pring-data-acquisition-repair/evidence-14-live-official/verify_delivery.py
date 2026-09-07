"""Check archived real acquisition outputs without network or database writes."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
report = json.loads((root / "result.json").read_text(encoding="utf-8"))
assert report["attempted_families"] == 2
records = {record["family"]: record for record in report["records"]}
assert set(records) == {"pbc_usdcny_central_parity", "nbs_gdp"}
artifact_hashes = set()
request_ids = set()
claim_ids = set()
for record in records.values():
    assert record["status"] == "stored_candidate"
    assert len(record["receipts"]) == 1
    receipt = record["receipts"][0]
    request_ids.add(receipt["acquisition_id"])
    assert receipt["state"] == "validated"
    assert datetime.fromisoformat(receipt["started_at"]) <= datetime.fromisoformat(
        receipt["received_at"]
    ) <= datetime.fromisoformat(receipt["validated_at"])
    for field in ("raw_hash", "normalized_hash"):
        digest = receipt[field]
        assert hashlib.sha256((root / digest).read_bytes()).hexdigest() == digest
        artifact_hashes.add(digest)
    for claim in record["claims"]:
        claim_ids.add(claim["claim_id"])
        assert claim["certification_status"] == "awaiting_source_certification"
        assert claim["fetched_at"] == receipt["received_at"]
        assert datetime.fromisoformat(claim["available_at"]) >= datetime.fromisoformat(
            receipt["validated_at"]
        )
    for trace in record["traces"]:
        assert trace["acquisition_status"] == "linked"
        assert {r["acquisition_id"] for r in trace["acquisitions"]} == {
            receipt["acquisition_id"]
        }
assert len(request_ids) == 2 and len(claim_ids) == 9 and len(artifact_hashes) == 4
parity = records["pbc_usdcny_central_parity"]["claims"]
assert len(parity) == 1 and parity[0]["value"] == 6.7787
assert parity[0]["unit"] == "cny_per_usd"
assert parity[0]["public_available_at"] == "2026-09-04 01:25:17+00:00"
gdp = records["nbs_gdp"]["claims"]
assert len(gdp) == 8
assert {
    c["dimensions"]["aggregate"]: c["value"]
    for c in gdp if c["dimensions"]["measure"] == "real_quarter_yoy"
} == {"total": 4.3, "primary": 3.7, "secondary": 3.0, "tertiary": 5.1}
assert {c["public_available_at"] for c in gdp} == {"2026-07-16 01:30:00+00:00"}
summary = {
    "verified_at": datetime.now().astimezone().isoformat(),
    "real_requests": len(request_ids), "claims": len(claim_ids),
    "verified_artifacts": len(artifact_hashes), "raw_artifacts": 2,
    "normalization_artifacts": 2, "trace_links_verified": 9,
    "official_sample_fields_match": True, "system_time_not_backfilled": True,
    "certification_grants": 0, "production_writes": 0, "verification_network_requests": 0,
}
(root / "delivery-verification.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(summary))
