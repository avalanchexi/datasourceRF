"""Read-only installed/source identity check; run with the project's WSL Python."""
from __future__ import annotations

import hashlib
import json
import sysconfig
from pathlib import Path

root = Path.cwd()
source = root / "src" / "pring_cycle"
installed = Path(sysconfig.get_paths()["purelib"]) / "pring_cycle"
source_paths = {path.relative_to(source) for path in source.rglob("*.py")}
installed_paths = {path.relative_to(installed) for path in installed.rglob("*.py")}
assert source_paths == installed_paths, (source_paths - installed_paths, installed_paths - source_paths)
files = []
for relative in sorted(source_paths):
    content = (source / relative).read_bytes().replace(b"\r\n", b"\n")
    assert content == (installed / relative).read_bytes().replace(b"\r\n", b"\n"), relative
    files.append({"path": f"src/pring_cycle/{relative.as_posix()}", "lf_sha256": hashlib.sha256(content).hexdigest()})
print(json.dumps({"scope": "all Python source; user-owned assets excluded", "installed_package": str(installed), "matched_source_files": len(files), "files": files}, indent=2))
