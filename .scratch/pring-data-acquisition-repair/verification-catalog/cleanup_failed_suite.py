"""Remove only this task's finished failed pytest basetemp, retaining its failed case."""
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd().resolve()
assert root == Path("/mnt/d/cursor/datasourceRF")
target = Path("/home/tywin/.cache/pring-cycle/verification/catalog-full-final")
assert not target.is_symlink() and target.resolve() == target
assert target.parent == Path("/home/tywin/.cache/pring-cycle/verification")
log = root / ".scratch/pring-data-acquisition-repair/verification-catalog-full-final.txt"
raw = log.read_bytes()
text = raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8-sig")
assert "2 failed, 817 passed" in text
assert "FAILED tests/integration/test_core_history_refresh.py::test_new_acquisition_preserves_old_release_and_claim_bytes" in text
for process in Path("/proc").iterdir():
    if not process.name.isdigit() or int(process.name) == os.getpid():
        continue
    try:
        arguments = (process / "cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        continue
    assert f"--basetemp={target}".encode() not in arguments, "suite_is_still_running"
failed = [path for pattern in ("test_new_acquisition_preserv*", "test_context_selection_combin*")
          for path in target.glob(pattern) if path.is_dir() and not path.is_symlink()]
assert len(failed) == 2, failed
archive = root / ".tmp/catalog-failed-full-01"
assert not archive.exists()
archive.mkdir()
for path in failed:
    shutil.copytree(path, archive / path.name, symlinks=True)
files = [path for path in target.rglob("*") if path.is_file() and not path.is_symlink()]
receipt = {"target": str(target), "owned_by": "catalog-full-final pytest --basetemp command",
           "terminal_result": "2 failed, 817 passed", "active_use": False,
           "file_count": len(files), "bytes": sum(path.stat().st_size for path in files),
           "retained_failed_case": str(archive), "time": datetime.now(UTC).isoformat()}
shutil.rmtree(target)
assert not target.exists()
receipt["removed"] = True
Path(__file__).with_name("failed-suite-cleanup.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
print(json.dumps(receipt))
