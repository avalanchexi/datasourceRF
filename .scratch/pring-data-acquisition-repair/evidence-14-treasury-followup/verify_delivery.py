"""Offline, standard-library verification of the bounded Treasury research delivery.

Run from any directory with C:/Python313/python.exe -B path/to/verify_delivery.py.
Only --write-manifest writes one file in this evidence directory; default is read-only.
This script does not import the app, open a database, or use the network.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
PROJECT = EVIDENCE.parent
REPO = PROJECT.parent.parent
REPORT = PROJECT / "treasury-followup.md"
OLD_HTML = PROJECT / "evidence-14/54a2b1462c7a2116201b45eaf2dfdfe8fe3654cfd62fe46b6c2c09439c252330"
OLD_REPORT_HASH = "1bad5c100b8996dfa1286da712c723211b9640d8cc98a1e24cdec8647bedf82b"


def digest(path: Path) -> dict[str, str | int]:
    raw = path.read_bytes()
    return {"path": path.relative_to(REPO).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict]] = []
        self.row: list[dict] | None = None
        self.cell: dict | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell = {"tag": tag, "attrs": dict(attrs), "text": ""}

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = re.sub(r"\s+", " ", self.cell["text"]).strip()
            assert self.row is not None
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def verify() -> dict:
    receipts = json.loads((EVIDENCE / "receipts.json").read_text(encoding="utf-8"))
    assert len(receipts) == 3
    for receipt in receipts:
        assert receipt["method"] == "GET" and receipt["status"] == 200 and receipt["truncated"] is False
        assert receipt["public_available_at"] is None
        actual = digest(EVIDENCE / receipt["local_file"])
        assert actual["bytes"] == receipt["bytes"] and actual["sha256"] == receipt["sha256"]
        assert datetime.fromisoformat(receipt["received_at"]) >= datetime.fromisoformat(receipt["started_at"])
    assert digest(OLD_HTML)["sha256"] == OLD_HTML.name
    assert digest(PROJECT / "research-14.md")["sha256"] == OLD_REPORT_HASH

    parser = TableRows()
    parser.feed(OLD_HTML.read_text(encoding="utf-8"))
    html_points = {}
    for row in parser.rows:
        cells = {cell["attrs"].get("headers"): cell["text"] for cell in row if cell["tag"] == "td"}
        text = cells.get("view-field-tdr-date-table-column")
        if text is None:
            continue
        period = datetime.strptime(text, "%m/%d/%Y").date().isoformat()
        assert period not in html_points
        html_points[period] = {f"{m} Yr": cells[f"view-field-bc-{m}year-table-column"] for m in (2, 10)}

    csv_receipt = next(r for r in receipts if r["headers"]["Content-Type"].startswith("text/csv"))
    reader = csv.DictReader(io.StringIO((EVIDENCE / csv_receipt["sha256"]).read_text(encoding="utf-8-sig")))
    assert reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)) == 15
    assert {"Date", "2 Yr", "10 Yr"}.issubset(reader.fieldnames)
    rows = []
    counts = {key: dict(positive=0, zero=0, negative=0, blank=0, special=0) for key in ("2 Yr", "10 Yr")}
    for row in reader:
        assert None not in row and all(value is not None for value in row.values())
        period = datetime.strptime(row["Date"], "%m/%d/%Y").date().isoformat()
        values = {key: row[key] for key in counts}
        matches = {}
        for key, text in values.items():
            try:
                value = Decimal(text)
            except InvalidOperation:
                value = None
            category = (
                "blank" if not text.strip() else
                "special" if value is None or not value.is_finite() else
                "positive" if value > 0 else "negative" if value < 0 else "zero"
            )
            counts[key][category] += 1
            matches[key] = period in html_points and value == Decimal(html_points[period][key])
        rows.append({"period": period, **values, "matches_old_html": matches})
    dates = [row["period"] for row in rows]
    assert len(dates) == len(set(dates)) == 171
    assert set(dates) == set(html_points)
    assert min(dates) == "2026-01-02" and max(dates) == "2026-09-04"
    assert sum("2026-03-09" <= day <= "2026-09-04" for day in dates) == 127
    assert all(all(row["matches_old_html"].values()) for row in rows)
    inspection = json.loads((EVIDENCE / "source-inspection.json").read_text(encoding="utf-8"))
    assert rows == inspection["rows"] and counts == inspection["value_classification"]
    assert inspection["csv_fieldnames"] == reader.fieldnames

    checked_links = []
    for target in re.findall(r"\[[^\]]*\]\(([^\n)]+)\)", REPORT.read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "#")):
            continue
        path = (PROJECT / target.split("#", 1)[0]).resolve()
        assert path.is_file(), target
        checked_links.append(target)

    delivery_paths = (EVIDENCE / "delivery-files.txt").read_text(encoding="utf-8").splitlines()
    assert len(delivery_paths) == len(set(delivery_paths)) == 9
    manifest_path = EVIDENCE / "delivery-verification.json"
    files = []
    for relative in delivery_paths:
        path = (REPO / relative).resolve()
        assert path == REPORT or path.is_relative_to(EVIDENCE)
        if path != manifest_path:
            assert path.is_file(), relative
            files.append(digest(path))
    return {
        "validation": "passed",
        "network_requests_during_verification": 0,
        "new_get_attempts": 3,
        "new_get_failures": 0,
        "new_raw_count": 3,
        "new_raw_bytes": sum(receipt["bytes"] for receipt in receipts),
        "verified_raw_including_reused_html": [digest(OLD_HTML)] + [digest(EVIDENCE / r["sha256"]) for r in receipts],
        "raw_bytes_including_reused_html": digest(OLD_HTML)["bytes"] + sum(r["bytes"] for r in receipts),
        "csv_period_count": len(rows),
        "window_period_count": 127,
        "compared_fields": len(rows) * 2,
        "matched_fields": sum(sum(row["matches_old_html"].values()) for row in rows),
        "value_classification": counts,
        "old_report_sha256_unchanged": OLD_REPORT_HASH,
        "report_local_links_checked": checked_links,
        "delivery_path_count": len(delivery_paths),
        "files": files,
        "manifest_self_hash_excluded": True,
    }


if __name__ == "__main__":
    result = verify()
    manifest = EVIDENCE / "delivery-verification.json"
    if sys.argv[1:] == ["--write-manifest"]:
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        assert not sys.argv[1:], "Only --write-manifest is supported"
        assert result == json.loads(manifest.read_text(encoding="utf-8")), "Manifest content differs from offline re-verification"
    print(json.dumps({key: result[key] for key in ("validation", "new_raw_count", "new_raw_bytes", "raw_bytes_including_reused_html", "csv_period_count", "compared_fields", "matched_fields", "delivery_path_count")}, indent=2))
