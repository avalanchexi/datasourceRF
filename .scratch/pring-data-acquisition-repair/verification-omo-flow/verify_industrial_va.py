"""Read-only literal verification; no application imports or parser calls."""

import calendar
import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self.tables[-1].append([])
        elif tag in {"td", "th"}:
            self.cell = [self.getpos()[0], ""]
            self.tables[-1][-1].append(self.cell)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[1] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"}:
            self.cell = None


def documents(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from documents(child)
    elif isinstance(value, list):
        for child in value:
            yield from documents(child)


base = Path(__file__).resolve().parents[1]
raw = (base / "p1-industrial-va-full-value-audit.md").read_bytes()
assert len(raw) == 16362
assert hashlib.sha256(raw).hexdigest() == "ef2e599944f049fab8a7bcce34aede93ac29dd2c33c5cd0a2541faf4d0984406"
text = raw.decode("utf-8")
links = [item for item in re.findall(r"\]\(([^)]+)\)", text) if "://" not in item]
assert len(links) == 12
for item in links:
    assert (base / item).is_file()
inputs = 0
originals = {}
for line in text.splitlines():
    match = re.fullmatch(r"\| `([^`]+)` \| (\d+) \| `([a-f0-9]{64})` \|", line)
    if match:
        name, length, sha = match.groups()
        data = (base / name).read_bytes()
        assert len(data) == int(length) and hashlib.sha256(data).hexdigest() == sha
        inputs += 1
    if not re.match(r"\| R\d{2} \| \[", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    target = re.search(r"\]\(([^)]+)\)", fields[2]).group(1)
    content = (base / target).read_bytes()
    sha = fields[4].strip("`")
    assert len(content) == int(fields[3]) and hashlib.sha256(content).hexdigest() == sha
    parser = Tables()
    source = content.decode("utf-8")
    parser.feed(source)
    assert len(parser.tables) == 4 and len(parser.tables[0]) == 73
    normalized = [[[''.join(cell[1].split()) for cell in row] for row in table] for table in parser.tables]
    assert normalized[0] == normalized[2] and normalized[1] == normalized[3]
    originals[fields[0]] = (sha, len(content), parser.tables, source)
assert inputs == 5 and len(originals) == 7
assert sum(item[1] for item in originals.values()) == 2664666
prep = json.loads((base / "evidence-13-preparation/preparation.json").read_text(encoding="utf-8"))
candidates = {doc["artifact_sha256"]: doc["parsed"]["scalars"] for doc in documents(prep)
              if doc.get("family") == "nbs_industrial_value_added" and "parsed" in doc}
assert len(candidates) == 7 and sum(map(len, candidates.values())) == 20
verified = []
times = 0
for line in text.splitlines():
    time_match = re.match(r"\| (R\d{2}) \| (\d{4}/\d{2}/\d{2} \d{2}:\d{2}) \|", line)
    if time_match:
        reference, stamp = time_match.groups()
        source = originals[reference][3]
        assert stamp in source.splitlines()[10] and stamp in source.splitlines()[276]
        times += 1
    if not re.match(r"\| \d{2} \| R\d{2} /", line):
        continue
    fields = [item.strip() for item in line.split("|")[1:-1]]
    reference, period = fields[1].split(" / ")
    sha, _, tables, _ = originals[reference]
    table, row, column, source_line = map(int, re.fullmatch(r"T(\d+) R(\d+) C(\d+) L(\d+)", fields[3]).groups())
    cell = tables[table-1][row-1][column-1]
    assert cell[0] == source_line
    expected = Decimal(fields[4])
    assert Decimal(''.join(cell[1].split())) == expected == Decimal(fields[5])
    measure = fields[2]
    year, month = map(int, period.split("-"))
    if measure == "mom_seasonally_adjusted":
        assert table == 2 and column == 2
        assert ''.join(tables[1][row-1][0][1].split()) == f"{month}月"
    else:
        assert table == 1 and row == 3
        assert "规模以上工业增加值" in ''.join(tables[0][2][0][1].split())
        assert column == (3 if measure == "current_month_real_yoy" or period == "2026-02" else 5)
    selected = [item for item in candidates[sha] if item["metric_id"] == "CN_INDUSTRIAL_VA" and item["dimensions"] == {"measure": measure}]
    assert len(selected) == 1
    candidate = selected[0]
    kind = "year_to_month" if measure == "ytd_real_yoy" else "month"
    field = {"current_month_real_yoy": "industrial_va_yoy_real_pct", "ytd_real_yoy": "industrial_va_ytd_yoy_real_pct", "mom_seasonally_adjusted": "industrial_va_mom_sa_pct"}[measure]
    assert candidate["source_field"] == field and candidate["unit"] == "percent" and candidate["period_kind"] == kind
    assert candidate["period_start"] == (f"{year}-01-01" if kind == "year_to_month" else f"{period}-01")
    assert candidate["period_end"] == f"{period}-{calendar.monthrange(year, month)[1]}"
    assert Decimal(str(candidate["value"])) == expected
    verified.append((sha, measure, period))
assert len(set(verified)) == 20 and times == 7
print(json.dumps({"verified_cells": 20, "conflicts": 0, "originals": 7, "original_bytes": 2664666,
                  "local_links": len(links), "input_fingerprints": inputs, "source_time_labels": times,
                  "report_bytes": len(raw), "report_sha256": hashlib.sha256(raw).hexdigest(),
                  "scope": "raw HTML cell lines, identity, period, unit, literal and page time label",
                  "network_requests": 0, "application_parser_calls": 0}, indent=2))
