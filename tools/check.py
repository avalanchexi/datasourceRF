"""Explicit related-test feedback; ordinary pytest discovery remains complete."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The complete registered catalog end to end: run it explicitly, not through quick.
HEAVY_FILES = {
    "tests/integration/test_worker_registered_catalog.py",
}


def _stale_environment() -> str | None:
    """Name the modules that differ between the source tree and what will be imported.

    ``--no-editable`` installs a copy, and ``uv sync`` only reinstalls when the version
    changes, which it never does. So the interpreter can import a package that is missing
    modules the tree has, or still carries ones it deleted, with nothing to say so. The
    failures look like ImportError in unrelated tests, and a full suite only reaches them
    after the wait its whole point was to avoid.
    """
    import importlib.util

    spec = importlib.util.find_spec("pring_cycle")
    if spec is None or not spec.origin:
        return "pring_cycle is not importable; install it into this environment first"
    installed_dir = Path(spec.origin).parent
    if installed_dir == ROOT / "src" / "pring_cycle":
        return None  # An editable or path install already reads the tree.
    tree = ROOT / "src" / "pring_cycle"
    return _package_drift(tree, installed_dir, packaged=_packaged_names(tree))


def _packaged_names(tree: Path) -> set[str] | None:
    """What the wheel takes from the tree: hatchling leaves out whatever git ignores."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=tree,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {name for name in listed.decode().split("\0") if name}


def _package_drift(tree: Path, installed: Path, *, packaged: set[str] | None = None) -> str | None:
    """Compare every packaged file by content, subpackages included.

    Names alone miss the usual case: an old copy keeps the same modules while their code moves
    on. Bytecode is left out; it is what the installed copy writes, not what it was built from.
    ``packaged`` narrows the tree to what a build would take from it.
    """

    def files(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }

    tree_files, installed_files = files(tree), files(installed)
    if packaged is not None:
        tree_files = {name: data for name, data in tree_files.items() if name in packaged}
    missing = sorted(tree_files.keys() - installed_files.keys())
    extra = sorted(installed_files.keys() - tree_files.keys())
    changed = sorted(
        name
        for name in tree_files.keys() & installed_files.keys()
        if tree_files[name] != installed_files[name]
    )
    parts = [
        f"{label} {len(names)}: {', '.join(names[:5])}"
        for label, names in (("missing", missing), ("stale", extra), ("changed", changed))
        if names
    ]
    return "; ".join(parts) or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("quick", "full"))
    parser.add_argument("tests", nargs="*", help="Explicit test files or pytest node IDs")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument(
        "--allow-stale-environment",
        action="store_true",
        help="Run even when the installed pring_cycle differs from src/",
    )
    args = parser.parse_args()
    if args.mode == "quick":
        if not args.tests:
            parser.error("quick requires explicit related test files or node IDs")
        for node in args.tests:
            path = (ROOT / node.split("::", 1)[0]).resolve()
            if not path.is_relative_to(ROOT / "tests") or not path.is_file():
                parser.error(f"quick requires a file inside tests, not a directory: {node}")
            if path.relative_to(ROOT).as_posix() in HEAVY_FILES:
                parser.error(f"explicit heavy acceptance is required for: {node}")
    elif args.tests:
        parser.error("full always uses complete default discovery; omit selectors")
    drift = _stale_environment()
    if drift is not None and not args.allow_stale_environment:
        print(
            f"The installed pring_cycle does not match src/: {drift}.\n"
            "Whatever this run reports would be about the installed copy, not the tree. Run:\n"
            "  uv sync --extra dev --no-editable --reinstall-package pring-cycle\n"
            "Pass --allow-stale-environment to run against the installed copy on purpose.",
            file=sys.stderr,
            flush=True,
        )
        return 2
    command = [sys.executable, "-m", "pytest", *args.tests, "-q", "--durations=10"]
    if args.collect_only:
        command.append("--collect-only")
    operation = "collection only" if args.collect_only else "execution"
    print(f"Scope: {args.mode}; {operation}", flush=True)
    print(shlex.join(command), flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, check=False)
    elapsed = time.monotonic() - started
    print(f"Exit: {result.returncode}; elapsed: {elapsed:.2f}s", flush=True)
    if args.mode == "quick":
        print(
            "Affected feedback only. Close the slice with the two fast smoke tests (ADR-0025).",
            flush=True,
        )
        if elapsed > 180:
            print("The 180s feedback target was exceeded; record the slow phases.", flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
