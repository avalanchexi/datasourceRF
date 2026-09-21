"""Reclaim what verification leaves behind; keep what a run could still be reading.

Two kinds of leftovers accumulate, and neither has an owner.

A material is stored under a key over the code, dependencies, builders and inputs that
produced it, so every change to any of them stores another one and none of the earlier ones
is ever read again. They are three gigabytes each. A build in progress lives beside it as
``<key>.build-<pid>``, removed when the build finishes -- so a build that is interrupted,
by a kill or a crash, leaves its partial copy behind forever.

Deleting the wrong one costs an hour of rebuilding, so this refuses to guess: a build whose
pid is still alive is left alone, and stored materials are kept newest-first. Nothing is
deleted without --apply.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import time
from pathlib import Path

BUILD_SUFFIX = re.compile(r"\.build-(\d+)$")


def material_store() -> Path:
    configured = os.environ.get("PRING_TEST_MATERIALS_ROOT")
    if configured:
        return Path(configured)
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "pring-cycle" / "test-materials"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _gib(size: int) -> str:
    return f"{size / 1024 ** 3:.1f}G"


def _classify(
    store: Path, keep: int, days: float
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Split the store into what may go and what is kept, each with its reason."""
    if not store.is_dir():
        return [], []
    builds: list[tuple[Path, str]] = []
    keepers: list[tuple[Path, str]] = []
    stored: list[Path] = []
    for entry in sorted(store.iterdir()):
        if not entry.is_dir():
            continue
        match = BUILD_SUFFIX.search(entry.name)
        if match:
            pid = int(match.group(1))
            if _alive(pid):
                keepers.append((entry, f"build in progress, pid {pid} alive"))
            else:
                builds.append((entry, f"interrupted build, pid {pid} gone"))
            continue
        stored.append(entry)

    stored.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    cutoff = time.time() - days * 86400
    removable: list[tuple[Path, str]] = list(builds)
    for index, entry in enumerate(stored):
        age_days = (time.time() - entry.stat().st_mtime) / 86400
        if index < keep:
            keepers.append((entry, f"newest {index + 1} of {keep} kept ({age_days:.1f}d old)"))
        elif entry.stat().st_mtime >= cutoff:
            keepers.append((entry, f"within {days:g}d window ({age_days:.1f}d old)"))
        else:
            removable.append((entry, f"superseded, {age_days:.1f}d old"))
    return removable, keepers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, default=3, help="Stored materials to keep (default 3)")
    parser.add_argument(
        "--days", type=float, default=2.0, help="Also keep anything newer than this (default 2)"
    )
    parser.add_argument("--apply", action="store_true", help="Delete; otherwise only report")
    args = parser.parse_args()
    if args.keep < 1:
        parser.error("--keep must be at least 1: a run with no material rebuilds from scratch")

    store = material_store()
    removable, keepers = _classify(store, args.keep, args.days)
    if not removable and not keepers:
        print(f"No material store at {store}")
        return 0

    print(f"Material store: {store}")
    for entry, reason in sorted(keepers, key=lambda item: item[0].name):
        print(f"  keep    {entry.name[:16]:16}  {_gib(_size_bytes(entry)):>6}  {reason}")
    freed = 0
    for entry, reason in sorted(removable, key=lambda item: item[0].name):
        size = _size_bytes(entry)
        freed += size
        verb = "remove " if args.apply else "would  "
        print(f"  {verb} {entry.name[:16]:16}  {_gib(size):>6}  {reason}")
        if args.apply:
            shutil.rmtree(entry, ignore_errors=True)

    if not removable:
        print("Nothing to reclaim.")
        return 0
    if args.apply:
        print(f"Reclaimed {_gib(freed)}.")
    else:
        print(f"Would reclaim {_gib(freed)}. Re-run with --apply to delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
