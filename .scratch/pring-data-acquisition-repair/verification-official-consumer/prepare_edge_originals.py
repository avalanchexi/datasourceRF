"""Copy five previously audited originals without claiming a new source acquisition."""
import hashlib
import json
from pathlib import Path

digests = (
    "e7e65eb8ae0656afae92ab36bcb8a6c261be5af0422352fadbecf45c4a0e2943",
    "2115d7cc67a22dd15a88c93101be752711a72e7f41534b01b1e8f7528f341f8e",
    "377f455aa92273c23d57540d2b33e5b4b99f01e6ebfa7beacae157c21c5632cc",
    "632b1709e4c27aac9b2fd9135394f11efb530321c8a1960577f8a0a562ec65b0",
    "0c66284a8d0420a6168c432e87e7e4ee31bf4002896634e5253780d928cdb02a",
)
source = Path("//wsl.localhost/Ubuntu-22.04/home/tywin/.local/share/pring-cycle/artifacts/sha256")
destination = Path(__file__).resolve().parents[1] / "evidence-official-consumer-edge"
destination.mkdir(exist_ok=False)
records = []
for digest in digests:
    original = source / digest[:2] / digest
    data = original.read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    output = destination / digest
    with output.open("xb") as stream:
        stream.write(data)
    assert output.read_bytes() == data
    records.append({"source": str(original), "sha256": digest, "bytes": len(data)})
receipt = {"operation": "local_copy_of_previously_audited_originals", "network_requests": 0,
           "acquisitions": 0, "records": records}
(destination / "copy-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"copied": len(records), "bytes": sum(r["bytes"] for r in records)}))
