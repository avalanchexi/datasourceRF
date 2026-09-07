"""One-time real document imports into a fresh isolated WSL acquisition store.

Creates acquisition receipts only. Does not create source claims, certify any
source, backdate system availability, activate models, or call the network.
"""
import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from pring_cycle.acquisition import AcquisitionRepository
from pring_cycle.official_lpr import CHINAMONEY_PROVIDER, parse_lpr_announcement
from pring_cycle.runtime import RuntimePaths, initialize_runtime
from pring_cycle.runtime_fingerprint import execution_fingerprint

arguments = argparse.ArgumentParser()
arguments.add_argument("--execute", action="store_true", required=True)
arguments.parse_args()
assert sys.platform == "linux" and sys.version_info[:2] == (3, 12)
root = Path.cwd()
repair = root / ".scratch/pring-data-acquisition-repair"
report = repair / "lpr-certification-gap-matrix.md"
report_bytes = report.read_bytes()
assert hashlib.sha256(report_bytes).hexdigest() == "b132c53abeb9a6653de37b84cd6001877a58a2cdfa7d893c5d7ee43341bd8c21"
inputs = re.findall(
    r"^\| (\d{4}-\d{2}) \| \[该期官方公告\]\((https://[^)]+)\).*?"
    r"\[原件\]\(([^)]+)\)；(\d+)；`([0-9a-f]{64})`", report_bytes.decode(), re.M,
)
assert len(inputs) == 9
runtime = Path("/home/tywin/.cache/pring-cycle/verification/lpr-document-import-20260908")
output = repair / "evidence-lpr-import-20260908"
assert not runtime.exists() and not output.exists(), "one_time_import_already_started"
paths = RuntimePaths.discover(runtime)
initialize_runtime(paths)
output.mkdir()
repository = AcquisitionRepository(paths.database, paths.artifacts)
document = {
    "status": "running", "runtime": str(runtime), "database": str(paths.database),
    "started_at": datetime.now(UTC).isoformat(), "execution_fingerprint": execution_fingerprint(paths),
    "operation": "document_import_of_existing_originals", "network_requests": 0,
    "source_claims_created": 0, "source_certification_grants": 0,
    "historical_system_availability_restored": False, "historical_public_certified": False,
    "real_candidate_models_created": 0, "activations": 0, "production_writes": 0,
    "receipts": [],
}
try:
    for period, url, target, expected_bytes, expected_hash in inputs:
        value = target.split("#", 1)[0]
        prefix = "//wsl.localhost/Ubuntu-22.04"
        source = Path(value[len(prefix):]) if value.startswith(prefix + "/") else repair / value
        raw = source.read_bytes()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == (int(expected_bytes), expected_hash)

        def parse(content: bytes):
            parsed = parse_lpr_announcement(
                content, source_url=url, fetched_at=datetime.now(UTC), expected_period=period,
            )
            assert {item.tenor: item.value for item in parsed.observations} == {"1y": 3.0, "5y_plus": 3.5}
            return parsed

        acquired = repository.capture(
            provider=CHINAMONEY_PROVIDER, api_name="document_import",
            parameters={"source_url": url, "period": period, "imported_from": str(source)},
            fields="1y,5y_plus", parser_version="chinamoney-lpr-parser-v0002",
            fetch=source.read_bytes, parse=parse, normalize=asdict,
        )
        receipt = repository.get(acquired.receipt.acquisition_id)
        assert receipt.state == "validated" and receipt.raw_hash == expected_hash
        assert receipt.received_at and receipt.validated_at
        assert receipt.started_at <= receipt.received_at <= receipt.validated_at
        for digest in (receipt.raw_hash, receipt.normalized_hash):
            assert digest is not None
            content = (paths.artifacts / digest[:2] / digest).read_bytes()
            assert hashlib.sha256(content).hexdigest() == digest
            destination = output / digest
            if destination.exists():
                assert destination.read_bytes() == content
            else:
                destination.write_bytes(content)
        document["receipts"].append({"receipt": asdict(receipt), "parsed_unreviewed_release": asdict(acquired.value)})
    document["status"] = "completed_acquisition_preparation"
    document["literal_values_verified"] = 18
    document["completed_at"] = datetime.now(UTC).isoformat()
finally:
    (output / "receipts.json").write_bytes(
        (json.dumps(document, ensure_ascii=False, indent=2, default=str) + "\n").encode()
    )
print(json.dumps({"status": document["status"], "validated_imports": len(document["receipts"]),
                  "literal_values_verified": 18, "network_requests": 0, "source_claims_created": 0}))
