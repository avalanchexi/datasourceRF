"""Independent stdlib verification of terminal acquisition preparation."""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

folder = Path(".scratch/pring-data-acquisition-repair/evidence-lpr-import-20260908")
document = json.loads((folder / "receipts.json").read_bytes())
assert document["status"] == "completed_acquisition_preparation"
assert len(document["receipts"]) == 9
database = Path(document["database"])
assert database == Path("/home/tywin/.cache/pring-cycle/verification/lpr-document-import-20260908/data/pring-cycle.sqlite3")
digests = set()
raw_bytes = 0
with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    assert connection.execute("SELECT COUNT(*) FROM source_claim").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM registered_metric_catalog").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM acquisition_request").fetchone()[0] == 9
    for item in document["receipts"]:
        receipt = item["receipt"]
        row = connection.execute("SELECT * FROM acquisition_request WHERE acquisition_id=?",
                                 (receipt["acquisition_id"],)).fetchone()
        assert row is not None
        for field in ("provider", "api_name", "fields", "parser_version", "state", "raw_hash", "normalized_hash"):
            assert row[field] == receipt[field]
        assert json.loads(row["parameters_json"]) == receipt["parameters"]
        clocks = [datetime.fromisoformat(receipt[field]) for field in ("started_at", "received_at", "validated_at")]
        assert clocks == sorted(clocks) and clocks[0] >= datetime.fromisoformat(document["started_at"])
        for field in ("started_at", "received_at", "validated_at"):
            assert datetime.fromisoformat(row[field]) == datetime.fromisoformat(receipt[field])
        raw = (folder / receipt["raw_hash"]).read_bytes()
        raw_bytes += len(raw)
        assert raw == Path(receipt["parameters"]["imported_from"]).read_bytes()
        normalized = (folder / receipt["normalized_hash"]).read_bytes()
        assert json.loads(normalized) == item["parsed_unreviewed_release"]
        observations = item["parsed_unreviewed_release"]["observations"]
        assert {part["tenor"]: part["value"] for part in observations} == {"1y": 3.0, "5y_plus": 3.5}
        for field in ("raw_hash", "normalized_hash"):
            digest = receipt[field]
            content = (folder / digest).read_bytes()
            assert hashlib.sha256(content).hexdigest() == digest
            digests.add(digest)
assert raw_bytes == 92717 and len(digests) == 18
result = {"validated_imports": 9, "literal_values": 18, "raw_bytes": raw_bytes,
          "verified_exported_artifacts": 18, "source_claims": 0, "registered_catalogs": 0,
          "receipt_bytes": (folder / "receipts.json").stat().st_size,
          "receipt_sha256": hashlib.sha256((folder / "receipts.json").read_bytes()).hexdigest(),
          "network_requests": 0, "read_only_verification": True}
Path(__file__).with_name("lpr-import-verification.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
print(json.dumps(result))
