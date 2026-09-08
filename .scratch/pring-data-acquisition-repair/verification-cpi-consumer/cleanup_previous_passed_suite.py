"""Release only the prior, terminal 819-pass pytest runtime; keep its logs."""
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

root = Path.cwd().resolve()
assert root == Path("/mnt/d/cursor/datasourceRF")
target = Path("/home/tywin/.cache/pring-cycle/verification/catalog-full-final-02")
assert not target.is_symlink() and target.resolve() == target and target.is_dir()
assert target.parent == Path("/home/tywin/.cache/pring-cycle/verification")
log = root / ".scratch/pring-data-acquisition-repair/verification-catalog-full-final-02.txt"
assert "819 passed" in log.read_text(encoding="utf-8")
for process in Path("/proc").iterdir():
    if not process.name.isdigit() or int(process.name) == os.getpid():
        continue
    try:
        arguments = (process / "cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        continue
    assert not any(str(target).encode() in argument for argument in arguments), "active_use"
files = [path for path in target.rglob("*") if path.is_file() and not path.is_symlink()]
receipt = {
    "target": str(target), "owner": "terminal catalog-full-final-02 pytest --basetemp",
    "terminal_result": "819 passed", "process_cmdline_target_matches": 0,
    "fd_and_cwd_scan_performed": False,
    "bytes": sum(path.stat().st_size for path in files), "file_count": len(files),
    "retained_log": str(log), "cleaned_at": datetime.now(UTC).isoformat(),
}
shutil.rmtree(target)
assert not target.exists()
Path(__file__).with_name("previous-suite-cleanup.json").write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
)
print(json.dumps(receipt))
