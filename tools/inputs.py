"""The software inputs a verification receipt pins; materials are pinned separately.

A receipt has to name what it is a receipt *for*, and two different things bind it.
The software half is the code, its tests, the tools that run them, and what the
build declares it reads. The material half is what a run actually reads, which
``material_identity`` in tests/models/test_isolated_lifecycle.py already pins by
builder and content.

Hashing the whole tree conflates the two. ``.scratch/`` carries both the materials
some runs read and the notes every run writes, so a note written after a run makes
the software look changed and forces the next batch to rerun what it could have
reused; the frozen copy then also carries the evidence, which cannot change what
the software does. Pinning the software half here drops no binding: a material
that changes still invalidates the material receipt, which is the receipt that
names it.

The source tree is only half of what ran. ``pring_cycle`` is installed into the
development venv as a built copy, not an editable link, so an interpreter started
without ``src`` on its path imports that copy instead of the tree this inventory
describes. A receipt that will be reused must therefore also record
``imported_package``: what the interpreter resolved.
"""

from __future__ import annotations

import hashlib
import importlib
import tomllib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

# Everything the installed package, its tests, and the tools that run them are built from.
SOFTWARE_TREES = ("src", "tests", "tools")
# The declarations that decide what gets built and which interpreter builds it.
BUILD_FILES = ("pyproject.toml", "uv.lock", ".python-version")
# Compiled copies and tool caches appear inside the software trees and are never inputs.
IGNORED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(2**20), b""):
            value.update(chunk)
    return value.hexdigest()


def declared_files(root: Path) -> tuple[str, ...]:
    """The build declarations plus the files they name, such as pyproject's readme."""
    declarations = list(BUILD_FILES)
    manifest = root / "pyproject.toml"
    if not manifest.is_file():
        return tuple(declarations)
    # TOML is UTF-8 by definition; reading text would decode it in the locale's encoding.
    with manifest.open("rb") as source:
        readme = tomllib.load(source).get("project", {}).get("readme")
    # The table form names its file under `file`; inline `text` declares no input.
    if isinstance(readme, dict):
        readme = readme.get("file")
    if isinstance(readme, str):
        # A declaration reaching outside the tree is not an input this receipt can pin.
        if Path(readme).is_absolute() or ".." in Path(readme).parts:
            raise ValueError(f"declared readme escapes the tree: {readme}")
        declarations.append(readme)
    return tuple(declarations)


def software_paths(root: Path) -> Iterator[Path]:
    """Every file that can change what the software does, in a stable order."""
    declarations = declared_files(root)
    # An absent tree or declaration means an incomplete copy, not an empty receipt.
    missing = [name for name in SOFTWARE_TREES if not (root / name).is_dir()]
    missing += [name for name in declarations if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"{root} is missing software inputs: {', '.join(missing)}")
    for tree in SOFTWARE_TREES:
        for path in sorted((root / tree).rglob("*")):
            if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(root).parts):
                yield path
    for name in declarations:
        yield root / name


def inventory(root: Path) -> dict[str, str]:
    """The receipt's software inputs: path relative to ``root`` to content hash."""
    return {path.relative_to(root).as_posix(): digest(path) for path in software_paths(root)}


def imported_package(name: str = "pring_cycle") -> dict[str, Any]:
    """What the interpreter actually resolved, which the source tree alone cannot prove."""
    module: ModuleType = importlib.import_module(name)
    if module.__file__ is None:
        raise ValueError(f"{name} has no file to pin")
    root = Path(module.__file__).resolve().parent
    files = {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(root).parts)
    }
    return {"name": name, "path": str(root), "files": files}
