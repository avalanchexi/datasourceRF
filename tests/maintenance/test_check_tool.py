"""tools/check.py: quick runs only named affected tests; full runs everything once, receipt-free."""

from __future__ import annotations

import json
import os
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


def test_every_run_records_each_phase_to_a_timings_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ticket 24: --durations=10 kept the ten slowest phases; the full ranking was lost."""
    timings = tmp_path / "timings.jsonl"
    code, launched = run_check(
        monkeypatch, "quick", "tests/domain/test_trend_state.py", "--timings", str(timings)
    )

    assert code == 0
    # Attached values, so no option reads as a test selector.
    assert "-ptools.timings" in launched[0]
    assert f"--timings-file={timings}" in launched[0]


def test_the_timings_plugin_writes_setup_call_and_teardown_of_every_test(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def prepared():\n"
        "    yield 1\n\n"
        "def test_one(prepared):\n"
        "    assert prepared\n\n"
        "def test_two():\n"
        "    pass\n",
        encoding="utf-8",
    )
    timings = tmp_path / "timings.jsonl"
    # The outer run's options (a basetemp above this directory) are not the sample's.
    environment = {
        **{key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"},
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    finished = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tmp_path / "test_sample.py"),
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tools.timings",
            "--timings-file",
            str(timings),
            f"--rootdir={tmp_path}",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr
    records = [json.loads(line) for line in timings.read_text(encoding="utf-8").splitlines()]
    phases = {(record["node"].rsplit("::", 1)[1], record["when"]) for record in records}
    assert phases == {
        (name, when) for name in ("test_one", "test_two") for when in ("setup", "call", "teardown")
    }
    assert all(record["duration"] >= 0 for record in records)


def test_the_run_ends_with_the_ranking_and_where_its_timings_are(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    check = load_check()

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        [option] = [part for part in command if part.startswith("--timings-file=")]
        target = Path(option.split("=", 1)[1])
        write_timings(target, {"tests/a.py::test_one": (1.0, 2.0, 0.0)})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    monkeypatch.setattr(check, "_stale_environment", lambda: None)
    monkeypatch.setattr(sys, "argv", ["check.py", "quick", "tests/domain/test_trend_state.py"])

    assert check.main() == 0

    out = capsys.readouterr().out
    assert "Timings: 1 tests, 3.00s in test phases" in out
    timings = Path(out.split("Timings file: ", 1)[1].splitlines()[0])
    assert timings.is_file()
    timings.unlink()


def test_a_run_that_recorded_nothing_still_reports_its_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """An interrupted or collection-only run leaves no timings; that is not a check failure."""
    code, _ = run_check(
        monkeypatch,
        "quick",
        "tests/domain/test_trend_state.py",
        "--timings",
        str(tmp_path / "never-written.jsonl"),
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "Exit: 0; elapsed:" in out
    assert "no test phases recorded" in out


def write_timings(path: Path, durations: dict[str, tuple[float, float, float]]) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for node, phases in durations.items():
            for when, duration in zip(("setup", "call", "teardown"), phases, strict=True):
                handle.write(json.dumps({"node": node, "when": when, "duration": duration}) + "\n")
    return path


def test_the_summary_ranks_tests_by_all_their_phases_and_files_by_their_sum(
    tmp_path: Path,
) -> None:
    check = load_check()
    timings = write_timings(
        tmp_path / "timings.jsonl",
        {
            # A module fixture's setup lands on the file's first test.
            "tests/a.py::test_shared_run": (90.0, 0.5, 0.0),
            "tests/a.py::test_reads_it": (0.0, 0.5, 0.0),
            "tests/b.py::test_two_runs[x]": (1.0, 50.0, 1.0),
            "tests/b.py::test_two_runs[y]": (1.0, 7.0, 0.0),
            "tests/c.py::test_fast": (0.0, 0.0, 0.0),
        },
    )

    summary = check.timing_summary(timings, top_tests=2, top_files=2, top_count=1)

    lines = summary.splitlines()
    assert lines[0] == "Timings: 5 tests, 151.00s in test phases"
    tests_at = lines.index("Slowest 2 tests (setup / call / teardown):")
    files_at = lines.index("Slowest 2 files:")
    assert [line.split() for line in lines[tests_at + 1 : tests_at + 3]] == [
        ["90.50s", "90.00", "/", "0.50", "/", "0.00", "tests/a.py::test_shared_run"],
        ["52.00s", "1.00", "/", "50.00", "/", "1.00", "tests/b.py::test_two_runs[x]"],
    ]
    assert [line.split() for line in lines[files_at + 1 : files_at + 3]] == [
        ["91.00s", "2", "tests", "tests/a.py"],
        ["60.00s", "2", "tests", "tests/b.py"],
    ]
    assert "Top 1 tests: 59.9% of test-phase time" in lines
    # A tenth of five tests rounds up to one.
    assert "Top 10% (1 tests): 59.9% of test-phase time" in lines
