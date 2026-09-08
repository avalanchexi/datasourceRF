"""Read-only forensics of the failed full-03 fixture, without application imports."""

import json
import hashlib
import shutil
import sqlite3
from pathlib import Path

database = Path(
    "/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908/full-03/"
    "test_p2_tushare_failure_or_mis1/runtime/data/pring-cycle.sqlite3"
)
assert database.is_file()
# A read-only mounted WAL database may need a new shared-memory file. Copy its
# closed, immutable fixture files to a fresh writable temporary directory first.
snapshot = Path("/dev/shm/pring-cycle-full03-forensics-20260908")
snapshot.mkdir(mode=0o700)
identities = []
for suffix in ("", "-wal", "-shm"):
    source = Path(str(database) + suffix)
    if source.is_file():
        destination = snapshot / source.name
        shutil.copyfile(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
        identities.append({"file": source.name, "bytes": source.stat().st_size,
                           "sha256": digest})
copy = snapshot / database.name
with sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    run = connection.execute(
        "SELECT run_id,status,error_classification,projection_set_id,system_as_of "
        "FROM parent_run"
    ).fetchall()
    acquisitions = connection.execute(
        "SELECT provider,api_name,state,error_type,started_at,received_at,validated_at "
        "FROM acquisition_request ORDER BY started_at"
    ).fetchall()
    print(json.dumps({"original_fixture_files": identities,
                      "run": [dict(row) for row in run],
                      "acquisitions": [dict(row) for row in acquisitions]}, indent=2))
