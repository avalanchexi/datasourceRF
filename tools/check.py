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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("quick", "full"))
    parser.add_argument("tests", nargs="*", help="Explicit test files or pytest node IDs")
    parser.add_argument("--collect-only", action="store_true")
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
