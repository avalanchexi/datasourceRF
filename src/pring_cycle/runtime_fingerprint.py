from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from pring_cycle.models import ModelRepository
from pring_cycle.runtime import RuntimePaths


def execution_fingerprint(
    paths: RuntimePaths,
    *,
    model_version_id: str | None = None,
) -> dict[str, Any]:
    package_root = Path(__file__).parent
    project_root = _project_root(package_root)
    dependency_file = project_root / "uv.lock"
    document: dict[str, Any] = {
        "code_hash": _tree_hash(package_root, ("*.py", "*.css", "*.js")),
        "configuration_version": "config-v0001",
        "database_revision": _database_revision(paths.database),
        "dependency_hash": (
            _file_hash(dependency_file) if dependency_file.is_file() else None
        ),
    }
    if model_version_id is not None:
        model = ModelRepository(paths.database).get(model_version_id)
        document.update(
            {
                "model_manifest_hash": model.manifest_hash,
                "model_version_id": model_version_id,
            }
        )
    return document


def model_manifest_hashes(paths: RuntimePaths) -> dict[str, str]:
    models = ModelRepository(paths.database)
    return {
        model.model_version_id: model.manifest_hash
        for model in models.list_versions()
    }


def fingerprint_matches(
    document: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    return all(document.get(key) == value for key, value in expected.items())


def _tree_hash(root: Path, patterns: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        {
            path
            for pattern in patterns
            for path in root.rglob(pattern)
            if path.is_file()
        }
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _project_root(package_root: Path) -> Path:
    candidates = (
        Path.cwd().resolve(),
        *Path.cwd().resolve().parents,
        *package_root.parents,
    )
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (candidate / "uv.lock").is_file():
            return candidate
    return package_root.parents[1]


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _database_revision(database: Path) -> str | None:
    if not database.is_file():
        return None
    try:
        with sqlite3.connect(database) as connection:
            row = connection.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
    except sqlite3.DatabaseError:
        return None
    return str(row[0]) if row is not None else None
