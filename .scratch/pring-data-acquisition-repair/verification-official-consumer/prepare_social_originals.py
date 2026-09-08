"""Preserve two audited separate PBC announcements as local test inputs."""
import hashlib
import json
from pathlib import Path

source = Path("//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256")
destination = Path(__file__).resolve().parents[1] / "evidence-official-consumer-social"
destination.mkdir(exist_ok=False)
records = []
for digest in ("42312d6054e2df029dfeeba68c7c60fc4bc45934cb72bdd739c143e1c9f02243",
               "d0ae83ced9ad510a057a853f51b185e729ed81c9cd5e958fa988c7b10a676d9d"):
    original = source / digest[:2] / digest
    data = original.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    with (destination / digest).open("xb") as stream:
        stream.write(data)
    assert (destination / digest).read_bytes() == data
    records.append({"source": str(original), "sha256": digest, "bytes": len(data)})
(destination / "copy-receipt.json").write_text(
    json.dumps({"operation": "local_copy_of_previously_audited_originals", "network_requests": 0,
                "acquisitions": 0, "records": records}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"copied": len(records), "bytes": sum(r["bytes"] for r in records)}))
