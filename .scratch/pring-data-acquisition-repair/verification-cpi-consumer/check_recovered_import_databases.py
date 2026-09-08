"""Read-only integrity checks for this task's two actual acquisition databases."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
results = []
for family, expected in (("cpi", 9), ("lpr", 9)):
    document = json.loads(
        (root / f"evidence-{family}-import-20260908" / "receipts.json").read_bytes()
    )
    database = Path(document["database"])
    assert database == Path(
        f"/home/tywin/.cache/pring-cycle/verification/{family}-document-import-20260908"
        "/data/pring-cycle.sqlite3"
    )
    assert database.is_file()
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchall()
        assert integrity == [("ok",)], (family, integrity)
        count = connection.execute("SELECT COUNT(*) FROM acquisition_request").fetchone()[0]
        assert count == expected
        assert connection.execute("SELECT COUNT(*) FROM source_claim").fetchone()[0] == 0
        for item in document["receipts"]:
            receipt = item["receipt"]
            for kind in ("raw", "normalized"):
                digest = receipt[kind + "_hash"]
                artifact = database.parent / "artifacts" / "sha256" / digest[:2] / digest
                assert hashlib.sha256(artifact.read_bytes()).hexdigest() == digest
    results.append({"family": family, "database": str(database), "quick_check": "ok",
                    "requests": count, "artifact_hashes_checked": expected * 2})
print(json.dumps({"checked_at": datetime.now(UTC).isoformat(), "read_only": True,
                  "results": results}, indent=2))
