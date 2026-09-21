"""Explicit related-test feedback; ordinary pytest discovery remains complete."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# These files prepare complete public model lifecycles. Use explicit pytest for their
# affected acceptance checks, or the full command below. No default pytest marker changes.
HEAVY_FILES = {
    "tests/models/test_isolated_lifecycle.py",
    "tests/integration/test_worker_registered_catalog.py",
    "tests/integration/test_integrated_worker_delivery.py",
    "tests/integration/test_integrated_worker_core_gap.py",
    "tests/models/test_material_preflight.py",
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
    tree = {path.name for path in (ROOT / "src" / "pring_cycle").glob("*.py")}
    installed = {path.name for path in installed_dir.glob("*.py")}
    if tree == installed:
        return None
    missing = sorted(tree - installed)
    extra = sorted(installed - tree)
    parts = []
    if missing:
        parts.append(f"missing {len(missing)}: {', '.join(missing[:5])}")
    if extra:
        parts.append(f"stale {len(extra)}: {', '.join(extra[:5])}")
    return "; ".join(parts)


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
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="Declare this full run is for a frozen version's receipt (see ADR-0014)",
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
    elif not args.freeze:
        print(
            "full produces one thing: the acceptance receipt for a frozen version. The material\n"
            "identity key covers the source, so the next edit to src/ voids whatever this run\n"
            "returns -- and this suite takes about 1.7 hours. Between 09-18 and 09-20 it was\n"
            "started nine times for 14.4 hours and the receipts kept being voided (ADR-0014).\n"
            "\n"
            "  freezing a version  ->  tools/check.py full --freeze\n"
            "  daily feedback      ->  tools/check.py quick <related test files>\n"
            "  affected heavy work ->  run that acceptance explicitly",
            file=sys.stderr,
            flush=True,
        )
        return 2
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
            "Related feedback only. Complete affected heavy acceptance before closing the slice.",
            flush=True,
        )
        if elapsed > 180:
            print("The 180s feedback target was exceeded; record the slow phases.", flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
