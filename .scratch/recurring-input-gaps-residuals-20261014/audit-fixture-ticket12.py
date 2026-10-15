"""Ticket 12 fixture: audit a run as if it had SOX's registered path (ADR-0042).

    PYTHONDONTWRITEBYTECODE=1 python audit-fixture-ticket12.py <worktree> <run_id> <out.md> MODE

The runtime database is opened read-only as usual; a few SOX rows are laid over it in TEMP
views of the same names (temp objects live in memory, nothing is written). Modes:

- ``held``: the run's own Nasdaq receipt (validated) and claims for 2026-10-12 and 10-13;
- ``receipt``: the run's own Nasdaq receipt, failed, no claim;
- ``freshness``: no receipt, only the run's batch freshness naming ``nasdaq:index_history``.

Every mode also sets the run's SOX batch freshness source to ``nasdaq:index_history``.
"""

import sys
from pathlib import Path

worktree, run_id, out, mode = sys.argv[1:5]
assert mode in {"held", "receipt", "freshness"}, mode
sys.path.insert(0, str(Path(worktree) / "tools/quality"))

import audit  # noqa: E402
import common  # noqa: E402

SOX = "NASDAQ_SOX_INDEX"
ACQ = "acquisition-ticket12-fixture-sox"
STARTED = "2026-10-14T03:41:46.000000+00:00"
CLAIMS = (
    ("2026-10-12", 12236.79, "2026-10-12T22:00:00+00:00"),
    ("2026-10-13", 12208.79, "2026-10-13T22:00:00+00:00"),
)


def overlay(path):
    db = common.connect(path)
    (version,) = db.execute(
        "SELECT json_extract(m.manifest_json, '$.metric_catalog_version') FROM parent_run p"
        " JOIN model_version m USING (model_version_id) WHERE p.run_id = ?",
        (run_id,),
    ).fetchone()
    for name in ("acquisition_request", "full_run_acquisition", "source_claim",
                 "source_claim_acquisition"):  # fmt: skip
        db.execute(f"CREATE TEMP TABLE fx_{name} AS SELECT * FROM main.{name} WHERE 0")
    if mode != "freshness":
        ok = mode == "held"
        db.execute(
            "INSERT INTO fx_acquisition_request (acquisition_id, provider, api_name,"
            " parameters_json, fields, parser_version, started_at, received_at, validated_at,"
            " state, structure_check, ingest_result, source_record_count,"
            " normalized_scalar_count, ingested_claim_count) VALUES (?, 'Nasdaq Global Indexes',"
            " 'official_http_post', ?, 'TimeStamp,Value', 'nasdaq-index-history-parser-v0001',"
            " ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ACQ,
                '{"definition_version": "%s", "period": "2026-10-13", "source_url":'
                ' "https://indexes.nasdaqomx.com/Index/HistoryData", "start_date": "2026-04-01"}'
                % version,
                STARTED,
                STARTED if ok else None,
                STARTED if ok else None,
                "validated" if ok else "failed",
                "passed" if ok else None,
                "accepted" if ok else None,
                *((2, 2, 2) if ok else (None, None, None)),
            ),
        )
        db.execute(
            "INSERT INTO fx_full_run_acquisition VALUES (?, ?, 'direct_context_refresh', ?, NULL)",
            (run_id, ACQ, f'["{SOX}"]'),
        )
    if mode == "held":
        for day, value, public in CLAIMS:
            claim = f"ticket12-fixture-sox-{day}"
            db.execute(
                "INSERT INTO fx_source_claim VALUES (?, ?, ?, ?, 'business_day', ?, ?, '{}', ?,"
                " 'reported_value', 'index_points', 'Nasdaq Global Indexes', ?,"
                " 'ticket12-fixture', NULL, NULL, ?, ?, 'awaiting_source_certification',"
                " 'validated', NULL, ?)",
                (claim, claim, SOX, version, day, day, value,
                 f"https://indexes.nasdaqomx.com/Index/HistoryData#date={day}",
                 STARTED, STARTED, public),
            )  # fmt: skip
            db.execute("INSERT INTO fx_source_claim_acquisition VALUES (?, ?)", (claim, ACQ))
    for name in ("acquisition_request", "full_run_acquisition", "source_claim",
                 "source_claim_acquisition"):  # fmt: skip
        db.execute(
            f"CREATE TEMP VIEW {name} AS SELECT * FROM main.{name}"
            f" UNION ALL SELECT * FROM temp.fx_{name}"
        )
    columns = [r[1] for r in db.execute("PRAGMA main.table_info(batch_freshness)")]
    chosen = [
        f"CASE WHEN batch_id = '{run_id}' AND metric_id = '{SOX}'"
        " THEN 'nasdaq:index_history' ELSE source END AS source"
        if c == "source"
        else c
        for c in columns
    ]
    db.execute(
        f"CREATE TEMP VIEW batch_freshness AS SELECT {', '.join(chosen)} FROM main.batch_freshness"
    )
    return db


audit.connect = overlay
raise SystemExit(audit.main(["--run", run_id, "--out", out]))
