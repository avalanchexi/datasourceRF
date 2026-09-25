"""tools/check.py: quick runs only named affected tests; full runs everything once, receipt-free."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_check() -> ModuleType:
    """tools/ is verification tooling beside the package, not part of the wheel."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import tools.check

    return tools.check


def run_check(monkeypatch: pytest.MonkeyPatch, *argv: str) -> tuple[int, list[list[str]]]:
    check = load_check()
    launched: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        launched.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    monkeypatch.setattr(check, "_stale_environment", lambda: None)
    monkeypatch.setattr(sys, "argv", ["check.py", *argv])
    return check.main(), launched


def test_full_runs_default_discovery_without_a_freeze_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, launched = run_check(monkeypatch, "full")

    assert code == 0
    assert len(launched) == 1
    selectors = [part for part in launched[0][3:] if not part.startswith("-")]
    assert selectors == []
    out = capsys.readouterr().out
    assert "Exit: 0; elapsed:" in out
    assert "receipt" not in out.lower()


def test_full_no_longer_accepts_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        run_check(monkeypatch, "full", "--freeze")


def test_quick_still_rejects_directories_and_heavy_files(monkeypatch: pytest.MonkeyPatch) -> None:
    check = load_check()
    for selector in ["tests/integration", *sorted(check.HEAVY_FILES)]:
        with pytest.raises(SystemExit):
            run_check(monkeypatch, "quick", selector)


def test_quick_runs_named_files(monkeypatch: pytest.MonkeyPatch) -> None:
    code, launched = run_check(monkeypatch, "quick", "tests/domain/test_trend_state.py")

    assert code == 0
    assert "tests/domain/test_trend_state.py" in launched[0]


def write_package(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_package_drift_is_none_when_every_file_matches(tmp_path: Path) -> None:
    check = load_check()
    files = {"a.py": "x = 1\n", "domain/b.py": "y = 2\n", "assets/c.css": "p {}\n"}
    tree = write_package(tmp_path / "tree", files)
    installed = write_package(tmp_path / "installed", files)
    (installed / "__pycache__").mkdir()
    (installed / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\0")

    assert check._package_drift(tree, installed) is None


def test_package_drift_names_a_module_whose_content_changed(tmp_path: Path) -> None:
    """The copy that `uv sync` leaves behind keeps every file name while the code moves on."""
    check = load_check()
    tree = write_package(tmp_path / "tree", {"a.py": "x = 2\n", "b.py": "y = 2\n"})
    installed = write_package(tmp_path / "installed", {"a.py": "x = 1\n", "b.py": "y = 2\n"})

    drift = check._package_drift(tree, installed)

    assert drift == "changed 1: a.py"


def test_package_drift_looks_inside_subpackages(tmp_path: Path) -> None:
    check = load_check()
    tree = write_package(tmp_path / "tree", {"a.py": "", "domain/new.py": ""})
    installed = write_package(tmp_path / "installed", {"a.py": "", "domain/old.py": ""})

    drift = check._package_drift(tree, installed)

    assert drift == "missing 1: domain/new.py; stale 1: domain/old.py"


def test_package_drift_leaves_out_what_a_build_would_not_take(tmp_path: Path) -> None:
    """Hatchling skips git-ignored files, so their absence from the copy is not drift."""
    check = load_check()
    tree = write_package(tmp_path / "tree", {"a.py": "", "debug.log": "noise"})
    installed = write_package(tmp_path / "installed", {"a.py": ""})

    assert check._package_drift(tree, installed, packaged={"a.py"}) is None
