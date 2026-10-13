"""One snapshot of heavy background work, for the periodic progress report.

    python3 tools/progress.py [--log <pytest console log>] [--timings <timings jsonl>]

Prints, in order: the heavy processes and how long each has run; the pytest run's cases done,
percent and failures (from ``--log``, the console output of ``check.py``) and its current case
(from ``--timings``, else the newest ``pring-check-*.jsonl`` in the temp directory); who holds
``/tmp/pring-heavy.lock``; free space on C:; and whether ``systemd-timesyncd`` runs. Standard
library only, read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HEAVY = re.compile(r"pytest|check\.py|pring-cycle worker|codex exec|audit\.py")
LOCK = Path("/tmp/pring-heavy.lock")
WRAPPER = re.compile(r"tools/progress\.py|shell-snapshots|^/bin/bash -c ")
PERCENT = re.compile(r"\[\s*(\d+)%\]")


def processes() -> list[str]:
    done = subprocess.run(
        ["ps", "-eo", "pid=,etime=,args="], capture_output=True, text=True, check=False
    )
    rows = []
    for line in done.stdout.splitlines():
        pid, etime, args = line.split(None, 2)
        # Skip this script and the agent's own shell wrappers, whose text quotes the command.
        if HEAVY.search(args) and not WRAPPER.search(args):
            rows.append(f"  {pid:>7} {etime:>11}  {args[:110]}")
    return rows


def pytest_progress(log: Path | None, timings: Path | None) -> list[str]:
    lines = []
    if timings is None:
        found = sorted(
            Path(tempfile.gettempdir()).glob("pring-check-*.jsonl"), key=lambda p: p.stat().st_mtime
        )
        timings = found[-1] if found else None
    calls, current = 0, ""
    if timings and timings.is_file():
        with timings.open(encoding="utf-8") as handle:
            for raw in handle:
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                current = record.get("node", current)
                calls += record.get("when") == "call"
        lines.append(f"  cases run: {calls}  current: {current}  ({timings})")
    if log and log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        progress = [ln for ln in text.splitlines() if PERCENT.search(ln) or set(ln) <= set(".FEsx")]
        marks = "".join(ln.split("[")[0].strip() for ln in progress)
        percents = PERCENT.findall(text)
        percent = int(percents[-1]) if percents else None
        total = f" of ~{round(calls * 100 / percent)}" if percent and calls else ""
        bar = "#" * (percent // 10) + "-" * (10 - percent // 10) if percent is not None else ""
        lines.append(
            f"  progress: {percent}%{total} [{bar}]  failed: {marks.count('F')}"
            f"  errors: {marks.count('E')}"
        )
        tail = text.rstrip().splitlines()[-1:] or [""]
        if re.search(r"\d+ (passed|failed)", tail[0]):
            lines.append(f"  finished: {tail[0]}")
    return lines


def lock_holder() -> str:
    if not LOCK.exists():
        return "free (no lock file)"
    inode = os.stat(LOCK).st_ino
    for line in Path("/proc/locks").read_text().splitlines():
        fields = line.split()
        if len(fields) > 5 and fields[5].endswith(f":{inode}"):
            pid = fields[4]
            try:
                cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
            except OSError:
                cmd = "?"
            return f"held by {pid}: {cmd[:100]}"
    return "free"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path)
    parser.add_argument("--timings", type=Path)
    args = parser.parse_args()
    rows = processes()
    print("heavy processes:" if rows else "heavy processes: none")
    for row in rows:
        print(row)
    progress = pytest_progress(args.log, args.timings)
    if progress:
        print("pytest:")
        print("\n".join(progress))
    print(f"heavy lock: {lock_holder()}")
    free = shutil.disk_usage("/mnt/c").free / 2**30 if Path("/mnt/c").exists() else float("nan")
    print(f"C: free {free:.0f}G")
    state = subprocess.run(
        ["systemctl", "is-active", "systemd-timesyncd"], capture_output=True, text=True, check=False
    ).stdout.strip()
    print(f"systemd-timesyncd: {state or 'unknown'}")


if __name__ == "__main__":
    main()
