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
