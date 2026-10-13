"""Is the wall clock steady enough for a real run or the full suite? Exit 0 if so, 1 if not.

    python3 tools/clock_check.py [--seconds 65] [--threshold 0.2]

Watches ``time.time() - time.monotonic()`` and reports every step larger than the threshold.
A backward step makes ``acquisition._check_time`` refuse receipts (``acquisition_time_invalid``)
and fails the quota timeline test, so run this before either. On this WSL host the steps come
from two clock syncs pulling against each other; see ``docs/development/local-runtime.md``
(墙钟回拨). Standard library only.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time


def _timesyncd_state() -> str:
    if shutil.which("systemctl") is None:
        return "unknown (no systemctl)"
    done = subprocess.run(
        ["systemctl", "is-active", "systemd-timesyncd"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or "unknown"


def watch(seconds: float, threshold: float) -> list[tuple[float, float]]:
    """Every step of the wall clock against the monotonic one, as (elapsed, size) pairs."""
    start = time.monotonic()
    previous = time.time() - start
    steps = []
    while (now := time.monotonic()) - start < seconds:
        time.sleep(0.02)
        offset = time.time() - time.monotonic()
        if abs(offset - previous) > threshold:
            steps.append((round(now - start, 1), round(offset - previous, 3)))
        previous = offset
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=65.0)
    parser.add_argument("--threshold", type=float, default=0.2)
    args = parser.parse_args()
    print(f"systemd-timesyncd: {_timesyncd_state()}")
    steps = watch(args.seconds, args.threshold)
    if steps:
        listed = ", ".join(f"{size:+.3f}s at {at}s" for at, size in steps)
        print(f"clock: {len(steps)} step(s) over {args.threshold}s in {args.seconds:g}s: {listed}")
        print("unsteady: see docs/development/local-runtime.md (墙钟回拨) before running")
        return 1
    print(f"clock: steady, no step over {args.threshold}s in {args.seconds:g}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
