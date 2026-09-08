"""Independently verify actual CPI acquisition receipts, read-only and stdlib-only."""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

folder = Path(".scratch/pring-data-acquisition-repair/evidence-cpi-import-20260908")
document = json.loads((folder / "receipts.json").read_bytes())
assert document["status"] == "completed_acquisition_preparation"
assert len(document["receipts"]) == 9 and document["network_attempts"] == 1
database = Path(document["database"])
assert database == Path("/home/tywin/.cache/pring-cycle/verification/cpi-document-import-20260908/data/pring-cycle.sqlite3")
hashes = set()
scalars = 0
with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    assert connection.execute("SELECT COUNT(*) FROM source_claim").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM registered_metric_catalog").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM acquisition_request").fetchone()[0] == 9
    for item in document["receipts"]:
        receipt = item["receipt"]
        row = connection.execute("SELECT * FROM acquisition_request WHERE acquisition_id=?", (receipt["acquisition_id"],)).fetchone()
        assert row is not None
        for key in ("provider", "api_name", "state", "raw_hash", "normalized_hash", "parser_version", "fields"):
            assert row[key] == receipt[key]
        assert json.loads(row["parameters_json"]) == receipt["parameters"]
        times = [datetime.fromisoformat(receipt[key]) for key in ("started_at", "received_at", "validated_at")]
        assert times == sorted(times) and times[0] >= datetime.fromisoformat(document["started_at"])
        for key in ("started_at", "received_at", "validated_at"):
            assert datetime.fromisoformat(row[key]) == datetime.fromisoformat(receipt[key])
        for kind in ("raw", "normalized"):
            digest = receipt[kind + "_hash"]
            assert hashlib.sha256((folder / digest).read_bytes()).hexdigest() == digest
            assert connection.execute("SELECT 1 FROM artifact_reference WHERE content_hash=? AND source_reference=?", (digest, receipt["acquisition_id"] + ":" + kind)).fetchone() is not None
            hashes.add(digest)
        normalized = json.loads((folder / receipt["normalized_hash"]).read_bytes())
        assert normalized == item["normalized_unreviewed"]
        if receipt["api_name"] == "document_import":
            assert (folder / receipt["raw_hash"]).read_bytes() == Path(receipt["parameters"]["imported_from"]).read_bytes()
            assert len(normalized["scalars"]) == (4 if normalized["period"] == "2026-01" else 6)
            assert {part["unit"] for part in normalized["scalars"]} == {"percent"}
            scalars += len(normalized["scalars"])
        else:
            assert receipt["api_name"] == "official_http_get"
            assert normalized["http"] == {"status": 200, "final_url": "https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html", "media_type": "text/html"}
            assert receipt["raw_hash"] == "fcb330d080046d9700e53c9a6416b3a97ca52a5cea770e7d467c2ea98589b5fe"
            assert (folder / receipt["raw_hash"]).stat().st_size == 127670
assert scalars == 46 and len(hashes) == 18
print(json.dumps({"validated_receipts": 9, "cpi_documents": 8, "scalars": scalars,
                  "terms_http_status": 200, "verified_artifacts": len(hashes), "source_claims": 0,
                  "receipt_bytes": (folder / "receipts.json").stat().st_size,
                  "receipt_sha256": hashlib.sha256((folder / "receipts.json").read_bytes()).hexdigest()}))
