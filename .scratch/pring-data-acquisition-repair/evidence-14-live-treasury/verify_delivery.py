"""Verify exported candidate evidence without network, app imports or database writes."""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
report = json.loads((root / "result.json").read_text(encoding="utf-8"))
expected = {
    "2026-08-24": (4.24, 4.70), "2026-08-25": (4.17, 4.64),
    "2026-08-26": (4.19, 4.66), "2026-08-27": (4.20, 4.67),
    "2026-08-28": (4.34, 4.73), "2026-08-31": (4.34, 4.75),
    "2026-09-01": (4.39, 4.79), "2026-09-02": (4.39, 4.79),
    "2026-09-03": (4.34, 4.77), "2026-09-04": (4.37, 4.78),
}
endpoint = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve"
    "&field_tdr_date_value=2026&page&_format=csv"
)
assert "error" not in report and len(report["receipts"]) == 1
assert report["result"]["status"] == "stored_candidate"
assert report["result"]["observation_count"] == 20 and report["result"]["missing_cell_count"] == 0
receipt = report["receipts"][0]
assert receipt["acquisition_id"] == report["result"]["acquisition_id"]
assert receipt["raw_hash"] == "a14a321adffded36dfd9ab1aec72cc81423aeca271110f76569d37dd02ca4ee5"
artifacts = {}
for key in ("raw_hash", "normalized_hash"):
    digest = receipt[key]
    content = (root / digest).read_bytes()
    assert hashlib.sha256(content).hexdigest() == digest
    artifacts[digest] = len(content)
assert datetime.fromisoformat(receipt["validated_at"]) >= datetime.fromisoformat(receipt["received_at"]) >= datetime.fromisoformat(receipt["started_at"])
research_receipts = json.loads((root.parent / "evidence-14-treasury-followup/receipts.json").read_text(encoding="utf-8"))
research_csv = next(item for item in research_receipts if item["sha256"] == receipt["raw_hash"])
assert datetime.fromisoformat(receipt["started_at"]) > datetime.fromisoformat(research_csv["received_at"])
batch = json.loads((root / receipt["normalized_hash"]).read_text(encoding="utf-8"))
assert batch["source_year"] == 2026 and batch["total_source_rows"] == 171
assert batch["endpoint"] == endpoint and batch["unit"] == "percent"
assert batch["source_timezone"] == "America/New_York"
assert batch["http_response"]["response_final_url"] == endpoint
assert batch["http_response"]["response_http_status"] == "200"
claim_ids = set()
observation_ids = set()
for index, metric in enumerate(("UST2Y_NOMINAL_YIELD", "UST10Y_NOMINAL_YIELD")):
    reference = {period: values[index] for period, values in expected.items()}
    assert batch["latest_reported_periods"][metric] == "2026-09-04"
    cells = [cell for cell in batch["cells"] if cell["metric_id"] == metric]
    assert len(cells) == 10 and all(cell["state"] == "reported_value" for cell in cells)
    assert {cell["business_date"]: cell["value"] for cell in cells} == reference
    exported = report["metrics"][metric]
    assert exported["public_points"] == 0 and len(exported["traces"]) == 10
    actual = {}
    for trace in exported["traces"]:
        assert trace["period_start"] == trace["period_end"]
        assert trace["acquisition_status"] == "linked" and len(trace["claims"]) == 1
        assert {item["acquisition_id"] for item in trace["acquisitions"]} == {receipt["acquisition_id"]}
        claim = trace["claims"][0]
        actual[trace["period_end"]] = claim["value"]
        assert claim["unit"] == "percent"
        assert claim["certification_status"] == "awaiting_source_certification"
        assert claim["public_available_at"] is None and claim["release_at"] is None
        assert claim["fetched_at"] == receipt["received_at"]
        assert datetime.fromisoformat(claim["available_at"]) >= datetime.fromisoformat(receipt["validated_at"])
        assert claim["source_reference"] == endpoint + "#date=" + trace["period_end"]
        claim_ids.add(claim["claim_id"])
        observation_ids.add(trace["observation_id"])
    assert actual == reference
    attempt = exported["latest_attempt"]
    assert attempt["outcome"] == "verified_candidate"
    assert attempt["safe_metadata"]["acquisition_ids"] == receipt["acquisition_id"]
    assert attempt["safe_metadata"]["latest_source_period"] == "2026-09-04"
    assert attempt["safe_metadata"]["observations"] == "10"
assert len(claim_ids) == len(observation_ids) == 20
for key in ("source_certification_grants", "model_adoptions", "model_activations", "production_writes", "api_keys_used"):
    assert report[key] == 0
summary = {"validation": "passed", "real_cli_commands": 1, "real_http_requests": 1,
           "source_days": 10, "candidate_claims": 20, "trace_links_verified": 20,
           "missing_calendar_cells": 0, "artifacts": artifacts,
           "reference_values_match": True, "unknown_public_time_preserved": True,
           "system_time_not_backfilled": True, "source_certification_grants": 0,
           "model_adoptions": 0, "production_writes": 0,
           "verification_network_requests": 0,
           "result_sha256": hashlib.sha256((root / "result.json").read_bytes()).hexdigest()}
destination = root / "delivery-verification.json"
if sys.argv[1:] == ["--write-manifest"]:
    destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
else:
    assert not sys.argv[1:]
    assert summary == json.loads(destination.read_text(encoding="utf-8"))
print(json.dumps(summary, indent=2))
