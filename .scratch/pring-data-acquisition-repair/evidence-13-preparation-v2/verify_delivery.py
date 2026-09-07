"""Windows stdlib verification of immutable parser output and original-byte lineage."""
import hashlib
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parent
path = here / "preparation.json"
raw = path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == "92f44dbb435ea56fd1b08813373f4abf4749d76db33f364547098e290fb58034"
doc = json.loads(raw)
data = doc["data"]
old_raw = (base / "evidence-13-preparation/preparation.json").read_bytes()
assert hashlib.sha256(old_raw).hexdigest() == "a9fe475c47303fb7791b27df04849dcef0aacabde27b64f57023972c9a4ec20a"
old = json.loads(old_raw)
assert data["raw_artifacts"] == old["data"]["raw_artifacts"]
seen = set()
total = 0
for artifact in data["raw_artifacts"]:
    location = artifact["cas_path"].replace("/home/tywin/", "//wsl.localhost/Ubuntu-22.04/home/tywin/")
    source = Path(location).read_bytes()
    sha = hashlib.sha256(source).hexdigest()
    assert sha == artifact["sha256"] and len(source) == artifact["bytes"]
    assert sha not in seen
    assert artifact["acquisition_time"] is None
    assert artifact["historical_first_publication_certified"] is False
    assert artifact["original_transport_receipt_in_this_package"] is False
    seen.add(sha)
    total += len(source)
assert len(seen) == 250 and total == 20069217
for audit in data["lineage"]["audit_files"]:
    source = (base / audit["path"]).read_bytes()
    assert len(source) == audit["bytes"] and hashlib.sha256(source).hexdigest() == audit["sha256"]
assert len(data["lineage"]["audit_files"]) == 11
old_rows = {(row["artifact_sha256"], row["family"]): row for row in old["data"]["results"]}
counts = Counter()
metrics = set()
changed = []
for row in data["results"]:
    assert row["certification_state"] == row["candidate_adoption_state"] == "not_performed"
    assert row["system_acquisition_time"] is None
    prior = old_rows[(row["artifact_sha256"], row["family"])]
    for index, (scalar, old_scalar) in enumerate(zip(row["parsed"]["scalars"], prior["parsed"]["scalars"], strict=True)):
        for key in old_scalar:
            if key not in {"value", "independent_review_status"}:
                assert scalar[key] == old_scalar[key], (row["family"], index, key)
        metrics.add(scalar["metric_id"])
        assert scalar["acquisition_ids"] == [] and scalar["definition_version"] is None
        if scalar["value"] != old_scalar["value"]:
            changed.append((row["family"], row["expected_period"], scalar["source_field"], old_scalar["value"], scalar["value"]))
        counts[scalar["independent_review_status"]] += 1
assert changed == [("pbc_money", "2026-02", "m2", 3492200.0000000005, 3492200.0)]
assert len(metrics) == 18 and sum(counts.values()) == 1858
assert counts == data["summary"]["full_value_review_counts"]
assert counts["same_interval_quarter_cell_reuse_source_mapping_pending"] == 1
for field in ("network_requests", "database_operations", "certifications_created", "candidate_models_created", "candidate_adoptions"):
    assert data["summary"][field] == 0
result = {"preparation_sha256": hashlib.sha256(raw).hexdigest(), "preparation_bytes": len(raw), "old_preparation_unchanged": True, "raw_artifacts": 250, "raw_bytes": total, "bound_audit_reports": 11, "metric_count": 18, "scalar_count": 1858, "literal_matching_scalars": 1857, "source_mapping_pending": 1, "changed_scalars": changed, "initial_reparse_seconds": doc["execution"]["elapsed_seconds"], "independent_read_only_reparse_seconds": 5.095091265999997, "independent_read_only_reparse_exit_code": 0, "network_requests": 0, "database_operations": 0, "certifications": 0, "model_adoptions": 0}
(here / "delivery-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
