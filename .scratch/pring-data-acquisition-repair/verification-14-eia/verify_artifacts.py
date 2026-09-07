"""Record the tested installed Python source identity without importing project modules."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


def main() -> None:
    destination = Path(__file__).resolve().parent
    repository = destination.parents[2]
    source = repository / "src" / "pring_cycle"
    spec = importlib.util.find_spec("pring_cycle")
    if spec is None or spec.origin is None:
        raise RuntimeError("Installed pring_cycle package is unavailable")
    installed = Path(spec.origin).resolve().parent
    if installed == source:
        raise RuntimeError("Verification must use the installed non-editable package")
    source_paths = {path.relative_to(source) for path in source.rglob("*.py")}
    installed_paths = {path.relative_to(installed) for path in installed.rglob("*.py")}
    if source_paths != installed_paths:
        raise RuntimeError("Installed Python file inventory differs from workspace")
    records = []
    for path in sorted(source.rglob("*.py")):
        relative = path.relative_to(source)
        workspace_bytes = path.read_bytes().replace(b"\r\n", b"\n")
        installed_bytes = (installed / relative).read_bytes().replace(b"\r\n", b"\n")
        if installed_bytes != workspace_bytes:
            raise RuntimeError(f"Installed source differs: {relative}")
        records.append(
            {
                "path": path.relative_to(repository).as_posix(),
                "lf_sha256": hashlib.sha256(workspace_bytes).hexdigest(),
            }
        )
    result = {
        "scope": "all Python source; assets are excluded",
        "comparison": "exact bytes after CRLF to LF normalization",
        "installed_package": str(installed),
        "matched_source_files": len(records),
        "files": records,
    }
    (destination / "code-fingerprint.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Installed Python source matches workspace: {len(records)} files")


if __name__ == "__main__":
    main()
