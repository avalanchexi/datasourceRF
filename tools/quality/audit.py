"""Read-only data quality audit of one completed run; writes a Markdown report.

    python tools/quality/audit.py --run <run_id> [--database <path>] [--out <md>]

Standard library only, and deliberately independent of ``pring_cycle``: the database is
opened read-only, raw artifacts are read by content hash, nothing calls out. See
``docs/development/data-quality-audit.md``.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import acquisition
import model_input
import output_consistency
from common import DEFAULT_DATABASE, Run, connect

# One entry per audit section, in report order. Each takes the loaded run and returns Markdown.
SECTIONS = [
    acquisition.section,
    model_input.section,
    output_consistency.section,
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, help="completed run id, e.g. run-a8675946…")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--out", type=Path, help="write the report here instead of stdout")
    args = parser.parse_args(argv)

    started = time.monotonic()
    db = connect(args.database)
    run = Run.load(db, args.run, args.database)
    parts = [
        f"# 数据质量体检：{run.run_id}",
        "",
        f"- 目标日 {run.target_date}，模型 {run.model_version_id}"
        f"（目录 {run.catalog_version}，{len(run.catalog)} 项，模型用到 {len(run.model_used)} 项）",
        f"- 截止（冻结的 system_as_of）{run.cutoff}",
        "",
    ]
    parts += [section(run) for section in SECTIONS]
    parts.append(f"_体检耗时 {time.monotonic() - started:.1f} 秒；数据库只读打开。_\n")
    report = "\n".join(parts)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
