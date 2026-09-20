"""What a verification receipt pins as software, and what it leaves to material identity."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]

PYPROJECT = """\
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "example"
version = "0.1.0"
readme = "{readme}"
"""


def load_inputs() -> ModuleType:
    """tools/ is verification tooling beside the package, not part of the wheel."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import tools.inputs

    return tools.inputs


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_project(root: Path, *, readme: str = "README.md") -> None:
    write(root / "src/example/cli.py", "def main() -> int:\n    return 0\n")
    write(root / "tests/test_cli.py", "def test_main() -> None:\n    assert True\n")
    write(root / "tools/check.py", "print('check')\n")
    write(root / "pyproject.toml", PYPROJECT.format(readme=readme))
    write(root / readme, "How to run it.\n")
    write(root / "uv.lock", "version = 1\n")
    write(root / ".python-version", "3.12\n")
    # .scratch carries both the materials a run reads and the notes it writes.
    write(root / ".scratch/repair/implementation-19.md", "run one\n")
    write(root / ".scratch/repair/evidence-import/original.json", '{"value": 1}\n')


def test_evidence_notes_leave_the_software_receipt_unchanged(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    receipt = inputs.inventory(tmp_path)

    write(tmp_path / ".scratch/repair/implementation-19.md", "run one\nrun two\n")
    write(tmp_path / ".scratch/repair/verification-19-related.txt", "3 passed\n")

    assert inputs.inventory(tmp_path) == receipt
    assert not [key for key in receipt if key.startswith(".scratch")]


def differences(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Compare both ways: a removed input changes the receipt as much as an edited one."""
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))


def test_source_change_invalidates_the_software_receipt(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    receipt = inputs.inventory(tmp_path)

    write(tmp_path / "src/example/cli.py", "def main() -> int:\n    return 1\n")

    assert differences(receipt, inputs.inventory(tmp_path)) == ["src/example/cli.py"]


def test_a_removed_source_file_invalidates_the_software_receipt(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    receipt = inputs.inventory(tmp_path)

    (tmp_path / "src/example/cli.py").unlink()

    assert differences(receipt, inputs.inventory(tmp_path)) == ["src/example/cli.py"]


def test_an_incomplete_tree_is_refused_rather_than_pinned_as_empty(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    (tmp_path / "uv.lock").unlink()

    with pytest.raises(FileNotFoundError, match="uv.lock"):
        inputs.inventory(tmp_path)

    # A root that is not a project at all must not read as a complete receipt either.
    with pytest.raises(FileNotFoundError):
        inputs.inventory(tmp_path / "nowhere")


def test_a_readme_declared_outside_the_tree_is_refused(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    write(tmp_path / "pyproject.toml", PYPROJECT.format(readme="../outside.md"))

    with pytest.raises(ValueError, match="escapes the tree"):
        inputs.inventory(tmp_path)


def test_receipt_keys_are_posix_paths(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)

    assert "src/example/cli.py" in inputs.inventory(tmp_path)
    assert not [key for key in inputs.inventory(tmp_path) if "\\" in key]


def test_the_imported_package_is_pinned_separately_from_the_tree(tmp_path: Path) -> None:
    """The venv holds a built copy, so the tree alone cannot say what ran."""
    inputs = load_inputs()
    write(tmp_path / "pinned_example/__init__.py", "VALUE = 1\n")
    write(tmp_path / "pinned_example/__pycache__/stale.pyc", "compiled\n")
    sys.path.insert(0, str(tmp_path))
    try:
        identity = inputs.imported_package("pinned_example")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("pinned_example", None)

    assert identity["path"] == str((tmp_path / "pinned_example").resolve())
    assert list(identity["files"]) == ["__init__.py"]


def test_the_build_declared_readme_is_pinned(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path, readme="DOC.md")
    receipt = inputs.inventory(tmp_path)
    assert "DOC.md" in receipt

    write(tmp_path / "DOC.md", "How to run it, revised.\n")
    assert inputs.inventory(tmp_path)["DOC.md"] != receipt["DOC.md"]


def test_caches_inside_the_software_trees_are_not_pinned(tmp_path: Path) -> None:
    inputs = load_inputs()
    build_project(tmp_path)
    write(tmp_path / "src/example/__pycache__/cli.cpython-312.pyc", "compiled\n")
    write(tmp_path / "tests/.pytest_cache/CACHEDIR.TAG", "signature\n")

    assert not [key for key in inputs.inventory(tmp_path) if "cache" in key.lower()]


def test_this_repository_pins_software_and_not_evidence() -> None:
    inputs = load_inputs()
    receipt = inputs.inventory(ROOT)

    declared = {"pyproject.toml", "uv.lock", ".python-version", "README.md"}
    stray = sorted(
        key
        for key in receipt
        if not key.startswith(("src/", "tests/", "tools/")) and key not in declared
    )
    assert stray == []
    assert declared <= set(receipt)
    assert {"src/pring_cycle/cli.py", "tests/conftest.py", "tools/check.py"} <= set(receipt)
