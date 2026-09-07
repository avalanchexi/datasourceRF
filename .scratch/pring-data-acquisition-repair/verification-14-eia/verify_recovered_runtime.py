"""Verify the recovered installed source and the two isolated candidate stores."""

import hashlib
import importlib.util
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

destination = Path(__file__).resolve().parent
repair = destination.parent
repository = repair.parents[1]
manifest = json.loads((destination / "code-fingerprint.json").read_text(encoding="utf-8"))
spec = importlib.util.find_spec("pring_cycle")
assert spec is not None and spec.origin is not None
installed = Path(spec.origin).resolve().parent
assert not installed.is_relative_to(repository)
assert {p.relative_to(installed).as_posix() for p in installed.rglob("*.py")} == {
    str(Path(item["path"]).relative_to("src/pring_cycle")) for item in manifest["files"]
}
for item in manifest["files"]:
    relative = Path(item["path"]).relative_to("src/pring_cycle")
    for path in (repository / item["path"], installed / relative):
        content = path.read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == item["lf_sha256"], str(path)

stores = []
for folder in ("evidence-14-live-eia", "evidence-14-live-official"):
    evidence = repair / folder
    report = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
    runtime = Path(report["runtime"])
    database = runtime / "data/pring-cycle.sqlite3"
    assert database.is_file()
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        checks = [row[0] for row in connection.execute("PRAGMA quick_check")]
        assert checks == ["ok"], checks
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
    finally:
        connection.close()
    artifacts = []
    for export in evidence.iterdir():
        if len(export.name) != 64 or any(c not in "0123456789abcdef" for c in export.name):
            continue
        stored = runtime / "data/artifacts/sha256" / export.name[:2] / export.name
        content = stored.read_bytes()
        assert hashlib.sha256(content).hexdigest() == export.name
        assert content == export.read_bytes()
        artifacts.append({"sha256": export.name, "bytes": len(content)})
    assert len(artifacts) == 4
    stores.append({"runtime": str(runtime), "sqlite_quick_check": checks,
                   "foreign_key_check": "passed", "artifacts": artifacts})

probe_root = Path("/home/tywin/.cache/pring-cycle/verification/repair-14-eia-recovery-probe-20260907a")
probe_root.mkdir(exist_ok=False)
probe = probe_root / "write-probe.txt"
with probe.open("xb") as output:
    output.write(b"WSL native filesystem write verified\n")
    output.flush()
    os.fsync(output.fileno())
assert probe.read_bytes() == b"WSL native filesystem write verified\n"
result = {"verified_at": datetime.now(timezone.utc).isoformat(),
          "installed_package": str(installed), "matched_source_files": len(manifest["files"]),
          "native_write_probe": str(probe), "candidate_stores": stores,
          "network_requests": 0, "candidate_database_writes": 0,
          "production_database_access": False}
(destination / "recovered-runtime.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"matched_source_files": len(manifest["files"]), "verified_candidate_stores": len(stores),
                  "verified_native_artifacts": sum(len(s["artifacts"]) for s in stores),
                  "native_write_probe": "passed"}, indent=2))
