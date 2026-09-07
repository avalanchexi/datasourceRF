"""Read-only byte checks of this batch's Git index before committing."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[2]


def index_bytes(path):
    return subprocess.run(
        ["git", "show", ":" + path], cwd=root, check=True, capture_output=True
    ).stdout


fingerprint = json.loads((folder / "code-fingerprint.json").read_text(encoding="utf-8"))
for row in fingerprint["files"]:
    data = index_bytes(row["path"]).replace(b"\r\n", b"\n")
    assert hashlib.sha256(data).hexdigest() == row["lf_sha256"], row["path"]
changed = subprocess.run(
    ["git", "diff", "--cached", "--name-only", "-z"],
    cwd=root, check=True, capture_output=True,
).stdout.decode().rstrip("\0").split("\0")
allowed = json.loads((folder / "staging-paths.json").read_text(encoding="utf-8"))
assert sorted(changed) == sorted(allowed), "staged paths differ from batch ownership list"
raw_count = 0
for path in changed:
    if re.fullmatch(r"[0-9a-f]{64}", Path(path).name):
        assert hashlib.sha256(index_bytes(path)).hexdigest() == Path(path).name, path
        raw_count += 1
for evidence in ("evidence-14-vix-followup", "evidence-13-dr007-followup"):
    manifest = json.loads((folder.parent / evidence / "delivery-verification.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = index_bytes(entry["path"])
        assert len(data) == entry["bytes"], entry["path"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
live = folder.parent / "evidence-14-live-treasury"
verification = json.loads((live / "delivery-verification.json").read_text(encoding="utf-8"))
result_path = (live / "result.json").relative_to(root).as_posix()
assert hashlib.sha256(index_bytes(result_path)).hexdigest() == verification["result_sha256"]
for name, size in verification["artifacts"].items():
    data = index_bytes((live / name).relative_to(root).as_posix())
    assert len(data) == size and hashlib.sha256(data).hexdigest() == name
print(json.dumps({"validation": "passed", "source_files": len(fingerprint["files"]),
                  "owned_staged_files": len(changed), "hash_named_artifacts": raw_count,
                  "research_manifests": 2, "live_claims": verification["candidate_claims"]}))
